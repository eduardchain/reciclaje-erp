import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User, OrganizationMember
from app.models.organization import Organization
from app.services.organization import (
    create_organization,
    get_user_organizations,
    add_member,
    remove_member,
    update_member_role,
)
from app.schemas.organization import OrganizationCreate


class TestCreateOrganization:
    """Tests for creating organizations."""
    
    def test_create_organization_success(
        self,
        client: TestClient,
        auth_headers: dict,
    ):
        """Test creating a new organization."""
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
        """Test creating organization with custom slug."""
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
        """Test auto-generation of slug from name."""
        response = client.post(
            "/api/v1/organizations",
            json={"name": "Test Ñoño & Company!"},
            headers=auth_headers,
        )
        
        assert response.status_code == 201
        data = response.json()
        # Unicode characters are preserved, spaces to hyphens
        # Note: \w in Python regex includes Unicode letters like ñ
        assert data["slug"] == "test-ñoño-company"
    
    def test_create_organization_unique_slug(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
    ):
        """Test that duplicate slugs are handled with counter."""
        # Try to create org with same name as existing
        response = client.post(
            "/api/v1/organizations",
            json={"name": "Test Organization"},
            headers=auth_headers,
        )
        
        assert response.status_code == 201
        data = response.json()
        # Should append number to make it unique
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
        """Test listing all organizations user is member of."""
        response = client.get(
            "/api/v1/organizations",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        
        # Check roles are correct
        orgs_by_id = {org["id"]: org for org in data}
        assert orgs_by_id[str(test_organization.id)]["member_role"] == "admin"
        assert orgs_by_id[str(test_organization2.id)]["member_role"] == "manager"
    
    def test_get_organizations_empty_list(
        self,
        client: TestClient,
        auth_headers_user2: dict,
    ):
        """Test user with no organizations gets empty list."""
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
        """Test getting organization details as member."""
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
        """Test non-member cannot access organization."""
        response = client.get(
            f"/api/v1/organizations/{test_organization.id}",
            headers=auth_headers_user2,
        )
        
        assert response.status_code == 404
        assert "no eres miembro" in response.json()["detail"].lower() or "no encontrad" in response.json()["detail"].lower()


class TestAddMember:
    """Tests for adding members to organization."""
    
    def test_add_member_success(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
        test_user2: User,
    ):
        """Test admin can add member to organization."""
        response = client.post(
            f"/api/v1/organizations/{test_organization.id}/members",
            json={"user_id": str(test_user2.id), "role": "user"},
            headers=auth_headers,
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == str(test_user2.id)
        assert data["role"] == "user"
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
        # Create org where test_user is just a 'user' (not admin)
        org = Organization(name="Test Org", slug="test-org-3")
        db_session.add(org)
        db_session.flush()
        
        membership = OrganizationMember(
            user_id=test_user.id,
            organization_id=org.id,
            role="user",  # Not admin
        )
        db_session.add(membership)
        db_session.commit()
        
        # Try to add member
        response = client.post(
            f"/api/v1/organizations/{org.id}/members",
            json={"user_id": str(test_user2.id), "role": "user"},
            headers=auth_headers,
        )
        
        assert response.status_code == 403
        assert "only admins" in response.json()["detail"].lower()
    
    def test_add_member_max_users_reached(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        auth_headers: dict,
    ):
        """Test cannot add member when max_users limit is reached."""
        # Create org with max_users=2
        org = Organization(name="Small Org", slug="small-org", max_users=2)
        db_session.add(org)
        db_session.flush()
        
        # Add test_user as admin (1/2 slots)
        membership1 = OrganizationMember(
            user_id=test_user.id,
            organization_id=org.id,
            role="admin",
        )
        db_session.add(membership1)
        
        # Add another user (2/2 slots - FULL)
        user2 = User(
            email="full@example.com",
            hashed_password="hash",
            is_active=True,
        )
        db_session.add(user2)
        db_session.flush()
        
        membership2 = OrganizationMember(
            user_id=user2.id,
            organization_id=org.id,
            role="user",
        )
        db_session.add(membership2)
        db_session.commit()
        
        # Try to add third user (should fail)
        user3 = User(
            email="third@example.com",
            hashed_password="hash",
            is_active=True,
        )
        db_session.add(user3)
        db_session.commit()
        
        response = client.post(
            f"/api/v1/organizations/{org.id}/members",
            json={"user_id": str(user3.id), "role": "user"},
            headers=auth_headers,
        )
        
        assert response.status_code == 400
        assert "maximum capacity" in response.json()["detail"].lower()
    
    def test_add_member_already_member(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
        test_user2: User,
        db_session: Session,
    ):
        """Test cannot add user who is already a member."""
        # Add user2 first time
        membership = OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role="user",
        )
        db_session.add(membership)
        db_session.commit()
        
        # Try to add again
        response = client.post(
            f"/api/v1/organizations/{test_organization.id}/members",
            json={"user_id": str(test_user2.id), "role": "admin"},
            headers=auth_headers,
        )
        
        assert response.status_code == 400
        assert "already a member" in response.json()["detail"].lower()


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
        """Test admin can remove member."""
        # Add user2 as member
        membership = OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role="user",
        )
        db_session.add(membership)
        db_session.commit()
        
        # Remove member
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
        """Test cannot remove the last admin from organization."""
        # test_user is the only admin
        response = client.delete(
            f"/api/v1/organizations/{test_organization.id}/members/{test_user.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 400
        assert "last admin" in response.json()["detail"].lower()
    
    def test_can_remove_admin_when_multiple_admins(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
        test_user2: User,
        db_session: Session,
    ):
        """Test can remove admin when there are multiple admins."""
        # Add user2 as another admin
        membership = OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role="admin",
        )
        db_session.add(membership)
        db_session.commit()
        
        # Now we can remove one admin
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
        """Test admin can update member role."""
        # Add user2 as user
        membership = OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role="user",
        )
        db_session.add(membership)
        db_session.commit()
        
        # Update to manager
        response = client.patch(
            f"/api/v1/organizations/{test_organization.id}/members/{test_user2.id}",
            json={"role": "manager"},
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "manager"
    
    def test_cannot_change_last_admin_role(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
        test_user: User,
    ):
        """Test cannot change role of last admin."""
        # test_user is the only admin, try to change to user
        response = client.patch(
            f"/api/v1/organizations/{test_organization.id}/members/{test_user.id}",
            json={"role": "user"},
            headers=auth_headers,
        )
        
        assert response.status_code == 400
        assert "last admin" in response.json()["detail"].lower()
    
    def test_can_change_admin_role_when_multiple_admins(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
        test_user: User,
        test_user2: User,
        db_session: Session,
    ):
        """Test can change admin role when multiple admins exist."""
        # Add user2 as another admin
        membership = OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role="admin",
        )
        db_session.add(membership)
        db_session.commit()
        
        # Now we can change test_user to manager
        response = client.patch(
            f"/api/v1/organizations/{test_organization.id}/members/{test_user.id}",
            json={"role": "manager"},
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "manager"


class TestMultipleOrganizations:
    """Tests for users in multiple organizations."""
    
    def test_user_can_be_member_of_multiple_orgs(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
        test_organization2: Organization,
    ):
        """Test user can be member of multiple organizations."""
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
        """Test user has different roles in different organizations."""
        response = client.get(
            "/api/v1/organizations",
            headers=auth_headers,
        )
        
        data = response.json()
        orgs_by_id = {org["id"]: org for org in data}
        
        # test_user is admin in test_organization
        assert orgs_by_id[str(test_organization.id)]["member_role"] == "admin"
        
        # test_user is manager in test_organization2
        assert orgs_by_id[str(test_organization2.id)]["member_role"] == "manager"


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
        """Test user can voluntarily leave organization."""
        # Add user2 as another admin first (so test_user isn't last admin)
        membership = OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role="admin",
        )
        db_session.add(membership)
        db_session.commit()
        
        # test_user leaves
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
        """Test last admin cannot leave organization."""
        response = client.post(
            f"/api/v1/organizations/{test_organization.id}/leave",
            headers=auth_headers,
        )
        
        assert response.status_code == 400
        assert "last admin" in response.json()["detail"].lower()
    
    def test_non_member_cannot_leave(
        self,
        client: TestClient,
        auth_headers_user2: dict,
        test_organization: Organization,
    ):
        """Test non-member gets 404 when trying to leave."""
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
        """Test admin can update organization details."""
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
        """Test non-admin cannot update organization."""
        # test_user is manager (not admin) in test_organization2
        response = client.patch(
            f"/api/v1/organizations/{test_organization2.id}",
            json={"name": "Hacked Name"},
            headers=auth_headers,
        )
        
        assert response.status_code == 403
        assert "only admins" in response.json()["detail"].lower()
    
    def test_cannot_set_max_users_below_current_count(
        self,
        client: TestClient,
        auth_headers: dict,
        test_organization: Organization,
        test_user2: User,
        db_session: Session,
    ):
        """Test cannot set max_users below current member count."""
        # Add user2 (now we have 2 members)
        membership = OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role="user",
        )
        db_session.add(membership)
        db_session.commit()
        
        # Try to set max_users to 1 (less than 2 current members)
        response = client.patch(
            f"/api/v1/organizations/{test_organization.id}",
            json={"max_users": 1},
            headers=auth_headers,
        )
        
        assert response.status_code == 400
        assert "currently has" in response.json()["detail"].lower()


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
        """Test listing all organization members."""
        # Add user2
        membership = OrganizationMember(
            user_id=test_user2.id,
            organization_id=test_organization.id,
            role="user",
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
        
        # Check both users are in list
        user_ids = [member["user_id"] for member in data]
        assert str(test_user.id) in user_ids
        assert str(test_user2.id) in user_ids
        
        # Check user details are included
        user_emails = [member["user_email"] for member in data]
        assert test_user.email in user_emails
        assert test_user2.email in user_emails
    
    def test_non_member_cannot_list_members(
        self,
        client: TestClient,
        auth_headers_user2: dict,
        test_organization: Organization,
    ):
        """Test non-member cannot list organization members."""
        response = client.get(
            f"/api/v1/organizations/{test_organization.id}/members",
            headers=auth_headers_user2,
        )
        
        assert response.status_code == 404
