import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, FileText, Download, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/shared/PageHeader";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { MoneyDisplay } from "@/components/shared/MoneyDisplay";
import { EmptyState } from "@/components/shared/EmptyState";
import { useAccountMovements } from "@/hooks/useMoneyMovements";
import { useMoneyAccounts } from "@/hooks/useMasterData";
import { formatCurrency, formatDate } from "@/utils/formatters";
import { exportAccountStatementPDF } from "@/utils/pdfExport";
import { exportAccountStatementExcel } from "@/utils/excelExport";

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
  advance_payment: "Anticipo a Proveedor",
  advance_collection: "Anticipo de Cliente",
  asset_payment: "Pago Activo Fijo",
  expense_accrual: "Gasto Causado (Pasivo)",
  deferred_funding: "Pago Gasto Diferido",
  deferred_expense: "Cuota Gasto Diferido",
  commission_accrual: "Comisión Causada",
  depreciation_expense: "Depreciación Activo",
  profit_distribution: "Repartición Utilidades",
};

interface AccountMovementItem {
  id: string;
  movement_number: number;
  date: string;
  movement_type: string;
  amount: string | number;
  description: string;
  third_party_name: string | null;
  status: string;
  direction: number;
  balance_after: number;
}

export default function AccountMovementsPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialAccount = searchParams.get("account_id") || "";
  const returnTo = searchParams.get("returnTo") || "";

  const [accountId, setAccountId] = useState(initialAccount);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [limit, setLimit] = useState<number | undefined>(undefined);

  const { data: accountsData } = useMoneyAccounts();
  const accounts = accountsData?.items ?? [];

  const filters = {
    ...(dateFrom ? { date_from: dateFrom } : {}),
    ...(dateTo ? { date_to: dateTo } : {}),
    ...(limit !== undefined ? { limit } : {}),
  };

  const { data, isLoading } = useAccountMovements(accountId, filters);
  const movements: AccountMovementItem[] = data?.items ?? [];
  const total = data?.total ?? 0;
  const isTruncated = total > movements.length;
  const openingBalance = data?.opening_balance ?? null;

  const selectedAccount = accounts.find((a) => a.id === accountId);

  // Totales (excluir anulados)
  const activeMovements = movements.filter((m) => m.status !== "annulled");
  const totalInflow = activeMovements.reduce((sum, m) => {
    return sum + (m.direction > 0 ? Number(m.amount) : 0);
  }, 0);
  const totalOutflow = activeMovements.reduce((sum, m) => {
    return sum + (m.direction < 0 ? Number(m.amount) : 0);
  }, 0);

  const canExport = !!accountId && movements.length > 0;

  const buildExportData = () => ({
    thirdPartyName: selectedAccount?.name ?? "",
    dateFrom: dateFrom || undefined,
    dateTo: dateTo || undefined,
    currentBalance: selectedAccount?.current_balance ?? 0,
    totalDebit: totalInflow,
    totalCredit: totalOutflow,
    openingBalance: openingBalance ?? 0,
    movements: movements.filter((m) => m.status !== "annulled" && m.status !== "cancelled").map((m) => ({
      movement_number: m.movement_number,
      date: m.date,
      movement_type: m.movement_type,
      typeLabel: MOVEMENT_TYPE_LABELS[m.movement_type] || m.movement_type,
      description: m.description,
      amount: Number(m.amount),
      status: m.status,
      balance_after: m.balance_after,
      isDebit: m.direction > 0,
    })),
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Movimientos de Cuenta" description="Historial de movimientos con saldo corrido por cuenta">
        <div className="flex gap-2">
          <Button variant="outline" disabled={!canExport} onClick={() => exportAccountStatementPDF(buildExportData())}>
            <FileText className="h-4 w-4 mr-2" />PDF
          </Button>
          <Button variant="outline" disabled={!canExport} onClick={() => exportAccountStatementExcel(buildExportData())}>
            <Download className="h-4 w-4 mr-2" />Excel
          </Button>
          {returnTo && (
            <Button variant="outline" onClick={() => navigate(returnTo)}>
              <ArrowLeft className="h-4 w-4 mr-2" />Volver
            </Button>
          )}
        </div>
      </PageHeader>

      {/* Filtros */}
      <Card className="shadow-sm">
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuenta *</Label>
              <EntitySelect
                value={accountId}
                onChange={(v) => { setAccountId(v); setLimit(undefined); }}
                options={accounts.map((a) => ({ id: a.id, label: a.name }))}
                placeholder="Seleccionar cuenta..."
              />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Desde</Label>
              <Input type="date" value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setLimit(undefined); }} />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Hasta</Label>
              <Input type="date" value={dateTo} onChange={(e) => { setDateTo(e.target.value); setLimit(undefined); }} />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Resumen */}
      {accountId && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="border-t-[3px] border-t-sky-500 shadow-sm">
            <CardContent className="p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Saldo Actual</p>
              <MoneyDisplay amount={selectedAccount?.current_balance ?? 0} className="text-xl font-bold" />
            </CardContent>
          </Card>
          <Card className="border-t-[3px] border-t-emerald-500 shadow-sm">
            <CardContent className="p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Total Entradas</p>
              <p className="text-xl font-bold text-emerald-600 tabular-nums">{formatCurrency(totalInflow)}</p>
            </CardContent>
          </Card>
          <Card className="border-t-[3px] border-t-rose-500 shadow-sm">
            <CardContent className="p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Total Salidas</p>
              <p className="text-xl font-bold text-rose-600 tabular-nums">{formatCurrency(totalOutflow)}</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Tabla de movimientos */}
      {accountId && (
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-2">
              <FileText className="h-4 w-4" />
              Movimientos
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isTruncated && (
              <div className="flex items-center justify-between gap-3 mb-4 px-3 py-2 rounded-md bg-amber-50 border border-amber-200 text-amber-800 text-sm">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>Mostrando {movements.length.toLocaleString("es-CO")} de {total.toLocaleString("es-CO")} movimientos. Ajusta el rango de fechas o usa exportar para verlos todos.</span>
                </div>
                <Button size="sm" variant="outline" className="shrink-0 border-amber-300 text-amber-800 hover:bg-amber-100" onClick={() => setLimit(5000)}>
                  Ver todos
                </Button>
              </div>
            )}
            {isLoading ? (
              <p className="text-sm text-slate-400 py-8 text-center">Cargando...</p>
            ) : movements.length === 0 ? (
              <EmptyState
                title="Sin movimientos"
                description="No se encontraron movimientos para esta cuenta en el periodo seleccionado."
              />
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12">#</TableHead>
                      <TableHead>Fecha</TableHead>
                      <TableHead>Tipo</TableHead>
                      <TableHead>Descripcion</TableHead>
                      <TableHead>Tercero</TableHead>
                      <TableHead className="text-right">Entrada</TableHead>
                      <TableHead className="text-right">Salida</TableHead>
                      <TableHead className="text-right">Saldo</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {dateFrom && openingBalance != null && (
                      <TableRow className="bg-slate-50">
                        <TableCell colSpan={5} className="text-sm font-medium text-slate-600">
                          Saldo de apertura
                        </TableCell>
                        <TableCell />
                        <TableCell />
                        <TableCell className="text-right">
                          <MoneyDisplay amount={openingBalance} className="font-medium" />
                        </TableCell>
                      </TableRow>
                    )}
                    {movements.map((m) => {
                      const isInflow = m.direction > 0;
                      const isAnnulled = m.status === "annulled";
                      const amount = Number(m.amount);
                      return (
                        <TableRow
                          key={m.id}
                          className={`cursor-pointer ${isAnnulled ? "opacity-50 bg-rose-50/50" : "hover:bg-slate-50"}`}
                          onClick={() => navigate(`/treasury/${m.id}`)}
                        >
                          <TableCell className="text-xs text-slate-400">{m.movement_number}</TableCell>
                          <TableCell className="text-sm">{formatDate(m.date)}</TableCell>
                          <TableCell className="text-sm">
                            <span className={isAnnulled ? "line-through" : ""}>
                              {MOVEMENT_TYPE_LABELS[m.movement_type] || m.movement_type}
                            </span>
                            {isAnnulled && (
                              <Badge variant="outline" className="ml-2 bg-rose-50 text-rose-600 text-[10px] py-0">
                                Anulado
                              </Badge>
                            )}
                          </TableCell>
                          <TableCell className={`text-sm max-w-[200px] truncate ${isAnnulled ? "line-through" : ""}`}>
                            {m.description}
                          </TableCell>
                          <TableCell className="text-sm text-slate-500">{m.third_party_name ?? "-"}</TableCell>
                          <TableCell className="text-right">
                            {isInflow ? (
                              <span className={`tabular-nums ${isAnnulled ? "text-emerald-300 line-through" : "text-emerald-600"}`}>
                                {formatCurrency(amount)}
                              </span>
                            ) : null}
                          </TableCell>
                          <TableCell className="text-right">
                            {!isInflow ? (
                              <span className={`tabular-nums ${isAnnulled ? "text-rose-300 line-through" : "text-rose-600"}`}>
                                {formatCurrency(amount)}
                              </span>
                            ) : null}
                          </TableCell>
                          <TableCell className="text-right">
                            <MoneyDisplay amount={m.balance_after} className="text-sm" />
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {!accountId && (
        <Card className="shadow-sm">
          <CardContent className="py-12">
            <EmptyState
              title="Seleccione una cuenta"
              description="Elija una cuenta del selector para ver sus movimientos."
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
