"""
Escenario 1: Compras — Stress Test Completo.

Cubre:
- Registrar → liquidar → cancelar (happy path)
- Auto-liquidate + pago inmediato
- Multi-linea (2 materiales, 2 bodegas)
- Liquidar sin pago (solo CxP)
- Comisiones: per_kg, percentage, fixed
- Edicion de compra registrada (revert-and-reapply)
- Cancelar compra registrada (no liquidada)
- Validaciones 422/400
"""
import pytest
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    TODAY, DATE_FROM, DATE_TO,
    create_material_category, create_business_unit, create_material,
    create_warehouse, create_account, create_expense_category,
    api_create_purchase, api_liquidate_purchase, api_cancel_purchase,
    api_money_movement,
    assert_material, assert_tp_balance, assert_account_balance,
    assert_pnl_equals_balance,
)


@pytest.fixture
def scenario(db_session, test_organization):
    org_id = test_organization.id
    cat = create_material_category(db_session, org_id, "Metales INT01")
    bu_ch = create_business_unit(db_session, org_id, "Chatarra INT01")
    bu_cu = create_business_unit(db_session, org_id, "Cobre INT01")
    mat_chatarra = create_material(db_session, org_id, "INT01-FE", "Chatarra Acero", cat.id, bu_ch.id)
    mat_cobre = create_material(db_session, org_id, "INT01-CU", "Cobre Limpio", cat.id, bu_cu.id)
    wh_principal = create_warehouse(db_session, org_id, "Bodega Principal INT01")
    wh_secundaria = create_warehouse(db_session, org_id, "Bodega Secundaria INT01")
    account = create_account(db_session, org_id, "Bancolombia INT01", balance=0)
    cat_gasto = create_expense_category(db_session, org_id, "Gastos INT01")

    investor = create_third_party_with_category(db_session, org_id, "Socio INT01", "investor")
    supplier = create_third_party_with_category(db_session, org_id, "Proveedor Principal", "material_supplier")
    supplier_2 = create_third_party_with_category(db_session, org_id, "Proveedor Secundario", "material_supplier")
    comisionista = create_third_party_with_category(db_session, org_id, "Comisionista INT01", "service_provider")
    customer = create_third_party_with_category(db_session, org_id, "Cliente INT01", "customer")

    db_session.commit()
    return {
        "mat_chatarra": mat_chatarra, "mat_cobre": mat_cobre,
        "wh_principal": wh_principal, "wh_secundaria": wh_secundaria,
        "account": account, "cat_gasto": cat_gasto,
        "investor": investor, "supplier": supplier, "supplier_2": supplier_2,
        "comisionista": comisionista, "customer": customer,
    }


