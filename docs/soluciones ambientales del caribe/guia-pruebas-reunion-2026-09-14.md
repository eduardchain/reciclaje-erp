# Guía de pruebas con el cliente — Salidas de Plomo, Traslados y Crisol

Reunión con Johana y Hugo. Cubre todo lo construido desde la demo del 28 de agosto: el módulo Salidas de Plomo completo (tres tipos, dos consecutivos, sin paso de revisión, remisión obligatoria, plomo crudo y puro), los traslados entre sedes con maquila, y el ciclo de planta (horno y crisol, retorno de dross, venta de puro, y la venta facturada por Circunvalar).

## Cómo usar esta guía

- Entorno: ambiente de pruebas con datos de prueba, no producción. Usuario hugo@sac.com. Nada de lo que se haga aquí afecta la operación real.
- El ambiente arranca limpio, con saldos iniciales redondos cargados como se cargarían el día del arranque real: saldos de kilos por movimiento manual auditado e inventario por ajuste de carga inicial. Todos los consecutivos empiezan en 1.
- Los pasos van en orden y con cantidades fijas. Si se siguen las cantidades, cada valor esperado de esta guía coincide al peso. Si el cliente prefiere otras cantidades, la columna "por qué" de cada tabla dice la regla para recalcular.
- Después de cada paso hay cuatro lugares donde mirar: Plomo (kg) (las cuatro tarjetas y el estado de cuenta de INTERSEDE), Tesorería (los movimientos que nacen), Salidas de Plomo (el documento), y al final Reportes, Estado de Resultados con el selector de sede.
- Ningún paso de esta guía debe producir avisos ámbar. Si aparece uno, es tema de conversación, no de arreglo.

## Los conceptos en una página

- Hay dos deudas en plomo con Willard y son de dueños distintos. Las baterías llegan a Circunvalar (cuenta Willard Baterías CV). Los drosses los manda Willard derecho a planta, sin pasar por Johana (cuenta Willard Drosses). Ese fue el nudo que destrabó el módulo.
- Intersede es la deuda de planta con Circunvalar. Nace al trasladar material de Circunvalar a Juan Mina (en kilos de plomo estimados por la fórmula de cada material). Baja con una venta y con un abono a batería. No baja con un abono a material, porque ese material nunca pasó por Circunvalar.
- Intersede tiene dos etapas: en horno (plomo crudo) y en crisol (plomo en refinación). Es una sola deuda; las dos etapas siempre suman el total. El traslado a crisoles y el retorno de dross mueven plomo entre etapas sin tocar la deuda ni el inventario.
- La maquila interna de $1.500 por kilo se causa una sola vez, al trasladar. Se causa otra vez en el retorno de dross, porque ese plomo se funde de nuevo. Es un cobro interno: nace como un par (gasto en Circunvalar, ingreso en Juan Mina), sin caja y sin tercero, y solo se ve en el P&L por sede. En el consolidado se cancela.
- Lo que Willard paga: en un abono, la maquila de $2.097 por kilo más el flete de $37 por kilo. Eso queda como cuenta por cobrar a Willard, sin mover caja hasta que paguen. En una venta Willard no paga nada: el cliente paga el precio del plomo.
- Abono a planta: $1.500 por kilo, solo en el abono a material. Circunvalar factura la maquila de Willard y le abona a planta esa parte, porque los drosses se fundieron en planta sin haber pasado por Circunvalar. También es un par interno.
- Crudo y puro son dos productos. El crudo (PLO-LIN) sale en los tres tipos y descarga la etapa horno. El puro (PLO-PUR) solo se vende, descarga la etapa crisol y causa el diferencial de $300 por kilo que planta le cobra a Circunvalar por refinar.
- Quién factura: Circunvalar, siempre. Por eso en el P&L por sede una venta de plomo aparece en Circunvalar aunque el plomo salga físicamente de Juan Mina.
- El plomo que sale en un abono no es una venta: sale del inventario al costo y ese costo aparece en el P&L de Juan Mina como pérdida por ajuste de inventario. Es el precio de pagar una deuda en plomo.
- Consecutivos: las ventas y los abonos llevan numeración separada (Venta No. y Abono No.), como los lleva Hugo con Willard. La remisión es obligatoria porque es el número con el que se concilia. En salidas no hay paso de revisión: registrar y liquidar.

## Punto de partida (saldos iniciales del ambiente de pruebas)

