"""
Tests CC-013 — IVA y retenciones de lo que SAC factura (Q-41).

Lo que se vigila de verdad:

- **Conservacion.** Lo que el cliente deja de deber es exactamente lo que las
  entidades tienen a favor, y el IVA que se le cobra de mas es exactamente lo
  que se le debe a la DIAN. Con la FE 2127 el cliente termina debiendo
  119.335.609,11, que es el "Total a Pagar" impreso en la factura.

- **La seccion del balance, no el total** (P19). El patrimonio es residual en
  los CUATRO caminos del balance (#110), asi que un pasivo aterrizado en la
  seccion de activos deja activos −x y pasivos −x y TODO cuadra igual. Un test
  de totales es ciego a eso. Los asserts son de seccion.

- **El par sin-bandera / con-bandera.** Sin el, "el guard funciona" y "lo
  apague para todos" se ven identicos (#94/#99).

- **El control positivo del permiso** (#111): un rol que LEE en 200 antes de
  que se le niegue la escritura. Sin ese 200, el 403 puede venir de la bandera.
"""
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.security import create_access_token
from app.models.document_tax import DocumentTax
from app.models.third_party import ThirdParty
from app.models.third_party_category import ThirdPartyCategory
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    api_create_sale,
    create_material,
    create_material_category,
    create_warehouse,
)

SALES_URL = "/api/v1/sales"
ADJUST_URL = "/api/v1/inventory/adjustments"
RET_URL = "/api/v1/third-parties/retention-configs"
SEED_DATE = "2026-07-01T12:00:00"
SALE_DATE = "2026-07-10"

# Cifras de la FE 2127 (venta de PLOMO PURO a Willard, 2026-09-17).
FE_SUBTOTAL = Decimal("106028973.00")
FE_IVA = Decimal("20145504.87")
FE_RETEFUENTE = Decimal("2650724.33")
FE_RETEIVA = Decimal("3021825.73")
FE_ICA = Decimal("1166318.70")
FE_TOTAL_A_PAGAR = Decimal("119335609.11")


# --------------------------------------------------------------- fixtures ---

@pytest.fixture
def warehouse(db_session, test_organization):
    wh = create_warehouse(db_session, test_organization.id, "Circunvalar")
    db_session.commit()
    return wh


@pytest.fixture
def flag_on(db_session, test_organization):
    test_organization.settings = {"kg_ledger_enabled": True}
    db_session.commit()
    return test_organization


@pytest.fixture
def customer(db_session, test_organization):
    return create_third_party_with_category(
        db_session, test_organization.id, "Baterias Willard S.A", "customer"
    )


@pytest.fixture
def material(db_session, test_organization, client, org_headers, warehouse):
    cat = create_material_category(db_session, test_organization.id, "Plomo")
    mat = create_material(db_session, test_organization.id, "PB-PUR", "Plomo Puro", cat.id)
    mat.default_unit = "kg"
    db_session.commit()
    resp = client.post(
        f"{ADJUST_URL}/increase",
        headers=org_headers,
        json={
            "material_id": str(mat.id), "warehouse_id": str(warehouse.id),
            "quantity": "50000", "unit_cost": "2000",
            "date": SEED_DATE, "reason": "Seed",
        },
    )
    assert resp.status_code == 201, resp.text
    return mat


