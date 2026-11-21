// Compras de una Entrada (#93, reparto por compra #122): la plata de cada una
// y el criterio de cuáles suman. UNA sola definición para el detalle (tabla,
// tarjetas, fila de totales, «Total Liquidado», «Total con IVA») y para el
// listado («Total $») — plan-sac-compras-entrada-tabla.md v1.2, D2/D4/D7.
import type {
  InboundOrderLineResponse,
  InboundPurchaseSummary,
} from "@/types/inbound-order";
import { num } from "@/types/willard-delivery";

export interface PurchaseMoney {
  subtotal: number;
  /** IVA VIVO: filas `iva` sin `reverted_at`. La API puede traer filas
   *  revertidas (precarga al reliquidar); esas no cuentan. */
  iva: number;
  /** Retenciones vivas (`retentions_total` ya viene filtrado por el servidor) */
  ret: number;
  /** Lo que queda acreditado al proveedor: subtotal + IVA − retenciones */
  total: number;
}

export function purchaseMoney(p: InboundPurchaseSummary): PurchaseMoney {
  const subtotal = num(p.total_amount);
  const iva = (p.taxes ?? [])
    .filter((t) => t.tax_type === "iva" && !t.reverted_at)
    .reduce((acc, t) => acc + num(t.amount), 0);
  const ret = num(p.retentions_total);
  return { subtotal, iva, ret, total: subtotal + iva - ret };
}

/** O1 de Daniel (20-nov): suma una compra si y solo si está LIQUIDADA. Una
 *  desliquidada (`registered`) deja de sumar hasta que se vuelva a liquidar;
 *  una cancelada nunca suma.
 *
 *  ⚠️ Es un criterio de PLATA. Los `status !== "cancelled"` que cuentan
 *  compras vivas por otra razón NO se unifican con este: el «Varios (N)» del
 *  listado, el conteo del diálogo de anular, la precarga de la liquidación y,
 *  sobre todo, `hasLivePurchases` de InboundEditPage (guard de sede de #118:
 *  una compra `registered` sí bloquea cambiar la sede, porque reliquidar la
 *  reusaría con sus líneas en la sede vieja). */
export function countsAsLiquidated(p: InboundPurchaseSummary): boolean {
  return p.status === "liquidated";
}

export interface PurchaseTotals extends PurchaseMoney {
  count: number;
}

/** Suma de las compras que cuentan (O1). */
export function liquidatedTotals(purchases: InboundPurchaseSummary[]): PurchaseTotals {
  return purchases.filter(countsAsLiquidated).reduce<PurchaseTotals>(
    (acc, p) => {
      const m = purchaseMoney(p);
      return {
        count: acc.count + 1,
        subtotal: acc.subtotal + m.subtotal,
        iva: acc.iva + m.iva,
        ret: acc.ret + m.ret,
        total: acc.total + m.total,
      };
    },
    { count: 0, subtotal: 0, iva: 0, ret: 0, total: 0 }
  );
}

export interface PurchaseMaterial {
  code: string;
  quantity: number;
  unit: string;
}

/** Materiales de una compra, desde el reparto: las asignaciones de su slot
 *  (D3). Una cancelada devuelve [] — su slot puede tenerlo hoy una compra
 *  nueva (R5/R6 de #122) y le asignaría materiales que no son suyos. Sin
 *  slot (legacy) también []. */
export function purchaseMaterials(
  p: InboundPurchaseSummary,
  lines: InboundOrderLineResponse[]
): PurchaseMaterial[] {
  if (p.status === "cancelled" || p.purchase_slot == null) return [];
  const out: PurchaseMaterial[] = [];
  for (const line of lines) {
    for (const a of line.allocations ?? []) {
      if (a.purchase_slot === p.purchase_slot) {
        out.push({
          code: line.material_code ?? "—",
          quantity: num(a.quantity),
          unit: line.material_unit || "kg",
        });
      }
    }
  }
  return out;
}
