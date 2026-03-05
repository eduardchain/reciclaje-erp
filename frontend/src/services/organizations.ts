import apiClient from "./api";
import type { OrganizationResponse } from "@/types/organization";

export const organizationService = {
  getOrganizations: async (): Promise<OrganizationResponse[]> => {
    const response = await apiClient.get<OrganizationResponse[]>("/api/v1/organizations/");
    return response.data;
  },

  getOrganization: async (id: string): Promise<OrganizationResponse> => {
    const response = await apiClient.get<OrganizationResponse>(`/api/v1/organizations/${id}`);
    return response.data;
  },
};
