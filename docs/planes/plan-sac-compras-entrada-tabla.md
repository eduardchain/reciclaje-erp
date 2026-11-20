# Plan: Detalle de Entrada, las compras en tabla y el total con IVA (v1.0)

Autor: Eco Coder 1 · 20-nov-2026 · rama `coder-1/compras-entrada-tabla` (base develop `1aacc2f`)
Base: escrito sobre `31ba117` y rebasado a `1aacc2f`. El delta `31ba117..1aacc2f` (MoneyInput y Ocultar Listas) no toca `frontend/src/pages/inbound`, `types/inbound.ts` ni `backend`, y `InboundDetailPage` no usa `MoneyInput`. Artefacto: `delta_develop_superficie.log`.
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
- **«Total Liquidado»** (`InfoRow`, `InboundDetailPage.tsx:390`) es `Σ total_amount` de las compras con `status !== "cancelled"`, sin IVA. Se muestra con `purchases.view_prices`.

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

- **Fila de totales** al pie, con permiso: suma las columnas 5 a 8 sobre las compras que cuentan (D4) y dice cuántas son: «Total (N compras)».
- **Orden.** Primero las vigentes por slot y número, como hoy. Después las canceladas, en gris con el texto «no suma». La fila de totales queda al final.
- Los números van con `tabular-nums`, alineados a la derecha. Si hay pocas filas, la tabla se queda sin scroll interno. Para pantallas de 768 a 1024 px va dentro de `overflow-x-auto` con un `min-w` (patrón B de CLAUDE.md), para que 9 columnas no se aprieten.

### D2. Un solo cálculo por compra, usado por la tabla, las tarjetas y los totales

Es una función pura de módulo, `purchaseMoney(p)`, que devuelve `{ subtotal, iva, ret, total }`:
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

- **Suman** las compras con `status !== "cancelled"`. Es **el mismo conjunto que usa hoy «Total Liquidado»**, a propósito: el número que ya existe no cambia (ver O1).
- **Nuevo `InfoRow` «Total con IVA»** justo debajo de «Total Liquidado», con `view_prices`: Σ (`subtotal + iva`) sobre el mismo conjunto. Para la Entrada #12 serían $236.480.
  - Se muestra **solo si el IVA sumado es > 0**. Si no lo es, repetiría el mismo número.
- **El total neto al proveedor** (− retenciones) no va en el encabezado: vive en la fila de totales de la tabla. El pedido es «total con IVA», y un tercer total arriba compite con los otros dos.
- **Compra desliquidada** (la Entrada vuelve a Revisada y las compras quedan `registered`, con su IVA y sus retenciones revertidos):
  - la fila muestra el subtotal, IVA 0, retenciones 0 y el estado «Registrada»;
  - suma igual que hoy en «Total Liquidado»;
  - «Total con IVA» queda oculto porque su IVA es 0.
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

## 3. Lo que NO cambia

- **Backend:** cero archivos. Ni schemas, ni endpoints, ni servicios. **Golden: no aplica**, porque no hay cambio en `app/`. Lo mido igual con `git diff --stat 31ba117 <sha> -- backend` vacío.
- «Total Liquidado» da el mismo número en todos los estados (D4).
- El listado de Entradas, la liquidación, el PDF de la compra y el detalle de la compra no se tocan.
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
  - una con IVA y otra con retención;
  - después **desliquidada y reliquidada intercambiando dos proveedores entre compras** (R6), para que queden 2 compras canceladas que comparten slot con vigentes.
- **Entrada B**, liquidada con IVA y después desliquidada: queda Revisada, con sus compras `registered`.
- **Entrada C**, liquidada sin IVA.
- **Un usuario con un rol** que tiene `purchases.view` y no `purchases.view_prices`. Es el control positivo de E4: el admin bypassa el permiso, así que con él no se prueba nada (#111).

| E | Qué mide | Cómo |
|---|---|---|
| E1 | Por fila vigente: Subtotal, IVA, Retenciones y Total al proveedor = los de la API | IVA = Σ iva sin `reverted_at`; total = sub + iva − ret, calculado en el script |
| E2 | Fila de totales = Σ de las vigentes, y dice «(N compras)» con el N de vigentes | Entrada A: las 2 canceladas presentes, en gris, «no suma» |
| E3 | «Total con IVA» = Σ (sub + iva) de las vigentes; oculto si el IVA es 0 | A muestra; C no; B (desliquidada) no |
| E4 | Sin `view_prices`: no hay columnas 5–8, ni fila de totales, ni «Total con IVA» | usuario del rol; control positivo: admin en la misma Entrada sí las ve |
| E5 | A 390 px no hay tabla, hay tarjetas y no hay scroll horizontal | `#main-scroll` `scrollWidth <= clientWidth`; a 1440 lo inverso |
| E6 | Materiales de cada fila = las asignaciones de su slot; cancelada → «—» | Entrada A, cruzado contra `lines[].allocations` |
| E7 | Desliquidada: filas «Registrada», IVA 0, totales = Σ subtotales = «Total Liquidado» | Entrada B |
| E8 | La tarjeta móvil (390) dice el mismo «Total al proveedor» que la fila de la tabla (1440) | Entrada A, compra con IVA y retención |
| E9 | *(solo si Coder 2 integró antes, ver D6)* Con alcance, una compra fuera del alcance sale sin link en la tabla | usuario con alcance de Coder 2 |

**Matriz del plantado** (se commitea antes de plantar; cada fila se restaura por ruta y se verifica por sha):

| P | Defecto | Caen |
|---|---|---|
| P1 | las canceladas suman en la fila de totales | E2 |
| P2 | el IVA cuenta también las filas con `reverted_at` | E1, E7 (al menos) |
| P3 | `total = sub + iva` (se olvida restar las retenciones) | E1, E8 (al menos) |
| P4 | las columnas de plata sin el gate `canViewPrices` | E4 |
| P5 | los materiales sin filtrar por slot (todos los del reparto) | E6 |
| P6 | la cancelada pinta los materiales de su slot | E6 |
| P7 | «Total con IVA» sin la condición IVA > 0 | E3 |
| P8 | la tabla sin `hidden md:block` | E5 |
| P9 | la tarjeta vuelve a su cálculo propio, sin restar las retenciones (deja de usar `purchaseMoney`) | E8 |

En las filas sobre vías compartidas (`purchaseMoney` la usan la tabla, la tarjeta y el pie), la predicción se escribe «al menos estos» (#105).

**Capturas a 1440 y 390** de las Entradas A, B y C. Costa no lleva captura: la ruta está detrás de `FP flag="kg_ledger_enabled"` (`App.tsx:174`), así que una org sin flag no llega a la página, y este cambio no toca ese guard.

## 5. Supuestos y decisiones abiertas

- **O1 (Daniel, observación, fuera de alcance):** hoy, después de desliquidar, «Total Liquidado» sigue sumando las compras `registered` aunque la Entrada esté Revisada. El número se lee como liquidado y no lo está. Este plan **no lo cambia**, para no mover un número que ya existe. Si Daniel prefiere que en ese estado el número diga «$0» o desaparezca, es un cambio de una línea, con su E.
- **O2:** dejar el neto (− retenciones) solo en la fila de totales, y no como un tercer total en el encabezado (D4), es decisión mía. Si Daniel lo quiere arriba, es un `InfoRow` más con el mismo cálculo.
- **O3:** «Total con IVA» oculto cuando el IVA es 0 (D4) también es decisión mía, para no repetir el mismo número.
- La columna Materiales es algo que la tarjeta no tenía. La pidió el Coordinador y sale del reparto sin consultas nuevas.
