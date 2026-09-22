import apiClient from "./api";
import { num } from "@/types/willard-delivery";
import type {
  DriverCreate,
  DriverResponse,
  DriverUpdate,
  FleetListResponse,
  MaterialConversionFormulaCreate,
  MaterialConversionFormulaListResponse,
  MaterialConversionFormulaResponse,
  MaterialKgProfileListResponse,
  MaterialKgProfileResponse,
  MaterialKgProfileUpsert,
  LeadMarketPriceCreate,
  LeadMarketPriceListResponse,
  LeadMarketPriceResponse,
  ServiceTariffCreate,
  ServiceTariffListResponse,
  ServiceTariffResponse,
  VehicleCreate,
  VehicleResponse,
  VehicleUpdate,
} from "@/types/sac-config";

// Configuracion SAC E1: tarifas y formulas son APPEND-ONLY (sin update/delete
// — corregir = crear nueva version); flota es CRUD estandar con soft delete.

function coerceLeadPrice(p: LeadMarketPriceResponse): LeadMarketPriceResponse {
  return { ...p, price_per_kg: num(p.price_per_kg) };
}

export const sacConfigService = {
  // --- Tarifas ---
  getTariffs: async (tariffCode?: string): Promise<ServiceTariffListResponse> => {
    const response = await apiClient.get<ServiceTariffListResponse>(
      "/api/v1/service-tariffs",
      { params: tariffCode ? { tariff_code: tariffCode } : {} }
    );
    return response.data;
  },

  getCurrentTariffs: async (): Promise<ServiceTariffListResponse> => {
    const response = await apiClient.get<ServiceTariffListResponse>(
      "/api/v1/service-tariffs/current"
    );
    return response.data;
  },

  createTariff: async (data: ServiceTariffCreate): Promise<ServiceTariffResponse> => {
    const response = await apiClient.post<ServiceTariffResponse>(
      "/api/v1/service-tariffs",
      data
    );
    return response.data;
  },

  // --- CC-014: precio de mercado del plomo ---
  // ⚠️ El backend serializa Decimal como STRING. El tipo dice number, asi que
  // se coerciona aqui, en la FRONTERA del servicio, y no en la pantalla: sin
  // esto `acc + x` concatena texto y el total sale "NaN" o pegado (#93/#107).
  getLeadPrices: async (): Promise<LeadMarketPriceListResponse> => {
    const response = await apiClient.get<LeadMarketPriceListResponse>(
      "/api/v1/lead-market-prices"
    );
    return {
      ...response.data,
      items: (response.data.items ?? []).map(coerceLeadPrice),
    };
  },

  getCurrentLeadPrice: async (): Promise<LeadMarketPriceResponse | null> => {
    const response = await apiClient.get<LeadMarketPriceResponse | null>(
      "/api/v1/lead-market-prices/current"
    );
    return response.data ? coerceLeadPrice(response.data) : null;
  },

  createLeadPrice: async (data: LeadMarketPriceCreate): Promise<LeadMarketPriceResponse> => {
    const response = await apiClient.post<LeadMarketPriceResponse>(
      "/api/v1/lead-market-prices",
      data
    );
    return coerceLeadPrice(response.data);
  },

  annulLeadPrice: async (id: string, reason: string): Promise<LeadMarketPriceResponse> => {
    const response = await apiClient.post<LeadMarketPriceResponse>(
      `/api/v1/lead-market-prices/${id}/annul`,
      { reason }
    );
    return coerceLeadPrice(response.data);
  },

  // --- Formulas de conversion ---
  getFormulas: async (filters?: {
    material_id?: string;
    formula_type?: string;
  }): Promise<MaterialConversionFormulaListResponse> => {
    const response = await apiClient.get<MaterialConversionFormulaListResponse>(
      "/api/v1/material-conversion-formulas",
      { params: filters ?? {} }
    );
    return response.data;
  },

  getCurrentFormulas: async (
    materialId?: string
  ): Promise<MaterialConversionFormulaListResponse> => {
    const response = await apiClient.get<MaterialConversionFormulaListResponse>(
      "/api/v1/material-conversion-formulas/current",
      { params: materialId ? { material_id: materialId } : {} }
    );
    return response.data;
  },

  createFormula: async (
    data: MaterialConversionFormulaCreate
  ): Promise<MaterialConversionFormulaResponse> => {
    const response = await apiClient.post<MaterialConversionFormulaResponse>(
      "/api/v1/material-conversion-formulas",
      data
    );
    return response.data;
  },

  // --- Clasificacion Willard del material (material_kg_profile, CC-005) ---
  getKgProfiles: async (filters?: {
    compra_regular?: boolean;
    willard_world?: string;
  }): Promise<MaterialKgProfileListResponse> => {
    const response = await apiClient.get<MaterialKgProfileListResponse>(
      "/api/v1/material-kg-profiles",
      { params: filters ?? {} }
    );
    return response.data;
  },

  upsertKgProfile: async (
    materialId: string,
    data: MaterialKgProfileUpsert
  ): Promise<MaterialKgProfileResponse> => {
    const response = await apiClient.put<MaterialKgProfileResponse>(
      `/api/v1/material-kg-profiles/${materialId}`,
      data
    );
    return response.data;
  },

  // --- Flota ---
  getDrivers: async (includeInactive = false): Promise<FleetListResponse<DriverResponse>> => {
    const response = await apiClient.get<FleetListResponse<DriverResponse>>(
      "/api/v1/drivers",
      { params: { limit: 500, include_inactive: includeInactive } }
    );
    return response.data;
  },

  createDriver: async (data: DriverCreate): Promise<DriverResponse> => {
    const response = await apiClient.post<DriverResponse>("/api/v1/drivers", data);
    return response.data;
  },

  updateDriver: async (id: string, data: DriverUpdate): Promise<DriverResponse> => {
    const response = await apiClient.patch<DriverResponse>(`/api/v1/drivers/${id}`, data);
    return response.data;
  },

  getVehicles: async (includeInactive = false): Promise<FleetListResponse<VehicleResponse>> => {
    const response = await apiClient.get<FleetListResponse<VehicleResponse>>(
      "/api/v1/vehicles",
      { params: { limit: 500, include_inactive: includeInactive } }
    );
    return response.data;
  },

  createVehicle: async (data: VehicleCreate): Promise<VehicleResponse> => {
    const response = await apiClient.post<VehicleResponse>("/api/v1/vehicles", data);
    return response.data;
  },

  updateVehicle: async (id: string, data: VehicleUpdate): Promise<VehicleResponse> => {
    const response = await apiClient.patch<VehicleResponse>(`/api/v1/vehicles/${id}`, data);
    return response.data;
  },
};
