import apiClient from "./api";
import type { ThirdPartyCategoryResponse, ThirdPartyCategoryCreate, ThirdPartyCategoryUpdate, ThirdPartyCategoryFlatResponse } from "@/types/third-party-category";
import type { PaginatedResponse } from "@/types/common";

export const thirdPartyCategoryService = {
  getAll: async (): Promise<PaginatedResponse<ThirdPartyCategoryResponse>> => {
    const response = await apiClient.get<PaginatedResponse<ThirdPartyCategoryResponse>>("/api/v1/third-party-categories", { params: { limit: 100 } });
    return response.data;
  },
  create: async (data: ThirdPartyCategoryCreate): Promise<ThirdPartyCategoryResponse> => {
    const response = await apiClient.post<ThirdPartyCategoryResponse>("/api/v1/third-party-categories", data);
    return response.data;
  },
  update: async (id: string, data: ThirdPartyCategoryUpdate): Promise<ThirdPartyCategoryResponse> => {
    const response = await apiClient.patch<ThirdPartyCategoryResponse>(`/api/v1/third-party-categories/${id}`, data);
    return response.data;
  },
  getFlat: async (behaviorType?: string): Promise<ThirdPartyCategoryFlatResponse> => {
    const params: Record<string, string> = {};
    if (behaviorType) params.behavior_type = behaviorType;
    const response = await apiClient.get<ThirdPartyCategoryFlatResponse>("/api/v1/third-party-categories/flat", { params });
    return response.data;
  },
};
