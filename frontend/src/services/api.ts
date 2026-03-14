import axios, { type AxiosError } from "axios";
import { API_BASE_URL } from "@/utils/constants";
import type { HealthResponse } from "@/types/common";

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor: JWT token + Organization ID
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    const orgId = localStorage.getItem("organizationId");
    if (orgId && orgId !== "system") {
      config.headers["X-Organization-ID"] = orgId;
    }

    return config;
  },
  (error) => Promise.reject(error),
);

// Response interceptor: handle 401
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // No redirigir si es un intento de login (no hay token aun)
      const isLoginRequest = error.config?.url?.includes("/auth/login");
      if (!isLoginRequest) {
        localStorage.removeItem("token");
        localStorage.removeItem("organizationId");
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);

// Health check (mantenido para compatibilidad con Dashboard actual)
export const api = {
  health: async (): Promise<HealthResponse> => {
    const response = await apiClient.get<HealthResponse>("/api/v1/health");
    return response.data;
  },
};

export default apiClient;
