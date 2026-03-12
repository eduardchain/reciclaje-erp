// --- Dashboard ---

export interface MetricCard {
  current_value: number;
  previous_value: number;
  change_percentage: number | null;
}

export interface DashboardMetrics {
  total_sales: MetricCard;
  total_purchases: MetricCard;
  gross_profit: MetricCard;
  cash_balance: MetricCard;
  pending_receivables: MetricCard;
  pending_payables: MetricCard;
}

export interface MaterialProfitSummary {
  material_id: string;
  material_name: string;
  total_profit: number;
  margin_percentage: number;
}

export interface SupplierVolumeSummary {
  supplier_id: string;
  supplier_name: string;
  total_amount: number;
  total_quantity: number;
}

export interface CustomerRevenueSummary {
  customer_id: string;
  customer_name: string;
  total_amount: number;
  total_profit: number;
}

export interface DashboardAlert {
  alert_type: string;
  severity: "warning" | "info";
  message: string;
  count: number | null;
}

export interface DashboardResponse {
  as_of: string;
  period_from: string;
  period_to: string;
  metrics: DashboardMetrics;
  top_materials_by_profit: MaterialProfitSummary[];
  top_suppliers_by_volume: SupplierVolumeSummary[];
  top_customers_by_revenue: CustomerRevenueSummary[];
  alerts: DashboardAlert[];
}

// --- P&L ---

export interface ExpenseCategoryBreakdown {
  category_id: string | null;
  category_name: string;
  is_direct_expense: boolean;
  total_amount: number;
  source_type: string; // expense, provision_expense, expense_accrual, deferred_expense
}

export interface ProfitAndLossResponse {
  period_from: string;
  period_to: string;
  sales_revenue: number;
  sales_count: number;
  service_income: number;
  cost_of_goods_sold: number;
  gross_profit_sales: number;
  gross_margin_sales: number;
  double_entry_profit: number;
  double_entry_count: number;
  transformation_profit: number;
  transformation_count: number;
  total_gross_profit: number;
  operating_expenses: number;
  commissions_paid: number;
  net_profit: number;
  net_margin: number;
  expenses_by_category: ExpenseCategoryBreakdown[];
}

// --- Cash Flow ---

export interface CashFlowInflows {
  sale_collections: number;
  customer_collections: number;
  service_income: number;
  capital_injections: number;
  advance_collections: number;
  total: number;
}

export interface CashFlowOutflows {
  purchase_payments: number;
  supplier_payments: number;
  expenses: number;
  commission_payments: number;
  capital_returns: number;
  provision_deposits: number;
  deferred_fundings: number;
  advance_payments: number;
  asset_payments: number;
  total: number;
}

export interface CashFlowResponse {
  period_from: string;
  period_to: string;
  opening_balance: number;
  inflows: CashFlowInflows;
  total_inflows: number;
  outflows: CashFlowOutflows;
  total_outflows: number;
  net_flow: number;
  closing_balance: number;
}

// --- Balance Sheet ---

export interface BalanceSheetAssets {
  cash_and_bank: number;
  accounts_receivable: number;
  inventory: number;
  prepaid_expenses: number;
  provision_funds: number;
  total: number;
}

export interface BalanceSheetLiabilities {
  accounts_payable: number;
  investor_debt: number;
  liability_debt: number;
  total: number;
}

export interface BalanceSheetResponse {
  as_of_date: string;
  assets: BalanceSheetAssets;
  total_assets: number;
  liabilities: BalanceSheetLiabilities;
  total_liabilities: number;
  equity: number;
}

// --- Purchase Report ---

export interface DailyTrendItem {
  date: string;
  total_amount: number;
  count: number;
}

export interface PurchaseBySupplier {
  supplier_id: string;
  supplier_name: string;
  total_amount: number;
  total_quantity: number;
  purchase_count: number;
}

export interface PurchaseByMaterial {
  material_id: string;
  material_code: string;
  material_name: string;
  total_amount: number;
  total_quantity: number;
  average_unit_price: number;
}

