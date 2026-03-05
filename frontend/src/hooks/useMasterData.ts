import { useQuery } from "@tanstack/react-query";
import { thirdPartyService } from "@/services/thirdParties";
import { materialService } from "@/services/materials";
import { warehouseService } from "@/services/warehouses";
import { moneyAccountService } from "@/services/moneyAccounts";
import { expenseCategoryService } from "@/services/masterData";

export function useSuppliers(search?: string) {
  return useQuery({
    queryKey: ["third-parties", "suppliers", search],
    queryFn: () => thirdPartyService.getAll({ role: "supplier", search, limit: 100 }),
  });
}

export function useCustomers(search?: string) {
  return useQuery({
    queryKey: ["third-parties", "customers", search],
    queryFn: () => thirdPartyService.getAll({ role: "customer", search, limit: 100 }),
  });
}

export function useThirdParties(filters?: { search?: string; role?: string }) {
  return useQuery({
    queryKey: ["third-parties", "list", filters],
    queryFn: () => thirdPartyService.getAll({ ...filters, limit: 100 }),
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
