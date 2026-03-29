import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { CheckCircle2, AlertTriangle, FileSpreadsheet, FileText } from "lucide-react";
import ReportsLayout from "./ReportsLayout";
import { useBalanceSheet } from "@/hooks/useReports";
import { formatCurrency, formatDate } from "@/utils/formatters";
import { exportBalanceSheetExcel } from "@/utils/excelExport";
import { exportBalanceSheetPDF } from "@/utils/pdfExport";
import { useAuthStore } from "@/stores/authStore";

export default function BalanceSheetPage() {
  const { data, isLoading } = useBalanceSheet();
  const { organizationId, organizations } = useAuthStore();
  const orgName = organizations.find((o) => o.id === organizationId)?.name ?? "";

  return (
    <ReportsLayout>
      {isLoading && <div className="text-center text-slate-500 py-8">Cargando...</div>}

      {data && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Corte al: {formatDate(data.as_of_date)}</p>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => exportBalanceSheetPDF(data, orgName)}><FileText className="w-4 h-4 mr-1" /> PDF</Button>
              <Button variant="outline" size="sm" onClick={() => exportBalanceSheetExcel(data)}><FileSpreadsheet className="w-4 h-4 mr-1" /> Excel</Button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="shadow-sm">
              <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-blue-700">Activos</CardTitle></CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="flex justify-between"><span>Efectivo y Bancos</span><span>{formatCurrency(data.assets.cash_and_bank)}</span></div>
                <div className="flex justify-between"><span>Cuentas por Cobrar</span><span>{formatCurrency(data.assets.accounts_receivable)}</span></div>
                <div className="flex justify-between"><span>Inventario</span><span>{formatCurrency(data.assets.inventory)}</span></div>
                {data.assets.advances > 0 && (
                  <div className="flex justify-between"><span>Anticipos</span><span>{formatCurrency(data.assets.advances)}</span></div>
                )}
                {data.assets.investor_receivable > 0 && (
                  <div className="flex justify-between"><span>CxC Inversionistas</span><span>{formatCurrency(data.assets.investor_receivable)}</span></div>
                )}
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
                  <div className="flex justify-between"><span>Pasivos</span><span>{formatCurrency(data.liabilities.liability_debt)}</span></div>
                )}
                {data.liabilities.service_provider_payable > 0 && (
                  <div className="flex justify-between"><span>Proveedores Servicios</span><span>{formatCurrency(data.liabilities.service_provider_payable)}</span></div>
                )}
                {data.liabilities.customer_advances > 0 && (
                  <div className="flex justify-between"><span>Anticipos de Clientes</span><span>{formatCurrency(data.liabilities.customer_advances)}</span></div>
                )}
                {data.liabilities.provision_obligations > 0 && (
                  <div className="flex justify-between"><span>Obligaciones de Provisión</span><span>{formatCurrency(data.liabilities.provision_obligations)}</span></div>
                )}
                {data.liabilities.generic_payable > 0 && (
                  <div className="flex justify-between"><span>Otras Cuentas por Pagar</span><span>{formatCurrency(data.liabilities.generic_payable)}</span></div>
                )}
                <Separator />
                <div className="flex justify-between font-bold"><span>Total Pasivos</span><span>{formatCurrency(data.total_liabilities)}</span></div>
              </CardContent>
            </Card>

            <Card className="border-2 border-emerald-200 bg-emerald-50 shadow-sm">
              <CardHeader><CardTitle className="text-sm font-semibold uppercase tracking-wider text-emerald-700">Patrimonio</CardTitle></CardHeader>
              <CardContent className="space-y-2 text-sm">
                {(data.accumulated_profit !== 0 || data.distributed_profit !== 0) && (
                  <>
                    <div className="flex justify-between"><span>Utilidad Acumulada</span><span>{formatCurrency(data.accumulated_profit)}</span></div>
                    <div className="flex justify-between text-red-600"><span>(-) Utilidades Distribuidas</span><span>{formatCurrency(data.distributed_profit)}</span></div>
                    <Separator />
                  </>
                )}
                <div className="flex justify-between font-bold text-emerald-700"><span>Patrimonio Neto</span><span>{formatCurrency(data.equity)}</span></div>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 text-center mt-2">Activos - Pasivos</p>
              </CardContent>
            </Card>
          </div>

          {/* Verificacion */}
          {(() => {
            const diff = Math.abs(data.total_assets - data.total_liabilities - data.equity);
            const isBalanced = diff < 0.01;
            return (
              <div className={`flex items-center justify-center gap-2 py-3 rounded-md text-sm font-medium ${isBalanced ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
                {isBalanced ? <CheckCircle2 className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
                <span>Activos ({formatCurrency(data.total_assets)}) = Pasivos ({formatCurrency(data.total_liabilities)}) + Patrimonio ({formatCurrency(data.equity)})</span>
                {isBalanced && <span>Cuadrado</span>}
              </div>
            );
          })()}
        </div>
      )}
    </ReportsLayout>
  );
}
