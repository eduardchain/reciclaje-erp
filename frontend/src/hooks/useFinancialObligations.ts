import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { financialObligationService } from "@/services/financialObligations";
import { getApiErrorMessage } from "@/utils/formatters";
import { invalidateAfterObligation } from "@/utils/queryInvalidation";
import type {
  FinancialObligationCreate,
  ObligationAccrueRequest,
  ObligationMovementCreate,
  ObligationTransferCreate,
} from "@/types/financial-obligation";

interface ObligationFilters {
  direction?: string;
  status?: string;
}

export function useFinancialObligations(filters: ObligationFilters = {}) {
  return useQuery({
    queryKey: ["financial-obligations", "list", filters],
    queryFn: () => financialObligationService.getAll(filters),
  });
}

export function useFinancialObligation(id: string) {
  return useQuery({
    queryKey: ["financial-obligations", "detail", id],
    queryFn: () => financialObligationService.getById(id),
    enabled: !!id,
  });
}

export function useObligationStatement(id: string) {
  return useQuery({
    queryKey: ["financial-obligations", "statement", id],
    queryFn: () => financialObligationService.getStatement(id),
    enabled: !!id,
  });
}

export function useObligationSummary() {
  return useQuery({
    queryKey: ["financial-obligations", "summary"],
    queryFn: () => financialObligationService.getSummary(),
  });
}

export function usePendingAccruals(enabled = true) {
  return useQuery({
    queryKey: ["financial-obligations", "pending-accruals"],
    queryFn: () => financialObligationService.getPendingAccruals(),
    enabled,
  });
}

export function useCreateObligation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: FinancialObligationCreate) => financialObligationService.create(data),
    onSuccess: () => {
      invalidateAfterObligation(queryClient);
      toast.success("Obligación creada exitosamente");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al crear la obligación"));
    },
  });
}

export function useAccruePending() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (expenseCategoryId?: string) =>
      financialObligationService.accruePending(expenseCategoryId),
    onSuccess: (result) => {
      invalidateAfterObligation(queryClient);
      toast.success(
        result.created_count > 0
          ? `${result.created_count} causación(es) de intereses creadas`
          : "No había períodos pendientes por causar"
      );
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al causar intereses"));
    },
  });
}

export function useAccruePreview(id: string, enabled = true) {
  return useQuery({
    queryKey: ["financial-obligations", "accrue-preview", id],
    queryFn: () => financialObligationService.getAccruePreview(id),
    enabled: enabled && !!id,
  });
}

export function useAccrueObligation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ObligationAccrueRequest }) =>
      financialObligationService.accrueObligation(id, data),
    onSuccess: (result) => {
      invalidateAfterObligation(queryClient);
      toast.success(`${result.created_count} causación(es) de intereses creadas`);
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al causar intereses"));
    },
  });
}

type MovementAction = "capital" | "interest" | "disbursement";

export function useObligationMovement(action: MovementAction) {
  const queryClient = useQueryClient();
  const fn = {
    capital: financialObligationService.capitalPayment,
    interest: financialObligationService.interestPayment,
    disbursement: financialObligationService.additionalDisbursement,
  }[action];
  const label = {
    capital: "Movimiento de capital registrado",
    interest: "Movimiento de intereses registrado",
    disbursement: "Desembolso adicional registrado",
  }[action];
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ObligationMovementCreate }) => fn(id, data),
    onSuccess: () => {
      invalidateAfterObligation(queryClient);
      toast.success(label);
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al registrar el movimiento"));
    },
  });
}

export function useObligationTransfer(action: "capital" | "interest") {
  const queryClient = useQueryClient();
  const fn = {
    capital: financialObligationService.capitalTransfer,
    interest: financialObligationService.interestTransfer,
  }[action];
  const label = {
    capital: "Abono a capital contra tercero registrado",
    interest: "Traslado de intereses registrado",
  }[action];
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ObligationTransferCreate }) => fn(id, data),
    onSuccess: () => {
      invalidateAfterObligation(queryClient);
      toast.success(label);
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al registrar el traslado"));
    },
  });
}

export function useSettleObligation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financialObligationService.settle(id),
    onSuccess: () => {
      invalidateAfterObligation(queryClient);
      toast.success("Obligación cerrada");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al cerrar la obligación"));
    },
  });
}

export function useAnnulObligationMovement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ movementId, reason }: { movementId: string; reason: string }) =>
      financialObligationService.annulMovement(movementId, reason),
    onSuccess: () => {
      invalidateAfterObligation(queryClient);
      toast.success("Movimiento anulado");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al anular el movimiento"));
    },
  });
}
