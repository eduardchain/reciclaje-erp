"""
Comprehensive tests for Material CRUD endpoints.
"""
import pytest
from uuid import uuid4

from app.models.material import Material, MaterialCategory
from app.models.business_unit import BusinessUnit


@pytest.fixture
def test_category(db_session, test_organization):
    """Create a test material category."""
    category = MaterialCategory(
        id=uuid4(),
        name="Raw Materials",
        description="Raw materials for production",
        organization_id=test_organization.id,
        is_active=True
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


@pytest.fixture
def test_business_unit(db_session, test_organization):
    """Create a test business unit."""
    business_unit = BusinessUnit(
        id=uuid4(),
        name="Main Warehouse",
        organization_id=test_organization.id,
        is_active=True
    )
    db_session.add(business_unit)
    db_session.commit()
    db_session.refresh(business_unit)
    return business_unit


@pytest.fixture
def test_material(db_session, test_organization, test_category, test_business_unit):
    """Create a test material."""
    material = Material(
        id=uuid4(),
        code="MAT001",
        name="Test Material",
        description="A test material",
        category_id=test_category.id,
        business_unit_id=test_business_unit.id,
        default_unit="kg",
        current_stock=10.0,
        current_average_cost=100.0,
        organization_id=test_organization.id,
        is_active=True
    )
    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)
    return material


