# Reporte para QA — PR Revalorización de Activos Fijos

**Fecha:** 2026-07-10 · **Plan:** `docs/planes/plan-revalorizacion-activos.md` (aprobado por QA con 2 correcciones, ambas plegadas) · **Estado:** implementado, pendiente QA del PR

---

## 1. Qué se implementó (resumen contra el plan)

Todo el plan §2–§8, más las 2 correcciones obligatorias de QA:

- **Corrección 1 (H2 endpoint maps)**: los 2 mapas duplicados de `endpoints/money_movements.py` (`THIRD_PARTY_BALANCE_DIRECTION`, `ACCOUNT_BALANCE_DIRECTION`) ganaron las 4 entradas — el saldo corrido de ambos statements integra los tipos nuevos. Test dedicado `test_h2b_statement_running_balance` (cuenta Y tercero, asserts sobre `balance_after` y `direction`).
- **Corrección 2 (H4 frozensets)**: `asset_revaluation_payment` → `OUTFLOW_TYPES`, `asset_devaluation_collection` → `INFLOW_TYPES` — cubre opening_balance del Cash Flow Y el MTD del Treasury Dashboard (ambos consumen los mismos frozensets, verificado en :931 y :3308). Test `test_h4_cash_flow_and_dashboard_mtd` asserta `opening + net_flow == closing == saldo vivo` y `mtd_income/mtd_expense` exactos.

**La terna de signos** (nota de QA) quedó alineada en los 6 lugares: efecto vivo en `revalue()` = reports as-of ×2 = endpoint statement ×2 = frozensets/mm_map. Los 4 tipos NO entraron al dispatch público de tesorería (no hay dispatcher genérico — cada tipo tiene método de creación propio, así que son module-owned por construcción) ni a `_reverse_effects` (inalcanzables: `annul()` los bloquea antes; entradas muertas invitan drift sin test).

## 2. Decisiones de implementación (donde el plan daba margen o quedó corto)

### 2.1 Guard LIFO ampliado: también revalorizaciones posteriores (NO solo depreciaciones)

