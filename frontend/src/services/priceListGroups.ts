import apiClient from "./api";
import type { PriceTableResponse } from "@/types/config";
import type {
  PriceListGroupCreate,
  PriceListGroupResponse,
  PriceListGroupUpdate,
  PriceListGroupsResponse,
  SeedResultResponse,
  SupplierMembershipsResponse,
} from "@/types/price-list-group";

const BASE = "/api/v1/price-list-groups";

export const priceListGroupService = {
  getAll: async (includeInactive = false): Promise<PriceListGroupsResponse> => {
    const response = await apiClient.get<PriceListGroupsResponse>(BASE, {
      params: { include_inactive: includeInactive },
    });
    return response.data;
  },

  create: async (data: PriceListGroupCreate): Promise<SeedResultResponse> => {
    const response = await apiClient.post<SeedResultResponse>(BASE, data);
    return response.data;
  },

  update: async (id: string, data: PriceListGroupUpdate): Promise<PriceListGroupResponse> => {
    const response = await apiClient.patch<PriceListGroupResponse>(`${BASE}/${id}`, data);
    return response.data;
  },

  /** Hoja de calculo de una lista: TODOS los materiales activos, con precio o vacios. */
  getTable: async (id: string): Promise<PriceTableResponse> => {
    const response = await apiClient.get<PriceTableResponse>(`${BASE}/${id}/table`);
    return response.data;
  },

  /** Proveedores de material con la lista a la que pertenecen hoy. */
  getSuppliers: async (): Promise<SupplierMembershipsResponse> => {
    const response = await apiClient.get<SupplierMembershipsResponse>(`${BASE}/suppliers`);
    return response.data;
  },

  setMembers: async (id: string, thirdPartyIds: string[]): Promise<SupplierMembershipsResponse> => {
    const response = await apiClient.put<SupplierMembershipsResponse>(`${BASE}/${id}/members`, {
      third_party_ids: thirdPartyIds,
    });
    return response.data;
  },
};
