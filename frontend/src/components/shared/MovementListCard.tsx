import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { MoneyDisplay } from "@/components/shared/MoneyDisplay";
import { cn } from "@/utils";
import { formatCurrency, formatDate } from "@/utils/formatters";

interface MovementListCardProps {
  date: string;
  typeLabel: string;
  amount: number;
  isInflow: boolean;
  description?: ReactNode;
  thirdPartyName?: ReactNode;
  movementNumber?: string | number;
  balanceAfter?: number;
  annulled?: boolean;
  onClick?: () => void;
  extras?: ReactNode;
}

export function MovementListCard({
  date,
  typeLabel,
  amount,
  isInflow,
  description,
  thirdPartyName,
  movementNumber,
  balanceAfter,
  annulled = false,
  onClick,
  extras,
}: MovementListCardProps) {
  const amountColor = isInflow ? "text-emerald-700" : "text-rose-700";
  const amountPrefix = isInflow ? "+" : "-";

  return (
    <div
      onClick={onClick}
      className={cn(
        "rounded-md border bg-white px-3 py-2 shadow-sm",
        onClick && "cursor-pointer active:bg-slate-50",
        annulled && "opacity-60 bg-rose-50/40",
      )}
    >
      {/* Linea 1: tipo + amount */}
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "text-sm font-semibold text-slate-800 truncate flex-1 min-w-0",
            annulled && "line-through",
          )}
        >
          {typeLabel}
        </span>
        {annulled && (
          <Badge
            variant="outline"
            className="bg-rose-50 text-rose-600 text-[10px] py-0 px-1.5 shrink-0 h-4"
          >
            Anulado
          </Badge>
        )}
        <span
          className={cn(
            "text-sm font-bold tabular-nums shrink-0",
            amountColor,
            annulled && "line-through",
          )}
        >
          {amountPrefix}
          {formatCurrency(amount)}
        </span>
      </div>

      {/* Linea 2: meta (fecha · #num · -> tercero · saldo) */}
      <div
        className={cn(
          "mt-0.5 flex items-center gap-1.5 text-[11px] text-slate-500 leading-tight",
          annulled && "line-through",
        )}
      >
        <span className="shrink-0">{formatDate(date)}</span>
        {movementNumber && (
          <>
            <span className="text-slate-300 shrink-0">·</span>
            <span className="shrink-0">#{movementNumber}</span>
          </>
        )}
        {thirdPartyName && (
          <>
            <span className="text-slate-300 shrink-0">·</span>
            <span className="truncate min-w-0">→ {thirdPartyName}</span>
          </>
        )}
        {balanceAfter != null && (
          <>
            <span className="text-slate-300 shrink-0">·</span>
            <span className="shrink-0 flex items-center gap-1">
              Saldo:
              <MoneyDisplay amount={balanceAfter} className="text-[11px]" />
            </span>
          </>
        )}
      </div>

      {/* Linea 3 (opcional): description solo si existe */}
      {description && (
        <div
          className={cn(
            "mt-0.5 text-[11px] text-slate-600 truncate leading-tight",
            annulled && "line-through",
          )}
        >
          {description}
        </div>
      )}

      {extras && <div className="mt-1">{extras}</div>}
    </div>
  );
}
