import { useNavigate, useLocation } from "react-router-dom";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/shared/PageHeader";
import { ROUTES } from "@/utils/constants";

const tabs = [
  { value: ROUTES.REPORTS_PL, label: "P&L" },
  { value: ROUTES.REPORTS_CASH_FLOW, label: "Flujo Caja" },
  { value: ROUTES.REPORTS_BALANCE_SHEET, label: "Balance" },
  { value: ROUTES.REPORTS_PURCHASES, label: "Compras" },
  { value: ROUTES.REPORTS_SALES, label: "Ventas" },
  { value: ROUTES.REPORTS_MARGINS, label: "Margenes" },
  { value: ROUTES.REPORTS_BALANCES, label: "Saldos" },
  { value: ROUTES.REPORTS_AUDIT, label: "Auditoría" },
];

export default function ReportsLayout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <div className="space-y-4">
      <PageHeader title="Reportes" description="Reportes financieros y operacionales" />

      <Tabs value={location.pathname} onValueChange={(v) => navigate(v)}>
        <TabsList className="flex-wrap h-auto">
          {tabs.map((t) => (
            <TabsTrigger key={t.value} value={t.value}>{t.label}</TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {children}
    </div>
  );
}
