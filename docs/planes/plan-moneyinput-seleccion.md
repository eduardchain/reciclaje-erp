# Plan — MoneyInput: escribir sobre un valor lo reemplaza (v1.1)

Autor: Eco Coder 1 · 20-nov-2026 · rama `coder-1/moneyinput-seleccion` (sale de develop)
Nivel: **lógica**. Es código compartido: lo usan 40 archivos con 74 instancias en las 7 orgs.
Solo frontend, en un archivo: `frontend/src/components/shared/MoneyInput.tsx`.
Autorización: Daniel lo pidió como ciclo propio (vía el Coordinador).
Historia: v1.0 `78ff582` → GO de Eco QA 1 con C1 y C2 sobre la matriz y las notas N1 y N2 → v1.1.

## 1. El defecto

Al recibir el foco, `MoneyInput` cambia el texto formateado («1.300») por el crudo («1300») con `setDisplayValue`. Ese cambio de `value` en un input controlado **mueve el cursor al final y borra la selección** que dejó el Tab. Escribir después **pega** la cifra al final en vez de reemplazarla.

Sonda en Nueva Compra de Costa, sobre la BD de dev de coder-1, con teclado real:

| Acción | Resultado |
|---|---|
| Tab a un precio prellenado (1.300) y escribir 1250 | **13.001.250** (roto) |
| Clic después del «1» y escribir 5 | 15.300 (bien: edita ese dígito) |
| Clic al final y escribir 0 | 13.000 (bien) |

`fill()` de Playwright no ve el defecto, porque escribe en el mismo instante del foco, antes del render.

## 2. Qué cambia

### D1 — Se selecciona todo solo si el foco llega por teclado
- Un `pointerDownRef` se pone en true en `onPointerDown` (mouse, dedo o lápiz).
- `handleFocus` lo lee y lo apaga:
  - si el foco llegó **sin puntero** (Tab, Shift+Tab, `.focus()` de código), marca `selectPendingRef = true`;
  - si llegó **con puntero**, no marca nada: el clic sigue dejando el cursor donde se hizo clic, como hoy.

**Por qué no seleccionar en cualquier foco:** la sonda muestra que hoy el clic en medio de la cifra sirve para corregir un dígito (15.300). Seleccionar todo al hacer clic rompería eso para todos los usuarios de las 7 orgs. El defecto vive solo en la entrada por teclado.

**Consecuencias declaradas:**
- Un `.focus()` programático también selecciona todo (p. ej. un diálogo que enfoca su primer campo). Escribir encima reemplaza, que es lo esperado en un campo prellenado.
- **N1 de QA:** un clic en un `<Label htmlFor>` enfoca el input sin que el input reciba `pointerdown`, así que cuenta como teclado y selecciona todo. Es inocuo, porque escribir reemplaza.

### D2 — La selección se aplica DESPUÉS del reformateo
Un `useLayoutEffect` sobre `[displayValue, focused]` hace esto: si `selectPendingRef` está en true y el input es el `document.activeElement`, llama `input.select()` y apaga el ref.

`useLayoutEffect` corre en el mismo commit que pinta el texto crudo y antes de que el navegador procese la tecla siguiente (el foco es un evento discreto: React 18 renderiza en forma síncrona al final del handler). Por eso no hay ventana para un dígito tecleado rápido, cosa que `requestAnimationFrame` sí dejaría.

Si el valor es 0, el campo queda vacío y `select()` no hace nada. Es inocuo.

### D3 — `pointerDownRef` se apaga también en el blur
Caso: el campo tiene el foco por Tab, se hace clic dentro (hay `pointerdown` pero no `focus`) y se sale con Tab. Sin el reset, el próximo foco por teclado se trataría como puntero y no seleccionaría.

**N2 de QA (declarado, no se corrige):** un `pointerdown` que no termina en foco deja `pointerDownRef` en true hasta el próximo foco. Pasa, por ejemplo, sobre un campo `disabled` si el navegador entrega el evento. Ese próximo foco, aunque venga del Tab, no selecciona, y eso ocurre una sola vez. Apagarlo en `pointerup`/`pointercancel` parece barato, pero rompe el toque en celular: en iOS el foco llega **después** de `pointerup`, así que el toque contaría como teclado y seleccionaría todo. Se prefiere el caso raro de N2 a cambiar el toque de todas las pantallas.

### D4 — Lo que NO cambia
- `handleBlur` (parseo de «,» y «.», redondeo a `decimals`, `min`, `onChange` en cada blur) y `handleChange` (el regex) quedan **byte a byte**, salvo la línea que apaga `pointerDownRef`.
- Las props y la firma no cambian. Los 74 usos no se tocan.
- El texto que se ve con y sin foco no cambia.

### D5 — Se retira el parche local de Liquidar Entrada
`selectOnFocus` en `InboundLiquidatePage.tsx` (de la rama `coder-1/precio-por-compra`) envuelve la celda y el precio base y hace lo mismo con `requestAnimationFrame`. Con D1–D3 sobra. Se retira **en este ciclo** solo si (a)+(b) ya está integrado en develop cuando llegue la construcción: en ese caso merge de develop a esta rama y retiro, medido con el mismo E2E. Si no está integrado, el retiro queda como línea propia del backlog para después del merge.

