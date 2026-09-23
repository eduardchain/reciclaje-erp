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

// --- Retenciones: catalogo v2 (CC-006) + entidades (SAC E2 D9) --- //

export type RetentionConfigType = "retefuente" | "reteiva" | "ica";

// Fila del GET unificado: config (tarifa) y/o entidad (saldo).
// entity_id null = config sin uso aun (sin Pagar/Estado);
// config_id null = entidad sin tarifa configurada (sin precalculo).
export interface RetentionRow {
  config_id: string | null;
  entity_id: string | null;
  retention_type: RetentionConfigType;
  municipality: string | null;
  concept: string | null;
  rate_pct: number | null;
  /** CC-013 D5: `subtotal` | `iva` — sobre que se aplica la tasa. */
  base_kind: string | null;
  name: string | null;
  current_balance: number;
  is_active: boolean;
}

export type RetentionBaseKind = "subtotal" | "iva";

export interface RetentionConfigCreate {
  retention_type: RetentionConfigType;
  municipality?: string; // obligatorio si ica
  concept?: string; // opcional (F3: ReteFuente compras vs servicios...)
  rate_pct: number;
  /** CC-013 D5. Ausente = `subtotal`, que es lo que hacen hoy las dos
   * pantallas de compras: por eso compras queda byte a byte. */
  base_kind?: RetentionBaseKind;
}

export interface RetentionConfigUpdate {
  rate_pct?: number;
  base_kind?: RetentionBaseKind;
  is_active?: boolean;
}
