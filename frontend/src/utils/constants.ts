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
  TREASURY_BATCH_EXPENSES: "/treasury/batch-expenses",

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
  REPORTS_PROFITABILITY_BU: "/reports/profitability-bu",
  REPORTS_REAL_COST: "/reports/real-cost-material",

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

  // Detail pages (antes hardcodeados en App.tsx)
  PURCHASE_DETAIL: "/purchases/:id",
  PURCHASE_EDIT: "/purchases/:id/edit",
  PURCHASE_LIQUIDATE: "/purchases/:id/liquidate",
  SALE_DETAIL: "/sales/:id",
  SALE_EDIT: "/sales/:id/edit",
  SALE_LIQUIDATE: "/sales/:id/liquidate",
  DOUBLE_ENTRY_DETAIL: "/double-entries/:id",
  DOUBLE_ENTRY_EDIT: "/double-entries/:id/edit",
  DOUBLE_ENTRY_LIQUIDATE: "/double-entries/:id/liquidate",
  TREASURY_MOVEMENT_DETAIL: "/treasury/:id",
  TREASURY_FIXED_ASSET_DETAIL: "/treasury/fixed-assets/:id",
  TREASURY_FIXED_ASSET_EDIT: "/treasury/fixed-assets/:id/edit",
  TREASURY_SCHEDULED_DETAIL: "/treasury/scheduled-expenses/:id",
  INVENTORY_ADJUSTMENT_DETAIL: "/inventory/adjustments/:id",
  INVENTORY_TRANSFORMATION_DETAIL: "/inventory/transformations/:id",
} as const;

export function buildRoute(template: string, params: Record<string, string>): string {
  return Object.entries(params).reduce(
    (path, [key, value]) => path.replace(`:${key}`, value),
    template
  );
}
