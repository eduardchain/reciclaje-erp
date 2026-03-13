import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { doubleEntryService } from "@/services/doubleEntries";
import { getApiErrorMessage } from "@/utils/formatters";
import { invalidateAfterDoubleEntry } from "@/utils/queryInvalidation";
import type { DoubleEntryCreate, DoubleEntryFullUpdate, DoubleEntryLiquidateRequest } from "@/types/double-entry";

interface DoubleEntryFilters {
  skip?: number;
  limit?: number;
  status?: string;
  search?: string;
  date_from?: string;
  date_to?: string;
}

export function useDoubleEntries(filters: DoubleEntryFilters = {}) {
  return useQuery({
    queryKey: ["double-entries", "list", filters],
    queryFn: () => doubleEntryService.getAll(filters),
  });
}

export function useDoubleEntry(id: string) {
  return useQuery({
    queryKey: ["double-entries", "detail", id],
    queryFn: () => doubleEntryService.getById(id),
    enabled: !!id,
  });
}

export function useCreateDoubleEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: DoubleEntryCreate) => doubleEntryService.create(data),
    onSuccess: () => {
      invalidateAfterDoubleEntry(queryClient);
      toast.success("Doble partida registrada exitosamente");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al registrar la doble partida"));
    },
  });
}

export function useEditDoubleEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: DoubleEntryFullUpdate }) =>
      doubleEntryService.edit(id, data),
    onSuccess: () => {
      invalidateAfterDoubleEntry(queryClient);
      toast.success("Doble partida actualizada exitosamente");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al actualizar la doble partida"));
    },
  });
}

export function useLiquidateDoubleEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: DoubleEntryLiquidateRequest }) =>
      doubleEntryService.liquidate(id, data),
    onSuccess: () => {
      invalidateAfterDoubleEntry(queryClient);
      toast.success("Doble partida liquidada exitosamente");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al liquidar la doble partida"));
    },
  });
}

export function useCancelDoubleEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => doubleEntryService.cancel(id),
    onSuccess: () => {
      invalidateAfterDoubleEntry(queryClient);
      toast.success("Doble partida cancelada exitosamente");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al cancelar la doble partida"));
    },
  });
}
