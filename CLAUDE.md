# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**IMPORTANTE: Siempre actualizar este archivo con decisiones importantes, cambios arquitectonicos, y nueva funcionalidad implementada. Esto es critico para mantener contexto entre sesiones.**

## Project Overview

EcoBalance is a multi-tenant ERP system for recycling companies (buying/selling metal and material scraps). The project has a Python/FastAPI backend and a React/TypeScript frontend.

## Common Commands

### Backend (run from `/backend/`)

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --port 8000

# Run database migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Run all tests (requires test PostgreSQL on port 5433)
pytest

# Run a single test file
pytest tests/test_api_purchases.py -xvs

# Run a single test method
pytest tests/test_api_purchases.py::TestPurchaseCreation::test_create_purchase -xvs

# Run tests with coverage report
pytest --cov=app --cov-report=html
```

### Frontend (run from `/frontend/`)

```bash
npm install
npm run dev       # Dev server on port 5173
npm run build     # Production build
npm run lint      # ESLint
```

### Database

```bash
# Dev database (port 5432)
docker-compose up -d

# Test database (port 5433) — required before running tests
docker-compose -f docker-compose.test.yml up -d
```

## Architecture

### Backend (`backend/app/`)

Layered architecture: **Endpoints → Services → Models**, with Pydantic schemas for validation.

- **`api/v1/endpoints/`** — FastAPI route handlers. Each module (purchases, sales, etc.) has its own router.
- **`api/deps.py`** — Dependency injection: `get_db()`, `get_current_user()`, `get_required_org_context()`, `get_optional_org_context()`. The org context dependencies extract `X-Organization-ID` from request headers.
- **`services/`** — Business logic. All services extend `CRUDBase` (generic CRUD with pagination, soft delete, search, and automatic `organization_id` filtering).
- **`models/`** — SQLAlchemy 2.0 ORM models. All domain models inherit `TimestampMixin` (created_at/updated_at) and `OrganizationMixin` (organization_id FK).
- **`schemas/`** — Pydantic v2 schemas for request/response validation. Use `model_validate` with `from_attributes=True`.
- **`core/config.py`** — Pydantic Settings loaded from env vars.
- **`core/security.py`** — JWT token creation/verification, password hashing with bcrypt.
- **`core/database.py`** — SQLAlchemy engine and session setup.
- **`models/base.py`** — `GUID` type (cross-database UUID), `Base`, `TimestampMixin`, `OrganizationMixin`.

### Frontend (`frontend/src/`)

- React 18 + TypeScript + Vite
- State management: Zustand (`stores/authStore.ts` — token, user, organizationId persisted in localStorage)
- Data fetching: TanStack React Query + Axios
- Styling: Tailwind CSS + shadcn/ui (all components installed)
- Icons: lucide-react (no inline SVGs)
- Toasts: sonner
- Tables: @tanstack/react-table via `DataTable` shared component
- Forms: useState pattern (react-hook-form installed but not used yet)

**Architecture:**
- `services/api.ts` — Axios client with JWT auto-attach, X-Organization-ID header from authStore, 401 redirect. Default export `apiClient`.
- `services/*.ts` — 14 service files (auth, organizations, purchases, sales, doubleEntries, moneyMovements, inventory, reports, thirdParties, materials, warehouses, moneyAccounts, masterData)
- `hooks/use*.ts` — 11 hook files wrapping React Query with toast notifications on mutations (includes `usePriceSuggestions`)
- `types/*.ts` — 15 type files matching backend Pydantic schemas exactly
- `components/shared/` — 12 reusable components (DataTable, PageHeader, StatusBadge, MoneyDisplay, DateRangePicker, SearchInput, ConfirmDialog, EmptyState, EntitySelect, WarningsList, PriceSuggestion, KpiCard)
- `components/auth/` — ProtectedRoute (token + org check), OrganizationSelector
- `components/layout/` — Layout, Header (user dropdown), Sidebar (collapsible submenus)
- `pages/` — 47 page components organized by module

**Modules (all complete, 45+ routes):**
- Auth: Login, org selection, protected routes
- Dashboard: 6 metric cards + top materials/suppliers/customers + alerts
- Purchases: List (status tabs, search, date range, Items/DP/Actions columns) + Create (dynamic lines, auto-liquidate, price suggestions) + Edit (full revert-and-reapply) + Detail (liquidate/cancel/PDF)
- Sales: Like purchases + commissions + profit display + stock warnings + Edit (lines + commissions)
- Double Entries: Simultaneous buy+sell form with real-time profit calculation
- Treasury: 11 movement types with dynamic form, annulment with reason, provisions (deposit/expense), account statement with running balance, financial dashboard
- Inventory: Stock view (expandable rows with warehouse breakdown, category/warehouse filters, transfer modal), movement history (material/warehouse filters, running balance/avg cost), adjustments (4 types), transformations (multi-line destinations, balance validation), warehouse transfers, valuation page, transit page (pending purchases/sales, bottleneck alerts)
- Reports: P&L, Cash Flow, Balance Sheet, Purchase Report, Sales Report, Margin Analysis, Third Party Balances — all with date range pickers
- Third Parties: CRUD with role badges (supplier/customer/investor/provision), balance display
- Materials: CRUD + categories page
- Config: Warehouses, Money Accounts (cash/bank/digital), Business Units, Expense Categories (direct/indirect toggle), Price Lists (append-only)

**Query Key Convention:**
```
['purchases', 'list', filters] / ['purchases', 'detail', id]
['inventory', 'stock', params] / ['inventory', 'adjustments', 'list', filters]
['reports', 'dashboard', params]
['third-parties', 'suppliers', search]
```

### Key Patterns

- **Multi-tenancy**: Every query filters by `organization_id`. The `X-Organization-ID` header is required on most endpoints. `CRUDBase._base_query()` enforces this automatically.
- **Soft delete**: Records use `is_active` flag instead of hard deletion.
- **3-step purchase workflow**: register (stock to transit, no financial effects) → liquidate (confirm prices, avg cost, supplier balance, stock transit→liquidated) → pay (separate MoneyMovement `payment_to_supplier`). Sales use 2-step: register → collect/pay.
- **Sequential numbering**: Purchase/sale/double-entry numbers are auto-incremented per organization.
- **Inventory audit trail**: All stock changes create `InventoryMovement` records.
- **Moving average cost**: Material `current_average_cost` is recalculated at purchase LIQUIDATION (not creation). Creation sets `unit_cost=0` on InventoryMovement.
- **Stock separation**: `current_stock_liquidated` (paid, available for sale) vs `current_stock_transit` (registered but unpaid). `current_stock` = total for backward compat.
- **Audit fields**: Purchases and Sales track `created_by` and `liquidated_by` (user UUIDs).
- **Price history & suggestions**: `PriceList` is append-only — each price update creates a new record. The "current" price is the most recent by `created_at`. Bulk endpoint `GET /price-lists/current` returns all current prices. Frontend `usePriceSuggestions()` hook auto-fills prices on material selection in purchase/sale/double-entry forms via `PriceSuggestion` component.
- **Treasury movements**: `MoneyMovement` tracks all money flows with 11 types (payment_to_supplier, collection_from_client, expense, service_income, transfer_out/in, capital_injection/return, commission_payment, provision_deposit, provision_expense). Each movement affects exactly ONE account (except provision_expense which has account_id=None). Transfers create a linked pair (transfer_out + transfer_in). Status is `confirmed` or `annulled` (with reason/date/user audit). Independent of purchase/sale liquidation.
- **Provision system**: ThirdParty entities with `is_provision=True` act as fund pools. `provision_deposit` removes money from an account and adds to provision (both balances decrease — negative = funds available). `provision_expense` only affects provision (balance increases, no account touched, account_id=NULL). Fund validation: blocks if overspent (balance > 0) or insufficient funds. Annulation of deposits is allowed even if overspent (consistent with negative stock policy).
- **Account statement (estado de cuenta)**: `GET /money-movements/third-party/{id}` returns movements with `balance_after` (running balance) and `opening_balance` when date_from is provided. Balance direction determined by THIRD_PARTY_BALANCE_DIRECTION map per movement type.
- **Treasury Dashboard**: `GET /reports/treasury-dashboard` returns accounts by type (cash/bank/digital), CxC/CxP, provisions with available funds, MTD income/expense, last 10 movements.
- **Negative stock allowed (RN-INV-03)**: Sales, adjustments, and transformations PERMIT negative stock. Instead of blocking, they return a `warnings[]` field in the response with descriptive messages. This is a global policy decision.
- **Inventory adjustments**: 4 types (increase, decrease, recount, zero_out). All affect `current_stock_liquidated` only (not transit). Increase recalculates avg cost; decrease/recount/zero_out use current avg cost.
- **Material transformation**: Disassembly of composite materials into components. Cost distribution: proportional by weight (default) or manual. Validation: `sum(destination_quantities) + waste == source_quantity`. Creates InventoryMovement for source and each destination.
- **Per-warehouse stock**: Calculated on-the-fly from `SUM(inventory_movements.quantity) GROUP BY warehouse_id`. No denormalized table.
- **Warehouse transfers**: Creates pair of InventoryMovement (transfer type, -qty source / +qty destination). Global stock unchanged.
- **Material cost history**: `MaterialCostHistory` table records every change to `current_average_cost`. Source types: `purchase_liquidation`, `adjustment_increase`, `transformation_in`. Enables precise cost reversal on cancellation and blocks cancellation if subsequent operations affected the same material's cost. Ordering uses `created_at` (monotonic) with `id` tiebreaker.

### Design Decisions

1. **Doble Partida SIN movimientos de inventario**: En operaciones "Pasa Mano" (compra+venta simultanea), el material NO toca bodega. Crear movimientos de inventario inflaria el costo promedio y distorsionaria estadisticas. La doble partida solo afecta saldos de terceros y cuentas.

2. **Estados**: Compras y Ventas usan `registered | liquidated | cancelled`. Workflow identico de 3 pasos: CREATE (stock) → LIQUIDATE (confirmar precios, saldo tercero, comisiones) → PAY/COLLECT (MoneyMovement separado).

3. **Stock liquidado vs transito**: Las compras registradas crean stock en transito (sin efectos financieros: ni saldo proveedor, ni costo promedio). Al LIQUIDAR se confirman precios, se recalcula costo promedio, se actualiza saldo proveedor, y stock pasa de transito a liquidado. El PAGO al proveedor es una operacion separada via MoneyMovement (`payment_to_supplier`).

4. **Categorias de gastos directos vs indirectos**: `is_direct_expense=True` indica gastos que afectan el costo del material (flete, pesaje). `is_direct_expense=False` son gastos administrativos (arriendo, servicios). Esta distincion es clave para calcular rentabilidad real.

5. **Liquidacion ≠ Pago**: La liquidacion (compras y ventas) confirma precios, actualiza saldo del tercero, y en compras recalcula costo promedio. NO mueve dinero de ninguna cuenta. El pago/cobro es una operacion separada via MoneyMovement. Los money_movements son un modulo SEPARADO para pagos/cobros manuales, gastos, transferencias, etc.

6. **Stock negativo permitido (RN-INV-03)**: Ventas, ajustes y transformaciones permiten stock negativo. No bloquean la operacion. Retornan `warnings[]` en la respuesta con mensajes descriptivos. El frontend puede mostrar estas advertencias al usuario.

7. **Stock por bodega on-the-fly**: No hay tabla denormalizada de stock por bodega. Se calcula desde `SUM(inventory_movements.quantity) GROUP BY warehouse_id`. Solo se denormalizara si el rendimiento lo requiere.

8. **COGS metodo directo**: El costo de ventas se calcula como `SUM(sale_lines.unit_cost × quantity)`, capturando el costo promedio movil al momento de cada venta. Mas preciso que el metodo tradicional (inventario inicial + compras - inventario final) dado el sistema de inventario perpetuo.

9. **Doble Partida en P&L como linea separada**: En el Estado de Resultados, la utilidad de operaciones Pasa Mano aparece como "Utilidad Pasa Mano" (linea separada), NO incluida en Sales Revenue ni COGS. Esto da visibilidad clara al margen de cada tipo de operacion.

10. **Cash Flow hibrido**: El flujo de caja combina DOS fuentes independientes: liquidacion de compras/ventas (cambios directos a account.balance) Y money_movements (pagos/cobros manuales). Opening balance se calcula restando todos los cambios desde date_from al balance actual de cuentas.

11. **Edicion de compras/ventas con Revert and Re-apply**: Las compras y ventas en estado `registered` (sin doble partida) se pueden editar completamente (metadata + lineas + proveedor/cliente). La estrategia es revertir todos los efectos colaterales (stock, movimientos de inventario, saldos de terceros), eliminar las lineas y movimientos originales, y re-aplicar las nuevas lineas con calculos frescos. Compras bloquean si no hay stock suficiente para revertir; ventas permiten stock negativo con warnings.

12. **PDF export con jsPDF**: `utils/pdfExport.ts` exporta compras y ventas a PDF con header, info general, tabla de lineas (con comisiones en ventas), y totales. Se usa desde el menu de acciones en listados y boton en detalle.

13. **Cancelacion con reversal de costo**: Al cancelar compras liquidadas, ajustes increase, o transformaciones, el costo promedio se revierte al valor anterior usando `MaterialCostHistory`. Si hay operaciones posteriores que afectaron el mismo material, la cancelacion se BLOQUEA con HTTP 400 y mensaje descriptivo indicando que operaciones deben cancelarse primero. El COGS de ventas ya registradas NO se recalcula (correcto por diseno: COGS refleja costo al momento de la venta).

14. **Precio sugerido desde lista de precios**: Al seleccionar un material en formularios de compra/venta/doble partida, el precio se auto-llena desde la lista de precios vigente (solo si el campo esta vacio). Un hint clickable `"Lista: $ X"` permite restaurar el precio sugerido. Materiales sin precio en la lista no muestran sugerencia.

### Business Modules (Implemented)

| Module | Endpoints | Description |
|--------|-----------|-------------|
| Auth | `/api/v1/auth/` | JWT login, registration |
| Organizations | `/api/v1/organizations/` | CRUD + member management, roles (admin/manager/user/accountant/viewer) |
| Materials | `/api/v1/materials/` | Materials + categories + business units, stock tracking |
| Third Parties | `/api/v1/third-parties/` | Multi-role entities (supplier/customer/investor/provision) with balance tracking |
| Purchases | `/api/v1/purchases/` | 3-step buy workflow (register→liquidate→pay), supplier debt, inventory movements, full edit (PATCH) |
| Sales | `/api/v1/sales/` | 2-step sell workflow, commissions (percentage/fixed), profit calculation, full edit (PATCH) |
| Double Entries | `/api/v1/double-entries/` | Simultaneous buy+sell ("Pasa Mano"), no inventory movement |
| Money Accounts | `/api/v1/money-accounts/` | Cash, bank, digital accounts (Nequi, etc.) |
| Warehouses | `/api/v1/warehouses/` | Physical storage locations |
| Business Units | `/api/v1/business-units/` | P&L analysis segments (Fibras, Chatarra, etc.) |
| Price Lists | `/api/v1/price-lists/` | Historical purchase/sale prices per material |
| Expense Categories | `/api/v1/expense-categories/` | Direct/indirect expense classification for treasury |
| Treasury | `/api/v1/money-movements/` | 11 movement types (incl. provision_deposit, provision_expense), annulment with audit, account statement with running balance |
| Inventory Adjustments | `/api/v1/inventory/adjustments/` | Manual stock corrections: increase, decrease, recount, zero-out. Warehouse transfers. Annulment with stock reversal |
| Material Transformations | `/api/v1/inventory/transformations/` | Material disassembly (e.g., Motor → Copper + Iron + Aluminum + Waste). Proportional/manual cost distribution |
| Inventory Views | `/api/v1/inventory/` | Consolidated stock (filterable by category/warehouse), per-material warehouse breakdown, transit stock (pending purchases/sales/bottleneck alerts), movement history (with running balance/avg cost per material), inventory valuation |
| Reports & Dashboard | `/api/v1/reports/` | Dashboard with period comparison, P&L, Cash Flow, Balance Sheet, Purchase/Sales reports, Margin Analysis, Third Party Balances, Treasury Dashboard. All read-only |

### Testing

Tests use a separate PostgreSQL database on port 5433. `conftest.py` provides fixtures for users, organizations, auth tokens, and org headers. Async mode is auto-enabled via pytest-asyncio. Coverage target is 80%+. Current: 413 tests. Run with `./venv/bin/pytest` from backend dir.

Key fixtures: `test_user`, `auth_headers`, `org_headers` (auth + X-Organization-ID), `db_session`.

### Database

PostgreSQL 16 with Alembic migrations in `backend/alembic/`. All IDs are UUIDs (using custom `GUID` type for cross-database compatibility). Foreign keys use `CASCADE` on delete. Decimal fields use 4-decimal precision for quantities (kg) and 2-decimal for monetary values.

### Inventory Module — UX & Architecture Details

**StockPage (`/inventory`):**
- Uses manual `<Table>` (not DataTable) with Fragment-based expandable rows. Click a material row to expand inline warehouse breakdown with per-warehouse stock.
- Filters: Category (Select), Warehouse (Select), Search (text). Category and search are client-side; warehouse filter calls backend `GET /stock?warehouse_id=`.
- Expanded rows show "Trasladar" button per warehouse, "Ver Movimientos" and "Ajustar Stock" action buttons. These navigate with `?material_id=` query param.
- `WarehouseTransferModal` (Dialog) pre-fills material and source warehouse from expanded row. Uses existing `POST /inventory/adjustments/warehouse-transfer`.

**MovementHistoryPage (`/inventory/movements`):**
- Filters: Material (EntitySelect), Warehouse (Select). No client-side search — filters passed to backend.
- When `material_id` filter active, backend returns `balance_after` and `avg_cost_after` fields (running balance calculated iteratively over all movements for that material, not SQL window function). Frontend shows conditional "Balance" and "Costo Prom." columns.
- Reads `material_id` from URL search params for cross-navigation from StockPage.

**TransitPage (`/inventory/transit`):**
- Backend `GET /inventory/transit` returns: `materials` (summary), `pending_purchases` (from Purchase+PurchaseLine joins where status=registered), `pending_sales` (from Sale+SaleLine joins where status=registered), `bottleneck_alerts` (materials where `stock_transit > stock_liquidated * 0.3`).
- Frontend: 3 KpiCards + amber alert Card for bottleneck warnings + 2 DataTables (compras/ventas pendientes). Rows clickable to navigate to purchase/sale detail.

**ValuationPage (`/inventory/valuation`):**
- Frontend-only page using existing `GET /inventory/valuation` endpoint. 2 KpiCards (Valor Total, Materiales) + DataTable with client-side search.

**AdjustmentCreatePage:**
- Reads `material_id` from URL search params (`useSearchParams`) to pre-select material when navigating from StockPage.

### Comments and Language

All code comments, docstrings, migration descriptions, and variable names should be in **Spanish** where they describe business logic. Technical terms (class names, function names, SQL) remain in English per Python conventions.
