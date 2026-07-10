import { useNavigate, useLocation } from "react-router-dom";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/shared/PageHeader";
import { ROUTES } from "@/utils/constants";
import { usePermissions } from "@/hooks/usePermissions";

const tabs = [
  { value: ROUTES.REPORTS_PL, label: "P&L", permission: "reports.view_pnl" },
  { value: ROUTES.REPORTS_CASH_FLOW, label: "Flujo Caja", permission: "reports.view_cashflow" },
  { value: ROUTES.REPORTS_BALANCE_SHEET, label: "Balance", permission: "reports.view_balance" },
  { value: ROUTES.REPORTS_BALANCE_DETAILED, label: "Balance Detallado", permission: "reports.view_balance" },
  { value: ROUTES.REPORTS_PURCHASES, label: "Compras", permission: "reports.view_purchases" },
  { value: ROUTES.REPORTS_SALES, label: "Ventas", permission: "reports.view_sales" },
  { value: ROUTES.REPORTS_MARGINS, label: "Margenes", permission: "reports.view_margins" },
  { value: ROUTES.REPORTS_PROFITABILITY_BU, label: "Rentabilidad UN", permission: "reports.view_pnl" },
  { value: ROUTES.REPORTS_REAL_COST, label: "Costo Real", permission: "reports.view_pnl" },
  { value: ROUTES.REPORTS_EXPENSES, label: "Gastos", permission: "reports.view_expenses" },
  { value: ROUTES.REPORTS_INACTIVE_BALANCES, label: "Dinero Inactivo", permission: "reports.view_balance" },
  { value: ROUTES.REPORTS_BALANCES, label: "Saldos", permission: "reports.view_third_parties" },
  { value: ROUTES.REPORTS_AUDIT, label: "Auditoría", permission: "admin.view_audit" },
];

export default function ReportsLayout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { hasPermission } = usePermissions();

  const visibleTabs = tabs.filter((t) => hasPermission(t.permission));

  return (
    <div className="space-y-4">
      <PageHeader title="Reportes" description="Reportes financieros y operacionales" />

      <Tabs value={location.pathname} onValueChange={(v) => navigate(v)}>
        <div className="overflow-x-auto -mx-3 px-3 sm:mx-0 sm:px-0">
          <TabsList className="inline-flex w-max sm:flex sm:w-auto sm:flex-wrap sm:h-auto">
            {visibleTabs.map((t) => (
              <TabsTrigger key={t.value} value={t.value}>{t.label}</TabsTrigger>
            ))}
          </TabsList>
        </div>
      </Tabs>

      {children}
    </div>
  );
}
