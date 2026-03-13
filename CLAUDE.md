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
- **`api/deps.py`** — Dependency injection: `get_db()`, `get_current_user()`, `get_required_org_context()`, `get_optional_org_context()`, `require_permission()`. The org context dependencies extract `X-Organization-ID` from request headers. `require_permission("module.action")` is a factory that returns a Depends checking user permissions (admin bypasses all).
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
- `pages/` — 51 page components organized by module

**Modules (all complete, 45+ routes):**
- Auth: Login, org selection, protected routes
- Dashboard: 6 metric cards + top materials/suppliers/customers + alerts
- Purchases: List (status tabs, search, date range, Items/DP/Actions columns) + Create (dynamic lines, auto-liquidate, price suggestions) + Edit (full revert-and-reapply) + Detail (liquidate/cancel/PDF)
- Sales: Like purchases + commissions + profit display + stock warnings + Edit (lines + commissions)
- Double Entries: 2-step workflow (register→liquidate), edit registered, liquidate with price adjustments, real-time profit calculation
- Treasury: 14 movement types with dynamic form, annulment with reason, provisions (deposit/expense), advances (supplier/customer), account statement with running balance + PDF/Excel export, financial dashboard, fixed assets with monthly depreciation
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
- **Treasury movements**: `MoneyMovement` tracks all money flows with 16 types (payment_to_supplier, collection_from_client, expense, service_income, transfer_out/in, capital_injection/return, commission_payment, commission_accrual, provision_deposit, provision_expense, advance_payment, advance_collection, asset_payment, asset_purchase). Each movement affects exactly ONE account (except provision_expense, expense_accrual, commission_accrual, deferred_expense, asset_purchase which have account_id=None). Transfers create a linked pair (transfer_out + transfer_in). Status is `confirmed` or `annulled` (with reason/date/user audit). Independent of purchase/sale liquidation.
- **Provision system**: ThirdParty entities with `is_provision=True` act as fund pools. `provision_deposit` removes money from an account and adds to provision (both balances decrease — negative = funds available). `provision_expense` only affects provision (balance increases, no account touched, account_id=NULL). Fund validation: blocks if overspent (balance > 0) or insufficient funds. Annulation of deposits is allowed even if overspent (consistent with negative stock policy).
- **Account statement (estado de cuenta)**: `GET /money-movements/third-party/{id}` returns movements with `balance_after` (running balance) and `opening_balance` when date_from is provided. Balance direction determined by THIRD_PARTY_BALANCE_DIRECTION map per movement type.
- **Treasury Dashboard**: `GET /reports/treasury-dashboard` returns accounts by type (cash/bank/digital), CxC/CxP, provisions with available funds, MTD income/expense, last 10 movements.
- **Negative stock allowed (RN-INV-03)**: Sales, adjustments, and transformations PERMIT negative stock. Instead of blocking, they return a `warnings[]` field in the response with descriptive messages. This is a global policy decision.
- **Inventory adjustments**: 4 types (increase, decrease, recount, zero_out). All affect `current_stock_liquidated` only (not transit). Increase recalculates avg cost; decrease/recount/zero_out use current avg cost.
- **Material transformation**: Disassembly of composite materials into components. Three cost distribution methods: `average_cost` (default — uses destination material's current avg cost, generates `value_difference`), `proportional_weight` (by weight), or `manual`. Validation: `sum(destination_quantities) + waste == source_quantity`. Creates InventoryMovement for source and each destination. `value_difference = total_dest_value - distributable_value` (excludes waste from comparison). Appears in P&L as "Ganancia/Perdida por Transformaciones".
- **Per-warehouse stock**: Calculated on-the-fly from `SUM(inventory_movements.quantity) GROUP BY warehouse_id`. No denormalized table.
- **Warehouse transfers**: Creates pair of InventoryMovement (transfer type, -qty source / +qty destination). Global stock unchanged.
- **Material cost history**: `MaterialCostHistory` table records every change to `current_average_cost`. Source types: `purchase_liquidation`, `adjustment_increase`, `transformation_in`. Enables precise cost reversal on cancellation and blocks cancellation if subsequent operations affected the same material's cost. Ordering uses `created_at` (monotonic) with `id` tiebreaker.

### Design Decisions

1. **Doble Partida SIN movimientos de inventario**: En operaciones "Pasa Mano" (compra+venta simultanea), el material NO toca bodega. Crear movimientos de inventario inflaria el costo promedio y distorsionaria estadisticas. La doble partida solo afecta saldos de terceros y cuentas. Usa workflow de 2 pasos: REGISTRAR (crea Purchase + Sale en `registered`, sin efectos financieros) → LIQUIDAR (confirma precios ajustables por linea, actualiza saldos terceros, crea comisiones `commission_accrual`). DPs registradas son completamente editables (lineas, terceros, precios, comisiones).

2. **Estados**: Compras, Ventas y Doble Partidas usan `registered | liquidated | cancelled`. Compras/Ventas: 3 pasos (CREATE stock → LIQUIDATE precios/saldos/comisiones → PAY/COLLECT MoneyMovement). Doble Partidas: 2 pasos (REGISTRAR sin efectos → LIQUIDAR con precios ajustables, saldos y comisiones).

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

15. **Anticipos a proveedor/cliente**: `advance_payment` (account-, supplier+) y `advance_collection` (account+, customer-). Un proveedor con balance > 0 significa "nos debe" (anticipo pagado). Un cliente con balance < 0 significa "le debemos" (anticipo recibido). No se vinculan a compras/ventas — el anticipo se consume automaticamente al liquidar operaciones futuras. El reporte de terceros muestra "Saldo a Favor" usando aproximacion por signo de balance.

17. **Upload de evidencia (comprobantes)**: Cada MoneyMovement puede tener un archivo adjunto (imagen o PDF, max 5MB). Endpoints: `POST /{id}/evidence` (upload, multipart/form-data), `GET /{id}/evidence` (download, FileResponse), `DELETE /{id}/evidence`. Almacenamiento local en `{UPLOAD_DIR}/evidence/{org_id}/`. Config: `UPLOAD_DIR` (default `./uploads`), `MAX_UPLOAD_SIZE` (5MB). Un archivo por movimiento (reemplaza anterior). Frontend: file input en MovementCreatePage (upload post-create), sección comprobante en MovementDetailPage (ver/reemplazar/eliminar), icono Paperclip en TreasuryPage.

18. **Gastos diferidos (Scheduled Expenses)**: Reemplazo completo de DeferredExpenses. 3 casos de uso: (a) **Provisiones** (existente, bug fix provision_expense en P&L). (b) **Pasivos** (`expense_accrual`): causar gasto sin mover dinero — NO cuenta, third_party.balance(-), aparece en P&L. Pago de pasivos via `payment_to_supplier` existente. (c) **Gastos Diferidos** (`ScheduledExpense`): pago upfront (`deferred_funding`: account(-), third_party(+), NO P&L) + cuotas mensuales (`deferred_expense`: NO cuenta, third_party(-), P&L). Tablas: `scheduled_expenses` + `scheduled_expense_applications` (reemplazan `deferred_expenses` + `deferred_applications` — DROP). ThirdParty nuevos campos: `is_liability` (pasivo laboral), `is_system_entity` (auto-creado por sistema, filtrado en todos los endpoints de terceros). `ScheduledExpense` crea ThirdParty auto `[Prepago] {name}` con `is_system_entity=True`. Backend no valida `is_liability` en expense_accrual — filtro solo en UI. Frontend: LiabilitiesPage (crear, causar, pagar, estado de cuenta), ScheduledExpensesPage/Create/Detail (reemplazan DeferredExpense*), MovementCreatePage (+expense_accrual, +third_party_id query param, suppliers+liabilities en payment_to_supplier). Migration: `c331bd643694`. 19 tests (5 expense_accrual + 14 scheduled_expense).

16. **Estado de cuenta unificado (Unified Account Statement)**: El endpoint `GET /money-movements/third-party/{id}` es un "unified account statement" que fusiona TODAS las operaciones que afectan el balance de un tercero: MoneyMovements (confirmados + anulados), compras liquidadas/canceladas (standalone), ventas liquidadas/canceladas (standalone), comisiones de ventas, doble partida (como proveedor y/o cliente), y comisiones de doble partida. Cada item incluye `source`/`source_id`/`source_number` para trazar al registro original. Eventos ordenados por (transaction_date, sort_datetime, sort_key: 0=comercial, 1=tesoreria, 2=cancelacion). Tupla `_evt` de 5 campos: `(txn_date, sort_dt, sort_key, filter_dt, kwargs)` con normalizacion Date/DateTime. Cancelaciones usan fecha original de transaccion (no cancelled_at). Display `date` usa fecha de transaccion. Balance corrido calculado iterativamente. Default: ultimos 90 dias si no se provee `date_from`. Compras/ventas con `double_entry_id IS NOT NULL` se excluyen para evitar duplicados con la seccion de doble partida.

19. **Transformacion con costo promedio movil**: Tercer metodo de distribucion `average_cost` (default) que usa el costo promedio del material DESTINO. Genera `value_difference = total_dest_value - distributable_value` (excluye merma de la comparacion). Positivo = ganancia, negativo = perdida. Se muestra en P&L como linea separada "Ganancia/Perdida por Transformaciones" sumada a `total_gross_profit`. Migration: `84cf14a916ca` (columna `value_difference` Numeric 15,2 nullable).

20. **Cantidad recibida por cliente (diferencia de bascula)**: En ventas, el cliente puede reportar una cantidad diferente a la despachada. `SaleLine.received_quantity` (Numeric 10,3 nullable) registra lo que el cliente peso. Al liquidar, si se envia `received_quantity`, el `total_price` se calcula como `received_quantity × unit_price` (facturar lo recibido). El COGS no cambia (`unit_cost × quantity` original — lo que salio de bodega). Profit = `total_price - (unit_cost × quantity)`. El inventario NO se ajusta — la diferencia es solo financiera. `SaleResponse` incluye `total_quantity_difference` y `total_amount_difference`. Migration: `bf0ec8815fdc`.

21. **Pago de pasivo (liability_payment)**: Tipo frontend-only que mapea a `payment_to_supplier` en backend (misma logica contable: account(-), third_party(+)). Frontend: `backendTypeMap` convierte `liability_payment` → `payment_to_supplier` antes de enviar. `getThirdPartyOptions` filtra: `payment_to_supplier` solo proveedores, `liability_payment` solo pasivos (`is_liability`). `isTypeLocked`: cuando URL tiene `?type=...`, el selector de tipo se reemplaza con texto estatico. Backend `_validate_third_party` acepta `str | list[str]` con logica OR para `require_type=["is_supplier", "is_liability"]`.

22. **Balance Sheet con provisiones y prepagos**: Activos incluyen `provision_funds` (provisiones con balance < 0, abs()) y `prepaid_expenses` (ThirdParty con `is_system_entity=True` y balance > 0). Pasivos incluyen `liability_debt` (ThirdParty con `is_liability=True` y balance < 0, abs()). Convencion de signo: `current_balance` raw se muestra como "Saldo Contable"; `abs()` como "Fondos Disponibles" solo en vistas operativas.

23. **Normalizacion de fechas de negocio (BusinessDate)**: Todas las fechas de negocio (compras, ventas, movimientos, ajustes, transformaciones, doble partida) se normalizan a mediodia UTC (12:00) via `BusinessDate` (Pydantic `Annotated[datetime, BeforeValidator]` en `app/utils/dates.py`). Esto garantiza que la fecha se muestre correctamente en cualquier timezone UTC-12 a UTC+12. El frontend envia fecha local, el schema la normaliza automaticamente. Para double_entry (que usa python `date`, no `datetime`), la normalizacion es en el service. Validaciones de "fecha futura" comparan `.date()` (no datetime completo). NO se aplica a Response schemas (solo lectura) ni a `reports.py._date_range` (query bounds, no almacenamiento).

24. **Pago/Cobro inmediato al liquidar**: Al liquidar compras/ventas, opcionalmente se puede marcar "pago/cobro inmediato" con cuenta seleccionada. Crea un `MoneyMovement` atomicamente dentro de la misma transaccion usando `_create_movement()` (composable, usa flush). Validacion de saldo de cuenta. Frontend: Switch + EntitySelect en PurchaseLiquidatePage/SaleLiquidatePage. **Tambien disponible al crear con auto_liquidate**: `PurchaseCreate.immediate_payment` + `payment_account_id` (requiere `auto_liquidate=True`), `SaleCreate.immediate_collection` + `collection_account_id`. Schema validators con dependencias cruzadas. Frontend: Switch + EntitySelect en PurchaseCreatePage/SaleCreatePage dentro de la seccion auto-liquidar. Cache invalidation condicional en hooks: `status === "liquidated"` → `invalidateAfterPurchaseLiquidateOrCancel`, else → `invalidateAfterPurchase`.

25. **Cash Flow desglosado**: Ingresos incluyen `advance_collections`. Egresos incluyen `provision_deposits`, `deferred_fundings`, `advance_payments`, `asset_payments`. Todos se suman a `total_outflows`/`total_inflows` para que `closing_balance = opening_balance + total_inflows - total_outflows` cuadre.

26. **Activos Fijos (Fixed Assets)**: Modulo completo de depreciacion mensual en linea recta. `FixedAsset` con status `active | fully_depreciated | disposed`. Crear activo con DOS fuentes de pago (XOR): `source_account_id` (pago desde cuenta, crea `asset_payment`, descuenta balance) O `supplier_id` (compra a credito, crea `asset_purchase`, supplier.balance(-), NO afecta cuenta). Schema valida exactamente UNA fuente via `@model_validator`. `asset_purchase` NO aparece en Cash Flow (no mueve dinero). Proveedor queda con deuda que se paga via `payment_to_supplier`. `depreciation_expense` (MoneyMovement sin cuenta ni tercero, solo expense_category) se crea al depreciar. Ultima cuota se ajusta para llegar exacto a `salvage_value`. Dispose crea depreciacion acelerada por valor pendiente. `apply-pending` batch deprecia todos los activos con periodos pendientes. Balance Sheet incluye `fixed_assets` (SUM current_value WHERE status != disposed). P&L incluye `depreciation_expense` como source_type en expenses_by_category. Update restricciones: si tiene depreciaciones, solo nombre/codigo/notas/categoria editables. Frontend: FixedAssetCreatePage con radio buttons "Pago desde Cuenta" / "A Credito (Proveedor)" y selector condicional. 4 paginas (List, Create, Detail, Edit). 25 tests.

24. **P&L desagregado por fuente**: `ExpenseCategoryBreakdown` incluye `source_type` (expense, provision_expense, expense_accrual, deferred_expense). Frontend agrupa gastos operativos por fuente con subtotales cuando hay mas de un tipo. Tabla detallada con secciones colapsables por fuente.

26. **Invalidacion de cache React Query (queryInvalidation.ts)**: Sistema centralizado en `frontend/src/utils/queryInvalidation.ts`. Cada operacion que crea registros en OTROS modulos debe invalidar esos modulos. Regla clave: **si una operacion crea side-effects cross-module, invalidar TODOS los query keys afectados**. Mapa actual:
    - `invalidateAfterPurchase` (crear/editar): `purchases` + `inventory` + `materials`
    - `invalidateAfterPurchaseLiquidateOrCancel`: + `money-movements` + `treasury-dashboard` + `third-parties` + `reports` + `money-accounts` (incluye pago inmediato)
    - `invalidateAfterSale` (crear/editar): `sales` + `inventory` + `materials`
    - `invalidateAfterSaleLiquidateOrCancel`: + `money-movements` + `treasury-dashboard` + `third-parties` + `reports` + `money-accounts` (incluye cobro inmediato)
    - `invalidateAfterDoubleEntry` (crear/cancelar): `double-entries` + `purchases` + `sales` + `third-parties` + `reports` + `money-accounts`
    - `invalidateAfterTreasury` (movimientos tesoreria): `money-movements` + `money-accounts` + `third-parties` + `reports` + `treasury-dashboard` + `scheduled-expenses`
    - `invalidateAfterInventoryChange` (ajustes/transformaciones): `inventory` + `materials`
    - Al agregar nuevas operaciones con side-effects, SIEMPRE agregar invalidacion de query keys afectados.

27. **Serializacion de fechas en Response schemas**: `DoubleEntryResponse.date` (python `date`, no `datetime`) necesita `field_serializer` que convierte a datetime mediodia UTC ISO string (`"2026-03-12T12:00:00+00:00"`). Sin esto, JS parsea `"2026-03-12"` como midnight UTC → dia anterior en Colombia. Otros Response schemas con campo `datetime` no necesitan esto (ya incluyen hora).

28. **Comision causada (commission_accrual)**: Tipo de movimiento que registra comisiones en P&L al momento de la liquidacion (base devengado). NO afecta cuenta (account_id=NULL), SI afecta third_party.balance(+). Se crea automaticamente en `_pay_commissions()` (ventas) y en `double_entry.create()`. Se anula automaticamente al cancelar venta/DE. En el estado de cuenta unificado, `sales_with_accrual` set evita duplicacion con `sale_commission` (backward compatible: ventas antiguas sin commission_accrual siguen usando SaleCommission). Frontend: "Comisión Causada" en 5 paginas de tesoreria. No se crea manualmente.

29. **Seed script con capital inicial**: `scripts/seed_test_data.py --clear` crea automaticamente un aporte de capital de $100M COP a "Bancolombia Ahorros" desde "Carlos Perez Inversores" con fecha de hoy.

31. **Carga inicial desde Excel (load_initial_data.py)**: Script `scripts/load_initial_data.py` carga datos maestros desde archivo Excel con 8 hojas (Categorias, UnidadesNegocio, Bodegas, Cuentas, Gastos, Terceros, Materiales, Precios) via API REST autenticada. Resolucion de FKs por nombre (categoria→category_id, etc.). Manejo de duplicados (409 → omitir). Modo `--dry-run` para validar sin crear. Re-ejecutable. No carga stock (se hace via ajustes de inventario). Dependencias: `openpyxl`, `requests`.

30. **Activos fijos con depreciacion mensual (F5)**: Modulo completo para equipos costosos con depreciacion lineal mensual. Dos tablas: `fixed_assets` + `asset_depreciations`. Tipo de movimiento `depreciation_expense`: NO cuenta, NO tercero, solo `expense_category_id` para P&L. Cuota = `purchase_value × (rate/100)`, vida util hasta `salvage_value`. Ultima cuota ajustada exactamente al residual. Dispose con depreciacion acelerada (periodo `YYYY-MMB`). `apply_pending` deprecia batch todos los activos activos del mes. Balance Sheet incluye `fixed_assets = SUM(current_value) WHERE status != 'disposed'`. Migration: `d3e73695da43`. 20 tests. Frontend: FixedAssetsPage (list + apply batch), FixedAssetCreatePage (form + preview calculo), FixedAssetDetailPage (KPIs + progress bar + depreciaciones + dispose). Sidebar: "Activos Fijos" (Building2 icon) en Tesoreria. Labels `depreciation_expense` en 5 paginas de tesoreria.

31. **Roles y permisos granulares (RBAC)**: Sistema completo de roles y permisos por organizacion. 3 tablas: `permissions` (catalogo global ~45 permisos, 11 modulos), `roles` (por org, `UniqueConstraint(org_id, name)`, flag `is_system_role`), `role_permissions` (junction M:N). `OrganizationMember.role_id` (UUID FK) reemplaza el viejo `role` string. 5 roles del sistema auto-creados por org: `admin` (todos los permisos via wildcard), `bascula` (crear compras/ventas sin precios), `liquidador` (liquidar + cancelar + precios + caja + reportes), `planillador` (doble partida sin liquidar), `viewer` (solo lectura). Roles personalizados via CRUD. `require_permission(*perms)` factory en deps.py para proteger endpoints (admin bypassa). `get_required_org_context()` retorna `user_permissions: set[str]`, `is_admin: bool`, `user_role_id: UUID`. **Enforcement completo**: `require_permission()` aplicado a TODOS los ~163 endpoints de negocio en 19 archivos. Solo `organizations.py` y `roles.py` usan `get_required_org_context` directamente (endpoints pre-permiso o any-member). Migrations: `bbed048158b2` (infraestructura), `f7a3c9e21b04` (permisos liquidador). 547 tests total. **Solo backend** — frontend (pages de roles, RBAC en UI) es segunda fase.

### Business Modules (Implemented)

| Module | Endpoints | Description |
|--------|-----------|-------------|
| Auth | `/api/v1/auth/` | JWT login, registration |
| Organizations | `/api/v1/organizations/` | CRUD + member management with role_id FK |
| Roles & Permissions | `/api/v1/roles/` | RBAC: 45 granular permissions, 5 system roles (admin/bascula/liquidador/planillador/viewer), custom roles, `require_permission()` factory |
| Materials | `/api/v1/materials/` | Materials + categories + business units, stock tracking |
| Third Parties | `/api/v1/third-parties/` | Multi-role entities (supplier/customer/investor/provision) with balance tracking |
| Purchases | `/api/v1/purchases/` | 3-step buy workflow (register→liquidate→pay), supplier debt, inventory movements, full edit (PATCH) |
| Sales | `/api/v1/sales/` | 2-step sell workflow, commissions (percentage/fixed), profit calculation, full edit (PATCH) |
| Double Entries | `/api/v1/double-entries/` | 2-step workflow (register→liquidate), edit registered, price adjustments at liquidation, commissions, no inventory movement |
| Money Accounts | `/api/v1/money-accounts/` | Cash, bank, digital accounts (Nequi, etc.) |
| Warehouses | `/api/v1/warehouses/` | Physical storage locations |
| Business Units | `/api/v1/business-units/` | P&L analysis segments (Fibras, Chatarra, etc.) |
| Price Lists | `/api/v1/price-lists/` | Historical purchase/sale prices per material |
| Expense Categories | `/api/v1/expense-categories/` | Direct/indirect expense classification for treasury |
| Treasury | `/api/v1/money-movements/` | 15 movement types (incl. provisions, advances, depreciation), annulment with audit, account statement with running balance + PDF/Excel export |
| Fixed Assets | `/api/v1/fixed-assets/` | Equipment depreciation: create, depreciate monthly, apply-pending batch, dispose with accelerated depreciation |
| Inventory Adjustments | `/api/v1/inventory/adjustments/` | Manual stock corrections: increase, decrease, recount, zero-out. Warehouse transfers. Annulment with stock reversal |
| Material Transformations | `/api/v1/inventory/transformations/` | Material disassembly (e.g., Motor → Copper + Iron + Aluminum + Waste). Proportional/manual cost distribution |
| Inventory Views | `/api/v1/inventory/` | Consolidated stock (filterable by category/warehouse), per-material warehouse breakdown, transit stock (pending purchases/sales/bottleneck alerts), movement history (with running balance/avg cost per material), inventory valuation |
| Deferred Expenses | `/api/v1/deferred-expenses/` | Large expenses distributed in monthly installments. Create, apply installments (creates MoneyMovement), cancel. Pending endpoint for dashboard |
| Reports & Dashboard | `/api/v1/reports/` | Dashboard with period comparison, P&L, Cash Flow, Balance Sheet, Purchase/Sales reports, Margin Analysis, Third Party Balances, Treasury Dashboard. All read-only |

### Testing

Tests use a separate PostgreSQL database on port 5433. `conftest.py` provides fixtures for users, organizations, auth tokens, and org headers. Async mode is auto-enabled via pytest-asyncio. Coverage target is 80%+. Current: 547 tests. Run with `./venv/bin/pytest` from backend dir.

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
