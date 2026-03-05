import apiClient from "./api";
import type { ThirdPartyResponse, ThirdPartyCreate, ThirdPartyUpdate } from "@/types/third-party";
import type { PaginatedResponse } from "@/types/common";

interface ThirdPartyFilters {
  skip?: number;
  limit?: number;
  search?: string;
  role?: string;
}

export const thirdPartyService = {
  getAll: async (filters: ThirdPartyFilters = {}): Promise<PaginatedResponse<ThirdPartyResponse>> => {
    const response = await apiClient.get<PaginatedResponse<ThirdPartyResponse>>("/api/v1/third-parties", { params: filters });
    return response.data;
  },

  getById: async (id: string): Promise<ThirdPartyResponse> => {
    const response = await apiClient.get<ThirdPartyResponse>(`/api/v1/third-parties/${id}`);
    return response.data;
  },

  create: async (data: ThirdPartyCreate): Promise<ThirdPartyResponse> => {
    const response = await apiClient.post<ThirdPartyResponse>("/api/v1/third-parties", data);
    return response.data;
  },

  update: async (id: string, data: ThirdPartyUpdate): Promise<ThirdPartyResponse> => {
    const response = await apiClient.patch<ThirdPartyResponse>(`/api/v1/third-parties/${id}`, data);
    return response.data;
  },
};
