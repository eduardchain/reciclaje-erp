import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import ReportsLayout from "./ReportsLayout";
import { useBalanceSheet } from "@/hooks/useReports";
import { formatCurrency, formatDate } from "@/utils/formatters";

export default function BalanceSheetPage() {
  const { data, isLoading } = useBalanceSheet();

  return (
    <ReportsLayout>
      {isLoading && <div className="text-center text-slate-500 py-8">Cargando...</div>}

      {data && (
        <div className="space-y-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Corte al: {formatDate(data.as_of_date)}</p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="shadow-sm">
              <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-blue-700">Activos</CardTitle></CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="flex justify-between"><span>Efectivo y Bancos</span><span>{formatCurrency(data.assets.cash_and_bank)}</span></div>
                <div className="flex justify-between"><span>Cuentas por Cobrar</span><span>{formatCurrency(data.assets.accounts_receivable)}</span></div>
                <div className="flex justify-between"><span>Inventario</span><span>{formatCurrency(data.assets.inventory)}</span></div>
                {data.assets.provision_funds > 0 && (
                  <div className="flex justify-between"><span>Fondos en Provisiones</span><span>{formatCurrency(data.assets.provision_funds)}</span></div>
                )}
                {data.assets.prepaid_expenses > 0 && (
                  <div className="flex justify-between"><span>Gastos Prepagados</span><span>{formatCurrency(data.assets.prepaid_expenses)}</span></div>
                )}
                {data.assets.fixed_assets > 0 && (
                  <div className="flex justify-between"><span>Activos Fijos (Neto)</span><span>{formatCurrency(data.assets.fixed_assets)}</span></div>
                )}
                <Separator />
                <div className="flex justify-between font-bold"><span>Total Activos</span><span>{formatCurrency(data.total_assets)}</span></div>
              </CardContent>
            </Card>

            <Card className="shadow-sm">
              <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-red-700">Pasivos</CardTitle></CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="flex justify-between"><span>Cuentas por Pagar</span><span>{formatCurrency(data.liabilities.accounts_payable)}</span></div>
                <div className="flex justify-between"><span>Deuda Inversionistas</span><span>{formatCurrency(data.liabilities.investor_debt)}</span></div>
                {data.liabilities.liability_debt > 0 && (
                  <div className="flex justify-between"><span>Pasivos Laborales</span><span>{formatCurrency(data.liabilities.liability_debt)}</span></div>
                )}
                <Separator />
                <div className="flex justify-between font-bold"><span>Total Pasivos</span><span>{formatCurrency(data.total_liabilities)}</span></div>
              </CardContent>
            </Card>

            <Card className="border-2 border-emerald-200 bg-emerald-50 shadow-sm">
              <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-emerald-700">Patrimonio</CardTitle></CardHeader>
              <CardContent>
                <p className="text-3xl font-bold text-emerald-700 text-center mt-4">{formatCurrency(data.equity)}</p>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 text-center mt-2">Activos - Pasivos</p>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </ReportsLayout>
  );
}
