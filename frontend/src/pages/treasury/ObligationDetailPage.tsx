import { useState } from "react";
import { useParams } from "react-router-dom";
import { ArrowLeft, Banknote, CalendarClock, HandCoins, Landmark, Lock, XCircle } from "lucide-react";
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
import { usePermissions } from "@/hooks/usePermissions";
import { useMoneyAccounts } from "@/hooks/useMasterData";
import { useReturnToBack } from "@/hooks/useReturnToBack";
import {
  useFinancialObligation,
  useObligationStatement,
  useObligationMovement,
  useSettleObligation,
  useAnnulObligationMovement,
} from "@/hooks/useFinancialObligations";
import { formatCurrency, formatDate } from "@/utils/formatters";
import { periodLabel } from "./ObligationsPage";
import type { MoneyMovementResponse } from "@/types/money-movement";

const MOVEMENT_LABELS: Record<string, string> = {
  obligation_disbursement: "Desembolso",
  obligation_interest_accrual: "Interés Causado",
  obligation_interest_payment: "Pago de Intereses",
  obligation_capital_payment: "Abono a Capital",
  loan_disbursement: "Desembolso",
  loan_interest_accrual: "Interés Causado",
  loan_interest_collection: "Recaudo de Intereses",
  loan_capital_collection: "Recaudo de Capital",
};

type ActionKind = "capital" | "interest" | "disbursement";

function ActionDialog({
  open, onOpenChange, obligationId, kind, title, maxAmount,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  obligationId: string;
  kind: ActionKind;
  title: string;
  maxAmount?: number;
}) {
  const [amount, setAmount] = useState(0);
  const [accountId, setAccountId] = useState("");
  const [date, setDate] = useState("");
  const [notes, setNotes] = useState("");
  const { data: accounts } = useMoneyAccounts();
  const mutation = useObligationMovement(kind);

  const overMax = maxAmount !== undefined && amount > maxAmount;
  const canSubmit = amount > 0 && !!accountId && !!date && !overMax;

  const handleSubmit = () => {
    mutation.mutate(
      { id: obligationId, data: { amount, account_id: accountId, date, ...(notes ? { notes } : {}) } },
      { onSuccess: () => { setAmount(0); setAccountId(""); setDate(""); setNotes(""); onOpenChange(false); } }
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
                <p className={`text-xs ${overMax ? "text-red-600" : "text-slate-500"}`}>
                  Máximo: {formatCurrency(maxAmount)}
                </p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label>Fecha</Label>
              <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
          </div>
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
          <div className="space-y-1.5">
            <Label>Notas (opcional)</Label>
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} />
          </div>
        </div>
        <DialogFooter className="gap-2">
          <Button variant="outline" className="w-full sm:w-auto" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button className="w-full sm:w-auto" disabled={!canSubmit || mutation.isPending} onClick={handleSubmit}>
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

export default function ObligationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const handleBack = useReturnToBack();
  const { hasPermission } = usePermissions();
  const canManage = hasPermission("treasury.manage_obligations");

  const { data: obligation, isLoading } = useFinancialObligation(id!);
  const { data: statement } = useObligationStatement(id!);
  const settleMutation = useSettleObligation();

  const [action, setAction] = useState<null | { kind: ActionKind; title: string; max?: number }>(null);
  const [showSettle, setShowSettle] = useState(false);
  const [annulTarget, setAnnulTarget] = useState<MoneyMovementResponse | null>(null);

  if (isLoading || !obligation) {
    return <p className="py-8 text-center text-sm text-slate-500">Cargando…</p>;
  }

  const isPayable = obligation.direction === "payable";
  const isActive = obligation.status === "active";
  const capital = Number(obligation.capital_balance);
  const pending = Number(obligation.pending_interest);

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
            <Button variant="outline" className="w-full sm:w-auto" onClick={() => setShowSettle(true)}>
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
        />
      )}
      <AnnulMovementDialog
        open={!!annulTarget}
        onOpenChange={(v) => !v && setAnnulTarget(null)}
        movement={annulTarget}
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
