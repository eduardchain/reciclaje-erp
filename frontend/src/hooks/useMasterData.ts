import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { SELECT_LIMIT, thirdPartyService } from "@/services/thirdParties";
import { getApiErrorMessage } from "@/utils/formatters";
import type { RetentionConfigCreate, RetentionConfigUpdate } from "@/types/third-party";
import { materialService } from "@/services/materials";
import { warehouseService } from "@/services/warehouses";
import { moneyAccountService } from "@/services/moneyAccounts";
import { expenseCategoryService } from "@/services/masterData";
import { thirdPartyCategoryService } from "@/services/thirdPartyCategories";

export function useSuppliers(search?: string) {
  return useQuery({
    queryKey: ["third-parties", "suppliers", search],
    queryFn: () => thirdPartyService.getSuppliers({ search, limit: SELECT_LIMIT, is_active: true }),
  });
}

// Alcance de recolector (plan Ingrid v1.6 §8): los proveedores de SU alcance,
// activos o no — el servidor filtra la lista (fila 11). Sirve para saber qué
// compra de una Entrada puede abrir. Solo con alcance (`enabled`): para
// cualquier otro usuario no sale ningún request.
export function useScopeSupplierIds(enabled: boolean) {
  const { data } = useQuery({
    queryKey: ["third-parties", "suppliers", "scope-ids"],
    queryFn: () => thirdPartyService.getSuppliers({ limit: SELECT_LIMIT }),
    enabled,
  });
  return data ? new Set(data.items.map((s) => s.id)) : null;
}

export function usePayableSuppliers(search?: string, enabled: boolean = true) {
  return useQuery({
    queryKey: ["third-parties", "payable-suppliers", search],
    queryFn: () => thirdPartyService.getPayableSuppliers({ search, limit: SELECT_LIMIT, is_active: true }),
    enabled,
  });
}

export function useCustomers(search?: string, enabled: boolean = true) {
  return useQuery({
    queryKey: ["third-parties", "customers", search],
    queryFn: () => thirdPartyService.getCustomers({ search, limit: SELECT_LIMIT, is_active: true }),
    enabled,
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
    collector_id?: string;
  },
  options?: { staleTime?: number }
) {
  // skip/limit/sort_by/sort_dir son opcionales: el listado de Terceros pasa los
  // suyos (paginacion server-side) y pisa el default; los dropdowns solo pasan
  // search/role y se quedan con SELECT_LIMIT.
  return useQuery({
    queryKey: ["third-parties", "list", filters],
    queryFn: () => thirdPartyService.getAll({ limit: SELECT_LIMIT, ...filters }),
    ...options,
  });
}

export function useMaterials(search?: string) {
  return useQuery({
    queryKey: ["materials", "list", search],
    queryFn: () => materialService.getAll({ search, limit: 500 }),
  });
}

export function useWarehouses(enabled: boolean = true) {
  return useQuery({
    queryKey: ["warehouses", "list"],
    queryFn: () => warehouseService.getAll(),
    enabled,
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
    queryFn: () => thirdPartyService.getAll({ role: "investor", search, limit: SELECT_LIMIT, is_active: true }),
  });
}

export function useExpenseCategories() {
  return useQuery({
    queryKey: ["expense-categories", "list"],
    queryFn: () => expenseCategoryService.getAll(),
  });
}

export function useExpenseCategoriesFlat(enabled: boolean = true) {
  return useQuery({
    queryKey: ["expense-categories", "flat"],
    queryFn: () => expenseCategoryService.getFlat(),
    enabled,
  });
}

export function useProvisions(search?: string, is_active?: boolean, enabled: boolean = true) {
  return useQuery({
    queryKey: ["third-parties", "provisions", search, is_active],
    queryFn: () => thirdPartyService.getProvisions({ search, limit: SELECT_LIMIT, is_active }),
    enabled,
  });
}

export function useLiabilities(
  search?: string,
  is_active?: boolean,
  includeSystem?: boolean,
  enabled: boolean = true,
) {
  // includeSystem (SAC E2 D9): suma las entidades "[Retenciones] X" — usar SOLO
  // en selectores de PAGO (sus saldos nacen de liquidaciones, no de causaciones).
  return useQuery({
    queryKey: ["third-parties", "liabilities", search, is_active, includeSystem ?? false],
    queryFn: () =>
      thirdPartyService.getLiabilities({
        search,
        limit: SELECT_LIMIT,
        is_active,
        ...(includeSystem ? { include_system: true } : {}),
      }),
    enabled,
  });
}

export function useRetentionRows(enabled: boolean) {
  // F2 QA: el endpoint es flag-gated (kg_ledger_enabled) y este hook vive
  // tambien en una pagina COMPARTIDA con las orgs prod (PurchaseLiquidatePage)
  // — pasar SIEMPRE enabled=flagEnabled("kg_ledger_enabled"): sin flag, cero requests.
  return useQuery({
    queryKey: ["third-parties", "retention-entities"],
    queryFn: () => thirdPartyService.getRetentionRows(),
    enabled,
  });
}

export function useTaxEntityRows(enabled: boolean) {
  // Endpoint flag-gated (kg_ledger_enabled), igual que useRetentionRows.
  // La llave cuelga de ["third-parties"]: invalidateAfterTreasury la refresca
  // tras un pago.
  return useQuery({
    queryKey: ["third-parties", "tax-entities"],
    queryFn: () => thirdPartyService.getTaxEntityRows(),
    enabled,
  });
}

export function useCreateRetentionConfig() {
  // Colision (tipo, municipio, concepto) normalizados H4 → 409 con la tarifa
  // existente en el detail (editarla, no duplicar).
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: RetentionConfigCreate) => thirdPartyService.createRetentionConfig(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["third-parties"] });
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al crear la retención"));
    },
  });
}

export function useUpdateRetentionConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ configId, data }: { configId: string; data: RetentionConfigUpdate }) =>
      thirdPartyService.updateRetentionConfig(configId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["third-parties"] });
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error, "Error al actualizar la retención"));
    },
  });
}

export function useGenericThirdParties(search?: string, enabled: boolean = true) {
  return useQuery({
    queryKey: ["third-parties", "generic", search],
    queryFn: () => thirdPartyService.getGeneric({ search, limit: SELECT_LIMIT, is_active: true }),
    enabled,
  });
}

export function usePayableProviders(search?: string, enabled: boolean = true) {
  return useQuery({
    queryKey: ["third-parties", "payable-providers", search],
    queryFn: () => thirdPartyService.getPayableProviders({ search, limit: SELECT_LIMIT, is_active: true }),
    enabled,
  });
}

export function useThirdPartyCategoriesFlat(behaviorType?: string) {
  return useQuery({
    queryKey: ["third-party-categories", "flat", behaviorType],
    queryFn: () => thirdPartyCategoryService.getFlat(behaviorType),
  });
}
