# Plan — SAC Ciclo B.2: recepción Willard a 2 pasos (capturar → confirmar)

**Versión**: v1.0 · **Fecha**: 2026-07-17 · **Base**: develop `6318ff9` (post Ciclo B)
**Origen**: feedback de pruebas de Daniel — "toda recepción queda registrada y pasa a la bandeja para que Johana la confirme; en compras funciona bien, en Willard falta". Decisión de producto explícita.

**Sanity check hecho**: `inbound_orders.status` ya es `String(16)` con vocabulario `draft | confirmed | annulled` (el estado intermedio existe en el modelo desde E2, nunca usado — **CERO migraciones**, esta vez de verdad: ningún cambio de schema). `StatusBadge` ya tiene el amarillo "Registrada". `get_multi` ya filtra por status.

---

## 0. Regla de oro

Aditivo y SAC-only por construcción: `inbound_orders` es tabla sin datos en prod y todo el módulo está flag-gated. Golden intacto. Órdenes willard ya confirmadas en dev **quedan como están** (el cambio solo afecta órdenes nuevas).

## 1. El modelo (aprobado por Daniel)

**Willard pasa de 1 paso a 2 — espejo del split de compras:**

| Paso | Quién (permiso) | Efectos |
|---|---|---|
| Capturar (`POST /inbound-orders`, tipo willard) | David — `purchases.create` | Orden en **`draft`** ("Registrada"): SOLO documento — cero inventario, cero kg, cero MCH |
| Confirmar (`POST /{id}/confirm`, NUEVO) | Johana — `purchases.liquidate` | Corre `_apply_willard_effects` (el código de hoy): inventario a identidad D2 + kg ledger D5 + MCH hoy (H1a) → `confirmed` |
| Anular | `purchases.cancel` | `draft` → anula SIN reversa (no movió nada); `confirmed` → reversa completa (hoy) |

- **Tipo Compra regular: intacto** — sigue `confirmed` al crear; su 2-pasos vive en la Purchase derivada (la bandeja de compras existente). Confirmar una orden tipo purchase → 400 (no aplica).
- **Sin `auto_confirm`**: el flujo es 2 pasos estricto (si Johana captura, confirma con un click más desde el detalle). Menos superficie.

## 2. Validaciones en DOS momentos (decisión clave)

