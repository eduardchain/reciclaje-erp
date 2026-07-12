import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Landmark, Percent, PiggyBank, TrendingUp, Plus, CalendarCheck } from "lucide-react";
import { PageHeader } from "@/components/shared/PageHeader";
import { EmptyState } from "@/components/shared/EmptyState";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { usePermissions } from "@/hooks/usePermissions";
import { useInvestors, useMoneyAccounts, useExpenseCategoriesFlat } from "@/hooks/useMasterData";
import {
  useFinancialObligations,
  useObligationSummary,
  usePendingAccruals,
  useCreateObligation,
  useAccruePending,
} from "@/hooks/useFinancialObligations";
import { formatCurrency } from "@/utils/formatters";
import { ROUTES } from "@/utils/constants";
import type {
  FinancialObligationResponse,
  ObligationDirection,
  ObligationDirectionSummary,
} from "@/types/financial-obligation";

const MONTHS_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

export function periodLabel(period: string | null): string {
  if (!period) return "—";
  const [y, m] = period.split("-").map(Number);
  return `${MONTHS_ES[m - 1]} ${y}`;
}

const DIRECTION_LABELS: Record<ObligationDirection, string> = {
  payable: "Por Pagar",
  receivable: "Por Cobrar",
};

// ---------------------------------------------------------------------------
// KPIs por direccion
// ---------------------------------------------------------------------------

