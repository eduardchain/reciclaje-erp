// Tipos InboundOrder — Recepción unificada (SAC, CC-004: 2 tipos)
// Espejo de backend/app/schemas/inbound_order.py

export type InboundType = "purchase" | "willard";
// B.2: willard nace "draft" (Registrada) y se confirma desde el detalle;
// tipos purchase nacen "confirmed" (su 2-pasos vive en la compra derivada)
export type InboundOrderStatus = "draft" | "confirmed" | "annulled";

export const INBOUND_TYPE_LABELS: Record<InboundType, string> = {
  purchase: "Compra regular",
  willard: "Willard",
};

// Willard mueve cuentas kg (ruteo por willard_world del material); purchase
// deriva una Compra registrada
export const WILLARD_INBOUND_TYPES: InboundType[] = ["willard"];
export const PURCHASE_INBOUND_TYPES: InboundType[] = ["purchase"];

export interface InboundOrderLineCreate {
  material_id: string;
  quantity: number;
  unit_price?: number | null;
  scale_weight_kg?: number | null;
  quality_notes?: string | null;
}

export interface InboundOrderCreate {
  inbound_type: InboundType;
  warehouse_id: string;
  third_party_id: string;
  date: string;
  driver_id?: string | null;
  vehicle_id?: string | null;
  /** Ciclo D: recolector por comisión (service_provider) — solo tipo compra */
  collector_id?: string | null;
  willard_distribution_center?: string | null;
  notes?: string | null;
  /** Ajustes 2026-08-03 (A): factura — compra la propaga a la compra derivada, willard a su columna */
  invoice_number?: string | null;
  lines: InboundOrderLineCreate[];
}

/**
 * Edición D18: campos ausentes = sin cambio (exclude_unset en backend).
 * Willard: lines/date disparan revert-and-reapply.
 * Tipos purchase: lines/date/centro → 422 (se editan en la compra derivada).
 */
export interface InboundOrderUpdate {
  date?: string;
  /** null explícito = quitar (alineado a fields_set en el backend, ajustes 2026-08-03) */
  driver_id?: string | null;
  vehicle_id?: string | null;
  /** Ciclo D: editable (incl. null para quitar) solo mientras la compra derivada esté registered */
  collector_id?: string | null;
  willard_distribution_center?: string;
  notes?: string | null;
  /** Ajustes 2026-08-03 (A): factura — compra la propaga a la compra derivada, willard a su columna */
  invoice_number?: string | null;
  lines?: InboundOrderLineCreate[];
}

export interface InboundOrderLineResponse {
  id: string;
  material_id: string;
  material_code: string | null;
  material_name: string | null;
  material_unit: string;
  quantity: number;
  unit: string | null;
  unit_price: number | null;
  unit_cost: number | null;
  scale_weight_kg: number | null;
  quality_notes: string | null;
  /** delta_kg emitido al KgLedger por esta línea (solo tipos Willard) */
  kg_lead: number | null;
}

/** Ciclo C: estado UNICO visible — deriva orden+compra (el usuario nunca ve
 *  el estado tecnico). registered=Registrada, liquidated=Liquidada,
 *  annulled=Anulada (incluye compras canceladas). */
export type InboundDisplayStatus = "registered" | "liquidated" | "annulled";

export const DISPLAY_STATUS_LABELS: Record<InboundDisplayStatus, string> = {
  registered: "Registrada",
  liquidated: "Liquidada",
  annulled: "Anulada",
};

export interface InboundOrderResponse {
  id: string;
  order_number: number;
  inbound_type: InboundType;
  warehouse_id: string;
  warehouse_name: string | null;
  third_party_id: string;
  third_party_name: string | null;
  date: string;
  driver_id: string | null;
  driver_name: string | null;
  vehicle_id: string | null;
  vehicle_plate: string | null;
  /** Ciclo D: recolector por comisión (solo tipo compra) */
  collector_id: string | null;
  collector_name: string | null;
  /** Solo en GET de detalle: comisión de recolección causada (gasto) */
  collector_commission_total?: number | null;
  willard_distribution_center: string | null;
  notes: string | null;
  /** Lectura condicional por tipo (D1): compra -> purchases.invoice_number, willard -> columna propia */
  invoice_number: string | null;
  status: InboundOrderStatus;
  display_status: InboundDisplayStatus;
  purchase_id: string | null;
  purchase_number: number | null;
  purchase_status: string | null;
  /** Mundo de la orden willard (drosses|postconsumo); null tipo compra */
  willard_world: string | null;
  /** Suma de deltas kg emitidos (solo tipos Willard) */
  total_kg_lead: number | null;
  annulled_reason: string | null;
  annulled_at: string | null;
  created_at: string;
  /** Ciclo C (C-5): quien hizo que */
  created_by_name: string | null;
  liquidated_by_name: string | null;
  liquidated_at: string | null;
  annulled_by_name: string | null;
  lines: InboundOrderLineResponse[];
  warnings: string[];
}

export interface InboundOrderListResponse {
  items: InboundOrderResponse[];
  total: number;
}
