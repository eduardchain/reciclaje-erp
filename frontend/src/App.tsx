import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import Layout from "@/components/layout/Layout";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { PermissionGate } from "@/components/auth/PermissionGate";
import Dashboard from "@/pages/Dashboard";
import Login from "@/pages/Login";
import NotFound from "@/pages/NotFound";
import PurchasesPage from "@/pages/purchases/PurchasesPage";
import PurchaseCreatePage from "@/pages/purchases/PurchaseCreatePage";
import PurchaseDetailPage from "@/pages/purchases/PurchaseDetailPage";
import PurchaseEditPage from "@/pages/purchases/PurchaseEditPage";
import PurchaseLiquidatePage from "@/pages/purchases/PurchaseLiquidatePage";
import SalesPage from "@/pages/sales/SalesPage";
import SaleCreatePage from "@/pages/sales/SaleCreatePage";
import SaleDetailPage from "@/pages/sales/SaleDetailPage";
import SaleEditPage from "@/pages/sales/SaleEditPage";
import SaleLiquidatePage from "@/pages/sales/SaleLiquidatePage";
import DoubleEntriesPage from "@/pages/double-entries/DoubleEntriesPage";
import DoubleEntryCreatePage from "@/pages/double-entries/DoubleEntryCreatePage";
import DoubleEntryEditPage from "@/pages/double-entries/DoubleEntryEditPage";
import DoubleEntryLiquidatePage from "@/pages/double-entries/DoubleEntryLiquidatePage";
import DoubleEntryDetailPage from "@/pages/double-entries/DoubleEntryDetailPage";
import TreasuryPage from "@/pages/treasury/TreasuryPage";
import MovementCreatePage from "@/pages/treasury/MovementCreatePage";
import MovementDetailPage from "@/pages/treasury/MovementDetailPage";
import ProvisionsPage from "@/pages/treasury/ProvisionsPage";
import AccountStatementPage from "@/pages/treasury/AccountStatementPage";
import TreasuryDashboardPage from "@/pages/treasury/TreasuryDashboardPage";
import AccountMovementsPage from "@/pages/treasury/AccountMovementsPage";
import LiabilitiesPage from "@/pages/treasury/LiabilitiesPage";
import ScheduledExpensesPage from "@/pages/treasury/ScheduledExpensesPage";
import ScheduledExpenseCreatePage from "@/pages/treasury/ScheduledExpenseCreatePage";
import ScheduledExpenseDetailPage from "@/pages/treasury/ScheduledExpenseDetailPage";
import FixedAssetsPage from "@/pages/treasury/FixedAssetsPage";
import FixedAssetCreatePage from "@/pages/treasury/FixedAssetCreatePage";
import FixedAssetDetailPage from "@/pages/treasury/FixedAssetDetailPage";
import FixedAssetEditPage from "@/pages/treasury/FixedAssetEditPage";
import ProfitDistributionPage from "@/pages/treasury/ProfitDistributionPage";
import BatchExpensesPage from "@/pages/treasury/BatchExpensesPage";
import StockPage from "@/pages/inventory/StockPage";
import MovementHistoryPage from "@/pages/inventory/MovementHistoryPage";
import AdjustmentsPage from "@/pages/inventory/AdjustmentsPage";
import AdjustmentCreatePage from "@/pages/inventory/AdjustmentCreatePage";
import AdjustmentDetailPage from "@/pages/inventory/AdjustmentDetailPage";
import TransformationsPage from "@/pages/inventory/TransformationsPage";
import TransformationCreatePage from "@/pages/inventory/TransformationCreatePage";
import TransformationDetailPage from "@/pages/inventory/TransformationDetailPage";
import ValuationPage from "@/pages/inventory/ValuationPage";
import TransitPage from "@/pages/inventory/TransitPage";
import ProfitAndLossPage from "@/pages/reports/ProfitAndLossPage";
import CashFlowPage from "@/pages/reports/CashFlowPage";
import BalanceSheetPage from "@/pages/reports/BalanceSheetPage";
import BalanceDetailedPage from "@/pages/reports/BalanceDetailedPage";
import PurchaseReportPage from "@/pages/reports/PurchaseReportPage";
import SalesReportPage from "@/pages/reports/SalesReportPage";
import MarginAnalysisPage from "@/pages/reports/MarginAnalysisPage";
import ThirdPartyBalancesPage from "@/pages/reports/ThirdPartyBalancesPage";
import AuditBalancesPage from "@/pages/reports/AuditBalancesPage";
import ProfitabilityBUPage from "@/pages/reports/ProfitabilityBUPage";
import RealCostMaterialPage from "@/pages/reports/RealCostMaterialPage";
import ThirdPartiesPage from "@/pages/third-parties/ThirdPartiesPage";
import MaterialsPage from "@/pages/materials/MaterialsPage";
import CategoriesPage from "@/pages/materials/CategoriesPage";
import WarehousesPage from "@/pages/config/WarehousesPage";
import MoneyAccountsPage from "@/pages/config/MoneyAccountsPage";
import BusinessUnitsPage from "@/pages/config/BusinessUnitsPage";
import ExpenseCategoriesPage from "@/pages/config/ExpenseCategoriesPage";
import PriceListsPage from "@/pages/config/PriceListsPage";
import ThirdPartyCategoriesPage from "@/pages/config/ThirdPartyCategoriesPage";
import RolesPage from "@/pages/admin/RolesPage";
import RoleEditPage from "@/pages/admin/RoleEditPage";
import UsersPage from "@/pages/admin/UsersPage";
import SystemOrganizationsPage from "@/pages/system/SystemOrganizationsPage";
import SystemUsersPage from "@/pages/system/SystemUsersPage";
import { ROUTES } from "@/utils/constants";

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
              <Route path="/purchases/:id/edit" element={<P permission="purchases.edit"><PurchaseEditPage /></P>} />
              <Route path="/purchases/:id/liquidate" element={<P permission="purchases.liquidate"><PurchaseLiquidatePage /></P>} />
              <Route path="/purchases/:id" element={<P permission="purchases.view"><PurchaseDetailPage /></P>} />
              {/* Ventas */}
              <Route path={ROUTES.SALES} element={<P permission="sales.view"><SalesPage /></P>} />
              <Route path={ROUTES.SALES_NEW} element={<P permission="sales.create"><SaleCreatePage /></P>} />
              <Route path="/sales/:id/edit" element={<P permission="sales.edit"><SaleEditPage /></P>} />
              <Route path="/sales/:id/liquidate" element={<P permission="sales.liquidate"><SaleLiquidatePage /></P>} />
              <Route path="/sales/:id" element={<P permission="sales.view"><SaleDetailPage /></P>} />
              {/* Doble Partida */}
              <Route path={ROUTES.DOUBLE_ENTRIES} element={<P permission="double_entries.view"><DoubleEntriesPage /></P>} />
              <Route path={ROUTES.DOUBLE_ENTRIES_NEW} element={<P permission="double_entries.create"><DoubleEntryCreatePage /></P>} />
              <Route path="/double-entries/:id/edit" element={<P permission="double_entries.edit"><DoubleEntryEditPage /></P>} />
              <Route path="/double-entries/:id/liquidate" element={<P permission="double_entries.liquidate"><DoubleEntryLiquidatePage /></P>} />
              <Route path="/double-entries/:id" element={<P permission="double_entries.view"><DoubleEntryDetailPage /></P>} />
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
              <Route path="/treasury/scheduled-expenses/:id" element={<P permission="treasury.view_scheduled"><ScheduledExpenseDetailPage /></P>} />
              <Route path={ROUTES.TREASURY_FIXED_ASSETS} element={<P permission="treasury.view_fixed_assets"><FixedAssetsPage /></P>} />
              <Route path={ROUTES.TREASURY_FIXED_ASSETS_NEW} element={<P permission="treasury.manage_fixed_assets"><FixedAssetCreatePage /></P>} />
              <Route path="/treasury/fixed-assets/:id/edit" element={<P permission="treasury.manage_fixed_assets"><FixedAssetEditPage /></P>} />
              <Route path="/treasury/fixed-assets/:id" element={<P permission="treasury.view_fixed_assets"><FixedAssetDetailPage /></P>} />
              <Route path={ROUTES.TREASURY_PROFIT_DISTRIBUTION} element={<P permission="treasury.manage_distributions"><ProfitDistributionPage /></P>} />
              <Route path={ROUTES.TREASURY_BATCH_EXPENSES} element={<P permission="treasury.create_movements"><BatchExpensesPage /></P>} />
              <Route path="/treasury/:id" element={<P permission="treasury.view_movements"><MovementDetailPage /></P>} />
              {/* Inventario */}
              <Route path={ROUTES.INVENTORY} element={<P permission="inventory.view"><StockPage /></P>} />
              <Route path={ROUTES.INVENTORY_MOVEMENTS} element={<P permission="inventory.view_movements"><MovementHistoryPage /></P>} />
              <Route path={ROUTES.INVENTORY_ADJUSTMENTS} element={<P permission="inventory.view_adjustments"><AdjustmentsPage /></P>} />
              <Route path={ROUTES.INVENTORY_ADJUSTMENTS_NEW} element={<P permission="inventory.adjust"><AdjustmentCreatePage /></P>} />
              <Route path="/inventory/adjustments/:id" element={<P permission="inventory.view_adjustments"><AdjustmentDetailPage /></P>} />
              <Route path={ROUTES.INVENTORY_TRANSFORMATIONS} element={<P permission="transformations.view"><TransformationsPage /></P>} />
              <Route path={ROUTES.INVENTORY_TRANSFORMATIONS_NEW} element={<P permission="transformations.create"><TransformationCreatePage /></P>} />
              <Route path="/inventory/transformations/:id" element={<P permission="transformations.view"><TransformationDetailPage /></P>} />
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
              <Route path={ROUTES.SYSTEM_ORGANIZATIONS} element={<SystemOrganizationsPage />} />
              <Route path={ROUTES.SYSTEM_USERS} element={<SystemUsersPage />} />
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
