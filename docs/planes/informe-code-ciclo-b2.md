# Informe post-código — SAC Ciclo B.2: recepción Willard a 2 pasos

**Fecha**: 2026-07-17 · **Base**: develop `6318ff9` (post Ciclo B) · **Plan**: `plan-sac-ciclo-b2-willard-dos-pasos.md` v1.0 (QA GO limpio, cero condiciones)

---

## 0. Resumen

Willard pasa de 1 paso a 2, espejo del split de compras: **capturar** (David, `purchases.create`) deja la orden en `draft` ("Registrada") — solo documento, cero efectos — y **confirmar** (Johana, `purchases.liquidate`, endpoint nuevo `POST /inbound-orders/{id}/confirm`) corre `_apply_willard_effects` (el MISMO código del 1-paso): inventario a identidad D2 + kg ledger D5 + MCH hoy H1a. Tipo compra intacto (nace `confirmed`, su 2-pasos vive en la Purchase derivada). **Cero migraciones** (draft ya estaba en el vocabulario de `status` desde E2), cero permisos nuevos, cero columnas.

**Un hallazgo en implementación** (fuera del plan, dentro de su espíritu): el guard del `annul` decía `status != "confirmed" → 400`, lo que hacía **inanulable un draft**. El plan §1 exige "draft → anula SIN reversa", así que el guard pasó a `status == "annulled" → 400` (draft y confirmed anulables; draft = solo status+auditoría). Lo atrapó la suite (`test_edit_annulled_404` — el annul silencioso fallaba y el PATCH veía un draft editable).

## 1. W1 — el confirm produce efectos BYTE-IDÉNTICOS al 1-paso previo

El confirm **no re-implementa nada**: borra las líneas draft y llama `_apply_willard_effects` — la misma función que el 1-paso llamaba en el create y que la edición D18 llama en el re-apply. Evidencia en tres capas:

1. **Tests re-semantizados con asserts intactos**: `test_postconsumo_happy_identity` conserva TODOS sus asserts del 1-paso (avg intacto, `liquidated +10`, snapshot `unit_cost=50.00`, `kg=25` a la cuenta de la sede, `source_type=postconsumo_receipt`, snapshot de fórmula sin subtype, MCH `inbound_receipt` HOY con `prev==new`, saldo cuenta kg 25) — solo se insertó `_confirm()` entre el create y los asserts. Igual `test_drosses_kg_by_percentage` (530 kg), `test_identity_on_negative_pool_guardian` (identidad D2 sobre pool negativo, P&L intacto), round-trip de anulación (3600 de `annul_cost_adjustment` con extracción entre medias) y los 3 de edición D18.
2. **Test nuevo dedicado** `test_confirm_effects_identical_to_one_step`: orden backdateada 4 días → al confirmar, `InventoryMovement.date` y `KgLedgerMovement.transaction_date` = **fecha de la orden** (D4 conservado) y MCH `transaction_date` = **HOY** (H1a, día de la confirmación — checkpoint al escribir). Es el contrato de fechas del plan §2 verificado con captura y confirmación en "días" distintos.
3. **Smoke live dev** (org SAC, cuenta WILLARD-BAT-CV): saldo 850 → captura draft (saldo **sigue 850**, `total_kg_lead=None`, `unit_cost=None`) → confirm → `confirmed`, kg +32 (4 baterías × 8.0 de la fórmula vigente dev), saldo **882**, `unit_cost=0.00` (avg vigente del material, identidad D2) → annul → reversa completa, saldo **850**. Doble confirm → 400 "ya esta confirmada".

## 2. W2 — refactor de validación behavior-preserving

`_validate_willard_capture(db, org, warehouse_id, third_party_id, lines_in)` es ahora el **único camino** de validación Willard (homogeneidad de mundo Q-10, drosses→planta, tercero == titular de la cuenta kg, mundo por línea, cuenta kg existente, fórmula vigente, material activo). No hay copia: `_apply_willard_effects` la **llama al inicio y consume su retorno** `(worlds, formulas, account_by_world)` — el loop de efectos ya no re-consulta ni re-valida. Corre en tres momentos: al capturar (fail-fast David: un draft no puede nacer roto), al editar un draft (líneas nuevas validadas), y al confirmar/re-aplicar (via apply — fórmula/cuenta/material pueden haber cambiado; el confirm además re-valida bodega y tercero activos).

Evidencia: los 6 tests de validación de captura (`test_mixed_worlds_rejected_homogeneity`, `test_material_without_willard_profile_422`, `test_no_formula_422`, `test_no_kg_account_422`, titular locked ×2, drosses sede ×2) pasan **sin tocar** — siguen validando el CREATE (422 al capturar, como antes). El stress walk (60 ops con 6 invariantes tras cada una, ahora con `capturar→confirmar` en la acción `inbound_create`) verde. Nota de orden aceptada: en órdenes multi-línea con varios errores, el refactor valida todas las líneas antes de aplicar efectos, así que el *primer* error reportado puede diferir del histórico (era por-línea intercalado); ningún test dependía de eso y el HTTP resultante es el mismo.

## 3. Archivos

