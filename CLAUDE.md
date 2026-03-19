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

## REGLA OBLIGATORIA: Tests en toda funcionalidad nueva

**Toda implementacion de funcionalidad nueva o modificacion significativa DEBE incluir tests que cubran:**

1. **Caso feliz**: flujo completo con datos validos (crear, liquidar, cancelar, etc.).
2. **Validaciones**: campos obligatorios, tipos invalidos, valores fuera de rango → esperar 422.
3. **Edge cases**: limites del negocio (stock negativo, balance cero, duplicados, estados invalidos).
4. **Side-effects cross-module**: verificar que operaciones que afectan otros modulos (balances, inventario, costos) producen los efectos esperados.
5. **Permisos RBAC**: si se agregan o modifican permisos, testear acceso permitido Y denegado.

**Si el paquete de instrucciones incluye criterios de aceptacion (seccion 7), cada criterio debe tener al menos un test correspondiente.**

Excepciones: cambios puramente cosmeticos en frontend (CSS, labels, reordenar UI) no requieren tests backend.

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
9. **Migraciones**: si se crean nuevas migraciones, SIEMPRE correr `./venv/bin/alembic upgrade head` en la BD de desarrollo (5434) Y en la de test (5433) antes de probar. NUNCA correr migraciones directamente contra produccion — las migraciones en produccion se ejecutan SOLO via la skill `/deploy`. Los permisos RBAC se leen de la tabla `permissions` en BD, no del catalogo Python — sin migrar, los nuevos permisos no existen.

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

**3 entornos separados — NUNCA conectar desarrollo a produccion.**

| Entorno | Contenedor | Puerto | User | Password | DB | docker-compose |
|---------|-----------|--------|------|----------|-----|----------------|
| Desarrollo | reciclaje_dev_db | 5434 | admin | localdev123 | reciclaje_db | `docker-compose.yml` (raiz) |
| Tests | reciclaje-test-db | 5433 | admin | test_password | reciclaje_test | `backend/docker-compose.test.yml` |
| Produccion | VPS (76.13.118.195) | 5432 | — | — | — | SOLO via `/deploy` |

```bash
# Levantar BDs
POSTGRES_PASSWORD=localdev123 docker-compose up -d                         # Dev (port 5434)
cd backend && docker-compose -f docker-compose.test.yml up -d              # Test (port 5433)

# Migraciones (SOLO en dev y test, NUNCA produccion)
cd backend && ./venv/bin/alembic upgrade head                                                        # Dev (usa .env)
cd backend && DATABASE_URL=postgresql://admin:test_password@localhost:5433/reciclaje_test ./venv/bin/alembic upgrade head  # Test

# Replicar datos de produccion a dev local
cd backend && ./scripts/replicate_prod.sh
```

**REGLAS DE BASE DE DATOS:**
- **NUNCA** ejecutar queries, migraciones (`alembic upgrade`), ni scripts directamente contra la BD de produccion.
- **Migraciones** solo en desarrollo (5434) y test (5433). Produccion se migra automaticamente via `/deploy`.
- **Si necesitas datos reales**, primero replica produccion a local con `replicate_prod.sh`.
- **`seed_test_data.py`** y cualquier script de carga apuntan a la BD configurada en `.env` (debe ser desarrollo).
- **Tests (`conftest.py`)** usan `TEST_DATABASE_URL` hardcoded (`admin:test_password@localhost:5433/reciclaje_test`). No dependen de `.env`.

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
- `services/*.ts` — 20 service files. `hooks/use*.ts` — 17 React Query hooks with toast on mutations.
- `types/*.ts` — 20 type files matching backend schemas.
- `components/shared/` — DataTable, PageHeader, StatusBadge, MoneyDisplay, MoneyInput, DateRangePicker, SearchInput, ConfirmDialog, EmptyState, EntitySelect, WarningsList, PriceSuggestion, KpiCard.
- `components/auth/` — ProtectedRoute, OrganizationSelector, PermissionGate (wraps content by permission check).
- `pages/` — 75 page components. Forms use useState pattern. Admin pages: RolesPage, RoleEditPage, UsersPage.
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
- **Treasury**: `MoneyMovement` with 21 types. Some have `account_id=NULL` (accruals, profit_distribution). Transfers = linked pair. Status: `confirmed|annulled`.
- **Provisions**: ThirdParty with `is_provision=True`. Negative balance = funds available. `provision_deposit` (account→provision), `provision_expense` (provision only, no account).
- **Price lists**: Append-only. Current price = most recent by `created_at`. Frontend auto-fills via `usePriceSuggestions()`.
- **Per-warehouse stock**: On-the-fly `SUM(inventory_movements.quantity) GROUP BY warehouse_id`.
- **BusinessDate**: All business dates normalized to noon UTC (12:00) via Pydantic `BeforeValidator` in `app/utils/dates.py`. Prevents timezone display issues.
- **RBAC**: `require_permission()` (AND) and `require_any_permission()` (OR) on all ~161 business endpoints. 72 permissions across 11 modules. 5 system roles: admin, bascula, liquidador, planillador, viewer. Custom roles via CRUD. **Master+Granular logic**: master permission (e.g., `treasury.view`) gives access to ALL sub-tabs; granular permissions (e.g., `treasury.view_provisions`) give access to specific sub-tabs WITHOUT master. Frontend: `usePermissions()` hook, `PermissionGate` component, sidebar filtering. Admin UI: RolesPage, RoleEditPage, UsersPage. **Superuser**: bypasses membership check in deps.py, gets synthesized admin context with all permissions. `/system/` endpoints use separate `get_current_superuser` guard.

