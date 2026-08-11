// Tipos InboundOrder — Entradas (SAC, #93: entrada sin proveedor)
// Espejo de backend/app/schemas/inbound_order.py

export type InboundType = "purchase" | "willard";
// #93 (D4): tipo compra vive draft -> reviewed -> liquidated | annulled;
// willard conserva draft -> confirmed | annulled (B.2 intacto)
export type InboundOrderStatus =
  | "draft"
  | "reviewed"
  | "liquidated"
  | "confirmed"
  | "annulled";

export const INBOUND_TYPE_LABELS: Record<InboundType, string> = {
  purchase: "Compra regular",
  willard: "Willard",
};

// Willard mueve cuentas kg (ruteo por willard_world del material); purchase
// se reparte entre proveedores al liquidar (#93)
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
  /** #93 D1: SOLO willard (titular de la cuenta kg) — tipo compra lo omite
   *  (el proveedor se asigna al liquidar, enviarlo da 422) */
  third_party_id?: string | null;
  date: string;
  driver_id?: string | null;
  vehicle_id?: string | null;
  /** Ciclo D: recolector (service_provider) — ambos tipos; comisión solo compra */
  collector_id?: string | null;
  willard_distribution_center?: string | null;
  notes?: string | null;
  /** #93 D12: factura SOLO willard — en compra llega POR PROVEEDOR al liquidar */
  invoice_number?: string | null;
  /** #93 D12: remisión del camión — UNA por entrada, capturada en patio */
  remission_number?: string | null;
  lines: InboundOrderLineCreate[];
}

/**
 * Edición: campos ausentes = sin cambio (exclude_unset en backend).
 * Willard: lines/date disparan revert-and-reapply.
 * Tipo compra (#93): lines/date editables en draft/reviewed (cero efectos);
 * liquidada → 422 (exige revertir la liquidación primero).
 */
export interface InboundOrderUpdate {
  date?: string;
  /** null explícito = quitar (alineado a fields_set en el backend) */
  driver_id?: string | null;
  vehicle_id?: string | null;
  /** Ciclo D: willard siempre; compra se congela al liquidar (#93) */
  collector_id?: string | null;
  willard_distribution_center?: string;
  notes?: string | null;
  /** Willard/legacy; tipo compra nuevo → 422 (vive en el reparto) */
  invoice_number?: string | null;
  remission_number?: string | null;
  lines?: InboundOrderLineCreate[];
}

// ------------------------------------------------------------------ //
// #93 — Reparto y liquidación                                         //
// ------------------------------------------------------------------ //

export interface InboundAllocationCreate {
  third_party_id: string;
  quantity: number;
  unit_price: number;
  /** Factura del proveedor (D12) */
  invoice_number?: string | null;
}

export interface InboundLiquidateLine {
  material_id: string;
  /** D6: obligatorio si la línea queda con descuadre != 0 */
  reference_unit_price?: number | null;
  /** D8: declaración explícita "este material no es de nadie" */
  unallocated_intentional?: boolean;
  allocations: InboundAllocationCreate[];
}

export interface InboundCollectorCommission {
  third_party_id: string;
  amount: number;
}

/** Addendum retenciones #93 (QA): un bloque = un tipo de retención con su
 *  monto (editable, el precálculo % × subtotal del proveedor solo sugiere) */
export interface InboundRetentionCreate {
  retention_type: "retefuente" | "reteiva" | "ica";
  /** Obligatorio en ICA (una entidad por municipio), prohibido en las demás */
  municipality?: string | null;
  /** Auditoría del precálculo ofrecido (informativos, F1 #79) */
  rate?: number | null;
  base?: number | null;
  amount: number;
}

/** Retenciones OPCIONALES por proveedor del reparto ("sí les descuenta,
 *  pero no a todas") — heredan #79 completo vía purchase.liquidate() */
export interface InboundSupplierRetentions {
  third_party_id: string;
  retentions: InboundRetentionCreate[];
}

/** Pago de contado POR PROVEEDOR (pruebas de usuario 2026-08-11) — misma
 *  familia que las retenciones. El monto no viaja: el backend paga el NETO. */
export interface InboundSupplierPayment {
  third_party_id: string;
  account_id: string;
}

export interface InboundLiquidateRequest {
  lines: InboundLiquidateLine[];
  /** D11: UNA comisión por entrada, sobre lo PESADO (sugerida = tarifa × base) */
  collector_commission?: InboundCollectorCommission | null;
  /** Ausente = cero efecto (data-gated D9) */
  supplier_retentions?: InboundSupplierRetentions[] | null;
  supplier_payments?: InboundSupplierPayment[] | null;
}

