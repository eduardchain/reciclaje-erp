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
from app.models.inventory_movement import InventoryMovement
from app.models.material_cost_history import MaterialCostHistory
from app.models.third_party_category import ThirdPartyCategory, ThirdPartyCategoryAssignment


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
        current_balance=Decimal("0.00"),
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(customer)
    db_session.flush()
    cat_customer = ThirdPartyCategory(name="Customer Cat", behavior_type="customer", organization_id=test_organization.id)
    db_session.add(cat_customer)
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(third_party_id=customer.id, category_id=cat_customer.id))
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
        current_balance=Decimal("0.00"),
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(customer)
    db_session.flush()
    cat_customer2 = ThirdPartyCategory(name="Customer Cat 2", behavior_type="customer", organization_id=test_organization.id)
    db_session.add(cat_customer2)
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(third_party_id=customer.id, category_id=cat_customer2.id))
    db_session.commit()
    db_session.refresh(customer)
    return customer


@pytest.fixture
def test_commission_recipient(db_session, test_organization):
    """Create a third party for commission payments."""
    recipient = ThirdParty(
        id=uuid4(),
        name="Sales Commission Account",
        current_balance=Decimal("0.00"),
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(recipient)
    db_session.flush()
    cat_supplier = ThirdPartyCategory(name="Service Provider Commission", behavior_type="service_provider", organization_id=test_organization.id)
    db_session.add(cat_supplier)
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(third_party_id=recipient.id, category_id=cat_supplier.id))
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
def test_material_with_stock(db_session, test_organization, test_category, test_business_unit, test_warehouse):
    """Create a test material with stock (500kg in test_warehouse)."""
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
    db_session.flush()

    # Seed InventoryMovement para que stock por bodega coincida con stock global
    seed_movement = InventoryMovement(
        id=uuid4(),
        organization_id=test_organization.id,
        material_id=material.id,
        warehouse_id=test_warehouse.id,
        movement_type="adjustment",
        quantity=Decimal("500.000"),
        unit_cost=Decimal("45.00"),
        reference_type="adjustment",
        reference_id=uuid4(),
        date=datetime.now(),
        notes="Seed stock for test",
    )
    db_session.add(seed_movement)
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
        }

        # Act
        response = client.post("/api/v1/sales", json=sale_data, headers=org_headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "liquidated"
        assert data["total_amount"] == 1500.0  # 20 * 75
    
    def test_create_sale_insufficient_stock_warns(
        self,
        client,
        org_headers,
        test_customer,
        test_material_with_stock,
        test_warehouse,
    ):
        """Test that creating a sale with insufficient stock succeeds with warnings (RN-INV-03)."""
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

        # Assert — negative stock allowed with warning (per-warehouse validation)
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "registered"
        assert len(data["warnings"]) > 0
        assert any("en bodega" in w.lower() for w in data["warnings"])
    
    def test_create_sale_no_customer_balance_change(
        self,
        client,
        org_headers,
        test_customer,
        test_material_with_stock,
        test_warehouse,
        db_session,
    ):
        """Crear venta NO afecta saldo del cliente (se aplica en liquidacion)."""
        db_session.refresh(test_customer)
        initial_balance = float(test_customer.current_balance)

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
            "auto_liquidate": False,
        }

        response = client.post("/api/v1/sales", json=sale_data, headers=org_headers)
        assert response.status_code == 201

        db_session.refresh(test_customer)
        assert float(test_customer.current_balance) == initial_balance


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
    
    def test_liquidate_sale(self, client, org_headers, test_sale, test_customer, db_session):
        """Liquidar venta: status → liquidated, saldo cliente aumenta."""
        db_session.refresh(test_customer)
        initial_balance = float(test_customer.current_balance)
        liquidate_data = {}

        response = client.patch(
            f"/api/v1/sales/{test_sale.id}/liquidate",
            json=liquidate_data,
            headers=org_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "liquidated"

        # Saldo cliente aumento (deuda)
        db_session.refresh(test_customer)
        assert float(test_customer.current_balance) == initial_balance + data["total_amount"]
    
    def test_liquidate_already_liquidated_sale_fails(
        self,
        client,
        org_headers,
        test_sale,
        db_session,
    ):
        """Liquidar venta ya liquidada falla."""
        from app.services.sale import crud_sale

        crud_sale.liquidate(
            db=db_session,
            sale_id=test_sale.id,
            organization_id=test_sale.organization_id,
        )
        db_session.commit()

        # Act - intentar liquidar de nuevo
        response = client.patch(
            f"/api/v1/sales/{test_sale.id}/liquidate",
            json={},
            headers=org_headers,
        )

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
    
    def test_cancel_liquidated_sale_succeeds(
        self,
        client,
        org_headers,
        test_sale,
        test_customer,
        test_material_with_stock,
        db_session,
    ):
        """Cancelar venta liquidada: revierte saldo cliente + stock."""
        from app.services.sale import crud_sale

        crud_sale.liquidate(
            db=db_session,
            sale_id=test_sale.id,
            organization_id=test_sale.organization_id,
        )
        db_session.commit()

        db_session.refresh(test_customer)
        balance_after_liquidate = float(test_customer.current_balance)
        db_session.refresh(test_material_with_stock)
        stock_after_sale = float(test_material_with_stock.current_stock)

        # Act - cancelar venta liquidada
        response = client.patch(f"/api/v1/sales/{test_sale.id}/cancel", headers=org_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"

        # Saldo cliente revertido
        db_session.refresh(test_customer)
        assert float(test_customer.current_balance) == balance_after_liquidate - data["total_amount"]

        # Stock restaurado
        db_session.refresh(test_material_with_stock)
        assert float(test_material_with_stock.current_stock) > stock_after_sale
    
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
        assert "cancelada" in response.json()["detail"].lower()


class TestUpdateSale:
    """Tests for PATCH /api/v1/sales/{id} — edicion completa"""

    def test_update_sale_metadata_only(
        self, client, org_headers, test_sale,
    ):
        """Actualizar solo metadata sin afectar inventario."""
        update_data = {
            "notes": "Updated notes",
            "vehicle_plate": "NEW-999",
            "invoice_number": "FV-UPDATED",
        }

        response = client.patch(
            f"/api/v1/sales/{test_sale.id}",
            json=update_data,
            headers=org_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["notes"] == "Updated notes"
        assert data["vehicle_plate"] == "NEW-999"
        assert data["invoice_number"] == "FV-UPDATED"
        # Lineas no cambiaron
        assert len(data["lines"]) == 1
        assert data["total_amount"] == 6000.0  # 100 * 60 original

    def test_update_sale_lines(
        self,
        client,
        org_headers,
        test_sale,
        test_material_with_stock,
        db_session,
    ):
        """Cambiar qty/precio de lineas, verificar stock y unit_cost recalculado."""
        # Stock antes: 500 - 100 (test_sale) = 400
        db_session.refresh(test_material_with_stock)
        stock_before = float(test_material_with_stock.current_stock)

        update_data = {
            "lines": [
                {
                    "material_id": str(test_material_with_stock.id),
                    "quantity": 200.0,
                    "unit_price": 70.00,
                }
            ],
        }

        response = client.patch(
            f"/api/v1/sales/{test_sale.id}",
            json=update_data,
            headers=org_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_amount"] == 14000.0  # 200 * 70
        assert len(data["lines"]) == 1
        assert float(data["lines"][0]["quantity"]) == 200.0
        assert float(data["lines"][0]["unit_price"]) == 70.0
        assert float(data["lines"][0]["unit_cost"]) == 45.0  # recaptured avg cost

        # Stock: +100 (revert) -200 (new) = stock_before - 100
        db_session.refresh(test_material_with_stock)
        expected_stock = stock_before + 100 - 200
        assert float(test_material_with_stock.current_stock) == expected_stock

    def test_update_sale_change_customer(
        self,
        client,
        org_headers,
        test_sale,
        test_customer,
        test_customer2,
        db_session,
    ):
        """Cambiar cliente sin afectar saldos (sale es registered, sin saldo aplicado)."""
        db_session.refresh(test_customer)
        old_balance_c1 = float(test_customer.current_balance)
        db_session.refresh(test_customer2)
        old_balance_c2 = float(test_customer2.current_balance)

        update_data = {
            "customer_id": str(test_customer2.id),
        }

        response = client.patch(
            f"/api/v1/sales/{test_sale.id}",
            json=update_data,
            headers=org_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["customer_id"] == str(test_customer2.id)

        # Saldos NO cambian (registered = sin efecto en saldo)
        db_session.refresh(test_customer)
        db_session.refresh(test_customer2)
        assert float(test_customer.current_balance) == old_balance_c1
        assert float(test_customer2.current_balance) == old_balance_c2

    def test_update_sale_change_commissions(
        self,
        client,
        org_headers,
        test_sale,
        test_commission_recipient,
    ):
        """Cambiar comisiones — reemplazar todas."""
        update_data = {
            "commissions": [
                {
                    "third_party_id": str(test_commission_recipient.id),
                    "concept": "Comision nueva",
                    "commission_type": "percentage",
                    "commission_value": 5.0,
                }
            ],
        }

        response = client.patch(
            f"/api/v1/sales/{test_sale.id}",
            json=update_data,
            headers=org_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["commissions"]) == 1
        assert data["commissions"][0]["concept"] == "Comision nueva"
        assert float(data["commissions"][0]["commission_value"]) == 5.0
        # 5% de 6000 = 300
        assert float(data["commissions"][0]["commission_amount"]) == 300.0

    def test_update_liquidated_sale_fails(
        self,
        client,
        org_headers,
        test_sale,
        db_session,
    ):
        """No se puede editar venta liquidada."""
        from app.services.sale import crud_sale

        crud_sale.liquidate(
            db=db_session,
            sale_id=test_sale.id,
            organization_id=test_sale.organization_id,
        )
        db_session.commit()

        response = client.patch(
            f"/api/v1/sales/{test_sale.id}",
            json={"notes": "try edit"},
            headers=org_headers,
        )

        assert response.status_code == 400
        assert "registered" in response.json()["detail"].lower()

    def test_update_cancelled_sale_fails(
        self,
        client,
        org_headers,
        test_sale,
        db_session,
    ):
        """No se puede editar venta cancelada."""
        from app.services.sale import crud_sale

        crud_sale.cancel(
            db=db_session,
            sale_id=test_sale.id,
            organization_id=test_sale.organization_id,
        )
        db_session.commit()

        response = client.patch(
            f"/api/v1/sales/{test_sale.id}",
            json={"notes": "try edit"},
            headers=org_headers,
        )

        assert response.status_code == 400
        assert "registered" in response.json()["detail"].lower()

    def test_update_double_entry_sale_fails(
        self,
        client,
        org_headers,
        test_sale,
        db_session,
    ):
        """No se puede editar venta vinculada a doble partida."""
        from sqlalchemy import text as sql_text

        # Bypass FK para poner double_entry_id falso
        db_session.execute(sql_text("SET session_replication_role = replica"))
        db_session.execute(
            sql_text("UPDATE sales SET double_entry_id = :de_id WHERE id = :sale_id"),
            {"de_id": str(uuid4()), "sale_id": str(test_sale.id)},
        )
        db_session.commit()
        db_session.execute(sql_text("SET session_replication_role = DEFAULT"))

        response = client.patch(
            f"/api/v1/sales/{test_sale.id}",
            json={"notes": "try edit"},
            headers=org_headers,
        )

        assert response.status_code == 400
        assert "doble partida" in response.json()["detail"].lower()

    def test_update_sale_negative_stock_warning(
        self,
        client,
        org_headers,
        test_sale,
        test_material_with_stock,
        db_session,
    ):
        """Stock insuficiente genera warning, no error (RN-INV-03)."""
        update_data = {
            "lines": [
                {
                    "material_id": str(test_material_with_stock.id),
                    "quantity": 9999.0,  # Mucho mas que el stock
                    "unit_price": 60.00,
                }
            ],
        }

        response = client.patch(
            f"/api/v1/sales/{test_sale.id}",
            json=update_data,
            headers=org_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["warnings"]) > 0
        assert any("stock" in w.lower() for w in data["warnings"])


class TestEnhancedLiquidation:
    """Tests para liquidación mejorada con precios editables, comisiones y validaciones."""

    def test_liquidate_with_line_price_updates(
        self,
        client,
        org_headers,
        test_customer,
        test_material_with_stock,
        test_warehouse,
        db_session,
    ):
        """Crear venta con precio=0, liquidar con precios, verificar totales."""
        sale_data = {
            "customer_id": str(test_customer.id),
            "warehouse_id": str(test_warehouse.id),
            "date": datetime.now().isoformat(),
            "lines": [
                {
                    "material_id": str(test_material_with_stock.id),
                    "quantity": 100.0,
                    "unit_price": 0,
                }
            ],
            "auto_liquidate": False,
        }
        resp = client.post("/api/v1/sales", json=sale_data, headers=org_headers)
        assert resp.status_code == 201
        sale = resp.json()
        assert sale["total_amount"] == 0
        line_id = sale["lines"][0]["id"]

        liquidate_data = {
            "lines": [{"line_id": line_id, "unit_price": 80.0}],
        }
        resp = client.patch(
            f"/api/v1/sales/{sale['id']}/liquidate",
            json=liquidate_data,
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "liquidated"
        assert data["total_amount"] == 8000.0  # 100 * 80
        assert data["lines"][0]["unit_price"] == 80.0

    def test_liquidate_with_zero_price_fails(
        self,
        client,
        org_headers,
        test_customer,
        test_material_with_stock,
        test_warehouse,
        db_session,
    ):
        """V-VENTA-04: liquidar sin precios > 0 falla."""
        sale_data = {
            "customer_id": str(test_customer.id),
            "warehouse_id": str(test_warehouse.id),
            "date": datetime.now().isoformat(),
            "lines": [
                {
                    "material_id": str(test_material_with_stock.id),
                    "quantity": 50.0,
                    "unit_price": 0,
                }
            ],
            "auto_liquidate": False,
        }
        resp = client.post("/api/v1/sales", json=sale_data, headers=org_headers)
        assert resp.status_code == 201
        sale = resp.json()

        liquidate_data = {}
        resp = client.patch(
            f"/api/v1/sales/{sale['id']}/liquidate",
            json=liquidate_data,
            headers=org_headers,
        )
        assert resp.status_code == 400
        assert "V-VENTA-04" in resp.json()["detail"]

    def test_liquidate_with_commissions(
        self,
        client,
        org_headers,
        test_sale,
        test_commission_recipient,
        db_session,
    ):
        """Agregar comisiones durante liquidación."""
        resp = client.get(f"/api/v1/sales/{test_sale.id}", headers=org_headers)
        line_id = resp.json()["lines"][0]["id"]

        liquidate_data = {
            "lines": [{"line_id": line_id, "unit_price": 60.0}],
            "commissions": [
                {
                    "third_party_id": str(test_commission_recipient.id),
                    "concept": "Comisión liquidación",
                    "commission_type": "percentage",
                    "commission_value": 5.0,
                }
            ],
        }
        resp = client.patch(
            f"/api/v1/sales/{test_sale.id}/liquidate",
            json=liquidate_data,
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "liquidated"
        assert len(data["commissions"]) == 1
        assert data["commissions"][0]["commission_amount"] == 300.0  # 5% de 6000

    def test_liquidate_price_adjusts_customer_balance(
        self,
        client,
        org_headers,
        test_customer,
        test_material_with_stock,
        test_warehouse,
        db_session,
    ):
        """Liquidar aplica saldo completo al cliente (con precios actualizados)."""
        # Crear venta con precio 50 -> total 5000
        sale_data = {
            "customer_id": str(test_customer.id),
            "warehouse_id": str(test_warehouse.id),
            "date": datetime.now().isoformat(),
            "lines": [
                {
                    "material_id": str(test_material_with_stock.id),
                    "quantity": 100.0,
                    "unit_price": 50.0,
                }
            ],
            "auto_liquidate": False,
        }
        resp = client.post("/api/v1/sales", json=sale_data, headers=org_headers)
        assert resp.status_code == 201
        sale = resp.json()
        line_id = sale["lines"][0]["id"]

        # Create NO afecta saldo
        db_session.refresh(test_customer)
        balance_after_create = float(test_customer.current_balance)

        # Liquidar con precio 80 -> total 8000
        liquidate_data = {
            "lines": [{"line_id": line_id, "unit_price": 80.0}],
        }
        resp = client.patch(
            f"/api/v1/sales/{sale['id']}/liquidate",
            json=liquidate_data,
            headers=org_headers,
        )
        assert resp.status_code == 200

        # Saldo = balance_after_create + 8000 (total despues de update de precios)
        db_session.refresh(test_customer)
        expected_balance = balance_after_create + 8000.0
        assert abs(float(test_customer.current_balance) - expected_balance) < 0.01

    def test_liquidate_replaces_commissions(
        self,
        client,
        org_headers,
        test_customer,
        test_material_with_stock,
        test_warehouse,
        test_commission_recipient,
        db_session,
    ):
        """Comisiones existentes reemplazadas al liquidar."""
        # Crear venta con comisión
        sale_data = {
            "customer_id": str(test_customer.id),
            "warehouse_id": str(test_warehouse.id),
            "date": datetime.now().isoformat(),
            "lines": [
                {
                    "material_id": str(test_material_with_stock.id),
                    "quantity": 100.0,
                    "unit_price": 60.0,
                }
            ],
            "commissions": [
                {
                    "third_party_id": str(test_commission_recipient.id),
                    "concept": "Comisión original",
                    "commission_type": "fixed",
                    "commission_value": 100.0,
                }
            ],
            "auto_liquidate": False,
        }
        resp = client.post("/api/v1/sales", json=sale_data, headers=org_headers)
        assert resp.status_code == 201
        sale = resp.json()
        assert len(sale["commissions"]) == 1
        line_id = sale["lines"][0]["id"]

        # Liquidar con comisiones nuevas (reemplaza las originales)
        liquidate_data = {
            "lines": [{"line_id": line_id, "unit_price": 60.0}],
            "commissions": [
                {
                    "third_party_id": str(test_commission_recipient.id),
                    "concept": "Comisión nueva",
                    "commission_type": "percentage",
                    "commission_value": 10.0,
                }
            ],
        }
        resp = client.patch(
            f"/api/v1/sales/{sale['id']}/liquidate",
            json=liquidate_data,
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["commissions"]) == 1
        assert data["commissions"][0]["concept"] == "Comisión nueva"
        assert data["commissions"][0]["commission_amount"] == 600.0  # 10% de 6000


class TestFutureDateAndDuplicate:
    """Tests para validación de fecha futura y detección de duplicados."""

    def test_create_sale_future_date_fails(
        self,
        client,
        org_headers,
        test_customer,
        test_material_with_stock,
        test_warehouse,
    ):
        """Fecha futura en creación devuelve error 400."""
        from datetime import timedelta
        future = (datetime.now() + timedelta(days=2)).isoformat()

        sale_data = {
            "customer_id": str(test_customer.id),
            "warehouse_id": str(test_warehouse.id),
            "date": future,
            "lines": [
                {
                    "material_id": str(test_material_with_stock.id),
                    "quantity": 10.0,
                    "unit_price": 50.0,
                }
            ],
            "auto_liquidate": False,
        }
        resp = client.post("/api/v1/sales", json=sale_data, headers=org_headers)
        assert resp.status_code == 400
        assert "futura" in resp.json()["detail"].lower()

    def test_check_duplicate_sale(
        self,
        client,
        org_headers,
        test_sale,
        test_customer,
    ):
        """Crear venta, luego check-duplicate devuelve count=1."""
        date_str = test_sale.date.strftime("%Y-%m-%d")
        resp = client.get(
            f"/api/v1/sales/check-duplicate?customer_id={test_customer.id}&date={date_str}",
            headers=org_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1

    def test_check_duplicate_sale_cancelled_excluded(
        self,
        client,
        org_headers,
        test_customer,
        test_material_with_stock,
        test_warehouse,
        db_session,
    ):
        """Venta cancelada no cuenta como duplicado."""
        from app.services.sale import crud_sale
        from app.schemas.sale import SaleCreate, SaleLineCreate

        sale_date = datetime.now()

        # Crear y cancelar una venta
        sale_data = SaleCreate(
            customer_id=test_customer.id,
            warehouse_id=test_warehouse.id,
            date=sale_date,
            lines=[SaleLineCreate(
                material_id=test_material_with_stock.id,
                quantity=Decimal("10"),
                unit_price=Decimal("50"),
            )],
            auto_liquidate=False,
        )
        sale = crud_sale.create(
            db=db_session,
            obj_in=sale_data,
            organization_id=test_customer.organization_id,
        )
        db_session.commit()

        crud_sale.cancel(
            db=db_session,
            sale_id=sale.id,
            organization_id=test_customer.organization_id,
        )
        db_session.commit()

        # Verificar que no cuenta como duplicado
        date_str = sale_date.strftime("%Y-%m-%d")
        resp = client.get(
            f"/api/v1/sales/check-duplicate?customer_id={test_customer.id}&date={date_str}",
            headers=org_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 0


class TestWarehouseStockValidation:
    """Tests para validacion de stock por bodega y fallback de costo."""

    def test_create_sale_insufficient_warehouse_stock_warns(
        self,
        client,
        org_headers,
        test_customer,
        test_material_with_stock,
        test_warehouse,
        test_organization,
        db_session,
    ):
        """Venta en bodega sin stock suficiente genera warning con 'en bodega'."""
        # Crear segunda bodega SIN stock del material
        warehouse2 = Warehouse(
            id=uuid4(),
            name="Empty Warehouse",
            address="456 Empty St",
            organization_id=test_organization.id,
            is_active=True,
        )
        db_session.add(warehouse2)
        db_session.commit()

        sale_data = {
            "customer_id": str(test_customer.id),
            "warehouse_id": str(warehouse2.id),
            "date": datetime.now().isoformat(),
            "lines": [
                {
                    "material_id": str(test_material_with_stock.id),
                    "quantity": 10.0,
                    "unit_price": 50.00,
                }
            ],
            "commissions": [],
            "auto_liquidate": False,
        }

        response = client.post("/api/v1/sales", json=sale_data, headers=org_headers)
        assert response.status_code == 201
        data = response.json()
        assert len(data["warnings"]) > 0
        assert any("en bodega" in w.lower() for w in data["warnings"])
        # Stock global es 500 (suficiente), pero en bodega2 es 0
        assert any("disponible en bodega: 0" in w.lower() for w in data["warnings"])

    def test_create_sale_sufficient_warehouse_stock_no_warning(
        self,
        client,
        org_headers,
        test_customer,
        test_material_with_stock,
        test_warehouse,
    ):
        """Venta con stock suficiente en bodega NO genera warning."""
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
            "auto_liquidate": False,
        }

        response = client.post("/api/v1/sales", json=sale_data, headers=org_headers)
        assert response.status_code == 201
        data = response.json()
        assert len(data["warnings"]) == 0

    def test_create_sale_zero_avg_cost_uses_last_known(
        self,
        client,
        org_headers,
        test_customer,
        test_warehouse,
        test_organization,
        db_session,
        test_category,
        test_business_unit,
    ):
        """Material con avg_cost=0 usa ultimo costo conocido de MaterialCostHistory."""
        # Material con avg_cost=0
        material = Material(
            id=uuid4(),
            code="ZERO-COST-001",
            name="Zero Cost Material",
            category_id=test_category.id,
            business_unit_id=test_business_unit.id,
            default_unit="kg",
            current_stock=Decimal("100.000"),
            current_stock_liquidated=Decimal("100.000"),
            current_stock_transit=Decimal("0.000"),
            current_average_cost=Decimal("0"),
            organization_id=test_organization.id,
            is_active=True,
        )
        db_session.add(material)
        db_session.flush()

        # Seed inventory movement para stock por bodega
        seed = InventoryMovement(
            id=uuid4(),
            organization_id=test_organization.id,
            material_id=material.id,
            warehouse_id=test_warehouse.id,
            movement_type="adjustment",
            quantity=Decimal("100.000"),
            unit_cost=Decimal("0"),
            reference_type="adjustment",
            reference_id=uuid4(),
            date=datetime.now(),
            notes="Seed",
        )
        db_session.add(seed)

        # Crear MaterialCostHistory con ultimo costo conocido de $30
        cost_history = MaterialCostHistory(
            id=uuid4(),
            organization_id=test_organization.id,
            material_id=material.id,
            previous_cost=Decimal("25.00"),
            new_cost=Decimal("30.00"),
            previous_stock=Decimal("50.000"),
            new_stock=Decimal("100.000"),
            source_type="purchase_liquidation",
            source_id=uuid4(),
        )
        db_session.add(cost_history)
        db_session.commit()

        sale_data = {
            "customer_id": str(test_customer.id),
            "warehouse_id": str(test_warehouse.id),
            "date": datetime.now().isoformat(),
            "lines": [
                {
                    "material_id": str(material.id),
                    "quantity": 10.0,
                    "unit_price": 50.00,
                }
            ],
            "commissions": [],
            "auto_liquidate": False,
        }

        response = client.post("/api/v1/sales", json=sale_data, headers=org_headers)
        assert response.status_code == 201
        data = response.json()
        # Verificar que unit_cost capturo el ultimo costo conocido ($30), no $0
        line = data["lines"][0]
        assert float(line["unit_cost"]) == 30.0


class TestImmediateCollection:
    """Tests para cobro inmediato en venta 1-step (auto_liquidate + immediate_collection)."""

    def test_create_with_auto_liquidate_and_immediate_collection(
        self, client, org_headers, test_customer, test_material_with_stock, test_warehouse, test_money_account, db_session
    ):
        """Crear venta con auto_liquidate + immediate_collection acredita cuenta y balance cliente = 0."""
        initial_balance = float(test_money_account.current_balance)
        sale_total = 10 * 500  # 10 kg a $500 = $5000

        payload = {
            "customer_id": str(test_customer.id),
            "warehouse_id": str(test_warehouse.id),
            "date": "2026-03-01T12:00:00",
            "lines": [{"material_id": str(test_material_with_stock.id), "quantity": 10, "unit_price": 500}],
            "commissions": [],
            "auto_liquidate": True,
            "immediate_collection": True,
            "collection_account_id": str(test_money_account.id),
        }
        resp = client.post("/api/v1/sales", json=payload, headers=org_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "liquidated"

        # Verificar cuenta acreditada
        db_session.refresh(test_money_account)
        assert float(test_money_account.current_balance) == initial_balance + sale_total

        # Verificar balance cliente = 0 (liquidado + cobrado)
        db_session.refresh(test_customer)
        assert float(test_customer.current_balance) == 0

    def test_immediate_collection_requires_auto_liquidate(
        self, client, org_headers, test_customer, test_material_with_stock, test_warehouse, test_money_account
    ):
        """immediate_collection sin auto_liquidate debe fallar 422."""
        payload = {
            "customer_id": str(test_customer.id),
            "warehouse_id": str(test_warehouse.id),
            "date": "2026-03-01T12:00:00",
            "lines": [{"material_id": str(test_material_with_stock.id), "quantity": 10, "unit_price": 500}],
            "commissions": [],
            "auto_liquidate": False,
            "immediate_collection": True,
            "collection_account_id": str(test_money_account.id),
        }
        resp = client.post("/api/v1/sales", json=payload, headers=org_headers)
        assert resp.status_code == 422
