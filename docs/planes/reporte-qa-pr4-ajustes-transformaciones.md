# Reporte para QA — PR-4: ajustes de inventario y transformaciones adoptan el helper

**Fecha:** 2026-07-10 · **Estado:** implementado, SIN commitear (pendiente QA) · **Rama:** develop
**Plan:** `docs/planes/plan-fix-estructural-costo-promedio.md` (Fase 2c). Aditivo sobre PR-1/PR-2/PR-3; **NO** participa del acople G5 (sin PR-4, un increase sobre hueco sigue reseteando el avg como hoy — no empeora nada; el paquete puede deployar con o sin él, aunque lo natural es junto).

## 1. Qué hace

PR-2 arregló el relleno de hueco (pool negativo) **solo para compras liquidadas**. Quedaban dos entradas al pool con el reset destructivo original (`if old_liquidated <= 0: avg = unit_cost`, que evapora el valor del hueco sin contrapartida):

1. **Ajuste de inventario `increase`** (`inventory_adjustment.py:89-94`)
2. **Línea destino de transformación** (`material_transformation.py:283-287`)

Ambas adoptan `incorporate_into_pool()` (mismo helper puro de PR-2, sin cambios): sobre pool negativo, la entrada rellena el hueco al costo promedio previo y la diferencia se persiste como `cost_adjustment` → entra al P&L en la línea "Ajuste Costo por Sobreventa" que ya existe.

## 2. El cambio (7 archivos + tests)

### Modelos + migración `7c2f9a41d8e3` (aplicada dev 5434 + test 5433)
- `InventoryAdjustment.cost_adjustment` y `MaterialTransformationLine.cost_adjustment` — `Numeric(15,2), nullable=False, server_default="0"` (mismo patrón que `PurchaseLine.cost_adjustment` de PR-2). Migración escrita A MANO (el autogenerate arrastra drift ajeno, mismo criterio que `8548fcde95ee`). Downgrade completo.
- ⚠️ Anécdota de guerra: el primer ID elegido (`a1b2c3d4e5f6`) **colisionó** con una migración existente de 2025 (`a1b2c3d4e5f6_agregar_tabla_money_movements.py`) → "Cycle is detected in revisions". Renombrada a `7c2f9a41d8e3`. Los IDs "bonitos" secuenciales ya están minados en este repo.

### `inventory_adjustment.py increase()`
- Reset destructivo → helper. `adjustment.cost_adjustment = cost_adjustment` tras `_create_adjustment`.
- **MCH `adjustment_increase` se sigue registrando SIEMPRE** (igual que antes, incluso si el avg no cambió — rama hueco-no-cubierto): el `annul()` depende de ese registro para `revert_cost_change`. Verificado en las 3 ramas del helper que el revert restaura exacto (`previous_cost` = avg pre-increase en todas).
- `decrease`/`recount`/`zero_out`: **intactos** (decrease y zero_out salen al avg vigente — ya conservan; recount mantiene su inconsistencia pre-existente documentada en el plan: pondera con `old_total` en vez de `old_liquidated`, fuera de alcance).

