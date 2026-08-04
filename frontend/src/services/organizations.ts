import apiClient from "./api";
import type { OrganizationResponse } from "@/types/organization";

export const organizationService = {
  /**
   * Ajustes 2026-08-03 (C): unica clave de settings que un admin de org puede
   * escribir. Los feature flags siguen siendo exclusivos del superusuario.
   * No hay GET hermano: la lista se lee con useOrgSettings (H2).
   */
  updateWillardDistributionCenters: async (
    centers: string[],
  ): Promise<{ centers: string[]; warnings: string[] }> => {
    const response = await apiClient.put(
      "/api/v1/organizations/settings/willard-distribution-centers",
      { centers },
    );
    return response.data;
  },

  getOrganizations: async (): Promise<OrganizationResponse[]> => {
    const response = await apiClient.get<OrganizationResponse[]>("/api/v1/organizations");
    return response.data;
  },

  getOrganization: async (id: string): Promise<OrganizationResponse> => {
    const response = await apiClient.get<OrganizationResponse>(`/api/v1/organizations/${id}`);
    return response.data;
  },
};
