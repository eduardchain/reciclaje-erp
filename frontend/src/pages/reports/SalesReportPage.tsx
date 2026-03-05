import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import ReportsLayout from "./ReportsLayout";
import { useSalesReport } from "@/hooks/useReports";
import { formatCurrency } from "@/utils/formatters";

function getDefaultDates() {
  const now = new Date();
  return {
    from: new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10),
    to: now.toISOString().slice(0, 10),
  };
}

export default function SalesReportPage() {
  const defaults = getDefaultDates();
  const [dateFrom, setDateFrom] = useState(defaults.from);
  const [dateTo, setDateTo] = useState(defaults.to);
  const { data, isLoading } = useSalesReport({ date_from: dateFrom, date_to: dateTo });

  return (
    <ReportsLayout>
      <div className="flex justify-end">
        <DateRangePicker dateFrom={dateFrom} dateTo={dateTo} onDateFromChange={setDateFrom} onDateToChange={setDateTo} />
      </div>

      {isLoading && <div className="text-center text-gray-500 py-8">Cargando...</div>}

      {data && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card><CardContent className="pt-6"><p className="text-sm text-gray-500">Ingresos</p><p className="text-2xl font-bold">{formatCurrency(data.total_revenue)}</p></CardContent></Card>
            <Card><CardContent className="pt-6"><p className="text-sm text-gray-500"># Ventas</p><p className="text-2xl font-bold">{data.sale_count}</p></CardContent></Card>
            <Card><CardContent className="pt-6"><p className="text-sm text-gray-500">Utilidad</p><p className="text-2xl font-bold text-green-700">{formatCurrency(data.total_profit)}</p></CardContent></Card>
            <Card><CardContent className="pt-6"><p className="text-sm text-gray-500">Margen</p><p className="text-2xl font-bold">{(data.overall_margin * 100).toFixed(1)}%</p></CardContent></Card>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader><CardTitle className="text-base">Por Cliente</CardTitle></CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Cliente</TableHead>
                      <TableHead className="text-right">Ventas</TableHead>
                      <TableHead className="text-right">Total</TableHead>
                      <TableHead className="text-right">Utilidad</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.by_customer.map((c) => (
                      <TableRow key={c.customer_id}>
                        <TableCell>{c.customer_name}</TableCell>
                        <TableCell className="text-right">{c.sale_count}</TableCell>
                        <TableCell className="text-right">{formatCurrency(c.total_amount)}</TableCell>
                        <TableCell className="text-right font-medium text-green-700">{formatCurrency(c.total_profit)}</TableCell>
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
                      <TableHead className="text-right">Utilidad</TableHead>
                      <TableHead className="text-right">Margen</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.by_material.map((m) => (
                      <TableRow key={m.material_id}>
                        <TableCell>{m.material_code} - {m.material_name}</TableCell>
                        <TableCell className="text-right tabular-nums">{m.total_quantity.toFixed(0)}</TableCell>
                        <TableCell className="text-right font-medium text-green-700">{formatCurrency(m.total_profit)}</TableCell>
                        <TableCell className="text-right">{(m.margin_percentage * 100).toFixed(1)}%</TableCell>
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
