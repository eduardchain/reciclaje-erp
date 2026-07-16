import type { PnlSection } from "@/types/reports";

// Drill-down de los rubros de gasto del P&L → Tesorería. Compartido por
// ProfitAndLossPeriodView y ProfitAndLossMonthlyView para evitar drift.
//
// operativo/financiero van SIN tab: la restricción implícita del backend
// (param pnl_section ⇒ movement_type IN EXPENSE_MOVEMENT_TYPES, N1 del plan)
// lista los tipos de gasto de la sección y la suma cuadra con el P&L
// (paridad #49 por construcción — ambos lados usan el mismo clasificador).
// depreciation_expense conserva su tab exacto (nivel 1: el tab YA es la sección).
export const PNL_EXPENSE_DRILL_URLS: Record<PnlSection, string> = {
  operativo: "/treasury?pnl_section=operativo&status=confirmed",
  depreciacion: "/treasury?tab=depreciation_expense&status=confirmed",
  financiero: "/treasury?pnl_section=financiero&status=confirmed",
};
