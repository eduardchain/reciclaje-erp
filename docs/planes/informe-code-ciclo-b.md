# Informe post-código — SAC Ciclo B: canal único + sede determinista + guard Willard + limpieza (CC-007)

**Plan**: `plan-sac-ciclo-b-recepcion-compras.md` v1.1 (QA GO condicionado 2026-07-17, F1/F2/F3 incorporadas) · **Base**: develop `9eb5ece`

## 0. Resumen

Los 4 ítems en un ciclo + **addendum de feedback de pruebas de Daniel** (mismo día, pre-commit). El núcleo B1–B4 quedó en cero migraciones; el addendum sumó **1 migración aditiva** (`notes` de cabecera, pedida por el usuario — `inbound_orders` no existe en prod, va en el mismo tren del viernes → golden intacto). Todo flag-gated o condicionado a datos que las orgs prod no tienen. Las 3 condiciones del QA aplicadas y testeadas.

**Addendum (feedback pruebas Daniel 2026-07-17):**
1. Label "Mundo Willard" → **"Tipo Willard"**; hint "camión con ambos mundos…" eliminado.
2. **Tercero fijo en Willard**: derivado del **titular de la cuenta kg** del tipo elegido (drosses → cuenta org-wide; postconsumo → cuenta de la sede) — Input deshabilitado con el nombre, "como la sede en drosses". La cuenta está amarrada a su tercero por CHECK del modelo → la derivación es autoritativa, sin setting nuevo. Defensa backend: TP ≠ titular → `422 "El tercero de una recepción Willard es el titular de la cuenta kg (Willard S.A)"`. Al cambiar tipo/mundo/sede se re-deriva; sin cuenta resoluble queda vacío y el submit se bloquea.
3. **Compra regular**: los terceros Willard (titulares de cuentas kg willard activas) **no aparecen** en el selector — son de otro canal.
4. **Quick-create conductor/vehículo**: botón "+" junto a ambos selects → mini-dialog (solo nombre / solo placa) → crea vía el CRUD de flota existente y auto-selecciona. La fricción "deben ser creados antes" desaparece: se crean en línea desde la captura; documento/teléfono/tipo se completan después en Config → Flota. Disponible en ambos tipos de recepción.
5. **Nota de cabecera** (`inbound_orders.notes`, migración `d4e5f6a7b8c9` aditiva nullable): textarea "Notas" en captura y edición (**ambos tipos** — NO entra al set bloqueado D7b: es la nota de la CAPTURA, la compra derivada conserva la suya propia, sin doble verdad), visible en el detalle.
6. **Bodegas receptoras (Q-12)**: la Recepción listaba Molino/Tránsito — bodegas del flujo INTERNO (molino se alimenta por Traslados/Transformaciones; tránsito es del intersede E3). Fix: **flag `warehouses.is_receiving`** (migración `e5f6a7b8c9d0`, `server_default=true`) — el check vive en la BODEGA, no en un setting, porque la pregunta de Daniel "¿y si mañana hay otra?" exige **autoservicio**: bodega nueva nace receptora (caso común), las internas se desmarcan una vez en Config → Bodegas (checkbox "Recibe material de terceros" + columna Recibe/Interna, **ambos gated por flag** — la Config de las 3 orgs prod queda idéntica y su payload de update no cambia). La Recepción filtra su selector a receptoras (base de los 3 modos); defensa backend: bodega interna → 422 "es interna… márquela como receptora en Configuración si aplica". Receptoras SAC confirmadas por Daniel: **Juan Mina, Circunvalar y Bogotá**; Molino y los 2 Tránsito marcados internos en dev.

## 1. Condiciones del GO — aplicadas

