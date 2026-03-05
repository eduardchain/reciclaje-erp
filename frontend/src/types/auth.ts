import type { BaseEntity } from "./common";

export interface UserResponse extends BaseEntity {
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
}

export interface UserLogin {
  email: string;
  password: string;
}

export interface UserCreate {
  email: string;
  password: string;
  full_name?: string | null;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface AuthState {
  user: UserResponse | null;
  token: string | null;
  organizationId: string | null;
  organizations: import("./organization").OrganizationResponse[];
  isAuthenticated: boolean;
}
