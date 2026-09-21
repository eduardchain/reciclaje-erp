# Preguntas de cierre — reunión SAC 17-sep-2026 (con ejemplos)

> El estado permanente de cada pregunta vive en `inventario-preguntas-cliente.md` (Q-27, Q-33, Q-36 a Q-40). Esta hoja las desarrolla con un ejemplo numérico para que Johana y Hugo contesten sobre un caso concreto y no sobre una regla abstracta. Las citas y los minutos están en `control-cambios-requerimientos.md`, § *Reunión de pruebas 2026-09-16*.

Tarifas vigentes usadas en los ejemplos: maquila Willard $2.097/kg, flete planta–Willard $37/kg, maquila interna $1.500/kg (se causa al trasladar de Circunvalar a Juan Mina), abono a planta $1.500/kg (solo en abono a materiales), diferencial crisol $300/kg. Todo en kilos de plomo. Los ejemplos usan las mismas cantidades de la guía de pruebas (abono a batería 300 kg, abono a material 500 kg, retorno de dross 20 kg, traslado a crisoles 200 kg), así que se pueden mostrar en pantalla mientras se pregunta.

En cada tabla, la columna **Hoy en el sistema** es lo que está construido, y viene de respuestas anteriores de Hugo (28-ago y 4-sep). La columna **Johana, 16-sep** es lo que ella planteó en la reunión de pruebas, con Hugo presente. Donde no cuadran, se pide una sola respuesta por escrito.

---

## Resumen: las dos versiones vistas por kilo de plomo

| Por cada kilo de plomo | Hoy en el sistema | Johana, 16-sep |
|---|---|---|
| Abono a batería: recibe planta | 1.500 (al trasladar) + 0 (al facturar) = 1.500 | 1.500 (al trasladar) + 566 (al facturar) = 2.066 |
| Abono a batería: se queda Circunvalar de la maquila facturada | 2.097 | 2.097 - 566 = 1.531 |
| Abono a material: recibe planta | 1.500 | 1.248 |
| Abono a material: se queda Circunvalar | 2.097 - 1.500 = 597 | 749 |
| Abono a material: suma del reparto | 1.500 + 597 = 2.097 | 1.248 + 749 = 1.997 |
| Abono a material: queda sin dueño | 0 | 2.097 - 1.997 = 100 (la factura a Willard es 2.097; los 100 parecen un error en la cifra) |
| Flete de 37 | Se factura a Willard en los dos abonos y queda en Circunvalar | No se habló |

Con las cifras de Johana, planta recibe 2.066 por kilo en baterías y 1.248 en materiales; con las de hoy recibe 1.500 en los dos. Vale la pena que lo vean junto.

---

## 1. Abono a baterías: ¿qué parte de lo facturado a Willard es de planta? (Q-36)

**Hoy en el sistema (Hugo, 28-ago):** en el abono a baterías no se causa nada más, porque la maquila de planta ya quedó causada cuando el material se trasladó a Juan Mina. La factura a Willard queda entera en Circunvalar.

**Johana, 16-sep:** además de los $1.500/kg que planta ya cobró en el traslado, cuando Circunvalar factura el abono le reconoce a planta **$566/kg** y se queda con **$1.531/kg**. Sugirió registrarlo como un gasto de maquila de 566. Hugo preguntó por qué se le abonaba otra vez a planta y aceptó la explicación (00:25:26). Al preguntar cómo se lleva, Johana nombró el flete junto con la maquila (00:23:07), pero el reparto que dio (566 + 1.531 = 2.097) es solo de la maquila; de ahí la pregunta c).

**Ejemplo:** planta le devuelve a Willard 300 kg de plomo crudo como abono a batería.

| Concepto | Hoy en el sistema | Johana, 16-sep |
|---|---|---|
| Deuda de baterías con Willard | baja 300 kg | baja 300 kg |
| Deuda de planta con Circunvalar (etapa horno) | baja 300 kg | baja 300 kg |
| Maquila del traslado, ya causada cuando esos 300 kg pasaron a Juan Mina | 300 x 1.500 = $450.000 para planta | 300 x 1.500 = $450.000 para planta |
| Factura a Willard, maquila | 300 x 2.097 = $629.100 | 300 x 2.097 = $629.100 |
| Factura a Willard, flete | 300 x 37 = $11.100 | 300 x 37 = $11.100 |
| Total que Willard queda debiendo | 629.100 + 11.100 = $640.200 | 629.100 + 11.100 = $640.200 |
| De la maquila facturada, para planta | $0 | 300 x 566 = $169.800 |
| De la maquila facturada, para Circunvalar | 300 x 2.097 = $629.100 | 300 x 1.531 = $459.300 |
| Comprobación del reparto | 0 + 629.100 = $629.100 | 169.800 + 459.300 = $629.100 |
| Total que recibe planta por estos 300 kg | 450.000 + 0 = $450.000 (1.500/kg) | 450.000 + 169.800 = $619.800 (2.066/kg) |
| El flete de $11.100 queda en | Circunvalar | No se habló |