class TestCreateMaterial:
    """Tests for POST /api/v1/materials"""

    def test_create_material_success(self, client, org_headers, test_category, test_business_unit):
        """Test successful material creation."""
        # Arrange
        material_data = {
            "code": "MAT-NEW-001",
            "name": "New Material",
            "description": "A newly created material",
            "category_id": str(test_category.id),
            "business_unit_id": str(test_business_unit.id),
            "default_unit": "kg"
        }

        # Act
        response = client.post("/api/v1/materials", json=material_data, headers=org_headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == material_data["code"]
        assert data["name"] == material_data["name"]
        assert data["description"] == material_data["description"]
        assert data["category_id"] == material_data["category_id"]
        assert data["business_unit_id"] == material_data["business_unit_id"]
        assert data["current_stock"] == 0.0
        assert data["current_average_cost"] == 0.0
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data

    def test_create_material_duplicate_code(self, client, org_headers, test_material, test_category, test_business_unit):
        """Test creating material with duplicate code returns 400."""
        # Arrange
        material_data = {
            "code": test_material.code,  # Duplicate code
            "name": "Another Material",
            "category_id": str(test_category.id),
            "business_unit_id": str(test_business_unit.id),
            "default_unit": "kg"
        }

        # Act
        response = client.post("/api/v1/materials", json=material_data, headers=org_headers)

        # Assert
        assert response.status_code == 400
        assert "ya existe" in response.json()["detail"].lower()

    def test_create_material_invalid_business_unit(self, client, org_headers, test_category):
        """Test creating material with business unit from different org returns 400."""
        # Arrange
        fake_business_unit_id = str(uuid4())
        material_data = {
            "code": "MAT-INVALID",
            "name": "Invalid Material",
            "category_id": str(test_category.id),
            "business_unit_id": fake_business_unit_id,
            "default_unit": "kg"
        }

        # Act
        response = client.post("/api/v1/materials", json=material_data, headers=org_headers)

        # Assert
        assert response.status_code == 400
        assert "unidad de negocio" in response.json()["detail"].lower()

    def test_create_material_invalid_category(self, client, org_headers, test_business_unit):
        """Test creating material with category from different org returns 400."""
        # Arrange
        fake_category_id = str(uuid4())
        material_data = {
            "code": "MAT-INVALID-CAT",
            "name": "Invalid Category Material",
            "category_id": fake_category_id,
            "business_unit_id": str(test_business_unit.id),
            "default_unit": "kg"
        }

        # Act
        response = client.post("/api/v1/materials", json=material_data, headers=org_headers)

        # Assert
        assert response.status_code == 400
        assert "categoria" in response.json()["detail"].lower()

    def test_create_material_without_auth(self, client, test_category, test_business_unit):
        """Test creating material without authentication returns 401."""
        # Arrange
        material_data = {
            "code": "MAT-NOAUTH",
            "name": "No Auth Material",
            "category_id": str(test_category.id),
            "business_unit_id": str(test_business_unit.id),
            "default_unit": "kg"
        }

        # Act
        response = client.post("/api/v1/materials", json=material_data)

        # Assert
        assert response.status_code == 401


class TestGetMaterial:
    """Tests for GET /api/v1/materials/{id}"""

    def test_get_material_success(self, client, org_headers, test_material):
        """Test successfully retrieving a material by ID."""
        # Act
        response = client.get(f"/api/v1/materials/{test_material.id}", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_material.id)
        assert data["code"] == test_material.code
        assert data["name"] == test_material.name
        assert data["current_stock"] == test_material.current_stock
        assert data["is_active"] is True

    def test_get_material_not_found(self, client, org_headers):
        """Test getting non-existent material returns 404."""
        # Arrange
        fake_id = uuid4()

        # Act
        response = client.get(f"/api/v1/materials/{fake_id}", headers=org_headers)

        # Assert
        assert response.status_code == 404
        assert "no encontrad" in response.json()["detail"].lower()

    def test_get_material_different_org(self, client, auth_headers, test_material, test_organization2):
        """Test getting material from different organization returns 404."""
        # Arrange
        org2_headers = {**auth_headers, "X-Organization-ID": str(test_organization2.id)}

        # Act
        response = client.get(f"/api/v1/materials/{test_material.id}", headers=org2_headers)

        # Assert
        assert response.status_code == 404


class TestGetMaterialByCode:
    """Tests for GET /api/v1/materials/code/{code}"""

    def test_get_material_by_code_success(self, client, org_headers, test_material):
        """Test successfully retrieving a material by code."""
        # Act
        response = client.get(f"/api/v1/materials/code/{test_material.code}", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_material.id)
        assert data["code"] == test_material.code
        assert data["name"] == test_material.name

    def test_get_material_by_code_not_found(self, client, org_headers):
        """Test getting material by non-existent code returns 404."""
        # Act
        response = client.get("/api/v1/materials/code/NONEXISTENT", headers=org_headers)

        # Assert
        assert response.status_code == 404


class TestListMaterials:
    """Tests for GET /api/v1/materials"""

    def test_list_materials_pagination(self, client, org_headers, db_session, test_organization, test_category, test_business_unit):
        """Test listing materials with pagination."""
        # Arrange - Create multiple materials
        materials = []
        for i in range(5):
            material = Material(
                id=uuid4(),
                code=f"MAT-{i:03d}",
                name=f"Material {i}",
                category_id=test_category.id,
                business_unit_id=test_business_unit.id,
                default_unit="kg",
                organization_id=test_organization.id,
                is_active=True
            )
            db_session.add(material)
            materials.append(material)
        db_session.commit()

        # Act
        response = client.get("/api/v1/materials?skip=0&limit=3", headers=org_headers)

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

    def test_list_materials_search_filter(self, client, org_headers, db_session, test_organization, test_category, test_business_unit):
        """Test searching materials by code, name, or description."""
        # Arrange
        material1 = Material(
            id=uuid4(),
            code="SEARCH-001",
            name="Searchable Material",
            description="Find me",
            category_id=test_category.id,
            business_unit_id=test_business_unit.id,
            default_unit="kg",
            organization_id=test_organization.id,
            is_active=True
        )
        material2 = Material(
            id=uuid4(),
            code="OTHER-002",
            name="Other Material",
            description="Not this one",
            category_id=test_category.id,
            business_unit_id=test_business_unit.id,
            default_unit="kg",
            organization_id=test_organization.id,
            is_active=True
        )
        db_session.add_all([material1, material2])
        db_session.commit()

        # Act
        response = client.get("/api/v1/materials?search=Searchable", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Searchable Material"

    def test_list_materials_is_active_filter(self, client, org_headers, db_session, test_organization, test_category, test_business_unit):
        """Test filtering materials by is_active status."""
        # Arrange
        active_material = Material(
            id=uuid4(),
            code="ACTIVE-001",
            name="Active Material",
            category_id=test_category.id,
            business_unit_id=test_business_unit.id,
            default_unit="kg",
            organization_id=test_organization.id,
            is_active=True
        )
        inactive_material = Material(
            id=uuid4(),
            code="INACTIVE-001",
            name="Inactive Material",
            category_id=test_category.id,
            business_unit_id=test_business_unit.id,
            default_unit="kg",
            organization_id=test_organization.id,
            is_active=False
        )
        db_session.add_all([active_material, inactive_material])
        db_session.commit()

        # Act - Get only active
        response = client.get("/api/v1/materials?is_active=true", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert all(item["is_active"] is True for item in data["items"])

        # Act - Get only inactive
        response = client.get("/api/v1/materials?is_active=false", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert all(item["is_active"] is False for item in data["items"])

    def test_list_materials_sorting(self, client, org_headers, db_session, test_organization, test_category, test_business_unit):
        """Test sorting materials."""
        # Arrange
        for i, name in enumerate(["Zebra", "Alpha", "Beta"]):
            material = Material(
                id=uuid4(),
                code=f"SORT-{i:03d}",
                name=name,
                category_id=test_category.id,
                business_unit_id=test_business_unit.id,
                default_unit="kg",
                organization_id=test_organization.id,
                is_active=True
            )
            db_session.add(material)
        db_session.commit()

        # Act - Sort by name ascending
        response = client.get("/api/v1/materials?sort_by=name&sort_order=asc", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        names = [item["name"] for item in data["items"]]
        assert names == sorted(names)

    def test_list_materials_organization_isolation(self, client, auth_headers, db_session, test_material, test_organization2, test_category, test_business_unit):
        """Test that users only see materials from their organization."""
        # Arrange - Create material in second org
        org2_category = MaterialCategory(
            id=uuid4(),
            name="Org2 Category",
            organization_id=test_organization2.id,
            is_active=True
        )
        org2_business_unit = BusinessUnit(
            id=uuid4(),
            name="Org2 Business Unit",
            organization_id=test_organization2.id,
            is_active=True
        )
        db_session.add_all([org2_category, org2_business_unit])
        db_session.commit()

        org2_material = Material(
            id=uuid4(),
            code="ORG2-MAT",
            name="Org2 Material",
            category_id=org2_category.id,
            business_unit_id=org2_business_unit.id,
            default_unit="kg",
            organization_id=test_organization2.id,
            is_active=True
        )
        db_session.add(org2_material)
        db_session.commit()

        org2_headers = {**auth_headers, "X-Organization-ID": str(test_organization2.id)}

        # Act
        response = client.get("/api/v1/materials", headers=org2_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        material_ids = [item["id"] for item in data["items"]]
        assert str(org2_material.id) in material_ids
        assert str(test_material.id) not in material_ids


class TestUpdateMaterial:
    """Tests for PATCH /api/v1/materials/{id}"""

    def test_update_material_success(self, client, org_headers, test_material):
        """Test successfully updating a material."""
        # Arrange
        update_data = {
            "name": "Updated Material Name",
            "description": "Updated description"
        }

        # Act
        response = client.patch(f"/api/v1/materials/{test_material.id}", json=update_data, headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]
        assert data["code"] == test_material.code  # Unchanged

    def test_update_material_code_duplicate(self, client, org_headers, db_session, test_organization, test_material, test_category, test_business_unit):
        """Test updating material code to duplicate returns 400."""
        # Arrange - Create another material
        another_material = Material(
            id=uuid4(),
            code="ANOTHER-001",
            name="Another Material",
            category_id=test_category.id,
            business_unit_id=test_business_unit.id,
            default_unit="kg",
            organization_id=test_organization.id,
            is_active=True
        )
        db_session.add(another_material)
        db_session.commit()

        update_data = {"code": "ANOTHER-001"}  # Duplicate

        # Act
        response = client.patch(f"/api/v1/materials/{test_material.id}", json=update_data, headers=org_headers)

        # Assert
        assert response.status_code == 400
        assert "ya existe" in response.json()["detail"].lower()

    def test_update_material_not_found(self, client, org_headers):
        """Test updating non-existent material returns 404."""
        # Arrange
        fake_id = uuid4()
        update_data = {"name": "New Name"}

        # Act
        response = client.patch(f"/api/v1/materials/{fake_id}", json=update_data, headers=org_headers)

        # Assert
        assert response.status_code == 404


class TestDeleteMaterial:
    """Tests for DELETE /api/v1/materials/{id}"""

    def test_delete_material_with_stock_fails(self, client, org_headers, test_material):
        """Test deleting material with stock > 0 returns 400."""
        # Assert precondition
        assert test_material.current_stock > 0

        # Act
        response = client.delete(f"/api/v1/materials/{test_material.id}", headers=org_headers)

        # Assert
        assert response.status_code == 400
        assert "stock" in response.json()["detail"].lower()

    def test_delete_material_soft_delete(self, client, org_headers, db_session, test_organization, test_category, test_business_unit):
        """Test soft deleting material sets is_active to False."""
        # Arrange - Create material with zero stock
        material = Material(
            id=uuid4(),
            code="DELETE-ME",
            name="Material to Delete",
            category_id=test_category.id,
            business_unit_id=test_business_unit.id,
            default_unit="kg",
            current_stock=0.0,
            organization_id=test_organization.id,
            is_active=True
        )
        db_session.add(material)
        db_session.commit()
        material_id = material.id

        # Act
        response = client.delete(f"/api/v1/materials/{material_id}", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False
        assert data["id"] == str(material_id)

        # Verify material still exists in DB but is inactive
        db_session.expire_all()
        deleted_material = db_session.get(Material, material_id)
        assert deleted_material is not None
        assert deleted_material.is_active is False

    def test_delete_material_not_found(self, client, org_headers):
        """Test deleting non-existent material returns 404."""
        # Arrange
        fake_id = uuid4()

        # Act
        response = client.delete(f"/api/v1/materials/{fake_id}", headers=org_headers)

        # Assert
        assert response.status_code == 404


class TestUpdateMaterialStock:
    """Tests for POST /api/v1/materials/{id}/stock"""

    def test_update_stock_positive_delta(self, client, org_headers, test_material, db_session):
        """Test increasing material stock."""
        # Arrange
        initial_stock = float(test_material.current_stock)
        stock_update = {"quantity_delta": 5.0}

        # Act
        response = client.post(f"/api/v1/materials/{test_material.id}/stock", json=stock_update, headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["current_stock"] == initial_stock + 5.0

        # Verify in DB
        db_session.expire_all()
        updated_material = db_session.get(Material, test_material.id)
        assert float(updated_material.current_stock) == initial_stock + 5.0

    def test_update_stock_negative_delta(self, client, org_headers, test_material, db_session):
        """Test decreasing material stock."""
        # Arrange
        initial_stock = float(test_material.current_stock)
        stock_update = {"quantity_delta": -3.0}

        # Act
        response = client.post(f"/api/v1/materials/{test_material.id}/stock", json=stock_update, headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["current_stock"] == initial_stock - 3.0

        # Verify in DB
        db_session.expire_all()
        updated_material = db_session.get(Material, test_material.id)
        assert float(updated_material.current_stock) == initial_stock - 3.0

    def test_update_stock_below_zero_fails(self, client, org_headers, test_material):
        """Test updating stock to negative value returns 400."""
        # Arrange
        stock_update = {"quantity_delta": -1000.0}  # More than current stock

        # Act
        response = client.post(f"/api/v1/materials/{test_material.id}/stock", json=stock_update, headers=org_headers)

        # Assert
        assert response.status_code == 400
        assert "stock insuficiente" in response.json()["detail"].lower()

    def test_update_stock_to_exactly_zero(self, client, org_headers, test_material, db_session):
        """Test updating stock to exactly zero."""
        # Arrange
        initial_stock = float(test_material.current_stock)
        stock_update = {"quantity_delta": -initial_stock}

        # Act
        response = client.post(f"/api/v1/materials/{test_material.id}/stock", json=stock_update, headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["current_stock"] == 0.0

        # Verify in DB
        db_session.expire_all()
        updated_material = db_session.get(Material, test_material.id)
        assert float(updated_material.current_stock) == 0.0

    def test_update_stock_material_not_found(self, client, org_headers):
        """Test updating stock of non-existent material returns 404."""
        # Arrange
        fake_id = uuid4()
        stock_update = {"quantity_delta": 10.0}

        # Act
        response = client.post(f"/api/v1/materials/{fake_id}/stock", json=stock_update, headers=org_headers)

        # Assert
        assert response.status_code == 404
