import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  AlertTriangle, ArrowLeft, Banknote, CalendarCheck, CalendarClock, HandCoins, Landmark, Lock, XCircle,
} from "lucide-react";
import { PageHeader } from "@/components/shared/PageHeader";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ThirdPartyLink } from "@/components/shared/EntityLink";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { Checkbox } from "@/components/ui/checkbox";
import { usePermissions } from "@/hooks/usePermissions";
import { useMoneyAccounts, useExpenseCategoriesFlat, useThirdParties } from "@/hooks/useMasterData";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { useReturnToBack } from "@/hooks/useReturnToBack";
import {
  useFinancialObligation,
  useObligationStatement,
  useObligationMovement,
  useObligationTransfer,
  useSettleObligation,
  useAnnulObligationMovement,
  useAccruePreview,
  useAccrueObligation,
} from "@/hooks/useFinancialObligations";
import { formatCurrency, formatDate } from "@/utils/formatters";
import { periodLabel } from "./ObligationsPage";
import type { MoneyMovementResponse } from "@/types/money-movement";
import type { AccruePreviewResponse } from "@/types/financial-obligation";

const MOVEMENT_LABELS: Record<string, string> = {
  obligation_disbursement: "Desembolso",
  obligation_interest_accrual: "Interés Causado",
  obligation_interest_payment: "Pago de Intereses",
  obligation_capital_payment: "Abono a Capital",
  loan_disbursement: "Desembolso",
  loan_interest_accrual: "Interés Causado",
  loan_interest_collection: "Recaudo de Intereses",
  loan_capital_collection: "Recaudo de Capital",
  obligation_interest_transfer: "Traslado de Intereses a Tercero",
  obligation_capital_transfer: "Abono a Capital (desde tercero)",
  loan_interest_transfer: "Traslado de Intereses a Tercero",
  loan_capital_transfer: "Recaudo de Capital (desde tercero)",
  tp_transfer_out: "Contraparte del Traslado",
  tp_transfer_in: "Contraparte del Traslado",
};

type ActionKind = "capital" | "interest" | "disbursement";

