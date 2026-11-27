import { num } from "@/types/willard-delivery";
import type { TransferLineResponse } from "@/types/transfer";

// Totales de la tabla «Líneas» del detalle de un traslado (kg de plomo y maquila).
//
// ⚠️ Los Decimal del backend llegan como STRING (#93/#107): se leen con `num()`,
// pero SOLO después de preguntar `!= null`, porque `num(null)` da 0 y un cero
// fabricado es justo lo que esta fila no puede mostrar.

export type TotalLine = Pick<
  TransferLineResponse,
  "is_contributor" | "effects_emitted" | "kg_lead_equivalent" | "maquila_amount"
>;

export interface ColumnTotal {
  value: number | null; // null = ninguna línea tiene valor
  pending: number; // aportantes con !effects_emitted
  contributors: number; // aportantes en total
  partial: boolean; // hay suma Y pending > 0
  emptyLabel: "—" | "N/A"; // lo que se pinta si value es null
}

// Escala de cada columna: kg con 4 decimales, pesos con centavos. Se suma en
// ENTEROS y se divide al final, así 0,1 + 0,2 da exactamente 0,3.
const KG_SCALE = 10_000;
const COP_SCALE = 100;

function column(
  lines: TotalLine[],
  pick: (l: TotalLine) => string | number | null | undefined,
  scale: number,
  noContributorLabel: "—" | "N/A"
): ColumnTotal {
  const contributors = lines.filter((l) => l.is_contributor).length;
  // «Parcial» se decide por líneas PENDIENTES (retenidas o sin recibir), no por
  // nulos: una línea ya emitida puede tener maquila null por ser legítimamente 0.
  const pending = lines.filter((l) => l.is_contributor && !l.effects_emitted).length;
  let units = 0;
  let withValue = 0;
  for (const l of lines) {
    const raw = pick(l);
    if (raw == null) continue;
    units += Math.round(num(raw) * scale);
    withValue += 1;
  }
  if (withValue === 0) {
    return {
      value: null,
      pending,
      contributors,
      partial: false,
      emptyLabel: contributors === 0 ? noContributorLabel : "—",
    };
  }
  return { value: units / scale, pending, contributors, partial: pending > 0, emptyLabel: "—" };
}

export function transferTotals(lines: TotalLine[]): { kg: ColumnTotal; maquila: ColumnTotal } {
  return {
    kg: column(lines, (l) => l.kg_lead_equivalent, KG_SCALE, "N/A"),
    maquila: column(lines, (l) => l.maquila_amount, COP_SCALE, "—"),
  };
}
