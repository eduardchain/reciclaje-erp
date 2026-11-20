# Plan: Detalle de Entrada, las compras en tabla y el total con IVA (v1.2)

Autor: Eco Coder 1 · 20-nov-2026 · rama `coder-1/compras-entrada-tabla` (base develop `87c799f`, traída con merge `1ce3156`)
Base: escrito sobre `31ba117`, rebasado a `1aacc2f` y con develop `87c799f` mergeado; `git diff --name-only 1aacc2f 87c799f` sobre `pages/inbound`, `types/inbound.ts` y los tres archivos de backend de Entradas sale vacío. El delta `31ba117..1aacc2f` (MoneyInput y Ocultar Listas) no toca `frontend/src/pages/inbound`, `types/inbound.ts` ni `backend`, y `InboundDetailPage` no usa `MoneyInput`. Artefacto: `delta_develop_superficie.log`.
v1.1 (20-nov): C1 y C2 del GO de QA 1 sobre la v1.0 (`830ecb7`), las dos del instrumento. C1: el setup suma una compra con IVA **y** retención, y E8 se mide sobre ella. C2: la predicción de P2 se escribe después de medir en el `GET` del setup qué compras vigentes traen IVA revertido. Develop ya está en `80afd45`; la construcción arranca con un merge de develop, y la entrega sale con merge-base == develop.
v1.2 (20-nov): **Daniel autorizó construir** y decidió O1–O3. **O1 va contra mi recomendación**: las compras de una Entrada desliquidada **dejan de sumar** en «Total Liquidado» hasta que se vuelva a liquidar. O2 y O3, como estaban recomendados. Cambian D1 (fila de totales), D4, el D7 nuevo (listado), §1, §3, E2/E3/E7, los E10–E11 nuevos y las filas P10–P12. Los lectores se encontraron por grep (`lectores_total_liquidado.log`), no de memoria.
Pedido: el Coordinador, 20-nov, desde la revisión en pantalla de #122 con Daniel. Con 10 compras, las tarjetas de `InboundDetailPage` no se leen. En la Entrada #12, «Total Liquidado» dice $200.000 y no dice en ningún lado que el IVA es $36.480.

**Nivel: lógica. Solo frontend, cero backend.** La subo a lógica aunque no toca el servidor porque agrega dos cálculos de plata que Johana usa para pagar: la fila de totales y el total con IVA. Además cada uno tiene una regla de exclusión: qué compras no suman y qué IVA no cuenta. La definición de nivel chico del protocolo («sin reglas ni cálculos») no alcanza a cubrirlo.

## 1. Qué pasa hoy

- **Tarjetas.** `InboundDetailPage` pinta una tarjeta por compra del reparto, en una grilla `grid-cols-1 sm:grid-cols-2 md:grid-cols-3`, ordenada por `purchase_slot` y después por `purchase_number`.
  - Cada tarjeta lleva el slot, el proveedor (link), el estado, «Compra #N» (link), el subtotal y la factura.
  - Si hay IVA o retenciones, agrega una línea «IVA · Retenciones · Total al proveedor».
  - La cancelada sale en rosa y con opacidad.
- **IVA por compra: ya llega, no hay que tocar el servidor.**
  - `InboundPurchaseSummary.taxes` existe desde #122 §4. Viene en el listado **y** en el detalle, por `purchase_extras`, que es un lookup por página (R2, sin outerjoin) en `backend/app/services/inbound_order.py:2254`.
  - Cada fila trae su `reverted_at`. La página ya calcula el IVA vivo así: `taxes.filter(t => t.tax_type === "iva" && !t.reverted_at)`, en `InboundDetailPage.tsx:479`.
  - `retentions_total` ya es solo la suma de las retenciones vivas (`reverted_at IS NULL`, `inbound_orders.py:204`).
  - Las canceladas también llegan: `purchases_by_order` dice «Incluye canceladas (el display decide como mostrarlas)», en `inbound_order.py:2233`.
