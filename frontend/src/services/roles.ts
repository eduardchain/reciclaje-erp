import apiClient from "./api";
import type {
  MyPermissions,
  RoleListItem,
  RoleResponse,
  RoleCreate,
  RoleUpdate,
  PermissionsByModule,
  OrgMemberResponse,
} from "@/types/role";

export const rolesService = {
  getMyPermissions: () =>
    apiClient.get<MyPermissions>("/api/v1/roles/my-permissions").then((r) => r.data),

  getAll: () =>
    apiClient.get<RoleListItem[]>("/api/v1/roles").then((r) => r.data),

  getById: (id: string) =>
    apiClient.get<RoleResponse>(`/api/v1/roles/${id}`).then((r) => r.data),

  getPermissionsByModule: () =>
    apiClient.get<PermissionsByModule[]>("/api/v1/roles/permissions").then((r) => r.data),

  create: (data: RoleCreate) =>
    apiClient.post<RoleResponse>("/api/v1/roles", data).then((r) => r.data),

  update: (id: string, data: RoleUpdate) =>
    apiClient.patch<RoleResponse>(`/api/v1/roles/${id}`, data).then((r) => r.data),

  delete: (id: string) =>
    apiClient.delete(`/api/v1/roles/${id}`),

  getMembers: (orgId: string) =>
    apiClient.get<OrgMemberResponse[]>(`/api/v1/organizations/${orgId}/members`).then((r) => r.data),

  updateMemberRole: (orgId: string, userId: string, roleId: string) =>
    apiClient.patch<OrgMemberResponse>(`/api/v1/organizations/${orgId}/members/${userId}`, { role_id: roleId }).then((r) => r.data),
};
