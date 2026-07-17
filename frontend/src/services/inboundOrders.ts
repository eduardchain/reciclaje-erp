import apiClient from "./api";
import type {
  InboundOrderCreate,
  InboundOrderListResponse,
  InboundOrderResponse,
  InboundOrderUpdate,
} from "@/types/inbound-order";

// Recepcion unificada (SAC E2): captura unica en patio. Router completo
// gated por flag kg_ledger_enabled en backend; permisos reusan purchases.*.

export interface InboundOrderFilters {
  inbound_type?: string;
  status?: "confirmed" | "annulled";
  third_party_id?: string;
  date_from?: string;
  date_to?: string;
  skip?: number;
  limit?: number;
}

export const inboundOrderService = {
  getAll: async (filters: InboundOrderFilters = {}): Promise<InboundOrderListResponse> => {
    const response = await apiClient.get<InboundOrderListResponse>(
      "/api/v1/inbound-orders",
      { params: filters }
    );
    return response.data;
  },

  getById: async (id: string): Promise<InboundOrderResponse> => {
    const response = await apiClient.get<InboundOrderResponse>(`/api/v1/inbound-orders/${id}`);
    return response.data;
  },

  create: async (data: InboundOrderCreate): Promise<InboundOrderResponse> => {
    const response = await apiClient.post<InboundOrderResponse>("/api/v1/inbound-orders", data);
    return response.data;
  },

  update: async (id: string, data: InboundOrderUpdate): Promise<InboundOrderResponse> => {
    const response = await apiClient.patch<InboundOrderResponse>(
      `/api/v1/inbound-orders/${id}`,
      data
    );
    return response.data;
  },

  annul: async (id: string, reason: string): Promise<InboundOrderResponse> => {
    const response = await apiClient.post<InboundOrderResponse>(
      `/api/v1/inbound-orders/${id}/annul`,
      { reason }
    );
    return response.data;
  },
};