- **«Total Liquidado»** (`InfoRow`, `InboundDetailPage.tsx:390`) es `Σ total_amount` de las compras con `status !== "cancelled"` (`liquidatedTotal`, línea 142), sin IVA. Se muestra con `purchases.view_prices` y `purchases.length > 0`. **Después de desliquidar sigue sumando** las compras `registered`: es lo que O1 corrige.
- **Lectores de ese conjunto, por grep** (`lectores_total_liquidado.log`):
  - el detalle: `liquidatedTotal` → «Total Liquidado»;
  - el **listado de Entradas**: `purchaseTotal(order)` en `InboundOrdersPage.tsx:128`, que alimenta la columna «Kg Plomo / Total $» (escritorio, línea 340) y la tarjeta móvil (línea 515). Su regla es «liquidada = Σ compras del reparto; pendiente = referencia capturada», y la escribe como `status !== "cancelled"`, o sea que una desliquidada también suma ahí;
  - **no lo leen**: el PDF (`pdfExport.ts` solo usa la remisión), el export a Excel del listado (la columna «efecto» no tiene `accessorKey`, así que `DataTable` exporta la celda vacía: es preexistente y no se toca), «Total Capturado (ref.)» (es Σ cantidad × precio de las líneas, la referencia de la captura) y el backend (ningún total de Entrada se calcula en el servidor; `total_amount` es por compra).

## 2. Qué cambia

### D1. Una tabla con una fila por compra (desde 768 px)

Columnas, en este orden:

| # | Columna | Origen | Con `view_prices` |
|---|---|---|---|
| 1 | Compra | `Compra #N` → link `PurchaseLink`, con «Compra {slot}» chico debajo | siempre |
| 2 | Proveedor | `ThirdPartyLink` | siempre |
| 3 | Factura | `invoice_number` o «—» | siempre |
| 4 | Materiales | D3 | siempre |
| 5 | Subtotal | `total_amount` | solo con permiso |
| 6 | IVA | IVA vivo (D2) | solo con permiso |
| 7 | Retenciones | `retentions_total` (vivas) | solo con permiso |
| 8 | Total al proveedor | subtotal + IVA − retenciones (D2) | solo con permiso |
| 9 | Estado | `StatusBadge` | siempre |

- **Fila de totales** al pie, con permiso: suma las columnas 5 a 8 sobre las compras **liquidadas** (D4) y dice cuántas son: «Total (N compras liquidadas)». Si no hay ninguna (Entrada desliquidada), la fila dice «Sin compras liquidadas» sin montos.
- **Orden.** Primero las no canceladas por slot y número, como hoy. Después las canceladas, en gris y tachadas, con «no suma». La fila de totales queda al final.
- **Una compra `registered`** (Entrada desliquidada) se muestra con sus montos y el estado «Registrada», en gris claro y sin tachar, con «no suma: sin liquidar».
- Los números van con `tabular-nums`, alineados a la derecha. Si hay pocas filas, la tabla se queda sin scroll interno. Para pantallas de 768 a 1024 px va dentro de `overflow-x-auto` con un `min-w` (patrón B de CLAUDE.md), para que 9 columnas no se aprieten.

### D2. Un solo cálculo por compra, usado por la tabla, las tarjetas y los totales

Es una función pura, `purchaseMoney(p)`, en `frontend/src/utils/inboundPurchases.ts` (junto con `countsAsLiquidated`, D4, que también lee el listado), que devuelve `{ subtotal, iva, ret, total }`:
- `iva` = Σ `amount` de `taxes` con `tax_type === "iva"` y sin `reverted_at`. Es la regla que ya está en la tarjeta, ahora escrita una sola vez.
- `ret` = `num(retentions_total)`.
- `total` = `subtotal + iva − ret`.

