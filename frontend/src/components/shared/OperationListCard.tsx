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
  /** Placa del vehiculo — se muestra en la linea meta solo si viene (opcional, los DP no la pasan). */
  plate?: string | null;
  /** Cantidad total ya formateada (ej. "1.500 kg") — se muestra en la linea meta solo si viene. */
  totalQuantity?: string | null;
}

export function OperationListCard({
  operationNumber,
  date,
  partyName,
  partyLabel: _partyLabel,
  total,
  statusBadge,
  description,
  extras,
  actions,
  cancelled = false,
  invoiceNumber,
  plate,
  totalQuantity,
}: OperationListCardProps) {
  return (
    <div
      className={cn(
        "rounded-md border bg-white px-3 py-2 shadow-sm",
        cancelled && "opacity-60 bg-rose-50/40",
      )}
    >
      {/* Linea 1: #NUM + Tercero (truncate) + Total + Status + Actions */}
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold text-slate-700 shrink-0 tabular-nums">
          #{operationNumber}
        </span>
        <span
          className={cn(
            "text-sm font-medium text-slate-800 truncate flex-1 min-w-0",
            cancelled && "line-through",
          )}
        >
          {partyName}
        </span>
        {total != null && (
          <span
            className={cn(
              "text-sm font-bold tabular-nums shrink-0",
              cancelled && "line-through",
            )}
          >
            {formatCurrency(total)}
          </span>
        )}
        <div className="shrink-0 flex items-center gap-1">
          {statusBadge}
          {actions}
        </div>
      </div>

      {/* Linea 2: meta (fecha · placa · cant. total · description · invoice) */}
      <div
        className={cn(
          "mt-0.5 flex items-center gap-1.5 text-[11px] text-slate-500 leading-tight",
          cancelled && "line-through",
        )}
      >
        <span className="shrink-0">{formatDate(date)}</span>
        {plate && (
          <>
            <span className="text-slate-300 shrink-0">·</span>
            <span className="shrink-0 uppercase">{plate}</span>
          </>
        )}
        {totalQuantity && (
          <>
            <span className="text-slate-300 shrink-0">·</span>
            <span className="shrink-0 font-medium text-slate-600 tabular-nums">Cant: {totalQuantity}</span>
          </>
        )}
        {description && (
          <>
            <span className="text-slate-300 shrink-0">·</span>
            <span className="truncate min-w-0">{description}</span>
          </>
        )}
        {invoiceNumber && (
          <>
            <span className="text-slate-300 shrink-0">·</span>
            <span className="shrink-0">Fac: {invoiceNumber}</span>
          </>
        )}
      </div>

      {/* Linea 3 (opcional): extras como chip inline */}
      {extras && <div className="mt-1 flex items-center gap-1.5">{extras}</div>}
    </div>
  );
}