- **Al capturar** se valida TODO lo de hoy (fail-fast para David): homogeneidad de mundo, drosses→planta, tercero == titular, bodega receptora, mundo por línea, fórmula vigente y cuenta kg existentes. Un draft no puede nacer roto.
- **Al confirmar** se RE-valida lo que puede haber cambiado entre captura y confirmación (fórmula vigente, cuenta kg activa, material activo) y se toman **ahí** el snapshot de fórmula y el avg de entrada — coherente con "los efectos nacen al confirmar". Consecuencia visible y deseada: si la fórmula cambió entre captura y confirmación, aplica la vigente **al confirmar** (append-only #35; el estimado de captura era preview).
- Fechas: `InventoryMovement.date` y `KgLedgerMovement.transaction_date` = **fecha de la orden** (el material llegó ese día, D4 se conserva); MCH `transaction_date` = **día de la confirmación** (H1a, sin back-dating de costo).

## 3. Backend

- `services/inbound_order.py`:
  - `create`: willard → `status="draft"`, persiste líneas espejo (como hace el path purchase) **sin** llamar `_apply_willard_effects`; purchase → sin cambio (`confirmed`). Las validaciones de captura corren igual (la parte de "existencia" de `_apply_willard_effects` se factoriza en `_validate_willard_capture` — homogeneidad/sede/titular/mundos/fórmulas/cuenta — para reusar en create y confirm sin duplicar).
  - `confirm` (NUEVO): 404 si no existe; 400 si tipo purchase, si `annulled`, o si ya `confirmed`; re-valida; **borra las líneas draft y re-aplica** vía `_apply_willard_effects` (que ya crea líneas con `unit_cost` snapshot + movimientos + kg + MCH) → un solo camino de efectos, cero divergencia con el código probado; `status="confirmed"`, auditoría `confirmed_by/confirmed_at`… ⚠️ NO hay columnas de auditoría de confirmación y no queremos migración → **la auditoría de quién confirmó queda fuera de alcance v1** (el MCH y los movimientos llevan el timestamp; si el cliente la pide, columna aditiva en ciclo futuro).
  - `update`: willard `draft` → edición SIMPLE (reemplazar líneas/fecha sin revert — no hay efectos); willard `confirmed` → revert-and-reapply (hoy); purchase → hoy.
  - `annul`: `draft` → sin reversa (solo status+auditoría de anulación, que SÍ existe); `confirmed` → hoy.
- `endpoints/inbound_orders.py`: `POST /{id}/confirm` con `require_permission("purchases.liquidate")`; enrich sin cambios (draft: `total_kg_lead=None`, `kg_lead=None` por línea — no hay movimientos).
- Sin columnas nuevas, sin permisos nuevos, sin migración.

## 4. Frontend

- `types/inbound-order.ts`: `InboundOrderStatus` gana `"draft"`.
- `StatusBadge`: + `draft: { label: "Registrada", amarillo }` (mismo visual que compras registradas).
- `InboundOrdersPage`: filtro de estado gana "Registradas" (`draft`); **bandeja**: badge contador de pendientes por confirmar (client-side sobre el total del filtro o KPI simple).
- `InboundDetailPage`: si `draft` y permiso liquidate → botón **"Confirmar Recepción"** (verde, con ConfirmDialog que recuerda: "entra el material al inventario y mueve el libro kg"); nota visual "Registrada — pendiente de confirmar" (banner ámbar); kg mostrados como **estimados client-side** (reusa `estimateKgLead` + fórmulas vigentes) con nota "definitivos al confirmar".
- `InboundEditPage`: sin cambio funcional visible (el backend ramifica solo); la nota "re-emite movimientos" solo aplica a confirmadas — condicionar el texto.
- `useInboundOrders`: hook `useConfirmInboundOrder` (invalidación = la misma del create willard de hoy: inbound + inventory + materials + kg-ledger).

## 5. Tests (~10 nuevos + re-semantización mecánica)

- **Nuevos**: willard create → `draft` + CERO efectos (stock/kg/MCH intactos) · confirm → efectos exactos de hoy + `confirmed` · confirm doble → 400 · confirm de tipo purchase → 400 · confirm de anulada → 400 · RBAC: bascula (sin liquidate) no confirma → 403 · draft edit simple (sin MCH de reversa) · draft annul sin reversa · fórmula cambiada entre captura y confirm → aplica la vigente al confirmar · purchase path intacto (sigue confirmed + derivada registered).
- **Re-semantización mecánica** (patrón #73/#76, disclosed): todos los tests willard existentes que asumen efectos al crear ganan un helper `_confirm(client, order)` tras el create — `test_inbound_orders.py` (Willard create/annul/edit), `test_sac_ciclo_b.py` (los de efectos; los de VALIDACIÓN de captura quedan igual — validan el create), stress walk (`_inbound_create` → create+confirm). Conteo de la suite puede crecer ~10.

## 6. Gates

Suite completa sin regresión · parity (sin cambios de schema → DIFF CERO trivial) · tsc/build · smoke live dev (capturar como flujo David → confirmar → efectos; draft sin efectos) · golden sin cambios (tabla SAC-only).

## 7. Fuera de alcance

- Auditoría `confirmed_by/at` (necesitaría migración — ciclo futuro si se pide).
- Confirmación en lote (una a una, como liquidación de compras).
- `auto_confirm` (no hay caso de negocio hoy).
- Notificaciones a Johana (la bandeja es pull: tab + contador).
