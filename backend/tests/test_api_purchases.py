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
from datetime import datetime, timezone
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
    MaterialCostHistory,
)
from app.models.third_party_category import ThirdPartyCategory, ThirdPartyCategoryAssignment


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def material_supplier_category(db_session, test_organization):
    """Create a shared material_supplier category for supplier fixtures."""
    cat = ThirdPartyCategory(
        id=uuid4(),
        name="Proveedor Material",
        behavior_type="material_supplier",
        organization_id=test_organization.id,
    )
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


@pytest.fixture
def test_supplier(db_session, test_organization, material_supplier_category):
    """Create a test supplier."""
    supplier = ThirdParty(
        id=uuid4(),
        name="Test Supplier Inc.",
        identification_number="12345678",
        current_balance=Decimal("0.00"),
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(supplier)
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(
        id=uuid4(),
        third_party_id=supplier.id,
        category_id=material_supplier_category.id,
    ))
    db_session.commit()
    db_session.refresh(supplier)
    return supplier


@pytest.fixture
def test_supplier2(db_session, test_organization, material_supplier_category):
    """Create a second test supplier."""
    supplier = ThirdParty(
        id=uuid4(),
        name="Second Supplier LLC",
        identification_number="87654321",
        current_balance=Decimal("0.00"),
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(supplier)
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(
        id=uuid4(),
        third_party_id=supplier.id,
        category_id=material_supplier_category.id,
    ))
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
        }

        # Act
        response = client.post("/api/v1/purchases", json=purchase_data, headers=org_headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "liquidated"
        assert data["total_amount"] == 1500.0  # 20 * 75
    
    def test_create_purchase_auto_liquidate_with_zero_price_fails(
        self,
        client,
        org_headers,
        test_supplier,
        test_material,
        test_warehouse,
    ):
        """Test that auto_liquidate=True with price=0 fails validation."""
        purchase_data = {
            "supplier_id": str(test_supplier.id),
            "date": datetime.now().isoformat(),
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 10.0,
                    "unit_price": 0,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
            "auto_liquidate": True,
        }

        response = client.post("/api/v1/purchases", json=purchase_data, headers=org_headers)
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
            params={"status": "liquidated"},
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
    ):
        """Test liquidating a registered purchase successfully."""
        # Act
        response = client.patch(
            f"/api/v1/purchases/{test_purchase.id}/liquidate",
            json={},
            headers=org_headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "liquidated"
    
    def test_liquidate_purchase_already_liquidated_fails(
        self,
        client,
        org_headers,
        test_purchase,
    ):
        """Test that liquidating an already liquidated purchase fails."""
        # Arrange - Liquidate first time
        client.patch(
            f"/api/v1/purchases/{test_purchase.id}/liquidate",
            json={},
            headers=org_headers,
        )

        # Act - Try to liquidate again
        response = client.patch(
            f"/api/v1/purchases/{test_purchase.id}/liquidate",
            json={},
            headers=org_headers,
        )

        # Assert
        assert response.status_code == 400


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
    
    def test_cancel_liquidated_purchase_succeeds(
        self,
        client,
        org_headers,
        test_purchase,
        test_supplier,
        db_session,
    ):
        """Test that canceling a liquidated purchase succeeds and reverts supplier balance."""
        # Arrange - Liquidate first
        client.patch(
            f"/api/v1/purchases/{test_purchase.id}/liquidate",
            json={},
            headers=org_headers,
        )
        db_session.refresh(test_supplier)
        supplier_balance_after_liquidation = test_supplier.current_balance

        # Act - Cancel the liquidated purchase
        response = client.patch(
            f"/api/v1/purchases/{test_purchase.id}/cancel",
            headers=org_headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"

        # Verify supplier balance was reverted (debt removed)
        db_session.refresh(test_supplier)
        assert test_supplier.current_balance == supplier_balance_after_liquidation + Decimal("5000")
    
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
    """Tests for weighted average cost calculation (at liquidation, not at create)."""

    def test_cost_not_updated_at_create(
        self,
        client,
        org_headers,
        test_supplier,
        test_material,
        test_warehouse,
        db_session,
    ):
        """Crear compra NO debe cambiar costo promedio del material."""
        initial_cost = test_material.current_average_cost

        purchase_data = {
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

        response = client.post("/api/v1/purchases", json=purchase_data, headers=org_headers)
        assert response.status_code == 201

        db_session.refresh(test_material)
        assert test_material.current_stock == Decimal("100.0000")
        assert test_material.current_stock_transit == Decimal("100.0000")
        assert test_material.current_average_cost == initial_cost  # NO CAMBIO

    def test_cost_updated_at_liquidation(
        self,
        client,
        org_headers,
        test_supplier,
        test_material,
        test_warehouse,
        db_session,
    ):
        """Liquidar compra DEBE recalcular costo promedio correctamente."""
        # Crear primera compra y liquidar
        p1 = client.post("/api/v1/purchases", json={
            "supplier_id": str(test_supplier.id),
            "date": datetime.now().isoformat(),
            "lines": [{
                "material_id": str(test_material.id),
                "quantity": 100.0,
                "unit_price": 50.00,
                "warehouse_id": str(test_warehouse.id),
            }],
        }, headers=org_headers)
        assert p1.status_code == 201
        p1_id = p1.json()["id"]

        # Liquidar primera compra
        client.patch(f"/api/v1/purchases/{p1_id}/liquidate", json={}, headers=org_headers)

        db_session.refresh(test_material)
        assert test_material.current_average_cost == Decimal("50.00")
        assert test_material.current_stock_liquidated == Decimal("100.0000")
        assert test_material.current_stock_transit == Decimal("0.0000")

        # Crear segunda compra y liquidar
        p2 = client.post("/api/v1/purchases", json={
            "supplier_id": str(test_supplier.id),
            "date": datetime.now().isoformat(),
            "lines": [{
                "material_id": str(test_material.id),
                "quantity": 50.0,
                "unit_price": 60.00,
                "warehouse_id": str(test_warehouse.id),
            }],
        }, headers=org_headers)
        assert p2.status_code == 201
        p2_id = p2.json()["id"]

        client.patch(f"/api/v1/purchases/{p2_id}/liquidate", json={}, headers=org_headers)

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

        # Saldo proveedor: NO debe cambiar al editar (se actualiza al liquidar)
        db_session.refresh(test_supplier)
        assert test_supplier.current_balance == old_supplier_balance

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
        """Cambiar proveedor. Saldos no cambian (se actualizan al liquidar)."""
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

        # Saldos no deben cambiar (se actualizan al liquidar)
        db_session.refresh(test_supplier)
        assert test_supplier.current_balance == old_balance_s1
        db_session.refresh(test_supplier2)
        assert test_supplier2.current_balance == old_balance_s2

    def test_update_liquidated_purchase_fails(
        self, client, org_headers, db_session,
        test_purchase,
    ):
        """No se puede editar compra liquidada."""
        # Primero liquidar
        client.patch(
            f"/api/v1/purchases/{test_purchase.id}/liquidate",
            json={},
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
        assert data["status"] == "liquidated"
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
        liquidate_data = {}
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
    ):
        """Test that liquidated_at timestamp is set on liquidation."""
        liquidate_data = {}
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

        # Liquidate with price 200 (cost should be set to 200)
        liquidate_data = {
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


class TestCancelLiquidatedPurchase:
    """Tests for canceling liquidated purchases."""

    def test_cancel_liquidated_purchase_reverts_supplier_balance(
        self,
        client,
        org_headers,
        db_session,
        test_supplier,
        test_material,
        test_warehouse,
    ):
        """Test that canceling a liquidated purchase reverts supplier balance (no money refund)."""
        initial_supplier_balance = float(test_supplier.current_balance)

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
        }
        resp = client.post("/api/v1/purchases", json=purchase_data, headers=org_headers)
        assert resp.status_code == 201
        purchase = resp.json()
        assert purchase["status"] == "liquidated"

        # Verify supplier balance decreased (debt increased)
        db_session.refresh(test_supplier)
        assert float(test_supplier.current_balance) == initial_supplier_balance - 5000.0

        # Cancel
        resp = client.patch(
            f"/api/v1/purchases/{purchase['id']}/cancel",
            headers=org_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

        # Verify supplier balance reverted
        db_session.refresh(test_supplier)
        assert float(test_supplier.current_balance) == initial_supplier_balance

    def test_cancel_liquidated_purchase_reverses_liquidated_stock(
        self,
        client,
        org_headers,
        db_session,
        test_supplier,
        test_material,
        test_warehouse,
    ):
        """Test that canceling a liquidated purchase reverses stock from liquidated bucket."""
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
        future_date = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()

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


class TestPurchaseWorkflowSeparation:
    """Tests para verificar que create no produce efectos financieros y liquidate si."""

    def test_create_no_supplier_balance_change(
        self, client, org_headers, db_session, test_supplier, test_material, test_warehouse
    ):
        """Crear compra NO debe cambiar saldo del proveedor."""
        initial_balance = test_supplier.current_balance

        resp = client.post("/api/v1/purchases", json={
            "supplier_id": str(test_supplier.id),
            "date": datetime.now().isoformat(),
            "lines": [{
                "material_id": str(test_material.id),
                "quantity": 100.0,
                "unit_price": 50.0,
                "warehouse_id": str(test_warehouse.id),
            }],
        }, headers=org_headers)
        assert resp.status_code == 201

        db_session.refresh(test_supplier)
        assert test_supplier.current_balance == initial_balance

    def test_create_no_avg_cost_change_with_zero_price(
        self, client, org_headers, db_session, test_supplier, test_material, test_warehouse
    ):
        """Crear compra con precio=0 NO debe corromper el costo promedio."""
        initial_cost = test_material.current_average_cost

        resp = client.post("/api/v1/purchases", json={
            "supplier_id": str(test_supplier.id),
            "date": datetime.now().isoformat(),
            "lines": [{
                "material_id": str(test_material.id),
                "quantity": 500.0,
                "unit_price": 0,
                "warehouse_id": str(test_warehouse.id),
            }],
        }, headers=org_headers)
        assert resp.status_code == 201

        db_session.refresh(test_material)
        assert test_material.current_average_cost == initial_cost
        assert test_material.current_stock_transit == Decimal("500.0000")

    def test_liquidate_updates_supplier_balance(
        self, client, org_headers, db_session, test_supplier, test_material, test_warehouse
    ):
        """Liquidar compra DEBE actualizar saldo del proveedor."""
        initial_balance = test_supplier.current_balance

        # Crear
        resp = client.post("/api/v1/purchases", json={
            "supplier_id": str(test_supplier.id),
            "date": datetime.now().isoformat(),
            "lines": [{
                "material_id": str(test_material.id),
                "quantity": 100.0,
                "unit_price": 50.0,
                "warehouse_id": str(test_warehouse.id),
            }],
        }, headers=org_headers)
        assert resp.status_code == 201
        purchase_id = resp.json()["id"]

        # Saldo no cambio al crear
        db_session.refresh(test_supplier)
        assert test_supplier.current_balance == initial_balance

        # Liquidar
        resp = client.patch(
            f"/api/v1/purchases/{purchase_id}/liquidate",
            json={},
            headers=org_headers,
        )
        assert resp.status_code == 200

        # Ahora si cambio
        db_session.refresh(test_supplier)
        assert test_supplier.current_balance == initial_balance - Decimal("5000")

    def test_liquidate_moves_stock_to_liquidated(
        self, client, org_headers, db_session, test_supplier, test_material, test_warehouse
    ):
        """Liquidar debe mover stock de transito a liquidado."""
        # Crear
        resp = client.post("/api/v1/purchases", json={
            "supplier_id": str(test_supplier.id),
            "date": datetime.now().isoformat(),
            "lines": [{
                "material_id": str(test_material.id),
                "quantity": 100.0,
                "unit_price": 50.0,
                "warehouse_id": str(test_warehouse.id),
            }],
        }, headers=org_headers)
        purchase_id = resp.json()["id"]

        db_session.refresh(test_material)
        assert test_material.current_stock_transit == Decimal("100.0000")
        assert test_material.current_stock_liquidated == Decimal("0.0000")

        # Liquidar
        client.patch(f"/api/v1/purchases/{purchase_id}/liquidate", json={}, headers=org_headers)

        db_session.refresh(test_material)
        assert test_material.current_stock_transit == Decimal("0.0000")
        assert test_material.current_stock_liquidated == Decimal("100.0000")

    def test_cancel_registered_no_balance_revert(
        self, client, org_headers, db_session, test_supplier, test_material, test_warehouse
    ):
        """Cancelar compra registrada NO debe revertir saldo (nunca cambio)."""
        initial_balance = test_supplier.current_balance

        resp = client.post("/api/v1/purchases", json={
            "supplier_id": str(test_supplier.id),
            "date": datetime.now().isoformat(),
            "lines": [{
                "material_id": str(test_material.id),
                "quantity": 100.0,
                "unit_price": 50.0,
                "warehouse_id": str(test_warehouse.id),
            }],
        }, headers=org_headers)
        purchase_id = resp.json()["id"]

        # Cancelar
        resp = client.patch(f"/api/v1/purchases/{purchase_id}/cancel", headers=org_headers)
        assert resp.status_code == 200

        # Saldo sigue igual
        db_session.refresh(test_supplier)
        assert test_supplier.current_balance == initial_balance

        # Stock revertido
        db_session.refresh(test_material)
        assert test_material.current_stock == Decimal("0.0000")
        assert test_material.current_stock_transit == Decimal("0.0000")


# ============================================================================
# Tests: Material Cost History
# ============================================================================

class TestCostHistory:
    """Tests para historial de costo y reversion precisa."""

    def test_cost_history_created_on_liquidation(
        self, client, org_headers, test_supplier, test_material, test_warehouse, db_session
    ):
        """Verificar que se crea MaterialCostHistory al liquidar."""
        # Crear compra auto-liquidada
        payload = {
            "supplier_id": str(test_supplier.id),
            "date": datetime.utcnow().isoformat(),
            "auto_liquidate": True,
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 1000,
                    "unit_price": 2000,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
        }
        response = client.post("/api/v1/purchases", json=payload, headers=org_headers)
        assert response.status_code == 201
        purchase_id = response.json()["id"]

        # Verificar que se creo registro en historial
        history = db_session.query(MaterialCostHistory).filter(
            MaterialCostHistory.source_type == "purchase_liquidation",
            MaterialCostHistory.source_id == purchase_id,
        ).first()
        assert history is not None
        assert history.new_cost == Decimal("2000.0000")
        assert history.material_id == test_material.id

    def test_cancel_liquidated_reverts_average_cost(
        self, client, org_headers, test_supplier, test_material, test_warehouse, db_session
    ):
        """
        Cancelar compra liquidada revierte el costo promedio al valor anterior.

        1. Material empieza en costo=0, stock=0
        2. Compra 1: 1000kg @ $2000 → costo=$2000
        3. Cancelar Compra 1 → costo vuelve a $0
        """
        payload = {
            "supplier_id": str(test_supplier.id),
            "date": datetime.utcnow().isoformat(),
            "auto_liquidate": True,
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 1000,
                    "unit_price": 2000,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
        }
        response = client.post("/api/v1/purchases", json=payload, headers=org_headers)
        assert response.status_code == 201
        purchase_id = response.json()["id"]

        db_session.refresh(test_material)
        assert test_material.current_average_cost == Decimal("2000.0000")

        # Cancelar
        response = client.patch(
            f"/api/v1/purchases/{purchase_id}/cancel",
            headers=org_headers,
        )
        assert response.status_code == 200

        db_session.refresh(test_material)
        assert test_material.current_average_cost == Decimal("0.0000")

    def test_cancel_most_recent_allowed(
        self, client, org_headers, test_supplier, test_material, test_warehouse, db_session
    ):
        """
        Cancelar la compra mas reciente esta permitido.

        1. Compra 1: 1000kg @ $2000 → costo=$2000
        2. Compra 2: 1000kg @ $2400 → costo=$2200
        3. Cancelar Compra 2 → OK, costo=$2000
        """
        base_payload = {
            "supplier_id": str(test_supplier.id),
            "date": datetime.utcnow().isoformat(),
            "auto_liquidate": True,
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 1000,
                    "unit_price": 2000,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
        }
        # Compra 1
        r1 = client.post("/api/v1/purchases", json=base_payload, headers=org_headers)
        assert r1.status_code == 201

        db_session.refresh(test_material)
        assert test_material.current_average_cost == Decimal("2000.0000")

        # Compra 2
        payload2 = {**base_payload, "lines": [
            {
                "material_id": str(test_material.id),
                "quantity": 1000,
                "unit_price": 2400,
                "warehouse_id": str(test_warehouse.id),
            }
        ]}
        r2 = client.post("/api/v1/purchases", json=payload2, headers=org_headers)
        assert r2.status_code == 201
        purchase2_id = r2.json()["id"]

        db_session.refresh(test_material)
        assert test_material.current_average_cost == Decimal("2200.0000")

        # Cancelar Compra 2 (la mas reciente) → debe funcionar
        response = client.patch(
            f"/api/v1/purchases/{purchase2_id}/cancel",
            headers=org_headers,
        )
        assert response.status_code == 200

        db_session.refresh(test_material)
        assert test_material.current_average_cost == Decimal("2000.0000")

    def test_cancel_blocked_by_subsequent_purchase(
        self, client, org_headers, test_supplier, test_material, test_warehouse, db_session
    ):
        """
        Cancelar compra bloqueada por operacion posterior.

        1. Compra 1: 1000kg @ $2000 → costo=$2000
        2. Compra 2: 1000kg @ $2400 → costo=$2200
        3. Intentar cancelar Compra 1 → HTTP 400
        """
        base_payload = {
            "supplier_id": str(test_supplier.id),
            "date": datetime.utcnow().isoformat(),
            "auto_liquidate": True,
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 1000,
                    "unit_price": 2000,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
        }
        # Compra 1
        r1 = client.post("/api/v1/purchases", json=base_payload, headers=org_headers)
        assert r1.status_code == 201
        purchase1_id = r1.json()["id"]

        # Compra 2
        payload2 = {**base_payload, "lines": [
            {
                "material_id": str(test_material.id),
                "quantity": 1000,
                "unit_price": 2400,
                "warehouse_id": str(test_warehouse.id),
            }
        ]}
        r2 = client.post("/api/v1/purchases", json=payload2, headers=org_headers)
        assert r2.status_code == 201

        # Intentar cancelar Compra 1 → debe fallar
        response = client.patch(
            f"/api/v1/purchases/{purchase1_id}/cancel",
            headers=org_headers,
        )
        assert response.status_code == 400
        assert "operaciones posteriores" in response.json()["detail"]

    def test_cost_history_deleted_on_reversal(
        self, client, org_headers, test_supplier, test_material, test_warehouse, db_session
    ):
        """Verificar que el registro de historial se elimina al revertir."""
        payload = {
            "supplier_id": str(test_supplier.id),
            "date": datetime.utcnow().isoformat(),
            "auto_liquidate": True,
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 1000,
                    "unit_price": 2000,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
        }
        response = client.post("/api/v1/purchases", json=payload, headers=org_headers)
        assert response.status_code == 201
        purchase_id = response.json()["id"]

        # Verificar historial existe
        count_before = db_session.query(MaterialCostHistory).filter(
            MaterialCostHistory.source_id == purchase_id,
        ).count()
        assert count_before == 1

        # Cancelar
        client.patch(f"/api/v1/purchases/{purchase_id}/cancel", headers=org_headers)

        # Historial debe estar eliminado
        count_after = db_session.query(MaterialCostHistory).filter(
            MaterialCostHistory.source_id == purchase_id,
        ).count()
        assert count_after == 0

    def test_cancel_registered_no_history_check(
        self, client, org_headers, test_supplier, test_material, test_warehouse, db_session
    ):
        """Cancelar compra registrada (no liquidada) no necesita historial de costo."""
        payload = {
            "supplier_id": str(test_supplier.id),
            "date": datetime.utcnow().isoformat(),
            "auto_liquidate": False,
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 1000,
                    "unit_price": 0,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
        }
        response = client.post("/api/v1/purchases", json=payload, headers=org_headers)
        assert response.status_code == 201
        purchase_id = response.json()["id"]

        # No debe haber historial (no se liquido)
        count = db_session.query(MaterialCostHistory).filter(
            MaterialCostHistory.source_id == purchase_id,
        ).count()
        assert count == 0

        # Cancelar → debe funcionar sin problemas
        response = client.patch(
            f"/api/v1/purchases/{purchase_id}/cancel",
            headers=org_headers,
        )
        assert response.status_code == 200

    def test_average_cost_ignores_transit_stock(
        self, client, org_headers, test_supplier, test_material, test_warehouse, db_session
    ):
        """El stock en transito (compras registradas) NO debe afectar el costo promedio."""
        # Resetear material
        test_material.current_stock = 0
        test_material.current_stock_liquidated = 0
        test_material.current_stock_transit = 0
        test_material.current_average_cost = 0
        db_session.commit()

        # Compra 1: 1000 kg @ $2000, registrada (NO liquidar)
        payload1 = {
            "supplier_id": str(test_supplier.id),
            "date": datetime.utcnow().isoformat(),
            "auto_liquidate": False,
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 1000,
                    "unit_price": 2000,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
        }
        r1 = client.post("/api/v1/purchases", json=payload1, headers=org_headers)
        assert r1.status_code == 201

        # Verificar: transito=1000, liquidado=0, costo=$0
        db_session.refresh(test_material)
        assert test_material.current_stock_transit == 1000
        assert test_material.current_stock_liquidated == 0
        assert test_material.current_average_cost == 0

        # Compra 2: 500 kg @ $2500, liquidar
        payload2 = {
            "supplier_id": str(test_supplier.id),
            "date": datetime.utcnow().isoformat(),
            "auto_liquidate": True,
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 500,
                    "unit_price": 2500,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
        }
        r2 = client.post("/api/v1/purchases", json=payload2, headers=org_headers)
        assert r2.status_code == 201

        # Verificar: costo = $2500 (NO $833 que seria con transito)
        db_session.refresh(test_material)
        assert test_material.current_stock_transit == 1000
        assert test_material.current_stock_liquidated == 500
        assert test_material.current_average_cost == 2500


class TestImmediatePayment:
    """Tests para pago inmediato en compra 1-step (auto_liquidate + immediate_payment)."""

    def test_create_with_auto_liquidate_and_immediate_payment(
        self, client, org_headers, test_supplier, test_material, test_warehouse, test_money_account, db_session
    ):
        """Crear compra con auto_liquidate + immediate_payment descuenta cuenta y balance proveedor = 0."""
        initial_balance = float(test_money_account.current_balance)
        purchase_total = 100 * 1000  # 100 kg a $1000

        payload = {
            "supplier_id": str(test_supplier.id),
            "date": "2026-03-01T12:00:00",
            "lines": [{"material_id": str(test_material.id), "quantity": 100, "unit_price": 1000, "warehouse_id": str(test_warehouse.id)}],
            "auto_liquidate": True,
            "immediate_payment": True,
            "payment_account_id": str(test_money_account.id),
        }
        resp = client.post("/api/v1/purchases", json=payload, headers=org_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "liquidated"

        # Verificar cuenta descontada
        db_session.refresh(test_money_account)
        assert float(test_money_account.current_balance) == initial_balance - purchase_total

        # Verificar balance proveedor = 0 (liquidado + pagado)
        db_session.refresh(test_supplier)
        assert float(test_supplier.current_balance) == 0

    def test_immediate_payment_requires_auto_liquidate(
        self, client, org_headers, test_supplier, test_material, test_warehouse, test_money_account
    ):
        """immediate_payment sin auto_liquidate debe fallar 422."""
        payload = {
            "supplier_id": str(test_supplier.id),
            "date": "2026-03-01T12:00:00",
            "lines": [{"material_id": str(test_material.id), "quantity": 100, "unit_price": 1000, "warehouse_id": str(test_warehouse.id)}],
            "auto_liquidate": False,
            "immediate_payment": True,
            "payment_account_id": str(test_money_account.id),
        }
        resp = client.post("/api/v1/purchases", json=payload, headers=org_headers)
        assert resp.status_code == 422


class TestCancelBlockedByTransformationSameCost:
    """
    Bug fix: transformacion posterior con mismo costo promedio
    no creaba registro en MaterialCostHistory, permitiendo cancelar
    la compra previa y corrompiendo el costo a $0.
    """

    def test_cancel_blocked_by_transformation_same_cost(
        self, client, org_headers, test_supplier, test_material, test_warehouse, db_session
    ):
        """
        Escenario del bug FE004:
        1. Compra liquidada: 36kg @ $1200 → costo = $1200
        2. Transformacion: material destino recibe 100kg al mismo costo $1200
           (costo no cambia → antes no se registraba en historial)
        3. Intentar cancelar compra → debe BLOQUEAR (hay transformacion posterior)
        """
        # Crear material destino de la transformacion (distinto del source)
        dest_material = Material(
            code="DEST-001",
            name="Material Destino",
            default_unit="kg",
            current_stock=Decimal("0"),
            current_stock_liquidated=Decimal("0"),
            current_stock_transit=Decimal("0"),
            current_average_cost=Decimal("0"),
            organization_id=test_material.organization_id,
            is_active=True,
        )
        db_session.add(dest_material)
        db_session.commit()
        db_session.refresh(dest_material)

        # 1. Compra liquidada: test_material 36kg @ $1200
        purchase_payload = {
            "supplier_id": str(test_supplier.id),
            "date": datetime.utcnow().isoformat(),
            "auto_liquidate": True,
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 36,
                    "unit_price": 1200,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
        }
        r1 = client.post("/api/v1/purchases", json=purchase_payload, headers=org_headers)
        assert r1.status_code == 201
        purchase_id = r1.json()["id"]

        # Verificar costo = 1200
        db_session.refresh(test_material)
        assert float(test_material.current_average_cost) == 1200

        # 2. Transformacion: test_material (source) → dest_material (destination)
        #    Source: 36kg de test_material @ $1200
        #    Dest: 36kg a dest_material con metodo average_cost
        #    Pero primero necesitamos que dest_material tenga costo $1200
        #    para que la transformacion NO cambie el costo del source.
        #    En realidad el bug es sobre el material SOURCE: la compra se
        #    hizo sobre test_material, la transformacion SALE de test_material.
        #    Pero check_can_revert busca en el material de la compra (test_material).
        #    La transformacion crea MaterialCostHistory solo para DESTINO.
        #    Entonces necesitamos que el DESTINO sea test_material tambien.
        #
        #    Escenario correcto: la compra Y la transformacion destino son el mismo material.
        #    Compra: +36kg test_material @ $1200 (costo 0→1200, SI registra)
        #    Transformacion: source=dest_material, dest=test_material +100kg @ $1200
        #       costo test_material = (36*1200 + 100*1200) / 136 = 1200 (NO cambia)
        #       Con el fix, ahora SI registra en historial.

        # Poner stock en dest_material para usarlo como source
        dest_material.current_stock = Decimal("100")
        dest_material.current_stock_liquidated = Decimal("100")
        dest_material.current_average_cost = Decimal("1200")
        db_session.commit()

        transform_payload = {
            "source_material_id": str(dest_material.id),
            "source_quantity": 100,
            "source_warehouse_id": str(test_warehouse.id),
            "waste_quantity": 0,
            "cost_distribution_method": "average_cost",
            "reason": "Test transformacion mismo costo",
            "date": datetime.utcnow().isoformat(),
            "lines": [
                {
                    "destination_material_id": str(test_material.id),
                    "destination_warehouse_id": str(test_warehouse.id),
                    "quantity": 100,
                }
            ],
        }
        r2 = client.post("/api/v1/inventory/transformations", json=transform_payload, headers=org_headers)
        assert r2.status_code == 201, r2.json()

        # Verificar: costo de test_material sigue siendo $1200
        db_session.refresh(test_material)
        assert float(test_material.current_average_cost) == 1200

        # Verificar que ahora SI hay registro de historial para la transformacion
        # (antes del fix, no se creaba porque costo no cambiaba)
        transform_id = r2.json()["id"]
        history_count = db_session.query(MaterialCostHistory).filter(
            MaterialCostHistory.material_id == test_material.id,
            MaterialCostHistory.source_type == "transformation_in",
            MaterialCostHistory.source_id == transform_id,
        ).count()
        assert history_count == 1, "Transformacion debe registrar historial incluso si costo no cambia"

        # 3. Intentar cancelar la compra → debe BLOQUEAR
        response = client.patch(
            f"/api/v1/purchases/{purchase_id}/cancel",
            headers=org_headers,
        )
        assert response.status_code == 400
        assert "operaciones posteriores" in response.json()["detail"]
