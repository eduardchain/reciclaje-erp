import { Link } from "react-router-dom";
import { useDateFilter } from "@/stores/dateFilterStore";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { FileSpreadsheet, ChevronRight } from "lucide-react";
import { useProfitAndLoss } from "@/hooks/useReports";
import { formatCurrency } from "@/utils/formatters";
import { exportPnlExcel } from "@/utils/excelExport";

interface DrillRowProps {
  to: string;
  label: string;
  value: string;
  valueClass?: string;
  indent?: boolean;
}

function DrillRow({ to, label, value, valueClass = "", indent = false }: DrillRowProps) {
  return (
    <Link
      to={to}
      className={`group flex justify-between text-sm cursor-pointer hover:bg-slate-50 rounded px-2 -mx-2 py-0.5 transition-colors ${indent ? "pl-4 text-slate-600" : ""}`}
    >
      <span className="flex items-center gap-1">
        {label}
        <ChevronRight className="h-3.5 w-3.5 text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />
      </span>
      <span className={`font-medium ${valueClass}`}>{value}</span>
    </Link>
  );
}

export default function ProfitAndLossPeriodView() {
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();
  const { data, isLoading } = useProfitAndLoss({ date_from: dateFrom, date_to: dateTo });

  return (
    <>
      <div className="flex justify-end gap-2">
        {data && <Button variant="outline" size="sm" onClick={() => exportPnlExcel(data)}><FileSpreadsheet className="w-4 h-4 mr-1" /> Excel</Button>}
        <DateRangePicker dateFrom={dateFrom} dateTo={dateTo} onDateFromChange={setDateFrom} onDateToChange={setDateTo} />
      </div>

      {isLoading && <div className="text-center text-slate-500 py-8">Cargando...</div>}

      {data && (
        <Card className="shadow-sm">
          <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Estado de Resultados</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <DrillRow
                to="/sales?tab=liquidated&dp=exclude&date_field=liquidated_at"
                label={`Ingresos por Ventas (${data.sales_count} ventas)`}
                value={formatCurrency(data.sales_revenue)}
              />
              <DrillRow
                to="/treasury?tab=service_income&status=confirmed"
                label="Ingresos por Servicios"
                value={formatCurrency(data.service_income)}
              />
              <DrillRow
                to="/sales?tab=liquidated&dp=exclude&date_field=liquidated_at"
                label="Costo de Ventas (COGS)"
                value={`-${formatCurrency(data.cost_of_goods_sold)}`}
                valueClass="text-red-600"
              />
              <Separator />
              <div className="flex justify-between font-medium"><span>Utilidad Bruta Ventas</span><span className={data.gross_profit_sales >= 0 ? "text-emerald-700" : "text-red-700"}>{formatCurrency(data.gross_profit_sales)} ({data.gross_margin_sales.toFixed(1)}%)</span></div>
            </div>

            <div className="space-y-2">
              <DrillRow
                to="/double-entries?tab=liquidated&date_field=liquidated_at"
                label={`Utilidad Pasa Mano (${data.double_entry_count} operaciones)`}
                value={formatCurrency(data.double_entry_profit)}
                valueClass="text-emerald-700"
              />
              {data.transformation_count > 0 && (
                <DrillRow
                  to="/inventory/transformations?tab=confirmed"
                  label={`Ganancia/Perdida Transformaciones (${data.transformation_count})`}
                  value={formatCurrency(data.transformation_profit)}
                  valueClass={data.transformation_profit >= 0 ? "text-emerald-700" : "text-red-700"}
                />
              )}
              {data.waste_loss > 0 && (
                <DrillRow
                  to="/inventory/transformations?tab=confirmed"
                  label="Perdida por Merma"
                  value={`-${formatCurrency(data.waste_loss)}`}
                  valueClass="text-red-600"
                />
              )}
              {data.adjustment_net !== 0 && (
                <DrillRow
                  to="/inventory/adjustments?tab=confirmed&exclude_migration=true"
                  label="Ajustes de Inventario"
                  value={`${data.adjustment_net >= 0 ? "" : "-"}${formatCurrency(Math.abs(data.adjustment_net))}`}
                  valueClass={data.adjustment_net >= 0 ? "text-emerald-700" : "text-red-700"}
                />
              )}
              {data.tp_adjustment_gain > 0 && (
                <DrillRow
                  to="/treasury?tab=tp_adjustment&adjustment_class=gain&status=confirmed"
                  label="+ Ganancia Ajuste Terceros"
                  value={formatCurrency(data.tp_adjustment_gain)}
                  valueClass="text-emerald-700"
                />
              )}
              {data.tp_adjustment_loss > 0 && (
                <DrillRow
                  to="/treasury?tab=tp_adjustment&adjustment_class=loss&status=confirmed"
                  label="- Perdida Ajuste Terceros"
                  value={`-${formatCurrency(data.tp_adjustment_loss)}`}
                  valueClass="text-red-600"
                />
              )}
              <Separator />
              <div className="flex justify-between font-medium"><span>Utilidad Bruta Total</span><span className={data.total_gross_profit >= 0 ? "text-emerald-700" : "text-red-700"}>{formatCurrency(data.total_gross_profit)}</span></div>
            </div>

            <div className="space-y-2">
              {(() => {
                const bySource: Record<string, number> = {};
                data.expenses_by_category.forEach((c) => {
                  bySource[c.source_type] = (bySource[c.source_type] || 0) + c.total_amount;
                });
                const labels: Record<string, string> = {
                  expense: "Gastos Directos",
                  provision_expense: "Gastos desde Provisiones",
                  expense_accrual: "Gastos Causados (Pasivos)",
                  deferred_expense: "Gastos Diferidos",
                  depreciation_expense: "Depreciación de Activos",
                };
                const urls: Record<string, string> = {
                  expense: "/treasury?tab=expense&status=confirmed",
                  provision_expense: "/treasury?tab=provision_expense&status=confirmed",
                  expense_accrual: "/treasury?tab=expense_accrual&status=confirmed",
                  deferred_expense: "/treasury?tab=deferred_expense&status=confirmed",
                  depreciation_expense: "/treasury?tab=depreciation_expense&status=confirmed",
                };
                const order = ["expense", "provision_expense", "expense_accrual", "deferred_expense", "depreciation_expense"];
                const sources = order.filter((s) => bySource[s] > 0);
                if (sources.length >= 1) {
                  return sources.map((s) => (
                    <DrillRow
                      key={s}
                      to={urls[s]}
                      label={labels[s]}
                      value={`-${formatCurrency(bySource[s])}`}
                      valueClass="text-red-600"
                      indent
                    />
                  ));
                }
                return null;
              })()}
              <div className="flex justify-between text-sm font-medium"><span>Total Gastos Operacionales</span><span className="font-medium text-red-600">-{formatCurrency(data.operating_expenses)}</span></div>
              <DrillRow
                to="/treasury?tab=commission_accrual&status=confirmed&commission_source=sale"
                label="Comisiones de Ventas"
                value={`-${formatCurrency(data.commissions_paid_sales)}`}
                valueClass="text-red-600"
                indent
              />
              <DrillRow
                to="/treasury?tab=commission_accrual&status=confirmed&commission_source=double_entry"
                label="Comisiones de Pasa Mano"
                value={`-${formatCurrency(data.commissions_paid_dp)}`}
                valueClass="text-red-600"
                indent
              />
              <div className="flex justify-between text-sm font-medium"><span>Total Comisiones</span><span className="font-medium text-red-600">-{formatCurrency(data.commissions_paid)}</span></div>
              <Separator />
              <div className="flex justify-between text-lg font-bold"><span>Utilidad Neta</span><span className={data.net_profit >= 0 ? "text-emerald-700" : "text-red-700"}>{formatCurrency(data.net_profit)} ({data.net_margin.toFixed(1)}%)</span></div>
            </div>
          </CardContent>
        </Card>
      )}
    </>
  );
}
