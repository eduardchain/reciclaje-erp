# Informe: Detalle de Entrada, compras en tabla + «Total con IVA»

Plan: `plan-sac-compras-entrada-tabla.md` v1.2 (af6e8a9, sha256 `fc402621…e789a`). Nivel: **lógica** (solo frontend). Rama `coder-1/compras-entrada-tabla`, base develop `87c799f`.

## 1. Entregas

| Paso | SHA | Qué |
|---|---|---|
| Construcción | `461478a` | `utils/inboundPurchases.ts` (nuevo), `InboundDetailPage.tsx`, `InboundOrdersPage.tsx` |
| Pasada 1 de QA 1 | `461478a` | GO, con 3 condiciones para los gates (§4) |
| Addendum de la matriz | *(este commit)* | §3, commiteado ANTES de plantar |

## 2. Notas de la pasada 1

**N1. Lectores de «Total Liquidado», con la ruta real.** El primer grep apuntaba a `frontend/src/types/inbound.ts`, que no existe. El r2 tampoco sirvió: en zsh, una variable con varias rutas no se separa en palabras, así que salió «0 de 6 rutas» y todos los greps vacíos. Se conserva como `lectores_total_liquidado_r2_INVALIDA_zsh.log`. El r3 (`lectores_total_liquidado_r3.log`) usa un arreglo: verifica 6 de 6 rutas en `87c799f`, y su control positivo da `InboundPurchaseSummary` > 0 en 3 archivos. Resultado:

- `liquidatedTotal` y «Total Liquidado»: solo InboundDetailPage (142–144, 392–394). Reemplazados por `liquidatedTotals`.
- `purchaseTotal` del listado (OrdersPage 128–130, columna 340 y tarjeta 515): pasa a `countsAsLiquidated` (D7).
- `purchaseTotal` del detalle (DetailPage 139, «Total Capturado (ref.)»): **no es plata de compras**. Es Σ cantidad × precio de referencia de las líneas. Lo encontró el r3 y no figuraba en el plan; queda igual y O1 no lo toca.
- Backend: `total_amount` solo se serializa (endpoint 200, schema 292). No hay un segundo criterio de suma del lado del servidor.
- `excelExport.ts` y `pdfExport.ts` leen `total_amount` de compras y ventas, no de `InboundPurchaseSummary`. Están fuera del alcance.

**N2. Los cuatro `!== "cancelled"` que no son plata se quedan.** El grep r3 sobre `frontend/src` los lista. No se unifican con `countsAsLiquidated`, y el docstring de esa función lo dice:

| Sitio | Para qué cuenta compras vivas |
|---|---|
| OrdersPage:138 `entradaPartyLabel` | el «Varios (N)» del proveedor |
| DetailPage:805 diálogo de anular | «las N compras del reparto se cancelan»: una registrada también se cancela |
| InboundEditPage:245 `hasLivePurchases` | **guard de sede #118**: una registrada bloquea cambiar la sede, porque al reliquidarla se reusaría con sus líneas en la sede vieja |
| InboundLiquidatePage:594 | la precarga elige la compra viva del slot |

Los tres de Tesorería (`annulled`/`cancelled` de movimientos) son de otro módulo.

## 3. Addendum de la matriz: predicciones exactas, escritas antes de plantar

La matriz del plan (§4) no se reescribe. Esto la precisa por fila con los datos del setup:

- **A #37:** liquidadas #16, #17, #20 y #21; canceladas #18 (sub 72.500, con una fila de IVA revertida) y #19 (sub 51.000).
- **B #40:** #24 registrada, sub 24.000, IVA revertido; referencia 22.500.
- **C #39:** #23, sub 28.000, sin IVA.

Las filas sobre una vía compartida (`purchaseMoney`, `liquidatedTotals`, `countsAsLiquidated`) se escriben «al menos estos».

| P | Defecto | Cae (predicción) | Por qué |
|---|---|---|---|
| P1 | canceladas suman en `liquidatedTotals` | **al menos E2, E3a, E10** | A pasa de 205.500 a 329.000 en la fila de totales y en el «Total Liquidado»; el control de E10 compara el listado contra el detalle, y el listado no usa `liquidatedTotals` |
| P2 | IVA cuenta las filas con `reverted_at` | **solo E7** | medición C2: la única no cancelada con IVA revertido es B#24, que está `registered`. Declarado: también cambia la celda IVA de #18 (cancelada, tachada), que **ningún E lee** |
| P3 | `total = sub + iva` | **al menos E1, E2, E8** | #17 y #20 tienen retención |
| P4 | columnas de plata sin `canViewPrices` | **E4** | |
| P5 | materiales sin filtrar por slot | **E6** | |
| P6 | la cancelada pinta los materiales de su slot | **E6** | #18 y #19 comparten slot 3 y 4 con #20 y #21 (R6) |
| P7 | «Total con IVA» sin la condición IVA > 0 | **E3c** | C mostraría 28.000. B no, porque sin liquidadas el bloque no aparece |
| P8 | tabla sin `hidden md:block` | **E5** | |
| P9 | la tarjeta con su cálculo propio, sin restar retenciones | **E8** | |
| P10 | `countsAsLiquidated` vuelve a `!== "cancelled"` | **al menos E7, E10, E11; E2 queda en VERDE** | A no tiene registradas, así que sus totales no cambian. B#24 empieza a sumar: aparece «Total Liquidado» 24.000 y el listado muestra 24.000 en vez de la referencia 22.500. E3b queda verde, porque el IVA de #24 está revertido. Si E2 cae, la causa se clasifica en el log (instrumento o comportamiento) |
| P11 | el listado vuelve a su filtro `!== "cancelled"` | **E10, E11** | B: 24.000 en vez de 22.500 |
| P12 | el InfoRow «Total Liquidado» vuelve a `purchases.length > 0` | **E7** | B muestra «$0» |

