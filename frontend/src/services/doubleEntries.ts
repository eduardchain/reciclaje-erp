import apiClient from "./api";
import type { DoubleEntryResponse, DoubleEntryCreate } from "@/types/double-entry";
import type { PaginatedResponse } from "@/types/common";

interface DoubleEntryFilters {
  skip?: number;
  limit?: number;
  status?: string;
  search?: string;
  date_from?: string;
  date_to?: string;
}

export const doubleEntryService = {
  getAll: async (filters: DoubleEntryFilters = {}): Promise<PaginatedResponse<DoubleEntryResponse>> => {
    const response = await apiClient.get<PaginatedResponse<DoubleEntryResponse>>("/api/v1/double-entries", { params: filters });
    return response.data;
  },

  getById: async (id: string): Promise<DoubleEntryResponse> => {
    const response = await apiClient.get<DoubleEntryResponse>(`/api/v1/double-entries/${id}`);
    return response.data;
  },

  create: async (data: DoubleEntryCreate): Promise<DoubleEntryResponse> => {
    const response = await apiClient.post<DoubleEntryResponse>("/api/v1/double-entries", data);
    return response.data;
  },

  cancel: async (id: string): Promise<DoubleEntryResponse> => {
    const response = await apiClient.patch<DoubleEntryResponse>(`/api/v1/double-entries/${id}/cancel`);
    return response.data;
  },
};
