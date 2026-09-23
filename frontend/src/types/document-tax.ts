/**
 * IVA y retenciones sobre lo que SAC factura (CC-013 / Q-41).
 *
 * El sistema REGISTRA lo que Siigo emitio (D1): el monto se digita y es
 * editable; la tasa solo sirve para llenar el campo.
 *
 * ⚠️ Los montos llegan del backend como `Decimal`, o sea STRING en el JSON,
 * aunque el tipo diga `number`. Cualquier suma sobre ellos concatena texto en
 * vez de sumar — es el bloqueante (b) de #93 y el "Deuda total NaN" de #107.
 * Por eso el servicio los coerciona en la FRONTERA con `num()`.
 */
export type TaxType = "iva" | "retefuente" | "reteiva" | "ica";

/** Direccion del efecto sobre el CLIENTE. La entidad recibe el contrario. */
export const TAX_SIGN_ON_CUSTOMER: Record<TaxType, 1 | -1> = {
  iva: 1,
  retefuente: -1,
  reteiva: -1,
  ica: -1,
};

export const TAX_TYPE_LABELS: Record<TaxType, string> = {
  iva: "IVA",
  retefuente: "ReteFuente",
  reteiva: "ReteIVA",
  ica: "ICA",
};

export interface DocumentTaxCreate {
  tax_type: TaxType;
  municipality?: string | null;
  concept?: string | null;
  rate?: number | null;
  /**
   * Sobre QUE se aplica la tasa. El monto de la base lo deriva el SERVIDOR de
   * lo que realmente facturo (D5) — la pantalla no lo manda, y en un abono ni
   * siquiera lo conoce: la maquila y el flete salen de las tarifas vigentes al
   * liquidar.
   */
  base_kind?: "subtotal" | "iva";
  amount: number;
}

export interface DocumentTax {
  id: string;
  third_party_id: string;
  third_party_name: string | null;
  tax_type: TaxType;
  municipality: string | null;
  concept: string | null;
  rate: number | null;
  base_amount: number;
  amount: number;
  reverted_at: string | null;
}

/** Coercion en la frontera: el backend serializa Decimal como string. */
export function numTax(value: unknown): number {
  const n = typeof value === "number" ? value : parseFloat(String(value ?? 0));
  return Number.isFinite(n) ? n : 0;
}