### Business Modules

| Module | Endpoints | Key Features |
|--------|-----------|-------------|
| Auth | `/api/v1/auth/` | JWT login, registration, change password |
| Organizations | `/api/v1/organizations/` | CRUD + members with role_id FK |
| Roles & Permissions | `/api/v1/roles/` | 72 permissions, 11 modules, 5 system roles, custom roles, admin UI |
| Materials | `/api/v1/materials/` | CRUD + categories + business units, stock tracking |
| Third Parties | `/api/v1/third-parties/` | Category-based roles via behavior_type (material_supplier/service_provider/customer/investor/generic/provision/liability), balance tracking |
| Third Party Categories | `/api/v1/third-party-categories/` | Hierarchical categories (max 2 levels), behavior_type enum, CRUD + flat list |
| Purchases | `/api/v1/purchases/` | 3-step workflow, full edit (revert-and-reapply), auto-liquidate, immediate payment |
| Sales | `/api/v1/sales/` | 2-step workflow, commissions, received_quantity, full edit, immediate collection |
| Double Entries | `/api/v1/double-entries/` | 2-step, edit registered, price adjustments at liquidation, commissions |
| Treasury | `/api/v1/money-movements/`, `/api/v1/profit-distributions/` | 21 types, annulment with audit, unified account statement, evidence upload, PDF/Excel export, profit distribution |
| Fixed Assets | `/api/v1/fixed-assets/` | Monthly depreciation, apply-pending batch, dispose, pay from account OR credit from supplier |
| Inventory | `/api/v1/inventory/` | Stock, movements, adjustments (4 types), transformations (3 cost methods), transfers, transit, valuation |
| Scheduled Expenses | `/api/v1/deferred-expenses/` | Deferred expenses with monthly installments |
| Reports | `/api/v1/reports/` | Dashboard, P&L, Cash Flow, Balance Sheet, Purchase/Sales/Margin reports, Treasury Dashboard |
| Config | Various | Warehouses, Money Accounts, Business Units, Expense Categories (direct/indirect), Price Lists, Third Party Categories |
| System (Super Admin) | `/api/v1/system/` | CRUD orgs, list users, add user to org. `get_current_superuser` guard. Org selector + system mode |

### Testing

PostgreSQL on port 5433. `conftest.py` provides: `test_user`, `auth_headers`, `org_headers`, `db_session`. Async auto-enabled via pytest-asyncio. Current: 759 tests (20 integration).

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

14. **Pasivos (expense_accrual)**: Causar gasto sin mover dinero — NO cuenta, third_party.balance(-), aparece en P&L. Pago via `payment_to_supplier`. ThirdParty con behavior_type `liability`.

15. **Pago de pasivo (liability_payment)**: Tipo frontend-only que mapea a `payment_to_supplier` en backend. `backendTypeMap` convierte antes de enviar. Backend `_validate_third_party` acepta `require_behavior=["material_supplier", "service_provider", "liability"]`.

