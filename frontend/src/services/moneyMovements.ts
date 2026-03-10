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
  ProvisionDepositCreate,
  ProvisionExpenseCreate,
  AdvancePaymentCreate,
  AdvanceCollectionCreate,
  AssetPaymentCreate,
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

  createProvisionDeposit: async (data: ProvisionDepositCreate): Promise<MoneyMovementResponse> => {
    const response = await apiClient.post<MoneyMovementResponse>("/api/v1/money-movements/provision-deposit", data);
    return response.data;
  },

  createProvisionExpense: async (data: ProvisionExpenseCreate): Promise<MoneyMovementResponse> => {
    const response = await apiClient.post<MoneyMovementResponse>("/api/v1/money-movements/provision-expense", data);
    return response.data;
  },

  createAdvancePayment: async (data: AdvancePaymentCreate): Promise<MoneyMovementResponse> => {
    const response = await apiClient.post<MoneyMovementResponse>("/api/v1/money-movements/advance-payment", data);
    return response.data;
  },

  createAdvanceCollection: async (data: AdvanceCollectionCreate): Promise<MoneyMovementResponse> => {
    const response = await apiClient.post<MoneyMovementResponse>("/api/v1/money-movements/advance-collection", data);
    return response.data;
  },

  createAssetPayment: async (data: AssetPaymentCreate): Promise<MoneyMovementResponse> => {
    const response = await apiClient.post<MoneyMovementResponse>("/api/v1/money-movements/asset-payment", data);
    return response.data;
  },

  annul: async (id: string, data: AnnulMovementRequest): Promise<MoneyMovementResponse> => {
    const response = await apiClient.post<MoneyMovementResponse>(`/api/v1/money-movements/${id}/annul`, data);
    return response.data;
  },

  uploadEvidence: async (id: string, file: File): Promise<MoneyMovementResponse> => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post<MoneyMovementResponse>(
      `/api/v1/money-movements/${id}/evidence`,
      formData,
      { headers: { "Content-Type": "multipart/form-data" } },
    );
    return response.data;
  },

  deleteEvidence: async (id: string): Promise<MoneyMovementResponse> => {
    const response = await apiClient.delete<MoneyMovementResponse>(`/api/v1/money-movements/${id}/evidence`);
    return response.data;
  },

  getEvidenceUrl: (id: string): string => {
    return `${apiClient.defaults.baseURL}/api/v1/money-movements/${id}/evidence`;
  },

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  getByThirdParty: async (thirdPartyId: string, filters: { date_from?: string; date_to?: string } = {}): Promise<{ items: any[]; opening_balance: number }> => {
    const response = await apiClient.get(`/api/v1/money-movements/third-party/${thirdPartyId}`, { params: filters });
    return response.data;
  },

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  getByAccount: async (accountId: string, filters: { date_from?: string; date_to?: string } = {}): Promise<{ items: any[]; total: number; opening_balance: number | null }> => {
    const response = await apiClient.get(`/api/v1/money-movements/account/${accountId}`, { params: filters });
    return response.data;
  },
};
