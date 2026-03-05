import apiClient from "./api";
import type {
  MoneyMovementResponse,
  SupplierPaymentCreate,
  CustomerCollectionCreate,
  ExpenseMovementCreate,
  ServiceIncomeCreate,
  TransferCreate,
  CapitalInjectionCreate,
  CapitalReturnCreate,
  CommissionPaymentCreate,
  AnnulMovementRequest,
} from "@/types/money-movement";
import type { PaginatedResponse } from "@/types/common";

interface MovementFilters {
  skip?: number;
  limit?: number;
  movement_type?: string;
  account_id?: string;
  third_party_id?: string;
  date_from?: string;
  date_to?: string;
  status?: string;
}

export const moneyMovementService = {
  getAll: async (filters: MovementFilters = {}): Promise<PaginatedResponse<MoneyMovementResponse>> => {
    const response = await apiClient.get<PaginatedResponse<MoneyMovementResponse>>("/api/v1/money-movements", { params: filters });
    return response.data;
  },

  getById: async (id: string): Promise<MoneyMovementResponse> => {
    const response = await apiClient.get<MoneyMovementResponse>(`/api/v1/money-movements/${id}`);
    return response.data;
  },

  createSupplierPayment: async (data: SupplierPaymentCreate): Promise<MoneyMovementResponse> => {
    const response = await apiClient.post<MoneyMovementResponse>("/api/v1/money-movements/supplier-payment", data);
    return response.data;
  },

  createCustomerCollection: async (data: CustomerCollectionCreate): Promise<MoneyMovementResponse> => {
    const response = await apiClient.post<MoneyMovementResponse>("/api/v1/money-movements/customer-collection", data);
    return response.data;
  },

  createExpense: async (data: ExpenseMovementCreate): Promise<MoneyMovementResponse> => {
    const response = await apiClient.post<MoneyMovementResponse>("/api/v1/money-movements/expense", data);
    return response.data;
  },

  createServiceIncome: async (data: ServiceIncomeCreate): Promise<MoneyMovementResponse> => {
    const response = await apiClient.post<MoneyMovementResponse>("/api/v1/money-movements/service-income", data);
    return response.data;
  },

  createTransfer: async (data: TransferCreate): Promise<MoneyMovementResponse> => {
    const response = await apiClient.post<MoneyMovementResponse>("/api/v1/money-movements/transfer", data);
    return response.data;
  },

  createCapitalInjection: async (data: CapitalInjectionCreate): Promise<MoneyMovementResponse> => {
    const response = await apiClient.post<MoneyMovementResponse>("/api/v1/money-movements/capital-injection", data);
    return response.data;
  },

  createCapitalReturn: async (data: CapitalReturnCreate): Promise<MoneyMovementResponse> => {
    const response = await apiClient.post<MoneyMovementResponse>("/api/v1/money-movements/capital-return", data);
    return response.data;
  },

  createCommissionPayment: async (data: CommissionPaymentCreate): Promise<MoneyMovementResponse> => {
    const response = await apiClient.post<MoneyMovementResponse>("/api/v1/money-movements/commission-payment", data);
    return response.data;
  },

  annul: async (id: string, data: AnnulMovementRequest): Promise<MoneyMovementResponse> => {
    const response = await apiClient.post<MoneyMovementResponse>(`/api/v1/money-movements/${id}/annul`, data);
    return response.data;
  },
};
