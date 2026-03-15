import type { BaseEntity } from "./common";

export interface ThirdPartyResponse extends BaseEntity {
  organization_id: string;
  name: string;
  identification_number: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  is_supplier: boolean;
  is_customer: boolean;
  is_investor: boolean;
  is_provision: boolean;
  is_liability: boolean;
  is_system_entity: boolean;
  investor_type: string | null;
  initial_balance: number;
  current_balance: number;
  is_active: boolean;
}

export interface ThirdPartyCreate {
  name: string;
  identification_number?: string | null;
  email?: string | null;
  phone?: string | null;
  address?: string | null;
  is_supplier?: boolean;
  is_customer?: boolean;
  is_investor?: boolean;
  is_provision?: boolean;
  is_liability?: boolean;
  investor_type?: string | null;
  initial_balance?: number;
}

export interface ThirdPartyUpdate {
  name?: string | null;
  identification_number?: string | null;
  email?: string | null;
  phone?: string | null;
  address?: string | null;
  is_supplier?: boolean | null;
  is_customer?: boolean | null;
  is_investor?: boolean | null;
  is_provision?: boolean | null;
  is_liability?: boolean | null;
  investor_type?: string | null;
}
