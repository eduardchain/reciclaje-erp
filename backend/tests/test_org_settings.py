"""
Tests de organization.settings (SAC E1, D3 del plan + condicion H1 del QA).

Cubre: escritura via system PATCH (superuser-only), semantica REPLACE,
round-trip completo de transfer_tolerance_pct por JSONB (H1 — un payload
solo-booleanos no atraparia la regresion de serializacion), validacion
estricta (claves desconocidas y tipos basura -> 422), y el helper
get_org_setting (NULL -> defaults, parcial -> mezcla).
"""
import pytest
from sqlalchemy import select

from app.core.security import get_password_hash, create_access_token
from app.models.organization import Organization
from app.models.user import User
from app.utils.org_settings import SETTING_DEFAULTS, get_org_setting

URL_SYSTEM = "/api/v1/system/organizations"

FULL_PAYLOAD = {
    "kg_ledger_enabled": True,
    "two_step_transfers_enabled": False,
    "internal_maquila_enabled": False,
    "transfer_tolerance_pct": 0.05,
    "intersede_stale_days": 30,
    "aging_buckets": [30, 60, 90],
}


@pytest.fixture
def su_headers(db_session):
    """Headers de superuser (patron test_system_endpoints)."""
    user = User(
        email="su-settings@example.com",
        hashed_password=get_password_hash("superpass"),
        full_name="Super Settings",
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    db_session.commit()
    token = create_access_token(data={"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


class TestOrgSettingsWrite:
    def test_system_patch_persists_and_org_get_returns(
        self, client, su_headers, org_headers, test_organization, db_session
    ):
        resp = client.patch(
            f"{URL_SYSTEM}/{test_organization.id}",
            headers=su_headers,
            json={"settings": FULL_PAYLOAD},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["settings"] == FULL_PAYLOAD

        # La org normal lo ve en su GET (OrganizationResponse.settings)
        resp = client.get(
            f"/api/v1/organizations/{test_organization.id}", headers=org_headers
        )
        assert resp.status_code == 200
        assert resp.json()["settings"] == FULL_PAYLOAD

    def test_transfer_tolerance_pct_roundtrip_jsonb(
        self, client, su_headers, test_organization, db_session
    ):
        """Condicion H1 del QA: el payload COMPLETO (incluye el float) debe
        persistir sin error y volver identico — atrapa la regresion de
        serializacion (Decimal en el payload -> TypeError -> 500) que un
        payload solo-booleanos no veria."""
        resp = client.patch(
            f"{URL_SYSTEM}/{test_organization.id}",
            headers=su_headers,
            json={"settings": FULL_PAYLOAD},
        )
        assert resp.status_code == 200, resp.text

        db_session.expire_all()
        value = get_org_setting(db_session, test_organization.id, "transfer_tolerance_pct")
        assert value == 0.05
        assert isinstance(value, float)

        org = db_session.execute(
            select(Organization).where(Organization.id == test_organization.id)
        ).scalar_one()
        assert org.settings["transfer_tolerance_pct"] == 0.05
        assert org.settings["aging_buckets"] == [30, 60, 90]

    def test_replace_semantics_subset_drops_rest(
        self, client, su_headers, test_organization, db_session
    ):
        """D3: el PATCH persiste exactamente las claves enviadas (REPLACE)."""
        client.patch(
            f"{URL_SYSTEM}/{test_organization.id}",
            headers=su_headers,
            json={"settings": FULL_PAYLOAD},
        )
        resp = client.patch(
            f"{URL_SYSTEM}/{test_organization.id}",
            headers=su_headers,
            json={"settings": {"kg_ledger_enabled": True}},
        )
        assert resp.status_code == 200
        assert resp.json()["settings"] == {"kg_ledger_enabled": True}

        db_session.expire_all()
        # Clave presente -> su valor; claves borradas -> default
        assert get_org_setting(db_session, test_organization.id, "kg_ledger_enabled") is True
        assert get_org_setting(
            db_session, test_organization.id, "transfer_tolerance_pct"
        ) == SETTING_DEFAULTS["transfer_tolerance_pct"]

    def test_org_patch_ignores_settings_silently(
        self, client, su_headers, org_headers, test_organization, db_session
    ):
        """El PATCH org normal NO acepta settings: Pydantic descarta extras —
        settings queda INALTERADO (no 422, plan §8)."""
        client.patch(
            f"{URL_SYSTEM}/{test_organization.id}",
            headers=su_headers,
            json={"settings": FULL_PAYLOAD},
        )
        resp = client.patch(
            f"/api/v1/organizations/{test_organization.id}",
            headers=org_headers,
            json={"name": "Test Organization Renamed", "settings": {"kg_ledger_enabled": False}},
        )
        assert resp.status_code == 200, resp.text

        db_session.expire_all()
        org = db_session.execute(
            select(Organization).where(Organization.id == test_organization.id)
        ).scalar_one()
        assert org.settings == FULL_PAYLOAD  # inalterado
        assert org.name == "Test Organization Renamed"

    def test_unknown_key_422(self, client, su_headers, test_organization):
        resp = client.patch(
            f"{URL_SYSTEM}/{test_organization.id}",
            headers=su_headers,
            json={"settings": {"kg_ledger_enable": True}},  # typo: clave desconocida
        )
        assert resp.status_code == 422

    def test_invalid_types_422(self, client, su_headers, test_organization):
        for bad in [
            {"kg_ledger_enabled": "yes"},   # strict: str no es bool
            {"aging_buckets": 30},           # int no es list[int]
            {"intersede_stale_days": "30"},  # strict: str no es int
            {"transfer_tolerance_pct": 1.5}, # fuera de rango le=1
        ]:
            resp = client.patch(
                f"{URL_SYSTEM}/{test_organization.id}",
                headers=su_headers,
                json={"settings": bad},
            )
            assert resp.status_code == 422, f"{bad} -> {resp.status_code}"

    def test_system_patch_requires_superuser(self, client, org_headers, test_organization):
        resp = client.patch(
            f"{URL_SYSTEM}/{test_organization.id}",
            headers=org_headers,  # admin de org, NO superuser
            json={"settings": {"kg_ledger_enabled": True}},
        )
        assert resp.status_code == 403


class TestGetOrgSetting:
    def test_null_settings_returns_all_defaults(self, db_session, test_organization):
        """Invariante 4: settings NULL == comportamiento actual (defaults)."""
        assert test_organization.settings is None
        for key, expected in SETTING_DEFAULTS.items():
            assert get_org_setting(db_session, test_organization.id, key) == expected

    def test_partial_settings_returns_mix(self, db_session, test_organization):
        test_organization.settings = {"kg_ledger_enabled": True}
        db_session.commit()

        assert get_org_setting(db_session, test_organization.id, "kg_ledger_enabled") is True
        assert get_org_setting(db_session, test_organization.id, "intersede_stale_days") == 30
        assert get_org_setting(db_session, test_organization.id, "aging_buckets") == [30, 60, 90]

    def test_null_value_falls_back_to_default(self, db_session, test_organization):
        test_organization.settings = {"transfer_tolerance_pct": None}
        db_session.commit()
        assert get_org_setting(
            db_session, test_organization.id, "transfer_tolerance_pct"
        ) == SETTING_DEFAULTS["transfer_tolerance_pct"]

    def test_unknown_key_raises(self, db_session, test_organization):
        with pytest.raises(KeyError):
            get_org_setting(db_session, test_organization.id, "no_existe")
