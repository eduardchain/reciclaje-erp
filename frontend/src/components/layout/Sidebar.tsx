import { useState, useMemo } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  ShoppingCart,
  DollarSign,
  ArrowLeftRight,
  Wallet,
  Package,
  BarChart3,
  Users,
  Boxes,
  Settings,
  ChevronDown,
  ChevronRight,
  Warehouse,
  CreditCard,
  Building,
  Tag,
  ListOrdered,
  ClipboardList,
  ArrowDownUp,
  Shuffle,
  Truck,
  Calculator,
  PanelLeftClose,
  PanelLeft,
  CalendarClock,
  Clock,
  Scale,
  Building2,
  PieChart,
  Shield,
  ShieldCheck,
  UserCog,
  Sheet,
  Receipt,
  Landmark,
  Percent,
  PackageOpen,
} from "lucide-react";
import { cn } from "@/utils";
import { ROUTES } from "@/utils/constants";
import EcoBalanceLogo from "@/components/EcoBalanceLogo";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { usePermissions } from "@/hooks/usePermissions";
import { useOrgSettings } from "@/hooks/useOrgSettings";
import { usePendingEntriesCount } from "@/hooks/useInboundOrders";
import { useAuthStore } from "@/stores/authStore";


// Ciclo C (W-C3): solo se monta dentro del item "Entradas", que existe
// unicamente con kg_ledger_enabled — en orgs sin flag este query jamas corre
function PendingEntriesBadge() {
  const count = usePendingEntriesCount();
  if (!count) return null;
  return (
    <span className="min-w-[20px] h-5 px-1.5 rounded-full bg-amber-500/90 text-white text-[11px] font-semibold flex items-center justify-center tabular-nums">
      {count > 99 ? "99+" : count}
    </span>
  );
}

interface NavChild {
  name: string;
  path: string;
  icon: React.ReactNode;
  permission?: string | string[];
  superuserOnly?: boolean;
  // Feature flag de la org (SAC E1, D12): la entrada solo aparece si el flag
  // esta encendido. Las entradas SIN orgFlag JAMAS dependen del query de
  // settings (regla de no-regresion §5.1 del plan E1).
  orgFlag?: string;
}

interface NavItem {
  name: string;
  path: string;
  icon: React.ReactNode;
  section?: string;
  permission?: string;
  children?: NavChild[];
  superuserOnly?: boolean;
  // Feature flag de la org (SAC E2, plan §5): NavItem hoja gated por flag.
  // Regla de no-regresion: las entradas SIN orgFlag jamas tocan el query de settings.
  orgFlag?: string;
  // Inverso (paquete UX W1): la entrada se OCULTA si el flag esta encendido.
  // Degradacion segura: en loading/error flagEnabled=false → visible (status
  // quo para orgs sin flag). Uso: "Materiales" general se oculta en SAC, cuyo
  // reemplazo es Config → Materiales (kg); la ruta /materials queda viva.
  hideWhenOrgFlag?: string;
  // Ciclo C: contador ambar de entradas por liquidar (solo item Entradas SAC)
  pendingBadge?: boolean;
}

const systemNavItems: NavItem[] = [
  {
    name: "Sistema",
    path: ROUTES.SYSTEM_ORGANIZATIONS,
    icon: <Settings className="w-5 h-5" />,
    superuserOnly: true,
    children: [
      { name: "Organizaciones", path: ROUTES.SYSTEM_ORGANIZATIONS, icon: <Building2 className="w-4 h-4" />, superuserOnly: true },
      { name: "Usuarios", path: ROUTES.SYSTEM_USERS, icon: <UserCog className="w-4 h-4" />, superuserOnly: true },
    ],
  },
];

