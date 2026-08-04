// SAC E3.1 — Traslados intersede dos pasos (plan v1.1)

export interface TransferLineCreate {
  material_id: string;
  quantity_dispatched: number;
}

export interface TransferDispatchCreate {
  from_warehouse_id: string;
  to_warehouse_id: string;
  dispatch_date?: string;
  notes?: string;
  lines: TransferLineCreate[];
}

export interface TransferReceiveLine {
  transfer_line_id: string;
  quantity_received: number;
}

export interface TransferReceiveRequest {
  lines: TransferReceiveLine[];
  receipt_date?: string;
  notes?: string;
}

export interface TransferResolveLine {
  transfer_line_id: string;
  resolution: "justify" | "correct";
  final_quantity?: number;
}

export interface TransferResolveRequest {
  lines: TransferResolveLine[];
  notes: string;
}

export type TransferStatus =
  | "dispatched"
  | "held_discrepancy"
  | "received"
  | "annulled";

export interface TransferLineResponse {
  id: string;
  material_id: string;
  material_code?: string | null;
  material_name?: string | null;
  material_unit: string;
  quantity_dispatched: number;
  quantity_received?: number | null;
  resolved_quantity?: number | null;
  unit_cost: number;
  is_contributor: boolean;
  kg_lead_equivalent?: number | null;
  maquila_amount?: number | null;
  discrepancy_task_id?: string | null;
  effects_emitted: boolean;
  variance_pct?: number | null;
}

export interface TransferResponse {
  id: string;
  transfer_number: number;
  from_warehouse_id: string;
  from_warehouse_name?: string | null;
  to_warehouse_id: string;
  to_warehouse_name?: string | null;
  transit_warehouse_id: string;
  transit_warehouse_name?: string | null;
  dispatch_date: string;
  received_date?: string | null;
  status: TransferStatus;
  notes?: string | null;
  created_by_name?: string | null;
  received_by_name?: string | null;
  annulled_reason?: string | null;
  annulled_at?: string | null;
  created_at: string;
  lines: TransferLineResponse[];
  warnings: string[];
}

export interface TransferListResponse {
  items: TransferResponse[];
  total: number;
  pending_receipt_count: number;
}

export const TRANSFER_STATUS_LABELS: Record<TransferStatus, string> = {
  dispatched: "Despachado",
  held_discrepancy: "En discrepancia",
  received: "Recibido",
  annulled: "Anulado",
};
