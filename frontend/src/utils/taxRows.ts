/**
 * Impuestos con % libre al liquidar una Entrada (plan-sac-retefuente-porcentajes
 * v1.5). Funciones puras: la pantalla las usa y los casos U1–U27 las prueban
 * solas.
 *
 * Reglas (Daniel, 23-nov): el % viene de la tarifa del catálogo de Tesorería
 * (el IVA de compra no tiene fila: arranca en 19), se edita a mano y el monto
 * se recalcula en vivo. Gana el último que se tocó (T4): elegir tarifa o editar
 * el % recalcula el monto; editar el monto lo deja fijo.
 */
import { RETENTION_TYPE_LABELS } from "@/types/purchase";
import type { RetentionType } from "@/types/purchase";
import type { RetentionRow } from "@/types/third-party";

/** El IVA de compra no tiene fila en el catálogo: su valor inicial (T8). */
export const IVA_DEFAULT_RATE_PCT = 19;

/** T7: aviso si el % se aleja más de este factor de la referencia. */
export const RATE_WARN_FACTOR = 5;

/** Una retención en la tarjeta de una compra. */
export interface RetRow {
  _key: number;
  /** "" = sin tarifa (fila nueva sin elegir, o T2) */
  config_id: string;
  /** % digitado (o el de la tarifa al elegirla) */
  rate: number;
  /** vigente solo cuando `touched` */
  amount: number;
  /** el monto se editó a mano (T4) */
  touched: boolean;
  /** T2: la tasa que tenía y ya no tiene tarifa usable de su tipo */
  staleRate?: number | null;
  /** T2: «Retención en la Fuente», «ICA — Barranquilla» */
  staleLabel?: string;
  /** Plan retención-sigue v1.3 R1: vino de la liquidación guardada, con su %, y
   * nadie editó el monto en esta sesión. Mientras siga así, si el subtotal de la
   * compra cambió respecto de la apertura, el monto sigue al % (R2). */
  fromSaved?: boolean;
}

/** Retención guardada de la compra (InboundRetentionDetail; Decimal llega string). */
export interface SavedRetention {
  retention_type: RetentionType;
  municipality: string | null;
  rate: number | string | null;
  amount: number | string;
}

/** Impuesto guardado (DocumentTax; Decimal llega string). */
export interface SavedTax {
  rate: number | string | null;
  base_amount: number | string;
  amount: number | string;
}

/** Decimal llega como string en el JSON (#93 b): coerción en la frontera. */
export const toNum = (v: unknown, fallback = 0): number => {
  const n = Number(v);
  return v === null || v === undefined || v === "" || !Number.isFinite(n) ? fallback : n;
};

const round4 = (x: number) => Math.round(x * 10000) / 10000;

/** % × base a 2 decimales (el mismo redondeo de siempre). */
export const pctOf = (base: number, rate: number): number => Math.round(base * rate) / 100;

/** R4: la comparación del subtotal es a centavos. */
const cents = (x: number): number => Math.round(x * 100);

/** Plan retención-sigue v1.3 R0–R6, el ÚNICO predicado (R7) para la retención
 * y el IVA precargados: ¿el monto guardado deja de valer y sigue al %?
 * Solo si la fila vino de lo guardado con su % (R1, R6), hay subtotal de
 * apertura (R6: un borrador de antes no lo trae) y el subtotal actual de la
 * compra en pantalla es distinto de la apertura, a centavos (R0, R4). Los dos
 * lados salen de la misma cuenta de la pantalla: sin cambios, dan igual y el
 * monto guardado se conserva, aunque esté escrito a mano (R3). */
export function followsSubtotal(
  fromSaved: boolean | undefined,
  openSubtotal: number | null | undefined,
  subtotal: number,
  rate: number | null | undefined,
): boolean {
  if (!fromSaved) return false;
  if (typeof openSubtotal !== "number" || !Number.isFinite(openSubtotal)) return false;
  if (typeof rate !== "number" || !Number.isFinite(rate)) return false;
  return cents(subtotal) !== cents(openSubtotal);
}

/** Mismo criterio que normalize_entity_name para comparar municipios. */
const normMuni = (s: string | null | undefined): string | null =>
  s
    ? s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/\s+/g, " ").trim()
    : null;

/** T3: el ÚNICO predicado de «esta tarifa sirve para una compra». */
export const isUsableConfig = (cfg: RetentionRow): boolean =>
  !!cfg.config_id && cfg.is_active && cfg.base_kind === "subtotal";

const typeLabel = (type: RetentionType, municipality: string | null | undefined): string =>
  `${RETENTION_TYPE_LABELS[type]}${municipality ? ` — ${municipality}` : ""}`;

/** T1': la tarifa usable de ese tipo y municipio; prefiere la general (sin
 * concepto). La preferencia la decide esta función, no el orden de la API. */
