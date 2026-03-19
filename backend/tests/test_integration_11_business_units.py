"""
Escenario 11: Rentabilidad por Unidad de Negocio — Stress Test.

Cubre:
- Pesos desiguales (70/30) para verificar prorrateo real
- 3 UNs con gasto compartido a solo 2 de 3
- Tipos de gasto variados (expense, expense_accrual, provision_expense, deferred_expense)
- Cancelacion de venta y su efecto en rentabilidad
- Doble Partida con profit asignado a UN del material
- Comision de compra per_kg prorrateada al COGS
- net_profit individual verificado por UN
- Reporte de costo real por material (overhead rate)
- Sum(UNs) == P&L global (estricto, con delta explicado)
"""
import pytest
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    TODAY, DATE_FROM, DATE_TO,
    create_material_category, create_business_unit, create_material,
    create_warehouse, create_account, create_expense_category,
    api_create_purchase, api_create_sale, api_cancel_sale,
    api_create_double_entry, api_money_movement,
    api_create_scheduled_expense, api_apply_scheduled_expense,
    assert_pnl, assert_pnl_equals_balance,
)


@pytest.fixture
def scenario(db_session, test_organization):
    org_id = test_organization.id

    # 3 UNs con pesos desiguales
    bu_chatarra = create_business_unit(db_session, org_id, "Chatarra INT11")
    bu_nf = create_business_unit(db_session, org_id, "No Ferrosos INT11")
    bu_elec = create_business_unit(db_session, org_id, "Electronicos INT11")

    cat = create_material_category(db_session, org_id, "Metales INT11")
    mat_chatarra = create_material(db_session, org_id, "INT11-CH", "Chatarra", cat.id, bu_chatarra.id)
    mat_cobre = create_material(db_session, org_id, "INT11-CU", "Cobre", cat.id, bu_nf.id)
    mat_motor = create_material(db_session, org_id, "INT11-MO", "Motor", cat.id, bu_elec.id)

    warehouse = create_warehouse(db_session, org_id, "Bodega INT11")
    account = create_account(db_session, org_id, "Cuenta INT11", balance=0)

    cat_flete = create_expense_category(db_session, org_id, "Flete INT11", is_direct=True)
    cat_mantenimiento = create_expense_category(db_session, org_id, "Mantenimiento INT11", is_direct=False)
    cat_arriendo = create_expense_category(db_session, org_id, "Arriendo INT11", is_direct=False)

    investor = create_third_party_with_category(db_session, org_id, "Socio INT11", "investor")
    supplier = create_third_party_with_category(db_session, org_id, "Proveedor INT11", "material_supplier")
    supplier_dp = create_third_party_with_category(db_session, org_id, "Proveedor DP INT11", "material_supplier")
    customer = create_third_party_with_category(db_session, org_id, "Cliente INT11", "customer")
    customer_dp = create_third_party_with_category(db_session, org_id, "Cliente DP INT11", "customer")
    comisionista = create_third_party_with_category(db_session, org_id, "Comisionista INT11", "service_provider")
    liability_tp = create_third_party_with_category(db_session, org_id, "Pasivo INT11", "liability")
    provision_tp = create_third_party_with_category(db_session, org_id, "Provision INT11", "provision")

    db_session.commit()
    return {
        "bu_chatarra": bu_chatarra, "bu_nf": bu_nf, "bu_elec": bu_elec,
        "mat_chatarra": mat_chatarra, "mat_cobre": mat_cobre, "mat_motor": mat_motor,
        "warehouse": warehouse, "account": account,
        "cat_flete": cat_flete, "cat_mantenimiento": cat_mantenimiento, "cat_arriendo": cat_arriendo,
        "investor": investor, "supplier": supplier, "supplier_dp": supplier_dp,
        "customer": customer, "customer_dp": customer_dp, "comisionista": comisionista,
        "liability_tp": liability_tp, "provision_tp": provision_tp,
    }


