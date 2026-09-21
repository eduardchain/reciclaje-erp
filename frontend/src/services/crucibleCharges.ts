import apiClient from "./api";
import { num } from "@/types/crucible-charge";
import type {
  CrucibleCharge,
  CrucibleChargeCreate,
  CrucibleChargeListResponse,
} from "@/types/crucible-charge";

// Regla de #107 (gate 6): un Decimal del backend llega como STRING y se
// coerciona AQUÍ, en la frontera, no en cada pantalla — `a - b` coerciona solo y
// `a + b` concatena, así que un preview puede "verse bien" con uno y no con otro.
const coerce = (c: CrucibleCharge): CrucibleCharge => ({
  ...c,
  quantity_kg: num(c.quantity_kg),
  lead_kg: num(c.lead_kg),
  maquila_amount: num(c.maquila_amount),
  inventory_out: c.inventory_out && { ...c.inventory_out, quantity: num(c.inventory_out.quantity) },
  inventory_in: c.inventory_in && { ...c.inventory_in, quantity: num(c.inventory_in.quantity) },
});

// Documentos de crisol (#107). Router gated por kg_ledger_enabled en backend;
// permisos reusan sales.* (los mismos de Salidas de Plomo).

export interface CrucibleChargeFilters {
  event_type?: string;
  status?: string;
  page?: number;
  page_size?: number;
}

const BASE = "/api/v1/crucible-charges";

export const crucibleChargeService = {
  getAll: async (filters: CrucibleChargeFilters = {}): Promise<CrucibleChargeListResponse> => {
    const { data } = await apiClient.get<CrucibleChargeListResponse>(BASE, { params: filters });
    return { ...data, items: data.items.map(coerce) };
  },

  getById: async (id: string): Promise<CrucibleCharge> => {
    const { data } = await apiClient.get<CrucibleCharge>(`${BASE}/${id}`);
    return coerce(data);
  },

  create: async (payload: CrucibleChargeCreate): Promise<CrucibleCharge> => {
    const { data } = await apiClient.post<CrucibleCharge>(BASE, payload);
    return coerce(data);
  },

  annul: async (id: string, reason: string): Promise<CrucibleCharge> => {
    const { data } = await apiClient.post<CrucibleCharge>(`${BASE}/${id}/annul`, { reason });
    return coerce(data);
  },
};
