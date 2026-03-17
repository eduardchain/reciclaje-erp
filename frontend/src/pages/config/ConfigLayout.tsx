import { useNavigate, useLocation } from "react-router-dom";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/shared/PageHeader";
import { ROUTES } from "@/utils/constants";
import { usePermissions } from "@/hooks/usePermissions";

const tabs = [
  { value: ROUTES.CONFIG_WAREHOUSES, label: "Bodegas", permission: "warehouses.view" },
  { value: ROUTES.CONFIG_ACCOUNTS, label: "Cuentas", permission: "treasury.manage_accounts" },
  { value: ROUTES.CONFIG_BUSINESS_UNITS, label: "Unidades Negocio", permission: "config.view_business_units" },
  { value: ROUTES.CONFIG_EXPENSE_CATEGORIES, label: "Cat. Gastos", permission: "treasury.manage_expenses" },
  { value: ROUTES.CONFIG_PRICE_LISTS, label: "Precios", permission: "materials.view_prices" },
  { value: ROUTES.CONFIG_THIRD_PARTY_CATEGORIES, label: "Cat. Terceros", permission: "third_parties.create" },
];

export default function ConfigLayout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { hasPermission } = usePermissions();

  const visibleTabs = tabs.filter((t) => hasPermission(t.permission));

  return (
    <div className="space-y-4">
      <PageHeader title="Configuracion" description="Datos maestros del sistema" />
      <Tabs value={location.pathname} onValueChange={(v) => navigate(v)}>
        <TabsList className="flex-wrap h-auto">
          {visibleTabs.map((t) => (
            <TabsTrigger key={t.value} value={t.value}>{t.label}</TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      {children}
    </div>
  );
}
