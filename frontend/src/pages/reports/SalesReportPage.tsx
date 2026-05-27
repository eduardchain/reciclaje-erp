import { useSearchParams } from "react-router-dom";
import { useDateFilter } from "@/stores/dateFilterStore";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { ResponsiveFilterBar } from "@/components/shared/ResponsiveFilterBar";
import { FileSpreadsheet } from "lucide-react";
import ReportsLayout from "./ReportsLayout";
import { useSalesReport } from "@/hooks/useReports";
import { formatCurrency } from "@/utils/formatters";
import { exportSalesReportExcel } from "@/utils/excelExport";
import type { DpFilter } from "@/types/reports";

const DP_FILTER_OPTIONS: { value: DpFilter; label: string }[] = [
  { value: "all", label: "Todas" },
  { value: "exclude", label: "Sin Pasa Mano" },
  { value: "only", label: "Solo Pasa Mano" },
];

export default function SalesReportPage() {
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();
  const [searchParams, setSearchParams] = useSearchParams();

  const dpFilter = (searchParams.get("dp") as DpFilter | null) ?? "all";
  const dpLabel = DP_FILTER_OPTIONS.find((o) => o.value === dpFilter)?.label ?? "Todas";

  const setDpFilter = (v: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (v === "all") next.delete("dp");
      else next.set("dp", v);
      return next;
    }, { replace: true });
  };

  const { data, isLoading } = useSalesReport({
    date_from: dateFrom,
    date_to: dateTo,
    dp_filter: dpFilter,
  });

  return (
    <ReportsLayout>
      <ResponsiveFilterBar className="sm:justify-end sm:items-end">
        <div className="flex flex-col gap-1 w-full sm:w-auto">
          <Label className="text-xs text-slate-500">Operaciones</Label>
          <Select value={dpFilter} onValueChange={setDpFilter}>
            <SelectTrigger className="w-full sm:w-44 h-9">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {DP_FILTER_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <DateRangePicker dateFrom={dateFrom} dateTo={dateTo} onDateFromChange={setDateFrom} onDateToChange={setDateTo} />
        {data && (
          <Button variant="outline" size="sm" onClick={() => exportSalesReportExcel(data, dpLabel)} className="w-full sm:w-auto">
            <FileSpreadsheet className="w-4 h-4 mr-1" /> Excel
          </Button>
        )}
      </ResponsiveFilterBar>

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
