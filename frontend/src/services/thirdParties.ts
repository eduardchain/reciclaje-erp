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

  getSuppliers: async (filters: Omit<ThirdPartyFilters, "role"> = {}): Promise<PaginatedResponse<ThirdPartyResponse>> => {
    const response = await apiClient.get<PaginatedResponse<ThirdPartyResponse>>("/api/v1/third-parties/suppliers", { params: filters });
    return response.data;
  },

  getCustomers: async (filters: Omit<ThirdPartyFilters, "role"> = {}): Promise<PaginatedResponse<ThirdPartyResponse>> => {
    const response = await apiClient.get<PaginatedResponse<ThirdPartyResponse>>("/api/v1/third-parties/customers", { params: filters });
    return response.data;
  },

  getProvisions: async (filters: Omit<ThirdPartyFilters, "role"> = {}): Promise<PaginatedResponse<ThirdPartyResponse>> => {
    const response = await apiClient.get<PaginatedResponse<ThirdPartyResponse>>("/api/v1/third-parties/provisions", { params: filters });
    return response.data;
  },

  getLiabilities: async (filters: Omit<ThirdPartyFilters, "role"> = {}): Promise<PaginatedResponse<ThirdPartyResponse>> => {
    const response = await apiClient.get<PaginatedResponse<ThirdPartyResponse>>("/api/v1/third-parties/liabilities", { params: filters });
    return response.data;
  },

  getPayableProviders: async (filters: Omit<ThirdPartyFilters, "role"> = {}): Promise<PaginatedResponse<ThirdPartyResponse>> => {
    const response = await apiClient.get<PaginatedResponse<ThirdPartyResponse>>("/api/v1/third-parties/payable-providers", { params: filters });
    return response.data;
  },

  getPayableSuppliers: async (filters: Omit<ThirdPartyFilters, "role"> = {}): Promise<PaginatedResponse<ThirdPartyResponse>> => {
    const response = await apiClient.get<PaginatedResponse<ThirdPartyResponse>>("/api/v1/third-parties/payable-suppliers", { params: filters });
    return response.data;
  },

  getInvestors: async (filters: Omit<ThirdPartyFilters, "role"> = {}): Promise<PaginatedResponse<ThirdPartyResponse>> => {
    const response = await apiClient.get<PaginatedResponse<ThirdPartyResponse>>("/api/v1/third-parties/investors", { params: filters });
    return response.data;
  },

  getGeneric: async (filters: Omit<ThirdPartyFilters, "role"> = {}): Promise<PaginatedResponse<ThirdPartyResponse>> => {
    const response = await apiClient.get<PaginatedResponse<ThirdPartyResponse>>("/api/v1/third-parties/generic", { params: filters });
    return response.data;
  },
};
