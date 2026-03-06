import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { moneyMovementService } from "@/services/moneyMovements";
import type { AnnulMovementRequest } from "@/types/money-movement";
import axios from "axios";

function getApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) return error.response?.data?.detail || fallback;
  return fallback;
}

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
  };

  return useMutation({
    mutationFn: (data: unknown) => {
      const fn = endpointMap[type];
      if (!fn) throw new Error(`Tipo de movimiento desconocido: ${type}`);
      return fn(data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["money-movements"] });
      queryClient.invalidateQueries({ queryKey: ["money-accounts"] });
      toast.success("Movimiento creado exitosamente");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al crear el movimiento"));
    },
  });
}

export function useAnnulMovement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: AnnulMovementRequest }) =>
      moneyMovementService.annul(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["money-movements"] });
      queryClient.invalidateQueries({ queryKey: ["money-accounts"] });
      toast.success("Movimiento anulado exitosamente");
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al anular el movimiento"));
    },
  });
}
