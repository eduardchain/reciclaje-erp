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

export function useBalanceSheet() {
  return useQuery({
    queryKey: ["reports", "balance-sheet"],
    queryFn: () => reportsService.getBalanceSheet(),
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
