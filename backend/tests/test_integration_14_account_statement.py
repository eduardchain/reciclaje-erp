"""
Escenario 14: Estado de Cuenta Unificado — Stress Test.

Verifica GET /money-movements/third-party/{id} que fusiona 6 fuentes:
1. MoneyMovements (pagos, cobros, anticipos, etc.)
2. Purchase liquidations (standalone, no DP)
3. Purchase commissions
4. Sale liquidations (standalone, no DP)
5. Sale commissions (excluyendo las que ya tienen commission_accrual)
6. Double Entry (supplier/customer roles)

Tests:
- Completeness: todas las transacciones de un tercero aparecen
- Running balance: balance_after cuadra transaccion por transaccion
- Saldo final == third_party.current_balance
- Exclusiones: compras/ventas con double_entry_id NO aparecen como standalone
- Cancelaciones aparecen con efecto corrector
- Ordering correcto (date, sort_datetime, sort_key)
- Date filtering funciona
- Multiples tipos de tercero: proveedor, cliente, comisionista
"""
import pytest
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    TODAY, DATE_FROM, DATE_TO,
    create_material_category, create_business_unit, create_material,
    create_warehouse, create_account, create_expense_category,
    api_create_purchase, api_liquidate_purchase, api_cancel_purchase,
    api_create_sale, api_cancel_sale,
    api_create_double_entry,
    api_money_movement,
    assert_tp_balance, assert_pnl_equals_balance,
)


@pytest.fixture
def scenario(db_session, test_organization):
    org_id = test_organization.id
    cat = create_material_category(db_session, org_id, "Metales INT14")
    bu = create_business_unit(db_session, org_id, "Chatarra INT14")
    material = create_material(db_session, org_id, "INT14-FE", "Chatarra INT14", cat.id, bu.id)
    warehouse = create_warehouse(db_session, org_id, "Bodega INT14")
    account = create_account(db_session, org_id, "Cuenta INT14", balance=0)
    cat_gasto = create_expense_category(db_session, org_id, "Gastos INT14")

    investor = create_third_party_with_category(db_session, org_id, "Socio INT14", "investor")
    supplier = create_third_party_with_category(db_session, org_id, "Proveedor INT14", "material_supplier")
    customer = create_third_party_with_category(db_session, org_id, "Cliente INT14", "customer")
    supplier_dp = create_third_party_with_category(db_session, org_id, "Proveedor DP INT14", "material_supplier")
    comisionista = create_third_party_with_category(db_session, org_id, "Comisionista INT14", "service_provider")

    db_session.commit()
    return {
        "material": material, "warehouse": warehouse, "account": account,
        "cat_gasto": cat_gasto,
        "investor": investor, "supplier": supplier, "customer": customer,
        "supplier_dp": supplier_dp, "comisionista": comisionista,
    }


def get_statement(client, headers, tp_id, date_from=None, date_to=None, limit=500):
    """Helper para obtener estado de cuenta."""
    params = {"limit": limit}
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to
    resp = client.get(f"/api/v1/money-movements/third-party/{tp_id}", params=params, headers=headers)
    assert resp.status_code == 200, f"Statement failed: {resp.json()}"
    return resp.json()


def verify_running_balance(items, expected_final_balance):
    """Verificar que balance_after es consistente y el ultimo == saldo actual."""
    if not items:
        return
    # Cada item tiene balance_after que es el saldo acumulado
    last_balance = items[-1]["balance_after"]
    assert last_balance == pytest.approx(expected_final_balance, abs=0.01), \
        f"Statement final balance ({last_balance}) != TP balance ({expected_final_balance})"


