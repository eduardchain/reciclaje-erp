import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User, OrganizationMember
from app.models.organization import Organization
from app.models.role import Role
from app.services.role import role_service
from app.services.organization import (
    create_organization,
    get_user_organizations,
    add_member,
    remove_member,
    update_member_role,
)
from app.schemas.organization import OrganizationCreate


def _get_role_id(db: Session, org_id, role_name: str):
    """Helper: get role_id for a given org and role name."""
    role = db.query(Role).filter(
        Role.organization_id == org_id,
        Role.name == role_name,
    ).first()
    return role.id if role else None


def _setup_org_with_roles(db: Session, user, slug, role_name="admin", max_users=10):
    """Helper: create org with roles seeded and user as member."""
    org = Organization(name=f"Org {slug}", slug=slug, max_users=max_users)
    db.add(org)
    db.flush()
    role_service.seed_permissions(db)
    role_service.create_system_roles_for_org(db, org.id)
    db.flush()
    role_id = _get_role_id(db, org.id, role_name)
    membership = OrganizationMember(
        user_id=user.id,
        organization_id=org.id,
        role_id=role_id,
    )
    db.add(membership)
    db.commit()
    db.refresh(org)
    return org


class TestCreateOrganization:
    """Tests for creating organizations."""

    def test_create_organization_success(
        self,
        client: TestClient,
        auth_headers: dict,
    ):
        response = client.post(
            "/api/v1/organizations",
            json={"name": "My New Organization"},
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My New Organization"
        assert data["slug"] == "my-new-organization"
        assert data["member_role"] == "admin"
        assert data["max_users"] == 10

    def test_create_organization_with_custom_slug(
        self,
        client: TestClient,
        auth_headers: dict,
    ):
        response = client.post(
            "/api/v1/organizations",
            json={"name": "Custom Org", "slug": "my-custom-slug"},
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["slug"] == "my-custom-slug"

    def test_create_organization_auto_generates_slug(
        self,
        client: TestClient,
        auth_headers: dict,
    ):
        response = client.post(
            "/api/v1/organizations",
            json={"name": "Test Ñoño & Company!"},
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["slug"] == "test-ñoño-company"

    def test_create_organization_unique_slug(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
    ):
        response = client.post(
            "/api/v1/organizations",
            json={"name": "Test Organization"},
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["slug"] == "test-organization-1"


class TestGetOrganizations:
    """Tests for listing user's organizations."""

    def test_get_user_organizations(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
        test_organization2: Organization,
    ):
        response = client.get(
            "/api/v1/organizations",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        orgs_by_id = {org["id"]: org for org in data}
        assert orgs_by_id[str(test_organization.id)]["member_role"] == "admin"
        assert orgs_by_id[str(test_organization2.id)]["member_role"] == "viewer"

    def test_get_organizations_empty_list(
        self,
        client: TestClient,
        auth_headers_user2: dict,
    ):
        response = client.get(
            "/api/v1/organizations",
            headers=auth_headers_user2,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0


class TestGetOrganizationDetails:
    """Tests for getting organization details."""

    def test_get_organization_success(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
    ):
        response = client.get(
            f"/api/v1/organizations/{test_organization.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_organization.id)
        assert data["name"] == test_organization.name
        assert data["member_role"] == "admin"

    def test_get_organization_not_member(
        self,
        client: TestClient,
        auth_headers_user2: dict,
        test_organization: Organization,
    ):
        response = client.get(
            f"/api/v1/organizations/{test_organization.id}",
            headers=auth_headers_user2,
        )

        assert response.status_code == 404


class TestAddMember:
    """Tests for adding members to organization."""

    def test_add_member_success(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
        test_user2: User,
        db_session: Session,
    ):
        viewer_role_id = _get_role_id(db_session, test_organization.id, "viewer")
        response = client.post(
            f"/api/v1/organizations/{test_organization.id}/members",
            json={"user_id": str(test_user2.id), "role_id": str(viewer_role_id)},
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == str(test_user2.id)
        assert data["role_id"] == str(viewer_role_id)
        assert data["role_name"] == "viewer"
        assert data["user_email"] == test_user2.email

    def test_add_member_non_admin_forbidden(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        test_user2: User,
        test_user3: User,
        auth_headers: dict,
    ):
        """Test non-admin cannot add members."""
        org = _setup_org_with_roles(db_session, test_user, "test-org-3", role_name="viewer")
        viewer_role_id = _get_role_id(db_session, org.id, "viewer")

        response = client.post(
            f"/api/v1/organizations/{org.id}/members",
            json={"user_id": str(test_user2.id), "role_id": str(viewer_role_id)},
            headers=auth_headers,
        )

        assert response.status_code == 403

    def test_add_member_max_users_reached(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict,
    ):
        """Test cannot add member when max_users limit is reached."""
        org = _setup_org_with_roles(db_session, test_user, "small-org", role_name="admin", max_users=2)
        viewer_role_id = _get_role_id(db_session, org.id, "viewer")

        user2 = User(email="full@example.com", hashed_password="hash", is_active=True)
        db_session.add(user2)
        db_session.flush()
        membership2 = OrganizationMember(
            user_id=user2.id, organization_id=org.id, role_id=viewer_role_id,
        )
        db_session.add(membership2)
        db_session.commit()

        user3 = User(email="third@example.com", hashed_password="hash", is_active=True)
        db_session.add(user3)
        db_session.commit()

        response = client.post(
            f"/api/v1/organizations/{org.id}/members",
            json={"user_id": str(user3.id), "role_id": str(viewer_role_id)},
            headers=auth_headers,
        )

        assert response.status_code == 400

    def test_add_member_already_member(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
        test_user2: User,
        db_session: Session,
    ):
        viewer_role_id = _get_role_id(db_session, test_organization.id, "viewer")
        membership = OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role_id=viewer_role_id,
        )
        db_session.add(membership)
        db_session.commit()

        admin_role_id = _get_role_id(db_session, test_organization.id, "admin")
        response = client.post(
            f"/api/v1/organizations/{test_organization.id}/members",
            json={"user_id": str(test_user2.id), "role_id": str(admin_role_id)},
            headers=auth_headers,
        )

        assert response.status_code == 400


class TestRemoveMember:
    """Tests for removing members from organization."""

    def test_remove_member_success(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
        test_user2: User,
        db_session: Session,
    ):
        viewer_role_id = _get_role_id(db_session, test_organization.id, "viewer")
        membership = OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role_id=viewer_role_id,
        )
        db_session.add(membership)
        db_session.commit()

        response = client.delete(
            f"/api/v1/organizations/{test_organization.id}/members/{test_user2.id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

    def test_cannot_remove_last_admin(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
        test_user: User,
    ):
        response = client.delete(
            f"/api/v1/organizations/{test_organization.id}/members/{test_user.id}",
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "ultimo administrador" in response.json()["detail"].lower()

    def test_can_remove_admin_when_multiple_admins(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
        test_user2: User,
        db_session: Session,
    ):
        admin_role_id = _get_role_id(db_session, test_organization.id, "admin")
        membership = OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role_id=admin_role_id,
        )
        db_session.add(membership)
        db_session.commit()

        response = client.delete(
            f"/api/v1/organizations/{test_organization.id}/members/{test_user2.id}",
            headers=auth_headers,
        )

        assert response.status_code == 204


class TestUpdateMemberRole:
    """Tests for updating member roles."""

    def test_update_member_role_success(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
        test_user2: User,
        db_session: Session,
    ):
        viewer_role_id = _get_role_id(db_session, test_organization.id, "viewer")
        membership = OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role_id=viewer_role_id,
        )
        db_session.add(membership)
        db_session.commit()

        bascula_role_id = _get_role_id(db_session, test_organization.id, "bascula")
        response = client.patch(
            f"/api/v1/organizations/{test_organization.id}/members/{test_user2.id}",
            json={"role_id": str(bascula_role_id)},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["role_name"] == "bascula"

    def test_cannot_change_last_admin_role(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
        test_user: User,
        db_session: Session,
    ):
        viewer_role_id = _get_role_id(db_session, test_organization.id, "viewer")
        response = client.patch(
            f"/api/v1/organizations/{test_organization.id}/members/{test_user.id}",
            json={"role_id": str(viewer_role_id)},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "ultimo administrador" in response.json()["detail"].lower()

    def test_can_change_admin_role_when_multiple_admins(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
        test_user: User,
        test_user2: User,
        db_session: Session,
    ):
        admin_role_id = _get_role_id(db_session, test_organization.id, "admin")
        membership = OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role_id=admin_role_id,
        )
        db_session.add(membership)
        db_session.commit()

        viewer_role_id = _get_role_id(db_session, test_organization.id, "viewer")
        response = client.patch(
            f"/api/v1/organizations/{test_organization.id}/members/{test_user.id}",
            json={"role_id": str(viewer_role_id)},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["role_name"] == "viewer"


class TestMultipleOrganizations:
    """Tests for users in multiple organizations."""

    def test_user_can_be_member_of_multiple_orgs(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
        test_organization2: Organization,
    ):
        response = client.get(
            "/api/v1/organizations",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_user_has_different_roles_in_different_orgs(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
        test_organization2: Organization,
    ):
        response = client.get(
            "/api/v1/organizations",
            headers=auth_headers,
        )

        data = response.json()
        orgs_by_id = {org["id"]: org for org in data}

        assert orgs_by_id[str(test_organization.id)]["member_role"] == "admin"
        assert orgs_by_id[str(test_organization2.id)]["member_role"] == "viewer"


class TestLeaveOrganization:
    """Tests for leaving organizations."""

    def test_user_can_leave_organization(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
        test_user2: User,
        test_user: User,
        db_session: Session,
    ):
        admin_role_id = _get_role_id(db_session, test_organization.id, "admin")
        membership = OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role_id=admin_role_id,
        )
        db_session.add(membership)
        db_session.commit()

        response = client.post(
            f"/api/v1/organizations/{test_organization.id}/leave",
            headers=auth_headers,
        )

        assert response.status_code == 204

    def test_cannot_leave_if_last_admin(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
    ):
        response = client.post(
            f"/api/v1/organizations/{test_organization.id}/leave",
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "ultimo administrador" in response.json()["detail"].lower()

    def test_non_member_cannot_leave(
        self,
        client: TestClient,
        auth_headers_user2: dict,
        test_organization: Organization,
    ):
        response = client.post(
            f"/api/v1/organizations/{test_organization.id}/leave",
            headers=auth_headers_user2,
        )

        assert response.status_code == 404


class TestUpdateOrganization:
    """Tests for updating organization details."""

    def test_admin_can_update_organization(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
    ):
        response = client.patch(
            f"/api/v1/organizations/{test_organization.id}",
            json={
                "name": "Updated Name",
                "max_users": 20,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["max_users"] == 20

    def test_non_admin_cannot_update(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization2: Organization,
    ):
        response = client.patch(
            f"/api/v1/organizations/{test_organization2.id}",
            json={"name": "Hacked Name"},
            headers=auth_headers,
        )

        assert response.status_code == 403

    def test_cannot_set_max_users_below_current_count(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
        test_user2: User,
        db_session: Session,
    ):
        viewer_role_id = _get_role_id(db_session, test_organization.id, "viewer")
        membership = OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role_id=viewer_role_id,
        )
        db_session.add(membership)
        db_session.commit()

        response = client.patch(
            f"/api/v1/organizations/{test_organization.id}",
            json={"max_users": 1},
            headers=auth_headers,
        )

        assert response.status_code == 400


class TestGetOrganizationMembers:
    """Tests for listing organization members."""

    def test_get_organization_members(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
        test_user: User,
        test_user2: User,
        db_session: Session,
    ):
        viewer_role_id = _get_role_id(db_session, test_organization.id, "viewer")
        membership = OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role_id=viewer_role_id,
        )
        db_session.add(membership)
        db_session.commit()

        response = client.get(
            f"/api/v1/organizations/{test_organization.id}/members",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        user_ids = [member["user_id"] for member in data]
        assert str(test_user.id) in user_ids
        assert str(test_user2.id) in user_ids

        user_emails = [member["user_email"] for member in data]
        assert test_user.email in user_emails
        assert test_user2.email in user_emails

    def test_non_member_cannot_list_members(
        self,
        client: TestClient,
        auth_headers_user2: dict,
        test_organization: Organization,
    ):
        response = client.get(
            f"/api/v1/organizations/{test_organization.id}/members",
            headers=auth_headers_user2,
        )

        assert response.status_code == 404
