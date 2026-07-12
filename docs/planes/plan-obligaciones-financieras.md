# Plan F — Módulo de Obligaciones Financieras (bidireccional)

**Fecha**: 2026-07-08 · **Estado**: v2.1 (2026-07-10) — **QA APROBÓ** (luz verde con corrección de alcance aplicada: sección `loans_receivable` DIFERIDA) · **Spec**: cerrada en llamada con el cliente (2026-07-08, respuestas 1–8 + espejo por cobrar)

> **Δ v2** (revisión contra los deploys del 10-jul: Modelo L #64-66, revalorización #67, Dinero Inactivo #68): catálogo MM 31→39 (era 21→29); conciliación #59 hoy tiene 5 líneas (pasa a 6); mapas tipo→signo enumerados con precisión (los 6 sitios que #67 dejó documentados, incl. los duplicados del statement que la v1 omitía); anulación adopta el patrón #67 (bloqueo en Tesorería + banner guía ya construido); **gap nuevo**: guard espejo para anulación retroactiva de movimientos de capital; **integración nueva**: Dinero Inactivo #68 (excluir accruals del activity map).
>
> **Δ v2.1 (corrección QA)**: la sección `loans_receivable` queda **DIFERIDA** — es cosmética (hoy los préstamos clasifican como `investor_receivable`, YA contado en todos los balances y en el panel #68 como tipo `investor`; la sub-agrupación por categoría #38 ya los separa visualmente de los socios). Hacerla tocaría ~7 enumeradores de secciones de activo (`ASSET_SECTIONS` ×2 en reports.py:1229/1343, grupos del balance detallado vivo/as-of ×4 en :1555/1591/1724/1753, `_INACTIVE_SECTION_TYPE` :338) con riesgo de corrupción silenciosa (un enumerador olvidado = deudores que desaparecen de ese reporte). Si el cliente pide la etiqueta propia: +1 aparte con disciplina de mapas de signo + test de invariante (total de activos del balance general NO cambia). ⚠️ Anclajes de línea verificados al 2026-07-10 — ubicar por símbolo (grep), no por número.

---

## 1. Requerimiento (acordado con el cliente)

Terceros le prestan dinero a la empresa (obligaciones **por pagar**) y la empresa presta dinero
a terceros (préstamos **por cobrar**). Hoy manejan intereses y abonos a capital manualmente
con movimientos sueltos. El módulo automatiza el ciclo completo:

| Regla | Decisión del cliente |
|---|---|
| Cálculo de interés | Prorrateo por días sobre saldo vigente. **Base 30 SIEMPRE** (30/360). Mes calendario del 1 al 30. El día del abono/desembolso cuenta con el saldo **nuevo** |
| Reconocimiento | **Devengo en ambos lados**: causación mensual al P&L aunque no se pague/cobre (gasto financiero o ingreso financiero) |
| Composición | **Interés simple**: solo sobre capital. Los intereses pendientes quedan congelados como deuda, NO capitalizan |
| Abonos | **Libres**: monto y fecha a discreción, sin plazo, cuota ni tabla de amortización |
| Terceros | **1 tercero = 1 obligación** (convención del cliente). Tasa fija de por vida — cambio de tasa = tercero/obligación nueva. Son los terceros `investor_type="obligacion_financiera"` existentes; **el signo del saldo define el lado** (negativo = les debemos, positivo = nos deben) |
| Desembolso | El módulo registra el desembolso inicial (mueve cuenta). Migración: saldos actuales de esos terceros = **solo capital** (intereses pendientes arrancan en $0) |
| Pagos | Intereses y capital son **dos pagos separados** |
| Vistas | Listas **separadas** por dirección: capital vigente, intereses pendientes, tasa por obligación; deuda/acreencia consolidada; tasa promedio; intereses del mes por pagar/cobrar; estado de cuenta por obligación |

**Ejemplo canónico del cliente** (valida la matemática): deben $20M al 2% mensual, abonan
$10M el día 16 → interés del mes = 20M × 2% × 15/30 + 10M × 2% × 15/30 = **$200.000 + $100.000**.

### Supuestos avisados a Daniel (2026-07-08, no objetados)

1. **Pagos parciales de intereses**: soportados (monto libre ≤ intereses pendientes).
2. **No se puede abonar más que el capital vigente** ni pagar más intereses que los pendientes (400).
3. **Tasa promedio ponderada** por capital vigente: `Σ(capital × tasa) / Σ(capital)`.
4. **Batch manual** tipo "Aplicar depreciaciones" (#21) — el sistema no tiene jobs. Botón "Causar intereses pendientes".
5. **Movimiento de capital retroactivo a un mes ya causado → bloqueado** (400). Alternativa: anular la causación y recausar.
6. **Desembolsos adicionales a la misma obligación permitidos** (mismo tercero, misma tasa, más plata): suben capital y entran como tramo en el cálculo del mes. (El cliente solo definió "tasa nueva = tercero nuevo".)

## 2. Alcance

| Incluido | Excluido |
|---|---|
| Entidad `FinancialObligation` bidireccional + migración | Tablas de amortización / cuota fija / plazos |
| 8 movement types nuevos con efectos espejados | Interés compuesto / capitalización |
| Batch de causación mensual idempotente (patrón #21) | Historial de tasas (tasa fija de por vida) |
| Motor de cálculo 30/360 por tramos (función pura, unit-testeable) | Jobs automáticos (batch manual v1) |
| Integración transversal: P&L (+ línea Ingresos Financieros), conciliación #59 (5→6 líneas), Cash Flow, estado de cuenta #16, balance histórico #41, Reporte de Gastos #44, Dinero Inactivo #68, anulaciones | Posición neta consolidada (cliente pidió listas separadas) |
| Página Obligaciones (2 tabs) + detalle + acciones + KPIs | Edición de movimientos del módulo (solo anular, patrón tesorería) |
| 2 permisos RBAC nuevos + migración de permisos | Notificaciones/recordatorios de pago |
| — | Mezcla de movimientos manuales sobre terceros con obligación (se documenta, no se bloquea) |
| — | **Sección `loans_receivable` en balances (DIFERIDA, QA v2.1)**: los préstamos ya cuentan como `investor_receivable` en todos los balances y el panel #68; el split de etiqueta va como +1 aparte (ver Δ v2.1) |

## 3. Modelo de datos

### 3.1 `FinancialObligation` (tabla nueva `financial_obligations`)

```python
class FinancialObligation(Base, TimestampMixin, OrganizationMixin):
    id: GUID pk
    third_party_id: GUID FK third_parties, index          # 1 obligación ACTIVA por tercero (validación en service, no constraint DB)
    direction: str                                         # 'payable' | 'receivable'
    monthly_rate: Numeric(5, 2)                            # % mensual, fija de por vida (2.00 = 2%)
    capital_balance: Numeric(15, 2) default 0              # capital vigente
    pending_interest: Numeric(15, 2) default 0             # intereses causados sin pagar/cobrar
    accrual_start_period: String(7)                        # "YYYY-MM": primer mes que causa el módulo
    last_accrued_period: String(7) nullable                # último mes causado (guard retroactivo + batch)
    disbursement_date: DateTime nullable                   # null si nació por migración de saldo
    status: str default 'active'                           # 'active' | 'settled'
    notes: String(500) nullable
```

- **Validación 1:1**: crear obligación falla con 400 si el tercero ya tiene una `active`.
- **Validación de tercero**: debe tener behavior_type `investor` con categoría de obligaciones
  (mismo filtro de `investor_type="obligacion_financiera"` — reutilizar el mecanismo del
  endpoint `/investors`, decisión #33).
- **Dos modos de creación**:
  - **Con desembolso**: requiere `account_id` + monto → crea el MM de desembolso (mueve cuenta y tercero) y setea `capital_balance`.
  - **Desde saldo existente (migración)**: sin cuenta ni MM (patrón `historical_load` #46). Exige que el tercero tenga saldo ≠ 0 con el **signo coherente** con la dirección (payable → negativo; receivable → positivo) y toma `capital_balance = abs(current_balance)`. Los intereses pendientes arrancan en $0 (respuesta 6b).
- `settled`: cierre **manual** con capital y pendientes en $0 (400 si no). Obligación settled no acepta movimientos ni causaciones.

### 3.2 `MoneyMovement` — columnas nuevas

```python
financial_obligation_id: GUID FK financial_obligations, nullable, index   # mismo patrón que sale_id/purchase_id
obligation_period: String(7) nullable                                     # "YYYY-MM", SOLO causaciones
```

- **Idempotencia de causación**: índice único parcial
  `(financial_obligation_id, obligation_period) WHERE movement_type IN (accruals) AND status = 'confirmed'`
  — espejo del `uq_asset_depreciation_period` de `AssetDepreciation` ([fixed_asset.py:190](../../backend/app/models/fixed_asset.py#L190)), pero anular libera el slot para recausar.
- El desglose por tramos va en `description` (auditoría humana): `"Intereses 2026-07: $20.000.000 × 15d + $10.000.000 × 15d @ 2%"`.

### 3.3 Los 8 movement types nuevos (`VALID_MOVEMENT_TYPES`, [models/money_movement.py:56](../../backend/app/models/money_movement.py#L56) — pasa de 31 a 39; los 4 de revalorización #67 entraron después de la v1 de este plan)

| Tipo | Cuenta | Tercero | P&L | Dirección |
|---|---|---|---|---|
| `obligation_disbursement` | + (entra el préstamo) | − (les debemos) | no | payable |
| `obligation_interest_accrual` | NULL | − (debemos más) | **gasto** (categoría, como `expense_accrual` #14) | payable |
| `obligation_interest_payment` | − | + | no (paga deuda ya causada) | payable |
| `obligation_capital_payment` | − | + | no | payable |
| `loan_disbursement` | − (sale el préstamo) | + (nos deben) | no | receivable |
| `loan_interest_accrual` | NULL | + (nos deben más) | **ingreso financiero** (línea nueva) | receivable |
| `loan_interest_collection` | + | − | no | receivable |
| `loan_capital_collection` | + | − | no | receivable |

- **Creación SOLO vía módulo** (endpoints propios), nunca desde `MovementCreatePage` — patrón `commission_accrual` (#23). El funnel `_create_movement` los acepta (para efectos y pago inmediato futuro) pero el endpoint genérico los rechaza.
- `obligation_interest_accrual` lleva `expense_category_id` (categoría "Intereses" del cliente u otra que elija al causar — default configurable por obligación **NO**: v1 la pide el batch una vez y la aplica a todas; ver §5).
- Los movimientos actualizan **transaccionalmente** los contadores de la obligación (capital/pendientes) además de los efectos estándar (cuenta/tercero). Invariante por obligación: `Δtercero == Δ(capital + pendientes)` con el signo de la dirección.

### 3.4 Migraciones (3)

1. Tabla `financial_obligations`.
2. Columnas + índice parcial en `money_movements`.
3. Permisos RBAC: `treasury.view_obligations` (granular bajo master `treasury.view`, patrón `view_provisions`) + `treasury.manage_obligations` → INSERT en `permissions` + asignación a roles sistema (admin implícito; `liquidador` ambos; `viewer` solo view). ⚠️ Los permisos se leen de BD (regla CLAUDE.md) — sin esta migración el módulo es invisible.

IDs únicos via `uuid4().hex[:12]`, encadenar desde el head vigente. Aplicar en dev (5434) y test (5433), NUNCA prod.

## 4. Motor de cálculo (función pura — el corazón testeable)

```python
def compute_monthly_interest(
    capital_events: list[tuple[int, Decimal]],  # [(dia_efectivo 1..30, capital_vigente_desde_ese_dia)]
    monthly_rate: Decimal,                      # 2.00 = 2%
    ) -> tuple[Decimal, str]:                   # (monto quantize 0.01, desglose humano)
```

Reglas exactas:
- El mes SIEMPRE tiene 30 días (base fija). Días de evento > 30 (día 31) se tratan como **día 30**. Febrero: el día 28 es el día 28 (quedan 3 días de saldo nuevo: 28, 29, 30 "virtuales").
- Tramos: evento en día D → días `D-1` con saldo anterior, saldo nuevo desde D inclusive.
  Interés = `Σ saldo_tramo × (rate/100) × días_tramo/30`, quantize 0.01 al TOTAL (no por tramo).
- Mes del desembolso: capital corre desde el día del desembolso inclusive (día 16 → 15 días).
- Varios eventos el mismo día: neto (se colapsan al último saldo del día).
- Capital $0 todo el mes → interés $0 (no genera MM; el batch lo salta).

Los `capital_events` del mes M se derivan de los MM confirmados de capital/desembolso de la
obligación con fecha en M + el saldo de arranque (capital al cierre de M−1, reconstruido
recorriendo los MM — NO desde el contador actual, para que el batch sea correcto aunque se
corra tarde con abonos de meses posteriores ya registrados).

## 5. Batch de causación (patrón depreciación #21)

- `GET /financial-obligations/pending-accruals` → por obligación activa: períodos cerrados
  (mes vencido: período < mes actual) desde `accrual_start_period` (o el mes del desembolso,
  el mayor) que no tengan causación confirmada. Con monto calculado (preview).
- `POST /financial-obligations/accrue-pending` body `{expense_category_id, income_category_id?}`
  → crea las causaciones en orden cronológico, actualiza `pending_interest` y
  `last_accrued_period`. Idempotente (índice parcial + re-chequeo). Solo períodos cerrados —
  **nunca el mes en curso** (los abonos del mes aún pueden llegar).
- Guard retroactivo (supuesto 5): crear abono/desembolso/recaudo de capital con `date` en un
  período `<= last_accrued_period` → 400 "El período ya tiene intereses causados; anule la
  causación para corregir".
- **Anulación SOLO desde el módulo** (patrón #67, cambia respecto a la v1 que extendía `annul()`):
  los 8 tipos entran a un set `OBLIGATION_MOVEMENT_TYPES` en `money_movement.annul()` → anular
  directo desde Tesorería = **422** con mensaje guía (espejo exacto de `ASSET_MOVEMENT_TYPES`,
  [money_movement.py:1032](../../backend/app/services/money_movement.py#L1032)); el frontend reusa
  el banner guía de `MovementDetailPage` recién construido para activos, apuntando a la obligación.
  La anulación real vive en un endpoint del módulo (§6) que aplica las reglas siguientes.
- Anular una causación: revierte `pending_interest`, libera el período (re-causable) y ajusta
  `last_accrued_period` si era el último.
- Anular pago/recaudo de **intereses**: restaura `pending_interest`. No toca tramos → sin guard
  de período.
- Anular movimiento de **capital** (abono, recaudo o desembolso adicional) cuyo `date` cae en un
  período `<= last_accrued_period` → **400** "El período ya tiene intereses causados; anule primero
  las causaciones desde ese período". **Guard espejo del supuesto 5** (gap detectado en v2): sin él,
  la causación ya calculada queda con tramos falsos — mismo agujero retroactivo que el guard de
  creación cierra, pero por la puerta de atrás.
- Anular desembolso inicial: 400 si la obligación tiene cualquier otro movimiento confirmado posterior.

## 6. Endpoints (`/api/v1/financial-obligations/`)

| Método | Ruta | Permiso | Nota |
|---|---|---|---|
| GET | `/` | view_obligations (o master) | lista con filtro `direction`, `status` |
| GET | `/{id}` | view | detalle + contadores |
| GET | `/{id}/statement` | view | movimientos de la obligación (MM por `financial_obligation_id`) |
| GET | `/summary` | view | KPIs por dirección: capital total, pendientes, tasa promedio ponderada, proyección mes en curso |
| GET | `/pending-accruals` | view | preview del batch |
| POST | `/` | manage_obligations | crear (con desembolso o desde saldo) |
| POST | `/accrue-pending` | manage | batch causación |
| POST | `/{id}/capital-payment` | manage | abono/recaudo de capital (`amount`, `account_id`, `date`) |
| POST | `/{id}/interest-payment` | manage | pago/recaudo de intereses (parcial ok) |
| POST | `/{id}/disbursement` | manage | desembolso adicional (supuesto 6) |
| POST | `/{id}/settle` | manage | cerrar (capital y pendientes en 0) |
| POST | `/movements/{mm_id}/annul` | manage | anular movimiento de obligación con las reglas de §5 (desde Tesorería directa → 422) |

La dirección de la obligación decide el movement type concreto de cada acción — el frontend
no conoce los 8 tipos, solo las acciones.

## 7. Integraciones transversales (checklist — aquí vive el riesgo)

| Sistema | Cambio | Anclaje |
|---|---|---|
| **P&L `_calculate_profit`** | `obligation_interest_accrual` → entra al pool de gastos por categoría (sumarlo al `IN` de mm_filters junto a `expense_accrual`). `loan_interest_accrual` → **línea nueva `interest_income`** paralela a `service_income`: suma a `total_gross_profit`, NO a `margin_base` (margen es de ventas). **Espejo filtro-por-filtro de `service_income`** (QA v2.1): mismos filtros de fechas, status y `_active_at_cutoff`/`cutoff_dt` — hereda gratis la corrección as-of #41. Response + schema + frontend P&L (Periodo y Mensual) + Excel | reports.py `_calculate_profit`, línea ~425 (mm_filters) y ~503 (fórmula) |
| **Conciliación #59** | `interest_income` es línea no-UN → agregarla a `PnlReconciliation` + `PasaManoCard` + Excel. Hoy son **5 líneas** (`oversell_cost_adjustment` entró con #65) → pasa a 6. ⚠️ `test_reconciliation_residual_zero` REVIENTA si se omite — es el guardrail funcionando, no un bug | [schemas/reports.py:647](../../backend/app/schemas/reports.py#L647) + reports.py sección 9 de profitability |
| **EXPENSE_MOVEMENT_TYPES** | + `obligation_interest_accrual` ([reports.py:3749](../../backend/app/services/reports.py#L3749)) → entra solo a: P&L por categoría (#22, nuevo `source_type` + label frontend `EXPENSE_SOURCE_LABELS`), Reporte de Gastos #44, Rentabilidad UN (cae al prorrateo **general** — igual que sus gastos manuales de intereses hoy; sin cambio de comportamiento), Costo Real. `loan_interest_accrual` NO entra (es ingreso) | |
| **Cash Flow (#7)** | inflows: `obligation_disbursement`, `loan_interest_collection`, `loan_capital_collection`. outflows: `loan_disbursement`, `obligation_interest_payment`, `obligation_capital_payment`. Desglosados con labels propios | service de cash flow |
| **Estado de cuenta unificado (#16)** | Los 8 tipos aparecen en la lista automáticamente (son MM del tercero), **PERO el saldo corrido usa los mapas duplicados del endpoint** (fila siguiente) — sin esa entrada el movimiento se lista con efecto $0, corrupción silenciosa del running balance. + labels legibles al mapa frontend (`movementTypeLabels`) | |
| **Mapas tipo→signo — los 6 sitios (#67 los dejó enumerados)** | Agregar los 8 tipos a: (1) `ACCOUNT_BALANCE_DIRECTION` [reports.py:93](../../backend/app/services/reports.py#L93) y (2) `THIRD_PARTY_BALANCE_DIRECTION` [reports.py:116](../../backend/app/services/reports.py#L116) — alimentan el balance histórico #41 (cuentas y terceros as-of; sin esto el `as_of_date` queda mudo, silencioso y grave); (3+4) sus **duplicados** en [money_movements.py:56](../../backend/app/api/v1/endpoints/money_movements.py#L56) y [:84](../../backend/app/api/v1/endpoints/money_movements.py#L84) (saldo corrido del estado de cuenta — los más fáciles de olvidar); (5) `INFLOW_TYPES`/`OUTFLOW_TYPES` [reports.py:142](../../backend/app/services/reports.py#L142) — cash flow opening **y** dashboard MTD; (6) efectos vivos en el service del módulo. Guardrail ya existente: `test_golden_parity_statement_vs_balance_detailed` (#61) revienta si statement y balance divergen | los mismos 6 sitios de la terna de #67 |
| **Balance/Balance Detallado (#31)** | Ya funciona **SIN cambios**: payable (saldo −) → `investors_obligations`; receivable (saldo +) → `investor_receivable`. La sub-agrupación por categoría (#38) ya separa visualmente "Obligaciones Financieras" de "Socios" dentro de la sección. Split a sección propia: DIFERIDO (Δ v2.1) | `_classify_third_party` — cero cambios |
| **Anulación (`money_movement.annul()`)** | **Bloquear** anulación directa en Tesorería: set `OBLIGATION_MOVEMENT_TYPES` → 422 con mensaje guía (patrón `ASSET_MOVEMENT_TYPES` de #67, [money_movement.py:1032](../../backend/app/services/money_movement.py#L1032)). La anulación real va por el endpoint del módulo con las reglas de §5 (incl. guard espejo retroactivo) | money_movement.py |
| **Dinero Inactivo (#68)** | (a) `_get_last_activity_map` rama 1 (MM confirmados, [reports.py:244](../../backend/app/services/reports.py#L244)) debe **EXCLUIR** `obligation_interest_accrual` y `loan_interest_accrual`: son batch, no actividad real del tercero — sin la exclusión, un deudor de préstamo moroso JAMÁS aparece inactivo porque la causación mensual le resetea el reloj (rompe exactamente el caso de Gabriel). Pagos/recaudos/desembolsos SÍ resetean. (b) Secciones: SIN cambios — los deudores de préstamo ya entran al panel como `investor_receivable` (tipo `investor`, ya presente en `_INACTIVE_SECTION_TYPE` [reports.py:338](../../backend/app/services/reports.py#L338)) | reports.py |
| **Endpoint genérico de MM** | `POST /money-movements` rechaza los 8 tipos (creación solo vía módulo) — validación explícita con mensaje | money_movement.py create |
| **Treasury UI** | `TreasuryPage`: labels de los 8 tipos en la lista/detalle (sin tab nuevo v1 — se ven en el estado de cuenta del tercero y en el módulo). `MovementDetailPage`: banner guía hacia la obligación ocultando el botón Anular (patrón recién construido para activos en #67 — constantes tipo `ASSET_OWNED_TYPES`/`REVALUATION_TYPES`, agregar el set de obligaciones) + `EntityLink` | |
| **queryInvalidation (#27)** | `invalidateAfterObligation`: financial-obligations + money-movements + money-accounts + third-parties + reports + treasury-dashboard | queryInvalidation.ts |
| **RBAC frontend** | sidebar Tesorería → "Obligaciones" gated por `treasury.view \|\| treasury.view_obligations` (master+granular #26); ruta protegida; acciones gated por manage | |

## 8. Frontend (mobile-first, patrones CLAUDE.md)

| Pieza | Detalle |
|---|---|
| `ObligationsPage` (`/treasury/obligations`) | Tabs "Por Pagar" / "Por Cobrar" (`?tab=`). KPIs por tab (`grid-cols-1 sm:grid-cols-2 md:grid-cols-4`): Capital total, Intereses pendientes, Tasa promedio ponderada, Proyección mes en curso. Tabla desktop + cards mobile (dual render). Botón "Causar intereses pendientes" (abre modal con preview del batch + selector de categoría de gasto/ingreso) |
| `ObligationDetailPage` | Contadores grandes (capital, pendientes, tasa), acciones (Abono a capital, Pagar/Recaudar intereses, Desembolso adicional, Cerrar), estado de cuenta de la obligación (tabla + cards), link al tercero |
| `ObligationCreateDialog` | Dirección, tercero (selector filtrado a obligaciones financieras SIN obligación activa), tasa, modo: desembolso (cuenta + monto + fecha) o "desde saldo actual" (muestra el saldo y valida signo) |
| Formularios de pago/abono | `MoneyInput` + cuenta + fecha (`BusinessDate`) + validaciones espejo del backend (max = capital/pendientes) |
| P&L | Línea "Ingresos Financieros" (Periodo + Mensual + Excel) con drill-down a treasury filtrado por tipo (patrón #49, `movement_type` CSV ya existe) |
| Types/services/hooks | `types/financialObligation.ts`, `services/financialObligations.ts`, `hooks/useFinancialObligations.ts` (React Query + toasts) |

## 9. Tests (~41)

**Motor de cálculo (unit, sin BD — 8):** ejemplo canónico del cliente (200K+100K con abono día 16); mes completo sin eventos; desembolso a mitad de mes; día 31→30; febrero; varios abonos mismo mes; abono a $0 (capital saldado, tramo final sin interés); quantize.

**Ciclo payable (7):** crear con desembolso (cuenta+, tercero−, capital ok); crear desde saldo existente (sin MM, capital = |saldo|, valida signo — 400 si positivo); causar mes (MM accrual + pendientes + P&L gasto por categoría); batch idempotente (segunda corrida = 0 nuevos); pago parcial de intereses; abono a capital (afecta tramos del mes siguiente); settle (400 con saldos, ok en 0, bloquea movimientos).

**Ciclo receivable (5):** desembolso (cuenta−, tercero+); causación → `interest_income` en P&L (NO en gastos); recaudo intereses; recaudo capital; espejo del ejemplo canónico.

**Validaciones (6):** abono > capital → 400; pago intereses > pendientes → 400; segunda obligación activa mismo tercero → 400; tercero sin categoría obligación → 400/422; movimiento de capital retroactivo a mes causado → 400; tipos de obligación por `POST /money-movements` genérico → 400.

**Anulaciones (6):** anular causación revierte pendientes y libera período (re-causable); anular pago de intereses restaura pendientes; anular abono restaura capital (fecha en período NO causado); anular movimiento de capital con fecha en período ya causado → 400 (guard espejo); anular desembolso con actividad posterior → 400; anular tipo de obligación vía `POST /money-movements/{id}/annul` de Tesorería → 422.

**Integraciones (7):** `test_reconciliation_residual_zero` actualizado con `interest_income` (⚠️ bloqueante); P&L parity gasto (drill-down por categoría lo incluye); cash flow buckets (6 tipos); balance histórico `as_of` con los 8 tipos (snapshot antes/después de un pago); `_classify_third_party` sin cambios — receivable → `investor_receivable`, payable → `investors_obligations` (assert de no-regresión de secciones); estado de cuenta unificado muestra los movimientos **con saldo corrido correcto** (mapas duplicados de money_movements.py); Dinero Inactivo: deudor con solo causaciones batch sigue apareciendo inactivo como tipo `investor` (accruals excluidos del activity map) y un recaudo real SÍ resetea el reloj.

**RBAC (2):** viewer con `view_obligations` accede a lista, sin manage → 403 en crear/causar.

## 10. Criterios de aceptación

1. El ejemplo del cliente reproduce exacto: $20M al 2%, abono de $10M el día 16 → causación de $300.000 con desglose "200.000 + 100.000" visible.
2. Causar es idempotente y solo sobre meses vencidos; los contadores de la obligación cuadran SIEMPRE con el saldo del tercero (obligaciones creadas post-módulo).
3. El gasto financiero entra al P&L del mes causado (devengo) por su categoría; el ingreso financiero aparece como línea propia y la conciliación #59 sigue cerrando al peso.
4. Todos los reportes existentes (Cash Flow, balances incluido `as_of_date`, estado de cuenta) reflejan los movimientos nuevos sin números huérfanos.
5. Con el módulo desplegado y sin obligaciones creadas: cero cambio en cualquier reporte (los 8 tipos no existen en datos).
6. RBAC: sin `view_obligations` (ni master) el módulo es invisible; sin `manage` es solo-lectura.
7. Un deudor de préstamo que no paga aparece en "Dinero Inactivo" aunque el batch le cause intereses todos los meses — la causación automática NO cuenta como actividad del tercero.

## 11. Riesgos y notas

- **R1 — El mayor riesgo es de integración, no de lógica**: 8 tipos nuevos tocan TODOS los mapas type→efecto del sistema. La buena noticia v2: #67 ya recorrió este camino con 4 tipos y dejó los **6 sitios enumerados** (fila "Mapas tipo→signo" de §7) + el golden test #61 como guardrail. QA debería validar especialmente los **mapas duplicados de money_movements.py** (statement) — son los más fáciles de olvidar porque no viven en reports.py.
- **R2 — Terceros con historia manual**: el cliente ya registró intereses/abonos manuales sobre estos terceros. La obligación migrada arranca del saldo actual (= capital según el cliente) y el módulo opera hacia adelante; los movimientos manuales viejos siguen en el estado de cuenta del tercero (correcto). Documentar al cliente: desde el go-live del módulo, NO registrar más movimientos manuales sobre estos terceros.
- **R3 — Doble conteo P&L en transición**: si el cliente causa julio manualmente Y con el módulo, se duplica el gasto. Mitigación: `accrual_start_period` explícito al crear (default mes actual) + instrucción de corte al entregar.
- **R4 — `pending_interest` y P&L mensual (#50)**: la causación lleva `date` = último día del período causado (mediodía UTC, `BusinessDate`) para que el P&L mensual la ubique en el mes correcto aunque el batch se corra días después.
- **R5 — Conexión con requerimiento C**: los tipos nuevos nacen identificables como financieros → el mapeo a rubros del P&L (C) sale casi gratis. No implementar C aquí, solo no estorbarlo.
