import { useId } from "react";
import { formatCurrency } from "@/utils/formatters";

export type AnnulChoice = "annul" | "advance" | null;

interface LinkedPaymentChoiceProps {
  kind: "sale" | "purchase";
  /** Monto del cobro/pago inmediato enlazado (confirmed). Si <= 0, no renderiza nada. */
  amount: number;
  value: AnnulChoice;
  onChange: (v: "annul" | "advance") => void;
}

/**
 * Panel de elección al cancelar una venta/compra con cobro/pago inmediato enlazado
 * (decisión #63, Opción 1). Sin default: el operador elige conscientemente entre anular
 * también el movimiento de caja o dejarlo como anticipo/prepago. Compartido por las
 * DetailPages y el listado para garantizar la misma experiencia.
 */
export function LinkedPaymentChoice({ kind, amount, value, onChange }: LinkedPaymentChoiceProps) {
  const name = useId();
  if (!amount || amount <= 0) return null;

  const isSale = kind === "sale";
  const noun = isSale ? "cobro" : "pago";
  const target = isSale ? "del cliente" : "del proveedor";
  const advanceLabel = isSale ? "Dejar como anticipo" : "Dejar como prepago";
  const advanceDesc = isSale
    ? "el efectivo se conserva como saldo a favor del cliente."
    : "el efectivo egresado queda como saldo a favor (el proveedor nos debe).";

  return (
    <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm space-y-3">
      <p className="text-amber-800">
        Esta {isSale ? "venta" : "compra"} tiene un{" "}
        <strong>{noun} de {formatCurrency(amount)}</strong>
        {isSale ? "" : " al proveedor"} registrado. Elige que hacer con el:
      </p>
      <label className="flex items-start gap-2 cursor-pointer">
        <input
          type="radio"
          name={name}
          className="mt-1"
          checked={value === "annul"}
          onChange={() => onChange("annul")}
        />
        <span>
          <strong>Anular tambien el {noun}</strong> — revierte el efectivo y deja el saldo {target} en cero.
        </span>
      </label>
      <label className="flex items-start gap-2 cursor-pointer">
        <input
          type="radio"
          name={name}
          className="mt-1"
          checked={value === "advance"}
          onChange={() => onChange("advance")}
        />
        <span>
          <strong>{advanceLabel}</strong> — {advanceDesc}
        </span>
      </label>
    </div>
  );
}
