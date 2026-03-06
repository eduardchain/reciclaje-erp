# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
- `hooks/use*.ts` — 10 hook files wrapping React Query with toast notifications on mutations
- `types/*.ts` — 15 type files matching backend Pydantic schemas exactly
- `components/shared/` — 10 reusable components (DataTable, PageHeader, StatusBadge, MoneyDisplay, DateRangePicker, SearchInput, ConfirmDialog, EmptyState, EntitySelect, WarningsList)
- `components/auth/` — ProtectedRoute (token + org check), OrganizationSelector
- `components/layout/` — Layout, Header (user dropdown), Sidebar (collapsible submenus)
- `pages/` — 42 page components organized by module

**Modules (all complete, 45+ routes):**
- Auth: Login, org selection, protected routes
- Dashboard: 6 metric cards + top materials/suppliers/customers + alerts
- Purchases: List (status tabs, search, date range) + Create (dynamic lines, auto-liquidate) + Detail (liquidate/cancel)
- Sales: Like purchases + commissions + profit display + stock warnings
- Double Entries: Simultaneous buy+sell form with real-time profit calculation
- Treasury: 8 movement types with dynamic form, annulment with reason
- Inventory: Stock view (warehouse breakdown), movement history, adjustments (4 types), transformations (multi-line destinations, balance validation), warehouse transfers
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
- **2-step workflows**: Purchases and Sales support immediate completion (`auto_liquidate=True`) or deferred payment (register → liquidate/collect).
- **Sequential numbering**: Purchase/sale/double-entry numbers are auto-incremented per organization.
- **Inventory audit trail**: All stock changes create `InventoryMovement` records.
- **Moving average cost**: Material `current_average_cost` is recalculated on each purchase.
- **Stock separation**: `current_stock_liquidated` (paid, available for sale) vs `current_stock_transit` (registered but unpaid). `current_stock` = total for backward compat.
- **Audit fields**: Purchases and Sales track `created_by` and `liquidated_by` (user UUIDs).
- **Price history**: `PriceList` is append-only — each price update creates a new record. The "current" price is the most recent by `created_at`.
- **Treasury movements**: `MoneyMovement` tracks all money flows with specific types (payment_to_supplier, collection_from_client, expense, etc.). Each movement affects exactly ONE account. Transfers create a linked pair (transfer_out + transfer_in). Status is `confirmed` or `annulled` (with reason/date/user audit). Independent of purchase/sale liquidation — liquidation handles balance changes directly, money_movements are for manual payments/collections/expenses.
- **Negative stock allowed (RN-INV-03)**: Sales, adjustments, and transformations PERMIT negative stock. Instead of blocking, they return a `warnings[]` field in the response with descriptive messages. This is a global policy decision.
- **Inventory adjustments**: 4 types (increase, decrease, recount, zero_out). All affect `current_stock_liquidated` only (not transit). Increase recalculates avg cost; decrease/recount/zero_out use current avg cost.
- **Material transformation**: Disassembly of composite materials into components. Cost distribution: proportional by weight (default) or manual. Validation: `sum(destination_quantities) + waste == source_quantity`. Creates InventoryMovement for source and each destination.
- **Per-warehouse stock**: Calculated on-the-fly from `SUM(inventory_movements.quantity) GROUP BY warehouse_id`. No denormalized table.
- **Warehouse transfers**: Creates pair of InventoryMovement (transfer type, -qty source / +qty destination). Global stock unchanged.

### Design Decisions

1. **Doble Partida SIN movimientos de inventario**: En operaciones "Pasa Mano" (compra+venta simultanea), el material NO toca bodega. Crear movimientos de inventario inflaria el costo promedio y distorsionaria estadisticas. La doble partida solo afecta saldos de terceros y cuentas.

2. **3 estados de venta** (`registered | paid | cancelled`): No se necesita un estado `collected` separado. El cobro al cliente se maneja como cambio de estado a `paid`, no como un paso adicional.

3. **Stock liquidado vs transito**: Las compras registradas (sin pagar) crean stock en transito. Solo al liquidar (pagar) el stock se mueve a "liquidado" y queda disponible para venta. Esto refleja la realidad del negocio donde no se puede vender material que aun no se ha pagado.

4. **Categorias de gastos directos vs indirectos**: `is_direct_expense=True` indica gastos que afectan el costo del material (flete, pesaje). `is_direct_expense=False` son gastos administrativos (arriendo, servicios). Esta distincion es clave para calcular rentabilidad real.

5. **Money_movements independiente de liquidacion**: La liquidacion de compras/ventas actualiza saldos directamente (account, third_party). Los money_movements son un modulo SEPARADO para pagos/cobros manuales, gastos, transferencias, etc. Esto refleja que liquidar ≠ pagar/cobrar. Se puede refactorizar en el futuro para unificar.

