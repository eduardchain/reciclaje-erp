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
    
    purchase, _warnings = purchase_service.create(
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
    
    def test_cancel_paid_purchase_succeeds(
        self,
        client,
        org_headers,
        test_purchase,
        test_money_account,
        db_session,
    ):
        """Test that canceling a paid purchase succeeds and refunds money."""
        # Arrange - Liquidate first
        initial_balance = test_money_account.current_balance
        liquidate_data = {
            "payment_account_id": str(test_money_account.id),
        }
        client.patch(
            f"/api/v1/purchases/{test_purchase.id}/liquidate",
            json=liquidate_data,
            headers=org_headers,
        )

        # Act - Cancel the paid purchase
        response = client.patch(
            f"/api/v1/purchases/{test_purchase.id}/cancel",
            headers=org_headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"

        # Verify money was refunded
        db_session.refresh(test_money_account)
        assert test_money_account.current_balance == initial_balance
    
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


# ============================================================================
# Test Update Purchase
# ============================================================================

class TestUpdatePurchase:
    """Tests for PATCH /api/v1/purchases/{id}"""

    def test_update_purchase_metadata_only(
        self, client, org_headers, db_session, test_purchase, test_material
    ):
        """Editar solo metadata (notas, fecha, placa) sin tocar lineas ni inventario."""
        old_stock = test_material.current_stock

        response = client.patch(
            f"/api/v1/purchases/{test_purchase.id}",
            json={
                "notes": "Nota actualizada",
                "vehicle_plate": "ABC-123",
                "invoice_number": "FAC-001",
            },
            headers=org_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["notes"] == "Nota actualizada"
        assert data["vehicle_plate"] == "ABC-123"
        assert data["invoice_number"] == "FAC-001"

        # Stock no debe cambiar
        db_session.refresh(test_material)
        assert test_material.current_stock == old_stock

    def test_update_purchase_lines(
        self, client, org_headers, db_session,
        test_purchase, test_supplier, test_material, test_warehouse
    ):
        """Cambiar cantidad y precio de lineas, verificar inventario."""
        db_session.refresh(test_material)
        db_session.refresh(test_supplier)
        old_supplier_balance = test_supplier.current_balance

        response = client.patch(
            f"/api/v1/purchases/{test_purchase.id}",
            json={
                "lines": [
                    {
                        "material_id": str(test_material.id),
                        "quantity": 200,
                        "unit_price": 60,
                        "warehouse_id": str(test_warehouse.id),
                    }
                ]
            },
            headers=org_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_amount"] == 12000.0  # 200 * 60
        assert len(data["lines"]) == 1
        assert data["lines"][0]["quantity"] == 200.0

        # Stock: fue 100, revertido a 0, luego +200 = 200
        db_session.refresh(test_material)
        assert test_material.current_stock == Decimal("200.0000")

        # Saldo proveedor: fue -5000, revertido a 0, luego -12000
        db_session.refresh(test_supplier)
        expected_balance = old_supplier_balance + Decimal("5000") - Decimal("12000")
        assert test_supplier.current_balance == expected_balance

    def test_update_purchase_add_remove_lines(
        self, client, org_headers, db_session,
        test_purchase, test_supplier, test_material, test_warehouse,
        test_category, test_business_unit, test_organization
    ):
        """Reemplazar lineas: eliminar la original, agregar nueva con material diferente."""
        # Crear segundo material
        material2 = Material(
            id=uuid4(),
            code="IRON-001",
            name="Iron Scrap",
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

        response = client.patch(
            f"/api/v1/purchases/{test_purchase.id}",
            json={
                "lines": [
                    {
                        "material_id": str(material2.id),
                        "quantity": 50,
                        "unit_price": 30,
                        "warehouse_id": str(test_warehouse.id),
                    }
                ]
            },
            headers=org_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_amount"] == 1500.0  # 50 * 30
        assert data["lines"][0]["material_code"] == "IRON-001"

        # Material original: stock revertido a 0
        db_session.refresh(test_material)
        assert test_material.current_stock == Decimal("0.0000")

        # Material2: stock = 50
        db_session.refresh(material2)
        assert material2.current_stock == Decimal("50.0000")

    def test_update_purchase_change_supplier(
        self, client, org_headers, db_session,
        test_purchase, test_supplier, test_supplier2, test_material, test_warehouse
    ):
        """Cambiar proveedor, verificar saldos de ambos."""
        db_session.refresh(test_supplier)
        db_session.refresh(test_supplier2)
        old_balance_s1 = test_supplier.current_balance
        old_balance_s2 = test_supplier2.current_balance

        response = client.patch(
            f"/api/v1/purchases/{test_purchase.id}",
            json={"supplier_id": str(test_supplier2.id)},
            headers=org_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["supplier_name"] == "Second Supplier LLC"

        # Proveedor original: deuda revertida
        db_session.refresh(test_supplier)
        assert test_supplier.current_balance == old_balance_s1 + Decimal("5000")

        # Nuevo proveedor: deuda aplicada
        db_session.refresh(test_supplier2)
        assert test_supplier2.current_balance == old_balance_s2 - Decimal("5000")

    def test_update_paid_purchase_fails(
        self, client, org_headers, db_session,
        test_purchase, test_money_account
    ):
        """No se puede editar compra pagada."""
        # Primero liquidar
        client.patch(
            f"/api/v1/purchases/{test_purchase.id}/liquidate",
            json={"payment_account_id": str(test_money_account.id)},
            headers=org_headers,
        )

        response = client.patch(
            f"/api/v1/purchases/{test_purchase.id}",
            json={"notes": "intento editar pagada"},
            headers=org_headers,
        )

        assert response.status_code == 400
        assert "registered" in response.json()["detail"].lower()

    def test_update_cancelled_purchase_fails(
        self, client, org_headers, db_session, test_purchase
    ):
        """No se puede editar compra cancelada."""
        # Primero cancelar
        client.patch(
            f"/api/v1/purchases/{test_purchase.id}/cancel",
            headers=org_headers,
        )

        response = client.patch(
            f"/api/v1/purchases/{test_purchase.id}",
            json={"notes": "intento editar cancelada"},
            headers=org_headers,
        )

        assert response.status_code == 400
        assert "registered" in response.json()["detail"].lower()

    def test_update_double_entry_purchase_fails(
        self, client, org_headers, db_session, test_purchase
    ):
        """No se puede editar compra vinculada a doble partida."""
        from sqlalchemy import text

        # Setear double_entry_id directamente via SQL (bypass FK para test)
        fake_de_id = uuid4()
        db_session.execute(text(
            "SET session_replication_role = replica"
        ))
        db_session.execute(text(
            "UPDATE purchases SET double_entry_id = :de_id WHERE id = :pid"
        ), {"de_id": str(fake_de_id), "pid": str(test_purchase.id)})
        db_session.commit()
        db_session.refresh(test_purchase)

        response = client.patch(
            f"/api/v1/purchases/{test_purchase.id}",
            json={"notes": "intento editar DP"},
            headers=org_headers,
        )

        assert response.status_code == 400
        assert "doble partida" in response.json()["detail"].lower()

        # Limpiar
        db_session.execute(text(
            "UPDATE purchases SET double_entry_id = NULL WHERE id = :pid"
        ), {"pid": str(test_purchase.id)})
        db_session.execute(text(
            "SET session_replication_role = DEFAULT"
        ))
        db_session.commit()
        db_session.refresh(test_purchase)

    def test_update_insufficient_stock_fails(
        self, client, org_headers, db_session,
        test_purchase, test_material, test_warehouse
    ):
        """Si no hay stock suficiente para revertir, falla."""
        # Forzar stock bajo (como si ya se hubiera vendido parte)
        test_material.current_stock = Decimal("10.0000")
        test_material.current_stock_transit = Decimal("10.0000")
        db_session.commit()

        response = client.patch(
            f"/api/v1/purchases/{test_purchase.id}",
            json={
                "lines": [
                    {
                        "material_id": str(test_material.id),
                        "quantity": 50,
                        "unit_price": 50,
                        "warehouse_id": str(test_warehouse.id),
                    }
                ]
            },
            headers=org_headers,
        )

        assert response.status_code == 400
        assert "stock insuficiente" in response.json()["detail"].lower()


class TestLiquidateWithPriceUpdates:
    """Tests for liquidation with price editing (V-LIQ-01)."""

    def test_liquidate_with_line_price_updates(
        self,
        client,
        org_headers,
        test_supplier,
        test_material,
        test_warehouse,
        test_money_account,
    ):
        """Test liquidating with updated prices recalculates totals."""
        # Create purchase with price 0
        purchase_data = {
            "supplier_id": str(test_supplier.id),
            "date": datetime.now().isoformat(),
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 100.0,
                    "unit_price": 0,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
        }
        resp = client.post("/api/v1/purchases", json=purchase_data, headers=org_headers)
        assert resp.status_code == 201
        purchase = resp.json()
        line_id = purchase["lines"][0]["id"]

        # Liquidate with new price
        liquidate_data = {
            "payment_account_id": str(test_money_account.id),
            "lines": [
                {"line_id": line_id, "unit_price": 200.0}
            ],
        }
        resp = client.patch(
            f"/api/v1/purchases/{purchase['id']}/liquidate",
            json=liquidate_data,
            headers=org_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "paid"
        assert data["total_amount"] == 20000.0  # 100 * 200
        assert data["lines"][0]["unit_price"] == 200.0

    def test_liquidate_with_zero_price_fails(
        self,
        client,
        org_headers,
        test_supplier,
        test_material,
        test_warehouse,
        test_money_account,
    ):
        """Test that liquidation fails if any line has price 0 (V-LIQ-01)."""
        # Create purchase with price 0
        purchase_data = {
            "supplier_id": str(test_supplier.id),
            "date": datetime.now().isoformat(),
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 50.0,
                    "unit_price": 0,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
        }
        resp = client.post("/api/v1/purchases", json=purchase_data, headers=org_headers)
        assert resp.status_code == 201
        purchase = resp.json()

        # Try to liquidate without updating prices
        liquidate_data = {
            "payment_account_id": str(test_money_account.id),
        }
        resp = client.patch(
            f"/api/v1/purchases/{purchase['id']}/liquidate",
            json=liquidate_data,
            headers=org_headers,
        )

        assert resp.status_code == 400
        assert "mayores a 0" in resp.json()["detail"].lower()

    def test_liquidate_sets_liquidated_at(
        self,
        client,
        org_headers,
        test_purchase,
        test_money_account,
    ):
        """Test that liquidated_at timestamp is set on liquidation."""
        liquidate_data = {
            "payment_account_id": str(test_money_account.id),
        }
        resp = client.patch(
            f"/api/v1/purchases/{test_purchase.id}/liquidate",
            json=liquidate_data,
            headers=org_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["liquidated_at"] is not None

    def test_liquidate_recalculates_average_cost(
        self,
        client,
        org_headers,
        db_session,
        test_supplier,
        test_material,
        test_warehouse,
        test_money_account,
    ):
        """Test that updating prices on liquidation adjusts material average cost."""
        # Create purchase with price 100
        purchase_data = {
            "supplier_id": str(test_supplier.id),
            "date": datetime.now().isoformat(),
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 100.0,
                    "unit_price": 100.0,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
        }
        resp = client.post("/api/v1/purchases", json=purchase_data, headers=org_headers)
        assert resp.status_code == 201
        purchase = resp.json()
        line_id = purchase["lines"][0]["id"]

        # Liquidate with price 200 (cost should adjust upward)
        liquidate_data = {
            "payment_account_id": str(test_money_account.id),
            "lines": [
                {"line_id": line_id, "unit_price": 200.0}
            ],
        }
        resp = client.patch(
            f"/api/v1/purchases/{purchase['id']}/liquidate",
            json=liquidate_data,
            headers=org_headers,
        )
        assert resp.status_code == 200

        # Verify material avg cost was updated
        db_session.refresh(test_material)
        assert float(test_material.current_average_cost) == 200.0


class TestCancelPaidPurchase:
    """Tests for canceling paid purchases with refund."""

    def test_cancel_paid_purchase_returns_money(
        self,
        client,
        org_headers,
        db_session,
        test_supplier,
        test_material,
        test_warehouse,
        test_money_account,
    ):
        """Test that canceling a paid purchase returns money to the account."""
        initial_balance = float(test_money_account.current_balance)

        # Create and liquidate
        purchase_data = {
            "supplier_id": str(test_supplier.id),
            "date": datetime.now().isoformat(),
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 50.0,
                    "unit_price": 100.0,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
            "auto_liquidate": True,
            "payment_account_id": str(test_money_account.id),
        }
        resp = client.post("/api/v1/purchases", json=purchase_data, headers=org_headers)
        assert resp.status_code == 201
        purchase = resp.json()
        assert purchase["status"] == "paid"

        # Cancel
        resp = client.patch(
            f"/api/v1/purchases/{purchase['id']}/cancel",
            headers=org_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

        # Verify money refunded
        db_session.refresh(test_money_account)
        assert float(test_money_account.current_balance) == initial_balance

    def test_cancel_paid_purchase_reverses_liquidated_stock(
        self,
        client,
        org_headers,
        db_session,
        test_supplier,
        test_material,
        test_warehouse,
        test_money_account,
    ):
        """Test that canceling a paid purchase reverses stock from liquidated bucket."""
        initial_stock = float(test_material.current_stock)
        initial_liquidated = float(test_material.current_stock_liquidated)

        # Create and liquidate
        purchase_data = {
            "supplier_id": str(test_supplier.id),
            "date": datetime.now().isoformat(),
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 75.0,
                    "unit_price": 80.0,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
            "auto_liquidate": True,
            "payment_account_id": str(test_money_account.id),
        }
        resp = client.post("/api/v1/purchases", json=purchase_data, headers=org_headers)
        assert resp.status_code == 201

        # Verify stock increased
        db_session.refresh(test_material)
        assert float(test_material.current_stock) == initial_stock + 75.0
        assert float(test_material.current_stock_liquidated) == initial_liquidated + 75.0

        purchase = resp.json()

        # Cancel
        resp = client.patch(
            f"/api/v1/purchases/{purchase['id']}/cancel",
            headers=org_headers,
        )
        assert resp.status_code == 200

        # Verify stock reverted
        db_session.refresh(test_material)
        assert float(test_material.current_stock) == initial_stock
        assert float(test_material.current_stock_liquidated) == initial_liquidated


class TestPurchaseValidations:
    """Tests for purchase validations (V-COMP-04, RN-COMP-02)."""

    def test_create_purchase_future_date_fails(
        self,
        client,
        org_headers,
        test_supplier,
        test_material,
        test_warehouse,
    ):
        """Test that creating a purchase with future date fails (V-COMP-04)."""
        from datetime import timedelta
        future_date = (datetime.now() + timedelta(days=1)).isoformat()

        purchase_data = {
            "supplier_id": str(test_supplier.id),
            "date": future_date,
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 10.0,
                    "unit_price": 50.0,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
        }

        resp = client.post("/api/v1/purchases", json=purchase_data, headers=org_headers)
        assert resp.status_code == 400
        assert "futura" in resp.json()["detail"].lower()

    def test_create_purchase_duplicate_warning(
        self,
        client,
        org_headers,
        test_supplier,
        test_material,
        test_warehouse,
    ):
        """Test that duplicate purchases generate warnings (RN-COMP-02)."""
        purchase_data = {
            "supplier_id": str(test_supplier.id),
            "date": datetime.now().isoformat(),
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 10.0,
                    "unit_price": 50.0,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
        }

        # Create first purchase
        resp1 = client.post("/api/v1/purchases", json=purchase_data, headers=org_headers)
        assert resp1.status_code == 201

        # Create second purchase (same supplier, same day)
        resp2 = client.post("/api/v1/purchases", json=purchase_data, headers=org_headers)
        assert resp2.status_code == 201
        data = resp2.json()
        assert data.get("warnings") is not None
        assert len(data["warnings"]) > 0
        assert "mismo proveedor" in data["warnings"][0].lower()