El plan §2.5 bloqueaba el annul solo con **depreciaciones** posteriores. Durante la implementación detecté que una **revalorización posterior activa** rompe lo mismo: los snapshots son acumulativos — anular A restaurando `value_before/monthly_before` de A pisa el recalculo que B hizo encima, y el merge as-of (H1) leería el `value_after` de B que INCLUYE a A anulada → as-of ≠ vivo. El guard quedó: **bloquea si existe cualquier evento activo posterior (dep O reval)** → anulación estrictamente LIFO. Con eso la restauración por snapshots es exacta por construcción. Test `test_annul_lifo_order_enforced`: con A y B activas, anular A → 400; anular B → OK (valor vuelve al de A); anular A → OK (valor origen). Sigue siendo un ledger completo — el contraste con Fase 5 (#66) del plan se mantiene.

### 2.2 Validación unificada de "sin meses restantes"

El plan pedía `months_extended ≥ 1` para revivir `fully_depreciated`. Lo implementé como regla general: si tras el alza `remaining_after < 1` → 400 pidiendo extensión. Cubre el caso fully_depreciated Y el edge de un activo `active` cargado histórico con `accumulated == depreciable` (current == salvage con status active, posible vía #46).

### 2.3 Baja que aterriza exacto en el residual

`decrease` con `amount == current − salvage` → `value_after == salvage`: la cuota NO se recalcula (no hay base), queda la anterior como dato, y `status → fully_depreciated` (consistente con `apply_depreciation`). El annul de esa baja restaura `active` (la transición de estado del annul se deriva de `value vs salvage`, no de flags).

### 2.4 H1 reescrito tras pruebas de usuario: reconstrucción pura con ancla diaria

`_fa_value_at_cutoff` ya NO usa snapshots ni merge: `valor(corte) = current_value + Σ dep(period > corte_mensual) − Σ reval_firmada(MM.date >= cutoff_dt)`. Helper nuevo `_fa_reval_future_delta` (JOIN al MoneyMovement de contrapartida — **mismo boundary diario que los saldos as-of de cuentas/terceros**, simetría exacta). Ventaja adicional sobre el merge v1: las sumas conmutan → inmune al orden de APLICACIÓN de eventos (una dep de mayo aplicada tarde en julio habría contaminado cortes intermedios vía su snapshot `current_value_after`, que ya incluye la reval). El delta de `revalued_amount`/acc_dep del detallado as-of también pasó a ancla diaria (`total activas − posteriores`). `AssetRevaluation.period` queda solo como display. Golden test reforzado con el caso exacto del bug: corte de AYER (mismo mes, día anterior al evento) → valor viejo, `revalued_amount` ausente, y `total_assets`/`fixed_assets`/`cash_and_bank` del balance general de ayer **idénticos antes y después** de revalorizar. Re-verificado: 26 revaluation + 21 `test_balance_historico_fixes` (#61) + 22 TestBalanceSheet/Detailed/Audit + 26 FA = **95 verdes** tras el rewrite.

### 2.5 H3 en el path vivo: campo almacenado + `revalued_amount`

El plan pedía corregir la fórmula en 2 sitios. Matiz encontrado: el **vivo** usa `fa.accumulated_depreciation` (campo almacenado, que la revalorización no toca) — ya era correcto individualmente; el que derivaba `purchase − current` era solo el **as-of**. Fix aplicado: as-of ahora deriva `acc_dep = purchase + Σreval_firmadas(≤corte, activas) − valor_al_corte` (helper nuevo `_fa_reval_delta`), y AMBOS paths exponen `revalued_amount` en el ítem (vivo: query agregada única, sin N+1) para que `compra + reval − acc_dep == valor` sea verificable a ojo en el Balance Detallado.

## 3. Archivos tocados

**Backend:** `models/fixed_asset.py` (+`AssetRevaluation`), `models/money_movement.py` (+4 tipos), migración `8d1a27b7bb31` (tabla, ID random, aplicada dev+test), `services/fixed_asset.py` (`revalue`, `annul_revaluation`, `cancel` extendido, `get` eager-load), `services/money_movement.py` (`ASSET_MOVEMENT_TYPES` +4, mensaje), `services/reports.py` (H1 reconstrucción pura + `_fa_reval_delta`/`_fa_reval_future_delta`, H2 ×2, H3 ×2, H4 buckets+frozensets), `endpoints/fixed_assets.py` (+2 rutas, `_build_response`), `endpoints/money_movements.py` (H2 ×2), `schemas/fixed_asset.py` (+3 schemas, response +2 campos), `schemas/reports.py` (+`asset_devaluation_collections`, +`revalued_amount`).

**Frontend:** `types/fixed-asset.ts`, `types/money-movement.ts`, `types/reports.ts`, `services/fixedAssets.ts` (+2), `hooks/useFixedAssets.ts` (+2), `components/treasury/RevalueAssetModal.tsx` (nuevo: toggle alza/baja, XOR contrapartida, preview en vivo espejo de la fórmula backend, warning G1 de depreciaciones pendientes), `FixedAssetDetailPage.tsx` (botón + sección dual desktop/mobile + annul con razón), labels en 5 páginas treasury + colores + hide de "Anular" en MovementDetailPage, línea condicional en CashFlowPage + Excel. `tsc` limpio, build OK. Mobile: modal `grid-cols-1 sm:grid-cols-2`, botones `w-full sm:w-auto`, tabla de revalorizaciones dual render.

**Sin cambios (verificado):** `_calculate_profit`, conciliación #59/#65 (cero P&L — test de paridad `test_pnl_untouched_by_revaluation`), Rentabilidad por UN, Reporte de Gastos, `EDITABLE_EXPENSE_TYPES`, migrate_org.

## 4. Tests — 26 nuevos en `tests/test_asset_revaluation.py`

| Grupo | # | Qué cubre |
|---|---|---|
| Happy paths | 4 | alza/baja × cuenta/tercero: valor, cuota recalculada, saldos, tipo MM, snapshots |
| Validaciones | 7 | monto ≤0, XOR, months en baja, baja>depreciable, disposed, provision (#32), fondos insuficientes |
| Recalculo | 4 | extensión baja la cuota; conservación hasta la última cuota (total depreciado == valor revalorizado); revivir fully_depreciated (sin meses 400 / con meses activo); baja a residual → fully_depreciated |
| Anulación | 5 | round-trip exacto; guard dep posterior; **guard LIFO entre revalorizaciones**; 422 desde Tesorería; cancel de activo revierte revalorizaciones (cuenta Y tercero a origen) |
| Reportes | 5 | **H1 golden**: cortes previos idénticos post-reval (no-restatement), corte hoy == vivo, nivel 2 reconstruye a valor de compra, acc_dep H3 correcto; **H2** as-of == vivo (cuenta y tercero); **H2b** saldo corrido de ambos statements; **H4** cash flow cierra + dashboard MTD; **P&L intocado** |
| RBAC | 1 | viewer → 403 |

Nota fixture: `fa_account` define `initial_balance == current_balance` — la invariante real que el as-of de cuentas reconstruye; el primer run falló por fixture (no por código) al omitirla.

**🔴 BUG encontrado en pruebas de usuario y CORREGIDO — ancla mensual → diaria (§2.4 abajo):** mi v1 anclaba la revalorización al mes (`period`, como #41) y lo reporté como "semántica esperada". Daniel lo refutó con el caso real: Camión LGU-673 revalorizado +5M hoy → **el corte de AYER mostraba el activo con el valor nuevo y el total de activos crecía 5M** (la caja, con ancla diaria del MM, no bajaba hasta hoy → descuadre). La analogía con depreciaciones era falsa: la cuota pertenece al mes y su MM no toca caja; la revalorización es un evento puntual CON contrapartida de caja/tercero — ambos lados deben moverse juntos en todo corte.

## 5. Resultado de suite

- `test_asset_revaluation.py`: **26/26 verdes**.
- Vecinos: `test_api_fixed_assets.py` + `test_integration_08` (38) y `test_api_money_movements.py` + `test_api_reports.py` (242) — verdes sin modificar ningún test existente (cero cambios de semántica en flujos previos).
- Suite completa: **1014 passed + 6 failed (los 6 pre-existentes conocidos exactos: 5×405 organizations/auth_with_org + `test_update_insufficient_stock_fails`, nota #54)** — 988 previos + 26 nuevos = 1014, cero fallos nuevos. Total 1020 tests.
- Post-suite se agregó un `joinedload(FixedAsset.revaluations)` a `get_multi` (el `revalued_total` en `_build_response` habría hecho lazy-load N+1 en el listado) y se re-corrieron `test_asset_revaluation.py` + `test_api_fixed_assets.py`: **63 passed**.

## 6. Validación de usuario (Daniel, 2026-07-10, localhost sobre réplica de prod — Reciclajes de la Costa)

- **Alza + cuenta** (Camión LGU-673, +5M) y **alza a crédito + tercero** (Prensa Vertical AH, +10M con cliente AAtlantic): efectos verificados contra BD al peso.
- **Encontró el bug del corte histórico** (corte de ayer incluía la reval de hoy → total activos +5M sin contrapartida) → corregido con ancla diaria (§2.4), golden test reforzado con su caso exacto.
- **Confusión documentada, no bug**: alza a crédito con un CLIENTE → la deuda cae en "Anticipos de Clientes" (pasivo, clasificación #31) y consume primero el saldo que el cliente debía. Ecuación verificada al peso (Δactivos = Δpasivos = $9.663.000). Copy del modal mejorado: ahora dice explícitamente dónde aterriza cada contrapartida (alza→PASIVOS, baja→CxC) y recomienda usar el proveedor que facturó la mejora.
- **Anulación de ambas alzas**: round-trip verificado contra BD (valores/cuotas exactos, MMs anulados, AAtlantic de vuelta a +337.000, auditoría de Caja Chica `initial + Σmovimientos == stored` al peso).
- **Baja + cuenta y baja + tercero** (Contenedor Prosperidad, 2×$2M): snapshots encadenados correctos (12M→10M→8M, cuotas 120K→100K→80K), caja +2M, CxC del tercero +2M, total de activos invariante.
- **Hallazgo UX (post-luz-verde)**: "Desde tesorería ni siquiera se muestra el botón de anular" — comportamiento diseñado (patrón pre-existente de #21: los MMs de activos ocultan Anular y el backend responde 422), pero la página quedaba muda. Fix: nota guía índigo en `MovementDetailPage` para los 7 tipos de activos (los 3 de #21 + los 4 de reval) explicando dónde se revierte cada uno, con link a Activos Fijos. Solo frontend, cosmético.

Las 4 patas + anulación + cortes históricos: validadas por usuario sobre datos reales.

## 7. Qué revisar con foco (sugerencia)

1. La terna de signos: `revalue()` vivo vs los 4 mapas vs frozensets (tabla 2.2 del plan).
2. El golden H1 (`test_h1_golden_asof_no_restatement`) y la reconstrucción pura con ancla diaria en `_fa_value_at_cutoff` / `_fa_reval_future_delta` (§2.4) — incluye el caso corte-de-ayer y la resta firmada.
3. El guard LIFO ampliado (§2.1 arriba) — decisión mía no explícita en el plan aprobado.
4. `cancel()` extendido — reversión de revalorizaciones con MM anulado + saldos a origen.