**Preguntas:**
- a) ¿Cuál de las dos es la correcta? Las dos vienen de ustedes; necesitamos dejar una sola por escrito.
- b) Si es la de Johana: los $566, ¿son un valor fijo por kilo, o son "2.097 menos 1.531"? Importa para saber cuál de los dos números cambia cuando Willard cambie la tarifa.
- c) El flete ($11.100 en el ejemplo), ¿queda entero en Circunvalar?

**Respuesta 18-sep (Johana, transcripción 00:05:50–00:11:22):** a) la de Johana: L155 «de ahí serían para planta 566», L159 «y 1531» (a); b) L183 «Sí, fijo por kilo» (a), y los 1.531 «también» fijos, «Así es» (L185-187, b); c) el flete queda entero en Circunvalar (L189-191, b; L399 «Si el flet es de circunval», a). **Pedido nuevo que introdujo ella:** L195 «Al momento de facturar, pues ahí me permite agregar IVA, retención, todo eso, ¿verdad?» (Q-41 del inventario). Firme: IVA 19 % (L277 «Sí. el 19ar», dañada; L651-653 «Correcto») que nace al facturar / liquidar, no al cobro (L279-281) (b). Con reserva (b): base maquila + flete (L267) y reparto sobre base sin IVA (L283-293). NO confirmado: IVA sobre la VENTA (lo dijo Daniel, L279; L217 es ilegible) y cuáles RETENCIONES — la palabra «cualquiera» NO está en la transcripción; Johana ofreció una factura de ejemplo con todos los impuestos (L653) y de ahí salen. _(Verificado 19-sep contra la transcripción del 18-sep; grados: (a) palabras de Johana, (b) «Correcto / Así es» a una frase de Daniel, (c) inferencia nuestra.)_

---

## 2. Abono a materiales: ¿cuánto se le factura a Willard y cómo se reparte? (Q-27, Q-37)

**Hoy en el sistema (Hugo, 4-sep por WhatsApp):** de los $2.097/kg que paga Willard, $1.500 van a planta y $597 quedan en Circunvalar. Lo facturado es ingreso de Circunvalar.

**Johana, 16-sep:** lo que se le factura a Willard por los materiales **no es ingreso de Circunvalar**; va a una cuenta por pagar llamada "Materiales Willard". A esa cuenta se le cobra una maquila de **$1.997/kg**: $1.248 para planta y $749 para Circunvalar.

**Ejemplo:** planta le devuelve a Willard 500 kg de plomo como abono a materiales (drosses que llegaron directo a planta, sin pasar por Circunvalar).

| Concepto | Hoy en el sistema | Johana, 16-sep |
|---|---|---|
| Deuda de materiales con Willard | baja 500 kg | baja 500 kg |
| Deuda de planta con Circunvalar | no cambia | no cambia |
| Maquila del traslado | no hubo traslado: los drosses llegaron derecho a planta | igual |
| Factura de maquila a Willard | 500 x 2.097 = $1.048.500 | 500 x 2.097 = $1.048.500 |
| Flete facturado a Willard | 500 x 37 = $18.500 | No se habló (pregunta 4) |
| Lo facturado por maquila es | ingreso de Circunvalar | cuenta por pagar "Materiales Willard" |
| Para planta | 500 x 1.500 = $750.000 | 500 x 1.248 = $624.000 |
| Para Circunvalar | 500 x 597 = $298.500 | 500 x 749 = $374.500 |
| Suma del reparto | 750.000 + 298.500 = $1.048.500 | 624.000 + 374.500 = $998.500 |
| Queda en "Materiales Willard" sin repartir | no existe esa cuenta | 1.048.500 - 998.500 = $50.000 (100/kg) |

