import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { deferredExpenseService } from "@/services/deferredExpenses";
import { getApiErrorMessage } from "@/utils/formatters";
import { invalidateAfterTreasury } from "@/utils/queryInvalidation";

interface DeferredExpenseFilters {
  skip?: number;
  limit?: number;
  status?: string;
}

export function useDeferredExpenses(filters: DeferredExpenseFilters = {}) {
  return useQuery({
    queryKey: ["deferred-expenses", "list", filters],
    queryFn: () => deferredExpenseService.getAll(filters),
  });
}

export function useDeferredExpense(id: string) {
  return useQuery({
    queryKey: ["deferred-expenses", "detail", id],
    queryFn: () => deferredExpenseService.getById(id),
    enabled: !!id,
  });
}

export function usePendingDeferredExpenses() {
  return useQuery({
    queryKey: ["deferred-expenses", "pending"],
    queryFn: () => deferredExpenseService.getPending(),
  });
}

export function useCreateDeferredExpense() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deferredExpenseService.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deferred-expenses"] });
      toast.success("Gasto programado creado exitosamente");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al crear el gasto programado"));
    },
  });
}

export function useApplyDeferredExpense() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deferredExpenseService.apply(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deferred-expenses"] });
      invalidateAfterTreasury(queryClient);
      toast.success("Cuota aplicada exitosamente");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al aplicar la cuota"));
    },
  });
}

export function useCancelDeferredExpense() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deferredExpenseService.cancel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deferred-expenses"] });
      toast.success("Gasto programado cancelado");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al cancelar el gasto programado"));
    },
  });
}
