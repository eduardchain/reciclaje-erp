import { useQuery } from "@tanstack/react-query";
import { reportsService } from "@/services/reports";
import type { ExpensesGroupBy, DpFilter } from "@/types/reports";

interface DateRange {
  date_from: string;
  date_to: string;
}

export function useDashboard(params: DateRange) {
  return useQuery({
    queryKey: ["reports", "dashboard", params],
    queryFn: () => reportsService.getDashboard(params),
    enabled: !!params.date_from && !!params.date_to,
  });
}

export function useProfitAndLoss(params: DateRange) {
  return useQuery({
    queryKey: ["reports", "profit-and-loss", params],
    queryFn: () => reportsService.getProfitAndLoss(params),
    enabled: !!params.date_from && !!params.date_to,
  });
}

export function useProfitAndLossMonthly(params: DateRange & { cutoff_day?: number }) {
  return useQuery({
    queryKey: ["reports", "profit-and-loss-monthly", params],
    queryFn: () => reportsService.getProfitAndLossMonthly(params),
    enabled: !!params.date_from && !!params.date_to,
  });
}

export function useCashFlow(params: DateRange) {
  return useQuery({
    queryKey: ["reports", "cash-flow", params],
    queryFn: () => reportsService.getCashFlow(params),
    enabled: !!params.date_from && !!params.date_to,
  });
}

export function useBalanceSheet(asOfDate?: string) {
  return useQuery({
    queryKey: ["reports", "balance-sheet", asOfDate ?? "today"],
    queryFn: () => reportsService.getBalanceSheet(asOfDate ? { as_of_date: asOfDate } : undefined),
  });
}

export function usePurchaseReport(params: DateRange & { dp_filter?: DpFilter }) {
  return useQuery({
    queryKey: ["reports", "purchases", params],
    queryFn: () => reportsService.getPurchaseReport(params),
    enabled: !!params.date_from && !!params.date_to,
  });
}

export function useSalesReport(params: DateRange & { dp_filter?: DpFilter }) {
  return useQuery({
    queryKey: ["reports", "sales", params],
    queryFn: () => reportsService.getSalesReport(params),
    enabled: !!params.date_from && !!params.date_to,
  });
}

export function useMarginAnalysis(params: DateRange) {
  return useQuery({
    queryKey: ["reports", "margins", params],
    queryFn: () => reportsService.getMarginAnalysis(params),
    enabled: !!params.date_from && !!params.date_to,
  });
}

export function useThirdPartyBalances() {
  return useQuery({
    queryKey: ["reports", "balances"],
    queryFn: () => reportsService.getThirdPartyBalances(),
  });
}

export function useAuditBalances(enabled: boolean) {
  return useQuery({
    queryKey: ["reports", "audit-balances"],
    queryFn: () => reportsService.getAuditBalances(),
    enabled,
  });
}

export function useBalanceDetailed(asOfDate?: string) {
  return useQuery({
    queryKey: ["reports", "balance-detailed", asOfDate ?? "today"],
    queryFn: () => reportsService.getBalanceDetailed(asOfDate ? { as_of_date: asOfDate } : undefined),
  });
}

export function useProfitabilityByBU(params: DateRange) {
  return useQuery({
    queryKey: ["reports", "profitability-bu", params],
    queryFn: () => reportsService.getProfitabilityByBU(params),
    enabled: !!params.date_from && !!params.date_to,
  });
}

export function useRealCostByMaterial(params: DateRange) {
  return useQuery({
    queryKey: ["reports", "real-cost-material", params],
    queryFn: () => reportsService.getRealCostByMaterial(params),
    enabled: !!params.date_from && !!params.date_to,
  });
}

interface ExpensesReportParams extends DateRange {
  group_by?: ExpensesGroupBy;
  business_unit_id?: string[];
  expense_category_id?: string[];
}

export function useExpensesReport(params: ExpensesReportParams) {
  return useQuery({
    queryKey: ["reports", "expenses", params],
    queryFn: () => reportsService.getExpensesReport(params),
    enabled: !!params.date_from && !!params.date_to,
  });
}

interface ExpensesDetailParams extends DateRange {
  business_unit_id?: string;
  category_id?: string;
  business_unit_ids?: string[];
  category_ids?: string[];
  business_unit_unassigned?: boolean;
  category_uncategorized?: boolean;
  include_child_categories?: boolean;
}

export function useExpensesDetail(params: ExpensesDetailParams, enabled: boolean) {
  return useQuery({
    queryKey: ["reports", "expenses-detail", params],
    queryFn: () => reportsService.getExpensesDetail(params),
    enabled: enabled && !!params.date_from && !!params.date_to,
  });
}
