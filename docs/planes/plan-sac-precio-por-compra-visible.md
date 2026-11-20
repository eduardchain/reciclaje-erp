# Plan — Liquidar Entrada: el precio de cada compra a la vista (v1.1)

Autor: Eco Coder 1 · 20-nov-2026 · rama `coder-1/precio-por-compra` (base `de32530`)
Nivel: **lógica** (cálculo en pantalla). Solo frontend; el backend no cambia.
Archivo: `frontend/src/pages/inbound/InboundLiquidatePage.tsx` (matriz de #122/#123).
Historia (v1.1 + C4 + E14): v1.0 `4070017` → GO de Eco QA 1 con C1–C3; revisión de producto del Coordinador
(sugerencias S-1 y S-2, nota E2); Daniel autorizó construir la v1.1. v1.1 `02743e2` → C4 de QA
(P1 medía nada: E13 nuevo), antes de plantar.

## 1. Qué pasa hoy

- Cada asignación ya lleva su precio (#93) y la pantalla ya acepta precio propio por celda
  (unitario / valor total / por kg) y ya toma el de la lista del proveedor (#98). Pero el precio
  vive detrás de un clic en el texto «$X c/u» debajo de la cantidad: en la reunión del 20-nov ni
  Daniel lo encontró.
- Johana, reunión del 20-nov, citas que me pasó el Coordinador (grado (a) según él; no las verifiqué
  contra la transcripción): «no para todos no. Todos manejan diferentes precios»; «hay como dos
  listas estándar… y otras particulares».
- La barra sobre la tabla dice «N compras» con `sortedCols.length` (cuenta columnas vacías) y el
  pie usa `activeCols.length` (solo las que tienen cantidades): «3 compras» arriba, «2» abajo.

## 2. Qué cambia

### D1 — La celda: cantidad y precio lado a lado, siempre visibles
`[ Cantidad ] [ Precio ]` en una fila de dos campos (encabezado de cada compra con los rótulos
«Cantidad · Precio»; en 390 px, igual dentro de la tarjeta de la compra). Se borra el editor
desplegable (`editing`, `closeEditor`, el botón «$X c/u»).
- El campo de precio **existe también con cantidad 0**, para que el Tab vaya cantidad → precio →
  siguiente celda sin depender de que React pinte un campo nuevo a mitad del Tab. Con cantidad 0
  y sin precio propio, el sugerido va como *placeholder* gris (no como valor): una celda vacía no
  aparenta tener precio.
- Columna de compra de `min-w-[13rem]` a `min-w-[15rem]`: un total de 7 cifras tiene que caber.

### D1b — La columna de la fila pasa a «Precio base» (S-1 del Coordinador)
Con precio por celda, el de la fila deja de ser «el precio» y queda de respaldo. Rótulo
«Precio base» (escritorio y tarjeta de 390 px) con el hint «se usa en las compras sin lista ni
precio propio». El origen de una celda que lo usa se rotula «base» (no «fila»). Sigue siendo la
referencia del descuadre (D6 de #93): no cambia nada de su cálculo.

### D2 — Qué muestra el campo y qué hace escribir en él
Sin tocar `cellMode`/`cellUnit`/`cellTotal`/`handleSubmit` (el payload sale igual que hoy):

| Modo de la celda | El campo muestra | Escribir un valor distinto | Dejarlo en 0 |
|---|---|---|---|
| vacía (cantidad 0, sin propio) | 0 (sugerido como placeholder) | → precio propio unitario | no-op |
| base (sin lista) | precio base, a centavos | → precio propio unitario | no-op (sigue en base) |
| lista | precio de la lista del proveedor, a centavos | → precio propio unitario | no-op (sigue en lista) |
| propio unitario | el unitario digitado, a centavos | lo reemplaza | quita el propio → lista/base |
| valor total | el total digitado | lo reemplaza | 0 = «falta precio» (como hoy) |
| por kg | el $/kg digitado | lo reemplaza | 0 = «falta precio» (como hoy) |

- 🔴 **C1 de QA — un blur que no cambia la cifra no escribe nada, en ningún modo.** `MoneyInput`
  llama `onChange` en CADA blur con el valor redondeado a 2 decimales. Regla única, antes de
  cualquier `setCell`: si `toCents(v) === toCents(valor que el campo muestra)` → `return`. Vale
  para las 6 filas de la tabla. Cubre: un unitario propio precargado con más de 2 decimales
  (`unit_price` es Numeric(21,8) desde #120, precarga l.390) no se reescribe redondeado con un
  Tab; un Tab por una celda en total no borra su «antes»; una celda vacía no se crea en 0 (el
  borrador fantasma de C5 de #122). La cifra que se guarda cuando SÍ cambia es `v` tal cual
  (2 decimales, lo que el usuario ve).
- Escribir un precio (cuando sí cambia) limpia el «antes: …» de la celda.
- **Hallado al construir (E14)**: `MoneyInput` reemplaza el texto al recibir el foco («1.300» →
  «1300») y eso borra la selección que deja el Tab: lo que se escribe se **pega** al final (1250
  sobre 1.300 daba «13.001.250»). Con el precio prellenado ese es el flujo normal, así que la celda
  (cantidad y precio) y el precio base seleccionan todo después de ese render (`selectOnFocus`).
  `MoneyInput` es compartido con Costa y Meta y **no se toca**: el mismo pegado existe hoy en todo
  `MoneyInput` de la app al entrar con Tab a un campo con valor (preexistente; lo decide Daniel).
  Un clic dentro de un campo que YA tiene el foco no selecciona (comportamiento del navegador).

### D3 — El modo y el origen, en una línea debajo (solo con cantidad > 0)
`c/u · total · kg` como tres botones chicos (kg solo si `canKg`) y, a la derecha, de dónde sale
el precio: «lista» / «base» / «propio ↺» (el ↺ vuelve a lista/base, patrón #10).
- **C2 de QA**: los tres modos **y** el ↺ llevan `tabIndex={-1}`: la línea aparece en medio del
  recorrido con Tab (entre el precio y la celda siguiente). Cuesta: cambiar de modo o volver al
  sugerido es solo con mouse o dedo.
- **S-2 del Coordinador**: la línea es la misma función de render en escritorio y en la tarjeta
  de 390 px, así que el origen se lee sin abrir nada en los dos.
- **C3 de QA — qué botón se ve activo y qué hace**: en lista, base y propio unitario se ve
  activo **c/u** (el campo muestra un unitario). Un clic en c/u en esos tres estados es **no-op**:
  no toca la celda ni pone «antes». (Hoy `switchMode` con `ownMode` null pondría
  `unit_price: 0`; se corta antes.)
- A **total** o **kg** (desde cualquier estado): como hoy (`switchMode`): el campo arranca vacío y
  el precio anterior queda como «antes: …». No se convierte ninguna cifra.
- De total/kg a **c/u**: se quita el precio propio y el campo vuelve **prellenado** con
  lista/base, con el total anterior en «antes: …». Cambia respecto de hoy (hoy deja el unitario
  vacío): el criterio pide que el unitario llegue prellenado.
- Debajo, la cuenta de la celda: total → «→ $X c/u»; kg → «60 kg × $1.000 = $60.000»;
  unitario/lista/base → «= $subtotal». Se conservan el «antes: …» y el aviso ámbar «La compra
  suma $X» del modo total.

### D4 — La barra no contradice al pie
La barra cuenta lo mismo que el pie: `activeCols.length` compras, y aparte las columnas vacías:
«2 compras · 1 columna sin materiales (no nace compra)»; sin ninguna con materiales:
«N columnas, ninguna con materiales todavía».

## 3. Lo que NO cambia
- Payload, schemas y backend. El borrador: `CellState` conserva su forma (`before` incluido),
  así que `assertDraftShape`, la firma y los borradores ya guardados siguen valiendo.
- `applySingleSupplier`, `removeCol`, `removeLine` y «Descartar borrador» solo pierden su
  `setEditing(null)`.
- **Comportamiento heredado, se conserva a propósito** (nota de QA): en una fila con base virgen
  (0, sin tocar), el primer precio que se escribe en una celda pasa a ser el precio base
  (`setCell` l.730, «reutilizar el primer precio digitado», pedido de Daniel), y esa celda queda
  «propio ↺» aunque valga lo mismo que la base: si después se cambia la base, esa celda NO la
  sigue. Se escribió el precio en esa compra, así que es de esa compra; un clic en ↺ la devuelve
  a la base. Con la celda visible esto se va a notar más: lo mira Daniel en la pantalla.
- Costa y Meta: la ruta está detrás del flag SAC; nada compartido se toca.

## 4. Verificación (no hay infra de test de frontend)

- Autor: `npm run lint` (techo 37), `tsc`, `build`, las tres guardas del árbol con
  `lockf -k ~/.cache/ecobalance/tests.lock` y mi `TEST_DATABASE_URL`. Sin suite completa ni
  dirigidas de backend (no se toca backend).
- **Datos** (solo mi BD `reciclaje_coder_1`, por la API de :8011): una Entrada revisada de SAC
  con 3+ materiales; una **segunda** lista por proveedor (#98) con precios distintos a la que ya
  existe, y un proveedor en cada una + uno sin lista (nota E2 del Coordinador: «dos listas
  estándar»).
- **E2E con Playwright propio** (scratchpad, navegador sin perfil) contra :8011/:5181. Intercepta
  el PATCH de liquidar, **lee el payload y lo aborta** (no liquida). Lo esperado se escribe en el
  log antes de cada corrida:

| # | Acción | Esperado en el payload / pantalla |
|---|---|---|
| E1 | compra sin lista: cantidad, Tab, (precio), Tab | 1.er Tab: foco en el precio; 2.º Tab: foco en la cantidad de la celda siguiente (no en c/u ni ↺); `unit_price` = base |
| E2 | compras A y B con proveedores en listas DISTINTAS, mismo material | A prellenada con la lista de A, B con la de B; payload: cada una la suya |
| E3 | escribir otro precio en una celda | `unit_price` propio solo en esa celda; las demás igual |
| E4 | Tab por un precio prellenado sin tocarlo, después cambiar la base | la celda sigue a la base (no se volvió propia) |
| E5 | dejar en 0 un propio | vuelve a lista/base |
| E6 | modo total, digitar | `total_price` digitado, sin `unit_price` |
| E7 | modo kg, digitar | `price_per_kg` digitado |
| E8 | de total a c/u | campo prellenado, «antes: $X total» |
| E9 | recargar | el borrador devuelve el precio propio |
| E10 | 3 columnas, una vacía | barra y pie dicen «2 compras» |
| E11 | Tab de punta a punta por una fila de celdas vacías y por una celda en total con «antes» | el borrador de `localStorage` queda **igual byte a byte** antes y después; el «antes» sigue visible |
| E12 | clic en c/u con la celda en lista, en base y en propio | ningún cambio: borrador igual byte a byte, sin «antes» |
| E14 | (hallado al construir) escribir SOBRE un prellenado: con Tab, con clic, sobre una cantidad con valor y sobre el precio base entrando con Tab | reemplaza: 4100, 4200, 12 y 705 — no «13.001.250» |
| E13 | (C4 de QA) Entrada liquidada por API con `unit_price` 1234.56789, desliquidada; abrir Liquidar, Tab por esa celda sin tocarla | el log imprime el precargado antes; payload `unit_price` = 1234.56789 (no 1234.57) y borrador igual byte a byte |

- **Plantado** (esta matriz va commiteada con la v1.1, antes de plantar). Cada defecto se planta
  sobre una copia por ruta, se corre el E2E entero y se restaura con cierre por sha256:

| P | Defecto plantado | Debe caer | Puede caer de más (vía compartida) |
|---|---|---|---|
| P1 | comparar sin `toCents` (exacto) | E13 | — (E4 **no** cae: los prellenados de lista y base son de 2 decimales — `price_lists.purchase_price` y `reference_unit_price` son Numeric(15,2); el único valor de más decimales es el unitario propio precargado desde `inbound_line_allocations.unit_price` Numeric(21,8)) |
| P2 | el 0 en un unitario propio no limpia | E5 | — |
| P3 | de total a c/u sin prellenar (`unit_price: 0`) | E8 | — |
| P4 | la barra con `sortedCols.length` | E10 | — |
| P5a | sin `tabIndex={-1}` en los modos | E1 | — |
| P5b | sin `tabIndex={-1}` en el ↺ | E1 (con la celda en propio) | — |
| P6 | sin el guard de C1 en la celda vacía | E11 | E1 |
| P7 | clic en c/u en lista/base cae en `switchMode` | E12 | E3 |
| P8 | `listPrices` leídos de la primera columna para todas | E2 | — |
| P9 | sin `selectOnFocus` en la celda | E14 | casi todo (el E2E escribe como una persona: vía compartida) |
| P9b | sin `selectOnFocus` en el precio base | E14 | E3, E4 |

- Capturas a 1440 y 390 con 3 compras y precios distintos (lista A, lista B, base, propio), al
  Coordinador antes de la revisión completa de QA.
- Golden: **no aplica** (solo frontend de una ruta SAC; el golden compara respuestas HTTP).

## 5. Supuestos
- S1: «el precio unitario de esa compra se ve y se edita directamente» se cumple con el campo de
  la celda; total y kg siguen a un clic (en la misma celda, sin abrir nada).
- S2: el 0 en un unitario propio significa «volver al sugerido» y no «sin precio».
