"""
Comprehensive tests for DoubleEntry (Pasa Mano) API endpoints.

Tests all 8 endpoints:
1. POST /api/v1/double-entries - Create double-entry
2. GET /api/v1/double-entries - List with filters
3. GET /api/v1/double-entries/{id} - Get by UUID
4. GET /api/v1/double-entries/by-number/{number} - Get by number
5. GET /api/v1/double-entries/supplier/{id} - List by supplier
6. GET /api/v1/double-entries/customer/{id} - List by customer
7. PATCH /api/v1/double-entries/{id}/cancel - Cancel
8. PATCH /api/v1/double-entries/{id} - Update metadata

Business Rules Tested:
- Material does NOT enter inventory (no stock movements)
- Creates Purchase (status='liquidated') without inventory movements
- Creates Sale (status='liquidated') without inventory movements
- Updates supplier balance (debt increases)
- Updates customer balance (receivable increases)
- Creates commissions (paid immediately at creation)
- Validates supplier != customer
- Multi-material lines support
- No duplicate materials across lines (V-DP-02)
- Cancel operation reverses balances
"""
import pytest
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from app.models import (
    ThirdParty,
    Material,
    Purchase,
    Sale,
    DoubleEntry,
    DoubleEntryLine,
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
        name="Metal Supplier Co.",
        identification_number="SUP-001",
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
def test_customer(db_session, test_organization):
    """Create a test customer."""
    customer = ThirdParty(
        id=uuid4(),
        name="Customer Industries",
        identification_number="CUST-001",
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
def test_supplier_customer(db_session, test_organization):
    """Create a third party that is BOTH supplier and customer (for validation test)."""
    party = ThirdParty(
        id=uuid4(),
        name="Dual Role Company",
        identification_number="DUAL-001",
        is_supplier=True,
        is_customer=True,
        current_balance=Decimal("0.00"),
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(party)
    db_session.commit()
    db_session.refresh(party)
    return party


@pytest.fixture
def test_commission_recipient(db_session, test_organization):
    """Create a third party for commission payments."""
    recipient = ThirdParty(
        id=uuid4(),
        name="Commission Agent",
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
    bu = BusinessUnit(
        id=uuid4(),
        name="Main Unit",
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(bu)
    db_session.commit()
    db_session.refresh(bu)
    return bu


@pytest.fixture
def test_material(db_session, test_organization, test_category, test_business_unit):
    """Create a test material (NO initial stock - double-entry doesn't use inventory)."""
    material = Material(
        id=uuid4(),
        code="COPPER-01",
        name="Copper Wire",
        default_unit="kg",
        current_stock=Decimal("0.00"),
        current_average_cost=Decimal("7500.00"),
        category_id=test_category.id,
        business_unit_id=test_business_unit.id,
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)
    return material


@pytest.fixture
def test_material_2(db_session, test_organization, test_category, test_business_unit):
    """Create a second test material for multi-line tests."""
    material = Material(
        id=uuid4(),
        code="ALUM-01",
        name="Aluminum Scrap",
        default_unit="kg",
        current_stock=Decimal("0.00"),
        current_average_cost=Decimal("3000.00"),
        category_id=test_category.id,
        business_unit_id=test_business_unit.id,
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)
    return material


@pytest.fixture
def test_double_entry(db_session, test_organization, test_supplier, test_customer, test_material):
    """Create a test double-entry operation with one line."""
    purchase = Purchase(
        id=uuid4(),
        organization_id=test_organization.id,
        purchase_number=1,
        supplier_id=test_supplier.id,
        date=datetime.now(),
        total_amount=Decimal("8000000.00"),  # 1000 kg x $8000/kg
        status="liquidated",
        notes="Test purchase for double-entry",
    )
    db_session.add(purchase)
    db_session.flush()

    sale = Sale(
        id=uuid4(),
        organization_id=test_organization.id,
        sale_number=1,
        customer_id=test_customer.id,
        warehouse_id=None,
        date=datetime.now(),
        invoice_number="INV-001",
        vehicle_plate="ABC-123",
        total_amount=Decimal("10000000.00"),  # 1000 kg x $10000/kg
        status="liquidated",
        notes="Test sale for double-entry",
    )
    db_session.add(sale)
    db_session.flush()

    double_entry = DoubleEntry(
        id=uuid4(),
        organization_id=test_organization.id,
        double_entry_number=1,
        date=date.today(),
        supplier_id=test_supplier.id,
        customer_id=test_customer.id,
        invoice_number="INV-001",
        vehicle_plate="ABC-123",
        notes="Test double-entry",
        purchase_id=purchase.id,
        sale_id=sale.id,
        status="completed",
    )
    db_session.add(double_entry)
    db_session.flush()

    # Crear linea de doble partida
    line = DoubleEntryLine(
        id=uuid4(),
        double_entry_id=double_entry.id,
        material_id=test_material.id,
        quantity=Decimal("1000.000"),
        purchase_unit_price=Decimal("8000.00"),
        sale_unit_price=Decimal("10000.00"),
    )
    db_session.add(line)

    # Update balances
    test_supplier.current_balance -= Decimal("8000000.00")  # Debt
    test_customer.current_balance += Decimal("10000000.00")  # Receivable

    # Link double_entry_id
    purchase.double_entry_id = double_entry.id
    sale.double_entry_id = double_entry.id

    db_session.commit()
    db_session.refresh(double_entry)
    return double_entry


# ============================================================================
# Test Class
# ============================================================================

class TestDoubleEntryAPI:
    """Test suite for DoubleEntry API endpoints."""

    # ========================================================================
    # POST /double-entries - Create
    # ========================================================================

    def test_create_double_entry_success(
        self,
        client,
        org_headers,
        test_supplier,
        test_customer,
        test_material,
        db_session,
    ):
        """Test successful double-entry creation with one line."""
        initial_supplier_balance = test_supplier.current_balance
        initial_customer_balance = test_customer.current_balance
        initial_material_stock = test_material.current_stock

        payload = {
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 500.5,
                    "purchase_unit_price": 8000.00,
                    "sale_unit_price": 10000.00,
                }
            ],
            "supplier_id": str(test_supplier.id),
            "customer_id": str(test_customer.id),
            "date": date.today().isoformat(),
            "invoice_number": "INV-TEST-001",
            "vehicle_plate": "XYZ-789",
            "notes": "Test double-entry operation",
            "commissions": [],
        }

        response = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert response.status_code == 201

        data = response.json()
        assert data["double_entry_number"] == 1
        assert data["status"] == "completed"
        assert data["invoice_number"] == "INV-TEST-001"
        assert data["vehicle_plate"] == "XYZ-789"
        assert data["supplier_name"] == "Metal Supplier Co."
        assert data["customer_name"] == "Customer Industries"

        # Verificar lineas
        assert len(data["lines"]) == 1
        line = data["lines"][0]
        assert line["material_code"] == "COPPER-01"
        assert line["material_name"] == "Copper Wire"
        assert float(line["quantity"]) == 500.5
        assert float(line["purchase_unit_price"]) == 8000.00
        assert float(line["sale_unit_price"]) == 10000.00

        # Verificar totales calculados
        assert float(data["total_purchase_cost"]) == 500.5 * 8000.00
        assert float(data["total_sale_amount"]) == 500.5 * 10000.00
        profit = (10000.00 - 8000.00) * 500.5
        assert float(data["profit"]) == profit
        assert float(data["profit_margin"]) == pytest.approx((profit / (500.5 * 8000.00)) * 100, rel=0.01)

        # Verificar materials_summary
        assert data["materials_summary"] == "Copper Wire"

        # Verify purchase_id and sale_id exist
        assert data["purchase_id"] is not None
        assert data["sale_id"] is not None

        # Refresh to get updated balances
        db_session.refresh(test_supplier)
        db_session.refresh(test_customer)
        db_session.refresh(test_material)

        # Verify balances updated
        expected_purchase_cost = Decimal("500.5") * Decimal("8000.00")
        expected_sale_amount = Decimal("500.5") * Decimal("10000.00")
        assert test_supplier.current_balance == initial_supplier_balance - expected_purchase_cost
        assert test_customer.current_balance == initial_customer_balance + expected_sale_amount

        # Verify material stock DID NOT change (no inventory movement)
        assert test_material.current_stock == initial_material_stock

        # Verify Purchase and Sale were created
        purchase = db_session.query(Purchase).filter(
            Purchase.id == data["purchase_id"]
        ).first()
        assert purchase is not None
        assert purchase.status == "liquidated"
        assert purchase.liquidated_at is not None
        assert str(purchase.double_entry_id) == data["id"]

        sale = db_session.query(Sale).filter(
            Sale.id == data["sale_id"]
        ).first()
        assert sale is not None
        assert sale.status == "liquidated"
        assert sale.liquidated_at is not None
        assert sale.warehouse_id is None
        assert str(sale.double_entry_id) == data["id"]

    def test_create_multi_line(
        self,
        client,
        org_headers,
        test_supplier,
        test_customer,
        test_material,
        test_material_2,
        db_session,
    ):
        """Test double-entry creation with multiple materials."""
        payload = {
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 1000.0,
                    "purchase_unit_price": 8000.00,
                    "sale_unit_price": 10000.00,
                },
                {
                    "material_id": str(test_material_2.id),
                    "quantity": 500.0,
                    "purchase_unit_price": 3000.00,
                    "sale_unit_price": 4000.00,
                },
            ],
            "supplier_id": str(test_supplier.id),
            "customer_id": str(test_customer.id),
            "date": date.today().isoformat(),
            "commissions": [],
        }

        response = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert response.status_code == 201

        data = response.json()
        assert len(data["lines"]) == 2

        # Verificar totales = suma de lineas
        expected_purchase = 1000.0 * 8000.0 + 500.0 * 3000.0  # 8M + 1.5M = 9.5M
        expected_sale = 1000.0 * 10000.0 + 500.0 * 4000.0  # 10M + 2M = 12M
        expected_profit = expected_sale - expected_purchase  # 2.5M

        assert float(data["total_purchase_cost"]) == expected_purchase
        assert float(data["total_sale_amount"]) == expected_sale
        assert float(data["profit"]) == expected_profit

        # Verificar materials_summary contiene ambos materiales
        assert "Copper Wire" in data["materials_summary"]
        assert "Aluminum Scrap" in data["materials_summary"]

        # Verificar que se crearon PurchaseLines y SaleLines correctamente
        purchase = db_session.query(Purchase).filter(
            Purchase.id == data["purchase_id"]
        ).first()
        assert purchase is not None
        assert len(purchase.lines) == 2

        sale = db_session.query(Sale).filter(
            Sale.id == data["sale_id"]
        ).first()
        assert sale is not None
        assert len(sale.lines) == 2

        # Verificar balances
        db_session.refresh(test_supplier)
        db_session.refresh(test_customer)
        assert test_supplier.current_balance == Decimal("0") - Decimal(str(expected_purchase))
        assert test_customer.current_balance == Decimal("0") + Decimal(str(expected_sale))

    def test_create_double_entry_with_commissions(
        self,
        client,
        org_headers,
        test_supplier,
        test_customer,
        test_material,
        test_commission_recipient,
        db_session,
    ):
        """Test double-entry creation with commissions."""
        payload = {
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 1000.0,
                    "purchase_unit_price": 8000.00,
                    "sale_unit_price": 10000.00,
                }
            ],
            "supplier_id": str(test_supplier.id),
            "customer_id": str(test_customer.id),
            "date": date.today().isoformat(),
            "commissions": [
                {
                    "third_party_id": str(test_commission_recipient.id),
                    "concept": "Sales Commission",
                    "commission_type": "percentage",
                    "commission_value": 2.5,
                }
            ],
        }

        response = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert response.status_code == 201

        data = response.json()
        assert len(data["commissions"]) == 1

        commission = data["commissions"][0]
        assert commission["concept"] == "Sales Commission"
        assert commission["commission_type"] == "percentage"
        assert float(commission["commission_value"]) == 2.5

        # Commission amount = 2.5% of sale total
        sale_total = 1000.0 * 10000.00
        expected_commission = sale_total * 0.025
        assert float(commission["commission_amount"]) == expected_commission
        assert commission["third_party_name"] == "Commission Agent"

        # Verify recipient balance IS updated (commissions paid immediately for DPs)
        db_session.refresh(test_commission_recipient)
        assert test_commission_recipient.current_balance == Decimal(str(expected_commission))

    def test_create_double_entry_same_supplier_customer_fails(
        self,
        client,
        org_headers,
        test_supplier_customer,
        test_material,
    ):
        """Test that supplier and customer cannot be the same party."""
        payload = {
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 100.0,
                    "purchase_unit_price": 8000.00,
                    "sale_unit_price": 10000.00,
                }
            ],
            "supplier_id": str(test_supplier_customer.id),
            "customer_id": str(test_supplier_customer.id),
            "date": date.today().isoformat(),
            "commissions": [],
        }

        response = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert response.status_code == 422

    def test_create_double_entry_negative_quantity_fails(
        self,
        client,
        org_headers,
        test_supplier,
        test_customer,
        test_material,
    ):
        """Test that negative quantity is rejected."""
        payload = {
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": -100.0,
                    "purchase_unit_price": 8000.00,
                    "sale_unit_price": 10000.00,
                }
            ],
            "supplier_id": str(test_supplier.id),
            "customer_id": str(test_customer.id),
            "date": date.today().isoformat(),
            "commissions": [],
        }

        response = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert response.status_code == 422

    def test_create_double_entry_zero_price_fails(
        self,
        client,
        org_headers,
        test_supplier,
        test_customer,
        test_material,
    ):
        """Test that zero or negative prices are rejected."""
        payload = {
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 100.0,
                    "purchase_unit_price": 0.00,
                    "sale_unit_price": 10000.00,
                }
            ],
            "supplier_id": str(test_supplier.id),
            "customer_id": str(test_customer.id),
            "date": date.today().isoformat(),
            "commissions": [],
        }

        response = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert response.status_code == 422

    def test_create_double_entry_empty_lines_fails(
        self,
        client,
        org_headers,
        test_supplier,
        test_customer,
    ):
        """Test that empty lines list is rejected (min_length=1)."""
        payload = {
            "lines": [],
            "supplier_id": str(test_supplier.id),
            "customer_id": str(test_customer.id),
            "date": date.today().isoformat(),
            "commissions": [],
        }

        response = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert response.status_code == 422

    def test_create_duplicate_material_in_lines_fails(
        self,
        client,
        org_headers,
        test_supplier,
        test_customer,
        test_material,
    ):
        """Test V-DP-02: duplicate material_id across lines is rejected."""
        payload = {
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 500.0,
                    "purchase_unit_price": 8000.00,
                    "sale_unit_price": 10000.00,
                },
                {
                    "material_id": str(test_material.id),  # Duplicado!
                    "quantity": 300.0,
                    "purchase_unit_price": 7500.00,
                    "sale_unit_price": 9500.00,
                },
            ],
            "supplier_id": str(test_supplier.id),
            "customer_id": str(test_customer.id),
            "date": date.today().isoformat(),
            "commissions": [],
        }

        response = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert response.status_code == 422

    def test_create_double_entry_invalid_supplier_fails(
        self,
        client,
        org_headers,
        test_customer,
        test_material,
    ):
        """Test that invalid supplier ID is rejected."""
        payload = {
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 100.0,
                    "purchase_unit_price": 8000.00,
                    "sale_unit_price": 10000.00,
                }
            ],
            "supplier_id": str(uuid4()),
            "customer_id": str(test_customer.id),
            "date": date.today().isoformat(),
            "commissions": [],
        }

        response = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert response.status_code == 404
        assert "supplier" in response.json()["detail"].lower()

    def test_create_double_entry_not_supplier_fails(
        self,
        client,
        org_headers,
        test_customer,
        test_material,
    ):
        """Test that ThirdParty without is_supplier=True is rejected."""
        payload = {
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 100.0,
                    "purchase_unit_price": 8000.00,
                    "sale_unit_price": 10000.00,
                }
            ],
            "supplier_id": str(test_customer.id),
            "customer_id": str(test_customer.id),
            "date": date.today().isoformat(),
            "commissions": [],
        }

        response = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert response.status_code == 422  # Pydantic: supplier == customer

    # ========================================================================
    # GET /double-entries - List with filters
    # ========================================================================

    def test_list_double_entries(
        self,
        client,
        org_headers,
        test_double_entry,
    ):
        """Test listing double-entries."""
        response = client.get("/api/v1/double-entries", headers=org_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == str(test_double_entry.id)
        assert data["items"][0]["double_entry_number"] == 1

    def test_list_double_entries_filter_by_status(
        self,
        client,
        org_headers,
        test_double_entry,
    ):
        """Test filtering by status."""
        response = client.get(
            "/api/v1/double-entries?status=completed",
            headers=org_headers,
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1

        response = client.get(
            "/api/v1/double-entries?status=cancelled",
            headers=org_headers,
        )
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_list_double_entries_filter_by_material(
        self,
        client,
        org_headers,
        test_double_entry,
        test_material,
    ):
        """Test filtering by material (via DoubleEntryLine subquery)."""
        response = client.get(
            f"/api/v1/double-entries?material_id={test_material.id}",
            headers=org_headers,
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1

        response = client.get(
            f"/api/v1/double-entries?material_id={uuid4()}",
            headers=org_headers,
        )
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_list_double_entries_filter_by_supplier(
        self,
        client,
        org_headers,
        test_double_entry,
        test_supplier,
    ):
        """Test filtering by supplier."""
        response = client.get(
            f"/api/v1/double-entries?supplier_id={test_supplier.id}",
            headers=org_headers,
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_list_double_entries_filter_by_customer(
        self,
        client,
        org_headers,
        test_double_entry,
        test_customer,
    ):
        """Test filtering by customer."""
        response = client.get(
            f"/api/v1/double-entries?customer_id={test_customer.id}",
            headers=org_headers,
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_list_double_entries_filter_by_date_range(
        self,
        client,
        org_headers,
        test_double_entry,
    ):
        """Test filtering by date range."""
        today = date.today()
        yesterday = date(today.year, today.month, today.day - 1) if today.day > 1 else today
        tomorrow = date(today.year, today.month, today.day + 1)

        response = client.get(
            f"/api/v1/double-entries?date_from={yesterday.isoformat()}&date_to={tomorrow.isoformat()}",
            headers=org_headers,
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1

        future_date = date(today.year + 1, 1, 1)
        response = client.get(
            f"/api/v1/double-entries?date_from={future_date.isoformat()}",
            headers=org_headers,
        )
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_list_double_entries_search(
        self,
        client,
        org_headers,
        test_double_entry,
    ):
        """Test search functionality."""
        response = client.get(
            f"/api/v1/double-entries?search={test_double_entry.double_entry_number}",
            headers=org_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

        found = any(item["id"] == str(test_double_entry.id) for item in data["items"])
        assert found, f"DoubleEntry {test_double_entry.id} not found in search results"

        response = client.get(
            "/api/v1/double-entries?search=INV-001",
            headers=org_headers,
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1

        response = client.get(
            "/api/v1/double-entries?search=Test double-entry",
            headers=org_headers,
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1

        response = client.get(
            "/api/v1/double-entries?search=NONEXISTENT",
            headers=org_headers,
        )
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_list_double_entries_pagination(
        self,
        client,
        org_headers,
        test_double_entry,
    ):
        """Test pagination."""
        response = client.get(
            "/api/v1/double-entries?skip=0&limit=10",
            headers=org_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["skip"] == 0
        assert data["limit"] == 10

    # ========================================================================
    # GET /double-entries/{id} - Get by UUID
    # ========================================================================

    def test_get_double_entry_by_id(
        self,
        client,
        org_headers,
        test_double_entry,
    ):
        """Test getting double-entry by UUID."""
        response = client.get(
            f"/api/v1/double-entries/{test_double_entry.id}",
            headers=org_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == str(test_double_entry.id)
        assert data["double_entry_number"] == 1
        assert data["status"] == "completed"
        assert data["supplier_name"] == "Metal Supplier Co."
        assert data["customer_name"] == "Customer Industries"

        # Verificar lineas
        assert len(data["lines"]) == 1
        assert data["lines"][0]["material_code"] == "COPPER-01"
        assert data["materials_summary"] == "Copper Wire"

    def test_get_double_entry_by_id_not_found(
        self,
        client,
        org_headers,
    ):
        """Test getting non-existent double-entry."""
        response = client.get(
            f"/api/v1/double-entries/{uuid4()}",
            headers=org_headers,
        )
        assert response.status_code == 404

    # ========================================================================
    # GET /double-entries/by-number/{number} - Get by sequential number
    # ========================================================================

    def test_get_double_entry_by_number(
        self,
        client,
        org_headers,
        test_double_entry,
    ):
        """Test getting double-entry by sequential number."""
        response = client.get(
            "/api/v1/double-entries/by-number/1",
            headers=org_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == str(test_double_entry.id)
        assert data["double_entry_number"] == 1

    def test_get_double_entry_by_number_not_found(
        self,
        client,
        org_headers,
    ):
        """Test getting double-entry by non-existent number."""
        response = client.get(
            "/api/v1/double-entries/by-number/999",
            headers=org_headers,
        )
        assert response.status_code == 404

    # ========================================================================
    # GET /double-entries/supplier/{id} - List by supplier
    # ========================================================================

    def test_get_double_entries_by_supplier(
        self,
        client,
        org_headers,
        test_double_entry,
        test_supplier,
    ):
        """Test listing double-entries by supplier."""
        response = client.get(
            f"/api/v1/double-entries/supplier/{test_supplier.id}",
            headers=org_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["supplier_name"] == "Metal Supplier Co."

    # ========================================================================
    # GET /double-entries/customer/{id} - List by customer
    # ========================================================================

    def test_get_double_entries_by_customer(
        self,
        client,
        org_headers,
        test_double_entry,
        test_customer,
    ):
        """Test listing double-entries by customer."""
        response = client.get(
            f"/api/v1/double-entries/customer/{test_customer.id}",
            headers=org_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["customer_name"] == "Customer Industries"

    # ========================================================================
    # PATCH /double-entries/{id}/cancel - Cancel
    # ========================================================================

    def test_cancel_double_entry_success(
        self,
        client,
        org_headers,
        test_double_entry,
        test_supplier,
        test_customer,
        test_material,
        db_session,
    ):
        """Test cancelling a double-entry operation."""
        initial_supplier_balance = test_supplier.current_balance
        initial_customer_balance = test_customer.current_balance
        initial_material_stock = test_material.current_stock

        response = client.patch(
            f"/api/v1/double-entries/{test_double_entry.id}/cancel",
            headers=org_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "cancelled"

        db_session.refresh(test_supplier)
        db_session.refresh(test_customer)
        db_session.refresh(test_material)

        # Verify balances reverted
        purchase_cost = Decimal("8000000.00")
        sale_amount = Decimal("10000000.00")
        assert test_supplier.current_balance == initial_supplier_balance + purchase_cost
        assert test_customer.current_balance == initial_customer_balance - sale_amount

        # Verify material stock did NOT change
        assert test_material.current_stock == initial_material_stock

        # Verify Purchase and Sale are cancelled
        purchase = db_session.query(Purchase).filter(
            Purchase.id == test_double_entry.purchase_id
        ).first()
        assert purchase.status == "cancelled"

        sale = db_session.query(Sale).filter(
            Sale.id == test_double_entry.sale_id
        ).first()
        assert sale.status == "cancelled"

    def test_cancel_multi_line_reverts_balances(
        self,
        client,
        org_headers,
        test_supplier,
        test_customer,
        test_material,
        test_material_2,
        db_session,
    ):
        """Test cancelling a multi-line double-entry reverts all balances correctly."""
        # Crear DP multi-linea primero
        payload = {
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 1000.0,
                    "purchase_unit_price": 8000.00,
                    "sale_unit_price": 10000.00,
                },
                {
                    "material_id": str(test_material_2.id),
                    "quantity": 500.0,
                    "purchase_unit_price": 3000.00,
                    "sale_unit_price": 4000.00,
                },
            ],
            "supplier_id": str(test_supplier.id),
            "customer_id": str(test_customer.id),
            "date": date.today().isoformat(),
            "commissions": [],
        }

        create_resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert create_resp.status_code == 201
        de_id = create_resp.json()["id"]

        db_session.refresh(test_supplier)
        db_session.refresh(test_customer)
        supplier_after_create = test_supplier.current_balance
        customer_after_create = test_customer.current_balance

        # Cancelar
        cancel_resp = client.patch(
            f"/api/v1/double-entries/{de_id}/cancel",
            headers=org_headers,
        )
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["status"] == "cancelled"

        db_session.refresh(test_supplier)
        db_session.refresh(test_customer)

        # Saldos deben volver a 0
        expected_purchase = Decimal("1000") * Decimal("8000") + Decimal("500") * Decimal("3000")
        expected_sale = Decimal("1000") * Decimal("10000") + Decimal("500") * Decimal("4000")
        assert test_supplier.current_balance == supplier_after_create + expected_purchase
        assert test_customer.current_balance == customer_after_create - expected_sale

    def test_cancel_already_cancelled_double_entry_fails(
        self,
        client,
        org_headers,
        test_double_entry,
        db_session,
    ):
        """Test that cancelling an already cancelled double-entry fails."""
        test_double_entry.status = "cancelled"
        db_session.commit()

        response = client.patch(
            f"/api/v1/double-entries/{test_double_entry.id}/cancel",
            headers=org_headers,
        )
        assert response.status_code == 400
        assert "already cancelled" in response.json()["detail"].lower()

    def test_cancel_with_commissions_reverts_balances(
        self,
        client,
        org_headers,
        test_supplier,
        test_customer,
        test_material,
        test_commission_recipient,
        db_session,
    ):
        """Test that cancelling a DP with commissions reverts commission recipient balance."""
        payload = {
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 1000.0,
                    "purchase_unit_price": 8000.00,
                    "sale_unit_price": 10000.00,
                }
            ],
            "supplier_id": str(test_supplier.id),
            "customer_id": str(test_customer.id),
            "date": date.today().isoformat(),
            "commissions": [
                {
                    "third_party_id": str(test_commission_recipient.id),
                    "concept": "Sales Commission",
                    "commission_type": "percentage",
                    "commission_value": 2.5,
                }
            ],
        }

        # Crear DP con comisiones
        create_resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert create_resp.status_code == 201
        de_id = create_resp.json()["id"]

        # Verificar que la comision fue pagada
        db_session.refresh(test_commission_recipient)
        sale_total = Decimal("1000") * Decimal("10000")
        expected_commission = sale_total * Decimal("0.025")
        assert test_commission_recipient.current_balance == expected_commission

        # Cancelar
        cancel_resp = client.patch(
            f"/api/v1/double-entries/{de_id}/cancel",
            headers=org_headers,
        )
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["status"] == "cancelled"

        # Verificar que el saldo del comisionista volvio a 0
        db_session.refresh(test_commission_recipient)
        assert test_commission_recipient.current_balance == Decimal("0.00")

    # ========================================================================
    # PATCH /double-entries/{id} - Update metadata
    # ========================================================================

    def test_update_double_entry_metadata(
        self,
        client,
        org_headers,
        test_double_entry,
    ):
        """Test updating double-entry metadata."""
        payload = {
            "notes": "Updated notes",
            "invoice_number": "INV-UPDATED",
            "vehicle_plate": "NEW-PLATE",
        }

        response = client.patch(
            f"/api/v1/double-entries/{test_double_entry.id}",
            json=payload,
            headers=org_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["notes"] == "Updated notes"
        assert data["invoice_number"] == "INV-UPDATED"
        assert data["vehicle_plate"] == "NEW-PLATE"
        assert data["status"] == "completed"
        # Verificar que las lineas siguen intactas
        assert len(data["lines"]) == 1
        assert float(data["lines"][0]["quantity"]) == 1000.0

    def test_update_double_entry_partial(
        self,
        client,
        org_headers,
        test_double_entry,
    ):
        """Test partial update (only some fields)."""
        payload = {
            "notes": "Only notes updated",
        }

        response = client.patch(
            f"/api/v1/double-entries/{test_double_entry.id}",
            json=payload,
            headers=org_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["notes"] == "Only notes updated"
        assert data["invoice_number"] == "INV-001"
        assert data["vehicle_plate"] == "ABC-123"

    def test_update_double_entry_not_found(
        self,
        client,
        org_headers,
    ):
        """Test updating non-existent double-entry."""
        payload = {
            "notes": "New notes",
        }

        response = client.patch(
            f"/api/v1/double-entries/{uuid4()}",
            json=payload,
            headers=org_headers,
        )
        assert response.status_code == 404
