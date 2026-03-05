import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import ReportsLayout from "./ReportsLayout";
import { usePurchaseReport } from "@/hooks/useReports";
import { formatCurrency } from "@/utils/formatters";

function getDefaultDates() {
  const now = new Date();
  return {
    from: new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10),
    to: now.toISOString().slice(0, 10),
  };
}

export default function PurchaseReportPage() {
  const defaults = getDefaultDates();
  const [dateFrom, setDateFrom] = useState(defaults.from);
  const [dateTo, setDateTo] = useState(defaults.to);
  const { data, isLoading } = usePurchaseReport({ date_from: dateFrom, date_to: dateTo });

  return (
    <ReportsLayout>
      <div className="flex justify-end">
        <DateRangePicker dateFrom={dateFrom} dateTo={dateTo} onDateFromChange={setDateFrom} onDateToChange={setDateTo} />
      </div>

      {isLoading && <div className="text-center text-gray-500 py-8">Cargando...</div>}

      {data && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card><CardContent className="pt-6"><p className="text-sm text-gray-500">Total Compras</p><p className="text-2xl font-bold">{formatCurrency(data.total_amount)}</p></CardContent></Card>
            <Card><CardContent className="pt-6"><p className="text-sm text-gray-500">Cantidad Total</p><p className="text-2xl font-bold">{data.total_quantity.toFixed(0)} kg</p></CardContent></Card>
            <Card><CardContent className="pt-6"><p className="text-sm text-gray-500"># Compras</p><p className="text-2xl font-bold">{data.purchase_count}</p></CardContent></Card>
            <Card><CardContent className="pt-6"><p className="text-sm text-gray-500">Promedio/Compra</p><p className="text-2xl font-bold">{formatCurrency(data.average_per_purchase)}</p></CardContent></Card>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader><CardTitle className="text-base">Por Proveedor</CardTitle></CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Proveedor</TableHead>
                      <TableHead className="text-right">Compras</TableHead>
                      <TableHead className="text-right">Cantidad</TableHead>
                      <TableHead className="text-right">Total</TableHead>
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
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle className="text-base">Por Material</CardTitle></CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Material</TableHead>
                      <TableHead className="text-right">Cantidad</TableHead>
                      <TableHead className="text-right">Precio Prom.</TableHead>
                      <TableHead className="text-right">Total</TableHead>
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
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </ReportsLayout>
  );
}