class TestPurchaseStress:

    def test_purchase_full_stress(self, client, org_headers, scenario):
        s = scenario
        h = org_headers
        wp = s["wh_principal"].id
        ws = s["wh_secundaria"].id
        aid = str(s["account"].id)
        ch_id = str(s["mat_chatarra"].id)
        cu_id = str(s["mat_cobre"].id)
        sup_id = str(s["supplier"].id)

        # Capital $2M
        api_money_movement(client, h, "capital-injection", {
            "investor_id": s["investor"].id, "amount": 2_000_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Capital",
        })

        # =================================================================
        # PASO 1: Registrar compra (sin liquidar)
        # 100kg CHATARRA × $50 = $5,000
        # =================================================================
        compra_1 = api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["mat_chatarra"].id, "quantity": 100, "unit_price": 50, "warehouse_id": wp}],
        )
        assert compra_1["status"] == "registered"
        assert compra_1["total_amount"] == 5_000.0

        # Stock en tránsito, sin efecto financiero
        assert_material(client, h, ch_id, total=100, transit=100, liquidated=0, avg_cost=0)
        assert_tp_balance(client, h, sup_id, 0)
        assert_account_balance(client, h, aid, 2_000_000)

        # =================================================================
        # PASO 2: Liquidar SIN pago (solo CxP)
        # =================================================================
        api_liquidate_purchase(client, h, compra_1["id"])

        # Stock: transito → liquidado, avg = $50
        assert_material(client, h, ch_id, total=100, transit=0, liquidated=100, avg_cost=50)
        # Proveedor: -$5K (le debemos)
        assert_tp_balance(client, h, sup_id, -5_000)
        # Cuenta: sin cambio (no pagamos)
        assert_account_balance(client, h, aid, 2_000_000)

        # =================================================================
        # PASO 3: Pago separado via MoneyMovement
        # =================================================================
        api_money_movement(client, h, "supplier-payment", {
            "supplier_id": s["supplier"].id, "amount": 5_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Pago compra 1",
        })
        assert_tp_balance(client, h, sup_id, 0)
        assert_account_balance(client, h, aid, 1_995_000)

        # =================================================================
        # PASO 4: Cancelar compra liquidada
        # =================================================================
        cancelled = api_cancel_purchase(client, h, compra_1["id"])
        assert cancelled["status"] == "cancelled"

        # Stock revertido, avg revertido
        assert_material(client, h, ch_id, total=0, transit=0, liquidated=0, avg_cost=0)
        # Proveedor: liquidación revertida (+$5K), pago NO revertido → +$5K (nos debe)
        assert_tp_balance(client, h, sup_id, 5_000)
        # Cuenta: sin cambio (pago es MM separado)
        assert_account_balance(client, h, aid, 1_995_000)

        # =================================================================
        # PASO 5: Auto-liquidate + pago inmediato
        # 200kg CHATARRA × $60 = $12,000
        # =================================================================
        compra_2 = api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["mat_chatarra"].id, "quantity": 200, "unit_price": 60, "warehouse_id": wp}],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["account"].id,
        )
        assert compra_2["status"] == "liquidated"

        # Stock directo a liquidado (0 transito), avg = $60
        assert_material(client, h, ch_id, total=200, transit=0, liquidated=200, avg_cost=60)
        # Proveedor: previo +$5K, liq -$12K, pago +$12K = +$5K
        assert_tp_balance(client, h, sup_id, 5_000)
        # Cuenta: -$12K
        assert_account_balance(client, h, aid, 1_983_000)

        # =================================================================
        # PASO 6: Multi-linea, 2 materiales, 2 bodegas
        # CHATARRA 300kg × $70 (Bodega Principal) + COBRE 50kg × $200 (Bodega Secundaria)
        # Total = $21,000 + $10,000 = $31,000
        # =================================================================
        compra_3 = api_create_purchase(client, h,
            supplier_id=s["supplier_2"].id,
            lines=[
                {"material_id": s["mat_chatarra"].id, "quantity": 300, "unit_price": 70, "warehouse_id": wp},
                {"material_id": s["mat_cobre"].id, "quantity": 50, "unit_price": 200, "warehouse_id": ws},
            ],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["account"].id,
        )
        assert compra_3["status"] == "liquidated"
        assert compra_3["total_amount"] == pytest.approx(31_000, abs=1)

        # CHATARRA: (200×60 + 300×70) / 500 = (12000+21000)/500 = $66
        assert_material(client, h, ch_id, total=500, transit=0, liquidated=500, avg_cost=66)
        # COBRE: primera compra, avg = $200
        assert_material(client, h, cu_id, total=50, transit=0, liquidated=50, avg_cost=200)
        assert_tp_balance(client, h, str(s["supplier_2"].id), 0)
        assert_account_balance(client, h, aid, 1_952_000)

        # =================================================================
        # PASO 7: Comision percentage (2%)
        # COBRE 100kg × $300 = $30,000. Comision = 2% = $600
        # adjusted = 300 + 600/100 = $306
        # COBRE avg: (50×200 + 100×306) / 150 = (10000+30600)/150 = $270.67
        # =================================================================
        payload_comm_pct = {
            "supplier_id": str(s["supplier"].id),
            "date": f"{TODAY}T12:00:00",
            "lines": [{"material_id": str(s["mat_cobre"].id), "quantity": 100, "unit_price": 300, "warehouse_id": str(wp)}],
            "commissions": [{
                "third_party_id": str(s["comisionista"].id),
                "commission_type": "percentage", "commission_value": 2,
                "concept": "Comision 2%",
            }],
            "auto_liquidate": True, "immediate_payment": True,
            "payment_account_id": str(s["account"].id),
        }
        resp = client.post("/api/v1/purchases", json=payload_comm_pct, headers=h)
        assert resp.status_code == 201
        assert_material(client, h, cu_id, total=150, liquidated=150, avg_cost=pytest.approx(270.67, abs=0.01))
        # Comisionista: -$600 (le debemos)
        assert_tp_balance(client, h, str(s["comisionista"].id), -600)

        # =================================================================
        # PASO 8: Comision fixed ($500)
        # CHATARRA 100kg × $80 = $8,000. Comision fija = $500
        # adjusted = 80 + 500/100 = $85
        # CHATARRA avg: (500×66 + 100×85) / 600 = (33000+8500)/600 = $69.17
        # =================================================================
        payload_comm_fixed = {
            "supplier_id": str(s["supplier"].id),
            "date": f"{TODAY}T12:00:00",
            "lines": [{"material_id": str(s["mat_chatarra"].id), "quantity": 100, "unit_price": 80, "warehouse_id": str(wp)}],
            "commissions": [{
                "third_party_id": str(s["comisionista"].id),
                "commission_type": "fixed", "commission_value": 500,
                "concept": "Comision fija",
            }],
            "auto_liquidate": True, "immediate_payment": True,
            "payment_account_id": str(s["account"].id),
        }
        resp = client.post("/api/v1/purchases", json=payload_comm_fixed, headers=h)
        assert resp.status_code == 201
        assert_material(client, h, ch_id, total=600, liquidated=600, avg_cost=pytest.approx(69.17, abs=0.01))
        # Comisionista: -$600 - $500 = -$1,100
        assert_tp_balance(client, h, str(s["comisionista"].id), -1_100)

        # =================================================================
        # PASO 9: Comision per_kg ($5/kg)
        # COBRE 200kg × $250 = $50,000. Comision = $5 × 200 = $1,000
        # adjusted = 250 + 1000/200 = $255
        # COBRE avg: (150×270.67 + 200×255) / 350 = (40600 + 51000)/350 = $261.71
        # =================================================================
        payload_comm_perkg = {
            "supplier_id": str(s["supplier"].id),
            "date": f"{TODAY}T12:00:00",
            "lines": [{"material_id": str(s["mat_cobre"].id), "quantity": 200, "unit_price": 250, "warehouse_id": str(wp)}],
            "commissions": [{
                "third_party_id": str(s["comisionista"].id),
                "commission_type": "per_kg", "commission_value": 5,
                "concept": "Comision per kg",
            }],
            "auto_liquidate": True, "immediate_payment": True,
            "payment_account_id": str(s["account"].id),
        }
        resp = client.post("/api/v1/purchases", json=payload_comm_perkg, headers=h)
        assert resp.status_code == 201
        assert_material(client, h, cu_id, total=350, liquidated=350, avg_cost=pytest.approx(261.71, abs=0.01))
        # Comisionista: -$1,100 - $1,000 = -$2,100
        assert_tp_balance(client, h, str(s["comisionista"].id), -2_100)

        # =================================================================
        # PASO 10: Edicion de compra registrada
        # Registrar, luego editar cantidad y precio
        # =================================================================
        compra_edit = api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["mat_chatarra"].id, "quantity": 50, "unit_price": 100, "warehouse_id": wp}],
        )
        assert compra_edit["status"] == "registered"
        # Stock: +50 en transito (avg no cambia por transito)
        assert_material(client, h, ch_id, total=650, transit=50, liquidated=600, avg_cost=pytest.approx(69.17, abs=0.01))

        # Editar: cambiar a 80kg × $90
        edit_payload = {
            "lines": [{"material_id": str(s["mat_chatarra"].id), "quantity": 80, "unit_price": 90, "warehouse_id": str(wp)}],
        }
        resp_edit = client.patch(f"/api/v1/purchases/{compra_edit['id']}", json=edit_payload, headers=h)
        assert resp_edit.status_code == 200
        edited = resp_edit.json()
        assert edited["total_amount"] == pytest.approx(7_200, abs=1)  # 80 × 90

        # Stock: revirtió 50 transit, agregó 80 transit = net +30
        assert_material(client, h, ch_id, total=680, transit=80, liquidated=600, avg_cost=pytest.approx(69.17, abs=0.01))

        # Liquidar la editada + pago
        api_liquidate_purchase(client, h, compra_edit["id"],
            immediate_payment=True, payment_account_id=s["account"].id,
        )
        # CHATARRA: (600×69.17 + 80×90) / 680 = (41500 + 7200)/680 = $71.62
        assert_material(client, h, ch_id, total=680, transit=0, liquidated=680, avg_cost=pytest.approx(71.62, abs=0.01))

        # =================================================================
        # PASO 11: Cancelar compra REGISTRADA (no liquidada)
        # Debe verificar stock suficiente (transito)
        # =================================================================
        compra_reg = api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["mat_chatarra"].id, "quantity": 30, "unit_price": 50, "warehouse_id": wp}],
        )
        assert compra_reg["status"] == "registered"
        assert_material(client, h, ch_id, total=710, transit=30, liquidated=680, avg_cost=pytest.approx(71.62, abs=0.01))

        cancelled_reg = api_cancel_purchase(client, h, compra_reg["id"])
        assert cancelled_reg["status"] == "cancelled"
        # Stock: revirtió 30 de transit, liquidado sin cambio, avg sin cambio
        assert_material(client, h, ch_id, total=680, transit=0, liquidated=680, avg_cost=pytest.approx(71.62, abs=0.01))

        # =================================================================
        # PASO 12: Validaciones 400/422
        # =================================================================

        # 12a: Supplier que no es material_supplier (usar customer)
        resp_bad_sup = client.post("/api/v1/purchases", json={
            "supplier_id": str(s["customer"].id),
            "date": f"{TODAY}T12:00:00",
            "lines": [{"material_id": str(s["mat_chatarra"].id), "quantity": 10, "unit_price": 50, "warehouse_id": str(wp)}],
        }, headers=h)
        assert resp_bad_sup.status_code == 400, f"Expected 400, got {resp_bad_sup.status_code}"

        # 12b: immediate_payment sin auto_liquidate → 422
        resp_bad_pay = client.post("/api/v1/purchases", json={
            "supplier_id": str(s["supplier"].id),
            "date": f"{TODAY}T12:00:00",
            "lines": [{"material_id": str(s["mat_chatarra"].id), "quantity": 10, "unit_price": 50, "warehouse_id": str(wp)}],
            "immediate_payment": True,
            "payment_account_id": str(s["account"].id),
        }, headers=h)
        assert resp_bad_pay.status_code == 422, f"Expected 422, got {resp_bad_pay.status_code}"

        # 12c: auto_liquidate con precio 0 → 422
        resp_bad_price = client.post("/api/v1/purchases", json={
            "supplier_id": str(s["supplier"].id),
            "date": f"{TODAY}T12:00:00",
            "lines": [{"material_id": str(s["mat_chatarra"].id), "quantity": 10, "unit_price": 0, "warehouse_id": str(wp)}],
            "auto_liquidate": True,
        }, headers=h)
        assert resp_bad_price.status_code == 422, f"Expected 422, got {resp_bad_price.status_code}"

        # 12d: Fecha futura → 400
        resp_bad_date = client.post("/api/v1/purchases", json={
            "supplier_id": str(s["supplier"].id),
            "date": "2099-12-31T12:00:00",
            "lines": [{"material_id": str(s["mat_chatarra"].id), "quantity": 10, "unit_price": 50, "warehouse_id": str(wp)}],
        }, headers=h)
        assert resp_bad_date.status_code == 400, f"Expected 400 for future date, got {resp_bad_date.status_code}"

        # 12e: Cancelar compra ya cancelada → 400
        resp_double_cancel = client.patch(f"/api/v1/purchases/{compra_1['id']}/cancel", headers=h)
        assert resp_double_cancel.status_code == 400

        # =================================================================
        # ACID TEST
        # =================================================================
        assert_pnl_equals_balance(client, h)
