import type { BaseEntity } from "./common";

export interface MaterialCategoryResponse extends BaseEntity {
  organization_id: string;
  name: string;
  description: string | null;
  is_active: boolean;
}

export interface MaterialCategoryCreate {
  name: string;
  description?: string | null;
}

export interface MaterialCategoryUpdate {
  name?: string | null;
  description?: string | null;
}

export interface MaterialResponse extends BaseEntity {
  organization_id: string;
  code: string;
  name: string;
  description: string | null;
  category_id: string;
  business_unit_id: string;
  default_unit: string;
  current_stock: number;
  current_stock_liquidated: number;
  current_stock_transit: number;
  current_average_cost: number;
  sort_order: number;
  is_active: boolean;
}

export interface MaterialCreate {
  code: string;
  name: string;
  description?: string | null;
  category_id: string;
  business_unit_id: string;
  default_unit: string;
}

export interface MaterialUpdate {
  code?: string | null;
  name?: string | null;
  description?: string | null;
  category_id?: string | null;
  business_unit_id?: string | null;
  default_unit?: string | null;
}
