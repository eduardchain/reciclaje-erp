"""
Escenario 6: Transformaciones — Stress Test Completo.

Cubre:
- 3 metodos de costo: proportional_weight, average_cost, manual
- Merma (waste_loss) y sin merma
- value_difference / transformation_profit en P&L
- Destino con stock preexistente (mezcla avg_cost)
- Anulacion de transformacion (revertir stock + avg_cost)
- Anulacion bloqueada por operacion posterior
- Transformacion entre bodegas (fuente en una, destino en otra)
- Multiples transformaciones secuenciales
- Stock negativo en fuente (warning)
- Validacion: material fuente == destino
- P&L == Balance Sheet acid test
"""
import pytest
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    TODAY, DATE_FROM, DATE_TO,
    create_material_category, create_business_unit, create_material,
    create_warehouse, create_account,
    api_create_purchase, api_create_sale, api_money_movement,
    api_create_transformation, api_create_adjustment,
    assert_material, assert_pnl, assert_pnl_equals_balance,
)


@pytest.fixture
def scenario(db_session, test_organization):
    org_id = test_organization.id
    cat = create_material_category(db_session, org_id, "Metales INT06")
    bu_mo = create_business_unit(db_session, org_id, "Motor INT06")
    bu_cu = create_business_unit(db_session, org_id, "Cobre INT06")
    bu_fe = create_business_unit(db_session, org_id, "Hierro INT06")

    motor = create_material(db_session, org_id, "INT06-MO", "Motor Electrico", cat.id, bu_mo.id)
    cobre = create_material(db_session, org_id, "INT06-CU", "Cobre Limpio", cat.id, bu_cu.id)
    hierro = create_material(db_session, org_id, "INT06-FE", "Hierro", cat.id, bu_fe.id)

    wh_1 = create_warehouse(db_session, org_id, "Bodega Principal INT06")
    wh_2 = create_warehouse(db_session, org_id, "Bodega Secundaria INT06")
    account = create_account(db_session, org_id, "Cuenta INT06", balance=0)

    investor = create_third_party_with_category(db_session, org_id, "Socio INT06", "investor")
    supplier = create_third_party_with_category(db_session, org_id, "Proveedor INT06", "material_supplier")
    customer = create_third_party_with_category(db_session, org_id, "Cliente INT06", "customer")

    db_session.commit()
    return {
        "motor": motor, "cobre": cobre, "hierro": hierro,
        "wh_1": wh_1, "wh_2": wh_2, "account": account,
        "investor": investor, "supplier": supplier, "customer": customer,
    }