| Cuenta o material | Saldo inicial | Qué es |
|---|---|---|
| Willard Baterías CV | 1.000 kg | Plomo que Circunvalar le debe a Willard por baterías recibidas |
| Willard Drosses | 1.000 kg | Plomo que planta le debe a Willard por drosses recibidos |
| Willard total | 2.000 kg | Suma de las dos cuentas |
| Intersede | 1.000 kg | Deuda de planta con Circunvalar |
| En horno (crudo) | 1.000 kg | Etapa horno de intersede |
| En crisol | 0 kg | Etapa crisol de intersede |
| PLO-LIN en Juan Mina | 2.000 kg | Plomo crudo en inventario, costo promedio $2.000 por kg |
| PLO-PUR en Juan Mina | 1.000 kg | Plomo puro en inventario, costo promedio $2.500 por kg |
| Baterías en Circunvalar | 0 unidades | Por eso el bloque 1 empieza con una Entrada |
| Tesorería y Estado de Resultados del día | en cero | Las cargas iniciales no pasan por el Estado de Resultados |

Tarifas vigentes: maquila interna $1.500 por kg, diferencial crisol $300 por kg, maquila Willard $2.097 por kg, flete planta a Willard $37 por kg, abono a planta $1.500 por kg. Fórmula de BAT-G1: 7,3 kg de plomo por batería. Tolerancia de traslados: 5%.

## Bloque 1. Entrada Willard de baterías en Circunvalar

Concepto: la deuda con Willard nace en Circunvalar, en kilos de plomo estimados por fórmula. Entra material sin proveedor y sin plata.

Pasos: Entradas, Nueva Entrada. Tipo Willard, Tipo Willard Postconsumo, sede Circunvalar. El tercero queda fijo en Willard S.A. Conductor y placa (se pueden crear al vuelo). Material BAT-G1, 100 unidades, peso de báscula 1.800 kg (obligatorio antes de revisar). Guardar. Luego Revisar y luego Liquidar.

| Qué mirar | Antes | Después | Por qué |
|---|---|---|---|
| Número del documento | | Entrada No. 1 | |
| Willard Baterías CV | 1.000 kg | 1.730 kg | 100 baterías por 7,3 kg cada una = 730 kg |
| Willard total | 2.000 kg | 2.730 kg | Solo cambia la cuenta de baterías |
| Intersede | 1.000 kg | 1.000 kg | Nada se ha trasladado todavía |
| Inventario BAT-G1 en Circunvalar | 0 | 100 unidades | Entra a inventario al costo promedio vigente (en este ambiente a $0: no hay compras previas de BAT-G1) |
| Tesorería | sin movimientos | sin movimientos | Willard no vende las baterías: no hay compra ni pago |

## Bloque 2. Traslado Circunvalar a Juan Mina en dos pasos

Concepto: aquí nace la deuda de planta con Circunvalar y se causa la maquila interna una sola vez. Como el material se pesa al salir y al llegar, el traslado tiene dos pasos y una tolerancia del 5%.

Paso 2a, despacho: Traslados, Nuevo Traslado. Bodega origen Circunvalar, bodega destino Juan Mina. El aviso índigo dice que va en dos pasos. Material BAT-G1, 100 unidades. Despachar.

| Qué mirar | Antes | Después del despacho | Por qué |
|---|---|---|---|
| Número del documento | | Traslado No. 1 | |
| Inventario BAT-G1 en Circunvalar | 100 | 0 | Sale a la bodega de tránsito |
| Inventario BAT-G1 en tránsito (bodega Juan Mina - Transito) | 0 | 100 | Todavía no llegó a planta |
| Intersede | 1.000 kg | 1.000 kg | La deuda nace al recibir, no al despachar |
| Tesorería | nada | nada | La maquila se causa al recibir |

Paso 2b, recepción: Traslados, bandeja, Recibir. Cantidad recibida 100. Recibir.

| Qué mirar | Antes | Después de recibir | Por qué |
|---|---|---|---|
| Inventario BAT-G1 en Juan Mina | 0 | 100 unidades | Llegó a planta |
| En horno (crudo) | 1.000 kg | 1.730 kg | 100 recibidas por 7,3 = 730 kg entran a la etapa horno |
| Intersede | 1.000 kg | 1.730 kg | Horno 1.730 más crisol 0 |
| Willard total | 2.730 kg | 2.730 kg | Trasladar no cambia la deuda con Willard |
| Tesorería, Maquila Intersede (gasto sede origen) | nada | $1.095.000, tipo gasto (Circunvalar) | 730 kg por $1.500 |
| Tesorería, Maquila Intersede (ingreso sede destino) | nada | $1.095.000, tipo ingreso (Juan Mina) | Espejo del anterior, sin cuenta ni tercero |

