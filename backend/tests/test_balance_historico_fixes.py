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


# ---------------------------------------------------------------------------
# Fix 2 — Terceros y cuentas inactivos en cortes históricos
# ---------------------------------------------------------------------------

class TestFix2InactiveEntities:

    def test_deactivate_tp_does_not_rewrite_past_cutoff(
        self, client, org_headers, db_session, base,
    ):
        """Reproducción del incidente (Luminarias/Cienaga): desactivar un tercero
        con saldo 0 hoy no lo borra de cortes donde SÍ tenía saldo."""
        cust = base["customer"]
        # Venta liquidada 20-abr: cliente queda debiendo 100.000
        sale = api_create_sale(
            client, org_headers, customer_id=cust.id, warehouse_id=base["wh"].id,
            lines=[{"material_id": base["mat"].id, "quantity": 10, "unit_price": 10000}],
            auto_liquidate=False, date="2026-04-10",
        )
        _liquidate_sale(client, org_headers, sale["id"], liquidation_date="2026-04-20")

        before, _, section_before = _bd_find_tp(
            _bd(client, org_headers, as_of="2026-04-30"), cust.id)
        assert before == pytest.approx(100_000, abs=0.01)
        assert section_before == "customers_receivable"

        # Cobrar TODO el 20-may (saldo 0) y desactivar
        api_money_movement(client, org_headers, "customer-collection", {
            "customer_id": cust.id, "amount": 100_000,
            "account_id": base["acc"].id, "date": "2026-05-20T12:00:00",
            "description": "Cobro total",
        })
        resp = client.delete(f"/api/v1/third-parties/{cust.id}", headers=org_headers)
        assert resp.status_code == 200, resp.json()

        # Corte 30-abr: el tercero sigue con su saldo de entonces + flag inactivo
        after_bal, after_item, section = _bd_find_tp(
            _bd(client, org_headers, as_of="2026-04-30"), cust.id)
        assert after_bal == pytest.approx(100_000, abs=0.01)
        assert section == "customers_receivable"
        assert after_item["is_inactive"] is True

        # balance-sheet histórico también lo cuenta
        bs = client.get(f"{BS_URL}?as_of_date=2026-04-30", headers=org_headers).json()
        assert bs["assets"]["accounts_receivable"] == pytest.approx(100_000, abs=0.01)

    def test_deactivated_tp_absent_when_balance_zero_at_cutoff(
        self, client, org_headers, db_session, base,
    ):
        """En un corte posterior al cobro total, el inactivo no aparece (saldo 0)."""
        cust = base["customer"]
        sale = api_create_sale(
            client, org_headers, customer_id=cust.id, warehouse_id=base["wh"].id,
            lines=[{"material_id": base["mat"].id, "quantity": 10, "unit_price": 10000}],
            auto_liquidate=False, date="2026-04-10",
        )
        _liquidate_sale(client, org_headers, sale["id"], liquidation_date="2026-04-20")
        api_money_movement(client, org_headers, "customer-collection", {
            "customer_id": cust.id, "amount": 100_000,
            "account_id": base["acc"].id, "date": "2026-05-20T12:00:00",
            "description": "Cobro total",
        })
        client.delete(f"/api/v1/third-parties/{cust.id}", headers=org_headers)

        bal, item, _ = _bd_find_tp(_bd(client, org_headers, as_of="2026-06-15"), cust.id)
        assert item is None, "tercero con saldo 0 al corte no debe listarse"

    def test_fast_path_excludes_inactive(self, client, org_headers, db_session, base):
        """El balance ACTUAL (sin as_of) mantiene el comportamiento previo."""
        cust = base["customer"]
        client.delete(f"/api/v1/third-parties/{cust.id}", headers=org_headers)
        bal, item, _ = _bd_find_tp(_bd(client, org_headers), cust.id)
        assert item is None

    def test_inactive_account_in_past_cutoff(
        self, client, org_headers, db_session, test_organization, base,
    ):
        """Cuenta desactivada hoy sigue en cortes donde tenía saldo."""
        org_id = test_organization.id
        acc2 = create_account(db_session, org_id, "Cuenta Temporal", balance=0)
        exp_cat = create_expense_category(db_session, org_id, "Gasto Hist", is_direct=False)
        db_session.commit()

        api_money_movement(client, org_headers, "service-income", {
            "amount": 5_000_000, "account_id": acc2.id,
            "date": "2026-04-15T12:00:00", "description": "Ingreso",
        })
        api_money_movement(client, org_headers, "expense", {
            "amount": 5_000_000, "account_id": acc2.id,
            "date": "2026-05-15T12:00:00", "description": "Gasto",
            "expense_category_id": str(exp_cat.id),
        })
        resp = client.delete(f"/api/v1/money-accounts/{acc2.id}", headers=org_headers)
        assert resp.status_code == 200, resp.json()

        data = _bd(client, org_headers, as_of="2026-04-30")
        item = next(
            (i for i in data["assets"]["cash_and_bank"]["items"] if i["id"] == str(acc2.id)),
            None,
        )
        assert item is not None, "cuenta inactiva con saldo al corte debe listarse"
        assert item["balance"] == pytest.approx(5_000_000, abs=0.01)
        assert item["is_inactive"] is True

    def test_active_items_have_is_inactive_false(self, client, org_headers, base):
        data = _bd(client, org_headers, as_of="2026-06-30")
        for i in data["assets"]["cash_and_bank"]["items"]:
            assert i["is_inactive"] is False


