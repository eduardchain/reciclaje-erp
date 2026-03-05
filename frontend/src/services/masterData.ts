import apiClient from "./api";
import type { BusinessUnitResponse, BusinessUnitCreate, BusinessUnitUpdate, ExpenseCategoryResponse, ExpenseCategoryCreate, ExpenseCategoryUpdate, PriceListResponse, PriceListCreate } from "@/types/config";
import type { MaterialCategoryResponse, MaterialCategoryCreate, MaterialCategoryUpdate } from "@/types/material";
import type { PaginatedResponse } from "@/types/common";

export const businessUnitService = {
  getAll: async (): Promise<PaginatedResponse<BusinessUnitResponse>> => {
    const response = await apiClient.get<PaginatedResponse<BusinessUnitResponse>>("/api/v1/business-units", { params: { limit: 100 } });
    return response.data;
  },
  create: async (data: BusinessUnitCreate): Promise<BusinessUnitResponse> => {
    const response = await apiClient.post<BusinessUnitResponse>("/api/v1/business-units", data);
    return response.data;
  },
  update: async (id: string, data: BusinessUnitUpdate): Promise<BusinessUnitResponse> => {
    const response = await apiClient.patch<BusinessUnitResponse>(`/api/v1/business-units/${id}`, data);
    return response.data;
  },
};

export const expenseCategoryService = {
  getAll: async (): Promise<PaginatedResponse<ExpenseCategoryResponse>> => {
    const response = await apiClient.get<PaginatedResponse<ExpenseCategoryResponse>>("/api/v1/expense-categories", { params: { limit: 100 } });
    return response.data;
  },
  create: async (data: ExpenseCategoryCreate): Promise<ExpenseCategoryResponse> => {
    const response = await apiClient.post<ExpenseCategoryResponse>("/api/v1/expense-categories", data);
    return response.data;
  },
  update: async (id: string, data: ExpenseCategoryUpdate): Promise<ExpenseCategoryResponse> => {
    const response = await apiClient.patch<ExpenseCategoryResponse>(`/api/v1/expense-categories/${id}`, data);
    return response.data;
  },
};

export const priceListService = {
  getAll: async (materialId?: string): Promise<PaginatedResponse<PriceListResponse>> => {
    const response = await apiClient.get<PaginatedResponse<PriceListResponse>>("/api/v1/price-lists", { params: { material_id: materialId, limit: 200 } });
    return response.data;
  },
  create: async (data: PriceListCreate): Promise<PriceListResponse> => {
    const response = await apiClient.post<PriceListResponse>("/api/v1/price-lists", data);
    return response.data;
  },
};

export const materialCategoryService = {
  getAll: async (): Promise<PaginatedResponse<MaterialCategoryResponse>> => {
    const response = await apiClient.get<PaginatedResponse<MaterialCategoryResponse>>("/api/v1/materials/categories", { params: { limit: 100 } });
    return response.data;
  },
  create: async (data: MaterialCategoryCreate): Promise<MaterialCategoryResponse> => {
    const response = await apiClient.post<MaterialCategoryResponse>("/api/v1/materials/categories", data);
    return response.data;
  },
  update: async (id: string, data: MaterialCategoryUpdate): Promise<MaterialCategoryResponse> => {
    const response = await apiClient.patch<MaterialCategoryResponse>(`/api/v1/materials/categories/${id}`, data);
    return response.data;
  },
};
