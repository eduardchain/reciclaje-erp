"""
Tests para endpoints de DeferredExpense (Gastos Diferidos).

Cubre: creacion (expense/provision), validaciones, aplicacion de cuotas,
completado automatico, ultima cuota con remainder, cancelacion, listado,
detalle con applications, endpoint pending.
"""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.money_account import MoneyAccount
from app.models.third_party import ThirdParty
from app.models.expense_category import ExpenseCategory


# ---------------------------------------------------------------------------
# Fixtures locales
# ---------------------------------------------------------------------------

@pytest.fixture
def test_account(db_session: Session, test_organization) -> MoneyAccount:
    """Cuenta de dinero con saldo $10,000,000."""
    account = MoneyAccount(
        name="Caja General",
        account_type="cash",
        current_balance=Decimal("10000000.00"),
        organization_id=test_organization.id,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


@pytest.fixture
def test_provision(db_session: Session, test_organization) -> ThirdParty:
    """Provision con fondos de $5,000,000 (balance negativo = fondos disponibles)."""
    tp = ThirdParty(
        name="Provision Seguros",
        is_provision=True,
        current_balance=Decimal("-5000000.00"),
        organization_id=test_organization.id,
    )
    db_session.add(tp)
    db_session.commit()
    db_session.refresh(tp)
    return tp


@pytest.fixture
def test_expense_category(db_session: Session, test_organization) -> ExpenseCategory:
    """Categoria de gasto."""
    cat = ExpenseCategory(
        name="Seguros",
        is_direct_expense=False,
        organization_id=test_organization.id,
    )
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


# ---------------------------------------------------------------------------
# Tests de creacion
# ---------------------------------------------------------------------------

class TestDeferredExpenseCreate:

    def test_create_expense_type(
        self, client: TestClient, org_headers, test_account, test_expense_category
    ):
        """Crear gasto diferido tipo expense con account_id."""
        resp = client.post(
            "/api/v1/deferred-expenses/",
            json={
                "name": "Seguro anual 2026",
                "total_amount": 12000000,
                "total_months": 12,
                "expense_category_id": str(test_expense_category.id),
                "expense_type": "expense",
                "account_id": str(test_account.id),
                "start_date": "2026-01-01",
                "description": "Seguro contra todo riesgo",
            },
            headers=org_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Seguro anual 2026"
        assert data["total_amount"] == 12000000
        assert data["monthly_amount"] == 1000000  # 12M / 12
        assert data["total_months"] == 12
        assert data["applied_months"] == 0
        assert data["status"] == "active"
        assert data["expense_type"] == "expense"
        assert data["account_name"] == "Caja General"
        assert data["expense_category_name"] == "Seguros"
        assert data["remaining_amount"] == 12000000
        assert data["next_amount"] == 1000000

    def test_create_provision_type(
        self, client: TestClient, org_headers, test_provision, test_expense_category
    ):
        """Crear gasto diferido tipo provision_expense con provision_id."""
        resp = client.post(
            "/api/v1/deferred-expenses/",
            json={
                "name": "Arriendo diferido",
                "total_amount": 6000000,
                "total_months": 6,
                "expense_category_id": str(test_expense_category.id),
                "expense_type": "provision_expense",
                "provision_id": str(test_provision.id),
                "start_date": "2026-02-01",
            },
            headers=org_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["expense_type"] == "provision_expense"
        assert data["provision_name"] == "Provision Seguros"
        assert data["monthly_amount"] == 1000000

    def test_create_validation_missing_account(
        self, client: TestClient, org_headers, test_expense_category
    ):
        """Error: tipo expense sin account_id."""
        resp = client.post(
            "/api/v1/deferred-expenses/",
            json={
                "name": "Test",
                "total_amount": 1000000,
                "total_months": 2,
                "expense_category_id": str(test_expense_category.id),
                "expense_type": "expense",
                "start_date": "2026-01-01",
            },
            headers=org_headers,
        )
        assert resp.status_code == 422

    def test_create_validation_missing_provision(
        self, client: TestClient, org_headers, test_expense_category
    ):
        """Error: tipo provision_expense sin provision_id."""
        resp = client.post(
            "/api/v1/deferred-expenses/",
            json={
                "name": "Test",
                "total_amount": 1000000,
                "total_months": 2,
                "expense_category_id": str(test_expense_category.id),
                "expense_type": "provision_expense",
                "start_date": "2026-01-01",
            },
            headers=org_headers,
        )
        assert resp.status_code == 422

    def test_create_invalid_expense_type(
        self, client: TestClient, org_headers, test_account, test_expense_category
    ):
        """Error: expense_type invalido."""
        resp = client.post(
            "/api/v1/deferred-expenses/",
            json={
                "name": "Test",
                "total_amount": 1000000,
                "total_months": 2,
                "expense_category_id": str(test_expense_category.id),
                "expense_type": "invalid_type",
                "account_id": str(test_account.id),
                "start_date": "2026-01-01",
            },
            headers=org_headers,
        )
        assert resp.status_code == 422

    def test_create_monthly_amount_rounding(
        self, client: TestClient, org_headers, test_account, test_expense_category
    ):
        """Verificar redondeo: 10,000 / 3 = 3333.33 (floor), no 3333.34."""
        resp = client.post(
            "/api/v1/deferred-expenses/",
            json={
                "name": "Test redondeo",
                "total_amount": 10000,
                "total_months": 3,
                "expense_category_id": str(test_expense_category.id),
                "expense_type": "expense",
                "account_id": str(test_account.id),
                "start_date": "2026-01-01",
            },
            headers=org_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["monthly_amount"] == 3333.33
        # Ultima cuota sera: 10000 - 3333.33*2 = 3333.34
        assert data["next_amount"] == 3333.33


# ---------------------------------------------------------------------------
# Tests de aplicacion de cuotas
# ---------------------------------------------------------------------------

class TestDeferredExpenseApply:

    def _create_deferred(self, client, org_headers, account_id, category_id, total=6000000, months=3):
        """Helper: crear gasto diferido tipo expense."""
        resp = client.post(
            "/api/v1/deferred-expenses/",
            json={
                "name": "Test Deferred",
                "total_amount": total,
                "total_months": months,
                "expense_category_id": str(category_id),
                "expense_type": "expense",
                "account_id": str(account_id),
                "start_date": "2026-01-01",
            },
            headers=org_headers,
        )
        assert resp.status_code == 201
        return resp.json()

    def test_apply_first_month(
        self, client: TestClient, org_headers, test_account, test_expense_category, db_session
    ):
        """Aplicar cuota 1: verifica monto y MoneyMovement creado."""
        de = self._create_deferred(client, org_headers, test_account.id, test_expense_category.id)

        resp = client.post(
            f"/api/v1/deferred-expenses/{de['id']}/apply",
            headers=org_headers,
        )
        assert resp.status_code == 201
        app = resp.json()
        assert app["application_number"] == 1
        assert app["amount"] == 2000000  # 6M / 3
        assert app["money_movement_id"] is not None

        # Verificar que se desconto de la cuenta
        db_session.expire_all()
        from app.models.money_account import MoneyAccount
        acct = db_session.get(MoneyAccount, test_account.id)
        assert float(acct.current_balance) == 8000000  # 10M - 2M

        # Verificar estado del deferred
        detail = client.get(f"/api/v1/deferred-expenses/{de['id']}", headers=org_headers)
        assert detail.json()["applied_months"] == 1
        assert detail.json()["status"] == "active"

    def test_apply_all_months_completes(
        self, client: TestClient, org_headers, test_account, test_expense_category
    ):
        """Aplicar todas las cuotas: status cambia a completed."""
        de = self._create_deferred(
            client, org_headers, test_account.id, test_expense_category.id,
            total=4000000, months=2,
        )

        # Cuota 1
        resp1 = client.post(f"/api/v1/deferred-expenses/{de['id']}/apply", headers=org_headers)
        assert resp1.status_code == 201
        assert resp1.json()["application_number"] == 1

        # Cuota 2 (ultima)
        resp2 = client.post(f"/api/v1/deferred-expenses/{de['id']}/apply", headers=org_headers)
        assert resp2.status_code == 201
        assert resp2.json()["application_number"] == 2

        # Verificar completed
        detail = client.get(f"/api/v1/deferred-expenses/{de['id']}", headers=org_headers)
        assert detail.json()["status"] == "completed"
        assert detail.json()["applied_months"] == 2

    def test_apply_last_month_remainder(
        self, client: TestClient, org_headers, test_account, test_expense_category
    ):
        """Ultima cuota tiene monto ajustado para que sume exacto."""
        # 10000 / 3 = 3333.33 mensual, ultima = 3333.34
        de = self._create_deferred(
            client, org_headers, test_account.id, test_expense_category.id,
            total=10000, months=3,
        )

        # Cuota 1 y 2
        client.post(f"/api/v1/deferred-expenses/{de['id']}/apply", headers=org_headers)
        client.post(f"/api/v1/deferred-expenses/{de['id']}/apply", headers=org_headers)

        # Cuota 3 (ultima, remainder)
        resp = client.post(f"/api/v1/deferred-expenses/{de['id']}/apply", headers=org_headers)
        assert resp.status_code == 201
        assert resp.json()["amount"] == 3333.34  # remainder

    def test_apply_completed_fails(
        self, client: TestClient, org_headers, test_account, test_expense_category
    ):
        """No se puede aplicar a gasto completado."""
        de = self._create_deferred(
            client, org_headers, test_account.id, test_expense_category.id,
            total=2000000, months=2,
        )
        client.post(f"/api/v1/deferred-expenses/{de['id']}/apply", headers=org_headers)
        client.post(f"/api/v1/deferred-expenses/{de['id']}/apply", headers=org_headers)

        # Intentar cuota extra
        resp = client.post(f"/api/v1/deferred-expenses/{de['id']}/apply", headers=org_headers)
        assert resp.status_code == 400

    def test_apply_cancelled_fails(
        self, client: TestClient, org_headers, test_account, test_expense_category
    ):
        """No se puede aplicar a gasto cancelado."""
        de = self._create_deferred(
            client, org_headers, test_account.id, test_expense_category.id,
        )
        # Cancelar
        client.post(f"/api/v1/deferred-expenses/{de['id']}/cancel", headers=org_headers)

        # Intentar aplicar
        resp = client.post(f"/api/v1/deferred-expenses/{de['id']}/apply", headers=org_headers)
        assert resp.status_code == 400

    def test_provision_expense_apply(
        self, client: TestClient, org_headers, test_provision, test_expense_category, db_session
    ):
        """Aplicar cuota tipo provision_expense: verifica efecto en provision."""
        resp = client.post(
            "/api/v1/deferred-expenses/",
            json={
                "name": "Gasto provision diferido",
                "total_amount": 2000000,
                "total_months": 2,
                "expense_category_id": str(test_expense_category.id),
                "expense_type": "provision_expense",
                "provision_id": str(test_provision.id),
                "start_date": "2026-01-01",
            },
            headers=org_headers,
        )
        assert resp.status_code == 201
        de = resp.json()

        # Aplicar cuota
        resp2 = client.post(f"/api/v1/deferred-expenses/{de['id']}/apply", headers=org_headers)
        assert resp2.status_code == 201
        assert resp2.json()["amount"] == 1000000

        # Verificar provision: -5M + 1M = -4M
        db_session.expire_all()
        prov = db_session.get(ThirdParty, test_provision.id)
        assert float(prov.current_balance) == -4000000


# ---------------------------------------------------------------------------
# Tests de cancelacion
# ---------------------------------------------------------------------------

class TestDeferredExpenseCancel:

    def test_cancel(
        self, client: TestClient, org_headers, test_account, test_expense_category
    ):
        """Cancelar gasto activo: status cambia, movimientos existentes intactos."""
        resp = client.post(
            "/api/v1/deferred-expenses/",
            json={
                "name": "Test Cancel",
                "total_amount": 6000000,
                "total_months": 6,
                "expense_category_id": str(test_expense_category.id),
                "expense_type": "expense",
                "account_id": str(test_account.id),
                "start_date": "2026-01-01",
            },
            headers=org_headers,
        )
        de = resp.json()

        # Aplicar 1 cuota
        client.post(f"/api/v1/deferred-expenses/{de['id']}/apply", headers=org_headers)

        # Cancelar
        resp2 = client.post(f"/api/v1/deferred-expenses/{de['id']}/cancel", headers=org_headers)
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["status"] == "cancelled"
        assert data["cancelled_at"] is not None
        assert data["applied_months"] == 1  # La cuota aplicada permanece

    def test_cancel_completed_fails(
        self, client: TestClient, org_headers, test_account, test_expense_category
    ):
        """No se puede cancelar gasto completado."""
        resp = client.post(
            "/api/v1/deferred-expenses/",
            json={
                "name": "Test Complete",
                "total_amount": 2000000,
                "total_months": 2,
                "expense_category_id": str(test_expense_category.id),
                "expense_type": "expense",
                "account_id": str(test_account.id),
                "start_date": "2026-01-01",
            },
            headers=org_headers,
        )
        de = resp.json()
        client.post(f"/api/v1/deferred-expenses/{de['id']}/apply", headers=org_headers)
        client.post(f"/api/v1/deferred-expenses/{de['id']}/apply", headers=org_headers)

        resp2 = client.post(f"/api/v1/deferred-expenses/{de['id']}/cancel", headers=org_headers)
        assert resp2.status_code == 400


# ---------------------------------------------------------------------------
# Tests de listado y detalle
# ---------------------------------------------------------------------------

class TestDeferredExpenseList:

    def test_list_all(
        self, client: TestClient, org_headers, test_account, test_expense_category
    ):
        """Listar todos los gastos diferidos."""
        # Crear 2
        for name in ["Gasto A", "Gasto B"]:
            client.post(
                "/api/v1/deferred-expenses/",
                json={
                    "name": name,
                    "total_amount": 1000000,
                    "total_months": 2,
                    "expense_category_id": str(test_expense_category.id),
                    "expense_type": "expense",
                    "account_id": str(test_account.id),
                    "start_date": "2026-01-01",
                },
                headers=org_headers,
            )

        resp = client.get("/api/v1/deferred-expenses/", headers=org_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_list_filter_by_status(
        self, client: TestClient, org_headers, test_account, test_expense_category
    ):
        """Filtrar por status."""
        # Crear y cancelar uno
        resp = client.post(
            "/api/v1/deferred-expenses/",
            json={
                "name": "Cancelable",
                "total_amount": 1000000,
                "total_months": 2,
                "expense_category_id": str(test_expense_category.id),
                "expense_type": "expense",
                "account_id": str(test_account.id),
                "start_date": "2026-01-01",
            },
            headers=org_headers,
        )
        de_id = resp.json()["id"]
        client.post(f"/api/v1/deferred-expenses/{de_id}/cancel", headers=org_headers)

        # Crear otro activo
        client.post(
            "/api/v1/deferred-expenses/",
            json={
                "name": "Activo",
                "total_amount": 1000000,
                "total_months": 2,
                "expense_category_id": str(test_expense_category.id),
                "expense_type": "expense",
                "account_id": str(test_account.id),
                "start_date": "2026-01-01",
            },
            headers=org_headers,
        )

        # Solo activos
        resp = client.get("/api/v1/deferred-expenses/?status=active", headers=org_headers)
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["name"] == "Activo"

        # Solo cancelados
        resp = client.get("/api/v1/deferred-expenses/?status=cancelled", headers=org_headers)
        assert resp.json()["total"] == 1

    def test_get_detail_with_applications(
        self, client: TestClient, org_headers, test_account, test_expense_category
    ):
        """Detalle incluye lista de applications."""
        resp = client.post(
            "/api/v1/deferred-expenses/",
            json={
                "name": "Con Cuotas",
                "total_amount": 3000000,
                "total_months": 3,
                "expense_category_id": str(test_expense_category.id),
                "expense_type": "expense",
                "account_id": str(test_account.id),
                "start_date": "2026-01-01",
            },
            headers=org_headers,
        )
        de_id = resp.json()["id"]

        # Aplicar 2 cuotas
        client.post(f"/api/v1/deferred-expenses/{de_id}/apply", headers=org_headers)
        client.post(f"/api/v1/deferred-expenses/{de_id}/apply", headers=org_headers)

        detail = client.get(f"/api/v1/deferred-expenses/{de_id}", headers=org_headers)
        assert detail.status_code == 200
        data = detail.json()
        assert len(data["applications"]) == 2
        assert data["applications"][0]["application_number"] == 1
        assert data["applications"][1]["application_number"] == 2

    def test_pending_endpoint(
        self, client: TestClient, org_headers, test_account, test_expense_category
    ):
        """GET /pending retorna solo gastos activos con cuotas pendientes."""
        # Crear uno y completarlo
        resp1 = client.post(
            "/api/v1/deferred-expenses/",
            json={
                "name": "Completado",
                "total_amount": 2000000,
                "total_months": 2,
                "expense_category_id": str(test_expense_category.id),
                "expense_type": "expense",
                "account_id": str(test_account.id),
                "start_date": "2026-01-01",
            },
            headers=org_headers,
        )
        de1_id = resp1.json()["id"]
        client.post(f"/api/v1/deferred-expenses/{de1_id}/apply", headers=org_headers)
        client.post(f"/api/v1/deferred-expenses/{de1_id}/apply", headers=org_headers)

        # Crear otro activo
        resp2 = client.post(
            "/api/v1/deferred-expenses/",
            json={
                "name": "Pendiente",
                "total_amount": 3000000,
                "total_months": 3,
                "expense_category_id": str(test_expense_category.id),
                "expense_type": "expense",
                "account_id": str(test_account.id),
                "start_date": "2026-02-01",
            },
            headers=org_headers,
        )

        resp = client.get("/api/v1/deferred-expenses/pending", headers=org_headers)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["name"] == "Pendiente"
