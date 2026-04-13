"""
Schemas de respuesta para reportes y dashboard.

Todos los campos monetarios usan float en la respuesta.
Los calculos internos se hacen en Decimal para precision.
"""
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_serializer


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

    # Perdida por merma
    waste_loss: float = 0.0

    # Ajustes de inventario (positivo=ganancia, negativo=perdida)
    adjustment_net: float = 0.0

    # Ajustes de terceros
    tp_adjustment_loss: float = 0.0
    tp_adjustment_gain: float = 0.0

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
    generic_collections: float = 0.0
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
    generic_payments: float = 0.0
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
    advances: float = 0.0
    investor_receivable: float = 0.0
    prepaid_expenses: float = 0.0
    provision_funds: float = 0.0
    fixed_assets: float = 0.0
    total: float


class BalanceSheetLiabilities(BaseModel):
    accounts_payable: float
    investor_debt: float
    liability_debt: float = 0.0
    service_provider_payable: float = 0.0
    customer_advances: float = 0.0
    provision_obligations: float = 0.0
    generic_payable: float = 0.0
    total: float


class BalanceSheetResponse(BaseModel):
    as_of_date: date
    assets: BalanceSheetAssets
    total_assets: float
    liabilities: BalanceSheetLiabilities
    total_liabilities: float
    equity: float
    accumulated_profit: float = 0.0
    distributed_profit: float = 0.0

    @field_serializer("as_of_date")
    def serialize_as_of_date(self, v: date, _info) -> str:
        return f"{v.year:04d}-{v.month:02d}-{v.day:02d}T12:00:00Z"


# ---------------------------------------------------------------------------
# Balance Detallado (desglose por item)
# ---------------------------------------------------------------------------

class BalanceDetailedItem(BaseModel):
    id: str
    name: str
    balance: float = 0.0
    code: Optional[str] = None
    stock: Optional[float] = None
    avg_cost: Optional[float] = None
    current_value: Optional[float] = None
    purchase_value: Optional[float] = None
    accumulated_depreciation: Optional[float] = None
    investor_type: Optional[str] = None
    account_type: Optional[str] = None


class BalanceDetailedGroup(BaseModel):
    label: str
    total: float
    items: list[BalanceDetailedItem]


class BalanceDetailedSection(BaseModel):
    label: str
    total: float
    items: list[BalanceDetailedItem]
    groups: list[BalanceDetailedGroup] | None = None


class BalanceDetailedVerification(BaseModel):
    formula: str
    result: float
    is_balanced: bool


class BalanceDetailedResponse(BaseModel):
    as_of_date: date
    assets: dict[str, BalanceDetailedSection]
    total_assets: float
    liabilities: dict[str, BalanceDetailedSection]
    total_liabilities: float
    equity: float
    accumulated_profit: float = 0.0
    distributed_profit: float = 0.0
    equity_label: str = "Patrimonio (Capital + Utilidad Acumulada)"

    @field_serializer("as_of_date")
    def serialize_as_of_date(self, v: date, _info) -> str:
        return f"{v.year:04d}-{v.month:02d}-{v.day:02d}T12:00:00Z"
    verification: BalanceDetailedVerification


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


# ---------------------------------------------------------------------------
# Rentabilidad por Unidad de Negocio
# ---------------------------------------------------------------------------

class ExpenseByCategoryItem(BaseModel):
    """Desglose de gasto por categoria."""
    category_id: Optional[str] = None
    category_name: str
    amount: float


class BusinessUnitProfitability(BaseModel):
    """Rentabilidad de una Unidad de Negocio."""
    business_unit_id: Optional[str] = None
    business_unit_name: str
    # Compras (base prorrateo)
    purchases_total: float = 0
    purchases_weight_pct: float = 0
    # Ingresos
    sales_revenue: float = 0
    sales_cogs: float = 0
    sales_gross_profit: float = 0
    de_profit: float = 0
    total_gross_profit: float = 0
    # Gastos
    direct_expenses: float = 0
    shared_expenses: float = 0
    general_expenses: float = 0
    sale_commissions: float = 0
    total_expenses: float = 0
    # Desglose gastos directos por categoria
    direct_expenses_detail: list[ExpenseByCategoryItem] = []
    # Resultado
    net_profit: float = 0
    net_margin: float = 0


class ProfitabilityByBUResponse(BaseModel):
    """Respuesta del reporte de rentabilidad por UN."""
    period_from: date
    period_to: date
    business_units: list[BusinessUnitProfitability]
    totals: BusinessUnitProfitability


# ---------------------------------------------------------------------------
# Costo Real por Material
# ---------------------------------------------------------------------------

class MaterialRealCost(BaseModel):
    """Costo real de un material."""
    material_id: str
    material_code: str
    material_name: str
    average_cost: float
    overhead_rate: float
    real_cost: float


class BusinessUnitOverhead(BaseModel):
    """Overhead y materiales de una UN."""
    business_unit_id: Optional[str] = None
    business_unit_name: str
    total_expenses: float
    kg_purchased: float
    overhead_rate: float
    materials: list[MaterialRealCost]


class RealCostByMaterialResponse(BaseModel):
    """Respuesta del reporte de costo real."""
    period_from: date
    period_to: date
    business_units: list[BusinessUnitOverhead]
