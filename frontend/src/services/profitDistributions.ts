import apiClient from "./api";
import type {
  AvailableProfitResponse,
  PartnerResponse,
  ProfitDistributionCreate,
  ProfitDistributionResponse,
} from "@/types/profit-distribution";
import type { PaginatedResponse } from "@/types/common";

export const profitDistributionService = {
  getAvailable: (): Promise<AvailableProfitResponse> =>
    apiClient.get("/api/v1/profit-distributions/available").then((r) => r.data),

  getPartners: (): Promise<PartnerResponse[]> =>
    apiClient.get("/api/v1/profit-distributions/partners").then((r) => r.data),

  create: (data: ProfitDistributionCreate): Promise<ProfitDistributionResponse> =>
    apiClient.post("/api/v1/profit-distributions/", data).then((r) => r.data),

  getAll: (params?: {
    skip?: number;
    limit?: number;
  }): Promise<PaginatedResponse<ProfitDistributionResponse>> =>
    apiClient
      .get("/api/v1/profit-distributions/", { params })
      .then((r) => r.data),
};
