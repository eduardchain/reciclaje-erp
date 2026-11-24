/**
 * IVA y retenciones con % libre en lo que SAC factura: Ventas y Salidas de
 * Plomo (plan-sac-impuestos-ventas-libres v1.1). Funciones puras: las usa
 * `DocumentTaxesCard` y los casos U las prueban solas.
 *
 * Reglas (Daniel, 23-nov): el selector elige la TARIFA —una opción por tipo si
 * el tipo tiene una sola, una por tarifa si tiene varias (plan
 * opcion-por-tarifa R1)—, el % viene de ella y se edita a mano, y gana el último
 * que se tocó (R2):
 * elegir el tipo o editar el % recalcula el monto; editar el monto lo deja fijo.
 * La reteIVA va sobre el IVA EFECTIVO de la fila de IVA (A2), que es lo que el
 * servidor guarda como base (`document_tax.py:133-152`).
 */
import type { DocumentTaxCreate, TaxType } from "@/types/document-tax";
import { TAX_SIGN_ON_CUSTOMER, TAX_TYPE_LABELS } from "@/types/document-tax";
import type { RetentionRow } from "@/types/third-party";
import { pctOf, rateOutOfRange, toNum } from "@/utils/taxRows";

export interface TaxFormRow {
  _key: number;
  /** "" = sin elegir; `IVA_KEY`; o el `config_id` de la tarifa elegida (R2). */
  source: string;
  /** % digitado (o el de la tarifa al elegir el tipo) */
  rate: number;
  /** vigente solo cuando `touched` */
  amount: number;
  /** el monto se editó a mano */
  touched: boolean;
}

let taxKeySeq = 0;
/** A1 (Daniel): la fila nueva arranca vacía, como hoy. */
export const createEmptyTax = (): TaxFormRow => ({
  _key: ++taxKeySeq, source: "", rate: 0, amount: 0, touched: false,
});

export const IVA_KEY = "iva";

/** O2: la MISMA normalización que `normalize_entity_name` del servidor (NFKD,
 * sin lo que no es ASCII, minúsculas, strip). No colapsa espacios internos,
 * porque el servidor tampoco. */
export const normMunicipality = (s: string): string =>
  s.normalize("NFKD").replace(/[\u0080-\uFFFF]/g, "").toLowerCase().trim();

/** R6: la clave del servidor para «una fila por documento»: (tipo, municipio). */
export const taxKey = (type: TaxType, municipality: string | null | undefined): string =>
  type === "ica" && municipality ? `ica:${normMunicipality(municipality)}` : type;

/** R0b: el ÚNICO predicado de «esta tarifa sirve en la tarjeta». No es
 * `isUsableConfig` de la Entrada: aquel excluye `base_kind='iva'`, y en una
 * factura la reteIVA sobre el IVA sí va. */
export const isUsableTaxConfig = (cfg: RetentionRow): boolean => !!cfg.config_id && cfg.is_active;

export interface TaxTypeOption {
  /** `IVA_KEY` o el `config_id` de la tarifa (R2: la opción ES la tarifa) */
  key: string;
  /** la clave del servidor para «una fila por documento» (R3) */
  serverKey: string;
  type: TaxType;
  /** la tarifa del tipo (null para el IVA, que sale de `iva_rate_pct`) */
  cfg: RetentionRow | null;
  label: string;
}

/** El nombre de una tarifa: tipo · municipio (ICA) · concepto (si se pide) ·
 * «(sobre el IVA)». */
function configLabel(cfg: RetentionRow, withConcept: boolean): string {
  const type = cfg.retention_type as TaxType;
  return [
    TAX_TYPE_LABELS[type] ?? cfg.retention_type,
    type === "ica" ? cfg.municipality : null,
    withConcept ? cfg.concept : null,
  ].filter(Boolean).join(" · ") + (cfg.base_kind === "iva" ? " (sobre el IVA)" : "");
}

/** R1 (Daniel, 23-nov: «Mostrar las dos»): IVA siempre; las tarifas usables se
 * agrupan por la clave del servidor (tipo, municipio en ICA). Un grupo con UNA
 * tarifa da una opción con el rótulo de siempre; con VARIAS, una opción por
 * tarifa con su concepto — la general primero, después el orden del catálogo.
 * Antes se ofrecía solo la general y la reteIVA «Ventas» al 15 % sobre el IVA
 * de producción no se podía elegir. */
export function taxTypeOptions(configs: RetentionRow[]): TaxTypeOption[] {
  const out: TaxTypeOption[] = [
    { key: IVA_KEY, serverKey: IVA_KEY, type: "iva", cfg: null, label: TAX_TYPE_LABELS.iva },
  ];
  const groups = new Map<string, RetentionRow[]>();
  for (const c of configs) {
    if (!isUsableTaxConfig(c)) continue;
    const type = c.retention_type as TaxType;
    if (type === "ica" && !c.municipality) continue;
    const sk = taxKey(type, c.municipality);
    groups.set(sk, [...(groups.get(sk) ?? []), c]);
  }
  for (const [serverKey, cands] of groups) {
    const ordered = [...cands.filter((c) => !c.concept), ...cands.filter((c) => c.concept)];
    const many = ordered.length > 1;
    for (const cfg of ordered) {
      out.push({
        key: cfg.config_id as string,
        serverKey,
        type: cfg.retention_type as TaxType,
        cfg,
        label: configLabel(cfg, many),
      });
    }
  }
  return out;
}

