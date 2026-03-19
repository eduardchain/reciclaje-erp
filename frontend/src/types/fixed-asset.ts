export type FixedAssetStatus = "active" | "fully_depreciated" | "disposed" | "cancelled";

export interface AssetDepreciation {
  id: string;
  depreciation_number: number;
  period: string;
  amount: number;
  accumulated_after: number;
  current_value_after: number;
  money_movement_id: string;
  applied_at: string;
  applied_by: string | null;
}

export interface FixedAsset {
  id: string;
  organization_id: string;
  name: string;
  asset_code: string | null;
  notes: string | null;
  purchase_date: string;
  depreciation_start_date: string;
  purchase_value: number;
  salvage_value: number;
  current_value: number;
  accumulated_depreciation: number;
  depreciation_rate: number;
  monthly_depreciation: number;
  useful_life_months: number;
  expense_category_id: string;
  expense_category_name: string | null;
  third_party_id: string | null;
  third_party_name: string | null;
  purchase_movement_id: string | null;
  status: FixedAssetStatus;
  disposed_at: string | null;
  disposed_by: string | null;
  disposal_reason: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  remaining_months: number;
  depreciation_progress: number;
  depreciations: AssetDepreciation[];
}

export interface FixedAssetCreate {
  name: string;
  asset_code?: string | null;
  purchase_date: string;
  purchase_value: number;
  salvage_value?: number;
  depreciation_rate: number;
  depreciation_start_date: string;
  expense_category_id: string;
  source_account_id?: string | null;
  supplier_id?: string | null;
  notes?: string | null;
  business_unit_id?: string | null;
  applicable_business_unit_ids?: string[] | null;
}

export interface FixedAssetUpdate {
  name?: string;
  asset_code?: string | null;
  notes?: string | null;
  purchase_value?: number;
  salvage_value?: number;
  depreciation_rate?: number;
  expense_category_id?: string;
}

export interface ApplyPendingResult {
  asset_id: string;
  asset_name: string;
  amount: number;
  new_status: string;
}
