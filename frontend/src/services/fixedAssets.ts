import apiClient from "./api";
import type { PaginatedResponse } from "@/types/common";
import type {
  FixedAsset,
  FixedAssetCreate,
  FixedAssetUpdate,
  FixedAssetSellRequest,
  ApplyPendingResult,
  AssetRevaluationCreate,
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

  sell: async (id: string, data: FixedAssetSellRequest): Promise<FixedAsset> => {
    const response = await apiClient.post<FixedAsset>(`/api/v1/fixed-assets/${id}/sell`, data);
    return response.data;
  },

  annulSale: async (id: string, reason: string): Promise<FixedAsset> => {
    const response = await apiClient.post<FixedAsset>(`/api/v1/fixed-assets/${id}/sale/annul`, { reason });
    return response.data;
  },

  revalue: async (id: string, data: AssetRevaluationCreate): Promise<FixedAsset> => {
    const response = await apiClient.post<FixedAsset>(`/api/v1/fixed-assets/${id}/revalue`, data);
    return response.data;
  },

  annulRevaluation: async (id: string, revaluationId: string, reason: string): Promise<FixedAsset> => {
    const response = await apiClient.post<FixedAsset>(
      `/api/v1/fixed-assets/${id}/revaluations/${revaluationId}/annul`,
      { reason },
    );
    return response.data;
  },
};
