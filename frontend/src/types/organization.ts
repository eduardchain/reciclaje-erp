import type { BaseEntity } from "./common";

export type MemberRole = "admin" | "manager" | "accountant" | "user" | "viewer";

export interface OrganizationResponse extends BaseEntity {
  name: string;
  slug: string;
  logo_url: string | null;
  subscription_plan: string;
  subscription_status: string;
  max_users: number;
  member_role?: string | null;
}

export interface OrganizationCreate {
  name: string;
  slug?: string | null;
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