Diferencias entre las dos versiones, en el ejemplo: planta recibe 750.000 - 624.000 = $126.000 menos con la versión de Johana; Circunvalar recibe 374.500 - 298.500 = $76.000 más; y los 126.000 - 76.000 = $50.000 restantes son los $100/kg que no tienen dueño.

**Preguntas:**
- a) La factura a Willard es de $2.097/kg, y el reparto que dio Johana suma $1.997 (1.248 + 749). ¿Los $100/kg que faltan ($50.000 en el ejemplo) son un error en la cifra? Si es así, ¿cuál se corrige: planta $1.348 y Circunvalar $749, o planta $1.248 y Circunvalar $849?
- b) Si los $100 no son error: ¿de quién son? ¿De planta, de Willard, o se quedan en Circunvalar?
- c) ¿La respuesta del 4-sep ($1.500 a planta) queda sin efecto?

**Respuesta 18-sep (Johana, transcripción 00:13:46–00:16:12):** a) no es error (a): L323 «eso se maneja con un negocio aparte, en una cuenta aparte… hay que controlarle… ¿Qué utilidad nos está dejando?», L361 «Están quedando 100 pesos de utilidades de esa maquila dentro de la cuenta de los materiales»; b) ella dijo DÓNDE quedan los 100 (dentro de la cuenta de materiales), no de quién son: atribuirlos a Circunvalar es inferencia nuestra (c); c) las cifras de Johana valen: L237 «1248 y 749», L249 «1997» (a). «La del 4-sep queda sin efecto» lo dijo solo Daniel leyendo esta hoja (L375) y ella no respondió a eso (c); Hugo oyó 1.248 / 749 el 16-sep (L585-589) y no objetó. Sin registrar hasta el 19-sep: L335-339, un «remanente de un plomo» de fin de mes de ese negocio que ella «también» liquida (Q-43 del inventario). _(Verificado 19-sep contra la transcripción del 18-sep; grados: (a) palabras de Johana, (b) «Correcto / Así es» a una frase de Daniel, (c) inferencia nuestra.)_

---

## 3. ¿Qué es la cuenta "Materiales Willard"? (Q-37)

| | Hoy en el sistema | Johana, 16-sep |
|---|---|---|
| Lo facturado a Willard por materiales | Es ingreso de Circunvalar el día de la salida; aparece en su Estado de Resultados | No es ingreso; es una cuenta por pagar llamada "Materiales Willard", y de ahí se cobra la maquila de 1.997 |

Johana dijo además que "esa deuda básicamente es de planta" (00:27:57), lo que apunta a la opción a). Ojo: si es de planta, los $100/kg de la pregunta 2 serían también de planta (1.348 + 749 = 2.097), y ella dijo 1.248; conviene cerrar las dos preguntas juntas. Para el sistema hace falta saber **a quién representa** esa cuenta, porque una cuenta por pagar tiene un acreedor y un momento en que se paga.

**Ejemplo con los mismos 500 kg:** después de la salida, ¿alguien queda con un saldo pendiente de cobrar, y cómo se cancela?

- a) Es **planta**: la plata de los materiales es de planta y Circunvalar solo factura en su nombre. El sistema la mostraría como lo que Circunvalar le debe a planta, y se cancela cuando Circunvalar le paga.
- b) Es un **nombre interno** para separar el negocio de materiales del de baterías dentro de la contabilidad de Circunvalar; nadie externo la cobra. Entonces basta con que el reporte separe el ingreso por materiales.
- c) Es **Willard**: parte de lo facturado se le devuelve o se le cruza a Willard.

**Pregunta:** ¿cuál de las tres?

**Respuesta 18-sep (Johana, transcripción 00:18:19 L385-389):** «Es la B» (b) — Daniel leyó en voz alta solo la primera frase de la opción («un nombre interno para separar el negocio… dentro de la contabilidad») y dijo «baterías» donde esta hoja dice «materiales». Consecuencia, que es NUESTRA (c) y no de ella: los $749 y los $100 se muestran juntos como lo que queda en Circunvalar ($849/kg), planta recibe $1.248 (a), y el resumen separa materiales de baterías. Ella separa 749 (ingreso de Circunvalar) de 100 (utilidad del negocio de materiales). Ojo, expectativa creada: en L305-307 Daniel le dijo «lo que vamos a hacer entonces es una cuenta por pagar llamada materiales will» y ella respondió «Correcto»; lo construido en #109 es un resumen por tipo, sin cuenta. **Reabierta el 19-sep (🟠, Q-37 del inventario):** Daniel leyó la A (L375) y la descartó en voz alta, «Creo que esta no es.» (L385), antes de que ella dijera «Es la B.» (L387); y el 16-sep L577 ella había dicho, con sus palabras, que lo facturado por materiales «no es un ingreso para circunval, sino una cuenta por pagar», lo contrario de como lo registra hoy el sistema. _(Verificado 19-sep contra la transcripción del 18-sep; grados: (a) palabras de Johana, (b) «Correcto / Así es» a una frase de Daniel, (c) inferencia nuestra.)_

