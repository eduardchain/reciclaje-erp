"""
Escenario 13: Pasivos y Provisiones — Flujo Completo.

PASIVOS (liability):
- Causar multiples gastos (expense_accrual) → saldo crece
- Pago parcial → saldo reduce
- Pago total → saldo a cero
- Sobrepagar → saldo positivo (nos deben a nosotros)
- Anular expense_accrual → saldo se revierte
- Balance Sheet: liability_debt (bal < 0) y liability_advances (bal > 0)

PROVISIONES (provision):
- Depositar fondos → saldo negativo (fondos disponibles)
- Multiples gastos → saldo sube
- Fondos insuficientes → 400 (bloquea, no warning)
- Provision en sobregiro → 400
- Anular deposito → saldo se revierte
- Balance Sheet: provision_funds (bal < 0) y provision_obligations (bal > 0)

Cross-module:
- Ambos aparecen correctamente en P&L operating_expenses
- Balance Sheet cuadra con ambos modulos activos
- P&L == Balance Sheet acid test
"""
import pytest
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    TODAY, DATE_FROM, DATE_TO,
    create_account, create_expense_category,
    api_money_movement, api_annul_movement,
    assert_account_balance, assert_tp_balance,
    assert_pnl, assert_balance_sheet, assert_pnl_equals_balance,
)


@pytest.fixture
def scenario(db_session, test_organization):
    org_id = test_organization.id
    account = create_account(db_session, org_id, "Cuenta INT13", balance=0)
    cat_mant = create_expense_category(db_session, org_id, "Mantenimiento INT13", is_direct=False)
    cat_legal = create_expense_category(db_session, org_id, "Legal INT13", is_direct=False)

    investor = create_third_party_with_category(db_session, org_id, "Socio INT13", "investor")
    liability_1 = create_third_party_with_category(db_session, org_id, "Tecniservicios INT13", "liability")
    liability_2 = create_third_party_with_category(db_session, org_id, "Alquiler Maq INT13", "liability")
    provision_1 = create_third_party_with_category(db_session, org_id, "Provision Legal INT13", "provision")
    provision_2 = create_third_party_with_category(db_session, org_id, "Provision Imprevistos INT13", "provision")

    db_session.commit()
    return {
        "account": account, "cat_mant": cat_mant, "cat_legal": cat_legal,
        "investor": investor,
        "liability_1": liability_1, "liability_2": liability_2,
        "provision_1": provision_1, "provision_2": provision_2,
    }


