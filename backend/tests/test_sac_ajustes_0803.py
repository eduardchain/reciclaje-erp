"""Tests de los ajustes rapidos de la reunion SAC del 3-ago-2026.

Cubre:
  A — factura en la Entrada con FUENTE UNICA POR TIPO (D1, re-semantizado por
      #93 D12): willard la guarda en su columna; tipo compra ya NO la acepta en
      la captura (el proveedor no existe ahi) — vive POR PROVEEDOR en el
      reparto y aterriza en las compras derivadas al liquidar; la columna del
      inbound queda NULL. Legacy 1:1 (purchase_id del backfill): propaga a la
      derivada como en #87.
  C — autoservicio de centros de distribucion Willard: endpoint estrecho que
      SOLO puede tocar esa clave del JSONB de settings (D6). El test estrella
      relee desde BD (H4: mutar in-place no persiste y el assert contra el
      response no lo detectaria).
  E — la placa editada en la Entrada llega a las compras derivadas (1:N desde
      #93: TODAS las del reparto), y quitar el vehiculo es posible (asimetria
      de fields_set alineada).

B (hora en auditoria) y D (categoria financiera del seeder) no llevan test:
frontend puro y data de seeder respectivamente (§6 del plan).
"""
import pytest
from datetime import datetime, timedelta, timezone

from app.models.inbound_order import InboundOrder
from app.models.organization import Organization
from app.models.purchase import Purchase
from tests.integration_helpers import create_material, create_material_category, create_warehouse
from tests.conftest import create_third_party_with_category
from app.utils.dates import business_today

INBOUND_URL = "/api/v1/inbound-orders"
KG_URL = "/api/v1/kg-ledger"
FORMULAS_URL = "/api/v1/material-conversion-formulas"
PROFILES_URL = "/api/v1/material-kg-profiles"
CENTERS_URL = "/api/v1/organizations/settings/willard-distribution-centers"
FLEET_URL = "/api/v1/vehicles"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _enable_kg_ledger_flag(db_session, test_organization, test_organization2):
    for org in (test_organization, test_organization2):
        org.settings = {"kg_ledger_enabled": True}
    db_session.commit()


@pytest.fixture
def warehouse(db_session, test_organization):
    wh = create_warehouse(db_session, test_organization.id, "Planta CV")
    db_session.commit()
    return wh


@pytest.fixture
def willard_tp(db_session, test_organization):
    tp = create_third_party_with_category(
        db_session, test_organization.id, "Willard S.A.", "material_supplier"
    )
    db_session.commit()
    return tp


@pytest.fixture
def sup_regular(db_session, test_organization):
    """Proveedor de compra corriente. Estos tests usaban `willard_tp` como
    proveedor por comodidad, pero el titular de una cuenta kg NO puede repartir
    una compra (#80, guard de las pruebas de usuario 2026-08-11): lo Willard
    entra por su propio canal. El sujeto de estos tests es la FACTURA, no el
    tercero — asi que el proveedor se separa y el guard queda intacto."""
    tp = create_third_party_with_category(
        db_session, test_organization.id, "Chatarreria del Norte", "material_supplier"
    )
    db_session.commit()
    return tp


def _mat(db, org_id, code, unit="kg"):
    cat = create_material_category(db, org_id, f"Cat {code}")
    mat = create_material(db, org_id, code, f"Material {code}", cat.id)
    mat.default_unit = unit
    db.commit()
    return mat


def _set_profile(client, headers, material_id, *, compra_regular=False, willard_world="none"):
    resp = client.put(
        f"{PROFILES_URL}/{material_id}",
        headers=headers,
        json={"compra_regular": compra_regular, "willard_world": willard_world},
    )
    assert resp.status_code == 200, resp.text


@pytest.fixture
def mat_bat(db_session, test_organization, client, org_headers):
    mat = _mat(db_session, test_organization.id, "BAT-AJ", unit="unidad")
    resp = client.post(
        FORMULAS_URL,
        headers=org_headers,
        json={
            "material_id": str(mat.id),
            "formula_type": "battery_to_lead",
            "parameters": {"kg_lead_per_unit": 2.5},
        },
    )
    assert resp.status_code == 201, resp.text
    _set_profile(client, org_headers, mat.id, willard_world="postconsumo")
    return mat