16. **Estado de cuenta unificado**: `GET /money-movements/third-party/{id}` fusiona TODAS las fuentes: MoneyMovements, compras/ventas standalone, comisiones, DPs. Ordenado por (transaction_date, sort_datetime, sort_key: 0=comercial, 1=tesoreria, 2=cancelacion). Default: ultimos 90 dias. Excluye compras/ventas con `double_entry_id IS NOT NULL`.

17. **Transformaciones de material**: Desarmado de compuestos. 3 metodos de costo: `average_cost` (default, usa costo promedio destino, genera `value_difference`), `proportional_weight`, `manual`. Validacion: `sum(dest_quantities) + waste == source_quantity`. P&L: "Ganancia/Perdida por Transformaciones".

18. **Cantidad recibida (diferencia de bascula)**: `SaleLine.received_quantity` registra lo que el cliente peso. Si se envia, `total_price = received_quantity × unit_price`. COGS no cambia (usa cantidad original). Inventario no se ajusta — diferencia solo financiera.

19. **Balance Sheet extendido**: Activos: `provision_funds` (balance < 0), `prepaid_expenses` (system_entity, balance > 0), `fixed_assets` (SUM current_value). Pasivos: `liability_debt` (behavior_type `liability`, balance < 0). Signo: raw = "Saldo Contable", abs() = "Fondos Disponibles".

20. **Pago/Cobro inmediato**: Al liquidar o crear con auto_liquidate, opcionalmente crear MoneyMovement atomico en misma transaccion via `_create_movement()` (composable, usa flush). Schema validators con dependencias cruzadas.

21. **Activos Fijos**: Depreciacion mensual linea recta. Dos fuentes de pago (XOR): `source_account_id` (asset_payment) o `supplier_id` (asset_purchase, no afecta cuenta). `depreciation_expense` sin cuenta ni tercero, solo expense_category. Ultima cuota ajustada al residual. Dispose = depreciacion acelerada.

22. **P&L desagregado por fuente**: `ExpenseCategoryBreakdown.source_type` (expense, provision_expense, expense_accrual, deferred_expense, depreciation_expense). Frontend agrupa con subtotales por fuente.

23. **Comision causada (commission_accrual)**: Registra comisiones en P&L al liquidar (base devengado). account_id=NULL, third_party.balance(+). Auto-creada y auto-anulada. `sales_with_accrual` set en estado de cuenta evita duplicacion.

24. **Serializacion de fechas date→datetime**: `DoubleEntryResponse.date` (python `date`) necesita `field_serializer` a datetime mediodia UTC. Sin esto, JS parsea "2026-03-12" como midnight UTC → dia anterior en Colombia.

25. **RBAC backend**: 3 tablas: `permissions` (71, 11 modulos), `roles` (por org, `is_system_role`), `role_permissions` (M:N). `require_permission()` (AND) y `require_any_permission()` (OR) en ~161 endpoints. Admin bypassa todo.

26. **RBAC frontend + Admin UI**: `usePermissions()` hook (staleTime 5min), `PermissionGate` component, sidebar filtering, route protection. Master+Granular: master da acceso a todos los sub-tabs, granular da acceso sin master (OR logic). Admin UI: RolesPage, RoleEditPage (72 permisos por modulo), UsersPage. Al editar permisos se invalida `["permissions", orgId]`.

27. **Cache invalidation centralizada**: `queryInvalidation.ts`. Regla: si una operacion crea side-effects cross-module, invalidar TODOS los query keys afectados:
    - `invalidateAfterPurchase` (crear/editar): purchases + inventory + materials
    - `invalidateAfterPurchaseLiquidateOrCancel`: + money-movements + treasury-dashboard + third-parties + third-party-categories + reports + money-accounts
    - `invalidateAfterSale` (crear/editar): sales + inventory + materials
    - `invalidateAfterSaleLiquidateOrCancel`: + money-movements + treasury-dashboard + third-parties + reports + money-accounts
    - `invalidateAfterDoubleEntry`: double-entries + purchases + sales + third-parties + reports + money-accounts
    - `invalidateAfterTreasury`: money-movements + money-accounts + third-parties + reports + treasury-dashboard + scheduled-expenses
    - `invalidateAfterInventoryChange`: inventory + materials
    - Role CRUD: roles + permissions (si afecta rol del usuario actual)