En Tesorería el par se ve como dos movimientos con la misma descripción y el mismo monto: el tipo dice cuál es el gasto (Circunvalar) y cuál el ingreso (Juan Mina). Tesorería no imprime la sede; donde se ve es en el Estado de Resultados con el selector de sede.

Si quieren probar la tolerancia: recibir 97 en vez de 100. Queda dentro del 5%, la merma de 3 unidades sale como ajuste de inventario, y los kilos y la maquila se calculan sobre lo recibido (97 por 7,3 = 708,1 kg, maquila $1.062.150). Si reciben 90, el traslado queda retenido con una tarea de discrepancia. Ojo: si prueban esto, los saldos de aquí en adelante bajan 21,9 kg respecto a la guía.

Variante que vale la pena mostrar: un traslado de Circunvalar a Circunvalar Molino es la misma sede, así que se completa en un solo paso, sin tránsito, sin kilos y sin maquila.

## Bloque 3 (opcional). Transformar baterías en plomo crudo

Concepto: la conversión física se registra como transformación, en Juan Mina. No toca las cuentas de kilos ni la plata entre sedes. El sistema no exige que cuadre en cantidad porque cambia de unidad (unidades a kilos); la receta de cuánto plomo y cuántos subproductos salen es la tabla que falta por parte de Erwin.

Pasos: Inventario, Transformaciones, Nueva. Origen Juan Mina, 100 BAT-G1. Destinos en Juan Mina: PLO-LIN 730 kg y los demás productos que Erwin defina. Una transformación con origen y destino en sedes distintas es rechazada: para eso está el traslado.

Este bloque se puede saltar. Ya hay 2.000 kg de PLO-LIN en Juan Mina para los bloques siguientes, y los valores de esta guía asumen que se salta (si se hace, el inventario de PLO-LIN queda 730 kg por encima de lo que dicen las tablas y el costo promedio del crudo cambia).

## Bloque 4. Salidas de Plomo, los tres tipos

Todas salen de Juan Mina con plomo crudo PLO-LIN. En kilos no se pide báscula: la cantidad ya es el peso. La remisión es obligatoria. Después de registrar, en el detalle se digita el precio (solo en venta) y se liquida.

### 4a. Abono a batería, 300 kg

Concepto: es un pago en plomo que salda dos deudas encadenadas a la vez. Planta le devuelve a Circunvalar y Circunvalar le devuelve a Willard, por la misma cantidad.

Pasos: Salidas de Plomo, nueva salida. Tipo Abono a batería, bodega Juan Mina, tercero Willard S.A, remisión AB-1001. Material PLO-LIN, 300 kg. Registrar. En el detalle, Liquidar.

| Qué mirar | Antes | Después | Por qué |
|---|---|---|---|
| Número del documento | | Abono No. 1 | Consecutivo propio de abonos |
| Willard Baterías CV | 1.730 kg | 1.430 kg | Se le devolvieron 300 kg a Willard |
| En horno (crudo) | 1.730 kg | 1.430 kg | Planta le devolvió los mismos 300 kg a Circunvalar |
| Intersede | 1.730 kg | 1.430 kg | Etapa horno bajó |
| Willard total | 2.730 kg | 2.430 kg | |
| Tesorería, Maquila a Willard | nada | $629.100, tercero Willard | 300 kg por $2.097, cuenta por cobrar sin caja |
| Tesorería, Flete a Willard | nada | $11.100, tercero Willard | 300 kg por $37 |
| Abono a planta | | $0 | Ese plomo pasó por Circunvalar: la maquila interna ya se causó al trasladar |
| Inventario PLO-LIN en Juan Mina | 2.000 kg | 1.700 kg | Sale valorado al costo promedio |
| Inventario, Ajustes (y Estado de Resultados de Juan Mina) | | disminución de 300 kg a $2.000: pérdida de $600.000 | 300 kg por $2.000 de costo: el plomo salió sin venta |

### 4b. Abono a material, 500 kg

Concepto: los drosses llegaron derecho a planta, así que Circunvalar nunca estuvo en esa cadena. Baja solo la deuda de drosses, intersede no se toca, y Circunvalar le abona a planta $1.500 por kilo de los $2.097 que factura.

