"""
Tests W1 — Salidas de plomo a Willard.

Lo que se vigila de verdad:
- El abono de bateria baja DOS contadores por la MISMA cantidad, y el de
  material no toca `intersede`. Es la regla que costo media reunion entender y
  la que ningun gate automatico habria descubierto.
- La factura de maquila/flete FRAGMENTA por sede (D4b): sin eso, Circunvalar
  —la sede que factura y se queda con la parte mayor— apareceria con puro costo.
- El par del reparto emite con `internal_maquila_enabled` APAGADO (D11): SAC
  apaga ese flag para que el traslado deje de cobrar, y si compartieran el gate
  apagarlo mataria tambien el reparto.
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

    `internal_maquila_enabled` queda APAGADO a proposito: es el estado en el que
    va a correr SAC (Hugo, 24-ago: la maquila se cobra en la entrega, no en el
    traslado). Que todos los tests de efectos pasen asi ES la prueba de D11.
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
    """Los numeros de Hugo: $1.500 facturados, de los cuales $600 van a planta."""
    return {
        "maquila": _tariff(db_session, test_organization.id, test_user.id, "maquila_willard", 1500),
        "flete": _tariff(db_session, test_organization.id, test_user.id, "flete_willard_planta_planta", 200),
        "abono": _tariff(db_session, test_organization.id, test_user.id, "abono_planta_por_kg", 600),
    }


@pytest.fixture
def plomo(db_session, test_organization, client, org_headers, wh_jm):
    """Plomo refinado en Juan Mina: 100 kg @ $2.000. Sin formula -> ya es plomo."""
    cat = create_material_category(db_session, test_organization.id, "Plomo")
    mat = create_material(db_session, test_organization.id, "PB-01", "Plomo Fino", cat.id)
    mat.default_unit = "kg"
    db_session.commit()
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
            "lines": [{"material_id": str(plomo.id), "quantity": qty}],
        },
    )
    assert resp.status_code == expect, resp.text
    return resp.json()


def _flow(client, headers, wh, willard, plomo, dtype, qty="50", price=None):
    """Registrar -> revisar -> liquidar."""
    d = _create(client, headers, wh, willard, plomo, dtype, qty)
    r = client.post(f"{URL}/{d['id']}/review", headers=headers)
    assert r.status_code == 200, r.text
    body = {"line_prices": []}
    if dtype == "venta":
        body["line_prices"] = [
            {"line_id": r.json()["lines"][0]["id"], "unit_price": str(price or 3000)}
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
        # 50 kg x $1.500 maquila + 50 x $200 flete
        assert Decimal(str(body["maquila_amount"])) == Decimal("75000.00")
        assert Decimal(str(body["freight_amount"])) == Decimal("10000.00")
        mms = _mms(db_session, test_organization.id, "service_income_accrual")
        assert len(mms) == 2
        assert all(m.account_id is None for m in mms), "es causado: sin cuenta"
        db_session.refresh(willard)
        assert willard.current_balance == before + Decimal("85000.00")

    def test_factura_no_entra_al_cash_flow(self):
        """La trampa de #86: el flujo de caja suma por tipo sin filtrar cuenta
        NULL, asi que un causado en INFLOW_TYPES inflaria plata que nadie
        recibio."""
        from app.services.reports import INFLOW_TYPES, OUTFLOW_TYPES

        assert "service_income_accrual" not in INFLOW_TYPES
        assert "service_income_accrual" not in OUTFLOW_TYPES

    def test_par_entrega_emite_con_flag_maquila_apagado(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, willard, plomo, tarifas, acc_intersede,
    ):
        """D11 — el reparto NO se gatea con `internal_maquila_enabled`.

        Ese flag apaga el cobro del TRASLADO (que segun Hugo cobra en el momento
        equivocado). Si compartieran el gate, apagarlo mataria tambien esto y
        quedaria el modo de falla de #94/#99: 'el guard funciona' y 'lo apague
        para todos' viendose identicos. El fixture lo deja en False.
        """
        body = _flow(client, org_headers, wh_jm, willard, plomo, "venta")
        assert Decimal(str(body["plant_credit_amount"])) == Decimal("30000.00")

        exp = _mms(db_session, test_organization.id, "internal_maquila_expense")
        inc = _mms(db_session, test_organization.id, "internal_maquila_income")
        assert len(exp) == 1 and len(inc) == 1
        assert exp[0].warehouse_id == wh_cv.id, "Circunvalar paga"
        assert inc[0].warehouse_id == wh_jm.id, "Juan Mina recibe"
        assert exp[0].transfer_pair_id == inc[0].id

    def test_par_reparto_no_mueve_cuentas(
        self, client, org_headers, db_session, test_organization,
        wh_jm, willard, plomo, tarifas, acc_intersede,
    ):
        _flow(client, org_headers, wh_jm, willard, plomo, "venta")
        for mtype in ("internal_maquila_expense", "internal_maquila_income"):
            for mm in _mms(db_session, test_organization.id, mtype):
                assert mm.account_id is None
                assert mm.third_party_id is None

    def test_sin_setting_sede_facturacion_no_emite_par(
        self, client, org_headers, db_session, test_organization,
        wh_jm, willard, plomo, tarifas, acc_intersede,
    ):
        """D4c: default inerte. Sin sede configurada no hay a quien abonarle."""
        test_organization.settings = {
            **test_organization.settings, "willard_sede_facturacion": None
        }
        db_session.commit()
        body = _flow(client, org_headers, wh_jm, willard, plomo, "venta")
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
        wh_cv, wh_jm, willard, plomo, tarifas, acc_intersede,
    ):
        """Los numeros del cliente: Circunvalar factura y le abona a planta.

        Sin fragmentar, Circunvalar —la sede que gana— apareceria en rojo con
        puro costo, sin error y sin warning.
        """
        _flow(client, org_headers, wh_jm, willard, plomo, "venta")

        cv = self._pnl(client, org_headers, wh_cv.id)
        jm = self._pnl(client, org_headers, wh_jm.id)

        # Circunvalar: factura 85.000 (maquila+flete) y abona 30.000 a planta
        assert Decimal(str(cv["service_income"])) == Decimal("85000.00")
        assert Decimal(str(cv["internal_maquila_expense"])) == Decimal("30000.00")
        # Juan Mina: recibe el abono, no factura
        assert Decimal(str(jm["service_income"])) == 0
        assert Decimal(str(jm["internal_maquila_income"])) == Decimal("30000.00")

    def test_drilldown_service_income_cuadra_con_pnl(
        self, client, org_headers, db_session, test_organization,
        wh_jm, willard, plomo, tarifas, acc_intersede,
    ):
        """La promesa de #49: la suma del listado destino == el numero del P&L.

        Este test existe porque el escenario de `test_pnl_drilldown_parity` NO
        tiene datos de W1: alli el cambio a CSV pasa verde sin ejercitarse. El
        guardrail hay que ponerlo donde SI hay una factura de Salida.
        """
        _flow(client, org_headers, wh_jm, willard, plomo, "venta")
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
        wh_cv, wh_jm, willard, plomo, tarifas, acc_intersede,
    ):
        """El par netea $0 y la factura entera aparece una sola vez."""
        _flow(client, org_headers, wh_jm, willard, plomo, "venta")
        total = self._pnl(client, org_headers)
        assert Decimal(str(total["service_income"])) == Decimal("85000.00")
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
                "lines": [{"material_id": str(plomo.id), "quantity": "10"}],
            },
        )
        assert r.status_code == 400
        assert "planta" in r.json()["detail"].lower()

    def test_peso_obligatorio_al_revisar(
        self, client, org_headers, db_session, test_organization, wh_jm, willard
    ):
        """#95 Q-13: opcional al capturar, obligatorio al revisar. Un material
        por UNIDAD no autocompleta el peso."""
        cat = create_material_category(db_session, test_organization.id, "Bat")
        mat = create_material(db_session, test_organization.id, "BAT-9", "Bateria", cat.id)
        mat.default_unit = "unidad"
        db_session.commit()
        d = _create(client, org_headers, wh_jm, willard, mat, "abono_bateria", qty="5")
        r = client.post(f"{URL}/{d['id']}/review", headers=org_headers)
        assert r.status_code == 400
        assert "báscula" in r.json()["detail"] or "bascula" in r.json()["detail"]

    def test_peso_se_autocompleta_en_kg(
        self, client, org_headers, wh_jm, willard, plomo
    ):
        """D2 de #95: el autocompletado vive en el SERVIDOR, no en la pantalla."""
        d = _create(client, org_headers, wh_jm, willard, plomo, "abono_material", qty="50")
        assert Decimal(str(d["lines"][0]["scale_weight_kg"])) == Decimal("50.0000")

    def test_editar_lineas_devuelve_a_registrada(
        self, client, org_headers, wh_jm, willard, plomo
    ):
        """D17 de #95: la revision certifica LINEAS. Editarlas la invalida."""
        d = _create(client, org_headers, wh_jm, willard, plomo, "abono_material")
        client.post(f"{URL}/{d['id']}/review", headers=org_headers)
        r = client.patch(
            f"{URL}/{d['id']}",
            headers=org_headers,
            json={"lines": [{"material_id": str(plomo.id), "quantity": "30"}]},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "draft"

    def test_editar_cabecera_conserva_revision(
        self, client, org_headers, wh_jm, willard, plomo
    ):
        d = _create(client, org_headers, wh_jm, willard, plomo, "abono_material")
        client.post(f"{URL}/{d['id']}/review", headers=org_headers)
        r = client.patch(f"{URL}/{d['id']}", headers=org_headers, json={"notes": "x"})
        assert r.status_code == 200
        assert r.json()["status"] == "reviewed"

    def test_liquidar_sin_revisar_400(
        self, client, org_headers, wh_jm, willard, plomo, tarifas, acc_drosses
    ):
        d = _create(client, org_headers, wh_jm, willard, plomo, "abono_material")
        r = client.post(f"{URL}/{d['id']}/liquidate", headers=org_headers, json={"line_prices": []})
        assert r.status_code == 400

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
        client.post(f"{URL}/{d['id']}/review", headers=org_headers)
        r = client.post(
            f"{URL}/{d['id']}/liquidate", headers=org_headers, json={"line_prices": []}
        )
        assert r.status_code == 400
        detail = r.json()["detail"]
        assert "Solo Proveedor" in detail and "Terceros" in detail

    def test_guard_maquila_nombra_el_modulo_correcto(
        self, client, org_headers, db_session, test_organization,
        wh_jm, willard, plomo, tarifas, acc_intersede,
    ):
        """D10 — el mensaje se DERIVA del source_type. Antes decia 'Anule el
        traslado desde el modulo de Traslados' hardcodeado, y con un segundo
        emisor mandaba al usuario al lugar equivocado."""
        _flow(client, org_headers, wh_jm, willard, plomo, "venta")
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
        wh_jm, willard, plomo, tarifas, acc_intersede,
    ):
        _flow(client, org_headers, wh_jm, willard, plomo, "venta")
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
        assert _mms(db_session, test_organization.id, "service_income_accrual") == []
        assert _mms(db_session, test_organization.id, "internal_maquila_expense") == []
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
