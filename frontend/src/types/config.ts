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
}

export interface ExpenseCategoryCreate {
  name: string;
  description?: string | null;
  is_direct_expense: boolean;
}

export interface ExpenseCategoryUpdate {
  name?: string | null;
  description?: string | null;
  is_direct_expense?: boolean | null;
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

export interface PriceListUpdate {
  purchase_price?: number | null;
  sale_price?: number | null;
  notes?: string | null;
}
