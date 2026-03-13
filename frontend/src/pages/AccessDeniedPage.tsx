import { useNavigate } from "react-router-dom";
import { ShieldX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ROUTES } from "@/utils/constants";

export default function AccessDeniedPage() {
  const navigate = useNavigate();

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
      <ShieldX className="w-16 h-16 text-red-400" />
      <h1 className="text-2xl font-bold text-gray-900">Acceso Denegado</h1>
      <p className="text-gray-500 text-center max-w-md">
        No tienes permisos para acceder a esta seccion. Contacta al administrador si necesitas acceso.
      </p>
      <Button
        onClick={() => navigate(ROUTES.DASHBOARD)}
        className="bg-emerald-600 hover:bg-emerald-700"
      >
        Ir al Dashboard
      </Button>
    </div>
  );
}
