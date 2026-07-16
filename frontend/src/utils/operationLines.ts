import { formatWeight } from "@/utils/formatters";

/**
 * Helpers compartidos para las lineas de operaciones (compras / ventas / DPs).
 *
 * En ventas el total usa `quantity` (la cantidad original despachada), NUNCA
 * `received_quantity`: la diferencia de bascula es solo financiera y el
 * inventario no se ajusta (decision #18).
 */
interface QuantityLine {
  quantity: number;
  material_unit?: string | null;
}

// Backend puede serializar Decimal como string ("100.0000") — coercion
// defensiva para que la suma no concatene strings.
const toNum = (v: unknown): number => {
  if (typeof v === "number") return v;
  if (typeof v === "string" && v.trim() !== "" && !Number.isNaN(Number(v))) return Number(v);
  return 0;
};

/** Suma de `lines[].quantity` como numero (para columnas Excel sumables). */
export function totalLinesQuantity(lines: QuantityLine[]): number {
  return lines.reduce((sum, l) => sum + toNum(l.quantity), 0);
}

/**
 * Unidad compartida por TODAS las lineas (fallback "kg" si viene vacia,
 * decision #54), o null si hay unidades mixtas.
 */
export function sharedLinesUnit(lines: QuantityLine[]): string | null {
  if (lines.length === 0) return null;
  const first = lines[0].material_unit || "kg";
  return lines.every((l) => (l.material_unit || "kg") === first) ? first : null;
}

/**
 * Total formateado: "1.500 kg" si todas las lineas comparten unidad;
 * solo el numero ("1.500") si hay unidades mixtas — un sufijo seria ambiguo.
 */
export function formatLinesTotalQuantity(lines: QuantityLine[]): string {
  const total = totalLinesQuantity(lines);
  const unit = sharedLinesUnit(lines);
  return unit ? formatWeight(total, unit) : formatWeight(total, "").trim();
}
