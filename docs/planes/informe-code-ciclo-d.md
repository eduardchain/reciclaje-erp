# Informe post-código — SAC Ciclo D: recolector + comisión como GASTO

**Fecha**: 2026-07-17/18 · **Base**: develop `8133b56` (post Ciclo C #82) · **Plan**: `plan-sac-ciclo-d-recolector-gasto.md` v1.2 (micro-QA 🟢 GO condicionado: D-01 mayor, D-02 menor, D-03 sugerencia; + corrección de pruebas Daniel)

---

## 0. Resumen

La decisión de producto de Daniel implementada tal cual: el recolector (Green Loop) se captura **opcional en la entrada — AMBOS tipos** (David, en el patio) y su comisión se causa al liquidar la compra como **GASTO** (`expense_accrual`, categoría sistema "Comisiones de recolección", INDIRECTA) — **jamás al costo del material** (#30 intacto para fletes/comisiones prorrateadas). **1 migración aditiva** (`inbound_orders.collector_id`, tabla SAC-only), **cero tipos MM nuevos** (catálogo sigue en 39), **cero permisos nuevos**, param de liquidación **data-gated calcado de retenciones D9**.

**Corrección de pruebas Daniel (2026-07-18)**: "Green Loop puede recolectar también willard pero no se le paga comisión por ello." La v1.1 sobre-restringía: bloqueaba el CAMPO en willard (422). Corregido en el mismo ciclo: el recolector se **REGISTRA en willard como informativo** (quién recolectó, editable siempre) y la comisión existe SOLO en compras regulares **por construcción** — willard no tiene liquidación de compra y el único punto que causa el gasto es `purchase.liquidate()`. Test dedicado: confirmar una willard con recolector → **cero MMs `collector_commission`, cero categoría creada, saldo de Green Loop intacto en $0**.

## 1. Condiciones del GO — cómo aterrizaron

### D-01 (MAYOR) — ruta (a): el embudo `_create_movement` ganó los 4 kwargs

`money_movement.py::_create_movement` ganó `source_type / source_id / tariff_id / warehouse_id`, todos `Optional=None`, pasados directo al constructor de `MoneyMovement` (las 4 columnas E2 que estaban sin uso — este ciclo las estrena).

**Argumento de no-regresión del embudo compartido (~23 call sites, 3 orgs prod):**
- Ningún call site existente pasa los kwargs nuevos → siguen produciendo `NULL` en las 4 columnas, **exactamente el mismo INSERT que hoy** (kwargs default None → mismos valores que el default del modelo).
- Es una extensión de firma pura: cero cambios de lógica dentro del embudo (el guard de UN sistema y la numeración quedan intactos).
- Evidencia: **test 7 del plan** (`test_byte_identical_without_param`) liquida sin el param y verifica cero MMs nuevos + efectos idénticos (avg = precio, saldo proveedor = −total); la suite completa cubre los 23 call sites vivos (pagos inmediatos, DPs, obligaciones, activos, distribuciones — todos pasan por el embudo).
- **Por qué (a) y no (b) post-hoc**: E3-E5 traerán más movimientos SAC con firma (las columnas nacieron en E2 para eso) — un solo camino de escritura, sin pokes por fuera del embudo.

### D-02 (MENOR) — filtro `source_type` en el auto-annul ✅

El Step 6d de `cancel()` filtra `movement_type='expense_accrual' AND purchase_id=X AND source_type='collector_commission' AND status='confirmed'`. Test dedicado `test_cancel_does_not_touch_manual_expense_accrual`: un accrual MANUAL (source_type NULL) etiquetado a la compra **sobrevive** la cancelación; el de recolector cae.

### D-03 (SUGERENCIA, aplicada) — un solo normalizador ✅

`_get_or_create_collector_category` importa `normalize_entity_name` de `retention_entities.py` (NFKD existente). Test H4: una categoría pre-existente `"comisiones de recoleccion"` (sin acento, minúsculas, `is_system_entity=True`) se **reusa** — cero duplicados tras 2 liquidaciones.

## 2. Qué se construyó

**Backend:**
- **Migración `f6a7b8c9d0e1`**: `inbound_orders.collector_id` GUID nullable FK `third_parties` ON DELETE SET NULL (única columna nueva; `money_movements` no se toca — usa las columnas E2). Aplicada en dev 5434; 5433 se recrea por conftest.
- **Entrada**: `collector_id` en Create/Update/Response (+`collector_name` vía joinedload, cero N+1) — **ambos tipos** (willard: informativo, corrección 2026-07-18). Guards en servicio: `service_provider` (#32); tipo compra **editable solo mientras la derivada esté `registered`** (después → 422: la comisión ya se definió); willard editable siempre (sin efectos).
- **Liquidación**: `PurchaseLiquidateRequest.collector_commission {third_party_id, amount>0}` — data-gated D9 (ausente = byte a byte; presente sin flag → 422). Step 8d en `liquidate()`: crea el `expense_accrual` (cuenta NULL, categoría sistema, saldo recolector −monto, descripción "Comisión recolección compra #N — Entrada #M") con la firma D-01 completa: `source_type='collector_commission'`, `source_id`=entrada, `tariff_id`=vigente `comision_green_loop` (snapshot informativo — el monto editado es la verdad, F1 #79), `warehouse_id`=header D11. **Fecha = `liquidation_date or purchase.date` (el PARÁMETRO — W-D5, trampa #61 esquivada por construcción)**. El backend NO exige `third_party == entrada.collector` (la liquidación confirma, como los precios).
- **Cancelación**: Step 6d auto-anula el accrual (patrón #23, sin elección #63 — no hay caja), solo `confirmed` → anulado a mano antes = no-op sin doble reversa. Anulación directa en Tesorería permitida (= condonar sin cancelar).
- **Categoría sistema**: get-or-create #78 con `is_system_entity=True` (columna E2 estrenada también en `expense_categories`), `is_direct_expense=False` (decisión Daniel: NO entra al Costo Real), `pnl_section` default operativo. Reclasificable en Config (retroactivo al leer). Limitación aceptada idéntica a retenciones: renombrar → nueva al próximo uso.
- **Enrich B1 extendido**: `_inbound_origin_map` ahora también trae `collector_id/collector_name` (mismo lookup por página + outerjoin, cero queries extra) → `PurchaseResponse` los expone para la pre-carga.

**Frontend:**
- **InboundCreatePage**: selector "Recolector" (EntitySelect de payable-providers, ya cargados) en **ambos tipos**; hint por tipo (willard: "solo registro — la recolección Willard no genera comisión"; compra: "la comisión se define al liquidar (va a gastos, no al costo)").
- **InboundEditPage**: mismo campo; tipo compra **deshabilitado con hint cuando la compra ya no está registered**; willard editable siempre; null explícito lo quita.
- **InboundDetailPage**: fila "Recolector".
- **PurchaseLiquidatePage** (superficie compartida — cambios 100% flag-gated): card "Comisión de Recolección" entre Comisiones y Retenciones, solo con `kg_ledger_enabled`. Pre-carga si la compra viene de entrada con recolector ("Capturado en la entrada"); "+Agregar" manual; monto sugerido = **tarifa vigente `comision_green_loop` × kg totales** (cantidad ORIGINAL, asimetría #70) vía `useCurrentTariffs(enabled)` — hook extendido con `enabled` (F2: cero requests en orgs prod); editable con "Sugerido: $X — restaurar" (#10); "Quitar" = condonada; panel índigo explica que va a gastos y no al pago del proveedor. **El Resumen Financiero no se toca** (la comisión no altera total/neto del proveedor).
- Types: `CollectorCommissionIn`, campos en purchase/inbound. Invalidaciones ya cubiertas (C dejó `["inbound-orders"]` en el mapa de liquidación).

## 2b. Addendum pruebas Daniel (2026-07-19) — 2 hallazgos corregidos en el ciclo

1. **El detalle no mostraba el costo de recolección**: nuevo `collector_commission_total` (patrón `linked_payment_total` #63: **solo en GET de detalle**, cero N+1 en listados) — suma de accruals `confirmed` con firma `collector_commission`; None si no hay o fue anulada (condonada se oculta). Expuesto en el detalle de la **compra** (card "Comisión de Recolección": recolector + monto + nota "no hace parte del costo ni del total al proveedor", gated `view_prices`) y en la **cara financiera de la entrada** (fila "Comisión Recolección (gasto)"). Servicio: `get_collector_commission_total` espejo de `get_linked_payment_total`.
2. **Selector "raro" en la liquidación**: el placeholder del EntitySelect decía `"Green Loop..."` — cuando la pre-carga no disparaba, el placeholder PARECÍA una selección hecha y Johana tenía que re-clickear la opción. Doble fix: (a) placeholder neutro "Seleccionar recolector..." (regla: JAMÁS un nombre de entidad como placeholder); (b) **pre-carga robusta** — efecto propio que reacciona cuando `purchase.collector_id` LLEGA (el init vivía dentro del effect de líneas y se perdía si la compra venía de un cache con shape pre-D); "Quitar" marca `collectorDismissed` para que el refetch no re-abra la fila.

## 2c. Addendum pruebas Daniel ronda 2 (2026-07-19) — falso "bug de costo" + Kg Plomo en Stock

1. **"¿Por qué una recepción willard sin costo cambia el promedio?" (foto BAT-08) — NO había bug de costo, era un bug de DISPLAY**. Forense contra el libro (`material_cost_histories`): las 4 recepciones willard de BAT-08 entraron a **identidad exacta** (avg 1453,1250 → 1453,1250; 1670,6330 → 1670,6330 — cero cambio, D2 se cumple al peso); lo que movió el promedio fue la **liquidación de la compra #10** (123 und @ $4.500: 1453 → 1670,63). La columna "Costo Prom." del historial usaba una **reconstrucción ingenua** (promedio corrido con heurística `cost==0` para tránsito) que no sabía de Modelo L (#64-#66) y las capturas SAC con precio la rompían — pintaba $1.776/$1.849, números que **nunca existieron**. Fix en `inventory_views.list_movements`: la columna ahora **lee del libro real** (MCH, append-only) con lookup de 2 niveles: (1) **por FUENTE** — mapa `movement_type → mch.source_type` (`purchase→purchase_liquidation`, `inbound_receipt→inbound_receipt`, y las 3 reversas): el efecto de liquidar una compra aparece EN la fila de la compra aunque la liquidación ocurra días después; (2) **por TIEMPO** — `bisect` sobre `created_at` (extracciones MCH-silenciosas como ventas muestran el promedio vigente sin cambio; empates de misma transacción entran porque PG congela `now()` por transacción). Sin historial → `None` (la UI pinta "—" en vez de inventar). `balance_after` intacto (suma exacta). Verificado live contra BAT-08: las 6 filas coinciden con el libro. Limitación conocida (display-only): una operación con el MISMO material 2+ veces en sus líneas escribe N registros MCH con `created_at` idéntico — "última fila gana" puede mostrar el avg intermedio en vez del final (raro; el valor sigue siendo un avg real de esa operación).
2. **"¿No deberíamos ver el total en kg de plomo que representa el stock?"** — columna **"Kg Plomo"** + KPI **"Plomo en Stock"** + columna en el Excel de Stock (paridad #51), todo **client-side** con la fórmula VIGENTE (mismo `estimateKgLead` de la recepción: batería = und × kg/und; drosses = kg × %). Solo materiales con fórmula ("para los que aplique" — resto "—"); respeta los filtros activos (el KPI suma lo filtrado). F2 estricto: `useCurrentFormulas` ganó param `enabled` — gated por flag, **cero requests en orgs prod**, columna/KPI invisibles sin flag (`showKgLead = flag && formulas.length > 0`). `KpiCard` ganó accent `indigo` (paleta SAC #67). Verificado con datos dev: BAT-08 2.923 und × 8,5 = 24.845,50 kg; DRO-W 600 × 5% = 30 kg; chatarra sin fórmula "—"; KPI 25.675,50 kg.

## 3. Tests — 18 nuevos (`test_sac_ciclo_d.py`, 3 clases)

- **TestCollectorCapture (5)**: response en entrada/detail/compra (B1) · **willard registra recolector y confirmar NO causa nada** (cero MMs `collector_commission`, cero categoría, saldo $0 — la corrección) · willard editable siempre (incluso confirmada) · no-service_provider 422 · lifecycle tipo compra (agregar/cambiar/quitar en registered ✓, tras liquidar 422).
- **TestCollectorCommissionEffects (10)**: **estrella W-D2** (avg == 900.0000 exacto con comisión $50K — el prorrateo #30 habría dado 1400; MM con firma D-01 completa verificada campo a campo; categoría indirecta+sistema; saldo −$50K) · P&L (`operating_expenses` + breakdown categoría/source/pnl_section) y Reporte de Gastos #44 · estado de cuenta + balance detallado (`service_provider_payable`) · get-or-create idempotente H4 · condonada (entrada con recolector, liquidada sin comisión → cero MMs, cero categoría) · sin flag 422 · **byte a byte sin param (guard W-D1)** · amount ≤0 422 · liquidate con no-service_provider 422 · **detalle expone `collector_commission_total`** (compra Y entrada; None pre-liquidación y post-cancel — addendum).
- **TestCollectorCancelRoundtrip (3)**: cancel → accrual anulado + saldo round-trip a $0 · anulado a mano primero → cancel no-op (razón original conservada, saldo NO doble-revertido) · **D-02**: accrual manual sobrevive.

**Addendum ronda 2 (+2)**: `TestMovementAvgDisplayWillard` (ciclo D) — semilla avg 500 por ajuste, willard confirmada muestra **500 → 500** en su fila (identidad D2 VISIBLE) y el avg vivo coincide · `test_avg_cost_after_reads_from_cost_history` (`test_api_inventory_views.py`) — compra registrada → `None`; liquidada → avg EN su fila (nivel fuente); venta MCH-silenciosa → promedio intacto; 2ª compra registrada muestra el vigente (donde la fórmula ingenua mentía) y al liquidar → 1700 exacto sin reescribir filas previas.

**Vecinos**: 271 verdes (inbound + ciclo_b + ciclo_c + api_purchases + api_money_movements — cubren el embudo D-01 y el cancel extendido). Ronda 2: 66 verdes (inventory_views + ciclo_d + inbound).

## 4. Gates

| Gate | Resultado |
|---|---|
| Ciclo D targeted (17 tests, incl. corrección willard) | ✅ verdes |
| Vecinos (271 pre-corrección; 101 re-run post-corrección: ciclo_d+inbound+ciclo_b+ciclo_c) | ✅ verdes |
| Suite completa | ✅ **1342 passed** en 29:41 (1325 + 17) — post-corrección |
| Parity check | ✅ DIFF CERO fuera del baseline (56 tablas / 247 índices / **268** constraints — el +1 vs C es el FK de `collector_id`, presente en AMBOS lados) |
| tsc / build | ✅ limpio / ✅ 4.0s (post-corrección) |
| Migración dev 5434 | ✅ aplicada (`f6a7b8c9d0e1`) |
| Smoke live dev | ✅ OpenAPI expone los 6 puntos nuevos · SAC: listado con campos nuevos (null en entradas existentes) · **Costa (réplica prod, sin flag): inbound 403 / purchases 200 (W-C3 intacto) y liquidar #2170 con `collector_commission` → 422 "módulo no habilitado" con rollback limpio (la compra siguió registered)** |
| Golden | Sin cambios de comportamiento en tablas compartidas (embudo D-01 = extensión de firma pura; `PurchaseLiquidateRequest` data-gated D9) |
| **Ronda 2** — targeted (2) + vecinos (66) | ✅ verdes |
| **Ronda 2** — avg display live vs BAT-08 | ✅ las 6 filas == libro MCH (willard idénticas 1453→1453, 1670→1670; compra #10 muestra 1670,63 en SU fila; reversa de compra #9 1483,33) |
| **Ronda 2** — Kg Plomo con datos dev SAC | ✅ BAT-08 24.845,50 · BAT-PC 800 · DRO-W 30 · chatarra "—" · KPI 25.675,50 kg |
| **Ronda 2** — tsc / build | ✅ limpio / ✅ 4.2s |
| **Ronda 2** — suite completa | ✅ **1345 passed** (1343 + 2) |

## 5. Walkthrough para pruebas de Daniel

1. **Entrada nueva**: campo "Recolector" en ambos tipos — elige Green Loop. En willard el hint aclara "solo registro — no genera comisión"; puedes verificar que confirmarla NO le crea saldo a Green Loop.
2. **Liquidar** esa entrada: la sección "Comisión de Recolección" llega pre-cargada con el monto sugerido (tarifa × kg). Edítalo o déjalo; "Quitar" = no se cobra.
3. Al liquidar: el **costo del material NO cambia** (compara con una compra igual sin comisión). El gasto aparece en **P&L → Gastos Operativos → "Comisiones de recolección"** y en el Reporte de Gastos.
4. **Green Loop** queda con saldo a favor (estado de cuenta muestra "Comisión recolección compra #N — Entrada #M"). Se le paga desde Tesorería como cualquier proveedor de servicios.
5. **Cancelar la compra**: la comisión se anula sola y el saldo vuelve. Anularla directo en Tesorería (sin cancelar la compra) = condonarla.
6. En la entrada: el recolector se puede cambiar/quitar mientras esté Registrada; tras liquidar queda congelado.
7. **(Ronda 2) Historial de movimientos de BAT-08**: la columna "Costo Prom." ahora muestra el promedio REAL — las recepciones willard repiten el promedio anterior (no lo mueven), y la fila de una compra muestra el promedio que ESA liquidación dejó. Filas sin historial de costo muestran "—".
8. **(Ronda 2) Tab Stock**: columna "Kg Plomo" (materiales con fórmula) + KPI "Plomo en Stock" que suma lo filtrado + columna en el Excel. Sin flag (Costa) nada de esto aparece.

## 6. Fuera de alcance (→ D.2, plan §7)

Backlog §7 de C (duplicar, recientes, siguiente-registrada, aviso doble captura, KPIs, toast kg, foto evidencia) · multi-recolector con tarifa por tercero (el modelo ya acepta CUALQUIER service_provider — solo la sugerencia de monto es Green Loop-céntrica) · comisión de recolector en ventas/DPs.
