"""
Tests del modulo de Obligaciones Financieras (plan F).

Cubre: motor de calculo 30/360 (unit, sin BD), ciclo payable, ciclo
receivable, validaciones, anulaciones, integraciones transversales y RBAC.
Plan: docs/planes/plan-obligaciones-financieras.md (v2.1 QA-aprobado).
"""
import calendar
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, update

from app.models.money_account import MoneyAccount
from app.models.money_movement import MoneyMovement
from app.models.third_party import ThirdParty
from app.models.third_party_category import (
    ThirdPartyCategory,
    ThirdPartyCategoryAssignment,
)
from app.models.expense_category import ExpenseCategory
from app.services.obligation_interest import (
    build_capital_events,
    compute_monthly_interest,
)
from tests.integration_helpers import create_account

D = Decimal
RATE_2 = D("2.00")
URL = "/api/v1/financial-obligations"
BOGOTA = timezone(timedelta(hours=-5))


# ---------------------------------------------------------------------------
# Helpers de fechas/periodos (Bogota, igual que el backend)
# ---------------------------------------------------------------------------

def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    m = month + delta
    y = year + (m - 1) // 12
    m = (m - 1) % 12 + 1
    return y, m


def _period(months_ago: int) -> str:
    now = datetime.now(BOGOTA)
    y, m = _shift_month(now.year, now.month, -months_ago)
    return f"{y}-{m:02d}"


def _date_in(months_ago: int, day: int) -> str:
    """Fecha ISO en el periodo de hace N meses (day <= 28 para ser seguro)."""
    return f"{_period(months_ago)}-{day:02d}"


def _days_in_period(period: str) -> int:
    return calendar.monthrange(int(period[:4]), int(period[5:7]))[1]


# ---------------------------------------------------------------------------
# Helpers de datos
# ---------------------------------------------------------------------------

def _obligation_tp(db, org_id, name, balance=0):
    """Tercero investor con categoria 'Obligaciones Financieras' (criterio #31)."""
    cat = db.execute(
        select(ThirdPartyCategory).where(
            ThirdPartyCategory.organization_id == org_id,
            ThirdPartyCategory.name == "Obligaciones Financieras",
        )
    ).scalar_one_or_none()
    if not cat:
        cat = ThirdPartyCategory(
            organization_id=org_id,
            name="Obligaciones Financieras",
            behavior_type="investor",
        )
        db.add(cat)
        db.flush()
    tp = ThirdParty(
        name=name,
        organization_id=org_id,
        current_balance=D(str(balance)),
        initial_balance=D(str(balance)),
    )
    db.add(tp)
    db.flush()
    db.add(ThirdPartyCategoryAssignment(third_party_id=tp.id, category_id=cat.id))
    db.commit()  # el endpoint corre en otra sesion (override_get_db)
    return tp


def _expense_cat(db, org_id, name="Intereses"):
    cat = db.execute(
        select(ExpenseCategory).where(
            ExpenseCategory.organization_id == org_id,
            ExpenseCategory.name == name,
        )
    ).scalar_one_or_none()
    if not cat:
        cat = ExpenseCategory(
            organization_id=org_id, name=name, is_direct_expense=False
        )
        db.add(cat)
        db.commit()
    return cat


def _account(db, org_id, name="Caja Obligaciones", balance=100_000_000):
    acc = create_account(db, org_id, name, balance=balance)
    db.commit()
    return acc


# ---------------------------------------------------------------------------
# Helpers de API
# ---------------------------------------------------------------------------

def _create_obligation(
    client, headers, tp_id, *, direction="payable", rate="2.00",
    mode="disbursement", account_id=None, amount=None, date=None,
    start_period=None, expect=201,
):
    payload = {
        "third_party_id": str(tp_id),
        "direction": direction,
        "monthly_rate": rate,
        "mode": mode,
    }
    if mode == "disbursement":
        payload["disbursement"] = {
            "account_id": str(account_id),
            "amount": str(amount),
            "date": date,
        }
    if start_period:
        payload["accrual_start_period"] = start_period
    resp = client.post(f"{URL}/", json=payload, headers=headers)
    assert resp.status_code == expect, resp.json()
    return resp.json()


def _action(client, headers, obligation_id, action, *, amount, account_id, date, expect=200):
    resp = client.post(
        f"{URL}/{obligation_id}/{action}",
        json={"amount": str(amount), "account_id": str(account_id), "date": date},
        headers=headers,
    )
    assert resp.status_code == expect, resp.json()
    return resp.json()


def _pending(client, headers):
    resp = client.get(f"{URL}/pending-accruals", headers=headers)
    assert resp.status_code == 200, resp.json()
    return resp.json()


def _accrue(client, headers, expense_category_id=None, expect=200):
    body = {}
    if expense_category_id:
        body["expense_category_id"] = str(expense_category_id)
    resp = client.post(f"{URL}/accrue-pending", json=body, headers=headers)
    assert resp.status_code == expect, resp.json()
    return resp.json()


def _annul(client, headers, movement_id, reason="Anulacion de prueba", expect=200):
    resp = client.post(
        f"{URL}/movements/{movement_id}/annul",
        json={"reason": reason},
        headers=headers,
    )
    assert resp.status_code == expect, resp.json()
    return resp.json()


def _get_obligation(client, headers, obligation_id):
    resp = client.get(f"{URL}/{obligation_id}", headers=headers)
    assert resp.status_code == 200, resp.json()
    return resp.json()


def _fresh(db, model, obj_id):
    db.expire_all()
    return db.get(model, obj_id)


class TestInterestEngine:
    """Motor de calculo puro — las reglas exactas de §4 del plan."""

    def test_canonical_client_example(self):
        """Deben $20M al 2%, abonan $10M el dia 16 → $200.000 + $100.000."""
        events = [(1, D("20000000")), (16, D("10000000"))]
        amount, breakdown = compute_monthly_interest(events, RATE_2)
        assert amount == D("300000.00")
        assert "$20.000.000 × 15d" in breakdown
        assert "$10.000.000 × 15d" in breakdown
        assert "@ 2%" in breakdown

    def test_full_month_no_events(self):
        """Mes completo sin movimientos: capital × tasa."""
        amount, breakdown = compute_monthly_interest([(1, D("20000000"))], RATE_2)
        assert amount == D("400000.00")
        assert breakdown == "$20.000.000 × 30d @ 2%"

    def test_disbursement_mid_month(self):
        """Desembolso el dia 16: capital corre desde ese dia inclusive (15 dias)."""
        # Derivado con build_capital_events desde apertura $0 (mes del desembolso)
        events = build_capital_events(D("0"), [(16, D("12000000"))])
        assert events == [(1, D("0")), (16, D("12000000"))]
        amount, breakdown = compute_monthly_interest(events, RATE_2)
        assert amount == D("120000.00")
        # El tramo de capital $0 no aparece en el desglose
        assert breakdown == "$12.000.000 × 15d @ 2%"

    def test_day_31_treated_as_day_30(self):
        """Evento el dia 31 → dia 30 (1 dia con el saldo nuevo)."""
        events = [(1, D("30000000")), (31, D("20000000"))]
        amount, _ = compute_monthly_interest(events, RATE_2)
        # 30M × 2% × 29/30 + 20M × 2% × 1/30 = 580.000 + 13.333,33 → peso entero
        assert amount == D("593333")

    def test_february_day_28_keeps_virtual_days(self):
        """En febrero el dia 28 es el dia 28: quedan 3 dias (28-30) con saldo nuevo."""
        events = [(1, D("10000000")), (28, D("5000000"))]
        amount, _ = compute_monthly_interest(events, RATE_2)
        # 10M × 2% × 27/30 + 5M × 2% × 3/30 = 180.000 + 10.000
        assert amount == D("190000.00")

    def test_multiple_events_and_same_day_netting(self):
        """Varios abonos el mes; el mismo dia se netean al ultimo saldo."""
        events = [(1, D("20000000")), (10, D("15000000")), (20, D("5000000"))]
        amount, _ = compute_monthly_interest(events, RATE_2)
        # 20M×2%×9/30 + 15M×2%×10/30 + 5M×2%×11/30 = 120.000 + 100.000
        # + 36.666,67 → 256.666,67 → peso entero HALF_UP = 256.667
        assert amount == D("256667")

        # build_capital_events netea dos abonos del dia 16 (-6M y -4M)
        built = build_capital_events(
            D("20000000"), [(16, D("-6000000")), (16, D("-4000000"))]
        )
        assert built == [(1, D("20000000")), (16, D("10000000"))]
        net_amount, _ = compute_monthly_interest(built, RATE_2)
        assert net_amount == D("300000.00")

    def test_payoff_to_zero_mid_month(self):
        """Abono que salda el capital: el tramo final a $0 no genera interes."""
        events = [(1, D("8000000")), (16, D("0"))]
        amount, breakdown = compute_monthly_interest(events, RATE_2)
        assert amount == D("80000.00")
        assert breakdown == "$8.000.000 × 15d @ 2%"

        # Capital $0 todo el mes → $0 (el batch lo salta)
        zero_amount, zero_breakdown = compute_monthly_interest([(1, D("0"))], RATE_2)
        assert zero_amount == D("0.00")
        assert zero_breakdown == "capital $0 todo el mes"

    def test_quantize_on_total_not_per_tramo(self):
        """El redondeo es sobre el TOTAL: 3 tramos de $16.666,67 suman $50.000 (no $50.001)."""
        events = [(1, D("5000000")), (11, D("5000000")), (21, D("5000000"))]
        amount, _ = compute_monthly_interest(events, D("1.00"))
        # 5M × 1% × 10/30 = 16.666,67 por tramo; total exacto = 50.000
        # (redondeo por tramo daria 16.667 × 3 = 50.001)
        assert amount == D("50000")

    def test_rounds_to_whole_peso(self):
        """La causacion es en pesos ENTEROS (HALF_UP): $86.666,67 → $86.667.

        Guardrail del caso reportado en pruebas de usuario: con centavos, el
        pendiente era impagable desde la UI (inputs de pesos enteros) y la
        obligacion no se podia sanear.
        """
        # 10M × 2% × 13/30 = 86.666,666... → 86.667
        events = [(1, D("10000000")), (14, D("0"))]
        amount, _ = compute_monthly_interest(events, RATE_2)
        assert amount == D("86667")
        assert amount == amount.to_integral_value()


