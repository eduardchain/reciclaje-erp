"""
Comprehensive tests for Material Category CRUD endpoints.
"""
import pytest
from uuid import uuid4

from app.models.material import MaterialCategory


@pytest.fixture
def test_category(db_session, test_organization):
    """Create a test material category."""
    category = MaterialCategory(
        id=uuid4(),
        name="Test Category",
        description="A test category",
        organization_id=test_organization.id,
        is_active=True
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


class TestCreateMaterialCategory:
    """Tests for POST /api/v1/material-categories"""

    def test_create_category_success(self, client, org_headers):
        """Test successful category creation."""
        # Arrange
        category_data = {
            "name": "New Category",
            "description": "A newly created category"
        }

        # Act
        response = client.post("/api/v1/material-categories", json=category_data, headers=org_headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == category_data["name"]
        assert data["description"] == category_data["description"]
        assert data["is_active"] is True
        assert "id" in data
        assert "organization_id" in data
        assert "created_at" in data

    def test_create_category_without_description(self, client, org_headers):
        """Test creating category without optional description."""
        # Arrange
        category_data = {
            "name": "Category Without Description"
        }

        # Act
        response = client.post("/api/v1/material-categories", json=category_data, headers=org_headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == category_data["name"]
        assert data["description"] is None

    def test_create_category_without_auth(self, client):
        """Test creating category without authentication returns 401."""
        # Arrange
        category_data = {
            "name": "Unauthorized Category"
        }

        # Act
        response = client.post("/api/v1/material-categories", json=category_data)

        # Assert
        assert response.status_code == 401

    def test_create_category_invalid_data(self, client, org_headers):
        """Test creating category with invalid data returns 422."""
        # Arrange
        category_data = {
            "name": ""  # Empty name
        }

        # Act
        response = client.post("/api/v1/material-categories", json=category_data, headers=org_headers)

        # Assert
        assert response.status_code == 422


class TestGetMaterialCategory:
    """Tests for GET /api/v1/material-categories/{id}"""

    def test_get_category_success(self, client, org_headers, test_category):
        """Test successfully retrieving a category by ID."""
        # Act
        response = client.get(f"/api/v1/material-categories/{test_category.id}", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_category.id)
        assert data["name"] == test_category.name
        assert data["description"] == test_category.description
        assert data["is_active"] is True

    def test_get_category_not_found(self, client, org_headers):
        """Test getting non-existent category returns 404."""
        # Arrange
        fake_id = uuid4()

        # Act
        response = client.get(f"/api/v1/material-categories/{fake_id}", headers=org_headers)

        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_category_different_org(self, client, auth_headers, test_category, test_organization2):
        """Test getting category from different organization returns 404."""
        # Arrange
        org2_headers = {**auth_headers, "X-Organization-ID": str(test_organization2.id)}

        # Act
        response = client.get(f"/api/v1/material-categories/{test_category.id}", headers=org2_headers)

        # Assert
        assert response.status_code == 404


class TestListMaterialCategories:
    """Tests for GET /api/v1/material-categories"""

    def test_list_categories_pagination(self, client, org_headers, db_session, test_organization):
        """Test listing categories with pagination."""
        # Arrange - Create multiple categories
        categories = []
        for i in range(5):
            category = MaterialCategory(
                id=uuid4(),
                name=f"Category {i}",
                description=f"Description {i}",
                organization_id=test_organization.id,
                is_active=True
            )
            db_session.add(category)
            categories.append(category)
        db_session.commit()

        # Act
        response = client.get("/api/v1/material-categories?skip=0&limit=3", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data
        assert len(data["items"]) == 3
        assert data["total"] == 5
        assert data["skip"] == 0
        assert data["limit"] == 3

    def test_list_categories_search_filter(self, client, org_headers, db_session, test_organization):
        """Test searching categories by name or description."""
        # Arrange
        category1 = MaterialCategory(
            id=uuid4(),
            name="Electronics",
            description="Electronic components",
            organization_id=test_organization.id,
            is_active=True
        )
        category2 = MaterialCategory(
            id=uuid4(),
            name="Plastics",
            description="Plastic materials",
            organization_id=test_organization.id,
            is_active=True
        )
        db_session.add_all([category1, category2])
        db_session.commit()

        # Act
        response = client.get("/api/v1/material-categories?search=Electronic", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Electronics"

    def test_list_categories_is_active_filter(self, client, org_headers, db_session, test_organization):
        """Test filtering categories by is_active status."""
        # Arrange
        active_category = MaterialCategory(
            id=uuid4(),
            name="Active Category",
            organization_id=test_organization.id,
            is_active=True
        )
        inactive_category = MaterialCategory(
            id=uuid4(),
            name="Inactive Category",
            organization_id=test_organization.id,
            is_active=False
        )
        db_session.add_all([active_category, inactive_category])
        db_session.commit()

        # Act - Get only active
        response = client.get("/api/v1/material-categories?is_active=true", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert all(item["is_active"] is True for item in data["items"])

        # Act - Get only inactive
        response = client.get("/api/v1/material-categories?is_active=false", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert all(item["is_active"] is False for item in data["items"])

    def test_list_categories_sorting(self, client, org_headers, db_session, test_organization):
        """Test sorting categories."""
        # Arrange
        for name in ["Zebra", "Alpha", "Beta"]:
            category = MaterialCategory(
                id=uuid4(),
                name=name,
                organization_id=test_organization.id,
                is_active=True
            )
            db_session.add(category)
        db_session.commit()

        # Act - Sort by name ascending
        response = client.get("/api/v1/material-categories?sort_by=name&sort_order=asc", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        names = [item["name"] for item in data["items"]]
        assert names == sorted(names)

    def test_list_categories_organization_isolation(self, client, auth_headers, db_session, test_category, test_organization2):
        """Test that users only see categories from their organization."""
        # Arrange - Create category in second org
        org2_category = MaterialCategory(
            id=uuid4(),
            name="Org2 Category",
            organization_id=test_organization2.id,
            is_active=True
        )
        db_session.add(org2_category)
        db_session.commit()

        org2_headers = {**auth_headers, "X-Organization-ID": str(test_organization2.id)}

        # Act
        response = client.get("/api/v1/material-categories", headers=org2_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        category_ids = [item["id"] for item in data["items"]]
        assert str(org2_category.id) in category_ids
        assert str(test_category.id) not in category_ids

    def test_list_categories_default_pagination(self, client, org_headers):
        """Test default pagination parameters."""
        # Act
        response = client.get("/api/v1/material-categories", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["skip"] == 0
        assert data["limit"] == 100  # Default limit


class TestUpdateMaterialCategory:
    """Tests for PATCH /api/v1/material-categories/{id}"""

    def test_update_category_success(self, client, org_headers, test_category):
        """Test successfully updating a category."""
        # Arrange
        update_data = {
            "name": "Updated Category Name",
            "description": "Updated description"
        }

        # Act
        response = client.patch(f"/api/v1/material-categories/{test_category.id}", json=update_data, headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]
        assert data["id"] == str(test_category.id)

    def test_update_category_partial(self, client, org_headers, test_category):
        """Test partially updating a category (only name)."""
        # Arrange
        original_description = test_category.description
        update_data = {
            "name": "Only Name Updated"
        }

        # Act
        response = client.patch(f"/api/v1/material-categories/{test_category.id}", json=update_data, headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == original_description

    def test_update_category_not_found(self, client, org_headers):
        """Test updating non-existent category returns 404."""
        # Arrange
        fake_id = uuid4()
        update_data = {"name": "New Name"}

        # Act
        response = client.patch(f"/api/v1/material-categories/{fake_id}", json=update_data, headers=org_headers)

        # Assert
        assert response.status_code == 404

    def test_update_category_different_org(self, client, auth_headers, test_category, test_organization2):
        """Test updating category from different org returns 404."""
        # Arrange
        org2_headers = {**auth_headers, "X-Organization-ID": str(test_organization2.id)}
        update_data = {"name": "Hacked Name"}

        # Act
        response = client.patch(f"/api/v1/material-categories/{test_category.id}", json=update_data, headers=org2_headers)

        # Assert
        assert response.status_code == 404


class TestDeleteMaterialCategory:
    """Tests for DELETE /api/v1/material-categories/{id}"""

    def test_delete_category_soft_delete(self, client, org_headers, db_session, test_organization):
        """Test soft deleting category sets is_active to False."""
        # Arrange
        category = MaterialCategory(
            id=uuid4(),
            name="Category to Delete",
            organization_id=test_organization.id,
            is_active=True
        )
        db_session.add(category)
        db_session.commit()
        category_id = category.id

        # Act
        response = client.delete(f"/api/v1/material-categories/{category_id}", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False
        assert data["id"] == str(category_id)

        # Verify category still exists in DB but is inactive
        db_session.expire_all()
        deleted_category = db_session.get(MaterialCategory, category_id)
        assert deleted_category is not None
        assert deleted_category.is_active is False

    def test_delete_category_not_found(self, client, org_headers):
        """Test deleting non-existent category returns 404."""
        # Arrange
        fake_id = uuid4()

        # Act
        response = client.delete(f"/api/v1/material-categories/{fake_id}", headers=org_headers)

        # Assert
        assert response.status_code == 404

    def test_delete_category_different_org(self, client, auth_headers, test_category, test_organization2):
        """Test deleting category from different org returns 404."""
        # Arrange
        org2_headers = {**auth_headers, "X-Organization-ID": str(test_organization2.id)}

        # Act
        response = client.delete(f"/api/v1/material-categories/{test_category.id}", headers=org2_headers)

        # Assert
        assert response.status_code == 404