| Condición | Cómo quedó |
|---|---|
| **F1** — test B4 assertea 422 (extra=forbid), no "ignorado" | `TestGoesDirectlyRetired`: create con el campo → **422**, PATCH con el campo → **422**, response sin la clave. El frontend dejó de enviarlo en el mismo commit (lockstep) |
| **F2** — claves de settings TAMBIÉN en SETTING_DEFAULTS backend | `app/utils/org_settings.py`: `willard_sede_drosses: None` + `willard_sede_postconsumo_default: None`. Test `test_setting_defaults_backend_has_keys` + `test_get_org_setting_reads_configured_value` (sin KeyError D12) |
| **F3** — LEFT JOIN podría duplicar filas | Resuelto **mejor que el DISTINCT**: el listado NO se joinea — `_inbound_origin_map()` hace un 2º query `WHERE purchase_id IN (ids de la página)` → dict → enrich. Duplicar filas es **imposible por construcción**; prod (sin inbounds) → dict vacío, costo ~0 |

## 2. Archivos

**Backend (8):**
- `app/schemas/inbound_order.py` — B4: `goes_directly_to_jm` fuera de Create/Update/Response (extra=forbid → 422).
- `app/api/v1/endpoints/inbound_orders.py` — B4: fuera del enrich.
- `app/services/inbound_order.py` — B4: fuera de create/update. **B2 en `_apply_willard_effects`** (cubre create Y edición re-apply con el mismo código): homogeneidad de mundo (>1 mundo → 422 "separe el camión en dos recepciones", Q-10) + drosses→planta (`warehouse_id != willard_sede_drosses` → 422 con el **nombre real** de la bodega; setting None = no valida, compat).
- `app/utils/org_settings.py` — B2/F2: 2 claves nuevas (default None).
- `app/schemas/organization.py` — B2: 2 campos `str | None` en `OrgSettingsPayload` (JSON-nativo, H1 OK).
- `app/schemas/purchase.py` — B1: `inbound_order_id` + `inbound_order_number` (Optional, None para todo lo existente).
- `app/api/v1/endpoints/purchases.py` — B1: helper `_inbound_origin_map` (F3) + aplicado en `list_purchases` y `get_purchase` (detalle). `_enrich_purchase_response` gana param opcional `inbound_map` — los demás callers no cambian (campos quedan None).
- `app/services/purchase.py` — B3: `_guard_willard_pure_materials()` (flag-gated, query única por operación) llamado en `create` (no-DP) **y en `update` cuando hay lines** — sin el segundo, el guard se esquivaba editando una compra válida. 400 con código(s) de material y guía "recíbalo como recepción Willard".

**Backend addendum (5 + Q-12):**
- `models/warehouse.py` + `alembic/versions/e5f6a7b8c9d0_warehouse_is_receiving.py` (NUEVA, 2ª del ciclo) — `is_receiving` boolean NOT NULL `server_default=true`; aplicada en dev.
- `schemas/warehouse.py` — Create (default True) / Update (opcional) / Response.
- `services/inbound_order.py` (además de lo de abajo) — `_validate_warehouse` rechaza internas (422).
- `models/inbound_order.py` — `notes` String(1000) nullable (+ comentario de columna inerte en `goes_directly_to_jm`).
- `alembic/versions/d4e5f6a7b8c9_inbound_notes.py` (NUEVA) — la única migración del ciclo, aditiva; aplicada en dev.
- `schemas/inbound_order.py` — `notes` en Create/Update/Response.
- `services/inbound_order.py` — create asigna notes; update la edita en AMBOS tipos (`"notes" in fields_set`: None explícito borra); **validación tercero == titular de la cuenta kg** en `_apply_willard_effects` (pre-resuelve la cuenta del mundo único post-homogeneidad, la cachea para el loop, 422 con el nombre del titular).
- `endpoints/inbound_orders.py` — notes en el enrich.

**Tests (2):**
- `tests/test_sac_ciclo_b.py` (NUEVO, **23 tests**): F2 settings (3) · B2 drosses/sede (4: wrong-wh 422, JM 201, sin setting 201 compat, postconsumo cualquier sede con cuenta 201) · B3 guard (6: manual 400, derivada 400, ambos-canales 201, sin perfil 201, sin flag inerte 201, update 400) · B1 origen (3: derivada expone en detalle+listado, manual null, org sin flag OK) · B4 (3: create 422, patch 422, response sin clave) · **addendum (4)**: TP ≠ titular 422 con nombre, compra acepta cualquier proveedor (lock solo Willard), notes round-trip en create, notes editable en tipo purchase.
- `tests/test_inbound_orders.py` (re-semantizado, mismo conteo 28): ver §3.

