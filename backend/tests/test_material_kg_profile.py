"""
Tests MaterialKgProfile — clasificacion Willard del material (SAC, CC-005).

Cubre: upsert 1:1 (crea/actualiza), worlds single-valued (postconsumo XOR
drosses via CHECK/Literal), compra_regular ortogonal, filtros de listado,
aislamiento (flag-gated: 403 sin kg_ledger_enabled, incluso admin) y RBAC
(materials.view lectura, materials.edit escritura).
"""
import pytest
from datetime import datetime, timezone

from tests.integration_helpers import create_material, create_material_category

PROFILES_URL = "/api/v1/material-kg-profiles"


@pytest.fixture(autouse=True)
def _enable_flag(db_session, test_organization, test_organization2):
    for org in (test_organization, test_organization2):
        org.settings = {"kg_ledger_enabled": True}
    db_session.commit()


def _mat(db, org_id, code, unit="kg"):
    cat = create_material_category(db, org_id, f"Cat {code}")
    mat = create_material(db, org_id, code, f"Material {code}", cat.id)
    mat.default_unit = unit
    db.commit()
    return mat


def _put(client, headers, material_id, **body):
    return client.put(f"{PROFILES_URL}/{material_id}", headers=headers, json=body)


class TestMaterialKgProfile:
    def test_upsert_creates_then_updates(
        self, client, org_headers, db_session, test_organization
    ):
        mat = _mat(db_session, test_organization.id, "BAT-1", unit="unidad")
        # Crea
        resp = _put(client, org_headers, mat.id, compra_regular=True, willard_world="postconsumo")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["compra_regular"] is True
        assert data["willard_world"] == "postconsumo"
        assert data["material_code"] == "BAT-1"
        assert data["material_unit"] == "unidad"

        # Actualiza (1:1 — misma fila, no crea otra)
        resp = _put(client, org_headers, mat.id, compra_regular=False, willard_world="none")
        assert resp.status_code == 200, resp.text
        assert resp.json()["willard_world"] == "none"

        listing = client.get(PROFILES_URL, headers=org_headers).json()
        assert listing["total"] == 1  # una sola fila (upsert, no duplica)

    def test_worlds_orthogonal_to_compra_regular(
        self, client, org_headers, db_session, test_organization
    ):
        """Una bateria es (compra_regular?, world=postconsumo); un dross es
        (world=drosses). El mundo es single-valued (postconsumo XOR drosses)."""
        bat = _mat(db_session, test_organization.id, "BAT-2", unit="unidad")
        dross = _mat(db_session, test_organization.id, "DROSS-2", unit="kg")
        _put(client, org_headers, bat.id, compra_regular=False, willard_world="postconsumo")
        _put(client, org_headers, dross.id, compra_regular=False, willard_world="drosses")

        by_world = client.get(
            PROFILES_URL, headers=org_headers, params={"willard_world": "postconsumo"}
        ).json()
        assert {i["material_code"] for i in by_world["items"]} == {"BAT-2"}
        by_world = client.get(
            PROFILES_URL, headers=org_headers, params={"willard_world": "drosses"}
        ).json()
        assert {i["material_code"] for i in by_world["items"]} == {"DROSS-2"}

    def test_filter_by_compra_regular(
        self, client, org_headers, db_session, test_organization
    ):
        a = _mat(db_session, test_organization.id, "CR-A", unit="kg")
        b = _mat(db_session, test_organization.id, "CR-B", unit="kg")
        _put(client, org_headers, a.id, compra_regular=True, willard_world="none")
        _put(client, org_headers, b.id, compra_regular=False, willard_world="drosses")
        only_cr = client.get(
            PROFILES_URL, headers=org_headers, params={"compra_regular": True}
        ).json()
        assert {i["material_code"] for i in only_cr["items"]} == {"CR-A"}

    def test_invalid_world_422(self, client, org_headers, db_session, test_organization):
        mat = _mat(db_session, test_organization.id, "BAD-W", unit="kg")
        resp = _put(client, org_headers, mat.id, compra_regular=False, willard_world="chatarra")
        assert resp.status_code == 422

    def test_get_404_when_no_profile(
        self, client, org_headers, db_session, test_organization
    ):
        mat = _mat(db_session, test_organization.id, "NOPROF", unit="kg")
        resp = client.get(f"{PROFILES_URL}/{mat.id}", headers=org_headers)
        assert resp.status_code == 404

    def test_material_other_org_404(
        self, client, org_headers, db_session, test_organization2
    ):
        mat_org2 = _mat(db_session, test_organization2.id, "AJENO", unit="kg")
        resp = _put(client, org_headers, mat_org2.id, willard_world="drosses")
        assert resp.status_code == 404

    def test_isolation_flag_off_403(
        self, client, org_headers, db_session, test_organization
    ):
        """Aislamiento: sin kg_ledger_enabled el router responde 403 incluso a
        admin — el maestro compartido de las 3 orgs prod no ve la clasificacion."""
        mat = _mat(db_session, test_organization.id, "ISO", unit="kg")
        test_organization.settings = {}
        db_session.commit()
        resp = client.get(PROFILES_URL, headers=org_headers)
        assert resp.status_code == 403
        resp = _put(client, org_headers, mat.id, willard_world="drosses")
        assert resp.status_code == 403

    def test_rbac_viewer_read_not_write(
        self, client, org_headers2, db_session, test_organization2
    ):
        """materials.view lee, materials.edit escribe (viewer no tiene edit)."""
        mat = _mat(db_session, test_organization2.id, "RBAC", unit="kg")
        assert client.get(PROFILES_URL, headers=org_headers2).status_code == 200
        resp = _put(client, org_headers2, mat.id, willard_world="drosses")
        assert resp.status_code == 403
