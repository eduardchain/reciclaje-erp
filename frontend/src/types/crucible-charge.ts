// Documentos de crisol (#107 D2): el 4º "ítem" de Salidas de Plomo.
//
// `charge` = traslado a crisoles (horno −kg / crisol +kg, sin pesos);
// `dross_return` = retorno de dross al horno, y la maquila del reproceso.
//
// 🔴 #109 (cierre con el cliente, 16 y 18-sep) cambia dos cosas de #107:
// (a) DOS cantidades — `quantity_kg` es lo FÍSICO que se digita (kg de crudo, o
//     kg de DROSS) y `lead_kg` es el plomo: en un retorno el crisol baja los kg
//     de dross y el horno sube solo el plomo (70 % por fórmula), así que la
//     deuda total baja la diferencia, y es intencional;
// (b) los dos documentos MUEVEN INVENTARIO (crudo → puro 1:1; puro → crudo con
//     merma) por una transformación enlazada que solo se anula desde aquí.
//
// ⚠️ Los Decimal del backend llegan como STRING (bloqueante (b) de #93): los
// montos se declaran `string | number` y se leen con `num()`.

import { num } from "./willard-delivery";

export { num };

export type CrucibleEventType = "charge" | "dross_return";
export type CrucibleChargeStatus = "confirmed" | "annulled";

export const CRUCIBLE_EVENT_LABELS: Record<CrucibleEventType, string> = {
  charge: "Traslado a crisoles",
  dross_return: "Retorno de dross al horno",
};

export const CRUCIBLE_EVENT_COLORS: Record<CrucibleEventType, string> = {
  charge: "bg-orange-100 text-orange-800",
  dross_return: "bg-stone-200 text-stone-800",
};

export const CRUCIBLE_STATUS_LABELS: Record<CrucibleChargeStatus, string> = {
  confirmed: "Registrado",
  annulled: "Anulado",
};

export interface CrucibleCharge {
  id: string;
  charge_number: number;
  /** "Crisol #n" — usar este, no charge_number. */
  label: string;
  event_type: CrucibleEventType;
  warehouse_id: string;
  warehouse_name: string | null;
  material_id: string;
  material_code: string | null;
  material_name: string | null;
  /** Kg FÍSICOS digitados: crudo en un traslado, DROSS en un retorno. */
  quantity_kg: string | number;
  /** Kg de PLOMO: = quantity_kg en un traslado; dross × % de la fórmula en un retorno. */
  lead_kg: string | number;
  transformation_id: string | null;
  transformation_number: number | null;
  inventory_out: CrucibleInventoryLeg | null;
  inventory_in: CrucibleInventoryLeg | null;
  date: string;
  notes: string | null;
  status: CrucibleChargeStatus;
  /** Maquila del reproceso causada por un retorno de dross ($0 en un traslado). */
  maquila_amount: string | number;
  annulled_reason: string | null;
  annulled_at: string | null;
  annulled_by_name: string | null;
  created_by_name: string | null;
  created_at: string;
  /** Advertencias no bloqueantes (#17/#76) — se leen de la RESPUESTA (#100 D4d). */
  warnings?: string[];
}

export interface CrucibleInventoryLeg {
  material_id: string;
  material_code: string | null;
  material_name: string | null;
  quantity: string | number;
}

export interface CrucibleChargeListResponse {
  items: CrucibleCharge[];
  total: number;
  page: number;
  page_size: number;
}

export interface CrucibleChargeCreate {
  event_type: CrucibleEventType;
  warehouse_id: string;
  material_id: string;
  quantity_kg: string;
  date: string;
  notes?: string | null;
  /** Solo si hay más de un material marcado como puro / crudo. */
  puro_material_id?: string | null;
  crudo_material_id?: string | null;
}
