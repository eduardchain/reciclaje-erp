import apiClient from "./api";
import { num } from "@/types/willard-delivery";
import type {
  ControlDispatch,
  ControlDispatchCreate,
  ControlDispatchListResponse,
  ControlDispatchUpdate,
  RemissionBookResponse,
} from "@/types/control-dispatch";

// Salida de control (documentos de control). Router gated por
// kg_ledger_enabled en backend; permisos reusan sales.*.

export interface ControlDispatchFilters {
  status?: "registered" | "annulled";
  search?: string;
  date_from?: string;
  date_to?: string;
  skip?: number;
  limit?: number;
}

/** Talonario de remisiones (Q-75): Entradas + Salidas de control. */
export interface RemissionBookFilters {
  /** Solo dígitos, como texto: una remisión de 20 dígitos no cabe en un number. */
  remission_from?: string;
  remission_to?: string;
  date_from?: string;
  date_to?: string;
  search?: string;
  order?: "asc" | "desc";
  skip?: number;
  limit?: number;
}

const BASE = "/api/v1/control-dispatches";

// Coercion en la frontera (#107): cantidades y pesos llegan como string.
function coerce(d: ControlDispatch): ControlDispatch {
  return {
    ...d,
    lines: d.lines.map((l) => ({
      ...l,
      quantity: num(l.quantity),
      scale_weight_kg: l.scale_weight_kg === null ? null : num(l.scale_weight_kg),
    })),
  };
}

export const controlDispatchService = {
  getAll: async (filters: ControlDispatchFilters = {}): Promise<ControlDispatchListResponse> => {
    const { data } = await apiClient.get<ControlDispatchListResponse>(BASE, { params: filters });
    return { ...data, items: data.items.map(coerce) };
  },

  getById: async (id: string): Promise<ControlDispatch> => {
    const { data } = await apiClient.get<ControlDispatch>(`${BASE}/${id}`);
    return coerce(data);
  },

  create: async (payload: ControlDispatchCreate): Promise<ControlDispatch> => {
    const { data } = await apiClient.post<ControlDispatch>(BASE, payload);
    return coerce(data);
  },

  update: async (id: string, payload: ControlDispatchUpdate): Promise<ControlDispatch> => {
    const { data } = await apiClient.patch<ControlDispatch>(`${BASE}/${id}`, payload);
    return coerce(data);
  },

  annul: async (id: string, reason: string): Promise<ControlDispatch> => {
    const { data } = await apiClient.post<ControlDispatch>(`${BASE}/${id}/annul`, { reason });
    return coerce(data);
  },

  getRemissionBook: async (filters: RemissionBookFilters = {}): Promise<RemissionBookResponse> => {
    const { data } = await apiClient.get<RemissionBookResponse>("/api/v1/remissions", {
      params: filters,
    });
    return data;
  },
};
