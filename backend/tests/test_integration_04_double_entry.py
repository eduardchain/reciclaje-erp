"""
Escenario 4: Doble Partida — Stress Test Completo.

Cubre:
- Registrar → sin efectos financieros ni inventario
- Liquidar → saldos terceros + P&L (profit + comision)
- Cancelar liquidada → todo revierte
- Auto-liquidate (1 paso)
- Multi-linea (2 materiales con margenes distintos)
- 3 tipos comision: fixed, percentage, per_kg
- Multiples comisionistas en 1 DP
- Edicion de DP registrada (cambiar precios/cantidad)
- Liquidar con ajuste de precios
- Cancelar DP registrada (trivial, sin reversiones)
- Stock NO se mueve nunca (verificacion explicita)
- Validaciones (same supplier/customer, bad behavior_type, doble cancel)
- P&L == Balance Sheet acid test
"""
import pytest
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    TODAY, DATE_FROM, DATE_TO,
    create_material_category, create_business_unit, create_material,
    create_warehouse, create_account,
    api_create_purchase,
    api_create_double_entry, api_liquidate_double_entry, api_cancel_double_entry,
    api_money_movement,
    assert_material, assert_tp_balance, assert_pnl, assert_pnl_equals_balance,
)


@pytest.fixture
def scenario(db_session, test_organization):
    org_id = test_organization.id
    cat = create_material_category(db_session, org_id, "Metales INT04")
    bu_ch = create_business_unit(db_session, org_id, "Chatarra INT04")
    bu_cu = create_business_unit(db_session, org_id, "Cobre INT04")
    mat_chatarra = create_material(db_session, org_id, "INT04-CH", "Chatarra DP", cat.id, bu_ch.id)
    mat_cobre = create_material(db_session, org_id, "INT04-CU", "Cobre DP", cat.id, bu_cu.id)
    warehouse = create_warehouse(db_session, org_id, "Bodega INT04")
    account = create_account(db_session, org_id, "Cuenta INT04", balance=0)

    investor = create_third_party_with_category(db_session, org_id, "Socio INT04", "investor")
    supplier = create_third_party_with_category(db_session, org_id, "Proveedor DP", "material_supplier")
    supplier_2 = create_third_party_with_category(db_session, org_id, "Proveedor DP 2", "material_supplier")
    customer = create_third_party_with_category(db_session, org_id, "Cliente DP", "customer")
    customer_2 = create_third_party_with_category(db_session, org_id, "Cliente DP 2", "customer")
    comisionista_1 = create_third_party_with_category(db_session, org_id, "Comisionista DP 1", "service_provider")
    comisionista_2 = create_third_party_with_category(db_session, org_id, "Comisionista DP 2", "service_provider")

    db_session.commit()
    return {
        "mat_chatarra": mat_chatarra, "mat_cobre": mat_cobre,
        "warehouse": warehouse, "account": account,
        "investor": investor,
        "supplier": supplier, "supplier_2": supplier_2,
        "customer": customer, "customer_2": customer_2,
        "comisionista_1": comisionista_1, "comisionista_2": comisionista_2,
    }


