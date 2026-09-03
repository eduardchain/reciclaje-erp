// Salidas de plomo a Willard (W1).
//
// ⚠️ Todo lo que el backend declara como Decimal llega como STRING (FastAPI
// serializa asi). Es el bloqueante (b) de #93: el tipo decia `number`, `acc + x`
// concatenaba texto y el resultado fue "NaN kg". Aca los montos se declaran
// `string | number` y se leen SIEMPRE con `num()`.

export type WillardDeliveryType = "venta" | "abono_bateria" | "abono_material";
export type WillardDeliveryStatus = "draft" | "reviewed" | "liquidated" | "annulled";

/** Coercion en la frontera: el tipo se cumple porque se fuerza al entrar. */
export function num(value: string | number | null | undefined): number {
  if (value === null || value === undefined) return 0;
  const n = typeof value === "number" ? value : parseFloat(value);
  return Number.isFinite(n) ? n : 0;
}

export const DELIVERY_TYPE_LABELS: Record<WillardDeliveryType, string> = {
  venta: "Venta",
  abono_bateria: "Abono a batería",
  abono_material: "Abono a material",
};

export const DELIVERY_TYPE_COLORS: Record<WillardDeliveryType, string> = {
  venta: "bg-emerald-100 text-emerald-800",
  abono_bateria: "bg-violet-100 text-violet-800",
  abono_material: "bg-cyan-100 text-cyan-800",
};

export const DELIVERY_STATUS_LABELS: Record<WillardDeliveryStatus, string> = {
  draft: "Registrada",
  reviewed: "Revisada",
  liquidated: "Liquidada",
  annulled: "Anulada",
};

export const DELIVERY_STATUS_COLORS: Record<WillardDeliveryStatus, string> = {
  draft: "bg-amber-100 text-amber-800",
  reviewed: "bg-blue-100 text-blue-800",
  liquidated: "bg-green-100 text-green-800",
  annulled: "bg-slate-200 text-slate-600",
};

export interface WillardDeliveryLine {
  id: string;
  material_id: string;
  material_code: string | null;
  material_name: string | null;
  material_unit: string;
  quantity: string | number;
  unit: string | null;
  scale_weight_kg: string | number | null;
  kg_lead_equivalent: string | number | null;
  unit_cost: string | number | null;
  unit_price: string | number | null;
  total_price: string | number | null;
}

export interface WillardDelivery {
  id: string;
  delivery_number: number;
  delivery_type: WillardDeliveryType;
  warehouse_id: string;
  warehouse_name: string | null;
  third_party_id: string;
  third_party_name: string | null;
  date: string;
  driver_id: string | null;
  driver_name: string | null;
  vehicle_id: string | null;
  vehicle_plate: string | null;
  invoice_number: string | null;
  remission_number: string | null;
  notes: string | null;
  status: WillardDeliveryStatus;

  reviewed_at: string | null;
  reviewed_by_name: string | null;
  liquidated_at: string | null;
  /** Instante real del clic — este SI lleva hora (#93/#87) */
  liquidated_ts: string | null;
  liquidated_by_name: string | null;
  annulled_reason: string | null;
  annulled_at: string | null;
  annulled_by_name: string | null;
  created_by_name: string | null;

  sale_id: string | null;
  sale_number: number | null;

  maquila_amount: string | number;
  freight_amount: string | number;
  plant_credit_amount: string | number;
  total_kg_lead: string | number;

  lines: WillardDeliveryLine[];
}

export interface WillardDeliveryListResponse {
  items: WillardDelivery[];
  total: number;
  page: number;
  page_size: number;
}

export interface WillardDeliveryLineCreate {
  material_id: string;
  quantity: string;
  scale_weight_kg?: string | null;
}

export interface WillardDeliveryCreate {
  delivery_type: WillardDeliveryType;
  warehouse_id: string;
  third_party_id: string;
  date: string;
  driver_id?: string | null;
  vehicle_id?: string | null;
  invoice_number?: string | null;
  remission_number?: string | null;
  notes?: string | null;
  lines: WillardDeliveryLineCreate[];
}

export interface WillardDeliveryUpdate {
  warehouse_id?: string;
  date?: string;
  driver_id?: string | null;
  vehicle_id?: string | null;
  invoice_number?: string | null;
  remission_number?: string | null;
  notes?: string | null;
  lines?: WillardDeliveryLineCreate[];
}

export interface WillardDeliveryLinePrice {
  line_id: string;
  unit_price?: string | null;
  total_price?: string | null;
}

export interface WillardDeliveryLiquidate {
  line_prices: WillardDeliveryLinePrice[];
  customer_id?: string | null;
}