def _config(client, headers, tax_type, rate, *, municipality=None, concept=None,
            base_kind="subtotal"):
    body = {"retention_type": tax_type, "rate_pct": str(rate), "base_kind": base_kind}
    if municipality:
        body["municipality"] = municipality
    if concept:
        body["concept"] = concept
    r = client.post(RET_URL, headers=headers, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _sale(client, headers, customer, warehouse, material, qty="16975.5", price="6246"):
    return api_create_sale(
        client, headers,
        customer_id=customer.id, warehouse_id=warehouse.id,
        lines=[{"material_id": material.id, "quantity": qty, "unit_price": price}],
        date=SALE_DATE,
    )


def _liquidate(client, headers, sale_id, taxes=None, expect=200, **extra):
    body = {"liquidation_date": f"{SALE_DATE}T12:00:00", **extra}
    if taxes is not None:
        body["taxes"] = taxes
    r = client.patch(f"{SALES_URL}/{sale_id}/liquidate", headers=headers, json=body)
    assert r.status_code == expect, r.text
    return r.json()


def _fe_taxes():
    """Los cuatro impuestos de la FE 2127, tal como los imprime la factura."""
    return [
        {"tax_type": "iva", "rate": "19", "base_kind": "subtotal", "amount": str(FE_IVA)},
        {"tax_type": "retefuente", "rate": "2.5", "base_kind": "subtotal",
         "amount": str(FE_RETEFUENTE)},
        {"tax_type": "reteiva", "rate": "15", "base_kind": "iva",
         "amount": str(FE_RETEIVA)},
        {"tax_type": "ica", "municipality": "Barranquilla", "rate": "1.1",
         "base_kind": "subtotal", "amount": str(FE_ICA)},
    ]


def _balance(db, tp_id) -> Decimal:
    return Decimal(str(db.execute(
        select(ThirdParty.current_balance).where(ThirdParty.id == tp_id)
    ).scalar_one()))


def _tax_entities(db, org_id) -> dict[str, ThirdParty]:
    rows = db.execute(
        select(ThirdParty).where(
            ThirdParty.organization_id == org_id,
            ThirdParty.name.like("[Impuestos]%"),
        )
    ).scalars().all()
    return {tp.name: tp for tp in rows}


# ------------------------------------------------------------ T1 / T3 / T9 ---

class TestConservacion:
    """T1: la suma de los cinco efectos da CERO."""

    def test_t1_la_factura_completa_conserva(
        self, client, org_headers, db_session, test_organization,
        flag_on, customer, warehouse, material,
    ):
        sale = _sale(client, org_headers, customer, warehouse, material)
        subtotal = Decimal(str(sale["total_amount"]))
        assert subtotal == FE_SUBTOTAL, "el escenario tiene que dar el subtotal de la FE 2127"

        _liquidate(client, org_headers, sale["id"], _fe_taxes())
        db_session.expire_all()

        # El cliente queda debiendo EXACTAMENTE el "Total a Pagar" de la factura.
        assert _balance(db_session, customer.id) == FE_TOTAL_A_PAGAR

        ents = _tax_entities(db_session, test_organization.id)
        assert set(ents) == {
            "[Impuestos] IVA por Pagar",
            "[Impuestos] ReteFuente a Favor",
            "[Impuestos] ReteIVA a Favor",
            "[Impuestos] ICA a Favor Barranquilla",
        }
        # El IVA se le DEBE a la DIAN (saldo en contra); las retenciones estan
        # a favor de SAC (saldo a favor). Signos OPUESTOS, que es la razon de
        # que vivan en un mapa y no en un `if`.
        assert _balance(db_session, ents["[Impuestos] IVA por Pagar"].id) == -FE_IVA
        assert _balance(db_session, ents["[Impuestos] ReteFuente a Favor"].id) == FE_RETEFUENTE
        assert _balance(db_session, ents["[Impuestos] ReteIVA a Favor"].id) == FE_RETEIVA
        assert _balance(db_session, ents["[Impuestos] ICA a Favor Barranquilla"].id) == FE_ICA

        # Conservacion: cliente + entidades == el subtotal de siempre.
        total_entidades = sum(_balance(db_session, tp.id) for tp in ents.values())
        assert _balance(db_session, customer.id) + total_entidades == subtotal

    def test_t1d_la_RESPUESTA_del_PATCH_trae_los_impuestos(
        self, client, org_headers, db_session, test_organization,
        flag_on, customer, warehouse, material,
    ):
        """🔴 Este test nacio del smoke con POST real, no del plan.

        `SaleResponse` declaraba `taxes` y la respuesta del PATCH de liquidar
        llegaba VACIA: el endpoint arma el response campo por campo, asi que
        declararlo en el schema no basta (trampa de #95). El resto de los tests
        leia los impuestos de la BD o del GET de detalle, o sea que ninguno
        preguntaba lo que el usuario recibe — que es la leccion de #100 con el
        warning que se calculaba y nadie entregaba.

        Y se verifica tambien en el CANCEL: ahi las filas siguen viniendo, con
        su `reverted_at` poblado. `_tax_rows` no las esconde a proposito — la
        fila revertida es evidencia, igual que en las retenciones de compra.
        """
        sale = _sale(client, org_headers, customer, warehouse, material)
        liq = _liquidate(client, org_headers, sale["id"], _fe_taxes())

        assert len(liq["taxes"]) == 4, "la respuesta del liquidate llego sin impuestos"
        porTipo = {t["tax_type"]: t for t in liq["taxes"]}
        assert porTipo["iva"]["third_party_name"] == "[Impuestos] IVA por Pagar"
        assert Decimal(str(porTipo["reteiva"]["base_amount"])) == FE_IVA
        assert Decimal(str(porTipo["retefuente"]["base_amount"])) == FE_SUBTOTAL
        assert all(t["reverted_at"] is None for t in liq["taxes"])

        r = client.patch(f"{SALES_URL}/{sale['id']}/cancel", headers=org_headers)
        assert r.status_code == 200, r.text
        canceladas = r.json()["taxes"]
        assert len(canceladas) == 4
        assert all(t["reverted_at"] is not None for t in canceladas)

    def test_t3_la_base_de_la_reteiva_es_el_IVA_no_el_subtotal(
        self, client, org_headers, db_session, flag_on, customer, warehouse, material,
    ):
        """T3: sin esto, una reteIVA se guardaria como un % del subtotal y daria
        el numero correcto SOLO mientras el IVA sea 19 %."""
        sale = _sale(client, org_headers, customer, warehouse, material)
        _liquidate(client, org_headers, sale["id"], _fe_taxes())

        rows = {
            t.tax_type: t for t in db_session.execute(
                select(DocumentTax).where(DocumentTax.sale_id == sale["id"])
            ).scalars().all()
        }
        assert rows["reteiva"].base_amount == FE_IVA
        assert rows["retefuente"].base_amount == FE_SUBTOTAL
        assert rows["ica"].base_amount == FE_SUBTOTAL
        assert rows["iva"].base_amount == FE_SUBTOTAL

    def test_t3b_reteiva_sin_iva_en_la_factura_es_422(
        self, client, org_headers, flag_on, customer, warehouse, material,
    ):
        """No se puede retener IVA sobre una factura que no cobro IVA."""
        sale = _sale(client, org_headers, customer, warehouse, material)
        r = _liquidate(
            client, org_headers, sale["id"],
            [{"tax_type": "reteiva", "rate": "15", "base_kind": "iva", "amount": "100"}],
            expect=422,
        )
        assert "IVA" in str(r)

    def test_t9_montos_redondeados_por_linea_se_aceptan_y_conservan(
        self, client, org_headers, db_session, test_organization,
        flag_on, customer, warehouse, material,
    ):
        """T9: el IVA se redondea POR LINEA y se suma (D6), asi que puede
        diferir en centavos de `total x tasa`. El backend REGISTRA lo que la
        factura dice: acepta ese monto y conserva igual."""
        sale = api_create_sale(
            client, org_headers,
            customer_id=customer.id, warehouse_id=warehouse.id,
            lines=[
                {"material_id": material.id, "quantity": "1", "unit_price": "100.03"},
                {"material_id": material.id, "quantity": "1", "unit_price": "100.03"},
            ],
            date=SALE_DATE,
        )
        subtotal = Decimal(str(sale["total_amount"]))  # 200.06
        # 100,03 x 19 % = 19,0057 -> 19,01 por linea, 38,02 sumados.
        # 200,06 x 19 % = 38,0114 -> 38,01 sobre el total. Difieren en un centavo.
        por_linea = (Decimal("100.03") * Decimal("0.19")).quantize(Decimal("0.01")) * 2
        sobre_total = (subtotal * Decimal("0.19")).quantize(Decimal("0.01"))
        # Guard anti-vacuidad: si los dos criterios coinciden, el test pasa sin
        # probar nada (#110). Se afirma, no se supone del escenario.
        assert por_linea != sobre_total, "el escenario tiene que distinguir los dos criterios"

        _liquidate(client, org_headers, sale["id"], [
            {"tax_type": "iva", "rate": "19", "base_kind": "subtotal", "amount": str(por_linea)},
        ])
        db_session.expire_all()
        assert _balance(db_session, customer.id) == subtotal + por_linea
        ents = _tax_entities(db_session, test_organization.id)
        assert _balance(db_session, ents["[Impuestos] IVA por Pagar"].id) == -por_linea

    def test_t1b_dos_veces_el_mismo_impuesto_es_422(
        self, client, org_headers, flag_on, customer, warehouse, material,
    ):
        sale = _sale(client, org_headers, customer, warehouse, material)
        r = _liquidate(client, org_headers, sale["id"], [
            {"tax_type": "iva", "rate": "19", "base_kind": "subtotal", "amount": "100"},
            {"tax_type": "iva", "rate": "19", "base_kind": "subtotal", "amount": "200"},
        ], expect=422)
        assert "dos veces" in str(r)

    def test_t1c_retenciones_que_se_comen_el_total_es_422(
        self, client, org_headers, flag_on, customer, warehouse, material,
    ):
        sale = _sale(client, org_headers, customer, warehouse, material)
        _liquidate(client, org_headers, sale["id"], [
            {"tax_type": "retefuente", "rate": "100", "base_kind": "subtotal",
             "amount": str(FE_SUBTOTAL)},
        ], expect=422)


# ---------------------------------------------------------- T2 / T7 / T8 ---

class TestNoRegresionYGuards:
    """El payload ausente deja el camino actual byte a byte, y sin bandera no pasa."""

    def test_t2_sin_impuestos_la_venta_queda_igual_que_hoy(
        self, client, org_headers, db_session, test_organization,
        flag_on, customer, warehouse, material,
    ):
        """T2: con la bandera ENCENDIDA pero sin payload, cero efecto nuevo.

        Es el data-gating de #75 D9: lo que protege a las otras seis
        organizaciones no es la bandera sino que NO MANDAN nada.
        """
        sale = _sale(client, org_headers, customer, warehouse, material)
        _liquidate(client, org_headers, sale["id"])
        db_session.expire_all()

        assert _balance(db_session, customer.id) == FE_SUBTOTAL
        assert _tax_entities(db_session, test_organization.id) == {}
        assert db_session.execute(
            select(func.count(DocumentTax.id))
        ).scalar_one() == 0
        # Y la categoria de sistema tampoco nace: no se crea "por si acaso".
        assert db_session.execute(
            select(func.count(ThirdPartyCategory.id)).where(
                ThirdPartyCategory.system_code.isnot(None)
            )
        ).scalar_one() == 0

    def test_t7_sin_bandera_el_payload_se_rechaza(
        self, client, org_headers, db_session, test_organization,
        customer, warehouse, material,
    ):
        """T7 — la mitad SIN bandera del par.

        Sin este guard, una organizacion que no sea SAC podria crear terceros
        de sistema indelebles por API cruda. El contraste con T1 (que corre con
        la bandera encendida y funciona) es lo que distingue "el guard funciona"
        de "lo apague para todos" (#94/#99).
        """
        assert not (test_organization.settings or {}).get("kg_ledger_enabled")
        sale = _sale(client, org_headers, customer, warehouse, material)
        r = _liquidate(client, org_headers, sale["id"], [
            {"tax_type": "iva", "rate": "19", "base_kind": "subtotal", "amount": "100"},
        ], expect=422)
        assert "no habilitado" in str(r)
        db_session.expire_all()
        # Y no dejo rastro: ni entidad, ni fila, ni saldo movido.
        assert _tax_entities(db_session, test_organization.id) == {}
        assert db_session.execute(select(func.count(DocumentTax.id))).scalar_one() == 0

    def test_t8_liquidar_exige_permiso_y_leer_no_alcanza(
        self, client, org_headers, db_session, test_organization,
        flag_on, customer, warehouse, material,
    ):
        """T8 con CONTROL POSITIVO (#111).

        Un rol que LEE en 200 y no puede liquidar. Sin el 200, el 403 podria
        venir de la bandera o de la membresia y el test diria que el permiso
        funciona sin haberlo tocado.
        """
        from app.models.permission import Permission
        from app.models.role import Role, RolePermission
        from app.models.user import OrganizationMember, User

        sale = _sale(client, org_headers, customer, warehouse, material)

        rol = Role(
            id=uuid4(), name="solo-lee-ventas", display_name="Solo Lee Ventas",
            organization_id=test_organization.id, is_system_role=False,
        )
        db_session.add(rol)
        db_session.flush()
        perms = db_session.query(Permission).filter(
            Permission.code.in_(["sales.view", "sales.view_prices"])
        ).all()
        assert perms, "faltan permisos en el catalogo de test"
        for perm in perms:
            db_session.add(RolePermission(role_id=rol.id, permission_id=perm.id))

        lector = User(
            email="lector-impuestos@test.com", hashed_password="x",
            full_name="Lector", is_active=True,
        )
        db_session.add(lector)
        db_session.flush()
        db_session.add(OrganizationMember(
            user_id=lector.id, organization_id=test_organization.id, role_id=rol.id,
        ))
        db_session.commit()
        headers = {
            "Authorization": f"Bearer {create_access_token(data={'sub': str(lector.id)})}",
            "X-Organization-ID": str(test_organization.id),
        }

        # CONTROL POSITIVO: lee en 200.
        assert client.get(f"{SALES_URL}/{sale['id']}", headers=headers).status_code == 200
        # Y no puede liquidar, ni con impuestos ni sin ellos.
        assert client.patch(
            f"{SALES_URL}/{sale['id']}/liquidate", headers=headers,
            json={"liquidation_date": f"{SALE_DATE}T12:00:00", "taxes": _fe_taxes()},
        ).status_code == 403


# ---------------------------------------------------------------- T4 / T5 ---

class TestReportes:
    """El P&L no se mueve y el balance pone cada saldo en SU seccion."""

    def test_t4_el_pnl_no_ve_los_impuestos(
        self, client, org_headers, flag_on, customer, warehouse, material,
    ):
        """T4: el IVA no es ingreso y la retencion no es gasto (D7).

        ⚠️ El test NO compara "antes de agregar impuestos" contra "despues":
        eso agregaria una VENTA al periodo y el P&L se moveria por la venta,
        no por los impuestos. Se liquida UNA venta con impuestos y se afirma
        que cada linea vale lo que valdria sin ellos.
        """
        params = {"date_from": "2026-07-01", "date_to": "2026-07-31"}
        sale = _sale(client, org_headers, customer, warehouse, material, qty="10", price="1000")
        _liquidate(client, org_headers, sale["id"], [
            {"tax_type": "iva", "rate": "19", "base_kind": "subtotal", "amount": "1900"},
            {"tax_type": "retefuente", "rate": "2.5", "base_kind": "subtotal", "amount": "250"},
        ])
        pnl = client.get(
            "/api/v1/reports/profit-and-loss", headers=org_headers, params=params
        ).json()

        # Ingreso = el subtotal, NO el subtotal + IVA.
        assert Decimal(str(pnl["sales_revenue"])) == Decimal("10000")
        # La retencion no es gasto ni servicio.
        assert Decimal(str(pnl["operating_expenses"])) == 0
        assert Decimal(str(pnl["service_income"])) == 0
        # Utilidad bruta = ingreso − COGS (10 x $2.000), sin rastro de impuestos.
        assert Decimal(str(pnl["gross_profit_sales"])) == Decimal("-10000")
        # Y ninguna cifra de la factura aparece suelta en el estado.
        planos = {k: v for k, v in pnl.items() if isinstance(v, (int, float))}
        for monto in (1900, 250, 11900, 9750):
            assert monto not in planos.values(), f"${monto} aparece en el P&L: {planos}"

    @pytest.mark.parametrize("as_of", [None, "2026-07-31"])
    def test_t5_las_secciones_del_balance_general(
        self, client, org_headers, db_session, flag_on, customer, warehouse, material, as_of,
    ):
        """🔴 T5 afirma SECCIONES, no totales (P19).

        El patrimonio es residual en los cuatro caminos del balance (#110), asi
        que un pasivo aterrizado en la seccion de activos deja activos −x y
        pasivos −x y todo cuadra igual. Los asserts son dos: el IVA por pagar
        ESTA en el pasivo, y NO esta en la seccion de anticipos de impuestos.
        """
        sale = _sale(client, org_headers, customer, warehouse, material)
        _liquidate(client, org_headers, sale["id"], _fe_taxes())

        params = {"as_of_date": as_of} if as_of else {}
        bs = client.get("/api/v1/reports/balance-sheet", headers=org_headers, params=params).json()

        retenciones = FE_RETEFUENTE + FE_RETEIVA + FE_ICA
        assert Decimal(str(bs["assets"]["tax_advances"])) == retenciones
        # El IVA por pagar NO se colo al activo: si se colara, `tax_advances`
        # valdria `retenciones - IVA` y el patrimonio absorberia la diferencia
        # sin que ningun total lo delate.
        assert Decimal(str(bs["assets"]["tax_advances"])) != retenciones - FE_IVA
        # Y los prepagados quedan intactos: la regla nueva es ESPECIFICA de
        # impuestos, no invierte la existente.
        assert Decimal(str(bs["assets"]["prepaid_expenses"])) == 0
        # El IVA por pagar vive en el pasivo.
        assert Decimal(str(bs["liabilities"]["liability_debt"])) >= FE_IVA

    @pytest.mark.parametrize("as_of", [None, "2026-07-31"])
    def test_t5b_las_secciones_del_balance_detallado(
        self, client, org_headers, flag_on, customer, warehouse, material, as_of,
    ):
        """T5 en el OTRO clasificador. P5b existe para que corregir uno solo
        no pase en verde: son dos funciones distintas."""
        sale = _sale(client, org_headers, customer, warehouse, material)
        _liquidate(client, org_headers, sale["id"], _fe_taxes())

        params = {"as_of_date": as_of} if as_of else {}
        bd = client.get("/api/v1/reports/balance-detailed", headers=org_headers, params=params).json()

        seccion = bd["assets"]["tax_advances"]
        nombres = {i["name"] for i in seccion["items"]}
        assert nombres == {
            "[Impuestos] ReteFuente a Favor",
            "[Impuestos] ReteIVA a Favor",
            "[Impuestos] ICA a Favor Barranquilla",
        }, f"el IVA por pagar no puede estar acá: {nombres}"
        assert Decimal(str(seccion["total"])) == FE_RETEFUENTE + FE_RETEIVA + FE_ICA
        # Y esta en el pasivo, con su nombre.
        pasivo = {i["name"] for i in bd["liabilities"]["liability_debt"]["items"]}
        assert "[Impuestos] IVA por Pagar" in pasivo


# -------------------------------------------------- fixtures Salida de Plomo ---

WILLARD_URL = "/api/v1/willard-deliveries"


@pytest.fixture
def planta(db_session, test_organization):
    wh = create_warehouse(db_session, test_organization.id, "Juan Mina")
    db_session.commit()
    return wh


@pytest.fixture
def flags_willard(db_session, test_organization, planta):
    """Bandera encendida y la planta declarada: la salida sale de allá (D8 de W1)."""
    test_organization.settings = {
        "kg_ledger_enabled": True,
        "willard_sede_drosses": str(planta.id),
    }
    db_session.commit()
    return test_organization


@pytest.fixture
def willard_tp(db_session, test_organization):
    """Willard es proveedor Y cliente: entrega baterias y compra plomo."""
    tp = create_third_party_with_category(
        db_session, test_organization.id, "Willard S.A", "customer"
    )
    return tp


@pytest.fixture
def acc_intersede(db_session, test_organization):
    from app.models.kg_ledger import KgLedgerAccount

    acc = KgLedgerAccount(
        organization_id=test_organization.id, code="INTERSEDE",
        display_name="Intersede", account_type="intersede", is_active=True,
    )
    db_session.add(acc)
    db_session.commit()
    return acc


@pytest.fixture
def plomo_crudo(db_session, test_organization, client, org_headers, planta):
    from app.models.material_kg_profile import MaterialKgProfile

    cat = create_material_category(db_session, test_organization.id, "Plomo")
    mat = create_material(db_session, test_organization.id, "PB-CRU", "Plomo Crudo", cat.id)
    mat.default_unit = "kg"
    db_session.add(MaterialKgProfile(
        organization_id=test_organization.id, material_id=mat.id, lead_product="crudo",
    ))
    db_session.commit()
    r = client.post(
        f"{ADJUST_URL}/increase", headers=org_headers,
        json={
            "material_id": str(mat.id), "warehouse_id": str(planta.id),
            "quantity": "1000", "unit_cost": "2000",
            "date": SEED_DATE, "reason": "Seed",
        },
    )
    assert r.status_code == 201, r.text
    return mat


def _delivery(client, headers, planta, willard_tp, plomo_crudo, taxes=None):
    """Registra y liquida una salida tipo VENTA con impuestos."""
    r = client.post(WILLARD_URL, headers=headers, json={
        "delivery_type": "venta",
        "warehouse_id": str(planta.id),
        "third_party_id": str(willard_tp.id),
        "date": f"{SALE_DATE}T12:00:00",
        "remission_number": "REM-948",
        "lines": [{"material_id": str(plomo_crudo.id), "quantity": "100"}],
    })
    assert r.status_code == 201, r.text
    d = r.json()
    body = {"line_prices": [{"line_id": d["lines"][0]["id"], "unit_price": "3000"}]}
    if taxes is not None:
        body["taxes"] = taxes
    liq = client.post(f"{WILLARD_URL}/{d['id']}/liquidate", headers=headers, json=body)
    assert liq.status_code == 200, liq.text
    return liq.json()


# ---------------------------------------------------------------- T6 / T11 ---

class TestReversion:
    """T6: los DOS unicos puntos que revierten (D11, enumerados por grep)."""

    def test_t6_cancelar_la_venta_devuelve_todos_los_saldos(
        self, client, org_headers, db_session, test_organization,
        flag_on, customer, warehouse, material,
    ):
        sale = _sale(client, org_headers, customer, warehouse, material)
        _liquidate(client, org_headers, sale["id"], _fe_taxes())
        db_session.expire_all()
        ents = _tax_entities(db_session, test_organization.id)
        assert _balance(db_session, customer.id) == FE_TOTAL_A_PAGAR

        r = client.patch(f"{SALES_URL}/{sale['id']}/cancel", headers=org_headers)
        assert r.status_code == 200, r.text
        db_session.expire_all()

        # Round-trip al origen: el signo invertido lo delataria.
        assert _balance(db_session, customer.id) == 0
        for tp in ents.values():
            assert _balance(db_session, tp.id) == 0, tp.name

        # Las filas NO se borran: el estado de cuenta las necesita para emitir
        # su par de eventos y el saldo corrido tiene que seguir cerrando (#55).
        rows = db_session.execute(
            select(DocumentTax).where(DocumentTax.sale_id == sale["id"])
        ).scalars().all()
        assert len(rows) == 4
        assert all(r_.reverted_at is not None for r_ in rows)

    def test_t6b_anular_la_salida_de_plomo_devuelve_los_saldos(
        self, client, org_headers, db_session, test_organization,
        flags_willard, planta, willard_tp, plomo_crudo, acc_intersede,
    ):
        """El OTRO punto de reversion. La salida deriva una venta, pero los
        impuestos son de la SALIDA (D10): el cancel de la venta derivada no los
        toca y no hay doble reversion."""
        d = _delivery(client, org_headers, planta, willard_tp, plomo_crudo, [
            {"tax_type": "iva", "rate": "19", "base_kind": "subtotal", "amount": "57000"},
            {"tax_type": "retefuente", "rate": "2.5", "base_kind": "subtotal", "amount": "7500"},
        ])
        db_session.expire_all()
        # 100 kg x $3.000 = 300.000 + IVA 57.000 − retefuente 7.500
        assert _balance(db_session, willard_tp.id) == Decimal("349500.00")

        r = client.post(
            f"{WILLARD_URL}/{d['id']}/annul", headers=org_headers,
            json={"reason": "Error de captura"},
        )
        assert r.status_code == 200, r.text
        db_session.expire_all()
        assert _balance(db_session, willard_tp.id) == 0
        for tp in _tax_entities(db_session, test_organization.id).values():
            assert _balance(db_session, tp.id) == 0, tp.name

    def test_t11_la_venta_derivada_rechaza_impuestos(
        self, client, org_headers, db_session,
        flags_willard, planta, willard_tp, plomo_crudo, acc_intersede,
    ):
        """T11 (D10): hay DOS documentos para UNA factura y la duena es la
        Salida. Sin este guard, los dos podrian llevar impuestos y el cliente
        quedaria cobrado dos veces."""
        d = _delivery(client, org_headers, planta, willard_tp, plomo_crudo)
        sale_id = d["sale_id"]
        assert sale_id, "la salida tipo venta tiene que derivar una venta"

        # La venta derivada ya esta liquidada; el guard vive en `liquidate`, asi
        # que se prueba directo contra el servicio con el payload que llegaria.
        from app.services.sale import crud_sale
        from fastapi import HTTPException
        from app.schemas.document_tax import DocumentTaxCreate

        sale = db_session.get(__import__("app.models.sale", fromlist=["Sale"]).Sale, sale_id)
        sale.status = "registered"
        sale.liquidated_at = None
        db_session.commit()

        with pytest.raises(HTTPException) as exc:
            crud_sale.liquidate(
                db_session, sale.id, sale.organization_id,
                taxes_data=[DocumentTaxCreate(tax_type="iva", rate=19, amount=Decimal("100"))],
            )
        assert exc.value.status_code == 422
        assert "Salida de Plomo" in exc.value.detail


# ---------------------------------------------------------------------- T10 ---

STATEMENT_URL = "/api/v1/money-movements/third-party"


def _statement(client, headers, tp_id, **params):
    r = client.get(
        f"{STATEMENT_URL}/{tp_id}", headers=headers,
        params={"date_from": "2026-01-01", "date_to": "2026-12-31", **params},
    )
    assert r.status_code == 200, r.text
    return r.json()


class TestEstadoDeCuenta:
    """T10 — el invariante de #55 en las DOS superficies.

    El evento de la venta carga +subtotal al cliente pero la liquidacion lo dejo
    debiendo el TOTAL A PAGAR. Si el estado de cuenta no emite sus eventos, el
    saldo corrido deja de cerrar contra el saldo vivo — y eso fue exactamente el
    bloqueante de QA en #93 con las retenciones de compra.
    """

    def _ultimo_saldo(self, data) -> Decimal:
        """Saldo corrido de la ULTIMA fila.

        El endpoint devuelve los eventos en orden ascendente (los ordena y no
        los invierte; el que invierte para mostrar es el frontend), asi que la
        ultima fila es `items[-1]` — no `items[0]`.
        """
        assert data["items"], "el estado de cuenta llego vacio"
        return Decimal(str(data["items"][-1]["balance_after"]))

    def test_t10_el_cliente_cierra_contra_su_saldo_vivo(
        self, client, org_headers, db_session, flag_on, customer, warehouse, material,
    ):
        sale = _sale(client, org_headers, customer, warehouse, material)
        _liquidate(client, org_headers, sale["id"], _fe_taxes())
        db_session.expire_all()

        data = _statement(client, org_headers, customer.id)
        tipos = [i["event_type"] for i in data["items"]]
        assert tipos.count("document_tax") == 4, tipos
        # La venta va PRIMERO y los impuestos encima: pintar el IVA sobre una
        # venta que todavia no aparece deja un saldo corrido que arranca en el
        # IVA y no se le puede explicar a nadie.
        assert tipos[0] == "sale_liquidation", tipos
        assert self._ultimo_saldo(data) == FE_TOTAL_A_PAGAR
        assert Decimal(str(data["current_balance"])) == FE_TOTAL_A_PAGAR

    def test_t10b_la_entidad_de_impuestos_cierra_contra_su_saldo_vivo(
        self, client, org_headers, db_session, test_organization,
        flag_on, customer, warehouse, material,
    ):
        """La OTRA superficie. Con una sola, un signo invertido en el lado de
        la entidad pasaria en verde."""
        sale = _sale(client, org_headers, customer, warehouse, material)
        _liquidate(client, org_headers, sale["id"], _fe_taxes())
        db_session.expire_all()
        ents = _tax_entities(db_session, test_organization.id)

        iva = ents["[Impuestos] IVA por Pagar"]
        data = _statement(client, org_headers, iva.id)
        assert [i["event_type"] for i in data["items"]] == ["document_tax"]
        assert self._ultimo_saldo(data) == -FE_IVA
        assert Decimal(str(data["current_balance"])) == -FE_IVA

        rete = ents["[Impuestos] ReteFuente a Favor"]
        data = _statement(client, org_headers, rete.id)
        assert self._ultimo_saldo(data) == FE_RETEFUENTE

    def test_t10c_la_reversion_emite_su_par_y_el_saldo_vuelve_a_cero(
        self, client, org_headers, db_session, test_organization,
        flag_on, customer, warehouse, material,
    ):
        sale = _sale(client, org_headers, customer, warehouse, material)
        _liquidate(client, org_headers, sale["id"], _fe_taxes())
        client.patch(f"{SALES_URL}/{sale['id']}/cancel", headers=org_headers)
        db_session.expire_all()

        data = _statement(client, org_headers, customer.id)
        tipos = [i["event_type"] for i in data["items"]]
        assert tipos.count("document_tax") == 4
        assert tipos.count("document_tax_cancellation") == 4
        # 🔴 Contra el saldo VIVO, no contra la constante 0. El plantado mostro
        # por que: con una reversion que estampa `reverted_at` pero no toca los
        # saldos, el statement igual emite su par de cancelacion y el corrido
        # baja a cero mientras el saldo vivo se queda con los impuestos pegados.
        # Los dos lados se separan y un `== 0` pasa igual — el `0 == 0` de #98.
        # El invariante de #55 es *corrido == vivo*; el `== 0` es el contenido
        # del caso y va DESPUES, no en su lugar.
        db_session.refresh(customer)
        assert self._ultimo_saldo(data) == Decimal(str(customer.current_balance))
        assert self._ultimo_saldo(data) == 0

        ents = _tax_entities(db_session, test_organization.id)
        iva = ents["[Impuestos] IVA por Pagar"]
        data = _statement(client, org_headers, iva.id)
        db_session.refresh(iva)
        assert self._ultimo_saldo(data) == Decimal(str(iva.current_balance))
        assert self._ultimo_saldo(data) == 0


# ---------------------------------------------------------------------- T12 ---

class TestPanelDineroInactivo:
    """T12 (D4c) — a la DIAN no se le persigue un cobro."""

    def test_t12_la_entidad_de_impuestos_no_aparece_en_el_panel(
        self, client, org_headers, db_session, test_organization,
        flag_on, customer, warehouse, material,
    ):
        """Al mover la retencion a una seccion ACTIVA, sin esta exclusion
        apareceria como saldo a cobrar con su semaforo de dias —"ReteFuente a
        Favor — 60 dias"— invitando a llamar a la DIAN."""
        sale = _sale(client, org_headers, customer, warehouse, material)
        _liquidate(client, org_headers, sale["id"], _fe_taxes())

        r = client.get(
            "/api/v1/reports/inactive-balances", headers=org_headers,
            params={"min_days": 0, "min_amount": 0},
        )
        assert r.status_code == 200, r.text
        nombres = {i["third_party_name"] for i in r.json()["items"]}
        assert not any(n.startswith("[Impuestos]") for n in nombres), nombres
        # CONTROL POSITIVO: el panel SI funciona en este escenario — el cliente
        # esta ahi. Sin esto, un panel roto pasaria como "no aparece".
        assert customer.name in nombres


# ---------------------------------------------------------------- T13 / T14 ---

TP_URL = "/api/v1/third-parties"
CAT_URL = "/api/v1/third-party-categories"


def _tax_category(db, org_id) -> ThirdPartyCategory:
    return db.execute(
        select(ThirdPartyCategory).where(
            ThirdPartyCategory.organization_id == org_id,
            ThirdPartyCategory.system_code == "taxes",
        )
    ).scalar_one()


class TestCategoriaDeSistema:
    """T13/T14 (D4d) — la categoria de impuestos se defiende.

    Hoy CUALQUIER usuario asigna categorias desde el formulario de terceros
    (#37, multi-select). Sin guard, ponerle a un proveedor normal la categoria
    de impuestos manda su saldo a favor a la seccion de impuestos Y lo saca del
    panel de cobro, las dos cosas en silencio.
    """

    @pytest.fixture
    def con_impuestos(self, client, org_headers, flag_on, customer, warehouse, material):
        """Una venta con impuestos: la categoria y las entidades ya existen."""
        sale = _sale(client, org_headers, customer, warehouse, material)
        _liquidate(client, org_headers, sale["id"], _fe_taxes())
        return sale

    # ---- T13: las dos mitades ----

    def test_t13a_un_usuario_no_puede_asignar_la_categoria(
        self, client, org_headers, db_session, test_organization, con_impuestos,
    ):
        cat = _tax_category(db_session, test_organization.id)
        r = client.post(TP_URL, headers=org_headers, json={
            "name": "Proveedor Cualquiera",
            "category_ids": [str(cat.id)],
        })
        assert r.status_code == 422, r.text
        assert "del sistema" in r.text

    def test_t13b_un_usuario_no_puede_quitarsela_a_la_entidad(
        self, client, org_headers, db_session, test_organization, con_impuestos,
    ):
        """La otra direccion. `_sync_category_assignments` BORRA y recrea, asi
        que quitarsela pasa por la misma linea que agregarla — y deja las
        retenciones cayendo otra vez en Gastos Prepagados, mintiendole al
        contador."""
        iva = _tax_entities(db_session, test_organization.id)["[Impuestos] IVA por Pagar"]
        r = client.patch(f"{TP_URL}/{iva.id}", headers=org_headers, json={"category_ids": []})
        assert r.status_code == 422, r.text
        assert "del sistema" in r.text

    def test_t13c_la_entidad_del_flujo_de_impuestos_SI_la_tiene(
        self, client, org_headers, db_session, test_organization, con_impuestos,
    ):
        """🔴 La mitad POSITIVA, y sin ella un guard que rechace absolutamente
        todo pasaria en verde (control positivo de #111).

        El flujo legitimo no pasa por `_sync_category_assignments`:
        `tax_entities.resolve_tax_entity` crea la asignacion directo. Mismo
        reparto que #58.
        """
        cat = _tax_category(db_session, test_organization.id)
        assert cat.behavior_type == "liability"
        for tp in _tax_entities(db_session, test_organization.id).values():
            r = client.get(f"{TP_URL}/{tp.id}", headers=org_headers)
            assert r.status_code == 200, r.text
            codigos = {c["id"] for c in r.json()["categories"]}
            assert str(cat.id) in codigos, tp.name

    def test_t13d_editar_la_entidad_sin_tocar_categorias_pasa(
        self, client, org_headers, db_session, test_organization, con_impuestos,
    ):
        """El guard no estorba la edicion normal, y esto es estructura y no
        suerte: el formulario inicializa `categoryIds` con TODAS las categorias
        del tercero —incluidas las ocultas— y las devuelve enteras al guardar.
        El delta queda vacio y pasa. El payload de este test es EXACTAMENTE ese.
        """
        iva = _tax_entities(db_session, test_organization.id)["[Impuestos] IVA por Pagar"]
        actuales = client.get(f"{TP_URL}/{iva.id}", headers=org_headers).json()["categories"]
        r = client.patch(f"{TP_URL}/{iva.id}", headers=org_headers, json={
            "phone": "3001234567",
            "category_ids": [c["id"] for c in actuales],
        })
        assert r.status_code == 200, r.text
        assert r.json()["phone"] == "3001234567"

    # ---- T14: la categoria blindada ----

    def test_t14a_dos_categorias_con_el_mismo_codigo_no_entran(
        self, db_session, test_organization, con_impuestos,
    ):
        """A1 — la unicidad no se documenta, se hace imposible.

        #58 dejo escrito que dos filas con el mismo codigo revientan con
        `MultipleResultsFound` y ahi quedo, como advertencia. Acá hay un indice
        unico PARCIAL y la segunda fila no se puede insertar.
        """
        from sqlalchemy.exc import IntegrityError

        db_session.add(ThirdPartyCategory(
            organization_id=test_organization.id, name="Impuestos Bis",
            behavior_type="liability", system_code="taxes", is_active=True,
        ))
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_t14b_el_indice_es_PARCIAL_y_no_toca_las_filas_normales(
        self, db_session, test_organization,
    ):
        """El control positivo de A1: en las seis organizaciones que no son SAC
        todas las filas tienen `system_code` NULL, asi que el indice no las
        toca. Si el indice fuera total, dos categorias normales colisionarian y
        este ciclo habria roto la creacion de categorias en TODAS partes."""
        for nombre in ("Chatarreros", "Recicladores"):
            db_session.add(ThirdPartyCategory(
                organization_id=test_organization.id, name=nombre,
                behavior_type="material_supplier", is_active=True,
            ))
        db_session.flush()  # dos NULL conviven sin problema
        db_session.rollback()

    def test_t14c_system_code_no_se_puede_escribir_desde_la_API(
        self, client, org_headers, db_session, test_organization,
    ):
        """A2 — la proteccion por AUSENCIA se fija con un test.

        Ni `Create` ni `Update` declaran `extra="forbid"`, asi que Pydantic
        ignora el campo EN SILENCIO. Eso hoy alcanza, pero es una propiedad que
        nadie enuncio y que se pierde el dia que alguien agregue el campo al
        schema. Acá deja de ser un accidente y pasa a ser invariante.
        """
        r = client.post(CAT_URL, headers=org_headers, json={
            "name": "Falsa Impuestos", "behavior_type": "liability",
            "system_code": "taxes",
        })
        assert r.status_code == 201, r.text
        cat_id = r.json()["id"]
        db_session.expire_all()
        cat = db_session.get(ThirdPartyCategory, cat_id)
        assert cat.system_code is None, "system_code entro por el POST"

        r = client.patch(f"{CAT_URL}/{cat_id}", headers=org_headers, json={
            "name": "Falsa Impuestos 2", "system_code": "taxes",
        })
        assert r.status_code == 200, r.text
        db_session.expire_all()
        db_session.refresh(cat)
        assert cat.system_code is None, "system_code entro por el PUT"

    def test_t14d_no_se_desactiva_ni_se_reparenta_pero_SI_se_renombra(
        self, client, org_headers, db_session, test_organization, con_impuestos,
    ):
        """A3. Renombrar SI se permite, y es la asimetria de #58: el
        reconocimiento va por codigo justamente para que el nombre sea libre.
        Si esto algun dia bloqueara el nombre, el codigo habria dejado de tener
        razon de ser."""
        cat = _tax_category(db_session, test_organization.id)
        padre = client.post(CAT_URL, headers=org_headers, json={
            "name": "Un Padre", "behavior_type": "liability",
        }).json()

        r = client.patch(f"{CAT_URL}/{cat.id}", headers=org_headers, json={"is_active": False})
        assert r.status_code == 422 and "desactivar" in r.text, r.text

        r = client.patch(f"{CAT_URL}/{cat.id}", headers=org_headers, json={"parent_id": padre["id"]})
        assert r.status_code == 422 and "raiz" in r.text, r.text

        r = client.patch(f"{CAT_URL}/{cat.id}", headers=org_headers, json={"name": "Tributos"})
        assert r.status_code == 200, r.text
        db_session.expire_all()
        assert _tax_category(db_session, test_organization.id).name == "Tributos"

    def test_t14e_no_se_elimina_aunque_este_vacia(
        self, client, org_headers, db_session, test_organization, flag_on,
    ):
        """El guard de "terceros asignados" que ya existia NO alcanza: no cubre
        la ventana entre que la categoria nace y la primera venta con impuestos,
        que es justo cuando esta vacia y se puede borrar."""
        from app.services.tax_entities import get_or_create_tax_category

        cat = get_or_create_tax_category(db_session, test_organization.id)
        db_session.commit()
        r = client.delete(f"{CAT_URL}/{cat.id}", headers=org_headers)
        assert r.status_code == 422, r.text
        assert "del sistema" in r.text

    def test_t14f_renombrar_la_categoria_no_rompe_la_siguiente_factura(
        self, client, org_headers, db_session, test_organization,
        flag_on, customer, warehouse, material, con_impuestos,
    ):
        """🔴 Este test nacio del plantado: P14 —reconocer la categoria por
        NOMBRE en vez de por codigo— no tumbaba ni un test de los 30.

        Renombrar esta PERMITIDO por diseño (T14d, la asimetria de #58) y es el
        motivo entero de que exista `system_code`. Con reconocimiento por
        nombre, la factura SIGUIENTE no encuentra la categoria renombrada,
        intenta crear otra con el mismo codigo y choca contra el indice unico
        parcial: un 500 en la cara del usuario. La decision D4b no tenia
        guardian — se documentaba a si misma.
        """
        cat = _tax_category(db_session, test_organization.id)
        cat_id = cat.id
        r = client.patch(f"{CAT_URL}/{cat_id}", headers=org_headers, json={"name": "Tributos"})
        assert r.status_code == 200, r.text

        # Una factura mas, DESPUES del renombre, y con un ICA de municipio nuevo
        # para forzar una entidad que todavia no existe.
        sale = _sale(client, org_headers, customer, warehouse, material)
        r = client.patch(
            f"{SALES_URL}/{sale['id']}/liquidate", headers=org_headers,
            json={"taxes": [{"tax_type": "ica", "municipality": "Soledad",
                             "amount": "1000.00"}]},
        )
        assert r.status_code == 200, r.text

        db_session.expire_all()
        cats = db_session.execute(
            select(ThirdPartyCategory).where(
                ThirdPartyCategory.organization_id == test_organization.id,
                ThirdPartyCategory.system_code == "taxes",
            )
        ).scalars().all()
        assert len(cats) == 1, "nacio una categoria de impuestos duplicada"
        assert cats[0].id == cat_id and cats[0].name == "Tributos"

        nueva = _tax_entities(db_session, test_organization.id)["[Impuestos] ICA a Favor Soledad"]
        asignadas = {c["id"] for c in client.get(
            f"{TP_URL}/{nueva.id}", headers=org_headers).json()["categories"]}
        assert str(cat_id) in asignadas, "la entidad nueva no quedo en la categoria renombrada"
