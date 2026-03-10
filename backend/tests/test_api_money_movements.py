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


# ---------------------------------------------------------------------------
# Fixtures para provisiones
# ---------------------------------------------------------------------------

@pytest.fixture
def test_provision(db_session: Session, test_organization) -> ThirdParty:
    """Provision con fondos disponibles ($500,000)."""
    tp = ThirdParty(
        name="Provision Mantenimiento",
        is_provision=True,
        provision_type="maintenance",
        current_balance=Decimal("-500000.00"),  # negativo = fondos disponibles
        organization_id=test_organization.id,
    )
    db_session.add(tp)
    db_session.commit()
    db_session.refresh(tp)
    return tp


@pytest.fixture
def test_provision_empty(db_session: Session, test_organization) -> ThirdParty:
    """Provision sin fondos (balance 0)."""
    tp = ThirdParty(
        name="Provision Vacia",
        is_provision=True,
        provision_type="other",
        current_balance=Decimal("0.00"),
        organization_id=test_organization.id,
    )
    db_session.add(tp)
    db_session.commit()
    db_session.refresh(tp)
    return tp


@pytest.fixture
def test_provision_overspent(db_session: Session, test_organization) -> ThirdParty:
    """Provision en sobregiro (balance > 0)."""
    tp = ThirdParty(
        name="Provision Sobregiro",
        is_provision=True,
        provision_type="other",
        current_balance=Decimal("100000.00"),  # sobregiro
        organization_id=test_organization.id,
    )
    db_session.add(tp)
    db_session.commit()
    db_session.refresh(tp)
    return tp


# ---------------------------------------------------------------------------
# Tests: Provisiones
# ---------------------------------------------------------------------------

