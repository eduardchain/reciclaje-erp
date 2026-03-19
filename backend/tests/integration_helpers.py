"""
Helpers compartidos para tests de integracion end-to-end.

NO es un archivo de tests — es importado por test_integration_*.py.
Provee: constantes, setup helpers, API wrappers, assertion helpers.
"""
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models.material import Material, MaterialCategory
from app.models.money_account import MoneyAccount
from app.models.expense_category import ExpenseCategory
from app.models.warehouse import Warehouse
from app.models.business_unit import BusinessUnit

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
TODAY = "2026-03-19"
DATE_FROM = "2026-03-01"
DATE_TO = "2026-03-31"


# ---------------------------------------------------------------------------
# Setup Helpers (crean entities en DB directamente)
# ---------------------------------------------------------------------------

def create_material_category(db: Session, org_id, name: str) -> MaterialCategory:
    cat = MaterialCategory(name=name, organization_id=org_id)
    db.add(cat)
    db.flush()
    return cat


def create_business_unit(db: Session, org_id, name: str) -> BusinessUnit:
    bu = BusinessUnit(name=name, organization_id=org_id)
    db.add(bu)
    db.flush()
    return bu


def create_material(db: Session, org_id, code: str, name: str, category_id, bu_id=None) -> Material:
    mat = Material(
        code=code,
        name=name,
        category_id=category_id,
        business_unit_id=bu_id,
        organization_id=org_id,
        current_stock=Decimal("0"),
        current_stock_transit=Decimal("0"),
        current_stock_liquidated=Decimal("0"),
        current_average_cost=Decimal("0"),
    )
    db.add(mat)
    db.flush()
    return mat


def create_warehouse(db: Session, org_id, name: str) -> Warehouse:
    wh = Warehouse(name=name, organization_id=org_id, is_active=True)
    db.add(wh)
    db.flush()
    return wh


def create_account(db: Session, org_id, name: str, balance: float = 0) -> MoneyAccount:
    acc = MoneyAccount(
        name=name,
        account_type="bank",
        current_balance=Decimal(str(balance)),
        organization_id=org_id,
    )
    db.add(acc)
    db.flush()
    return acc


def create_expense_category(db: Session, org_id, name: str, is_direct: bool = False) -> ExpenseCategory:
    cat = ExpenseCategory(
        name=name,
        is_direct_expense=is_direct,
        organization_id=org_id,
    )
    db.add(cat)
    db.flush()
    return cat


# ---------------------------------------------------------------------------
# API Operation Wrappers
# ---------------------------------------------------------------------------

def api_create_purchase(client, headers, *, supplier_id, lines, auto_liquidate=False,
                        immediate_payment=False, payment_account_id=None, date=TODAY) -> dict:
    payload = {
        "supplier_id": str(supplier_id),
        "date": f"{date}T12:00:00",
        "lines": [
            {
                "material_id": str(l["material_id"]),
                "quantity": l["quantity"],
                "unit_price": l["unit_price"],
                "warehouse_id": str(l["warehouse_id"]),
            }
            for l in lines
        ],
        "auto_liquidate": auto_liquidate,
        "immediate_payment": immediate_payment,
    }
    if payment_account_id:
        payload["payment_account_id"] = str(payment_account_id)
    resp = client.post("/api/v1/purchases", json=payload, headers=headers)
    assert resp.status_code == 201, f"Create purchase failed: {resp.json()}"
    return resp.json()


def api_liquidate_purchase(client, headers, purchase_id, *,
                           immediate_payment=False, payment_account_id=None) -> dict:
    payload = {"immediate_payment": immediate_payment}
    if payment_account_id:
        payload["payment_account_id"] = str(payment_account_id)
    resp = client.patch(f"/api/v1/purchases/{purchase_id}/liquidate", json=payload, headers=headers)
    assert resp.status_code == 200, f"Liquidate purchase failed: {resp.json()}"
    return resp.json()


def api_cancel_purchase(client, headers, purchase_id) -> dict:
    resp = client.patch(f"/api/v1/purchases/{purchase_id}/cancel", headers=headers)
    assert resp.status_code == 200, f"Cancel purchase failed: {resp.json()}"
    return resp.json()


