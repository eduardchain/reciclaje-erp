import pytest
from fastapi.testclient import TestClient

from app.models.user import User


class TestRegisterWithOrganization:
    """Tests for registration with organization creation."""
    
    def test_register_with_organization_name(
        self,
        client: TestClient,
    ):
        """Test registering user with organization creates both."""
        response = client.post(
            "/api/v1/auth/register",
            params={"organization_name": "My Test Company"},
            json={
                "email": "newuser@example.com",
                "password": "password123",
                "full_name": "New User"
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        
        # Check user was created
        assert "user" in data
        assert data["user"]["email"] == "newuser@example.com"
        assert data["user"]["full_name"] == "New User"
        
        # Check organization was created
        assert "organization" in data
        assert data["organization"]["name"] == "My Test Company"
        assert data["organization"]["slug"] == "my-test-company"
        assert data["organization"]["role"] == "admin"
    
    def test_register_without_organization_name(
        self,
        client: TestClient,
    ):
        """Test registering user without organization works."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "solo@example.com",
                "password": "password123",
                "full_name": "Solo User"
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        
        # Check user was created
        assert "user" in data
        assert data["user"]["email"] == "solo@example.com"
        
        # Check NO organization was created
        assert "organization" not in data
    
    def test_organization_owner_gets_admin_role(
        self,
        client: TestClient,
    ):
        """Test user who creates organization gets admin role."""
        # Register with org
        response = client.post(
            "/api/v1/auth/register",
            params={"organization_name": "Admin Test Org"},
            json={
                "email": "admin@example.com",
                "password": "password123",
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        
        # Verify admin role
        assert data["organization"]["role"] == "admin"
        
        # Login
        login_response = client.post(
            "/api/v1/auth/login/json",
            json={
                "email": "admin@example.com",
                "password": "password123",
            },
        )
        token = login_response.json()["access_token"]
        
        # List organizations to confirm admin role
        orgs_response = client.get(
            "/api/v1/organizations",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert orgs_response.status_code == 200
        orgs = orgs_response.json()
        assert len(orgs) == 1
        assert orgs[0]["member_role"] == "admin"
    
    def test_register_response_includes_organization_details(
        self,
        client: TestClient,
    ):
        """Test registration response includes complete organization details."""
        response = client.post(
            "/api/v1/auth/register",
            params={"organization_name": "Detail Test"},
            json={
                "email": "detail@example.com",
                "password": "password123",
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        
        # Check all expected fields
        org = data["organization"]
        assert "id" in org
        assert "name" in org
        assert "slug" in org
        assert "role" in org
        
        assert org["name"] == "Detail Test"
        assert org["slug"] == "detail-test"
        assert org["role"] == "admin"
    
    def test_register_duplicate_email_fails(
        self,
        client: TestClient,
    ):
        """Test cannot register with existing email."""
        # First registration
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "duplicate@example.com",
                "password": "password123",
            },
        )
        
        # Try to register again with same email
        response = client.post(
            "/api/v1/auth/register",
            params={"organization_name": "Another Org"},
            json={
                "email": "duplicate@example.com",
                "password": "password123",
            },
        )
        
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()
