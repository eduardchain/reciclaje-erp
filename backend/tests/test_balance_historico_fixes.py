"""
Tests del paquete de fixes de Balance Histórico (incidente Costa jul-2026).

Plan: docs/planes/plan-fixes-balance-historico.md (v2.1, opción B).

Promesa central (reproducción del incidente como fixtures): dar de baja un
activo, desactivar un tercero/cuenta, o liquidar tarde una operación NO
cambian un corte histórico anterior a la acción.

- Fix 1: activos dados de baja después del corte siguen en el balance histórico.
- Fix 2: terceros y cuentas inactivos siguen en cortes históricos (is_inactive).
- Fix 3: inventario histórico cuenta compras/ventas por liquidated_at; el
  MCH de liquidación nace con transaction_date = fecha de liquidación; los
  commission_accrual nacen con date = liquidated_at (opción B).
- Fix 4: estado de cuenta posiciona eventos comerciales en liquidated_at con
  document_date; TEST DE ORO: paridad statement ↔ balance detallado as-of
  con fixture no-trivial (DP + comisión + venta standalone, QA obligatoria #2).
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.models.money_movement import MoneyMovement
from app.models.material_cost_history import MaterialCostHistory
from tests.conftest import create_third_party_with_category, _get_or_create_category
from tests.integration_helpers import (
    create_material_category,
    create_business_unit,
    create_material,
    create_warehouse,
    create_account,
    create_expense_category,
    api_create_purchase,
    api_create_sale,
    api_create_double_entry,
    api_create_fixed_asset,
    api_money_movement,
    api_cancel_purchase,
    api_cancel_sale,
)

BD_URL = "/api/v1/reports/balance-detailed"
BS_URL = "/api/v1/reports/balance-sheet"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bd(client, headers, as_of=None):
    url = f"{BD_URL}?as_of_date={as_of}" if as_of else BD_URL
    resp = client.get(url, headers=headers)
    assert resp.status_code == 200, resp.json()
    return resp.json()


def _bd_find_tp(data, tp_id):
    """Busca un tercero en todas las secciones del balance detallado.

    Returns (signed_balance, item, section_key) — signo: activo +, pasivo −.
    """
    tp_id = str(tp_id)
    for side, sign in (("assets", 1), ("liabilities", -1)):
        for key, section in data[side].items():
            for item in section["items"]:
                if item["id"] == tp_id:
                    return sign * item["balance"], item, key
    return None, None, None


def _bd_inventory_value(data, material_id=None):
    items = data["assets"]["inventory_liquidated"]["items"]
    if material_id is not None:
        items = [i for i in items if i["id"] == str(material_id)]
    return sum(i["balance"] for i in items)


def _statement(client, headers, tp_id, date_from="2026-01-01"):
    resp = client.get(
        f"/api/v1/money-movements/third-party/{tp_id}?date_from={date_from}&limit=5000",
        headers=headers,
    )
    assert resp.status_code == 200, resp.json()
    return resp.json()


def _statement_balance_at(items, cutoff: str) -> float:
    """Saldo corrido del estado de cuenta al final del día `cutoff` (YYYY-MM-DD)."""
    balance = 0.0
    for evt in items:
        if evt["event_type"] == "initial_balance":
            balance = evt["balance_after"]
            continue
        if evt["date"] and evt["date"][:10] <= cutoff:
            balance = evt["balance_after"]
    return balance


def _liquidate_purchase(client, headers, purchase_id, liquidation_date=None):
    payload = {"liquidation_date": liquidation_date} if liquidation_date else {}
    resp = client.patch(f"/api/v1/purchases/{purchase_id}/liquidate", json=payload, headers=headers)
    assert resp.status_code == 200, resp.json()
    return resp.json()


def _liquidate_sale(client, headers, sale_id, liquidation_date=None, commissions=None):
    payload = {}
    if liquidation_date:
        payload["liquidation_date"] = liquidation_date
    if commissions is not None:
        payload["commissions"] = commissions
    resp = client.patch(f"/api/v1/sales/{sale_id}/liquidate", json=payload, headers=headers)
    assert resp.status_code == 200, resp.json()
    return resp.json()


def _liquidate_de(client, headers, de_id, liquidation_date=None):
    payload = {"liquidation_date": liquidation_date} if liquidation_date else {}
    resp = client.patch(f"/api/v1/double-entries/{de_id}/liquidate", json=payload, headers=headers)
    assert resp.status_code == 200, resp.json()
    return resp.json()


@pytest.fixture
def base(db_session, test_organization, client, org_headers):
    """Entidades base: material con stock liquidado en abril + terceros."""
    org_id = test_organization.id
    cat = create_material_category(db_session, org_id, "HistCat")
    bu = create_business_unit(db_session, org_id, "HistBU")
    mat = create_material(db_session, org_id, "HI-01", "Hierro Hist", cat.id, bu.id)
    wh = create_warehouse(db_session, org_id, "Bodega Hist")
    acc = create_account(db_session, org_id, "Cuenta Hist", balance=50_000_000)
    supplier = create_third_party_with_category(db_session, org_id, "Prov Hist", "material_supplier")
    customer = create_third_party_with_category(db_session, org_id, "Cli Hist", "customer")
    db_session.commit()

    # Stock base: compra 1-abr liquidada mismo día (500 @ 5000)
    api_create_purchase(
        client, org_headers, supplier_id=supplier.id,
        lines=[{"material_id": mat.id, "quantity": 500, "unit_price": 5000, "warehouse_id": wh.id}],
        auto_liquidate=True, date="2026-04-01",
    )
    return {
        "org_id": org_id, "cat": cat, "bu": bu, "mat": mat, "wh": wh,
        "acc": acc, "supplier": supplier, "customer": customer,
    }


# ---------------------------------------------------------------------------
# Fix 1 — Activos dados de baja después del corte
# ---------------------------------------------------------------------------

class TestFix1DisposedAssets:

    def _create_fa(self, client, headers, db_session, org_id, value=10_000_000):
        exp_cat = create_expense_category(db_session, org_id, "Deprec Hist", is_direct=False)
        fa_acc = create_account(db_session, org_id, "Cuenta FA", balance=value * 2)
        db_session.commit()
        return api_create_fixed_asset(client, headers, {
            "name": "Camion Test LGU",
            "asset_code": "FA-HIST-1",
            "purchase_date": "2026-04-01",
            "purchase_value": value,
            "salvage_value": 0,
            "depreciation_rate": 1.0,
            "depreciation_start_date": "2026-05-01",
            "expense_category_id": str(exp_cat.id),
            "source_account_id": str(fa_acc.id),
        })

    def test_dispose_does_not_rewrite_past_cutoff(
        self, client, org_headers, db_session, test_organization, base,
    ):
        """Reproducción del incidente (camión LGU-673): la baja de hoy no borra
        el activo de un corte anterior."""
        fa = self._create_fa(client, org_headers, db_session, test_organization.id)
        fa_id = fa["id"]

        before = _bd(client, org_headers, as_of="2026-06-30")
        fa_items = before["assets"]["fixed_assets"]["items"]
        assert any(i["id"] == fa_id for i in fa_items)
        value_before = before["assets"]["fixed_assets"]["total"]

        # Dar de baja HOY
        resp = client.post(f"/api/v1/fixed-assets/{fa_id}/dispose",
                           json={"reason": "Vendido"}, headers=org_headers)
        assert resp.status_code == 200

        # El corte 30-jun NO cambia (antes del fix: el activo desaparecía)
        after = _bd(client, org_headers, as_of="2026-06-30")
        assert after["assets"]["fixed_assets"]["total"] == pytest.approx(value_before, abs=0.01)
        item = next(i for i in after["assets"]["fixed_assets"]["items"] if i["id"] == fa_id)
        assert item["current_value"] == pytest.approx(10_000_000, abs=0.01)
        assert "(baja " in item["name"]

        # balance-sheet (helper agregado) también lo conserva
        bs = client.get(f"{BS_URL}?as_of_date=2026-06-30", headers=org_headers).json()
        assert bs["assets"]["fixed_assets"] == pytest.approx(value_before, abs=0.01)

    def test_disposed_before_cutoff_excluded(
        self, client, org_headers, db_session, test_organization, base,
    ):
        """Un corte POSTERIOR a la baja no incluye el activo (boundary >=)."""
        fa = self._create_fa(client, org_headers, db_session, test_organization.id)
        fa_id = fa["id"]
        client.post(f"/api/v1/fixed-assets/{fa_id}/dispose",
                    json={"reason": "Vendido"}, headers=org_headers)
        # Fijar la baja en el pasado (9-jun) para probar el boundary sin
        # depender del reloj/timezone del test
        db_session.execute(text(
            "UPDATE fixed_assets SET disposed_at = '2026-06-09T12:00:00+00' WHERE id = :fid"
        ), {"fid": fa_id})
        db_session.commit()

        # Corte 30-jun (posterior a la baja): excluido
        data = _bd(client, org_headers, as_of="2026-06-30")
        assert not any(i["id"] == fa_id for i in data["assets"]["fixed_assets"]["items"])

        # Corte 31-may (anterior a la baja): incluido a valor pre-baja
        data2 = _bd(client, org_headers, as_of="2026-05-31")
        item = next(i for i in data2["assets"]["fixed_assets"]["items"] if i["id"] == fa_id)
        assert item["current_value"] == pytest.approx(10_000_000, abs=0.01)

    def test_cancelled_always_excluded(
        self, client, org_headers, db_session, test_organization, base,
    ):
        """Activo cancelado = nunca existió (filosofía 735c2c3), en cualquier corte."""
        fa = self._create_fa(client, org_headers, db_session, test_organization.id)
        fa_id = fa["id"]
        resp = client.post(f"/api/v1/fixed-assets/{fa_id}/cancel",
                           json={"reason": "Error de captura"}, headers=org_headers)
        assert resp.status_code == 200, resp.json()

        data = _bd(client, org_headers, as_of="2026-06-30")
        assert not any(i["id"] == fa_id for i in data["assets"]["fixed_assets"]["items"])


