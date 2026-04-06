import { useQuery } from "@tanstack/react-query";
import { reportsService } from "@/services/reports";

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

export function usePurchaseReport(params: DateRange) {
  return useQuery({
    queryKey: ["reports", "purchases", params],
    queryFn: () => reportsService.getPurchaseReport(params),
    enabled: !!params.date_from && !!params.date_to,
  });
}

export function useSalesReport(params: DateRange) {
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