export const optionFor = (source: string, configs: RetentionRow[]): TaxTypeOption | null =>
  taxTypeOptions(configs).find((o) => o.key === source) ?? null;

/** R3: la clave del servidor de una fila. Una huérfana devuelve su `source`,
 * que ya bloquea por sí sola. */
export function serverKeyOf(row: TaxFormRow, configs: RetentionRow[]): string {
  if (row.source === IVA_KEY) return IVA_KEY;
  return optionFor(row.source, configs)?.serverKey ?? row.source;
}

/** R1: elegir el tipo trae el % de su tarifa (o el IVA de la org) y recalcula. */
export function selectTaxType(row: TaxFormRow, source: string, configs: RetentionRow[], ivaRatePct: number): TaxFormRow {
  const opt = optionFor(source, configs);
  const rate = source === IVA_KEY ? ivaRatePct : toNum(opt?.cfg?.rate_pct);
  return { _key: row._key, source, rate, amount: 0, touched: false };
}

const round4 = (x: number) => Math.round(x * 10000) / 10000;

/** R2 + R8: editar el % recalcula el monto; pasar con Tab sin cambiarlo no
 * cuenta. Si la base que conoce la pantalla es 0 (abono), un monto digitado se
 * conserva: % × 0 lo dejaría en 0 y bloquearía Liquidar (C2). */
export function withTaxRate(row: TaxFormRow, rate: number, base: number): TaxFormRow {
  if (round4(rate) === round4(row.rate)) return row;
  if (base === 0 && row.touched) return { ...row, rate };
  return { ...row, rate, amount: 0, touched: false };
}

export const withTaxAmount = (row: TaxFormRow, amount: number): TaxFormRow => ({ ...row, amount, touched: true });

export const sumLines = (lineAmounts: number[]): number => lineAmounts.reduce((a, b) => a + b, 0);

/** R3 (D6 de #112): el IVA redondea CADA LÍNEA a la tasa de la fila y suma. */
export function suggestedIva(lineAmounts: number[], ivaRatePct: number): number {
  return lineAmounts.reduce((sum, amount) => sum + Math.round(amount * ivaRatePct) / 100, 0);
}

const ivaRowOf = (rows: TaxFormRow[]) => rows.find((r) => r.source === IVA_KEY) ?? null;

/** El IVA de la factura: el monto efectivo de la fila de IVA, o 0 si no hay.
 * Delega en `effectiveTaxAmount` (P24 del plantado): con una copia propia de la
 * regla, la tarjeta podía mostrar un IVA y la reteIVA calcularse sobre otro. La
 * fila de IVA no lee el catálogo ni va sobre el IVA, así que no hay recursión. */
export function effectiveIva(rows: TaxFormRow[], lineAmounts: number[]): number {
  const iva = ivaRowOf(rows);
  if (!iva) return 0;
  return effectiveTaxAmount(iva, rows, lineAmounts, []);
}

const basedOnIva = (row: TaxFormRow, configs: RetentionRow[]): boolean =>
  row.source !== IVA_KEY && optionFor(row.source, configs)?.cfg?.base_kind === "iva";

/** La base que conoce la pantalla para ESTA fila (O1: R8 se mide por fila).
 * IVA y tarifas sobre el subtotal: el subtotal. Sobre el IVA: el IVA efectivo (R4). */
export function taxRowBase(row: TaxFormRow, rows: TaxFormRow[], lineAmounts: number[], configs: RetentionRow[]): number {
  return basedOnIva(row, configs) ? effectiveIva(rows, lineAmounts) : sumLines(lineAmounts);
}

export function suggestedTaxAmount(
  row: TaxFormRow, rows: TaxFormRow[], lineAmounts: number[], configs: RetentionRow[],
): number {
  if (!row.source) return 0;
  if (row.source === IVA_KEY) return suggestedIva(lineAmounts, row.rate);
  return pctOf(taxRowBase(row, rows, lineAmounts, configs), row.rate);
}

export function effectiveTaxAmount(
  row: TaxFormRow, rows: TaxFormRow[], lineAmounts: number[], configs: RetentionRow[],
): number {
  return row.touched ? row.amount : suggestedTaxAmount(row, rows, lineAmounts, configs);
}

/** R5: la referencia del aviso ×5 y cómo se nombra. */
export function taxRateReference(
  row: TaxFormRow, configs: RetentionRow[], ivaRatePct: number,
): { ref: number; label: string } | null {
  if (!row.source) return null;
  if (row.source === IVA_KEY) return { ref: ivaRatePct, label: "el IVA habitual" };
  const cfg = optionFor(row.source, configs)?.cfg;
  return cfg ? { ref: toNum(cfg.rate_pct), label: "la tarifa" } : null;
}

