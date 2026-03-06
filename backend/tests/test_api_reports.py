"""
Tests para el modulo de reportes y dashboard.

~28 tests cubriendo: P&L, Cash Flow, Balance Sheet, Purchase Report,
Sales Report, Margin Analysis, Dashboard, Third Party Balances, Auth.
"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.double_entry import DoubleEntry
from app.models.expense_category import ExpenseCategory
from app.models.material import Material, MaterialCategory
from app.models.money_account import MoneyAccount
from app.models.money_movement import MoneyMovement
from app.models.organization import Organization
from app.models.purchase import Purchase, PurchaseLine
from app.models.sale import Sale, SaleLine, SaleCommission
from app.models.third_party import ThirdParty
from app.models.user import User
from app.models.warehouse import Warehouse


# ---------------------------------------------------------------------------
# Fixture principal: dataset completo para reportes
# ---------------------------------------------------------------------------

@pytest.fixture
def report_data(db_session: Session, test_organization: Organization, test_user: User):
    """
    Crea un dataset completo para testing de reportes.

    Retorna dict con todos los objetos y valores esperados.
    """
    org_id = test_organization.id
    now = datetime.now(tz=timezone.utc)
    today = now.date()

    # --- Categorias ---
    cat_metales = MaterialCategory(
        name="Metales", organization_id=org_id, is_active=True,
    )
    db_session.add(cat_metales)
    db_session.flush()

    cat_gasto_directo = ExpenseCategory(
        name="Fletes", organization_id=org_id,
        is_direct_expense=True, is_active=True,
    )
    cat_gasto_indirecto = ExpenseCategory(
        name="Arriendo", organization_id=org_id,
        is_direct_expense=False, is_active=True,
    )
    db_session.add_all([cat_gasto_directo, cat_gasto_indirecto])
    db_session.flush()

    # --- Materiales ---
    mat_cobre = Material(
        code="CU", name="Cobre", organization_id=org_id,
        category_id=cat_metales.id, default_unit="kg",
        current_stock=Decimal("500"), current_stock_liquidated=Decimal("500"),
        current_stock_transit=Decimal("0"), current_average_cost=Decimal("8000"),
        is_active=True,
    )
    mat_hierro = Material(
        code="FE", name="Hierro", organization_id=org_id,
        category_id=cat_metales.id, default_unit="kg",
        current_stock=Decimal("1000"), current_stock_liquidated=Decimal("1000"),
        current_stock_transit=Decimal("0"), current_average_cost=Decimal("1200"),
        is_active=True,
    )
    db_session.add_all([mat_cobre, mat_hierro])
    db_session.flush()

    # --- Bodega ---
    warehouse = Warehouse(
        name="Bodega Principal", organization_id=org_id, is_active=True,
    )
    db_session.add(warehouse)
    db_session.flush()

    # --- Cuentas de dinero ---
    cuenta_efectivo = MoneyAccount(
        name="Caja", account_type="cash", organization_id=org_id,
        current_balance=Decimal("10000000"), is_active=True,
    )
    cuenta_banco = MoneyAccount(
        name="Banco", account_type="bank", organization_id=org_id,
        current_balance=Decimal("5000000"), is_active=True,
    )
    db_session.add_all([cuenta_efectivo, cuenta_banco])
    db_session.flush()

    # --- Terceros ---
    proveedor1 = ThirdParty(
        name="Proveedor Alfa", organization_id=org_id,
        is_supplier=True, is_customer=False,
        current_balance=Decimal("-2000000"),  # les debemos 2M
        is_active=True,
    )
    proveedor2 = ThirdParty(
        name="Proveedor Beta", organization_id=org_id,
        is_supplier=True, is_customer=False,
        current_balance=Decimal("-500000"),
        is_active=True,
    )
    cliente1 = ThirdParty(
        name="Cliente Uno", organization_id=org_id,
        is_supplier=False, is_customer=True,
        current_balance=Decimal("3000000"),  # nos deben 3M
        is_active=True,
    )
    cliente2 = ThirdParty(
        name="Cliente Dos", organization_id=org_id,
        is_supplier=False, is_customer=True,
        current_balance=Decimal("1000000"),
        is_active=True,
    )
    inversor = ThirdParty(
        name="Inversor Capital", organization_id=org_id,
        is_supplier=False, is_customer=False, is_investor=True,
        current_balance=Decimal("-5000000"),  # les debemos 5M
        is_active=True,
    )
    comisionista = ThirdParty(
        name="Vendedor Externo", organization_id=org_id,
        is_supplier=False, is_customer=False,
        current_balance=Decimal("0"),
        is_active=True,
    )
    db_session.add_all([proveedor1, proveedor2, cliente1, cliente2, inversor, comisionista])
    db_session.flush()

    # --- Compras (3 liquidadas + 1 registrada) ---
    # Compra 1: Proveedor Alfa, 200kg Cobre @ $8000 = $1,600,000
    compra1 = Purchase(
        purchase_number=1, organization_id=org_id,
        supplier_id=proveedor1.id, date=now - timedelta(days=10),
        total_amount=Decimal("1600000"), status="liquidated",
        payment_account_id=cuenta_efectivo.id,
    )
    db_session.add(compra1)
    db_session.flush()
    linea_c1 = PurchaseLine(
        purchase_id=compra1.id, material_id=mat_cobre.id,
        warehouse_id=warehouse.id,
        quantity=Decimal("200"), unit_price=Decimal("8000"),
        total_price=Decimal("1600000"),
    )
    db_session.add(linea_c1)

    # Compra 2: Proveedor Beta, 500kg Hierro @ $1200 = $600,000
    compra2 = Purchase(
        purchase_number=2, organization_id=org_id,
        supplier_id=proveedor2.id, date=now - timedelta(days=5),
        total_amount=Decimal("600000"), status="liquidated",
        payment_account_id=cuenta_efectivo.id,
    )
    db_session.add(compra2)
    db_session.flush()
    linea_c2 = PurchaseLine(
        purchase_id=compra2.id, material_id=mat_hierro.id,
        warehouse_id=warehouse.id,
        quantity=Decimal("500"), unit_price=Decimal("1200"),
        total_price=Decimal("600000"),
    )
    db_session.add(linea_c2)

    # Compra 3: Proveedor Alfa, 100kg Cobre @ $8500 = $850,000
    compra3 = Purchase(
        purchase_number=3, organization_id=org_id,
        supplier_id=proveedor1.id, date=now - timedelta(days=3),
        total_amount=Decimal("850000"), status="liquidated",
        payment_account_id=cuenta_banco.id,
    )
    db_session.add(compra3)
    db_session.flush()
    linea_c3 = PurchaseLine(
        purchase_id=compra3.id, material_id=mat_cobre.id,
        warehouse_id=warehouse.id,
        quantity=Decimal("100"), unit_price=Decimal("8500"),
        total_price=Decimal("850000"),
    )
    db_session.add(linea_c3)

    # Compra 4: Registrada (sin pagar)
    compra4 = Purchase(
        purchase_number=4, organization_id=org_id,
        supplier_id=proveedor2.id, date=now - timedelta(days=1),
        total_amount=Decimal("300000"), status="registered",
    )
    db_session.add(compra4)
    db_session.flush()
    linea_c4 = PurchaseLine(
        purchase_id=compra4.id, material_id=mat_hierro.id,
        warehouse_id=warehouse.id,
        quantity=Decimal("250"), unit_price=Decimal("1200"),
        total_price=Decimal("300000"),
    )
    db_session.add(linea_c4)

    # --- Ventas (3 pagadas + 1 cancelada) ---
    # Venta 1: Cliente Uno, 100kg Cobre @ $10500, cost $8000 = profit $250,000
    venta1 = Sale(
        sale_number=1, organization_id=org_id,
        customer_id=cliente1.id, warehouse_id=warehouse.id,
        date=now - timedelta(days=8), total_amount=Decimal("1050000"),
        status="liquidated", payment_account_id=cuenta_efectivo.id,
    )
    db_session.add(venta1)
    db_session.flush()
    linea_v1 = SaleLine(
        sale_id=venta1.id, material_id=mat_cobre.id,
        quantity=Decimal("100"), unit_price=Decimal("10500"),
        total_price=Decimal("1050000"), unit_cost=Decimal("8000"),
    )
    db_session.add(linea_v1)

    # Venta 2: Cliente Dos, 300kg Hierro @ $1600, cost $1200 = profit $120,000
    venta2 = Sale(
        sale_number=2, organization_id=org_id,
        customer_id=cliente2.id, warehouse_id=warehouse.id,
        date=now - timedelta(days=6), total_amount=Decimal("480000"),
        status="liquidated", payment_account_id=cuenta_banco.id,
    )
    db_session.add(venta2)
    db_session.flush()
    linea_v2 = SaleLine(
        sale_id=venta2.id, material_id=mat_hierro.id,
        quantity=Decimal("300"), unit_price=Decimal("1600"),
        total_price=Decimal("480000"), unit_cost=Decimal("1200"),
    )
    db_session.add(linea_v2)

    # Venta 3: Cliente Uno, 50kg Cobre @ $11000, cost $8000 = profit $150,000
    venta3 = Sale(
        sale_number=3, organization_id=org_id,
        customer_id=cliente1.id, warehouse_id=warehouse.id,
        date=now - timedelta(days=2), total_amount=Decimal("550000"),
        status="liquidated", payment_account_id=cuenta_efectivo.id,
    )
    db_session.add(venta3)
    db_session.flush()
    linea_v3 = SaleLine(
        sale_id=venta3.id, material_id=mat_cobre.id,
        quantity=Decimal("50"), unit_price=Decimal("11000"),
        total_price=Decimal("550000"), unit_cost=Decimal("8000"),
    )
    db_session.add(linea_v3)

    # Venta cancelada (no debe contar en reportes)
    venta_cancelada = Sale(
        sale_number=4, organization_id=org_id,
        customer_id=cliente2.id, warehouse_id=warehouse.id,
        date=now - timedelta(days=4), total_amount=Decimal("999999"),
        status="cancelled",
    )
    db_session.add(venta_cancelada)
    db_session.flush()
    linea_vc = SaleLine(
        sale_id=venta_cancelada.id, material_id=mat_cobre.id,
        quantity=Decimal("999"), unit_price=Decimal("1000"),
        total_price=Decimal("999999"), unit_cost=Decimal("500"),
    )
    db_session.add(linea_vc)

    # --- Doble Partida ---
    # DE completada: 200kg Hierro, compra@1100, venta@1500 = profit $80,000
    # Crear purchase y sale vinculados
    de_purchase = Purchase(
        purchase_number=5, organization_id=org_id,
        supplier_id=proveedor1.id, date=now - timedelta(days=7),
        total_amount=Decimal("220000"), status="registered",
    )
    db_session.add(de_purchase)
    db_session.flush()

    de_sale = Sale(
        sale_number=5, organization_id=org_id,
        customer_id=cliente2.id, warehouse_id=None,
        date=now - timedelta(days=7), total_amount=Decimal("300000"),
        status="registered",
    )
    db_session.add(de_sale)
    db_session.flush()

    doble_partida = DoubleEntry(
        double_entry_number=1, organization_id=org_id,
        date=(now - timedelta(days=7)).date(),
        material_id=mat_hierro.id, quantity=Decimal("200"),
        supplier_id=proveedor1.id, customer_id=cliente2.id,
        purchase_unit_price=Decimal("1100"), sale_unit_price=Decimal("1500"),
        purchase_id=de_purchase.id, sale_id=de_sale.id,
        status="completed",
    )
    db_session.add(doble_partida)
    db_session.flush()

    # Vincular purchase y sale a la DE
    de_purchase.double_entry_id = doble_partida.id
    de_sale.double_entry_id = doble_partida.id

    # DE cancelada (no debe contar)
    de_purchase2 = Purchase(
        purchase_number=6, organization_id=org_id,
        supplier_id=proveedor2.id, date=now - timedelta(days=4),
        total_amount=Decimal("100000"), status="registered",
    )
    db_session.add(de_purchase2)
    db_session.flush()
    de_sale2 = Sale(
        sale_number=6, organization_id=org_id,
        customer_id=cliente1.id, warehouse_id=None,
        date=now - timedelta(days=4), total_amount=Decimal("150000"),
        status="registered",
    )
    db_session.add(de_sale2)
    db_session.flush()

    doble_partida_cancelada = DoubleEntry(
        double_entry_number=2, organization_id=org_id,
        date=(now - timedelta(days=4)).date(),
        material_id=mat_cobre.id, quantity=Decimal("50"),
        supplier_id=proveedor2.id, customer_id=cliente1.id,
        purchase_unit_price=Decimal("2000"), sale_unit_price=Decimal("3000"),
        purchase_id=de_purchase2.id, sale_id=de_sale2.id,
        status="cancelled",
    )
    db_session.add(doble_partida_cancelada)
    db_session.flush()
    de_purchase2.double_entry_id = doble_partida_cancelada.id
    de_sale2.double_entry_id = doble_partida_cancelada.id

    # --- Money Movements ---
    # Gasto directo: Flete $200,000
    mm_gasto = MoneyMovement(
        movement_number=1, organization_id=org_id,
        date=now - timedelta(days=5),
        movement_type="expense", amount=Decimal("200000"),
        account_id=cuenta_efectivo.id,
        expense_category_id=cat_gasto_directo.id,
        description="Flete compra", status="confirmed",
    )
    # Gasto indirecto: Arriendo $500,000
    mm_arriendo = MoneyMovement(
        movement_number=2, organization_id=org_id,
        date=now - timedelta(days=3),
        movement_type="expense", amount=Decimal("500000"),
        account_id=cuenta_banco.id,
        expense_category_id=cat_gasto_indirecto.id,
        description="Arriendo mensual", status="confirmed",
    )
    # Comision: $50,000
    mm_comision = MoneyMovement(
        movement_number=3, organization_id=org_id,
        date=now - timedelta(days=2),
        movement_type="commission_payment", amount=Decimal("50000"),
        account_id=cuenta_efectivo.id,
        third_party_id=comisionista.id,
        description="Comision venta", status="confirmed",
    )
    # Service income: $150,000
    mm_servicio = MoneyMovement(
        movement_number=4, organization_id=org_id,
        date=now - timedelta(days=1),
        movement_type="service_income", amount=Decimal("150000"),
        account_id=cuenta_efectivo.id,
        description="Servicio pesaje", status="confirmed",
    )
    # Cobro a cliente manual: $100,000
    mm_cobro = MoneyMovement(
        movement_number=5, organization_id=org_id,
        date=now - timedelta(days=1),
        movement_type="collection_from_client", amount=Decimal("100000"),
        account_id=cuenta_efectivo.id,
        third_party_id=cliente1.id,
        description="Abono cliente", status="confirmed",
    )
    db_session.add_all([mm_gasto, mm_arriendo, mm_comision, mm_servicio, mm_cobro])

    db_session.commit()

    # Valores esperados
    # Ventas normales (excl DE, excl canceladas): v1+v2+v3
    expected_sales_revenue = Decimal("1050000") + Decimal("480000") + Decimal("550000")  # 2,080,000
    # COGS: sum(unit_cost * qty) de ventas normales
    expected_cogs = (
        Decimal("8000") * Decimal("100")   # v1: 800,000
        + Decimal("1200") * Decimal("300")  # v2: 360,000
        + Decimal("8000") * Decimal("50")   # v3: 400,000
    )  # = 1,560,000
    # DE profit: (1500-1100)*200 = 80,000
    expected_de_profit = Decimal("80000")
    # Service income: 150,000
    expected_service_income = Decimal("150000")
    # Operating expenses: 200,000 + 500,000 = 700,000
    expected_expenses = Decimal("700000")
    # Commissions: 50,000
    expected_commissions = Decimal("50000")

    return {
        "org_id": org_id,
        "now": now,
        "today": today,
        "date_from": (now - timedelta(days=15)).date(),
        "date_to": (now + timedelta(days=1)).date(),
        # Objects
        "mat_cobre": mat_cobre,
        "mat_hierro": mat_hierro,
        "proveedor1": proveedor1,
        "proveedor2": proveedor2,
        "cliente1": cliente1,
        "cliente2": cliente2,
        "inversor": inversor,
        "cuenta_efectivo": cuenta_efectivo,
        "cuenta_banco": cuenta_banco,
        "warehouse": warehouse,
        # Purchases (non-cancelled)
        "compras_pagadas": [compra1, compra2, compra3],
        "compra_registrada": compra4,
        # Sales (non-cancelled)
        "ventas_pagadas": [venta1, venta2, venta3],
        # Expected values
        "expected_sales_revenue": expected_sales_revenue,
        "expected_cogs": expected_cogs,
        "expected_de_profit": expected_de_profit,
        "expected_service_income": expected_service_income,
        "expected_expenses": expected_expenses,
        "expected_commissions": expected_commissions,
        "expected_gross_profit_sales": expected_sales_revenue - expected_cogs,
        "expected_total_gross_profit": (
            expected_sales_revenue - expected_cogs + expected_de_profit + expected_service_income
        ),
        "expected_net_profit": (
            expected_sales_revenue - expected_cogs + expected_de_profit
            + expected_service_income - expected_expenses - expected_commissions
        ),
    }


# ---------------------------------------------------------------------------
# P&L Tests
# ---------------------------------------------------------------------------

class TestProfitAndLoss:

    def test_pl_basic(self, client: TestClient, org_headers: dict, report_data: dict):
        """P&L calcula revenue, COGS y profit correctamente."""
        response = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": str(report_data["date_from"]), "date_to": str(report_data["date_to"])},
            headers=org_headers,
        )
        assert response.status_code == 200
        data = response.json()

        assert data["sales_revenue"] == pytest.approx(float(report_data["expected_sales_revenue"]), abs=1)
        assert data["cost_of_goods_sold"] == pytest.approx(float(report_data["expected_cogs"]), abs=1)
        assert data["gross_profit_sales"] == pytest.approx(
            float(report_data["expected_gross_profit_sales"]), abs=1
        )

    def test_pl_double_entry_separate(self, client: TestClient, org_headers: dict, report_data: dict):
        """DE profit aparece como linea separada, no en sales_revenue."""
        response = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": str(report_data["date_from"]), "date_to": str(report_data["date_to"])},
            headers=org_headers,
        )
        data = response.json()

        assert data["double_entry_profit"] == pytest.approx(float(report_data["expected_de_profit"]), abs=1)
        assert data["double_entry_count"] == 1
        # sales_revenue no incluye DE
        assert data["sales_revenue"] == pytest.approx(float(report_data["expected_sales_revenue"]), abs=1)

    def test_pl_expenses_by_category(self, client: TestClient, org_headers: dict, report_data: dict):
        """Desglose de gastos por categoria correcto."""
        response = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": str(report_data["date_from"]), "date_to": str(report_data["date_to"])},
            headers=org_headers,
        )
        data = response.json()

        assert data["operating_expenses"] == pytest.approx(float(report_data["expected_expenses"]), abs=1)
        assert data["commissions_paid"] == pytest.approx(float(report_data["expected_commissions"]), abs=1)
        assert len(data["expenses_by_category"]) == 2

        cat_names = {c["category_name"] for c in data["expenses_by_category"]}
        assert "Fletes" in cat_names
        assert "Arriendo" in cat_names

    def test_pl_excludes_cancelled(self, client: TestClient, org_headers: dict, report_data: dict):
        """Ventas canceladas no aparecen en revenue."""
        response = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": str(report_data["date_from"]), "date_to": str(report_data["date_to"])},
            headers=org_headers,
        )
        data = response.json()

        # sales_count should be 3 (normal paid, excl DE and cancelled)
        assert data["sales_count"] == 3

    def test_pl_empty_period(self, client: TestClient, org_headers: dict, report_data: dict):
        """Periodo sin datos retorna zeros."""
        response = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": "2020-01-01", "date_to": "2020-01-31"},
            headers=org_headers,
        )
        assert response.status_code == 200
        data = response.json()

        assert data["sales_revenue"] == 0
        assert data["cost_of_goods_sold"] == 0
        assert data["double_entry_profit"] == 0
        assert data["net_profit"] == 0


# ---------------------------------------------------------------------------
# Cash Flow Tests
# ---------------------------------------------------------------------------

class TestCashFlow:

    def test_cf_inflows_outflows(self, client: TestClient, org_headers: dict, report_data: dict):
        """Buckets de inflows y outflows correctos."""
        response = client.get(
            "/api/v1/reports/cash-flow",
            params={"date_from": str(report_data["date_from"]), "date_to": str(report_data["date_to"])},
            headers=org_headers,
        )
        assert response.status_code == 200
        data = response.json()

        # Inflows: sale_collections (ventas pagadas) + MM inflows
        assert data["inflows"]["sale_collections"] > 0
        assert data["inflows"]["service_income"] == pytest.approx(150000, abs=1)
        assert data["inflows"]["customer_collections"] == pytest.approx(100000, abs=1)

        # Outflows: purchase_payments (compras pagadas) + MM outflows
        assert data["outflows"]["purchase_payments"] > 0
        assert data["outflows"]["expenses"] == pytest.approx(700000, abs=1)
        assert data["outflows"]["commission_payments"] == pytest.approx(50000, abs=1)

    def test_cf_opening_closing_balance(self, client: TestClient, org_headers: dict, report_data: dict):
        """opening + net_flow = closing."""
        response = client.get(
            "/api/v1/reports/cash-flow",
            params={"date_from": str(report_data["date_from"]), "date_to": str(report_data["date_to"])},
            headers=org_headers,
        )
        data = response.json()

        assert data["closing_balance"] == pytest.approx(
            data["opening_balance"] + data["net_flow"], abs=1
        )

    def test_cf_includes_liquidation_flows(self, client: TestClient, org_headers: dict, report_data: dict):
        """Cash flow incluye pagos de compras y cobros de ventas."""
        response = client.get(
            "/api/v1/reports/cash-flow",
            params={"date_from": str(report_data["date_from"]), "date_to": str(report_data["date_to"])},
            headers=org_headers,
        )
        data = response.json()

        # 3 compras pagadas: 1,600,000 + 600,000 + 850,000 = 3,050,000
        assert data["outflows"]["purchase_payments"] == pytest.approx(3050000, abs=1)
        # 3 ventas pagadas: 1,050,000 + 480,000 + 550,000 = 2,080,000
        assert data["inflows"]["sale_collections"] == pytest.approx(2080000, abs=1)

    def test_cf_empty_period(self, client: TestClient, org_headers: dict, report_data: dict):
        """Periodo vacio retorna zeros con opening balance correcto."""
        response = client.get(
            "/api/v1/reports/cash-flow",
            params={"date_from": "2020-01-01", "date_to": "2020-01-31"},
            headers=org_headers,
        )
        assert response.status_code == 200
        data = response.json()

        assert data["net_flow"] == 0
        assert data["total_inflows"] == 0
        assert data["total_outflows"] == 0


# ---------------------------------------------------------------------------
# Balance Sheet Tests
# ---------------------------------------------------------------------------

class TestBalanceSheet:

    def test_bs_assets(self, client: TestClient, org_headers: dict, report_data: dict):
        """Activos: efectivo + CxC + inventario."""
        response = client.get("/api/v1/reports/balance-sheet", headers=org_headers)
        assert response.status_code == 200
        data = response.json()

        # Cash: 10M + 5M = 15M
        assert data["assets"]["cash_and_bank"] == pytest.approx(15000000, abs=1)
        # AR: cliente1 (3M) + cliente2 (1M) = 4M
        assert data["assets"]["accounts_receivable"] == pytest.approx(4000000, abs=1)
        # Inventory: cobre 500*8000 + hierro 1000*1200 = 4M + 1.2M = 5.2M
        assert data["assets"]["inventory"] == pytest.approx(5200000, abs=1)

    def test_bs_liabilities(self, client: TestClient, org_headers: dict, report_data: dict):
        """Pasivos: CxP + deuda inversores."""
        response = client.get("/api/v1/reports/balance-sheet", headers=org_headers)
        data = response.json()

        # AP: proveedor1 (2M) + proveedor2 (500K) = 2.5M
        assert data["liabilities"]["accounts_payable"] == pytest.approx(2500000, abs=1)
        # Investor debt: 5M
        assert data["liabilities"]["investor_debt"] == pytest.approx(5000000, abs=1)

    def test_bs_equation(self, client: TestClient, org_headers: dict, report_data: dict):
        """Ecuacion patrimonial: assets = liabilities + equity."""
        response = client.get("/api/v1/reports/balance-sheet", headers=org_headers)
        data = response.json()

        assert data["total_assets"] == pytest.approx(
            data["total_liabilities"] + data["equity"], abs=1
        )


# ---------------------------------------------------------------------------
# Purchase Report Tests
# ---------------------------------------------------------------------------

class TestPurchaseReport:

    def test_purchases_totals(self, client: TestClient, org_headers: dict, report_data: dict):
        """Totales de compras correctos."""
        response = client.get(
            "/api/v1/reports/purchases",
            params={"date_from": str(report_data["date_from"]), "date_to": str(report_data["date_to"])},
            headers=org_headers,
        )
        assert response.status_code == 200
        data = response.json()

        # Solo compras liquidadas (no registradas ni canceladas)
        # c1(liquidated) + c2(liquidated) + c3(liquidated) = 3 normales + DE purchases
        assert data["purchase_count"] >= 3
        assert data["total_amount"] > 0

    def test_purchases_by_supplier(self, client: TestClient, org_headers: dict, report_data: dict):
        """Desglose por proveedor."""
        response = client.get(
            "/api/v1/reports/purchases",
            params={"date_from": str(report_data["date_from"]), "date_to": str(report_data["date_to"])},
            headers=org_headers,
        )
        data = response.json()

        supplier_names = {s["supplier_name"] for s in data["by_supplier"]}
        assert "Proveedor Alfa" in supplier_names
        assert "Proveedor Beta" in supplier_names

    def test_purchases_filter_supplier(self, client: TestClient, org_headers: dict, report_data: dict):
        """Filtro por supplier_id funciona."""
        response = client.get(
            "/api/v1/reports/purchases",
            params={
                "date_from": str(report_data["date_from"]),
                "date_to": str(report_data["date_to"]),
                "supplier_id": str(report_data["proveedor1"].id),
            },
            headers=org_headers,
        )
        data = response.json()

        # Solo compras de proveedor1
        for s in data["by_supplier"]:
            assert s["supplier_name"] == "Proveedor Alfa"


# ---------------------------------------------------------------------------
# Sales Report Tests
# ---------------------------------------------------------------------------

class TestSalesReport:

    def test_sales_totals_with_profit(self, client: TestClient, org_headers: dict, report_data: dict):
        """Revenue, cost, profit y margin correctos."""
        response = client.get(
            "/api/v1/reports/sales",
            params={"date_from": str(report_data["date_from"]), "date_to": str(report_data["date_to"])},
            headers=org_headers,
        )
        assert response.status_code == 200
        data = response.json()

        assert data["total_revenue"] > 0
        assert data["total_cost"] > 0
        assert data["total_profit"] > 0
        assert data["overall_margin"] > 0
        # Profit = revenue - cost
        assert data["total_profit"] == pytest.approx(
            data["total_revenue"] - data["total_cost"], abs=1
        )

    def test_sales_by_customer(self, client: TestClient, org_headers: dict, report_data: dict):
        """Desglose por cliente."""
        response = client.get(
            "/api/v1/reports/sales",
            params={"date_from": str(report_data["date_from"]), "date_to": str(report_data["date_to"])},
            headers=org_headers,
        )
        data = response.json()

        customer_names = {c["customer_name"] for c in data["by_customer"]}
        assert "Cliente Uno" in customer_names
        assert "Cliente Dos" in customer_names

    def test_sales_by_material(self, client: TestClient, org_headers: dict, report_data: dict):
        """Desglose por material con profit."""
        response = client.get(
            "/api/v1/reports/sales",
            params={"date_from": str(report_data["date_from"]), "date_to": str(report_data["date_to"])},
            headers=org_headers,
        )
        data = response.json()

        material_names = {m["material_name"] for m in data["by_material"]}
        assert "Cobre" in material_names or "Hierro" in material_names

        for m in data["by_material"]:
            assert m["total_profit"] >= 0
            assert m["margin_percentage"] >= 0


# ---------------------------------------------------------------------------
# Margin Analysis Tests
# ---------------------------------------------------------------------------

class TestMarginAnalysis:

    def test_margins_per_material(self, client: TestClient, org_headers: dict, report_data: dict):
        """Compra/venta/profit por material."""
        response = client.get(
            "/api/v1/reports/margins",
            params={"date_from": str(report_data["date_from"]), "date_to": str(report_data["date_to"])},
            headers=org_headers,
        )
        assert response.status_code == 200
        data = response.json()

        assert len(data["materials"]) >= 2
        assert data["overall_margin"] > 0

        for m in data["materials"]:
            assert "material_code" in m
            assert "margin_percentage" in m

    def test_margins_de_contribution(self, client: TestClient, org_headers: dict, report_data: dict):
        """Contribucion DE separada por material."""
        response = client.get(
            "/api/v1/reports/margins",
            params={"date_from": str(report_data["date_from"]), "date_to": str(report_data["date_to"])},
            headers=org_headers,
        )
        data = response.json()

        # Hierro tiene DE contribution
        hierro = next((m for m in data["materials"] if m["material_code"] == "FE"), None)
        assert hierro is not None
        assert hierro["double_entry_qty"] == pytest.approx(200, abs=1)
        assert hierro["double_entry_profit"] == pytest.approx(80000, abs=1)

    def test_margins_zero_sales(self, client: TestClient, org_headers: dict, report_data: dict):
        """Material sin ventas tiene 0% margin."""
        response = client.get(
            "/api/v1/reports/margins",
            params={"date_from": "2020-01-01", "date_to": "2020-01-31"},
            headers=org_headers,
        )
        data = response.json()

        assert data["overall_margin"] == 0
        assert len(data["materials"]) == 0


# ---------------------------------------------------------------------------
# Dashboard Tests
# ---------------------------------------------------------------------------

class TestDashboard:

    def test_dashboard_metrics(self, client: TestClient, org_headers: dict, report_data: dict):
        """6 metric cards con valores."""
        response = client.get(
            "/api/v1/reports/dashboard",
            params={"date_from": str(report_data["date_from"]), "date_to": str(report_data["date_to"])},
            headers=org_headers,
        )
        assert response.status_code == 200
        data = response.json()

        metrics = data["metrics"]
        assert metrics["total_sales"]["current_value"] > 0
        assert metrics["total_purchases"]["current_value"] > 0
        assert metrics["gross_profit"]["current_value"] > 0
        assert metrics["cash_balance"]["current_value"] == pytest.approx(15000000, abs=1)
        assert metrics["pending_receivables"]["current_value"] == pytest.approx(4000000, abs=1)
        assert metrics["pending_payables"]["current_value"] == pytest.approx(2500000, abs=1)

    def test_dashboard_period_comparison(self, client: TestClient, org_headers: dict, report_data: dict):
        """change_percentage calculado correctamente."""
        response = client.get(
            "/api/v1/reports/dashboard",
            params={"date_from": str(report_data["date_from"]), "date_to": str(report_data["date_to"])},
            headers=org_headers,
        )
        data = response.json()

        metrics = data["metrics"]
        # Periodo anterior no tiene datos -> previous_value=0 -> change_percentage=None
        assert metrics["total_sales"]["previous_value"] == 0
        assert metrics["total_sales"]["change_percentage"] is None
        # Cash balance es point-in-time -> change_percentage=None
        assert metrics["cash_balance"]["change_percentage"] is None

    def test_dashboard_top_lists(self, client: TestClient, org_headers: dict, report_data: dict):
        """Top materials/suppliers/customers poblados."""
        response = client.get(
            "/api/v1/reports/dashboard",
            params={"date_from": str(report_data["date_from"]), "date_to": str(report_data["date_to"])},
            headers=org_headers,
        )
        data = response.json()

        assert len(data["top_materials_by_profit"]) > 0
        assert len(data["top_suppliers_by_volume"]) > 0
        assert len(data["top_customers_by_revenue"]) > 0

    def test_dashboard_alerts(self, client: TestClient, org_headers: dict, report_data: dict):
        """Alertas generadas correctamente."""
        response = client.get(
            "/api/v1/reports/dashboard",
            params={"date_from": str(report_data["date_from"]), "date_to": str(report_data["date_to"])},
            headers=org_headers,
        )
        data = response.json()

        alert_types = {a["alert_type"] for a in data["alerts"]}
        # Hay 1 compra registrada (pending)
        assert "pending_purchases" in alert_types


# ---------------------------------------------------------------------------
# Third Party Balances Tests
# ---------------------------------------------------------------------------

class TestThirdPartyBalances:

    def test_tp_balances_suppliers_customers(self, client: TestClient, org_headers: dict, report_data: dict):
        """Proveedores y clientes separados correctamente."""
        response = client.get("/api/v1/reports/third-party-balances", headers=org_headers)
        assert response.status_code == 200
        data = response.json()

        # Payable: 2M + 500K = 2.5M
        assert data["total_payable"] == pytest.approx(2500000, abs=1)
        # Receivable: 3M + 1M = 4M
        assert data["total_receivable"] == pytest.approx(4000000, abs=1)
        assert data["net_position"] == pytest.approx(1500000, abs=1)

        assert len(data["suppliers"]) == 2
        assert len(data["customers"]) == 2

    def test_tp_balances_filter_type(self, client: TestClient, org_headers: dict, report_data: dict):
        """Filtro por tipo funciona."""
        # Solo proveedores
        response = client.get(
            "/api/v1/reports/third-party-balances",
            params={"type": "suppliers"},
            headers=org_headers,
        )
        data = response.json()

        assert len(data["suppliers"]) == 2
        assert len(data["customers"]) == 0

        # Solo clientes
        response = client.get(
            "/api/v1/reports/third-party-balances",
            params={"type": "customers"},
            headers=org_headers,
        )
        data = response.json()

        assert len(data["suppliers"]) == 0
        assert len(data["customers"]) == 2


# ---------------------------------------------------------------------------
# Auth Test
# ---------------------------------------------------------------------------

class TestReportsAuth:

    def test_reports_require_auth(self, client: TestClient):
        """401 sin token de autenticacion."""
        response = client.get(
            "/api/v1/reports/dashboard",
            params={"date_from": "2025-01-01", "date_to": "2025-12-31"},
        )
        assert response.status_code in (401, 403)
