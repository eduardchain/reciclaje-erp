// Tipos para repartición de utilidades

export interface ProfitDistributionLineCreate {
  third_party_id: string;
  amount: number;
}

export interface ProfitDistributionCreate {
  date: string;
  lines: ProfitDistributionLineCreate[];
  notes?: string;
}

export interface ProfitDistributionLineResponse {
  id: string;
  third_party_id: string;
  third_party_name: string;
  amount: number;
  money_movement_id?: string;
}

export interface ProfitDistributionResponse {
  id: string;
  date: string;
  total_amount: number;
  notes?: string;
  created_by?: string;
  created_at: string;
  lines: ProfitDistributionLineResponse[];
}

export interface AvailableProfitResponse {
  accumulated_profit: number;
  distributed_profit: number;
  available_profit: number;
}

export interface PartnerResponse {
  id: string;
  name: string;
  current_balance: number;
}
