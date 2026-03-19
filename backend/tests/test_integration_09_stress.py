"""
Escenario 9: Multi-Operación Stress Test — 12 operaciones → ACID TEST FINAL.
"""
import pytest
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    TODAY, DATE_FROM, DATE_TO,
    create_material_category, create_business_unit, create_material,
    create_warehouse, create_account, create_expense_category,
    api_create_purchase, api_create_sale, api_create_double_entry,
    api_money_movement, api_create_adjustment,
    assert_material, assert_tp_balance, assert_account_balance,
    assert_pnl, assert_balance_sheet, assert_cash_flow, assert_pnl_equals_balance,
)


@pytest.fixture
def scenario(db_session, test_organization):
    org_id = test_organization.id
    cat = create_material_category(db_session, org_id, "Metales INT09")
    bu_nf = create_business_unit(db_session, org_id, "No Ferrosos INT09")
    bu_ch = create_business_unit(db_session, org_id, "Chatarra INT09")
    bu_el = create_business_unit(db_session, org_id, "Electronicos INT09")

    mat_cobre = create_material(db_session, org_id, "INT09-CU", "Cobre", cat.id, bu_nf.id)
    mat_hierro = create_material(db_session, org_id, "INT09-FE", "Hierro", cat.id, bu_ch.id)
    warehouse = create_warehouse(db_session, org_id, "Bodega INT09")
    account_1 = create_account(db_session, org_id, "Cuenta1 INT09", balance=0)
    account_2 = create_account(db_session, org_id, "Cuenta2 INT09", balance=0)
    cat_direct = create_expense_category(db_session, org_id, "Flete INT09", is_direct=True)
    cat_indirect = create_expense_category(db_session, org_id, "Servicios INT09", is_direct=False)

    investor = create_third_party_with_category(db_session, org_id, "Socio INT09", "investor")
    supplier = create_third_party_with_category(db_session, org_id, "Proveedor INT09", "material_supplier")
    supplier_dp = create_third_party_with_category(db_session, org_id, "Proveedor DP INT09", "material_supplier")
    customer = create_third_party_with_category(db_session, org_id, "Cliente INT09", "customer")
    comisionista = create_third_party_with_category(db_session, org_id, "Comisionista INT09", "service_provider")
    liability = create_third_party_with_category(db_session, org_id, "Pasivo INT09", "liability")
    provision = create_third_party_with_category(db_session, org_id, "Provision INT09", "provision")
    db_session.commit()
    return {
        "mat_cobre": mat_cobre, "mat_hierro": mat_hierro,
        "warehouse": warehouse, "account_1": account_1, "account_2": account_2,
        "cat_direct": cat_direct, "cat_indirect": cat_indirect,
        "investor": investor, "supplier": supplier, "supplier_dp": supplier_dp,
        "customer": customer, "comisionista": comisionista,
        "liability": liability, "provision": provision,
    }


