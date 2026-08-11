# Informe post-código — Entrada sin proveedor (#93)

**Plan:** [plan-sac-entrada-sin-proveedor.md](plan-sac-entrada-sin-proveedor.md) v1.4 (🟢 GO sin condiciones).
**Estado:** código completo (backend + tests + frontend) **con los fixes de las pruebas de usuario
del 2026-08-11 incorporados** (§9). Los cuatro gates verdes sobre el árbol final: suite
**1549/1549** (incluye los 3 tests del hallazgo §11), parity sin divergencias nuevas, golden ×3 orgs **45/45 byte-idéntico** (6ª corrida),
`tsc` + build limpios. **Nada commiteado ni staged** (gate de QA).
**Pedido explícito de QA:** *"lo reviso con la lupa en los siete cambios del motor y en el helper
compartido de D20"* — §2 y §3 están escritos para esa lupa, con anclas de línea.

---

## 1. Qué se construyó (mapa de archivos)

| Pieza | Archivo | Qué |
|---|---|---|
| Migración única | `backend/alembic/versions/b8c9d0e1f2a3_sac_entrada_sin_proveedor.py` | G1/G2 data-gates, puente+backfill, `inbound_line_allocations`, `third_party_id` nullable, `reviewed_by/at`, `remission_number`, cols de línea + UNIQUE(order,material), `inventory_adjustments.inbound_order_id` (🔴 tabla compartida → golden), `service_tariffs.kg_per_unit`, backfill de status legacy, permiso `purchases.review` (sort 148) |
| Modelos | `inbound_order.py` (+`InboundLineAllocation`, `InboundOrderPurchase`), `inventory_adjustment.py`, `service_tariff.py`, `material_cost_history.py` (docstring A4: catálogo 12) | |
| Motor D7 | `services/inventory_adjustment.py` | decrease con `unit_cost_override` + fix W-1 del annul |
| Primitivas D14/D20 | `services/purchase.py` | `liquidate(commit=)`, `update(commit=)`, guard de cancel por puente, helper `_revert_liquidation_effects`, `unliquidate()` |
| Reportes | `services/reports.py` | `purchase_unliquidation` en MCH_FASE5_REVERSAL_TYPES; `inbound_discrepancy` en `mch_source_is_cancelled` |
| Servicio Entrada | `services/inbound_order.py` | captura sin proveedor, review, liquidate (reparto→N compras→descuadres→comisión, atómico), unliquidate, annul delegado, update por estado, listado column-driven + search por asignaciones |
| Endpoints | `api/v1/endpoints/inbound_orders.py` (+review/liquidate/unliquidate), `purchases.py` (`_inbound_origin_map` por puente) | |
| Schemas | `schemas/inbound_order.py` (reparto D14), `service_tariff.py` (kg_per_unit) | |
| Seed | `scripts/seed_sac_org.py` | rol `revisor_inventario` (R5) + tarifa `comision_green_loop` con `kg_per_unit=14` (idempotencia extendida con `same_kg` — sin eso el 14 jamás llegaría a prod) |
| Tests | `tests/test_sac_entrada_sin_proveedor.py` (39) + re-semantización de 4 suites + walk extendido | §6 |
| Frontend | captura sin proveedor + remisión, botón/permiso Revisar, **`InboundLiquidatePage`** (reparto con descuadre en vivo), detalle (tarjetas por proveedor, reparto por línea, Revertir Liquidación), Edit (líneas editables draft/reviewed), listado (tab Revisadas, "Varios (N)", acciones por estado), tipos/servicio/hooks/invalidación | §7 |

---

## 2. La lupa 1 — los siete cambios del motor

