"""
Escenario 5: Tesoreria — Stress Test Completo.

Cubre 15+ tipos de MoneyMovement:
- capital_injection, capital_return
- expense (directo e indirecto), expense_accrual
- supplier-payment (a liability)
- provision-deposit, provision-expense
- transfer (par linked)
- service_income
- advance_payment, advance_collection
- commission_payment
- payment_to_generic, collection_from_generic
- Anulacion + verificar P&L se ajusta
- Multiples cuentas, Cash Flow closing == sum(cuentas)
- P&L == Balance Sheet acid test
"""
import pytest
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    TODAY, DATE_FROM, DATE_TO,
    create_account, create_expense_category,
    api_money_movement, api_annul_movement,
    assert_account_balance, assert_tp_balance,
    assert_pnl, assert_cash_flow, assert_pnl_equals_balance,
)


@pytest.fixture
def scenario(db_session, test_organization):
    org_id = test_organization.id
    cuenta_1 = create_account(db_session, org_id, "Bancolombia INT05", balance=0)
    cuenta_2 = create_account(db_session, org_id, "Caja INT05", balance=0)
    cat_directo = create_expense_category(db_session, org_id, "Flete INT05", is_direct=True)
    cat_indirecto = create_expense_category(db_session, org_id, "Admin INT05", is_direct=False)

    investor = create_third_party_with_category(db_session, org_id, "Socio INT05", "investor")
    supplier = create_third_party_with_category(db_session, org_id, "Proveedor INT05", "material_supplier")
    customer = create_third_party_with_category(db_session, org_id, "Cliente INT05", "customer")
    comisionista = create_third_party_with_category(db_session, org_id, "Comisionista INT05", "service_provider")
    liability = create_third_party_with_category(db_session, org_id, "Pasivo INT05", "liability")
    provision = create_third_party_with_category(db_session, org_id, "Provision INT05", "provision")
    generic = create_third_party_with_category(db_session, org_id, "Varios INT05", "generic")

    db_session.commit()
    return {
        "cuenta_1": cuenta_1, "cuenta_2": cuenta_2,
        "cat_directo": cat_directo, "cat_indirecto": cat_indirecto,
        "investor": investor, "supplier": supplier, "customer": customer,
        "comisionista": comisionista, "liability": liability,
        "provision": provision, "generic": generic,
    }


