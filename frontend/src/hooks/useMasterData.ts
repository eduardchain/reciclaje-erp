import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { thirdPartyService } from "@/services/thirdParties";
import { getApiErrorMessage } from "@/utils/formatters";
import type { RetentionEntityCreate } from "@/types/third-party";
import { materialService } from "@/services/materials";
import { warehouseService } from "@/services/warehouses";
import { moneyAccountService } from "@/services/moneyAccounts";
import { expenseCategoryService } from "@/services/masterData";
import { thirdPartyCategoryService } from "@/services/thirdPartyCategories";

export function useSuppliers(search?: string) {
  return useQuery({
    queryKey: ["third-parties", "suppliers", search],
    queryFn: () => thirdPartyService.getSuppliers({ search, limit: 500, is_active: true }),
  });
}

export function usePayableSuppliers(search?: string) {
  return useQuery({
    queryKey: ["third-parties", "payable-suppliers", search],
    queryFn: () => thirdPartyService.getPayableSuppliers({ search, limit: 500, is_active: true }),
  });
}

export function useCustomers(search?: string) {
  return useQuery({
    queryKey: ["third-parties", "customers", search],
    queryFn: () => thirdPartyService.getCustomers({ search, limit: 500, is_active: true }),
  });
}

export function useThirdParties(
  filters?: {
    search?: string;
    role?: string;
    is_active?: boolean;
    skip?: number;
    limit?: number;
    sort_by?: string;
    sort_dir?: "asc" | "desc";
  },
  options?: { staleTime?: number }
) {
  // skip/limit/sort_by/sort_dir son opcionales — dropdowns que solo pasan
  // search/role siguen funcionando con limit=500 por default (sin cambio).
  return useQuery({
    queryKey: ["third-parties", "list", filters],
    queryFn: () => thirdPartyService.getAll({ limit: 500, ...filters }),
    ...options,
  });
}

export function useMaterials(search?: string) {
  return useQuery({
    queryKey: ["materials", "list", search],
    queryFn: () => materialService.getAll({ search, limit: 500 }),
  });
}

export function useWarehouses() {
  return useQuery({
    queryKey: ["warehouses", "list"],
    queryFn: () => warehouseService.getAll(),
  });
}

export function useMoneyAccounts() {
  return useQuery({
    queryKey: ["money-accounts", "list"],
    queryFn: () => moneyAccountService.getAll(),
  });
}

export function useInvestors(search?: string) {
  return useQuery({
    queryKey: ["third-parties", "investors", search],
    queryFn: () => thirdPartyService.getAll({ role: "investor", search, limit: 500, is_active: true }),
  });
}

export function useExpenseCategories() {
  return useQuery({
    queryKey: ["expense-categories", "list"],
    queryFn: () => expenseCategoryService.getAll(),
  });
}

export function useExpenseCategoriesFlat() {
  return useQuery({
    queryKey: ["expense-categories", "flat"],
    queryFn: () => expenseCategoryService.getFlat(),
  });
}

export function useProvisions(search?: string, is_active?: boolean) {
  return useQuery({
    queryKey: ["third-parties", "provisions", search, is_active],
    queryFn: () => thirdPartyService.getProvisions({ search, limit: 500, is_active }),
  });
}

export function useLiabilities(search?: string, is_active?: boolean, includeSystem?: boolean) {
  // includeSystem (SAC E2 D9): suma las entidades "[Retenciones] X" — usar SOLO
  // en selectores de PAGO (sus saldos nacen de liquidaciones, no de causaciones).
  return useQuery({
    queryKey: ["third-parties", "liabilities", search, is_active, includeSystem ?? false],
    queryFn: () =>
      thirdPartyService.getLiabilities({
        search,
        limit: 500,
        is_active,
        ...(includeSystem ? { include_system: true } : {}),
      }),
  });
}

export function useRetentionEntities(enabled: boolean) {
  // F2 QA: el endpoint es flag-gated (kg_ledger_enabled) y este hook vive en
  // páginas COMPARTIDAS con las orgs prod (LiabilitiesPage, Liquidate) — pasar
  // SIEMPRE enabled=flagEnabled("kg_ledger_enabled"): sin flag, cero requests.
  return useQuery({
    queryKey: ["third-parties", "retention-entities"],
    queryFn: () => thirdPartyService.getRetentionEntities(),
    enabled,
  });
}

export function useCreateRetentionEntity() {
  // POST idempotente (matching sin acentos/casing en backend): repetir un
  // municipio existente devuelve la MISMA entidad — sin riesgo de duplicados.
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: RetentionEntityCreate) => thirdPartyService.createRetentionEntity(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["third-parties"] });
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al crear el municipio ICA"));
    },
  });
}

export function useGenericThirdParties(search?: string) {
  return useQuery({
    queryKey: ["third-parties", "generic", search],
    queryFn: () => thirdPartyService.getGeneric({ search, limit: 500, is_active: true }),
  });
}

export function usePayableProviders(search?: string) {
  return useQuery({
    queryKey: ["third-parties", "payable-providers", search],
    queryFn: () => thirdPartyService.getPayableProviders({ search, limit: 500, is_active: true }),
  });
}

export function useThirdPartyCategoriesFlat(behaviorType?: string) {
  return useQuery({
    queryKey: ["third-party-categories", "flat", behaviorType],
    queryFn: () => thirdPartyCategoryService.getFlat(behaviorType),
  });
}