28. **Scripts utilitarios**: `scripts/seed_test_data.py --clear` (solo maestros: materiales, categorias, bodegas, cuentas con saldo $0. NO crea terceros ni movimientos — flujo manual). `scripts/load_initial_data.py` (carga maestros desde Excel, 8 hojas, resolucion FKs por nombre, `--dry-run`).

29. **Super Admin + Multi-Org**: `is_superuser=True` bypasses membership en `get_required_org_context()` / `get_optional_org_context()` (sintetiza admin context con todos los permisos). `/system/` endpoints (6) protegidos con `get_current_superuser`. Frontend: `organizationId="system"` sentinel — API interceptor no envia `X-Organization-ID`, `usePermissions` retorna admin full, sidebar muestra solo seccion SISTEMA, ProtectedRoute permite pasar sin org. Header dropdown: multi-org selector + opcion "Sistema" para superusers. `queryClient.clear()` al cambiar org. Soft delete de org: `is_active=False` + desactivar usuarios huerfanos.

30. **Comision de compra (prorrateo al costo)**: `PurchaseCommission` tabla separada (reutiliza enum `commission_type`). A diferencia de ventas (comision→P&L via `commission_accrual`), en compras la comision se **prorratea al costo** del material: `adjusted_unit_cost = unit_price + (commission_prorate / quantity)`. Afecta `InventoryMovement.unit_cost` y costo promedio. NO crea MoneyMovement — solo actualiza `third_party.balance` del comisionista. Cancelacion revierte balance. UI en Create/Edit/Liquidate/Detail pages.

31. **Balance Detallado sin inventario en tránsito**: Compras `registered` no crean CxP (solo liquidación lo hace), así que incluir transit como activo desbalancearía la ecuación. Se eliminó `inventory_transit` de activos. Secciones activo: cash, inventory_liquidated, customers_receivable, supplier_advances, service_provider_advances, liability_advances, investor_receivable, provision_funds, prepaid_expenses, generic_receivable, fixed_assets. Secciones pasivo: suppliers_payable, service_provider_payable, liability_debt, investors_partners, investors_obligations, investors_legacy, customer_advances, provision_obligations, generic_payable. Clasificación terceros: `_classify_third_party` usa prioridad por signo de balance + behavior_types. `investor_type`: `"socio"` → partners, `"obligacion_financiera"` → obligations, null → legacy.

32. **Comisionista requiere service_provider**: Validación en `_process_commissions` (compras, ventas) y `_create_commission_records` (DPs): el recipient debe tener `behavior_type` `service_provider` via `has_behavior_type()`. Razón: comisiones generan balance negativo; sin behavior_type proveedor, `_classify_third_party` no lo ubica en pasivos. Frontend: selector de comisionistas filtrado a `payable-providers` (solo `service_provider`). Reglas de proveedor por contexto: DP supplier = `material_supplier` only. Fixed asset supplier = cualquiera excepto `provision`/`liability`. Purchase supplier = `material_supplier`. Sale customer = `customer`.

33. **Categorías de terceros (behavior_type)**: Eliminados flags booleanos. Unica fuente de verdad: `ThirdPartyCategory` con `behavior_type` enum (7 tipos: `material_supplier`, `service_provider`, `customer`, `investor`, `generic`, `provision`, `liability`). M:N via `ThirdPartyCategoryAssignment`. Jerarquía max 2 niveles. `_classify_third_party()` en reports usa behavior_types + category_names. Endpoints: `/suppliers` filtra `material_supplier`, `/payable-providers` filtra `service_provider`, `/liabilities` filtra `liability`, `/investors` filtra `investor`. `liability` y `provision` ocultos de Config y multi-select (se crean solo desde LiabilitiesPage/ProvisionsPage). `payment_to_supplier` y `advance_payment` aceptan `liability` en `require_behavior`.

34. **Repartición de utilidades (profit_distribution)**: Causado contable — incrementa deuda a socios (`third_party.balance -= amount`) sin mover dinero de cuentas (`account_id=NULL`). MoneyMovement tipo `profit_distribution`. NO afecta P&L ni Cash Flow. Balance Sheet: `accumulated_profit` (P&L all-time via `_calculate_profit()` refactorizado) y `distributed_profit` (SUM líneas). Retiro físico usa `capital_return` existente. Permiso: `treasury.manage_distributions`. 18 tests.