def api_create_sale(client, headers, *, customer_id, warehouse_id, lines, auto_liquidate=False,
                    immediate_collection=False, collection_account_id=None,
                    commissions=None, date=TODAY) -> dict:
    payload = {
        "customer_id": str(customer_id),
        "warehouse_id": str(warehouse_id),
        "date": f"{date}T12:00:00",
        "lines": [
            {
                "material_id": str(l["material_id"]),
                "quantity": l["quantity"],
                "unit_price": l["unit_price"],
            }
            for l in lines
        ],
        "auto_liquidate": auto_liquidate,
        "immediate_collection": immediate_collection,
        "commissions": commissions or [],
    }
    if collection_account_id:
        payload["collection_account_id"] = str(collection_account_id)
    resp = client.post("/api/v1/sales", json=payload, headers=headers)
    assert resp.status_code == 201, f"Create sale failed: {resp.json()}"
    return resp.json()


def api_liquidate_sale(client, headers, sale_id, *,
                       immediate_collection=False, collection_account_id=None) -> dict:
    payload = {"immediate_collection": immediate_collection}
    if collection_account_id:
        payload["collection_account_id"] = str(collection_account_id)
    resp = client.patch(f"/api/v1/sales/{sale_id}/liquidate", json=payload, headers=headers)
    assert resp.status_code == 200, f"Liquidate sale failed: {resp.json()}"
    return resp.json()


def api_cancel_sale(client, headers, sale_id) -> dict:
    resp = client.patch(f"/api/v1/sales/{sale_id}/cancel", headers=headers)
    assert resp.status_code == 200, f"Cancel sale failed: {resp.json()}"
    return resp.json()


def api_create_double_entry(client, headers, *, supplier_id, customer_id, lines,
                            commissions=None, auto_liquidate=False, date=TODAY) -> dict:
    payload = {
        "supplier_id": str(supplier_id),
        "customer_id": str(customer_id),
        "date": date,
        "lines": [
            {
                "material_id": str(l["material_id"]),
                "quantity": l["quantity"],
                "purchase_unit_price": l["purchase_unit_price"],
                "sale_unit_price": l["sale_unit_price"],
            }
            for l in lines
        ],
        "commissions": commissions or [],
        "auto_liquidate": auto_liquidate,
    }
    resp = client.post("/api/v1/double-entries", json=payload, headers=headers)
    assert resp.status_code == 201, f"Create DE failed: {resp.json()}"
    return resp.json()


def api_liquidate_double_entry(client, headers, de_id) -> dict:
    resp = client.patch(f"/api/v1/double-entries/{de_id}/liquidate", json={}, headers=headers)
    assert resp.status_code == 200, f"Liquidate DE failed: {resp.json()}"
    return resp.json()


def api_cancel_double_entry(client, headers, de_id) -> dict:
    resp = client.patch(f"/api/v1/double-entries/{de_id}/cancel", headers=headers)
    assert resp.status_code == 200, f"Cancel DE failed: {resp.json()}"
    return resp.json()


def api_money_movement(client, headers, endpoint_suffix, payload) -> dict:
    # Normalizar UUIDs a string
    for key in list(payload.keys()):
        if hasattr(payload[key], "hex"):
            payload[key] = str(payload[key])
    resp = client.post(f"/api/v1/money-movements/{endpoint_suffix}", json=payload, headers=headers)
    assert resp.status_code == 201, f"Money movement '{endpoint_suffix}' failed: {resp.json()}"
    return resp.json()


def api_create_transformation(client, headers, *, source_material_id, source_warehouse_id,
                              source_quantity, waste_quantity, cost_distribution, lines,
                              reason="Test", date=TODAY) -> dict:
    payload = {
        "source_material_id": str(source_material_id),
        "source_warehouse_id": str(source_warehouse_id),
        "source_quantity": source_quantity,
        "waste_quantity": waste_quantity,
        "cost_distribution": cost_distribution,
        "lines": [
            {
                "destination_material_id": str(l["destination_material_id"]),
                "destination_warehouse_id": str(l["destination_warehouse_id"]),
                "quantity": l["quantity"],
                **({"unit_cost": l["unit_cost"]} if "unit_cost" in l else {}),
            }
            for l in lines
        ],
        "date": f"{date}T12:00:00",
        "reason": reason,
    }
    resp = client.post("/api/v1/inventory/transformations", json=payload, headers=headers)
    assert resp.status_code == 201, f"Create transformation failed: {resp.json()}"
    return resp.json()


