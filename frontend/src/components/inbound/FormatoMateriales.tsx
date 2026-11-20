/**
 * La captura de la Entrada tipo compra como el formato en papel «Materiales
 * recolectados» (pedido de Johana, 19-nov; plan-sac-orden-formato-materiales.md
 * §3). Un renglon por material del formato, en su orden, con una casilla de
 * cantidad; el peso de bascula solo en materiales por unidad (#95 Q-13).
 *
 * Lo comparten la captura y la edicion. El estado es un mapa material_id ->
 * valores; las lineas que no estan en el formato siguen en «Otros materiales»,
 * que cada pagina pinta con sus lineas libres de siempre.
 */
import { StickyNote } from "lucide-react";
import { MoneyInput } from "@/components/shared/MoneyInput";
import { cn } from "@/utils";
import type { MaterialKgProfileResponse } from "@/types/sac-config";

export interface FormatoValue {
  quantity: number;
  scale_weight_kg: number;
  /** F6: el renglon no los muestra, pero una linea guardada puede traerlos y
   *  se reenvian tal cual (si no, la edicion los borraria en silencio). */
  unit_price: number;
  quality_notes: string;
}

export type FormatoValues = Record<string, FormatoValue>;

export interface FormatoSlot {
  materialId: string;
  /** El numero del renglon en el papel (con el hueco del 8 incluido). */
  position: number;
  code: string;
  name: string;
  unit: string;
  /** Material del formato que no entra por compra (Willard puro): el renglon
   *  se muestra deshabilitado para no correr el orden contra el papel. */
  disabledReason: string | null;
}

export const EMPTY_FORMATO_VALUE: FormatoValue = {
  quantity: 0,
  scale_weight_kg: 0,
  unit_price: 0,
  quality_notes: "",
};

/** Renglones del formato, en orden. F3: un material desactivado despues de
 *  ordenarlo no se muestra (recibirlo daria 422). */
export function buildFormatoSlots(
  profiles: MaterialKgProfileResponse[] | undefined
): FormatoSlot[] {
  return (profiles ?? [])
    .filter((p) => p.form_order != null && p.material_is_active !== false)
    .sort((a, b) => (a.form_order ?? 0) - (b.form_order ?? 0))
    .map((p) => ({
      materialId: p.material_id,
      position: p.form_order as number,
      code: p.material_code ?? "",
      name: p.material_name ?? p.material_code ?? "",
      unit: p.material_unit ?? "",
      disabledReason: p.compra_regular
        ? null
        : p.willard_world !== "none"
          ? "Solo entra por Willard"
          : "No está habilitado para compra",
    }));
}

/** Materiales que ocupan un renglon (habilitado o no): el selector de «Otros
 *  materiales» los excluye, porque un material en dos lugares sumaria dos
 *  lineas que la Entrada rechaza. */
export function formatoMaterialIds(slots: FormatoSlot[]): Set<string> {
  return new Set(slots.map((s) => s.materialId));
}

export interface FormatoLine {
  material_id: string;
  quantity: number;
  unit_price: number;
  scale_weight_kg: number;
  quality_notes: string;
}

/** Al guardar: solo los renglones con cantidad, en el orden del formato. */
export function formatoLines(slots: FormatoSlot[], values: FormatoValues): FormatoLine[] {
  const out: FormatoLine[] = [];
  for (const s of slots) {
    if (s.disabledReason) continue;
    const v = values[s.materialId];
    if (!v || v.quantity <= 0) continue;
    out.push({ material_id: s.materialId, ...v });
  }
  return out;
}

/** Edicion: reparte las lineas guardadas entre el formato y «Otros
 *  materiales». Solo van al formato las de un renglon HABILITADO y con
 *  cantidad; el resto queda en otros con su cantidad, para que nada
 *  desaparezca de la pantalla. C1 de QA: las lineas en 0 (truncamiento de
 *  #93 D5, que sobreviven a desliquidar) quedan en otros, visibles y
 *  bloqueando el guardado como siempre. En un renglon, `formatoLines` las
 *  descartaria y el guardado las borraria sin aviso. */
