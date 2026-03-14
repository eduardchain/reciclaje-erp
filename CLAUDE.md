# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## REGLA OBLIGATORIA: Persistencia de contexto

**ANTES de considerar la tarea terminada, SIEMPRE ejecutar estos dos pasos. No son opcionales.**

1. **Actualizar CLAUDE.md** si hubo: nueva funcionalidad, decision arquitectonica, nuevo patron, cambio de workflow, nuevo modulo, o cualquier informacion que una sesion futura necesitaria para no romper cosas.
2. **Actualizar memory/** si hubo: feedback del usuario sobre como trabajar, preferencias nuevas, contexto de proyecto (deadlines, estado actual), o referencias externas utiles.

**Si no hay nada que actualizar, decir explicitamente: "No hay cambios para CLAUDE.md ni memory."** Esto confirma que se evaluo y se decidio no actualizar, en vez de olvidarlo.

## REGLA OBLIGATORIA: Validacion de requerimientos

**Cuando el usuario entregue un paquete de instrucciones o requisitos, ANTES de planear o implementar:**

1. Revisar los requisitos contra el codigo actual y CLAUDE.md.
2. Identificar: requisitos faltantes, contradicciones con patrones existentes, edge cases no cubiertos, side-effects con otros modulos.
3. Si hay gaps, listarlos y esperar confirmacion antes de continuar.
4. Si no hay gaps, decir "Requisitos validados, no encontre gaps" y proceder.

---

## Guia para mantener CLAUDE.md

Al terminar una sesion donde se implemento funcionalidad nueva o se tomo una decision arquitectonica:

1. **Agregar decision nueva** al final de "Decisiones de Diseno" con el siguiente numero consecutivo. Incluir: que se hizo, por que, y como interactua con el resto del sistema. Ser conciso pero completo.
2. **Actualizar secciones existentes** si la nueva funcionalidad cambia algo ya documentado (ej: nuevo tipo de movimiento → actualizar la lista en Key Patterns, nuevo modulo → actualizar tabla de Business Modules, nuevos tests → actualizar conteo).
3. **No duplicar informacion**: si algo ya esta en Key Patterns, no repetirlo en Decisiones. Key Patterns = "que hace el sistema", Decisiones = "por que lo hace asi".
4. **Nunca desordenar la numeracion**: las decisiones se numeran secuencialmente. No saltar numeros, no duplicar.
5. **Condensar**: cada decision debe ser 2-4 lineas max. Si necesita mas, probablemente son 2 decisiones separadas.
6. **Conteos**: actualizar `Current: N tests` en Testing, y conteos de componentes/servicios/hooks en Frontend si cambian.
7. **Migrations**: solo mencionar migration ID si es relevante para entender la historia (ej: rename de tabla). No listar todas.
8. **Cache invalidation**: si la nueva funcionalidad crea side-effects cross-module, actualizar el mapa en `queryInvalidation.ts` Y documentarlo aqui.
9. **Migraciones**: si se crean nuevas migraciones, SIEMPRE correr `./venv/bin/alembic upgrade head` en la BD de desarrollo Y en la de test antes de probar. Los permisos RBAC se leen de la tabla `permissions` en BD, no del catalogo Python — sin migrar, los nuevos permisos no existen.

## Project Overview

EcoBalance is a multi-tenant ERP system for recycling companies (buying/selling metal and material scraps). Python/FastAPI backend + React/TypeScript frontend.

## Common Commands

### Backend (run from `/backend/`)

**IMPORTANTE: Usar `./venv/bin/` para todos los comandos Python.** No usar `pip`, `pytest`, `alembic` directamente — no estan en PATH.

```bash
./venv/bin/pip install -r requirements.txt
./venv/bin/uvicorn app.main:app --reload --port 8000
./venv/bin/alembic upgrade head
./venv/bin/alembic revision --autogenerate -m "description"

# Tests (requires test PostgreSQL on port 5433)
./venv/bin/pytest
./venv/bin/pytest tests/test_api_purchases.py -xvs                                          # single file
./venv/bin/pytest tests/test_api_purchases.py::TestPurchaseCreation::test_create_purchase -xvs  # single method
./venv/bin/pytest --cov=app --cov-report=html                                                # coverage
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
docker-compose up -d                              # Dev database (port 5432)
docker-compose -f docker-compose.test.yml up -d   # Test database (port 5433)
```

## Architecture

### Backend (`backend/app/`)

Layered: **Endpoints → Services → Models**, with Pydantic schemas for validation.

- **`api/v1/endpoints/`** — Route handlers, one router per module.
- **`api/deps.py`** — DI: `get_db()`, `get_current_user()`, `get_required_org_context()`, `get_optional_org_context()`, `require_permission("module.action")` (AND), `require_any_permission("perm1", "perm2")` (OR). Admin bypasses all.
- **`services/`** — Business logic. All extend `CRUDBase` (pagination, soft delete, search, auto `organization_id` filtering).
- **`models/`** — SQLAlchemy 2.0. All domain models inherit `TimestampMixin` + `OrganizationMixin`.
- **`schemas/`** — Pydantic v2. Use `model_validate` with `from_attributes=True`.
- **`models/base.py`** — `GUID` type (cross-DB UUID), `Base`, mixins.
- **`core/`** — `config.py` (Settings from env), `security.py` (JWT + bcrypt), `database.py` (engine/session).

### Frontend (`frontend/src/`)

React 18 + TypeScript + Vite. Zustand (auth state), TanStack React Query + Axios (data), Tailwind + shadcn/ui (UI), lucide-react (icons), sonner (toasts).

- `services/api.ts` — Axios client: JWT auto-attach, X-Organization-ID from authStore, 401 redirect.
- `services/*.ts` — 17 service files. `hooks/use*.ts` — 15 React Query hooks with toast on mutations.
- `types/*.ts` — 15 type files matching backend schemas.
- `components/shared/` — DataTable, PageHeader, StatusBadge, MoneyDisplay, DateRangePicker, SearchInput, ConfirmDialog, EmptyState, EntitySelect, WarningsList, PriceSuggestion, KpiCard.
- `components/auth/` — ProtectedRoute, OrganizationSelector, PermissionGate (wraps content by permission check).
- `pages/` — 54 page components. Forms use useState pattern. Admin pages: RolesPage, RoleEditPage, UsersPage.
- `utils/queryInvalidation.ts` — Centralized cache invalidation (see decision #26).

**Query Key Convention:** `['module', 'list'|'detail', filters|id]` (ej: `['purchases', 'list', filters]`, `['inventory', 'stock', params]`)

### Key Patterns

- **Multi-tenancy**: `X-Organization-ID` header required. `CRUDBase._base_query()` enforces `organization_id` filtering.
- **Soft delete**: `is_active` flag, never hard delete.
- **Purchase workflow (3-step)**: register (stock→transit, zero financial effect) → liquidate (confirm prices, avg cost, supplier balance, transit→liquidated) → pay (separate MoneyMovement).
- **Sale workflow (2-step)**: register (stock out, zero financial) → liquidate (prices, customer balance, commissions). Collect via MoneyMovement.
- **Double Entry (Pasa Mano)**: 2-step, NO inventory movements. Only third-party balances + commissions.
- **Liquidacion ≠ Pago**: Liquidation confirms prices/balances. Payment is always a separate MoneyMovement.
- **Moving average cost**: Recalculated at purchase LIQUIDATION only. `MaterialCostHistory` enables reversal on cancellation.
- **Stock separation**: `current_stock_transit` (registered) vs `current_stock_liquidated` (confirmed). `current_stock` = total.
- **Negative stock allowed**: Sales, adjustments, transformations return `warnings[]` instead of blocking.
- **Sequential numbering**: Purchase/sale/double-entry numbers auto-incremented per org.
- **Treasury**: `MoneyMovement` with 16 types. Some have `account_id=NULL` (accruals). Transfers = linked pair. Status: `confirmed|annulled`.
- **Provisions**: ThirdParty with `is_provision=True`. Negative balance = funds available. `provision_deposit` (account→provision), `provision_expense` (provision only, no account).
- **Price lists**: Append-only. Current price = most recent by `created_at`. Frontend auto-fills via `usePriceSuggestions()`.
- **Per-warehouse stock**: On-the-fly `SUM(inventory_movements.quantity) GROUP BY warehouse_id`.
- **BusinessDate**: All business dates normalized to noon UTC (12:00) via Pydantic `BeforeValidator` in `app/utils/dates.py`. Prevents timezone display issues.
- **RBAC**: `require_permission()` (AND) and `require_any_permission()` (OR) on all ~163 business endpoints. 65 permissions across 11 modules. 5 system roles: admin, bascula, liquidador, planillador, viewer. Custom roles via CRUD. **Master+Granular logic**: master permission (e.g., `treasury.view`) gives access to ALL sub-tabs; granular permissions (e.g., `treasury.view_provisions`) give access to specific sub-tabs WITHOUT master. Frontend: `usePermissions()` hook, `PermissionGate` component, sidebar filtering. Admin UI: RolesPage, RoleEditPage, UsersPage.

### Business Modules

| Module | Endpoints | Key Features |
|--------|-----------|-------------|
| Auth | `/api/v1/auth/` | JWT login, registration |
| Organizations | `/api/v1/organizations/` | CRUD + members with role_id FK |
| Roles & Permissions | `/api/v1/roles/` | 65 permissions, 11 modules, 5 system roles, custom roles, admin UI |
| Materials | `/api/v1/materials/` | CRUD + categories + business units, stock tracking |
| Third Parties | `/api/v1/third-parties/` | Multi-role (supplier/customer/investor/provision/liability), balance tracking |
| Purchases | `/api/v1/purchases/` | 3-step workflow, full edit (revert-and-reapply), auto-liquidate, immediate payment |
| Sales | `/api/v1/sales/` | 2-step workflow, commissions, received_quantity, full edit, immediate collection |
| Double Entries | `/api/v1/double-entries/` | 2-step, edit registered, price adjustments at liquidation, commissions |
| Treasury | `/api/v1/money-movements/` | 16 types, annulment with audit, unified account statement, evidence upload, PDF/Excel export |
| Fixed Assets | `/api/v1/fixed-assets/` | Monthly depreciation, apply-pending batch, dispose, pay from account OR credit from supplier |
| Inventory | `/api/v1/inventory/` | Stock, movements, adjustments (4 types), transformations (3 cost methods), transfers, transit, valuation |
| Scheduled Expenses | `/api/v1/deferred-expenses/` | Deferred expenses with monthly installments |
| Reports | `/api/v1/reports/` | Dashboard, P&L, Cash Flow, Balance Sheet, Purchase/Sales/Margin reports, Treasury Dashboard |
| Config | Various | Warehouses, Money Accounts, Business Units, Expense Categories (direct/indirect), Price Lists |

### Testing

PostgreSQL on port 5433. `conftest.py` provides: `test_user`, `auth_headers`, `org_headers`, `db_session`. Async auto-enabled via pytest-asyncio. Current: 547 tests.

### Database

PostgreSQL 16, Alembic migrations. UUIDs everywhere (`GUID` type). Decimals: 4 places for quantities (kg), 2 for money. `CASCADE` on FK delete.

### Comments and Language

Business logic comments/docstrings in **Spanish**. Technical names (classes, functions, SQL) in English.

---

## Decisiones de Diseno

Numeradas secuencialmente. Solo agregar al final con el siguiente numero.

1. **Doble Partida sin inventario**: Operaciones "Pasa Mano" NO tocan bodega — inflaria costo promedio. Solo afecta saldos de terceros y comisiones (`commission_accrual`).

2. **Estados uniformes**: Compras, Ventas y DPs usan `registered | liquidated | cancelled`. Compras/Ventas: CREATE→LIQUIDATE→PAY. DPs: REGISTER→LIQUIDATE.

3. **Stock en transito**: Compras registradas crean stock transit sin efectos financieros. Al liquidar: confirmar precios, recalcular costo promedio, actualizar saldo proveedor, transit→liquidated.

4. **Gastos directos vs indirectos**: `is_direct_expense=True` afecta costo del material (flete, pesaje). `False` = administrativo. Clave para rentabilidad.

5. **COGS directo**: `SUM(sale_lines.unit_cost × quantity)` captura costo promedio movil al momento de cada venta. Mas preciso que metodo tradicional en inventario perpetuo.

6. **P&L de Doble Partida**: Utilidad Pasa Mano como linea separada, NO incluida en Sales Revenue ni COGS.

7. **Cash Flow hibrido**: Combina liquidacion de compras/ventas (cambios a account.balance) + money_movements. Opening balance = balance actual - cambios desde date_from. Desglosado: ingresos incluyen advance_collections; egresos incluyen provision_deposits, deferred_fundings, advance_payments, asset_payments.

8. **Edicion con Revert-and-Reapply**: Compras/ventas `registered` (sin DP) editables completamente. Revierte efectos colaterales, elimina lineas/movimientos, re-aplica. Compras bloquean si stock insuficiente; ventas permiten negativo con warnings.

9. **Cancelacion con reversal de costo**: Usa `MaterialCostHistory` para revertir costo promedio. BLOQUEA si hay operaciones posteriores sobre el mismo material. COGS de ventas existentes NO se recalcula (correcto: refleja costo al momento de la venta).

10. **Precio sugerido**: Auto-fill desde lista de precios vigente (solo si campo vacio). Hint clickable "Lista: $ X" para restaurar.

11. **Anticipos**: `advance_payment` (account-, supplier+) y `advance_collection` (account+, customer-). Proveedor balance > 0 = nos debe. Cliente balance < 0 = le debemos. Se consumen automaticamente al liquidar operaciones futuras.

12. **Upload de evidencia**: Un archivo por MoneyMovement (imagen/PDF, max 5MB). Almacenamiento local `{UPLOAD_DIR}/evidence/{org_id}/`.

13. **Gastos diferidos (ScheduledExpense)**: Pago upfront (`deferred_funding`: account(-), third_party(+), NO P&L) + cuotas mensuales (`deferred_expense`: NO cuenta, third_party(-), SI P&L). Crea ThirdParty auto `[Prepago] {name}` con `is_system_entity=True`.

14. **Pasivos (expense_accrual)**: Causar gasto sin mover dinero — NO cuenta, third_party.balance(-), aparece en P&L. Pago via `payment_to_supplier`. ThirdParty con `is_liability=True`.

15. **Pago de pasivo (liability_payment)**: Tipo frontend-only que mapea a `payment_to_supplier` en backend. `backendTypeMap` convierte antes de enviar. Backend `_validate_third_party` acepta `require_type=["is_supplier", "is_liability"]` con logica OR.

16. **Estado de cuenta unificado**: `GET /money-movements/third-party/{id}` fusiona TODAS las fuentes: MoneyMovements, compras/ventas standalone, comisiones, DPs. Ordenado por (transaction_date, sort_datetime, sort_key: 0=comercial, 1=tesoreria, 2=cancelacion). Default: ultimos 90 dias. Excluye compras/ventas con `double_entry_id IS NOT NULL`.

17. **Transformaciones de material**: Desarmado de compuestos. 3 metodos de costo: `average_cost` (default, usa costo promedio destino, genera `value_difference`), `proportional_weight`, `manual`. Validacion: `sum(dest_quantities) + waste == source_quantity`. P&L: "Ganancia/Perdida por Transformaciones".

18. **Cantidad recibida (diferencia de bascula)**: `SaleLine.received_quantity` registra lo que el cliente peso. Si se envia, `total_price = received_quantity × unit_price`. COGS no cambia (usa cantidad original). Inventario no se ajusta — diferencia solo financiera.

19. **Balance Sheet extendido**: Activos: `provision_funds` (balance < 0), `prepaid_expenses` (system_entity, balance > 0), `fixed_assets` (SUM current_value). Pasivos: `liability_debt` (is_liability, balance < 0). Signo: raw = "Saldo Contable", abs() = "Fondos Disponibles".

20. **Pago/Cobro inmediato**: Al liquidar o crear con auto_liquidate, opcionalmente crear MoneyMovement atomico en misma transaccion via `_create_movement()` (composable, usa flush). Schema validators con dependencias cruzadas.

21. **Activos Fijos**: Depreciacion mensual linea recta. Dos fuentes de pago (XOR): `source_account_id` (asset_payment) o `supplier_id` (asset_purchase, no afecta cuenta). `depreciation_expense` sin cuenta ni tercero, solo expense_category. Ultima cuota ajustada al residual. Dispose = depreciacion acelerada.

22. **P&L desagregado por fuente**: `ExpenseCategoryBreakdown.source_type` (expense, provision_expense, expense_accrual, deferred_expense, depreciation_expense). Frontend agrupa con subtotales por fuente.

23. **Comision causada (commission_accrual)**: Registra comisiones en P&L al liquidar (base devengado). account_id=NULL, third_party.balance(+). Auto-creada y auto-anulada. `sales_with_accrual` set en estado de cuenta evita duplicacion.

24. **Serializacion de fechas date→datetime**: `DoubleEntryResponse.date` (python `date`) necesita `field_serializer` a datetime mediodia UTC. Sin esto, JS parsea "2026-03-12" como midnight UTC → dia anterior en Colombia.

25. **RBAC backend**: 3 tablas: `permissions` (65, 11 modulos), `roles` (por org, `is_system_role`), `role_permissions` (M:N). `require_permission()` (AND) y `require_any_permission()` (OR) en ~163 endpoints. Admin bypassa todo.

26. **RBAC frontend + Admin UI**: `usePermissions()` hook (staleTime 5min), `PermissionGate` component, sidebar filtering, route protection. Master+Granular: master da acceso a todos los sub-tabs, granular da acceso sin master (OR logic). Admin UI: RolesPage, RoleEditPage (65 permisos por modulo), UsersPage. Al editar permisos se invalida `["permissions", orgId]`.

27. **Cache invalidation centralizada**: `queryInvalidation.ts`. Regla: si una operacion crea side-effects cross-module, invalidar TODOS los query keys afectados:
    - `invalidateAfterPurchase` (crear/editar): purchases + inventory + materials
    - `invalidateAfterPurchaseLiquidateOrCancel`: + money-movements + treasury-dashboard + third-parties + reports + money-accounts
    - `invalidateAfterSale` (crear/editar): sales + inventory + materials
    - `invalidateAfterSaleLiquidateOrCancel`: + money-movements + treasury-dashboard + third-parties + reports + money-accounts
    - `invalidateAfterDoubleEntry`: double-entries + purchases + sales + third-parties + reports + money-accounts
    - `invalidateAfterTreasury`: money-movements + money-accounts + third-parties + reports + treasury-dashboard + scheduled-expenses
    - `invalidateAfterInventoryChange`: inventory + materials
    - Role CRUD: roles + permissions (si afecta rol del usuario actual)

28. **Scripts utilitarios**: `scripts/seed_test_data.py --clear` (datos de prueba + capital $100M COP). `scripts/load_initial_data.py` (carga maestros desde Excel, 8 hojas, resolucion FKs por nombre, `--dry-run`).

### Inventory Module — UX Details

- **StockPage**: Manual `<Table>` (no DataTable) con expandable rows por bodega. Filters: Category, Warehouse, Search. Acciones: Trasladar, Ver Movimientos, Ajustar Stock (navegan con `?material_id=`).
- **MovementHistoryPage**: Filters Material + Warehouse al backend. Con `material_id`: muestra `balance_after` y `avg_cost_after` (running balance iterativo).
- **TransitPage**: KpiCards + bottleneck alerts + 2 DataTables (compras/ventas pendientes).
- **AdjustmentCreatePage**: Lee `material_id` de URL search params para pre-seleccionar material.
