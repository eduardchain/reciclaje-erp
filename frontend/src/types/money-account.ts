import type { BaseEntity } from "./common";

export type MoneyAccountType = "cash" | "bank" | "digital";

export interface MoneyAccountResponse extends BaseEntity {
  organization_id: string;
  name: string;
  account_type: MoneyAccountType;
  account_number: string | null;
  bank_name: string | null;
  current_balance: number;
  is_active: boolean;
}

export interface MoneyAccountCreate {
  name: string;
  account_type: MoneyAccountType;
  account_number?: string | null;
  bank_name?: string | null;
  initial_balance?: number;
}

export interface MoneyAccountUpdate {
  name?: string | null;
  account_type?: MoneyAccountType | null;
  account_number?: string | null;
  bank_name?: string | null;
}
