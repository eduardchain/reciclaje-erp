import { useState, useEffect } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { useDateFilter } from "@/stores/dateFilterStore";
import { saveScroll, useScrollRestoration } from "@/hooks/useScrollRestoration";
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
import { PNL_EXPENSE_DRILL_URLS } from "@/utils/pnlSections";

interface PnlPeriodLike {
  period_from: string;
  period_to: string;
}

interface CellLinkProps {
  to: string;
  children: React.ReactNode;
  valueClass?: string;
}

function CellLink({ to, children, valueClass = "" }: CellLinkProps) {
  const location = useLocation();
  return (
    <Link
      to={to}
      // Guardar el scroll del P&L mensual antes del drill-down (patron #57)
      onClick={() => saveScroll(location.pathname + location.search)}
      className={`hover:underline hover:text-emerald-700 ${valueClass}`}
    >
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
  const { dateFrom, dateTo, setDateFrom, setDateTo, pnlCutoffDay, setPnlCutoffDay } = useDateFilter();

  // Source of truth: URL > store > 1. Al cambiar persistir en ambos para que al
  // volver desde sidebar (sin params) se restaure el ultimo cutoff usado.
  const urlCutoff = searchParams.get("cutoff_day");
  const cutoffFromUrl = urlCutoff != null ? parseInt(urlCutoff, 10) : NaN;
  const validUrlCutoff = !isNaN(cutoffFromUrl) && cutoffFromUrl >= 1 && cutoffFromUrl <= 28 ? cutoffFromUrl : null;
  const cutoffDay = validUrlCutoff ?? pnlCutoffDay;
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
  useScrollRestoration(!isLoading);

  const commitCutoffDay = (v: number) => {
    const clamped = Math.max(1, Math.min(28, v));
    setPnlCutoffDay(clamped);
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
      label: "Ingresos por Servicios",
      drillUrl: (p) => withDateRange("/treasury?tab=service_income&status=confirmed", p.period_from, p.period_to),
      value: (p) => p.service_income,
      cellClass: () => "text-emerald-700",
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
      label: "Ajuste Costo por Sobreventa y Reversiones",
      value: (p) => p.oversell_cost_adjustment,
      cellClass: (v) => v >= 0 ? "text-emerald-700" : "text-red-700",
      visible: (d) => d.periods.some((p) => Math.abs(p.oversell_cost_adjustment) > 0.01)
                   || Math.abs(d.totals.oversell_cost_adjustment) > 0.01,
    },
    {
      label: "Ganancia/Pérdida por Venta de Activos",
      value: (p) => p.asset_sale_gain,
      cellClass: (v) => v >= 0 ? "text-emerald-700" : "text-red-700",
      visible: (d) => d.periods.some((p) => Math.abs(p.asset_sale_gain) > 0.01)
                   || Math.abs(d.totals.asset_sale_gain) > 0.01,
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
      // GAP-1 QA: subtotal bruto SIN intereses (mismo campo que el tab Periodo)
      label: "Utilidad Bruta Total",
      value: (p) => p.gross_profit_before_financial,
      bold: true,
      separatorAbove: true,
      cellClass: (v) => v >= 0 ? "text-emerald-700" : "text-red-700",
      subtotal: true,
    },
  ] : [];

  return (
    <>
      <div className="flex flex-col md:flex-row md:flex-wrap md:items-end md:justify-between gap-3">
        <div className="flex flex-col sm:flex-row sm:items-end gap-3">
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
          <span className="text-xs text-slate-500 sm:pb-2 max-w-sm">
            1 = mes calendario. Valores 2-28 producen meses contables personalizados
            (ej. cutoff=4 → "4 Mar – 3 Abr").
          </span>
        </div>
        <div className="flex flex-col sm:flex-row sm:items-end gap-2">
          {data && (
            <Button variant="outline" size="sm" onClick={() => exportPnlMonthlyExcel(data, rows)} className="w-full sm:w-auto">
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
            <div className="overflow-x-auto -mx-3 sm:mx-0">
              <table className="w-full text-sm min-w-[640px]">
                <thead>
                  <tr className="border-b">
                    <th className="sticky left-0 bg-white z-10 text-left py-2 px-3 font-medium text-slate-600 min-w-[200px]">Linea</th>
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
                            return <CellLink to={row.drillUrl({ period_from: data.range_from, period_to: data.range_to })} valueClass={row.cellClass ? row.cellClass(v) : ""}>{text}</CellLink>;
                          })()}
                        </td>
                      </tr>
                    );
                  })}

                  {/* Comisiones — linea propia entre bruta y gastos (D2) */}
                  {/* Comisiones y Cargos (Ventas) */}
                  <tr className="hover:bg-slate-50">
                    <td className="sticky left-0 bg-white z-10 py-1.5 px-3">Comisiones y Cargos (Ventas)</td>
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

                  {/* Comisiones y Cargos (Pasa Mano) */}
                  <tr className="hover:bg-slate-50">
                    <td className="sticky left-0 bg-white z-10 py-1.5 px-3">Comisiones y Cargos (Pasa Mano)</td>
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

                  {/* Rubros de gasto — una linea por rubro, SIN desglose por fuente
                      (causado o pagado da igual). Escalera final del P&L por rubros. */}
                  {(() => {
                    type PeriodOrTotals = ProfitAndLossMonthlyPeriod | ProfitAndLossResponse;
                    const anyNonZero = (selector: (p: PeriodOrTotals) => number) =>
                      data.periods.some((p) => selector(p) !== 0) || selector(data.totals) !== 0;
                    const interestVisible = data.periods.some((p) => Math.abs(p.interest_income ?? 0) > 0.01) || Math.abs(data.totals.interest_income ?? 0) > 0.01;

                    const rubroRow = (
                      key: string,
                      label: string,
                      selector: (p: PeriodOrTotals) => number,
                      drillBase: string,
                    ) => (
                      <tr key={key} className="hover:bg-slate-50">
                        <td className="sticky left-0 bg-white z-10 py-1.5 px-3">{label}</td>
                        {data.periods.map((p, i) => {
                          const v = selector(p);
                          return (
                            <td key={i} className="text-right py-1.5 px-3 tabular-nums text-red-600">
                              {v > 0 ? (
                                <CellLink to={withDateRange(drillBase, p.period_from, p.period_to)} valueClass="text-red-600">
                                  -{formatCurrency(v)}
                                </CellLink>
                              ) : "-"}
                            </td>
                          );
                        })}
                        <td className="text-right py-1.5 px-3 tabular-nums border-l text-red-600">
                          {selector(data.totals) > 0 ? (
                            <CellLink to={withDateRange(drillBase, data.range_from, data.range_to)} valueClass="text-red-600">
                              -{formatCurrency(selector(data.totals))}
                            </CellLink>
                          ) : "-"}
                        </td>
                      </tr>
                    );

                    return (
                      <>
                        {/* Gastos Operativos (siempre visible) */}
                        {rubroRow("exp-operativo", "Gastos Operativos", (p) => p.expenses_operating, PNL_EXPENSE_DRILL_URLS.operativo)}

                        {/* Depreciacion de Activos */}
                        {anyNonZero((p) => p.expenses_depreciation) &&
                          rubroRow("exp-depreciacion", "Depreciación de Activos", (p) => p.expenses_depreciation, PNL_EXPENSE_DRILL_URLS.depreciacion)}

                        {/* UTILIDAD OPERACIONAL (D4) */}
                        <tr className="border-t">
                          <td className="sticky left-0 bg-white z-10 py-1.5 px-3 font-semibold">Utilidad Operacional</td>
                          {data.periods.map((p, i) => (
                            <td key={i} className={`text-right py-1.5 px-3 tabular-nums font-semibold ${p.operating_result >= 0 ? "text-emerald-700" : "text-red-700"}`}>
                              {formatCurrency(p.operating_result)}
                            </td>
                          ))}
                          <td className={`text-right py-1.5 px-3 tabular-nums font-semibold border-l ${data.totals.operating_result >= 0 ? "text-emerald-700" : "text-red-700"}`}>
                            {formatCurrency(data.totals.operating_result)}
                          </td>
                        </tr>

                        {/* Ingresos Financieros — unica aparicion (GAP-1) */}
                        {interestVisible && (
                          <tr className="hover:bg-slate-50">
                            <td className="sticky left-0 bg-white z-10 py-1.5 px-3">Ingresos Financieros (Intereses)</td>
                            {data.periods.map((p, i) => (
                              <td key={i} className="text-right py-1.5 px-3 tabular-nums text-emerald-700">
                                {(p.interest_income ?? 0) !== 0 ? (
                                  <CellLink to={withDateRange("/treasury?tab=loan_interest_accrual&status=confirmed", p.period_from, p.period_to)} valueClass="text-emerald-700">
                                    {formatCurrency(p.interest_income ?? 0)}
                                  </CellLink>
                                ) : "-"}
                              </td>
                            ))}
                            <td className="text-right py-1.5 px-3 tabular-nums border-l text-emerald-700">
                              {(data.totals.interest_income ?? 0) !== 0 ? (
                                <CellLink to={withDateRange("/treasury?tab=loan_interest_accrual&status=confirmed", data.range_from, data.range_to)} valueClass="text-emerald-700">
                                  {formatCurrency(data.totals.interest_income ?? 0)}
                                </CellLink>
                              ) : "-"}
                            </td>
                          </tr>
                        )}

                        {/* Gastos Financieros */}
                        {anyNonZero((p) => p.expenses_financial) &&
                          rubroRow("exp-financiero", "Gastos Financieros", (p) => p.expenses_financial, PNL_EXPENSE_DRILL_URLS.financiero)}
                      </>
                    );
                  })()}

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
