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
        "rounded-md border bg-white p-3 shadow-sm",
        onClick && "cursor-pointer active:bg-slate-50",
        annulled && "opacity-60 bg-rose-50/40",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span className="font-medium">{formatDate(date)}</span>
            <span className="text-slate-300">·</span>
            <span className={cn("font-semibold text-slate-700 truncate", annulled && "line-through")}>{typeLabel}</span>
            {movementNumber && <span className="text-slate-300 shrink-0">#{movementNumber}</span>}
          </div>
        </div>
        <span className={cn("font-bold tabular-nums text-sm shrink-0", amountColor, annulled && "line-through")}>
          {amountPrefix}{formatCurrency(amount)}
        </span>
      </div>

      {description && (
        <div className={cn("mt-1 text-sm text-slate-700 truncate", annulled && "line-through")}>
          {description}
        </div>
      )}

      {(thirdPartyName || balanceAfter != null) && (
        <div className="mt-1.5 flex items-center justify-between gap-2 text-xs">
          <div className="min-w-0 text-slate-500 truncate">
            {thirdPartyName && <>→ {thirdPartyName}</>}
          </div>
          {balanceAfter != null && (
            <div className="shrink-0 text-slate-500">
              Saldo: <MoneyDisplay amount={balanceAfter} className="text-xs" />
            </div>
          )}
        </div>
      )}

      {annulled && (
        <Badge variant="outline" className="mt-2 bg-rose-50 text-rose-600 text-[10px] py-0">Anulado</Badge>
      )}

      {extras && <div className="mt-2">{extras}</div>}
    </div>
  );
}
