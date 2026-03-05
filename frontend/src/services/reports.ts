import apiClient from "./api";
import type {
  DashboardResponse,
  ProfitAndLossResponse,
  CashFlowResponse,
  BalanceSheetResponse,
  PurchaseReportResponse,
  SalesReportResponse,
  MarginAnalysisResponse,
  ThirdPartyBalancesResponse,
} from "@/types/reports";

interface DateRange {
  date_from: string;
  date_to: string;
}

async function get<T>(url: string, params?: DateRange): Promise<T> {
  const response = await apiClient.get<T>(url, params ? { params } : undefined);
  return response.data;
}

export const reportsService = {
  getDashboard: (params: DateRange) =>
    get<DashboardResponse>("/api/v1/reports/dashboard", params),

  getProfitAndLoss: (params: DateRange) =>
    get<ProfitAndLossResponse>("/api/v1/reports/profit-and-loss", params),

  getCashFlow: (params: DateRange) =>
    get<CashFlowResponse>("/api/v1/reports/cash-flow", params),

  getBalanceSheet: () =>
    get<BalanceSheetResponse>("/api/v1/reports/balance-sheet"),

  getPurchaseReport: (params: DateRange) =>
    get<PurchaseReportResponse>("/api/v1/reports/purchases", params),

  getSalesReport: (params: DateRange) =>
    get<SalesReportResponse>("/api/v1/reports/sales", params),

  getMarginAnalysis: (params: DateRange) =>
    get<MarginAnalysisResponse>("/api/v1/reports/margins", params),

  getThirdPartyBalances: () =>
    get<ThirdPartyBalancesResponse>("/api/v1/reports/balances"),
};
