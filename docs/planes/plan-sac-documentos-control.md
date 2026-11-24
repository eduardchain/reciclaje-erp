# Plan — Entradas y Salidas «de control» (SAC, v1.0)

**Autor:** Eco Coder 2 · **Fecha:** 2026-11-24 · **Rama:** `coder-2/documentos-control` sobre develop `5139940`
**Nivel:** lógica (migración, reglas de estado en un servicio con dinero, guards en servicios compartidos si se aprueba D5).
**Autorización:** Daniel, 24-nov («esos dos, dale»), vía Coordinador. Este documento es SOLO el plan; construir exige el GO de QA 2 y después la autorización de Daniel.

## 1. Qué pide el cliente

Johana, 24-nov (mensaje, con sus palabras): *«no tenerlas en cuenta. Pero por el consecutivo sí necesito dejarlas en el registro del sistema. Más que no me afecten el inventario ni nada»*.

- Estibas, tubulares y electrolito entran o salen a $0.
- Se registran para que la numeración no quede con huecos.
- No se liquidan, no tocan el inventario, ni los kg, ni los saldos.

Hoy les ponen $1, y eso mete inventario y crea deuda con un proveedor. El reparto exige precio mayor que 0 (`schemas/inbound_order.py` l.133-147).

**Datos de prod al 24-nov** (GET del Coordinador, `~/sac-evidencia/2026-11-24/coordinador-control/leer_control.log`):
- 14 Entradas solo de ESTIBAS, con remisiones de 16267 a 16454, del 3 al 20-nov.
- Las 14 están en Revisada esperando liquidar. Tienen que poder cerrarse sin valor.
- ESTIBAS existe y se mide en `unidad`. Tubulares y electrolito no existen como material.
- No hay un documento de salida para lo que no es plomo.

