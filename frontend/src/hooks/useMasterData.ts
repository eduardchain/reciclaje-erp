import { useQuery } from "@tanstack/react-query";
import { thirdPartyService } from "@/services/thirdParties";
import { materialService } from "@/services/materials";
import { warehouseService } from "@/services/warehouses";
import { moneyAccountService } from "@/services/moneyAccounts";
import { expenseCategoryService } from "@/services/masterData";
import { thirdPartyCategoryService } from "@/services/thirdPartyCategories";

export function useSuppliers(search?: string) {
  return useQuery({
    queryKey: ["third-parties", "suppliers", search],
    queryFn: () => thirdPartyService.getSuppliers({ search, limit: 100 }),
  });
}

export function useCustomers(search?: string) {
  return useQuery({
    queryKey: ["third-parties", "customers", search],
    queryFn: () => thirdPartyService.getCustomers({ search, limit: 100 }),
  });
}

export function useThirdParties(filters?: { search?: string; role?: string }, options?: { staleTime?: number }) {
  return useQuery({
    queryKey: ["third-parties", "list", filters],
    queryFn: () => thirdPartyService.getAll({ ...filters, limit: 100 }),
    ...options,
  });
}

export function useMaterials(search?: string) {
  return useQuery({
    queryKey: ["materials", "list", search],
    queryFn: () => materialService.getAll({ search, limit: 200 }),
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
    queryFn: () => thirdPartyService.getAll({ role: "investor", search, limit: 100 }),
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

export function useProvisions(search?: string) {
  return useQuery({
    queryKey: ["third-parties", "provisions", search],
    queryFn: () => thirdPartyService.getProvisions({ search, limit: 100 }),
  });
}

export function useLiabilities(search?: string) {
  return useQuery({
    queryKey: ["third-parties", "liabilities", search],
    queryFn: () => thirdPartyService.getLiabilities({ search, limit: 100 }),
  });
}

export function useGenericThirdParties(search?: string) {
  return useQuery({
    queryKey: ["third-parties", "generic", search],
    queryFn: () => thirdPartyService.getGeneric({ search, limit: 100 }),
  });
}

export function usePayableProviders(search?: string) {
  return useQuery({
    queryKey: ["third-parties", "payable-providers", search],
    queryFn: () => thirdPartyService.getPayableProviders({ search, limit: 100 }),
  });
}

export function useThirdPartyCategoriesFlat(behaviorType?: string) {
  return useQuery({
    queryKey: ["third-party-categories", "flat", behaviorType],
    queryFn: () => thirdPartyCategoryService.getFlat(behaviorType),
  });
}
