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
      collectorScope: null,
      unscoped: true,
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
    // Alcance de recolector (SAC): el backend ya filtra; la pantalla solo deja
    // de pedir lo que el backend le niega (plan §8).
    collectorScope: data?.collector_scope ?? null,
    // true SOLO cuando ya se sabe que no hay alcance. Es el `enabled` de los
    // queries que un usuario con alcance no puede pedir: mientras cargan los
    // permisos no se dispara nada, y sin alcance la request sale igual que hoy.
    unscoped: !isLoading && !data?.collector_scope,
    isLoading,
    hasPermission,
    hasAnyPermission,
  };
}
