/**
 * Naturaleza de un saldo de impuesto — UN solo criterio para la tabla y las
 * tarjetas de Tesorería → Impuestos y retenciones (plan v1.2 D2).
 *
 * 🔴 La decide el SIGNO, nunca el nombre ni el tipo (#112 D4c y P19). En la
 * convención de terceros, saldo < 0 = le debemos (pasivo) y saldo > 0 = nos
 * debe (activo). La entidad «[Impuestos] IVA por Pagar» puede quedar A FAVOR
 * (más IVA descontable de compras que IVA generado, #122): rotularla por su
 * nombre diría «Por pagar» y sería falso.
 *
 * `payable` solo dice si el saldo se paga. En la sección de retenciones que
 * practicamos el botón Pagar NO lo gobierna este helper (C1): queda como hoy.
 */
export type TaxBalanceNature = {
  kind: "payable" | "favor" | "zero";
  label: string;
  className: string;
  payable: boolean;
};

export function taxBalanceNature(balance: number): TaxBalanceNature {
  const b = Number(balance) || 0;
  if (b < 0) {
    return { kind: "payable", label: "Por pagar", className: "text-red-700 border-red-200 bg-red-50", payable: true };
  }
  if (b > 0) {
    return { kind: "favor", label: "A favor", className: "text-emerald-700 border-emerald-200 bg-emerald-50", payable: false };
  }
  return { kind: "zero", label: "—", className: "text-slate-500 border-slate-200", payable: false };
}
