# Informe post-código — Paquete UX: config unificada de materiales SAC + UI de retenciones

**Plan:** `plan-paquete-ux-recepcion.md` (GO de QA sin bloqueantes; F1 incorporado, F2/F3 como forward-notes).
**Conjunto ampliado:** `{E2 − subtype + material_kg_profiles + este paquete}` — todo en el working tree, commit atómico único tras pruebas manuales + GO.
**Fecha:** 2026-07-17. **Estado:** para re-QA + walkthrough de Daniel.

---

## 0. Resumen

8 archivos frontend, **cero backend** (gate duro verificado por mtime: ningún archivo de `backend/` tocado durante el paquete). Dos entregas:

- **A — Página "Materiales (kg)"** (C1+C3+C4+C5): reescritura de `FormulasPage.tsx` — tabla **material-céntrica** (todos los materiales con badge de Clasificación + factor vigente) y **formulario unificado** que crea material + clasifica + registra factor en un solo submit encadenado.
- **B — UI de retenciones** (GAP-1): sección en la liquidación de compras (gated por flag), preview del neto, pago inmediato por el neto, y sección "Retenciones Aplicadas" en el detalle.

## 1. Archivos (los 8)

| Archivo | Cambio |
|---|---|
| `pages/config/FormulasPage.tsx` | **Reescrito** — página Materiales (kg): join client-side `useMaterials`+`useKgProfiles`+`useCurrentFormulas`, tabla material-céntrica (badge Sin clasificar/Compra regular/Postconsumo/Drosses + badge secundario "Compra"), búsqueda + filtro por clasificación, form unificado crear/editar con submit encadenado y toasts por paso, historial de fórmulas conservado |
| `types/purchase.ts` | `RetentionType` + `RETENTION_TYPE_LABELS` + `PurchaseRetentionCreate/Response` + `retentions?` en `PurchaseLiquidateRequest` + `retentions` en `PurchaseResponse` |
| `pages/purchases/PurchaseLiquidatePage.tsx` | Sección "Retenciones (Opcional)" gated por `kg_ledger_enabled`; filas tipo/municipio(ICA)/monto; validación Σ<total + municipio obligatorio en ICA; Resumen Financiero con (−) Retenciones / **Neto al Proveedor** / CxP Entidades; pago inmediato valida y anuncia el **neto**; payload `retentions` AUSENTE sin filas |
| `pages/purchases/PurchaseDetailPage.tsx` | Sección "Retenciones Aplicadas" (si `retentions.length>0` y `view_prices`): tabla con link a la entidad, badge "Revertida", total y neto acreditado |
| `pages/config/ConfigLayout.tsx` | Tab "Formulas" → **"Materiales (kg)"** |
| `components/layout/Sidebar.tsx` | Ídem en el child de Configuración |
| `types/sac-config.ts` | Removido `WILLARD_WORLD_LABELS` (muerto tras la reescritura — los labels viven en la página como `CLASSIFICATION_LABELS`) |
| `hooks/useSacConfig.ts` | Toast "Clasificacion Willard guardada" → "Clasificacion guardada" (C3) |

## 1b. Incremento W1 (walkthrough de Daniel, 2026-07-17) — "Materiales" general oculto en SAC

**Comentario origen:** con la página nueva, el tab top-level "Materiales" queda duplicado para SAC ("me genera ruido mantenerlo en sac, no es limpio"). Dirección elegida por Daniel: ocultarlo para SAC y enriquecer Materiales (kg).

- **`Sidebar.tsx`**: mecanismo nuevo `hideWhenOrgFlag` (inverso del `orgFlag` E1) — la entrada se oculta si el flag está encendido. **Degradación segura**: en loading/error `flagEnabled=false` → visible = status quo para las 3 orgs prod; solo la entrada que declara el campo consulta el query (extiende la regla de no-regresión E1 §5.1, no la viola). Aplicado a "Materiales" top-level. La ruta `/materials` queda viva (deep links + página Categorías intactos).
- **`FormulasPage.tsx` enriquecida a reemplazo completo**: columnas **Categoría** y **Unidad de Negocio**, campo **Descripción** en el form unificado (create + edit diff), botón **"Categorías"** → navega a la página de categorías existente (reutiliza, no duplica).
- ~~**No absorbido (declarado)**: export Excel del catálogo~~ **[Superseded por W2]**.

