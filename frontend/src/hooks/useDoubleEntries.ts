import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { doubleEntryService } from "@/services/doubleEntries";
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
      queryClient.invalidateQueries({ queryKey: ["double-entries"] });
      toast.success("Doble partida creada exitosamente");
    },
    onError: (error: unknown) => {
      const message =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Error al crear la doble partida";
      toast.error(message);
    },
  });
}

export function useCancelDoubleEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => doubleEntryService.cancel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["double-entries"] });
      toast.success("Doble partida cancelada exitosamente");
    },
    onError: (error: unknown) => {
      const message =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Error al cancelar la doble partida";
      toast.error(message);
    },
  });
}