export function splitLinesForFormato<L extends FormatoLine>(
  lines: L[],
  slots: FormatoSlot[]
): { values: FormatoValues; others: L[] } {
  const enabled = new Set(slots.filter((s) => !s.disabledReason).map((s) => s.materialId));
  const values: FormatoValues = {};
  const others: L[] = [];
  for (const l of lines) {
    if (enabled.has(l.material_id) && l.quantity > 0 && !values[l.material_id]) {
      values[l.material_id] = {
        quantity: l.quantity,
        scale_weight_kg: l.scale_weight_kg,
        unit_price: l.unit_price,
        quality_notes: l.quality_notes,
      };
    } else {
      others.push(l);
    }
  }
  return { values, others };
}

interface Props {
  slots: FormatoSlot[];
  values: FormatoValues;
  onChange: (materialId: string, value: FormatoValue) => void;
}

const labelCls = "text-xs font-semibold uppercase tracking-wider text-slate-500";

export function FormatoMateriales({ slots, values, onChange }: Props) {
  const set = (materialId: string, patch: Partial<FormatoValue>) =>
    onChange(materialId, { ...(values[materialId] ?? EMPTY_FORMATO_VALUE), ...patch });

  return (
    <div>
      {/* Encabezado de columnas: solo desktop (en mobile cada casilla lleva
          su etiqueta) */}
      <div className="hidden md:grid md:grid-cols-12 gap-3 pb-2 border-b border-slate-200">
        <span className={cn(labelCls, "md:col-span-6")}>Material</span>
        <span className={cn(labelCls, "md:col-span-3")}>Cantidad</span>
        <span className={cn(labelCls, "md:col-span-3")}>Peso báscula (kg)</span>
      </div>
      {slots.map((s) => {
        const v = values[s.materialId] ?? EMPTY_FORMATO_VALUE;
        const disabled = !!s.disabledReason;
        const perUnit = !!s.unit && s.unit !== "kg";
        return (
          <div
            key={s.materialId}
            className={cn(
              "grid grid-cols-2 md:grid-cols-12 gap-x-3 gap-y-1.5 py-2 border-b border-slate-100 items-center",
              v.quantity > 0 && "bg-emerald-50/40",
              disabled && "opacity-60"
            )}
          >
            <div className="col-span-2 md:col-span-6 flex items-start gap-2 min-w-0">
              <span className="w-6 shrink-0 text-right text-xs tabular-nums text-slate-400 pt-0.5">
                {s.position}
              </span>
              <div className="min-w-0">
                <p className="text-sm font-medium text-slate-800 break-words">
                  {s.name}
                  {v.quality_notes.trim() && (
                    // F6: la nota de calidad de una linea guardada no tiene
                    // casilla en el renglon; el icono la deja a la vista
                    <span
                      title={`Nota de calidad: ${v.quality_notes}`}
                      aria-label={`Nota de calidad: ${v.quality_notes}`}
                      className="inline-flex align-middle ml-1.5"
                    >
                      <StickyNote className="h-3.5 w-3.5 text-amber-500" />
                    </span>
                  )}
                </p>
                <p className="text-xs text-slate-400">
                  {s.code}
                  {disabled && <span className="text-slate-500"> · {s.disabledReason}</span>}
                </p>
              </div>
            </div>
            <div className="md:col-span-3">
              <span className={cn(labelCls, "md:hidden")}>Cantidad</span>
              <div className="relative">
                <MoneyInput
                  value={v.quantity}
                  onChange={(q) => set(s.materialId, { quantity: q })}
                  decimals={4}
                  placeholder="0"
                  disabled={disabled}
                  className={s.unit ? "pr-16" : undefined}
                />
                {s.unit && (
                  <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs font-medium text-slate-400">
                    {s.unit}
                  </span>
                )}
              </div>
            </div>
            <div className="md:col-span-3">
              {perUnit && !disabled && (
                <>
                  <span className={cn(labelCls, "md:hidden")}>Peso báscula (kg)</span>
                  <MoneyInput
                    value={v.scale_weight_kg}
                    onChange={(w) => set(s.materialId, { scale_weight_kg: w })}
                    decimals={2}
                    placeholder="0,00"
                  />
                  {/* #95 Q-13: opcional al capturar, obligatorio al revisar */}
                  {v.quantity > 0 && v.scale_weight_kg <= 0 && (
                    <p className="text-xs text-amber-600 mt-0.5">Sin este peso no se puede revisar</p>
                  )}
                </>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
