"""
Comprehensive tests for Inventory Adjustment API endpoints.

Tests all 9 endpoints:
1. POST /api/v1/inventory/adjustments/increase — increase stock
2. POST /api/v1/inventory/adjustments/decrease — decrease stock
3. POST /api/v1/inventory/adjustments/recount — physical count
4. POST /api/v1/inventory/adjustments/zero-out — set stock to zero
5. POST /api/v1/inventory/adjustments/{id}/annul — annul adjustment
6. POST /api/v1/inventory/adjustments/warehouse-transfer — transfer between warehouses
7. GET /api/v1/inventory/adjustments — list with filters
8. GET /api/v1/inventory/adjustments/by-number/{number} — get by number
9. GET /api/v1/inventory/adjustments/{id} — get by ID
"""
import pytest
from decimal import Decimal
from uuid import uuid4

from app.models import Material, Warehouse, InventoryMovement


# ============================================================================
# Fixtures
# ============================================================================

BASE_URL = "/api/v1/inventory/adjustments"


@pytest.fixture
def test_material(db_session, test_organization):
    """Create a test material with existing stock and average cost."""
    material = Material(
        code="CU-001",
        name="Cobre",
        default_unit="kg",
        current_stock=Decimal("200.0000"),
        current_stock_liquidated=Decimal("200.0000"),
        current_stock_transit=Decimal("0"),
        current_average_cost=Decimal("40.0000"),
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)
    return material


