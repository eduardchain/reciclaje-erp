import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { transferService, type TransferFilters } from "@/services/transfers";
import { getApiErrorMessage } from "@/utils/formatters";
import { invalidateAfterTransfer } from "@/utils/queryInvalidation";
import type {
  TransferDispatchCreate,
  TransferReceiveRequest,
  TransferResolveRequest,
} from "@/types/transfer";

// SAC E3.1 — hooks de traslados dos pasos. Los callers solo los montan bajo
// flag two_step_transfers_enabled (regla F2: cero requests sin flag).

export function useTransfers(filters: TransferFilters = {}) {
  return useQuery({
    queryKey: ["transfers", "list", filters],
    queryFn: () => transferService.getAll(filters),
  });
}

export function useTransfer(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ["transfers", "detail", id],
    queryFn: () => transferService.getById(id),
    enabled: !!id && (options?.enabled ?? true),
  });
}

/** Contador de la bandeja "Por recibir" (badge ámbar del Sidebar). */
export function usePendingTransfersCount(): number {
  const { data } = useQuery({
    queryKey: ["transfers", "list", { pending_receipt: true, limit: 1 }],
    queryFn: () => transferService.getAll({ pending_receipt: true, limit: 1 }),
    staleTime: 30_000,
  });
  return data?.pending_receipt_count ?? 0;
}

function showWarnings(warnings?: string[]) {
  (warnings ?? []).forEach((w) => toast.warning(w, { duration: 8000 }));
}

export function useDispatchTransfer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: TransferDispatchCreate) => transferService.dispatch(data),
    onSuccess: (t) => {
      invalidateAfterTransfer(qc);
      toast.success(`Traslado #${t.transfer_number} despachado`);
      showWarnings(t.warnings);
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });
}

export function useReceiveTransfer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: TransferReceiveRequest }) =>
      transferService.receive(id, data),
    onSuccess: (t) => {
      invalidateAfterTransfer(qc);
      toast.success(
        t.status === "held_discrepancy"
          ? `Traslado #${t.transfer_number} recibido con discrepancia — pendiente de resolver`
          : `Traslado #${t.transfer_number} recibido`
      );
      showWarnings(t.warnings);
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });
}

export function useResolveTransfer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: TransferResolveRequest }) =>
      transferService.resolve(id, data),
    onSuccess: (t) => {
      invalidateAfterTransfer(qc);
      toast.success(`Discrepancia del traslado #${t.transfer_number} resuelta`);
      showWarnings(t.warnings);
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });
}

export function useAnnulTransfer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      transferService.annul(id, reason),
    onSuccess: (t) => {
      invalidateAfterTransfer(qc);
      toast.success(`Traslado #${t.transfer_number} anulado`);
      showWarnings(t.warnings);
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });
}
