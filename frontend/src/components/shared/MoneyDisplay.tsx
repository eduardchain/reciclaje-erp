import { cn } from "@/utils";
import { formatCurrency } from "@/utils/formatters";

interface MoneyDisplayProps {
  amount: number;
  className?: string;
  showSign?: boolean;
}

export function MoneyDisplay({ amount, className, showSign = false }: MoneyDisplayProps) {
  const colorClass =
    amount > 0 ? "text-emerald-700" : amount < 0 ? "text-red-700" : "text-slate-500";

  const prefix = showSign && amount > 0 ? "+" : "";

  return (
    <span className={cn("font-medium tabular-nums", colorClass, className)}>
      {prefix}{formatCurrency(amount)}
    </span>
  );
}