class TestProfitabilityByBU:

    def test_bu_profitability_stress(self, client, org_headers, scenario):
        s = scenario
        h = org_headers
        wid = s["warehouse"].id

        # =================================================================
        # FASE 1: Compras con pesos desiguales (70/20/10)
        # =================================================================

        # Capital $5M
        api_money_movement(client, h, "capital-injection", {
            "investor_id": s["investor"].id, "amount": 5_000_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Capital",
        })

        # Chatarra: 1000kg × $70 = $70K (70% del total de compras)
        api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["mat_chatarra"].id, "quantity": 1000, "unit_price": 70, "warehouse_id": wid}],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["account"].id,
        )

        # Cobre: 100kg × $200 = $20K (20% del total) — con comision per_kg $10
        # commission = 10 × 100 = $1,000
        # adjusted_unit_cost = 200 + 1000/100 = $210
        payload_cobre = {
            "supplier_id": str(s["supplier"].id),
            "date": f"{TODAY}T12:00:00",
            "lines": [{"material_id": str(s["mat_cobre"].id), "quantity": 100, "unit_price": 200, "warehouse_id": str(wid)}],
            "commissions": [{
                "third_party_id": str(s["comisionista"].id),
                "commission_type": "per_kg",
                "commission_value": 10,
                "concept": "Comision compra cobre",
            }],
            "auto_liquidate": True,
            "immediate_payment": True,
            "payment_account_id": str(s["account"].id),
        }
        resp = client.post("/api/v1/purchases", json=payload_cobre, headers=h)
        assert resp.status_code == 201

        # Motor: 50kg × $200 = $10K (10% del total)
        api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["mat_motor"].id, "quantity": 50, "unit_price": 200, "warehouse_id": wid}],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["account"].id,
        )

        # Total compras: $70K + $20K + $10K = $100K
        # Pesos: Chatarra=70%, No Ferrosos=20%, Electronicos=10%

        # =================================================================
        # FASE 2: Gastos variados
        # =================================================================

        # Gasto directo: Flete $7K → Chatarra
        api_money_movement(client, h, "expense", {
            "amount": 7_000, "expense_category_id": s["cat_flete"].id,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Flete chatarra", "business_unit_id": s["bu_chatarra"].id,
        })

        # Gasto compartido: Mantenimiento $10K → [Chatarra, No Ferrosos] (excluye Electronicos)
        # Prorrateo por compras dentro del grupo: CH=$70K, NF=$20K → CH=77.78%, NF=22.22%
        # CH = $10K × 70/(70+20) = $7,777.78, NF = $10K × 20/(70+20) = $2,222.22
        api_money_movement(client, h, "expense", {
            "amount": 10_000, "expense_category_id": s["cat_mantenimiento"].id,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Mantenimiento compartido CH+NF",
            "applicable_business_unit_ids": [str(s["bu_chatarra"].id), str(s["bu_nf"].id)],
        })

        # Gasto general: Arriendo $15K (sin UN → prorrateado a las 3 UNs por peso)
        # CH = $15K × 70% = $10,500, NF = $15K × 20% = $3,000, EL = $15K × 10% = $1,500
        api_money_movement(client, h, "expense", {
            "amount": 15_000, "expense_category_id": s["cat_arriendo"].id,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Arriendo oficina",
        })

        # Expense accrual (causar gasto sin mover dinero): $3K → Chatarra
        api_money_movement(client, h, "expense-accrual", {
            "third_party_id": s["liability_tp"].id, "amount": 3_000,
            "expense_category_id": s["cat_mantenimiento"].id,
            "date": f"{TODAY}T12:00:00", "description": "Mantenimiento causado",
            "business_unit_id": s["bu_chatarra"].id,
        })

        # Provision expense: $2K → No Ferrosos
        api_money_movement(client, h, "provision-deposit", {
            "provision_id": s["provision_tp"].id, "amount": 10_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Fondeo provision",
        })
        api_money_movement(client, h, "provision-expense", {
            "provision_id": s["provision_tp"].id, "amount": 2_000,
            "expense_category_id": s["cat_flete"].id,
            "date": f"{TODAY}T12:00:00", "description": "Gasto provision NF",
            "business_unit_id": s["bu_nf"].id,
        })

        # Gasto diferido: $6K / 6 meses, aplicar 1 cuota ($1K) → Electronicos
        scheduled = api_create_scheduled_expense(client, h, {
            "name": "Seguro equipos", "total_amount": 6_000, "total_months": 6,
            "source_account_id": s["account"].id,
            "expense_category_id": s["cat_arriendo"].id,
            "start_date": "2026-03-01", "apply_day": 15,
            "business_unit_id": s["bu_elec"].id,
        })
        api_apply_scheduled_expense(client, h, scheduled["id"])
        # deferred_expense $1K → Electronicos directo

        # =================================================================
        # FASE 3: Ventas + DP + cancelaciones
        # =================================================================

        # Venta Chatarra: 500kg × $120 = $60K (COGS = 500 × $70 = $35K)
        api_create_sale(client, h,
            customer_id=s["customer"].id, warehouse_id=wid,
            lines=[{"material_id": s["mat_chatarra"].id, "quantity": 500, "unit_price": 120}],
            auto_liquidate=True, immediate_collection=True, collection_account_id=s["account"].id,
        )

        # Venta Cobre: 50kg × $400 = $20K (COGS = 50 × $210 = $10,500)
        # Comision 5% = $1,000
        api_create_sale(client, h,
            customer_id=s["customer"].id, warehouse_id=wid,
            lines=[{"material_id": s["mat_cobre"].id, "quantity": 50, "unit_price": 400}],
            auto_liquidate=True, immediate_collection=True, collection_account_id=s["account"].id,
            commissions=[{
                "third_party_id": str(s["comisionista"].id),
                "commission_type": "percentage", "commission_value": 5,
                "concept": "Comision venta cobre",
            }],
        )

        # Venta Motor: 20kg × $350 = $7K (COGS = 20 × $200 = $4K) — LUEGO CANCELAR
        venta_motor = api_create_sale(client, h,
            customer_id=s["customer"].id, warehouse_id=wid,
            lines=[{"material_id": s["mat_motor"].id, "quantity": 20, "unit_price": 350}],
            auto_liquidate=True, immediate_collection=True, collection_account_id=s["account"].id,
        )

        # Cancelar venta motor — no debe aparecer en rentabilidad
        api_cancel_sale(client, h, venta_motor["id"])

        # DP: Chatarra 200kg, compra@$80, venta@$110 → profit = 200 × ($110-$80) = $6K
        api_create_double_entry(client, h,
            supplier_id=s["supplier_dp"].id, customer_id=s["customer_dp"].id,
            lines=[{
                "material_id": s["mat_chatarra"].id, "quantity": 200,
                "purchase_unit_price": 80, "sale_unit_price": 110,
            }],
            auto_liquidate=True, date=TODAY,
        )

        # =================================================================
        # VERIFICACIONES
        # =================================================================

        # --- P&L Global ---
        # Revenue: $60K(CH) + $20K(CU) = $80K (motor cancelada)
        # COGS: $35K(CH) + $10.5K(CU) = $45,500
        # DP profit: $6K
        # Gross: $80K - $45.5K + $6K = $40,500
        # Expenses: $7K(flete) + $10K(mant compartido) + $15K(arriendo)
        #           + $3K(accrual) + $2K(provision) + $1K(diferido) = $38K
        # Comisiones venta: $1K
        # Comision compra per_kg: NO aparece en P&L como gasto,
        #   se prorratea al costo (COGS ya lo incluye)
        # Net: $40,500 - $38K - $1K = $1,500

        pnl_resp = client.get("/api/v1/reports/profit-and-loss",
            params={"date_from": DATE_FROM, "date_to": DATE_TO}, headers=h)
        assert pnl_resp.status_code == 200
        pnl = pnl_resp.json()
        assert pnl["sales_revenue"] == pytest.approx(80_000, abs=1)
        assert pnl["cost_of_goods_sold"] == pytest.approx(45_500, abs=1)
        assert pnl["double_entry_profit"] == pytest.approx(6_000, abs=1)
        assert pnl["operating_expenses"] == pytest.approx(38_000, abs=1)
        assert pnl["commissions_paid"] == pytest.approx(1_000, abs=1)
        pnl_net = pnl["net_profit"]
        assert pnl_net == pytest.approx(1_500, abs=1)

        # --- Rentabilidad por UN ---
        bu_resp = client.get(
            "/api/v1/reports/profitability-by-business-unit",
            params={"date_from": DATE_FROM, "date_to": DATE_TO},
            headers=h,
        )
        assert bu_resp.status_code == 200
        bus = {bu["business_unit_name"]: bu for bu in bu_resp.json()["business_units"]}

        assert "Chatarra INT11" in bus, f"UNs: {list(bus.keys())}"
        assert "No Ferrosos INT11" in bus, f"UNs: {list(bus.keys())}"
        assert "Electronicos INT11" in bus, f"UNs: {list(bus.keys())}"

        ch = bus["Chatarra INT11"]
        nf = bus["No Ferrosos INT11"]
        el = bus["Electronicos INT11"]

        # --- Chatarra (70% peso) ---
        assert ch["purchases_total"] == pytest.approx(70_000, abs=1)
        assert ch["purchases_weight_pct"] == pytest.approx(70, abs=1)
        assert ch["sales_revenue"] == pytest.approx(60_000, abs=1)
        assert ch["sales_cogs"] == pytest.approx(35_000, abs=1)
        assert ch["de_profit"] == pytest.approx(6_000, abs=1)
        # direct: $7K(flete) + $3K(accrual) = $10K
        assert ch["direct_expenses"] == pytest.approx(10_000, abs=1)
        # shared: $10K × 70/(70+20) = $7,777.78
        assert ch["shared_expenses"] == pytest.approx(7_777.78, abs=1)
        # general: $15K × 70% = $10,500
        assert ch["general_expenses"] == pytest.approx(10_500, abs=1)
        assert ch["sale_commissions"] == pytest.approx(0, abs=1)
        # net: (60K - 35K + 6K) - (10K + 7777.78 + 10500 + 0) = 31K - 28277.78 = 2,722.22
        assert ch["net_profit"] == pytest.approx(2_722.22, abs=1)

        # --- No Ferrosos (20% peso) ---
        assert nf["purchases_total"] == pytest.approx(20_000, abs=1)
        assert nf["purchases_weight_pct"] == pytest.approx(20, abs=1)
        assert nf["sales_revenue"] == pytest.approx(20_000, abs=1)
        assert nf["sales_cogs"] == pytest.approx(10_500, abs=1)  # 50 × $210 (incluye comision compra)
        assert nf["de_profit"] == pytest.approx(0, abs=1)
        # direct: $2K(provision expense)
        assert nf["direct_expenses"] == pytest.approx(2_000, abs=1)
        # shared: $10K × 20/(70+20) = $2,222.22
        assert nf["shared_expenses"] == pytest.approx(2_222.22, abs=1)
        # general: $15K × 20% = $3,000
        assert nf["general_expenses"] == pytest.approx(3_000, abs=1)
        # comision venta: $1K
        assert nf["sale_commissions"] == pytest.approx(1_000, abs=1)
        # net: (20K - 10.5K) - (2K + 2222.22 + 3K + 1K) = 9.5K - 8222.22 = 1,277.78
        assert nf["net_profit"] == pytest.approx(1_277.78, abs=1)

        # --- Electronicos (10% peso) ---
        assert el["purchases_total"] == pytest.approx(10_000, abs=1)
        assert el["purchases_weight_pct"] == pytest.approx(10, abs=1)
        assert el["sales_revenue"] == pytest.approx(0, abs=1)  # venta cancelada
        assert el["sales_cogs"] == pytest.approx(0, abs=1)
        assert el["de_profit"] == pytest.approx(0, abs=1)
        # direct: $1K(deferred expense)
        assert el["direct_expenses"] == pytest.approx(1_000, abs=1)
        # shared: $0 (no incluido en el compartido)
        assert el["shared_expenses"] == pytest.approx(0, abs=1)
        # general: $15K × 10% = $1,500
        assert el["general_expenses"] == pytest.approx(1_500, abs=1)
        assert el["sale_commissions"] == pytest.approx(0, abs=1)
        # net: (0 - 0) - (1K + 0 + 1.5K) = -2,500
        assert el["net_profit"] == pytest.approx(-2_500, abs=1)

        # --- Sum(UNs) == P&L ---
        total_un = ch["net_profit"] + nf["net_profit"] + el["net_profit"]
        assert total_un == pytest.approx(pnl_net, abs=1), \
            f"Sum UNs ({total_un}) != P&L ({pnl_net})"

        # =================================================================
        # REPORTE DE COSTO REAL POR MATERIAL
        # =================================================================
        rc_resp = client.get(
            "/api/v1/reports/real-cost-by-material",
            params={"date_from": DATE_FROM, "date_to": DATE_TO},
            headers=h,
        )
        assert rc_resp.status_code == 200
        rc_bus = {bu["business_unit_name"]: bu for bu in rc_resp.json()["business_units"]}

        assert "Chatarra INT11" in rc_bus
        assert "No Ferrosos INT11" in rc_bus
        assert "Electronicos INT11" in rc_bus

        rc_ch = rc_bus["Chatarra INT11"]
        rc_nf = rc_bus["No Ferrosos INT11"]
        rc_el = rc_bus["Electronicos INT11"]

        # Chatarra: gastos totales = $10K(directo) + $7,777.78(compartido) + $10,500(general) = $28,277.78
        # kg comprados = 1000. overhead_rate = 28277.78 / 1000 = $28.28/kg
        # material avg_cost = $70. real_cost = 70 + 28.28 = $98.28
        assert rc_ch["kg_purchased"] == pytest.approx(1_000, abs=1)
        assert rc_ch["total_expenses"] == pytest.approx(28_277.78, abs=1)
        assert rc_ch["overhead_rate"] == pytest.approx(28.28, abs=0.01)
        ch_mat = {m["material_code"]: m for m in rc_ch["materials"]}
        assert "INT11-CH" in ch_mat
        assert ch_mat["INT11-CH"]["average_cost"] == pytest.approx(70, abs=0.01)
        assert ch_mat["INT11-CH"]["real_cost"] == pytest.approx(98.28, abs=0.01)

        # No Ferrosos: gastos = $2K + $2,222.22 + $3K = $7,222.22
        # kg = 100. overhead = 72.22/kg
        # material avg_cost = $210 (incluye comision). real_cost = 210 + 72.22 = $282.22
        assert rc_nf["kg_purchased"] == pytest.approx(100, abs=1)
        assert rc_nf["total_expenses"] == pytest.approx(7_222.22, abs=1)
        assert rc_nf["overhead_rate"] == pytest.approx(72.22, abs=0.01)
        nf_mat = {m["material_code"]: m for m in rc_nf["materials"]}
        assert "INT11-CU" in nf_mat
        assert nf_mat["INT11-CU"]["average_cost"] == pytest.approx(210, abs=0.01)
        assert nf_mat["INT11-CU"]["real_cost"] == pytest.approx(282.22, abs=0.01)

        # Electronicos: gastos = $1K + $0 + $1,500 = $2,500
        # kg = 50. overhead = 50/kg
        # material avg_cost = $200. real_cost = 200 + 50 = $250
        assert rc_el["kg_purchased"] == pytest.approx(50, abs=1)
        assert rc_el["total_expenses"] == pytest.approx(2_500, abs=1)
        assert rc_el["overhead_rate"] == pytest.approx(50, abs=0.01)
        el_mat = {m["material_code"]: m for m in rc_el["materials"]}
        assert "INT11-MO" in el_mat
        assert el_mat["INT11-MO"]["average_cost"] == pytest.approx(200, abs=0.01)
        assert el_mat["INT11-MO"]["real_cost"] == pytest.approx(250, abs=0.01)

        # =================================================================
        # ACID TEST
        # =================================================================
        assert_pnl_equals_balance(client, h)
