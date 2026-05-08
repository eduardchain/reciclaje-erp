import { useSearchParams } from "react-router-dom";
import { useDateFilter } from "@/stores/dateFilterStore";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import { FileSpreadsheet } from "lucide-react";
import ReportsLayout from "./ReportsLayout";
import { usePurchaseReport } from "@/hooks/useReports";
import { formatCurrency } from "@/utils/formatters";
import { exportPurchaseReportExcel } from "@/utils/excelExport";
import type { DpFilter } from "@/types/reports";

const DP_FILTER_OPTIONS: { value: DpFilter; label: string }[] = [
  { value: "all", label: "Todas" },
  { value: "exclude", label: "Sin Pasa Mano" },
  { value: "only", label: "Solo Pasa Mano" },
];

export default function PurchaseReportPage() {
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

  const { data, isLoading } = usePurchaseReport({
    date_from: dateFrom,
    date_to: dateTo,
    dp_filter: dpFilter,
  });

  return (
    <ReportsLayout>
      <div className="flex flex-wrap items-end justify-end gap-3">
        <div className="flex flex-col gap-1">
          <Label className="text-xs text-slate-500">Operaciones</Label>
          <Select value={dpFilter} onValueChange={setDpFilter}>
            <SelectTrigger className="w-44 h-9">
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
          <Button variant="outline" size="sm" onClick={() => exportPurchaseReportExcel(data, dpLabel)}>
            <FileSpreadsheet className="w-4 h-4 mr-1" /> Excel
          </Button>
        )}
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
