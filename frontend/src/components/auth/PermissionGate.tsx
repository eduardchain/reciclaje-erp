import { ReactNode } from "react";
import { usePermissions } from "@/hooks/usePermissions";
import AccessDeniedPage from "@/pages/AccessDeniedPage";

interface PermissionGateProps {
  permission: string | string[];
  children: ReactNode;
  fallback?: ReactNode;
}

export function PermissionGate({ permission, children, fallback }: PermissionGateProps) {
  const { hasPermission, hasAnyPermission, isLoading } = usePermissions();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600" />
      </div>
    );
  }

  const allowed = Array.isArray(permission)
    ? hasAnyPermission(permission)
    : hasPermission(permission);

  if (!allowed) {
    return <>{fallback ?? <AccessDeniedPage />}</>;
  }

  return <>{children}</>;
}