def api_create_adjustment(client, headers, *, adjustment_type, material_id, warehouse_id,
                          quantity, unit_cost=None, reason="Test", date=TODAY) -> dict:
    payload = {
        "material_id": str(material_id),
        "warehouse_id": str(warehouse_id),
        "quantity": quantity,
        "date": f"{date}T12:00:00",
        "reason": reason,
    }
    if unit_cost is not None:
        payload["unit_cost"] = unit_cost
    resp = client.post(f"/api/v1/inventory/adjustments/{adjustment_type}", json=payload, headers=headers)
    assert resp.status_code == 201, f"Adjustment '{adjustment_type}' failed: {resp.json()}"
    return resp.json()


def api_create_fixed_asset(client, headers, payload) -> dict:
    resp = client.post("/api/v1/fixed-assets/", json=payload, headers=headers)
    assert resp.status_code == 201, f"Create fixed asset failed: {resp.json()}"
    return resp.json()


def api_apply_pending_depreciations(client, headers) -> dict:
    resp = client.post("/api/v1/fixed-assets/apply-pending", headers=headers)
    assert resp.status_code == 200, f"Apply pending failed: {resp.json()}"
    return resp.json()


def api_cancel_asset(client, headers, asset_id) -> dict:
    resp = client.post(f"/api/v1/fixed-assets/{asset_id}/cancel", headers=headers)
    assert resp.status_code == 200, f"Cancel asset failed: {resp.json()}"
    return resp.json()


def api_warehouse_transfer(client, headers, *, material_id, source_warehouse_id,
                           destination_warehouse_id, quantity, reason="Transfer", date=TODAY) -> dict:
    """POST /api/v1/inventory/adjustments/warehouse-transfer"""
    payload = {
        "material_id": str(material_id),
        "source_warehouse_id": str(source_warehouse_id),
        "destination_warehouse_id": str(destination_warehouse_id),
        "quantity": quantity,
        "date": f"{date}T12:00:00",
        "reason": reason,
    }
    resp = client.post("/api/v1/inventory/adjustments/warehouse-transfer", json=payload, headers=headers)
    assert resp.status_code == 201, f"Warehouse transfer failed: {resp.json()}"
    return resp.json()


def api_annul_movement(client, headers, movement_id, reason="Error") -> dict:
    """POST /api/v1/money-movements/{id}/annul"""
    resp = client.post(f"/api/v1/money-movements/{movement_id}/annul",
                       json={"reason": reason}, headers=headers)
    assert resp.status_code == 200, f"Annul movement failed: {resp.json()}"
    return resp.json()


def api_create_scheduled_expense(client, headers, payload) -> dict:
    """POST /api/v1/scheduled-expenses/"""
    for key in list(payload.keys()):
        if hasattr(payload[key], "hex"):
            payload[key] = str(payload[key])
    resp = client.post("/api/v1/scheduled-expenses/", json=payload, headers=headers)
    assert resp.status_code == 201, f"Create scheduled expense failed: {resp.json()}"
    return resp.json()


def api_apply_scheduled_expense(client, headers, se_id) -> dict:
    """POST /api/v1/scheduled-expenses/{id}/apply"""
    resp = client.post(f"/api/v1/scheduled-expenses/{se_id}/apply", headers=headers)
    assert resp.status_code == 201, f"Apply scheduled expense failed: {resp.json()}"
    return resp.json()


def api_create_profit_distribution(client, headers, payload) -> dict:
    """POST /api/v1/profit-distributions/"""
    resp = client.post("/api/v1/profit-distributions/", json=payload, headers=headers)
    assert resp.status_code == 201, f"Create profit distribution failed: {resp.json()}"
    return resp.json()


# ---------------------------------------------------------------------------
# Assertion Helpers
# ---------------------------------------------------------------------------