**Q-75 (🟠 abierta):** ¿la salida usa el talonario de remisiones de las entradas o uno propio? ¿Qué anotan en ella?
- **Supuesto de este plan, a decidir por Daniel:** la Salida de control lleva su **consecutivo propio**. Además, la remisión va como **texto libre**, como en la Entrada (#93 D12), que no valida ni numera nada.
- Si Johana responde que comparten talonario, el texto libre ya lo admite: se escribe el número del talonario y nada del modelo cambia.
- Lo que la respuesta sí podría cambiar son los campos de la salida (§4.3). El plan los deja opcionales salvo fecha, bodega y líneas.

## 2. Dirección aprobada (Coordinador, 24-nov)

1. Marca «solo control» en Materiales (kg).
2. Una Entrada que tiene SOLO materiales de control muestra **«Cerrar sin valor»**:
   - es un estado terminal propio, ni Anulada ni Liquidada;
   - conserva el número y la remisión y sale de la bandeja;
   - tiene cero efectos: sin compras, inventario, kg ni saldos.
3. En una Entrada mixta, las líneas de control quedan fuera del reparto y del descuadre.
4. **«Salida de control»:** documento nuevo, sin efectos, con consecutivo propio. Lleva fecha, remisión, a quién, material de control, cantidad, peso y notas. **Salidas de Plomo y su guard #103 NO se tocan.**

## 3. Lo que el código ya dice (medido en `5139940`)

| Hecho | Dónde | Consecuencia para el plan |
|---|---|---|
| `inbound_orders.status` es `String(16)` sin CHECK. Valores: `draft \| reviewed \| liquidated \| confirmed \| annulled` | `models/inbound_order.py` l.147-158; ninguna migración crea un CHECK sobre esa columna (grep) | Un valor nuevo no necesita migración de CHECK; se documenta en el comentario de la columna |
| `display_status_of` cae a `"liquidated"` para **cualquier** valor que no reconoce | `services/inbound_order.py` l.2250-2261 | 🔴 Trampa. Sin una rama propia, una Entrada cerrada se pintaría «Liquidada» y contaría como liquidada en el filtro. La rama va ANTES del fallback |
| El espejo del filtro es `status_map` en `get_multi`, y el endpoint valida `display_status` con una regex | `services/inbound_order.py` l.2052-2060; `endpoints/inbound_orders.py` l.418-422 | Hay que tocar tres lugares a la vez: `display_status_of`, `status_map` y las regex de `status` y `display_status`. `test_filter_parity_with_field` (#82) suma el caso |
| Los contadores de la bandeja piden `display_status=registered` y `reviewed` | `hooks/useInboundOrders.ts` l.30-36 | Una cerrada sale de la bandeja sola, sin tocar los hooks |
| La captura Willard rechaza todo material con `willard_world == 'none'` | `_validate_willard_capture`, l.1456-1463 | Un material de control (que exige `none`, §4.1) **no puede entrar a una Entrada Willard por construcción**. El plan **no toca el camino Willard** (`confirm`, `_apply_willard_effects`), que es el que está trabajando Coder 1 |
| `liquidate` exige que el reparto traiga **todas** las líneas (completitud) y crea una línea nueva para todo material del payload que la báscula no vio | l.534-539 (D16) y l.598-609 | La completitud ignora las líneas de control; un material de control en el payload da 422 |
| La comisión del recolector usa como base **todo lo pesado**: kg más unidades × `kg_per_unit` | `suggested_collector_commission` l.1217-1252 y `commissionBase` de `InboundLiquidatePage` | Sin cambio, 100 estibas × 14 kg pagarían comisión. Se excluyen las líneas de control (§4.2, R8) |
| `_require_scale_weights` exige peso de báscula a toda línea por unidad al revisar | l.263-299 | En una Entrada mixta, ESTIBAS (unidad) sin peso bloquearía la revisión. Se exime a las líneas de control (D4) |
| `MaterialKgProfileUpsert` es `extra="forbid"` y reemplaza el perfil entero | `schemas/material_kg_profile.py`, #103 D4 | La marca **no** viaja por el upsert, porque un caller que no la mande la borraría. Va con endpoint propio, como `form_order` (#121) |
| Los consecutivos salen de `next_number()`, con `SEQUENCES` y `RANK` en `utils/advisory_locks.py`. Los documentos ocupan los rangos 10–14 | l.42-75 | La secuencia nueva es `control_dispatch_number` con rango **15**. Los asserts del módulo y `TestGuarda` la vigilan |
| El router de Entradas y el de perfiles están detrás de `require_org_flag("kg_ledger_enabled")` | `endpoints/inbound_orders.py:44`, `material_kg_profiles.py:22` | Las 3 orgs que no son SAC reciben 403 antes de llegar a cualquier código nuevo |
| Las rutas que no están en `SCOPED_ENDPOINTS` dan 403 a un usuario con alcance (#129) | `services/collector_scope.py` l.71-80 | Las rutas nuevas (cerrar, reabrir, marca, salidas de control) **no** se agregan: Ingrid no las ve. Ver R10 |
| Fuera de su módulo, `InboundOrder.status` se lee solo con `!= 'annulled'` | `services/purchase.py` l.60 y l.1924 | Una Entrada cerrada no tiene compras en el puente, así que esos predicados no la ven |

## 4. Diseño

### 4.1 Marca «solo control» (`material_kg_profiles.control_only`)

- **Columna:** `material_kg_profiles.control_only` Boolean NOT NULL `server_default false`. La tabla es exclusiva de SAC y está detrás del flag.
- **Endpoint propio:** `PUT /material-kg-profiles/{material_id}/control` con cuerpo `{control_only: bool}`, `extra="forbid"` y permiso `materials.edit`.
  - Si el material no tiene perfil, se crea con los valores por defecto (`compra_regular=false`, `willard_world='none'`, `lead_product='none'`).
  - En el router se declara ANTES de `PUT /{material_id}` (lección F1 de `form-order`).
- **El upsert no conoce la marca**, así que no la puede borrar (#103 D4). `MaterialKgProfileResponse` la devuelve como solo lectura.
- **Coherencia en las DOS direcciones** (#112 D4d):
  - marcar un material con `willard_world != 'none'` o `lead_product != 'none'` → **422** que dice qué quitar primero;
  - el upsert que intente poner un mundo Willard o un plomo sobre un material marcado → **422**. El upsert lee la marca guardada aunque no la reciba.
  - Así un material de control no puede ser Willard ni plomo, y eso es lo que deja fuera de alcance los caminos de Willard y de Salidas de Plomo (#103: su guard exige `lead_product != 'none'`).
- `compra_regular` es **ortogonal**: no se toca ni se exige.
- **Selector de la captura** (Entrada tipo compra): ofrece `compra_regular || control_only`, y el material de control lleva la etiqueta «(control)».
- **Marcar y desmarcar no reescribe nada.** El estado de una Entrada se decide al leer la marca en el momento de cerrar o liquidar (R2), y una cerrada es terminal.
- **Config → Materiales (kg):**
  - casilla «Solo control (sin valor)» en el diálogo del material;
  - badge «Control» en la tabla;
  - la casilla se deshabilita, con el motivo, si el material es Willard o plomo.

### 4.2 Entrada — cerrar sin valor, Entrada mixta

**Estado nuevo `closed`**, rotulado «Cerrada sin valor». `display_status` nuevo: `closed`.

**`POST /inbound-orders/{id}/close`**, con permiso `purchases.liquidate`, el mismo verbo al que reemplaza.

**Reglas del cierre:**

| Regla | Comportamiento |
|---|---|
| R1 — tipo | Solo tipo compra. Willard → 400 («una recepción Willard no se cierra sin valor»). No ocurre en la práctica, porque Willard no acepta material de control, pero el 400 explica |
| R2 — todas las líneas de control | Se lee `control_only` de cada material **al cerrar**. Si alguna línea no es de control → 422 que **nombra** los materiales con valor y dice «liquídela». Sin líneas → 400 (como en `review`) |
| R3 — estados de origen | `draft` y `reviewed` → `closed` (D2: no exige revisar). `liquidated`, `confirmed`, `annulled` o `closed` → 400 con el estado |
| R4 — efectos | **Cero.** Solo cambian `status`, `closed_at` (`now(utc)`, timestamp de auditoría, #87) y `closed_by`. Ningún `Purchase`, `InventoryMovement`, `KgLedgerMovement`, `MoneyMovement`, `InventoryAdjustment` ni MCH |
| R5 — número y remisión | Se conservan: no hay renumeración ni borrado |
| R6 — reabrir (D3) | `POST /inbound-orders/{id}/reopen`, con `purchases.cancel` (el de desliquidar). Solo desde `closed`. Vuelve a `reviewed` si tiene `reviewed_at`, y si no a `draft`: el cierre no borra la revisión, así que reabrir devuelve exactamente el estado de antes. Limpia `closed_at` y `closed_by` |
| R7 — editar una cerrada | Igual que una liquidada: `lines` y `date` dan 422 («reábrala primero»), y la sede ya da 422 por `_change_warehouse` (estado ∉ draft/reviewed). La cabecera (notas, remisión, vehículo, conductor, recolector) sigue editable |
| R7b — anular una cerrada | Se permite, y es solo status y auditoría (cero efectos que revertir). `annul` ya acepta cualquier estado menos `annulled`; el `for` de compras del puente no encuentra ninguna |
| R7c — desliquidar o liquidar una cerrada | 400 con el estado, por los guards existentes más la rama nueva |

**Entrada mixta** (líneas con valor y líneas de control):

| Regla | Dónde |
|---|---|
| R8 — el reparto ignora el control | `liquidate`: la completitud (l.534-539) excluye las líneas de control. Un material de control en `payload.lines` → 422 que lo nombra («es de control: no se reparte ni se liquida»). Esto también cubre el camino D16 (un material que la báscula no vio) |
| R8b — sin descuadre del control | Como la línea de control nunca entra al `plan`, no genera descuadre, ajuste ni precio de referencia |
| R8c — comisión | `suggested_collector_commission` (servidor, el de Ingrid) y `commissionBase` (pantalla) excluyen las líneas de control. «No tenerlas en cuenta» |
| R8d — todo de control | Si todas las líneas son de control, `liquidate` → 422 «Esta Entrada es solo de control: ciérrela sin valor» |
| R8e — alcance de recolector | Con `require_full_allocation` (#129 9g), las líneas de control se saltan ANTES del cálculo de `gaps`. Si no, una estiba «sin repartir» le bloquearía la liquidación a Ingrid |
| D4 — báscula | `_require_scale_weights` no exige peso a las líneas de control: el peso certifica lo que se valora (#95 Q-13) y aquí no se valora nada. Si viene, se guarda |

**Columnas nuevas en `inbound_orders`** (exclusiva de SAC): `closed_at` (timestamptz, nullable) y `closed_by` (FK users, SET NULL, nullable).

### 4.3 Salida de control (documento nuevo)

**Tablas** (exclusivas de SAC, nuevas):
- `control_dispatches`:
  - `id`, `organization_id`;
  - `dispatch_number` int, con UNIQUE (org, número);
  - `date` (fecha de negocio, `BusinessDate`);
  - `warehouse_id` NOT NULL (FK RESTRICT), la bodega de donde sale;
  - `third_party_id` nullable (FK RESTRICT), a quién;
  - `remission_number` `String(50)` nullable, texto libre (Q-75);
  - `notes` `String(1000)`;
  - `status` (`registered | annulled`, String más CHECK, sin pg_enum, por el parity);
  - `annulled_reason`, `annulled_at`, `annulled_by`, `created_by` y los timestamps.
- `control_dispatch_lines`:
  - `dispatch_id` (CASCADE), `material_id` (RESTRICT);
  - `quantity` `Numeric(15,4)` con CHECK > 0;
  - `scale_weight_kg` `Numeric(15,3)` nullable;
  - UNIQUE (dispatch, material).

**Consecutivo:** `control_dispatch_number` en `SEQUENCES`, con **RANK 15**. Se toma solo y al crear. No tiene series.

**Rutas** `/control-dispatches` (router con `require_org_flag("kg_ledger_enabled")`):

| Ruta | Permiso |
|---|---|
| `GET` (lista con filtro por fecha y búsqueda por número, remisión o tercero) | `sales.view` |
| `GET /{id}` | `sales.view` |
| `POST` | `sales.create` |
| `PATCH /{id}` (solo `registered`; cabecera y líneas) | `sales.edit` |
| `POST /{id}/annul` (motivo obligatorio) | `sales.cancel` |

Son los mismos permisos que Salidas de Plomo, así que no hace falta ningún permiso nuevo.

**Validaciones:**
- cada material de las líneas debe tener `control_only` → 422 que lo nombra y manda a marcarlo en Materiales (kg). **Este es el clasificador**, igual que #103 D1 lo es para el plomo;
- al menos una línea;
- una fila por material;
- bodega activa de la org y que no sea de tránsito (`validate_not_transit_warehouse`);
- tercero activo de la org, sin restricción de categoría (a quién se entregan estibas no es un rol);
- fecha no futura con `business_today()`.

**Efectos: cero**, en crear, editar y anular. Ningún movimiento de inventario, kg, tesorería ni ajuste. Lo afirma un test por conteo de tablas (T13).

**Pantalla:**
- lista, nueva, detalle, editar y anular;
- vive en el menú según D6.

### 4.4 Frontend de la Entrada

- **Detalle:**
  - Entrada solo de control en `draft` o `reviewed`: el botón «Cerrar sin valor» reemplaza a «Liquidar», con un diálogo que explica que no crea compras ni mueve inventario;
  - Entrada cerrada: badge gris «Cerrada sin valor», fila de auditoría «Cerrada» con el formato de auditoría (como «Anulada», 1e5a912) y el botón «Reabrir»;
  - Entrada mixta: nota «N líneas de control no se liquidan».
- **Lista:**
  - badge gris «Sin valor»;
  - «Total $» queda en «—»;
  - el filtro de estado gana la opción «Cerradas sin valor». Las pestañas no cambian.
- **Liquidar (`InboundLiquidatePage`):**
  - las filas de control no entran a la matriz;
  - se listan aparte, en solo lectura, con «control, no se liquida»;
  - `assertDraftShape` y la firma del borrador ignoran esas filas.

## 5. Decisiones que pide el plan (las toma Daniel, vía Coordinador)

| # | Pregunta | Recomendada | Alternativa y su costo |
|---|---|---|---|
| D1 | Nombre del estado | «Cerrada sin valor» | «Registrada sin valor». Se confunde con «Registrada», que es el borrador |
| D2 | ¿Se cierra desde Registrada, sin revisar? | Sí, desde Registrada y Revisada. La revisión certifica peso para valorar, y aquí no se valora nada | Solo desde Revisada: obliga a revisar estibas, con el peso que eso exige si no se aprueba D4 |
| D3 | ¿Se puede reabrir una cerrada? | Sí, con «Reabrir» (`purchases.cancel`), que vuelve al estado de antes | Sin reabrir: un cierre por error solo se arregla anulando, y anular **rompe el consecutivo**, que es justo lo que se quiere cuidar |
| D4 | ¿El peso de báscula es opcional en las líneas de control? | Sí | No: una Entrada mixta con estibas sin peso no se puede revisar |
| D5 | ¿Ventas y Compras directas rechazan materiales de control? | Sí. Guard con flag en `sale.create/update` y en `purchase.create/update` (no DP), el mismo patrón de #104 y #80 B3. El selector de material de Nueva/Editar venta los oculta. Con eso «¿es de control? → Salida de control» deja de depender de la memoria | No: ESTIBAS sigue vendible desde Ventas (aparece porque `lead_product = 'none'`), y una venta así saca inventario que nunca entró, a un precio. **Toca código compartido** (con flag; las 3 orgs no lo ven, y el PAR con y sin flag es la red) |
| D6 | ¿Dónde vive la Salida de control? | Entrada propia en el menú, «Salidas de control», junto a Salidas de Plomo | Pestaña dentro de Salidas de Plomo (como Crisol, #107): toca una página que el pedido dice no tocar, y su nombre dice «Plomo» |
| D7 | Q-75: ¿consecutivo propio o el talonario de las entradas? | Consecutivo propio, con la remisión como texto libre (cubre las dos respuestas) | Compartir la secuencia de `inbound_order_number`: mezclaría dos documentos en un número y se rompería la numeración de las Entradas, que es lo que Johana cuida |

R8c (la comisión excluye el control) no se pregunta: sale literal de «no tenerlas en cuenta».

## 6. Fuera de alcance (declarado)

- El camino Willard (`confirm`, `_apply_willard_effects`), que lo está tocando Coder 1, y Salidas de Plomo con su guard #103. Un material de control no puede llegar a ninguno de los dos (§3).
- Crear los materiales TUBULARES y ELECTROLITO: es un dato que se carga en Materiales (kg) después del deploy (runbook §9).
- Convertir o «reparar» las Entradas o compras **ya liquidadas a $1**, si las hubiera. Se mide antes del deploy (G-prod 2) y, si existen, decide Daniel.
- Un informe o export propio de las salidas de control: el listado tiene el Excel genérico de `DataTable`.
- Inventario o stock de materiales de control: no lo hay por diseño.

## 7. Golden, parity y no-regresión

**Golden: NO APLICA, medido** (`~/sac-evidencia/2026-11-24/documentos-control/golden_medicion.log`).
- Las rutas de `CAPTURES` son `/money-accounts`, `/money-movements`, `/reports/*` y `/warehouses`. Ninguna es de Entradas, perfiles ni salidas.
- `reports.py` lee `InboundOrder` en dos sitios, los dos con `status == 'annulled'`. Una Entrada cerrada no entra en ninguno, y no escribe MCH ni `annul_cost_adjustment`. El plan no toca `reports.py`.
- ⚠️ La predicción de ese log fue **0 coincidencias y salieron 2**: no conté los imports de `reports.py`. Quedan medidos y explicados en el mismo log.
- Si D5 se aprueba, los guards nuevos de `purchase.py` y `sale.py` **solo leen** y van detrás del flag. `/purchases` y `/sales` no son capturas.

**Parity check: APLICA** (migración nueva, con 2 tablas y 3 columnas). FKs sin nombre (default de PG, #111), y CHECKs como String+CHECK.

**Migración:** una sola, aditiva, sobre el head de develop:
- `material_kg_profiles.control_only`;
- `inbound_orders.closed_at` y `closed_by`;
- las tablas `control_dispatches` y `control_dispatch_lines`.
`created_at` y `updated_at` llevan el `server_default` de `TimestampMixin` (#100, el defecto que solo vio el smoke). Smoke up/down/up más un POST real.

**No-regresión de las 3 orgs:** todo router nuevo o tocado está detrás de `kg_ledger_enabled`. El único código compartido es `advisory_locks.py` (una secuencia más) y, con D5, los dos guards con flag.

**Guardas del árbol, siempre:** `test_reloj_de_negocio.py`, `test_advisory_locks.py` y `test_crucible_charges.py`.

## 8. Tests (T) y plantado (P)

**Tests nuevos:** `tests/test_sac_documentos_control.py`.

| T | Qué afirma |
|---|---|
| T1 | Marcar: `PUT …/control` crea el perfil si falta y lo devuelve. Con un mundo Willard o un plomo → 422 que nombra el campo |
| T2 | El upsert del perfil no borra la marca (manda los 3 campos sin `control_only`; la marca sigue). Poner un mundo Willard sobre un material marcado → 422 |
| T3 | Cerrar una Entrada solo de control desde `reviewed` y desde `draft` → `closed`, `display_status == 'closed'`, `closed_by`/`closed_at` puestos. **Cero filas nuevas** en purchases, inventory_movements, kg_ledger_movements, money_movements, inventory_adjustments y material_cost_history, por conteo antes y después |
| T4 | Cerrar una mixta → 422 que nombra el material con valor. Liquidar una solo de control → 422 que manda a cerrar |
| T5 | Paridad: `display_status_of` y `status_map` coinciden en `closed`, y el filtro `display_status=closed` la trae. Las bandejas `registered` y `reviewed` NO la traen. Extiende `test_filter_parity_with_field` |
| T6 | Mixta: liquidar sin las líneas de control da 200. Las compras tienen solo las líneas con valor, sin ajuste de descuadre del material de control. Mandar el material de control en el payload → 422 |
| T7 | Comisión: `suggested_collector_commission` de una mixta es igual a la de la misma Entrada sin la línea de control |
| T8 | Reabrir: cerrada desde `reviewed` vuelve a `reviewed`, y desde `draft` vuelve a `draft`. Reabrir una no cerrada → 400 |
| T9 | Editar una cerrada: líneas o fecha → 422, notas y remisión → 200. Anular una cerrada → 200 sin efectos. Desliquidar una cerrada → 400 |
| T10 | Báscula: revisar una mixta con la línea de control sin peso → 200. La línea con valor y sin peso sigue dando 400 |
| T11 | Alcance (#129): Ingrid recibe 403 en `close`, `reopen` y `/control-dispatches`. Su liquidación de una mixta con `require_full_allocation` no cuenta la estiba como hueco |
| T12 | Salida de control: crear y leer por HTTP. El número consecutivo arranca en 1 y es independiente de `inbound_order_number`. Material sin marca → 422 que lo nombra. Bodega de tránsito → 422 |
| T13 | Salida de control: crear, editar y anular dejan **cero filas** en las 6 tablas de efectos de T3 |
| T14 | Flag: sin `kg_ledger_enabled`, 403 en `close`, `/control` y `/control-dispatches` |
| T15 | Locks: `control_dispatch_number` está en `SEQUENCES` y `RANK`, y la llave es crc32 estable (calco de `test_advisory_locks`) |
| T16 (D5) | PAR con y sin flag: con flag, venta o compra directa con material de control → 400 que manda a la Salida o la Entrada de control; sin flag → 201 |
| T17 | Permisos con **control positivo** (memoria `test-de-permiso-necesita-control-positivo`): un rol con `purchases.view` y sin `purchases.liquidate` → 403 en `close` y 200 en el GET. Lo mismo con `sales.view` sin `sales.create` en `/control-dispatches` |

**Plantado** (la matriz va commiteada ANTES de plantar, con la predicción escrita):

| P | Defecto | Debe caer |
|---|---|---|
| P1 | Quitar la rama `closed` de `display_status_of` (cae a «liquidated») | T5 |
| P2 | Quitar `closed` de `status_map` | T5 |
| P3 | La completitud vuelve a exigir las líneas de control | T6 |
| P4 | `close` acepta una mixta | T4 |
| P5 | `close` crea una compra vacía, o cualquier fila de efectos | T3 |
| P6 | La comisión vuelve a contar el control | T7 |
| P7 | Reabrir va siempre a `draft` | T8 |
| P8 | El upsert borra la marca (default `false` en el schema) | T2 |
| P9 | La coherencia de la marca solo se chequea al marcar | T2 |
| P10 | La Salida de control acepta un material sin marca | T12 |
| P11 | La Salida de control comparte la secuencia de las Entradas | T12 |
| P12 | `_require_scale_weights` vuelve a exigir peso a las líneas de control | T10 |
| P13 | Se agrega `close` a `SCOPED_ENDPOINTS` | T11 |
| P14 (D5) | Se quita el flag del guard de ventas | T16 (rama sin flag) |
| P15 | Se cambia el permiso de `close` a `purchases.view` | T17 |

**e2e** (Playwright, 1440 y 390): marcar ESTIBAS; capturar una Entrada solo de estibas; cerrar, ver el badge y que salió de la bandeja; reabrir; Entrada mixta con la fila de control fuera de la matriz; crear una Salida de control y anularla. Capturas con control positivo.

**Dirigidas:** salen del `grep` sobre la superficie tocada, con el comando escrito en el log, incluidos los importadores de los importadores (memoria `dirigidas-grep-del-simbolo`). Mínimo: `test_inbound_orders.py`, `test_sac_entrada_sin_proveedor.py`, `test_sac_ciclo_c.py`, los tests del perfil kg (`form_order`), `test_advisory_locks.py`, los tests de alcance (#129), los de ventas y compras si D5, y las tres guardas del árbol. La suite completa se difiere al checkpoint.

## 9. Runbook (después del deploy; lo ejecuta quien Daniel diga)

**Antes del deploy (G-prod, por GET):**
1. Perfil actual de ESTIBAS en SAC: `willard_world` y `lead_product` tienen que ser `none`, o la marca dará 422.
2. ¿Hay compras o Entradas **liquidadas** con ESTIBAS, a $1? Si las hay, queda stock y deuda de antes. Decide Daniel, fuera de este ciclo.
3. Stock actual de ESTIBAS por bodega.

**Después:**
1. Marcar ESTIBAS como «Solo control» en Config → Materiales (kg).
2. Johana crea TUBULARES y ELECTROLITO con la marca, unidad a su elección.
3. Cerrar sin valor las 14 Entradas de ESTIBAS (16267–16454), una por una desde el detalle. Es una escritura en producción y la hace el usuario de SAC, no una sesión.

## 10. Coordinación con Coder 1

Coder 1 trabaja el factor de Willard en `inbound_order.py` (`confirm`, `_apply_willard_effects`) y en las pantallas de la Entrada.
- Este plan **no toca** esas funciones. Sí toca otras del mismo archivo (`liquidate`, `review`, `update`, `annul`, `display_status_of`, `get_multi`, `suggested_collector_commission`) y las páginas `InboundDetailPage`, `InboundLiquidatePage` e `InboundOrdersPage`.
- Es probable que haya conflictos de merge de texto, no de lógica. Propongo integrar primero el que termine antes, y que el segundo rebase antes de su pasada 2 de QA.
