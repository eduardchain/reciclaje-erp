import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getApiErrorMessage } from "@/utils/formatters";
import { thirdPartyService } from "@/services/thirdParties";
import { materialService } from "@/services/materials";
import { warehouseService } from "@/services/warehouses";
import { moneyAccountService } from "@/services/moneyAccounts";
import { businessUnitService, expenseCategoryService, priceListService, materialCategoryService } from "@/services/masterData";
import type { ThirdPartyCreate, ThirdPartyUpdate } from "@/types/third-party";
import type { MaterialCreate, MaterialUpdate, MaterialCategoryCreate, MaterialCategoryUpdate } from "@/types/material";
import type { WarehouseCreate, WarehouseUpdate } from "@/types/warehouse";
import type { MoneyAccountCreate, MoneyAccountUpdate } from "@/types/money-account";
import type { BusinessUnitCreate, BusinessUnitUpdate, ExpenseCategoryCreate, ExpenseCategoryUpdate, PriceListCreate } from "@/types/config";

// --- Third Parties ---

export function useCreateThirdParty() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ThirdPartyCreate) => thirdPartyService.create(data),
    onSuccess: () => { toast.success("Tercero creado"); qc.invalidateQueries({ queryKey: ["third-parties"] }); },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error")),
  });
}

export function useUpdateThirdParty() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ThirdPartyUpdate }) => thirdPartyService.update(id, data),
    onSuccess: () => { toast.success("Tercero actualizado"); qc.invalidateQueries({ queryKey: ["third-parties"] }); },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error")),
  });
}

// --- Materials ---

export function useCreateMaterial() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: MaterialCreate) => materialService.create(data),
    onSuccess: () => { toast.success("Material creado"); qc.invalidateQueries({ queryKey: ["materials"] }); },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error")),
  });
}

export function useUpdateMaterial() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: MaterialUpdate }) => materialService.update(id, data),
    onSuccess: () => { toast.success("Material actualizado"); qc.invalidateQueries({ queryKey: ["materials"] }); },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error")),
  });
}

// --- Material Categories ---

export function useMaterialCategories() {
  return useQuery({
    queryKey: ["materials", "categories"],
    queryFn: () => materialCategoryService.getAll(),
  });
}

export function useCreateMaterialCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: MaterialCategoryCreate) => materialCategoryService.create(data),
    onSuccess: () => { toast.success("Categoria creada"); qc.invalidateQueries({ queryKey: ["materials", "categories"] }); },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error")),
  });
}

export function useUpdateMaterialCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: MaterialCategoryUpdate }) => materialCategoryService.update(id, data),
    onSuccess: () => { toast.success("Categoria actualizada"); qc.invalidateQueries({ queryKey: ["materials", "categories"] }); },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error")),
  });
}

// --- Warehouses ---

export function useCreateWarehouse() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: WarehouseCreate) => warehouseService.create(data),
    onSuccess: () => { toast.success("Bodega creada"); qc.invalidateQueries({ queryKey: ["warehouses"] }); },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error")),
  });
}

export function useUpdateWarehouse() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: WarehouseUpdate }) => warehouseService.update(id, data),
    onSuccess: () => { toast.success("Bodega actualizada"); qc.invalidateQueries({ queryKey: ["warehouses"] }); },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error")),
  });
}

// --- Money Accounts ---

export function useCreateMoneyAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: MoneyAccountCreate) => moneyAccountService.create(data),
    onSuccess: () => { toast.success("Cuenta creada"); qc.invalidateQueries({ queryKey: ["money-accounts"] }); },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error")),
  });
}

export function useUpdateMoneyAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: MoneyAccountUpdate }) => moneyAccountService.update(id, data),
    onSuccess: () => { toast.success("Cuenta actualizada"); qc.invalidateQueries({ queryKey: ["money-accounts"] }); },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error")),
  });
}

// --- Business Units ---

export function useBusinessUnits() {
  return useQuery({
    queryKey: ["business-units", "list"],
    queryFn: () => businessUnitService.getAll(),
  });
}

export function useCreateBusinessUnit() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: BusinessUnitCreate) => businessUnitService.create(data),
    onSuccess: () => { toast.success("Unidad de negocio creada"); qc.invalidateQueries({ queryKey: ["business-units"] }); },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error")),
  });
}

export function useUpdateBusinessUnit() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: BusinessUnitUpdate }) => businessUnitService.update(id, data),
    onSuccess: () => { toast.success("Unidad de negocio actualizada"); qc.invalidateQueries({ queryKey: ["business-units"] }); },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error")),
  });
}

// --- Expense Categories ---

export function useExpenseCategoriesList() {
  return useQuery({
    queryKey: ["expense-categories", "list"],
    queryFn: () => expenseCategoryService.getAll(),
  });
}

export function useCreateExpenseCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ExpenseCategoryCreate) => expenseCategoryService.create(data),
    onSuccess: () => { toast.success("Categoria de gasto creada"); qc.invalidateQueries({ queryKey: ["expense-categories"] }); },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error")),
  });
}

export function useUpdateExpenseCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ExpenseCategoryUpdate }) => expenseCategoryService.update(id, data),
    onSuccess: () => { toast.success("Categoria actualizada"); qc.invalidateQueries({ queryKey: ["expense-categories"] }); },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error")),
  });
}

// --- Price Lists ---

export function usePriceLists(materialId?: string) {
  return useQuery({
    queryKey: ["price-lists", materialId],
    queryFn: () => priceListService.getAll(materialId),
  });
}

export function useCreatePriceList() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: PriceListCreate) => priceListService.create(data),
    onSuccess: () => { toast.success("Precio registrado"); qc.invalidateQueries({ queryKey: ["price-lists"] }); },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, "Error")),
  });
}
