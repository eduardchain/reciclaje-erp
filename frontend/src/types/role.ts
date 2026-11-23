/** Recolector al que esta acotado el usuario (SAC). Null = sin alcance. */
export interface CollectorScopeInfo {
  id: string;
  name: string;
}

export interface MyPermissions {
  role_id: string;
  role_name: string;
  role_display_name: string;
  is_admin: boolean;
  permissions: string[];
  assigned_account_ids: string[];
  collector_scope?: CollectorScopeInfo | null;
}

export interface RoleListItem {
  id: string;
  name: string;
  display_name: string;
  description: string | null;
  is_system_role: boolean;
  permission_count: number;
  member_count: number;
}

export interface PermissionResponse {
  id: string;
  code: string;
  display_name: string;
  module: string;
  description: string | null;
  sort_order: number;
}

export interface PermissionsByModule {
  module: string;
  module_display: string;
  permissions: PermissionResponse[];
}

export interface RoleResponse {
  id: string;
  organization_id: string;
  name: string;
  display_name: string;
  description: string | null;
  is_system_role: boolean;
  created_at: string;
  updated_at: string;
  permissions: PermissionResponse[];
}

export interface RoleCreate {
  name: string;
  display_name: string;
  description?: string;
  permission_codes: string[];
}

export interface RoleUpdate {
  display_name?: string;
  description?: string;
  permission_codes?: string[];
}

export interface OrgMemberResponse {
  id: string;
  user_id: string;
  organization_id: string;
  role_id: string;
  role_name: string | null;
  role_display_name: string | null;
  joined_at: string;
  user_email: string | null;
  user_full_name: string | null;
  account_ids: string[];
  org_count: number;
  /** D5: también pertenece a otra org ACTIVA → el reseteo lo hace soporte. */
  in_other_active_org?: boolean;
  collector_scope_id?: string | null;
}

export interface CollectorScopeResponse {
  user_id: string;
  collector_id: string | null;
  collector_name: string | null;
}

export interface CreateUserWithMembership {
  email: string;
  full_name: string;
  role_id: string;
  /** La elige el admin (mínimo 8). No vuelve en la respuesta. */
  password: string;
}
