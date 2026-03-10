import type { BaseEntity } from "./common";

export type MoneyMovementType =
  | "payment_to_supplier"
  | "collection_from_client"
  | "expense"
  | "service_income"
  | "transfer_out"
  | "transfer_in"
  | "capital_injection"
  | "capital_return"
  | "commission_payment"
  | "provision_deposit"
  | "provision_expense"
  | "advance_payment"
  | "advance_collection";

export type MovementStatus = "confirmed" | "annulled";

export interface MoneyMovementResponse extends BaseEntity {
  organization_id: string;
  movement_number: number;
  date: string;
  movement_type: MoneyMovementType;
  amount: number;
  description: string;
  account_id: string | null;
  account_name: string | null;
  third_party_id: string | null;
  third_party_name: string | null;
  expense_category_id: string | null;
  expense_category_name: string | null;
  purchase_id: string | null;
  sale_id: string | null;
  transfer_pair_id: string | null;
  reference_number: string | null;
  notes: string | null;
  evidence_url: string | null;
  status: MovementStatus;
  annulled_reason: string | null;
  annulled_at: string | null;
  annulled_by: string | null;
  created_by: string | null;
  is_active: boolean;
}

// --- Create schemas por tipo de movimiento ---

export interface SupplierPaymentCreate {
  supplier_id: string;
  amount: number;
  account_id: string;
  purchase_id?: string | null;
  date: string;
  description?: string | null;
  reference_number?: string | null;
  notes?: string | null;
}

export interface CustomerCollectionCreate {
  customer_id: string;
  amount: number;
  account_id: string;
  sale_id?: string | null;
  date: string;
  description?: string | null;
  reference_number?: string | null;
  notes?: string | null;
}

export interface ExpenseMovementCreate {
  amount: number;
  expense_category_id: string;
  account_id: string;
  description: string;
  date: string;
  third_party_id?: string | null;
  reference_number?: string | null;
  notes?: string | null;
}

export interface ServiceIncomeCreate {
  amount: number;
  account_id: string;
  description: string;
  date: string;
  third_party_id?: string | null;
  reference_number?: string | null;
  notes?: string | null;
}

export interface TransferCreate {
  amount: number;
  source_account_id: string;
  destination_account_id: string;
  date: string;
  description: string;
  reference_number?: string | null;
  notes?: string | null;
}

export interface CapitalInjectionCreate {
  investor_id: string;
  amount: number;
  account_id: string;
  date: string;
  description?: string | null;
  reference_number?: string | null;
  notes?: string | null;
}

export interface CapitalReturnCreate {
  investor_id: string;
  amount: number;
  account_id: string;
  date: string;
  description?: string | null;
  reference_number?: string | null;
  notes?: string | null;
}

export interface CommissionPaymentCreate {
  third_party_id: string;
  amount: number;
  account_id: string;
  date: string;
  description?: string | null;
  reference_number?: string | null;
  notes?: string | null;
}

export interface ProvisionDepositCreate {
  provision_id: string;
  amount: number;
  account_id: string;
  date: string;
  description?: string | null;
  reference_number?: string | null;
  notes?: string | null;
}

export interface ProvisionExpenseCreate {
  provision_id: string;
  amount: number;
  expense_category_id: string;
  date: string;
  description: string;
  reference_number?: string | null;
  notes?: string | null;
}

export interface AdvancePaymentCreate {
  supplier_id: string;
  amount: number;
  account_id: string;
  date: string;
  description?: string | null;
  reference_number?: string | null;
  evidence_url?: string | null;
  notes?: string | null;
}

export interface AdvanceCollectionCreate {
  customer_id: string;
  amount: number;
  account_id: string;
  date: string;
  description?: string | null;
  reference_number?: string | null;
  evidence_url?: string | null;
  notes?: string | null;
}

export interface AnnulMovementRequest {
  reason: string;
}

export interface MoneyMovementWithBalance extends MoneyMovementResponse {
  balance_after: number | null;
}
