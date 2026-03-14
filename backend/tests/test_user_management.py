"""Tests para CRUD de usuarios y eliminacion de roles con reasignacion."""
import pytest
from sqlalchemy.orm import Session

from app.models.user import User, OrganizationMember
from app.models.organization import Organization
from app.models.role import Role
from app.core.security import get_password_hash, verify_password


def _get_role_id(db: Session, org_id, role_name: str):
    role = db.query(Role).filter(
        Role.organization_id == org_id,
        Role.name == role_name,
    ).first()
    return role.id if role else None


class TestCreateUserWithMembership:
    """POST /{org_id}/members/create-user"""

    def test_create_user_success(self, client, auth_headers, test_organization, db_session):
        viewer_role_id = _get_role_id(db_session, test_organization.id, "viewer")

        response = client.post(
            f"/api/v1/organizations/{test_organization.id}/members/create-user",
            json={
                "email": "nuevo@example.com",
                "full_name": "Usuario Nuevo",
                "role_id": str(viewer_role_id),
            },
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["user_email"] == "nuevo@example.com"
        assert data["user_full_name"] == "Usuario Nuevo"
        assert data["role_id"] == str(viewer_role_id)
        assert data["org_count"] == 1

    def test_created_user_can_login_with_default_password(
        self, client, auth_headers, test_organization, db_session
    ):
        viewer_role_id = _get_role_id(db_session, test_organization.id, "viewer")

        client.post(
            f"/api/v1/organizations/{test_organization.id}/members/create-user",
            json={
                "email": "logintest@example.com",
                "full_name": "Login Test",
                "role_id": str(viewer_role_id),
            },
            headers=auth_headers,
        )

        # Verificar que puede loguearse con 123456
        response = client.post(
            "/api/v1/auth/login/json",
            json={"email": "logintest@example.com", "password": "123456"},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_create_user_duplicate_email(self, client, auth_headers, test_organization, db_session):
        viewer_role_id = _get_role_id(db_session, test_organization.id, "viewer")

        # Crear primero
        client.post(
            f"/api/v1/organizations/{test_organization.id}/members/create-user",
            json={
                "email": "dup@example.com",
                "full_name": "Dup User",
                "role_id": str(viewer_role_id),
            },
            headers=auth_headers,
        )

        # Intentar duplicar
        response = client.post(
            f"/api/v1/organizations/{test_organization.id}/members/create-user",
            json={
                "email": "dup@example.com",
                "full_name": "Dup User 2",
                "role_id": str(viewer_role_id),
            },
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "email ya esta registrado" in response.json()["detail"].lower()

    def test_non_admin_cannot_create_user(
        self, client, auth_headers_user2, test_organization, test_user2, db_session
    ):
        # Agregar user2 como viewer
        viewer_role_id = _get_role_id(db_session, test_organization.id, "viewer")
        membership = OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role_id=viewer_role_id,
        )
        db_session.add(membership)
        db_session.commit()

        response = client.post(
            f"/api/v1/organizations/{test_organization.id}/members/create-user",
            json={
                "email": "blocked@example.com",
                "full_name": "Blocked",
                "role_id": str(viewer_role_id),
            },
            headers=auth_headers_user2,
        )

        assert response.status_code == 403


class TestResetPassword:
    """POST /{org_id}/members/{user_id}/reset-password"""

    def test_reset_password_success(
        self, client, auth_headers, test_organization, test_user2, db_session
    ):
        # Agregar user2 a la org
        viewer_role_id = _get_role_id(db_session, test_organization.id, "viewer")
        membership = OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role_id=viewer_role_id,
        )
        db_session.add(membership)
        db_session.commit()

        response = client.post(
            f"/api/v1/organizations/{test_organization.id}/members/{test_user2.id}/reset-password",
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert "reseteada" in response.json()["message"].lower()

        # Verificar que puede loguearse con 123456
        login_response = client.post(
            "/api/v1/auth/login/json",
            json={"email": "testuser2@example.com", "password": "123456"},
        )
        assert login_response.status_code == 200

    def test_reset_password_non_member(
        self, client, auth_headers, test_organization, test_user2
    ):
        # user2 NO es miembro de la org
        response = client.post(
            f"/api/v1/organizations/{test_organization.id}/members/{test_user2.id}/reset-password",
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_non_admin_cannot_reset(
        self, client, auth_headers_user2, test_organization, test_user, test_user2, db_session
    ):
        viewer_role_id = _get_role_id(db_session, test_organization.id, "viewer")
        membership = OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role_id=viewer_role_id,
        )
        db_session.add(membership)
        db_session.commit()

        response = client.post(
            f"/api/v1/organizations/{test_organization.id}/members/{test_user.id}/reset-password",
            headers=auth_headers_user2,
        )

        assert response.status_code == 403


class TestDeleteMember:
    """DELETE /{org_id}/members/{user_id}"""

    def test_delete_user_single_org(
        self, client, auth_headers, test_organization, test_user2, db_session
    ):
        """Usuario con 1 org -> hard delete."""
        viewer_role_id = _get_role_id(db_session, test_organization.id, "viewer")
        user2_id = test_user2.id  # Guardar ID antes de que se elimine
        membership = OrganizationMember(
            user_id=user2_id,
            organization_id=test_organization.id,
            role_id=viewer_role_id,
        )
        db_session.add(membership)
        db_session.commit()

        response = client.delete(
            f"/api/v1/organizations/{test_organization.id}/members/{user2_id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

        # Verificar que el usuario fue eliminado o desactivado
        db_session.expire_all()
        user = db_session.get(User, user2_id)
        assert user is None or user.is_active is False

    def test_delete_user_multiple_orgs(
        self, client, auth_headers, test_organization, test_organization2, test_user2, db_session
    ):
        """Usuario con 2+ orgs -> solo quitar membership."""
        viewer_role_id_org1 = _get_role_id(db_session, test_organization.id, "viewer")
        viewer_role_id_org2 = _get_role_id(db_session, test_organization2.id, "viewer")

        # Agregar user2 a ambas orgs
        db_session.add(OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role_id=viewer_role_id_org1,
        ))
        db_session.add(OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization2.id,
            role_id=viewer_role_id_org2,
        ))
        db_session.commit()

        response = client.delete(
            f"/api/v1/organizations/{test_organization.id}/members/{test_user2.id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

        # Verificar que el usuario SIGUE existiendo
        db_session.expire_all()
        user = db_session.get(User, test_user2.id)
        assert user is not None

        # Pero ya no es miembro de org1
        membership = db_session.query(OrganizationMember).filter(
            OrganizationMember.user_id == test_user2.id,
            OrganizationMember.organization_id == test_organization.id,
        ).first()
        assert membership is None

    def test_admin_cannot_delete_self(
        self, client, auth_headers, test_organization, test_user
    ):
        response = client.delete(
            f"/api/v1/organizations/{test_organization.id}/members/{test_user.id}",
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "eliminarte a ti mismo" in response.json()["detail"].lower()

    def test_non_admin_cannot_delete(
        self, client, auth_headers_user2, test_organization, test_user, test_user2, db_session
    ):
        viewer_role_id = _get_role_id(db_session, test_organization.id, "viewer")
        db_session.add(OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role_id=viewer_role_id,
        ))
        db_session.commit()

        response = client.delete(
            f"/api/v1/organizations/{test_organization.id}/members/{test_user.id}",
            headers=auth_headers_user2,
        )

        assert response.status_code == 403


class TestDeleteRoleWithReassignment:
    """DELETE /roles/{id}?reassign_to=UUID"""

    def test_delete_empty_role(self, client, org_headers, db_session, test_organization):
        """Rol sin usuarios -> eliminar directo."""
        # Crear rol custom
        response = client.post(
            "/api/v1/roles",
            json={"name": "temporal", "display_name": "Temporal", "permission_codes": []},
            headers=org_headers,
        )
        assert response.status_code == 201
        role_id = response.json()["id"]

        # Eliminar sin reassign_to
        response = client.delete(f"/api/v1/roles/{role_id}", headers=org_headers)
        assert response.status_code == 204

    def test_delete_role_with_reassignment(
        self, client, org_headers, db_session, test_organization, test_user2
    ):
        """Rol con usuarios + reassign_to -> reasignar y eliminar."""
        # Crear rol custom
        response = client.post(
            "/api/v1/roles",
            json={"name": "to_delete", "display_name": "A Eliminar", "permission_codes": []},
            headers=org_headers,
        )
        custom_role_id = response.json()["id"]

        # Agregar user2 con ese rol
        db_session.add(OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role_id=custom_role_id,
        ))
        db_session.commit()

        # Eliminar con reasignacion a viewer
        viewer_role_id = _get_role_id(db_session, test_organization.id, "viewer")
        response = client.delete(
            f"/api/v1/roles/{custom_role_id}",
            params={"reassign_to": str(viewer_role_id)},
            headers=org_headers,
        )

        assert response.status_code == 204

        # Verificar que user2 ahora tiene rol viewer
        db_session.expire_all()
        membership = db_session.query(OrganizationMember).filter(
            OrganizationMember.user_id == test_user2.id,
            OrganizationMember.organization_id == test_organization.id,
        ).first()
        assert membership is not None
        assert membership.role_id == viewer_role_id

    def test_delete_role_with_users_no_reassign_fails(
        self, client, org_headers, db_session, test_organization, test_user2
    ):
        """Rol con usuarios sin reassign_to -> error 400."""
        response = client.post(
            "/api/v1/roles",
            json={"name": "has_users", "display_name": "Tiene Usuarios", "permission_codes": []},
            headers=org_headers,
        )
        custom_role_id = response.json()["id"]

        db_session.add(OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role_id=custom_role_id,
        ))
        db_session.commit()

        response = client.delete(
            f"/api/v1/roles/{custom_role_id}",
            headers=org_headers,
        )

        assert response.status_code == 400
        assert "reasignar" in response.json()["detail"].lower()

    def test_delete_role_reassign_to_same_fails(
        self, client, org_headers, db_session, test_organization, test_user2
    ):
        """Reasignar al mismo rol -> error 400."""
        response = client.post(
            "/api/v1/roles",
            json={"name": "self_ref", "display_name": "Self Ref", "permission_codes": []},
            headers=org_headers,
        )
        custom_role_id = response.json()["id"]

        db_session.add(OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role_id=custom_role_id,
        ))
        db_session.commit()

        response = client.delete(
            f"/api/v1/roles/{custom_role_id}",
            params={"reassign_to": custom_role_id},
            headers=org_headers,
        )

        assert response.status_code == 400

    def test_cannot_delete_system_role(self, client, org_headers, db_session, test_organization):
        """No se puede eliminar rol del sistema."""
        admin_role_id = _get_role_id(db_session, test_organization.id, "admin")

        response = client.delete(
            f"/api/v1/roles/{admin_role_id}",
            headers=org_headers,
        )

        assert response.status_code == 400
        assert "sistema" in response.json()["detail"].lower()
