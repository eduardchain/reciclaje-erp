import type { BaseEntity } from "./common";

// --- Business Units ---

export interface BusinessUnitResponse extends BaseEntity {
  organization_id: string;
  name: string;
  description: string | null;
  is_active: boolean;
}

export interface BusinessUnitCreate {
  name: string;
  description?: string | null;
}

export interface BusinessUnitUpdate {
  name?: string | null;
  description?: string | null;
}

// --- Expense Categories ---

export interface ExpenseCategoryResponse extends BaseEntity {
  organization_id: string;
  name: string;
  description: string | null;
  is_direct_expense: boolean;
  is_active: boolean;
  parent_id: string | null;
  parent_name: string | null;
}

export interface ExpenseCategoryCreate {
  name: string;
  description?: string | null;
  is_direct_expense?: boolean;
  parent_id?: string | null;
}

export interface ExpenseCategoryUpdate {
  name?: string | null;
  description?: string | null;
  is_direct_expense?: boolean | null;
  parent_id?: string | null;
}

export interface ExpenseCategoryFlat {
  id: string;
  name: string;
  display_name: string;
  parent_id: string | null;
  is_direct_expense: boolean;
}

export interface ExpenseCategoryFlatResponse {
  items: ExpenseCategoryFlat[];
}

// --- Price Lists ---

export interface PriceListResponse extends BaseEntity {
  organization_id: string;
  material_id: string;
  purchase_price: number;
  sale_price: number;
  notes: string | null;
  updated_by: string | null;
}

export interface PriceListCreate {
  material_id: string;
  purchase_price?: number;
  sale_price?: number;
  notes?: string | null;
}

export interface CurrentPriceItem {
  material_id: string;
  purchase_price: number;
  sale_price: number;
}

export interface CurrentPricesResponse {
  items: CurrentPriceItem[];
}

export interface PriceListUpdate {
  purchase_price?: number | null;
  sale_price?: number | null;
  notes?: string | null;
}

export interface PriceTableItem {
  material_id: string;
  material_code: string;
  material_name: string;
  category_id: string | null;
  category_name: string | null;
  purchase_price: number | null;
  sale_price: number | null;
  last_updated: string | null;
  updated_by_name: string | null;
}

export interface PriceTableResponse {
  items: PriceTableItem[];
}
