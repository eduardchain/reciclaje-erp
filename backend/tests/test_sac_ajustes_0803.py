"""Tests de los ajustes rapidos de la reunion SAC del 3-ago-2026.

Cubre:
  A — factura en la Entrada con FUENTE UNICA POR TIPO (D1): tipo compra la
      guarda en purchases.invoice_number y deja NULL la columna del inbound;
      willard al reves. La lectura del response es condicional -> la
      desincronizacion es imposible por construccion.
  C — autoservicio de centros de distribucion Willard: endpoint estrecho que
      SOLO puede tocar esa clave del JSONB de settings (D6). El test estrella
      relee desde BD (H4: mutar in-place no persiste y el assert contra el
      response no lo detectaria).
  E — la placa editada en la Entrada llega a la compra derivada, y quitar el
      vehiculo ahora es posible (asimetria de fields_set alineada).

B (hora en auditoria) y D (categoria financiera del seeder) no llevan test:
frontend puro y data de seeder respectivamente (§6 del plan).
"""
import pytest
from datetime import datetime, timezone

from app.models.inbound_order import InboundOrder
from app.models.organization import Organization
from app.models.purchase import Purchase
from tests.integration_helpers import create_material, create_material_category, create_warehouse
from tests.conftest import create_third_party_with_category

INBOUND_URL = "/api/v1/inbound-orders"
KG_URL = "/api/v1/kg-ledger"
FORMULAS_URL = "/api/v1/material-conversion-formulas"
PROFILES_URL = "/api/v1/material-kg-profiles"
CENTERS_URL = "/api/v1/organizations/settings/willard-distribution-centers"
PURCHASES_URL = "/api/v1/purchases"
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


def _inbound(client, headers, *, inbound_type, warehouse_id, third_party_id, lines, **extra):
    body = {
        "inbound_type": inbound_type,
        "warehouse_id": str(warehouse_id),
        "third_party_id": str(third_party_id),
        "date": datetime.now(timezone.utc).date().isoformat(),
        "lines": lines,
        **extra,
    }
    return client.post(INBOUND_URL, headers=headers, json=body)