function ActionDialog({
  open, onOpenChange, obligationId, kind, title, maxAmount, direction, obligationThirdPartyId,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  obligationId: string;
  kind: ActionKind;
  title: string;
  maxAmount?: number;
  direction: "payable" | "receivable";
  obligationThirdPartyId: string;
}) {
  const [amount, setAmount] = useState(0);
  const [accountId, setAccountId] = useState("");
  const [thirdPartyId, setThirdPartyId] = useState("");
  const [mode, setMode] = useState<"account" | "third_party">("account");
  const [date, setDate] = useState("");
  const [notes, setNotes] = useState("");
  const { data: accounts } = useMoneyAccounts();
  const mutation = useObligationMovement(kind);
  const transferMutation = useObligationTransfer(kind === "interest" ? "interest" : "capital");
  // Traslado contra tercero: solo capital/intereses (el desembolso siempre es por cuenta)
  const canTransfer = kind !== "disbursement";
  const { data: thirdParties } = useThirdParties(
    { is_active: true, limit: 1000 },
    { staleTime: 60_000 }
  );
  const tpOptions = (thirdParties?.items ?? []).filter(
    (tp: any) => tp.id !== obligationThirdPartyId && !tp.is_system_entity
  );
  const selectedTp = tpOptions.find((tp: any) => tp.id === thirdPartyId);
  // Preview del saldo resultante (informativo, no bloquea — mas negativo es valido)
  const resultingBalance = selectedTp !== undefined
    ? Number(selectedTp.current_balance ?? 0) + (direction === "payable" ? -amount : amount)
    : null;

  const overMax = maxAmount !== undefined && amount > maxAmount;
  const isTransfer = canTransfer && mode === "third_party";
  const canSubmit = amount > 0 && !!date && !overMax
    && (isTransfer ? !!thirdPartyId : !!accountId);

  const reset = () => {
    setAmount(0); setAccountId(""); setThirdPartyId("");
    setMode("account"); setDate(""); setNotes("");
  };

  const handleSubmit = () => {
    if (isTransfer) {
      transferMutation.mutate(
        { id: obligationId, data: { amount, third_party_id: thirdPartyId, date, ...(notes ? { notes } : {}) } },
        { onSuccess: () => { reset(); onOpenChange(false); } }
      );
      return;
    }
    mutation.mutate(
      { id: obligationId, data: { amount, account_id: accountId, date, ...(notes ? { notes } : {}) } },
      { onSuccess: () => { reset(); onOpenChange(false); } }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>{title}</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Monto</Label>
              <MoneyInput value={amount} onChange={setAmount} min={0} />
              {maxAmount !== undefined && (
                <button
                  type="button"
                  className={`block text-left text-xs ${overMax ? "text-red-600" : "text-indigo-600"} hover:underline`}
                  onClick={() => setAmount(maxAmount)}
                >
                  Máximo: {formatCurrency(maxAmount)} — usar
                </button>
              )}
            </div>
            <div className="space-y-1.5">
              <Label>Fecha</Label>
              <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
          </div>
          {canTransfer && (
            <div className="space-y-1.5">
              <Label>Contrapartida</Label>
              <div className="flex flex-col sm:flex-row gap-2">
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="radio"
                    checked={mode === "account"}
                    onChange={() => setMode("account")}
                  />
                  Desde cuenta
                </label>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="radio"
                    checked={mode === "third_party"}
                    onChange={() => setMode("third_party")}
                  />
                  Contra tercero (sin caja)
                </label>
              </div>
            </div>
          )}
          {isTransfer ? (
            <div className="space-y-1.5">
              <Label>Tercero contraparte</Label>
              <EntitySelect
                value={thirdPartyId}
                onChange={setThirdPartyId}
                options={tpOptions.map((tp: any) => ({ id: tp.id, label: tp.name }))}
                placeholder="Seleccione el tercero"
              />
              {selectedTp !== undefined && amount > 0 && (
                <p className="text-xs text-slate-500">
                  Saldo resultante de {selectedTp.name}: {formatCurrency(resultingBalance ?? 0)}
                </p>
              )}
            </div>
          ) : (
            <div className="space-y-1.5">
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
          )}
          <div className="space-y-1.5">
            <Label>Notas (opcional)</Label>
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} />
          </div>
        </div>
        <DialogFooter className="gap-2">
          <Button variant="outline" className="w-full sm:w-auto" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button
            className="w-full sm:w-auto"
            disabled={!canSubmit || mutation.isPending || transferMutation.isPending}
            onClick={handleSubmit}
          >
            Registrar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function AnnulMovementDialog({
  open, onOpenChange, movement,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  movement: MoneyMovementResponse | null;
}) {
  const [reason, setReason] = useState("");
  const mutation = useAnnulObligationMovement();

  const handleSubmit = () => {
    if (!movement) return;
    mutation.mutate(
      { movementId: movement.id, reason },
      { onSuccess: () => { setReason(""); onOpenChange(false); } }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>Anular Movimiento</DialogTitle></DialogHeader>
        {movement && (
          <div className="space-y-4">
            <p className="text-sm text-slate-600">
              {MOVEMENT_LABELS[movement.movement_type] ?? movement.movement_type} · {formatDate(movement.date)} ·{" "}
              <span className="font-semibold">{formatCurrency(movement.amount)}</span>
            </p>
            <div className="space-y-1.5">
              <Label>Razón de la anulación *</Label>
              <Textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3} maxLength={500} />
              <p className="text-xs text-slate-500">Mínimo 5 caracteres. Revierte saldos y contadores de la obligación.</p>
            </div>
          </div>
        )}
        <DialogFooter className="gap-2">
          <Button variant="outline" className="w-full sm:w-auto" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button
            variant="destructive" className="w-full sm:w-auto"
            disabled={reason.trim().length < 5 || mutation.isPending}
            onClick={handleSubmit}
          >
            Anular
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function AccrueObligationDialog({
  open, onOpenChange, obligationId, isPayable, preview, isLoading, initialTranche,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  obligationId: string;
  isPayable: boolean;
  preview: AccruePreviewResponse | undefined;
  isLoading: boolean;
  initialTranche: boolean;
}) {
  const [categoryId, setCategoryId] = useState("");
  const [includeTranche, setIncludeTranche] = useState(false);
  const { data: categories } = useExpenseCategoriesFlat();
  const mutation = useAccrueObligation();

  // El pre-check del tramo depende de por donde se abrio (boton vs pre-cierre)
  useEffect(() => {
    if (open) setIncludeTranche(initialTranche);
  }, [open, initialTranche]);

  const items = preview?.items ?? [];
  const tranche = preview?.current_tranche ?? null;
  const willAccrueTranche = !!tranche && includeTranche;
  const somethingToAccrue = items.length > 0 || willAccrueTranche;
  const needsCategory = isPayable && somethingToAccrue;
  const canSubmit = somethingToAccrue && (!needsCategory || !!categoryId);
  const total =
    items.reduce((sum, i) => sum + Number(i.amount), 0) +
    (willAccrueTranche ? Number(tranche!.amount) : 0);

  const handleSubmit = () => {
    mutation.mutate(
      {
        id: obligationId,
        data: {
          include_current_tranche: willAccrueTranche,
          ...(needsCategory ? { expense_category_id: categoryId } : {}),
        },
      },
      { onSuccess: () => { setCategoryId(""); onOpenChange(false); } }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle>Causar Intereses de esta Obligación</DialogTitle></DialogHeader>
        {isLoading ? (
          <p className="py-6 text-center text-sm text-slate-500">Calculando períodos pendientes…</p>
        ) : !items.length && !tranche ? (
          <p className="py-6 text-center text-sm text-slate-500">
            No hay intereses pendientes de causar. El mes en curso se causa cuando termine
            (o como tramo de cierre si el capital queda en $0).
          </p>
        ) : (
          <div className="space-y-4">
            {items.length > 0 && (
              <div className="max-h-56 overflow-y-auto rounded-lg border divide-y">
                {items.map((item) => (
                  <div key={item.period} className="p-2.5 text-sm">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{periodLabel(item.period)}</span>
                      <span className="font-semibold whitespace-nowrap">{formatCurrency(Number(item.amount))}</span>
                    </div>
                    <p className="mt-0.5 text-xs text-slate-400 break-words">{item.breakdown}</p>
                  </div>
                ))}
              </div>
            )}

            {tranche && (
              <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-3 space-y-1.5">
                <div className="flex items-start gap-2">
                  <Checkbox
                    id="include-tranche"
                    checked={includeTranche}
                    onCheckedChange={(v) => setIncludeTranche(!!v)}
                    className="mt-0.5"
                  />
                  <div className="min-w-0">
                    <Label htmlFor="include-tranche" className="font-medium cursor-pointer">
                      Causar también el tramo del mes en curso ({periodLabel(tranche.period)}):{" "}
                      <span className="font-semibold">{formatCurrency(Number(tranche.amount))}</span>
                    </Label>
                    <p className="mt-0.5 text-xs text-slate-500 break-words">{tranche.breakdown}</p>
                    <p className="mt-1 text-xs text-indigo-700">
                      Disponible porque el capital está en $0 — los días que corrieron este mes.
                      Útil para cobrar todo antes de cerrar la obligación.
                    </p>
                  </div>
                </div>
              </div>
            )}

            <div className="rounded-lg bg-slate-50 p-2.5 text-sm flex items-center justify-between">
              <span className="text-slate-600">Total a causar</span>
              <span className="font-semibold">{formatCurrency(total)}</span>
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
              La causación registra el interés en el P&L (devengo) sin mover dinero.
              El pago se registra aparte con "{isPayable ? "Pagar" : "Recaudar"} Intereses".
            </p>
          </div>
        )}
        <DialogFooter className="gap-2">
          <Button variant="outline" className="w-full sm:w-auto" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button className="w-full sm:w-auto" disabled={!canSubmit || mutation.isPending} onClick={handleSubmit}>
            <CalendarCheck className="h-4 w-4 mr-2" />Causar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function SettleChoiceDialog({
  open, onOpenChange, preview, isPayable, onAccrueFirst, onForgive, isSettling,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  preview: AccruePreviewResponse | undefined;
  isPayable: boolean;
  onAccrueFirst: () => void;
  onForgive: () => void;
  isSettling: boolean;
}) {
  const [choice, setChoice] = useState<null | "accrue" | "forgive">(null);

  useEffect(() => {
    if (open) setChoice(null); // eleccion consciente en cada apertura, sin default (#63)
  }, [open]);

  const items = preview?.items ?? [];
  const tranche = preview?.current_tranche ?? null;
  const total =
    items.reduce((sum, i) => sum + Number(i.amount), 0) + Number(tranche?.amount ?? 0);
  const verb = isPayable ? "pagar" : "cobrar";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>Cerrar Obligación — intereses sin causar</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
              <div>
                Esta obligación tiene <span className="font-semibold">{formatCurrency(total)}</span> de
                intereses sin causar:
                <ul className="mt-1 list-disc pl-4 text-xs space-y-0.5">
                  {items.map((i) => (
                    <li key={i.period}>{periodLabel(i.period)} (vencido): {formatCurrency(Number(i.amount))}</li>
                  ))}
                  {tranche && (
                    <li>Tramo del mes en curso ({periodLabel(tranche.period)}): {formatCurrency(Number(tranche.amount))}</li>
                  )}
                </ul>
              </div>
            </div>
          </div>

          <label className="flex items-start gap-2 rounded-lg border p-3 cursor-pointer hover:bg-slate-50">
            <input
              type="radio"
              name="settle-choice"
              className="mt-1"
              checked={choice === "accrue"}
              onChange={() => setChoice("accrue")}
            />
            <span className="text-sm">
              <span className="font-medium">Causar los intereses primero</span>
              <span className="block text-xs text-slate-500">
                Abre la causación de esta obligación. Después de {verb} los intereses, podrá cerrarla.
              </span>
            </span>
          </label>
          <label className="flex items-start gap-2 rounded-lg border p-3 cursor-pointer hover:bg-slate-50">
            <input
              type="radio"
              name="settle-choice"
              className="mt-1"
              checked={choice === "forgive"}
              onChange={() => setChoice("forgive")}
            />
            <span className="text-sm">
              <span className="font-medium">Cerrar sin causarlos (condonar {formatCurrency(total)})</span>
              <span className="block text-xs text-slate-500">
                Los intereses no se registran ni se {verb === "pagar" ? "pagan" : "cobran"}. La obligación
                queda cerrada y no acepta más movimientos. No se puede deshacer.
              </span>
            </span>
          </label>
        </div>
        <DialogFooter className="gap-2">
          <Button variant="outline" className="w-full sm:w-auto" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button
            className="w-full sm:w-auto"
            variant={choice === "forgive" ? "destructive" : "default"}
            disabled={choice === null || isSettling}
            onClick={() => (choice === "accrue" ? onAccrueFirst() : onForgive())}
          >
            {choice === "forgive" ? "Cerrar Obligación" : "Continuar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function ObligationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const handleBack = useReturnToBack();
  const { hasPermission } = usePermissions();
  const canManage = hasPermission("treasury.manage_obligations");

  const { data: obligation, isLoading } = useFinancialObligation(id!);
  const { data: statement } = useObligationStatement(id!);
  const { data: accruePreview, isLoading: previewLoading } = useAccruePreview(id!, canManage);
  const settleMutation = useSettleObligation();

  const [action, setAction] = useState<null | { kind: ActionKind; title: string; max?: number }>(null);
  const [showSettle, setShowSettle] = useState(false);
  const [showSettleChoice, setShowSettleChoice] = useState(false);
  const [showAccrue, setShowAccrue] = useState(false);
  const [accrueWithTranche, setAccrueWithTranche] = useState(false);
  const [annulTarget, setAnnulTarget] = useState<MoneyMovementResponse | null>(null);

  if (isLoading || !obligation) {
    return <p className="py-8 text-center text-sm text-slate-500">Cargando…</p>;
  }

  const isPayable = obligation.direction === "payable";
  const isActive = obligation.status === "active";
  const capital = Number(obligation.capital_balance);
  const pending = Number(obligation.pending_interest);

  const overdueCount = accruePreview?.items?.length ?? 0;
  const unaccruedTotal =
    (accruePreview?.items ?? []).reduce((sum, i) => sum + Number(i.amount), 0) +
    Number(accruePreview?.current_tranche?.amount ?? 0);

  const handleSettleClick = () => {
    // Cerrar con intereses sin causar = condonarlos — eleccion explicita (#63)
    if (unaccruedTotal > 0) setShowSettleChoice(true);
    else setShowSettle(true);
  };

  const actions = [
    {
      kind: "capital" as const,
      label: isPayable ? "Abono a Capital" : "Recaudo de Capital",
      icon: <Banknote className="h-4 w-4 mr-2" />,
      max: capital,
    },
    {
      kind: "interest" as const,
      label: isPayable ? "Pagar Intereses" : "Recaudar Intereses",
      icon: <HandCoins className="h-4 w-4 mr-2" />,
      max: pending,
    },
    {
      kind: "disbursement" as const,
      label: "Desembolso Adicional",
      icon: <Landmark className="h-4 w-4 mr-2" />,
      max: undefined,
    },
  ];

  return (
    <div className="space-y-4">
      <PageHeader
        title={obligation.third_party_name}
        description={`Obligación ${isPayable ? "por pagar" : "por cobrar"} · ${Number(obligation.monthly_rate).toFixed(2)}% mensual`}
      >
        <div className="flex flex-wrap items-center gap-2">
          {canManage && isActive && capital === 0 && pending === 0 && (
            <Button variant="outline" className="w-full sm:w-auto" onClick={handleSettleClick}>
              <Lock className="h-4 w-4 mr-2" />Cerrar Obligación
            </Button>
          )}
          <Button variant="outline" className="w-full sm:w-auto" onClick={handleBack}>
            <ArrowLeft className="h-4 w-4 mr-2" />Volver
          </Button>
        </div>
      </PageHeader>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
        <Card className="shadow-sm">
          <CardContent className="pt-4 pb-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Capital Vigente</p>
            <p className="mt-1 text-xl font-bold text-slate-900">{formatCurrency(capital)}</p>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardContent className="pt-4 pb-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Intereses Pendientes</p>
            <p className="mt-1 text-xl font-bold text-amber-600">{formatCurrency(pending)}</p>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardContent className="pt-4 pb-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Último Mes Causado</p>
            <p className="mt-1 text-xl font-bold text-slate-900">{periodLabel(obligation.last_accrued_period)}</p>
            <p className="text-xs text-slate-500">Causa desde {periodLabel(obligation.accrual_start_period)}</p>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardContent className="pt-4 pb-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Estado</p>
            <div className="mt-1.5 flex items-center gap-2">
              <Badge variant={isActive ? "default" : "secondary"}>{isActive ? "Activa" : "Cerrada"}</Badge>
              <Badge variant="outline">{isPayable ? "Por Pagar" : "Por Cobrar"}</Badge>
            </div>
            <p className="mt-1 text-xs text-slate-500">
              <ThirdPartyLink id={obligation.third_party_id}>Estado de cuenta del tercero</ThirdPartyLink>
            </p>
          </CardContent>
        </Card>
      </div>

      {canManage && isActive && (
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            className="w-full sm:w-auto"
            onClick={() => { setAccrueWithTranche(false); setShowAccrue(true); }}
          >
            <CalendarCheck className="h-4 w-4 mr-2" />
            Causar Intereses{overdueCount > 0 ? ` (${overdueCount})` : ""}
          </Button>
          {actions.map((a) => (
            <Button
              key={a.kind}
              variant="outline"
              className="w-full sm:w-auto"
              onClick={() => setAction({ kind: a.kind, title: a.label, max: a.max })}
            >
              {a.icon}{a.label}
            </Button>
          ))}
        </div>
      )}

      {obligation.notes && (
        <Card className="shadow-sm">
          <CardContent className="pt-4 pb-4 text-sm text-slate-600">{obligation.notes}</CardContent>
        </Card>
      )}

      <Card className="shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <CalendarClock className="h-4 w-4 text-slate-400" />Movimientos de la Obligación
          </CardTitle>
        </CardHeader>
        <CardContent>
          {(statement ?? []).length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-500">Sin movimientos aún.</p>
          ) : (
            <>
              {/* Desktop */}
              <div className="hidden md:block">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Fecha</TableHead>
                      <TableHead>Tipo</TableHead>
                      <TableHead>Descripción</TableHead>
                      <TableHead className="text-right">Monto</TableHead>
                      <TableHead>Estado</TableHead>
                      {canManage && <TableHead className="w-10" />}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(statement ?? []).map((m) => (
                      <TableRow key={m.id} className={m.status === "annulled" ? "opacity-50" : ""}>
                        <TableCell className="whitespace-nowrap">{formatDate(m.date)}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{MOVEMENT_LABELS[m.movement_type] ?? m.movement_type}</Badge>
                        </TableCell>
                        <TableCell className="max-w-md truncate text-sm text-slate-600">{m.description}</TableCell>
                        <TableCell className="text-right font-semibold">{formatCurrency(m.amount)}</TableCell>
                        <TableCell><StatusBadge status={m.status} /></TableCell>
                        {canManage && (
                          <TableCell>
                            {m.status === "confirmed" && isActive && (
                              <Button
                                variant="ghost" size="sm"
                                className="h-7 px-2 text-red-600 hover:bg-red-50"
                                onClick={() => setAnnulTarget(m)}
                              >
                                <XCircle className="h-4 w-4" />
                              </Button>
                            )}
                          </TableCell>
                        )}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Mobile cards */}
              <div className="md:hidden space-y-2">
                {(statement ?? []).map((m) => (
                  <div key={m.id} className={`rounded-lg border p-3 ${m.status === "annulled" ? "opacity-50" : ""}`}>
                    <div className="flex items-center justify-between gap-2">
                      <Badge variant="outline">{MOVEMENT_LABELS[m.movement_type] ?? m.movement_type}</Badge>
                      <span className="font-semibold">{formatCurrency(m.amount)}</span>
                    </div>
                    <div className="mt-1 flex items-center justify-between gap-2 text-xs text-slate-500">
                      <span>{formatDate(m.date)}</span>
                      <StatusBadge status={m.status} />
                    </div>
                    <p className="mt-1 text-xs text-slate-500 break-words">{m.description}</p>
                    {canManage && m.status === "confirmed" && isActive && (
                      <Button
                        variant="outline" size="sm"
                        className="mt-2 w-full text-red-600 border-red-200"
                        onClick={() => setAnnulTarget(m)}
                      >
                        <XCircle className="h-4 w-4 mr-2" />Anular
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {action && (
        <ActionDialog
          open={!!action}
          onOpenChange={(v) => !v && setAction(null)}
          obligationId={obligation.id}
          kind={action.kind}
          title={action.title}
          maxAmount={action.max}
          direction={obligation.direction}
          obligationThirdPartyId={obligation.third_party_id}
        />
      )}
      <AnnulMovementDialog
        open={!!annulTarget}
        onOpenChange={(v) => !v && setAnnulTarget(null)}
        movement={annulTarget}
      />
      <AccrueObligationDialog
        open={showAccrue}
        onOpenChange={setShowAccrue}
        obligationId={obligation.id}
        isPayable={isPayable}
        preview={accruePreview}
        isLoading={previewLoading}
        initialTranche={accrueWithTranche}
      />
      <SettleChoiceDialog
        open={showSettleChoice}
        onOpenChange={setShowSettleChoice}
        preview={accruePreview}
        isPayable={isPayable}
        isSettling={settleMutation.isPending}
        onAccrueFirst={() => {
          setShowSettleChoice(false);
          setAccrueWithTranche(true);
          setShowAccrue(true);
        }}
        onForgive={() =>
          settleMutation.mutate(obligation.id, { onSuccess: () => setShowSettleChoice(false) })
        }
      />
      <ConfirmDialog
        open={showSettle}
        onOpenChange={setShowSettle}
        title="Cerrar Obligación"
        description="La obligación quedará cerrada y no aceptará más movimientos ni causaciones. Esta acción no se puede deshacer."
        confirmLabel="Cerrar Obligación"
        onConfirm={() => settleMutation.mutate(obligation.id, { onSuccess: () => setShowSettle(false) })}
      />
    </div>
  );
}
