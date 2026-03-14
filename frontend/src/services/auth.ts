import apiClient from "./api";
import type { Token, UserResponse, UserLogin } from "@/types/auth";

export const authService = {
  login: async (data: UserLogin): Promise<Token> => {
    const response = await apiClient.post<Token>("/api/v1/auth/login/json", data);
    return response.data;
  },

  getMe: async (): Promise<UserResponse> => {
    const response = await apiClient.get<UserResponse>("/api/v1/auth/me");
    return response.data;
  },

  changePassword: async (data: { current_password: string; new_password: string }) => {
    const response = await apiClient.post("/api/v1/auth/change-password", data);
    return response.data;
  },

  register: async (data: { email: string; password: string; full_name?: string; organization_name?: string }) => {
    const response = await apiClient.post("/api/v1/auth/register", data);
    return response.data;
  },
};