Los `num()` siguen en la frontera: el `Decimal` del backend llega como string (#93 b, #107).

La tarjeta (D5) deja de calcular por su cuenta y llama a esta función. La fila de totales suma lo que devuelve. Así la tabla, las tarjetas y el pie no pueden dar números distintos.

### D3. Materiales de cada compra, desde el reparto

- `InboundPurchaseSummary` no trae líneas. Los materiales salen de `order.lines[].allocations`, que ya están en el detalle, filtrando por `allocation.purchase_slot === p.purchase_slot`.
- Formato del patrón #82: hasta 3 renglones «CÓDIGO cantidad unidad», más «+N más».
- **Una compra cancelada muestra «—».** Su slot lo puede estar usando una compra nueva (R5/R6 de #122: se reliquidó con los proveedores intercambiados). Pintarle los materiales del reparto actual le asignaría lo que hoy es de otra compra.
- Una compra con `purchase_slot === null` (legacy, la migración no lo deja) también muestra «—».
- Sin `view_prices` se muestran código y cantidad, sin precio. Hoy la tarjeta no muestra materiales, así que no se pierde nada.

### D4. Qué compras suman, y el «Total con IVA» al lado de «Total Liquidado»

**Criterio único (O1 de Daniel):** suma una compra **si y solo si `status === "liquidated"`**. Es un predicado de módulo, `countsAsLiquidated(p)`, en `utils/inboundPurchases.ts`, junto con `purchaseMoney` (D2). Lo usan **todos** los lectores: el detalle («Total Liquidado», «Total con IVA», la fila de totales y la tarjeta de totales móvil) y el listado (`purchaseTotal`, D7).

Por qué el estado de la **compra** y no el de la Entrada ni `liquidated_at`:
- **La compra es el registro que lleva el efecto financiero.** Desliquidar (#93 D20) pasa **todas** las compras de la Entrada a `registered` en una transacción, y liquidar (D14) las pasa a `liquidated` juntas. Mientras se use la Entrada, los dos criterios dan lo mismo.
- **Donde difieren, gana la compra**: el legacy 1:1 (#93), con la Entrada `confirmed` y la compra derivada todavía `registered`. Esa compra no está liquidada y no debe sumar. La migración de #93 (G1) obligó a liquidar o anular las derivadas registradas antes del deploy, así que en producción no debería quedar ninguna; si queda, el número dice la verdad.
- **`liquidated_at` no llega al frontend**: `InboundPurchaseSummary` no lo trae. Usarlo exigiría tocar el backend por un dato equivalente al `status`.
- **Una cancelada** nunca suma, igual que hoy. Incluye las de R6 y las de una Entrada anulada: anular delega en desliquidar y después cancela.

**Qué se ve:**
- **«Total Liquidado»**: Σ `total_amount` de las liquidadas. El `InfoRow` se muestra **solo si hay al menos una liquidada**. En una Entrada desliquidada **desaparece**, en vez de decir «$0», porque un cero se leería como «se liquidó por cero». La tabla sigue mostrando las compras con su estado.
- **«Total con IVA»** (O3), justo debajo: Σ (`subtotal + iva`) de las liquidadas, con `view_prices`, **solo si ese IVA es > 0**. Para la Entrada #12 serían $236.480.
- **El neto al proveedor** (− retenciones) va solo en la fila de totales de la tabla (O2).
- **Compra desliquidada** (`registered`, con su IVA y sus retenciones revertidos): la fila muestra el subtotal, IVA 0, retenciones 0 y «Registrada»; **no suma** en ningún total.
- **Compra cancelada:** fila gris, «no suma», montos tachados y materiales «—» (D3).

### D5. Los 390 px: render dual

- Va el patrón A de CLAUDE.md. La tabla queda en `<div className="hidden md:block">` y las tarjetas actuales en `<div className="md:hidden space-y-2">`.
- Las tarjetas **se conservan casi intactas**: la grilla `grid-cols-1 sm:grid-cols-2 md:grid-cols-3` pasa a `md:hidden`, y el cálculo de la línea de IVA pasa a `purchaseMoney` (D2).
- Al pie de las tarjetas va una tarjeta de totales con las mismas sumas de la fila de la tabla.
- Además de la captura, la verificación de 390 mide `scrollWidth <= clientWidth` en `#main-scroll`.

### D6. Cruce con Coder 2 (Ingrid, rama `coder-2/recolector-alcance`)

Medido con `git diff 31ba117 coder-2/recolector-alcance -- frontend/src/pages/inbound/InboundDetailPage.tsx` (rama en `41940cf`). El artefacto es `~/sac-evidencia/2026-11-20/coder-1-compras-tabla/cruce_coder2.log`.

**Coder 2 toca justo las tarjetas.**
- Agrega `outOfScope(supplierId)`, sacado de `useScopeSupplierIds`.
- Con alcance, una compra de un proveedor fuera del alcance:
  - se pinta **sin link** en el proveedor y en «Compra #N», porque el link daría 404;
  - lleva una nota ámbar: «Proveedor sin la marca de {recolector}: pídele a SAC que lo marque en Terceros».
- También cambia el criterio de `taxes` en el servidor (`last_liquidation_batch`, plan Ingrid v1.7). **No afecta a esta tabla**: la tabla filtra por `!reverted_at`, y el lote nuevo sigue trayendo `reverted_at`, así que el IVA vivo es el mismo con las dos versiones. `retentions_total` no cambia.

**Cómo se resuelve el merge.**
- Las tarjetas se quedan en su lugar con los mínimos cambios (D5), así que los hunks de Coder 2 caen sobre líneas que no muevo. El único cambio cerca es el bloque `iva`/`ret` de las líneas 479-482, que queda a más de 3 líneas de su primer hunk (494).
- La **tabla es código nuevo**, y necesita la misma regla de alcance en dos celdas: Compra y Proveedor. La nota va como renglón ámbar debajo del nombre del proveedor.
- **Si Coder 2 integra primero:** traigo develop con un merge **antes de construir la tabla** y la escribo usando `outOfScope`. Agrego E9 (ver §4), y el delta va a QA 1.
- **Si integro yo primero:** le dejo a Coder 2 la receta escrita. En la tabla, `outOfScope(p.supplier_id)` decide link o texto en las celdas 1 y 2, y la nota va debajo del proveedor, igual que en la tarjeta.
- En los dos casos, la tabla y la tarjeta tienen que dar el mismo resultado con alcance: ningún link de una compra fuera del alcance.
- **Listado (D7, v1.2):** Coder 2 también toca `InboundOrdersPage.tsx`, en la rama `c0ef770`, medido contra `87c799f` en `cruce_coder2_listado.log`. Sus hunks son la desestructuración de `usePermissions` (desde la línea 144), `useWarehouses(unscoped)` y el filtro de sede oculto con alcance. D7 cambia `purchaseTotal` (líneas 128-131) y agrega un import. Hay más de 3 líneas entre los dos cambios y no se toca el mismo bloque, así que no hay conflicto textual previsto. Con alcance, el «Total $» se rige igual por `countsAsLiquidated`, y la plata la gobierna `view_prices` como hoy.

### D7. El listado de Entradas usa el mismo criterio (O1)

- `purchaseTotal(order)` (`InboundOrdersPage.tsx:128`) pasa a `order.purchases.filter(countsAsLiquidated)`.
- Si hay al menos una liquidada, la columna vale Σ de esas. Si no, cae a la referencia capturada (Σ cantidad × `unit_price` de las líneas), que es lo que su docstring ya dice para una Entrada pendiente. Una Entrada desliquidada **vuelve a verse como pendiente**: muestra su referencia, que puede ser $0 (#93 captura sin precios), y no la suma de compras que ya no están liquidadas.
- La tarjeta móvil del listado (línea 515) llama a la misma función, así que no necesita otro cambio.
- `entradaPartyLabel` («Varios (N)») **no cambia**: cuenta proveedores del reparto, no plata, y una Entrada desliquidada conserva su reparto (#93 D20).

## 3. Lo que NO cambia

- **Backend:** cero archivos. Ni schemas, ni endpoints, ni servicios: el número de O1 se calcula en el frontend (§1). **Nivel lógica** (dos cálculos de plata más el criterio de O1). **Golden: no aplica**, porque no hay cambio en `app/`. Lo mido igual con `git diff --stat <base> <sha> -- backend` vacío.
- «Total Liquidado» y el «Total $» del listado **solo cambian en un estado**: Entrada con compras `registered` (desliquidada, o legacy sin liquidar). En una Entrada liquidada dan el mismo número que hoy; ese es el control de E10.
- La liquidación, el PDF de la compra, el detalle de la compra y el export a Excel del listado no se tocan.
- Orgs sin `kg_ledger_enabled`: no ven la página (guard de ruta, `App.tsx:174`). Este cambio no lo toca.
- Tipo Willard y legacy 1:1: la sección «Compras» sigue apareciendo solo con `isPurchaseType && purchases.length > 0`, igual que hoy.

## 4. Verificación

**Gates de autor:**
- lint, `tsc` y `build`;
- las guardas del árbol: `test_reloj_de_negocio.py` (escanea `frontend/src`), `test_advisory_locks.py` y `test_crucible_charges.py`;
- **dirigidas por grep**: no hay superficie de backend, así que el set son las tres guardas. El comando y su salida vacía quedan en el log.

**Instrumento:** un e2e con Playwright, `e2e_compras_tabla.mjs check`, contra :5181/:8011, que lee la pantalla **y** el `GET /inbound-orders/{id}` del mismo instante. Cada E compara números de la pantalla contra números calculados aparte desde la API, nunca contra constantes.

**Datos (`setup`, en mi BD `reciclaje_coder_1`, org SAC, idempotente):**
- **Entrada A** (tipo compra), 3 materiales, liquidada con 4 compras:
  - dos del **mismo** proveedor (Q-65);
  - una solo con IVA, una solo con retención y **una con IVA y retención a la vez** (C1 de QA: E8, P3 y P9 se miden sobre esta, que es la única en la que olvidar restar la retención cambia un total que también lleva IVA);
  - después **desliquidada y reliquidada intercambiando dos proveedores entre compras** (R6), para que queden 2 compras canceladas que comparten slot con vigentes.
- **Entrada B**, liquidada con IVA y después desliquidada: queda Revisada, con sus compras `registered`.
- **Entrada C**, liquidada sin IVA.
- **Un usuario con un rol** que tiene `purchases.view` y no `purchases.view_prices`. Es el control positivo de E4: el admin bypassa el permiso, así que con él no se prueba nada (#111).

| E | Qué mide | Cómo |
|---|---|---|
| E1 | Por fila vigente: Subtotal, IVA, Retenciones y Total al proveedor = los de la API | IVA = Σ iva sin `reverted_at`; total = sub + iva − ret, calculado en el script |
| E2 | Fila de totales = Σ de las liquidadas, y dice «(N compras liquidadas)» con el N de la API | Entrada A: las 2 canceladas presentes, en gris, «no suma» |
| E3 | «Total con IVA» = Σ (sub + iva) de las liquidadas; oculto si el IVA es 0 | A muestra; C no; B (desliquidada) no |
| E4 | Sin `view_prices`: no hay columnas 5–8, ni fila de totales, ni «Total con IVA» | usuario del rol; control positivo: admin en la misma Entrada sí las ve |
| E5 | A 390 px no hay tabla, hay tarjetas y no hay scroll horizontal | `#main-scroll` `scrollWidth <= clientWidth`; a 1440 lo inverso |
| E6 | Materiales de cada fila = las asignaciones de su slot; cancelada → «—» | Entrada A, cruzado contra `lines[].allocations` |
| E7 | Desliquidada (O1): filas «Registrada» con su subtotal, IVA 0 y «no suma»; **sin** «Total Liquidado» ni «Total con IVA»; la fila de totales dice «Sin compras liquidadas» | Entrada B |
| E8 | La tarjeta móvil (390) dice el mismo «Total al proveedor» que la fila de la tabla (1440), y los dos = sub + iva − ret de la API | Entrada A, **la compra con IVA y retención** (C1), buscada por número desde el setup, no «la primera con IVA» |
| E10 | Listado (1440), columna «Total $» (O1, D7): **control**, para A y C = Σ `total_amount` de sus compras liquidadas según la API, que coincide con el «Total Liquidado» de su detalle; para B = la referencia capturada (Σ cantidad × `unit_price` de sus líneas), no Σ de sus compras | las tres filas del listado, buscadas por número de Entrada |
| E11 | Listado a 390 px: la tarjeta de A, B y C dice el mismo «Total $» que E10 | mismas Entradas |
| E9 | *(solo si Coder 2 integró antes, ver D6)* Con alcance, una compra fuera del alcance sale sin link en la tabla | usuario con alcance de Coder 2 |

**Matriz del plantado** (se commitea antes de plantar; cada fila se restaura por ruta y se verifica por sha):

| P | Defecto | Caen |
|---|---|---|
| P1 | las canceladas suman en la fila de totales | E2 |
| P2 | el IVA cuenta también las filas con `reverted_at` | **E7 siempre**; E1 solo si la medición de C2 lo dice (ver abajo) |
| P3 | `total = sub + iva` (se olvida restar las retenciones) | E1, E8 (al menos) |
| P4 | las columnas de plata sin el gate `canViewPrices` | E4 |
| P5 | los materiales sin filtrar por slot (todos los del reparto) | E6 |
| P6 | la cancelada pinta los materiales de su slot | E6 |
| P7 | «Total con IVA» sin la condición IVA > 0 | E3 |
| P8 | la tabla sin `hidden md:block` | E5 |
| P9 | la tarjeta vuelve a su cálculo propio, sin restar las retenciones (deja de usar `purchaseMoney`) | E8 |
| P10 | `countsAsLiquidated` vuelve a `status !== "cancelled"` (el criterio viejo) | E7, E10, E11 (al menos: vía compartida) |
| P11 | el listado deja de usar `countsAsLiquidated` y vuelve a su filtro propio `!== "cancelled"` | E10, E11 |
| P12 | el `InfoRow` «Total Liquidado» vuelve a la condición `purchases.length > 0` (aparece «$0» en la desliquidada) | E7 |

El control de O1 es la mitad «liquidada» de E10 y E2/E3 sobre A y C: una Entrada liquidada **sí** suma. Sin ese contraste, «el criterio funciona» y «no suma nada nunca» se ven iguales (#94/#99). Por eso P10 tiene que dejar E2 en verde: con el criterio viejo, A y C suman lo mismo.

En las filas sobre vías compartidas (`purchaseMoney` la usan la tabla, la tarjeta y el pie), la predicción se escribe «al menos estos» (#105).

**C2 de QA: la predicción de P2 depende de lo que traiga la API.**
- E7 cae siempre: la Entrada B desliquidada tiene todo su IVA revertido, así que con P2 el IVA deja de ser 0.
- E1 cae solo si alguna compra **vigente** trae filas de IVA revertidas. Por ejemplo, una compra reusada al reliquidar: la fila vieja queda revertida y la nueva viva. El criterio del lote que devuelve `taxes` lo decide el servidor: hoy «vivas, o si no el último lote revertido», y con Coder 2, `last_liquidation_batch`. Así que esas filas pueden no llegar, y entonces P2 no tumba E1 por motivos del servidor, no del código.
- Por eso, antes de escribir la predicción de P2, el `setup` imprime por compra vigente de las Entradas A, B y C cuántas filas de IVA vivas y cuántas revertidas trae el `GET /inbound-orders/{id}`. Esa medición queda en `setup.log`.
- La predicción de P2 se escribe en el informe (addendum, commiteado antes de plantar) a partir de esa medición: «E1» solo si hay al menos una compra vigente con IVA revertido.

**Capturas a 1440 y 390** de las Entradas A, B y C. Costa no lleva captura: la ruta está detrás de `FP flag="kg_ledger_enabled"` (`App.tsx:174`), así que una org sin flag no llega a la página, y este cambio no toca ese guard.

## 5. Supuestos y decisiones abiertas

Decididas por Daniel el 20-nov, vía el Coordinador:
- **O1:** «Que dejen de sumar». **Fue contra mi recomendación** (yo proponía no tocar el número). Queda en D4 y D7, con su criterio y sus pruebas. Que el `InfoRow` desaparezca en vez de decir «$0» es decisión mía, dentro de O1 (D4), y se puede cambiar en una línea.
- **O2:** el neto (− retenciones) solo en la fila de totales. Recomendada y aceptada.
- **O3:** «Total con IVA» oculto si el IVA es 0. Recomendada y aceptada.
- La columna Materiales es algo que la tarjeta no tenía. La pidió el Coordinador y sale del reparto sin consultas nuevas.