**Frontend (9):**
- `pages/inbound/InboundCreatePage.tsx` — **B2**: sub-selector "Mundo Willard" (drosses/postconsumo, obligatorio, con hint "camión con ambos mundos: dos recepciones"); materiales filtrados a `world === willardWorld`; **cambiar de mundo limpia las líneas que no aplican**; bodega gobernada: drosses → forzada al setting y **disabled** ("bodega fija"), postconsumo → **opciones = solo bodegas con cuenta `willard_baterias` activa** (mejora Daniel, vía `useKgAccounts`) con default CV (setting) → fallback primera válida, y **empty-state** "No hay bodegas con cuenta de baterías postconsumo. Créala en Plomo (kg)" + submit bloqueado; compra → libre. B4: checkbox JM eliminado.
- `pages/inbound/InboundEditPage.tsx` — B2: picker de materiales filtrado al **mundo de la orden** (derivado de sus líneas vía perfiles — la edición no puede romper la homogeneidad). B4: checkbox y payload limpios.
- `pages/inbound/InboundDetailPage.tsx` — B4: InfoRow "Directo a JM" eliminado.
- `types/inbound-order.ts` — B4: campo fuera de los 3 contratos.
- `types/purchase.ts` — B1: 2 campos opcionales.
- `pages/purchases/PurchasesPage.tsx` — B1: botón "Nueva Compra" **oculto con flag** y reemplazado por "Nueva Recepción" (→ `/inbound/new`); link "Recepción #N" bajo el número en la tabla (stopPropagation, no dispara el row-click) + badge índigo en la card mobile.
- `pages/purchases/PurchaseCreatePage.tsx` — B1: con flag, `useEffect` redirige a `/inbound/new` con toast "En esta organización las compras se crean desde Recepción" (defensa del deep-link).
- `pages/purchases/PurchaseDetailPage.tsx` — B1: banner índigo "Origen: Recepción #N — esta compra fue derivada desde el patio" con link.
- `hooks/useOrgSettings.ts` — B2: espejo de las 2 claves (null).

## 3. Tests re-semantizados (cambio de contrato deliberado, patrón #73/#76)

| Test | Antes | Ahora | Por qué |
|---|---|---|---|
| `test_mixed_worlds_route_per_line` | orden con drosses+postconsumo → 201 ruteando por línea | **`test_mixed_worlds_rejected_homogeneity`** → 422 | Q-10 (decisión Daniel/Johana): camión mixto = dos recepciones. D1 (ruteo por línea) sigue vigente como mecanismo |
| `test_drosses_org_wide_account` | enviaba `goes_directly_to_jm=True` + assert del campo | sin el campo | B4 (Q-03: peso muerto) |
| `test_edit_purchase_type_lines_422` | usaba `goes_directly_to_jm` como ejemplo de "cabecera editable" | usa `driver_id` (crea driver vía API) | B4: el campo ya no existe |
| `TestPurchaseDerivation` (6 tests) + `test_edit_purchase_type_lines_422` | recepción tipo purchase con `mat_dross` | fixture nuevo **`mat_regular`** (`compra_regular=True`, world=none) | `mat_dross` es Willard-puro → **el guard B3 los bloqueaba correctamente**: la falla de estos tests fue la primera evidencia de que B3 funciona. `test_supplier_behavior_enforced` también migrado (pasaba solo por orden de validación) |

| `TestInventoryStressWalk` (test_avg_cost_model_l.py) | perfil del material del walk `compra_regular=False` + drosses | `compra_regular=True` + drosses | El walk ejercita AMBOS canales (compras + recepciones willard) con el mismo material — con False era Willard-puro y **el guard B3 bloqueó sus compras (400)**: segunda evidencia del guard funcionando. True = el escenario Q-04 "cuentas apartes", que es exactamente lo que el walk modela |