export interface InboundAllocationResponse {
  id: string;
  third_party_id: string;
  third_party_name: string | null;
  quantity: number;
  unit_price: number;
  invoice_number: string | null;
}

/** Cara financiera por proveedor — las N compras del reparto (vía puente) */
export interface InboundPurchaseSummary {
  purchase_id: string;
  purchase_number: number;
  supplier_id: string;
  supplier_name: string | null;
  status: string;
  total_amount: number;
  invoice_number: string | null;
  /** Retenciones vivas de la compra — el proveedor quedó acreditado NETO */
  retentions_total?: number | null;
  /** Último lote de retenciones (vivas, o las revertidas más recientes tras
   *  des-liquidar) — alimenta la precarga al re-liquidar */
  retentions?: InboundRetentionDetail[];
}

export interface InboundRetentionDetail {
  retention_type: "retefuente" | "reteiva" | "ica";
  municipality: string | null;
  rate: number | null;
  base: number | null;
  amount: number;
}

/** Ajuste de descuadre generado al liquidar (D7) — la ganancia/pérdida que la
 *  Entrada mandó a resultados, visible sin salir a Reportes */
export interface InboundDiscrepancyAdjustment {
  adjustment_id: string;
  adjustment_number: number | null;
  material_id: string;
  material_code: string | null;
  material_unit: string;
  adjustment_type: "increase" | "decrease";
  quantity: number;
  unit_cost: number | null;
  /** con signo: + ganancia (sobrante), − pérdida (faltante) */
  total_value: number;
  status: string;
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
  /** #93: reparto y descuadre (tipo compra) */
  reference_unit_price: number | null;
  unallocated_intentional: boolean;
  allocations: InboundAllocationResponse[];
  allocated_quantity: number | null;
  /** pesado - repartido (D5): + sobrante, - faltante */
  discrepancy: number | null;
}

/** #93 D4: estado ÚNICO visible, columna-driven. registered=Registrada,
 *  reviewed=Revisada, liquidated=Liquidada, annulled=Anulada. */
export type InboundDisplayStatus =
  | "registered"
  | "reviewed"
  | "liquidated"
  | "annulled";

export const DISPLAY_STATUS_LABELS: Record<InboundDisplayStatus, string> = {
  registered: "Registrada",
  reviewed: "Revisada",
  liquidated: "Liquidada",
  annulled: "Anulada",
};

export interface InboundOrderResponse {
  id: string;
  order_number: number;
  inbound_type: InboundType;
  warehouse_id: string;
  warehouse_name: string | null;
  /** #93 D1: NULL en capturas tipo compra (el proveedor vive en el reparto) */
  third_party_id: string | null;
  third_party_name: string | null;
  date: string;
  driver_id: string | null;
  driver_name: string | null;
  vehicle_id: string | null;
  vehicle_plate: string | null;
  /** Ciclo D: recolector — informativo en willard, con comisión en compras */
  collector_id: string | null;
  collector_name: string | null;
  /** Solo en GET de detalle: comisión de recolección causada (gasto) */
  collector_commission_total?: number | null;
  willard_distribution_center: string | null;
  notes: string | null;
  /** Willard: columna propia. Compra #93: NULL — vive POR PROVEEDOR en purchases[] */
  invoice_number: string | null;
  /** #93 D12: remisión del camión (documento de patio) */
  remission_number: string | null;
  status: InboundOrderStatus;
  display_status: InboundDisplayStatus;
  /** Legacy 1:1 (ciclos B-D) — poblados solo en filas viejas */
  purchase_id: string | null;
  purchase_number: number | null;
  purchase_status: string | null;
  /** #93: las N compras del reparto (vía puente) */
  purchases: InboundPurchaseSummary[];
  /** Solo en el detalle (el listado no los trae) */
  discrepancy_adjustments?: InboundDiscrepancyAdjustment[];
  /** #93 D10: auditoría de revisión */
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  /** Mundo de la orden willard (drosses|postconsumo); null tipo compra */
  willard_world: string | null;
  /** Suma de deltas kg emitidos (solo tipos Willard) */
  total_kg_lead: number | null;
  annulled_reason: string | null;
  annulled_at: string | null;
  created_at: string;
  /** Ciclo C (C-5): quién hizo qué */
  created_by_name: string | null;
  liquidated_by_name: string | null;
  /** Fecha de NEGOCIO — pintar con formatDate (SIN hora, #87) */
  liquidated_at: string | null;
  /** Instante real del clic — este SÍ con formatDateTime */
  liquidated_ts?: string | null;
  annulled_by_name: string | null;
  lines: InboundOrderLineResponse[];
  warnings: string[];
}

export interface InboundOrderListResponse {
  items: InboundOrderResponse[];
  total: number;
}
