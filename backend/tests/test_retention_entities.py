"""
Tests retenciones: catálogo configurable v2 (CC-006) + GET unificado.

Cubre: CRUD de configs (crear los 3 tipos, concept F3, dup H4 → 409 con
config_id, validaciones municipio/rate → 422, PATCH rate, soft delete y
reactivación con colisión), GET unificado D-v2-1 (config+entidad matcheadas,
config sin entidad = visible con saldo 0, entidad huérfana sin config),
flag gating (403 sin kg_ledger_enabled incluso admin), RBAC (viewer lee,
no crea) y aislamiento multi-org.

El get-or-create compartido con la liquidación (F3 del addendum) lo guardan
los 16 tests de tests/test_purchase_retentions.py — acá solo la capa catálogo.
"""
import pytest

from app.services.retention_entities import resolve_retention_entity
from tests.conftest import create_third_party_with_category

ROWS_URL = "/api/v1/third-parties/retention-entities"
CONFIGS_URL = "/api/v1/third-parties/retention-configs"


@pytest.fixture(autouse=True)
def _enable_flag(db_session, test_organization, test_organization2):
    for org in (test_organization, test_organization2):
        org.settings = {"kg_ledger_enabled": True}
    db_session.commit()


def _post_config(client, headers, **body):
    return client.post(CONFIGS_URL, headers=headers, json=body)


class TestRetentionConfigs:
    def test_create_all_types_and_concept(self, client, org_headers):
        r1 = _post_config(client, org_headers, retention_type="retefuente", rate_pct=2.5)
        assert r1.status_code == 201, r1.text
        assert r1.json()["rate_pct"] == 2.5
        assert r1.json()["entity_id"] is None  # config sin uso aún
        assert r1.json()["current_balance"] == 0.0

        r2 = _post_config(
            client, org_headers, retention_type="retefuente",
            concept="Servicios", rate_pct=4,
        )
        assert r2.status_code == 201, r2.text  # F3: mismo tipo, concepto distinto
        assert r2.json()["concept"] == "Servicios"

        r3 = _post_config(
            client, org_headers, retention_type="ica",
            municipality="Barranquilla", rate_pct=0.7,
        )
        assert r3.status_code == 201, r3.text
        assert r3.json()["municipality"] == "Barranquilla"

    def test_duplicate_h4_409_with_config_id(self, client, org_headers):
        r1 = _post_config(
            client, org_headers, retention_type="ica",
            municipality="Bogotá", rate_pct=1,
        )
        assert r1.status_code == 201
        # Mismo municipio sin tilde/casing → colisión H4, aunque el % sea otro
        r2 = _post_config(
            client, org_headers, retention_type="ica",
            municipality="bogota", rate_pct=2,
        )
        assert r2.status_code == 409, r2.text
        assert r1.json()["config_id"] in r2.json()["detail"]  # QA: detail trae el id

    def test_validation_422(self, client, org_headers):
        # ica sin municipio
        assert _post_config(
            client, org_headers, retention_type="ica", rate_pct=1
        ).status_code == 422
        # municipio en tipo no-ica
        assert _post_config(
            client, org_headers, retention_type="reteiva",
            municipality="Cali", rate_pct=1,
        ).status_code == 422
        # rate fuera de rango
        for bad_rate in (0, -1, 101):
            assert _post_config(
                client, org_headers, retention_type="retefuente", rate_pct=bad_rate
            ).status_code == 422, f"rate {bad_rate}"

    def test_patch_rate_and_soft_delete(self, client, org_headers):
        created = _post_config(
            client, org_headers, retention_type="reteiva", rate_pct=15
        ).json()
        cid = created["config_id"]

        resp = client.patch(f"{CONFIGS_URL}/{cid}", headers=org_headers, json={"rate_pct": 19})
        assert resp.status_code == 200, resp.text
        assert resp.json()["rate_pct"] == 19.0

        resp = client.patch(f"{CONFIGS_URL}/{cid}", headers=org_headers, json={"is_active": False})
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

        # Desactivada libera el slot: crear otra reteiva pasa
        r2 = _post_config(client, org_headers, retention_type="reteiva", rate_pct=5)
        assert r2.status_code == 201
        # Reactivar la vieja ahora colisiona con la nueva → 409
        resp = client.patch(f"{CONFIGS_URL}/{cid}", headers=org_headers, json={"is_active": True})
        assert resp.status_code == 409, resp.text

    def test_patch_other_org_404(self, client, org_headers, org_headers2):
        created = _post_config(
            client, org_headers, retention_type="retefuente", rate_pct=2.5
        ).json()
        resp = client.patch(
            f"{CONFIGS_URL}/{created['config_id']}",
            headers=org_headers2, json={"rate_pct": 9},
        )
        assert resp.status_code in (403, 404)  # viewer sin create → 403; admin ajeno → 404


