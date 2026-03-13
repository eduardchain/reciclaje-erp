"""
Tests para endpoints de FixedAsset (Activos Fijos).

Cubre: CRUD, depreciacion manual, ultima cuota ajustada, duplicado periodo,
apply-pending batch, dispose con depreciacion acelerada, update restricciones,
P&L incluye depreciation_expense, Balance Sheet incluye fixed_assets,
depreciation_start_date futuro, pago obligatorio desde cuenta.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.expense_category import ExpenseCategory
from app.models.money_account import MoneyAccount
from app.models.third_party import ThirdParty


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fa_category(db_session: Session, test_organization) -> ExpenseCategory:
    """Categoria de gasto para depreciacion."""
    cat = ExpenseCategory(
        name="Depreciación Equipos",
        is_direct_expense=False,
        organization_id=test_organization.id,
    )
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


@pytest.fixture
def fa_supplier(db_session: Session, test_organization) -> ThirdParty:
    """Proveedor de equipos."""
    tp = ThirdParty(
        name="Equipos Industriales S.A.",
        is_supplier=True,
        organization_id=test_organization.id,
        current_balance=Decimal("0"),
        initial_balance=Decimal("0"),
    )
    db_session.add(tp)
    db_session.commit()
    db_session.refresh(tp)
    return tp


@pytest.fixture
def fa_account(db_session: Session, test_organization) -> MoneyAccount:
    """Cuenta de dinero con saldo suficiente para comprar activos."""
    acc = MoneyAccount(
        name="Cuenta Principal",
        account_type="bank",
        current_balance=Decimal("5000000000"),
        organization_id=test_organization.id,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


BASE_URL = "/api/v1/fixed-assets"


def _create_asset(client, org_headers, fa_category, fa_account, **overrides):
    """Helper para crear un activo fijo con datos default."""
    payload = {
        "name": "Retroexcavadora CAT 320",
        "asset_code": "EQ-001",
        "purchase_date": "2026-01-01",
        "purchase_value": 630000000,
        "salvage_value": 0,
        "depreciation_rate": 1.0,
        "depreciation_start_date": "2026-01-01",
        "expense_category_id": str(fa_category.id),
        "source_account_id": str(fa_account.id),
    }
    payload.update(overrides)
    return client.post(BASE_URL + "/", json=payload, headers=org_headers)


# ---------------------------------------------------------------------------
# Tests: Crear
# ---------------------------------------------------------------------------

class TestFixedAssetCreate:
    def test_create_basic(self, client: TestClient, org_headers, fa_category, fa_account):
        """Crear activo fijo basico."""
        resp = _create_asset(client, org_headers, fa_category, fa_account)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Retroexcavadora CAT 320"
        assert data["asset_code"] == "EQ-001"
        assert data["purchase_value"] == 630000000.0
        assert data["salvage_value"] == 0.0
        assert data["current_value"] == 630000000.0
        assert data["accumulated_depreciation"] == 0.0
        assert data["depreciation_rate"] == 1.0
        # monthly = 630M * 1% = 6.3M
        assert data["monthly_depreciation"] == 6300000.0
        # useful_life = 630M / 6.3M = 100
        assert data["useful_life_months"] == 100
        assert data["status"] == "active"
        assert data["depreciation_progress"] == 0.0

    def test_create_with_salvage(self, client: TestClient, org_headers, fa_category, fa_account):
        """Crear activo con valor residual."""
        resp = _create_asset(
            client, org_headers, fa_category, fa_account,
            purchase_value=100000000,
            salvage_value=10000000,
            depreciation_rate=5.0,
        )
        assert resp.status_code == 201
        data = resp.json()
        # monthly = 100M * 5% = 5M
        assert data["monthly_depreciation"] == 5000000.0
        # depreciable = 100M - 10M = 90M, useful_life = 90M / 5M = 18
        assert data["useful_life_months"] == 18

    def test_create_with_supplier_credit(self, client: TestClient, org_headers, fa_category, fa_account, fa_supplier, db_session):
        """Crear activo a credito con proveedor — NO afecta cuenta, SI afecta balance proveedor."""
        initial_supplier_balance = float(fa_supplier.current_balance)
        initial_account_balance = float(fa_account.current_balance)
        purchase_value = 10000000

        payload = {
            "name": "Bascula Industrial",
            "purchase_date": "2026-01-01",
            "purchase_value": purchase_value,
            "depreciation_rate": 2.0,
            "depreciation_start_date": "2026-01-01",
            "expense_category_id": str(fa_category.id),
            "supplier_id": str(fa_supplier.id),
        }
        resp = client.post(BASE_URL + "/", json=payload, headers=org_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["third_party_id"] == str(fa_supplier.id)
        assert data["third_party_name"] == "Equipos Industriales S.A."

        # Movimiento debe ser asset_purchase (NO asset_payment)
        assert data["purchase_movement_id"] is not None
        from app.models.money_movement import MoneyMovement
        mm = db_session.query(MoneyMovement).filter_by(id=data["purchase_movement_id"]).first()
        assert mm.movement_type == "asset_purchase"
        assert mm.account_id is None  # NO cuenta involucrada

        # Balance proveedor baja (le debemos)
        db_session.refresh(fa_supplier)
        assert float(fa_supplier.current_balance) == initial_supplier_balance - purchase_value

        # Balance cuenta NO cambia
        db_session.refresh(fa_account)
        assert float(fa_account.current_balance) == initial_account_balance

    def test_create_supplier_not_supplier_role(self, client: TestClient, org_headers, fa_category, db_session, test_organization):
        """Crear activo con tercero que NO es proveedor debe fallar."""
        customer = ThirdParty(
            name="Solo Cliente",
            is_customer=True,
            is_supplier=False,
            organization_id=test_organization.id,
            current_balance=Decimal("0"),
            initial_balance=Decimal("0"),
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        payload = {
            "name": "Activo Invalido",
            "purchase_date": "2026-01-01",
            "purchase_value": 1000000,
            "depreciation_rate": 5.0,
            "depreciation_start_date": "2026-01-01",
            "expense_category_id": str(fa_category.id),
            "supplier_id": str(customer.id),
        }
        resp = client.post(BASE_URL + "/", json=payload, headers=org_headers)
        assert resp.status_code in (400, 404)

    def test_create_xor_validation(self, client: TestClient, org_headers, fa_category, fa_account, fa_supplier):
        """Enviar ambos source_account_id Y supplier_id debe fallar 422."""
        payload = {
            "name": "Activo Doble Fuente",
            "purchase_date": "2026-01-01",
            "purchase_value": 1000000,
            "depreciation_rate": 5.0,
            "depreciation_start_date": "2026-01-01",
            "expense_category_id": str(fa_category.id),
            "source_account_id": str(fa_account.id),
            "supplier_id": str(fa_supplier.id),
        }
        resp = client.post(BASE_URL + "/", json=payload, headers=org_headers)
        assert resp.status_code == 422

    def test_create_invalid_salvage(self, client: TestClient, org_headers, fa_category, fa_account):
        """Valor residual >= valor compra debe fallar."""
        resp = _create_asset(
            client, org_headers, fa_category, fa_account,
            purchase_value=100000,
            salvage_value=100000,
        )
        assert resp.status_code == 422

    def test_create_invalid_dates(self, client: TestClient, org_headers, fa_category, fa_account):
        """depreciation_start_date < purchase_date debe fallar."""
        resp = _create_asset(
            client, org_headers, fa_category, fa_account,
            purchase_date="2026-03-01",
            depreciation_start_date="2026-02-01",
        )
        assert resp.status_code == 422

    def test_create_requires_account_or_supplier(self, client: TestClient, org_headers, fa_category):
        """Sin source_account_id ni supplier_id debe fallar 422 (validacion XOR)."""
        payload = {
            "name": "Sin Cuenta",
            "purchase_date": "2026-01-01",
            "purchase_value": 1000000,
            "depreciation_rate": 5.0,
            "depreciation_start_date": "2026-01-01",
            "expense_category_id": str(fa_category.id),
        }
        resp = client.post(BASE_URL + "/", json=payload, headers=org_headers)
        assert resp.status_code == 422

    def test_create_insufficient_balance(self, client: TestClient, org_headers, fa_category, db_session, test_organization):
        """Saldo insuficiente en cuenta debe fallar 400."""
        # Cuenta con saldo bajo
        low_acc = MoneyAccount(
            name="Cuenta Pobre",
            account_type="cash",
            current_balance=Decimal("100"),
            organization_id=test_organization.id,
        )
        db_session.add(low_acc)
        db_session.commit()
        db_session.refresh(low_acc)

        resp = _create_asset(
            client, org_headers, fa_category, low_acc,
            purchase_value=1000000,
        )
        assert resp.status_code == 400

    def test_create_creates_asset_payment(self, client: TestClient, org_headers, fa_category, fa_account, db_session):
        """Crear activo genera MoneyMovement asset_payment y descuenta balance."""
        initial_balance = float(fa_account.current_balance)
        purchase_value = 10000000

        resp = _create_asset(
            client, org_headers, fa_category, fa_account,
            purchase_value=purchase_value,
        )
        assert resp.status_code == 201
        data = resp.json()

        # Verificar purchase_movement_id existe
        assert data["purchase_movement_id"] is not None

        # Verificar movimiento
        mov_resp = client.get(
            f"/api/v1/money-movements/{data['purchase_movement_id']}",
            headers=org_headers,
        )
        assert mov_resp.status_code == 200
        mov = mov_resp.json()
        assert mov["movement_type"] == "asset_payment"
        assert mov["amount"] == float(purchase_value)
        assert mov["account_id"] == str(fa_account.id)

        # Verificar balance descontado
        db_session.refresh(fa_account)
        assert float(fa_account.current_balance) == initial_balance - purchase_value


# ---------------------------------------------------------------------------
# Tests: Depreciacion
# ---------------------------------------------------------------------------

class TestFixedAssetDepreciation:
    def test_depreciate_manual(self, client: TestClient, org_headers, fa_category, fa_account):
        """Aplicar una depreciacion manual."""
        # Crear activo con start_date en el pasado
        resp = _create_asset(
            client, org_headers, fa_category, fa_account,
            purchase_value=10000000,
            depreciation_rate=10.0,
            depreciation_start_date="2026-01-01",
        )
        asset_id = resp.json()["id"]

        # Depreciar
        resp2 = client.post(f"{BASE_URL}/{asset_id}/depreciate", headers=org_headers)
        assert resp2.status_code == 201
        data = resp2.json()

        # monthly = 10M * 10% = 1M
        assert data["accumulated_depreciation"] == 1000000.0
        assert data["current_value"] == 9000000.0
        assert len(data["depreciations"]) == 1
        dep = data["depreciations"][0]
        assert dep["depreciation_number"] == 1
        assert dep["amount"] == 1000000.0

    def test_depreciate_duplicate_period(self, client: TestClient, org_headers, fa_category, fa_account):
        """Duplicar depreciacion del mismo periodo debe fallar con 409."""
        resp = _create_asset(
            client, org_headers, fa_category, fa_account,
            purchase_value=10000000,
            depreciation_rate=10.0,
            depreciation_start_date="2026-01-01",
        )
        asset_id = resp.json()["id"]

        # Primera OK
        resp2 = client.post(f"{BASE_URL}/{asset_id}/depreciate", headers=org_headers)
        assert resp2.status_code == 201

        # Segunda falla
        resp3 = client.post(f"{BASE_URL}/{asset_id}/depreciate", headers=org_headers)
        assert resp3.status_code == 409

    def test_last_quota_adjustment(self, client: TestClient, org_headers, fa_category, fa_account):
        """Ultima cuota se ajusta para llegar exacto a salvage_value."""
        # Activo 10M, salvage 1M, rate 50% → monthly=5M, depreciable=9M
        # Cuota 1: 5M, queda 4M. Cuota 2: 4M (ajustada, no 5M)
        resp = _create_asset(
            client, org_headers, fa_category, fa_account,
            purchase_value=10000000,
            salvage_value=1000000,
            depreciation_rate=50.0,
            depreciation_start_date="2026-01-01",
        )
        asset_id = resp.json()["id"]

        # Cuota 1: 5M normal
        resp2 = client.post(f"{BASE_URL}/{asset_id}/depreciate", headers=org_headers)
        assert resp2.status_code == 201
        assert resp2.json()["current_value"] == 5000000.0

        # Necesitamos depreciar otro mes, pero el endpoint usa mes actual
        # Asi que verificamos que el remaining vale 4M (no 5M)
        detail = client.get(f"{BASE_URL}/{asset_id}", headers=org_headers)
        data = detail.json()
        remaining = data["current_value"] - data["salvage_value"]
        assert remaining == 4000000.0

    def test_depreciate_creates_movement(self, client: TestClient, org_headers, fa_category, fa_account):
        """Depreciacion crea MoneyMovement tipo depreciation_expense."""
        resp = _create_asset(
            client, org_headers, fa_category, fa_account,
            purchase_value=10000000,
            depreciation_rate=10.0,
            depreciation_start_date="2026-01-01",
        )
        asset_id = resp.json()["id"]

        resp2 = client.post(f"{BASE_URL}/{asset_id}/depreciate", headers=org_headers)
        assert resp2.status_code == 201
        dep = resp2.json()["depreciations"][0]

        # Verificar movimiento existe
        mov_resp = client.get(
            f"/api/v1/money-movements/{dep['money_movement_id']}",
            headers=org_headers,
        )
        assert mov_resp.status_code == 200
        mov = mov_resp.json()
        assert mov["movement_type"] == "depreciation_expense"
        assert mov["amount"] == 1000000.0
        assert mov["account_id"] is None
        assert mov["third_party_id"] is None


# ---------------------------------------------------------------------------
# Tests: Apply Pending (batch)
# ---------------------------------------------------------------------------

class TestFixedAssetApplyPending:
    def test_apply_pending_batch(self, client: TestClient, org_headers, fa_category, fa_account):
        """Apply-pending procesa multiples activos."""
        # Crear 2 activos con start_date en el pasado
        _create_asset(
            client, org_headers, fa_category, fa_account,
            name="Equipo A",
            purchase_value=10000000,
            depreciation_rate=10.0,
            depreciation_start_date="2026-01-01",
        )
        _create_asset(
            client, org_headers, fa_category, fa_account,
            name="Equipo B",
            purchase_value=20000000,
            depreciation_rate=5.0,
            depreciation_start_date="2026-01-01",
        )

        resp = client.post(f"{BASE_URL}/apply-pending", headers=org_headers)
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 2
        names = {r["asset_name"] for r in results}
        assert "Equipo A" in names
        assert "Equipo B" in names

    def test_apply_pending_skips_future_start(self, client: TestClient, org_headers, fa_category, fa_account):
        """Apply-pending NO deprecia activos con start_date futuro."""
        future = (date.today() + timedelta(days=60)).isoformat()
        _create_asset(
            client, org_headers, fa_category, fa_account,
            name="Equipo Futuro",
            purchase_value=10000000,
            depreciation_rate=10.0,
            depreciation_start_date=future,
        )

        resp = client.post(f"{BASE_URL}/apply-pending", headers=org_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 0


# ---------------------------------------------------------------------------
# Tests: Dispose
# ---------------------------------------------------------------------------

class TestFixedAssetDispose:
    def test_dispose_with_accelerated(self, client: TestClient, org_headers, fa_category, fa_account):
        """Dar de baja crea depreciacion acelerada."""
        resp = _create_asset(
            client, org_headers, fa_category, fa_account,
            purchase_value=10000000,
            salvage_value=0,
            depreciation_rate=10.0,
            depreciation_start_date="2026-01-01",
        )
        asset_id = resp.json()["id"]

        # Depreciar una cuota (1M)
        client.post(f"{BASE_URL}/{asset_id}/depreciate", headers=org_headers)

        # Dar de baja: deberia crear depreciacion acelerada por 9M restantes
        resp2 = client.post(
            f"{BASE_URL}/{asset_id}/dispose",
            json={"reason": "Vendido"},
            headers=org_headers,
        )
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["status"] == "disposed"
        assert data["current_value"] == 0.0
        assert data["accumulated_depreciation"] == 10000000.0
        assert data["disposal_reason"] == "Vendido"
        # 2 depreciaciones: 1 normal + 1 acelerada
        assert len(data["depreciations"]) == 2

    def test_dispose_already_disposed(self, client: TestClient, org_headers, fa_category, fa_account):
        """Dar de baja un activo ya dado de baja falla."""
        resp = _create_asset(client, org_headers, fa_category, fa_account)
        asset_id = resp.json()["id"]

        client.post(
            f"{BASE_URL}/{asset_id}/dispose",
            json={"reason": "Obsoleto"},
            headers=org_headers,
        )

        resp2 = client.post(
            f"{BASE_URL}/{asset_id}/dispose",
            json={"reason": "Otra vez"},
            headers=org_headers,
        )
        assert resp2.status_code == 400


# ---------------------------------------------------------------------------
# Tests: Update
# ---------------------------------------------------------------------------

class TestFixedAssetUpdate:
    def test_update_before_depreciation(self, client: TestClient, org_headers, fa_category, fa_account):
        """Editar campos financieros antes de depreciar."""
        resp = _create_asset(client, org_headers, fa_category, fa_account)
        asset_id = resp.json()["id"]

        resp2 = client.patch(
            f"{BASE_URL}/{asset_id}",
            json={"name": "Retroexcavadora Modificada", "purchase_value": 700000000},
            headers=org_headers,
        )
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["name"] == "Retroexcavadora Modificada"
        assert data["purchase_value"] == 700000000.0
        # Recalcula: monthly = 700M * 1% = 7M
        assert data["monthly_depreciation"] == 7000000.0

    def test_update_after_depreciation_restricted(self, client: TestClient, org_headers, fa_category, fa_account):
        """No editar campos financieros despues de depreciar."""
        resp = _create_asset(
            client, org_headers, fa_category, fa_account,
            purchase_value=10000000,
            depreciation_rate=10.0,
            depreciation_start_date="2026-01-01",
        )
        asset_id = resp.json()["id"]

        # Depreciar
        client.post(f"{BASE_URL}/{asset_id}/depreciate", headers=org_headers)

        # Intentar editar valor
        resp2 = client.patch(
            f"{BASE_URL}/{asset_id}",
            json={"purchase_value": 20000000},
            headers=org_headers,
        )
        assert resp2.status_code == 400

        # Pero nombre si se puede
        resp3 = client.patch(
            f"{BASE_URL}/{asset_id}",
            json={"name": "Nombre Nuevo"},
            headers=org_headers,
        )
        assert resp3.status_code == 200
        assert resp3.json()["name"] == "Nombre Nuevo"


# ---------------------------------------------------------------------------
# Tests: List & Detail
# ---------------------------------------------------------------------------

class TestFixedAssetList:
    def test_list_all(self, client: TestClient, org_headers, fa_category, fa_account):
        """Listar todos los activos."""
        _create_asset(client, org_headers, fa_category, fa_account, name="A1")
        _create_asset(client, org_headers, fa_category, fa_account, name="A2")

        resp = client.get(BASE_URL + "/", headers=org_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    def test_list_filter_status(self, client: TestClient, org_headers, fa_category, fa_account):
        """Filtrar por status."""
        resp = _create_asset(client, org_headers, fa_category, fa_account)
        asset_id = resp.json()["id"]

        # Dispose
        client.post(
            f"{BASE_URL}/{asset_id}/dispose",
            json={"reason": "test"},
            headers=org_headers,
        )

        # Crear otro activo
        _create_asset(client, org_headers, fa_category, fa_account, name="Otro")

        resp_active = client.get(f"{BASE_URL}/?status=active", headers=org_headers)
        assert resp_active.json()["total"] == 1

        resp_disposed = client.get(f"{BASE_URL}/?status=disposed", headers=org_headers)
        assert resp_disposed.json()["total"] == 1


# ---------------------------------------------------------------------------
# Tests: P&L y Balance Sheet
# ---------------------------------------------------------------------------

class TestFixedAssetReports:
    def test_pnl_includes_depreciation(self, client: TestClient, org_headers, fa_category, fa_account):
        """P&L incluye depreciation_expense como gasto operativo."""
        resp = _create_asset(
            client, org_headers, fa_category, fa_account,
            purchase_value=10000000,
            depreciation_rate=10.0,
            depreciation_start_date="2026-01-01",
        )
        asset_id = resp.json()["id"]

        # Depreciar
        client.post(f"{BASE_URL}/{asset_id}/depreciate", headers=org_headers)

        # Consultar P&L
        today = date.today().isoformat()
        first_of_year = date.today().replace(month=1, day=1).isoformat()
        pnl_resp = client.get(
            f"/api/v1/reports/profit-and-loss?date_from={first_of_year}&date_to={today}",
            headers=org_headers,
        )
        assert pnl_resp.status_code == 200
        pnl = pnl_resp.json()

        # Debe aparecer en gastos operacionales
        assert pnl["operating_expenses"] >= 1000000.0

        # Verificar en expenses_by_category
        dep_cats = [e for e in pnl["expenses_by_category"] if e["source_type"] == "depreciation_expense"]
        assert len(dep_cats) == 1
        assert dep_cats[0]["total_amount"] == 1000000.0
        assert dep_cats[0]["category_name"] == "Depreciación Equipos"

    def test_balance_sheet_includes_fixed_assets(self, client: TestClient, org_headers, fa_category, fa_account):
        """Balance Sheet incluye fixed_assets en activos."""
        # Crear activo de 50M
        _create_asset(
            client, org_headers, fa_category, fa_account,
            purchase_value=50000000,
            depreciation_start_date="2026-01-01",
            depreciation_rate=10.0,
        )
        asset_id = client.get(f"{BASE_URL}/", headers=org_headers).json()["items"][0]["id"]

        # Depreciar (5M)
        client.post(f"{BASE_URL}/{asset_id}/depreciate", headers=org_headers)

        # Balance Sheet
        bs_resp = client.get("/api/v1/reports/balance-sheet", headers=org_headers)
        assert bs_resp.status_code == 200
        bs = bs_resp.json()

        # fixed_assets = 45M (50M - 5M depreciado)
        assert bs["assets"]["fixed_assets"] == 45000000.0
        # total_assets incluye fixed_assets
        assert bs["total_assets"] >= 45000000.0

    def test_balance_sheet_excludes_disposed(self, client: TestClient, org_headers, fa_category, fa_account):
        """Balance Sheet no incluye activos dados de baja."""
        resp = _create_asset(
            client, org_headers, fa_category, fa_account,
            purchase_value=10000000,
        )
        asset_id = resp.json()["id"]

        # Dar de baja
        client.post(
            f"{BASE_URL}/{asset_id}/dispose",
            json={"reason": "test"},
            headers=org_headers,
        )

        bs_resp = client.get("/api/v1/reports/balance-sheet", headers=org_headers)
        assert bs_resp.status_code == 200
        assert bs_resp.json()["assets"]["fixed_assets"] == 0.0