class TestStressTest:

    def test_12_operations_acid_test(self, client, org_headers, scenario):
        s = scenario
        h = org_headers
        wid = s["warehouse"].id

        # 1. Capital injection $2M → account_1
        api_money_movement(client, h, "capital-injection", {
            "investor_id": s["investor"].id, "amount": 2_000_000,
            "account_id": s["account_1"].id, "date": f"{TODAY}T12:00:00",
            "description": "Capital",
        })

        # 2. Transfer $500K a1 → a2
        api_money_movement(client, h, "transfer", {
            "amount": 500_000, "source_account_id": s["account_1"].id,
            "destination_account_id": s["account_2"].id,
            "date": f"{TODAY}T12:00:00", "description": "Transfer",
        })

        # 3. Compra COBRE 1000 kg × $100 = $100K (auto-liq+pago a1)
        api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["mat_cobre"].id, "quantity": 1000, "unit_price": 100, "warehouse_id": wid}],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["account_1"].id,
        )

        # 4. Compra HIERRO 2000 kg × $50 = $100K (auto-liq+pago a1)
        api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["mat_hierro"].id, "quantity": 2000, "unit_price": 50, "warehouse_id": wid}],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["account_1"].id,
        )

        # 5. Venta COBRE 500 kg × $150 = $75K (auto-liq+cobro a2)
        api_create_sale(client, h,
            customer_id=s["customer"].id, warehouse_id=wid,
            lines=[{"material_id": s["mat_cobre"].id, "quantity": 500, "unit_price": 150}],
            auto_liquidate=True, immediate_collection=True, collection_account_id=s["account_2"].id,
        )

        # 6. Venta HIERRO 1000 kg × $80 = $80K (auto-liq+cobro a1)
        api_create_sale(client, h,
            customer_id=s["customer"].id, warehouse_id=wid,
            lines=[{"material_id": s["mat_hierro"].id, "quantity": 1000, "unit_price": 80}],
            auto_liquidate=True, immediate_collection=True, collection_account_id=s["account_1"].id,
        )

        # 7. DP: COBRE 200kg, compra@$120, venta@$140 (comisión fija $1K)
        api_create_double_entry(client, h,
            supplier_id=s["supplier_dp"].id, customer_id=s["customer"].id,
            lines=[{"material_id": s["mat_cobre"].id, "quantity": 200, "purchase_unit_price": 120, "sale_unit_price": 140}],
            commissions=[{
                "third_party_id": str(s["comisionista"].id),
                "concept": "Comisión DP",
                "commission_type": "fixed",
                "commission_value": 1000,
            }],
            auto_liquidate=True,
        )

        # 8. Expense $5K indirecto (a1)
        api_money_movement(client, h, "expense", {
            "amount": 5_000, "expense_category_id": s["cat_indirect"].id,
            "account_id": s["account_1"].id, "date": f"{TODAY}T12:00:00",
            "description": "Servicios generales",
        })

        # 9. Expense accrual $3K (liability)
        api_money_movement(client, h, "expense-accrual", {
            "third_party_id": s["liability"].id, "amount": 3_000,
            "expense_category_id": s["cat_indirect"].id,
            "date": f"{TODAY}T12:00:00", "description": "Gasto causado",
        })

        # 10. Increase adjustment COBRE +50 kg @ $110
        api_create_adjustment(client, h,
            adjustment_type="increase", material_id=s["mat_cobre"].id,
            warehouse_id=wid, quantity=50, unit_cost=110,
        )

        # 11. Decrease adjustment HIERRO -100 kg
        api_create_adjustment(client, h,
            adjustment_type="decrease", material_id=s["mat_hierro"].id,
            warehouse_id=wid, quantity=100,
        )

        # 12. Provision deposit $10K (a2)
        api_money_movement(client, h, "provision-deposit", {
            "provision_id": s["provision"].id, "amount": 10_000,
            "account_id": s["account_2"].id,
            "date": f"{TODAY}T12:00:00", "description": "Fondeo provisión",
        })

        # =================================================================
        # VERIFICACIÓN FINAL
        # =================================================================

        # Cuentas
        # a1: 2M - 500K(transfer) - 100K(cobre) - 100K(hierro) + 80K(vta hierro) - 5K(expense) = $1,375K
        # a2: 0 + 500K(transfer) + 75K(vta cobre) - 10K(provision) = $565K
        assert_account_balance(client, h, str(s["account_1"].id), 1_375_000)
        assert_account_balance(client, h, str(s["account_2"].id), 565_000)

        # Materiales
        # COBRE: 1000 - 500(venta) + 50(increase) = 550 kg
        # avg_cost: (500×100 + 50×110) / 550 = 55500/550 ≈ $100.91
        assert_material(client, h, str(s["mat_cobre"].id),
                        total=550, liquidated=550, avg_cost=pytest.approx(100.91, abs=0.01))
        # HIERRO: 2000 - 1000(venta) - 100(decrease) = 900 kg @ $50
        assert_material(client, h, str(s["mat_hierro"].id),
                        total=900, liquidated=900, avg_cost=50)

        # Saldos terceros
        assert_tp_balance(client, h, str(s["investor"].id), -2_000_000)
        assert_tp_balance(client, h, str(s["supplier"].id), 0)  # compras pagadas
        # Customer: ventas cobradas (0) + DP liquidada (+$28K, 200×$140) = $28K
        assert_tp_balance(client, h, str(s["customer"].id), 28_000)
        assert_tp_balance(client, h, str(s["supplier_dp"].id), -24_000)  # DP supplier: -200×$120
        assert_tp_balance(client, h, str(s["comisionista"].id), -1_000)
        assert_tp_balance(client, h, str(s["liability"].id), -3_000)
        assert_tp_balance(client, h, str(s["provision"].id), -10_000)

        # P&L
        # Revenue: $75K + $80K = $155K
        # COGS: 500×$100 + 1000×$50 = $100K
        # Gross profit sales: $55K
        # DP profit: 200×($140-$120) = $4K
        # Adjustment net: 50×$110 - 100×$50 = $5,500 - $5,000 = $500
        # Expenses: $5K + $3K = $8K
        # Commissions: $1K
        # Net: $55K + $4K + $500 - $8K - $1K = $50,500
        assert_pnl(client, h,
                   sales_revenue=155_000,
                   cost_of_goods_sold=100_000,
                   gross_profit_sales=55_000,
                   double_entry_profit=4_000,
                   adjustment_net=500,
                   operating_expenses=8_000,
                   commissions_paid=1_000,
                   net_profit=50_500)

        # Cash Flow
        # Inflows: capital $2M + venta cobre $75K + venta hierro $80K = $2,155K
        # Outflows: compra cobre $100K + compra hierro $100K + expense $5K + provision $10K = $215K
        # Transfer is internal (no net flow)
        # Closing: $1,375K + $565K = $1,940K
        assert_cash_flow(client, h,
                         closing_balance=1_940_000)

        # ACID TEST
        assert_pnl_equals_balance(client, h)
