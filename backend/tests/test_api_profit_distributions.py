"""Tests para repartición de utilidades a socios."""
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.material import Material, MaterialCategory
from app.models.money_account import MoneyAccount
from app.models.sale import Sale, SaleLine
from app.models.third_party import ThirdParty
from app.models.warehouse import Warehouse


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_category(db_session: Session, test_organization) -> MaterialCategory:
    cat = MaterialCategory(
        name="Metales", organization_id=test_organization.id
    )
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


@pytest.fixture
def test_material(db_session: Session, test_organization, test_category) -> Material:
    mat = Material(
        name="Cobre",
        code="CU",
        category_id=test_category.id,
        organization_id=test_organization.id,
        current_stock=Decimal("1000"),
        current_stock_liquidated=Decimal("1000"),
        current_average_cost=Decimal("5000"),
    )
    db_session.add(mat)
    db_session.commit()
    db_session.refresh(mat)
    return mat


@pytest.fixture
def test_warehouse(db_session: Session, test_organization) -> Warehouse:
    wh = Warehouse(
        name="Bodega Principal", organization_id=test_organization.id
    )
    db_session.add(wh)
    db_session.commit()
    db_session.refresh(wh)
    return wh


@pytest.fixture
def test_customer(db_session: Session, test_organization) -> ThirdParty:
    tp = ThirdParty(
        name="Cliente Test",
        is_customer=True,
        organization_id=test_organization.id,
    )
    db_session.add(tp)
    db_session.commit()
    db_session.refresh(tp)
    return tp


