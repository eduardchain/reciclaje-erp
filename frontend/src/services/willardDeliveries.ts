import apiClient from "./api";
import { num } from "@/types/willard-delivery";
import type {
  WillardDeliverySummary,
  WillardDelivery,
  WillardDeliveryCreate,
  WillardDeliveryListResponse,
  WillardDeliveryLiquidate,
  WillardDeliveryUpdate,
} from "@/types/willard-delivery";

// Salidas de plomo a Willard (W1). Router gated por kg_ledger_enabled en
// backend; permisos reusan sales.*. El paso de revision se retiro (Hugo, 28-ago).

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
  // Los Decimal llegan como string: se coercionan AQUÍ (regla de #107).
  getSummary: async (dateFrom: string, dateTo: string): Promise<WillardDeliverySummary> => {
    const { data } = await apiClient.get<WillardDeliverySummary>(`${BASE}/summary`, {
      params: { date_from: dateFrom, date_to: dateTo },
    });
    return {
      ...data,
      rows: data.rows.map((r) => ({
        ...r,
        lead_kg: num(r.lead_kg),
        maquila_amount: num(r.maquila_amount),
        freight_amount: num(r.freight_amount),
        plant_credit_amount: num(r.plant_credit_amount),
        crucible_amount: num(r.crucible_amount),
        kept_by_billing_sede: num(r.kept_by_billing_sede),
      })),
    };
  },

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

  liquidate: async (id: string, payload: WillardDeliveryLiquidate): Promise<WillardDelivery> => {
    const { data } = await apiClient.post<WillardDelivery>(`${BASE}/${id}/liquidate`, payload);
    return data;
  },

  annul: async (id: string, reason: string): Promise<WillardDelivery> => {
    const { data } = await apiClient.post<WillardDelivery>(`${BASE}/${id}/annul`, { reason });
    return data;
  },
};
