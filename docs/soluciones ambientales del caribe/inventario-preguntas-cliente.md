# Inventario de preguntas al cliente — SAC

**Para qué existe:** una sola lista de TODO lo que se le ha preguntado (o se pensó preguntar) a Hugo, Johana y Erwin, con su estado en una línea. Antes de cualquier conversación con el cliente y antes de planear cualquier cosa de SAC, **se lee este archivo**. Nada se repregunta si aquí está respondido; lo abierto se pregunta con la formulación que está aquí.

**Cómo se mantiene:** cada pregunta nueva entra con el siguiente `Q-nn` (la serie sigue la del registro `control-cambios-requerimientos.md`, que conserva la prosa larga y las citas; aquí va la línea de estado). Cuando algo se responde, se construye o se decide, se cambia el estado aquí **el mismo día**. Fuentes: registro de cambios, `requerimientos-funcionales.md` (Anexo F = decisiones de junio/julio con cita; §18 = preguntas de la fase de requisitos), briefing del 11-ago, `plan-cierre-entradas-traslados-transformaciones.md` §4 (las 18 del 12-ago) y las transcripciones.

**Estados:** ✅ **construido** (respondida y en el código, con la decisión `#nn` de CLAUDE.md) · ☑️ **respondida, sin construir** (la respuesta está, falta el ciclo) · 🟢 **decidida por nosotros** (se informa, no se pregunta) · 🟡 **para confirmar de paso** (ya dicha; se repite en voz alta para que la corrijan) · 🟠 **abierta** (pregunta real: nadie la ha contestado o dos fuentes se contradicen) · ⬜ **sin objeto / superada** · 📎 **pedido pendiente** (un dato o documento que el cliente debe entregar).

**Última revisión:** 2026-09-09 (auditoría antes de la reunión de septiembre).

---

## A. Entradas y compras

