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
} from "lucide-react";
import { cn } from "@/utils";
import { ROUTES } from "@/utils/constants";

interface NavItem {
  name: string;
  path: string;
  icon: React.ReactNode;
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
  },
  {
    name: "Inventario",
    path: ROUTES.INVENTORY,
    icon: <Package className="w-5 h-5" />,
    children: [
      { name: "Stock", path: ROUTES.INVENTORY, icon: <Boxes className="w-4 h-4" /> },
      { name: "Movimientos", path: ROUTES.INVENTORY_MOVEMENTS, icon: <ArrowDownUp className="w-4 h-4" /> },
      { name: "Ajustes", path: ROUTES.INVENTORY_ADJUSTMENTS, icon: <ClipboardList className="w-4 h-4" /> },
      { name: "Transformaciones", path: ROUTES.INVENTORY_TRANSFORMATIONS, icon: <Shuffle className="w-4 h-4" /> },
    ],
  },
  {
    name: "Reportes",
    path: ROUTES.REPORTS,
    icon: <BarChart3 className="w-5 h-5" />,
  },
  {
    name: "Terceros",
    path: ROUTES.THIRD_PARTIES,
    icon: <Users className="w-5 h-5" />,
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

  const toggleExpand = (name: string) => {
    setExpanded((prev) => ({ ...prev, [name]: !prev[name] }));
  };

  const isActive = (path: string) => {
    if (path === "/") return location.pathname === "/";
    return location.pathname.startsWith(path);
  };

  return (
    <aside className="w-64 bg-white border-r border-gray-200 h-full overflow-y-auto">
      <nav className="p-4 space-y-1">
        {navItems.map((item) => {
          const active = isActive(item.path);
          const hasChildren = item.children && item.children.length > 0;
          const isExpanded = expanded[item.name] || (hasChildren && isActive(item.path));

          if (hasChildren) {
            return (
              <div key={item.name}>
                <button
                  onClick={() => toggleExpand(item.name)}
                  className={cn(
                    "flex items-center justify-between w-full px-4 py-3 rounded-lg transition-colors",
                    active
                      ? "bg-green-50 text-green-700 font-medium"
                      : "text-gray-700 hover:bg-gray-50"
                  )}
                >
                  <div className="flex items-center space-x-3">
                    {item.icon}
                    <span>{item.name}</span>
                  </div>
                  {isExpanded ? (
                    <ChevronDown className="w-4 h-4" />
                  ) : (
                    <ChevronRight className="w-4 h-4" />
                  )}
                </button>
                {isExpanded && (
                  <div className="ml-4 mt-1 space-y-1">
                    {item.children!.map((child) => (
                      <Link
                        key={child.path}
                        to={child.path}
                        className={cn(
                          "flex items-center space-x-3 px-4 py-2 rounded-lg text-sm transition-colors",
                          location.pathname === child.path
                            ? "bg-green-50 text-green-700 font-medium"
                            : "text-gray-600 hover:bg-gray-50"
                        )}
                      >
                        {child.icon}
                        <span>{child.name}</span>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            );
          }

          return (
            <Link
              key={item.path}
              to={item.path}
              className={cn(
                "flex items-center space-x-3 px-4 py-3 rounded-lg transition-colors",
                active
                  ? "bg-green-50 text-green-700 font-medium"
                  : "text-gray-700 hover:bg-gray-50"
              )}
            >
              {item.icon}
              <span>{item.name}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