## 3. Verificación (no hay infra de test de frontend)

**Autor:** `npm run lint` (techo 37), `tsc`, `build` y las tres guardas del árbol con `lockf` y mi `TEST_DATABASE_URL`, con un log que imprime la base de test. Sin suite completa ni dirigidas de backend (no se toca backend; regla de Daniel del 20-nov).

🔴 **Regla de las cifras (C2 de QA).** Lo que borra la selección es el reformateo del valor que **ya está en el campo** al entrar, no la cifra que se escribe: «1.300» → «1300» la borra; «900» → «900» no. Lo destapó el plantado de (a)+(b) (P9b, `sonda_p9b.log`). Por eso:
- Cada fila que entra con Tab parte de un valor previo de 1.000 o más, o con decimales (M-E1, M-E4 al volver con Shift+Tab, M-E5, M-E7 y M-E8: la celda **y** el precio base).
- Cada fila imprime en el log el valor previo **formateado** (sin foco) y **crudo** (con foco), y `selectionStart`/`selectionEnd` justo antes de escribir. **La fila no vale si el formateado y el crudo son iguales**: el E2E la marca INVÁLIDA y no PASS.

**Datos** (solo en mi BD `reciclaje_coder_1`, por la API de :8011): en Costa los precios de **venta** vigentes están todos en 0, así que Nueva Venta no sugiere nada. Para M-E5 se carga un precio de venta de 3.800 para un material de Costa (`POST /price-lists`). Nueva Compra ya sugiere precios de 1.650 a 7.950.

**E2E con teclado real** (Playwright propio, sin `fill()`), contra :8011/:5181 en la BD `reciclaje_coder_1`. No guarda nada: aborta el POST o no hace clic en guardar.

| # | Pantalla | Acción | Esperado |
|---|---|---|---|
| M-E1 | Nueva Compra (Costa) | Tab a un precio prellenado por la lista, escribir 1250, Tab | 1.250 |
| M-E2 | Nueva Compra (Costa) | clic después del 1.er dígito, escribir 5, Tab | dígito insertado (como hoy, 15.300 sobre 1.300) |
| M-E3 | Nueva Compra (Costa) | clic al final, escribir 0, Tab | 13.000 (como hoy) |
| M-E4 | Nueva Compra (Costa) | Tab al precio, clic dentro, Tab afuera, Shift+Tab de vuelta, escribir 7, Tab | 7 (D3) |
| M-E5 | Nueva Venta (Costa) | Tab al precio sugerido, escribir 900, Tab | 900 |
| M-E6 | Nueva Venta (Costa) | cantidad (2 decimales): escribir «1,23456», Tab; volver con clic y leer el valor crudo | «1.23» (redondeo a `decimals` intacto). Se lee el crudo porque el formateado muestra «1,23» con o sin redondeo (C1 de QA) |
| M-E7 | Nueva Venta (Costa) | Tab por un precio sin escribir | el valor no cambia (blur igual que hoy) |
| M-E8 | Liquidar Entrada (SAC) | Tab al precio de una celda prellenada, escribir, Tab (y lo mismo en el precio base) | reemplaza; con D5, sin el parche local |

**Plantado** (la matriz va commiteada con el plan, antes de plantar; copia por ruta, restauración desde la copia y cierre con sha256):

| P | Defecto plantado | Debe caer | Puede caer de más |
|---|---|---|---|
| M1 | seleccionar en todo foco (sin `pointerDownRef`) | M-E2, M-E3 | — |
| M2 | sin selección (el código de hoy) | M-E1, M-E5 | M-E4, M-E8 |
| M3 | `select()` en `handleFocus`, ANTES del reformateo (sin `useLayoutEffect`) | M-E1, M-E5 | M-E4, M-E8 |
| M4 | sin el reset de `pointerDownRef` en el blur | M-E4 | — |
| M5 | `handleBlur` sin redondeo a `decimals` | M-E6 (crudo «1.23456») | — |
| M6 | solo si D5 entra: `MoneyInput` con M2 **y** la página sin el parche | M-E8 | — |

M5 es el control de que M-E6 mide el parseo. Si M5 no tumba M-E6, el test de «el blur no cambió» es vacuo. M6 es el control de que Liquidar Entrada ya no depende de su parche: con el componente roto y sin el parche, M-E8 tiene que caer.

**Capturas de Costa** a 1440 y 390: Nueva Compra después de Tab y escribir sobre el precio.

**Golden:** no aplica. El golden compara respuestas HTTP y aquí no cambia ninguna.

## 4. Supuestos
- S1: el defecto es solo de la entrada por teclado. El clic que edita un dígito es uso real y se conserva.
- S2: en una tablet, el toque se trata como puntero (no selecciona), igual que hoy.
