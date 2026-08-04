# Informe CODE — SAC E3.1: Traslados dos pasos + maquila intersede + P&L por sede

**Fecha:** 2026-07-20 (golden y re-QA: 2026-07-23). **Plan:** `plan-sac-e3-1-traslados-maquila.md` **v1.2** (C1 resuelto — `transfer_id` NO se serializa). **Re-QA del informe: 🟢 GO sin condiciones (2026-07-23)**; cosmético aplicado: docstring del guard tránsito alineado al orden real de los checks. **Decisión:** #84 en CLAUDE.md. Sin commit (quedan pruebas de Daniel → commit develop).

---

## 1. Qué se construyó (mapa de archivos)

**Backend:**
- `app/models/transfer.py` (NUEVO): `Transfer` + `TransferLine` — cabecera+líneas, todo por línea (E2), CHECKs `qty_dispatched > 0` / `qty_received >= 0` (bloq-7).
- `app/models/warehouse.py`: `is_transit` + `transit_target_warehouse_id` (ruteo único menor-31).
- `app/models/inventory_adjustment.py`: `transfer_id` FK nullable (C1: interna, NO expuesta en response — verificable en `GET /inventory/adjustments`, serialización byte-idéntica).
- `app/models/money_movement.py`: catálogo 39→41 (`internal_maquila_expense/income`) + set `INTERNAL_MAQUILA_MOVEMENT_TYPES`.
- `alembic/versions/a7b8c9d0e1f2_sac_e3_transfers.py`: todo aditivo, FKs sin nombre (paridad create_all), permiso `inventory.transfer_receive` (sort 147, **sin** roles de sistema, dual-write triple con `services/role.py`). Aplicada en dev(5434) y test(5433).
- `app/services/transfer.py` (NUEVO, ~700 líneas): dispatch / receive / resolve / annul + guard exportado `validate_not_transit_warehouse` (flag-check primero, mayor-12).
- `app/services/inventory_adjustment.py`: `increase`/`decrease`/`annul` ganan `commit: bool=True` (patrón #20/#75, default = comportamiento actual byte a byte) + `_validate_warehouse` gana `allow_transit=False` con el guard E12.
- `app/services/purchase.py` (create + update) y `app/services/sale.py` (create + update): guard tránsito tras la validación de bodega existente.
- `app/services/money_movement.py`: guard 422 en `annul()` (patrón #67/#69) + rama `pass` explícita en `_reverse_effects`.
- `app/services/reports.py`: `_calculate_profit` gana `warehouse_id`/`include_internal_maquila`; `get_profit_and_loss` + `monthly` + endpoint los propagan.
- `app/schemas/transfer.py` (NUEVO) + `app/schemas/warehouse.py` (campos tránsito) + `app/schemas/reports.py` (2 campos maquila, default 0.0).
- `app/api/v1/endpoints/transfers.py` (NUEVO): router `dependencies=[require_org_flag("two_step_transfers_enabled")]`.

**Frontend:** `types/transfer.ts`, `services/transfers.ts`, `hooks/useTransfers.ts`, `invalidateAfterTransfer` (N1, #27), páginas `transfers/{TransfersPage,TransferCreatePage,TransferDetailPage}`, rutas FP + Sidebar "Traslados" (orgFlag + badge ámbar), selector de sede en `ProfitAndLossPeriodView` (flag-gated, excluye tránsito, banner explicativo del alcance M1), filas maquila condicionales ≠0, guard visual en `MovementDetailPage` (botón Anular oculto + nota índigo, labels), Config→Bodegas campos tránsito gated, StockPage "Trasladar" redirige al 2-pasos con flag (§2.12).

## 2. Cómo aterrizaron los 3 hallazgos del re-QA

**B1 (E8 ↔ invariante #1)** — `_close_transit_with_merma` llama `inventory_adjustment.decrease(commit=False, allow_transit=True)` sobre la bodega de TRÁNSITO al avg org-wide → la pérdida cae en `adjustment_net` (verificado contra `reports.py:611`). Cero `incorporate/remove_from_pool` en el camino de traslado; los movimientos salen/entran al `unit_cost` snapshot. **Test guardián** `test_receive_merma_within_tolerance_b1_guardian`: avg == 1000.0000 exacto tras recepción con merma + `cost_adjustment == 0` en el ajuste + `test_transfer_movements_write_no_mch` (cero MCH nuevos). El cascade de anulación usa el annul canónico #66 (N-b: reingreso ponderado — el walk no lo lee como violación del invariante, acotado a despacho/recepción).

**M1 (comisiones por sede + alcance E13)** — el filtro es `Sale.warehouse_id` en `comm_filters` (la query ya hacía `.outerjoin(Sale)`, `reports.py:897`); comentario ⚠️ en el código contra el filtro-trampa. Gastos/service_income/DP/transformaciones/ajustes/oversell/tp_adj por sede: **`false()` inyectado en los 14 filter-lists** (`_not_by_sede`) → WHERE false, $0 exacto, y el camino consolidado (`warehouse_id=None`) no agrega NINGÚN filtro (byte-idéntico). **Test de oro** `test_golden_commission_parity_by_sede`: fixture con comisión $1.000 ≠ 0; asserts `commissions_paid(CV) == Σ accruals de ventas CV ±$1` **y `> 0`** — con el filtro equivocado da $0 y revienta. `test_pnl_sede_cv` además clava el neto completo (−$11.000: bruta 20.000 − maquila 30.000 − comisión 1.000).

**M2 (vendido)** — `annul` del traslado con venta posterior desde JM → `test_annul_with_sold_material_warns_not_blocks`: 200 + warning "queda negativo…", NO 400. Desviación declarada §2.7 + Q-E3.1-d en el paquete a Johana/Hugo.

## 3. Menores N1-N5 + C1 + notas

| # | Aterrizaje |
|---|---|
| C1 | `transfer_id` NO está en ningún response schema de ajustes (solo modelo+migración). |
| N1 | `invalidateAfterTransfer` en `queryInvalidation.ts` + documentado en #27. |
| N2 | `test_receive_multiline_mixed_tolerance`: línea A emite (kg=20), B retiene, cabecera `held_discrepancy`. |
| N3 | `test_receive_over_dispatched_always_held` (recibido 41 vs 40 = 2.5% ≤ 5% numérico → held igual; físico capado, tránsito 0) + `test_resolve_excess_enters_identity_d2` (increase destino, `cost_adjustment==0`, avg intacto, tránsito==0 — N-a asserted). |
| N4 | Runbook §7: la tarifa se **CREA** vía POST (fail-fast del receive la exige: `test_receive_missing_tariff_400`). |
| N5 | Terna §2.3 con el allowlist inline `reports.py:817`; la exclusión del consolidado es por construcción (los tipos jamás entran al allowlist) + query separada gated. |
| N-a | Resolve mueve SOLO el delta (`target_from_transit − entered`); sin doble entrada física. |
| N-b | Docstring del servicio + invariante 1 del plan acotados a despacho/recepción. |
| N-c/N-e | Referencias `reports.py:817` y `services/role.py` corregidas en el plan. |
| N-d | `transfer_id` espejado en el modelo (D13) — parity lo verifica mecánicamente. |

## 4. Evidencia de gates

| Gate | Resultado |
|---|---|
| Tests nuevos | **50/50 verdes** — `test_sac_transfer_two_step.py` (42: gating×5, dispatch×6, receive×12, resolve×5, annul×7, guard tránsito×5, no-regresión×2) + `test_pnl_by_warehouse.py` (8: consolidado byte-safe, include netea $0, CV, JM, oro comisión≠0, no-atribuibles $0, monthly, conciliación #59). |
| Suite completa | **1395/1395 verdes** en 32:42 (1345 previos + 50 nuevos, CERO regresiones — exit 0). |
| Migración | `alembic upgrade head` OK en dev(5434) y test(5433). |
| Schema parity | **DIFF CERO fuera del baseline** — 58 tablas, 259 índices, 286 constraints comparados (corrido tras la suite, secuencial). |
| tsc / build | Limpios (`tsc --noEmit` exit 0; `vite build` 5.8s). |
| 390px | Patrones CLAUDE.md aplicados (dual render tabla/cards, sticky bottom, grid-cols-1 sm:, tabs overflow); verificación DevTools en pruebas de Daniel. |
| Golden ×3 orgs | **✅ EJECUTADO 2026-07-23 — 0 diffs reales** (pedido de Daniel de adelantarlo; la org SAC dev se recrea con `scripts/seed_sac_org.py`, ya no es blocker). Réplica fresca de prod (backup 2026-07-24 00:03 UTC) → BEFORE con `origin/main` (7471230, incluye hotfix PR #11) en :8001 → `alembic upgrade head` (las 11 migraciones E1→E3.1 aplicaron limpias = ensayo del deploy) → AFTER con develop+E3.1 en :8002 → diff. **45 capturas** (15 × Costa/Biogreen/MetaRecycling: P&L período+junio+mensual, BG y BD vivo+as-of 2026-06-30, cash flow, saldos cuentas, estado de cuenta del tercero más caliente, GET /warehouses, GET /money-movements paginado, gastos+detail, rentabilidad por UN): **cero diferencias de valor; solo claves aditivas documentadas** — `warehouses` +3 (`is_receiving=true` Ciclo B, `is_transit=false`/`transit_target_warehouse_id=null` E3.1), P&L +2 (`internal_maquila_*=0.0`), y hallazgo nuevo: `money_movements` +4 (`warehouse_id/tariff_id/source_type/source_id`) y `money_accounts` +1 (`warehouse_id`) **siempre null en prod** — columnas E1 que los list endpoints (`response_model=dict` + ORM → jsonable_encoder) serializan solos; mismo carácter aditivo-nulo, allowlist con valor exacto. Harness persistido en `backend/scripts/golden_capture.py`/`golden_diff.py` (E2 perdió el suyo con el scratchpad); evidencia en `docs/planes/evidencia-golden-2026-07-23/`. Smoke E3.1 post-golden sobre SAC recreada: despacho 40kg SCR-MOTO CV→JM, recepción 39kg (merma 2,5% ≤ 5%) → kg plomo 19,11 (39×0,49), par maquila $28.665 (19,11×$1.500) ambos lados y en P&L por sede, avg intacto $1.000, merma como `decrease`, tránsito en 0 — **TODO VERDE**. |

**No-regresión estructural**: flags default false (3 orgs prod jamás entran a ningún camino nuevo); guard tránsito cortocircuita sin flag (`test_guard_inert_without_flag`); P&L sin params no agrega filtros (los `_not_by_sede` son lista vacía); los 2 tipos MM fuera de todos los mapas; response P&L +2 claves con 0.0 (mismo patrón #65/#71).

## 5. Limitaciones declaradas / preguntas vivas

- Por sede solo fragmenta ventas+COGS+comisiones+maquila (M1); gastos $0 hasta caja-menor-por-sede (E4) — banner en la UI lo dice.
- Q-E3.1-a/b/c/d/e en el paquete a Johana/Hugo (defaults conservadores, no bloquean).
- Recepción parcial no soportada (atómica, Q-E3.1-b): request sin todas las líneas → 400.
- `include_internal_maquila` en consolidado es para E5 (hoy el frontend no lo usa).

## 6. Runbook prod E3.1 (se suma al del tren)

1. Config→Bodegas: crear **JM-TRANSITO** (`is_transit=True`, target=JM, `is_receiving=False`).
2. **Crear** tarifa `maquila_intersede_cv_jm` = $1.500 `per_kg_lead` (POST /service-tariffs — N4: sin seed).
3. Confirmar cuenta kg `intersede` activa (crearla en Plomo (kg) si falta).
4. Settings org SAC: sumar `two_step_transfers_enabled: true` + `internal_maquila_enabled: true` al payload COMPLETO (REPLACE — no perder claves previas).
5. ~~Golden gate duro antes del merge~~ **HECHO 2026-07-23 (ver §4) — 0 diffs reales**. Si develop recibe más commits antes del deploy, re-correr con `golden_capture.py`/`golden_diff.py` es barato (~15 min).
6. **Hallazgo de la réplica**: la org **SAC ya existe en PROD** (id `db95c7c1-…`, shell sin operaciones — el schema prod aún no tiene `settings`). El go-live provisiona ESA org (o se decide resetearla); los maestros se pueden sembrar con `scripts/seed_sac_org.py` apuntado a prod SOLO vía decisión explícita en el deploy (el script hoy es dev-only, `BASE_URL` fijo a localhost).
