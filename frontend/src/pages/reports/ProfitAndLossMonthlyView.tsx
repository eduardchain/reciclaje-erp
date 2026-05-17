import { useState, useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useDateFilter } from "@/stores/dateFilterStore";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { FileSpreadsheet } from "lucide-react";
import { useProfitAndLossMonthly } from "@/hooks/useReports";
import { formatCurrency } from "@/utils/formatters";
import { exportPnlMonthlyExcel } from "@/utils/excelExport";
import type {
  ProfitAndLossMonthlyResponse,
  ProfitAndLossMonthlyPeriod,
  ProfitAndLossResponse,
} from "@/types/reports";

const EXPENSE_SOURCE_LABELS: Record<string, string> = {
  expense: "Gastos Directos",
  provision_expense: "Gastos desde Provisiones",
  expense_accrual: "Gastos Causados (Pasivos)",
  deferred_expense: "Gastos Diferidos",
  depreciation_expense: "Depreciación de Activos",
};

const EXPENSE_SOURCE_ORDER = ["expense", "provision_expense", "expense_accrual", "deferred_expense", "depreciation_expense"];

const EXPENSE_SOURCE_URL_TAB: Record<string, string> = {
  expense: "expense",
  provision_expense: "provision_expense",
  expense_accrual: "expense_accrual",
  deferred_expense: "deferred_expense",
  depreciation_expense: "depreciation_expense",
};

interface PnlPeriodLike {
  period_from: string;
  period_to: string;
  expenses_by_category: ProfitAndLossResponse["expenses_by_category"];
}

function sumExpensesBySource(p: PnlPeriodLike): Record<string, number> {
  const out: Record<string, number> = {};
  for (const c of p.expenses_by_category) {
    out[c.source_type] = (out[c.source_type] || 0) + c.total_amount;
  }
  return out;
}

interface CellLinkProps {
  to: string;
  children: React.ReactNode;
  valueClass?: string;
}

function CellLink({ to, children, valueClass = "" }: CellLinkProps) {
  return (
    <Link to={to} className={`hover:underline hover:text-emerald-700 ${valueClass}`}>
      {children}
    </Link>
  );
}

interface RowSpec {
  label: string;
  /** Si esta definido, la celda es Link a este URL (sin date_from/date_to —
   * se completan al render por periodo). */
  drillUrl?: (period: PnlPeriodLike) => string;
  /** Selector de valor por periodo. */
  value: (period: ProfitAndLossMonthlyPeriod | ProfitAndLossResponse) => number;
  /** Filtro opcional: si retorna false para todos los periodos, se omite la fila. */
  visible?: (data: ProfitAndLossMonthlyResponse) => boolean;
  /** Estilos por celda. */
  cellClass?: (value: number) => string;
  /** Display options: prefijo `-`, bold, separator, indent. */
  prefix?: "-" | "+";
  bold?: boolean;
  indent?: boolean;
  separatorAbove?: boolean;
  /** Para fila con count agregado tipo "Ingresos por Ventas (10 ventas)". */
  countSelector?: (period: ProfitAndLossMonthlyPeriod | ProfitAndLossResponse) => number;
  countLabel?: string;
  /** En vez de un valor numerico, valor especial (subtotal sin drill). */
  subtotal?: boolean;
}

function withDateRange(base: string, period_from: string, period_to: string): string {
  const sep = base.includes("?") ? "&" : "?";
  return `${base}${sep}date_from=${period_from}&date_to=${period_to}`;
}

