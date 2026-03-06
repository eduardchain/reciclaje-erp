import type { BaseEntity } from "./common";

export type PurchaseStatus = "registered" | "paid" | "cancelled";

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
  warehouse_name: string | null;
}

export interface PurchaseCreate {
  supplier_id: string;
  date: string;
  notes?: string | null;
  vehicle_plate?: string | null;
  invoice_number?: string | null;
  lines: PurchaseLineCreate[];
  auto_liquidate?: boolean;
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
  supplier_name: string;
  payment_account_name: string | null;
  lines: PurchaseLineResponse[];
}

export interface PurchaseFullUpdate {
  supplier_id?: string;
  date?: string;
  notes?: string | null;
  vehicle_plate?: string | null;
  invoice_number?: string | null;
  lines?: PurchaseLineCreate[];
}

export interface PurchaseLiquidateRequest {
  payment_account_id: string;
}
