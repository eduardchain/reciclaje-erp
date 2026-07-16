// Tipos de configuracion SAC E1: tarifas, formulas de conversion, flota
// (espejo de backend/app/schemas/{service_tariff,material_conversion_formula,fleet}.py)

export type TariffCode =
  | "maquila_willard"
  | "maquila_intersede_cv_jm"
  | "maquila_crisol"
  | "flete_willard_bog_baq"
  | "flete_willard_planta_planta";

export type TariffUnit = "per_kg_lead" | "per_kg_battery" | "per_unit";

export const TARIFF_CODE_LABELS: Record<TariffCode, string> = {
  maquila_willard: "Maquila Willard",
  maquila_intersede_cv_jm: "Maquila Intersede CV→JM",
  maquila_crisol: "Maquila Crisol",
  flete_willard_bog_baq: "Flete Willard BOG→BAQ",
  flete_willard_planta_planta: "Flete Willard Planta→Planta",
};

export const TARIFF_UNIT_LABELS: Record<TariffUnit, string> = {
  per_kg_lead: "por kg de plomo",
  per_kg_battery: "por kg de bateria",
  per_unit: "por unidad",
};

// D11a — espejo de CANONICAL_UNIT_BY_CODE del backend (la UI preselecciona
// la unidad, el backend valida coherencia con 422)
export const CANONICAL_UNIT_BY_CODE: Record<TariffCode, TariffUnit> = {
  maquila_willard: "per_kg_lead",
  maquila_intersede_cv_jm: "per_kg_lead",
  maquila_crisol: "per_kg_lead",
  flete_willard_bog_baq: "per_kg_battery",
  flete_willard_planta_planta: "per_kg_lead",
};

export interface ServiceTariffResponse {
  id: string;
  organization_id: string;
  tariff_code: TariffCode;
  unit_price_cop: number | string;
  unit: TariffUnit;
  notes: string | null;
  created_by: string;
  created_by_name: string | null;
  created_at: string;
}

export interface ServiceTariffCreate {
  tariff_code: TariffCode;
  unit_price_cop: number;
  unit: TariffUnit;
  notes?: string | null;
}

export interface ServiceTariffListResponse {
  items: ServiceTariffResponse[];
  total: number;
}

// --- Formulas de conversion ---

export type FormulaType =
  | "battery_to_lead"
  | "drosses_to_lead"
  | "scrap_with_terminal_to_lead";

export type WillardSubtype = "escurrido" | "pinza";

export const FORMULA_TYPE_LABELS: Record<FormulaType, string> = {
  battery_to_lead: "Bateria → plomo (kg/unidad)",
  drosses_to_lead: "Dross → plomo (% de plomo)",
  scrap_with_terminal_to_lead: "Scrap con borne → plomo",
};

export interface MaterialConversionFormulaResponse {
  id: string;
  organization_id: string;
  material_id: string;
  material_code: string | null;
  material_name: string | null;
  material_unit: string | null;
  formula_type: FormulaType;
  parameters: Record<string, unknown>;
  willard_account_subtype: WillardSubtype | null;
  notes: string | null;
  created_by: string;
  created_by_name: string | null;
  created_at: string;
}

export interface MaterialConversionFormulaCreate {
  material_id: string;
  formula_type: FormulaType;
  parameters: Record<string, unknown>;
  willard_account_subtype?: WillardSubtype | null;
  notes?: string | null;
}

export interface MaterialConversionFormulaListResponse {
  items: MaterialConversionFormulaResponse[];
  total: number;
}

// --- Flota ---

export type VehicleType = "camion" | "montacargas" | "otro";

export const VEHICLE_TYPE_LABELS: Record<VehicleType, string> = {
  camion: "Camion",
  montacargas: "Montacargas",
  otro: "Otro",
};

export interface DriverResponse {
  id: string;
  organization_id: string;
  name: string;
  document_id: string | null;
  phone: string | null;
  is_active: boolean;
  created_at: string;
}

export interface DriverCreate {
  name: string;
  document_id?: string | null;
  phone?: string | null;
}

export interface DriverUpdate {
  name?: string;
  document_id?: string | null;
  phone?: string | null;
  is_active?: boolean;
}

export interface VehicleResponse {
  id: string;
  organization_id: string;
  plate: string;
  display_name: string | null;
  vehicle_type: VehicleType | null;
  is_active: boolean;
  created_at: string;
}

export interface VehicleCreate {
  plate: string;
  display_name?: string | null;
  vehicle_type?: VehicleType | null;
}

export interface VehicleUpdate {
  plate?: string;
  display_name?: string | null;
  vehicle_type?: VehicleType | null;
  is_active?: boolean;
}

export interface FleetListResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}
