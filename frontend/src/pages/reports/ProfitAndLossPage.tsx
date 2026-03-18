import { useDateFilter } from "@/stores/dateFilterStore";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { FileSpreadsheet } from "lucide-react";
import ReportsLayout from "./ReportsLayout";
import { useProfitAndLoss } from "@/hooks/useReports";
import { formatCurrency } from "@/utils/formatters";
import { exportPnlExcel } from "@/utils/excelExport";

export default function ProfitAndLossPage() {
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();
  const { data, isLoading } = useProfitAndLoss({ date_from: dateFrom, date_to: dateTo });

  return (
    <ReportsLayout>
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
              <div className="flex justify-between text-sm"><span>Ingresos por Ventas ({data.sales_count} ventas)</span><span className="font-medium">{formatCurrency(data.sales_revenue)}</span></div>
              <div className="flex justify-between text-sm"><span>Ingresos por Servicios</span><span className="font-medium">{formatCurrency(data.service_income)}</span></div>
              <div className="flex justify-between text-sm"><span>Costo de Ventas (COGS)</span><span className="font-medium text-red-600">-{formatCurrency(data.cost_of_goods_sold)}</span></div>
              <Separator />
              <div className="flex justify-between font-medium"><span>Utilidad Bruta Ventas</span><span className={data.gross_profit_sales >= 0 ? "text-emerald-700" : "text-red-700"}>{formatCurrency(data.gross_profit_sales)} ({(data.gross_margin_sales * 100).toFixed(1)}%)</span></div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-sm"><span>Utilidad Pasa Mano ({data.double_entry_count} operaciones)</span><span className="font-medium text-emerald-700">{formatCurrency(data.double_entry_profit)}</span></div>
              {data.transformation_count > 0 && (
                <div className="flex justify-between text-sm"><span>Ganancia/Perdida Transformaciones ({data.transformation_count})</span><span className={`font-medium ${data.transformation_profit >= 0 ? "text-emerald-700" : "text-red-700"}`}>{formatCurrency(data.transformation_profit)}</span></div>
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
                const order = ["expense", "provision_expense", "expense_accrual", "deferred_expense", "depreciation_expense"];
                const sources = order.filter((s) => bySource[s] > 0);
                if (sources.length >= 1) {
                  return sources.map((s) => (
                    <div key={s} className="flex justify-between text-sm pl-2 text-slate-600">
                      <span>{labels[s]}</span><span className="text-red-600">-{formatCurrency(bySource[s])}</span>
                    </div>
                  ));
                }
                return null;
              })()}
              <div className="flex justify-between text-sm font-medium"><span>Total Gastos Operacionales</span><span className="font-medium text-red-600">-{formatCurrency(data.operating_expenses)}</span></div>
              <div className="flex justify-between text-sm"><span>Comisiones Pagadas</span><span className="font-medium text-red-600">-{formatCurrency(data.commissions_paid)}</span></div>
              <Separator />
              <div className="flex justify-between text-lg font-bold"><span>Utilidad Neta</span><span className={data.net_profit >= 0 ? "text-emerald-700" : "text-red-700"}>{formatCurrency(data.net_profit)} ({(data.net_margin * 100).toFixed(1)}%)</span></div>
            </div>
          </CardContent>
        </Card>
      )}
    </ReportsLayout>
  );
}
