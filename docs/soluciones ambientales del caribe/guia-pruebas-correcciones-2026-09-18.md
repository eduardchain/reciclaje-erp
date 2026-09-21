# Guía de pruebas — correcciones del cierre del 18 de septiembre

Complementa la guía del 14 de septiembre. Solo cubre lo que cambió después de la reunión del 16 y del cierre del 18: el reparto a planta en los abonos, el retorno de dross y el inventario del crisol. Los bloques 1, 2, 3 y 4c de la guía anterior no cambian.

Se parte del mismo punto de partida de la guía anterior y se hacen los pasos en el mismo orden y el mismo día.

## Qué cambió, en una página

- Abono a baterías: Circunvalar ahora le reparte a planta 566 por kilo, fijo. A Willard se le factura igual (2.097 de maquila más 37 de flete). Circunvalar se queda con 1.531 de la maquila y con todo el flete.
- Abono a materiales: el reparto a planta pasa de 1.500 a 1.248 por kilo. Circunvalar se queda con 849 de la maquila y con todo el flete.
- Retorno de dross: se digitan los kilos de dross. El crisol baja esos kilos. El horno sube solo el plomo que contienen, que es el 70 por ciento. La maquila del reproceso se cobra sobre ese plomo. La deuda total de planta con Circunvalar baja la diferencia, y es lo esperado.
- El crisol ahora mueve inventario. El traslado a crisoles saca plomo crudo y mete plomo puro, kilo por kilo. El retorno de dross saca plomo puro y mete plomo crudo por el 70 por ciento; el resto es merma.
- Ya no se registra aparte una transformación entre plomo crudo y plomo puro. El sistema la rechaza y manda al documento de crisol.
- En Salidas de Plomo hay un resumen por tipo de salida, para ver separado lo que dejan las baterías y lo que dejan los materiales.
- Las dos tarifas de reparto a planta ahora se ven y se cambian en Configuración, Tarifas.

Tarifas vigentes después del cambio: reparto a planta en abono a baterías 566 por kg; reparto a planta en abono a materiales 1.248 por kg. Las demás no cambian. Fórmula del dross de crisol (DROSS-CRI): 70 por ciento de plomo.

## 4a. Abono a batería, 300 kg

Mismos pasos de la guía anterior. Cambia una sola fila.

| Qué mirar | Antes del cambio | Ahora | Por qué |
|---|---|---|---|
| Tesorería, reparto a planta (par interno) | nada | 169.800 de gasto en Circunvalar y de ingreso en Juan Mina | 300 kg por 566 |
| Maquila y flete a Willard | 629.100 y 11.100 | igual | El reparto es interno: a Willard no se le cambia nada |
| Kilos e inventario | | igual | |

Prueba negativa: si en Configuración, Tarifas no existe la tarifa de reparto de baterías, la salida se liquida, los kilos bajan y el sistema avisa que a planta no se le repartió nada.

## 4b. Abono a material, 500 kg

| Qué mirar | Antes del cambio | Ahora | Por qué |
|---|---|---|---|
| Tesorería, reparto a planta (par interno) | 750.000 | 624.000 | 500 kg por 1.248 |
| Maquila y flete a Willard | 1.048.500 y 18.500 | igual | |
| Kilos e inventario | | igual | |

## 5a. Traslado a crisoles, 200 kg

Pasos: Salidas de Plomo, tab Crisol, Nuevo documento de crisol. Traslado a crisoles, PLO-LIN, 200 kg. La vista previa muestra ahora también el efecto sobre el inventario.

| Qué mirar | Antes | Después | Por qué |
|---|---|---|---|
| En horno (crudo) | 1.330 kg | 1.130 kg | Igual que antes |
| En crisol | 0 kg | 200 kg | Igual que antes |
| Intersede | 1.330 kg | 1.330 kg | El traslado a crisoles no cambia la deuda |
| Inventario PLO-LIN en Juan Mina | 1.100 kg | 900 kg | Nuevo: sale el crudo |
| Inventario PLO-PUR en Juan Mina | 1.000 kg | 1.200 kg | Nuevo: entra como puro, kilo por kilo |
| Costo promedio de PLO-PUR | 2.500 | 2.416,67 | Los 200 kg entran al costo del crudo (2.000). El valor total del inventario no cambia |
| Detalle del documento | | sección Efecto sobre el inventario, con el número de la transformación | La transformación pertenece al documento |

Prueba negativa: abrir esa transformación en Inventario, Transformaciones e intentar anularla. El sistema la rechaza y dice desde qué documento de crisol se anula.

Prueba negativa: en Inventario, Transformaciones, intentar una transformación nueva de PLO-LIN a PLO-PUR. El sistema la rechaza y manda a Salidas de Plomo, Crisol.

## 5b. Retorno de dross al horno, 20 kg

Pasos: Nuevo documento de crisol, Retorno de dross al horno. El selector de material solo ofrece materiales con porcentaje de plomo (DROSS-CRI). Se digitan 20 kg de dross. La vista previa muestra 14 kg de plomo.

