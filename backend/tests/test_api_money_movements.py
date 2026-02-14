"""
Tests para endpoints de MoneyMovement (Movimientos de Dinero - Tesoreria).

Cubre: pagos a proveedores, cobros a clientes, gastos, ingresos por servicio,
transferencias, capital injection/return, pagos de comision, anulacion,
listado con filtros, resumen y aislamiento multi-tenant.
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
def test_account2(db_session: Session, test_organization) -> MoneyAccount:
    """Segunda cuenta con saldo $5,000,000."""
    account = MoneyAccount(
        name="Banco Bancolombia",
        account_type="bank",
        current_balance=Decimal("5000000.00"),
        organization_id=test_organization.id,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


@pytest.fixture
def test_supplier(db_session: Session, test_organization) -> ThirdParty:
    """Proveedor con saldo -$2,000,000 (le debemos)."""
    tp = ThirdParty(
        name="Metales XYZ",
        is_supplier=True,
        current_balance=Decimal("-2000000.00"),
        organization_id=test_organization.id,
    )
    db_session.add(tp)
    db_session.commit()
    db_session.refresh(tp)
    return tp


@pytest.fixture
def test_customer(db_session: Session, test_organization) -> ThirdParty:
    """Cliente con saldo +$3,000,000 (nos debe)."""
    tp = ThirdParty(
        name="Industrial ABC",
        is_customer=True,
        current_balance=Decimal("3000000.00"),
        organization_id=test_organization.id,
    )
    db_session.add(tp)
    db_session.commit()
    db_session.refresh(tp)
    return tp


@pytest.fixture
def test_investor(db_session: Session, test_organization) -> ThirdParty:
    """Inversor con saldo -$5,000,000 (le debemos)."""
    tp = ThirdParty(
        name="Socio Gustavo",
        is_investor=True,
        current_balance=Decimal("-5000000.00"),
        organization_id=test_organization.id,
    )
    db_session.add(tp)
    db_session.commit()
    db_session.refresh(tp)
    return tp


@pytest.fixture
def test_commission_recipient(db_session: Session, test_organization) -> ThirdParty:
    """Tercero con comision pendiente (saldo negativo = le debemos)."""
    tp = ThirdParty(
        name="Vendedor Juan",
        is_supplier=False,
        is_customer=False,
        current_balance=Decimal("-500000.00"),
        organization_id=test_organization.id,
    )
    db_session.add(tp)
    db_session.commit()
    db_session.refresh(tp)
    return tp


@pytest.fixture
def test_expense_category(db_session: Session, test_organization) -> ExpenseCategory:
    """Categoria de gasto indirecto."""
    cat = ExpenseCategory(
        name="Combustible",
        is_direct_expense=False,
        organization_id=test_organization.id,
    )
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


# ---------------------------------------------------------------------------
# Tests: Pago a proveedor
# ---------------------------------------------------------------------------

class TestSupplierPayment:
    """Tests para POST /api/v1/money-movements/supplier-payment."""

    def test_pay_supplier(
        self, client: TestClient, org_headers: dict,
        test_account, test_supplier, db_session,
    ):
        """Pago basico a proveedor — verifica saldos."""
        payload = {
            "supplier_id": str(test_supplier.id),
            "amount": 1000000,
            "account_id": str(test_account.id),
            "date": "2026-02-14T10:00:00Z",
            "description": "Pago parcial",
        }
        response = client.post(
            "/api/v1/money-movements/supplier-payment",
            json=payload, headers=org_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["movement_type"] == "payment_to_supplier"
        assert data["amount"] == 1000000.0
        assert data["status"] == "confirmed"
        assert data["movement_number"] == 1
        assert data["account_name"] == "Caja General"
        assert data["third_party_name"] == "Metales XYZ"

        # Verificar saldos en BD
        db_session.refresh(test_account)
        db_session.refresh(test_supplier)
        assert test_account.current_balance == Decimal("9000000.00")
        assert test_supplier.current_balance == Decimal("-1000000.00")

    def test_pay_supplier_insufficient_funds(
        self, client: TestClient, org_headers: dict,
        test_account, test_supplier,
    ):
        """Fondos insuficientes retorna 400."""
        payload = {
            "supplier_id": str(test_supplier.id),
            "amount": 99000000,
            "account_id": str(test_account.id),
            "date": "2026-02-14T10:00:00Z",
        }
        response = client.post(
            "/api/v1/money-movements/supplier-payment",
            json=payload, headers=org_headers,
        )
        assert response.status_code == 400
        assert "Fondos insuficientes" in response.json()["detail"]

    def test_pay_supplier_not_supplier(
        self, client: TestClient, org_headers: dict,
        test_account, test_customer,
    ):
        """Tercero que no es proveedor retorna 400."""
        payload = {
            "supplier_id": str(test_customer.id),
            "amount": 100000,
            "account_id": str(test_account.id),
            "date": "2026-02-14T10:00:00Z",
        }
        response = client.post(
            "/api/v1/money-movements/supplier-payment",
            json=payload, headers=org_headers,
        )
        assert response.status_code == 400
        assert "proveedor" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Tests: Cobro a cliente
# ---------------------------------------------------------------------------

class TestCustomerCollection:
    """Tests para POST /api/v1/money-movements/customer-collection."""

    def test_collect_from_customer(
        self, client: TestClient, org_headers: dict,
        test_account, test_customer, db_session,
    ):
        """Cobro basico — verifica saldos."""
        payload = {
            "customer_id": str(test_customer.id),
            "amount": 1500000,
            "account_id": str(test_account.id),
            "date": "2026-02-14T11:00:00Z",
            "description": "Cobro parcial venta",
        }
        response = client.post(
            "/api/v1/money-movements/customer-collection",
            json=payload, headers=org_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["movement_type"] == "collection_from_client"
        assert data["amount"] == 1500000.0

        db_session.refresh(test_account)
        db_session.refresh(test_customer)
        assert test_account.current_balance == Decimal("11500000.00")
        assert test_customer.current_balance == Decimal("1500000.00")

    def test_collect_not_customer(
        self, client: TestClient, org_headers: dict,
        test_account, test_supplier,
    ):
        """Tercero que no es cliente retorna 400."""
        payload = {
            "customer_id": str(test_supplier.id),
            "amount": 100000,
            "account_id": str(test_account.id),
            "date": "2026-02-14T11:00:00Z",
        }
        response = client.post(
            "/api/v1/money-movements/customer-collection",
            json=payload, headers=org_headers,
        )
        assert response.status_code == 400
        assert "cliente" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Tests: Gastos
# ---------------------------------------------------------------------------

class TestExpense:
    """Tests para POST /api/v1/money-movements/expense."""

    def test_create_expense(
        self, client: TestClient, org_headers: dict,
        test_account, test_expense_category, db_session,
    ):
        """Gasto basico — verifica saldo cuenta."""
        payload = {
            "amount": 300000,
            "expense_category_id": str(test_expense_category.id),
            "account_id": str(test_account.id),
            "description": "Tanqueo vehiculo",
            "date": "2026-02-14T12:00:00Z",
        }
        response = client.post(
            "/api/v1/money-movements/expense",
            json=payload, headers=org_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["movement_type"] == "expense"
        assert data["expense_category_name"] == "Combustible"

        db_session.refresh(test_account)
        assert test_account.current_balance == Decimal("9700000.00")

    def test_expense_insufficient_funds(
        self, client: TestClient, org_headers: dict,
        test_account, test_expense_category,
    ):
        """Fondos insuficientes para gasto retorna 400."""
        payload = {
            "amount": 99000000,
            "expense_category_id": str(test_expense_category.id),
            "account_id": str(test_account.id),
            "description": "Gasto enorme",
            "date": "2026-02-14T12:00:00Z",
        }
        response = client.post(
            "/api/v1/money-movements/expense",
            json=payload, headers=org_headers,
        )
        assert response.status_code == 400

    def test_expense_invalid_category(
        self, client: TestClient, org_headers: dict,
        test_account,
    ):
        """Categoria inexistente retorna 404."""
        payload = {
            "amount": 100000,
            "expense_category_id": str(uuid4()),
            "account_id": str(test_account.id),
            "description": "Gasto",
            "date": "2026-02-14T12:00:00Z",
        }
        response = client.post(
            "/api/v1/money-movements/expense",
            json=payload, headers=org_headers,
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Ingreso por servicio
# ---------------------------------------------------------------------------

class TestServiceIncome:
    """Tests para POST /api/v1/money-movements/service-income."""

    def test_create_service_income(
        self, client: TestClient, org_headers: dict,
        test_account, db_session,
    ):
        """Ingreso por servicio — verifica saldo."""
        payload = {
            "amount": 2000000,
            "account_id": str(test_account.id),
            "description": "Servicio de transporte",
            "date": "2026-02-14T13:00:00Z",
        }
        response = client.post(
            "/api/v1/money-movements/service-income",
            json=payload, headers=org_headers,
        )

        assert response.status_code == 201
        assert response.json()["movement_type"] == "service_income"

        db_session.refresh(test_account)
        assert test_account.current_balance == Decimal("12000000.00")


# ---------------------------------------------------------------------------
# Tests: Transferencias
# ---------------------------------------------------------------------------

class TestTransfer:
    """Tests para POST /api/v1/money-movements/transfer."""

    def test_create_transfer(
        self, client: TestClient, org_headers: dict,
        test_account, test_account2, db_session,
    ):
        """Transferencia crea par de movimientos y actualiza saldos."""
        payload = {
            "amount": 2000000,
            "source_account_id": str(test_account.id),
            "destination_account_id": str(test_account2.id),
            "date": "2026-02-14T14:00:00Z",
            "description": "Transferencia a banco",
        }
        response = client.post(
            "/api/v1/money-movements/transfer",
            json=payload, headers=org_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["movement_type"] == "transfer_out"
        assert data["transfer_pair_id"] is not None

        db_session.refresh(test_account)
        db_session.refresh(test_account2)
        assert test_account.current_balance == Decimal("8000000.00")
        assert test_account2.current_balance == Decimal("7000000.00")

    def test_transfer_same_account(
        self, client: TestClient, org_headers: dict,
        test_account,
    ):
        """Transferencia a la misma cuenta retorna 400."""
        payload = {
            "amount": 100000,
            "source_account_id": str(test_account.id),
            "destination_account_id": str(test_account.id),
            "date": "2026-02-14T14:00:00Z",
            "description": "Auto-transferencia",
        }
        response = client.post(
            "/api/v1/money-movements/transfer",
            json=payload, headers=org_headers,
        )
        assert response.status_code == 400
        assert "diferentes" in response.json()["detail"]

    def test_transfer_insufficient_funds(
        self, client: TestClient, org_headers: dict,
        test_account, test_account2,
    ):
        """Fondos insuficientes en cuenta origen retorna 400."""
        payload = {
            "amount": 99000000,
            "source_account_id": str(test_account.id),
            "destination_account_id": str(test_account2.id),
            "date": "2026-02-14T14:00:00Z",
            "description": "Transferencia grande",
        }
        response = client.post(
            "/api/v1/money-movements/transfer",
            json=payload, headers=org_headers,
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Tests: Capital injection / return
# ---------------------------------------------------------------------------

class TestCapital:
    """Tests para capital-injection y capital-return."""

    def test_capital_injection(
        self, client: TestClient, org_headers: dict,
        test_account, test_investor, db_session,
    ):
        """Aporte de capital — account(+), investor(-)."""
        payload = {
            "investor_id": str(test_investor.id),
            "amount": 10000000,
            "account_id": str(test_account.id),
            "date": "2026-02-14T15:00:00Z",
        }
        response = client.post(
            "/api/v1/money-movements/capital-injection",
            json=payload, headers=org_headers,
        )

        assert response.status_code == 201
        assert response.json()["movement_type"] == "capital_injection"

        db_session.refresh(test_account)
        db_session.refresh(test_investor)
        assert test_account.current_balance == Decimal("20000000.00")
        assert test_investor.current_balance == Decimal("-15000000.00")

    def test_capital_return(
        self, client: TestClient, org_headers: dict,
        test_account, test_investor, db_session,
    ):
        """Retiro de capital — account(-), investor(+)."""
        payload = {
            "investor_id": str(test_investor.id),
            "amount": 3000000,
            "account_id": str(test_account.id),
            "date": "2026-02-14T16:00:00Z",
        }
        response = client.post(
            "/api/v1/money-movements/capital-return",
            json=payload, headers=org_headers,
        )

        assert response.status_code == 201

        db_session.refresh(test_account)
        db_session.refresh(test_investor)
        assert test_account.current_balance == Decimal("7000000.00")
        assert test_investor.current_balance == Decimal("-2000000.00")

    def test_capital_injection_not_investor(
        self, client: TestClient, org_headers: dict,
        test_account, test_supplier,
    ):
        """Tercero que no es inversor retorna 400."""
        payload = {
            "investor_id": str(test_supplier.id),
            "amount": 1000000,
            "account_id": str(test_account.id),
            "date": "2026-02-14T15:00:00Z",
        }
        response = client.post(
            "/api/v1/money-movements/capital-injection",
            json=payload, headers=org_headers,
        )
        assert response.status_code == 400
        assert "inversor" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Tests: Pago de comision
# ---------------------------------------------------------------------------

class TestCommissionPayment:
    """Tests para POST /api/v1/money-movements/commission-payment."""

    def test_pay_commission(
        self, client: TestClient, org_headers: dict,
        test_account, test_commission_recipient, db_session,
    ):
        """Pago de comision — account(-), third_party.balance(+)."""
        payload = {
            "third_party_id": str(test_commission_recipient.id),
            "amount": 500000,
            "account_id": str(test_account.id),
            "date": "2026-02-14T17:00:00Z",
            "description": "Pago comision venta #42",
        }
        response = client.post(
            "/api/v1/money-movements/commission-payment",
            json=payload, headers=org_headers,
        )

        assert response.status_code == 201
        assert response.json()["movement_type"] == "commission_payment"

        db_session.refresh(test_account)
        db_session.refresh(test_commission_recipient)
        assert test_account.current_balance == Decimal("9500000.00")
        # -500,000 + 500,000 = 0 (ya no le debemos)
        assert test_commission_recipient.current_balance == Decimal("0.00")


# ---------------------------------------------------------------------------
# Tests: Anulacion
# ---------------------------------------------------------------------------

class TestAnnul:
    """Tests para POST /api/v1/money-movements/{id}/annul."""

    def test_annul_supplier_payment(
        self, client: TestClient, org_headers: dict,
        test_account, test_supplier, db_session,
    ):
        """Anular pago revierte saldos."""
        # Crear pago
        payload = {
            "supplier_id": str(test_supplier.id),
            "amount": 1000000,
            "account_id": str(test_account.id),
            "date": "2026-02-14T10:00:00Z",
        }
        create_resp = client.post(
            "/api/v1/money-movements/supplier-payment",
            json=payload, headers=org_headers,
        )
        movement_id = create_resp.json()["id"]

        # Verificar saldos post-pago
        db_session.refresh(test_account)
        db_session.refresh(test_supplier)
        assert test_account.current_balance == Decimal("9000000.00")
        assert test_supplier.current_balance == Decimal("-1000000.00")

        # Anular
        annul_resp = client.post(
            f"/api/v1/money-movements/{movement_id}/annul",
            json={"reason": "Error de digitacion"},
            headers=org_headers,
        )
        assert annul_resp.status_code == 200
        data = annul_resp.json()
        assert data["status"] == "annulled"
        assert data["annulled_reason"] == "Error de digitacion"

        # Verificar saldos revertidos
        db_session.refresh(test_account)
        db_session.refresh(test_supplier)
        assert test_account.current_balance == Decimal("10000000.00")
        assert test_supplier.current_balance == Decimal("-2000000.00")

    def test_annul_transfer_annuls_pair(
        self, client: TestClient, org_headers: dict,
        test_account, test_account2, db_session,
    ):
        """Anular transferencia anula ambos movimientos del par."""
        # Crear transferencia
        payload = {
            "amount": 1000000,
            "source_account_id": str(test_account.id),
            "destination_account_id": str(test_account2.id),
            "date": "2026-02-14T14:00:00Z",
            "description": "Transfer test",
        }
        create_resp = client.post(
            "/api/v1/money-movements/transfer",
            json=payload, headers=org_headers,
        )
        movement_id = create_resp.json()["id"]
        pair_id = create_resp.json()["transfer_pair_id"]

        # Anular
        annul_resp = client.post(
            f"/api/v1/money-movements/{movement_id}/annul",
            json={"reason": "Error"},
            headers=org_headers,
        )
        assert annul_resp.status_code == 200

        # Verificar saldos revertidos
        db_session.refresh(test_account)
        db_session.refresh(test_account2)
        assert test_account.current_balance == Decimal("10000000.00")
        assert test_account2.current_balance == Decimal("5000000.00")

        # Verificar que el par tambien esta anulado
        pair_resp = client.get(
            f"/api/v1/money-movements/{pair_id}",
            headers=org_headers,
        )
        assert pair_resp.json()["status"] == "annulled"

    def test_annul_already_annulled(
        self, client: TestClient, org_headers: dict,
        test_account, test_supplier,
    ):
        """Anular un movimiento ya anulado retorna 400."""
        # Crear y anular
        payload = {
            "supplier_id": str(test_supplier.id),
            "amount": 100000,
            "account_id": str(test_account.id),
            "date": "2026-02-14T10:00:00Z",
        }
        create_resp = client.post(
            "/api/v1/money-movements/supplier-payment",
            json=payload, headers=org_headers,
        )
        movement_id = create_resp.json()["id"]

        client.post(
            f"/api/v1/money-movements/{movement_id}/annul",
            json={"reason": "Error"},
            headers=org_headers,
        )

        # Intentar anular de nuevo
        response = client.post(
            f"/api/v1/money-movements/{movement_id}/annul",
            json={"reason": "Otro error"},
            headers=org_headers,
        )
        assert response.status_code == 400
        assert "ya esta anulado" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Tests: Listado y filtros
# ---------------------------------------------------------------------------

class TestListAndFilter:
    """Tests para GET /api/v1/money-movements."""

    def test_list_empty(self, client: TestClient, org_headers: dict):
        """Lista vacia retorna total=0."""
        response = client.get("/api/v1/money-movements", headers=org_headers)
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_list_with_movements(
        self, client: TestClient, org_headers: dict,
        test_account, test_supplier, test_customer,
    ):
        """Listar multiples movimientos."""
        # Crear pago y cobro
        client.post("/api/v1/money-movements/supplier-payment", json={
            "supplier_id": str(test_supplier.id),
            "amount": 100000,
            "account_id": str(test_account.id),
            "date": "2026-02-14T10:00:00Z",
        }, headers=org_headers)

        client.post("/api/v1/money-movements/customer-collection", json={
            "customer_id": str(test_customer.id),
            "amount": 200000,
            "account_id": str(test_account.id),
            "date": "2026-02-14T11:00:00Z",
        }, headers=org_headers)

        response = client.get("/api/v1/money-movements", headers=org_headers)
        assert response.status_code == 200
        assert response.json()["total"] == 2

    def test_list_filter_by_type(
        self, client: TestClient, org_headers: dict,
        test_account, test_supplier, test_customer,
    ):
        """Filtrar por tipo de movimiento."""
        client.post("/api/v1/money-movements/supplier-payment", json={
            "supplier_id": str(test_supplier.id),
            "amount": 100000,
            "account_id": str(test_account.id),
            "date": "2026-02-14T10:00:00Z",
        }, headers=org_headers)

        client.post("/api/v1/money-movements/customer-collection", json={
            "customer_id": str(test_customer.id),
            "amount": 200000,
            "account_id": str(test_account.id),
            "date": "2026-02-14T11:00:00Z",
        }, headers=org_headers)

        response = client.get(
            "/api/v1/money-movements?movement_type=payment_to_supplier",
            headers=org_headers,
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["items"][0]["movement_type"] == "payment_to_supplier"

    def test_list_pagination(
        self, client: TestClient, org_headers: dict,
        test_account, test_expense_category,
    ):
        """Paginacion con limit=1."""
        for i in range(3):
            client.post("/api/v1/money-movements/service-income", json={
                "amount": 100000,
                "account_id": str(test_account.id),
                "description": f"Ingreso {i+1}",
                "date": "2026-02-14T10:00:00Z",
            }, headers=org_headers)

        response = client.get(
            "/api/v1/money-movements?skip=0&limit=1",
            headers=org_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 1


# ---------------------------------------------------------------------------
# Tests: Consultas especiales
# ---------------------------------------------------------------------------

class TestSpecialQueries:
    """Tests para by-number, by-account, by-third-party, summary."""

    def test_get_by_number(
        self, client: TestClient, org_headers: dict,
        test_account,
    ):
        """Obtener movimiento por numero secuencial."""
        client.post("/api/v1/money-movements/service-income", json={
            "amount": 500000,
            "account_id": str(test_account.id),
            "description": "Ingreso test",
            "date": "2026-02-14T10:00:00Z",
        }, headers=org_headers)

        response = client.get(
            "/api/v1/money-movements/by-number/1",
            headers=org_headers,
        )
        assert response.status_code == 200
        assert response.json()["movement_number"] == 1

    def test_get_by_account(
        self, client: TestClient, org_headers: dict,
        test_account, test_account2,
    ):
        """Movimientos filtrados por cuenta."""
        # Ingreso en cuenta 1
        client.post("/api/v1/money-movements/service-income", json={
            "amount": 100000,
            "account_id": str(test_account.id),
            "description": "Ingreso caja",
            "date": "2026-02-14T10:00:00Z",
        }, headers=org_headers)

        # Ingreso en cuenta 2
        client.post("/api/v1/money-movements/service-income", json={
            "amount": 200000,
            "account_id": str(test_account2.id),
            "description": "Ingreso banco",
            "date": "2026-02-14T11:00:00Z",
        }, headers=org_headers)

        response = client.get(
            f"/api/v1/money-movements/account/{test_account.id}",
            headers=org_headers,
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_get_summary(
        self, client: TestClient, org_headers: dict,
        test_account, test_supplier, test_customer,
    ):
        """Resumen por tipo."""
        client.post("/api/v1/money-movements/supplier-payment", json={
            "supplier_id": str(test_supplier.id),
            "amount": 100000,
            "account_id": str(test_account.id),
            "date": "2026-02-14T10:00:00Z",
        }, headers=org_headers)

        client.post("/api/v1/money-movements/customer-collection", json={
            "customer_id": str(test_customer.id),
            "amount": 200000,
            "account_id": str(test_account.id),
            "date": "2026-02-14T11:00:00Z",
        }, headers=org_headers)

        response = client.get(
            "/api/v1/money-movements/summary",
            headers=org_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_not_found(self, client: TestClient, org_headers: dict):
        """ID inexistente retorna 404."""
        response = client.get(
            f"/api/v1/money-movements/{uuid4()}",
            headers=org_headers,
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Autenticacion
# ---------------------------------------------------------------------------

class TestAuth:
    """Tests de autenticacion."""

    def test_without_auth(self, client: TestClient):
        """Sin autenticacion retorna 401."""
        response = client.get("/api/v1/money-movements")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Tests: Aislamiento multi-tenant
# ---------------------------------------------------------------------------

class TestOrganizationIsolation:
    """Verificar aislamiento entre organizaciones."""

    def test_cannot_access_other_org_movement(
        self, client: TestClient, org_headers: dict,
        db_session, test_organization2,
    ):
        """Movimiento de otra org retorna 404."""
        from app.models.money_movement import MoneyMovement
        from app.models.money_account import MoneyAccount

        # Crear cuenta y movimiento en org2
        account_org2 = MoneyAccount(
            name="Caja Org2",
            account_type="cash",
            current_balance=Decimal("1000000.00"),
            organization_id=test_organization2.id,
        )
        db_session.add(account_org2)
        db_session.commit()
        db_session.refresh(account_org2)

        movement = MoneyMovement(
            organization_id=test_organization2.id,
            movement_number=1,
            date=datetime.now(timezone.utc),
            movement_type="service_income",
            amount=Decimal("100000.00"),
            account_id=account_org2.id,
            description="Ingreso org2",
            status="confirmed",
        )
        db_session.add(movement)
        db_session.commit()
        db_session.refresh(movement)

        # Intentar acceder desde org1
        response = client.get(
            f"/api/v1/money-movements/{movement.id}",
            headers=org_headers,
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Numeracion secuencial
# ---------------------------------------------------------------------------

class TestSequentialNumbering:
    """Tests para numeracion secuencial de movimientos."""

    def test_sequential_numbers(
        self, client: TestClient, org_headers: dict,
        test_account,
    ):
        """Cada movimiento recibe numero secuencial incrementado."""
        numbers = []
        for i in range(3):
            resp = client.post("/api/v1/money-movements/service-income", json={
                "amount": 100000,
                "account_id": str(test_account.id),
                "description": f"Ingreso {i+1}",
                "date": "2026-02-14T10:00:00Z",
            }, headers=org_headers)
            numbers.append(resp.json()["movement_number"])

        assert numbers == [1, 2, 3]
