// Tipos KgLedger — cuentas en kilogramos de plomo (SAC E2)
// Espejo de backend/app/schemas/kg_ledger.py

export type KgAccountType =
  | "willard_baterias"
  | "willard_drosses"
  | "intersede"
  | "intra_horno"
  | "crisol";

export type KgMovementStatus = "confirmed" | "annulled";

export const KG_ACCOUNT_TYPE_LABELS: Record<KgAccountType, string> = {
  willard_baterias: "Willard Baterías",
  willard_drosses: "Willard Drosses",
  intersede: "Intersede",
  intra_horno: "Horno",
  crisol: "Crisol",
};

// Coherencia tipo↔FKs — espejo de services/kg_ledger.py (el backend valida con 422)
export const KG_WILLARD_TYPES: KgAccountType[] = ["willard_baterias", "willard_drosses"];
export const KG_WAREHOUSE_REQUIRED_TYPES: KgAccountType[] = [
  "willard_baterias",
  "intra_horno",
  "crisol",
];

export const KG_SOURCE_TYPE_LABELS: Record<string, string> = {
  manual_adjustment: "Ajuste manual",
  postconsumo_receipt: "Recepción postconsumo",
  drosses_receipt: "Recepción drosses",
  migration_initial_load: "Carga inicial migración",
};

export interface KgLedgerAccountResponse {
  id: string;
  code: string;
  display_name: string;
  account_type: KgAccountType;
  warehouse_id: string | null;
  warehouse_name: string | null;
  third_party_id: string | null;
  third_party_name: string | null;
  tolerance_kg: number | null;
  current_balance_kg: number;
  is_active: boolean;
  created_at: string;
}

export interface KgLedgerAccountCreate {
  code: string;
  display_name: string;
  account_type: KgAccountType;
  warehouse_id?: string | null;
  third_party_id?: string | null;
  tolerance_kg?: number | null;
}

export interface KgLedgerAccountUpdate {
  display_name?: string;
  tolerance_kg?: number;
  is_active?: boolean;
}

export interface KgLedgerMovementManualCreate {
  account_id: string;
  delta_kg: number;
  transaction_date: string;
  description: string;
  reason: string;
}

export interface KgLedgerMovementResponse {
  id: string;
  account_id: string;
  delta_kg: number;
  transaction_date: string;
  description: string | null;
  source_type: string;
  source_id: string | null;
  inventory_movement_id: string | null;
  conversion_formula_snapshot: Record<string, unknown> | null;
  status: KgMovementStatus;
  annulled_reason: string | null;
  annulled_at: string | null;
  created_at: string;
}

export interface KgLedgerStatementRow extends KgLedgerMovementResponse {
  balance_after_kg: number;
}

export interface KgLedgerStatementResponse {
  account: KgLedgerAccountResponse;
  opening_balance_kg: number;
  movements: KgLedgerStatementRow[];
  current_balance_kg: number;
}

export interface KgLedgerSummaryAccount {
  account_id: string;
  code: string;
  display_name: string;
  account_type: KgAccountType;
  warehouse_id: string | null;
  warehouse_name: string | null;
  balance_kg: number;
  tolerance_kg: number | null;
  last_movement_at: string | null;
  is_active: boolean;
}

export interface KgLedgerSummaryResponse {
  accounts: KgLedgerSummaryAccount[];
  total_willard_kg: number;
  total_intersede_kg: number;
  total_intra_horno_kg: number;
  total_crisol_kg: number;
}
