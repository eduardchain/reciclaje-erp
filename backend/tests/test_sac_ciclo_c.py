"""
Tests SAC Ciclo C — modulo unico "Entradas": capa de lectura derivada
(plan-sac-ciclo-c-entradas-unificadas.md v1.0).

C-1: display_status — estado UNICO visible (registered|liquidated|annulled)
     derivado de orden+compra; filtro SQL espejo del campo del enrich
     (test de paridad W-C2, incl. cancelled-post-liquidacion).
C-2: search — #, placa, conductor, tercero, material (ILIKE OR + EXISTS lineas).
C-3: sort=oldest — FIFO para la bandeja de Johana.
C-4: willard_world en response (drosses|postconsumo; null tipo compra).
C-5: quien hizo que — created_by_name / liquidated_by_name (compra:
     Purchase.liquidated_by; willard: created_by del primer kg movement) /
     annulled_by_name.

Todo aditivo sobre el router flag-gated — create/confirm/annul/update intactos.
"""
import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from tests.integration_helpers import create_material, create_material_category, create_warehouse
from tests.conftest import create_third_party_with_category

INBOUND_URL = "/api/v1/inbound-orders"
PURCHASES_URL = "/api/v1/purchases"
KG_URL = "/api/v1/kg-ledger"
FORMULAS_URL = "/api/v1/material-conversion-formulas"
PROFILES_URL = "/api/v1/material-kg-profiles"
DRIVERS_URL = "/api/v1/drivers"
VEHICLES_URL = "/api/v1/vehicles"


# ---------------------------------------------------------------------------
# Fixtures / helpers (patron test_sac_ciclo_b)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _enable_flag(db_session, test_organization, test_organization2):
    test_organization.settings = {"kg_ledger_enabled": True}
    test_organization2.settings = {"kg_ledger_enabled": True}
    db_session.commit()


@pytest.fixture
def wh_cv(db_session, test_organization):
    wh = create_warehouse(db_session, test_organization.id, "Circunvalar C")
    db_session.commit()
    return wh


