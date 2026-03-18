"""
Comprehensive tests for Material Transformation API endpoints.

Tests all 5 endpoints:
1. POST /api/v1/inventory/transformations — Create transformation (disassembly)
2. POST /api/v1/inventory/transformations/{id}/annul — Annul transformation
3. GET /api/v1/inventory/transformations — List with filters
4. GET /api/v1/inventory/transformations/by-number/{number} — Get by sequential number
5. GET /api/v1/inventory/transformations/{id} — Get by ID

14 tests covering cost distribution, waste, stock changes, annulment, and queries.
"""
import pytest
from decimal import Decimal
from uuid import uuid4

from app.models import Material, Warehouse


# Base URL for all transformation endpoints
BASE_URL = "/api/v1/inventory/transformations"


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def source_material(db_session, test_organization):
    """Motor Electrico - 500kg @ $1000/kg"""
    material = Material(
        code="MOTOR-001",
        name="Motor Electrico",
        default_unit="kg",
        current_stock=Decimal("500.0000"),
        current_stock_liquidated=Decimal("500.0000"),
        current_stock_transit=Decimal("0"),
        current_average_cost=Decimal("1000.0000"),
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)
    return material


@pytest.fixture
def dest_copper(db_session, test_organization):
    """Cobre - starts at 0 stock."""
    material = Material(
        code="CU-001",
        name="Cobre",
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
def dest_iron(db_session, test_organization):
    """Hierro - starts at 0 stock."""
    material = Material(
        code="FE-001",
        name="Hierro",
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
def dest_aluminum(db_session, test_organization):
    """Aluminio - starts at 0 stock."""
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
    """Bodega Principal."""
    wh = Warehouse(
        name="Bodega Principal",
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(wh)
    db_session.commit()
    db_session.refresh(wh)
    return wh


def _build_transformation_payload(
    source_material,
    test_warehouse,
    dest_copper,
    dest_iron,
    dest_aluminum,
    *,
    source_quantity=500.0,
    waste_quantity=20.0,
    copper_qty=200.0,
    iron_qty=180.0,
    aluminum_qty=100.0,
    cost_distribution="proportional_weight",
    lines_override=None,
):
    """Helper to build a standard transformation creation payload."""
    lines = lines_override or [
        {
            "destination_material_id": str(dest_copper.id),
            "destination_warehouse_id": str(test_warehouse.id),
            "quantity": copper_qty,
        },
        {
            "destination_material_id": str(dest_iron.id),
            "destination_warehouse_id": str(test_warehouse.id),
            "quantity": iron_qty,
        },
        {
            "destination_material_id": str(dest_aluminum.id),
            "destination_warehouse_id": str(test_warehouse.id),
            "quantity": aluminum_qty,
        },
    ]
    return {
        "source_material_id": str(source_material.id),
        "source_warehouse_id": str(test_warehouse.id),
        "source_quantity": source_quantity,
        "waste_quantity": waste_quantity,
        "cost_distribution": cost_distribution,
        "date": "2026-02-14T10:00:00Z",
        "reason": "Desintegracion de motor electrico",
        "lines": lines,
    }


# ============================================================================
# TestCreateTransformation
# ============================================================================

class TestCreateTransformation:
    """Tests for POST /api/v1/inventory/transformations"""

    def test_create_proportional_distribution(
        self,
        client,
        org_headers,
        source_material,
        test_warehouse,
        dest_copper,
        dest_iron,
        dest_aluminum,
    ):
        """Create with 3 destinations; verify cost is distributed proportionally by weight."""
        # Arrange
        payload = _build_transformation_payload(
            source_material, test_warehouse, dest_copper, dest_iron, dest_aluminum,
        )

        # Act
        response = client.post(BASE_URL, json=payload, headers=org_headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "confirmed"
        assert data["transformation_number"] == 1
        assert data["cost_distribution"] == "proportional_weight"
        assert data["source_material_code"] == "MOTOR-001"
        assert data["source_warehouse_name"] == "Bodega Principal"
        assert len(data["lines"]) == 3

        # Source: 500kg @ $1000 = $500,000 total
        # Waste: 20kg @ $1000 = $20,000
        # Distributable: $500,000 - $20,000 = $480,000
        # Total dest qty: 200 + 180 + 100 = 480
        # Copper 200/480 * 480,000 = $200,000 => unit_cost = 200,000/200 = $1,000
        # Iron   180/480 * 480,000 = $180,000 => unit_cost = 180,000/180 = $1,000
        # Aluminum 100/480 * 480,000 = $100,000 => unit_cost = 100,000/100 = $1,000
        for line in data["lines"]:
            assert abs(line["unit_cost"] - 1000.0) < 0.01

        # Verify copper line specifically
        copper_line = next(
            l for l in data["lines"] if l["destination_material_code"] == "CU-001"
        )
        assert abs(copper_line["quantity"] - 200.0) < 0.01
        assert abs(copper_line["total_cost"] - 200000.0) < 1.0

    def test_create_with_waste(
        self,
        client,
        org_headers,
        source_material,
        test_warehouse,
        dest_copper,
        dest_iron,
        dest_aluminum,
    ):
        """Verify waste_value is calculated correctly: waste_quantity * source_unit_cost."""
        # Arrange
        payload = _build_transformation_payload(
            source_material, test_warehouse, dest_copper, dest_iron, dest_aluminum,
            waste_quantity=50.0,
            copper_qty=200.0,
            iron_qty=180.0,
            aluminum_qty=70.0,  # 200+180+70+50 = 500
        )

        # Act
        response = client.post(BASE_URL, json=payload, headers=org_headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        # waste_value = 50 * 1000 = $50,000
        assert abs(data["waste_value"] - 50000.0) < 1.0
        assert abs(data["waste_quantity"] - 50.0) < 0.01
        assert abs(data["source_total_value"] - 500000.0) < 1.0

    def test_create_manual_distribution(
        self,
        client,
        org_headers,
        source_material,
        test_warehouse,
        dest_copper,
        dest_iron,
        dest_aluminum,
    ):
        """Provide unit_cost per line (manual distribution); verify accepted."""
        # Source: 500kg @ $1000 = $500,000
        # Waste: 20kg @ $1000 = $20,000
        # Distributable: $480,000
        # Manual: Copper 200 @ $1200 = $240,000
        #         Iron   180 @ $800  = $144,000
        #         Aluminum 100 @ $960 = $96,000
        # Total manual = $480,000 == distributable (exact match)
        lines = [
            {
                "destination_material_id": str(dest_copper.id),
                "destination_warehouse_id": str(test_warehouse.id),
                "quantity": 200.0,
                "unit_cost": 1200.0,
            },
            {
                "destination_material_id": str(dest_iron.id),
                "destination_warehouse_id": str(test_warehouse.id),
                "quantity": 180.0,
                "unit_cost": 800.0,
            },
            {
                "destination_material_id": str(dest_aluminum.id),
                "destination_warehouse_id": str(test_warehouse.id),
                "quantity": 100.0,
                "unit_cost": 960.0,
            },
        ]
        payload = _build_transformation_payload(
            source_material, test_warehouse, dest_copper, dest_iron, dest_aluminum,
            cost_distribution="manual",
            lines_override=lines,
        )

        # Act
        response = client.post(BASE_URL, json=payload, headers=org_headers)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["cost_distribution"] == "manual"

        copper_line = next(
            l for l in data["lines"] if l["destination_material_code"] == "CU-001"
        )
        assert abs(copper_line["unit_cost"] - 1200.0) < 0.01
        assert abs(copper_line["total_cost"] - 240000.0) < 1.0

    def test_create_balance_mismatch(
        self,
        client,
        org_headers,
        source_material,
        test_warehouse,
        dest_copper,
        dest_iron,
        dest_aluminum,
    ):
        """sum(lines.qty) + waste != source_qty should return 422 validation error."""
        # Arrange — quantities don't balance: 200+180+100+20 = 500, but source=600
        payload = _build_transformation_payload(
            source_material, test_warehouse, dest_copper, dest_iron, dest_aluminum,
            source_quantity=600.0,  # mismatch: 200+180+100+20 = 500 != 600
        )

        # Act
        response = client.post(BASE_URL, json=payload, headers=org_headers)

        # Assert
        assert response.status_code == 422

    def test_create_insufficient_stock(
        self,
        client,
        org_headers,
        source_material,
        test_warehouse,
        dest_copper,
        dest_iron,
        dest_aluminum,
        db_session,
    ):
        """Source material has less stock than requested — returns 201 with warnings (stock negativo permitido)."""
        # Arrange — reduce source stock to 100 (less than requested 500)
        source_material.current_stock = Decimal("100.0000")
        source_material.current_stock_liquidated = Decimal("100.0000")
        db_session.commit()

        payload = _build_transformation_payload(
            source_material, test_warehouse, dest_copper, dest_iron, dest_aluminum,
        )

        # Act
        response = client.post(BASE_URL, json=payload, headers=org_headers)

        # Assert — negative stock is allowed but generates a warning
        assert response.status_code == 201
        data = response.json()
        assert len(data["warnings"]) > 0
        assert any("insuficiente" in w.lower() or "stock" in w.lower() for w in data["warnings"])

    def test_create_no_lines(
        self,
        client,
        org_headers,
        source_material,
        test_warehouse,
    ):
        """Empty lines should return 422 validation error."""
        # Arrange
        payload = {
            "source_material_id": str(source_material.id),
            "source_warehouse_id": str(test_warehouse.id),
            "source_quantity": 500.0,
            "waste_quantity": 500.0,
            "cost_distribution": "proportional_weight",
            "date": "2026-02-14T10:00:00Z",
            "reason": "Desintegracion de motor electrico",
            "lines": [],
        }

        # Act
        response = client.post(BASE_URL, json=payload, headers=org_headers)

        # Assert
        assert response.status_code == 422

    def test_create_source_equals_destination(
        self,
        client,
        org_headers,
        source_material,
        test_warehouse,
        dest_copper,
        dest_iron,
    ):
        """Source material same as a destination should return 400 error."""
        # Arrange — one destination is the source material itself
        lines = [
            {
                "destination_material_id": str(source_material.id),  # same as source!
                "destination_warehouse_id": str(test_warehouse.id),
                "quantity": 300.0,
            },
            {
                "destination_material_id": str(dest_copper.id),
                "destination_warehouse_id": str(test_warehouse.id),
                "quantity": 200.0,
            },
        ]
        payload = {
            "source_material_id": str(source_material.id),
            "source_warehouse_id": str(test_warehouse.id),
            "source_quantity": 500.0,
            "waste_quantity": 0.0,
            "cost_distribution": "proportional_weight",
            "date": "2026-02-14T10:00:00Z",
            "reason": "Desintegracion de motor electrico",
            "lines": lines,
        }

        # Act
        response = client.post(BASE_URL, json=payload, headers=org_headers)

        # Assert
        assert response.status_code == 400

    def test_create_updates_stock(
        self,
        client,
        org_headers,
        source_material,
        test_warehouse,
        dest_copper,
        dest_iron,
        dest_aluminum,
        db_session,
    ):
        """Verify source stock decreased and destination stocks increased after creation."""
        # Arrange
        payload = _build_transformation_payload(
            source_material, test_warehouse, dest_copper, dest_iron, dest_aluminum,
        )

        # Act
        response = client.post(BASE_URL, json=payload, headers=org_headers)
        assert response.status_code == 201

        # Refresh from DB to see changes applied by the API session
        db_session.expire_all()
        db_session.refresh(source_material)
        db_session.refresh(dest_copper)
        db_session.refresh(dest_iron)
        db_session.refresh(dest_aluminum)

        # Assert source decreased: 500 - 500 = 0
        assert source_material.current_stock_liquidated == Decimal("0")
        assert source_material.current_stock == Decimal("0")

        # Assert destinations increased
        assert dest_copper.current_stock_liquidated == Decimal("200.0000")
        assert dest_iron.current_stock_liquidated == Decimal("180.0000")
        assert dest_aluminum.current_stock_liquidated == Decimal("100.0000")

    def test_create_recalculates_dest_avg_cost(
        self,
        client,
        org_headers,
        source_material,
        test_warehouse,
        dest_copper,
        dest_iron,
        dest_aluminum,
        db_session,
    ):
        """Verify destination avg cost is properly recalculated after transformation."""
        # Arrange — give copper some existing stock at a different cost
        dest_copper.current_stock = Decimal("100.0000")
        dest_copper.current_stock_liquidated = Decimal("100.0000")
        dest_copper.current_average_cost = Decimal("500.0000")  # existing cost = $500/kg
        db_session.commit()

        payload = _build_transformation_payload(
            source_material, test_warehouse, dest_copper, dest_iron, dest_aluminum,
        )

        # Act
        response = client.post(BASE_URL, json=payload, headers=org_headers)
        assert response.status_code == 201

        # Refresh from DB
        db_session.expire_all()
        db_session.refresh(dest_copper)

        # Copper gets 200kg at $1000/kg ($200,000) from transformation
        # Existing: 100kg at $500/kg = $50,000
        # New avg = (50,000 + 200,000) / (100 + 200) = 250,000 / 300 = $833.3333...
        expected_avg = Decimal("250000") / Decimal("300")  # ~833.3333
        assert abs(dest_copper.current_average_cost - expected_avg) < Decimal("0.01")
        assert dest_copper.current_stock == Decimal("300.0000")
        assert dest_copper.current_stock_liquidated == Decimal("300.0000")


# ============================================================================
# TestAnnulTransformation
# ============================================================================

class TestAnnulTransformation:
    """Tests for POST /api/v1/inventory/transformations/{id}/annul"""

    def test_annul_success(
        self,
        client,
        org_headers,
        source_material,
        test_warehouse,
        dest_copper,
        dest_iron,
        dest_aluminum,
        db_session,
    ):
        """Annul a transformation and verify all stock changes are reversed."""
        # Arrange — create a transformation first
        payload = _build_transformation_payload(
            source_material, test_warehouse, dest_copper, dest_iron, dest_aluminum,
        )
        create_resp = client.post(BASE_URL, json=payload, headers=org_headers)
        assert create_resp.status_code == 201
        transformation_id = create_resp.json()["id"]

        # Act — annul the transformation
        annul_resp = client.post(
            f"{BASE_URL}/{transformation_id}/annul",
            json={"reason": "Error en la transformacion"},
            headers=org_headers,
        )

        # Assert
        assert annul_resp.status_code == 200
        data = annul_resp.json()
        assert data["status"] == "annulled"
        assert data["annulled_reason"] == "Error en la transformacion"
        assert data["annulled_at"] is not None

        # Verify stock is restored
        db_session.expire_all()
        db_session.refresh(source_material)
        db_session.refresh(dest_copper)
        db_session.refresh(dest_iron)
        db_session.refresh(dest_aluminum)

        # Source restored: 0 + 500 = 500
        assert source_material.current_stock_liquidated == Decimal("500.0000")
        assert source_material.current_stock == Decimal("500.0000")

        # Destinations reverted: back to 0
        assert dest_copper.current_stock_liquidated == Decimal("0")
        assert dest_iron.current_stock_liquidated == Decimal("0")
        assert dest_aluminum.current_stock_liquidated == Decimal("0")

    def test_annul_already_annulled(
        self,
        client,
        org_headers,
        source_material,
        test_warehouse,
        dest_copper,
        dest_iron,
        dest_aluminum,
    ):
        """Double annulment should return 400 error."""
        # Arrange — create and annul
        payload = _build_transformation_payload(
            source_material, test_warehouse, dest_copper, dest_iron, dest_aluminum,
        )
        create_resp = client.post(BASE_URL, json=payload, headers=org_headers)
        assert create_resp.status_code == 201
        transformation_id = create_resp.json()["id"]

        first_annul = client.post(
            f"{BASE_URL}/{transformation_id}/annul",
            json={"reason": "Primera anulacion"},
            headers=org_headers,
        )
        assert first_annul.status_code == 200

        # Act — try to annul again
        second_annul = client.post(
            f"{BASE_URL}/{transformation_id}/annul",
            json={"reason": "Segunda anulacion"},
            headers=org_headers,
        )

        # Assert
        assert second_annul.status_code == 400


# ============================================================================
# TestListAndGet
# ============================================================================

class TestListAndGet:
    """Tests for GET endpoints (list, get by id, get by number)."""

    def test_get_by_id(
        self,
        client,
        org_headers,
        source_material,
        test_warehouse,
        dest_copper,
        dest_iron,
        dest_aluminum,
    ):
        """Create a transformation and retrieve it by ID."""
        # Arrange
        payload = _build_transformation_payload(
            source_material, test_warehouse, dest_copper, dest_iron, dest_aluminum,
        )
        create_resp = client.post(BASE_URL, json=payload, headers=org_headers)
        assert create_resp.status_code == 201
        transformation_id = create_resp.json()["id"]

        # Act
        get_resp = client.get(f"{BASE_URL}/{transformation_id}", headers=org_headers)

        # Assert
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == transformation_id
        assert data["transformation_number"] == 1
        assert data["source_material_code"] == "MOTOR-001"
        assert data["source_material_name"] == "Motor Electrico"
        assert len(data["lines"]) == 3

    def test_get_by_number(
        self,
        client,
        org_headers,
        source_material,
        test_warehouse,
        dest_copper,
        dest_iron,
        dest_aluminum,
    ):
        """Retrieve transformation by sequential number."""
        # Arrange
        payload = _build_transformation_payload(
            source_material, test_warehouse, dest_copper, dest_iron, dest_aluminum,
        )
        create_resp = client.post(BASE_URL, json=payload, headers=org_headers)
        assert create_resp.status_code == 201
        expected_number = create_resp.json()["transformation_number"]

        # Act
        get_resp = client.get(
            f"{BASE_URL}/by-number/{expected_number}",
            headers=org_headers,
        )

        # Assert
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["transformation_number"] == expected_number
        assert data["source_material_code"] == "MOTOR-001"

    def test_list_with_filters(
        self,
        client,
        org_headers,
        source_material,
        test_warehouse,
        dest_copper,
        dest_iron,
        dest_aluminum,
    ):
        """Create two transformations, annul one, and filter by status."""
        # Arrange — create two transformations
        payload = _build_transformation_payload(
            source_material, test_warehouse, dest_copper, dest_iron, dest_aluminum,
        )
        resp1 = client.post(BASE_URL, json=payload, headers=org_headers)
        assert resp1.status_code == 201

        resp2 = client.post(BASE_URL, json=payload, headers=org_headers)
        assert resp2.status_code == 201
        t2_id = resp2.json()["id"]

        # Anular la mas reciente (la segunda) para evitar bloqueo por historial
        annul_resp = client.post(
            f"{BASE_URL}/{t2_id}/annul",
            json={"reason": "Error"},
            headers=org_headers,
        )
        assert annul_resp.status_code == 200

        # Act — list all (no filter)
        all_resp = client.get(BASE_URL, headers=org_headers)
        assert all_resp.status_code == 200
        all_data = all_resp.json()
        assert all_data["total"] == 2

        # Act — filter by status=confirmed
        confirmed_resp = client.get(
            BASE_URL,
            params={"status": "confirmed"},
            headers=org_headers,
        )
        assert confirmed_resp.status_code == 200
        confirmed_data = confirmed_resp.json()
        assert confirmed_data["total"] == 1
        assert confirmed_data["items"][0]["status"] == "confirmed"

        # Act — filter by status=annulled
        annulled_resp = client.get(
            BASE_URL,
            params={"status": "annulled"},
            headers=org_headers,
        )
        assert annulled_resp.status_code == 200
        annulled_data = annulled_resp.json()
        assert annulled_data["total"] == 1
        assert annulled_data["items"][0]["status"] == "annulled"