---

## 4. El flete de $37/kg en el abono a materiales (Q-38)

| | Hoy en el sistema | Johana, 16-sep |
|---|---|---|
| Flete en el abono a materiales, 500 kg | 500 x 37 = $18.500, facturado a Willard, queda entero en Circunvalar | Solo habló de la maquila |

**Preguntas:**
- a) ¿En el abono a materiales también se le factura el flete a Willard?
- b) Si sí, ¿queda entero en Circunvalar o se reparte con planta como la maquila? Los drosses viajan de planta a Willard sin pasar por Circunvalar.

**Respuesta 18-sep (Johana, transcripción 00:18:19 L397-403 y L263-265):** a) sí, siempre se factura (frase de Daniel, «Sí» de ella, b); b) L399 «Si el flet es de circunval» (a). Es como está hoy: sin cambio.

---

## 5. Retorno de dross: la maquila va sobre el 70 % (Q-33, Q-40) — ya respondido el 16-sep, solo confirmar de paso

**Hoy en el sistema:** los kilos que se digitan en el retorno se toman como kilos de plomo: mueven la deuda entre etapas y causan la maquila del reproceso tal cual.

**Reunión 16-sep (Hugo y Johana):** los 20 kg que vuelven son dross y tienen 70 % de plomo (factor fijo, Hugo 00:39:30); la maquila del reproceso se cobra sobre ese plomo, no sobre los kilos de dross. El movimiento entre etapas sí es de los 20 kg: Daniel lo preguntó tal cual ("la maquila se genera por los 14... pero acá sí se hacen movimiento de los 20") y los dos dijeron que sí.

**Ejemplo:** Erwin saca 20 kg de dross del crisol y los vuelve al horno grande.

| Concepto | Hoy en el sistema | Reunión 16-sep (70 %) |
|---|---|---|
| Kilos de dross que vuelven al horno | 20 kg | 20 kg |
| Plomo contenido | 20 kg (se toma lo digitado como plomo) | 20 x 70 % = 14 kg |
| Deuda de planta con Circunvalar, etapa crisol | baja 20 kg | baja 20 kg (los 20 kg de dross salen del crisol) |
| Deuda de planta con Circunvalar, etapa horno | sube 20 kg | sube 14 kg (solo el plomo recuperado) |
| Deuda total | no cambia | baja 20 - 14 = 6 kg (la parte del dross que no es plomo deja de deberse) |
| Maquila del reproceso (gasto Circunvalar, ingreso planta) | 20 x 1.500 = $30.000 | 14 x 1.500 = $21.000 |
| Diferencia por cada 20 kg de dross | | 30.000 - 21.000 = $9.000 de más hoy (6 kg x 1.500) |
| Inventario | el documento no lo toca; la fundición se registra aparte como transformación | retornan 20 kg de dross; al inventario de planta entran 14 kg de plomo (20 - 14 = 6 kg se pierden) |

**Respuesta 18-sep (Johana, transcripción 00:20:10–00:23:50, a):** la etapa crisol baja los 20 kg de dross (L433) y la etapa horno sube solo los 14 kg de plomo — L451 «no subiría 20, sino 14», L471 «esos 20 kg se convierten en 14 porque pierde… un 30%», L505 «la deuda en el horno subiría 14 kg por esos 20 que recibió el crisol»; corrigió a Daniel tres veces. La deuda total: L517 «la deuda total cambiaría en 6 kilos» (a). El 16-sep NO se había dicho lo contrario: Hugo habló de 14 kg de «plomo a devolver» (L767, L775) y «sí retorna los 20» (L795) sobre lo que sale del crisol; el 20/20 fue lectura nuestra de un «Sí, señor» a una frase ambigua (L799). Hugo no estuvo el 18-sep. El documento pedirá kilos de dross, bajará el crisol por esos kilos, subirá el horno por el 70 % y cobrará la maquila sobre ese 70 %. **Confirmado 18-sep:** la baja de 6 kg en la deuda total (L517, a; L623-625, b — «intencional» es palabra nuestra), y el retorno también mueve inventario: L649 Johana «Salen 20 del crisol, entran 14 al horno grande» (a); «de puro» y «de crudo» lo dijo Daniel (L639, b).

