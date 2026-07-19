# Plan SAC Ciclo D — Recolector en la entrada + comisión como GASTO (no prorrateo)

**Versión**: v1.2 (v1.1 + corrección de pruebas Daniel 2026-07-18: recolector registrable en willard, sin comisión) · **Fecha**: 2026-07-17 · **Base**: develop `8133b56` (post Ciclo C #82)

**Corrección (pruebas Daniel 2026-07-18)**: "Green Loop puede recolectar también willard pero no se le paga comisión por ello" — la v1.1 bloqueaba el CAMPO en willard (422); lo correcto es **registrarlo en AMBOS tipos** (en willard es informativo: quién recolectó) y que la comisión exista SOLO al liquidar compras regulares — garantizado **por construcción**: willard no tiene liquidación de compra y el único punto que causa el gasto es `purchase.liquidate()`. En willard el recolector es editable siempre (sin efectos); el candado post-liquidación aplica solo a tipo compra.

**Resolución de condiciones QA**:
- **D-01 (MAYOR)** — ruta (a): `_create_movement` (embudo compartido, ~23 call sites) se extiende con 4 kwargs opcionales `source_type=None, source_id=None, tariff_id=None, warehouse_id=None` que pasan directo al constructor. No-regresión: ningún call site existente los pasa → columnas NULL exactamente como hoy (byte-idéntico prod); test 7 (data-gate) + suite completa son el guard. Se elige (a) sobre el post-hoc (b) porque E3-E5 reusarán el embudo para más movimientos SAC con firma (las columnas nacieron en E2 para esto) — un solo camino de escritura, sin pokes por fuera.
- **D-02 (MENOR)**: el filtro del auto-annul en `cancel()` suma `source_type='collector_commission'` (defensa en profundidad — jamás anular un `expense_accrual` manual que un usuario haya asociado a la compra).
- **D-03 (SUGERENCIA, aceptada)**: el helper de categoría reusa `normalize_entity_name` (`services/retention_entities.py`) — un solo normalizador NFKD en el repo.
**Decisión de producto (Daniel)**: "la comisión de Green Loop NO se prorratea al costo del material, se carga como un gasto, SOLO en caso de que la compra sea regular." Resuelve la pregunta abierta de la memoria `sac-ruta-generalizar-recolector-comision` y es coherente con Q-02 de Johana (Green Loop recolecta postconsumo willard pero NO cobra comisión por eso).

**Decisiones de alcance (Daniel, 2026-07-17, AskUserQuestion)**:
1. Ciclo D = **solo recolector** (backlog §7 de C queda para D.2 post-deploy).
2. El gasto es **operativo general** — categoría INDIRECTA (`is_direct_expense=False`): NO entra al Costo Real por material. Cambiable en Config después si Hugo lo pide (retroactivo al leer, #4).
3. Categoría **fija del sistema**: "Comisiones de recolección", get-or-create al primer uso (patrón entidades de retención #75/#78). Johana no elige categoría.

---

## 1. Modelo conceptual

- **Quién asigna**: David (o quien capture) marca el **recolector** en la entrada, en el patio — **ambos tipos** (corrección 2026-07-18; en willard es solo registro de quién recolectó). Campo opcional.
- **Quién confirma y cuánto**: Johana, al **liquidar** la compra derivada. La comisión llega pre-cargada (tarifa vigente `comision_green_loop` × kg), **editable** y **removible** — el monto editado es la fuente de verdad, sin recomputo server-side (patrón retenciones F1 #79). Quitar la fila = no se causa nada (condonada / no aplica).
- **Efecto financiero** (al liquidar, fechado en `liquidated_at` #61):
  `MoneyMovement(movement_type='expense_accrual', account_id=NULL, third_party=recolector, expense_category=«Comisiones de recolección», amount, purchase_id=compra, source_type='collector_commission', source_id=entrada, tariff_id=snapshot vigente, warehouse_id=sede)`.
  - Saldo del recolector baja (pasivo — le debemos), clasifica en `service_provider_payable` (#32/#38).
  - P&L: entra SOLO a Gastos Operativos por categoría — `expense_accrual` ya está en `EXPENSE_MOVEMENT_TYPES` → **CERO cambios al P&L, Reporte de Gastos #44, drill-down #49, conciliación #59/#65/#69, rubros #71**. Todo por construcción.
  - Pago posterior: `payment_to_supplier` de siempre (acepta `service_provider`). Estado de cuenta del recolector muestra el evento (es un MM normal).
- **Lo que NO pasa**: el costo promedio del material NO se toca. NO es `PurchaseCommission` (#30 queda intacta para fletes/comisiones prorrateadas). NO es `commission_accrual` (#23 — aterrizaría en la línea "Comisiones (Ventas)" del P&L, etiqueta incorrecta; Daniel dijo "gasto").

### Por qué `expense_accrual` y no un tipo MM nuevo
El catálogo pasa de 39 tipos… a 39. `expense_accrual` (#14) ya tiene exactamente la mecánica pedida: causar gasto sin mover dinero, con categoría, P&L por categoría, pago vía proveedor, anulable. La terna de signos, los 6 sitios de mapas (#67) y la conciliación quedan intactos sin tocar una línea. La distinción "es de recolector" vive en `source_type='collector_commission'` (columna E2 sin uso, con índice `(source_type, source_id)` ya creado).

---

## 2. Migración (1, aditiva)

`inbound_orders.collector_id` — GUID nullable, FK `third_parties.id` (ON DELETE SET NULL). Espejada en el modelo. Tabla SAC-only (flag-gated en router) → cero exposición prod; golden inalterado (la tabla no existe en el path de las 3 orgs prod… existe pero vacía y sin lecturas). Correr en 5434; 5433 se recrea por conftest (no-op). Parity check post.

**Cero columnas nuevas en money_movements** — `purchase_id`/`tariff_id`/`warehouse_id`/`source_type`/`source_id` existen desde E2 (migración B) sin uso. Este ciclo las estrena.

## 3. Backend

### 3a. Entrada (`inbound_order.py`)
- `InboundOrderCreate/Update` ganan `collector_id: UUID | None`.
- Validación en servicio (create y update): el tercero existe en la org y tiene behavior `service_provider` (#32, copy "recolector") → si no, 422. **[CORREGIDO 2026-07-18]** El campo aplica a AMBOS tipos — en willard es informativo (la comisión no puede nacer ahí por construcción).
- **Tipo compra: editable solo mientras la derivada esté `registered`** (display_status Registrada): tras liquidar, la comisión ya se causó — cambiar el recolector sería cosmético/engañoso → 422 con mensaje guía. **Willard: editable siempre** (sin efectos). (La cabecera conductor/vehículo/notas sigue editable como hoy.)
- `InboundOrderResponse` gana `collector_id` + `collector_name` (join barato en `_page_context`, cero N+1).

### 3b. Liquidación (`purchase.py`)
- `PurchaseLiquidateRequest` gana `collector_commission: CollectorCommissionIn | None = None` con `{third_party_id: UUID, amount: Decimal > 0}`.
  **Data-gated calcado de retenciones D9 (#75)**: ausente → camino actual **byte a byte** (las 3 orgs prod jamás lo envían); presente sin flag `kg_ledger_enabled` → 422. Validación: tercero `service_provider` de la org; amount > 0 (Numeric money 2 decimales).
  - El backend NO exige que `third_party_id == entrada.collector_id`: la liquidación es el paso que confirma (misma filosofía que precios #64); si Johana corrige el recolector ahí, la verdad es el MM. La entrada conserva lo capturado.
  - `collector_commission` presente en compra SIN entrada enlazada → se acepta (mismo gate por flag; SAC va siempre por entradas — canal único B1 — pero no hay razón para bloquear el edge).
- En `liquidate()`, tras el bloque de retenciones: si `collector_commission` → crear el MM vía `mm_service._create_movement(...)` (composable #20, misma transacción), con los campos de §1. `date = liquidated_at` (usar el PARÁMETRO `liquidation_date or purchase.date` — trampa de orden #61). Descripción: `"Comisión recolección compra #{number}"` (+ `" — Entrada #{M}"` si hay orden enlazada).
- Categoría: helper module-owned `get_or_create_collector_category(db, org_id)` (patrón #78): busca por nombre normalizado H4 (sin acentos/casing) `comisiones de recoleccion` + `is_system_entity=True`; crea con `is_direct_expense=False`, `is_system_entity=True`, `pnl_section` default (operativo). Idempotente. Limitación aceptada (idéntica a entidades de retención): renombrarla en Config hace que el próximo uso cree una nueva.

### 3c. Cancelación (`purchase.cancel()`)
- Auto-anular el accrual enlazado: `movement_type='expense_accrual' AND purchase_id=X AND status='confirmed'` → `money_movement.annul()` (revierte el saldo del recolector). Patrón commission_accrual #23: **sin elección #63** (no hay cuenta de por medio — el accrual es espejo de la liquidación, se anula siempre). Solo `confirmed` → si Johana ya lo anuló a mano en Tesorería, no-op seguro (no doble reversa).
- **Anulación directa en Tesorería: PERMITIDA** (simétrico con `commission_accrual`; anular = corregir/condonar después de liquidar, sin cancelar la compra). NO entra a los sets bloqueados (`ASSET/OBLIGATION_MOVEMENT_TYPES`).

### 3d. RBAC y gating
- **CERO permisos nuevos**: capturar el recolector = `purchases.create/edit` (D13); causar la comisión = dentro de `purchases.liquidate`; ver/pagar/anular el MM = permisos de tesorería existentes.
- Flag: campo en tabla SAC-only + param data-gated. Orgs prod: byte a byte por construcción.

## 4. Frontend

- **InboundCreatePage / InboundEditPage** (ambos tipos): selector "Recolector" con EntitySelect de `payable-providers` (#32); hint por tipo (willard: "solo registro — no genera comisión"; compra: "la comisión se define al liquidar"). En edit tipo compra: deshabilitado con hint si la compra ya está liquidada.
- **Detalle de entrada**: fila "Recolector: X" si hay.
- **PurchaseLiquidatePage** (flag+data-gated, cero cambio sin flag): sección nueva "Comisión de recolección" — aparece si la compra viene de entrada con recolector (el enrich B1 de `PurchaseResponse` gana `collector_id`/`collector_name` del MISMO lookup por página, cero queries extra) o si Johana la agrega a mano ("+ Agregar comisión de recolección"). Pre-carga: monto = tarifa vigente `comision_green_loop` (hook `useSacConfig` existente) × Σ kg de líneas (cantidad ORIGINAL — asimetría de compras #70), editable con hint "Sugerido: $X" restaurable (#10), removible. Al enviar → `collector_commission` en el payload.
- **Tesorería**: nada nuevo — el MM es un `expense_accrual` normal (label existente). `MovementDetailPage` ya linkea compra.
- Invalidaciones: `invalidateAfterPurchaseLiquidateOrCancel` ya cubre (money-movements + third-parties + reports + inbound-orders desde C).

## 5. Tests (≥14)

1. **Estrella — no prorrateo**: liquidar con comisión de recolector → `avg_cost` del material IDÉNTICO al de liquidar sin ella; `InventoryMovement.unit_cost` sin ajuste; MM creado con account NULL + categoría sistema + saldo recolector −amount.
2. P&L: `operating_expenses` (y breakdown por categoría, source `expense_accrual`) incluye el monto; `test_reconciliation_residual_zero` sigue verde (por construcción).
3. Reporte de Gastos #44 lo incluye; balance detallado clasifica al recolector en `service_provider_payable`; estado de cuenta del recolector muestra el evento en `liquidated_at`.
4. Get-or-create idempotente: 2 liquidaciones → 1 categoría (match H4 con acentos).
5. Cancelar compra liquidada → accrual auto-anulado + saldo round-trip al origen; anulado a mano antes → cancel no-op sobre él (sin doble reversa).
6. Validaciones: willard registra recolector SIN comisión (confirmar → cero MMs, test dedicado) y edita siempre; tercero no `service_provider` → 422 (create entrada Y liquidate); `collector_commission` sin flag → 422 (org tipo Costa); amount ≤ 0 → 422; editar collector con compra liquidada → 422; editable en registered → 200.
7. Data-gate byte a byte: liquidar SIN el param → cero MMs nuevos, mismos efectos de siempre (guard de no-regresión).
8. Entrada con recolector liquidada SIN `collector_commission` → no se causa nada (condonada).
9. Response: entrada expone `collector_id/name`; purchase enriquecida expone collector del lookup B1.

## 6. Watch-points para QA

- **W-D1**: `PurchaseLiquidateRequest` es superficie compartida (las 3 orgs prod liquidan ahí) — el data-gate D9 es el precedente exacto ya QA-aprobado en E2; el test 7 es el guard.
- **W-D2**: la comisión JAMÁS entra al túnel de prorrateo #30 (`commissions[]` y `collector_commission` son params disjuntos; el loop de `adjusted_unit_cost` no la ve). Test 1 es el guard.
- **W-D3**: conciliación/rubros P&L intactos por construcción (tipo MM existente). Test 2.
- **W-D4**: auto-annul solo `confirmed` (no doble reversa). Test 5.
- **W-D5**: fecha del MM = `liquidated_at` con el PARÁMETRO, no `purchase.liquidated_at` (asignado después — trampa #61).

## 7. Fuera de alcance (D.2, post-deploy)

Backlog §7 de C (duplicar entrada, selectores recientes, siguiente-registrada, aviso doble captura, KPIs del día, toast kg, foto evidencia) · generalización multi-recolector con tarifa por tercero (la memoria `sac-ruta-generalizar-recolector-comision` sigue viva: hoy la tarifa sugerida es la única `comision_green_loop`; el modelo ya soporta CUALQUIER `service_provider` como recolector — solo la sugerencia de monto es Green Loop-céntrica) · comisión de recolector en ventas/DPs (no existe el caso).
