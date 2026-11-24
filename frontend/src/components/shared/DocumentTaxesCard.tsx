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
 * % libre (plan-sac-impuestos-ventas-libres v1.1): el selector elige el TIPO de
 * impuesto, cada fila tiene su % editable al lado del monto y gana el último
 * que se tocó. Las reglas viven, puras, en `utils/documentTaxRows.ts`.
 *
 * ⚠️ El MONTO de la base lo deriva el SERVIDOR de lo que realmente facturo; lo
 * que se calcula acá es la SUGERENCIA. Con `subtotal = 0` —una Salida tipo
 * abono, donde la maquila y el flete salen de las tarifas vigentes al
 * liquidar— la sugerencia es 0 y el usuario digita lo que dice la factura (R8).
 */
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { FormLineGrid, lineLabelClass } from "@/components/shared/FormLineGrid";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { cn } from "@/utils";
import { formatCurrency } from "@/utils/formatters";
import type { RetentionRow } from "@/types/third-party";
import { rateOutOfRange, rateWarning, rateWarningText } from "@/utils/taxRows";
import {
  IVA_KEY, createEmptyTax, effectiveTaxAmount, isOrphanTaxRow, optionFor, selectTaxType,
  suggestedTaxAmount, sumLines, taxNetDelta, taxRateReference, taxRowBase,
  taxRowsProblems, taxTypeOptions, withTaxAmount, withTaxRate,
} from "@/utils/documentTaxRows";
import type { TaxFormRow } from "@/utils/documentTaxRows";

// Los dos llamadores importan de acá: su interfaz no cambia.
export type { TaxFormRow } from "@/utils/documentTaxRows";
export {
  buildTaxPayload, createEmptyTax, taxNetDelta, taxRowsValid,
} from "@/utils/documentTaxRows";

interface Props {
  /**
   * Monto facturado de cada linea. D6: el IVA se redondea POR LINEA y se suma,
   * que es lo que hace Siigo — sobre el total daria un centavo distinto y el
   * usuario tendria que corregirlo a mano todos los dias.
   */
  lineAmounts: number[];
  /** El IVA habitual de la org: el % con que arranca la fila de IVA (R1). */
  ivaRatePct: number;
  /** Catalogo de tarifas (reusa `retention_configs`, #79). */
  configs: RetentionRow[];
  rows: TaxFormRow[];
  onChange: (rows: TaxFormRow[]) => void;
  /** Texto que explica sobre que se factura — difiere entre venta y abono. */
  baseHint: string;
}

const fmtRate = (v: number): string =>
  new Intl.NumberFormat("es-CO", { maximumFractionDigits: 4 }).format(v);

