export interface HealthResponse {
  status: string;
  database: string;
}

export interface ApiError {
  message: string;
  status?: number;
}

export interface User {
  id: number;
  email: string;
  name: string;
  role: string;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
}
