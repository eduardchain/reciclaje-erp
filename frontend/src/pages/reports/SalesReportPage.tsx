import { useDateFilter } from "@/stores/dateFilterStore";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import ReportsLayout from "./ReportsLayout";
import { useSalesReport } from "@/hooks/useReports";
import { formatCurrency } from "@/utils/formatters";

export default function SalesReportPage() {
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();
  const { data, isLoading } = useSalesReport({ date_from: dateFrom, date_to: dateTo });

  return (
    <ReportsLayout>
      <div className="flex justify-end">
        <DateRangePicker dateFrom={dateFrom} dateTo={dateTo} onDateFromChange={setDateFrom} onDateToChange={setDateTo} />
      </div>

      {isLoading && <div className="text-center text-slate-500 py-8">Cargando...</div>}

      {data && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card className="shadow-sm"><CardContent className="pt-6"><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Ingresos</p><p className="text-2xl font-bold">{formatCurrency(data.total_revenue)}</p></CardContent></Card>
            <Card className="shadow-sm"><CardContent className="pt-6"><p className="text-xs font-semibold uppercase tracking-wider text-slate-500"># Ventas</p><p className="text-2xl font-bold">{data.sale_count}</p></CardContent></Card>
            <Card className="shadow-sm"><CardContent className="pt-6"><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Utilidad</p><p className="text-2xl font-bold text-emerald-700">{formatCurrency(data.total_profit)}</p></CardContent></Card>
            <Card className="shadow-sm"><CardContent className="pt-6"><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Margen</p><p className="text-2xl font-bold">{(data.overall_margin * 100).toFixed(1)}%</p></CardContent></Card>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card className="shadow-sm">
              <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Por Cliente</CardTitle></CardHeader>
              <CardContent>
                <div className="rounded-lg border border-slate-200/80 overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-slate-50/80 border-b border-slate-200/80">
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Cliente</TableHead>
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Ventas</TableHead>
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Total</TableHead>
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Utilidad</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.by_customer.map((c) => (
                      <TableRow key={c.customer_id}>
                        <TableCell>{c.customer_name}</TableCell>
                        <TableCell className="text-right">{c.sale_count}</TableCell>
                        <TableCell className="text-right">{formatCurrency(c.total_amount)}</TableCell>
                        <TableCell className="text-right font-medium text-emerald-700">{formatCurrency(c.total_profit)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                </div>
              </CardContent>
            </Card>

            <Card className="shadow-sm">
              <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Por Material</CardTitle></CardHeader>
              <CardContent>
                <div className="rounded-lg border border-slate-200/80 overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-slate-50/80 border-b border-slate-200/80">
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Material</TableHead>
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Cantidad</TableHead>
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Utilidad</TableHead>
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Margen</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.by_material.map((m) => (
                      <TableRow key={m.material_id}>
                        <TableCell>{m.material_code} - {m.material_name}</TableCell>
                        <TableCell className="text-right tabular-nums">{m.total_quantity.toFixed(0)}</TableCell>
                        <TableCell className="text-right font-medium text-emerald-700">{formatCurrency(m.total_profit)}</TableCell>
                        <TableCell className="text-right">{(m.margin_percentage * 100).toFixed(1)}%</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </ReportsLayout>
  );
}
