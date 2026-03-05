import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { useAuthStore } from "@/stores/authStore";
import { authService } from "@/services/auth";
import { organizationService } from "@/services/organizations";
import type { UserLogin } from "@/types/auth";

export function useLogin() {
  const navigate = useNavigate();
  const { setToken, setUser, setOrganizations, setOrganization } = useAuthStore();

  return useMutation({
    mutationFn: async (data: UserLogin) => {
      // 1. Login -> get token
      const tokenData = await authService.login(data);
      setToken(tokenData.access_token);

      // 2. Fetch user profile
      const user = await authService.getMe();
      setUser(user);

      // 3. Fetch organizations
      const orgs = await organizationService.getOrganizations();
      setOrganizations(orgs);

      // 4. Auto-select org if only one
      if (orgs.length === 1) {
        setOrganization(orgs[0].id);
      }

      return { user, orgs };
    },
    onSuccess: ({ orgs }) => {
      if (orgs.length === 1) {
        navigate("/");
      }
      // Si hay multiples orgs, el componente OrgSelector se mostrara
    },
    onError: (error: unknown) => {
      const message =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Error al iniciar sesion";
      toast.error(message);
    },
  });
}

export function useLogout() {
  const navigate = useNavigate();
  const logout = useAuthStore((s) => s.logout);

  return useCallback(() => {
    logout();
    navigate("/login");
  }, [logout, navigate]);
}

export function useCurrentUser() {
  return useAuthStore((s) => s.user);
}

export function useCurrentOrganization() {
  const { organizationId, organizations } = useAuthStore();
  return organizations.find((o) => o.id === organizationId) ?? null;
}
