import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { doubleEntryService } from "@/services/doubleEntries";
import { getApiErrorMessage } from "@/utils/formatters";
import { invalidateAfterDoubleEntry } from "@/utils/queryInvalidation";
import type { DoubleEntryCreate } from "@/types/double-entry";

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
      toast.success("Doble partida creada exitosamente");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al crear la doble partida"));
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
