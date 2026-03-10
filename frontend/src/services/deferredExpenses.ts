import apiClient from "./api";
import type { PaginatedResponse } from "@/types/common";
import type {
  DeferredExpenseResponse,
  DeferredExpenseCreate,
  DeferredApplicationResponse,
} from "@/types/deferred-expense";

interface DeferredExpenseFilters {
  skip?: number;
  limit?: number;
  status?: string;
}

export const deferredExpenseService = {
  getAll: async (filters: DeferredExpenseFilters = {}): Promise<PaginatedResponse<DeferredExpenseResponse>> => {
    const response = await apiClient.get<PaginatedResponse<DeferredExpenseResponse>>("/api/v1/deferred-expenses/", { params: filters });
    return response.data;
  },

  getById: async (id: string): Promise<DeferredExpenseResponse> => {
    const response = await apiClient.get<DeferredExpenseResponse>(`/api/v1/deferred-expenses/${id}`);
    return response.data;
  },

  getPending: async (): Promise<DeferredExpenseResponse[]> => {
    const response = await apiClient.get<DeferredExpenseResponse[]>("/api/v1/deferred-expenses/pending");
    return response.data;
  },

  create: async (data: DeferredExpenseCreate): Promise<DeferredExpenseResponse> => {
    const response = await apiClient.post<DeferredExpenseResponse>("/api/v1/deferred-expenses/", data);
    return response.data;
  },

  apply: async (id: string): Promise<DeferredApplicationResponse> => {
    const response = await apiClient.post<DeferredApplicationResponse>(`/api/v1/deferred-expenses/${id}/apply`);
    return response.data;
  },

  cancel: async (id: string): Promise<DeferredExpenseResponse> => {
    const response = await apiClient.post<DeferredExpenseResponse>(`/api/v1/deferred-expenses/${id}/cancel`);
    return response.data;
  },
};
