import type { BaseEntity } from "./common";

export interface ThirdPartyCategory {
  id: string;
  name: string;
  display_name: string;
  behavior_type: string;
}

export interface ThirdPartyResponse extends BaseEntity {
  organization_id: string;
  name: string;
  identification_number: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  is_system_entity: boolean;
  initial_balance: number;
  current_balance: number;
  is_active: boolean;
  categories: ThirdPartyCategory[];
}

export interface ThirdPartyCreate {
  name: string;
  identification_number?: string | null;
  email?: string | null;
  phone?: string | null;
  address?: string | null;
  category_ids?: string[];
  initial_balance?: number;
}

export interface ThirdPartyUpdate {
  name?: string | null;
  identification_number?: string | null;
  email?: string | null;
  phone?: string | null;
  address?: string | null;
  category_ids?: string[];
}
