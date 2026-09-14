import apiClient from "./api";
import type {
  CrucibleCharge,
  CrucibleChargeCreate,
  CrucibleChargeListResponse,
} from "@/types/crucible-charge";

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
    return data;
  },

  getById: async (id: string): Promise<CrucibleCharge> => {
    const { data } = await apiClient.get<CrucibleCharge>(`${BASE}/${id}`);
    return data;
  },

  create: async (payload: CrucibleChargeCreate): Promise<CrucibleCharge> => {
    const { data } = await apiClient.post<CrucibleCharge>(BASE, payload);
    return data;
  },

  annul: async (id: string, reason: string): Promise<CrucibleCharge> => {
    const { data } = await apiClient.post<CrucibleCharge>(`${BASE}/${id}/annul`, { reason });
    return data;
  },
};
