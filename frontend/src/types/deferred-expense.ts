import type { BaseEntity } from "./common";

export type DeferredExpenseStatus = "active" | "completed" | "cancelled";
export type DeferredExpenseType = "expense" | "provision_expense";

export interface DeferredApplicationResponse {
  id: string;
  application_number: number;
  amount: number;
  money_movement_id: string;
  applied_at: string;
  applied_by: string | null;
}

export interface DeferredExpenseResponse extends BaseEntity {
  organization_id: string;
  name: string;
  total_amount: number;
  monthly_amount: number;
  total_months: number;
  applied_months: number;
  expense_category_id: string;
  expense_category_name: string | null;
  expense_type: DeferredExpenseType;
  account_id: string | null;
  account_name: string | null;
  provision_id: string | null;
  provision_name: string | null;
  description: string | null;
  start_date: string;
  status: DeferredExpenseStatus;
  cancelled_at: string | null;
  cancelled_by: string | null;
  created_by: string | null;
  is_active: boolean;
  remaining_amount: number;
  next_amount: number;
  applications: DeferredApplicationResponse[];
}

export interface DeferredExpenseCreate {
  name: string;
  total_amount: number;
  total_months: number;
  expense_category_id: string;
  expense_type: DeferredExpenseType;
  account_id?: string | null;
  provision_id?: string | null;
  description?: string | null;
  start_date: string;
}
