"""Tests para endpoints /system/ (super admin)."""
import pytest
from uuid import uuid4

from app.models.user import User, OrganizationMember
from app.models.organization import Organization
from app.models.role import Role
from app.core.security import get_password_hash, create_access_token
from app.services.role import role_service


# ---- Fixtures ----
# Nota: test_user, test_user2, auth_headers, db_session vienen de conftest.py

@pytest.fixture
def superuser(db_session):
    """Crear super admin user (depende de db_session para que existan las tablas)."""
    user = User(
        email="superadmin@example.com",
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
    """Headers con token de superuser (sin org)."""
    token = create_access_token(data={"sub": str(superuser.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def org_with_roles(db_session, test_user):
    """Crear org con roles seedeados y test_user como admin."""
    org = Organization(name="Org Alpha", slug="org-alpha", max_users=10)
    db_session.add(org)
    db_session.flush()

    role_service.seed_permissions(db_session)
    role_service.create_system_roles_for_org(db_session, org.id)
    db_session.flush()

    admin_role = db_session.query(Role).filter(
        Role.organization_id == org.id, Role.name == "admin"
    ).first()
    membership = OrganizationMember(
        user_id=test_user.id,
        organization_id=org.id,
        role_id=admin_role.id,
    )
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(org)
    return org


# ---- Listar Organizaciones ----

class TestSystemOrganizations:
    def test_list_orgs_as_superuser(self, client, su_headers, org_with_roles):
        resp = client.get("/api/v1/system/organizations", headers=su_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        org_data = next(o for o in data if o["id"] == str(org_with_roles.id))
        assert org_data["name"] == "Org Alpha"
        assert org_data["is_active"] is True
        assert org_data["member_count"] >= 1

    def test_list_orgs_excludes_inactive_by_default(self, client, su_headers, db_session, org_with_roles):
        # Crear org inactiva
        inactive = Organization(name="Inactive Org", slug="inactive-org", is_active=False)
        db_session.add(inactive)
        db_session.commit()

        resp = client.get("/api/v1/system/organizations", headers=su_headers)
        data = resp.json()
        slugs = [o["slug"] for o in data]
        assert "inactive-org" not in slugs

    def test_list_orgs_include_inactive(self, client, su_headers, db_session, org_with_roles):
        inactive = Organization(name="Inactive Org", slug="inactive-org", is_active=False)
        db_session.add(inactive)
        db_session.commit()

        resp = client.get(
            "/api/v1/system/organizations",
            headers=su_headers,
            params={"include_inactive": True},
        )
        data = resp.json()
        slugs = [o["slug"] for o in data]
        assert "inactive-org" in slugs

    def test_list_orgs_forbidden_for_non_superuser(self, client, auth_headers):
        resp = client.get("/api/v1/system/organizations", headers=auth_headers)
        assert resp.status_code == 403


class TestSystemCreateOrganization:
    def test_create_org_with_new_user(self, client, su_headers, db_session):
        # Seed permisos (necesarios para create_organization)
        role_service.seed_permissions(db_session)
        db_session.commit()

        resp = client.post(
            "/api/v1/system/organizations",
            headers=su_headers,
            json={
                "name": "New Corp",
                "admin_email": "newadmin@example.com",
                "admin_full_name": "New Admin",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "New Corp"
        assert data["member_count"] == 1

        # Verificar que usuario fue creado
        user = db_session.query(User).filter(User.email == "newadmin@example.com").first()
        assert user is not None
        assert user.full_name == "New Admin"

    def test_create_org_with_existing_user(self, client, su_headers, db_session, test_user):
        role_service.seed_permissions(db_session)
        db_session.commit()

        resp = client.post(
            "/api/v1/system/organizations",
            headers=su_headers,
            json={
                "name": "Existing User Corp",
                "admin_email": test_user.email,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["member_count"] == 1

    def test_create_org_new_user_requires_name(self, client, su_headers, db_session):
        role_service.seed_permissions(db_session)
        db_session.commit()

        resp = client.post(
            "/api/v1/system/organizations",
            headers=su_headers,
            json={
                "name": "No Name Corp",
                "admin_email": "noname@example.com",
            },
        )
        assert resp.status_code == 400
        assert "admin_full_name" in resp.json()["detail"]

    def test_create_org_forbidden_for_non_superuser(self, client, auth_headers):
        resp = client.post(
            "/api/v1/system/organizations",
            headers=auth_headers,
            json={"name": "Blocked Corp", "admin_email": "x@x.com", "admin_full_name": "X"},
        )
        assert resp.status_code == 403


class TestSystemUpdateOrganization:
    def test_update_org(self, client, su_headers, org_with_roles):
        resp = client.patch(
            f"/api/v1/system/organizations/{org_with_roles.id}",
            headers=su_headers,
            json={"name": "Org Alpha Updated", "max_users": 50},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Org Alpha Updated"
        assert data["max_users"] == 50

    def test_update_org_not_found(self, client, su_headers):
        resp = client.patch(
            f"/api/v1/system/organizations/{uuid4()}",
            headers=su_headers,
            json={"name": "Ghost"},
        )
        assert resp.status_code == 404


class TestSystemDeleteOrganization:
    def test_delete_org_soft(self, client, su_headers, db_session, org_with_roles):
        # Crear otra org para que no sea la unica activa
        org2 = Organization(name="Org Beta", slug="org-beta")
        db_session.add(org2)
        db_session.commit()

        resp = client.delete(
            f"/api/v1/system/organizations/{org_with_roles.id}",
            headers=su_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "desactivada" in data["message"].lower()

        # Verificar que org quedo inactiva
        db_session.expire_all()
        org = db_session.query(Organization).filter(Organization.id == org_with_roles.id).first()
        assert org.is_active is False

    def test_delete_org_deactivates_orphaned_users(self, client, su_headers, db_session, org_with_roles, test_user):
        # Crear otra org para que no sea la unica activa
        org2 = Organization(name="Org Beta", slug="org-beta")
        db_session.add(org2)
        db_session.commit()

        # test_user solo esta en org_with_roles → deberia ser desactivado
        resp = client.delete(
            f"/api/v1/system/organizations/{org_with_roles.id}",
            headers=su_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["orphaned_users_deactivated"] >= 1

        db_session.expire_all()
        user = db_session.query(User).filter(User.id == test_user.id).first()
        assert user.is_active is False

    def test_cannot_delete_last_active_org(self, client, su_headers, org_with_roles):
        # Solo hay una org activa
        resp = client.delete(
            f"/api/v1/system/organizations/{org_with_roles.id}",
            headers=su_headers,
        )
        assert resp.status_code == 400
        assert "unica" in resp.json()["detail"].lower()


# ---- Usuarios ----

class TestSystemUsers:
    def test_list_users(self, client, su_headers, test_user, org_with_roles):
        resp = client.get("/api/v1/system/users", headers=su_headers)
        assert resp.status_code == 200
        data = resp.json()
        # Al menos superuser + test_user
        assert len(data) >= 2
        # test_user tiene membership
        tu = next(u for u in data if u["email"] == test_user.email)
        assert len(tu["memberships"]) >= 1
        assert tu["memberships"][0]["organization_name"] == "Org Alpha"

    def test_list_users_forbidden_for_non_superuser(self, client, auth_headers):
        resp = client.get("/api/v1/system/users", headers=auth_headers)
        assert resp.status_code == 403


class TestSystemAddUserToOrg:
    def test_add_user_to_org(self, client, su_headers, db_session, superuser, org_with_roles):
        # Obtener viewer role de la org
        viewer_role = db_session.query(Role).filter(
            Role.organization_id == org_with_roles.id, Role.name == "viewer"
        ).first()

        resp = client.post(
            f"/api/v1/system/users/{superuser.id}/add-to-org",
            headers=su_headers,
            json={
                "organization_id": str(org_with_roles.id),
                "role_id": str(viewer_role.id),
            },
        )
        assert resp.status_code == 201
        assert "agregado" in resp.json()["message"].lower()

    def test_add_user_already_member(self, client, su_headers, db_session, test_user, org_with_roles):
        admin_role = db_session.query(Role).filter(
            Role.organization_id == org_with_roles.id, Role.name == "admin"
        ).first()

        resp = client.post(
            f"/api/v1/system/users/{test_user.id}/add-to-org",
            headers=su_headers,
            json={
                "organization_id": str(org_with_roles.id),
                "role_id": str(admin_role.id),
            },
        )
        assert resp.status_code == 400
        assert "ya es miembro" in resp.json()["detail"].lower()

    def test_add_user_not_found(self, client, su_headers, org_with_roles, db_session):
        viewer_role = db_session.query(Role).filter(
            Role.organization_id == org_with_roles.id, Role.name == "viewer"
        ).first()

        resp = client.post(
            f"/api/v1/system/users/{uuid4()}/add-to-org",
            headers=su_headers,
            json={
                "organization_id": str(org_with_roles.id),
                "role_id": str(viewer_role.id),
            },
        )
        assert resp.status_code == 404


# ---- Superuser bypass en org-scoped endpoints ----

class TestSuperuserBypass:
    def test_superuser_accesses_org_without_membership(self, client, su_headers, org_with_roles):
        """Superuser sin membership puede acceder a endpoints org-scoped."""
        headers = {**su_headers, "X-Organization-ID": str(org_with_roles.id)}
        # Intentar endpoint que requiere org context (ej: listar materiales)
        resp = client.get("/api/v1/materials/", headers=headers)
        assert resp.status_code == 200

    def test_non_superuser_without_membership_rejected(self, client, db_session, org_with_roles):
        """Usuario no-superuser sin membership recibe 403."""
        # Crear usuario sin membership en org_with_roles
        user = User(
            email="outsider@example.com",
            hashed_password=get_password_hash("test"),
            full_name="Outsider",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        token = create_access_token(data={"sub": str(user.id)})
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Organization-ID": str(org_with_roles.id),
        }
        resp = client.get("/api/v1/materials/", headers=headers)
        assert resp.status_code == 403
