"""
Tests para endpoints de ScheduledExpense (Gastos Diferidos Programados).

Cubre: crear con pago upfront, aplicar cuotas, ultima cuota con residuo,
cancelar, intentar aplicar completado/cancelado, P&L.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.money_account import MoneyAccount
from app.models.third_party import ThirdParty
from app.models.expense_category import ExpenseCategory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def se_account(db_session: Session, test_organization) -> MoneyAccount:
    """Cuenta con saldo $12,000,000 para gastos diferidos."""
    account = MoneyAccount(
        name="Caja SE",
        account_type="cash",
        current_balance=Decimal("12000000.00"),
        organization_id=test_organization.id,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


@pytest.fixture
def se_category(db_session: Session, test_organization) -> ExpenseCategory:
    """Categoria de gasto para gastos diferidos."""
    cat = ExpenseCategory(
        name="Dotacion",
        is_direct_expense=False,
        organization_id=test_organization.id,
    )
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


# ---------------------------------------------------------------------------
# Tests: Crear
# ---------------------------------------------------------------------------

class TestScheduledExpenseCreate:
    """Tests para POST /api/v1/scheduled-expenses/."""

    def test_create_basic(
        self, client: TestClient, org_headers: dict,
        se_account, se_category, db_session,
    ):
        """Crear gasto diferido — verifica funding, cuenta, TP prepago."""
        payload = {
            "name": "Dotacion 2026",
            "total_amount": 12000000,
            "total_months": 12,
            "source_account_id": str(se_account.id),
            "expense_category_id": str(se_category.id),
            "start_date": "2026-01-15",
            "apply_day": 1,
        }
        resp = client.post(
            "/api/v1/scheduled-expenses/",
            json=payload, headers=org_headers,
        )
        assert resp.status_code == 201
        data = resp.json()

        assert data["name"] == "Dotacion 2026"
        assert data["total_amount"] == 12000000.0
        assert data["monthly_amount"] == 1000000.0  # 12M / 12
        assert data["total_months"] == 12
        assert data["applied_months"] == 0
        assert data["status"] == "active"
        assert data["funding_movement_id"] is not None
        assert data["prepaid_third_party_name"] == "[Prepago] Dotacion 2026"
        assert data["source_account_name"] == "Caja SE"
        assert data["expense_category_name"] == "Dotacion"
        assert data["next_application_date"] == "2026-02-01"  # start_date=15 >= apply_day=1 → mes sig
        assert data["prepaid_balance"] == 12000000.0

        # Verificar efecto en cuenta
        db_session.refresh(se_account)
        assert se_account.current_balance == Decimal("0.00")  # 12M - 12M

    def test_create_insufficient_funds(
        self, client: TestClient, org_headers: dict,
        se_account, se_category,
    ):
        """Crear con fondos insuficientes — 400."""
        payload = {
            "name": "Gasto excesivo",
            "total_amount": 99000000,
            "total_months": 12,
            "source_account_id": str(se_account.id),
            "expense_category_id": str(se_category.id),
            "start_date": "2026-01-01",
        }
        resp = client.post(
            "/api/v1/scheduled-expenses/",
            json=payload, headers=org_headers,
        )
        assert resp.status_code == 400
        assert "Fondos insuficientes" in resp.json()["detail"]

    def test_create_monthly_floor(
        self, client: TestClient, org_headers: dict,
        se_account, se_category,
    ):
        """Cuota mensual se redondea hacia abajo (floor)."""
        payload = {
            "name": "Gasto impar",
            "total_amount": 1000000,
            "total_months": 3,  # 1M / 3 = 333333.33...
            "source_account_id": str(se_account.id),
            "expense_category_id": str(se_category.id),
            "start_date": "2026-03-01",
        }
        resp = client.post(
            "/api/v1/scheduled-expenses/",
            json=payload, headers=org_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["monthly_amount"] == 333333.33  # floor


# ---------------------------------------------------------------------------
# Tests: Aplicar cuota
# ---------------------------------------------------------------------------

class TestScheduledExpenseApply:
    """Tests para POST /api/v1/scheduled-expenses/{id}/apply."""

    def _create_se(self, client, org_headers, account_id, category_id, total=1000000, months=3):
        """Helper: crear gasto diferido."""
        resp = client.post(
            "/api/v1/scheduled-expenses/",
            json={
                "name": "Test SE",
                "total_amount": total,
                "total_months": months,
                "source_account_id": account_id,
                "expense_category_id": category_id,
                "start_date": "2026-03-01",
                "apply_day": 15,
            },
            headers=org_headers,
        )
        assert resp.status_code == 201
        return resp.json()

    def test_apply_first_installment(
        self, client: TestClient, org_headers: dict,
        se_account, se_category, db_session,
    ):
        """Aplicar primera cuota — crea deferred_expense movement."""
        se = self._create_se(client, org_headers, str(se_account.id), str(se_category.id))
        se_id = se["id"]
        prepaid_tp_id = se["prepaid_third_party_id"]

        resp = client.post(
            f"/api/v1/scheduled-expenses/{se_id}/apply",
            headers=org_headers,
        )
        assert resp.status_code == 201
        app_data = resp.json()
        assert app_data["application_number"] == 1
        assert app_data["amount"] == 333333.33  # floor(1M/3)

        # Verificar balance del TP prepago: 1M - 333333.33
        tp = db_session.get(ThirdParty, prepaid_tp_id)
        db_session.refresh(tp)
        assert tp.current_balance == Decimal("1000000") - Decimal("333333.33")

    def test_apply_last_installment_remainder(
        self, client: TestClient, org_headers: dict,
        se_account, se_category, db_session,
    ):
        """Ultima cuota absorbe residuo — suma total es exacta."""
        se = self._create_se(client, org_headers, str(se_account.id), str(se_category.id))
        se_id = se["id"]

        # Aplicar 3 cuotas
        amounts = []
        for i in range(3):
            resp = client.post(
                f"/api/v1/scheduled-expenses/{se_id}/apply",
                headers=org_headers,
            )
            assert resp.status_code == 201
            amounts.append(resp.json()["amount"])

        # Primeras 2: 333333.33, ultima: 333333.34 (residuo)
        assert amounts[0] == 333333.33
        assert amounts[1] == 333333.33
        assert amounts[2] == 333333.34  # 1M - 333333.33*2 = 333333.34

        # Verificar status completed
        resp = client.get(
            f"/api/v1/scheduled-expenses/{se_id}",
            headers=org_headers,
        )
        assert resp.json()["status"] == "completed"
        assert resp.json()["applied_months"] == 3
        assert resp.json()["next_application_date"] is None

        # Verificar TP prepago en 0
        prepaid_tp_id = resp.json()["prepaid_third_party_id"]
        tp = db_session.get(ThirdParty, prepaid_tp_id)
        db_session.refresh(tp)
        assert tp.current_balance == Decimal("0")

    def test_apply_completed_fails(
        self, client: TestClient, org_headers: dict,
        se_account, se_category,
    ):
        """Intentar aplicar cuota a gasto completado — 400."""
        se = self._create_se(client, org_headers, str(se_account.id), str(se_category.id))
        se_id = se["id"]

        # Aplicar todas
        for _ in range(3):
            client.post(f"/api/v1/scheduled-expenses/{se_id}/apply", headers=org_headers)

        # Intentar otra
        resp = client.post(
            f"/api/v1/scheduled-expenses/{se_id}/apply",
            headers=org_headers,
        )
        assert resp.status_code == 400

    def test_apply_cancelled_fails(
        self, client: TestClient, org_headers: dict,
        se_account, se_category,
    ):
        """Intentar aplicar cuota a gasto cancelado — 400."""
        se = self._create_se(client, org_headers, str(se_account.id), str(se_category.id))
        se_id = se["id"]

        # Cancelar
        client.post(f"/api/v1/scheduled-expenses/{se_id}/cancel", headers=org_headers)

        # Intentar aplicar
        resp = client.post(
            f"/api/v1/scheduled-expenses/{se_id}/apply",
            headers=org_headers,
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tests: Cancelar
# ---------------------------------------------------------------------------

class TestScheduledExpenseCancel:
    """Tests para POST /api/v1/scheduled-expenses/{id}/cancel."""

    def test_cancel_active(
        self, client: TestClient, org_headers: dict,
        se_account, se_category,
    ):
        """Cancelar gasto activo — status cancelled, cuotas previas intactas."""
        # Crear
        resp = client.post(
            "/api/v1/scheduled-expenses/",
            json={
                "name": "Cancelable",
                "total_amount": 600000,
                "total_months": 6,
                "source_account_id": str(se_account.id),
                "expense_category_id": str(se_category.id),
                "start_date": "2026-03-01",
            },
            headers=org_headers,
        )
        se_id = resp.json()["id"]

        # Aplicar 2 cuotas
        for _ in range(2):
            client.post(f"/api/v1/scheduled-expenses/{se_id}/apply", headers=org_headers)

        # Cancelar
        resp = client.post(
            f"/api/v1/scheduled-expenses/{se_id}/cancel",
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"
        assert data["applied_months"] == 2  # Cuotas previas intactas
        assert data["next_application_date"] is None

    def test_cancel_completed_fails(
        self, client: TestClient, org_headers: dict,
        se_account, se_category,
    ):
        """Cancelar gasto completado — 400."""
        resp = client.post(
            "/api/v1/scheduled-expenses/",
            json={
                "name": "Short",
                "total_amount": 200000,
                "total_months": 2,
                "source_account_id": str(se_account.id),
                "expense_category_id": str(se_category.id),
                "start_date": "2026-03-01",
            },
            headers=org_headers,
        )
        se_id = resp.json()["id"]

        # Aplicar todas
        for _ in range(2):
            client.post(f"/api/v1/scheduled-expenses/{se_id}/apply", headers=org_headers)

        # Intentar cancelar
        resp = client.post(
            f"/api/v1/scheduled-expenses/{se_id}/cancel",
            headers=org_headers,
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tests: Listado y pendientes
# ---------------------------------------------------------------------------

class TestScheduledExpenseList:
    """Tests para GET /api/v1/scheduled-expenses/ y /pending."""

    def test_list_with_status_filter(
        self, client: TestClient, org_headers: dict,
        se_account, se_category,
    ):
        """Listar con filtro por status."""
        # Crear 2
        for name in ["SE1", "SE2"]:
            client.post(
                "/api/v1/scheduled-expenses/",
                json={
                    "name": name,
                    "total_amount": 200000,
                    "total_months": 2,
                    "source_account_id": str(se_account.id),
                    "expense_category_id": str(se_category.id),
                    "start_date": "2026-03-01",
                },
                headers=org_headers,
            )

        # Listar activos
        resp = client.get(
            "/api/v1/scheduled-expenses/",
            params={"status": "active"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        assert all(i["status"] == "active" for i in data["items"])

    def test_pending_endpoint(
        self, client: TestClient, org_headers: dict,
        se_account, se_category,
    ):
        """Endpoint /pending retorna solo gastos activos."""
        client.post(
            "/api/v1/scheduled-expenses/",
            json={
                "name": "Pending Test",
                "total_amount": 400000,
                "total_months": 4,
                "source_account_id": str(se_account.id),
                "expense_category_id": str(se_category.id),
                "start_date": "2026-03-01",
            },
            headers=org_headers,
        )

        resp = client.get(
            "/api/v1/scheduled-expenses/pending",
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert all(i["status"] == "active" for i in data)


# ---------------------------------------------------------------------------
# Tests: Detalle con applications
# ---------------------------------------------------------------------------

class TestScheduledExpenseDetail:
    """Tests para GET /api/v1/scheduled-expenses/{id}."""

    def test_detail_with_applications(
        self, client: TestClient, org_headers: dict,
        se_account, se_category,
    ):
        """Detalle incluye lista de applications."""
        # Crear
        resp = client.post(
            "/api/v1/scheduled-expenses/",
            json={
                "name": "Detail Test",
                "total_amount": 300000,
                "total_months": 3,
                "source_account_id": str(se_account.id),
                "expense_category_id": str(se_category.id),
                "start_date": "2026-03-01",
            },
            headers=org_headers,
        )
        se_id = resp.json()["id"]

        # Aplicar 2 cuotas
        for _ in range(2):
            client.post(f"/api/v1/scheduled-expenses/{se_id}/apply", headers=org_headers)

        # Detalle
        resp = client.get(
            f"/api/v1/scheduled-expenses/{se_id}",
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["applications"]) == 2
        assert data["applications"][0]["application_number"] == 1
        assert data["applications"][1]["application_number"] == 2
        assert data["applied_months"] == 2
        assert data["remaining_amount"] > 0


# ---------------------------------------------------------------------------
# Tests: P&L integration
# ---------------------------------------------------------------------------

class TestScheduledExpensePnL:
    """Tests para verificar que deferred_expense aparece en P&L."""

    def test_deferred_expense_in_pnl(
        self, client: TestClient, org_headers: dict,
        se_account, se_category,
    ):
        """Cuota deferred_expense aparece como gasto operativo en P&L."""
        # Crear gasto diferido
        resp = client.post(
            "/api/v1/scheduled-expenses/",
            json={
                "name": "P&L Test",
                "total_amount": 600000,
                "total_months": 6,
                "source_account_id": str(se_account.id),
                "expense_category_id": str(se_category.id),
                "start_date": "2026-03-01",
            },
            headers=org_headers,
        )
        se_id = resp.json()["id"]

        # Aplicar 1 cuota
        resp = client.post(
            f"/api/v1/scheduled-expenses/{se_id}/apply",
            headers=org_headers,
        )
        assert resp.status_code == 201

        # Consultar P&L
        resp = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": "2026-03-01", "date_to": "2026-03-31"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # La cuota (100000) debe aparecer como gasto operativo
        assert data["operating_expenses"] >= 100000.0
        cat_names = [c["category_name"] for c in data["expenses_by_category"]]
        assert "Dotacion" in cat_names

    def test_deferred_funding_not_in_pnl(
        self, client: TestClient, org_headers: dict,
        se_account, se_category,
    ):
        """Pago inicial (deferred_funding) NO aparece en P&L."""
        # Crear gasto diferido (sin aplicar cuotas)
        client.post(
            "/api/v1/scheduled-expenses/",
            json={
                "name": "Funding Only",
                "total_amount": 500000,
                "total_months": 5,
                "source_account_id": str(se_account.id),
                "expense_category_id": str(se_category.id),
                "start_date": "2026-03-01",
            },
            headers=org_headers,
        )

        # Consultar P&L — deferred_funding NO debe aparecer como gasto
        resp = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": "2026-03-01", "date_to": "2026-03-31"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # deferred_funding no es "expense" — operating_expenses debe ser 0
        assert data["operating_expenses"] == 0
