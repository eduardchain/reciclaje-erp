# Plan — Remisión en los traslados + entrada propia del Talonario (SAC)

Versión 1.3 · 25-nov-2026 · autor: Eco Coder 2 · **nivel: lógica** · base: `7829411` (rama `coder-2/control-ajustes`)
Pedido: Daniel, 25-nov, vía el Coordinador (brief en `~/sac-evidencia/2026-11-25/traslados-remision/brief.md`).
Estado: **solo plan. No se construye hasta el GO de QA 2 y el OK de Daniel.**

v1.3: aplica C1–C4 del veredicto de QA 2 sobre la v1.2 (`31f082d`; `~/sac-evidencia/2026-11-25/qa-2-traslados-remision/veredicto_plan_v12_31f082d.md`): TP12 y P31 (traslado viejo con remisión NULL), el control de TP8 escrito por tabla con P32 y P33, P24 a «≥ {TP1}», y T15 con las tres rutas con P18b y P18c. El diseño no cambia. Números: tests nuevos 48, dirigido 703. QA 2 revisa solo el delta contra `31f082d`.

v1.2: Daniel respondió O1–O3 (vía el Coordinador, 25-nov): O2 y O3 con la recomendada y **O1 = incluir el `PATCH` de la remisión en este ciclo** (contra la recomendada). Esta versión agrega solo eso (§1.1 punto 7, D-e, D-f, el PATCH en §2–§9) y una corrección que salió al diseñarlo (D-f, la caché). Lo de v1.1 no cambia, salvo los números que el PATCH mueve: tests nuevos 47, dirigido 702, filas P21–P30 y PF6–PF9, caso e2e E5. QA 2 lee esta v1.2 directamente.

v1.1: aplica C1 y C2 y las observaciones O1–O5 del veredicto de QA 2 sobre `4efead9` (`~/sac-evidencia/2026-11-25/qa-2-traslados-remision/veredicto_plan_4efead9.md`). El diseño no cambia: se parte P12, se define el e2e, y se corrigen cuatro afirmaciones del texto.

---

## 0. Lo que se verificó antes de planear