@pytest.fixture
def mat_regular(db_session, test_organization, client, org_headers):
    mat = _mat(db_session, test_organization.id, "CHATARRA-AJ", unit="kg")
    _set_profile(client, org_headers, mat.id, compra_regular=True, willard_world="none")
    return mat


@pytest.fixture
def kg_bat_account(client, org_headers, warehouse, willard_tp):
    resp = client.post(
        f"{KG_URL}/accounts",
        headers=org_headers,
        json={
            "code": "WILLARD-BAT-AJ",
            "display_name": "Willard Baterias CV",
            "account_type": "willard_baterias",
            "warehouse_id": str(warehouse.id),
            "third_party_id": str(willard_tp.id),
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _inbound(client, headers, *, inbound_type, warehouse_id, lines, third_party_id=None, **extra):
    body = {
        "inbound_type": inbound_type,
        "warehouse_id": str(warehouse_id),
        "date": business_today().isoformat(),
        "lines": lines,
        **extra,
    }
    # #93: tipo compra captura SIN proveedor; willard sigue exigiendo titular
    if third_party_id is not None:
        body["third_party_id"] = str(third_party_id)
    return client.post(INBOUND_URL, headers=headers, json=body)


def _past(days: int = 2) -> str:
    """Fecha de negocio robusta a zona horaria.

    Los validadores de "no futura" de compras usan `date.today()` (LOCAL,
    Bogota UTC-5) mientras estos tests arman fechas con `now(utc).date()`.
    Entre las 00:00 y 05:00 UTC (19:00-24:00 en Bogota) la fecha UTC de hoy es
    un dia MAYOR que la local, y liquidar "hoy" revienta con 422 "no puede ser
    futura" — flake que solo aparece de noche. Una fecha pasada es <= hoy en
    cualquier zona. Ver memoria `gotcha_fechas_utc_vs_local`.
    """
    return (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()


def _purchase_inbound(client, headers, warehouse, mat, **extra):
    # #93: la captura tipo compra no lleva proveedor — solo el hecho fisico
    return _inbound(
        client, headers,
        inbound_type="purchase",
        warehouse_id=warehouse.id,
        lines=[{"material_id": str(mat.id), "quantity": "100", "unit_price": "1000"}],
        **extra,
    )


def _review(client, headers, order_id):
    resp = client.post(f"{INBOUND_URL}/{order_id}/review", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _alloc(supplier, qty, price="1000", invoice=None):
    body = {"third_party_id": str(supplier.id), "quantity": str(qty), "unit_price": price}
    if invoice:
        body["invoice_number"] = invoice
    return body


def _liquidate_allocs(client, headers, order_id, mat, allocs):
    resp = client.post(
        f"{INBOUND_URL}/{order_id}/liquidate", headers=headers,
        json={"lines": [{"material_id": str(mat.id), "allocations": allocs}]},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _liquidate_one(client, headers, order_id, mat, supplier, qty="100", invoice=None):
    return _liquidate_allocs(
        client, headers, order_id, mat, [_alloc(supplier, qty, invoice=invoice)]
    )


def _willard_inbound(client, headers, warehouse, willard_tp, mat, **extra):
    return _inbound(
        client, headers,
        inbound_type="willard",
        warehouse_id=warehouse.id,
        third_party_id=willard_tp.id,
        lines=[{"material_id": str(mat.id), "quantity": "10"}],
        **extra,
    )


# ---------------------------------------------------------------------------
# A — Factura (fuente unica POR TIPO)
# ---------------------------------------------------------------------------

class TestInvoiceNumber:
    def test_purchase_type_stores_on_purchase_not_on_order(
        self, client, org_headers, db_session, warehouse, sup_regular, mat_regular
    ):
        """D1 re-semantizado por #93 D12: en la captura no hay proveedor, asi
        que la factura se RECHAZA con guia; llega con el reparto al liquidar y
        aterriza en la compra derivada. La columna del inbound queda NULL —
        sigue habiendo una sola fuente de verdad por tipo."""
        rejected = _purchase_inbound(
            client, org_headers, warehouse, mat_regular, invoice_number="FAC-1001"
        )
        assert rejected.status_code == 422, rejected.text
        assert "liquidar" in rejected.text.lower()

        p = _purchase_inbound(client, org_headers, warehouse, mat_regular).json()
        _review(client, org_headers, p["id"])
        _liquidate_one(
            client, org_headers, p["id"], mat_regular, sup_regular, invoice="FAC-1001"
        )

        detail = client.get(f"{INBOUND_URL}/{p['id']}", headers=org_headers).json()
        assert detail["invoice_number"] is None, "el header no inventa una factura"
        assert [pu["invoice_number"] for pu in detail["purchases"]] == ["FAC-1001"]

        order = db_session.get(InboundOrder, p["id"])
        db_session.refresh(order)
        assert order.invoice_number is None, "la columna del inbound debe quedar NULL"
        purchase = db_session.get(Purchase, detail["purchases"][0]["purchase_id"])
        db_session.refresh(purchase)
        assert purchase.invoice_number == "FAC-1001"

    def test_willard_type_stores_on_own_column(
        self, client, org_headers, db_session, warehouse, willard_tp, mat_bat, kg_bat_account
    ):
        resp = _willard_inbound(
            client, org_headers, warehouse, willard_tp, mat_bat,
            invoice_number="FAC-W-77",
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["invoice_number"] == "FAC-W-77"

        order = db_session.get(InboundOrder, data["id"])
        db_session.refresh(order)
        assert order.invoice_number == "FAC-W-77"
        assert order.purchase_id is None

    def test_update_propagates_to_the_right_destination(
        self, client, org_headers, db_session, warehouse, willard_tp, sup_regular, mat_regular,
        mat_bat, kg_bat_account,
    ):
        """Willard: columna propia. Tipo compra #93: el PATCH de factura guia
        al reparto (422). Legacy 1:1 (purchase_id como lo dejo el backfill de
        la migracion): propaga a la derivada, igual que en #87."""
        w = _willard_inbound(
            client, org_headers, warehouse, willard_tp, mat_bat, invoice_number="B-1"
        ).json()
        assert client.patch(
            f"{INBOUND_URL}/{w['id']}", headers=org_headers, json={"invoice_number": "B-2"}
        ).status_code == 200
        wo = db_session.get(InboundOrder, w["id"])
        db_session.refresh(wo)
        assert wo.invoice_number == "B-2"

        p = _purchase_inbound(client, org_headers, warehouse, mat_regular).json()
        blocked = client.patch(
            f"{INBOUND_URL}/{p['id']}", headers=org_headers, json={"invoice_number": "A-2"}
        )
        assert blocked.status_code == 422, blocked.text
        assert "reparto" in blocked.text.lower()

        # Legacy 1:1 simulado como lo dejo la migracion: purchase_id seteado
        # (el backfill conserva el FK inerte junto a la fila puente)
        _review(client, org_headers, p["id"])
        _liquidate_one(client, org_headers, p["id"], mat_regular, sup_regular)
        detail = client.get(f"{INBOUND_URL}/{p['id']}", headers=org_headers).json()
        po = db_session.get(InboundOrder, p["id"])
        db_session.refresh(po)
        po.purchase_id = detail["purchases"][0]["purchase_id"]
        db_session.commit()

        assert client.patch(
            f"{INBOUND_URL}/{p['id']}", headers=org_headers, json={"invoice_number": "A-3"}
        ).status_code == 200
        purchase = db_session.get(Purchase, detail["purchases"][0]["purchase_id"])
        db_session.refresh(purchase)
        assert purchase.invoice_number == "A-3"
        db_session.refresh(po)
        assert po.invoice_number is None

    def test_explicit_null_clears_invoice(
        self, client, org_headers, db_session, warehouse, willard_tp, mat_bat, kg_bat_account
    ):
        """exclude_unset distingue ausente de null explicito (patron de notes).
        Re-semantizado a willard (#93): tipo compra ya no tiene factura de
        cabecera que borrar — vive por proveedor en el reparto."""
        w = _willard_inbound(
            client, org_headers, warehouse, willard_tp, mat_bat, invoice_number="BORRAME"
        ).json()

        # Ausente: no toca la factura
        client.patch(f"{INBOUND_URL}/{w['id']}", headers=org_headers, json={"notes": "x"})
        order = db_session.get(InboundOrder, w["id"])
        db_session.refresh(order)
        assert order.invoice_number == "BORRAME"

        # null explicito: la borra
        client.patch(
            f"{INBOUND_URL}/{w['id']}", headers=org_headers, json={"invoice_number": None}
        )
        db_session.refresh(order)
        assert order.invoice_number is None

    def test_editable_after_liquidation(
        self, client, org_headers, db_session, warehouse, willard_tp, sup_regular, mat_regular
    ):
        """D2 evoluciona con #93: la factura que llega tarde se escribe
        des-liquidando (D20 conserva el reparto) y re-liquidando — el re-sync
        por firma la estampa en la MISMA compra (mismo numero). El PATCH
        directo guia al reparto y la fecha en liquidada sigue dando 422."""
        p = _purchase_inbound(
            client, org_headers, warehouse, mat_regular, date=_past()
        ).json()
        _review(client, org_headers, p["id"])
        _liquidate_one(client, org_headers, p["id"], mat_regular, sup_regular)
        detail = client.get(f"{INBOUND_URL}/{p['id']}", headers=org_headers).json()
        purchase_id = detail["purchases"][0]["purchase_id"]
        assert detail["purchases"][0]["invoice_number"] is None

        # PATCH directo en liquidada: guia al reparto (la factura no vive aca)
        direct = client.patch(
            f"{INBOUND_URL}/{p['id']}", headers=org_headers, json={"invoice_number": "TARDE-9"}
        )
        assert direct.status_code == 422, direct.text

        # La fecha en liquidada exige des-liquidar (idioma inbound: 422, #80)
        blocked = client.patch(
            f"{INBOUND_URL}/{p['id']}",
            headers=org_headers,
            json={"date": business_today().isoformat()},
        )
        assert blocked.status_code == 422, blocked.text

        # El camino real: des-liquidar -> re-liquidar con la factura
        assert client.post(
            f"{INBOUND_URL}/{p['id']}/unliquidate", headers=org_headers
        ).status_code == 200
        _liquidate_one(
            client, org_headers, p["id"], mat_regular, sup_regular, invoice="TARDE-9"
        )
        after = client.get(f"{INBOUND_URL}/{p['id']}", headers=org_headers).json()
        assert [pu["purchase_id"] for pu in after["purchases"]] == [purchase_id], (
            "la re-liquidacion re-usa la MISMA compra (re-sync por firma)"
        )
        assert after["purchases"][0]["invoice_number"] == "TARDE-9"
        purchase = db_session.get(Purchase, purchase_id)
        db_session.refresh(purchase)
        assert purchase.invoice_number == "TARDE-9"

    def test_response_reads_right_source_without_extra_queries(
        self, client, org_headers, db_session, warehouse, willard_tp, sup_regular,
        mat_regular, mat_bat, kg_bat_account,
    ):
        """Invariante estrella de A re-semantizado a #93: willard expone su
        columna; tipo compra expone NULL en el header y la factura POR
        PROVEEDOR en purchases[] — y el listado no gana queries por fila (las
        compras de la puente vienen del lookup por pagina)."""
        p = _purchase_inbound(client, org_headers, warehouse, mat_regular).json()
        _review(client, org_headers, p["id"])
        _liquidate_one(
            client, org_headers, p["id"], mat_regular, sup_regular, invoice="LIST-P"
        )
        _willard_inbound(
            client, org_headers, warehouse, willard_tp, mat_bat, invoice_number="LIST-W"
        )

        from sqlalchemy import event
        from app.core.database import engine

        counter = {"n": 0}

        def _count(conn, cursor, statement, params, context, executemany):
            counter["n"] += 1

        event.listen(engine, "before_cursor_execute", _count)
        try:
            listed = client.get(INBOUND_URL, headers=org_headers)
            with_invoice = counter["n"]
        finally:
            event.remove(engine, "before_cursor_execute", _count)

        assert listed.status_code == 200
        by_id = {i["id"]: i for i in listed.json()["items"]}
        willard_invoices = {i["invoice_number"] for i in by_id.values()}
        assert "LIST-W" in willard_invoices
        assert by_id[p["id"]]["invoice_number"] is None, "header tipo compra: NULL"
        assert [pu["invoice_number"] for pu in by_id[p["id"]]["purchases"]] == ["LIST-P"]

        # Sanity: el listado resuelve en un numero acotado de queries — si la
        # factura hubiera forzado un lookup por fila esto crecería con N.
        assert with_invoice < 40, f"demasiadas queries en el listado: {with_invoice}"

        for item in listed.json()["items"]:
            detail = client.get(f"{INBOUND_URL}/{item['id']}", headers=org_headers)
            assert detail.json()["invoice_number"] == item["invoice_number"]

    def test_search_by_invoice_keeps_willard_visible(
        self, client, org_headers, warehouse, willard_tp, sup_regular, mat_regular,
        mat_bat, kg_bat_account
    ):
        """H3 re-semantizado a #93: la factura de tipo compra vive en el
        reparto Y en la compra derivada — el buscador alcanza ambas via EXISTS
        (R2: jamas join). La entrada aparece UNA vez y las willard no
        desaparecen del buscador."""
        p = _purchase_inbound(client, org_headers, warehouse, mat_regular).json()
        _review(client, org_headers, p["id"])
        _liquidate_one(
            client, org_headers, p["id"], mat_regular, sup_regular, invoice="FX-500"
        )
        w = _willard_inbound(
            client, org_headers, warehouse, willard_tp, mat_bat, invoice_number="FX-600"
        ).json()

        by_p = client.get(f"{INBOUND_URL}?search=FX-500", headers=org_headers).json()
        assert [i["id"] for i in by_p["items"]] == [p["id"]], (
            "una entrada, una fila — el EXISTS no duplica ni pierde"
        )

        by_w = client.get(f"{INBOUND_URL}?search=FX-600", headers=org_headers).json()
        assert [i["invoice_number"] for i in by_w["items"]] == ["FX-600"]

        # Termino que NO matchea ninguna factura: la willard sigue apareciendo
        by_number = client.get(
            f"{INBOUND_URL}?search={w['order_number']}", headers=org_headers
        ).json()
        assert w["id"] in [i["id"] for i in by_number["items"]]


# ---------------------------------------------------------------------------
# C — Centros de distribucion en autoservicio
# ---------------------------------------------------------------------------

class TestWillardDistributionCenters:
    def test_put_normalizes_dedups_and_orders(self, client, org_headers):
        resp = client.put(
            CENTERS_URL,
            headers=org_headers,
            json={"centers": ["  Montería ", "BAQ", "monteria", "Santa Marta"]},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["centers"] == ["monteria", "baq", "santa_marta"]

    def test_flags_and_other_settings_survive(
        self, client, org_headers, db_session, test_organization
    ):
        """Invariante estrella de C (D6): el endpoint SOLO puede tocar su clave.
        Se relee desde BD (H4) — la columna no usa MutableDict, asi que mutar
        in-place NO persistiria y el assert contra el response pasaria igual,
        con los flags 'intactos'... por no haberse escrito nada."""
        test_organization.settings = {
            "kg_ledger_enabled": True,
            "two_step_transfers_enabled": True,
            "internal_maquila_enabled": True,
            "transfer_tolerance_pct": 0.07,
            "intersede_stale_days": 45,
            "aging_buckets": [15, 30, 45],
            "willard_distribution_centers": ["baq", "bog"],
            "willard_sede_drosses": "abc",
            "willard_sede_postconsumo_default": "def",
        }
        db_session.commit()

        resp = client.put(
            CENTERS_URL, headers=org_headers, json={"centers": ["baq", "bog", "sincelejo"]}
        )
        assert resp.status_code == 200, resp.text

        db_session.expire_all()
        org = db_session.get(Organization, test_organization.id)
        s = org.settings
        assert s["willard_distribution_centers"] == ["baq", "bog", "sincelejo"], (
            "el efecto no persistio: mutacion in-place en vez de reasignacion"
        )
        assert s["kg_ledger_enabled"] is True
        assert s["two_step_transfers_enabled"] is True
        assert s["internal_maquila_enabled"] is True
        assert s["transfer_tolerance_pct"] == 0.07
        assert s["intersede_stale_days"] == 45
        assert s["aging_buckets"] == [15, 30, 45]
        assert s["willard_sede_drosses"] == "abc"
        assert s["willard_sede_postconsumo_default"] == "def"

    def test_empty_list_rejected(self, client, org_headers):
        """Vacia rompe la validacion de pertenencia del consumidor: ninguna
        entrada Willard podria declarar centro."""
        resp = client.put(CENTERS_URL, headers=org_headers, json={"centers": []})
        assert resp.status_code == 422, resp.text

    def test_too_long_rejected(self, client, org_headers):
        resp = client.put(
            CENTERS_URL, headers=org_headers, json={"centers": ["x" * 25]}
        )
        assert resp.status_code == 422, resp.text

    def test_removing_center_in_use_warns_but_allows(
        self, client, org_headers, db_session, warehouse, willard_tp, mat_bat, kg_bat_account
    ):
        """Avisar, no bloquear (#17/#76): el historico guarda el string en la
        fila, no una FK — no hay integridad que proteger."""
        client.put(CENTERS_URL, headers=org_headers, json={"centers": ["baq", "bog"]})
        order = _willard_inbound(
            client, org_headers, warehouse, willard_tp, mat_bat,
            willard_distribution_center="bog",
        ).json()

        resp = client.put(CENTERS_URL, headers=org_headers, json={"centers": ["baq"]})
        assert resp.status_code == 200, resp.text
        assert any("bog" in w for w in resp.json()["warnings"])

        stored = db_session.get(InboundOrder, order["id"])
        db_session.refresh(stored)
        assert stored.willard_distribution_center == "bog", "el historico no cambia"

    def test_flag_off_forbidden_even_for_admin(
        self, client, org_headers, db_session, test_organization
    ):
        test_organization.settings = {"kg_ledger_enabled": False}
        db_session.commit()
        resp = client.put(CENTERS_URL, headers=org_headers, json={"centers": ["baq"]})
        assert resp.status_code == 403, resp.text

    def test_requires_permission(self, client, org_headers2):
        """test_user es viewer en la org2 (con el flag ON por el autouse):
        no tiene config.manage_sac_settings -> 403."""
        resp = client.put(CENTERS_URL, headers=org_headers2, json={"centers": ["baq"]})
        assert resp.status_code == 403, resp.text

    def test_new_center_immediately_selectable(
        self, client, org_headers, warehouse, willard_tp, mat_bat, kg_bat_account
    ):
        """Integracion con el consumidor: el centro nuevo pasa la validacion de
        pertenencia de la captura sin recargar nada."""
        rejected = _willard_inbound(
            client, org_headers, warehouse, willard_tp, mat_bat,
            willard_distribution_center="sincelejo",
        )
        assert rejected.status_code == 422, rejected.text

        client.put(
            CENTERS_URL,
            headers=org_headers,
            json={"centers": ["baq", "bog", "monteria", "santa_marta", "motocosta", "sincelejo"]},
        )
        ok = _willard_inbound(
            client, org_headers, warehouse, willard_tp, mat_bat,
            willard_distribution_center="sincelejo",
        )
        assert ok.status_code == 201, ok.text


# ---------------------------------------------------------------------------
# E — La placa editada llega a la compra derivada
# ---------------------------------------------------------------------------

class TestVehiclePlatePropagation:
    @staticmethod
    def _vehicle(client, headers, plate):
        resp = client.post(FLEET_URL, headers=headers, json={"plate": plate})
        assert resp.status_code == 201, resp.text
        return resp.json()

    def test_edit_vehicle_updates_purchase_plate(
        self, client, org_headers, db_session, test_organization, warehouse,
        willard_tp, sup_regular, mat_regular,
    ):
        """El listado de Compras (#72) filtra y muestra por vehicle_plate — sin
        propagar, la correccion del operador no se ve donde importa. Desde #93
        la propagacion es 1:N: TODAS las compras del reparto se corrigen."""
        v1 = self._vehicle(client, org_headers, "AAA111")
        v2 = self._vehicle(client, org_headers, "BBB222")
        other_sup = create_third_party_with_category(
            db_session, test_organization.id, "Proveedor Dos AJ", "material_supplier"
        )
        db_session.commit()

        p = _purchase_inbound(
            client, org_headers, warehouse, mat_regular, vehicle_id=v1["id"]
        ).json()
        _review(client, org_headers, p["id"])
        _liquidate_allocs(
            client, org_headers, p["id"], mat_regular,
            [_alloc(sup_regular, "60"), _alloc(other_sup, "40")],
        )
        detail = client.get(f"{INBOUND_URL}/{p['id']}", headers=org_headers).json()
        pids = [pu["purchase_id"] for pu in detail["purchases"]]
        assert len(pids) == 2
        for pid in pids:
            purchase = db_session.get(Purchase, pid)
            db_session.refresh(purchase)
            assert purchase.vehicle_plate == "AAA111"

        assert client.patch(
            f"{INBOUND_URL}/{p['id']}", headers=org_headers, json={"vehicle_id": v2["id"]}
        ).status_code == 200
        for pid in pids:
            purchase = db_session.get(Purchase, pid)
            db_session.refresh(purchase)
            assert purchase.vehicle_plate == "BBB222", (
                "la propagacion cubre TODAS las compras del reparto"
            )

    def test_clearing_vehicle_clears_plate(
        self, client, org_headers, db_session, warehouse, willard_tp, sup_regular, mat_regular
    ):
        """Antes de #87 `is not None` impedia QUITAR el vehiculo: mandar null
        no hacia nada (asimetria con notes, que usa fields_set). Sin guard de
        estado: la compra ya liquidada tambien se corrige (cero efecto
        financiero)."""
        v1 = self._vehicle(client, org_headers, "CCC333")
        p = _purchase_inbound(
            client, org_headers, warehouse, mat_regular, vehicle_id=v1["id"]
        ).json()
        _review(client, org_headers, p["id"])
        _liquidate_one(client, org_headers, p["id"], mat_regular, sup_regular)
        detail = client.get(f"{INBOUND_URL}/{p['id']}", headers=org_headers).json()

        assert client.patch(
            f"{INBOUND_URL}/{p['id']}", headers=org_headers, json={"vehicle_id": None}
        ).status_code == 200

        order = db_session.get(InboundOrder, p["id"])
        db_session.refresh(order)
        assert order.vehicle_id is None
        purchase = db_session.get(Purchase, detail["purchases"][0]["purchase_id"])
        db_session.refresh(purchase)
        assert purchase.vehicle_plate is None

    def test_draft_edit_lands_on_purchases_at_liquidation(
        self, client, org_headers, db_session, warehouse, willard_tp, sup_regular, mat_regular
    ):
        """Re-semantizado por #93 (era test_propagates_after_liquidation, hoy
        redundante: las compras solo existen post-liquidacion). La correccion
        ANTES de liquidar tambien cuenta: editar el vehiculo en draft no tiene
        compras que tocar (200 igual) y la compra nace con la placa VIGENTE al
        liquidar, no con la de la captura."""
        v1 = self._vehicle(client, org_headers, "DDD444")
        v2 = self._vehicle(client, org_headers, "EEE555")
        p = _purchase_inbound(
            client, org_headers, warehouse, mat_regular,
            vehicle_id=v1["id"], date=_past(),
        ).json()

        assert client.patch(
            f"{INBOUND_URL}/{p['id']}", headers=org_headers, json={"vehicle_id": v2["id"]}
        ).status_code == 200

        _review(client, org_headers, p["id"])
        _liquidate_one(client, org_headers, p["id"], mat_regular, sup_regular)
        detail = client.get(f"{INBOUND_URL}/{p['id']}", headers=org_headers).json()
        purchase = db_session.get(Purchase, detail["purchases"][0]["purchase_id"])
        db_session.refresh(purchase)
        assert purchase.vehicle_plate == "EEE555"