Control: el árbol restaurado da 12/12 (E9 no aplica, D6).

## 4. Gates (condiciones de QA 1)

1. La evidencia de los gates (check E1–E11 y capturas a 1440/390) se re-corre sobre el SHA final, con el SHA en el encabezado del log.
2. La predicción de P2 es «solo E7» (§3).
3. P10 deja E2 en verde; si cae, la causa va clasificada.

## 5. Resultados

Evidencia en `~/sac-evidencia/2026-11-20/coder-1-compras-tabla/`.

| Gate | Log | Resultado |
|---|---|---|
| Plantado P1–P12 | `plantado_r1.log` (script `plantado.py`, HEAD `d57f6a9`) | control del árbol limpio 12/12. **Diagonal OK: 12 de 12 filas como estaban predichas, cero caídas de más.** P2 tumba solo E7 (IVA 4.560 en B#24). P10 tumba E7, E10 y E11, y **E2 queda en verde**. Por fila: el reemplazo aparece una sola vez; Vite sirve la versión plantada y después la restaurada; se re-verifica el sha256 en disco. Al cerrar, los 3 archivos quedan iguales al original, `git status` limpio y `git diff HEAD` vacío |
| Dirigidas | `dirigidas.log` | superficie de backend: `git diff --name-only 87c799f HEAD -- backend` da 0 archivos. Corren solo las 3 guardas: **52 passed, EXIT=0**, contra una predicción de 52 escrita antes. BD `reciclaje_test_coder_1`; había 6 pytest vivos, todos de otras sesiones con otra BD |
| Lint / tsc / build | `lint_final.log`, `tsc_final.log`, `build_final.log` | 37 avisos y 0 errores (igual al techo); tsc EXIT=0; build EXIT=0 |
| Check E1–E11 y capturas | `check_final.log`, `capturas_final/` | corren sobre el SHA final (condición 1); el SHA va en el encabezado del log |

Golden: **no aplica**. Es un cambio solo de frontend (0 archivos de `backend/`), y el golden captura respuestas HTTP.

Suite completa del frontend: diferida al checkpoint.

## 6. Delta tras la entrada de Ingrid (develop `d5d9267`, decisión #129)

| Paso | SHA | Qué |
|---|---|---|
| Merge de develop | `3fcb5ba` | sin conflictos de texto: Ingrid toca las tarjetas, el «Cara Financiera» y el listado (hunks fuera de los míos, como preveía D6) |
| Alcance en la tabla | *(este commit)* | `PurchasesTable` recibe `outOfScope` y `collectorName`. Con la MISMA regla de las tarjetas de Ingrid: proveedor fuera del alcance → Compra y Proveedor sin link y la nota ámbar debajo del proveedor. Sin alcance, `outOfScope` da siempre false y la tabla queda byte a byte como en `0732eab` |

**E9** (`e2e_e9.mjs`, en la BD dev propia; escenario restaurado en `finally`):
- **Escenario:**
  - SUP_A marcado con el recolector Green Loop (dentro del alcance) y SUP_B sin marca (fuera).
  - Entrada D #41 con recolector Green Loop, liquidada en dos compras.
  - Alcance Green Loop TEMPORAL para un miembro no admin (david); se le quita al terminar.
- **Asserts:**
  - E9a: tabla a 1440, la compra de dentro con los 2 links y sin nota; la de fuera sin links y con nota.
  - E9b: tarjetas a 390, la misma regla (paridad con el código de Ingrid).
  - E9c: **control positivo**, el admin sin alcance ve los 2 links en las dos filas.
- **Antes del plantado:** `e9_r1.log` da 3/3 sobre el árbol con el delta.

**Matriz del delta, escrita antes de plantar:**

| P | Defecto | Cae (predicción) |
|---|---|---|
| P13 | la tabla ignora `outOfScope` (las celdas con link siempre) | **E9a, y solo E9a.** E9b queda verde (las tarjetas son de Ingrid) y E9c también (sin alcance no cambia nada) |