Bonus en `test_purchase_type_derives_registered`: asserts B1 (`inbound_order_id`/`number` en la derivada).

## 4. Decisiones de implementación (margen del plan)

1. **Botón "Nueva Recepción" en Compras (flag ON)**: el plan solo pedía ocultar "Nueva Compra"; dejar el header sin acción primaria era un dead-end para David — el botón muta a "Nueva Recepción". Mismo permiso (`purchases.create`).
2. **Status 422 (no 400) en las validaciones B2 del inbound**: el módulo inbound usa 422 para TODAS sus validaciones de negocio (helper `_err`, ej. "material no es de mundo Willard"); B3 en compras usa 400 (idioma del módulo compras). Consistencia intra-módulo sobre la letra del plan; los tests assertean el código real.
3. **El mensaje drosses→planta resuelve el nombre real de la bodega** del setting (no hardcodea "Juan Mina") — el setting podría apuntar a cualquier bodega.
4. **`_apply_willard_effects` como único punto B2**: create y edición (revert-and-reapply D18) pasan por ahí — una sola implementación, cero divergencia.
5. **Guard B3 también en `update`**: el plan decía "create"; sin update, se creaba con material válido y se editaba a Willard-puro. Test `test_update_lines_willard_pure_blocked`.
6. **Edit de recepción Willard filtra materiales al mundo de la orden** (derivado de líneas vía perfiles): la homogeneidad no se puede romper por edición ni en UI ni en backend.

## 5. Gates

| Gate | Resultado |
|---|---|
| Import sanity backend (schemas/endpoints/servicios/payload) | ✅ `backend OK` (×2: núcleo y addendum) |
| `tests/test_sac_ciclo_b.py` (19 núcleo + 4 addendum + 2 Q-12 = **25**) | ✅ `25 passed` (con inbound: 51; con warehouses: 40+) |
| `tests/test_inbound_orders.py` (re-semantizado) | ✅ `28 passed` |
| Migraciones `d4e5f6a7b8c9` (notes) + `e5f6a7b8c9d0` (is_receiving) aplicadas en dev | ✅ |
| Smoke live addendum (dev) | ✅ TP ≠ titular → `422 …titular de la cuenta kg (Willard S.A)` · notes round-trip en create · orden de smoke #6 **anulada** (D8 revirtió kg+inventario, auditada como smoke) |
| Dominio afectado (org_settings + api_purchases + sac_e1 + kg_ledger + retenciones ×2) | ✅ `169 passed` |
| Barrido `goes_directly` backend tests+app / frontend | ✅ 0 referencias (solo modelo inerte + comentarios) |
| `npx tsc --noEmit` | ✅ exit 0 |
| `npm run build` | ✅ built in 4.20s |
| **Smoke live (dev, datos reales SAC + settings sembrados)** | ✅ 4/4 — B2 drosses→CV: `422 "Los drosses se reciben en la planta (Juan Mina)"` (nombre resuelto del setting) · B2 mixto: `422 "…separe el camion en dos recepciones"` · B3 compra manual con BAT-PC (postconsumo-puro): `400 "…recibalo como recepcion Willard"` · B4 create con el campo: `422`. Bonus: **B1 con datos reales** — compras #3/#4 de dev ya muestran `inbound_order_number` 4/5 en el listado |
| **Suite completa** | ✅ **`1294 passed in 1586.60s (0:26:26)`, exit 0** — reconcilia exacto: 1269 baseline + 25 nuevos (19 núcleo + 4 addendum + 2 Q-12). La corrida previa tuvo 1 fallo: el stress walk, **bloqueado por el guard B3** (su fixture era Willard-puro y compraba) — re-semantizado a `compra_regular=True` (escenario Q-04), ver §3 |
| `schema_parity_check.py` (secuencial, TRAS la suite) | ✅ **DIFF CERO fuera del baseline** — 56 tablas, 247 índices, 267 constraints; `inbound_orders.notes` y `warehouses.is_receiving` modelo ≡ migración |

