import type { BaseEntity } from "./common";

export interface WarehouseResponse extends BaseEntity {
  organization_id: string;
  name: string;
  description: string | null;
  address: string | null;
  is_active: boolean;
  /** SAC Q-12: recibe material de terceros (false = interna: molino/transito) */
  is_receiving: boolean;
  /** SAC E3.1: bodega virtual de transito intersede (solo opera via traslados 2 pasos) */
  is_transit: boolean;
  /** SAC E3.1: sede fisica destino a la que rutea esta bodega de transito */
  transit_target_warehouse_id?: string | null;
}

export interface WarehouseCreate {
  name: string;
  description?: string | null;
  address?: string | null;
  is_receiving?: boolean;
  is_transit?: boolean;
  transit_target_warehouse_id?: string | null;
}

export interface WarehouseUpdate {
  name?: string | null;
  description?: string | null;
  address?: string | null;
  is_receiving?: boolean;
  is_transit?: boolean;
  transit_target_warehouse_id?: string | null;
}
