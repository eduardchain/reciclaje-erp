import apiClient from "./api";
import type {
  KgLedgerAccountCreate,
  KgLedgerAccountResponse,
  KgLedgerAccountUpdate,
  KgLedgerMovementManualCreate,
  KgLedgerMovementResponse,
  KgLedgerStatementResponse,
  KgLedgerSummaryResponse,
} from "@/types/kg-ledger";

// KgLedger (SAC E2): cuentas en kg de plomo. Router completo gated por
// flag kg_ledger_enabled en backend (403 si la org no tiene el modulo).

export interface KgStatementFilters {
  date_from?: string;
  date_to?: string;
  status_filter?: "confirmed" | "annulled" | "all";
}

export const kgLedgerService = {
  getAccounts: async (filters?: {
    account_type?: string;
    include_inactive?: boolean;
  }): Promise<KgLedgerAccountResponse[]> => {
    const response = await apiClient.get<KgLedgerAccountResponse[]>(
      "/api/v1/kg-ledger/accounts",
      { params: filters ?? {} }
    );
    return response.data;
  },

  createAccount: async (data: KgLedgerAccountCreate): Promise<KgLedgerAccountResponse> => {
    const response = await apiClient.post<KgLedgerAccountResponse>(
      "/api/v1/kg-ledger/accounts",
      data
    );
    return response.data;
  },

  updateAccount: async (
    id: string,
    data: KgLedgerAccountUpdate
  ): Promise<KgLedgerAccountResponse> => {
    const response = await apiClient.patch<KgLedgerAccountResponse>(
      `/api/v1/kg-ledger/accounts/${id}`,
      data
    );
    return response.data;
  },

  getStatement: async (
    accountId: string,
    filters?: KgStatementFilters
  ): Promise<KgLedgerStatementResponse> => {
    const response = await apiClient.get<KgLedgerStatementResponse>(
      `/api/v1/kg-ledger/accounts/${accountId}/movements`,
      { params: filters ?? {} }
    );
    return response.data;
  },

  getSummary: async (asOf?: string): Promise<KgLedgerSummaryResponse> => {
    const response = await apiClient.get<KgLedgerSummaryResponse>(
      "/api/v1/kg-ledger/summary",
      { params: asOf ? { as_of: asOf } : {} }
    );
    return response.data;
  },

  createManualMovement: async (
    data: KgLedgerMovementManualCreate
  ): Promise<KgLedgerMovementResponse> => {
    const response = await apiClient.post<KgLedgerMovementResponse>(
      "/api/v1/kg-ledger/movements",
      data
    );
    return response.data;
  },

  annulMovement: async (id: string, reason: string): Promise<KgLedgerMovementResponse> => {
    const response = await apiClient.post<KgLedgerMovementResponse>(
      `/api/v1/kg-ledger/movements/${id}/annul`,
      { reason }
    );
    return response.data;
  },
};
