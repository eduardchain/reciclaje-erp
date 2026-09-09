"""
Tests W1 — Salidas de plomo a Willard.

Lo que se vigila de verdad:
- El abono de bateria baja DOS contadores por la MISMA cantidad, y el de
  material no toca `intersede`. Es la regla que costo media reunion entender y
  la que ningun gate automatico habria descubierto.
- La factura de maquila/flete FRAGMENTA por sede (D4b): sin eso, Circunvalar
  —la sede que factura y se queda con la parte mayor— apareceria con puro costo.
- El par del reparto emite SOLO en el abono en materiales (CC-009): en venta y
  en abono de baterias la maquila interna ya se causo AL TRASLADAR, y repetirla
  en la entrega la cobraria dos veces. El PAR de tests es la prueba — con uno
  solo, "el gate funciona" y "lo apague para todos" se ven identicos.
"""
import pytest
from decimal import Decimal

from sqlalchemy import func, select

from app.models.kg_ledger import KgLedgerAccount, KgLedgerMovement
from app.models.money_movement import MoneyMovement
from app.models.sale import Sale
from app.models.service_tariff import ServiceTariff
from app.models.warehouse import Warehouse
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    create_material,
    create_material_category,
    create_warehouse,
)

URL = "/api/v1/willard-deliveries"
ADJUST_URL = "/api/v1/inventory/adjustments"
FORMULAS_URL = "/api/v1/material-conversion-formulas"

SEED_DATE = "2026-07-01T12:00:00"
DELIVERY_DATE = "2026-07-10T12:00:00"


# --------------------------------------------------------------- fixtures ---

@pytest.fixture
def wh_cv(db_session, test_organization):
    wh = create_warehouse(db_session, test_organization.id, "Circunvalar")
    db_session.commit()
    return wh


@pytest.fixture
def wh_jm(db_session, test_organization):
    wh = create_warehouse(db_session, test_organization.id, "Juan Mina")
    db_session.commit()
    return wh


@pytest.fixture(autouse=True)
def _flags(db_session, test_organization, wh_cv, wh_jm):
    """Circunvalar factura, Juan Mina es la planta.

    `internal_maquila_enabled` queda APAGADO a proposito, pero desde CC-009 lo
    que prueba es lo CONTRARIO de lo que probaba antes. Bajo D11 demostraba
    "el par emite aunque el flag este apagado"; hoy el par gatea por TIPO, asi
    que este False es lo que hace que **re-acoplar el par al flag tumbe
    `test_par_emite_en_abono_material`** — con el flag en True ese defecto
    pasaria desapercibido. La red no desaparecio: cambio de lado.

    En produccion SAC lo tiene en True (el traslado vuelve a cobrar); aca sigue
    en False porque estos tests no ejercitan traslados y el contraste vale mas.
    """
    test_organization.settings = {
        "kg_ledger_enabled": True,
        "two_step_transfers_enabled": True,
        "internal_maquila_enabled": False,
        "willard_sede_facturacion": str(wh_cv.id),
        "willard_sede_drosses": str(wh_jm.id),
    }
    db_session.commit()


@pytest.fixture
def willard(db_session, test_organization):
    return create_third_party_with_category(
        db_session, test_organization.id, "Willard S.A", "customer"
    )


def _kg_account(db, org_id, account_type, warehouse_id=None, code=None):
    acc = KgLedgerAccount(
        organization_id=org_id,
        code=code or account_type.upper(),
        display_name=account_type,
        account_type=account_type,
        warehouse_id=warehouse_id,
        is_active=True,
    )
    db.add(acc)
    db.commit()
    return acc


@pytest.fixture
def acc_intersede(db_session, test_organization):
    return _kg_account(db_session, test_organization.id, "intersede")


@pytest.fixture
def acc_baterias(db_session, test_organization, willard, wh_cv):
    acc = KgLedgerAccount(
        organization_id=test_organization.id,
        code="WILL-BAT-CV",
        display_name="Willard Baterias CV",
        account_type="willard_baterias",
        warehouse_id=wh_cv.id,
        third_party_id=willard.id,
        is_active=True,
    )
    db_session.add(acc)
    db_session.commit()
    return acc


@pytest.fixture
def acc_drosses(db_session, test_organization, willard):
    acc = KgLedgerAccount(
        organization_id=test_organization.id,
        code="WILL-DROSS",
        display_name="Willard Drosses",
        account_type="willard_drosses",
        third_party_id=willard.id,
        is_active=True,
    )
    db_session.add(acc)
    db_session.commit()
    return acc


def _tariff(db, org_id, user_id, code, price):
    t = ServiceTariff(
        organization_id=org_id,
        tariff_code=code,
        unit_price_cop=Decimal(str(price)),
        unit="per_kg_lead",
        created_by=user_id,
    )
    db.add(t)
    db.commit()
    return t


@pytest.fixture
def tarifas(db_session, test_organization, test_user):
    """Las tarifas reales (CC-009). Willard paga $2.097 de maquila + $37 de
    flete; de esos $2.097, $1.500 se le abonan a planta y $597 quedan en
    Circunvalar (Hugo, 4-sep).

    ⚠️ Que esos $1.500 sean la MISMA tarifa que la maquila interna del traslado
    (`maquila_intersede_cv_jm`, que hoy tambien vale $1.500) NO esta confirmado:
    Hugo contesto "1500" y nada mas. Es inferencia mia, no testimonio — ver Q-29
    en control-cambios-requerimientos.md. Los numeros de este fixture son del
    cliente; su relacion entre si, no. NO unificar las dos tarifas apoyandose
    en este fixture."""
    return {
        "maquila": _tariff(db_session, test_organization.id, test_user.id, "maquila_willard", 2097),
        "flete": _tariff(db_session, test_organization.id, test_user.id, "flete_willard_planta_planta", 37),
        "abono": _tariff(db_session, test_organization.id, test_user.id, "abono_planta_por_kg", 1500),
    }


def _mark_lead(db, org_id, material, lead):
    """Marca el material como plomo entregable (#103 D1).

    Sin fila de perfil el guard bloquea (fail-closed), asi que toda fixture que
    entregue material a Willard tiene que pasar por aca.
    """
    from app.models.material_kg_profile import MaterialKgProfile

    prof = db.execute(
        select(MaterialKgProfile).where(
            MaterialKgProfile.organization_id == org_id,
            MaterialKgProfile.material_id == material.id,
        )
    ).scalar_one_or_none()
    if prof is None:
        prof = MaterialKgProfile(organization_id=org_id, material_id=material.id)
        db.add(prof)
    prof.lead_product = lead
    db.commit()
    return material


