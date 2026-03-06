import { useDateFilter } from "@/stores/dateFilterStore";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import ReportsLayout from "./ReportsLayout";
import { useMarginAnalysis } from "@/hooks/useReports";
import { formatCurrency } from "@/utils/formatters";

export default function MarginAnalysisPage() {
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();
  const { data, isLoading } = useMarginAnalysis({ date_from: dateFrom, date_to: dateTo });

  return (
    <ReportsLayout>
      <div className="flex justify-end">
        <DateRangePicker dateFrom={dateFrom} dateTo={dateTo} onDateFromChange={setDateFrom} onDateToChange={setDateTo} />
      </div>

      {isLoading && <div className="text-center text-slate-500 py-8">Cargando...</div>}

      {data && (
        <div className="space-y-4">
          <Card className="shadow-sm">
            <CardContent className="pt-6">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Margen Global</p>
              <p className="text-3xl font-bold">{(data.overall_margin * 100).toFixed(1)}%</p>
            </CardContent>
          </Card>

          <Card className="shadow-sm">
            <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Analisis por Material</CardTitle></CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <div className="rounded-lg border border-slate-200/80 overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-slate-50/80 border-b border-slate-200/80">
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Material</TableHead>
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Compra Qty</TableHead>
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Compra $</TableHead>
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Precio Compra</TableHead>
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Venta Qty</TableHead>
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Venta $</TableHead>
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Precio Venta</TableHead>
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Utilidad</TableHead>
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Margen</TableHead>
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">DE Qty</TableHead>
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">DE Util.</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.materials.map((m) => (
                      <TableRow key={m.material_id}>
                        <TableCell className="font-medium">{m.material_code} - {m.material_name}</TableCell>
                        <TableCell className="text-right tabular-nums">{m.total_purchased_qty.toFixed(0)}</TableCell>
                        <TableCell className="text-right">{formatCurrency(m.total_purchased_amount)}</TableCell>
                        <TableCell className="text-right">{formatCurrency(m.avg_purchase_price)}</TableCell>
                        <TableCell className="text-right tabular-nums">{m.total_sold_qty.toFixed(0)}</TableCell>
                        <TableCell className="text-right">{formatCurrency(m.total_sold_revenue)}</TableCell>
                        <TableCell className="text-right">{formatCurrency(m.avg_sale_price)}</TableCell>
                        <TableCell className={`text-right font-medium ${m.gross_profit >= 0 ? "text-emerald-700" : "text-red-700"}`}>{formatCurrency(m.gross_profit)}</TableCell>
                        <TableCell className="text-right">{(m.margin_percentage * 100).toFixed(1)}%</TableCell>
                        <TableCell className="text-right tabular-nums">{m.double_entry_qty.toFixed(0)}</TableCell>
                        <TableCell className="text-right text-emerald-700">{formatCurrency(m.double_entry_profit)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </ReportsLayout>
  );
}
