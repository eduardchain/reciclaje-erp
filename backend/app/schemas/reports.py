"""
Schemas de respuesta para reportes y dashboard.

Todos los campos monetarios usan float en la respuesta.
Los calculos internos se hacen en Decimal para precision.
"""
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Shared / Reusable
# ---------------------------------------------------------------------------

class DailyTrendItem(BaseModel):
    """Punto de tendencia diaria."""
    date: date
    total_amount: float
    count: int


class MetricCard(BaseModel):
    """KPI card con comparacion vs periodo anterior."""
    current_value: float
    previous_value: float
    change_percentage: Optional[float] = None  # None si previous == 0


# ---------------------------------------------------------------------------
# Dashboard (Section 20.1)
# ---------------------------------------------------------------------------

class DashboardMetrics(BaseModel):
    total_sales: MetricCard
    total_purchases: MetricCard
    gross_profit: MetricCard
    cash_balance: MetricCard
    pending_receivables: MetricCard
    pending_payables: MetricCard


class MaterialProfitSummary(BaseModel):
    material_id: UUID
    material_name: str
    total_profit: float
    margin_percentage: float


class SupplierVolumeSummary(BaseModel):
    supplier_id: UUID
    supplier_name: str
    total_amount: float
    total_quantity: float


class CustomerRevenueSummary(BaseModel):
    customer_id: UUID
    customer_name: str
    total_amount: float
    total_profit: float


class DashboardAlert(BaseModel):
    alert_type: str
    severity: str  # 'warning' | 'info'
    message: str
    count: Optional[int] = None


class DashboardResponse(BaseModel):
    as_of: datetime
    period_from: date
    period_to: date
    metrics: DashboardMetrics
    top_materials_by_profit: list[MaterialProfitSummary]
    top_suppliers_by_volume: list[SupplierVolumeSummary]
    top_customers_by_revenue: list[CustomerRevenueSummary]
    alerts: list[DashboardAlert]


# ---------------------------------------------------------------------------
# P&L - Estado de Resultados (Section 18.1)
# ---------------------------------------------------------------------------

class ExpenseCategoryBreakdown(BaseModel):
    category_id: Optional[UUID] = None
    category_name: str
    is_direct_expense: bool
    total_amount: float
    source_type: str = "expense"  # expense, provision_expense, expense_accrual, deferred_expense


class ProfitAndLossResponse(BaseModel):
    period_from: date
    period_to: date

    # Ingresos
    sales_revenue: float
    sales_count: int
    service_income: float

    # Costo de ventas (metodo directo)
    cost_of_goods_sold: float

    # Utilidad bruta ventas
    gross_profit_sales: float
    gross_margin_sales: float

    # Utilidad Pasa Mano (linea separada)
    double_entry_profit: float
    double_entry_count: int

    # Ganancia/Perdida por transformaciones
    transformation_profit: float = 0.0
    transformation_count: int = 0

    # Utilidad bruta total
    total_gross_profit: float

    # Gastos operacionales
    operating_expenses: float
    commissions_paid: float

    # Utilidad neta
    net_profit: float
    net_margin: float

    # Detalle gastos
    expenses_by_category: list[ExpenseCategoryBreakdown]


# ---------------------------------------------------------------------------
# Cash Flow - Flujo de Caja (Section 18.2)
# ---------------------------------------------------------------------------

class CashFlowInflows(BaseModel):
    sale_collections: float
    customer_collections: float
    service_income: float
    capital_injections: float
    advance_collections: float = 0.0
    total: float


class CashFlowOutflows(BaseModel):
    purchase_payments: float
    supplier_payments: float
    expenses: float
    commission_payments: float
    capital_returns: float
    provision_deposits: float = 0.0
    deferred_fundings: float = 0.0
    advance_payments: float = 0.0
    asset_payments: float = 0.0
    total: float


class CashFlowResponse(BaseModel):
    period_from: date
    period_to: date
    opening_balance: float
    inflows: CashFlowInflows
    total_inflows: float
    outflows: CashFlowOutflows
    total_outflows: float
    net_flow: float
    closing_balance: float


# ---------------------------------------------------------------------------
# Balance Sheet - Balance General (Section 18.3)
# ---------------------------------------------------------------------------

class BalanceSheetAssets(BaseModel):
    cash_and_bank: float
    accounts_receivable: float
    inventory: float
    prepaid_expenses: float = 0.0
    provision_funds: float = 0.0
    fixed_assets: float = 0.0
    total: float


class BalanceSheetLiabilities(BaseModel):
    accounts_payable: float
    investor_debt: float
    liability_debt: float = 0.0
    total: float


class BalanceSheetResponse(BaseModel):
    as_of_date: date
    assets: BalanceSheetAssets
    total_assets: float
    liabilities: BalanceSheetLiabilities
    total_liabilities: float
    equity: float


# ---------------------------------------------------------------------------
# Purchase Report (Section 19.1)
# ---------------------------------------------------------------------------

class PurchaseBySupplier(BaseModel):
    supplier_id: UUID
    supplier_name: str
    total_amount: float
    total_quantity: float
    purchase_count: int