# ---------------------------------------------------------------------------
# Fix 3 — Inventario histórico por fecha de liquidación + fechas canónicas
# ---------------------------------------------------------------------------

class TestFix3InventoryByLiquidation:

    def test_late_sale_liquidation_does_not_rewrite_cutoff(
        self, client, org_headers, base,
    ):
        """Reproducción del incidente (ventas Aburrà): liquidar hoy una venta de
        abril NO baja el inventario del corte de abril; baja en la fecha de
        liquidación."""
        mat = base["mat"]
        sale = api_create_sale(
            client, org_headers, customer_id=base["customer"].id, warehouse_id=base["wh"].id,
            lines=[{"material_id": mat.id, "quantity": 100, "unit_price": 9000}],
            auto_liquidate=False, date="2026-04-20",
        )
        # Corte 3-may con la venta REGISTRADA: stock intacto (500 @ 5000)
        v_before = _bd_inventory_value(_bd(client, org_headers, as_of="2026-05-03"), mat.id)
        assert v_before == pytest.approx(2_500_000, abs=0.01)

        # Liquidar con fecha 20-may
        _liquidate_sale(client, org_headers, sale["id"], liquidation_date="2026-05-20")

        # El corte 3-may NO cambió (antes del fix caía a 400 unidades)
        v_after = _bd_inventory_value(_bd(client, org_headers, as_of="2026-05-03"), mat.id)
        assert v_after == pytest.approx(v_before, abs=0.01)

        # En un corte posterior a la liquidación el stock sí salió
        v_late = _bd_inventory_value(_bd(client, org_headers, as_of="2026-05-25"), mat.id)
        assert v_late == pytest.approx(2_000_000, abs=0.01)  # 400 @ 5000

    def test_purchase_transit_then_liquidation_counts_at_liq_date(
        self, client, org_headers, base,
    ):
        """Compra en tránsito: excluida del corte; al liquidar entra en la fecha
        de liquidación, no en la fecha del documento."""
        mat = base["mat"]
        p = api_create_purchase(
            client, org_headers, supplier_id=base["supplier"].id,
            lines=[{"material_id": mat.id, "quantity": 200, "unit_price": 6000, "warehouse_id": base["wh"].id}],
            auto_liquidate=False, date="2026-04-10",
        )
        v_before = _bd_inventory_value(_bd(client, org_headers, as_of="2026-04-15"), mat.id)
        assert v_before == pytest.approx(2_500_000, abs=0.01)  # solo la base

        _liquidate_purchase(client, org_headers, p["id"], liquidation_date="2026-05-10")

        # Corte 15-abr: estable (antes del fix, el flip la metía en 10-abr)
        v_after = _bd_inventory_value(_bd(client, org_headers, as_of="2026-04-15"), mat.id)
        assert v_after == pytest.approx(v_before, abs=0.01)

        # Corte 15-may: entra el stock (700 unidades al costo promedio nuevo)
        data_late = _bd(client, org_headers, as_of="2026-05-15")
        item = next(i for i in data_late["assets"]["inventory_liquidated"]["items"]
                    if i["id"] == str(mat.id))
        assert item["stock"] == pytest.approx(700, abs=0.001)

    def test_cancelled_purchase_no_phantom_stock(
        self, client, org_headers, db_session, test_organization, base,
    ):
        """Compra liquidada y cancelada después: desaparece de TODOS los cortes
        (antes dejaba stock fantasma en cortes entre documento y cancelación)."""
        org_id = test_organization.id
        mat2 = create_material(db_session, org_id, "HI-02", "Cobre Hist", base["cat"].id, base["bu"].id)
        db_session.commit()

        api_create_purchase(
            client, org_headers, supplier_id=base["supplier"].id,
            lines=[{"material_id": mat2.id, "quantity": 50, "unit_price": 8000, "warehouse_id": base["wh"].id}],
            auto_liquidate=True, date="2026-04-05",
        )
        v = _bd_inventory_value(_bd(client, org_headers, as_of="2026-04-30"), mat2.id)
        assert v == pytest.approx(400_000, abs=0.01)

        # Cancelar HOY → el corte de abril ya no la muestra (nunca existió)
        purchases = client.get("/api/v1/purchases?limit=50", headers=org_headers).json()
        target = next(p for p in purchases["items"]
                      if any(l["material_id"] == str(mat2.id) for l in p["lines"]))
        api_cancel_purchase(client, org_headers, target["id"])

        v_after = _bd_inventory_value(_bd(client, org_headers, as_of="2026-04-30"), mat2.id)
        assert v_after == pytest.approx(0, abs=0.01)

    def test_cutoff_cost_stable_when_old_purchase_liquidated_late(
        self, client, org_headers, base, db_session,
    ):
        """El MCH de una liquidación tardía nace con transaction_date = fecha de
        liquidación → el costo de cortes anteriores no se reescribe."""
        mat = base["mat"]
        # Costo al 30-abr: 5000 (compra base)
        data = _bd(client, org_headers, as_of="2026-04-30")
        item = next(i for i in data["assets"]["inventory_liquidated"]["items"]
                    if i["id"] == str(mat.id))
        assert item["avg_cost"] == pytest.approx(5000, abs=0.01)

        # Compra doc 20-abr liquidada con fecha 20-may @ 9000
        p = api_create_purchase(
            client, org_headers, supplier_id=base["supplier"].id,
            lines=[{"material_id": mat.id, "quantity": 500, "unit_price": 9000, "warehouse_id": base["wh"].id}],
            auto_liquidate=False, date="2026-04-20",
        )
        _liquidate_purchase(client, org_headers, p["id"], liquidation_date="2026-05-20")

        # MCH nació con transaction_date = 20-may (no 20-abr)
        mch = db_session.query(MaterialCostHistory).filter_by(
            source_type="purchase_liquidation", source_id=p["id"],
        ).first()
        assert mch is not None
        assert mch.transaction_date == date(2026, 5, 20)

        # Costo del corte 30-abr: intacto (antes del fix saltaba a 7000)
        data2 = _bd(client, org_headers, as_of="2026-04-30")
        item2 = next(i for i in data2["assets"]["inventory_liquidated"]["items"]
                     if i["id"] == str(mat.id))
        assert item2["avg_cost"] == pytest.approx(5000, abs=0.01)

        # Y el corte 31-may sí ve el promedio nuevo (7000 = (500*5000+500*9000)/1000)
        data3 = _bd(client, org_headers, as_of="2026-05-31")
        item3 = next(i for i in data3["assets"]["inventory_liquidated"]["items"]
                     if i["id"] == str(mat.id))
        assert item3["avg_cost"] == pytest.approx(7000, abs=0.01)

    def test_commission_accrual_born_at_liquidation_date(
        self, client, org_headers, db_session, test_organization, base,
    ):
        """Opción B: el commission_accrual nace con date = liquidated_at."""
        org_id = test_organization.id
        comisionista = create_third_party_with_category(
            db_session, org_id, "Comisionista Hist", "service_provider")
        db_session.commit()

        sale = api_create_sale(
            client, org_headers, customer_id=base["customer"].id, warehouse_id=base["wh"].id,
            lines=[{"material_id": base["mat"].id, "quantity": 10, "unit_price": 10000}],
            commissions=[{
                "third_party_id": str(comisionista.id), "concept": "Com",
                "commission_type": "fixed", "commission_value": 5000,
            }],
            auto_liquidate=False, date="2026-04-20",
        )
        _liquidate_sale(client, org_headers, sale["id"], liquidation_date="2026-05-20")

        mm = db_session.query(MoneyMovement).filter_by(
            movement_type="commission_accrual", sale_id=sale["id"],
        ).first()
        assert mm is not None
        assert mm.date.date() == date(2026, 5, 20)

    def test_dp_commission_accrual_born_at_liquidation_date(
        self, client, org_headers, db_session, test_organization, base,
    ):
        """Opción B en DPs: liq_dt se pasa como parámetro (trampa de orden QA #1)."""
        org_id = test_organization.id
        dp_supplier = create_third_party_with_category(db_session, org_id, "Prov DP Hist", "material_supplier")
        dp_customer = create_third_party_with_category(db_session, org_id, "Cli DP Hist", "customer")
        comisionista = create_third_party_with_category(db_session, org_id, "Com DP Hist", "service_provider")
        db_session.commit()

        de = api_create_double_entry(
            client, org_headers, supplier_id=dp_supplier.id, customer_id=dp_customer.id,
            lines=[{"material_id": base["mat"].id, "quantity": 10,
                    "purchase_unit_price": 5000, "sale_unit_price": 6000}],
            commissions=[{
                "third_party_id": str(comisionista.id), "concept": "Com DP",
                "commission_type": "fixed", "commission_value": 3000,
            }],
            date="2026-04-20",
        )
        _liquidate_de(client, org_headers, de["id"], liquidation_date="2026-05-20")

        mm = db_session.query(MoneyMovement).filter_by(
            movement_type="commission_accrual", sale_id=de["sale_id"],
        ).first()
        assert mm is not None
        assert mm.date.date() == date(2026, 5, 20)

    def test_migration_backfill_idempotent(self, db_session, org_headers, client, base):
        """La lógica de la migración 4d8f2c1e9a7b: alinear → segunda pasada 0 filas."""
        p = api_create_purchase(
            client, org_headers, supplier_id=base["supplier"].id,
            lines=[{"material_id": base["mat"].id, "quantity": 10, "unit_price": 5000, "warehouse_id": base["wh"].id}],
            auto_liquidate=False, date="2026-04-02",
        )
        _liquidate_purchase(client, org_headers, p["id"], liquidation_date="2026-05-02")
        # Desalinear a mano (simular dato pre-fix)
        db_session.execute(text(
            "UPDATE material_cost_histories SET transaction_date = '2026-04-02' "
            "WHERE source_type='purchase_liquidation' AND source_id = :pid"
        ), {"pid": p["id"]})
        db_session.commit()

        upd = text("""
            UPDATE material_cost_histories mch
            SET transaction_date = (p.liquidated_at AT TIME ZONE 'UTC')::date
            FROM purchases p
            WHERE mch.source_type = 'purchase_liquidation' AND mch.source_id = p.id
              AND p.liquidated_at IS NOT NULL
              AND mch.transaction_date IS DISTINCT FROM (p.liquidated_at AT TIME ZONE 'UTC')::date
        """)
        r1 = db_session.execute(upd)
        db_session.commit()
        assert r1.rowcount >= 1
        r2 = db_session.execute(upd)
        db_session.commit()
        assert r2.rowcount == 0