class TestLiabilitiesAndProvisions:

    def test_full_liabilities_provisions(self, client, org_headers, scenario):
        s = scenario
        h = org_headers
        aid = str(s["account"].id)
        l1 = str(s["liability_1"].id)
        l2 = str(s["liability_2"].id)
        p1 = str(s["provision_1"].id)
        p2 = str(s["provision_2"].id)

        # Capital $500K
        api_money_movement(client, h, "capital-injection", {
            "investor_id": s["investor"].id, "amount": 500_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Capital",
        })

        # =================================================================
        # PASIVOS
        # =================================================================

        # --- Causar gastos (expense_accrual) a 2 pasivos ---
        # Liability 1: $10K + $5K = $15K
        api_money_movement(client, h, "expense-accrual", {
            "third_party_id": s["liability_1"].id, "amount": 10_000,
            "expense_category_id": s["cat_mant"].id,
            "date": f"{TODAY}T12:00:00", "description": "Mantenimiento marzo",
        })
        api_money_movement(client, h, "expense-accrual", {
            "third_party_id": s["liability_1"].id, "amount": 5_000,
            "expense_category_id": s["cat_mant"].id,
            "date": f"{TODAY}T12:00:00", "description": "Mantenimiento extra",
        })
        assert_tp_balance(client, h, l1, -15_000)  # le debemos

        # Liability 2: $8K
        api_money_movement(client, h, "expense-accrual", {
            "third_party_id": s["liability_2"].id, "amount": 8_000,
            "expense_category_id": s["cat_mant"].id,
            "date": f"{TODAY}T12:00:00", "description": "Alquiler maquinaria",
        })
        assert_tp_balance(client, h, l2, -8_000)

        # Cuenta sin cambio (accrual no toca dinero)
        assert_account_balance(client, h, aid, 500_000)

        # --- Pago parcial liability 1: $10K de $15K ---
        api_money_movement(client, h, "supplier-payment", {
            "supplier_id": s["liability_1"].id, "amount": 10_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Pago parcial mantenimiento",
        })
        assert_tp_balance(client, h, l1, -5_000)  # aun debemos $5K
        assert_account_balance(client, h, aid, 490_000)

        # --- Pago total liability 2: $8K ---
        api_money_movement(client, h, "supplier-payment", {
            "supplier_id": s["liability_2"].id, "amount": 8_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Pago total alquiler",
        })
        assert_tp_balance(client, h, l2, 0)
        assert_account_balance(client, h, aid, 482_000)

        # --- Sobrepagar liability 2: $3K adicionales ---
        # Saldo pasa a positivo (nos deben a nosotros)
        api_money_movement(client, h, "supplier-payment", {
            "supplier_id": s["liability_2"].id, "amount": 3_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Pago anticipado",
        })
        assert_tp_balance(client, h, l2, 3_000)  # nos debe
        assert_account_balance(client, h, aid, 479_000)

        # --- Anular un expense_accrual del liability 1 ($5K extra) ---
        # Primero necesitamos el ID. Buscar el ultimo expense_accrual
        accrual_anular = api_money_movement(client, h, "expense-accrual", {
            "third_party_id": s["liability_1"].id, "amount": 2_000,
            "expense_category_id": s["cat_mant"].id,
            "date": f"{TODAY}T12:00:00", "description": "Gasto a anular",
        })
        assert_tp_balance(client, h, l1, -7_000)  # -5K - 2K

        api_annul_movement(client, h, accrual_anular["id"], "Registrado por error")
        assert_tp_balance(client, h, l1, -5_000)  # vuelve a -5K

        # =================================================================
        # PROVISIONES
        # =================================================================

        # --- Depositar fondos a 2 provisiones ---
        api_money_movement(client, h, "provision-deposit", {
            "provision_id": s["provision_1"].id, "amount": 20_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Fondeo provision legal",
        })
        assert_tp_balance(client, h, p1, -20_000)  # fondos disponibles
        assert_account_balance(client, h, aid, 459_000)

        api_money_movement(client, h, "provision-deposit", {
            "provision_id": s["provision_2"].id, "amount": 10_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Fondeo provision imprevistos",
        })
        assert_tp_balance(client, h, p2, -10_000)
        assert_account_balance(client, h, aid, 449_000)

        # --- Gastos de provision ---
        # Provision 1: $8K + $5K = $13K (de $20K disponibles)
        api_money_movement(client, h, "provision-expense", {
            "provision_id": s["provision_1"].id, "amount": 8_000,
            "expense_category_id": s["cat_legal"].id,
            "date": f"{TODAY}T12:00:00", "description": "Honorarios abogado",
        })
        assert_tp_balance(client, h, p1, -12_000)  # -20K + 8K

        api_money_movement(client, h, "provision-expense", {
            "provision_id": s["provision_1"].id, "amount": 5_000,
            "expense_category_id": s["cat_legal"].id,
            "date": f"{TODAY}T12:00:00", "description": "Gastos notariales",
        })
        assert_tp_balance(client, h, p1, -7_000)  # -12K + 5K

        # Provision 2: $6K (de $10K)
        api_money_movement(client, h, "provision-expense", {
            "provision_id": s["provision_2"].id, "amount": 6_000,
            "expense_category_id": s["cat_mant"].id,
            "date": f"{TODAY}T12:00:00", "description": "Reparacion imprevista",
        })
        assert_tp_balance(client, h, p2, -4_000)

        # Cuenta sin cambio (provision_expense no toca cuenta)
        assert_account_balance(client, h, aid, 449_000)

        # --- Fondos insuficientes → 400 ---
        # Provision 2 tiene $4K, intentar gastar $5K
        resp_insuf = client.post("/api/v1/money-movements/provision-expense", json={
            "provision_id": str(s["provision_2"].id), "amount": 5_000,
            "expense_category_id": str(s["cat_mant"].id),
            "date": f"{TODAY}T12:00:00", "description": "Excede fondos",
        }, headers=h)
        assert resp_insuf.status_code == 400, \
            f"Expected 400 for insufficient funds, got {resp_insuf.status_code}"

        # Gastar exactamente lo que queda ($4K) → OK
        api_money_movement(client, h, "provision-expense", {
            "provision_id": s["provision_2"].id, "amount": 4_000,
            "expense_category_id": s["cat_mant"].id,
            "date": f"{TODAY}T12:00:00", "description": "Ultimo gasto",
        })
        assert_tp_balance(client, h, p2, 0)  # fondos agotados

        # Provision en cero (no sobregiro) → gastar $1 mas → 400
        resp_sobregiro = client.post("/api/v1/money-movements/provision-expense", json={
            "provision_id": str(s["provision_2"].id), "amount": 1,
            "expense_category_id": str(s["cat_mant"].id),
            "date": f"{TODAY}T12:00:00", "description": "Sin fondos",
        }, headers=h)
        assert resp_sobregiro.status_code == 400

        # --- Anular deposito de provision ---
        deposito_anular = api_money_movement(client, h, "provision-deposit", {
            "provision_id": s["provision_1"].id, "amount": 5_000,
            "account_id": s["account"].id, "date": f"{TODAY}T12:00:00",
            "description": "Deposito a anular",
        })
        assert_tp_balance(client, h, p1, -12_000)  # -7K - 5K
        assert_account_balance(client, h, aid, 444_000)

        api_annul_movement(client, h, deposito_anular["id"], "Deposito duplicado")
        assert_tp_balance(client, h, p1, -7_000)  # vuelve a -7K
        assert_account_balance(client, h, aid, 449_000)  # restaurado

        # =================================================================
        # VERIFICACION P&L
        # =================================================================
        # operating_expenses:
        #   expense_accrual: $10K + $5K + $8K = $23K (el de $2K fue anulado)
        #   provision_expense: $8K + $5K + $6K + $4K = $23K
        #   Total: $46K
        assert_pnl(client, h, operating_expenses=46_000, net_profit=-46_000)

        # =================================================================
        # VERIFICACION BALANCE SHEET
        # =================================================================
        bs = client.get("/api/v1/reports/balance-sheet", headers=h).json()

        # Liabilities side:
        # liability_1: -$5K (le debemos) → liability_debt
        # liability_2: +$3K (nos debe) → liability_advances (activo)
        # provision_1: -$7K → provision_funds (activo)
        # provision_2: $0 → no aparece
        assert bs["assets"]["provision_funds"] == pytest.approx(7_000, abs=1)

        # Total assets - total liabilities == equity
        assert bs["total_assets"] - bs["total_liabilities"] == pytest.approx(bs["equity"], abs=1)

        # =================================================================
        # ACID TEST
        # =================================================================
        assert_pnl_equals_balance(client, h)