---

## 6. El plomo en el crisol, ¿se ve como plomo puro en el inventario? (Q-39)

Johana preguntó si el plomo que pasa al crisol queda representado en el inventario como plomo puro, y en la reunión dijimos que sí. Hoy no es exactamente así.

**Ejemplo:** pasan 200 kg de crudo al crisol. Días después Erwin saca 175 kg de plomo puro y 20 kg de dross; 200 - 175 - 20 = 5 kg se perdieron.

| Momento | Hoy en el sistema | Lo que Johana espera ver |
|---|---|---|
| Traslado a crisoles, 200 kg de crudo | Deuda: etapa horno baja 200, etapa crisol sube 200. Inventario: los 200 kg siguen como plomo crudo | Inventario muestra 200 kg de plomo puro |
| Erwin cierra el crisol: 175 puro, 20 dross | Se registra una transformación: salen 200 de crudo, entran 175 de puro y 20 de dross, 5 de merma | Por definir: ¿se corrige 200 a 175 de puro, o el puro aparece recién aquí? |
| Deuda de planta con Circunvalar al cerrar el crisol | No cambia: sigue 200 en la etapa crisol | Por definir |

Dos formas de resolverlo:

- a) Al pasar al crisol, el inventario ya muestra 200 kg de plomo puro y 0 de crudo; al terminar, Erwin corrige con lo que realmente salió (175 puro, 20 dross, 5 merma).
- b) El inventario sigue mostrando 200 kg de crudo "en crisol", y el plomo puro aparece cuando Erwin cierra el crisol y digita lo que salió: 175 kg de puro y 20 kg de dross.

**Preguntas:** ¿cuál prefieren? ¿Erwin pesa el puro al sacarlo del crisol?

**Respuesta 18-sep (Johana, transcripción 00:25:28–00:26:56, a):** L555 «En el crisol no hay ninguna transformación,» · L559 «no hay porcentaje.» · L563 «El peso se mantiene en el crisol.» · L579 «salen 200 de crudo, ingresan 200 de puro». El ejemplo de esta hoja (200 → 175 + 20 + 5) NO se comentó: en L529-539 ella lee la pantalla. El traslado a crisoles convierte el inventario 1:1 (crudo baja 200, puro sube 200) al mismo tiempo que mueve la etapa. Confirmado 18-sep: el retorno de dross también toca el inventario, salen 20 de puro (crisol) y entran 14 de crudo (horno grande).

---

## 7. Si alcanza el tiempo (quedaron de la hoja de septiembre, no se hicieron el 16-sep)

- **Q-B:** lo que le deben a Willard en plomo y lo que planta le debe a Circunvalar, ¿en pesos en el balance o solo en kilos? Si en pesos, ¿a qué valor el kilo?
- **Q-34:** el plomo de baterías que SAC compra y el de Willard se funden juntos. ¿Quieren ver aparte cuánto ganan con el plomo propio?
- **Cargos por compra:** fuera de la comisión de Green Loop, ¿hay flete del camión, pesaje o descargue? Y si el camión trae varios proveedores, ¿cómo se reparte el flete?

**Respuestas 18-sep (Johana, transcripción 00:26:56–00:30:04) — CORREGIDAS el 19-sep:** Q-B: SOLO sobre la deuda con Willard, L601-605 «yo siempre la coloco pues negativo en el balance, en pesos. le doy un valor de acuerdo al precio del mercado en ese momento y la tengo como un valor negativo, o sea, restando dentro de mi inventario» (a); la mitad de la pregunta sobre lo que planta le debe a Circunvalar NO se hizo — Daniel la leyó y la saltó (L585-595) → Q-44 del inventario. Q-34: L597 «Sí, es un solo inventario. Todo eso ingresa en la circunval» (a); la mitad del margen del plomo propio NO se preguntó (L595). Cargos por compra: el registro decía «solo Green Loop» y ella dijo lo contrario — L621 «eso ellos lo pasan como gastos por aparte. Es como si fueran gastos de nosotros de SA de circunval» (a): existen y van como gasto aparte de Circunvalar; siguen sin prorratearse a la compra.
