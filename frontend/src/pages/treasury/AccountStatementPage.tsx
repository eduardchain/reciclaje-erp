import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, FileText, Download } from "lucide-react";
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
import { useThirdPartyMovements } from "@/hooks/useMoneyMovements";
import { useThirdParties } from "@/hooks/useMasterData";
import { formatCurrency, formatDate, formatWeight } from "@/utils/formatters";
import { exportAccountStatementPDF } from "@/utils/pdfExport";
import { exportAccountStatementExcel } from "@/utils/excelExport";
import { ROUTES } from "@/utils/constants";

const EVENT_TYPE_LABELS: Record<string, string> = {
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
  asset_purchase: "Compra Activo (Crédito)",
  purchase_liquidation: "Compra Liquidada",
  purchase_cancellation: "Compra Cancelada",
  sale_liquidation: "Venta Liquidada",
  sale_cancellation: "Venta Cancelada",
  sale_commission: "Comision de Venta",
  commission_cancellation: "Comision Cancelada",
  purchase_commission: "Comision de Compra",
  purchase_commission_cancellation: "Comision Compra Cancelada",
  double_entry_purchase: "Doble Partida (Compra)",
  double_entry_sale: "Doble Partida (Venta)",
  double_entry_commission: "Comision Doble Partida",
  double_entry_cancellation: "Doble Partida Cancelada",
  double_entry_commission_cancellation: "Comision DP Cancelada",
  initial_balance: "Saldo Inicial",
  expense_accrual: "Gasto Causado (Pasivo)",
  deferred_funding: "Pago Gasto Diferido",
  deferred_expense: "Cuota Gasto Diferido",
  commission_accrual: "Comisión Causada",
  depreciation_expense: "Depreciación Activo",
  profit_distribution: "Repartición de Utilidades",
  payment_to_generic: "Pago a Tercero Genérico",
  collection_from_generic: "Cobro a Tercero Genérico",
  tp_transfer_out: "Cruce Terceros (Origen)",
  tp_transfer_in: "Cruce Terceros (Destino)",
  tp_adjustment_credit: "Ajuste Saldo (Credito)",
  tp_adjustment_debit: "Ajuste Saldo (Debito)",
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
interface StatementItem {
  id: string;
  date: string;
  event_type: string;
  description: string;
  amount: number;
  direction: number;
  status: string;
  reference_number: string | null;
  movement_number: number | null;
  balance_after: number | null;
  source: string;
  source_id: string;
  source_number: number | string | null;
  vehicle_plate?: string | null;
  invoice_number?: string | null;
  material_code?: string | null;
  material_name?: string | null;
  quantity?: number | null;
  unit_price?: number | null;
  received_quantity?: number | null;
  is_line_item?: boolean;
  parent_source_id?: string | null;
}

export default function AccountStatementPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialThirdParty = searchParams.get("third_party_id") || "";

  const [thirdPartyId, setThirdPartyId] = useState(initialThirdParty);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [viewMode, setViewMode] = useState<"financial" | "operations">("financial");

  const { data: thirdPartiesData } = useThirdParties(undefined, { staleTime: 0 });
  const thirdParties = thirdPartiesData?.items ?? [];

  const filters = {
    ...(dateFrom ? { date_from: dateFrom } : {}),
    ...(dateTo ? { date_to: dateTo } : {}),
    ...(viewMode === "operations" ? { view: "operations" } : {}),
  };

  const { data, isLoading } = useThirdPartyMovements(thirdPartyId, filters);
  const movements: StatementItem[] = data?.items ?? [];
  const openingBalance = data?.opening_balance ?? 0;

  // Calcular totales (excluir anulados/cancelados)
  const activeMovements = movements.filter((m) => m.status !== "annulled" && m.status !== "cancelled");
  const totalDebit = activeMovements.reduce((sum, m) => {
    return sum + (m.direction > 0 ? Number(m.amount) : 0);
  }, 0);
  const totalCredit = activeMovements.reduce((sum, m) => {
    return sum + (m.direction < 0 ? Number(m.amount) : 0);
  }, 0);

  const selectedThirdParty = thirdParties.find((t) => t.id === thirdPartyId);

  const canExport = !!thirdPartyId && movements.length > 0;

  const buildExportData = () => ({
    thirdPartyName: selectedThirdParty?.name ?? "",
    dateFrom: dateFrom || undefined,
    dateTo: dateTo || undefined,
    currentBalance: selectedThirdParty?.current_balance ?? 0,
    totalDebit,
    totalCredit,
    openingBalance,
    viewMode: viewMode as "financial" | "operations",
    movements: movements.filter((m) => m.status !== "annulled" && m.status !== "cancelled").map((m) => ({
      movement_number: m.movement_number ?? "",
      date: m.date,
      movement_type: m.event_type,
      typeLabel: EVENT_TYPE_LABELS[m.event_type] || m.event_type,
      description: m.description,
      amount: m.amount,
      status: m.status,
      balance_after: m.balance_after ?? null,
      isDebit: m.direction > 0,
      vehicle_plate: m.vehicle_plate,
      invoice_number: m.invoice_number,
      material_code: m.material_code,
      material_name: m.material_name,
      quantity: m.quantity,
      unit_price: m.unit_price,
      received_quantity: m.received_quantity,
      is_line_item: m.is_line_item,
      parent_source_id: m.parent_source_id,
    })),
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Estado de Cuenta" description="Movimientos y saldo corrido por tercero">
        <div className="flex gap-2 items-center">
          <div className="flex gap-1 border rounded-md p-0.5">
            <Button size="sm" variant={viewMode === "financial" ? "default" : "ghost"} onClick={() => setViewMode("financial")}>Financiero</Button>
            <Button size="sm" variant={viewMode === "operations" ? "default" : "ghost"} onClick={() => setViewMode("operations")}>Operaciones</Button>
          </div>
          <Button variant="outline" disabled={!canExport} onClick={() => exportAccountStatementPDF(buildExportData())}>
            <FileText className="h-4 w-4 mr-2" />PDF
          </Button>
          <Button variant="outline" disabled={!canExport} onClick={() => exportAccountStatementExcel(buildExportData())}>
            <Download className="h-4 w-4 mr-2" />Excel
          </Button>
          <Button variant="outline" onClick={() => navigate(ROUTES.TREASURY)}>
            <ArrowLeft className="h-4 w-4 mr-2" />Volver
          </Button>
        </div>
      </PageHeader>

      {/* Filtros */}
      <Card className="shadow-sm">
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tercero *</Label>
              <EntitySelect
                value={thirdPartyId}
                onChange={setThirdPartyId}
                options={thirdParties.map((t) => ({ id: t.id, label: t.name }))}
                placeholder="Seleccionar tercero..."
              />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Desde</Label>
              <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Hasta</Label>
              <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Resumen */}
      {thirdPartyId && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="border-t-[3px] border-t-sky-500 shadow-sm">
            <CardContent className="p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Saldo Contable</p>
              <MoneyDisplay amount={selectedThirdParty?.current_balance ?? 0} className="text-xl font-bold" />
            </CardContent>
          </Card>
          <Card className="border-t-[3px] border-t-rose-500 shadow-sm">
            <CardContent className="p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Total Debe</p>
              <p className="text-xl font-bold text-slate-900 tabular-nums">{formatCurrency(totalDebit)}</p>
            </CardContent>
          </Card>
          <Card className="border-t-[3px] border-t-emerald-500 shadow-sm">
            <CardContent className="p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Total Haber</p>
              <p className="text-xl font-bold text-slate-900 tabular-nums">{formatCurrency(totalCredit)}</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Tabla de movimientos */}
      {thirdPartyId && (
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-2">
              <FileText className="h-4 w-4" />
              Movimientos
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <p className="text-sm text-slate-400 py-8 text-center">Cargando...</p>
            ) : movements.length === 0 ? (
              <EmptyState
                title="Sin movimientos"
                description="No se encontraron movimientos para este tercero en el periodo seleccionado."
              />
            ) : viewMode === "financial" ? (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12">#</TableHead>
                      <TableHead>Fecha</TableHead>
                      <TableHead>Tipo</TableHead>
                      <TableHead>Descripcion</TableHead>
                      <TableHead className="text-right">Debe</TableHead>
                      <TableHead className="text-right">Haber</TableHead>
                      <TableHead className="text-right">Saldo</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {dateFrom && (
                      <TableRow className="bg-slate-50">
                        <TableCell colSpan={4} className="text-sm font-medium text-slate-600">
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
                      const isDebit = m.direction > 0;
                      const isAnnulled = m.status === "annulled" || m.status === "cancelled";
                      return (
                        <TableRow key={m.id} className={isAnnulled ? "opacity-50 bg-rose-50/50" : ""}>
                          <TableCell className="text-xs text-slate-400">{m.movement_number ?? ""}</TableCell>
                          <TableCell className="text-sm">{formatDate(m.date)}</TableCell>
                          <TableCell className="text-sm">
                            <span className={isAnnulled ? "line-through" : ""}>{EVENT_TYPE_LABELS[m.event_type] || m.event_type}</span>
                            {isAnnulled && <Badge variant="outline" className="ml-2 bg-rose-50 text-rose-600 text-[10px] py-0">Anulado</Badge>}
                          </TableCell>
                          <TableCell className={`text-sm max-w-[200px] truncate ${isAnnulled ? "line-through" : ""}`}>{m.description}</TableCell>
                          <TableCell className="text-right">
                            {isDebit ? <span className={`tabular-nums ${isAnnulled ? "text-rose-300 line-through" : "text-rose-600"}`}>{formatCurrency(m.amount)}</span> : null}
                          </TableCell>
                          <TableCell className="text-right">
                            {!isDebit ? <span className={`tabular-nums ${isAnnulled ? "text-emerald-300 line-through" : "text-emerald-600"}`}>{formatCurrency(m.amount)}</span> : null}
                          </TableCell>
                          <TableCell className="text-right">
                            {m.balance_after != null && <MoneyDisplay amount={m.balance_after} className="text-sm" />}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <div className="overflow-x-auto">
                {(() => {
                  // Compute last-in-group set: for items with parent_source_id, only the last one shows balance
                  const lastInGroup = new Map<string, string>();
                  movements.forEach((m) => {
                    if (m.parent_source_id) {
                      lastInGroup.set(m.parent_source_id, m.id);
                    }
                  });
                  const lastIds = new Set(lastInGroup.values());

                  return (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Fecha</TableHead>
                          <TableHead>Concepto</TableHead>
                          <TableHead>Material</TableHead>
                          <TableHead className="text-right">Peso</TableHead>
                          <TableHead className="text-right">Precio</TableHead>
                          <TableHead className="text-right">Dif Peso</TableHead>
                          <TableHead className="text-right">Debito</TableHead>
                          <TableHead className="text-right">Credito</TableHead>
                          <TableHead className="text-right">Saldo</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {dateFrom && (
                          <TableRow className="bg-slate-50">
                            <TableCell colSpan={6} className="text-sm font-medium text-slate-600">
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
                          const isDebit = m.direction > 0;
                          const isAnnulled = m.status === "annulled" || m.status === "cancelled";
                          const concepto = m.vehicle_plate || m.invoice_number || (m.source_number ? `${m.event_type?.includes("purchase") ? "Compra" : m.event_type?.includes("sale") ? "Venta" : m.event_type?.includes("double") ? "DP" : ""} #${m.source_number}` : m.description) || m.description;
                          const hasWeightDiff = m.is_line_item && m.received_quantity != null && m.quantity != null && m.received_quantity !== m.quantity;
                          const weightDiffMoney = hasWeightDiff && m.unit_price ? (m.received_quantity! - m.quantity!) * m.unit_price : null;

                          // Show balance on last item of a group, or on non-grouped items
                          const showBalance = !m.parent_source_id
                            ? m.balance_after != null
                            : lastIds.has(m.id) && m.balance_after != null;

                          return (
                            <TableRow key={m.id} className={isAnnulled ? "opacity-50 bg-rose-50/50" : ""}>
                              <TableCell className="text-sm">{formatDate(m.date)}</TableCell>
                              <TableCell className={`text-sm max-w-[200px] truncate ${isAnnulled ? "line-through" : ""}`}>
                                {concepto}
                                {isAnnulled && <Badge variant="outline" className="ml-2 bg-rose-50 text-rose-600 text-[10px] py-0">Anulado</Badge>}
                              </TableCell>
                              <TableCell className="text-sm text-slate-600">
                                {m.is_line_item && m.material_code ? `${m.material_code} - ${m.material_name ?? ""}` : ""}
                              </TableCell>
                              <TableCell className="text-right text-sm tabular-nums">
                                {m.is_line_item && m.quantity != null ? formatWeight(m.quantity) : ""}
                              </TableCell>
                              <TableCell className="text-right text-sm tabular-nums">
                                {m.is_line_item && m.unit_price != null ? formatCurrency(m.unit_price) : ""}
                              </TableCell>
                              <TableCell className="text-right text-sm tabular-nums">
                                {weightDiffMoney != null ? (
                                  <span className={weightDiffMoney < 0 ? "text-rose-600" : "text-emerald-600"}>
                                    {formatCurrency(weightDiffMoney)}
                                  </span>
                                ) : ""}
                              </TableCell>
                              <TableCell className="text-right">
                                {isDebit ? <span className={`tabular-nums ${isAnnulled ? "text-rose-300 line-through" : "text-rose-600"}`}>{formatCurrency(m.amount)}</span> : null}
                              </TableCell>
                              <TableCell className="text-right">
                                {!isDebit ? <span className={`tabular-nums ${isAnnulled ? "text-emerald-300 line-through" : "text-emerald-600"}`}>{formatCurrency(m.amount)}</span> : null}
                              </TableCell>
                              <TableCell className="text-right">
                                {showBalance && <MoneyDisplay amount={m.balance_after!} className="text-sm" />}
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  );
                })()}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {!thirdPartyId && (
        <Card className="shadow-sm">
          <CardContent className="py-12">
            <EmptyState
              title="Seleccione un tercero"
              description="Elija un tercero del selector para ver su estado de cuenta."
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
