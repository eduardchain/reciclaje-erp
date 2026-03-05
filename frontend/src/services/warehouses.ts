import apiClient from "./api";
import type { WarehouseResponse, WarehouseCreate, WarehouseUpdate } from "@/types/warehouse";
import type { PaginatedResponse } from "@/types/common";

export const warehouseService = {
  getAll: async (): Promise<PaginatedResponse<WarehouseResponse>> => {
    const response = await apiClient.get<PaginatedResponse<WarehouseResponse>>("/api/v1/warehouses", { params: { limit: 100 } });
    return response.data;
  },

  create: async (data: WarehouseCreate): Promise<WarehouseResponse> => {
    const response = await apiClient.post<WarehouseResponse>("/api/v1/warehouses", data);
    return response.data;
  },

  update: async (id: string, data: WarehouseUpdate): Promise<WarehouseResponse> => {
    const response = await apiClient.patch<WarehouseResponse>(`/api/v1/warehouses/${id}`, data);
    return response.data;
  },
};
