import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import ReportsLayout from "./ReportsLayout";
import { useCashFlow } from "@/hooks/useReports";
import { formatCurrency } from "@/utils/formatters";

function getDefaultDates() {
  const now = new Date();
  return {
    from: new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10),
    to: now.toISOString().slice(0, 10),
  };
}

export default function CashFlowPage() {
  const defaults = getDefaultDates();
  const [dateFrom, setDateFrom] = useState(defaults.from);
  const [dateTo, setDateTo] = useState(defaults.to);
  const { data, isLoading } = useCashFlow({ date_from: dateFrom, date_to: dateTo });

  return (
    <ReportsLayout>
      <div className="flex justify-end">
        <DateRangePicker dateFrom={dateFrom} dateTo={dateTo} onDateFromChange={setDateFrom} onDateToChange={setDateTo} />
      </div>

      {isLoading && <div className="text-center text-gray-500 py-8">Cargando...</div>}

      {data && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card>
            <CardHeader><CardTitle className="text-base text-green-700">Ingresos</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between"><span>Cobros de Ventas (Liquidacion)</span><span>{formatCurrency(data.inflows.sale_collections)}</span></div>
              <div className="flex justify-between"><span>Cobros a Clientes (Tesoreria)</span><span>{formatCurrency(data.inflows.customer_collections)}</span></div>
              <div className="flex justify-between"><span>Ingresos por Servicios</span><span>{formatCurrency(data.inflows.service_income)}</span></div>
              <div className="flex justify-between"><span>Aportes de Capital</span><span>{formatCurrency(data.inflows.capital_injections)}</span></div>
              <Separator />
              <div className="flex justify-between font-bold text-green-700"><span>Total Ingresos</span><span>{formatCurrency(data.total_inflows)}</span></div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-base text-red-700">Egresos</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between"><span>Pagos de Compras (Liquidacion)</span><span>{formatCurrency(data.outflows.purchase_payments)}</span></div>
              <div className="flex justify-between"><span>Pagos a Proveedores (Tesoreria)</span><span>{formatCurrency(data.outflows.supplier_payments)}</span></div>
              <div className="flex justify-between"><span>Gastos</span><span>{formatCurrency(data.outflows.expenses)}</span></div>
              <div className="flex justify-between"><span>Comisiones</span><span>{formatCurrency(data.outflows.commission_payments)}</span></div>
              <div className="flex justify-between"><span>Devolucion de Capital</span><span>{formatCurrency(data.outflows.capital_returns)}</span></div>
              <Separator />
              <div className="flex justify-between font-bold text-red-700"><span>Total Egresos</span><span>{formatCurrency(data.total_outflows)}</span></div>
            </CardContent>
          </Card>

          <Card className="md:col-span-2 border-2 border-blue-200 bg-blue-50">
            <CardContent className="pt-6">
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <p className="text-sm text-gray-500">Saldo Inicial</p>
                  <p className="text-xl font-bold">{formatCurrency(data.opening_balance)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Flujo Neto</p>
                  <p className={`text-xl font-bold ${data.net_flow >= 0 ? "text-green-700" : "text-red-700"}`}>{data.net_flow >= 0 ? "+" : ""}{formatCurrency(data.net_flow)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Saldo Final</p>
                  <p className="text-xl font-bold">{formatCurrency(data.closing_balance)}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </ReportsLayout>
  );
}
