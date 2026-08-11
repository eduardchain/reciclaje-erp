# Análisis previo — Multi-proveedor por línea en la Entrada (SAC)

**Estado:** borrador de análisis, NO es plan todavía. Cinco preguntas abiertas cambian el diseño de forma material; el plan se escribe cuando estén contestadas.
**Origen:** reunión SAC 2026-08-03, minuto 00:58:40 – 01:03:00.
**Fecha:** 2026-08-04.

---

## 1. Lo que la transcripción YA resuelve

Veníamos con esto anotado como "preguntar primero a Johana si Green Loop es el proveedor único
y los 15 son informativos — si lo es, no hay nada que construir". **La transcripción lo contesta y
la respuesta es que sí hay algo que construir:**

| Hecho | Cita |
|---|---|
| Son proveedores **reales y distintos**, cada uno con su cuenta | Johana: *"Correcto. Cada una tiene un proveedor diferente."* |
| Volumen: de 1 a 15 compras por entrada | Johana: *"puede haber una como pueden haber 11, 12, 15"* / Erwin: *"en unas hay 14, 10 así, depende"* |
| Frecuencia: **diaria** | Johana: *"Todos los días todos los días hacen recolección"* |
| Las entradas de Green Loop son **siempre compra regular** | Johana: *"los de ellos siempre es regular"* |
| Existe también el caso simple (un proveedor entrega directo en patio) | Johana: *"es el mismo proveedor, un solo proveedor en la entrada"* |
| Quien liquida esas compras es **Ingrid** | Johana: *"la que la liquidaría sería Ingrid"* |

Y lo que Daniel se comprometió a entregar, textual:

> *"las entradas nos permitan no tener aquí un proveedor fijo, sino que por cada línea de material
> destinamos al proveedor"* … *"con que ustedes puedan fijar … 'todas estas líneas van a un mismo
> proveedor, pum' o van a proveedores distintos, le dan clic a algo"*