# ===========================================================================
# Ciclo PAYABLE (nos prestaron)
# ===========================================================================

class TestPayableCycle:

    def test_create_with_disbursement(self, client, org_headers, db_session, test_organization):
        """Desembolso inicial: cuenta(+), tercero(-), capital seteado, MM creado."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Prestamista A")
        acc = _account(db_session, org_id, "Caja Pay A", balance=10_000_000)

        data = _create_obligation(
            client, org_headers, tp.id, direction="payable",
            account_id=acc.id, amount=20_000_000, date=_date_in(1, 5),
        )
        assert data["capital_balance"] == "20000000.00" or float(data["capital_balance"]) == 20_000_000
        assert data["pending_interest"] == "0.00" or float(data["pending_interest"]) == 0
        assert data["direction"] == "payable"
        assert data["third_party_name"] == "Prestamista A"

        acc_f = _fresh(db_session, MoneyAccount, acc.id)
        tp_f = _fresh(db_session, ThirdParty, tp.id)
        assert acc_f.current_balance == D("30000000")   # 10M + 20M entra el prestamo
        assert tp_f.current_balance == D("-20000000")   # les debemos

        mm = db_session.execute(
            select(MoneyMovement).where(
                MoneyMovement.financial_obligation_id == data["id"],
                MoneyMovement.movement_type == "obligation_disbursement",
            )
        ).scalar_one()
        assert mm.status == "confirmed"
        assert mm.amount == D("20000000")

    def test_create_from_balance(self, client, org_headers, db_session, test_organization):
        """Migracion: saldo negativo existente → capital = |saldo|, SIN MM."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Prestamista Migrado", balance=-15_000_000)

        data = _create_obligation(
            client, org_headers, tp.id, direction="payable", mode="from_balance",
        )
        assert float(data["capital_balance"]) == 15_000_000
        assert data["disbursement_date"] is None

        count = db_session.execute(
            select(MoneyMovement).where(
                MoneyMovement.financial_obligation_id == data["id"]
            )
        ).scalars().all()
        assert count == []  # sin MM — el saldo ya existia
        tp_f = _fresh(db_session, ThirdParty, tp.id)
        assert tp_f.current_balance == D("-15000000")  # intacto

    def test_accrue_closed_month(self, client, org_headers, db_session, test_organization):
        """Causar mes vencido: MM accrual sin cuenta, pendientes suben, tercero baja."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Prestamista Causa")
        acc = _account(db_session, org_id, "Caja Causa")
        cat = _expense_cat(db_session, org_id)

        # Desembolso el dia 1 del mes pasado → mes completo al 2% = 400K
        ob = _create_obligation(
            client, org_headers, tp.id, direction="payable",
            account_id=acc.id, amount=20_000_000, date=_date_in(1, 1),
        )
        pending = _pending(client, org_headers)
        assert pending["has_payable"] is True
        item = next(i for i in pending["items"] if i["obligation_id"] == ob["id"])
        assert float(item["amount"]) == 400_000
        assert item["period"] == _period(1)

        tp_before = _fresh(db_session, ThirdParty, tp.id).current_balance
        result = _accrue(client, org_headers, expense_category_id=cat.id)
        assert result["created_count"] == 1
        assert float(result["total_payable"]) == 400_000

        ob_f = _get_obligation(client, org_headers, ob["id"])
        assert float(ob_f["pending_interest"]) == 400_000
        assert ob_f["last_accrued_period"] == _period(1)

        tp_f = _fresh(db_session, ThirdParty, tp.id)
        assert tp_f.current_balance == tp_before - D("400000")  # debemos mas

        mm = db_session.execute(
            select(MoneyMovement).where(
                MoneyMovement.financial_obligation_id == ob["id"],
                MoneyMovement.movement_type == "obligation_interest_accrual",
            )
        ).scalar_one()
        assert mm.account_id is None
        assert mm.obligation_period == _period(1)
        assert mm.expense_category_id == cat.id

    def test_batch_idempotent(self, client, org_headers, db_session, test_organization):
        """Segunda corrida del batch = 0 causaciones nuevas."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Prestamista Idem")
        acc = _account(db_session, org_id, "Caja Idem")
        cat = _expense_cat(db_session, org_id)
        _create_obligation(
            client, org_headers, tp.id, direction="payable",
            account_id=acc.id, amount=10_000_000, date=_date_in(1, 1),
        )
        first = _accrue(client, org_headers, expense_category_id=cat.id)
        assert first["created_count"] == 1
        second = _accrue(client, org_headers, expense_category_id=cat.id)
        assert second["created_count"] == 0

    def test_partial_interest_payment(self, client, org_headers, db_session, test_organization):
        """Pago parcial de intereses: cuenta(-), tercero(+), pendientes bajan."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Prestamista Parcial")
        acc = _account(db_session, org_id, "Caja Parcial", balance=50_000_000)
        cat = _expense_cat(db_session, org_id)
        ob = _create_obligation(
            client, org_headers, tp.id, direction="payable",
            account_id=acc.id, amount=20_000_000, date=_date_in(1, 1),
        )
        _accrue(client, org_headers, expense_category_id=cat.id)  # 400K pendientes

        _action(
            client, org_headers, ob["id"], "interest-payment",
            amount=100_000, account_id=acc.id, date=_date_in(0, 5),
        )
        ob_f = _get_obligation(client, org_headers, ob["id"])
        assert float(ob_f["pending_interest"]) == 300_000

        acc_f = _fresh(db_session, MoneyAccount, acc.id)
        # 50M + 20M (desembolso) - 100K (pago intereses)
        assert acc_f.current_balance == D("69900000")
        tp_f = _fresh(db_session, ThirdParty, tp.id)
        # -20M (desembolso) - 400K (causacion) + 100K (pago)
        assert tp_f.current_balance == D("-20300000")

    def test_capital_payment_splits_next_accrual(self, client, org_headers, db_session, test_organization):
        """Ejemplo canonico end-to-end: abono $10M el dia 16 → causacion $300K."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Prestamista Canonico")
        acc = _account(db_session, org_id, "Caja Canonica", balance=50_000_000)
        cat = _expense_cat(db_session, org_id)

        # Desembolso $20M el dia 1 de hace 2 meses; causar ese mes completo (400K)
        ob = _create_obligation(
            client, org_headers, tp.id, direction="payable",
            account_id=acc.id, amount=20_000_000, date=_date_in(2, 1),
            start_period=_period(2),
        )
        # Abono $10M el dia 16 del mes pasado (aun sin causar)
        _action(
            client, org_headers, ob["id"], "capital-payment",
            amount=10_000_000, account_id=acc.id, date=_date_in(1, 16),
        )
        ob_f = _get_obligation(client, org_headers, ob["id"])
        assert float(ob_f["capital_balance"]) == 10_000_000

        pending = _pending(client, org_headers)
        mine = [i for i in pending["items"] if i["obligation_id"] == ob["id"]]
        by_period = {i["period"]: i for i in mine}
        assert float(by_period[_period(2)]["amount"]) == 400_000   # mes completo
        assert float(by_period[_period(1)]["amount"]) == 300_000   # canonico: 200K + 100K
        assert "15d" in by_period[_period(1)]["breakdown"]

        result = _accrue(client, org_headers, expense_category_id=cat.id)
        assert result["created_count"] == 2
        assert float(result["total_payable"]) == 700_000

    def test_settle(self, client, org_headers, db_session, test_organization):
        """Settle exige saldos en 0; obligacion cerrada no acepta movimientos."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Prestamista Cierre")
        acc = _account(db_session, org_id, "Caja Cierre", balance=50_000_000)
        ob = _create_obligation(
            client, org_headers, tp.id, direction="payable",
            account_id=acc.id, amount=5_000_000, date=_date_in(0, 1),
        )
        # Con capital vigente → 400
        resp = client.post(f"{URL}/{ob['id']}/settle", headers=org_headers)
        assert resp.status_code == 400

        # Abonar todo el capital (mes en curso, sin causaciones) → settle ok
        _action(
            client, org_headers, ob["id"], "capital-payment",
            amount=5_000_000, account_id=acc.id, date=_date_in(0, 2),
        )
        resp = client.post(f"{URL}/{ob['id']}/settle", headers=org_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "settled"

        # Cerrada → no acepta movimientos
        _action(
            client, org_headers, ob["id"], "capital-payment",
            amount=1_000, account_id=acc.id, date=_date_in(0, 3), expect=400,
        )


# ===========================================================================
# Ciclo RECEIVABLE (prestamos nosotros)
# ===========================================================================

class TestReceivableCycle:

    def test_loan_disbursement(self, client, org_headers, db_session, test_organization):
        """Prestamo entregado: cuenta(-), tercero(+)."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Deudor A")
        acc = _account(db_session, org_id, "Caja Loan A", balance=30_000_000)
        _create_obligation(
            client, org_headers, tp.id, direction="receivable",
            account_id=acc.id, amount=12_000_000, date=_date_in(1, 1),
        )
        acc_f = _fresh(db_session, MoneyAccount, acc.id)
        tp_f = _fresh(db_session, ThirdParty, tp.id)
        assert acc_f.current_balance == D("18000000")  # sale el prestamo
        assert tp_f.current_balance == D("12000000")   # nos debe

    def test_accrual_goes_to_interest_income(self, client, org_headers, db_session, test_organization):
        """Causacion receivable → P&L interest_income, NO gastos, sin categoria."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Deudor P&L")
        acc = _account(db_session, org_id, "Caja Loan PnL", balance=30_000_000)
        ob = _create_obligation(
            client, org_headers, tp.id, direction="receivable",
            account_id=acc.id, amount=12_000_000, date=_date_in(1, 1),
        )
        # Sin categoria — las receivable no la necesitan
        result = _accrue(client, org_headers)
        assert result["created_count"] == 1
        assert float(result["total_receivable"]) == 240_000  # 12M × 2%

        period = _period(1)
        resp = client.get(
            "/api/v1/reports/profit-and-loss",
            params={
                "date_from": f"{period}-01",
                "date_to": f"{period}-{_days_in_period(period):02d}",
            },
            headers=org_headers,
        )
        assert resp.status_code == 200
        pnl = resp.json()
        assert pnl["interest_income"] == 240_000
        assert pnl["operating_expenses"] == 0  # NO es gasto
        assert pnl["total_gross_profit"] == 240_000

        ob_f = _get_obligation(client, org_headers, ob["id"])
        assert float(ob_f["pending_interest"]) == 240_000
        tp_f = _fresh(db_session, ThirdParty, tp.id)
        assert tp_f.current_balance == D("12240000")  # nos debe mas

    def test_interest_collection(self, client, org_headers, db_session, test_organization):
        """Recaudo de intereses: cuenta(+), tercero(-), pendientes bajan."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Deudor Recaudo")
        acc = _account(db_session, org_id, "Caja Recaudo", balance=30_000_000)
        ob = _create_obligation(
            client, org_headers, tp.id, direction="receivable",
            account_id=acc.id, amount=12_000_000, date=_date_in(1, 1),
        )
        _accrue(client, org_headers)  # 240K
        _action(
            client, org_headers, ob["id"], "interest-payment",
            amount=240_000, account_id=acc.id, date=_date_in(0, 5),
        )
        ob_f = _get_obligation(client, org_headers, ob["id"])
        assert float(ob_f["pending_interest"]) == 0
        acc_f = _fresh(db_session, MoneyAccount, acc.id)
        assert acc_f.current_balance == D("18240000")  # 30M - 12M + 240K
        tp_f = _fresh(db_session, ThirdParty, tp.id)
        assert tp_f.current_balance == D("12000000")  # +12M +240K -240K

    def test_capital_collection(self, client, org_headers, db_session, test_organization):
        """Recaudo de capital: cuenta(+), tercero(-), capital baja."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Deudor Capital")
        acc = _account(db_session, org_id, "Caja Cap Loan", balance=30_000_000)
        ob = _create_obligation(
            client, org_headers, tp.id, direction="receivable",
            account_id=acc.id, amount=12_000_000, date=_date_in(0, 1),
        )
        _action(
            client, org_headers, ob["id"], "capital-payment",
            amount=5_000_000, account_id=acc.id, date=_date_in(0, 2),
        )
        ob_f = _get_obligation(client, org_headers, ob["id"])
        assert float(ob_f["capital_balance"]) == 7_000_000
        acc_f = _fresh(db_session, MoneyAccount, acc.id)
        assert acc_f.current_balance == D("23000000")  # 30M - 12M + 5M
        tp_f = _fresh(db_session, ThirdParty, tp.id)
        assert tp_f.current_balance == D("7000000")

    def test_canonical_mirror(self, client, org_headers, db_session, test_organization):
        """Espejo del ejemplo canonico: prestamo $20M, recaudo $10M dia 16 → $300K."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Deudor Canonico")
        acc = _account(db_session, org_id, "Caja Can Loan", balance=50_000_000)
        ob = _create_obligation(
            client, org_headers, tp.id, direction="receivable",
            account_id=acc.id, amount=20_000_000, date=_date_in(1, 1),
        )
        _action(
            client, org_headers, ob["id"], "capital-payment",
            amount=10_000_000, account_id=acc.id, date=_date_in(1, 16),
        )
        pending = _pending(client, org_headers)
        item = next(i for i in pending["items"] if i["obligation_id"] == ob["id"])
        assert float(item["amount"]) == 300_000
        assert item["direction"] == "receivable"


