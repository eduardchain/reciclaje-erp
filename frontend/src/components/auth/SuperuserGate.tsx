import { ReactNode } from "react";
import { useAuthStore } from "@/stores/authStore";
import AccessDeniedPage from "@/pages/AccessDeniedPage";

interface SuperuserGateProps {
  children: ReactNode;
}

export function SuperuserGate({ children }: SuperuserGateProps) {
  const user = useAuthStore((s) => s.user);

  // Mientras user no este cargado, ProtectedRoute ya muestra un spinner global.
  // Aqui solo decidimos render una vez tengamos el user.
  if (!user) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600" />
      </div>
    );
  }

  if (!user.is_superuser) {
    return <AccessDeniedPage />;
  }

  return <>{children}</>;
}
