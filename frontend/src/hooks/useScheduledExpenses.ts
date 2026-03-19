import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { scheduledExpenseService } from "@/services/scheduledExpenses";
import { getApiErrorMessage } from "@/utils/formatters";
import { invalidateAfterTreasury } from "@/utils/queryInvalidation";

interface ScheduledExpenseFilters {
  skip?: number;
  limit?: number;
  status?: string;
}

export function useScheduledExpenses(filters: ScheduledExpenseFilters = {}) {
  return useQuery({
    queryKey: ["scheduled-expenses", "list", filters],
    queryFn: () => scheduledExpenseService.getAll(filters),
  });
}

export function useScheduledExpense(id: string) {
  return useQuery({
    queryKey: ["scheduled-expenses", "detail", id],
    queryFn: () => scheduledExpenseService.getById(id),
    enabled: !!id,
  });
}

export function usePendingScheduledExpenses() {
  return useQuery({
    queryKey: ["scheduled-expenses", "pending"],
    queryFn: () => scheduledExpenseService.getPending(),
  });
}

export function useCreateScheduledExpense() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: scheduledExpenseService.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scheduled-expenses"] });
      invalidateAfterTreasury(queryClient);
      toast.success("Gasto diferido creado exitosamente");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al crear el gasto diferido"));
    },
  });
}

export function useApplyScheduledExpense() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => scheduledExpenseService.apply(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scheduled-expenses"] });
      invalidateAfterTreasury(queryClient);
      toast.success("Cuota aplicada exitosamente");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al aplicar la cuota"));
    },
  });
}

export function useCancelScheduledExpense() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => scheduledExpenseService.cancel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scheduled-expenses"] });
      invalidateAfterTreasury(queryClient);
      toast.success("Gasto diferido cancelado");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al cancelar el gasto diferido"));
    },
  });
}
