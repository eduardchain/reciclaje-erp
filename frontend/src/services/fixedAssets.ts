import apiClient from "./api";
import type { PaginatedResponse } from "@/types/common";
import type {
  FixedAsset,
  FixedAssetCreate,
  FixedAssetUpdate,
  ApplyPendingResult,
} from "@/types/fixed-asset";

interface FixedAssetFilters {
  skip?: number;
  limit?: number;
  status?: string;
}

export const fixedAssetService = {
  getAll: async (filters: FixedAssetFilters = {}): Promise<PaginatedResponse<FixedAsset>> => {
    const response = await apiClient.get<PaginatedResponse<FixedAsset>>("/api/v1/fixed-assets/", { params: filters });
    return response.data;
  },

  getById: async (id: string): Promise<FixedAsset> => {
    const response = await apiClient.get<FixedAsset>(`/api/v1/fixed-assets/${id}`);
    return response.data;
  },

  create: async (data: FixedAssetCreate): Promise<FixedAsset> => {
    const response = await apiClient.post<FixedAsset>("/api/v1/fixed-assets/", data);
    return response.data;
  },

  update: async (id: string, data: FixedAssetUpdate): Promise<FixedAsset> => {
    const response = await apiClient.patch<FixedAsset>(`/api/v1/fixed-assets/${id}`, data);
    return response.data;
  },

  depreciate: async (id: string): Promise<FixedAsset> => {
    const response = await apiClient.post<FixedAsset>(`/api/v1/fixed-assets/${id}/depreciate`);
    return response.data;
  },

  applyPending: async (): Promise<ApplyPendingResult[]> => {
    const response = await apiClient.post<ApplyPendingResult[]>("/api/v1/fixed-assets/apply-pending");
    return response.data;
  },

  dispose: async (id: string, reason: string): Promise<FixedAsset> => {
    const response = await apiClient.post<FixedAsset>(`/api/v1/fixed-assets/${id}/dispose`, { reason });
    return response.data;
  },

  cancel: async (id: string): Promise<FixedAsset> => {
    const response = await apiClient.post<FixedAsset>(`/api/v1/fixed-assets/${id}/cancel`);
    return response.data;
  },
};
