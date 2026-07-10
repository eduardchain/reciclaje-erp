# Reporte para QA — PR-5: remoción ponderada en reversiones (Fase 5)

**Fecha:** 2026-07-10 · **Estado:** implementado, SIN commitear (pendiente QA) · **Rama:** develop
**Plan:** `docs/planes/plan-fase5-remocion-ponderada.md` (aprobado por ustedes con 3 clarificaciones — las 3 plegadas e implementadas). Self-contained sobre PR-2; sin acople G5.

## 1. Qué hace

Las reversiones (cancelar compra liquidada, anular ajuste, anular transformación) dejan de rebobinar el costo vía MCH y pasan a **remoción/reingreso ponderado** con conservación de valor por construcción. Consecuencias: `check_can_revert` y `revert_cost_change` **retirados** (nunca más "Cancele primero: …"), MCH **append-only puro**, decisión **#40 superseded**, y el gap de `bug_check_can_revert_falsos_permisos` cerrado.

## 2. El cambio (backend 8 archivos + 4 frontend + migración + tests)

- **`inventory_costing.py`**: helper espejo `remove_from_pool(liquidated, avg, qty, unit_cost) → (new_avg, adjustment)`. Ecuación exacta en 3 ramas: `pool_after == pool_before − qty×u + adj`. Rama 2/3 comparten `adj = q×(u−A)` con avg quedándose (D1 aprobada).
- **`purchase.cancel()`**: guard Step 2a eliminado; remoción ponderada per línea. **H1 implementado como pidieron**: el costo ajustado se lee del `InventoryMovement` vía deque-por-firma (mismo patrón QW-B de liquidate; fallback a `unit_price` solo para huérfanos sin movimiento) + `line.cost_adjustment/qty`. Cosmético adoptado: el reversal movement lleva el costo ajustado. `purchases.cancellation_cost_adjustment` persiste la diferencia.
- **`inventory_adjustment.annul()`**: guard eliminado. `qty > 0` → remoción a `unit_cost + cost_adjustment/qty`; `qty < 0` → **reingreso ponderado a `adjustment.unit_cost`** (el avg de la salida — cierra el gap del primo hermano); `qty == 0` (recount sin delta) → no-op. `annul_cost_adjustment` persiste.
- **`transformation.annul()`**: ambos guards eliminados. Fuente: reingreso ponderado a `source_unit_cost`. Destinos: remoción per línea a `line.unit_cost + line.cost_adjustment/qty`. `material_transformations.annul_cost_adjustment` (header, suma).
- **`material_cost_history.py`**: `check_can_revert` + `revert_cost_change` eliminados (cero callers, verificado por grep); docstrings reescritos a doctrina append-only. `get_history_record` queda (utilitario read-only).
- **`reports.py` P&L 3.8**: 3 SUMs nuevos al mismo `oversell_cost_adjustment` (compras cancelled por `cancelled_at`; ajustes/transformaciones annulled por `annulled_at`) — patrón espejo de `sales.cancellation_cost_adjustment`.
- **`reports.py` H2 (`_get_inventory_as_of`)**: filtro dual — camino principal excluye MCH de ops cancelled/annulled (predicado EXISTS por source_type→tabla; los tipos de reversión no matchean → pasan); Fallback 1 excluye solo los 3 tipos de reversión Fase 5 e **incluye** los MCH de ops canceladas (su `previous_cost` = avg pre-op, evidencia válida). Fallbacks 2/3 ya filtraban por status (#61), intactos.
- **Migración `4530b4e47938`** (ID **aleatorio** — lección PR-4): 3 columnas `server_default=0` (P&L histórico intacto al deploy) + comment MCH a 8 source_types. Aplicada dev 5434 + test 5433. Escrita a mano.
- **Frontend (solo label, D2)**: "Ajuste Costo por Sobreventa" → "Ajuste Costo por Sobreventa **y Reversiones**" en P&L periodo/mensual, conciliación Rentabilidad UN y 3 sitios de Excel. `tsc` verde. D3 (confirmación suave) → v2, no incluida.

## 3. Dos decisiones de diseño tomadas EN implementación (léanlas con lupa)

### 3.1 El MCH de reversión se escribe SIEMPRE (no solo si el avg cambió)

El plan decía "solo si avg cambió" (patrón `sale_cancellation`). Al construir el golden H2 encontré el hueco: si la reversión no cambia el avg (ej. remoción a hueco al mismo costo → adj 0), no habría registro nuevo Y el original queda oculto para el as-of (op cancelada) → **la cadena visible pierde el costo y `as-of(hoy) ≠ balance vivo`**. Fix: los 3 caminos de reversión registran incondicionalmente. `sale_cancellation` sigue condicional (su original nunca escribió MCH — no hay cadena que preservar; cambiarlo alteraría datos/tests de PR-2 sin necesidad). El golden `test_golden_three_cuts_and_live_parity` revienta sin esto.

### 3.2 Excepción en Fallback 1: `sale_cancellation` SÍ se incluye

Su racional de exclusión ("previous_cost contaminado por el original oculto") no aplica: la venta que revierte es MCH-silenciosa, no hay original oculto. Incluirlo preserva **byte a byte** el comportamiento actual para datos existentes (es el único tipo de reversión pre-Fase 5 en prod). Los 3 tipos nuevos sí se excluyen. Plan actualizado (§5).

## 4. Cambios de semántica en tests EXISTENTES (aprobados por ustedes en PRs previos — cada uno justificado)

| Test | Antes | Ahora | Por qué |
|---|---|---|---|
| `test_fill_hole_persists_adjustment_and_pnl` (PR-2 round-trip) | post-cancel: avg 10.000, P&L 0 | avg 8.000, `cancellation_cost_adjustment` +400K, P&L junio 0 + rango amplio +400K | El rewind "devolvía" un hueco a 10.000 descontando de un pool ya mezclado; la remoción deja el hueco al avg vigente y el P&L se **redistribuye entre fechas** — verificado a mano que cuando el hueco se rellene a costo X el total reconcilia a `200×(10.000−X)`, como si la compra nunca hubiera existido |
| `test_weighted_reentry_symmetric_with_pnl` (PR-2) | cancel compra anterior → 400 "Cancelacion de venta" | → 200, y recupera **exactamente** 1.000@9.000 | La demo más linda del PR: reingreso trajo 800×9.000, remoción saca 300×7.000 → ponderado da el estado original exacto donde el rewind habría corrompido |
| PR-4 annul round-trips (increase + transformación) | post-annul: avg vuelve, P&L 0 | avg queda al vigente, `annul_cost_adjustment` reconoce la diferencia, P&L mes original limpio + annul-adj por `annulled_at` | Misma redistribución G3 |
| `test_cancel_liquidated_reverts_average_cost` | avg → 0 tras cancelar única compra | avg queda 2.000 con stock 0 (remanente inocuo: próxima entrada resetea vía pool==0) | Pool value $0 en ambos casos |
| `test_cancel_blocked_by_subsequent_purchase` → renombrado `_weighted_removal` | 400 | 200 + avg 2.400 exacto (queda la compra 2) | El caso del 79% |
| `test_cost_history_deleted_on_reversal` → `_append_only_on_cancel` | MCH borrado (count 0) | liquidación sobrevive + registro de cancelación (1+1) | Append-only |
| `TestCancelBlockedByTransformationSameCost` (FE004) | 400 | 200 + 100@1.200 exacto | #40 superseded; la protección era contra el rewind, que ya no existe |
| `test_integration_12` Steps 5a/10/12a | 3 asserts de bloqueo 400 | eliminados (nota Fase 5); Step 5b (cancel limpio) pasa con números IDÉNTICOS | Rama 1 == rewind cuando nada pasó entre medias |
| `test_purchase_commissions::test_cancel_liquidated_..._reverts_commissions` | avg → 0 tras cancelar | stock 0, avg queda 50.50 (remanente inocuo; de paso verifica H1: 50.50 = precio + comisión, leído del movimiento) | Encontrado en la 1ª corrida full-suite (no estaba en mi subset) |
| `test_integration_01` PASO 4 | `avg_cost=0` tras cancelar | `avg_cost=50` (remanente, pool $0 igual) | Ídem |
| `test_integration_06` PASO 6 | annul de t3 esperando 400 (bloqueado por t4/t5 posteriores) | intento eliminado (nota Fase 5); el annul de t5 (limpio) se mantiene con números idénticos | Ídem — anular t3 de verdad cascadearía el estado del stress; el caso "annul con posteriores" ya está cubierto dedicado en model_l |

Los cancels/annuls "limpios" (inmediatos) dan resultados **idénticos** al rewind — `test_cancel_most_recent_allowed`, `test_annul_increase/decrease`, annul de transformaciones y Step 5b pasan **sin tocar**, que es la paridad de regresión que importa.

## 5. Tests nuevos (12) — archivo queda en 36

- `TestRemoveFromPool` (5 unit, sin BD): ecuación en 3 ramas + inverso exacto de incorporate + boundary vaciado exacto.
- `TestFase5WeightedRemoval` (5 e2e): **la secuencia de la fuga** (§1 del plan: increase→decrease→annul; antes se evaporaban $100K, ahora 50@12.000 y adj 0, con MCH del increase sobreviviendo); **H1 con comisión Y fill** (u_total = 9.100 leído del movimiento: adj 180.000 exacto — con el precio crudo daría 200.000, el test lo atraparía); cancel del 79% (compra anterior); **#40 superseded** (cancel tras transformation_out, con warning PR-3 presente); **annul de decrease ponderado** (reingresa a 10.000, no al 6.000 vigente — conservación manual al peso).
- `TestFase5AsOfH2` (2, directo contra `_get_inventory_as_of`): **golden 3 cortes** (antes vacío / entre: doctrina #41 stock −60 costo 0 / después: == vivo) y el **dedicado a Fallback 1 que exigieron**: material cuyo único MCH relevante es de op cancelada (decrease sin MCH fuerza el fallback) — asserta que toma el `previous_cost` del MCH oculto-en-principal (0, doctrina exacta) y NO el del increase posterior (contaminado); corte hoy == vivo.
- **Stress walk SIN restricciones**: los 3 `confirmed_increases.clear()` eliminados, cancels/annuls con assert estricto 200, I5 gana los términos `cancellation_cost_adjustment` (compras cancelled) y `annul_cost_adjustment` (ajustes annulled), sanidad nueva `p_cxl + aa >= 1`. Misma semilla 20260710 — **pasó a la primera**. Este era el guardrail estrella del plan: el walk que PR-4 tuvo que esquivar ahora corre libre.

## 6. Verificación

- `test_avg_cost_model_l.py`: **36 passed** (24 previos con semántica actualizada + 12 nuevos).
- Subset impactado (purchases + integration_12 + adjustments + transformations + reports + parity drill-down + P&L monthly + balance histórico): **280 passed, 1 failed** — el pre-existente exacto (#54 `test_update_insufficient_stock_fails`).
- Suite completa: **988 passed, 6 failed en 18:01** — los 6 son EXACTAMENTE los pre-existentes conocidos (5×405 en organizations/auth_with_org + `test_update_insufficient_stock_fails`, nota #54). Total sube de 982 a 994 (+12 de PR-5). La 1ª corrida full descubrió 3 tests legacy con semántica rewind fuera de mi subset (commissions + integration_01 + integration_06, tabla §4) — corregidos y re-verificados; la 2ª corrida quedó limpia.
- `tsc --noEmit` verde (frontend = 1 string en 4 archivos).
- Migración aplicada dev + test; **BD test 5433 queda libre y limpia** (un pytest a la vez).

## 7. Puntos con lupa (self-review honesto)

1. **H1 en compras** — lo que pidieron: fuente = `InventoryMovement` vía deque (cero recompute). Nota: movimientos legacy `unit_cost=0` (#1074/#1295, no remediados por decisión de negocio) se removerían "según libros" — la ecuación cierra igual; coherente con el descarte de la remediación.
2. **Fill adjustment dentro de u_total**: si el fill sale del P&L al cancelar (status), su valor debe salir del pool — sin esto, I5 global no cierra. El walk lo verificaría en segundos.
3. **G3 se extiende a reversiones**: el adjustment de una reversión aterriza por `cancelled_at`/`annulled_at` — puede caer en mes distinto al original (los tests lo assertan explícitamente con ventana junio vs amplia). Misma comunicación al cliente que el G3 original.
4. **`test_reconciliation_residual_zero`** verde en el subset (los 3 términos nuevos entran al mismo campo org-level — G4 se mantiene).
5. **Riesgo H2**: es la zona del incidente Costa. Además de los 2 golden nuevos, `test_balance_historico_fixes.py` completo pasó (34 tests en el subset). El filtro es no-op para datos existentes (con rewind, las ops canceladas no tienen MCH que filtrar) — el deploy NO re-presenta ningún corte actual.
6. **Retiro de fricción operativa**: cancelar ya nunca bloquea — la única protección contra cancels accidentales que se pierde es el 400 del guard (que era incorrecta como protección de valor). D3 (confirmación frontend con actividad posterior) quedó para v2, como acordaron.
7. `sale.cancel` intacto (ya era ponderado); su comment del rol bloqueante actualizado.

Al cerrar (tras QA): decisión #66 nueva en CLAUDE.md (es un cambio de semántica mayor, no cabe como línea de #65) + actualizar #40/#65 con nota superseded + memoria `bug_check_can_revert_falsos_permisos` → RESUELTO con hash + `bug_costo_promedio_movil`.