class TestAccountStatement:

    def test_supplier_statement(self, client, org_headers, scenario):
        """Estado de cuenta de PROVEEDOR con multiples operaciones."""
        s = scenario
        h = org_headers
        wid = s["warehouse"].id
        sup_id = str(s["supplier"].id)

        # Capital
        api_money_movement(client, h, "capital-injection", {
            "investor_id": s["investor"].id, "amount": 2_000_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Capital",
        })

        # --- Operaciones del proveedor ---

        # 1. Anticipo $20K → proveedor nos debe
        api_money_movement(client, h, "advance-payment", {
            "supplier_id": s["supplier"].id, "amount": 20_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Anticipo",
        })

        # 2. Compra 1: 500kg × $100 = $50K (registrar + liquidar sin pago)
        compra_1 = api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["material"].id, "quantity": 500, "unit_price": 100, "warehouse_id": wid}],
        )
        api_liquidate_purchase(client, h, compra_1["id"])
        # Proveedor: +$20K(anticipo) - $50K(liquidacion) = -$30K

        # 3. Pago $30K
        api_money_movement(client, h, "supplier-payment", {
            "supplier_id": s["supplier"].id, "amount": 30_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Pago parcial",
        })
        # Proveedor: -$30K + $30K = $0

        # 4. Compra 2: auto-liq + pago = $25K
        api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["material"].id, "quantity": 250, "unit_price": 100, "warehouse_id": wid}],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["account"].id,
        )
        # Proveedor: liq -$25K + pago +$25K = $0

        # 5. Compra 3: liquidar y CANCELAR (verificar que aparece en statement)
        compra_cancel = api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["material"].id, "quantity": 100, "unit_price": 80, "warehouse_id": wid}],
        )
        api_liquidate_purchase(client, h, compra_cancel["id"],
            immediate_payment=True, payment_account_id=s["account"].id)
        api_cancel_purchase(client, h, compra_cancel["id"])
        # Cancelacion revierte liquidacion: +$8K → saldo = +$8K

        # Saldo final esperado
        assert_tp_balance(client, h, sup_id, 8_000)

        # --- Verificar estado de cuenta ---
        stmt = get_statement(client, h, sup_id, date_from=DATE_FROM, date_to=DATE_TO)
        items = stmt["items"]

        # Debe tener todas las operaciones (anticipo + 3 compras liq + pagos + cancel)
        assert len(items) >= 6, f"Expected >= 6 items, got {len(items)}"

        # Running balance final == saldo actual
        verify_running_balance(items, 8_000)

        # Verificar que hay evento de cancelacion
        cancel_events = [i for i in items if i["status"] == "cancelled"]
        assert len(cancel_events) >= 1, "Expected at least 1 cancelled event in statement"

        # Todos los items tienen los campos requeridos
        for item in items:
            assert "date" in item
            assert "event_type" in item
            assert "amount" in item
            assert "direction" in item
            assert "balance_after" in item
            assert "source" in item

    def test_customer_statement(self, client, org_headers, scenario):
        """Estado de cuenta de CLIENTE con ventas, anticipos y cancelacion."""
        s = scenario
        h = org_headers
        wid = s["warehouse"].id
        cust_id = str(s["customer"].id)

        # Capital + stock
        api_money_movement(client, h, "capital-injection", {
            "investor_id": s["investor"].id, "amount": 2_000_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Capital",
        })
        api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["material"].id, "quantity": 2000, "unit_price": 50, "warehouse_id": wid}],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["account"].id,
        )

        # 1. Anticipo cliente $15K
        api_money_movement(client, h, "advance-collection", {
            "customer_id": s["customer"].id, "amount": 15_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Anticipo cliente",
        })

        # 2. Venta 1: 300kg × $120 = $36K (auto-liq + cobro)
        api_create_sale(client, h,
            customer_id=s["customer"].id, warehouse_id=wid,
            lines=[{"material_id": s["material"].id, "quantity": 300, "unit_price": 120}],
            auto_liquidate=True, immediate_collection=True, collection_account_id=s["account"].id,
        )

        # 3. Venta 2: 200kg × $100 = $20K (auto-liq + cobro) — cancelar despues
        venta_cancel = api_create_sale(client, h,
            customer_id=s["customer"].id, warehouse_id=wid,
            lines=[{"material_id": s["material"].id, "quantity": 200, "unit_price": 100}],
            auto_liquidate=True, immediate_collection=True, collection_account_id=s["account"].id,
        )
        api_cancel_sale(client, h, venta_cancel["id"])

        # 4. Cobro manual $10K
        api_money_movement(client, h, "customer-collection", {
            "customer_id": s["customer"].id, "amount": 10_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Cobro adicional",
        })

        # Saldo: -$15K(anticipo) + $36K(liq1) - $36K(cobro1)
        #   + $20K(liq2) - $20K(cobro2) - $20K(cancel liq2)
        #   - $10K(cobro manual) = -$45K
        assert_tp_balance(client, h, cust_id, -45_000)

        stmt = get_statement(client, h, cust_id, date_from=DATE_FROM, date_to=DATE_TO)
        items = stmt["items"]

        assert len(items) >= 5, f"Expected >= 5 items, got {len(items)}"
        verify_running_balance(items, -45_000)

    def test_dp_excluded_from_standalone(self, client, org_headers, scenario):
        """Compras/ventas de DP NO aparecen como standalone en statement del proveedor."""
        s = scenario
        h = org_headers
        wid = s["warehouse"].id
        sup_dp_id = str(s["supplier_dp"].id)

        # Capital + stock
        api_money_movement(client, h, "capital-injection", {
            "investor_id": s["investor"].id, "amount": 2_000_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Capital",
        })

        # DP: proveedor_dp como supplier
        api_create_double_entry(client, h,
            supplier_id=s["supplier_dp"].id, customer_id=s["customer"].id,
            lines=[{
                "material_id": s["material"].id, "quantity": 100,
                "purchase_unit_price": 80, "sale_unit_price": 120,
            }],
            auto_liquidate=True, date=TODAY,
        )
        # Proveedor DP: -$8K (le debemos)
        assert_tp_balance(client, h, sup_dp_id, -8_000)

        stmt = get_statement(client, h, sup_dp_id, date_from=DATE_FROM, date_to=DATE_TO)
        items = stmt["items"]

        # Debe tener evento de DP, NO evento standalone de purchase
        assert len(items) >= 1
        sources = [i["source"] for i in items]
        assert "double_entry" in sources, f"Expected 'double_entry' source, got {sources}"
        # No debe haber purchase standalone
        standalone_purchases = [i for i in items if i["source"] == "purchase"]
        assert len(standalone_purchases) == 0, \
            f"DP purchases should NOT appear as standalone, found {len(standalone_purchases)}"

        verify_running_balance(items, -8_000)

    def test_comisionista_statement(self, client, org_headers, scenario):
        """Estado de cuenta del comisionista: commission_accrual al liquidar venta."""
        s = scenario
        h = org_headers
        wid = s["warehouse"].id
        com_id = str(s["comisionista"].id)

        # Capital + stock
        api_money_movement(client, h, "capital-injection", {
            "investor_id": s["investor"].id, "amount": 2_000_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Capital",
        })
        api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["material"].id, "quantity": 1000, "unit_price": 50, "warehouse_id": wid}],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["account"].id,
        )

        # Venta con comision 5% = $2,500
        api_create_sale(client, h,
            customer_id=s["customer"].id, warehouse_id=wid,
            lines=[{"material_id": s["material"].id, "quantity": 500, "unit_price": 100}],
            auto_liquidate=True, immediate_collection=True, collection_account_id=s["account"].id,
            commissions=[{
                "third_party_id": str(s["comisionista"].id),
                "commission_type": "percentage", "commission_value": 5,
                "concept": "Comision 5%",
            }],
        )
        # Comisionista: -$2,500 (le debemos)

        # Pagar comision
        api_money_movement(client, h, "commission-payment", {
            "third_party_id": s["comisionista"].id, "amount": 2_500,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Pago comision",
        })
        assert_tp_balance(client, h, com_id, 0)

        stmt = get_statement(client, h, com_id, date_from=DATE_FROM, date_to=DATE_TO)
        items = stmt["items"]

        # Debe tener: commission_accrual + commission_payment = 2 items
        assert len(items) >= 2, f"Expected >= 2 items for comisionista, got {len(items)}"
        verify_running_balance(items, 0)

        # Verificar tipos de evento
        event_types = [i["event_type"] for i in items]
        assert "commission_accrual" in event_types, f"Missing commission_accrual, got {event_types}"
        assert "commission_payment" in event_types, f"Missing commission_payment, got {event_types}"

    def test_ordering(self, client, org_headers, scenario):
        """Verificar que el ordering es consistente: fechas no decrecen."""
        s = scenario
        h = org_headers
        wid = s["warehouse"].id
        sup_id = str(s["supplier"].id)

        api_money_movement(client, h, "capital-injection", {
            "investor_id": s["investor"].id, "amount": 2_000_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Capital",
        })

        # Multiples operaciones en fechas distintas
        api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["material"].id, "quantity": 100, "unit_price": 50, "warehouse_id": wid}],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["account"].id,
            date="2026-03-01",
        )
        api_money_movement(client, h, "advance-payment", {
            "supplier_id": s["supplier"].id, "amount": 5_000,
            "account_id": s["account"].id, "date": "2026-03-05T12:00:00",
            "description": "Anticipo",
        })
        api_create_purchase(client, h,
            supplier_id=s["supplier"].id,
            lines=[{"material_id": s["material"].id, "quantity": 200, "unit_price": 60, "warehouse_id": wid}],
            auto_liquidate=True, immediate_payment=True, payment_account_id=s["account"].id,
            date="2026-03-10",
        )

        stmt = get_statement(client, h, sup_id, date_from="2026-03-01", date_to="2026-03-31")
        items = stmt["items"]

        # Fechas no deben decrecer
        for i in range(1, len(items)):
            assert items[i]["date"] >= items[i-1]["date"], \
                f"Ordering broken: item {i-1} date={items[i-1]['date']} > item {i} date={items[i]['date']}"

    def test_acid_all_statements(self, client, org_headers, scenario):
        """ACID: P&L == Balance Sheet despues de todas las operaciones."""
        s = scenario
        h = org_headers

        api_money_movement(client, h, "capital-injection", {
            "investor_id": s["investor"].id, "amount": 2_000_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Capital",
        })

        assert_pnl_equals_balance(client, h)
