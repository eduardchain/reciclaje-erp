# Plan — Entradas y Salidas «de control» (SAC, v1.3)

**Autor:** Eco Coder 2 · **Fecha:** 2026-11-24 · **Rama:** `coder-2/documentos-control` sobre develop `5139940`
**Nivel:** lógica (migración, reglas de estado en un servicio con dinero, guards en servicios compartidos si se aprueba D5).
**Autorización:** Daniel, 24-nov («esos dos, dale»), vía Coordinador. Este documento es SOLO el plan; construir exige el GO de QA 2 y después la autorización de Daniel.

**Cambios v1.2 → v1.3** (24-nov, después de la primera vista en localhost): Daniel aprobó 5 ajustes antes del deploy (ventanita de las ~21:15, vía Coordinador). Van en la §11, con su cómo, sus tests y su plantado. Las secciones 1–10 no cambian. Rama `coder-2/control-ajustes` sobre develop `7a3cb78`.

**Cambios v1.1 → v1.2** (GO condicionado de QA 2, `veredicto_plan_v1.1_5e9140fe.md`, `1f24ed16`):
- **C1:** la llave de la remisión es UNA sola expresión SQL, `remission_key`, que usan el orden, la marca «Repetida» y el aviso. No hay normalización en Python. Se agregan T23 (paridad con el conjunto de frontera) y P23.
- **C2:** un hueco se mide contra **toda** la org, sin importar la fecha ni el estado. Con búsqueda activa no se intercalan huecos. Se agregan los filtros remisión desde y hasta, y T24, T25 y P24.
- **O1:** la fila de la lista y `InboundLiquidatePage` con una Entrada solo de control (§4.4).
- **O2:** el tercero de la Salida de control no puede ser una entidad de sistema (§4.3).
- **O3:** Salidas de Plomo queda fuera del talonario, por escrito (§4.5).
- **O4:** que las Entradas Willard usen el mismo talonario es grado (c), y queda D11 para confirmarlo.

**Cambios v1.0 → v1.1:**
- **Q-75 respondida** (Daniel, 24-nov, vía Coordinador): las salidas de control usan el **mismo talonario de remisiones** que las Entradas. Por eso:
  - la remisión es obligatoria en la Salida de control (§4.3);
  - se agrega la vista común «Talonario de remisiones» con los huecos marcados (§4.5);
  - una remisión repetida entre los dos documentos se **avisa** (D8, §4.5);
  - D7 cambia de pregunta.
  Lo que anotan en cada salida (a quién, cantidad, peso) **no se preguntó** y sigue como supuesto.
- **C1 de QA 2** (notas preliminares sobre la v1.0, `4f4ae08d`): una Entrada desliquidada conserva sus compras `registered` en el puente. Cerrarla sin valor dejaría compras vivas, que #134 congela. Se agregan R2b y D10, y T6 cubre la re-liquidación de una mixta.
- Nota de QA 2: el guard de líneas y fecha de `update` es `== "liquidated"` (l.1755). R7 lo extiende a `closed` de forma explícita.

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

**Q-75, respondida** (Daniel, 24-nov, vía Coordinador): las salidas de control usan el **MISMO talonario de remisiones** que las Entradas. Para revisar que el talonario no tenga huecos, Johana tiene que poder ver Entradas y Salidas de control **juntas, ordenadas por remisión**.
- Lo que comparten es la **remisión**. El consecutivo interno del sistema puede seguir siendo propio de cada documento (D7).
- **Sigue como supuesto** lo que anotan en cada salida (a quién, cantidad, peso), porque no se preguntó. Por eso el plan deja opcionales el tercero y el peso. Son obligatorios la fecha, la bodega, la remisión y las líneas.

**Lo que valida hoy la Entrada sobre la remisión** (medido, `~/sac-evidencia/2026-11-24/documentos-control/remision_unica.log`):
- **nada más que el largo**: `Field(None, max_length=50)` en create y update (`schemas/inbound_order.py` l.71 y l.105), sin strip, sin índice ni constraint en ninguna migración y sin guard en el servicio;
- es opcional: en dev, la SAC activa tiene 27 Entradas no anuladas con remisión y 10 sin ella;
- en dev **no hay remisiones repetidas** entre Entradas no anuladas (0 grupos). ⚠️ **Dev no es prod** (memoria `copia-dev-no-es-replica`), así que la medición de prod queda como G-prod 4 (§9);
- en dev conviven remisiones de solo dígitos (13) y con texto (14). Las 14 de ESTIBAS en prod son numéricas (16267–16454).
- ⚠️ La primera corrida del log falló porque `psql` no está en el PATH (EXIT=127). Se re-corrió con `docker exec` y las dos quedaron en el log.

## 2. Dirección aprobada (Coordinador, 24-nov)

1. Marca «solo control» en Materiales (kg).
2. Una Entrada que tiene SOLO materiales de control muestra **«Cerrar sin valor»**:
   - es un estado terminal propio, ni Anulada ni Liquidada;
   - conserva el número y la remisión y sale de la bandeja;
   - tiene cero efectos: sin compras, inventario, kg ni saldos.
