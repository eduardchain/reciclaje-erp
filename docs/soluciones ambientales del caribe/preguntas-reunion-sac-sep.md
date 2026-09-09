# Preguntas para la reunión SAC (semana del 9-sep-2026) — versión auditada

Auditada el 9-sep contra `control-cambios-requerimientos.md`, `requerimientos-funcionales.md` v0.5, el briefing del 11-ago y las transcripciones del 24 y 28-ago. De 13 preguntas quedan **4**; las otras 9 ya tenían respuesta (sección E, con la cita) o son decisión nuestra.

## A. Las cuatro que sí hay que hacer

| # | Pregunta | Responde | Por qué está abierta | Qué decide |
|---|---|---|---|---|
| 1 (Q-B) | Lo que le deben a Willard en plomo (y lo que planta le debe a Circunvalar): ¿lo quieren ver en el **balance, en pesos**, o solo en kilos? Si en pesos, ¿a qué valor el kilo? | Hugo | Nadie lo ha dicho. Hugo habla de "deuda" y "plomo a pagar" (24-ago), pero nunca de cómo se valora | Dónde aterriza el valor del plomo que sale en un abono (#100 D13). El flujo físico no cambia |
| 2 (Q-34) | El plomo de baterías que SAC compra y el de Willard (que entra a $0) se funden juntos. ¿Quieren ver aparte cuánto ganan con el plomo **propio**? | Hugo + Johana | Salió en las pruebas del 9-sep; ninguna fuente lo toca | Dos materiales (crudo propio / crudo Willard) o aceptar la mezcla y avisar que el costo promedio se diluye |
| 3 | Fuera de la comisión de Green Loop, ¿hay algún otro cargo por compra — flete del camión, pesaje, descargue? Y si hay flete y el camión trae varios proveedores, ¿cómo lo reparten? | Johana | #93 lo difirió "para consultar en reunión" y no aparece en ninguna reunión desde entonces (cero menciones de flete de compra el 3, 11 y 12-ago) | Si no hay: se cierra sin código. Si hay: regla de reparto (matemática nueva) |
| 4 | Confirmar en una frase (no preguntar): *"planta cobra $1.500 por kilo por fundir, venga el material de Circunvalar o lo mande Willard directo"* | Hugo | Ya está dicho dos veces (28-ago y 4-sep) — solo se dice en voz alta para que lo corrija si no es así | Si lo corrige, se reabre Q-29 |

## B. Pedidos pendientes (no son preguntas, son cosas que faltan por llegar)

- **Tabla del molino** (qué sale de cada material que entra: plomo, plástico, ácido, merma). Pedida el 11-ago; el dueño del dato es **Erwin**, no Johana. Sin ella no se preconfigura el molino (#99).
- **Los informes de Johana** tal como se los entrega a SAC. Ella los ofreció el 11-ago (briefing §3.1: "lo más valioso de la reunión"); no hay registro de que hayan llegado.

## C. Propuesta para cerrar la reunión (no pregunta)

Hugo, 28-ago 00:33:23: *"sin ya ponerlo en marcha lo que son las entradas, todo el movimiento del inventario, ver cómo está haciendo el traslado […] empezarlo a trabajar ya […] ya no dejar de utilizarlo hasta que lo dejemos estandarizado"*. Propuesta: arrancan con **Entradas + traslados + saldos a Juan Mina** apenas salga el tren de develop; **Salidas de plomo** cuando cerremos crisol/puro (con las respuestas 1 y 2 de arriba).

## D. Decisiones nuestras (se informan, no se preguntan)

- **Listas por proveedor (Q-26)**: el día que se enciendan, todos los proveedores arrancan con la lista general y Hugo los reparte después. El sembrado ya lo hace en una sola operación (#98 Q-26).
- **Dos códigos de tarifa para la misma maquila de planta**: unificar en Config (sale de la respuesta 4).
- **Orden de captura del reparto en la Entrada** (material→proveedores, como está): se deja y se observa cómo lo usa Johana la primera semana; es reversible.
- **Bogotá**: sin cuenta de kilos (ver Q-35 abajo).

## E. Ya respondidas — no volver a preguntar

| Pregunta que iba a hacerse | Quién la respondió y dónde |
|---|---|
| Q-29 ¿$1.500 es un solo precio o dos cobros? | Filas 1 y 5 de la tabla del registro: $1.500 al trasladar (Hugo 28-ago) y $1.500 a planta en el abono en materiales (Hugo 4-sep). Queda como la afirmación 4 de arriba |
| Q-30 ¿El margen de la venta queda entero en planta? | **No era pregunta, era un defecto nuestro.** Hugo 24-ago 00:38:22: *"le queda un ingreso a Johana allá por la venta […] y le abona la cantidad de kilogramos por el valor establecido planta"*, *"todo lo factura Johana"*. La venta la factura Circunvalar; el código la pone en Juan Mina. Corrección en el ciclo de planta |
| Q-33 ¿El dross del 13% es traslado a Circunvalar? | Johana 3-sep: vuelve al **horno grande** (en planta) y causa maquila otra vez. Hugo 28-ago :395 dice lo mismo desde planta. No sale de planta: se modela, no se pregunta |
| Q-35 ¿Las baterías en Bogotá ya son deuda con Willard? | Johana, cuatro veces (26-jun, 11-ago "Bogotá es un proveedor, no una sede", 24-ago, 3-sep): **no** hasta Circunvalar. La §2.3 quedó vieja; la regla de precedencia lo cierra |
| Crisol (a) horno + crisol suman la deuda | Johana 3-sep (fila 7: intersede = horno grande + crisol) |
| Crisol (b) pasar al crisol no mueve nada | Hugo 28-ago (fila 9) |
| Crisol (c) ¿quién cobra los $300 y cuándo? | Dirección: spec §5 validado el 2-jul (*"gasto sede origen / ingreso JM"* = planta a Circunvalar); momento: al vender el puro, Hugo 28-ago tres veces (fila 8) |
| Crisol (d) el dross del crisol vuelve al horno | Johana 3-sep (fila 10) |
| Q-26 ¿todos con la general al encender las listas? | Es decisión de operación nuestra, no de Hugo (sección D) |
| ¿Cuándo empiezan? | Hugo 28-ago 00:33:23: ya, con Entradas y traslados, corrigiendo sobre la marcha (sección C) |
| ¿Material por material o proveedor por proveedor? | Reversible y de bajo costo: se decide observando, no preguntando (sección D) |
| Recolector, % de plomo por material, PLO-LIN = crudo, la venta sale de planta, remisión manual, dos consecutivos, tarifas vigentes | Ya cerradas antes de esta hoja (#83, #95, Q-31, Q-32, Q-27 de salidas, #105, Johana 3-sep) |