@pytest.fixture
def test_material_zero(db_session, test_organization):
    """Create a test material with zero stock."""
    material = Material(
        code="AL-001",
        name="Aluminio",
        default_unit="kg",
        current_stock=Decimal("0"),
        current_stock_liquidated=Decimal("0"),
        current_stock_transit=Decimal("0"),
        current_average_cost=Decimal("0"),
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
        name="Bodega Principal",
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(warehouse)
    db_session.commit()
    db_session.refresh(warehouse)
    return warehouse


@pytest.fixture
def test_warehouse2(db_session, test_organization):
    """Create a second test warehouse for transfer tests."""
    warehouse = Warehouse(
        name="Bodega Secundaria",
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(warehouse)
    db_session.commit()
    db_session.refresh(warehouse)
    return warehouse


# ============================================================================
# Test Classes
# ============================================================================


class TestIncrease:
    """Tests for POST /api/v1/inventory/adjustments/increase"""

    def test_increase_success(
        self, client, org_headers, test_material, test_warehouse
    ):
        """Create an increase adjustment with qty=100, cost=50 and verify response fields."""
        payload = {
            "material_id": str(test_material.id),
            "warehouse_id": str(test_warehouse.id),
            "quantity": 100.0,
            "unit_cost": 50.0,
            "date": "2026-02-14T10:00:00Z",
            "reason": "Material encontrado en bodega",
            "notes": "Inventario fisico",
        }

        response = client.post(f"{BASE_URL}/increase", json=payload, headers=org_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["adjustment_type"] == "increase"
        assert data["status"] == "confirmed"
        assert data["previous_stock"] == 200.0
        assert data["quantity"] == 100.0
        assert data["new_stock"] == 300.0
        assert data["unit_cost"] == 50.0
        assert data["total_value"] == 5000.0
        assert data["reason"] == "Material encontrado en bodega"
        assert data["notes"] == "Inventario fisico"
        assert data["material_code"] == "CU-001"
        assert data["material_name"] == "Cobre"
        assert data["warehouse_name"] == "Bodega Principal"
        assert data["adjustment_number"] == 1
        assert "id" in data
        assert "created_at" in data
        assert data["warnings"] == []

    def test_increase_recalculates_avg_cost(
        self, client, org_headers, test_material, test_warehouse, db_session
    ):
        """Material starts with stock=200@$40, increase 100@$70.

        New avg cost = (200*40 + 100*70) / (200+100) = (8000+7000)/300 = $50.00
        """
        payload = {
            "material_id": str(test_material.id),
            "warehouse_id": str(test_warehouse.id),
            "quantity": 100.0,
            "unit_cost": 70.0,
            "date": "2026-02-14T10:00:00Z",
            "reason": "Material recibido sin compra",
        }

        response = client.post(f"{BASE_URL}/increase", json=payload, headers=org_headers)

        assert response.status_code == 201

        # Verify material's average cost was recalculated
        db_session.refresh(test_material)
        # (200 * 40 + 100 * 70) / 300 = 15000 / 300 = 50.0
        assert abs(test_material.current_average_cost - Decimal("50.0000")) < Decimal("0.01")
        assert test_material.current_stock == Decimal("300.0000")
        assert test_material.current_stock_liquidated == Decimal("300.0000")

    def test_increase_creates_inventory_movement(
        self, client, org_headers, test_material, test_warehouse, db_session
    ):
        """Verify that an InventoryMovement record is created for the increase."""
        payload = {
            "material_id": str(test_material.id),
            "warehouse_id": str(test_warehouse.id),
            "quantity": 50.0,
            "unit_cost": 60.0,
            "date": "2026-02-14T10:00:00Z",
            "reason": "Verificar movimiento",
        }

        response = client.post(f"{BASE_URL}/increase", json=payload, headers=org_headers)
        assert response.status_code == 201
        adj_id = response.json()["id"]

        # Query the InventoryMovement table for this adjustment
        movements = db_session.query(InventoryMovement).filter(
            InventoryMovement.reference_id == adj_id,
            InventoryMovement.reference_type == "adjustment",
        ).all()

        assert len(movements) == 1
        mov = movements[0]
        assert mov.movement_type == "adjustment"
        assert mov.quantity == Decimal("50.000")
        assert mov.material_id == test_material.id
        assert mov.warehouse_id == test_warehouse.id

    def test_increase_sequential_numbering(
        self, client, org_headers, test_material, test_warehouse
    ):
        """Two increases should get sequential numbers 1 and 2."""
        payload = {
            "material_id": str(test_material.id),
            "warehouse_id": str(test_warehouse.id),
            "quantity": 10.0,
            "unit_cost": 30.0,
            "date": "2026-02-14T10:00:00Z",
            "reason": "Primer ajuste",
        }

        resp1 = client.post(f"{BASE_URL}/increase", json=payload, headers=org_headers)
        assert resp1.status_code == 201
        assert resp1.json()["adjustment_number"] == 1

        payload["reason"] = "Segundo ajuste"
        resp2 = client.post(f"{BASE_URL}/increase", json=payload, headers=org_headers)
        assert resp2.status_code == 201
        assert resp2.json()["adjustment_number"] == 2


class TestDecrease:
    """Tests for POST /api/v1/inventory/adjustments/decrease"""

    def test_decrease_success(
        self, client, org_headers, test_material, test_warehouse
    ):
        """Decrease stock by 50 units."""
        payload = {
            "material_id": str(test_material.id),
            "warehouse_id": str(test_warehouse.id),
            "quantity": 50.0,
            "date": "2026-02-14T10:00:00Z",
            "reason": "Merma detectada",
        }

        response = client.post(f"{BASE_URL}/decrease", json=payload, headers=org_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["adjustment_type"] == "decrease"
        assert data["status"] == "confirmed"
        assert data["previous_stock"] == 200.0
        assert data["quantity"] == -50.0  # Stored as negative delta
        assert data["new_stock"] == 150.0
        assert data["total_value"] == 2000.0  # 50 * 40 (avg cost)
        assert data["warnings"] == []

    def test_decrease_uses_current_avg_cost(
        self, client, org_headers, test_material, test_warehouse, db_session
    ):
        """Verify that decrease uses the material's current average cost, not a user-provided one."""
        payload = {
            "material_id": str(test_material.id),
            "warehouse_id": str(test_warehouse.id),
            "quantity": 30.0,
            "date": "2026-02-14T10:00:00Z",
            "reason": "Faltante en inventario",
        }

        response = client.post(f"{BASE_URL}/decrease", json=payload, headers=org_headers)

        assert response.status_code == 201
        data = response.json()
        # unit_cost should be the material's current_average_cost ($40)
        assert data["unit_cost"] == 40.0

        # Avg cost should NOT change after a decrease
        db_session.refresh(test_material)
        assert test_material.current_average_cost == Decimal("40.0000")

    def test_decrease_negative_stock_warning(
        self, client, org_headers, test_material, test_warehouse
    ):
        """Decrease more than available stock. Should succeed with 201 and include warnings."""
        payload = {
            "material_id": str(test_material.id),
            "warehouse_id": str(test_warehouse.id),
            "quantity": 300.0,  # More than current stock of 200
            "date": "2026-02-14T10:00:00Z",
            "reason": "Perdida total detectada",
        }

        response = client.post(f"{BASE_URL}/decrease", json=payload, headers=org_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["new_stock"] == -100.0  # 200 - 300
        assert len(data["warnings"]) > 0
        assert "negativo" in data["warnings"][0].lower() or "Stock negativo" in data["warnings"][0]


class TestRecount:
    """Tests for POST /api/v1/inventory/adjustments/recount"""

    def test_recount_positive_delta(
        self, client, org_headers, test_material, test_warehouse
    ):
        """Counted quantity > current stock should increase stock."""
        payload = {
            "material_id": str(test_material.id),
            "warehouse_id": str(test_warehouse.id),
            "counted_quantity": 250.0,  # Current is 200
            "date": "2026-02-14T10:00:00Z",
            "reason": "Conteo fisico mensual",
        }

        response = client.post(f"{BASE_URL}/recount", json=payload, headers=org_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["adjustment_type"] == "recount"
        assert data["counted_quantity"] == 250.0
        assert data["previous_stock"] == 200.0
        assert data["quantity"] == 50.0  # delta = 250 - 200
        assert data["new_stock"] == 250.0

    def test_recount_negative_delta(
        self, client, org_headers, test_material, test_warehouse
    ):
        """Counted quantity < current stock should decrease stock."""
        payload = {
            "material_id": str(test_material.id),
            "warehouse_id": str(test_warehouse.id),
            "counted_quantity": 180.0,  # Current is 200
            "date": "2026-02-14T10:00:00Z",
            "reason": "Conteo fisico - faltante",
        }

        response = client.post(f"{BASE_URL}/recount", json=payload, headers=org_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["adjustment_type"] == "recount"
        assert data["counted_quantity"] == 180.0
        assert data["previous_stock"] == 200.0
        assert data["quantity"] == -20.0  # delta = 180 - 200
        assert data["new_stock"] == 180.0

    def test_recount_zero_delta(
        self, client, org_headers, test_material, test_warehouse, db_session
    ):
        """Counted == current: creates record but no stock change."""
        payload = {
            "material_id": str(test_material.id),
            "warehouse_id": str(test_warehouse.id),
            "counted_quantity": 200.0,  # Same as current
            "date": "2026-02-14T10:00:00Z",
            "reason": "Conteo confirmatorio",
        }

        response = client.post(f"{BASE_URL}/recount", json=payload, headers=org_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["counted_quantity"] == 200.0
        assert data["quantity"] == 0.0  # No change
        assert data["new_stock"] == 200.0
        assert data["previous_stock"] == 200.0

        # Stock should remain unchanged
        db_session.refresh(test_material)
        assert test_material.current_stock_liquidated == Decimal("200.0000")


class TestZeroOut:
    """Tests for POST /api/v1/inventory/adjustments/zero-out"""

    def test_zero_out_success(
        self, client, org_headers, test_material, test_warehouse, db_session
    ):
        """Sets stock to zero from 200."""
        payload = {
            "material_id": str(test_material.id),
            "warehouse_id": str(test_warehouse.id),
            "date": "2026-02-14T10:00:00Z",
            "reason": "Liquidacion completa de material",
        }

        response = client.post(f"{BASE_URL}/zero-out", json=payload, headers=org_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["adjustment_type"] == "zero_out"
        assert data["previous_stock"] == 200.0
        assert data["quantity"] == -200.0  # delta = -previous
        assert data["new_stock"] == 0.0
        assert data["total_value"] == 8000.0  # 200 * 40 (avg cost)

        # Verify material stock in DB
        db_session.refresh(test_material)
        assert test_material.current_stock_liquidated == Decimal("0")

    def test_zero_out_already_zero(
        self, client, org_headers, test_material_zero, test_warehouse
    ):
        """Warning when stock is already zero."""
        payload = {
            "material_id": str(test_material_zero.id),
            "warehouse_id": str(test_warehouse.id),
            "date": "2026-02-14T10:00:00Z",
            "reason": "Intento de llevar a cero",
        }

        response = client.post(f"{BASE_URL}/zero-out", json=payload, headers=org_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["new_stock"] == 0.0
        assert data["quantity"] == 0.0
        assert len(data["warnings"]) > 0
        assert "cero" in data["warnings"][0].lower()


class TestAnnul:
    """Tests for POST /api/v1/inventory/adjustments/{id}/annul"""

    def test_annul_increase(
        self, client, org_headers, test_material, test_warehouse, db_session
    ):
        """Annulling an increase should revert the stock increase."""
        # First, create an increase
        increase_payload = {
            "material_id": str(test_material.id),
            "warehouse_id": str(test_warehouse.id),
            "quantity": 100.0,
            "unit_cost": 50.0,
            "date": "2026-02-14T10:00:00Z",
            "reason": "Aumento temporal",
        }
        create_resp = client.post(
            f"{BASE_URL}/increase", json=increase_payload, headers=org_headers
        )
        assert create_resp.status_code == 201
        adj_id = create_resp.json()["id"]

        # Verify stock went up to 300
        db_session.refresh(test_material)
        assert test_material.current_stock_liquidated == Decimal("300.0000")

        # Annul the increase
        annul_resp = client.post(
            f"{BASE_URL}/{adj_id}/annul",
            json={"reason": "Error de digitacion"},
            headers=org_headers,
        )

        assert annul_resp.status_code == 200
        annul_data = annul_resp.json()
        assert annul_data["status"] == "annulled"
        assert annul_data["annulled_reason"] == "Error de digitacion"

        # Verify stock reverted back to 200
        db_session.refresh(test_material)
        assert test_material.current_stock_liquidated == Decimal("200.0000")
        assert test_material.current_stock == Decimal("200.0000")

    def test_annul_decrease(
        self, client, org_headers, test_material, test_warehouse, db_session
    ):
        """Annulling a decrease should restore the stock."""
        # First, create a decrease
        decrease_payload = {
            "material_id": str(test_material.id),
            "warehouse_id": str(test_warehouse.id),
            "quantity": 80.0,
            "date": "2026-02-14T10:00:00Z",
            "reason": "Merma temporal",
        }
        create_resp = client.post(
            f"{BASE_URL}/decrease", json=decrease_payload, headers=org_headers
        )
        assert create_resp.status_code == 201
        adj_id = create_resp.json()["id"]

        # Verify stock went down to 120
        db_session.refresh(test_material)
        assert test_material.current_stock_liquidated == Decimal("120.0000")

        # Annul the decrease
        annul_resp = client.post(
            f"{BASE_URL}/{adj_id}/annul",
            json={"reason": "Merma no confirmada"},
            headers=org_headers,
        )

        assert annul_resp.status_code == 200
        assert annul_resp.json()["status"] == "annulled"

        # Verify stock reverted back to 200
        db_session.refresh(test_material)
        assert test_material.current_stock_liquidated == Decimal("200.0000")
        assert test_material.current_stock == Decimal("200.0000")

    def test_annul_already_annulled(
        self, client, org_headers, test_material, test_warehouse
    ):
        """Annulling an already-annulled adjustment should return 400."""
        # Create and annul an increase
        increase_payload = {
            "material_id": str(test_material.id),
            "warehouse_id": str(test_warehouse.id),
            "quantity": 50.0,
            "unit_cost": 30.0,
            "date": "2026-02-14T10:00:00Z",
            "reason": "Ajuste para anular",
        }
        create_resp = client.post(
            f"{BASE_URL}/increase", json=increase_payload, headers=org_headers
        )
        assert create_resp.status_code == 201
        adj_id = create_resp.json()["id"]

        # First annulment succeeds
        annul_resp1 = client.post(
            f"{BASE_URL}/{adj_id}/annul",
            json={"reason": "Primera anulacion"},
            headers=org_headers,
        )
        assert annul_resp1.status_code == 200

        # Second annulment should fail with 400
        annul_resp2 = client.post(
            f"{BASE_URL}/{adj_id}/annul",
            json={"reason": "Segunda anulacion"},
            headers=org_headers,
        )
        assert annul_resp2.status_code == 400


class TestWarehouseTransfer:
    """Tests for POST /api/v1/inventory/adjustments/warehouse-transfer"""

    def test_transfer_success(
        self, client, org_headers, test_material, test_warehouse, test_warehouse2
    ):
        """Transfer material between warehouses and verify response."""
        payload = {
            "material_id": str(test_material.id),
            "source_warehouse_id": str(test_warehouse.id),
            "destination_warehouse_id": str(test_warehouse2.id),
            "quantity": 50.0,
            "date": "2026-02-14T10:00:00Z",
            "reason": "Traslado por requerimiento",
        }

        response = client.post(
            f"{BASE_URL}/warehouse-transfer", json=payload, headers=org_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["material_id"] == str(test_material.id)
        assert data["material_code"] == "CU-001"
        assert data["material_name"] == "Cobre"
        assert data["source_warehouse_id"] == str(test_warehouse.id)
        assert data["source_warehouse_name"] == "Bodega Principal"
        assert data["destination_warehouse_id"] == str(test_warehouse2.id)
        assert data["destination_warehouse_name"] == "Bodega Secundaria"
        assert data["quantity"] == 50.0
        assert data["reason"] == "Traslado por requerimiento"

    def test_transfer_same_warehouse_error(
        self, client, org_headers, test_material, test_warehouse
    ):
        """Transferring to the same warehouse should return 400."""
        payload = {
            "material_id": str(test_material.id),
            "source_warehouse_id": str(test_warehouse.id),
            "destination_warehouse_id": str(test_warehouse.id),
            "quantity": 50.0,
            "date": "2026-02-14T10:00:00Z",
            "reason": "Traslado invalido",
        }

        response = client.post(
            f"{BASE_URL}/warehouse-transfer", json=payload, headers=org_headers
        )

        assert response.status_code == 400


class TestListAndGet:
    """Tests for GET endpoints: list, by-number, and by-id."""

    def test_list_adjustments_with_filters(
        self, client, org_headers, test_material, test_warehouse
    ):
        """Create multiple adjustments of different types, then filter by type."""
        # Create an increase
        client.post(
            f"{BASE_URL}/increase",
            json={
                "material_id": str(test_material.id),
                "warehouse_id": str(test_warehouse.id),
                "quantity": 10.0,
                "unit_cost": 30.0,
                "date": "2026-02-14T10:00:00Z",
                "reason": "Aumento para test",
            },
            headers=org_headers,
        )

        # Create a decrease
        client.post(
            f"{BASE_URL}/decrease",
            json={
                "material_id": str(test_material.id),
                "warehouse_id": str(test_warehouse.id),
                "quantity": 5.0,
                "date": "2026-02-14T11:00:00Z",
                "reason": "Disminucion para test",
            },
            headers=org_headers,
        )

        # List all — should have 2
        resp_all = client.get(BASE_URL, headers=org_headers)
        assert resp_all.status_code == 200
        data_all = resp_all.json()
        assert data_all["total"] == 2
        assert len(data_all["items"]) == 2

        # Filter by type=increase — should have 1
        resp_inc = client.get(
            BASE_URL,
            params={"adjustment_type": "increase"},
            headers=org_headers,
        )
        assert resp_inc.status_code == 200
        data_inc = resp_inc.json()
        assert data_inc["total"] == 1
        assert data_inc["items"][0]["adjustment_type"] == "increase"

        # Filter by type=decrease — should have 1
        resp_dec = client.get(
            BASE_URL,
            params={"adjustment_type": "decrease"},
            headers=org_headers,
        )
        assert resp_dec.status_code == 200
        data_dec = resp_dec.json()
        assert data_dec["total"] == 1
        assert data_dec["items"][0]["adjustment_type"] == "decrease"