function SummaryCards({ summary }: { summary?: ObligationDirectionSummary }) {
  const kpis = [
    { label: "Capital Vigente", value: formatCurrency(Number(summary?.total_capital ?? 0)), icon: <Landmark className="h-4 w-4 text-indigo-500" /> },
    { label: "Intereses Pendientes", value: formatCurrency(Number(summary?.total_pending_interest ?? 0)), icon: <PiggyBank className="h-4 w-4 text-amber-500" /> },
    { label: "Tasa Promedio", value: `${Number(summary?.weighted_avg_rate ?? 0).toFixed(2)}% mensual`, icon: <Percent className="h-4 w-4 text-slate-500" /> },
    { label: "Proyección Mes en Curso", value: formatCurrency(Number(summary?.current_month_projection ?? 0)), icon: <TrendingUp className="h-4 w-4 text-emerald-500" /> },
  ];
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
      {kpis.map((kpi) => (
        <Card key={kpi.label} className="shadow-sm">
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{kpi.label}</p>
              {kpi.icon}
            </div>
            <p className="mt-1 text-lg font-bold text-slate-900">{kpi.value}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dialog: crear obligacion
// ---------------------------------------------------------------------------

function currentPeriod(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function CreateObligationDialog({
  open, onOpenChange, existingActiveTpIds,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  existingActiveTpIds: Set<string>;
}) {
  const [direction, setDirection] = useState<ObligationDirection>("payable");
  const [thirdPartyId, setThirdPartyId] = useState("");
  const [rate, setRate] = useState("");
  const [mode, setMode] = useState<"disbursement" | "from_balance">("disbursement");
  const [accountId, setAccountId] = useState("");
  const [amount, setAmount] = useState(0);
  const [date, setDate] = useState("");
  const [startPeriod, setStartPeriod] = useState(currentPeriod());
  const [notes, setNotes] = useState("");

  const { data: investors } = useInvestors();
  const { data: accounts } = useMoneyAccounts();
  const createMutation = useCreateObligation();

  // Solo terceros con categoria de Obligaciones Financieras y SIN obligacion activa
  const eligibleTps = useMemo(() => {
    const items = investors?.items ?? [];
    return items.filter(
      (tp: any) =>
        (tp.categories ?? []).some((c: any) =>
          `${c.display_name ?? c.name ?? ""}`.toLowerCase().includes("obligaci")
        ) && !existingActiveTpIds.has(tp.id)
    );
  }, [investors, existingActiveTpIds]);

  const selectedTp = eligibleTps.find((tp: any) => tp.id === thirdPartyId);
  const tpBalance = Number(selectedTp?.current_balance ?? 0);
  const balanceSignOk =
    mode !== "from_balance" || (direction === "payable" ? tpBalance < 0 : tpBalance > 0);

  const startPeriodOk = /^\d{4}-(0[1-9]|1[0-2])$/.test(startPeriod);
  const canSubmit =
    !!thirdPartyId && Number(rate) > 0 && Number(rate) <= 100 &&
    (mode === "from_balance"
      ? balanceSignOk && startPeriodOk
      : !!accountId && amount > 0 && !!date);

  const reset = () => {
    setThirdPartyId(""); setRate(""); setMode("disbursement");
    setAccountId(""); setAmount(0); setDate(""); setStartPeriod(currentPeriod()); setNotes("");
  };

  const handleSubmit = () => {
    createMutation.mutate(
      {
        third_party_id: thirdPartyId,
        direction,
        monthly_rate: Number(rate),
        mode,
        ...(mode === "disbursement"
          ? { disbursement: { account_id: accountId, amount, date } }
          : { accrual_start_period: startPeriod }),
        ...(notes ? { notes } : {}),
      },
      { onSuccess: () => { reset(); onOpenChange(false); } }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Nueva Obligación Financiera</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Dirección</Label>
              <Select value={direction} onValueChange={(v) => setDirection(v as ObligationDirection)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="payable">Por Pagar (nos prestan)</SelectItem>
                  <SelectItem value="receivable">Por Cobrar (prestamos)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Tasa mensual (%)</Label>
              <Input
                type="number" step="0.01" min="0.01" max="100" inputMode="decimal"
                value={rate} onChange={(e) => setRate(e.target.value)} placeholder="2.00"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Tercero (categoría Obligaciones Financieras)</Label>
            <Select value={thirdPartyId} onValueChange={setThirdPartyId}>
              <SelectTrigger><SelectValue placeholder="Seleccione el tercero" /></SelectTrigger>
              <SelectContent>
                {eligibleTps.length === 0 && (
                  <div className="px-3 py-2 text-sm text-slate-500">
                    No hay terceros elegibles (categoría Obligaciones Financieras sin obligación activa)
                  </div>
                )}
                {eligibleTps.map((tp: any) => (
                  <SelectItem key={tp.id} value={tp.id}>{tp.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label>Modo de creación</Label>
            <Select value={mode} onValueChange={(v) => setMode(v as typeof mode)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="disbursement">Con desembolso (mueve cuenta)</SelectItem>
                <SelectItem value="from_balance">Desde saldo actual (migración, sin movimiento)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {mode === "disbursement" ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1.5 sm:col-span-2">
                <Label>Cuenta</Label>
                <Select value={accountId} onValueChange={setAccountId}>
                  <SelectTrigger><SelectValue placeholder="Seleccione la cuenta" /></SelectTrigger>
                  <SelectContent>
                    {(accounts?.items ?? []).map((acc: any) => (
                      <SelectItem key={acc.id} value={acc.id}>{acc.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Monto del desembolso</Label>
                <MoneyInput value={amount} onChange={setAmount} min={0} />
              </div>
              <div className="space-y-1.5">
                <Label>Fecha</Label>
                <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
              </div>
            </div>
          ) : (
            <>
              {selectedTp && (
                <div className={`rounded-lg border p-3 text-sm ${balanceSignOk ? "border-indigo-200 bg-indigo-50 text-indigo-800" : "border-red-200 bg-red-50 text-red-700"}`}>
                  Saldo actual del tercero: <span className="font-semibold">{formatCurrency(tpBalance)}</span>.{" "}
                  {balanceSignOk
                    ? `El capital inicial será ${formatCurrency(Math.abs(tpBalance))} (los intereses pendientes arrancan en $0).`
                    : direction === "payable"
                      ? "Para una obligación por pagar el saldo debe ser negativo (le debemos)."
                      : "Para un préstamo por cobrar el saldo debe ser positivo (nos debe)."}
                </div>
              )}
              <div className="space-y-1.5">
                <Label>Causar intereses desde el mes *</Label>
                <Input
                  type="month"
                  value={startPeriod}
                  onChange={(e) => setStartPeriod(e.target.value)}
                  className="w-full sm:w-48"
                />
                <p className="text-xs text-slate-500">
                  El módulo causa desde este mes (una vez el mes termina). Los intereses
                  anteriores al corte deben estar consolidados a mano o dentro del saldo
                  migrado — alinee el corte al cierre de mes para no duplicar causaciones.
                </p>
              </div>
            </>
          )}

          <div className="space-y-1.5">
            <Label>Notas (opcional)</Label>
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} maxLength={500} />
          </div>
        </div>
        <DialogFooter className="gap-2">
          <Button variant="outline" className="w-full sm:w-auto" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button className="w-full sm:w-auto" disabled={!canSubmit || createMutation.isPending} onClick={handleSubmit}>
            Crear Obligación
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Dialog: causar intereses pendientes (batch, patron #21)
// ---------------------------------------------------------------------------

function AccrueDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const [categoryId, setCategoryId] = useState("");
  const { data: pending, isLoading } = usePendingAccruals(open);
  const { data: categories } = useExpenseCategoriesFlat();
  const accrueMutation = useAccruePending();

  const items = pending?.items ?? [];
  const needsCategory = pending?.has_payable ?? false;
  const canSubmit = items.length > 0 && (!needsCategory || !!categoryId);

  const handleSubmit = () => {
    accrueMutation.mutate(needsCategory ? categoryId : undefined, {
      onSuccess: () => { setCategoryId(""); onOpenChange(false); },
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Causar Intereses Pendientes</DialogTitle>
        </DialogHeader>
        {isLoading ? (
          <p className="py-6 text-center text-sm text-slate-500">Calculando períodos pendientes…</p>
        ) : items.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-500">
            No hay períodos vencidos por causar. El mes en curso se causa cuando termine.
          </p>
        ) : (
          <div className="space-y-4">
            <div className="max-h-64 overflow-y-auto rounded-lg border divide-y">
              {items.map((item) => (
                <div key={`${item.obligation_id}-${item.period}`} className="p-2.5 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium truncate">{item.third_party_name}</span>
                    <span className="font-semibold whitespace-nowrap">{formatCurrency(Number(item.amount))}</span>
                  </div>
                  <div className="mt-0.5 flex items-center justify-between gap-2 text-xs text-slate-500">
                    <span>
                      {periodLabel(item.period)} ·{" "}
                      <Badge variant="outline" className="text-[10px] px-1 py-0">
                        {DIRECTION_LABELS[item.direction]}
                      </Badge>
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs text-slate-400 break-words">{item.breakdown}</p>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
              <div className="rounded-lg bg-red-50 p-2.5">
                <p className="text-xs text-slate-500">Gasto financiero (por pagar)</p>
                <p className="font-semibold text-red-700">{formatCurrency(Number(pending?.total_payable ?? 0))}</p>
              </div>
              <div className="rounded-lg bg-emerald-50 p-2.5">
                <p className="text-xs text-slate-500">Ingreso financiero (por cobrar)</p>
                <p className="font-semibold text-emerald-700">{formatCurrency(Number(pending?.total_receivable ?? 0))}</p>
              </div>
            </div>

            {needsCategory && (
              <div className="space-y-1.5">
                <Label>Categoría de gasto para intereses por pagar *</Label>
                <Select value={categoryId} onValueChange={setCategoryId}>
                  <SelectTrigger><SelectValue placeholder="Seleccione la categoría (ej: Intereses)" /></SelectTrigger>
                  <SelectContent>
                    {(categories?.items ?? []).map((cat: any) => (
                      <SelectItem key={cat.id} value={cat.id}>{cat.display_name ?? cat.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            <p className="text-xs text-slate-500">
              La causación registra el interés en el P&L del mes correspondiente (devengo) sin mover dinero.
              El pago se registra aparte desde cada obligación.
            </p>
          </div>
        )}
        <DialogFooter className="gap-2">
          <Button variant="outline" className="w-full sm:w-auto" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button className="w-full sm:w-auto" disabled={!canSubmit || accrueMutation.isPending} onClick={handleSubmit}>
            <CalendarCheck className="h-4 w-4 mr-2" />
            Causar {items.length > 0 ? `(${items.length})` : ""}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Pagina principal
// ---------------------------------------------------------------------------

export default function ObligationsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = (searchParams.get("tab") === "receivable" ? "receivable" : "payable") as ObligationDirection;
  const [statusFilter, setStatusFilter] = useState("active");
  const [showCreate, setShowCreate] = useState(false);
  const [showAccrue, setShowAccrue] = useState(false);
  const { hasPermission } = usePermissions();
  const canManage = hasPermission("treasury.manage_obligations");

  const { data: obligations, isLoading } = useFinancialObligations(
    statusFilter === "all" ? {} : { status: statusFilter }
  );
  const { data: summary } = useObligationSummary();
  const { data: pending } = usePendingAccruals(canManage);

  const rows = useMemo(
    () => (obligations ?? []).filter((o) => o.direction === tab),
    [obligations, tab]
  );
  const activeTpIds = useMemo(
    () => new Set((obligations ?? []).filter((o) => o.status === "active").map((o) => o.third_party_id)),
    [obligations]
  );
  const pendingCount = pending?.items.length ?? 0;

  const goDetail = (o: FinancialObligationResponse) =>
    navigate(ROUTES.TREASURY_OBLIGATION_DETAIL.replace(":id", o.id));

  return (
    <div className="space-y-4">
      <PageHeader
        title="Obligaciones Financieras"
        description="Préstamos por pagar y por cobrar con intereses mensuales"
      >
        <div className="flex flex-wrap items-center gap-2">
          {canManage && (
            <Button variant="outline" className="w-full sm:w-auto" onClick={() => setShowAccrue(true)}>
              <CalendarCheck className="h-4 w-4 mr-2" />
              Causar Intereses{pendingCount > 0 ? ` (${pendingCount})` : ""}
            </Button>
          )}
          {canManage && (
            <Button className="w-full sm:w-auto" onClick={() => setShowCreate(true)}>
              <Plus className="h-4 w-4 mr-2" />Nueva Obligación
            </Button>
          )}
        </div>
      </PageHeader>

      <div className="flex flex-col sm:flex-row sm:flex-wrap gap-2 sm:items-center sm:justify-between">
        <Tabs value={tab} onValueChange={(v) => setSearchParams((prev) => { const p = new URLSearchParams(prev); p.set("tab", v); return p; })}>
          <TabsList>
            <TabsTrigger value="payable">Por Pagar</TabsTrigger>
            <TabsTrigger value="receivable">Por Cobrar</TabsTrigger>
          </TabsList>
        </Tabs>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-full sm:w-40"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="active">Activas</SelectItem>
            <SelectItem value="settled">Cerradas</SelectItem>
            <SelectItem value="all">Todas</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <SummaryCards summary={tab === "payable" ? summary?.payable : summary?.receivable} />

      {isLoading ? (
        <p className="py-8 text-center text-sm text-slate-500">Cargando…</p>
      ) : rows.length === 0 ? (
        <EmptyState
          title={`Sin obligaciones ${tab === "payable" ? "por pagar" : "por cobrar"}`}
          description="Cree una obligación con desembolso o desde el saldo migrado de un tercero."
        />
      ) : (
        <>
          {/* Desktop */}
          <Card className="shadow-sm hidden md:block">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Tercero</TableHead>
                  <TableHead className="text-right">Tasa</TableHead>
                  <TableHead className="text-right">Capital Vigente</TableHead>
                  <TableHead className="text-right">Intereses Pendientes</TableHead>
                  <TableHead>Último Mes Causado</TableHead>
                  <TableHead>Estado</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((o) => (
                  <TableRow key={o.id} className="cursor-pointer" onClick={() => goDetail(o)}>
                    <TableCell className="font-medium">{o.third_party_name}</TableCell>
                    <TableCell className="text-right">{Number(o.monthly_rate).toFixed(2)}%</TableCell>
                    <TableCell className="text-right font-semibold">{formatCurrency(Number(o.capital_balance))}</TableCell>
                    <TableCell className="text-right">{formatCurrency(Number(o.pending_interest))}</TableCell>
                    <TableCell>{periodLabel(o.last_accrued_period)}</TableCell>
                    <TableCell>
                      <Badge variant={o.status === "active" ? "default" : "secondary"}>
                        {o.status === "active" ? "Activa" : "Cerrada"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>

          {/* Mobile cards */}
          <div className="md:hidden space-y-2">
            {rows.map((o) => (
              <Card key={o.id} className="shadow-sm cursor-pointer" onClick={() => goDetail(o)}>
                <CardContent className="p-3 space-y-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium truncate">{o.third_party_name}</span>
                    <Badge variant={o.status === "active" ? "default" : "secondary"}>
                      {o.status === "active" ? "Activa" : "Cerrada"}
                    </Badge>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-500">Capital</span>
                    <span className="font-semibold">{formatCurrency(Number(o.capital_balance))}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-500">Intereses pendientes</span>
                    <span>{formatCurrency(Number(o.pending_interest))}</span>
                  </div>
                  <div className="flex justify-between text-xs text-slate-500">
                    <span>{Number(o.monthly_rate).toFixed(2)}% mensual</span>
                    <span>Causado: {periodLabel(o.last_accrued_period)}</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}

      <CreateObligationDialog open={showCreate} onOpenChange={setShowCreate} existingActiveTpIds={activeTpIds} />
      <AccrueDialog open={showAccrue} onOpenChange={setShowAccrue} />
    </div>
  );
}