# ---------------------------------------------------------------------------
# Fix 4 — Estado de cuenta por fecha de liquidación
# ---------------------------------------------------------------------------

class TestFix4StatementByLiquidation:

    def test_purchase_positioned_at_liquidation_with_document_date(
        self, client, org_headers, base,
    ):
        p = api_create_purchase(
            client, org_headers, supplier_id=base["supplier"].id,
            lines=[{"material_id": base["mat"].id, "quantity": 20, "unit_price": 5000, "warehouse_id": base["wh"].id}],
            auto_liquidate=False, date="2026-04-20",
        )
        _liquidate_purchase(client, org_headers, p["id"], liquidation_date="2026-05-20")

        items = _statement(client, org_headers, base["supplier"].id)["items"]
        evt = next(e for e in items if e["source"] == "purchase" and e["source_id"] == p["id"])
        assert evt["date"][:10] == "2026-05-20"
        assert evt["document_date"][:10] == "2026-04-20"

    def test_windowing_follows_liquidation_date(self, client, org_headers, base):
        """Ventana y saldo de apertura (#55) siguen la fecha de liquidación."""
        p = api_create_purchase(
            client, org_headers, supplier_id=base["supplier"].id,
            lines=[{"material_id": base["mat"].id, "quantity": 20, "unit_price": 5000, "warehouse_id": base["wh"].id}],
            auto_liquidate=False, date="2026-04-20",
        )
        _liquidate_purchase(client, org_headers, p["id"], liquidation_date="2026-05-20")

        # Ventana desde 1-may: la compra (liq 20-may) SE LISTA y no está en apertura
        data = _statement(client, org_headers, base["supplier"].id, date_from="2026-05-01")
        assert any(e["source"] == "purchase" and e["source_id"] == p["id"] for e in data["items"])
        # apertura solo tiene la compra base de abril (-2.5M)
        assert data["opening_balance"] == pytest.approx(-2_500_000, abs=0.01)

        # Ventana desde 1-jun: absorbida en apertura, no listada
        data2 = _statement(client, org_headers, base["supplier"].id, date_from="2026-06-01")
        assert not any(e.get("source_id") == p["id"] for e in data2["items"])
        assert data2["opening_balance"] == pytest.approx(-2_600_000, abs=0.01)

    def test_commission_positioned_with_its_sale(
        self, client, org_headers, db_session, test_organization, base,
    ):
        """La comisión del comisionista aparece en la fecha de liquidación de la
        venta, nunca antes."""
        org_id = test_organization.id
        comisionista = create_third_party_with_category(
            db_session, org_id, "Com Stmt", "service_provider")
        db_session.commit()

        sale = api_create_sale(
            client, org_headers, customer_id=base["customer"].id, warehouse_id=base["wh"].id,
            lines=[{"material_id": base["mat"].id, "quantity": 10, "unit_price": 10000}],
            commissions=[{
                "third_party_id": str(comisionista.id), "concept": "Com",
                "commission_type": "fixed", "commission_value": 5000,
            }],
            auto_liquidate=False, date="2026-04-20",
        )
        _liquidate_sale(client, org_headers, sale["id"], liquidation_date="2026-05-20")

        items = _statement(client, org_headers, comisionista.id)["items"]
        comm_events = [e for e in items if e["event_type"] == "commission_accrual"]
        assert len(comm_events) == 1
        assert comm_events[0]["date"][:10] == "2026-05-20"

    def test_dp_positioned_at_liquidation_date(
        self, client, org_headers, db_session, test_organization, base,
    ):
        org_id = test_organization.id
        dp_supplier = create_third_party_with_category(db_session, org_id, "Prov DP Stmt", "material_supplier")
        dp_customer = create_third_party_with_category(db_session, org_id, "Cli DP Stmt", "customer")
        db_session.commit()

        de = api_create_double_entry(
            client, org_headers, supplier_id=dp_supplier.id, customer_id=dp_customer.id,
            lines=[{"material_id": base["mat"].id, "quantity": 10,
                    "purchase_unit_price": 5000, "sale_unit_price": 6000}],
            date="2026-04-20",
        )
        _liquidate_de(client, org_headers, de["id"], liquidation_date="2026-05-20")

        items = _statement(client, org_headers, dp_supplier.id)["items"]
        evt = next(e for e in items if e["event_type"] == "double_entry_purchase")
        assert evt["date"][:10] == "2026-05-20"
        assert evt["document_date"][:10] == "2026-04-20"

    def test_cancelled_pair_adjacent_and_balance_neutral(
        self, client, org_headers, db_session, test_organization, base,
    ):
        """Venta liquidada y cancelada: ambos eventos en la fecha de liquidación,
        sin efecto en el saldo corrido."""
        org_id = test_organization.id
        cust2 = create_third_party_with_category(db_session, org_id, "Cli Cancel", "customer")
        db_session.commit()

        sale = api_create_sale(
            client, org_headers, customer_id=cust2.id, warehouse_id=base["wh"].id,
            lines=[{"material_id": base["mat"].id, "quantity": 10, "unit_price": 10000}],
            auto_liquidate=False, date="2026-04-20",
        )
        _liquidate_sale(client, org_headers, sale["id"], liquidation_date="2026-05-20")
        api_cancel_sale(client, org_headers, sale["id"])

        data = _statement(client, org_headers, cust2.id)
        evts = [e for e in data["items"] if e.get("source_id") == sale["id"]]
        assert len(evts) == 2
        assert all(e["date"][:10] == "2026-05-20" for e in evts)
        assert {e["status"] for e in evts} == {"cancelled", "annulled"}
        # Saldo final del tercero: 0 (los eventos cancelados no mueven balance)
        assert data["current_balance"] == pytest.approx(0, abs=0.01)
        if data["items"]:
            assert data["items"][-1]["balance_after"] == pytest.approx(0, abs=0.01)

    def test_golden_parity_statement_vs_balance_detailed(
        self, client, org_headers, db_session, test_organization, base,
    ):
        """🔴 TEST DE ORO (QA obligatoria #2): saldo corrido del estado de cuenta
        al corte X == saldo del tercero en balance detallado as-of X.

        Fixture no-trivial por flujo natural: el tercero X es cliente de una
        venta standalone, cliente de un DP, comisionista de otra venta (accrual)
        y receptor de un cobro — los dedup de accruals y la representación de
        DPs difieren entre los dos code paths; un fixture trivial no protege nada.
        """
        from app.models.third_party_category import ThirdPartyCategoryAssignment

        org_id = test_organization.id
        # X: customer + service_provider (multi-behavior)
        x = create_third_party_with_category(db_session, org_id, "Multi X", "customer")
        sp_cat = _get_or_create_category(db_session, org_id, "service_provider")
        db_session.add(ThirdPartyCategoryAssignment(third_party_id=x.id, category_id=sp_cat.id))
        dp_supplier = create_third_party_with_category(db_session, org_id, "Prov DP Gold", "material_supplier")
        other_customer = create_third_party_with_category(db_session, org_id, "Cli Otro Gold", "customer")
        db_session.commit()

        # (a) Venta standalone a X: doc 10-abr, liq 20-abr → X +100.000
        s1 = api_create_sale(
            client, org_headers, customer_id=x.id, warehouse_id=base["wh"].id,
            lines=[{"material_id": base["mat"].id, "quantity": 10, "unit_price": 10000}],
            auto_liquidate=False, date="2026-04-10",
        )
        _liquidate_sale(client, org_headers, s1["id"], liquidation_date="2026-04-20")

        # (b) DP con X como cliente: doc 5-may, liq 15-may → X +60.000
        de = api_create_double_entry(
            client, org_headers, supplier_id=dp_supplier.id, customer_id=x.id,
            lines=[{"material_id": base["mat"].id, "quantity": 10,
                    "purchase_unit_price": 5000, "sale_unit_price": 6000}],
            date="2026-05-05",
        )
        _liquidate_de(client, org_headers, de["id"], liquidation_date="2026-05-15")

        # (c) Venta a OTRO cliente con comisión a X: doc 20-may, liq 25-may → X -5.000
        s2 = api_create_sale(
            client, org_headers, customer_id=other_customer.id, warehouse_id=base["wh"].id,
            lines=[{"material_id": base["mat"].id, "quantity": 5, "unit_price": 10000}],
            commissions=[{
                "third_party_id": str(x.id), "concept": "Com Gold",
                "commission_type": "fixed", "commission_value": 5000,
            }],
            auto_liquidate=False, date="2026-05-20",
        )
        _liquidate_sale(client, org_headers, s2["id"], liquidation_date="2026-05-25")

        # (d) Cobro a X: 10-jun → X -50.000
        api_money_movement(client, org_headers, "customer-collection", {
            "customer_id": x.id, "amount": 50_000,
            "account_id": base["acc"].id, "date": "2026-06-10T12:00:00",
            "description": "Cobro parcial X",
        })

        expected = {
            "2026-04-30": 100_000,           # solo (a)
            "2026-05-31": 155_000,           # (a)+(b)-(c)
            "2026-07-01": 105_000,           # todo
        }
        stmt_items = _statement(client, org_headers, x.id)["items"]
        for cutoff, exp in expected.items():
            stmt_bal = _statement_balance_at(stmt_items, cutoff)
            bd_bal, item, section = _bd_find_tp(
                _bd(client, org_headers, as_of=cutoff), x.id)
            assert stmt_bal == pytest.approx(exp, abs=1), f"statement@{cutoff}"
            assert bd_bal == pytest.approx(exp, abs=1), (
                f"balance-detailed@{cutoff} (section={section})"
            )
            assert stmt_bal == pytest.approx(bd_bal, abs=1), (
                f"PARIDAD ROTA @{cutoff}: statement={stmt_bal} vs balance={bd_bal}"
            )
