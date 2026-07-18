"""
Tests SAC Ciclo B — canal unico + sede determinista + guard Willard-puro + B4
(plan-sac-ciclo-b-recepcion-compras.md v1.1, CC-007).

B1: origen inbound en PurchaseResponse (lookup por pagina F3 — sin JOIN).
B2: homogeneidad de mundo (Q-10: camion mixto = dos recepciones — test en
    test_inbound_orders.test_mixed_worlds_rejected_homogeneity) + drosses van
    a la planta configurada (willard_sede_drosses; None = compat, no valida).
B3: material Willard-puro (world != none y compra_regular=False) NO entra por
    compra — bloqueo 400 en create Y update, solo con flag (inerte sin el).
B4: goes_directly_to_jm retirado de la superficie — enviarlo da 422 (F1 QA:
    extra="forbid" rechaza, no ignora); la columna queda inerte.
F2: las claves nuevas viven en SETTING_DEFAULTS backend (trampa KeyError D12).
"""
import pytest
from datetime import datetime, timezone
from decimal import Decimal

from app.utils.org_settings import SETTING_DEFAULTS, get_org_setting
from tests.integration_helpers import create_material, create_material_category, create_warehouse
from tests.conftest import create_third_party_with_category

INBOUND_URL = "/api/v1/inbound-orders"
PURCHASES_URL = "/api/v1/purchases"
KG_URL = "/api/v1/kg-ledger"
FORMULAS_URL = "/api/v1/material-conversion-formulas"
PROFILES_URL = "/api/v1/material-kg-profiles"


# ---------------------------------------------------------------------------
# Fixtures / helpers (patron test_inbound_orders)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _enable_flag(db_session, test_organization):
    test_organization.settings = {"kg_ledger_enabled": True}
    db_session.commit()


@pytest.fixture
def wh_jm(db_session, test_organization):
    wh = create_warehouse(db_session, test_organization.id, "Juan Mina")
    db_session.commit()
    return wh


@pytest.fixture
def wh_cv(db_session, test_organization):
    wh = create_warehouse(db_session, test_organization.id, "Circunvalar")
    db_session.commit()
    return wh


