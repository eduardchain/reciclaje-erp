import apiClient from "./api";
import type {
  TransferDispatchCreate,
  TransferListResponse,
  TransferReceiveRequest,
  TransferResolveRequest,
  TransferResponse,
} from "@/types/transfer";

// SAC E3.1 — Traslados dos pasos. Router gated two_step_transfers_enabled.

export interface TransferFilters {
  status?: string;
  pending_receipt?: boolean;
  from_warehouse_id?: string;
  to_warehouse_id?: string;
  material_id?: string;
  date_from?: string;
  date_to?: string;
  skip?: number;
  limit?: number;
  sort?: "newest" | "oldest";
}

export const transferService = {
  getAll: async (filters: TransferFilters = {}): Promise<TransferListResponse> => {
    const response = await apiClient.get<TransferListResponse>("/api/v1/transfers", {
      params: filters,
    });
    return response.data;
  },

  getById: async (id: string): Promise<TransferResponse> => {
    const response = await apiClient.get<TransferResponse>(`/api/v1/transfers/${id}`);
    return response.data;
  },

  dispatch: async (data: TransferDispatchCreate): Promise<TransferResponse> => {
    const response = await apiClient.post<TransferResponse>("/api/v1/transfers", data);
    return response.data;
  },

  receive: async (id: string, data: TransferReceiveRequest): Promise<TransferResponse> => {
    const response = await apiClient.post<TransferResponse>(
      `/api/v1/transfers/${id}/receive`,
      data
    );
    return response.data;
  },

  resolve: async (id: string, data: TransferResolveRequest): Promise<TransferResponse> => {
    const response = await apiClient.post<TransferResponse>(
      `/api/v1/transfers/${id}/resolve`,
      data
    );
    return response.data;
  },

  annul: async (id: string, reason: string): Promise<TransferResponse> => {
    const response = await apiClient.post<TransferResponse>(
      `/api/v1/transfers/${id}/annul`,
      { reason }
    );
    return response.data;
  },
};
