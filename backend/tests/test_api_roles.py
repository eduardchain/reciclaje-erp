"""Tests para el sistema de roles y permisos."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User, OrganizationMember
from app.models.organization import Organization
from app.models.role import Role
from app.services.role import role_service


def _get_role_id(db: Session, org_id, role_name: str):
    role = db.query(Role).filter(
        Role.organization_id == org_id,
        Role.name == role_name,
    ).first()
    return role.id if role else None


class TestListRoles:
    """Tests para listar roles de la organizacion."""

    def test_list_roles_returns_system_roles(
        self,
        client: TestClient,
        org_headers: dict,
    ):
        response = client.get("/api/v1/roles", headers=org_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 5
        names = {r["name"] for r in data}
        assert {"admin", "bascula", "liquidador", "planillador", "viewer"} <= names

        # System roles should have permission counts
        admin = next(r for r in data if r["name"] == "admin")
        assert admin["is_system_role"] is True
        assert admin["permission_count"] > 0

    def test_list_roles_includes_member_count(
        self,
        client: TestClient,
        org_headers: dict,
    ):
        response = client.get("/api/v1/roles", headers=org_headers)
        data = response.json()

        admin = next(r for r in data if r["name"] == "admin")
        assert admin["member_count"] == 1  # test_user is admin


class TestGetRoleDetail:
    """Tests para obtener detalle de un rol."""

    def test_get_role_with_permissions(
        self,
        client: TestClient,
        org_headers: dict,
        test_organization: Organization,
        db_session: Session,
    ):
        role_id = _get_role_id(db_session, test_organization.id, "bascula")
        response = client.get(f"/api/v1/roles/{role_id}", headers=org_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "bascula"
        assert data["is_system_role"] is True
        assert len(data["permissions"]) > 0

        perm_codes = {p["code"] for p in data["permissions"]}
        assert "purchases.create" in perm_codes
        assert "purchases.liquidate" not in perm_codes

    def test_get_role_not_found(
        self,
        client: TestClient,
        org_headers: dict,
    ):
        from uuid import uuid4
        response = client.get(f"/api/v1/roles/{uuid4()}", headers=org_headers)
        assert response.status_code == 404


class TestCreateRole:
    """Tests para crear roles personalizados."""

    def test_create_custom_role(
        self,
        client: TestClient,
        org_headers: dict,
    ):
        response = client.post(
            "/api/v1/roles",
            json={
                "name": "supervisor",
                "display_name": "Supervisor",
                "description": "Rol de supervision",
                "permission_codes": ["purchases.view", "sales.view", "inventory.view"],
            },
            headers=org_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "supervisor"
        assert data["display_name"] == "Supervisor"
        assert data["is_system_role"] is False
        assert len(data["permissions"]) == 3

    def test_create_role_duplicate_name(
        self,
        client: TestClient,
        org_headers: dict,
    ):
        """No se puede crear rol con nombre que ya existe."""
        response = client.post(
            "/api/v1/roles",
            json={
                "name": "admin",
                "display_name": "Otro Admin",
            },
            headers=org_headers,
        )

        assert response.status_code == 400
        assert "ya existe" in response.json()["detail"].lower()


class TestUpdateRole:
    """Tests para actualizar roles."""

    def test_update_role_permissions(
        self,
        client: TestClient,
        org_headers: dict,
    ):
        # Crear rol primero
        create = client.post(
            "/api/v1/roles",
            json={
                "name": "custom",
                "display_name": "Custom",
                "permission_codes": ["purchases.view"],
            },
            headers=org_headers,
        )
        role_id = create.json()["id"]

        # Actualizar permisos
        response = client.patch(
            f"/api/v1/roles/{role_id}",
            json={
                "display_name": "Custom Updated",
                "permission_codes": ["purchases.view", "sales.view", "inventory.view"],
            },
            headers=org_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Custom Updated"
        assert len(data["permissions"]) == 3


class TestDeleteRole:
    """Tests para eliminar roles."""

    def test_delete_custom_role(
        self,
        client: TestClient,
        org_headers: dict,
    ):
        create = client.post(
            "/api/v1/roles",
            json={"name": "temp", "display_name": "Temporal"},
            headers=org_headers,
        )
        role_id = create.json()["id"]

        response = client.delete(f"/api/v1/roles/{role_id}", headers=org_headers)
        assert response.status_code == 204

    def test_cannot_delete_system_role(
        self,
        client: TestClient,
        org_headers: dict,
        test_organization: Organization,
        db_session: Session,
    ):
        role_id = _get_role_id(db_session, test_organization.id, "admin")
        response = client.delete(f"/api/v1/roles/{role_id}", headers=org_headers)

        assert response.status_code == 400
        assert "sistema" in response.json()["detail"].lower()

    def test_cannot_delete_role_with_members(
        self,
        client: TestClient,
        org_headers: dict,
        test_organization: Organization,
        test_user2: User,
        db_session: Session,
    ):
        # Crear rol custom y asignar usuario
        create = client.post(
            "/api/v1/roles",
            json={"name": "occupied", "display_name": "Occupied"},
            headers=org_headers,
        )
        role_id = create.json()["id"]

        from uuid import UUID
        membership = OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role_id=UUID(role_id),
        )
        db_session.add(membership)
        db_session.commit()

        response = client.delete(f"/api/v1/roles/{role_id}", headers=org_headers)
        assert response.status_code == 400
        assert "usuario" in response.json()["detail"].lower()


class TestMyPermissions:
    """Tests para el endpoint my-permissions."""

    def test_admin_has_all_permissions(
        self,
        client: TestClient,
        org_headers: dict,
    ):
        response = client.get("/api/v1/roles/my-permissions", headers=org_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["role_name"] == "admin"
        assert data["is_admin"] is True
        assert len(data["permissions"]) >= 40  # Admin tiene todos


class TestListPermissions:
    """Tests para listar permisos del sistema."""

    def test_list_permissions_by_module(
        self,
        client: TestClient,
        org_headers: dict,
    ):
        response = client.get("/api/v1/roles/permissions", headers=org_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 10  # Al menos 10 modulos

        modules = {m["module"] for m in data}
        assert "purchases" in modules
        assert "sales" in modules
        assert "admin" in modules


class TestRequirePermission:
    """Tests para verificar que require_permission funciona."""

    def test_admin_bypasses_permission_check(
        self,
        client: TestClient,
        org_headers: dict,
    ):
        """Admin puede acceder a endpoints protegidos."""
        response = client.get("/api/v1/roles/permissions", headers=org_headers)
        assert response.status_code == 200

    def test_viewer_cannot_access_admin_endpoint(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization2: Organization,
    ):
        """Viewer no puede acceder a endpoints de admin."""
        headers = {
            **auth_headers,
            "X-Organization-ID": str(test_organization2.id),
        }
        # GET /permissions requiere admin.manage_roles
        response = client.get("/api/v1/roles/permissions", headers=headers)
        assert response.status_code == 403
        assert "permisos insuficientes" in response.json()["detail"].lower()