const orgNavItems: NavItem[] = [
  {
    name: "Dashboard",
    path: ROUTES.DASHBOARD,
    icon: <LayoutDashboard className="w-5 h-5" />,
  },
  {
    name: "Compras",
    path: ROUTES.PURCHASES,
    icon: <ShoppingCart className="w-5 h-5" />,
    section: "OPERACIONES",
    permission: "purchases.view",
    // Ciclo C: en SAC el canal es "Entradas" — las rutas /purchases siguen
    // vivas (cara financiera), solo sale del menu
    hideWhenOrgFlag: "kg_ledger_enabled",
  },
  {
    // Ciclo C: modulo unico de entradas (ex "Recepción") — compras + willard
    name: "Entradas",
    path: ROUTES.INBOUND,
    icon: <PackageOpen className="w-5 h-5" />,
    section: "OPERACIONES",
    permission: "purchases.view",
    orgFlag: "kg_ledger_enabled",
    pendingBadge: true,
  },
  {
    name: "Ventas",
    path: ROUTES.SALES,
    icon: <DollarSign className="w-5 h-5" />,
    // Fallback de seccion cuando Compras esta oculta (SAC) — el dedupe de
    // secciones consecutivas evita el doble header en orgs normales
    section: "OPERACIONES",
    permission: "sales.view",
  },
  {
    name: "Doble Partida",
    path: ROUTES.DOUBLE_ENTRIES,
    icon: <ArrowLeftRight className="w-5 h-5" />,
    permission: "double_entries.view",
  },
  {
    name: "Plomo (kg)",
    path: ROUTES.KG_LEDGER,
    icon: <Scale className="w-5 h-5" />,
    permission: "kg_ledger.view",
    orgFlag: "kg_ledger_enabled",
  },
  {
    name: "Tesoreria",
    path: ROUTES.TREASURY,
    icon: <Wallet className="w-5 h-5" />,
    children: [
      { name: "Dashboard", path: ROUTES.TREASURY_DASHBOARD, icon: <LayoutDashboard className="w-4 h-4" />, permission: "treasury.view_dashboard" },
      { name: "Movimientos", path: ROUTES.TREASURY, icon: <ArrowDownUp className="w-4 h-4" />, permission: "treasury.view_movements" },
      { name: "Gastos Masivos", path: ROUTES.TREASURY_BATCH_EXPENSES, icon: <Sheet className="w-4 h-4" />, permission: "treasury.create_movements" },
      { name: "Terceros", path: ROUTES.TREASURY_ACCOUNT_STATEMENT, icon: <ListOrdered className="w-4 h-4" />, permission: "treasury.view_statements" },
      { name: "Cuentas", path: ROUTES.TREASURY_ACCOUNT_MOVEMENTS, icon: <CreditCard className="w-4 h-4" />, permission: "treasury.view_accounts" },
      { name: "Provisiones", path: ROUTES.TREASURY_PROVISIONS, icon: <Tag className="w-4 h-4" />, permission: "treasury.view_provisions" },
      { name: "Pasivos", path: ROUTES.TREASURY_LIABILITIES, icon: <Scale className="w-4 h-4" />, permission: "treasury.view_liabilities" },
      { name: "Retenciones", path: ROUTES.TREASURY_RETENTIONS, icon: <Percent className="w-4 h-4" />, permission: "third_parties.view", orgFlag: "kg_ledger_enabled" },
      { name: "Gastos Diferidos", path: ROUTES.TREASURY_SCHEDULED, icon: <CalendarClock className="w-4 h-4" />, permission: "treasury.view_scheduled" },
      { name: "Activos Fijos", path: ROUTES.TREASURY_FIXED_ASSETS, icon: <Building2 className="w-4 h-4" />, permission: "treasury.view_fixed_assets" },
      { name: "Obligaciones", path: ROUTES.TREASURY_OBLIGATIONS, icon: <Landmark className="w-4 h-4" />, permission: "treasury.view_obligations" },
      { name: "Repartición Utilidades", path: ROUTES.TREASURY_PROFIT_DISTRIBUTION, icon: <PieChart className="w-4 h-4" />, permission: "treasury.manage_distributions" },
    ],
  },
  {
    name: "Inventario",
    path: ROUTES.INVENTORY,
    icon: <Package className="w-5 h-5" />,
    section: "INVENTARIO",
    children: [
      { name: "Stock", path: ROUTES.INVENTORY, icon: <Boxes className="w-4 h-4" />, permission: "inventory.view" },
      { name: "Movimientos", path: ROUTES.INVENTORY_MOVEMENTS, icon: <ArrowDownUp className="w-4 h-4" />, permission: "inventory.view_movements" },
      { name: "Ajustes", path: ROUTES.INVENTORY_ADJUSTMENTS, icon: <ClipboardList className="w-4 h-4" />, permission: "inventory.view_adjustments" },
      { name: "Transformaciones", path: ROUTES.INVENTORY_TRANSFORMATIONS, icon: <Shuffle className="w-4 h-4" />, permission: "transformations.view" },
      { name: "Valorizacion", path: ROUTES.INVENTORY_VALUATION, icon: <Calculator className="w-4 h-4" />, permission: "inventory.view_values" },
      { name: "En Transito", path: ROUTES.INVENTORY_TRANSIT, icon: <Truck className="w-4 h-4" />, permission: "inventory.view_transit" },
    ],
  },
  {
    name: "Reportes",
    path: ROUTES.REPORTS,
    icon: <BarChart3 className="w-5 h-5" />,
    section: "ANALISIS",
    children: [
      { name: "Estado de Resultados", path: ROUTES.REPORTS_PL, icon: <BarChart3 className="w-4 h-4" />, permission: "reports.view_pnl" },
      { name: "Flujo de Caja", path: ROUTES.REPORTS_CASH_FLOW, icon: <ArrowDownUp className="w-4 h-4" />, permission: "reports.view_cashflow" },
      { name: "Balance General", path: ROUTES.REPORTS_BALANCE_SHEET, icon: <Calculator className="w-4 h-4" />, permission: "reports.view_balance" },
      { name: "Balance Detallado", path: ROUTES.REPORTS_BALANCE_DETAILED, icon: <ClipboardList className="w-4 h-4" />, permission: "reports.view_balance" },
      { name: "Dinero Inactivo", path: ROUTES.REPORTS_INACTIVE_BALANCES, icon: <Clock className="w-4 h-4" />, permission: "reports.view_balance" },
      { name: "Compras", path: ROUTES.REPORTS_PURCHASES, icon: <ShoppingCart className="w-4 h-4" />, permission: "reports.view_purchases" },
      { name: "Ventas", path: ROUTES.REPORTS_SALES, icon: <DollarSign className="w-4 h-4" />, permission: "reports.view_sales" },
      { name: "Margenes", path: ROUTES.REPORTS_MARGINS, icon: <BarChart3 className="w-4 h-4" />, permission: "reports.view_margins" },
      { name: "Rentabilidad por UN", path: ROUTES.REPORTS_PROFITABILITY_BU, icon: <BarChart3 className="w-4 h-4" />, permission: "reports.view_pnl" },
      { name: "Costo Real Material", path: ROUTES.REPORTS_REAL_COST, icon: <Calculator className="w-4 h-4" />, permission: "reports.view_pnl" },
      { name: "Gastos", path: ROUTES.REPORTS_EXPENSES, icon: <Receipt className="w-4 h-4" />, permission: "reports.view_expenses" },
      { name: "Saldos Terceros", path: ROUTES.REPORTS_BALANCES, icon: <Users className="w-4 h-4" />, permission: "reports.view_third_parties" },
    ],
  },
  {
    name: "Terceros",
    path: ROUTES.THIRD_PARTIES,
    icon: <Users className="w-5 h-5" />,
    section: "MAESTROS",
    permission: "third_parties.view",
  },
  {
    name: "Materiales",
    path: ROUTES.MATERIALS,
    icon: <Boxes className="w-5 h-5" />,
    permission: "materials.view",
    // W1: en SAC el catalogo vive en Config → Materiales (kg) — esta entrada
    // duplicaria el alta de materiales (ruido, C1). Ruta /materials sigue viva.
    hideWhenOrgFlag: "kg_ledger_enabled",
  },
  {
    name: "Configuracion",
    path: ROUTES.CONFIG,
    icon: <Settings className="w-5 h-5" />,
    section: "SISTEMA",
    children: [
      { name: "Bodegas", path: ROUTES.CONFIG_WAREHOUSES, icon: <Warehouse className="w-4 h-4" />, permission: "warehouses.view" },
      { name: "Cuentas", path: ROUTES.CONFIG_ACCOUNTS, icon: <CreditCard className="w-4 h-4" />, permission: "treasury.manage_accounts" },
      { name: "Unidades Negocio", path: ROUTES.CONFIG_BUSINESS_UNITS, icon: <Building className="w-4 h-4" />, permission: "config.view_business_units" },
      { name: "Cat. Gastos", path: ROUTES.CONFIG_EXPENSE_CATEGORIES, icon: <Tag className="w-4 h-4" />, permission: "treasury.manage_expenses" },
      { name: "Listas Precios", path: ROUTES.CONFIG_PRICE_LISTS, icon: <ListOrdered className="w-4 h-4" />, permission: "materials.view_prices" },
      { name: "Cat. Terceros", path: ROUTES.CONFIG_THIRD_PARTY_CATEGORIES, icon: <Users className="w-4 h-4" />, permission: "third_parties.create" },
      { name: "Tarifas", path: ROUTES.CONFIG_TARIFFS, icon: <Receipt className="w-4 h-4" />, permission: "tariffs.view", orgFlag: "kg_ledger_enabled" },
      { name: "Materiales (kg)", path: ROUTES.CONFIG_FORMULAS, icon: <Calculator className="w-4 h-4" />, permission: "formulas.view", orgFlag: "kg_ledger_enabled" },
      { name: "Conductores y Vehiculos", path: ROUTES.CONFIG_FLEET, icon: <Truck className="w-4 h-4" />, permission: "config.view_fleet", orgFlag: "kg_ledger_enabled" },
    ],
  },
  {
    name: "Admin",
    path: ROUTES.ADMIN_ROLES,
    icon: <Shield className="w-5 h-5" />,
    section: "ADMIN",
    children: [
      { name: "Roles", path: ROUTES.ADMIN_ROLES, icon: <ShieldCheck className="w-4 h-4" />, permission: "admin.manage_roles" },
      { name: "Usuarios", path: ROUTES.ADMIN_USERS, icon: <UserCog className="w-4 h-4" />, permission: "admin.manage_users" },
    ],
  },
];