export function DocumentTaxesCard({
  lineAmounts, ivaRatePct, configs, rows, onChange, baseHint,
}: Props) {
  const subtotal = sumLines(lineAmounts);
  const options = taxTypeOptions(configs);
  const used = new Set(rows.map((r) => r.source));

  const setRow = (key: number, fn: (r: TaxFormRow) => TaxFormRow) =>
    onChange(rows.map((r) => (r._key === key ? fn(r) : r)));

  const net = taxNetDelta(rows, lineAmounts, ivaRatePct, configs);
  const problems = taxRowsProblems(rows, lineAmounts, configs);

  return (
    <Card className="shadow-sm">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">
          IVA y Retenciones (Opcional)
        </CardTitle>
        <Button
          variant="outline" size="sm"
          // A1 (Daniel): la fila nueva arranca vacía, como hoy
          onClick={() => onChange([...rows, createEmptyTax()])}
          className="w-full sm:w-auto"
        >
          <Plus className="h-4 w-4 mr-1" />Agregar
        </Button>
      </CardHeader>
      {rows.length > 0 && (
        <CardContent className="space-y-0">
          {rows.map((row, idx) => {
            const amount = effectiveTaxAmount(row, rows, lineAmounts, configs);
            const suggested = suggestedTaxAmount(row, rows, lineAmounts, configs);
            const base = taxRowBase(row, rows, lineAmounts, configs);
            const onIva = row.source !== IVA_KEY
              && optionFor(row.source, configs)?.cfg?.base_kind === "iva";
            const ref = taxRateReference(row, configs, ivaRatePct);
            // El patrón del repo: rótulos en todas las filas en móvil, solo en la
            // primera en escritorio (estilo tabla).
            const labelCls = cn(
              "text-xs font-semibold uppercase tracking-wider text-slate-500",
              lineLabelClass(idx),
            );
            return (
              <FormLineGrid
                key={row._key}
                isFirst={idx === 0}
                isLast={idx === rows.length - 1}
                onDelete={() => onChange(rows.filter((r) => r._key !== row._key))}
                // arriba: la pista bajo el monto no desalinea las casillas
                className="md:items-start"
              >
                {/* en móvil, espacio para la papelera absoluta de FormLineGrid */}
                <div className="pr-10 md:pr-0 md:col-span-6">
                  <Label className={labelCls}>Impuesto *</Label>
                  <Select
                    value={row.source || undefined}
                    onValueChange={(v) => setRow(row._key, (r) => selectTaxType(r, v, configs, ivaRatePct))}
                  >
                    <SelectTrigger className={!row.source || isOrphanTaxRow(row, configs) ? "border-red-300" : ""}>
                      <SelectValue placeholder="Seleccionar impuesto..." />
                    </SelectTrigger>
                    <SelectContent>
                      {options.map((o) => (
                        <SelectItem
                          key={o.key}
                          value={o.key}
                          // R6: una fila por (tipo, municipio), la clave del servidor
                          disabled={used.has(o.key) && row.source !== o.key}
                        >
                          {o.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="md:col-span-2">
                  <Label className={labelCls}>{onIva ? "% del IVA" : "% del subtotal"}</Label>
                  <div className="relative" data-field="tax-rate">
                    <MoneyInput
                      value={row.rate}
                      onChange={(v) => setRow(row._key, (r) => withTaxRate(r, v, base))}
                      decimals={4}
                      // R2: el monto se recalcula mientras se escribe el %
                      liveChange
                      disabled={!row.source}
                      className={cn("pr-6", row.source && rateOutOfRange(row.rate) && "border-red-300")}
                    />
                    <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-xs text-slate-400">
                      %
                    </span>
                  </div>
                </div>
                <div className="md:col-span-3" data-field="tax-amount">
                  <Label className={labelCls}>Monto *</Label>
                  <MoneyInput
                    value={amount}
                    // un blur sin cambio no cuenta como tocar el monto
                    onChange={(v) => v !== amount && setRow(row._key, (r) => withTaxAmount(r, v))}
                    decimals={2}
                    placeholder="0"
                    className={amount <= 0 ? "border-red-300" : ""}
                  />
                  {/* R9: la pista y el texto usan el % de la fila */}
                  {row.source && row.touched && amount !== suggested && suggested > 0 && (
                    <button
                      type="button"
                      className="text-xs text-indigo-600 hover:underline mt-0.5"
                      onClick={() => setRow(row._key, (r) => ({ ...r, touched: false }))}
                    >
                      Sugerido: {formatCurrency(suggested)} ({fmtRate(row.rate)}%)
                    </button>
                  )}
                  {row.source && !row.touched && (
                    <p className="text-xs text-slate-400 mt-0.5">
                      {fmtRate(row.rate)}% de {formatCurrency(base)} — editable
                    </p>
                  )}
                  {/* R5: aviso ×5, no bloquea */}
                  {ref && rateWarning(row.rate, ref.ref) && (
                    <p className="text-xs text-amber-700 mt-0.5" data-testid="tax-rate-warning">
                      {rateWarningText(row.rate, ref.ref, ref.label)}
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
            <p className="text-slate-600 font-medium">
              Efecto neto sobre el cliente: {net >= 0 ? "+" : "−"}
              {formatCurrency(Math.abs(net))} → total a pagar {formatCurrency(subtotal + net)}
            </p>
            {problems.map((p) => (
              <p key={p} className="text-red-500 font-medium" data-testid="tax-problem">{p}</p>
            ))}
            {subtotal + net <= 0 && (
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