**Backend**
- `services/inbound_order.py`: `_validate_willard_capture` (nuevo, camino único), `_apply_willard_effects` (consume el retorno), `create` (willard → `status="draft"` + `_persist_mirror_lines` sin efectos; helper compartido con el path purchase), `confirm` (nuevo: guards 400 tipo compra/anulada/ya confirmada, re-valida, borra líneas draft, re-aplica, `confirmed`), `update` (rama draft: reemplazo simple de líneas/fecha con validación de captura, cero reversa), `annul` (guard corregido + rama draft sin reversa).
- `endpoints/inbound_orders.py`: `POST /{id}/confirm` con `require_permission("purchases.liquidate")`; pattern del filtro `status` gana `draft`.

**Frontend**
- `types/inbound-order.ts` (+"draft"), `StatusBadge` (draft → "Registrada" amarillo), `services/inboundOrders.ts` (`confirm()` + filtro), `hooks/useInboundOrders.ts` (`useConfirmInboundOrder`, misma invalidación del create; toast del create dice "registrada — pendiente de confirmar").
- `InboundOrdersPage`: filtro "Registradas" + **botón bandeja ámbar "Por confirmar: N"** (query `status=draft&limit=1`, fija el filtro al tocarlo).
- `InboundDetailPage`: banner ámbar "Registrada — pendiente de confirmar", botón verde **"Confirmar Recepción"** (permiso liquidate) con ConfirmDialog, **kg estimados client-side** en drafts (`estimateKgLead` + fórmulas vigentes, prefijo `~` en ámbar, "definitivos al confirmar"), Editar/Anular habilitados también en draft, diálogo de anulación con texto ramificado (draft: "no ha movido nada").
- `InboundEditPage`: nota condicionada (draft: "editar solo actualiza el documento").

## 4. Tests

**11 nuevos** (`TestWillardTwoStep` en `test_inbound_orders.py`): draft cero-efectos (stock/kg/MCH/InventoryMovement vacíos + response sin snapshot) · confirm efectos idénticos W1 (con contrato de fechas D4/H1a) · doble confirm 400 · confirm tipo compra 400 · confirm anulada 400 · RBAC viewer sin liquidate 403 · draft edit simple→confirm refleja líneas nuevas · draft annul sin reversa (adjustment 0) · fórmula cambiada entre captura y confirm → aplica la vigente (#35) · tipo purchase sigue confirmed+registered · draft invisible en balance y saldo kg.

**Re-semantización mecánica** (patrón #73/#76, helper `_confirm()`): `test_inbound_orders.py` 7 tests de efectos (happy, negative-pool, drosses, annul ×2, corte histórico, edit ×3 — los de validación quedaron intactos a propósito); `test_sac_ciclo_b.py` 2 asserts de kg (drosses OK, postconsumo any-sede); stress walk (`inbound_create` → create+confirm). `test_annul_already_annulled_422` y `test_edit_annulled_404` quedaron ejercitando el path DRAFT-annul (legal ahora) — el path confirmed-annul lo cubren round-trip y conservación.

## 5. Gates

| Gate | Resultado |
|---|---|
| Targeted (inbound + ciclo_b, 64 tests) | ✅ verdes |
| Stress walk (con confirm) | ✅ verde |
| Suite completa | ✅ **1305 passed** (1294 + 11) |
| Parity check | ✅ DIFF CERO trivial (sin cambio de schema — corrido secuencial post-suite) |
| tsc / build | ✅ limpio / ✅ 3.96s |
| Smoke live dev | ✅ 6 caminos (draft sin efectos, confirm+32kg, doble 400, annul reversa, draft-annul sin reversa, bandeja filtra) |
| Golden | Sin cambios (tabla SAC-only, cero migraciones) — el gate DURO del viernes sigue siendo el de Ciclo B (`warehouses.is_receiving`) |

Artefactos de smoke anulados (#9, #11, motivo "smoke test B.2"). Nota: durante el smoke, Daniel estaba capturando en dev en vivo — la orden #10 quedó en `draft` en su bandeja (primer uso real del flujo).

## 6. Walkthrough para pruebas de Daniel

1. **David** (o admin): Recepción → Nueva → Willard → capturar. Toast "registrada — pendiente de confirmar". La orden queda amarilla "Registrada"; el saldo kg y el inventario NO se mueven.
2. Listado: botón ámbar "Por confirmar: N" → filtra la bandeja. Filtro de estado gana "Registradas".
3. Detalle de un draft: banner ámbar, kg **estimados** (`~`), botones Editar / **Confirmar Recepción** / Anular.
4. **Johana** (o admin): Confirmar → los kg pasan de estimados a definitivos, saldo kg y stock se mueven. Estado verde "Confirmada".
5. Editar draft: solo documento (sin re-emisión); editar confirmada: revert-and-reapply como hoy.
6. Anular draft: solo lo marca; anular confirmada: reversa completa como hoy.
7. Usuario báscula (sin `purchases.liquidate`): NO ve el botón Confirmar y el endpoint le da 403.
8. Tipo Compra regular: idéntico a ayer (nace confirmada + compra derivada registrada).

## 7. Fuera de alcance (según plan)

Auditoría `confirmed_by/at` (columna aditiva futura si se pide; mientras tanto `KgLedgerMovement.created_by` = quién confirmó), confirmación en lote, `auto_confirm`, notificaciones push a Johana (la bandeja es pull).
