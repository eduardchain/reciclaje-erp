"""Tests del reseteo de contrasena por superusuario.

Plan: docs/planes/plan-reseteo-password-superusuario.md (micro-QA GO).
Cubre efecto real (incluido login end-to-end), validaciones, los 3 edge
cases (404 / objetivo superusuario / usuario inactivo), RBAC en ambos
sentidos, y no-fuga del secreto en response y en logs (D1 + H3).
"""
import logging

import pytest

from app.core.security import get_password_hash, create_access_token, verify_password
from app.models.user import User

NEW_PASSWORD = "claveNueva456"
OLD_PASSWORD = "claveVieja123"


# ---- Fixtures ----

@pytest.fixture
def superuser(db_session):
    user = User(
        email="superadmin.reset@example.com",
        hashed_password=get_password_hash("superpass"),
        full_name="Super Admin",
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def su_headers(superuser):
    token = create_access_token(data={"sub": str(superuser.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def target_user(db_session):
    """Usuario comun que olvido su clave."""
    user = User(
        email="olvidadizo@example.com",
        hashed_password=get_password_hash(OLD_PASSWORD),
        full_name="Usuario Olvidadizo",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _reset_url(user_id) -> str:
    return f"/api/v1/system/users/{user_id}/reset-password"


# ---- Caso feliz y efecto real ----

class TestPasswordResetHappyPath:

    def test_reset_sets_new_password(self, client, db_session, su_headers, target_user):
        """El hash nuevo verifica contra la clave nueva."""
        r = client.post(
            _reset_url(target_user.id),
            json={"new_password": NEW_PASSWORD},
            headers=su_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["email"] == target_user.email

        db_session.expire_all()
        refreshed = db_session.query(User).filter(User.id == target_user.id).first()
        assert verify_password(NEW_PASSWORD, refreshed.hashed_password)

    def test_old_password_stops_working(self, client, db_session, su_headers, target_user):
        client.post(
            _reset_url(target_user.id),
            json={"new_password": NEW_PASSWORD},
            headers=su_headers,
        )
        db_session.expire_all()
        refreshed = db_session.query(User).filter(User.id == target_user.id).first()
        assert not verify_password(OLD_PASSWORD, refreshed.hashed_password)

    def test_login_end_to_end_with_new_password(self, client, su_headers, target_user):
        """El usuario entra de verdad con la clave nueva (y ya no con la vieja)."""
        client.post(
            _reset_url(target_user.id),
            json={"new_password": NEW_PASSWORD},
            headers=su_headers,
        )

        ok = client.post(
            "/api/v1/auth/login/json",
            json={"email": target_user.email, "password": NEW_PASSWORD},
        )
        assert ok.status_code == 200, ok.text
        assert ok.json()["access_token"]

        denied = client.post(
            "/api/v1/auth/login/json",
            json={"email": target_user.email, "password": OLD_PASSWORD},
        )
        assert denied.status_code == 401


# ---- Validaciones ----

class TestPasswordResetValidation:

    def test_password_too_short_422(self, client, su_headers, target_user):
        r = client.post(
            _reset_url(target_user.id),
            json={"new_password": "12345"},  # 5 < min_length=6
            headers=su_headers,
        )
        assert r.status_code == 422

    def test_missing_field_422(self, client, su_headers, target_user):
        r = client.post(_reset_url(target_user.id), json={}, headers=su_headers)
        assert r.status_code == 422


# ---- Edge cases ----

class TestPasswordResetEdgeCases:

    def test_unknown_user_404(self, client, su_headers):
        from uuid import uuid4
        r = client.post(
            _reset_url(uuid4()),
            json={"new_password": NEW_PASSWORD},
            headers=su_headers,
        )
        assert r.status_code == 404

    def test_target_superuser_forbidden(self, client, db_session, su_headers):
        """D2: superusuario -> superusuario es toma de cuenta lateral."""
        other_su = User(
            email="otro.super@example.com",
            hashed_password=get_password_hash(OLD_PASSWORD),
            full_name="Otro Super",
            is_active=True,
            is_superuser=True,
        )
        db_session.add(other_su)
        db_session.commit()
        db_session.refresh(other_su)
        hash_before = other_su.hashed_password

        r = client.post(
            _reset_url(other_su.id),
            json={"new_password": NEW_PASSWORD},
            headers=su_headers,
        )
        assert r.status_code == 403

        db_session.expire_all()
        refreshed = db_session.query(User).filter(User.id == other_su.id).first()
        assert refreshed.hashed_password == hash_before  # intacto

    def test_inactive_user_reset_but_still_locked_out(
        self, client, db_session, su_headers
    ):
        """D3: se puede resetear, pero el reset NO reactiva."""
        inactive = User(
            email="inactivo@example.com",
            hashed_password=get_password_hash(OLD_PASSWORD),
            full_name="Usuario Inactivo",
            is_active=False,
            is_superuser=False,
        )
        db_session.add(inactive)
        db_session.commit()
        db_session.refresh(inactive)

        r = client.post(
            _reset_url(inactive.id),
            json={"new_password": NEW_PASSWORD},
            headers=su_headers,
        )
        assert r.status_code == 200
        assert r.json()["is_active"] is False

        # sigue sin poder entrar pese a la clave nueva
        denied = client.post(
            "/api/v1/auth/login/json",
            json={"email": inactive.email, "password": NEW_PASSWORD},
        )
        assert denied.status_code in (400, 401, 403)


# ---- RBAC ----

class TestPasswordResetRBAC:

    def test_org_admin_forbidden(self, client, auth_headers, target_user):
        """Un admin de organizacion NO es superusuario."""
        r = client.post(
            _reset_url(target_user.id),
            json={"new_password": NEW_PASSWORD},
            headers=auth_headers,
        )
        assert r.status_code == 403

    def test_unauthenticated_401(self, client, target_user):
        r = client.post(
            _reset_url(target_user.id), json={"new_password": NEW_PASSWORD}
        )
        assert r.status_code in (401, 403)


# ---- No-fuga del secreto (D1 + H3 del micro-QA) ----

class TestPasswordResetNoLeak:

    def test_response_never_contains_secret(self, client, su_headers, target_user):
        r = client.post(
            _reset_url(target_user.id),
            json={"new_password": NEW_PASSWORD},
            headers=su_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert "password" not in body
        assert "hashed_password" not in body
        assert NEW_PASSWORD not in r.text

    def test_audit_log_has_actor_and_target_but_no_secret(
        self, client, su_headers, target_user, superuser, caplog
    ):
        """H3: el log de auditoria (D5) jamas debe incluir la clave.

        Es el punto exacto donde D1 se desharia sin querer: loggear el
        payload completo del request anularia todo el racional.
        """
        with caplog.at_level(logging.WARNING, logger="app.api.v1.endpoints.system"):
            r = client.post(
                _reset_url(target_user.id),
                json={"new_password": NEW_PASSWORD},
                headers=su_headers,
            )
        assert r.status_code == 200

        audit = [rec for rec in caplog.records if "password_reset" in rec.getMessage()]
        assert len(audit) == 1, "debe registrarse exactamente una linea de auditoria"

        message = audit[0].getMessage()
        assert str(superuser.id) in message      # actor
        assert superuser.email in message
        assert str(target_user.id) in message    # objetivo
        assert target_user.email in message
        assert NEW_PASSWORD not in message       # <-- el corazon de H3
        assert "new_password" not in message
