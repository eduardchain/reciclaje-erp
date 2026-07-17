"""
Tests endpoints de entidades de retencion (paquete UX addendum §8).

Cubre: GET lista estructurada (tipos parseados + municipio + balance, orden
canonico, entidades ajenas al formato excluidas), POST ICA idempotente con
matching H4 ('bogota' == 'Bogotá' → misma entidad), POST retefuente → 422
(solo ica es creable a mano), flag gating (403 sin kg_ledger_enabled incluso
admin), RBAC (viewer lee, no crea) y aislamiento multi-org.

El get-or-create compartido con la liquidacion (F3) lo guardan los 16 tests
de tests/test_purchase_retentions.py — aca solo se prueba la capa endpoint.
"""
import pytest

from app.services.retention_entities import resolve_retention_entity
from tests.conftest import create_third_party_with_category

URL = "/api/v1/third-parties/retention-entities"


@pytest.fixture(autouse=True)
def _enable_flag(db_session, test_organization, test_organization2):
    for org in (test_organization, test_organization2):
        org.settings = {"kg_ledger_enabled": True}
    db_session.commit()


class TestRetentionEntities:
    def test_list_structured_and_ordered(
        self, client, org_headers, db_session, test_organization
    ):
        """GET parsea el formato canonico: tipo + municipio + balance, orden
        retefuente → reteiva → ica por municipio. Entidades sistema de OTRO
        formato ([Prepago]) y terceros normales NO aparecen."""
        org_id = test_organization.id
        # Seed via servicio compartido (mismo camino que la liquidacion)
        resolve_retention_entity(db_session, org_id, "ica", "Soledad")
        resolve_retention_entity(db_session, org_id, "retefuente", None)
        resolve_retention_entity(db_session, org_id, "ica", "Barranquilla")
        # Ruido: system entity de otro modulo + tercero normal
        from app.models.third_party import ThirdParty
        db_session.add(ThirdParty(
            name="[Prepago] Seguro Todo Riesgo", organization_id=org_id,
            is_system_entity=True, is_active=True,
        ))
        create_third_party_with_category(
            db_session, org_id, "Proveedor Normal", "material_supplier"
        )
        db_session.commit()

        resp = client.get(URL, headers=org_headers)
        assert resp.status_code == 200, resp.text
        rows = resp.json()
        assert [(r["retention_type"], r["municipality"]) for r in rows] == [
            ("retefuente", None),
            ("ica", "Barranquilla"),
            ("ica", "Soledad"),
        ]
        assert all(r["current_balance"] == 0.0 for r in rows)
        assert all(r["is_active"] for r in rows)
        assert rows[0]["name"] == "[Retenciones] ReteFuente"
        assert rows[1]["name"] == "[Retenciones] ICA Barranquilla"

    def test_post_ica_idempotent_h4(self, client, org_headers):
        """POST ICA crea; repetir sin acentos/casing devuelve la MISMA entidad
        (matching H4) y conserva el display bonito de la primera vez."""
        r1 = client.post(URL, headers=org_headers, json={
            "retention_type": "ica", "municipality": "Bogotá",
        })
        assert r1.status_code == 201, r1.text
        assert r1.json()["name"] == "[Retenciones] ICA Bogotá"
        assert r1.json()["municipality"] == "Bogotá"

        r2 = client.post(URL, headers=org_headers, json={
            "retention_type": "ica", "municipality": "bogota",
        })
        assert r2.status_code == 201, r2.text
        assert r2.json()["id"] == r1.json()["id"]
        assert r2.json()["municipality"] == "Bogotá"  # display original, no el input

        rows = client.get(URL, headers=org_headers).json()
        assert len([r for r in rows if r["retention_type"] == "ica"]) == 1

    def test_post_non_ica_422(self, client, org_headers):
        """Solo ICA es creable a mano — ReteFuente/ReteIVA nacen al liquidar."""
        for rtype in ("retefuente", "reteiva", "otra"):
            resp = client.post(URL, headers=org_headers, json={
                "retention_type": rtype, "municipality": "Barranquilla",
            })
            assert resp.status_code == 422, f"{rtype}: {resp.text}"

    def test_post_blank_municipality_422(self, client, org_headers):
        resp = client.post(URL, headers=org_headers, json={
            "retention_type": "ica", "municipality": "",
        })
        assert resp.status_code == 422

    def test_flag_off_403(self, client, org_headers, db_session, test_organization):
        """Sin kg_ledger_enabled ambos endpoints responden 403 incluso a admin —
        las 3 orgs prod no ven el modulo (regresion Costa)."""
        test_organization.settings = {}
        db_session.commit()
        assert client.get(URL, headers=org_headers).status_code == 403
        resp = client.post(URL, headers=org_headers, json={
            "retention_type": "ica", "municipality": "Cali",
        })
        assert resp.status_code == 403

    def test_rbac_viewer_read_not_create(self, client, org_headers2):
        """third_parties.view lee el grupo (F1); third_parties.create crea —
        viewer no lo tiene."""
        assert client.get(URL, headers=org_headers2).status_code == 200
        resp = client.post(URL, headers=org_headers2, json={
            "retention_type": "ica", "municipality": "Monteria",
        })
        assert resp.status_code == 403

    def test_org_isolation(
        self, client, org_headers, org_headers2, db_session, test_organization
    ):
        """Entidades de org1 no se filtran al GET de org2."""
        resolve_retention_entity(db_session, test_organization.id, "ica", "Envigado")
        db_session.commit()
        assert len(client.get(URL, headers=org_headers).json()) == 1
        assert client.get(URL, headers=org_headers2).json() == []