| Qué mirar | Antes | Después | Por qué |
|---|---|---|---|
| En crisol | 200 kg | 180 kg | Bajan los 20 kg de dross |
| En horno (crudo) | 1.130 kg | 1.144 kg | Suben 14 kg: el 70 por ciento de 20 |
| Intersede | 1.330 kg | 1.324 kg | Baja 6 kg: lo que el dross tiene que no es plomo |
| Detalle, maquila del reproceso | 30.000 | 21.000 | 14 kg por 1.500 |
| Tesorería, Maquila Intersede | par de 30.000 | par de 21.000 | |
| Inventario PLO-PUR en Juan Mina | 1.200 kg | 1.180 kg | Nuevo: salen 20 del crisol |
| Inventario PLO-LIN en Juan Mina | 900 kg | 914 kg | Nuevo: entran 14 al horno grande |
| Merma | | 6 kg, valorada en 14.500 | 6 kg por 2.416,67 |

## 5c. Venta de plomo puro, 100 kg

| Qué mirar | Antes del cambio | Ahora | Por qué |
|---|---|---|---|
| En crisol | 180 a 80 kg | igual | |
| Intersede | 1.330 a 1.230 kg | 1.324 a 1.224 kg | Arrastra los 6 kg del retorno |
| Diferencial crisol | 30.000 | igual | 100 kg por 300 |
| Costo de la venta | 250.000 | 241.667 | El costo promedio del puro bajó a 2.416,67 al entrar los 200 kg del crisol |
| Inventario PLO-PUR en Juan Mina | 1.000 a 900 kg | 1.180 a 1.080 kg | |

## Cierre: cómo debe quedar

### Plomo (kg)

| Tarjeta | Valor esperado | Cuenta |
|---|---|---|
| Willard | 1.930 kg | Sin cambio |
| Intersede | 1.224 kg | Horno 1.144 más crisol 80 |
| En horno (crudo) | 1.144 kg | 1.000 inicial, más 730 del traslado, menos 300 del abono, menos 100 de la venta de crudo, menos 200 al crisol, más 14 del retorno |
| En crisol | 80 kg | 200 que entraron, menos 20 de dross, menos 100 vendidos como puro |

Comprobación de intersede: 1.000 inicial, más 730 recibidos, menos 300 del abono a batería, menos 100 de la venta de crudo, menos 100 de la venta de puro, menos 6 del retorno de dross = 1.224.

### Inventario en Juan Mina

| Material | Inicial | Final | Cuenta |
|---|---|---|---|
| PLO-LIN | 2.000 kg | 914 kg | Menos 300 y 500 de los abonos, menos 100 de la venta de crudo, menos 200 al crisol, más 14 del retorno |
| PLO-PUR | 1.000 kg | 1.080 kg | Más 200 del crisol, menos 20 del retorno, menos 100 de la venta de puro |

### Pares internos Circunvalar a Juan Mina

| Movimiento | Valor |
|---|---|
| Traslado | 1.095.000 |
| Reparto a planta, abono a batería | 169.800 |
| Reparto a planta, abono a material | 624.000 |
| Retorno de dross | 21.000 |
| Diferencial crisol | 30.000 |
| Total en cada lado | 1.939.800 |

### Resumen por tipo (Salidas de Plomo, Resumen por tipo de salida)

| Tipo | Salidas | Kg plomo | Maquila facturada | Flete facturado | Reparto a planta | Queda en Circunvalar de lo facturado |
|---|---|---|---|---|---|---|
| Venta | 2 | 200 kg | 0 | 0 | 0 | 0 |
| Abono a batería | 1 | 300 kg | 629.100 | 11.100 | 169.800 | 470.400 |
| Abono a material | 1 | 500 kg | 1.048.500 | 18.500 | 624.000 | 443.000 |

La última columna no es una utilidad: no descuenta el costo del plomo entregado. En la fila de venta aparece además el diferencial de crisol a planta, 30.000.

### Estado de Resultados por sede, solo el día de la prueba

| Línea | Circunvalar | Juan Mina | Consolidado |
|---|---|---|---|
| Ingresos por ventas | 900.000 | 0 | 900.000 |
| Costo de ventas | 441.667 | 0 | 441.667 |
| Ingresos por servicios (maquila y flete a Willard) | 1.707.200 | 0 | 1.707.200 |
| Ajustes de inventario (costo de los abonos) | 0 | menos 1.600.000 | menos 1.600.000 |
| Merma de transformaciones (retorno de dross) | no aparece | no aparece | menos 14.500 |
| Maquila intersede, gasto | menos 1.939.800 | | no aparece |
| Maquila intersede, ingreso | | 1.939.800 | no aparece |
| Utilidad neta del día | 225.733 | 339.800 | 551.033 |

Comprobaciones: Circunvalar = 900.000 menos 441.667 más 1.707.200 menos 1.939.800 = 225.733. Juan Mina = 1.939.800 menos 1.600.000 = 339.800. Consolidado = 900.000 menos 441.667 más 1.707.200 menos 1.600.000 menos 14.500 = 551.033. La suma de las dos sedes da 565.533: la diferencia de 14.500 es la merma del retorno de dross, que hoy el Estado de Resultados muestra solo en el consolidado y no por sede.

## Reglas que cambian para la operación

- El paso entre plomo crudo y plomo puro se registra solo con el documento de crisol. No se registra además una transformación.
- En el retorno de dross se digitan kilos de dross, no kilos de plomo.
- Las tarifas de reparto a planta se cambian en Configuración, Tarifas. Un cambio aplica a las salidas que se liquiden después; las ya liquidadas no se tocan.
