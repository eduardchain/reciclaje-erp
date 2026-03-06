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
- Creates Purchase (status='registered') without inventory movements
- Creates Sale (status='registered') without inventory movements
- Updates supplier balance (debt increases)
- Updates customer balance (receivable increases)
- Creates commissions (NOT paid until sale is liquidated)
- Validates supplier != customer
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
        current_stock=Decimal("0.00"),  # No stock
        current_average_cost=Decimal("7500.00"),  # Average cost (irrelevant for double-entry)
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
    """Create a test double-entry operation."""
    # Create Purchase first (no warehouse for double-entry)
    purchase = Purchase(
        id=uuid4(),
        organization_id=test_organization.id,
        purchase_number=1,
        supplier_id=test_supplier.id,
        date=datetime.now(),
        total_amount=Decimal("8000000.00"),  # 1000 kg × $8000/kg
        status="registered",
        notes="Test purchase for double-entry",
    )
    db_session.add(purchase)
    db_session.flush()

    # Create Sale (no warehouse for double-entry)
    sale = Sale(
        id=uuid4(),
        organization_id=test_organization.id,
        sale_number=1,
        customer_id=test_customer.id,
        warehouse_id=None,  # NULL for double-entry operations
        date=datetime.now(),
        invoice_number="INV-001",
        vehicle_plate="ABC-123",
        total_amount=Decimal("10000000.00"),  # 1000 kg × $10000/kg
        status="registered",
        notes="Test sale for double-entry",
    )
    db_session.add(sale)
    db_session.flush()

    # Create DoubleEntry
    double_entry = DoubleEntry(
        id=uuid4(),
        organization_id=test_organization.id,
        double_entry_number=1,
        date=date.today(),
        material_id=test_material.id,
        quantity=Decimal("1000.000"),
        supplier_id=test_supplier.id,
        purchase_unit_price=Decimal("8000.00"),
        customer_id=test_customer.id,
        sale_unit_price=Decimal("10000.00"),
        invoice_number="INV-001",
        vehicle_plate="ABC-123",
        notes="Test double-entry",
        purchase_id=purchase.id,
        sale_id=sale.id,
        status="completed",
    )
    db_session.add(double_entry)
    db_session.flush()  # Ensure double_entry.id is available

    # Update balances
    test_supplier.current_balance -= Decimal("8000000.00")  # Debt
    test_customer.current_balance += Decimal("10000000.00")  # Receivable

    # Link double_entry_id (now safe because double_entry exists)
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
        """Test successful double-entry creation."""
        # Get initial balances
        initial_supplier_balance = test_supplier.current_balance
        initial_customer_balance = test_customer.current_balance
        initial_material_stock = test_material.current_stock

        payload = {
            "material_id": str(test_material.id),
            "quantity": 500.5,
            "supplier_id": str(test_supplier.id),
            "purchase_unit_price": 8000.00,
            "customer_id": str(test_customer.id),
            "sale_unit_price": 10000.00,
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
        assert float(data["quantity"]) == 500.5
        assert float(data["purchase_unit_price"]) == 8000.00
        assert float(data["sale_unit_price"]) == 10000.00
        assert data["invoice_number"] == "INV-TEST-001"
        assert data["vehicle_plate"] == "XYZ-789"
        assert data["material_code"] == "COPPER-01"
        assert data["material_name"] == "Copper Wire"
        assert data["supplier_name"] == "Metal Supplier Co."
        assert data["customer_name"] == "Customer Industries"

        # Verify calculated properties
        assert float(data["total_purchase_cost"]) == 500.5 * 8000.00
        assert float(data["total_sale_amount"]) == 500.5 * 10000.00
        profit = (10000.00 - 8000.00) * 500.5
        assert float(data["profit"]) == profit
        assert float(data["profit_margin"]) == pytest.approx((profit / (500.5 * 8000.00)) * 100, rel=0.01)

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
        assert purchase.status == "registered"
        assert str(purchase.double_entry_id) == data["id"]

        sale = db_session.query(Sale).filter(
            Sale.id == data["sale_id"]
        ).first()
        assert sale is not None
        assert sale.status == "registered"
        assert sale.warehouse_id is None  # NULL for double-entry operations (no physical inventory)
        assert str(sale.double_entry_id) == data["id"]

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
            "material_id": str(test_material.id),
            "quantity": 1000.0,
            "supplier_id": str(test_supplier.id),
            "purchase_unit_price": 8000.00,
            "customer_id": str(test_customer.id),
            "sale_unit_price": 10000.00,
            "date": date.today().isoformat(),
            "commissions": [
                {
                    "third_party_id": str(test_commission_recipient.id),
                    "concept": "Sales Commission",
                    "commission_type": "percentage",
                    "commission_value": 2.5,  # 2.5%
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

        # Verify recipient balance NOT updated (commissions paid when sale is liquidated)
        db_session.refresh(test_commission_recipient)
        assert test_commission_recipient.current_balance == Decimal("0.00")

    def test_create_double_entry_same_supplier_customer_fails(
        self,
        client,
        org_headers,
        test_supplier_customer,
        test_material,
    ):
        """Test that supplier and customer cannot be the same party."""
        payload = {
            "material_id": str(test_material.id),
            "quantity": 100.0,
            "supplier_id": str(test_supplier_customer.id),
            "purchase_unit_price": 8000.00,
            "customer_id": str(test_supplier_customer.id),  # Same as supplier!
            "sale_unit_price": 10000.00,
            "date": date.today().isoformat(),
            "commissions": [],
        }

        response = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert response.status_code == 422  # Pydantic validation error
        # The error comes from the validator, not HTTP 400

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
            "material_id": str(test_material.id),
            "quantity": -100.0,  # Negative!
            "supplier_id": str(test_supplier.id),
            "purchase_unit_price": 8000.00,
            "customer_id": str(test_customer.id),
            "sale_unit_price": 10000.00,
            "date": date.today().isoformat(),
            "commissions": [],
        }

        response = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert response.status_code == 422  # Validation error

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
            "material_id": str(test_material.id),
            "quantity": 100.0,
            "supplier_id": str(test_supplier.id),
            "purchase_unit_price": 0.00,  # Zero!
            "customer_id": str(test_customer.id),
            "sale_unit_price": 10000.00,
            "date": date.today().isoformat(),
            "commissions": [],
        }

        response = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert response.status_code == 422  # Validation error

    def test_create_double_entry_invalid_supplier_fails(
        self,
        client,
        org_headers,
        test_customer,
        test_material,
    ):
        """Test that invalid supplier ID is rejected."""
        payload = {
            "material_id": str(test_material.id),
            "quantity": 100.0,
            "supplier_id": str(uuid4()),  # Non-existent supplier
            "purchase_unit_price": 8000.00,
            "customer_id": str(test_customer.id),
            "sale_unit_price": 10000.00,
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
            "material_id": str(test_material.id),
            "quantity": 100.0,
            "supplier_id": str(test_customer.id),  # Customer, not supplier!
            "purchase_unit_price": 8000.00,
            "customer_id": str(test_customer.id),
            "sale_unit_price": 10000.00,
            "date": date.today().isoformat(),
            "commissions": [],
        }

        response = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert response.status_code == 422  # Pydantic validation error

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
        # Filter completed
        response = client.get(
            "/api/v1/double-entries?status=completed",
            headers=org_headers,
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1

        # Filter cancelled (should be empty)
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
        """Test filtering by material."""
        response = client.get(
            f"/api/v1/double-entries?material_id={test_material.id}",
            headers=org_headers,
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1

        # Filter by non-existent material
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

        # Filter with date range that includes today
        response = client.get(
            f"/api/v1/double-entries?date_from={yesterday.isoformat()}&date_to={tomorrow.isoformat()}",
            headers=org_headers,
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1

        # Filter with future dates (should be empty)
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
        # Search by double_entry_number
        response = client.get(
            f"/api/v1/double-entries?search={test_double_entry.double_entry_number}",
            headers=org_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1  # At least one result
        
        # Verify the found entry matches
        found = False
        for item in data["items"]:
            if item["id"] == str(test_double_entry.id):
                found = True
                break
        assert found, f"DoubleEntry {test_double_entry.id} not found in search results"

        # Search by invoice_number
        response = client.get(
            "/api/v1/double-entries?search=INV-001",
            headers=org_headers,
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1

        # Search by notes
        response = client.get(
            "/api/v1/double-entries?search=Test double-entry",
            headers=org_headers,
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1

        # Search non-existent
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
        assert data["material_code"] == "COPPER-01"
        assert data["supplier_name"] == "Metal Supplier Co."
        assert data["customer_name"] == "Customer Industries"

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
        # Get balances before cancel
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

        # Refresh to get updated data
        db_session.refresh(test_supplier)
        db_session.refresh(test_customer)
        db_session.refresh(test_material)

        # Verify balances reverted
        purchase_cost = Decimal("8000000.00")
        sale_amount = Decimal("10000000.00")
        assert test_supplier.current_balance == initial_supplier_balance + purchase_cost
        assert test_customer.current_balance == initial_customer_balance - sale_amount

        # Verify material stock did NOT change (no inventory movements)
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

    def test_cancel_already_cancelled_double_entry_fails(
        self,
        client,
        org_headers,
        test_double_entry,
        db_session,
    ):
        """Test that cancelling an already cancelled double-entry fails."""
        # Cancel first time
        test_double_entry.status = "cancelled"
        db_session.commit()

        # Try to cancel again
        response = client.patch(
            f"/api/v1/double-entries/{test_double_entry.id}/cancel",
            headers=org_headers,
        )
        assert response.status_code == 400
        assert "already cancelled" in response.json()["detail"].lower()

    def test_cancel_double_entry_with_paid_purchase_fails(
        self,
        client,
        org_headers,
        test_double_entry,
        db_session,
    ):
        """Test that cancelling fails if Purchase is liquidated."""
        # Mark purchase as liquidated
        purchase = db_session.query(Purchase).filter(
            Purchase.id == test_double_entry.purchase_id
        ).first()
        purchase.status = "liquidated"
        db_session.commit()

        response = client.patch(
            f"/api/v1/double-entries/{test_double_entry.id}/cancel",
            headers=org_headers,
        )
        assert response.status_code == 400
        assert "liquidat" in response.json()["detail"].lower()

    def test_cancel_double_entry_with_paid_sale_fails(
        self,
        client,
        org_headers,
        test_double_entry,
        db_session,
    ):
        """Test that cancelling fails if Sale is liquidated."""
        sale = db_session.query(Sale).filter(
            Sale.id == test_double_entry.sale_id
        ).first()
        sale.status = "liquidated"
        db_session.commit()

        response = client.patch(
            f"/api/v1/double-entries/{test_double_entry.id}/cancel",
            headers=org_headers,
        )
        assert response.status_code == 400
        assert "liquidated" in response.json()["detail"].lower()

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
        # Other fields unchanged
        assert data["status"] == "completed"
        assert float(data["quantity"]) == 1000.0

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
        # Original values preserved
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

    # TODO: Implement DELETE endpoints for purchases and sales to test these validations
    # def test_cannot_delete_purchase_with_double_entry(
    #     self,
    #     client,
    #     org_headers,
    #     test_double_entry,
    # ):
    #     """Test that Purchase with double_entry_id cannot be deleted."""
    #     # Try to delete the purchase that belongs to double-entry
    #     response = client.delete(
    #         f"/api/v1/purchases/{test_double_entry.purchase_id}",
    #         headers=org_headers,
    #     )
    #     assert response.status_code == 400
    #     assert "double-entry" in response.json()["detail"].lower()

    # def test_cannot_delete_sale_with_double_entry(
    #     self,
    #     client,
    #     org_headers,
    #     test_double_entry,
    # ):
    #     """Test that Sale with double_entry_id cannot be deleted."""
    #     # Try to delete the sale that belongs to double-entry
    #     response = client.delete(
    #         f"/api/v1/sales/{test_double_entry.sale_id}",
    #         headers=org_headers,
    #     )
    #     assert response.status_code == 400
    #     assert "double-entry" in response.json()["detail"].lower()