/** R7: el bloque que va al servidor. `undefined` si no hay nada: ausente = byte a byte. */
export function buildTaxPayload(
  rows: TaxFormRow[], lineAmounts: number[], _ivaRatePct: number, configs: RetentionRow[],
): DocumentTaxCreate[] | undefined {
  const out: DocumentTaxCreate[] = [];
  for (const row of rows) {
    const amount = effectiveTaxAmount(row, rows, lineAmounts, configs);
    if (!row.source || amount <= 0) continue;
    if (row.source === IVA_KEY) {
      out.push({ tax_type: "iva", rate: row.rate, base_kind: "subtotal", amount });
      continue;
    }
    const cfg = optionFor(row.source, configs)?.cfg;
    if (!cfg) continue;
    out.push({
      tax_type: cfg.retention_type as TaxType,
      municipality: cfg.retention_type === "ica" ? cfg.municipality : undefined,
      concept: cfg.concept || undefined,
      rate: row.rate,
      // El MONTO de la base lo deriva el servidor (D5 de #112); viaja sobre QUÉ
      base_kind: cfg.base_kind === "iva" ? "iva" : "subtotal",
      amount,
    });
  }
  return out.length > 0 ? out : undefined;
}

/** Delta neto sobre el cliente: el IVA suma y las retenciones restan. */
export function taxNetDelta(
  rows: TaxFormRow[], lineAmounts: number[], _ivaRatePct: number, configs: RetentionRow[],
): number {
  let net = 0;
  for (const row of rows) {
    if (!row.source) continue;
    const type: TaxType = row.source === IVA_KEY
      ? "iva"
      : ((optionFor(row.source, configs)?.cfg?.retention_type ?? "retefuente") as TaxType);
    net += TAX_SIGN_ON_CUSTOMER[type] * effectiveTaxAmount(row, rows, lineAmounts, configs);
  }
  return net;
}

/** C1 (QA 1): una fila cuyo tipo ya no tiene tarifa usable (se desactivó
 * mientras la pantalla estaba abierta y el catálogo se volvió a pedir).
 * `buildTaxPayload` la omite, así que sin este bloqueo se perdería en silencio. */
export const isOrphanTaxRow = (row: TaxFormRow, configs: RetentionRow[]): boolean =>
  !!row.source && row.source !== IVA_KEY && optionFor(row.source, configs) === null;

/** R4: el nombre de la tarifa de una fila, buscado en el catálogo COMPLETO
 * (trae también las inactivas), con su concepto; null si ya no está. */
export function taxSourceLabel(source: string, configs: RetentionRow[]): string | null {
  const cfg = configs.find((c) => c.config_id === source);
  return cfg ? configLabel(cfg, true) : null;
}

export function orphanTaxText(source: string, configs: RetentionRow[]): string {
  const label = taxSourceLabel(source, configs);
  return `${label ? `La tarifa ${label} no está activa` : "La tarifa de esta fila ya no está en el catálogo"}: `
    + "créela o reactívela en Tesorería → Retenciones, o quite la fila.";
}

/** R4b: el texto del servidor (`document_tax.py:137-145`). */
export const RETEIVA_SIN_IVA =
  "Hay una retención que se aplica sobre el IVA y esta factura no tiene IVA. Agregue el IVA o use una tarifa sobre el subtotal.";

/** Lo que bloquea Liquidar, con su texto. Vacío = válido. */
export function taxRowsProblems(
  rows: TaxFormRow[], lineAmounts: number[], configs: RetentionRow[],
): string[] {
  const out: string[] = [];
  if (rows.some((r) => !r.source)) out.push("Falta elegir el impuesto de una fila.");
  if (rows.some((r) => r.source && rateOutOfRange(r.rate))) out.push("El % de un impuesto debe estar entre 0 y 100.");
  if (rows.some((r) => r.source && effectiveTaxAmount(r, rows, lineAmounts, configs) <= 0)) {
    out.push("Hay un impuesto con monto en cero.");
  }
  // R3: una fila por (tipo, municipio), con la clave del servidor — no por tarifa
  const keys = rows.filter((r) => r.source).map((r) => serverKeyOf(r, configs));
  if (new Set(keys).size !== keys.length) out.push("Hay un impuesto repetido. Sume los montos en una sola línea.");
  if (!ivaRowOf(rows) && rows.some((r) => basedOnIva(r, configs))) out.push(RETEIVA_SIN_IVA);
  for (const r of rows) if (isOrphanTaxRow(r, configs)) out.push(orphanTaxText(r.source, configs));
  return [...new Set(out)];
}

export function taxRowsValid(
  rows: TaxFormRow[], lineAmounts: number[], _ivaRatePct: number, configs: RetentionRow[],
): boolean {
  return taxRowsProblems(rows, lineAmounts, configs).length === 0;
}
