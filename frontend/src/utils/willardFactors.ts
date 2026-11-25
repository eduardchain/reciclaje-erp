/**
 * Factores de Willard (plan-sac-factor-willard.md v1.3).
 *
 * La lista vive DENTRO de la fórmula `drosses_to_lead` vigente (D1):
 * `lead_percentage` es SIEMPRE el factor por defecto (lo único que leen
 * traslados, Salidas, crisol y los kg estimados), `label` le pone nombre y
 * `alternatives` lista los otros factores que se escogen al liquidar una
 * Entrada de Willard. Sin `alternatives` la fórmula es la de siempre.
 */
import type { MaterialConversionFormulaResponse } from "@/types/sac-config";

export interface LeadAlternative {
  label: string;
  lead_percentage: number;
}

export interface FactorOption {
  /** null = el defecto (lo que se manda y se guarda como null, A2) */
  value: string | null;
  label: string;
  /** fracción 0–1 */
  pct: number;
}

/** Valor de Select para el defecto (los Select de shadcn no aceptan null). */
export const DEFAULT_FACTOR = "__default__";

const num = (v: unknown): number => (typeof v === "number" ? v : Number(v ?? 0));

export function readFactors(parameters: Record<string, unknown> | undefined | null): {
  label: string | null;
  alternatives: LeadAlternative[];
} {
  const p = parameters ?? {};
  const alts = Array.isArray(p.alternatives) ? (p.alternatives as Record<string, unknown>[]) : [];
  return {
    label: typeof p.label === "string" ? p.label : null,
    alternatives: alts.map((a) => ({ label: String(a.label ?? ""), lead_percentage: num(a.lead_percentage) })),
  };
}

/** Opciones de factor de un material; [] si su fórmula no tiene alternativas. */
export function factorOptions(formula: MaterialConversionFormulaResponse | undefined): FactorOption[] {
  if (!formula || formula.formula_type !== "drosses_to_lead") return [];
  const { label, alternatives } = readFactors(formula.parameters);
  if (alternatives.length === 0) return [];
  return [
    { value: null, label: label ?? "Por defecto", pct: num(formula.parameters.lead_percentage) },
    ...alternatives.map((a) => ({ value: a.label, label: a.label, pct: a.lead_percentage })),
  ];
}

/** 0.56 → "56 %", 0.565 → "56,5 %". */
export function pctText(fraction: number): string {
  const pct = Math.round(fraction * 100 * 10000) / 10000;
  return `${String(pct).replace(".", ",")} %`;
}

/** Mismo criterio que el servidor (normalize_entity_name): sin tildes ni mayúsculas. */
export function normalizeFactorName(name: string): string {
  return name.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
}

export interface AlternativeDraft {
  label: string;
  /** porcentaje 0–100 como texto del input */
  pct: string;
}

/**
 * Valida la lista que se edita en Configuración (espejo de D1 del servidor).
 * Devuelve el problema en texto o null si está bien. `defaultPct` en 0–100.
 */
export function factorListProblem(
  defaultLabel: string,
  defaultPct: number,
  alternatives: AlternativeDraft[],
): string | null {
  if (alternatives.length === 0) return null;
  if (alternatives.length > 5) return "Máximo 5 factores alternativos.";
  if (!defaultLabel.trim()) return "Ponle nombre al factor por defecto.";
  if (defaultLabel.trim().length > 40) return "El nombre del factor por defecto pasa de 40 caracteres.";
  const names = new Set([normalizeFactorName(defaultLabel)]);
  const pcts = new Set([defaultPct]);
  for (const a of alternatives) {
    if (!a.label.trim()) return "Cada factor alternativo necesita nombre.";
    if (a.label.trim().length > 40) return `El nombre «${a.label.trim()}» pasa de 40 caracteres.`;
    const pct = parseFloat(a.pct);
    if (!pct || pct <= 0 || pct > 100) return `El porcentaje de «${a.label.trim()}» tiene que estar entre 0 y 100.`;
    const n = normalizeFactorName(a.label);
    if (names.has(n)) return `El nombre «${a.label.trim()}» está repetido.`;
    names.add(n);
    if (pcts.has(pct)) return `«${a.label.trim()}» tiene el mismo porcentaje que otro factor.`;
    pcts.add(pct);
  }
  return null;
}
