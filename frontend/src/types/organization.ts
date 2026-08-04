import type { BaseEntity } from "./common";

export type MemberRole = "admin" | "manager" | "accountant" | "user" | "viewer";

export interface OrganizationResponse extends BaseEntity {
  name: string;
  slug: string;
  logo_url: string | null;
  subscription_plan: string;
  subscription_status: string;
  max_users: number;
  is_active?: boolean;
  member_role?: string | null;
  settings?: Record<string, unknown> | null; // Flags/parametros SAC (D3) — NULL = defaults
}

export interface OrganizationCreate {
  name: string;
  slug?: string | null;
}

// --- Tipos para panel Sistema (super admin) ---

export interface SystemOrgResponse {
  id: string;
  name: string;
  slug: string;
  subscription_plan: string;
  subscription_status: string;
  max_users: number;
  is_active: boolean;
  member_count: number;
  created_at: string;
  settings?: Record<string, unknown> | null;
}

export interface SystemOrgCreate {
  name: string;
  admin_email: string;
  admin_full_name?: string | null;
}

export interface SystemOrgUpdate {
  name?: string;
  max_users?: number;
  subscription_plan?: string;
  subscription_status?: string;
  is_active?: boolean;
  // Semantica REPLACE: mandar SIEMPRE el dict completo (un subset borra el resto)
  settings?: Record<string, unknown>;
}

export interface SystemUserMembership {
  organization_id: string;
  organization_name: string;
  role_name: string;
  role_display_name: string;
}

export interface SystemUserResponse {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  memberships: SystemUserMembership[];
}

export interface AddUserToOrgRequest {
  organization_id: string;
  role_id: string;
}

export interface OrganizationMemberResponse {
  id: string;
  user_id: string;
  organization_id: string;
  role: MemberRole;
  joined_at: string;
  user_email?: string | null;
  user_full_name?: string | null;
}
