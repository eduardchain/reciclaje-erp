"""
Test 12: Costo Promedio Movil — Edge Cases

Verifica calculo de costo promedio ponderado en todos los escenarios:
- Multiples compras a precios distintos
- Venta no cambia avg
- Cancelacion revierte avg (MaterialCostHistory)
- Bloqueo de cancelacion por operaciones posteriores (3 tipos)
- Comision per_kg prorrateada al costo
- Stock a cero + nueva compra (avg = precio nuevo)
- Adjustment increase mezcla con avg existente
- Transformacion proportional_weight y average_cost
"""
import pytest
from decimal import Decimal

from app.models.third_party import ThirdParty
from app.models.third_party_category import ThirdPartyCategory, ThirdPartyCategoryAssignment
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    TODAY, DATE_FROM, DATE_TO,
    create_material_category, create_business_unit, create_material,
    create_warehouse, create_account, create_expense_category,
    api_create_purchase, api_cancel_purchase,
    api_create_sale, api_money_movement,
    api_create_transformation, api_create_adjustment,
    assert_material, assert_pnl_equals_balance,
)


@pytest.fixture
def avg_cost_scenario(db_session, test_organization):
    """Setup: 4 materiales, 1 bodega, 1 cuenta $0 (capital via API), 4 terceros."""
    org_id = test_organization.id

    # Unidades de negocio (requeridas por material)
    bu_cobre = create_business_unit(db_session, org_id, "Cobre")
    bu_chatarra = create_business_unit(db_session, org_id, "Chatarra")
    bu_motor = create_business_unit(db_session, org_id, "Motor")
    bu_aluminio = create_business_unit(db_session, org_id, "Aluminio")

    # Materiales
    cat = create_material_category(db_session, org_id, "Metales AvgCost")
    cobre = create_material(db_session, org_id, "CU001", "COBRE", cat.id, bu_cobre.id)
    chatarra = create_material(db_session, org_id, "CH001", "CHATARRA", cat.id, bu_chatarra.id)
    motor = create_material(db_session, org_id, "MO001", "MOTOR", cat.id, bu_motor.id)
    aluminio = create_material(db_session, org_id, "AL001", "ALUMINIO", cat.id, bu_aluminio.id)

    # Bodega y cuenta (balance $0, capital se inyecta via API)
    bodega = create_warehouse(db_session, org_id, "Bodega Test")
    cuenta = create_account(db_session, org_id, "Cuenta Principal", balance=0)

    # Categoria de gasto
    cat_gasto = create_expense_category(db_session, org_id, "Gastos Generales")

    # Terceros
    supplier = create_third_party_with_category(db_session, org_id, "Proveedor Metales", "material_supplier")
    customer = create_third_party_with_category(db_session, org_id, "Cliente Final", "customer")
    comisionista = create_third_party_with_category(db_session, org_id, "Comisionista Test", "service_provider")

    # Inversor (para capital injection, requerido por acid test)
    inv_cat = ThirdPartyCategory(name="Socios AvgCost", behavior_type="investor", organization_id=org_id)
    db_session.add(inv_cat)
    db_session.flush()
    inversor = ThirdParty(name="Socio Capital", organization_id=org_id)
    db_session.add(inversor)
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(third_party_id=inversor.id, category_id=inv_cat.id))

    db_session.commit()

    return {
        "cobre": cobre,
        "chatarra": chatarra,
        "motor": motor,
        "aluminio": aluminio,
        "bodega": bodega,
        "cuenta": cuenta,
        "cat_gasto": cat_gasto,
        "supplier": supplier,
        "customer": customer,
        "comisionista": comisionista,
        "inversor": inversor,
    }


