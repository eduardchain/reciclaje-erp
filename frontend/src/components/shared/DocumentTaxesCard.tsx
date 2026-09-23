/**
 * Captura de IVA y retenciones sobre lo que SAC factura (CC-013 / Q-41).
 *
 * UNA sola implementacion para las DOS vias — la venta normal y la Salida de
 * Plomo — porque son la misma factura vista desde dos modulos. Dos copias se
 * desincronizan, y acá lo que se desincronizaria son los signos y las bases.
 *
 * D1: el sistema REGISTRA lo que Siigo emitio. Los montos se precalculan para
 * no tipear, pero son editables y el valor editado es la verdad (#79 F1).
 *
 * D5: cada tipo dice sobre QUE se aplica. La reteIVA va sobre el IVA y las
 * demas sobre el subtotal. Guardar una reteIVA como "2,85 % del subtotal" da
 * el numero correcto SOLO mientras el IVA sea 19 %.
 *
 * ⚠️ El MONTO de la base lo deriva el SERVIDOR de lo que realmente facturo; lo
 * que se calcula acá es la SUGERENCIA. Con `subtotal = 0` —una Salida tipo
 * abono, donde la maquila y el flete salen de las tarifas vigentes al
 * liquidar— la sugerencia es 0 y el usuario digita lo que dice la factura. Eso
 * es correcto y no es un hueco: el sistema registra, no emite.
 */
import { useMemo } from "react";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { FormLineGrid } from "@/components/shared/FormLineGrid";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { cn } from "@/utils";
import { formatCurrency } from "@/utils/formatters";
import type { DocumentTaxCreate, TaxType } from "@/types/document-tax";
import { TAX_SIGN_ON_CUSTOMER, TAX_TYPE_LABELS } from "@/types/document-tax";
import type { RetentionRow } from "@/types/third-party";

export interface TaxFormRow {
  _key: number;
  /** `iva`, o el `config_id` de una tarifa del catalogo. */
  source: string;
  amount: number;
  touched: boolean;
}

let taxKeySeq = 0;
export const createEmptyTax = (): TaxFormRow => ({
  _key: ++taxKeySeq, source: "", amount: 0, touched: false,
});

const IVA_SOURCE = "__iva__";

interface Props {
  /**
   * Monto facturado de cada linea. D6: el IVA se redondea POR LINEA y se suma,
   * que es lo que hace Siigo — sobre el total daria un centavo distinto y el
   * usuario tendria que corregirlo a mano todos los dias.
   */
  lineAmounts: number[];
  ivaRatePct: number;
  /** Catalogo de tarifas activas (reusa `retention_configs`, #79). */
  configs: RetentionRow[];
  rows: TaxFormRow[];
  onChange: (rows: TaxFormRow[]) => void;
  /** Texto que explica sobre que se factura — difiere entre venta y abono. */
  baseHint: string;
}

/** Fila de catalogo, legible: "ReteFuente · Venta de bienes (2,5%)". */
function configLabel(cfg: RetentionRow): string {
  const parts = [TAX_TYPE_LABELS[cfg.retention_type as TaxType] ?? cfg.retention_type];
  if (cfg.municipality) parts.push(cfg.municipality);
  if (cfg.concept) parts.push(cfg.concept);
  return parts.join(" · ");
}

export const sumLines = (lineAmounts: number[]): number =>
  lineAmounts.reduce((a, b) => a + b, 0);

/**
 * IVA sugerido: se redondea CADA LINEA y se suman (D6), que es lo que hace
 * Siigo. Sobre el total el resultado difiere en centavos y, con el sistema
 * REGISTRANDO lo que la factura dice, esa diferencia la tendria que corregir
 * el usuario a mano en cada venta.
 */
export function suggestedIva(lineAmounts: number[], ivaRatePct: number): number {
  return lineAmounts.reduce(
    (sum, amount) => sum + Math.round(amount * ivaRatePct) / 100,
    0,
  );
}

/**
 * Monto sugerido de una fila. El IVA sale de las lineas; una retencion sale de
 * su base declarada (`base_kind`), que es toda la razon de ser de D5.
 */
