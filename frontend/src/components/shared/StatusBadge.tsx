import { Badge } from "@/components/ui/badge";
import { cn } from "@/utils";

type Status =
  | "registered"
  | "paid"
  | "liquidated"
  | "cancelled"
  | "confirmed"
  | "annulled"
  | "completed"
  | "active"
  | "inactive";

const statusConfig: Record<Status, { label: string; className: string }> = {
  registered: { label: "Registrada", className: "bg-yellow-100 text-yellow-800 border-yellow-200" },
  paid: { label: "Pagada", className: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  liquidated: { label: "Liquidada", className: "bg-sky-100 text-sky-800 border-sky-200" },
  cancelled: { label: "Cancelada", className: "bg-red-100 text-red-800 border-red-200" },
  confirmed: { label: "Confirmado", className: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  annulled: { label: "Anulado", className: "bg-red-100 text-red-800 border-red-200" },
  completed: { label: "Completado", className: "bg-blue-100 text-blue-800 border-blue-200" },
  active: { label: "Activo", className: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  inactive: { label: "Inactivo", className: "bg-slate-100 text-slate-800 border-slate-200" },
};

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = statusConfig[status as Status] ?? {
    label: status,
    className: "bg-slate-100 text-slate-800 border-slate-200",
  };

  return (
    <Badge variant="outline" className={cn(config.className, className)}>
      {config.label}
    </Badge>
  );
}