class TestTransformationStress:

    def test_transformation_full_stress(self, client, org_headers, scenario):
        s = scenario
        h = org_headers
        w1 = s["wh_1"].id
        w2 = s["wh_2"].id
        mo_id = str(s["motor"].id)
        cu_id = str(s["cobre"].id)
        fe_id = str(s["hierro"].id)

        # Setup: capital + compras
        api_money_movement(client, h, "capital-injection", {
            "investor_id": s["investor"].id, "amount": 2_000_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Capital",
        })

        # Motor: 500kg × $200 = $100K (Bodega 1)
        api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["motor"].id, "quantity": 500, "unit_price": 200, "warehouse_id": w1}],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["account"].id,
        )
        # Cobre preexistente: 100kg × $400 = $40K (Bodega 1)
        api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["cobre"].id, "quantity": 100, "unit_price": 400, "warehouse_id": w1}],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["account"].id,
        )

        assert_material(client, h, mo_id, total=500, liquidated=500, avg_cost=200)
        assert_material(client, h, cu_id, total=100, liquidated=100, avg_cost=400)

        # =================================================================
        # PASO 1: proportional_weight con merma, 2 destinos
        # Motor 300kg → Cobre 150kg + Hierro 120kg + waste 30kg
        # source_value = 300 × $200 = $60K
        # waste_value = 30 × $200 = $6K
        # distributable = $54K
        # total_dest = 150 + 120 = 270
        # Cobre: (150/270) × $54K = $30K → $200/kg
        # Hierro: (120/270) × $54K = $24K → $200/kg
        # Cobre avg: (100×400 + 150×200) / 250 = (40K+30K)/250 = $280
        # =================================================================
        t1 = api_create_transformation(client, h,
            source_material_id=s["motor"].id, source_warehouse_id=w1,
            source_quantity=300, waste_quantity=30,
            cost_distribution="proportional_weight",
            lines=[
                {"destination_material_id": s["cobre"].id, "destination_warehouse_id": str(w1), "quantity": 150},
                {"destination_material_id": s["hierro"].id, "destination_warehouse_id": str(w1), "quantity": 120},
            ],
            reason="Desarmado motor lote 1",
        )
        assert t1["waste_value"] == pytest.approx(6_000, abs=1)
        assert t1["value_difference"] == pytest.approx(0, abs=1)  # proportional: no value diff

        assert_material(client, h, mo_id, total=200, liquidated=200, avg_cost=200)
        assert_material(client, h, cu_id, total=250, liquidated=250, avg_cost=pytest.approx(280, abs=0.01))
        assert_material(client, h, fe_id, total=120, liquidated=120, avg_cost=200)

        # =================================================================
        # PASO 2: average_cost — usa avg DESTINO, genera value_difference
        # Motor 200kg → Cobre 170kg + waste 30kg
        # source_value = 200 × $200 = $40K
        # waste = 30 × $200 = $6K
        # distributable = $34K
        # Cobre avg actual = $280, dest_value = 170 × $280 = $47.6K
        # value_difference = $47.6K - $34K = $13.6K (ganancia)
        # Cobre avg no cambia porque usa su propio avg:
        # (250×280 + 170×280) / 420 = 280
        # =================================================================
        t2 = api_create_transformation(client, h,
            source_material_id=s["motor"].id, source_warehouse_id=w1,
            source_quantity=200, waste_quantity=30,
            cost_distribution="average_cost",
            lines=[
                {"destination_material_id": s["cobre"].id, "destination_warehouse_id": str(w1), "quantity": 170},
            ],
            reason="Desarmado motor lote 2",
        )
        assert t2["value_difference"] == pytest.approx(13_600, abs=1)
        assert t2["waste_value"] == pytest.approx(6_000, abs=1)

        assert_material(client, h, mo_id, total=0, liquidated=0, avg_cost=200)
        assert_material(client, h, cu_id, total=420, liquidated=420, avg_cost=pytest.approx(280, abs=0.01))

        # =================================================================
        # PASO 3: Transformacion SIN merma (waste=0)
        # Cobre 100kg → Hierro 100kg (proportional_weight)
        # Cobre avg = $280, source_value = $28K, waste = $0, distributable = $28K
        # Hierro: 100kg × $280/kg
        # Hierro avg: (120×200 + 100×280) / 220 = (24K+28K)/220 = $236.36
        # =================================================================
        t3 = api_create_transformation(client, h,
            source_material_id=s["cobre"].id, source_warehouse_id=w1,
            source_quantity=100, waste_quantity=0,
            cost_distribution="proportional_weight",
            lines=[
                {"destination_material_id": s["hierro"].id, "destination_warehouse_id": str(w1), "quantity": 100},
            ],
            reason="Reconfigurar cobre a hierro",
        )
        assert t3["waste_value"] == pytest.approx(0, abs=1)
        assert_material(client, h, cu_id, total=320, liquidated=320, avg_cost=pytest.approx(280, abs=0.01))
        assert_material(client, h, fe_id, total=220, liquidated=220, avg_cost=pytest.approx(236.36, abs=0.01))

        # =================================================================
        # PASO 4: manual — unit_cost explicito
        # Hierro 100kg → Cobre 90kg + waste 10kg
        # Hierro avg ≈ $236.36, source_value = 100 × 236.36 = $23,636
        # waste_value = 10 × 236.36 = $2,363.64
        # distributable = $21,272.73
        # manual: 90kg × $236.36/kg = $21,272.73 (cuadra exacto)
        # Cobre avg: (320×280 + 90×236.36) / 410 = (89600+21272.73)/410 = $270.18
        # =================================================================
        fe_resp = client.get(f"/api/v1/materials/{fe_id}", headers=h)
        fe_avg = fe_resp.json()["current_average_cost"]

        t4 = api_create_transformation(client, h,
            source_material_id=s["hierro"].id, source_warehouse_id=w1,
            source_quantity=100, waste_quantity=10,
            cost_distribution="manual",
            lines=[
                {"destination_material_id": s["cobre"].id, "destination_warehouse_id": str(w1),
                 "quantity": 90, "unit_cost": round(fe_avg, 2)},
            ],
            reason="Refinar hierro a cobre",
        )
        assert_material(client, h, fe_id, total=120, liquidated=120, avg_cost=pytest.approx(236.36, abs=0.01))
        assert_material(client, h, cu_id, total=410, liquidated=410, avg_cost=pytest.approx(270.18, abs=0.5))

        # =================================================================
        # PASO 5: Transformacion entre bodegas
        # Hierro 50kg (Bodega 1) → Cobre 40kg (Bodega 2) + waste 10kg
        # =================================================================
        t5 = api_create_transformation(client, h,
            source_material_id=s["hierro"].id, source_warehouse_id=w1,
            source_quantity=50, waste_quantity=10,
            cost_distribution="proportional_weight",
            lines=[
                {"destination_material_id": s["cobre"].id, "destination_warehouse_id": str(w2), "quantity": 40},
            ],
            reason="Cross-warehouse transform",
        )
        assert_material(client, h, fe_id, total=70, liquidated=70, avg_cost=pytest.approx(236.36, abs=0.01))
        # Cobre total: 410 + 40 = 450
        cu_resp = client.get(f"/api/v1/materials/{cu_id}", headers=h)
        assert cu_resp.json()["current_stock"] == pytest.approx(450, abs=0.01)

        # =================================================================
        # PASO 6: Anulacion de transformacion (t3: cobre→hierro sin merma)
        # Debe revertir: hierro -100, cobre +100, avg_cost de hierro revertido
        # =================================================================
        # Primero, el hierro actual tiene transformaciones posteriores (t4, t5)
        # sobre hierro como FUENTE → transformation_out bloquea?
        # t4 usó hierro como fuente → sí, transformation_out existe
        # Intentar anular t3 debería FALLAR porque t4 es posterior sobre hierro
        resp_annul_blocked = client.post(
            f"/api/v1/inventory/transformations/{t3['id']}/annul",
            json={"reason": "Revertir"}, headers=h,
        )
        assert resp_annul_blocked.status_code == 400, \
            f"Expected 400 for blocked annul, got {resp_annul_blocked.status_code}"

        # Anular t5 (la ultima sobre hierro como fuente, sin posteriores sobre hierro)
        # Pero t5 agregó cobre como destino → hay transformation_in sobre cobre
        # Y después no hay operaciones sobre cobre que bloqueen t5... verificar
        resp_annul_t5 = client.post(
            f"/api/v1/inventory/transformations/{t5['id']}/annul",
            json={"reason": "Revertir cross-warehouse"}, headers=h,
        )
        assert resp_annul_t5.status_code == 200, f"Annul t5 failed: {resp_annul_t5.json()}"

        # Hierro restaurado: 70 + 50 = 120
        assert_material(client, h, fe_id, total=120, liquidated=120, avg_cost=pytest.approx(236.36, abs=0.01))
        # Cobre: 450 - 40 = 410
        cu_resp2 = client.get(f"/api/v1/materials/{cu_id}", headers=h)
        assert cu_resp2.json()["current_stock"] == pytest.approx(410, abs=0.01)

        # =================================================================
        # PASO 7: Stock negativo en fuente (warning, no bloquea)
        # Hierro tiene 120kg, transformamos 150kg
        # =================================================================
        resp_neg = client.post("/api/v1/inventory/transformations", json={
            "source_material_id": str(s["hierro"].id),
            "source_warehouse_id": str(w1),
            "source_quantity": 150,
            "waste_quantity": 10,
            "cost_distribution": "proportional_weight",
            "lines": [{"destination_material_id": str(s["cobre"].id), "destination_warehouse_id": str(w1), "quantity": 140}],
            "date": f"{TODAY}T12:00:00",
            "reason": "Forzar negativo",
        }, headers=h)
        assert resp_neg.status_code == 201
        neg_data = resp_neg.json()
        assert len(neg_data.get("warnings", [])) > 0, "Expected stock warning"
        # Hierro: 120 - 150 = -30
        assert_material(client, h, fe_id, total=-30, liquidated=-30, avg_cost=pytest.approx(236.36, abs=0.01))

        # =================================================================
        # PASO 8: Validacion — material fuente == destino
        # =================================================================
        resp_same = client.post("/api/v1/inventory/transformations", json={
            "source_material_id": str(s["cobre"].id),
            "source_warehouse_id": str(w1),
            "source_quantity": 10,
            "waste_quantity": 0,
            "cost_distribution": "proportional_weight",
            "lines": [{"destination_material_id": str(s["cobre"].id), "destination_warehouse_id": str(w1), "quantity": 10}],
            "date": f"{TODAY}T12:00:00",
            "reason": "Same material",
        }, headers=h)
        assert resp_same.status_code == 400, f"Expected 400 for same source/dest, got {resp_same.status_code}"

        # =================================================================
        # PASO 9: Venta de material transformado para verificar COGS
        # Cobre 100kg × $500 = $50K, COGS = 100 × avg_cobre
        # =================================================================
        api_create_sale(client, h,
            customer_id=s["customer"].id, warehouse_id=w1,
            lines=[{"material_id": s["cobre"].id, "quantity": 100, "unit_price": 500}],
            auto_liquidate=True, immediate_collection=True, collection_account_id=s["account"].id,
        )

        # =================================================================
        # P&L: debe tener waste_loss, transformation_profit, todo cuadrado
        # =================================================================
        pnl_resp = client.get("/api/v1/reports/profit-and-loss",
            params={"date_from": DATE_FROM, "date_to": DATE_TO}, headers=h)
        pnl = pnl_resp.json()

        assert pnl["sales_revenue"] == pytest.approx(50_000, abs=1)
        # waste_loss = sum de todas las transformaciones activas
        assert pnl["waste_loss"] > 0, f"Expected waste_loss > 0, got {pnl['waste_loss']}"
        # transformation_profit = value_difference de t2 ($13.6K) + otros
        assert pnl["transformation_profit"] != 0, "Expected non-zero transformation_profit"

        # =================================================================
        # ACID TEST
        # =================================================================
        assert_pnl_equals_balance(client, h)
