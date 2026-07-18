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
  status?: "draft" | "confirmed" | "annulled";
  /** Ciclo C: estado derivado unico (orden+compra) */
  display_status?: "registered" | "liquidated" | "annulled";
  /** Ciclo C: busca por #, placa, conductor, tercero o material */
  search?: string;
  /** Ciclo C: oldest = FIFO para la bandeja */
  sort?: "newest" | "oldest";
  /** Ciclo C: filtra entradas willard por mundo */
  willard_world?: "postconsumo" | "drosses";
  warehouse_id?: string;
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

  // B.2: draft -> confirmed (efectos inventario + kg nacen aca)
  confirm: async (id: string): Promise<InboundOrderResponse> => {
    const response = await apiClient.post<InboundOrderResponse>(
      `/api/v1/inbound-orders/${id}/confirm`
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
