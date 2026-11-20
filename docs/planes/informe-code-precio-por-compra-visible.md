# Informe — Liquidar Entrada: el precio de cada compra a la vista

Autor: Eco Coder 1 · 20-nov-2026 · rama `coder-1/precio-por-compra` (base `de32530`)
Plan: `plan-sac-precio-por-compra-visible.md` v1.1 + C4 + E14 + §4b (GO de Eco QA 1; autorización
de Daniel vía el Coordinador). Nivel **lógica**, solo frontend. Código en `15e6278`.

## Qué cambió (`InboundLiquidatePage.tsx`)

- **Celda** = `[Cantidad] [Precio]` siempre visibles; se borró el editor desplegable. El precio llega
  prellenado con la lista del proveedor (#98) o el precio base; escribir otro lo vuelve propio.
  Debajo (con cantidad > 0): `c/u · total · kg` y el origen (`lista` / `base` / `propio ↺`), los
  cuatro botones con `tabIndex={-1}`; y la cuenta de la celda (`= $X`, `→ $X c/u`, `kg × $ = $`).
- **Un blur que no cambia la cifra no escribe nada** (C1): `toCents(v) === priceFieldValue(...)`
  antes de cualquier `setCell`, en todos los modos y en la celda vacía.
- **c/u en lista/base/propio = no-op** (C3); de total/kg a c/u vuelve prellenado con «antes: …».
- **«Precio base»** con su hint (S-1); el origen se lee en la tarjeta de 390 (S-2).
- **Barra** = `activeCols.length` como el pie, más las columnas vacías aparte (D4).
- **`selectOnFocus`** (hallado al construir, E14): `MoneyInput` reemplaza el texto al recibir el foco
  y borra la selección del Tab, así que escribir sobre un prellenado PEGABA («13.001.250»). Celda y
  precio base seleccionan todo después del render. `MoneyInput` no se toca.

Sin cambios: payload, `CellState` (borrador y firma), `cellMode`/`cellUnit`/`cellTotal`,
`handleSubmit`, backend.

## Pendientes y decisiones para Daniel

1. **El pegado de cifras existe en TODO `MoneyInput` de la app** (Costa y Meta incluidas) al entrar
   con Tab a un campo con valor y escribir. Arreglarlo en el componente es lo correcto y toca código
   compartido: nivel lógica, ciclo propio.
2. **Heredado y conservado**: en una fila con base virgen, el primer precio escrito en una celda pasa
   a ser el base y esa celda queda «propio ↺»; un cambio posterior de la base no la mueve.
3. Con C1, un unitario propio de 8 decimales (1234.56789) no se puede cambiar a su propio redondeo
   (1234.57): son la misma cifra a centavos. Inofensivo.
4. **O1 de QA (conocido, se deja)**: en una celda vacía, escribir exactamente el sugerido la vuelve
   «propio» con esa cifra; si después cambia la lista o la base, no la sigue (↺ la devuelve).

## Gates (evidencia en `~/sac-evidencia/2026-11-20/coder-1-precio-por-compra/`)

- lint 37/0, `tsc` 0, `build` 0, las tres guardas 52 passed (`guardas.log`, sobre 15e6278).
- E2E con teclado real, sin `fill()`, que aborta el PATCH: 22/22 (`e2e_limpio_r2.log`).
- Plantado contra la matriz commiteada en `dfc6556` (no se reescribió), con predicciones escritas antes,
  copia por ruta y cierre por sha256 (`eae50ea4…` y `git status` vacío en cada fila):
  - **Ronda 1** (`plantado.log`): P9b no tumbó nada, P2 y P3 murieron sin resumen.
    - Causa en el instrumento, no en el código. E14 medía sobre cifras sin separador de miles (700 y 10), donde el reformateo de `MoneyInput` no borra la selección: `sonda_p9b.log` muestra el defecto vivo sobre 4.000.
    - `submit()` moría con el botón deshabilitado.
    - El driver descartaba la salida.
    - Delta del instrumento en el plan §4b (`48cb039`).
  - **Ronda 2** (`plantado_r2.log`, salida completa por fila): **las 11 filas tumban lo predicho**, y lo que cae de más va en la dirección barata (P3 → E5, porque su segundo submit queda deshabilitado).
- Golden: no aplica (solo frontend de una ruta SAC).

## Borrador de la decisión (la numera el Coordinador)

**Liquidar Entrada: el precio de cada compra a la vista (pedido de Johana, 20-nov)**: la celda de la
matriz (#122) muestra cantidad y precio lado a lado, prellenado con la lista del proveedor (#98) o el
«precio base» de la fila; escribirlo lo vuelve propio (unitario, total o por kg sin abrir nada). Un
blur que no cambia la cifra no escribe nada (a centavos, en todos los modos): un unitario precargado
de 8 decimales (#120) no se redondea con un Tab. `MoneyInput` reemplaza el texto al recibir el foco y
borra la selección del Tab — escribir sobre un prellenado pegaba la cifra («13.001.250»); la celda y
el precio base seleccionan después del render (el componente compartido sigue con el defecto). La
barra cuenta las compras como el pie. Solo frontend; payload y borrador sin cambios.
