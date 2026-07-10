import { useState, useEffect, useMemo } from "react";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { useThirdParties, useMoneyAccounts } from "@/hooks/useMasterData";
import { useRevalueAsset } from "@/hooks/useFixedAssets";
import { formatCurrency } from "@/utils/formatters";
import type { FixedAsset, RevaluationType } from "@/types/fixed-asset";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  asset: FixedAsset;
}

type Counterpart = "account" | "third_party";

/** Meses restantes de depreciación (misma fórmula del backend: ceil((valor − residual) / cuota)). */
function remainingMonths(value: number, salvage: number, monthly: number): number {
  if (value <= salvage || monthly <= 0) return 0;
  return Math.ceil((value - salvage) / monthly);
}

export function RevalueAssetModal({ open, onOpenChange, asset }: Props) {
  const { data: thirdPartiesData } = useThirdParties();
  const { data: accountsData } = useMoneyAccounts();
  const revalue = useRevalueAsset();

  const accounts = accountsData?.items ?? [];
  const thirdParties = thirdPartiesData?.items ?? [];

  const [revalType, setRevalType] = useState<RevaluationType>("increase");
  const [amount, setAmount] = useState(0);
  const [monthsExtended, setMonthsExtended] = useState(0);
  const [counterpart, setCounterpart] = useState<Counterpart>("account");
  const [accountId, setAccountId] = useState("");
  const [thirdPartyId, setThirdPartyId] = useState("");
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (open) {
      setRevalType("increase");
      setAmount(0);
      setMonthsExtended(0);
      setCounterpart("account");
      setAccountId("");
      setThirdPartyId("");
      setReason("");
    }
  }, [open]);

  const isIncrease = revalType === "increase";
  const depreciable = asset.current_value - asset.salvage_value;

  // Preview en vivo (espejo de la fórmula del backend)
  const preview = useMemo(() => {
    const before = remainingMonths(asset.current_value, asset.salvage_value, asset.monthly_depreciation);
    const after = before + (isIncrease ? monthsExtended : 0);
    const valueAfter = isIncrease ? asset.current_value + amount : asset.current_value - amount;
    let monthlyAfter = asset.monthly_depreciation;
    if (valueAfter > asset.salvage_value && after >= 1) {
      monthlyAfter = Math.round(((valueAfter - asset.salvage_value) / after) * 100) / 100;
    }
    return { remainingBefore: before, remainingAfter: after, valueAfter, monthlyAfter };
  }, [asset, amount, monthsExtended, isIncrease]);

  // G1: depreciaciones pendientes — la cuota nueva rige para lo que se aplique después
  const hasPendingDepreciation = useMemo(() => {
    if (asset.status !== "active") return false;
    const currentPeriod = new Date().toISOString().slice(0, 7);
    const startPeriod = asset.depreciation_start_date.slice(0, 7);
    if (startPeriod > currentPeriod) return false;
    const lastPeriod = (asset.depreciations ?? [])
      .map((d) => d.period.replace("B", ""))
      .sort()
      .pop();
    return !lastPeriod || lastPeriod < currentPeriod;
  }, [asset]);

  const needsExtension = isIncrease && preview.remainingBefore === 0;
  const decreaseTooBig = !isIncrease && amount > depreciable;

  const canSubmit =
    amount > 0 &&
    !decreaseTooBig &&
    (!needsExtension || monthsExtended >= 1) &&
    (counterpart === "account" ? !!accountId : !!thirdPartyId);

  const handleSubmit = () => {
    revalue.mutate(
      {
        id: asset.id,
        data: {
          revaluation_type: revalType,
          amount,
          months_extended: isIncrease ? monthsExtended : 0,
          source_account_id: counterpart === "account" ? accountId : null,
          third_party_id: counterpart === "third_party" ? thirdPartyId : null,
          reason: reason.trim() || null,
        },
      },
      { onSuccess: () => onOpenChange(false) },
    );
  };

  const radioClass = (active: boolean) =>
    `flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-colors text-sm ${
      active ? "border-emerald-500 bg-emerald-50 font-medium" : "border-slate-200 hover:bg-slate-50"
    }`;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Revalorizar Activo</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tipo *</Label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-1">
              <label className={radioClass(isIncrease)}>
                <input
                  type="radio"
                  name="revalType"
                  checked={isIncrease}
                  onChange={() => setRevalType("increase")}
                  className="accent-emerald-600"
                />
                Alza (mejora / inversión)
              </label>
              <label className={radioClass(!isIncrease)}>
                <input
                  type="radio"
                  name="revalType"
                  checked={!isIncrease}
                  onChange={() => { setRevalType("decrease"); setMonthsExtended(0); }}
                  className="accent-emerald-600"
                />
                Baja (recuperación de valor)
              </label>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Monto *</Label>
              <MoneyInput value={amount} onChange={setAmount} placeholder="0" />
              {decreaseTooBig && (
                <p className="text-xs mt-1 text-red-600">
                  Máximo {formatCurrency(depreciable)} — el valor no puede caer bajo el residual
                </p>
              )}
            </div>
            {isIncrease && (
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Meses de vida útil adicionales
                </Label>
                <Input
                  type="number"
                  min={0}
                  max={600}
                  step={1}
                  value={monthsExtended || ""}
                  onChange={(e) => setMonthsExtended(parseInt(e.target.value) || 0)}
                  placeholder="0"
                />
                {needsExtension && monthsExtended < 1 && (
                  <p className="text-xs mt-1 text-red-600">
                    El activo no tiene meses restantes — extienda la vida útil (≥ 1)
                  </p>
                )}
              </div>
            )}
          </div>

          <div>
            <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Contrapartida *</Label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-1">
              <label className={radioClass(counterpart === "account")}>
                <input
                  type="radio"
                  name="counterpart"
                  checked={counterpart === "account"}
                  onChange={() => { setCounterpart("account"); setThirdPartyId(""); }}
                  className="accent-emerald-600"
                />
                {isIncrease ? "Pago desde Cuenta" : "Reembolso a Cuenta"}
              </label>
              <label className={radioClass(counterpart === "third_party")}>
                <input
                  type="radio"
                  name="counterpart"
                  checked={counterpart === "third_party"}
                  onChange={() => { setCounterpart("third_party"); setAccountId(""); }}
                  className="accent-emerald-600"
                />
                {isIncrease ? "A Crédito (Tercero)" : "A Cargo del Tercero"}
              </label>
            </div>
            <div className="mt-2">
              {counterpart === "account" ? (
                <EntitySelect
                  value={accountId}
                  onChange={setAccountId}
                  options={accounts.map((a) => ({ id: a.id, label: `${a.name} (${formatCurrency(a.current_balance)})` }))}
                  placeholder="Seleccionar cuenta..."
                />
              ) : (
                <EntitySelect
                  value={thirdPartyId}
                  onChange={setThirdPartyId}
                  options={thirdParties.map((t) => ({ id: t.id, label: t.name }))}
                  placeholder="Seleccionar tercero..."
                />
              )}
              <p className="text-xs mt-1 text-slate-400">
                {isIncrease
                  ? counterpart === "account"
                    ? "El monto sale de la cuenta"
                    : "Le quedas debiendo el monto al tercero → aparece en PASIVOS (cuentas por pagar). Usa el proveedor que facturó la mejora; si el tercero te debía, primero se consume ese saldo."
                  : counterpart === "account"
                    ? "El monto entra a la cuenta"
                    : "El tercero te queda debiendo el monto → aparece en ACTIVOS (cuentas por cobrar)"}
              </p>
            </div>
          </div>

          <div>
            <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Motivo</Label>
            <Input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Ej: Overhaul de motor, avalúo, corrección"
              maxLength={500}
            />
          </div>

          {/* Preview en vivo */}
          {amount > 0 && !decreaseTooBig && (
            <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-3 text-sm space-y-1">
              <div className="flex justify-between gap-3">
                <span className="text-slate-500">Valor</span>
                <span className="font-medium tabular-nums">
                  {formatCurrency(asset.current_value)} → {formatCurrency(preview.valueAfter)}
                </span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-slate-500">Cuota mensual</span>
                <span className="font-medium tabular-nums">
                  {formatCurrency(asset.monthly_depreciation)} → {formatCurrency(preview.monthlyAfter)}
                </span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-slate-500">Meses restantes</span>
                <span className="font-medium tabular-nums">
                  {preview.remainingBefore} → {preview.remainingAfter}
                </span>
              </div>
              <p className="text-xs text-indigo-600 pt-1">
                Fecha del evento: hoy. Sin efecto en el P&L — la contrapartida es {counterpart === "account" ? "la cuenta" : "el tercero"}.
              </p>
            </div>
          )}

          {/* G1: warning depreciaciones pendientes */}
          {hasPendingDepreciation && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              Este activo tiene depreciaciones pendientes de meses anteriores. Aplícalas primero
              para que conserven la cuota anterior — la cuota nueva rige para todo lo que se
              aplique después de revalorizar.
            </div>
          )}
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" onClick={() => onOpenChange(false)} className="w-full sm:w-auto">
            Cancelar
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!canSubmit || revalue.isPending}
            className="w-full sm:w-auto bg-emerald-600 hover:bg-emerald-700"
          >
            {revalue.isPending ? "Aplicando..." : "Revalorizar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
