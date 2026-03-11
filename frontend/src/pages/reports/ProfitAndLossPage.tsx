import { useDateFilter } from "@/stores/dateFilterStore";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Separator } from "@/components/ui/separator";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import ReportsLayout from "./ReportsLayout";
import { useProfitAndLoss } from "@/hooks/useReports";
import { formatCurrency } from "@/utils/formatters";

export default function ProfitAndLossPage() {
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();
  const { data, isLoading } = useProfitAndLoss({ date_from: dateFrom, date_to: dateTo });

  return (
    <ReportsLayout>
      <div className="flex justify-end">
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
              <div className="flex justify-between text-sm"><span>Gastos Operacionales</span><span className="font-medium text-red-600">-{formatCurrency(data.operating_expenses)}</span></div>
              <div className="flex justify-between text-sm"><span>Comisiones Pagadas</span><span className="font-medium text-red-600">-{formatCurrency(data.commissions_paid)}</span></div>
              <Separator />
              <div className="flex justify-between text-lg font-bold"><span>Utilidad Neta</span><span className={data.net_profit >= 0 ? "text-emerald-700" : "text-red-700"}>{formatCurrency(data.net_profit)} ({(data.net_margin * 100).toFixed(1)}%)</span></div>
            </div>

            {data.expenses_by_category.length > 0 && (
              <>
                <Separator />
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Desglose de Gastos</p>
                  <div className="rounded-lg border border-slate-200/80 overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-slate-50/80 border-b border-slate-200/80">
                        <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Categoria</TableHead>
                        <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Tipo</TableHead>
                        <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Monto</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {data.expenses_by_category.map((cat) => (
                        <TableRow key={cat.category_id ?? "none"}>
                          <TableCell>{cat.category_name}</TableCell>
                          <TableCell className="text-sm text-slate-500">{cat.is_direct_expense ? "Directo" : "Indirecto"}</TableCell>
                          <TableCell className="text-right">{formatCurrency(cat.total_amount)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      )}
    </ReportsLayout>
  );
}
