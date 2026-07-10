# Reporte para QA — PR-2: Conservación de valor (helper oversell + cancel ponderado + línea P&L)

**Fecha:** 2026-07-10 · **Estado:** implementado, SIN commitear (pendiente QA) · **Rama:** develop
**Plan:** `docs/planes/plan-fix-estructural-costo-promedio.md` secciones 4 y 4.4 (Fases 2a+2b). Gaps del QA del plan: **G1 y G2 implementados con test cada uno; G3 y G4 documentados en código y schema; G5 aplica al deploy** (PR-1 `b293216` + este PR salen JUNTOS).

---

## 1. Qué implementa

Los **tres mecanismos que perdían valor** ahora conservan o reconocen explícitamente:

1. **(2a)** Liquidar compra sobre pool negativo: el reset que borraba el valor del hueco se reemplaza por el helper — la diferencia entre el COGS ya cargado y el costo real de reposición se persiste en **`purchase_lines.cost_adjustment`** y entra al P&L.
2. **(2b)** Cancelar venta liquidada: reingreso **ponderado** al pool (el COGS devuelto vuelve como VALOR, no solo cantidad — mata la re-valuación fantasma tipo $152M mayo Costa). Si el reingreso rellena un hueco, la diferencia va a **`sales.cancellation_cost_adjustment`**.
3. **(4.4)** Línea nueva de P&L **"Ajuste Costo por Sobreventa"** (`oversell_cost_adjustment`) = Σ ajustes de compras liquidadas (por `liquidated_at`) + Σ ajustes de cancelaciones (por `cancelled_at`), sumada a `total_gross_profit` → `net_profit`. **Conciliación #59 actualizada a 5 líneas** (su test de oro se actualizó a propósito, no como efecto colateral).

**NO implementa** (fases posteriores): ajustes/transformaciones adoptando el helper (PR-4/2c), warnings al cancelar compra (PR-3), remediación histórica (Fase 4).

## 2. La pieza central: helper puro `app/services/inventory_costing.py`

`incorporate_into_pool(liquidated, avg_cost, quantity, unit_cost) -> (new_avg, cost_adjustment)`, sin DB. Tres ramas:
- `liquidated >= 0`: ponderado clásico, adjustment 0 — **idéntico al comportamiento actual** (T6).
- Hueco cubierto (`remaining > 0`): resto entra limpio a `unit_cost`; `adjustment = filled × (avg − unit_cost)`.
- Hueco no cubierto: avg queda en el previo (el hueco restante sigue "cargado" a ese costo).

**El invariante que QA puede verificar a mano** (asiento contable completo — débito inventario / crédito ganancia-oversell o viceversa):

```
pool_after == pool_before + quantity×unit_cost + adjustment      (exacto, 3 ramas)
```

Verificado en los 4 tests unitarios vía `_pool_equation_holds()`. Ejemplos numéricos del plan reproducidos exactos: A (−200@10.000 + 1.000@8.000 → 800@8.000, **+400.000**), B encadenado (−800@8.000 → dos compras → **−300.000 / −750.000**, cuadre total al peso), borde de relleno exacto.

## 3. Cambios por archivo