| Pregunta | Hallazgo (leído en el código, no de memoria) |
|---|---|
| ¿Dónde está hoy el Talonario en el menú? | **En ninguna parte del menú lateral.** `Sidebar.tsx` no tiene la ruta. Se llega por un botón «Talonario de remisiones» en **tres** pantallas: la lista de *Salidas de control* (`ControlDispatchesPage.tsx:89-97`), el detalle de una Salida de control (`ControlDispatchDetailPage.tsx:140`) y la lista de *Entradas* (`InboundOrdersPage.tsx:507`, con `unscoped && sales.view`). |
| ¿Qué permiso exige hoy? | **Ruta:** `App.tsx:192` → `FP flag="kg_ledger_enabled" permission="purchases.view"` + `P permission="sales.view"` (los dos, AND). **API:** `GET /remissions` → `require_permission("purchases.view", "sales.view")` (`control_dispatches.py:156-160`), router con `require_org_flag("kg_ledger_enabled")`. El botón se pinta solo con los dos permisos. |
| ¿Quedan fuera de `/remissions` los usuarios con alcance de recolector? | Sí: `/remissions` no está en `SCOPED_ENDPOINTS` (deny-by-default, #129), ni la ruta en `SCOPE_PATHS` del Sidebar. No cambia. |
| ¿Quién despacha un traslado y con qué permiso? | `POST /transfers` → `inventory.transfer`; `GET` lista y detalle → `inventory.view`; recibir/resolver → `inventory.transfer_receive`; anular → `inventory.transfer`. Router con `require_org_flag("two_step_transfers_enabled")`. |
| ¿Hay un PATCH del traslado? | **No hoy.** Un traslado no se edita: se anula y se vuelve a registrar (anular uno recibido revierte kg, merma y maquila). Daniel decidió agregar uno **solo para la remisión** (§1.1 punto 7). Los otros dos documentos del talonario sí se editan: la Salida de control (`control_dispatch.py:88-89`: anulada → 400 «no se edita») y la Entrada (`inbound_order.py:1930`, `update`: una anulada «no se edita» — responde 404 «Orden no encontrada», D18). |
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
7. (O1, 25-nov, contra la recomendada del plan) **`PATCH` de la remisión del traslado en este ciclo**: no toca inventario, kg, merma ni maquila; mismo strip y misma obligatoriedad (no se puede vaciar); «Repetida» como aviso en la respuesta HTTP; botón «Corregir remisión» en el detalle. El permiso y los estados permitidos los decide el plan (D-e).
8. (O2, O3) El Talonario se abre como hoy (`purchases.view` Y `sales.view`), y los huecos y las marcas se miden contra toda la org.

### 1.2 Del plan (las confirma QA 2 o Daniel; ninguna cambia a las de arriba)

- **D-a — Quién ve las filas de traslado.** `inventory.view` (el permiso de leer traslados) **Y** el flag `two_step_transfers_enabled`. La vista sigue exigiendo `purchases.view` y `sales.view` como hoy; el permiso de inventario solo decide si salen las filas de traslado. Admin pasa por el bypass de `require_permission` (`is_admin`).
- **D-b — Ver y medir son dos cosas** (principio de C2 de #141: «el filtro decide qué filas se MUESTRAN; nunca qué números existen»). Las marcas «Repetida», los huecos y el aviso al capturar se calculan sobre **todos** los documentos de la org, vean o no el traslado. Así, quien no tiene `inventory.view` no recibe un hueco falso («Sin documento») donde en realidad hay un traslado. Costo declarado: ve un salto en la serie sin fila, o una «Repetida» sin su pareja visible; solo se revela que ese número existe. Ver O3.
- **D-c — Entrada en el menú.** Después de «Traslados», sección OPERACIONES, ícono `BookOpen`, ruta `ROUTES.REMISSION_BOOK`, `orgFlag: "kg_ledger_enabled"`. El Sidebar hoy solo sabe `permission` (un string; un arreglo es «alguno»). El Talonario necesita **los dos** (purchases.view Y sales.view), así que `NavItem` gana un campo opcional `permissionAll?: string[]` con su `every()`. Ningún otro ítem lo usa. Los tres botones actuales (lista y detalle de Salidas de control, lista de Entradas) se quedan.
- **D-d — `RemissionStr` pasa a un módulo compartido.** Hoy vive en `schemas/control_dispatch.py`. Pasa a `schemas/remission.py`; `control_dispatch.py` y `transfer.py` lo importan. **Quedan dos definiciones, no una:** `schemas/willard_delivery.py:77` tiene su propia copia inline de las mismas restricciones (strip + `min_length=1` + `max_length=50`) y no se toca: Salidas de Plomo está fuera del talonario y fuera de este ciclo. Si alguna vez cambian las restricciones, se cambian en los dos sitios.
- **D-e — El `PATCH` de la remisión.** `PATCH /api/v1/transfers/{id}/remission`, cuerpo `{"remission_number": "..."}` (`extra="forbid"`, `RemissionStr`: strip antes de `min_length`, obligatorio, no se puede vaciar ni mandar `null`).
  - **Permiso: `inventory.transfer`**, el mismo de despachar y anular. Argumento: la remisión es el número del papel que acompañó el despacho, así que corregirla es una corrección de quien despacha. `inventory.view` no basta (es de lectura) y `inventory.transfer_receive` tampoco (quien recibe en el destino no es quien despacha; recibir no incluye reescribir el documento de salida). No se crea un permiso nuevo (política D4: un permiso nuevo exige migración y no se asigna a roles).
  - **Estados permitidos: `dispatched`, `held_discrepancy` y `received`.** La remisión no cambia ningún efecto, y un traslado recibido es justamente donde se descubre el error (el destino compara el papel con el sistema). Incluye los intra-sede, que nacen `received`.
  - **Anulado: 400, no se corrige** (decisión del plan, argumentada). Es lo que hacen los otros dos documentos del talonario (Salida de control: 400 «está anulada — no se edita»; Entrada: 404, «anuladas no se editan», D18). Un anulado es un registro congelado con su razón y su autor, y su número **cubre** lo que cubrió al anularse (D-b y T9); cambiarlo después movería qué números están cubiertos con efecto retroactivo. **Costo declarado:** si alguien anula un traslado por una remisión mal digitada, el número equivocado sigue cubierto por el anulado y el correcto aparecería como hueco hasta que se registre el traslado nuevo; el camino sano es corregir con este PATCH **antes** de anular. El mensaje del 400 lo dice.
  - **Sin cambio = sin aviso.** Si la remisión nueva (con strip) es igual a la guardada, responde 200 igual que hoy y no avisa (igual que `control_dispatch.update`, que avisa solo si cambió). La guardada puede ser NULL (traslados anteriores a este ciclo): se compara contra `(transfer.remission_number or "").strip()`, como `control_dispatch`; un traslado viejo siempre «cambia» al primer PATCH (TP12).
  - **«Repetida»**: `duplicate_remission_warning(..., exclude_transfer_id=transfer.id)` después del `flush`, el mismo orden Entrada → Salida de control → Traslado, y el aviso va en `warnings` de la respuesta. Se avisa, no se bloquea.
  - **Sin efectos**: el servicio solo escribe `transfers.remission_number`. No llama a `_recompute_status`, no toca líneas, movimientos, kg, ajustes, MCH ni pares de maquila. No toma locks de numeración (no hay secuencia). Un traslado de otra org o inexistente da 404 (`_get_or_404` por org).
  - **Sin historial**: no se guarda el valor anterior (las Entradas y las Salidas de control tampoco lo guardan). Se anota en §11.
- **D-f — La caché del talonario (corrección a v1.1, hallada al diseñar el PATCH).** `invalidateAfterTransfer` invalida `transfers`, `kg-ledger`, `money-movements`, `reports` e inventario, pero **no `["remissions"]`**, y el talonario ahora muestra traslados: despachar, anular o corregir la remisión de un traslado dejaría la vista vieja hasta recargar. Las Entradas (`invalidateAfterInboundOrder`) y las Salidas de control (`invalidateAfterControlDispatch`) ya invalidan `["remissions"]`. Se agrega esa línea a `invalidateAfterTransfer` y el PATCH usa el mismo helper (#27: un helper, una regla). Se mide en el e2e (E3 y E5, PF9).

---

## 2. Alcance

**Entra**

| Capa | Archivo | Cambio |
|---|---|---|
| Migración | `alembic/versions/a9c1e3f5b7d2_sac_remision_traslados.py` (padre `f8a0b2c4d6e9`, el head; ID libre, verificado con `ls`) | `transfers.remission_number String(50) NULL`. Aditiva. `downgrade`: `drop_column`. Sin gate de datos: no hay nada que pueda chocar. Sin índice (tabla chica; la llave se calcula en SQL como en las otras dos). |
| Modelo | `models/transfer.py` | `remission_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)` |
| Schema | `schemas/remission.py` (nuevo) | `RemissionStr`. |
| Schema | `schemas/transfer.py` | `TransferDispatchCreate.remission_number: RemissionStr` (obligatorio; `extra="forbid"` ya está). `TransferResponse.remission_number: Optional[str] = None`. **PATCH:** `TransferRemissionUpdate` con `remission_number: RemissionStr` (obligatorio) y `extra="forbid"`. |
| Schema | `schemas/control_dispatch.py` | importa `RemissionStr`; `RemissionBookItem.doc_type` gana `"transfer"`. |
| Servicio | `services/transfer.py` `dispatch` | guarda `remission_number=data.remission_number`; después del `flush`, `duplicate_remission_warning(..., exclude_transfer_id=transfer.id)` y el aviso va a `warnings`. |
| Servicio | `services/transfer.py` `update_remission` (nuevo) | `_get_or_404` por org; 400 si está anulado; si el valor (con strip) cambió, lo escribe, hace `flush`, calcula el aviso con `exclude_transfer_id` y hace `commit`; devuelve `(transfer, warnings)`. Solo escribe esa columna. |
| Servicio | `services/remission_book.py` | (1) `duplicate_remission_warning` gana `exclude_transfer_id` y un tercer bloque contra `Transfer` no anulado: «La remision X ya esta en el Traslado #n». (2) `_union` gana la tercera fuente (`doc_type='transfer'`, `transfer_number`, `remission_number`, `dispatch_date`, `status`). (3) `remission_book(..., show_transfers: bool = True)`: filtra las filas de traslado de la LISTA si es False; `dup_keys` y `all_nums` salen de la unión completa. (4) `_attach_materials`: tercera consulta por página sobre `TransferLine`. |
| Endpoint | `endpoints/transfers.py` | `_enrich` pasa `remission_number`. **PATCH:** `PATCH /{transfer_id}/remission` con `require_permission("inventory.transfer")`, responde `TransferResponse` con `warnings` (el router ya exige `two_step_transfers_enabled`). |
| Endpoint | `endpoints/control_dispatches.py` | `list_remissions` calcula `show_transfers = is_admin or "inventory.view" in user_permissions` y `get_org_setting(db, org, "two_step_transfers_enabled")`, y lo pasa. |
| Frontend | `types/transfer.ts`, `types/control-dispatch.ts` | `remission_number` (create: `string`; response: `string \| null`); `doc_type` gana `"transfer"`. |
| Frontend | `TransferCreatePage.tsx` | campo «Remisión *» (Input, `trim`), el botón no habilita sin ella; la clave va como **propiedad directa** del payload (`remission_number: remission.trim()`), no dentro de un spread (TS no revisa claves de más ahí). |
| Frontend | `TransfersPage.tsx`, `TransferDetailPage.tsx` | columna «Remisión» (y la línea en la tarjeta móvil); «—» en los traslados viejos. **PATCH:** en el detalle, botón «Corregir remisión» (con `inventory.transfer` y el traslado no anulado) que abre un diálogo con la remisión actual, el botón Guardar deshabilitado si está vacía o igual a la actual (con trim), y los avisos de «Repetida» como toast ámbar. |
| Frontend | `types/transfer.ts`, `services/transfers.ts`, `hooks/useTransfers.ts` | `TransferRemissionUpdate`; `transferService.updateRemission(id, remission_number)` con la clave como propiedad directa; `useUpdateTransferRemission` (toast de éxito, `showWarnings`, `invalidateAfterTransfer`). |
| Frontend | `utils/queryInvalidation.ts` | `invalidateAfterTransfer` gana `qc.invalidateQueries({ queryKey: ["remissions"] })` (D-f). |
| Frontend | `RemissionBookPage.tsx` | etiqueta «Traslado #n», enlace a `TRANSFER_DETAIL`, badge de dirección «Traslado», `STATUS_LABELS` con los tres estados del traslado, subtítulo «Entradas, Salidas de control y Traslados…». |
| Frontend | `Sidebar.tsx` | entrada nueva + `permissionAll`. |

**No entra:** inventario, kg, saldos, maquila, P&L, costo promedio (el traslado no cambia nada de eso; los 56 tests de `test_sac_transfer_two_step.py` son la red, y TP8 compara tablas antes y después del PATCH). Salidas de Plomo sigue fuera del talonario (O3 de #141). No hay otro `PATCH` del traslado: solo la remisión (notas, fecha, bodegas y líneas siguen sin editarse). No se exporta a Excel.

---

## 3. Riesgos y cómo se cubre cada uno

| # | Riesgo | Cobertura |
|---|---|---|
| R1 | Volver obligatoria la remisión rompe a todo cliente de `POST /transfers`. | Medido por grep (§7): un solo llamador en `app/` (el endpoint), cero scripts. En los tests, 3 archivos y **6 sitios de edición**: los helpers `_dispatch` de `test_sac_transfer_two_step.py` (40 llamadas) y de `test_sac_planta_proveedor.py` (4 llamadas) y los 3 `POST` directos (`test_sac_transfer_two_step.py` L305 y L364, `test_pnl_by_warehouse.py` L143). Cada uno pasa una remisión distinta por llamada, para que ningún `warnings` cambie por un aviso de repetida. Ningún negativo espera 422 por otra causa. Front y back salen en el MISMO deploy: un front viejo contra el back nuevo da 422 al despachar (igual que #132); lo dice el informe. |
| R2 | El aviso nuevo cambia el comportamiento de las Entradas y las Salidas de control (ahora también avisan contra un traslado). | Es lo pedido (mismo talonario). Se cubre en las dos direcciones (T4, T5). Sin traslados el tercer bloque no encuentra nada: las Entradas de las demás orgs quedan igual. |
| R3 | Un traslado intra-sede nace `received` en un salto; la remisión debe quedar igual. | T1 cubre cruzado e intra-sede. |
| R4 | `RemissionStr` movido: `min_length` cuenta caracteres y `"  "` pasaba (lección #100). | El strip va ANTES del `min_length` (como hoy); T2 manda `""` y `"   "`. |
| R5 | `permissionAll` toca el Sidebar compartido. | Campo opcional; solo lo declara el ítem nuevo; los demás evalúan igual. E2E: una org sin `kg_ledger_enabled` no muestra la entrada ni hace requests de más (registro de red igual al de antes). |
| R6 | Ocultar filas de traslado no debe esconder números ni marcas (D-b). | T12 mide la cobertura con un usuario sin `inventory.view`. |
| R7 | Ver filas de traslado exige el flag **y** el permiso; con un solo cambio se rompe en silencio. | El PAR (T13): con y sin `two_step_transfers_enabled`; T12: con y sin `inventory.view`, con un rol que tiene uno y no el otro. |
| R8 | La remisión de un traslado ya registrado es NULL; no debe romper listas, detalle ni el talonario. | T14. |
| R9 | `remission_key` y los huecos con la tercera fuente (anulados, texto, 20 dígitos). | Todo pasa por la MISMA `remission_key`; T7, T9, T10, T16 (y se reusan los 3 casos de frontera de #141). |
| R10 | Fricción operativa: el molino traslada seguido y ahora cada uno pide remisión. | Decisión de Daniel (#1 del brief). Se anota en el informe. |
| R11 | Alcance de recolector (#129): el talonario y los traslados no deben abrirse a Ingrid. | No se agrega nada a `SCOPED_ENDPOINTS` ni a `SCOPE_PATHS`; T15 afirma 403 en `/remissions`, en `POST /transfers` y en `PATCH /transfers/{id}/remission` (el mismo test, tres aserciones; el PATCH apunta a un traslado que **existe**, para que un 404 no tape el 403); P18, P18b y P18c plantan cada ruta. |
| R12 | El `PATCH` mueve algo que no debe (inventario, kg, merma, maquila, estado). | El servicio solo escribe una columna; TP8 compara, antes y después, las tablas de efectos de un traslado cruzado recibido con merma y par de maquila (con un control positivo **por tabla**, ver TP8) y P26, P32 y P33 plantan una fila de efectos en tres tablas distintas, la última la más débil. |
| R16 | El `PATCH` a un traslado anterior a este ciclo (remisión NULL, el diálogo arranca vacío): la comparación «igual a la guardada» sobre NULL. | `update_remission` compara contra `(transfer.remission_number or "").strip()`; TP12, P31 y E5 con un traslado viejo. |
| R13 | Un permiso demasiado bajo deja que cualquiera reescriba el papel de salida. | `inventory.transfer` (D-e); TP7a usa un rol con `inventory.view` e `inventory.transfer_receive` y sin `inventory.transfer` → 403; TP7b es el control positivo. |
| R14 | Corregir una remisión de un traslado ya recibido cambia qué números cubre el talonario hacia atrás. | Es lo pedido (corregir un error). Los huecos y las marcas se recalculan solos porque salen de la columna; TP11 lo mide. El anulado queda congelado (D-e). Sin historial del valor anterior (§11). |
| R15 | La caché del talonario queda vieja tras despachar, anular o corregir. | D-f; E3 y E5, PF9. |

---

## 4. Diseño del talonario con la tercera fuente

- **`_union`**: un tercer `select` de `Transfer` con las mismas columnas (`doc_type='transfer'`, `doc_id`, `doc_number=transfer_number`, `remission=remission_number`, `date=dispatch_date`, `status`, `inbound_type=NULL`). Los traslados con `remission_number` NULL quedan fuera de la lista por la regla de siempre (`remission_key(...).vacia`): no hay hueco ni repetida que inventar con ellos.
- **Ver vs. medir** (D-b): `base` (la lista) agrega `doc_type != 'transfer'` solo si `show_transfers` es False. `dup_keys` y `all_nums` se leen de la unión entera, sin ese filtro. `documents` y `total` cuentan lo que se ve.
- **Aviso al capturar** (`duplicate_remission_warning`): orden fijo Entrada → Salida de control → Traslado; el primero que choca nombra el documento. Las anuladas no cuentan para el aviso (anular y recapturar con la misma remisión es el camino de corregir un error); sí cubren su número en el talonario (huecos). Es la regla de hoy, extendida.
- **Materiales por fila**: una tercera consulta por página (`TransferLine.transfer_id IN (…)` unida a `Material.code`), nunca un join 1:N (#89/#93).
- **`inbound_without_remission`** no cambia (solo Entradas); los traslados viejos sin remisión no se cuentan (el brief los deja así).
- **El PATCH** (D-e): el servicio no recalcula nada; la corrección se ve en el talonario sin código nuevo porque `_union` lee la columna. El aviso usa la misma `duplicate_remission_warning`, con la misma exclusión por id que `dispatch`.
- **Permiso en el endpoint**: `require_permission("purchases.view", "sales.view")` se queda; `show_transfers` se decide adentro con `org_context["is_admin"]` / `user_permissions` (patrón #102: la regla depende de un dato que la dependency estática no ve) y el flag con `get_org_setting`.

---

## 5. Frontend

- **Menú**: entrada «Talonario de remisiones» después de «Traslados», con `permissionAll: ["purchases.view", "sales.view"]` y `orgFlag: "kg_ledger_enabled"`. Un usuario con alcance de recolector no la ve (`SCOPE_PATHS` no la lleva).
- **Nuevo Traslado**: campo «Remisión *» junto a la fecha. El botón «Registrar/Despachar» se habilita solo con remisión (trim) además de lo de hoy. El aviso de repetida llega en `warnings` y ya se muestra como toast ámbar (`useDispatchTransfer → showWarnings`), sin código nuevo.
- **Lista y detalle**: columna «Remisión» en la tabla (desktop) y línea en la tarjeta (390); el detalle la muestra en el bloque de datos. «—» si es NULL.
- **Talonario**: fila «Traslado #n» con enlace al detalle, badge «Traslado» (color propio, distinto de Entra/Sale), estado en español: Por recibir / En discrepancia / Recibido / Anulada.
- **Corregir remisión** (detalle del traslado): botón «Corregir remisión» junto a las acciones de la cabecera, visible solo con `inventory.transfer` y si el traslado no está anulado; el diálogo (shadcn `Dialog`, ya usado en esa página) lleva un `Input` con la remisión actual y el texto «No cambia inventario ni kg: solo el número del papel». Guardar se habilita solo con un valor no vacío y distinto del actual (ambos con trim). Éxito → toast y el detalle se refresca; si repite otra remisión, toast ámbar con el documento. A 390 el diálogo usa el ancho de los `Dialog` de la casa (`w-[calc(100vw-1.5rem)]`) y el botón es `w-full sm:w-auto`.
- **Responsive**: 390 sin scroll horizontal; el campo nuevo es `w-full`.
- **Decimal/Tipos**: no hay Decimal nuevo. `remission_number` es texto; las remisiones largas viajan como texto.

---

## 6. Tests nuevos — `backend/tests/test_sac_remision_traslados.py` (48)

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
| T12a | Cobertura sin permiso (C1): un usuario sin `inventory.view`; un traslado con remisión 101 **entre** dos Entradas visibles de números consecutivos en la serie (100 y 102): no sale la fila del traslado y **no sale un hueco** en el 101 | 1 |
| T12b | «Repetida» sin permiso (C1): un usuario sin `inventory.view`; un traslado con la **misma** remisión que una Entrada visible, sin vecinos en la serie (para que no haya huecos que medir): no sale la fila del traslado y la fila de la Entrada sigue marcada «Repetida» | 1 |
| T12c | Control positivo del permiso: con `inventory.view` salen las filas de traslado de T12a y T12b | 1 |
| T12d | Un rol con `inventory.view` y sin `sales.view` recibe 403 en `/remissions`, y uno con `purchases.view` y `sales.view` recibe 200 | 1 |
| T13 | El PAR del flag: con `kg_ledger_enabled` sin `two_step_transfers_enabled` las filas de traslado no salen aunque el usuario tenga `inventory.view` (la fila existe, cargada por el ORM); con el flag, sí | 2 |
| T14 | Un traslado ya registrado, sin remisión: lista y detalle devuelven `null` (sin 500), no sale en el talonario y no entra a `inbound_without_remission` | 2 |
| T15 | Alcance de recolector (#129): `GET /remissions`, `POST /transfers` y `PATCH /transfers/{id}/remission` dan 403; el PATCH apunta a un traslado **existente** (con id inexistente el 404 podría taparlo) | 1 |
| T16 | Orden: una remisión de texto de un traslado va al final en los dos sentidos, como las otras | 1 |

**PATCH de la remisión (19 tests: 18 de v1.2 + TP12 de v1.3).** Mismo archivo; todo por HTTP; los efectos se miden con tablas, no con la respuesta.

| T | Qué prueba | # |
|---|---|---|
| TP1 | Caso feliz: el PATCH cambia la remisión (con espacios → guarda sin ellos), la respuesta, la lista y el detalle la muestran, y `warnings == []`; en un traslado `dispatched`, en uno `received` (cruzado, recibido) y en uno `held_discrepancy` | 3 |
| TP2 | Obligatoria: `""`, `"   "`, `null` y la clave ausente dan 422 y la remisión guardada no cambia | 4 |
| TP3 | `extra="forbid"`: el campo correcto **más** una clave de más (`remision_number`) da 422 | 1 |
| TP4 | «Repetida» por HTTP, en la respuesta del PATCH: contra una Entrada, contra una Salida de control y contra otro traslado; cada aviso **nombra** el documento; responde 200 y la remisión queda cambiada | 3 |
| TP5 | Sin cambio = sin aviso: PATCH con el mismo valor (también con espacios alrededor) cuando otro documento ya lo tiene responde 200 y `warnings == []` | 1 |
| TP6 | Anulado: 400 que lo nombra y dice que se corrija antes de anular; la remisión no cambia | 1 |
| TP7a | Permiso: un rol con `inventory.view` e `inventory.transfer_receive` y **sin** `inventory.transfer` recibe 403 y la remisión no cambia | 1 |
| TP7b | Control positivo: un rol con `inventory.transfer` (y sin `inventory.transfer_receive`) recibe 200 | 1 |
| TP8 | **No mueve nada.** Dos traslados en la misma org: A, cruzado y recibido con merma y par de maquila; B, recibido fuera de tolerancia (`held_discrepancy`, con su `DiscrepancyTask` abierta). Antes de despacharlos se siembra un MCH del mismo material (una compra liquidada). Se vuelcan (conteo + huella de cada fila) las ocho tablas y las existencias y el costo promedio de los materiales, más las columnas de los dos traslados menos `remission_number`; se hace el PATCH a A **y** a B; tras eso todo es idéntico. **Control positivo por tabla** (se afirma antes de comparar, tabla por tabla; si alguna estuviera vacía, su igualdad sería `0 == 0`): `inventory_movements`, `kg_ledger_movements` y `transfer_lines` por A; `money_movements` por el par de maquila de A; `inventory_adjustments` por la merma de A; `material_cost_histories` por el MCH sembrado (un traslado nunca escribe MCH, B1 de #84, así que sin siembra estaría vacía); `discrepancy_tasks` por B (sin discrepancia no hay tarea) | 1 |
| TP10 | Aislamiento por org: un traslado de otra organización y un id inexistente dan 404; la remisión del otro no cambia | 1 |
| TP12 | Traslado viejo (C1): uno sin remisión (se carga con el ORM tras crearlo, como los anteriores a este ciclo): el PATCH la fija, responde 200 con `warnings == []`, el detalle la muestra y el talonario lo trae | 1 |
| TP11 | El talonario sigue la corrección: tras el PATCH, `/remissions` muestra el traslado con la remisión nueva, el número viejo ya no lo cubre (aparece como hueco si queda entre dos) y el nuevo sí | 1 |

(TP9 no existe: el 403 de alcance de recolector va en T15, una aserción más.)

Re-semantización (no suman tests): los 6 sitios de R1 pasan una remisión única por llamada. La lista sale de este grep, que se repite al construir y se pega en el log (medido sobre `4efead9`):

```
cd backend
grep -n "def _dispatch" tests/test_sac_transfer_two_step.py tests/test_sac_planta_proveedor.py   # los 2 helpers
grep -c "_dispatch(" tests/test_sac_transfer_two_step.py     # 41 = la definición + 40 llamadas
grep -c "_dispatch(" tests/test_sac_planta_proveedor.py      # 5 = la definición + 4 llamadas
grep -n -A1 "client.post(" tests/test_sac_transfer_two_step.py tests/test_pnl_by_warehouse.py tests/test_sac_planta_proveedor.py | grep "TRANSFERS_URL"
                                                             # POST directos: 2 + 1 fuera de los helpers (más el de cada helper)
```

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

**Predicción escrita antes**: `--collect-only` de los 19 existentes = **655** (medido sobre `7829411` por mí y sobre `4efead9` por QA 2; el commit del plan no toca tests). El archivo nuevo suma **48** (§6: 29 de la remisión en el despacho y el talonario, con T12 partido en cuatro, y 19 del PATCH). Los tests re-semantizados no cambian de número. Predicción del set dirigido: **703**. **El PATCH no cambia el set**: vive en `services/transfer.py`, `endpoints/transfers.py` y `schemas/transfer.py`, que ya cubre el grep C; no hay archivos de test nuevos fuera de `test_sac_remision_traslados.py` ni importadores nuevos (se repiten los cuatro greps al construir). Se compara con `--collect-only` del set final y con la corrida.

Frontend: sin infra de test. `tsc`, `eslint` (37 = techo) y `build`, más un e2e con Playwright (§9).
Suite completa: **diferida al checkpoint** (regla del 19-nov). La predicción del checkpoint saldrá de `git diff --name-only 7e2ee4f -- backend/tests`, no de memoria.

---

## 8. Matriz de plantado (commiteada ANTES de plantar; no se reescribe — lo que falte va en una adenda)

Se planta en una copia sacada con `git archive` del commit de esta matriz, no en el worktree; un defecto por vez, con el conteo de ocurrencias afirmado; `PYTHONDONTWRITEBYTECODE=1`; restaurar y verificar el sha256. Se corre `test_sac_remision_traslados.py` **entero**, para ver también lo que cae de más, y el script exige `exit 0` antes de leer la diagonal. «= {…}» es exacto; «≥ {…}» es «al menos» (vía compartida). La dirección peligrosa es un test predicho que NO cae.

| P | Defecto (archivo · cambio) | Debe caer |
|---|---|---|
| P1 | `schemas/transfer.py` · `remission_number: RemissionStr` → `Optional[RemissionStr] = None` (opcional) | ≥ {T2} |
| P2 | `schemas/remission.py` · `strip_whitespace=True` → `False` | ≥ {T1, T2, TP1, TP2} y los de control (`t19_remision_obligatoria`, `t19_el_patch_no_la_deja_vaciar`) |
| P3 | `services/transfer.py` · se quita `remission_number=data.remission_number` (se pierde) | ≥ {T1, T8, T11} |
| P4 | `services/transfer.py` · se quita `warnings.append(dup)` (se calcula y no llega) | = {T4 ×3} |
| P5 | `services/transfer.py` · se quita `exclude_transfer_id=transfer.id` (se avisa a sí mismo) | ≥ {T1}. Los T4 contra una Entrada o una Salida de control no pueden caer (esos bloques chocan antes y nombran bien) y T4 traslado-contra-traslado tampoco (la consulta ordena por número y nombra al más viejo): si no caen, se anota, no es la dirección peligrosa |
| P6 | `services/remission_book.py` · `duplicate_remission_warning`: se quita el bloque de traslados | ≥ {T4 (traslado vs traslado), T5 ×3} |
| P7 | ídem · se quita `Transfer.status != "annulled"` | = {T6} |
| P8 | ídem · la llave del traslado sin normalizar (`lower(trim)` en vez de `remission_key`) | ≥ {T7} |
| P9 | `remission_book._union` · sin la tercera fuente | ≥ {T8, T9, T10, T11, T13, T16} |
| P10 | `remission_book` · `show_transfers` ignorado (siempre se ven) | = {T12a, T12b, T13 sin flag} |
| P11 | `remission_book` · `show_transfers` siempre False | ≥ {T8, T12c, T13 con flag} |
| P12a | `remission_book` · `all_nums` sale de las filas visibles (el traslado oculto no cubre su número) | = {T12a} |
| P12b | `remission_book` · `dup_keys` sale de las filas visibles (el traslado oculto no marca «Repetida») | = {T12b} |
| P13 | `endpoints/control_dispatches.py` · `show_transfers` no mira el flag | = {T13 sin flag} |
| P14 | `endpoints/control_dispatches.py` · `show_transfers` no mira el permiso | = {T12a, T12b} |
| P15 | `remission_book._attach_materials` · sin la rama de traslados | ≥ {T8} |
| P16 | `remission_book` · `base` excluye `status == "annulled"` de los traslados | ≥ {T9} |
| P17 | `schemas/control_dispatch.py` · `RemissionBookItem.doc_type` sin `"transfer"` (500 al serializar) | ≥ {T8, T9, T10, T11, T16} |
| P18 | `services/collector_scope.py` · `SCOPED_ENDPOINTS` gana `control_dispatches.list_remissions` | = {T15} |
| P18b | ídem · `SCOPED_ENDPOINTS` gana `transfers.dispatch_transfer` | = {T15} |
| P18c | ídem · `SCOPED_ENDPOINTS` gana el endpoint del PATCH (`transfers.update_transfer_remission`) | = {T15} |
| P19 | `endpoints/transfers.py` · `_enrich` sin `remission_number` (el POST lo guarda y la respuesta no lo devuelve) | ≥ {T1, T14} |
| P20 | `remission_book` · `inbound_without_remission` cuenta también los traslados sin remisión | = {T14 (contador)} |

**PATCH de la remisión (v1.2):**

| P | Defecto (archivo · cambio) | Debe caer |
|---|---|---|
| P21 | `endpoints/transfers.py` · el permiso del PATCH pasa de `inventory.transfer` a `inventory.view` | = {TP7a} |
| P22 | `services/transfer.py` · `update_remission`: se quita el guard de anulado | = {TP6} |
| P23 | `services/transfer.py` · `update_remission`: se quita `warnings.append(dup)` (se calcula y no llega) | = {TP4 ×3} |
| P24 | `services/transfer.py` · `update_remission`: se quita `exclude_transfer_id=transfer.id` (se avisa a sí mismo; tras el `flush` ya tiene el valor nuevo) | ≥ {TP1 ×3}. TP5 no puede caer (sin cambio el servicio no hace la consulta): se mide con P25 |
| P25 | `services/transfer.py` · `update_remission`: se quita la comparación `changed` (avisa aunque no cambie) | = {TP5} |
| P26 | `services/transfer.py` · `update_remission`: se agrega un `InventoryMovement` de la primera línea (una fila de efectos) | = {TP8} |
| P27 | `services/transfer.py` · `update_remission`: `self._get_or_404(db, id, org)` → `db.get(Transfer, id)` (sin filtro de org; un id inexistente da `None`) | ≥ {TP10} |
| P28 | `services/transfer.py` · `update_remission`: escribe en `transfer.notes` y no en `remission_number` | ≥ {TP1 ×3, TP11} |
| P29 | `schemas/transfer.py` · `TransferRemissionUpdate`: se quita `extra="forbid"` | = {TP3} |
| P30 | `schemas/transfer.py` · `TransferRemissionUpdate.remission_number` pasa a `Optional[RemissionStr] = None` | = {TP2 `null`, TP2 clave ausente} |
| P31 | `services/transfer.py` · `update_remission`: la comparación `(transfer.remission_number or "").strip()` → `transfer.remission_number.strip()` (asume una guardada; sobre NULL da 500) | = {TP12} |
| P32 | `services/transfer.py` · `update_remission`: se agrega una fila de `MaterialCostHistory` (copia de la sembrada) | = {TP8} (la tabla más débil: no la toca ningún traslado) |
| P33 | `services/transfer.py` · `update_remission`: se borra la `DiscrepancyTask` de la línea retenida | = {TP8} |

**Frontend (e2e, mismo método, contra el árbol servido; los casos E1–E5 están definidos en el §9):**

| P | Defecto | Debe caer |
|---|---|---|
| PF1 | `Sidebar.tsx` · `permissionAll` evaluado como «alguno» | = {E1 con uno solo de los dos permisos} |
| PF2 | `Sidebar.tsx` · la entrada sin `orgFlag` | = {E1 en la org sin `kg_ledger_enabled`, y su registro de red} |
| PF3 | `RemissionBookPage.tsx` · el enlace del traslado va a `INBOUND_DETAIL` | = {E2} |
| PF4 | `TransferCreatePage.tsx` · el botón no exige la remisión | = {E3, cruzado e intra-sede} |
| PF5 | `TransferCreatePage.tsx` · el payload manda `remision_number` (clave mal escrita) | = {E3: el POST real da 422 y la petición capturada no lleva `remission_number`} |
| PF6 | `TransferDetailPage.tsx` · el botón «Corregir remisión» se pinta sin mirar `inventory.transfer` | = {E5 (usuario sin `inventory.transfer`)} |
| PF7 | `TransferDetailPage.tsx` · el botón se pinta también en un traslado anulado | = {E5 (traslado anulado)} |
| PF8 | `services/transfers.ts` · `updateRemission` manda `remision_number` (clave mal escrita) | = {E5: el PATCH real da 422 y la petición capturada no lleva `remission_number`} |
| PF9 | `utils/queryInvalidation.ts` · se quita `["remissions"]` de `invalidateAfterTransfer` (D-f) | = {E3 (talonario fresco tras despachar), E5 (tras corregir)} |
| PF10 | `TransferDetailPage.tsx` · el diálogo arranca con `t.remission_number.trim()` (asume una remisión guardada; revienta sobre NULL) | = {E5 con el traslado viejo} |

Cada fila se mide por su NÚMERO de caídas y no solo por si cae; una predicción que falle se anota con su causa (las de «vía compartida» caen de más y es la dirección barata).

---

## 9. Gates, en el orden del flujo con QA (#CLAUDE.md, 17-nov)

1. **Este plan → GO de QA 2 → OK de Daniel.** No se construye antes. Si el plan se edita después del GO, vuelve a QA con el sha en el acto.
2. Construcción: código y tests nuevos; el autor corre solo el lint y los tests nuevos. Migración en dev (5434) y test (5433, la BD de este coder).
3. **QA pasada 1**: el delta como patch con su sha256, la base y el sha256 de cada archivo; el árbol queda quieto.
4. Correcciones; QA relee el delta.
5. Gates: dirigidas del §7 (predicción escrita antes), plantado del §8, `ruff`, `tsc`, `eslint`, `build`, `schema_parity_check.py` (DIFF CERO esperado, +0 divergencias), migración up/down/up a archivo, smoke con POST real contra un backend arrancado DESPUÉS del último cambio de `app/` (con su procedencia impresa), y el e2e de abajo.
**E2e (Playwright, cinco casos E1–E5, contra un backend y un front arrancados DESPUÉS del último cambio, con su procedencia impresa).** Cada caso corre a **1440 y a 390** y lleva su **control positivo** (la misma pantalla con el permiso o el dato que sí lo habilita); sin él, un «no aparece» no distingue «funciona» de «no cargó». A 390: sin scroll horizontal. Los usuarios son roles con un permiso y no el otro; los datos de prueba se revierten al final con deltas.

| E | Caso | Control positivo | Lo mide |
|---|---|---|---|
| E1 | **Menú.** La entrada «Talonario de remisiones» aparece con `purchases.view` + `sales.view` + `kg_ledger_enabled`; **no** aparece con solo uno de los dos permisos, ni en una org sin `kg_ledger_enabled` (con el registro de red de esa org igual al de antes: cero requests de más), ni con alcance de recolector | el usuario con los dos permisos y el flag la ve y entra | PF1, PF2 |
| E2 | **Talonario.** La fila «Traslado #n» sale con su remisión, badge «Traslado» y estado en español (Por recibir / En discrepancia / Recibido / Anulada); el enlace abre el detalle **del traslado** (no una Entrada); un usuario sin `inventory.view` no ve la fila | el mismo talonario con `inventory.view` la muestra | PF3 |
| E3 | **Nuevo Traslado, cruzado e intra-sede.** El botón está deshabilitado sin remisión y con solo espacios; con ella, el POST real sale con `remission_number` (se lee de la petición capturada, no del código) y el traslado se crea; el talonario (visitado antes, navegando sin recargar) muestra el traslado nuevo; una remisión repetida muestra el toast ámbar con el documento | el mismo formulario con remisión llena queda habilitado y registra | PF4, PF5 |
| E5 | **Corregir remisión.** En el detalle de un traslado `received` el botón «Corregir remisión» está con `inventory.transfer` y **no** está sin él ni en un traslado anulado; el diálogo no deja guardar vacío ni igual a la actual; guardar con otro valor manda un PATCH con `{remission_number}` y solo esa clave (se lee de la petición capturada), el detalle muestra el valor nuevo, y el talonario (visitado antes, navegando sin recargar) lo muestra también; una remisión que repite otra muestra el toast ámbar con el documento; **y un traslado viejo, sin remisión** (cargado por el ORM): el botón está, el diálogo arranca vacío, Guardar está deshabilitado hasta escribir y luego guarda | el mismo detalle con `inventory.transfer` y un traslado no anulado muestra el botón y guarda | PF6, PF7, PF8, PF9, PF10 |
| E4 | **Lista y detalle.** La columna «Remisión» (y la línea de la tarjeta a 390) muestra el valor, y «—» en un traslado viejo sin remisión | un traslado nuevo con remisión en la misma lista | (red de lectura) |

6. QA pasada 2 → OK de commit → commit en mi rama. Integración a develop y deploy: los hace el Coordinador con el OK de Daniel.

**Golden: no aplica — medido, no argumentado.** Comandos que se repiten al construir y se pegan en el log:
- `grep -nE '^\s+\("' scripts/golden_capture.py` sobre `CAPTURES`: **14 entradas / 11 rutas únicas**, todas de `/reports/*`, `/money-accounts`, `/warehouses`, `/money-movements`. Ninguna es `/transfers`, `/remissions` ni `/inbound-orders`.
- `grep -n "Transfer" app/services/reports.py`: solo cadenas de tipos de movimiento («Transferencia entre terceros»); `reports.py` no importa el modelo `Transfer`.
- El cambio de `app/` agrega una columna a una tabla exclusiva de SAC, un tercer bloque en una lectura de SAC y un campo en un schema de SAC. No cambia ningún valor ni forma de lo que el golden captura, así que daría «0 diffs y 0 aditivas»: el resultado que #110 mostró que no distingue «no rompió nada» de «comparó viejo contra viejo». La red es el PAR de T12/T13 y los 56 tests existentes de traslados.

---

## 10. Decisiones de Daniel sobre O1–O3 (25-nov, vía el Coordinador)

Sin preguntas abiertas.
- **O1 — Corregir una remisión:** **se incluye el `PATCH`** en este ciclo (contra la recomendada del plan). Diseño en D-e; permiso, estados y anulado los decide el plan y los revisa QA 2.
- **O2 — Quién abre el Talonario:** como hoy, `purchases.view` Y `sales.view`.
- **O3 — Números cubiertos por un documento que el usuario no ve:** huecos y marcas contra toda la org. El costo alcanza también a los avisos: una Entrada o una Salida de control que se captura con la remisión de un traslado avisa «Traslado #n» aunque quien captura no tenga `inventory.view`; en los dos casos solo se revela que ese número existe.

**Observación abierta de QA 2 (no condiciona el GO; decide Daniel):** con el PATCH el valor anterior de la remisión se pierde, y la remisión es obligatoria «para que no me alteren el consecutivo» (Hugo). Una línea de log al estilo de #85 D5 (actor, traslado, valor anterior y nuevo; sin tabla ni migración) cuesta poco. **(Recomendado)** incluirla; si Daniel dice que sí, va en una adenda con su test (`caplog`) y su fila de plantado, y el conteo pasa a 49 / 704. Mientras no responda, no se construye.

## 11. Fuera de este ciclo (se anota, no se hace)

- El inventario (`inventario-preguntas-cliente.md`) y CLAUDE.md los escribe el Coordinador al integrar: la lectura (c) de Q-75 «los traslados salen del mismo talonario» (decisión de Daniel, no respuesta de Johana) y la decisión nueva.
- Los traslados de Salidas de Plomo y las conversiones del crisol no llevan remisión de este talonario.
- No se guarda el valor anterior de una remisión corregida (ni en traslados, ni en Entradas, ni en Salidas de control). Si hace falta auditoría de verdad, es un ciclo propio; la línea de log es la observación abierta del §10.
- El `PATCH` no edita nada más del traslado (notas, fecha, bodegas, líneas).
- Una venta no tiene campo de remisión (anotado en #141); sigue como hueco.
