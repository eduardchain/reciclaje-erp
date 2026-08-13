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

        # Cancelar la compra que relleno (Fase 5: remocion ponderada, ya no
        # rewind). La remocion saca qty x (8.000 + fill 400K/1.000) = 8.400.000
        # de un pool de 6.400.000 → rama 3: el hueco resultante carga el avg
        # vigente (8.000, NO los 10.000 pre-compra) y la diferencia +400.000 va
        # a cancellation_cost_adjustment. El P&L del rango pierde el fill
        # (status cancelled) pero gana el cancel-adj por cancelled_at (hoy,
        # dentro del rango amplio): neto +400.000. Cuando una compra futura
        # rellene el hueco a costo X, el total reconcilia a 200x(10.000-X) —
        # exactamente como si esta compra nunca hubiera existido (G3: el P&L
        # se redistribuye entre fechas, el total conserva).
        _cancel_purchase(client, org_headers, purchase["id"])
        db_session.expire_all()
        db_session.refresh(ml_material)
        assert ml_material.current_average_cost == Decimal("8000")
        assert ml_material.current_stock_liquidated == Decimal("-200")
        from app.models.purchase import Purchase as _P
        assert db_session.get(_P, purchase["id"]).cancellation_cost_adjustment == Decimal("400000")
        pnl2 = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": "2026-06-01", "date_to": "2026-12-31"},
            headers=org_headers,
        ).json()
        assert pnl2["oversell_cost_adjustment"] == pytest.approx(400000, abs=1)
        # Y el mes original queda limpio (el fill se fue con la compra):
        pnl_junio = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": "2026-06-01", "date_to": "2026-06-30"},
            headers=org_headers,
        ).json()
        assert pnl_junio["oversell_cost_adjustment"] == pytest.approx(0, abs=1)

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

        # Fase 5: cancelar la compra ANTERIOR ya no bloquea (antes 400 por el
        # MCH sale_cancellation posterior). La remocion ponderada recupera el
        # estado EXACTO pre-compra: el reingreso trajo 800x9.000 y la remocion
        # saca 300x7.000 → (200x9.000 + 800x9.000)/1.000 = 9.000. Con rewind
        # habria corrompido (avg de vuelta a 9.000 pero descontando cantidad
        # de un pool ya mezclado); ponderado lo hace legitimo.
        resp = client.patch(f"/api/v1/purchases/{purchase2['id']}/cancel", headers=org_headers)
        assert resp.status_code == 200, resp.text
        db_session.expire_all()
        db_session.refresh(ml_material)
        assert ml_material.current_stock_liquidated == Decimal("1000")
        assert abs(ml_material.current_average_cost - Decimal("9000")) < Decimal("0.01")
        from app.models.purchase import Purchase as _P
        assert db_session.get(_P, purchase2["id"]).cancellation_cost_adjustment == Decimal("0")

        # Sin hueco (pool era positivo): adjustment de cancelacion de venta = 0
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


