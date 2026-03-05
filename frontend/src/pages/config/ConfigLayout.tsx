import { useNavigate, useLocation } from "react-router-dom";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/shared/PageHeader";
import { ROUTES } from "@/utils/constants";

const tabs = [
  { value: ROUTES.CONFIG_WAREHOUSES, label: "Bodegas" },
  { value: ROUTES.CONFIG_ACCOUNTS, label: "Cuentas" },
  { value: ROUTES.CONFIG_BUSINESS_UNITS, label: "Unidades Negocio" },
  { value: ROUTES.CONFIG_EXPENSE_CATEGORIES, label: "Cat. Gastos" },
  { value: ROUTES.CONFIG_PRICE_LISTS, label: "Precios" },
];

export default function ConfigLayout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <div className="space-y-4">
      <PageHeader title="Configuracion" description="Datos maestros del sistema" />
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
