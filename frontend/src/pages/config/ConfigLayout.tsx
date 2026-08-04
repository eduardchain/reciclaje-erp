import { useNavigate, useLocation } from "react-router-dom";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/shared/PageHeader";
import { ROUTES } from "@/utils/constants";
import { usePermissions } from "@/hooks/usePermissions";
import { useOrgSettings } from "@/hooks/useOrgSettings";

// orgFlag (SAC E1, D12): el tab solo aparece con el flag encendido. Los tabs
// SIN orgFlag jamas dependen del query de settings (no-regresion §5.1).
// ⚠️ Lista duplicada con Sidebar.tsx (children de Configuracion) — mantener AMBAS.
const tabs = [
  { value: ROUTES.CONFIG_WAREHOUSES, label: "Bodegas", permission: "warehouses.view" },
  { value: ROUTES.CONFIG_ACCOUNTS, label: "Cuentas", permission: "treasury.manage_accounts" },
  { value: ROUTES.CONFIG_BUSINESS_UNITS, label: "Unidades Negocio", permission: "config.view_business_units" },
  { value: ROUTES.CONFIG_EXPENSE_CATEGORIES, label: "Cat. Gastos", permission: "treasury.manage_expenses" },
  { value: ROUTES.CONFIG_PRICE_LISTS, label: "Precios", permission: "materials.view_prices" },
  { value: ROUTES.CONFIG_THIRD_PARTY_CATEGORIES, label: "Cat. Terceros", permission: "third_parties.create" },
  { value: ROUTES.CONFIG_TARIFFS, label: "Tarifas", permission: "tariffs.view", orgFlag: "kg_ledger_enabled" },
  { value: ROUTES.CONFIG_FORMULAS, label: "Materiales (kg)", permission: "formulas.view", orgFlag: "kg_ledger_enabled" },
  { value: ROUTES.CONFIG_FLEET, label: "Conductores y Vehiculos", permission: "config.view_fleet", orgFlag: "kg_ledger_enabled" },
  { value: ROUTES.CONFIG_WILLARD_CENTERS, label: "Centros Willard", permission: "config.manage_sac_settings", orgFlag: "kg_ledger_enabled" },
];

export default function ConfigLayout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { hasPermission } = usePermissions();
  const { flagEnabled } = useOrgSettings();

  const visibleTabs = tabs.filter(
    (t) => hasPermission(t.permission) && (!t.orgFlag || flagEnabled(t.orgFlag))
  );

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
