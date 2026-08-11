# Auditoria del Documento de Requerimientos v0.1 — SAC

**Documento auditado:** `docs/soluciones ambientales del caribe/requerimientos-funcionales.md` (1646 lineas, 16 secciones)
**Fecha auditoria:** Junio 2026
**Auditores:** 6 lentes adversariales paralelas (coherencia, fidelidad, cobertura, neutralidad, calidad de preguntas, empatia)

---

## Resumen ejecutivo

### Veredicto general

**El documento NO esta listo para mostrar a SAC en su estado actual.** Tiene calidad de negocio razonable (glosario solido, flujos correctos, identificacion fiel de pain points), pero esta atravesado por tres problemas estructurales que cualquier lector adversarial — y especialmente un asesor tecnico contratado por SAC — detectaria en la primera lectura: (1) **fugas de implementacion de EcoBalance** que delatan el sistema preconstruido (terminos como "revert-and-reapply", "aislamiento por organizacion", "Carga inicial migracion", "cutoff configurable") y hacen ver al doc como brochure de producto, no como propuesta a medida; (2) **tres contradicciones de fases bloqueantes** (Ventas 5.11, Subproductos 5.10 y Recoleccion en Campo 5.2 quedan en Fase 2/3 pero Fase 1 los necesita para funcionar end-to-end, rompiendo el Hito 2); (3) **decisiones tomadas que debieron ser preguntas** sobre las practicas reales del cliente — la mas critica: la liquidacion por peso de Johana esta reinterpretada en contra de lo que ella dijo literalmente en la reunion. Riesgo principal: si se entrega tal cual, SAC sospechara sobreprecio o subestimacion del esfuerzo, y Johana entrara en modo defensivo desde la primera lectura. Con 1-2 dias de trabajo de neutralizacion + reasignacion de fases + 3 conversaciones 1:1 (Johana, Erwin, Jose) el documento se puede llevar a un estado defendible.

### Scores por dimension

| Dimension | Score (0-10) | Estado |
|---|---|---|
| Coherencia interna | 5 | Critico (3 contradicciones bloqueantes de fases) |
| Fidelidad a transcripcion | 4.5 | Critico (inventos de fundicion/subproductos/regulacion) |
| Cobertura real | 6 | Necesita ajuste (modulos vacios: 5.15, cuadre diario, deuda multi-dim) |
| Neutralidad comercial | 3 | Critico (24 leaks de EcoBalance) |
| Calidad de preguntas | 6 | Necesita ajuste (redundancias + 48 faltantes) |
| Empatia con cliente | 5.5 | Necesita ajuste (3 conversaciones 1:1 faltantes) |

### Score global ponderado

**4.7 / 10.** Ponderacion: neutralidad y coherencia pesan doble (son los que mas dano hacen frente a SAC); fidelidad pesa 1.5x; cobertura/preguntas/empatia pesan 1x. Calculo: (3·2 + 5·2 + 4.5·1.5 + 6·1 + 6·1 + 5.5·1) / 8.5 = 40.25 / 8.5 ≈ 4.7. El doc no es desechable — el glosario, el mapa de flujo, la captura de pain points y las 152 preguntas son activos reutilizables. Pero los modulos 5 (16 modulos con plantilla identica), las 40 reglas y la matriz RBAC + cronograma ajustado a 10-14 semanas configuran una huella de producto preexistente que un lector promedio detecta en 10 minutos. Con la pasada de neutralizacion + fix de fases + tabla de roles consolidada, sube facil a 7-8/10.

---

## Hallazgos BLOQUEANTES (hay que arreglar antes de mostrar a SAC)