| ID | Pregunta | Respuesta | Quién / cuándo | Estado | Dónde |
|---|---|---|---|---|---|
| Q-01 | Lista real de referencias (baterías kg/unidad, drosses %) | Plantilla en Drive que SAC llena | Johana 17-jul | ✅ | seeder `seed_sac_org.py` (37 materiales + perfiles) |
| Q-04 | ¿Un material Willard puede entrar también por compra? | Excluyente por ENTRADA, no por material ("cuentas apartes") | Johana 17-jul | ✅ | #77 `material_kg_profiles`, #80 B3 |
| Q-05 | ¿La sede de recepción es determinista? | Sí: drosses→Juan Mina, postconsumo→Circunvalar | Johana/Hugo 17-jul | ✅ | #80 B2 |
| Q-06 | ¿Patio captura también las compras regulares? | Sí, mismo flujo: patio captura, Johana liquida | Johana/Hugo 17-jul | ✅ | #75, #82 |
| Q-09 | ¿Cerramos la compra manual para que Recepción sea la única puerta? | Sí, todo pasa por báscula | Johana/Hugo 17-jul | ✅ | #80 B1 |
| Q-10 | Camión con drosses y baterías juntos: ¿una o dos recepciones? | Muy raro; si pasa, dos | Daniel con input 17-jul | ✅ | #80 B2 (homogeneidad, 422) |
| Q-11 | Sede de las compras regulares: ¿fija o la elige el usuario? | Bodega libre | Daniel 17-jul | ✅ | #80 |
| Q-12 | ¿Qué bodegas reciben de terceros? | Juan Mina, Circunvalar, Bogotá; "¿y si mañana hay otra?" → flag en la bodega | Johana 17-jul | ✅ | #80 `warehouses.is_receiving` |
| Q-03 | ¿Un dross entra alguna vez por Circunvalar? | Nunca, siempre a Juan Mina | Johana 17-jul | ✅ | #80 B4 (`goes_directly_to_jm` retirado) |
| — | Un proveedor por línea en compra regular (v0.6, 3-ago) → el patio no conoce al proveedor | El proveedor se asigna al LIQUIDAR, con reparto por material | Johana 3-ago y 5-ago (Excel de Johana) | ✅ | #93 (supersede #89) |
| Q-13 | ¿Cuándo es obligatorio el peso de báscula? | Opcional al capturar, obligatorio al REVISAR | Hugo 13-ago (tel.) | ✅ | #95 Q-13 |
| Q-14 | ¿Erwin pesa por referencia o el camión entero? | Por referencia, cada línea con su peso | Hugo 13-ago (tel.) | ✅ | #95 (disuelve el reparto del húmedo) |
| Q-15 | Al liquidar por peso, ¿precio por kilo o valor total? | El valor TOTAL de la línea; luego Hugo pidió también kilos × precio | Hugo 13-ago y 12-ago | ✅ | #95 D8 (total) + #101 (precio por kg) |
| Q-16 | ¿Willard pasa por revisión? | Sí (draft → reviewed → confirmed) | Hugo 13-ago (tel.) | ✅ | #95 (b) |
| Q-17 | El % de plomo (53%), ¿único o por referencia? | No hace falta la respuesta: valor por defecto de la org, ajustable por material | Daniel 13-ago (diseño) | ☑️ | se construye con su consumidor (el informe); NO re-preguntar (#95) |
| Q-19 | ¿Quién captura y quién revisa? | Erwin captura, David revisa, Johana liquida | Hugo 13-ago (tel.) | ✅ | #95 (f) seeder `REVISOR_ROLE` |
| — | El centavo del redondeo ($200.000 ÷ 3) | Se acepta, la pantalla lo muestra antes de guardar | Hugo/Daniel 13-ago | ✅ | #95 D8 |
| — | ¿Fuera de la comisión de Green Loop hay otro cargo por compra (flete del camión, pesaje, descargue)? Si hay flete con varios proveedores, ¿cómo se reparte? | — | Nadie; #93 lo difirió "para consultar en reunión" | 🟠 | hoja de septiembre, pregunta 3 |
| — | Orden de captura del reparto: ¿material→proveedores o proveedor→materiales? | Se deja como está (material→proveedores) y se observa la primera semana; reversible | Daniel/Claude 9-sep | 🟢 | #93 (diferido), hoja §D |
| — | Consecutivo de arranque configurable (entradas ~15.000) | Se retoma en la puesta en marcha | Daniel 3-ago | ☑️ | memoria `sac-reunion-0803-compromisos` |
| — | ¿Quién parte el peso cuando una línea se reparte entre dos proveedores? | Hoy lo hace Johana a mano; no pidió que el sistema lo haga | Hugo 12-ago (l.205) | ⬜ | el reparto por asignación con peso por unidad lo cubre (#101 D2) |
| — | ¿El estado de cuenta puede diferir en centavos de la factura? | Sí (centavo aceptado) | Hugo 13-ago | ✅ | #95 D8 |

## B. Retenciones

| ID | Pregunta | Respuesta | Quién / cuándo | Estado | Dónde |
|---|---|---|---|---|---|
| Q-07 | ¿SAC aplica retenciones al liquidar? ¿Imprescindible para el go-live? | Sí, opcionales; tarifas típicas pero monto editable | Johana 17-jul | ✅ | #75, #79 (catálogo con precálculo), #93 (opcionales por proveedor) |
| Q-08 | ¿Contabilidad necesita certificados / resumen mensual? | Por ahora basta el estado de cuenta | Johana 17-jul | ☑️ | backlog si contabilidad lo pide |
| — | Tabla de retenciones por tipo de proveedor (ICA, ReteFte, ReteIVA) | Se recoge al arranque, confirmar con el contador | spec §18.2 | 📎 | Config → Retenciones ya admite cargarlas |

## C. Listas de precios por proveedor

| ID | Pregunta | Respuesta | Quién / cuándo | Estado | Dónde |
|---|---|---|---|---|---|
| Q-18a | Tercero sin lista, ¿usa la general como respaldo? | Hugo dijo "de acuerdo" a una propuesta abstracta; preguntado de frente (Q-22) dijo lo contrario | Hugo 13-ago | ⬜ superada por Q-22 | #98 D3 |
| Q-18b | ¿Listas también de venta? | Fue un supuesto mío registrado como respuesta; **solo de compra** | corrección 13-ago | ⬜ | #95 (nota), #98 |
| Q-20 | ¿Proveedor y cliente comparten lista? | Sin objeto (solo compra) | — | ⬜ | — |
| Q-21 | ¿Cuántas listas y qué materiales lleva cada una? | Las que sean; cada lista trae TODOS los materiales, el cero = sin precio | Hugo 13-ago | ✅ | #98 (Q-21), `zeroMeansUnset` #102 |
| Q-22 | Proveedor nuevo, ¿a qué lista entra? | A ninguna, y no se sugiere precio | Hugo 13-ago | ✅ | #98 D3 |
| Q-23 | ¿Quién administra las listas? | El administrador | Hugo 13-ago | ✅ | #98 D5 |
| Q-24 | ¿El precio de la lista se puede cambiar al liquidar? | Sí, editable | Hugo 13-ago | ✅ | #98 D8 |
| Q-25 | ¿Cada cuánto cambian? | Cada 3 meses (→ pantalla tipo hoja de cálculo) | Hugo 13-ago | ✅ | #98, Tab en celdas #102 |
| — | ¿Los terceros se marcan desde la lista o al revés? | Desde la lista ("es al contrario") | Hugo 13-ago | ✅ | #98 D2 |
| — | ¿Un tercero en dos listas? | No, una sola | Hugo 13-ago | ✅ | #98 D2 (UNIQUE) |
| Q-26 | Al encender las listas, ¿qué pasa con los proveedores que hoy usan la general? | Todos arrancan con la general y Hugo los reparte después (sembrado en una operación) | Claude/Daniel 9-sep | 🟢 | #98 Q-26 `seed_from_general` + `assign_all_suppliers`; se informa a Hugo |

## D. Plomo, Willard y maquila (el modelo)

| ID | Pregunta | Respuesta | Quién / cuándo | Estado | Dónde |
|---|---|---|---|---|---|
| D2 | Tarifa Willard por kilo de plomo entregado | $2.097 | Hugo 26-jun; Johana 3-sep | ✅ | seeder `maquila_willard` (corregido en CC-009) |
| D4 | Maquila de planta a Circunvalar | $1.500/kg + $300/kg si pasa por crisol | Hugo 26-jun | ✅ / ☑️ | $1.500 al trasladar (#84); los $300 sin construir (ver crisol) |
| D5 | Fletes Willard | $37/kg planta–Willard por entrega; $216/kg Bogotá–Barranquilla mensual | Hugo 26-jun, visita 2-jul, Johana 3-sep | ✅ / ☑️ | $37 en seeder; $216 **diferido** (Johana 3-sep) |
| D28 | ¿Hay flete en el tramo Circunvalar→Juan Mina? | No, carros propios; los $1.500 son solo procesamiento | visita 2-jul | ✅ | — |
| Q-viva.1 / Q-A | ¿Cuándo se causa la maquila interna? | AL TRASLADAR, una sola vez. (Q-A "en la entrega", 24-ago, quedó SUPERADA por la demo del 28-ago) | Hugo+Johana 2-jul; Hugo 28-ago | ✅ | #84; CC-009 fila 1 (D11 revertida) |
| Q-27 | En el abono en materiales, ¿de quién es el ingreso de maquila? | Se reparte: $1.500/kg a planta, $597 a Circunvalar | Hugo 4-sep (WhatsApp) | ✅ | `abono_planta_por_kg` 1.500; par solo en `abono_material` (CC-009) |
| Q-28 | En una venta a Willard, ¿se factura maquila y flete? | No: solo el precio del plomo. Maquila y flete solo en abonos | Hugo 4-sep | ✅ | CC-009 fila 14 |
| Q-29 | Planta cobra $1.500/kg por fundir, ¿da igual de dónde vino el material? | Ya dicho dos veces ($1.500 en los dos caminos) | Hugo 28-ago y 4-sep | 🟡 | hoja de septiembre, afirmación 4; unificar los dos códigos de tarifa es nuestro |
| Q-30 | En una venta, ¿el margen queda entero en planta? | No era pregunta: **Johana factura todo**, planta recibe su valor por kilo. El código pone la venta en Juan Mina → corrección nuestra | Hugo 24-ago 00:38:22 | ☑️ | ciclo de planta (la venta derivada debe nacer en la sede de facturación) |
| Q-31 | ¿Cuál material es el plomo crudo? | `PLO-LIN` (lingote) es el crudo; `PLO-PUR` el puro | Johana 9-sep + §4.1 | ✅ | #103, commit `cbd2a79` |
| Q-32 | ¿La venta de plomo sale siempre de planta? | Sí; otros materiales de cualquier bodega | Johana 9-sep (tel.) | ✅ | #100 D8 guard |
| Q-33 | El dross del 13% del crisol, ¿es traslado a Circunvalar? | No sale de planta: vuelve al horno grande y causa maquila otra vez; "retorno a Johana" es en kilos | Johana 3-sep; Hugo 28-ago :395 | ☑️ | ciclo de planta (crisol→horno dentro de intersede + nueva maquila) |
| Q-34 | Plomo propio (baterías compradas) y de Willard: ¿un solo material? ¿Quieren ver aparte el margen del propio? | — | nadie (pruebas 9-sep) | 🟠 | hoja de septiembre, pregunta 2 |
| Q-35 | Las baterías en Bogotá, ¿ya son deuda con Willard? | No hasta llegar a Circunvalar; Bogotá es un proveedor | Johana 26-jun, 11-ago, 24-ago, 3-sep | 🟢 | sin cuenta kg en Bogotá (#105 punto 19); D23 del spec queda superada |
| Q-B | La deuda en plomo con Willard, ¿pasivo en pesos en el balance o costo del mes? | — | nadie | 🟠 | hoja de septiembre, pregunta 1; decide #100 D13 |
| — | Deuda Willard: ¿nacional o discriminada por sede? | Hugo dijo las dos cosas en 60 segundos (12-ago l.771 y l.795); el modelo la lleva por sede | Hugo 12-ago | 🟠 ambigua | confirmar por escrito cuando se retome Bogotá |
| Q-viva.2 | ¿El crisol es cuenta aparte del horno? | Sí, 5 cuentas; y intersede = horno grande + crisol | Johana 2-jul y 3-sep | ☑️ | cuentas horno/crisol NO construidas (#100 (c), #103 D8) |
| — | Pasar crudo al crisol, ¿mueve inventario o deuda? | No: solo control de dónde está el plomo | Hugo 28-ago | ☑️ | cuarto tipo "traslado a crisoles" pedido y no construido |
| — | Los $300/kg del crisol, ¿cuándo y a quién? | Al VENDER el plomo puro (antes: al salir del crisol); planta se los cobra a Circunvalar | Hugo 28-ago ×3; spec §5 | ☑️ | ciclo de planta |
| — | El dross que sale del crisol | Vuelve al horno grande y causa maquila otra vez (un kg puede causar dos veces) | Johana 3-sep | ☑️ | ciclo de planta |
| — | Plomo crudo vs puro, ¿los dos salen a Willard? | Crudo en los tres tipos; puro solo en venta | Hugo 28-ago | ✅ | #103 D2, #104 (pantalla no ofrece puro en abonos) |
| — | Exportación y venta a terceros de plomo | Cuatro destinos del crudo (venta, abono, exportación, refinación) — dichos el 26-jun y en los diagramas | Hugo 26-jun; diagramas | ☑️ | no construido (registro "Alcance conocido y NO construido") |
| — | ¿Se lleva un saldo intermedio en kilos de scrap (lo que sale del molino) o todo se convierte a plomo equivalente? | Todo en plomo equivalente (Hugo mismo ofreció esa salida: "o lo deja también en plomo... que coincida plomo con plomo"); lo que se pierde entre batería y scrap es rendimiento del molino contra estándar, no una deuda | Hugo 12-ago 00:49:28; decisión 9-sep | 🟢 | libro kg plomo-only por construcción; el rendimiento va con la tabla del molino (T0/T1) |
| D6 | Utilidad cero gerencial en Juan Mina y Bogotá | Sí ("lo que genere el gasto, la compra y la venta") | Hugo 26-jun | ☑️ | P&L por sede existe (#84); toggle consolidado no |

## E. Salidas de plomo (el módulo)

| ID | Pregunta | Respuesta | Quién / cuándo | Estado | Dónde |
|---|---|---|---|---|---|
| — | ¿Las salidas pasan por "Revisar"? | No: registrado → liquidado ("inmediatamente queda la deuda") | Hugo 28-ago | ✅ | #100 corrección 9-sep (commit `5a9f798`) |
| — | ¿La remisión es obligatoria? | Sí, "para que no me alteren el consecutivo"; es el número de Willard digitado a mano | Hugo 28-ago | ✅ | #100 corrección (2) |
| — | ¿Un consecutivo o dos? | Dos: ventas y abonos (el de abonos se concilia con Willard) | Hugo 28-ago | ✅ | #105 (a) serie |
| — | ¿Quitar el tipo venta del módulo? | No: es la única vía que baja `intersede` junto con abono_bateria; el nombre pasa a "Salidas de Plomo" | Hugo 28-ago; Daniel 9-sep | ✅ | #104 |
| — | Báscula en material en kg | Redundante en pantalla; el servidor la autocompleta | Daniel 9-sep | ✅ | #105 (b) |
| — | Venta de plomo por valor total | Conmutador unitario/total | Daniel 9-sep | ✅ | #105 (e) |
| — | ¿Qué material puede salir a Willard? | Solo el marcado como crudo/puro (antes salía cualquiera y facturaba maquila) | hallazgo propio, Johana 9-sep | ✅ | #103 |
| — | ¿Puede salir más plomo del que planta le debe a Circunvalar? | Regla general de la app: avisar, no bloquear | briefing 11-ago §3.3 | ✅ | #100 D4d (warning) |

## F. Traslados, molino y transformaciones

| ID | Pregunta | Respuesta | Quién / cuándo | Estado | Dónde |
|---|---|---|---|---|---|
| — | ¿Dónde está el molino? | En Circunvalar; Circunvalar y molino son un solo inventario | Johana 11-ago | ✅ | #94 (sede; traslado intra-sede en un salto) |
| — | Traslado CV→JM: ¿dos pasos con tolerancia? | Sí, con merma y discrepancia | visita 2-jul (D25) | ✅ | #84 |
| T0 | ¿El paso por el molino es traslado, transformación o documento nuevo? | — | Hugo 12-ago no lo cerró | 🟠 | bloqueado por la tabla de estándares; #99 lo deja preparado |
| — | Tabla de estándares del molino (qué sale de cada material) | Pedida el 11-ago; dueño Erwin | — | 📎 | sin ella no hay T0/T1 |
| — | Subproductos de trituración | Fijos según lo que entra (batería normal: plomo fino/grueso, lodo, PP, jamiche; moto: ABS) | Johana 11-ago | ☑️ | faltan los materiales de salida (T2b) |
| — | Estándar del molino: ¿90 o 91%? ¿piso o % por material de salida? | Hugo dijo 90 y 91; "no es tan fácil de controlar" | Hugo 12-ago | 🟠 ambigua | va con la tabla del molino |
| — | ¿Picadores es bodega o proceso? | — | — | 🟠 | preguntar cuando se construya el molino |
| — | ¿El corte es la medición o el cierre mensual? ¿Ajuste mensual lo hace el sistema o Johana? | — | Hugo 12-ago habló de "corte corte" y de "ajuste mensual" | 🟠 | ídem |
| — | ¿La transformación se corrige o se anula? | Hoy solo se anula y recrea | — | 🟠 | ídem |
| — | ¿Segundo pesaje dentro de la misma sede? | Hugo pidió pesar al salir y al llegar; Daniel decidió que intra-sede no se pesa dos veces | Hugo 12-ago; Daniel 18-ago | 🟢 | #94 (nace recibido) — si Hugo insiste, se reabre |
| — | ¿Una transformación puede cruzar de sede? | No: bloquea con 400 (no hay recepción que garantice lo que llegó) | Daniel/Claude 20-ago | 🟢 | #99 |
| Q-15 spec | Alcance de Henry (fundición): ¿solo operativo o registra coladas? | Nunca se habló con Henry | — | 📎 | auditoría interna B9 |

## G. Bogotá y Green Loop

| ID | Pregunta | Respuesta | Quién / cuándo | Estado | Dónde |
|---|---|---|---|---|---|
| — | ¿Bogotá es sede o proveedor? | Proveedor: Johana no lleva sus proveedores ni gastos, solo el saldo consolidado | Johana 11-ago (y ×3 más) | 🟢 | Q-35; sin cuenta kg BOG |
| T5 | ¿"SA Bogotá" como un solo tercero agregado basta? | Textual de Hugo ("no discriminamos los x proveedores de Bogotá"); pendiente por escrito | Hugo 12-ago l.1071 | 🟡 | convierte "saldos por sede" (XL) en configuración |
| T4 | Bogotá→Barranquilla: ¿traslado, entrada o los dos? | Hugo dijo las dos cosas; con Q-35 la llegada a Circunvalar es una Entrada normal | Hugo 12-ago | 🟢 | se reabre solo si Bogotá pasa a sede |
| W2 | ¿Dónde nace el flete Willard de Bogotá? | Por RUTA, no por centro; nace en el traslado, no en la Entrada | Hugo 12-ago; diseño | ☑️ | diferido con el flete $216 (Johana 3-sep) |
| — | ¿Cuál es la tarifa de flete vigente de Bogotá? | "Justo la cambié a principio de mes" y no la dictó | Hugo 12-ago l.665 | 📎 | pedir cuando se retome Bogotá |
| Q-02 | ¿Green Loop recolecta postconsumo? ¿Se le paga comisión por eso? | Sí recolecta; comisión SOLO en compras regulares, y es gasto, no costo | Johana 17-jul y 3-ago | ✅ | #83 |
| Q-viva.3 | Estructura de Green Loop | Caja provista por SAC, compra en ruta a nombre del proveedor real, rendición, $100/kg | Johana 2-jul | ✅ / ☑️ | comisión ✅ (#83); caja propia y "solo ve lo suyo" ☑️ (11-ago, desarrollo nuevo) |
| — | Provisionales de Green Loop a conductores | Control interno de ellos; con caja propia son anticipos desde esa caja | Johana 11-ago | ☑️ | el sistema ya lo soporta cuando exista la caja |

## H. Personas, arranque y datos

| ID | Pregunta | Respuesta | Quién / cuándo | Estado | Dónde |
|---|---|---|---|---|---|
| — | ¿Cuándo empiezan a operar? | Ya: Entradas, inventario y traslados, corrigiendo sobre la marcha ("no dejar de utilizarlo") | Hugo 28-ago 00:33:23 | 🟢 propuesta | hoja de septiembre §C |
| P55 | Fecha de corte del arranque | Idealmente un viernes (último cuadre Willard) | spec §18.2 | 📎 | se fija con la fecha de arranque |
| — | Informes de Johana tal como se los entrega a SAC | Los ofreció; no hay registro de que llegaran | Johana 11-ago | 📎 | briefing 11-ago §3.1 |
| — | Saldos iniciales al corte (kg en tránsito, horno, crisol, sub-saldos, terceros, cuentas) | Se recogen al arranque; no pedirlos antes de la propuesta comercial | spec §18.2 | 📎 | `migrate_org.py` (#28) |
| — | Formato de factura a Willard (Excel/PDF/DIAN) y tolerancia del cuadre (±50/100 kg) | — | spec §18.2 | 📎 | `KgLedgerAccount.tolerance_kg` existe |
| — | Vencimientos y plazos en obligaciones financieras | Johana preguntó; Daniel dijo "sí, totalmente"; no existe en el modelo | 3-ago | ☑️ compromiso | ciclo propio (memoria `sac-reunion-0803-compromisos`) |
| P1 | Volúmenes pico por sede | — | spec §18.2 | ⬜ | ya no condiciona nada (10–20 entradas/día confirmadas) |
| — | Preguntas de Fase 2 (Henry, Jose: coladas, fundentes, móvil) y Fase 3 (contador, DIAN) | — | spec §18.3/§18.4 | ⬜ fuera de fase | se abren en su sesión 1:1 |

---

## Regla de uso (resumen)

1. **Antes de hablar con el cliente:** filtrar este archivo por 🟠 y 📎. Eso es lo único que se pregunta o se pide. Lo 🟡 se dice en voz alta como afirmación.
2. **Antes de planear:** buscar aquí el tema; si está ✅ no se rediseña, si está ☑️ la respuesta manda, si está 🟢 se informa al cliente en vez de preguntarle.
3. **Después de cada reunión o llamada:** cada respuesta nueva cambia una fila el mismo día (con quién y cuándo); las preguntas nuevas entran con `Q-nn` aquí y en el registro.