### `material_transformation.py create()`
- Primer loop captura `created_lines` (las líneas ya se creaban antes del loop de costeo; solo se conserva la referencia).
- Loop de destinos: reset destructivo → helper + `created_lines[i].cost_adjustment = cost_adjustment`.
- Dato no obvio: con método `average_cost` el destino entra A SU PROPIO promedio → `filled × (avg − avg) = 0`, el adjustment es siempre 0 (la diferencia de valor ya va a `value_difference`, decisión #17). El adjustment ≠ 0 aparece con `proportional_weight` y `manual`. Hay test que lo documenta.
- `annul()`: intacto — revierte via MCH `transformation_in` (siempre registrado) y la transformación anulada sale del P&L por el filtro de status.

### `reports.py` bloque 3.8 (P&L)
Dos SUM nuevos en `oversell_adjustment` (misma línea del P&L, mismos campos de schema — **cero cambios frontend**, la fila "Ajuste Costo por Sobreventa" de PR-2 los absorbe):
- `InventoryAdjustment.cost_adjustment` — status `confirmed`, fechado por `InventoryAdjustment.date`. Sin exclusión de seeds de migración: entran sobre pool 0 → helper devuelve 0 → el filtro `!= 0` los deja fuera solo.
- `MaterialTransformationLine.cost_adjustment` JOIN transformación — status `confirmed`, fechado por `MaterialTransformation.date`.

Sin exposición en response schemas (paridad con PR-2: `PurchaseLine.cost_adjustment` tampoco se expone — el campo es fuente del P&L, no dato de detalle).

## 3. Tests (5 dirigidos nuevos + walk extendido → archivo queda en 24)

- `TestOversellInventoryIncrease` (3): Ejemplo A vía ajuste (hueco -200@10.000 + increase 1.000@8.000 → `cost_adjustment=400.000`, avg 8.000, P&L, **annul round-trip exacto** de vuelta a -200@10.000 y P&L 0); relleno parcial (hueco no cubierto → avg queda en 10.000, adjustment 300.000); pool positivo → ponderado clásico con adjustment 0 (paridad legacy).
- `TestOversellTransformationDestination` (2): destino en hueco con `proportional_weight` (filled 100×5.000 = 500.000 al P&L, annul revierte destino Y fuente, P&L a 0); método `average_cost` auto-neutral (adjustment 0 incluso sobre hueco).
- **Stress walk extendido**: 3 acciones nuevas (`adj_increase` peso 6, `adj_decrease` 6, `adj_annul` 4; pesos rebalanceados suman 100), sanidad `ai≥2, ad≥2`, e **I5 gana 2 términos**: `+ Σ(IA.quantity × IA.unit_cost)` y `+ Σ(IA.cost_adjustment)` sobre ajustes `confirmed`. Misma semilla 20260710 — pasó a la primera con `saw_hole` intacto.

### Regla de invalidación en el walk (hallazgo del diseño, léelo con lupa)

Las reversiones vía MCH (annul de increase, cancel de compra liquidada) **solo son exactas si nada extrajo/reingresó valor del pool después sin dejar MCH** — y bajo Modelo L las ventas liquidadas, los cancels sin cambio de avg y los decreases son MCH-silenciosos: `check_can_revert` no los ve, permite el revert, y el avg rebobinado ya no corresponde al pool actual → conservación rota. Ejemplo: pool 100@10.000 → increase 100@6.000 (avg 8.000) → decrease 50 (sale a 8.000, sin MCH) → annul del increase permitido → avg vuelve a 10.000 con 50 unidades que salieron "baratas" → fuga de 100.000.

**Esto es PRE-EXISTENTE** (las ventas nunca crearon MCH, tampoco los decreases) y NO lo introduce ni lo arregla PR-4 — pero el walk extendido lo habría pisado. Mitigación en el test: `confirmed_increases.clear()` tras cada operación MCH-silenciosa → el walk solo anula increases "limpios" (que es exactamente la condición bajo la cual el revert es matemáticamente sólido). El walk pre-PR-4 con `purchase_cancel` tenía la misma exposición y pasó por suerte de semilla.

**Implicación para producción** (decisión para Daniel/QA, candidata a Fase 5 o backlog): `check_can_revert` da falsos permisos cuando entre la operación y su reversión hubo extracciones MCH-silenciosas. Opciones: (a) que también mire `InventoryMovement` posteriores, (b) que cancel/annul hagan remoción ponderada en vez de revert (análogo del reingreso ponderado de PR-2), (c) aceptarlo documentado (las magnitudes son proporcionales a lo extraído entre medias × delta de avg). Igual gap en **annul de decrease** (reingresa al avg vigente, no al de la salida). Nada de esto empeora con PR-4; solo quedó visible al formalizar I5.

## 4. Verificación

- `test_avg_cost_model_l.py`: **24 passed** (19 previos + 5 nuevos, walk extendido incluido).
- Subset impactado (`test_api_inventory_adjustments` + `test_api_material_transformations` + `test_api_reports` + `test_pnl_drilldown_parity` + `test_pnl_monthly` + `test_balance_historico_fixes`): **213 passed** — incluye `test_reconciliation_residual_zero` (el guardián anti-drift de #59) y las paridades doradas.
- Suite completa: **976 passed, 6 failed en 16:40** — los 6 son EXACTAMENTE los pre-existentes conocidos (5×405 en organizations/auth_with_org + `test_update_insufficient_stock_fails`, nota decisión #54). Total sube de 977 a 982 (+5 de PR-4).
- Frontend: **cero cambios** (la línea P&L existe desde PR-2). No aplica tsc.
- BD test 5433 queda libre y limpia — mi corrida terminó. Un pytest a la vez, como siempre.

## 5. Puntos con lupa (self-review honesto)

1. **MCH incondicional en increase** (a diferencia del `sale_cancellation` de PR-2 que solo registra si el avg cambió): deliberado — el annul de increase revierte VIA ese MCH; sin registro, `revert_cost_change` no encontraría qué revertir. En la rama hueco-no-cubierto el MCH queda con `previous_cost == new_cost` (no-op al revertir, pero el registro bloquea reverts anteriores correctamente).
2. **Anulación y P&L**: el `cost_adjustment` de un ajuste/transformación anulado sale del P&L por el filtro `status='confirmed'` (no hace falta campo espejo tipo `cancellation_cost_adjustment` — a diferencia de ventas, donde la cancelación es un EVENTO nuevo con efecto propio; aquí anular = "nunca existió", consistente con `_active_at_cutoff` de #41).
3. **G3 (timing)** aplica igual: el adjustment se fecha por la fecha del ajuste/transformación que rellena, que puede caer en mes distinto al de la sobreventa.
4. **G4**: los 2 términos nuevos entran al `oversell_adjustment` org-level → misma 5ª línea de la conciliación de Rentabilidad por UN. `test_reconciliation_residual_zero` verde lo confirma.
5. **Transferencias entre bodegas**: no tocan `current_average_cost` ni stock global — fuera de alcance, correcto.
6. **`recount`**: NO adoptó el helper (su rama de aumento pondera con `old_total` — inconsistencia pre-existente distinta, documentada en el plan §10). Adoptarlo aquí habría mezclado dos cambios de semántica en un PR.
7. **Polizón de PR-2**: `models/material_cost_history.py` trae el comment del modelo alineado a los 5 source_types (`sale_cancellation`) — la migración `8548fcde95ee` ya lo había actualizado en BD, pero el archivo del modelo quedó sin commitear en fb80037. Viaja en este commit (1 línea, solo comment).

Al cerrar (tras QA): documentar dentro de #65 (línea de Fase 2c) + memoria `bug_costo_promedio_movil` con el hash.