3. En una Entrada mixta, las líneas de control quedan fuera del reparto y del descuadre.
4. **«Salida de control»:** documento nuevo, sin efectos, con consecutivo propio. Lleva fecha, remisión, a quién, material de control, cantidad, peso y notas. **Salidas de Plomo y su guard #103 NO se tocan.**
5. (v1.1, Q-75) La remisión de la Salida de control sale del **mismo talonario** que las Entradas, y Johana ve los dos documentos juntos, ordenados por remisión (§4.5).

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
| R2b — compras del puente (C1 de QA 2) | Una Entrada **desliquidada** vuelve a `reviewed` y conserva sus compras `registered` en el puente (`_revert_entrada_liquidation`, l.1103-1120). Si después sus materiales se marcan de control (el caso de G-prod 2: ESTIBAS liquidadas a $1), un cierre sin más la dejaría en `closed` con compras vivas y stock en tránsito. #134 congela esas compras porque la Entrada no está anulada. **Recomendada (D10): rechazar.** Si `_linked_purchases` trae alguna compra no `cancelled`, `close` → 422 que nombra las compras y ofrece los dos caminos: anular la Entrada (que las cancela, l.1707-1719) o liquidarla. También rechaza si `annul_cost_adjustment != 0`: ese residuo de una desliquidación solo entra al P&L al **anular** (`reports.py` filtra `status == 'annulled'`, l.933-946), y en una cerrada se perdería en silencio. Hoy las dos condiciones van juntas, porque el residuo solo existe si hubo compras liquidadas, que vuelven `registered`; el chequeo se escribe igual, defensivo y con su razón. La alternativa de D10 está en §5 |
| R3 — estados de origen | `draft` y `reviewed` → `closed` (D2: no exige revisar). `liquidated`, `confirmed`, `annulled` o `closed` → 400 con el estado |
| R4 — efectos | **Cero.** Solo cambian `status`, `closed_at` (`now(utc)`, timestamp de auditoría, #87) y `closed_by`. Ningún `Purchase`, `InventoryMovement`, `KgLedgerMovement`, `MoneyMovement`, `InventoryAdjustment` ni MCH |
| R5 — número y remisión | Se conservan: no hay renumeración ni borrado |
| R6 — reabrir (D3) | `POST /inbound-orders/{id}/reopen`, con `purchases.cancel` (el de desliquidar). Solo desde `closed`. Vuelve a `reviewed` si tiene `reviewed_at`, y si no a `draft`: el cierre no borra la revisión, así que reabrir devuelve exactamente el estado de antes. Limpia `closed_at` y `closed_by` |
| R7 — editar una cerrada | Igual que una liquidada: `lines` y `date` dan 422 («reábrala primero»). Hoy el guard de `update` es `order.status == "liquidated"` (l.1755), así que **se extiende a `closed` de forma explícita** (nota de QA 2), con su propio mensaje. La sede ya da 422 por `_change_warehouse` (estado ∉ draft/reviewed). La cabecera (notas, remisión, vehículo, conductor, recolector) sigue editable. El recolector queda editable solo, porque su guard también es `== "liquidated"` (l.1795), y está bien: en una cerrada no hay comisión causada |
| R7b — anular una cerrada | Se permite, y es solo status y auditoría (cero efectos que revertir). `annul` ya acepta cualquier estado menos `annulled`; el `for` de compras del puente no encuentra ninguna |
| R7c — desliquidar o liquidar una cerrada | 400 con el estado, por los guards existentes más la rama nueva |

**Entrada mixta** (líneas con valor y líneas de control):

| Regla | Dónde |
|---|---|
| R8 — el reparto ignora el control | `liquidate`: la completitud (l.534-539) excluye las líneas de control. Un material de control en `payload.lines` → 422 que lo nombra («es de control: no se reparte ni se liquida»). Esto también cubre el camino D16 (un material que la báscula no vio) |
| R8a — re-liquidar una mixta (C1 de QA 2) | Caso: la Entrada se liquidó con la línea de ESTIBAS dentro de una compra, se desliquidó, se marcó ESTIBAS y se re-liquida. La sincronización por slot (#93 + #122) ya resuelve las dos variantes sin código nuevo. Si el slot conserva otras líneas, la firma cambia y la compra se edita (revert-and-reapply de registrada) **sin** la línea de control. Si el slot tenía solo control, desaparece del reparto y su compra se cancela (`from_inbound`). T6b y T6c lo afirman: no se supone |
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
  - `third_party_id` nullable (FK RESTRICT), a quién (supuesto: no se preguntó qué anotan);
  - `remission_number` `String(50)` **NOT NULL**: sale del mismo talonario de las Entradas (Q-75). Es obligatoria porque el talonario es la razón de ser del documento: una salida sin remisión no se puede ubicar en él. En el schema va `StringConstraints(strip_whitespace=True, min_length=1)`, porque `min_length` solo cuenta caracteres y `"  "` pasaría (lección de #100). El PATCH tampoco la deja vaciar. En la Entrada sigue opcional como hoy: volverla obligatoria es otro cambio, que no se pidió;
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
- tercero activo de la org, sin restricción de categoría (a quién se entregan estibas no es un rol), salvo las **entidades de sistema** (`is_system_entity`: `[Impuestos]`, `[Retenciones]`, prepagos), que dan 422, como en los otros selectores (O2 de QA 2). El selector de la pantalla tampoco las ofrece;
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
  - la fila de una Entrada solo de control en Registrada o Revisada no ofrece «Liquidar», que llevaría a una matriz vacía y a un 422 (R8d). Ofrece **«Cerrar sin valor»**, que abre el mismo diálogo del detalle (O1 de QA 2). Para saberlo, el response gana `is_control_only` (bool). Se calcula por página con **una** consulta de los perfiles de los materiales de la página (lookup por página, sin N+1) y se lee al momento, como R2;
  - badge gris «Sin valor»;
  - «Total $» queda en «—»;
  - el filtro de estado gana la opción «Cerradas sin valor». Las pestañas no cambian.
- **Liquidar (`InboundLiquidatePage`), entrando por URL con una Entrada solo de control:** no pinta la matriz. Muestra un aviso, «Esta Entrada es solo de control: ciérrela sin valor», con un enlace al detalle. Es el mismo patrón del aviso que ya pinta para un estado que no se puede liquidar (l.820).
- **Liquidar (`InboundLiquidatePage`), Entrada mixta:**
  - las filas de control no entran a la matriz;
  - se listan aparte, en solo lectura, con «control, no se liquida»;
  - `assertDraftShape` y la firma del borrador ignoran esas filas.

### 4.5 Talonario de remisiones (Q-75): vista común y remisión repetida

**Por qué una vista común y no un solo documento con dirección.** Meter la salida dentro de `inbound_orders` con una columna de dirección haría que cada camino de la Entrada tuviera que preguntarse «¿es de salida?»: liquidar, reparto, descuadre, comisión, puente de compras, Willard, alcance de recolector y `display_status`. Es la misma clase de defecto que #89/#93 (una columna con dos semánticas) y chocaría con el trabajo de Coder 1. Los dos documentos solo comparten la **remisión**, así que lo común es una **lectura**, no un modelo.

**Qué documentos entran al talonario:**
- las Entradas, tipo compra y Willard;
- las Salidas de control.

**Lo que queda fuera:**
- Salidas de Plomo, porque su `remission_number` es el número de **Willard**, digitado a mano (#105, Q-27), y no el talonario de SAC (O3 de QA 2);
- ⚠️ que las Entradas **Willard** usen el mismo talonario es una **inferencia nuestra, de grado (c)** (O4): sus remisiones de Q-76 (16272, 16341 y 16391) caen dentro del rango de las de ESTIBAS. Se confirma con Daniel (D11). Si la respuesta es que no, se excluyen con un `WHERE inbound_type = 'purchase'` en la vista y en el aviso, sin otro cambio.

#### La llave de la remisión: UNA sola implementación, en SQL (C1 de QA 2)

`remission_key(col)` (helper nuevo en `services/inbound_order.py`, junto a `_remission_order`) construye, a partir de una columna o de un parámetro ligado, las expresiones que usan **todos** los consumidores:
- `r = NULLIF(TRIM(col), '')` es la **vacía**, la misma definición que hoy usa #117.
- `numerica = CASE WHEN r ~ '^[0-9]+$' THEN CAST(r AS NUMERIC) END`. El regex de PostgreSQL es **ASCII**, así que «١٢» y «²» son texto. `NUMERIC` no tiene límite de dígitos, así que una remisión de 20 dígitos no desborda.
- `texto = lower(r)` (el `lower` de PostgreSQL). Para **ordenar** se le agrega `COLLATE "C"`, igual que hoy. Para **comparar** se usa la igualdad del `lower` del mismo servidor.
- `llave = CASE WHEN numerica IS NOT NULL THEN 'n:' || CAST(numerica AS TEXT) ELSE 't:' || texto END`. Es NULL si la remisión es vacía. «0012», «12» y « 12 » dan `n:12`. «R-12» y «r-12 » dan `t:r-12`. «012a», «12.0» y «16.300» dan `t:…`, distintos de `n:12` y de `n:16300`.

**Quién la usa, y ninguno normaliza en Python:**
1. `_remission_order` (el orden de la lista de Entradas, #117), que pasa a construirse con `remission_key` sin cambiar ninguna llave. Los tests de #117 son la red de que el refactor no cambió el orden.
2. El orden de la vista del talonario.
3. La marca **«Repetida»** de la vista: `COUNT(*) OVER (PARTITION BY llave)` mayor que 1 sobre la unión de los documentos **no anulados**. Las vacías no son repetidas, porque su llave es NULL y se excluyen.
4. El **aviso** de create y update: una consulta que compara `remission_key(columna) = remission_key(:remision_nueva)` en las dos tablas. La remisión que entra se normaliza **en SQL**, con el mismo helper aplicado al parámetro ligado.

No hay `normalize_remission` en Python. Si en la construcción apareciera la necesidad de uno (no la hay en este diseño), usaría `re.fullmatch(r"[0-9]+", s)` y nunca `str.isdigit()`, y entraría al test de paridad.

#### La vista: `GET /remissions`

**Acceso:** router con `require_org_flag("kg_ledger_enabled")`, permisos `purchases.view` **y** `sales.view`, fuera de `SCOPED_ENDPOINTS`.

**Filas:** una por documento, de los que entran al talonario. Las anuladas **también** salen, marcadas: usaron su papel, así que cubren su número.

**Columnas:**
- remisión;
- documento («Entrada #N» o «Salida de control #N»);
- dirección (entra o sale);
- fecha y estado;
- materiales en una línea;
- marca «Repetida»;
- enlace al detalle.

**Cómo se arma:** `UNION ALL` de dos `SELECT` mínimos, paginado sobre la unión. Los materiales se cargan después, solo para las filas de la página (lookup por página, nunca un join 1:N: #89/#93 R2).

**Filtros:**
- remisión **desde** y **hasta**, numéricas;
- fecha opcional;
- búsqueda por remisión.

**Orden:**
- **Por defecto**, sin filtros, de la remisión más alta a la más baja, para que lo reciente quede arriba. El orden de #117 tiene sus dos sentidos.
- El desempate es por fecha y número de documento.

**Huecos (C2 de QA 2): se miden contra la org, nunca contra lo filtrado.**
- Un número es **hueco** solo si **ningún** documento del talonario de la org lo tiene, cualquiera sea su fecha o su estado (las anuladas cubren su número).
- El servidor arma **una vez por pedido** el conjunto de llaves numéricas de toda la org. Es chico: en prod hay ~190 remisiones en 18 días.
- Entre dos filas numéricas **consecutivas de la lista filtrada y ordenada**, intercala una fila «Faltan N: de A a B» por cada tramo de números que no esté en ese conjunto. Si la 16305 está fechada en noviembre, la vista de diciembre **no** muestra un hueco entre 16304 y 16306.
- El cálculo va sobre la lista **filtrada entera**, no sobre la página (T22).
- Las filas de texto no tienen vecino numérico, así que no generan hueco y salen al final.
- **Con búsqueda activa no se intercalan huecos**: el resultado de una búsqueda no es un tramo del talonario.

**Entradas sin remisión:** no están en el talonario y no salen en la vista. El encabezado dice cuántas Entradas sin remisión hay dentro del filtro de fecha, para que no se pierdan en silencio.

**Pantalla:**
- «Talonario de remisiones», con un botón desde la lista de Entradas y otro desde la de Salidas de control;
- dual render: tabla en escritorio y tarjetas a 390;
- las filas de hueco van en ámbar.

#### Remisión repetida: se AVISA, no se rechaza (D8)

**Cuándo avisa:** en el **create y el update** (solo cuando cambia la remisión) de una Entrada **o** de una Salida de control. Si otro documento del talonario, **no anulado**, tiene la misma `llave`, la respuesta lleva un `warning` que **nombra** el otro documento: «La remisión 16300 ya está en la Entrada #142». El documento se guarda igual.

**Por qué avisar y no rechazar:**
1. Hoy la Entrada no valida nada (§1, medido). Un 422 nuevo podría trabar la edición de la cabecera de una Entrada que ya esté repetida en prod (G-prod 4 lo mide).
2. Un rechazo exigiría unicidad **entre dos tablas**, que PostgreSQL no da con un índice. Habría que serializar con un advisory lock, y eso suma un rango a `RANK`.
3. Es la filosofía del repo: #17/#76, «avisar, no bloquear».

La vista marca las repetidas con «Repetida», así que el aviso no depende de que alguien lea un toast.

**Los avisos llegan por HTTP** (lección de #100 D4d). El create de la Entrada ya devuelve `warnings` (`endpoints/inbound_orders.py` l.300-308), y la Salida de control nace con el campo. Los tests leen el aviso **de la respuesta**, no del servicio.

**Camino Willard:** el aviso en el create y el update de la Entrada **Willard** es una consulta de solo lectura que se agrega a la respuesta. No toca `_validate_willard_capture`, `confirm` ni `_apply_willard_effects`.

## 5. Decisiones que pide el plan (las toma Daniel, vía Coordinador)

| # | Pregunta | Recomendada | Alternativa y su costo |
|---|---|---|---|
| D1 | Nombre del estado | «Cerrada sin valor» | «Registrada sin valor». Se confunde con «Registrada», que es el borrador |
| D2 | ¿Se cierra desde Registrada, sin revisar? | Sí, desde Registrada y Revisada. La revisión certifica peso para valorar, y aquí no se valora nada | Solo desde Revisada: obliga a revisar estibas, con el peso que eso exige si no se aprueba D4 |
| D3 | ¿Se puede reabrir una cerrada? | Sí, con «Reabrir» (`purchases.cancel`), que vuelve al estado de antes | Sin reabrir: un cierre por error solo se arregla anulando, y anular **rompe el consecutivo**, que es justo lo que se quiere cuidar |
| D4 | ¿El peso de báscula es opcional en las líneas de control? | Sí | No: una Entrada mixta con estibas sin peso no se puede revisar |
| D5 | ¿Ventas y Compras directas rechazan materiales de control? | Sí. Guard con flag en `sale.create/update` y en `purchase.create/update` (no DP), el mismo patrón de #104 y #80 B3. El selector de material de Nueva/Editar venta los oculta. Con eso «¿es de control? → Salida de control» deja de depender de la memoria | No: ESTIBAS sigue vendible desde Ventas (aparece porque `lead_product = 'none'`), y una venta así saca inventario que nunca entró, a un precio. **Toca código compartido** (con flag; las 3 orgs no lo ven, y el PAR con y sin flag es la red) |
| D6 | ¿Dónde vive la Salida de control? | Entrada propia en el menú, «Salidas de control», junto a Salidas de Plomo | Pestaña dentro de Salidas de Plomo (como Crisol, #107): toca una página que el pedido dice no tocar, y su nombre dice «Plomo» |
| D7 | Q-75 ya está respondida: comparten el **talonario de remisiones**. Lo que queda por decidir es el **número interno** que da el sistema. ¿«Salida de control #N» propio o el de las Entradas? | Consecutivo propio (`control_dispatch_number`). Lo que Johana revisa es la remisión, y eso lo cubre la vista común (§4.5) | Compartir `inbound_order_number`: la numeración de Entradas pasaría a tener números que no son Entradas, y todas las pantallas que dicen «Entrada #N» tendrían huecos |
| D8 | Remisión repetida entre Entradas y Salidas de control: ¿avisar o rechazar? | **Avisar** con el documento nombrado, y marcar «Repetida» en la vista del talonario (§4.5) | Rechazar con 422: hace falta medir antes que prod no tenga repetidas (G-prod 4), porque si las tiene se traba la edición de esas Entradas. Además exige un advisory lock entre dos tablas |
| D9 | ¿Dónde vive la vista del talonario? | Página propia «Talonario de remisiones», con un botón desde la lista de Entradas y otro desde la de Salidas de control | Una pestaña dentro de Entradas: queda escondida para quien entra por Salidas, y la lista de Entradas ya tiene sus propias pestañas por estado |
| D10 | Cerrar sin valor una Entrada que tiene compras registradas en el puente (desliquidada; C1 de QA 2) | **Rechazar** con 422, que nombra las compras y ofrece anular o liquidar. Es la única forma de no perder en silencio el residuo de costo de la desliquidación, que solo entra al P&L al anular | Cancelar las compras dentro del mismo cierre (como `annul`, l.1707-1719): el cierre deja de tener cero efectos, y el residuo de `annul_cost_adjustment` no entraría nunca al P&L, porque `reports.py` solo lo lee de las anuladas |
| D11 | Confirmar un hecho (O4 de QA 2): ¿las Entradas **Willard** usan el mismo talonario de remisiones que las de compra? Hoy es una inferencia nuestra, grado (c), por el rango de Q-76 | Incluirlas en la vista y en el aviso, mientras Daniel no diga otra cosa | Excluirlas: un `WHERE inbound_type = 'purchase'` en la vista y en el aviso. Si están en el talonario y se excluyen, sus números saldrían como huecos falsos |

R8c (la comisión excluye el control) no se pregunta: sale literal de «no tenerlas en cuenta».

## 6. Fuera de alcance (declarado)

- El camino Willard (`confirm`, `_apply_willard_effects`), que lo está tocando Coder 1, y Salidas de Plomo con su guard #103. Un material de control no puede llegar a ninguno de los dos (§3).
- Crear los materiales TUBULARES y ELECTROLITO: es un dato que se carga en Materiales (kg) después del deploy (runbook §9).
- Convertir o «reparar» las Entradas o compras **ya liquidadas a $1**, si las hubiera. Se mide antes del deploy (G-prod 2) y, si existen, decide Daniel.
- Un informe o export propio de las salidas de control: el listado tiene el Excel genérico de `DataTable`.
- Inventario o stock de materiales de control: no lo hay por diseño.

## 7. Golden, parity y no-regresión

**Golden: NO APLICA, medido** (`~/sac-evidencia/2026-11-24/documentos-control/golden_medicion.log`).
- Las rutas de `CAPTURES` son `/money-accounts`, `/money-movements`, `/reports/*` y `/warehouses`. Ninguna es de Entradas, perfiles, salidas ni `/remissions`, que es nueva.
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
| T17 | Permisos con **control positivo** (memoria `test-de-permiso-necesita-control-positivo`): un rol con `purchases.view` y sin `purchases.liquidate` → 403 en `close` y 200 en el GET. Lo mismo con `sales.view` sin `sales.create` en `/control-dispatches`. En `/remissions`, un rol con `purchases.view` y sin `sales.view` → 403, y con los dos → 200 |
| T6b (C1) | Mixta re-liquidada después de marcar el control, cuando el slot **conserva** otras líneas: la compra existente se edita sin la línea de control. Su número no cambia, y sus líneas y su total quedan solo con lo que tiene valor |
| T6c (C1) | Mixta re-liquidada cuando el slot tenía **solo** la línea de control: su compra queda `cancelled` con el aviso «salió del reparto», y las otras compras se liquidan |
| T18 (C1) | Cerrar una Entrada desliquidada que conserva compras `registered` → 422 que nombra las compras. Cero cambios: sigue `reviewed` y las compras siguen `registered`. Con `annul_cost_adjustment != 0` forzado por ORM, y sin compras vivas, → 422 también |
| T19 | Salida de control sin remisión, con `""` o con `"  "` → 422. El PATCH tampoco la deja vaciar |
| T20 | Remisión repetida: crear una Salida de control con la remisión de una Entrada no anulada → 201 con el aviso que **nombra** la Entrada, leído **de la respuesta HTTP**. Al revés también (una Entrada con la remisión de una salida). «0016300» se cruza con «16300». Contra una **anulada** no hay aviso. Un update que no cambia la remisión no avisa |
| T21 | Vista del talonario: Entradas y Salidas de control intercaladas por remisión, con la anulada incluida y marcada. Hay una fila de hueco «Faltan 2: de 16301 a 16302» entre 16300 y 16303. Las remisiones de texto van al final y sin hueco. Una repetida sale con la marca. El encabezado cuenta las Entradas sin remisión. Una Salida de Plomo con remisión 16301 **no** tapa el hueco (O3) |
| T23 (C1) | **Paridad de la llave** con el conjunto de frontera, por HTTP y en los tres consumidores (orden de la lista de Entradas, «Repetida» de la vista, aviso). «0012» = «12» = « 12 » (una sola llave, se marcan repetidas y avisan); «012a», «R-12», «12.0» y «16.300» son texto y distintos de 12 y de 16300; «R-12» = «r-12 »; «١٢» es texto y distinto de 12; «» y «   » son vacías: no salen en la vista, no son repetidas entre sí y no avisan; un número de 20 dígitos ordena y se compara sin error. El orden de la lista de Entradas (#117) queda igual que antes del refactor: lo sostienen los tests de #117, sin cambiar |
| T24 (C2) | Hueco medido contra la org: 16304 y 16306 en diciembre, 16305 fechada en noviembre. La vista filtrada a diciembre **no** muestra hueco. Sin la 16305 en ningún lado, sí lo muestra. Una 16305 **anulada** también lo tapa |
| T25 (C2) | Con búsqueda activa («163») no hay filas de hueco. Con el filtro desde y hasta (16300–16310), los huecos de dentro salen y los de fuera no |
| T22 | Vista del talonario con paginación: el hueco entre la última fila de una página y la primera de la siguiente sale igual (se calcula sobre el rango, no sobre la página) |

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
| P16 (C1) | `close` no mira el puente de compras | T18 |
| P17 | La remisión de la Salida de control sin strip (pasa `"  "`) | T19 |
| P18 | El aviso de remisión repetida se calcula pero no llega al response | T20 |
| P19 | El aviso compara la remisión sin normalizar («0016300» ≠ «16300») | T20 |
| P20 | La vista excluye las anuladas (aparece un hueco falso) | T21 |
| P21 | Los huecos se calculan por página | T22 |
| P22 | El aviso cuenta a las anuladas | T20 |
| P23 (C1) | La llave decide «numérica» con `str.isdigit()` en Python, o con un regex sin anclas, en lugar del regex ASCII anclado de SQL | T23 («١٢» se cruza con «12») |
| P24 (C2) | Los huecos se calculan sobre el rango filtrado y no sobre el conjunto de la org | T24 |
| P25 (C2) | Con búsqueda activa se intercalan huecos | T25 |

**e2e** (Playwright, 1440 y 390): marcar ESTIBAS; capturar una Entrada solo de estibas; cerrar, ver el badge y que salió de la bandeja; reabrir; Entrada mixta con la fila de control fuera de la matriz; crear una Salida de control con la remisión de una Entrada y ver el aviso; anularla; abrir el Talonario de remisiones con una fila de hueco y una repetida. Capturas con control positivo.

**Dirigidas:** salen del `grep` sobre la superficie tocada, con el comando escrito en el log, incluidos los importadores de los importadores (memoria `dirigidas-grep-del-simbolo`). Mínimo: `test_inbound_orders.py`, `test_sac_entrada_sin_proveedor.py`, `test_sac_ciclo_c.py`, los tests del perfil kg (`form_order`), `test_advisory_locks.py`, los tests de alcance (#129), los de ventas y compras si D5, y las tres guardas del árbol. La suite completa se difiere al checkpoint.

## 9. Runbook (después del deploy; lo ejecuta quien Daniel diga)

**Antes del deploy (G-prod, por GET):**
1. Perfil actual de ESTIBAS en SAC: `willard_world` y `lead_product` tienen que ser `none`, o la marca dará 422.
2. ¿Hay compras o Entradas **liquidadas** con ESTIBAS, a $1? Si las hay, queda stock y deuda de antes. Decide Daniel, fuera de este ciclo.
3. Stock actual de ESTIBAS por bodega.
4. **Remisiones repetidas** entre Entradas no anuladas de SAC (Q-75, D8), y cuántas son de solo dígitos frente a texto. En dev hay 0 repetidas, pero dev no es prod. Si las hay, se listan para Daniel antes de construir el aviso: no cambia el diseño, cambia lo que Johana va a ver el primer día.
5. Entradas de SAC no anuladas con ESTIBAS **y** compras en el puente que no estén canceladas (C1, D10): son las que el cierre rechazaría.

**Después:**
1. Marcar ESTIBAS como «Solo control» en Config → Materiales (kg).
2. Johana crea TUBULARES y ELECTROLITO con la marca, unidad a su elección.
3. Cerrar sin valor las 14 Entradas de ESTIBAS (16267–16454), una por una desde el detalle. Es una escritura en producción y la hace el usuario de SAC, no una sesión.

## 10. Coordinación con Coder 1

Coder 1 trabaja el factor de Willard en `inbound_order.py` (`confirm`, `_apply_willard_effects`) y en las pantallas de la Entrada.
- Este plan **no toca** esas funciones. Sí toca otras del mismo archivo (`create` y `update` por el aviso de remisión, `liquidate`, `review`, `display_status_of`, `get_multi`, `_remission_order`, `suggested_collector_commission`) y las páginas `InboundDetailPage`, `InboundLiquidatePage` e `InboundOrdersPage`.
- Es probable que haya conflictos de merge de texto, no de lógica. Propongo integrar primero el que termine antes, y que el segundo rebase antes de su pasada 2 de QA.

## 11. Adenda v1.3 — los 5 ajustes de Daniel (24-nov)

Daniel vio la funcionalidad en localhost (12 pruebas cuadraron) y aprobó estos ajustes antes del deploy. Medido sobre `7a3cb78`. El nivel lo decide QA 2; el punto 2 toca el backend, así que lo propongo como **lógica**.

### 11.1 «Control» es una opción de Clasificación (FormulasPage)

Hoy un material de control se guarda como «Compra regular» (`willard_world='none'`, `compra_regular=true`) más `control_only=true`, y la tabla pinta dos badges: «Compra regular» y «Control».

**Cómo:**
- `Classification` gana `"control"`, con el rótulo «Control (sin valor)». El selector queda: Compra regular / Postconsumo (baterías) / Drosses / Control (sin valor). La casilla «Solo control (sin valor)» se quita. Su texto de ayuda pasa a ser el de la opción.
- **`classificationOf` mira `control_only` PRIMERO** (nota 2 de QA 2): con `control_only=true` devuelve `"control"`, sin importar `compra_regular` ni el mundo. Lo mismo para:
  - la píldora: una fila de control muestra solo «Control», nunca «Compra regular» al lado;
  - el filtro de la tabla: gana la opción «Control», y «Compra regular» excluye a los de control (hoy los incluiría, porque su `compra_regular` es true);
  - el export a Excel: `classification = "Control (sin valor)"` y `alsoCompra = false` para una fila de control.
- **Con qué flags se guarda** (nota 1): «Control» mapea a `willard_world='none'`, `lead_product='none'` y **`compra_regular=true`**. Así, los tres lectores de `compra_regular` no cambian por construcción:
  - el renglón del formato (`FormatoMateriales` l.60) sigue habilitado si el material está en el formato;
  - la captura (`InboundCreatePage` l.264) ya admitía el control;
  - el guard B3 de #80 (`purchase.py` l.2005) es inerte, porque exige `willard_world != 'none'`.
  `compra_regular` ya no se lee como «el usuario eligió Compra regular»: para un material de control solo dice «la captura lo deja pasar». La Compra directa la sigue frenando D5.
- **Lo que no se ofrece con «Control»** (nota 3): «También entra por compra regular» (solo existe en Willard) y el selector «Plomo entregable» (se oculta y se fuerza `none`). El factor tampoco: `isWillard` es false.
- **El orden del guardado no cambia** (§4.1): desmarcar → perfil → marcar → fórmula. Entrar a «Control» desde Willard o desde plomo primero guarda el perfil en `none` y después marca. Salir de «Control» desmarca primero y después reclasifica. `effControlOnly` pasa a ser `classification === "control"`, y `controlBlockedReason` desaparece: la exclusión ahora la da el selector.
- **Filas existentes sin re-guardar** (nota 4): ESTIBAS en dev (`compra_regular=true`, `control_only=true`) y en prod (marcada por el runbook, que solo usa `PUT /control`, así que conserva su `compra_regular`) se ven como «Control» apenas carga la pantalla, porque `classificationOf` mira la marca primero.
  - Si alguna fila de control tuviera `compra_regular=false` (solo por API), también se ve como «Control». Re-guardarla sin cambios la pasa a `compra_regular=true`: `profileChanged` compara ese campo. Lo declaro; no hay ninguna así en dev, y prod se mide en G-prod 6 (abajo).
- **Backend:** no cambia.

### 11.2 Tipo «Control» deducido en la lista y el detalle (Entradas)

**Cómo:**
- `EntradaTypeBadge` (que usan la lista y el detalle) y la tarjeta de 390 (l.579) muestran «Control», con badge gris, cuando `order.is_control_only` es true y la Entrada no es Willard. Si no, muestran lo de hoy. El pesador no elige nada nuevo: la Entrada se sigue capturando como tipo compra.
- **Filtro «Todos los tipos»:** gana «Control». La paginación es del servidor, así que el filtro va al backend.
  - `GET /inbound-orders` gana `control_only: Optional[bool]`. `get_multi` lo aplica con una sola expresión SQL que espeja el campo de la respuesta (`is_control_only` = tiene líneas y todas son de material con `control_only`, endpoint l.298):
    ```
    es_control = EXISTS(línea de la Entrada)
                 AND NOT EXISTS(línea cuyo material no tiene perfil de la org con control_only = true)
    ```
    `true` filtra `es_control`; `false` filtra `NOT es_control`. Todo va por EXISTS, sin join (trampa 1:N de #89/#93).
  - Pantalla: «Control» manda `control_only=true`. **«Compra regular» pasa a mandar `inbound_type=purchase&control_only=false`**: si la lista muestra el tipo «Control», el filtro «Compra regular» no puede traer esas Entradas (paridad filtro ↔ lo que se ve, como T5). Los filtros Willard no cambian; una Willard nunca es de control (§4.1).
- **Backend:** un parámetro opcional. Sin él, la consulta es la misma de hoy.

### 11.3 Pestaña «Cerradas sin valor»

- `TABS` gana `{ value: "closed", label: "Cerradas sin valor" }`, al lado de «Anuladas». `?tab=closed` ya funciona, porque `display_status=closed` existe desde la v1.2 (T5).
- Se quitan `closedOnly` y el desplegable de estados: solo tenía esa opción. En «Todas» se ven todas, como antes.
- **Backend:** no cambia.

### 11.4 Sin «Marcar Revisada» en una Entrada solo de control

- En el detalle, «Marcar Revisada» se oculta cuando `isControlOnly`. «Cerrar sin valor» ya se ofrece desde Registrada o Revisada.
- La fila de la lista ya ofrecía solo «Cerrar sin valor» (`closableControl`, l.160).
- Las que ya están en Revisada se cierran igual. D2 no cambia en el backend: `review` sigue aceptando una solo de control, por API.
- **Backend:** no cambia.

### 11.5 El hueco del talonario, en sus columnas

- Escritorio: la fila del hueco deja de ser una celda con `colSpan=6`. La columna Remisión lleva el rango («16255 – 16299»; un solo número va solo, «16255»), y la columna Documento lleva «Sin documento · 45 números» («1 número» en singular). Las otras 4 celdas quedan vacías y la fila sigue ámbar.
- 390: la tarjeta lleva el rango arriba y «Sin documento · N números» debajo.
- El conteo sigue siendo texto agrupado por miles sin pasar por `number` (2^53). `gapText` se parte en `gapRange` y `gapCountText`, puras.
- `GAP_NOTE` no cambia.
- **Backend:** no cambia.

### 11.6 Tests, plantado y gates de la adenda

**Backend**, en `test_sac_documentos_control.py`:
- **T26, paridad del filtro `control_only` con el campo.** Escenario:
  - una solo de control registrada;
  - una solo de control cerrada;
  - una mixta;
  - una compra normal;
  - una Willard;
  - una Entrada sin líneas, armada por ORM (N2 de QA 2: sin líneas no es solo de control).
  Afirma:
  - `control_only=true` da exactamente los ids con `is_control_only=true`, leídos de la misma lista sin filtro;
  - `false` da el complemento;
  - las dos son distintas de vacío (guarda anti-vacuidad, #110).
- **T27, «Compra regular» de la pantalla.** `inbound_type=purchase&control_only=false` trae la mixta y la compra normal, y no trae ni las de control ni la Willard. Combinado con `display_status=closed`, da vacío.

**Plantado:** la matriz va en adenda a `matriz-plantado-documentos-control.md`, commiteada antes de plantar.

| Fila | Defecto | Predicción |
|---|---|---|
| P30 | quitar el NOT de la rama `false` | = {t26, t27} |
| P31 | quitar el `EXISTS(línea)` | = {t26}, por la Entrada sin líneas |
| P32 | la rama `true` sin el `NOT EXISTS` (solo «tiene líneas») | = {t26}: trae la mixta y la compra normal |
| P33 | `true` y `false` invertidos | = {t26, t27} |

**Front:**
- lint (37 = techo), `tsc` y `build`, más las 3 guardas del árbol;
- e2e con Playwright, a 1440 y 390, contra :8012 sobre el árbol nuevo:
  - **Materiales (kg):** ESTIBAS sale «Control» sin re-guardar. El filtro «Control» trae solo los de control y «Compra regular» los excluye. Se pasa ESTIBAS a «Compra regular» y la API da `control_only=false`; se vuelve a «Control» y la API da `control_only=true`, `compra_regular=true`. El diálogo no ofrece «Plomo entregable» con «Control».
  - **Lista:** la #37 muestra el tipo «Control». El filtro «Control» trae solo las de control y «Compra regular» no las trae, con red registrada. La pestaña «Cerradas sin valor» existe y no hay desplegable de estados.
  - **Detalle:** la #37 no tiene «Marcar Revisada» y sí «Cerrar sin valor». Control positivo: una compra normal registrada sí tiene «Marcar Revisada».
  - **Talonario:** las columnas del hueco 16301 – 16302.

**Dirigidas:** set rehecho con `dirigidas_set.sh` sobre el árbol final, con la predicción escrita antes. **Golden:** no aplica, y se mide: el parámetro es opcional y ninguna captura toca `/inbound-orders`.

**G-prod 6 (lectura, la corre el Coordinador antes del deploy):** materiales de SAC con `control_only=true`, con su `compra_regular` y su `willard_world`. Esperado: ESTIBAS con `compra_regular=true` y `willard_world='none'`.
