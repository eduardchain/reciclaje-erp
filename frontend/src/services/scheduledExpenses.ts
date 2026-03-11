import apiClient from "./api";
import type { PaginatedResponse } from "@/types/common";
import type {
  ScheduledExpenseResponse,
  ScheduledExpenseCreate,
  ScheduledExpenseApplicationResponse,
} from "@/types/scheduled-expense";

interface ScheduledExpenseFilters {
  skip?: number;
  limit?: number;
  status?: string;
}

export const scheduledExpenseService = {
  getAll: async (filters: ScheduledExpenseFilters = {}): Promise<PaginatedResponse<ScheduledExpenseResponse>> => {
    const response = await apiClient.get<PaginatedResponse<ScheduledExpenseResponse>>("/api/v1/scheduled-expenses/", { params: filters });
    return response.data;
  },

  getById: async (id: string): Promise<ScheduledExpenseResponse> => {
    const response = await apiClient.get<ScheduledExpenseResponse>(`/api/v1/scheduled-expenses/${id}`);
    return response.data;
  },

  getPending: async (): Promise<ScheduledExpenseResponse[]> => {
    const response = await apiClient.get<ScheduledExpenseResponse[]>("/api/v1/scheduled-expenses/pending");
    return response.data;
  },

  create: async (data: ScheduledExpenseCreate): Promise<ScheduledExpenseResponse> => {
    const response = await apiClient.post<ScheduledExpenseResponse>("/api/v1/scheduled-expenses/", data);
    return response.data;
  },

  apply: async (id: string): Promise<ScheduledExpenseApplicationResponse> => {
    const response = await apiClient.post<ScheduledExpenseApplicationResponse>(`/api/v1/scheduled-expenses/${id}/apply`);
    return response.data;
  },

  cancel: async (id: string): Promise<ScheduledExpenseResponse> => {
    const response = await apiClient.post<ScheduledExpenseResponse>(`/api/v1/scheduled-expenses/${id}/cancel`);
    return response.data;
  },
};