class PurchaseByMaterial(BaseModel):
    material_id: UUID
    material_code: str
    material_name: str
    total_amount: float
    total_quantity: float
    average_unit_price: float


class PurchaseReportResponse(BaseModel):
    period_from: date
    period_to: date
    total_amount: float
    total_quantity: float
    purchase_count: int
    average_per_purchase: float
    by_supplier: list[PurchaseBySupplier]
    by_material: list[PurchaseByMaterial]
    daily_trend: list[DailyTrendItem]


# ---------------------------------------------------------------------------
# Sales Report (Section 19.2)
# ---------------------------------------------------------------------------

class SaleByCustomer(BaseModel):
    customer_id: UUID
    customer_name: str
    total_amount: float
    total_quantity: float
    sale_count: int
    total_profit: float


class SaleByMaterial(BaseModel):
    material_id: UUID
    material_code: str
    material_name: str
    total_amount: float
    total_quantity: float
    total_cost: float
    total_profit: float
    margin_percentage: float


class SalesReportResponse(BaseModel):
    period_from: date
    period_to: date
    total_revenue: float
    total_quantity: float
    sale_count: int
    total_cost: float
    total_profit: float
    overall_margin: float
    by_customer: list[SaleByCustomer]
    by_material: list[SaleByMaterial]
    daily_trend: list[DailyTrendItem]


# ---------------------------------------------------------------------------
# Margin Analysis (Section 19.3)
# ---------------------------------------------------------------------------

class MaterialMargin(BaseModel):
    material_id: UUID
    material_code: str
    material_name: str
    category_name: Optional[str] = None
    # Lado compra
    total_purchased_qty: float
    total_purchased_amount: float
    avg_purchase_price: float
    # Lado venta (solo ventas normales)
    total_sold_qty: float
    total_sold_revenue: float
    total_sold_cost: float
    avg_sale_price: float
    # Margenes
    gross_profit: float
    margin_percentage: float
    # Contribucion doble partida
    double_entry_qty: float
    double_entry_profit: float


class MarginAnalysisResponse(BaseModel):
    period_from: date
    period_to: date
    overall_margin: float
    materials: list[MaterialMargin]


# ---------------------------------------------------------------------------
# Third Party Balances
# ---------------------------------------------------------------------------

class SupplierBalance(BaseModel):
    id: UUID
    name: str
    balance: float


class CustomerBalance(BaseModel):
    id: UUID
    name: str
    balance: float


class ThirdPartyBalancesResponse(BaseModel):
    total_payable: float
    total_receivable: float
    net_position: float
    total_advances_paid: float  # Proveedores con balance > 0 (nos deben)
    total_advances_received: float  # Clientes con balance < 0 (les debemos)
    suppliers: list[SupplierBalance]
    customers: list[CustomerBalance]


# ---------------------------------------------------------------------------
# Treasury Dashboard
# ---------------------------------------------------------------------------

class AccountSummary(BaseModel):
    id: UUID
    name: str
    account_type: str
    current_balance: float


class ProvisionSummary(BaseModel):
    id: UUID
    name: str
    provision_type: Optional[str] = None
    current_balance: float
    available_funds: float  # abs(balance) si negativo, 0 si positivo


class RecentMovementItem(BaseModel):
    id: UUID
    movement_number: int
    date: datetime
    movement_type: str
    amount: float
    description: str
    account_name: Optional[str] = None
    third_party_name: Optional[str] = None


# ---------------------------------------------------------------------------
# Audit Balances (Auditoria de saldos)
# ---------------------------------------------------------------------------

class AccountAuditItem(BaseModel):
    """Resultado de auditoria para una cuenta de dinero."""
    id: UUID
    name: str
    account_type: str
    stored_balance: float
    calculated_balance: float
    difference: float
    status: str  # "ok" | "mismatch"


class ThirdPartyAuditItem(BaseModel):
    """Resultado de auditoria para un tercero."""
    id: UUID
    name: str
    roles: list[str]
    stored_balance: float
    calculated_balance: float
    difference: float
    status: str  # "ok" | "mismatch"


class AuditSummary(BaseModel):
    """Resumen de auditoria."""
    total_accounts: int
    accounts_ok: int
    accounts_mismatch: int
    total_third_parties: int
    third_parties_ok: int
    third_parties_mismatch: int


class AuditBalancesResponse(BaseModel):
    """Respuesta completa de auditoria de saldos."""
    accounts: list[AccountAuditItem]
    third_parties: list[ThirdPartyAuditItem]
    summary: AuditSummary


class TreasuryDashboardResponse(BaseModel):
    # Cuentas agrupadas por tipo
    cash_accounts: list[AccountSummary]
    bank_accounts: list[AccountSummary]
    digital_accounts: list[AccountSummary]
    total_cash: float
    total_bank: float
    total_digital: float
    total_all_accounts: float
    # CxC / CxP
    total_receivable: float
    total_payable: float
    net_position: float
    # Provisiones
    provisions: list[ProvisionSummary]
    total_provision_available: float
    # Mes en curso (MTD)
    mtd_income: float
    mtd_expense: float
    # Ultimos movimientos
    recent_movements: list[RecentMovementItem]