@pytest.fixture
def test_account(db_session: Session, test_organization) -> MoneyAccount:
    acc = MoneyAccount(
        name="Caja Principal",
        account_type="cash",
        current_balance=Decimal("100000000"),
        organization_id=test_organization.id,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


@pytest.fixture
def partner_a(db_session: Session, test_organization) -> ThirdParty:
    tp = ThirdParty(
        name="Socio A",
        is_investor=True,
        investor_type="socio",
        organization_id=test_organization.id,
    )
    db_session.add(tp)
    db_session.commit()
    db_session.refresh(tp)
    return tp


@pytest.fixture
def partner_b(db_session: Session, test_organization) -> ThirdParty:
    tp = ThirdParty(
        name="Socio B",
        is_investor=True,
        investor_type="socio",
        organization_id=test_organization.id,
    )
    db_session.add(tp)
    db_session.commit()
    db_session.refresh(tp)
    return tp


@pytest.fixture
def non_partner(db_session: Session, test_organization) -> ThirdParty:
    """Inversionista tipo obligacion financiera (NO socio)."""
    tp = ThirdParty(
        name="Banco XYZ",
        is_investor=True,
        investor_type="obligacion_financiera",
        organization_id=test_organization.id,
    )
    db_session.add(tp)
    db_session.commit()
    db_session.refresh(tp)
    return tp


@pytest.fixture
def liquidated_sale(
    db_session: Session, test_organization, test_customer,
    test_material, test_warehouse, test_account,
) -> Sale:
    """Venta liquidada para generar utilidad acumulada."""
    sale = Sale(
        sale_number=1,
        customer_id=test_customer.id,
        organization_id=test_organization.id,
        status="liquidated",
        total_amount=Decimal("50000000"),  # 50M ingresos
        date="2026-03-01T12:00:00+00:00",
    )
    db_session.add(sale)
    db_session.flush()

    line = SaleLine(
        sale_id=sale.id,
        material_id=test_material.id,
        quantity=Decimal("100"),
        unit_price=Decimal("500000"),
        total_price=Decimal("50000000"),
        unit_cost=Decimal("5000"),  # COGS = 100 * 5000 = 500,000
    )
    db_session.add(line)
    db_session.commit()
    db_session.refresh(sale)
    return sale


# ---------------------------------------------------------------------------
# Tests: GET /profit-distributions/available
# ---------------------------------------------------------------------------

class TestAvailableProfit:
    def test_available_no_sales(self, client: TestClient, org_headers, partner_a):
        """Sin ventas, utilidad acumulada = 0."""
        resp = client.get("/api/v1/profit-distributions/available", headers=org_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["accumulated_profit"] == 0
        assert data["distributed_profit"] == 0
        assert data["available_profit"] == 0

    def test_available_with_sales(self, client: TestClient, org_headers, partner_a, liquidated_sale):
        """Con venta liquidada, utilidad = revenue - COGS."""
        resp = client.get("/api/v1/profit-distributions/available", headers=org_headers)
        assert resp.status_code == 200
        data = resp.json()
        # Revenue = 50M, COGS = 500K, utilidad = 49.5M
        assert data["accumulated_profit"] == 49500000.0
        assert data["distributed_profit"] == 0
        assert data["available_profit"] == 49500000.0


# ---------------------------------------------------------------------------
# Tests: GET /profit-distributions/partners
# ---------------------------------------------------------------------------

class TestPartners:
    def test_only_socios(self, client: TestClient, org_headers, partner_a, partner_b, non_partner):
        """Solo retorna terceros con investor_type='socio'."""
        resp = client.get("/api/v1/profit-distributions/partners", headers=org_headers)
        assert resp.status_code == 200
        data = resp.json()
        names = {p["name"] for p in data}
        assert "Socio A" in names
        assert "Socio B" in names
        assert "Banco XYZ" not in names

    def test_empty_when_no_socios(self, client: TestClient, org_headers, non_partner):
        """Sin socios, lista vacía."""
        resp = client.get("/api/v1/profit-distributions/partners", headers=org_headers)
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Tests: POST /profit-distributions
# ---------------------------------------------------------------------------

class TestCreateDistribution:
    def test_create_happy_path(
        self, client: TestClient, org_headers, db_session,
        partner_a, partner_b, liquidated_sale,
    ):
        """Caso feliz: crea distribución, actualiza saldos de socios."""
        payload = {
            "date": "2026-03-15",
            "lines": [
                {"third_party_id": str(partner_a.id), "amount": 10000000},
                {"third_party_id": str(partner_b.id), "amount": 5000000},
            ],
            "notes": "Primera repartición",
        }
        resp = client.post("/api/v1/profit-distributions/", json=payload, headers=org_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["total_amount"] == 15000000
        assert len(data["lines"]) == 2
        assert data["notes"] == "Primera repartición"

        # Verificar saldos actualizados
        db_session.expire_all()
        db_session.refresh(partner_a)
        db_session.refresh(partner_b)
        assert float(partner_a.current_balance) == -10000000
        assert float(partner_b.current_balance) == -5000000

    def test_zero_lines_filtered(
        self, client: TestClient, org_headers, partner_a, partner_b, liquidated_sale,
    ):
        """Líneas con amount=0 se filtran; solo se crean las positivas."""
        payload = {
            "date": "2026-03-15",
            "lines": [
                {"third_party_id": str(partner_a.id), "amount": 5000000},
                {"third_party_id": str(partner_b.id), "amount": 0},
            ],
        }
        resp = client.post("/api/v1/profit-distributions/", json=payload, headers=org_headers)
        assert resp.status_code == 201
        assert len(resp.json()["lines"]) == 1

    def test_all_zero_rejected(
        self, client: TestClient, org_headers, partner_a, partner_b,
    ):
        """Todas las líneas con amount=0 → error de validación."""
        payload = {
            "date": "2026-03-15",
            "lines": [
                {"third_party_id": str(partner_a.id), "amount": 0},
                {"third_party_id": str(partner_b.id), "amount": 0},
            ],
        }
        resp = client.post("/api/v1/profit-distributions/", json=payload, headers=org_headers)
        assert resp.status_code == 422

    def test_non_socio_rejected(
        self, client: TestClient, org_headers, non_partner,
    ):
        """Tercero que no es socio → 400."""
        payload = {
            "date": "2026-03-15",
            "lines": [
                {"third_party_id": str(non_partner.id), "amount": 1000000},
            ],
        }
        resp = client.post("/api/v1/profit-distributions/", json=payload, headers=org_headers)
        assert resp.status_code == 400
        assert "no es socio" in resp.json()["detail"]

    def test_nonexistent_third_party(self, client: TestClient, org_headers):
        """Tercero inexistente → 404."""
        payload = {
            "date": "2026-03-15",
            "lines": [{"third_party_id": str(uuid4()), "amount": 1000000}],
        }
        resp = client.post("/api/v1/profit-distributions/", json=payload, headers=org_headers)
        assert resp.status_code == 404

    def test_exceeds_available_allowed(
        self, client: TestClient, org_headers, partner_a, liquidated_sale,
    ):
        """Repartir más de lo disponible está permitido."""
        payload = {
            "date": "2026-03-15",
            "lines": [
                {"third_party_id": str(partner_a.id), "amount": 999999999},
            ],
        }
        resp = client.post("/api/v1/profit-distributions/", json=payload, headers=org_headers)
        assert resp.status_code == 201

    def test_money_movements_created(
        self, client: TestClient, org_headers, db_session,
        partner_a, liquidated_sale,
    ):
        """Se crean MoneyMovements tipo profit_distribution."""
        payload = {
            "date": "2026-03-15",
            "lines": [{"third_party_id": str(partner_a.id), "amount": 5000000}],
        }
        resp = client.post("/api/v1/profit-distributions/", json=payload, headers=org_headers)
        assert resp.status_code == 201

        line = resp.json()["lines"][0]
        assert line["money_movement_id"] is not None


# ---------------------------------------------------------------------------
# Tests: GET /profit-distributions
# ---------------------------------------------------------------------------

class TestListDistributions:
    def test_list_empty(self, client: TestClient, org_headers):
        """Sin distribuciones, retorna lista vacía."""
        resp = client.get("/api/v1/profit-distributions/", headers=org_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_with_history(
        self, client: TestClient, org_headers, partner_a, liquidated_sale,
    ):
        """Después de crear distribución, aparece en historial."""
        # Crear distribución
        payload = {
            "date": "2026-03-15",
            "lines": [{"third_party_id": str(partner_a.id), "amount": 5000000}],
        }
        client.post("/api/v1/profit-distributions/", json=payload, headers=org_headers)

        resp = client.get("/api/v1/profit-distributions/", headers=org_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["total_amount"] == 5000000


# ---------------------------------------------------------------------------
# Tests: Balance Sheet con patrimonio desglosado
# ---------------------------------------------------------------------------

class TestBalanceSheetEquityBreakdown:
    def test_balance_sheet_has_breakdown(
        self, client: TestClient, org_headers, partner_a, liquidated_sale,
    ):
        """Balance sheet retorna accumulated_profit y distributed_profit."""
        resp = client.get("/api/v1/reports/balance-sheet", headers=org_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "accumulated_profit" in data
        assert "distributed_profit" in data
        assert data["accumulated_profit"] == 49500000.0
        assert data["distributed_profit"] == 0

    def test_balance_sheet_after_distribution(
        self, client: TestClient, org_headers, partner_a, liquidated_sale,
    ):
        """Después de distribuir, distributed_profit se actualiza."""
        payload = {
            "date": "2026-03-15",
            "lines": [{"third_party_id": str(partner_a.id), "amount": 10000000}],
        }
        client.post("/api/v1/profit-distributions/", json=payload, headers=org_headers)

        resp = client.get("/api/v1/reports/balance-sheet", headers=org_headers)
        data = resp.json()
        assert data["accumulated_profit"] == 49500000.0
        assert data["distributed_profit"] == 10000000.0

    def test_balance_still_squares(
        self, client: TestClient, org_headers, partner_a, liquidated_sale,
    ):
        """Después de distribuir, A - P - Patrimonio = 0."""
        # Distribuir
        payload = {
            "date": "2026-03-15",
            "lines": [{"third_party_id": str(partner_a.id), "amount": 20000000}],
        }
        client.post("/api/v1/profit-distributions/", json=payload, headers=org_headers)

        # Verificar balance detallado
        resp = client.get("/api/v1/reports/balance-detailed", headers=org_headers)
        data = resp.json()
        assert data["verification"]["is_balanced"] is True


# ---------------------------------------------------------------------------
# Tests: Cash Flow NO incluye profit_distribution
# ---------------------------------------------------------------------------

class TestCashFlowExclusion:
    def test_cash_flow_excludes_distribution(
        self, client: TestClient, org_headers, partner_a,
    ):
        """profit_distribution NO aparece en cash flow (sin otras operaciones)."""
        # Distribuir (sin venta, para aislar efecto)
        payload = {
            "date": "2026-03-15",
            "lines": [{"third_party_id": str(partner_a.id), "amount": 10000000}],
        }
        client.post("/api/v1/profit-distributions/", json=payload, headers=org_headers)

        resp = client.get(
            "/api/v1/reports/cash-flow?date_from=2026-03-01&date_to=2026-03-31",
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # Net flow = 0 porque profit_distribution no afecta cuentas
        assert data["net_flow"] == 0


# ---------------------------------------------------------------------------
# Tests: Estado de cuenta del socio
# ---------------------------------------------------------------------------

class TestAccountStatement:
    def test_distribution_in_statement(
        self, client: TestClient, org_headers, partner_a, liquidated_sale,
    ):
        """MoneyMovement profit_distribution aparece en estado de cuenta."""
        payload = {
            "date": "2026-03-15",
            "lines": [{"third_party_id": str(partner_a.id), "amount": 10000000}],
        }
        client.post("/api/v1/profit-distributions/", json=payload, headers=org_headers)

        resp = client.get(
            f"/api/v1/money-movements/third-party/{partner_a.id}"
            "?date_from=2026-03-01&date_to=2026-03-31",
            headers=org_headers,
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        # Debe haber al menos un movimiento de tipo profit_distribution
        profit_items = [i for i in items if i.get("event_type") == "profit_distribution"]
        assert len(profit_items) == 1
        assert profit_items[0]["amount"] == 10000000
