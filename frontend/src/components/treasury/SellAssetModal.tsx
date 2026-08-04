import { useState, useEffect, useMemo } from "react";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { useThirdParties, useMoneyAccounts } from "@/hooks/useMasterData";
import { useSellAsset } from "@/hooks/useFixedAssets";
import { formatCurrency } from "@/utils/formatters";
import type { FixedAsset } from "@/types/fixed-asset";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  asset: FixedAsset;
}

type Counterpart = "account" | "third_party" | null;

export function SellAssetModal({ open, onOpenChange, asset }: Props) {
  const { data: thirdPartiesData } = useThirdParties();
  const { data: accountsData } = useMoneyAccounts();
  const sell = useSellAsset();

  const accounts = accountsData?.items ?? [];
  // Comprador: cualquier tercero menos provision/liability (espejo #32, backend valida igual)
  const buyers = (thirdPartiesData?.items ?? []).filter(
    (t) =>
      !(t.categories ?? []).some(
        (c) => c.behavior_type === "provision" || c.behavior_type === "liability",
      ),
  );

  const [salePrice, setSalePrice] = useState(0);
  // Sin default — elección explícita de contrapartida (#63)
  const [counterpart, setCounterpart] = useState<Counterpart>(null);
  const [accountId, setAccountId] = useState("");
  const [thirdPartyId, setThirdPartyId] = useState("");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (open) {
      setSalePrice(0);
      setCounterpart(null);
      setAccountId("");
      setThirdPartyId("");
      setNotes("");
    }
  }, [open]);

  const gain = salePrice - asset.current_value;

  // Warning informativo de depreciaciones pendientes (mismo criterio de RevalueAssetModal)
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

  const canSubmit =
    salePrice > 0 &&
    counterpart !== null &&
    (counterpart === "account" ? !!accountId : !!thirdPartyId);

  const handleSubmit = () => {
    sell.mutate(
      {
        id: asset.id,
        data: {
          sale_price: salePrice,
          account_id: counterpart === "account" ? accountId : null,
          third_party_id: counterpart === "third_party" ? thirdPartyId : null,
          notes: notes.trim() || null,
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
          <DialogTitle>Vender Activo</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="rounded-lg bg-slate-50 border border-slate-200 p-3 text-sm flex justify-between gap-3">
            <span className="text-slate-500">Valor en libros</span>
            <span className="font-medium tabular-nums">{formatCurrency(asset.current_value)}</span>
          </div>

          <div>
            <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Precio de venta *
            </Label>
            <MoneyInput value={salePrice} onChange={setSalePrice} placeholder="0" />
          </div>

          <div>
            <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              La plata entra a *
            </Label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-1">
              <label className={radioClass(counterpart === "account")}>
                <input
                  type="radio"
                  name="saleCounterpart"
                  checked={counterpart === "account"}
                  onChange={() => { setCounterpart("account"); setThirdPartyId(""); }}
                  className="accent-emerald-600"
                />
                Cuenta de dinero
              </label>
              <label className={radioClass(counterpart === "third_party")}>
                <input
                  type="radio"
                  name="saleCounterpart"
                  checked={counterpart === "third_party"}
                  onChange={() => { setCounterpart("third_party"); setAccountId(""); }}
                  className="accent-emerald-600"
                />
                A crédito (tercero)
              </label>
            </div>
            {counterpart !== null && (
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
                    options={buyers.map((t) => ({ id: t.id, label: t.name }))}
                    placeholder="Seleccionar comprador..."
                  />
                )}
                <p className="text-xs mt-1 text-slate-400">
                  {counterpart === "account"
                    ? "El precio entra a la cuenta hoy"
                    : "El comprador te queda debiendo el precio → aparece en ACTIVOS (cuentas por cobrar) y se cobra por el flujo normal de recaudos. Si el tercero tenía saldo en contra, la cuenta por cobrar primero lo consume."}
                </p>
              </div>
            )}
          </div>

          <div>
            <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Notas</Label>
            <Input
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Ej: comprador, placa, factura"
              maxLength={500}
            />
          </div>

          {/* Preview vivo de ganancia/pérdida */}
          {salePrice > 0 && (
            <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-3 text-sm space-y-1">
              <div className="flex justify-between gap-3">
                <span className="text-slate-500">Precio − valor en libros</span>
                <span
                  className={`font-semibold tabular-nums ${
                    gain > 0 ? "text-emerald-700" : gain < 0 ? "text-red-600" : "text-slate-700"
                  }`}
                >
                  {gain >= 0 ? "Ganancia " : "Pérdida "}
                  {formatCurrency(Math.abs(gain))}
                </span>
              </div>
              <p className="text-xs text-indigo-600 pt-1">
                Fecha del evento: hoy. La diferencia va al Estado de Resultados como
                "Ganancia/Pérdida por Venta de Activos"; el activo sale del balance.
              </p>
            </div>
          )}

          {hasPendingDepreciation && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              Este activo tiene depreciaciones pendientes de meses anteriores. La venta usa
              el valor en libros actual — si aplicas primero la depreciación pendiente, el
              libro baja y la ganancia registrada sube.
            </div>
          )}
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" onClick={() => onOpenChange(false)} className="w-full sm:w-auto">
            Cancelar
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!canSubmit || sell.isPending}
            className="w-full sm:w-auto bg-emerald-600 hover:bg-emerald-700"
          >
            {sell.isPending ? "Vendiendo..." : "Vender"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
