import apiClient from "./api";
import type { SaleResponse, SaleCreate, SaleFullUpdate, SaleLiquidateRequest, PaginatedSaleResponse } from "@/types/sale";

interface SaleFilters {
  skip?: number;
  limit?: number;
  status?: string;
  customer_id?: string;
  date_from?: string;
  date_to?: string;
  search?: string;
  dp_filter?: "all" | "exclude" | "only";
  date_field?: "date" | "liquidated_at";
  sort_by?: string;
  sort_dir?: "asc" | "desc";
}

export const saleService = {
  getAll: async (filters: SaleFilters = {}): Promise<PaginatedSaleResponse> => {
    const params: Record<string, unknown> = { ...filters };
    if (!params.sort_by) delete params.sort_by;
    if (!params.sort_dir) delete params.sort_dir;
    const response = await apiClient.get<PaginatedSaleResponse>("/api/v1/sales", { params });
    return response.data;
  },

  getById: async (id: string): Promise<SaleResponse> => {
    const response = await apiClient.get<SaleResponse>(`/api/v1/sales/${id}`);
    return response.data;
  },

  create: async (data: SaleCreate): Promise<SaleResponse> => {
    const response = await apiClient.post<SaleResponse>("/api/v1/sales", data);
    return response.data;
  },

  update: async (id: string, data: SaleFullUpdate): Promise<SaleResponse> => {
    const response = await apiClient.patch<SaleResponse>(`/api/v1/sales/${id}`, data);
    return response.data;
  },

  liquidate: async (id: string, data: SaleLiquidateRequest): Promise<SaleResponse> => {
    const response = await apiClient.patch<SaleResponse>(`/api/v1/sales/${id}/liquidate`, data);
    return response.data;
  },

  cancel: async (id: string, annulLinkedPayments = false): Promise<SaleResponse> => {
    const response = await apiClient.patch<SaleResponse>(
      `/api/v1/sales/${id}/cancel`,
      undefined,
      { params: { annul_linked_payments: annulLinkedPayments } },
    );
    return response.data;
  },

  checkDuplicate: async (customerId: string, date: string): Promise<{ count: number }> => {
    const response = await apiClient.get<{ count: number }>("/api/v1/sales/check-duplicate", {
      params: { customer_id: customerId, date },
    });
    return response.data;
  },

  checkInvoice: async (invoiceNumber: string, excludeId?: string): Promise<{ matches: Array<{ id: string; number: number; date: string; status: string; third_party_name: string; total_amount: number }> }> => {
    const response = await apiClient.get("/api/v1/sales/check-invoice", {
      params: { invoice_number: invoiceNumber, exclude_id: excludeId },
    });
    return response.data;
  },
};
