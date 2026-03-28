"""
Test Acido: "Un Mes de Operaciones"

37 operaciones secuenciales, 4 checkpoints de verificacion.
Cubre TODOS los tipos de transaccion: compras, ventas, DPs, 15+ money movements,
transformaciones, ajustes, activos fijos, diferidos, distribuciones, anticipos, anulaciones.
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
    api_create_purchase, api_liquidate_purchase, api_cancel_purchase,
    api_create_sale, api_liquidate_sale,
    api_create_double_entry, api_cancel_double_entry,
    api_money_movement, api_create_transformation,
    api_create_adjustment, api_warehouse_transfer, api_annul_movement,
    api_create_fixed_asset, api_apply_pending_depreciations,
    api_create_scheduled_expense, api_apply_scheduled_expense,
    api_create_profit_distribution,
    assert_material, assert_tp_balance, assert_account_balance,
    assert_pnl, assert_balance_sheet, assert_cash_flow, assert_pnl_equals_balance,
)


@pytest.fixture
def acid(db_session, test_organization):
    """Setup completo: 15+ maestros para simular un mes de operaciones."""
    org_id = test_organization.id

    # Unidades de negocio
    bu_ch = create_business_unit(db_session, org_id, "Chatarra")
    bu_nf = create_business_unit(db_session, org_id, "No Ferrosos")
    bu_el = create_business_unit(db_session, org_id, "Electronicos")

    # Materiales
    cat = create_material_category(db_session, org_id, "Metales ACID")
    chatarra = create_material(db_session, org_id, "FE001", "Chatarra Acero", cat.id, bu_ch.id)
    cobre = create_material(db_session, org_id, "NF001", "Cobre Limpio", cat.id, bu_nf.id)
    motor = create_material(db_session, org_id, "EL001", "Motor Electrico", cat.id, bu_el.id)

    # Bodegas
    bodega_principal = create_warehouse(db_session, org_id, "Bodega Principal")
    bodega_secundaria = create_warehouse(db_session, org_id, "Bodega Secundaria")

    # Cuentas
    bancolombia = create_account(db_session, org_id, "Bancolombia", balance=0)
    caja = create_account(db_session, org_id, "Caja", balance=0)

    # Categorias de gasto
    cat_flete = create_expense_category(db_session, org_id, "Flete", is_direct=True)
    cat_servicios = create_expense_category(db_session, org_id, "Servicios", is_direct=False)
    cat_depreciacion = create_expense_category(db_session, org_id, "Depreciacion Equipos", is_direct=False)

    # Terceros — inversor con categoría "Socios" para profit distribution
    inv_cat = ThirdPartyCategory(name="Socios ACID", behavior_type="investor", organization_id=org_id)
    db_session.add(inv_cat)
    db_session.flush()
    inversor = ThirdParty(name="Socio Principal", organization_id=org_id)
    db_session.add(inversor)
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(third_party_id=inversor.id, category_id=inv_cat.id))

    proveedor_local = create_third_party_with_category(db_session, org_id, "Chatarrero Martinez", "material_supplier")
    proveedor_directo = create_third_party_with_category(db_session, org_id, "Metales del Sur", "material_supplier")
    cliente_a = create_third_party_with_category(db_session, org_id, "Fundicion ABC", "customer")
    cliente_e = create_third_party_with_category(db_session, org_id, "Exportadora E", "customer")
    comisionista = create_third_party_with_category(db_session, org_id, "Comisionista JR", "service_provider")
    liability_tp = create_third_party_with_category(db_session, org_id, "Tecniservicios", "liability")
    provision_tp = create_third_party_with_category(db_session, org_id, "Provision Legal", "provision")
    generic_tp = create_third_party_with_category(db_session, org_id, "Varios Generico", "generic")

    db_session.commit()

    return {
        "bu_ch": bu_ch, "bu_nf": bu_nf, "bu_el": bu_el,
        "chatarra": chatarra, "cobre": cobre, "motor": motor,
        "bodega_principal": bodega_principal, "bodega_secundaria": bodega_secundaria,
        "bancolombia": bancolombia, "caja": caja,
        "cat_flete": cat_flete, "cat_servicios": cat_servicios, "cat_depreciacion": cat_depreciacion,
        "inversor": inversor,
        "proveedor_local": proveedor_local, "proveedor_directo": proveedor_directo,
        "cliente_a": cliente_a, "cliente_e": cliente_e,
        "comisionista": comisionista,
        "liability_tp": liability_tp, "provision_tp": provision_tp, "generic_tp": generic_tp,
    }


class TestAcidFullMonth:

    def test_acid_full_month(self, client, org_headers, acid):
        s = acid
        h = org_headers
        bp = s["bodega_principal"].id
        bs_ = s["bodega_secundaria"].id

        # =================================================================
        # SEMANA 1 — Capitalización + Primeras Compras (Ops 1-7)
        # =================================================================

        # Op 1: Capital injection $5M → Bancolombia
        api_money_movement(client, h, "capital-injection", {
            "investor_id": s["inversor"].id, "amount": 5_000_000,
            "account_id": s["bancolombia"].id, "date": "2026-03-01T12:00:00",
            "description": "Aporte de capital inicial",
        })

        # Op 2: Transfer $500K Bancolombia → Caja
        api_money_movement(client, h, "transfer", {
            "amount": 500_000, "source_account_id": s["bancolombia"].id,
            "destination_account_id": s["caja"].id,
            "date": "2026-03-01T12:00:00", "description": "Fondeo caja",
        })

        # Op 3: Compra CHATARRA 2000kg × $100 = $200K (SOLO REGISTRAR)
        compra_1 = api_create_purchase(client, h,
            supplier_id=s["proveedor_local"].id,
            lines=[{"material_id": s["chatarra"].id, "quantity": 2000, "unit_price": 100, "warehouse_id": bp}],
            date="2026-03-02",
        )

        # Op 4: Compra COBRE 500kg × $500 = $250K (auto-liq + pago Bancolombia)
        api_create_purchase(client, h,
            supplier_id=s["proveedor_directo"].id,
            lines=[{"material_id": s["cobre"].id, "quantity": 500, "unit_price": 500, "warehouse_id": bp}],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["bancolombia"].id,
            date="2026-03-03",
        )

        # Op 5: Compra MOTOR 300kg × $200 = $60K (auto-liq + pago Caja)
        api_create_purchase(client, h,
            supplier_id=s["proveedor_local"].id,
            lines=[{"material_id": s["motor"].id, "quantity": 300, "unit_price": 200, "warehouse_id": bs_}],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["caja"].id,
            date="2026-03-04",
        )

        # Op 6: Anticipo proveedor $50K
        api_money_movement(client, h, "advance-payment", {
            "supplier_id": s["proveedor_local"].id, "amount": 50_000,
            "account_id": s["bancolombia"].id, "date": "2026-03-05T12:00:00",
            "description": "Anticipo compras futuras",
        })

        # Op 7: Liquidar compra #1 + pago inmediato
        api_liquidate_purchase(client, h, compra_1["id"],
            immediate_payment=True, payment_account_id=s["bancolombia"].id,
        )

        # --- CHECKPOINT 1 ---
        assert_account_balance(client, h, str(s["bancolombia"].id), 4_000_000)
        assert_account_balance(client, h, str(s["caja"].id), 440_000)
        assert_material(client, h, str(s["chatarra"].id), total=2000, transit=0, liquidated=2000, avg_cost=100)
        assert_material(client, h, str(s["cobre"].id), total=500, transit=0, liquidated=500, avg_cost=500)
        assert_material(client, h, str(s["motor"].id), total=300, transit=0, liquidated=300, avg_cost=200)
        assert_tp_balance(client, h, str(s["inversor"].id), -5_000_000)
        assert_tp_balance(client, h, str(s["proveedor_local"].id), 50_000)
        assert_tp_balance(client, h, str(s["proveedor_directo"].id), 0)
        assert_pnl(client, h, net_profit=0)
        assert_balance_sheet(client, h, total_assets=5_000_000)
        assert_pnl_equals_balance(client, h)

        # =================================================================
        # SEMANA 2 — Ventas + Gastos + DP (Ops 8-15)
        # =================================================================

        # Op 8: Venta CHATARRA 800kg × $150 = $120K (SOLO REGISTRAR)
        venta_1 = api_create_sale(client, h,
            customer_id=s["cliente_a"].id, warehouse_id=bp,
            lines=[{"material_id": s["chatarra"].id, "quantity": 800, "unit_price": 150}],
            date="2026-03-08",
        )

        # Op 9: Venta COBRE 200kg × $800 = $160K (auto-liq + cobro + comisión 2%)
        api_create_sale(client, h,
            customer_id=s["cliente_e"].id, warehouse_id=bp,
            lines=[{"material_id": s["cobre"].id, "quantity": 200, "unit_price": 800}],
            auto_liquidate=True, immediate_collection=True, collection_account_id=s["bancolombia"].id,
            commissions=[{
                "third_party_id": str(s["comisionista"].id),
                "commission_type": "percentage", "commission_value": 2,
                "concept": "Comision venta COBRE",
            }],
            date="2026-03-09",
        )

        # Op 10: Anticipo cobro $30K de cliente A
        api_money_movement(client, h, "advance-collection", {
            "customer_id": s["cliente_a"].id, "amount": 30_000,
            "account_id": s["bancolombia"].id, "date": "2026-03-10T12:00:00",
            "description": "Anticipo venta futura",
        })

        # Op 11: Liquidar venta #1 + cobro inmediato
        api_liquidate_sale(client, h, venta_1["id"],
            immediate_collection=True, collection_account_id=s["bancolombia"].id,
        )

        # Op 12: Gasto directo — Flete $15K, UN Chatarra
        api_money_movement(client, h, "expense", {
            "amount": 15_000, "expense_category_id": s["cat_flete"].id,
            "account_id": s["bancolombia"].id, "business_unit_id": s["bu_ch"].id,
            "date": "2026-03-11T12:00:00", "description": "Flete compra chatarra",
        })

        # Op 13: Gasto compartido — Servicios $12K (guardar ID para anular en op 33)
        gasto_compartido = api_money_movement(client, h, "expense", {
            "amount": 12_000, "expense_category_id": s["cat_servicios"].id,
            "account_id": s["bancolombia"].id,
            "applicable_business_unit_ids": [str(s["bu_ch"].id), str(s["bu_nf"].id)],
            "date": "2026-03-12T12:00:00", "description": "Servicios publicos",
        })
        gasto_compartido_id = gasto_compartido["id"]

        # Op 14: DP — CHATARRA 1000kg, compra@$110, venta@$140, comisión $3K (auto-liq)
        dp_1 = api_create_double_entry(client, h,
            supplier_id=s["proveedor_local"].id, customer_id=s["cliente_e"].id,
            lines=[{"material_id": s["chatarra"].id, "quantity": 1000, "purchase_unit_price": 110, "sale_unit_price": 140}],
            commissions=[{
                "third_party_id": str(s["comisionista"].id),
                "commission_type": "fixed", "commission_value": 3000,
                "concept": "Comision DP chatarra",
            }],
            auto_liquidate=True, date="2026-03-13",
        )

        # Op 15: Ingreso por servicio $5K
        api_money_movement(client, h, "service-income", {
            "account_id": s["bancolombia"].id, "amount": 5_000,
            "date": "2026-03-14T12:00:00", "description": "Servicio de pesaje",
        })

        # --- CHECKPOINT 2 ---
        assert_account_balance(client, h, str(s["bancolombia"].id), 4_288_000)
        assert_account_balance(client, h, str(s["caja"].id), 440_000)
        assert_tp_balance(client, h, str(s["proveedor_local"].id), -60_000)
        assert_tp_balance(client, h, str(s["cliente_a"].id), -30_000)
        assert_tp_balance(client, h, str(s["cliente_e"].id), 140_000)
        assert_tp_balance(client, h, str(s["comisionista"].id), -6_200)
        assert_pnl(client, h,
            sales_revenue=280_000, cost_of_goods_sold=180_000,
            double_entry_profit=30_000, service_income=5_000,
            operating_expenses=27_000, commissions_paid=6_200,
            net_profit=101_800)
        assert_pnl_equals_balance(client, h)

        # =================================================================
        # SEMANA 3 — Transformación + Cancelaciones + Pasivos (Ops 16-25)
        # =================================================================

        # Op 16: Transformar MOTOR 300kg → COBRE 120kg + CHATARRA 160kg + merma 20kg
        api_create_transformation(client, h,
            source_material_id=s["motor"].id, source_warehouse_id=bs_,
            source_quantity=300, waste_quantity=20,
            cost_distribution="proportional_weight",
            lines=[
                {"destination_material_id": s["cobre"].id, "destination_warehouse_id": bs_, "quantity": 120},
                {"destination_material_id": s["chatarra"].id, "destination_warehouse_id": bs_, "quantity": 160},
            ],
            reason="Desarmado de motores", date="2026-03-16",
        )

        # Op 17: Transfer COBRE 120kg Secundaria → Principal
        api_warehouse_transfer(client, h,
            material_id=s["cobre"].id, source_warehouse_id=bs_,
            destination_warehouse_id=bp, quantity=120,
            reason="Consolidar cobre",
        )

        # Op 18: Cancelar DP #1
        api_cancel_double_entry(client, h, dp_1["id"])

        # Op 19-20: Expense accrual $8K al pasivo + pago $8K
        api_money_movement(client, h, "expense-accrual", {
            "third_party_id": s["liability_tp"].id, "amount": 8_000,
            "expense_category_id": s["cat_servicios"].id,
            "date": "2026-03-18T12:00:00", "description": "Mantenimiento pendiente",
        })
        api_money_movement(client, h, "supplier-payment", {
            "supplier_id": s["liability_tp"].id, "amount": 8_000,
            "account_id": s["bancolombia"].id, "date": "2026-03-18T12:00:00",
            "description": "Pago mantenimiento",
        })

        # Op 21-22: Provision deposit $20K + provision expense $5K
        api_money_movement(client, h, "provision-deposit", {
            "provision_id": s["provision_tp"].id, "amount": 20_000,
            "account_id": s["bancolombia"].id, "date": "2026-03-19T12:00:00",
            "description": "Fondeo provision",
        })
        api_money_movement(client, h, "provision-expense", {
            "provision_id": s["provision_tp"].id, "amount": 5_000,
            "expense_category_id": s["cat_flete"].id,
            "date": "2026-03-19T12:00:00", "description": "Honorarios abogado",
        })

        # Op 23: Venta COBRE 120kg × $900 = $108K (auto-liq + cobro Caja)
        # COBRE avg after transformation: (300×500 + 120×200) / 420 = 174000/420 ≈ $414.29
        api_create_sale(client, h,
            customer_id=s["cliente_a"].id, warehouse_id=bp,
            lines=[{"material_id": s["cobre"].id, "quantity": 120, "unit_price": 900}],
            auto_liquidate=True, immediate_collection=True, collection_account_id=s["caja"].id,
            date=TODAY,
        )

        # --- CHECKPOINT 3 ---
        # Proveedor local: volvió a +$50K (DP cancelada)
        assert_tp_balance(client, h, str(s["proveedor_local"].id), 50_000)
        # Cliente E: $0 (DP cancelada)
        assert_tp_balance(client, h, str(s["cliente_e"].id), 0)
        # Comisionista: solo -$3.2K (DP comisión cancelada)
        assert_tp_balance(client, h, str(s["comisionista"].id), -3_200)
        # Liability pagado
        assert_tp_balance(client, h, str(s["liability_tp"].id), 0)
        # Provision con fondos
        assert_tp_balance(client, h, str(s["provision_tp"].id), -15_000)
        # P&L: waste_loss visible, DP cancelada no aparece
        assert_pnl(client, h, waste_loss=4_000, double_entry_profit=0)
        assert_pnl_equals_balance(client, h)

        # =================================================================
        # SEMANA 4 — Nuevas ops + Activos + Diferidos + Cierre
        # =================================================================

        # Op 24: Compra CHATARRA 500kg × $120 con comision per_kg $5
        # commission = $5 × 500 = $2,500
        # adjusted = 120 + 2500/500 = $125/kg
        payload_perkg = {
            "supplier_id": str(s["proveedor_directo"].id),
            "date": f"{TODAY}T12:00:00",
            "lines": [{"material_id": str(s["chatarra"].id), "quantity": 500, "unit_price": 120, "warehouse_id": str(bp)}],
            "commissions": [{
                "third_party_id": str(s["comisionista"].id),
                "commission_type": "per_kg", "commission_value": 5,
                "concept": "Comision per kg chatarra",
            }],
            "auto_liquidate": True, "immediate_payment": True,
            "payment_account_id": str(s["bancolombia"].id),
        }
        resp_perkg = client.post("/api/v1/purchases", json=payload_perkg, headers=h)
        assert resp_perkg.status_code == 201

        # Op 25: Venta CHATARRA 300kg para cancelar despues
        venta_cancelar = api_create_sale(client, h,
            customer_id=s["cliente_a"].id, warehouse_id=bp,
            lines=[{"material_id": s["chatarra"].id, "quantity": 300, "unit_price": 160}],
            auto_liquidate=True, immediate_collection=True, collection_account_id=s["bancolombia"].id,
            date=TODAY,
        )

        # Op 26: Cancelar esa venta — revenue y COGS deben revertir
        from tests.integration_helpers import api_cancel_sale
        api_cancel_sale(client, h, venta_cancelar["id"])

        # Op 27: Capital return $100K al socio
        api_money_movement(client, h, "capital-return", {
            "investor_id": s["inversor"].id, "amount": 100_000,
            "account_id": s["bancolombia"].id, "date": f"{TODAY}T12:00:00",
            "description": "Retiro parcial capital",
        })

        # Op 28: Venta COBRE con received_quantity (bascula)
        # 50kg × $850, pero cliente recibe 47kg → total = 47 × $850
        venta_recv = api_create_sale(client, h,
            customer_id=s["cliente_e"].id, warehouse_id=bp,
            lines=[{"material_id": s["cobre"].id, "quantity": 50, "unit_price": 850}],
            date=TODAY,
        )
        resp_liq_recv = client.patch(f"/api/v1/sales/{venta_recv['id']}/liquidate", json={
            "lines": [{"line_id": venta_recv["lines"][0]["id"], "unit_price": 850, "received_quantity": 47}],
            "immediate_collection": True,
            "collection_account_id": str(s["bancolombia"].id),
        }, headers=h)
        assert resp_liq_recv.status_code == 200

        # Op 29: Crear activo $3M, tasa 2.5%, residual $300K
        asset = api_create_fixed_asset(client, h, {
            "name": "Bascula Industrial",
            "purchase_date": "2026-03-01", "purchase_value": 3_000_000,
            "salvage_value": 300_000, "depreciation_rate": 2.5,
            "depreciation_start_date": "2026-03-01",
            "expense_category_id": str(s["cat_depreciacion"].id),
            "source_account_id": str(s["bancolombia"].id),
        })
        asset_id = asset["id"]

        # Op 25: Depreciar marzo 2026
        api_apply_pending_depreciations(client, h)
        # monthly = $3M × 2.5% = $75K

        # Op 26: Crear gasto diferido $12K / 12 meses
        scheduled = api_create_scheduled_expense(client, h, {
            "name": "Seguro anual", "total_amount": 12_000, "total_months": 12,
            "source_account_id": s["bancolombia"].id,
            "expense_category_id": s["cat_servicios"].id,
            "start_date": "2026-03-01", "apply_day": 15,
        })

        # Op 27: Aplicar 1 cuota diferido ($1K)
        api_apply_scheduled_expense(client, h, scheduled["id"])

        # Op 28: Ajuste increase CHATARRA +100kg @ $90
        api_create_adjustment(client, h,
            adjustment_type="increase", material_id=s["chatarra"].id,
            warehouse_id=bp, quantity=100, unit_cost=90,
            reason="Material encontrado", date="2026-03-19",
        )

        # Op 29: Ajuste decrease COBRE -10kg
        api_create_adjustment(client, h,
            adjustment_type="decrease", material_id=s["cobre"].id,
            warehouse_id=bp, quantity=10,
            reason="Merma almacenamiento", date="2026-03-19",
        )

        # Op 30: Pago comisión $3,200 al comisionista
        api_money_movement(client, h, "commission-payment", {
            "third_party_id": s["comisionista"].id, "amount": 3_200,
            "account_id": s["bancolombia"].id, "date": "2026-03-19T12:00:00",
            "description": "Pago comision venta COBRE",
        })

        # Op 31: Anular gasto compartido $12K (op 13)
        api_annul_movement(client, h, gasto_compartido_id, "Error en asignacion")

        # Op 32: Pago genérico $2K desde Caja
        api_money_movement(client, h, "payment-to-generic", {
            "account_id": s["caja"].id, "third_party_id": s["generic_tp"].id,
            "amount": 2_000, "date": "2026-03-19T12:00:00", "description": "Pago varios",
        })

        # Op 33: Cobro genérico $1K a Caja
        api_money_movement(client, h, "collection-from-generic", {
            "account_id": s["caja"].id, "third_party_id": s["generic_tp"].id,
            "amount": 1_000, "date": "2026-03-19T12:00:00", "description": "Cobro pendiente",
        })

        # Op 34: Ajuste pérdida — anticipo proveedor local $50K irrecuperable
        resp_adj_loss = client.post("/api/v1/money-movements/tp-adjustment-debit", json={
            "third_party_id": str(s["proveedor_local"].id),
            "amount": 50_000,
            "adjustment_class": "loss",
            "date": "2026-03-19T12:00:00",
            "description": "Anticipo irrecuperable",
        }, headers=h)
        assert resp_adj_loss.status_code == 201

        # Op 35: Ajuste ganancia — comisionista no reclamó $2,500
        resp_adj_gain = client.post("/api/v1/money-movements/tp-adjustment-credit", json={
            "third_party_id": str(s["comisionista"].id),
            "amount": 2_500,
            "adjustment_class": "gain",
            "date": "2026-03-19T12:00:00",
            "description": "Comision no reclamada",
        }, headers=h)
        assert resp_adj_gain.status_code == 201

        # Op 36: Distribución de utilidades $50K al socio
        api_create_profit_distribution(client, h, {
            "date": "2026-03-19T12:00:00",
            "lines": [{"third_party_id": str(s["inversor"].id), "amount": 50_000}],
        })

        # =================================================================
        # CHECKPOINT 4 — ACID TESTS FINALES (exhaustivo)
        # =================================================================

        # --- Terceros: valores exactos ---
        # Inversor: -$5M(capital) + $100K(return) - $50K(distribucion) = -$4,950K
        assert_tp_balance(client, h, str(s["inversor"].id), -4_950_000)
        assert_tp_balance(client, h, str(s["proveedor_local"].id), 0)  # anticipo $50K ajustado como pérdida
        # Proveedor directo: compra cobre pagada + compra chatarra per_kg pagada = 0
        assert_tp_balance(client, h, str(s["proveedor_directo"].id), 0)
        # Cliente A: -$30K(anticipo) + venta cancelada (cobro no revertido) = cobro de venta cancelada incluido
        # Cliente E: DP cancelada ($0) + venta received_qty cobrada ($0)
        assert_tp_balance(client, h, str(s["cliente_e"].id), 0)
        # Comisionista: -$3.2K(venta) - $2.5K(per_kg compra) + $3.2K(pago) - $2.5K + $2.5K(adj gain) = 0
        assert_tp_balance(client, h, str(s["comisionista"].id), 0)
        assert_tp_balance(client, h, str(s["liability_tp"].id), 0)
        assert_tp_balance(client, h, str(s["provision_tp"].id), -15_000)
        assert_tp_balance(client, h, str(s["generic_tp"].id), 1_000)

        # --- Cuentas: obtener saldos reales para verificaciones cruzadas ---
        c1_resp = client.get(f"/api/v1/money-accounts/{s['bancolombia'].id}", headers=h)
        c2_resp = client.get(f"/api/v1/money-accounts/{s['caja'].id}", headers=h)
        cash_bancolombia = c1_resp.json()["current_balance"]
        cash_caja = c2_resp.json()["current_balance"]
        cash_total = cash_bancolombia + cash_caja

        # --- P&L completo ---
        pnl_resp = client.get("/api/v1/reports/profit-and-loss",
            params={"date_from": DATE_FROM, "date_to": DATE_TO}, headers=h)
        pnl = pnl_resp.json()

        # Ventas activas (cancelada NO aparece):
        # Chatarra 800×$150=$120K + Cobre 200×$800=$160K + Cobre 120×$900=$108K + Cobre 47×$850=$39,950
        assert pnl["sales_revenue"] == pytest.approx(427_950, abs=1)
        # DP cancelada
        assert pnl["double_entry_profit"] == pytest.approx(0, abs=1)
        assert pnl["service_income"] == pytest.approx(5_000, abs=1)
        assert pnl["waste_loss"] == pytest.approx(4_000, abs=1)
        # Comisiones causadas: solo venta cobre $3.2K (DP cancelada, per_kg no genera accrual)
        assert pnl["commissions_paid"] == pytest.approx(3_200, abs=1)

        # Ajustes de terceros presentes
        assert pnl["tp_adjustment_loss"] == pytest.approx(50_000, abs=1)
        assert pnl["tp_adjustment_gain"] == pytest.approx(2_500, abs=1)

        # net_profit formula cuadra
        expected_net = (
            pnl["sales_revenue"] - pnl["cost_of_goods_sold"]
            + pnl["double_entry_profit"] + pnl["service_income"]
            + pnl.get("transformation_profit", 0)
            - pnl["waste_loss"] + pnl["adjustment_net"]
            + pnl["tp_adjustment_gain"] - pnl["tp_adjustment_loss"]
            - pnl["operating_expenses"] - pnl["commissions_paid"]
        )
        assert pnl["net_profit"] == pytest.approx(expected_net, abs=1), \
            f"P&L formula mismatch: net={pnl['net_profit']}, expected={expected_net}"

        # --- Balance Sheet ---
        bs = client.get("/api/v1/reports/balance-sheet", headers=h).json()

        # Cash == sum(cuentas)
        assert bs["assets"]["cash_and_bank"] == pytest.approx(cash_total, abs=1)

        # Inventory == sum(material.stock × avg_cost)
        mat_ch = client.get(f"/api/v1/materials/{s['chatarra'].id}", headers=h).json()
        mat_cu = client.get(f"/api/v1/materials/{s['cobre'].id}", headers=h).json()
        mat_mo = client.get(f"/api/v1/materials/{s['motor'].id}", headers=h).json()
        inv_value = (
            mat_ch["current_stock_liquidated"] * mat_ch["current_average_cost"]
            + mat_cu["current_stock_liquidated"] * mat_cu["current_average_cost"]
            + mat_mo["current_stock_liquidated"] * mat_mo["current_average_cost"]
        )
        assert bs["assets"]["inventory"] == pytest.approx(inv_value, abs=1), \
            f"BS inventory ({bs['assets']['inventory']}) != calculated ({inv_value})"

        # Ecuacion contable: assets - liabilities == equity
        assert bs["total_assets"] - bs["total_liabilities"] == pytest.approx(bs["equity"], abs=1), \
            f"Accounting eq: {bs['total_assets']} - {bs['total_liabilities']} != {bs['equity']}"

        # accumulated_profit == P&L net_profit
        assert bs["accumulated_profit"] == pytest.approx(pnl["net_profit"], abs=1)

        # Distribucion
        assert bs["distributed_profit"] == pytest.approx(50_000, abs=1)

        # equity = accumulated - distributed
        assert bs["equity"] == pytest.approx(bs["accumulated_profit"] - bs["distributed_profit"], abs=1)

        # --- Cash Flow ---
        cf = client.get("/api/v1/reports/cash-flow",
            params={"date_from": DATE_FROM, "date_to": DATE_TO}, headers=h).json()

        # Closing == sum(cuentas)
        assert cf["closing_balance"] == pytest.approx(cash_total, abs=1)
        # Opening + net == closing
        assert cf["opening_balance"] + cf["net_flow"] == pytest.approx(cf["closing_balance"], abs=1)
        # net_flow == inflows - outflows
        assert cf["net_flow"] == pytest.approx(cf["total_inflows"] - cf["total_outflows"], abs=1)

        # --- Rentabilidad por UN ---
        bu_resp = client.get(
            "/api/v1/reports/profitability-by-business-unit",
            params={"date_from": DATE_FROM, "date_to": DATE_TO}, headers=h,
        )
        assert bu_resp.status_code == 200
        bus = {bu["business_unit_name"]: bu for bu in bu_resp.json()["business_units"]}

        assert "Chatarra" in bus, f"UN 'Chatarra' missing. UNs: {list(bus.keys())}"
        assert "No Ferrosos" in bus, f"UN 'No Ferrosos' missing. UNs: {list(bus.keys())}"

        ch = bus["Chatarra"]
        nf = bus["No Ferrosos"]

        # Chatarra: compra original $200K + compra per_kg $60K = $260K
        # Ventas: 800×$150=$120K (cancelada no aparece)
        assert ch["purchases_total"] == pytest.approx(260_000, abs=100)
        assert ch["sales_revenue"] == pytest.approx(120_000, abs=100)
        assert ch["direct_expenses"] == pytest.approx(15_000, abs=100)

        # No Ferrosos: compra $250K
        # Ventas: 200×$800 + 120×$900 + 47×$850 = $160K + $108K + $39.95K = $307.95K
        assert nf["purchases_total"] == pytest.approx(250_000, abs=100)
        assert nf["sales_revenue"] == pytest.approx(307_950, abs=100)
        assert nf["sale_commissions"] == pytest.approx(3_200, abs=10)

        # Delta P&L vs sum(UNs) = conceptos sin UN
        total_un_profit = sum(bu["net_profit"] for bu in bus.values())
        delta = pnl["net_profit"] - total_un_profit
        total_un_expenses = sum(
            b["direct_expenses"] + b["shared_expenses"] + b["general_expenses"]
            for b in bus.values()
        )
        expenses_without_un = pnl["operating_expenses"] - total_un_expenses
        expected_delta = (
            pnl.get("service_income", 0)
            - pnl.get("waste_loss", 0)
            + pnl.get("adjustment_net", 0)
            + pnl.get("transformation_profit", 0)
            + pnl.get("tp_adjustment_gain", 0)
            - pnl.get("tp_adjustment_loss", 0)
            - expenses_without_un
        )
        assert delta == pytest.approx(expected_delta, abs=10), \
            f"Delta P&L-UNs ({delta}) != expected ({expected_delta})"

        # --- Costo Real por Material ---
        rc_resp = client.get("/api/v1/reports/real-cost-by-material",
            params={"date_from": DATE_FROM, "date_to": DATE_TO}, headers=h)
        assert rc_resp.status_code == 200
        rc_bus = {bu["business_unit_name"]: bu for bu in rc_resp.json()["business_units"]}
        # Cada UN con actividad debe tener overhead_rate calculado
        for un_name in ["Chatarra", "No Ferrosos"]:
            assert un_name in rc_bus, f"Real cost missing UN '{un_name}'"
            assert rc_bus[un_name]["kg_purchased"] > 0
            assert rc_bus[un_name]["overhead_rate"] >= 0
            for mat in rc_bus[un_name]["materials"]:
                assert mat["real_cost"] >= mat["average_cost"], \
                    f"{mat['material_name']}: real_cost ({mat['real_cost']}) < avg_cost ({mat['average_cost']})"

        # === THE ULTIMATE ACID TEST ===
        assert_pnl_equals_balance(client, h)