@pytest.fixture
def supplier(db_session, test_organization):
    tp = create_third_party_with_category(
        db_session, test_organization.id, "Proveedor Ciclo B", "material_supplier"
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
    return resp.json()


def _post_formula(client, headers, material_id, ftype, params):
    resp = client.post(
        FORMULAS_URL, headers=headers,
        json={"material_id": str(material_id), "formula_type": ftype, "parameters": params},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def mat_dross(db_session, test_organization, client, org_headers):
    mat = _mat(db_session, test_organization.id, "DROSS-B", unit="kg")
    _post_formula(client, org_headers, mat.id, "drosses_to_lead", {"lead_percentage": 0.5})
    _set_profile(client, org_headers, mat.id, willard_world="drosses")
    return mat


@pytest.fixture
def mat_compra(db_session, test_organization, client, org_headers):
    """Material de compra regular (world=none, compra_regular=True)."""
    mat = _mat(db_session, test_organization.id, "CHATARRA-B", unit="kg")
    _set_profile(client, org_headers, mat.id, compra_regular=True, willard_world="none")
    return mat


@pytest.fixture
def mat_willard_puro(db_session, test_organization, client, org_headers):
    """Willard-puro: postconsumo, NO compra regular — el objetivo del guard B3."""
    mat = _mat(db_session, test_organization.id, "BAT-PURA", unit="unidad")
    _post_formula(client, org_headers, mat.id, "battery_to_lead", {"kg_lead_per_unit": 2.5})
    _set_profile(client, org_headers, mat.id, compra_regular=False, willard_world="postconsumo")
    return mat


@pytest.fixture
def kg_dross_account(client, org_headers, supplier):
    resp = client.post(
        f"{KG_URL}/accounts", headers=org_headers,
        json={
            "code": "W-DROSS-B", "display_name": "Willard Drosses B",
            "account_type": "willard_drosses", "third_party_id": str(supplier.id),
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def kg_bat_cv(client, org_headers, wh_cv, supplier):
    resp = client.post(
        f"{KG_URL}/accounts", headers=org_headers,
        json={
            "code": "W-BAT-CV-B", "display_name": "Willard Baterias CV B",
            "account_type": "willard_baterias", "warehouse_id": str(wh_cv.id),
            "third_party_id": str(supplier.id),
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _today():
    return datetime.now(timezone.utc).date().isoformat()


def _inbound(client, headers, *, inbound_type, warehouse_id, third_party_id, lines, **extra):
    return client.post(
        INBOUND_URL, headers=headers,
        json={
            "inbound_type": inbound_type,
            "warehouse_id": str(warehouse_id),
            "third_party_id": str(third_party_id),
            "date": _today(),
            "lines": lines,
            **extra,
        },
    )


def _confirm(client, headers, order_id):
    """B.2: draft -> confirmed (los efectos willard nacen al confirmar)."""
    resp = client.post(f"{INBOUND_URL}/{order_id}/confirm", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _purchase(client, headers, *, supplier_id, material_id, warehouse_id, qty="100", price="1000"):
    return client.post(
        PURCHASES_URL, headers=headers,
        json={
            "supplier_id": str(supplier_id),
            "date": _today(),
            "lines": [{
                "material_id": str(material_id),
                "warehouse_id": str(warehouse_id),
                "quantity": qty,
                "unit_price": price,
            }],
        },
    )


def _set_org_settings(db, org, **extra):
    org.settings = {"kg_ledger_enabled": True, **extra}
    db.commit()


# ---------------------------------------------------------------------------
# F2 — settings backend (trampa D12)
# ---------------------------------------------------------------------------

class TestCicloBSettings:
    def test_setting_defaults_backend_has_keys(self):
        """F2 QA: sin las claves en SETTING_DEFAULTS backend, get_org_setting
        lanza KeyError (D12) — el guard de B2 las lee."""
        assert "willard_sede_drosses" in SETTING_DEFAULTS
        assert "willard_sede_postconsumo_default" in SETTING_DEFAULTS
        assert SETTING_DEFAULTS["willard_sede_drosses"] is None
        assert SETTING_DEFAULTS["willard_sede_postconsumo_default"] is None

    def test_get_org_setting_reads_configured_value(self, db_session, test_organization, wh_jm):
        _set_org_settings(db_session, test_organization, willard_sede_drosses=str(wh_jm.id))
        assert get_org_setting(
            db_session, test_organization.id, "willard_sede_drosses"
        ) == str(wh_jm.id)
        # Clave no configurada -> default None (no KeyError)
        assert get_org_setting(
            db_session, test_organization.id, "willard_sede_postconsumo_default"
        ) is None

    def test_payload_accepts_str_rejects_non_str(self):
        from app.schemas.organization import OrgSettingsPayload
        p = OrgSettingsPayload(willard_sede_drosses="abc", willard_sede_postconsumo_default="def")
        assert p.willard_sede_drosses == "abc"
        with pytest.raises(Exception):
            OrgSettingsPayload(willard_sede_drosses=123)  # strict: sin coercion


# ---------------------------------------------------------------------------
# B2 — drosses van a la planta configurada
# ---------------------------------------------------------------------------

class TestDrossesSedeDeterminista:
    def test_drosses_wrong_warehouse_rejected(
        self, client, org_headers, db_session, test_organization,
        wh_jm, wh_cv, supplier, mat_dross, kg_dross_account,
    ):
        _set_org_settings(db_session, test_organization, willard_sede_drosses=str(wh_jm.id))
        resp = _inbound(
            client, org_headers,
            inbound_type="willard", warehouse_id=wh_cv.id, third_party_id=supplier.id,
            lines=[{"material_id": str(mat_dross.id), "quantity": "100"}],
        )
        assert resp.status_code == 422, resp.text
        assert "Juan Mina" in resp.json()["detail"]

    def test_drosses_correct_warehouse_ok(
        self, client, org_headers, db_session, test_organization,
        wh_jm, supplier, mat_dross, kg_dross_account,
    ):
        _set_org_settings(db_session, test_organization, willard_sede_drosses=str(wh_jm.id))
        resp = _inbound(
            client, org_headers,
            inbound_type="willard", warehouse_id=wh_jm.id, third_party_id=supplier.id,
            lines=[{"material_id": str(mat_dross.id), "quantity": "100"}],
        )
        assert resp.status_code == 201, resp.text
        body = _confirm(client, org_headers, resp.json()["id"])  # B.2: efectos al confirmar
        assert Decimal(body["total_kg_lead"]) == Decimal("50")

    def test_drosses_no_setting_any_warehouse_ok(
        self, client, org_headers, wh_cv, supplier, mat_dross, kg_dross_account,
    ):
        """Setting None (compat): orgs sin configurar no rompen — no valida."""
        resp = _inbound(
            client, org_headers,
            inbound_type="willard", warehouse_id=wh_cv.id, third_party_id=supplier.id,
            lines=[{"material_id": str(mat_dross.id), "quantity": "100"}],
        )
        assert resp.status_code == 201, resp.text

    def test_postconsumo_any_sede_with_account_ok(
        self, client, org_headers, db_session, test_organization,
        wh_jm, wh_cv, supplier, mat_willard_puro, kg_bat_cv,
    ):
        """Postconsumo NO se bloquea por sede en backend (editable entre sedes
        con cuenta willard_baterias — el filtro vive en el frontend); el
        setting de drosses no interfiere."""
        _set_org_settings(db_session, test_organization, willard_sede_drosses=str(wh_jm.id))
        resp = _inbound(
            client, org_headers,
            inbound_type="willard", warehouse_id=wh_cv.id, third_party_id=supplier.id,
            lines=[{"material_id": str(mat_willard_puro.id), "quantity": "10"}],
        )
        assert resp.status_code == 201, resp.text
        body = _confirm(client, org_headers, resp.json()["id"])  # B.2: efectos al confirmar
        assert Decimal(body["total_kg_lead"]) == Decimal("25")


# ---------------------------------------------------------------------------
# B3 — guard Willard-puro en compras (bloqueo 400)
# ---------------------------------------------------------------------------

class TestGuardWillardPuro:
    def test_manual_purchase_willard_pure_blocked(
        self, client, org_headers, wh_cv, supplier, mat_willard_puro,
    ):
        resp = _purchase(
            client, org_headers,
            supplier_id=supplier.id, material_id=mat_willard_puro.id, warehouse_id=wh_cv.id,
        )
        assert resp.status_code == 400, resp.text
        assert "BAT-PURA" in resp.json()["detail"]
        assert "recepcion Willard" in resp.json()["detail"]

    def test_derived_purchase_willard_pure_blocked(
        self, client, org_headers, wh_cv, supplier, mat_willard_puro,
    ):
        """El mismo guard fia en el path inbound->purchase (un solo guard,
        dos puertas cubiertas)."""
        resp = _inbound(
            client, org_headers,
            inbound_type="purchase", warehouse_id=wh_cv.id, third_party_id=supplier.id,
            lines=[{
                "material_id": str(mat_willard_puro.id),
                "quantity": "10", "unit_price": "500",
            }],
        )
        assert resp.status_code == 400, resp.text
        assert "recepcion Willard" in resp.json()["detail"]

    def test_both_channels_material_purchasable(
        self, client, org_headers, db_session, test_organization, wh_cv, supplier,
    ):
        """Q-04: una referencia puede entrar por AMBOS canales (world=postconsumo
        Y compra_regular=True) — NO es Willard-pura, la compra pasa."""
        mat = _mat(db_session, test_organization.id, "BAT-AMBOS", unit="unidad")
        _set_profile(
            client, org_headers, mat.id, compra_regular=True, willard_world="postconsumo"
        )
        resp = _purchase(
            client, org_headers,
            supplier_id=supplier.id, material_id=mat.id, warehouse_id=wh_cv.id,
        )
        assert resp.status_code == 201, resp.text

    def test_unclassified_material_purchasable(
        self, client, org_headers, db_session, test_organization, wh_cv, supplier,
    ):
        """Material sin perfil (no clasificado) compra normal — el guard solo
        actua sobre clasificacion explicita Willard-pura."""
        mat = _mat(db_session, test_organization.id, "SIN-PERFIL", unit="kg")
        resp = _purchase(
            client, org_headers,
            supplier_id=supplier.id, material_id=mat.id, warehouse_id=wh_cv.id,
        )
        assert resp.status_code == 201, resp.text

    def test_without_flag_guard_inert(
        self, client, org_headers, db_session, test_organization, wh_cv, supplier, mat_willard_puro,
    ):
        """Sin kg_ledger_enabled el guard es inerte (prod byte-identico) —
        aunque exista un perfil residual."""
        test_organization.settings = {"kg_ledger_enabled": False}
        db_session.commit()
        resp = _purchase(
            client, org_headers,
            supplier_id=supplier.id, material_id=mat_willard_puro.id, warehouse_id=wh_cv.id,
        )
        assert resp.status_code == 201, resp.text

    def test_update_lines_willard_pure_blocked(
        self, client, org_headers, wh_cv, supplier, mat_compra, mat_willard_puro,
    ):
        """Editar una compra valida metiendole material Willard-puro -> 400
        (sin esto, el guard de create se esquiva por edicion)."""
        created = _purchase(
            client, org_headers,
            supplier_id=supplier.id, material_id=mat_compra.id, warehouse_id=wh_cv.id,
        )
        assert created.status_code == 201, created.text
        pid = created.json()["id"]
        resp = client.patch(
            f"{PURCHASES_URL}/{pid}", headers=org_headers,
            json={"lines": [{
                "material_id": str(mat_willard_puro.id),
                "warehouse_id": str(wh_cv.id),
                "quantity": "5", "unit_price": "900",
            }]},
        )
        assert resp.status_code == 400, resp.text
        assert "recepcion Willard" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# B1 — origen inbound en PurchaseResponse
# ---------------------------------------------------------------------------

class TestPurchaseInboundOrigin:
    def test_derived_purchase_exposes_origin(
        self, client, org_headers, wh_cv, supplier, mat_compra,
    ):
        order = _inbound(
            client, org_headers,
            inbound_type="purchase", warehouse_id=wh_cv.id, third_party_id=supplier.id,
            lines=[{
                "material_id": str(mat_compra.id), "quantity": "100", "unit_price": "800",
            }],
        ).json()
        pid = order["purchase_id"]
        assert pid is not None

        # Detalle
        detail = client.get(f"{PURCHASES_URL}/{pid}", headers=org_headers).json()
        assert detail["inbound_order_id"] == order["id"]
        assert detail["inbound_order_number"] == order["order_number"]

        # Listado (lookup por pagina F3)
        listing = client.get(PURCHASES_URL, headers=org_headers).json()
        row = next(i for i in listing["items"] if i["id"] == pid)
        assert row["inbound_order_number"] == order["order_number"]

    def test_manual_purchase_origin_null(
        self, client, org_headers, wh_cv, supplier, mat_compra,
    ):
        created = _purchase(
            client, org_headers,
            supplier_id=supplier.id, material_id=mat_compra.id, warehouse_id=wh_cv.id,
        )
        pid = created.json()["id"]
        detail = client.get(f"{PURCHASES_URL}/{pid}", headers=org_headers).json()
        assert detail["inbound_order_id"] is None
        assert detail["inbound_order_number"] is None
        listing = client.get(PURCHASES_URL, headers=org_headers).json()
        row = next(i for i in listing["items"] if i["id"] == pid)
        assert row["inbound_order_number"] is None

    def test_org_without_inbounds_list_ok(
        self, client, org_headers, db_session, test_organization, wh_cv, supplier, mat_compra,
    ):
        """Orgs prod (sin recepciones, sin flag): el listado no cambia — campos
        null, cero errores."""
        test_organization.settings = None
        db_session.commit()
        created = _purchase(
            client, org_headers,
            supplier_id=supplier.id, material_id=mat_compra.id, warehouse_id=wh_cv.id,
        )
        assert created.status_code == 201
        listing = client.get(PURCHASES_URL, headers=org_headers)
        assert listing.status_code == 200
        assert all(i["inbound_order_number"] is None for i in listing.json()["items"])


# ---------------------------------------------------------------------------
# B4 — goes_directly_to_jm retirado (F1: 422, no ignorado)
# ---------------------------------------------------------------------------

class TestGoesDirectlyRetired:
    def test_create_with_field_422(
        self, client, org_headers, wh_cv, supplier, mat_dross, kg_dross_account,
    ):
        resp = _inbound(
            client, org_headers,
            inbound_type="willard", warehouse_id=wh_cv.id, third_party_id=supplier.id,
            lines=[{"material_id": str(mat_dross.id), "quantity": "10"}],
            goes_directly_to_jm=True,
        )
        assert resp.status_code == 422, resp.text

    def test_patch_with_field_422(
        self, client, org_headers, wh_cv, supplier, mat_dross, kg_dross_account,
    ):
        order = _inbound(
            client, org_headers,
            inbound_type="willard", warehouse_id=wh_cv.id, third_party_id=supplier.id,
            lines=[{"material_id": str(mat_dross.id), "quantity": "10"}],
        ).json()
        resp = client.patch(
            f"{INBOUND_URL}/{order['id']}", headers=org_headers,
            json={"goes_directly_to_jm": True},
        )
        assert resp.status_code == 422, resp.text

    def test_response_without_field(
        self, client, org_headers, wh_cv, supplier, mat_dross, kg_dross_account,
    ):
        order = _inbound(
            client, org_headers,
            inbound_type="willard", warehouse_id=wh_cv.id, third_party_id=supplier.id,
            lines=[{"material_id": str(mat_dross.id), "quantity": "10"}],
        ).json()
        assert "goes_directly_to_jm" not in order
        detail = client.get(f"{INBOUND_URL}/{order['id']}", headers=org_headers).json()
        assert "goes_directly_to_jm" not in detail


# ---------------------------------------------------------------------------
# Addendum feedback Daniel (2026-07-17): tercero Willard fijo + notes cabecera
# ---------------------------------------------------------------------------

class TestWillardThirdPartyLocked:
    def test_willard_wrong_third_party_422(
        self, client, org_headers, db_session, test_organization,
        wh_cv, supplier, mat_dross, kg_dross_account,
    ):
        """El tercero de una recepcion Willard ES el titular de la cuenta kg —
        otro proveedor -> 422 con el nombre del titular."""
        otro = create_third_party_with_category(
            db_session, test_organization.id, "Otro Proveedor", "material_supplier"
        )
        db_session.commit()
        resp = _inbound(
            client, org_headers,
            inbound_type="willard", warehouse_id=wh_cv.id, third_party_id=otro.id,
            lines=[{"material_id": str(mat_dross.id), "quantity": "10"}],
        )
        assert resp.status_code == 422, resp.text
        assert "titular de la cuenta kg" in resp.json()["detail"]
        assert supplier.name in resp.json()["detail"]

    def test_purchase_type_any_supplier_ok(
        self, client, org_headers, db_session, test_organization, wh_cv, mat_compra,
    ):
        """El lock aplica SOLO a Willard — compra regular acepta cualquier
        proveedor de material."""
        otro = create_third_party_with_category(
            db_session, test_organization.id, "Proveedor Chatarra", "material_supplier"
        )
        db_session.commit()
        resp = _inbound(
            client, org_headers,
            inbound_type="purchase", warehouse_id=wh_cv.id, third_party_id=otro.id,
            lines=[{"material_id": str(mat_compra.id), "quantity": "50", "unit_price": "700"}],
        )
        assert resp.status_code == 201, resp.text


class TestReceivingWarehouses:
    """Q-12 (feedback Daniel): bodegas internas (molino/transito) no reciben
    de terceros — flag is_receiving en la bodega (default True: una bodega
    nueva nace receptora, autoservicio)."""

    def test_default_true_and_toggle(self, client, org_headers):
        created = client.post(
            "/api/v1/warehouses", headers=org_headers,
            json={"name": "Sede Nueva Q12"},
        )
        assert created.status_code == 201, created.text
        assert created.json()["is_receiving"] is True
        wid = created.json()["id"]
        upd = client.patch(
            f"/api/v1/warehouses/{wid}", headers=org_headers,
            json={"is_receiving": False},
        )
        assert upd.status_code == 200, upd.text
        assert upd.json()["is_receiving"] is False

    def test_inbound_to_internal_warehouse_422(
        self, client, org_headers, db_session, test_organization, supplier, mat_compra,
    ):
        molino = create_warehouse(db_session, test_organization.id, "CV - Molino Q12")
        molino.is_receiving = False
        db_session.commit()
        resp = _inbound(
            client, org_headers,
            inbound_type="purchase", warehouse_id=molino.id, third_party_id=supplier.id,
            lines=[{"material_id": str(mat_compra.id), "quantity": "10", "unit_price": "500"}],
        )
        assert resp.status_code == 422, resp.text
        assert "interna" in resp.json()["detail"]


class TestInboundHeaderNotes:
    def test_notes_roundtrip_create(
        self, client, org_headers, wh_cv, supplier, mat_dross, kg_dross_account,
    ):
        resp = _inbound(
            client, org_headers,
            inbound_type="willard", warehouse_id=wh_cv.id, third_party_id=supplier.id,
            lines=[{"material_id": str(mat_dross.id), "quantity": "10"}],
            notes="Camion azul, llego 6am",
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["notes"] == "Camion azul, llego 6am"

    def test_notes_editable_on_purchase_type(
        self, client, org_headers, wh_cv, supplier, mat_compra,
    ):
        """notes es cabecera informativa — editable tambien en tipo purchase
        (NO esta en el set bloqueado de D7b)."""
        order = _inbound(
            client, org_headers,
            inbound_type="purchase", warehouse_id=wh_cv.id, third_party_id=supplier.id,
            lines=[{"material_id": str(mat_compra.id), "quantity": "50", "unit_price": "700"}],
        ).json()
        resp = client.patch(
            f"{INBOUND_URL}/{order['id']}", headers=org_headers,
            json={"notes": "Corregida placa en compra"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["notes"] == "Corregida placa en compra"