# ===========================================================================
# Validaciones
# ===========================================================================

class TestValidations:

    def _setup(self, client, org_headers, db_session, org_id, name, **kwargs):
        tp = _obligation_tp(db_session, org_id, name)
        acc = _account(db_session, org_id, f"Caja {name}", balance=50_000_000)
        ob = _create_obligation(
            client, org_headers, tp.id, account_id=acc.id,
            amount=kwargs.get("amount", 10_000_000),
            date=kwargs.get("date", _date_in(1, 1)),
            direction=kwargs.get("direction", "payable"),
        )
        return tp, acc, ob

    def test_capital_payment_over_balance(self, client, org_headers, db_session, test_organization):
        tp, acc, ob = self._setup(client, org_headers, db_session, test_organization.id, "Val Sobregiro")
        _action(
            client, org_headers, ob["id"], "capital-payment",
            amount=99_000_000, account_id=acc.id, date=_date_in(0, 5), expect=400,
        )

    def test_interest_payment_over_pending(self, client, org_headers, db_session, test_organization):
        tp, acc, ob = self._setup(client, org_headers, db_session, test_organization.id, "Val Intereses")
        # Sin causar nada → pendientes 0 → cualquier pago revienta
        _action(
            client, org_headers, ob["id"], "interest-payment",
            amount=1_000, account_id=acc.id, date=_date_in(0, 5), expect=400,
        )

    def test_second_active_obligation_same_tp(self, client, org_headers, db_session, test_organization):
        tp, acc, ob = self._setup(client, org_headers, db_session, test_organization.id, "Val Duplicado")
        _create_obligation(
            client, org_headers, tp.id, account_id=acc.id,
            amount=1_000_000, date=_date_in(0, 1), expect=400,
        )

    def test_tp_without_obligation_category(self, client, org_headers, db_session, test_organization):
        """Tercero investor pero con categoria 'Socios' (sin 'obligaci') → 400."""
        from tests.conftest import create_third_party_with_category
        org_id = test_organization.id
        cat = ThirdPartyCategory(
            organization_id=org_id, name="Socios", behavior_type="investor"
        )
        db_session.add(cat)
        db_session.flush()
        tp = ThirdParty(name="Socio No Obligacion", organization_id=org_id)
        db_session.add(tp)
        db_session.flush()
        db_session.add(
            ThirdPartyCategoryAssignment(third_party_id=tp.id, category_id=cat.id)
        )
        db_session.commit()
        acc = _account(db_session, org_id, "Caja Val Cat")
        _create_obligation(
            client, org_headers, tp.id, account_id=acc.id,
            amount=1_000_000, date=_date_in(0, 1), expect=400,
        )

    def test_retroactive_capital_movement_blocked(self, client, org_headers, db_session, test_organization):
        """Abono con fecha en periodo ya causado → 400 (supuesto 5)."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Val Retro")
        acc = _account(db_session, org_id, "Caja Retro", balance=50_000_000)
        cat = _expense_cat(db_session, org_id)
        ob = _create_obligation(
            client, org_headers, tp.id, direction="payable",
            account_id=acc.id, amount=10_000_000, date=_date_in(1, 1),
        )
        _accrue(client, org_headers, expense_category_id=cat.id)  # causa el mes pasado
        _action(
            client, org_headers, ob["id"], "capital-payment",
            amount=1_000_000, account_id=acc.id, date=_date_in(1, 20), expect=400,
        )

    def test_from_balance_wrong_sign(self, client, org_headers, db_session, test_organization):
        """from_balance payable exige saldo negativo → saldo positivo revienta."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Val Signo", balance=5_000_000)
        resp = client.post(
            f"{URL}/", headers=org_headers,
            json={
                "third_party_id": str(tp.id), "direction": "payable",
                "monthly_rate": "2.00", "mode": "from_balance",
            },
        )
        assert resp.status_code == 400


