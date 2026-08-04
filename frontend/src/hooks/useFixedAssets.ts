import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { fixedAssetService } from "@/services/fixedAssets";
import { getApiErrorMessage } from "@/utils/formatters";
import { invalidateAfterFixedAsset } from "@/utils/queryInvalidation";

interface FixedAssetFilters {
  skip?: number;
  limit?: number;
  status?: string;
}

export function useFixedAssets(filters: FixedAssetFilters = {}) {
  return useQuery({
    queryKey: ["fixed-assets", "list", filters],
    queryFn: () => fixedAssetService.getAll(filters),
  });
}

export function useFixedAsset(id: string) {
  return useQuery({
    queryKey: ["fixed-assets", "detail", id],
    queryFn: () => fixedAssetService.getById(id),
    enabled: !!id,
  });
}

export function useCreateFixedAsset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fixedAssetService.create,
    onSuccess: () => {
      invalidateAfterFixedAsset(queryClient);
      toast.success("Activo fijo creado exitosamente");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al crear el activo fijo"));
    },
  });
}

export function useUpdateFixedAsset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof fixedAssetService.update>[1] }) =>
      fixedAssetService.update(id, data),
    onSuccess: () => {
      invalidateAfterFixedAsset(queryClient);
      toast.success("Activo fijo actualizado");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al actualizar el activo fijo"));
    },
  });
}

export function useDepreciateAsset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => fixedAssetService.depreciate(id),
    onSuccess: () => {
      invalidateAfterFixedAsset(queryClient);
      toast.success("Depreciación aplicada exitosamente");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al aplicar depreciación"));
    },
  });
}

export function useApplyPendingDepreciations() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fixedAssetService.applyPending,
    onSuccess: (results) => {
      invalidateAfterFixedAsset(queryClient);
      if (results.length === 0) {
        toast.info("No hay depreciaciones pendientes para este mes");
      } else {
        toast.success(`${results.length} depreciación(es) aplicada(s)`);
      }
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al aplicar depreciaciones pendientes"));
    },
  });
}

export function useCancelFixedAsset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => fixedAssetService.cancel(id),
    onSuccess: () => {
      invalidateAfterFixedAsset(queryClient);
      toast.success("Activo cancelado — pago y depreciaciones revertidos");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al cancelar el activo"));
    },
  });
}

export function useRevalueAsset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof fixedAssetService.revalue>[1] }) =>
      fixedAssetService.revalue(id, data),
    onSuccess: () => {
      invalidateAfterFixedAsset(queryClient);
      toast.success("Revalorización aplicada");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al revalorizar el activo"));
    },
  });
}

export function useAnnulRevaluation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, revaluationId, reason }: { id: string; revaluationId: string; reason: string }) =>
      fixedAssetService.annulRevaluation(id, revaluationId, reason),
    onSuccess: () => {
      invalidateAfterFixedAsset(queryClient);
      toast.success("Revalorización anulada — efectos revertidos");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al anular la revalorización"));
    },
  });
}

export function useSellAsset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof fixedAssetService.sell>[1] }) =>
      fixedAssetService.sell(id, data),
    onSuccess: (asset) => {
      invalidateAfterFixedAsset(queryClient);
      toast.success("Venta registrada");
      (asset.warnings ?? []).forEach((w) => toast.warning(w, { duration: 8000 }));
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al vender el activo"));
    },
  });
}

export function useAnnulAssetSale() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      fixedAssetService.annulSale(id, reason),
    onSuccess: () => {
      invalidateAfterFixedAsset(queryClient);
      toast.success("Venta anulada — contrapartida revertida y activo restaurado");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al anular la venta"));
    },
  });
}

export function useDisposeAsset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      fixedAssetService.dispose(id, reason),
    onSuccess: () => {
      invalidateAfterFixedAsset(queryClient);
      toast.success("Activo dado de baja exitosamente");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al dar de baja el activo"));
    },
  });
}
