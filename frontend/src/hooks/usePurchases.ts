import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { purchaseService } from "@/services/purchases";
import type { PurchaseCreate, PurchaseLiquidateRequest } from "@/types/purchase";

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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["purchases"] });
      toast.success("Compra creada exitosamente");
    },
    onError: (error: unknown) => {
      const message =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Error al crear la compra";
      toast.error(message);
    },
  });
}

export function useLiquidatePurchase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: PurchaseLiquidateRequest }) =>
      purchaseService.liquidate(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["purchases"] });
      toast.success("Compra liquidada exitosamente");
    },
    onError: (error: unknown) => {
      const message =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Error al liquidar la compra";
      toast.error(message);
    },
  });
}

export function useCancelPurchase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => purchaseService.cancel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["purchases"] });
      toast.success("Compra cancelada exitosamente");
    },
    onError: (error: unknown) => {
      const message =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Error al cancelar la compra";
      toast.error(message);
    },
  });
}