export default function ProfitAndLossMonthlyView() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();

  const cutoffParam = parseInt(searchParams.get("cutoff_day") || "1", 10);
  const cutoffDay = isNaN(cutoffParam) || cutoffParam < 1 || cutoffParam > 28 ? 1 : cutoffParam;
  const [cutoffInput, setCutoffInput] = useState(String(cutoffDay));

  // Sincroniza input local cuando cambia URL externamente.
  useEffect(() => {
    setCutoffInput(String(cutoffDay));
  }, [cutoffDay]);

  const { data, isLoading, error } = useProfitAndLossMonthly({
    date_from: dateFrom,
    date_to: dateTo,
    cutoff_day: cutoffDay,
  });

  const commitCutoffDay = (v: number) => {
    const clamped = Math.max(1, Math.min(28, v));
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (clamped === 1) next.delete("cutoff_day");
      else next.set("cutoff_day", String(clamped));
      return next;
    }, { replace: true });
  };

  // Definicion de filas — orden exacto del tab "Periodo" (decision #49).
  // Cada celda es un Link al destino con date_from/date_to del mes contable.
  const rows: RowSpec[] = data ? [
    {
      label: "Ingresos por Ventas",
      countLabel: "ventas",
      countSelector: (p) => "sales_count" in p ? p.sales_count : 0,
      drillUrl: (p) => withDateRange("/sales?tab=liquidated&dp=exclude&date_field=liquidated_at", p.period_from, p.period_to),
      value: (p) => p.sales_revenue,
    },
    {
      label: "Ingresos por Servicios",
      drillUrl: (p) => withDateRange("/treasury?tab=service_income&status=confirmed", p.period_from, p.period_to),
      value: (p) => p.service_income,
    },
    {
      label: "Costo de Ventas (COGS)",
      drillUrl: (p) => withDateRange("/sales?tab=liquidated&dp=exclude&date_field=liquidated_at", p.period_from, p.period_to),
      value: (p) => p.cost_of_goods_sold,
      prefix: "-",
      cellClass: () => "text-red-600",
    },
    {
      label: "Utilidad Bruta Ventas",
      value: (p) => p.gross_profit_sales,
      bold: true,
      separatorAbove: true,
      cellClass: (v) => v >= 0 ? "text-emerald-700" : "text-red-700",
      subtotal: true,
    },
    {
      label: "Utilidad Pasa Mano",
      countLabel: "operaciones",
      countSelector: (p) => "double_entry_count" in p ? p.double_entry_count : 0,
      drillUrl: (p) => withDateRange("/double-entries?tab=liquidated&date_field=liquidated_at", p.period_from, p.period_to),
      value: (p) => p.double_entry_profit,
      cellClass: () => "text-emerald-700",
    },
    {
      label: "Ganancia/Perdida Transformaciones",
      drillUrl: (p) => withDateRange("/inventory/transformations?tab=confirmed", p.period_from, p.period_to),
      value: (p) => p.transformation_profit,
      cellClass: (v) => v >= 0 ? "text-emerald-700" : "text-red-700",
      visible: (d) => d.periods.some((p) => Math.abs(p.transformation_profit) > 0.01)
                   || Math.abs(d.totals.transformation_profit) > 0.01,
    },
    {
      label: "Perdida por Merma",
      drillUrl: (p) => withDateRange("/inventory/transformations?tab=confirmed", p.period_from, p.period_to),
      value: (p) => p.waste_loss,
      prefix: "-",
      cellClass: () => "text-red-600",
      visible: (d) => d.periods.some((p) => p.waste_loss > 0) || d.totals.waste_loss > 0,
    },
    {
      label: "Ajustes de Inventario",
      drillUrl: (p) => withDateRange("/inventory/adjustments?tab=confirmed&exclude_migration=true", p.period_from, p.period_to),
      value: (p) => p.adjustment_net,
      cellClass: (v) => v >= 0 ? "text-emerald-700" : "text-red-700",
      visible: (d) => d.periods.some((p) => Math.abs(p.adjustment_net) > 0.01)
                   || Math.abs(d.totals.adjustment_net) > 0.01,
    },
    {
      label: "+ Ganancia Ajuste Terceros",
      drillUrl: (p) => withDateRange("/treasury?tab=tp_adjustment&adjustment_class=gain&status=confirmed", p.period_from, p.period_to),
      value: (p) => p.tp_adjustment_gain,
      cellClass: () => "text-emerald-700",
      visible: (d) => d.periods.some((p) => p.tp_adjustment_gain > 0) || d.totals.tp_adjustment_gain > 0,
    },
    {
      label: "- Perdida Ajuste Terceros",
      drillUrl: (p) => withDateRange("/treasury?tab=tp_adjustment&adjustment_class=loss&status=confirmed", p.period_from, p.period_to),
      value: (p) => p.tp_adjustment_loss,
      prefix: "-",
      cellClass: () => "text-red-600",
      visible: (d) => d.periods.some((p) => p.tp_adjustment_loss > 0) || d.totals.tp_adjustment_loss > 0,
    },
    {
      label: "Utilidad Bruta Total",
      value: (p) => p.total_gross_profit,
      bold: true,
      separatorAbove: true,
      cellClass: (v) => v >= 0 ? "text-emerald-700" : "text-red-700",
      subtotal: true,
    },
  ] : [];

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex items-end gap-3">
          <div className="space-y-1">
            <Label htmlFor="cutoff_day" className="text-xs text-slate-600">Día inicio del mes</Label>
            <Input
              id="cutoff_day"
              type="number"
              min={1}
              max={28}
              value={cutoffInput}
              onChange={(e) => setCutoffInput(e.target.value)}
              onBlur={() => {
                const v = parseInt(cutoffInput, 10);
                if (isNaN(v)) {
                  setCutoffInput(String(cutoffDay));
                } else {
                  commitCutoffDay(v);
                }
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") (e.target as HTMLInputElement).blur();
              }}
              className="w-20"
            />
          </div>
          <span className="text-xs text-slate-500 pb-2 max-w-sm">
            1 = mes calendario. Valores 2-28 producen meses contables personalizados
            (ej. cutoff=4 → "4 Mar – 3 Abr").
          </span>
        </div>
        <div className="flex items-end gap-2">
          {data && (
            <Button variant="outline" size="sm" onClick={() => exportPnlMonthlyExcel(data, rows)}>
              <FileSpreadsheet className="w-4 h-4 mr-1" /> Excel
            </Button>
          )}
          <DateRangePicker dateFrom={dateFrom} dateTo={dateTo} onDateFromChange={setDateFrom} onDateToChange={setDateTo} />
        </div>
      </div>

      {isLoading && <div className="text-center text-slate-500 py-8">Cargando...</div>}
      {error && (
        <div className="text-center text-red-600 py-4 text-sm">
          {error instanceof Error ? error.message : "Error al cargar el reporte"}
        </div>
      )}

      {data && (
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">
              Estado de Resultados — Mensual
            </CardTitle>
            <p className="text-xs text-slate-500 mt-1">
              {data.periods.length} mes(es) contables. La columna <span className="font-medium">Total</span> es la suma del rango exacto
              ({data.range_from} – {data.range_to}), NO la suma aritmetica de las columnas — los meses pueden extenderse mas alla del rango.
            </p>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="sticky left-0 bg-white z-10 text-left py-2 px-3 font-medium text-slate-600 min-w-[260px]">Linea</th>
                    {data.periods.map((p, i) => (
                      <th key={i} className="text-right py-2 px-3 font-medium text-slate-600 whitespace-nowrap">{p.label}</th>
                    ))}
                    <th className="text-right py-2 px-3 font-semibold text-slate-700 border-l whitespace-nowrap">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, rowIdx) => {
                    if (row.visible && !row.visible(data)) return null;
                    const totalCount = row.countSelector ? row.countSelector(data.totals) : null;
                    return (
                      <tr key={rowIdx} className={row.separatorAbove ? "border-t hover:bg-slate-50" : "hover:bg-slate-50"}>
                        <td className={`sticky left-0 bg-white z-10 py-1.5 px-3 ${row.bold ? "font-semibold" : ""} ${row.indent ? "pl-7 text-slate-600" : ""}`}>
                          {row.label}
                          {row.countLabel && totalCount != null && totalCount > 0 && (
                            <span className="text-xs text-slate-500 ml-1">({totalCount} {row.countLabel})</span>
                          )}
                        </td>
                        {data.periods.map((p, pIdx) => {
                          const v = row.value(p);
                          const cellClass = row.cellClass ? row.cellClass(v) : "";
                          const text = row.prefix === "-" ? `-${formatCurrency(Math.abs(v))}` : formatCurrency(v);
                          return (
                            <td key={pIdx} className={`text-right py-1.5 px-3 tabular-nums ${row.bold ? "font-semibold" : ""} ${cellClass}`}>
                              {row.subtotal || !row.drillUrl ? text : (
                                <CellLink to={row.drillUrl(p)} valueClass={cellClass}>{text}</CellLink>
                              )}
                            </td>
                          );
                        })}
                        <td className={`text-right py-1.5 px-3 tabular-nums border-l ${row.bold ? "font-semibold" : ""} ${row.cellClass ? row.cellClass(row.value(data.totals)) : ""}`}>
                          {(() => {
                            const v = row.value(data.totals);
                            const text = row.prefix === "-" ? `-${formatCurrency(Math.abs(v))}` : formatCurrency(v);
                            if (row.subtotal || !row.drillUrl) return text;
                            return <CellLink to={row.drillUrl({ period_from: data.range_from, period_to: data.range_to, expenses_by_category: data.totals.expenses_by_category })} valueClass={row.cellClass ? row.cellClass(v) : ""}>{text}</CellLink>;
                          })()}
                        </td>
                      </tr>
                    );
                  })}

                  {/* Gastos operacionales agregados por source_type */}
                  {(() => {
                    const bySourceByPeriod = data.periods.map(sumExpensesBySource);
                    const bySourceTotal = sumExpensesBySource(data.totals);
                    const sourcesPresent = EXPENSE_SOURCE_ORDER.filter((s) =>
                      bySourceByPeriod.some((m) => (m[s] || 0) > 0) || (bySourceTotal[s] || 0) > 0,
                    );
                    return sourcesPresent.map((s) => (
                      <tr key={`exp-${s}`} className="hover:bg-slate-50">
                        <td className="sticky left-0 bg-white z-10 py-1.5 px-3 pl-7 text-slate-600">
                          {EXPENSE_SOURCE_LABELS[s]}
                        </td>
                        {data.periods.map((p, pIdx) => {
                          const v = bySourceByPeriod[pIdx][s] || 0;
                          const drill = withDateRange(`/treasury?tab=${EXPENSE_SOURCE_URL_TAB[s]}&status=confirmed`, p.period_from, p.period_to);
                          return (
                            <td key={pIdx} className="text-right py-1.5 px-3 tabular-nums text-red-600">
                              {v > 0 ? (
                                <CellLink to={drill} valueClass="text-red-600">{`-${formatCurrency(v)}`}</CellLink>
                              ) : "-"}
                            </td>
                          );
                        })}
                        <td className="text-right py-1.5 px-3 tabular-nums border-l text-red-600">
                          {(() => {
                            const v = bySourceTotal[s] || 0;
                            const drill = withDateRange(`/treasury?tab=${EXPENSE_SOURCE_URL_TAB[s]}&status=confirmed`, data.range_from, data.range_to);
                            return v > 0 ? (
                              <CellLink to={drill} valueClass="text-red-600">{`-${formatCurrency(v)}`}</CellLink>
                            ) : "-";
                          })()}
                        </td>
                      </tr>
                    ));
                  })()}

                  <tr className="border-t">
                    <td className="sticky left-0 bg-white z-10 py-1.5 px-3 font-semibold">Total Gastos Operacionales</td>
                    {data.periods.map((p, i) => (
                      <td key={i} className="text-right py-1.5 px-3 tabular-nums font-semibold text-red-600">
                        -{formatCurrency(p.operating_expenses)}
                      </td>
                    ))}
                    <td className="text-right py-1.5 px-3 tabular-nums font-semibold text-red-600 border-l">
                      -{formatCurrency(data.totals.operating_expenses)}
                    </td>
                  </tr>

                  {/* Comisiones de Ventas */}
                  <tr className="hover:bg-slate-50">
                    <td className="sticky left-0 bg-white z-10 py-1.5 px-3 pl-7 text-slate-600">Comisiones de Ventas</td>
                    {data.periods.map((p, i) => (
                      <td key={i} className="text-right py-1.5 px-3 tabular-nums text-red-600">
                        {p.commissions_paid_sales > 0 ? (
                          <CellLink to={withDateRange("/treasury?tab=commission_accrual&status=confirmed&commission_source=sale", p.period_from, p.period_to)} valueClass="text-red-600">
                            -{formatCurrency(p.commissions_paid_sales)}
                          </CellLink>
                        ) : "-"}
                      </td>
                    ))}
                    <td className="text-right py-1.5 px-3 tabular-nums border-l text-red-600">
                      {data.totals.commissions_paid_sales > 0 ? (
                        <CellLink to={withDateRange("/treasury?tab=commission_accrual&status=confirmed&commission_source=sale", data.range_from, data.range_to)} valueClass="text-red-600">
                          -{formatCurrency(data.totals.commissions_paid_sales)}
                        </CellLink>
                      ) : "-"}
                    </td>
                  </tr>

                  {/* Comisiones de Pasa Mano */}
                  <tr className="hover:bg-slate-50">
                    <td className="sticky left-0 bg-white z-10 py-1.5 px-3 pl-7 text-slate-600">Comisiones de Pasa Mano</td>
                    {data.periods.map((p, i) => (
                      <td key={i} className="text-right py-1.5 px-3 tabular-nums text-red-600">
                        {p.commissions_paid_dp > 0 ? (
                          <CellLink to={withDateRange("/treasury?tab=commission_accrual&status=confirmed&commission_source=double_entry", p.period_from, p.period_to)} valueClass="text-red-600">
                            -{formatCurrency(p.commissions_paid_dp)}
                          </CellLink>
                        ) : "-"}
                      </td>
                    ))}
                    <td className="text-right py-1.5 px-3 tabular-nums border-l text-red-600">
                      {data.totals.commissions_paid_dp > 0 ? (
                        <CellLink to={withDateRange("/treasury?tab=commission_accrual&status=confirmed&commission_source=double_entry", data.range_from, data.range_to)} valueClass="text-red-600">
                          -{formatCurrency(data.totals.commissions_paid_dp)}
                        </CellLink>
                      ) : "-"}
                    </td>
                  </tr>

                  {/* Total Comisiones */}
                  <tr>
                    <td className="sticky left-0 bg-white z-10 py-1.5 px-3 font-semibold">Total Comisiones</td>
                    {data.periods.map((p, i) => (
                      <td key={i} className="text-right py-1.5 px-3 tabular-nums font-semibold text-red-600">
                        -{formatCurrency(p.commissions_paid)}
                      </td>
                    ))}
                    <td className="text-right py-1.5 px-3 tabular-nums font-semibold text-red-600 border-l">
                      -{formatCurrency(data.totals.commissions_paid)}
                    </td>
                  </tr>

                  {/* Utilidad Neta */}
                  <tr className="border-t">
                    <td className="sticky left-0 bg-white z-10 py-2 px-3 font-bold text-base">Utilidad Neta</td>
                    {data.periods.map((p, i) => (
                      <td key={i} className={`text-right py-2 px-3 tabular-nums font-bold ${p.net_profit >= 0 ? "text-emerald-700" : "text-red-700"}`}>
                        {formatCurrency(p.net_profit)}
                        <div className="text-xs font-normal text-slate-500">({p.net_margin.toFixed(1)}%)</div>
                      </td>
                    ))}
                    <td className={`text-right py-2 px-3 tabular-nums font-bold border-l ${data.totals.net_profit >= 0 ? "text-emerald-700" : "text-red-700"}`}>
                      {formatCurrency(data.totals.net_profit)}
                      <div className="text-xs font-normal text-slate-500">({data.totals.net_margin.toFixed(1)}%)</div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </>
  );
}
