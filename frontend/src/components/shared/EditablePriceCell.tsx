import { useState, useRef, useEffect, useCallback } from "react";
import { Loader2, CheckCircle2 } from "lucide-react";
import { formatCurrency } from "@/utils/formatters";
import type { PriceTableItem } from "@/types/config";

export type PriceCellField = "purchase_price" | "sale_price";

/** Clave de celda compartida por las dos hojas de precios. */
export const priceCellKey = (materialId: string, field: PriceCellField) => `${materialId}-${field}`;

interface Props {
  item: PriceTableItem;
  field: PriceCellField;
  canEdit: boolean;
  isEditing: boolean;
  onStartEdit: () => void;
  onSave: (value: number) => void;
  onCancel: () => void;
  /**
   * Tab / Shift+Tab: guarda y salta a la celda siguiente/anterior de la hoja.
   * El padre es quien conoce el orden (filas visibles x columnas editables).
   */
  onNavigate?: (direction: 1 | -1) => void;
  savingCell: string | null;
  savedCell: string | null;
  /**
   * Hoja por proveedor (#98 D1/D3): un precio en 0 NO es "vale cero pesos", es
   * "a este proveedor no se le sugiere nada para este material" — la aspereza
   * que Daniel decidio dejar asi. La hoja general no lo trata como especial:
   * ahi un 0 es un precio de $0. Esta prop es esa divergencia, deliberada.
   */
  zeroMeansUnset?: boolean;
}

/**
 * Celda editable de las hojas de precios (modo tabla #35 y listas por proveedor #98).
 * Vive en shared porque el comportamiento de teclado debe ser identico en ambas:
 * cada hoja tenia su propia copia y ya habian divergido.
 */
export function EditablePriceCell({
  item,
  field,
  canEdit,
  isEditing,
  onStartEdit,
  onSave,
  onCancel,
  onNavigate,
  savingCell,
  savedCell,
  zeroMeansUnset = false,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [editValue, setEditValue] = useState("");
  // El commit puede dispararse por Enter/Tab y DESPUES por el blur que provoca
  // desmontar el input. Sin este guard, Tab guardaria dos veces (la segunda
  // comparando contra un currentValue que la mutation aun no actualizo).
  const committedRef = useRef(false);
  const cellKey = priceCellKey(item.material_id, field);
  const isSaving = savingCell === cellKey;
  const isSaved = savedCell === cellKey;
  const currentValue = item[field];

  useEffect(() => {
    if (isEditing) {
      committedRef.current = false;
      setEditValue(currentValue != null ? String(currentValue) : "");
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [isEditing, currentValue]);

  const commit = useCallback(() => {
    if (committedRef.current) return;
    committedRef.current = true;
    const parsed = parseFloat(editValue) || 0;
    const final = Math.max(0, parsed);
    if (final !== (currentValue ?? 0)) {
      onSave(final);
    } else {
      onCancel();
    }
  }, [editValue, currentValue, onSave, onCancel]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        commit();
      } else if (e.key === "Escape") {
        e.preventDefault();
        committedRef.current = true; // el blur posterior no debe guardar
        onCancel();
      } else if (e.key === "Tab") {
        // preventDefault: el foco lo mueve el padre abriendo la celda destino,
        // no el orden natural del DOM (el input actual se desmonta al guardar).
        e.preventDefault();
        commit();
        onNavigate?.(e.shiftKey ? -1 : 1);
      }
    },
    [commit, onCancel, onNavigate],
  );

  if (isEditing) {
    return (
      <input
        ref={inputRef}
        type="text"
        inputMode="numeric"
        value={editValue}
        onChange={(e) => {
          if (e.target.value === "" || /^\d*\.?\d*$/.test(e.target.value)) {
            setEditValue(e.target.value);
          }
        }}
        onBlur={commit}
        onKeyDown={handleKeyDown}
        className="w-full h-8 px-2 text-right text-sm border border-emerald-400 rounded bg-white focus:outline-none focus:ring-2 focus:ring-emerald-300"
      />
    );
  }

  const isUnset = currentValue == null || (zeroMeansUnset && currentValue === 0);
  const unsetLabel = zeroMeansUnset ? "Sin precio" : "$0";

  return (
    <div
      className={`flex items-center justify-end gap-1 h-8 px-2 rounded text-sm tabular-nums ${canEdit ? "cursor-pointer hover:bg-emerald-50" : ""} ${isUnset ? "text-slate-400 italic" : ""}`}
      onClick={canEdit ? onStartEdit : undefined}
      title={isUnset && zeroMeansUnset ? "Sin precio: a este proveedor no se le sugiere nada para este material" : undefined}
    >
      {isSaving && <Loader2 className="w-3 h-3 animate-spin text-emerald-600" />}
      {isSaved && <CheckCircle2 className="w-3 h-3 text-emerald-500" />}
      <span>{isUnset ? unsetLabel : formatCurrency(currentValue)}</span>
    </div>
  );
}