def _stock(client, headers, mat, wh, qty="100", cost="2000"):
    r = client.post(
        f"{ADJUST_URL}/increase",
        headers=headers,
        json={
            "material_id": str(mat.id),
            "warehouse_id": str(wh.id),
            "quantity": qty,
            "unit_cost": cost,
            "date": SEED_DATE,
            "reason": "Seed",
        },
    )
    assert r.status_code == 201, r.text
    return mat


@pytest.fixture
def plomo(db_session, test_organization, client, org_headers, wh_jm):
    """Plomo CRUDO en Juan Mina: 100 kg @ $2.000. Sin formula -> ya es plomo.

    Se llama "crudo" y no "fino" a proposito (#103 C3): el fino es el PURO, y
    marcarlo asi haria que ~20 tests de abono dispararan el aviso de D3 — el
    ruido taparia lo que cada test prueba. El puro vive en su propia fixture.
    """
    cat = create_material_category(db_session, test_organization.id, "Plomo")
    mat = create_material(db_session, test_organization.id, "PB-CRU", "Plomo Crudo", cat.id)
    mat.default_unit = "kg"
    db_session.commit()
    _mark_lead(db_session, test_organization.id, mat, "crudo")
    resp = client.post(
        f"{ADJUST_URL}/increase",
        headers=org_headers,
        json={
            "material_id": str(mat.id),
            "warehouse_id": str(wh_jm.id),
            "quantity": "100",
            "unit_cost": "2000",
            "date": SEED_DATE,
            "reason": "Seed",
        },
    )
    assert resp.status_code == 201, resp.text
    return mat


def _create(client, headers, wh, willard, plomo, dtype, qty="50", expect=201):
    resp = client.post(
        URL,
        headers=headers,
        json={
            "delivery_type": dtype,
            "warehouse_id": str(wh.id),
            "third_party_id": str(willard.id),
            "date": DELIVERY_DATE,
            "remission_number": "REM-1",
            "lines": [{"material_id": str(plomo.id), "quantity": qty}],
        },
    )
    assert resp.status_code == expect, resp.text
    return resp.json()


def _flow(client, headers, wh, willard, plomo, dtype, qty="50", price=None):
    """Registrar -> liquidar. El paso de revision se retiro (Hugo, 28-ago)."""
    r_create = _create(client, headers, wh, willard, plomo, dtype, qty)
    d = r_create
    body = {"line_prices": []}
    if dtype == "venta":
        body["line_prices"] = [
            {"line_id": d["lines"][0]["id"], "unit_price": str(price or 3000)}
        ]
    liq = client.post(f"{URL}/{d['id']}/liquidate", headers=headers, json=body)
    assert liq.status_code == 200, liq.text
    return liq.json()


def _kg(db, account_id) -> Decimal:
    return Decimal(str(db.execute(
        select(func.coalesce(func.sum(KgLedgerMovement.delta_kg), 0)).where(
            KgLedgerMovement.account_id == account_id,
            KgLedgerMovement.status == "confirmed",
        )
    ).scalar_one()))


def _mms(db, org_id, mtype, status="confirmed"):
    return db.execute(
        select(MoneyMovement).where(
            MoneyMovement.organization_id == org_id,
            MoneyMovement.movement_type == mtype,
            MoneyMovement.status == status,
        )
    ).scalars().all()


# ------------------------------------------------------ los tres contadores ---

class TestDescargaDeContadores:
    """La regla del cliente: dos deudas con Willard, de duenos distintos."""

    def test_venta_descarga_solo_intersede(
        self, client, org_headers, db_session, test_organization,
        wh_jm, willard, plomo, tarifas, acc_intersede, acc_baterias, acc_drosses,
    ):
        _flow(client, org_headers, wh_jm, willard, plomo, "venta")
        assert _kg(db_session, acc_intersede.id) == Decimal("-50")
        assert _kg(db_session, acc_baterias.id) == 0
        assert _kg(db_session, acc_drosses.id) == 0

    def test_abono_bateria_descarga_ambos_mismo_kg(
        self, client, org_headers, db_session, test_organization,
        wh_jm, willard, plomo, tarifas, acc_intersede, acc_baterias, acc_drosses,
    ):
        """El pago en cadena: planta -> Circunvalar -> Willard."""
        _flow(client, org_headers, wh_jm, willard, plomo, "abono_bateria")
        assert _kg(db_session, acc_baterias.id) == Decimal("-50")
        assert _kg(db_session, acc_intersede.id) == Decimal("-50")
        assert _kg(db_session, acc_drosses.id) == 0

    def test_abono_material_no_toca_intersede(
        self, client, org_headers, db_session, test_organization,
        wh_jm, willard, plomo, tarifas, acc_intersede, acc_baterias, acc_drosses,
    ):
        """Los drosses llegan derecho a planta: Circunvalar nunca estuvo."""
        _flow(client, org_headers, wh_jm, willard, plomo, "abono_material")
        assert _kg(db_session, acc_drosses.id) == Decimal("-50")
        assert _kg(db_session, acc_intersede.id) == 0
        assert _kg(db_session, acc_baterias.id) == 0


# ------------------------------------------------------------ venta vs abono ---

class TestVentaDerivada:

    def test_venta_deriva_sale_con_cogs(
        self, client, org_headers, db_session, test_organization,
        wh_jm, willard, plomo, tarifas, acc_intersede,
    ):
        body = _flow(client, org_headers, wh_jm, willard, plomo, "venta", price=3000)
        assert body["sale_id"] is not None
        sale = db_session.get(Sale, body["sale_id"])
        assert sale.status == "liquidated"
        assert sale.willard_delivery_id is not None
        assert sale.total_amount == Decimal("150000.00")   # 50 x 3.000
        assert sale.lines[0].unit_cost == Decimal("2000.00")

    def test_abono_no_deriva_sale(
        self, client, org_headers, db_session, test_organization,
        wh_jm, willard, plomo, tarifas, acc_baterias, acc_intersede,
    ):
        """Un abono no es una venta: una linea a precio cero daria PERDIDA por
        el COGS completo (#60) y ensuciaria el reporte de ventas."""
        body = _flow(client, org_headers, wh_jm, willard, plomo, "abono_bateria")
        assert body["sale_id"] is None
        assert db_session.execute(
            select(func.count()).select_from(Sale).where(
                Sale.organization_id == test_organization.id
            )
        ).scalar_one() == 0

    def test_abono_lleva_el_costo_al_pnl(
        self, client, org_headers, db_session, test_organization,
        wh_jm, willard, plomo, tarifas, acc_drosses,
    ):
        """El inventario que sale esta valorizado; sin vehiculo al P&L el activo
        bajaria sin que nada lo compense."""
        from app.models.inventory_adjustment import InventoryAdjustment

        body = _flow(client, org_headers, wh_jm, willard, plomo, "abono_material")
        adj = db_session.execute(
            select(InventoryAdjustment).where(
                InventoryAdjustment.willard_delivery_id == body["id"]
            )
        ).scalars().all()
        assert len(adj) == 1
        assert adj[0].adjustment_type == "decrease"
        # el `decrease` guarda la cantidad FIRMADA (la trampa de #93 W-1)
        assert adj[0].quantity == Decimal("-50.0000")


