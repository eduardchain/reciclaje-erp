import { lazy } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import Layout from "@/components/layout/Layout";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { PermissionGate } from "@/components/auth/PermissionGate";
import { SuperuserGate } from "@/components/auth/SuperuserGate";
import Dashboard from "@/pages/Dashboard";
import Login from "@/pages/Login";
import NotFound from "@/pages/NotFound";
import { ROUTES } from "@/utils/constants";

// Code-splitting: cada pagina se descarga on-demand al navegar.
// Login/Dashboard/NotFound/Layout quedan eager (estan en el critical path).
// El Suspense fallback vive en Layout, envolviendo el Outlet.
const PurchasesPage = lazy(() => import("@/pages/purchases/PurchasesPage"));
const PurchaseCreatePage = lazy(() => import("@/pages/purchases/PurchaseCreatePage"));
const PurchaseDetailPage = lazy(() => import("@/pages/purchases/PurchaseDetailPage"));
const PurchaseEditPage = lazy(() => import("@/pages/purchases/PurchaseEditPage"));
const PurchaseLiquidatePage = lazy(() => import("@/pages/purchases/PurchaseLiquidatePage"));
const SalesPage = lazy(() => import("@/pages/sales/SalesPage"));
const SaleCreatePage = lazy(() => import("@/pages/sales/SaleCreatePage"));
const SaleDetailPage = lazy(() => import("@/pages/sales/SaleDetailPage"));
const SaleEditPage = lazy(() => import("@/pages/sales/SaleEditPage"));
const SaleLiquidatePage = lazy(() => import("@/pages/sales/SaleLiquidatePage"));
const DoubleEntriesPage = lazy(() => import("@/pages/double-entries/DoubleEntriesPage"));
const DoubleEntryCreatePage = lazy(() => import("@/pages/double-entries/DoubleEntryCreatePage"));
const DoubleEntryEditPage = lazy(() => import("@/pages/double-entries/DoubleEntryEditPage"));
const DoubleEntryLiquidatePage = lazy(() => import("@/pages/double-entries/DoubleEntryLiquidatePage"));
const DoubleEntryDetailPage = lazy(() => import("@/pages/double-entries/DoubleEntryDetailPage"));
const TreasuryPage = lazy(() => import("@/pages/treasury/TreasuryPage"));
const MovementCreatePage = lazy(() => import("@/pages/treasury/MovementCreatePage"));
const MovementDetailPage = lazy(() => import("@/pages/treasury/MovementDetailPage"));
const ProvisionsPage = lazy(() => import("@/pages/treasury/ProvisionsPage"));
const AccountStatementPage = lazy(() => import("@/pages/treasury/AccountStatementPage"));
const TreasuryDashboardPage = lazy(() => import("@/pages/treasury/TreasuryDashboardPage"));
const AccountMovementsPage = lazy(() => import("@/pages/treasury/AccountMovementsPage"));
const LiabilitiesPage = lazy(() => import("@/pages/treasury/LiabilitiesPage"));
const ScheduledExpensesPage = lazy(() => import("@/pages/treasury/ScheduledExpensesPage"));
const ScheduledExpenseCreatePage = lazy(() => import("@/pages/treasury/ScheduledExpenseCreatePage"));
const ScheduledExpenseDetailPage = lazy(() => import("@/pages/treasury/ScheduledExpenseDetailPage"));
const FixedAssetsPage = lazy(() => import("@/pages/treasury/FixedAssetsPage"));
const FixedAssetCreatePage = lazy(() => import("@/pages/treasury/FixedAssetCreatePage"));
const FixedAssetDetailPage = lazy(() => import("@/pages/treasury/FixedAssetDetailPage"));
const FixedAssetEditPage = lazy(() => import("@/pages/treasury/FixedAssetEditPage"));
const ProfitDistributionPage = lazy(() => import("@/pages/treasury/ProfitDistributionPage"));
const BatchExpensesPage = lazy(() => import("@/pages/treasury/BatchExpensesPage"));
const StockPage = lazy(() => import("@/pages/inventory/StockPage"));
const MovementHistoryPage = lazy(() => import("@/pages/inventory/MovementHistoryPage"));
const AdjustmentsPage = lazy(() => import("@/pages/inventory/AdjustmentsPage"));
const AdjustmentCreatePage = lazy(() => import("@/pages/inventory/AdjustmentCreatePage"));
const AdjustmentDetailPage = lazy(() => import("@/pages/inventory/AdjustmentDetailPage"));
const TransformationsPage = lazy(() => import("@/pages/inventory/TransformationsPage"));
const TransformationCreatePage = lazy(() => import("@/pages/inventory/TransformationCreatePage"));
const TransformationDetailPage = lazy(() => import("@/pages/inventory/TransformationDetailPage"));
const ValuationPage = lazy(() => import("@/pages/inventory/ValuationPage"));
const TransitPage = lazy(() => import("@/pages/inventory/TransitPage"));
const ProfitAndLossPage = lazy(() => import("@/pages/reports/ProfitAndLossPage"));
const CashFlowPage = lazy(() => import("@/pages/reports/CashFlowPage"));
const BalanceSheetPage = lazy(() => import("@/pages/reports/BalanceSheetPage"));
const BalanceDetailedPage = lazy(() => import("@/pages/reports/BalanceDetailedPage"));
const PurchaseReportPage = lazy(() => import("@/pages/reports/PurchaseReportPage"));
const SalesReportPage = lazy(() => import("@/pages/reports/SalesReportPage"));
const MarginAnalysisPage = lazy(() => import("@/pages/reports/MarginAnalysisPage"));
const ThirdPartyBalancesPage = lazy(() => import("@/pages/reports/ThirdPartyBalancesPage"));
const AuditBalancesPage = lazy(() => import("@/pages/reports/AuditBalancesPage"));
const ProfitabilityBUPage = lazy(() => import("@/pages/reports/ProfitabilityBUPage"));
const RealCostMaterialPage = lazy(() => import("@/pages/reports/RealCostMaterialPage"));
const ExpensesReportPage = lazy(() => import("@/pages/reports/ExpensesReportPage"));
const ThirdPartiesPage = lazy(() => import("@/pages/third-parties/ThirdPartiesPage"));
const MaterialsPage = lazy(() => import("@/pages/materials/MaterialsPage"));
const CategoriesPage = lazy(() => import("@/pages/materials/CategoriesPage"));
const WarehousesPage = lazy(() => import("@/pages/config/WarehousesPage"));
const MoneyAccountsPage = lazy(() => import("@/pages/config/MoneyAccountsPage"));
const BusinessUnitsPage = lazy(() => import("@/pages/config/BusinessUnitsPage"));
const ExpenseCategoriesPage = lazy(() => import("@/pages/config/ExpenseCategoriesPage"));
const PriceListsPage = lazy(() => import("@/pages/config/PriceListsPage"));
const ThirdPartyCategoriesPage = lazy(() => import("@/pages/config/ThirdPartyCategoriesPage"));
const RolesPage = lazy(() => import("@/pages/admin/RolesPage"));
const RoleEditPage = lazy(() => import("@/pages/admin/RoleEditPage"));
const UsersPage = lazy(() => import("@/pages/admin/UsersPage"));
const SystemOrganizationsPage = lazy(() => import("@/pages/system/SystemOrganizationsPage"));
const SystemUsersPage = lazy(() => import("@/pages/system/SystemUsersPage"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000,
    },
  },
});