export function suggestedTaxAmount(
  row: TaxFormRow, lineAmounts: number[], ivaRatePct: number, configs: RetentionRow[],
): number {
  if (row.source === IVA_SOURCE) return suggestedIva(lineAmounts, ivaRatePct);
  const cfg = configs.find((c) => c.config_id === row.source);
  if (!cfg || cfg.rate_pct == null) return 0;
  const base = cfg.base_kind === "iva"
    ? suggestedIva(lineAmounts, ivaRatePct)
    : sumLines(lineAmounts);
  return Math.round(base * cfg.rate_pct) / 100;
}

export function effectiveTaxAmount(
  row: TaxFormRow, lineAmounts: number[], ivaRatePct: number, configs: RetentionRow[],
): number {
  return row.touched
    ? row.amount
    : suggestedTaxAmount(row, lineAmounts, ivaRatePct, configs);
}

/** Payload del backend. Devuelve `undefined` si no hay nada: ausente = byte a byte. */
export function buildTaxPayload(
  rows: TaxFormRow[], lineAmounts: number[], ivaRatePct: number, configs: RetentionRow[],
): DocumentTaxCreate[] | undefined {
  const out: DocumentTaxCreate[] = [];
  for (const row of rows) {
    const amount = effectiveTaxAmount(row, lineAmounts, ivaRatePct, configs);
    if (!row.source || amount <= 0) continue;
    if (row.source === IVA_SOURCE) {
      out.push({ tax_type: "iva", rate: ivaRatePct, base_kind: "subtotal", amount });
      continue;
    }
    const cfg = configs.find((c) => c.config_id === row.source);
    if (!cfg) continue;
    out.push({
      tax_type: cfg.retention_type as TaxType,
      ...(cfg.retention_type === "ica" && cfg.municipality
        ? { municipality: cfg.municipality }
        : {}),
      ...(cfg.concept ? { concept: cfg.concept } : {}),
      rate: cfg.rate_pct ?? undefined,
      // El MONTO de la base lo deriva el servidor (D5). Acá solo viaja sobre
      // QUE se aplica: en un abono la pantalla no conoce la base.
      base_kind: cfg.base_kind === "iva" ? "iva" : "subtotal",
      amount,
    });
  }
  return out.length > 0 ? out : undefined;
}

/** Delta neto sobre el cliente: el IVA suma y las retenciones restan. */
export function taxNetDelta(
  rows: TaxFormRow[], lineAmounts: number[], ivaRatePct: number, configs: RetentionRow[],
): number {
  let net = 0;
  for (const row of rows) {
    if (!row.source) continue;
    const amount = effectiveTaxAmount(row, lineAmounts, ivaRatePct, configs);
    const type: TaxType = row.source === IVA_SOURCE
      ? "iva"
      : ((configs.find((c) => c.config_id === row.source)?.retention_type ?? "retefuente") as TaxType);
    net += TAX_SIGN_ON_CUSTOMER[type] * amount;
  }
  return net;
}

/** Una fila sin tarifa elegida, o en cero, bloquea. */
export function taxRowsValid(
  rows: TaxFormRow[], lineAmounts: number[], ivaRatePct: number, configs: RetentionRow[],
): boolean {
  if (rows.some((r) => !r.source)) return false;
  if (rows.some((r) => effectiveTaxAmount(r, lineAmounts, ivaRatePct, configs) <= 0)) return false;
  // Duplicados: dos IVA sobre la misma factura es captura repetida, y el
  // servidor la rechaza. Avisar acá evita el 422 despues de llenar todo.
  const sources = rows.map((r) => r.source).filter(Boolean);
  return new Set(sources).size === sources.length;
}

