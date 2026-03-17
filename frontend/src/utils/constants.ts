export const API_BASE_URL = (import.meta.env.VITE_API_URL as string) || "http://localhost:8000";

export const APP_NAME = "EcoBalance";
export const APP_VERSION = "0.1.0";

export const ROUTES = {
  HOME: "/",
  DASHBOARD: "/",
  LOGIN: "/login",

  // Operaciones
  PURCHASES: "/purchases",
  PURCHASES_NEW: "/purchases/new",
  PURCHASES_EDIT: "/purchases/:id/edit",
  SALES: "/sales",
  SALES_NEW: "/sales/new",
  SALES_EDIT: "/sales/:id/edit",
  DOUBLE_ENTRIES: "/double-entries",
  DOUBLE_ENTRIES_NEW: "/double-entries/new",

  // Tesoreria
  TREASURY: "/treasury",
  TREASURY_NEW: "/treasury/new",
  TREASURY_PROVISIONS: "/treasury/provisions",
  TREASURY_ACCOUNT_STATEMENT: "/treasury/account-statement",
  TREASURY_DASHBOARD: "/treasury/dashboard",
  TREASURY_ACCOUNT_MOVEMENTS: "/treasury/account-movements",
  TREASURY_LIABILITIES: "/treasury/liabilities",
  TREASURY_SCHEDULED: "/treasury/scheduled-expenses",
  TREASURY_SCHEDULED_NEW: "/treasury/scheduled-expenses/new",
  TREASURY_FIXED_ASSETS: "/treasury/fixed-assets",
  TREASURY_FIXED_ASSETS_NEW: "/treasury/fixed-assets/new",
  TREASURY_PROFIT_DISTRIBUTION: "/treasury/profit-distribution",

  // Inventario
  INVENTORY: "/inventory",
  INVENTORY_MOVEMENTS: "/inventory/movements",
  INVENTORY_ADJUSTMENTS: "/inventory/adjustments",
  INVENTORY_ADJUSTMENTS_NEW: "/inventory/adjustments/new",
  INVENTORY_TRANSFORMATIONS: "/inventory/transformations",
  INVENTORY_TRANSFORMATIONS_NEW: "/inventory/transformations/new",
  INVENTORY_VALUATION: "/inventory/valuation",
  INVENTORY_TRANSIT: "/inventory/transit",

  // Reportes
  REPORTS: "/reports",
  REPORTS_PL: "/reports/profit-and-loss",
  REPORTS_CASH_FLOW: "/reports/cash-flow",
  REPORTS_BALANCE_SHEET: "/reports/balance-sheet",
  REPORTS_BALANCE_DETAILED: "/reports/balance-detailed",
  REPORTS_PURCHASES: "/reports/purchases",
  REPORTS_SALES: "/reports/sales",
  REPORTS_MARGINS: "/reports/margins",
  REPORTS_BALANCES: "/reports/balances",
  REPORTS_AUDIT: "/reports/audit",

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
  CONFIG_THIRD_PARTY_CATEGORIES: "/config/third-party-categories",

  // Admin
  ADMIN_ROLES: "/admin/roles",
  ADMIN_USERS: "/admin/users",

  // Sistema (super admin)
  SYSTEM_ORGANIZATIONS: "/system/organizations",
  SYSTEM_USERS: "/system/users",
} as const;