# ------------------------------------------------------------- facturacion ---

class TestFacturacionYReparto:

    def test_factura_maquila_y_flete_crea_cxc(
        self, client, org_headers, db_session, test_organization,
        wh_jm, willard, plomo, tarifas, acc_drosses,
    ):
        # abono, no venta: una venta ademas mueve el saldo del cliente por el
        # valor del plomo y el test dejaria de aislar la factura del servicio
        before = willard.current_balance
        body = _flow(client, org_headers, wh_jm, willard, plomo, "abono_material")
        # 50 kg x $2.097 maquila + 50 x $37 flete
        assert Decimal(str(body["maquila_amount"])) == Decimal("104850.00")
        assert Decimal(str(body["freight_amount"])) == Decimal("1850.00")
        mms = _mms(db_session, test_organization.id, "service_income_accrual")
        assert len(mms) == 2
        assert all(m.account_id is None for m in mms), "es causado: sin cuenta"
        db_session.refresh(willard)
        assert willard.current_balance == before + Decimal("106700.00")

    def test_factura_no_entra_al_cash_flow(self):
        """La trampa de #86: el flujo de caja suma por tipo sin filtrar cuenta
        NULL, asi que un causado en INFLOW_TYPES inflaria plata que nadie
        recibio."""
        from app.services.reports import INFLOW_TYPES, OUTFLOW_TYPES

        assert "service_income_accrual" not in INFLOW_TYPES
        assert "service_income_accrual" not in OUTFLOW_TYPES

    def test_par_emite_en_abono_material(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, willard, plomo, tarifas, acc_drosses,
    ):
        """CC-009 — los drosses son la UNICA rama que reparte.

        Llegan derecho a planta, asi que nunca hubo traslado y la maquila
        interna nunca se causo. Este test es la mitad viva del contraste: sin el,
        `test_par_no_emite_en_venta_ni_abono_bateria` pasaria igual con el
        mecanismo entero roto.
        """
        body = _flow(client, org_headers, wh_jm, willard, plomo, "abono_material")
        assert Decimal(str(body["plant_credit_amount"])) == Decimal("75000.00")

        exp = _mms(db_session, test_organization.id, "internal_maquila_expense")
        inc = _mms(db_session, test_organization.id, "internal_maquila_income")
        assert len(exp) == 1 and len(inc) == 1
        assert exp[0].warehouse_id == wh_cv.id, "Circunvalar paga"
        assert inc[0].warehouse_id == wh_jm.id, "Juan Mina recibe"
        assert exp[0].transfer_pair_id == inc[0].id

    @pytest.mark.parametrize("dtype", ["venta", "abono_bateria"])
    def test_par_no_emite_en_venta_ni_abono_bateria(
        self, dtype, client, org_headers, db_session, test_organization,
        wh_jm, willard, plomo, tarifas, acc_intersede, acc_baterias,
    ):
        """CC-009 — ese material paso por Circunvalar, asi que la maquila
        interna YA se causo al trasladar (Hugo, demo 28-ago: "no se le afecta
        maquila porque ya yo la maquila la tengo causada"). Emitir el par aqui
        la cobraria dos veces por el mismo kilo.

        La factura a Willard NO se toca: sigue emitiendose (Q-28 abierta).
        """
        body = _flow(client, org_headers, wh_jm, willard, plomo, dtype)
        assert Decimal(str(body["plant_credit_amount"])) == 0
        assert _mms(db_session, test_organization.id, "internal_maquila_expense") == []
        assert _mms(db_session, test_organization.id, "internal_maquila_income") == []

    @pytest.mark.parametrize(
        "dtype,facturas", [("venta", 0), ("abono_bateria", 2), ("abono_material", 2)]
    )
    def test_factura_solo_en_los_abonos(
        self, dtype, facturas, client, org_headers, db_session, test_organization,
        wh_jm, willard, plomo, tarifas, acc_intersede, acc_baterias, acc_drosses,
    ):
        """CC-009 — en una venta Willard paga el PRECIO del plomo y nada mas.

        Hugo (4-sep): "de venta normal, solamente el precio de venta. La maquila
        solamente aplica para el plomo a devolucion... el flete afecta solamente
        cuando facturamos maquila. En venta no". Facturarlas en la venta le
        cobraba $2.134/kg de mas ($2.097 + $37) e inflaba su cuenta por cobrar.
        """
        body = _flow(client, org_headers, wh_jm, willard, plomo, dtype)
        assert len(_mms(db_session, test_organization.id, "service_income_accrual")) == facturas
        esperado = Decimal("0") if dtype == "venta" else None
        if esperado is not None:
            assert Decimal(str(body["maquila_amount"])) == esperado
            assert Decimal(str(body["freight_amount"])) == esperado

    def test_par_reparto_no_mueve_cuentas(
        self, client, org_headers, db_session, test_organization,
        wh_jm, willard, plomo, tarifas, acc_drosses,
    ):
        _flow(client, org_headers, wh_jm, willard, plomo, "abono_material")
        for mtype in ("internal_maquila_expense", "internal_maquila_income"):
            for mm in _mms(db_session, test_organization.id, mtype):
                assert mm.account_id is None
                assert mm.third_party_id is None

    def test_sin_setting_sede_facturacion_no_emite_par(
        self, client, org_headers, db_session, test_organization,
        wh_jm, willard, plomo, tarifas, acc_drosses,
    ):
        """D4c: sin sede configurada no hay a quien abonarle.

        Se prueba sobre abono_material porque es la unica rama que reparte
        (CC-009); en las otras dos no hay par que suprimir y el test pasaria
        vacio.
        """
        test_organization.settings = {
            **test_organization.settings, "willard_sede_facturacion": None
        }
        db_session.commit()
        body = _flow(client, org_headers, wh_jm, willard, plomo, "abono_material")
        assert Decimal(str(body["plant_credit_amount"])) == 0
        assert _mms(db_session, test_organization.id, "internal_maquila_expense") == []

    def test_kg_se_descarga_sin_tarifa(
        self, client, org_headers, db_session, test_organization,
        wh_jm, willard, plomo, acc_drosses,
    ):
        """D4d — facturar y descargar deuda son efectos independientes. Un
        efecto fisico no puede quedar colgado de un dato de configuracion."""
        body = _flow(client, org_headers, wh_jm, willard, plomo, "abono_material")
        assert _kg(db_session, acc_drosses.id) == Decimal("-50")
        assert Decimal(str(body["maquila_amount"])) == 0


