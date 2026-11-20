# Informe — MoneyInput: escribir sobre un valor lo reemplaza

Autor: Eco Coder 1 · 20-nov-2026 · rama `coder-1/moneyinput-seleccion` (base develop `439258a`)
Plan: `plan-moneyinput-seleccion.md` v1.1 (`78a4ea2`, GO de Eco QA 1 con C1 y C2). Nivel **lógica**.
Es código compartido: un archivo, que usan 40 pantallas de las 7 orgs. Código en `584d2e2`.

## Qué cambió (`frontend/src/components/shared/MoneyInput.tsx`)

- **Al entrar con teclado** (Tab, Shift+Tab, `.focus()`, `<Label htmlFor>`) el campo selecciona todo: escribir reemplaza el valor. Antes, el foco cambiaba «1.300» por «1300», ese cambio de `value` borraba la selección del Tab y escribir 1250 daba «13.001.250».
- **Con mouse o dedo no selecciona.** `pointerDownRef` se enciende en `onPointerDown` y lo consume `handleFocus`. El clic sigue dejando el cursor donde se hizo, para corregir un dígito (15.300 sobre 1.300, como antes).
- **La selección se aplica en `useLayoutEffect`**, sobre `[displayValue, focused]`, después del reformateo y antes de la tecla siguiente.
- **`pointerDownRef` se apaga también en el blur** (D3).
- `handleBlur` (parseo y redondeo) y `handleChange` (regex) quedan iguales.

## Pendientes y decisiones para Daniel

1. **N2 de QA (declarado, no se corrige):** un `pointerdown` que no termina en foco deja el ref encendido, y el próximo foco por Tab no selecciona, una sola vez. Apagarlo en `pointerup` rompería el toque en iOS, donde el foco llega después.
2. 🔴 **D5 no se aplica — DECIDIDO (Coordinador, 20-nov): en la matriz el clic selecciona todo y el parche se queda.** El plan decía que el `selectOnFocus` local de Liquidar Entrada «hace lo mismo» y sobraba, y era falso: el parche selecciona también con **clic**, y `MoneyInput`, por D1, a propósito no lo hace. Son una divergencia deliberada (lección de #102): en una matriz de precios lo normal es reemplazar el precio entero, y en un formulario de Costa el clic sirve para corregir un dígito. Daniel ya había visto y aprobado la matriz en localhost («lo veo bien»). **Lo fija E14b** del E2E de (a)+(b) («clic + escribir 4200» reemplaza), que da 22/22 con el `MoneyInput` nuevo. M6 no corre: el parche no se retira.
3. **Ya existían y no se tocan:**
   - en Nueva Compra, el Tab desde el precio cae en el hint «Lista: $ X»;
   - a 390 px ese hint se monta sobre el rótulo «TOTAL» (se ve en `costa_nueva_compra-390.png`);
   - en mi BD, Costa tiene todos los precios de venta vigentes en 0, así que Nueva Venta no sugiere nada.

## Gates (evidencia en `~/sac-evidencia/2026-11-20/coder-1-moneyinput-seleccion/`)

- lint 37/0, `tsc` 0, `build` 0, y las tres guardas con 52 passed en `reciclaje_test_coder_1` bajo lockf (`guardas.log`).
- **E2E** con teclado real, sin `fill()`, sin guardar nada: **9/9** (`e2e_limpio.log`).
  - Cubre Nueva Compra y Nueva Venta de Costa, y Liquidar Entrada de SAC en su versión de develop.
  - Cada fila imprime el valor previo formateado y crudo y la selección. Si formateado == crudo, la fila sale INVÁLIDA (C2).
  - En la primera corrida, M-E1 y M-E5 salieron INVÁLIDAS porque el instrumento leía el previo con el campo enfocado; la guarda lo atrapó y se corrigió antes de plantar.
  - Dato de M-E5: precio de venta de 3.800 para NF024 en Costa, solo en mi BD (`datos.log`, id `917b1bc1…`).
- **Plantado** contra la matriz de `78a4ea2`, con predicciones escritas antes, copia por ruta y cierre por sha256 `a01f6c20…` con `git status` vacío (`plantado.log`). **Las 5 filas caen en la diagonal:**

| M | Defecto plantado | Cayó |
|---|---|---|
| M1 | selecciona en todo foco | M-E2 («5»), M-E3 |
| M2 | sin select() | M-E1 («36.001.250»), M-E5, más M-E4 y M-E8 (predichos de más) |
| M3 | select() antes del reformateo | lo mismo que M2: la selección se pierde |
| M4 | sin reset en el blur | M-E4 («36.007») |
| M5 | sin redondeo | M-E6 (crudo «1.23456») |

- Capturas de Costa: `costa_nueva_compra-1440.png` y `-390.png`, tomadas después de Tab y escribir 1250 sobre 3.600.
- **Merge de develop** (`31ba117`, que trae (a)+(b)) en `3017bd5`: sin conflictos y con `--remerge-diff` vacío. `git diff develop` = `207de853…`, el mismo delta que antes del merge. Sobre el árbol combinado:
  - lint 37/0, `tsc` 0, `build` 0 (`*_merge.log`);
  - E2E de MoneyInput 9/9 (`e2e_merge.log`; M-E8 ahora mide la página nueva con el parche);
  - E2E de (a)+(b) 22/22 (`e2e_precio_por_compra_con_moneyinput.log`);
  - guardas (`guardas_merge.log`).
- Golden: no aplica (solo frontend).

## Borrador de la decisión (la numera el Coordinador)

**MoneyInput reemplaza al escribir sobre un valor (pedido de Daniel, 20-nov; código compartido, 7 orgs)**: el foco cambiaba «1.300» por «1300», y ese cambio de `value` borraba la selección del Tab: escribir 1250 daba «13.001.250» en todo campo de monto con valor. Ahora, si el foco llega por teclado, se selecciona todo en `useLayoutEffect`, después del reformateo. Si llega con mouse o dedo, el cursor queda donde se hizo clic, para corregir un dígito. El parseo y el blur no cambian. ⚠️ El defecto solo se ve cuando el valor previo tiene separador de miles o decimales: con 700 o 10 el texto no cambia al enfocar y un test pasa con y sin el arreglo.