6. **Stock negativo permitido (RN-INV-03)**: Ventas, ajustes y transformaciones permiten stock negativo. No bloquean la operacion. Retornan `warnings[]` en la respuesta con mensajes descriptivos. El frontend puede mostrar estas advertencias al usuario.

7. **Stock por bodega on-the-fly**: No hay tabla denormalizada de stock por bodega. Se calcula desde `SUM(inventory_movements.quantity) GROUP BY warehouse_id`. Solo se denormalizara si el rendimiento lo requiere.

8. **COGS metodo directo**: El costo de ventas se calcula como `SUM(sale_lines.unit_cost × quantity)`, capturando el costo promedio movil al momento de cada venta. Mas preciso que el metodo tradicional (inventario inicial + compras - inventario final) dado el sistema de inventario perpetuo.

9. **Doble Partida en P&L como linea separada**: En el Estado de Resultados, la utilidad de operaciones Pasa Mano aparece como "Utilidad Pasa Mano" (linea separada), NO incluida en Sales Revenue ni COGS. Esto da visibilidad clara al margen de cada tipo de operacion.

10. **Cash Flow hibrido**: El flujo de caja combina DOS fuentes independientes: liquidacion de compras/ventas (cambios directos a account.balance) Y money_movements (pagos/cobros manuales). Opening balance se calcula restando todos los cambios desde date_from al balance actual de cuentas.

### Business Modules (Implemented)

| Module | Endpoints | Description |
|--------|-----------|-------------|
| Auth | `/api/v1/auth/` | JWT login, registration |
| Organizations | `/api/v1/organizations/` | CRUD + member management, roles (admin/manager/user/accountant/viewer) |
| Materials | `/api/v1/materials/` | Materials + categories + business units, stock tracking |
| Third Parties | `/api/v1/third-parties/` | Multi-role entities (supplier/customer/investor/provision) with balance tracking |
| Purchases | `/api/v1/purchases/` | 2-step buy workflow, supplier debt, inventory movements |
| Sales | `/api/v1/sales/` | 2-step sell workflow, commissions (percentage/fixed), profit calculation |
| Double Entries | `/api/v1/double-entries/` | Simultaneous buy+sell ("Pasa Mano"), no inventory movement |
| Money Accounts | `/api/v1/money-accounts/` | Cash, bank, digital accounts (Nequi, etc.) |
| Warehouses | `/api/v1/warehouses/` | Physical storage locations |
| Business Units | `/api/v1/business-units/` | P&L analysis segments (Fibras, Chatarra, etc.) |
| Price Lists | `/api/v1/price-lists/` | Historical purchase/sale prices per material |
| Expense Categories | `/api/v1/expense-categories/` | Direct/indirect expense classification for treasury |
| Treasury | `/api/v1/money-movements/` | Supplier payments, customer collections, expenses, transfers, capital, commissions. 9 movement types, annulment with audit |
| Inventory Adjustments | `/api/v1/inventory/adjustments/` | Manual stock corrections: increase, decrease, recount, zero-out. Warehouse transfers. Annulment with stock reversal |
| Material Transformations | `/api/v1/inventory/transformations/` | Material disassembly (e.g., Motor → Copper + Iron + Aluminum + Waste). Proportional/manual cost distribution |
| Inventory Views | `/api/v1/inventory/` | Consolidated stock view, per-material warehouse breakdown, transit stock, movement history, inventory valuation |
| Reports & Dashboard | `/api/v1/reports/` | Dashboard with period comparison, P&L, Cash Flow, Balance Sheet, Purchase/Sales reports, Margin Analysis, Third Party Balances. All read-only |

### Testing

Tests use a separate PostgreSQL database on port 5433. `conftest.py` provides fixtures for users, organizations, auth tokens, and org headers. Async mode is auto-enabled via pytest-asyncio. Coverage target is 80%+. Current: 360 tests, 92% coverage.

Key fixtures: `test_user`, `auth_headers`, `org_headers` (auth + X-Organization-ID), `db_session`.

### Database

PostgreSQL 16 with Alembic migrations in `backend/alembic/`. All IDs are UUIDs (using custom `GUID` type for cross-database compatibility). Foreign keys use `CASCADE` on delete. Decimal fields use 4-decimal precision for quantities (kg) and 2-decimal for monetary values.

### Comments and Language

All code comments, docstrings, migration descriptions, and variable names should be in **Spanish** where they describe business logic. Technical terms (class names, function names, SQL) remain in English per Python conventions.
