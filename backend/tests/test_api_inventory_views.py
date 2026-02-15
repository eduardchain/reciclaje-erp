"""
Tests for Inventory Views API endpoints.

Tests all 5 read-only endpoints:
1. GET /api/v1/inventory/stock        - Consolidated stock view
2. GET /api/v1/inventory/stock/{id}   - Material stock detail with warehouse breakdown
3. GET /api/v1/inventory/transit      - Materials with stock in transit
4. GET /api/v1/inventory/movements    - Movement history with filters
5. GET /api/v1/inventory/valuation    - Inventory valuation
"""
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.models import Material, Warehouse
from app.models.inventory_movement import InventoryMovement


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def materials_with_stock(db_session, test_organization):
    """Create 2 materials: one with liquidated stock, one with transit stock."""
    m1 = Material(
        id=uuid4(),
        code="CU-001",
        name="Cobre",
        default_unit="kg",
        current_stock=Decimal("200.0000"),
        current_stock_liquidated=Decimal("200.0000"),
        current_stock_transit=Decimal("0"),
        current_average_cost=Decimal("50.0000"),
        organization_id=test_organization.id,
        is_active=True,
    )
    m2 = Material(
        id=uuid4(),
        code="FE-001",
        name="Hierro",
        default_unit="kg",
        current_stock=Decimal("300.0000"),
        current_stock_liquidated=Decimal("100.0000"),
        current_stock_transit=Decimal("200.0000"),
        current_average_cost=Decimal("20.0000"),
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add_all([m1, m2])
    db_session.commit()
    db_session.refresh(m1)
    db_session.refresh(m2)
    return m1, m2


@pytest.fixture
def test_warehouse(db_session, test_organization):
    """Create a primary test warehouse."""
    wh = Warehouse(
        id=uuid4(),
        name="Bodega Principal",
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(wh)
    db_session.commit()
    db_session.refresh(wh)
    return wh


@pytest.fixture
def test_warehouse2(db_session, test_organization):
    """Create a secondary test warehouse."""
    wh = Warehouse(
        id=uuid4(),
        name="Bodega Secundaria",
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(wh)
    db_session.commit()
    db_session.refresh(wh)
    return wh


# ============================================================================
# Test Classes
# ============================================================================

class TestStockConsolidated:
    """Tests for GET /api/v1/inventory/stock"""

    def test_stock_consolidated(
        self,
        client,
        org_headers,
        materials_with_stock,
    ):
        """Verify consolidated stock lists both materials with correct values."""
        m1, m2 = materials_with_stock

        # Act
        response = client.get("/api/v1/inventory/stock", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

        # Build lookup by material_id for flexible ordering
        items_map = {item["material_id"]: item for item in data["items"]}

        cu = items_map[str(m1.id)]
        assert cu["material_code"] == "CU-001"
        assert cu["material_name"] == "Cobre"
        assert cu["current_stock_liquidated"] == 200.0
        assert cu["current_stock_transit"] == 0.0
        assert cu["current_stock_total"] == 200.0
        assert cu["current_average_cost"] == 50.0
        assert cu["total_value"] == 10000.0  # 200 * 50
        assert cu["is_active"] is True

        fe = items_map[str(m2.id)]
        assert fe["material_code"] == "FE-001"
        assert fe["current_stock_liquidated"] == 100.0
        assert fe["current_stock_transit"] == 200.0
        assert fe["current_stock_total"] == 300.0
        assert fe["current_average_cost"] == 20.0
        assert fe["total_value"] == 2000.0  # 100 * 20

    def test_stock_consolidated_total_valuation(
        self,
        client,
        org_headers,
        materials_with_stock,
    ):
        """Verify total_valuation = sum(stock_liquidated * avg_cost) for all materials."""
        m1, m2 = materials_with_stock

        # Act
        response = client.get("/api/v1/inventory/stock", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()

        # m1: 200 * 50 = 10000, m2: 100 * 20 = 2000
        expected_valuation = 12000.0
        assert data["total_valuation"] == expected_valuation

        # Also verify sum of item-level total_value matches
        item_sum = sum(item["total_value"] for item in data["items"])
        assert item_sum == expected_valuation


class TestStockDetail:
    """Tests for GET /api/v1/inventory/stock/{material_id}"""

    def test_material_stock_detail_with_warehouse_breakdown(
        self,
        client,
        org_headers,
        db_session,
        test_organization,
        test_warehouse,
        test_warehouse2,
    ):
        """Create a material with movements in 2 warehouses and verify breakdown."""
        # Arrange -- create material
        material = Material(
            id=uuid4(),
            code="AL-001",
            name="Aluminio",
            default_unit="kg",
            current_stock=Decimal("250.0000"),
            current_stock_liquidated=Decimal("250.0000"),
            current_stock_transit=Decimal("0"),
            current_average_cost=Decimal("30.0000"),
            organization_id=test_organization.id,
            is_active=True,
        )
        db_session.add(material)
        db_session.commit()
        db_session.refresh(material)

        # Arrange -- create inventory movements in 2 warehouses
        mov1 = InventoryMovement(
            id=uuid4(),
            organization_id=test_organization.id,
            material_id=material.id,
            warehouse_id=test_warehouse.id,
            movement_type="purchase",
            quantity=Decimal("100.000"),
            unit_cost=Decimal("30.00"),
            reference_type="purchase",
            date=datetime.now(timezone.utc),
        )
        mov2 = InventoryMovement(
            id=uuid4(),
            organization_id=test_organization.id,
            material_id=material.id,
            warehouse_id=test_warehouse2.id,
            movement_type="purchase",
            quantity=Decimal("150.000"),
            unit_cost=Decimal("30.00"),
            reference_type="purchase",
            date=datetime.now(timezone.utc),
        )
        db_session.add_all([mov1, mov2])
        db_session.commit()

        # Act
        response = client.get(
            f"/api/v1/inventory/stock/{material.id}",
            headers=org_headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["material_id"] == str(material.id)
        assert data["material_code"] == "AL-001"
        assert data["material_name"] == "Aluminio"
        assert data["current_stock_liquidated"] == 250.0
        assert data["current_stock_total"] == 250.0
        assert data["current_average_cost"] == 30.0
        assert data["total_value"] == 7500.0  # 250 * 30

        # Verify warehouse breakdown
        assert len(data["warehouses"]) == 2
        wh_map = {w["warehouse_id"]: w for w in data["warehouses"]}

        wh1 = wh_map[str(test_warehouse.id)]
        assert wh1["warehouse_name"] == "Bodega Principal"
        assert wh1["stock"] == 100.0

        wh2 = wh_map[str(test_warehouse2.id)]
        assert wh2["warehouse_name"] == "Bodega Secundaria"
        assert wh2["stock"] == 150.0


class TestTransit:
    """Tests for GET /api/v1/inventory/transit"""

    def test_transit_stock(
        self,
        client,
        org_headers,
        materials_with_stock,
    ):
        """Only materials with stock_transit > 0 should appear in transit list."""
        m1, m2 = materials_with_stock
        # m1 (Cobre) has transit=0, m2 (Hierro) has transit=200

        # Act
        response = client.get("/api/v1/inventory/transit", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

        transit_item = data["items"][0]
        assert transit_item["material_id"] == str(m2.id)
        assert transit_item["material_code"] == "FE-001"
        assert transit_item["material_name"] == "Hierro"
        assert transit_item["current_stock_transit"] == 200.0
        assert transit_item["current_stock_liquidated"] == 100.0


class TestMovements:
    """Tests for GET /api/v1/inventory/movements"""

    def test_list_movements_with_filters(
        self,
        client,
        org_headers,
        db_session,
        test_organization,
        test_warehouse,
    ):
        """Create movements for 2 materials and filter by material_id."""
        # Arrange -- create 2 materials
        mat_a = Material(
            id=uuid4(),
            code="MAT-A",
            name="Material A",
            default_unit="kg",
            current_stock=Decimal("0"),
            current_stock_liquidated=Decimal("0"),
            current_stock_transit=Decimal("0"),
            current_average_cost=Decimal("0"),
            organization_id=test_organization.id,
            is_active=True,
        )
        mat_b = Material(
            id=uuid4(),
            code="MAT-B",
            name="Material B",
            default_unit="kg",
            current_stock=Decimal("0"),
            current_stock_liquidated=Decimal("0"),
            current_stock_transit=Decimal("0"),
            current_average_cost=Decimal("0"),
            organization_id=test_organization.id,
            is_active=True,
        )
        db_session.add_all([mat_a, mat_b])
        db_session.commit()
        db_session.refresh(mat_a)
        db_session.refresh(mat_b)

        # Arrange -- create movements: 2 for mat_a, 1 for mat_b
        mov_a1 = InventoryMovement(
            id=uuid4(),
            organization_id=test_organization.id,
            material_id=mat_a.id,
            warehouse_id=test_warehouse.id,
            movement_type="purchase",
            quantity=Decimal("50.000"),
            unit_cost=Decimal("10.00"),
            reference_type="purchase",
            date=datetime.now(timezone.utc),
        )
        mov_a2 = InventoryMovement(
            id=uuid4(),
            organization_id=test_organization.id,
            material_id=mat_a.id,
            warehouse_id=test_warehouse.id,
            movement_type="purchase",
            quantity=Decimal("30.000"),
            unit_cost=Decimal("12.00"),
            reference_type="purchase",
            date=datetime.now(timezone.utc),
        )
        mov_b1 = InventoryMovement(
            id=uuid4(),
            organization_id=test_organization.id,
            material_id=mat_b.id,
            warehouse_id=test_warehouse.id,
            movement_type="purchase",
            quantity=Decimal("70.000"),
            unit_cost=Decimal("15.00"),
            reference_type="purchase",
            date=datetime.now(timezone.utc),
        )
        db_session.add_all([mov_a1, mov_a2, mov_b1])
        db_session.commit()

        # Act -- filter by mat_a
        response = client.get(
            "/api/v1/inventory/movements",
            params={"material_id": str(mat_a.id)},
            headers=org_headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["skip"] == 0
        assert data["limit"] == 100

        # All returned items should belong to mat_a
        for item in data["items"]:
            assert item["material_id"] == str(mat_a.id)
            assert item["material_code"] == "MAT-A"
            assert item["warehouse_name"] == "Bodega Principal"

        # Act -- unfiltered should return all 3
        response_all = client.get(
            "/api/v1/inventory/movements",
            headers=org_headers,
        )
        assert response_all.status_code == 200
        assert response_all.json()["total"] == 3


class TestValuation:
    """Tests for GET /api/v1/inventory/valuation"""

    def test_valuation(
        self,
        client,
        org_headers,
        materials_with_stock,
    ):
        """Verify valuation returns materials with stock and correct totals."""
        m1, m2 = materials_with_stock
        # m1: liquidated=200, avg_cost=50 -> value=10000
        # m2: liquidated=100, avg_cost=20 -> value=2000

        # Act
        response = client.get("/api/v1/inventory/valuation", headers=org_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Both materials have current_stock_liquidated > 0, so both appear
        assert data["total_materials"] == 2
        assert len(data["items"]) == 2
        assert data["total_valuation"] == 12000.0  # 10000 + 2000

        items_map = {item["material_id"]: item for item in data["items"]}

        cu = items_map[str(m1.id)]
        assert cu["material_code"] == "CU-001"
        assert cu["current_stock_liquidated"] == 200.0
        assert cu["current_average_cost"] == 50.0
        assert cu["total_value"] == 10000.0

        fe = items_map[str(m2.id)]
        assert fe["material_code"] == "FE-001"
        assert fe["current_stock_liquidated"] == 100.0
        assert fe["current_average_cost"] == 20.0
        assert fe["total_value"] == 2000.0