def _purchase_inbound(client, headers, warehouse, supplier, mat, **extra):
    return _inbound(
        client, headers,
        inbound_type="purchase",
        warehouse_id=warehouse.id,
        third_party_id=supplier.id,
        lines=[{"material_id": str(mat.id), "quantity": "100", "unit_price": "1000"}],
        **extra,
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
        self, client, org_headers, db_session, warehouse, willard_tp, mat_regular
    ):
        """D1: la factura del documento comercial vive en la compra; la columna
        del inbound queda NULL. Dos copias del mismo dato serian dos fuentes de
        verdad que habria que sincronizar en tres caminos de escritura."""
        resp = _purchase_inbound(
            client, org_headers, warehouse, willard_tp, mat_regular,
            invoice_number="FAC-1001",
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["invoice_number"] == "FAC-1001"

        order = db_session.get(InboundOrder, data["id"])
        db_session.refresh(order)
        assert order.invoice_number is None, "la columna del inbound debe quedar NULL"
        assert order.purchase.invoice_number == "FAC-1001"

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
        self, client, org_headers, db_session, warehouse, willard_tp, mat_regular,
        mat_bat, kg_bat_account,
    ):
        p = _purchase_inbound(
            client, org_headers, warehouse, willard_tp, mat_regular, invoice_number="A-1"
        ).json()
        w = _willard_inbound(
            client, org_headers, warehouse, willard_tp, mat_bat, invoice_number="B-1"
        ).json()

        assert client.patch(
            f"{INBOUND_URL}/{p['id']}", headers=org_headers, json={"invoice_number": "A-2"}
        ).status_code == 200
        assert client.patch(
            f"{INBOUND_URL}/{w['id']}", headers=org_headers, json={"invoice_number": "B-2"}
        ).status_code == 200

        po = db_session.get(InboundOrder, p["id"])
        wo = db_session.get(InboundOrder, w["id"])
        db_session.refresh(po)
        db_session.refresh(wo)
        assert po.purchase.invoice_number == "A-2" and po.invoice_number is None
        assert wo.invoice_number == "B-2"

    def test_explicit_null_clears_invoice(
        self, client, org_headers, db_session, warehouse, willard_tp, mat_regular
    ):
        """exclude_unset distingue ausente de null explicito (patron de notes)."""
        p = _purchase_inbound(
            client, org_headers, warehouse, willard_tp, mat_regular, invoice_number="BORRAME"
        ).json()

        # Ausente: no toca la factura
        client.patch(f"{INBOUND_URL}/{p['id']}", headers=org_headers, json={"notes": "x"})
        order = db_session.get(InboundOrder, p["id"])
        db_session.refresh(order)
        assert order.purchase.invoice_number == "BORRAME"

        # null explicito: la borra
        client.patch(
            f"{INBOUND_URL}/{p['id']}", headers=org_headers, json={"invoice_number": None}
        )
        db_session.refresh(order.purchase)
        assert order.purchase.invoice_number is None

    def test_editable_after_liquidation(
        self, client, org_headers, db_session, warehouse, willard_tp, mat_regular
    ):
        """D2: la factura del proveedor llega tarde con frecuencia. Bloquearla
        obligaria a anular una compra liquidada para escribir un numero. El
        resto del set bloqueado D7b sigue dando 400."""
        p = _purchase_inbound(client, org_headers, warehouse, willard_tp, mat_regular).json()
        liq = client.patch(
            f"{PURCHASES_URL}/{p['purchase_id']}/liquidate",
            headers=org_headers,
            json={"lines": [], "liquidation_date": datetime.now(timezone.utc).date().isoformat()},
        )
        assert liq.status_code == 200, liq.text

        ok = client.patch(
            f"{INBOUND_URL}/{p['id']}", headers=org_headers, json={"invoice_number": "TARDE-9"}
        )
        assert ok.status_code == 200, ok.text
        order = db_session.get(InboundOrder, p["id"])
        db_session.refresh(order)
        assert order.purchase.invoice_number == "TARDE-9"

        # El set bloqueado D7b responde 422 (idioma del modulo inbound, #80:
        # "inbound 422, compras 400") — invoice_number queda fuera de el.
        blocked = client.patch(
            f"{INBOUND_URL}/{p['id']}",
            headers=org_headers,
            json={"date": datetime.now(timezone.utc).date().isoformat()},
        )
        assert blocked.status_code == 422, blocked.text

    def test_response_reads_right_source_without_extra_queries(
        self, client, org_headers, db_session, warehouse, willard_tp, mat_regular,
        mat_bat, kg_bat_account,
    ):
        """Invariante estrella de A: list y detail exponen la factura correcta
        para los dos tipos, y el listado no gana queries (la compra derivada ya
        viene del enrich B1 por pagina)."""
        _purchase_inbound(
            client, org_headers, warehouse, willard_tp, mat_regular, invoice_number="LIST-P"
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
        items = {i["invoice_number"] for i in listed.json()["items"]}
        assert {"LIST-P", "LIST-W"} <= items

        # Sanity: el listado resuelve en un numero acotado de queries — si la
        # factura hubiera forzado un lookup por fila esto crecería con N.
        assert with_invoice < 40, f"demasiadas queries en el listado: {with_invoice}"

        for item in listed.json()["items"]:
            detail = client.get(f"{INBOUND_URL}/{item['id']}", headers=org_headers)
            assert detail.json()["invoice_number"] == item["invoice_number"]

    def test_search_by_invoice_keeps_willard_visible(
        self, client, org_headers, warehouse, willard_tp, mat_regular, mat_bat, kg_bat_account
    ):
        """H3: la factura vive en dos sitios, asi que el buscador tiene que
        alcanzar Purchase. Si ese alcance degradara el outerjoin a join, TODAS
        las willard desaparecerian en silencio del buscador."""
        _purchase_inbound(
            client, org_headers, warehouse, willard_tp, mat_regular, invoice_number="FX-500"
        )
        w = _willard_inbound(
            client, org_headers, warehouse, willard_tp, mat_bat, invoice_number="FX-600"
        ).json()

        by_p = client.get(f"{INBOUND_URL}?search=FX-500", headers=org_headers).json()
        assert [i["invoice_number"] for i in by_p["items"]] == ["FX-500"]

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
        self, client, org_headers, db_session, warehouse, willard_tp, mat_regular
    ):
        """El listado de Compras (#72) filtra y muestra por vehicle_plate — sin
        propagar, la correccion del operador no se ve donde importa."""
        v1 = self._vehicle(client, org_headers, "AAA111")
        v2 = self._vehicle(client, org_headers, "BBB222")

        p = _purchase_inbound(
            client, org_headers, warehouse, willard_tp, mat_regular, vehicle_id=v1["id"]
        ).json()
        order = db_session.get(InboundOrder, p["id"])
        db_session.refresh(order)
        assert order.purchase.vehicle_plate == "AAA111"

        assert client.patch(
            f"{INBOUND_URL}/{p['id']}", headers=org_headers, json={"vehicle_id": v2["id"]}
        ).status_code == 200
        db_session.refresh(order.purchase)
        assert order.purchase.vehicle_plate == "BBB222"

    def test_clearing_vehicle_clears_plate(
        self, client, org_headers, db_session, warehouse, willard_tp, mat_regular
    ):
        """Antes de este ciclo `is not None` impedia QUITAR el vehiculo: mandar
        null no hacia nada (asimetria con notes, que usa fields_set)."""
        v1 = self._vehicle(client, org_headers, "CCC333")
        p = _purchase_inbound(
            client, org_headers, warehouse, willard_tp, mat_regular, vehicle_id=v1["id"]
        ).json()

        assert client.patch(
            f"{INBOUND_URL}/{p['id']}", headers=org_headers, json={"vehicle_id": None}
        ).status_code == 200

        order = db_session.get(InboundOrder, p["id"])
        db_session.refresh(order)
        db_session.refresh(order.purchase)
        assert order.vehicle_id is None
        assert order.purchase.vehicle_plate is None

    def test_propagates_after_liquidation(
        self, client, org_headers, db_session, warehouse, willard_tp, mat_regular
    ):
        """D10 sin guard de estado: una compra liquidada con la placa
        equivocada es justo el caso que hay que poder corregir."""
        v1 = self._vehicle(client, org_headers, "DDD444")
        v2 = self._vehicle(client, org_headers, "EEE555")
        p = _purchase_inbound(
            client, org_headers, warehouse, willard_tp, mat_regular, vehicle_id=v1["id"]
        ).json()
        liq = client.patch(
            f"{PURCHASES_URL}/{p['purchase_id']}/liquidate",
            headers=org_headers,
            json={"lines": [], "liquidation_date": datetime.now(timezone.utc).date().isoformat()},
        )
        assert liq.status_code == 200, liq.text

        assert client.patch(
            f"{INBOUND_URL}/{p['id']}", headers=org_headers, json={"vehicle_id": v2["id"]}
        ).status_code == 200

        purchase = db_session.get(Purchase, p["purchase_id"])
        db_session.refresh(purchase)
        assert purchase.vehicle_plate == "EEE555"
