"""
Escenario 2: Ventas — Stress Test Completo.

Cubre:
- Registrar → liquidar → cancelar (happy path)
- Auto-liquidate + cobro inmediato
- Liquidar sin cobro (solo CxC)
- Cobro separado via MoneyMovement
- Multi-linea (2 materiales)
- Comisiones: percentage, fixed, per_kg + commission_accrual
- received_quantity (diferencia de bascula)
- Edicion de venta registrada (revert-and-reapply)
- Cancelar venta registrada (no liquidada)
- Venta con stock negativo (warning, no bloquea)
- Validaciones 400/422
- Stock cargado via compras reales (no hack al modelo)
"""
import pytest
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    TODAY, DATE_FROM, DATE_TO,
    create_material_category, create_business_unit, create_material,
    create_warehouse, create_account, create_expense_category,
    api_create_purchase, api_create_sale, api_liquidate_sale, api_cancel_sale,
    api_money_movement,
    assert_material, assert_tp_balance, assert_account_balance, assert_pnl,
    assert_pnl_equals_balance,
)


@pytest.fixture
def scenario(db_session, test_organization):
    org_id = test_organization.id
    cat = create_material_category(db_session, org_id, "Metales INT02")
    bu_cu = create_business_unit(db_session, org_id, "Cobre INT02")
    bu_ch = create_business_unit(db_session, org_id, "Chatarra INT02")
    mat_cobre = create_material(db_session, org_id, "INT02-CU", "Cobre Limpio", cat.id, bu_cu.id)
    mat_chatarra = create_material(db_session, org_id, "INT02-CH", "Chatarra Acero", cat.id, bu_ch.id)
    warehouse = create_warehouse(db_session, org_id, "Bodega INT02")
    account = create_account(db_session, org_id, "Cuenta INT02", balance=0)

    investor = create_third_party_with_category(db_session, org_id, "Socio INT02", "investor")
    supplier = create_third_party_with_category(db_session, org_id, "Proveedor INT02", "material_supplier")
    customer = create_third_party_with_category(db_session, org_id, "Fundicion ABC", "customer")
    customer_2 = create_third_party_with_category(db_session, org_id, "Exportadora XY", "customer")
    comisionista = create_third_party_with_category(db_session, org_id, "Comisionista INT02", "service_provider")

    db_session.commit()
    return {
        "mat_cobre": mat_cobre, "mat_chatarra": mat_chatarra,
        "warehouse": warehouse, "account": account,
        "investor": investor, "supplier": supplier,
        "customer": customer, "customer_2": customer_2,
        "comisionista": comisionista,
    }