class TestDoubleEntryStress:

    def test_dp_full_stress(self, client, org_headers, scenario):
        s = scenario
        h = org_headers
        wid = s["warehouse"].id
        sup_id = str(s["supplier"].id)
        cust_id = str(s["customer"].id)
        com1_id = str(s["comisionista_1"].id)
        com2_id = str(s["comisionista_2"].id)
        ch_id = str(s["mat_chatarra"].id)
        cu_id = str(s["mat_cobre"].id)

        # Setup: capital + compra para tener stock y verificar que DP no lo toca
        api_money_movement(client, h, "capital-injection", {
            "investor_id": s["investor"].id, "amount": 1_000_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Capital",
        })
        api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[
                {"material_id": s["mat_chatarra"].id, "quantity": 500, "unit_price": 50, "warehouse_id": wid},
                {"material_id": s["mat_cobre"].id, "quantity": 100, "unit_price": 300, "warehouse_id": wid},
            ],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["account"].id,
        )
        # Guardar stock inicial para verificar que DP no lo toca
        assert_material(client, h, ch_id, total=500, liquidated=500, avg_cost=50)
        assert_material(client, h, cu_id, total=100, liquidated=100, avg_cost=300)

        # =================================================================
        # PASO 1: Registrar DP — sin efectos financieros ni inventario
        # Chatarra 200kg, compra@$60, venta@$80 → profit $4K
        # =================================================================
        dp_1 = api_create_double_entry(client, h,
            supplier_id=s["supplier_2"].id, customer_id=s["customer"].id,
            lines=[{
                "material_id": s["mat_chatarra"].id, "quantity": 200,
                "purchase_unit_price": 60, "sale_unit_price": 80,
            }],
            commissions=[{
                "third_party_id": com1_id,
                "commission_type": "fixed", "commission_value": 1_000,
                "concept": "Comision fija",
            }],
        )
        assert dp_1["status"] == "registered"

        # Sin efectos
        assert_tp_balance(client, h, str(s["supplier_2"].id), 0)
        assert_tp_balance(client, h, cust_id, 0)
        assert_tp_balance(client, h, com1_id, 0)
        # Stock NO cambia
        assert_material(client, h, ch_id, total=500, liquidated=500, avg_cost=50)

        # =================================================================
        # PASO 2: Liquidar DP
        # =================================================================
        liq = api_liquidate_double_entry(client, h, dp_1["id"])
        assert liq["status"] == "liquidated"

        # Proveedor 2: -$12K (200 × $60)
        assert_tp_balance(client, h, str(s["supplier_2"].id), -12_000)
        # Cliente: +$16K (200 × $80)
        assert_tp_balance(client, h, cust_id, 16_000)
        # Comisionista: -$1K
        assert_tp_balance(client, h, com1_id, -1_000)
        # Stock sigue igual
        assert_material(client, h, ch_id, total=500, liquidated=500, avg_cost=50)

        assert_pnl(client, h, double_entry_profit=4_000, commissions_paid=1_000)

        # =================================================================
        # PASO 3: Cancelar DP liquidada
        # =================================================================
        api_cancel_double_entry(client, h, dp_1["id"])

        # Todo a cero
        assert_tp_balance(client, h, str(s["supplier_2"].id), 0)
        assert_tp_balance(client, h, cust_id, 0)
        assert_tp_balance(client, h, com1_id, 0)
        assert_pnl(client, h, double_entry_profit=0, commissions_paid=0, net_profit=0)
        # Stock sigue igual
        assert_material(client, h, ch_id, total=500, liquidated=500, avg_cost=50)

        # =================================================================
        # PASO 4: Auto-liquidate
        # Chatarra 300kg, compra@$70, venta@$100 → profit = 300 × $30 = $9K
        # =================================================================
        dp_2 = api_create_double_entry(client, h,
            supplier_id=s["supplier"].id, customer_id=s["customer"].id,
            lines=[{
                "material_id": s["mat_chatarra"].id, "quantity": 300,
                "purchase_unit_price": 70, "sale_unit_price": 100,
            }],
            auto_liquidate=True, date=TODAY,
        )
        assert dp_2["status"] == "liquidated"
        assert_tp_balance(client, h, sup_id, -21_000)  # 300 × $70
        assert_tp_balance(client, h, cust_id, 30_000)   # 300 × $100
        assert_pnl(client, h, double_entry_profit=9_000)
        # Stock sigue igual
        assert_material(client, h, ch_id, total=500, liquidated=500, avg_cost=50)

        # =================================================================
        # PASO 5: Multi-linea (2 materiales con margenes distintos)
        # Chatarra 100kg: compra@$50, venta@$90 → profit $4K
        # Cobre 50kg: compra@$250, venta@$400 → profit $7.5K
        # Total profit: $11.5K
        # Comision 2% sobre total venta = 2% × ($9K + $20K) = $580
        # =================================================================
        dp_3 = api_create_double_entry(client, h,
            supplier_id=s["supplier_2"].id, customer_id=s["customer_2"].id,
            lines=[
                {"material_id": s["mat_chatarra"].id, "quantity": 100, "purchase_unit_price": 50, "sale_unit_price": 90},
                {"material_id": s["mat_cobre"].id, "quantity": 50, "purchase_unit_price": 250, "sale_unit_price": 400},
            ],
            commissions=[{
                "third_party_id": com1_id,
                "commission_type": "percentage", "commission_value": 2,
                "concept": "Comision 2%",
            }],
            auto_liquidate=True, date=TODAY,
        )
        assert dp_3["status"] == "liquidated"

        # Proveedor 2: -(100×50 + 50×250) = -$17.5K
        assert_tp_balance(client, h, str(s["supplier_2"].id), -17_500)
        # Cliente 2: +(100×90 + 50×400) = +$29K
        assert_tp_balance(client, h, str(s["customer_2"].id), 29_000)
        # Comision: 2% × $29K = $580
        assert_tp_balance(client, h, com1_id, -580)

        # P&L acumulado: $9K(dp2) + $11.5K(dp3) = $20.5K
        assert_pnl(client, h, double_entry_profit=20_500)

        # Stock sin cambio
        assert_material(client, h, ch_id, total=500, liquidated=500, avg_cost=50)
        assert_material(client, h, cu_id, total=100, liquidated=100, avg_cost=300)

        # =================================================================
        # PASO 6: Multiples comisionistas + per_kg
        # Chatarra 400kg, compra@$55, venta@$85 → profit $12K
        # Comisionista 1: $3/kg = $1,200
        # Comisionista 2: fija $500
        # =================================================================
        dp_4 = api_create_double_entry(client, h,
            supplier_id=s["supplier"].id, customer_id=s["customer_2"].id,
            lines=[{
                "material_id": s["mat_chatarra"].id, "quantity": 400,
                "purchase_unit_price": 55, "sale_unit_price": 85,
            }],
            commissions=[
                {"third_party_id": com1_id, "commission_type": "per_kg", "commission_value": 3, "concept": "Per kg"},
                {"third_party_id": com2_id, "commission_type": "fixed", "commission_value": 500, "concept": "Fija"},
            ],
            auto_liquidate=True, date=TODAY,
        )
        assert dp_4["status"] == "liquidated"

        # Comisionista 1: -$580 - $1,200 = -$1,780
        assert_tp_balance(client, h, com1_id, -1_780)
        # Comisionista 2: -$500
        assert_tp_balance(client, h, com2_id, -500)

        # =================================================================
        # PASO 7: Edicion de DP registrada
        # =================================================================
        dp_edit = api_create_double_entry(client, h,
            supplier_id=s["supplier"].id, customer_id=s["customer"].id,
            lines=[{
                "material_id": s["mat_chatarra"].id, "quantity": 100,
                "purchase_unit_price": 40, "sale_unit_price": 70,
            }],
        )
        assert dp_edit["status"] == "registered"

        # Editar: cambiar precios y cantidad
        resp_edit = client.patch(f"/api/v1/double-entries/{dp_edit['id']}", json={
            "lines": [{
                "material_id": str(s["mat_chatarra"].id), "quantity": 150,
                "purchase_unit_price": 45, "sale_unit_price": 75,
            }],
        }, headers=h)
        assert resp_edit.status_code == 200
        edited = resp_edit.json()
        # total_purchase_cost = 150 × 45 = $6,750, total_sale_amount = 150 × 75 = $11,250
        assert edited["total_purchase_cost"] == pytest.approx(6_750, abs=1)
        assert edited["total_sale_amount"] == pytest.approx(11_250, abs=1)

        # Liquidar la editada
        api_liquidate_double_entry(client, h, dp_edit["id"])

        # =================================================================
        # PASO 8: Liquidar con ajuste de precios
        # =================================================================
        dp_price_adj = api_create_double_entry(client, h,
            supplier_id=s["supplier_2"].id, customer_id=s["customer"].id,
            lines=[{
                "material_id": s["mat_cobre"].id, "quantity": 30,
                "purchase_unit_price": 200, "sale_unit_price": 350,
            }],
        )
        assert dp_price_adj["status"] == "registered"

        # Liquidar con precios ajustados
        liq_payload = {
            "lines": [{
                "line_id": dp_price_adj["lines"][0]["id"],
                "purchase_unit_price": 220,
                "sale_unit_price": 380,
            }],
        }
        resp_liq = client.patch(f"/api/v1/double-entries/{dp_price_adj['id']}/liquidate",
            json=liq_payload, headers=h)
        assert resp_liq.status_code == 200
        liq_data = resp_liq.json()
        assert liq_data["status"] == "liquidated"
        # profit = 30 × (380 - 220) = $4,800
        assert liq_data["total_purchase_cost"] == pytest.approx(6_600, abs=1)  # 30 × 220
        assert liq_data["total_sale_amount"] == pytest.approx(11_400, abs=1)   # 30 × 380

        # =================================================================
        # PASO 9: Cancelar DP REGISTRADA (trivial, sin reversiones)
        # =================================================================
        dp_cancel_reg = api_create_double_entry(client, h,
            supplier_id=s["supplier"].id, customer_id=s["customer"].id,
            lines=[{
                "material_id": s["mat_chatarra"].id, "quantity": 50,
                "purchase_unit_price": 60, "sale_unit_price": 90,
            }],
        )
        assert dp_cancel_reg["status"] == "registered"

        # Guardar saldos antes
        sup_before = client.get(f"/api/v1/third-parties/{sup_id}", headers=h).json()["current_balance"]
        cust_before = client.get(f"/api/v1/third-parties/{cust_id}", headers=h).json()["current_balance"]

        api_cancel_double_entry(client, h, dp_cancel_reg["id"])

        # Saldos no cambian (registrada no afecto nada)
        assert_tp_balance(client, h, sup_id, sup_before)
        assert_tp_balance(client, h, cust_id, cust_before)

        # =================================================================
        # PASO 10: Validaciones
        # =================================================================

        # 10a: Mismo proveedor y cliente → 400
        resp_same = client.post("/api/v1/double-entries", json={
            "supplier_id": str(s["supplier"].id),
            "customer_id": str(s["supplier"].id),  # same!
            "date": f"{TODAY}T12:00:00",
            "lines": [{"material_id": str(s["mat_chatarra"].id), "quantity": 10,
                        "purchase_unit_price": 50, "sale_unit_price": 80}],
        }, headers=h)
        assert resp_same.status_code in (400, 422), f"Expected 400/422 for same supplier/customer, got {resp_same.status_code}"

        # 10b: Supplier que no es material_supplier (usar customer)
        resp_bad_sup = client.post("/api/v1/double-entries", json={
            "supplier_id": str(s["customer"].id),
            "customer_id": str(s["customer_2"].id),
            "date": f"{TODAY}T12:00:00",
            "lines": [{"material_id": str(s["mat_chatarra"].id), "quantity": 10,
                        "purchase_unit_price": 50, "sale_unit_price": 80}],
        }, headers=h)
        assert resp_bad_sup.status_code in (400, 422), f"Expected 400/422 for bad supplier, got {resp_bad_sup.status_code}"

        # 10c: Customer que no es customer (usar supplier)
        resp_bad_cust = client.post("/api/v1/double-entries", json={
            "supplier_id": str(s["supplier"].id),
            "customer_id": str(s["supplier_2"].id),
            "date": f"{TODAY}T12:00:00",
            "lines": [{"material_id": str(s["mat_chatarra"].id), "quantity": 10,
                        "purchase_unit_price": 50, "sale_unit_price": 80}],
        }, headers=h)
        assert resp_bad_cust.status_code in (400, 422), f"Expected 400/422 for bad customer, got {resp_bad_cust.status_code}"

        # 10d: Cancelar ya cancelada → 400
        resp_double = client.patch(f"/api/v1/double-entries/{dp_cancel_reg['id']}/cancel", headers=h)
        assert resp_double.status_code == 400

        # =================================================================
        # ACID TEST — Stock sin cambio + P&L == Balance Sheet
        # =================================================================
        assert_material(client, h, ch_id, total=500, liquidated=500, avg_cost=50)
        assert_material(client, h, cu_id, total=100, liquidated=100, avg_cost=300)
        assert_pnl_equals_balance(client, h)
