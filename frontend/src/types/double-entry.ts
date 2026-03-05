import type { BaseEntity } from "./common";
import type { SaleCommissionCreate, SaleCommissionResponse } from "./sale";

export type DoubleEntryStatus = "completed" | "cancelled";

export interface DoubleEntryCreate {
  material_id: string;
  quantity: number;
  supplier_id: string;
  purchase_unit_price: number;
  customer_id: string;
  sale_unit_price: number;
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
  material_id: string;
  quantity: number;
  supplier_id: string;
  purchase_unit_price: number;
  customer_id: string;
  sale_unit_price: number;
  date: string;
  invoice_number: string | null;
  vehicle_plate: string | null;
  notes: string | null;
  purchase_id: string;
  sale_id: string;
  status: DoubleEntryStatus;
  total_purchase_cost: number;
  total_sale_amount: number;
  profit: number;
  profit_margin: number;
  material_code: string;
  material_name: string;
  supplier_name: string;
  customer_name: string;
  commissions: SaleCommissionResponse[];
}
