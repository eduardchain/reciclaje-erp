# Informe post-código — SAC Ciclo C: módulo único "Entradas"

**Fecha**: 2026-07-17 · **Base**: develop `1ca94ec` (post B.2) · **Plan**: `plan-sac-ciclo-c-entradas-unificadas.md` v1.0 (micro-QA GO, cero condiciones)

---

## 0. Resumen

La unificación UX acordada con Daniel: **un módulo "Entradas"** (Compras sale del menú SAC, rutas vivas), **estado derivado único** (Registrada / Liquidada / Anulada — el usuario nunca ve el estado técnico de la orden vs el de la compra), **verbo único "Liquidar"**, liquidación de compras **reusando el formulario existente** con retorno a la entrada, y las 6 mejoras del corte: contador en sidebar, bandeja FIFO con antigüedad, liquidar desde la fila, buscador, mundo Willard visible, quién-hizo-qué. **CERO migraciones, cero permisos nuevos** — capa de lectura/presentación sobre el router flag-gated; create/confirm/annul/update intactos.

**Un hallazgo mayor en implementación (disclosed): deadlock pre-existente de E2.** El test W-C2 del caso "compra cancelada post-liquidación" lo expuso: el guard D7b bloqueaba el cancel directo de CUALQUIER derivada ("Anule desde la orden #N") y el annul de la orden con derivada liquidada también bloqueaba ("Cancele primero la compra #N") → **una derivada liquidada era incancelable por ambos caminos**. Nadie lo vio porque ningún flujo E2/B canceló una liquidada derivada. Fix mínimo alineado con el plan §3: el guard D7b queda **solo para derivadas registradas** (el par se anula atómico desde la orden, como siempre); una derivada **liquidada sí se cancela directo** — con reversa financiera y la elección de pago enlazado (#63). La preocupación original del guard ("orden confirmada apuntando a compra cancelada" confunde) la cura exactamente el `display_status` de este ciclo: esa combinación se muestra **Anulada**. Regression tests: el 400 de registradas sigue testeado (`test_direct_cancel_of_derived_400` intacto); el camino nuevo tiene test propio; vecinos verdes (132 tests de inbound+ciclo_b+purchases).

## 1. W-C1 — `?returnTo=` en PurchaseLiquidatePage: default EXACTO al comportamiento de hoy

Único toque a superficie compartida (las 3 orgs prod liquidan ahí). Patrón aditivo-condicional (#50): `exitTo = returnTo ?? \`/purchases/${id}\``. **Sin el param, los 4 puntos de navegación quedan byte-idénticos al código previo** (mismo destino literal): redirect si no-liquidable, onSuccess, botón Volver, botón Cancelar. Guard anti open-redirect: solo se acepta `returnTo` que empiece con `/` (ruta interna). Las 3 orgs prod jamás envían el param (solo lo arman EntradasPage/InboundDetailPage, que viven tras el flag).

## 2. W-C2 — paridad del `display_status`

- **Fuente única**: `display_status_of(order)` (Python) y el filtro SQL de `get_multi` son espejos; `test_filter_parity_with_field` arma el set mixto completo (willard draft/liquidada/anulada + compra registrada/liquidada/**cancelada-post-liquidación**) y exige `ids(filtro=X) == ids(campo==X)` para los 3 valores, más el total.
- **Precedencia Anulada**: orden anulada O compra cancelada gana sobre todo — test dedicado del caso delicado (compra liquidada → cancelada desde Compras → la orden interna sigue `confirmed` pero el usuario ve **Anulada**).
- **Bug real atrapado por el test de paridad**: la primera versión del filtro negaba un OR con columnas NULL del outer join (three-valued logic) — los drafts willard desaparecían del filtro `registered`. Fix NULL-safe explícito (`Purchase.id.is_(None)` en la rama no-anulada). El test de paridad existe exactamente para esto.
- **Smoke con datos reales dev**: bandeja `registered` FIFO (1 entrada — captura en vivo de Daniel), `liquidated` 6 (incluye willard del 1-paso viejo — auditoría retroactiva vía kg movement), `annulled` 5 — **incluida la entrada #2 con `purchase_status='cancelled'`** (la precedencia en datos reales).

## 3. W-C3 — aislamiento en orgs sin flag

- `GET /inbound-orders?...` en **Costa (réplica prod, sin flag) → 403** (router-level `require_org_flag`); `GET /purchases → 200` intacto.
- El contador (`usePendingEntriesCount`) solo se monta dentro del item "Entradas" del sidebar y del EntradasPage — ambos existen únicamente con `kg_ledger_enabled` → **cero requests nuevos en orgs prod** (mismo mecanismo F2 del addendum de retenciones).
- Sidebar Costa: "Compras" visible (checkHide con flag off → true), "Entradas" ausente. El dedupe de secciones consecutivas garantiza un solo header "OPERACIONES" en ambos mundos.
- `invalidateAfterPurchaseLiquidateOrCancel` ganó la key `["inbound-orders"]` — no-op para orgs sin queries bajo ella.

## 4. Qué se construyó

**Backend** (`/inbound-orders`, todo aditivo):
- `display_status` (param con pattern + campo en response, mapeo §2 del plan).
- `search` (ILIKE OR: `#` casteado, placa, conductor, tercero + EXISTS líneas→material).
- `sort=newest|oldest` (oldest = FIFO por `created_at`).
- `willard_world` en response (perfil del material de la primera línea, 1 query por página).
- Quién-hizo-qué: `created_by_name`, `liquidated_by_name`/`liquidated_at` (compra: `Purchase.liquidated_by/at` — columnas existentes; willard: `created_by/created_at` del primer kg movement confirmado, decisión de auditoría B.2), `annulled_by_name`. `_page_context()`: 3 queries por página (audit, worlds, users), cero N+1.
- Fix D7b (§0). Sin cambios en efectos.

**Frontend**:
- **Sidebar**: "Recepción"→"Entradas" (primera de OPERACIONES), badge ámbar con contador; "Compras" con `hideWhenOrgFlag` (ruta viva); "Ventas" carga la sección como fallback + dedupe de headers consecutivos.
- **EntradasPage** (rework): tabs URL `?tab=` (Todas/Registradas/Liquidadas/Anuladas, contador en el tab), buscador, columnas nuevas (Tipo con mundo "Willard · Drosses", Materiales resumen "+N", Cant. total, Kg plomo / **Total $** gated `purchases.view_prices`, Placa, Estado derivado), bandeja FIFO con columna **Días** (semáforo #68: ámbar hoy / naranja >1 / rojo >3), botón **Liquidar por fila** (willard → diálogo inline; compra → formulario con returnTo a la lista), cards mobile equivalentes, empty-state "Nada por liquidar — la bandeja está al día".
- **Detalle de entrada**: título "Entrada #N", estado/borde derivados, botón único **"Liquidar"** (willard → diálogo B.2 relabelado; compra → formulario con returnTo al detalle), banner ámbar por tipo, sección financiera ("Total Capturado" + link "Cara Financiera: Ver compra #N" + estado compra), líneas "Registrada por X · fecha" / "Liquidada por Y · fecha" / "Anulada por Z"; anular una compra liquidada guía a la cara financiera (donde vive la elección del pago enlazado #63) con el confirm deshabilitado.
- **Vocabulario**: barrido completo "Recepción"→"Entrada" en títulos, toasts, badges y hints (toast del confirm: "Entrada #N liquidada").
- **Addendum pruebas Daniel (mismo ciclo)**: (1) colores de tipo bien separados — Compra **azul**, Willard·Postconsumo **violeta**, Willard·Drosses **cian** (antes indigo vs azul se confundían; sin chocar con los colores de estado); (2) columna Materiales al **patrón Costa** de Compras: hasta 3 líneas apiladas "CÓDIGO - cantidad unidad x $precio" (precio solo en compras con `view_prices`; willard sin precio) + "+N materiales más", `hideOnMobile`; card mobile lidera con los materiales unidos ("BAT-PC 4 und · ... — Willard · Postconsumo · CV"); (3) **filtros**: selector de tipo gana los mundos (Compra regular / Willard todos / Willard·Postconsumo / Willard·Drosses — backend param `willard_world` vía EXISTS de líneas→perfil, restringido a tipo willard: un material "ambos canales" Q-04 comprado por canal regular NO aparece al filtrar por mundo) + filtro de **Sede** (`warehouse_id`, param nuevo) + filtro de **Tercero** (param existente, UI nueva). 4 tests nuevos (`TestWorldAndWarehouseFilters`, incl. exclusión Q-04 y 422). Conscientemente NO se agregaron: material dedicado y conductor/placa (los cubre el buscador), estado (tabs). **Edge legacy conocido**: órdenes mixtas pre-B2 en dev (ej. #1) matchean ambos mundos en el filtro (contienen líneas de ambos — correcto) pero el badge muestra el mundo de la primera línea; imposible desde B2 (homogeneidad) y el reseed pre-go-live las elimina.

## 5. Tests

**20 nuevos** (`test_sac_ciclo_c.py`, 7 clases): mapeo display_status × 7 casos (incl. cancelada-post-liquidación y par anulado D7b) · **paridad filtro==campo** (guardrail W-C2) · search ×5 términos + miss · FIFO + sort inválido 422 · willard_world ×3 · auditoría (created/liquidated willard y compra, annulled) · `TestWorldAndWarehouseFilters` ×4 (filtro por mundo, exclusión Q-04 "ambos canales", filtro por sede, mundo inválido 422) · multi-tenancy con params nuevos (org2 no ve org1) · display_status inválido 422.

## 6. Gates

| Gate | Resultado |
|---|---|
| Ciclo C targeted (20 tests) | ✅ verdes |
| Vecinos D7b (inbound + ciclo_b + api_purchases, 132) | ✅ verdes |
| Suite completa | ✅ **1325 passed** en 31:42 (1305 + 20) |
| Parity check | ✅ DIFF CERO fuera del baseline (56 tablas / 247 índices / 267 constraints; corrido secuencial post-suite) |
| tsc / build | ✅ limpio / ✅ 4.2s |
| Smoke live dev | ✅ filtros derivados + FIFO + search + auditoría sobre datos reales; W-C3 Costa 403/200 |
| Golden | Sin cambios (cero tablas compartidas; W-C1 es param opcional frontend) |

## 7. Walkthrough para pruebas de Daniel

1. Sidebar: ya no hay "Compras" — hay **"Entradas"** con contador ámbar si hay pendientes.
2. Listado: tabs Todas / **Registradas** (la bandeja, más vieja primero, columna Días) / Liquidadas / Anuladas. Buscador por placa, conductor, material o #. Columna Estado única: una compra sin liquidar y una willard sin liquidar se ven IGUAL ("Registrada").
3. **Liquidar** directo desde la fila o desde el detalle: willard → diálogo (kg definitivos); compra → el formulario de siempre (precios, retenciones, pago inmediato) y **vuelve a la entrada**, que queda "Liquidada".
4. Detalle: quién registró y quién liquidó, con fecha. Tipo con mundo ("Willard · Drosses"). En compras: Total capturado + "Ver compra #N" (cara financiera).
5. Anular: registrada → anula el par completo; willard liquidada → reversa total; compra liquidada → el diálogo guía a la cara financiera (ahí se decide qué pasa con el pago enlazado) — **ese camino antes estaba bloqueado por el deadlock, ahora funciona**.
6. La compra #N sigue accesible siempre por link (estado de cuenta, reportes, "Ver compra") — solo salió del menú.

## 8. Fuera de alcance (→ Ciclo D, plan §7)

Duplicar entrada · selectores por uso reciente · "siguiente registrada" · aviso de doble captura · KPIs del día · toast consecuencia kg · foto de evidencia (migración) · embedding completo de la cara financiera · edición de liquidadas (sigue cancelar-y-rehacer).
