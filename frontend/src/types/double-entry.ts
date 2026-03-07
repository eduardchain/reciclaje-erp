import type { BaseEntity } from "./common";
import type { SaleCommissionCreate, SaleCommissionResponse } from "./sale";

export type DoubleEntryStatus = "completed" | "cancelled";

// ============================================================================
// Line schemas
// ============================================================================

export interface DoubleEntryLineCreate {
  material_id: string;
  quantity: number;
  purchase_unit_price: number;
  sale_unit_price: number;
}

export interface DoubleEntryLineResponse {
  id: string;
  material_id: string;
  quantity: number;
  purchase_unit_price: number;
  sale_unit_price: number;
  total_purchase: number;
  total_sale: number;
  profit: number;
  material_code: string;
  material_name: string;
}

// ============================================================================
// DoubleEntry schemas
// ============================================================================

export interface DoubleEntryCreate {
  lines: DoubleEntryLineCreate[];
  supplier_id: string;
  customer_id: string;
  date: string;
  invoice_number?: string | null;
  vehicle_plate?: string | null;
  notes?: string | null;
  commissions?: SaleCommissionCreate[];
}

export interface DoubleEntryUpdate {
  notes?: string | null;
  invoice_number?: string | null;
  vehicle_plate?: string | null;
}

export interface DoubleEntryResponse extends BaseEntity {
  organization_id: string;
  double_entry_number: number;
  date: string;
  supplier_id: string;
  customer_id: string;
  invoice_number: string | null;
  vehicle_plate: string | null;
  notes: string | null;
  purchase_id: string;
  sale_id: string;
  status: DoubleEntryStatus;
  lines: DoubleEntryLineResponse[];
  materials_summary: string;
  total_purchase_cost: number;
  total_sale_amount: number;
  profit: number;
  profit_margin: number;
  supplier_name: string;
  customer_name: string;
  commissions: SaleCommissionResponse[];
}