## 1c. Incremento W2 (walkthrough de Daniel, 2026-07-17) — pulidos de la página Materiales (kg)

1. **Columna "Unidad" separada** — la unidad salía inline en la celda Material ("BAT-08 - Batería 8 (unidad)"); ahora es columna propia (9 columnas, min-w 1120).
2. **Export Excel del catálogo** — `exportMaterialsKgExcel` en `excelExport.ts` (patrón aoa del repo): Código/Nombre/Unidad/Categoría/UN/Clasificación/También Compra/Factor/Desde/Por/Descripción. **Respeta los filtros activos** (misma promesa que los demás exports). Botón "Excel" en el header, disabled sin filas.
3. ~~**Badges inequívocos** — outline "+ Compra regular"~~ **[Superseded por W3 — ni así quedó claro]**.

## 1d. Incremento W3 (walkthrough de Daniel, 2026-07-17) — un badge por material + paleta + navegación de Categorías

1. ~~**UN solo badge por material**~~ **[Superseded por W4]** — Daniel aclaró la intención: **estandarizar, no ocultar**. Regla final (W4): cada clasificación tiene UNA sola forma canónica de badge (`ClassPill`, cero variantes outline/"+"); un material que aplica a ambos muestra **los dos tags idénticos al estándar** ("Postconsumo (baterías)" + "Compra regular"). El filtro "Compra regular" matchea por **tag visible** (incluye Willard+también-compra). Excel "También Compra" intacto.
2. **Paleta claramente distinta**: Drosses pasó de teal (casi idéntico al emerald de Compra regular) a **ámbar**. Paleta final: gris=Sin clasificar · verde=Compra regular · azul=Postconsumo · ámbar=Drosses.
3. **"Volver" de Categorías flag-aware**: el botón regresaba a `/materials` (la página general, oculta del sidebar SAC en W1) — costura de W1 que el barrido debió atrapar. Fix en `CategoriesPage`: con flag → "Materiales (kg)" (`CONFIG_FORMULAS`); sin flag → "Materiales" como siempre (degradación segura: loading/error = comportamiento prod). **Barrido de la clase completa**: `grep ROUTES.MATERIALS` en `src/` = 3 hits — la definición de ruta (App.tsx), la entrada de sidebar (ya oculta W1) y este botón (corregido). No queda ningún otro camino de un usuario SAC a la página vieja.

Gates re-corridos tras W1+W2+W3: tsc ✅ limpio · build ✅ 3.72s · backend intacto ✅.

## 1e. Incrementos W4 + W5 (walkthrough de Daniel, 2026-07-17)

**W4 — Badges estandarizados (aclaración de intención)**: cada clasificación tiene UNA forma canónica (`ClassPill`); un material que aplica a ambos muestra los DOS tags idénticos al estándar. Filtro "Compra regular" matchea por tag visible. (Ver §1d punto 1 superseded.)

