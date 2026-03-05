import apiClient from "./api";
import type { MoneyAccountResponse, MoneyAccountCreate, MoneyAccountUpdate } from "@/types/money-account";
import type { PaginatedResponse } from "@/types/common";

export const moneyAccountService = {
  getAll: async (): Promise<PaginatedResponse<MoneyAccountResponse>> => {
    const response = await apiClient.get<PaginatedResponse<MoneyAccountResponse>>("/api/v1/money-accounts", { params: { limit: 100 } });
    return response.data;
  },

  create: async (data: MoneyAccountCreate): Promise<MoneyAccountResponse> => {
    const response = await apiClient.post<MoneyAccountResponse>("/api/v1/money-accounts", data);
    return response.data;
  },

  update: async (id: string, data: MoneyAccountUpdate): Promise<MoneyAccountResponse> => {
    const response = await apiClient.patch<MoneyAccountResponse>(`/api/v1/money-accounts/${id}`, data);
    return response.data;
  },
};
