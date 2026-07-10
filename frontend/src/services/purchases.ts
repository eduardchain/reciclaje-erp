import apiClient from "./api";
import type {
  PurchaseResponse,
  PurchaseCreate,
  PurchaseFullUpdate,
  PurchaseLiquidateRequest,
  PaginatedPurchaseResponse,
} from "@/types/purchase";

interface PurchaseFilters {
  skip?: number;
  limit?: number;
  status?: string;
  supplier_id?: string;
  date_from?: string;
  date_to?: string;
  search?: string;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
}

export const purchaseService = {
  getAll: async (filters: PurchaseFilters = {}): Promise<PaginatedPurchaseResponse> => {
    const params: Record<string, unknown> = { ...filters };
    if (!params.sort_by) delete params.sort_by;
    if (!params.sort_dir) delete params.sort_dir;
    const response = await apiClient.get<PaginatedPurchaseResponse>("/api/v1/purchases", { params });
    return response.data;
  },

  getById: async (id: string): Promise<PurchaseResponse> => {
    const response = await apiClient.get<PurchaseResponse>(`/api/v1/purchases/${id}`);
    return response.data;
  },

  checkDuplicate: async (supplierId: string, date: string, totalQuantity?: number): Promise<{ count: number }> => {
    const response = await apiClient.get<{ count: number }>("/api/v1/purchases/check-duplicate", {
      params: { supplier_id: supplierId, date, total_quantity: totalQuantity },
    });
    return response.data;
  },

  checkInvoice: async (invoiceNumber: string, excludeId?: string): Promise<{ matches: Array<{ id: string; number: number; date: string; status: string; third_party_name: string; total_amount: number }> }> => {
    const response = await apiClient.get("/api/v1/purchases/check-invoice", {
      params: { invoice_number: invoiceNumber, exclude_id: excludeId },
    });
    return response.data;
  },

  create: async (data: PurchaseCreate): Promise<PurchaseResponse> => {
    const response = await apiClient.post<PurchaseResponse>("/api/v1/purchases", data);
    return response.data;
  },

  liquidate: async (id: string, data: PurchaseLiquidateRequest): Promise<PurchaseResponse> => {
    const response = await apiClient.patch<PurchaseResponse>(`/api/v1/purchases/${id}/liquidate`, data);
    return response.data;
  },

  update: async (id: string, data: PurchaseFullUpdate): Promise<PurchaseResponse> => {
    const response = await apiClient.patch<PurchaseResponse>(`/api/v1/purchases/${id}`, data);
    return response.data;
  },

  cancel: async (id: string, annulLinkedPayments = false): Promise<PurchaseResponse> => {
    const response = await apiClient.patch<PurchaseResponse>(
      `/api/v1/purchases/${id}/cancel`,
      undefined,
      { params: { annul_linked_payments: annulLinkedPayments } },
    );
    return response.data;
  },
};
