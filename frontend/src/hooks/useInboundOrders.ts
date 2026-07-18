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

/**
 * Ciclo C: contador de la bandeja (entradas por liquidar, ambos tipos).
 * Vive en la familia ["inbound-orders"] — se refresca con la misma
 * invalidacion del modulo Y con la de liquidar/cancelar compras (D17).
 * W-C3: los callers solo lo montan bajo flag kg_ledger_enabled.
 */
export function usePendingEntriesCount(): number {
  const { data } = useQuery({
    queryKey: ["inbound-orders", "list", { display_status: "registered", limit: 1 }],
    queryFn: () => inboundOrderService.getAll({ display_status: "registered", limit: 1 }),
    staleTime: 30_000,
  });
  return data?.total ?? 0;
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
      // B.2: willard nace draft — dejar claro que falta la confirmacion
      toast.success(
        order.status === "draft"
          ? `Entrada #${order.order_number} registrada — pendiente de liquidar`
          : `Entrada #${order.order_number} creada`
      );
      (order.warnings ?? []).forEach((w) => toast.warning(w, { duration: 8000 }));
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al crear la entrada")),
  });
}

export function useUpdateInboundOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: InboundOrderUpdate }) =>
      inboundOrderService.update(id, data),
    onSuccess: (order) => {
      invalidateAfterInboundOrder(qc);
      toast.success("Entrada actualizada");
      (order.warnings ?? []).forEach((w) => toast.warning(w, { duration: 8000 }));
    },
    onError: (e: unknown) =>
      toast.error(getApiErrorMessage(e, "Error al actualizar la entrada")),
  });
}

export function useConfirmInboundOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => inboundOrderService.confirm(id),
    onSuccess: (order) => {
      // B.2: los efectos (inventario + kg) nacen aca — misma invalidacion que el create
      invalidateAfterInboundOrder(qc);
      toast.success(`Entrada #${order.order_number} liquidada`);
    },
    onError: (e: unknown) =>
      toast.error(getApiErrorMessage(e, "Error al liquidar la entrada")),
  });
}

export function useAnnulInboundOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      inboundOrderService.annul(id, reason),
    onSuccess: (order) => {
      invalidateAfterInboundOrder(qc);
      toast.success("Entrada anulada");
      // Warnings no bloqueantes (D8): ej. stock queda negativo tras la reversa
      (order.warnings ?? []).forEach((w) => toast.warning(w, { duration: 8000 }));
    },
    onError: (e: unknown) =>
      // Ej: 400 "Cancele primero la compra #N" cuando la derivada esta liquidada
      toast.error(getApiErrorMessage(e, "Error al anular la entrada")),
  });
}