export function DocumentTaxesCard({
  lineAmounts, ivaRatePct, configs, rows, onChange, baseHint,
}: Props) {
  const subtotal = sumLines(lineAmounts);
  const activeConfigs = useMemo(
    () => configs.filter((c) => c.config_id && c.is_active),
    [configs],
  );
  const used = new Set(rows.map((r) => r.source));

  const setRow = (key: number, patch: Partial<TaxFormRow>) =>
    onChange(rows.map((r) => (r._key === key ? { ...r, ...patch } : r)));

  const net = taxNetDelta(rows, lineAmounts, ivaRatePct, configs);
  const duplicated = (() => {
    const s = rows.map((r) => r.source).filter(Boolean);
    return new Set(s).size !== s.length;
  })();

  return (
    <Card className="shadow-sm">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">
          IVA y Retenciones (Opcional)
        </CardTitle>
        <Button
          variant="outline" size="sm"
          onClick={() => onChange([...rows, createEmptyTax()])}
          className="w-full sm:w-auto"
        >
          <Plus className="h-4 w-4 mr-1" />Agregar
        </Button>
      </CardHeader>
      {rows.length > 0 && (
        <CardContent className="space-y-0">
          {rows.map((row, idx) => {
            const amount = effectiveTaxAmount(row, lineAmounts, ivaRatePct, configs);
            const suggested = suggestedTaxAmount(row, lineAmounts, ivaRatePct, configs);
            const cfg = configs.find((c) => c.config_id === row.source);
            const ratePct = row.source === IVA_SOURCE ? ivaRatePct : cfg?.rate_pct;
            const baseAmount = row.source === IVA_SOURCE
              ? subtotal
              : cfg?.base_kind === "iva"
                ? suggestedIva(lineAmounts, ivaRatePct)
                : subtotal;
            return (
              <FormLineGrid
                key={row._key}
                isFirst={idx === 0}
                isLast={idx === rows.length - 1}
                onDelete={() => onChange(rows.filter((r) => r._key !== row._key))}
              >
                <div className="md:col-span-6">
                  <Label className={cn(
                    "text-xs font-semibold uppercase tracking-wider text-slate-500",
                    idx > 0 && "sr-only md:not-sr-only",
                  )}>
                    Impuesto *
                  </Label>
                  <Select
                    value={row.source || undefined}
                    onValueChange={(v) => setRow(row._key, { source: v, touched: false })}
                  >
                    <SelectTrigger className={!row.source ? "border-red-300" : ""}>
                      <SelectValue placeholder="Seleccionar impuesto..." />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem
                        value={IVA_SOURCE}
                        disabled={used.has(IVA_SOURCE) && row.source !== IVA_SOURCE}
                      >
                        IVA ({ivaRatePct}%)
                      </SelectItem>
                      {activeConfigs.map((c) => (
                        <SelectItem
                          key={c.config_id}
                          value={c.config_id as string}
                          disabled={used.has(c.config_id as string) && row.source !== c.config_id}
                        >
                          {configLabel(c)} ({c.rate_pct}%)
                          {c.base_kind === "iva" ? " sobre IVA" : ""}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="md:col-span-4">
                  <Label className={cn(
                    "text-xs font-semibold uppercase tracking-wider text-slate-500",
                    idx > 0 && "sr-only md:not-sr-only",
                  )}>
                    Monto *
                  </Label>
                  <MoneyInput
                    value={amount}
                    onChange={(v) => setRow(row._key, { amount: v, touched: true })}
                    decimals={2}
                    placeholder="0"
                    className={amount <= 0 ? "border-red-300" : ""}
                  />
                  {row.source && row.touched && amount !== suggested && suggested > 0 && (
                    <button
                      type="button"
                      className="text-xs text-indigo-600 hover:underline mt-0.5"
                      onClick={() => setRow(row._key, { touched: false })}
                    >
                      Sugerido: {formatCurrency(suggested)} ({ratePct}%)
                    </button>
                  )}
                  {row.source && !row.touched && (
                    <p className="text-xs text-slate-400 mt-0.5">
                      {ratePct}% de {formatCurrency(baseAmount)} — editable
                    </p>
                  )}
                </div>
              </FormLineGrid>
            );
          })}
          <div className="bg-slate-50 rounded-lg p-3 mt-2 text-xs text-slate-500 space-y-1">
            <p>{baseHint}</p>
            <p>
              El cliente queda debiendo el <strong>total a pagar</strong> de la factura:
              el IVA se le suma y las retenciones se le restan. Cada impuesto crea su
              contrapartida con la entidad <strong>[Impuestos]</strong>.
            </p>
            {rows.length > 0 && (
              <p className="text-slate-600 font-medium">
                Efecto neto sobre el cliente: {net >= 0 ? "+" : "−"}
                {formatCurrency(Math.abs(net))} → total a pagar {formatCurrency(subtotal + net)}
              </p>
            )}
            {duplicated && (
              <p className="text-red-500 font-medium">
                Hay un impuesto repetido. Sume los montos en una sola linea.
              </p>
            )}
            {subtotal + net <= 0 && rows.length > 0 && (
              <p className="text-red-500 font-medium">
                Las retenciones no pueden igualar ni superar el total facturado.
              </p>
            )}
          </div>
        </CardContent>
      )}
    </Card>
  );
}
