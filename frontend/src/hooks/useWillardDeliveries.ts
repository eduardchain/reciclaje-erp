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
    onSuccess: () => {
      toast.success("Salida actualizada");
      invalidateAfterWillardDelivery(qc);
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al actualizar")),
  });
}

export function useReviewWillardDelivery() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => willardDeliveryService.review(id),
    onSuccess: () => {
      toast.success("Salida revisada — pesos certificados");
      invalidateAfterWillardDelivery(qc);
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al revisar")),
  });
}

export function useLiquidateWillardDelivery() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: WillardDeliveryLiquidate }) =>
      willardDeliveryService.liquidate(id, data),
    onSuccess: (d) => {
      toast.success(`Salida #${d.delivery_number} liquidada`);
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