export interface PurchaseReportResponse {
  period_from: string;
  period_to: string;
  total_amount: number;
  total_quantity: number;
  purchase_count: number;
  average_per_purchase: number;
  by_supplier: PurchaseBySupplier[];
  by_material: PurchaseByMaterial[];
  daily_trend: DailyTrendItem[];
}

// --- Sales Report ---

export interface SaleByCustomer {
  customer_id: string;
  customer_name: string;
  total_amount: number;
  total_quantity: number;
  sale_count: number;
  total_profit: number;
}

export interface SaleByMaterial {
  material_id: string;
  material_code: string;
  material_name: string;
  total_amount: number;
  total_quantity: number;
  total_cost: number;
  total_profit: number;
  margin_percentage: number;
}

export interface SalesReportResponse {
  period_from: string;
  period_to: string;
  total_revenue: number;
  total_quantity: number;
  sale_count: number;
  total_cost: number;
  total_profit: number;
  overall_margin: number;
  by_customer: SaleByCustomer[];
  by_material: SaleByMaterial[];
  daily_trend: DailyTrendItem[];
}

// --- Margin Analysis ---

export interface MaterialMargin {
  material_id: string;
  material_code: string;
  material_name: string;
  category_name: string | null;
  total_purchased_qty: number;
  total_purchased_amount: number;
  avg_purchase_price: number;
  total_sold_qty: number;
  total_sold_revenue: number;
  total_sold_cost: number;
  avg_sale_price: number;
  gross_profit: number;
  margin_percentage: number;
  double_entry_qty: number;
  double_entry_profit: number;
}

export interface MarginAnalysisResponse {
  period_from: string;
  period_to: string;
  overall_margin: number;
  materials: MaterialMargin[];
}

// --- Audit Balances ---

export interface AccountAuditItem {
  id: string;
  name: string;
  account_type: string;
  stored_balance: number;
  calculated_balance: number;
  difference: number;
  status: string; // "ok" | "mismatch"
}

export interface ThirdPartyAuditItem {
  id: string;
  name: string;
  roles: string[];
  stored_balance: number;
  calculated_balance: number;
  difference: number;
  status: string; // "ok" | "mismatch"
}

export interface AuditSummary {
  total_accounts: number;
  accounts_ok: number;
  accounts_mismatch: number;
  total_third_parties: number;
  third_parties_ok: number;
  third_parties_mismatch: number;
}

export interface AuditBalancesResponse {
  accounts: AccountAuditItem[];
  third_parties: ThirdPartyAuditItem[];
  summary: AuditSummary;
}

// --- Treasury Dashboard ---

export interface AccountSummary {
  id: string;
  name: string;
  account_type: string;
  current_balance: number;
}

export interface ProvisionSummary {
  id: string;
  name: string;
  current_balance: number;
  available_funds: number;
}

export interface RecentMovementItem {
  id: string;
  date: string;
  movement_type: string;
  amount: number;
  description: string;
  account_name: string | null;
}

export interface TreasuryDashboardResponse {
  cash_accounts: AccountSummary[];
  bank_accounts: AccountSummary[];
  digital_accounts: AccountSummary[];
  total_cash: number;
  total_bank: number;
  total_digital: number;
  total_all_accounts: number;
  total_receivable: number;
  total_payable: number;
  net_position: number;
  provisions: ProvisionSummary[];
  total_provision_available: number;
  mtd_income: number;
  mtd_expense: number;
  recent_movements: RecentMovementItem[];
}

// --- Third Party Balances ---

export interface SupplierBalance {
  id: string;
  name: string;
  balance: number;
}

export interface CustomerBalance {
  id: string;
  name: string;
  balance: number;
}

export interface ThirdPartyBalancesResponse {
  total_payable: number;
  total_receivable: number;
  net_position: number;
  total_advances_paid: number;
  total_advances_received: number;
  suppliers: SupplierBalance[];
  customers: CustomerBalance[];
}
