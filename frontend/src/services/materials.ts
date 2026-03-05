import apiClient from "./api";
import type { MaterialResponse, MaterialCreate, MaterialUpdate, MaterialCategoryResponse } from "@/types/material";
import type { PaginatedResponse } from "@/types/common";

interface MaterialFilters {
  skip?: number;
  limit?: number;
  search?: string;
  category_id?: string;
}

export const materialService = {
  getAll: async (filters: MaterialFilters = {}): Promise<PaginatedResponse<MaterialResponse>> => {
    const response = await apiClient.get<PaginatedResponse<MaterialResponse>>("/api/v1/materials", { params: filters });
    return response.data;
  },

  getById: async (id: string): Promise<MaterialResponse> => {
    const response = await apiClient.get<MaterialResponse>(`/api/v1/materials/${id}`);
    return response.data;
  },

  create: async (data: MaterialCreate): Promise<MaterialResponse> => {
    const response = await apiClient.post<MaterialResponse>("/api/v1/materials", data);
    return response.data;
  },

  update: async (id: string, data: MaterialUpdate): Promise<MaterialResponse> => {
    const response = await apiClient.patch<MaterialResponse>(`/api/v1/materials/${id}`, data);
    return response.data;
  },

  getCategories: async (): Promise<PaginatedResponse<MaterialCategoryResponse>> => {
    const response = await apiClient.get<PaginatedResponse<MaterialCategoryResponse>>("/api/v1/materials/categories");
    return response.data;
  },
};
