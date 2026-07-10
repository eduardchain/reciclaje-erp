# Reporte para QA — Implementación: Fixes de Balance Histórico (incidente Costa)

**Fecha:** 2026-07-09 · **Estado:** implementado, SIN commitear (pendiente aprobación QA) · **Plan aprobado:** `docs/planes/plan-fixes-balance-historico.md` v2.1 (aprobado con 2 correcciones obligatorias, ambas incorporadas)

---

## 1. Contexto en una línea

El Balance General con fecha de corte (as-of) cambiaba retroactivamente entre consultas (incidente Reciclajes de la Costa, corte 03/05/2026): 4 mecanismos reescribían el pasado. Este paquete los corrige y alinea el estado de cuenta de terceros con la fecha canónica de liquidación (decisión #42). Documentado como decisión #61 en CLAUDE.md.

## 2. Alcance implementado (4 fixes + opción B + migración)

### Fix 1 — Activos fijos dados de baja desaparecían de cortes anteriores a la baja
- `backend/app/services/reports.py`: nuevo helper estático `_fa_existed_at_cutoff(cutoff_dt)`: incluye activos `disposed` con `disposed_at >= corte`. `cancelled` sigue excluido siempre (semántica 735c2c3: "nunca existió").
- Aplicado en `_get_fixed_assets_as_of` y `_get_fixed_assets_detailed_as_of`; el detallado sufija el nombre con `(baja DD/MM/YYYY)`.
- `_fa_value_at_cutoff` NO se tocó — su fallback (current_value + Σ depreciaciones posteriores) ya reconstruía el valor pre-baja.

### Fix 2 — Terceros y cuentas inactivos desaparecían de cortes históricos
- `reports.py`: eliminados los filtros `is_active=true` en `_get_tp_balances_as_of` (initial_balance), `_get_account_balances_as_of`, y en los `tp_objs/acc_objs/mat_objs` que consumen los caminos históricos (balance sheet histórico y `_get_balance_detailed_historical`). Esto elimina también el "medio-conteo" previo (initial excluido pero MMs sumados y luego descartados al clasificar).
- `backend/app/schemas/reports.py`: `BalanceDetailedItem.is_inactive: bool = False`.
- Frontend: badge "Inactivo" en `BalanceDetailedPage.tsx`; sufijo `(inactivo)` en PDF (`pdfExport.ts`) y Excel (`excelExport.ts`); tipo en `types/reports.ts`.
- El camino actual (sin as_of) NO cambia: desactivar exige saldo 0, así que los inactivos no aportan al presente.

### Fix 3 — Inventario histórico contaba operaciones comerciales por fecha de documento
- `reports.py` `_get_inventory_as_of` reestructurado: movimientos de compra/venta se incluyen **si y solo si** su operación padre está `liquidated` con `liquidated_at < corte` (EXISTS), posicionados por liquidación. No-comerciales (ajustes/transformaciones/transfers, `reference_type` NULL-safe) siguen por `im.date`. Canceladas excluidas SIEMPRE (de paso corrige stock fantasma de compras canceladas post-corte). Ramas huérfanas (movimiento sin fila padre — 0 en prod, existen en fixtures legacy) preservan el comportamiento anterior.
- **MCH nace con fecha de liquidación**: `purchase.py:439-441` calcula `effective_liq_date = liquidation_date or purchase.date` y `purchase.py:475` lo usa como `transaction_date` del MaterialCostHistory. ⚠️ **Corrección obligatoria QA #1 aplicada**: se usa el PARÁMETRO, no `purchase.liquidated_at` (que se asigna DESPUÉS del loop de MCH, en :513) — leerlo ahí habría grabado NULL/valor viejo.
- Fallback-2 de costo en `_get_inventory_as_of` gana la misma condición de liquidación.

### Opción B — commission_accrual nace con fecha de liquidación (decisión de Daniel tras falsificar un claim de QA)
- Contexto: la justificación de la corrección QA #2 afirmaba que el accrual "ya nacía con liquidated_at" — **verificamos y era falso** (nacía con `sale.date` / `de.date`). Se presentaron opciones A/B y Daniel eligió B: cambiar el nacimiento + migrar datos históricos.
- `sale.py:1220`: `date=sale.liquidated_at or sale.date` (en ventas `liquidated_at` ya está asignado al llamar `_pay_commissions`).
- `double_entry.py:331`: `liq_dt = liquidation_date or double_entry.date` **hoisted ANTES del Step 5** (comisiones); `:343` `date=liq_dt`. ⚠️ Misma trampa de orden que QA #1: en DPs `liquidated_at` se asigna en Step 6, después de las comisiones — por eso se pasa el valor calculado, no el atributo.

### Migración de datos — `backend/alembic/versions/4d8f2c1e9a7b_backfill_canonical_liquidation_dates.py`
- 2 UPDATEs idempotentes (WHERE excluye filas ya alineadas):
  1. `material_cost_histories.transaction_date` de `purchase_liquidation` → `liquidated_at` de su compra.
  2. `money_movements.date` de `commission_accrual` → `liquidated_at` de su venta (cubre DPs: sus accruals llevan `sale_id` de la venta sombra, cuyo `liquidated_at` se setea al liquidar el DP).
- Downgrade re-deriva de la fecha documento (reversible).
- Dimensionado en réplica prod: Costa 160 accruals desalineados ($41,6M redistribuidos entre meses del P&L; la utilidad total no cambia), Meta/Demo 0. Aplicada en dev (5434) y test (5433); segunda corrida = 0 filas (idempotencia verificada).

### Fix 4 — Estado de cuenta posiciona eventos comerciales en fecha de liquidación
- `backend/app/api/v1/endpoints/money_movements.py` (endpoint statement, `response_model=dict`): compras/ventas/DPs/comisiones (y sus pares de cancelación, display-only) se posicionan en `liquidated_at`; campo nuevo `document_date` en cada evento comercial. La ventana de fechas y el saldo de apertura (#55) siguen el nuevo posicionamiento automáticamente (helper `_evt` con `filter_dt` derivado de la fecha del evento). MMs de tesorería intactos.
- DPs: fallback `de.liquidated_at or mediodía-UTC(de.date)` para DPs cancelados que nunca se liquidaron. ⚠️ Se corrigió un scope-bug detectado en autorevisión: el loop de comisiones DP es un bloque separado y definía sus propias variables (`de_liq_dt` habría filtrado un valor viejo del loop anterior).
- Frontend: sub-línea `doc: DD/MM/YY` en web (`AccountStatementPage.tsx`, solo cuando difiere), sufijo en cards mobile, PDF móvil/escritorio (`pdfExport.ts`, con `ellipsis()` real en vez de `substring`), columna "Fecha Doc" en Excel (`excelExport.ts`, ambas vistas).

## 3. Correcciones obligatorias del QA del plan — estado

| # | Corrección | Estado |
|---|---|---|
| 1 | MCH debe usar la fórmula-parámetro, no `purchase.liquidated_at` (orden de asignación) | ✅ `purchase.py:439-441,475`. Test lo cubre (`test_mch_transaction_date_is_liquidation_date`). |
| 2 | Golden test de paridad con fixture natural: DP + comisión + venta standalone | ✅ `test_golden_parity_statement_vs_balance_detailed`: tercero multi-behavior (customer + service_provider) con venta standalone liquidada tarde, DP como cliente, comisión recibida de otra venta y cobro MM; saldo corrido del statement == balance detallado as-of en 3 cortes (abr-30: 100.000, may-31: 155.000, jul-01: 105.000). Nota: el claim que justificaba esta corrección era falso; el fixture igual se implementó como estaba pedido y la causa raíz se resolvió con opción B. |
| — | (No bloqueante) Check pre-deploy de `liquidated_at NULL` | ✅ 0 filas en las 3 tablas (réplica prod). Repetir en prod antes del deploy real. |
| — | (No bloqueante) Verificar que la ventana/filtrado siguen al reposicionamiento | ✅ vía `filter_dt` en `_evt`; test `test_window_follows_liquidation_date`. |
| — | (No bloqueante) Confirmar intención del boundary `>=` en FA disposed | ✅ `disposed_at >= corte` = "dado de baja el mismo día del corte todavía existe al corte". Test de boundary con timestamp determinístico. |

## 4. Evidencia de verificación

**Tests:** 21 nuevos en `backend/tests/test_balance_historico_fixes.py`, todos verdes:
- `TestFix1DisposedAssets` (3): estabilidad del incidente, boundary determinístico, cancelled excluido.
- `TestFix2InactiveEntities` (5): TP/cuenta inactivos en cortes, flag `is_inactive`, fast-path intacto.
- `TestFix3InventoryByLiquidation` (7): reposicionamiento, MCH `transaction_date`, fecha de accrual DP, idempotencia de migración (rowcount=0 en re-corrida vía SQL crudo), huérfanas, canceladas.
- `TestFix4StatementByLiquidation` (6): posicionamiento, `document_date`, ventana, saldo apertura, par de cancelación, **golden parity**.

**Suite completa:** 943 passed + 6 failed = exactamente el set de fallos pre-existentes conocidos (5×405 organizations/auth_with_org + `test_update_insufficient_stock_fails`, nota decisión #54). **Cero regresiones.** Frontend: `tsc` y `npm run build` limpios.

**Smoke contra réplica prod de Costa (corte 03-may):**
- Activos Fijos 771.881.524 — EXACTO a la foto del cliente (fix 1).
- Luminarias +15.009.000 / Cienaga +29.047.890 — EXACTOS (fix 2).
- Inventario 537.169.648 — **tercer valor deliberado** (ni 514,0M de la foto ni 487,5M actual): 13 ventas y 3 compras con doc ≤ 03-may liquidadas después se reposicionan. Re-presentación única al deploy, luego estable.

**Verificación independiente post-fix (2026-07-08):** Daniel comparó su local contra otra foto del cliente; los 4 deltas restantes cerraron AL PESO: inventario +23.152.958 (fix 3, deliberado); ProvServicios/Utilidad ±372.862 (= exactamente los 4 accruals de ventas #313/#314 movidos por la migración, deliberado); CxC +500.000 y Anticipos +1.575.000 (= Alberto Avila +200.000 y Ruben Proyectos +1.875.000 restaurados por fix 2, ± un tercero de $300.000 recategorizado por el propio cliente). Ninguna anomalía sin explicar.

## 5. Dónde mirar con lupa (auto-señalado para QA)

1. **Trampas de orden de asignación** (las dos ya corregidas, verificar que no haya un tercer sitio): MCH antes de `purchase.liquidated_at` (:475 vs :513) y comisiones DP antes del Step 6. En ventas es seguro (`liquidated_at` se asigna en :390, `_pay_commissions` se llama en :406).
2. **`_get_inventory_as_of`**: es el cambio más denso (WHERE con 5 ramas OR). Revisar: NULL-safety de `reference_type`, ramas huérfanas, y que la rama de costo (fallback-2) tenga la misma condición que la de stock.
3. **Timezones**: DP `liquidated_at` queda a medianoche Colombia cuando se asigna un `date` a columna DateTime; los tests usan timestamps determinísticos para no depender de la hora de corrida (una corrida vespertina en Colombia = día siguiente UTC).
4. **Statement `response_model=dict`**: sin schema Pydantic; el contrato de `document_date` solo lo protegen los tests del statement.
5. **Migración**: corre en el deploy vía `/deploy` (alembic upgrade). Idempotente y reversible, pero **el downgrade re-deriva de fecha documento** — si se hace rollback DESPUÉS de que usuarios liquiden operaciones nuevas, esos accruals nuevos también se re-fecharían a documento (aceptable: es exactamente el comportamiento viejo).
6. **Fuera de alcance (explícito)**: el retrofechado manual sigue permitido (mejora `cutoff_date` en backlog); el bug de costo promedio móvil (ventas registradas-no-liquidadas) NO se toca — es write-layer y tiene sesión de diseño pendiente.

## 6. Comunicación al cliente requerida antes del deploy

- Los cortes históricos de inventario se re-presentan UNA vez (Costa 03-may: 487,5M → 537,2M) y quedan estables.
- Los estados de cuenta reordenan operaciones comerciales a su fecha de liquidación (con la fecha de documento visible como referencia).
- El P&L mensual histórico redistribuye comisiones al mes de liquidación (~$41,6M entre meses en Costa; total anual invariante).

## 7. Orden de commits propuesto (develop, tras aprobación QA)

1. `fix(reports): activos dados de baja post-corte permanecen en cortes históricos`
2. `fix(reports): terceros y cuentas inactivos incluidos en cortes históricos`
3. `fix(inventory,reports): inventario histórico por fecha de liquidación + MCH transaction_date` (incluye migración `4d8f2c1e9a7b` + opción B accruals)
4. `feat(treasury): estado de cuenta posiciona eventos comerciales en fecha de liquidación`

Archivos tocados: 6 backend (`reports.py`, `purchase.py`, `sale.py`, `double_entry.py`, `money_movements.py`, `schemas/reports.py`) + 5 frontend (`AccountStatementPage.tsx`, `BalanceDetailedPage.tsx`, `types/reports.ts`, `pdfExport.ts`, `excelExport.ts`) + migración + tests + CLAUDE.md (decisión #61).
