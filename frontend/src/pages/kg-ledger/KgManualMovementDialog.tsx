import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { useCreateKgManualMovement } from "@/hooks/useKgLedger";
import { toLocalDateInput } from "@/utils/formatters";
import {
  STAGE_LABELS,
  type IntersedeStage,
  type KgLedgerAccountResponse,
} from "@/types/kg-ledger";

interface KgManualMovementDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  accounts: KgLedgerAccountResponse[];
  /** Pre-seleccionar cuenta (statement) — el selector queda deshabilitado */
  defaultAccountId?: string;
}

/**
 * Ajuste manual auditado del ledger kg (D15/D16): delta ± con motivo
 * obligatorio y fecha no futura. source_type='manual_adjustment'.
 */
export function KgManualMovementDialog({
  open,
  onOpenChange,
  accounts,
  defaultAccountId,
}: KgManualMovementDialogProps) {
  const createMovement = useCreateKgManualMovement();

  const [accountId, setAccountId] = useState("");
  const [direction, setDirection] = useState<"in" | "out">("in");
  const [quantity, setQuantity] = useState(0);
  const [date, setDate] = useState(toLocalDateInput());
  const [description, setDescription] = useState("");
  const [reason, setReason] = useState("");
  // #107 D1: en intersede el movimiento va a UNA etapa (horno o crisol); el
  // backend lo exige con 422 y lo prohibe en las demas cuentas.
  const [stage, setStage] = useState<IntersedeStage | "">("");

  const todayStr = toLocalDateInput();
  const isIntersede = accounts.find((a) => a.id === accountId)?.account_type === "intersede";

  useEffect(() => {
    if (open) {
      setAccountId(defaultAccountId ?? "");
      setDirection("in");
      setQuantity(0);
      setDate(toLocalDateInput());
      setDescription("");
      setReason("");
      setStage("");
    }
  }, [open, defaultAccountId]);

  const isFuture = date ? date > todayStr : false;
  const canSubmit =
    !!accountId && quantity > 0 && !!date && !isFuture && !!description.trim() && !!reason.trim() &&
    (!isIntersede || !!stage);

  const submit = () => {
    if (!canSubmit) return;
    createMovement.mutate(
      {
        account_id: accountId,
        delta_kg: direction === "in" ? quantity : -quantity,
        transaction_date: date,
        description: description.trim(),
        reason: reason.trim(),
        stage: isIntersede && stage ? stage : null,
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent onClick={(e) => e.stopPropagation()}>
        <DialogHeader>
          <DialogTitle>Movimiento Manual (kg)</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuenta *</Label>
            <EntitySelect
              value={accountId}
              onChange={setAccountId}
              options={accounts.map((a) => ({ id: a.id, label: `${a.code} - ${a.display_name}` }))}
              placeholder="Cuenta kg..."
              disabled={!!defaultAccountId}
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Dirección *</Label>
              <Select value={direction} onValueChange={(v) => setDirection(v as "in" | "out")}>
                <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="in">Entrada (+)</SelectItem>
                  <SelectItem value="out">Salida (−)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cantidad (kg) *</Label>
              <MoneyInput value={quantity} onChange={setQuantity} decimals={2} placeholder="0,00" />
            </div>
          </div>
          {isIntersede && (
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Etapa *</Label>
              <Select value={stage} onValueChange={(v) => setStage(v as IntersedeStage)}>
                <SelectTrigger className="w-full"><SelectValue placeholder="¿Dónde está el plomo?" /></SelectTrigger>
                <SelectContent>
                  {(Object.keys(STAGE_LABELS) as IntersedeStage[]).map((s) => (
                    <SelectItem key={s} value={s}>{STAGE_LABELS[s]}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-slate-500 mt-0.5">
                La deuda de planta con Circunvalar es una sola; la etapa dice si el plomo está en el horno (crudo) o ya pasó al crisol.
              </p>
            </div>
          )}
          <div>
            <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha *</Label>
            <Input
              type="date"
              value={date}
              max={todayStr}
              onChange={(e) => setDate(e.target.value)}
              className={isFuture ? "border-red-300" : ""}
            />
            {isFuture && <p className="text-xs text-red-500 mt-0.5">La fecha no puede ser futura</p>}
          </div>
          <div>
            <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Descripción *</Label>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={300}
              placeholder="Ej: Diferencia de cuadre semanal"
            />
          </div>
          <div>
            <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Motivo *</Label>
            <Textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              maxLength={180}
              rows={2}
              placeholder="Motivo del ajuste (obligatorio, auditado)"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} className="w-full sm:w-auto">
            Cancelar
          </Button>
          <Button
            onClick={submit}
            disabled={!canSubmit || createMovement.isPending}
            className="bg-emerald-600 hover:bg-emerald-700 w-full sm:w-auto"
          >
            {createMovement.isPending ? "Guardando..." : "Registrar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