**Green Loop es el recolector (comisionista), no el proveedor.** Eso ya está construido: la comisión
del recolector se causa como gasto al liquidar (decisión #83). Lo que falta es que los proveedores
del material dejen de ser uno solo por entrada.

### Reductor de alcance importante

Como las entradas de ruta son **siempre compra regular**, el multi-proveedor **no toca el camino
Willard** en absoluto: ni el libro de kg, ni el snapshot de fórmulas, ni la confirmación en dos pasos
(#81), ni la sede determinista (#80). Toda esa maquinaria queda intacta por construcción si el
proveedor por línea se restringe a `inbound_type='purchase'`.

---

## 2. Lo que NO está resuelto — preguntas para Johana

Ninguna de estas se preguntó en la reunión y **cada una cambia el diseño**.

### P1 — ¿De dónde salen los kilos de cada proveedor? *(la crítica)*

El camión llega con material de 15 proveedores mezclado y se descarga de una sola vez. Si la báscula
pesa el total, ¿cómo se sabe cuánto puso cada proveedor? Presumiblemente Green Loop trae una
relación con el peso de cada uno. **¿Y si el peso de la báscula no cuadra con la suma de esa
relación — quién absorbe la diferencia?** Hoy la línea de la entrada tiene `quantity` y
`scale_weight_kg` como campos separados; la respuesta define si hay que repartir un faltante entre
proveedores (y con qué criterio) o si cada línea se pesa por aparte.

### P2 — ¿La comisión de Green Loop es una sola por ruta, o una por proveedor?

Hoy la comisión se causa al liquidar **una** compra. Con 15 compras derivadas de una entrada, el
comportamiento natural sería 15 comisiones. La tarifa es por kg, así que el **monto total es el
mismo** en ambos casos — pero el estado de cuenta de Green Loop se ve muy distinto: 15 renglones de
$40.000 o uno de $600.000.

### P3 — ¿Se puede liquidar la entrada por partes?

Si a Ingrid le falta el precio de dos proveedores, ¿liquida los otros 13 hoy y esos dos mañana? Si la
respuesta es sí, la entrada necesita un estado intermedio ("parcialmente liquidada") que hoy no
existe: el estado es binario. Si es no, se exige liquidar todo junto y el modelo actual se conserva.

### P4 — ¿Cada proveedor trae su propia remisión o factura?

Acabamos de poner la factura en la Entrada (una sola, en la cabecera). Si cada proveedor de la ruta
tiene su documento, la factura tiene que bajar al nivel del proveedor.

### P5 — Estado "revisada": ¿puede la misma persona registrar y revisar?

Johana lo planteó como separación de funciones: *"el que la registra no sería el mismo que la
revise"*, David registra y Erwin revisa. Pero si el sistema lo prohíbe de forma dura y un día David
está solo en el patio, la operación se traba. ¿Bloqueo estricto, o se permite con el registro de
quién hizo qué?

*(P5 pertenece al ciclo del estado "revisada", no a este — pero se pregunta en el mismo mensaje.)*

---

## 3. Mapa de impacto técnico

### 3.1 El cambio estructural de fondo: invertir la dirección del FK

Hoy el vínculo entrada↔compra vive en `inbound_orders.purchase_id` — **un FK único hacia UNA
compra**. `purchases` no tiene ninguna columna que apunte de vuelta (verificado: el enrich de la
decisión #80 resuelve el sentido compra→entrada con una consulta por página, no con una columna).

Una entrada con N compras exige mover el vínculo al otro lado: `purchases.inbound_order_id`. Eso es
lo más invasivo del ciclo, y arrastra:

| Qué | Dónde | Por qué |
|---|---|---|
| Estado derivado | `display_status_of()` + su espejo SQL en `get_multi` | Hoy lee `order.purchase` (una). Con N compras el estado deja de ser binario (ver P3). El test de paridad entre ambos es el guardarraíl. |
| Guard D7b | `purchase.cancel(from_inbound=)` | "Anule desde la orden #N" se multiplica por N. |
| Anulación en cascada | `inbound_order.annul()` | Hoy cancela la única compra registrada y aborta con 400 si está liquidada. Con N compras aparece el caso mixto: unas liquidadas, otras no. |
| Enrich B1 | `PurchaseResponse.inbound_order_id/number` | Se simplifica: pasa a ser una columna en vez de una consulta por página. |
| Auditoría C-5 | `willard_confirm_audit` | Solo willard, no se toca. |
| Comisión del recolector | `purchase.liquidate()` (#83) | `source_id` apunta a la entrada; con N liquidaciones depende de P2. |

### 3.2 Estructura de datos

- `inbound_orders.third_party_id` es **NOT NULL**. Pasa a nullable, o se conserva como "proveedor por
  defecto de la entrada" (lo que además da gratis el botón *"todas estas líneas van al mismo
  proveedor"* que Daniel prometió: la cabecera es el default, la línea lo pisa).
- Nace `inbound_order_lines.third_party_id`, nullable, con *fallback* a la cabecera.
- La derivación deja de crear una `PurchaseCreate` y pasa a agrupar las líneas por proveedor y crear
  una por grupo, todas en la misma transacción.

### 3.3 Lo que NO se toca

Retenciones (#75/#79), costo promedio, kg, fórmulas, tarifas, P&L, traslados, y todo el camino
Willard. Cada compra derivada sigue siendo una compra normal: sus retenciones, su saldo de proveedor
y su liquidación funcionan tal cual hoy, solo que ahora hay varias.

### 3.4 Superficie de frontend

Las 4 páginas del módulo de Entradas (~2.300 líneas) más la de liquidación. El grueso está en el
formulario: el selector de proveedor baja a la línea y aparece el interruptor
*"un solo proveedor / varios"*.

---

## 4. Por qué conviene hacerlo ahora y no en tres meses

La migración **no es puramente aditiva** (mover un FK y aflojar un NOT NULL exige backfill), pero
`inbound_orders` es una tabla exclusiva de SAC, con **cero filas en las otras organizaciones** y con
apenas unos días de datos reales. El backfill de hoy son unas pocas filas; el de dentro de tres meses
son miles, con compras liquidadas, retenciones aplicadas y pagos hechos encima.

Es la ventana más barata que va a haber.

---

## 5. Siguiente paso

Mandarle a Johana las cinco preguntas. Con P1 y P3 contestadas se puede escribir el plan de verdad;
las otras tres afinan detalles pero no cambian la arquitectura.
