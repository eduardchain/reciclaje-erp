"""
Escenario 10: Gastos Diferidos + Distribución de Utilidades — Stress Test.

Cubre Gastos Diferidos:
- Crear deferred → fondeo (deferred_funding) descuenta cuenta
- Tercero sistema [Prepago] auto-creado con saldo = total_amount
- Aplicar multiples cuotas → prepaid decrece, P&L operating_expenses sube
- prepaid_expenses en Balance Sheet
- Aplicar cuando no hay cuotas pendientes → 400
- Cancelar scheduled expense (cuotas previas quedan aplicadas)
- Deferred con UN asignada

Cubre Distribución:
- Distribución a multiples socios
- NO afecta P&L ni Cash Flow (solo Balance Sheet)
- distributed_profit en Balance Sheet
- equity = accumulated - distributed
- Capital return despues de distribución

P&L == Balance Sheet acid test.
"""
import pytest
from app.models.third_party import ThirdParty
from app.models.third_party_category import ThirdPartyCategory, ThirdPartyCategoryAssignment
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    TODAY, DATE_FROM, DATE_TO,
    create_material_category, create_business_unit, create_material,
    create_warehouse, create_account, create_expense_category,
    api_money_movement, api_create_purchase, api_create_sale,
    api_create_scheduled_expense, api_apply_scheduled_expense,
    api_create_profit_distribution,
    assert_account_balance, assert_tp_balance,
    assert_pnl, assert_balance_sheet, assert_cash_flow, assert_pnl_equals_balance,
)


@pytest.fixture
def scenario(db_session, test_organization):
    org_id = test_organization.id
    cat = create_material_category(db_session, org_id, "Metales INT10")
    bu = create_business_unit(db_session, org_id, "Chatarra INT10")
    material = create_material(db_session, org_id, "INT10-FE", "Chatarra INT10", cat.id, bu.id)
    warehouse = create_warehouse(db_session, org_id, "Bodega INT10")
    account = create_account(db_session, org_id, "Cuenta INT10", balance=0)
    cat_arriendo = create_expense_category(db_session, org_id, "Arriendo INT10", is_direct=False)
    cat_seguro = create_expense_category(db_session, org_id, "Seguro INT10", is_direct=False)

    # 2 inversores con categoría "Socios" para profit_distribution
    inv_cat = ThirdPartyCategory(name="Socios INT10", behavior_type="investor", organization_id=org_id)
    db_session.add(inv_cat)
    db_session.flush()
    investor_1 = ThirdParty(name="Socio Principal INT10", organization_id=org_id)
    investor_2 = ThirdParty(name="Socio Minoritario INT10", organization_id=org_id)
    db_session.add_all([investor_1, investor_2])
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(third_party_id=investor_1.id, category_id=inv_cat.id))
    db_session.add(ThirdPartyCategoryAssignment(third_party_id=investor_2.id, category_id=inv_cat.id))

    supplier = create_third_party_with_category(db_session, org_id, "Proveedor INT10", "material_supplier")
    customer = create_third_party_with_category(db_session, org_id, "Cliente INT10", "customer")
    db_session.commit()
    return {
        "material": material, "warehouse": warehouse, "account": account,
        "cat_arriendo": cat_arriendo, "cat_seguro": cat_seguro,
        "investor_1": investor_1, "investor_2": investor_2,
        "supplier": supplier, "customer": customer, "bu": bu,
    }