# ===========================================================================
# Anulaciones (solo via modulo)
# ===========================================================================

class TestAnnulments:

    def _accrued_setup(self, client, org_headers, db_session, org_id, name):
        """Obligacion payable con 1 mes causado (400K pendientes)."""
        tp = _obligation_tp(db_session, org_id, name)
        acc = _account(db_session, org_id, f"Caja {name}", balance=50_000_000)
        cat = _expense_cat(db_session, org_id)
        ob = _create_obligation(
            client, org_headers, tp.id, direction="payable",
            account_id=acc.id, amount=20_000_000, date=_date_in(1, 1),
        )
        _accrue(client, org_headers, expense_category_id=cat.id)
        accrual = db_session.execute(
            select(MoneyMovement).where(
                MoneyMovement.financial_obligation_id == ob["id"],
                MoneyMovement.movement_type == "obligation_interest_accrual",
            )
        ).scalar_one()
        return tp, acc, cat, ob, accrual

    def test_annul_accrual_frees_period(self, client, org_headers, db_session, test_organization):
        """Anular causacion: pendientes revertidos, periodo re-causable."""
        tp, acc, cat, ob, accrual = self._accrued_setup(
            client, org_headers, db_session, test_organization.id, "Anu Causa"
        )
        tp_before = _fresh(db_session, ThirdParty, tp.id).current_balance
        _annul(client, org_headers, accrual.id)

        ob_f = _get_obligation(client, org_headers, ob["id"])
        assert float(ob_f["pending_interest"]) == 0
        assert ob_f["last_accrued_period"] is None
        tp_f = _fresh(db_session, ThirdParty, tp.id)
        assert tp_f.current_balance == tp_before + D("400000")

        # El periodo vuelve a aparecer como pendiente (re-causable)
        pending = _pending(client, org_headers)
        assert any(
            i["obligation_id"] == ob["id"] and i["period"] == _period(1)
            for i in pending["items"]
        )

    def test_annul_interest_payment_restores_pending(self, client, org_headers, db_session, test_organization):
        tp, acc, cat, ob, accrual = self._accrued_setup(
            client, org_headers, db_session, test_organization.id, "Anu Pago Int"
        )
        payment = _action(
            client, org_headers, ob["id"], "interest-payment",
            amount=400_000, account_id=acc.id, date=_date_in(0, 5),
        )
        assert float(_get_obligation(client, org_headers, ob["id"])["pending_interest"]) == 0

        acc_before = _fresh(db_session, MoneyAccount, acc.id).current_balance
        _annul(client, org_headers, payment["id"])
        assert float(_get_obligation(client, org_headers, ob["id"])["pending_interest"]) == 400_000
        acc_f = _fresh(db_session, MoneyAccount, acc.id)
        assert acc_f.current_balance == acc_before + D("400000")  # el pago vuelve

    def test_annul_capital_payment_unaccrued_period(self, client, org_headers, db_session, test_organization):
        """Anular abono del mes en curso (no causado) → capital restaurado."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Anu Abono")
        acc = _account(db_session, org_id, "Caja Anu Abono", balance=50_000_000)
        ob = _create_obligation(
            client, org_headers, tp.id, direction="payable",
            account_id=acc.id, amount=10_000_000, date=_date_in(0, 1),
        )
        payment = _action(
            client, org_headers, ob["id"], "capital-payment",
            amount=4_000_000, account_id=acc.id, date=_date_in(0, 2),
        )
        assert float(_get_obligation(client, org_headers, ob["id"])["capital_balance"]) == 6_000_000
        _annul(client, org_headers, payment["id"])
        assert float(_get_obligation(client, org_headers, ob["id"])["capital_balance"]) == 10_000_000

    def test_annul_capital_in_accrued_period_blocked(self, client, org_headers, db_session, test_organization):
        """Guard espejo (gap v2): anular abono fechado en periodo YA causado → 400."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Anu Espejo")
        acc = _account(db_session, org_id, "Caja Anu Espejo", balance=50_000_000)
        cat = _expense_cat(db_session, org_id)
        ob = _create_obligation(
            client, org_headers, tp.id, direction="payable",
            account_id=acc.id, amount=20_000_000, date=_date_in(1, 1),
        )
        # Abono el dia 16 del mes pasado, ANTES de causar
        payment = _action(
            client, org_headers, ob["id"], "capital-payment",
            amount=10_000_000, account_id=acc.id, date=_date_in(1, 16),
        )
        _accrue(client, org_headers, expense_category_id=cat.id)  # causa con el abono adentro
        # Anular el abono dejaria la causacion con tramos falsos → 400
        _annul(client, org_headers, payment["id"], expect=400)

    def test_annul_initial_disbursement_with_later_activity(self, client, org_headers, db_session, test_organization):
        """Desembolso inicial con movimiento posterior → 400."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Anu Desembolso")
        acc = _account(db_session, org_id, "Caja Anu Des", balance=50_000_000)
        ob = _create_obligation(
            client, org_headers, tp.id, direction="payable",
            account_id=acc.id, amount=10_000_000, date=_date_in(0, 1),
        )
        _action(
            client, org_headers, ob["id"], "capital-payment",
            amount=1_000_000, account_id=acc.id, date=_date_in(0, 2),
        )
        disbursement = db_session.execute(
            select(MoneyMovement).where(
                MoneyMovement.financial_obligation_id == ob["id"],
                MoneyMovement.movement_type == "obligation_disbursement",
            )
        ).scalar_one()
        _annul(client, org_headers, disbursement.id, expect=400)

    def test_annul_on_settled_obligation_blocked(self, client, org_headers, db_session, test_organization):
        """Anular movimientos de una obligacion cerrada → 400 (dejaria contadores >0 en settled)."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Anu Settled")
        acc = _account(db_session, org_id, "Caja Anu Settled", balance=50_000_000)
        ob = _create_obligation(
            client, org_headers, tp.id, direction="payable",
            account_id=acc.id, amount=5_000_000, date=_date_in(0, 1),
        )
        payment = _action(
            client, org_headers, ob["id"], "capital-payment",
            amount=5_000_000, account_id=acc.id, date=_date_in(0, 2),
        )
        resp = client.post(f"{URL}/{ob['id']}/settle", headers=org_headers)
        assert resp.status_code == 200
        _annul(client, org_headers, payment["id"], expect=400)

    def test_treasury_direct_annul_blocked_422(self, client, org_headers, db_session, test_organization):
        """PATCH de anulacion de Tesoreria sobre tipo de obligacion → 422."""
        tp, acc, cat, ob, accrual = self._accrued_setup(
            client, org_headers, db_session, test_organization.id, "Anu Tesoreria"
        )
        resp = client.post(
            f"/api/v1/money-movements/{accrual.id}/annul",
            json={"reason": "Intento directo desde tesoreria"},
            headers=org_headers,
        )
        assert resp.status_code == 422, resp.json()


# ===========================================================================
# Integraciones transversales
# ===========================================================================

