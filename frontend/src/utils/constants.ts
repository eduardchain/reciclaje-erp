export const API_BASE_URL = (import.meta.env.VITE_API_URL as string) || "http://localhost:8000";

export const APP_NAME = "ReciclaTrac";
export const APP_VERSION = "0.1.0";

export const ROUTES = {
  HOME: "/",
  DASHBOARD: "/",
  LOGIN: "/login",

  // Operaciones
  PURCHASES: "/purchases",
  PURCHASES_NEW: "/purchases/new",
  SALES: "/sales",
  SALES_NEW: "/sales/new",
  DOUBLE_ENTRIES: "/double-entries",
  DOUBLE_ENTRIES_NEW: "/double-entries/new",

  // Tesoreria
  TREASURY: "/treasury",
  TREASURY_NEW: "/treasury/new",

  // Inventario
  INVENTORY: "/inventory",
  INVENTORY_MOVEMENTS: "/inventory/movements",
  INVENTORY_ADJUSTMENTS: "/inventory/adjustments",
  INVENTORY_ADJUSTMENTS_NEW: "/inventory/adjustments/new",
  INVENTORY_TRANSFORMATIONS: "/inventory/transformations",
  INVENTORY_TRANSFORMATIONS_NEW: "/inventory/transformations/new",

  // Reportes
  REPORTS: "/reports",
  REPORTS_PL: "/reports/profit-and-loss",
  REPORTS_CASH_FLOW: "/reports/cash-flow",
  REPORTS_BALANCE_SHEET: "/reports/balance-sheet",
  REPORTS_PURCHASES: "/reports/purchases",
  REPORTS_SALES: "/reports/sales",
  REPORTS_MARGINS: "/reports/margins",
  REPORTS_BALANCES: "/reports/balances",

  // Maestros
  THIRD_PARTIES: "/third-parties",
  MATERIALS: "/materials",
  MATERIALS_CATEGORIES: "/materials/categories",

  // Configuracion
  CONFIG: "/config",
  CONFIG_WAREHOUSES: "/config/warehouses",
  CONFIG_ACCOUNTS: "/config/accounts",
  CONFIG_BUSINESS_UNITS: "/config/business-units",
  CONFIG_EXPENSE_CATEGORIES: "/config/expense-categories",
  CONFIG_PRICE_LISTS: "/config/price-lists",
} as const;
