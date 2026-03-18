export type ScheduledExpenseStatus = "active" | "completed" | "cancelled";

export interface ScheduledExpenseApplicationResponse {
  id: string;
  application_number: number;
  amount: number;
  money_movement_id: string;
  applied_at: string;
  applied_by: string | null;
}

export interface ScheduledExpenseResponse {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  total_amount: number;
  monthly_amount: number;
  total_months: number;
  applied_months: number;
  source_account_id: string;
  source_account_name: string | null;
  prepaid_third_party_id: string;
  prepaid_third_party_name: string | null;
  expense_category_id: string;
  expense_category_name: string | null;
  funding_movement_id: string | null;
  start_date: string;
  apply_day: number;
  next_application_date: string | null;
  status: ScheduledExpenseStatus;
  created_by: string | null;
  cancelled_at: string | null;
  cancelled_by: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  remaining_amount: number;
  next_amount: number;
  prepaid_balance: number;
  applications: ScheduledExpenseApplicationResponse[];
}

export interface ScheduledExpenseCreate {
  name: string;
  total_amount: number;
  total_months: number;
  source_account_id: string;
  expense_category_id: string;
  start_date: string;
  apply_day?: number;
  description?: string | null;
  business_unit_id?: string;
  applicable_business_unit_ids?: string[];
}
