import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Banknote,
  Building2,
  Smartphone,
  Wallet,
  ArrowUpCircle,
  ArrowDownCircle,
  TrendingUp,
  PiggyBank,
  CalendarClock,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/shared/PageHeader";
import { MoneyDisplay } from "@/components/shared/MoneyDisplay";
import { reportsService } from "@/services/reports";
import { usePendingScheduledExpenses } from "@/hooks/useScheduledExpenses";
import { formatCurrency, formatDate } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";

const MOVEMENT_TYPE_LABELS: Record<string, string> = {
  payment_to_supplier: "Pago a Proveedor",
  collection_from_client: "Cobro a Cliente",
  expense: "Gasto",
  service_income: "Ingreso por Servicio",
  transfer_out: "Transferencia Salida",
  transfer_in: "Transferencia Entrada",
  capital_injection: "Aporte de Capital",
  capital_return: "Devolucion de Capital",
  commission_payment: "Pago de Comision",
  provision_deposit: "Deposito a Provision",
  provision_expense: "Gasto desde Provision",
  advance_payment: "Anticipo a Proveedor",
  advance_collection: "Anticipo de Cliente",
  asset_payment: "Pago Activo Fijo",
  expense_accrual: "Gasto Causado (Pasivo)",
  deferred_funding: "Pago Gasto Diferido",
  deferred_expense: "Cuota Gasto Diferido",
  commission_accrual: "Comisión Causada",
  depreciation_expense: "Depreciación Activo",
};

