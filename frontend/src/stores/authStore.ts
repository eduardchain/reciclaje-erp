import { create } from "zustand";
import type { UserResponse } from "@/types/auth";
import type { OrganizationResponse } from "@/types/organization";

interface AuthStore {
  user: UserResponse | null;
  token: string | null;
  organizationId: string | null;
  organizations: OrganizationResponse[];
  isAuthenticated: boolean;

  setToken: (token: string) => void;
  setUser: (user: UserResponse) => void;
  setOrganizations: (orgs: OrganizationResponse[]) => void;
  setOrganization: (orgId: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  token: localStorage.getItem("token"),
  organizationId: localStorage.getItem("organizationId"),
  organizations: [],
  isAuthenticated: !!localStorage.getItem("token"),

  setToken: (token: string) => {
    localStorage.setItem("token", token);
    set({ token, isAuthenticated: true });
  },

  setUser: (user: UserResponse) => {
    set({ user });
  },

  setOrganizations: (organizations: OrganizationResponse[]) => {
    set({ organizations });
  },

  setOrganization: (orgId: string) => {
    localStorage.setItem("organizationId", orgId);
    set({ organizationId: orgId });
  },

  logout: () => {
    localStorage.removeItem("token");
    localStorage.removeItem("organizationId");
    set({
      user: null,
      token: null,
      organizationId: null,
      organizations: [],
      isAuthenticated: false,
    });
  },
}));
