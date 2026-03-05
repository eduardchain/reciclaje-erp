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
}
