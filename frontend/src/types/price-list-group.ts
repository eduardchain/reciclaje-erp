/**
 * Listas de precios por proveedor (SAC).
 *
 * Una lista trae TODOS los materiales y el usuario decide a cuales les pone
 * precio (Hugo, Q-21). Un material en cero es una decision deliberada: el
 * sistema NO cae a la lista general para rellenarlo.
 */

export interface PriceListGroupResponse {
  id: string;
  organization_id: string;
  name: string;
  is_active: boolean;
  member_count: number;
  priced_material_count: number;
  created_at: string;
  updated_at: string;
}

export interface PriceListGroupsResponse {
  items: PriceListGroupResponse[];
}

export interface PriceListGroupCreate {
  name: string;
  /** Copia los precios vigentes de la lista general como punto de partida (Q-26). */
  seed_from_general?: boolean;
  /** Asigna los proveedores que hoy no pertenecen a ninguna lista. NO roba de otras. */
  assign_all_suppliers?: boolean;
}

export interface PriceListGroupUpdate {
  name?: string;
  is_active?: boolean;
}

export interface SupplierMembershipItem {
  third_party_id: string;
  third_party_name: string;
  /** La lista a la que pertenece HOY — para avisar el conflicto ANTES de guardar. */
  current_group_id: string | null;
  current_group_name: string | null;
}

export interface SupplierMembershipsResponse {
  items: SupplierMembershipItem[];
}

export interface SeedResultResponse {
  group: PriceListGroupResponse;
  seeded_prices: number;
  assigned_suppliers: number;
  skipped_suppliers: number;
}
