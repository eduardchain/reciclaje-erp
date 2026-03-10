import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, FileText } from "lucide-react";
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
};

// Tipos que representan DEBE (incrementan deuda del tercero)
const DEBIT_TYPES = new Set([
  "payment_to_supplier",
  "capital_return",
  "commission_payment",
  "provision_expense",
]);

export default function AccountStatementPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialThirdParty = searchParams.get("third_party_id") || "";

  const [thirdPartyId, setThirdPartyId] = useState(initialThirdParty);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const { data: thirdPartiesData } = useThirdParties();
  const thirdParties = thirdPartiesData?.items ?? [];

  const filters = {
    ...(dateFrom ? { date_from: dateFrom } : {}),
    ...(dateTo ? { date_to: dateTo } : {}),
  };

  const { data, isLoading } = useThirdPartyMovements(thirdPartyId, filters);
  const movements = data?.items ?? [];
  const openingBalance = data?.opening_balance ?? 0;

  // Calcular totales
  const totalDebit = movements.reduce((sum, m) => {
    return sum + (DEBIT_TYPES.has(m.movement_type) ? m.amount : 0);
  }, 0);
  const totalCredit = movements.reduce((sum, m) => {
    return sum + (!DEBIT_TYPES.has(m.movement_type) ? m.amount : 0);
  }, 0);

  const selectedThirdParty = thirdParties.find((t) => t.id === thirdPartyId);

  return (
    <div className="space-y-6">
      <PageHeader title="Estado de Cuenta" description="Movimientos y saldo corrido por tercero">
        <Button variant="outline" onClick={() => navigate(ROUTES.TREASURY)}>
          <ArrowLeft className="h-4 w-4 mr-2" />Volver
        </Button>
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
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Saldo Actual</p>
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
            ) : (
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
                      const isDebit = DEBIT_TYPES.has(m.movement_type);
                      const isAnnulled = m.status === "annulled";
                      return (
                        <TableRow key={m.id} className={isAnnulled ? "opacity-50 bg-rose-50/50" : ""}>
                          <TableCell className="text-xs text-slate-400">{m.movement_number}</TableCell>
                          <TableCell className="text-sm">{formatDate(m.date)}</TableCell>
                          <TableCell className="text-sm">
                            <span className={isAnnulled ? "line-through" : ""}>{MOVEMENT_TYPE_LABELS[m.movement_type] || m.movement_type}</span>
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
