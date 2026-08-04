import { ReactNode } from "react";
import { useOrgSettings } from "@/hooks/useOrgSettings";
import AccessDeniedPage from "@/pages/AccessDeniedPage";

interface FlagGateProps {
  flag: string;
  children: ReactNode;
  fallback?: ReactNode;
}

/**
 * Guard de ruta por feature flag de la org (SAC E1, D12).
 *
 * Compone con el guard P (permisos): sin FlagGate, un admin de otra org
 * deep-linkea /config/tariffs por el bypass de permisos de admin. Se usa
 * envolviendo: <FlagGate flag="..."><P permission="..."><Page /></P></FlagGate>
 */
export function FlagGate({ flag, children, fallback }: FlagGateProps) {
  const { flagEnabled, isLoading } = useOrgSettings();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600" />
      </div>
    );
  }

  if (!flagEnabled(flag)) {
    return <>{fallback ?? <AccessDeniedPage />}</>;
  }

  return <>{children}</>;
}
