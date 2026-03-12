import { useState } from "react";
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
  Scale,
  Building2,
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

interface NavItem {
  name: string;
  path: string;
  icon: React.ReactNode;
  section?: string;
  children?: { name: string; path: string; icon: React.ReactNode }[];
}

const navItems: NavItem[] = [
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
  },
  {
    name: "Ventas",
    path: ROUTES.SALES,
    icon: <DollarSign className="w-5 h-5" />,
  },
  {
    name: "Doble Partida",
    path: ROUTES.DOUBLE_ENTRIES,
    icon: <ArrowLeftRight className="w-5 h-5" />,
  },
  {
    name: "Tesoreria",
    path: ROUTES.TREASURY,
    icon: <Wallet className="w-5 h-5" />,
    children: [
      { name: "Dashboard", path: ROUTES.TREASURY_DASHBOARD, icon: <LayoutDashboard className="w-4 h-4" /> },
      { name: "Movimientos", path: ROUTES.TREASURY, icon: <ArrowDownUp className="w-4 h-4" /> },
      { name: "Terceros", path: ROUTES.TREASURY_ACCOUNT_STATEMENT, icon: <ListOrdered className="w-4 h-4" /> },
      { name: "Cuentas", path: ROUTES.TREASURY_ACCOUNT_MOVEMENTS, icon: <CreditCard className="w-4 h-4" /> },
      { name: "Provisiones", path: ROUTES.TREASURY_PROVISIONS, icon: <Tag className="w-4 h-4" /> },
      { name: "Pasivos", path: ROUTES.TREASURY_LIABILITIES, icon: <Scale className="w-4 h-4" /> },
      { name: "Gastos Diferidos", path: ROUTES.TREASURY_SCHEDULED, icon: <CalendarClock className="w-4 h-4" /> },
      { name: "Activos Fijos", path: ROUTES.TREASURY_FIXED_ASSETS, icon: <Building2 className="w-4 h-4" /> },
    ],
  },
  {
    name: "Inventario",
    path: ROUTES.INVENTORY,
    icon: <Package className="w-5 h-5" />,
    section: "INVENTARIO",
    children: [
      { name: "Stock", path: ROUTES.INVENTORY, icon: <Boxes className="w-4 h-4" /> },
      { name: "Movimientos", path: ROUTES.INVENTORY_MOVEMENTS, icon: <ArrowDownUp className="w-4 h-4" /> },
      { name: "Ajustes", path: ROUTES.INVENTORY_ADJUSTMENTS, icon: <ClipboardList className="w-4 h-4" /> },
      { name: "Transformaciones", path: ROUTES.INVENTORY_TRANSFORMATIONS, icon: <Shuffle className="w-4 h-4" /> },
      { name: "Valorizacion", path: ROUTES.INVENTORY_VALUATION, icon: <Calculator className="w-4 h-4" /> },
      { name: "En Transito", path: ROUTES.INVENTORY_TRANSIT, icon: <Truck className="w-4 h-4" /> },
    ],
  },
  {
    name: "Reportes",
    path: ROUTES.REPORTS,
    icon: <BarChart3 className="w-5 h-5" />,
    section: "ANALISIS",
  },
  {
    name: "Terceros",
    path: ROUTES.THIRD_PARTIES,
    icon: <Users className="w-5 h-5" />,
    section: "MAESTROS",
  },
  {
    name: "Materiales",
    path: ROUTES.MATERIALS,
    icon: <Boxes className="w-5 h-5" />,
  },
  {
    name: "Configuracion",
    path: ROUTES.CONFIG,
    icon: <Settings className="w-5 h-5" />,
    section: "SISTEMA",
    children: [
      { name: "Bodegas", path: ROUTES.CONFIG_WAREHOUSES, icon: <Warehouse className="w-4 h-4" /> },
      { name: "Cuentas", path: ROUTES.CONFIG_ACCOUNTS, icon: <CreditCard className="w-4 h-4" /> },
      { name: "Unidades Negocio", path: ROUTES.CONFIG_BUSINESS_UNITS, icon: <Building className="w-4 h-4" /> },
      { name: "Cat. Gastos", path: ROUTES.CONFIG_EXPENSE_CATEGORIES, icon: <Tag className="w-4 h-4" /> },
      { name: "Listas Precios", path: ROUTES.CONFIG_PRICE_LISTS, icon: <ListOrdered className="w-4 h-4" /> },
    ],
  },
];

export default function Sidebar() {
  const location = useLocation();
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [collapsed, setCollapsed] = useState(false);

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
          collapsed ? "w-[68px]" : "w-64"
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
            {navItems.map((item, index) => {
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
                      className={cn(
                        "flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-150 group",
                        active
                          ? "bg-white/10 text-white font-medium"
                          : "text-sidebar-foreground hover:bg-white/5 hover:text-white"
                      )}
                    >
                      <span className={cn(active && "text-emerald-400")}>{item.icon}</span>
                      <span className="text-sm">{item.name}</span>
                      {active && (
                        <div className="ml-auto w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      )}
                    </Link>
                  )}
                </div>
              );
            })}
          </div>
        </nav>

        {/* Collapse toggle */}
        <div className={cn(
          "border-t border-white/10 p-3 shrink-0",
          collapsed && "flex justify-center"
        )}>
          <button
            onClick={() => setCollapsed(!collapsed)}
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
      </aside>
    </TooltipProvider>
  );
}