class TestCancelPurchaseHoleWarning:
    """PR-3 (#65): cancelar compra cuyo material ya fue vendido AVISA (no bloquea)."""

    def test_cancel_projecting_hole_returns_warning(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        purchase = _create_purchase(client, org_headers, ml_supplier, ml_warehouse, ml_material, 100, 10000, auto=True)
        sale = _create_sale(client, org_headers, ml_customer, ml_warehouse, ml_material, 80, 12000)
        _liquidate_sale(client, org_headers, sale["id"])
        # Pool: 20 @ 10.000. Cancelar la compra deja -80 (venta ya salio)

        data = _cancel_purchase(client, org_headers, purchase["id"])
        assert data["status"] == "cancelled"
        assert data.get("warnings"), "Esperaba warning de stock liquidado negativo"
        assert "ML-COBRE" in data["warnings"][0]
        assert "-80" in data["warnings"][0]

        db_session.refresh(ml_material)
        assert ml_material.current_stock_liquidated == Decimal("-80")

    def test_cancel_without_hole_no_warning(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        # Dos compras: cancelar una con stock de sobra no avisa
        _create_purchase(client, org_headers, ml_supplier, ml_warehouse, ml_material, 500, 9000, auto=True)
        purchase2 = _create_purchase(client, org_headers, ml_supplier, ml_warehouse, ml_material, 100, 9000, auto=True)

        data = _cancel_purchase(client, org_headers, purchase2["id"])
        assert data["status"] == "cancelled"
        assert not data.get("warnings")


# ============================================================================
# PR-4 (Fase 2c): ajustes de inventario y transformaciones adoptan el helper
# ============================================================================

ADJ_URL = "/api/v1/inventory/adjustments"
TRANS_URL = "/api/v1/inventory/transformations"


def _increase(client, org_headers, material, warehouse, qty, cost):
    resp = client.post(
        f"{ADJ_URL}/increase",
        json={
            "material_id": str(material.id),
            "warehouse_id": str(warehouse.id),
            "quantity": float(qty),
            "unit_cost": float(cost),
            "date": DOC_DATE,
            "reason": "Ajuste Modelo L PR-4",
        },
        headers=org_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _decrease(client, org_headers, material, warehouse, qty):
    resp = client.post(
        f"{ADJ_URL}/decrease",
        json={
            "material_id": str(material.id),
            "warehouse_id": str(warehouse.id),
            "quantity": float(qty),
            "date": DOC_DATE,
            "reason": "Ajuste Modelo L PR-4",
        },
        headers=org_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _annul_adjustment(client, org_headers, adjustment_id, expect=200):
    resp = client.post(
        f"{ADJ_URL}/{adjustment_id}/annul",
        json={"reason": "Anulacion test PR-4"},
        headers=org_headers,
    )
    assert resp.status_code == expect, resp.text
    return resp.json()


def _seed_hole(client, org_headers, db_session, supplier, customer, warehouse, material, seed_qty, sell_qty, seed_cost=10000):
    """Pool en hueco: compra seed auto-liquidada + venta liquidada que sobrevende."""
    _create_purchase(client, org_headers, supplier, warehouse, material, seed_qty, seed_cost, auto=True)
    sale = _create_sale(client, org_headers, customer, warehouse, material, sell_qty, 12000)
    _liquidate_sale(client, org_headers, sale["id"])
    db_session.refresh(material)
    assert material.current_stock_liquidated == Decimal(str(seed_qty - sell_qty))
    assert material.current_average_cost == Decimal(str(seed_cost))
    return sale


def _pnl_oversell(client, org_headers):
    resp = client.get(
        "/api/v1/reports/profit-and-loss",
        params={"date_from": "2026-06-01", "date_to": "2026-06-30"},
        headers=org_headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["oversell_cost_adjustment"]


def _mk_material(db_session, org_id, code):
    """Material adicional (fuente de transformaciones), mismo patron que ml_material."""
    category = MaterialCategory(id=uuid4(), name=f"Cat {code}", organization_id=org_id, is_active=True)
    bu = BusinessUnit(id=uuid4(), name=f"UN {code}", organization_id=org_id, is_active=True)
    db_session.add_all([category, bu])
    db_session.flush()
    material = Material(
        id=uuid4(),
        code=code,
        name=f"Material {code}",
        category_id=category.id,
        business_unit_id=bu.id,
        default_unit="kg",
        current_stock=Decimal("0"),
        current_stock_liquidated=Decimal("0"),
        current_stock_transit=Decimal("0"),
        current_average_cost=Decimal("0"),
        organization_id=org_id,
        is_active=True,
    )
    db_session.add(material)
    db_session.commit()
    return material


def _create_transformation(client, org_headers, source, source_wh, source_qty, lines, distribution="proportional_weight", waste=0):
    resp = client.post(
        TRANS_URL,
        json={
            "source_material_id": str(source.id),
            "source_warehouse_id": str(source_wh.id),
            "source_quantity": float(source_qty),
            "waste_quantity": float(waste),
            "cost_distribution": distribution,
            "date": DOC_DATE,
            "reason": "Transformacion Modelo L PR-4",
            "lines": lines,
        },
        headers=org_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestOversellInventoryIncrease:
    """PR-4: increase sobre hueco usa el helper — sin reset destructivo del avg."""

    def test_increase_over_hole_adjustment_pnl_and_annul_roundtrip(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        from app.models.inventory_adjustment import InventoryAdjustment

        _seed_hole(client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material, 100, 300)
        # Pool: -200 @ 10.000. Increase 1.000 @ 8.000 (Ejemplo A via ajuste manual).
        adj = _increase(client, org_headers, ml_material, ml_warehouse, 1000, 8000)

        db_session.expire_all()
        adj_db = db_session.get(InventoryAdjustment, adj["id"])
        assert adj_db.cost_adjustment == Decimal("400000")
        db_session.refresh(ml_material)
        assert ml_material.current_average_cost == Decimal("8000")
        assert ml_material.current_stock_liquidated == Decimal("800")
        # ANTES del fix: reset avg=8.000 sin adjustment → los 400K se esfumaban del P&L

        assert _pnl_oversell(client, org_headers) == pytest.approx(400000, abs=1)

        # Anular el increase (Fase 5: remocion ponderada, ya no rewind). Saca
        # 1.000 x (8.000 + fill 400K/1.000) = 8.400.000 de un pool de 6.400.000
        # → rama 3: hueco -200 al avg vigente (8.000) y +400.000 a
        # annul_cost_adjustment. En junio el P&L queda limpio (el fill del
        # increase sale por status annulled); el annul-adj entra por
        # annulled_at (hoy, fuera de la ventana de junio).
        _annul_adjustment(client, org_headers, adj["id"])
        db_session.expire_all()
        db_session.refresh(ml_material)
        assert ml_material.current_average_cost == Decimal("8000")
        assert ml_material.current_stock_liquidated == Decimal("-200")
        assert db_session.get(InventoryAdjustment, adj["id"]).annul_cost_adjustment == Decimal("400000")
        assert _pnl_oversell(client, org_headers) == pytest.approx(0, abs=1)
        # Rango amplio (incluye annulled_at de hoy): el annul-adj aparece
        resp = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": "2026-06-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        assert resp.json()["oversell_cost_adjustment"] == pytest.approx(400000, abs=1)

    def test_increase_partial_fill_keeps_prev_avg(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        from app.models.inventory_adjustment import InventoryAdjustment

        _seed_hole(client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material, 100, 300)
        # Pool: -200 @ 10.000. Increase 150 @ 8.000: hueco NO cubierto → avg queda
        adj = _increase(client, org_headers, ml_material, ml_warehouse, 150, 8000)

        db_session.expire_all()
        assert db_session.get(InventoryAdjustment, adj["id"]).cost_adjustment == Decimal("300000")
        db_session.refresh(ml_material)
        assert ml_material.current_average_cost == Decimal("10000")
        assert ml_material.current_stock_liquidated == Decimal("-50")

    def test_increase_positive_pool_weighted_zero_adjustment(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        from app.models.inventory_adjustment import InventoryAdjustment

        # Paridad legacy: pool positivo → ponderado clasico, adjustment 0
        _create_purchase(client, org_headers, ml_supplier, ml_warehouse, ml_material, 100, 10000, auto=True)
        adj = _increase(client, org_headers, ml_material, ml_warehouse, 100, 8000)

        db_session.expire_all()
        assert db_session.get(InventoryAdjustment, adj["id"]).cost_adjustment == Decimal("0")
        db_session.refresh(ml_material)
        assert ml_material.current_average_cost == Decimal("9000")
        assert ml_material.current_stock_liquidated == Decimal("200")


class TestOversellTransformationDestination:
    """PR-4: linea destino que entra a pool negativo usa el helper."""

    def test_destination_over_hole_proportional_adjustment_pnl_annul(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        from app.models.material_transformation import MaterialTransformationLine

        # Destino (ml_material) en hueco: -100 @ 10.000
        _seed_hole(client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material, 100, 200)
        # Fuente independiente: 200 kg @ 5.000
        source = _mk_material(db_session, ml_material.organization_id, "ML-MOTOR")
        _create_purchase(client, org_headers, ml_supplier, ml_warehouse, source, 200, 5000, auto=True)

        # Desarme 200 kg fuente → 200 kg destino (proporcional: entra a 5.000/kg)
        trans = _create_transformation(
            client, org_headers, source, ml_warehouse, 200,
            [{
                "destination_material_id": str(ml_material.id),
                "destination_warehouse_id": str(ml_warehouse.id),
                "quantity": 200,
            }],
        )

        # filled 100 x (10.000 - 5.000) = 500.000; remaining 100 entra a 5.000
        db_session.expire_all()
        line = db_session.query(MaterialTransformationLine).filter(
            MaterialTransformationLine.transformation_id == trans["id"]
        ).one()
        assert line.cost_adjustment == Decimal("500000")
        db_session.refresh(ml_material)
        assert ml_material.current_average_cost == Decimal("5000")
        assert ml_material.current_stock_liquidated == Decimal("100")

        assert _pnl_oversell(client, org_headers) == pytest.approx(500000, abs=1)

        # Anular (Fase 5: remocion ponderada de destinos + reingreso ponderado
        # de fuente). Destino: saca 200 x (5.000 + fill 500K/200) = 1.500.000
        # de un pool de 500.000 → rama 3: hueco -100 al avg vigente (5.000) y
        # +500.000 a annul_cost_adjustment. Fuente: recupera 200 @ 5.000 exacto
        # (reingreso a su costo de salida sobre pool 0). Junio queda limpio
        # (el fill sale por status annulled); el annul-adj entra por annulled_at.
        resp = client.post(
            f"{TRANS_URL}/{trans['id']}/annul",
            json={"reason": "Anulacion test PR-4"},
            headers=org_headers,
        )
        assert resp.status_code == 200, resp.text
        db_session.expire_all()
        db_session.refresh(ml_material)
        assert ml_material.current_average_cost == Decimal("5000")
        assert ml_material.current_stock_liquidated == Decimal("-100")
        db_session.refresh(source)
        assert source.current_stock_liquidated == Decimal("200")
        assert source.current_average_cost == Decimal("5000")
        from app.models.material_transformation import MaterialTransformation as _MT
        assert db_session.get(_MT, trans["id"]).annul_cost_adjustment == Decimal("500000")
        assert _pnl_oversell(client, org_headers) == pytest.approx(0, abs=1)
        resp = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": "2026-06-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        assert resp.json()["oversell_cost_adjustment"] == pytest.approx(500000, abs=1)

    def test_destination_average_cost_method_self_neutral(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        """Metodo average_cost: el destino entra A SU PROPIO promedio → el relleno
        del hueco es neutro (filled x (avg - avg) = 0). La diferencia de valor va
        a value_difference (decision #17), no al oversell."""
        from app.models.material_transformation import MaterialTransformationLine

        _seed_hole(client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material, 100, 200)
        source = _mk_material(db_session, ml_material.organization_id, "ML-AIRE")
        _create_purchase(client, org_headers, ml_supplier, ml_warehouse, source, 200, 5000, auto=True)

        trans = _create_transformation(
            client, org_headers, source, ml_warehouse, 200,
            [{
                "destination_material_id": str(ml_material.id),
                "destination_warehouse_id": str(ml_warehouse.id),
                "quantity": 200,
            }],
            distribution="average_cost",
        )

        db_session.expire_all()
        line = db_session.query(MaterialTransformationLine).filter(
            MaterialTransformationLine.transformation_id == trans["id"]
        ).one()
        assert line.cost_adjustment == Decimal("0")
        db_session.refresh(ml_material)
        assert ml_material.current_average_cost == Decimal("10000")
        assert ml_material.current_stock_liquidated == Decimal("100")
        assert _pnl_oversell(client, org_headers) == pytest.approx(0, abs=1)


# ============================================================================
# Stress test: random walk determinista con invariantes globales
# ============================================================================

class TestInventoryStressWalk:
    """Barrido combinatorio del motor de costeo (Modelo L completo, PR-1+PR-2+PR-4).

    ~60 operaciones pseudo-aleatorias con SEMILLA FIJA (determinista, sin
    flakes): crear/liquidar compras y ventas en ordenes arbitrarios (incluye
    oversell natural), cancelar liquidadas y registradas, ajustes de inventario
    increase/decrease y anulacion de increases. Tras CADA operacion se verifican
    los invariantes globales leyendo TODO de la BD (no de un tracking paralelo
    del test):

    I1. stock == transit + liquidated (invariante duro del sistema)
    I2. stock == SUM(inventory_movements.quantity)
    I3. avg >= 0 SIEMPRE (el helper nunca produce promedios negativos)
    I4. avg == new_cost del ultimo MaterialCostHistory (revert BORRA el registro,
        por eso el ultimo MCH siempre refleja el estado vigente)
    I5. CONSERVACION DE VALOR (la promesa del Modelo L):
        liquidated x avg == compras_liquidadas_in - COGS_ventas_liquidadas
                            + ajustes_inventario_in/out (qty x unit_cost, confirmed)
                            + ajustes_oversell (compras activas + cancels
                              + cost_adjustment de ajustes confirmed)
                            + recepciones Willard confirmadas (qty x unit_cost
                              snapshot — identidad D2, SAC E2)
                            + annul_cost_adjustment de ordenes inbound (TODAS:
                              anuladas y confirmadas-editadas — el residuo de
                              edicion D18 vive en el header)
        con tolerancia = $1 + $0.005 x kg (redondeo Numeric(15,2) de unit_cost).

    I6 (SAC E2). LIBRO KG: saldo de la cuenta kg == 0.53 x Σ(qty de lineas de
        ordenes drosses confirmadas) — el libro paralelo cierra contra el
        documento fuente, no contra si mismo.

    Fase 5 (remocion ponderada): el walk anula y cancela SIN restricciones — ya
    no existe la regla de invalidacion de candidatos que PR-4 necesitaba (las
    reversiones eran rewind via MCH, exactas solo sin extracciones intermedias).
    Con remocion/reingreso ponderado la conservacion cierra por construccion
    sin importar que paso entre medias — si este walk pasa sin la regla, el gap
    de check_can_revert quedo cerrado de verdad. I5 gana los terminos de
    reversion: cancellation_cost_adjustment de compras canceladas y
    annul_cost_adjustment de ajustes anulados.
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
        # PR-4: ajustes de inventario confirmed — valor entrado/salido (quantity
        # es delta con signo) + su cost_adjustment por relleno de hueco
        from app.models.inventory_adjustment import InventoryAdjustment as IA
        ia_value = db_session.query(
            sa_func.coalesce(sa_func.sum(IA.quantity * IA.unit_cost), 0)
        ).filter(IA.material_id == material.id, IA.status == "confirmed").scalar()
        ia_cost_adj = db_session.query(
            sa_func.coalesce(sa_func.sum(IA.cost_adjustment), 0)
        ).filter(IA.material_id == material.id, IA.status == "confirmed").scalar()
        # Fase 5: reversiones ponderadas — la diferencia que la remocion no pudo
        # sacar (o el reingreso no pudo devolver) quedo reconocida en P&L
        purchase_cancel_adj = db_session.query(
            sa_func.coalesce(sa_func.sum(P.cancellation_cost_adjustment), 0)
        ).filter(
            P.status == "cancelled",
            P.id.in_(
                db_session.query(PurchaseLine.purchase_id).filter(
                    PurchaseLine.material_id == material.id
                )
            ),
        ).scalar()
        ia_annul_adj = db_session.query(
            sa_func.coalesce(sa_func.sum(IA.annul_cost_adjustment), 0)
        ).filter(IA.material_id == material.id, IA.status == "annulled").scalar()

        # SAC E2: recepciones Willard — valor entrado a identidad (snapshot) de
        # ordenes confirmadas + residuo de remocion (annul_cost_adjustment de
        # TODAS las ordenes: anuladas y confirmadas-editadas, D8/D18)
        from app.models.inbound_order import InboundOrder as IO, InboundOrderLine as IOL
        inbound_value = db_session.query(
            sa_func.coalesce(sa_func.sum(IOL.quantity * IOL.unit_cost), 0)
        ).join(IO, IOL.inbound_order_id == IO.id).filter(
            IOL.material_id == material.id, IO.status == "confirmed",
            IOL.unit_cost.isnot(None),
        ).scalar()
        inbound_annul_adj = db_session.query(
            sa_func.coalesce(sa_func.sum(IO.annul_cost_adjustment), 0)
        ).filter(
            IO.id.in_(
                db_session.query(IOL.inbound_order_id).filter(
                    IOL.material_id == material.id
                )
            )
        ).scalar()

        pool_value = material.current_stock_liquidated * material.current_average_cost
        expected = (
            Decimal(str(in_total)) - Decimal(str(cogs_total))
            + Decimal(str(purchase_adj)) + Decimal(str(cancel_adj))
            + Decimal(str(ia_value)) + Decimal(str(ia_cost_adj))
            + Decimal(str(purchase_cancel_adj)) + Decimal(str(ia_annul_adj))
            + Decimal(str(inbound_value)) + Decimal(str(inbound_annul_adj))
        )
        tolerance = Decimal("1") + tol_qty * Decimal("0.005")
        assert abs(pool_value - expected) <= tolerance, (
            f"Conservacion rota: pool={pool_value} vs esperado={expected} "
            f"(in={in_total} cogs={cogs_total} adj_compras={purchase_adj} adj_cancels={cancel_adj} "
            f"aj_inv={ia_value} aj_inv_cost={ia_cost_adj} "
            f"cxl_compras={purchase_cancel_adj} annul_aj={ia_annul_adj} "
            f"inbound={inbound_value} inbound_annul={inbound_annul_adj}, tol={tolerance})"
        )

        # I6 — libro kg contra documento fuente (solo si el walk creo inbounds)
        from app.models.kg_ledger import KgLedgerMovement as KGM
        kg_balance = db_session.query(
            sa_func.coalesce(sa_func.sum(KGM.delta_kg), 0)
        ).filter(KGM.status == "confirmed").scalar()
        expected_kg = db_session.query(
            sa_func.coalesce(sa_func.sum(IOL.quantity), 0)
        ).join(IO, IOL.inbound_order_id == IO.id).filter(
            IOL.material_id == material.id, IO.status == "confirmed",
            IO.inbound_type == "willard",
        ).scalar()
        expected_kg = (Decimal(str(expected_kg)) * Decimal("0.53"))
        assert abs(Decimal(str(kg_balance)) - expected_kg) <= Decimal("0.01"), (
            f"Libro kg descuadrado: {kg_balance} vs {expected_kg}"
        )

    def test_random_walk_all_invariants_hold(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        import random
        from datetime import datetime as _dt, timezone as _tz
        rng = random.Random(20260710)  # semilla fija → reproducible

        # Setup SAC E2: flag + formula drosses + cuenta kg (las acciones
        # inbound del walk ejercitan identidad D2 + remocion D8 + edicion D18)
        from app.models.organization import Organization
        org = db_session.get(Organization, ml_material.organization_id)
        org.settings = {"kg_ledger_enabled": True}
        db_session.commit()
        resp = client.post(
            "/api/v1/material-conversion-formulas",
            headers=org_headers,
            json={
                "material_id": str(ml_material.id),
                "formula_type": "drosses_to_lead",
                "parameters": {"lead_percentage": 0.53},
            },
        )
        assert resp.status_code == 201, resp.text
        # Clasificacion Willard (CC-005): rutea la linea al libro drosses.
        # compra_regular=True — el walk ejercita AMBOS canales con el mismo
        # material (escenario Q-04 "cuentas apartes"); con False seria
        # Willard-puro y el guard B3 (Ciclo B) bloquearia las compras del walk.
        resp = client.put(
            f"/api/v1/material-kg-profiles/{ml_material.id}",
            headers=org_headers,
            json={"compra_regular": True, "willard_world": "drosses"},
        )
        assert resp.status_code == 200, resp.text
        resp = client.post(
            "/api/v1/kg-ledger/accounts",
            headers=org_headers,
            json={
                "code": "WALK-DROSS",
                "display_name": "Willard Drosses Walk",
                "account_type": "willard_drosses",
                "third_party_id": str(ml_supplier.id),
            },
        )
        assert resp.status_code == 201, resp.text
        _today = _dt.now(_tz.utc).date().isoformat()

        def _inbound_create(qty):
            return client.post(
                "/api/v1/inbound-orders",
                headers=org_headers,
                json={
                    "inbound_type": "willard",
                    "warehouse_id": str(ml_warehouse.id),
                    "third_party_id": str(ml_supplier.id),
                    "date": _today,
                    "lines": [{"material_id": str(ml_material.id), "quantity": str(qty),
                               "scale_weight_kg": str(qty)}],  # Q-13
                },
            )

        pending_purchases: list[str] = []
        liquidated_purchases: list[str] = []
        pending_sales: list[str] = []
        liquidated_sales: list[str] = []
        confirmed_increases: list[str] = []
        confirmed_priced_decreases: list[str] = []
        confirmed_inbounds: list[str] = []
        tol_qty = Decimal("0")  # kg acumulados que pasaron por redondeo 2-dec
        saw_hole = False
        counts = {
            "pc": 0, "pl": 0, "sc": 0, "sl": 0, "s_cxl": 0,
            "p_cxl": 0, "ai": 0, "ad": 0, "aa": 0,
            "ic": 0, "ia": 0, "ie": 0, "adp": 0, "aap": 0,
        }

        for _ in range(self.OPS):
            action = rng.choices(
                [
                    "purchase_create", "purchase_liq", "sale_create", "sale_liq",
                    "sale_cancel", "purchase_cancel",
                    "adj_increase", "adj_decrease", "adj_annul",
                    "inbound_create", "inbound_annul", "inbound_edit",
                    "adj_decrease_priced", "adj_annul_priced",
                ],
                weights=[18, 15, 18, 15, 5, 5, 6, 6, 4, 8, 4, 3, 5, 3],
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
                # Fase 5: nunca bloquea (remocion ponderada, sin guard)
                resp = client.patch(f"/api/v1/purchases/{pid}/cancel", headers=org_headers)
                assert resp.status_code == 200, resp.text
                tol_qty += Decimal("400")
                counts["p_cxl"] += 1
            elif action == "adj_increase":
                qty = rng.randrange(30, 300, 10)
                cost = rng.randrange(1000, 12000, 100)
                a = _increase(client, org_headers, ml_material, ml_warehouse, qty, cost)
                confirmed_increases.append(a["id"])
                tol_qty += Decimal("300")
                counts["ai"] += 1
            elif action == "adj_decrease":
                qty = rng.randrange(30, 250, 10)
                _decrease(client, org_headers, ml_material, ml_warehouse, qty)
                counts["ad"] += 1
            elif action == "adj_annul" and confirmed_increases:
                aid = confirmed_increases.pop(rng.randrange(len(confirmed_increases)))
                # Fase 5: nunca bloquea (remocion ponderada, sin guard)
                resp = client.post(
                    f"{ADJ_URL}/{aid}/annul",
                    json={"reason": "Anulacion walk"},
                    headers=org_headers,
                )
                assert resp.status_code == 200, resp.text
                tol_qty += Decimal("300")
                counts["aa"] += 1
            elif action == "inbound_create":
                qty = rng.randrange(20, 200, 10)
                resp = _inbound_create(qty)
                assert resp.status_code == 201, resp.text
                oid = resp.json()["id"]
                # Q-16: capturar -> revisar -> confirmar (los efectos willard
                # siguen naciendo al confirmar)
                resp = client.post(
                    f"/api/v1/inbound-orders/{oid}/review", headers=org_headers
                )
                assert resp.status_code == 200, resp.text
                resp = client.post(
                    f"/api/v1/inbound-orders/{oid}/confirm", headers=org_headers
                )
                assert resp.status_code == 200, resp.text
                confirmed_inbounds.append(oid)
                tol_qty += Decimal("200")
                counts["ic"] += 1
            elif action == "inbound_annul" and confirmed_inbounds:
                oid = confirmed_inbounds.pop(rng.randrange(len(confirmed_inbounds)))
                resp = client.post(
                    f"/api/v1/inbound-orders/{oid}/annul",
                    json={"reason": "Anulacion walk"},
                    headers=org_headers,
                )
                assert resp.status_code == 200, resp.text
                tol_qty += Decimal("200")
                counts["ia"] += 1
            elif action == "inbound_edit" and confirmed_inbounds:
                # D18: revert-and-reapply — remocion al snapshot + re-entrada hoy
                oid = rng.choice(confirmed_inbounds)
                qty = rng.randrange(20, 200, 10)
                resp = client.patch(
                    f"/api/v1/inbound-orders/{oid}",
                    json={"lines": [{"material_id": str(ml_material.id), "quantity": str(qty)}]},
                    headers=org_headers,
                )
                assert resp.status_code == 200, resp.text
                tol_qty += Decimal("400")
                counts["ie"] += 1
            elif action == "adj_decrease_priced":
                # #93 D7: el motor del descuadre faltante — decrease con precio
                # explicito (remove_from_pool, MCH inbound_discrepancy). Camino
                # de servicio: el endpoint no lo expone (lo usa la liquidacion
                # de Entradas); aca se ejercita pelado, sin FK de entrada.
                from app.services.inventory_adjustment import (
                    inventory_adjustment as _ia_service,
                )
                from app.schemas.inventory_adjustment import (
                    DecreaseCreate as _DecreaseCreate,
                )
                qty = rng.randrange(20, 200, 10)
                price = rng.randrange(1000, 12000, 100)
                # db_session arrastra una transaccion de solo-lectura abierta
                # desde el primer chequeo de invariantes — func.now() de PG es
                # transaction_timestamp y estamparia el MCH con la hora de
                # INICIO del walk (ordenado antes que todo, I4 falso-roto).
                # En produccion cada request abre transaccion fresca; aca se
                # cierra la stale a mano. Artefacto del test, no del motor.
                db_session.rollback()
                adj, _w = _ia_service.decrease(
                    db_session,
                    _DecreaseCreate(
                        material_id=ml_material.id,
                        warehouse_id=ml_warehouse.id,
                        date=_today,
                        quantity=Decimal(str(qty)),
                        reason="Descuadre walk (#93)",
                    ),
                    ml_material.organization_id,
                    commit=True,
                    unit_cost_override=Decimal(str(price)),
                )
                confirmed_priced_decreases.append(str(adj.id))
                tol_qty += Decimal("200")
                counts["adp"] += 1
            elif action == "adj_annul_priced" and confirmed_priced_decreases:
                # W-1: reingreso a u_total = p + adj/q — round-trip exacto por
                # algebra tambien en rama de hueco (criterio 20)
                aid = confirmed_priced_decreases.pop(
                    rng.randrange(len(confirmed_priced_decreases))
                )
                resp = client.post(
                    f"{ADJ_URL}/{aid}/annul",
                    json={"reason": "Anulacion walk (#93)"},
                    headers=org_headers,
                )
                assert resp.status_code == 200, resp.text
                tol_qty += Decimal("200")
                counts["aap"] += 1

            self._invariants(db_session, ml_material, tol_qty)
            if ml_material.current_stock_liquidated < 0:
                saw_hole = True

        # Sanidad del walk: ejercito de verdad todos los caminos criticos
        assert counts["pl"] >= 5, counts
        assert counts["sl"] >= 5, counts
        assert counts["s_cxl"] + counts["p_cxl"] >= 1, counts
        assert counts["ai"] >= 2, counts
        assert counts["ad"] >= 2, counts
        # Fase 5: al menos una reversion ponderada real (cancel o annul)
        assert counts["p_cxl"] + counts["aa"] >= 1, counts
        # SAC E2: el walk ejercita de verdad el inbound (identidad + reversa/edicion)
        assert counts["ic"] >= 2, counts
        assert counts["ia"] + counts["ie"] >= 1, counts
        # #93 D7: decreases con precio explicito (motor del descuadre) y al
        # menos un round-trip de anulacion W-1
        assert counts["adp"] >= 2, counts
        assert counts["aap"] >= 1, counts
        assert saw_hole, f"El walk nunca paso por oversell — ajustar semilla/pesos: {counts}"

        # Cierre: liquidar todo lo pendiente y verificar una ultima vez
        for pid in list(pending_purchases):
            _liquidate_purchase(client, org_headers, pid)
        for sid in list(pending_sales):
            _liquidate_sale(client, org_headers, sid)
            tol_qty += Decimal("400")
        self._invariants(db_session, ml_material, tol_qty)


# ============================================================================
# Fase 5 (PR-5): remocion ponderada en reversiones — plan
# docs/planes/plan-fase5-remocion-ponderada.md
# ============================================================================

from app.services.inventory_costing import remove_from_pool


def _removal_equation_holds(liq, avg, qty, cost):
    """Ecuacion de conservacion del helper de remocion:
    pool_after == pool_before - qty*cost + adjustment. Exacta en las 3 ramas.
    """
    new_avg, adj = remove_from_pool(liq, avg, qty, cost)
    pool_after = (liq - qty) * new_avg
    assert pool_after == liq * avg - qty * cost + adj, (
        f"Ecuacion rota: {pool_after} != {liq * avg} - {qty * cost} + {adj}"
    )
    return new_avg, adj


class TestRemoveFromPool:
    """Unitarios puros del helper espejo (plan §3, sin BD)."""

    def test_clean_removal_leak_case(self):
        # El caso de la fuga (§1 del plan): pool 150@8.000, remover 100@6.000
        new_avg, adj = _removal_equation_holds(
            Decimal("150"), Decimal("8000"), Decimal("100"), Decimal("6000")
        )
        assert new_avg == Decimal("12000")  # el valor queda EN el inventario
        assert adj == Decimal("0")

    def test_clean_removal_is_inverse_of_incorporate(self):
        # incorporate ∘ remove == identidad cuando nada paso entre medias
        liq, avg = Decimal("1100"), (Decimal("100") * Decimal("10000") + Decimal("1000") * Decimal("8000")) / Decimal("1100")
        new_avg, adj = _removal_equation_holds(liq, avg, Decimal("1000"), Decimal("8000"))
        assert abs(new_avg - Decimal("10000")) < Decimal("0.0001")
        assert adj == Decimal("0")

    def test_insufficient_value_avg_stays(self):
        # Rama 2: pool 150@5.000 (=750.000), remover 100@10.000 (=1.000.000)
        new_avg, adj = _removal_equation_holds(
            Decimal("150"), Decimal("5000"), Decimal("100"), Decimal("10000")
        )
        assert new_avg == Decimal("5000")  # queda — evita avg negativo y stock a $0
        assert adj == Decimal("500000")

    def test_removal_into_hole(self):
        # Rama 3: pool 20@10.000, remover 100@8.000 → hueco -80 al avg vigente
        new_avg, adj = _removal_equation_holds(
            Decimal("20"), Decimal("10000"), Decimal("100"), Decimal("8000")
        )
        assert new_avg == Decimal("10000")
        assert adj == Decimal("-200000")

    def test_exact_empty_boundary(self):
        # Remocion exacta del pool completo al mismo costo: adj 0, avg remanente
        new_avg, adj = _removal_equation_holds(
            Decimal("100"), Decimal("2000"), Decimal("100"), Decimal("2000")
        )
        assert (new_avg, adj) == (Decimal("2000"), Decimal("0"))


class TestFase5WeightedRemoval:
    """End-to-end de los caminos de reversion (plan §4 + §9)."""

    def test_leak_case_now_conserves(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        """LA secuencia de la fuga (plan §1): increase → decrease → annul del
        increase. Antes: guard permitia el rewind y $100.000 se evaporaban
        (pool quedaba en 50x10.000=500.000). Ahora: remocion ponderada deja
        50@12.000=600.000 — el valor que las salidas baratas no se llevaron
        queda EN el inventario, nada en P&L (rama 1, adj 0)."""
        from app.models.inventory_adjustment import InventoryAdjustment

        _create_purchase(client, org_headers, ml_supplier, ml_warehouse, ml_material, 100, 10000, auto=True)
        adj = _increase(client, org_headers, ml_material, ml_warehouse, 100, 6000)
        db_session.refresh(ml_material)
        assert ml_material.current_average_cost == Decimal("8000")
        _decrease(client, org_headers, ml_material, ml_warehouse, 50)  # sale a 8.000, sin MCH

        # Annul del increase: antes el guard lo permitia (sin MCH posterior) y
        # el rewind corrompia; ahora la remocion ponderada conserva.
        _annul_adjustment(client, org_headers, adj["id"])

        db_session.expire_all()
        db_session.refresh(ml_material)
        assert ml_material.current_stock_liquidated == Decimal("50")
        assert ml_material.current_average_cost == Decimal("12000")
        adj_db = db_session.get(InventoryAdjustment, adj["id"])
        assert adj_db.annul_cost_adjustment == Decimal("0")
        # Append-only: el MCH del increase sigue existiendo + hay registro del annul
        assert db_session.query(MaterialCostHistory).filter(
            MaterialCostHistory.source_type == "adjustment_increase",
            MaterialCostHistory.source_id == adj["id"],
        ).count() == 1
        assert db_session.query(MaterialCostHistory).filter(
            MaterialCostHistory.source_type == "adjustment_annulment",
            MaterialCostHistory.source_id == adj["id"],
        ).count() == 1

    def test_h1_cancel_with_commission_and_fill(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material, ml_commissionist
    ):
        """H1: la remocion saca la contribucion REAL — costo ajustado por
        comision (leido del InventoryMovement) + fill adjustment prorrateado.
        Con el precio crudo, el valor de la comision quedaria en el pool."""
        from app.models.purchase import Purchase as _P

        _seed_hole(client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material, 50, 150)
        # Pool -100@10.000. Compra 200@8.000 + comision fija 40.000 → adjusted 8.200
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
        purchase_id = resp.json()["id"]
        _liquidate_purchase(client, org_headers, purchase_id)
        db_session.refresh(ml_material)
        assert ml_material.current_average_cost == Decimal("8200")  # fill 180.000

        # Cancelar: u_total = 8.200 + 180.000/200 = 9.100. remove(100@8.200, 200, 9.100)
        # → rama 3: avg queda 8.200, adj = 200x(9.100-8.200) = 180.000
        _cancel_purchase(client, org_headers, purchase_id)
        db_session.expire_all()
        db_session.refresh(ml_material)
        assert ml_material.current_stock_liquidated == Decimal("-100")
        assert ml_material.current_average_cost == Decimal("8200")
        assert db_session.get(_P, purchase_id).cancellation_cost_adjustment == Decimal("180000")

    def test_cancel_earlier_purchase_now_allowed(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        """El caso del 79%: cancelar una compra con MCH posterior (otra compra
        liquidada despues) antes daba 400; ahora remocion ponderada exacta."""
        p1 = _create_purchase(client, org_headers, ml_supplier, ml_warehouse, ml_material, 1000, 2000, auto=True)
        _create_purchase(client, org_headers, ml_supplier, ml_warehouse, ml_material, 1000, 2400, auto=True)
        db_session.refresh(ml_material)
        assert ml_material.current_average_cost == Decimal("2200")

        _cancel_purchase(client, org_headers, p1["id"])  # antes: 400 "Cancele primero"
        db_session.expire_all()
        db_session.refresh(ml_material)
        assert ml_material.current_stock_liquidated == Decimal("1000")
        assert ml_material.current_average_cost == Decimal("2400")

    def test_cancel_purchase_after_transformation_out(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        """Decision #40 superseded: cancelar la compra de un material ya
        transformado antes bloqueaba (transformation_out MCH); ahora pasa y
        conserva (el hueco proyectado avisa via warning PR-3)."""
        purchase = _create_purchase(client, org_headers, ml_supplier, ml_warehouse, ml_material, 200, 10000, auto=True)
        dest = _mk_material(db_session, ml_material.organization_id, "ML-DEST40")
        _create_transformation(
            client, org_headers, ml_material, ml_warehouse, 150,
            [{
                "destination_material_id": str(dest.id),
                "destination_warehouse_id": str(ml_warehouse.id),
                "quantity": 150,
            }],
        )
        db_session.refresh(ml_material)
        assert ml_material.current_stock_liquidated == Decimal("50")

        data = _cancel_purchase(client, org_headers, purchase["id"])  # antes: 400
        assert data["status"] == "cancelled"
        assert data.get("warnings"), "Esperaba warning de hueco proyectado (PR-3)"
        db_session.refresh(ml_material)
        assert ml_material.current_stock_liquidated == Decimal("-150")
        # Remocion 200@10.000 de pool 50@10.000 → rama 3: avg queda, adj 0
        assert ml_material.current_average_cost == Decimal("10000")

    def test_annul_decrease_weighted_reentry(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        """El primo hermano: anular un decrease reingresaba al avg VIGENTE (si
        el avg se movio entre medias, fugaba valor). Ahora reingresa al
        unit_cost de la salida (adjustment.unit_cost) ponderado."""
        from app.models.inventory_adjustment import InventoryAdjustment

        _create_purchase(client, org_headers, ml_supplier, ml_warehouse, ml_material, 100, 10000, auto=True)
        dec = _decrease(client, org_headers, ml_material, ml_warehouse, 50)  # sale a 10.000
        # Compra barata mueve el avg: (50x10.000 + 50x2.000)/100 = 6.000
        _create_purchase(client, org_headers, ml_supplier, ml_warehouse, ml_material, 50, 2000, auto=True)
        db_session.refresh(ml_material)
        assert ml_material.current_average_cost == Decimal("6000")

        # Annul del decrease: reingresa 50 @ 10.000 (su costo de salida)
        # → (100x6.000 + 50x10.000)/150 = 7.333,33 — con el avg vigente
        # habria reingresado a 6.000 y perdido 200.000.
        _annul_adjustment(client, org_headers, dec["id"])
        db_session.expire_all()
        db_session.refresh(ml_material)
        assert ml_material.current_stock_liquidated == Decimal("150")
        assert abs(ml_material.current_average_cost - Decimal("7333.3333")) < Decimal("0.01")
        assert db_session.get(InventoryAdjustment, dec["id"]).annul_cost_adjustment == Decimal("0")
        # Conservacion manual: 100x10.000 + 50x2.000 - 50x10.000 + 50x10.000 = 1.100.000
        value = ml_material.current_stock_liquidated * ml_material.current_average_cost
        assert abs(value - Decimal("1100000")) <= Decimal("1")


class TestFase5AsOfH2:
    """H2: el MCH append-only no debe reescribir cortes historicos (#41/#61).
    Se prueba directo contra _get_inventory_as_of (la funcion bajo test)."""

    def _inventory_as_of(self, db_session, org_id, as_of):
        from datetime import date as _date, datetime as _dt, time as _time, timedelta as _td, timezone as _tz
        from app.services.reports import report_service
        cutoff_dt = _dt.combine(as_of + _td(days=1), _time.min, tzinfo=_tz.utc)
        return report_service._get_inventory_as_of(db_session, org_id, cutoff_dt)

    def test_golden_three_cuts_and_live_parity(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        """Liquidar → vender → cancelar. Cortes: antes (nada), entre (doctrina
        #41: la compra cancelada nunca existio), despues (== balance vivo,
        gracias al MCH de cancelacion incondicional)."""
        from datetime import date as _date

        org_id = ml_material.organization_id
        # Compra 100@10.000 el 2-jun (auto → liquidated_at 2-jun)
        resp = client.post(
            "/api/v1/purchases",
            json={
                "supplier_id": str(ml_supplier.id),
                "date": "2026-06-02T12:00:00",
                "lines": [{
                    "material_id": str(ml_material.id),
                    "quantity": 100,
                    "unit_price": 10000,
                    "warehouse_id": str(ml_warehouse.id),
                }],
                "auto_liquidate": True,
            },
            headers=org_headers,
        )
        assert resp.status_code == 201, resp.text
        purchase_id = resp.json()["id"]
        # Venta 60 el 3-jun, liquidada (liquidated_at 3-jun)
        resp = client.post(
            "/api/v1/sales",
            json={
                "customer_id": str(ml_customer.id),
                "warehouse_id": str(ml_warehouse.id),
                "date": "2026-06-03T12:00:00",
                "lines": [{"material_id": str(ml_material.id), "quantity": 60, "unit_price": 12000}],
                "commissions": [],
                "auto_liquidate": True,
            },
            headers=org_headers,
        )
        assert resp.status_code == 201, resp.text

        # Cancelar la compra HOY (cancelled_at = hoy; adj 0 → avg no cambia,
        # pero el MCH purchase_cancellation se escribe IGUAL — sin el, la
        # cadena visible pierde el costo y as-of(hoy) != vivo)
        _cancel_purchase(client, org_headers, purchase_id)
        db_session.expire_all()
        db_session.refresh(ml_material)
        assert ml_material.current_stock_liquidated == Decimal("-60")
        assert ml_material.current_average_cost == Decimal("10000")

        # Corte ANTES (1-jun): sin stock ni costo
        inv = self._inventory_as_of(db_session, org_id, _date(2026, 6, 1))
        assert ml_material.id not in inv

        # Corte ENTRE (5-jun): la compra "nunca existio" → stock = -60 (solo
        # la venta), costo = 0 (el MCH de la liquidacion esta oculto y el
        # fallback 1 toma su previous_cost = 0, el avg pre-compra)
        inv = self._inventory_as_of(db_session, org_id, _date(2026, 6, 5))
        stock, cost = inv[ml_material.id]
        assert stock == Decimal("-60")
        assert cost == Decimal("0")

        # Corte DESPUES (hoy): == balance vivo
        from datetime import datetime as _dt, timezone as _tz
        inv = self._inventory_as_of(db_session, org_id, _dt.now(_tz.utc).date())
        stock, cost = inv[ml_material.id]
        assert stock == Decimal("-60")
        assert cost == Decimal("10000")

    def test_fallback1_dedicated_cancelled_op_previous_cost(
        self, client, org_headers, db_session, ml_supplier, ml_customer, ml_warehouse, ml_material
    ):
        """Dedicado a Fallback 1 (exigido por QA): material cuyo UNICO MCH
        relevante al corte es de una op cancelada — fuerza el fallback. Su
        previous_cost (avg pre-op) es evidencia valida; el previous_cost de un
        MCH posterior NO-cancelado (contaminado por la op 'que nunca existio')
        seria incorrecto."""
        from datetime import date as _date

        org_id = ml_material.organization_id
        # 2-jun: decrease 30 (stock -30, SIN MCH — por eso el corte caera a fallback)
        resp = client.post(
            f"{ADJ_URL}/decrease",
            json={
                "material_id": str(ml_material.id),
                "warehouse_id": str(ml_warehouse.id),
                "quantity": 30,
                "date": "2026-06-02T12:00:00",
                "reason": "Decrease pre-corte H2",
            },
            headers=org_headers,
        )
        assert resp.status_code == 201, resp.text
        # 3-jun: compra 100@10.000 liquidada (MCH purchase_liquidation 3-jun)
        resp = client.post(
            "/api/v1/purchases",
            json={
                "supplier_id": str(ml_supplier.id),
                "date": "2026-06-03T12:00:00",
                "lines": [{
                    "material_id": str(ml_material.id),
                    "quantity": 100,
                    "unit_price": 10000,
                    "warehouse_id": str(ml_warehouse.id),
                }],
                "auto_liquidate": True,
            },
            headers=org_headers,
        )
        assert resp.status_code == 201, resp.text
        purchase_id = resp.json()["id"]
        # 6-jun: increase 50@6.000 (MCH adjustment_increase 6-jun — su
        # previous_cost YA incluye la compra: evidencia contaminada para 5-jun)
        resp = client.post(
            f"{ADJ_URL}/increase",
            json={
                "material_id": str(ml_material.id),
                "warehouse_id": str(ml_warehouse.id),
                "quantity": 50,
                "unit_cost": 6000,
                "date": "2026-06-06T12:00:00",
                "reason": "Increase post-corte H2",
            },
            headers=org_headers,
        )
        assert resp.status_code == 201, resp.text
        # HOY: cancelar la compra
        _cancel_purchase(client, org_headers, purchase_id)

        # Corte 5-jun: stock = -30 (decrease; compra cancelada excluida).
        # Costo: sin MCH visible <= 5-jun → Fallback 1. El primer MCH posterior
        # es el purchase_liquidation del 3-jun?? No: transaction_date 3-jun ES
        # <= 5-jun pero esta OCULTO en el camino principal (op cancelada). En
        # fallback 1 los MCH de ops canceladas SI cuentan → toma su
        # previous_cost = 0 (avg pre-compra, doctrina exacta). Si el filtro
        # fuera uniforme (excluirlo tambien del fallback), tomaria el
        # previous_cost del increase del 6-jun — contaminado por la compra.
        inv = self._inventory_as_of(db_session, org_id, _date(2026, 6, 5))
        stock, cost = inv[ml_material.id]
        assert stock == Decimal("-30")
        assert cost == Decimal("0")

        # Corte HOY: == vivo (el MCH de la cancelacion es el ultimo visible)
        from datetime import datetime as _dt, timezone as _tz
        db_session.refresh(ml_material)
        inv = self._inventory_as_of(db_session, org_id, _dt.now(_tz.utc).date())
        stock, cost = inv[ml_material.id]
        assert stock == ml_material.current_stock_liquidated
        assert cost == ml_material.current_average_cost