**W5 — GAP operativo destapado por pregunta de Daniel ("¿dónde veo/configuro las entidades de retención?")**: el selector de **Pago de Pasivo** no mostraba las entidades `[Retenciones] X` — el backend E2 soporta `include_system=true` en `/third-parties/liabilities` (construido justo para esto, D9), pero el frontend nunca enviaba el parámetro → **las retenciones no se podían pagar desde la UI**. Mismo patrón que GAP-1 (backend listo, frontend sin cablear; el "verificado end-to-end" del informe E2 era por API/tests).
- Fix (frontend-only): `getLiabilities` acepta `include_system`; `useLiabilities` gana 3er parámetro `includeSystem` (query key propia); `MovementCreatePage` hace **dos fetches** — `liability_payment` usa la lista CON system entities, `expense_accrual` la lista SIN (causar gasto contra una entidad de retención sería incorrecto: sus saldos nacen solo de liquidaciones).
- **Prod-safe**: el filtro del endpoint es por behavior `liability`; los `[Prepago]` (otras system entities) no llevan esa categoría → `include_system=true` solo agrega `[Retenciones]`, que solo existen en orgs con flag.
- **Por diseño (sin cambio)**: las entidades `[Retenciones]` NO aparecen en la lista general de Terceros (`is_system_entity=True` se excluye en el service, patrón `[Prepago]` #13) — se llega a ellas por link directo, Balance Detallado (pasivo) y ahora el selector de pago. Mostrarlas en el tab Pasivos de Terceros requeriría backend (param en el path compartido) → fuera del alcance de este paquete; decisión pendiente si Daniel la quiere.
- **Forward-note (contrato)**: `types/third-party.ts` declara `is_system_entity: boolean` pero `ThirdPartyResponse` del backend NO lo serializa — campo fantasma (cero usos hoy). Corregir en un ciclo backend: exponer el campo (y entonces poder filtrar client-side) o quitarlo del type.

Gates tras W4+W5: tsc ✅ · build ✅ 3.83s · backend intacto ✅.

## 1f. Addendum §8 — Hogar de retenciones + municipios ICA (aprobado por Daniel, QA GO con F1/F2/F3)

Primer incremento del paquete que TOCA backend (decisión consciente de Daniel: mata el typo-duplicado de municipios desde la raíz). **Cero migraciones** — solo endpoints sobre datos existentes.

**Backend (4 archivos + 1 test nuevo):**
- `services/retention_entities.py` (NUEVO): módulo dueño del formato canónico `[Retenciones] X`. Extracción VERBATIM del get-or-create de `services/purchase.py` (`resolve_retention_entity`, matching H4 NFKD intacto — F3) + `list_retention_entities()` que parsea el formato propio a filas estructuradas `{retention_type, municipality, balance}` (orden retefuente → reteiva → ICA por municipio; nombres ajenos al formato se omiten defensivo).
- `services/purchase.py`: `_apply_retentions` delega en el módulo compartido (helpers privados eliminados). **Guardrail F3 verificado: los 16 tests D9 pasaron sin tocar** tras el refactor.
- `schemas/third_party.py`: `RetentionEntityCreate` (Literal["ica"] — solo ICA es creable a mano) + `RetentionEntityResponse`.
- `endpoints/third_parties.py`: `GET /third-parties/retention-entities` (permiso `third_parties.view` — F1) + `POST` (permiso `third_parties.create`), ambos `require_org_flag("kg_ledger_enabled")` per-endpoint → **403 sin flag incluso para admin**. Rutas estáticas declaradas ANTES de `/{third_party_id}`. POST idempotente: repetir "bogota" tras crear "Bogotá" devuelve la MISMA entidad (H4).
- `tests/test_retention_entities.py` (NUEVO, 7 tests): lista estructurada+orden+exclusión de `[Prepago]`/terceros normales · POST ICA idempotente H4 · POST no-ica → 422 · municipio vacío → 422 · flag-off → 403 GET+POST · RBAC viewer lee/no crea · aislamiento multi-org. **7/7 verdes.**

**Frontend (6 archivos):**
- `types/third-party.ts` + `services/thirdParties.ts`: tipos y llamadas GET/POST.
- `hooks/useMasterData.ts`: `useRetentionEntities(enabled)` — **F2: el parámetro `enabled` DEBE ser `flagEnabled("kg_ledger_enabled")`** (documentado en el hook; ambos consumidores lo cumplen) + `useCreateRetentionEntity()` (invalida `["third-parties"]`, prefijo que cubre la key nueva y las listas de pasivos).
- `LiabilitiesPage`: Card "Retenciones" debajo de los pasivos normales, **solo con flag** (F2: `useRetentionEntities(kgMode)` → para Costa/prod: cero requests nuevos, página idéntica). Filas con label amigable (ReteFuente / ReteIVA / ICA — Municipio), badge "Sistema" índigo, saldo contable, acciones **Pagar** (→ MovementCreate `liability_payment` preseleccionado, que ya incluye system entities por W5) y **Estado de Cuenta** (returnTo). Botón "Agregar Municipio ICA" (permiso `third_parties.create`) con dialog. Sin Causar/Desactivar (sus saldos nacen SOLO de liquidaciones). Empty state explica que ReteFuente/ReteIVA nacen solas al liquidar. Respeta search y "Mostrar inactivos". Mobile cards (390px).
- `PurchaseLiquidatePage`: municipio ICA pasa de **Input libre → Select** alimentado del GET (solo entidades ica activas) + item "+ Agregar municipio…" que abre dialog, crea (idempotente) y auto-selecciona en la fila. `useRetentionEntities(retentionsEnabled)` — mismo gate F2.

**Sin cambios**: `_apply_retentions` sigue aceptando cualquier string de municipio (el backend normaliza H4) — el Select es UX, no validación nueva; API compat total.

## 2. Decisiones de implementación (dentro del margen del plan)

1. **Semántica del badge**: perfil con `world=none` y `compra_regular=false` se muestra "Sin clasificar" (mismo badge que sin-perfil). Distinguirlos confundiría más de lo que aporta; guardar desde el form normaliza. (Micro-decisión declarada.)
2. **Fórmula de material que deja de ser Willard**: si se cambia la clasificación a Compra regular, la fórmula vigente NO se toca (append-only, dato histórico) — la columna Factor la sigue mostrando; la recepción no la usa.
3. **Comparación de factor en editar**: si los valores del form == fórmula vigente, NO se postea (evita versiones espurias). Cambio → POST nueva versión (append). 
4. **F2 aplicado ya** (era forward-note): "Nuevo Material" gated en `materials.create`, "Editar" en `materials.edit` — costo cero, coherente hoy y para E5.
5. **`rate`/`base` omitidos en v1** (opcionales informativos del schema) — si Q-07 revela que el cliente piensa en base×tarifa, se agregan en v1.1 sin tocar backend.
6. **Limpieza C3**: `WILLARD_WORLD_LABELS` eliminado (cero usos tras la reescritura); comentarios de código con "Clasificacion Willard" se conservan (referencian el nombre del modelo `material_kg_profile`, no son user-visible).
7. **Guard de unidad (F3 QA)**: en editar, unidad deshabilitada si hay fórmula vigente, con hint. El hardening backend queda rastreado en el plan (forward-note).

## 3. Gates

**Pre-addendum** (paquete UX puro, gate "cero backend" vigente entonces): tsc ✅ · build ✅ · backend intacto ✅ (`find -newermt` = cero) · suite `1258 passed (0:28:15)` ✅.

**Post-addendum** (el gate "cero backend" fue reemplazado conscientemente por "diff backend acotado" — decisión de Daniel, QA GO):

| Gate | Resultado |
|---|---|
| `npx tsc --noEmit` | ✅ exit 0 |
| `npm run build` | ✅ built in 3.88s |
| **Diff backend acotado al addendum** | ✅ 4 archivos (`services/retention_entities.py` NUEVO, `services/purchase.py` delegación, `schemas/third_party.py`, `endpoints/third_parties.py`) + `tests/test_retention_entities.py` — **cero migraciones** |
| **Guardrail F3** (16 tests D9 tras el refactor) | ✅ `16 passed in 33.06s` — H4/get-or-create intactos |
| Tests nuevos del addendum | ✅ 7/7 verdes |
| **Suite completa** | ✅ **`1265 passed in 1754.90s (0:29:14)`, exit 0** — baseline 1258 + 7 nuevos, cero regresiones |
| Smoke live (dev, SAC real) | ✅ GET parsea entidad real (ICA Barranquilla −$25.000) · POST "Soledad"/"soledad" → mismo id (H4 vivo, limpiado después) · Costa sin flag → **403 incluso superuser** |
| **Walkthrough Daniel** | ✅ **2026-07-17, 12/12 "todo correcto"** — incluye grupo Retenciones en Pasivos con saldos reales (ReteFuente −$5.000, ICA Barranquilla −$25.000), pago desde el grupo, Select de municipio con idempotencia H4, y **regresión Costa (F2)**: Pasivos idéntica + cero requests a `/retention-entities` en Network tab |

**Acordado durante el walkthrough (NO entra a este paquete)**: CC-006 — Retenciones v2 (catálogo configurable tipo+municipio+% con precálculo editable al liquidar, per Q-07). Requiere migración (`retention_configs`) → **ciclo corto inmediato POST-commit** por decisión de Daniel. El botón "Agregar Municipio ICA" actual es transicional y será reemplazado por "Agregar Retención" en v2.

## 4. Guía de walkthrough (los 8 casos del §6 del plan + QA-a/QA-b)

Pre-condición: dev con la SAC reseteada del walkthrough anterior (materiales BAT-PC/DRO-W/CHA-PB y cuentas kg pueden reusarse o partir de cero).

1. **C5/C3** — Config → **Materiales (kg)**: la tabla lista TODOS los materiales con su badge de Clasificación (CHA-PB aparece como Compra regular; un material sin perfil aparece "Sin clasificar"). Cero "Mundo Willard" en pantalla.
2. **C1** — "Nuevo Material": crear una batería nueva (ej. `BAT-08`, unidad=`unidad` en dropdown, categoría Baterias, UN Maquila, Clasificación Postconsumo, factor 9 kg/unidad) — **un solo formulario, un submit**. Verificar fila completa (badge + factor).
3. **C4** — En el mismo form: Clasificación default es "Compra regular" y el check "También entra por compra regular" solo aparece al elegir Willard.
4. **C2-SAC** — La unidad es dropdown (kg/unidad) y al cambiarla el bloque de factor cambia de tipo (kg/unidad ↔ %).
5. **Editar** — clic lápiz sobre BAT-PC: cambiar SOLO el factor (8→8.5) → guarda; historial (⏱) muestra ambas versiones (**QA-b**, append-only verificado). La unidad aparece bloqueada (tiene fórmula vigente).
6. **QA-a (fallo parcial)** — crear un material Willard con factor inválido forzado… (el form lo bloquea client-side; para forzar el fallo del paso 2/3 se puede desconectar el backend a mitad, o aceptar la verificación por lectura del código de toasts por paso). Alternativa realista: crear material Willard, y ANTES de guardar apagar el backend → el toast del paso correcto aparece y el material (si alcanzó a crearse) queda "Sin clasificar" → Editar recupera.
7. **Retenciones end-to-end** — nueva recepción tipo Compra (Chatarra 500 kg @ $2.000) → Compras → Liquidar: sección "Retenciones" visible; agregar ReteFuente $25.000 + ICA municipio "Barranquilla" $10.000 → Resumen muestra (−)$35.000 y **Neto al Proveedor $965.000**; liquidar con fecha; en el detalle: sección "Retenciones Aplicadas" con las 2 filas y neto; Terceros → aparece `[Retenciones] ReteFuente` y `[Retenciones] ICA Barranquilla` con saldo negativo (pasivo); estado de cuenta del proveedor muestra el crédito neto (+retención como evento sintético).
8. **Pago inmediato con retención** — otra liquidación con retención + switch pago inmediato: el copy anuncia "Se paga el neto: $X" y la validación de fondos usa el neto.
9. **Regresión sin flag** — cambiar a una org SIN flag (ej. Reciclajes de la Costa dev): Config NO muestra "Materiales (kg)"; liquidar una compra NO muestra sección Retenciones; flujo intacto.

**Addendum (hogar de retenciones + municipios ICA):**

10. **Grupo Retenciones en Pasivos** — Tesorería → Pasivos: card "Retenciones" debajo de los pasivos normales con las entidades del paso 7 (`ReteFuente`, `ICA — Barranquilla`), badge Sistema, saldos negativos (deuda). "Estado de Cuenta" abre el estado con los eventos sintéticos de retención. **"Pagar"** → formulario de Pago de Pasivo con la entidad preseleccionada → pagar los $25.000 de ReteFuente desde una cuenta → el saldo de la entidad vuelve a $0 y el pago aparece en su estado de cuenta.
11. **Selector de municipio** — nueva compra + liquidar con retención ICA: el municipio ya NO es texto libre — es Select con "Barranquilla" listado. Probar **"+ Agregar municipio…"** → escribir "Soledad" → se crea y queda seleccionado en la fila; en Pasivos aparece "ICA — Soledad" con saldo $0. **Idempotencia H4**: en el dialog de Pasivos, agregar "barranquilla" (minúscula, sin tilde) → toast con la entidad EXISTENTE "[Retenciones] ICA Barranquilla", sin duplicado.
12. **Regresión Costa (condición F2 de QA)** — org SIN flag: Pasivos se ve IDÉNTICA a hoy (sin card Retenciones) y en DevTools → Network **cero requests a `/third-parties/retention-entities`**; además `GET /retention-entities` por API directa responde 403 incluso como admin.

## 5. Fuera de alcance (sin cambios)

C6/C7/C4-exclusión (esperan Q-04/Q-05/Q-06 de Johana/Hugo) · C2 en el maestro compartido (backlog transversal) · hardening backend de unidad (F3, rastreado).
