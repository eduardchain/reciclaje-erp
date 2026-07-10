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
from app.models.purchase import PurchaseLine
from app.models.sale import Sale, SaleLine
from app.models.inventory_movement import InventoryMovement
from app.models.material_cost_history import MaterialCostHistory
from app.models.third_party_category import ThirdPartyCategory, ThirdPartyCategoryAssignment
from app.services.inventory_costing import incorporate_into_pool


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


@pytest.fixture
def ml_commissionist(db_session, test_organization):
    # Comisionista requiere behavior_type service_provider (decision #32)
    return _third_party(db_session, test_organization.id, "Comisionista Modelo L", "service_provider")


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


# ============================================================================
# PR-2 (Fase 2) — Conservacion de valor: helper + oversell + cancel ponderado
# ============================================================================

def _pool_equation_holds(liq, avg, qty, cost):
    """Ecuacion de conservacion del helper (asiento contable completo):
    pool_after == pool_before + entrada + adjustment
    (el adjustment tiene contrapartida en P&L — debito inventario / credito
    ganancia oversell, o al reves). Debe cerrar EXACTO en las 3 ramas.
    """
    new_avg, adj = incorporate_into_pool(liq, avg, qty, cost)
    pool_after = (liq + qty) * new_avg
    assert pool_after == liq * avg + qty * cost + adj, (
        f"Ecuacion rota: {pool_after} != {liq * avg} + {qty * cost} + {adj}"
    )
    return new_avg, adj


class TestIncorporateIntoPool:
    """Unitarios puros del helper (T5-T7 del plan, sin BD)."""

    def test_fill_complete_example_a(self):
        # Ejemplo A del plan: hueco -200@10.000, compra 1.000@8.000
        new_avg, adj = _pool_equation_holds(
            Decimal("-200"), Decimal("10000"), Decimal("1000"), Decimal("8000")
        )
        assert new_avg == Decimal("8000")
        assert adj == Decimal("400000")  # se cargo COGS de mas → ganancia

    def test_positive_pool_identical_to_legacy(self):
        # Rama positiva: ponderado clasico, adjustment siempre 0
        new_avg, adj = _pool_equation_holds(
            Decimal("200"), Decimal("9000"), Decimal("500"), Decimal("8000")
        )
        assert adj == Decimal("0")
        assert abs(new_avg - Decimal("8285.714285714285714285714286")) < Decimal("0.0001")

        # Pool vacio: primer costo
        new_avg, adj = incorporate_into_pool(
            Decimal("0"), Decimal("9999"), Decimal("100"), Decimal("7000")
        )
        assert (new_avg, adj) == (Decimal("7000"), Decimal("0"))

    def test_partial_fill_chained_example_b(self):
        # Ejemplo B del plan: hueco -800@8.000, dos compras encadenadas
        new_avg, adj = _pool_equation_holds(
            Decimal("-800"), Decimal("8000"), Decimal("300"), Decimal("9000")
        )
        assert new_avg == Decimal("8000")  # hueco no cubierto: avg queda
        assert adj == Decimal("-300000")   # se cargo COGS de menos → perdida

        new_avg, adj = _pool_equation_holds(
            Decimal("-500"), Decimal("8000"), Decimal("1000"), Decimal("9500")
        )
        assert new_avg == Decimal("9500")  # resto entra limpio al costo real
        assert adj == Decimal("-750000")

    def test_exact_fill_boundary(self):
        # Relleno exacto (remaining == 0): pool queda en 0, avg conserva el previo
        new_avg, adj = _pool_equation_holds(
            Decimal("-200"), Decimal("10000"), Decimal("200"), Decimal("8000")
        )
        assert adj == Decimal("400000")
        assert new_avg == Decimal("10000")  # pool vacio: irrelevante, proxima compra resetea


