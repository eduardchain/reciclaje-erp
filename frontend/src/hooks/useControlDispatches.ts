import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getApiErrorMessage } from "@/utils/formatters";
import {
  controlDispatchService,
  type ControlDispatchFilters,
  type RemissionBookFilters,
} from "@/services/controlDispatches";
import type { ControlDispatchCreate, ControlDispatchUpdate } from "@/types/control-dispatch";
import { invalidateAfterControlDispatch } from "@/utils/queryInvalidation";

export function useControlDispatches(filters: ControlDispatchFilters = {}) {
  return useQuery({
    queryKey: ["control-dispatches", "list", filters],
    queryFn: () => controlDispatchService.getAll(filters),
  });
}

export function useControlDispatch(id: string | undefined) {
  return useQuery({
    queryKey: ["control-dispatches", "detail", id],
    queryFn: () => controlDispatchService.getById(id!),
    enabled: !!id,
  });
}

export function useRemissionBook(filters: RemissionBookFilters) {
  return useQuery({
    queryKey: ["remissions", "book", filters],
    queryFn: () => controlDispatchService.getRemissionBook(filters),
  });
}

export function useCreateControlDispatch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ControlDispatchCreate) => controlDispatchService.create(data),
    onSuccess: (d) => {
      toast.success(`Salida de control #${d.dispatch_number} registrada`);
      // Remision repetida (D8): llega por HTTP y se muestra; no bloquea.
      (d.warnings ?? []).forEach((w) => toast.warning(w, { duration: 10000 }));
      invalidateAfterControlDispatch(qc);
    },
    onError: (e: unknown) =>
      toast.error(getApiErrorMessage(e, "Error al registrar la salida de control")),
  });
}

export function useUpdateControlDispatch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ControlDispatchUpdate }) =>
      controlDispatchService.update(id, data),
    onSuccess: (d) => {
      toast.success(`Salida de control #${d.dispatch_number} actualizada`);
      (d.warnings ?? []).forEach((w) => toast.warning(w, { duration: 10000 }));
      invalidateAfterControlDispatch(qc);
    },
    onError: (e: unknown) =>
      toast.error(getApiErrorMessage(e, "Error al actualizar la salida de control")),
  });
}

export function useAnnulControlDispatch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      controlDispatchService.annul(id, reason),
    onSuccess: (d) => {
      toast.success(`Salida de control #${d.dispatch_number} anulada`);
      invalidateAfterControlDispatch(qc);
    },
    onError: (e: unknown) =>
      toast.error(getApiErrorMessage(e, "Error al anular la salida de control")),
  });
}