# --------------------------------------------------------------- por sede ---

class TestPorSede:

    def _pnl(self, client, headers, warehouse_id=None):
        # D21: la liquidacion se fecha con `business_today()`, no con la fecha
        # del documento — el rango tiene que cubrir HOY o el P&L sale en cero.
        from app.utils.dates import business_today

        today = business_today()
        params = f"date_from={today.isoformat()}&date_to={today.isoformat()}"
        if warehouse_id:
            params += f"&warehouse_id={warehouse_id}"
        r = client.get(f"/api/v1/reports/profit-and-loss?{params}", headers=headers)
        assert r.status_code == 200, r.text
        return r.json()

    def test_factura_fragmenta_por_sede(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, willard, plomo, tarifas, acc_drosses,
    ):
        """Los numeros del cliente: Circunvalar factura y le abona a planta.

        Sin fragmentar, Circunvalar —la sede que gana— apareceria en rojo con
        puro costo, sin error y sin warning. Sobre abono_material, que desde
        CC-009 es la unica rama con reparto.
        """
        _flow(client, org_headers, wh_jm, willard, plomo, "abono_material")

        cv = self._pnl(client, org_headers, wh_cv.id)
        jm = self._pnl(client, org_headers, wh_jm.id)

        # Circunvalar: factura 106.700 (maquila+flete) y abona 75.000 a planta
        assert Decimal(str(cv["service_income"])) == Decimal("106700.00")
        assert Decimal(str(cv["internal_maquila_expense"])) == Decimal("75000.00")
        # Juan Mina: recibe el abono, no factura
        assert Decimal(str(jm["service_income"])) == 0
        assert Decimal(str(jm["internal_maquila_income"])) == Decimal("75000.00")

    def test_drilldown_service_income_cuadra_con_pnl(
        self, client, org_headers, db_session, test_organization,
        wh_jm, willard, plomo, tarifas, acc_drosses,
    ):
        """La promesa de #49: la suma del listado destino == el numero del P&L.

        Este test existe porque el escenario de `test_pnl_drilldown_parity` NO
        tiene datos de W1: alli el cambio a CSV pasa verde sin ejercitarse. El
        guardrail hay que ponerlo donde SI hay una factura de Salida.
        """
        # abono_material: desde CC-009 la venta no factura, y con cero de los
        # dos lados el test pasaria vacio sin ejercitar nada
        _flow(client, org_headers, wh_jm, willard, plomo, "abono_material")
        pnl = self._pnl(client, org_headers)

        from app.utils.dates import business_today

        today = business_today().isoformat()
        r = client.get(
            "/api/v1/money-movements/",
            headers=org_headers,
            params={
                "date_from": today,
                "date_to": today,
                "movement_type": "service_income,service_income_accrual",
                "status": "confirmed",
                "limit": 1000,
            },
        )
        assert r.status_code == 200, r.text
        items = r.json()["items"] if isinstance(r.json(), dict) else r.json()
        listing = sum(Decimal(str(m["amount"])) for m in items)
        assert listing == Decimal(str(pnl["service_income"])), (
            f"drill-down: P&L={pnl['service_income']}, listado={listing}"
        )

    def test_consolidado_invariante_con_y_sin_sede(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, willard, plomo, tarifas, acc_drosses,
    ):
        """El par netea $0 y la factura entera aparece una sola vez."""
        _flow(client, org_headers, wh_jm, willard, plomo, "abono_material")
        total = self._pnl(client, org_headers)
        assert Decimal(str(total["service_income"])) == Decimal("106700.00")
        cv = self._pnl(client, org_headers, wh_cv.id)
        jm = self._pnl(client, org_headers, wh_jm.id)
        assert (
            Decimal(str(cv["service_income"])) + Decimal(str(jm["service_income"]))
            == Decimal(str(total["service_income"]))
        )


    def test_costo_del_abono_fragmenta_por_sede(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, willard, plomo, tarifas, acc_intersede, acc_drosses,
    ):
        """Ronda 2 de QA — el ingreso y el costo del MISMO hecho, en la misma sede.

        El abono saca 50 kg de plomo a $2.000 = $100.000 de costo, contra un
        reparto que es una tarifa por kg. Con el costo org-level, el P&L de Juan
        Mina —la sede que ENTREGA— mostraba utilidad donde hay perdida, y el
        hueco no se veia desde ninguna de las dos sedes.
        """
        _flow(client, org_headers, wh_jm, willard, plomo, "abono_material")

        jm = self._pnl(client, org_headers, wh_jm.id)
        cv = self._pnl(client, org_headers, wh_cv.id)

        # El plomo salio de planta: su costo es de planta.
        assert Decimal(str(jm["adjustment_net"])) == Decimal("-100000.00")
        assert Decimal(str(cv["adjustment_net"])) == 0

    def test_costo_del_abono_no_se_cuenta_dos_veces(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, willard, plomo, tarifas, acc_intersede, acc_drosses,
    ):
        """El invariante del arreglo: el costo aterriza en UNA sede y la suma reconcilia.

        ⚠️ Este test NO prueba el gate `by_sede` — plantando el defecto pasa
        igual, porque sin el gate el bloque no duplica: suma CERO
        (`warehouse_id == None` degenera en `IS NULL` sobre una columna NOT
        NULL). Lo que si prueba, y es lo que importa, es que el consolidado no
        cambia y que `cv + jm == total`."""
        _flow(client, org_headers, wh_jm, willard, plomo, "abono_material")

        total = self._pnl(client, org_headers)
        assert Decimal(str(total["adjustment_net"])) == Decimal("-100000.00")

        cv = self._pnl(client, org_headers, wh_cv.id)
        jm = self._pnl(client, org_headers, wh_jm.id)
        assert (
            Decimal(str(cv["adjustment_net"])) + Decimal(str(jm["adjustment_net"]))
            == Decimal(str(total["adjustment_net"]))
        )


# ----------------------------------------------------------------- guards ---

