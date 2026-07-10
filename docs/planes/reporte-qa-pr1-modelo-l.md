# Reporte para QA — PR-1: Núcleo Modelo L (COGS al liquidar)

**Fecha:** 2026-07-09 · **Estado:** implementado, SIN commitear (pendiente QA) · **Rama:** develop
**Plan aprobado por QA:** `docs/planes/plan-fix-estructural-costo-promedio.md` (Fase 1). Gaps G1-G5 del QA del plan quedaron incorporados al documento (G1/G2 → sección 4.1, G3/G4 → 4.4, G5 → 7). Este PR NO los toca — son de PR-2.

---

## 1. Qué implementa (y qué NO)

**Implementa la Fase 1 exacta del plan:** el COGS de la venta se finaliza en su LIQUIDACIÓN al promedio vigente en ese momento, actualizando `SaleLine.unit_cost` y el `InventoryMovement.unit_cost` espejo. El `unit_cost` capturado al registrar pasa a ser provisional (utilidad estimada).

**NO implementa** (PR-2): helper de oversell, columnas nuevas, línea P&L, MCH `sale_cancellation`, warnings al cancelar compra. **Sin migración.**

⚠️ **G5 vigente: este PR NO se deploya sin PR-2** (restricción dura del plan, sección 7).

## 2. El cambio (un solo archivo de producción)

[backend/app/services/sale.py](../../backend/app/services/sale.py) — 2 ediciones:

1. **Import**: `from collections import defaultdict, deque`.
2. **`liquidate()`, Step 5b nuevo** (antes del move transit→liquidated, que pasa a ser Step 5c): pre-carga los `InventoryMovement` de la venta (`reference_type="sale"`, `movement_type="sale"`) y los agrupa en colas por firma `(material_id, quantity)`. Luego, por línea:
   - `final_cost = material.current_average_cost`, con fallback `_get_last_known_cost` si es 0 (mismo criterio que create).
   - `line.unit_cost = final_cost` y `inv_movement.unit_cost = final_cost` (matching `(material_id, -line.quantity)` — el movimiento nace con cantidad negativa).
   - El move de stock (transit/liquidated) queda igual.

**No se crea MaterialCostHistory**: extraer al promedio no cambia el promedio (invariante del ponderado). El avg del material queda intacto — solo cambia qué costo se lleva la venta.

