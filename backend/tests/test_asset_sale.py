"""
Tests para Venta de Activos Fijos (plan-venta-activos-fijos.md v1.0 QA-GO).

Cubre: happy paths (cuenta/tercero × ganancia/pérdida), validaciones y guards,
warning de depreciaciones pendientes, línea P&L "Ganancia/Pérdida por Venta de
Activos" (rango, anulada excluida, suma al gross, cascada #71), conciliación
residual cero CON venta, cash flow (inflow solo cuenta, tercero before==after),
golden as-of corte-de-ayer sin restatement, estado de cuenta del comprador,
anulación round-trip (status derivado active/fully_depreciated), bloqueo desde
Tesorería y RBAC.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.expense_category import ExpenseCategory
from app.models.money_account import MoneyAccount
from app.models.money_movement import MoneyMovement
from app.models.fixed_asset import FixedAsset
from app.models.third_party import ThirdParty
from app.models.third_party_category import ThirdPartyCategory, ThirdPartyCategoryAssignment


BASE_URL = "/api/v1/fixed-assets"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sale_category(db_session: Session, test_organization) -> ExpenseCategory:
    cat = ExpenseCategory(
        name="Depreciación Equipos Venta",
        is_direct_expense=False,
        organization_id=test_organization.id,
    )
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


@pytest.fixture
def sale_account(db_session: Session, test_organization) -> MoneyAccount:
    acc = MoneyAccount(
        name="Cuenta Principal Venta FA",
        account_type="bank",
        current_balance=Decimal("5000000000"),
        initial_balance=Decimal("5000000000"),
        organization_id=test_organization.id,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


def _make_tp(db_session, org_id, name, behavior) -> ThirdParty:
    tp = ThirdParty(
        name=name,
        organization_id=org_id,
        current_balance=Decimal("0"),
        initial_balance=Decimal("0"),
    )
    db_session.add(tp)
    db_session.flush()
    cat = ThirdPartyCategory(
        name=f"Cat {name}",
        behavior_type=behavior,
        organization_id=org_id,
    )
    db_session.add(cat)
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(third_party_id=tp.id, category_id=cat.id))
    db_session.commit()
    db_session.refresh(tp)
    return tp


@pytest.fixture
def sale_buyer(db_session: Session, test_organization) -> ThirdParty:
    """Comprador genérico — 'cualquier tercero' (respuesta del cliente)."""
    return _make_tp(db_session, test_organization.id, "Comprador Activos S.A.", "generic")


@pytest.fixture
def sale_provision(db_session: Session, test_organization) -> ThirdParty:
    return _make_tp(db_session, test_organization.id, "Provisión Venta FA", "provision")


@pytest.fixture
def sale_liability(db_session: Session, test_organization) -> ThirdParty:
    return _make_tp(db_session, test_organization.id, "Pasivo Venta FA", "liability")


def _create_asset(client, org_headers, sale_category, sale_account, **overrides):
    """Activo default: 100M, rate 1% → cuota 1M, salvage 0. Pagado de cuenta."""
    payload = {
        "name": "Camión Venta FA",
        "asset_code": "VN-001",
        "purchase_date": "2026-01-01",
        "purchase_value": 100000000,
        "salvage_value": 0,
        "depreciation_rate": 1.0,
        "depreciation_start_date": "2026-01-01",
        "expense_category_id": str(sale_category.id),
        "source_account_id": str(sale_account.id),
    }
    payload.update(overrides)
    resp = client.post(BASE_URL + "/", json=payload, headers=org_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _sell(client, org_headers, asset_id, **overrides):
    payload = {"sale_price": 80000000}
    payload.update(overrides)
    return client.post(f"{BASE_URL}/{asset_id}/sell", json=payload, headers=org_headers)


def _annul_sale(client, org_headers, asset_id, reason="Error de captura"):
    return client.post(
        f"{BASE_URL}/{asset_id}/sale/annul",
        json={"reason": reason}, headers=org_headers,
    )


def _pnl(client, org_headers, **params):
    resp = client.get("/api/v1/reports/profit-and-loss", params=params, headers=org_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------

class TestSellHappyPaths:

    def test_sell_to_account_with_loss(
        self, client: TestClient, org_headers, sale_category, sale_account, db_session,
    ):
        """Venta por cuenta bajo el libro: entra el precio, sale_gain negativo,
        libro CONGELADO (D1: current_value intacto, cero depreciaciones nuevas)."""
        asset = _create_asset(client, org_headers, sale_category, sale_account)
        # Tras compra: cuenta 5.000M − 100M = 4.900M
        resp = _sell(
            client, org_headers, asset["id"],
            sale_price=80000000, account_id=str(sale_account.id),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()

        assert data["status"] == "disposed"
        assert data["disposal_reason"] == "Venta"
        assert data["sale_price"] == 80000000
        assert data["sale_gain"] == -20000000  # 80M − 100M
        assert data["sale_active"] is True
        # D1: libro congelado, sin depreciación acelerada
        assert data["current_value"] == 100000000
        assert data["accumulated_depreciation"] == 0
        assert data["depreciations"] == []

        db_session.expire_all()
        acc = db_session.get(MoneyAccount, sale_account.id)
        assert acc.current_balance == Decimal("4980000000")  # 4.900M + 80M
        mov = db_session.get(MoneyMovement, UUID(data["sale_movement_id"]))
        assert mov.movement_type == "asset_sale_collection"
        assert mov.amount == Decimal("80000000")
        assert mov.status == "confirmed"
        assert mov.account_id is not None and mov.third_party_id is None

    def test_sell_to_third_party_with_gain(
        self, client, org_headers, sale_category, sale_account, sale_buyer, db_session,
    ):
        """Venta a crédito sobre el libro: CxC +precio, ganancia positiva, caja intacta."""
        asset = _create_asset(client, org_headers, sale_category, sale_account)
        resp = _sell(
            client, org_headers, asset["id"],
            sale_price=130000000, third_party_id=str(sale_buyer.id),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["sale_gain"] == 30000000  # 130M − 100M
        assert data["current_value"] == 100000000  # congelado

        db_session.expire_all()
        tp = db_session.get(ThirdParty, sale_buyer.id)
        assert tp.current_balance == Decimal("130000000")  # nos debe (CxC)
        acc = db_session.get(MoneyAccount, sale_account.id)
        assert acc.current_balance == Decimal("4900000000")  # sin cambio
        mov = db_session.get(MoneyMovement, UUID(data["sale_movement_id"]))
        assert mov.movement_type == "asset_sale_receivable"
        assert mov.account_id is None and mov.third_party_id == sale_buyer.id

    def test_sell_at_book_value_zero_gain(
        self, client, org_headers, sale_category, sale_account,
    ):
        asset = _create_asset(client, org_headers, sale_category, sale_account)
        resp = _sell(
            client, org_headers, asset["id"],
            sale_price=100000000, account_id=str(sale_account.id),
        )
        assert resp.status_code == 201
        assert resp.json()["sale_gain"] == 0

    def test_sell_negative_balance_buyer_allowed(
        self, client, org_headers, sale_category, sale_account, sale_buyer, db_session,
    ):
        """Filosofía #76: un tercero puede quedar donde su saldo lo lleve —
        la CxC de la venta se suma sin restricción de signo."""
        sale_buyer.current_balance = Decimal("-50000000")
        db_session.commit()
        asset = _create_asset(client, org_headers, sale_category, sale_account)
        resp = _sell(
            client, org_headers, asset["id"],
            sale_price=30000000, third_party_id=str(sale_buyer.id),
        )
        assert resp.status_code == 201
        db_session.expire_all()
        tp = db_session.get(ThirdParty, sale_buyer.id)
        assert tp.current_balance == Decimal("-20000000")  # −50M + 30M

    def test_sell_with_pending_depreciation_warns(
        self, client, org_headers, sale_category, sale_account,
    ):
        """Meses vencidos sin aplicar → warning informativo, nunca bloqueo."""
        asset = _create_asset(client, org_headers, sale_category, sale_account)
        resp = _sell(
            client, org_headers, asset["id"],
            sale_price=90000000, account_id=str(sale_account.id),
        )
        assert resp.status_code == 201
        warnings = resp.json().get("warnings") or []
        assert warnings, "esperaba warning de depreciación pendiente"
        assert "sin aplicar" in warnings[0]


# ---------------------------------------------------------------------------
# Validaciones y guards
# ---------------------------------------------------------------------------

class TestSellValidations:

    def test_xor_counterpart_required(
        self, client, org_headers, sale_category, sale_account, sale_buyer,
    ):
        asset = _create_asset(client, org_headers, sale_category, sale_account)
        # Ninguna contrapartida
        resp = _sell(client, org_headers, asset["id"], sale_price=1000)
        assert resp.status_code == 422
        # Ambas
        resp = _sell(
            client, org_headers, asset["id"], sale_price=1000,
            account_id=str(sale_account.id), third_party_id=str(sale_buyer.id),
        )
        assert resp.status_code == 422

    def test_price_zero_or_negative_rejected(
        self, client, org_headers, sale_category, sale_account,
    ):
        asset = _create_asset(client, org_headers, sale_category, sale_account)
        for price in (0, -5):
            resp = _sell(
                client, org_headers, asset["id"],
                sale_price=price, account_id=str(sale_account.id),
            )
            assert resp.status_code == 422

    def test_disposed_asset_rejected(
        self, client, org_headers, sale_category, sale_account,
    ):
        asset = _create_asset(client, org_headers, sale_category, sale_account)
        resp = client.post(
            f"{BASE_URL}/{asset['id']}/dispose",
            json={"reason": "Chatarra"}, headers=org_headers,
        )
        assert resp.status_code == 200
        resp = _sell(
            client, org_headers, asset["id"],
            sale_price=1000, account_id=str(sale_account.id),
        )
        assert resp.status_code == 400
        assert "disposed" in resp.json()["detail"]

    def test_cancelled_asset_rejected(
        self, client, org_headers, sale_category, sale_account,
    ):
        asset = _create_asset(client, org_headers, sale_category, sale_account)
        resp = client.post(
            f"{BASE_URL}/{asset['id']}/cancel",
            json={}, headers=org_headers,
        )
        assert resp.status_code == 200, resp.text
        resp = _sell(
            client, org_headers, asset["id"],
            sale_price=1000, account_id=str(sale_account.id),
        )
        assert resp.status_code == 400

    def test_provision_and_liability_buyer_rejected(
        self, client, org_headers, sale_category, sale_account,
        sale_provision, sale_liability,
    ):
        """Espejo #32: provision y liability no son compradores válidos."""
        asset = _create_asset(client, org_headers, sale_category, sale_account)
        for tp in (sale_provision, sale_liability):
            resp = _sell(
                client, org_headers, asset["id"],
                sale_price=1000, third_party_id=str(tp.id),
            )
            assert resp.status_code == 404, f"{tp.name}: {resp.text}"


