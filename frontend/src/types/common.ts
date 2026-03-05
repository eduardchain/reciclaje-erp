export interface BaseEntity {
  id: string;
  created_at: string;
  updated_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

export interface ApiError {
  detail: string;
  status?: number;
}

export interface HealthResponse {
  status: string;
  database: string;
}

export interface PaginationParams {
  skip?: number;
  limit?: number;
}