class TestProvisionDeposit:
    """Tests para POST /api/v1/money-movements/provision-deposit."""

    def test_provision_deposit(
        self, client: TestClient, org_headers: dict,
        test_account, test_provision, db_session,
    ):
        """Deposito a provision — verifica saldos de cuenta y provision."""
        payload = {
            "provision_id": str(test_provision.id),
            "amount": 200000,
            "account_id": str(test_account.id),
            "date": "2026-03-01T10:00:00Z",
            "description": "Aporte a provision mantenimiento",
        }
        resp = client.post(
            "/api/v1/money-movements/provision-deposit",
            json=payload, headers=org_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["movement_type"] == "provision_deposit"
        assert data["amount"] == 200000.0
        assert data["third_party_name"] == "Provision Mantenimiento"

        # Verificar saldos
        db_session.refresh(test_account)
        db_session.refresh(test_provision)
        assert test_account.current_balance == Decimal("9800000.00")  # 10M - 200K
        assert test_provision.current_balance == Decimal("-700000.00")  # -500K - 200K

    def test_provision_deposit_insufficient_funds(
        self, client: TestClient, org_headers: dict,
        test_account, test_provision,
    ):
        """Deposito que excede saldo de cuenta — 400."""
        payload = {
            "provision_id": str(test_provision.id),
            "amount": 99000000,
            "account_id": str(test_account.id),
            "date": "2026-03-01T10:00:00Z",
        }
        resp = client.post(
            "/api/v1/money-movements/provision-deposit",
            json=payload, headers=org_headers,
        )
        assert resp.status_code == 400
        assert "Fondos insuficientes" in resp.json()["detail"]


class TestProvisionExpense:
    """Tests para POST /api/v1/money-movements/provision-expense."""

    def test_provision_expense(
        self, client: TestClient, org_headers: dict,
        test_provision, test_expense_category, test_account, db_session,
    ):
        """Gasto desde provision — provision(+), cuenta sin cambio."""
        initial_account_balance = test_account.current_balance
        payload = {
            "provision_id": str(test_provision.id),
            "amount": 100000,
            "expense_category_id": str(test_expense_category.id),
            "date": "2026-03-02T10:00:00Z",
            "description": "Reparacion equipo",
        }
        resp = client.post(
            "/api/v1/money-movements/provision-expense",
            json=payload, headers=org_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["movement_type"] == "provision_expense"
        assert data["account_id"] is None
        assert data["amount"] == 100000.0

        # Verificar saldos
        db_session.refresh(test_provision)
        db_session.refresh(test_account)
        assert test_provision.current_balance == Decimal("-400000.00")  # -500K + 100K
        assert test_account.current_balance == initial_account_balance  # Sin cambio

    def test_provision_expense_insufficient_funds(
        self, client: TestClient, org_headers: dict,
        test_provision, test_expense_category,
    ):
        """Gasto que excede fondos de provision — 400."""
        payload = {
            "provision_id": str(test_provision.id),
            "amount": 600000,  # provision tiene 500K
            "expense_category_id": str(test_expense_category.id),
            "date": "2026-03-02T10:00:00Z",
            "description": "Gasto excesivo",
        }
        resp = client.post(
            "/api/v1/money-movements/provision-expense",
            json=payload, headers=org_headers,
        )
        assert resp.status_code == 400
        assert "Fondos insuficientes" in resp.json()["detail"]

    def test_provision_expense_when_overspent(
        self, client: TestClient, org_headers: dict,
        test_provision_overspent, test_expense_category,
    ):
        """Gasto desde provision en sobregiro — 400."""
        payload = {
            "provision_id": str(test_provision_overspent.id),
            "amount": 10000,
            "expense_category_id": str(test_expense_category.id),
            "date": "2026-03-02T10:00:00Z",
            "description": "Intento gasto sobregiro",
        }
        resp = client.post(
            "/api/v1/money-movements/provision-expense",
            json=payload, headers=org_headers,
        )
        assert resp.status_code == 400
        assert "sobregiro" in resp.json()["detail"]


class TestProvisionAnnulment:
    """Tests para anulacion de movimientos de provision."""

    def test_annul_provision_deposit(
        self, client: TestClient, org_headers: dict,
        test_account, test_provision, db_session,
    ):
        """Anular deposito a provision — reversa ambos saldos."""
        # Crear deposito
        resp = client.post(
            "/api/v1/money-movements/provision-deposit",
            json={
                "provision_id": str(test_provision.id),
                "amount": 200000,
                "account_id": str(test_account.id),
                "date": "2026-03-01T10:00:00Z",
            },
            headers=org_headers,
        )
        movement_id = resp.json()["id"]

        # Anular
        resp = client.post(
            f"/api/v1/money-movements/{movement_id}/annul",
            json={"reason": "Error en monto"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "annulled"

        # Saldos vuelven al original
        db_session.refresh(test_account)
        db_session.refresh(test_provision)
        assert test_account.current_balance == Decimal("10000000.00")
        assert test_provision.current_balance == Decimal("-500000.00")

    def test_annul_provision_expense(
        self, client: TestClient, org_headers: dict,
        test_provision, test_expense_category, test_account, db_session,
    ):
        """Anular gasto de provision — reversa solo provision."""
        initial_account = test_account.current_balance

        # Crear gasto
        resp = client.post(
            "/api/v1/money-movements/provision-expense",
            json={
                "provision_id": str(test_provision.id),
                "amount": 100000,
                "expense_category_id": str(test_expense_category.id),
                "date": "2026-03-02T10:00:00Z",
                "description": "Gasto a anular",
            },
            headers=org_headers,
        )
        movement_id = resp.json()["id"]

        # Anular
        resp = client.post(
            f"/api/v1/money-movements/{movement_id}/annul",
            json={"reason": "Error"},
            headers=org_headers,
        )
        assert resp.status_code == 200

        db_session.refresh(test_provision)
        db_session.refresh(test_account)
        assert test_provision.current_balance == Decimal("-500000.00")  # Vuelve al original
        assert test_account.current_balance == initial_account  # Sin cambio


# ---------------------------------------------------------------------------
# Tests: Estado de Cuenta con saldo corrido
# ---------------------------------------------------------------------------

class TestAccountStatement:
    """Tests para GET /api/v1/money-movements/third-party/{id} con balance."""

    def test_third_party_movements_with_balance(
        self, client: TestClient, org_headers: dict,
        test_account, test_supplier, db_session,
    ):
        """Movimientos de tercero incluyen balance_after correcto."""
        # Crear 3 pagos al proveedor
        for amt in [500000, 300000, 200000]:
            client.post(
                "/api/v1/money-movements/supplier-payment",
                json={
                    "supplier_id": str(test_supplier.id),
                    "amount": amt,
                    "account_id": str(test_account.id),
                    "date": "2026-03-01T10:00:00Z",
                },
                headers=org_headers,
            )

        resp = client.get(
            f"/api/v1/money-movements/third-party/{test_supplier.id}",
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

        # Ordenado DESC por defecto, asi que items[0] es el ultimo
        # Pero balance se calcula ASC. Verificar que balance_after existe
        for item in data["items"]:
            assert "balance_after" in item
            assert item["balance_after"] is not None

        # Balance final = sum de pagos con direccion +1
        # Proveedor empieza en 0 (balance calculado), pagos: +500K, +800K, +1M
        balances = sorted(
            [(i["movement_number"], i["balance_after"]) for i in data["items"]],
            key=lambda x: x[0],
        )
        assert balances[0][1] == 500000.0   # primer pago
        assert balances[1][1] == 800000.0   # +300K
        assert balances[2][1] == 1000000.0  # +200K

    def test_balance_with_date_filter_opening_balance(
        self, client: TestClient, org_headers: dict,
        test_account, test_supplier, db_session,
    ):
        """Con date_from, opening_balance refleja movimientos anteriores."""
        # Pago en febrero
        client.post(
            "/api/v1/money-movements/supplier-payment",
            json={
                "supplier_id": str(test_supplier.id),
                "amount": 500000,
                "account_id": str(test_account.id),
                "date": "2026-02-15T10:00:00Z",
            },
            headers=org_headers,
        )
        # Pago en marzo
        client.post(
            "/api/v1/money-movements/supplier-payment",
            json={
                "supplier_id": str(test_supplier.id),
                "amount": 300000,
                "account_id": str(test_account.id),
                "date": "2026-03-05T10:00:00Z",
            },
            headers=org_headers,
        )

        # Consultar solo marzo
        resp = client.get(
            f"/api/v1/money-movements/third-party/{test_supplier.id}",
            params={"date_from": "2026-03-01", "date_to": "2026-03-31"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1  # Solo el de marzo
        assert data["opening_balance"] == 500000.0  # El de febrero como apertura
        assert data["items"][0]["balance_after"] == 800000.0  # 500K + 300K


# ---------------------------------------------------------------------------
# Tests: Treasury Dashboard
# ---------------------------------------------------------------------------

class TestTreasuryDashboard:
    """Tests para GET /api/v1/reports/treasury-dashboard."""

    def test_treasury_dashboard_accounts_by_type(
        self, client: TestClient, org_headers: dict,
        test_account, test_account2,
    ):
        """Dashboard muestra cuentas agrupadas por tipo."""
        resp = client.get(
            "/api/v1/reports/treasury-dashboard",
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()

        # test_account = cash, test_account2 = bank
        assert len(data["cash_accounts"]) >= 1
        assert len(data["bank_accounts"]) >= 1
        assert data["total_cash"] >= 10000000.0
        assert data["total_bank"] >= 5000000.0
        assert data["total_all_accounts"] >= 15000000.0

    def test_treasury_dashboard_provisions(
        self, client: TestClient, org_headers: dict,
        test_provision, test_account,
    ):
        """Dashboard incluye provisiones con fondos disponibles."""
        resp = client.get(
            "/api/v1/reports/treasury-dashboard",
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()

        assert len(data["provisions"]) >= 1
        prov = next(p for p in data["provisions"] if p["name"] == "Provision Mantenimiento")
        assert prov["current_balance"] == -500000.0
        assert prov["available_funds"] == 500000.0
        assert data["total_provision_available"] >= 500000.0

    def test_treasury_dashboard_recent_movements(
        self, client: TestClient, org_headers: dict,
        test_account, test_supplier,
    ):
        """Dashboard muestra ultimos movimientos."""
        # Crear un movimiento
        client.post(
            "/api/v1/money-movements/supplier-payment",
            json={
                "supplier_id": str(test_supplier.id),
                "amount": 100000,
                "account_id": str(test_account.id),
                "date": "2026-03-09T10:00:00Z",
            },
            headers=org_headers,
        )

        resp = client.get(
            "/api/v1/reports/treasury-dashboard",
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["recent_movements"]) >= 1
        assert data["recent_movements"][0]["movement_type"] == "payment_to_supplier"


class TestAdvancePayment:
    """Tests para POST /api/v1/money-movements/advance-payment."""

    def test_advance_payment(
        self, client: TestClient, org_headers: dict,
        test_account, test_supplier, db_session,
    ):
        """Anticipo a proveedor — account(-), supplier(+)."""
        payload = {
            "supplier_id": str(test_supplier.id),
            "amount": 500000,
            "account_id": str(test_account.id),
            "date": "2026-03-01T10:00:00Z",
            "description": "Anticipo compra futura",
        }
        resp = client.post(
            "/api/v1/money-movements/advance-payment",
            json=payload, headers=org_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["movement_type"] == "advance_payment"
        assert data["amount"] == 500000.0
        assert data["third_party_name"] == "Metales XYZ"

        db_session.refresh(test_account)
        db_session.refresh(test_supplier)
        assert test_account.current_balance == Decimal("9500000.00")  # 10M - 500K
        assert test_supplier.current_balance == Decimal("-1500000.00")  # -2M + 500K

    def test_advance_payment_insufficient_funds(
        self, client: TestClient, org_headers: dict,
        test_account, test_supplier,
    ):
        """Anticipo que excede saldo de cuenta — 400."""
        payload = {
            "supplier_id": str(test_supplier.id),
            "amount": 99000000,
            "account_id": str(test_account.id),
            "date": "2026-03-01T10:00:00Z",
        }
        resp = client.post(
            "/api/v1/money-movements/advance-payment",
            json=payload, headers=org_headers,
        )
        assert resp.status_code == 400
        assert "Fondos insuficientes" in resp.json()["detail"]


class TestAdvanceCollection:
    """Tests para POST /api/v1/money-movements/advance-collection."""

    def test_advance_collection(
        self, client: TestClient, org_headers: dict,
        test_account, test_customer, db_session,
    ):
        """Anticipo de cliente — account(+), customer(-)."""
        payload = {
            "customer_id": str(test_customer.id),
            "amount": 1000000,
            "account_id": str(test_account.id),
            "date": "2026-03-01T10:00:00Z",
            "description": "Anticipo pedido grande",
        }
        resp = client.post(
            "/api/v1/money-movements/advance-collection",
            json=payload, headers=org_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["movement_type"] == "advance_collection"
        assert data["amount"] == 1000000.0
        assert data["third_party_name"] == "Industrial ABC"

        db_session.refresh(test_account)
        db_session.refresh(test_customer)
        assert test_account.current_balance == Decimal("11000000.00")  # 10M + 1M
        assert test_customer.current_balance == Decimal("2000000.00")  # 3M - 1M

    def test_annul_advance_payment(
        self, client: TestClient, org_headers: dict,
        test_account, test_supplier, db_session,
    ):
        """Anular anticipo a proveedor — reversa correcta."""
        # Crear anticipo
        payload = {
            "supplier_id": str(test_supplier.id),
            "amount": 300000,
            "account_id": str(test_account.id),
            "date": "2026-03-01T10:00:00Z",
        }
        resp = client.post(
            "/api/v1/money-movements/advance-payment",
            json=payload, headers=org_headers,
        )
        assert resp.status_code == 201
        movement_id = resp.json()["id"]

        # Anular
        resp = client.post(
            f"/api/v1/money-movements/{movement_id}/annul",
            json={"reason": "Error en monto"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "annulled"

        db_session.refresh(test_account)
        db_session.refresh(test_supplier)
        assert test_account.current_balance == Decimal("10000000.00")  # Restaurado
        assert test_supplier.current_balance == Decimal("-2000000.00")  # Restaurado

    def test_annul_advance_collection(
        self, client: TestClient, org_headers: dict,
        test_account, test_customer, db_session,
    ):
        """Anular anticipo de cliente — reversa correcta."""
        payload = {
            "customer_id": str(test_customer.id),
            "amount": 500000,
            "account_id": str(test_account.id),
            "date": "2026-03-01T10:00:00Z",
        }
        resp = client.post(
            "/api/v1/money-movements/advance-collection",
            json=payload, headers=org_headers,
        )
        assert resp.status_code == 201
        movement_id = resp.json()["id"]

        resp = client.post(
            f"/api/v1/money-movements/{movement_id}/annul",
            json={"reason": "Cliente cancelo"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "annulled"

        db_session.refresh(test_account)
        db_session.refresh(test_customer)
        assert test_account.current_balance == Decimal("10000000.00")
        assert test_customer.current_balance == Decimal("3000000.00")


# ---------------------------------------------------------------------------
# Tests de evidencia (upload / download / delete)
# ---------------------------------------------------------------------------

class TestEvidence:
    """Tests para subir, descargar y eliminar comprobantes de movimientos."""

    def _create_movement(self, client, org_headers, account_id, supplier_id):
        """Helper: crea un pago a proveedor y retorna el ID."""
        payload = {
            "supplier_id": supplier_id,
            "amount": 100000,
            "account_id": account_id,
            "date": "2026-03-01T10:00:00Z",
            "description": "Pago test evidencia",
        }
        resp = client.post(
            "/api/v1/money-movements/supplier-payment",
            json=payload, headers=org_headers,
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_upload_evidence(
        self, client: TestClient, org_headers: dict,
        test_account, test_supplier,
    ):
        """Subir comprobante a un movimiento."""
        mid = self._create_movement(client, org_headers, str(test_account.id), str(test_supplier.id))

        # Crear archivo de prueba (PNG falso de pocos bytes)
        import io
        fake_file = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        resp = client.post(
            f"/api/v1/money-movements/{mid}/evidence",
            headers=org_headers,
            files={"file": ("comprobante.png", fake_file, "image/png")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["evidence_url"] is not None
        assert "evidence/" in data["evidence_url"]

    def test_upload_evidence_invalid_extension(
        self, client: TestClient, org_headers: dict,
        test_account, test_supplier,
    ):
        """Archivo con extension no permitida — 400."""
        mid = self._create_movement(client, org_headers, str(test_account.id), str(test_supplier.id))

        import io
        fake_file = io.BytesIO(b"not a real exe")
        resp = client.post(
            f"/api/v1/money-movements/{mid}/evidence",
            headers=org_headers,
            files={"file": ("virus.exe", fake_file, "application/octet-stream")},
        )
        assert resp.status_code == 400
        assert "no permitido" in resp.json()["detail"]

    def test_download_evidence(
        self, client: TestClient, org_headers: dict,
        test_account, test_supplier,
    ):
        """Subir y luego descargar comprobante."""
        mid = self._create_movement(client, org_headers, str(test_account.id), str(test_supplier.id))

        import io
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        fake_file = io.BytesIO(content)
        client.post(
            f"/api/v1/money-movements/{mid}/evidence",
            headers=org_headers,
            files={"file": ("test.png", fake_file, "image/png")},
        )

        resp = client.get(
            f"/api/v1/money-movements/{mid}/evidence",
            headers=org_headers,
        )
        assert resp.status_code == 200
        assert resp.content == content

    def test_download_evidence_not_found(
        self, client: TestClient, org_headers: dict,
        test_account, test_supplier,
    ):
        """Descargar sin comprobante — 404."""
        mid = self._create_movement(client, org_headers, str(test_account.id), str(test_supplier.id))

        resp = client.get(
            f"/api/v1/money-movements/{mid}/evidence",
            headers=org_headers,
        )
        assert resp.status_code == 404

    def test_delete_evidence(
        self, client: TestClient, org_headers: dict,
        test_account, test_supplier,
    ):
        """Eliminar comprobante — evidence_url = None."""
        mid = self._create_movement(client, org_headers, str(test_account.id), str(test_supplier.id))

        import io
        fake_file = io.BytesIO(b"\x89PNG" + b"\x00" * 50)
        client.post(
            f"/api/v1/money-movements/{mid}/evidence",
            headers=org_headers,
            files={"file": ("test.png", fake_file, "image/png")},
        )

        resp = client.delete(
            f"/api/v1/money-movements/{mid}/evidence",
            headers=org_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["evidence_url"] is None

    def test_upload_replaces_existing(
        self, client: TestClient, org_headers: dict,
        test_account, test_supplier,
    ):
        """Subir segundo archivo reemplaza el primero."""
        mid = self._create_movement(client, org_headers, str(test_account.id), str(test_supplier.id))

        import io
        # Primer upload
        f1 = io.BytesIO(b"file1content")
        resp1 = client.post(
            f"/api/v1/money-movements/{mid}/evidence",
            headers=org_headers,
            files={"file": ("first.pdf", f1, "application/pdf")},
        )
        url1 = resp1.json()["evidence_url"]

        # Segundo upload
        f2 = io.BytesIO(b"file2content")
        resp2 = client.post(
            f"/api/v1/money-movements/{mid}/evidence",
            headers=org_headers,
            files={"file": ("second.jpg", f2, "image/jpeg")},
        )
        url2 = resp2.json()["evidence_url"]

        assert url1 != url2

        # Descargar retorna segundo archivo
        resp = client.get(
            f"/api/v1/money-movements/{mid}/evidence",
            headers=org_headers,
        )
        assert resp.content == b"file2content"
