import apiClient from "./api";
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
  ServiceTariffCreate,
  ServiceTariffListResponse,
  ServiceTariffResponse,
  VehicleCreate,
  VehicleResponse,
  VehicleUpdate,
} from "@/types/sac-config";

// Configuracion SAC E1: tarifas y formulas son APPEND-ONLY (sin update/delete
// — corregir = crear nueva version); flota es CRUD estandar con soft delete.

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
