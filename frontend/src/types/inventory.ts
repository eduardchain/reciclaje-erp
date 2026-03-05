import type { BaseEntity } from "./common";

// --- Inventory Movements ---

export type InventoryMovementType =
  | "purchase"
  | "sale"
  | "adjustment"
  | "transfer"
  | "purchase_reversal"
  | "sale_reversal"
  | "transformation";

export interface InventoryMovementResponse extends BaseEntity {
  organization_id: string;
  material_id: string;
  warehouse_id: string;
  movement_type: InventoryMovementType;
  quantity: number;
  unit_cost: number;
  reference_type: string | null;
  reference_id: string | null;
  date: string;
  notes: string | null;
  material_code: string;
  material_name: string;
  warehouse_name: string;
}

// --- Inventory Adjustments ---

export type AdjustmentType = "increase" | "decrease" | "recount" | "zero_out";
export type AdjustmentStatus = "completed" | "annulled";

export interface IncreaseCreate {
  material_id: string;
  warehouse_id: string;
  quantity: number;
  unit_cost: number;
  date: string;
  reason: string;
  notes?: string | null;
}

export interface DecreaseCreate {
  material_id: string;
  warehouse_id: string;
  quantity: number;
  date: string;
  reason: string;
  notes?: string | null;
}

export interface RecountCreate {
  material_id: string;
  warehouse_id: string;
  counted_quantity: number;
  date: string;
  reason: string;
  notes?: string | null;
}

export interface ZeroOutCreate {
  material_id: string;
  warehouse_id: string;
  date: string;
  reason: string;
  notes?: string | null;
}

export interface AnnulAdjustmentRequest {
  reason: string;
}

export interface InventoryAdjustmentResponse extends BaseEntity {
  organization_id: string;
  adjustment_number: number;
  date: string;
  adjustment_type: AdjustmentType;
  material_id: string;
  material_code: string | null;
  material_name: string | null;
  warehouse_id: string;
  warehouse_name: string | null;
  previous_stock: number;
  quantity: number;
  new_stock: number;
  counted_quantity: number | null;
  unit_cost: number;
  total_value: number;
  reason: string;
  notes: string | null;
  status: AdjustmentStatus;
  annulled_reason: string | null;
  annulled_at: string | null;
  annulled_by: string | null;
  created_by: string | null;
  warnings: string[];
}

// --- Warehouse Transfers ---

export interface WarehouseTransferCreate {
  material_id: string;
  source_warehouse_id: string;
  destination_warehouse_id: string;
  quantity: number;
  date: string;
  reason: string;
  notes?: string | null;
}

export interface WarehouseTransferResponse {
  material_id: string;
  material_code: string | null;
  material_name: string | null;
  source_warehouse_id: string;
  source_warehouse_name: string | null;
  destination_warehouse_id: string;
  destination_warehouse_name: string | null;
  quantity: number;
  date: string;
  reason: string;
  notes: string | null;
  warnings: string[];
}

// --- Material Transformations ---

export type CostDistribution = "proportional_weight" | "manual";
export type TransformationStatus = "completed" | "annulled";

export interface TransformationLineCreate {
  destination_material_id: string;
  destination_warehouse_id: string;
  quantity: number;
  unit_cost?: number | null;
}

export interface MaterialTransformationCreate {
  source_material_id: string;
  source_warehouse_id: string;
  source_quantity: number;
  waste_quantity?: number;
  cost_distribution: CostDistribution;
  lines: TransformationLineCreate[];
  date: string;
  reason: string;
  notes?: string | null;
}

export interface TransformationLineResponse {
  id: string;
  destination_material_id: string;
  destination_material_code: string | null;
  destination_material_name: string | null;
  destination_warehouse_id: string;
  destination_warehouse_name: string | null;
  quantity: number;
  unit_cost: number;
  total_cost: number;
}

export interface MaterialTransformationResponse extends BaseEntity {
  organization_id: string;
  transformation_number: number;
  date: string;
  source_material_id: string;
  source_material_code: string | null;
  source_material_name: string | null;
  source_warehouse_id: string;
  source_warehouse_name: string | null;
  source_quantity: number;
  source_unit_cost: number;
  source_total_value: number;
  waste_quantity: number;
  waste_value: number;
  cost_distribution: CostDistribution;
  lines: TransformationLineResponse[];
  reason: string;
  notes: string | null;
  status: TransformationStatus;
  annulled_reason: string | null;
  annulled_at: string | null;
  annulled_by: string | null;
  created_by: string | null;
  warnings: string[];
}

export interface AnnulTransformationRequest {
  reason: string;
}

// --- Inventory Views ---

export interface StockItem {
  material_id: string;
  material_code: string;
  material_name: string;
  default_unit: string;
  current_stock_liquidated: number;
  current_stock_transit: number;
  current_stock_total: number;
  current_average_cost: number;
  total_value: number;
  is_active: boolean;
}

export interface StockConsolidatedResponse {
  items: StockItem[];
  total: number;
  total_valuation: number;
}

export interface WarehouseStockDetail {
  warehouse_id: string;
  warehouse_name: string;
  stock: number;
}

export interface MaterialStockDetailResponse {
  material_id: string;
  material_code: string;
  material_name: string;
  default_unit: string;
  current_stock_liquidated: number;
  current_stock_transit: number;
  current_stock_total: number;
  current_average_cost: number;
  total_value: number;
  warehouses: WarehouseStockDetail[];
}

export interface TransitItem {
  material_id: string;
  material_code: string;
  material_name: string;
  default_unit: string;
  current_stock_transit: number;
  current_stock_liquidated: number;
}

export interface TransitResponse {
  items: TransitItem[];
  total: number;
}

export interface MovementItem {
  id: string;
  material_id: string;
  material_code: string | null;
  material_name: string | null;
  warehouse_id: string;
  warehouse_name: string | null;
  movement_type: string;
  quantity: number;
  unit_cost: number;
  reference_type: string | null;
  reference_id: string | null;
  date: string;
  notes: string | null;
  created_at: string;
}

export interface PaginatedMovementResponse {
  items: MovementItem[];
  total: number;
  skip: number;
  limit: number;
}

export interface ValuationItem {
  material_id: string;
  material_code: string;
  material_name: string;
  default_unit: string;
  current_stock_liquidated: number;
  current_average_cost: number;
  total_value: number;
}

export interface ValuationResponse {
  items: ValuationItem[];
  total_materials: number;
  total_valuation: number;
}
