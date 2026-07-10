# Plan Fase 5 — Remoción ponderada en reversiones (retiro del rewind + check_can_revert)

**Fecha:** 2026-07-10 · **Estado:** BORRADOR para revisión QA (sin implementar) · **Decisión de Daniel:** "planea con remoción ponderada"
**Prerequisito:** PR-2 (#65) deployado o en el mismo paquete — reusa `incorporate_into_pool` y el patrón `cost_adjustment` → P&L.
**Memoria relacionada:** `bug_check_can_revert_falsos_permisos`.

---

## 1. El problema (recap con el ejemplo de la conversación)

Hoy las reversiones (cancelar compra liquidada, anular increase, anular transformación) funcionan por **rewind**: `revert_cost_change` restaura `previous_cost` del registro `MaterialCostHistory` (MCH) y **borra** el registro. El guardián `check_can_revert` solo permite el rewind si no hay MCH posterior.

**El punto ciego:** bajo Modelo L, liquidar ventas, cancelar ventas sin cambio de avg y los decreases **mueven valor sin escribir MCH**. El guardián no los ve → permite rewinds inexactos:

```
1. Pool: 100 kg @ $10.000 ($1.000.000)
2. Increase +100 @ $6.000 → avg $8.000. MCH: "10.000 → 8.000"
3. Venta liquida 50 kg → salen a $8.000 (COGS $400.000). MCH: NADA
4. Annul del increase: guardián mira MCH → el increase es el último → PERMITE
5. Rewind: stock 150−100=50, avg vuelve a $10.000 → pool dice $500.000
   Cuenta real: 1.000.000 + 600.000 − 400.000 − 600.000 = $600.000
   → $100.000 EVAPORADOS sin rastro en ningún P&L
```

### 1.1 Evidencia en datos (réplica prod fresca 2026-07-10, dev 5434)

| Métrica | Valor |
|---|---|
| Compras canceladas que estaban liquidadas | 18 |
| … de esas, con ventas liquidadas del mismo material ENTRE liquidación y cancelación (condición de fuga) | **13 (72%)** |
| Increases anulados / con actividad entre medias | 10 / 0 |
| Transformaciones anuladas / con actividad entre medias | 3 / 0 |
| Ventas canceladas liquidadas (ya cubiertas por reingreso ponderado PR-2) | 21 |
| Compras liquidadas HOY que el guardián **bloquearía** si se intentara cancelar (MCH posterior) | **1.731 de 2.195 (79%)** |

**Lectura:** el guardián bloquea sobre el eje equivocado. Bloquea el 79% de los cancels legítimos (dolor operativo: "Cancele primero: …" encadenado) mientras que las 13 fugas reales pasaron limpio (no había MCH posterior, había ventas). Las magnitudes de las 13 fugas históricas NO se remedian (decisión 2026-07-10: el pasado no se reescribe) — esto es forward-only.

---

## 2. La idea: todo movimiento del pool es entrada/salida A VALOR, conservación garantizada

PR-2 ya lo hizo para un caso: cancelar venta liquidada = **reingreso ponderado** (la cantidad vuelve con su COGS original como valor, `incorporate_into_pool`). Fase 5 completa el espejo: **toda reversión saca (o reingresa) la cantidad al costo con que entró (o salió), y la diferencia contra el estado actual del pool fluye como `cost_adjustment` al P&L**. Nunca se rebobina, nunca se bloquea, nunca se borra historia.

Consecuencias arquitectónicas:

1. **`check_can_revert` se retira** de estos caminos (queda sin callers → deprecar). Desaparecen los errores "Cancele primero: …". La decisión #40 (transformación bloquea cancel de compra fuente) y el rol bloqueante del MCH `sale_cancellation` (#65) quedan **superseded**: la protección era necesaria porque el rewind corrompía; con remoción ponderada el valor conserva por construcción, haya pasado lo que haya pasado después.
2. **MCH pasa a append-only PURO**: `revert_cost_change` (que hace `db.delete(history)`) se retira. Las reversiones ESCRIBEN un MCH nuevo en vez de borrar el viejo. El invariante I4 (avg == último MCH) se fortalece: hoy tiene la excepción "salvo que un revert borre"; después del cambio no hay excepción.
3. El warning de PR-3 (hueco proyectado al cancelar) **se mantiene** — sigue siendo información útil.

---

## 3. Helper nuevo: `remove_from_pool` (espejo de `incorporate_into_pool`)

`services/inventory_costing.py`:

```python
def remove_from_pool(liquidated, avg_cost, quantity, unit_cost) -> tuple[Decimal, Decimal]
```

**Ecuación de conservación (exacta en las 3 ramas):**
`pool_after == pool_before − quantity×unit_cost + adjustment`
donde `unit_cost` = costo con que la cantidad ENTRÓ originalmente (ver H1) y `adjustment` va al P&L (mismo signo/semántica que PR-2: positivo = ganancia).

**Ramas** (L = liquidated, A = avg, q = quantity, u = unit_cost):

| Rama | Condición | new_avg | adjustment | Racional |
|---|---|---|---|---|
| 1. Remoción limpia | `L−q > 0` y `L×A − q×u ≥ 0` | `(L×A − q×u)/(L−q)` | `0` | Ponderado exacto — inverso del incorporate |
| 2. Valor insuficiente | `L−q > 0` pero `L×A − q×u < 0` | `A` (queda) | `(L−q)×A − (L×A − q×u)` = `q×(u−A)` | El pool no tiene el valor que la operación decía haber metido; el stock restante conserva su valuación y la diferencia va al P&L. **Evita crear stock a costo $0** (wart conocido) y avg negativo |
| 3. Remoción cruza a hueco | `L−q ≤ 0` | `A` (el hueco carga el avg vigente, misma semántica que incorporate) | `q×(u−A)` | Los kg que "no están" ya fueron vendidos; el pool queda en hueco valuado a A y la diferencia contra u va al P&L |

Nota: las ramas 2 y 3 comparten fórmula de adjustment (`q×(u−A)`) — la implementación puede unificarlas; se listan separadas porque las condiciones y ejemplos difieren.

**Ejemplos numéricos (para tests unitarios espejo):**

- **Rama 1 (el caso de la fuga, ahora exacto):** pool 150@8.000, remover 100@6.000 → new_avg = (1.200.000−600.000)/50 = **$12.000**, adj 0. Los 50 kg restantes cargan el valor que las ventas baratas no se llevaron. Conservación: 600.000 ✓ (los $100.000 ya no se evaporan — quedan EN el inventario, correcto porque la venta extrajo a $8.000 mezclado).
- **Rama 2:** pool 150@5.000 (=750.000), remover 100@10.000 (=1.000.000) → ponderado daría avg −$5.000 (inaceptable). new_avg = 5.000, pool_after = 50×5.000 = 250.000, adj = 100×(10.000−5.000) = **+500.000 al P&L**. Equación: 750.000 − 1.000.000 + 500.000 = 250.000 ✓.
- **Rama 3:** pool 20@10.000, cancelar compra de 100 que entró a 8.000 → L−q = −80, new_avg = 10.000, pool_after = −800.000, adj = 100×(8.000−10.000) = **−200.000**. Equación: 200.000 − 800.000 + (−200.000)… = −800.000 ✓. (El warning PR-3 avisa el hueco.)

**D1 (decisión de diseño, propuesta ya tomada en la tabla):** en rama 2 se eligió "avg queda + diferencia al P&L" sobre "avg 0" — evita stock a costo $0 (produce COGS $0 después, wart conocido del audit). QA puede refutar.

---

## 4. Consumidores (4 caminos, con sus trampas H1/H2)

### 4.1 `purchase.cancel()` — rama liquidada (`purchase.py` Step 5, hoy líneas ~669-700)

Por línea (mismo loop que hoy revierte): `remove_from_pool(L, A, line.quantity, u)` donde **u = contribución REAL de la línea**:

> **H1 (crítico, análogo del G1 de PR-2):** lo que la línea metió al pool al liquidar fue `quantity × adjusted_unit_cost + line.cost_adjustment` (precio + prorrateo de comisión #30, MÁS el ajuste de relleno de hueco si lo hubo). La remoción debe sacar ESE total, no `quantity × unit_price`. Motivo de incluir el fill-adj: al cancelar, el `cost_adjustment` de la línea **sale del P&L** (filtro `status='liquidated'` — semántica existente aprobada en PR-2, round-trip test), así que su valor también debe salir del pool o la conservación global no cierra.
>
> **Fuente del adjusted_unit_cost (clarificación QA, obligatoria):** el costo ajustado NO está en `PurchaseLine` (solo `unit_price` crudo + `cost_adjustment`) — se escribe en `InventoryMovement.unit_cost` al liquidar (`purchase.py:472`), y el cancel actual usa `line.unit_price` (`purchase.py:681`). Pasar `unit_price` al helper reintroduciría la fuga (el valor de la comisión quedaría en el pool). Regla: **leer el costo ajustado del `InventoryMovement` de la compra vía el mismo patrón deque-por-firma `(material, warehouse, quantity)` de liquidate/QW-B** — single source of truth, sin recompute drift. `u_total = im.unit_cost + line.cost_adjustment/quantity`. Nota legacy: los 2 movimientos con `unit_cost=0` de QW-B (#1074/#1295, sin remediar por decisión 2026-07-10) se removerían "según libros" — la ecuación cierra igual (el adjustment absorbe) y es lo coherente con no haber remediado. En ajustes y transformaciones H1 es trivial: `unit_cost` sí vive en la fila.

- Se elimina la llamada a `check_can_revert` (Step 2a) y a `revert_cost_change`.
- MCH nuevo **`purchase_cancellation`** (6º source_type) con `transaction_date = fecha de cancelación`, solo si `new_avg != old_avg` (patrón `sale_cancellation`).
- `adjustment` se persiste en columna nueva **`purchases.cancellation_cost_adjustment`** (header-level, suma de líneas — espejo exacto de `sales.cancellation_cost_adjustment`).
- Multi-línea mismo material: loop ve el pool corriente por línea (G2 aplica igual).

### 4.2 `inventory_adjustment.annul()`

- **increase**: `remove_from_pool` con `u_total = unit_cost + cost_adjustment/quantity` (H1 igual — el increase de PR-4 puede traer fill-adj). Sin `check_can_revert`, sin `revert_cost_change`.
- **decrease / zero_out / recount(−)**: hoy reingresan al avg VIGENTE en silencio (el primo hermano de la fuga). Pasan a **reingreso ponderado**: `incorporate_into_pool(L, A, qty, unit_cost=adjustment.unit_cost)` — el `unit_cost` persistido ES el avg al momento de la salida, exactamente el valor que salió. Puede rellenar hueco → adjustment.
- **recount(+)**: remoción como increase pero con u = adjustment.unit_cost (recount entra al avg de su momento — su inconsistencia `old_total` es pre-existente y NO se toca acá, plan #64 §10).
- MCH nuevo **`adjustment_annulment`** (si avg cambió). Columna nueva **`inventory_adjustments.annul_cost_adjustment`** — separada de `cost_adjustment` (PR-4) porque el annul es un EVENTO nuevo: el `cost_adjustment` original sale del P&L al anular (status), el `annul_cost_adjustment` ENTRA al P&L por `annulled_at` aunque el ajuste esté annulled (espejo de `cancellation_cost_adjustment` de ventas).

### 4.3 `material_transformation.annul()`

Dos direcciones, cada una con su helper:

- **Destinos** (por línea): `remove_from_pool` con `u_total = line.unit_cost + line.cost_adjustment/quantity` (H1).
- **Fuente**: **reingreso ponderado** `incorporate_into_pool(L, A, source_quantity, source_unit_cost)` — la fuente salió a `source_unit_cost` (avg de su momento, persistido), vuelve como ese valor. Puede rellenar hueco de la fuente.
- La merma nunca entró a ningún pool y `value_difference`/`waste_value` salen del P&L por status (semántica existente) — no participan de los helpers.
- MCH **`transformation_annulment`** para fuente y/o destinos que cambien avg. Columna nueva **`material_transformations.annul_cost_adjustment`** (header-level: suma de fuente + destinos — no hace falta per-line, el P&L es org-level G4).

### 4.4 `sale.cancel()` — SIN CAMBIOS

Ya es reingreso ponderado (PR-2). Su MCH `sale_cancellation` pierde el rol bloqueante (irrelevante: nadie más bloquea) y queda como audit trail. Verificar en tests que nada se rompe al convivir.

---

## 5. H2 — Balance histórico as-of: el MCH que ya no se borra

**La trampa más fina del plan.** `_get_inventory_as_of` (#41/#61) valúa el inventario al corte con el último MCH `transaction_date <= corte`. Hoy, cancelar BORRA el MCH de la liquidación → los cortes históricos ven "como si nunca existió" (doctrina #41, simplificación 735c2c3). Con append-only, el MCH original **sobrevive** → un corte ENTRE la liquidación y la cancelación vería el efecto de costo de una compra "que nunca existió" (cantidad excluida, costo incluido → inconsistente).

**Propuesta:** los helpers históricos filtran MCH cuyo **source op esté cancelled/annulled**, EXCEPTO los source_types de reversión (`sale_cancellation`, `purchase_cancellation`, `adjustment_annulment`, `transformation_annulment`) que son eventos válidos para siempre:

- Corte ANTES de la operación: no ve nada (igual que hoy) ✓
- Corte ENTRE operación y reversión: no ve el MCH original (op cancelada = nunca existió, doctrina #41) ✓
- Corte DESPUÉS de la reversión: ve el MCH de la reversión, cuyo `new_cost` == avg vivo real ✓ (con el rewind actual esto también cuadra, pero por borrado)

Implementación: EXISTS por source_type → tabla de estado (purchases/inventory_adjustments/material_transformations/sales).

**Dualidad del filtro por nivel (clarificación QA sobre Fallback 1, obligatoria):** el filtro NO es uniforme en los 3 niveles de `_get_inventory_as_of` — el Fallback 1 usa `previous_cost` del PRIMER MCH posterior al corte, y ahí la lógica se invierte:

- **Camino principal** (último MCH `<= corte`, usa `new_cost`): excluir MCH de ops cancelled/annulled, **exentar** los 4 source_types de reversión (regla original del plan).
- **Fallback 1** (primer MCH `> corte`, usa `previous_cost`): **incluir** los MCH de ops canceladas y **excluir los 3 tipos de reversión de Fase 5**. Racional: si el primer MCH posterior es la liquidación de una compra luego-cancelada, entre el corte y esa liquidación solo hubo eventos MCH-silenciosos (si no, habría un MCH antes) → el avg no cambió → su `previous_cost` == avg al corte, **evidencia válida**. En cambio el MCH de una reversión Fase 5 (`purchase_cancellation`) tiene `previous_cost` = avg justo antes de cancelar, que YA incluye la actividad del original oculto (la compra "que nunca existió") → **evidencia inválida** para el corte. Escenario que lo demuestra: liquidar en T−5 (MCH oculto por filtro principal), corte en T, cancelar en T+5 → sin la dualidad, el fallback tomaría el `previous_cost` del cancel-MCH (contaminado); con ella, salta al siguiente MCH real o cae a Fallback 2 (que ya filtra por status, #61). **Excepción (afinada en implementación): `sale_cancellation` SÍ se incluye en Fallback 1** — la venta que revierte nunca escribió MCH (extracción silenciosa), así que no hay "original oculto" que contamine: su `previous_cost` es evidencia válida del costo al corte. Además preserva byte a byte el comportamiento actual para los datos existentes (es el único tipo de reversión pre-Fase 5).
- **Fallbacks 2 y 3**: ya filtran por status del padre (#61) — sin cambio.

**Tests de oro H2 (dos):** (a) escenario liquidar→vender→cancelar, as-of en 3 cortes (antes/entre/después) == doctrina, y as-of(hoy) == balance vivo; (b) **dedicado a Fallback 1**: material cuyo ÚNICO MCH relevante al corte sea de una op cancelada (fuerza el fallback), en los 3 cortes — exigido por QA, es la zona del incidente Costa, sin hand-wave. Sin estos tests, `test_golden_parity_statement_vs_balance_detailed` y los de #41 no atrapan el drift (no cubren avg-post-cancel).

**Alternativa descartada:** flag `superseded` materializado en MCH (columna extra + backfill; el EXISTS es más simple y no requiere migración de datos).

---

## 6. P&L y conciliación

Bloque 3.8 gana 3 SUM (mismo campo `oversell_cost_adjustment`, org-level G4, timing G3 aplica igual):

- `purchases.cancellation_cost_adjustment` — `status='cancelled'`, por `cancelled_at` (espejo exacto del término de ventas)
- `inventory_adjustments.annul_cost_adjustment` — `status='annulled'`, por `annulled_at`
- `material_transformations.annul_cost_adjustment` — `status='annulled'`, por `annulled_at`

**D2:** el label frontend "Ajuste Costo por Sobreventa" ¿pasa a "Ajuste Costo por Sobreventa y Reversiones"? (campo backend NO cambia; solo el texto de la fila y el Excel). Propuesta: sí — con 7 fuentes el nombre viejo miente.

La conciliación de Rentabilidad por UN (#59, 5 líneas) NO cambia estructuralmente: el campo ya existe, solo crece su contenido. `test_reconciliation_residual_zero` debe seguir verde sin tocar.

---

## 7. Migración (1, escrita a mano)

- 3 columnas: `purchases.cancellation_cost_adjustment`, `inventory_adjustments.annul_cost_adjustment`, `material_transformations.annul_cost_adjustment` — `Numeric(15,2), nullable=False, server_default='0'` → **P&L histórico NO cambia al deploy** (mismo argumento de PR-2/PR-4).
- Comment de `material_cost_histories.source_type` → 8 tipos.
- ⚠️ **Revision ID ALEATORIO** (lección PR-4: los IDs hex "bonitos" del repo están minados — `a1b2c3d4e5f6` ya existía).
- Sin backfill: las 13 fugas históricas quedan como están (decisión no-remediación 2026-07-10).

## 8. Lo que NO cambia (invariantes para refutar)

| Invariante | Estado |
|---|---|
| I1 stock == transit + liquidated | Intacto (reversiones mueven cantidad igual que hoy) |
| I2 stock == Σ inventory_movements | Intacto (los movimientos de reversal se crean igual) |
| I3 avg ≥ 0 | **Garantizado por rama 2** (hoy el rewind también lo cumple, pero por suerte) |
| I4 avg == último MCH | **Se fortalece**: append-only puro, sin excepción de borrado |
| I5 conservación | **Se extiende a reversiones** (hoy solo cubre el camino feliz + PR-2/PR-4) |
| P&L histórico al deploy | Sin cambio (server_default=0) |
| DP | Fuera (sin inventario, #1) |
| Balance vivo actual | Sin cambio al deploy (las columnas nuevas nacen en 0; el comportamiento cambia solo para reversiones FUTURAS) |
| Warning PR-3 | Se mantiene |

## 9. Tests (estimado ~15-18 nuevos)

1. **Unitarios espejo del helper** (sin BD): ecuación de conservación en las 3 ramas + boundary L−q == 0 (paralelo exacto de `TestIncorporateIntoPool`).
2. **El caso de la fuga** (§1): la secuencia completa por API → el pool queda en $600.000 (50@12.000) y NADA en P&L (rama 1, adj 0) — los $100.000 quedan en inventario donde corresponden. Assert explícito contra el valor viejo ($500.000).
3. **Round-trips limpios == rewind**: cancelar/anular inmediatamente después (sin actividad entre medias) da EXACTAMENTE el mismo resultado que hoy (rama 1 con pool intacto == rewind). Paridad de regresión para los 4 caminos.
4. **H1**: cancelar compra con comisión Y fill-adjustment → la remoción saca `qty×adjusted + fill` y la conservación cierra; el fill sale del P&L y el cancel-adj entra.
5. **H2 golden**: as-of antes/entre/después vs doctrina y vs balance vivo (§5).
6. **Cancel ahora permitido**: compra liquidada + compra posterior liquidada (MCH posterior — hoy 400) → cancelar la primera pasa con 200 y conserva (el caso del 79%).
7. **Cancel de compra fuente transformada** (#40 superseded): pasa con 200, conserva, warning si hueco.
8. **Annul de decrease con avg movido entre medias**: reingreso al unit_cost de la salida, no al vigente (el primo hermano, ejemplo del reporte PR-4).
9. **Stress walk SIN restricciones**: se ELIMINAN los `confirmed_increases.clear()` y el walk gana `purchase_cancel`/`adj_annul` sin condiciones + I5 con los 3 términos nuevos. **Este es el guardrail estrella: si el walk pasa sin la regla de invalidación, el gap está cerrado de verdad.** Esperar re-tuning de semilla/pesos (los 400 de bloqueo desaparecen → más cancels efectivos).

## 10. Orden de entrega

**PR-5 único** (helper + 4 caminos + H2 + P&L + migración + tests) — **confirmado por QA**: evita el estado transitorio donde transformaciones seguirían borrando MCH mientras compras/ajustes hacen append. Si por tamaño se partiera igual (5a compras/ajustes, 5b transformaciones), **el filtro H2 va en 5a cubriendo los 8 source_types** (inocuo para paths aún no migrados: no hay MCH sobreviviente que filtrar). Sin acople tipo G5 con nada: self-contained sobre PR-2 (deployable en cualquier momento posterior al paquete). QA-gate antes de commit, un pytest a la vez.

**Notas de cierre acordadas con QA (no bloquean):** deprecar/eliminar `check_can_revert` y `revert_cost_change` (quedan sin callers) + actualizar el docstring de `record_cost_change` (referencia obsoleta al guard); docs al commitear: #40, #65 (rol bloqueante), #9, nota I4 en #64/#65 ("salvo que un revert borre" → append-only puro); cosmético adoptado: el movimiento de reversal de compra pasa a `unit_cost = adjusted` (hoy `line.unit_price`) — no se lee para costo, pero mejora la auditoría y el dato ya está en mano por el deque.

## 11. Puntos débiles auto-señalados (léanse con lupa)

1. **La semántica del cancel cambia visiblemente**: hoy "cancelar devuelve el promedio al número de antes" (cuando el guardián deja); después "cancelar saca el valor que la operación metió" — con actividad entre medias el avg resultante NO es el número de antes (ejemplo rama 1: $12.000, no $10.000). Es deliberado (el número de antes era una ficción que evaporaba plata), pero el liquidador puede notarlo. Comunicable con el mismo mensaje del Modelo L: "el inventario conserva el valor".
2. **Retirar el guardián elimina una fricción que también frenaba errores operativos** (cancelar cosas viejas por accidente). Mitigación posible (D3): mantener una CONFIRMACIÓN suave en frontend al cancelar operaciones con actividad posterior ("este material tuvo N movimientos desde entonces — el costo promedio se recalculará"). Opcional, no bloquea el plan.
3. **Rama 2/3 derivadas de la ecuación, no de doctrina contable externa** — igual que PR-2 (QA ya aceptó ese marco); los ejemplos numéricos están para refutar.
4. **H2 toca los helpers as-of** (#41/#61, zona del incidente Costa) — riesgo de regresión real; por eso test de oro dedicado + correr `test_balance_historico_fixes.py` completo.
5. Rounding: mismo ≤$0.005/kg pre-existente (Numeric 15,2 vs 15,4); tolerancias de tests iguales a PR-2/PR-4.
6. `recount` sigue sin arreglar su ponderación `old_total` (pre-existente, explícitamente fuera — no mezclar semánticas).

## 12. Preguntas abiertas (D1-D3)

- **D1** (§3): rama 2 = "avg queda + adj" vs "avg 0". Propuesta: avg queda.
- **D2** (§6): renombrar label frontend de la línea P&L. Propuesta: sí, "Ajuste Costo por Sobreventa y Reversiones".
- **D3** (§11.2): confirmación suave en frontend al cancelar con actividad posterior. Propuesta: v2, no en PR-5.
