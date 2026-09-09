import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getApiErrorMessage } from "@/utils/formatters";
import {
  willardDeliveryService,
  type WillardDeliveryFilters,
} from "@/services/willardDeliveries";
import type {
  WillardDeliveryCreate,
  WillardDeliveryLiquidate,
  WillardDeliveryUpdate,
} from "@/types/willard-delivery";
import { invalidateAfterWillardDelivery } from "@/utils/queryInvalidation";

export function useWillardDeliveries(filters: WillardDeliveryFilters = {}, enabled = true) {
  return useQuery({
    queryKey: ["willard-deliveries", "list", filters],
    queryFn: () => willardDeliveryService.getAll(filters),
    enabled,
  });
}

export function useWillardDelivery(id: string | undefined) {
  return useQuery({
    queryKey: ["willard-deliveries", "detail", id],
    queryFn: () => willardDeliveryService.getById(id!),
    enabled: !!id,
  });
}

export function useCreateWillardDelivery() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: WillardDeliveryCreate) => willardDeliveryService.create(data),
    onSuccess: (d) => {
      toast.success(`Salida #${d.delivery_number} registrada`);
      // El backend los entrega en los 4 endpoints (#103 C2): si la
      // pantalla los descarta, el aviso llega igual de tarde que si no
      // existiera. D2 y D3 son hermanos — fail-fast vale para los dos.
      (d.warnings ?? []).forEach((w) => toast.warning(w, { duration: 10000 }));
      invalidateAfterWillardDelivery(qc);
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al registrar la salida")),
  });
}

export function useUpdateWillardDelivery() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: WillardDeliveryUpdate }) =>
      willardDeliveryService.update(id, data),
    onSuccess: (d) => {
      toast.success("Salida actualizada");
      // El backend los entrega en los 4 endpoints (#103 C2): si la
      // pantalla los descarta, el aviso llega igual de tarde que si no
      // existiera. D2 y D3 son hermanos — fail-fast vale para los dos.
      (d.warnings ?? []).forEach((w) => toast.warning(w, { duration: 10000 }));
      invalidateAfterWillardDelivery(qc);
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al actualizar")),
  });
}

export function useLiquidateWillardDelivery() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: WillardDeliveryLiquidate }) =>
      willardDeliveryService.liquidate(id, data),
    onSuccess: (d) => {
      toast.success(`Salida #${d.delivery_number} liquidada`);
      // Patron de usePurchases/useInboundOrders. Sin esto el backend entrega
      // los warnings y la pantalla los descarta — el mismo defecto que
      // CC-009 arreglo en el endpoint, una capa mas arriba.
      (d.warnings ?? []).forEach((w) => toast.warning(w, { duration: 10000 }));
      invalidateAfterWillardDelivery(qc);
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al liquidar")),
  });
}

export function useAnnulWillardDelivery() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      willardDeliveryService.annul(id, reason),
    onSuccess: () => {
      toast.success("Salida anulada");
      invalidateAfterWillardDelivery(qc);
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al anular")),
  });
}