export function pickTypeConfig(
  type: RetentionType,
  municipality: string | null | undefined,
  catalog: RetentionRow[],
): RetentionRow | null {
  const target = normMuni(municipality);
  const candidates = catalog.filter(
    (c) => isUsableConfig(c) && c.retention_type === type && normMuni(c.municipality) === target,
  );
  return candidates.find((c) => !c.concept) ?? candidates[0] ?? null;
}

/** T3 / D1: la ReteFuente general usable, o ninguna. La usan «+ Retención» y
 * la marca de Tesorería → Retenciones. */
export function defaultRetentionConfig(catalog: RetentionRow[]): RetentionRow | null {
  return (
    catalog.find((c) => isUsableConfig(c) && c.retention_type === "retefuente" && !c.concept) ?? null
  );
}

/** T1' / T2: la retención guardada vuelve con su tasa; la tarifa solo da el tipo. */
export function precargaRetention(saved: SavedRetention, catalog: RetentionRow[], key: number): RetRow {
  const savedRate = saved.rate == null || saved.rate === "" ? null : toNum(saved.rate);
  const amount = toNum(saved.amount);
  const cfg = pickTypeConfig(saved.retention_type, saved.municipality, catalog);
  // R6: sin % guardado el % es el de la tarifa, no el de lo guardado: queda fija
  const fromSaved = savedRate != null;
  if (cfg) {
    return {
      _key: key,
      config_id: cfg.config_id as string,
      rate: savedRate ?? toNum(cfg.rate_pct),
      amount,
      touched: true,
      fromSaved,
    };
  }
  return {
    _key: key,
    config_id: "",
    rate: savedRate ?? 0,
    amount,
    touched: true,
    fromSaved,
    staleRate: savedRate,
    staleLabel: typeLabel(saved.retention_type, saved.municipality),
  };
}

/** C1 de QA 1 (pasada 1): con alcance de recolector (#129, S5) no hay catálogo
 * ni pie de impuestos. Si se precargaran, cada retención sería una fila T2
 * («falta elegir la tarifa») que el usuario NO ve y que le bloquearía Liquidar
 * sin salida. Con alcance no se precarga ninguna, como antes de este cambio;
 * la regla 9f (RELIQ_TAXES) sigue siendo la que le explica por qué no puede. */
export const precargaRetentions = (
  saved: SavedRetention[],
  catalog: RetentionRow[],
  scoped: boolean,
  nextKey: () => number,
): RetRow[] => (scoped ? [] : saved.map((r) => precargaRetention(r, catalog, nextKey())));

/** C1, la misma regla para el borrador: con alcance no se revive ninguna. */
export const reviveDraftRetentions = (
  rows: RetRow[],
  catalog: RetentionRow[],
  scoped: boolean,
): RetRow[] => (scoped ? [] : rows.map((r) => reviveDraftRetention(r, catalog)));

/** T2b: una fila del borrador cuya tarifa ya no sirve no desaparece. */
export function reviveDraftRetention(row: RetRow, catalog: RetentionRow[]): RetRow {
  const ownRate = typeof row.rate === "number" && Number.isFinite(row.rate) ? row.rate : null;
  if (!row.config_id) return ownRate == null ? { ...row, rate: 0 } : row;
  const cfg = catalog.find((c) => c.config_id === row.config_id) ?? null;
  if (cfg && isUsableConfig(cfg)) {
    return ownRate == null ? { ...row, rate: toNum(cfg.rate_pct) } : row;
  }
  const alt = cfg ? pickTypeConfig(cfg.retention_type, cfg.municipality, catalog) : null;
  const rate = ownRate ?? (cfg ? toNum(cfg.rate_pct) : null);
  if (alt) {
    return { ...row, config_id: alt.config_id as string, rate: rate ?? toNum(alt.rate_pct) };
  }
  return {
    ...row,
    config_id: "",
    rate: rate ?? 0,
    staleRate: rate,
    staleLabel: cfg ? typeLabel(cfg.retention_type, cfg.municipality) : undefined,
  };
}

/** Fila nueva con una tarifa: el % de la tarifa y el monto precalculado (D3). */
export const newRetRow = (cfg: RetentionRow | null, key: number): RetRow =>
  cfg
    ? { _key: key, config_id: cfg.config_id as string, rate: toNum(cfg.rate_pct), amount: 0, touched: false }
    : { _key: key, config_id: "", rate: 0, amount: 0, touched: false };

/** T4: elegir una tarifa trae su % y recalcula el monto. */
export const withConfig = (row: RetRow, cfg: RetentionRow): RetRow => ({
  _key: row._key,
  config_id: cfg.config_id as string,
  rate: toNum(cfg.rate_pct),
  amount: 0,
  touched: false,
});

/** T4: editar el % recalcula el monto. Pasar por la casilla sin cambiarlo no
 * cuenta como tocarlo (la misma fila, con `touched` intacto). */
export const withRate = (row: RetRow, rate: number): RetRow =>
  round4(rate) === round4(row.rate) ? row : { ...row, rate, amount: 0, touched: false };

