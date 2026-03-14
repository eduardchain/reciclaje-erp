"""Tests para cambio de contraseña."""
import pytest
from app.core.security import verify_password


class TestChangePassword:
    """POST /auth/change-password"""

    def test_change_password_success(self, client, auth_headers, test_user, db_session):
        response = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "testpassword123", "new_password": "nuevapass"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert "actualizada" in response.json()["message"].lower()

        # Verificar que puede loguearse con la nueva contraseña
        login_response = client.post(
            "/api/v1/auth/login/json",
            json={"email": "testuser@example.com", "password": "nuevapass"},
        )
        assert login_response.status_code == 200
        assert "access_token" in login_response.json()

    def test_change_password_wrong_current(self, client, auth_headers, test_user):
        response = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "incorrecta", "new_password": "nuevapass"},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "incorrecta" in response.json()["detail"].lower()
