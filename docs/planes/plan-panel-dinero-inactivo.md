# Plan — Panel de Dinero Inactivo (R1)

**Requerimiento**: Gabriel Cuartas (Reciclajes de la Costa), WhatsApp 2026-07-10. Priorizado por Daniel al frente del backlog.
**Estado**: plan para QA-refutación. Sin código todavía.
**Autor**: sesión de arquitectura. **Fecha**: 2026-07-10.

---

## 1. Contexto y objetivo

Cita textual del cliente:

> "muchas veces damos anticipos y como son tantos proveedores y terceros se nos pasa darle seguimiento a que nos entreguen, o no hacemos una gestión de cobro a un tercero, necesitamos un panel de alerta, cuando el saldo de un tercero no tenga movimiento después de 10 días yo pueda entrar a un panel donde me muestre todos esos dineros inactivos que no están en rotación (...) para poder llamar a ese proveedor que devuelva el dinero o entregue el material (...) incluso proyectos que iniciamos y se queda el dinero congelado, que la plataforma me dé ese indicador de cuánto tiempo lleva ese dinero inactivo."

Aclaración de Daniel con el cliente en el mismo chat:

> Daniel: "¿Sería solo para los saldos de terceros que le deben a reciclaje, cierto?"
> Gabriel: "Sí, que se me olvide pagar no tiene tanto problema jaja. El problema es que no nos paguen."

**Objetivo**: un panel que liste los saldos del **lado activo** (terceros que **nos deben** dinero o material) que llevan **N o más días sin movimiento**, con el indicador de días inactivos, para gestión de cobro/recuperación.

**Alcance del umbral (Daniel)**: "con opción de seleccionar el umbral de días de alertas" → filtro en pantalla, default 10 días.
**Alcance de tipos (Daniel)**: "todo el lado activo pero con filtros para que filtren por tipo de tercero" → mostrar todo el lado activo, con tabs/filtro por tipo.

---

## 2. Fuera de alcance (explícito)

- **R2 / Requerimiento G — Alerta de vencimiento por término de pago** (clientes a 30 días). Gabriel lo separó explícitamente ("eso es diferente a esto, no tienen nada que ver, porque a un cliente le puedo hacer ventas seguidas y no está inactivo"). Es greenfield (no existe concepto de plazo en el modelo) y necesita aging de cartera por documento. Va con su propio plan.
- **Vista histórica as-of** (inactividad a una fecha de corte pasada). El panel es siempre "a hoy".
- **Notificaciones push / email**. Es un panel que el usuario abre, no un sistema de alertas activas. (Si el cliente lo pide luego, es una capa aparte sobre el mismo endpoint.)

---

## 3. Decisiones de diseño (numeradas, cada una refutable)

