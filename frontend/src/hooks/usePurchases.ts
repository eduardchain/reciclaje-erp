import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { purchaseService } from "@/services/purchases";
import { getApiErrorMessage } from "@/utils/formatters";
import { invalidateAfterPurchase, invalidateAfterPurchaseLiquidateOrCancel } from "@/utils/queryInvalidation";
import type { PurchaseCreate, PurchaseFullUpdate, PurchaseLiquidateRequest } from "@/types/purchase";

interface PurchaseFilters {
  skip?: number;
  limit?: number;
  status?: string;
  supplier_id?: string;
  date_from?: string;
  date_to?: string;
  search?: string;
}

export function usePurchases(filters: PurchaseFilters = {}) {
  return useQuery({
    queryKey: ["purchases", "list", filters],
    queryFn: () => purchaseService.getAll(filters),
  });
}

export function usePurchase(id: string) {
  return useQuery({
    queryKey: ["purchases", "detail", id],
    queryFn: () => purchaseService.getById(id),
    enabled: !!id,
  });
}

export function useCreatePurchase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: PurchaseCreate) => purchaseService.create(data),
    onSuccess: (purchase) => {
      invalidateAfterPurchase(queryClient);
      toast.success("Compra creada exitosamente");
      if (purchase.warnings && purchase.warnings.length > 0) {
        purchase.warnings.forEach((w) => toast.warning(w));
      }
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al crear la compra"));
    },
  });
}

export function useUpdatePurchase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: PurchaseFullUpdate }) =>
      purchaseService.update(id, data),
    onSuccess: () => {
      invalidateAfterPurchase(queryClient);
      toast.success("Compra actualizada exitosamente");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al actualizar la compra"));
    },
  });
}

export function useLiquidatePurchase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: PurchaseLiquidateRequest }) =>
      purchaseService.liquidate(id, data),
    onSuccess: () => {
      invalidateAfterPurchaseLiquidateOrCancel(queryClient);
      toast.success("Compra liquidada exitosamente");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al liquidar la compra"));
    },
  });
}

export function useCancelPurchase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => purchaseService.cancel(id),
    onSuccess: () => {
      invalidateAfterPurchaseLiquidateOrCancel(queryClient);
      toast.success("Compra cancelada exitosamente");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al cancelar la compra"));
    },
  });
}
