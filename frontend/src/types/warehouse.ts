import type { BaseEntity } from "./common";

export interface WarehouseResponse extends BaseEntity {
  organization_id: string;
  name: string;
  description: string | null;
  address: string | null;
  is_active: boolean;
  /** SAC Q-12: recibe material de terceros (false = interna: molino/transito) */
  is_receiving: boolean;
}

export interface WarehouseCreate {
  name: string;
  description?: string | null;
  address?: string | null;
  is_receiving?: boolean;
}

export interface WarehouseUpdate {
  name?: string | null;
  description?: string | null;
  address?: string | null;
  is_receiving?: boolean;
}
