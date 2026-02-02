"""
Comprehensive tests for Purchase API endpoints.

Tests all 8 endpoints:
1. POST /api/v1/purchases - Create purchase
2. GET /api/v1/purchases - List purchases
3. GET /api/v1/purchases/pending - List pending
4. GET /api/v1/purchases/by-number/{number} - Get by number
5. GET /api/v1/purchases/supplier/{id} - List by supplier
6. GET /api/v1/purchases/{id} - Get by ID
7. PATCH /api/v1/purchases/{id}/liquidate - Liquidate
8. PATCH /api/v1/purchases/{id}/cancel - Cancel
"""
import pytest
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from app.models import (
    ThirdParty,
    Material,
    Warehouse,
    MoneyAccount,
    Purchase,
    MaterialCategory,
    BusinessUnit,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def test_supplier(db_session, test_organization):
    """Create a test supplier."""
    supplier = ThirdParty(
        id=uuid4(),
        name="Test Supplier Inc.",
        identification_number="12345678",
        is_supplier=True,
        is_customer=False,
        current_balance=Decimal("0.00"),
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(supplier)
    db_session.commit()
    db_session.refresh(supplier)
    return supplier


@pytest.fixture
def test_supplier2(db_session, test_organization):
    """Create a second test supplier."""
    supplier = ThirdParty(
        id=uuid4(),
        name="Second Supplier LLC",
        identification_number="87654321",
        is_supplier=True,
        is_customer=False,
        current_balance=Decimal("0.00"),
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(supplier)
    db_session.commit()
    db_session.refresh(supplier)
    return supplier


@pytest.fixture
def test_category(db_session, test_organization):
    """Create a test material category."""
    category = MaterialCategory(
        id=uuid4(),
        name="Metals",
        organization_id=test_organization.id,
        is_active=True,
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
        name="Main Unit",
        organization_id=test_organization.id,
        is_active=True,
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
        code="COPPER-001",
        name="Copper Scrap",
        category_id=test_category.id,
        business_unit_id=test_business_unit.id,
        default_unit="kg",
        current_stock=Decimal("0.0000"),
        current_average_cost=Decimal("0.0000"),
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)
    return material


@pytest.fixture
def test_warehouse(db_session, test_organization):
    """Create a test warehouse."""
    warehouse = Warehouse(
        id=uuid4(),
        name="Main Warehouse",
        address="123 Test Street",
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(warehouse)
    db_session.commit()
    db_session.refresh(warehouse)
    return warehouse


@pytest.fixture
def test_money_account(db_session, test_organization):
    """Create a test money account with balance."""
    account = MoneyAccount(
        id=uuid4(),
        name="Cash Account",
        account_type="cash",
        current_balance=Decimal("100000.00"),
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


@pytest.fixture
def test_purchase(db_session, test_organization, test_supplier, test_material, test_warehouse):
    """Create a test purchase (registered status)."""
    from app.schemas.purchase import PurchaseCreate, PurchaseLineCreate
    from app.services.purchase import purchase as purchase_service
    
    purchase_data = PurchaseCreate(
        supplier_id=test_supplier.id,
        date=datetime.now(),
        notes="Test purchase",
        lines=[
            PurchaseLineCreate(
                material_id=test_material.id,
                quantity=Decimal("100.0"),
                unit_price=Decimal("50.00"),
                warehouse_id=test_warehouse.id,
            )
        ],
        auto_liquidate=False,
    )
    
    purchase = purchase_service.create(
        db=db_session,
        obj_in=purchase_data,
        organization_id=test_organization.id,
    )
    
    return purchase


# ============================================================================
# Test Classes
# ============================================================================

class TestCreatePurchase:
    """Tests for POST /api/v1/purchases"""
    
    def test_create_purchase_2step_workflow(
        self,
        client,
        org_headers,
        test_supplier,
        test_material,
        test_warehouse,
    ):
        """Test creating a purchase with 2-step workflow (auto_liquidate=False)."""
        # Arrange
        purchase_data = {
            "supplier_id": str(test_supplier.id),
            "date": datetime.now().isoformat(),
            "notes": "Test purchase 2-step",
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 50.0,
                    "unit_price": 100.00,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
            "auto_liquidate": False,
        }
        
        # Act
        response = client.post("/api/v1/purchases", json=purchase_data, headers=org_headers)
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["purchase_number"] == 1
        assert data["status"] == "registered"
        assert data["total_amount"] == 5000.0  # 50 * 100
        assert data["supplier_name"] == test_supplier.name
        assert len(data["lines"]) == 1
        assert float(data["lines"][0]["quantity"]) == 50.0  # Quantity comes as string from Decimal
        assert data["lines"][0]["material_code"] == "COPPER-001"
        assert "id" in data
        assert "created_at" in data
    
    def test_create_purchase_1step_workflow(
        self,
        client,
        org_headers,
        test_supplier,
        test_material,
        test_warehouse,
        test_money_account,
    ):
        """Test creating a purchase with 1-step workflow (auto_liquidate=True)."""
        # Arrange
        purchase_data = {
            "supplier_id": str(test_supplier.id),
            "date": datetime.now().isoformat(),
            "notes": "Test purchase 1-step",
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 20.0,
                    "unit_price": 75.00,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
            "auto_liquidate": True,
            "payment_account_id": str(test_money_account.id),
        }
        
        # Act
        response = client.post("/api/v1/purchases", json=purchase_data, headers=org_headers)
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "paid"
        assert data["total_amount"] == 1500.0  # 20 * 75
        assert data["payment_account_id"] == str(test_money_account.id)
        assert data["payment_account_name"] == "Cash Account"
    
    def test_create_purchase_auto_liquidate_without_account_fails(
        self,
        client,
        org_headers,
        test_supplier,
        test_material,
        test_warehouse,
    ):
        """Test that auto_liquidate=True without payment_account_id fails validation."""
        # Arrange
        purchase_data = {
            "supplier_id": str(test_supplier.id),
            "date": datetime.now().isoformat(),
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 10.0,
                    "unit_price": 50.00,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
            "auto_liquidate": True,
            # Missing payment_account_id
        }
        
        # Act
        response = client.post("/api/v1/purchases", json=purchase_data, headers=org_headers)
        
        # Assert
        assert response.status_code == 422  # Validation error
    
    def test_create_purchase_without_auth_fails(
        self,
        client,
        test_supplier,
        test_material,
        test_warehouse,
    ):
        """Test that creating purchase without authentication fails."""
        # Arrange
        purchase_data = {
            "supplier_id": str(test_supplier.id),
            "date": datetime.now().isoformat(),
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 10.0,
                    "unit_price": 50.00,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
            "auto_liquidate": False,
        }
        
        # Act
        response = client.post("/api/v1/purchases", json=purchase_data)
        
        # Assert
        assert response.status_code == 401
    
    def test_create_purchase_multiple_lines(
        self,
        client,
        org_headers,
        test_supplier,
        test_material,
        test_warehouse,
        db_session,
        test_organization,
        test_category,
        test_business_unit,
    ):
        """Test creating purchase with multiple lines."""
        # Create second material
        material2 = Material(
            id=uuid4(),
            code="ALUMINUM-001",
            name="Aluminum Scrap",
            category_id=test_category.id,
            business_unit_id=test_business_unit.id,
            default_unit="kg",
            current_stock=Decimal("0.0000"),
            current_average_cost=Decimal("0.0000"),
            organization_id=test_organization.id,
            is_active=True,
        )
        db_session.add(material2)
        db_session.commit()
        
        # Arrange
        purchase_data = {
            "supplier_id": str(test_supplier.id),
            "date": datetime.now().isoformat(),
            "notes": "Multi-line purchase",
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 100.0,
                    "unit_price": 50.00,
                    "warehouse_id": str(test_warehouse.id),
                },
                {
                    "material_id": str(material2.id),
                    "quantity": 200.0,
                    "unit_price": 30.00,
                    "warehouse_id": str(test_warehouse.id),
                },
            ],
            "auto_liquidate": False,
        }
        
        # Act
        response = client.post("/api/v1/purchases", json=purchase_data, headers=org_headers)
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert len(data["lines"]) == 2
        assert data["total_amount"] == 11000.0  # (100*50) + (200*30)


class TestListPurchases:
    """Tests for GET /api/v1/purchases"""
    
    def test_list_purchases_empty(self, client, org_headers):
        """Test listing purchases when none exist."""
        # Act
        response = client.get("/api/v1/purchases", headers=org_headers)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["skip"] == 0
        assert data["limit"] == 100
    
    def test_list_purchases_with_data(
        self,
        client,
        org_headers,
        test_purchase,
    ):
        """Test listing purchases with existing data."""
        # Act
        response = client.get("/api/v1/purchases", headers=org_headers)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(test_purchase.id)
    
    def test_list_purchases_with_status_filter(
        self,
        client,
        org_headers,
        test_purchase,
    ):
        """Test listing purchases filtered by status."""
        # Act - Filter by registered
        response = client.get(
            "/api/v1/purchases",
            params={"status": "registered"},
            headers=org_headers,
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        
        # Act - Filter by paid (should be empty)
        response = client.get(
            "/api/v1/purchases",
            params={"status": "paid"},
            headers=org_headers,
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
    
    def test_list_purchases_with_supplier_filter(
        self,
        client,
        org_headers,
        test_purchase,
        test_supplier,
        test_supplier2,
    ):
        """Test listing purchases filtered by supplier."""
        # Act - Filter by test_supplier (has purchase)
        response = client.get(
            "/api/v1/purchases",
            params={"supplier_id": str(test_supplier.id)},
            headers=org_headers,
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        
        # Act - Filter by test_supplier2 (no purchases)
        response = client.get(
            "/api/v1/purchases",
            params={"supplier_id": str(test_supplier2.id)},
            headers=org_headers,
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
    
    def test_list_purchases_with_search(
        self,
        client,
        org_headers,
        test_purchase,
    ):
        """Test listing purchases with search."""
        # Act - Search by purchase number
        response = client.get(
            "/api/v1/purchases",
            params={"search": "1"},
            headers=org_headers,
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        
        # Act - Search by supplier name
        response = client.get(
            "/api/v1/purchases",
            params={"search": "Test Supplier"},
            headers=org_headers,
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
    
    def test_list_purchases_pagination(
        self,
        client,
        org_headers,
        test_purchase,
    ):
        """Test listing purchases with pagination."""
        # Act
        response = client.get(
            "/api/v1/purchases",
            params={"skip": 0, "limit": 10},
            headers=org_headers,
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["skip"] == 0
        assert data["limit"] == 10


class TestListPendingPurchases:
    """Tests for GET /api/v1/purchases/pending"""
    
    def test_list_pending_purchases(
        self,
        client,
        org_headers,
        test_purchase,
    ):
        """Test listing pending purchases (status='registered')."""
        # Act
        response = client.get("/api/v1/purchases/pending", headers=org_headers)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "registered"


class TestGetPurchaseByNumber:
    """Tests for GET /api/v1/purchases/by-number/{purchase_number}"""
    
    def test_get_purchase_by_number_success(
        self,
        client,
        org_headers,
        test_purchase,
    ):
        """Test getting purchase by number successfully."""
        # Act
        response = client.get(
            f"/api/v1/purchases/by-number/{test_purchase.purchase_number}",
            headers=org_headers,
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_purchase.id)
        assert data["purchase_number"] == test_purchase.purchase_number
    
    def test_get_purchase_by_number_not_found(
        self,
        client,
        org_headers,
    ):
        """Test getting non-existent purchase number returns 404."""
        # Act
        response = client.get(
            "/api/v1/purchases/by-number/99999",
            headers=org_headers,
        )
        
        # Assert
        assert response.status_code == 404


class TestListPurchasesBySupplier:
    """Tests for GET /api/v1/purchases/supplier/{supplier_id}"""
    
    def test_list_purchases_by_supplier(
        self,
        client,
        org_headers,
        test_purchase,
        test_supplier,
    ):
        """Test listing purchases by supplier."""
        # Act
        response = client.get(
            f"/api/v1/purchases/supplier/{test_supplier.id}",
            headers=org_headers,
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["supplier_id"] == str(test_supplier.id)


class TestGetPurchaseById:
    """Tests for GET /api/v1/purchases/{purchase_id}"""
    
    def test_get_purchase_by_id_success(
        self,
        client,
        org_headers,
        test_purchase,
    ):
        """Test getting purchase by ID successfully."""
        # Act
        response = client.get(
            f"/api/v1/purchases/{test_purchase.id}",
            headers=org_headers,
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_purchase.id)
        assert data["purchase_number"] == test_purchase.purchase_number
        assert "lines" in data
        assert len(data["lines"]) > 0
    
    def test_get_purchase_by_id_not_found(
        self,
        client,
        org_headers,
    ):
        """Test getting non-existent purchase returns 404."""
        # Act
        response = client.get(
            f"/api/v1/purchases/{uuid4()}",
            headers=org_headers,
        )
        
        # Assert
        assert response.status_code == 404


class TestLiquidatePurchase:
    """Tests for PATCH /api/v1/purchases/{purchase_id}/liquidate"""
    
    def test_liquidate_purchase_success(
        self,
        client,
        org_headers,
        test_purchase,
        test_money_account,
    ):
        """Test liquidating a registered purchase successfully."""
        # Arrange
        liquidate_data = {
            "payment_account_id": str(test_money_account.id),
        }
        
        # Act
        response = client.patch(
            f"/api/v1/purchases/{test_purchase.id}/liquidate",
            json=liquidate_data,
            headers=org_headers,
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "paid"
        assert data["payment_account_id"] == str(test_money_account.id)
    
    def test_liquidate_purchase_already_paid_fails(
        self,
        client,
        org_headers,
        test_purchase,
        test_money_account,
        db_session,
    ):
        """Test that liquidating an already paid purchase fails."""
        # Arrange - Liquidate first time
        liquidate_data = {
            "payment_account_id": str(test_money_account.id),
        }
        client.patch(
            f"/api/v1/purchases/{test_purchase.id}/liquidate",
            json=liquidate_data,
            headers=org_headers,
        )
        
        # Act - Try to liquidate again
        response = client.patch(
            f"/api/v1/purchases/{test_purchase.id}/liquidate",
            json=liquidate_data,
            headers=org_headers,
        )
        
        # Assert
        assert response.status_code == 400
    
    def test_liquidate_purchase_insufficient_funds_fails(
        self,
        client,
        org_headers,
        test_purchase,
        db_session,
        test_organization,
    ):
        """Test that liquidating with insufficient funds fails."""
        # Arrange - Create account with low balance
        poor_account = MoneyAccount(
            id=uuid4(),
            name="Poor Account",
            account_type="cash",
            current_balance=Decimal("10.00"),  # Not enough for purchase
            organization_id=test_organization.id,
            is_active=True,
        )
        db_session.add(poor_account)
        db_session.commit()
        
        liquidate_data = {
            "payment_account_id": str(poor_account.id),
        }
        
        # Act
        response = client.patch(
            f"/api/v1/purchases/{test_purchase.id}/liquidate",
            json=liquidate_data,
            headers=org_headers,
        )
        
        # Assert
        assert response.status_code == 400
        assert "insufficient funds" in response.json()["detail"].lower()


class TestCancelPurchase:
    """Tests for PATCH /api/v1/purchases/{purchase_id}/cancel"""
    
    def test_cancel_purchase_success(
        self,
        client,
        org_headers,
        test_purchase,
    ):
        """Test canceling a registered purchase successfully."""
        # Act
        response = client.patch(
            f"/api/v1/purchases/{test_purchase.id}/cancel",
            headers=org_headers,
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
    
    def test_cancel_paid_purchase_fails(
        self,
        client,
        org_headers,
        test_purchase,
        test_money_account,
    ):
        """Test that canceling a paid purchase fails."""
        # Arrange - Liquidate first
        liquidate_data = {
            "payment_account_id": str(test_money_account.id),
        }
        client.patch(
            f"/api/v1/purchases/{test_purchase.id}/liquidate",
            json=liquidate_data,
            headers=org_headers,
        )
        
        # Act - Try to cancel
        response = client.patch(
            f"/api/v1/purchases/{test_purchase.id}/cancel",
            headers=org_headers,
        )
        
        # Assert
        assert response.status_code == 400
        assert "cannot cancel paid purchase" in response.json()["detail"].lower()
    
    def test_cancel_purchase_already_cancelled_fails(
        self,
        client,
        org_headers,
        test_purchase,
    ):
        """Test that canceling an already cancelled purchase fails."""
        # Arrange - Cancel first time
        client.patch(
            f"/api/v1/purchases/{test_purchase.id}/cancel",
            headers=org_headers,
        )
        
        # Act - Try to cancel again
        response = client.patch(
            f"/api/v1/purchases/{test_purchase.id}/cancel",
            headers=org_headers,
        )
        
        # Assert
        assert response.status_code == 400


class TestPurchaseOrganizationIsolation:
    """Tests for organization isolation in purchase endpoints."""
    
    def test_cannot_access_purchase_from_different_org(
        self,
        client,
        test_purchase,
        test_user,
        test_organization2,
        auth_token,
    ):
        """Test that user cannot access purchase from different organization."""
        # Arrange - Headers for organization2
        org2_headers = {
            "Authorization": f"Bearer {auth_token}",
            "X-Organization-ID": str(test_organization2.id),
        }
        
        # Act
        response = client.get(
            f"/api/v1/purchases/{test_purchase.id}",
            headers=org2_headers,
        )
        
        # Assert
        assert response.status_code == 404


class TestPurchaseWeightedAverageCost:
    """Tests for weighted average cost calculation."""
    
    def test_weighted_average_cost_calculation(
        self,
        client,
        org_headers,
        test_supplier,
        test_material,
        test_warehouse,
        db_session,
    ):
        """Test that weighted average cost is calculated correctly."""
        # Arrange - First purchase
        purchase1_data = {
            "supplier_id": str(test_supplier.id),
            "date": datetime.now().isoformat(),
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 100.0,
                    "unit_price": 50.00,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
            "auto_liquidate": False,
        }
        
        # Act - Create first purchase
        response1 = client.post("/api/v1/purchases", json=purchase1_data, headers=org_headers)
        assert response1.status_code == 201
        
        # Arrange - Second purchase
        purchase2_data = {
            "supplier_id": str(test_supplier.id),
            "date": datetime.now().isoformat(),
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 50.0,
                    "unit_price": 60.00,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
            "auto_liquidate": False,
        }
        
        # Act - Create second purchase
        response2 = client.post("/api/v1/purchases", json=purchase2_data, headers=org_headers)
        assert response2.status_code == 201
        
        # Assert - Check material cost
        # Weighted average: (100*50 + 50*60) / 150 = 8000/150 = 53.33
        db_session.refresh(test_material)
        assert test_material.current_stock == Decimal("150.0000")
        assert abs(test_material.current_average_cost - Decimal("53.3333")) < Decimal("0.01")
