"""
Tests del Modelo L (decision #64): el COGS de la venta se finaliza al LIQUIDAR,
al promedio vigente en ese momento — no al registrar.

Guardrails del modelo (plan: docs/planes/plan-fix-estructural-costo-promedio.md):
- T1 (oro): conservacion de valor — COGS + valor de inventario == valor total
  entrado, en AMBOS ordenes de liquidacion (la order-dependence del COGS es
  esperada y aceptada; la conservacion es el invariante).
- T2: el COGS se finaliza al liquidar (y el InventoryMovement se actualiza);
  extraer del pool no cambia el promedio.
- T3: auto_liquidate (1 paso) es neutro — mismo costo que hoy.
- T4: material nuevo (avg 0): si una compra se liquida antes que la venta,
  el COGS ya no queda congelado en $0.
- T5: paridad P&L — cost_of_goods_sold == SUM(unit_cost final x quantity).

Escenario canonico (plan seccion 2): pool 1.000 @ 9.000; compra 500 @ 8.000
registrada; venta de 800 registrada. Valor total = 13.000.000.
"""
import pytest
from decimal import Decimal
from uuid import uuid4

from app.models import (
    ThirdParty,
    Material,
    Warehouse,
    MaterialCategory,
    BusinessUnit,
)
from app.models.sale import SaleLine
from app.models.inventory_movement import InventoryMovement
from app.models.third_party_category import ThirdPartyCategory, ThirdPartyCategoryAssignment


