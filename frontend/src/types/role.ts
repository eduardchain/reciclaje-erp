export interface MyPermissions {
  role_id: string;
  role_name: string;
  role_display_name: string;
  is_admin: boolean;
  permissions: string[];
  assigned_account_ids: string[];
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
}

export interface CreateUserWithMembership {
  email: string;
  full_name: string;
  role_id: string;
}