class TestUnifiedRows:
    def test_config_matches_entity_and_orphans(
        self, client, org_headers, db_session, test_organization
    ):
        """Los 3 sabores de fila: config+entidad, config sola, entidad sola."""
        org_id = test_organization.id
        # Entidad nacida "al liquidar" (servicio compartido) para ICA Soledad
        resolve_retention_entity(db_session, org_id, "ica", "Soledad")
        # Entidad huérfana (sin config): ReteIVA
        resolve_retention_entity(db_session, org_id, "reteiva", None)
        db_session.commit()

        # Config que matchea la entidad (H4: sin tilde) + config sin entidad
        _post_config(client, org_headers, retention_type="ica",
                     municipality="soledad", rate_pct=0.5)
        _post_config(client, org_headers, retention_type="retefuente", rate_pct=2.5)

        rows = client.get(ROWS_URL, headers=org_headers).json()
        by_key = {(r["retention_type"], r["municipality"]): r for r in rows}

        matched = by_key[("ica", "soledad")]  # display de la config
        assert matched["config_id"] is not None
        assert matched["entity_id"] is not None  # matcheó la entidad "Soledad"
        assert matched["name"] == "[Retenciones] ICA Soledad"
        assert matched["rate_pct"] == 0.5

        config_only = by_key[("retefuente", None)]
        assert config_only["config_id"] is not None
        assert config_only["entity_id"] is None
        assert config_only["current_balance"] == 0.0

        orphan = by_key[("reteiva", None)]
        assert orphan["config_id"] is None
        assert orphan["entity_id"] is not None
        assert orphan["rate_pct"] is None

    def test_excludes_non_retention_entities(
        self, client, org_headers, db_session, test_organization
    ):
        from app.models.third_party import ThirdParty
        db_session.add(ThirdParty(
            name="[Prepago] Seguro", organization_id=test_organization.id,
            is_system_entity=True, is_active=True,
        ))
        create_third_party_with_category(
            db_session, test_organization.id, "Proveedor Normal", "material_supplier"
        )
        db_session.commit()
        assert client.get(ROWS_URL, headers=org_headers).json() == []

    def test_org_isolation(self, client, org_headers, org_headers2):
        _post_config(client, org_headers, retention_type="retefuente", rate_pct=2.5)
        assert len(client.get(ROWS_URL, headers=org_headers).json()) == 1
        assert client.get(ROWS_URL, headers=org_headers2).json() == []


class TestGatingAndRBAC:
    def test_flag_off_403(self, client, org_headers, db_session, test_organization):
        test_organization.settings = {}
        db_session.commit()
        assert client.get(ROWS_URL, headers=org_headers).status_code == 403
        assert _post_config(
            client, org_headers, retention_type="retefuente", rate_pct=2.5
        ).status_code == 403
        assert client.patch(
            f"{CONFIGS_URL}/00000000-0000-0000-0000-000000000000",
            headers=org_headers, json={"rate_pct": 1},
        ).status_code == 403

    def test_rbac_viewer_read_not_create(self, client, org_headers2):
        assert client.get(ROWS_URL, headers=org_headers2).status_code == 200
        resp = _post_config(
            client, org_headers2, retention_type="retefuente", rate_pct=2.5
        )
        assert resp.status_code == 403
