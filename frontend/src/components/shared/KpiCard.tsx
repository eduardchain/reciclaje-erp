import { Link } from "react-router-dom";
import { TrendingUp, TrendingDown } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { formatCurrency, formatPercentage } from "@/utils/formatters";
import { cn } from "@/utils";
import type { MetricCard } from "@/types/reports";

interface KpiCardProps {
  label: string;
  metric: MetricCard;
  icon: React.ReactNode;
  accentColor: string;
  secondaryLabel?: string;
  secondaryValue?: string;
  href?: string;
  formatValue?: (n: number) => string;
}

const accentBorderMap: Record<string, string> = {
  emerald: "border-t-emerald-500",
  sky: "border-t-sky-500",
  violet: "border-t-violet-500",
  amber: "border-t-amber-500",
  teal: "border-t-teal-500",
  rose: "border-t-rose-500",
};

const accentIconMap: Record<string, string> = {
  emerald: "text-emerald-600 bg-emerald-50",
  sky: "text-sky-600 bg-sky-50",
  violet: "text-violet-600 bg-violet-50",
  amber: "text-amber-600 bg-amber-50",
  teal: "text-teal-600 bg-teal-50",
  rose: "text-rose-600 bg-rose-50",
};

export function KpiCard({
  label,
  metric,
  icon,
  accentColor,
  secondaryLabel,
  secondaryValue,
  href,
  formatValue,
}: KpiCardProps) {
  const borderClass = accentBorderMap[accentColor] || "border-t-slate-300";
  const iconClass = accentIconMap[accentColor] || "text-slate-600 bg-slate-50";

  const content = (
    <Card className={cn(
      "border-t-[3px] shadow-sm hover:shadow-md transition-all duration-200 overflow-hidden",
      borderClass,
      href && "hover:-translate-y-0.5 cursor-pointer"
    )}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center", iconClass)}>
              {icon}
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              {label}
            </span>
          </div>
        </div>

        <p className="text-2xl font-bold text-slate-900 tabular-nums tracking-tight">
          {(formatValue ?? formatCurrency)(metric.current_value)}
        </p>

        {metric.change_percentage != null && (
          <div className="flex items-center gap-1.5 mt-2">
            {metric.change_percentage >= 0 ? (
              <div className="flex items-center gap-1 text-emerald-600">
                <TrendingUp className="h-3.5 w-3.5" />
                <span className="text-xs font-semibold tabular-nums">
                  +{formatPercentage(metric.change_percentage)}
                </span>
              </div>
            ) : (
              <div className="flex items-center gap-1 text-rose-600">
                <TrendingDown className="h-3.5 w-3.5" />
                <span className="text-xs font-semibold tabular-nums">
                  {formatPercentage(metric.change_percentage)}
                </span>
              </div>
            )}
            <span className="text-xs text-slate-400">vs periodo anterior</span>
          </div>
        )}

        {secondaryLabel && (
          <>
            <div className="border-t border-slate-100 my-3" />
            <p className="text-xs text-slate-400">
              {secondaryLabel}: <span className="font-medium text-slate-600">{secondaryValue}</span>
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );

  if (href) {
    return <Link to={href}>{content}</Link>;
  }
  return content;
}
