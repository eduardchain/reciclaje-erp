"""
Comprehensive tests for Third Party CRUD endpoints.
"""
import pytest
from uuid import uuid4

from app.models.third_party import ThirdParty


@pytest.fixture
def test_supplier(db_session, test_organization):
    """Create a test supplier."""
    supplier = ThirdParty(
        id=uuid4(),
        name="Test Supplier",
        identification_number="SUP-001",
        email="supplier@test.com",
        phone="123456789",
        address="Supplier Address",
        is_supplier=True,
        is_customer=False,
        is_investor=False,
        is_provision=False,
        current_balance=0.0,
        organization_id=test_organization.id,
        is_active=True
    )
    db_session.add(supplier)
    db_session.commit()
    db_session.refresh(supplier)
    return supplier


@pytest.fixture
def test_customer(db_session, test_organization):
    """Create a test customer."""
    customer = ThirdParty(
        id=uuid4(),
        name="Test Customer",
        identification_number="CUS-001",
        email="customer@test.com",
        is_supplier=False,
        is_customer=True,
        is_investor=False,
        is_provision=False,
        current_balance=0.0,
        organization_id=test_organization.id,
        is_active=True
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


class TestCreateThirdParty:
    """Tests for POST /api/v1/third-parties"""

    def test_create_supplier_success(self, client, org_headers):
        """Test creating a supplier."""
        # Arrange
        third_party_data = {
            "name": "New Supplier",
            "identification_number": "NEW-SUP-001",
            "email": "newsupplier@test.com",
            "phone": "987654321",
            "address": "New Supplier Address",
            "is_supplier": True,
            "is_customer": False,
            "is_investor": False,
            "is_provision": False
        }

        # Act
        response = client.post("/api/v1/third-parties", json=third_party_data, headers=org_headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == third_party_data["name"]
        assert data["identification_number"] == third_party_data["identification_number"]
        assert data["email"] == third_party_data["email"]
        assert data["is_supplier"] is True
        assert data["is_customer"] is False
        assert data["current_balance"] == 0.0
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data

    def test_create_customer_success(self, client, org_headers):
        """Test creating a customer."""
        # Arrange
        third_party_data = {
            "name": "New Customer",
            "identification_number": "NEW-CUS-001",
            "is_supplier": False,
            "is_customer": True
        }

        # Act
        response = client.post("/api/v1/third-parties", json=third_party_data, headers=org_headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == third_party_data["name"]
        assert data["is_customer"] is True
        assert data["is_supplier"] is False

    def test_create_provision_success(self, client, org_headers):
        """Test creating a provision third party."""
        # Arrange
        third_party_data = {
            "name": "New Provision",
            "identification_number": "NEW-PROV-001",
            "is_provision": True
        }

        # Act
        response = client.post("/api/v1/third-parties", json=third_party_data, headers=org_headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["is_provision"] is True
        assert data["is_supplier"] is False
        assert data["is_customer"] is False

    def test_create_multiple_roles(self, client, org_headers):
        """Test creating third party with multiple roles (supplier + customer)."""
        # Arrange
        third_party_data = {
            "name": "Supplier and Customer",
            "identification_number": "BOTH-001",
            "is_supplier": True,
            "is_customer": True
        }

        # Act
        response = client.post("/api/v1/third-parties", json=third_party_data, headers=org_headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["is_supplier"] is True
        assert data["is_customer"] is True

    def test_create_third_party_minimal_data(self, client, org_headers):
        """Test creating third party with only required fields."""
        # Arrange
        third_party_data = {
            "name": "Minimal Third Party",
            "identification_number": "MIN-001"
        }

        # Act
        response = client.post("/api/v1/third-parties", json=third_party_data, headers=org_headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == third_party_data["name"]
        assert data["is_supplier"] is False  # Default
        assert data["is_customer"] is False  # Default
        assert data["current_balance"] == 0.0  # Default

    def test_create_third_party_invalid_email(self, client, org_headers):
        """Test creating third party with invalid email returns 422."""
        # Arrange
        third_party_data = {
            "name": "Invalid Email",
            "identification_number": "INV-001",
            "email": "not-an-email"
        }

        # Act
        response = client.post("/api/v1/third-parties", json=third_party_data, headers=org_headers)

        # Assert
        assert response.status_code == 422

    def test_create_third_party_without_auth(self, client):
        """Test creating third party without authentication returns 401."""
        # Arrange
        third_party_data = {
            "name": "Unauthorized",
            "identification_number": "UNAUTH-001"
        }

        # Act
        response = client.post("/api/v1/third-parties", json=third_party_data)

        # Assert
        assert response.status_code == 401


class TestGetThirdParty:
    """Tests for GET /api/v1/third-parties/{id}"""

    def test_get_third_party_success(self, client, org_headers, test_supplier):
        """Test successfully retrieving a third party by ID."""
        # Act
        response = client.get(f"/api/v1/third-parties/{test_supplier.id}", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_supplier.id)
        assert data["name"] == test_supplier.name
        assert data["identification_number"] == test_supplier.identification_number
        assert data["is_supplier"] is True
        assert data["is_active"] is True

    def test_get_third_party_not_found(self, client, org_headers):
        """Test getting non-existent third party returns 404."""
        # Arrange
        fake_id = uuid4()

        # Act
        response = client.get(f"/api/v1/third-parties/{fake_id}", headers=org_headers)

        # Assert
        assert response.status_code == 404
        assert "no encontrad" in response.json()["detail"].lower()

    def test_get_third_party_different_org(self, client, auth_headers, test_supplier, test_organization2):
        """Test getting third party from different organization returns 404."""
        # Arrange
        org2_headers = {**auth_headers, "X-Organization-ID": str(test_organization2.id)}

        # Act
        response = client.get(f"/api/v1/third-parties/{test_supplier.id}", headers=org2_headers)

        # Assert
        assert response.status_code == 404


class TestListThirdParties:
    """Tests for GET /api/v1/third-parties"""

    def test_list_third_parties_pagination(self, client, org_headers, db_session, test_organization):
        """Test listing third parties with pagination."""
        # Arrange - Create multiple third parties
        for i in range(5):
            third_party = ThirdParty(
                id=uuid4(),
                name=f"Third Party {i}",
                identification_number=f"TP-{i:03d}",
                organization_id=test_organization.id,
                is_active=True
            )
            db_session.add(third_party)
        db_session.commit()

        # Act
        response = client.get("/api/v1/third-parties?skip=0&limit=3", headers=org_headers)

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

    def test_list_third_parties_search_filter(self, client, org_headers, db_session, test_organization):
        """Test searching third parties by name, identification, or email."""
        # Arrange
        tp1 = ThirdParty(
            id=uuid4(),
            name="Searchable Company",
            identification_number="SEARCH-001",
            email="search@company.com",
            organization_id=test_organization.id,
            is_active=True
        )
        tp2 = ThirdParty(
            id=uuid4(),
            name="Other Company",
            identification_number="OTHER-002",
            email="other@company.com",
            organization_id=test_organization.id,
            is_active=True
        )
        db_session.add_all([tp1, tp2])
        db_session.commit()

        # Act - Search by name
        response = client.get("/api/v1/third-parties?search=Searchable", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Searchable Company"

    def test_list_third_parties_is_active_filter(self, client, org_headers, db_session, test_organization):
        """Test filtering third parties by is_active status."""
        # Arrange
        active_tp = ThirdParty(
            id=uuid4(),
            name="Active TP",
            identification_number="ACTIVE-001",
            organization_id=test_organization.id,
            is_active=True
        )
        inactive_tp = ThirdParty(
            id=uuid4(),
            name="Inactive TP",
            identification_number="INACTIVE-001",
            organization_id=test_organization.id,
            is_active=False
        )
        db_session.add_all([active_tp, inactive_tp])
        db_session.commit()

        # Act - Get only active
        response = client.get("/api/v1/third-parties?is_active=true", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert all(item["is_active"] is True for item in data["items"])

    def test_list_third_parties_organization_isolation(self, client, auth_headers, db_session, test_supplier, test_organization2):
        """Test that users only see third parties from their organization."""
        # Arrange - Create third party in second org
        org2_tp = ThirdParty(
            id=uuid4(),
            name="Org2 Third Party",
            identification_number="ORG2-TP",
            organization_id=test_organization2.id,
            is_active=True
        )
        db_session.add(org2_tp)
        db_session.commit()

        org2_headers = {**auth_headers, "X-Organization-ID": str(test_organization2.id)}

        # Act
        response = client.get("/api/v1/third-parties", headers=org2_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        tp_ids = [item["id"] for item in data["items"]]
        assert str(org2_tp.id) in tp_ids
        assert str(test_supplier.id) not in tp_ids


class TestGetSuppliers:
    """Tests for GET /api/v1/third-parties/suppliers"""

    def test_get_suppliers_only(self, client, org_headers, db_session, test_organization, test_supplier, test_customer):
        """Test filtering to get only suppliers."""
        # Act
        response = client.get("/api/v1/third-parties/suppliers", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert all(item["is_supplier"] is True for item in data["items"])
        supplier_ids = [item["id"] for item in data["items"]]
        assert str(test_supplier.id) in supplier_ids
        assert str(test_customer.id) not in supplier_ids


class TestGetCustomers:
    """Tests for GET /api/v1/third-parties/customers"""

    def test_get_customers_only(self, client, org_headers, db_session, test_organization, test_supplier, test_customer):
        """Test filtering to get only customers."""
        # Act
        response = client.get("/api/v1/third-parties/customers", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert all(item["is_customer"] is True for item in data["items"])
        customer_ids = [item["id"] for item in data["items"]]
        assert str(test_customer.id) in customer_ids
        assert str(test_supplier.id) not in customer_ids


class TestGetProvisions:
    """Tests for GET /api/v1/third-parties/provisions"""

    def test_get_provisions_only(self, client, org_headers, db_session, test_organization):
        """Test filtering to get only provisions."""
        # Arrange
        provision = ThirdParty(
            id=uuid4(),
            name="Test Provision",
            identification_number="PROV-001",
            is_provision=True,
            organization_id=test_organization.id,
            is_active=True
        )
        non_provision = ThirdParty(
            id=uuid4(),
            name="Not Provision",
            identification_number="NOT-PROV-001",
            is_provision=False,
            organization_id=test_organization.id,
            is_active=True
        )
        db_session.add_all([provision, non_provision])
        db_session.commit()

        # Act
        response = client.get("/api/v1/third-parties/provisions", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert all(item["is_provision"] is True for item in data["items"])
        provision_ids = [item["id"] for item in data["items"]]
        assert str(provision.id) in provision_ids
        assert str(non_provision.id) not in provision_ids


class TestUpdateThirdParty:
    """Tests for PATCH /api/v1/third-parties/{id}"""

    def test_update_third_party_success(self, client, org_headers, test_supplier):
        """Test successfully updating a third party."""
        # Arrange
        update_data = {
            "name": "Updated Supplier Name",
            "email": "updated@supplier.com",
            "phone": "999888777"
        }

        # Act
        response = client.patch(f"/api/v1/third-parties/{test_supplier.id}", json=update_data, headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["email"] == update_data["email"]
        assert data["phone"] == update_data["phone"]
        assert data["identification_number"] == test_supplier.identification_number  # Unchanged

    def test_update_third_party_change_roles(self, client, org_headers, test_supplier):
        """Test updating third party roles."""
        # Arrange
        update_data = {
            "is_supplier": True,
            "is_customer": True  # Add customer role
        }

        # Act
        response = client.patch(f"/api/v1/third-parties/{test_supplier.id}", json=update_data, headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["is_supplier"] is True
        assert data["is_customer"] is True

    def test_update_third_party_not_found(self, client, org_headers):
        """Test updating non-existent third party returns 404."""
        # Arrange
        fake_id = uuid4()
        update_data = {"name": "New Name"}

        # Act
        response = client.patch(f"/api/v1/third-parties/{fake_id}", json=update_data, headers=org_headers)

        # Assert
        assert response.status_code == 404


class TestDeleteThirdParty:
    """Tests for DELETE /api/v1/third-parties/{id}"""

    def test_delete_third_party_with_balance_fails(self, client, org_headers, db_session, test_organization):
        """Test deleting third party with balance != 0 returns 400."""
        # Arrange - Create third party with balance
        tp_with_balance = ThirdParty(
            id=uuid4(),
            name="TP with Balance",
            identification_number="BALANCE-001",
            current_balance=100.0,  # Has balance
            organization_id=test_organization.id,
            is_active=True
        )
        db_session.add(tp_with_balance)
        db_session.commit()

        # Act
        response = client.delete(f"/api/v1/third-parties/{tp_with_balance.id}", headers=org_headers)

        # Assert
        assert response.status_code == 400
        assert "saldo pendiente" in response.json()["detail"].lower()

    def test_delete_third_party_with_zero_balance(self, client, org_headers, db_session, test_organization):
        """Test soft deleting third party with balance = 0."""
        # Arrange
        tp = ThirdParty(
            id=uuid4(),
            name="TP to Delete",
            identification_number="DELETE-001",
            current_balance=0.0,
            organization_id=test_organization.id,
            is_active=True
        )
        db_session.add(tp)
        db_session.commit()
        tp_id = tp.id

        # Act
        response = client.delete(f"/api/v1/third-parties/{tp_id}", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False
        assert data["id"] == str(tp_id)

        # Verify still exists but is inactive
        db_session.expire_all()
        deleted_tp = db_session.get(ThirdParty, tp_id)
        assert deleted_tp is not None
        assert deleted_tp.is_active is False

    def test_delete_third_party_not_found(self, client, org_headers):
        """Test deleting non-existent third party returns 404."""
        # Arrange
        fake_id = uuid4()

        # Act
        response = client.delete(f"/api/v1/third-parties/{fake_id}", headers=org_headers)

        # Assert
        assert response.status_code == 404


class TestUpdateThirdPartyBalance:
    """Tests for POST /api/v1/third-parties/{id}/balance"""

    def test_update_balance_positive_delta(self, client, org_headers, test_supplier, db_session):
        """Test increasing third party balance."""
        # Arrange
        initial_balance = float(test_supplier.current_balance)
        balance_update = {"amount_delta": 100.0}

        # Act
        response = client.post(f"/api/v1/third-parties/{test_supplier.id}/balance", json=balance_update, headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["current_balance"] == initial_balance + 100.0

        # Verify in DB
        db_session.expire_all()
        updated_third_party = db_session.get(ThirdParty, test_supplier.id)
        assert float(updated_third_party.current_balance) == initial_balance + 100.0

    def test_update_balance_negative_delta(self, client, org_headers, db_session, test_organization):
        """Test decreasing third party balance."""
        # Arrange - Create third party with positive balance
        tp = ThirdParty(
            id=uuid4(),
            name="TP with Balance",
            identification_number="BAL-001",
            current_balance=1000.0,
            organization_id=test_organization.id,
            is_active=True
        )
        db_session.add(tp)
        db_session.commit()

        balance_update = {"amount_delta": -300.0}

        # Act
        response = client.post(f"/api/v1/third-parties/{tp.id}/balance", json=balance_update, headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["current_balance"] == 700.0

    def test_update_balance_to_negative(self, client, org_headers, test_supplier, db_session):
        """Test balance can become negative (debt allowed)."""
        # Arrange
        balance_update = {"amount_delta": -500.0}  # Create debt

        # Act
        response = client.post(f"/api/v1/third-parties/{test_supplier.id}/balance", json=balance_update, headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["current_balance"] < 0  # Negative balance is allowed

    def test_update_balance_third_party_not_found(self, client, org_headers):
        """Test updating balance of non-existent third party returns 404."""
        # Arrange
        fake_id = uuid4()
        balance_update = {"amount_delta": 100.0}

        # Act
        response = client.post(f"/api/v1/third-parties/{fake_id}/balance", json=balance_update, headers=org_headers)

        # Assert
        assert response.status_code == 404
