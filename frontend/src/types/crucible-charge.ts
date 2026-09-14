// Documentos de crisol (#107 D2): el 4º "ítem" de Salidas de Plomo.
//
// `charge` = traslado a crisoles (horno −kg / crisol +kg, sin pesos);
// `dross_return` = retorno de dross al horno (crisol −kg / horno +kg, y se causa
// la maquila del reproceso). Ninguno mueve inventario: es control de DÓNDE está
// el plomo dentro de la deuda de planta con Circunvalar.
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
  quantity_kg: string | number;
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
}
