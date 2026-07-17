import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { inboundOrderService, type InboundOrderFilters } from "@/services/inboundOrders";
import { getApiErrorMessage } from "@/utils/formatters";
import { invalidateAfterInboundOrder } from "@/utils/queryInvalidation";
import type { InboundOrderCreate, InboundOrderUpdate } from "@/types/inbound-order";

export function useInboundOrders(filters: InboundOrderFilters = {}) {
  return useQuery({
    queryKey: ["inbound-orders", "list", filters],
    queryFn: () => inboundOrderService.getAll(filters),
  });
}

export function useInboundOrder(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ["inbound-orders", "detail", id],
    queryFn: () => inboundOrderService.getById(id),
    enabled: !!id && (options?.enabled ?? true),
  });
}

export function useCreateInboundOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: InboundOrderCreate) => inboundOrderService.create(data),
    onSuccess: (order) => {
      invalidateAfterInboundOrder(qc);
      toast.success(`Recepción #${order.order_number} creada`);
      (order.warnings ?? []).forEach((w) => toast.warning(w, { duration: 8000 }));
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al crear la recepción")),
  });
}

export function useUpdateInboundOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: InboundOrderUpdate }) =>
      inboundOrderService.update(id, data),
    onSuccess: (order) => {
      invalidateAfterInboundOrder(qc);
      toast.success("Recepción actualizada");
      (order.warnings ?? []).forEach((w) => toast.warning(w, { duration: 8000 }));
    },
    onError: (e: unknown) =>
      toast.error(getApiErrorMessage(e, "Error al actualizar la recepción")),
  });
}

export function useAnnulInboundOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      inboundOrderService.annul(id, reason),
    onSuccess: (order) => {
      invalidateAfterInboundOrder(qc);
      toast.success("Recepción anulada");
      // Warnings no bloqueantes (D8): ej. stock queda negativo tras la reversa
      (order.warnings ?? []).forEach((w) => toast.warning(w, { duration: 8000 }));
    },
    onError: (e: unknown) =>
      // Ej: 400 "Cancele primero la compra #N" cuando la derivada esta liquidada
      toast.error(getApiErrorMessage(e, "Error al anular la recepción")),
  });
}
