import apiClient from "./api";
import type {
  DoubleEntryResponse,
  DoubleEntryCreate,
  DoubleEntryFullUpdate,
  DoubleEntryLiquidateRequest,
  PaginatedDoubleEntryResponse,
} from "@/types/double-entry";

interface DoubleEntryFilters {
  skip?: number;
  limit?: number;
  status?: string;
  search?: string;
  date_from?: string;
  date_to?: string;
  date_field?: "date" | "liquidated_at";
  sort_by?: string;
  sort_dir?: "asc" | "desc";
}

export const doubleEntryService = {
  getAll: async (filters: DoubleEntryFilters = {}): Promise<PaginatedDoubleEntryResponse> => {
    const params: Record<string, unknown> = { ...filters };
    if (!params.sort_by) delete params.sort_by;
    if (!params.sort_dir) delete params.sort_dir;
    const response = await apiClient.get<PaginatedDoubleEntryResponse>("/api/v1/double-entries", { params });
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

  edit: async (id: string, data: DoubleEntryFullUpdate): Promise<DoubleEntryResponse> => {
    const response = await apiClient.patch<DoubleEntryResponse>(`/api/v1/double-entries/${id}`, data);
    return response.data;
  },

  liquidate: async (id: string, data: DoubleEntryLiquidateRequest = {}): Promise<DoubleEntryResponse> => {
    const response = await apiClient.patch<DoubleEntryResponse>(`/api/v1/double-entries/${id}/liquidate`, data);
    return response.data;
  },

  cancel: async (id: string): Promise<DoubleEntryResponse> => {
    const response = await apiClient.patch<DoubleEntryResponse>(`/api/v1/double-entries/${id}/cancel`);
    return response.data;
  },
};
