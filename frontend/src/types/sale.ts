import type { BaseEntity } from "./common";

export type SaleStatus = "registered" | "liquidated" | "cancelled";

export interface SaleCommissionCreate {
  third_party_id: string;
  concept: string;
  commission_type: "percentage" | "fixed";
  commission_value: number;
}

export interface SaleCommissionResponse {
  id: string;
  sale_id: string;
  third_party_id: string;
  concept: string;
  commission_type: "percentage" | "fixed";
  commission_value: number;
  commission_amount: number;
  created_at: string;
  third_party_name: string;
}

export interface SaleLineCreate {
  material_id: string;
  quantity: number;
  unit_price: number;
}

export interface SaleLineResponse {
  id: string;
  sale_id: string;
  material_id: string;
  quantity: number;
  unit_price: number;
  total_price: number;
  unit_cost: number;
  profit: number;
  created_at: string;
  material_code: string;
  material_name: string;
  received_quantity: number | null;
  quantity_difference: number | null;
  amount_difference: number | null;
}

export interface SaleCreate {
  customer_id: string;
  warehouse_id?: string | null;
  date: string;
  vehicle_plate?: string | null;
  invoice_number?: string | null;
  notes?: string | null;
  lines: SaleLineCreate[];
  commissions?: SaleCommissionCreate[];
  auto_liquidate?: boolean;
  immediate_collection?: boolean;
  collection_account_id?: string | null;
}

export interface SaleUpdate {
  notes?: string | null;
  vehicle_plate?: string | null;
  invoice_number?: string | null;
}

export interface SaleFullUpdate {
  customer_id?: string | null;
  warehouse_id?: string | null;
  date?: string | null;
  notes?: string | null;
  vehicle_plate?: string | null;
  invoice_number?: string | null;
  lines?: SaleLineCreate[] | null;
  commissions?: SaleCommissionCreate[] | null;
}

export interface SaleResponse extends BaseEntity {
  organization_id: string;
  sale_number: number;
  customer_id: string;
  warehouse_id: string | null;
  date: string;
  vehicle_plate: string | null;
  invoice_number: string | null;
  notes: string | null;
  double_entry_id: string | null;
  total_amount: number;
  total_profit: number;
  status: SaleStatus;
  payment_account_id: string | null;
  created_by: string | null;
  liquidated_by: string | null;
  updated_by: string | null;
  liquidated_at: string | null;
  cancelled_by: string | null;
  cancelled_at: string | null;
  created_by_name: string | null;
  liquidated_by_name: string | null;
  updated_by_name: string | null;
  customer_name: string;
  warehouse_name: string | null;
  payment_account_name: string | null;
  lines: SaleLineResponse[];
  commissions: SaleCommissionResponse[];
  total_quantity_difference: number | null;
  total_amount_difference: number | null;
  warnings: string[];
}

export interface SaleLiquidateLineUpdate {
  line_id: string;
  unit_price: number;
  received_quantity?: number;
}

export interface SaleLiquidateRequest {
  lines?: SaleLiquidateLineUpdate[];
  commissions?: SaleCommissionCreate[];
  immediate_collection?: boolean;
  collection_account_id?: string;
}
