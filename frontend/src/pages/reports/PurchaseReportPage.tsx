import { useDateFilter } from "@/stores/dateFilterStore";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { FileSpreadsheet } from "lucide-react";
import ReportsLayout from "./ReportsLayout";
import { usePurchaseReport } from "@/hooks/useReports";
import { formatCurrency } from "@/utils/formatters";
import { exportPurchaseReportExcel } from "@/utils/excelExport";

export default function PurchaseReportPage() {
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();
  const { data, isLoading } = usePurchaseReport({ date_from: dateFrom, date_to: dateTo });

  return (
    <ReportsLayout>
      <div className="flex justify-end gap-2">
        {data && <Button variant="outline" size="sm" onClick={() => exportPurchaseReportExcel(data)}><FileSpreadsheet className="w-4 h-4 mr-1" /> Excel</Button>}
        <DateRangePicker dateFrom={dateFrom} dateTo={dateTo} onDateFromChange={setDateFrom} onDateToChange={setDateTo} />
      </div>

      {isLoading && <div className="text-center text-slate-500 py-8">Cargando...</div>}

      {data && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card className="shadow-sm"><CardContent className="pt-6"><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total Compras</p><p className="text-2xl font-bold">{formatCurrency(data.total_amount)}</p></CardContent></Card>
            <Card className="shadow-sm"><CardContent className="pt-6"><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cantidad Total</p><p className="text-2xl font-bold">{data.total_quantity.toFixed(0)} kg</p></CardContent></Card>
            <Card className="shadow-sm"><CardContent className="pt-6"><p className="text-xs font-semibold uppercase tracking-wider text-slate-500"># Compras</p><p className="text-2xl font-bold">{data.purchase_count}</p></CardContent></Card>
            <Card className="shadow-sm"><CardContent className="pt-6"><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Promedio/Compra</p><p className="text-2xl font-bold">{formatCurrency(data.average_per_purchase)}</p></CardContent></Card>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card className="shadow-sm">
              <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Por Proveedor</CardTitle></CardHeader>
              <CardContent>
                <div className="rounded-lg border border-slate-200/80 overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-slate-50/80 border-b border-slate-200/80">
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10">Proveedor</TableHead>
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Compras</TableHead>
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Cantidad</TableHead>
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Total</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.by_supplier.map((s) => (
                      <TableRow key={s.supplier_id}>
                        <TableCell>{s.supplier_name}</TableCell>
                        <TableCell className="text-right">{s.purchase_count}</TableCell>
                        <TableCell className="text-right tabular-nums">{s.total_quantity.toFixed(0)}</TableCell>
                        <TableCell className="text-right font-medium">{formatCurrency(s.total_amount)}</TableCell>
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
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Precio Prom.</TableHead>
                      <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 h-10 text-right">Total</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.by_material.map((m) => (
                      <TableRow key={m.material_id}>
                        <TableCell>{m.material_code} - {m.material_name}</TableCell>
                        <TableCell className="text-right tabular-nums">{m.total_quantity.toFixed(0)}</TableCell>
                        <TableCell className="text-right">{formatCurrency(m.average_unit_price)}</TableCell>
                        <TableCell className="text-right font-medium">{formatCurrency(m.total_amount)}</TableCell>
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
