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
