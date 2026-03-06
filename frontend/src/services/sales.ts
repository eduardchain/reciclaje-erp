import apiClient from "./api";
import type { SaleResponse, SaleCreate, SaleFullUpdate, SaleLiquidateRequest } from "@/types/sale";
import type { PaginatedResponse } from "@/types/common";

interface SaleFilters {
  skip?: number;
  limit?: number;
  status?: string;
  customer_id?: string;
  date_from?: string;
  date_to?: string;
  search?: string;
}

export const saleService = {
  getAll: async (filters: SaleFilters = {}): Promise<PaginatedResponse<SaleResponse>> => {
    const response = await apiClient.get<PaginatedResponse<SaleResponse>>("/api/v1/sales", { params: filters });
    return response.data;
  },

  getById: async (id: string): Promise<SaleResponse> => {
    const response = await apiClient.get<SaleResponse>(`/api/v1/sales/${id}`);
    return response.data;
  },

  create: async (data: SaleCreate): Promise<SaleResponse> => {
    const response = await apiClient.post<SaleResponse>("/api/v1/sales", data);
    return response.data;
  },

  update: async (id: string, data: SaleFullUpdate): Promise<SaleResponse> => {
    const response = await apiClient.patch<SaleResponse>(`/api/v1/sales/${id}`, data);
    return response.data;
  },

  liquidate: async (id: string, data: SaleLiquidateRequest): Promise<SaleResponse> => {
    const response = await apiClient.patch<SaleResponse>(`/api/v1/sales/${id}/liquidate`, data);
    return response.data;
  },

  cancel: async (id: string): Promise<SaleResponse> => {
    const response = await apiClient.patch<SaleResponse>(`/api/v1/sales/${id}/cancel`);
    return response.data;
  },
};