def assert_material(client, headers, material_id, *, total, transit=0, liquidated=0, avg_cost):
    resp = client.get(f"/api/v1/materials/{material_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_stock"] == pytest.approx(total, abs=0.01), \
        f"Material stock: expected {total}, got {data['current_stock']}"
    assert data["current_stock_transit"] == pytest.approx(transit, abs=0.01), \
        f"Material transit: expected {transit}, got {data['current_stock_transit']}"
    assert data["current_stock_liquidated"] == pytest.approx(liquidated, abs=0.01), \
        f"Material liquidated: expected {liquidated}, got {data['current_stock_liquidated']}"
    assert data["current_average_cost"] == pytest.approx(avg_cost, abs=0.01), \
        f"Material avg_cost: expected {avg_cost}, got {data['current_average_cost']}"


def assert_tp_balance(client, headers, tp_id, expected_balance):
    resp = client.get(f"/api/v1/third-parties/{tp_id}", headers=headers)
    assert resp.status_code == 200
    actual = resp.json()["current_balance"]
    assert actual == pytest.approx(expected_balance, abs=0.01), \
        f"TP balance: expected {expected_balance}, got {actual}"


def assert_account_balance(client, headers, account_id, expected_balance):
    resp = client.get(f"/api/v1/money-accounts/{account_id}", headers=headers)
    assert resp.status_code == 200
    actual = resp.json()["current_balance"]
    assert actual == pytest.approx(expected_balance, abs=0.01), \
        f"Account balance: expected {expected_balance}, got {actual}"


def assert_pnl(client, headers, date_from=DATE_FROM, date_to=DATE_TO, **expected):
    resp = client.get(
        "/api/v1/reports/profit-and-loss",
        params={"date_from": date_from, "date_to": date_to},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    for key, val in expected.items():
        assert data[key] == pytest.approx(val, abs=0.01), \
            f"P&L {key}: expected {val}, got {data[key]}"


def assert_balance_sheet(client, headers, **expected):
    resp = client.get("/api/v1/reports/balance-sheet", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    for key, val in expected.items():
        # Soportar campos anidados como assets.cash_and_bank
        if "." in key:
            parts = key.split(".")
            actual = data
            for p in parts:
                actual = actual[p]
        else:
            actual = data[key]
        assert actual == pytest.approx(val, abs=0.01), \
            f"Balance Sheet {key}: expected {val}, got {actual}"


def assert_cash_flow(client, headers, date_from=DATE_FROM, date_to=DATE_TO, **expected):
    resp = client.get(
        "/api/v1/reports/cash-flow",
        params={"date_from": date_from, "date_to": date_to},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    for key, val in expected.items():
        if "." in key:
            parts = key.split(".")
            actual = data
            for p in parts:
                actual = actual[p]
        else:
            actual = data[key]
        assert actual == pytest.approx(val, abs=0.01), \
            f"Cash Flow {key}: expected {val}, got {actual}"


def assert_pnl_equals_balance(client, headers, date_from=DATE_FROM, date_to=DATE_TO):
    """ACID TEST: P&L net_profit == BS accumulated_profit == BS equity."""
    pnl_resp = client.get(
        "/api/v1/reports/profit-and-loss",
        params={"date_from": date_from, "date_to": date_to},
        headers=headers,
    )
    assert pnl_resp.status_code == 200
    pnl_net = pnl_resp.json()["net_profit"]

    bs_resp = client.get("/api/v1/reports/balance-sheet", headers=headers)
    assert bs_resp.status_code == 200
    bs = bs_resp.json()
    bs_accumulated = bs["accumulated_profit"]
    bs_equity = bs["equity"]

    bs_distributed = bs.get("distributed_profit", 0)

    assert pnl_net == pytest.approx(bs_accumulated, abs=1.0), \
        f"ACID TEST FAILED: P&L net_profit ({pnl_net}) != BS accumulated_profit ({bs_accumulated}). " \
        f"BS: total_assets={bs['total_assets']}, total_liabilities={bs['total_liabilities']}, " \
        f"equity={bs_equity}, distributed={bs_distributed}"
    expected_equity = bs_accumulated - bs_distributed
    assert expected_equity == pytest.approx(bs_equity, abs=1.0), \
        f"ACID TEST FAILED: accumulated({bs_accumulated}) - distributed({bs_distributed}) = {expected_equity} != equity({bs_equity}). " \
        f"BS: total_assets={bs['total_assets']}, total_liabilities={bs['total_liabilities']}"
