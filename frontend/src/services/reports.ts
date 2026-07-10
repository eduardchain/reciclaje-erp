import apiClient from "./api";
import type {
  DashboardResponse,
  ProfitAndLossResponse,
  ProfitAndLossMonthlyResponse,
  CashFlowResponse,
  BalanceSheetResponse,
  BalanceDetailedResponse,
  PurchaseReportResponse,
  SalesReportResponse,
  MarginAnalysisResponse,
  ThirdPartyBalancesResponse,
  TreasuryDashboardResponse,
  AuditBalancesResponse,
  ProfitabilityByBUResponse,
  RealCostByMaterialResponse,
  ExpensesReportResponse,
  InactiveBalancesResponse,
  ExpensesGroupBy,
  ExpenseDetailResponse,
  DpFilter,
} from "@/types/reports";

interface DateRange {
  date_from: string;
  date_to: string;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function get<T>(url: string, params?: any): Promise<T> {
  const response = await apiClient.get<T>(url, params ? { params } : undefined);
  return response.data;
}

export const reportsService = {
  getDashboard: (params: DateRange) =>
    get<DashboardResponse>("/api/v1/reports/dashboard", params),

  getProfitAndLoss: (params: DateRange) =>
    get<ProfitAndLossResponse>("/api/v1/reports/profit-and-loss", params),

  getProfitAndLossMonthly: (params: DateRange & { cutoff_day?: number }) =>
    get<ProfitAndLossMonthlyResponse>("/api/v1/reports/profit-and-loss/monthly", params),

  getCashFlow: (params: DateRange) =>
    get<CashFlowResponse>("/api/v1/reports/cash-flow", params),

  getBalanceSheet: (params?: { as_of_date?: string }) =>
    get<BalanceSheetResponse>("/api/v1/reports/balance-sheet", params),

  getPurchaseReport: (params: DateRange & { dp_filter?: DpFilter }) =>
    get<PurchaseReportResponse>("/api/v1/reports/purchases", params),

  getSalesReport: (params: DateRange & { dp_filter?: DpFilter }) =>
    get<SalesReportResponse>("/api/v1/reports/sales", params),

  getMarginAnalysis: (params: DateRange) =>
    get<MarginAnalysisResponse>("/api/v1/reports/margins", params),

  getThirdPartyBalances: () =>
    get<ThirdPartyBalancesResponse>("/api/v1/reports/third-party-balances"),

  getTreasuryDashboard: () =>
    get<TreasuryDashboardResponse>("/api/v1/reports/treasury-dashboard"),

  getAuditBalances: () =>
    get<AuditBalancesResponse>("/api/v1/reports/audit-balances"),

  getBalanceDetailed: (params?: { as_of_date?: string }) =>
    get<BalanceDetailedResponse>("/api/v1/reports/balance-detailed", params),

  getInactiveBalances: (params: { min_days: number; min_amount: number }) =>
    get<InactiveBalancesResponse>("/api/v1/reports/inactive-balances", params),

  getProfitabilityByBU: (params: DateRange) =>
    get<ProfitabilityByBUResponse>("/api/v1/reports/profitability-by-business-unit", params),

  getRealCostByMaterial: (params: DateRange) =>
    get<RealCostByMaterialResponse>("/api/v1/reports/real-cost-by-material", params),

  getExpensesReport: (params: {
    date_from: string;
    date_to: string;
    group_by?: ExpensesGroupBy;
    business_unit_id?: string[];
    expense_category_id?: string[];
  }) => get<ExpensesReportResponse>("/api/v1/reports/expenses", params),

  getExpensesDetail: (params: {
    date_from: string;
    date_to: string;
    business_unit_id?: string;
    category_id?: string;
    business_unit_ids?: string[];
    category_ids?: string[];
    business_unit_unassigned?: boolean;
    category_uncategorized?: boolean;
    include_child_categories?: boolean;
  }) => get<ExpenseDetailResponse>("/api/v1/reports/expenses/detail", params),
};