class TestGuards:

    def test_sin_flag_403(
        self, client, org_headers, db_session, test_organization, wh_jm, willard, plomo
    ):
        test_organization.settings = {**test_organization.settings, "kg_ledger_enabled": False}
        db_session.commit()
        r = client.get(URL, headers=org_headers)
        assert r.status_code == 403

    def test_salida_desde_otra_sede_bloquea(
        self, client, org_headers, wh_cv, willard, plomo
    ):
        """D8 — Hugo: 'drosses nunca sale de Circunvalar, siempre de Juan Mina'."""
        r = client.post(
            URL,
            headers=org_headers,
            json={
                "delivery_type": "abono_material",
                "warehouse_id": str(wh_cv.id),
                "third_party_id": str(willard.id),
                "date": DELIVERY_DATE,
                "remission_number": "REM-1",
                "lines": [{"material_id": str(plomo.id), "quantity": "10"}],
            },
        )
        assert r.status_code == 400
        assert "planta" in r.json()["detail"].lower()

    def test_peso_obligatorio_al_liquidar(
        self, client, org_headers, db_session, test_organization, wh_jm, willard
    ):
        """#95 Q-13 sigue vivo: opcional al capturar, obligatorio antes de que se
        muevan kg y pesos. Al retirarse el paso de revision (Hugo, 28-ago) la
        certificacion se mudo a la liquidacion — no se perdio. Un material por
        UNIDAD no autocompleta el peso."""
        cat = create_material_category(db_session, test_organization.id, "Bat")
        mat = create_material(db_session, test_organization.id, "BAT-9", "Bateria", cat.id)
        mat.default_unit = "unidad"
        db_session.commit()
        _mark_lead(db_session, test_organization.id, mat, "crudo")
        d = _create(client, org_headers, wh_jm, willard, mat, "abono_bateria", qty="5")
        r = client.post(
            f"{URL}/{d['id']}/liquidate", headers=org_headers, json={"line_prices": []}
        )
        assert r.status_code == 400
        assert "báscula" in r.json()["detail"] or "bascula" in r.json()["detail"]

    def test_peso_se_autocompleta_en_kg(
        self, client, org_headers, wh_jm, willard, plomo
    ):
        """D2 de #95: el autocompletado vive en el SERVIDOR, no en la pantalla."""
        d = _create(client, org_headers, wh_jm, willard, plomo, "abono_material", qty="50")
        assert Decimal(str(d["lines"][0]["scale_weight_kg"])) == Decimal("50.0000")

    def test_se_liquida_directo_sin_paso_de_revision(
        self, client, org_headers, wh_jm, willard, plomo, tarifas, acc_drosses
    ):
        """Hugo, demo 28-ago: "esto funciona muy diferente porque inmediatamente
        queda la deuda: registrado y liquidar". Antes esto daba 400 exigiendo una
        revision; ahora es el camino normal. Si alguien reintroduce el paso, este
        test cae."""
        d = _create(client, org_headers, wh_jm, willard, plomo, "abono_material")
        assert d["status"] == "draft"
        r = client.post(
            f"{URL}/{d['id']}/liquidate", headers=org_headers, json={"line_prices": []}
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "liquidated"

    def test_la_ruta_de_revision_ya_no_existe(
        self, client, org_headers, wh_jm, willard, plomo
    ):
        """El endpoint se retiro, no se dejo respondiendo 400: una ruta viva que
        siempre falla es superficie que no hace nada y no avisa."""
        d = _create(client, org_headers, wh_jm, willard, plomo, "abono_material")
        r = client.post(f"{URL}/{d['id']}/review", headers=org_headers)
        assert r.status_code in (404, 405), r.status_code

    def test_remision_obligatoria(
        self, client, org_headers, wh_jm, willard, plomo
    ):
        """Hugo, demo 28-ago: "que no te deje avanzar sin digitar el numero" —
        y el motivo no es formal: "para que no me alteren el consecutivo". La
        remision es el numero con el que el concilia con Willard."""
        base = {
            "delivery_type": "abono_material",
            "warehouse_id": str(wh_jm.id),
            "third_party_id": str(willard.id),
            "date": DELIVERY_DATE,
            "lines": [{"material_id": str(plomo.id), "quantity": "10"}],
        }
        assert client.post(URL, headers=org_headers, json=base).status_code == 422
        # Vacia tampoco: seria la misma ausencia con otra forma.
        assert client.post(
            URL, headers=org_headers, json={**base, "remission_number": "  "}
        ).status_code in (400, 422)
        r = client.post(URL, headers=org_headers, json={**base, "remission_number": "R-77"})
        assert r.status_code == 201, r.text
        assert r.json()["remission_number"] == "R-77"

    def test_no_se_puede_borrar_la_remision_editando(
        self, client, org_headers, wh_jm, willard, plomo
    ):
        """La obligatoriedad del create no debe poder esquivarse por el PATCH."""
        d = _create(client, org_headers, wh_jm, willard, plomo, "abono_material")
        r = client.patch(f"{URL}/{d['id']}", headers=org_headers, json={"remission_number": ""})
        assert r.status_code == 422, r.text

    def test_venta_a_no_cliente_avisa_donde_arreglarlo(
        self, client, org_headers, db_session, test_organization,
        wh_jm, plomo, tarifas, acc_intersede,
    ):
        """Encontrado en el smoke: Willard estaba sembrado solo como proveedor y
        la venta reventaba con "El tercero no es cliente" desde adentro de la
        venta derivada — cierto, pero sin decir donde arreglarlo."""
        proveedor = create_third_party_with_category(
            db_session, test_organization.id, "Solo Proveedor", "material_supplier"
        )
        db_session.commit()
        d = _create(client, org_headers, wh_jm, proveedor, plomo, "venta")
        r = client.post(
            f"{URL}/{d['id']}/liquidate", headers=org_headers, json={"line_prices": []}
        )
        assert r.status_code == 400
        detail = r.json()["detail"]
        assert "Solo Proveedor" in detail and "Terceros" in detail

    def test_guard_maquila_nombra_el_modulo_correcto(
        self, client, org_headers, db_session, test_organization,
        wh_jm, willard, plomo, tarifas, acc_drosses,
    ):
        """D10 — el mensaje se DERIVA del source_type. Antes decia 'Anule el
        traslado desde el modulo de Traslados' hardcodeado, y con un segundo
        emisor mandaba al usuario al lugar equivocado."""
        _flow(client, org_headers, wh_jm, willard, plomo, "abono_material")
        mm = _mms(db_session, test_organization.id, "internal_maquila_expense")[0]
        r = client.post(
            f"/api/v1/money-movements/{mm.id}/annul",
            headers=org_headers,
            json={"reason": "prueba"},
        )
        assert r.status_code == 422
        assert "Salidas a Willard" in r.json()["detail"]
        assert "Traslados" not in r.json()["detail"]

    def test_factura_no_se_anula_desde_tesoreria(
        self, client, org_headers, db_session, test_organization,
        wh_jm, willard, plomo, tarifas, acc_drosses,
    ):
        # abono: desde CC-009 la venta no factura, y sin factura no hay que anular
        _flow(client, org_headers, wh_jm, willard, plomo, "abono_material")
        mm = _mms(db_session, test_organization.id, "service_income_accrual")[0]
        r = client.post(
            f"/api/v1/money-movements/{mm.id}/annul",
            headers=org_headers,
            json={"reason": "prueba"},
        )
        assert r.status_code == 422


# ---------------------------------------------------------------- anulacion ---

class TestAnulacion:

    def test_annul_round_trip(
        self, client, org_headers, db_session, test_organization,
        wh_jm, willard, plomo, tarifas, acc_intersede,
    ):
        """Inventario, kg, factura, par y venta vuelven al origen."""
        db_session.refresh(plomo)
        stock_before = plomo.current_stock
        balance_before = willard.current_balance

        body = _flow(client, org_headers, wh_jm, willard, plomo, "venta")
        r = client.post(
            f"{URL}/{body['id']}/annul", headers=org_headers, json={"reason": "error"}
        )
        assert r.status_code == 200
        assert r.json()["status"] == "annulled"

        db_session.expire_all()
        db_session.refresh(plomo)
        db_session.refresh(willard)
        assert plomo.current_stock == stock_before
        assert willard.current_balance == balance_before
        assert _kg(db_session, acc_intersede.id) == 0
        sale = db_session.get(Sale, body["sale_id"])
        assert sale.status == "cancelled"

    def test_annul_abono_devuelve_inventario(
        self, client, org_headers, db_session, test_organization,
        wh_jm, willard, plomo, tarifas, acc_drosses,
    ):
        db_session.refresh(plomo)
        stock_before = plomo.current_stock
        body = _flow(client, org_headers, wh_jm, willard, plomo, "abono_material")
        r = client.post(f"{URL}/{body['id']}/annul", headers=org_headers, json={"reason": "error de captura"})
        assert r.status_code == 200, r.text
        db_session.expire_all()
        db_session.refresh(plomo)
        assert plomo.current_stock == stock_before
        assert _kg(db_session, acc_drosses.id) == 0
        # factura y par se revierten con la salida (aca SI hay ambos, CC-009)
        assert _mms(db_session, test_organization.id, "service_income_accrual") == []
        assert _mms(db_session, test_organization.id, "internal_maquila_expense") == []
        assert _mms(db_session, test_organization.id, "internal_maquila_income") == []


# ------------------------------------------ los warnings, que nadie veia ---

class TestWarningsDeLiquidacion:
    """Tres defectos de la misma familia, encontrados en la 2a pasada de QA.

    El tercero es el que los vuelve importantes: el servicio calculaba
    warnings y el endpoint hacia `response.notes = (response.notes or "")`
    — se asignaba a si mismo. Ninguno llegaba nunca al usuario. O sea que
    el warning del invariante de abajo habria nacido muerto y nosotros
    lo habriamos reportado como mitigacion.
    """

    def test_la_venta_no_pide_anular_una_salida_perfecta(
        self, client, org_headers, wh_jm, willard, plomo, _flags,
        db_session, test_organization, test_user, acc_intersede,
    ):
        """Sin tarifa de maquila, una VENTA no debe advertir nada.

        En venta no se factura por diseno (CC-009), asi que el warning de
        'configurela y anule/rehaga la salida' le pedia deshacer algo que
        estaba bien. Familia de #100 D10. Ojo: este test corre SIN el
        fixture `tarifas` — esa ausencia es el escenario.
        """
        out = _flow(client, org_headers, wh_jm, willard, plomo, "venta")

        assert out["warnings"] == []
        assert Decimal(str(out["maquila_amount"])) == 0
        assert Decimal(str(out["freight_amount"])) == 0

    def test_el_abono_si_avisa_cuando_falta_la_tarifa(
        self, client, org_headers, wh_jm, willard, plomo, _flags,
        db_session, test_organization, test_user, acc_drosses,
    ):
        """El contraste del anterior: en un abono el aviso SI corresponde.

        Sin este par, 'el gate funciona' y 'mate el warning para todos' se
        ven identicos — la leccion de #94/#99.
        """
        out = _flow(client, org_headers, wh_jm, willard, plomo, "abono_material")

        assert any("maquila_willard" in w for w in out["warnings"]), out["warnings"]
        assert any("flete_willard" in w for w in out["warnings"]), out["warnings"]

    def test_abono_a_planta_mayor_que_la_maquila_avisa_y_no_bloquea(
        self, client, org_headers, wh_jm, willard, plomo, _flags,
        db_session, test_organization, test_user, acc_drosses,
    ):
        """Q-27 volvio el abono una TAJADA de la maquila, y nada lo verificaba.

        Con la maquila en $1.000 y el abono en $1.500, Circunvalar le abona a
        planta mas de lo que le facturo a Willard: la sede que factura queda
        en perdida, en silencio. Es #100 D13 por la otra puerta.

        El numero importa, no solo que falle: 50 kg x $1.500 = $75.000 de
        abono contra 50 kg x $1.000 = $50.000 de factura.
        """
        _tariff(db_session, test_organization.id, test_user.id, "maquila_willard", 1000)
        _tariff(db_session, test_organization.id, test_user.id, "flete_willard_planta_planta", 37)
        _tariff(db_session, test_organization.id, test_user.id, "abono_planta_por_kg", 1500)

        out = _flow(client, org_headers, wh_jm, willard, plomo, "abono_material")

        aviso = [w for w in out["warnings"] if "supera la maquila" in w]
        assert len(aviso) == 1, out["warnings"]
        assert "75.000" in aviso[0] and "50.000" in aviso[0], aviso[0]

        # avisa, NO bloquea (#17/#76): el reparto se emite igual
        assert Decimal(str(out["plant_credit_amount"])) == Decimal("75000.00")
        assert len(_mms(db_session, test_organization.id, "internal_maquila_expense")) == 1

    def test_con_tarifas_sanas_no_hay_ruido(
        self, client, org_headers, wh_jm, willard, plomo, _flags, tarifas,
        db_session, test_organization, acc_drosses,
    ):
        """$1.500 de abono contra $2.097 de maquila: el invariante se cumple.

        Sin este, un warning que se disparara siempre pasaria por bueno.
        """
        out = _flow(client, org_headers, wh_jm, willard, plomo, "abono_material")

        assert out["warnings"] == [], out["warnings"]


# ------------------------------------- guard de material entregable (#103) ---
#
# El defecto que cierra: una salida aceptaba CUALQUIER material. En dev entraron
# 1.000 kg de guarru seco de Willard y el MISMO material salio como abono — SAC
# no fundio nada y el sistema facturo $1,5M de maquila (el cobro POR FUNDIR),
# flete, y abono a planta por un trabajo que no ocurrio. Sin un aviso.
#
# La causa: `_compute_lead_kg` usaba una heuristica de CALCULO ("sin formula el
# material ya es plomo") como CLASIFICADOR. 15 materiales activos pasaban como
# plomo 1:1, entre ellos aluminio, hierro y cajas plasticas.
#
# El cuadrante que cubren estos tests — dibujado, no enumerado, porque en prosa
# se declaro cubierto tres veces con una celda vacia:
#
#                  | plomo marcado          | no plomo
#     sin formula  | test 2  (crudo)        | test 7  (plastico)
#     con formula  | test 9  (crudo+form.)  | test 1  (guarru)

@pytest.fixture
def puro(db_session, test_organization, client, org_headers, wh_jm):
    """Plomo PURO: pasa el guard, pero avisa si se usa para abonar."""
    cat = create_material_category(db_session, test_organization.id, "Plomo")
    mat = create_material(db_session, test_organization.id, "PB-PUR", "Plomo Puro", cat.id)
    mat.default_unit = "kg"
    db_session.commit()
    _mark_lead(db_session, test_organization.id, mat, "puro")
    return _stock(client, org_headers, mat, wh_jm)


@pytest.fixture
def plastico(db_session, test_organization, client, org_headers, wh_jm):
    """CAJAS PLASTICAS: SIN formula y sin marca. Es el material que hoy saldaba
    la deuda de plomo 1:1 — la celda que la heuristica dejaba pasar."""
    cat = create_material_category(db_session, test_organization.id, "Plomo")
    mat = create_material(db_session, test_organization.id, "CAJ-PLA", "Cajas Plasticas", cat.id)
    mat.default_unit = "kg"
    db_session.commit()
    _mark_lead(db_session, test_organization.id, mat, "none")
    return _stock(client, org_headers, mat, wh_jm)


@pytest.fixture
def guarru(db_session, test_organization, client, org_headers, wh_jm):
    """GUARRU SECO: CON formula (72% de plomo) y sin marca. Es de lo que SE
    EXTRAE plomo, o sea justo lo que NO puede pagar la deuda."""
    cat = create_material_category(db_session, test_organization.id, "Drosses")
    mat = create_material(db_session, test_organization.id, "MR-02", "Guarru Seco", cat.id)
    mat.default_unit = "kg"
    db_session.commit()
    _mark_lead(db_session, test_organization.id, mat, "none")
    r = client.post(FORMULAS_URL, headers=org_headers, json={
        "material_id": str(mat.id),
        "formula_type": "drosses_to_lead",
        "parameters": {"lead_percentage": 0.72},
    })
    assert r.status_code == 201, r.text
    return _stock(client, org_headers, mat, wh_jm)


@pytest.fixture
def sin_perfil(db_session, test_organization, client, org_headers, wh_jm):
    """Material SIN fila de perfil: el fail-closed de D6."""
    cat = create_material_category(db_session, test_organization.id, "Plomo")
    mat = create_material(db_session, test_organization.id, "SIN-P", "Sin Perfil", cat.id)
    mat.default_unit = "kg"
    db_session.commit()
    return _stock(client, org_headers, mat, wh_jm)


@pytest.fixture
def crudo_con_formula(db_session, test_organization, client, org_headers, wh_jm):
    """Plomo crudo CON formula de rendimiento: la cuarta celda del cuadrante.
    Hoy no existe en SAC, pero un guard `marcado AND sin formula` lo bloquearia
    el dia que alguien la cree — y ese guard pasa todos los demas tests."""
    cat = create_material_category(db_session, test_organization.id, "Plomo")
    mat = create_material(db_session, test_organization.id, "PB-CF", "Crudo Con Formula", cat.id)
    mat.default_unit = "kg"
    db_session.commit()
    _mark_lead(db_session, test_organization.id, mat, "crudo")
    r = client.post(FORMULAS_URL, headers=org_headers, json={
        "material_id": str(mat.id),
        "formula_type": "drosses_to_lead",
        "parameters": {"lead_percentage": 0.5},
    })
    assert r.status_code == 201, r.text
    return _stock(client, org_headers, mat, wh_jm)


def _walk_expecting_block(client, headers, wh, willard, mat, dtype, qty="10"):
    """Camina create -> liquidate y devuelve la PRIMERA respuesta que bloquea,
    sin importar la etapa.

    A proposito no afirma DONDE sale el 400: eso lo fijan los tests 8 y 11. Si
    este afirmara la etapa, mover el guard de sitio lo rompería y no se podria
    distinguir "el guard desaparecio" de "el guard se movio".
    """
    r = client.post(URL, headers=headers, json={
        "delivery_type": dtype,
        "warehouse_id": str(wh.id),
        "third_party_id": str(willard.id),
        "date": DELIVERY_DATE,
        "remission_number": "REM-1",
        "lines": [{"material_id": str(mat.id), "quantity": qty}],
    })
    if r.status_code >= 400:
        return r
    created = r.json()
    did = created["id"]
    body = {"line_prices": []}
    if dtype == "venta":
        body["line_prices"] = [
            {"line_id": created["lines"][0]["id"], "unit_price": "3000"}
        ]
    r = client.post(f"{URL}/{did}/liquidate", headers=headers, json=body)
    assert r.status_code >= 400, (
        "La salida se liquido entera: el guard no bloqueo en NINGUNA etapa."
    )
    return r


class TestGuardMaterialEntregable:

    def test_abono_con_material_que_no_es_plomo_bloquea(
        self, client, org_headers, wh_jm, willard, guarru, acc_drosses, tarifas
    ):
        """Test 1 — con formula / no plomo. La reproduccion exacta del hallazgo:
        guarru seco entra de Willard y sale como abono sin haberse fundido."""
        r = _walk_expecting_block(
            client, org_headers, wh_jm, willard, guarru, "abono_material"
        )
        assert r.status_code == 400, r.text
        assert "MR-02" in r.json()["detail"], r.text
        assert "plomo entregable" in r.json()["detail"]

    def test_abono_con_plomo_crudo_pasa(
        self, client, org_headers, wh_jm, willard, plomo, acc_drosses, tarifas
    ):
        """Test 2 — sin formula / plomo. La otra mitad del par: el camino bueno
        sigue vivo. Sin este, "el guard funciona" y "bloquee todo" se ven igual."""
        out = _flow(client, org_headers, wh_jm, willard, plomo, "abono_material")
        assert out["status"] == "liquidated"

    def test_venta_tambien_exige_plomo(
        self, client, org_headers, wh_jm, willard, plastico, acc_intersede, tarifas
    ):
        """Test 3 — el guard cubre los TRES tipos. La venta tambien descarga
        `intersede` por kg, asi que la misma aritmetica perversa la afecta."""
        r = _walk_expecting_block(
            client, org_headers, wh_jm, willard, plastico, "venta"
        )
        assert r.status_code == 400, r.text
        assert "CAJ-PLA" in r.json()["detail"]

    def test_puro_en_abono_avisa_y_no_bloquea(
        self, client, org_headers, wh_jm, willard, puro, acc_drosses, tarifas
    ):
        """Test 4 — el aviso de D3, leido de la RESPUESTA HTTP de liquidate.

        Leerlo del retorno del servicio es lo que dejo pasar el defecto D4d de
        #100: el servicio lo calculaba bien y el endpoint lo tiraba a la basura.
        """
        out = _flow(client, org_headers, wh_jm, willard, puro, "abono_material")
        assert out["status"] == "liquidated"
        assert any("PURO" in w for w in out["warnings"]), out["warnings"]

    def test_abono_a_tercero_ajeno_rechazado(
        self, client, org_headers, db_session, test_organization,
        wh_jm, plomo, acc_drosses,
    ):
        """Test 5a — el unico hallazgo con dano financiero silencioso: las
        cuentas kg se resuelven por `account_type`, no por el tercero del
        documento, asi que se saldaba la deuda de uno y se le facturaba a otro."""
        otro = create_third_party_with_category(
            db_session, test_organization.id, "Green Loop", "customer"
        )
        # El helper solo hace flush: sin commit, la sesion de la API no lo ve y
        # el POST responde 404 en vez de ejercitar el guard.
        db_session.commit()
        r = client.post(URL, headers=org_headers, json={
            "delivery_type": "abono_material",
            "warehouse_id": str(wh_jm.id),
            "third_party_id": str(otro.id),
            "date": DELIVERY_DATE,
            "remission_number": "REM-1",
            "lines": [{"material_id": str(plomo.id), "quantity": "10"}],
        })
        assert r.status_code == 422, r.text
        assert "Willard" in r.json()["detail"], r.text

    def test_abono_al_titular_de_la_cuenta_pasa(
        self, client, org_headers, wh_jm, willard, plomo, acc_drosses
    ):
        """Test 5b — la otra mitad del par de D7."""
        _create(client, org_headers, wh_jm, willard, plomo, "abono_material", qty="10")

    def test_material_sin_perfil_kg_bloquea(
        self, client, org_headers, wh_jm, willard, sin_perfil, acc_drosses, tarifas
    ):
        """Test 6 — fail-closed (D6): sin fila de perfil se trata como `none`.
        Bloquear con un mensaje que dice donde marcarlo es el modo de falla
        correcto; seguir calculando en silencio es el defecto."""
        r = _walk_expecting_block(
            client, org_headers, wh_jm, willard, sin_perfil, "abono_material"
        )
        assert r.status_code == 400, r.text
        assert "SIN-P" in r.json()["detail"]

    def test_material_sin_formula_que_no_es_plomo_bloquea(
        self, client, org_headers, wh_jm, willard, plastico, acc_drosses, tarifas
    ):
        """Test 7 — sin formula / no plomo. EL test que faltaba.

        Es el unico que cae con las DOS variantes del atajo prohibido. Con
        `sin formula => entregable`, los tests 1, 2 y 3 quedan verdes y las
        cajas plasticas siguen saldando la deuda 1:1 sin ningun testigo.
        """
        r = _walk_expecting_block(
            client, org_headers, wh_jm, willard, plastico, "abono_material"
        )
        assert r.status_code == 400, r.text
        assert "CAJ-PLA" in r.json()["detail"]

    def test_guard_corre_al_capturar(
        self, client, org_headers, wh_jm, willard, plastico, acc_drosses
    ):
        """Test 8 — fija la ETAPA: el rechazo sale en `create`, no despues.

        Si el guard vive solo en la liquidacion, el material equivocado se acepta
        en el patio y el error aparece dias despues, con el camion ido.
        """
        _create(
            client, org_headers, wh_jm, willard, plastico,
            "abono_material", qty="10", expect=400,
        )

    def test_plomo_marcado_con_formula_pasa_y_convierte(
        self, client, org_headers, db_session, wh_jm, willard,
        crudo_con_formula, acc_drosses, tarifas,
    ):
        """Test 9 — la cuarta celda: con formula / plomo.

        Pinta dos cosas de una: que el guard lee SOLO `lead_product` (un
        `marcado AND sin formula` bloquearia esto y pasaria los otros diez), y
        que la heuristica de calculo sigue viva — 50 kg x 0,5 = 25 kg de plomo.
        """
        out = _flow(client, org_headers, wh_jm, willard, crudo_con_formula,
                    "abono_material", qty="50")
        assert out["status"] == "liquidated"
        assert _kg(db_session, acc_drosses.id) == Decimal("-25.0000")

    def test_aviso_de_puro_llega_al_capturar(
        self, client, org_headers, wh_jm, willard, puro, acc_drosses
    ):
        """Test 10 — el aviso tambien tiene que llegar a tiempo.

        D2 y D3 son hermanos: si el guard corre en `create` pero el aviso solo
        viaja en la respuesta de `liquidate`, se descarta y el usuario se entera
        igual de tarde. El campo `warnings` tiene que estar cableado en los
        cuatro endpoints, no solo en el ultimo.
        """
        out = _create(client, org_headers, wh_jm, willard, puro,
                      "abono_material", qty="10")
        assert any("PURO" in w for w in out["warnings"]), out

    def test_guard_corre_al_editar(
        self, client, org_headers, wh_jm, willard, plomo, plastico, acc_drosses
    ):
        """Test 11 — fija la etapa de `update`, el punto de entrada que no tenia
        testigo.

        Sin este test, un validador cableado en create/liquidate pero SIN
        la llamada en `update` deja los otros diez en verde: los de flujo
        completo reciben su 400 en la liquidacion igual, el 8 valida `create`,
        que si valida, y los avisos siguen cableados. Firma vacia.

        Y es el camino mas realista de los cuatro: se registra bien, se edita
        despues, y ahi se cuela el material equivocado.
        """
        d = _create(client, org_headers, wh_jm, willard, plomo,
                    "abono_material", qty="10")
        r = client.patch(f"{URL}/{d['id']}", headers=org_headers, json={
            "lines": [{"material_id": str(plastico.id), "quantity": "10"}],
        })
        assert r.status_code == 400, r.text
        assert "CAJ-PLA" in r.json()["detail"]