class TestAvgCostEdgeCases:

    def test_avg_cost_edge_cases(self, client, org_headers, avg_cost_scenario):
        s = avg_cost_scenario
        h = org_headers
        wh = s["bodega"].id
        cobre_id = str(s["cobre"].id)
        chatarra_id = str(s["chatarra"].id)
        motor_id = str(s["motor"].id)

        # =================================================================
        # Step 0: Capital injection $2M para que balance sheet cuadre
        # =================================================================
        api_money_movement(client, h, "capital-injection", {
            "investor_id": s["inversor"].id, "amount": 2_000_000,
            "account_id": s["cuenta"].id, "date": f"{TODAY}T12:00:00",
            "description": "Aporte de capital inicial",
        })

        # =================================================================
        # Step 1: Purchase A — COBRE 100kg x $50
        # =================================================================
        purchase_a = api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["cobre"].id, "quantity": 100, "unit_price": 50, "warehouse_id": wh}],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["cuenta"].id,
        )
        assert_material(client, h, cobre_id, total=100, liquidated=100, avg_cost=50.00)

        # =================================================================
        # Step 2: Purchase B — COBRE 200kg x $80
        # (100x50 + 200x80) / 300 = 21000/300 = 70.00
        # =================================================================
        purchase_b = api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["cobre"].id, "quantity": 200, "unit_price": 80, "warehouse_id": wh}],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["cuenta"].id,
        )
        assert_material(client, h, cobre_id, total=300, liquidated=300, avg_cost=70.00)

        # =================================================================
        # Step 3: Sale — COBRE 150kg x $120 (venta NO cambia avg)
        # =================================================================
        sale_1 = api_create_sale(client, h,
            customer_id=s["customer"].id, warehouse_id=wh,
            lines=[{"material_id": s["cobre"].id, "quantity": 150, "unit_price": 120}],
            auto_liquidate=True, immediate_collection=True, collection_account_id=s["cuenta"].id,
        )
        assert_material(client, h, cobre_id, total=150, liquidated=150, avg_cost=70.00)
        # COGS capturado al momento de la venta
        assert sale_1["lines"][0]["unit_cost"] == pytest.approx(70.00, abs=0.01)

        # =================================================================
        # Step 4: Purchase C — COBRE 50kg x $60
        # (150x70 + 50x60) / 200 = (10500+3000)/200 = 67.50
        # =================================================================
        purchase_c = api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["cobre"].id, "quantity": 50, "unit_price": 60, "warehouse_id": wh}],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["cuenta"].id,
        )
        assert_material(client, h, cobre_id, total=200, liquidated=200, avg_cost=67.50)

        # =================================================================
        # Step 5a: Cancel Purchase B -> MUST FAIL (Purchase C es posterior)
        # =================================================================
        resp_cancel_b = client.patch(f"/api/v1/purchases/{purchase_b['id']}/cancel", headers=h)
        assert resp_cancel_b.status_code == 400, \
            f"Expected 400 for blocked cancel, got {resp_cancel_b.status_code}: {resp_cancel_b.json()}"
        # Verificar que sigue liquidada
        resp_check = client.get(f"/api/v1/purchases/{purchase_b['id']}", headers=h)
        assert resp_check.json()["status"] == "liquidated"

        # =================================================================
        # Step 5b: Cancel Purchase C (ultima, sin operaciones posteriores)
        # Revierte a: stock=150, avg_cost=70.00 (via MaterialCostHistory)
        # =================================================================
        api_cancel_purchase(client, h, purchase_c["id"])
        assert_material(client, h, cobre_id, total=150, liquidated=150, avg_cost=70.00)

        # =================================================================
        # Step 6: Purchase D — COBRE 100kg x $90 con comision per_kg $5/kg
        # adjusted_unit_cost = 90 + 5 = 95
        # (150x70 + 100x95) / 250 = (10500+9500)/250 = 20000/250 = 80.00
        # =================================================================
        payload_d = {
            "supplier_id": str(s["supplier"].id),
            "date": f"{TODAY}T12:00:00",
            "lines": [{
                "material_id": str(s["cobre"].id),
                "quantity": 100,
                "unit_price": 90,
                "warehouse_id": str(wh),
            }],
            "commissions": [{
                "third_party_id": str(s["comisionista"].id),
                "commission_type": "per_kg",
                "commission_value": 5,
                "concept": "Comision per kg",
            }],
            "auto_liquidate": True,
            "immediate_payment": True,
            "payment_account_id": str(s["cuenta"].id),
        }
        resp_d = client.post("/api/v1/purchases", json=payload_d, headers=h)
        assert resp_d.status_code == 201, f"Create purchase D failed: {resp_d.json()}"
        purchase_d = resp_d.json()
        # 150x70=10500, 100x95=9500, total=20000/250=80.00
        assert_material(client, h, cobre_id, total=250, liquidated=250, avg_cost=80.00)

        # =================================================================
        # Step 7: Sale total — COBRE 250kg x $100 (stock a cero)
        # avg se mantiene incluso con stock=0
        # =================================================================
        sale_2 = api_create_sale(client, h,
            customer_id=s["customer"].id, warehouse_id=wh,
            lines=[{"material_id": s["cobre"].id, "quantity": 250, "unit_price": 100}],
            auto_liquidate=True, immediate_collection=True, collection_account_id=s["cuenta"].id,
        )
        assert_material(client, h, cobre_id, total=0, liquidated=0, avg_cost=80.00)

        # =================================================================
        # Step 8: Purchase E — COBRE 80kg x $110 (stock era 0, avg = precio nuevo)
        # =================================================================
        purchase_e = api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["cobre"].id, "quantity": 80, "unit_price": 110, "warehouse_id": wh}],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["cuenta"].id,
        )
        assert_material(client, h, cobre_id, total=80, liquidated=80, avg_cost=110.00)

        # =================================================================
        # Step 9: Adjustment increase — COBRE +20kg x $90
        # (80x110 + 20x90) / 100 = (8800+1800)/100 = 106.00
        # =================================================================
        api_create_adjustment(client, h,
            adjustment_type="increase", material_id=s["cobre"].id,
            warehouse_id=wh, quantity=20, unit_cost=90,
            reason="Found material",
        )
        assert_material(client, h, cobre_id, total=100, liquidated=100, avg_cost=106.00)

        # =================================================================
        # Step 10: Cancel Purchase E -> MUST FAIL (adjustment es posterior)
        # =================================================================
        resp_cancel_e = client.patch(f"/api/v1/purchases/{purchase_e['id']}/cancel", headers=h)
        assert resp_cancel_e.status_code == 400, \
            f"Expected 400 for blocked cancel, got {resp_cancel_e.status_code}: {resp_cancel_e.json()}"
        resp_check_e = client.get(f"/api/v1/purchases/{purchase_e['id']}", headers=h)
        assert resp_check_e.json()["status"] == "liquidated"

        # =================================================================
        # Step 11: Purchase CHATARRA — 500kg x $30
        # =================================================================
        purchase_chatarra = api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["chatarra"].id, "quantity": 500, "unit_price": 30, "warehouse_id": wh}],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["cuenta"].id,
        )
        assert_material(client, h, chatarra_id, total=500, liquidated=500, avg_cost=30.00)

        # =================================================================
        # Step 12: Transform CHATARRA 500kg -> COBRE 200kg + waste 50kg + CHATARRA restante via 2do destino?
        # NO — dest+waste must == source. Usamos 500kg completos:
        # CHATARRA 500kg -> COBRE 450kg + waste 50kg (proportional_weight)
        # distributable_value = 500x30 - 50x30 = 15000 - 1500 = 13500
        # COBRE 450kg -> unit_cost = 13500/450 = 30.00
        # New COBRE avg = (100x106 + 450x30) / 550 = (10600+13500)/550 = 43.82
        # CHATARRA: 500-500 = 0
        # =================================================================
        transf_1 = api_create_transformation(client, h,
            source_material_id=s["chatarra"].id,
            source_warehouse_id=wh,
            source_quantity=500,
            waste_quantity=50,
            cost_distribution="proportional_weight",
            lines=[{
                "destination_material_id": s["cobre"].id,
                "destination_warehouse_id": str(wh),
                "quantity": 450,
            }],
            reason="Transform chatarra a cobre",
        )
        assert_material(client, h, cobre_id, total=550, liquidated=550, avg_cost=pytest.approx(43.82, abs=0.01))
        assert_material(client, h, chatarra_id, total=0, liquidated=0, avg_cost=30.00)
        assert transf_1["waste_value"] == pytest.approx(1500.00, abs=0.01)

        # =================================================================
        # Step 12a: Cancel Purchase CHATARRA -> MUST FAIL
        # transformation_out en CHATARRA bloquea la cancelacion (sin hacks)
        # =================================================================
        resp_cancel_ch = client.patch(f"/api/v1/purchases/{purchase_chatarra['id']}/cancel", headers=h)
        assert resp_cancel_ch.status_code == 400, \
            f"Expected 400 for blocked cancel (transformation_out), got {resp_cancel_ch.status_code}: {resp_cancel_ch.json()}"
        # Verificar que sigue liquidada
        resp_check_ch = client.get(f"/api/v1/purchases/{purchase_chatarra['id']}", headers=h)
        assert resp_check_ch.json()["status"] == "liquidated"

        # =================================================================
        # Step 13: Purchase MOTOR 100kg x $200 + Transform -> COBRE 80kg + waste 20kg
        # (average_cost method)
        # =================================================================
        api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["motor"].id, "quantity": 100, "unit_price": 200, "warehouse_id": wh}],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["cuenta"].id,
        )
        assert_material(client, h, motor_id, total=100, liquidated=100, avg_cost=200.00)

        # Transform MOTOR 100kg -> COBRE 80kg + waste 20kg (average_cost)
        # average_cost uses destination's current avg (~43.82) as unit_cost for dest lines
        # New COBRE avg = (550x43.82 + 80x43.82) / 630 = 43.82 (no cambia, misma avg)
        transf_2 = api_create_transformation(client, h,
            source_material_id=s["motor"].id,
            source_warehouse_id=wh,
            source_quantity=100,
            waste_quantity=20,
            cost_distribution="average_cost",
            lines=[{
                "destination_material_id": s["cobre"].id,
                "destination_warehouse_id": str(wh),
                "quantity": 80,
            }],
            reason="Transform motor a cobre",
        )
        assert_material(client, h, cobre_id, total=630, liquidated=630, avg_cost=pytest.approx(43.82, abs=0.01))

        # =================================================================
        # Step 15: Compra multi-linea con comision fija — prorrateo por valor
        # COBRE 100kg x $50 = $5,000 + CHATARRA 200kg x $30 = $6,000
        # Total compra = $11,000. Comision fija = $1,100
        # Prorrateo: COBRE = 1100 × 5000/11000 = $500 → adj = 50 + 500/100 = $55/kg
        #            CHATARRA = 1100 × 6000/11000 = $600 → adj = 30 + 600/200 = $33/kg
        # COBRE: (630 × 43.82 + 100 × 55) / 730 = (27606.67 + 5500) / 730 = 45.35
        # CHATARRA: stock era 0 → avg = $33.00
        # =================================================================
        aluminio_id = str(s["aluminio"].id)

        payload_multi = {
            "supplier_id": str(s["supplier"].id),
            "date": f"{TODAY}T12:00:00",
            "lines": [
                {"material_id": str(s["cobre"].id), "quantity": 100, "unit_price": 50, "warehouse_id": str(wh)},
                {"material_id": str(s["chatarra"].id), "quantity": 200, "unit_price": 30, "warehouse_id": str(wh)},
            ],
            "commissions": [{
                "third_party_id": str(s["comisionista"].id),
                "commission_type": "fixed",
                "commission_value": 1100,
                "concept": "Comision compra multi-linea",
            }],
            "auto_liquidate": True,
            "immediate_payment": True,
            "payment_account_id": str(s["cuenta"].id),
        }
        resp_multi = client.post("/api/v1/purchases", json=payload_multi, headers=h)
        assert resp_multi.status_code == 201, f"Multi-line purchase failed: {resp_multi.json()}"

        assert_material(client, h, cobre_id, total=730, liquidated=730, avg_cost=pytest.approx(45.35, abs=0.01))
        assert_material(client, h, chatarra_id, total=200, liquidated=200, avg_cost=pytest.approx(33.00, abs=0.01))

        # =================================================================
        # Step 16: Multiples adjustments consecutivos en ALUMINIO (aislado)
        # increase 100kg@$50 → avg=50
        # increase 200kg@$80 → avg=(100×50 + 200×80)/300 = 70
        # decrease 150kg → avg=70 (decrease no cambia avg)
        # increase 50kg@$40 → avg=(150×70 + 50×40)/200 = 62.50
        # =================================================================
        api_create_adjustment(client, h,
            adjustment_type="increase", material_id=s["aluminio"].id,
            warehouse_id=wh, quantity=100, unit_cost=50, reason="Aluminio inicial",
        )
        assert_material(client, h, aluminio_id, total=100, liquidated=100, avg_cost=50.00)

        api_create_adjustment(client, h,
            adjustment_type="increase", material_id=s["aluminio"].id,
            warehouse_id=wh, quantity=200, unit_cost=80, reason="Segundo lote aluminio",
        )
        assert_material(client, h, aluminio_id, total=300, liquidated=300, avg_cost=pytest.approx(70.00, abs=0.01))

        api_create_adjustment(client, h,
            adjustment_type="decrease", material_id=s["aluminio"].id,
            warehouse_id=wh, quantity=150, reason="Merma aluminio",
        )
        assert_material(client, h, aluminio_id, total=150, liquidated=150, avg_cost=pytest.approx(70.00, abs=0.01))

        api_create_adjustment(client, h,
            adjustment_type="increase", material_id=s["aluminio"].id,
            warehouse_id=wh, quantity=50, unit_cost=40, reason="Tercer lote barato",
        )
        assert_material(client, h, aluminio_id, total=200, liquidated=200, avg_cost=pytest.approx(62.50, abs=0.01))

        # =================================================================
        # Step 17: Transformacion manual — ALUMINIO 200kg → COBRE 180kg + waste 20kg
        # unit_cost manual = $75/kg (distinto al avg del destino)
        # manual total = 180 × 75 = $13,500
        # waste_value = 20 × 62.50 = $1,250
        # source_value = 200 × 62.50 = $12,500
        # Validacion: manual($13,500) + waste($1,250) = $14,750 vs source $12,500
        #   → diff = $2,250 > 1% tolerance ($125) → SHOULD FAIL
        # Usemos unit_cost que cuadre: distributable = 12500 - 1250 = 11250
        #   → 11250 / 180 = $62.50/kg (cuadra exacto)
        # COBRE: (730 × 45.35 + 180 × 62.50) / 910 = (33105.50 + 11250) / 910 = 48.74
        # =================================================================
        transf_manual = api_create_transformation(client, h,
            source_material_id=s["aluminio"].id,
            source_warehouse_id=wh,
            source_quantity=200,
            waste_quantity=20,
            cost_distribution="manual",
            lines=[{
                "destination_material_id": s["cobre"].id,
                "destination_warehouse_id": str(wh),
                "quantity": 180,
                "unit_cost": 62.50,
            }],
            reason="Transform manual aluminio a cobre",
        )
        assert_material(client, h, cobre_id, total=910, liquidated=910, avg_cost=pytest.approx(48.74, abs=0.01))
        assert_material(client, h, aluminio_id, total=0, liquidated=0, avg_cost=pytest.approx(62.50, abs=0.01))

        # =================================================================
        # Step 18: Final acid test — contabilidad cuadra
        # =================================================================
        assert_pnl_equals_balance(client, h)