Pasos: nueva salida, tipo Abono a material, Juan Mina, Willard S.A, remisión AB-1002. PLO-LIN 500 kg. Registrar y Liquidar.

| Qué mirar | Antes | Después | Por qué |
|---|---|---|---|
| Número del documento | | Abono No. 2 | Mismo consecutivo que el abono anterior |
| Willard Drosses | 1.000 kg | 500 kg | Se le devolvieron 500 kg a Willard por drosses |
| Intersede | 1.430 kg | 1.430 kg | Circunvalar no participó: no cambia |
| Willard total | 2.430 kg | 1.930 kg | |
| Tesorería, Maquila a Willard | | $1.048.500 | 500 kg por $2.097 |
| Tesorería, Flete a Willard | | $18.500 | 500 kg por $37 |
| Tesorería, Abono a planta (par interno) | nada | $750.000 gasto en Circunvalar e ingreso en Juan Mina | 500 kg por $1.500 |
| Inventario PLO-LIN en Juan Mina | 1.700 kg | 1.200 kg | |
| Inventario, Ajustes (y Estado de Resultados de Juan Mina) | | disminución de 500 kg a $2.000: pérdida de $1.000.000 | 500 kg por $2.000 de costo |

### 4c. Venta de plomo crudo, 100 kg

Concepto: la venta también le devuelve plomo a Circunvalar (baja intersede), nace una venta normal en el módulo de Ventas y Willard no paga nada. La factura es de Circunvalar.

Pasos: nueva salida, tipo Venta, Juan Mina, cliente PRUEBA Cliente Nacional, remisión V-2001. PLO-LIN 100 kg. Registrar. En el detalle, precio unitario $4.000 (o total $400.000, el sistema acepta los dos). Liquidar.

| Qué mirar | Antes | Después | Por qué |
|---|---|---|---|
| Número del documento | | Venta No. 1 | Consecutivo propio de ventas |
| En horno (crudo) | 1.430 kg | 1.330 kg | Crudo descarga la etapa horno |
| Intersede | 1.430 kg | 1.330 kg | |
| Willard total | 1.930 kg | 1.930 kg | Una venta a un cliente no toca a Willard |
| Maquila y flete facturados | | $0 | En una venta Willard no paga nada |
| Ventas, venta derivada | | $400.000 de ingreso, $200.000 de costo, liquidada | 100 kg a $4.000, costo promedio $2.000. Nace y se liquida sola; el link está en el detalle. En Ventas muestra bodega Juan Mina (de donde salió el plomo); en el Estado de Resultados por sede cuenta en Circunvalar, que es quien factura |
| Inventario PLO-LIN en Juan Mina | 1.200 kg | 1.100 kg | |

Prueba negativa útil aquí: intentar vender PLO-LIN desde el módulo de Ventas. La pantalla no lo ofrece y el servidor lo rechaza con un mensaje que manda a Salidas de Plomo. Vender plomo por fuera del módulo dejaría la deuda con Circunvalar colgada para siempre.

### Resumen de efectos por tipo de salida

| Tipo | Baja Willard | Baja intersede | Willard paga | Par interno | Nace venta |
|---|---|---|---|---|---|
| Venta (crudo) | No | Sí, etapa horno | Nada | No | Sí |
| Venta (puro) | No | Sí, etapa crisol | Nada | Diferencial crisol $300 por kg | Sí |
| Abono a batería | Sí, cuenta baterías | Sí, etapa horno, misma cantidad | Maquila $2.097 más flete $37 por kg | No | No |
| Abono a material | Sí, cuenta drosses | No | Maquila $2.097 más flete $37 por kg | Abono a planta $1.500 por kg | No |

## Bloque 5. El ciclo de planta: crisol

### 5a. Traslado a crisoles, 200 kg

Concepto: el crudo pasa del horno grande al crisol para refinarlo. No sale de planta ni cambia de dueño; solo cambia de etapa. Solo acepta materiales marcados como plomo crudo.

Pasos: Salidas de Plomo, tab Crisol, Nuevo documento de crisol. Tarjeta Traslado a crisoles, planta Juan Mina (fija), material PLO-LIN, 200 kg. La vista previa muestra el efecto antes de registrar. Registrar.

