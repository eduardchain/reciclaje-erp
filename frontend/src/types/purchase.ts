import type { BaseEntity, PaginatedResponse } from "./common";

export type PurchaseStatus = "registered" | "liquidated" | "cancelled";

export type PurchaseChargeType = "commission" | "freight";

export interface PurchaseCommissionCreate {
  third_party_id: string;
  concept: string;
  commission_type: "percentage" | "fixed" | "per_kg";
  commission_value: number;
  charge_type?: PurchaseChargeType; // default backend: commission
}

export interface PurchaseCommissionResponse {
  id: string;
  purchase_id: string;
  third_party_id: string;
  concept: string;
  commission_type: "percentage" | "fixed" | "per_kg";
  commission_value: number;
  commission_amount: number;
  charge_type: PurchaseChargeType;
  created_at: string;
  third_party_name: string;
}

// SAC E2 D9 — retenciones tributarias al liquidar (solo con flag kg_ledger_enabled)
export type RetentionType = "retefuente" | "reteiva" | "ica";

export const RETENTION_TYPE_LABELS: Record<RetentionType, string> = {
  retefuente: "ReteFuente",
  reteiva: "ReteIVA",
  ica: "ICA",
};

export interface PurchaseRetentionCreate {
  retention_type: RetentionType;
  /** Obligatorio en ICA (una entidad por municipio), prohibido en las demás */
  municipality?: string | null;
  amount: number;
}

export interface PurchaseRetentionResponse {
  id: string;
  third_party_id: string;
  retention_type: RetentionType;
  municipality: string | null;
  rate: number | null;
  base: number | null;
  amount: number;
  reverted_at: string | null;
}

export interface PurchaseLineCreate {
  material_id: string;
  quantity: number;
  unit_price: number;
  warehouse_id?: string | null;
}

export interface PurchaseLineResponse {
  id: string;
  purchase_id: string;
  material_id: string;
  quantity: number;
  unit_price: number;
  total_price: number;
  warehouse_id: string | null;
  created_at: string;
  material_code: string;
  material_name: string;
  material_unit: string;
  warehouse_name: string | null;
}

export interface PurchaseCreate {
  supplier_id: string;
  date: string;
  notes?: string | null;
  vehicle_plate?: string | null;
  invoice_number?: string | null;
  /** Bodega header (SAC E2 D11, solo con flag kg_ledger_enabled): fuerza la bodega de todas las lineas */
  warehouse_id?: string | null;
  lines: PurchaseLineCreate[];
  commissions?: PurchaseCommissionCreate[];
  auto_liquidate?: boolean;
  immediate_payment?: boolean;
  payment_account_id?: string | null;
}

export interface PurchaseUpdate {
  notes?: string | null;
  date?: string | null;
  vehicle_plate?: string | null;
  invoice_number?: string | null;
}

export interface PurchaseResponse extends BaseEntity {
  organization_id: string;
  purchase_number: number;
  supplier_id: string;
  date: string;
  notes: string | null;
  vehicle_plate: string | null;
  invoice_number: string | null;
  double_entry_id: string | null;
  total_amount: number;
  status: PurchaseStatus;
  payment_account_id: string | null;
  created_by: string | null;
  liquidated_by: string | null;
  liquidated_at: string | null;
  cancelled_by: string | null;
  cancelled_at: string | null;
  updated_by: string | null;
  created_by_name: string | null;
  liquidated_by_name: string | null;
  cancelled_by_name: string | null;
  updated_by_name: string | null;
  supplier_name: string;
  payment_account_name: string | null;
  lines: PurchaseLineResponse[];
  commissions: PurchaseCommissionResponse[];
  /** SAC E2 D9 — vacío para orgs sin flag */
  retentions: PurchaseRetentionResponse[];
  linked_payment_total: number | null;
  /** SAC Ciclo B (B1) — origen inbound; null para compras manuales / orgs sin recepción */
  inbound_order_id?: string | null;
  inbound_order_number?: number | null;
  warnings?: string[];
}

export interface PurchaseFullUpdate {
  supplier_id?: string;
  date?: string;
  notes?: string | null;
  vehicle_plate?: string | null;
  invoice_number?: string | null;
  lines?: PurchaseLineCreate[];
  commissions?: PurchaseCommissionCreate[];
}

export interface PurchaseLiquidateLineUpdate {
  line_id: string;
  unit_price: number;
}

export interface PurchaseLiquidateRequest {
  lines?: PurchaseLiquidateLineUpdate[];
  commissions?: PurchaseCommissionCreate[];
  /** SAC E2 D9 — AUSENTE (no []) para orgs sin flag: payload byte-idéntico al actual */
  retentions?: PurchaseRetentionCreate[];
  immediate_payment?: boolean;
  payment_account_id?: string;
  liquidation_date?: string;
}

/**
 * Listado paginado de compras con totales agregados sobre el set filtrado
 * EXCLUYENDO canceladas (paridad con P&L).
 */
export interface PaginatedPurchaseResponse extends PaginatedResponse<PurchaseResponse> {
  /** Count excluyendo canceladas — para KPI "Operaciones". `total` cuenta tambien canceladas (paginacion). */
  active_total: number;
  /** SUM(total_amount) excluyendo canceladas. */
  total_amount_sum: number;
}