**Backend:**
- `app/services/inventory_costing.py` — NUEVO (helper puro).
- `app/models/purchase.py` / `app/models/sale.py` — columnas `cost_adjustment` / `cancellation_cost_adjustment` (Numeric(15,2), NOT NULL, server_default 0).
- `alembic/versions/8548fcde95ee_*.py` — migración **escrita a mano** (el autogenerate arrastraba drift ajeno, incl. drop de `backfill_liquidated_at_audit` — tabla de rollback #43 que NO se toca). Solo: 2 add_column + comment de `source_type`. **Aplicada en dev (5434) y test (5433).** Downgrade completo.
- `app/services/purchase.py` — `_apply_cost_at_liquidation` delega en el helper y retorna el adjustment; el loop per-línea (QW-B) lo persiste en `line.cost_adjustment`. **G1**: el helper recibe `adjusted_unit_cost` (precio + comisión/qty) — ya era así por QW-B, ahora con test. **G2**: per-línea con pool corriente — ya era así por QW-B, ahora con test.
- `app/services/sale.py` — `cancel()` rama `was_liquidated`: reingreso ponderado via helper con `line.unit_cost`; **MCH `source_type="sale_cancellation"`** (5º tipo) solo si el avg cambió; `sale.cancellation_cost_adjustment = Σ adjustments`. Cancel de registered intocado (transit no participa del avg).
- `app/services/material_cost_history.py` — `source_labels` + "Cancelacion de venta" → `check_can_revert` **bloquea automáticamente** revertir compras anteriores tras un cancel que movió el avg (mensaje autoexplicativo).
- `app/services/reports.py` — bloque 3.8 en `_calculate_profit` (dos SUMs con el patrón `has_dates` estándar → hereda el corte histórico as-of gratis, que siempre pasa fechas), suma a `total_gross_profit`, mapper, conciliación 5ª línea.
- `app/schemas/reports.py` — `oversell_cost_adjustment` en `ProfitAndLossResponse` y `PnlReconciliation`.
- `tests/test_api_reports.py` — `test_reconciliation_residual_zero` actualizado (5 líneas + assert de la nueva == 0 en fixture sin oversell).

**Frontend** (patrón idéntico a las líneas existentes, fila visible solo si ≠ 0):
- `types/reports.ts` (2 interfaces), `ProfitAndLossPeriodView.tsx` (fila sin drill), `ProfitAndLossMonthlyView.tsx` (fila pivotada con `visible`), `excelExport.ts` (P&L periodo + mensual + conciliación), `ProfitabilityBUPage.tsx` (5ª línea del bloque conciliación).

## 4. Tests — 16/16 verdes (6 de PR-1 + 10 nuevos)

`tests/test_avg_cost_model_l.py`:
- **TestIncorporateIntoPool (4, unitarios puros):** Ejemplo A, rama positiva idéntica a legacy + pool vacío, Ejemplo B encadenado, borde relleno exacto — todos via la ecuación de conservación.
- **TestOversellAtPurchaseLiquidation (3):**
  - T9+T10: hueco −200@10.000 → compra 1.000@8.000 → `cost_adjustment == 400.000`, avg 8.000, **P&L `oversell_cost_adjustment == 400.000` y `net_profit` lo incluye**; luego **round-trip**: cancelar la compra → pool vuelve a −200@10.000 y el P&L a 0.
  - **G1:** compra con comisión fija 40.000 rellenando hueco → adjustment **180.000** (con el ajustado 8.200), no 200.000 (que daría el precio crudo).
  - **G2:** compra de 2 líneas del mismo material sobre hueco de 100 → Σ adjustments == **200.000** exactos y estado final orden-invariante (si el helper viera el pool PRE-liquidación rellenaría 160 unidades ficticias → 320.000; el test lo atrapa).
- **TestCancelSaleWeightedReentry (3):**
  - T8: pool 500@7.800, cancelar venta con COGS 9.000 → avg **8.538,46**, el inventario sube **exactamente** los 7.200.000 devueltos al P&L (simetría), MCH `sale_cancellation` con `previous_cost == 7.800`, y **cancelar la compra anterior ahora da 400** con "Cancelacion de venta" en el detail.
  - Cancel EN hueco: venta A (COGS 10.000) cancelada sobre pool −80@6.000 → `cancellation_cost_adjustment == −320.000` (pérdida: se cargó COGS de menos), pool termina 20@10.000, **P&L por `cancelled_at`** lo refleja.
  - Cancel de registered: avg/liquidated/MCH intocados.

**Stress test adicional (pedido de Daniel):** `TestInventoryStressWalk` — random walk **determinista** (semilla fija 20260710, sin flakes) de 60 operaciones mezcladas (crear/liquidar compras y ventas en órdenes arbitrarios, cancelar liquidadas — aceptando el 400 de `check_can_revert` como resultado válido — y oversell natural). Tras **cada** operación verifica 5 invariantes globales leyendo TODO de BD (no de un tracking del test): I1 `stock == transit + liquidated`; I2 `stock == SUM(inventory_movements)`; I3 `avg >= 0` siempre; I4 `avg == último MCH.new_cost` (válido porque el revert BORRA su registro); I5 **conservación del Modelo L**: `pool == compras_liq − COGS_liq + ajustes_oversell` (tolerancia $1 + $0.005/kg por redondeo de columna). Sanidad: exige ≥5 liquidaciones de cada tipo, ≥1 cancelación efectiva y **haber pasado por hueco** (`saw_hole`). Cierra liquidando todo lo pendiente + verificación final.

**Regresión (corridas SIN solape — BD 5433 exclusiva):**
- `tests/test_avg_cost_model_l.py`: **17/17 verdes** (6 PR-1 + 10 PR-2 + stress walk) en 16s.
- **Suite completa: 968 passed, 6 failed en 15:14** — los 6 failed son EXACTAMENTE los pre-existentes conocidos (5×405 organizations/auth_with_org + `test_update_insufficient_stock_fails`, #54). **Cero regresión.** (968 = 958 de PR-1 + 10 nuevos; el stress se agregó después y está en la corrida de 17.)
- `test_reconciliation_residual_zero` (#59) verde con 5 líneas. `tsc --noEmit` exit 0.
- Nota: `npm run lint` falla en TODO el repo por ausencia de config de ESLint (nunca existió `.eslintrc`/`eslint.config` en frontend/ — verificado en git). Pre-existente, no gate de este PR.

## 5. Puntos para mirar con lupa (auto-señalados)

1. **Signo del adjustment**: `filled × (avg_previo − costo_entrante)`. Positivo = ganancia. Un signo invertido pasa tests de valor absoluto — por eso la ecuación de conservación (exacta, con signo) está en los 4 unitarios, y G1 distingue 180.000 de 200.000.
2. **La ecuación del asiento**: `pool_after = pool_before + entrada + adjustment` — el adjustment aparece en el pool Y en P&L porque es un asiento completo (débito inventario / crédito ganancia), no doble conteo. El round-trip T9 es la verificación independiente: cancelar la compra devuelve TODO (pool, avg, P&L) al estado exacto pre-compra.
3. **Order-dependence intra-compra en oversell** (multi-línea con precios DISTINTOS rellenando un hueco): el estado final depende del orden de las líneas — análogo al inter-operación ya aceptado. El test G2 usa precios iguales (orden-invariante) a propósito; la conservación se mantiene en cualquier orden por la ecuación.
4. **Fecha del MCH de cancelación**: `datetime.now(timezone.utc).date()` — la cancelación es un evento de HOY, no admite fecha elegible (consistente con `cancelled_at`).
5. **Política del adjustment de venta cancelada en el P&L**: se cuenta por `cancelled_at` **aunque la venta esté cancelled** (a diferencia del resto de sus efectos, que se excluyen). Es deliberado: el ajuste ES el efecto real que la cancelación dejó en el inventario. Documentado en el bloque 3.8.
6. **G3 recordatorio de negocio**: el ajuste de compra se fecha por el `liquidated_at` de la compra que rellena — el margen "real" de una venta que sobrevendió en M puede aterrizar en M+1. Comunicar al cliente con el deploy.
7. **`server_default='0'`** en ambas columnas: las filas históricas nacen en 0 → el P&L histórico NO cambia con el deploy de este PR (los ajustes solo aparecen hacia adelante).
8. **⚠️ G5: PR-1 + PR-2 se deployan JUNTOS.** Con este PR el paquete queda deployable (PR-3 warnings es aditivo, no bloquea).

## 6. Pendiente al cerrar (tras QA)

- Commit (feat) + decisión **#65** en CLAUDE.md (el código ya la referencia) + memoria.
- PR-3 (warnings al cancelar compra que proyecta hueco) — trivial sobre esta base.