class TestSaleStress:

    def test_sale_full_stress(self, client, org_headers, scenario):
        s = scenario
        h = org_headers
        wid = s["warehouse"].id
        aid = str(s["account"].id)
        cu_id = str(s["mat_cobre"].id)
        ch_id = str(s["mat_chatarra"].id)
        cust_id = str(s["customer"].id)

        # =================================================================
        # SETUP: Capital + compras para tener stock real
        # =================================================================
        api_money_movement(client, h, "capital-injection", {
            "investor_id": s["investor"].id, "amount": 5_000_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Capital",
        })

        # Cobre: 500kg × $200 = $100K
        api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["mat_cobre"].id, "quantity": 500, "unit_price": 200, "warehouse_id": wid}],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["account"].id,
        )
        # Chatarra: 1000kg × $50 = $50K
        api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["mat_chatarra"].id, "quantity": 1000, "unit_price": 50, "warehouse_id": wid}],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["account"].id,
        )

        assert_material(client, h, cu_id, total=500, liquidated=500, avg_cost=200)
        assert_material(client, h, ch_id, total=1000, liquidated=1000, avg_cost=50)
        assert_account_balance(client, h, aid, 4_850_000)

        # =================================================================
        # PASO 1: Registrar venta (sin liquidar)
        # Cobre 200kg × $350 = $70K
        # =================================================================
        venta_1 = api_create_sale(client, h,
            customer_id=s["customer"].id, warehouse_id=wid,
            lines=[{"material_id": s["mat_cobre"].id, "quantity": 200, "unit_price": 350}],
        )
        assert venta_1["status"] == "registered"
        assert venta_1["total_amount"] == 70_000.0

        # Stock baja al registrar (no al liquidar)
        assert_material(client, h, cu_id, total=300, liquidated=300, avg_cost=200)
        # COGS capturado al crear
        assert venta_1["lines"][0]["unit_cost"] == pytest.approx(200, abs=0.01)
        # Sin efecto financiero
        assert_tp_balance(client, h, cust_id, 0)

        # =================================================================
        # PASO 2: Liquidar SIN cobro (solo CxC)
        # =================================================================
        api_liquidate_sale(client, h, venta_1["id"])

        # Stock sin cambio (ya bajo al registrar)
        assert_material(client, h, cu_id, total=300, liquidated=300, avg_cost=200)
        # Cliente: +$70K (nos debe)
        assert_tp_balance(client, h, cust_id, 70_000)
        # Cuenta: sin cambio
        assert_account_balance(client, h, aid, 4_850_000)

        # =================================================================
        # PASO 3: Cobro separado via MoneyMovement
        # =================================================================
        api_money_movement(client, h, "customer-collection", {
            "customer_id": s["customer"].id, "amount": 70_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Cobro venta 1",
        })
        assert_tp_balance(client, h, cust_id, 0)
        assert_account_balance(client, h, aid, 4_920_000)

        # P&L: revenue $70K, COGS 200×$200 = $40K, gross = $30K
        assert_pnl(client, h, sales_revenue=70_000, cost_of_goods_sold=40_000, net_profit=30_000)

        # =================================================================
        # PASO 4: Cancelar venta liquidada
        # =================================================================
        cancelled = api_cancel_sale(client, h, venta_1["id"])
        assert cancelled["status"] == "cancelled"

        # Stock restaurado
        assert_material(client, h, cu_id, total=500, liquidated=500, avg_cost=200)
        # Cliente: liquidacion revertida, cobro NO revertido → -$70K (le debemos)
        assert_tp_balance(client, h, cust_id, -70_000)
        # P&L limpio
        assert_pnl(client, h, sales_revenue=0, cost_of_goods_sold=0, net_profit=0)

        # =================================================================
        # PASO 5: Auto-liquidate + cobro inmediato
        # Cobre 100kg × $400 = $40K
        # =================================================================
        venta_2 = api_create_sale(client, h,
            customer_id=s["customer"].id, warehouse_id=wid,
            lines=[{"material_id": s["mat_cobre"].id, "quantity": 100, "unit_price": 400}],
            auto_liquidate=True, immediate_collection=True, collection_account_id=s["account"].id,
        )
        assert venta_2["status"] == "liquidated"
        assert_material(client, h, cu_id, total=400, liquidated=400, avg_cost=200)
        # Cliente: -$70K + $40K(liq) - $40K(cobro) = -$70K
        assert_tp_balance(client, h, cust_id, -70_000)
        assert_account_balance(client, h, aid, 4_960_000)

        # =================================================================
        # PASO 6: Multi-linea (2 materiales)
        # Cobre 50kg × $380 = $19K + Chatarra 300kg × $80 = $24K = $43K
        # =================================================================
        venta_3 = api_create_sale(client, h,
            customer_id=s["customer_2"].id, warehouse_id=wid,
            lines=[
                {"material_id": s["mat_cobre"].id, "quantity": 50, "unit_price": 380},
                {"material_id": s["mat_chatarra"].id, "quantity": 300, "unit_price": 80},
            ],
            auto_liquidate=True, immediate_collection=True, collection_account_id=s["account"].id,
        )
        assert venta_3["status"] == "liquidated"
        assert venta_3["total_amount"] == pytest.approx(43_000, abs=1)
        assert_material(client, h, cu_id, total=350, liquidated=350, avg_cost=200)
        assert_material(client, h, ch_id, total=700, liquidated=700, avg_cost=50)
        assert_tp_balance(client, h, str(s["customer_2"].id), 0)

        # =================================================================
        # PASO 7: Comision percentage (3% = $1,200 sobre $40K)
        # Cobre 50kg × $500 = $25K. Comision = 3% = $750
        # =================================================================
        venta_comm_pct = api_create_sale(client, h,
            customer_id=s["customer"].id, warehouse_id=wid,
            lines=[{"material_id": s["mat_cobre"].id, "quantity": 50, "unit_price": 500}],
            auto_liquidate=True, immediate_collection=True, collection_account_id=s["account"].id,
            commissions=[{
                "third_party_id": str(s["comisionista"].id),
                "commission_type": "percentage", "commission_value": 3,
                "concept": "Comision 3%",
            }],
        )
        assert venta_comm_pct["status"] == "liquidated"
        # Comisionista: -$750 (comision causada via commission_accrual)
        assert_tp_balance(client, h, str(s["comisionista"].id), -750)

        # =================================================================
        # PASO 8: Comision fixed ($1K)
        # Chatarra 200kg × $90 = $18K
        # =================================================================
        venta_comm_fixed = api_create_sale(client, h,
            customer_id=s["customer"].id, warehouse_id=wid,
            lines=[{"material_id": s["mat_chatarra"].id, "quantity": 200, "unit_price": 90}],
            auto_liquidate=True, immediate_collection=True, collection_account_id=s["account"].id,
            commissions=[{
                "third_party_id": str(s["comisionista"].id),
                "commission_type": "fixed", "commission_value": 1_000,
                "concept": "Comision fija",
            }],
        )
        # Comisionista: -$750 - $1,000 = -$1,750
        assert_tp_balance(client, h, str(s["comisionista"].id), -1_750)

        # =================================================================
        # PASO 9: Comision per_kg ($2/kg)
        # Chatarra 100kg × $85 = $8,500. Comision = $2 × 100 = $200
        # =================================================================
        venta_comm_perkg = api_create_sale(client, h,
            customer_id=s["customer"].id, warehouse_id=wid,
            lines=[{"material_id": s["mat_chatarra"].id, "quantity": 100, "unit_price": 85}],
            auto_liquidate=True, immediate_collection=True, collection_account_id=s["account"].id,
            commissions=[{
                "third_party_id": str(s["comisionista"].id),
                "commission_type": "per_kg", "commission_value": 2,
                "concept": "Comision per kg",
            }],
        )
        # Comisionista: -$1,750 - $200 = -$1,950
        assert_tp_balance(client, h, str(s["comisionista"].id), -1_950)

        # =================================================================
        # PASO 10: received_quantity (diferencia de bascula)
        # Chatarra 100kg × $100 = $10K registrado
        # Al liquidar, cliente recibio 95kg → total_price = 95 × $100 = $9,500
        # COGS sigue siendo 100 × $50 = $5,000 (no cambia)
        # =================================================================
        venta_recv = api_create_sale(client, h,
            customer_id=s["customer_2"].id, warehouse_id=wid,
            lines=[{"material_id": s["mat_chatarra"].id, "quantity": 100, "unit_price": 100}],
        )
        assert venta_recv["status"] == "registered"
        # Chatarra: 1000 - 300(p6) - 200(p8) - 100(p9) - 100(p10) = 300
        assert_material(client, h, ch_id, total=300, liquidated=300, avg_cost=50)

        # Liquidar con received_quantity (unit_price requerido en line_updates)
        liq_payload = {
            "lines": [{"line_id": venta_recv["lines"][0]["id"], "unit_price": 100, "received_quantity": 95}],
            "immediate_collection": True,
            "collection_account_id": str(s["account"].id),
        }
        resp_liq = client.patch(f"/api/v1/sales/{venta_recv['id']}/liquidate", json=liq_payload, headers=h)
        assert resp_liq.status_code == 200, f"Liquidate with received_qty failed: {resp_liq.json()}"
        liq_data = resp_liq.json()
        assert liq_data["status"] == "liquidated"
        # total_amount debe reflejar received_quantity
        assert liq_data["total_amount"] == pytest.approx(9_500, abs=1)
        # La linea debe tener received_quantity
        line = liq_data["lines"][0]
        assert line["received_quantity"] == pytest.approx(95, abs=0.01)
        # COGS no cambia (usa quantity original, no received)
        assert line["unit_cost"] == pytest.approx(50, abs=0.01)

        # =================================================================
        # PASO 11: Edicion de venta registrada (revert-and-reapply)
        # =================================================================
        venta_edit = api_create_sale(client, h,
            customer_id=s["customer"].id, warehouse_id=wid,
            lines=[{"material_id": s["mat_cobre"].id, "quantity": 30, "unit_price": 450}],
        )
        assert venta_edit["status"] == "registered"
        # Stock bajo: Cobre 300 - 30 = 270
        assert_material(client, h, cu_id, total=270, liquidated=270, avg_cost=200)

        # Editar: cambiar a 20kg × $500
        resp_edit = client.patch(f"/api/v1/sales/{venta_edit['id']}", json={
            "lines": [{"material_id": str(s["mat_cobre"].id), "quantity": 20, "unit_price": 500}],
        }, headers=h)
        assert resp_edit.status_code == 200
        edited = resp_edit.json()
        assert edited["total_amount"] == pytest.approx(10_000, abs=1)

        # Stock: revirtio 30, desconto 20 → Cobre 300 - 20 = 280
        assert_material(client, h, cu_id, total=280, liquidated=280, avg_cost=200)

        # Liquidar la editada
        api_liquidate_sale(client, h, venta_edit["id"],
            immediate_collection=True, collection_account_id=s["account"].id,
        )
        assert_material(client, h, cu_id, total=280, liquidated=280, avg_cost=200)

        # =================================================================
        # PASO 12: Cancelar venta REGISTRADA (no liquidada)
        # =================================================================
        venta_reg = api_create_sale(client, h,
            customer_id=s["customer"].id, warehouse_id=wid,
            lines=[{"material_id": s["mat_cobre"].id, "quantity": 10, "unit_price": 300}],
        )
        assert venta_reg["status"] == "registered"
        assert_material(client, h, cu_id, total=270, liquidated=270, avg_cost=200)

        cancelled_reg = api_cancel_sale(client, h, venta_reg["id"])
        assert cancelled_reg["status"] == "cancelled"
        # Stock restaurado, avg sin cambio
        assert_material(client, h, cu_id, total=280, liquidated=280, avg_cost=200)
        # Cliente: sin efecto (registrada no afecta saldo)

        # =================================================================
        # PASO 13: Venta con stock negativo (warning, no bloquea)
        # Cobre tiene 280kg, vendemos 300kg → stock = -20
        # =================================================================
        resp_neg = client.post("/api/v1/sales", json={
            "customer_id": str(s["customer"].id),
            "warehouse_id": str(wid),
            "date": f"{TODAY}T12:00:00",
            "lines": [{"material_id": str(s["mat_cobre"].id), "quantity": 300, "unit_price": 400}],
            "auto_liquidate": True,
            "immediate_collection": True,
            "collection_account_id": str(s["account"].id),
        }, headers=h)
        assert resp_neg.status_code == 201, f"Negative stock sale failed: {resp_neg.json()}"
        neg_data = resp_neg.json()
        # Debe tener warnings
        assert len(neg_data.get("warnings", [])) > 0, "Expected warnings for negative stock"
        # Stock negativo
        assert_material(client, h, cu_id, total=-20, liquidated=-20, avg_cost=200)

        # =================================================================
        # PASO 14: Validaciones 400/422
        # =================================================================

        # 14a: Customer que no es customer (usar supplier)
        resp_bad_cust = client.post("/api/v1/sales", json={
            "customer_id": str(s["supplier"].id),
            "warehouse_id": str(wid),
            "date": f"{TODAY}T12:00:00",
            "lines": [{"material_id": str(s["mat_chatarra"].id), "quantity": 10, "unit_price": 80}],
        }, headers=h)
        assert resp_bad_cust.status_code == 400, f"Expected 400, got {resp_bad_cust.status_code}"

        # 14b: immediate_collection sin auto_liquidate → 422
        resp_bad_coll = client.post("/api/v1/sales", json={
            "customer_id": str(s["customer"].id),
            "warehouse_id": str(wid),
            "date": f"{TODAY}T12:00:00",
            "lines": [{"material_id": str(s["mat_chatarra"].id), "quantity": 10, "unit_price": 80}],
            "immediate_collection": True,
            "collection_account_id": str(s["account"].id),
        }, headers=h)
        assert resp_bad_coll.status_code == 422, f"Expected 422, got {resp_bad_coll.status_code}"

        # 14c: auto_liquidate con precio 0 → 422
        resp_bad_price = client.post("/api/v1/sales", json={
            "customer_id": str(s["customer"].id),
            "warehouse_id": str(wid),
            "date": f"{TODAY}T12:00:00",
            "lines": [{"material_id": str(s["mat_chatarra"].id), "quantity": 10, "unit_price": 0}],
            "auto_liquidate": True,
        }, headers=h)
        assert resp_bad_price.status_code == 422, f"Expected 422, got {resp_bad_price.status_code}"

        # 14d: Fecha futura → 400
        resp_bad_date = client.post("/api/v1/sales", json={
            "customer_id": str(s["customer"].id),
            "warehouse_id": str(wid),
            "date": "2099-12-31T12:00:00",
            "lines": [{"material_id": str(s["mat_chatarra"].id), "quantity": 10, "unit_price": 80}],
        }, headers=h)
        assert resp_bad_date.status_code == 400, f"Expected 400 for future date, got {resp_bad_date.status_code}"

        # 14e: Cancelar venta ya cancelada → 400
        resp_double_cancel = client.patch(f"/api/v1/sales/{venta_1['id']}/cancel", headers=h)
        assert resp_double_cancel.status_code == 400

        # =================================================================
        # ACID TEST
        # =================================================================
        assert_pnl_equals_balance(client, h)
