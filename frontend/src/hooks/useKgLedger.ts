import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { kgLedgerService, type KgStatementFilters } from "@/services/kgLedger";
import { getApiErrorMessage } from "@/utils/formatters";
import { invalidateAfterKgMovement } from "@/utils/queryInvalidation";
import type {
  KgLedgerAccountCreate,
  KgLedgerAccountUpdate,
  KgLedgerMovementManualCreate,
} from "@/types/kg-ledger";

// Query keys: ["kg-ledger", "accounts" | "summary" | "statement", ...]

export function useKgAccounts(filters?: { account_type?: string; include_inactive?: boolean }) {
  return useQuery({
    queryKey: ["kg-ledger", "accounts", filters ?? {}],
    queryFn: () => kgLedgerService.getAccounts(filters),
  });
}

export function useKgSummary(asOf?: string) {
  return useQuery({
    queryKey: ["kg-ledger", "summary", asOf ?? "now"],
    queryFn: () => kgLedgerService.getSummary(asOf),
  });
}

export function useKgStatement(accountId: string, filters?: KgStatementFilters) {
  return useQuery({
    queryKey: ["kg-ledger", "statement", accountId, filters ?? {}],
    queryFn: () => kgLedgerService.getStatement(accountId, filters),
    enabled: !!accountId,
  });
}

export function useCreateKgAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: KgLedgerAccountCreate) => kgLedgerService.createAccount(data),
    onSuccess: () => {
      toast.success("Cuenta kg creada");
      invalidateAfterKgMovement(qc);
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al crear la cuenta kg")),
  });
}

export function useUpdateKgAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: KgLedgerAccountUpdate }) =>
      kgLedgerService.updateAccount(id, data),
    onSuccess: () => {
      toast.success("Cuenta kg actualizada");
      invalidateAfterKgMovement(qc);
    },
    onError: (e: unknown) =>
      toast.error(getApiErrorMessage(e, "Error al actualizar la cuenta kg")),
  });
}

export function useCreateKgManualMovement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: KgLedgerMovementManualCreate) =>
      kgLedgerService.createManualMovement(data),
    onSuccess: () => {
      toast.success("Movimiento manual registrado");
      invalidateAfterKgMovement(qc);
    },
    onError: (e: unknown) =>
      toast.error(getApiErrorMessage(e, "Error al registrar el movimiento")),
  });
}

export function useAnnulKgMovement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      kgLedgerService.annulMovement(id, reason),
    onSuccess: () => {
      toast.success("Movimiento anulado");
      invalidateAfterKgMovement(qc);
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error al anular el movimiento")),
  });
}
