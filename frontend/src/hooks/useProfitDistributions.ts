import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { profitDistributionService } from "@/services/profitDistributions";
import { invalidateAfterTreasury } from "@/utils/queryInvalidation";
import type { ProfitDistributionCreate } from "@/types/profit-distribution";

export function useAvailableProfit() {
  return useQuery({
    queryKey: ["profit-distributions", "available"],
    queryFn: profitDistributionService.getAvailable,
  });
}

export function usePartners() {
  return useQuery({
    queryKey: ["profit-distributions", "partners"],
    queryFn: profitDistributionService.getPartners,
  });
}

export function useProfitDistributions(params?: { skip?: number; limit?: number }) {
  return useQuery({
    queryKey: ["profit-distributions", "list", params],
    queryFn: () => profitDistributionService.getAll(params),
  });
}

export function useCreateDistribution() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ProfitDistributionCreate) =>
      profitDistributionService.create(data),
    onSuccess: () => {
      toast.success("Repartición registrada exitosamente");
      queryClient.invalidateQueries({ queryKey: ["profit-distributions"] });
      invalidateAfterTreasury(queryClient);
    },
    onError: (error: any) => {
      toast.error(
        error.response?.data?.detail || "Error al registrar repartición"
      );
    },
  });
}
