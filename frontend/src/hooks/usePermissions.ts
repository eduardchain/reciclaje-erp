import { useQuery } from "@tanstack/react-query";
import { rolesService } from "@/services/roles";
import { useAuthStore } from "@/stores/authStore";

export function usePermissions() {
  const organizationId = useAuthStore((s) => s.organizationId);
  const isSystemMode = organizationId === "system";

  const { data, isLoading } = useQuery({
    queryKey: ["permissions", organizationId],
    queryFn: rolesService.getMyPermissions,
    enabled: !!organizationId && !isSystemMode,
    staleTime: 5 * 60 * 1000,
  });

  // En modo sistema, superuser tiene todos los permisos
  if (isSystemMode) {
    return {
      permissions: [],
      isAdmin: true,
      roleName: "Super Admin",
      assignedAccountIds: [],
      isLoading: false,
      hasPermission: () => true,
      hasAnyPermission: () => true,
    };
  }

  const hasPermission = (permission: string): boolean => {
    if (!data) return false;
    if (data.is_admin) return true;
    return data.permissions.includes(permission);
  };

  const hasAnyPermission = (permissions: string[]): boolean => {
    if (!data) return false;
    if (data.is_admin) return true;
    return permissions.some((p) => data.permissions.includes(p));
  };

  return {
    permissions: data?.permissions ?? [],
    isAdmin: data?.is_admin ?? false,
    roleName: data?.role_display_name ?? "",
    assignedAccountIds: data?.assigned_account_ids ?? [],
    isLoading,
    hasPermission,
    hasAnyPermission,
  };
}
