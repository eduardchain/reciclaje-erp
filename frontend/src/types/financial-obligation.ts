// Obligaciones Financieras (plan F): prestamos por pagar / por cobrar

export type ObligationDirection = "payable" | "receivable";
export type ObligationStatus = "active" | "settled";

export interface FinancialObligationResponse {
  id: string;
  organization_id: string;
  third_party_id: string;
  third_party_name: string;
  direction: ObligationDirection;
  monthly_rate: string; // Decimal serializado
  capital_balance: string;
  pending_interest: string;
  accrual_start_period: string; // "YYYY-MM"
  last_accrued_period: string | null;
  disbursement_date: string | null;
  status: ObligationStatus;
  notes: string | null;
  created_at: string;
}

export interface ObligationDisbursementData {
  account_id: string;
  amount: number;
  date: string;
}

export interface FinancialObligationCreate {
  third_party_id: string;
  direction: ObligationDirection;
  monthly_rate: number;
  mode: "disbursement" | "from_balance";
  disbursement?: ObligationDisbursementData;
  accrual_start_period?: string;
  notes?: string;
}

export interface ObligationMovementCreate {
  amount: number;
  account_id: string;
  date: string;
  reference_number?: string;
  notes?: string;
}

export interface PendingAccrualItem {
  obligation_id: string;
  third_party_name: string;
  direction: ObligationDirection;
  period: string;
  amount: string;
  breakdown: string;
}

export interface PendingAccrualsResponse {
  items: PendingAccrualItem[];
  total_payable: string;
  total_receivable: string;
  has_payable: boolean;
}

export interface AccrueResultResponse {
  created_count: number;
  total_payable: string;
  total_receivable: string;
}

export interface ObligationDirectionSummary {
  direction: ObligationDirection;
  count: number;
  total_capital: string;
  total_pending_interest: string;
  weighted_avg_rate: string;
  current_month_projection: string;
}

export interface ObligationSummaryResponse {
  payable: ObligationDirectionSummary;
  receivable: ObligationDirectionSummary;
}