class TestDeferredAndDistributionStress:

    def test_deferred_and_distribution_full(self, client, org_headers, scenario):
        s = scenario
        h = org_headers
        aid = str(s["account"].id)

        # Capital $1M desde socio 1 ($700K) + socio 2 ($300K)
        api_money_movement(client, h, "capital-injection", {
            "investor_id": s["investor_1"].id, "amount": 700_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Capital socio 1",
        })
        api_money_movement(client, h, "capital-injection", {
            "investor_id": s["investor_2"].id, "amount": 300_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Capital socio 2",
        })
        assert_account_balance(client, h, aid, 1_000_000)

        # =================================================================
        # PASO 1: Crear deferred expense A — $12K / 12 meses
        # deferred_funding: cuenta -$12K, tercero [Prepago] +$12K
        # =================================================================
        se_a = api_create_scheduled_expense(client, h, {
            "name": "Arriendo anual",
            "total_amount": 12_000, "total_months": 12,
            "source_account_id": s["account"].id,
            "expense_category_id": s["cat_arriendo"].id,
            "start_date": "2026-03-01", "apply_day": 1,
        })
        assert_account_balance(client, h, aid, 988_000)
        # Verificar estado del scheduled expense
        resp_se = client.get(f"/api/v1/scheduled-expenses/{se_a['id']}", headers=h)
        assert resp_se.json()["applied_months"] == 0

        # =================================================================
        # PASO 2: Crear deferred expense B — $6K / 6 meses, con UN
        # =================================================================
        se_b = api_create_scheduled_expense(client, h, {
            "name": "Seguro equipos",
            "total_amount": 6_000, "total_months": 6,
            "source_account_id": s["account"].id,
            "expense_category_id": s["cat_seguro"].id,
            "start_date": "2026-03-01", "apply_day": 15,
            "business_unit_id": s["bu"].id,
        })
        assert_account_balance(client, h, aid, 982_000)

        # =================================================================
        # PASO 3: Aplicar cuota 1 de A ($1K) y cuota 1 de B ($1K)
        # P&L: operating_expenses = $2K (2 cuotas deferred_expense)
        # =================================================================
        api_apply_scheduled_expense(client, h, se_a["id"])
        api_apply_scheduled_expense(client, h, se_b["id"])

        assert_pnl(client, h, operating_expenses=2_000)

        # Verificar applied_months
        resp_a = client.get(f"/api/v1/scheduled-expenses/{se_a['id']}", headers=h)
        assert resp_a.json()["applied_months"] == 1
        resp_b = client.get(f"/api/v1/scheduled-expenses/{se_b['id']}", headers=h)
        assert resp_b.json()["applied_months"] == 1

        # =================================================================
        # PASO 4: Aplicar cuota 2 de B ($1K)
        # Total expenses = $3K
        # =================================================================
        api_apply_scheduled_expense(client, h, se_b["id"])

        resp_b2 = client.get(f"/api/v1/scheduled-expenses/{se_b['id']}", headers=h)
        assert resp_b2.json()["applied_months"] == 2

        assert_pnl(client, h, operating_expenses=3_000)

        # =================================================================
        # PASO 5: Cancelar scheduled expense B
        # Cuotas previas (2) quedan aplicadas, no se aplican más
        # =================================================================
        resp_cancel = client.post(f"/api/v1/scheduled-expenses/{se_b['id']}/cancel", headers=h)
        assert resp_cancel.status_code == 200
        assert resp_cancel.json()["status"] == "cancelled"

        # P&L sin cambio (cuotas aplicadas quedan)
        assert_pnl(client, h, operating_expenses=3_000)

        # =================================================================
        # PASO 6: Generar utilidad — compra $5K + venta $20K = profit $15K
        # =================================================================
        api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["material"].id, "quantity": 100, "unit_price": 50, "warehouse_id": s["warehouse"].id}],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["account"].id,
        )
        api_create_sale(client, h,
            customer_id=s["customer"].id, warehouse_id=s["warehouse"].id,
            lines=[{"material_id": s["material"].id, "quantity": 100, "unit_price": 200}],
            auto_liquidate=True, immediate_collection=True, collection_account_id=s["account"].id,
        )

        # P&L: revenue $20K, COGS $5K, expenses $3K, net = $12K
        assert_pnl(client, h,
            sales_revenue=20_000, cost_of_goods_sold=5_000,
            operating_expenses=3_000, net_profit=12_000)

        # =================================================================
        # PASO 7: Profit distribution a 2 socios ($5K + $2K = $7K)
        # NO afecta P&L ni Cash Flow — solo Balance Sheet
        # =================================================================
        pnl_before = client.get("/api/v1/reports/profit-and-loss",
            params={"date_from": DATE_FROM, "date_to": DATE_TO}, headers=h).json()
        cf_before = client.get("/api/v1/reports/cash-flow",
            params={"date_from": DATE_FROM, "date_to": DATE_TO}, headers=h).json()

        api_create_profit_distribution(client, h, {
            "date": f"{TODAY}T12:00:00",
            "lines": [
                {"third_party_id": str(s["investor_1"].id), "amount": 5_000},
                {"third_party_id": str(s["investor_2"].id), "amount": 2_000},
            ],
        })

        # P&L sin cambio
        pnl_after = client.get("/api/v1/reports/profit-and-loss",
            params={"date_from": DATE_FROM, "date_to": DATE_TO}, headers=h).json()
        assert pnl_after["net_profit"] == pytest.approx(pnl_before["net_profit"], abs=1), \
            "Profit distribution should NOT affect P&L"

        # Cash Flow sin cambio
        cf_after = client.get("/api/v1/reports/cash-flow",
            params={"date_from": DATE_FROM, "date_to": DATE_TO}, headers=h).json()
        assert cf_after["closing_balance"] == pytest.approx(cf_before["closing_balance"], abs=1), \
            "Profit distribution should NOT affect Cash Flow"

        # Saldos socios
        # Socio 1: -$700K(capital) - $5K(distribucion) = -$705K
        assert_tp_balance(client, h, str(s["investor_1"].id), -705_000)
        # Socio 2: -$300K(capital) - $2K(distribucion) = -$302K
        assert_tp_balance(client, h, str(s["investor_2"].id), -302_000)

        # =================================================================
        # PASO 8: Capital return $10K al socio 1
        # =================================================================
        api_money_movement(client, h, "capital-return", {
            "investor_id": s["investor_1"].id, "amount": 10_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Retiro parcial",
        })
        # Socio 1: -$705K + $10K = -$695K
        assert_tp_balance(client, h, str(s["investor_1"].id), -695_000)

        # =================================================================
        # PASO 9: Balance Sheet — todo cuadra
        # =================================================================
        assert_balance_sheet(client, h,
            accumulated_profit=12_000,
            distributed_profit=7_000,
            equity=5_000,  # 12K - 7K
        )

        # prepaid_expenses > 0 (deferred A tiene 11 cuotas pendientes + B cancelado con saldo)
        bs = client.get("/api/v1/reports/balance-sheet", headers=h).json()
        assert bs["assets"]["prepaid_expenses"] > 0, \
            f"Expected prepaid_expenses > 0, got {bs['assets']['prepaid_expenses']}"

        # =================================================================
        # PASO 10: Aplicar cuotas restantes de B (cancelado) → 400
        # =================================================================
        resp_apply_cancelled = client.post(
            f"/api/v1/scheduled-expenses/{se_b['id']}/apply", headers=h)
        assert resp_apply_cancelled.status_code == 400, \
            f"Expected 400 for cancelled expense, got {resp_apply_cancelled.status_code}"

        # =================================================================
        # ACID TEST
        # =================================================================
        assert_pnl_equals_balance(client, h)
