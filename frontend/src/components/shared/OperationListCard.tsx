import type { ReactNode } from "react";
import { cn } from "@/utils";
import { formatCurrency, formatDate } from "@/utils/formatters";

interface OperationListCardProps {
  operationNumber: string | number;
  date: string;
  partyName: ReactNode;
  partyLabel?: string;
  total?: number;
  statusBadge: ReactNode;
  description?: ReactNode;
  extras?: ReactNode;
  actions?: ReactNode;
  cancelled?: boolean;
  invoiceNumber?: string | null;
}

export function OperationListCard({
  operationNumber,
  date,
  partyName,
  partyLabel,
  total,
  statusBadge,
  description,
  extras,
  actions,
  cancelled = false,
  invoiceNumber,
}: OperationListCardProps) {
  return (
    <div
      className={cn(
        "rounded-md border bg-white p-3 shadow-sm",
        cancelled && "opacity-60 bg-rose-50/40",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span className="font-semibold text-slate-700">#{operationNumber}</span>
            <span className="text-slate-300">·</span>
            <span>{formatDate(date)}</span>
            {invoiceNumber && (
              <>
                <span className="text-slate-300">·</span>
                <span className="truncate">Fac: {invoiceNumber}</span>
              </>
            )}
          </div>
        </div>
        <div className="shrink-0 flex items-center gap-1">
          {statusBadge}
          {actions}
        </div>
      </div>

      <div className="mt-1.5 flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1 text-sm">
          {partyLabel && <span className="text-xs text-slate-400">{partyLabel}: </span>}
          <span className={cn("font-medium text-slate-800 truncate", cancelled && "line-through")}>{partyName}</span>
        </div>
        {total != null && (
          <span className={cn("font-bold tabular-nums text-sm shrink-0", cancelled && "line-through")}>
            {formatCurrency(total)}
          </span>
        )}
      </div>

      {description && (
        <div className={cn("mt-1 text-xs text-slate-500 line-clamp-2", cancelled && "line-through")}>
          {description}
        </div>
      )}

      {extras && <div className="mt-1.5">{extras}</div>}
    </div>
  );
}
