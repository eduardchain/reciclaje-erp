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

*(resultados: §5, se llenan al correr)*

## 5. Resultados

*(pendiente)*
