# Plan — Remisión en los traslados + entrada propia del Talonario (SAC)

Versión 1.0 · 25-nov-2026 · autor: Eco Coder 2 · **nivel: lógica** · base: `7829411` (rama `coder-2/control-ajustes`)
Pedido: Daniel, 25-nov, vía el Coordinador (brief en `~/sac-evidencia/2026-11-25/traslados-remision/brief.md`).
Estado: **solo plan. No se construye hasta el GO de QA 2 y el OK de Daniel.**

---

## 0. Lo que se verificó antes de planear

| Pregunta | Hallazgo (leído en el código, no de memoria) |
|---|---|
| ¿Dónde está hoy el Talonario en el menú? | **En ninguna parte del menú lateral.** `Sidebar.tsx` no tiene la ruta. Se llega por un botón «Talonario de remisiones» dentro de *Salidas de control*: la lista (`ControlDispatchesPage.tsx:89-97`) y el detalle (`ControlDispatchDetailPage.tsx:140`). |
| ¿Qué permiso exige hoy? | **Ruta:** `App.tsx:192` → `FP flag="kg_ledger_enabled" permission="purchases.view"` + `P permission="sales.view"` (los dos, AND). **API:** `GET /remissions` → `require_permission("purchases.view", "sales.view")` (`control_dispatches.py:156-160`), router con `require_org_flag("kg_ledger_enabled")`. El botón se pinta solo con los dos permisos. |
| ¿Quedan fuera de `/remissions` los usuarios con alcance de recolector? | Sí: `/remissions` no está en `SCOPED_ENDPOINTS` (deny-by-default, #129), ni la ruta en `SCOPE_PATHS` del Sidebar. No cambia. |
| ¿Quién despacha un traslado y con qué permiso? | `POST /transfers` → `inventory.transfer`; `GET` lista y detalle → `inventory.view`; recibir/resolver → `inventory.transfer_receive`; anular → `inventory.transfer`. Router con `require_org_flag("two_step_transfers_enabled")`. |
| ¿Hay un PATCH del traslado? | **No.** Un traslado no se edita: se anula y se vuelve a registrar. Por eso la remisión (obligatoria al despachar) tampoco se podrá corregir sin anular. Ver pregunta O1. |
| ¿Quién llama a `dispatch` / `POST /transfers`? | App: solo el endpoint. Scripts: ninguno (`seed_demo_org` usa `/inventory/adjustments/warehouse-transfer`, otro camino; `archivar_org_sac` solo LEE `/transfers` y su fake no valida campos). Tests: ver §7. |
| ¿La migración toca tablas compartidas? | No: `transfers` es exclusiva de SAC (router detrás de `two_step_transfers_enabled`, que solo `seed_sac_org.py` enciende). |

---

## 1. Decisiones

### 1.1 De Daniel (brief, ya tomadas)

1. Los traslados llevan **remisión OBLIGATORIA al despachar**, también los intra-sede (molino). Con strip de espacios, igual que las Salidas de control. Los traslados ya registrados quedan sin remisión (columna nullable).
2. Remisión repetida: **avisa**, no bloquea (misma regla D8 de las Entradas y las Salidas de control).
3. El talonario es el mismo de las Entradas (Q-75). Que los traslados salgan del mismo talonario es **decisión de Daniel**, no respuesta de Johana: en el inventario va como lectura nuestra (c) y lo confirma él. El plan no lo escribe como respuesta del cliente.
4. Los traslados entran a `GET /remissions` como **tercera fuente**, con la misma `remission_key` (única definición de «misma remisión»), anulados incluidos (cubren su número) y huecos medidos contra toda la org.
5. Entrada propia «Talonario de remisiones» en el menú. Los traslados se muestran solo a quien tenga el permiso de inventario; el resto ve lo de hoy.
6. Formulario Nuevo Traslado con campo Remisión; lista y detalle del traslado muestran la columna.

### 1.2 Del plan (las confirma QA 2 o Daniel; ninguna cambia a las de arriba)

- **D-a — Quién ve las filas de traslado.** `inventory.view` (el permiso de leer traslados) **Y** el flag `two_step_transfers_enabled`. La vista sigue exigiendo `purchases.view` y `sales.view` como hoy; el permiso de inventario solo decide si salen las filas de traslado. Admin pasa por el bypass de `require_permission` (`is_admin`).
- **D-b — Ver y medir son dos cosas** (principio de C2 de #141: «el filtro decide qué filas se MUESTRAN; nunca qué números existen»). Las marcas «Repetida», los huecos y el aviso al capturar se calculan sobre **todos** los documentos de la org, vean o no el traslado. Así, quien no tiene `inventory.view` no recibe un hueco falso («Sin documento») donde en realidad hay un traslado. Costo declarado: ve un salto en la serie sin fila, o una «Repetida» sin su pareja visible; solo se revela que ese número existe. Ver O3.
- **D-c — Entrada en el menú.** Después de «Traslados», sección OPERACIONES, ícono `BookOpen`, ruta `ROUTES.REMISSION_BOOK`, `orgFlag: "kg_ledger_enabled"`. El Sidebar hoy solo sabe `permission` (un string; un arreglo es «alguno»). El Talonario necesita **los dos** (purchases.view Y sales.view), así que `NavItem` gana un campo opcional `permissionAll?: string[]` con su `every()`. Ningún otro ítem lo usa. Los dos botones actuales en Salidas de control se quedan.
- **D-d — `RemissionStr` se define una sola vez.** Hoy vive en `schemas/control_dispatch.py`. Pasa a `schemas/remission.py` y `control_dispatch.py` lo importa con el mismo nombre. Una sola definición de strip + `min_length=1` + `max_length=50`.
- **D-e — Sin PATCH ni «editar remisión».** Corregir una remisión mal digitada es anular el traslado y registrarlo de nuevo. No se agrega nada (ver O1).

---

## 2. Alcance

**Entra**

| Capa | Archivo | Cambio |
|---|---|---|
| Migración | `alembic/versions/a9c1e3f5b7d2_sac_remision_traslados.py` (padre `f8a0b2c4d6e9`, el head; ID libre, verificado con `ls`) | `transfers.remission_number String(50) NULL`. Aditiva. `downgrade`: `drop_column`. Sin gate de datos: no hay nada que pueda chocar. Sin índice (tabla chica; la llave se calcula en SQL como en las otras dos). |
| Modelo | `models/transfer.py` | `remission_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)` |
| Schema | `schemas/remission.py` (nuevo) | `RemissionStr`. |
| Schema | `schemas/transfer.py` | `TransferDispatchCreate.remission_number: RemissionStr` (obligatorio; `extra="forbid"` ya está). `TransferResponse.remission_number: Optional[str] = None`. |
| Schema | `schemas/control_dispatch.py` | importa `RemissionStr`; `RemissionBookItem.doc_type` gana `"transfer"`. |
| Servicio | `services/transfer.py` `dispatch` | guarda `remission_number=data.remission_number`; después del `flush`, `duplicate_remission_warning(..., exclude_transfer_id=transfer.id)` y el aviso va a `warnings`. |
| Servicio | `services/remission_book.py` | (1) `duplicate_remission_warning` gana `exclude_transfer_id` y un tercer bloque contra `Transfer` no anulado: «La remision X ya esta en el Traslado #n». (2) `_union` gana la tercera fuente (`doc_type='transfer'`, `transfer_number`, `remission_number`, `dispatch_date`, `status`). (3) `remission_book(..., show_transfers: bool = True)`: filtra las filas de traslado de la LISTA si es False; `dup_keys` y `all_nums` salen de la unión completa. (4) `_attach_materials`: tercera consulta por página sobre `TransferLine`. |
| Endpoint | `endpoints/transfers.py` | `_enrich` pasa `remission_number`. |
| Endpoint | `endpoints/control_dispatches.py` | `list_remissions` calcula `show_transfers = is_admin or "inventory.view" in user_permissions` y `get_org_setting(db, org, "two_step_transfers_enabled")`, y lo pasa. |
| Frontend | `types/transfer.ts`, `types/control-dispatch.ts` | `remission_number` (create: `string`; response: `string \| null`); `doc_type` gana `"transfer"`. |
| Frontend | `TransferCreatePage.tsx` | campo «Remisión *» (Input, `trim`), el botón no habilita sin ella; la clave va como **propiedad directa** del payload (`remission_number: remission.trim()`), no dentro de un spread (TS no revisa claves de más ahí). |
| Frontend | `TransfersPage.tsx`, `TransferDetailPage.tsx` | columna «Remisión» (y la línea en la tarjeta móvil); «—» en los traslados viejos. |
| Frontend | `RemissionBookPage.tsx` | etiqueta «Traslado #n», enlace a `TRANSFER_DETAIL`, badge de dirección «Traslado», `STATUS_LABELS` con los tres estados del traslado, subtítulo «Entradas, Salidas de control y Traslados…». |
| Frontend | `Sidebar.tsx` | entrada nueva + `permissionAll`. |

**No entra:** inventario, kg, saldos, maquila, P&L, costo promedio (el traslado no cambia nada de eso; los 56 tests de `test_sac_transfer_two_step.py` son la red). Salidas de Plomo sigue fuera del talonario (O3 de #141). No hay PATCH (O1). No se exporta a Excel.

---

## 3. Riesgos y cómo se cubre cada uno

| # | Riesgo | Cobertura |
|---|---|---|
| R1 | Volver obligatoria la remisión rompe a todo cliente de `POST /transfers`. | Medido por grep (§7): un solo llamador en `app/` (el endpoint), cero scripts, 3 archivos de tests con **28** puntos de `POST` (21 + 6 + 1), que se re-semantizan con un helper que da una remisión distinta por llamada (para que ningún `warnings` cambie por un aviso de repetida). Front y back salen en el MISMO deploy: un front viejo contra el back nuevo da 422 al despachar (igual que #132); lo dice el informe. |
| R2 | El aviso nuevo cambia el comportamiento de las Entradas y las Salidas de control (ahora también avisan contra un traslado). | Es lo pedido (mismo talonario). Se cubre en las dos direcciones (T4, T5). Sin traslados el tercer bloque no encuentra nada: las Entradas de las demás orgs quedan igual. |
| R3 | Un traslado intra-sede nace `received` en un salto; la remisión debe quedar igual. | T1 cubre cruzado e intra-sede. |
| R4 | `RemissionStr` movido: `min_length` cuenta caracteres y `"  "` pasaba (lección #100). | El strip va ANTES del `min_length` (como hoy); T2 manda `""` y `"   "`. |
| R5 | `permissionAll` toca el Sidebar compartido. | Campo opcional; solo lo declara el ítem nuevo; los demás evalúan igual. E2E: una org sin `kg_ledger_enabled` no muestra la entrada ni hace requests de más (registro de red igual al de antes). |
| R6 | Ocultar filas de traslado no debe esconder números ni marcas (D-b). | T12 mide la cobertura con un usuario sin `inventory.view`. |
| R7 | Ver filas de traslado exige el flag **y** el permiso; con un solo cambio se rompe en silencio. | El PAR (T13): con y sin `two_step_transfers_enabled`; T12: con y sin `inventory.view`, con un rol que tiene uno y no el otro. |
| R8 | La remisión de un traslado ya registrado es NULL; no debe romper listas, detalle ni el talonario. | T14. |
| R9 | `remission_key` y los huecos con la tercera fuente (anulados, texto, 20 dígitos). | Todo pasa por la MISMA `remission_key`; T7, T9, T10, T16 (y se reusan los 3 casos de frontera de #141). |
| R10 | Fricción operativa: el molino traslada seguido y ahora cada uno pide remisión. | Decisión de Daniel (#1 del brief). Se anota en el informe. |
| R11 | Alcance de recolector (#129): el talonario y los traslados no deben abrirse a Ingrid. | No se agrega nada a `SCOPED_ENDPOINTS` ni a `SCOPE_PATHS`; T15 afirma 403 en `/remissions` y en `POST /transfers`. |

---

## 4. Diseño del talonario con la tercera fuente

- **`_union`**: un tercer `select` de `Transfer` con las mismas columnas (`doc_type='transfer'`, `doc_id`, `doc_number=transfer_number`, `remission=remission_number`, `date=dispatch_date`, `status`, `inbound_type=NULL`). Los traslados con `remission_number` NULL quedan fuera de la lista por la regla de siempre (`remission_key(...).vacia`): no hay hueco ni repetida que inventar con ellos.
- **Ver vs. medir** (D-b): `base` (la lista) agrega `doc_type != 'transfer'` solo si `show_transfers` es False. `dup_keys` y `all_nums` se leen de la unión entera, sin ese filtro. `documents` y `total` cuentan lo que se ve.
- **Aviso al capturar** (`duplicate_remission_warning`): orden fijo Entrada → Salida de control → Traslado; el primero que choca nombra el documento. Las anuladas no cuentan para el aviso (anular y recapturar con la misma remisión es el camino de corregir un error); sí cubren su número en el talonario (huecos). Es la regla de hoy, extendida.
- **Materiales por fila**: una tercera consulta por página (`TransferLine.transfer_id IN (…)` unida a `Material.code`), nunca un join 1:N (#89/#93).
- **`inbound_without_remission`** no cambia (solo Entradas); los traslados viejos sin remisión no se cuentan (el brief los deja así).
- **Permiso en el endpoint**: `require_permission("purchases.view", "sales.view")` se queda; `show_transfers` se decide adentro con `org_context["is_admin"]` / `user_permissions` (patrón #102: la regla depende de un dato que la dependency estática no ve) y el flag con `get_org_setting`.

---

## 5. Frontend

- **Menú**: entrada «Talonario de remisiones» después de «Traslados», con `permissionAll: ["purchases.view", "sales.view"]` y `orgFlag: "kg_ledger_enabled"`. Un usuario con alcance de recolector no la ve (`SCOPE_PATHS` no la lleva).
- **Nuevo Traslado**: campo «Remisión *» junto a la fecha. El botón «Registrar/Despachar» se habilita solo con remisión (trim) además de lo de hoy. El aviso de repetida llega en `warnings` y ya se muestra como toast ámbar (`useDispatchTransfer → showWarnings`), sin código nuevo.
- **Lista y detalle**: columna «Remisión» en la tabla (desktop) y línea en la tarjeta (390); el detalle la muestra en el bloque de datos. «—» si es NULL.
- **Talonario**: fila «Traslado #n» con enlace al detalle, badge «Traslado» (color propio, distinto de Entra/Sale), estado en español: Por recibir / En discrepancia / Recibido / Anulada.
- **Responsive**: 390 sin scroll horizontal; el campo nuevo es `w-full`.
- **Decimal/Tipos**: no hay Decimal nuevo. `remission_number` es texto; las remisiones largas viajan como texto.

---

## 6. Tests nuevos — `backend/tests/test_sac_remision_traslados.py` (28)

Todo se lee **por HTTP** (un warning se prueba en la respuesta, lección de #100/#141). Los permisos se prueban con roles que tienen uno y no el otro, más una lectura en 200 como control positivo.

| T | Qué prueba | # |
|---|---|---|
| T1 | Despachar con remisión (con espacios) la guarda sin ellos y la devuelve en el POST, la lista y el detalle: cruzado **e** intra-sede; `warnings == []` | 2 |
| T2 | Obligatoria: ausente, `""` y `"   "` dan 422 que nombra el campo | 3 |
| T3 | Una clave mal escrita (`remision_number`) da 422 (`extra="forbid"`) | 1 |
| T4 | El traslado con la remisión de una Entrada / de una Salida de control / de otro traslado avisa en `warnings` y **nombra** el documento («Entrada #n», «Salida de control #n», «Traslado #n»); responde 201 | 3 |
| T5 | Al revés: la Entrada (create **y** update) y la Salida de control creadas con la remisión de un traslado avisan «Traslado #n» | 3 |
| T6 | Un traslado anulado no cuenta para el aviso | 1 |
| T7 | La llave: «0016300» y «16300» chocan entre traslado y Entrada; «12.0» no choca con «12» | 2 |
| T8 | El talonario trae el traslado como tercera fuente: tipo, número, remisión, fecha, estado y materiales | 1 |
| T9 | Un traslado anulado sigue en el talonario y cubre su número (sin hueco falso entre sus vecinos) | 1 |
| T10 | Los huecos se miden contra toda la org con un traslado en medio, y un filtro por fecha no crea huecos falsos | 1 |
| T11 | «Repetida» entre un traslado y una Entrada en las dos filas; una anulada no cuenta | 1 |
| T12 | Permiso: sin `inventory.view` no salen las filas de traslado pero el número queda **cubierto** (sin hueco falso) y la marca «Repetida» se conserva; con `inventory.view` salen; un rol con `inventory.view` y sin `sales.view` recibe 403 | 3 |
| T13 | El PAR del flag: con `kg_ledger_enabled` sin `two_step_transfers_enabled` las filas de traslado no salen aunque el usuario tenga `inventory.view` (la fila existe, cargada por el ORM); con el flag, sí | 2 |
| T14 | Un traslado ya registrado, sin remisión: lista y detalle devuelven `null` (sin 500), no sale en el talonario y no entra a `inbound_without_remission` | 2 |
| T15 | Alcance de recolector: `/remissions` y `POST /transfers` dan 403 | 1 |
| T16 | Orden: una remisión de texto de un traslado va al final en los dos sentidos, como las otras | 1 |

Re-semantización (no suman tests): `_dispatch` y los `POST` directos de `test_sac_transfer_two_step.py` (21), `test_pnl_by_warehouse.py` (6) y `test_sac_planta_proveedor.py` (1) pasan una remisión única por llamada. La lista sale del grep en el momento de construir; no de memoria.

---

## 7. Set dirigido (por grep del SÍMBOLO y de los importadores de los módulos)

Comandos, corridos en el worktree sobre `7829411` (se repiten al construir y se pegan en el log):

```
cd backend
# A. el símbolo de la remisión
grep -rlE "remission_book|duplicate_remission_warning|remission_key|remission_order|RemissionStr|/remissions|remissions_router" tests app scripts
# B. el campo en los tests
grep -rl "remission_number\|remission" tests
# C. traslados
grep -rlE "services\.transfer|transfer_service|/api/v1/transfers|TransferDispatchCreate|models\.transfer|schemas\.transfer|\"/transfers\"" tests scripts app
# D. importadores de otros test_* (lección C2 de #141: el grep del símbolo no los ve)
grep -rnE "^from tests\.test_|^from \.test_|^import tests\.test_" tests
```

Resultado y set final (19 archivos existentes + el nuevo):

- A + B: `test_sac_documentos_control`, `test_sac_entrada_sin_proveedor`, `test_sac_entradas_remision`, `test_sac_factor_willard`, `test_sac_impuestos_ventas`, `test_sac_pdf_remision_compra`, `test_sac_planta_proveedor`, `test_tax_rate_tope`, `test_willard_deliveries`.
- C: `test_advisory_locks`, `test_archivar_org_sac`, `test_pnl_by_warehouse`, `test_sac_transfer_two_step` (+ los de arriba).
- D (importan de un archivo del set, o son importados por él): `test_inbound_orders` (lo importa `test_sac_factor_willard`), `test_seed_sac_settings` y `test_seed_sac_retention_configs` (importan `test_archivar_org_sac`), `test_redondeo_precio_compras` (importa `test_sac_entrada_sin_proveedor`).
- Guardas del árbol, siempre: `test_reloj_de_negocio` (rglob de `frontend/src`), `test_advisory_locks` (ya está), `test_crucible_charges`.

**Predicción escrita antes**: `--collect-only` de los 19 existentes sobre `7829411` = **655**. El archivo nuevo suma **28** (§6). Los tests re-semantizados no cambian de número. Predicción del set dirigido: **683**. Se compara con `--collect-only` del set final y con la corrida.

Frontend: sin infra de test. `tsc`, `eslint` (37 = techo) y `build`, más un e2e con Playwright (§9).
Suite completa: **diferida al checkpoint** (regla del 19-nov). La predicción del checkpoint saldrá de `git diff --name-only 7e2ee4f -- backend/tests`, no de memoria.

---

## 8. Matriz de plantado (commiteada ANTES de plantar; no se reescribe — lo que falte va en una adenda)

Se planta en una copia sacada con `git archive` del commit de esta matriz, no en el worktree; un defecto por vez, con el conteo de ocurrencias afirmado; `PYTHONDONTWRITEBYTECODE=1`; restaurar y verificar el sha256. Se corre `test_sac_remision_traslados.py` **entero**, para ver también lo que cae de más, y el script exige `exit 0` antes de leer la diagonal. «= {…}» es exacto; «≥ {…}» es «al menos» (vía compartida). La dirección peligrosa es un test predicho que NO cae.

| P | Defecto (archivo · cambio) | Debe caer |
|---|---|---|
| P1 | `schemas/transfer.py` · `remission_number: RemissionStr` → `Optional[RemissionStr] = None` (opcional) | ≥ {T2} |
| P2 | `schemas/remission.py` · `strip_whitespace=True` → `False` | ≥ {T1, T2} y los de control (`t19_remision_obligatoria`, `t19_el_patch_no_la_deja_vaciar`) |
| P3 | `services/transfer.py` · se quita `remission_number=data.remission_number` (se pierde) | ≥ {T1, T8, T11} |
| P4 | `services/transfer.py` · se quita `warnings.append(dup)` (se calcula y no llega) | = {T4 ×3} |
| P5 | `services/transfer.py` · se quita `exclude_transfer_id=transfer.id` (se avisa a sí mismo) | ≥ {T1, T4 ×3} |
| P6 | `services/remission_book.py` · `duplicate_remission_warning`: se quita el bloque de traslados | ≥ {T4 (traslado vs traslado), T5 ×3} |
| P7 | ídem · se quita `Transfer.status != "annulled"` | = {T6} |
| P8 | ídem · la llave del traslado sin normalizar (`lower(trim)` en vez de `remission_key`) | ≥ {T7} |
| P9 | `remission_book._union` · sin la tercera fuente | ≥ {T8, T9, T10, T11, T13, T16} |
| P10 | `remission_book` · `show_transfers` ignorado (siempre se ven) | = {T12 sin permiso, T13 sin flag} |
| P11 | `remission_book` · `show_transfers` siempre False | ≥ {T8, T12 con permiso, T13 con flag} |
| P12 | `remission_book` · `dup_keys` y `all_nums` salen de las filas visibles | = {T12 (cobertura y «Repetida» sin permiso)} |
| P13 | `endpoints/control_dispatches.py` · `show_transfers` no mira el flag | = {T13 sin flag} |
| P14 | `endpoints/control_dispatches.py` · `show_transfers` no mira el permiso | = {T12 sin permiso} |
| P15 | `remission_book._attach_materials` · sin la rama de traslados | ≥ {T8} |
| P16 | `remission_book` · `base` excluye `status == "annulled"` de los traslados | ≥ {T9} |
| P17 | `schemas/control_dispatch.py` · `RemissionBookItem.doc_type` sin `"transfer"` (500 al serializar) | ≥ {T8, T9, T10, T11, T16} |
| P18 | `services/collector_scope.py` · `SCOPED_ENDPOINTS` gana `control_dispatches.list_remissions` | = {T15} |
| P19 | `endpoints/transfers.py` · `_enrich` sin `remission_number` (el POST lo guarda y la respuesta no lo devuelve) | ≥ {T1, T14} |
| P20 | `remission_book` · `inbound_without_remission` cuenta también los traslados sin remisión | = {T14 (contador)} |

**Frontend (e2e, mismo método, contra el árbol servido):**

| P | Defecto | Debe caer |
|---|---|---|
| PF1 | `Sidebar.tsx` · `permissionAll` evaluado como «alguno» | = {E2 (usuario con una sola de las dos)} |
| PF2 | `Sidebar.tsx` · la entrada sin `orgFlag` | = {E2 (org sin el flag)} |
| PF3 | `RemissionBookPage.tsx` · el enlace del traslado va a `INBOUND_DETAIL` | = {E3} |
| PF4 | `TransferCreatePage.tsx` · el botón no exige la remisión | = {E4} |
| PF5 | `TransferCreatePage.tsx` · el payload manda `remision_number` (clave mal escrita) | = {E4: el POST da 422 y el toast lo dice} |

Cada fila se mide por su NÚMERO de caídas y no solo por si cae; una predicción que falle se anota con su causa (las de «vía compartida» caen de más y es la dirección barata).

---

## 9. Gates, en el orden del flujo con QA (#CLAUDE.md, 17-nov)

1. **Este plan → GO de QA 2 → OK de Daniel.** No se construye antes. Si el plan se edita después del GO, vuelve a QA con el sha en el acto.
2. Construcción: código y tests nuevos; el autor corre solo el lint y los tests nuevos. Migración en dev (5434) y test (5433, la BD de este coder).
3. **QA pasada 1**: el delta como patch con su sha256, la base y el sha256 de cada archivo; el árbol queda quieto.
4. Correcciones; QA relee el delta.
5. Gates: dirigidas del §7 (predicción escrita antes), plantado del §8, `ruff`, `tsc`, `eslint`, `build`, `schema_parity_check.py` (DIFF CERO esperado, +0 divergencias), migración up/down/up a archivo, smoke con POST real contra un backend arrancado DESPUÉS del último cambio de `app/` (con su procedencia impresa), y el e2e a 1440 y 390 con registro de red de una org sin flag (cero requests de más).
6. QA pasada 2 → OK de commit → commit en mi rama. Integración a develop y deploy: los hace el Coordinador con el OK de Daniel.

**Golden: no aplica — medido, no argumentado.** Comandos que se repiten al construir y se pegan en el log:
- `grep -nE '^\s+\("' scripts/golden_capture.py` sobre `CAPTURES`: **14 entradas / 11 rutas únicas**, todas de `/reports/*`, `/money-accounts`, `/warehouses`, `/money-movements`. Ninguna es `/transfers`, `/remissions` ni `/inbound-orders`.
- `grep -n "Transfer" app/services/reports.py`: solo cadenas de tipos de movimiento («Transferencia entre terceros»); `reports.py` no importa el modelo `Transfer`.
- El cambio de `app/` agrega una columna a una tabla exclusiva de SAC, un tercer bloque en una lectura de SAC y un campo en un schema de SAC. No cambia ningún valor ni forma de lo que el golden captura, así que daría «0 diffs y 0 aditivas»: el resultado que #110 mostró que no distingue «no rompió nada» de «comparó viejo contra viejo». La red es el PAR de T12/T13 y los 56 tests existentes de traslados.

---

## 10. Preguntas para Daniel (no frenan el plan; la recomendada es la del plan)

- **O1 — Corregir una remisión.** Hoy no hay forma de editar un traslado. Una remisión mal digitada obliga a anular y registrar de nuevo (se revierte el inventario). **(Recomendado)** no agregar nada ahora y anotarlo; si pasa más de una vez, un `PATCH` solo de la remisión (sin tocar inventario) es un ciclo corto. Alternativa: incluirlo en este ciclo.
- **O2 — Quién abre el Talonario.** Hoy `purchases.view` Y `sales.view`. **(Recomendado)** dejarlo igual: quien tiene solo `inventory.view` no ve el Talonario. Alternativa: abrirlo también con `inventory.view` solo (vería solo los traslados).
- **O3 — Números cubiertos por un documento que el usuario no ve** (D-b). **(Recomendado)** medir contra toda la org: se ve un salto sin hueco falso. Alternativa: medir solo contra lo visible, que puede mostrar un «Sin documento» donde hay un traslado.

## 11. Fuera de este ciclo (se anota, no se hace)

- El inventario (`inventario-preguntas-cliente.md`) y CLAUDE.md los escribe el Coordinador al integrar: la lectura (c) de Q-75 «los traslados salen del mismo talonario» (decisión de Daniel, no respuesta de Johana) y la decisión nueva.
- Los traslados de Salidas de Plomo y las conversiones del crisol no llevan remisión de este talonario.
- Una venta no tiene campo de remisión (anotado en #141); sigue como hueco.