@pytest.fixture
def supplier(db_session, test_organization):
    tp = create_third_party_with_category(
        db_session, test_organization.id, "Willard Ciclo C", "material_supplier"
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


def _post_formula(client, headers, material_id, ftype, params):
    resp = client.post(
        FORMULAS_URL, headers=headers,
        json={"material_id": str(material_id), "formula_type": ftype, "parameters": params},
    )
    assert resp.status_code == 201, resp.text


@pytest.fixture
def mat_dross(db_session, test_organization, client, org_headers):
    mat = _mat(db_session, test_organization.id, "DROSS-C", unit="kg")
    _post_formula(client, org_headers, mat.id, "drosses_to_lead", {"lead_percentage": 0.5})
    _set_profile(client, org_headers, mat.id, willard_world="drosses")
    return mat


@pytest.fixture
def mat_bat(db_session, test_organization, client, org_headers):
    mat = _mat(db_session, test_organization.id, "BAT-C", unit="unidad")
    _post_formula(client, org_headers, mat.id, "battery_to_lead", {"kg_lead_per_unit": 2.5})
    _set_profile(client, org_headers, mat.id, willard_world="postconsumo")
    return mat


@pytest.fixture
def mat_compra(db_session, test_organization, client, org_headers):
    mat = _mat(db_session, test_organization.id, "CHATARRA-C", unit="kg")
    _set_profile(client, org_headers, mat.id, compra_regular=True, willard_world="none")
    return mat


@pytest.fixture
def willard_holder(db_session, test_organization):
    """Titular de las cuentas kg. Antes era el MISMO `supplier` que reparte las
    compras, atajo que dejo de ser valido con el guard de #80 (el titular de una
    cuenta kg no puede ser proveedor de compra): un solo tercero no puede vivir
    en los dos canales. Separarlos es tambien mas fiel a la realidad."""
    tp = create_third_party_with_category(
        db_session, test_organization.id, "Willard S.A. (titular kg)",
        "material_supplier",
    )
    db_session.commit()
    return tp


@pytest.fixture
def kg_dross_account(client, org_headers, willard_holder):
    resp = client.post(
        f"{KG_URL}/accounts", headers=org_headers,
        json={
            "code": "W-DROSS-C", "display_name": "Willard Drosses C",
            "account_type": "willard_drosses",
            "third_party_id": str(willard_holder.id),
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def kg_bat_cv(client, org_headers, wh_cv, willard_holder):
    resp = client.post(
        f"{KG_URL}/accounts", headers=org_headers,
        json={
            "code": "W-BAT-C", "display_name": "Willard Baterias C",
            "account_type": "willard_baterias", "warehouse_id": str(wh_cv.id),
            "third_party_id": str(willard_holder.id),
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _past(days=2):
    return (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()


def _weighed(line: dict) -> dict:
    """Q-13: el peso es opcional al capturar pero obligatorio al REVISAR."""
    if "scale_weight_kg" in line:
        out = dict(line)
        if out["scale_weight_kg"] is None:
            out.pop("scale_weight_kg")
        return out
    return {**line, "scale_weight_kg": "100"}


def _inbound(client, headers, *, inbound_type, warehouse_id, third_party_id=None,
             lines, date_str=None, **extra):
    body = {
        "inbound_type": inbound_type,
        "warehouse_id": str(warehouse_id),
        "date": date_str or _past(),
        "lines": [_weighed(l) for l in lines],
        **extra,
    }
    if third_party_id is not None:
        body["third_party_id"] = str(third_party_id)
    resp = client.post(INBOUND_URL, headers=headers, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _willard(client, headers, wh, tp, mat, qty="10"):
    return _inbound(
        client, headers, inbound_type="willard", warehouse_id=wh.id,
        third_party_id=tp.id, lines=[{"material_id": str(mat.id), "quantity": qty}],
    )


def _purchase_order(client, headers, wh, mat, qty="100", **extra):
    """#93: la captura tipo compra NO lleva proveedor — llega al liquidar."""
    return _inbound(
        client, headers, inbound_type="purchase", warehouse_id=wh.id,
        lines=[{"material_id": str(mat.id), "quantity": qty}],
        **extra,
    )


def _confirm(client, headers, order_id):
    """Q-16: la willard pasa por revision antes de confirmar."""
    rev = client.post(f"{INBOUND_URL}/{order_id}/review", headers=headers)
    assert rev.status_code == 200, rev.text
    resp = client.post(f"{INBOUND_URL}/{order_id}/confirm", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _review(client, headers, order_id):
    resp = client.post(f"{INBOUND_URL}/{order_id}/review", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _liquidate_order(client, headers, order, mat, tp, qty="100", price="900"):
    """#93: reviewed -> liquidated con reparto de UN proveedor."""
    resp = client.post(
        f"{INBOUND_URL}/{order['id']}/liquidate", headers=headers,
        json={"lines": [{
            "material_id": str(mat.id),
            "allocations": [{
                "third_party_id": str(tp.id),
                "quantity": str(qty), "unit_price": str(price),
            }],
        }]},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _detail(client, headers, order_id):
    resp = client.get(f"{INBOUND_URL}/{order_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _listing(client, headers, **params):
    resp = client.get(INBOUND_URL, headers=headers, params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# C-1 — display_status: mapeo campo por campo
# ---------------------------------------------------------------------------

class TestDisplayStatus:
    def test_willard_draft_registered(
        self, client, org_headers, wh_cv, willard_holder, supplier, mat_bat, kg_bat_cv,
    ):
        body = _willard(client, org_headers, wh_cv, willard_holder, mat_bat)
        assert body["display_status"] == "registered"
        assert body["status"] == "draft"  # el tecnico sigue expuesto (compat)

    def test_willard_confirmed_liquidated(
        self, client, org_headers, wh_cv, willard_holder, supplier, mat_bat, kg_bat_cv,
    ):
        body = _willard(client, org_headers, wh_cv, willard_holder, mat_bat)
        out = _confirm(client, org_headers, body["id"])
        assert out["display_status"] == "liquidated"

    def test_willard_annulled(
        self, client, org_headers, wh_cv, willard_holder, supplier, mat_bat, kg_bat_cv,
    ):
        body = _willard(client, org_headers, wh_cv, willard_holder, mat_bat)
        resp = client.post(
            f"{INBOUND_URL}/{body['id']}/annul", headers=org_headers,
            json={"reason": "c"},
        )
        assert resp.json()["display_status"] == "annulled"

    def test_purchase_draft_and_reviewed(
        self, client, org_headers, wh_cv, mat_compra,
    ):
        """#93: la entrada tipo compra nace draft (Registrada) y la revision
        es un estado visible propio (Revisada)."""
        body = _purchase_order(client, org_headers, wh_cv, mat_compra)
        assert body["status"] == "draft"
        assert body["display_status"] == "registered"
        assert body["purchases"] == []

        out = _review(client, org_headers, body["id"])
        assert out["status"] == "reviewed"
        assert out["display_status"] == "reviewed"

    def test_purchase_liquidated(
        self, client, org_headers, wh_cv, supplier, mat_compra,
    ):
        body = _purchase_order(client, org_headers, wh_cv, mat_compra)
        _review(client, org_headers, body["id"])
        out = _liquidate_order(client, org_headers, body, mat_compra, supplier)
        assert out["display_status"] == "liquidated"

    def test_purchase_annulled_after_liquidation(
        self, client, org_headers, wh_cv, supplier, mat_compra,
    ):
        """#93 supersede el caso W-C2: la compra puente no se cancela directo
        (400) — anular la entrada LIQUIDADA delega en unliquidate y el usuario
        ve UNA cosa: Anulada."""
        body = _purchase_order(client, org_headers, wh_cv, mat_compra)
        _review(client, org_headers, body["id"])
        result = _liquidate_order(client, org_headers, body, mat_compra, supplier)
        pid = result["purchases"][0]["purchase_id"]
        resp = client.patch(f"{PURCHASES_URL}/{pid}/cancel", headers=org_headers)
        assert resp.status_code == 400  # guia a la Entrada

        resp = client.post(
            f"{INBOUND_URL}/{body['id']}/annul", headers=org_headers,
            json={"reason": "c"},
        )
        assert resp.status_code == 200, resp.text
        out = _detail(client, org_headers, body["id"])
        assert out["status"] == "annulled"
        assert out["display_status"] == "annulled"

    def test_purchase_order_annulled(
        self, client, org_headers, wh_cv, mat_compra,
    ):
        """Anular la captura draft — Anulada (sin compras que cancelar)."""
        body = _purchase_order(client, org_headers, wh_cv, mat_compra)
        resp = client.post(
            f"{INBOUND_URL}/{body['id']}/annul", headers=org_headers,
            json={"reason": "c"},
        )
        assert resp.json()["display_status"] == "annulled"

    def test_filter_parity_with_field(
        self, client, org_headers, wh_cv, willard_holder, supplier, mat_bat, mat_compra,
        kg_bat_cv,
    ):
        """W-C2 guardrail: para cada valor del filtro, los ids retornados ==
        los ids cuyo campo display_status tiene ese valor (sin filtro).
        #93: se suma el estado 'reviewed'."""
        # Set mixto: willard draft, willard liquidada, willard anulada,
        # compra draft, compra revisada, compra liquidada, compra anulada
        w_draft = _willard(client, org_headers, wh_cv, willard_holder, mat_bat)
        w_liq = _willard(client, org_headers, wh_cv, willard_holder, mat_bat)
        _confirm(client, org_headers, w_liq["id"])
        w_ann = _willard(client, org_headers, wh_cv, willard_holder, mat_bat)
        client.post(f"{INBOUND_URL}/{w_ann['id']}/annul", headers=org_headers,
                    json={"reason": "c"})
        p_draft = _purchase_order(client, org_headers, wh_cv, mat_compra)
        p_rev = _purchase_order(client, org_headers, wh_cv, mat_compra)
        _review(client, org_headers, p_rev["id"])
        p_liq = _purchase_order(client, org_headers, wh_cv, mat_compra)
        _review(client, org_headers, p_liq["id"])
        _liquidate_order(client, org_headers, p_liq, mat_compra, supplier)
        p_ann = _purchase_order(client, org_headers, wh_cv, mat_compra)
        _review(client, org_headers, p_ann["id"])
        _liquidate_order(client, org_headers, p_ann, mat_compra, supplier)
        client.post(f"{INBOUND_URL}/{p_ann['id']}/annul", headers=org_headers,
                    json={"reason": "c"})

        all_items = _listing(client, org_headers, limit=100)["items"]
        by_field = {
            ds: {i["id"] for i in all_items if i["display_status"] == ds}
            for ds in ("registered", "reviewed", "liquidated", "annulled")
        }
        expected = {
            "registered": {w_draft["id"], p_draft["id"]},
            "reviewed": {p_rev["id"]},
            "liquidated": {w_liq["id"], p_liq["id"]},
            "annulled": {w_ann["id"], p_ann["id"]},
        }
        for ds, ids in expected.items():
            assert by_field[ds] == ids, f"campo {ds}: {by_field[ds]} != {ids}"
            filtered = _listing(client, org_headers, display_status=ds, limit=100)
            filtered_ids = {i["id"] for i in filtered["items"]}
            assert filtered_ids == ids, f"filtro {ds}: {filtered_ids} != {ids}"
            assert filtered["total"] == len(ids)


# ---------------------------------------------------------------------------
# C-2 — buscador
# ---------------------------------------------------------------------------

class TestSearch:
    def test_search_by_plate_driver_material_tp_number(
        self, client, org_headers, wh_cv, supplier, mat_compra,
    ):
        """#93: el tercero ya no vive en la cabecera — el buscador lo alcanza
        via las ASIGNACIONES del reparto (EXISTS, R2)."""
        drv = client.post(DRIVERS_URL, headers=org_headers,
                          json={"name": "Anibal Buscable"}).json()
        veh = client.post(VEHICLES_URL, headers=org_headers,
                          json={"plate": "XYZ-987"}).json()
        body = _inbound(
            client, org_headers, inbound_type="purchase", warehouse_id=wh_cv.id,
            lines=[{"material_id": str(mat_compra.id), "quantity": "50"}],
            driver_id=drv["id"], vehicle_id=veh["id"],
        )
        _review(client, org_headers, body["id"])
        _liquidate_order(client, org_headers, body, mat_compra, supplier, qty="50", price="700")
        # Ruido: otra orden sin esos atributos
        _purchase_order(client, org_headers, wh_cv, mat_compra)

        for term in ("XYZ-987", "xyz", "Anibal", "CHATARRA-C", "Willard Ciclo C",
                     str(body["order_number"])):
            hits = _listing(client, org_headers, search=term, limit=100)["items"]
            assert any(i["id"] == body["id"] for i in hits), f"'{term}' no encontro la orden"

        misses = _listing(client, org_headers, search="NO-EXISTE-QQQ", limit=100)
        assert misses["total"] == 0


# ---------------------------------------------------------------------------
# C-3 — FIFO
# ---------------------------------------------------------------------------

class TestSort:
    def test_sort_oldest_fifo(
        self, client, org_headers, wh_cv, willard_holder, supplier, mat_bat, kg_bat_cv,
    ):
        first = _willard(client, org_headers, wh_cv, willard_holder, mat_bat)
        second = _willard(client, org_headers, wh_cv, willard_holder, mat_bat)
        newest = _listing(client, org_headers)["items"]
        assert newest[0]["id"] == second["id"]  # default: mas nueva primero
        oldest = _listing(client, org_headers, sort="oldest")["items"]
        assert oldest[0]["id"] == first["id"]  # FIFO: la mas vieja arriba

    def test_sort_invalid_422(self, client, org_headers):
        resp = client.get(INBOUND_URL, headers=org_headers, params={"sort": "x"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# C-4 — mundo willard en response
# ---------------------------------------------------------------------------

class TestWillardWorld:
    def test_worlds_and_purchase_null(
        self, client, org_headers, wh_cv, willard_holder, supplier, mat_bat, mat_dross,
        mat_compra, kg_bat_cv, kg_dross_account,
    ):
        w_bat = _willard(client, org_headers, wh_cv, willard_holder, mat_bat)
        w_dross = _willard(client, org_headers, wh_cv, willard_holder, mat_dross, qty="100")
        p = _purchase_order(client, org_headers, wh_cv, mat_compra)

        assert w_bat["willard_world"] == "postconsumo"
        assert w_dross["willard_world"] == "drosses"
        assert p["willard_world"] is None

        by_id = {i["id"]: i for i in _listing(client, org_headers, limit=100)["items"]}
        assert by_id[w_bat["id"]]["willard_world"] == "postconsumo"
        assert by_id[w_dross["id"]]["willard_world"] == "drosses"
        assert by_id[p["id"]]["willard_world"] is None


# ---------------------------------------------------------------------------
# C-5 — quien hizo que
# ---------------------------------------------------------------------------

class TestAuditNames:
    def test_created_and_liquidated_willard(
        self, client, org_headers, test_user, wh_cv, willard_holder, supplier, mat_bat, kg_bat_cv,
    ):
        expected_name = test_user.full_name or test_user.email
        body = _willard(client, org_headers, wh_cv, willard_holder, mat_bat)
        assert body["created_by_name"] == expected_name
        assert body["liquidated_by_name"] is None  # draft: nadie ha liquidado
        assert body["liquidated_at"] is None

        out = _confirm(client, org_headers, body["id"])
        assert out["liquidated_by_name"] == expected_name  # kg mov created_by
        assert out["liquidated_at"] is not None

    def test_liquidated_purchase_and_annulled(
        self, client, org_headers, test_user, wh_cv, supplier, mat_compra,
    ):
        expected_name = test_user.full_name or test_user.email
        body = _purchase_order(client, org_headers, wh_cv, mat_compra)
        assert body["created_by_name"] == expected_name
        assert body["liquidated_by_name"] is None

        _review(client, org_headers, body["id"])
        _liquidate_order(client, org_headers, body, mat_compra, supplier)
        out = _detail(client, org_headers, body["id"])
        assert out["liquidated_by_name"] == expected_name  # Purchase.liquidated_by
        assert out["liquidated_at"] is not None
        # #93: la revision tambien queda auditada
        assert out["reviewed_by_name"] == expected_name

        other = _purchase_order(client, org_headers, wh_cv, mat_compra)
        ann = client.post(
            f"{INBOUND_URL}/{other['id']}/annul", headers=org_headers,
            json={"reason": "c"},
        ).json()
        assert ann["annulled_by_name"] == expected_name


# ---------------------------------------------------------------------------
# Filtros mundo willard + sede (addendum pruebas Daniel)
# ---------------------------------------------------------------------------

class TestWorldAndWarehouseFilters:
    def test_filter_by_willard_world(
        self, client, org_headers, wh_cv, willard_holder, supplier, mat_bat, mat_dross,
        kg_bat_cv, kg_dross_account,
    ):
        w_bat = _willard(client, org_headers, wh_cv, willard_holder, mat_bat)
        w_dross = _willard(client, org_headers, wh_cv, willard_holder, mat_dross, qty="100")

        post = _listing(client, org_headers, willard_world="postconsumo", limit=100)
        assert {i["id"] for i in post["items"]} == {w_bat["id"]}
        dross = _listing(client, org_headers, willard_world="drosses", limit=100)
        assert {i["id"] for i in dross["items"]} == {w_dross["id"]}

    def test_world_filter_excludes_both_channels_purchase(
        self, client, org_headers, db_session, test_organization, wh_cv, willard_holder, supplier,
        kg_bat_cv,
    ):
        """Q-04: un material 'ambos canales' (world=postconsumo Y compra_regular)
        comprado por canal regular NO aparece al filtrar por mundo — el filtro
        es de entradas Willard, no de materiales."""
        mat = _mat(db_session, test_organization.id, "BAT-AMBOS-C", unit="unidad")
        _post_formula(client, org_headers, mat.id, "battery_to_lead", {"kg_lead_per_unit": 2.5})
        _set_profile(client, org_headers, mat.id, compra_regular=True, willard_world="postconsumo")
        p = _purchase_order(client, org_headers, wh_cv, mat, qty="10")
        w = _willard(client, org_headers, wh_cv, willard_holder, mat)

        out = _listing(client, org_headers, willard_world="postconsumo", limit=100)
        ids = {i["id"] for i in out["items"]}
        assert w["id"] in ids
        assert p["id"] not in ids

    def test_filter_by_warehouse(
        self, client, org_headers, db_session, test_organization, wh_cv, supplier,
        mat_compra,
    ):
        wh_jm = create_warehouse(db_session, test_organization.id, "Juan Mina C")
        db_session.commit()
        p_cv = _purchase_order(client, org_headers, wh_cv, mat_compra)
        p_jm = _inbound(
            client, org_headers, inbound_type="purchase", warehouse_id=wh_jm.id,
            lines=[{"material_id": str(mat_compra.id), "quantity": "20"}],
        )
        out = _listing(client, org_headers, warehouse_id=str(wh_jm.id), limit=100)
        ids = {i["id"] for i in out["items"]}
        assert p_jm["id"] in ids and p_cv["id"] not in ids

    def test_world_invalid_422(self, client, org_headers):
        resp = client.get(INBOUND_URL, headers=org_headers,
                          params={"willard_world": "none"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Multi-tenancy + params en org ajena
# ---------------------------------------------------------------------------

class TestTenancyAndGating:
    def test_new_params_do_not_leak_across_orgs(
        self, client, org_headers, org_headers2, wh_cv, supplier, mat_compra,
    ):
        """Los joins nuevos (search/display_status) conservan el filtro de org:
        org2 (viewer, flag on) no ve las ordenes de org1."""
        _purchase_order(client, org_headers, wh_cv, mat_compra)
        for params in (
            {"display_status": "registered"},
            {"search": "CHATARRA-C"},
            {"sort": "oldest"},
        ):
            out = _listing(client, org_headers2, **params)
            assert out["total"] == 0, params

    def test_display_status_invalid_422(self, client, org_headers):
        resp = client.get(INBOUND_URL, headers=org_headers,
                          params={"display_status": "draft"})
        assert resp.status_code == 422