| Qué mirar | Antes | Después | Por qué |
|---|---|---|---|
| Número del documento | | Crisol No. 1 | |
| En horno (crudo) | 1.330 kg | 1.130 kg | Sale de la etapa horno |
| En crisol | 0 kg | 200 kg | Entra a la etapa crisol |
| Intersede | 1.330 kg | 1.330 kg | La deuda no cambia |
| Inventario y Tesorería | | sin cambio | Es control de dónde está el plomo |
| Estado de cuenta de INTERSEDE | | dos filas de signo contrario, columna Etapa | Menos 200 en horno, más 200 en crisol |

### 5b. Retorno de dross al horno, 20 kg

Concepto: el crisol deja un residuo (más o menos el 10% de lo que entró) que vuelve al horno grande y se funde otra vez. Como planta lo procesa de nuevo, cobra otra vez la maquila del horno. Los kilos de dross se digitan a mano: los pesa Erwin al sacarlos.

Pasos: Nuevo documento de crisol, tarjeta Retorno de dross al horno, material DROSS-CRI, 20 kg. Registrar.

| Qué mirar | Antes | Después | Por qué |
|---|---|---|---|
| Número del documento | | Crisol No. 2 | |
| En crisol | 200 kg | 180 kg | Sale del crisol |
| En horno (crudo) | 1.130 kg | 1.150 kg | Vuelve al horno |
| Intersede | 1.330 kg | 1.330 kg | Sin cambio |
| Detalle del documento, Maquila del reproceso | | $30.000 | 20 kg por $1.500 |
| Tesorería, Maquila Intersede | nada | par de $30.000, gasto Circunvalar e ingreso Juan Mina | Misma categoría que la maquila del traslado |

### 5c. Venta de plomo puro, 100 kg

Concepto: el puro solo se vende. Descarga la etapa crisol, nace la venta normal facturada por Circunvalar, y planta le cobra a Circunvalar $300 por kilo por refinar, encima de los $1.500 que ya cobró al fundir.

Pasos: Salidas de Plomo, nueva salida, tipo Venta, Juan Mina, cliente PRUEBA Cliente Nacional, remisión V-2002. Material PLO-PUR, 100 kg. Registrar. Precio unitario $5.000. Liquidar.

| Qué mirar | Antes | Después | Por qué |
|---|---|---|---|
| Número del documento | | Venta No. 2 | |
| En crisol | 180 kg | 80 kg | Puro descarga la etapa crisol |
| En horno (crudo) | 1.150 kg | 1.150 kg | No se toca |
| Intersede | 1.330 kg | 1.230 kg | |
| Detalle, Diferencial crisol | | $30.000 | 100 kg por $300 |
| Tesorería, Maquila Intersede (categoría Crisol Refinación) | | par de $30.000, gasto Circunvalar e ingreso Juan Mina | |
| Ventas, venta derivada | | $500.000 de ingreso, $250.000 de costo | 100 kg a $5.000, costo promedio $2.500 |
| Inventario PLO-PUR en Juan Mina | 1.000 kg | 900 kg | |

Prueba negativa útil: en un abono, la pantalla no ofrece PLO-PUR. El puro no se abona, se vende (así lo describió Hugo). Y si intentan vender puro sin haber pasado plomo al crisol, el sistema deja hacerlo pero avisa que la etapa crisol queda en negativo y dice qué documento falta.

## Bloque 6. Cierre: cómo debe quedar todo

### Plomo (kg)

| Tarjeta | Valor esperado | Cuenta |
|---|---|---|
| Willard | 1.930 kg | Baterías CV 1.430 más Drosses 500 |
| Intersede | 1.230 kg | Horno 1.150 más crisol 80 |
| En horno (crudo) | 1.150 kg | 1.000 inicial, más 730 del traslado, menos 300 del abono, menos 100 de la venta de crudo, menos 200 al crisol, más 20 del retorno |
| En crisol | 80 kg | 200 que entraron, menos 20 de dross, menos 100 vendidos como puro |

Comprobación de intersede: 1.000 inicial más 730 recibidos, menos 300 del abono a batería, menos 100 de la venta de crudo, menos 100 de la venta de puro = 1.230. Los documentos de crisol no cambian el total.

En el estado de cuenta de INTERSEDE se ve la historia completa con la columna Etapa, y la última fila coincide con la tarjeta.

### Inventario en Juan Mina

| Material | Inicial | Final | Cuenta |
|---|---|---|---|
| PLO-LIN | 2.000 kg | 1.100 kg | Menos 300 y 500 de los abonos, menos 100 de la venta de crudo |
| PLO-PUR | 1.000 kg | 900 kg | Menos 100 de la venta de puro |