interface SidebarProps {
  mode?: "desktop" | "mobile";
  onNavigate?: () => void;
}

export default function Sidebar({ mode = "desktop", onNavigate }: SidebarProps = {}) {
  const location = useLocation();
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [collapsedDesktop, setCollapsedDesktop] = useState(false);
  const { hasPermission, hasAnyPermission, isLoading } = usePermissions();
  const { flagEnabled } = useOrgSettings();
  const user = useAuthStore((s) => s.user);
  const organizationId = useAuthStore((s) => s.organizationId);
  const isSuperuser = user?.is_superuser ?? false;
  const isSystemMode = organizationId === "system";

  const isMobile = mode === "mobile";
  // En mobile: nunca colapsado (el drawer ya controla visibilidad)
  const collapsed = isMobile ? false : collapsedDesktop;

  const filteredNavItems = useMemo(() => {
    if (isLoading) return [];

    // En modo sistema, solo mostrar items de sistema
    if (isSystemMode) {
      return isSuperuser ? systemNavItems : [];
    }

    const checkPerm = (perm?: string | string[]) => {
      if (!perm) return true;
      if (Array.isArray(perm)) return hasAnyPermission(perm);
      return hasPermission(perm);
    };

    // Regla de no-regresion (plan E1 §5.1): SOLO las entradas CON orgFlag
    // consultan flagEnabled — en loading/error/settings NULL se ocultan ellas
    // y el resto del sidebar se renderiza identico a hoy.
    const checkFlag = (flag?: string) => !flag || flagEnabled(flag);
    // W1: ocultar-si-flag — solo la consulta la entrada que lo declara
    const checkHide = (flag?: string) => !flag || !flagEnabled(flag);

    const filtered = orgNavItems
      .map((item) => {
        if (item.children) {
          const filteredChildren = item.children.filter(
            (child) => checkPerm(child.permission) && checkFlag(child.orgFlag)
          );
          if (filteredChildren.length === 0) return null;
          return { ...item, children: filteredChildren };
        }
        if (!checkPerm(item.permission) || !checkFlag(item.orgFlag) || !checkHide(item.hideWhenOrgFlag)) return null;
        return item;
      })
      .filter(Boolean) as NavItem[];

    // Ciclo C: dedupe de secciones consecutivas — varios items declaran la
    // misma seccion como fallback (ej. Compras oculta en SAC → Entradas o
    // Ventas cargan "OPERACIONES"); solo el primero visible la renderiza
    let lastSection: string | undefined;
    return filtered.map((item) => {
      if (!item.section) return item;
      if (item.section === lastSection) {
        const { section: _dropped, ...rest } = item;
        return rest as NavItem;
      }
      lastSection = item.section;
      return item;
    });
  }, [isLoading, hasPermission, hasAnyPermission, isSystemMode, isSuperuser, flagEnabled]);

  const toggleExpand = (name: string) => {
    setExpanded((prev) => ({ ...prev, [name]: !prev[name] }));
  };

  const isActive = (path: string) => {
    if (path === "/") return location.pathname === "/";
    return location.pathname.startsWith(path);
  };

  return (
    <TooltipProvider delayDuration={0}>
      <aside
        className={cn(
          "bg-sidebar-bg h-full overflow-y-auto overflow-x-hidden flex flex-col transition-all duration-200",
          isMobile ? "w-full" : collapsed ? "w-[68px]" : "w-64"
        )}
      >
        {/* Logo */}
        <div className={cn(
          "flex items-center h-16 px-4 border-b border-white/10 shrink-0",
          collapsed ? "justify-center" : ""
        )}>
          <EcoBalanceLogo textColor="light" showText={!collapsed} />
        </div>

        {/* Navigation */}
        <nav className={cn("flex-1 py-4", collapsed ? "px-2" : "px-3")}>
          <div className="space-y-1">
            {filteredNavItems.map((item, index) => {
              const active = isActive(item.path);
              const hasChildren = item.children && item.children.length > 0;
              const isExpanded = expanded[item.name] || (hasChildren && isActive(item.path));

              // Separador de seccion
              const sectionLabel = item.section && index > 0 ? (
                <div className={cn("pt-5 pb-2", collapsed ? "px-0" : "px-3")}>
                  {!collapsed && (
                    <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                      {item.section}
                    </span>
                  )}
                  {collapsed && <div className="border-t border-white/10" />}
                </div>
              ) : null;

              if (hasChildren) {
                return (
                  <div key={item.name}>
                    {sectionLabel}
                    {collapsed ? (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Link
                            to={item.path}
                            onClick={onNavigate}
                            className={cn(
                              "flex items-center justify-center w-full p-2.5 rounded-lg transition-all duration-150",
                              active
                                ? "bg-white/10 text-emerald-400"
                                : "text-sidebar-foreground hover:bg-white/5 hover:text-white"
                            )}
                          >
                            {item.icon}
                          </Link>
                        </TooltipTrigger>
                        <TooltipContent side="right" className="font-medium">
                          {item.name}
                        </TooltipContent>
                      </Tooltip>
                    ) : (
                      <>
                        <button
                          onClick={() => toggleExpand(item.name)}
                          className={cn(
                            "flex items-center justify-between w-full px-3 py-2.5 rounded-lg transition-all duration-150 group",
                            active
                              ? "bg-white/10 text-white"
                              : "text-sidebar-foreground hover:bg-white/5 hover:text-white"
                          )}
                        >
                          <div className="flex items-center gap-3">
                            <span className={cn(active && "text-emerald-400")}>{item.icon}</span>
                            <span className="text-sm font-medium">{item.name}</span>
                          </div>
                          {isExpanded ? (
                            <ChevronDown className="w-4 h-4 opacity-50" />
                          ) : (
                            <ChevronRight className="w-4 h-4 opacity-50" />
                          )}
                        </button>
                        {isExpanded && (
                          <div className="mt-1 ml-4 space-y-0.5 border-l border-white/10 pl-3">
                            {item.children!.map((child) => {
                              const childActive = location.pathname === child.path;
                              return (
                                <Link
                                  key={child.path}
                                  to={child.path}
                                  onClick={onNavigate}
                                  className={cn(
                                    "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-150",
                                    childActive
                                      ? "text-emerald-400 bg-white/5 font-medium"
                                      : "text-sidebar-foreground hover:text-white hover:bg-white/5"
                                  )}
                                >
                                  {child.icon}
                                  <span>{child.name}</span>
                                </Link>
                              );
                            })}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                );
              }

              return (
                <div key={item.path}>
                  {sectionLabel}
                  {collapsed ? (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Link
                          to={item.path}
                          onClick={onNavigate}
                          className={cn(
                            "flex items-center justify-center p-2.5 rounded-lg transition-all duration-150",
                            active
                              ? "bg-white/10 text-emerald-400"
                              : "text-sidebar-foreground hover:bg-white/5 hover:text-white"
                          )}
                        >
                          {item.icon}
                        </Link>
                      </TooltipTrigger>
                      <TooltipContent side="right" className="font-medium">
                        {item.name}
                      </TooltipContent>
                    </Tooltip>
                  ) : (
                    <Link
                      to={item.path}
                      onClick={onNavigate}
                      className={cn(
                        "flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-150 group",
                        active
                          ? "bg-white/10 text-white font-medium"
                          : "text-sidebar-foreground hover:bg-white/5 hover:text-white"
                      )}
                    >
                      <span className={cn(active && "text-emerald-400")}>{item.icon}</span>
                      <span className="text-sm">{item.name}</span>
                      {item.pendingBadge ? (
                        <span className="ml-auto flex items-center gap-1.5">
                          <PendingEntriesBadge />
                          {active && <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" />}
                        </span>
                      ) : (
                        active && (
                          <div className="ml-auto w-1.5 h-1.5 rounded-full bg-emerald-400" />
                        )
                      )}
                    </Link>
                  )}
                </div>
              );
            })}
          </div>
        </nav>

        {/* Collapse toggle - solo en desktop (en mobile el drawer ya provee cerrar) */}
        {!isMobile && (
          <div className={cn(
            "border-t border-white/10 p-3 shrink-0",
            collapsed && "flex justify-center"
          )}>
            <button
              onClick={() => setCollapsedDesktop(!collapsed)}
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-sidebar-foreground hover:text-white hover:bg-white/5 transition-all duration-150 w-full"
            >
              {collapsed ? (
                <PanelLeft className="w-5 h-5 mx-auto" />
              ) : (
                <>
                  <PanelLeftClose className="w-5 h-5" />
                  <span className="text-sm">Colapsar</span>
                </>
              )}
            </button>
          </div>
        )}
      </aside>
    </TooltipProvider>
  );
}
