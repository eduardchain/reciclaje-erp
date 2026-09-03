import apiClient from "./api";
import type {
  WillardDelivery,
  WillardDeliveryCreate,
  WillardDeliveryListResponse,
  WillardDeliveryLiquidate,
  WillardDeliveryUpdate,
} from "@/types/willard-delivery";

// Salidas de plomo a Willard (W1). Router gated por kg_ledger_enabled en
// backend; permisos reusan sales.* (+ sales.review para certificar pesos).

export interface WillardDeliveryFilters {
  status?: string;
  delivery_type?: string;
  warehouse_id?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

const BASE = "/api/v1/willard-deliveries";

export const willardDeliveryService = {
  getAll: async (filters: WillardDeliveryFilters = {}): Promise<WillardDeliveryListResponse> => {
    const { data } = await apiClient.get<WillardDeliveryListResponse>(BASE, { params: filters });
    return data;
  },

  getById: async (id: string): Promise<WillardDelivery> => {
    const { data } = await apiClient.get<WillardDelivery>(`${BASE}/${id}`);
    return data;
  },

  create: async (payload: WillardDeliveryCreate): Promise<WillardDelivery> => {
    const { data } = await apiClient.post<WillardDelivery>(BASE, payload);
    return data;
  },

  update: async (id: string, payload: WillardDeliveryUpdate): Promise<WillardDelivery> => {
    const { data } = await apiClient.patch<WillardDelivery>(`${BASE}/${id}`, payload);
    return data;
  },

  review: async (id: string): Promise<WillardDelivery> => {
    const { data } = await apiClient.post<WillardDelivery>(`${BASE}/${id}/review`);
    return data;
  },

  liquidate: async (id: string, payload: WillardDeliveryLiquidate): Promise<WillardDelivery> => {
    const { data } = await apiClient.post<WillardDelivery>(`${BASE}/${id}/liquidate`, payload);
    return data;
  },

  annul: async (id: string, reason: string): Promise<WillardDelivery> => {
    const { data } = await apiClient.post<WillardDelivery>(`${BASE}/${id}/annul`, { reason });
    return data;
  },
};
