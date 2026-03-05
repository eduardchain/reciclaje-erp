import { Badge } from "@/components/ui/badge";
import { cn } from "@/utils";

type Status =
  | "registered"
  | "paid"
  | "cancelled"
  | "confirmed"
  | "annulled"
  | "completed"
  | "active"
  | "inactive";

const statusConfig: Record<Status, { label: string; className: string }> = {
  registered: { label: "Registrada", className: "bg-yellow-100 text-yellow-800 border-yellow-200" },
  paid: { label: "Pagada", className: "bg-green-100 text-green-800 border-green-200" },
  cancelled: { label: "Cancelada", className: "bg-red-100 text-red-800 border-red-200" },
  confirmed: { label: "Confirmado", className: "bg-green-100 text-green-800 border-green-200" },
  annulled: { label: "Anulado", className: "bg-red-100 text-red-800 border-red-200" },
  completed: { label: "Completado", className: "bg-blue-100 text-blue-800 border-blue-200" },
  active: { label: "Activo", className: "bg-green-100 text-green-800 border-green-200" },
  inactive: { label: "Inactivo", className: "bg-gray-100 text-gray-800 border-gray-200" },
};

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = statusConfig[status as Status] ?? {
    label: status,
    className: "bg-gray-100 text-gray-800 border-gray-200",
  };

  return (
    <Badge variant="outline" className={cn(config.className, className)}>
      {config.label}
    </Badge>
  );
}
