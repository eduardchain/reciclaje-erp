# Plan — Liquidar Entrada: el precio de cada compra a la vista (v1.0)

Autor: Eco Coder 1 · 20-nov-2026 · rama `coder-1/precio-por-compra` (base `de32530`)
Nivel: **lógica** (cálculo en pantalla). Solo frontend; el backend no cambia.
Archivo: `frontend/src/pages/inbound/InboundLiquidatePage.tsx` (matriz de #122/#123).

## 1. Qué pasa hoy

- Cada asignación ya lleva su precio (#93) y la pantalla ya acepta precio propio por celda
  (unitario / valor total / por kg) y ya toma el de la lista del proveedor (#98). Pero el precio
  vive detrás de un clic en el texto «$X c/u» debajo de la cantidad: en la reunión del 20-nov ni
  Daniel lo encontró.
- Johana, según el Coordinador (no leí la transcripción): «no para todos no. Todos manejan
  diferentes precios»; «hay como dos listas estándar… y otras particulares».
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

### D2 — Qué muestra el campo y qué hace escribir en él
Sin tocar `cellMode`/`cellUnit`/`cellTotal`/`handleSubmit` (el payload sale igual que hoy):

| Modo de la celda | El campo muestra | Escribir un valor distinto | Dejarlo en 0 |
|---|---|---|---|
| fila (sin lista) | precio de la fila, a centavos | → precio propio unitario | vuelve a la fila (no-op) |
| lista | precio de la lista del proveedor, a centavos | → precio propio unitario | vuelve a la lista (no-op) |
| propio unitario | el unitario digitado | lo reemplaza | quita el propio → lista/fila |
| valor total | el total digitado | lo reemplaza | 0 = «falta precio» (como hoy) |
| por kg | el $/kg digitado | lo reemplaza | 0 = «falta precio» (como hoy) |

- Lo prellenado se compara **a centavos** (`toCents`) contra lo que devuelve el blur de
  `MoneyInput` (2 decimales, llama `onChange` en CADA blur): pasar con Tab por un precio de lista
  con más decimales no lo vuelve propio (familia C1/C5 de #120/#122).
- Escribir un precio limpia el «antes: …» de la celda.
- Una fila virgen sigue tomando el primer precio propio digitado (`setCell`, sin cambios).

### D3 — El modo, en una línea debajo (solo con cantidad > 0)
`c/u · total · kg` como tres botones chicos (kg solo si `canKg`), con `tabIndex={-1}` para que el
Tab no pase por ellos (cuesta: cambiar de modo es solo con el mouse o el dedo). A la derecha, de
dónde sale el precio: «lista» / «fila» / «propio ↺» (el ↺ vuelve a lista/fila, patrón #10).
- A **total** o **kg**: como hoy (`switchMode`): el campo arranca vacío y el precio anterior
  queda como «antes: …». No se convierte ninguna cifra.
- De total/kg a **c/u**: se quita el precio propio y el campo vuelve **prellenado** con
  lista/fila, con el total anterior en «antes: …». Cambia respecto de hoy (hoy deja el unitario
  vacío): el criterio pide que el unitario llegue prellenado.
- Debajo, la cuenta de la celda: total → «→ $X c/u»; kg → «60 kg × $1.000 = $60.000»;
  unitario/lista/fila → «= $subtotal». Se conservan el «antes: …» y el aviso ámbar «La compra
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
- Costa y Meta: la ruta está detrás del flag SAC; nada compartido se toca.

## 4. Verificación (no hay infra de test de frontend)
- Autor: `npm run lint` (techo 37), `tsc`, `build`, las tres guardas del árbol.
- **E2E con Playwright propio** (scratchpad, navegador sin perfil) contra :8011/:5181 y mi BD,
  sobre la Entrada #33 o #31 de SAC. Intercepta el PATCH de liquidar, **lee el payload y lo
  aborta** (no liquida). Casos (cada uno con lo esperado escrito antes):

| # | Acción | Esperado en el payload / pantalla |
|---|---|---|
| E1 | compra sin lista, cantidad, Tab | foco en el precio; `unit_price` = fila |
| E2 | compra con proveedor de la lista | campo prellenado con la lista; `unit_price` = lista |
| E3 | escribir otro precio en una celda | `unit_price` propio solo en esa celda; las demás igual |
| E4 | Tab por un precio prellenado sin tocarlo, cambiar la fila | la celda sigue a la fila (no se volvió propia) |
| E5 | dejar en 0 un propio | vuelve a lista/fila |
| E6 | modo total, digitar | `total_price` digitado, sin `unit_price` |
| E7 | modo kg, digitar | `price_per_kg` digitado |
| E8 | de total a c/u | campo prellenado, «antes: $X total» |
| E9 | recargar | el borrador devuelve el precio propio |
| E10 | 3 columnas, una vacía | barra y pie dicen «2 compras» |

- **Plantado** sobre la pantalla (matriz commiteada antes): P1 comparar sin `toCents` (E4 debe
  caer), P2 el 0 de un propio no limpia (E5), P3 total→c/u sin prellenar (E8), P4 la barra con
  `sortedCols` (E10), P5 sin `tabIndex={-1}` en los modos (E1: el foco cae en «c/u»).
- Capturas a 1440 y 390 con 3 compras y precios distintos (lista, fila, propio), al Coordinador
  antes de la revisión completa de QA.
- Golden: **no aplica** (solo frontend de una ruta SAC; el golden compara respuestas HTTP).

## 5. Supuestos
- S1: «el precio unitario de esa compra se ve y se edita directamente» se cumple con el campo de
  la celda; total y kg siguen a un clic (en la misma celda, sin abrir nada).
- S2: el 0 en un unitario propio significa «volver al sugerido» y no «sin precio».
