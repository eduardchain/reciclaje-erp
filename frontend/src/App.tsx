import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import Layout from "@/components/layout/Layout";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
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
import DoubleEntryDetailPage from "@/pages/double-entries/DoubleEntryDetailPage";
import TreasuryPage from "@/pages/treasury/TreasuryPage";
import MovementCreatePage from "@/pages/treasury/MovementCreatePage";
import MovementDetailPage from "@/pages/treasury/MovementDetailPage";
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
import PurchaseReportPage from "@/pages/reports/PurchaseReportPage";
import SalesReportPage from "@/pages/reports/SalesReportPage";
import MarginAnalysisPage from "@/pages/reports/MarginAnalysisPage";
import ThirdPartyBalancesPage from "@/pages/reports/ThirdPartyBalancesPage";
import ThirdPartiesPage from "@/pages/third-parties/ThirdPartiesPage";
import MaterialsPage from "@/pages/materials/MaterialsPage";
import CategoriesPage from "@/pages/materials/CategoriesPage";
import WarehousesPage from "@/pages/config/WarehousesPage";
import MoneyAccountsPage from "@/pages/config/MoneyAccountsPage";
import BusinessUnitsPage from "@/pages/config/BusinessUnitsPage";
import ExpenseCategoriesPage from "@/pages/config/ExpenseCategoriesPage";
import PriceListsPage from "@/pages/config/PriceListsPage";
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
              <Route path={ROUTES.PURCHASES} element={<PurchasesPage />} />
              <Route path={ROUTES.PURCHASES_NEW} element={<PurchaseCreatePage />} />
              <Route path="/purchases/:id/edit" element={<PurchaseEditPage />} />
              <Route path="/purchases/:id/liquidate" element={<PurchaseLiquidatePage />} />
              <Route path="/purchases/:id" element={<PurchaseDetailPage />} />
              {/* Ventas */}
              <Route path={ROUTES.SALES} element={<SalesPage />} />
              <Route path={ROUTES.SALES_NEW} element={<SaleCreatePage />} />
              <Route path="/sales/:id/edit" element={<SaleEditPage />} />
              <Route path="/sales/:id/liquidate" element={<SaleLiquidatePage />} />
              <Route path="/sales/:id" element={<SaleDetailPage />} />
              {/* Doble Partida */}
              <Route path={ROUTES.DOUBLE_ENTRIES} element={<DoubleEntriesPage />} />
              <Route path={ROUTES.DOUBLE_ENTRIES_NEW} element={<DoubleEntryCreatePage />} />
              <Route path="/double-entries/:id" element={<DoubleEntryDetailPage />} />
              {/* Tesoreria */}
              <Route path={ROUTES.TREASURY} element={<TreasuryPage />} />
              <Route path={ROUTES.TREASURY_NEW} element={<MovementCreatePage />} />
              <Route path="/treasury/:id" element={<MovementDetailPage />} />
              {/* Inventario */}
              <Route path={ROUTES.INVENTORY} element={<StockPage />} />
              <Route path={ROUTES.INVENTORY_MOVEMENTS} element={<MovementHistoryPage />} />
              <Route path={ROUTES.INVENTORY_ADJUSTMENTS} element={<AdjustmentsPage />} />
              <Route path={ROUTES.INVENTORY_ADJUSTMENTS_NEW} element={<AdjustmentCreatePage />} />
              <Route path="/inventory/adjustments/:id" element={<AdjustmentDetailPage />} />
              <Route path={ROUTES.INVENTORY_TRANSFORMATIONS} element={<TransformationsPage />} />
              <Route path={ROUTES.INVENTORY_TRANSFORMATIONS_NEW} element={<TransformationCreatePage />} />
              <Route path="/inventory/transformations/:id" element={<TransformationDetailPage />} />
              <Route path={ROUTES.INVENTORY_VALUATION} element={<ValuationPage />} />
              <Route path={ROUTES.INVENTORY_TRANSIT} element={<TransitPage />} />
              {/* Reportes */}
              <Route path={ROUTES.REPORTS} element={<ProfitAndLossPage />} />
              <Route path={ROUTES.REPORTS_PL} element={<ProfitAndLossPage />} />
              <Route path={ROUTES.REPORTS_CASH_FLOW} element={<CashFlowPage />} />
              <Route path={ROUTES.REPORTS_BALANCE_SHEET} element={<BalanceSheetPage />} />
              <Route path={ROUTES.REPORTS_PURCHASES} element={<PurchaseReportPage />} />
              <Route path={ROUTES.REPORTS_SALES} element={<SalesReportPage />} />
              <Route path={ROUTES.REPORTS_MARGINS} element={<MarginAnalysisPage />} />
              <Route path={ROUTES.REPORTS_BALANCES} element={<ThirdPartyBalancesPage />} />
              {/* Maestros */}
              <Route path={ROUTES.THIRD_PARTIES} element={<ThirdPartiesPage />} />
              <Route path={ROUTES.MATERIALS} element={<MaterialsPage />} />
              <Route path={ROUTES.MATERIALS_CATEGORIES} element={<CategoriesPage />} />
              {/* Configuracion */}
              <Route path={ROUTES.CONFIG} element={<WarehousesPage />} />
              <Route path={ROUTES.CONFIG_WAREHOUSES} element={<WarehousesPage />} />
              <Route path={ROUTES.CONFIG_ACCOUNTS} element={<MoneyAccountsPage />} />
              <Route path={ROUTES.CONFIG_BUSINESS_UNITS} element={<BusinessUnitsPage />} />
              <Route path={ROUTES.CONFIG_EXPENSE_CATEGORIES} element={<ExpenseCategoriesPage />} />
              <Route path={ROUTES.CONFIG_PRICE_LISTS} element={<PriceListsPage />} />
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
