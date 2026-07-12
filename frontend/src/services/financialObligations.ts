import apiClient from "./api";
import type { MoneyMovementResponse } from "@/types/money-movement";
import type {
  AccrueResultResponse,
  FinancialObligationCreate,
  FinancialObligationResponse,
  ObligationMovementCreate,
  ObligationSummaryResponse,
  PendingAccrualsResponse,
} from "@/types/financial-obligation";

const BASE = "/api/v1/financial-obligations";

interface ObligationFilters {
  direction?: string;
  status?: string;
}

export const financialObligationService = {
  getAll: async (filters: ObligationFilters = {}): Promise<FinancialObligationResponse[]> => {
    const response = await apiClient.get<FinancialObligationResponse[]>(`${BASE}/`, { params: filters });
    return response.data;
  },

  getById: async (id: string): Promise<FinancialObligationResponse> => {
    const response = await apiClient.get<FinancialObligationResponse>(`${BASE}/${id}`);
    return response.data;
  },

  getStatement: async (id: string): Promise<MoneyMovementResponse[]> => {
    const response = await apiClient.get<MoneyMovementResponse[]>(`${BASE}/${id}/statement`);
    return response.data;
  },

  getSummary: async (): Promise<ObligationSummaryResponse> => {
    const response = await apiClient.get<ObligationSummaryResponse>(`${BASE}/summary`);
    return response.data;
  },

  getPendingAccruals: async (): Promise<PendingAccrualsResponse> => {
    const response = await apiClient.get<PendingAccrualsResponse>(`${BASE}/pending-accruals`);
    return response.data;
  },

  create: async (data: FinancialObligationCreate): Promise<FinancialObligationResponse> => {
    const response = await apiClient.post<FinancialObligationResponse>(`${BASE}/`, data);
    return response.data;
  },

  accruePending: async (expenseCategoryId?: string): Promise<AccrueResultResponse> => {
    const body = expenseCategoryId ? { expense_category_id: expenseCategoryId } : {};
    const response = await apiClient.post<AccrueResultResponse>(`${BASE}/accrue-pending`, body);
    return response.data;
  },

  capitalPayment: async (id: string, data: ObligationMovementCreate): Promise<MoneyMovementResponse> => {
    const response = await apiClient.post<MoneyMovementResponse>(`${BASE}/${id}/capital-payment`, data);
    return response.data;
  },

  interestPayment: async (id: string, data: ObligationMovementCreate): Promise<MoneyMovementResponse> => {
    const response = await apiClient.post<MoneyMovementResponse>(`${BASE}/${id}/interest-payment`, data);
    return response.data;
  },

  additionalDisbursement: async (id: string, data: ObligationMovementCreate): Promise<MoneyMovementResponse> => {
    const response = await apiClient.post<MoneyMovementResponse>(`${BASE}/${id}/disbursement`, data);
    return response.data;
  },

  settle: async (id: string): Promise<FinancialObligationResponse> => {
    const response = await apiClient.post<FinancialObligationResponse>(`${BASE}/${id}/settle`);
    return response.data;
  },

  annulMovement: async (movementId: string, reason: string): Promise<MoneyMovementResponse> => {
    const response = await apiClient.post<MoneyMovementResponse>(`${BASE}/movements/${movementId}/annul`, { reason });
    return response.data;
  },
};
