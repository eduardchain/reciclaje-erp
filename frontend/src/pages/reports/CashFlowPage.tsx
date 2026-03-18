import { useDateFilter } from "@/stores/dateFilterStore";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { DateRangePicker } from "@/components/shared/DateRangePicker";
import ReportsLayout from "./ReportsLayout";
import { useCashFlow } from "@/hooks/useReports";
import { formatCurrency } from "@/utils/formatters";

export default function CashFlowPage() {
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDateFilter();
  const { data, isLoading } = useCashFlow({ date_from: dateFrom, date_to: dateTo });

  return (
    <ReportsLayout>
      <div className="flex justify-end">
        <DateRangePicker dateFrom={dateFrom} dateTo={dateTo} onDateFromChange={setDateFrom} onDateToChange={setDateTo} />
      </div>

      {isLoading && <div className="text-center text-slate-500 py-8">Cargando...</div>}

      {data && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card className="shadow-sm">
            <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-emerald-700">Ingresos</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between"><span>Cobros de Ventas (Liquidacion)</span><span>{formatCurrency(data.inflows.sale_collections)}</span></div>
              <div className="flex justify-between"><span>Cobros a Clientes (Tesoreria)</span><span>{formatCurrency(data.inflows.customer_collections)}</span></div>
              <div className="flex justify-between"><span>Ingresos por Servicios</span><span>{formatCurrency(data.inflows.service_income)}</span></div>
              <div className="flex justify-between"><span>Aportes de Capital</span><span>{formatCurrency(data.inflows.capital_injections)}</span></div>
              {data.inflows.advance_collections > 0 && (
                <div className="flex justify-between"><span>Anticipos de Clientes</span><span>{formatCurrency(data.inflows.advance_collections)}</span></div>
              )}
              {data.inflows.generic_collections > 0 && (
                <div className="flex justify-between"><span>Cobros a Terceros Genéricos</span><span>{formatCurrency(data.inflows.generic_collections)}</span></div>
              )}
              <Separator />
              <div className="flex justify-between font-bold text-emerald-700"><span>Total Ingresos</span><span>{formatCurrency(data.total_inflows)}</span></div>
            </CardContent>
          </Card>

          <Card className="shadow-sm">
            <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-red-700">Egresos</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between"><span>Pagos de Compras (Liquidacion)</span><span>{formatCurrency(data.outflows.purchase_payments)}</span></div>
              <div className="flex justify-between"><span>Pagos a Proveedores (Tesoreria)</span><span>{formatCurrency(data.outflows.supplier_payments)}</span></div>
              <div className="flex justify-between"><span>Gastos</span><span>{formatCurrency(data.outflows.expenses)}</span></div>
              <div className="flex justify-between"><span>Comisiones</span><span>{formatCurrency(data.outflows.commission_payments)}</span></div>
              <div className="flex justify-between"><span>Devolucion de Capital</span><span>{formatCurrency(data.outflows.capital_returns)}</span></div>
              {data.outflows.provision_deposits > 0 && (
                <div className="flex justify-between"><span>Depositos a Provisiones</span><span>{formatCurrency(data.outflows.provision_deposits)}</span></div>
              )}
              {data.outflows.deferred_fundings > 0 && (
                <div className="flex justify-between"><span>Pagos Gastos Diferidos</span><span>{formatCurrency(data.outflows.deferred_fundings)}</span></div>
              )}
              {data.outflows.advance_payments > 0 && (
                <div className="flex justify-between"><span>Anticipos a Proveedores</span><span>{formatCurrency(data.outflows.advance_payments)}</span></div>
              )}
              {data.outflows.asset_payments > 0 && (
                <div className="flex justify-between"><span>Compras de Activos Fijos</span><span>{formatCurrency(data.outflows.asset_payments)}</span></div>
              )}
              {data.outflows.generic_payments > 0 && (
                <div className="flex justify-between"><span>Pagos a Terceros Genéricos</span><span>{formatCurrency(data.outflows.generic_payments)}</span></div>
              )}
              <Separator />
              <div className="flex justify-between font-bold text-red-700"><span>Total Egresos</span><span>{formatCurrency(data.total_outflows)}</span></div>
            </CardContent>
          </Card>

          <Card className="md:col-span-2 border-2 border-blue-200 bg-blue-50 shadow-sm">
            <CardContent className="pt-6">
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Saldo Inicial</p>
                  <p className="text-xl font-bold">{formatCurrency(data.opening_balance)}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Flujo Neto</p>
                  <p className={`text-xl font-bold ${data.net_flow >= 0 ? "text-emerald-700" : "text-red-700"}`}>{data.net_flow >= 0 ? "+" : ""}{formatCurrency(data.net_flow)}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Saldo Final</p>
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