/** T4: editar el monto lo deja fijo; R5: deja de ser «lo guardado». */
export const withAmount = (row: RetRow, amount: number): RetRow => ({
  ...row,
  amount,
  touched: true,
  fromSaved: false,
});

/** El monto que vale: el editado, o el % × base. R2: el guardado sigue al %
 * si el subtotal cambió respecto de la apertura (`followsSubtotal`). */
export const effAmount = (row: RetRow, base: number, openSubtotal?: number | null): number =>
  row.touched && !followsSubtotal(row.fromSaved, openSubtotal, base, row.rate)
    ? row.amount
    : pctOf(base, row.rate);

/** T7: ¿el % se aleja más de 5 veces de la referencia, por arriba o por abajo? */
export const rateWarning = (rate: number, ref: number | null | undefined): boolean =>
  !!ref && ref > 0 && rate > 0 && (rate > RATE_WARN_FACTOR * ref || rate < ref / RATE_WARN_FACTOR);

const fmtPct = (v: number): string =>
  new Intl.NumberFormat("es-CO", { maximumFractionDigits: 4 }).format(v);

/** T7: el texto del aviso ámbar. `refLabel`: «la tarifa» o «el IVA habitual». */
export function rateWarningText(rate: number, ref: number, refLabel: string): string {
  const veces = rate / ref;
  const cuanto =
    veces >= 1
      ? `es ${fmtPct(Math.round(veces * 10) / 10)} veces ${refLabel}`
      : `es menos de la quinta parte de ${refLabel}`;
  return `${fmtPct(rate)} % ${cuanto} (${fmtPct(ref)} %). Revise que no sea un error de dedo`;
}

/** T2: la nota de una retención que se quedó sin tarifa usable (un solo texto, O1). */
export const staleNote = (staleLabel: string | undefined): string =>
  `No hay una tarifa activa de ${staleLabel ?? "esta retención"} sobre el subtotal: créela o reactívela en Tesorería → Retenciones, o quite la retención`;

/** T5: el % tiene que estar en (0, 100]. */
export const rateOutOfRange = (rate: number): boolean => !(rate > 0) || rate > 100;

/** El bloque que va al servidor (`rate` es el % digitado, no el del catálogo). */
export function buildRetentionPayload(
  row: RetRow,
  cfg: RetentionRow,
  base: number,
  openSubtotal?: number | null,
) {
  return {
    retention_type: cfg.retention_type,
    // CC-013 C2: la tarifa, para que el servidor rechace una `base_kind='iva'`
    config_id: cfg.config_id as string,
    municipality: cfg.retention_type === "ica" ? cfg.municipality ?? null : undefined,
    amount: effAmount(row, base, openSubtotal),
    rate: row.rate,
    base: base > 0 ? base : undefined,
  };
}

/* ------------------------------ IVA (T8) ------------------------------ */

export interface IvaState {
  withIva: boolean;
  ivaRate: number;
  ivaAmount: number;
  ivaTouched: boolean;
  /** R1, igual que `RetRow.fromSaved` */
  ivaFromSaved?: boolean;
}

/** T8: el IVA guardado vuelve con su tasa. Retención-sigue v1.3: vuelve FIJO
 * (R3: el monto guardado vale tal cual, calculado o a mano) y marcado como
 * guardado; si el subtotal cambia respecto de la apertura, sigue al % (R2).
 * `base_amount` (la base del servidor) NO se compara: es de otra fuente (C1). */
export function precargaIva(tax: SavedTax): IvaState {
  const hasRate = !(tax.rate == null || tax.rate === "");
  const ivaRate = hasRate ? toNum(tax.rate) : IVA_DEFAULT_RATE_PCT;
  return {
    withIva: true,
    ivaRate,
    ivaAmount: toNum(tax.amount),
    ivaTouched: true,
    // R6: sin % guardado queda fijo
    ivaFromSaved: hasRate,
  };
}

/** Borrador escrito antes de este cambio: sin `ivaRate`, arranca en 19. */
export const reviveDraftIvaRate = (ivaRate: unknown): number =>
  typeof ivaRate === "number" && Number.isFinite(ivaRate) ? ivaRate : IVA_DEFAULT_RATE_PCT;

/** T4 para el IVA: el mismo criterio que `withRate`. `null` = sin cambio. */
export const ivaRatePatch = (current: number, rate: number): Partial<IvaState> | null =>
  round4(rate) === round4(current) ? null : { ivaRate: rate, ivaAmount: 0, ivaTouched: false };

/** R7: el único lugar que decide el monto del IVA (la tarjeta, el pie y el
 * payload leen este). */
export const effIva = (s: IvaState, base: number, openSubtotal?: number | null): number =>
  !s.withIva
    ? 0
    : s.ivaTouched && !followsSubtotal(s.ivaFromSaved, openSubtotal, base, s.ivaRate)
      ? s.ivaAmount
      : pctOf(base, s.ivaRate);

export const ivaPayload = (rate: number, amount: number) => ({
  tax_type: "iva" as const,
  rate,
  base_kind: "subtotal" as const,
  amount,
});