**Settings sembrados en dev** (pre-requisito walkthrough, ya hecho): `willard_sede_drosses` = Juan Mina (`a2bd897e…`), `willard_sede_postconsumo_default` = Circunvalar (`9fd76560…`), payload completo REPLACE vía PATCH de sistema.

## 6. Guía de walkthrough (Daniel)

Pre-requisito **ya sembrado en dev** durante el smoke: `willard_sede_drosses` = Juan Mina, `willard_sede_postconsumo_default` = Circunvalar. Puedes probar directo.

1. **Recepción Willard → sub-selector** — Nueva Recepción → tipo "Willard": aparece "**Tipo Willard** *" (vacío, borde ámbar). Sin elegirlo: materiales vacíos, bodega deshabilitada, **tercero "Se fija al elegir el tipo"**, no puedes confirmar.
2. **Drosses** — tipo "Drosses": bodega salta a Juan Mina **bloqueada** ("bodega fija"), **tercero fijo "Willard S.A"** (deshabilitado); el picker solo muestra materiales drosses.
3. **Postconsumo** — tipo "Baterías Postconsumo": bodega editable pero **solo lista sedes con cuenta de baterías** (CV preseleccionada), tercero fijo "Willard S.A"; picker solo baterías. En una org sin cuentas: empty-state rojo "Créala en Plomo (kg)" + confirmar bloqueado.
4. **Cambio de tipo limpia líneas** — con una línea de batería elegida, cambia a Drosses: la línea desaparece (no puedes mezclar); cambiar entre Willard/Compra resetea tercero y líneas.
4b. **Quick-create + notas** — "+" junto a Conductor: dialog solo-nombre → crea y queda seleccionado (igual Vehículo con placa). Textarea "Notas" en la captura; se ve en el detalle y se edita en ambos tipos. En Compra regular, "Willard S.A" ya NO aparece en el selector de tercero.
5. **Canal único** — Compras: el botón ahora dice "Nueva Recepción". Entra a mano a `/purchases/new`: redirige a Recepción con toast.
6. **Badge de origen** — crea una recepción tipo "Compra regular" → en Compras la fila muestra "Recepción #N" bajo el número (click → va a la recepción, no al detalle de la compra); el detalle de la compra muestra el banner "Origen: Recepción #N"; la card mobile muestra el badge índigo.
7. **Guard Willard-puro** — intenta una recepción tipo "Compra regular" con una batería postconsumo (si aparece en el picker no aparecerá — pruébalo por API o edita una compra metiéndole la batería): 400 "es Willard… recíbalo como recepción Willard".
8. **B4** — en Recepción ya no existe el checkbox "Va directamente a JM" (create/edit/detail).
9. **Regresión Costa (org sin flag)** — Compras idéntica (botón "Nueva Compra" visible, sin badges, sin redirect); Recepción no existe en el sidebar; Network sin llamadas a kg-ledger desde compras.
10. **Mobile 390px** — sub-selector y bodega usables; badge en cards.

## 7. Runbook post-deploy (cola del viernes, se suma al existente)

Al payload completo de settings de SAC prod se agregan: `willard_sede_drosses` (ID Juan Mina prod) y `willard_sede_postconsumo_default` (ID Circunvalar prod). **Nota**: los IDs de bodega difieren entre dev y prod — resolverlos contra la BD de prod vía API en el momento del runbook, no copiar los de dev.

## 8. Fuera de alcance (sin cambios)

- Columna `goes_directly_to_jm` queda inerte en la tabla (drop = limpieza futura opcional).
- El mundo no se persiste en `inbound_orders` (se deriva de líneas homogéneas).
- Selector recolector-comisionista (memoria `sac-ruta-generalizar-recolector-comision`) — ciclo de productización.
- Comunicar a Johana: para habilitar postconsumo en una sede nueva, primero crear su cuenta de baterías en Plomo (kg).