# ---------------------------------------------------------------------------
# P&L — línea "Ganancia/Pérdida por Venta de Activos"
# ---------------------------------------------------------------------------

class TestSalePnl:

    def test_pnl_line_in_period_and_gross(
        self, client, org_headers, sale_category, sale_account, db_session,
    ):
        """La línea aparece en el período de la venta (fecha HOY), suma al
        total_gross_profit y respeta la cascada #71."""
        today = date.today()
        base = _pnl(
            client, org_headers,
            date_from=today.isoformat(), date_to=today.isoformat(),
        )
        asset = _create_asset(client, org_headers, sale_category, sale_account)
        resp = _sell(
            client, org_headers, asset["id"],
            sale_price=130000000, account_id=str(sale_account.id),
        )
        assert resp.status_code == 201

        pnl = _pnl(
            client, org_headers,
            date_from=today.isoformat(), date_to=today.isoformat(),
        )
        assert pnl["asset_sale_gain"] == pytest.approx(30000000, abs=1)
        assert pnl["total_gross_profit"] == pytest.approx(
            base["total_gross_profit"] + 30000000, abs=1,
        )
        # Cascada #71: identidades intactas con la línea ≠ 0
        assert pnl["gross_profit_before_financial"] == pytest.approx(
            pnl["total_gross_profit"] - pnl["interest_income"], abs=1,
        )
        assert pnl["net_profit"] == pytest.approx(
            pnl["operating_result"] + pnl["interest_income"] - pnl["expenses_financial"],
            abs=1,
        )

        # Fuera del rango: la línea no aparece
        yesterday = (today - timedelta(days=1)).isoformat()
        pnl_prev = _pnl(client, org_headers, date_from=yesterday, date_to=yesterday)
        assert pnl_prev["asset_sale_gain"] == pytest.approx(0, abs=1)

    def test_annulled_sale_out_of_pnl(
        self, client, org_headers, sale_category, sale_account,
    ):
        """Anular la venta la saca del P&L (gobierna el status del MM,
        las columnas sale_* quedan como rastro)."""
        today = date.today().isoformat()
        asset = _create_asset(client, org_headers, sale_category, sale_account)
        _sell(
            client, org_headers, asset["id"],
            sale_price=130000000, account_id=str(sale_account.id),
        )
        resp = _annul_sale(client, org_headers, asset["id"])
        assert resp.status_code == 200

        pnl = _pnl(client, org_headers, date_from=today, date_to=today)
        assert pnl["asset_sale_gain"] == pytest.approx(0, abs=1)

    def test_reconciliation_residual_zero_with_sale(
        self, client, org_headers, sale_category, sale_account,
    ):
        """Test de oro extendido: con una venta con ganancia en el período,
        grand_total + las 7 líneas == utilidad neta del P&L (tolerancia $1)."""
        today = date.today().isoformat()
        asset = _create_asset(client, org_headers, sale_category, sale_account)
        _sell(
            client, org_headers, asset["id"],
            sale_price=130000000, account_id=str(sale_account.id),
        )
        resp = client.get(
            "/api/v1/reports/profitability-by-business-unit",
            params={"date_from": today, "date_to": today},
            headers=org_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        rec = data["pnl_reconciliation"]
        assert rec["asset_sale_gain"] == pytest.approx(30000000, abs=1)
        residual = (
            rec["pnl_net_profit"]
            - data["grand_total_net"]
            - rec["service_income"]
            - rec["interest_income"]
            - rec["transformation_net"]
            - rec["inventory_adjustment_net"]
            - rec["tp_adjustment_net"]
            - rec["oversell_cost_adjustment"]
            - rec["asset_sale_gain"]
        )
        assert abs(residual) < 1


# ---------------------------------------------------------------------------
# Cash flow y balance histórico
# ---------------------------------------------------------------------------

class TestSaleCashFlowAndAsOf:

    def test_cash_flow_inflow_only_for_account_sale(
        self, client, org_headers, sale_category, sale_account, sale_buyer,
    ):
        """Venta por cuenta = inflow con campo propio; venta por tercero no
        toca el cash flow (before == after)."""
        today = date.today().isoformat()

        def cash_flow():
            resp = client.get(
                "/api/v1/reports/cash-flow",
                params={"date_from": today, "date_to": today},
                headers=org_headers,
            )
            assert resp.status_code == 200
            return resp.json()

        asset_a = _create_asset(client, org_headers, sale_category, sale_account)
        asset_b = _create_asset(
            client, org_headers, sale_category, sale_account, asset_code="VN-002",
        )
        base = cash_flow()

        # Venta a TERCERO: cash flow idéntico
        _sell(
            client, org_headers, asset_a["id"],
            sale_price=70000000, third_party_id=str(sale_buyer.id),
        )
        after_tp = cash_flow()
        assert after_tp["total_inflows"] == base["total_inflows"]
        assert after_tp["inflows"]["asset_sale_collections"] == 0
        assert after_tp["closing_balance"] == base["closing_balance"]

        # Venta por CUENTA: inflow por el precio
        _sell(
            client, org_headers, asset_b["id"],
            sale_price=80000000, account_id=str(sale_account.id),
        )
        after_acc = cash_flow()
        assert after_acc["inflows"]["asset_sale_collections"] == pytest.approx(80000000, abs=1)
        assert after_acc["total_inflows"] == pytest.approx(
            base["total_inflows"] + 80000000, abs=1,
        )

    def test_golden_asof_yesterday_stable(
        self, client, org_headers, sale_category, sale_account, db_session,
    ):
        """Golden corte-de-ayer (lección #67 H1): la venta de HOY no reescribe
        el balance de AYER; el corte de hoy refleja activo fuera + caja dentro."""
        asset = _create_asset(client, org_headers, sale_category, sale_account)
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        today = date.today().isoformat()

        def balance(as_of=None):
            params = {"as_of_date": as_of} if as_of else {}
            resp = client.get(
                "/api/v1/reports/balance-sheet", params=params, headers=org_headers,
            )
            assert resp.status_code == 200
            return resp.json()

        bs_yesterday_before = balance(yesterday)

        resp = _sell(
            client, org_headers, asset["id"],
            sale_price=130000000, account_id=str(sale_account.id),
        )
        assert resp.status_code == 201

        # AYER: ni el activo ni la caja se movieron un peso
        bs_yesterday_after = balance(yesterday)
        assert bs_yesterday_after["assets"]["fixed_assets"] == bs_yesterday_before["assets"]["fixed_assets"]
        assert bs_yesterday_after["assets"]["cash_and_bank"] == bs_yesterday_before["assets"]["cash_and_bank"]
        assert bs_yesterday_after["total_assets"] == bs_yesterday_before["total_assets"]

        # HOY (corte del día del evento) y VIVO: activo fuera, caja con el precio
        for bs in (balance(today), balance()):
            assert bs["assets"]["fixed_assets"] == bs_yesterday_before["assets"]["fixed_assets"] - 100000000
            assert bs["assets"]["cash_and_bank"] == pytest.approx(
                bs_yesterday_before["assets"]["cash_and_bank"] + 130000000, abs=1,
            )

    def test_statement_of_buyer_shows_sale(
        self, client, org_headers, sale_category, sale_account, sale_buyer,
    ):
        asset = _create_asset(client, org_headers, sale_category, sale_account)
        _sell(
            client, org_headers, asset["id"],
            sale_price=130000000, third_party_id=str(sale_buyer.id),
        )
        resp = client.get(
            f"/api/v1/money-movements/third-party/{sale_buyer.id}",
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        events = [
            e for e in data["items"]
            if e.get("event_type") == "asset_sale_receivable"
        ]
        assert len(events) == 1
        assert data["current_balance"] == pytest.approx(130000000, abs=1)
        # Saldo corrido: el último evento cierra en el saldo vivo
        assert events[0]["balance_after"] == pytest.approx(130000000, abs=1)


# ---------------------------------------------------------------------------
# Anulación
# ---------------------------------------------------------------------------

class TestSaleAnnul:

    def test_annul_round_trip_account(
        self, client, org_headers, sale_category, sale_account, db_session,
    ):
        """Round-trip: cuenta devuelta al peso, activo restaurado a active
        (libro a media vida), sale_* como rastro con sale_active=False."""
        asset = _create_asset(client, org_headers, sale_category, sale_account)
        db_session.expire_all()
        balance_before_sale = db_session.get(MoneyAccount, sale_account.id).current_balance

        _sell(
            client, org_headers, asset["id"],
            sale_price=130000000, account_id=str(sale_account.id),
        )
        resp = _annul_sale(client, org_headers, asset["id"])
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["status"] == "active"  # libro 100M > salvage 0 → derivado
        assert data["disposed_at"] is None
        assert data["disposal_reason"] is None
        assert data["current_value"] == 100000000
        # Rastro (QA nota 2): columnas pobladas pero venta NO vigente
        assert data["sale_price"] == 130000000
        assert data["sale_active"] is False

        db_session.expire_all()
        acc = db_session.get(MoneyAccount, sale_account.id)
        assert acc.current_balance == balance_before_sale
        mov = db_session.get(MoneyMovement, UUID(data["sale_movement_id"]))
        assert mov.status == "annulled"

    def test_annul_round_trip_third_party_fully_depreciated(
        self, client, org_headers, sale_category, sale_account, sale_buyer,
        db_session, test_organization, test_user,
    ):
        """Activo totalmente depreciado vendido a tercero: el annul restaura
        status DERIVADO fully_depreciated y devuelve la CxC al peso."""
        from app.services.fixed_asset import fixed_asset as fa_service

        asset = _create_asset(
            client, org_headers, sale_category, sale_account,
            purchase_value=2000000, depreciation_rate=50.0, asset_code="VN-003",
        )
        # 2 cuotas de 1M → fully_depreciated
        fa_service.apply_depreciation(
            db_session, UUID(asset["id"]), test_organization.id, test_user.id, "2026-05",
        )
        fa_service.apply_depreciation(
            db_session, UUID(asset["id"]), test_organization.id, test_user.id, "2026-06",
        )
        db_session.expire_all()
        fa = db_session.get(FixedAsset, UUID(asset["id"]))
        assert fa.status == "fully_depreciated"

        resp = _sell(
            client, org_headers, asset["id"],
            sale_price=500000, third_party_id=str(sale_buyer.id),
        )
        assert resp.status_code == 201
        assert resp.json()["sale_gain"] == 500000  # libro 0 → todo es ganancia

        resp = _annul_sale(client, org_headers, asset["id"])
        assert resp.status_code == 200
        assert resp.json()["status"] == "fully_depreciated"

        db_session.expire_all()
        tp = db_session.get(ThirdParty, sale_buyer.id)
        assert tp.current_balance == Decimal("0")

    def test_annul_without_sale_rejected(
        self, client, org_headers, sale_category, sale_account,
    ):
        asset = _create_asset(client, org_headers, sale_category, sale_account)
        resp = _annul_sale(client, org_headers, asset["id"])
        assert resp.status_code == 400
        # Dar de baja normal tampoco es venta anulable
        client.post(
            f"{BASE_URL}/{asset['id']}/dispose",
            json={"reason": "Chatarra"}, headers=org_headers,
        )
        resp = _annul_sale(client, org_headers, asset["id"])
        assert resp.status_code == 400

    def test_annul_twice_rejected(
        self, client, org_headers, sale_category, sale_account,
    ):
        asset = _create_asset(client, org_headers, sale_category, sale_account)
        _sell(
            client, org_headers, asset["id"],
            sale_price=80000000, account_id=str(sale_account.id),
        )
        assert _annul_sale(client, org_headers, asset["id"]).status_code == 200
        assert _annul_sale(client, org_headers, asset["id"]).status_code == 400

    def test_treasury_annul_blocked(
        self, client, org_headers, sale_category, sale_account, sale_buyer,
    ):
        """Los 2 tipos entran a ASSET_MOVEMENT_TYPES → anular directo en
        Tesorería = 422 con guía al módulo."""
        asset_a = _create_asset(client, org_headers, sale_category, sale_account)
        asset_b = _create_asset(
            client, org_headers, sale_category, sale_account, asset_code="VN-004",
        )
        mm_a = _sell(
            client, org_headers, asset_a["id"],
            sale_price=1000000, account_id=str(sale_account.id),
        ).json()["sale_movement_id"]
        mm_b = _sell(
            client, org_headers, asset_b["id"],
            sale_price=1000000, third_party_id=str(sale_buyer.id),
        ).json()["sale_movement_id"]
        for mm_id in (mm_a, mm_b):
            resp = client.post(
                f"/api/v1/money-movements/{mm_id}/annul",
                json={"reason": "Directo"}, headers=org_headers,
            )
            assert resp.status_code == 422
            assert "Activos Fijos" in resp.json()["detail"]

    def test_resell_after_annul(
        self, client, org_headers, sale_category, sale_account, sale_buyer, db_session,
    ):
        """Anular y re-vender: las columnas guardan la ÚLTIMA venta y el P&L
        solo cuenta la vigente."""
        today = date.today().isoformat()
        asset = _create_asset(client, org_headers, sale_category, sale_account)
        _sell(
            client, org_headers, asset["id"],
            sale_price=130000000, account_id=str(sale_account.id),
        )
        _annul_sale(client, org_headers, asset["id"])
        resp = _sell(
            client, org_headers, asset["id"],
            sale_price=110000000, third_party_id=str(sale_buyer.id),
        )
        assert resp.status_code == 201
        assert resp.json()["sale_gain"] == 10000000

        pnl = _pnl(client, org_headers, date_from=today, date_to=today)
        assert pnl["asset_sale_gain"] == pytest.approx(10000000, abs=1)


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------

class TestSaleRBAC:

    def test_viewer_cannot_sell(
        self, client, org_headers, sale_category, sale_account, db_session, test_organization,
    ):
        from app.core.security import create_access_token
        from app.models.role import Role
        from app.models.user import User, OrganizationMember

        asset = _create_asset(client, org_headers, sale_category, sale_account)

        viewer = User(
            email="viewer-venta-fa@test.com", hashed_password="x",
            full_name="Viewer Venta FA", is_active=True,
        )
        db_session.add(viewer)
        db_session.flush()
        role = db_session.query(Role).filter(
            Role.organization_id == test_organization.id,
            Role.name == "viewer",
            Role.is_system_role == True,
        ).first()
        assert role is not None
        db_session.add(OrganizationMember(
            user_id=viewer.id,
            organization_id=test_organization.id,
            role_id=role.id,
        ))
        db_session.commit()

        token = create_access_token(data={"sub": str(viewer.id)})
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Organization-ID": str(test_organization.id),
        }
        resp = client.post(
            f"{BASE_URL}/{asset['id']}/sell",
            json={"sale_price": 1000, "account_id": str(sale_account.id)},
            headers=headers,
        )
        assert resp.status_code == 403