### D1 — Definición de "última actividad" que resetea el reloj
`last_activity` de un tercero = **MAX de la fecha de negocio de todos los eventos CONFIRMADOS que afectan su saldo**, uniendo las 7 fuentes que ya fusiona el estado de cuenta unificado ([money_movements.py:874-1247](backend/app/api/v1/endpoints/money_movements.py#L874)):

| # | Fuente | Liga al tercero | Fecha del evento | Filtro |
|---|--------|-----------------|------------------|--------|
| 1 | `MoneyMovement` | `third_party_id` | `date` | `status='confirmed'` |
| 2 | `Purchase` (standalone) | `supplier_id` | `liquidated_at` | `status='liquidated'`, `liquidated_at IS NOT NULL`, `double_entry_id IS NULL` |
| 3 | `PurchaseCommission` | `third_party_id` | padre `Purchase.liquidated_at` | igual que #2 |
| 4 | `Sale` (standalone) | `customer_id` | `liquidated_at` | `status='liquidated'`, `liquidated_at IS NOT NULL`, `double_entry_id IS NULL` |
| 5 | `SaleCommission` | `third_party_id` | padre `Sale.liquidated_at` | igual que #4 **+ dedup**: excluir ventas con `commission_accrual` (ya cubiertas por #1) |
| 6 | `DoubleEntry` (dual) | `supplier_id` **y** `customer_id` | `liquidated_at` (fallback `date`@noon) | `status='liquidated'` |
| 7 | `SaleCommission` de DP | `third_party_id` | `DoubleEntry.liquidated_at` | `status='liquidated'` + mismo dedup de accrual |

**Solo `status='confirmed'`/`'liquidated'`**. Las cancelaciones/anulaciones **NO resetean el reloj**.

**Justificación**: el dinero que queda parqueado proviene del último movimiento *vivo*. Una operación cancelada netea su propio efecto; el saldo residual es más viejo y debe medirse desde la última operación que realmente lo dejó ahí. Esto es coherente con el modelo "el pasado no se reescribe" (#61) y con "nada existe hasta que se liquida" (#64).

**Trade-off que QA debe validar**: si el usuario cancela una operación reciente, esa acción no cuenta como "actividad". Para el caso de uso (perseguir dinero viejo que no rota) esto es correcto: mide la antigüedad del dinero, no la del último clic. Caso borde, aceptable v1.

**Addendum (QA 2026-07-10) — fecha de negocio vs fecha de captura**: D1 mide contra la **fecha de negocio** del evento (`date`/`liquidated_at`), no contra `created_at`. Consecuencia reconocida: un movimiento **back-dateado** (registrar hoy un pago con `date` de hace 40 días) haría que el saldo figure "inactivo 40 días" aunque alguien lo tocó hoy — falso positivo. Para el caso de uso "dinero económicamente parado" la fecha de negocio es la correcta (refleja cuándo el dinero se movió de verdad), así que se acepta el trade-off — mismo criterio que las cancelaciones. Documentado, no bloqueante.

### D2 — Alcance del lado activo (qué secciones entran)
Reusar el set `ASSET_SECTIONS` que ya existe ([reports.py:1037-1041](backend/app/services/reports.py#L1037)), **excluyendo `prepaid_expenses`**:

| Sección | Condición de signo | Entra |
|---------|-------------------|-------|
| `customers_receivable` | customer, balance > 0 | ✅ |
| `supplier_advances` | material_supplier, balance > 0 | ✅ |
| `service_provider_advances` | service_provider, balance > 0 | ✅ |
| `liability_advances` | liability, balance > 0 | ✅ |
| `investor_receivable` | investor, balance > 0 | ✅ |
| `provision_funds` | provision, balance < 0 → `abs()` | ✅ |
| `generic_receivable` | generic, balance > 0 | ✅ |
| `prepaid_expenses` | `is_system_entity`, balance > 0 | ❌ **excluida** |

**Por qué excluir `prepaid_expenses`**: son entidades de sistema (`[Prepago] {nombre}`, `is_system_entity=True`, decisión #13) que representan gastos diferidos que **nosotros** pagamos por adelantado y se consumen solos mes a mes. No es un tercero al que llamar para que "devuelva el dinero" — no es perseguible. Incluirlas sería ruido puro.

**Por qué incluir `provision_funds`**: es exactamente el "proyectos que iniciamos y se queda el dinero congelado" que mencionó Gabriel. El saldo negativo = fondos apartados no gastados. Se muestra con `abs(balance)` (igual que balance detallado, [reports.py:1056](backend/app/services/reports.py#L1056)).

**Reuso exacto**: `_classify_third_party(tp, behaviors, cat_names)` ([reports.py:1614](backend/app/services/reports.py#L1614)) devuelve UNA sección por tercero (respeta la prioridad ya definida, evita doble conteo cuando un tercero tiene múltiples behavior_types). Nos quedamos solo con los que caen en las 7 secciones de arriba.

### D3 — "A hoy", sin rango de fechas
El panel calcula inactividad contra **HOY** (fecha de negocio en Bogotá), no contra un rango. **No hay DateRangePicker.** Único parámetro temporal: `min_days`.

**Justificación**: Gabriel pide "sin movimiento en N días" = `hoy − last_activity ≥ N`. Un rango de fechas no tiene semántica aquí. (Contrasta con ExpensesReportPage, que sí es por rango — no copiar ese patrón mecánicamente.)

### D4 — Umbral configurable = filtro en pantalla (cero migración)
- `min_days: int = Query(10, ge=0)` — umbral de días inactivos. Persistido en URL (`?min_days=`).
- `min_amount: float = Query(0, ge=0)` — filtro secundario opcional: no listar saldos por debajo de este monto (para no perseguir $2.000). Default 0 = sin filtro.

Ambos son query params leídos en cada request. **Sin tabla de config, sin migración.** Si el cliente luego quiere un default por organización, es una mejora aditiva (columna en `organizations` o settings) — no la construimos ahora.

### D5 — Filtro por tipo de tercero (client-side sobre data completa)
El "tipo" de cada tercero ya viene de `_load_tp_behavior_map` ([reports.py:187](backend/app/services/reports.py#L187)) — **sin queries extra**. El backend devuelve **todos** los items del lado activo que superan `min_days`; cada item trae su `third_party_type` (derivado de la sección/behavior). El frontend filtra por tab (patrón de las 8 tabs de [ThirdPartiesPage.tsx:206](frontend/src/pages/third-parties/ThirdPartiesPage.tsx#L206)) y recalcula el subtotal del tab.

**Justificación**: el dataset es chico (terceros con saldo activo ≠ 0, típicamente decenas a bajos cientos). Filtrar client-side simplifica y da tabs instantáneas sin refetch. El `total_inactive_balance` global viene del backend; los subtotales por tab se derivan en el front.

**Tipo mostrado**: se deriva de la sección de `_classify_third_party` (una sola, por prioridad), así que es coherente y no ambiguo aunque el tercero tenga varios behavior_types.

### D6 — Terceros sin ningún movimiento (solo `initial_balance`)
Si un tercero tiene saldo del lado activo pero **cero eventos** en las 7 fuentes (típico de un anticipo migrado con `initial_balance`), `last_activity = created_at` (fecha de creación/migración) y `days_inactive = hoy − created_at`.

**Justificación**: es conservador — el corte de migración (`created_at`) suele ser **posterior** a la fecha real del anticipo, así que subestimamos la antigüedad. Para el objetivo (que el dinero viejo *aparezca*), subestimar es seguro: igual cruza el umbral. Conecta con la mejora pendiente `mejora_cutoff_date_terceros` (persistir `cutoff_date` real). **Limitación conocida documentada, no bloqueante.**

### D7 — Rendimiento: agregado en SQL, no N+1
El `last_activity` por tercero se calcula con **una** query agregada: `UNION ALL` de las 7 ramas de D1 → subquery → `func.max(event_date) GROUP BY third_party_id`. Cada rama filtra por `organization_id`.

Total del endpoint: ~3 queries (terceros con balance≠0 + `_load_tp_behavior_map` + agregado de última actividad). **No** se llama al estado de cuenta por-tercero (eso sería N+1 y mataría el panel).

### D8 — Monto mostrado y total
`amount_inactive` por item = `abs(balance)` para `provision_funds`, `balance` tal cual para el resto (todos > 0 en el lado activo). `total_inactive_balance` = suma de `amount_inactive`. Coherente con balance detallado.

### D9 — Permiso RBAC: reusar, sin migración
Endpoint y gate de ruta/sidebar usan `require_any_permission("reports.view", "reports.view_balance")` — el mismo que `balance-detailed`. **Sin migración de permisos.**

**Alternativa descartada para v1**: permiso dedicado `reports.view_inactive`. Requeriría migración RBAC (insert en `permissions` + asignación a roles + seed). Si el cliente quiere restringir este panel a un rol específico distinto de quien ve balances, se agrega después como +1 migración. Recomendación: reusar `reports.view_balance` (lo tienen viewer + liquidador + admin).

### D10 — Ubicación y nombre
- **Nombre UI**: "Dinero Inactivo".
- **Ruta**: `/reports/inactive-balances` → `ROUTES.REPORTS_INACTIVE_BALANCES`.
- **Sidebar**: sección ANÁLISIS → Reportes, ítem "Dinero Inactivo" (icono `Clock`), gated por `reports.view_balance`.
- **ReportsLayout**: nueva tab "Dinero Inactivo".

**Justificación**: reusa la infraestructura de balance (clasificación de saldos) y es de naturaleza "estado de saldos", así que vive junto a Balance General/Detallado.

---

## 4. Backend

### 4.1 Endpoint
`GET /api/v1/reports/inactive-balances` en [reports.py](backend/app/api/v1/endpoints/reports.py):
```
min_days: int = Query(10, ge=0)
min_amount: float = Query(0, ge=0)
org_context = Depends(require_any_permission("reports.view", "reports.view_balance"))
db = Depends(get_db)
→ InactiveBalancesResponse
```

### 4.2 Servicio: `get_inactive_balances(db, org_id, min_days, min_amount)`
Nuevo método en `ReportService` ([reports.py](backend/app/services/reports.py)). Pasos:
1. Cargar terceros activos con `current_balance != 0` (patrón de `get_balance_detailed`, [reports.py:1345](backend/app/services/reports.py#L1345)).
2. `tp_behaviors, tp_cat_names, tp_cat_by_behavior = self._load_tp_behavior_map(db, org_id)`.
3. Agregado de última actividad (D7): helper nuevo `_get_last_activity_map(db, org_id) -> dict[UUID, date]` — `UNION ALL` de las 7 ramas de D1, `MAX` group by tercero. **Solo eventos confirmados/liquidados.**
4. Para cada tercero: `section = _classify_third_party(...)`; si `section` no está en las 7 secciones activas (D2) → descartar.
5. `last = last_activity_map.get(tp.id) or tp.created_at.date()` (D6).
6. `days_inactive = (today_bogota - last).days`.
7. Filtrar `days_inactive >= min_days` y `amount_inactive >= min_amount`.
8. `third_party_type` derivado de la sección; `amount_inactive` por D8.
9. Ordenar por `days_inactive DESC` (más viejo arriba), tie-break `amount_inactive DESC`.
10. Devolver `InactiveBalancesResponse`.

`today_bogota` = fecha de negocio de hoy (mediodía UTC, patrón `BusinessDate` de [app/utils/dates.py](backend/app/utils/dates.py)). `days_inactive` se calcula sobre `date`, no `datetime`.

### 4.3 Schema ([schemas/reports.py](backend/app/schemas/reports.py))
```
class InactiveBalanceItem(BaseModel):
    third_party_id: str
    third_party_name: str
    third_party_type: str        # "customer" | "material_supplier" | "service_provider" | "liability" | "investor" | "provision" | "generic"
    section: str                 # la sección de _classify_third_party (para el label)
    amount_inactive: float
    days_inactive: int
    last_activity_date: date | None   # None solo si cae al fallback created_at y queremos marcarlo; ver nota
    has_movements: bool          # False = nunca tuvo eventos (fallback a created_at) → badge "sin movimientos"

class InactiveBalancesResponse(BaseModel):
    as_of: date
    min_days: int
    min_amount: float
    total_inactive_balance: float
    item_count: int
    items: list[InactiveBalanceItem]
```

`has_movements=False` alimenta un badge en la UI ("sin movimientos, desde creación") para ser transparentes sobre D6.

---

## 5. Frontend

Patrones tomados de ExpensesReportPage, ThirdPartiesPage, BalanceDetailedPage (mapeados).

- **Página**: `frontend/src/pages/reports/InactiveBalancesPage.tsx`.
- **Type**: `types/reports.ts` → `InactiveBalanceItem`, `InactiveBalancesResponse`.
- **Service**: `services/reports.ts` → `getInactiveBalances(params)`.
- **Hook**: `hooks/useReports.ts` → `useInactiveBalances({ min_days, min_amount })`, `queryKey: ["reports", "inactive-balances", params]`.
- **Filtros** (sin DateRangePicker):
  - Umbral días: `<Input type="number" min={0}>` (default 10), persistido en URL `?min_days=`.
  - Monto mínimo: `<Input type="number" min={0} step={1000}>` (default 0), URL `?min_amount=`.
  - Wrapper `ResponsiveFilterBar` (`flex flex-col sm:flex-row ...`).
- **Tabs por tipo** (D5): patrón `overflow-x-auto -mx-3 px-3 sm:mx-0` + `TabsList inline-flex w-max sm:w-auto sm:flex-wrap`. Tabs: Todos / Clientes / Proveedores / Servicios / Provisiones / Inversionistas / Pasivos / Genéricos. Filtra client-side por `third_party_type`; subtotal por tab derivado.
- **Tabla responsive**: `DataTable` con `renderMobileCard`. Columnas desktop: Tercero · Tipo · **Días inactivos** (badge de color por severidad) · Monto · Última actividad. Card móvil: nombre + tipo + días + monto.
  - KPIs arriba (grid `grid-cols-1 sm:grid-cols-2 md:grid-cols-4`): Total inactivo, # terceros, umbral aplicado.
  - Cada fila enlaza al **estado de cuenta** del tercero (`EntityLink` con `saveScroll`, decisión #57) — es la acción natural ("ver por qué está parado").
  - Badge "sin movimientos" cuando `has_movements=false`.
- **Excel**: `exportInactiveBalancesExcel(data)` en `excelExport.ts`. Columnas: Tercero · Tipo · Días · Monto (número sumable, `CURRENCY_FMT`) · Última actividad. Respeta el tab activo (contexto en header).
- **Ruta**: `App.tsx` `<Route path={ROUTES.REPORTS_INACTIVE_BALANCES} element={<P permission="reports.view_balance">...}>`; `constants.ts` ROUTES; `Sidebar.tsx` ítem con icono `Clock`; `ReportsLayout.tsx` tab.

---

## 6. Tests (obligatorio — CLAUDE.md)

`backend/tests/test_inactive_balances.py`:

**Caso feliz**
1. `test_supplier_advance_appears` — anticipo a proveedor, última actividad hace 15 días, `min_days=10` → aparece, `days_inactive=15`, `amount=balance`.
2. `test_customer_receivable_appears` — CxC de cliente inactiva → aparece.

**Umbral**
3. `test_below_threshold_excluded` — mismo tercero, `min_days=20` → no aparece.
4. `test_min_amount_filter` — saldo de $500 con `min_amount=1000` → excluido.
5. `test_min_days_zero_returns_all_active_side` — `min_days=0` → todos los del lado activo con balance≠0.

**Lado activo / clasificación**
6. `test_liability_side_excluded` — tercero al que le debemos (saldo pasivo) inactivo → NO aparece.
7. `test_prepaid_expense_excluded` — `is_system_entity` con balance>0 → NO aparece (D2).
8. `test_provision_funds_included_abs` — provisión con balance<0 → aparece con `amount=abs(balance)` (D2/D8).
9. `test_zero_balance_excluded` — balance 0 → no aparece.

**Fuentes de última actividad (D1)**
10. `test_last_activity_from_liquidated_sale` — última actividad es una venta liquidada (no MM) → `last_activity_date = sale.liquidated_at`.
11. `test_last_activity_from_money_movement` — un `advance_payment` reciente resetea el reloj.
12. `test_cancellation_does_not_reset_clock` — venta vieja (viva, 40 días) + otra venta cancelada ayer → `days_inactive` mide desde la viva (40), no desde la cancelación (D1 trade-off).
13. `test_double_entry_not_double_counted` — DP no infla ni duplica (respeta `double_entry_id IS NULL` en compras/ventas standalone).

**Edge**
14. `test_no_movements_falls_back_to_created_at` — tercero con `initial_balance`, cero eventos → `has_movements=False`, `days_inactive` desde `created_at` (D6).

**Cross-module / multi-tenancy**
15. `test_other_org_not_leaked` — terceros de otra org no aparecen (organization_id en todas las ramas del agregado).

**RBAC**
16. `test_requires_permission` — sin `reports.view`/`reports.view_balance` → 403; con permiso → 200.

---

## 7. Criterios de aceptación (mapeados a tests)

| # | Criterio | Test |
|---|----------|------|
| CA1 | Muestra saldos del lado activo inactivos ≥ umbral | 1, 2 |
| CA2 | El umbral de días es configurable y filtra | 3, 5 |
| CA3 | No muestra lo que nosotros debemos (pasivo) | 6 |
| CA4 | Excluye entidades de sistema no perseguibles | 7 |
| CA5 | Incluye provisiones/proyectos congelados | 8 |
| CA6 | El reloj usa la última actividad real que dejó el saldo | 10, 11, 12 |
| CA7 | No duplica por Pasa Mano ni por comisiones con accrual | 13 |
| CA8 | Terceros migrados sin movimientos aparecen (conservador) | 14 |
| CA9 | Aislamiento multi-tenant | 15 |
| CA10 | Gated por permiso | 16 |
| CA11 | Filtro por tipo de tercero | (frontend; verificación manual + `third_party_type` correcto en 1/2/6/8) |

---

## 8. Riesgos y limitaciones conocidas (para comunicar)

1. **Migrados sin `cutoff_date` real** (D6): la antigüedad se mide desde la fecha de carga, no desde la fecha real del anticipo. Conservador. Mejora futura: `mejora_cutoff_date_terceros`.
2. **Cancelaciones no cuentan como actividad** (D1): decisión deliberada; el panel mide antigüedad del dinero, no del último clic.
3. **Sin histórico as-of**: el panel es "a hoy". No responde "¿qué estaba inactivo hace 3 meses?".
4. **Permiso reusado** (D9): quien ve balances ve este panel. Si se necesita gate propio → +1 migración RBAC.
5. **Back-dating = falso positivo** (D1 addendum): un movimiento registrado hoy con fecha de negocio vieja aparece como "inactivo" desde esa fecha vieja. Se mide el dinero económicamente parado, no el último clic. Deliberado.

---

## 9. Focos para QA (dónde atacar)

1. **Que el agregado UNION ALL no pierda ninguna de las 7 fuentes** ni cuente DPs dos veces — verificar los filtros `double_entry_id IS NULL` (fuentes 2/4) y la rama dual de DP (fuente 6, supplier_id + customer_id).
2. **Dedup de `commission_accrual`** (fuentes 5/7): una comisión de venta con accrual ya aparece como MoneyMovement (fuente 1) — no debe contarse también por SaleCommission.
3. **`status` correcto por fuente**: MM `confirmed`; operaciones `liquidated` con `liquidated_at IS NOT NULL`. Que ninguna rama incluya `cancelled`/`annulled` (D1).
4. **Signo de `provision_funds`**: `abs()` y que el disparo sea balance < 0.
5. **`prepaid_expenses`/system entities fuera** (D2).
6. **`organization_id` en cada rama** del agregado (multi-tenancy).
7. **Timezone**: `days_inactive` sobre fecha de negocio (Bogotá/noon UTC), no `datetime` crudo — que no haya off-by-one por UTC.
8. **N+1**: confirmar que es agregado en SQL, no un loop de statements.

---

## 10. Estimación

- **Backend**: endpoint + `get_inactive_balances` + `_get_last_activity_map` (7 ramas) + schema + 16 tests. **Medio día.**
- **Frontend**: página + tabs + 2 filtros + tabla responsive + Excel + ruta/sidebar/layout. **Medio día.**
- **Sin migración.**
- **Total: ~1 día** de trabajo, tests incluidos.

---

## 11. Preguntas abiertas — RESUELTAS (QA + Daniel, 2026-07-10)

1. `min_amount` en v1: **SÍ**, default 0 (inocuo, ahorra "perseguir $2.000").
2. Orden por defecto: **días inactivos DESC** (el viejo arriba = el caso de uso). Toggle a monto disponible client-side.
3. Enlace al estado de cuenta del tercero: **SÍ**, reusar (cero superficie nueva, es la acción natural "ver por qué está parado").

## 12. Watch-points de implementación (QA, aprobación 2026-07-10)

Aprobado el plan; estos son puntos de *implementación* a cuidar (no gaps del plan):

1. **🔴 El agregado filtra `confirmed`/`liquidated` SOLO — NO copiar `status.in_(["liquidated","cancelled"])` del statement.** El estado de cuenta incluye canceladas a propósito (para mostrar los eventos de reversa); el panel las excluye (D1). Es el #1 lugar donde un copy-paste mete el bug: una rama que arrastre `cancelled` haría que una cancelación de ayer resetee el reloj y rompa D1 / test 12. El código del statement al lado invita a copiarlo mal.
2. **🔴 Rol dual de DP → DOS ramas en el UNION.** El statement filtra `(supplier_id==X) OR (customer_id==X)` para UN tercero; el agregado agrupa por tercero, así que la DP debe emitir su fecha bajo AMBAS llaves: una rama `GROUP BY supplier_id`, otra `GROUP BY customer_id`. Si solo se agrupa por una, el otro rol pierde la actividad de la DP (rompe test 13).
3. **🔴 Timezone Bogotá para TODO cálculo de fecha, incluido el fallback D6.** `days_inactive = today_bogota − event_date` debe derivar la fecha en Bogotá, no `datetime.date()` crudo en UTC (off-by-one: un evento a las 02:00 UTC es el día anterior en Bogotá). Aplica IGUAL a `tp.created_at` del fallback D6 — convertir a Bogotá, no `.date()` directo.
4. **🔴 `organization_id` en CADA rama del UNION** (multi-tenancy, test 15). Un filtro omitido en una rama = fuga cross-tenant.
5. **🟢 El dedup de `commission_accrual` NO es load-bearing para el MAX.** La comisión aparece como MM (fuente 1, `date=liquidated_at` por #61) y como SaleCommission (fuente 5, posicionada en `liquidated_at`) — misma fecha, el MAX no cambia si se cuenta dos veces. El dedup importa para la SUMA (statement), no para el MAX. Mantenerlo por paridad, sin sobre-ingenierizar.
