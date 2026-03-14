import apiClient from "./api";
import type {
  SystemOrgResponse,
  SystemOrgCreate,
  SystemOrgUpdate,
  SystemUserResponse,
  AddUserToOrgRequest,
} from "@/types/organization";

export const systemService = {
  // Organizaciones
  getOrganizations: async (includeInactive = false): Promise<SystemOrgResponse[]> => {
    const response = await apiClient.get<SystemOrgResponse[]>("/api/v1/system/organizations", {
      params: includeInactive ? { include_inactive: true } : undefined,
    });
    return response.data;
  },

  createOrganization: async (data: SystemOrgCreate): Promise<SystemOrgResponse> => {
    const response = await apiClient.post<SystemOrgResponse>("/api/v1/system/organizations", data);
    return response.data;
  },

  updateOrganization: async (id: string, data: SystemOrgUpdate): Promise<SystemOrgResponse> => {
    const response = await apiClient.patch<SystemOrgResponse>(`/api/v1/system/organizations/${id}`, data);
    return response.data;
  },

  deleteOrganization: async (id: string): Promise<{ message: string; orphaned_users_deactivated: number }> => {
    const response = await apiClient.delete(`/api/v1/system/organizations/${id}`);
    return response.data;
  },

  // Usuarios
  getUsers: async (): Promise<SystemUserResponse[]> => {
    const response = await apiClient.get<SystemUserResponse[]>("/api/v1/system/users");
    return response.data;
  },

  addUserToOrg: async (userId: string, data: AddUserToOrgRequest) => {
    const response = await apiClient.post(`/api/v1/system/users/${userId}/add-to-org`, data);
    return response.data;
  },
};
