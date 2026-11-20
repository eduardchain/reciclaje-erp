# Plan — Reparto por compra: la liquidación de la Entrada se llena por proveedor (SAC)

**Versión:** v1.2 · **Fecha:** 2026-11-20 · **Nivel:** lógica · **Base:** `d647410` (#121, después del redondeo #120)

**v1.2 (20-nov, madrugada), sobre la v1.1 con GO de QA (sha `29be1f12`):**
- Dos cambios posteriores al GO que ya estaban en el archivo: el párrafo de §5 sobre la rotación por kg (#101, pedido por QA al revisar el redondeo) y la decisión de Daniel sobre el borrador en `localStorage` (§9, antes «a decidir»).
- **A1–A5**, ajustes por releer el plan contra `d647410`. Cada uno está marcado en su lugar con su número.

**Pedidos de Johana (19-nov, vía Daniel; registrados en `inventario-preguntas-cliente.md`):**
1. **Orden del reparto.** «Es muy engorroso… hay que estar creando los proveedores material por material»; «en esta sola entrada hay 10 proveedores». Quiere trabajar «al revés»: «qué materiales de esa entrada se le compraron a ese proveedor». Mandó su hoja: una matriz de materiales × proveedores, con el precio una vez por material y totales por proveedor y por material.
2. **Q-65.** Un mismo proveedor puede tener **dos compras** en una Entrada: «son dos recolecciones».
3. **Crear el proveedor** desde la liquidación, o buscar uno existente, sin salir a Terceros.
4. **IVA 19 % en las compras**, que se sume y se lleve a la provisión del IVA. **Daniel (ventanita, 19-nov): va a la MISMA entidad `[Impuestos] IVA` de las ventas.**

**Fuera de este plan:**
- **Proveedores de Green Loop aparte y filtro por recolector:** espera Q-69 a Q-71 y tendrá plan propio. La ventana de crear proveedor (§5) se diseña para que después pueda pre-asignar la categoría del recolector sin rehacerse.
- **Redondeo del valor total:** `plan-redondeo-precio-compras.md`, que va antes.

**Abiertas con Johana que tocan este plan:** Q-66 (¿IVA por defecto o se marca?), Q-67 (¿IVA sobre todo o por material?) y Q-68 (¿reteIVA al proveedor con IVA?). §6 dice qué cambia con cada respuesta; el diseño base no cambia.

## 1. La idea: la columna es una COMPRA, no un proveedor

Hoy la unidad del reparto es el **proveedor**, y todo lo que se amarra a él se amarra por `third_party_id`:

| Pieza | Dónde |
|---|---|
| UNIQUE(línea, proveedor) en el reparto | `models/inbound_order.py:406-408` |
| Agrupación de las compras | `services/inbound_order.py:727` (`groups.setdefault(third_party_id)`) |
| Reuso al reliquidar | `:730-733`, `:760`, `:815` (`live_by_supplier[p.supplier_id]`): con dos compras del mismo proveedor, una se pisa en el dict y queda huérfana, **en silencio** |
| Retenciones | `:619-635` |
| Pago de contado | `:639-655` |
| Factura | primera no nula de cada grupo |
| Duplicado en la línea | `:556-562` |

**A2:** los números de línea de esta tabla y de §3.2 son de `d647410`; la v1.1 citaba `4dc2c73`, y el redondeo (#120) y el orden (#121) los corrieron. En la construcción se ubica cada sitio por su contenido (`grep`), no por el número.

Pasa a ser la **compra de la Entrada**, identificada por un número de orden dentro de ella (`purchase_slot`: 1, 2, 3…). Cada compra tiene **un** proveedor, y dos compras pueden tener el mismo. Es la columna de la hoja de Johana.

## 2. Modelo — migración (tabla exclusiva de SAC + una compartida por esquema)

1. **`inbound_line_allocations.purchase_slot`** (`SmallInteger`, NOT NULL, `>= 1`).
   - La UNIQUE pasa de `(inbound_line_id, third_party_id)` a **`(inbound_line_id, purchase_slot)`**: en una compra un material aparece una vez, que es una línea de compra.
   - Que todas las asignaciones de un slot tengan el mismo proveedor es una regla entre filas. Se valida en el servicio (§3.2) y no la impone la BD; queda declarado.
   - **Backfill (R7):** UNA sola función calcula, por Entrada, el mapeo proveedor → slot, y la usan tanto las asignaciones como el puente. Regla exacta: los proveedores se ordenan primero por el número más bajo de sus compras NO canceladas en el puente; los que no tienen compra van después, por nombre normalizado (`normalize_entity_name`) y luego por id. El slot es la posición 1, 2, 3…
   - **«Viva» = `status != 'cancelled'`** (registered o liquidated), tanto en el backfill como en el gate (R5). Las Entradas liquidadas tienen sus compras en `liquidated`.
2. **`inbound_order_purchases.purchase_slot`** (nullable en el esquema, y el backfill lo llena en TODAS las filas, R5).
   - Mismo mapeo, vía `purchase.supplier_id`. Para una compra cancelada se usa el slot de su proveedor si ese proveedor tiene slot; si no, el siguiente libre.
   - **Las legacy 1:1 (pre-#93) también se llenan** con el mismo mapeo. Si quedaran en NULL y esa Entrada se desliquidara y reliquidara, su compra viva no entraría a `live_by_slot`: se cancelaría como sobrante y nacería otra con número nuevo.
   - **Sin UNIQUE (entrada, slot) en el puente, y es a propósito** (R5). Si al reliquidar cambia el proveedor de un slot, quedan dos filas con ese slot: la compra cancelada y la nueva.
   - Cuántas filas legacy hay en producción se mide por GET, no con SQL contra prod.
3. **`document_taxes.purchase_id`** (FK nullable) para el IVA de compras (§4). El CHECK de dueño único pasa a «exactamente uno de tres» (#102 D1, #112).
   - La tabla es compartida por esquema y tiene **cero filas** fuera de SAC.
4. **Gate de datos en el upgrade** (#93 G1/G2): si alguna Entrada tiene dos compras VIVAS del mismo proveedor, hoy imposible, la migración se detiene con el listado en vez de inventar slots.

## 3. Backend

### 3.1 Schemas (`schemas/inbound_order.py`)
- `InboundAllocationCreate` gana `purchase_slot: int = Field(ge=1)`. Es obligatorio: el único cliente es la pantalla, que cambia en el mismo ciclo.
- `InboundSupplierRetentions` e `InboundSupplierPayment` pasan a identificarse por `purchase_slot`. Conservan `third_party_id` como dato de control: si no coincide con el proveedor del slot, 422.
- **Nuevo** `InboundPurchaseTaxes { purchase_slot, taxes: list[DocumentTaxCreate] }`. Hoy solo admite `iva` (§4). Es opcional, y si está ausente el camino es el de siempre.
- `InboundAllocationResponse` y `InboundPurchaseSummary` ganan `purchase_slot` (el endpoint arma la respuesta campo por campo: trampa #95).

### 3.2 `liquidate`
- **Validación por slot:**
  - un proveedor por slot (422 que nombra el slot y los dos proveedores);
  - una asignación por (línea, slot): el duplicado de `:533-541` pasa a ese par;
  - slots del payload consecutivos o no, da igual, pero cada uno con al menos una asignación.
  - Se conservan el guard del titular Willard (`:569-589`) y `_validate_third_party`.
- **Agrupación** por `purchase_slot` (`:701-705`).
- **Reuso al reliquidar** por `live_by_slot` (`:707-719`): toma las filas del puente con compra `registered`, tolera varias filas con el mismo slot (R5) y compara con la firma de #93 la compra del MISMO slot.
  - Si el proveedor de un slot cambió, la compra viva de ese slot se cancela y se crea otra, que es lo que hoy pasa cuando se quita un proveedor y se agrega otro.
  - **Defensa dura (QA c):** después de agrupar, cada compra que se va a reusar tiene que tener `supplier_id` igual al proveedor del slot. Si no, 409, con el mismo criterio del `:713`.
- **Retenciones, pago de contado, factura e IVA** se buscan por slot (`:803-830`). El candado anti doble pago (`:808-823`) ya mira la compra (`get_linked_payment_total(p.id)`), así que con slots queda correcto sin cambios.
- **El aviso «Ya existen N compra(s) del mismo proveedor en esta fecha»** (`purchase.py:200-207`), que `liquidate` reenvía (`:782`), deja de contar las compras de ESTA Entrada (las del puente), y nada más (R8). No es una bandera que lo apague para todo `from_inbound`: otra Entrada del mismo día con el mismo proveedor SÍ avisa. Las dos recolecciones de Johana son legítimas y el aviso le mentiría.
- `pesos_prorrateados` (`:434`, `:463-467`) pasa a llave `(material, slot)`.
- **Sin cambios:** descuadre (pesado − Σ asignaciones por línea), comisión del recolector (una por Entrada), `unliquidate`/`_revert_entrada_liquidation` (no miran proveedor), `annul`, `_change_warehouse` (#118) y los filtros del listado.

### 3.3 Crear proveedor (§5) — backend
- **`GET /third-parties/similar?name=&identification=`** (permiso `third_parties.view`, flag-gated; ruta estática declarada ANTES de `/{third_party_id}`, R10): terceros ACTIVOS de la org cuyo nombre normalizado con `normalize_entity_name` (#78, sin tildes ni mayúsculas) sea igual, o cuya identificación coincida (sin puntos, guiones ni espacios). Devuelve id, nombre, identificación y si es proveedor de material.
  - No hay ninguna detección de duplicados hoy: la tabla no tiene unicidad y el schema solo exige el nombre.
- La creación usa el **`POST /third-parties` existente** con `category_ids` = una categoría `material_supplier` y `initial_balance: 0`. Cero endpoints de escritura nuevos.
- «Agregarle la categoría de proveedor» a uno existente usa el `PUT` existente con sus categorías actuales MÁS la de proveedor. `_sync_category_assignments` borra y recrea, así que mandar solo la nueva le quitaría las otras; un test lo fija.

## 4. IVA en compras

- **Dónde vive:** `document_taxes` con dueño `purchase_id`. Es el mismo modelo de impuestos de documento de CC-013, con su entidad, su signo por mapa y su reversa. Se descartan dos alternativas:
  - un cuarto tipo en `retention_configs`/`purchase_retentions`: el signo es el contrario, y ese es el error que Johana intentó hacer desde la pantalla;
  - una tabla nueva: tendría que repetir entidad, signo y reversa.
- **Signo.** Hoy `TAX_SIGN_ON_CUSTOMER` dice el efecto sobre el CLIENTE de una venta. Para una compra, el IVA va con el signo opuesto sobre el tercero:
  - el proveedor queda −IVA: le debemos subtotal + IVA;
  - la entidad `[Impuestos] IVA` recibe +IVA: descuenta del IVA por pagar (decisión de Daniel).

  Se escribe UNA vez, como mapa por clase de dueño (`TAX_SIGN_ON_PARTY[owner_kind][tax_type]`), no como un `if` en cada consumidor (lección de la terna, #67/#69/#86). **Los cuatro sitios que hoy leen `TAX_SIGN_ON_CUSTOMER` pasan por ese mapa:** el efecto en `apply_taxes`, el `added`/`withheld` y su guard «retenciones ≥ subtotal + added» (`document_tax.py:83-95`, R3), el as-of de `reports.py` y el estado de cuenta.
- **Cuándo, y en qué orden (R3):** DENTRO de `purchase.liquidate`, con un kwarg nuevo `taxes_data` (ausente = camino de siempre, byte a byte), aplicado ANTES del Step 10. Hoy `net_payment = total_amount − total_retentions` (`purchase.py:604`), así que si el IVA se aplicara después, desde la Entrada, el contado pagaría sin IVA. El neto pasa a ser `total_amount + IVA − retenciones`. Todo en la transacción de la Entrada (D14 de #93).
  - Monto precalculado `19 % × subtotal de la compra` y editable: el monto digitado es la verdad (#79 F1).
- **Reversa (R4):** va en `purchase._revert_liquidation_effects`, el helper compartido de cancel y unliquidate (#93 D20c), y no solo en el camino de la Entrada, porque una compra derivada LIQUIDADA se puede cancelar directo desde Compras (#82 c). `revert_taxes` estampa `reverted_at`.
  - La precarga al reliquidar toma el último lote, igual que `_last_retention_batch`.
- **Consumidores compartidos que ganan la rama de compra** (golden aplica, §8):
  - `apply_taxes`/`revert_taxes` (`services/document_tax.py:45`, `:143`) aceptan `purchase_id` como tercer dueño;
  - **el balance as-of** (`services/reports.py:2706`, R2): `DocumentTax` ya es fuente de `_get_tp_balances_as_of`. Hoy hace join solo a `Sale`/`WillardDelivery` y calcula ahí los DOS lados, el del cliente y el de la entidad (por `DocumentTax.third_party_id`). Sin la rama `Purchase`, el IVA de compra faltaría en el corte de los dos terceros, no solo en el del proveedor.
  - **el estado de cuenta** (`endpoints/money_movements.py:1263`, `:1388-1404`, R1). Hoy pasa algo en silencio: la consulta del lado ENTIDAD (`DocumentTax.third_party_id == tercero`) no hace join al dueño, así que una fila con `purchase_id` YA le llega, `_tax_owner` devuelve None (`db.get(WillardDelivery, None)`) y se salta. El saldo vivo de `[Impuestos] IVA` la incluiría y el corrido no: se rompe #55. Con la rama nueva:
    - `_tax_owner` reconoce el dueño compra y devuelve la posición COMPLETA de la compra: clase 0, instante y número de la compra; en el par de reversa, el instante de la cancelación o desliquidación (regla del bloque 4b de #112);
    - la dirección sale del mapa por clase de dueño, no de `side × TAX_SIGN_ON_CUSTOMER`;
    - el lado del PROVEEDOR gana su propia consulta (join a `Purchase` por `supplier_id`);
    - el IVA de compra sale en las dos superficies del estado de cuenta, eventos y operaciones (#112).
- **Ni costo ni P&L:** el IVA descontable no entra al costo del material.

## 5. Pantalla — `InboundLiquidatePage`

**Escritorio (≥ md): la hoja de Johana.**
- **A1 (#121):** las filas salen de `orderedLines` (el orden del formato en papel, desempate alfabético). Las cards de hoy («Compras a nacer», `InboundLiquidatePage.tsx:426`) iteran `orderedLines` agrupando por `third_party_id`; pasan a agrupar por slot y conservan ese orden adentro. Las columnas van en orden de slot. El celular lista los materiales de cada tarjeta en el mismo orden.
- **Filas = materiales de la Entrada:**
  - pesado;
  - **precio de la fila**: un precio por material que sirve para todas las compras; arranca del precio de referencia o de la lista;
  - Σ repartido y descuadre en vivo.
- **Columnas = compras.** Encabezado con:
  - el proveedor (`EntitySelect` con búsqueda y «+ Crear proveedor»);
  - la factura;
  - el total de la compra.

  Un botón «+ Compra» agrega una columna. El mismo proveedor puede estar en dos columnas, que es el caso de Q-65.
- **Celda = cantidad.** Vacía es que no se le compró ese material.
  - El precio de la celda es el de la fila, salvo que se cambie en la celda.
  - Al cambiarlo se abre el editor de precio de hoy, con los tres modos: unitario, valor total (Q-15) y por kg (#101). Una celda con precio propio se pinta distinto.
  - Si el proveedor tiene lista de precios (#98) y su precio difiere del de la fila, la celda lo toma como propio y lo muestra.
- **Pie de cada columna:**
  - total de la compra;
  - IVA (§4);
  - retenciones;
  - pago de contado;
  - neto.
- La tabla es ancha (Opción B de CLAUDE.md): `overflow-x-auto`, con la columna de material sticky y `bg-white`.

- **Rotación de modos y el hallazgo de #101 (QA, 19-nov, al revisar el redondeo).** Hoy, con peso de báscula, la rotación es total → kg → unitario, y al pasar por kg el precio por kg se redondea a centavos. Ejemplo medido en la Entrada #27 de dev: $3.138.450 → 104,41 $/kg → $3.138.564,60, o sea que el número digitado se pierde ($114,60) al dar la vuelta. Es preexistente y se ve en la vista previa. **En la matriz el modo NO rota con la cifra:** cambiar de modo en el editor de la celda deja el campo nuevo vacío, con el valor anterior como texto de referencia («antes: $3.138.450 total»). Así ningún número digitado se transforma solo. Si en la construcción se elige conservar la conversión, se escribe aquí qué pasa al rotar, con este ejemplo como test de pantalla.

- **A3 (#120):** el precio de la asignación se guarda con 8 decimales, y `effUnitPrice` lo deriva así. Se conserva la regla C1 del redondeo: todo valor que pase de un cálculo a un `MoneyInput` editable de 2 decimales (el precio de la fila sugerido desde una celda, «Repartir todo», el valor «antes:») pasa por `toCents`. Como en la matriz el modo no rota la cifra, el único camino de ese tipo que queda es la sugerencia; un test de pantalla lo fija con el caso de Johana ($3.138.450 / 1.503).

**Celular (< md, 390 px): tarjetas por compra**, con el mismo estado. Cada tarjeta tiene el proveedor, sus materiales (cantidad y precio, con el editor de modos) y el pie. La matriz no cabe en 390 px.

**Se conservan:**
- **«Repartir todo a este proveedor»:** una sola compra con todo lo pesado; misma prioridad de precio que hoy.
- El material extra, la comisión del recolector y las marcas «sin proveedor, intencional» (D8 de #93) por material.

**Crear proveedor**, una ventana chica desde el selector de cualquier columna:
1. Pide nombre (obligatorio), identificación y teléfono.
2. Antes de crear consulta `/third-parties/similar`.
   - Si encuentra un proveedor: «Ya existe X», y el botón «Usar este» lo pone en la columna.
   - Si encuentra un tercero que no es proveedor (por ejemplo, un cliente): «Agregarle la categoría de proveedor y usarlo».
   - Si no encuentra nada: crea con la categoría `material_supplier`. Si hay una sola, la usa; si hay varias, la ventana las ofrece. En SAC dev hay una sola, «Proveedor Material».
3. Al guardar: invalida `["third-parties"]`, deja al proveedor seleccionado en esa columna y disponible en las demás.

La ventana es un componente nuevo con `onCreated(id)`. `ThirdPartyFormDialog` no devuelve el id creado, y vive en `pages/`.

**Lo que dicen los datos para el precio.** Un proveedor nuevo no tiene lista (#98 D3), así que no tiene sugerencia propia; con el precio por fila igual se le llena la celda. En SAC dev hay 0 listas activas. Producción se verifica por GET antes de construir.

**Los slots son IDENTIDAD y la pantalla nunca los renumera (R6).** Una columna nueva toma `max + 1`; al quitar una del medio queda el hueco; la precarga conserva los slots guardados. Si se renumerara, al reliquidar el slot 3 se compararía contra la compra del slot 2, se cancelaría y se recrearía, y se perderían números de compra. El encabezado muestra «Compra 1, 2, 4…» tal cual.

**La compra con IVA en sus propias pantallas (R9).** `PurchaseResponse` no trae impuestos: el `_tax_rows` de `sales.py:52` es por venta o salida. Sin cambio, `PurchaseDetailPage` y el PDF de #119 mostrarían el subtotal como si fuera el total. Alcance:
- `PurchaseResponse` gana `taxes` (detalle, no listado, decisión de #112) y `total_with_taxes`, que el endpoint arma campo por campo;
- el detalle y el PDF muestran el IVA y el total a pagar;
- **A4 (#119, #121):** `exportPurchasePDF` es compartido (Costa, Meta). El bloque de IVA se pinta SOLO si la compra trae `taxes` no vacío; sin impuestos el PDF sale igual byte a byte (content stream comparado con pypdf contra la base, como en #119, con control positivo). El llamador sigue pasando por el envoltorio de orden de #121 (`usePurchasePdfOrder`) y por el título de la remisión de #119;
- un test lo lee por HTTP (lección de #112 c).

**Estado:** el estado actual es `LineState[].allocations[]`, material → proveedores. Pasa a ser `purchases[]` (slot, proveedor, factura, IVA, retenciones, contado) más `cells[material][slot]`. El payload se arma transponiendo, al mismo `lines[].allocations[]` con `purchase_slot`. La precarga de un reparto guardado (`initLines`, `:194-223`, y retenciones `:304-339`) pasa a llave de slot. Hoy esa precarga de retenciones también se pisaría con dos compras del mismo proveedor.

**Detalle de la Entrada** (`InboundDetailPage`): las tarjetas «Compras por Proveedor» ya son una por compra (`:466-511`) y pasan a «Compras (N)». La sub-fila del reparto por material muestra «Compra n · proveedor».

## 6. Lo que cambia con las respuestas de Johana

| Pregunta | Si responde… | Cambia |
|---|---|---|
| Q-66 ¿quiénes cobran IVA? | pocos / la mayoría | si la casilla «Con IVA» de cada compra nace apagada o prendida. Nada más |
| Q-67 ¿IVA sobre todo o por material? | sobre todo | lo de §4 |
| | por material | la base pasa a ser la suma de las celdas marcadas; una marca por fila. El modelo no cambia: `base_amount` ya se persiste |
| Q-68 ¿reteIVA al proveedor con IVA? | sí | el guard de #112 (e) en `_apply_retentions`, que rechaza en compras las tarifas con `base_kind='iva'`, se levanta SOLO si la compra trae IVA, y la base es el IVA capturado. Sin IVA, sigue rechazando |
| | no | sin cambio |

El plan se puede aprobar sin las tres respuestas. Lo que dependa de Q-67 y Q-68 no se construye hasta tenerlas.

## 7. Tests

**Re-semantizados.** Son 19 tests que hoy asumen «una compra por proveedor». La lista sale del mapa del explorador:
- `test_sac_entrada_sin_proveedor.py`: `:465`, `:647`, `:852`, `:1423`, `:1460`, `:1479`, `:1520`, `:1568`, `:1740`, `:1772`, `:1825`, `:1849`, `:1868`, `:1895`, `:1918`, `:1950`, `:2184`, `:2237`, `:2563`;
- `test_inbound_orders.py:541`.

**A5:** las líneas citadas abajo son de la v1.1 y ya se corrieron con #120/#121; el set se saca con `grep` al construir. El helper `_alloc` gana `slot` con default por proveedor, para que los que no prueban slots no cambien de significado. El set exacto se recalcula con `grep` sobre `allocations`/`/liquidate` en `backend/tests` al construir, no de memoria (regla de #103).

**Nuevos** (`tests/test_sac_reparto_por_compra.py`):

| T | Caso | Afirma |
|---|---|---|
| T1 | Dos compras del MISMO proveedor (Q-65), materiales cruzados | 2 compras con sus líneas; el saldo del proveedor = suma de las dos; el aviso «mismo proveedor en esta fecha» NO sale |
| T2 | T1 → desliquidar → reliquidar sin cambios | los MISMOS números de compra (reuso por slot); ninguna huérfana |
| T3 | T2, pero se cambia el proveedor del slot 2 | la compra vieja del slot 2 se cancela, nace una nueva, la del slot 1 intacta |
| T4 | Mismo material dos veces en el mismo slot | 422 que nombra material y compra |
| T5 | Un slot con dos proveedores | 422 |
| T6 | Retenciones y contado por slot con `third_party_id` que no coincide | 422; sin escritura (atomicidad leída por HTTP) |
| T7 | IVA en una compra: liquidar | proveedor −(subtotal + IVA); `[Impuestos] IVA` +IVA; el contado paga subtotal + IVA − retenciones; costo del material = subtotal (no incluye IVA) |
| T8 | IVA de compra y de venta en la misma org | la entidad nettea: saldo = IVA de la venta − IVA de la compra; clasificación del balance por signo (#112 P19). **Estado de cuenta de la ENTIDAD leído por HTTP con los dos mezclados** (R1): corrido == vivo, cada impuesto debajo de su documento, y en las dos superficies (eventos y operaciones) |
| T9 | T7 → desliquidar | IVA revertido (`reverted_at`); saldos al de antes; corrido == vivo (#55) en el estado de cuenta del proveedor Y de la entidad, con el par de reversa en la posición de la desliquidación |
| T9b | Compra con IVA cancelada DIRECTO desde Compras (R4) | entidad y proveedor vuelven al saldo de antes; el par sale en los dos estados de cuenta |
| T10 | Balance as-of con IVA de compra antes y después del corte | `_get_tp_balances_as_of` lo cuenta en el proveedor Y en la entidad, a los dos lados del corte (R2) |
| T10b | Detalle de la compra con IVA y PDF (R9) | `GET /purchases/{id}` trae `taxes` y `total_with_taxes`, leídos por HTTP |
| T11 | `GET /third-parties/similar` | match por nombre sin tildes ni mayúsculas, por identificación con puntos, no devuelve inactivos ni de otra org; 403 sin flag. **Permiso (R10, #111):** rol custom con `third_parties.view` → 200 (control positivo), rol sin él → 403 |
| T16 | Slots como identidad (R6): tres compras → desliquidar → quitar la del medio → reliquidar | las otras dos conservan su número; la del medio sale cancelada como sobrante |
| T17 | Aviso de duplicado (R8) | dentro de la Entrada no avisa; otra Entrada del mismo día con el mismo proveedor SÍ avisa |
| T18 | Defensa dura (QA c): una compra del puente con slot cuyo proveedor no coincide (forzada por ORM) | 409 |
| T12 | Agregar la categoría de proveedor a un cliente existente | conserva la de cliente (el PUT manda las dos) |
| T13 | Gate del backfill: una Entrada con dos compras vivas del mismo proveedor | la migración se detiene con el listado |
| T14 | Backfill de slots (R7) | slots deterministas; el mapeo de las asignaciones y el del puente salen iguales (se comparan); las Entradas desliquidadas existentes y una legacy 1:1 reliquidan con los mismos números |
| T15 | Costa: compra directa sin Entrada | sin `document_taxes` ni cambio de saldos: no-regresión |

## 8. Gates

- ruff, tsc, eslint (37 = techo).
- **QA pasada 1:** el código y los tests, antes de cualquier gate (flujo del 17-nov).
- **Dirigidas por grep**, con el comando en el log:
  - superficie: Entradas, compras, `document_tax`, `reports.py` (balance as-of) y `money_movements.py` (estado de cuenta);
  - más las tres guardas del árbol.
- **Plantado** con matriz commiteada ANTES:
  - una fila por cada pieza de §3.2 y §4: agrupar por proveedor en vez de por slot, reuso por proveedor, signo del IVA de compra invertido, as-of sin rama `Purchase`, aviso de duplicado sin suprimir;
  - el PUT de categorías mandando solo la nueva;
  - (R1–R4) el estado de cuenta de la entidad sin la rama compra en `_tax_owner`; `added`/`withheld` con el mapa de venta; el IVA aplicado después del Step 10; la reversa solo en el camino de la Entrada;
  - (R5–R8) las filas legacy del puente en NULL; la pantalla renumerando slots; el aviso apagado con una bandera para todo `from_inbound`.
- **Parity check:** DIFF CERO.
- **Smoke de migración en dev:** up, down y up, con el backfill sobre la Entrada #25 (dos proveedores) y una Entrada desliquidada.
- **Golden: APLICA** (`reports.py`, `money_movements.py` y el CHECK de `document_taxes`).
  - **Una sola BD alcanza, y por qué (R10):** la migración es aditiva. Son columnas nullable más un CHECK ampliado que las filas existentes cumplen («uno de tres»), y ningún valor existente cambia de escala ni de contenido. Distinto del redondeo, que necesita dos BDs.
  - Predicción: 0 diffs reales y 0 aditivas, porque Costa y Meta no tienen filas de `document_taxes` ni Entradas.
  - **Prueba de que los dos procesos son códigos distintos (R10, #110)**, en el log ANTES de capturar: `GET /third-parties/similar` da 404 en la base y 200 en develop.
  - La rama nueva no la ve el golden: su control positivo es el smoke de SAC en dev. Se dice así en el log, y el golden no se presenta como prueba de la rama nueva.
- **Suite completa:** diferida al checkpoint.
- **Pantalla de Daniel en localhost**, a 1440 y 390 px:
  - la Entrada de 10 proveedores reconstruida con la hoja de Johana;
  - dos compras de CHREPUESTOS;
  - crear un proveedor nuevo y uno que ya existe;
  - una compra con IVA y su PDF.

## 9. Riesgos y lo que queda declarado

- **La pantalla se reescribe casi entera** (1.501 líneas). El riesgo real son las clases que ningún gate ve: hooks después de un `return` (#93 a) y `Decimal` como string (#93 b, #107). ESLint cubre la primera; para la segunda, todo número que viene del servidor pasa por `num()` en la frontera. Abrir la pantalla es parte de terminar.
- **El reparto solo se guarda al liquidar.** No hay endpoint para guardarlo antes. Con 10 compras, un error de red pierde lo digitado. **Daniel (ventanita, 19-nov): sí.** Borrador en `localStorage` por Entrada y usuario, con try/catch en cada lectura y escritura. Se recupera al volver a la Entrada, se borra al liquidar y la pantalla funciona igual sin él.
- **El proveedor del slot es una regla entre filas que impone el servicio, no la BD.** Si otro escritor de asignaciones aparece mañana, la tiene que respetar. Hoy no hay otro: `liquidate` es el único (verificado).
