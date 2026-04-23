import apiClient from "./api";
import type {
  IncreaseCreate,
  DecreaseCreate,
  RecountCreate,
  ZeroOutCreate,
  AnnulAdjustmentRequest,
  InventoryAdjustmentResponse,
  WarehouseTransferCreate,
  WarehouseTransferResponse,
  MaterialTransformationCreate,
  MaterialTransformationResponse,
  AnnulTransformationRequest,
  StockConsolidatedResponse,
  MaterialStockDetailResponse,
  TransitResponse,
  PaginatedMovementResponse,
  ValuationResponse,
} from "@/types/inventory";
import type { PaginatedResponse } from "@/types/common";

interface AdjustmentFilters {
  skip?: number;
  limit?: number;
  material_id?: string;
  adjustment_type?: string;
  status?: string;
  date_from?: string;
  date_to?: string;
}

interface TransformationFilters {
  skip?: number;
  limit?: number;
  source_material_id?: string;
  status?: string;
  date_from?: string;
  date_to?: string;
}

interface MovementFilters {
  skip?: number;
  limit?: number;
  material_id?: string;
  warehouse_id?: string;
  movement_type?: string;
  date_from?: string;
  date_to?: string;
}

// Helper to avoid implicit any
async function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const response = await apiClient.get<T>(url, { params });
  return response.data;
}

async function post<T>(url: string, data?: unknown): Promise<T> {
  const response = await apiClient.post<T>(url, data);
  return response.data;
}

export const inventoryService = {
  // --- Views ---
  getStock: (params?: { active_only?: boolean }) =>
    get<StockConsolidatedResponse>("/api/v1/inventory/stock", params),

  getStockDetail: (materialId: string) =>
    get<MaterialStockDetailResponse>(`/api/v1/inventory/stock/${materialId}`),

  getTransit: () =>
    get<TransitResponse>("/api/v1/inventory/transit"),

  getMovements: (filters: MovementFilters = {}) =>
    get<PaginatedMovementResponse>("/api/v1/inventory/movements", filters as Record<string, unknown>),

  getValuation: (params?: { category_id?: string }) =>
    get<ValuationResponse>("/api/v1/inventory/valuation", params),

  // --- Adjustments ---
  getAdjustments: (filters: AdjustmentFilters = {}) =>
    get<PaginatedResponse<InventoryAdjustmentResponse>>("/api/v1/inventory/adjustments", filters as Record<string, unknown>),

  getAdjustment: (id: string) =>
    get<InventoryAdjustmentResponse>(`/api/v1/inventory/adjustments/${id}`),

  createIncrease: (data: IncreaseCreate) =>
    post<InventoryAdjustmentResponse>("/api/v1/inventory/adjustments/increase", data),

  createDecrease: (data: DecreaseCreate) =>
    post<InventoryAdjustmentResponse>("/api/v1/inventory/adjustments/decrease", data),

  createRecount: (data: RecountCreate) =>
    post<InventoryAdjustmentResponse>("/api/v1/inventory/adjustments/recount", data),

  createZeroOut: (data: ZeroOutCreate) =>
    post<InventoryAdjustmentResponse>("/api/v1/inventory/adjustments/zero-out", data),

  annulAdjustment: (id: string, data: AnnulAdjustmentRequest) =>
    post<InventoryAdjustmentResponse>(`/api/v1/inventory/adjustments/${id}/annul`, data),

  createTransfer: (data: WarehouseTransferCreate) =>
    post<WarehouseTransferResponse>("/api/v1/inventory/adjustments/warehouse-transfer", data),

  // --- Transformations ---
  getTransformations: (filters: TransformationFilters = {}) =>
    get<PaginatedResponse<MaterialTransformationResponse>>("/api/v1/inventory/transformations", filters as Record<string, unknown>),

  getTransformation: (id: string) =>
    get<MaterialTransformationResponse>(`/api/v1/inventory/transformations/${id}`),

  createTransformation: (data: MaterialTransformationCreate) =>
    post<MaterialTransformationResponse>("/api/v1/inventory/transformations", data),

  annulTransformation: (id: string, data: AnnulTransformationRequest) =>
    post<MaterialTransformationResponse>(`/api/v1/inventory/transformations/${id}/annul`, data),
};