### B1: Frases-bandera de EcoBalance que delatan sistema preconstruido
- **Severidad:** BLOQUEANTE
- **Lente:** Neutralidad comercial
- **Ubicacion:** Lineas 1267 ("aislamiento por organizacion"); 447, 524, 1136 ("costo promedio solo al liquidar"); 706, 1117 ("revert and reapply"); 538 ("Carga inicial migracion"); 277, 534, 916, 973 ("bodega virtual de transito").
- **Problema:** 5 frases bloqueantes mas 9 importantes coinciden 1:1 con decisiones internas documentadas en `CLAUDE.md` (decisiones #3, #5, #8, #11, #17, #28, #41, #50, #52). Ejemplo: linea 1267 *"Aislamiento por organizacion: los datos de SAC estan aislados; ningun otro cliente puede verlos"* — solo tiene sentido si hay otros clientes (lenguaje SaaS multi-tenant); linea 538 *"motivo 'Carga inicial migracion' para excluirse de los reportes"* es textualmente el marker de la decision #28.
- **Por que es bloqueante:** Un asesor tecnico contratado por SAC google-eara "revert and reapply" y/o detectara el lenguaje multi-tenant. Da pie a sospecha de sobreprecio ("nos venden algo ya hecho como si lo construyeran") o subestimacion ("nos prometen tiempos que solo cuadran si reusan, pero no lo dicen").
- **Fix propuesto:** Pasada de neutralizacion completa sobre los 24 riesgos detectados (sustituir por descripciones de negocio sin implementacion: "el sistema debe mantener un costo promedio movil — el momento exacto de recalculo se definira con SAC"; "los datos residen en BD dedicada con cifrado en reposo y acceso restringido por usuarios autorizados"; "el sistema reversa internamente y recalcula" en vez de "revert and reapply"). Eliminar la frase del marker "Carga inicial migracion".
- **Esfuerzo:** 3-4 horas.

### B2: Ventas (5.11), Subproductos (5.10) y Recoleccion en Campo (5.2) fuera de Fase 1 — rompe el Hito 2 "end-to-end"
- **Severidad:** BLOQUEANTE
- **Lente:** Coherencia interna
- **Ubicacion:** Seccion 11 lineas 1292-1325 (asignacion a fases) vs secciones 5.5, 5.7, 6.9, regla 17-18.
- **Problema:** Fase 1 incluye Maquila/Postconsumo Willard con "abonos" y "conciliacion mensual" (linea 1296), pero el abono se modela como una "Venta tipo Abono Willard" en modulo 5.11 que esta en Fase 2 (linea 1323). Sin 5.11, la cuenta corriente Willard de Fase 1 no se puede descargar. Ademas Fase 1 promete Tesoreria con CXC/CXP en pesos pero las CXC nacen de 5.11. Similar: las transformaciones de Fase 1 generan subproductos que no tienen donde ir hasta Fase 3 (modulo 5.10). Y la recoleccion postconsumo en ruta esta en 5.2 (Fase 2) sin "modo degradado" definido para Fase 1.
- **Por que es bloqueante:** El criterio de aceptacion "un dia completo sin Excel paralelos" + "Hito 2 funcionando end-to-end" no es alcanzable como esta escrito. SAC va a marcarlo inmediatamente y la credibilidad del cronograma se erosiona antes de empezar.
- **Fix propuesto:** Subir a Fase 1 (a) modulo 5.11 al menos en su parte de venta nacional + abono Willard, (b) bodegas e inventario de subproductos del 5.10 (sin la venta a gestores RESPEL ni manifiestos, que quedan en Fase 3), (c) entrada postconsumo en ruta capturada manualmente en patio por Erwin como orden de entrada tipo "recoleccion postconsumo" (Fase 1) — la app movil de conductores llega en Fase 2 para eliminar el papel. Documentar este "modo degradado" explicitamente en seccion 11.
- **Esfuerzo:** 2-3 horas.

### B3: Liquidacion por peso reinterpreta lo que Johana dijo literalmente
- **Severidad:** BLOQUEANTE
- **Lente:** Empatia con cliente / Fidelidad
- **Ubicacion:** Seccion 5.4 lineas 441-447, regla 6, ejemplo de 631 kg.
- **Problema:** El doc dice *"ambas magnitudes se persisten"* y *"el costo unitario del inventario se distribuye proporcionalmente"*. Johana dijo textualmente (transcripcion 01:03): *"para no afectar el inventario, ya esas liquidaciones por aparte"*. Es decir, **ella NO distribuye el costo proporcionalmente — ella las lleva aparte para que no afecten el inventario por unidades**. Ademas el ejemplo "631 kg para 10 unidades" inventa el "10 unidades" (Johana solo dio 631 kg).
- **Por que es bloqueante:** Johana es la guardiana del cuadre. Si abre el doc y ve que su practica esta reinterpretada en su contra, entra en modo defensivo desde la primera linea y el resto del proyecto se contamina politicamente. Ademas afecta directamente el modelo de datos (costo unitario por kg virtual vs por unidad fisica vs documento separado).
- **Fix propuesto:** Reescribir 5.4 reflejando la practica actual de Johana: la liquidacion por peso se persiste en documento separado vinculado a la orden; el inventario por unidades mantiene su propio costo unitario (a definir con ella: ¿costo zero hasta liquidacion? ¿costo estimado por precio de lista?). Confirmar con ella en sesion 1:1 si quiere cambiar la practica o respetarla. Quitar "para 10 unidades" del ejemplo.
- **Esfuerzo:** 1 hora doc + 30 min reunion con Johana.

### B4: Lista detallada de insumos de fundicion, subproductos y regulacion ambiental inventada por el experto
- **Severidad:** BLOQUEANTE
- **Lente:** Fidelidad a transcripcion
- **Ubicacion:** Seccion 1.1 lin 37; seccion 2.4 lin 137-148 (insumos: Na2CO3, antracita, calamina, NH4Cl, cal, Al, soda caustica, carbon vegetal); seccion 2.7 (Resolucion 372/2009, 1297/2010, RUA, RESPEL, Basilea A1160, ANLA, IDEAM, UIAF); modulo 5.10 entero (electrolito, separador, polvoducto, drosses Willard); seccion 2.3 (plomo 99.97%, proceso Harris, grados A/B).
- **Problema:** Nada de esto fue mencionado por SAC en la reunion. Hugo dijo que Henry haria una sesion aparte. Toda la quimica de fundicion, los subproductos no nombrados (electrolito, separador, polvoducto, drosses), y el marco regulatorio colombiano son proyecciones del experto en dominio. SAC menciono solo: plastico, lodo, fino, grueso, scrap, tapas, cajas acrilicas.
- **Por que es bloqueante:** Si Hugo lee y siente que "inventamos" su receta y sus obligaciones regulatorias, perdemos credibilidad. Si Henry contradice 30-40% en su sesion, hay retrabajo masivo + percepcion de improvisacion.
- **Fix propuesto:** Marcar bloques afectados con `[PROPUESTA — validar con Henry/SAC]` en lugar de presentarlos como hecho. Eliminar Seccion 2.7 (marco regulatorio) y reformularla como bloque de preguntas a SAC. Reducir Seccion 2.4 a "insumos a definir con Henry". Reducir 5.10 a los subproductos que SAC mencionara (PP, lodo, grueso, fino, scrap, tapas, cajas acrilicas). Eliminar numeros de pureza concretos. Mover los demas a Seccion 15 (preguntas).
- **Esfuerzo:** 2-3 horas.

### B5: Cronograma de 10-14 semanas para Fase 1 — irreal si se construye desde cero, sospechoso si se reutiliza sin decirlo
- **Severidad:** BLOQUEANTE
- **Lente:** Neutralidad + Empatia
- **Ubicacion:** Seccion 11 lin 1304-1316.
- **Problema:** 16 modulos + 26 reportes + RBAC granular + multi-sede + offline-first + exportaciones + trazabilidad por colada + balance historico en 10-14 semanas es **imposible** si se construye desde cero. Si se reutiliza EcoBalance pero no se declara, SAC oler que algo no cuadra (junto a B1).
- **Por que es bloqueante:** El cliente puede tomar dos lecturas igualmente malas: (a) "nos estan mintiendo en el tiempo → habra retrasos", o (b) "ya lo tienen → sobreprecio". Ambas matan el cierre.
- **Fix propuesto:** Dos opciones: (1) ampliar a 16-22 semanas con hitos progresivos, primer hito de valor en semana 4 (recepcion + maestros), o (2) declarar explicitamente la reutilizacion de la plataforma base (sin mencionar otros clientes) — "el sistema esta construido sobre una plataforma ERP de operaciones multi-modulo desarrollada por Eduardo que se configura para el negocio de SAC; esto permite cronogramas mas cortos sin sacrificar calidad". Reformular criterio "un dia completo sin Excel paralelos" → "se inicia operacion en sistema con Excel paralelos opcionales durante X semanas, cierre definitivo cuando se cumplan Y criterios".
- **Esfuerzo:** 2 horas (incluye recalcular hitos).

### B6: Modelo contable del abono a Willard ambiguo y contradictorio entre 3 secciones
- **Severidad:** BLOQUEANTE
- **Lente:** Coherencia interna
- **Ubicacion:** 5.11 linea 702 vs regla 18 linea 1151 vs flujo 6.9 linea 1061 vs P&L seccion 8 linea 1184.
- **Problema:** Tres tratamientos contables incompatibles para el mismo evento. (a) 5.11 + regla 18: "salida al costo, sin ingreso en pesos" → asimetrico, P&L siempre pierde en abonos. (b) Flujo 6.9: "liquidacion de obligacion de maquila" → sugiere ingreso por servicio. (c) P&L: lista "abonos a Willard como servicio de maquila" como linea de ingreso. Como esta hoy, el negocio postconsumo se ve perdedor en P&L cuando es el corazon del negocio.
- **Por que es bloqueante:** Es el modelo contable del producto mas estrategico. Si esta mal o ambiguo, todos los reportes financieros de SAC quedan mal. Y Johana es la primera que lo va a marcar.
- **Fix propuesto:** Decidir el modelo en una sola seccion de referencia con un ejemplo numerico paso a paso. Recomendacion: al recibir baterias Willard se causa ingreso por servicio de maquila a tarifa pactada (en pesos), creando CXC contra Willard, que se compensa al entregar plomo (descarga CXC + sale inventario al costo). De este modo el P&L muestra ingreso + costo correctamente. Validar con Johana.
- **Esfuerzo:** 1 hora doc + 30-45 min sesion con Johana.

### B7: Trazabilidad por colada vendida como capability nuclear pero sin modelo de mezcla de lotes
- **Severidad:** BLOQUEANTE
- **Lente:** Cobertura real
- **Ubicacion:** Seccion 1.3 (promete "trazabilidad uno a uno por colada"), modulo 5.8, regla 13, pregunta 47.
- **Problema:** Hugo lo pidio textualmente. Pero el doc no aborda: (a) mezcla fisica de plomo crudo de 2+ coladas en el mismo molde, (b) que significa "trazabilidad proporcional" matematicamente cuando la refinacion mezcla varios lotes (5.9), (c) FIFO por colada vs eleccion manual de lote y quien decide, (d) identificacion fisica del lote (pregunta 47 sigue abierta — lingote con marca? granel? ambos?).
- **Por que es bloqueante:** Sin un modelo de mezcla + algoritmo de back-trace + etiquetado fisico, "trazabilidad" es marketing. Es Fase 2 pero impacta el modelo de datos de Fase 1 (debe contemplarlo desde el inicio).
- **Fix propuesto:** Sub-modulo en 5.8 que defina: modelo de linked tree con proporciones; algoritmo de back-trace (de un envio refinado → todos los aportantes consumidos); mecanismo de etiquetado fisico (QR de colada en lingote). Levantar con Henry. Mientras tanto marcarlo en el doc como `[BORRADOR — validacion con Henry pendiente]`.
- **Esfuerzo:** 1.5 horas doc + sesion Henry obligatoria.

### B8: Deuda en plomo multi-dimensional sin reglas de cascada entre los 4 contadores
- **Severidad:** BLOQUEANTE
- **Lente:** Cobertura real
- **Ubicacion:** Glosario 2.6, modulo 5.5, regla 4, transcripcion (00:14, 01:04, 01:11).
- **Problema:** Johana dijo 3 veces: hay deuda del horno grande Y deuda del crisol. Ademas hay deuda intersede (Circunvalar → Juan Mina) y deuda Willard postconsumo = **4 contadores de plomo simultaneos**. El doc los trata como variantes pero no define como se descarga cada uno ni que pasa cuando un evento toca varios (ej: al vender plomo puro como abono Willard, ¿se descarga deuda Willard + deuda crisol→grande + deuda intersede en cascada?).
- **Por que es bloqueante:** Sin esto, los 4 saldos van a divergir y van a aparecer descuadres que Johana no podra explicar. Es la angustia central del proyecto.
- **Fix propuesto:** Diagrama de cuentas en kg con cada par debe/acreedor explicito + tabla de reglas de cascada por evento (recepcion postconsumo, salida intersede, cierre de colada, entrega plomo puro a Willard, refinacion, venta nacional). Validar con Johana.
- **Esfuerzo:** 2 horas doc + 1 hora sesion Johana.

### B9: Henry no entrevistado pero modulos 5.8, 5.9, 5.15 disenados como compromisos firmes
- **Severidad:** BLOQUEANTE
- **Lente:** Cobertura + Fidelidad
- **Ubicacion:** Modulos 5.8, 5.9, 5.15; riesgo 8; supuesto 6; pregunta 103.
- **Problema:** Hugo dijo en min 00:09 "llamame a Henry tambien por favor"; Henry **nunca aparecio**. Toda la fundicion (corazon productivo) se diseno con conocimiento del experto, no de SAC. No hay datos de: coladas/dia, duracion, rendimientos, identificacion fisica del plomo crudo, turnos 24/7, handover.
- **Por que es bloqueante:** Henry es responsable real de Juan Mina (no operario). Cuando entre, va a refutar supuestos. Si Fase 2 se planifica antes de la sesion con el, hay retrabajo grande.
- **Fix propuesto:** Marcar secciones 5.8, 5.9 y 5.15 con header visible `[BORRADOR — pendiente validacion con Henry — Juan Mina]`. Subir Henry a Proximo Paso #1 (no #2). Bloquear calendario para sesion antes de iniciar diseno detallado de Fase 2. Tratar al rol Henry como "Jefe de Planta Juan Mina" (autoridad, no operario), no como "operador de fundicion".
- **Esfuerzo:** 30 min doc + agendar sesion.

### B10: Modulo 5.15 Fundentes e Insumos casi vacio — bloqueante para coladas funcionales
- **Severidad:** BLOQUEANTE
- **Lente:** Cobertura real
- **Ubicacion:** Seccion 5.15 (22 lineas de prosa generica).
- **Problema:** El diagrama 1 muestra dos listas concretas y distintas (insumos del horno grande vs fundentes del crisol). El modulo no define: receta por horno con proporciones; politica de sustitucion; mecanismo de prorrateo del costo de fundentes al kg de plomo producido; unidades (m3 para gas/oxigeno vs kg vs L); stock minimo. Sin esto las coladas no costean correctamente.
- **Por que es bloqueante:** El costo unitario del plomo depende de esto. Sin modelo claro, la rentabilidad por colada es incorrecta y todo P&L industrial es inexacto.
- **Fix propuesto:** Partir en 5.15.a (insumos horno grande, vinculado a 5.8) y 5.15.b (fundentes crisol, vinculado a 5.9). Definir politica de costo (prorrateo por kg de plomo producido), politica de sustitucion documentada, unidad de medida por insumo, stock minimo con alerta. Marcar como `[BORRADOR — validar con Henry]`.
- **Esfuerzo:** 2 horas doc + sesion Henry.

### B11: Aplicativo de Jose en limbo politico-tecnico
- **Severidad:** BLOQUEANTE
- **Lente:** Empatia + Cobertura
- **Ubicacion:** Riesgo 11, supuesto 8, preguntas 145-152, mencionado en transcripcion ~15 min.
- **Problema:** Hugo dedica 15 minutos a presentar la app de Jose como activo en uso (entradas/salidas, postconsumo, coladas, inspeccion, panel de compras). El doc lo trata como "decision a tomar en Fase 2" sin propuesta concreta de coexistencia, sin sesion planificada con Jose, sin tratamiento de los datos ya capturados, sin abordar el conflicto politico (Jose es vinculado de la empresa). Riesgo de duplicacion de esfuerzo y de enfriamiento de Hugo.
- **Por que es bloqueante:** Hugo apoya a Jose. Si el doc minimiza su trabajo, Hugo lo lee como falta de respeto. Tecnicamente, si Jose termina la version web en 2-3 semanas, la decision cambia drasticamente.
- **Fix propuesto:** Sesion 1:1 con Jose ANTES de mandar el doc para inventariar exactamente que captura, donde lo almacena (Google Sheets + BD), estado del puerto a web. Proponer 3 caminos concretos en el doc (no como pregunta abierta): (a) la app de Jose alimenta via API el sistema nuevo durante X meses; (b) Jose pasa a ser co-desarrollador de la app movil del sistema; (c) reemplazo escalonado con plan de migracion de datos. Hablar con Hugo primero.
- **Esfuerzo:** 1 hora sesion Jose + 1 hora redaccion + 30 min Hugo.

### B12: "Cuadre y Conciliacion Diaria" — el motivo del proyecto no tiene modulo dedicado
- **Severidad:** BLOQUEANTE
- **Lente:** Cobertura
- **Ubicacion:** Mencionado superficialmente en Dashboard Ejecutivo y flujo 6.11; transcripcion 01:08 ("tomo renglon por renglon") y 00:56 (Hugo: "lo primero saber mis cuentas actualizadas").
- **Problema:** Johana lo describio textualmente como su mayor dolor; Hugo lo confirmo como prioridad #1. El doc lo trata como una linea de bullet ("alertas de cuadre") sin definir: que es una alerta de cuadre, cuando se dispara, como se resuelve, quien la asigna, "OK del dia" que Johana firma.
- **Por que es bloqueante:** Es la promesa central. Sin un modulo concreto, se replica el problema en software (Johana sigue revisando renglon por renglon, ahora en pantalla en vez de Excel).
- **Fix propuesto:** Modulo nuevo 5.X "Cuadre y Conciliacion Diaria" con: tablero de discrepancias del dia (por sede, por tipo: peso despacho≠recepcion, conteo orden≠liquidacion, saldo postconsumo sistema vs Willard, etc.), workflow de asignacion, umbrales que disparan alerta, mecanismo de "OK del dia". Disenarlo CON Johana, no para ella.
- **Esfuerzo:** 2 horas doc + 1 hora Johana.

---

## Hallazgos IMPORTANTES (antes de cerrar alcance pero no bloquea v0.2)

### I1: Edicion de orden de entrada — 3 reglas contradictorias en 3 secciones
- **Lente:** Coherencia. **Ubicacion:** 5.1 lin 345 vs 5.4 lin 446 vs 6.12 lin 1118.
- **Problema:** 5.1 dice "ajuste compensatorio post-liquidacion"; 5.4 dice "edicion limitada con auditoria hasta el pago"; 6.12 dice "anulacion completa si no hay procesamiento posterior".
- **Fix:** Adoptar 6.12 como unica regla — la distincion real es "¿el material ya se proceso/consumio/vendio?", no "¿se liquido?". Armonizar 5.1 y 5.4.
- **Esfuerzo:** 30 min.

### I2: Stock negativo — politica inconsistente entre 4 lugares
- **Lente:** Coherencia. **Ubicacion:** 5.1 lin 343, 5.6 lin 525 y 535, regla 8 lin 1141, regla 24 lin 1157.
- **Problema:** El doc mezcla "avisar" con "bloquear hasta aprobacion" sin patron claro. Hay ademas inconsistencia con decision #8 de EcoBalance (compras bloquean, ventas avisan).
- **Fix:** Tabla explicita de validaciones por evento marcando aviso vs bloqueo vs aprobacion. Politica: "avisar, no bloquear" salvo productos de alto valor (plomo crudo, plomo puro). Validar con Johana.
- **Esfuerzo:** 1 hora.

### I3: Asignacion plomo crudo a Willard — sugerida vs automatica (3 reglas distintas)
- **Lente:** Coherencia. **Ubicacion:** 5.8 lin 602 vs 6.6 lin 1003 vs regla 15 lin 1148.
- **Problema:** "Sugiere" (5.8) ≠ "se asigna automaticamente descargando deuda" (6.6) ≠ "proporcional con ajuste manual" (regla 15).
- **Fix:** El sistema **propone** la asignacion al cerrar colada; el operador la confirma o ajusta antes de pasar a "Finalizada"; al "Finalizada" se descarga deuda. Sin confirmacion explicita, los errores son irreversibles.
- **Esfuerzo:** 30 min.

### I4: Estados de orden de entrada — 5.1 lista estados que ningun flujo transita
- **Lente:** Coherencia. **Ubicacion:** 5.1 lin 344, 6.2 lin 907, 5.4.
- **Problema:** "Borrador → registrada → digitada/clasificada → liquidada → cancelada" en 5.1, pero "digitada/clasificada" no aparece en ningun flujo; 6.2 introduce "pendiente de recepcion" que no esta en 5.1.
- **Fix:** Maquina de estados unica explicita: `borrador (opcional) | pendiente_recepcion (solo desde acta de ruta) | registrada | liquidada | cancelada`. Eliminar "digitada/clasificada".
- **Esfuerzo:** 30 min.

### I5: 5 roles huerfanos referenciados pero no definidos en seccion 4
- **Lente:** Coherencia. **Ubicacion:** "Operario de despacho" (5.11 lin 708, 6.8, 6.10); "Coordinador ambiental" (sec 8 lin 1204); "Supervisor de planta Juan Mina" (6.5 lin 979); "Supervisor de auditoria" (6.11) duplica "Auditor de inventario"; "Coordinador postconsumo" sin nombre.
- **Fix:** Consolidar tabla de roles unica en seccion 4. Definir "Jefe de Planta Juan Mina" como autoridad (Henry). Unificar "Supervisor de auditoria" → "Auditor de inventario". Decidir si "Operario de despacho" es rol propio o subset del operador de bascula. Eliminar "Coordinador ambiental" o fusionarlo con gerencia.
- **Esfuerzo:** 1 hora.

### I6: Validacion de pesos contra "rango historico", reglas tributarias, calibracion de bascula, aging Willard — todos presentados como features pero nunca confirmados
- **Lente:** Fidelidad. **Ubicacion:** 5.1 lin 343 (plausibilidad); 5.4 lin 442 + regla 28 (tributario); regla 31 (calibracion); 5.5 lin 484-486 (aging).
- **Problema:** Ninguno de estos temas fue mencionado por SAC. Las preguntas 16-19, 27, 117-118 los preguntan correctamente pero los modulos ya los dan por hecho.
- **Fix:** Bajar todos a `[PROPUESTA — confirmar con SAC]` en los modulos. Mover las afirmaciones a las preguntas pendientes.
- **Esfuerzo:** 45 min.

### I7: Captura con foto/firma/QR/GPS asumida como funcionalidad core
- **Lente:** Fidelidad + Empatia. **Ubicacion:** 1.3, 5.1, 5.2, 6.1, 6.2, 6.3 (multiples).
- **Problema:** Asume infraestructura (camaras, hardware GPS confiable, capacidad de firma en pantalla para conductores rurales) y presupuesto (tabletas rugerizadas). Hugo solo menciono que conductores llenan papeles a mano.
- **Fix:** Marcar como `[PROPUESTA — depende de presupuesto hardware]` o moverlo a Seccion 13. El supuesto 2 sobre tabletas debe ser pregunta.
- **Esfuerzo:** 30 min.

### I8: Convivencia con World Office no aterrizada
- **Lente:** Cobertura. **Ubicacion:** 1.1 lin 39 (mencion unica), pregunta 95.
- **Problema:** Mencionado de pasada; si SAC sigue con World Office para contabilidad fiscal, el sistema necesita export estructurado al formato WO o vivira en doble realidad eterna.
- **Fix:** Definir alcance de integracion (export Excel/CSV vs API) con Johana. Sesion para revisar el formato real de WO.
- **Esfuerzo:** 30 min doc + 30 min Johana.

### I9: Cierre de periodo — politica muy estricta para realidad de SAC
- **Lente:** Empatia. **Ubicacion:** Modulo 5.16, regla 29.
- **Problema:** "Bloquea edicion retroactiva" pero el ciclo real tiene ajustes tardios constantes (compras liquidadas dias despues, exportaciones cuyo precio final llega meses despues).
- **Fix:** Definir explicitamente que se permite/bloquea post-cierre. Documentar mecanismo de "ajuste post-cierre en periodo abierto" con efecto visible en reporte mensual ya emitido (¿recalcula? ¿nota explicativa?). Validar con Johana.
- **Esfuerzo:** 1 hora.

### I10: Comisionista, prorrateo de comisiones de compras, deuda al supplier — features traidos de EcoBalance sin confirmar
- **Lente:** Neutralidad + Cobertura. **Ubicacion:** 5.4 (comisiones), 5.11 (comisiones), 1.4 (excluye "comisiones complejas con rappels").
- **Problema:** "Fase 1 soporta comisiones basicas" en presente sugiere capacidad existente. SAC casi no menciono comisiones en la reunion.
- **Fix:** Confirmar con Hugo si hay comisionistas hoy y como se liquidan. Si si, levantar el modelo. Si no, mover comisiones a "fuera de alcance Fase 1".
- **Esfuerzo:** 15 min + sesion Hugo.

### I11: 152 preguntas — abrumadoras, sin priorizacion
- **Lente:** Empatia + Calidad de preguntas. **Ubicacion:** Seccion 15.
- **Problema:** Las 152 al mismo nivel jerarquico, sin marcar cuales bloquean cierre de alcance. ~25 son abiertas/anecdoticas; ~15 redundantes. SAC va a pensar "les voy a pagar para responder 152 preguntas?".
- **Fix:** Reducir a ~20-25 criticas con prefijo `[BLOQUEANTE PARA CIERRE DE ALCANCE]`. Resto a anexo. Fusionar grupos redundantes (factores Willard P21-23-32; subproductos P65-70; conectividad P110-118; app Jose P145-152; tributario P16-19-95-96-97).
- **Esfuerzo:** 2 horas.

### I12: 48 preguntas criticas faltantes
- **Lente:** Calidad de preguntas. **Ubicacion:** Auditoria #5 lista 48.
- **Problema:** Faltan temas criticos: cloud vs on-premise (F33), SLA post-go-live (F45), deadline duro de go-live (F46), obligaciones financieras / creditos bancarios (F29), segregacion de funciones anti-lavado (F30), IP de la app de Jose (F42), tolerancia exacta del balance (F4), umbral de diferencia de bascula, factura electronica DIAN (F26), costo de servir Willard (combustible, viaticos), saldos iniciales exactos.
- **Fix:** Agregar Seccion 15.17 (Modelo comercial: presupuesto, modalidad, SLA, deadline) y 15.18 (Compliance/datos). Incluir las 48 faltantes priorizadas.
- **Esfuerzo:** 2 horas.

### I13: Concepto del "Operario de despacho" + reclasificacion al patio no formalizada
- **Lente:** Cobertura + Coherencia. **Ubicacion:** 5.11 lin 708, 6.8, 6.10; supervisor de patio reclasifica referencias (5.1).
- **Problema:** Rol fantasma. Reclasificacion de referencia (cambiar Ref 1 por Ref 2 al digitar) no esta modelada como tipo de ajuste con efectos cross-modulo (decremento bodega general Ref 1 + incremento Ref 2, recalculo de factor Willard, auditoria).
- **Fix:** Definir "reclasificacion de referencia" como tipo de ajuste de inventario con efectos en deuda Willard. Aclarar rol del despachador.
- **Esfuerzo:** 45 min.

### I14: Tolerancia documentada del balance — Johana no acepta tolerancia
- **Lente:** Empatia. **Ubicacion:** Criterios de aceptacion Fase 1.
- **Problema:** "El balance general muestra cifras consistentes con los Excel actuales (con tolerancia documentada)" — Johana cuadra a la unidad.
- **Fix:** Definir con ella el numero exacto (¿0 kg? ¿1%? ¿$X COP por categoria?) antes de incluirlo en criterios de aceptacion. Si la respuesta es "0", reformular el criterio para no prometer tolerancia.
- **Esfuerzo:** 15 min doc + sesion Johana.

### I15: Erwin como riesgo de boicot — sin conversacion 1:1 previa
- **Lente:** Empatia. **Ubicacion:** Seccion 4 (rol redefinido), riesgo 2.
- **Problema:** Doc "asciende" a Erwin a "Auditor de inventario" sin que el haya participado. Su memoria de oficio (los 5 Excel, la logica de salida/entrada) es indispensable para la migracion.
- **Fix:** Conversacion 1:1 con Erwin ANTES de mandar el doc. Mostrar concretamente como cambia su dia a dia (con metrica de velocidad de captura: "una orden de entrada se completa en ≤90 segundos"). Validar con el que el nuevo rol le calza.
- **Esfuerzo:** 1 hora reunion.

### I16: "Por organizacion" y numeracion "por org" — leak multi-tenant en multiples lugares
- **Lente:** Neutralidad. **Ubicacion:** Lin 357, 1145, 1267.
- **Fix:** Cambiar todos los "por organizacion" → "por sede dentro de SAC" o "global". Eliminar el bullet "Aislamiento por organizacion" o reescribirlo sin referencia a "otros clientes".
- **Esfuerzo:** 15 min.

### I17: Estructura por modulo identica 16 veces — huella de template
- **Lente:** Neutralidad. **Ubicacion:** Seccion 5 entera.
- **Fix:** Variar estructura por modulo (algunos narrativos, otros bullets, otros con flujo, otros con tabla). Romper la simetria visual del template.
- **Esfuerzo:** 1.5 horas.

### I18: P&L Mensual, Balance historico as_of_date, Excel con 2 hojas — features muy especificas que delatan EcoBalance
- **Lente:** Neutralidad. **Ubicacion:** Lin 1185, 526, 808, 465, 725.
- **Fix:** Reescribir en lenguaje de negocio: "el sistema debe permitir consultar saldos a una fecha pasada"; "exportar reportes a Excel incluyendo el detalle por linea de material"; "P&L con vista comparativa mes a mes con dia de corte configurable si no coincide con calendario".
- **Esfuerzo:** 30 min.

### I19: Sin presupuesto, sin SLA, sin continuidad de Eduardo
- **Lente:** Empatia. **Ubicacion:** Ausente.
- **Problema:** Hugo no puede aprobar 14 semanas sin saber el costo. Riesgo: SAC pide propuesta comercial antes de iterar el doc — y este doc completo se desperdicia.
- **Fix:** Agregar seccion con orden de magnitud de inversion, modelo (fijo / hora / suscripcion), SLA post-go-live (tiempo de respuesta a incidente critico), continuidad (equipo de soporte si Eduardo se enferma).
- **Esfuerzo:** 1 hora.

### I20: Fase 1 no entrega valor visible para Hugo (sin coladas, sin exportaciones completas)
- **Lente:** Empatia. **Ubicacion:** Seccion 11.
- **Problema:** Hugo pidio "balance en tiempo real" pero sin coladas formalizadas el plomo crudo no tiene costo ni trazabilidad; en semana 10 va a no ver el resultado y a desconfiar.
- **Fix:** Considerar incluir balance simplificado de Willard en Fase 1 (sumas en kg sin trazabilidad por colada) — Hugo pidio "saldo en kg de Willard hoy". Definir hito explicito de "primer balance visible para Hugo" en semana 4-6.
- **Esfuerzo:** 1 hora.

---

## Hallazgos MENORES (mejoras de pulido)

### M1: Factor Willard con "fecha desde/hasta" rompe patron append-only de EcoBalance
- **Lente:** Coherencia. **Ubicacion:** 5.3 lin 423, regla 5.
- **Fix:** Cambiar a "fecha desde" unicamente; "hasta" se infiere del siguiente registro. Alinear con append-only.
- **Esfuerzo:** 10 min.

### M2: Refinacion: regla 16 afirma "parte de plomo crudo" pero pregunta 53 lo cuestiona
- **Fix:** Reformular regla 16 como "Por defecto la refinacion parte de plomo crudo; capacidad de aceptar otras entradas a confirmar con SAC".
- **Esfuerzo:** 5 min.

### M3: Pseudo-materiales de merma ("merma molino", "merma picado") referenciados pero no en catalogo
- **Lente:** Coherencia. **Ubicacion:** 5.7 lin 561, regla 10.
- **Fix:** Agregar al catalogo de materiales (5.3) los pseudo-materiales de merma o cambiar el modelo a campo `waste_quantity` del registro de transformacion.
- **Esfuerzo:** 15 min.

### M4: "Cuenta de perdida o recuperacion operativa" mencionada pero no definida
- **Ubicacion:** 5.6 lin 537, regla 36, 6.5 lin 979. **Fix:** Listar en 5.13 catalogo minimo de cuentas internas.
- **Esfuerzo:** 10 min.

### M5: Plomo a devolver — glosario lista 3 modalidades pero seccion 8 solo 2 reportes (falta deuda inter-horno)
- **Fix:** Agregar reporte "Estado de deuda inter-horno" o aclarar que se reporta como sub-vista del intersede.
- **Esfuerzo:** 10 min.

### M6: "Receta de produccion" definida 2 veces en glosario (lin 113 y 159)
- **Fix:** Eliminar una.
- **Esfuerzo:** 2 min.

### M7: Duplicaciones de nomenclatura (Liquidador/Johana, plomo a devolver/deuda/saldo, BPAU/UBA, sede Juan Mina/sede de fundicion)
- **Fix:** Consolidar sinonimos en glosario; usar termino canonico en todo el resto.
- **Esfuerzo:** 30 min.

### M8: "Recirculacion" como tipo de movimiento pero sin flujo
- **Ubicacion:** 5.6 lin 518.
- **Fix:** Definir mini-flujo de recirculacion escoria/polvoducto en seccion 6, o eliminar como tipo y modelarlo como atributo del consumo en colada.
- **Esfuerzo:** 15 min.

### M9: "Bunker de carga", "lingotera", "moldes", "tolva o playa de pre-mezcla" — fisica del horno inventada
- **Fix:** Marcar como `[BORRADOR — validar con Henry]` o eliminar hasta sesion.
- **Esfuerzo:** 5 min.

### M10: Anglicismos sin traducir (snapshot, idempotency, FIFO, aging, cutoff, sunken costs[sic], flagged, cross-sede, go-live, running balance, COGS)
- **Fix:** Reemplazar por equivalentes en espanol o explicar en primera mencion: instantanea, clave de idempotencia, antiguedad, dia de corte, costo de venta, etc.
- **Esfuerzo:** 45 min.

### M11: Numero "5 Excel" presentado como hecho pero Johana enumero entre 4 y 7
- **Fix:** "Varios cuadros Excel paralelos (Circunvalar, Molino, Planta/Maquilas, Exportaciones, Postconsumo, Consecutivos)" sin numero rigido.
- **Esfuerzo:** 5 min.

### M12: "Bateria de vasos: antenas marinas SAN/acrilico" — material "SAN" inventado
- **Fix:** Eliminar "SAN/acrilico"; dejar solo descripcion de uso.
- **Esfuerzo:** 2 min.

### M13: "Bateria de moto: corazas acrilicas a picadores" — detalle inventado
- **Fix:** Quitar "(corazas acrilicas)" o validar con Erwin.
- **Esfuerzo:** 2 min.

### M14: Bateria estacionaria asociada a "sistemas solares" — no mencionado
- **Fix:** Eliminar "sistemas solares" o marcar como ejemplo del autor.
- **Esfuerzo:** 1 min.

### M15: Ejemplo "631 kg para 10 unidades" — Johana solo dio 631 kg
- **Fix:** Eliminar "para 10 unidades" del ejemplo. (Tambien parte del fix B3).
- **Esfuerzo:** 2 min.

### M16: Tono de marketing en seccion 1.3 ("vision"), 5.5 ("modulo mas distintivo"), 5.1 ("elimina la doble y triple digitacion")
- **Fix:** Bajar tono a descriptivo neutro. "Lo que buscamos lograr es X, asumiendo Y".
- **Esfuerzo:** 30 min.

### M17: Matriz RBAC 13×15 muy granular para v0.1
- **Fix:** Mantener pero marcada como `[BORRADOR — refinar con SAC]` y reducir a 4 niveles (Ver / Operar / Administrar / Aprobar) en lugar de V/C/E/A/Ap.
- **Esfuerzo:** 45 min.

### M18: Lista de productos del molino: "lodo/pasta/oxido" fusionados — Hugo los menciono separados
- **Fix:** Verificar con SAC si son sinonimos o entidades distintas en su jerga.
- **Esfuerzo:** Pregunta en sesion.

### M19: "Mantenimiento de activos, S&OP, salud ocupacional como fuera-de-alcance" — listar como fuera puede sembrar la idea de que estaban en juego
- **Fix:** Acortar la lista de "fuera de alcance" a items que SAC efectivamente menciono.
- **Esfuerzo:** 15 min.

### M20: 12 supuestos / 15 riesgos — exceso para v0.1, abruma
- **Fix:** Consolidar y priorizar; los riesgos politicos (Jose, Henry, Erwin, Johana) van separados.
- **Esfuerzo:** 30 min.

---

## Top 10 preguntas mas criticas para SAC

Las que SI o SI deben responderse antes de cerrar contrato. Marcar con prefijo `[BLOQUEANTE PARA CIERRE DE ALCANCE]` en seccion 15.

1. **Factores Willard completos:** tabla por referencia con vigencia + quien autoriza cambios + retroactivo o prospectivo (fusion P21+P22+P23+P32+F11).
2. **Contrato Willard:** deuda en crudo o puro, tolerancia, plazo de devolucion, saldo negativo permitido (fusion P24+P25+P26+P27+P28+F8).
3. **Saldos iniciales exactos al corte:** deuda Willard, deuda intersede, CXP, CXC, obligaciones financieras / creditos bancarios, inventarios fisicos por bodega (P142 + F29 + F40).
4. **Cloud vs on-premise:** decision arquitectonica que cambia dimensionamiento y costo (F33 nueva — Hugo menciono que esta poniendo un servidor on-premise).
5. **Deadline duro de go-live:** auditoria externa, requerimiento legal? Define si Fase 1 cabe en 10-14 vs 16-22 semanas (F46 nueva).
6. **Liquidacion por unidades pero pago por peso:** ¿la practica de Johana (separar inventario y liquidacion) se respeta o se cambia? Tolerancia de bascula exacta (P13 + F4 + B3).
7. **Colada con multiples remisiones origen:** una colada consume 1 o N remisiones de salida Circunvalar→Juan Mina? Define complejidad de trazabilidad (F15 + P44).
8. **Integracion con World Office:** profundidad (export Excel/CSV, API, manual) y codigos de cuenta contable a referenciar (P95 + F41).
9. **Aplicativo de Jose:** decision de reemplazo/integracion/coexistencia + propiedad intelectual + rol futuro de Jose (P152 + F42).
10. **Segregacion de funciones anti-lavado:** quien digita NO puede liquidar al mismo proveedor? Define matriz RBAC y bloquea decisiones de Fase 1 (F30 + P100).

Adicionales criticos del modelo comercial (Seccion nueva 15.17): presupuesto orientativo, modelo de pago, SLA post-go-live, continuidad si Eduardo se incapacita.

---

## Riesgos de adopcion detectados

R1. **Johana en modo defensivo desde primera lectura** — su practica reinterpretada (B3) + tolerancia del balance impuesta (I14) + automatizaciones que le quitan control (I3 abonos automaticos, I2 anticipos automaticos) sin negociacion previa.

R2. **Erwin sintiendose desplazado, no promovido** — rol redefinido sin participacion (I15). Riesgo de boicot pasivo-agresivo + perdida de memoria de oficio en la migracion.

R3. **Jose como bomba politica** — Hugo lo apoya; doc minimiza su trabajo (B11). Riesgo de enfriamiento de Hugo y duplicacion de esfuerzo.

R4. **Henry no consultado** — modulos 5.8/5.9/5.15 son supuestos (B9). Riesgo de retrabajo masivo + perdida de credibilidad cuando aparezca y contradiga.

R5. **Sobre-ingenieria percibida** — 16 modulos + 40 reglas + 152 preguntas para PYME. Riesgo de buscar proveedor mas simple/barato.

R6. **Cronograma sin precio y sin equipo** — Hugo no puede aprobar 14 semanas sin saber costo (B5 + I19). Riesgo de que pidan propuesta comercial antes de iterar el doc, dejando todo este trabajo en el aire.

R7. **Fase 1 sin valor visible para Hugo** — sin coladas/exportaciones completas, no ve "balance en tiempo real" prometido (I20). Riesgo de desconfianza en semana 10.

R8. **152 preguntas como senal de "no saben nada todavia"** — erosiona confianza (I11).

R9. **Sin mockups** — cliente compra "lo que se ve"; doc 100% textual = imagina lo peor.

R10. **Operacion dual con Excel sin plan operativo** — quien hace doble entrada, hasta cuando, con que criterio de corte. Donde mas proyectos mueren.

R11. **"Cierre de periodo bloquea edicion retroactiva"** suena a camisa de fuerza para SAC, que tiene ajustes tardios constantes (I9).

R12. **Asesor tecnico contratado por SAC detecta huellas de EcoBalance** y mete sospecha de sobreprecio (B1).

---

## Plan de mitigacion sugerido

### 1. Cambios pre-revision con Eduardo (Eduardo hace estos cambios solo, ~1-2 dias)

a. **Pasada de neutralizacion completa (B1, I16, I17, I18, M9, M10, M16)** — eliminar 24 leaks de EcoBalance. 4 horas.
b. **Reasignacion de fases (B2)** — subir 5.11 (venta + abono Willard), parte de 5.10 (inventario subproductos) y modo degradado de 5.2 a Fase 1. 2 horas.
c. **Marcar bloques inventados con `[PROPUESTA — validar]` o `[BORRADOR — pendiente Henry]` (B4, B9, B10, M9)** — secciones 2.4, 2.7, 5.8, 5.9, 5.15, captura foto/firma/GPS. 2 horas.
d. **Consolidar tabla de roles (I5)** y eliminar roles huerfanos. 1 hora.
e. **Armonizar reglas contradictorias (I1, I2, I3, I4)** — edicion, stock negativo, asignacion Willard, estados. 2 horas.
f. **Reducir 152 preguntas a 20-25 criticas con prefijo `[BLOQUEANTE PARA CIERRE]` + anexo (I11)**. 2 horas.
g. **Agregar 48 preguntas faltantes prioritizadas + seccion 15.17 (modelo comercial) + 15.18 (compliance) (I12)**. 2 horas.
h. **Reformular cronograma (B5)** — 16-22 semanas con hitos progresivos, primer hito de valor visible en semana 4. 1 hora.
i. **Resumen ejecutivo de 1 pagina al inicio** — problema, solucion, 3 fases, siguiente paso (para Hugo). 1 hora.
j. **Hallazgos menores M1-M20** — pulido cosmetico. 3 horas en bloque.

**Total estimado: 20-22 horas de trabajo concentrado.**

### 2. Cambios durante revision con Eduardo (decisiones de producto)

a. **Modelo contable del abono Willard (B6)** — decidir entre ingreso por servicio vs solo costo. Eduardo + Johana en sesion.
b. **Practica de liquidacion por peso de Johana (B3)** — respetar separacion o cambiar. Eduardo + Johana.
c. **Aplicativo de Jose (B11)** — 3 caminos concretos; Eduardo decide cual proponer despues de sesion con Jose.
d. **Modulo de Cuadre Diario (B12)** — Eduardo disena con Johana.
e. **Modelo de deuda en plomo multi-dimensional (B8)** — diagrama de cuentas en kg + cascadas. Eduardo + Johana.
f. **Trazabilidad por colada — modelo de mezcla (B7)** — Eduardo borrador, validacion con Henry obligatoria.
g. **Mockups de 3 pantallas criticas** — orden de entrada (Erwin), liquidacion (Johana), dashboard (Hugo). Eduardo + opcionalmente Jose.
h. **Presupuesto y modelo comercial (I19)** — Eduardo define.

### 3. Cambios despues de primer feedback de SAC (v0.2)

- Resultado de sesion 1:1 con Johana → ajustar practica de liquidacion + modelo abono Willard + tolerancia balance + modulo cuadre.
- Resultado de sesion 1:1 con Erwin → ajustar rol y plan de migracion + metricas de velocidad de captura.
- Resultado de sesion 1:1 con Jose → camino concreto de coexistencia/integracion + plan tecnico.
- Resultado de sesion con Henry → reescribir 5.8/5.9/5.15 + factores reales + modelo de trazabilidad.
- Respuesta a 20 preguntas bloqueantes → cerrar alcance Fase 1 y emitir propuesta comercial formal.

---

## Anexo: tracker de hallazgos

| ID | Lente | Seccion | Severidad | Titulo | Estado |
|---|---|---|---|---|---|
| B1 | Neutralidad | Multiples (1267, 447, 706, 538, 277) | BLOQUEANTE | Frases-bandera de EcoBalance | Open |
| B2 | Coherencia | 11, 5.5, 5.7, 5.11 | BLOQUEANTE | Modulos clave fuera de Fase 1 rompen Hito 2 | Open |
| B3 | Fidelidad/Empatia | 5.4 (441-447) | BLOQUEANTE | Liquidacion por peso reinterpreta a Johana | Open |
| B4 | Fidelidad | 2.4, 2.7, 5.10 | BLOQUEANTE | Insumos/subproductos/regulacion inventados | Open |
| B5 | Neutralidad/Empatia | 11 (1304) | BLOQUEANTE | Cronograma 10-14 semanas irreal o sospechoso | Open |
| B6 | Coherencia | 5.11, 6.9, 8 | BLOQUEANTE | Modelo contable abono Willard contradictorio | Open |
| B7 | Cobertura | 5.8 | BLOQUEANTE | Trazabilidad colada sin modelo de mezcla | Open |
| B8 | Cobertura | 2.6, 5.5 | BLOQUEANTE | Deuda multi-dim sin reglas de cascada | Open |
| B9 | Cobertura/Fidelidad | 5.8, 5.9, 5.15 | BLOQUEANTE | Henry no entrevistado | Open |
| B10 | Cobertura | 5.15 | BLOQUEANTE | Modulo Fundentes vacio | Open |
| B11 | Empatia/Cobertura | 14, 15.16 | BLOQUEANTE | App de Jose en limbo politico | Open |
| B12 | Cobertura | (ausente) | BLOQUEANTE | Modulo Cuadre Diario ausente | Open |
| I1 | Coherencia | 5.1, 5.4, 6.12 | IMPORTANTE | Edicion de orden — 3 reglas contradictorias | Open |
| I2 | Coherencia | 5.1, 5.6, 8, 24 | IMPORTANTE | Stock negativo politica inconsistente | Open |
| I3 | Coherencia | 5.8, 6.6, 15 | IMPORTANTE | Asignacion Willard sugerida vs automatica | Open |
| I4 | Coherencia | 5.1, 6.2 | IMPORTANTE | Estados de orden — flujo no transita | Open |
| I5 | Coherencia | 4, 5.11, 6.5, 6.8, 6.10, 6.11, 8 | IMPORTANTE | 5 roles huerfanos | Open |
| I6 | Fidelidad | 5.1, 5.4, 5.5 | IMPORTANTE | Validacion plausibilidad/tributario/calibracion/aging asumido | Open |
| I7 | Fidelidad/Empatia | 1.3, 5.1, 5.2, 6.x | IMPORTANTE | Foto/firma/QR/GPS asumido | Open |
| I8 | Cobertura | 1.1, 95 | IMPORTANTE | World Office sin alcance | Open |
| I9 | Empatia | 5.16, 29 | IMPORTANTE | Cierre de periodo demasiado estricto | Open |
| I10 | Neutralidad/Cobertura | 5.4, 5.11, 1.4 | IMPORTANTE | Comisiones traidas de EcoBalance | Open |
| I11 | Empatia/Preguntas | 15 | IMPORTANTE | 152 preguntas abrumadoras sin prioridad | Open |
| I12 | Preguntas | 15 | IMPORTANTE | 48 preguntas criticas faltantes | Open |
| I13 | Cobertura/Coherencia | 5.1, 5.11 | IMPORTANTE | Reclasificacion + operario despacho | Open |
| I14 | Empatia | Criterios Fase 1 | IMPORTANTE | Tolerancia balance no negociada con Johana | Open |
| I15 | Empatia | 4 | IMPORTANTE | Erwin sin conversacion 1:1 previa | Open |
| I16 | Neutralidad | 357, 1145, 1267 | IMPORTANTE | "Por organizacion" / aislamiento multi-tenant | Open |
| I17 | Neutralidad | Seccion 5 | IMPORTANTE | Estructura por modulo identica 16 veces | Open |
| I18 | Neutralidad | 465, 526, 725, 1185 | IMPORTANTE | P&L mensual / balance historico / Excel 2 hojas | Open |
| I19 | Empatia | (ausente) | IMPORTANTE | Sin presupuesto/SLA/continuidad | Open |
| I20 | Empatia | 11 | IMPORTANTE | Fase 1 sin valor visible para Hugo | Open |
| M1 | Coherencia | 5.3, 5 | MENOR | Factor Willard fecha-hasta rompe append-only | Open |
| M2 | Coherencia | 16, 53 | MENOR | Refinacion: regla contradice pregunta abierta | Open |
| M3 | Coherencia | 5.7, 10 | MENOR | Pseudo-materiales merma sin catalogo | Open |
| M4 | Coherencia | 5.6, 5.13, 36 | MENOR | Cuenta perdida operativa sin definir | Open |
| M5 | Coherencia | 2.6, 8 | MENOR | Falta reporte deuda inter-horno | Open |
| M6 | Coherencia | 2 | MENOR | Receta de produccion definida 2 veces | Open |
| M7 | Coherencia | 2 | MENOR | Duplicaciones de nomenclatura | Open |
| M8 | Coherencia | 5.6 | MENOR | "Recirculacion" sin flujo | Open |
| M9 | Fidelidad | 2.2, 3.4, 6.6 | MENOR | Fisica del horno inventada | Open |
| M10 | Neutralidad | Multiples | MENOR | Anglicismos sin traducir | Open |
| M11 | Fidelidad | 1.1, 1.2 | MENOR | "5 Excel" presentado como hecho | Open |
| M12 | Fidelidad | 2.1 | MENOR | "SAN/acrilico" inventado | Open |
| M13 | Fidelidad | 2.1 | MENOR | "Corazas acrilicas" inventado | Open |
| M14 | Fidelidad | 2.1 | MENOR | "Sistemas solares" inventado | Open |
| M15 | Fidelidad | 5.4, 6.1 | MENOR | "631 kg / 10 unidades" — 10 unidades inventadas | Open |
| M16 | Neutralidad | 1.3, 5.5, 5.1 | MENOR | Tono de marketing | Open |
| M17 | Neutralidad | 9 | MENOR | Matriz RBAC muy granular para v0.1 | Open |
| M18 | Fidelidad | 1.1 | MENOR | Lodo/pasta/oxido fusionados | Open |
| M19 | Empatia | 1.4, 12 | MENOR | Lista "fuera de alcance" siembra ideas | Open |
| M20 | Empatia | 13, 14 | MENOR | 12 supuestos + 15 riesgos abruma | Open |

**Conteo final:** 12 BLOQUEANTES + 20 IMPORTANTES + 20 MENORES = **52 hallazgos abiertos**.