DOC_DATE = "2026-06-01T12:00:00"


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def ml_warehouse(db_session, test_organization):
    warehouse = Warehouse(
        id=uuid4(),
        name="Bodega Modelo L",
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(warehouse)
    db_session.commit()
    return warehouse


@pytest.fixture
def ml_material(db_session, test_organization):
    """Material SIN stock ni costo: el pool se construye con compras liquidadas."""
    category = MaterialCategory(
        id=uuid4(), name="Metales L", organization_id=test_organization.id, is_active=True
    )
    bu = BusinessUnit(
        id=uuid4(), name="UN Modelo L", organization_id=test_organization.id, is_active=True
    )
    db_session.add_all([category, bu])
    db_session.flush()
    material = Material(
        id=uuid4(),
        code="ML-COBRE",
        name="Cobre Modelo L",
        category_id=category.id,
        business_unit_id=bu.id,
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
    return material


def _third_party(db_session, org_id, name, behavior):
    tp = ThirdParty(
        id=uuid4(),
        name=name,
        identification_number=str(uuid4())[:12],
        current_balance=Decimal("0"),
        organization_id=org_id,
        is_active=True,
    )
    db_session.add(tp)
    db_session.flush()
    cat = ThirdPartyCategory(name=f"{name} Cat", behavior_type=behavior, organization_id=org_id)
    db_session.add(cat)
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(third_party_id=tp.id, category_id=cat.id))
    db_session.commit()
    return tp


@pytest.fixture
def ml_supplier(db_session, test_organization):
    return _third_party(db_session, test_organization.id, "Proveedor Modelo L", "material_supplier")


@pytest.fixture
def ml_customer(db_session, test_organization):
    return _third_party(db_session, test_organization.id, "Cliente Modelo L", "customer")


# ============================================================================
# Helpers API
# ============================================================================

def _create_purchase(client, org_headers, supplier, warehouse, material, qty, price, auto=False):
    resp = client.post(
        "/api/v1/purchases",
        json={
            "supplier_id": str(supplier.id),
            "date": DOC_DATE,
            "lines": [
                {
                    "material_id": str(material.id),
                    "quantity": float(qty),
                    "unit_price": float(price),
                    "warehouse_id": str(warehouse.id),
                }
            ],
            "auto_liquidate": auto,
        },
        headers=org_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _liquidate_purchase(client, org_headers, purchase_id):
    resp = client.patch(f"/api/v1/purchases/{purchase_id}/liquidate", json={}, headers=org_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _create_sale(client, org_headers, customer, warehouse, material, qty, price, auto=False):
    resp = client.post(
        "/api/v1/sales",
        json={
            "customer_id": str(customer.id),
            "warehouse_id": str(warehouse.id),
            "date": DOC_DATE,
            "lines": [
                {
                    "material_id": str(material.id),
                    "quantity": float(qty),
                    "unit_price": float(price),
                }
            ],
            "commissions": [],
            "auto_liquidate": auto,
        },
        headers=org_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _liquidate_sale(client, org_headers, sale_id):
    resp = client.patch(f"/api/v1/sales/{sale_id}/liquidate", json={}, headers=org_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _sale_lines(db_session, sale_id):
    return db_session.query(SaleLine).filter(SaleLine.sale_id == sale_id).all()


def _canonical_setup(client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material):
    """Pool 1.000 @ 9.000 liquidado; compra 500 @ 8.000 registrada; venta 800 registrada."""
    _create_purchase(client, org_headers, ml_supplier, ml_warehouse, ml_material, 1000, 9000, auto=True)
    purchase2 = _create_purchase(client, org_headers, ml_supplier, ml_warehouse, ml_material, 500, 8000)
    sale = _create_sale(client, org_headers, ml_customer, ml_warehouse, ml_material, 800, 12000)
    db_session.refresh(ml_material)
    assert ml_material.current_average_cost == Decimal("9000")
    assert ml_material.current_stock_liquidated == Decimal("1000")
    return purchase2, sale


def _assert_conservation(db_session, material, sale_id, expected_total):
    """Invariante del modelo: COGS + valor del pool liquidado == valor total entrado.

    Tolerancia: $1 + medio centavo por kg vendido — SaleLine.unit_cost se persiste
    a 2 decimales (Numeric(15,2), pre-existente) mientras el avg vive a 4, asi que
    el COGS guardado arrastra hasta $0.005/kg de redondeo de columna.
    """
    db_session.refresh(material)
    lines = _sale_lines(db_session, sale_id)
    cogs = sum(l.unit_cost * l.quantity for l in lines)
    inventory_value = material.current_stock_liquidated * material.current_average_cost
    tolerance = Decimal("1") + sum(l.quantity for l in lines) * Decimal("0.005")
    assert abs((cogs + inventory_value) - expected_total) <= tolerance, (
        f"Conservacion rota: COGS={cogs} + inventario={inventory_value} != {expected_total}"
    )
    return cogs


# ============================================================================
# T1 — Test de oro: conservacion de valor en ambos ordenes
# ============================================================================

class TestConservationBothOrders:
    """Mismos hechos fisicos, dos ordenes de liquidacion: el COGS difiere
    (esperado, decision de Daniel 2026-07-09) pero el valor total se conserva."""

    def test_order_sale_first(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        purchase2, sale = _canonical_setup(
            client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
        )
        _liquidate_sale(client, org_headers, sale["id"])
        _liquidate_purchase(client, org_headers, purchase2["id"])

        cogs = _assert_conservation(db_session, ml_material, sale["id"], Decimal("13000000"))
        # Venta liquidada ANTES de la compra: COGS al avg previo (9.000)
        assert abs(cogs - Decimal("7200000")) <= Decimal("1")
        # Pool final: 700 @ 8.285,71 (200 @ 9.000 + 500 @ 8.000)
        assert ml_material.current_stock_liquidated == Decimal("700")
        assert abs(ml_material.current_average_cost - Decimal("8285.7143")) < Decimal("0.01")

    def test_order_purchase_first(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        purchase2, sale = _canonical_setup(
            client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
        )
        _liquidate_purchase(client, org_headers, purchase2["id"])
        _liquidate_sale(client, org_headers, sale["id"])

        cogs = _assert_conservation(db_session, ml_material, sale["id"], Decimal("13000000"))
        # Compra liquidada ANTES: la venta se costea al avg mezclado (8.666,67).
        # El COGS guardado usa el unit_cost persistido a 2 decimales.
        expected_unit = (Decimal("13000000") / Decimal("1500")).quantize(Decimal("0.01"))
        assert cogs == expected_unit * Decimal("800")
        assert ml_material.current_stock_liquidated == Decimal("700")
        assert abs(ml_material.current_average_cost - Decimal("8666.6667")) < Decimal("0.01")


# ============================================================================
# T2 — El COGS se finaliza al liquidar (no al registrar)
# ============================================================================

class TestCogsFinalizedAtLiquidation:
    def test_cogs_uses_avg_at_liquidation_not_registration(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        purchase2, sale = _canonical_setup(
            client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
        )
        # Al registrar, el unit_cost provisional es el avg del momento (9.000)
        lines = _sale_lines(db_session, sale["id"])
        assert lines[0].unit_cost == Decimal("9000")

        # La compra liquidada mueve el avg: (1.000x9.000 + 500x8.000)/1.500 = 8.666,67
        # (la venta registrada NO salio del pool liquidado — regla del Modelo L)
        _liquidate_purchase(client, org_headers, purchase2["id"])
        db_session.refresh(ml_material)
        avg_at_liquidation = ml_material.current_average_cost
        assert abs(avg_at_liquidation - Decimal("8666.6667")) < Decimal("0.01")

        _liquidate_sale(client, org_headers, sale["id"])

        # COGS finalizado al avg vigente, NO al provisional del registro.
        # unit_cost se persiste a 2 decimales (Numeric(15,2)) — comparar quantizado.
        expected_cost = avg_at_liquidation.quantize(Decimal("0.01"))
        db_session.expire_all()
        lines = _sale_lines(db_session, sale["id"])
        assert lines[0].unit_cost == expected_cost

        # El InventoryMovement de la venta tambien se actualiza
        mv = (
            db_session.query(InventoryMovement)
            .filter(
                InventoryMovement.reference_type == "sale",
                InventoryMovement.reference_id == sale["id"],
                InventoryMovement.movement_type == "sale",
            )
            .one()
        )
        assert mv.unit_cost == expected_cost

        # Extraer del pool NO cambia el promedio
        db_session.refresh(ml_material)
        assert ml_material.current_average_cost == avg_at_liquidation


# ============================================================================
# T3 — auto_liquidate (1 paso) es neutro
# ============================================================================

class TestAutoLiquidateNeutral:
    def test_one_step_sale_keeps_current_avg(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        _create_purchase(client, org_headers, ml_supplier, ml_warehouse, ml_material, 1000, 9000, auto=True)
        sale = _create_sale(client, org_headers, ml_customer, ml_warehouse, ml_material, 300, 12000, auto=True)

        assert sale["status"] == "liquidated"
        lines = _sale_lines(db_session, sale["id"])
        assert lines[0].unit_cost == Decimal("9000")


# ============================================================================
# T4 — Material nuevo (avg 0): el COGS ya no queda congelado en $0
# ============================================================================

class TestNewMaterialZeroCost:
    def test_cogs_picks_up_cost_from_purchase_liquidated_before_sale_liquidation(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        # Venta ANTES de cualquier compra (stock negativo permitido): provisional $0
        sale = _create_sale(client, org_headers, ml_customer, ml_warehouse, ml_material, 100, 5000)
        lines = _sale_lines(db_session, sale["id"])
        assert lines[0].unit_cost == Decimal("0")

        # Llega la compra y se liquida antes de liquidar la venta
        _create_purchase(client, org_headers, ml_supplier, ml_warehouse, ml_material, 200, 7000, auto=True)
        _liquidate_sale(client, org_headers, sale["id"])

        db_session.expire_all()
        lines = _sale_lines(db_session, sale["id"])
        assert lines[0].unit_cost == Decimal("7000")

        db_session.refresh(ml_material)
        assert ml_material.current_stock_liquidated == Decimal("100")


# ============================================================================
# T5 — Paridad P&L: cost_of_goods_sold == SUM(unit_cost final x quantity)
# ============================================================================

class TestPnlParity:
    def test_pnl_cogs_matches_finalized_unit_cost(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        purchase2, sale = _canonical_setup(
            client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
        )
        _liquidate_purchase(client, org_headers, purchase2["id"])
        _liquidate_sale(client, org_headers, sale["id"])

        lines = _sale_lines(db_session, sale["id"])
        expected_cogs = float(sum(l.unit_cost * l.quantity for l in lines))

        resp = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": "2026-06-01", "date_to": "2026-06-30"},
            headers=org_headers,
        )
        assert resp.status_code == 200, resp.text
        pnl = resp.json()
        assert abs(pnl["cost_of_goods_sold"] - expected_cogs) <= 1
        assert abs(pnl["sales_revenue"] - 9600000) <= 1