function P({ permission, children }: { permission: string | string[]; children: React.ReactNode }) {
  return <PermissionGate permission={permission}>{children}</PermissionGate>;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Rutas publicas */}
          <Route path={ROUTES.LOGIN} element={<Login />} />

          {/* Rutas protegidas */}
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route path={ROUTES.DASHBOARD} element={<Dashboard />} />

              {/* Compras */}
              <Route path={ROUTES.PURCHASES} element={<P permission="purchases.view"><PurchasesPage /></P>} />
              <Route path={ROUTES.PURCHASES_NEW} element={<P permission="purchases.create"><PurchaseCreatePage /></P>} />
              <Route path={ROUTES.PURCHASE_EDIT} element={<P permission="purchases.edit"><PurchaseEditPage /></P>} />
              <Route path={ROUTES.PURCHASE_LIQUIDATE} element={<P permission="purchases.liquidate"><PurchaseLiquidatePage /></P>} />
              <Route path={ROUTES.PURCHASE_DETAIL} element={<P permission="purchases.view"><PurchaseDetailPage /></P>} />
              {/* Ventas */}
              <Route path={ROUTES.SALES} element={<P permission="sales.view"><SalesPage /></P>} />
              <Route path={ROUTES.SALES_NEW} element={<P permission="sales.create"><SaleCreatePage /></P>} />
              <Route path={ROUTES.SALE_EDIT} element={<P permission="sales.edit"><SaleEditPage /></P>} />
              <Route path={ROUTES.SALE_LIQUIDATE} element={<P permission="sales.liquidate"><SaleLiquidatePage /></P>} />
              <Route path={ROUTES.SALE_DETAIL} element={<P permission="sales.view"><SaleDetailPage /></P>} />
              {/* Doble Partida */}
              <Route path={ROUTES.DOUBLE_ENTRIES} element={<P permission="double_entries.view"><DoubleEntriesPage /></P>} />
              <Route path={ROUTES.DOUBLE_ENTRIES_NEW} element={<P permission="double_entries.create"><DoubleEntryCreatePage /></P>} />
              <Route path={ROUTES.DOUBLE_ENTRY_EDIT} element={<P permission="double_entries.edit"><DoubleEntryEditPage /></P>} />
              <Route path={ROUTES.DOUBLE_ENTRY_LIQUIDATE} element={<P permission="double_entries.liquidate"><DoubleEntryLiquidatePage /></P>} />
              <Route path={ROUTES.DOUBLE_ENTRY_DETAIL} element={<P permission="double_entries.view"><DoubleEntryDetailPage /></P>} />
              {/* Tesoreria */}
              <Route path={ROUTES.TREASURY} element={<P permission="treasury.view_movements"><TreasuryPage /></P>} />
              <Route path={ROUTES.TREASURY_NEW} element={<P permission="treasury.create_movements"><MovementCreatePage /></P>} />
              <Route path={ROUTES.TREASURY_PROVISIONS} element={<P permission="treasury.view_provisions"><ProvisionsPage /></P>} />
              <Route path={ROUTES.TREASURY_ACCOUNT_STATEMENT} element={<P permission="treasury.view_statements"><AccountStatementPage /></P>} />
              <Route path={ROUTES.TREASURY_DASHBOARD} element={<P permission="treasury.view_dashboard"><TreasuryDashboardPage /></P>} />
              <Route path={ROUTES.TREASURY_ACCOUNT_MOVEMENTS} element={<P permission="treasury.view_accounts"><AccountMovementsPage /></P>} />
              <Route path={ROUTES.TREASURY_LIABILITIES} element={<P permission="treasury.view_liabilities"><LiabilitiesPage /></P>} />
              <Route path={ROUTES.TREASURY_SCHEDULED} element={<P permission="treasury.view_scheduled"><ScheduledExpensesPage /></P>} />
              <Route path={ROUTES.TREASURY_SCHEDULED_NEW} element={<P permission="treasury.manage_expenses"><ScheduledExpenseCreatePage /></P>} />
              <Route path={ROUTES.TREASURY_SCHEDULED_DETAIL} element={<P permission="treasury.view_scheduled"><ScheduledExpenseDetailPage /></P>} />
              <Route path={ROUTES.TREASURY_FIXED_ASSETS} element={<P permission="treasury.view_fixed_assets"><FixedAssetsPage /></P>} />
              <Route path={ROUTES.TREASURY_FIXED_ASSETS_NEW} element={<P permission="treasury.manage_fixed_assets"><FixedAssetCreatePage /></P>} />
              <Route path={ROUTES.TREASURY_FIXED_ASSET_EDIT} element={<P permission="treasury.manage_fixed_assets"><FixedAssetEditPage /></P>} />
              <Route path={ROUTES.TREASURY_FIXED_ASSET_DETAIL} element={<P permission="treasury.view_fixed_assets"><FixedAssetDetailPage /></P>} />
              <Route path={ROUTES.TREASURY_PROFIT_DISTRIBUTION} element={<P permission="treasury.manage_distributions"><ProfitDistributionPage /></P>} />
              <Route path={ROUTES.TREASURY_BATCH_EXPENSES} element={<P permission="treasury.create_movements"><BatchExpensesPage /></P>} />
              <Route path={ROUTES.TREASURY_MOVEMENT_DETAIL} element={<P permission="treasury.view_movements"><MovementDetailPage /></P>} />
              {/* Inventario */}
              <Route path={ROUTES.INVENTORY} element={<P permission="inventory.view"><StockPage /></P>} />
              <Route path={ROUTES.INVENTORY_MOVEMENTS} element={<P permission="inventory.view_movements"><MovementHistoryPage /></P>} />
              <Route path={ROUTES.INVENTORY_ADJUSTMENTS} element={<P permission="inventory.view_adjustments"><AdjustmentsPage /></P>} />
              <Route path={ROUTES.INVENTORY_ADJUSTMENTS_NEW} element={<P permission="inventory.adjust"><AdjustmentCreatePage /></P>} />
              <Route path={ROUTES.INVENTORY_ADJUSTMENT_DETAIL} element={<P permission="inventory.view_adjustments"><AdjustmentDetailPage /></P>} />
              <Route path={ROUTES.INVENTORY_TRANSFORMATIONS} element={<P permission="transformations.view"><TransformationsPage /></P>} />
              <Route path={ROUTES.INVENTORY_TRANSFORMATIONS_NEW} element={<P permission="transformations.create"><TransformationCreatePage /></P>} />
              <Route path={ROUTES.INVENTORY_TRANSFORMATION_DETAIL} element={<P permission="transformations.view"><TransformationDetailPage /></P>} />
              <Route path={ROUTES.INVENTORY_VALUATION} element={<P permission="inventory.view_values"><ValuationPage /></P>} />
              <Route path={ROUTES.INVENTORY_TRANSIT} element={<P permission="inventory.view_transit"><TransitPage /></P>} />
              {/* Reportes */}
              <Route path={ROUTES.REPORTS} element={<P permission="reports.view_pnl"><ProfitAndLossPage /></P>} />
              <Route path={ROUTES.REPORTS_PL} element={<P permission="reports.view_pnl"><ProfitAndLossPage /></P>} />
              <Route path={ROUTES.REPORTS_CASH_FLOW} element={<P permission="reports.view_cashflow"><CashFlowPage /></P>} />
              <Route path={ROUTES.REPORTS_BALANCE_SHEET} element={<P permission="reports.view_balance"><BalanceSheetPage /></P>} />
              <Route path={ROUTES.REPORTS_BALANCE_DETAILED} element={<P permission="reports.view_balance"><BalanceDetailedPage /></P>} />
              <Route path={ROUTES.REPORTS_PURCHASES} element={<P permission="reports.view_purchases"><PurchaseReportPage /></P>} />
              <Route path={ROUTES.REPORTS_SALES} element={<P permission="reports.view_sales"><SalesReportPage /></P>} />
              <Route path={ROUTES.REPORTS_MARGINS} element={<P permission="reports.view_margins"><MarginAnalysisPage /></P>} />
              <Route path={ROUTES.REPORTS_BALANCES} element={<P permission="reports.view_third_parties"><ThirdPartyBalancesPage /></P>} />
              <Route path={ROUTES.REPORTS_AUDIT} element={<P permission="admin.view_audit"><AuditBalancesPage /></P>} />
              <Route path={ROUTES.REPORTS_PROFITABILITY_BU} element={<P permission="reports.view_pnl"><ProfitabilityBUPage /></P>} />
              <Route path={ROUTES.REPORTS_REAL_COST} element={<P permission="reports.view_pnl"><RealCostMaterialPage /></P>} />
              <Route path={ROUTES.REPORTS_EXPENSES} element={<P permission="reports.view_expenses"><ExpensesReportPage /></P>} />
              {/* Maestros */}
              <Route path={ROUTES.THIRD_PARTIES} element={<P permission="third_parties.view"><ThirdPartiesPage /></P>} />
              <Route path={ROUTES.MATERIALS} element={<P permission="materials.view"><MaterialsPage /></P>} />
              <Route path={ROUTES.MATERIALS_CATEGORIES} element={<P permission="materials.view"><CategoriesPage /></P>} />
              {/* Configuracion */}
              <Route path={ROUTES.CONFIG} element={<P permission="warehouses.view"><WarehousesPage /></P>} />
              <Route path={ROUTES.CONFIG_WAREHOUSES} element={<P permission="warehouses.view"><WarehousesPage /></P>} />
              <Route path={ROUTES.CONFIG_ACCOUNTS} element={<P permission="treasury.manage_accounts"><MoneyAccountsPage /></P>} />
              <Route path={ROUTES.CONFIG_BUSINESS_UNITS} element={<P permission="config.view_business_units"><BusinessUnitsPage /></P>} />
              <Route path={ROUTES.CONFIG_EXPENSE_CATEGORIES} element={<P permission="treasury.manage_expenses"><ExpenseCategoriesPage /></P>} />
              <Route path={ROUTES.CONFIG_PRICE_LISTS} element={<P permission="materials.view_prices"><PriceListsPage /></P>} />
              <Route path={ROUTES.CONFIG_THIRD_PARTY_CATEGORIES} element={<P permission="third_parties.create"><ThirdPartyCategoriesPage /></P>} />
              {/* Admin */}
              <Route path={ROUTES.ADMIN_ROLES} element={<P permission="admin.manage_roles"><RolesPage /></P>} />
              <Route path="/admin/roles/:id" element={<P permission="admin.manage_roles"><RoleEditPage /></P>} />
              <Route path={ROUTES.ADMIN_USERS} element={<P permission="admin.manage_users"><UsersPage /></P>} />
              {/* Sistema (super admin) */}
              <Route path={ROUTES.SYSTEM_ORGANIZATIONS} element={<SuperuserGate><SystemOrganizationsPage /></SuperuserGate>} />
              <Route path={ROUTES.SYSTEM_USERS} element={<SuperuserGate><SystemUsersPage /></SuperuserGate>} />
            </Route>
          </Route>

          {/* 404 */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" richColors />
    </QueryClientProvider>
  );
}

export default App;
