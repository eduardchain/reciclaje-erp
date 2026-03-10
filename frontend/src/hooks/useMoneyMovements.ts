import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { moneyMovementService } from "@/services/moneyMovements";
import { getApiErrorMessage } from "@/utils/formatters";
import { invalidateAfterTreasury } from "@/utils/queryInvalidation";
import type { AnnulMovementRequest } from "@/types/money-movement";

interface MovementFilters {
  skip?: number;
  limit?: number;
  movement_type?: string;
  account_id?: string;
  date_from?: string;
  date_to?: string;
  status?: string;
}

export function useMoneyMovements(filters: MovementFilters = {}) {
  return useQuery({
    queryKey: ["money-movements", "list", filters],
    queryFn: () => moneyMovementService.getAll(filters),
  });
}

export function useMoneyMovement(id: string) {
  return useQuery({
    queryKey: ["money-movements", "detail", id],
    queryFn: () => moneyMovementService.getById(id),
    enabled: !!id,
  });
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function useCreateMovement(type: string) {
  const queryClient = useQueryClient();
  const endpointMap: Record<string, (data: any) => Promise<any>> = {
    payment_to_supplier: moneyMovementService.createSupplierPayment,
    collection_from_client: moneyMovementService.createCustomerCollection,
    expense: moneyMovementService.createExpense,
    service_income: moneyMovementService.createServiceIncome,
    transfer: moneyMovementService.createTransfer,
    capital_injection: moneyMovementService.createCapitalInjection,
    capital_return: moneyMovementService.createCapitalReturn,
    commission_payment: moneyMovementService.createCommissionPayment,
    provision_deposit: moneyMovementService.createProvisionDeposit,
    provision_expense: moneyMovementService.createProvisionExpense,
    advance_payment: moneyMovementService.createAdvancePayment,
    advance_collection: moneyMovementService.createAdvanceCollection,
    asset_payment: moneyMovementService.createAssetPayment,
  };

  return useMutation({
    mutationFn: (data: unknown) => {
      const fn = endpointMap[type];
      if (!fn) throw new Error(`Tipo de movimiento desconocido: ${type}`);
      return fn(data);
    },
    onSuccess: () => {
      invalidateAfterTreasury(queryClient);
      toast.success("Movimiento creado exitosamente");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al crear el movimiento"));
    },
  });
}

export function useAccountMovements(accountId: string, filters: { date_from?: string; date_to?: string } = {}) {
  return useQuery({
    queryKey: ["money-movements", "account", accountId, filters],
    queryFn: () => moneyMovementService.getByAccount(accountId, filters),
    enabled: !!accountId,
    staleTime: 0,
  });
}

export function useThirdPartyMovements(thirdPartyId: string, filters: { date_from?: string; date_to?: string } = {}) {
  return useQuery({
    queryKey: ["money-movements", "third-party", thirdPartyId, filters],
    queryFn: () => moneyMovementService.getByThirdParty(thirdPartyId, filters),
    enabled: !!thirdPartyId,
    staleTime: 0,
  });
}

export function useUploadEvidence() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, file }: { id: string; file: File }) =>
      moneyMovementService.uploadEvidence(id, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["money-movements"] });
      toast.success("Comprobante subido exitosamente");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al subir el comprobante"));
    },
  });
}

export function useDeleteEvidence() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => moneyMovementService.deleteEvidence(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["money-movements"] });
      toast.success("Comprobante eliminado");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al eliminar el comprobante"));
    },
  });
}

export function useAnnulMovement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: AnnulMovementRequest }) =>
      moneyMovementService.annul(id, data),
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    onSuccess: (response: any) => {
      invalidateAfterTreasury(queryClient);
      toast.success("Movimiento anulado exitosamente");
      if (response?.warnings?.length) {
        response.warnings.forEach((w: string) => toast.warning(w));
      }
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al anular el movimiento"));
    },
  });
}