### Tesorería y ajustes de inventario

| Grupo | Movimientos | Total |
|---|---|---|
| Cuenta por cobrar a Willard (sin caja) | Maquila $629.100, flete $11.100, maquila $1.048.500, flete $18.500 | $1.707.200, el saldo de Willard sube ese monto |
| Pares internos Circunvalar a Juan Mina | Traslado $1.095.000, abono a planta $750.000, retorno de dross $30.000, diferencial crisol $30.000 | $1.905.000 en cada lado |
| Ajustes de inventario por los abonos (en Inventario, Ajustes, no en Tesorería) | Abono a batería $600.000, abono a material $1.000.000 | $1.600.000 de pérdida en Juan Mina |

Un par interno no se puede anular desde Tesorería: se anula desde el documento que lo causó (traslado, salida o documento de crisol).

### Estado de Resultados por sede, solo el día de la prueba

Todos los pasos deben hacerse el mismo día para que el rango "hoy" los recoja todos. Las cargas iniciales no aparecen.

| Línea | Circunvalar | Juan Mina | Consolidado |
|---|---|---|---|
| Ingresos por ventas | $900.000 | $0 | $900.000 |
| Costo de ventas | $450.000 | $0 | $450.000 |
| Ingresos por servicios (maquila y flete a Willard) | $1.707.200 | $0 | $1.707.200 |
| Ajustes de inventario (costo de los abonos) | $0 | menos $1.600.000 | menos $1.600.000 |
| Maquila intersede, gasto | menos $1.905.000 | | no aparece |
| Maquila intersede, ingreso | | $1.905.000 | no aparece |
| Utilidad neta del día | $252.200 | $305.000 | $557.200 |

Comprobaciones: Circunvalar = 900.000 menos 450.000 más 1.707.200 menos 1.905.000 = 252.200. Juan Mina = 1.905.000 menos 1.600.000 = 305.000. Consolidado = 900.000 menos 450.000 más 1.707.200 menos 1.600.000 = 557.200, y 252.200 más 305.000 = 557.200. Las ventas de plomo aparecen en Circunvalar aunque el plomo salió de Juan Mina, porque Circunvalar factura. Las dos líneas de maquila se cancelan en el consolidado.

## Reglas para la operación

- Todo el plomo sale por Salidas de Plomo. El módulo de Ventas no ofrece plomo marcado como crudo o puro y lo rechaza si llega por otra vía.
- El retorno de dross no se registra como traslado. Si se registrara como traslado Juan Mina a Circunvalar y de vuelta, el sistema cobraría maquila dos veces.
- Para vender puro primero se registra el traslado a crisoles. Si no, la etapa crisol queda en negativo y el sistema avisa.
- Los abonos solo llevan crudo. El puro se vende.
- Toda salida sale de Juan Mina. Una salida desde otra sede descargaría una deuda que no existe allá y el sistema la rechaza.
- La remisión es obligatoria y es el número de Willard. Sin ella no se avanza.
- Una transformación no cruza de sede. Entre sedes va el traslado, que es el que pesa dos veces y causa la maquila.

## Para cerrar con ustedes

Preguntas que siguen abiertas (solo estas; el resto ya está confirmado en reuniones anteriores):

1. Para Hugo. Lo que le deben a Willard en plomo, y lo que planta le debe a Circunvalar: ¿lo quieren ver en el balance en pesos, o solo en kilos? Si en pesos, ¿a qué valor el kilo? Esto decide dónde aterriza el valor del plomo que sale en un abono.
2. Para Hugo y Johana. El plomo de baterías que SAC compra y el de Willard (que entra a $0) se funden juntos. ¿Quieren ver aparte cuánto ganan con el plomo propio? Si sí, serían dos materiales de crudo.
3. Para Johana. Fuera de la comisión de Green Loop, ¿hay algún otro cargo por compra: flete del camión, pesaje, descargue? Y si hay flete y el camión trae varios proveedores, ¿cómo lo reparten?
4. Para Hugo, solo confirmar en voz alta: planta cobra $1.500 por kilo por fundir, venga el material de Circunvalar o lo mande Willard directo.

Pendientes por recibir: la tabla del molino (qué sale de cada material que entra), cuyo dueño es Erwin; y los informes de Johana tal como se los entrega hoy a SAC.

Propuesta para arrancar: Entradas, traslados y saldos a Juan Mina apenas salga esta versión; Salidas de Plomo cuando cerremos las preguntas 1 y 2.
