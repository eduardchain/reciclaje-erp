# Plan — SAC Ciclo C: módulo único "Entradas" (unificación UX recepción + compras)

**Versión**: v1.0 · **Fecha**: 2026-07-17 · **Base**: develop + Ciclo B.2 (willard 2 pasos, decisión #81 — **prerequisito: B.2 commiteado tras GO de Daniel**)
**Origen**: feedback de producto de Daniel (2026-07-17): "tenemos un módulo de recepciones donde se reciben entradas willard pero también compras, pero las willard se liquidan en recepciones y las compras en el tab de compras — está bastante desordenado. Debería ser más sencillo: un módulo de entradas, ahí se hacen todas, quedan registradas, y ahí mismo está la opción de liquidar. No necesitamos un módulo de compras."

**Decisiones de producto ya tomadas (Daniel, mismo día):**
1. Verbo y estado únicos: **"Liquidar" / "Liquidada"** para ambos tipos (willard incluido — su liquidar es el confirm de B.2, sin efecto financiero; el diálogo lo aclara).
2. Nombre del módulo: **"Entradas"**.
3. Liquidación de compras: **reusar el formulario existente** (retenciones, pago inmediato) navegando desde la entrada y volviendo a ella.
4. Dos entidades se mantienen (entrada = documento de patio; compra = documento financiero) — validado explícitamente; lo que se unifica es la PRESENTACIÓN: una sola cosa visible (la entrada), la compra es su cara financiera.
5. Anuladas: **un solo estado visible "Anulada"** (orden anulada y compra cancelada no se distinguen en UI; el detalle conserva el motivo).
6. Corte acordado: unificación + 6 mejoras baratas (contador sidebar, FIFO+antigüedad, liquidar desde la fila, buscador, mundo visible, quién-hizo-qué). El resto → Ciclo D.

---

## 0. Regla de oro

**CERO migraciones. Cero cambios en tablas o endpoints compartidos.** Todo vive en el router flag-gated `/inbound-orders` (params y campos de response ADITIVOS) y en frontend gated por `kg_ledger_enabled`. Las 3 empresas prod no ven ni un pixel distinto; golden intacto por construcción. El módulo Compras queda intacto en código y rutas — SAC solo pierde su entrada del menú (`hideWhenOrgFlag`, mecanismo #77). Los guards y estados internos NO cambian (draft/confirmed/annulled en órdenes; registered/liquidated/cancelled en compras): C es una capa de presentación + queries de lectura.

## 1. El modelo mental (lo que ve el usuario)

**Una fila por camión = una entrada.** Estado ÚNICO derivado:

| Por debajo | Se muestra |
|---|---|
| willard `draft` · compra derivada `registered` | **Registrada** (amarillo) |
| willard `confirmed` · compra `liquidated` | **Liquidada** (verde) |
| orden `annulled` · compra `cancelled` | **Anulada** (rojo) |

Flujo: David/Erwin capturan (`purchases.create`) y editan registradas (`purchases.edit`) → bandeja → Johana liquida (`purchases.liquidate`) / anula (`purchases.cancel`). Permisos existentes, cero nuevos. Liquidadas NO se editan (regla #8: cancelar y rehacer; willard confirmada sí, D18 — asimetría existente, no se toca).

## 2. Backend (router inbound-orders, todo aditivo)

- **`display_status`** (C-1): query param nuevo `display_status ∈ registered|liquidated|annulled` en GET lista (LEFT JOIN a purchases para el mapeo de la tabla §1; el param `status` actual queda intacto — tests y compat). Response (lista y detalle) gana campo **`display_status`** calculado en el enrich con el MISMO mapeo (la compra ya viene joineada — `purchase_status` existe desde E2). Fuente única: helper `_display_status(order) -> str` usado por filtro (SQL espejo) y enrich; test de paridad filtro-vs-campo.
- **`search`** (C-2): ILIKE OR sobre `order_number::text`, placa (join Vehicle), conductor (join Driver), tercero (join ThirdParty) y material (EXISTS lines→Material code/name).
- **`sort ∈ newest|oldest`** (C-3): default `newest` (hoy: order_number DESC). `oldest` = ASC por `created_at` — FIFO para la bandeja.
- **`willard_world`** (C-4): campo response derivado de las líneas (homogéneo por construcción B2) vía 1 query de perfiles por página; `null` para tipo compra.
- **Quién hizo qué** (C-5): response gana `created_by_name`, `annulled_by_name`, `liquidated_by_name`/`liquidated_at`. Fuentes: `created_by`/`annulled_by` de la orden; para compras `purchase.liquidated_by/at` (columnas existentes, verificado); para willard el `created_by`/`created_at` del primer `KgLedgerMovement` confirmado (decisión de auditoría B.2). Nombres: 1 query de users por página (ids → full_name).
- Sin cambios en create/confirm/annul/update — C no toca efectos.

## 3. Frontend

- **Sidebar** (C-6): "Recepción" → **"Entradas"**; entrada "Compras" gana `hideWhenOrgFlag: "kg_ledger_enabled"` (rutas `/purchases/*` VIVAS — se llega por links). Badge contador ámbar "N" en el item Entradas (hook `usePendingEntriesCount`: lista `display_status=registered&limit=1` → total; solo se dispara con flag, staleTime corto).
- **EntradasPage** (rework de InboundOrdersPage):
  - **Tabs en URL** (`?tab=`, convención #49): Todas · Registradas · Liquidadas · Anuladas → `display_status`. En Registradas: orden FIFO (`sort=oldest`) + columna "Días" con semáforo (#68: rojo >3, naranja >1 — umbrales de entrada, ajustables por feedback).
  - **Columnas**: # · Fecha · Tipo (chip "Compra" / "Willard · Drosses|Postconsumo" con `willard_world`) · Tercero · Sede · Materiales (primera línea + "+N") · Cant. total (patrón #72) · Kg plomo (willard) o Total $ (compras: Σ qty×unit_price client-side, gated `purchases.view_prices`) · Placa · Estado (`display_status`).
  - **Buscador** (`SearchInput` → `search`).
  - **Liquidar desde la fila** (solo `purchases.liquidate`, filas Registradas): willard → diálogo de confirmación B.2 inline (relabel "Liquidar"); compra → navega al formulario de liquidación con `returnTo`. `stopPropagation` (patrón ActionsCell #63).
  - Cards mobile actualizadas (mismos datos).
- **Detalle de entrada**:
  - Botón "Confirmar Recepción" → **"Liquidar"** (willard, B.2 relabel); botón **"Liquidar"** para tipo compra (visible si `display_status=registered` y permiso) → `PurchaseLiquidatePage?returnTo=/inbound/:id`.
  - **Cara financiera** (tipo compra): sección "Compra" con estado, total, retenciones/pagos resumidos si liquidada, y link "Ver compra completa" → PurchaseDetailPage (que ya tiene banner de vuelta a la entrada, B1). v1 = resumen + link; embedding total queda para D si hace falta.
  - Líneas "Registrada por X hace N" / "Liquidada por Y el F" / "Anulada por Z" (C-5).
  - Estado del header con `display_status`.
- **PurchaseLiquidatePage**: soporte `?returnTo=` (al liquidar navega de vuelta; hoy navega al detalle de compra). Patrón `useReturnToBack` existente en detail pages.
- **queryInvalidation** (D17): `invalidateAfterPurchaseLiquidateOrCancel` gana `["inbound-orders"]` — al liquidar/cancelar la compra desde su formulario, la entrada y la bandeja se refrescan. Key extra inofensiva para orgs sin flag (no hay queries registradas bajo ella).
- **Labels**: toasts y diálogos de B.2 re-labelados a "Liquidar"/"Liquidada" (los textos internos siguen explicando el efecto por tipo).

## 4. Tests (~14 backend nuevos)

`display_status`: mapeo completo (willard draft/confirmed/annulled; compra registered/liquidated/cancelled-post-liquidación → annulled; filtro == campo, test de paridad) · `search` por placa/material/tercero/# · `sort=oldest` · `willard_world` (drosses/postconsumo/null compra) · nombres de auditoría (created/liquidated willard vía kg mov y compra vía liquidated_by) · params nuevos ignoran órdenes de otra org (multi-tenancy) · RBAC/flag sin cambios (smoke). Re-semantización: los tests existentes NO cambian (params nuevos opcionales, campos nuevos aditivos); solo se ajustan los asserts de frontend si los hubiera (no hay infra).

## 5. Gates

Suite completa sin regresión (base 1305) · parity DIFF CERO trivial (cero schema) · tsc/build · smoke live dev (flujo completo: capturar compra → bandeja → liquidar con retenciones → vuelve a entrada Liquidada; willard capturar → liquidar; anuladas fusionadas visibles; buscador; contador sidebar) · golden sin cambios (cero tablas compartidas) · verificación mobile 390px (regla CLAUDE.md).

## 6. Secuencia

1. Daniel prueba B.2 en dev → GO → **commit B.2** (atómico, ya listo).
2. Micro-QA de ESTE plan → GO → código C sobre esa base.
3. Pruebas Daniel de C → GO → commit C.
El deploy del viernes NO depende de C (B+B.2 son deployables solos; C puede entrar al siguiente tren si QA/pruebas no alcanzan).

## 7. Fuera de alcance (→ Ciclo D u otros)

Duplicar entrada · selectores por uso reciente · "siguiente registrada" · aviso de doble captura · KPIs del día · toast consecuencia kg (850→882) · foto de evidencia (migración) · edición de liquidadas (decisión: se mantiene cancelar-y-rehacer) · embedding completo del detalle financiero en la entrada · confirmación/liquidación en lote.
