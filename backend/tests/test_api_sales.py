"""
Comprehensive tests for Sale API endpoints.

Tests all 8 endpoints:
1. POST /api/v1/sales - Create sale
2. GET /api/v1/sales - List sales
3. GET /api/v1/sales/pending - List pending
4. GET /api/v1/sales/by-number/{number} - Get by number
5. GET /api/v1/sales/customer/{id} - List by customer
6. GET /api/v1/sales/{id} - Get by ID
7. PATCH /api/v1/sales/{id}/liquidate - Liquidate
8. PATCH /api/v1/sales/{id}/cancel - Cancel
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
    Sale,
    MaterialCategory,
    BusinessUnit,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def test_customer(db_session, test_organization):
    """Create a test customer."""
    customer = ThirdParty(
        id=uuid4(),
        name="Test Customer Inc.",
        identification_number="12345678",
        is_supplier=False,
        is_customer=True,
        current_balance=Decimal("0.00"),
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


@pytest.fixture
def test_customer2(db_session, test_organization):
    """Create a second test customer."""
    customer = ThirdParty(
        id=uuid4(),
        name="Second Customer LLC",
        identification_number="87654321",
        is_supplier=False,
        is_customer=True,
        current_balance=Decimal("0.00"),
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


@pytest.fixture
def test_commission_recipient(db_session, test_organization):
    """Create a third party for commission payments."""
    recipient = ThirdParty(
        id=uuid4(),
        name="Sales Commission Account",
        is_supplier=False,
        is_customer=False,
        current_balance=Decimal("0.00"),
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(recipient)
    db_session.commit()
    db_session.refresh(recipient)
    return recipient


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
def test_material_with_stock(db_session, test_organization, test_category, test_business_unit):
    """Create a test material with stock."""
    material = Material(
        id=uuid4(),
        code="COPPER-001",
        name="Copper Scrap",
        category_id=test_category.id,
        business_unit_id=test_business_unit.id,
        default_unit="kg",
        current_stock=Decimal("500.000"),  # Stock total
        current_stock_liquidated=Decimal("500.000"),  # Stock disponible para venta
        current_stock_transit=Decimal("0.000"),  # Sin stock en transito
        current_average_cost=Decimal("45.00"),  # Costo para calculo de utilidad
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
    """Create a test money account."""
    account = MoneyAccount(
        id=uuid4(),
        name="Cash Account",
        account_type="cash",
        current_balance=Decimal("10000.00"),
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


@pytest.fixture
def test_sale(db_session, test_organization, test_customer, test_material_with_stock, test_warehouse):
    """Create a test sale (registered status)."""
    from app.schemas.sale import SaleCreate, SaleLineCreate
    from app.services.sale import crud_sale
    
    sale_data = SaleCreate(
        customer_id=test_customer.id,
        warehouse_id=test_warehouse.id,
        date=datetime.now(),
        vehicle_plate="ABC-123",
        invoice_number="FAC-001",
        notes="Test sale",
        lines=[
            SaleLineCreate(
                material_id=test_material_with_stock.id,
                quantity=Decimal("100.0"),
                unit_price=Decimal("60.00"),
            )
        ],
        commissions=[],
        auto_liquidate=False,
    )
    
    sale = crud_sale.create(
        db=db_session,
        obj_in=sale_data,
        organization_id=test_organization.id,
    )
    
    db_session.commit()
    db_session.refresh(sale)
    
    return sale


# ============================================================================
# Test Classes
# ============================================================================

class TestCreateSale:
    """Tests for POST /api/v1/sales"""
    
    def test_create_sale_2step_workflow(
        self,
        client,
        org_headers,
        test_customer,
        test_material_with_stock,
        test_warehouse,
    ):
        """Test creating a sale with 2-step workflow (auto_liquidate=False)."""
        # Arrange
        sale_data = {
            "customer_id": str(test_customer.id),
            "warehouse_id": str(test_warehouse.id),
            "date": datetime.now().isoformat(),
            "vehicle_plate": "XYZ-789",
            "invoice_number": "INV-001",
            "notes": "Test sale 2-step",
            "lines": [
                {
                    "material_id": str(test_material_with_stock.id),
                    "quantity": 50.0,
                    "unit_price": 80.00,
                }
            ],
            "commissions": [],
            "auto_liquidate": False,
        }
        
        # Act
        response = client.post("/api/v1/sales", json=sale_data, headers=org_headers)
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["sale_number"] == 1
        assert data["status"] == "registered"
        assert data["total_amount"] == 4000.0  # 50 * 80
        assert data["customer_name"] == test_customer.name
        assert data["warehouse_name"] == test_warehouse.name
        assert data["vehicle_plate"] == "XYZ-789"
        assert data["invoice_number"] == "INV-001"
        assert len(data["lines"]) == 1
        assert float(data["lines"][0]["quantity"]) == 50.0
        assert data["lines"][0]["material_code"] == "COPPER-001"
        assert float(data["lines"][0]["unit_cost"]) == 45.0  # Captured cost
        assert float(data["lines"][0]["profit"]) == 1750.0  # (80-45) * 50
        assert "total_profit" in data
        assert "id" in data
        assert "created_at" in data
    
    def test_create_sale_with_commissions(
        self,
        client,
        org_headers,
        test_customer,
        test_material_with_stock,
        test_warehouse,
        test_commission_recipient,
    ):
        """Test creating a sale with commissions."""
        # Arrange
        sale_data = {
            "customer_id": str(test_customer.id),
            "warehouse_id": str(test_warehouse.id),
            "date": datetime.now().isoformat(),
            "notes": "Sale with commissions",
            "lines": [
                {
                    "material_id": str(test_material_with_stock.id),
                    "quantity": 100.0,
                    "unit_price": 100.00,
                }
            ],
            "commissions": [
                {
                    "third_party_id": str(test_commission_recipient.id),
                    "concept": "Comisión de ventas",
                    "commission_type": "percentage",
                    "commission_value": 2.5,
                }
            ],
            "auto_liquidate": False,
        }
        
        # Act
        response = client.post("/api/v1/sales", json=sale_data, headers=org_headers)
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["total_amount"] == 10000.0  # 100 * 100
        assert len(data["commissions"]) == 1
        assert data["commissions"][0]["concept"] == "Comisión de ventas"
        assert data["commissions"][0]["commission_type"] == "percentage"
        assert float(data["commissions"][0]["commission_value"]) == 2.5
        assert float(data["commissions"][0]["commission_amount"]) == 250.0  # 2.5% of 10000
        assert data["commissions"][0]["third_party_name"] == test_commission_recipient.name
    
    def test_create_sale_1step_workflow(
        self,
        client,
        org_headers,
        test_customer,
        test_material_with_stock,
        test_warehouse,
        test_money_account,
    ):
        """Test creating a sale with 1-step workflow (auto_liquidate=True)."""
        # Arrange
        sale_data = {
            "customer_id": str(test_customer.id),
            "warehouse_id": str(test_warehouse.id),
            "date": datetime.now().isoformat(),
            "notes": "Test sale 1-step",
            "lines": [
                {
                    "material_id": str(test_material_with_stock.id),
                    "quantity": 20.0,
                    "unit_price": 75.00,
                }
            ],
            "commissions": [],
            "auto_liquidate": True,
            "payment_account_id": str(test_money_account.id),
        }
        
        # Act
        response = client.post("/api/v1/sales", json=sale_data, headers=org_headers)
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "paid"
        assert data["total_amount"] == 1500.0  # 20 * 75
        assert data["payment_account_id"] == str(test_money_account.id)
        assert data["payment_account_name"] == "Cash Account"
    
    def test_create_sale_insufficient_stock_fails(
        self,
        client,
        org_headers,
        test_customer,
        test_material_with_stock,
        test_warehouse,
    ):
        """Test that creating a sale with insufficient stock fails."""
        # Arrange
        sale_data = {
            "customer_id": str(test_customer.id),
            "warehouse_id": str(test_warehouse.id),
            "date": datetime.now().isoformat(),
            "lines": [
                {
                    "material_id": str(test_material_with_stock.id),
                    "quantity": 1000.0,  # More than available (500)
                    "unit_price": 50.00,
                }
            ],
            "commissions": [],
            "auto_liquidate": False,
        }
        
        # Act
        response = client.post("/api/v1/sales", json=sale_data, headers=org_headers)
        
        # Assert
        assert response.status_code == 400
        assert "Insufficient" in response.json()["detail"]
    
    def test_create_sale_auto_liquidate_without_account_fails(
        self,
        client,
        org_headers,
        test_customer,
        test_material_with_stock,
        test_warehouse,
    ):
        """Test that auto_liquidate=True without payment_account_id fails validation."""
        # Arrange
        sale_data = {
            "customer_id": str(test_customer.id),
            "warehouse_id": str(test_warehouse.id),
            "date": datetime.now().isoformat(),
            "lines": [
                {
                    "material_id": str(test_material_with_stock.id),
                    "quantity": 10.0,
                    "unit_price": 50.00,
                }
            ],
            "commissions": [],
            "auto_liquidate": True,
            # Missing payment_account_id
        }
        
        # Act
        response = client.post("/api/v1/sales", json=sale_data, headers=org_headers)
        
        # Assert
        assert response.status_code == 422  # Validation error


class TestListSales:
    """Tests for GET /api/v1/sales"""
    
    def test_list_sales_empty(self, client, org_headers):
        """Test listing sales when there are none."""
        # Act
        response = client.get("/api/v1/sales", headers=org_headers)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["skip"] == 0
        assert data["limit"] == 100
    
    def test_list_sales_with_data(self, client, org_headers, test_sale):
        """Test listing sales with data."""
        # Act
        response = client.get("/api/v1/sales", headers=org_headers)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["total"] == 1
        assert data["items"][0]["sale_number"] == test_sale.sale_number
        assert data["items"][0]["status"] == "registered"
    
    def test_list_sales_with_pagination(
        self,
        client,
        org_headers,
        db_session,
        test_organization,
        test_customer,
        test_material_with_stock,
        test_warehouse,
    ):
        """Test listing sales with pagination."""
        # Arrange - create multiple sales
        from app.schemas.sale import SaleCreate, SaleLineCreate
        from app.services.sale import crud_sale
        
        for i in range(5):
            sale_data = SaleCreate(
                customer_id=test_customer.id,
                warehouse_id=test_warehouse.id,
                date=datetime.now(),
                notes=f"Sale {i}",
                lines=[
                    SaleLineCreate(
                        material_id=test_material_with_stock.id,
                        quantity=Decimal("10.0"),
                        unit_price=Decimal("50.00"),
                    )
                ],
                commissions=[],
                auto_liquidate=False,
            )
            crud_sale.create(db=db_session, obj_in=sale_data, organization_id=test_organization.id)
        
        db_session.commit()
        
        # Act
        response = client.get("/api/v1/sales?skip=0&limit=2", headers=org_headers)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["skip"] == 0
        assert data["limit"] == 2
    
    def test_list_sales_filter_by_status(self, client, org_headers, test_sale):
        """Test filtering sales by status."""
        # Act
        response = client.get("/api/v1/sales?status=registered", headers=org_headers)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == "registered"


class TestGetSale:
    """Tests for GET /api/v1/sales/{id}"""
    
    def test_get_sale_by_id(self, client, org_headers, test_sale):
        """Test getting a sale by ID."""
        # Act
        response = client.get(f"/api/v1/sales/{test_sale.id}", headers=org_headers)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_sale.id)
        assert data["sale_number"] == test_sale.sale_number
        assert data["status"] == "registered"
        assert len(data["lines"]) > 0
    
    def test_get_sale_not_found(self, client, org_headers):
        """Test getting a non-existent sale."""
        # Act
        fake_id = uuid4()
        response = client.get(f"/api/v1/sales/{fake_id}", headers=org_headers)
        
        # Assert
        assert response.status_code == 404


class TestGetSaleByNumber:
    """Tests for GET /api/v1/sales/by-number/{number}"""
    
    def test_get_sale_by_number(self, client, org_headers, test_sale):
        """Test getting a sale by sale_number."""
        # Act
        response = client.get(f"/api/v1/sales/by-number/{test_sale.sale_number}", headers=org_headers)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["sale_number"] == test_sale.sale_number
        assert data["id"] == str(test_sale.id)
    
    def test_get_sale_by_number_not_found(self, client, org_headers):
        """Test getting a sale by non-existent number."""
        # Act
        response = client.get("/api/v1/sales/by-number/9999", headers=org_headers)
        
        # Assert
        assert response.status_code == 404


class TestListSalesByCustomer:
    """Tests for GET /api/v1/sales/customer/{id}"""
    
    def test_list_sales_by_customer(self, client, org_headers, test_sale, test_customer):
        """Test listing sales by customer."""
        # Act
        response = client.get(f"/api/v1/sales/customer/{test_customer.id}", headers=org_headers)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["customer_id"] == str(test_customer.id)


class TestListPendingSales:
    """Tests for GET /api/v1/sales/pending"""
    
    def test_list_pending_sales(self, client, org_headers, test_sale):
        """Test listing pending sales (status='registered')."""
        # Act
        response = client.get("/api/v1/sales/pending", headers=org_headers)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == "registered"


class TestLiquidateSale:
    """Tests for PATCH /api/v1/sales/{id}/liquidate"""
    
    def test_liquidate_sale(self, client, org_headers, test_sale, test_money_account, db_session):
        """Test liquidating a registered sale."""
        # Arrange
        initial_balance = test_money_account.current_balance
        liquidate_data = {
            "payment_account_id": str(test_money_account.id),
        }
        
        # Act
        response = client.patch(
            f"/api/v1/sales/{test_sale.id}/liquidate",
            json=liquidate_data,
            headers=org_headers,
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "paid"
        assert data["payment_account_id"] == str(test_money_account.id)
        
        # Verify account balance increased
        db_session.refresh(test_money_account)
        assert test_money_account.current_balance > initial_balance
    
    def test_liquidate_already_paid_sale_fails(
        self,
        client,
        org_headers,
        test_sale,
        test_money_account,
        db_session,
    ):
        """Test that liquidating an already paid sale fails."""
        # Arrange - liquidate first time
        from app.services.sale import crud_sale
        
        crud_sale.liquidate(
            db=db_session,
            sale_id=test_sale.id,
            payment_account_id=test_money_account.id,
            organization_id=test_sale.organization_id,
        )
        db_session.commit()
        
        liquidate_data = {
            "payment_account_id": str(test_money_account.id),
        }
        
        # Act - try to liquidate again
        response = client.patch(
            f"/api/v1/sales/{test_sale.id}/liquidate",
            json=liquidate_data,
            headers=org_headers,
        )
        
        # Assert
        assert response.status_code == 400
        assert "registered" in response.json()["detail"].lower()


class TestCancelSale:
    """Tests for PATCH /api/v1/sales/{id}/cancel"""
    
    def test_cancel_registered_sale(
        self,
        client,
        org_headers,
        test_sale,
        test_material_with_stock,
        db_session,
    ):
        """Test cancelling a registered sale."""
        # Arrange
        initial_stock = test_material_with_stock.current_stock
        
        # Act
        response = client.patch(f"/api/v1/sales/{test_sale.id}/cancel", headers=org_headers)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
        
        # Verify stock was restored
        db_session.refresh(test_material_with_stock)
        assert test_material_with_stock.current_stock > initial_stock
    
    def test_cancel_paid_sale_fails(
        self,
        client,
        org_headers,
        test_sale,
        test_money_account,
        db_session,
    ):
        """Test that cancelling a paid sale fails."""
        # Arrange - liquidate the sale first
        from app.services.sale import crud_sale
        
        crud_sale.liquidate(
            db=db_session,
            sale_id=test_sale.id,
            payment_account_id=test_money_account.id,
            organization_id=test_sale.organization_id,
        )
        db_session.commit()
        
        # Act
        response = client.patch(f"/api/v1/sales/{test_sale.id}/cancel", headers=org_headers)
        
        # Assert
        assert response.status_code == 400
        assert "paid" in response.json()["detail"].lower()
    
    def test_cancel_already_cancelled_sale_fails(
        self,
        client,
        org_headers,
        test_sale,
        db_session,
    ):
        """Test that cancelling an already cancelled sale fails."""
        # Arrange - cancel first time
        from app.services.sale import crud_sale
        
        crud_sale.cancel(
            db=db_session,
            sale_id=test_sale.id,
            organization_id=test_sale.organization_id,
        )
        db_session.commit()
        
        # Act - try to cancel again
        response = client.patch(f"/api/v1/sales/{test_sale.id}/cancel", headers=org_headers)
        
        # Assert
        assert response.status_code == 400
        assert "cancelled" in response.json()["detail"].lower()