class TestIntegrations:

    def test_pnl_payable_expense_by_category(self, client, org_headers, db_session, test_organization):
        """Causacion payable entra al P&L como gasto por categoria con source_type propio."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Int PnL Gasto")
        acc = _account(db_session, org_id, "Caja Int PnL")
        cat = _expense_cat(db_session, org_id, "Intereses Financieros")
        _create_obligation(
            client, org_headers, tp.id, direction="payable",
            account_id=acc.id, amount=20_000_000, date=_date_in(1, 1),
        )
        _accrue(client, org_headers, expense_category_id=cat.id)

        period = _period(1)
        resp = client.get(
            "/api/v1/reports/profit-and-loss",
            params={
                "date_from": f"{period}-01",
                "date_to": f"{period}-{_days_in_period(period):02d}",
            },
            headers=org_headers,
        )
        pnl = resp.json()
        assert pnl["operating_expenses"] == 400_000
        entry = next(
            e for e in pnl["expenses_by_category"]
            if e["source_type"] == "obligation_interest_accrual"
        )
        assert entry["category_name"] == "Intereses Financieros"
        assert entry["total_amount"] == 400_000
        assert pnl["interest_income"] == 0  # payable NO es ingreso

    def test_pnl_drilldown_parity(self, client, org_headers, db_session, test_organization):
        """Suma del listado de MMs filtrado == linea del P&L (promesa #49)."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Int Drill")
        acc = _account(db_session, org_id, "Caja Drill")
        cat = _expense_cat(db_session, org_id)
        _create_obligation(
            client, org_headers, tp.id, direction="payable",
            account_id=acc.id, amount=20_000_000, date=_date_in(1, 1),
        )
        _accrue(client, org_headers, expense_category_id=cat.id)

        period = _period(1)
        date_from = f"{period}-01"
        date_to = f"{period}-{_days_in_period(period):02d}"
        resp = client.get(
            "/api/v1/money-movements",
            params={
                "movement_type": "obligation_interest_accrual",
                "status": "confirmed",
                "date_from": date_from, "date_to": date_to,
                "limit": 100,
            },
            headers=org_headers,
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        total = sum(float(m["amount"]) for m in items)
        assert total == 400_000

    def test_cash_flow_buckets(self, client, org_headers, db_session, test_organization):
        """Los 6 tipos con caja aparecen en sus buckets del flujo de caja."""
        org_id = test_organization.id
        tp_pay = _obligation_tp(db_session, org_id, "Int CF Pay")
        tp_loan = _obligation_tp(db_session, org_id, "Int CF Loan")
        acc = _account(db_session, org_id, "Caja CF", balance=100_000_000)
        cat = _expense_cat(db_session, org_id)

        ob_pay = _create_obligation(
            client, org_headers, tp_pay.id, direction="payable",
            account_id=acc.id, amount=20_000_000, date=_date_in(1, 1),
        )
        ob_loan = _create_obligation(
            client, org_headers, tp_loan.id, direction="receivable",
            account_id=acc.id, amount=12_000_000, date=_date_in(1, 1),
        )
        _accrue(client, org_headers, expense_category_id=cat.id)
        _action(client, org_headers, ob_pay["id"], "interest-payment",
                amount=400_000, account_id=acc.id, date=_date_in(0, 5))
        _action(client, org_headers, ob_pay["id"], "capital-payment",
                amount=2_000_000, account_id=acc.id, date=_date_in(0, 6))
        _action(client, org_headers, ob_loan["id"], "interest-payment",
                amount=240_000, account_id=acc.id, date=_date_in(0, 7))
        _action(client, org_headers, ob_loan["id"], "capital-payment",
                amount=1_000_000, account_id=acc.id, date=_date_in(0, 8))

        resp = client.get(
            "/api/v1/reports/cash-flow",
            params={"date_from": _date_in(1, 1), "date_to": _date_in(0, 28)},
            headers=org_headers,
        )
        assert resp.status_code == 200
        cf = resp.json()
        assert cf["inflows"]["obligation_disbursements"] == 20_000_000
        assert cf["inflows"]["loan_interest_collections"] == 240_000
        assert cf["inflows"]["loan_capital_collections"] == 1_000_000
        assert cf["outflows"]["loan_disbursements"] == 12_000_000
        assert cf["outflows"]["obligation_interest_payments"] == 400_000
        assert cf["outflows"]["obligation_capital_payments"] == 2_000_000

    def test_balance_detailed_sections_no_regression(self, client, org_headers, db_session, test_organization):
        """payable → investors_obligations (pasivo); receivable → loans_receivable (activo, split)."""
        org_id = test_organization.id
        tp_pay = _obligation_tp(db_session, org_id, "Int Bal Pay")
        tp_loan = _obligation_tp(db_session, org_id, "Int Bal Loan")
        acc = _account(db_session, org_id, "Caja Bal", balance=100_000_000)
        _create_obligation(
            client, org_headers, tp_pay.id, direction="payable",
            account_id=acc.id, amount=20_000_000, date=_date_in(0, 1),
        )
        _create_obligation(
            client, org_headers, tp_loan.id, direction="receivable",
            account_id=acc.id, amount=12_000_000, date=_date_in(0, 1),
        )
        resp = client.get("/api/v1/reports/balance-detailed", headers=org_headers)
        assert resp.status_code == 200
        data = resp.json()
        pay_items = data["liabilities"]["investors_obligations"]["items"]
        assert any(i["id"] == str(tp_pay.id) for i in pay_items)
        # Split: el prestamo va a linea propia, NO a CxC Inversionistas
        loan_items = data["assets"]["loans_receivable"]["items"]
        assert any(i["id"] == str(tp_loan.id) for i in loan_items)
        inv_items = data["assets"].get("investor_receivable", {}).get("items", [])
        assert not any(i["id"] == str(tp_loan.id) for i in inv_items)

    def test_loans_split_invariant_total_assets(self, client, org_headers, db_session, test_organization):
        """Split loans_receivable + obligations_payable: lineas propias sin alterar totales.

        Invariante QA: total == suma de TODOS los componentes del response —
        si el split perdiera o duplicara una obligacion, revienta. Los socios
        (investor sin categoria de obligaciones) se quedan en CxC Inversionistas
        / Deuda Inversionistas segun signo.
        """
        org_id = test_organization.id
        tp_loan = _obligation_tp(db_session, org_id, "Split Loan TP")
        tp_pay = _obligation_tp(db_session, org_id, "Split Pay TP")
        # Socios: investor SIN categoria "obligaci..." (categoria propia por nombre —
        # el lookup generico por behavior_type reusaria la de Obligaciones)
        socio_cat = ThirdPartyCategory(
            organization_id=org_id, name="Socios", behavior_type="investor"
        )
        db_session.add(socio_cat)
        db_session.flush()
        socio = ThirdParty(
            name="Split Socio TP", organization_id=org_id,
            current_balance=D("5000000"), initial_balance=D("5000000"),
        )
        socio_deuda = ThirdParty(
            name="Split Socio Deuda TP", organization_id=org_id,
            current_balance=D("-3000000"), initial_balance=D("-3000000"),
        )
        db_session.add_all([socio, socio_deuda])
        db_session.flush()
        db_session.add_all([
            ThirdPartyCategoryAssignment(third_party_id=socio.id, category_id=socio_cat.id),
            ThirdPartyCategoryAssignment(third_party_id=socio_deuda.id, category_id=socio_cat.id),
        ])
        db_session.commit()
        acc = _account(db_session, org_id, "Caja Split", balance=100_000_000)
        _create_obligation(
            client, org_headers, tp_loan.id, direction="receivable",
            account_id=acc.id, amount=12_000_000, date=_date_in(0, 1),
        )
        _create_obligation(
            client, org_headers, tp_pay.id, direction="payable",
            account_id=acc.id, amount=20_000_000, date=_date_in(0, 1),
        )

        resp = client.get("/api/v1/reports/balance-sheet", headers=org_headers)
        assert resp.status_code == 200
        data = resp.json()
        assets = data["assets"]
        assert assets["loans_receivable"] == 12_000_000.0
        assert assets["investor_receivable"] == 5_000_000.0
        # Invariante activo: el total es la suma exacta de sus componentes
        components = (
            assets["cash_and_bank"] + assets["accounts_receivable"] + assets["inventory"]
            + assets["advances"] + assets["investor_receivable"] + assets["loans_receivable"]
            + assets["prepaid_expenses"] + assets["provision_funds"] + assets["fixed_assets"]
        )
        assert abs(assets["total"] - components) < 0.01

        # Lado pasivo (split espejo): obligacion payable en linea propia,
        # socio con deuda sigue en Deuda Inversionistas
        liab = data["liabilities"]
        assert liab["obligations_payable"] == 20_000_000.0
        assert liab["investor_debt"] == 3_000_000.0
        liab_components = (
            liab["accounts_payable"] + liab["investor_debt"] + liab["obligations_payable"]
            + liab["liability_debt"] + liab["service_provider_payable"]
            + liab["customer_advances"] + liab["provision_obligations"] + liab["generic_payable"]
        )
        assert abs(liab["total"] - liab_components) < 0.01

        # As-of hoy (path historico _classify_tp_by_balance): mismo split ambos lados
        from datetime import date as date_cls
        resp = client.get(
            "/api/v1/reports/balance-sheet",
            params={"as_of_date": date_cls.today().isoformat()},
            headers=org_headers,
        )
        assert resp.status_code == 200
        asof = resp.json()
        assert asof["assets"]["loans_receivable"] == 12_000_000.0
        assert asof["liabilities"]["obligations_payable"] == 20_000_000.0

        # Panel #68: el prestamo sigue apareciendo (seccion nueva mapeada a investor)
        resp = client.get(
            "/api/v1/reports/inactive-balances",
            params={"min_days": 0},
            headers=org_headers,
        )
        assert resp.status_code == 200
        names = [i["third_party_name"] for i in resp.json()["items"]]
        assert "Split Loan TP" in names

    def test_balance_as_of_snapshot(self, client, org_headers, db_session, test_organization):
        """as_of ANTES del abono muestra el saldo pre-abono (mapas de signos as-of)."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Int AsOf")
        acc = _account(db_session, org_id, "Caja AsOf", balance=50_000_000)
        ob = _create_obligation(
            client, org_headers, tp.id, direction="payable",
            account_id=acc.id, amount=20_000_000, date=_date_in(1, 1),
        )
        _action(
            client, org_headers, ob["id"], "capital-payment",
            amount=5_000_000, account_id=acc.id, date=_date_in(0, 5),
        )
        # Corte al cierre del mes pasado: el abono (este mes) NO cuenta
        period = _period(1)
        cutoff = f"{period}-{_days_in_period(period):02d}"
        resp = client.get(
            "/api/v1/reports/balance-detailed",
            params={"as_of_date": cutoff},
            headers=org_headers,
        )
        data = resp.json()
        items = data["liabilities"]["investors_obligations"]["items"]
        item = next(i for i in items if i["id"] == str(tp.id))
        assert abs(item["balance"]) == 20_000_000  # sin el abono de 5M

    def test_statement_running_balance(self, client, org_headers, db_session, test_organization):
        """Estado de cuenta unificado: saldo corrido correcto (mapas duplicados)."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Int Statement")
        acc = _account(db_session, org_id, "Caja Stmt", balance=50_000_000)
        cat = _expense_cat(db_session, org_id)
        ob = _create_obligation(
            client, org_headers, tp.id, direction="payable",
            account_id=acc.id, amount=20_000_000, date=_date_in(1, 1),
        )
        _accrue(client, org_headers, expense_category_id=cat.id)  # -400K
        _action(
            client, org_headers, ob["id"], "interest-payment",
            amount=400_000, account_id=acc.id, date=_date_in(0, 5),
        )
        resp = client.get(
            f"/api/v1/money-movements/third-party/{tp.id}",
            params={"date_from": _date_in(2, 1)},
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        entries = data["items"] if isinstance(data, dict) else data
        # El saldo corrido final == saldo vivo del tercero (-20M)
        tp_f = _fresh(db_session, ThirdParty, tp.id)
        assert tp_f.current_balance == D("-20000000")
        last_balance = entries[-1]["balance_after"]
        assert last_balance == -20_000_000

    def test_inactive_panel_ignores_accruals(self, client, org_headers, db_session, test_organization):
        """Deudor moroso con solo causaciones batch sigue INACTIVO; un recaudo real resetea."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Deudor Moroso", balance=12_000_000)
        # Tercero "viejo": created_at hace 60 dias (fallback D6)
        d = datetime.now(BOGOTA).date() - timedelta(days=60)
        db_session.execute(
            update(ThirdParty).where(ThirdParty.id == tp.id).values(
                created_at=datetime(d.year, d.month, d.day, 12, tzinfo=timezone.utc)
            )
        )
        db_session.commit()
        ob = _create_obligation(
            client, org_headers, tp.id, direction="receivable", mode="from_balance",
            start_period=_period(1),
        )
        _accrue(client, org_headers)  # causacion del mes pasado (MM reciente)

        resp = client.get(
            "/api/v1/reports/inactive-balances",
            params={"min_days": 30}, headers=org_headers,
        )
        items = resp.json()["items"]
        item = next((i for i in items if i["third_party_id"] == str(tp.id)), None)
        # La causacion NO reseteo el reloj: sigue apareciendo con ~60 dias
        assert item is not None
        assert item["days_inactive"] >= 59

        # Un recaudo REAL si resetea el reloj → desaparece del panel
        acc = _account(db_session, org_id, "Caja Moroso")
        _action(
            client, org_headers, ob["id"], "interest-payment",
            amount=100_000, account_id=acc.id, date=_date_in(0, min(datetime.now(BOGOTA).day, 28)),
        )
        resp = client.get(
            "/api/v1/reports/inactive-balances",
            params={"min_days": 30}, headers=org_headers,
        )
        items = resp.json()["items"]
        assert not any(i["third_party_id"] == str(tp.id) for i in items)


def _today_bogota():
    return datetime.now(BOGOTA)


def _ind_preview(client, headers, obligation_id):
    resp = client.get(f"{URL}/{obligation_id}/accrue-preview", headers=headers)
    assert resp.status_code == 200, resp.json()
    return resp.json()


def _ind_accrue(client, headers, obligation_id, category_id=None, tranche=False, expect=200):
    body = {"include_current_tranche": tranche}
    if category_id:
        body["expense_category_id"] = str(category_id)
    resp = client.post(f"{URL}/{obligation_id}/accrue", json=body, headers=headers)
    assert resp.status_code == expect, resp.json()
    return resp.json()


class TestIndividualAccrue:
    """Causacion individual por obligacion + tramo de cierre del mes en curso.

    El tramo usa capital $9M @ 2% → $6.000/dia exactos (cero ambiguedad de
    redondeo). Los tests de tramo hacen branch si hoy es dia 1 en Bogota
    (payoff mismo dia = 0 dias devengados → no hay tramo que causar).
    """

    def _payoff_today(self, client, org_headers, db, org_id, name, direction="payable"):
        """Obligacion con payoff hoy: desembolso $9M dia 1 del mes en curso,
        abono/recaudo total hoy → capital $0, tramo = $6.000 × (dia−1)."""
        tp = _obligation_tp(db, org_id, name)
        acc = _account(db, org_id, f"Caja {name}", balance=50_000_000)
        ob = _create_obligation(
            client, org_headers, tp.id, direction=direction,
            account_id=acc.id, amount=9_000_000, date=f"{_period(0)}-01",
        )
        _action(client, org_headers, ob["id"], "capital-payment",
                amount=9_000_000, account_id=acc.id,
                date=_today_bogota().strftime("%Y-%m-%d"))
        return tp, acc, ob

    def test_individual_accrues_only_this_obligation(
        self, client, org_headers, db_session, test_organization
    ):
        """Causar UNA obligacion no toca las demas; el batch queda con el resto."""
        org_id = test_organization.id
        tp_a = _obligation_tp(db_session, org_id, "Individual A")
        tp_b = _obligation_tp(db_session, org_id, "Individual B")
        acc = _account(db_session, org_id, "Caja Individual")
        cat = _expense_cat(db_session, org_id)
        ob_a = _create_obligation(client, org_headers, tp_a.id, direction="payable",
                                  account_id=acc.id, amount=10_000_000, date=_date_in(2, 1))
        ob_b = _create_obligation(client, org_headers, tp_b.id, direction="payable",
                                  account_id=acc.id, amount=5_000_000, date=_date_in(1, 1))

        preview = _ind_preview(client, org_headers, ob_a["id"])
        assert [i["period"] for i in preview["items"]] == [_period(2), _period(1)]
        assert all(float(i["amount"]) == 200_000 for i in preview["items"])
        assert preview["current_tranche"] is None  # capital vigente > 0
        assert preview["has_payable"] is True

        result = _ind_accrue(client, org_headers, ob_a["id"], category_id=cat.id)
        assert result["created_count"] == 2
        assert float(result["total_payable"]) == 400_000

        ob_a_f = _get_obligation(client, org_headers, ob_a["id"])
        assert float(ob_a_f["pending_interest"]) == 400_000
        assert ob_a_f["last_accrued_period"] == _period(1)
        ob_b_f = _get_obligation(client, org_headers, ob_b["id"])
        assert float(ob_b_f["pending_interest"]) == 0
        assert ob_b_f["last_accrued_period"] is None

        # El batch global ya solo ofrece la obligacion B
        pending = _pending(client, org_headers)
        assert {i["obligation_id"] for i in pending["items"]} == {ob_b["id"]}

    def test_individual_accrue_requires_category_for_payable(
        self, client, org_headers, db_session, test_organization
    ):
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Sin Categoria Ind")
        acc = _account(db_session, org_id, "Caja SCI")
        ob = _create_obligation(client, org_headers, tp.id, direction="payable",
                                account_id=acc.id, amount=10_000_000, date=_date_in(1, 1))
        result = _ind_accrue(client, org_headers, ob["id"], expect=400)
        assert "categoría" in result["detail"]

    def test_individual_accrue_nothing_pending(
        self, client, org_headers, db_session, test_organization
    ):
        """Sin vencidos y sin flag de tramo → 400 con mensaje claro."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Nada Pendiente")
        acc = _account(db_session, org_id, "Caja NP")
        cat = _expense_cat(db_session, org_id)
        ob = _create_obligation(client, org_headers, tp.id, direction="payable",
                                account_id=acc.id, amount=10_000_000,
                                date=f"{_period(0)}-01")
        result = _ind_accrue(client, org_headers, ob["id"], category_id=cat.id, expect=400)
        assert "No hay intereses pendientes" in result["detail"]

    def test_tranche_requires_zero_capital(
        self, client, org_headers, db_session, test_organization
    ):
        """Con capital vigente el tramo NO se ofrece ni se puede causar."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Capital Vivo")
        acc = _account(db_session, org_id, "Caja CV")
        cat = _expense_cat(db_session, org_id)
        ob = _create_obligation(client, org_headers, tp.id, direction="payable",
                                account_id=acc.id, amount=10_000_000, date=_date_in(1, 1))
        preview = _ind_preview(client, org_headers, ob["id"])
        assert preview["current_tranche"] is None
        result = _ind_accrue(client, org_headers, ob["id"], category_id=cat.id,
                             tranche=True, expect=400)
        assert "capital en $0" in result["detail"]

    def test_closing_tranche_math_and_freeze(
        self, client, org_headers, db_session, test_organization
    ):
        """Payoff hoy: tramo = $6.000 × (dia−1); tras causarlo, el retro guard
        congela los movimientos de capital del mes (composicion gratis)."""
        org_id = test_organization.id
        day = _today_bogota().day
        cat = _expense_cat(db_session, org_id)
        tp, acc, ob = self._payoff_today(client, org_headers, db_session, org_id, "Tramo Math")

        preview = _ind_preview(client, org_headers, ob["id"])
        if day == 1:
            assert preview["current_tranche"] is None
            _ind_accrue(client, org_headers, ob["id"], category_id=cat.id,
                        tranche=True, expect=400)
            return
        expected = D(6_000 * (day - 1))
        tranche = preview["current_tranche"]
        assert tranche is not None and tranche["period"] == _period(0)
        assert D(str(tranche["amount"])) == expected

        result = _ind_accrue(client, org_headers, ob["id"], category_id=cat.id, tranche=True)
        assert result["created_count"] == 1
        assert D(str(result["total_payable"])) == expected
        ob_f = _get_obligation(client, org_headers, ob["id"])
        assert D(str(ob_f["pending_interest"])) == expected
        assert ob_f["last_accrued_period"] == _period(0)

        # Freeze: desembolso adicional fechado hoy (mes ya causado) → 400
        resp = _action(client, org_headers, ob["id"], "disbursement",
                       amount=1_000_000, account_id=acc.id,
                       date=_today_bogota().strftime("%Y-%m-%d"), expect=400)
        assert "ya tiene intereses causados" in resp["detail"]

        # Summary: la proyeccion del mes en curso NO duplica el tramo causado
        # (el monto ya vive en pendientes)
        resp = client.get(f"{URL}/summary", headers=org_headers)
        assert resp.status_code == 200
        payable = resp.json()["payable"]
        assert float(payable["current_month_projection"]) == 0
        assert D(str(payable["total_pending_interest"])) == expected

    def test_tranche_twice_blocked(
        self, client, org_headers, db_session, test_organization
    ):
        org_id = test_organization.id
        day = _today_bogota().day
        if day == 1:
            return  # sin tramo posible el dia 1 — cubierto por math_and_freeze
        cat = _expense_cat(db_session, org_id)
        tp, acc, ob = self._payoff_today(client, org_headers, db_session, org_id, "Tramo Doble")
        _ind_accrue(client, org_headers, ob["id"], category_id=cat.id, tranche=True)
        result = _ind_accrue(client, org_headers, ob["id"], category_id=cat.id,
                             tranche=True, expect=400)
        assert "ya está causado" in result["detail"]

    def test_annul_tranche_frees_period_and_reaccrues_same(
        self, client, org_headers, db_session, test_organization
    ):
        """Anular el tramo libera el mes en curso y se puede re-causar identico."""
        org_id = test_organization.id
        day = _today_bogota().day
        if day == 1:
            return
        cat = _expense_cat(db_session, org_id)
        tp, acc, ob = self._payoff_today(client, org_headers, db_session, org_id, "Tramo Anul")
        first = _ind_accrue(client, org_headers, ob["id"], category_id=cat.id, tranche=True)

        accrual = db_session.execute(
            select(MoneyMovement).where(
                MoneyMovement.financial_obligation_id == ob["id"],
                MoneyMovement.movement_type == "obligation_interest_accrual",
                MoneyMovement.status == "confirmed",
            )
        ).scalar_one()
        assert "tramo de cierre" in accrual.description
        _annul(client, org_headers, accrual.id)

        ob_f = _get_obligation(client, org_headers, ob["id"])
        assert float(ob_f["pending_interest"]) == 0
        assert ob_f["last_accrued_period"] is None

        again = _ind_accrue(client, org_headers, ob["id"], category_id=cat.id, tranche=True)
        assert again["total_payable"] == first["total_payable"]

    def test_settle_after_tranche_paid(
        self, client, org_headers, db_session, test_organization
    ):
        """Flujo payoff completo: causar tramo → pagar intereses → liquidar."""
        org_id = test_organization.id
        day = _today_bogota().day
        cat = _expense_cat(db_session, org_id)
        tp, acc, ob = self._payoff_today(client, org_headers, db_session, org_id, "Payoff Full")
        if day > 1:
            _ind_accrue(client, org_headers, ob["id"], category_id=cat.id, tranche=True)
            _action(client, org_headers, ob["id"], "interest-payment",
                    amount=6_000 * (day - 1), account_id=acc.id,
                    date=_today_bogota().strftime("%Y-%m-%d"))
        resp = client.post(f"{URL}/{ob['id']}/settle", headers=org_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "settled"
        # Tercero en 0: el ciclo completo cerro redondo
        db_session.expire_all()
        tp_f = db_session.get(ThirdParty, tp.id)
        assert tp_f.current_balance == 0

    def test_batch_next_month_skips_tranche_period(
        self, client, org_headers, db_session, test_organization, monkeypatch
    ):
        """Anti doble conteo: el batch del mes siguiente NO re-ofrece el periodo
        ya causado como tramo de cierre (la gemela sin tramo SI aparece)."""
        org_id = test_organization.id
        day = _today_bogota().day
        cat = _expense_cat(db_session, org_id)
        tp1, acc1, ob1 = self._payoff_today(client, org_headers, db_session, org_id, "Con Tramo")
        if day > 1:
            _ind_accrue(client, org_headers, ob1["id"], category_id=cat.id, tranche=True)
        tp2, acc2, ob2 = self._payoff_today(client, org_headers, db_session, org_id, "Gemela")

        import app.services.financial_obligation as fo_mod
        from app.services.financial_obligation import financial_obligation as svc
        next_p = _period(-1)  # viajar al mes siguiente
        monkeypatch.setattr(fo_mod, "_current_period", lambda: next_p)

        db_session.expire_all()
        pending = svc.get_pending_accruals(db_session, org_id)
        offered = {(str(i.obligation_id), i.period) for i in pending.items}
        if day > 1:
            assert (ob2["id"], _period(0)) in offered      # gemela: julio pendiente
            assert (ob1["id"], _period(0)) not in offered  # tramo causado: sin duplicado
        else:
            assert (ob1["id"], _period(0)) not in offered
            assert (ob2["id"], _period(0)) not in offered

    def test_receivable_tranche_mirror(
        self, client, org_headers, db_session, test_organization
    ):
        """Espejo receivable: tramo sin categoria de gasto (es ingreso financiero)."""
        org_id = test_organization.id
        day = _today_bogota().day
        if day == 1:
            return
        tp, acc, ob = self._payoff_today(
            client, org_headers, db_session, org_id, "Prestamo Tramo",
            direction="receivable",
        )
        result = _ind_accrue(client, org_headers, ob["id"], tranche=True)
        assert D(str(result["total_receivable"])) == D(6_000 * (day - 1))
        accrual = db_session.execute(
            select(MoneyMovement).where(
                MoneyMovement.financial_obligation_id == ob["id"],
                MoneyMovement.movement_type == "loan_interest_accrual",
                MoneyMovement.status == "confirmed",
            )
        ).scalar_one()
        assert accrual.expense_category_id is None

    def test_individual_accrue_rbac(self, client, org_headers2):
        """Viewer: preview OK (view), causar 403 (manage)."""
        from uuid import uuid4
        fake = uuid4()
        resp = client.get(f"{URL}/{fake}/accrue-preview", headers=org_headers2)
        assert resp.status_code == 404  # paso el permiso de view, recurso no existe
        resp = client.post(
            f"{URL}/{fake}/accrue",
            json={"include_current_tranche": False},
            headers=org_headers2,
        )
        assert resp.status_code == 403


# ===========================================================================
# Walk multi-mes con invariantes (analogo del stress walk de Modelo L #65)
# ===========================================================================

class TestObligationWalk:
    """Combinaciones complejas: causar + pagar + anular + re-causar intercalados.

    Tras CADA operacion se verifican 4 invariantes:
    1. tp.current_balance == signo_direccion × (capital + pendientes)
    2. capital == Σ desembolsos − Σ abonos (reconstruido de MMs confirmados)
    3. pendientes == Σ causaciones − Σ pagos de intereses (idem)
    4. saldo corrido del estado de cuenta unificado == tp.current_balance

    Los montos de interes esperados estan calculados A MANO (no contra el
    motor) para que un bug del motor no se auto-valide.
    """

    def _assert_invariants(self, client, org_headers, db, ob_id, tp_id, direction, step=""):
        from uuid import UUID as _UUID
        from app.models.financial_obligation import FinancialObligation

        db.expire_all()
        ob = db.get(FinancialObligation, _UUID(ob_id))
        tp = db.get(ThirdParty, _UUID(str(tp_id)))
        sign = -1 if direction == "payable" else 1

        # 1. Invariante de signo (plan §3.3): Δtercero == signo × (capital + pendientes)
        expected_tp = sign * (ob.capital_balance + ob.pending_interest)
        assert tp.current_balance == expected_tp, (
            f"[{step}] tp={tp.current_balance} != {expected_tp} "
            f"(capital={ob.capital_balance}, pendientes={ob.pending_interest})"
        )

        # 2-3. Contadores == reconstruccion desde MMs confirmados
        movements = db.execute(
            select(MoneyMovement).where(
                MoneyMovement.financial_obligation_id == ob.id,
                MoneyMovement.status == "confirmed",
            )
        ).scalars().all()
        disb = {"obligation_disbursement", "loan_disbursement"}
        cap_pay = {"obligation_capital_payment", "loan_capital_collection"}
        accr = {"obligation_interest_accrual", "loan_interest_accrual"}
        int_pay = {"obligation_interest_payment", "loan_interest_collection"}
        capital_rebuilt = sum((m.amount for m in movements if m.movement_type in disb), D("0")) \
            - sum((m.amount for m in movements if m.movement_type in cap_pay), D("0"))
        pending_rebuilt = sum((m.amount for m in movements if m.movement_type in accr), D("0")) \
            - sum((m.amount for m in movements if m.movement_type in int_pay), D("0"))
        assert ob.capital_balance == capital_rebuilt, f"[{step}] capital contador != MMs"
        assert ob.pending_interest == pending_rebuilt, f"[{step}] pendientes contador != MMs"

        # 4. Estado de cuenta unificado: saldo corrido final == saldo vivo
        resp = client.get(
            f"/api/v1/money-movements/third-party/{tp.id}",
            params={"date_from": _date_in(5, 1)},
            headers=org_headers,
        )
        assert resp.status_code == 200
        entries = resp.json()["items"]
        if entries:
            assert entries[-1]["balance_after"] == float(tp.current_balance), (
                f"[{step}] statement={entries[-1]['balance_after']} != tp={tp.current_balance}"
            )

    def test_payable_multi_month_walk(self, client, org_headers, db_session, test_organization):
        """Payable 2%: 3 meses con abonos/desembolsos intercalados, causacion
        batch, pago parcial, anulacion de causacion intermedia, re-causacion,
        guards en medio, y settle — invariantes tras cada paso."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Walk Payable")
        acc = _account(db_session, org_id, "Caja Walk", balance=200_000_000)
        cat = _expense_cat(db_session, org_id)
        check = lambda step: self._assert_invariants(
            client, org_headers, db_session, ob["id"], tp.id, "payable", step
        )

        # M-3: desembolso $30M dia 1, abono $12M dia 10, adicional $6M dia 20
        ob = _create_obligation(
            client, org_headers, tp.id, direction="payable",
            account_id=acc.id, amount=30_000_000, date=_date_in(3, 1),
        )
        check("desembolso inicial")
        _action(client, org_headers, ob["id"], "capital-payment",
                amount=12_000_000, account_id=acc.id, date=_date_in(3, 10))
        check("abono M-3")
        _action(client, org_headers, ob["id"], "disbursement",
                amount=6_000_000, account_id=acc.id, date=_date_in(3, 20))
        check("desembolso adicional M-3")

        # M-1: abono total $24M el dia 16 (capital queda en 0 desde ese dia)
        _action(client, org_headers, ob["id"], "capital-payment",
                amount=24_000_000, account_id=acc.id, date=_date_in(1, 16))
        check("abono final M-1")

        # Preview: 3 periodos con montos calculados A MANO
        #   M-3: 30M×9d + 18M×10d + 24M×11d @2%/30 = 180.000+120.000+176.000 = 476.000
        #   M-2: 24M×30d @2% = 480.000
        #   M-1: 24M×15d @2%/30 = 240.000 (dia 16 en adelante capital 0)
        pending = _pending(client, org_headers)
        mine = {i["period"]: i for i in pending["items"] if i["obligation_id"] == ob["id"]}
        assert float(mine[_period(3)]["amount"]) == 476_000
        assert "9d" in mine[_period(3)]["breakdown"] and "11d" in mine[_period(3)]["breakdown"]
        assert float(mine[_period(2)]["amount"]) == 480_000
        assert float(mine[_period(1)]["amount"]) == 240_000

        result = _accrue(client, org_headers, expense_category_id=cat.id)
        assert result["created_count"] == 3
        assert float(result["total_payable"]) == 1_196_000
        check("causacion 3 meses")

        # Guards en medio de la caminata:
        # (a) abono retroactivo a mes causado → 400
        _action(client, org_headers, ob["id"], "capital-payment",
                amount=1_000, account_id=acc.id, date=_date_in(2, 5), expect=400)
        # (b) guard espejo: anular el abono de M-3 (mes ya causado) → 400
        abono_m3 = db_session.execute(
            select(MoneyMovement).where(
                MoneyMovement.financial_obligation_id == ob["id"],
                MoneyMovement.movement_type == "obligation_capital_payment",
                MoneyMovement.amount == D("12000000"),
            )
        ).scalar_one()
        _annul(client, org_headers, abono_m3.id, expect=400)
        check("guards no mutaron nada")

        # Pago parcial de intereses $500K → pendientes 696.000
        _action(client, org_headers, ob["id"], "interest-payment",
                amount=500_000, account_id=acc.id, date=_date_in(0, 5))
        check("pago parcial intereses")

        # Anular la causacion de M-2 (480K ≤ 696K pendientes → permitido)
        accrual_m2 = db_session.execute(
            select(MoneyMovement).where(
                MoneyMovement.financial_obligation_id == ob["id"],
                MoneyMovement.obligation_period == _period(2),
                MoneyMovement.movement_type == "obligation_interest_accrual",
                MoneyMovement.status == "confirmed",
            )
        ).scalar_one()
        _annul(client, org_headers, accrual_m2.id)
        check("anulacion causacion M-2")
        ob_f = _get_obligation(client, org_headers, ob["id"])
        assert float(ob_f["pending_interest"]) == 216_000
        # last_accrued sigue en M-1 (el periodo anulado no era el ultimo)
        assert ob_f["last_accrued_period"] == _period(1)

        # M-2 reaparece pendiente y se re-causa con el MISMO monto (idempotencia del calculo)
        pending2 = _pending(client, org_headers)
        again = [i for i in pending2["items"] if i["obligation_id"] == ob["id"]]
        assert len(again) == 1 and again[0]["period"] == _period(2)
        assert float(again[0]["amount"]) == 480_000
        result2 = _accrue(client, org_headers, expense_category_id=cat.id)
        assert result2["created_count"] == 1
        check("re-causacion M-2")

        # Pagar el resto ($696K) y cerrar
        _action(client, org_headers, ob["id"], "interest-payment",
                amount=696_000, account_id=acc.id, date=_date_in(0, 6))
        check("pago total intereses")
        resp = client.post(f"{URL}/{ob['id']}/settle", headers=org_headers)
        assert resp.status_code == 200
        check("settle")

        # P&L del rango completo: gasto financiero == 1.196.000 (3 causaciones vivas)
        resp = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": _date_in(3, 1),
                    "date_to": f"{_period(1)}-{_days_in_period(_period(1)):02d}"},
            headers=org_headers,
        )
        assert resp.json()["operating_expenses"] == 1_196_000

    def test_receivable_walk_with_annulled_collection(self, client, org_headers, db_session, test_organization):
        """Receivable: causar 2 meses, recaudar, ANULAR el recaudo, re-recaudar,
        recaudo de capital y settle — espejo de signos con los mismos invariantes."""
        org_id = test_organization.id
        tp = _obligation_tp(db_session, org_id, "Walk Receivable")
        acc = _account(db_session, org_id, "Caja Walk R", balance=100_000_000)
        check = lambda step: self._assert_invariants(
            client, org_headers, db_session, ob["id"], tp.id, "receivable", step
        )

        # M-2 dia 1: prestamos $10M; M-1 dia 16: adicional $5M
        ob = _create_obligation(
            client, org_headers, tp.id, direction="receivable",
            account_id=acc.id, amount=10_000_000, date=_date_in(2, 1),
        )
        check("desembolso prestamo")
        _action(client, org_headers, ob["id"], "disbursement",
                amount=5_000_000, account_id=acc.id, date=_date_in(1, 16))
        check("desembolso adicional M-1")

        # A mano: M-2 = 10M×2% = 200.000; M-1 = 10M×15d + 15M×15d @2%/30 = 100.000+150.000 = 250.000
        result = _accrue(client, org_headers)
        assert result["created_count"] == 2
        assert float(result["total_receivable"]) == 450_000
        check("causacion 2 meses")

        # Recaudo total → anulado → pendientes restaurados → re-recaudo
        collection = _action(client, org_headers, ob["id"], "interest-payment",
                             amount=450_000, account_id=acc.id, date=_date_in(0, 5))
        check("recaudo intereses")
        _annul(client, org_headers, collection["id"])
        check("anulacion recaudo")
        assert float(_get_obligation(client, org_headers, ob["id"])["pending_interest"]) == 450_000
        _action(client, org_headers, ob["id"], "interest-payment",
                amount=450_000, account_id=acc.id, date=_date_in(0, 6))
        check("re-recaudo")

        # Recaudo de capital total y settle
        _action(client, org_headers, ob["id"], "capital-payment",
                amount=15_000_000, account_id=acc.id, date=_date_in(0, 7))
        check("recaudo capital total")
        resp = client.post(f"{URL}/{ob['id']}/settle", headers=org_headers)
        assert resp.status_code == 200
        check("settle")


# ===========================================================================
# RBAC
# ===========================================================================

class TestRBAC:

    def test_viewer_can_view_not_manage(self, client, org_headers2, db_session, test_organization2):
        """Viewer (org2): lista 200, crear 403."""
        resp = client.get(f"{URL}/", headers=org_headers2)
        assert resp.status_code == 200

        tp = _obligation_tp(db_session, test_organization2.id, "RBAC TP")
        resp = client.post(
            f"{URL}/", headers=org_headers2,
            json={
                "third_party_id": str(tp.id), "direction": "payable",
                "monthly_rate": "2.00", "mode": "from_balance",
            },
        )
        assert resp.status_code == 403

    def test_viewer_cannot_accrue(self, client, org_headers2, test_organization2):
        resp = client.post(f"{URL}/accrue-pending", json={}, headers=org_headers2)
        assert resp.status_code == 403
