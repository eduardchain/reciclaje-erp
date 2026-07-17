import apiClient from "./api";
import type {
  ThirdPartyResponse,
  ThirdPartyCreate,
  ThirdPartyUpdate,
  RetentionEntityResponse,
  RetentionEntityCreate,
} from "@/types/third-party";
import type { PaginatedResponse } from "@/types/common";

interface ThirdPartyFilters {
  skip?: number;
  limit?: number;
  search?: string;
  role?: string;
  is_active?: boolean;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
}

export const thirdPartyService = {
  getAll: async (filters: ThirdPartyFilters = {}): Promise<PaginatedResponse<ThirdPartyResponse>> => {
    // Omitir sort_by/sort_dir si son undefined para no contaminar el queryKey
    // ni mandar params vacios. Axios serializa undefined como omision, pero ser
    // explicitos evita que se serialice "sort_by=" cuando alguien pasa "".
    const params: Record<string, unknown> = { ...filters };
    if (!params.sort_by) delete params.sort_by;
    if (!params.sort_dir) delete params.sort_dir;
    const response = await apiClient.get<PaginatedResponse<ThirdPartyResponse>>("/api/v1/third-parties", { params });
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

  deactivate: async (id: string): Promise<ThirdPartyResponse> => {
    const response = await apiClient.delete<ThirdPartyResponse>(`/api/v1/third-parties/${id}`);
    return response.data;
  },

  reactivate: async (id: string): Promise<ThirdPartyResponse> => {
    const response = await apiClient.patch<ThirdPartyResponse>(`/api/v1/third-parties/${id}/reactivate`);
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

  getLiabilities: async (
    filters: (Omit<ThirdPartyFilters, "role"> & { include_system?: boolean }) = {}
  ): Promise<PaginatedResponse<ThirdPartyResponse>> => {
    // include_system=true (SAC E2 D9): incluye entidades sistema "[Retenciones] X"
    // — necesario en el selector de Pago de Pasivo para poder pagarlas.
    const response = await apiClient.get<PaginatedResponse<ThirdPartyResponse>>("/api/v1/third-parties/liabilities", { params: filters });
    return response.data;
  },

  // Entidades "[Retenciones] X" estructuradas (addendum paquete UX) — endpoints
  // flag-gated (kg_ledger_enabled): NO llamar sin gate en el consumidor (F2 QA).
  getRetentionEntities: async (): Promise<RetentionEntityResponse[]> => {
    const response = await apiClient.get<RetentionEntityResponse[]>("/api/v1/third-parties/retention-entities");
    return response.data;
  },

  createRetentionEntity: async (data: RetentionEntityCreate): Promise<RetentionEntityResponse> => {
    const response = await apiClient.post<RetentionEntityResponse>("/api/v1/third-parties/retention-entities", data);
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
