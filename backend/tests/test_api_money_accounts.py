"""
Tests para endpoints de MoneyAccount (Cuentas de Dinero).

Cubre: CRUD completo, validaciones de tipo, eliminacion con saldo,
busqueda, paginacion y aislamiento multi-tenant.
"""
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.money_account import MoneyAccount


# ---------------------------------------------------------------------------
# Fixtures locales
# ---------------------------------------------------------------------------

@pytest.fixture
def test_money_account(db_session: Session, test_organization) -> MoneyAccount:
    """Crear una cuenta de dinero de prueba (tipo bank)."""
    account = MoneyAccount(
        name="Banco Bogota",
        account_type="bank",
        account_number="1234567890",
        bank_name="Banco de Bogota",
        current_balance=Decimal("1000000.00"),
        organization_id=test_organization.id,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


@pytest.fixture
def test_cash_account(db_session: Session, test_organization) -> MoneyAccount:
    """Crear una cuenta de efectivo de prueba."""
    account = MoneyAccount(
        name="Caja Principal",
        account_type="cash",
        current_balance=Decimal("500000.00"),
        organization_id=test_organization.id,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


# ---------------------------------------------------------------------------
# Tests de creacion
# ---------------------------------------------------------------------------

class TestCreateMoneyAccount:
    """Tests para POST /api/v1/money-accounts."""

    def test_create_bank_account(self, client: TestClient, org_headers: dict):
        """Crear cuenta bancaria con todos los campos."""
        payload = {
            "name": "Davivienda Empresarial",
            "account_type": "bank",
            "account_number": "9876543210",
            "bank_name": "Davivienda",
            "initial_balance": 500000.00,
        }
        response = client.post("/api/v1/money-accounts", json=payload, headers=org_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Davivienda Empresarial"
        assert data["account_type"] == "bank"
        assert data["account_number"] == "9876543210"
        assert data["bank_name"] == "Davivienda"
        assert data["current_balance"] == 500000.00
        assert data["is_active"] is True
        assert "id" in data

    def test_create_cash_account(self, client: TestClient, org_headers: dict):
        """Crear cuenta de efectivo (sin banco ni numero de cuenta)."""
        payload = {
            "name": "Caja Menor",
            "account_type": "cash",
        }
        response = client.post("/api/v1/money-accounts", json=payload, headers=org_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Caja Menor"
        assert data["account_type"] == "cash"
        assert data["current_balance"] == 0.00

    def test_create_digital_account(self, client: TestClient, org_headers: dict):
        """Crear cuenta digital (Nequi, Daviplata, etc.)."""
        payload = {
            "name": "Nequi Empresa",
            "account_type": "digital",
            "initial_balance": 250000.00,
        }
        response = client.post("/api/v1/money-accounts", json=payload, headers=org_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["account_type"] == "digital"
        assert data["current_balance"] == 250000.00

    def test_create_invalid_account_type(self, client: TestClient, org_headers: dict):
        """Tipo de cuenta invalido debe retornar 400."""
        payload = {
            "name": "Cuenta Invalida",
            "account_type": "crypto",
        }
        response = client.post("/api/v1/money-accounts", json=payload, headers=org_headers)

        assert response.status_code == 400
        assert "Tipo de cuenta invalido" in response.json()["detail"]

    def test_create_without_auth(self, client: TestClient):
        """Sin autenticacion debe retornar 401."""
        payload = {"name": "Cuenta", "account_type": "cash"}
        response = client.post("/api/v1/money-accounts", json=payload)

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Tests de listado
# ---------------------------------------------------------------------------

class TestListMoneyAccounts:
    """Tests para GET /api/v1/money-accounts."""

    def test_list_empty(self, client: TestClient, org_headers: dict):
        """Lista vacia retorna items=[] y total=0."""
        response = client.get("/api/v1/money-accounts", headers=org_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_with_accounts(
        self, client: TestClient, org_headers: dict,
        test_money_account, test_cash_account,
    ):
        """Listar debe retornar todas las cuentas de la organizacion."""
        response = client.get("/api/v1/money-accounts", headers=org_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_list_search_by_name(
        self, client: TestClient, org_headers: dict,
        test_money_account, test_cash_account,
    ):
        """Buscar por nombre debe filtrar correctamente."""
        response = client.get(
            "/api/v1/money-accounts?search=Bogota", headers=org_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Banco Bogota"

    def test_list_pagination(
        self, client: TestClient, org_headers: dict,
        test_money_account, test_cash_account,
    ):
        """Paginacion con skip y limit."""
        response = client.get(
            "/api/v1/money-accounts?skip=0&limit=1", headers=org_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 1


# ---------------------------------------------------------------------------
# Tests de lectura individual
# ---------------------------------------------------------------------------

class TestGetMoneyAccount:
    """Tests para GET /api/v1/money-accounts/{id}."""

    def test_get_by_id(
        self, client: TestClient, org_headers: dict, test_money_account,
    ):
        """Obtener cuenta por ID."""
        response = client.get(
            f"/api/v1/money-accounts/{test_money_account.id}", headers=org_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Banco Bogota"
        assert data["account_type"] == "bank"

    def test_get_not_found(self, client: TestClient, org_headers: dict):
        """ID inexistente retorna 404."""
        fake_id = uuid4()
        response = client.get(
            f"/api/v1/money-accounts/{fake_id}", headers=org_headers
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests de actualizacion
# ---------------------------------------------------------------------------

class TestUpdateMoneyAccount:
    """Tests para PATCH /api/v1/money-accounts/{id}."""

    def test_update_name(
        self, client: TestClient, org_headers: dict, test_money_account,
    ):
        """Actualizar solo el nombre (PATCH parcial)."""
        payload = {"name": "Banco Bogota - Principal"}
        response = client.patch(
            f"/api/v1/money-accounts/{test_money_account.id}",
            json=payload, headers=org_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Banco Bogota - Principal"
        # Los demas campos no cambian
        assert data["account_type"] == "bank"

    def test_update_not_found(self, client: TestClient, org_headers: dict):
        """Actualizar cuenta inexistente retorna 404."""
        fake_id = uuid4()
        response = client.patch(
            f"/api/v1/money-accounts/{fake_id}",
            json={"name": "X"}, headers=org_headers,
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests de eliminacion
# ---------------------------------------------------------------------------

class TestDeleteMoneyAccount:
    """Tests para DELETE /api/v1/money-accounts/{id}."""

    def test_delete_account_with_zero_balance(
        self, client: TestClient, org_headers: dict, db_session: Session,
        test_organization,
    ):
        """Se puede eliminar una cuenta con saldo 0."""
        account = MoneyAccount(
            name="Cuenta Temporal",
            account_type="cash",
            current_balance=Decimal("0.00"),
            organization_id=test_organization.id,
        )
        db_session.add(account)
        db_session.commit()
        db_session.refresh(account)

        response = client.delete(
            f"/api/v1/money-accounts/{account.id}", headers=org_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

    def test_delete_account_with_balance_fails(
        self, client: TestClient, org_headers: dict, test_money_account,
    ):
        """No se puede eliminar una cuenta con saldo != 0."""
        response = client.delete(
            f"/api/v1/money-accounts/{test_money_account.id}", headers=org_headers
        )

        assert response.status_code == 400
        assert "saldo" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Tests de aislamiento multi-tenant
# ---------------------------------------------------------------------------

class TestMoneyAccountOrganizationIsolation:
    """Verificar que una organizacion no puede ver cuentas de otra."""

    def test_cannot_access_other_org_account(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_organization2,
    ):
        """Cuenta de otra organizacion retorna 404."""
        # Crear cuenta en organizacion 2
        other_account = MoneyAccount(
            name="Cuenta Org2",
            account_type="cash",
            current_balance=Decimal("0"),
            organization_id=test_organization2.id,
        )
        db_session.add(other_account)
        db_session.commit()
        db_session.refresh(other_account)

        # Intentar acceder desde org1
        response = client.get(
            f"/api/v1/money-accounts/{other_account.id}", headers=org_headers
        )

        assert response.status_code == 404
