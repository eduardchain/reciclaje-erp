import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { inboundOrderService, type InboundOrderFilters } from "@/services/inboundOrders";
import { getApiErrorMessage } from "@/utils/formatters";
import {
  invalidateAfterEntradaLiquidation,
  invalidateAfterInboundOrder,
} from "@/utils/queryInvalidation";
import type {
  InboundLiquidateRequest,
  InboundOrderCreate,
  InboundOrderUpdate,
} from "@/types/inbound-order";

export function useInboundOrders(filters: InboundOrderFilters = {}) {
  return useQuery({
    queryKey: ["inbound-orders", "list", filters],
    queryFn: () => inboundOrderService.getAll(filters),
  });
}

/**
 * Contadores de la bandeja por estado (#93: registradas por revisar +
 * revisadas por liquidar). Viven en la familia ["inbound-orders"] — se
 * refrescan con la misma invalidacion del modulo Y con la de
 * liquidar/cancelar compras (D17). W-C3: montar solo bajo flag.
 */
export function useEntriesStatusCounts(): { registered: number; reviewed: number } {
  const { data: reg } = useQuery({
    queryKey: ["inbound-orders", "list", { display_status: "registered", limit: 1 }],
    queryFn: () => inboundOrderService.getAll({ display_status: "registered", limit: 1 }),
    staleTime: 30_000,
  });
  const { data: rev } = useQuery({
    queryKey: ["inbound-orders", "list", { display_status: "reviewed", limit: 1 }],
    queryFn: () => inboundOrderService.getAll({ display_status: "reviewed", limit: 1 }),
    staleTime: 30_000,
  });
  return { registered: reg?.total ?? 0, reviewed: rev?.total ?? 0 };
}

/** Ciclo C: total de entradas pendientes (registradas + revisadas, #93). */
export function usePendingEntriesCount(): number {
  const { registered, reviewed } = useEntriesStatusCounts();
  return registered + reviewed;
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
      // #93: anular una liquidada revierte N compras + descuadres + comision
      invalidateAfterEntradaLiquidation(qc);
      toast.success("Entrada anulada");
      // Warnings no bloqueantes (D8): ej. stock queda negativo tras la reversa
      (order.warnings ?? []).forEach((w) => toast.warning(w, { duration: 8000 }));
    },
    onError: (e: unknown) =>
      toast.error(getApiErrorMessage(e, "Error al anular la entrada")),
  });
}

/** #93 D10: marcar revisada (permiso purchases.review) — ambos tipos desde
 *  el ciclo de Entradas: Willard también pasa por revisión */
export function useReviewInboundOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => inboundOrderService.review(id),
    onSuccess: (order) => {
      invalidateAfterInboundOrder(qc);
      toast.success(`Entrada #${order.order_number} revisada — lista para liquidar`);
    },
    onError: (e: unknown) =>
      toast.error(getApiErrorMessage(e, "Error al marcar la entrada como revisada")),
  });
}

/** #93 D14: liquidar con reparto — N compras + descuadres + comision, atomico */
export function useLiquidateInboundOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: InboundLiquidateRequest }) =>
      inboundOrderService.liquidate(id, data),
    onSuccess: (order) => {
      invalidateAfterEntradaLiquidation(qc);
      toast.success(
        `Entrada #${order.order_number} liquidada — ${order.purchases.length} compra${order.purchases.length === 1 ? "" : "s"}`
      );
      // D8: descuadres dentro/FUERA de tolerancia, proveedores cancelados, etc.
      (order.warnings ?? []).forEach((w) => toast.warning(w, { duration: 10000 }));
    },
    onError: (e: unknown) =>
      toast.error(getApiErrorMessage(e, "Error al liquidar la entrada")),
  });
}

/** #93 D20: revertir la liquidacion — vuelve a Revisada conservando el reparto */
export function useUnliquidateInboundOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => inboundOrderService.unliquidate(id),
    onSuccess: (order) => {
      invalidateAfterEntradaLiquidation(qc);
      toast.success(`Liquidación revertida — Entrada #${order.order_number} vuelve a Revisada`);
      (order.warnings ?? []).forEach((w) => toast.warning(w, { duration: 10000 }));
    },
    onError: (e: unknown) =>
      toast.error(getApiErrorMessage(e, "Error al revertir la liquidación")),
  });
}
