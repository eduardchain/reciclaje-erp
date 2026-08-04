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

from app.models.double_entry import DoubleEntry, DoubleEntryLine
from app.models.expense_category import ExpenseCategory
from app.models.material import Material, MaterialCategory
from app.models.money_account import MoneyAccount
from app.models.money_movement import MoneyMovement
from app.models.organization import Organization
from app.models.purchase import Purchase, PurchaseLine
from app.models.sale import Sale, SaleLine, SaleCommission
from app.models.third_party import ThirdParty
from app.models.third_party_category import ThirdPartyCategory, ThirdPartyCategoryAssignment
from app.models.user import User
from app.models.warehouse import Warehouse
from app.models.business_unit import BusinessUnit
from app.models.fixed_asset import FixedAsset, AssetDepreciation


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
        current_balance=Decimal("-2000000"),  # les debemos 2M
        is_active=True,
    )
    proveedor2 = ThirdParty(
        name="Proveedor Beta", organization_id=org_id,
        current_balance=Decimal("-500000"),
        is_active=True,
    )
    cliente1 = ThirdParty(
        name="Cliente Uno", organization_id=org_id,
        current_balance=Decimal("3000000"),  # nos deben 3M
        is_active=True,
    )
    cliente2 = ThirdParty(
        name="Cliente Dos", organization_id=org_id,
        current_balance=Decimal("1000000"),
        is_active=True,
    )
    inversor = ThirdParty(
        name="Inversor Capital", organization_id=org_id,
        current_balance=Decimal("-5000000"),  # les debemos 5M
        is_active=True,
    )
    comisionista = ThirdParty(
        name="Vendedor Externo", organization_id=org_id,
        current_balance=Decimal("0"),
        is_active=True,
    )
    db_session.add_all([proveedor1, proveedor2, cliente1, cliente2, inversor, comisionista])
    db_session.flush()

    # --- Categorias de terceros ---
    cat_supplier = ThirdPartyCategory(name="Proveedores Mat", behavior_type="material_supplier", organization_id=org_id)
    cat_service = ThirdPartyCategory(name="Proveedores Serv", behavior_type="service_provider", organization_id=org_id)
    cat_customer = ThirdPartyCategory(name="Clientes", behavior_type="customer", organization_id=org_id)
    cat_investor = ThirdPartyCategory(name="Inversores", behavior_type="investor", organization_id=org_id)
    db_session.add_all([cat_supplier, cat_service, cat_customer, cat_investor])
    db_session.flush()
    db_session.add_all([
        ThirdPartyCategoryAssignment(third_party_id=proveedor1.id, category_id=cat_supplier.id),
        ThirdPartyCategoryAssignment(third_party_id=proveedor2.id, category_id=cat_supplier.id),
        ThirdPartyCategoryAssignment(third_party_id=cliente1.id, category_id=cat_customer.id),
        ThirdPartyCategoryAssignment(third_party_id=cliente2.id, category_id=cat_customer.id),
        ThirdPartyCategoryAssignment(third_party_id=inversor.id, category_id=cat_investor.id),
        ThirdPartyCategoryAssignment(third_party_id=comisionista.id, category_id=cat_service.id),
    ])
    db_session.flush()

    # --- Compras (3 liquidadas + 1 registrada) ---
    # Compra 1: Proveedor Alfa, 200kg Cobre @ $8000 = $1,600,000
    compra1 = Purchase(
        purchase_number=1, organization_id=org_id,
        supplier_id=proveedor1.id, date=now - timedelta(days=10),
        total_amount=Decimal("1600000"), status="liquidated",
        liquidated_at=now - timedelta(days=10),
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
        liquidated_at=now - timedelta(days=5),
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
        liquidated_at=now - timedelta(days=3),
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
        status="liquidated", liquidated_at=now - timedelta(days=8),
        payment_account_id=cuenta_efectivo.id,
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
        status="liquidated", liquidated_at=now - timedelta(days=6),
        payment_account_id=cuenta_banco.id,
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
        status="liquidated", liquidated_at=now - timedelta(days=2),
        payment_account_id=cuenta_efectivo.id,
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

    # Venta registrada (NO debe contar en reportes financieros, SI en alertas)
    venta_registrada = Sale(
        sale_number=7, organization_id=org_id,
        customer_id=cliente2.id, warehouse_id=warehouse.id,
        date=now - timedelta(days=1), total_amount=Decimal("777777"),
        status="registered",
    )
    db_session.add(venta_registrada)
    db_session.flush()
    linea_vr = SaleLine(
        sale_id=venta_registrada.id, material_id=mat_hierro.id,
        quantity=Decimal("500"), unit_price=Decimal("1555"),
        total_price=Decimal("777777"), unit_cost=Decimal("1200"),
    )
    db_session.add(linea_vr)

    # --- Doble Partida ---
    # DE completada: 200kg Hierro, compra@1100, venta@1500 = profit $80,000
    # Crear purchase y sale vinculados
    de_purchase = Purchase(
        purchase_number=5, organization_id=org_id,
        supplier_id=proveedor1.id, date=now - timedelta(days=7),
        total_amount=Decimal("220000"), status="liquidated",
        liquidated_at=now - timedelta(days=7),
    )
    db_session.add(de_purchase)
    db_session.flush()

    de_sale = Sale(
        sale_number=5, organization_id=org_id,
        customer_id=cliente2.id, warehouse_id=None,
        date=now - timedelta(days=7), total_amount=Decimal("300000"),
        status="liquidated", liquidated_at=now - timedelta(days=7),
    )
    db_session.add(de_sale)
    db_session.flush()

    doble_partida = DoubleEntry(
        double_entry_number=1, organization_id=org_id,
        date=(now - timedelta(days=7)).date(),
        supplier_id=proveedor1.id, customer_id=cliente2.id,
        purchase_id=de_purchase.id, sale_id=de_sale.id,
        status="liquidated", liquidated_at=now - timedelta(days=7),
    )
    db_session.add(doble_partida)
    db_session.flush()
    de_line1 = DoubleEntryLine(
        double_entry_id=doble_partida.id, material_id=mat_hierro.id,
        quantity=Decimal("200"), purchase_unit_price=Decimal("1100"),
        sale_unit_price=Decimal("1500"),
    )
    db_session.add(de_line1)

    # Vincular purchase y sale a la DE
    de_purchase.double_entry_id = doble_partida.id
    de_sale.double_entry_id = doble_partida.id

    # PurchaseLine y SaleLine de la DE (en produccion el servicio de DP las crea)
    de_purchase_line = PurchaseLine(
        purchase_id=de_purchase.id, material_id=mat_hierro.id,
        quantity=Decimal("200"), unit_price=Decimal("1100"),
        total_price=Decimal("220000"),
    )
    db_session.add(de_purchase_line)
    de_sale_line = SaleLine(
        sale_id=de_sale.id, material_id=mat_hierro.id,
        quantity=Decimal("200"), unit_price=Decimal("1500"),
        total_price=Decimal("300000"), unit_cost=Decimal("1100"),
    )
    db_session.add(de_sale_line)

    # DE cancelada (no debe contar)
    de_purchase2 = Purchase(
        purchase_number=6, organization_id=org_id,
        supplier_id=proveedor2.id, date=now - timedelta(days=4),
        total_amount=Decimal("100000"), status="cancelled",
    )
    db_session.add(de_purchase2)
    db_session.flush()
    de_sale2 = Sale(
        sale_number=6, organization_id=org_id,
        customer_id=cliente1.id, warehouse_id=None,
        date=now - timedelta(days=4), total_amount=Decimal("150000"),
        status="cancelled",
    )
    db_session.add(de_sale2)
    db_session.flush()

    doble_partida_cancelada = DoubleEntry(
        double_entry_number=2, organization_id=org_id,
        date=(now - timedelta(days=4)).date(),
        supplier_id=proveedor2.id, customer_id=cliente1.id,
        purchase_id=de_purchase2.id, sale_id=de_sale2.id,
        status="cancelled",
    )
    db_session.add(doble_partida_cancelada)
    db_session.flush()
    de_line2 = DoubleEntryLine(
        double_entry_id=doble_partida_cancelada.id, material_id=mat_cobre.id,
        quantity=Decimal("50"), purchase_unit_price=Decimal("2000"),
        sale_unit_price=Decimal("3000"),
    )
    db_session.add(de_line2)
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
    # Comision pagada (commission_payment): $50,000 → afecta Cash Flow, NO P&L
    mm_comision = MoneyMovement(
        movement_number=3, organization_id=org_id,
        date=now - timedelta(days=2),
        movement_type="commission_payment", amount=Decimal("50000"),
        account_id=cuenta_efectivo.id,
        third_party_id=comisionista.id,
        description="Pago comision venta", status="confirmed",
    )
    # Comision causada (commission_accrual): $50,000 → afecta P&L (base devengado,
    # decision #23), account_id=NULL. Es lo que el P&L cuenta como commissions_paid,
    # NO el commission_payment (que es el desembolso, va a Cash Flow).
    mm_comision_accrual = MoneyMovement(
        movement_number=12, organization_id=org_id,
        date=now - timedelta(days=2),
        movement_type="commission_accrual", amount=Decimal("50000"),
        account_id=None,
        third_party_id=comisionista.id,
        description="Comision causada venta", status="confirmed",
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
    db_session.add_all([mm_gasto, mm_arriendo, mm_comision, mm_comision_accrual, mm_servicio, mm_cobro])

    # --- Pagos de compras y cobros de ventas (Cash Flow puro) ---
    # Pago compra 1: $1,600,000 (cuenta efectivo)
    mm_pago_c1 = MoneyMovement(
        movement_number=6, organization_id=org_id,
        date=now - timedelta(days=10),
        movement_type="payment_to_supplier", amount=Decimal("1600000"),
        account_id=cuenta_efectivo.id, third_party_id=proveedor1.id,
        purchase_id=compra1.id, description="Pago compra 1", status="confirmed",
    )
    # Pago compra 2: $600,000 (cuenta efectivo)
    mm_pago_c2 = MoneyMovement(
        movement_number=7, organization_id=org_id,
        date=now - timedelta(days=5),
        movement_type="payment_to_supplier", amount=Decimal("600000"),
        account_id=cuenta_efectivo.id, third_party_id=proveedor2.id,
        purchase_id=compra2.id, description="Pago compra 2", status="confirmed",
    )
    # Pago compra 3: $850,000 (cuenta banco)
    mm_pago_c3 = MoneyMovement(
        movement_number=8, organization_id=org_id,
        date=now - timedelta(days=3),
        movement_type="payment_to_supplier", amount=Decimal("850000"),
        account_id=cuenta_banco.id, third_party_id=proveedor1.id,
        purchase_id=compra3.id, description="Pago compra 3", status="confirmed",
    )
    # Cobro venta 1: $1,050,000 (cuenta efectivo)
    mm_cobro_v1 = MoneyMovement(
        movement_number=9, organization_id=org_id,
        date=now - timedelta(days=8),
        movement_type="collection_from_client", amount=Decimal("1050000"),
        account_id=cuenta_efectivo.id, third_party_id=cliente1.id,
        sale_id=venta1.id, description="Cobro venta 1", status="confirmed",
    )
    # Cobro venta 2: $480,000 (cuenta banco)
    mm_cobro_v2 = MoneyMovement(
        movement_number=10, organization_id=org_id,
        date=now - timedelta(days=6),
        movement_type="collection_from_client", amount=Decimal("480000"),
        account_id=cuenta_banco.id, third_party_id=cliente2.id,
        sale_id=venta2.id, description="Cobro venta 2", status="confirmed",
    )
    # Cobro venta 3: $550,000 (cuenta efectivo)
    mm_cobro_v3 = MoneyMovement(
        movement_number=11, organization_id=org_id,
        date=now - timedelta(days=2),
        movement_type="collection_from_client", amount=Decimal("550000"),
        account_id=cuenta_efectivo.id, third_party_id=cliente1.id,
        sale_id=venta3.id, description="Cobro venta 3", status="confirmed",
    )
    db_session.add_all([mm_pago_c1, mm_pago_c2, mm_pago_c3, mm_cobro_v1, mm_cobro_v2, mm_cobro_v3])

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
        "comisionista": comisionista,
        "cuenta_efectivo": cuenta_efectivo,
        "cuenta_banco": cuenta_banco,
        "warehouse": warehouse,
        # Purchases (non-cancelled)
        "compras_pagadas": [compra1, compra2, compra3],
        "compra_registrada": compra4,
        # Sales (non-cancelled)
        "ventas_pagadas": [venta1, venta2, venta3],
        # DP-linked (operacion Pasa Mano liquidada)
        "de_purchase": de_purchase,
        "de_sale": de_sale,
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

    def test_pl_excludes_non_liquidated(self, client: TestClient, org_headers: dict, report_data: dict):
        """Ventas canceladas y registradas no aparecen en revenue."""
        response = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": str(report_data["date_from"]), "date_to": str(report_data["date_to"])},
            headers=org_headers,
        )
        data = response.json()

        # sales_count should be 3 (only liquidated, excl DE, cancelled, and registered)
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

        # Inflows: customer_collections (cobros via MM) + service_income
        # 3 cobros de ventas + 1 cobro manual = 1,050,000 + 480,000 + 550,000 + 100,000 = 2,180,000
        assert data["inflows"]["customer_collections"] == pytest.approx(2180000, abs=1)
        assert data["inflows"]["service_income"] == pytest.approx(150000, abs=1)
        # sale_collections = 0 (campo legacy, Cash Flow puro)
        assert data["inflows"]["sale_collections"] == 0

        # Outflows: supplier_payments (pagos via MM) + expenses + commissions
        # 3 pagos de compras = 1,600,000 + 600,000 + 850,000 = 3,050,000
        assert data["outflows"]["supplier_payments"] == pytest.approx(3050000, abs=1)
        assert data["outflows"]["expenses"] == pytest.approx(700000, abs=1)
        assert data["outflows"]["commission_payments"] == pytest.approx(50000, abs=1)
        # purchase_payments = 0 (campo legacy, Cash Flow puro)
        assert data["outflows"]["purchase_payments"] == 0

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
        """Cash flow incluye pagos de compras y cobros de ventas (solo MoneyMovements)."""
        response = client.get(
            "/api/v1/reports/cash-flow",
            params={"date_from": str(report_data["date_from"]), "date_to": str(report_data["date_to"])},
            headers=org_headers,
        )
        data = response.json()

        # 3 compras pagadas (DE no tiene MM, no cuenta): 1,600,000 + 600,000 + 850,000 = 3,050,000
        assert data["outflows"]["supplier_payments"] == pytest.approx(3050000, abs=1)
        # 3 ventas cobradas + cobro manual: 1,050,000 + 480,000 + 550,000 + 100,000 = 2,180,000
        assert data["inflows"]["customer_collections"] == pytest.approx(2180000, abs=1)

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

    def test_purchase_report_dp_filter_all(self, client: TestClient, org_headers: dict, report_data: dict):
        """dp_filter='all' (default) incluye compras de Pasa Mano."""
        response = client.get(
            "/api/v1/reports/purchases",
            params={
                "date_from": str(report_data["date_from"]),
                "date_to": str(report_data["date_to"]),
                "dp_filter": "all",
            },
            headers=org_headers,
        )
        assert response.status_code == 200
        data = response.json()
        # 3 compras normales (compra1/2/3) + de_purchase = 4
        assert data["purchase_count"] == 4

    def test_purchase_report_dp_filter_exclude(self, client: TestClient, org_headers: dict, report_data: dict):
        """dp_filter='exclude' omite la compra de Pasa Mano."""
        response_all = client.get(
            "/api/v1/reports/purchases",
            params={"date_from": str(report_data["date_from"]), "date_to": str(report_data["date_to"])},
            headers=org_headers,
        )
        response_excl = client.get(
            "/api/v1/reports/purchases",
            params={
                "date_from": str(report_data["date_from"]),
                "date_to": str(report_data["date_to"]),
                "dp_filter": "exclude",
            },
            headers=org_headers,
        )
        all_data = response_all.json()
        excl_data = response_excl.json()

        # de_purchase aporta exactamente 220000 y 200kg, 1 conteo
        assert excl_data["purchase_count"] == all_data["purchase_count"] - 1
        assert excl_data["total_amount"] == pytest.approx(all_data["total_amount"] - 220000, abs=1)
        assert excl_data["total_quantity"] == pytest.approx(all_data["total_quantity"] - 200, abs=1)

    def test_purchase_report_dp_filter_only(self, client: TestClient, org_headers: dict, report_data: dict):
        """dp_filter='only' devuelve solo la compra de Pasa Mano."""
        response = client.get(
            "/api/v1/reports/purchases",
            params={
                "date_from": str(report_data["date_from"]),
                "date_to": str(report_data["date_to"]),
                "dp_filter": "only",
            },
            headers=org_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["purchase_count"] == 1
        assert data["total_amount"] == pytest.approx(220000, abs=1)
        assert data["total_quantity"] == pytest.approx(200, abs=1)
        # Solo Proveedor Alfa (proveedor1)
        assert len(data["by_supplier"]) == 1
        assert data["by_supplier"][0]["supplier_name"] == "Proveedor Alfa"
        # Solo Hierro
        assert len(data["by_material"]) == 1
        assert data["by_material"][0]["material_code"] == "FE"


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

    def test_sales_report_dp_filter_all(self, client: TestClient, org_headers: dict, report_data: dict):
        """dp_filter='all' (default) incluye ventas de Pasa Mano."""
        response = client.get(
            "/api/v1/reports/sales",
            params={
                "date_from": str(report_data["date_from"]),
                "date_to": str(report_data["date_to"]),
                "dp_filter": "all",
            },
            headers=org_headers,
        )
        assert response.status_code == 200
        data = response.json()
        # 3 ventas normales (venta1/2/3) + de_sale = 4
        assert data["sale_count"] == 4

    def test_sales_report_dp_filter_exclude(self, client: TestClient, org_headers: dict, report_data: dict):
        """dp_filter='exclude' omite la venta de Pasa Mano."""
        response_all = client.get(
            "/api/v1/reports/sales",
            params={"date_from": str(report_data["date_from"]), "date_to": str(report_data["date_to"])},
            headers=org_headers,
        )
        response_excl = client.get(
            "/api/v1/reports/sales",
            params={
                "date_from": str(report_data["date_from"]),
                "date_to": str(report_data["date_to"]),
                "dp_filter": "exclude",
            },
            headers=org_headers,
        )
        all_data = response_all.json()
        excl_data = response_excl.json()

        # de_sale aporta 300000 revenue, 220000 cost, 80000 profit, 200kg
        assert excl_data["sale_count"] == all_data["sale_count"] - 1
        assert excl_data["total_revenue"] == pytest.approx(all_data["total_revenue"] - 300000, abs=1)
        assert excl_data["total_cost"] == pytest.approx(all_data["total_cost"] - 220000, abs=1)
        assert excl_data["total_profit"] == pytest.approx(all_data["total_profit"] - 80000, abs=1)
        assert excl_data["total_quantity"] == pytest.approx(all_data["total_quantity"] - 200, abs=1)

    def test_sales_report_dp_filter_only(self, client: TestClient, org_headers: dict, report_data: dict):
        """dp_filter='only' devuelve solo la venta de Pasa Mano."""
        response = client.get(
            "/api/v1/reports/sales",
            params={
                "date_from": str(report_data["date_from"]),
                "date_to": str(report_data["date_to"]),
                "dp_filter": "only",
            },
            headers=org_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["sale_count"] == 1
        assert data["total_revenue"] == pytest.approx(300000, abs=1)
        assert data["total_cost"] == pytest.approx(220000, abs=1)
        assert data["total_profit"] == pytest.approx(80000, abs=1)
        assert data["total_quantity"] == pytest.approx(200, abs=1)
        # Solo Cliente Dos (cliente2)
        assert len(data["by_customer"]) == 1
        assert data["by_customer"][0]["customer_name"] == "Cliente Dos"
        # Solo Hierro
        assert len(data["by_material"]) == 1
        assert data["by_material"][0]["material_code"] == "FE"

    def test_sales_profit_received_quantity_matches_pnl(
        self, client: TestClient, org_headers: dict, db_session, report_data: dict,
    ):
        """Utilidad bruta con diferencia de bascula (received_quantity).

        total_price = received_qty x precio (decision #18), COGS usa la
        cantidad original. La formula vieja (price - cost) x qty ignoraba
        la bascula y descuadraba contra el P&L (caso real Costa: $357M vs
        $342.5M). Guardrail: reporte de ventas == P&L gross_profit_sales.
        """
        now = report_data["now"]
        venta = Sale(
            organization_id=report_data["org_id"], sale_number=990,
            customer_id=report_data["cliente1"].id, date=now,
            status="liquidated", liquidated_at=now,
            total_amount=Decimal("950000"),  # 95kg recibidos x 10000
        )
        db_session.add(venta)
        db_session.flush()
        db_session.add(SaleLine(
            sale_id=venta.id, material_id=report_data["mat_cobre"].id,
            quantity=Decimal("100"), received_quantity=Decimal("95"),
            unit_price=Decimal("10000"), total_price=Decimal("950000"),
            unit_cost=Decimal("8000"),
        ))
        db_session.commit()

        params = {
            "date_from": str(report_data["date_from"]),
            "date_to": str(report_data["date_to"]),
        }
        report = client.get(
            "/api/v1/reports/sales",
            params={**params, "dp_filter": "exclude"},
            headers=org_headers,
        ).json()
        pnl = client.get(
            "/api/v1/reports/profit-and-loss", params=params, headers=org_headers,
        ).json()

        # La utilidad de esta venta es 950000 - 800000 = 150000
        # (la formula vieja diria (10000-8000)x100 = 200000)
        assert report["total_profit"] == pytest.approx(
            pnl["gross_profit_sales"], abs=1
        )
        # Identidad interna: profit == revenue - cost tambien con bascula
        assert report["total_profit"] == pytest.approx(
            report["total_revenue"] - report["total_cost"], abs=1
        )


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
        # Hay 1 compra registrada (pending) y 1 venta registrada (pending)
        assert "pending_purchases" in alert_types
        assert "pending_sales" in alert_types


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

    def test_tp_balances_advances(self, client: TestClient, org_headers: dict, report_data: dict, db_session):
        """Anticipos: proveedor con balance > 0 y cliente con balance < 0."""
        org_id = report_data["org_id"]

        # Proveedor con balance positivo (anticipo pagado, nos debe)
        prov_advance = ThirdParty(
            name="Proveedor Anticipo", organization_id=org_id,
            current_balance=Decimal("300000"),  # nos debe 300K
            is_active=True,
        )
        # Cliente con balance negativo (anticipo recibido, le debemos)
        cli_advance = ThirdParty(
            name="Cliente Anticipo", organization_id=org_id,
            current_balance=Decimal("-200000"),  # le debemos 200K
            is_active=True,
        )
        db_session.add_all([prov_advance, cli_advance])
        db_session.flush()
        cat_supplier = ThirdPartyCategory(name="Proveedores Adv", behavior_type="material_supplier", organization_id=org_id)
        cat_customer = ThirdPartyCategory(name="Clientes Adv", behavior_type="customer", organization_id=org_id)
        db_session.add_all([cat_supplier, cat_customer])
        db_session.flush()
        db_session.add_all([
            ThirdPartyCategoryAssignment(third_party_id=prov_advance.id, category_id=cat_supplier.id),
            ThirdPartyCategoryAssignment(third_party_id=cli_advance.id, category_id=cat_customer.id),
        ])
        db_session.commit()

        response = client.get("/api/v1/reports/third-party-balances", headers=org_headers)
        assert response.status_code == 200
        data = response.json()

        # Anticipos pagados = proveedores con balance > 0
        assert data["total_advances_paid"] == pytest.approx(300000, abs=1)
        # Anticipos recibidos = clientes con balance < 0
        assert data["total_advances_received"] == pytest.approx(200000, abs=1)

        # Payable ahora NO incluye al proveedor con balance > 0
        # Original: 2M + 500K = 2.5M (sin cambio, el nuevo proveedor tiene balance > 0)
        assert data["total_payable"] == pytest.approx(2500000, abs=1)
        # Receivable ahora NO incluye al cliente con balance < 0
        # Original: 3M + 1M = 4M (sin cambio, el nuevo cliente tiene balance < 0)
        assert data["total_receivable"] == pytest.approx(4000000, abs=1)


# ---------------------------------------------------------------------------
# Audit Balances Tests
# ---------------------------------------------------------------------------

class TestAuditBalances:

    @pytest.fixture
    def audit_data(self, db_session: Session, test_organization: Organization, test_user: User):
        """
        Dataset con saldos consistentes: current_balance refleja exactamente
        las operaciones creadas.
        """
        org_id = test_organization.id
        now = datetime.now(tz=timezone.utc)

        # Cuenta de dinero
        cuenta = MoneyAccount(
            name="Caja Audit", account_type="cash", organization_id=org_id,
            current_balance=Decimal("0"), is_active=True,
        )
        db_session.add(cuenta)
        db_session.flush()

        # Terceros
        proveedor = ThirdParty(
            name="Proveedor Audit", organization_id=org_id,
            current_balance=Decimal("0"), is_active=True,
        )
        cliente = ThirdParty(
            name="Cliente Audit", organization_id=org_id,
            current_balance=Decimal("0"), is_active=True,
        )
        comisionista = ThirdParty(
            name="Comisionista Audit", organization_id=org_id,
            current_balance=Decimal("0"), is_active=True,
        )
        db_session.add_all([proveedor, cliente, comisionista])
        db_session.flush()

        cat_supplier = ThirdPartyCategory(name="Proveedores Audit", behavior_type="material_supplier", organization_id=org_id)
        cat_customer = ThirdPartyCategory(name="Clientes Audit", behavior_type="customer", organization_id=org_id)
        db_session.add_all([cat_supplier, cat_customer])
        db_session.flush()
        db_session.add_all([
            ThirdPartyCategoryAssignment(third_party_id=proveedor.id, category_id=cat_supplier.id),
            ThirdPartyCategoryAssignment(third_party_id=cliente.id, category_id=cat_customer.id),
        ])
        db_session.flush()

        # Material y bodega
        cat = MaterialCategory(
            name="TestCat", organization_id=org_id, is_active=True,
        )
        db_session.add(cat)
        db_session.flush()
        mat = Material(
            code="TEST", name="Material Test", organization_id=org_id,
            category_id=cat.id, default_unit="kg",
            current_stock=Decimal("0"), current_stock_liquidated=Decimal("0"),
            current_stock_transit=Decimal("0"), current_average_cost=Decimal("0"),
            is_active=True,
        )
        wh = Warehouse(name="Bodega Audit", organization_id=org_id, is_active=True)
        db_session.add_all([mat, wh])
        db_session.flush()

        # Compra liquidada: $500,000 → proveedor.balance -= 500000
        compra = Purchase(
            purchase_number=100, organization_id=org_id,
            supplier_id=proveedor.id, date=now - timedelta(days=5),
            total_amount=Decimal("500000"), status="liquidated",
            liquidated_at=now - timedelta(days=5),
        )
        db_session.add(compra)
        db_session.flush()
        db_session.add(PurchaseLine(
            purchase_id=compra.id, material_id=mat.id, warehouse_id=wh.id,
            quantity=Decimal("100"), unit_price=Decimal("5000"),
            total_price=Decimal("500000"),
        ))
        proveedor.current_balance -= Decimal("500000")

        # Venta liquidada: $800,000 → cliente.balance += 800000
        venta = Sale(
            sale_number=100, organization_id=org_id,
            customer_id=cliente.id, warehouse_id=wh.id,
            date=now - timedelta(days=3), total_amount=Decimal("800000"),
            status="liquidated", liquidated_at=now - timedelta(days=3),
        )
        db_session.add(venta)
        db_session.flush()
        db_session.add(SaleLine(
            sale_id=venta.id, material_id=mat.id,
            quantity=Decimal("50"), unit_price=Decimal("16000"),
            total_price=Decimal("800000"), unit_cost=Decimal("5000"),
        ))
        cliente.current_balance += Decimal("800000")

        # Comision: $40,000 → commission_accrual MM → comisionista.balance -= 40000
        comm = SaleCommission(
            sale_id=venta.id, third_party_id=comisionista.id,
            concept="Comision test", commission_type="fixed",
            commission_value=Decimal("40000"), commission_amount=Decimal("40000"),
        )
        db_session.add(comm)
        mm_comision = MoneyMovement(
            movement_number=102, organization_id=org_id,
            date=now - timedelta(days=3),
            movement_type="commission_accrual", amount=Decimal("40000"),
            account_id=None, third_party_id=comisionista.id,
            description="Comision causada", status="confirmed",
        )
        db_session.add(mm_comision)
        comisionista.current_balance -= Decimal("40000")  # commission_accrual: direction=-1

        # MoneyMovement: pago proveedor $300,000 → cuenta -= 300000, proveedor.balance += 300000
        mm_pago = MoneyMovement(
            movement_number=100, organization_id=org_id,
            date=now - timedelta(days=2),
            movement_type="payment_to_supplier", amount=Decimal("300000"),
            account_id=cuenta.id, third_party_id=proveedor.id,
            description="Pago proveedor", status="confirmed",
        )
        db_session.add(mm_pago)
        cuenta.current_balance -= Decimal("300000")
        proveedor.current_balance += Decimal("300000")

        # MoneyMovement: cobro cliente $500,000 → cuenta += 500000, cliente.balance -= 500000
        mm_cobro = MoneyMovement(
            movement_number=101, organization_id=org_id,
            date=now - timedelta(days=1),
            movement_type="collection_from_client", amount=Decimal("500000"),
            account_id=cuenta.id, third_party_id=cliente.id,
            description="Cobro cliente", status="confirmed",
        )
        db_session.add(mm_cobro)
        cuenta.current_balance += Decimal("500000")
        cliente.current_balance -= Decimal("500000")

        db_session.commit()

        return {
            "cuenta": cuenta,
            "proveedor": proveedor,
            "cliente": cliente,
            "comisionista": comisionista,
        }

    def test_audit_balances_all_ok(
        self, client: TestClient, org_headers: dict, audit_data: dict,
    ):
        """Saldos correctos: todos los items reportan status=ok."""
        response = client.get("/api/v1/reports/audit-balances", headers=org_headers)
        assert response.status_code == 200
        data = response.json()

        # Summary sin mismatches
        assert data["summary"]["accounts_mismatch"] == 0
        assert data["summary"]["third_parties_mismatch"] == 0

        # Verificar que los items de audit existen con status ok
        account_map = {a["name"]: a for a in data["accounts"]}
        assert "Caja Audit" in account_map
        assert account_map["Caja Audit"]["status"] == "ok"
        # cuenta: -300000 + 500000 = 200000
        assert account_map["Caja Audit"]["calculated_balance"] == pytest.approx(200000, abs=1)

        tp_map = {t["name"]: t for t in data["third_parties"]}
        assert tp_map["Proveedor Audit"]["status"] == "ok"
        # proveedor: -500000 (compra) + 300000 (pago) = -200000
        assert tp_map["Proveedor Audit"]["calculated_balance"] == pytest.approx(-200000, abs=1)

        assert tp_map["Cliente Audit"]["status"] == "ok"
        # cliente: +800000 (venta) - 500000 (cobro) = 300000
        assert tp_map["Cliente Audit"]["calculated_balance"] == pytest.approx(300000, abs=1)

        assert tp_map["Comisionista Audit"]["status"] == "ok"
        # comisionista: commission_accrual direction=-1 → -40000 (les debemos la comision)
        assert tp_map["Comisionista Audit"]["calculated_balance"] == pytest.approx(-40000, abs=1)

    def test_audit_balances_detects_mismatch(
        self, client: TestClient, org_headers: dict, audit_data: dict, db_session: Session,
    ):
        """Detecta discrepancia cuando current_balance fue modificado manualmente."""
        # Forzar discrepancia en proveedor
        proveedor = audit_data["proveedor"]
        proveedor.current_balance += Decimal("999")
        db_session.commit()

        response = client.get("/api/v1/reports/audit-balances", headers=org_headers)
        assert response.status_code == 200
        data = response.json()

        assert data["summary"]["third_parties_mismatch"] >= 1

        tp_map = {t["name"]: t for t in data["third_parties"]}
        prov_audit = tp_map["Proveedor Audit"]
        assert prov_audit["status"] == "mismatch"
        assert prov_audit["difference"] == pytest.approx(999, abs=1)
        assert prov_audit["roles"] == ["material_supplier"]


# ---------------------------------------------------------------------------
# Balance Detailed Tests
# ---------------------------------------------------------------------------

class TestBalanceDetailed:

    def test_bd_endpoint_returns_structure(self, client: TestClient, org_headers: dict, report_data: dict):
        """Endpoint retorna estructura completa con activos, pasivos, patrimonio y verificacion."""
        response = client.get("/api/v1/reports/balance-detailed", headers=org_headers)
        assert response.status_code == 200
        data = response.json()

        # Estructura basica
        assert "assets" in data
        assert "liabilities" in data
        assert "total_assets" in data
        assert "total_liabilities" in data
        assert "equity" in data
        assert "verification" in data
        assert data["verification"]["is_balanced"] is True
        assert data["verification"]["result"] == 0

    def test_bd_asset_sections(self, client: TestClient, org_headers: dict, report_data: dict):
        """Activos contiene secciones esperadas con items individuales."""
        response = client.get("/api/v1/reports/balance-detailed", headers=org_headers)
        data = response.json()

        # Debe tener cash_and_bank con 2 cuentas (Caja y Banco)
        assert "cash_and_bank" in data["assets"]
        cash_items = data["assets"]["cash_and_bank"]["items"]
        assert len(cash_items) == 2
        cash_total = sum(i["balance"] for i in cash_items)
        assert cash_total == pytest.approx(15000000, abs=1)

        # Debe tener inventory_liquidated con 2 materiales (Cobre y Hierro)
        assert "inventory_liquidated" in data["assets"]
        inv_items = data["assets"]["inventory_liquidated"]["items"]
        assert len(inv_items) == 2

        # Debe tener customers_receivable con clientes que nos deben
        assert "customers_receivable" in data["assets"]
        cr_items = data["assets"]["customers_receivable"]["items"]
        assert len(cr_items) >= 2  # cliente1 y cliente2

    def test_bd_liability_sections(self, client: TestClient, org_headers: dict, report_data: dict):
        """Pasivos contiene proveedores e inversores."""
        response = client.get("/api/v1/reports/balance-detailed", headers=org_headers)
        data = response.json()

        # Proveedores: proveedor1 (-2M) y proveedor2 (-500K)
        assert "suppliers_payable" in data["liabilities"]
        sp_items = data["liabilities"]["suppliers_payable"]["items"]
        assert len(sp_items) == 2
        sp_total = data["liabilities"]["suppliers_payable"]["total"]
        assert sp_total == pytest.approx(2500000, abs=1)

        # Inversores
        inv_sections = [
            data["liabilities"].get("investors_partners", {"total": 0}),
            data["liabilities"].get("investors_obligations", {"total": 0}),
            data["liabilities"].get("investors_legacy", {"total": 0}),
        ]
        inv_total = sum(s["total"] for s in inv_sections)
        assert inv_total == pytest.approx(5000000, abs=1)

    def test_bd_equation_balances(self, client: TestClient, org_headers: dict, report_data: dict):
        """Verificacion: Activos - Pasivos - Patrimonio = 0."""
        response = client.get("/api/v1/reports/balance-detailed", headers=org_headers)
        data = response.json()

        result = data["total_assets"] - data["total_liabilities"] - data["equity"]
        assert abs(result) < 0.01

    def test_bd_investor_type_classification(
        self, client: TestClient, org_headers: dict, report_data: dict, db_session: Session,
    ):
        """Inversores con investor_type se clasifican en secciones distintas."""
        org_id = report_data["org_id"]

        # Crear socio
        socio = ThirdParty(
            name="Socio Capital", organization_id=org_id,
            current_balance=Decimal("-3000000"), is_active=True,
        )
        # Crear obligacion financiera
        obl = ThirdParty(
            name="Banco Credito", organization_id=org_id,
            current_balance=Decimal("-2000000"), is_active=True,
        )
        db_session.add_all([socio, obl])
        db_session.flush()
        cat_parent = ThirdPartyCategory(name="Inversionista", behavior_type="investor", organization_id=org_id)
        db_session.add(cat_parent)
        db_session.flush()
        cat_socios = ThirdPartyCategory(name="Socios", behavior_type="investor", parent_id=cat_parent.id, organization_id=org_id)
        cat_obligaciones = ThirdPartyCategory(name="Obligaciones Financieras", behavior_type="investor", parent_id=cat_parent.id, organization_id=org_id)
        db_session.add_all([cat_socios, cat_obligaciones])
        db_session.flush()
        db_session.add_all([
            ThirdPartyCategoryAssignment(third_party_id=socio.id, category_id=cat_socios.id),
            ThirdPartyCategoryAssignment(third_party_id=obl.id, category_id=cat_obligaciones.id),
        ])
        db_session.commit()

        response = client.get("/api/v1/reports/balance-detailed", headers=org_headers)
        data = response.json()

        # Socio debe estar en investors_partners
        partners = data["liabilities"].get("investors_partners", {"items": []})
        partner_names = [i["name"] for i in partners["items"]]
        assert "Socio Capital" in partner_names

        # Obligacion financiera en investors_obligations
        obligations = data["liabilities"].get("investors_obligations", {"items": []})
        obl_names = [i["name"] for i in obligations["items"]]
        assert "Banco Credito" in obl_names

        # Balance sigue cuadrado
        assert data["verification"]["is_balanced"] is True

    def test_bd_as_of_date_excludes_future_cost_changes(
        self, client: TestClient, org_headers: dict, report_data: dict, db_session: Session,
    ):
        """as_of_date no debe incluir MaterialCostHistory con transaction_date posterior.

        Regresion: cutoff_date = cutoff_dt.date() daba as_of_date+1 dia, incluyendo
        cambios de costo de operaciones del dia siguiente. Ahora usa as_of_date.
        """
        from datetime import date
        from app.models.material_cost_history import MaterialCostHistory
        from app.models.inventory_movement import InventoryMovement

        org_id = report_data["org_id"]
        material = db_session.query(Material).filter_by(organization_id=org_id).first()
        warehouse = db_session.query(Warehouse).filter_by(organization_id=org_id).first()

        # Movimiento de inventario en T-5 con costo inicial 1000
        base = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)
        db_session.add(InventoryMovement(
            organization_id=org_id, material_id=material.id, warehouse_id=warehouse.id,
            movement_type="purchase", quantity=Decimal("100"), unit_cost=Decimal("1000"),
            reference_type="purchase", reference_id=uuid4(),
            date=base,
        ))
        # Cost history: costo inicial 1000 (transaction_date T-5)
        db_session.add(MaterialCostHistory(
            organization_id=org_id, material_id=material.id,
            previous_cost=Decimal("0"), new_cost=Decimal("1000"),
            previous_stock=Decimal("0"), new_stock=Decimal("100"),
            source_type="purchase_liquidation", source_id=uuid4(),
            transaction_date=date(2026, 1, 5),
        ))
        # Cost history posterior: costo cambia a 2000 con transaction_date T+0 (2026-01-10)
        db_session.add(MaterialCostHistory(
            organization_id=org_id, material_id=material.id,
            previous_cost=Decimal("1000"), new_cost=Decimal("2000"),
            previous_stock=Decimal("100"), new_stock=Decimal("100"),
            source_type="purchase_liquidation", source_id=uuid4(),
            transaction_date=date(2026, 1, 10),
        ))
        db_session.commit()

        # Balance al 2026-01-09 NO debe incluir el cost change del 2026-01-10
        resp = client.get(
            "/api/v1/reports/balance-detailed?as_of_date=2026-01-09", headers=org_headers,
        )
        assert resp.status_code == 200
        items = resp.json()["assets"]["inventory_liquidated"]["items"]
        target = next((i for i in items if i["id"] == str(material.id)), None)
        assert target is not None
        # Costo al 09 debe ser 1000, NO 2000 (que es del 10)
        assert target["avg_cost"] == pytest.approx(1000, abs=0.01)

        # Balance al 2026-01-10 SI debe incluir el cost change
        resp2 = client.get(
            "/api/v1/reports/balance-detailed?as_of_date=2026-01-10", headers=org_headers,
        )
        items2 = resp2.json()["assets"]["inventory_liquidated"]["items"]
        target2 = next((i for i in items2 if i["id"] == str(material.id)), None)
        assert target2["avg_cost"] == pytest.approx(2000, abs=0.01)


# ---------------------------------------------------------------------------
# Commission Supplier Category Validation Tests
# ---------------------------------------------------------------------------

class TestCommissionSupplierValidation:

    def test_purchase_commission_rejects_non_supplier(
        self, client: TestClient, org_headers: dict, report_data: dict, db_session: Session,
    ):
        """Comisionista sin categoria proveedor en compra → 400."""
        org_id = report_data["org_id"]

        # Tercero solo cliente (sin categoria proveedor)
        non_supplier = ThirdParty(
            name="Solo Cliente", organization_id=org_id,
            current_balance=Decimal("0"), is_active=True,
        )
        db_session.add(non_supplier)
        db_session.flush()
        cat_customer = ThirdPartyCategory(name="Clientes Com", behavior_type="customer", organization_id=org_id)
        db_session.add(cat_customer)
        db_session.flush()
        db_session.add(ThirdPartyCategoryAssignment(third_party_id=non_supplier.id, category_id=cat_customer.id))
        db_session.commit()

        wh_id = str(report_data["warehouse"].id)
        payload = {
            "supplier_id": str(report_data["proveedor1"].id),
            "date": datetime.now(timezone.utc).isoformat(),
            "lines": [{
                "material_id": str(report_data["mat_cobre"].id),
                "warehouse_id": wh_id,
                "quantity": 10,
                "unit_price": 1000,
            }],
            "commissions": [{
                "third_party_id": str(non_supplier.id),
                "concept": "Test",
                "commission_type": "fixed",
                "commission_value": 100,
            }],
        }
        response = client.post("/api/v1/purchases/", json=payload, headers=org_headers)
        assert response.status_code == 400
        assert "proveedor" in response.json()["detail"].lower()

    def test_sale_commission_rejects_non_supplier(
        self, client: TestClient, org_headers: dict, report_data: dict, db_session: Session,
    ):
        """Comisionista sin categoria proveedor en venta → 400."""
        org_id = report_data["org_id"]

        non_supplier = ThirdParty(
            name="Solo Inversionista", organization_id=org_id,
            current_balance=Decimal("0"), is_active=True,
        )
        db_session.add(non_supplier)
        db_session.flush()
        cat_investor = ThirdPartyCategory(name="Inversores Com", behavior_type="investor", organization_id=org_id)
        db_session.add(cat_investor)
        db_session.flush()
        db_session.add(ThirdPartyCategoryAssignment(third_party_id=non_supplier.id, category_id=cat_investor.id))
        db_session.commit()

        payload = {
            "customer_id": str(report_data["cliente1"].id),
            "warehouse_id": str(report_data["warehouse"].id),
            "date": datetime.now(timezone.utc).isoformat(),
            "lines": [{
                "material_id": str(report_data["mat_cobre"].id),
                "quantity": 10,
                "unit_price": 15000,
            }],
            "commissions": [{
                "third_party_id": str(non_supplier.id),
                "concept": "Test",
                "commission_type": "fixed",
                "commission_value": 100,
            }],
        }
        response = client.post("/api/v1/sales/", json=payload, headers=org_headers)
        assert response.status_code == 400
        assert "proveedor" in response.json()["detail"].lower()

    def test_commission_accepts_supplier(
        self, client: TestClient, org_headers: dict, report_data: dict,
    ):
        """Comisionista con categoria service_provider → aceptado (201)."""
        wh_id = str(report_data["warehouse"].id)
        payload = {
            "supplier_id": str(report_data["proveedor1"].id),
            "date": datetime.now(timezone.utc).isoformat(),
            "lines": [{
                "material_id": str(report_data["mat_cobre"].id),
                "warehouse_id": wh_id,
                "quantity": 10,
                "unit_price": 1000,
            }],
            "commissions": [{
                "third_party_id": str(report_data["comisionista"].id),  # has service_provider category
                "concept": "Intermediacion",
                "commission_type": "fixed",
                "commission_value": 500,
            }],
        }
        response = client.post("/api/v1/purchases/", json=payload, headers=org_headers)
        assert response.status_code == 201


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


# ---------------------------------------------------------------------------
# Tests: Gastos por Unidad de Negocio
# ---------------------------------------------------------------------------

@pytest.fixture
def bu_data(db_session: Session, test_organization, test_user):
    """Dataset para tests de reportes por Unidad de Negocio."""
    org_id = test_organization.id
    now = datetime.now(tz=timezone.utc)

    # UNs (incluye la UN de sistema Pasa Mano, como la crea el seed/migracion)
    bu_cobre = BusinessUnit(name="Cobre", organization_id=org_id, is_active=True)
    bu_chatarra = BusinessUnit(name="Chatarra", organization_id=org_id, is_active=True)
    bu_pasamano = BusinessUnit(
        name="Pasa Mano", organization_id=org_id, is_active=True,
        system_code="double_entry",
    )
    db_session.add_all([bu_cobre, bu_chatarra, bu_pasamano])
    db_session.flush()

    # Categorias
    cat_metales = MaterialCategory(name="Metales BU", organization_id=org_id, is_active=True)
    db_session.add(cat_metales)
    db_session.flush()

    cat_gasto_directo = ExpenseCategory(name="Nomina Op", organization_id=org_id, is_direct_expense=True, is_active=True)
    cat_gasto_indirecto = ExpenseCategory(name="Arriendo BU", organization_id=org_id, is_direct_expense=False, is_active=True)
    db_session.add_all([cat_gasto_directo, cat_gasto_indirecto])
    db_session.flush()

    # Materiales con UN
    mat_cobre = Material(
        code="CU-BU", name="Cobre BU", organization_id=org_id,
        category_id=cat_metales.id, default_unit="kg",
        business_unit_id=bu_cobre.id,
        current_stock=Decimal("500"), current_stock_liquidated=Decimal("500"),
        current_stock_transit=Decimal("0"), current_average_cost=Decimal("8000"),
        is_active=True,
    )
    mat_chatarra = Material(
        code="CH-BU", name="Chatarra BU", organization_id=org_id,
        category_id=cat_metales.id, default_unit="kg",
        business_unit_id=bu_chatarra.id,
        current_stock=Decimal("1000"), current_stock_liquidated=Decimal("1000"),
        current_stock_transit=Decimal("0"), current_average_cost=Decimal("1200"),
        is_active=True,
    )
    db_session.add_all([mat_cobre, mat_chatarra])
    db_session.flush()

    # Bodega, cuenta, terceros
    wh = Warehouse(name="Bodega BU", organization_id=org_id, is_active=True)
    cuenta = MoneyAccount(name="Caja BU", account_type="cash", organization_id=org_id, current_balance=Decimal("50000000"), is_active=True)
    db_session.add_all([wh, cuenta])
    db_session.flush()

    supplier_cat = ThirdPartyCategory(name="Prov Mat BU", behavior_type="material_supplier", organization_id=org_id)
    customer_cat = ThirdPartyCategory(name="Clientes BU", behavior_type="customer", organization_id=org_id)
    db_session.add_all([supplier_cat, customer_cat])
    db_session.flush()

    supplier = ThirdParty(name="Prov BU", organization_id=org_id, current_balance=Decimal("0"), is_active=True)
    customer = ThirdParty(name="Cliente BU", organization_id=org_id, current_balance=Decimal("0"), is_active=True)
    db_session.add_all([supplier, customer])
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(third_party_id=supplier.id, category_id=supplier_cat.id))
    db_session.add(ThirdPartyCategoryAssignment(third_party_id=customer.id, category_id=customer_cat.id))
    db_session.flush()

    # Compras liquidadas: Cobre 200kg @ $8000 = $1.6M, Chatarra 500kg @ $1200 = $600K
    compra = Purchase(
        organization_id=org_id, purchase_number=900,
        supplier_id=supplier.id, date=now, status="liquidated",
        liquidated_at=now,
        total_amount=Decimal("2200000"),
    )
    db_session.add(compra)
    db_session.flush()
    db_session.add(PurchaseLine(
        purchase_id=compra.id, material_id=mat_cobre.id,
        warehouse_id=wh.id, quantity=Decimal("200"), unit_price=Decimal("8000"),
        total_price=Decimal("1600000"),
    ))
    db_session.add(PurchaseLine(
        purchase_id=compra.id, material_id=mat_chatarra.id,
        warehouse_id=wh.id, quantity=Decimal("500"), unit_price=Decimal("1200"),
        total_price=Decimal("600000"),
    ))
    db_session.flush()

    # Venta liquidada: Cobre 100kg @ $12000 = $1.2M
    venta = Sale(
        organization_id=org_id, sale_number=900,
        customer_id=customer.id, date=now, status="liquidated",
        liquidated_at=now,
        total_amount=Decimal("1200000"),
    )
    db_session.add(venta)
    db_session.flush()
    db_session.add(SaleLine(
        sale_id=venta.id, material_id=mat_cobre.id,
        quantity=Decimal("100"), unit_price=Decimal("12000"),
        total_price=Decimal("1200000"), unit_cost=Decimal("8000"),
    ))
    db_session.flush()

    # Gasto DIRECTO a Chatarra: $500K
    gasto_directo = MoneyMovement(
        organization_id=org_id, movement_number=900,
        date=now, movement_type="expense", amount=Decimal("500000"),
        account_id=cuenta.id, description="Nomina operarios Chatarra",
        expense_category_id=cat_gasto_directo.id,
        business_unit_id=bu_chatarra.id,
        status="confirmed",
    )
    db_session.add(gasto_directo)

    # Gasto GENERAL (ambos NULL): $1M
    gasto_general = MoneyMovement(
        organization_id=org_id, movement_number=901,
        date=now, movement_type="expense", amount=Decimal("1000000"),
        account_id=cuenta.id, description="Arriendo bodega",
        expense_category_id=cat_gasto_indirecto.id,
        status="confirmed",
    )
    db_session.add(gasto_general)

    # Gasto COMPARTIDO entre Cobre y Chatarra: $200K
    gasto_compartido = MoneyMovement(
        organization_id=org_id, movement_number=902,
        date=now, movement_type="expense", amount=Decimal("200000"),
        account_id=cuenta.id, description="Mantenimiento prensa",
        expense_category_id=cat_gasto_indirecto.id,
        applicable_business_unit_ids=[str(bu_cobre.id), str(bu_chatarra.id)],
        status="confirmed",
    )
    db_session.add(gasto_compartido)

    # --- Doble Partida liquidada (material Chatarra): 300kg @1000 compra / @1400 venta ---
    # Sus compras NO entran a la base de prorrateo (double_entry_id != NULL) y
    # su margen/comisiones van a la seccion Pasa Mano, no a la UN Chatarra.
    de_purchase = Purchase(
        organization_id=org_id, purchase_number=950,
        supplier_id=supplier.id, date=now, status="liquidated",
        liquidated_at=now, total_amount=Decimal("300000"),
    )
    db_session.add(de_purchase)
    db_session.flush()
    de_sale = Sale(
        organization_id=org_id, sale_number=950,
        customer_id=customer.id, date=now, status="liquidated",
        liquidated_at=now, total_amount=Decimal("420000"),
    )
    db_session.add(de_sale)
    db_session.flush()
    dp = DoubleEntry(
        double_entry_number=950, organization_id=org_id,
        date=now.date(), supplier_id=supplier.id, customer_id=customer.id,
        purchase_id=de_purchase.id, sale_id=de_sale.id,
        status="liquidated", liquidated_at=now,
    )
    db_session.add(dp)
    db_session.flush()
    de_purchase.double_entry_id = dp.id
    de_sale.double_entry_id = dp.id
    db_session.add(DoubleEntryLine(
        double_entry_id=dp.id, material_id=mat_chatarra.id,
        quantity=Decimal("300"), purchase_unit_price=Decimal("1000"),
        sale_unit_price=Decimal("1400"),
    ))
    db_session.add(PurchaseLine(
        purchase_id=de_purchase.id, material_id=mat_chatarra.id,
        warehouse_id=wh.id, quantity=Decimal("300"), unit_price=Decimal("1000"),
        total_price=Decimal("300000"),
    ))
    db_session.add(SaleLine(
        sale_id=de_sale.id, material_id=mat_chatarra.id,
        quantity=Decimal("300"), unit_price=Decimal("1400"),
        total_price=Decimal("420000"), unit_cost=Decimal("1000"),
    ))

    # Comision de la DP: $30K -> debe ir a la seccion Pasa Mano (fuga #2)
    comm_dp = MoneyMovement(
        organization_id=org_id, movement_number=903,
        date=now, movement_type="commission_accrual", amount=Decimal("30000"),
        account_id=None, sale_id=de_sale.id,
        description="Comision DP", status="confirmed",
    )
    db_session.add(comm_dp)

    # Comision de la venta de bodega (Cobre): $60K -> se queda en la UN Cobre
    comm_bodega = MoneyMovement(
        organization_id=org_id, movement_number=904,
        date=now, movement_type="commission_accrual", amount=Decimal("60000"),
        account_id=None, sale_id=venta.id,
        description="Comision venta bodega", status="confirmed",
    )
    db_session.add(comm_bodega)

    # Gasto DIRECTO a la UN sistema Pasa Mano: $250K (ej. bono de mula foranea)
    gasto_pasamano = MoneyMovement(
        organization_id=org_id, movement_number=905,
        date=now, movement_type="expense", amount=Decimal("250000"),
        account_id=cuenta.id, description="Bono mula foranea",
        expense_category_id=cat_gasto_directo.id,
        business_unit_id=bu_pasamano.id,
        status="confirmed",
    )
    db_session.add(gasto_pasamano)

    db_session.commit()

    return {
        "bu_cobre": bu_cobre,
        "bu_chatarra": bu_chatarra,
        "bu_pasamano": bu_pasamano,
        "mat_cobre": mat_cobre,
        "mat_chatarra": mat_chatarra,
        "cat_metales": cat_metales,
        "cat_gasto_directo": cat_gasto_directo,
        "cat_gasto_indirecto": cat_gasto_indirecto,
        "warehouse": wh,
        "cuenta": cuenta,
        "gasto_general_mov": gasto_general,
        "compra_cobre_value": Decimal("1600000"),  # 200kg @ $8000
        "compra_chatarra_value": Decimal("600000"),  # 500kg @ $1200
        "compra_total": Decimal("2200000"),
        "venta_cobre_revenue": Decimal("1200000"),
        "venta_cobre_cogs": Decimal("800000"),  # 100 * 8000
        "gasto_directo_chatarra": Decimal("500000"),
        "gasto_general": Decimal("1000000"),
        "gasto_compartido": Decimal("200000"),
        # Doble partida
        "dp_sales": Decimal("420000"),
        "dp_purchases": Decimal("300000"),
        "dp_gross": Decimal("120000"),
        "dp_commission": Decimal("30000"),
        "bodega_commission": Decimal("60000"),
        "gasto_pasamano": Decimal("250000"),
    }


class TestProfitabilityByBU:

    def test_endpoint_returns_200(self, client, org_headers, bu_data):
        resp = client.get(
            "/api/v1/reports/profitability-by-business-unit",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "business_units" in data
        assert "totals" in data

    def test_direct_expenses_assigned_correctly(self, client, org_headers, bu_data):
        """Gasto directo de $500K debe ir 100% a Chatarra."""
        resp = client.get(
            "/api/v1/reports/profitability-by-business-unit",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        data = resp.json()
        chatarra = next((bu for bu in data["business_units"] if bu["business_unit_name"] == "Chatarra"), None)
        assert chatarra is not None
        assert chatarra["direct_expenses"] == 500000.0

    def test_general_expenses_prorated(self, client, org_headers, bu_data):
        """Gasto general $1M prorrateado por valor compras: Cobre 1.6M/2.2M, Chatarra 0.6M/2.2M."""
        resp = client.get(
            "/api/v1/reports/profitability-by-business-unit",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        data = resp.json()
        cobre = next((bu for bu in data["business_units"] if bu["business_unit_name"] == "Cobre"), None)
        chatarra = next((bu for bu in data["business_units"] if bu["business_unit_name"] == "Chatarra"), None)
        assert cobre is not None
        assert chatarra is not None
        # Cobre: 1.6M/2.2M * 1M ≈ 727,272.73
        assert abs(cobre["general_expenses"] - 727272.73) < 1
        # Chatarra: 0.6M/2.2M * 1M ≈ 272,727.27
        assert abs(chatarra["general_expenses"] - 272727.27) < 1

    def test_shared_expenses_prorated(self, client, org_headers, bu_data):
        """Gasto compartido $200K entre Cobre y Chatarra, prorrateado por compras."""
        resp = client.get(
            "/api/v1/reports/profitability-by-business-unit",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        data = resp.json()
        cobre = next((bu for bu in data["business_units"] if bu["business_unit_name"] == "Cobre"), None)
        chatarra = next((bu for bu in data["business_units"] if bu["business_unit_name"] == "Chatarra"), None)
        # Cobre: 1.6M/2.2M * 200K ≈ 145,454.55
        assert abs(cobre["shared_expenses"] - 145454.55) < 1
        # Chatarra: 0.6M/2.2M * 200K ≈ 54,545.45
        assert abs(chatarra["shared_expenses"] - 54545.45) < 1

    def test_sales_revenue_by_bu(self, client, org_headers, bu_data):
        """Venta de Cobre debe ir a UN Cobre."""
        resp = client.get(
            "/api/v1/reports/profitability-by-business-unit",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        data = resp.json()
        cobre = next((bu for bu in data["business_units"] if bu["business_unit_name"] == "Cobre"), None)
        assert cobre["sales_revenue"] == 1200000.0
        assert cobre["sales_cogs"] == 800000.0


class TestRealCostByMaterial:

    def test_endpoint_returns_200(self, client, org_headers, bu_data):
        resp = client.get(
            "/api/v1/reports/real-cost-by-material",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "business_units" in data

    def test_overhead_rate_calculation(self, client, org_headers, bu_data):
        """Overhead rate = gastos totales UN / kg comprados."""
        resp = client.get(
            "/api/v1/reports/real-cost-by-material",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        data = resp.json()
        chatarra = next((bu for bu in data["business_units"] if bu["business_unit_name"] == "Chatarra"), None)
        assert chatarra is not None
        assert chatarra["kg_purchased"] == 500.0
        # Chatarra total expenses = directo $500K + shared prorate + general prorate
        # overhead = total / 500
        assert chatarra["overhead_rate"] > 0

    def test_real_cost_includes_overhead(self, client, org_headers, bu_data):
        """Costo real = avg cost + overhead rate."""
        resp = client.get(
            "/api/v1/reports/real-cost-by-material",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        data = resp.json()
        cobre_bu = next((bu for bu in data["business_units"] if bu["business_unit_name"] == "Cobre"), None)
        assert cobre_bu is not None
        assert len(cobre_bu["materials"]) >= 1
        mat = cobre_bu["materials"][0]
        assert mat["average_cost"] == 8000.0
        assert mat["real_cost"] == mat["average_cost"] + mat["overhead_rate"]


class TestBUValidation:

    def test_expense_with_both_bu_fields_returns_422(self, client, org_headers, bu_data):
        """business_unit_id Y applicable_business_unit_ids → 422."""
        payload = {
            "amount": 100000,
            "expense_category_id": str(MoneyMovement.__table__.c.expense_category_id),  # dummy
            "account_id": "dummy",
            "date": "2026-03-17T12:00:00Z",
            "description": "test",
            "business_unit_id": str(bu_data["bu_cobre"].id),
            "applicable_business_unit_ids": [str(bu_data["bu_chatarra"].id)],
        }
        # Intentar via el endpoint directamente no es facil sin IDs validos,
        # asi que testeamos la validacion del schema
        from app.schemas.money_movement import ExpenseCreate
        import pydantic
        with pytest.raises(pydantic.ValidationError, match="directa O compartida"):
            ExpenseCreate(**{
                "amount": 100000,
                "expense_category_id": bu_data["bu_cobre"].id,
                "account_id": bu_data["bu_cobre"].id,
                "date": "2026-03-17T12:00:00",
                "description": "test",
                "business_unit_id": bu_data["bu_cobre"].id,
                "applicable_business_unit_ids": [bu_data["bu_chatarra"].id],
            })


PROFITABILITY_URL = "/api/v1/reports/profitability-by-business-unit"
PROFITABILITY_PARAMS = {"date_from": "2026-01-01", "date_to": "2026-12-31"}


class TestPasamanoSection:
    """Seccion Pasa Mano del reporte de rentabilidad (plan-rentabilidad-un-pasamano.md).

    La tabla por UN es SOLO bodega; doble partida se analiza en `double_entry`.
    """

    def test_bu_rows_exclude_dp_commissions(self, client, org_headers, bu_data):
        """Fuga #2: la comision de la DP ($30K, material Chatarra) NO cae en la
        UN Chatarra; la comision de bodega ($60K) SI queda en Cobre."""
        resp = client.get(PROFITABILITY_URL, params=PROFITABILITY_PARAMS, headers=org_headers)
        data = resp.json()
        chatarra = next(bu for bu in data["business_units"] if bu["business_unit_name"] == "Chatarra")
        cobre = next(bu for bu in data["business_units"] if bu["business_unit_name"] == "Cobre")
        assert chatarra["sale_commissions"] == 0.0
        assert cobre["sale_commissions"] == float(bu_data["bodega_commission"])
        assert data["double_entry"]["commissions"] == float(bu_data["dp_commission"])

    def test_bu_rows_have_no_de_profit(self, client, org_headers, bu_data):
        """Las filas por UN no exponen de_profit y la utilidad bruta = revenue - cogs."""
        resp = client.get(PROFITABILITY_URL, params=PROFITABILITY_PARAMS, headers=org_headers)
        data = resp.json()
        for bu in data["business_units"] + [data["totals"]]:
            assert "de_profit" not in bu
            assert bu["total_gross_profit"] == pytest.approx(
                bu["sales_revenue"] - bu["sales_cogs"], abs=0.01
            )
        # El margen de la DP (material Chatarra) NO infla la bruta de Chatarra
        chatarra = next(bu for bu in data["business_units"] if bu["business_unit_name"] == "Chatarra")
        assert chatarra["sales_revenue"] == 0.0
        assert chatarra["total_gross_profit"] == 0.0

    def test_system_bu_not_a_bodega_row(self, client, org_headers, bu_data):
        """La UN sistema no aparece como fila de la tabla bodega."""
        resp = client.get(PROFITABILITY_URL, params=PROFITABILITY_PARAMS, headers=org_headers)
        data = resp.json()
        names = {bu["business_unit_name"] for bu in data["business_units"]}
        assert "Pasa Mano" not in names

    def test_pasamano_section_totals(self, client, org_headers, bu_data):
        """Seccion Pasa Mano: ventas/compras/margen/comisiones/gastos/neta/margen%."""
        resp = client.get(PROFITABILITY_URL, params=PROFITABILITY_PARAMS, headers=org_headers)
        de = resp.json()["double_entry"]
        assert de["label"] == "Pasa Mano"
        assert de["business_unit_id"] == str(bu_data["bu_pasamano"].id)
        assert de["sales_total"] == float(bu_data["dp_sales"])
        assert de["purchases_total"] == float(bu_data["dp_purchases"])
        assert de["gross_profit"] == float(bu_data["dp_gross"])
        assert de["commissions"] == float(bu_data["dp_commission"])
        assert de["direct_expenses"] == float(bu_data["gasto_pasamano"])
        expected_net = float(bu_data["dp_gross"] - bu_data["dp_commission"] - bu_data["gasto_pasamano"])
        assert de["net_profit"] == pytest.approx(expected_net, abs=0.01)
        # Detalle por categoria
        assert de["direct_expenses_detail"][0]["amount"] == float(bu_data["gasto_pasamano"])

    def test_grand_total_net(self, client, org_headers, bu_data):
        """Total General = neta bodega + neta pasamano."""
        resp = client.get(PROFITABILITY_URL, params=PROFITABILITY_PARAMS, headers=org_headers)
        data = resp.json()
        assert data["grand_total_net"] == pytest.approx(
            data["totals"]["net_profit"] + data["double_entry"]["net_profit"], abs=0.01
        )

    def test_pasamano_margin_matches_pnl(self, client, org_headers, bu_data):
        """Paridad: pasamano.gross_profit == P&L double_entry_profit."""
        resp = client.get(PROFITABILITY_URL, params=PROFITABILITY_PARAMS, headers=org_headers)
        de = resp.json()["double_entry"]
        pnl = client.get(
            "/api/v1/reports/profit-and-loss",
            params=PROFITABILITY_PARAMS, headers=org_headers,
        ).json()
        assert de["gross_profit"] == pytest.approx(pnl["double_entry_profit"], abs=1)

    def test_pasamano_direct_expense_not_in_unassigned(self, client, org_headers, bu_data):
        """El gasto directo a la UN sistema NO fuga a 'Sin Asignar' (punto fragil QA)."""
        resp = client.get(PROFITABILITY_URL, params=PROFITABILITY_PARAMS, headers=org_headers)
        data = resp.json()
        unassigned = next(
            (bu for bu in data["business_units"] if bu["business_unit_name"] == "Sin Asignar"),
            None,
        )
        if unassigned is not None:
            assert unassigned["direct_expenses"] == 0.0

    def test_expenses_report_shows_pasamano_group(self, client, org_headers, bu_data):
        """Reporte de Gastos (#44): la UN Pasa Mano SI aparece como grupo con su directo."""
        resp = client.get(
            "/api/v1/reports/expenses",
            params={**PROFITABILITY_PARAMS, "group_by": "bu"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        groups = resp.json()["groups"]
        pasamano = next((g for g in groups if g["label"] == "Pasa Mano"), None)
        assert pasamano is not None
        assert pasamano["total"] == float(bu_data["gasto_pasamano"])

    def test_proration_unchanged_with_dp_present(self, client, org_headers, bu_data):
        """Criterio #6: el prorrateo de generales NO cambia por la presencia de DP
        (la compra DP de $300K queda fuera de la base $2.2M)."""
        resp = client.get(PROFITABILITY_URL, params=PROFITABILITY_PARAMS, headers=org_headers)
        data = resp.json()
        cobre = next(bu for bu in data["business_units"] if bu["business_unit_name"] == "Cobre")
        chatarra = next(bu for bu in data["business_units"] if bu["business_unit_name"] == "Chatarra")
        # Mismos valores exactos que test_general_expenses_prorated (base 1.6M/0.6M de 2.2M)
        assert abs(cobre["general_expenses"] - 727272.73) < 1
        assert abs(chatarra["general_expenses"] - 272727.27) < 1

    def test_real_cost_excludes_system_bu(self, client, org_headers, bu_data):
        """Costo Real por Material: la UN sistema no genera fila fantasma ni
        su gasto cae en 'Sin Asignar'."""
        resp = client.get(
            "/api/v1/reports/real-cost-by-material",
            params=PROFITABILITY_PARAMS, headers=org_headers,
        )
        data = resp.json()
        names = {bu["business_unit_name"] for bu in data["business_units"]}
        assert "Pasa Mano" not in names
        unassigned = next(
            (bu for bu in data["business_units"] if bu["business_unit_name"] == "Sin Asignar"),
            None,
        )
        if unassigned is not None:
            assert unassigned["total_expenses"] == 0.0

    def test_empty_period_pasamano_zeros(self, client, org_headers, bu_data):
        """Periodo sin actividad: seccion pasamano en ceros, sin error."""
        resp = client.get(
            PROFITABILITY_URL,
            params={"date_from": "2020-01-01", "date_to": "2020-01-31"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["double_entry"]["sales_total"] == 0
        assert data["double_entry"]["net_profit"] == 0
        assert data["grand_total_net"] == 0


class TestSystemBUGuards:
    """Guards de la UN de sistema (Pasa Mano): 5 puntos de entrada de asignacion
    compartida + materiales + delete."""

    def test_pasamano_bu_created_on_new_org(self, db_session, test_user):
        """El seed de org nueva crea la UN Pasa Mano con system_code."""
        from sqlalchemy import select
        from app.services.organization import create_organization
        from app.schemas.organization import OrganizationCreate

        org = create_organization(
            db_session,
            OrganizationCreate(name="Org Seed Pasamano Test"),
            owner_user_id=test_user.id,
        )
        bu = db_session.execute(
            select(BusinessUnit).where(
                BusinessUnit.organization_id == org.id,
                BusinessUnit.system_code == "double_entry",
            )
        ).scalar_one_or_none()
        assert bu is not None
        assert bu.name == "Pasa Mano"
        assert bu.is_active is True

    def test_material_cannot_use_system_bu_on_create(self, client, org_headers, bu_data):
        resp = client.post(
            "/api/v1/materials",
            json={
                "code": "PMX-1", "name": "Material invalido",
                "category_id": str(bu_data["cat_metales"].id),
                "business_unit_id": str(bu_data["bu_pasamano"].id),
                "default_unit": "kg",
            },
            headers=org_headers,
        )
        assert resp.status_code == 400
        assert "sistema" in resp.json()["detail"]

    def test_material_cannot_use_system_bu_on_update(self, client, org_headers, bu_data):
        resp = client.patch(
            f"/api/v1/materials/{bu_data['mat_cobre'].id}",
            json={"business_unit_id": str(bu_data["bu_pasamano"].id)},
            headers=org_headers,
        )
        assert resp.status_code == 400
        assert "sistema" in resp.json()["detail"]

    def test_system_bu_cannot_be_deleted(self, client, org_headers, bu_data):
        resp = client.delete(
            f"/api/v1/business-units/{bu_data['bu_pasamano'].id}",
            headers=org_headers,
        )
        assert resp.status_code == 400
        assert "sistema" in resp.json()["detail"]

    def test_system_bu_rename_allowed(self, client, org_headers, bu_data):
        """Rename SI permitido (lookup por system_code, no por nombre)."""
        resp = client.patch(
            f"/api/v1/business-units/{bu_data['bu_pasamano'].id}",
            json={"name": "Foráneos"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Foráneos"
        assert resp.json()["system_code"] == "double_entry"

    def test_shared_expense_rejects_system_bu(self, client, org_headers, bu_data):
        """Punto de entrada 1: create MoneyMovement (expense)."""
        resp = client.post(
            "/api/v1/money-movements/expense",
            json={
                "amount": 100000,
                "account_id": str(bu_data["cuenta"].id),
                "expense_category_id": str(bu_data["cat_gasto_directo"].id),
                "date": "2026-03-17T12:00:00Z",
                "description": "Gasto compartido invalido",
                "applicable_business_unit_ids": [
                    str(bu_data["bu_cobre"].id),
                    str(bu_data["bu_pasamano"].id),
                ],
            },
            headers=org_headers,
        )
        assert resp.status_code == 422
        assert "sistema" in str(resp.json()["detail"])

    def test_direct_expense_to_system_bu_allowed(self, client, org_headers, bu_data):
        """Asignacion DIRECTA a la UN sistema: permitida (es el proposito)."""
        resp = client.post(
            "/api/v1/money-movements/expense",
            json={
                "amount": 150000,
                "account_id": str(bu_data["cuenta"].id),
                "expense_category_id": str(bu_data["cat_gasto_directo"].id),
                "date": "2026-03-17T12:00:00Z",
                "description": "Flete DP directo",
                "business_unit_id": str(bu_data["bu_pasamano"].id),
            },
            headers=org_headers,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["business_unit_id"] == str(bu_data["bu_pasamano"].id)

    def test_shared_scheduled_expense_rejects_system_bu(self, client, org_headers, bu_data):
        """Punto de entrada 2: create ScheduledExpense."""
        resp = client.post(
            "/api/v1/scheduled-expenses/",
            json={
                "name": "Poliza compartida invalida",
                "total_amount": 1200000,
                "total_months": 12,
                "source_account_id": str(bu_data["cuenta"].id),
                "expense_category_id": str(bu_data["cat_gasto_directo"].id),
                "start_date": "2026-03-01",
                "applicable_business_unit_ids": [str(bu_data["bu_pasamano"].id)],
            },
            headers=org_headers,
        )
        assert resp.status_code == 422
        assert "sistema" in str(resp.json()["detail"])

    def test_shared_fixed_asset_rejects_system_bu(self, client, org_headers, bu_data):
        """Punto de entrada 3: create FixedAsset."""
        resp = client.post(
            "/api/v1/fixed-assets/",
            json={
                "name": "Prensa compartida invalida",
                "purchase_date": "2026-03-01",
                "purchase_value": 5000000,
                "salvage_value": 0,
                "depreciation_rate": 10,
                "depreciation_start_date": "2026-03-01",
                "expense_category_id": str(bu_data["cat_gasto_directo"].id),
                "source_account_id": str(bu_data["cuenta"].id),
                "applicable_business_unit_ids": [str(bu_data["bu_pasamano"].id)],
            },
            headers=org_headers,
        )
        assert resp.status_code == 422
        assert "sistema" in str(resp.json()["detail"])

    def test_reclassify_shared_to_system_bu_rejected(self, client, org_headers, bu_data):
        """Punto de entrada 4 (gap QA): PATCH /classification con UN sistema en compartido."""
        mov = bu_data["gasto_general_mov"]
        resp = client.patch(
            f"/api/v1/money-movements/{mov.id}/classification",
            json={
                "expense_category_id": str(bu_data["cat_gasto_directo"].id),
                "applicable_business_unit_ids": [
                    str(bu_data["bu_cobre"].id),
                    str(bu_data["bu_pasamano"].id),
                ],
            },
            headers=org_headers,
        )
        assert resp.status_code == 422
        assert "sistema" in str(resp.json()["detail"])

    def test_reclassify_direct_to_system_bu_allowed(self, client, org_headers, bu_data):
        """Reclasificar DIRECTO a la UN sistema: permitido (Gustavo reclasifica un flete)."""
        mov = bu_data["gasto_general_mov"]
        resp = client.patch(
            f"/api/v1/money-movements/{mov.id}/classification",
            json={
                "expense_category_id": str(bu_data["cat_gasto_directo"].id),
                "business_unit_id": str(bu_data["bu_pasamano"].id),
            },
            headers=org_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["business_unit_id"] == str(bu_data["bu_pasamano"].id)

    def test_expense_category_default_shared_rejects_system_bu(self, client, org_headers, bu_data):
        """Punto de entrada 5: default compartido de ExpenseCategory."""
        resp = client.post(
            "/api/v1/expense-categories",
            json={
                "name": "Cat default compartido invalido",
                "is_direct_expense": True,
                "default_applicable_business_unit_ids": [str(bu_data["bu_pasamano"].id)],
            },
            headers=org_headers,
        )
        assert resp.status_code == 422
        assert "sistema" in str(resp.json()["detail"])

    def test_expense_category_default_direct_to_system_bu_allowed(self, client, org_headers, bu_data):
        """Default DIRECTO a la UN sistema: permitido (ej. categoria 'Bonos Foraneos')."""
        resp = client.post(
            "/api/v1/expense-categories",
            json={
                "name": "Bonos Foraneos",
                "is_direct_expense": True,
                "default_business_unit_id": str(bu_data["bu_pasamano"].id),
            },
            headers=org_headers,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["default_business_unit_id"] == str(bu_data["bu_pasamano"].id)

    def test_expense_with_direct_bu_valid(self, client, org_headers, bu_data):
        """business_unit_id solo → valido."""
        from app.schemas.money_movement import ExpenseCreate
        schema = ExpenseCreate(
            amount=100000,
            expense_category_id=bu_data["bu_cobre"].id,
            account_id=bu_data["bu_cobre"].id,
            date="2026-03-17T12:00:00",
            description="test",
            business_unit_id=bu_data["bu_cobre"].id,
        )
        assert schema.business_unit_id == bu_data["bu_cobre"].id
        assert schema.applicable_business_unit_ids is None

    def test_expense_empty_applicable_normalized_to_none(self, client, org_headers, bu_data):
        """applicable_business_unit_ids=[] → normalizado a None (General)."""
        from app.schemas.money_movement import ExpenseCreate
        schema = ExpenseCreate(
            amount=100000,
            expense_category_id=bu_data["bu_cobre"].id,
            account_id=bu_data["bu_cobre"].id,
            date="2026-03-17T12:00:00",
            description="test",
            applicable_business_unit_ids=[],
        )
        assert schema.applicable_business_unit_ids is None


# ---------------------------------------------------------------------------
# Tests: Edge cases de reportes por UN
# ---------------------------------------------------------------------------

@pytest.fixture
def bu_data_with_de_commission(db_session: Session, test_organization, test_user, bu_data):
    """Extiende bu_data con una Doble Partida multi-material + comision."""
    from sqlalchemy import select as sa_select
    org_id = test_organization.id
    now = datetime.now(tz=timezone.utc)

    # Service provider para comision
    sp_cat = ThirdPartyCategory(name="SP Comision BU", behavior_type="service_provider", organization_id=org_id)
    db_session.add(sp_cat)
    db_session.flush()
    comisionista = ThirdParty(name="Comisionista BU", organization_id=org_id, current_balance=Decimal("0"), is_active=True)
    db_session.add(comisionista)
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(third_party_id=comisionista.id, category_id=sp_cat.id))
    db_session.flush()

    # Terceros para DP
    supplier_cat = db_session.execute(
        sa_select(ThirdPartyCategory).where(
            ThirdPartyCategory.organization_id == org_id,
            ThirdPartyCategory.behavior_type == "material_supplier",
        )
    ).scalar_one()
    customer_cat = db_session.execute(
        sa_select(ThirdPartyCategory).where(
            ThirdPartyCategory.organization_id == org_id,
            ThirdPartyCategory.behavior_type == "customer",
        )
    ).scalar_one()
    de_supplier = ThirdParty(name="DP Supplier BU", organization_id=org_id, current_balance=Decimal("0"), is_active=True)
    de_customer = ThirdParty(name="DP Customer BU", organization_id=org_id, current_balance=Decimal("0"), is_active=True)
    db_session.add_all([de_supplier, de_customer])
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(third_party_id=de_supplier.id, category_id=supplier_cat.id))
    db_session.add(ThirdPartyCategoryAssignment(third_party_id=de_customer.id, category_id=customer_cat.id))
    db_session.flush()

    # Compra y venta internas del DP
    de_purchase = Purchase(
        organization_id=org_id, purchase_number=901,
        supplier_id=de_supplier.id, date=now, status="liquidated",
        liquidated_at=now,
        total_amount=Decimal("5000000"),
    )
    db_session.add(de_purchase)
    db_session.flush()

    de_sale = Sale(
        organization_id=org_id, sale_number=901,
        customer_id=de_customer.id, date=now, status="liquidated",
        liquidated_at=now,
        total_amount=Decimal("6500000"),
    )
    db_session.add(de_sale)
    db_session.flush()

    # DP referencia compra y venta internas
    de = DoubleEntry(
        organization_id=org_id, double_entry_number=900,
        supplier_id=de_supplier.id, customer_id=de_customer.id,
        purchase_id=de_purchase.id, sale_id=de_sale.id,
        date=now, status="liquidated", liquidated_at=now,
    )
    db_session.add(de)
    db_session.flush()

    # Vincular venta y compra al DP
    de_sale.double_entry_id = de.id
    de_purchase.double_entry_id = de.id

    db_session.add(DoubleEntryLine(
        double_entry_id=de.id, material_id=bu_data["mat_cobre"].id,
        quantity=Decimal("100"), purchase_unit_price=Decimal("40000"), sale_unit_price=Decimal("50000"),
    ))
    db_session.add(DoubleEntryLine(
        double_entry_id=de.id, material_id=bu_data["mat_chatarra"].id,
        quantity=Decimal("200"), purchase_unit_price=Decimal("5000"), sale_unit_price=Decimal("7500"),
    ))

    db_session.add(SaleLine(
        sale_id=de_sale.id, material_id=bu_data["mat_cobre"].id,
        quantity=Decimal("100"), unit_price=Decimal("50000"),
        total_price=Decimal("5000000"), unit_cost=Decimal("40000"),
    ))
    db_session.add(SaleLine(
        sale_id=de_sale.id, material_id=bu_data["mat_chatarra"].id,
        quantity=Decimal("200"), unit_price=Decimal("7500"),
        total_price=Decimal("1500000"), unit_cost=Decimal("5000"),
    ))
    db_session.flush()

    # Comision de $1M vinculada a la venta del DP
    comm_movement = MoneyMovement(
        organization_id=org_id, movement_number=910,
        date=now, movement_type="commission_accrual",
        amount=Decimal("1000000"),
        account_id=None, description="Comision DP test",
        third_party_id=comisionista.id, sale_id=de_sale.id,
        status="confirmed",
    )
    db_session.add(comm_movement)
    db_session.commit()

    return {
        **bu_data,
        "de_commission": Decimal("1000000"),
        "de_sale_total": Decimal("6500000"),
        "de_cobre_line_value": Decimal("5000000"),
        "de_chatarra_line_value": Decimal("1500000"),
    }


class TestDpPctGeneralExpenses:
    """Plan A.2: % de gastos generales por categoria atribuido a Pasa Mano.

    Fixture base bu_data: compras Cobre $1.6M / Chatarra $600K (base $2.2M),
    gasto GENERAL $1M en 'Arriendo BU' (indirecta raiz), compartido $200K,
    directo Chatarra $500K, directo Pasa Mano $250K, DP margen $120K,
    comisiones DP $30K / bodega $60K.
    """

    CATS_URL = "/api/v1/expense-categories"

    def _set_pct(self, db_session, cat, pct):
        cat.double_entry_general_pct = Decimal(str(pct))
        db_session.commit()

    def _get_report(self, client, org_headers):
        resp = client.get(PROFITABILITY_URL, params=PROFITABILITY_PARAMS, headers=org_headers)
        assert resp.status_code == 200
        return resp.json()

    # ------------------------------------------------------------------
    # Mecanica del slice en Rentabilidad por UN
    # ------------------------------------------------------------------

    def test_pct_slice_to_pasamano(self, client, org_headers, db_session, bu_data):
        """General $1M al 20% -> $200K a Pasa Mano, $800K prorrateados."""
        self._set_pct(db_session, bu_data["cat_gasto_indirecto"], 20)
        data = self._get_report(client, org_headers)

        de = data["double_entry"]
        assert de["general_expenses"] == pytest.approx(200000, abs=0.01)
        assert len(de["general_expenses_detail"]) == 1
        detail = de["general_expenses_detail"][0]
        assert detail["category_name"] == "Arriendo BU"
        assert detail["pct"] == pytest.approx(20.0)
        assert detail["amount"] == pytest.approx(200000, abs=0.01)

        cobre = next(bu for bu in data["business_units"] if bu["business_unit_name"] == "Cobre")
        chatarra = next(bu for bu in data["business_units"] if bu["business_unit_name"] == "Chatarra")
        # 800K x (1.6/2.2) y 800K x (0.6/2.2)
        assert abs(cobre["general_expenses"] - 581818.18) < 1
        assert abs(chatarra["general_expenses"] - 218181.82) < 1

    def test_pct_child_inherits_parent(self, client, org_headers, db_session, bu_data):
        """Gasto general en subcategoria usa el % del padre (herencia en lectura)."""
        parent = bu_data["cat_gasto_indirecto"]
        self._set_pct(db_session, parent, 20)
        child = ExpenseCategory(
            name="Arriendo Bodega Norte", organization_id=parent.organization_id,
            is_direct_expense=False, parent_id=parent.id, is_active=True,
        )
        db_session.add(child)
        db_session.flush()
        db_session.add(MoneyMovement(
            organization_id=parent.organization_id, movement_number=960,
            date=datetime.now(tz=timezone.utc), movement_type="expense",
            amount=Decimal("500000"), account_id=bu_data["cuenta"].id,
            description="Arriendo bodega norte", expense_category_id=child.id,
            status="confirmed",
        ))
        db_session.commit()

        data = self._get_report(client, org_headers)
        de = data["double_entry"]
        # 200K del padre ($1M) + 100K de la hija ($500K), ambos al 20%
        assert de["general_expenses"] == pytest.approx(300000, abs=0.01)
        child_line = next(
            d for d in de["general_expenses_detail"]
            if d["category_name"] == "Arriendo Bodega Norte"
        )
        assert child_line["pct"] == pytest.approx(20.0)
        assert child_line["amount"] == pytest.approx(100000, abs=0.01)

    def test_pct_zero_default_unchanged(self, client, org_headers, bu_data):
        """Sin % configurado (default 0): numeros identicos a la decision #58."""
        data = self._get_report(client, org_headers)
        cobre = next(bu for bu in data["business_units"] if bu["business_unit_name"] == "Cobre")
        chatarra = next(bu for bu in data["business_units"] if bu["business_unit_name"] == "Chatarra")
        assert abs(cobre["general_expenses"] - 727272.73) < 1
        assert abs(chatarra["general_expenses"] - 272727.27) < 1
        assert data["double_entry"]["general_expenses"] == 0
        assert data["double_entry"]["general_expenses_detail"] == []

    def test_pct_100_percent(self, client, org_headers, db_session, bu_data):
        """100%: todo el general a Pasa Mano, bodegas $0 de esa categoria."""
        self._set_pct(db_session, bu_data["cat_gasto_indirecto"], 100)
        data = self._get_report(client, org_headers)
        assert data["double_entry"]["general_expenses"] == pytest.approx(1000000, abs=0.01)
        cobre = next(bu for bu in data["business_units"] if bu["business_unit_name"] == "Cobre")
        chatarra = next(bu for bu in data["business_units"] if bu["business_unit_name"] == "Chatarra")
        assert cobre["general_expenses"] == pytest.approx(0, abs=0.01)
        assert chatarra["general_expenses"] == pytest.approx(0, abs=0.01)

    def test_pct_uncategorized_general_ignored(self, client, org_headers, db_session, bu_data):
        """Gasto general SIN categoria -> 0%, se prorratea completo."""
        self._set_pct(db_session, bu_data["cat_gasto_indirecto"], 20)
        db_session.add(MoneyMovement(
            organization_id=bu_data["cat_gasto_indirecto"].organization_id,
            movement_number=961, date=datetime.now(tz=timezone.utc),
            movement_type="expense", amount=Decimal("300000"),
            account_id=bu_data["cuenta"].id, description="Gasto sin categoria",
            expense_category_id=None, status="confirmed",
        ))
        db_session.commit()

        data = self._get_report(client, org_headers)
        # Solo el $1M de Arriendo aporta slice; el $300K sin categoria no
        assert data["double_entry"]["general_expenses"] == pytest.approx(200000, abs=0.01)
        cobre = next(bu for bu in data["business_units"] if bu["business_unit_name"] == "Cobre")
        chatarra = next(bu for bu in data["business_units"] if bu["business_unit_name"] == "Chatarra")
        # (800K + 300K) prorrateados
        assert abs(cobre["general_expenses"] - 800000.00) < 1
        assert abs(chatarra["general_expenses"] - 300000.00) < 1

    def test_pct_direct_and_shared_untouched(self, client, org_headers, db_session, bu_data):
        """El % NO toca gastos directos ni compartidos de la misma categoria."""
        # 'Arriendo BU' tambien tiene el compartido de $200K — debe quedar igual
        self._set_pct(db_session, bu_data["cat_gasto_indirecto"], 20)
        data = self._get_report(client, org_headers)
        cobre = next(bu for bu in data["business_units"] if bu["business_unit_name"] == "Cobre")
        chatarra = next(bu for bu in data["business_units"] if bu["business_unit_name"] == "Chatarra")
        assert abs(cobre["shared_expenses"] - 145454.55) < 1
        assert abs(chatarra["shared_expenses"] - 54545.45) < 1
        assert chatarra["direct_expenses"] == pytest.approx(500000, abs=0.01)
        assert data["double_entry"]["direct_expenses"] == pytest.approx(250000, abs=0.01)

    def test_pct_net_and_grand_total_parity(self, client, org_headers, db_session, bu_data):
        """La neta Pasa Mano baja exactamente el slice; el TOTAL GENERAL no cambia."""
        before = self._get_report(client, org_headers)
        self._set_pct(db_session, bu_data["cat_gasto_indirecto"], 20)
        after = self._get_report(client, org_headers)

        assert after["double_entry"]["net_profit"] == pytest.approx(
            before["double_entry"]["net_profit"] - 200000, abs=0.01
        )
        # El slice solo MUEVE plata dentro del reporte
        assert after["grand_total_net"] == pytest.approx(before["grand_total_net"], abs=1)
        # Sin lineas no-UN en este fixture, el P&L == TOTAL GENERAL
        rec = after["pnl_reconciliation"]
        assert rec["pnl_net_profit"] == pytest.approx(after["grand_total_net"], abs=1)

    # ------------------------------------------------------------------
    # Sync: Reporte de Gastos + drill-down + Costo Real
    # ------------------------------------------------------------------

    def test_pct_expenses_report_shows_pasamano_general(
        self, client, org_headers, db_session, bu_data,
    ):
        """El grupo Pasa Mano del Reporte de Gastos incluye directo + slice."""
        self._set_pct(db_session, bu_data["cat_gasto_indirecto"], 20)
        resp = client.get(
            "/api/v1/reports/expenses",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31", "group_by": "bu"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        groups = resp.json()["groups"]
        pasamano = next((g for g in groups if g["label"] == "Pasa Mano"), None)
        assert pasamano is not None
        # $250K directo + $200K slice de generales
        assert pasamano["total"] == pytest.approx(450000, abs=0.01)

    def test_pct_expenses_detail_drilldown(self, client, org_headers, db_session, bu_data):
        """El drill-down del grupo Pasa Mano lista el gasto con allocated == slice."""
        self._set_pct(db_session, bu_data["cat_gasto_indirecto"], 20)
        resp = client.get(
            "/api/v1/reports/expenses/detail",
            params={
                "date_from": "2026-01-01", "date_to": "2026-12-31",
                "business_unit_id": str(bu_data["bu_pasamano"].id),
            },
            headers=org_headers,
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        general_item = next(
            i for i in items if i["movement_id"] == str(bu_data["gasto_general_mov"].id)
        )
        assert general_item["allocated_amount"] == pytest.approx(200000, abs=0.01)
        assert general_item["allocation_type"] == "general"

    def test_pct_real_cost_excludes_slice(self, client, org_headers, db_session, bu_data):
        """Costo Real por Material: el slice NO es overhead de material."""
        self._set_pct(db_session, bu_data["cat_gasto_indirecto"], 20)
        resp = client.get(
            "/api/v1/reports/real-cost-by-material",
            params=PROFITABILITY_PARAMS,
            headers=org_headers,
        )
        assert resp.status_code == 200
        bus = resp.json()["business_units"]
        cobre = next(b for b in bus if b["business_unit_name"] == "Cobre")
        chatarra = next(b for b in bus if b["business_unit_name"] == "Chatarra")
        # Cobre: compartido 145,454.55 + general 581,818.18 (de los $800K restantes)
        assert abs(cobre["total_expenses"] - 727272.73) < 1
        # Chatarra: directo 500K + compartido 54,545.45 + general 218,181.82
        assert abs(chatarra["total_expenses"] - 772727.27) < 1

    # ------------------------------------------------------------------
    # Validaciones del CRUD de categorias
    # ------------------------------------------------------------------
    # RBAC del PATCH (treasury.manage_expenses) ya cubierto en
    # test_permission_enforcement.py — el % viaja por el endpoint existente.

    def test_pct_validation_range(self, client, org_headers):
        for bad_pct in (-1, 101):
            resp = client.post(
                self.CATS_URL,
                json={"name": f"Cat pct {bad_pct}", "double_entry_general_pct": bad_pct},
                headers=org_headers,
            )
            assert resp.status_code == 422

    def test_pct_on_subcategory_rejected(self, client, org_headers, db_session, bu_data):
        parent = bu_data["cat_gasto_indirecto"]
        # Crear hija con pct > 0 -> 422
        resp = client.post(
            self.CATS_URL,
            json={
                "name": "Hija con pct", "parent_id": str(parent.id),
                "double_entry_general_pct": 10,
            },
            headers=org_headers,
        )
        assert resp.status_code == 422
        # Editar hija existente para ponerle pct -> 422
        child = ExpenseCategory(
            name="Hija sin pct", organization_id=parent.organization_id,
            is_direct_expense=False, parent_id=parent.id, is_active=True,
        )
        db_session.add(child)
        db_session.commit()
        resp = client.patch(
            f"{self.CATS_URL}/{child.id}",
            json={"double_entry_general_pct": 10},
            headers=org_headers,
        )
        assert resp.status_code == 422

    def test_pct_on_direct_category_rejected(self, client, org_headers, bu_data):
        # Crear directa con pct -> 422
        resp = client.post(
            self.CATS_URL,
            json={
                "name": "Directa con pct", "is_direct_expense": True,
                "double_entry_general_pct": 10,
            },
            headers=org_headers,
        )
        assert resp.status_code == 422
        # Editar la directa existente para ponerle pct -> 422
        resp = client.patch(
            f"{self.CATS_URL}/{bu_data['cat_gasto_directo'].id}",
            json={"double_entry_general_pct": 10},
            headers=org_headers,
        )
        assert resp.status_code == 422

    def test_pct_cleared_on_reparent(self, client, org_headers, db_session, bu_data):
        """G1 (QA): reparentar una raiz con pct > 0 zerea el pct (no queda huerfano)."""
        resp = client.post(
            self.CATS_URL,
            json={"name": "Raiz con pct", "double_entry_general_pct": 20},
            headers=org_headers,
        )
        assert resp.status_code == 201
        cat_id = resp.json()["id"]
        assert float(resp.json()["double_entry_general_pct"]) == pytest.approx(20.0)

        resp = client.patch(
            f"{self.CATS_URL}/{cat_id}",
            json={"parent_id": str(bu_data["cat_gasto_indirecto"].id)},
            headers=org_headers,
        )
        assert resp.status_code == 200
        assert float(resp.json()["double_entry_general_pct"]) == 0

    def test_pct_no_system_bu_fallback(self, client, org_headers, db_session, bu_data):
        """Sin UN sistema el % se ignora — la plata no se pierde."""
        bu_data["bu_pasamano"].system_code = None
        self._set_pct(db_session, bu_data["cat_gasto_indirecto"], 20)
        data = self._get_report(client, org_headers)
        assert data["double_entry"]["general_expenses"] == 0
        # El $1M general se prorratea completo (conservacion)
        total_general = sum(bu["general_expenses"] for bu in data["business_units"])
        assert abs(total_general - 1000000) < 1

    # ------------------------------------------------------------------
    # Bloque de conciliacion con P&L (§3.7)
    # ------------------------------------------------------------------

    def test_reconciliation_zero_case(self, client, org_headers, bu_data):
        """Sin servicios/transformaciones/ajustes: 4 lineas en 0 y P&L == TOTAL GENERAL."""
        data = self._get_report(client, org_headers)
        rec = data["pnl_reconciliation"]
        assert rec["service_income"] == 0
        assert rec["transformation_net"] == 0
        assert rec["inventory_adjustment_net"] == 0
        assert rec["tp_adjustment_net"] == 0
        assert rec["pnl_net_profit"] == pytest.approx(data["grand_total_net"], abs=1)

    def test_reconciliation_residual_zero(self, client, org_headers, db_session, bu_data):
        """Test de oro anti-drift: TOTAL GENERAL + 4 lineas == Utilidad Neta P&L.

        Si el P&L gana una linea nueva y nadie la agrega al bloque, esto revienta.
        """
        from app.models.inventory_adjustment import InventoryAdjustment
        from app.models.material_transformation import MaterialTransformation

        org_id = bu_data["cat_gasto_indirecto"].organization_id
        now = datetime.now(tz=timezone.utc)
        self._set_pct(db_session, bu_data["cat_gasto_indirecto"], 20)

        # Servicios: +150K
        db_session.add(MoneyMovement(
            organization_id=org_id, movement_number=962, date=now,
            movement_type="service_income", amount=Decimal("150000"),
            account_id=bu_data["cuenta"].id, description="Servicio de pesaje",
            status="confirmed",
        ))
        # Ajustes de terceros: gain 80K - loss 50K = +30K
        db_session.add(MoneyMovement(
            organization_id=org_id, movement_number=963, date=now,
            movement_type="tp_adjustment_credit", amount=Decimal("80000"),
            adjustment_class="gain", description="Ajuste a favor",
            status="confirmed",
        ))
        db_session.add(MoneyMovement(
            organization_id=org_id, movement_number=964, date=now,
            movement_type="tp_adjustment_debit", amount=Decimal("50000"),
            adjustment_class="loss", description="Ajuste en contra",
            status="confirmed",
        ))
        # Ajuste de inventario: +10kg @ 1200 = +12K
        db_session.add(InventoryAdjustment(
            organization_id=org_id, adjustment_number=97001, date=now,
            adjustment_type="increase", material_id=bu_data["mat_chatarra"].id,
            warehouse_id=bu_data["warehouse"].id,
            previous_stock=Decimal("1000"), quantity=Decimal("10"),
            new_stock=Decimal("1010"), unit_cost=Decimal("1200"),
            total_value=Decimal("12000"), reason="Ajuste conteo fisico",
            status="confirmed",
        ))
        # Transformacion: value_difference 25K - waste 5K = +20K
        db_session.add(MaterialTransformation(
            organization_id=org_id, transformation_number=970, date=now,
            source_material_id=bu_data["mat_chatarra"].id,
            source_warehouse_id=bu_data["warehouse"].id,
            source_quantity=Decimal("50"), source_unit_cost=Decimal("1200"),
            source_total_value=Decimal("60000"),
            waste_quantity=Decimal("2"), waste_value=Decimal("5000"),
            value_difference=Decimal("25000"), cost_distribution="average_cost",
            reason="Desarmado test A.2", status="confirmed",
        ))
        # Ingresos financieros (plan F): interes causado de prestamo por cobrar +45K
        db_session.add(MoneyMovement(
            organization_id=org_id, movement_number=965, date=now,
            movement_type="loan_interest_accrual", amount=Decimal("45000"),
            description="Intereses prestamo test", status="confirmed",
        ))
        db_session.commit()

        data = self._get_report(client, org_headers)
        rec = data["pnl_reconciliation"]
        assert rec["service_income"] == pytest.approx(150000, abs=1)
        assert rec["interest_income"] == pytest.approx(45000, abs=1)
        assert rec["transformation_net"] == pytest.approx(20000, abs=1)
        assert rec["inventory_adjustment_net"] == pytest.approx(12000, abs=1)
        assert rec["tp_adjustment_net"] == pytest.approx(30000, abs=1)
        # 5a linea (Modelo L #65): sin oversell en esta fixture debe ser 0
        assert rec["oversell_cost_adjustment"] == pytest.approx(0, abs=1)
        # 7a linea (venta de activos): sin ventas en esta fixture debe ser 0
        assert rec["asset_sale_gain"] == pytest.approx(0, abs=1)

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


class TestDECommissionProration:

    def test_de_commission_goes_to_pasamano_section(
        self, client, org_headers, bu_data_with_de_commission,
    ):
        """Comision de DP $1M NO se prorratea a las UN de bodega — va a la
        seccion Pasa Mano (antes contaminaba Cobre/Chatarra, fuga #2 del plan).
        """
        resp = client.get(
            "/api/v1/reports/profitability-by-business-unit",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()

        cobre = next((bu for bu in data["business_units"] if bu["business_unit_name"] == "Cobre"), None)
        chatarra = next((bu for bu in data["business_units"] if bu["business_unit_name"] == "Chatarra"), None)
        assert cobre is not None
        assert chatarra is not None

        # Bodega: solo la comision de la venta de bodega ($60K, en Cobre)
        assert cobre["sale_commissions"] == 60000.0
        assert chatarra["sale_commissions"] == 0.0

        # Pasa Mano: comision DP de este fixture ($1M) + la del bu_data base ($30K)
        assert data["double_entry"]["commissions"] == pytest.approx(1030000.0, abs=1)


class TestEdgeCases:

    def test_overhead_rate_zero_when_no_purchases(self, client, org_headers, bu_data):
        """UN sin compras en periodo tiene overhead_rate = 0."""
        resp = client.get(
            "/api/v1/reports/real-cost-by-material",
            params={"date_from": "2099-01-01", "date_to": "2099-12-31"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        for bu in data["business_units"]:
            assert bu["overhead_rate"] == 0
            assert bu["kg_purchased"] == 0

    def test_profitability_empty_period_no_error(self, client, org_headers, bu_data):
        """Periodo sin compras ni ventas retorna 200 con lista vacia."""
        resp = client.get(
            "/api/v1/reports/profitability-by-business-unit",
            params={"date_from": "2099-01-01", "date_to": "2099-12-31"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["business_units"] == []
        assert data["totals"]["net_profit"] == 0


# ---------------------------------------------------------------------------
# Tests: P&L waste_loss (perdida por merma)
# ---------------------------------------------------------------------------

class TestPnLWasteLoss:
    """Verificar que waste_loss aparece en P&L cuando hay transformaciones con merma."""

    def test_pnl_includes_waste_loss(self, client: TestClient, org_headers: dict, db_session: Session, test_organization):
        """P&L muestra waste_loss > 0 cuando hay transformacion con merma."""
        from app.models.material_transformation import MaterialTransformation
        from app.models.warehouse import Warehouse

        org_id = test_organization.id
        cat = MaterialCategory(name="Metales WL", organization_id=org_id)
        db_session.add(cat)
        db_session.flush()
        mat = Material(name="Cable", code="WL-SRC", category_id=cat.id, organization_id=org_id, current_stock=Decimal("100"), current_average_cost=Decimal("8000"))
        db_session.add(mat)
        db_session.flush()
        wh = Warehouse(name="Bodega WL", organization_id=org_id, is_active=True)
        db_session.add(wh)
        db_session.flush()

        # Crear transformacion con merma directamente en BD
        trans = MaterialTransformation(
            organization_id=org_id,
            transformation_number=9001,
            date=datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc),
            source_material_id=mat.id,
            source_warehouse_id=wh.id,
            source_quantity=Decimal("100"),
            source_unit_cost=Decimal("8000"),
            source_total_value=Decimal("800000"),
            waste_quantity=Decimal("10"),
            waste_value=Decimal("80000"),
            cost_distribution="proportional_weight",
            value_difference=Decimal("0"),
            reason="Test waste loss",
            status="confirmed",
        )
        db_session.add(trans)
        db_session.commit()

        resp = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["waste_loss"] == 80000.0
        # waste_loss reduce utilidad bruta
        assert data["total_gross_profit"] == -80000.0  # sin ventas, solo merma

    def test_pnl_no_waste_loss_without_waste(self, client: TestClient, org_headers: dict, db_session: Session, test_organization):
        """P&L muestra waste_loss = 0 cuando transformacion sin merma."""
        from app.models.material_transformation import MaterialTransformation
        from app.models.warehouse import Warehouse

        org_id = test_organization.id
        cat = MaterialCategory(name="Metales NW", organization_id=org_id)
        db_session.add(cat)
        db_session.flush()
        mat = Material(name="Acero", code="NW-SRC", category_id=cat.id, organization_id=org_id, current_stock=Decimal("100"), current_average_cost=Decimal("5000"))
        db_session.add(mat)
        db_session.flush()
        wh = Warehouse(name="Bodega NW", organization_id=org_id, is_active=True)
        db_session.add(wh)
        db_session.flush()

        trans = MaterialTransformation(
            organization_id=org_id,
            transformation_number=9002,
            date=datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc),
            source_material_id=mat.id,
            source_warehouse_id=wh.id,
            source_quantity=Decimal("100"),
            source_unit_cost=Decimal("5000"),
            source_total_value=Decimal("500000"),
            waste_quantity=Decimal("0"),
            waste_value=Decimal("0"),
            cost_distribution="proportional_weight",
            value_difference=Decimal("0"),
            reason="Test waste loss",
            status="confirmed",
        )
        db_session.add(trans)
        db_session.commit()

        resp = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["waste_loss"] == 0.0


# ---------------------------------------------------------------------------
# Tests: P&L adjustment_net (ajustes de inventario)
# ---------------------------------------------------------------------------

class TestPnLAdjustmentNet:
    """Verificar que adjustment_net aparece en P&L para ajustes de inventario."""

    def _make_adjustment(self, db_session, org_id, adj_type, quantity, unit_cost, status="confirmed", reason="Test adjustment"):
        from app.models.inventory_adjustment import InventoryAdjustment
        from app.models.warehouse import Warehouse
        adj = InventoryAdjustment(
            organization_id=org_id,
            adjustment_number=abs(hash(f"{adj_type}{quantity}{reason}")) % 90000 + 10000,
            date=datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc),
            adjustment_type=adj_type,
            material_id=self._mat_id,
            warehouse_id=self._wh_id,
            previous_stock=Decimal("100"),
            quantity=Decimal(str(quantity)),
            new_stock=Decimal("100") + Decimal(str(quantity)),
            unit_cost=Decimal(str(unit_cost)),
            total_value=abs(Decimal(str(quantity)) * Decimal(str(unit_cost))),
            reason=reason,
            status=status,
        )
        db_session.add(adj)
        return adj

    def _setup_material(self, db_session, org_id):
        from app.models.warehouse import Warehouse
        cat = MaterialCategory(name="Metales ADJ", organization_id=org_id)
        db_session.add(cat)
        db_session.flush()
        mat = Material(name="Cobre ADJ", code="ADJ-001", category_id=cat.id, organization_id=org_id, current_stock=Decimal("100"), current_average_cost=Decimal("5000"))
        db_session.add(mat)
        db_session.flush()
        wh = Warehouse(name="Bodega ADJ", organization_id=org_id, is_active=True)
        db_session.add(wh)
        db_session.flush()
        self._mat_id = mat.id
        self._wh_id = wh.id

    def test_pnl_decrease_negative(self, client: TestClient, org_headers: dict, db_session: Session, test_organization):
        """Decrease adjustment aparece como perdida en P&L."""
        self._setup_material(db_session, test_organization.id)
        self._make_adjustment(db_session, test_organization.id, "decrease", -20, 5000)
        db_session.commit()

        resp = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        # quantity=-20, total_value=100000 → adjustment_net = -100000
        assert resp.json()["adjustment_net"] == -100000.0

    def test_pnl_increase_positive(self, client: TestClient, org_headers: dict, db_session: Session, test_organization):
        """Increase adjustment aparece como ganancia en P&L."""
        self._setup_material(db_session, test_organization.id)
        self._make_adjustment(db_session, test_organization.id, "increase", 10, 5000)
        db_session.commit()

        resp = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        # quantity=10, total_value=50000 → adjustment_net = +50000
        assert resp.json()["adjustment_net"] == 50000.0

    def test_pnl_no_adjustments_zero(self, client: TestClient, org_headers: dict):
        """Sin ajustes, adjustment_net = 0."""
        resp = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["adjustment_net"] == 0.0

    def test_pnl_net_increase_and_decrease(self, client: TestClient, org_headers: dict, db_session: Session, test_organization):
        """Increase + decrease = neto."""
        self._setup_material(db_session, test_organization.id)
        self._make_adjustment(db_session, test_organization.id, "increase", 10, 5000)  # +50000
        self._make_adjustment(db_session, test_organization.id, "decrease", -30, 5000)  # -150000
        db_session.commit()

        resp = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        # neto = 50000 - 150000 = -100000
        assert resp.json()["adjustment_net"] == -100000.0

    def test_pnl_annulled_excluded(self, client: TestClient, org_headers: dict, db_session: Session, test_organization):
        """Ajustes anulados no cuentan en P&L."""
        self._setup_material(db_session, test_organization.id)
        self._make_adjustment(db_session, test_organization.id, "decrease", -50, 5000, status="annulled")
        db_session.commit()

        resp = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["adjustment_net"] == 0.0

    def test_pnl_migration_seed_excluded(self, client: TestClient, org_headers: dict, db_session: Session, test_organization):
        """Seeds del script de migracion (reason 'Carga inicial migracion %') no cuentan en P&L.

        El script siembra stock via adjustment_increase para que MaterialCostHistory
        quede sembrado, pero ese inventario representa patrimonio inicial (absorbido
        en los saldos de los socios), no una ganancia operativa. Se excluye por reason.
        """
        self._setup_material(db_session, test_organization.id)
        # Seed de migracion: NO debe contar
        self._make_adjustment(
            db_session, test_organization.id, "increase", 100, 5000,
            reason="Carga inicial migracion MetaRecycling",
        )  # total_value = 500000
        # Ajuste operativo real: SI cuenta
        self._make_adjustment(
            db_session, test_organization.id, "increase", 10, 5000,
            reason="Hallazgo en bodega",
        )  # total_value = 50000
        db_session.commit()

        resp = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        # Solo cuenta el operativo (50000), no el seed (500000)
        assert resp.json()["adjustment_net"] == 50000.0


# ===========================================================================
# Reporte de Gastos (agrupacion flexible UN/Categoria)
# ===========================================================================


@pytest.fixture
def expenses_data(db_session: Session, test_organization, test_user):
    """Dataset para tests del reporte de gastos.

    Replica la estructura de bu_data, anade categoria padre/hijo y un
    gasto legacy (is_direct_expense=True con UN NULL).
    """
    org_id = test_organization.id
    now = datetime.now(tz=timezone.utc)

    bu_cobre = BusinessUnit(name="UNCobre", organization_id=org_id, is_active=True)
    bu_chatarra = BusinessUnit(name="UNChatarra", organization_id=org_id, is_active=True)
    db_session.add_all([bu_cobre, bu_chatarra])
    db_session.flush()

    cat_metales = MaterialCategory(name="Metales E", organization_id=org_id, is_active=True)
    db_session.add(cat_metales)
    db_session.flush()

    cat_servicios = ExpenseCategory(
        name="Servicios", organization_id=org_id,
        is_direct_expense=False, is_active=True,
    )
    db_session.add(cat_servicios)
    db_session.flush()

    cat_internet = ExpenseCategory(
        name="Internet", organization_id=org_id,
        parent_id=cat_servicios.id,
        is_direct_expense=False, is_active=True,
    )
    cat_telefono = ExpenseCategory(
        name="Telefono", organization_id=org_id,
        parent_id=cat_servicios.id,
        is_direct_expense=False, is_active=True,
    )
    cat_nomina = ExpenseCategory(
        name="Nomina E", organization_id=org_id,
        is_direct_expense=True, is_active=True,
    )
    db_session.add_all([cat_internet, cat_telefono, cat_nomina])
    db_session.flush()

    mat_cobre = Material(
        code="CU-E", name="Cobre E", organization_id=org_id,
        category_id=cat_metales.id, default_unit="kg",
        business_unit_id=bu_cobre.id,
        current_stock=Decimal("500"), current_stock_liquidated=Decimal("500"),
        current_stock_transit=Decimal("0"), current_average_cost=Decimal("8000"),
        is_active=True,
    )
    mat_chatarra = Material(
        code="CH-E", name="Chatarra E", organization_id=org_id,
        category_id=cat_metales.id, default_unit="kg",
        business_unit_id=bu_chatarra.id,
        current_stock=Decimal("1000"), current_stock_liquidated=Decimal("1000"),
        current_stock_transit=Decimal("0"), current_average_cost=Decimal("1200"),
        is_active=True,
    )
    db_session.add_all([mat_cobre, mat_chatarra])
    db_session.flush()

    wh = Warehouse(name="Bodega E", organization_id=org_id, is_active=True)
    cuenta = MoneyAccount(
        name="Caja E", account_type="cash", organization_id=org_id,
        current_balance=Decimal("50000000"), is_active=True,
    )
    db_session.add_all([wh, cuenta])
    db_session.flush()

    supplier_cat = ThirdPartyCategory(
        name="Prov Mat E", behavior_type="material_supplier", organization_id=org_id,
    )
    db_session.add(supplier_cat)
    db_session.flush()
    supplier = ThirdParty(
        name="Prov E", organization_id=org_id, current_balance=Decimal("0"), is_active=True,
    )
    db_session.add(supplier)
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(
        third_party_id=supplier.id, category_id=supplier_cat.id,
    ))
    db_session.flush()

    # Compras: Cobre $1.6M, Chatarra $0.6M (base de prorrateo)
    compra = Purchase(
        organization_id=org_id, purchase_number=910,
        supplier_id=supplier.id, date=now, status="liquidated",
        liquidated_at=now, total_amount=Decimal("2200000"),
    )
    db_session.add(compra)
    db_session.flush()
    db_session.add(PurchaseLine(
        purchase_id=compra.id, material_id=mat_cobre.id, warehouse_id=wh.id,
        quantity=Decimal("200"), unit_price=Decimal("8000"), total_price=Decimal("1600000"),
    ))
    db_session.add(PurchaseLine(
        purchase_id=compra.id, material_id=mat_chatarra.id, warehouse_id=wh.id,
        quantity=Decimal("500"), unit_price=Decimal("1200"), total_price=Decimal("600000"),
    ))
    db_session.flush()

    # Gastos del periodo:
    # 1. DIRECTO Chatarra, cat=Internet (subcategoria) — $300K
    g_directo = MoneyMovement(
        organization_id=org_id, movement_number=910,
        date=now, movement_type="expense", amount=Decimal("300000"),
        account_id=cuenta.id, description="Internet planta Chatarra",
        expense_category_id=cat_internet.id,
        business_unit_id=bu_chatarra.id,
        status="confirmed",
    )
    # 2. COMPARTIDO Cobre+Chatarra, cat=Telefono — $200K
    g_compartido = MoneyMovement(
        organization_id=org_id, movement_number=911,
        date=now, movement_type="expense", amount=Decimal("200000"),
        account_id=cuenta.id, description="Telefono prensa",
        expense_category_id=cat_telefono.id,
        applicable_business_unit_ids=[str(bu_cobre.id), str(bu_chatarra.id)],
        status="confirmed",
    )
    # 3. GENERAL (todos NULL), cat padre Servicios — $1M
    g_general = MoneyMovement(
        organization_id=org_id, movement_number=912,
        date=now, movement_type="expense", amount=Decimal("1000000"),
        account_id=cuenta.id, description="Servicio general",
        expense_category_id=cat_servicios.id,
        status="confirmed",
    )
    # 4. LEGACY: is_direct_expense=True + UN NULL → unassigned directo — $400K
    g_legacy = MoneyMovement(
        organization_id=org_id, movement_number=913,
        date=now, movement_type="expense", amount=Decimal("400000"),
        account_id=cuenta.id, description="Nomina legacy sin UN",
        expense_category_id=cat_nomina.id,
        status="confirmed",
    )
    # 5. ANULADO — no debe contar
    g_anulado = MoneyMovement(
        organization_id=org_id, movement_number=914,
        date=now, movement_type="expense", amount=Decimal("999999"),
        account_id=cuenta.id, description="Anulado",
        expense_category_id=cat_servicios.id,
        business_unit_id=bu_cobre.id,
        status="annulled",
    )
    db_session.add_all([g_directo, g_compartido, g_general, g_legacy, g_anulado])
    db_session.commit()

    return {
        "bu_cobre": bu_cobre,
        "bu_chatarra": bu_chatarra,
        "cat_servicios": cat_servicios,
        "cat_internet": cat_internet,
        "cat_telefono": cat_telefono,
        "cat_nomina": cat_nomina,
        "g_directo": g_directo,
        "g_compartido": g_compartido,
        "g_general": g_general,
        "g_legacy": g_legacy,
        # 300K + 200K + 1M + 400K
        "expected_total": Decimal("1900000"),
    }


class TestExpensesReport:

    def test_endpoint_returns_200(self, client, org_headers, expenses_data):
        resp = client.get(
            "/api/v1/reports/expenses",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "groups" in data
        assert "total" in data

    def test_total_matches_pnl(self, client, org_headers, expenses_data):
        """Suma global == operating_expenses del P&L."""
        resp_exp = client.get(
            "/api/v1/reports/expenses",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        resp_pnl = client.get(
            "/api/v1/reports/profit-and-loss",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        total_expenses = resp_exp.json()["total"]
        operating_expenses = resp_pnl.json()["operating_expenses"]
        assert abs(total_expenses - operating_expenses) < 1

    def test_total_matches_profitability_bu_sum(self, client, org_headers, expenses_data):
        """Suma global == Σ (directos + compartidos + generales) de Rentabilidad por UN."""
        resp_exp = client.get(
            "/api/v1/reports/expenses",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        resp_pbu = client.get(
            "/api/v1/reports/profitability-by-business-unit",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        total_expenses = resp_exp.json()["total"]
        bu_sum = sum(
            bu["direct_expenses"] + bu["shared_expenses"] + bu["general_expenses"]
            for bu in resp_pbu.json()["business_units"]
        )
        assert abs(total_expenses - bu_sum) < 1

    def test_group_by_bu_shared_prorated(self, client, org_headers, expenses_data):
        """Compartido $200K Cobre+Chatarra: 1.6/2.2 a Cobre, 0.6/2.2 a Chatarra."""
        resp = client.get(
            "/api/v1/reports/expenses",
            params={
                "date_from": "2026-01-01", "date_to": "2026-12-31",
                "group_by": "bu",
            },
            headers=org_headers,
        )
        assert resp.status_code == 200
        groups = resp.json()["groups"]
        # UN Cobre: 200K * 1.6/2.2 + 1M * 1.6/2.2 ≈ 872,727
        # UN Chatarra: 300K + 200K * 0.6/2.2 + 1M * 0.6/2.2 ≈ 627,272
        # Sin Asignar: 400K (legacy)
        cobre = next(g for g in groups if g["label"] == "UNCobre")
        chatarra = next(g for g in groups if g["label"] == "UNChatarra")
        sin_asignar = next(g for g in groups if g["label"] == "Sin Asignar")
        assert abs(cobre["total"] - 872727.27) < 1
        assert abs(chatarra["total"] - 627272.73) < 1
        assert abs(sin_asignar["total"] - 400000) < 1

    def test_legacy_direct_unassigned_not_prorated(self, client, org_headers, expenses_data):
        """is_direct_expense=True + UN NULL → unassigned directo (no prorrateado)."""
        resp = client.get(
            "/api/v1/reports/expenses",
            params={
                "date_from": "2026-01-01", "date_to": "2026-12-31",
                "group_by": "bu",
            },
            headers=org_headers,
        )
        groups = resp.json()["groups"]
        sin_asignar = next(g for g in groups if g["label"] == "Sin Asignar")
        assert sin_asignar["total"] == 400000.0
        assert sin_asignar["has_shared_allocations"] is False

    def test_filter_by_bu(self, client, org_headers, expenses_data):
        """Filtrar por UN Cobre: solo aparece Cobre."""
        bu_cobre_id = str(expenses_data["bu_cobre"].id)
        resp = client.get(
            "/api/v1/reports/expenses",
            params={
                "date_from": "2026-01-01", "date_to": "2026-12-31",
                "group_by": "bu",
                "business_unit_id": [bu_cobre_id],
            },
            headers=org_headers,
        )
        assert resp.status_code == 200
        groups = resp.json()["groups"]
        assert len(groups) == 1
        assert groups[0]["label"] == "UNCobre"

    def test_filter_by_parent_category_includes_children(
        self, client, org_headers, expenses_data,
    ):
        """Filtrar por categoria padre incluye gastos en hijas."""
        cat_servicios_id = str(expenses_data["cat_servicios"].id)
        resp = client.get(
            "/api/v1/reports/expenses",
            params={
                "date_from": "2026-01-01", "date_to": "2026-12-31",
                "group_by": "category",
                "expense_category_id": [cat_servicios_id],
            },
            headers=org_headers,
        )
        assert resp.status_code == 200
        groups = resp.json()["groups"]
        servicios = next(g for g in groups if g["label"] == "Servicios")
        # Total = 300K (Internet) + 200K (Telefono) + 1M (directo padre) = 1.5M
        assert abs(servicios["total"] - 1500000) < 1

    def test_hierarchy_parent_aggregates_children(self, client, org_headers, expenses_data):
        """Padre agrega montos de hijas en group_by=category."""
        resp = client.get(
            "/api/v1/reports/expenses",
            params={
                "date_from": "2026-01-01", "date_to": "2026-12-31",
                "group_by": "category",
            },
            headers=org_headers,
        )
        groups = resp.json()["groups"]
        servicios = next(g for g in groups if g["label"] == "Servicios")
        assert abs(servicios["total"] - 1500000) < 1
        child_labels = {c["label"] for c in servicios["children"]}
        assert "Internet" in child_labels
        assert "Telefono" in child_labels

    def test_excludes_annulled(self, client, org_headers, expenses_data):
        """Gastos anulados no aparecen en el reporte."""
        resp = client.get(
            "/api/v1/reports/expenses",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        assert abs(resp.json()["total"] - float(expenses_data["expected_total"])) < 1

    def test_summary_breakdown_sums_to_total(self, client, org_headers, expenses_data):
        """total == total_direct + total_shared + total_general; movement_count == 4."""
        resp = client.get(
            "/api/v1/reports/expenses",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # Las 4 metricas deben existir
        assert "total_direct" in data
        assert "total_shared" in data
        assert "total_general" in data
        assert "movement_count" in data
        # Suma cuadra con total
        breakdown_sum = data["total_direct"] + data["total_shared"] + data["total_general"]
        assert abs(data["total"] - breakdown_sum) < 1
        # Conteo: 4 gastos no anulados (directo, compartido, general, legacy)
        assert data["movement_count"] == 4
        # Directo: 300K (chatarra) + 400K (legacy) = 700K
        assert abs(data["total_direct"] - 700000) < 1
        # Compartido: 200K (telefono entre cobre+chatarra)
        assert abs(data["total_shared"] - 200000) < 1
        # General: 1M (servicios padre)
        assert abs(data["total_general"] - 1000000) < 1

    def test_detail_unassigned_returns_legacy(self, client, org_headers, expenses_data):
        """Detalle del bucket Sin Asignar: solo el movimiento legacy."""
        resp = client.get(
            "/api/v1/reports/expenses/detail",
            params={
                "date_from": "2026-01-01", "date_to": "2026-12-31",
                "business_unit_unassigned": True,
            },
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] == 1
        assert abs(data["total_allocated"] - 400000) < 1
        assert data["items"][0]["allocation_type"] == "direct"
        assert data["items"][0]["movement_id"] == str(expenses_data["g_legacy"].id)


class TestExpensesReportRBAC:

    def _make_user_with_role(
        self, db_session, test_organization, role_name: str, email: str,
    ):
        from app.models.role import Role
        from app.models.user import User, OrganizationMember

        u = User(email=email, hashed_password="x", full_name=email, is_active=True)
        db_session.add(u)
        db_session.flush()
        role = db_session.query(Role).filter(
            Role.organization_id == test_organization.id,
            Role.name == role_name,
            Role.is_system_role == True,
        ).first()
        assert role is not None, f"Rol {role_name} no encontrado"
        db_session.add(OrganizationMember(
            user_id=u.id,
            organization_id=test_organization.id,
            role_id=role.id,
        ))
        db_session.commit()
        return u

    def test_viewer_can_access(
        self, client, db_session, test_organization, expenses_data,
    ):
        """Rol viewer (con reports.view_expenses) puede acceder."""
        from app.core.security import create_access_token

        user = self._make_user_with_role(
            db_session, test_organization, "viewer", "viewer-exp@test.com",
        )
        token = create_access_token(data={"sub": str(user.id)})
        resp = client.get(
            "/api/v1/reports/expenses",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers={
                "Authorization": f"Bearer {token}",
                "X-Organization-ID": str(test_organization.id),
            },
        )
        assert resp.status_code == 200

    def test_planillador_denied(
        self, client, db_session, test_organization, expenses_data,
    ):
        """Rol planillador (sin reports.view_expenses) recibe 403."""
        from app.core.security import create_access_token

        user = self._make_user_with_role(
            db_session, test_organization, "planillador", "plan-exp@test.com",
        )
        token = create_access_token(data={"sub": str(user.id)})
        resp = client.get(
            "/api/v1/reports/expenses",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers={
                "Authorization": f"Bearer {token}",
                "X-Organization-ID": str(test_organization.id),
            },
        )
        assert resp.status_code == 403
