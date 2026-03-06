import { useEffect, useState } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import { authService } from "@/services/auth";
import { organizationService } from "@/services/organizations";
import { OrganizationSelector } from "./OrganizationSelector";

export function ProtectedRoute() {
  const { token, organizationId, isAuthenticated, setUser, setOrganizations, setOrganization, logout } =
    useAuthStore();
  const organizations = useAuthStore((s) => s.organizations);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }

    const init = async () => {
      try {
        const user = await authService.getMe();
        setUser(user);

        const orgs = await organizationService.getOrganizations();
        setOrganizations(orgs);

        // Auto-select si solo hay 1 org y no hay org seleccionada
        if (!organizationId && orgs.length === 1) {
          setOrganization(orgs[0].id);
        }
      } catch {
        logout();
      } finally {
        setLoading(false);
      }
    };

    init();
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600" />
      </div>
    );
  }

  if (!isAuthenticated || !token) {
    return <Navigate to="/login" replace />;
  }

  // Si tiene token pero no org seleccionada y hay multiples orgs
  if (!organizationId && organizations.length > 1) {
    return <OrganizationSelector />;
  }

  // Si no tiene organizaciones
  if (!organizationId && organizations.length === 0) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl font-semibold text-slate-900">Sin organizacion</h2>
          <p className="mt-2 text-slate-600">No perteneces a ninguna organizacion.</p>
        </div>
      </div>
    );
  }

  return <Outlet />;
}
