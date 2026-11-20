# Plan — El valor total digitado llega exacto a la compra (redondeo del precio unitario)

**Versión:** v1.1 (C1–C5 de QA) · **Fecha:** 2026-11-19 · **Nivel:** lógica · **Base:** `4dc2c73`

**Pedido.** Johana, por Daniel (19-nov), con una captura de la liquidación de una Entrada:
- digitó un valor total de **$3.138.450** para 1.503 unidades;
- la compra nació en **$3.138.444,36**, y le descuadra contra la factura del proveedor.

«El valor de la factura es ese… y me lo toma por… no se puede estar [con] rastros, más diferencia, siempre ahí en las cuentas y en las compras». Pidió un ítem de ajuste por la diferencia; se descarta, porque es justo el rastro que ella no quiere.

**Decisión de Daniel (19-nov, por la ventanita): opción A.** Se guarda el precio con más decimales en las columnas compartidas. Se descartó la B, «el total digitado manda solo en el camino Entrada→compra», porque rompe la regla «total = cantidad × unitario» y deja una regla especial para SAC.

## 1. Causa

`#95 D8` aceptó la diferencia creyendo que era de un centavo («$200.000 entre 3 → $200.000,01»). No lo es:
1. el unitario se deriva como `total / cantidad` y se cuantiza a 2 decimales ([inbound_order.py:419](../../backend/app/services/inbound_order.py#L419) y [:474](../../backend/app/services/inbound_order.py#L474)), porque `purchase_lines.unit_price` es `Numeric(15,2)`;
2. la compra se arma con `cantidad × unitario` ([purchase.py:447](../../backend/app/services/purchase.py#L447) y [:460](../../backend/app/services/purchase.py#L460));
3. el error del redondeo, que llega a medio centavo, se multiplica por la cantidad: hasta `cantidad × $0,005`.

**Medido** (python, `Decimal`, mismo cálculo que el servidor):

| Total digitado | Cantidad | Hoy (2 decimales) | Con 8 decimales |
|---|---|---|---|
| 3.138.450 | 1.503 | 3.138.444,36 | **3.138.450,00** |
| 200.000 | 3 | 200.000,01 | **200.000,00** |
| 987.654.321 | 45.660 | 987.654.109,20 | **987.654.321,00** |
| 123.456.789 | 999.999,999 | 123.459.999,88 | **123.456.789,00** |

**Por qué 8 y no 6.** Las cantidades por línea de compra en dev (réplica) llegan a 35.330 en Costa y 45.660 en Meta. Con 6 decimales el error queda en `cantidad × 0,0000005`, o sea hasta $0,02 en esas líneas. Con 8 decimales queda bajo medio centavo para cualquier cantidad que admite `purchase_lines.quantity` (`Numeric(10,3)`, la fila de 999.999,999 de la tabla).

## 2. Alcance

| Columna | Hoy | Después | Tabla |
|---|---|---|---|
| `purchase_lines.unit_price` | `Numeric(15,2)` | `Numeric(21,8)` | **compartida** |
| `inventory_movements.unit_cost` | `Numeric(15,2)` | `Numeric(21,8)` | **compartida** |
| `inbound_line_allocations.unit_price` | `Numeric(15,2)` | `Numeric(21,8)` | exclusiva de SAC |

`21,8` conserva los 13 dígitos enteros de hoy.

**Por qué también `inventory_movements.unit_cost`.** Desliquidar una Entrada (#93 D20) o cancelar una compra liquidada saca del pool con el costo leído del `InventoryMovement` ([purchase.py:913](../../backend/app/services/purchase.py#L913), #66 H1, fuente única del costo con comisión). Si esa columna se queda en 2 decimales, la reversa saca `cantidad × 2.088,12` de un pool al que entró `cantidad × 2.088,1237…`. Lo que pasa con la diferencia depende de la rama de `remove_from_pool` ([inventory_costing.py:103-114](../../backend/app/services/inventory_costing.py#L103-L114)):
- **Rama 1, queda stock y valor:** la diferencia (los $5,64 del caso) se queda escondida en el promedio del material.
- **Rama 2, queda stock pero el valor no alcanza, y rama 3, la reversa vacía el pool:** va a la línea del P&L «Ajuste costo por sobreventa y reversiones» (`cancellation_cost_adjustment`).

En los dos casos el rastro solo cambiaría de lugar.

**Ruido que queda y es preexistente.** El promedio se guarda con 4 decimales (`15,4`), así que las reversas no vuelven exacto. Medido con los helpers REALES de `inventory_costing.py`, cuantizando el promedio a 4 como la BD (C2 de QA, reproducido):
- **Rama 1:** el error del promedio al INCORPORAR se reparte sobre `stock + cantidad`, y al REMOVER queda concentrado en el stock previo. Cota: `(2 × stock_previo + cantidad) × $0,00005`. Ejemplo: stock 13 a $123,4567 más la Entrada de Johana; el pool vuelve con $0,0663 de diferencia y el promedio queda en $123,4516.
- **Ramas 2 y 3:** el ajuste se cuantiza a centavos, así que la cota es `cantidad × $0,00005 + $0,005`. En el caso de Johana el ajuste da −$0,07.

Pasa igual con cualquier compra de Costa y no toca la factura ni el saldo del proveedor. No se arregla acá (§8).

**Lo que la columna en 2 decimales del `InventoryMovement` haría, medido y no supuesto** (C2c): con la base de HOY la rama 3 da $0,00, porque línea, movimiento y promedio están los tres en 2.088,12. Los −$5,71 aparecen SOLO si la línea pasa a 8 decimales y el movimiento se queda en 2, que es justo el plantado P2. Por eso el movimiento se ensancha en el MISMO cambio.

**No cambia:**
- `purchase_lines.total_price` y `purchases.total_amount` (`15,2`): son pesos y quedan exactos.
- `materials.current_average_cost` y `material_cost_history` (`15,4`): el promedio sigue con 4 decimales. El inventario valorizado (`promedio × stock`) puede diferir del valor pagado en centavos. Es preexistente y no es la factura.
- `sale_lines.unit_cost` (`15,2`, #64 «rounding conocido pre-existente»).
- El espejo Willard `unit_cost=avg.quantize(0.01)` ([inbound_order.py:1322](../../backend/app/services/inbound_order.py#L1322)) cuantiza explícito y no se toca: entra a identidad D2 y no es una factura.

## 3. Backend

1. **Migración** (una, nueva): `ALTER COLUMN … TYPE NUMERIC(21,8)` en las tres columnas.
   - Ensanchar la escala **no cambia ningún valor guardado**: 2088.12 queda 2088.12000000.
   - Reescribe la tabla. En la réplica son 7.482 líneas de compra y 8.631 movimientos: segundos.
   - El `downgrade` vuelve a `(15,2)` y **redondea** lo que se haya guardado con más decimales. Queda escrito en el docstring.
2. **Modelos** (`purchase.py`, `inventory_movement.py`, `inbound_order.py`) declaran `Numeric(21,8)`. El parity check exige que coincidan con la migración.
3. **`PRICE_Q`** en [inbound_order.py:419](../../backend/app/services/inbound_order.py#L419) pasa de `0.01` a `0.00000001`. Se corrige el comentario de la línea 470-473, que dice que se cuantiza a centavos por la firma.
   - **Firma de reliquidación (#93).** Sigue viendo el mismo número que se persiste, porque el cuantizado ocurre en el mismo punto. Una Entrada desliquidada ANTES del deploy tiene compras con el unitario viejo de 2 decimales: al reliquidarla, la firma difiere y se rearma (revert-and-reapply) con el número exacto. Es lo correcto y queda declarado.
   - **Modo por kg (#101).** `_total_desde_kg` resuelve a `total_price` y desemboca en la misma división, así que queda cubierto sin tocarlo (T6).
4. **`purchase.py` no cambia.** `total_amount = Σ cantidad × unitario` sin redondear da `3.138.450,0000075`, y el saldo del proveedor, el pago inmediato y la cabecera se guardan en columnas de 2 decimales. Con 8 decimales los productos quedan a menos de 0,00001 del centavo, así que redondear antes o después de sumar da lo mismo.

**Efecto en los otros escritores de `inventory_movements.unit_cost`** (filas NUEVAS; las existentes no cambian). Hoy Postgres redondea a 2 lo que le llega con más decimales; después guarda el valor tal cual:

| Escritor | Qué guarda | Efecto |
|---|---|---|
| Compra con comisión (#30, [purchase.py:519-525](../../backend/app/services/purchase.py#L519-L525)) | `precio + comisión/cantidad` sin redondear | El costo guardado pasa a ser el que entró al pool, y la reversa (#66 H1) saca lo mismo que entró. **Afecta a Costa**, y para mejor |
| Venta liquidada (#64, [sale.py:450](../../backend/app/services/sale.py#L450)) | el promedio (4 decimales) | Guarda 4 decimales en vez de 2. El COGS sale de `sale_lines.unit_cost`, no de acá |
| Traslado, despacho ([transfer.py:219](../../backend/app/services/transfer.py#L219)) | promedio cuantizado EXPLÍCITO a 0,01 en `transfer_lines.unit_cost` | **Sin cambio**: sigue guardando 2 decimales (C4 de QA) |
| Ajustes, transformaciones y el resto de los movimientos de traslado | promedio o costo dado | Guardan el valor sin redondear. Su anulación refleja el valor guardado ([transfer.py:799](../../backend/app/services/transfer.py#L799)), así que sigue siendo consistente |

Lectores de `inventory_movements.unit_cost` con aritmética (verificado por QA): solo [purchase.py:913](../../backend/app/services/purchase.py#L913), que es el que se quiere arreglar, y [transfer.py:799](../../backend/app/services/transfer.py#L799), que es espejo. Los de `reports.py` (2829, 2999 con `Decimal(str())`, 3979 del dashboard) sirven `float` o comparan contra 0, así que no cambian de forma.

Lo que se sirve no cambia de forma: `PurchaseLineResponse` e `InventoryMovementResponse` serializan a `float` ([schemas/purchase.py:86](../../backend/app/schemas/purchase.py#L86), [schemas/inventory_movement.py:56](../../backend/app/schemas/inventory_movement.py#L56)), así que `2088.12000000` sale como `2088.12`. Los schemas de la Entrada que devuelven `Decimal` sin serializador (`unit_price` en las asignaciones) pasan a mandar el string con 8 decimales, **también para los datos VIEJOS** («2088.12» pasa a «2088.12000000», C5 de QA). Grep de render crudo de `unit_price` en `pages/inbound` (19-nov):
- `InboundLiquidatePage.tsx:213` entra por `num(a.unit_price)`;
- `:132` y `:1011` usan ese valor ya coercionado;
- `InboundDetailPage.tsx:686` pinta con `fmtMoney(a.unit_price)`, que resta (coerciona) y formatea con `Intl`, que acepta el string;
- los `line.unit_price` de `InboundEditPage.tsx:595` e `InboundCreatePage.tsx:747` son de `inbound_order_lines`, que NO se ensancha.

Ninguno pinta el valor crudo. Se repite el grep sobre el árbol final y su salida va al informe.

## 4. Frontend

- **`InboundLiquidatePage`**, vista previa del reparto ([:124-135](../../frontend/src/pages/inbound/InboundLiquidatePage.tsx#L124-L135) y [:1030-1050](../../frontend/src/pages/inbound/InboundLiquidatePage.tsx#L1030-L1050)): `effUnitPrice` redondea a 8 decimales en vez de 2, y `effAllocTotal` redondea el producto a centavos.
  - Con eso el aviso ámbar (D8) desaparece en los casos normales, y deja de pintar «$ 2.088,12 c/u → $ 3.138.444,36». Muestra «$ 2.088,12 c/u → $ 3.138.450».
  - El comentario de D8 se corrige: dice que la diferencia es de un centavo.
  - El ámbar se conserva por si algún caso llega a diferir; no se espera ninguno.
  - En JS, `cantidad × 1e8` cabe sin pérdida en un `number` para las cantidades de la tabla de §1.
- **Display del unitario.** `formatCurrency` y `fmtMoney` pintan 2 decimales, así que 2088.12375250 se ve «$ 2.088,12» en el detalle, el PDF (#119) y el estado de cuenta. Sin cambio.
- **Declarado, sin cambio:** una compra de Entrada desliquidada queda `registered` y se puede editar directo en Compras, donde el `MoneyInput` del unitario tiene 2 decimales. Si alguien la edita ahí, el unitario vuelve a 2 decimales. Al reliquidar desde la Entrada, la firma difiere y la compra se rearma desde el reparto, así que el reparto gana igual.

## 5. Tests — `tests/test_redondeo_precio_compras.py` (nuevo)

| T | Caso | Afirma |
|---|---|---|
| T1 | Entrada, una asignación por **valor total** 3.138.450 para 1.503 | El unitario PERSISTIDO, leído por HTTP después del commit (`GET /purchases/{id}`): `unit_price == 2088.1237525`. `total_amount` de la compra = 3.138.450,00; `total_price` de la línea igual; el saldo del proveedor baja exactamente eso; el evento del estado de cuenta lleva ese monto. Todo leído por HTTP |
| T2 | 45.660 kg por valor total 987.654.321 | Igual que T1, al peso |
| T3 | T1 → **desliquidar**, en las dos ramas: (a) con stock previo del material, (b) con el pool vacío antes de la Entrada | El saldo del proveedor vuelve al de antes, exacto. (a) el valor del pool (`promedio × stock`) vuelve al previo dentro de `(2 × stock_previo + cantidad) × $0,00005`. (b) `|cancellation_cost_adjustment|` ≤ `cantidad × $0,00005 + $0,005`. **No discrimina base contra nuevo**: con la base de hoy (b) da $0,00. Lo que discrimina es P2 (−$5,71) |
| T4 | T3 → reliquidar sin cambios | Los mismos números de compra (firma igual); el total sigue en 3.138.450,00 |
| T5 | Compra directa estilo Costa, unitario de 2 decimales | Los mismos totales que hoy: no-regresión |
| T6 | Modo **por kg** (#101) con un precio por kg que no divide exacto | `total_amount` = el total que muestra la pantalla (`peso × precio_kg`, a centavos) |
| T7 | Compra directa **con comisión** (#30) cuyo costo ajustado no cae en centavos, liquidar y cancelar con el pool vacío antes (rama 3) | `|cancellation_cost_adjustment|` ≤ `cantidad × $0,00005 + $0,005`. Hoy lo excede, porque el `InventoryMovement` guarda el costo con comisión redondeado a 2 mientras el pool recibió el valor sin redondear. Se mide en la construcción contra la base, y el control positivo es P2 |
| T8 | Dos asignaciones de la misma línea, dos proveedores, cada una por valor total | Cada compra exacta; el descuadre (pesado − repartido) no cambia |

## 6. Matriz de plantado (predicciones escritas antes)

Reescrita el 19-nov con C1 y C2 de QA (T9, T10, P5–P7) y ANTES de plantar. Donde la v1.1 decía otra cosa, se corrige aquí y no después de medir: la v1.1 ponía que T3 caía con P1 «al menos por su primer assert», pero ningún assert de T3 mira un total. Afirma el saldo de vuelta al previo, que se cumple con cualquier escala, y cotas de pool que con la línea y el movimiento en la misma escala también se cumplen.

| P | Defecto plantado | Predicción: caen |
|---|---|---|
| P1 | `PRICE_Q` vuelve a `0.01` | **Al menos:** T1, T2, T4, T6, T8 y `test_total_deriva_el_unitario`. **No caen:** T3a, T3b, T5, T7, T9, T10 y `test_total_demasiado_bajo_avisa_claro` ($0,01 / 3.000.000 queda en 0 con cualquier escala) |
| P2 | `InventoryMovement.unit_cost` del modelo vuelve a `Numeric(15,2)` | **Al menos:** T3a (el pool se aleja 1.503 × 0,0037525 ≈ $5,64, contra una cota de $0,095), T3b (ajuste ≈ −$5,64, contra una cota de $0,08), T7 (≈ $0,02 contra $0,00535) y `test_cogs_uses_avg_at_liquidation_not_registration` (el movimiento queda en 8666,67). Es vía compartida, así que pueden caer otros |
| P3 | `PurchaseLine.unit_price` del modelo vuelve a `Numeric(15,2)` | **Al menos:** T1, por el unitario persistido leído por HTTP. Los asserts de totales no la tumban. T4 puede caer o no: la firma ve 2088,12 en la línea contra 2088,1237525 en la asignación y re-sincroniza; si cae, se escribe por qué assert. Es vía compartida |
| P4 | `effUnitPrice` vuelve a 2 decimales | Ningún test: es pantalla. Se verifica abriéndola (§7) |
| P5 | Se quita la cuantización de `reference_unit_price` (la guarda queda) | T9: el ajuste queda en 2088,1238 y el aviso con 2088.1237525. T10: 0,001 ya no es ≤ 0, así que no hay 422 |
| P6 | Se quita `toCents` de la rotación hacia unitario (pantalla) | Ningún test. En el navegador: rotar total → unitario y hacer Tab. Plantado, el total de la vista previa se mueve al hacer Tab; con el arreglo, no se mueve |
| P7 | Se quita la guarda del ref en ≤ 0 (la cuantización queda) | T10. El ref de $0,00 sigue al descuadre, y no se sabe por dónde revienta: el `gt=0` del increase (422 con otro texto, o 500) o un ajuste en $0 con 200. Las tres cosas tumban T10. Se escribe en el log cuál fue |

P1, P2 y P3 viven en vías compartidas: la predicción es «al menos estas». Que caiga algo más es la dirección barata, no la peligrosa.

## 7. Gates

- ruff, tsc, eslint (37 = techo).
- **QA pasada 1** con el patch y sha256, antes de cualquier gate.
- **Dirigidas por grep**, con el comando en el log. Superficie: `unit_price` de compras, `inventory_movements`, Entradas. Más las tres guardas del árbol: `test_reloj_de_negocio.py`, `test_advisory_locks.py` y `test_crucible_charges.py`.
- **Plantado** según §6, con respaldo por ruta y cierre por sha256 del árbol.
- **Parity check**: DIFF CERO (la migración y los modelos tienen que declarar la misma escala).
- **Smoke de migración en dev**:
  - `upgrade`, `downgrade` y `upgrade`;
  - `information_schema` impreso con la escala antes y después;
  - una Entrada liquidada por POST real con los números de Johana, contra un backend arrancado DESPUÉS del último cambio de `app/`, con el PID impreso.
- **Golden: APLICA** (dos tablas compartidas), con **DOS bases de datos** (C1 de QA).
  - **Por qué no basta el golden de hoy.** `golden_run.sh` levanta :8001 (worktree base) y :8002 (develop) contra la MISMA BD del `.env`. Con la BD migrada, el código base también lee `Numeric(21,8)`, porque psycopg devuelve el `Decimal` con la escala de la BD y no la del modelo. Un «2088.12000000» saldría igual en los dos lados y el diff daría 0, justo en la dimensión que este cambio mueve.
  - **Cambio a `golden_run.sh`** (pasa por QA): opción `--db-before <url>` / `--db-after <url>`, y cada uvicorn arranca con su `DATABASE_URL` explícito. Sin las opciones, el comportamiento de hoy, byte a byte.
  - **Procedimiento:** antes del `upgrade`, `CREATE DATABASE golden_before TEMPLATE <réplica>`, una copia SIN migrar. Después se migra la réplica. BEFORE = base sobre `golden_before`; AFTER = develop sobre la réplica migrada.
  - ⚠️ **Runbook (nota de QA):** `CREATE DATABASE … TEMPLATE` falla si hay CUALQUIER sesión conectada a la réplica, incluido el :8001 de la pantalla de Daniel con `--reload`. Se avisa y se para el backend de dev antes, o se usa `pg_dump | pg_restore` hacia la copia, que no exige la base vacía de sesiones.
  - **Procedencia de la BD:** el log imprime la escala de las tres columnas consultando la URL QUE USA CADA PROCESO, y tiene que mostrar 2 contra 8. Si muestra lo mismo, el script aborta.
  - **Control positivo FUERA de `CAPTURES`:** GET de una Entrada liquidada de SAC en los dos lados. `InboundAllocationResponse.unit_price` es `Decimal` sin serializador, así que tiene que salir «2088.12» contra «2088.12000000». Esa diferencia solo la produce la escala, y prueba que los lados difieren en lo que se mide.
  - **Predicción escrita antes:** 0 diffs reales y 0 claves aditivas en `CAPTURES`, más ese diff en el control positivo. Si en `CAPTURES` aparece un diff de forma («2088.12» contra «2088.12000000»), se analiza; no se perdona por ser de forma.
  - **El checkpoint necesita la misma forma de dos BDs:** el golden del deploy (main contra develop) corre con esta opción mientras este cambio esté en el lote.
- **Suite completa: diferida al checkpoint** (regla del 19-nov).
- **Pantalla de Daniel en localhost:** el caso de Johana en la liquidación de una Entrada (vista previa sin ámbar, la compra en $3.138.450 y el PDF), y una compra directa de Costa.

## 8. Fuera de alcance

- El promedio con 4 decimales y los centavos que deja en la rama 3 de las reversas (§2).
- `sale_lines.unit_cost` con 2 decimales.
- El ciclo «reparto por compra» (matriz, dos compras del mismo proveedor, IVA en compras, crear proveedor): plan propio. Este cambio va primero porque es independiente y el otro reusa la misma división.