1. **`decrease(unit_cost_override=)`** ([inventory_adjustment.py:166-220](../../backend/app/services/inventory_adjustment.py#L166-L220)) — con override: `remove_from_pool(liquidated=previous_stock, avg, qty, override)` (#66), avg actualizado, `adjustment.unit_cost=override`, `adjustment.cost_adjustment` persistido. **Sin override: byte a byte el camino de las 7 orgs** (criterio 29, test endpoint-level: cero MCH nuevos, avg intacto, cost_adjustment 0). El param vive en la FIRMA del servicio, no en `DecreaseCreate` — el schema es contrato público y un precio en la merma manual re-abriría lo que #66 cerró.
2. **MCH `inbound_discrepancy`** ([inventory_adjustment.py:250-269](../../backend/app/services/inventory_adjustment.py#L250-L269)) — SIEMPRE que hay override (espejo del increase). Sin él, I4 ("avg == último MCH") revienta y `_get_inventory_as_of` valuaría cortes al avg viejo. `transaction_date = data.date` = **día de la liquidación** (D21, el caller lo fija). **A5**: es OPERATIVO — deliberadamente FUERA de `MCH_FASE5_REVERSAL_TYPES`.
3. **Fix W-1 del `annul`** ([inventory_adjustment.py:434+](../../backend/app/services/inventory_adjustment.py#L434)) — rama qty<0: `u_total = adjustment.unit_cost + (adjustment.cost_adjustment / qty)` (qty FIRMADO negativo → resta) y reingreso con `incorporate_into_pool`. Para decreases históricos `cost_adjustment=0` → álgebra idéntica a hoy (criterio 33, test); para decreases con precio en rama de hueco → round-trip EXACTO al pool original (criterio 20, test con los números del plan: $1.000 se queda en $1.000, no $3.700).
4. **Guard D17/A3 del `annul`** ([inventory_adjustment.py:442-466](../../backend/app/services/inventory_adjustment.py#L442)) — `inbound_order_id` O `transfer_id` seteados → 422 guía al módulo dueño, salvo `from_module=True` (cascadas internas: `transfer.annul` y `_revert_entrada_liquidation` lo pasan). Cierra también el hueco hermano de #84 (la merma de un traslado era anulable desde Ajustes — criterio 35, test).
5. **`purchase.liquidate(commit=)` y `purchase.update(commit=)`** ([purchase.py:358](../../backend/app/services/purchase.py#L358), [purchase.py:1162](../../backend/app/services/purchase.py#L1162)) — patrón #20/#75, aditivo puro (default True). La liquidación de la Entrada liquida N compras y sincroniza registradas dentro de UNA transacción.
6. **Guard de cancel por puente** ([purchase.py:644+](../../backend/app/services/purchase.py#L644)) — cualquier compra enlazada por `inbound_order_purchases`, **cualquier estado** → 400 "anule la liquidación desde la Entrada". Supersede D7b y la excepción del ciclo C: el deadlock no vuelve porque el annul de la Entrada ya no delega en cancel directo sino en unliquidate.
7. **Reportes** ([reports.py:2480](../../backend/app/services/reports.py#L2480), [reports.py:2505](../../backend/app/services/reports.py#L2505)) — `purchase_unliquidation` entra a `MCH_FASE5_REVERSAL_TYPES` (D20b: el checkpoint original `purchase_liquidation` PERMANECE — `mch_source_is_cancelled` NO se extiende a compras: la compra queda `registered`, no cancelada); `inbound_discrepancy` entra a `mch_source_is_cancelled` vía EXISTS sobre el ajuste `annulled` (el as-of deja de ver el checkpoint cuando el ajuste se anula). Criterio 32 (estabilidad as-of ante liquidación tardía) tiene test con snapshot byte a byte de balance-sheet en 2 cortes.

**Nota de paridad #83 (encontrada por el test, corregida en código):** mi refactor del cancel pasaba
`reason_label` en inglés al auto-annul del accrual de recolector — el original escribía
`"Cancelación compra #N"`. Restaurado el texto español ([purchase.py:782](../../backend/app/services/purchase.py#L782)); el
test de ciclo D volvió a verde sin re-semantizar el assert.

---

## 3. La lupa 2 — el helper compartido de D20

**`_revert_liquidation_effects(db, purchase, org, user, *, mch_source_type, to_transit, reason_label, warning_event) -> (residual, warnings)`**
([purchase.py:853](../../backend/app/services/purchase.py#L853)). Dos callers, cero copias nuevas del código delicado:

| | `cancel()` (liquidada) | `unliquidate()` |
|---|---|---|
| mch_source_type | `purchase_cancellation` | `purchase_unliquidation` |
| to_transit | False (stock sale del sistema) | **True** (liquidated→transit; la compra vuelve a `registered` = tránsito por definición, cero movimiento de reversa) |
| Movimiento inventario | reversa física −qty | **ninguno** (el de la compra original queda; deja de contar en cortes por `liquidated_at=NULL`, #61c) |
| Después del helper | status=cancelled + elección #63 pago enlazado | status=registered, `liquidated_at/by=NULL`, `line.cost_adjustment=0`, **warning** informativo del pago enlazado (sin elección — no es cancelación) |

Dentro del helper (idéntico para ambos): remoción ponderada por deque-de-firma con `u_total` del
fill (#66 H1), MCH SIEMPRE a `business_today()`, reversa de saldo proveedor + comisionistas +
retenciones (`reverted_at`) + auto-annul del accrual de recolector (filtro `source_type`, D-02), y
warnings de hueco por material con estado FINAL.

**En la Entrada** (`_revert_entrada_liquidation`, compartido por unliquidate y annul-de-liquidada):
residual≠0 de las N compras → `order.annul_cost_adjustment` (+warning, precedente micro-gap E2 —
entra al P&L solo si la orden se anula después), annul de ajustes de descuadre con `from_module=True`
(round-trip W-1), annul del accrual POR ENTRADA (`source_id=order.id`, `purchase_id NULL`).
El reparto **se conserva** (criterio 22: re-liquidar reusa las mismas N compras por firma
cuantizada — cero consecutivos quemados, test lo clava contra `MAX(purchase_number)`).

**D14 atomicidad** (criterio 27, test): la validación del recolector no-service_provider dispara 422
DESPUÉS de liquidar las N compras dentro de la transacción sin commit → rollback total, la entrada
sigue `reviewed`, saldos en 0, stock en 0.

---

## 4. Desviaciones y decisiones tomadas en código (para el veredicto de QA)

1. **`remission_number` — columna nueva no listada en el plan**: D12 exige remisión en la captura
   pero el modelo de datos del plan no le daba casa. NO se reusó `invoice_number` (#87 acaba de
   pagar el costo de un campo con dos semánticas). Editable siempre (criterio de `notes`).
2. **`reviewed_by`/`reviewed_at`** — auditoría de la revisión (D10 la implica; el plan no la
   enumera). Costo: 2 columnas nullable en tabla SAC-only.
3. **Permiso del `unliquidate` = `purchases.cancel`** — es una reversa (familia del cancel), no una
   liquidación. Alternativa era un permiso nuevo; se descartó por D10 ("cero permisos nuevos" salvo
   `purchases.review`). QA puede objetar.
4. **✅ RESUELTO EN EL CICLO — Retenciones en la liquidación de Entrada (addendum post-veredicto,
   2026-08-06)**: QA lo reclasificó de gap a **regresión** (canal único #80 + liquidación atómica
   D14 = el bloque de PurchaseLiquidatePage quedaba inalcanzable en SAC) y Daniel confirmó: *"sí
   les descuenta, pero no a todas, es opcional"*. Implementado como bloques **OPCIONALES POR
   PROVEEDOR**:
   - **Schema**: `InboundLiquidateRequest.supplier_retentions?: [{third_party_id, retentions:
     PurchaseRetentionCreate[]}]` — reusa el bloque de #79 tal cual (validaciones ICA/municipio
     incluidas); ausente = byte a byte (data-gate D9).
   - **Servicio** ([inbound_order.py](../../backend/app/services/inbound_order.py), fase plan D14):
     cada bloque debe apuntar a un proveedor DEL reparto (422 con nombre) y sin duplicar proveedor;
     el pass-through a `purchase.liquidate(retentions_data=...)` hereda #79 completo — flag-guard,
     tope Σret < total (dispara TARDE y D14 lo cubre: rollback total, test), matching H4,
     get-or-create de entidades, neto al proveedor.
   - **D20 gratis**: el helper compartido YA revertía retenciones (purchase.py:977-989, inverso
     exacto + `reverted_at`) — unliquidate→re-liquidar hace round-trip exacto de proveedor Y
     entidad, en la MISMA compra (test).
   - **Display**: `InboundPurchaseSummary.retentions_total` (vivas; `selectinload` = 1 query por
     página, R2 respetada) → "Retenciones · Neto" en las cards del detalle.
   - **UI**: filas de retención en las cards por proveedor de InboundLiquidatePage (Select del
     catálogo #79 + precálculo `% × subtotal del proveedor` vivo, editable con "Sugerido"
     restaurable, neto por card, totales en el sticky). Deviación menor: sin quick-create de
     tarifas inline (vive en Tesorería → Retenciones y en la compra directa) — hint en la card.
   - **5 tests nuevos** (`TestRetencionesEntrada`): neto opcional por proveedor, 422 con nombre +
     atomicidad, duplicado, tope tardío con rollback total, round-trip completo con ICA.
   - **Bonus del addendum**: input de `kg_per_unit` en Config → Tarifas (faltaba — el valor era
     configurable solo por API) + 2 tests (`TestTarifaKgPerUnit`: versionado y 422 en otros
     códigos). Golden RE-CORRIDO post-addendum: 45/45 byte-idéntico, 0 diffs.
   - **🔧 Fix del BLOQUEANTE de la re-lupa QA (mismo día)**: el estado de cuenta emitía las DOS
     filas de retención de una compra re-liquidada (vieja revertida + nueva viva) como
     `confirmed` sin contra-evento — el disparador era `purch.status == "cancelled"` y tras
     re-liquidar la compra está `liquidated` → $1.400 mostrados donde el saldo tiene $700, en
     proveedor Y entidad (rompía el invariante #55/#61 sobre el camino que el addendum vende
     como remediación). **Fix exactamente el prescrito por QA**
     ([money_movements.py](../../backend/app/api/v1/endpoints/money_movements.py), sección 2c,
     ambos lados): el status del evento y el disparador del contra-evento siguen a la FILA
     (`ret.reverted_at`), no al status de la compra — fila viva → `confirmed` (mueve saldo);
     fila revertida → evento `cancelled` + reversa `annulled` fechada en `reverted_at`
     (par display-only que neta a cero, descripción "revertida (des-liquidación)"); compra
     cancelada → byte a byte con hoy (el cancel SIEMPRE estampa `reverted_at` desde #75, y su
     par conserva el texto "cancelada (reversa)"). NO se filtró `reverted_at IS NULL` en las
     queries — habría borrado el rastro de auditoría de canceladas, como advirtió QA.
     **Test `test_statement_parity_after_reliquidation`** (ciclo completo en AMBOS lados:
     saldo corrido == vivo, exactamente 1 confirmada, par que neta, descripción de corrección)
     — **verificado contra el código con bug: falla** (la paridad de saldo revienta). Suites
     de statement verdes tras el fix: retenciones #75 (17, incl. cancelada→cero) + balance
     histórico #61 (test de oro) + money movements = 204. Golden re-corrido (3ª vez): 45/45.
     **Calibración de evidencia (QA)**: el golden NO cubre la rama de retenciones — las 3 orgs
     prod no tienen `kg_ledger_enabled` ni filas en `purchase_retentions`; sus `tp_statement`
     ejercitan la maquinaria compartida (`_evt`, orden, saldo corrido), que es lo que confirma.
     La rama descansa en los 17 tests de #75 + el test de paridad nuevo.
     **Consecuencia declarada (QA, no es cambio)**: las retenciones de una Entrada ANULADA
     desaparecen del statement (el annul des-liquida primero → `liquidated_at=NULL` → la query
     las excluye), coherente con #41 y con el trato de las cantidades; una compra cancelada por
     fuera de una Entrada sí muestra su par. Documentado también en CLAUDE.md junto a la regla.
5. **Fix fuera de alcance estricto** en `endpoints/inbound_orders.py` (detalle): el
   `collector_commission_total` legacy leía SOLO `order.purchase_id` → la comisión POR ENTRADA de
   #93 (purchase_id NULL) jamás se mostraría. Reescrito a UNA query por FUENTE
   (`source_type='collector_commission' AND source_id=order.id`) — cubre legacy y nuevo (ambos
   estampan `source_id=orden`). Test nuevo en ciclo D lo cubre.
6. **Ciclo D re-anclado a compras DIRECTAS**: el camino purchase-level de #83 (param
   `collector_commission` en `purchase.liquidate`) sigue vivo y se prueba con compras sin entrada;
   el camino por-entrada (D11) se prueba en la suite nueva y en 2 tests de ciclo D re-semantizados.
7. **Walk — artefacto de test, no del motor**: la acción nueva `adj_decrease_priced` llama el
   servicio directo sobre `db_session`, cuya transacción de solo-lectura llevaba abierta desde el
   primer chequeo → `func.now()` (transaction_timestamp) estampaba el MCH con la hora de INICIO del
   walk y I4 fallaba en falso. `db_session.rollback()` antes de la llamada (comentado en el test).
   En producción cada request abre transacción fresca — verificado que el path real no lo sufre.
8. **Escala preexistente `InventoryMovement.quantity = Numeric(10,3)`**: cantidades con 4º decimal
   pierden el último dígito en el bucket transit/liquidated (0.0040 en el test estrella con
   78.3077×13). NO es de #93 — el test usa cantidades a 1 decimal y lo documenta. Deuda declarada,
   no se toca en este ciclo (columna compartida, las 7 orgs).

---

## 5. Migración y runbook de deploy

- **G1**: entradas tipo compra legacy con derivada `registered` → `RuntimeError` con la lista de
  números — liquidarlas o anularlas via UI ANTES del deploy. **Medido contra réplica fresca de
  prod 2026-08-06 (§8): 0 filas — SAC aún no captura entradas, el paso NO aplica hoy.** Se deja
  documentado por si Johana captura entre este informe y el deploy: re-verificar con el query de
  G1 en el pre-deploy (nota de QA: §8 manda sobre la estimación "~2 días de datos" que decía esta
  línea).
- **G2**: líneas duplicadas por material → `RuntimeError` (el UNIQUE nuevo no entra con datos sucios).
- Backfill: puente desde `inbound_orders.purchase_id` (columna queda INERTE); status legacy
  `cancelled→annulled | resto→liquidated`.
- Verificación pre-deploy: SQL "solo SAC en inbound_orders" + backup completo (calco §7.1 de #89).
- Downgrade: ventana de reversa SOLO antes de la primera captura sin proveedor (documented en el
  propio downgrade — falla con razón si hay NULLs nuevos).
- Aplicada en dev (5434) con round-trip upgrade→downgrade→upgrade verificado.
- 🔴 `inventory_adjustments.inbound_order_id` toca tabla compartida → **golden ×3 orgs = gate duro**
  (D18), igual que `is_receiving` en ciclo B.

## 6. Tests

- **`test_sac_entrada_sin_proveedor.py` — 60/60 verdes** (39 del plan + 7 del addendum
  retenciones/kg_per_unit + 1 del fix del bloqueante de QA — ver §4.4 — + **5 de la superficie
  de detalle** que abrieron las pruebas de usuario, ver §9):
  captura (5), revisión (4, incl. RBAC positivo con rol custom y negativo con viewer real),
  liquidación (9: 13 proveedores consecutivos + bandeja una vez, sobrante/faltante a referencia,
  excepción de precio, truncamiento sin neteo D5, intención D8, tolerancia avisa/no bloquea,
  fail-before-writes), invariantes (2: **estrella avg 1-vs-13** y degradación −q·A en hueco),
  reversas (8: round-trip completo de unliquidate + re-liquidación con mismos consecutivos,
  unliquidate-tras-venta avisa sin bloquear, cancel individual 400, annul de liquidada, D17 ×2,
  **criterio 20** y **criterio 33**, D20b MCH), atomicidad + comisión D11 (2), no-regresión (3:
  criterio 28, criterio 29, **criterio 32** as-of estable), búsqueda 1:N (3),
  **retenciones addendum (5)**: neto opcional por proveedor con entidad al peso, 422 nombrado +
  nada persiste, bloques duplicados, tope tardío con rollback D14 total, round-trip
  unliquidate→re-liquidar con ICA H4; **tarifa kg_per_unit (2)**: versionado append-only y 422
  fuera de comision_green_loop; **superficie de detalle (5, §9)**: descuadres con signo de
  negocio, ausentes en el listado (detail-only por costo), `annulled` tras des-liquidar,
  retenciones vivas + último lote revertido para la precarga, y precarga que ve UNA sola fila
  tras re-liquidar (el mismo modo de falla del bloqueante de QA, ahora cubierto en el detalle).
- **Re-semantización**: `test_inbound_orders.py` 39/39, `test_sac_ciclo_b.py` 25/25,
  `test_sac_ciclo_c.py` 20/20 (display_status gana "reviewed" en el guardrail de paridad),
  `test_sac_ciclo_d.py` 20/20 (+1 test nuevo del total por entrada).
- **Stress walk extendido** (`test_avg_cost_model_l.py` 36/36): acciones `adj_decrease_priced`
  (motor D7 pelado) y `adj_annul_priced` (round-trip W-1) con asserts de sanidad ≥2/≥1; I4/I5
  cubren el MCH nuevo y el cost_adjustment por construcción.
- Suites del motor tocadas de refilón: purchases+model L (104) y transfers (6) verdes tras la
  factorización.

## 7. Frontend

- **Captura**: sin tercero ni factura en tipo compra (la nota lo explica), remisión en ambos tipos,
  precio de línea relabel "Precio (ref.)".
- **`InboundLiquidatePage`** (ruta `/inbound/:id/liquidate`, guard flag+`purchases.liquidate`):
  reparto por línea con proveedores/cantidad/precio, **descuadre en vivo** con semáforo por
  tolerancia de la org, precio de referencia que se auto-llena con el primer precio digitado
  (respuesta de Daniel) y se puede editar, checkbox D8 "sin proveedor (intencional)", líneas de
  truncamiento ("material que la báscula no vio"), comisión de recolector con sugerido
  tarifa × base (kg + unidades×`kg_per_unit`), factura POR PROVEEDOR en el resumen de compras a
  nacer, validación por línea con mensajes, y **retenciones OPCIONALES por proveedor en la misma
  card** (addendum §4.4: Select del catálogo #79, precálculo `% × subtotal del proveedor` vivo y
  editable con "Sugerido" restaurable, neto por card, total de retenciones en el sticky).
- **Detalle**: estados nuevos (borde y badge Revisada), botones por estado (Marcar Revisada /
  Liquidar / Revertir Liquidación / Anular con textos honestos), tarjetas por proveedor (con
  "Retenciones · Neto" cuando las hay), reparto y descuadre por línea, remisión y "Revisada por".
  Legacy 1:1 conserva su flujo (link a la derivada).
- **Config → Tarifas**: input "Equivalencia kg por unidad" (solo comisión Green Loop), columna en
  la tabla e historial con la equivalencia — el 14 deja de ser editable solo por API.
- **Listado**: tab Revisadas con badge propio, acciones Revisar/Liquidar según estado y tipo,
  tercero "Varios (N)" desde el reparto, total = Σ compras vivas al liquidar.
- **Edit**: líneas/fecha/precio-ref editables en draft/reviewed (respuesta 4 — corregir báscula);
  liquidada solo cabecera; factura oculta en compra nueva; remisión editable.
- `tsc` limpio + build de producción verde. Verificación mobile 390px pendiente de las pruebas de
  Daniel (patrones del repo aplicados: FormLineGrid, w-full sm:w-auto, sticky bottom, grids 1→N).

## 8. Gates (estado al cierre del informe)

- Suite completa backend: **1538 passed, 0 failed en corrida única (24:47) sobre el árbol final**
  — incluye el addendum de retenciones, el fix del bloqueante de QA y los 5 tests nuevos de la
  superficie de detalle (§9). Historia: la corrida completa previa (33 min) encontró
  **9 fallos, todos en `test_sac_ajustes_0803.py`** — la suite de #87 había quedado FUERA del
  barrido de re-semantización (creaba entradas tipo compra con proveedor y esperaba la derivada
  al capturar). Re-semantizada al modelo #93 con cero cambios de código de producción:
  factura de captura → 422 con guía; factura por proveedor en el reparto → aterriza en la
  derivada (y NULL en header/columna del inbound); "factura tardía" = des-liquidar →
  re-liquidar (el re-sync por firma la estampa en la MISMA compra, mismo número); rama legacy
  1:1 probada simulando el `purchase_id` que deja el backfill; propagación de placa probada
  **1:N** (2 proveedores, ambas compras) + placa vigente-al-liquidar. 18/18 verdes ×2 corridas.
  El resto de la suite (1516) pasó en la corrida completa con el mismo código de producción.
- Parity check (5433): **ejecutado post-suite sobre el árbol final — cero divergencias nuevas**;
  quedan solo las 4
  cosméticas de #87 (rendering de CHECKs preexistentes; el arreglo declarado allí sigue siendo
  normalizar el comparador, no ampliar baseline). Las tablas/columnas/constraints de #93
  quedaron en paridad exacta migración↔modelos.
- Golden ×3 orgs prod: **EJECUTADO 2026-08-06 — 45/45 capturas byte-idénticas, 0 diffs reales,
  0 claves aditivas — RE-CORRIDO tras el addendum de retenciones, tras el fix del bloqueante de QA
  y una CUARTA vez tras los fixes de las pruebas de usuario (2026-08-11), siempre 45/45**
  (evidencia: `docs/planes/evidencia-golden-2026-08-06-entrada-93/`). La corrida 4 declara su
  protocolo en la evidencia: mide **solo el delta de código** (BEFORE = worktree de `origin/main`
  2c13f02, verificado idéntico a develop commiteado; AFTER = árbol de trabajo; **misma BD** para
  ambos, sin re-replicar prod — así no se destruyeron los datos de prueba de Daniel).
  BEFORE = `origin/main` 2c13f02 (= prod `deploy-2026-08-06-1340`) sobre réplica fresca de prod;
  AFTER = develop con la migración `b8c9d0e1f2a3` aplicada a esa réplica. Bonus del ensayo con
  datos reales: **los gates G1/G2 dieron 0 filas en prod** (SAC aún no tiene inbound_orders) —
  la migración corre limpia al deploy, sin acciones previas de runbook.
- Seed SAC: rol revisor + tarifa 14 listos; corre en prod como provisión idempotente post-deploy.
- Comunicación al cliente ANTES del deploy: truncamiento no se compensa entre materiales (D5) +
  mostrar a Johana el flujo revisar→liquidar (R8).

## 9. Pruebas de usuario con Daniel (2026-08-11) — hallazgos y fixes

Recorrido guiado paso a paso sobre dev con datos SAC: captura → revisar → liquidar (2 proveedores
+ retención + comisión) → estado de cuenta → des-liquidar → re-liquidar → anular → P&L. **El flujo
completo funcionó de punta a punta**; los hallazgos son de superficie, con dos excepciones que
merecen quedar escritas.

### 9.1 Los dos bloqueantes que ningún gate atrapó

| # | Síntoma | Causa | Por qué pasó el gate |
|---|---|---|---|
| 1 | **Pantalla en blanco al liquidar** (rompía TODA liquidación) | `supplierSummary` (useMemo) quedó *después* de los `return` condicionales de carga → "Rendered more hooks than during the previous render" | `tsc`, `build`, 1533 tests y golden **no ejecutan la pantalla**. El repo **no tiene ESLint configurado** (`npm run lint` no corre) — `react-hooks/rules-of-hooks` lo habría marcado al escribirlo |
| 2 | **"NaN kg repartidos"** en el resumen por proveedor | FastAPI serializa `Decimal` como **string**; el tipo TS decía `number` → `acc + a.quantity` concatenaba texto | Mismo motivo: es un defecto de *runtime del navegador*, invisible para el typechecker (el tipo miente) y para el backend (que serializa bien) |

**Recomendación con nombre propio**: montar ESLint con `react-hooks/rules-of-hooks` como ciclo
corto propio. El primer bloqueante es exactamente la clase de bug que esa regla existe para
prevenir, y hoy la única red que tenemos es que alguien abra la pantalla.

*(Nota de método: tras arreglar el NaN el usuario seguía viéndolo en pantalla. En vez de declarar
el fix bueno, se diagnosticó HMR de Vite preservando estado stale y se pidió recarga dura — se
confirmó resuelto. Vale como recordatorio de que "lo arreglé" no es lo mismo que "lo verifiqué".)*

### 9.2 Los 9 fixes acordados

Backend (superficie de **solo lectura**; ningún camino de escritura cambió):

- **Descuadres en el detalle** — `InboundOrderResponse.discrepancy_adjustments` (detail-only, 1
  query; el listado devuelve `[]` por costo) con `total_value` **firmado por el negocio**
  (+ ganancia / − pérdida) en vez del `|valor|` que guarda la tabla. Antes había que ir a Reportes
  para saber si la entrada ganó o perdió.
- **Retenciones visibles y precargables** — `InboundPurchaseSummary.retentions[]` + helper
  `_last_retention_batch`: **vivas** si las hay, si no el **último lote revertido**. Así
  re-liquidar precarga lo que se aplicó en vez de exigir memoria; y expone UNA fila, no dos —
  el mismo modo de falla del bloqueante que encontró QA en el estado de cuenta.
- **Mensaje del candado** — el 422 al intentar anular el ajuste de descuadre desde Ajustes ahora
  nombra la entrada (`Entrada #N`) y usa **el verbo del botón** ("Revertir Liquidación"); decía
  "anule la liquidación", que manda a buscar un botón que no existe.
- **Cantidades del warning** — `f"{abs(disc).normalize():f}"` + unidad del material: el toast decía
  `10.0000` donde debía decir `10 unidad`.

Frontend:

- Resumen por proveedor **por unidad** (`kg` y `unidad` no se suman — convención #54).
- Etiquetas `purchase_retention` / `purchase_retention_cancellation` en el estado de cuenta
  (aparecían crudas, en inglés; el mapa único alimenta pantalla, PDF y Excel).
- Hipervínculos a estado de cuenta en recolector y proveedores del detalle.
- **Unidad dentro del input de cantidad** en captura/edición: en desktop el label se oculta de la
  2ª fila en adelante (`lineLabelClass`) y kg vs unidad dejaba de verse.
- El mensaje de "falta precio de referencia" **explica para qué se usa** (valorar lo que entra
  como ganancia) — marcar "sin proveedor" y seguir bloqueado sin saber por qué desconcierta.

### 9.3 Diferido con criterio (no son deuda silenciosa)

- Warning ámbar vs error rojo son visualmente indistinguibles en la pantalla de liquidación; y el
  estado inicial arranca en rojo antes de que el usuario toque nada. Cosmético, no bloquea.
- Descubribilidad de la factura por proveedor (está en la card del proveedor, se encontró
  preguntando).
- **Orden de captura del reparto** (material→proveedores, como está hoy, vs proveedor→materiales):
  el modelo de datos soporta ambos **idénticamente** (`inbound_line_allocations` es una lista de
  triples), así que es una decisión de UI reversible. Daniel la está consultando con Johana; si
  sus papeles de origen vienen por proveedor, conviene invertirlo.

### 9.4 Confirmaciones de negocio obtenidas en la sesión

- **Retenciones de una Entrada anulada desaparecen del estado de cuenta** → *"Aceptarlo — coherente
  con 'lo cancelado nunca existió' (#41), que es la doctrina del sistema"*. Queda como decisión
  explícita, no como efecto colateral.
- La tarifa de **14 kg/unidad** de Green Loop se vio funcionando en la comisión sugerida
  ($265.000) y ya es editable desde Config → Tarifas.
- Rastro en P&L verificado en pantalla: +$80.000 de ganancia por sobrante, −$265.000 de comisión,
  neto −$185.000.

## 10. Segunda ronda de pruebas de usuario (2026-08-11, tarde)

Daniel revisó la pantalla de liquidación con ojo de operación y encontró algo que va más allá
de la superficie: **el canal único (#80) dejó inalcanzables CUATRO campos de
`PurchaseLiquidateRequest`, no uno.** QA nombró las retenciones; la barrida correcta era enumerar
el schema completo.

| Campo | Estado antes de esta ronda |
|---|---|
| `retentions` | ✅ resuelto (addendum §4.4) |
| `collector_commission` | ✅ ya estaba (#83) |
| `immediate_payment` + `payment_account_id` | 🔴 inalcanzable → **resuelto acá** |
| `commissions` (comisiones y fletes #30/#70) | 🔴 inalcanzable → **diferido**, Daniel lo consulta en la reunión |

**Lección de método**: cuando QA reclasifica un gap como regresión, el arreglo no es el campo que
nombró — es *la clase entera*. Acá la clase era "todo lo que el schema de liquidación de compras
ofrece y el canal único escondió".

### 10.1 Pago de contado por proveedor

`InboundLiquidateRequest.supplier_payments` = bloques opcionales `{third_party_id, account_id}`,
misma forma que las retenciones porque es la misma pregunta de negocio: *a unos se les paga de
contado y a otros no*. **El monto no viaja** — `purchase.liquidate()` paga el NETO (Σlíneas − Σret,
#75), así que no puede desalinearse del saldo del proveedor. Validación en la fase de plan
(proveedor del reparto, sin duplicar, cuenta activa de la org) → falla antes de escribir.

🔴 **Candado anti doble pago (el riesgo que abre esta feature)**: des-liquidar **no anula** el pago
enlazado — queda como anticipo del proveedor (#16/#63, "Liquidación ≠ Pago"). Sin candado,
re-liquidar marcando contado otra vez pagaría **dos veces**. Ahora un 422 nombra el monto vivo y
guía: liquidar sin contado, o anular ese movimiento en Tesorería. Rollback total lo respalda (D14).
Test dedicado con el ciclo completo liquidar → revertir → re-liquidar.

### 10.2 El tercero Willard fuera del reparto

#80 decidió que el titular de la cuenta kg **no** es proveedor de compra ("lo Willard nunca es
compra", Q-04). Esa exclusión vivía en el selector de la **captura**; cuando #93 mudó el proveedor
a la **liquidación**, no viajó — y nunca tuvo defensa de backend (el guard existente solo protege
el lado Willard). Ahora: filtro en el selector + **422** con el nombre del tercero.

Distinción que importa y que la UI mezclaba: **el MATERIAL sí puede venir por compra** si está
marcado `compra_regular` (los "ambos canales" de Q-04 — BAT-G1 es uno). Lo exclusivo por canal es
el **tercero**, no la referencia. El guard es por tercero, y hay test de ambos lados.

Alcance: aplica **solo al camino de la Entrada**. `purchase.create` directo no cambia → datos
existentes intactos y las otras organizaciones ni se enteran (no tienen cuentas kg).

### 10.3 Hora real de la liquidación

*"¿Por qué la liquidación no tiene hora?"* — porque `liquidated_at` es **fecha de negocio**
(mediodía UTC), que es por donde cortan los reportes, y el instante del clic no se persistía. #87
había quitado la hora de ahí justamente porque imprimía **"07:00 a. m."**, el mediodía UTC
traducido a Bogotá: una hora inventada que vivió en producción.

Nueva columna `inbound_orders.liquidated_ts` (migración `c9d0e1f2a3b4`, aditiva nullable) con el
instante real. Va acá y **no** en purchases/sales/double_entries —la deuda declarada en #87, que
sigue abierta— porque `inbound_orders` es tabla **exclusiva de SAC**: cero filas en las 3
organizaciones cliente, cero riesgo en el golden. Se limpia al des-liquidar y se re-estampa al
re-liquidar. Helper `formatTime` nuevo, con la advertencia en su docstring de no aplicarlo jamás
sobre un `BusinessDate`.

### 10.4 Detalle por material en las cards

Cada card de "compras que van a nacer" lista ahora `CÓDIGO · cantidad × precio` por material,
además del total. Sin eso, Johana no podía verificar **qué** le está comprando a cada proveedor sin
volver a leer el reparto de arriba. Client-side, cero queries.

### 10.5 Re-semantización de tests (cero cambios de producción)

El guard de Willard rompió 4 tests de #87 y #82 que usaban al titular de la cuenta kg como
proveedor de compra **por comodidad** — el sujeto de esos tests era la factura, la placa o el
filtro, no el tercero. Se separaron los roles con fixtures propias (`sup_regular` en
`test_sac_ajustes_0803.py`, `willard_holder` en `test_sac_ciclo_c.py`). Que hayan fallado es
evidencia de que el guard funciona: probaban una combinación que el negocio no permite.

### 10.6 Materiales "Sin clasificar" que no lo eran + reset de la SAC de dev

Daniel: *"¿por qué tenemos materiales sin clasificar si te pasé el listado completo clasificado?"*
Su hipótesis —"quedaron materiales creados por defecto antes del listado"— era exacta, y el
mecanismo tenía dos capas:

1. **Causa raíz**: los 19 códigos viejos (`BAT-1..5`, `DROSS-MOTO`, `JAMICHE`, `SEC`, `CHATARRA`…)
   que el seeder **desactiva** en modo provisión (soft delete, regla sin-DROP, #28) y que nunca
   tuvieron perfil kg.
2. **Por qué se veían**: `GET /materials` no filtra por estado cuando el cliente no lo pide, y la
   página Materiales (kg) los listaba junto a los vivos → badge "Sin clasificar", indistinguible de
   trabajo pendiente real. **Fix**: la página filtra `is_active`. Un material fuera de servicio no
   se clasifica.

**Reset de la org SAC en dev** (`seed_sac_org.py --apply --reset`, guard local intacto): quedó con
37 materiales, los 37 clasificados y **cero inactivos**. Ojo con la semántica: `--reset` hace
**soft delete de la org** y crea una nueva — la vieja sigue en la BD con `is_active=false`, así que
cualquier query por `organizations.name` sin filtrar estado cuenta **las dos** (me pasó al
verificar). El ID de org cambia: hay que re-seleccionarla en el header.

**Proveedores de prueba**: `THIRD_PARTIES_LOCAL` (3 proveedores de material) se siembra **solo si
`api.is_local`**, mismo criterio que el guard de `--reset` — producción no acumula terceros
ficticios. Hacían falta porque el reparto es multi-proveedor por naturaleza y **Willard S.A. ya no
sirve para probarlo**: el guard de §10.2 lo rechaza. Total en dev: 4 proveedores de material.

---

## 11. Hallazgo fuera del alcance de #93 — el soft delete de organizaciones no se aplicaba

**⚠️ Este fix NO pertenece a #93 y debe ir en su propio commit** (toca `services/organization.py`,
código compartido por las 7 organizaciones). Queda documentado acá porque salió de las mismas
pruebas.

**Síntoma**: tras `seed_sac_org.py --reset`, el selector de organizaciones mostraba **dos "SAC"**.
La causa no era el seeder: `--reset` hace soft delete de la org y crea otra, que es su contrato.

**El bug**: el filtro `Organization.is_active` estaba en la rama de **superusuario**
([organizations.py:83](../../backend/app/api/v1/endpoints/organizations.py#L83)), en el GET
individual ([organizations.py:181](../../backend/app/api/v1/endpoints/organizations.py#L181)) y en
`_build_superuser_context` ([deps.py:147](../../backend/app/api/deps.py#L147)) — pero **faltaba en
las dos funciones que sirven al miembro normal**:

1. `get_user_organizations` → la org de baja seguía en su selector, para siempre.
2. `get_user_role_in_org` → y quitarla del selector no habría bastado: el `org_id` vive en el
   `authStore` y en los deep-links, así que el miembro **seguía operando dentro de una organización
   dada de baja**. Esta es la mitad grave.

O sea: el soft delete de #29 era efectivo contra superusuarios y **inerte contra los miembros**, que
son justamente quienes usan el sistema.

**Alcance del arreglo**: dos `WHERE` (uno de ellos con un `join` a `organizations`). Verificado
contra la réplica de producción: **no hay ninguna organización inactiva** en las 3 orgs cliente, así
que el cambio no le quita una entrada a nadie. El endpoint `/organizations` no está entre las 15
capturas del golden, de modo que tampoco puede moverlo — pero por la regla vigente el golden se
corre igual antes del commit.

3 tests (`TestInactiveOrganizationHidden`): desaparece del selector, **403 al intentar operar**, y
la rama de superusuario intacta.