35. **Precios modo tabla (editable spreadsheet)**: `GET /price-lists/table` retorna todos los materiales activos con precio vigente (DISTINCT ON + LEFT JOIN). Frontend: tabla manual con celdas editables (click→input, Enter/blur→auto-save via `POST /price-lists` existente, Escape→cancel). Check verde 1.5s en save exitoso. Filtro categoría (server-side), búsqueda código/nombre (client-side). Modal historial por material. Permission-gated: `materials.edit_prices` para editar.

36. **Subcategorías de gasto (max 2 niveles)**: `parent_id` FK self-referencial en `expense_categories`. Validaciones: max 2 niveles (parent no puede tener parent), misma org, activo. Subcategoría hereda `is_direct_expense` del padre. `GET /flat` retorna lista plana con `display_name` ("PADRE > HIJO"), ordenada alfabéticamente. Frontend: selector padre en dialog config (oculta switch is_direct si tiene padre), 5 formularios treasury usan `useExpenseCategoriesFlat()` + `display_name` como label. 13 tests.

37. **Frontend categorías de terceros**: `ThirdPartyResponse.categories[]` con `display_name` y `behavior_type`. ThirdPartyFormDialog: multi-select checkbox agrupado por behavior_type, oculta `liability` y `provision`, `initial_balance` siempre 0 (balances solo via transacciones). ThirdPartiesPage: 8 tabs (Todos, Proveedores, Servicios, Clientes, Inversionistas, Pasivos, Provisiones, Genéricos). Config: 7 behavior_types en tabla, dropdown oculta `liability`/`provision`. MovementCreatePage: `liability_payment` y `expense_accrual` usan `useLiabilities()`. LiabilitiesPage filtra categorías `"liability"`.

38. **Balance Detallado: liability separado + sub-agrupación por categoría**: (a) `_classify_third_party()` separa `liability` de `service_provider` en secciones propias: `liability_advances` (activo, bal>0), `liability_debt` (pasivo, bal<0). `service_provider_payable` reemplaza `liabilities_other`. (b) Sub-agrupación opcional por `ThirdPartyCategory` en todas las secciones de terceros. `_load_tp_behavior_map()` retorna 3er dict `tp_cat_by_behavior[tp_id][behavior_type] = display_name`. `_group_by_category()` agrupa items si >1 categoría distinta; orden por total desc, "Sin Categoría" al final. Frontend: 2 niveles expand/collapse con keys `"section_key"` y `"section_key:group_label"`. Excel export con sub-grupos. `BalanceDetailedGroup` schema nuevo.

39. **Edicion de clasificacion de gastos**: `PATCH /money-movements/{id}/classification` permite cambiar `expense_category_id` y asignacion UN en movimientos tipo gasto (`expense`, `expense_accrual`, `provision_expense`, `deferred_expense`, `depreciation_expense`). No modifica montos/cuentas/terceros. Permiso: `treasury.edit_classification` (admin + liquidador). Frontend: boton "Editar Clasificacion" en `MovementDetailPage` + modal `EditClassificationModal` reutiliza `BusinessUnitAllocationSelector`. No afecta saldos — solo impacta reportes (P&L por categoria, Rentabilidad por UN).

40. **Transformation bloquea cancelacion de compra fuente**: `MaterialCostHistory` ahora registra `transformation_out` para el material fuente al transformar. Esto bloquea cancelar compras anteriores cuyo material ya fue transformado (protege integridad del costo promedio). `annul()` tambien verifica y revierte el historial del fuente. 4 source_types: `purchase_liquidation`, `adjustment_increase`, `transformation_in`, `transformation_out`.

### Inventory Module — UX Details

- **StockPage**: Manual `<Table>` (no DataTable) con expandable rows por bodega. Filters: Category, Warehouse, Search. Acciones: Trasladar, Ver Movimientos, Ajustar Stock (navegan con `?material_id=`).
- **MovementHistoryPage**: Filters Material + Warehouse al backend. Con `material_id`: muestra `balance_after` y `avg_cost_after` (running balance iterativo).
- **TransitPage**: KpiCards + bottleneck alerts + 2 DataTables (compras/ventas pendientes).
- **AdjustmentCreatePage**: Lee `material_id` de URL search params para pre-seleccionar material.
