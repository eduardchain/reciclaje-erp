/**
 * Orden del formato en papel «Materiales recolectados» (pedido de Johana,
 * 19-nov; plan-sac-orden-formato-materiales.md §3).
 *
 * Una sola fuente para las cuatro pantallas de la Entrada, las cards del
 * reparto y el PDF de la compra: primero los materiales del formato en su
 * renglon; despues los que no estan, alfabeticos por nombre (la regla de
 * 0862891, que pasa a ser solo el desempate).
 */
import type { MaterialKgProfileResponse } from "@/types/sac-config";

/** material_id -> renglon del formato. Vacio si no hay perfiles. */
export function formOrderMap(
  profiles: MaterialKgProfileResponse[] | undefined
): Map<string, number> {
  const map = new Map<string, number>();
  for (const p of profiles ?? []) {
    if (p.form_order != null) map.set(p.material_id, p.form_order);
  }
  return map;
}

const byName = (a: string, b: string) =>
  a.localeCompare(b, "es", { numeric: true, sensitivity: "base" });

/** Devuelve una COPIA ordenada (las listas suelen venir del cache de React
 *  Query, que no se debe mutar). */
export function sortByFormOrder<
  T extends { material_id: string; material_name?: string | null; material_code?: string | null }
>(lines: T[], order: Map<string, number>): T[] {
  return [...lines].sort((x, y) => {
    const ox = order.get(x.material_id);
    const oy = order.get(y.material_id);
    if (ox != null && oy != null) return ox - oy;
    if (ox != null) return -1;
    if (oy != null) return 1;
    return byName(
      x.material_name ?? x.material_code ?? "",
      y.material_name ?? y.material_code ?? ""
    );
  });
}

/** F4 del plan: el PDF de la compra tiene DOS llamadores (detalle y menú de
 *  fila del listado) y los dos pasan por aca. `purchase_lines` se ordena por
 *  `created_at` y las N compras de una Entrada nacen en UNA transaccion, asi
 *  que su orden no esta definido. Solo actua si la compra viene de una
 *  Entrada y la org es SAC; si no, devuelve la MISMA compra (Costa y Meta
 *  quedan byte a byte). */
export function orderPurchaseLinesForPdf<
  P extends {
    inbound_order_id?: string | null;
    lines: { material_id: string; material_name?: string | null; material_code?: string | null }[];
  }
>(purchase: P, order: Map<string, number>, sacEnabled: boolean): P {
  if (!sacEnabled || !purchase.inbound_order_id || order.size === 0) return purchase;
  return { ...purchase, lines: sortByFormOrder(purchase.lines, order) };
}