export default function TreasuryDashboardPage() {
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({
    queryKey: ["treasury-dashboard"],
    queryFn: () => reportsService.getTreasuryDashboard(),
  });
  const { data: pendingDeferred } = usePendingScheduledExpenses();

  if (isLoading || !data) {
    return (
      <div className="space-y-6">
        <PageHeader title="Dashboard Financiero" description="Vision general de tesoreria" />
        <p className="text-center text-slate-400 py-12">Cargando...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Dashboard Financiero" description="Vision general de tesoreria" />

      {/* Cuentas por tipo */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="border-t-[3px] border-t-emerald-500 shadow-sm">
          <CardContent className="p-5">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center text-emerald-600 bg-emerald-50">
                <Banknote className="h-4 w-4" />
              </div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Efectivo</span>
            </div>
            <p className="text-2xl font-bold text-slate-900 tabular-nums">{formatCurrency(data.total_cash)}</p>
            <p className="text-xs text-slate-400 mt-1">{data.cash_accounts.length} cuenta(s)</p>
          </CardContent>
        </Card>

        <Card className="border-t-[3px] border-t-sky-500 shadow-sm">
          <CardContent className="p-5">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center text-sky-600 bg-sky-50">
                <Building2 className="h-4 w-4" />
              </div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Bancos</span>
            </div>
            <p className="text-2xl font-bold text-slate-900 tabular-nums">{formatCurrency(data.total_bank)}</p>
            <p className="text-xs text-slate-400 mt-1">{data.bank_accounts.length} cuenta(s)</p>
          </CardContent>
        </Card>

        <Card className="border-t-[3px] border-t-violet-500 shadow-sm">
          <CardContent className="p-5">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center text-violet-600 bg-violet-50">
                <Smartphone className="h-4 w-4" />
              </div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Digital</span>
            </div>
            <p className="text-2xl font-bold text-slate-900 tabular-nums">{formatCurrency(data.total_digital)}</p>
            <p className="text-xs text-slate-400 mt-1">{data.digital_accounts.length} cuenta(s)</p>
          </CardContent>
        </Card>

        <Card className="border-t-[3px] border-t-amber-500 shadow-sm">
          <CardContent className="p-5">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center text-amber-600 bg-amber-50">
                <Wallet className="h-4 w-4" />
              </div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total General</span>
            </div>
            <p className="text-2xl font-bold text-slate-900 tabular-nums">{formatCurrency(data.total_all_accounts)}</p>
          </CardContent>
        </Card>
      </div>

      {/* CxC / CxP / Posicion Neta */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="border-t-[3px] border-t-emerald-500 shadow-sm">
          <CardContent className="p-5">
            <div className="flex items-center gap-2 mb-2">
              <ArrowDownCircle className="h-5 w-5 text-emerald-600" />
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuentas por Cobrar</span>
            </div>
            <p className="text-2xl font-bold text-slate-900 tabular-nums">{formatCurrency(data.total_receivable)}</p>
          </CardContent>
        </Card>

        <Card className="border-t-[3px] border-t-rose-500 shadow-sm">
          <CardContent className="p-5">
            <div className="flex items-center gap-2 mb-2">
              <ArrowUpCircle className="h-5 w-5 text-rose-600" />
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuentas por Pagar</span>
            </div>
            <p className="text-2xl font-bold text-slate-900 tabular-nums">{formatCurrency(data.total_payable)}</p>
          </CardContent>
        </Card>

        <Card className="border-t-[3px] border-t-teal-500 shadow-sm">
          <CardContent className="p-5">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="h-5 w-5 text-teal-600" />
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Posicion Neta</span>
            </div>
            <MoneyDisplay amount={data.net_position} className="text-2xl font-bold" />
          </CardContent>
        </Card>
      </div>

      {/* MTD Ingresos / Egresos */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="shadow-sm">
          <CardContent className="p-5">
            <div className="flex items-center gap-2 mb-2">
              <ArrowDownCircle className="h-5 w-5 text-emerald-600" />
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Ingresos del Mes</span>
            </div>
            <p className="text-2xl font-bold text-emerald-700 tabular-nums">{formatCurrency(data.mtd_income)}</p>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardContent className="p-5">
            <div className="flex items-center gap-2 mb-2">
              <ArrowUpCircle className="h-5 w-5 text-rose-600" />
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Egresos del Mes</span>
            </div>
            <p className="text-2xl font-bold text-rose-700 tabular-nums">{formatCurrency(data.mtd_expense)}</p>
          </CardContent>
        </Card>
      </div>

      {/* Provisiones */}
      {data.provisions.length > 0 && (
        <Card className="shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-2">
              <PiggyBank className="h-4 w-4" />
              Provisiones
            </CardTitle>
            <span className="text-sm font-medium text-slate-600">
              Total disponible: {formatCurrency(data.total_provision_available)}
            </span>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nombre</TableHead>
                  <TableHead className="text-right">Fondos Disponibles</TableHead>
                  <TableHead className="text-right">Saldo Contable</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.provisions.map((p) => (
                  <TableRow key={p.id} className="cursor-pointer hover:bg-slate-50" onClick={() => navigate(`${ROUTES.TREASURY_ACCOUNT_STATEMENT}?third_party_id=${p.id}`)}>
                    <TableCell className="font-medium">{p.name}</TableCell>
                    <TableCell className="text-right">
                      <MoneyDisplay amount={p.available_funds} />
                    </TableCell>
                    <TableCell className="text-right">
                      <MoneyDisplay amount={p.current_balance} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Gastos Programados Pendientes */}
      <Card className="shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-2">
            <CalendarClock className="h-4 w-4" />
            Gastos Diferidos Pendientes
          </CardTitle>
          <Button variant="outline" size="sm" onClick={() => navigate(ROUTES.TREASURY_SCHEDULED)}>
            Ver todos
          </Button>
        </CardHeader>
        <CardContent>
          {!pendingDeferred || pendingDeferred.length === 0 ? (
            <p className="text-sm text-slate-400 py-4 text-center">No hay cuotas pendientes</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nombre</TableHead>
                  <TableHead>Categoria</TableHead>
                  <TableHead className="text-center">Progreso</TableHead>
                  <TableHead className="text-right">Siguiente Cuota</TableHead>
                  <TableHead className="text-right">Restante</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pendingDeferred.map((se) => (
                  <TableRow key={se.id} className="cursor-pointer hover:bg-slate-50" onClick={() => navigate(`${ROUTES.TREASURY_SCHEDULED}/${se.id}`)}>
                    <TableCell className="font-medium">
                      {se.name}
                    </TableCell>
                    <TableCell className="text-sm text-slate-500">{se.expense_category_name}</TableCell>
                    <TableCell className="text-center">
                      <div className="flex items-center justify-center gap-2">
                        <div className="w-16 bg-slate-100 rounded-full h-2">
                          <div
                            className="bg-emerald-500 h-2 rounded-full"
                            style={{ width: `${(se.applied_months / se.total_months) * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-slate-500 tabular-nums">
                          {se.applied_months}/{se.total_months}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-right font-medium tabular-nums">{formatCurrency(se.next_amount)}</TableCell>
                    <TableCell className="text-right tabular-nums text-slate-500">{formatCurrency(se.remaining_amount)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Ultimos movimientos */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">Ultimos Movimientos</CardTitle>
        </CardHeader>
        <CardContent>
          {data.recent_movements.length === 0 ? (
            <p className="text-sm text-slate-400 py-4 text-center">Sin movimientos recientes</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Fecha</TableHead>
                  <TableHead>Tipo</TableHead>
                  <TableHead>Descripcion</TableHead>
                  <TableHead>Cuenta</TableHead>
                  <TableHead className="text-right">Monto</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.recent_movements.map((m) => (
                  <TableRow key={m.id} className="cursor-pointer hover:bg-slate-50" onClick={() => navigate(`/treasury/${m.id}`)}>
                    <TableCell className="text-sm">{formatDate(m.date)}</TableCell>
                    <TableCell className="text-sm">{MOVEMENT_TYPE_LABELS[m.movement_type] || m.movement_type}</TableCell>
                    <TableCell className="text-sm max-w-[200px] truncate">{m.description}</TableCell>
                    <TableCell className="text-sm">{m.account_name || "—"}</TableCell>
                    <TableCell className="text-right">
                      <span className="font-medium tabular-nums">{formatCurrency(m.amount)}</span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