def _cancel_sale(client, org_headers, sale_id, expect=200):
    resp = client.patch(f"/api/v1/sales/{sale_id}/cancel", headers=org_headers)
    assert resp.status_code == expect, resp.text
    return resp.json()


def _cancel_purchase(client, org_headers, purchase_id, expect=200):
    resp = client.patch(f"/api/v1/purchases/{purchase_id}/cancel", headers=org_headers)
    assert resp.status_code == expect, resp.text
    return resp.json()


def _purchase_lines(db_session, purchase_id):
    return db_session.query(PurchaseLine).filter(PurchaseLine.purchase_id == purchase_id).all()


class TestOversellAtPurchaseLiquidation:
    """T9/T10/G1/G2: compra que rellena hueco persiste cost_adjustment → P&L."""

    def _make_hole(self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material, seed_qty, sell_qty, seed_cost=10000):
        """Pool en hueco: compra seed auto-liquidada + venta liquidada que sobrevende."""
        _create_purchase(client, org_headers, ml_supplier, ml_warehouse, ml_material, seed_qty, seed_cost, auto=True)
        sale = _create_sale(client, org_headers, ml_customer, ml_warehouse, ml_material, sell_qty, 12000)
        _liquidate_sale(client, org_headers, sale["id"])
        db_session.refresh(ml_material)
        assert ml_material.current_stock_liquidated == Decimal(str(seed_qty - sell_qty))
        assert ml_material.current_average_cost == Decimal(str(seed_cost))
        return sale

    def test_fill_hole_persists_adjustment_and_pnl(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        """T9+T10: Ejemplo A end-to-end + linea P&L + round-trip al cancelar."""
        self._make_hole(client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material, 100, 300)
        # Pool: -200 @ 10.000. Compra 1.000 @ 8.000 rellena.
        purchase = _create_purchase(client, org_headers, ml_supplier, ml_warehouse, ml_material, 1000, 8000)
        _liquidate_purchase(client, org_headers, purchase["id"])

        db_session.expire_all()
        lines = _purchase_lines(db_session, purchase["id"])
        assert lines[0].cost_adjustment == Decimal("400000")
        db_session.refresh(ml_material)
        assert ml_material.current_average_cost == Decimal("8000")
        assert ml_material.current_stock_liquidated == Decimal("800")

        # P&L reconoce la ganancia por oversell (fecha: liquidated_at de la compra)
        resp = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": "2026-06-01", "date_to": "2026-06-30"},
            headers=org_headers,
        )
        assert resp.status_code == 200, resp.text
        pnl = resp.json()
        assert pnl["oversell_cost_adjustment"] == pytest.approx(400000, abs=1)
        # net = revenue (300x12.000) - COGS (300x10.000) + oversell 400K
        assert pnl["net_profit"] == pytest.approx(3600000 - 3000000 + 400000, abs=1)

        # Round-trip: cancelar la compra que relleno → pool y P&L vuelven exactos
        _cancel_purchase(client, org_headers, purchase["id"])
        db_session.refresh(ml_material)
        assert ml_material.current_average_cost == Decimal("10000")
        assert ml_material.current_stock_liquidated == Decimal("-200")
        pnl2 = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": "2026-06-01", "date_to": "2026-06-30"},
            headers=org_headers,
        ).json()
        assert pnl2["oversell_cost_adjustment"] == pytest.approx(0, abs=1)

    def test_commission_adjusted_cost_feeds_helper(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material, ml_commissionist
    ):
        """G1: el adjustment usa el costo AJUSTADO (precio + comision/qty), no el crudo."""
        self._make_hole(client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material, 50, 150)
        # Pool: -100 @ 10.000. Compra 200 @ 8.000 + comision fija 40.000 → adjusted 8.200
        resp = client.post(
            "/api/v1/purchases",
            json={
                "supplier_id": str(ml_supplier.id),
                "date": DOC_DATE,
                "lines": [{
                    "material_id": str(ml_material.id),
                    "quantity": 200,
                    "unit_price": 8000,
                    "warehouse_id": str(ml_warehouse.id),
                }],
                "commissions": [{
                    "third_party_id": str(ml_commissionist.id),
                    "concept": "Comision intermediario",
                    "commission_type": "fixed",
                    "commission_value": 40000,
                }],
                "auto_liquidate": False,
            },
            headers=org_headers,
        )
        assert resp.status_code == 201, resp.text
        _liquidate_purchase(client, org_headers, resp.json()["id"])

        db_session.expire_all()
        lines = _purchase_lines(db_session, resp.json()["id"])
        # filled 100 x (10.000 - 8.200) = 180.000 — con el crudo (8.000) daria 200.000
        assert lines[0].cost_adjustment == Decimal("180000")
        db_session.refresh(ml_material)
        assert ml_material.current_average_cost == Decimal("8200")

    def test_multi_line_same_material_sees_running_pool(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        """G2: cada linea ve el pool YA actualizado por las previas de la misma compra.

        Mismo precio en ambas lineas → total y estado final orden-invariantes:
        el hueco de 100 se rellena a 2.000/u de diferencia = 200.000 exactos.
        Si el helper viera el pool PRE-liquidacion en ambas llamadas, rellenaria
        160 unidades ficticias → 320.000 (el test lo atraparia).
        """
        self._make_hole(client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material, 40, 140)
        # Pool: -100 @ 10.000. Compra con 2 lineas del mismo material @ 8.000
        resp = client.post(
            "/api/v1/purchases",
            json={
                "supplier_id": str(ml_supplier.id),
                "date": DOC_DATE,
                "lines": [
                    {"material_id": str(ml_material.id), "quantity": 60, "unit_price": 8000, "warehouse_id": str(ml_warehouse.id)},
                    {"material_id": str(ml_material.id), "quantity": 100, "unit_price": 8000, "warehouse_id": str(ml_warehouse.id)},
                ],
                "auto_liquidate": False,
            },
            headers=org_headers,
        )
        assert resp.status_code == 201, resp.text
        _liquidate_purchase(client, org_headers, resp.json()["id"])

        db_session.expire_all()
        lines = _purchase_lines(db_session, resp.json()["id"])
        total_adjustment = sum(l.cost_adjustment for l in lines)
        assert total_adjustment == Decimal("200000")
        db_session.refresh(ml_material)
        assert ml_material.current_average_cost == Decimal("8000")
        assert ml_material.current_stock_liquidated == Decimal("60")


class TestCancelSaleWeightedReentry:
    """T8: cancelar venta liquidada reingresa VALOR (no solo cantidad) al pool."""

    def test_weighted_reentry_symmetric_with_pnl(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        # Pool 1.000@9.000 → venta 800 liquidada (COGS 9.000) → pool 200@9.000
        _create_purchase(client, org_headers, ml_supplier, ml_warehouse, ml_material, 1000, 9000, auto=True)
        sale = _create_sale(client, org_headers, ml_customer, ml_warehouse, ml_material, 800, 12000)
        _liquidate_sale(client, org_headers, sale["id"])
        # Compra 300@7.000 mueve el avg: (200x9.000 + 300x7.000)/500 = 7.800
        purchase2 = _create_purchase(client, org_headers, ml_supplier, ml_warehouse, ml_material, 300, 7000)
        _liquidate_purchase(client, org_headers, purchase2["id"])
        db_session.refresh(ml_material)
        assert ml_material.current_average_cost == Decimal("7800")
        value_before = ml_material.current_stock_liquidated * ml_material.current_average_cost

        _cancel_sale(client, org_headers, sale["id"])

        # Reingreso ponderado: (500x7.800 + 800x9.000)/1.300 = 8.538,4615
        db_session.refresh(ml_material)
        assert ml_material.current_stock_liquidated == Decimal("1300")
        assert abs(ml_material.current_average_cost - Decimal("8538.4615")) < Decimal("0.01")
        # Simetria: el inventario sube EXACTAMENTE el COGS devuelto (800x9.000)
        value_after = ml_material.current_stock_liquidated * ml_material.current_average_cost
        assert abs((value_after - value_before) - Decimal("7200000")) <= Decimal("1")

        # MCH sale_cancellation registrado (audita + bloquea reverts anteriores)
        mch = db_session.query(MaterialCostHistory).filter(
            MaterialCostHistory.source_type == "sale_cancellation",
            MaterialCostHistory.source_id == sale["id"],
        ).one()
        assert mch.previous_cost == Decimal("7800")

        # check_can_revert: cancelar la compra ANTERIOR ahora bloquea (400)
        resp = client.patch(f"/api/v1/purchases/{purchase2['id']}/cancel", headers=org_headers)
        assert resp.status_code == 400
        assert "Cancelacion de venta" in resp.text

        # Sin hueco (pool era positivo): adjustment de cancelacion = 0
        db_session.expire_all()
        sale_db = db_session.get(Sale, sale["id"])
        assert sale_db.cancellation_cost_adjustment == Decimal("0")

    def test_cancel_into_hole_recognizes_adjustment(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        """Cancelar una venta cuando el pool esta en hueco: el reingreso rellena
        y la diferencia de costo va a Sale.cancellation_cost_adjustment + P&L."""
        # Venta A 100 @ COGS 10.000 (vacia el pool)
        _create_purchase(client, org_headers, ml_supplier, ml_warehouse, ml_material, 100, 10000, auto=True)
        sale_a = _create_sale(client, org_headers, ml_customer, ml_warehouse, ml_material, 100, 12000)
        _liquidate_sale(client, org_headers, sale_a["id"])
        # Pool 0 → compra 100@6.000 → pool 100@6.000 → venta B 180 → hueco -80@6.000
        _create_purchase(client, org_headers, ml_supplier, ml_warehouse, ml_material, 100, 6000, auto=True)
        sale_b = _create_sale(client, org_headers, ml_customer, ml_warehouse, ml_material, 180, 12000)
        _liquidate_sale(client, org_headers, sale_b["id"])
        db_session.refresh(ml_material)
        assert ml_material.current_stock_liquidated == Decimal("-80")
        assert ml_material.current_average_cost == Decimal("6000")

        # Cancelar venta A (COGS 10.000): filled 80 x (6.000-10.000) = -320.000;
        # remaining 20 entra al costo del reingreso (10.000)
        _cancel_sale(client, org_headers, sale_a["id"])
        db_session.expire_all()
        sale_a_db = db_session.get(Sale, sale_a["id"])
        assert sale_a_db.cancellation_cost_adjustment == Decimal("-320000")
        db_session.refresh(ml_material)
        assert ml_material.current_stock_liquidated == Decimal("20")
        assert ml_material.current_average_cost == Decimal("10000")

        # P&L por cancelled_at (hoy) — rango amplio que incluye la cancelacion
        resp = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": "2026-06-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["oversell_cost_adjustment"] == pytest.approx(-320000, abs=1)

    def test_cancel_registered_sale_untouched(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        """Cancelar venta REGISTERED: devuelve a transit, sin ponderacion ni MCH."""
        _create_purchase(client, org_headers, ml_supplier, ml_warehouse, ml_material, 500, 9000, auto=True)
        sale = _create_sale(client, org_headers, ml_customer, ml_warehouse, ml_material, 200, 12000)
        _cancel_sale(client, org_headers, sale["id"])

        db_session.refresh(ml_material)
        assert ml_material.current_average_cost == Decimal("9000")
        assert ml_material.current_stock_liquidated == Decimal("500")
        assert db_session.query(MaterialCostHistory).filter(
            MaterialCostHistory.source_type == "sale_cancellation",
            MaterialCostHistory.source_id == sale["id"],
        ).count() == 0


# ============================================================================
# Stress test: random walk determinista con invariantes globales
# ============================================================================

class TestInventoryStressWalk:
    """Barrido combinatorio del motor de costeo (Modelo L completo, PR-1+PR-2).

    ~60 operaciones pseudo-aleatorias con SEMILLA FIJA (determinista, sin
    flakes): crear/liquidar compras y ventas en ordenes arbitrarios (incluye
    oversell natural), cancelar liquidadas y registradas. Tras CADA operacion
    se verifican los invariantes globales leyendo TODO de la BD (no de un
    tracking paralelo del test):

    I1. stock == transit + liquidated (invariante duro del sistema)
    I2. stock == SUM(inventory_movements.quantity)
    I3. avg >= 0 SIEMPRE (el helper nunca produce promedios negativos)
    I4. avg == new_cost del ultimo MaterialCostHistory (revert BORRA el registro,
        por eso el ultimo MCH siempre refleja el estado vigente)
    I5. CONSERVACION DE VALOR (la promesa del Modelo L):
        liquidated x avg == compras_liquidadas_in - COGS_ventas_liquidadas
                            + ajustes_oversell (compras activas + cancels)
        con tolerancia = $1 + $0.005 x kg (redondeo Numeric(15,2) de unit_cost).
    """

    OPS = 60

    def _invariants(self, db_session, material, tol_qty):
        from sqlalchemy import func as sa_func
        from app.models.purchase import Purchase as P

        db_session.expire_all()
        db_session.refresh(material)

        # I1
        assert material.current_stock == material.current_stock_transit + material.current_stock_liquidated
        # I2
        mv_sum = db_session.query(sa_func.coalesce(sa_func.sum(InventoryMovement.quantity), 0)).filter(
            InventoryMovement.material_id == material.id
        ).scalar()
        assert material.current_stock == mv_sum
        # I3
        assert material.current_average_cost >= 0
        # I4
        last_mch = db_session.query(MaterialCostHistory).filter(
            MaterialCostHistory.material_id == material.id
        ).order_by(MaterialCostHistory.created_at.desc(), MaterialCostHistory.id.desc()).first()
        if last_mch is not None:
            assert material.current_average_cost == last_mch.new_cost

        # I5 — todo desde BD
        in_total = db_session.query(
            sa_func.coalesce(sa_func.sum(PurchaseLine.quantity * PurchaseLine.unit_price), 0)
        ).join(P, PurchaseLine.purchase_id == P.id).filter(
            PurchaseLine.material_id == material.id, P.status == "liquidated"
        ).scalar()
        purchase_adj = db_session.query(
            sa_func.coalesce(sa_func.sum(PurchaseLine.cost_adjustment), 0)
        ).join(P, PurchaseLine.purchase_id == P.id).filter(
            PurchaseLine.material_id == material.id, P.status == "liquidated"
        ).scalar()
        cogs_total = db_session.query(
            sa_func.coalesce(sa_func.sum(SaleLine.unit_cost * SaleLine.quantity), 0)
        ).join(Sale, SaleLine.sale_id == Sale.id).filter(
            SaleLine.material_id == material.id, Sale.status == "liquidated"
        ).scalar()
        cancel_adj = db_session.query(
            sa_func.coalesce(sa_func.sum(Sale.cancellation_cost_adjustment), 0)
        ).join(SaleLine, SaleLine.sale_id == Sale.id).filter(
            SaleLine.material_id == material.id, Sale.status == "cancelled"
        ).scalar()

        pool_value = material.current_stock_liquidated * material.current_average_cost
        expected = Decimal(str(in_total)) - Decimal(str(cogs_total)) + Decimal(str(purchase_adj)) + Decimal(str(cancel_adj))
        tolerance = Decimal("1") + tol_qty * Decimal("0.005")
        assert abs(pool_value - expected) <= tolerance, (
            f"Conservacion rota: pool={pool_value} vs esperado={expected} "
            f"(in={in_total} cogs={cogs_total} adj_compras={purchase_adj} adj_cancels={cancel_adj}, tol={tolerance})"
        )

    def test_random_walk_all_invariants_hold(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        import random
        rng = random.Random(20260710)  # semilla fija → reproducible

        pending_purchases: list[str] = []
        liquidated_purchases: list[str] = []
        pending_sales: list[str] = []
        liquidated_sales: list[str] = []
        tol_qty = Decimal("0")  # kg acumulados que pasaron por redondeo 2-dec
        saw_hole = False
        counts = {"pc": 0, "pl": 0, "sc": 0, "sl": 0, "s_cxl": 0, "p_cxl": 0, "p_cxl_blocked": 0}

        for _ in range(self.OPS):
            action = rng.choices(
                ["purchase_create", "purchase_liq", "sale_create", "sale_liq", "sale_cancel", "purchase_cancel"],
                weights=[25, 20, 25, 20, 5, 5],
            )[0]

            if action == "purchase_create":
                qty = rng.randrange(50, 500, 10)
                price = rng.randrange(1000, 12000, 100)
                p = _create_purchase(client, org_headers, ml_supplier, ml_warehouse, ml_material, qty, price)
                pending_purchases.append(p["id"])
                counts["pc"] += 1
            elif action == "purchase_liq" and pending_purchases:
                pid = pending_purchases.pop(rng.randrange(len(pending_purchases)))
                _liquidate_purchase(client, org_headers, pid)
                liquidated_purchases.append(pid)
                counts["pl"] += 1
            elif action == "sale_create":
                qty = rng.randrange(30, 400, 10)
                s = _create_sale(client, org_headers, ml_customer, ml_warehouse, ml_material, qty, 15000)
                pending_sales.append(s["id"])
                counts["sc"] += 1
            elif action == "sale_liq" and pending_sales:
                sid = pending_sales.pop(rng.randrange(len(pending_sales)))
                _liquidate_sale(client, org_headers, sid)
                liquidated_sales.append(sid)
                tol_qty += Decimal("400")
                counts["sl"] += 1
            elif action == "sale_cancel" and liquidated_sales:
                sid = liquidated_sales.pop(rng.randrange(len(liquidated_sales)))
                _cancel_sale(client, org_headers, sid)
                tol_qty += Decimal("400")
                counts["s_cxl"] += 1
            elif action == "purchase_cancel" and liquidated_purchases:
                pid = liquidated_purchases.pop(rng.randrange(len(liquidated_purchases)))
                resp = client.patch(f"/api/v1/purchases/{pid}/cancel", headers=org_headers)
                # 400 = bloqueada por check_can_revert (MCH posterior) — valido
                assert resp.status_code in (200, 400), resp.text
                if resp.status_code == 200:
                    counts["p_cxl"] += 1
                else:
                    counts["p_cxl_blocked"] += 1
                    liquidated_purchases.append(pid)  # sigue liquidada

            self._invariants(db_session, ml_material, tol_qty)
            if ml_material.current_stock_liquidated < 0:
                saw_hole = True

        # Sanidad del walk: ejercito de verdad todos los caminos criticos
        assert counts["pl"] >= 5, counts
        assert counts["sl"] >= 5, counts
        assert counts["s_cxl"] + counts["p_cxl"] >= 1, counts
        assert saw_hole, f"El walk nunca paso por oversell — ajustar semilla/pesos: {counts}"

        # Cierre: liquidar todo lo pendiente y verificar una ultima vez
        for pid in list(pending_purchases):
            _liquidate_purchase(client, org_headers, pid)
        for sid in list(pending_sales):
            _liquidate_sale(client, org_headers, sid)
            tol_qty += Decimal("400")
        self._invariants(db_session, ml_material, tol_qty)
