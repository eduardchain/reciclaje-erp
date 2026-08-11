import apiClient from "./api";
import type {
  InboundLiquidateRequest,
  InboundOrderCreate,
  InboundOrderListResponse,
  InboundOrderResponse,
  InboundOrderUpdate,
} from "@/types/inbound-order";

// Recepcion unificada (SAC E2): captura unica en patio. Router completo
// gated por flag kg_ledger_enabled en backend; permisos reusan purchases.*
// (+ purchases.review para la revision #93).

export interface InboundOrderFilters {
  inbound_type?: string;
  status?: "draft" | "reviewed" | "liquidated" | "confirmed" | "annulled";
  /** #93: estado UNICO visible (columna-driven) */
  display_status?: "registered" | "reviewed" | "liquidated" | "annulled";
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

  // B.2: draft -> confirmed (efectos inventario + kg nacen aca) — solo willard
  confirm: async (id: string): Promise<InboundOrderResponse> => {
    const response = await apiClient.post<InboundOrderResponse>(
      `/api/v1/inbound-orders/${id}/confirm`
    );
    return response.data;
  },

  // #93 D10: draft -> reviewed (permiso purchases.review) — solo tipo compra
  review: async (id: string): Promise<InboundOrderResponse> => {
    const response = await apiClient.post<InboundOrderResponse>(
      `/api/v1/inbound-orders/${id}/review`
    );
    return response.data;
  },

  // #93 D14: reparto -> N compras + descuadres + comision, atomico
  liquidate: async (
    id: string,
    data: InboundLiquidateRequest
  ): Promise<InboundOrderResponse> => {
    const response = await apiClient.post<InboundOrderResponse>(
      `/api/v1/inbound-orders/${id}/liquidate`,
      data
    );
    return response.data;
  },

  // #93 D20: reversa completa del evento de liquidacion (vuelve a Revisada,
  // conserva el reparto, sin quemar consecutivos)
  unliquidate: async (id: string): Promise<InboundOrderResponse> => {
    const response = await apiClient.post<InboundOrderResponse>(
      `/api/v1/inbound-orders/${id}/unliquidate`
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