class TestTreasuryStress:

    def test_treasury_full_stress(self, client, org_headers, scenario):
        s = scenario
        h = org_headers
        c1 = str(s["cuenta_1"].id)
        c2 = str(s["cuenta_2"].id)

        # =================================================================
        # 1. Capital injection $1M → Bancolombia
        # =================================================================
        api_money_movement(client, h, "capital-injection", {
            "investor_id": s["investor"].id, "amount": 1_000_000,
            "account_id": s["cuenta_1"].id, "date": f"{TODAY}T12:00:00",
            "description": "Aporte capital",
        })
        assert_account_balance(client, h, c1, 1_000_000)
        assert_tp_balance(client, h, str(s["investor"].id), -1_000_000)

        # =================================================================
        # 2. Transfer $200K Bancolombia → Caja
        # =================================================================
        api_money_movement(client, h, "transfer", {
            "amount": 200_000, "source_account_id": s["cuenta_1"].id,
            "destination_account_id": s["cuenta_2"].id,
            "date": f"{TODAY}T12:00:00", "description": "Fondeo caja",
        })
        assert_account_balance(client, h, c1, 800_000)
        assert_account_balance(client, h, c2, 200_000)

        # =================================================================
        # 3. Expense directo $10K desde Bancolombia
        # =================================================================
        api_money_movement(client, h, "expense", {
            "amount": 10_000, "expense_category_id": s["cat_directo"].id,
            "account_id": s["cuenta_1"].id, "date": f"{TODAY}T12:00:00",
            "description": "Flete",
        })
        assert_account_balance(client, h, c1, 790_000)

        # =================================================================
        # 4. Expense indirecto $5K desde Caja
        # =================================================================
        api_money_movement(client, h, "expense", {
            "amount": 5_000, "expense_category_id": s["cat_indirecto"].id,
            "account_id": s["cuenta_2"].id, "date": f"{TODAY}T12:00:00",
            "description": "Papeleria",
        })
        assert_account_balance(client, h, c2, 195_000)

        # =================================================================
        # 5. Expense accrual $8K (pasivo, sin cuenta)
        # =================================================================
        api_money_movement(client, h, "expense-accrual", {
            "third_party_id": s["liability"].id, "amount": 8_000,
            "expense_category_id": s["cat_indirecto"].id,
            "date": f"{TODAY}T12:00:00", "description": "Servicio causado",
        })
        assert_tp_balance(client, h, str(s["liability"].id), -8_000)

        # =================================================================
        # 6. Pago pasivo $8K desde Bancolombia
        # =================================================================
        api_money_movement(client, h, "supplier-payment", {
            "supplier_id": s["liability"].id, "amount": 8_000,
            "account_id": s["cuenta_1"].id, "date": f"{TODAY}T12:00:00",
            "description": "Pago pasivo",
        })
        assert_account_balance(client, h, c1, 782_000)
        assert_tp_balance(client, h, str(s["liability"].id), 0)

        # =================================================================
        # 7. Provision deposit $30K + provision expense $5K
        # =================================================================
        api_money_movement(client, h, "provision-deposit", {
            "provision_id": s["provision"].id, "amount": 30_000,
            "account_id": s["cuenta_1"].id, "date": f"{TODAY}T12:00:00",
            "description": "Fondeo provision",
        })
        assert_account_balance(client, h, c1, 752_000)
        assert_tp_balance(client, h, str(s["provision"].id), -30_000)

        api_money_movement(client, h, "provision-expense", {
            "provision_id": s["provision"].id, "amount": 5_000,
            "expense_category_id": s["cat_directo"].id,
            "date": f"{TODAY}T12:00:00", "description": "Gasto provision",
        })
        assert_tp_balance(client, h, str(s["provision"].id), -25_000)

        # =================================================================
        # 8. Service income $12K → Bancolombia
        # =================================================================
        api_money_movement(client, h, "service-income", {
            "account_id": s["cuenta_1"].id, "amount": 12_000,
            "date": f"{TODAY}T12:00:00", "description": "Servicio pesaje",
        })
        assert_account_balance(client, h, c1, 764_000)

        # =================================================================
        # 9. Advance payment $15K a proveedor desde Bancolombia
        # =================================================================
        api_money_movement(client, h, "advance-payment", {
            "supplier_id": s["supplier"].id, "amount": 15_000,
            "account_id": s["cuenta_1"].id, "date": f"{TODAY}T12:00:00",
            "description": "Anticipo proveedor",
        })
        assert_account_balance(client, h, c1, 749_000)
        assert_tp_balance(client, h, str(s["supplier"].id), 15_000)  # nos debe

        # =================================================================
        # 10. Advance collection $7K de cliente a Caja
        # =================================================================
        api_money_movement(client, h, "advance-collection", {
            "customer_id": s["customer"].id, "amount": 7_000,
            "account_id": s["cuenta_2"].id, "date": f"{TODAY}T12:00:00",
            "description": "Anticipo cliente",
        })
        assert_account_balance(client, h, c2, 202_000)
        assert_tp_balance(client, h, str(s["customer"].id), -7_000)  # le debemos

        # =================================================================
        # 11. Commission payment $3K al comisionista
        # =================================================================
        # Primero darle saldo al comisionista (simulando que hay comision pendiente)
        # No hay forma directa, pero commission_payment acepta cualquier service_provider
        api_money_movement(client, h, "commission-payment", {
            "third_party_id": s["comisionista"].id, "amount": 3_000,
            "account_id": s["cuenta_1"].id, "date": f"{TODAY}T12:00:00",
            "description": "Pago comision",
        })
        assert_account_balance(client, h, c1, 746_000)
        assert_tp_balance(client, h, str(s["comisionista"].id), 3_000)

        # =================================================================
        # 12. Capital return $50K al socio
        # =================================================================
        api_money_movement(client, h, "capital-return", {
            "investor_id": s["investor"].id, "amount": 50_000,
            "account_id": s["cuenta_1"].id, "date": f"{TODAY}T12:00:00",
            "description": "Retiro parcial capital",
        })
        assert_account_balance(client, h, c1, 696_000)
        assert_tp_balance(client, h, str(s["investor"].id), -950_000)

        # =================================================================
        # 13. Payment to generic $4K + Collection from generic $2K
        # =================================================================
        api_money_movement(client, h, "payment-to-generic", {
            "account_id": s["cuenta_2"].id, "third_party_id": s["generic"].id,
            "amount": 4_000, "date": f"{TODAY}T12:00:00", "description": "Pago varios",
        })
        assert_account_balance(client, h, c2, 198_000)
        assert_tp_balance(client, h, str(s["generic"].id), 4_000)

        api_money_movement(client, h, "collection-from-generic", {
            "account_id": s["cuenta_2"].id, "third_party_id": s["generic"].id,
            "amount": 2_000, "date": f"{TODAY}T12:00:00", "description": "Cobro varios",
        })
        assert_account_balance(client, h, c2, 200_000)
        assert_tp_balance(client, h, str(s["generic"].id), 2_000)

        # =================================================================
        # 14. Gasto para ANULAR — $6K indirecto
        # =================================================================
        gasto_anular = api_money_movement(client, h, "expense", {
            "amount": 6_000, "expense_category_id": s["cat_indirecto"].id,
            "account_id": s["cuenta_1"].id, "date": f"{TODAY}T12:00:00",
            "description": "Gasto a anular",
        })
        assert_account_balance(client, h, c1, 690_000)

        # Anular
        api_annul_movement(client, h, gasto_anular["id"], "Error de clasificacion")
        assert_account_balance(client, h, c1, 696_000)  # revertido

        # Anular ya anulado → 400
        resp_double = client.post(f"/api/v1/money-movements/{gasto_anular['id']}/annul",
            json={"reason": "otra vez"}, headers=h)
        assert resp_double.status_code == 400

        # =================================================================
        # VERIFICACIONES
        # =================================================================

        # P&L: operating_expenses = $10K(directo) + $5K(indirecto) + $8K(accrual) + $5K(provision) = $28K
        #       commission_payment NO aparece en P&L (solo tesoreria, no gasto operativo)
        #       commissions_paid = $0 (solo commission_accrual cuenta, no hay ventas/DPs en este test)
        #       gasto anulado NO aparece
        #       service_income = $12K
        #       net = $12K - $28K = -$16K
        assert_pnl(client, h,
            service_income=12_000,
            operating_expenses=28_000,
            commissions_paid=0,
            net_profit=-16_000,
        )

        # Cash Flow: closing == sum(Bancolombia + Caja) = $696K + $200K = $896K
        assert_cash_flow(client, h, closing_balance=896_000)

        # Opening + net == closing
        cf_resp = client.get("/api/v1/reports/cash-flow",
            params={"date_from": DATE_FROM, "date_to": DATE_TO}, headers=h)
        cf = cf_resp.json()
        assert cf["opening_balance"] + cf["net_flow"] == pytest.approx(cf["closing_balance"], abs=1)

        # =================================================================
        # ACID TEST
        # =================================================================
        assert_pnl_equals_balance(client, h)