**Decisiones de diseño dentro del cambio:**
- **Firma sin bodega:** la venta es mono-bodega (`sale.warehouse_id`) — verificado por QA en el plan. Si dos líneas comparten `(material, qty)` son intercambiables (mismo costo final).
- **Patrón deque desde el día 1** (lección QW-B): venta multi-línea del mismo material no puede repetir el bug de `.first()`.
- **DP intocable por construcción:** `sale.liquidate` rechaza DPs con 400 ([sale.py:316-320](../../backend/app/services/sale.py#L316-L320)); la liquidación DP es servicio propio con COGS = precio de cruce. Cero cambios ahí.

## 3. Tests nuevos — `tests/test_avg_cost_model_l.py` (6 tests)

Escenario canónico del plan (pool 1.000 @ 9.000; compra 500 @ 8.000 registrada; venta 800 registrada; valor total 13.000.000):

- **T1a/T1b (oro — conservación en ambos órdenes):** liquidar venta→compra da COGS 7.200.000 y pool 700 @ 8.285,71; compra→venta da COGS 6.933.333 y pool 700 @ 8.666,67. En AMBOS: `COGS + liquidated×avg == 13.000.000 ± $1`. La order-dependence del COGS es la aceptada por Daniel; la conservación es el invariante.
- **T2 (COGS finaliza al liquidar):** provisional 9.000 al registrar → compra mueve avg a 8.666,67 → liquidar venta → `SaleLine.unit_cost == 8.666,67` **y** el `InventoryMovement` actualizado **y** el avg del material NO cambió por liquidar la venta.
- **T3 (auto_liquidate neutro):** 1-paso → unit_cost == avg del momento (idéntico a hoy).
- **T4 (material nuevo, avg 0):** venta antes de toda compra (provisional $0) → compra 200 @ 7.000 liquidada → liquidar venta → COGS 7.000, no $0. El caso "utilidad ficticia" ($14,3M revenue en Costa) muere hacia adelante.
- **T5 (paridad P&L):** `cost_of_goods_sold` del endpoint == Σ(unit_cost final × qty) ± $1.

## 4. Verificación

- `py_compile` de sale.py: **OK**.
- `tests/test_avg_cost_model_l.py`: **6/6 verdes**.
- Regresión `test_api_sales.py` + `test_api_purchases.py` + `test_pnl_drilldown_parity.py`: **146 passed, 1 failed** — el failed es exactamente el pre-existente `test_update_insufficient_stock_fails` (#54, ajeno). Los **16 tests de oro de paridad drill-down (#49) pasan intactos**.
- Suite completa: **958 passed, 6 failed en 14:00** — los 6 failed son EXACTAMENTE los pre-existentes conocidos (5×405 organizations/auth_with_org + `test_update_insufficient_stock_fails`, nota decisión #54). **Cero regresión.**
- Nota ambiental: dos corridas anteriores dieron errores masivos `relation "users" does not exist` por pytest CONCURRENTE de la sesión QA contra la misma BD 5433 (el conftest dropea el schema). No es defecto de código. Coordinar: un solo pytest a la vez.

## 5. Puntos para mirar con lupa (auto-señalados)

1. **El orden Step 5b vs Step 6 (saldo cliente):** el recálculo de COGS ocurre ANTES de actualizar el saldo del cliente y pagar comisiones — ninguno de esos pasos lee `unit_cost`, no hay dependencia. Verificar que no se me escape un lector intermedio.
2. **`db.query(...).all()` vs líneas:** si una venta tuviera un movimiento huérfano (movement sin línea correspondiente), queda sin actualizar (queue no consumida) — inofensivo; y una línea sin movimiento (DP nunca llega aquí; ventas normales siempre lo crean en create) deja `inv_movement=None` y no explota.
3. **Ventas ya liquidadas ANTES del deploy:** conservan su COGS histórico (congelado al registro). La remediación es Fase 4, gated. Hasta entonces conviven ambos criterios en los datos históricos — igual que el plan lo documenta.
4. **Utilidad "estimada" en ventas registered:** el detalle de una venta registrada muestra utilidad con el provisional; al liquidar puede cambiar. UI-rotulado es pregunta abierta del plan (sección 11), no bloquea.
5. **`expire_all()` en tests:** el `unit_cost` se muta vía la sesión del request; los asserts refrescan (`db_session.expire_all()`/`refresh`) antes de leer — si QA ve un assert leyendo stale, es del test, no del fix.
6. **Precisión de columna (hallazgo durante los tests, PRE-existente):** `SaleLine.unit_cost` e `InventoryMovement.unit_cost` son `Numeric(15,2)`; `current_average_cost` es `Numeric(15,4)`. El COGS persistido arrastra hasta $0.005/kg de redondeo (con avg 8.666,6667 se guarda 8.666,67 → $2,67 en 800 kg). El flujo ACTUAL pierde exactamente la misma precisión al registrar — el fix no lo introduce ni lo empeora. Los tests lo documentan (tolerancia $1 + $0.005×kg en el helper de conservación, comparaciones `quantize(0.01)`). Si algún día molesta: ampliar columnas a 4 decimales = migración aparte, fuera de alcance.

## 6. Pendiente al cerrar (tras QA)

- Documentar como **decisión #64** en CLAUDE.md (el código ya la referencia por ese número).
- Actualizar memoria `bug_costo_promedio_movil` (PR-1 commiteado + hash).
- PR-2 (Fase 2) es el siguiente — con G1/G2 fijados en el plan.
