# Documento de Requerimientos Funcionales — Soluciones Ambientales del Caribe (SAC) — v0.6

**Version:** 0.6 (incrementa desde v0.5 tras la reunion con Johana y Erwin del 2026-08-03, ya con el sistema en produccion y el equipo probandolo)
**Fecha:** Agosto 2026
**Estado:** Interno del equipo EcoBalance. Documento espejo cara al cliente: `propuesta-alcance-cliente.md` (v0.5).
**Autor:** Eduardo Chain

> **Sobre la v0.6 (2026-08-04).** Version corta: **dos correcciones**, ambas nacidas de tener el sistema ya operando.
>
> 1. **§7.3 — un proveedor por LÍNEA en compra regular.** La regla de v0.4 ("una entrada por proveedor") se **relaja unicamente en compra regular de chatarra** y **se conserva intacta en postconsumo Willard**, que es donde vive su razon. Detonante: Johana, el 2026-08-03, ya con el formulario a la vista — una ruta trae de 10 a 15 proveedores en **una sola descarga fisica**, todos los dias. Cada proveedor sigue teniendo su propia compra, su remision, sus retenciones y su liquidacion independiente; lo unico que cambia es cuantos documentos de captura se digitan.
> 2. **La comision de Green Loop NO se prorratea al costo** — es un gasto causado ([decision #83], desplegada). El texto de v0.5 quedo obsoleto en **dos** lugares: §2.4 (tabla de actores) y §7.3 punto 5. Ambos corregidos.
>
> Lo demas de la v0.5 sigue vigente sin cambios.

> **Sobre la v0.5.** La v0.5 incorpora los resultados de la visita a planta del 2026-07-02 (sesion de trabajo con Johana en Juan Mina; Hugo valido las decisiones por WhatsApp), que cerro TODAS las preguntas tecnicas que quedaban abiertas en v0.4:
>
> - **Maquila interna con causacion al envio** (cambio mayor de §5): $1.500/kg de plomo equivalente se causa al confirmar el traslado CV→JM, y $300/kg adicional al salir el material del crisol — en ambos momentos como **par de `MoneyMovement` enlazados** (gasto Circunvalar + ingreso Juan Mina, sin cuenta). El modelo de causacion diferida FIFO de v0.4 se **descarta** (validado por Hugo Y por Johana — ver nota de decision en §5.2 y Anexo F).
> - **Crisol confirmado como quinta cuenta** en kg — se elimina la alternativa de 4 cuentas. Razon del cliente: medir la eficiencia por etapa.
> - **Willard baterias con sub-saldos por sede** (Barranquilla / Bogota); los kg pasan al sub-saldo Barranquilla cuando el material llega fisicamente a Circunvalar.
> - **Green Loop cerrado**: caja provista por SAC, compras a nombre del proveedor real, comision $100/kg ~~prorrateada al costo ([decision #30])~~ → **corregido en v0.6: causada como gasto** ([decision #83], ver §7.3 punto 5).
> - **Eco Alloys** — nombre correcto del proyecto de aluminio (antes escrito "Equalois" segun transcripcion).
> - **Panel de excepciones** reemplaza el "tablero de cuadre" (§10.3): con captura unica el cuadre renglon-por-renglon desaparece por construccion; el panel muestra solo lo anomalo.
> - **Tarifas corregidas y con momento de facturacion definido**: flete planta–Willard $37/kg (antes $38); maquila Willard y flete planta se facturan por cada entrega; flete BOG-BAQ $216/kg mensual + transporte fisico tercerizado como gasto variable.
> - **Cajas menores: una por sede**, todas operadas por Yurani; el gasto hereda la sede de la CAJA usada, no del usuario.
> - **Liquidacion por peso cerrada** (P2): la composicion se conoce al recibir; el valor pagado se reparte por costo promedio historico.
> - Quedan abiertas SOLO P1 (volumenes pico), P55 (fecha de corte) y P64 (modalidad comercial) — ninguna es tecnica (§18).
>
> Este documento **no se envia al cliente** — es la especificacion tecnica que sostiene la propuesta comercial resumida y guia la implementacion.

**Control de versiones:**

| Version | Fecha | Cambios principales |
|---|---|---|
| 0.3 | 2026-06 | Primer outline tecnico completo (opciones A/B/C modelo Willard, cuentas kg sin numero cerrado). |
| 0.4 | 2026-06-30 | Cierra arquitectura hibrida: tarifas Willard con cita, 5 cuentas kg propuestas, causacion diferida FIFO, warehouse_id en MoneyMovement, roles reales, 4 reviews adversariales + cierres sesion 2026-06-30 con Daniel. |
| 0.5 | 2026-07 | Resultados visita a planta 2026-07-02 (Johana en sitio; Hugo por WhatsApp): maquila interna causada al envio (par de MMs enlazados; se descarta el modelo diferido FIFO), crisol confirmado (5 cuentas), sub-saldos Willard baterias por sede, Green Loop cerrado ($100/kg prorrateada), Eco Alloys, panel de excepciones, tarifas $37/$216 con momentos de facturacion, cajas menores por sede (Yurani), liquidacion por peso cerrada. |
| 0.5 — errata | 2026-07-15 | Conteo de clientes en produccion corregido en todo el documento: son **tres** (Costa, Biogreen, MetaRecycling) — "Meta" y "MetaRecycling" eran el mismo cliente contado dos veces. Verificado contra la BD de produccion (tabla organizations). Hallazgo del agente QA en su arranque de ciclo. |
| 0.5 — errata 2 | 2026-07-15 | Precisada la asistencia del 2026-07-02: sesion de trabajo con Johana en Juan Mina; Hugo valido las decisiones por WhatsApp (no estuvo presente, confirmado por Daniel). Las validaciones "por Hugo Y por Johana" se mantienen — ambas ocurrieron, por canales distintos. |
| 0.6 | 2026-08-04 | Reunion con Johana y Erwin del 2026-08-03, con el sistema ya en produccion. **(1)** §7.3: un proveedor por **linea** en compra regular — la regla "una entrada por proveedor" de v0.4 se relaja SOLO ahi y se conserva intacta en postconsumo Willard, donde vive su razon (una ruta trae 10-15 proveedores en una sola descarga fisica, a diario). **(2)** La comision de Green Loop **NO se prorratea al costo**: es gasto causado ([decision #83], desplegada). El error de v0.5 estaba repetido en **ocho** lugares del documento (§2.4, §7.3 punto 5, §8, tabla de categorias de gasto, tabla de entidades reusadas, tabla de decisiones aplicables, Q-viva.3 y el log de preguntas) — todos corregidos. **(3)** `inbound_orders.third_party_id` pasa a nullable en §11.1.12. |

---

## 0.1 Como leer este documento

El documento esta organizado en cuatro capas que van de negocio a implementacion. La lectura recomendada depende del rol: si el lector busca decidir alcance, lee §1–§3 y §16; si busca entender el modelo de datos, lee §4–§9 y §11; si busca implementar, lee §11–§15 y los anexos.

| Capa | Secciones | Contenido |
|---|---|---|
| Negocio y contexto | §1–§3 | Resumen ejecutivo, contexto SAC, glosario, mapa de flujos |
| Modelo funcional por flujo | §4–§10 | Cuentas en kg, maquilas, inventario, comerciales, gastos, reportes |
| Implementacion tecnica | §11–§15 | Modelo de datos, endpoints, frontend, RBAC, migracion |
| Plan y anexos | §16–§19 + Anexos | Roadmap por fases, riesgos, preguntas pendientes, anexos tecnicos |

### Convencion de marcas

Cada componente del modelo (tabla, endpoint, pantalla, decision) esta etiquetado para que un lector pueda inferir el impacto sobre el codigo existente sin abrir el repo:

| Marca | Significado |
|---|---|
| [NUEVO] | Componente que se construye desde cero. No existe hoy en EcoBalance. |
| [MODIFICADO] | Extension a algo existente. Tipicamente un campo nullable, un enum ampliado o un parametro opcional. |
| [REUTILIZADO #N] | Reusa la decision N del `CLAUDE.md` sin cambios. |
| [PENDING-CONFIRM] | Requiere validacion con el cliente (Hugo/Johana) antes de implementar. |
| [PENDING-DESIGN] | Requiere diseño tecnico adicional (no bloqueado por cliente pero si por arquitectura). |
| [BLOQUEANTE-CRITICO] | Si no se resuelve antes de codificar, cambia el modelo. |

### Glosario rapido de terminos ambiguos

Tres terminos aparecen intercambiablemente en las conversaciones con el cliente y se prestan a confusion cuando se pasan al modelo. Se fijan a continuacion:

| Termino | Significado en este documento |
|---|---|
| Warehouse | Modelo tecnico SQL de EcoBalance (`warehouses` tabla, `id` UUID). Se escribe con mayuscula y en ingles solo cuando se refiere al modelo. |
| Sede | Ubicacion operativa cara al negocio: Circunvalar (CV), Juan Mina (JM), Bogota (BOG). Se escribe en minuscula y en español cuando se habla del negocio. |
| Bodega | Instalacion fisica dentro de una sede. Puede haber varias bodegas por sede (recepcion, molino, JM-TRANSITO, etc.). |

El mapeo entre las tres capas es 1:1 en la topologia base: `Warehouse(CV)` ↔ sede Circunvalar ↔ bodega principal de Circunvalar. Cuando el texto narrativo dice "sede", el modelo tecnico entiende `warehouse_id`; cuando dice "Warehouse", el negocio ya no aplica.

El documento distingue ademas dos usos diferentes de la palabra **maquila** que en las transcripciones aparecen indiferenciados:

- **Maquila Willard** (§6): servicio que SAC presta a Willard procesando su postconsumo (baterias y drosses) y cobrando una tarifa contractual de $2.097/kg de plomo entregado (Hugo, reunion noche 2026-06-26). Genera ingreso real.
- **Maquila intersede** (§5): servicio que Juan Mina presta a Circunvalar (o Bogota) procesando material de otra sede. Se causa **al enviar**: $1.500/kg de plomo equivalente al confirmar el traslado CV→JM, mas $300/kg adicional al salir el material del crisol (cerrado en visita 2026-07-02, validado por Hugo y Johana). Es una tarifa interna — gasto de la sede origen e ingreso de Juan Mina — que se excluye del consolidado SAC porque las tres sedes comparten NIT. Tarifas sugeridas y parametrizables.

### Cross-references

Cada seccion de negocio (§1–§10) tiene su contraparte tecnica en §11–§15. Cuando el texto necesita apuntar a otra seccion se usa la forma "ver §X.Y"; cuando apunta a una decision existente del `CLAUDE.md` se usa "[decision #N]" o "[REUTILIZADO #N]".

### Lo que NO esta en este documento (vs v0.3)

Se movieron o eliminaron tres bloques que existian en v0.3:

- La matriz RBAC "roles ilustrativos" del v0.3 se rehizo con roles reales validados y esta en §14 con permisos concretos por endpoint.
- Las 71 preguntas dispersas del v0.3 se consolidaron en §18 y en el Anexo F, clasificadas entre bloqueantes de visita, resolubles en implementacion, Fase 2 y Fase 3.
- Las opciones A/B/C sobre modelo Willard desaparecen: Hugo cerro Q7 con cita explicita, ver §6.1.

---

## 0.2 Tabla de contenidos

Indice completo del documento con nivel de detalle hasta §X.Y. Anexos al final.

| Seccion | Titulo |
|---|---|
| 0.1 | Como leer este documento |
| 0.2 | Tabla de contenidos |
| 0.3 | Mapeo propuesta-cliente vs outline tecnico |
| 0.4 | Decisiones cerradas vs asumidas — resumen ejecutivo |
| 1 | Resumen ejecutivo y filosofia de la arquitectura |
| 1.1 | Problema operativo concreto (estado actual SAC) |
| 1.2 | Vision del sistema |
| 1.3 | Las 5 capacidades centrales |
| 1.4 | Filosofia de la arquitectura hibrida |
| 1.5 | Diferencias clave vs v0.3 |
| 2 | Contexto del cliente SAC |
| 2.1 | Estructura societaria (1 sociedad, 3 sedes operativas) |
| 2.2 | Sedes y su rol operativo |
| 2.3 | Unidades de negocio (ortogonales a sede) |
| 2.4 | Organigrama y roles validados |
| 2.5 | Volumen y escala operativa |
| 2.6 | Proyectos especiales y Molino (modelado) |
| 3 | Modelo conceptual de negocio |
| 3.1 | Glosario del negocio |
| 3.2 | Referencias y materiales (mapeo N:1 con Willard) |
| 3.3 | Los cuatro flujos centrales |
| 3.4 | Mapa visual de flujos fisicos y financieros |
| 3.5 | Politica contable 'utilidad cero gerencial' |
| 4 | Las 5 cuentas en kg de plomo (KgLedger) |
| 4.1 | Inventario de las 5 cuentas |
| 4.2 | Modelo de datos KgLedger |
| 4.3 | Eventos que mueven KgLedger |
| 4.4 | Factor contractual vs eficiencia real |
| 4.5 | Conciliacion semanal con Willard |
| 4.6 | Saldos iniciales en kg (migracion) |
| 5 | Maquila intersede (CV→JM, causacion al envio) |
| 5.1 | Los dos momentos de causacion (envio y salida del crisol) |
| 5.2 | Par de MoneyMovements internos enlazados |
| 5.3 | Causacion contable (asientos generados) |
| 5.4 | Edge cases (anulacion, merma, tolerancia, tarifa vigente) |
| 5.5 | Comparacion con maquila Willard |
| 6 | Maquila Willard (factor contractual, tarifas y fletes) |
| 6.1 | Modelo comercial Willard |
| 6.2 | Fletes Willard + Fletes Internos |
| 6.3 | ServiceTariff: tabla maestra de tarifas |
| 6.4 | Tabla de factores Willard (MaterialConversionFormula) |
| 6.5 | Centros distribucion Willard (informativos) |
| 7 | Inventario y transformaciones internas |
| 7.1 | Inventario multi-sede unificado |
| 7.2 | Compras y liquidacion MANUAL (chatarra propia) |
| 7.3 | Recolecciones postconsumo + rutas multi-proveedor (Green Loop como gestor) |
| 7.4 | Transformaciones internas (molino, picado, fundicion, crisol) |
| 7.5 | Traslados intersede (Transfer + KgLedgerMovement + par de maquila interna) |
| 7.6 | Ventas (Sale workflow + descarga intersede) |
| 8 | Comerciales y nomina (NO comisiones por kg) |
| 9 | Gastos (3-tier con dimension warehouse_id ortogonal) |
| 9.1 | Modelo de gastos heredado (3-tier) |
| 9.2 | Nueva dimension: warehouse_id ORTOGONAL en MoneyMovement |
| 9.3 | Categorias de gasto JERARQUICAS con auxiliares |
| 9.4 | Tesoreria Yurani (cajas menores por sede) |
| 10 | Reportes |
| 10.1 | Reportes preservados (17 base + heredados EcoBalance) |
| 10.2 | Reportes NUEVOS para SAC (6 propios) |
| 10.3 | Panel de excepciones y alarmas (modulo de primera clase) |
| 10.4 | Dashboard SAC personalizado (interactivo con drill-down) |
| 10.5 | Reportes Excel con paridad web/Excel |
| 11 | Cambios al modelo de datos |
| 11.1 | Nuevas tablas |
| 11.2 | Tablas modificadas |
| 11.3 | Modelos REUTILIZADOS sin cambios |
| 11.4 | Relacion con decisiones existentes |
| 12 | Endpoints |
| 12.1 | Endpoints nuevos |
| 12.2 | Endpoints modificados |
| 13 | Frontend |
| 13.1 | Modulos nuevos en sidebar |
| 13.2 | Formularios extendidos |
| 13.3 | Filtros warehouse en reportes |
| 13.4 | Verificacion mobile responsive |
| 14 | Permisos RBAC (nuevos permisos SAC) |
| 14.1 | Permisos nuevos |
| 14.2 | Roles SAC sugeridos (tabla exhaustiva rol-permiso) |
| 14.3 | Aislamiento por organization_id |
| 15 | Migracion inicial |
| 15.1 | Estrategia: solo saldos iniciales |
| 15.2 | Hojas Excel del template SAC |
| 15.3 | Workflow migracion (skill /migrate-client extendido) |
| 15.4 | Validaciones especificas SAC |
| 16 | Roadmap por fases (Fase 1, 2, 3) |
| 16.1 | Fase 1 — Cuadre operativo y financiero (foundations) |
| 16.2 | Fase 2 — Trazabilidad de planta y movilidad |
| 16.3 | Fase 3 — Cierre comercial y regulatorio |
| 16.4 | Dependencias entre fases |
| 17 | Riesgos abiertos y mitigaciones |
| 18 | Preguntas — estado tras la visita a planta (2026-07-02) |
| 18.1 | Preguntas cerradas en la visita (2026-07-02) |
| 18.2 | Abiertas (P1, P55, P64) + datos de configuracion al arranque |
| 18.3 | Preguntas Fase 2 (sesion con Henry y Jose) |
| 18.4 | Preguntas Fase 3 (cierre comercial y regulatorio) |
| 19 | Anexos |
| Anexo A | Plan de coexistencia con app movil de Jose |
| Anexo B | Glosario tecnico completo |
| Anexo C | Mapeo N:1 Materiales SAC-Willard |
| Anexo D | Conversiones de scrap (matematica + JSON schemas) |
| Anexo E | Proximos pasos |
| Anexo F | Decisiones cerradas vs asumidas (sesiones 2026-06-26, 2026-06-30 y visita 2026-07-02) |

---

## 0.3 Mapeo propuesta-cliente vs outline tecnico

La propuesta comercial (`propuesta-alcance-cliente.md`) y este documento tecnico deben leerse en conjunto: la propuesta es contractual y esta escrita en lenguaje del cliente sin mencionar EcoBalance ni el modelo de datos; este documento describe como se implementa cada compromiso. La tabla a continuacion cruza cada seccion de la propuesta con el capitulo tecnico que la entrega y clasifica el estado:

- **Alineado**: el compromiso cliente se cumple sin necesidad de extension o supuesto adicional.
- **Extendido**: el outline agrega detalle o alcance que la propuesta no menciona (tipicamente por decision tecnica) — se marca la razon.
- **Divergente**: el outline propone algo distinto de lo que la propuesta afirma — requiere reconciliacion antes de firmar.

| Compromiso en propuesta cliente | Seccion tecnica del v0.5 | Estado |
|---|---|---|
| 1.1 Problema resuelto (triple digitacion, cuadre manual Johana) | §1.1, §1.2 | Alineado |
| 1.3 Capacidades centrales | §1.3 | Alineado (propuesta v0.5 ya dice "cinco cuentas en kg", confirmadas en visita 2026-07-02) |
| 1.4 Mapa general de operaciones (CV → JM en una direccion) | §3.3, §3.4 | Alineado; outline agrega ruta directa BOG→JM para drosses |
| 2.2 Modulo 1 (Recepcion y orden de entrada) | §7.2, §7.3 | Alineado |
| 2.2 Modulo 3 (Maestros con maquilantes, conductores, vehiculos, hornos) | §6.4 (MaterialConversionFormula), §11.1.14 (Driver/Vehicle) | Alineado — hornos representados por las cuentas kg intra_horno/crisol en Fase 1 |
| 2.2 Modulo 4 (Compras y liquidacion — soporte liquidacion por peso) | §7.2 | Alineado (liquidacion **manual** por Johana, no automatica — corrige asuncion v0.3) |
| 2.2 Modulo 5 (Maquila y postconsumo Willard, dos cuentas kg) | §4.1, §6 | Alineado: Willard Baterias y Willard Drosses como dos cuentas kg distintas ("no pueden ir mezclados", Johana), balance en pesos unico; remision define a que cuenta va cada abono |
| 2.2 Modulo 10 (Tesoreria: libro pesos + libro kg con 5 cuentas) | §4, §9 | Alineado en cuentas kg; Extendido con dimension `warehouse_id` en `MoneyMovement` (decision tecnica) |
| 2.2 Modulo 15 (Panel de excepciones y alarmas) | §10.3 | Alineado (v0.5: el tablero de cuadre se reenfoca a panel de excepciones) |
| 2.3 Cinco cuentas en plomo (Willard Baterias con sub-saldos, Willard Drosses, Intersede, Horno, Crisol) | §4.1 | Alineado — confirmadas en visita 2026-07-02 (crisol separado para medir eficiencia por etapa) |
| 2.3 Cierre de colada agregado en Fase 1, uno-a-uno en Fase 2 | §7.4, §16.2 | Alineado (Fase 1 = descargo agregado; Fase 2 = FurnaceDischarge por colada) |
| 2.6 17 reportes esenciales de Fase 1 | §10.1, §10.1.1 | **Divergente reconciliado**: 3 reportes del corte cliente no existian en EcoBalance (Antiguedad CxC, Antiguedad CxP, Historico de factores y tarifas) — disenados en §10.1.1 como nuevos de Fase 1 |
| 2.6 Todos los reportes exportables Excel/PDF con filtros | §10.5 | Alineado (paridad web/Excel/PDF via helper compartido — [decision #51]) |
| 2.7 Criterios de aceptacion Fase 1 | §16.1 | Alineado |
| 2.9 P7 Modelo contable Willard | §6.1 | CERRADO segun Hugo 2026-06-26: tarifa $2.097/kg |
| 2.9 P8 Factores Willard | §6.4 (MaterialConversionFormula) + Anexo C | Alineado |
| 2.9 P33 Validar modelo cuentas kg con Johana | §4.1 | CERRADA en visita 2026-07-02 — cinco cuentas confirmadas, crisol independiente (medir eficiencia por etapa) |
| 2.9 P38 Cambio rol de Erwin | §2.4, §14.2 | Alineado (rol "Auditor Inventario CV") |
| 2.9 P55/P56 Migracion inicial saldos | §15 | Alineado (solo saldos, no historial — Hugo/Johana 2026-06-26) |
| 2.9 P71 Politica cierre periodo / OK del dia | §10.3 | Alineado (OK del dia firmado por Johana; cierre periodo con permiso elevado — detalle operativo se afina al arranque) |
| 3 Fase 2 (trazabilidad colada + movil offline) | §16.2 | Alineado (descargo agregado en Fase 1; FurnaceDischarge uno-a-uno en Fase 2) |
| 3.6 P16 sesion Henry | §18.3 | Alineado |
| 3.6 P61 sesion Jose (co-desarrollo) | Anexo A | Alineado |
| 4 Fase 3 (exportaciones + subproductos + regulatorios) | §16.3 | Alineado |
| Propuesta NO menciona estructura societaria (1 NIT vs 3) | §2.1 | Extendido: outline asume misma sociedad segun Hugo — CERRADA en sesion 2026-06-30 con Daniel (1 NIT, misma razon social, sin caveat) |
| 2.2 Modulo 13 Proyectos especiales (Panama, Prosperidad, Eco Alloys) | §2.6 | Alineado: modelados como `ThirdParty generic` con CXC |
| Propuesta NO menciona Molino como area operativa distinta | §2.6 | Extendido: Molino re-clasificado como bodega virtual (no proyecto ni tercero) |
| 2.6 Los 6 reportes propios SAC | §10.2 | Alineado: 6 reportes propios dentro de Fase 1 |
| 2.2 Modulo 12 Gastos con detalle por maquina/vehiculo | §9.3 | Alineado: requerimiento explicito de Johana (auxiliares por maquina/vehiculo) |
| Propuesta NO menciona `warehouse_id` en MoneyMovement | §9.2 | Extendido: dimension gerencial persistida como columna nullable — CERRADO en sesion 2026-06-30, retrocompatible con los 3 clientes existentes |

Regla operativa: si en algun momento la propuesta comercial se firma como contractual y el outline evoluciona con una decision "Extendida", esta tabla se actualiza y el ajuste se propone al cliente antes de codificar.

---

## 0.4 Decisiones cerradas vs asumidas — resumen ejecutivo

Resumen de alto nivel del estado de decisiones tras las sesiones 2026-06-26 (Hugo/Johana), 2026-06-30 (Daniel) y la visita a planta 2026-07-02 (Johana en sitio; Hugo por WhatsApp). La tabla completa con las decisiones y su cita/evidencia vive en el **Anexo F**.

| Bloque | Estado agregado | Fuente principal |
|---|---|---|
| Modelo comercial Willard (tarifas, fletes, factor contractual, IPC, SEC PINZA) | 7 CERRADAS | Hugo, reunion noche 2026-06-26 (tarifa flete planta corregida a $37/kg en visita 2026-07-02) |
| Estructura societaria + roles + arquitectura clave (misma sociedad/NIT, Yurani caja menor, warehouse_id persistido, 6 reportes en Fase 1, Jose = "el pelado") | 5 CERRADAS | Daniel, sesion 2026-06-30 |
| Operacion diaria (baterias/drosses no mezclados, liquidacion manual, drosses BOG→JM directo, migracion solo saldos, utilidad cero gerencial) | 5 CERRADAS | Hugo + Johana, 2026-06-26 |
| Correcciones arquitectonicas por review adversarial (Molino como Warehouse virtual, descargo agregado Fase 1) | 5 CERRADAS | Reviews 2026-06-27 |
| Visita a planta: maquila al envio (descarta modelo diferido FIFO), crisol = quinta cuenta, sub-saldos Willard baterias, Green Loop, Eco Alloys, panel de excepciones, liquidacion por peso, cajas menores por sede | TODAS CERRADAS | Johana en la visita 2026-07-02; Hugo por WhatsApp |
| Abiertas (ninguna tecnica): P1 volumenes pico, P55 fecha de corte, P64 modalidad comercial | 3 ABIERTAS no tecnicas | Ver §18.2 |
| Datos de configuracion al arranque (factores, retenciones, maquinas/vehiculos, saldos al corte, formatos Excel) | Se recogen al arranque — no bloquean | Regla cliente: no pedir saldos antes de la propuesta comercial |

**Ver Anexo F para la tabla completa con cita textual, fecha y accion siguiente por decision.**

---

# 1. Resumen ejecutivo y filosofia de la arquitectura

El sistema propuesto absorbe la operacion diaria de Soluciones Ambientales del Caribe (SAC) — recolector y procesador colombiano de baterias plomo-acido usadas — reemplazando cinco cuadros Excel paralelos por captura unica en el punto donde ocurre el hecho. La arquitectura extiende el ERP EcoBalance existente (multi-tenant, tres clientes en produccion: Costa, Biogreen, MetaRecycling) sin romper sus invariantes criticas: costo promedio movil unico por material a nivel organizacion, patrones de causacion existentes (compras 3-step, ventas 2-step, doble partida sin inventario), y el sistema RBAC con 72 permisos en 11 modulos. Los componentes nuevos son aditivos y opcionales: un modulo `KgLedger` paralelo al libro en pesos, dos tablas maestras (`ServiceTariff`, `MaterialConversionFormula`), dos tipos nuevos de `MoneyMovement` internos enlazados para la maquila intersede (`internal_maquila_expense` / `internal_maquila_income`, causados al envio — ver §5), y una dimension gerencial persistida (`warehouse_id` en `MoneyMovement`) que los clientes existentes pueden ignorar.

## 1.1 Problema operativo concreto (estado actual SAC)

SAC procesa entre 10 y 20 entradas diarias entre sus tres sedes (Circunvalar y Juan Mina en Barranquilla, Bogota como centro de acopio y compras). Cada entrada es hoy digitada tres veces: el operador de bascula la anota en su cuadro de patio, Erwin la re-digita en el inventario general de Circunvalar, y Johana la digita una tercera vez cuando liquida la compra o registra el efecto contable. Cualquier error en una de las tres digitaciones descuadra el balance del dia. Johana lo describe: "Tengo que tomar renglon por renglon y validar que todo haya sido bien liquidado y bien anotado en los otros cuadros, porque si no se me descuadra el balance, porque como todo esta manual, ese es el tema" (reunion mañana 2026-06-26).

La deuda con Willard — el gran cliente institucional del programa postconsumo — se cuadra cada viernes por telefono con Willard, sumando cuatro cuadernos paralelos: baterias por sede, drosses por sede, saldos por centro de distribucion, entregas de plomo semanal. Hugo lo describe: "cada viernes se contienen los saldos con ellos" (reunion noche 2026-06-26). La deuda al cierre del reporte reciente es de 422 toneladas de plomo: 131 en Barranquilla, 48 en Bogota, el resto distribuido en otros centros. Baterias postconsumo y drosses no se pueden mezclar en el cuadro — Johana lo enfatiza: "no pueden ir mezclados" — porque Willard renegocio los porcentajes de recuperacion de forma independiente entre ambos productos.

En paralelo, la sede de Juan Mina opera dos hornos con sub-saldos internos que hoy se llevan solo mentalmente: el horno grande (fundicion → plomo crudo) y el crisol (refinacion → plomo puro). Cuando material entra a Juan Mina desde Circunvalar, Johana debe recordar cuanto material aportante del despacho ya se procesado y cuanto queda pendiente — un ejercicio que se agrava con material Willard mezclado en el mismo horno. Hugo confirma que fisicamente los inventarios se mezclan pero la trazabilidad contable es paralela: "debe sumar cuanto de los proveedores y cuanto de Willard. Debe ser lo mismo… daria igual al fisico" (reunion noche 2026-06-26).

Bogota agrega una capa adicional. Hoy funciona como una unidad de negocio completa (compras, ventas, gastos operativos, nomina local, deuda Willard con 48 toneladas), pero se trata como un bolsillo aparte porque los cuadros Excel de Circunvalar y Juan Mina no la contemplan. Hugo: "es donde mas compramos… en Bogota tenemos comerciales, gastos, todo eso, pero no dejamos utilidad, simplemente lo que genere el gasto, la compra y la venta".

El objetivo del sistema es cerrar este gap sin fragmentar el modelo tecnico: una sola organizacion `SAC` en EcoBalance, tres `Warehouses` fisicos, cuatro unidades de negocio ortogonales, y cinco cuentas paralelas en kg de plomo — **confirmadas en la visita a planta del 2026-07-02** (el crisol es cuenta separada del horno grande para medir la eficiencia por etapa).

## 1.2 Vision del sistema

La vision arquitectonica es una organizacion unica `SAC` en EcoBalance con tres sedes operativas, cuatro unidades de negocio (UN) que atraviesan las sedes, y un modulo `KgLedger` paralelo al libro en pesos que trackea la deuda en kilos de plomo:

- **1 Organization SAC**: mismo NIT y razon social cara al contador. **Decision CERRADA** por Daniel (sesion 2026-06-30), ratificando lo confirmado por Hugo ("Todos esos empleados estan afiliados a SAC"). Se implementa eliminacion inter-company automatica en el consolidado SAC (ver §2.1).
- **3 Warehouses fisicos**: Circunvalar (CV, recepcion + molino + picado + despacho a JM), Juan Mina (JM, fundicion en horno grande + refinacion en crisol), Bogota (BOG, acopio alto volumen + compras + recepcion postconsumo Willard).
- **4 Unidades de negocio ortogonales**: `Reciclaje Plomo` (compra-venta chatarra propia), `Maquila Willard` (servicios postconsumo — baterias y drosses), `Reventa DP` o Pasa Mano (operaciones sin inventario, [decision #1]), `Proyectos Especiales` (Panama, Prosperidad, Eco Alloys).
- **5 KgLedgerAccount** (paralelas al libro en pesos): (1) Willard Baterias — con sub-saldos por sede (Barranquilla / Bogota), (2) Willard Drosses, (3) Intersede CV↔JM, (4) Intra-horno JM (horno grande), (5) Crisol JM. **Confirmadas en visita 2026-07-02** (§4.1).
- **Costo promedio unico**: `Material.current_average_cost` sigue siendo ORG-WIDE ([decision #5]). Un mismo codigo de material vale igual en CV, JM y BOG. Fragmentarlo por sede rompe los tres clientes existentes en produccion — no es una opcion.
- **Politica utilidad cero gerencial** en JM y BOG (Hugo): no se miden con P&L independiente. El consolidado SAC integra los tres bolsillos.
- **Ciudades sin sede fisica** (Bucaramanga, Cucuta, otros): solo aparecen como proveedores externos. No tienen `Warehouse` ni inventario SAC. Los centros de distribucion Willard (Monteria, Santa Marta, Motocosta, Pereira, Medellin) son campos informativos en las entradas — las baterias entran fisicamente por CV o BOG; los drosses, directamente por JM.

## 1.3 Las 5 capacidades centrales

La propuesta comercial menciona cinco capacidades. La v0.5 las alinea con las 5 cuentas en kg confirmadas en la visita 2026-07-02 y la dimension gerencial por sede en tesoreria:

| # | Capacidad | Implementacion tecnica |
|---|---|---|
| 1 | Captura unica en el punto del hecho | Orden de entrada → alimenta inventario + costo proveedor + `KgLedger` (segun tipo) en una unica transaccion |
| 2 | Inventarios unificados multi-sede | 1 codigo material = 1 costo promedio ORG-WIDE = distribuido en 3 `Warehouses` — stock per-warehouse via `SUM GROUP BY warehouse_id` on-the-fly |
| 3 | 5 saldos paralelos en kg de plomo | Modulo `KgLedger` — las cuentas se codifican por `account_type`; la cuenta Willard baterias ademas lleva sub-saldos por sede via `warehouse_id` (BAQ/BOG, §4.1) |
| 4 | Tesoreria bidimensional | Libro en pesos (`Account` + `MoneyMovement`) + dimension gerencial por sede via `warehouse_id` nullable en `MoneyMovement` (NULL = corporativo / sin asignar) |
| 5 | Panel de excepciones y alarmas | Con captura unica, el cuadre renglon-por-renglon desaparece por construccion; el panel muestra solo lo anomalo — diferencias despacho vs recibido fuera de tolerancia (3–5% configurable), operaciones sin liquidar al cierre, diferencias de arqueo, saldos cruzados inconsistentes |

La dimension `warehouse_id` en `MoneyMovement` es una clasificacion **gerencial** que no afecta el balance del tercero, no impacta la conciliacion contable en pesos y no rompe el mecanismo de `expense_accrual` existente [decision #14]. Es ortogonal al 3-tier de asignacion por unidad de negocio [decision #44]: un mismo gasto puede ser Directo a `UN1` con `warehouse_id=CV`, o Compartido entre `UN1+UN2` con `warehouse_id=BOG`. Los tres clientes existentes en produccion pueden ignorar el campo (nulo por default).

## 1.4 Filosofia de la arquitectura hibrida

El diseño de v0.4 responde a un filtro arquitectonico repetido: **encontrar el tradeoff que no rompa lo que esta pero permita modelar el negocio nuevo mas complejo**. Cinco decisiones fundamentales se derivan de ese filtro:

- **Warehouse fisico + UN ortogonales, no UN por sede.** Un mismo material (por ejemplo, `BAT-07`) opera en CV, JM y BOG pero pertenece a una sola UN (Reciclaje Plomo o Maquila Willard). Modelar UN por sede duplicaria el maestro de materiales y romperia el costo promedio unico. La solucion: `Material.business_unit_id` fijo, `InventoryMovement.warehouse_id` variable.
- **Costo promedio global, no por sede.** Invariante critica [decision #5]. Si el sistema calculara costo promedio por `warehouse_id`, un traslado CV→JM se volveria un evento con impacto en costo — inaceptable para los tres clientes existentes cuya operacion es exclusivamente mono-sede o donde el traslado es semanticamente neutro. La solucion: costo promedio se recalcula al liquidar la compra ORG-WIDE, sin importar sede de recepcion.
- **KgLedger como modulo paralelo, no como extension de MoneyMovement.** Los kilogramos de plomo no tienen tipo de cambio, no se anulan con dinero, no entran en el P&L. Modelarlos dentro de `MoneyMovement` obligaria a agregar `unit` polimorfico y contaminar los reportes existentes. La solucion: tablas nuevas `KgLedgerAccount` y `KgLedgerMovement`, patron inspirado en `MoneyMovement` + `PriceList` (append-only con snapshot al momento del evento), estado de cuenta unificado analogo a [decision #16].
- **Maquila intersede con causacion al envio.** Cerrado en la visita a planta 2026-07-02, validado por Hugo Y por Johana. Cuando material aportante va CV→JM, en la misma confirmacion del traslado se mueve kg en `KgLedger Intersede` (deuda operativa) **y** se causa la maquila del horno: $1.500/kg de plomo equivalente. Al salir el material del crisol se causa el adicional de refinacion: $300/kg. El transporte CV→JM es con carros propios — no hay flete en ese tramo. Tarifas sugeridas y parametrizables con vigencia historica (`ServiceTariff` append-only); como la causacion es inmediata al evento, aplica la tarifa vigente en ese momento sin snapshot intermedio.
- **Par de MoneyMovements internos enlazados en maquila intersede.** Cada causacion emite un **par enlazado** de `MoneyMovement` sin cuenta (`account_id=NULL`, patron `expense_accrual` [decision #14]) y sin tercero (`third_party_id=NULL` — mismo NIT, §2.1): `internal_maquila_expense` con `warehouse_id=CV` (sede que consume el servicio) + `internal_maquila_income` con `warehouse_id=JM` (sede que lo presta), enlazados como los transfers (linked pair). En el P&L por sede cada lado aparece; en el P&L consolidado SAC ambos tipos internos se **excluyen por filtro de tipo** — se netean a cero y no inflan ingresos ni gastos brutos.

Como corolario, la politica de "utilidad cero gerencial" de Hugo se implementa con asientos internos explicitos y neteables: el P&L por `warehouse_id=JM` muestra los `internal_maquila_income` como ingreso igualado contra gastos operativos + costo del plomo consumido, dejando la utilidad de la UN concentrada en CV o BOG segun donde se comercialice el plomo final. El consolidado SAC excluye ambos tipos internos por filtro.

## 1.5 Diferencias clave vs v0.3

Un lector del v0.3 encontrara los siguientes cambios conceptuales (actualizados a v0.5 donde la visita 2026-07-02 cambio la respuesta):

| v0.3 decia | v0.4/v0.5 dice |
|---|---|
| "3 cuentas en plomo" (Willard, Intersede, Intra-horno) | 5 cuentas CONFIRMADAS (visita 2026-07-02): Willard Baterias (con sub-saldos por sede), Willard Drosses, Intersede, Intra-horno, Crisol |
| CV/JM/BOG como entidades separadas potencialmente distintas | Misma sociedad / mismo NIT — dimension gerencial por sede via `warehouse_id` |
| Sede confundida con UN | Warehouse (fisico) ortogonal a Business Unit (linea de negocio) |
| Tres opciones (a/b/c) sobre modelo comercial Willard | Tarifa fija $2.097/kg de plomo entregado, cita explicita Hugo — Q7 cerrada |
| Maquila causada al envio CV→JM | v0.4 propuso causacion diferida al facturar la venta; la visita 2026-07-02 **confirmo el modelo del v0.3**: causacion al envio ($1.500/kg) + adicional al salir del crisol ($300/kg), como par de MMs internos enlazados (§5) |
| Nomenclatura "PIC" | IPC (Indice de Precios al Consumidor) — actualizacion anual de tarifas Willard |
| Referencia "PIMSA" | "SEC PINZA" — nomenclatura correcta Willard |
| 7 referencias bateria sin mapeo | ~25 materiales SAC → 7 referencias Willard via mapeo N:1 (`MaterialConversionFormula`) |
| Sin proyectos especiales | Panama / Prosperidad / Eco Alloys modelados como `ThirdParty generic` con CXC; Molino re-clasificado como bodega virtual (no tercero, no proyecto) |
| Sin matriz RBAC validada | Matriz con David / Yurani / Jose / companera de despachos + rol "caja menor" filtrado por `warehouse_id` para Yurani |
| Liquidacion de compras automatica al recibir | Liquidacion **manual** por Johana entrada por entrada — corrige asuncion incorrecta del v0.3 |
| Comerciales con comision variable por kg | Comerciales con nomina fija (Hugo cita explicita) — mecanismo de comisiones EcoBalance se reserva para casos futuros |

---

# 2. Contexto del cliente SAC

Este capitulo consolida el contexto de negocio necesario para leer el resto del documento: estructura societaria, mapa fisico de sedes, unidades de negocio, organigrama con nombres reales, escala operativa, y la clasificacion de "proyectos especiales" que aparecen en la contabilidad SAC pero no encajan como flujo estandar.

## 2.1 Estructura societaria (1 sociedad, 3 sedes operativas)

SAC es una sola sociedad juridica con tres sedes operativas. Decision **CERRADA** por Daniel en sesion 2026-06-30: un unico NIT, misma razon social para CV/JM/BOG. Ratifica lo confirmado por Hugo (reunion noche 2026-06-26): "Todos esos empleados estan afiliados a SAC". Se implementa eliminacion inter-company automatica en el consolidado SAC — el modo "no eliminar pares intersede" queda descartado del backlog.

- **Cerrado**: 1 NIT, 1 razon social ("Soluciones Ambientales del Caribe / SAC"). No requiere reconfirmacion adicional.
- **Sedes operativas con bodegas fisicas**: Circunvalar (Barranquilla — recepcion y comercializacion), Juan Mina (Barranquilla — fundicion y refinacion), Bogota (acopio alto volumen y compras).
- **Otras ciudades sin sede fisica**: Monteria, Santa Marta, Motocosta, Pereira, Medellin, Bucaramanga, Cucuta. NO tienen inventario SAC — son proveedores externos que entregan en CV o BOG. Pereira y Medellin quedan [PENDING-CONFIRM] sobre si son centros distribucion Willard o solo proveedores.
- **Implicacion contable (misma sociedad)**: en el consolidado SAC se eliminan pares intersede automaticamente. El P&L por sede sigue siendo gerencial, no un P&L contable independiente.
- **Implicacion gerencial**: se puede calcular P&L por sede (dimension `warehouse_id`), pero no genera Balance Sheet contable separado.
- **Politica utilidad cero gerencial** en JM y BOG (Hugo 2026-06-26): "no dejamos utilidad en Bogota, simplemente lo que genere el gasto, la compra y la venta".

## 2.2 Sedes y su rol operativo

Cada sede tiene un rol funcional distinto. La descripcion siguiente reemplaza la seccion 0.3 del v0.3 que confundia sede con UN:

- **Circunvalar (CV / Barranquilla)**: recepcion de chatarra y postconsumo Willard (baterias). Alberga el molino (trituracion de baterias automotrices) y el area de picado manual (desarme manual de UPS, estacionarias, vasos, moto). Es el origen fisico de los despachos a Juan Mina. Lider operativo: David.
- **Juan Mina (JM / Barranquilla)**: sede de procesamiento pesado. Horno grande (fundicion → plomo crudo por colada) + crisol (refinacion → plomo puro). Recibe drosses Willard directamente desde BOG sin pasar por CV (Hugo 2026-06-26). Lider operativo: Henry [PENDING-CONFIRM alcance en sistema — sesion 1:1 pendiente].
- **Bogota (BOG)**: acopio de alto volumen, compras locales (Hugo: "es donde mas compramos"), recepcion de postconsumo Willard para el centro del pais. Saldo Willard al cierre reciente: 48 toneladas.

El flujo cross-sede sigue tres rutas:

- **Baterias Willard de BOG → trasladan primero a CV** para procesamiento (molino, picado, clasificacion) antes de pasar a JM.
- **Drosses Willard de BOG → directo a JM** sin pasar por CV (Hugo). El sistema modela esto con un campo `goes_directly_to_jm` en la `InboundOrder` para trazar la ruta fisica.
- **Chatarra propia BOG → despacho a CV o directo a JM** dependiendo del material y decision operativa.

Adicionalmente existen tres bodegas virtuales:

- **`JM-TRANSITO`**: durante el traslado CV → JM el material esta en esta bodega virtual hasta la confirmacion de recepcion en JM. El despacho NO tiene efectos en KgLedger ni en pesos — el asiento `intersede_send` y el par de maquila se emiten al confirmar la recepcion, sobre los kg recibidos (§5.1, §7.5).
- **`CV-TRANSITO`**: analoga para la ruta BOG → CV (llegada fisica de baterias que mueve los sub-saldos Willard, `willard_subbalance_move` §4.3), con la misma regla de doble cantidad y tolerancia — el transporte de ese tramo es tercerizado.
- **`CV-MOLINO`**: el area de trituracion en CV. Se modela como bodega dentro del `Warehouse CV` (o subwarehouse, [PENDING-DESIGN]) para trackear stock en el molino. No es un proyecto ni un tercero — es solo un area operativa (ver §2.6).

## 2.3 Unidades de negocio (ortogonales a sede)

SAC opera cuatro unidades de negocio (UN) que son lineas de negocio, no sedes. La confusion en v0.3 (tratar CV/JM/BOG como UN) se corrige aqui:

| UN | Nombre | Descripcion | Sedes donde opera |
|---|---|---|---|
| UN1 | Reciclaje Plomo | Compra chatarra propia → procesa → vende a Willard u otros. Genera margen propio. | CV, JM, BOG |
| UN2 | Maquila Willard | Recibe postconsumo Willard (baterias + drosses) → procesa → devuelve plomo. Cobra $2.097/kg maquila. | CV, JM, BOG |
| UN3 | Reventa DP (Pasa Mano) | Operaciones de doble partida sin inventario ([decision #1]). Sin comision a comerciales (nomina fija). | Transversal — no toca sede |
| UN4 | Proyectos Especiales | Panama (equipos trasladados con CXC), Prosperidad (construccion), Eco Alloys (aluminio). | Se modela como `ThirdParty generic`. |

La consecuencia tecnica es directa: `Material.business_unit_id` determina la UN, `InventoryMovement.warehouse_id` determina la sede fisica. Un mismo material puede operar en cualquier sede pero su UN es unica. El reporte de rentabilidad por UN sigue usando [decision #44] (3-tier allocation) sin cambios, y `warehouse_id` es una dimension adicional ortogonal.

UN4 requiere una nota especial: Panama, Prosperidad y Eco Alloys **no** necesitan una UN operativa dedicada — se modelan como terceros `generic` con cuenta por cobrar (ver §2.6). Molino no es proyecto, es bodega virtual (misma seccion).

## 2.4 Organigrama y roles validados

Los roles siguientes reemplazan la tabla "roles ilustrativos" del v0.3. Cada persona esta confirmada en las reuniones 2026-06-26 salvo indicacion contraria. El sistema RBAC usa roles funcionales, no nombres — los nombres son ilustrativos y sirven para asignar permisos al onboarding.

| Persona | Rol operativo | Notas |
|---|---|---|
| Hugo Armando Bedoya | Gerente general | Postconsumo Willard, coordinacion contractual con Willard, decisiones comerciales mayores. Fuente autoritativa sobre modelo Willard y politica utilidad cero. |
| Johana | Gerente financiera | Liquidacion **manual** entrada por entrada, precios, cuadre diario, autoriza cierres. Fuente autoritativa sobre flujo caja menor Yurani. |
| David | Jefe operaciones BAQ | Digita entradas, supervisa CV+JM. Decide `willard_account_subtype` (escurrido / pinza) al digitar entradas SEC. |
| Erwin | Auditor inventario CV | P38 del v0.3 (cambio de rol digitador → auditor). Audita fisicamente inventario en CV y firma arqueos. |
| Henry | Operacion JM | P16 del v0.3 (coladas y refinacion). Alcance exacto en el sistema [PENDING-CONFIRM] — sesion 1:1 pendiente. |
| Companera de despachos (CV) | Procesa salidas y remisiones a clientes/Willard. | Nombre [PENDING-CONFIRM]. |
| Yurani | Administradora de las cajas menores (una caja POR SEDE, todas operadas por ella) | **Modelo cerrado en visita 2026-07-02**: hay una caja menor por sede y Yurani (una persona) las opera todas con su propio acceso al sistema (rol "caja menor"). Cada gasto **hereda la sede (`warehouse_id`) de la CAJA usada**, no de un default del usuario (ver §9.4). Johana valida/reclasifica despues via `PATCH /money-movements/{id}/classification` (decision #39). |
| Jose | Desarrollador interno SAC + operacion JM (app movil) | **Cerrado 2026-06-30**: "el pelado" = Jose (mismo desarrollador del app movil actual — un solo actor). Ha creado utilidades operativas internas. Sera integrado al proyecto EcoBalance en Fase 2 para co-desarrollar el modulo movil (ver Anexo A). |
| Coordinador de postconsumo (nacional) | Cuadre semanal Willard | Persona de SAC que envia el cuadro semanal a Willard y concilia el saldo nacional (el cuadre consolida el saldo nacional — detalle a confirmar con el coordinador al arranque). Usuario del sistema con permisos de postconsumo/reportes (`willard.reconcile`, `kg_ledger.view`, `reports.view` — ver §14.2). El acta semanal incluye detalle por entrega (fecha, remision, kg). |
| Comerciales (equipo) | Ventas nacionales | Nomina fija mensual (Hugo 2026-06-26). **NO comision por kg**. El mecanismo de comisiones EcoBalance [decision #23, #30, #32] se reserva para casos futuros. |
| Green Loop | Gestor externo de recolecciones (NO comercial) | **Cerrado en visita 2026-07-02**: opera con una caja provista por SAC; compra en ruta a nombre del proveedor real; comision de $100/kg recolectado (sugerida y parametrizable), liquidada por consignacion aparte. **Corregido en v0.6**: la comision se registra como **gasto causado** (`expense_accrual`, categoria indirecta) al liquidar la compra — [decision #83], desplegada; hasta v0.5 este renglon decia que se prorrateaba al costo del material via `PurchaseCommission` [decision #30], lo cual ya no es cierto (ver §7.3 punto 5). Una ruta suya puede traer material de varios proveedores: desde v0.6 se captura como **una entrada con un proveedor por linea** (ver §7.3). |

## 2.5 Volumen y escala operativa

Datos cuantitativos validados en la reunion noche 2026-06-26. Se usan para dimensionar arquitectura y para configurar las tolerancias del panel de excepciones (§10.3):

- **Entradas diarias**: 10 a 20 entre las tres sedes (compras propias + postconsumo baterias + drosses + otros). Confirmado por Erwin y Johana en reunion mañana 2026-06-26.
- **Deuda Willard total**: 422 toneladas de plomo (Hugo). Desglose: 131 ton en BAQ, 48 ton en BOG, resto en otros centros distribucion (informativos).
- **Ventas a Willard**: facturacion semanal o por entrega. Conciliacion cada viernes con Willard — el lenguaje cliente es "contienen saldos".
- **Materiales activos**: aproximadamente 25 codigos en SAC (mismo codigo todas las sedes). Mapean N:1 a 7 referencias Willard (baterias) + factores por material adicional (drosses, jamiche, SEC ESCURRIDO, SEC PINZA, etc.). Lista exacta: dato de configuracion que se recoge al arranque (no bloquea el alcance).
- **Eco Alloys**: cuenta por cobrar superior a **$20.000 millones** (proyecto aluminio). Hugo textual: *"Esa cuenta debe estar como en 20.000, más de 20.000 millones"* (reunion noche 2026-06-26). Nombre oficial confirmado en visita 2026-07-02. La cifra es placeholder — el saldo exacto se toma al corte de arranque; el cliente prefirio no entregar saldos antes de la propuesta comercial.
- **Panama**: cuenta por cobrar por equipos trasladados a BAQ. Monto: se toma al corte de arranque (regla cliente: no se piden saldos antes de la propuesta comercial).
- **Migracion inicial**: solo saldos iniciales sin historial transaccional. Cargar un mes completo de operacion seria volumen masivo prohibitivo (Johana y Hugo).

## 2.6 Proyectos especiales y Molino (modelado)

Hay tres proyectos que aparecen en la contabilidad SAC pero no encajan como flujo operativo estandar, mas el area operativa Molino que en v0.3 se trataba como un modulo separado y en v0.4 se re-clasifica correctamente:

- **Panama**: `ThirdParty generic`, `behavior_type='generic'`. Cuenta por cobrar por equipos trasladados a BAQ. Se migra con `initial_balance` positivo (SAC les cobra). Monto: se toma al corte de arranque.
- **Prosperidad**: `ThirdParty generic`. Construccion en curso — objetivo unificar CV+JM en corto plazo. Saldo inicial: se toma al corte de arranque. Posible que tambien se modele como `FixedAsset` si hay terreno o construccion capitalizable — [PENDING-DESIGN] segun politica contable SAC.
- **Eco Alloys**: `ThirdParty generic`. Aluminio (nombre confirmado en visita 2026-07-02). Saldo inicial > **$20.000 millones** (placeholder — cifra exacta al corte de arranque). Posible evolucion futura a operativo si SAC comienza a comprar/vender aluminio de forma regular — el gap conocido `convert_generic_to_operational` esta fuera de v1.
- **Molino**: **NO es proyecto ni tercero**. Es un area operativa dentro de la sede Circunvalar donde se tritura bateria automotriz. Se modela como bodega virtual (`Warehouse CV-MOLINO` o subwarehouse dentro del `Warehouse CV`, [PENDING-DESIGN]) para trackear stock de material en trituracion. Correccion respecto de v0.3, donde se sugeria implicitamente como proyecto separado.

Los tres proyectos (Panama, Prosperidad, Eco Alloys) aparecen en Balance Detallado bajo la seccion `Generic Receivable` ([decision #31]). Su estado de cuenta unificado sigue [decision #16] sin cambios, y sera filtrable por `warehouse_id` si Johana lo requiere como extension gerencial.

---

# 3. Modelo conceptual de negocio

Este capitulo cierra la capa de negocio antes de bajar al modelo tecnico de datos. Define el glosario funcional con las correcciones de v0.3 (SEC PINZA en lugar de PIMSA, IPC en lugar de PIC), aclara la relacion N:1 entre materiales SAC y referencias Willard, describe los cuatro flujos centrales, presenta el mapa visual con el par de `MoneyMovement` internos enlazados de la maquila intersede (modelo v0.5, visita 2026-07-02), y explica el mecanismo de "utilidad cero gerencial" sin inventar asientos.

## 3.1 Glosario del negocio

Reemplaza el 0.2 del v0.3 con los terminos corregidos:

| Termino | Definicion |
|---|---|
| Sede | Lugar fisico. Modelo tecnico: `Warehouse`. |
| Unidad de negocio (UN) | Linea de negocio. Modelo tecnico: `BusinessUnit`. Ortogonal a sede. |
| Cuenta en kg de plomo | Saldo paralelo al libro en pesos. SAC tiene 5 cuentas kg confirmadas (visita 2026-07-02). Modelo tecnico: `KgLedgerAccount`. Independiente del tipo de cambio, no entra en P&L. |
| Maquila Willard | Servicio que SAC presta a Willard procesando postconsumo. Tarifa $2.097/kg de plomo entregado (Hugo 2026-06-26). |
| Maquila intersede | Servicio que JM presta a CV procesando material. $1.500/kg de plomo equivalente causado **al enviar** CV→JM + $300/kg causado **al salir del crisol** (visita 2026-07-02). Gasto sede origen / ingreso JM; se excluye del consolidado SAC. |
| Factor contractual Willard | Kilogramos de plomo a devolver por unidad o kg de input recibido. CONTRACTUAL — si SAC es eficiente/ineficiente en la extraccion, la diferencia va a inventario propio, no al saldo Willard (Hugo 2026-06-26: "No, no, ya ahi la sumo yo completamente"). |
| IPC | Indice de Precios al Consumidor. Tarifas Willard se actualizan anualmente con IPC (correccion de "PIC" del v0.3). |
| Conciliacion viernes | Cada viernes Johana "contiene/cuadra" saldos kg con Willard (llamada con Willard). Lenguaje cliente: "contienen los saldos". |
| Postconsumo | Canal de recoleccion Willard. Dos productos separados que NO se mezclan: baterias (en unidades, 7 referencias) y drosses (en kg, multiples referencias). |
| Scrap-con-borne | Bateria descargada tras extraccion de acido. Salida del picado manual. Formula dual: `kg_plomo = (kg_scrap × factor_scrap) + kg_borne`. Ver Anexo D. |
| Aportante / material aportante | Material que aporta plomo recuperable al horno grande: scrap, lodo, **retal** y demas (cada uno con rendimiento distinto). El retal es un INSUMO del horno, no su producto. Salida del picado + del molino. |
| Plomo crudo | Salida del horno grande (fundicion) — **plomo crudo en lingote**. Es la unica entrada del crisol. Identificado por colada (Fase 2 uno-a-uno; Fase 1 agregado). |
| Plomo puro / refinado | Salida del crisol (refinacion). Producto final para venta nacional / abono Willard / exportacion. |
| Colada | Corrida individual del horno grande, con identidad propia (Fase 2). En Fase 1 se agrega por dia. |
| Merma | Diferencia entre input y suma de salidas en una transformacion fisica. Refleja perdida operativa esperada. |
| Rendimiento | Kg de plomo crudo producido sobre kg de aportante consumido. Alerta al desviarse de tolerancia. |

## 3.2 Referencias y materiales (mapeo N:1 con Willard)

SAC maneja aproximadamente 25 materiales activos internos con codigo unico cross-sede — el mismo codigo se usa en CV, JM y BOG (Hugo 2026-06-26). Willard, en cambio, reporta y factura sobre 7 referencias de bateria mas categorias de material adicional (drosses, jamiche, SEC ESCURRIDO, SEC PINZA, etc.). El mapeo entre el maestro SAC y las referencias Willard es N:1 y vive en la tabla `MaterialConversionFormula` (append-only con vigencia, patron [decision #35]).

Las 7 referencias de bateria Willard son: 07, 08, 1, 2, 3, 4, 5 (de menor a mayor tamaño). Adicionalmente Willard maneja factores para: drosses, jamiche (con factor 53% del peso = plomo equivalente), SEC ESCURRIDO (56%), SEC PINZA (59%), UPS, estacionaria, vasos, moto, seca.

Caso especial critico: **SEC ESCURRIDO y SEC PINZA son el mismo material fisico** pero dos cuentas Willard distintas. Willard renegocio el porcentaje de recuperacion y dejo dos cuentas separadas (Hugo 2026-06-26). El mecanismo de diferenciacion en el sistema es un campo obligatorio en la `InboundOrder` de postconsumo Willard cuando el material recibido es "SEC":

```json
{
  "material_id": "...",
  "willard_account_subtype": "escurrido"
}
```

El enum permitido es `escurrido | pinza`. Quien decide: David al digitar, basado en la remision Willard. Sin asignacion, la deuda kg no puede causarse correctamente porque los factores de conversion son distintos entre subtipos.

La formula scrap-con-borne (aplicable al material que sale del picado manual) es tambien un caso especial. La salida es un mixto de scrap (varias referencias, factor ~0.8–0.9 kg/L de plomo) y borne (terminales de plomo casi puro > 90%). La conversion final a "kg plomo" usa una formula dual detallada en Anexo D. El factor exacto del scrap es [CONFIG-ARRANQUE: se pide por escrito a Willard/Erwin al arranque] — SAC no lo conoce por escrito hoy.

## 3.3 Los cuatro flujos centrales

Vista macro de los flujos operativos. Cada flujo toca una combinacion distinta del `KgLedger`, y solo dos afectan la deuda con Willard:

- **Flujo 1 — Reciclaje Plomo (UN1)**: proveedor → compra CV o BOG → traslado a JM → fundicion / crisol → venta. Toca `KgLedger` Intersede, Intra-horno, Crisol. NO toca `KgLedger` Willard. La rentabilidad de la UN se calcula con los mecanismos existentes de EcoBalance.
- **Flujo 2 — Maquila Willard (UN2)**: Willard entrega postconsumo → recepcion en CV (baterias) o directamente en JM (drosses) → procesamiento en JM → entrega de plomo a Willard. Toca `KgLedger` Willard Baterias y Willard Drosses (suben al ingreso, bajan al entregar). La factura a Willard incluye maquila $2.097/kg + fletes contractuales.
- **Flujo 3 — Reventa DP / Pasa Mano (UN3)**: SAC intermedia entre comprador y vendedor externo, cobra comision. NO toca inventario ([decision #1]), NO toca `KgLedger`. Preserva completamente el mecanismo de Doble Partida existente.
- **Flujo 4 — Proyectos Especiales (UN4)**: Panama (equipos con CXC), Prosperidad (construccion), Eco Alloys (aluminio). Pueden tener inventario operativo, `FixedAsset` o solo CXC. NO tocan `KgLedger` plomo.

Un hecho critico del negocio: **en JM se mezclan fisicamente materiales de UN1 (Reciclaje) y UN2 (Maquila Willard)**. El `KgLedger` trackea cada uno independientemente, pero el inventario fisico es total. Hugo lo confirma: "debe sumar cuanto de los proveedores y cuanto de Willard. Debe ser lo mismo… daria igual al fisico".

## 3.4 Mapa visual de flujos fisicos y financieros

Tabla que muestra cada evento operativo, el efecto que produce en `KgLedger` y en `MoneyMovement`, y el momento de causacion. Esta version refleja el modelo cerrado en la visita 2026-07-02: la maquila interna se causa **al envio** como par de MMs internos enlazados (§5):

| Evento | KgLedger | MoneyMovement | Comentario |
|---|---|---|---|
| Compra propia chatarra en CV | — | `InventoryMovement in` + MM cuenta proveedor (al liquidar) | Liquidacion manual Johana |
| Postconsumo Willard baterias CV o BOG | `+Willard Baterias` (factor × unidades) — sub-saldo de la sede de ingreso (BAQ o BOG) | — | source = `InboundOrder` |
| Postconsumo Willard drosses (BOG → JM directo) | `+Willard Drosses` (factor × kg) | — | `InboundOrder` con `goes_directly_to_jm=true`. Drosses SIEMPRE ingresan por JM |
| Llegada fisica de baterias Bogota → Circunvalar | Willard Baterias: **mueve entre sub-saldos** (BOG −, BAQ +) | — | Evento de traslado; el saldo total Willard no cambia |
| Traslado CV → JM — despacho | — | — | `InventoryMovement out CV + in JM-TRANSITO`. Sin efectos kg ni pesos todavia (§5.1) |
| Traslado CV → JM — recepcion confirmada | `+Intersede` (kg **recibidos** × factor) | **Par enlazado**: `internal_maquila_expense` (warehouse=CV) + `internal_maquila_income` (warehouse=JM), monto = `kg plomo equivalente recibido × $1.500` | Lo recibido = fuente de verdad; dentro de tolerancia (3–5%) ajuste automatico; fuera → excepcion (§10.3) y par retenido. Causacion "al envio" = el evento del traslado (visita 2026-07-02), anclada a la recepcion (§5.1) |
| Devolucion JM → CV sin procesar | `-Intersede` (kg equivalente devuelto) | Anulacion proporcional del par de maquila del envio correspondiente | `intersede_return` (§4.3, §5.1) |
| Carga aportante a horno grande | `+Intra-horno` (kg cargado) | — | `FurnaceCharge` (nuevo evento). Al horno entran scrap, lodo, retal y demas aportantes |
| Cierre colada horno grande (Fase 2) | `-Intra-horno` | + `InventoryMovement` plomo crudo en lingote | En Fase 1: descargo agregado diario proporcional |
| Carga crudo a crisol | `+Crisol` (kg crudo) | — | `CrucibleCharge` |
| Cierre crisol (sale plomo puro) | `-Crisol` | + `InventoryMovement` plomo refinado + **par enlazado** `internal_maquila_expense` (CV) / `internal_maquila_income` (JM) por `kg × $300` | `CrucibleDischarge` — adicional de refinacion causado a la salida del crisol |
| Entrega plomo a Willard (Sale liquidada) | `-Willard Baterias` o `-Willard Drosses` segun la **remision** de la entrega; `-Intersede` (descarga kg pendientes) | + MM Sale + MM maquila Willard ($2.097/kg) + flete planta ($37/kg) — facturados **por cada entrega** | La remision define si el abono descarga baterias o drosses |

Ejemplo numerico concreto. Traslado CV → JM de 1.000 kg de aportante con factor scrap→plomo de 0.6:

- Al confirmar la recepcion del traslado (mismo dia — carros propios): `KgLedger Intersede += 600 kg` (sobre kg recibidos) **y** se causa la maquila del horno: par enlazado `internal_maquila_expense` (warehouse=CV) + `internal_maquila_income` (warehouse=JM) por $900.000 (`600 × 1.500`), ambos con `account_id=NULL`, `third_party_id=NULL`, categoria "Maquila Intersede". Tarifa vigente al momento del evento (`ServiceTariff`).
- A la salida del crisol (refinacion produce plomo puro): segundo par por $180.000 (`600 × 300`), categoria "Crisol Refinacion".
- En el P&L por sede cada lado aparece (CV gasto, JM ingreso). En el P&L consolidado SAC ambos tipos internos se **excluyen por filtro de tipo** — se netean a cero sin inflar ingresos ni gastos brutos.

## 3.5 Politica contable 'utilidad cero gerencial'

La directriz de Hugo — "no dejamos utilidad en Bogota, simplemente lo que genere el gasto, la compra y la venta" — es una politica **gerencial**, no contable. En el consolidado SAC (misma sociedad, mismo NIT), la utilidad es una sola. Lo que la politica pide es que el sistema no muestre una utilidad artificialmente inflada o deprimida para JM o BOG cuando se los mira de forma aislada.

El mecanismo de implementacion tiene tres piezas:

1. **P&L por `warehouse_id`**: el reporte existente [decision #6, #22, #44] gana un filtro por `warehouse_id` que suma ingresos y gastos con esa dimension. No inventa asientos artificiales — solo agrupa lo que ya existe.
2. **Par de MMs internos enlazados en maquila intersede** (§5): cada causacion (envio y salida de crisol) emite `internal_maquila_expense` (warehouse=CV) + `internal_maquila_income` (warehouse=JM), ambos sin cuenta y sin tercero. El P&L filtrado por `warehouse_id=JM` muestra los ingresos internos como lineas reales; el filtrado por CV muestra el gasto. No hay vistas derivadas ni asientos reconstruidos al vuelo.
3. **Exclusion por tipo en el consolidado**: el P&L consolidado SAC (sin filtro de sede) **excluye** los tipos `internal_maquila_expense` e `internal_maquila_income` mediante filtro por tipo de movimiento — se netean a cero entre si (mismo NIT) y excluirlos evita inflar ingresos y gastos brutos. Las vistas por sede los incluyen.

Con este mecanismo, el reporte "P&L de JM" mostrara aproximadamente:

| Linea | Monto |
|---|---|
| Ingresos por maquila intersede (`internal_maquila_income`) | $900.000 |
| Ingresos por crisol (`internal_maquila_income`) | $180.000 |
| Gastos operativos JM | −$500.000 |
| Costo del plomo consumido | −$580.000 |
| **Utilidad neta JM** | **~$0** |

Los numeros no cuadran exactamente a cero — la variacion operativa es natural — pero la politica se refleja: no hay margen sistematico en JM porque el sistema no le atribuye margen artificial.

Nota final: si Johana eventualmente pide un **Balance Sheet contable** separado por sede (no solo P&L gerencial), se requeriria implementar inter-company eliminations explicitas + journal entries de reparto entre sedes. Eso queda fuera de v1 y esta [PENDING-CONFIRM Q2 diferido a Fase 2].

# 4. Las 5 cuentas en kg de plomo (KgLedger)

Este capítulo es el corazón técnico del v0.4. Modela un módulo nuevo — `KgLedger` — paralelo al libro en pesos existente en EcoBalance, que trackea los saldos de plomo (medidos en kg) que se acumulan y descargan a lo largo del ciclo operativo de SAC. El módulo es necesario porque los kg de plomo no son dinero: no tienen tipo de cambio, no se anulan con MoneyMovements, no entran directamente en el P&L, y responden a una lógica de causación distinta (factor contractual vs eficiencia real, ver §4.4). Además, cierto tipo de decisiones operativas críticas de Johana (¿cuánto le debemos hoy a Willard?, ¿cuánto quedó en el horno al cierre?) se toman en kg, no en pesos.

Son **5 cuentas kg confirmadas en la visita a planta del 2026-07-02** (el crisol quedó como cuenta separada del horno grande — razón del cliente: medir la eficiencia por etapa, ver §4.1). Todas comparten el mismo patrón append-only que `MoneyMovement` ([REUTILIZADO #16]), la misma convención `BusinessDate` noon UTC en `transaction_date` ([REUTILIZADO patrón `BusinessDate` global CLAUDE.md]) y el mismo mecanismo de anulación con auditoría de `ProfitDistribution.annul` ([REUTILIZADO #48]).

Aclaración crítica sobre Willard: aunque Willard tiene dos cuentas kg separadas (Baterías y Drosses), en el libro en pesos Willard sigue siendo **un solo `ThirdParty` con un único `balance` en pesos** ([REUTILIZADO #16, #55]). Las cuentas kg viven en `KgLedger`, dimensión separada del balance en pesos. El estado de cuenta del `ThirdParty` Willard muestra transacciones en pesos + un bloque informativo lateral con los dos saldos kg (ver §4.5).

## 4.1 Inventario de las 5 cuentas [CONFIRMADO en visita 2026-07-02]

Las 5 cuentas cubren todos los flujos físicos de plomo que hoy Johana lleva en cuadros Excel paralelos: dos son deudas con Willard (postconsumo baterías y drosses), una es deuda interna entre las sedes Circunvalar (CV) y Juan Mina (JM), y dos son saldos de proceso en JM (horno grande y crisol). **El crisol quedó confirmado como cuenta separada del horno grande** en la visita a planta del 2026-07-02 — razón del cliente: medir la eficiencia de cada etapa. Al horno grande entran scrap, lodo, retal y demás aportantes (cada uno con rendimiento distinto) y sale **plomo crudo en lingote**; al crisol entra plomo crudo y sale plomo puro. Nota de vocabulario: el **retal es un INSUMO del horno, no su producto**.

La tabla siguiente resume cada cuenta, su sentido económico, sus disparadores de acumulación y descarga, y el saldo de referencia según Hugo (reunion noche 2026-06-26).

| # | Cuenta | Sentido | Acumula por | Descarga por | Saldo de referencia |
|---|--------|---------|-------------|--------------|--------------|
| 1 | Willard Baterías (**sub-saldos por sede**: Barranquilla / Bogotá) | SAC debe a Willard | Postconsumo baterías recibido (unidades × factor por referencia): lo que entra por CV suma al sub-saldo Barranquilla (el que cuadra Johana); lo que entra por BOG suma al sub-saldo Bogotá | Entregas de plomo a Willard cuya **remisión** las asigna a baterías. Además, la llegada física de baterías Bogotá→Circunvalar **mueve entre sub-saldos** (BOG −, BAQ +) sin cambiar el total | 422 ton deuda total — 131 BAQ, 48 BOG, resto en otros centros de distribución Willard (informativos, no son bodegas SAC) |
| 2 | Willard Drosses | SAC debe a Willard | Drosses Willard recibidos (kg × factor conversión). Drosses SIEMPRE ingresan por Juan Mina | Entregas de plomo a Willard cuya **remisión** las asigna a drosses | Subtotal: se toma al corte de arranque — separado obligatoriamente de Baterías porque Johana afirma que "no pueden ir mezclados" |
| 3 | Intersede CV↔JM | JM debe a CV | Traslado de aportantes CV→JM — emitido al confirmar la **recepción**, sobre kg recibidos × factor scrap→plomo (§5.1) | Salida de plomo procesado desde JM (venta/entrega); devolución física a CV sin procesar (`intersede_return`) | Kg en tránsito: se toman al corte de arranque |
| 4 | Intra-horno JM (horno grande) | Saldo interno del horno grande | Carga de aportante al horno (`FurnaceCharge`) — scrap, lodo, retal y demás | Cierre de colada, produce plomo crudo en lingote (Fase 2: por colada; Fase 1: descargo agregado periódico) | Kg en proceso: se toman al corte de arranque |
| 5 | Crisol JM | Saldo interno del crisol de refinación (entra plomo crudo, sale plomo puro) | Carga de plomo crudo al crisol (`CrucibleCharge`) | Cierre de refinación (produce plomo refinado/puro) | Kg en proceso: se toman al corte de arranque. **Confirmada como cuenta separada** — permite medir la eficiencia de cada etapa (visita 2026-07-02) |

El cuadre semanal con Willard consolida el **saldo nacional** (los sub-saldos BAQ y BOG más lo distribuido en otros centros informativos de Willard); el detalle operativo se confirma con el coordinador de postconsumo al arranque (§4.5).

Todas las cuentas comparten atributos comunes: son `organization_id`-scoped, se desactivan vía `is_active` (nunca hard delete), y su saldo se calcula como `SUM(KgLedgerMovement.delta_kg) WHERE status='confirmed'` — patrón idéntico al `third_party.balance` en pesos ([REUTILIZADO #16]). Las cuentas 1 y 2 tienen `third_party_id=Willard`; las cuentas 3, 4 y 5 son internas con `third_party_id=NULL`.

## 4.2 Modelo de datos KgLedger [NUEVO]

Se agregan dos tablas nuevas: `KgLedgerAccount` (maestro de cuentas) y `KgLedgerMovement` (asientos append-only). El diseño espeja `MoneyAccount` + `MoneyMovement` ([REUTILIZADO #16]) para minimizar sorpresas cognitivas al leer el código y para reusar todos los patrones ya probados: `organization_id` scoping, `TimestampMixin`, soft delete, anulación con auditoría ([REUTILIZADO #48]), snapshot temporal de fórmula ([REUTILIZADO #41]) y `BusinessDate` en fecha de negocio ([REUTILIZADO patrón CLAUDE.md `BusinessDate`]).

### Tabla `KgLedgerAccount` [NUEVO]

| Columna | Tipo | Nullable | Descripción |
|---------|------|----------|-------------|
| `id` | UUID (GUID) | NO | PK |
| `organization_id` | UUID (GUID) | NO | FK `organizations.id`, filtrado automático `CRUDBase` |
| `code` | VARCHAR(50) | NO | Código legible corto (`WILLARD-BAT-BAQ`, `WILLARD-BAT-BOG`, `WILLARD-DROSS`, `INTERSEDE-CV-JM`, `INTRA-HORNO-JM`, `CRISOL-JM`) |
| `display_name` | VARCHAR(200) | NO | Nombre presentable en UI |
| `account_type` | ENUM | NO | `willard_baterias \| willard_drosses \| intersede \| intra_horno \| crisol` |
| `warehouse_id` | UUID (GUID) | SÍ | FK `warehouses.id`. Dimensión de sub-saldo: para `willard_baterias` distingue los **dos sub-saldos de la misma cuenta lógica** (CV = Barranquilla, BOG = Bogotá); JM para Intra-horno y Crisol; NULL para Willard Drosses e Intersede (org-wide) |
| `third_party_id` | UUID (GUID) | SÍ | FK `third_parties.id`. Solo poblado para Willard Baterías y Drosses |
| `is_active` | BOOLEAN | NO | Soft delete |
| `created_at`, `updated_at` | TIMESTAMPTZ | NO | `TimestampMixin` |

Invariantes:

- `UNIQUE (organization_id, code)` — cada org tiene sus propios códigos.
- `UNIQUE (organization_id, account_type, warehouse_id)` con `NULLS NOT DISTINCT` (PostgreSQL 15+; sin él, `NULL ≠ NULL` permitiría duplicar las cuentas org-wide) — evita duplicados de la misma cuenta lógica y a la vez permite los **dos sub-saldos** de `willard_baterias` (uno por sede de ingreso: CV/Barranquilla y BOG/Bogotá).
- Si `account_type IN ('willard_baterias', 'willard_drosses')` → `third_party_id IS NOT NULL`.
- Si `account_type = 'willard_baterias'` → `warehouse_id IS NOT NULL` (sub-saldo por sede).
- Si `account_type IN ('intersede', 'intra_horno', 'crisol')` → `third_party_id IS NULL`.

El saldo lógico "Willard Baterías" que se reporta a Willard es la suma de sus sub-saldos; la UI los muestra como una cuenta con desglose por sede.

Ejemplo JSON de creación (sub-saldo Barranquilla):

```json
{
  "code": "WILLARD-BAT-BAQ",
  "display_name": "Willard - Postconsumo Baterías (Barranquilla)",
  "account_type": "willard_baterias",
  "warehouse_id": "cv-warehouse-uuid",
  "third_party_id": "3f8...willard-uuid"
}
```

### Tabla `KgLedgerMovement` [NUEVO]

| Columna | Tipo | Nullable | Descripción |
|---------|------|----------|-------------|
| `id` | UUID (GUID) | NO | PK |
| `organization_id` | UUID (GUID) | NO | FK `organizations.id` |
| `account_id` | UUID (GUID) | NO | FK `kg_ledger_accounts.id` |
| `delta_kg` | NUMERIC(14,4) | NO | Positivo = acumula deuda / carga; negativo = descarga |
| `transaction_date` | TIMESTAMPTZ | NO | Fecha de negocio. **`BusinessDate` noon UTC** vía `BeforeValidator` — igual que `MoneyMovement.date` (evita el bug de zona horaria que se corrigió en [REUTILIZADO #24]). NO usar `Date` plano |
| `description` | VARCHAR(500) | SÍ | Nota libre |
| `source_type` | ENUM | NO | Ver §4.3 |
| `source_id` | UUID (GUID) | SÍ | FK polimórfico al documento origen (`InboundOrder.id`, `Transfer.id`, `Sale.id`, `FurnaceCharge.id`, etc.). Cada `source_type` define la tabla destino |
| `inventory_movement_id` | UUID (GUID) | SÍ | FK `inventory_movements.id` cuando el evento también movió inventario físico (permite trazabilidad cruzada) |
| `conversion_formula_snapshot` | JSONB | SÍ | Snapshot de la fórmula usada para calcular `delta_kg` (ver Anexo D para schema completo). Ejemplo: `{"formula_type": "battery_to_lead", "parameters": {"kg_lead_per_unit": 2.5}, "material_reference": "07", "willard_account_subtype": null}` |
| `status` | ENUM | NO | `confirmed \| annulled` — default `confirmed` |
| `annulled_reason` | VARCHAR(500) | SÍ | Motivo de anulación |
| `annulled_by` | UUID (GUID) | SÍ | FK `users.id` que anuló |
| `annulled_at` | TIMESTAMPTZ | SÍ | Timestamp de anulación |
| `created_by` | UUID (GUID) | NO | FK `users.id` que registró |
| `created_at`, `updated_at` | TIMESTAMPTZ | NO | `TimestampMixin` |

Invariantes:

- `delta_kg != 0` (no permite movimientos nulos — se anulan, no se insertan en cero).
- `status='annulled'` requiere los tres campos `annulled_*` poblados ([REUTILIZADO #48]).
- Los movimientos anulados **no cuentan** para saldo: `balance = SUM(delta_kg) WHERE status='confirmed'`.
- `transaction_date` siempre almacenado como noon UTC del día de negocio; presentación local se resuelve en frontend.

Ejemplo JSON de un movimiento (recepción de 100 baterías ref 07 de postconsumo Willard en CV, factor 2.5 kg/unidad):

```json
{
  "account_id": "willard-bat-uuid",
  "delta_kg": 250.0000,
  "transaction_date": "2026-06-30T12:00:00+00:00",
  "description": "Postconsumo Willard - 100 baterías ref 07",
  "source_type": "postconsumo_receipt",
  "source_id": "inbound-order-uuid",
  "inventory_movement_id": "inv-mov-uuid",
  "conversion_formula_snapshot": {
    "formula_type": "battery_to_lead",
    "parameters": {"kg_lead_per_unit": 2.5},
    "material_reference": "07",
    "willard_account_subtype": null
  }
}
```

### Endpoint estado de cuenta [NUEVO]

`GET /api/v1/kg-ledger/accounts/{id}/movements?date_from=&date_to=&status=` — análogo estructural a `GET /money-movements/third-party/{id}` ([REUTILIZADO #16, #55]). Retorna la lista de movimientos con saldo corrido (`balance_after` calculado in-memory tras `ORDER BY transaction_date, created_at`) y una fila sintética "Saldo Inicial" que aplica el mismo fix de decisión #55: apertura = `SUM(delta_kg) WHERE transaction_date < date_from AND status='confirmed'`.

Permiso: `kg_ledger.view` (nuevo, ver §14.1).

## 4.3 Eventos que mueven KgLedger [NUEVO]

El enum `KgLedgerMovement.source_type` cataloga todas las operaciones de negocio que generan un asiento en kg. Cada evento tiene: (a) el tipo `source_type`, (b) la tabla origen a la que apunta `source_id`, (c) la cuenta afectada, (d) el signo del `delta_kg`, y (e) el disparador operativo.

| Evento (`source_type`) | Origen (`source_id` → tabla) | Cuenta afectada | Signo | Disparador |
|------------------------|------------------------------|-----------------|-------|------------|
| `postconsumo_receipt` | `InboundOrder` | Willard Baterías | + | Recepción de baterías postconsumo Willard en CV o BOG. `conversion_formula_snapshot.formula_type='battery_to_lead'` |
| `drosses_receipt` | `InboundOrder` | Willard Drosses | + | Recepción de drosses Willard directamente en JM (`InboundOrder.goes_directly_to_jm=true` — drosses SIEMPRE ingresan por JM). `conversion_formula_snapshot.formula_type='drosses_to_lead'` |
| `willard_subbalance_move` | `Transfer` | Willard Baterías (par de sub-saldos) | ± | **Llegada física de baterías Bogotá → Circunvalar: mueve entre sub-saldos (BOG −, BAQ +)**. Dos asientos espejo del mismo evento; el saldo total Willard no cambia |
| `intersede_send` | `Transfer` | Intersede CV↔JM | + | **Recepción confirmada** del traslado de aportantes CV→JM (o BOG→JM): kg **recibidos** × factor de conversión vigente — lo recibido es la fuente de verdad (§5.1). El despacho solo mueve inventario a JM-TRANSITO, sin efectos kg/pesos. **Dispara además el par de maquila interna $1.500/kg (§5)**. Fuera de tolerancia (3–5%): excepción (§10.3) y emisión retenida |
| `intersede_return` | `Transfer` (JM→CV) | Intersede CV↔JM | − | Devolución física de aportante a CV **sin procesar**. Descarga los kg equivalentes devueltos y anula proporcionalmente el par de maquila del envío correspondiente (§5.1); si no es rastreable al envío origen, ajuste manual con `kg_ledger.manage_adjustments` |
| `furnace_charge` | `FurnaceCharge` [NUEVO] | Intra-horno JM | + | Carga de aportante al horno grande. Kg cargados (input físico), no aplica factor |
| `furnace_discharge` | `FurnaceCharge` (Fase 2) o descargo agregado periódico (Fase 1) | Intra-horno JM | − | Cierre de colada. En Fase 1 es un evento agregado diario que descarga con base en proporciones promedio (alinea con propuesta cliente §2.3). En Fase 2 es 1:1 por colada con trazabilidad |
| `crucible_charge` | `CrucibleCharge` [NUEVO] | Crisol JM | + | Carga de plomo crudo al crisol para refinación (el crisol solo recibe plomo crudo del horno) |
| `crucible_discharge` | `CrucibleCharge` | Crisol JM | − | Cierre de refinación. Produce plomo refinado (puro) en inventario. **Dispara además el par de maquila interna $300/kg (§5)** |
| `willard_delivery` | `Sale` | Willard Baterías o Willard Drosses | − | Entrega de plomo a Willard. Descarga la cuenta que indique la **remisión** de la entrega (`baterias \| drosses`) — dato del documento de entrega, no decisión al liquidar |
| `intersede_discharge` | `Sale` (JM) | Intersede CV↔JM | − | Salida de plomo procesado desde JM (venta/entrega). Descarga los kg pendientes más antiguos de la cuenta intersede. Solo mueve kg — la maquila en pesos ya se causó al envío (§5) |
| `manual_adjustment` | — (registro directo) | Cualquiera | ± | Ajuste manual con motivo obligatorio. Permiso especial `kg_ledger.manage_adjustments` |
| `migration_initial_load` | — (carga migración) | Cualquiera | + | Carga inicial de saldos de migración. Description obligatorio con marker `"Carga inicial migracion SAC"` ([REUTILIZADO #28] marker excluye estos movimientos de reportes operativos) |

### Nota crítica sobre `FurnaceCharge`/`CrucibleCharge` vs `MaterialTransformation` [NUEVO]

`FurnaceCharge` y `CrucibleCharge` son eventos **nuevos** y distintos de `MaterialTransformation` ([REUTILIZADO #17, #53]). La diferencia:

- `MaterialTransformation` modela un cambio de composición: 1000 kg batería entra, produce 600 kg plomo crudo + 200 kg plástico + 200 kg residuos. Actualiza costo promedio y produce `InventoryMovement` de destinos.
- `FurnaceCharge`/`CrucibleCharge` solo modelan el traslado de material al horno/crisol para mover el saldo KgLedger. No cambian composición ni tocan costo promedio hasta que se cierra la colada (que sí es una `MaterialTransformation` en Fase 2, o un descargo agregado en Fase 1).

Ejemplo numérico completo del ciclo, sin crisol adicional:

- CV recibe 1.000 kg de aportante scrap-con-borne de proveedor propio. Factor `scrap_with_terminal_to_lead` = 0.60 → equivalente 600 kg plomo si se transformara.
- CV despacha 1.000 kg de ese aportante a JM: `Transfer` con `quantity_dispatched=1000`, inventario CV → JM-TRANSITO. Sin efectos kg ni pesos todavía.
- JM confirma recepción (`quantity_received=1000`, dentro de tolerancia): en una sola transacción se mueve el inventario JM-TRANSITO → bodega JM, se genera `intersede_send`: `delta_kg=+600` en Intersede CV↔JM (sobre kg recibidos), y se causa la maquila del horno: par enlazado `internal_maquila_expense` (CV) + `internal_maquila_income` (JM) por $900.000 (ver §5.1-§5.2).
- JM carga los 1.000 kg al horno grande: `furnace_charge` `delta_kg=+1.000` en Intra-horno JM (aquí sí son kg físicos de aportante, no plomo equivalente).
- JM cierra la colada del día. Cierre agregado (Fase 1) descarga Intra-horno con base en proporción de aportante consumido: `furnace_discharge` `delta_kg=−1.000`. Se produce plomo crudo real (por ejemplo, 610 kg si la eficiencia fue del 61%) que ingresa a inventario físico como `MaterialTransformation` destino.
- JM vende 600 kg de plomo a Willard como abono: `Sale.liquidate` dispara `willard_delivery` `delta_kg=−600` en el sub-saldo Willard Baterías que indique la remisión, e `intersede_discharge` `delta_kg=−600` en Intersede CV↔JM (solo kg — la maquila en pesos ya se causó al envío, §5).
- Los 10 kg extra (610 producidos − 600 entregados) quedan como inventario SAC — plomo excedente por eficiencia real superior al factor contractual (ver §4.4).

## 4.4 Factor contractual vs eficiencia real [NUEVO]

Este es uno de los conceptos que más se malinterpretó en el v0.3 y que Hugo aclaró explícitamente en la reunion noche 2026-06-26. Cierra el riesgo R12 identificado en analysis: el factor Willard es **contractual, no fisico**. La eficiencia real del proceso de SAC (mejor o peor extracción) va al inventario propio de SAC, nunca al saldo Willard.

**Principio:** cuando Willard entrega N unidades de referencia R, la deuda que SAC contrae con Willard es exactamente `N × factor(R)` kg de plomo. Ese es el número fijo que aparece en `KgLedgerMovement(source_type='postconsumo_receipt')`. Si SAC procesa mejor o peor, la variación queda absorbida por su inventario, no por la deuda kg.

Hugo lo formuló textualmente: *"No, no, ya ahí la sumo yo completamente. Para ellos va a ser lo mismo siempre"* (Hugo, reunion noche 2026-06-26).

### Ejemplo numérico

Willard entrega 1.000 unidades de baterías ref 07 con factor contractual 2.5 kg/unidad. La deuda kg contraída es fija:

`KgLedgerMovement(account=Willard Baterías, delta_kg=+2.500, formula_snapshot={kg_lead_per_unit: 2.5, material_reference: '07'})`

SAC procesa esas 1.000 baterías. Salen tres escenarios:

| Escenario | Plomo producido real | Deuda kg a Willard | Entregado a Willard | Inventario SAC resultante |
|-----------|----------------------|--------------------|--------------------|---------------------------|
| Neutro | 2.500 kg | 2.500 | 2.500 | 0 kg de este lote |
| Eficiente | 2.550 kg | 2.500 | 2.500 | +50 kg (ganancia en `MaterialTransformation.value_difference` según método de costo) |
| Ineficiente | 2.470 kg | 2.500 | 2.500 | −30 kg (déficit — SAC lo cubre con plomo de otras fuentes; pérdida operativa) |

**Implicación contable:** `KgLedger` Willard Baterías se descarga **exclusivamente** por `willard_delivery.delta_kg`, no por la producción real. Los kg de plomo producidos son un evento separado que actualiza inventario físico y costo promedio ([REUTILIZADO #5, #17]). La diferencia entre "kg contractual asumidos" y "kg reales extraídos" queda visible en el reporte de eficiencia de proceso (fuera de scope Fase 1 formal, se aproxima con drill-down entre `KgLedgerMovement.delta_kg` y `MaterialTransformation.value_difference`).

**Por qué esto justifica que `KgLedger` sea un módulo separado de inventario:** si la deuda Willard se recalculara con eficiencia real, entonces `KgLedgerMovement` tendría que reflejar los kg producidos y no los kg contractuales — pero eso rompería la lógica comercial ("le debo a Willard lo que le prometí, no lo que extraje"). La separación entre `InventoryMovement` (kg reales físicos) y `KgLedgerMovement` (kg contractuales acordados) es lo que permite modelar sin ambigüedad este comportamiento.

## 4.5 Conciliación semanal con Willard [NUEVO]

Cada viernes se ejecuta un cierre semanal con Willard donde ambas partes cuadran los saldos kg. Lo maneja el **coordinador de postconsumo nacional** (persona de SAC, §2.4 — envía el cuadro a Willard y concilia el saldo nacional); Johana cuadra el sub-saldo Barranquilla que alimenta ese consolidado. En lenguaje cliente: *"cada viernes se contienen los saldos con ellos"* (Hugo, reunion noche 2026-06-26). El sistema debe facilitar este ritual sin reemplazar el juicio operativo de ninguno de los dos.

### Reporte "Cuadre Semanal Willard" [NUEVO]

`GET /reports/willard-weekly-reconciliation?week_ending=YYYY-MM-DD` (`week_ending` = viernes de cierre — parámetro canónico, ver contrato completo en §12.1.5) — permiso `willard.reconcile` (§14.1). Retorna, por cada una de las dos cuentas Willard (Baterías y Drosses):

- Saldo apertura de la semana (`transaction_date < week_start`, `status='confirmed'`), con desglose de sub-saldos por sede para Willard Baterías.
- Movimientos de la semana agrupados por tipo (`postconsumo_receipt`, `drosses_receipt`, `willard_delivery`, `willard_subbalance_move`, `manual_adjustment`).
- **Detalle por entrega (fecha, remisión, kg)** de cada `willard_delivery` de la semana — la diferencia típica con Willard es una entrega que un lado registró y el otro no.
- Saldo cierre de la semana.
- Bloque de discrepancias detectadas: movimientos sin `conversion_formula_snapshot` (no debería pasar), entregas sin remisión adjunta, factores usados que difieren del vigente hoy (indicativo de renegociación).
- Desglose informativo por centro de distribución Willard (`willard_distribution_center`, ver §6.5) — no afecta saldo total, solo permite a Willard rastrear origen.

**Regla de negocio Johana (reunion mañana 2026-06-26):** *"ese inventario no lo tengo yo aquí... yo no lo estoy debiendo hasta que no ingresen"*. La deuda solo se activa cuando el material fisicamente ingresa a una planta SAC. Esto ya está garantizado por el diseño: `KgLedgerMovement` se crea a partir de `InboundOrder`, que exige recepción física para completarse.

### Firma del cuadre — "OK del viernes"

Al finalizar el cuadre, se marca la semana como cerrada. El cuadro semanal lo envía a Willard y lo concilia el **coordinador de postconsumo nacional** (§2.4); el cuadre consolida el saldo nacional (sub-saldos BAQ/BOG más centros informativos — detalle a confirmar con el coordinador al arranque). Se emite un `KgLedgerReconciliationSeal` (registro auditable): usuario, timestamp, saldos cerrados, hash de los movimientos incluidos. A partir de ese momento, editar o anular movimientos de esa semana requiere permiso especial `kg_ledger.edit_after_seal` (solo admin) y deja bitácora explícita. Comportamiento análogo al bloqueo de periodo contable en cierres mensuales.

### Actualización IPC anual

Las tarifas Willard (maquila $2.097/kg, fletes) se actualizan anualmente con IPC ([REUTILIZADO #35 patrón append-only] sobre `ServiceTariff`, ver §6.3). La conciliación anual (típicamente en enero) genera nuevos registros de `ServiceTariff` con `unit_price_cop` ajustado; las operaciones anteriores mantienen su `tariff_id` snapshot para trazabilidad histórica. Los factores de conversión Willard (`MaterialConversionFormula`) también son append-only y pueden actualizarse en renegociaciones (caso reciente: SEC ESCURRIDO vs SEC PINZA, ver §6.4).

## 4.6 Saldos iniciales en kg (migración) [NUEVO]

La migración de SAC a EcoBalance requiere cargar los saldos kg de arranque en todas las cuentas `KgLedger`. Referencia conocida: 422 toneladas de deuda Willard total (Hugo, reunion noche 2026-06-26), desagregado como ~131 ton en el sub-saldo BAQ y ~48 ton en el sub-saldo BOG, más lo distribuido en otros centros Willard (informativos — no son bodegas SAC). Los saldos exactos (Willard, Intersede, Intra-horno y Crisol) son **datos de configuración que se recogen al corte de arranque** — no bloquean el cierre del alcance; regla del cliente: no se piden saldos antes de la propuesta comercial.

### Hoja nueva `CuentasPlomo` en migration template [NUEVO]

Se extiende el `data/migration_template.xlsx` existente ([REUTILIZADO #28] script `migrate_org.py`) con una hoja nueva `CuentasPlomo`. Cada fila representa una `KgLedgerAccount` con su saldo inicial:

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `code` | string | Código único (`WILLARD-BAT-BAQ`, `WILLARD-BAT-BOG`, `WILLARD-DROSS`, `INTERSEDE-CV-JM`, `INTRA-HORNO-JM`, `CRISOL-JM`) |
| `display_name` | string | Nombre presentable |
| `account_type` | enum | `willard_baterias \| willard_drosses \| intersede \| intra_horno \| crisol` |
| `warehouse_id` | string (código) | Código warehouse referenciado (si aplica) |
| `third_party_code` | string | Código Willard (si aplica) |
| `saldo_inicial_kg` | decimal | Saldo al corte |
| `fecha_corte` | date | Fecha del snapshot |
| `notas` | string | Contexto libre |

Al ejecutar `migrate_org.py --apply`, el script crea las `KgLedgerAccount` y por cada fila con `saldo_inicial_kg != 0` inserta un `KgLedgerMovement(source_type='migration_initial_load', description='Carga inicial migracion SAC', delta_kg=<saldo>, transaction_date=<fecha_corte a noon UTC>)`. El marker en `description` es lo que permite a los reportes operativos filtrar y excluir estos movimientos ([REUTILIZADO #28] patrón idéntico al de `InventoryAdjustment` con reason `"Carga inicial migracion..."`) — porque el saldo inicial representa patrimonio de arranque, no ganancia/pérdida operativa.

### Verificación post-load

`migrate_org.py --dry-run` y `--apply` reportan, entre las validaciones automáticas de decisión #28:

- Suma de `saldo_inicial_kg` por `account_type` cuadra con las cifras conocidas de Hugo (422 ton total Willard Baterías + Drosses, dentro de tolerancia).
- Ninguna cuenta con `saldo_inicial_kg < 0` a menos que se pase `--allow-negative-kg` (default no).
- Nueva flag `--kg-tolerance` (default 5 kg por cuenta, configurable) — análoga a `--balance-tolerance` existente.
- Todas las cuentas Willard tienen `third_party_code` referenciando a un `ThirdParty` que ya existe en la hoja `Terceros`.

### Excels a recoger al corte de arranque (post-propuesta comercial)

Estos cuadros son **datos de configuración de arranque** — se recogen SOLO después de aceptada la propuesta comercial (regla del cliente: no pedir saldos confidenciales antes; §18.2): (a) cuadro deuda Willard con desglose BAQ/BOG/otros centros, (b) cuadro saldos Intersede al corte, (c) cuadro saldos Intra-horno y Crisol al corte (Johana los lleva mentalmente — puede requerir sesión guiada), (d) tabla factores de conversión Willard vigente por referencia, (e) inventarios físicos por sede (ya cubierto por hoja `InventarioInicial` existente).

Regla operativa: **solo saldos iniciales, no historial transaccional** (Johana, Hugo, reunion noche 2026-06-26). Cargar historial completo generaría volumen inmanejable sin agregar valor operativo: la conciliación semanal con Willard opera a nivel de saldo, no de detalle histórico.

---

# 5. Maquila intersede (CV→JM, causación al envío)

Este capítulo modela el mecanismo por el cual la sede Juan Mina "cobra" a la sede Circunvalar (o Bogotá) por procesar su material. **Modelo cerrado en la visita a planta del 2026-07-02, validado por Hugo Y por Johana**: la maquila del horno — **$1.500/kg de plomo equivalente** — se causa **al confirmar el envío/traslado CV→JM** del material aportante, y el adicional de crisol — **$300/kg** — se causa **a la salida del crisol** (cuando la refinación produce plomo puro). En ambos momentos el efecto es un doble asiento simétrico — **gasto de Circunvalar e ingreso de Juan Mina** — materializado como un **par de `MoneyMovement` internos enlazados** (§5.2). Aunque técnicamente es una operación intra-sociedad (CV/JM/BOG son la misma SAC, ver §2.1), Hugo y Johana requieren visibilidad gerencial de la utilidad por sede — política "utilidad cero JM/BOG" (ver §3.5) — y este mecanismo la refleja sin inventar terceros ficticios intercompañía.

El transporte CV→JM es con **carros propios** — no hay flete en este tramo (cerrado en visita 2026-07-02; cierra la duda que §6.2 dejaba abierta en v0.4). Las tarifas son **valores sugeridos y parametrizables** con vigencia histórica (`ServiceTariff` append-only, §6.3); como la causación es inmediata al evento, aplica la tarifa vigente al momento del envío (o de la salida del crisol) — ya no se necesita snapshot de tarifa en tablas intermedias.

## 5.1 Los dos momentos de causación (envío y salida del crisol)

La contradicción de fuentes que el v0.4 dejaba como bloqueante (Hugo: *"con la factura"*; Johana: *"apenas ingresa a planta"*) se resolvió el 2026-07-02 — Johana en la visita a planta y Hugo por WhatsApp: **la maquila se causa al envío**. Los dos momentos del modelo definitivo:

### Momento 1: Envío/traslado CV→JM confirmado (maquila del horno, $1.500/kg)

Cuando CV (o BOG) despacha material aportante a JM, el flujo son **dos pasos sobre el mismo `Transfer`** ([REUTILIZADO] modelo existente `transfer_between_warehouses`, extendido con doble cantidad §7.5):

- **Paso A — Despacho**: se crea `Transfer` con `quantity_dispatched`; `InventoryMovement OUT` en CV + `IN` en JM-TRANSITO (bodega virtual, §7.5). **Sin efectos todavía en KgLedger ni en pesos.**
- **Paso B — Recepción confirmada en JM**: se registra `quantity_received` — **lo recibido es la fuente de verdad** (visita 2026-07-02). En una sola transacción atómica se emiten los tres efectos: (1) `InventoryMovement` JM-TRANSITO → bodega JM por lo recibido; (2) `KgLedgerMovement(account=Intersede CV↔JM, delta_kg=+kg_plomo_equivalente_recibido, source_type='intersede_send', source_id=Transfer.id)` — plomo equivalente = kg recibidos × factor del material (`MaterialConversionFormula` vigente); (3) el **par enlazado** de `MoneyMovement`: `internal_maquila_expense` (`warehouse_id=CV`) + `internal_maquila_income` (`warehouse_id=JM`), monto = `kg_plomo_equivalente_recibido × $1.500`, categoría "Maquila Intersede". Detalle en §5.2.
- **Tolerancia**: si despachado vs recibido difieren dentro del 3–5% configurable (§7.5), el ajuste de inventario es automático con lo recibido como fuente de verdad. **Fuera de tolerancia**, la discrepancia crea una excepción en el panel (§10.3) y el par NO se emite hasta resolverla (justificar o corregir el documento origen).
- **Criterio de "material aportante"**: existe `MaterialConversionFormula` vigente para el material (§6.4). Traslados CV→JM de otros materiales (plomo puro, insumos, herramientas) NO disparan `intersede_send` ni par de maquila.
- **Lectura de negocio**: la causación sigue siendo "al envío" tal como lo cerró la visita — el evento causante es el traslado (no la venta posterior). Operativamente despacho y recepción del tramo CV→JM ocurren el mismo día (carros propios); el sistema ancla la emisión a la confirmación de recepción para que el monto se calcule sobre los kg recibidos, sin mecanismo de ajuste posterior.

### Momento 2: Salida del crisol (adicional de refinación, $300/kg)

Cuando la refinación en crisol produce plomo puro (`CrucibleDischarge`, ver §4.3 y §7.4):

- Se descarga la cuenta kg Crisol y entra plomo refinado a inventario.
- Se emite un segundo **par enlazado** análogo: `internal_maquila_expense` (CV) + `internal_maquila_income` (JM), monto = `kg de plomo puro producido × $300`, categoría "Crisol Refinacion".

### Qué pasa en los demás eventos

- **Despacho sin recepción confirmada**: el material queda en JM-TRANSITO sin efectos kg ni pesos; si el `Transfer` sigue pendiente al cierre del día, aparece en el panel de excepciones (§10.3).
- **Venta/salida de plomo procesado desde JM**: descarga la cuenta kg intersede (`intersede_discharge`, los kg pendientes más antiguos) pero **NO causa maquila** — ya se causó al envío. La liquidación de la venta solo tiene sus efectos estándar (precios, balance cliente, `willard_delivery` si es abono a Willard).
- **Devolución JM→CV sin procesar** (`intersede_return`, ver §4.3): Transfer inverso que descarga la cuenta intersede (−kg equivalente devuelto) y **anula proporcionalmente el par de maquila** del envío correspondiente (anular-y-reemitir por el neto cuando la devolución es rastreable al Transfer origen); si no es rastreable, se maneja como excepción con ajuste manual (`kg_ledger.manage_adjustments`) y bitácora.

La cuenta kg intersede **sigue existiendo** con su semántica de siempre: +kg con el traslado CV→JM (emitido al confirmar la recepción, §5.1), −kg al salir el plomo procesado de JM. Lo que desaparece respecto del v0.4 es la maquinaria de causación diferida **en pesos** atada a ese saldo.

## 5.2 Par de MoneyMovements internos enlazados [NUEVO]

> **Nota de decisión (v0.4 → v0.5).** El modelo de causación diferida del v0.4 — dos tablas (`PendingMaquilaCommitment` y `MaquilaConsumption`) que registraban un compromiso al despachar y lo consumían FIFO al liquidar la venta en JM — se **descartó en la visita a planta del 2026-07-02**. Razón: el cliente causa la maquila **al envío**, y lo confirmaron ambos lados (Johana en la visita; Hugo por WhatsApp), lo que simplifica considerablemente el diseño. Esas tablas, sus endpoints, sus tests y su esfuerzo estimado se eliminan del diseño activo; esta nota se conserva solo por trazabilidad de la decisión.

El mecanismo definitivo son **dos tipos nuevos de `MoneyMovement`**, emitidos siempre en par y enlazados entre sí (patrón linked pair de los transfers de tesorería existentes):

| Atributo | `internal_maquila_expense` | `internal_maquila_income` |
|---|---|---|
| Semántica | Gasto interno de la sede que consume el servicio | Ingreso interno de la sede que presta el servicio |
| `account_id` | `NULL` — causación pura, patrón `expense_accrual` ([decision #14]): no mueve caja ni bancos | `NULL` — ídem |
| `third_party_id` | `NULL` — mismo NIT (§2.1), no existe tercero intercompañía | `NULL` — ídem |
| `warehouse_id` | Momento 1: sede origen del material (CV o BOG). Momento 2 (crisol): **siempre CV** (visita 2026-07-02; en Fase 1 el descargo del crisol es agregado y el origen del crudo no es determinable) | JM (sede que presta el servicio) |
| `business_unit_id` | Heredada de `Material.business_unit_id` (las sedes NO son UN, §2.3) | Ídem |
| `expense_category` | "Maquila Intersede" (momento 1) o "Crisol Refinacion" (momento 2) | Ídem (misma categoría, lado ingreso) |
| `amount` | `kg × tarifa vigente` ($1.500/kg envío; $300/kg crisol) | Idéntico al del expense (simetría exacta) |
| Enlace | `linked_movement_id` → apunta al income | `linked_movement_id` → apunta al expense |
| Creación | Automática: confirmación de la **recepción** del traslado CV→JM (momento 1, sobre kg recibidos §5.1) o `CrucibleDischarge` (momento 2). No se crean a mano | Ídem (mismo evento, misma transacción) |
| Anulación | Anular uno anula el otro (cascade del par, patrón transfers + [decision #48]). Anular el traslado/cierre de crisol origen anula el par completo | Ídem |
| `status` | `confirmed \| annulled` | Ídem |

Reglas:

- El par se crea **atómicamente** en la misma transacción que el evento origen (traslado confirmado o cierre de refinación); si algo falla, se revierte todo.
- **Reportes consolidados SAC excluyen ambos tipos por filtro de tipo de movimiento** — se netean a cero entre sí (mismo NIT) y excluirlos evita inflar los ingresos y gastos brutos. Las **vistas por sede los incluyen**: CV ve el gasto, JM ve el ingreso.
- No afectan balances de terceros ni de cuentas (`account_id=NULL`, `third_party_id=NULL`) — solo P&L gerencial por sede.
- La tarifa aplicada es la vigente en `ServiceTariff` al momento del evento; el MM persiste el monto calculado y `tariff_id` como referencia de trazabilidad (los cambios futuros de tarifa no son retroactivos, §6.3).

Ejemplo JSON del par (momento 1, envío de 600 kg de plomo equivalente):

```json
[
  {
    "movement_type": "internal_maquila_expense",
    "amount": 900000,
    "account_id": null,
    "third_party_id": null,
    "warehouse_id": "cv-warehouse-uuid",
    "business_unit_id": "un1-reciclaje-plomo-uuid",
    "expense_category": "Maquila Intersede",
    "linked_movement_id": "mm-income-uuid",
    "source_type": "transfer",
    "source_id": "transfer-uuid",
    "description": "Maquila intersede - Transfer #142 (600 kg plomo equivalente)"
  },
  {
    "movement_type": "internal_maquila_income",
    "amount": 900000,
    "account_id": null,
    "third_party_id": null,
    "warehouse_id": "jm-warehouse-uuid",
    "business_unit_id": "un1-reciclaje-plomo-uuid",
    "expense_category": "Maquila Intersede",
    "linked_movement_id": "mm-expense-uuid",
    "source_type": "transfer",
    "source_id": "transfer-uuid",
    "description": "Maquila intersede - Transfer #142 (600 kg plomo equivalente)"
  }
]
```

## 5.3 Causación contable (asientos generados)

Detalle exhaustivo de los asientos generados en cada momento del modelo v0.5. Claves: par de MMs internos enlazados sin cuenta y sin tercero, `warehouse_id` distinto en cada lado (CV gasto / JM ingreso), `business_unit_id` heredada del material procesado (§2.3) para clasificación gerencial. NO se crea un `ThirdParty` intercompañía ficticio.

### Escenario: CV despacha 1.000 kg aportante scrap (factor 0.6); luego el crisol produce 600 kg de plomo puro

**Momento 1 (envío/traslado CV→JM confirmado):**

1. **Despacho**: `Transfer(from=CV, to=JM-TRANSITO, material=aportante, quantity_dispatched=1000 kg)` → `InventoryMovement OUT` en CV (−1.000 kg) + `IN` en JM-TRANSITO (+1.000 kg). Sin efectos kg/pesos.
2. **Recepción confirmada** (`quantity_received=1000 kg`, dentro de tolerancia) — en la misma transacción: `InventoryMovement` JM-TRANSITO → bodega JM + `KgLedgerMovement(account=Intersede CV↔JM, delta_kg=+600, source_type='intersede_send', source_id=Transfer.id, conversion_formula_snapshot={formula_type:'scrap_with_terminal_to_lead', parameters:{scrap_factor:0.6}})`.
3. **Par enlazado de `MoneyMovement`** (la misma transacción del paso 2):
   - `internal_maquila_expense`: `account_id=NULL`, `third_party_id=NULL`, `business_unit_id=<UN del material>` (heredada — CV NO es una UN, §2.3), `warehouse_id=CV`, `amount = 600 kg × $1.500/kg = $900.000`, categoría "Maquila Intersede".
   - `internal_maquila_income`: idéntico salvo `warehouse_id=JM`; ambos apuntándose vía `linked_movement_id`.

**Momento 2 (cierre de refinación en crisol — produce 600 kg de plomo puro):**

4. `CrucibleDischarge`: `KgLedgerMovement(account=Crisol JM, delta_kg=−600)` + `InventoryMovement IN` de plomo refinado.
5. **Segundo par enlazado**: `internal_maquila_expense` (CV) + `internal_maquila_income` (JM), `amount = 600 kg × $300/kg = $180.000`, categoría "Crisol Refinacion".

**Al vender el plomo desde JM (efectos estándar únicamente):**

6. `Sale.liquidate()` — precios, balance cliente, `willard_delivery` (si es abono a Willard) e `intersede_discharge` (`delta_kg=−600` en la cuenta kg intersede). **Cero causación de maquila** — ya ocurrió en los pasos 3 y 5.

Total causado en el escenario completo: $1.080.000 como gasto interno de CV y $1.080.000 como ingreso interno de JM (maquila $900.000 + crisol $180.000).

### Reflejo en P&L por sede y en consolidado

El reporte de P&L por sede filtra por `warehouse_id` en `MoneyMovement`, y con este modelo ambos lados son asientos reales:

- `P&L warehouse_id=CV`: aparece el gasto `internal_maquila_expense` ($1.080.000).
- `P&L warehouse_id=JM`: aparece el ingreso `internal_maquila_income` ($1.080.000) — la base de la política "utilidad cero" (§3.5).
- `P&L consolidado SAC` (sin filtro de sede): **excluye ambos tipos internos por filtro de tipo de movimiento**. Se netean a cero entre sí (mismo NIT, §2.1) y excluirlos evita inflar ingresos y gastos brutos del consolidado. No hay vistas derivadas ni líneas sintéticas.

### Contraste con maquila Willard (§6)

**No confundir:** la maquila Willard ($2.097/kg) emite `service_income` con `third_party=Willard real`, porque Willard es tercero externo con NIT distinto. En cambio, la maquila intersede emite el par interno sin tercero y sin cuenta. La diferencia refleja el hecho de que Willard es una relación contractual externa (ingreso real que permanece en el consolidado), mientras que CV↔JM es un cargo interno gerencial (visibilidad por sede, neteado en consolidado).

## 5.4 Edge cases (anulación, merma, tolerancia, tarifa vigente) [NUEVO]

Tests bloqueantes del modelo:

- `test_transfer_reception_creates_maquila_pair`: confirmar la **recepción** de un traslado CV→JM de material aportante crea exactamente un par `internal_maquila_expense` + `internal_maquila_income` con montos idénticos, `account_id=NULL`, `third_party_id=NULL`, `warehouse_id` CV/JM y `linked_movement_id` cruzados.
- `test_crucible_discharge_creates_crucible_pair`: el cierre de refinación crea el par de $300/kg sobre los kg de plomo puro producidos.
- `test_transfer_annulment_annuls_pair`: anular el traslado anula ambos MMs del par (y el `KgLedgerMovement` intersede) en cascade.
- `test_consolidated_pnl_excludes_internal_types`: el P&L consolidado no incluye ninguno de los dos tipos internos; el P&L por sede sí.
- `test_sale_liquidation_does_not_create_maquila`: liquidar una venta desde JM no crea movimientos de maquila interna (solo `intersede_discharge` en kg).
- `test_transfer_out_of_tolerance_blocks_pair`: una recepción con diferencia fuera de tolerancia NO emite el par, crea `DiscrepancyTask` (§10.3) y la emisión ocurre al resolverla.
- `test_non_contributor_transfer_creates_no_pair`: trasladar CV→JM un material sin `MaterialConversionFormula` vigente (p.ej. plomo puro, insumos) no crea `intersede_send` ni par de maquila.

### Anulación de un traslado ya causado

Anular el `Transfer` revierte los tres efectos: `InventoryMovements` anulados, `KgLedgerMovement` intersede a `status='annulled'`, y el **par de maquila anulado en cascade** (ambos lados, patrón [decision #48]). Si el material del traslado ya fue cargado al horno o vendido, la anulación se bloquea con 400 — primero hay que revertir los eventos posteriores.

### Diferencia despachado vs recibido (tolerancia)

El par se emite en la recepción sobre los **kg recibidos confirmados** — lo recibido es la fuente de verdad (visita 2026-07-02), así que no existe "ajuste del par": el monto nace correcto. Dentro de la tolerancia (3–5% configurable, §7.5) la diferencia despachado/recibido se ajusta automáticamente en inventario. Fuera de tolerancia, la discrepancia genera una excepción en el panel (§10.3) y el par queda **retenido** hasta resolverla (justificación o corrección del documento origen, con bitácora) — al resolver, se emite con la cantidad final.

### Merma en horno

La merma del horno **ya no afecta la causación en pesos** — la maquila se causó al envío sobre el plomo equivalente enviado, exactamente como el cliente la cobra. La merma es un hecho de proceso que se refleja en: (a) la cuenta kg Intra-horno (descargo agregado menor que la carga), y (b) la cuenta kg Intersede, que se ajusta con `KgLedgerMovement(source_type='manual_adjustment')` y permiso `kg_ledger.manage_adjustments` si quedan kg huérfanos al cierre. El panel de excepciones (§10.3) alerta sobre saldos intersede sin movimiento antiguos.

### Sede del gasto en el par de crisol

El par del crisol ($300/kg) carga el gasto **siempre a CV** (visita 2026-07-02). En Fase 1 el descargo del crisol es un evento agregado sin trazabilidad uno-a-uno (§4.4): el origen del plomo crudo refinado (aportantes CV, compras locales JM, drosses Willard) no es determinable por lote, así que no se intenta prorratear por sede de origen. Si en Fase 2 la trazabilidad por colada lo permite y el cliente lo pide, el prorrateo se revisa — hoy no.

### Cambio de tarifa

La tarifa aplicada es la vigente al momento del evento (`ServiceTariff` current, §6.3). Renegociaciones posteriores (IPC) no son retroactivas: los pares ya emitidos conservan su monto. Tarifas sugeridas y parametrizables.

## 5.5 Comparación con maquila Willard (tabla diferencias) [NUEVO]

Ambas maquilas comparten conceptualmente el patrón *"SAC procesa material ajeno a cambio de una tarifa"*. Sin embargo, técnicamente son distintas en varios aspectos que la tabla siguiente enumera.

| Dimensión | Maquila intersede (CV→JM) | Maquila Willard (SAC→Willard) |
|-----------|---------------------------|-------------------------------|
| Contraparte | Sede propia (mismo NIT, §2.1) | Tercero externo Willard (NIT distinto) |
| Tarifa | $1.500/kg de plomo equivalente + $300/kg a la salida del crisol (sugeridas y parametrizables) | $2.097/kg (uniforme baterías/drosses) |
| Momento causación | **Al confirmar el envío** ($1.500) y **a la salida del crisol** ($300) — visita 2026-07-02 | A la entrega — se factura **por cada entrega** (§6.1) |
| Tipo de `MoneyMovement` | Par enlazado `internal_maquila_expense` + `internal_maquila_income` (sin cuenta, sin tercero) | `service_income` (ingreso real con Willard tercero) |
| `third_party_id` | `NULL` | Willard real |
| `account_id` | `NULL` (causación pura) | `NULL` — causación de CxC (§6.1); el cobro es un `MoneyMovement` separado |
| Reflejo en P&L consolidado SAC | **Excluido por filtro de tipo** (se netea a cero) | Ingreso real, permanece |
| Reflejo en P&L por sede | CV ve gasto real, JM ve ingreso real (ambos lados son asientos) | Sede que emite la remisión ve el ingreso |
| Mecanismo intermedio | Ninguno — causación inmediata al evento | Ninguno — kg se causan directamente al facturar la entrega |
| Fuente de la tarifa | `ServiceTariff(tariff_code='maquila_intersede_cv_jm' / 'maquila_crisol')` — vigente al momento del evento | `ServiceTariff(tariff_code='maquila_willard')` — leído `current` al facturar |
| Movimiento en `KgLedger` | `intersede_send` al confirmar la recepción del traslado (kg recibidos, §5.1) + `intersede_discharge` al salir plomo procesado | `postconsumo_receipt`/`drosses_receipt` al recibir + `willard_delivery` al entregar |
| Actualización periódica | Configurable (IPC opcional) | Anual con IPC ([REUTILIZADO #35] append-only `ServiceTariff`) |

Puntos clave a recordar:

- La maquila intersede es un cargo interno gerencial que no altera el resultado contable consolidado, solo permite mostrar visibilidad por sede.
- La maquila Willard sí impacta el P&L SAC porque Willard es tercero externo — es el ingreso principal del canal postconsumo.
- Ambas usan la tarifa vigente de `ServiceTariff` al momento del evento; ninguna necesita snapshot intermedio porque la causación es inmediata en ambos casos.

---

# 6. Maquila Willard (factor contractual, tarifas y fletes)

Este capítulo cubre el modelo comercial y técnico de la relación con Willard — el tercero comercial más importante de SAC. Se cierran las preguntas Q7 (modelo contable Willard) y las tarifas de fletes explicitadas por Hugo (reunion noche 2026-06-26), y se detalla el modelo maestro de tarifas (`ServiceTariff`) y factores de conversión (`MaterialConversionFormula`), ambos append-only en línea con decisión #35 (patrón `PriceList`).

## 6.1 Modelo comercial Willard [CERRADO Q7 con cita Hugo 2026-06-26]

Hugo cerró Q7 con cita textual: *"2097 pesos"* (Hugo, reunion noche 2026-06-26, 10:09). El modelo comercial queda como sigue:

- **Tarifa uniforme:** $2.097 por kg de plomo entregado a Willard, igual para baterías (postconsumo unidad) y drosses (postconsumo kg). Aplica sobre kg de plomo que sale en la remisión, no sobre kg de input.
- **Base de facturación:** SAC emite factura periódica a Willard por kg de plomo entregado × $2.097. La factura es en pesos (Willard paga en pesos, no en plomo — el plomo viaja en sentido opuesto como abono a la deuda kg).
- **Momento de causación:** a la entrega — la maquila **se factura por cada entrega** (no mensual), precisado en la visita 2026-07-02. El ingreso se causa al liquidar la venta/entrega correspondiente (Hugo, reunion noche 2026-06-26: *"con la factura es que se abona la maquila"*). Se apoya en el patrón `Sale.liquidate` existente en EcoBalance ([REUTILIZADO] workflow 2-step decisión #2).
- **Actualización periódica:** anual con IPC (Índice de Precios Consumidor, corrección explícita al v0.3 que mencionaba "PIC"). Cada renegociación anual genera un nuevo registro `ServiceTariff` append-only (ver §6.3); las operaciones anteriores mantienen su snapshot histórico.
- **Categoría contable:** ingreso por servicios — `expense_category='Maquila Willard'` (seed system).

Aunque Q7 está cerrada con cita explícita de Hugo, se recomienda formalizarla contractualmente al arranque, antes de implementar los reportes de conciliación semanal. Es la decisión que más peso comercial tiene en el sistema y merece validación firmada.

### Emisión del `MoneyMovement` de maquila Willard

Al liquidar una `Sale` a Willard, se emite:

```
MoneyMovement(
  type='service_income',
  account_id=NULL,  -- causación pura de CxC: la factura se cobra después
  third_party_id=<Willard real>,
  business_unit_id=<UN2 Maquila Willard>,
  warehouse_id=<sede que despacha, típicamente JM>,
  amount=<kg plomo entregado × $2.097>,
  expense_category='Maquila Willard',
  description='Maquila Willard - Sale <sale_id>'
)
```

**Causación ≠ cobro** (invariante EcoBalance "Liquidación ≠ Pago"): este `service_income` se emite con `account_id=NULL` — es el espejo de ingreso del patrón `expense_accrual` ([decision #14]) — e **incrementa la CxC de Willard** (`Willard.balance` sube: Willard nos debe la factura de la entrega). El **cobro es un `MoneyMovement` separado** (`collection_from_client`: cuenta bancaria +, balance Willard −) cuando Willard paga la factura. Así el bloque "CxC Willard" del dashboard (§10.4) refleja las facturas pendientes reales. Es ingreso real de SAC con tercero externo y participa del P&L consolidado sin eliminación — a diferencia del par interno intersede.

## 6.2 Fletes Willard (ingreso para SAC) y fletes internos (gasto) [NUEVO]

Hugo confirmó explícitamente dos tarifas de flete que SAC factura a Willard como servicio adicional a la maquila. Estas son ingresos para SAC, no costos. Existen adicionalmente fletes internos de SAC (movimientos entre sedes propias) que sí son gasto operativo. La distinción es crítica porque el v0.3 las confundía.

### Fletes Willard (INGRESO)

Dos tarifas contractuales — valores sugeridos y parametrizables (`ServiceTariff`, vigencia histórica). **Con momentos de facturación distintos, precisados en la visita 2026-07-02:**

| Concepto | Tarifa | Base | Momento de facturación | Fuente |
|----------|--------|------|------------------------|--------|
| Flete Willard planta – Willard | $37/kg de plomo entregado (corrige el $38 de v0.4 — visita 2026-07-02) | Kg de plomo entregado en la remisión final | **Por cada entrega**, junto con la maquila | Hugo 2026-06-26 (~00:22:55), tarifa corregida en visita 2026-07-02 |
| Flete Willard BOG-BAQ | $216/kg de batería | Kg de batería trasladada desde BOG hacia BAQ | **Mensual** — se factura a Willard una vez al mes | Hugo 2026-06-26: *"son 216 pesos por kilogramo de batería"* |

Modelo técnico: dos códigos adicionales en `ServiceTariff`:

- `flete_willard_bog_baq` con `unit_price_cop=216`, `unit='per_kg_battery'`.
- `flete_willard_planta_planta` con `unit_price_cop=37`, `unit='per_kg_lead'`.

Causación (dos momentos distintos):

- **Por cada entrega** (en el `Sale.liquidate` de esa entrega) se emiten hasta 2 `service_income`: (a) maquila $2.097/kg y (b) flete planta $37/kg de plomo entregado, `expense_category='Logistica Willard'` para el flete. Ambos con `account_id=NULL` — causación de CxC Willard (§6.1); el cobro llega después como `collection_from_client`.
- **Mensual**: el flete BOG-BAQ ($216/kg de batería trasladada en el mes) se factura a Willard como un `service_income` mensual separado — NO va atado al `Sale.liquidate` de las entregas. **Mecanismo** (endpoint en §12.1): `POST /api/v1/willard/monthly-freight-invoices` con `period=YYYY-MM` — suma los kg físicos de batería de los `Transfer` BOG→CV **confirmados en recepción** durante el periodo, lee la tarifa vigente `flete_willard_bog_baq` y emite el `service_income` mensual (`account_id=NULL`, CxC Willard, §6.1). Anulable con cascade ([decision #48]) y re-generable; idempotente por periodo (un segundo POST del mismo periodo falla con 409 salvo que el anterior esté anulado).

**El transporte físico BOG-BAQ es tercerizado** (cerrado en visita 2026-07-02): son DOS conceptos distintos — el ingreso $216/kg que SAC factura a Willard, y el **gasto variable** del transportador tercero, que se causa **cuando factura la transportadora** (ver "Fletes internos SAC" abajo). La diferencia entre ambos es el margen de logística de ese tramo.

### Fletes internos SAC (GASTO)

Costos reales de operación de mover material entre sedes propias. Estos son gastos operativos regulares — no facturables a nadie. Dos casos, cerrados en la visita 2026-07-02:

- **Tramo BOG→BAQ (tercerizado)**: el transporte físico lo hace una transportadora externa. Gasto **variable** que se causa **cuando factura la transportadora**: `MoneyMovement(type='expense' o 'expense_accrual', third_party_id=<transportadora>, business_unit_id=<UN según carga>, warehouse_id=<sede que asume el costo>, expense_category='Logistica Interna BOG-BAQ')`. No confundir con el ingreso $216/kg que SAC factura mensualmente a Willard por ese mismo tramo — son dos conceptos distintos.
- **Tramo CV→JM (carros propios)**: **no hay flete en este tramo** (cerrado en visita 2026-07-02 — cierra el [PENDING] de v0.4). Los costos reales del tramo (combustible, mantenimiento, conductor) se registran como gastos operativos normales con auxiliar por vehículo (§9.3); la maquila intersede $1.500/kg es solo procesamiento.

Categorías seed: `Logistica Interna BOG-BAQ`, `Logistica Interna CV-JM` (esta última para gastos operativos del tramo propio, no un flete). Se pueden refinar con auxiliares por vehículo (ver §9.3) — ejemplo: `Categoria='Combustible' / Subcategoria='Vehículos' / Auxiliar='Camión-1'`.

## 6.3 `ServiceTariff`: tabla maestra de tarifas (alineada decisión #35) [NUEVO]

`ServiceTariff` es el maestro de tarifas de servicios (maquilas + fletes) — patrón append-only puro sin `valid_from`/`valid_to`, análogo estructural a `PriceList` ([REUTILIZADO #35]). La tarifa vigente hoy es el registro con `MAX(created_at)` por `tariff_code`. Cambios (renegociaciones IPC) se materializan como nuevos inserts; los registros antiguos no se editan ni desactivan.

### Modelo

| Columna | Tipo | Nullable | Descripción |
|---------|------|----------|-------------|
| `id` | UUID (GUID) | NO | PK |
| `organization_id` | UUID (GUID) | NO | FK `organizations.id` |
| `tariff_code` | ENUM | NO | `maquila_willard \| maquila_intersede_cv_jm \| maquila_crisol \| flete_willard_bog_baq \| flete_willard_planta_planta` |
| `unit_price_cop` | NUMERIC(14,2) | NO | Precio unitario en COP |
| `unit` | ENUM | NO | `per_kg_lead \| per_kg_battery \| per_unit` |
| `notes` | TEXT | SÍ | Contexto de la renegociación |
| `created_by` | UUID (GUID) | NO | FK `users.id` |
| `created_at`, `updated_at` | TIMESTAMPTZ | NO | `TimestampMixin` |

Invariantes:

- Append-only: no hay UPDATE ni DELETE. Nueva tarifa = nuevo INSERT.
- `unit_price_cop > 0`.
- Uso: toda causación (maquila intersede, crisol, maquila Willard, fletes) lee la tarifa **vigente al momento del evento** y persiste el monto calculado en el `MoneyMovement` (con `tariff_id` como referencia de trazabilidad). Como la causación es inmediata (§5, §6.1), no se necesitan snapshots en tablas intermedias.

### Endpoint tarifas vigentes

`GET /api/v1/service-tariffs/current` — retorna todas las tarifas con `MAX(created_at)` por `tariff_code` (patrón idéntico al `PriceList` current query). Ejemplo respuesta:

```json
[
  {"tariff_code": "maquila_willard", "unit_price_cop": 2097.00, "unit": "per_kg_lead", "created_at": "2026-01-15T..."},
  {"tariff_code": "maquila_intersede_cv_jm", "unit_price_cop": 1500.00, "unit": "per_kg_lead", "created_at": "2026-01-15T..."},
  {"tariff_code": "maquila_crisol", "unit_price_cop": 300.00, "unit": "per_kg_lead", "created_at": "2026-01-15T..."},
  {"tariff_code": "flete_willard_bog_baq", "unit_price_cop": 216.00, "unit": "per_kg_battery", "created_at": "2026-01-15T..."},
  {"tariff_code": "flete_willard_planta_planta", "unit_price_cop": 37.00, "unit": "per_kg_lead", "created_at": "2026-07-02T..."}
]
```

### Tarifa vigente al momento del evento (sin snapshot intermedio)

En v0.5 todos los usos de tarifa siguen un único mecanismo: **causación inmediata con la tarifa vigente al momento del evento**.

1. **Maquila intersede y crisol** (§5): al confirmar el traslado (momento 1) o al cerrar la refinación (momento 2), se lee la tarifa vigente (`maquila_intersede_cv_jm`, `maquila_crisol`) y el par de MMs internos persiste el monto calculado. No hay compromiso pendiente que sobreviva un cambio de tarifa — el snapshot en tabla intermedia del v0.4 quedó obsoleto con el modelo de causación al envío.

2. **Entrega a Willard**: al liquidar la venta de cada entrega, se leen las tarifas vigentes `maquila_willard` y `flete_willard_planta_planta` y se aplican. El `service_income` guarda el monto ya calculado. El flete mensual BOG-BAQ usa la tarifa vigente al facturar el mes.

### Consideración operativa: no retroactivo

Cambiar la tarifa Willard en enero 2027 (IPC) no afecta ventas ya facturadas ni pares de maquila interna ya emitidos. Solo aplica a operaciones posteriores. Esto respeta el principio del snapshot inmutable y evita revalorizaciones históricas indeseadas.

## 6.4 Tabla de factores Willard (`MaterialConversionFormula`) [NUEVO]

Los factores de conversión kg-input a kg-plomo son otro maestro append-only, esta vez asociado al `Material`. Cada referencia Willard (07, 08, 1, 2, 3, 4, 5) más los materiales especiales (jamiche, SEC ESCURRIDO, SEC PINZA, scrap-con-borne) tiene su fórmula vigente. **Qué cuenta kg alimenta cada grupo**: las referencias de batería (07, 08, 1–5, `formula_type='battery_to_lead'`) acreditan la cuenta **Willard Baterías**; los materiales especiales (jamiche, SEC, scrap-con-borne — `drosses_to_lead`/`scrap_with_terminal_to_lead`) son drosses/materiales y acreditan la cuenta **Willard Drosses**, que además siempre ingresa por Juan Mina (§4.1). El caso más interesante es SEC ESCURRIDO vs SEC PINZA: mismo material físico en SAC, dos factores distintos según cómo lo reporta Willard.

### Modelo

| Columna | Tipo | Nullable | Descripción |
|---------|------|----------|-------------|
| `id` | UUID (GUID) | NO | PK |
| `organization_id` | UUID (GUID) | NO | FK `organizations.id` |
| `material_id` | UUID (GUID) | NO | FK `materials.id` |
| `formula_type` | ENUM | NO | `battery_to_lead \| drosses_to_lead \| scrap_with_terminal_to_lead \| custom` |
| `parameters` | JSONB | NO | Ver Anexo D para schema por `formula_type` |
| `willard_account_subtype` | ENUM | SÍ | `escurrido \| pinza \| NULL`. Permite dos fórmulas para el mismo material_id según reporte Willard |
| `notes` | TEXT | SÍ | Contexto |
| `created_by` | UUID (GUID) | NO | FK `users.id` |
| `created_at`, `updated_at` | TIMESTAMPTZ | NO | `TimestampMixin` |

Invariantes:

- Append-only ([REUTILIZADO #35]).
- Vigente = `MAX(created_at)` por `(material_id, willard_account_subtype)`.
- Si `willard_account_subtype IS NOT NULL`, el material está sujeto a diferenciación Willard al recibirse (ver mecanismo abajo).

Ejemplos de `parameters` por `formula_type`:

- `battery_to_lead`: `{"kg_lead_per_unit": 2.5}` — para batería ref 07.
- `drosses_to_lead`: `{"lead_percentage": 0.53}` — para jamiche.
- `scrap_with_terminal_to_lead`: `{"scrap_factor": 0.6, "terminal_weight": 0.05}` — factor compuesto scrap+borne. [CONFIG-ARRANQUE: valores exactos con Erwin] ver Anexo D.

### Caso especial: SEC ESCURRIDO vs SEC PINZA (2 cuentas Willard, mismo material SAC)

Willard renegoció en algún momento su porcentaje de reporte del SEC (material seco escurrido) y quedaron dos cuentas activas: SEC ESCURRIDO (factor 0.56) y SEC PINZA (factor 0.59). Para SAC internamente es el **mismo material físico** con un solo `current_average_cost` ([REUTILIZADO #5] costo promedio global preservado). Modelo:

- 2 registros de `MaterialConversionFormula` para el mismo `material_id`:
  - `(material=SEC, willard_account_subtype='escurrido', parameters={lead_percentage:0.56})`.
  - `(material=SEC, willard_account_subtype='pinza', parameters={lead_percentage:0.59})`.
- En `InboundOrder` de postconsumo Willard, si el material es SEC, se **requiere** el campo `willard_account_subtype` para saber qué factor aplicar. Sin ese campo, la creación falla con 422.
- El operador (David al digitar, según review #2) elige `escurrido` o `pinza` mirando la remisión Willard. La `KgLedgerMovement` resultante queda con `conversion_formula_snapshot.willard_account_subtype='pinza'` (o `escurrido`) para trazabilidad.

Ejemplo numérico: llegan 1.000 kg de SEC. Si Willard lo reporta como PINZA (0.59): deuda +590 kg en **Willard Drosses**. Si Willard lo reporta como ESCURRIDO (0.56): deuda +560 kg, también en Willard Drosses (el SEC es material tipo drosses — el subtipo escurrido/pinza discrimina la FÓRMULA, nunca la cuenta). Inventario SAC entra igual en ambos casos (1.000 kg del material SEC con su costo promedio); lo que cambia es el kg equivalente contractual que se debe.

### Endpoint factores vigentes

`GET /api/v1/material-conversion-formulas/current` — retorna todos los factores con `MAX(created_at)` por `(material_id, willard_account_subtype)`. Frontend usa este endpoint para poblar los cálculos al momento de crear `InboundOrder` postconsumo.

## 6.5 Centros distribución Willard (informativos) [NUEVO]

Willard opera con centros de distribución regional (Barranquilla, Bogotá, Monteria, Santa Marta, Motocosta, y posiblemente Pereira y Medellín — [CONFIG-ARRANQUE: lista exacta]). Estos centros son puntos donde Willard entrega material desde sus zonas de recolección, pero SAC físicamente solo recibe en tres puntos: Circunvalar (CV) o Bogotá (BOG) para baterías, y Juan Mina (JM) para drosses. Los centros son dimensión informativa, no operativa para SAC.

Hugo lo explicó textualmente en la reunion noche 2026-06-26: *"todo lo que está así en la costa, yo no recojo nada, todo me lo entregan en mi bodega... para nosotros no, solo que ellos sí si quieren saber de dónde fueron las unidades"*.

### Modelo

Se agrega un campo opcional a `InboundOrder`:

- `willard_distribution_center`: ENUM nullable — solo poblado para `InboundOrder` de postconsumo Willard. Valores: `baq | bog | monteria | santa_marta | motocosta | pereira | medellin`. [CONFIG-ARRANQUE: lista final — dato informativo, extensible sin migración].

### Uso operativo

- **Para SAC**: no afecta el saldo `KgLedger` (que es único por cuenta Willard Baterías o Drosses, no por centro).
- **Para Willard**: rastrea el origen operativo — permite a Willard pagar al chatarrero de origen o auditar su cadena de suministro. SAC lo reporta como cortesía.
- **Para reportes**: la conciliación semanal Willard (§4.5) puede desglosar informativamente por `willard_distribution_center` para facilitar el cruce con la contabilidad de Willard. Cero impacto contable en SAC.

### No confundir con `warehouse_id` SAC

Los centros Willard **no son** `warehouse` de SAC. `warehouse_id` en `InboundOrder` sigue siendo CV, BOG o JM (donde SAC físicamente recibe el material). `willard_distribution_center` es un metadato adicional. La distinción es limpia: un `InboundOrder` puede tener `warehouse_id=CV` (SAC recibe en Circunvalar) + `willard_distribution_center=motocosta` (Willard reporta que la unidad viene de Motocosta).

Consecuencia: los saldos deuda Willard por sede/centro son consultas informativas sobre los movimientos, no cuentas separadas. Un solo `KgLedgerAccount(account_type='willard_baterias')` con desglose informativo por `conversion_formula_snapshot.material_reference` y por `InboundOrder.willard_distribution_center` cubre las necesidades de conciliación.

# 7. Inventario y transformaciones internas

Este capítulo cubre el corazón operativo de SAC: cómo entra el material, cómo se liquida, cómo se traslada entre sedes y cómo se transforma físicamente. El principio rector — que se repite en cada sub-sección — es que **la sede es una dimensión física de dónde está el material, no una fragmentación del catálogo**. Un mismo material tiene un único código, un único costo promedio global y una única identidad de negocio; lo que cambia entre CV, JM y BOG es dónde está físicamente y cuánto hay allí. Este principio preserva la invariante de costo promedio móvil establecida como decisión #5 y garantiza que los tres clientes existentes (Costa, Biogreen, MetaRecycling) no se vean afectados por las extensiones que introduce SAC.

## 7.1 Inventario multi-sede unificado [REUTILIZADO #5]

SAC opera con tres sedes físicas — Circunvalar (CV), Juan Mina (JM) y Bogotá (BOG) — más tres bodegas virtuales (`CV-MOLINO` para material en trituración, `JM-TRANSITO` para material en camino hacia JM, `CV-TRANSITO` para baterías en camino BOG→CV). El modelo NO fragmenta el catálogo de materiales por sede: cada material vive como un solo registro `Material` con un único `code` (por ejemplo `BAT-07`), un único `default_unit`, un único `current_average_cost` calculado a nivel organización (ORG-WIDE), y una única `business_unit_id` que lo asocia a su unidad de negocio (UN).

Lo que sí es multi-sede es el **stock físico**: cada `InventoryMovement` persiste `warehouse_id`, y el stock por sede se calcula on-the-fly mediante `SUM(inventory_movements.quantity) GROUP BY warehouse_id` (patrón ya establecido en EcoBalance, ver §7 del CLAUDE.md — Per-warehouse stock). El stock total del material es la suma de sus warehouses.

| Concepto | Ámbito | Cálculo |
|---|---|---|
| `Material.code` | ORG-WIDE | Único cross-sede — `BAT-07` es el mismo material en CV, JM y BOG |
| `Material.current_average_cost` | ORG-WIDE | Recalculado en liquidación de compras (decisión #5), no por sede |
| `Material.business_unit_id` | ORG-WIDE | UN dueña del material (`Reciclaje Plomo`, `Maquila Willard`, `Proyectos Especiales`) |
| Stock por sede | Por `warehouse_id` | `SUM(InventoryMovement.quantity) WHERE material_id=X AND warehouse_id=Y` |
| Stock total | ORG-WIDE | `SUM(stock_por_sede)` sobre los 3 warehouses + bodegas virtuales |
| `current_stock_transit` vs `current_stock_liquidated` | ORG-WIDE | Separación establecida en decisión #3, aplica a todas las sedes |

Las **bodegas virtuales** cumplen dos funciones que preservan la trazabilidad sin inflar el modelo:

- `JM-TRANSITO` (por sede): al hacer un traslado CV→JM (ver §7.5), el material sale de `CV` y entra a `JM-TRANSITO`. La compañera de despachos en CV genera la remisión; el material permanece en `JM-TRANSITO` hasta que Henry o el operador de JM confirma recepción, momento en el que se mueve a `JM`. Esto refleja la realidad operativa — camión en ruta — sin duplicar inventario.
- `CV-MOLINO`: área operativa dentro de CV para material en trituración. NO es un tercero (contrario a lo que sugería el v0.3), NO es una unidad de negocio y NO es un proyecto — es una bodega física dentro de CV donde el material espera ser procesado. La transformación baterías → fragmentos (ver §7.4) se registra saliendo de `CV-STOCK` y entrando a `CV-MOLINO`, y luego de `CV-MOLINO` a `CV-STOCK` como scrap.

Se preserva la política de **stock negativo permitido con warnings** (patrón establecido de EcoBalance): en ventas, ajustes y transformaciones, si la cantidad excede el stock disponible, la operación no se bloquea pero retorna `warnings[]`. Esto es especialmente relevante para SAC donde la digitación puede llegar con retraso respecto al movimiento físico real.

Ejemplo numérico. Al corte de migración, el material `BAT-08` tiene:

- Stock CV: 1.200 unidades
- Stock JM: 0 (no se guarda en JM antes de procesar)
- Stock BOG: 850 unidades
- Stock JM-TRANSITO: 400 unidades (camión en ruta CV→JM enviado ayer)
- `current_average_cost` (ORG-WIDE): $8.500/unidad

Todos comparten el mismo costo. Si mañana se registra una compra en BOG a $9.000/unidad × 500 unidades, el `current_average_cost` se recalcula al liquidar (Johana, manualmente — ver §7.2) usando el promedio ponderado sobre el total ORG (2.450 + 500 unidades), NO sobre BOG aislado. Fragmentar el costo por sede rompería esta invariante y contradiría el modelo de las cuatro organizaciones existentes.

## 7.2 Compras y liquidación MANUAL (chatarra propia) [REUTILIZADO #3, MODIFICADO]

La compra de chatarra propia (`UN1 Reciclaje Plomo`) reusa íntegramente el workflow de tres pasos de EcoBalance — `register → liquidate → pay` (decisión #3) — con una **corrección crítica respecto al v0.3**: la liquidación es **manual, entrada por entrada, hecha por Johana**. El sistema NO auto-liquida en SAC, y esto es una diferencia deliberada de configuración operacional respecto a los otros tres clientes.

Johana (reunion mañana 2026-06-26): "me tocaría a mi hacerla" — refiriéndose a la liquidación. El proceso real que se digitaliza es:

1. **David** (o el operador de recepción en la sede correspondiente) captura la entrada al momento del pesaje: peso + referencia tentativa + tercero proveedor. Se crea `Purchase` en estado `registered` con `warehouse_id = sede de recepción` y `auto_liquidate = false`. El stock entra a `current_stock_transit`, sin efecto financiero.
2. **Erwin** (P38 — gestor de compras chatarra) hace la auditoría física del inventario en CV: valida pesos, ajusta referencias si el material vino desagregado, deja notas de calidad.
3. **Johana** liquida entrada por entrada: asigna precio unitario definitivo por línea, ajusta referencias si Erwin marcó cambios, aplica retenciones (ICA, ReteFte), y confirma. La liquidación dispara el recálculo de costo promedio (decisión #5), transit → liquidated, y actualiza balance del proveedor.
4. **Pago**: siempre es un `MoneyMovement` separado (decisión #3). Puede ser inmediato al liquidar (`auto_pay = true`, decisión #20) o diferido.

El campo `warehouse_id` en el header de la compra es la sede donde se recibe físicamente. Es **inmutable post-registro**: cambiar la sede de recepción una vez la compra está registrada requiere anular la operación y crear una nueva. Esta regla se justifica porque el stock ya se movió a un warehouse específico y cambiarlo sin trazabilidad rompería el histórico de movimientos.

### Baterías húmedas y multi-referencia (no rompen decisión #5)

Un caso frecuente en SAC: llega un camión con 1.000 kg de "batería húmeda mixta" que en realidad es una mezcla de referencias 07, 08 y 1. Este NO se modela como un material genérico "batería húmeda" con costo propio (eso rompería la invariante ORG-WIDE de `current_average_cost` cada vez que la mezcla llega en proporciones distintas). Se modela como **N líneas de `Purchase`**, una por referencia detectada, con el costo unitario correspondiente a esa referencia al momento:

**Purchase X — CV — Proveedor Y:**

| Línea | Material | Cantidad | Precio unitario |
|---|---|---|---|
| 1 | BAT-07 | 400 unidades | $8.500 |
| 2 | BAT-08 | 350 unidades | $9.200 |
| 3 | BAT-01 | 250 unidades | $7.800 |

La división por referencia la hacen Erwin (visual) y Johana (a partir del pesaje detallado que Erwin registra). **Liquidación por peso — P2 CERRADA en visita 2026-07-02**: la composición se conoce AL RECIBIR, y el valor pagado se reparte entre las referencias según su **costo promedio histórico**. Cita de Hugo: *"Esa es la regla."* La liquidación es manual de Johana (no automática); el sistema asiste el split sugiriendo el reparto por costo promedio histórico de cada referencia, y Johana confirma. Este mecanismo se documenta como el flujo canónico de captura, no como transformación posterior.

Consecuencia: cada `Material` mantiene su `current_average_cost` ORG-WIDE inalterable en su semántica (decisión #5 preservada). La complejidad de la mezcla física se resuelve en la digitación, no en el modelo.

### Inventario en unidades (no en peso)

Confirmación de Daniel (sesion 2026-06-30): el inventario final se lleva en unidades, no en peso, para las referencias de batería. Esto simplifica el conteo físico y coincide con cómo Willard factura por unidad de referencia. El peso solo aparece como cantidad al recibir postconsumo y drosses, donde no hay unidad natural (kg de drosses). El modelo actual (`Material.default_unit` con decisión #54 unit-aware) ya soporta ambos: baterías en `unidad`, drosses en `kg`, sin fragmentar el catálogo.

### Volumen y retenciones

Volumen esperado: 10-20 entradas diarias entre las tres sedes (Erwin 2026-06-26). Retenciones aplicables al liquidar: ICA y ReteFte según tipo de proveedor. La tabla exacta de tasas es [CONFIG-ARRANQUE: se recoge con Johana al arranque] — la estructura queda preparada desde Fase 1.

## 7.3 Recolecciones postconsumo + rutas multi-proveedor (Green Loop como gestor) [MODIFICADO en v0.6]

El postconsumo Willard llega a SAC de dos formas distintas, y ambas requieren un manejo diferenciado al de la chatarra propia:

- **Baterías postconsumo**: unidades de batería descargada. Cada unidad tiene una referencia Willard (07, 08, 1, 2, 3, 4, 5) y un factor `kg_lead_per_unit` snapshot en `MaterialConversionFormula` (ver §6.4). Al recibirse, se acredita `KgLedgerAccount(willard_baterias)` por unidades × factor.
- **Drosses postconsumo**: material a granel en kg (jamiche, SEC ESCURRIDO, SEC PINZA). Al recibirse, se acredita `KgLedgerAccount(willard_drosses)` por kg × lead_percentage.

Estos flujos son cuentas separadas por regla explícita de Johana (reunion mañana 2026-06-26): "no pueden ir mezclados". El detalle del asiento en `KgLedger` está en §4.3.

### Un proveedor por LÍNEA (revisado en v0.6)

**Historia de la regla.** El modelo original generaba UNA entrada global por ruta. Se corrigió en v0.4 según Hugo (reunion noche 2026-06-26): *"Tendrá que ser que nosotros en la entrada no hagamos una sola, sino que hagamos cada entrada por cada proveedor"* y Johana: *"la idea seria que hagan una entrada por proveedor y no una global"*. Las dos razones que sustentaban esa corrección fueron: (a) poder liquidar precios individualmente por proveedor según lo negociado, y (b) mantener trazabilidad de origen para el saldo Willard por centro de distribución (ver §6.5).

**Qué cambia en v0.6 y qué NO.** En la reunión del 2026-08-03, ya con el formulario a la vista, Johana levantó la fricción operativa: una ruta puede traer material de 10 a 15 proveedores y llega como **una sola descarga física** (*"cuando ellos llegan acá y se les descarga, se les hace una sola entrada… ajá, es que ahí es donde está el tema"*), con frecuencia **diaria**. Digitar 15 documentos de captura para un hecho físico único es fricción sin contrapartida.

La regla se **relaja únicamente en compra regular de chatarra** y **se conserva intacta donde vive su razón**:

| Flujo | Modelo en v0.6 |
|---|---|
| **Compra regular** (`inbound_type='purchase'`) | Una `InboundOrder` puede tener **varios proveedores, uno por línea de material**. De ella derivan **N `Purchase`**, una por proveedor, cada una con su remisión, su liquidación, sus retenciones y su saldo. |
| **Postconsumo Willard** (`inbound_type='willard'`) | **Sin cambios: un solo tercero por entrada.** No es una restricción nueva — desde [decisión #80] el tercero de una entrada Willard se **deriva del titular de la cuenta de kg** (amarrado por CHECK en la base de datos, con defensa 422 en el backend y el campo deshabilitado en la interfaz). Una entrada Willard multi-proveedor es imposible por construcción. Confirmado por Daniel el 2026-08-04: **el material Willard tiene un solo proveedor, que es Willard**. |

Las dos razones de v0.4 sobreviven: **(a)** cada proveedor conserva su propia `Purchase` y se liquida por separado, en el momento que decida quien liquida —incluso de forma gradual, dejando proveedores pendientes— y **(b)** es explícitamente sobre el saldo Willard, donde el modelo de v0.4 queda literalmente intacto. Lo único que cambia es cuántos documentos de captura se digitan para una misma realidad física.

⚠️ La mención *"su factor Willard si aplica"* que traía la redacción anterior de este párrafo es **legado previo a la decisión #80** y ya no describe el sistema: en una ruta multi-proveedor no hay material Willard.

Ver el plan de implementación: `docs/planes/plan-sac-multiproveedor-por-linea.md`.

### Rol de Green Loop y flujo completo [CERRADO en visita 2026-07-02]

Green Loop es un **gestor logístico externo**, no un comercial. Se modela como `ThirdParty` con `behavior_type = service_provider`. El modelo quedó cerrado en la visita a planta del 2026-07-02:

1. **Caja provista por SAC**: Green Loop opera con una `MoneyAccount` tipo caja (como una caja menor, con `warehouse_id` si aplica). SAC le consigna fondos según necesidad (transfer entre cuentas propias).
2. Green Loop hace la ruta y **compra EN RUTA a proveedores de SAC**, pagando desde esa caja.
3. Las compras quedan registradas **al proveedor real** (no a Green Loop): N `InboundOrder`/`Purchase`, uno por proveedor visitado, con el `ThirdParty` proveedor específico. El pago de cada compra sale de la caja Green Loop.
4. Green Loop **pasa las cuentas** de lo pagado y se le descarga la caja (rendición contra los pagos registrados; diferencias van al panel de excepciones §10.3).
5. **Comisión Green Loop: $100/kg recolectado** (valor sugerido y parametrizable). Se liquida por **consignación aparte** (no se descuenta de la caja de compras) y se registra como **GASTO CAUSADO** al liquidar la compra: un `expense_accrual` (sin cuenta, contra el saldo del recolector) en la categoría de sistema "Comisiones de recolección", que es **indirecta** — no entra al costo del material. El pago es un `payment_to_supplier` separado contra esa consignación.

   > **Corregido en v0.6.** Hasta v0.5 este punto decía que la comisión se **prorrateaba al costo del material** vía `PurchaseCommission` ([decisión #30]). Eso dejó de ser cierto con la **[decisión #83]** (Ciclo D, desplegada 2026-08-04), por decisión de producto explícita de Daniel: la comisión del recolector es un gasto, no un mayor costo del inventario. El mismo error estaba repetido en la tabla de actores de §2.4, también corregido.
   >
   > Consecuencia práctica: el costo promedio móvil del material **no cambia** por la comisión, y el gasto aparece en el Estado de Resultados por su categoría en vez de diluirse en el COGS.

En Fase 2 se espera que la captura sea directa en móvil por el conductor de Green Loop (Hugo: "Les ponemos el conductor virtual de una vez"). En Fase 1 la captura es desktop, hecha por David o Johana tras descargar el camión.

### Drosses directo BOG → JM

Los drosses Willard van directamente de BOG a JM sin pasar por CV (Hugo reunion noche 2026-06-26). Para trazar esta ruta física distinta, `InboundOrder` acepta un campo `goes_directly_to_jm: bool` (ver §11.2). Cuando es `true`, el `InventoryMovement` se registra en el warehouse `JM` directamente, y el `KgLedgerMovement` acredita `willard_drosses` con la misma semántica pero sin tránsito CV intermedio.

## 7.4 Transformaciones internas (molino y picado en CV, fundición y crisol en JM) [REUTILIZADO #17, #53]

Las transformaciones internas — molino y picado manual en CV, fundición horno grande y refinación crisol en JM — reusan íntegramente el modelo `MaterialTransformation` (decisiones #17 y #53) que ya soporta cambio de composición y cambio de unidad. La única adición son dos eventos nuevos, `FurnaceCharge` y `CrucibleCharge`, que NO cambian composición pero SÍ mueven `KgLedger` (ver §4.3). Estos eventos son distintos de `MaterialTransformation`: la transformación modela cambio físico del material (batería → plomo + residuo), mientras que la carga a horno/crisol modela un traslado interno a un contenedor de proceso donde el material queda en cola para ser fundido/refinado.

### Molino y picado (CV)

- **Molino**: baterías completas ingresan a `CV-MOLINO` (bodega virtual dentro de CV) y salen como fragmentos + acido drenado. Modelado como `MaterialTransformation` con origen `BAT-XX` (unidad) y destinos `SCRAP-XX` (kg) + `ACIDO` (kg). Como cambia la unidad (unidad → kg), aplica decisión #53: la validación `sum(destinos) + merma == origen` NO se ejecuta (no hay invariante de masa cross-unit), y la merma debe ser 0 en la transformación (los residuos se modelan como material destino, no como merma).
- **Picado manual**: los fragmentos de molino se separan manualmente en scrap-con-borne y otros componentes. Modelado como `MaterialTransformation` mismo-unidad (kg → kg), con validación de balance activa (`sum(destinos) + merma == origen`).

### Fundición horno grande (JM)

El evento `FurnaceCharge` (nuevo) mueve `KgLedger(intra_horno) += kg` cuando se carga aportante al horno. NO cambia composición del inventario, NO crea `MaterialTransformation`. El material sigue siendo el mismo aportante pero está físicamente en el horno.

El evento `FurnaceDischarge` — en Fase 2 será un evento 1:1 con la colada específica (entidad negocio `FurnaceBatch`, concepto de trazabilidad `BatchTracking`), pero en Fase 1 es un **descargo agregado periódico** (diario o por lote de fundición aggregate). Esto alinea con la propuesta cliente §2.3 "descargo agregado Fase 1". El descargo hace:

- `KgLedger(intra_horno) -= kg_aportante_consumido` (basado en proporciones promedio del período)
- `InventoryMovement out` del aportante consumido
- `InventoryMovement in` de plomo crudo producido, con `unit_cost` calculado por promedio ponderado del aportante

En Fase 1 la trazabilidad NO es 1:1 colada→aportantes (Fase 2 lo agregará). Fase 1 descarga en lote, refleja el promedio del período. Esto es una decisión consciente de scope y alinea con la promesa contractual al cliente.

### Crisol (JM)

`CrucibleCharge` mueve `KgLedger(crisol) += kg` cuando plomo crudo entra al crisol para refinación (el crisol solo recibe plomo crudo del horno — el retal NO es entrada del crisol). `CrucibleDischarge` descarga:

- `KgLedger(crisol) -= kg_crudo_consumido`
- `InventoryMovement out` del crudo
- `InventoryMovement in` del plomo refinado (puro)
- **Par de maquila interna del crisol**: `internal_maquila_expense` (CV) + `internal_maquila_income` (JM) por `kg de plomo puro producido × $300` (§5.1 momento 2)

El Crisol quedó **confirmado como cuenta separada** del horno grande en la visita a planta del 2026-07-02 — razón del cliente: medir la eficiencia de cada etapa (ver §4.1).

### Fórmulas y métodos de costo

- Fórmula única de conversión scrap → plomo para todas las sedes (Hugo reunion noche 2026-06-26: "misma fórmula scrap-plomo en todas las sedes"). Vive en `MaterialConversionFormula` (ver §6.4), una sola vigente por material + `willard_account_subtype`.
- Métodos de costo en `MaterialTransformation` (decisión #17): `average_cost` (default), `proportional_weight`, `manual`. Los tres funcionan cross-unit desde decisión #53.
- Conversión scrap-con-borne: `kg_plomo = (kg_scrap × scrap_factor) + kg_bornes`. Los bornes son terminales de la batería, >90% plomo puro, se pesan aparte del scrap general. Ver Anexo D para el JSON schema y ejemplo numérico exacto.

### Trazabilidad diferida a Fase 2

Fase 1 opera con descargo aggregate; Fase 2 introducirá el concepto `BatchTracking` (trazabilidad genérica) materializado en una tabla nueva `FurnaceBatch` (entidad de negocio: la colada individual) que permitirá vincular una colada específica a los aportantes que consumió y al plomo crudo que produjo. La arquitectura de `MaterialTransformation` + eventos `FurnaceCharge/Discharge` NO impide agregar esto después: se añadirá una FK opcional `batch_id` en los eventos apuntando a `FurnaceBatch`. Esto se documenta como riesgo controlado, no como bloqueante Fase 1.

## 7.5 Traslados intersede (Transfer + KgLedgerMovement + par de maquila interna) [NUEVO]

Un traslado CV→JM (o BOG→JM) es un evento **compuesto en dos pasos sobre un único `Transfer`** (extensión del `transfer_between_warehouses` existente), que registra **cantidad despachada Y cantidad recibida** (§5.1):

**Paso A — Despacho** (`POST /api/v1/transfers`). Dos `InventoryMovement`:

- `out` desde la sede origen (CV o BOG) con `quantity = -kg_despachado`, `unit_cost = current_average_cost` (ORG-WIDE snapshot). Campo técnico: `warehouse_id` de origen.
- `in` a la bodega virtual de tránsito (`JM-TRANSITO`) con `quantity = +kg_despachado`, mismo `unit_cost`.

**El despacho no tiene efectos en KgLedger ni en pesos** — el material queda en tránsito. Un despacho sin recepción confirmada al cierre del día aparece en el panel de excepciones (§10.3).

**Paso B — Recepción confirmada** (`POST /api/v1/transfers/{id}/receive`). El operador JM (o la compañera de despachos CV) registra la **cantidad recibida** — la fuente de verdad (visita 2026-07-02). **Regla de tolerancia**: dentro del **3–5% configurable**, el ajuste es automático tomando lo recibido como verdad (el delta se ajusta contra la bodega de tránsito con bitácora); por encima, se genera la excepción/alarma en el panel (§10.3) y los efectos 2 y 3 quedan **retenidos** hasta justificar/corregir/arquear. Dentro de tolerancia, en **una sola transacción atómica** se emiten los tres efectos:

- **Efecto 1 — Inventario físico**: `InventoryMovement out JM-TRANSITO` + `in JM-STOCK` por la cantidad recibida.
- **Efecto 2 — Cuenta en kg intersede**: `KgLedgerMovement` con `account_type = intersede`, `delta_kg = +kg_plomo_equivalente` calculado como `kg_recibidos × MaterialConversionFormula.parameters.scrap_factor` (fórmula vigente, snapshot en `conversion_formula_snapshot`). El signo positivo refleja que JM ahora debe X kg de plomo equivalente a CV. La descarga ocurrirá cuando salga el plomo procesado desde JM (`intersede_discharge`, ver §7.6).
- **Efecto 3 — Par de maquila interna** (§5): `internal_maquila_expense` (`warehouse_id = CV` o BOG, `account_id=NULL`, `third_party_id=NULL`, `business_unit_id` heredada del material, `amount = kg_plomo_equivalente_recibido × tarifa vigente` `maquila_intersede_cv_jm` $1.500/kg, categoría "Maquila Intersede") + `internal_maquila_income` (ídem con `warehouse_id = JM`); enlazados vía `linked_movement_id`.

La atomicidad aplica al paso B: si algún efecto falla (no hay `MaterialConversionFormula` vigente para el material, no hay `ServiceTariff` vigente), la recepción se revierte completa. La UI presenta el flujo como un wizard "Transferencia Intersede" en dos pantallas (despachar / recibir) que oculta la complejidad de los tres modelos. Lectura de negocio: la causación sigue siendo "al envío" — el evento causante es el traslado; el ancla técnica en la recepción garantiza que el monto nazca sobre los kg recibidos (§5.1).

### Anulación

Anular un traslado revierte los tres efectos:

- `InventoryMovements` marcados `annulled`.
- `KgLedgerMovement` de intersede pasa a `status = annulled` con `annulled_reason` y bitácora.
- El **par de maquila interna se anula en cascade** (ambos MMs, patrón [decision #48]).

Si el material del traslado ya fue cargado al horno o vendido desde JM, la anulación del transfer se **bloquea** con 400 — primero hay que revertir los eventos posteriores. Esta regla protege la consistencia del KgLedger y de los pares ya causados.

### Ejemplo numérico

CV despacha a JM 1.000 kg de scrap con factor 0.60 (scrap → plomo). Tarifa intersede vigente: $1.500/kg.

- `InventoryMovement out CV-STOCK`: -1.000 kg scrap, unit_cost $4.200.
- `InventoryMovement in JM-TRANSITO`: +1.000 kg scrap, unit_cost $4.200.
- `KgLedgerMovement intersede`: +600 kg plomo equivalente (1.000 × 0.60).
- Par de maquila interna: `internal_maquila_expense` (CV) + `internal_maquila_income` (JM) por $900.000 (600 × $1.500).

La causación en pesos ocurre aquí, en el evento del traslado — emitida al confirmar la recepción del mismo día (§5.1). Cuando JM venda esos 600 kg de plomo solo se descargará la cuenta kg intersede (ver §7.6).

## 7.6 Ventas (Sale workflow + descarga de cuenta intersede) [REUTILIZADO #2, MODIFICADO]

El workflow de ventas reusa el patrón estándar de EcoBalance (decisión #2): dos pasos, `register → liquidate`, con cobro (`MoneyMovement`) siempre como operación separada aunque pueda dispararse atómicamente en la liquidación (decisión #20, `auto_pay`).

El header de `Sale` acepta `warehouse_id` — sede desde donde se despacha físicamente el material. Al igual que en compras, es **inmutable post-registro** (ver §7.2). El detalle de líneas, precios, comisiones y `received_quantity` opera igual que en las cuatro organizaciones existentes.

**Importante (modelo v0.5, visita 2026-07-02): la liquidación de la venta NO causa maquila intersede.** La maquila se causó al confirmar el envío CV→JM ($1.500/kg) y a la salida del crisol ($300/kg) — ver §5. Lo que la venta sí hace en el mundo kg:

### Descarga de la cuenta kg intersede (`intersede_discharge`)

Cuando JM vende/entrega plomo procesado, `Sale.liquidate()` inserta un `KgLedgerMovement(account=Intersede CV↔JM, source_type='intersede_discharge', delta_kg=−kg_salientes)` que descarga los kg pendientes más antiguos de la cuenta. Es un movimiento **solo en kg** — cero efecto en pesos por maquila. Si además la venta es un abono a Willard, se inserta el `willard_delivery` correspondiente (la **remisión** define si descarga baterías o drosses, §4.3).

### Casos que NO mueven la cuenta intersede

- Venta desde JM de material comprado localmente en JM (nunca vino de CV/BOG): no hay descarga intersede. Test bloqueante `test_jm_local_sale_does_not_discharge_intersede`.
- Venta desde CV o BOG: no aplica — la cuenta intersede registra material aportante despachado hacia JM.
- Venta anulada: revierte el `intersede_discharge` (status `annulled`) junto con los demás efectos estándar. Si la venta era un abono a Willard, la anulación revierte **en cascade** el `willard_delivery` y los `service_income` de maquila Willard ($2.097/kg) y flete planta ($37/kg) emitidos al liquidar (§6.1-§6.2) — cada causación tiene su reverso. Test bloqueante: `test_willard_sale_annulment_reverts_service_incomes`. Los pares de maquila interna del envío NO se tocan — corresponden al traslado, no a la venta.

### Merma horno (solo kg)

Si se cargan 600 kg equivalentes y el proceso produce menos (merma), el saldo intersede puede quedar con kg huérfanos que ya no existen físicamente. Se resuelven con `POST /api/v1/kg-ledger/movements` tipo `manual_adjustment` sobre `intersede`, con motivo "Merma horno colada del DD/MM" y permiso `kg_ledger.manage_adjustments` (Johana o admin). El sistema NO ajusta automáticamente para evitar ocultar pérdidas de proceso; el panel de excepciones (§10.3) alerta sobre saldos intersede antiguos sin movimiento. La causación en pesos no se ve afectada — ya ocurrió al envío (§5.4).

### Comisiones a comerciales

No aplica en SAC — los comerciales son nómina fija mensual (ver §8). NO se usa `PurchaseCommission` (decisión #30) ni `commission_accrual` (decisión #23) sobre ventas SAC.

# 8. Comerciales y nómina (NO comisiones por kg)

En SAC los comerciales que gestionan ventas de chatarra y postconsumo reciben **nómina fija mensual**, no comisión variable por kg vendido. Esto fue confirmado por Hugo (reunion noche 2026-06-26) y cierra la pregunta Q10 heredada del v0.3. La implicación arquitectónica es directa: **no se usan `PurchaseCommission` (decisión #30) ni `commission_accrual` (decisión #23) para comerciales internos SAC**. El modelo de comisiones existente en EcoBalance queda disponible pero no se activa en la configuración de SAC.

El pago de nómina comercial se registra como cualquier gasto operativo: `MoneyMovement` de tipo `expense` con:

- `expense_category_id` → categoría `"Nomina Comercial"` (seed system, ver §11.1)
- `business_unit_id` → generalmente `UN1 Reciclaje Plomo` cuando el comercial se dedica a chatarra; puede ser `UN2 Maquila Willard` si es dedicado a postconsumo (los mismos comerciales suelen cubrir ambas, en cuyo caso se modela como Gasto Compartido — Tier 2 de decisión #44)
- `warehouse_id` → sede a la que está adscrito el comercial (CV, JM, BOG o `NULL` si es corporativo). Esta dimension permite reportar costo de nómina comercial por sede
- `third_party_id` → el empleado como `ThirdParty` con `behavior_type = liability` si se lleva causación separada, o directo a caja/banco si es pago simple

Como no se requiere comisión variable por kg, el reporte "Comisiones por comercial y por kg" heredado de otros clientes NO aplica en SAC — el sistema simplemente no muestra la sección en el dashboard de la organización. Esto cierra la pregunta Q13 sin cambios de modelo.

**Excepción Green Loop (gestor externo) — CERRADO en visita 2026-07-02, MODELO CORREGIDO en v0.6**: la comisión a Green Loop es **$100/kg recolectado** (tarifa sugerida y parametrizable). Se registra como **gasto causado** al liquidar la compra: un `expense_accrual` sin cuenta, contra el saldo del recolector, en la categoría de sistema "Comisiones de recolección" (indirecta) — **SÍ va al Estado de Resultados como gasto y NO engorda el costo unitario del material** ([decisión #83], desplegada 2026-08-04). La liquidación a Green Loop se paga por **consignación aparte** (no se descuenta de la caja de ruta).

> ⚠️ Hasta v0.5 este párrafo decía exactamente lo contrario —`PurchaseCommission` con prorrateo al costo, decisión #30— y era el enunciado más detallado del error. La decisión #83 lo invirtió por decisión de producto de Daniel: la comisión del recolector es un gasto operativo, no un mayor costo del inventario. Las compras en ruta se registran al **proveedor real** de cada punto de recolección y se pagan desde la **caja Green Loop provista por SAC** (`MoneyAccount` tipo caja, §7.3), que rinde cuentas contra las compras registradas. La contraparte de la comisión es `ThirdParty(Green Loop)` con `behavior_type = service_provider`. Esto cierra Q-viva.3.

Ejemplo de asiento nómina comercial (CV, dedicado a chatarra propia):

```json
{
  "movement_type": "expense",
  "amount": 3500000,
  "account_id": "<cuenta-CV-caja o banco>",
  "third_party_id": "<empleado-comercial-como-liability>",
  "business_unit_id": "<UN1-Reciclaje-Plomo>",
  "warehouse_id": "<CV>",
  "expense_category_id": "<Nomina Comercial>",
  "description": "Nomina comercial junio 2026 - Jorge Hernandez"
}
```

Comerciales identificables por nombre y estructura organizacional dedicada [CONFIG-ARRANQUE: lista de personas] — Hugo mencionó "estructura de costos comercializadora" (reunion noche 2026-06-26 00:26:01) sin nombrar personas. Al arranque se valida si hay una sub-organización comercial dedicada dentro de SAC o si es nómina genérica repartida entre roles operativos con función comercial ocasional.

# 9. Gastos (3-tier con dimensión `warehouse_id` ortogonal)

Este capítulo cierra la pregunta Q3 (dimensionalidad de gastos) heredada del v0.3. La respuesta arquitectónica es: **reusar íntegramente la lógica 3-tier de gastos de EcoBalance (decisión #44) sin modificaciones, y agregar una nueva dimensión persistida `warehouse_id` en `MoneyMovement` que es ORTOGONAL al 3-tier**. Ortogonal significa que la sede (dónde se generó el gasto físicamente) es independiente de la asignación a unidades de negocio (a qué UN pertenece contablemente). Un mismo gasto puede ser Directo a `UN1` y físicamente ocurrir en CV; otro puede ser Compartido entre `UN1 + UN2` y ocurrir en BOG; otro puede ser General (todas las UN) y no tener sede asignada.

## 9.1 Modelo de gastos heredado (3-tier) [REUTILIZADO #44]

El modelo 3-tier de EcoBalance clasifica cada `MoneyMovement` de tipo gasto según su relación con las unidades de negocio:

| Tier | Nombre | Semántica | Campos |
|---|---|---|---|
| Tier 1 | Directo | Gasto pertenece 100% a una UN específica | `business_unit_id` seteado, `applicable_business_unit_ids` NULL |
| Tier 2 | Compartido | Gasto se reparte entre N UN según proporción definida | `business_unit_id` NULL, `applicable_business_unit_ids` con N UN |
| Tier 3 | General | Gasto se prorratea automáticamente a todas las UN activas | `business_unit_id` NULL, `applicable_business_unit_ids` NULL |

El endpoint `GET /reports/expenses` (decisión #44) acepta `group_by ∈ bu | category | bu_then_category | category_then_bu` y computa el prorrateo 3-tier internamente. Este comportamiento se preserva sin cambios para SAC y para los tres clientes existentes. Ver también decisión #49 que expone drill-down desde P&L al listado de movimientos con filtros precisos.

Aplicado a SAC:

- **Directo**: nómina comercial UN1 (§8), par de maquila interna causado al envío (§5, con `business_unit_id` heredada del material procesado).
- **Compartido**: alquiler de la bodega BOG que se reparte entre `UN1 Reciclaje Plomo` y `UN2 Maquila Willard` porque ambas operan allí; mantenimiento del camión que hace tanto rutas de chatarra como rutas Willard.
- **General**: honorarios contables SAC corporativos, servicios públicos de oficinas administrativas, pólizas.

## 9.2 Nueva dimensión: `warehouse_id` ORTOGONAL en `MoneyMovement` [MODIFICADO]

Se agrega la columna `warehouse_id UUID NULL` a la tabla `money_movements` como **dimensión persistida** (no calculada on-the-fly). Esta decisión fue cerrada por Daniel (sesion 2026-06-30): persistir como columna nullable, backwards-compatible con los tres clientes existentes (Costa, Biogreen, MetaRecycling) — todos sus `MoneyMovement` existentes quedan con `warehouse_id = NULL` sin migración de datos.

### Cambios técnicos

- **Migración Alembic**: `ADD COLUMN warehouse_id UUID NULL` en `money_movements` + índice `ix_money_movements_warehouse_id`.
- **Schema POST /money-movements**: acepta `warehouse_id` opcional. **Regla de herencia**: si la `MoneyAccount` usada tiene `warehouse_id` (caso cajas menores por sede, §9.4), el movimiento **hereda la sede de la CUENTA** — esa es la fuente de verdad. El `default_warehouse_id` del usuario es solo conveniencia de UI (preselección); en cuentas corporativas sin sede, queda NULL.
- **Schema PATCH /money-movements/{id}/classification**: extendido con `warehouse_id` (extensión directa de decisión #39). Permiso `treasury.edit_classification`. No modifica montos, cuentas ni terceros — solo clasificación gerencial.
- **Backwards-compatible**: nullable con default NULL, ningún cliente existente se afecta.

### Ortogonalidad con 3-tier — ejemplos concretos

Las dos dimensiones (Tier 3-tier + Warehouse) operan independientes. Combinaciones válidas:

| Ejemplo | Tier | `business_unit_id` | `warehouse_id` | Interpretación |
|---|---|---|---|---|
| Combustible camión CV asignado a Reciclaje | Directo | UN1 | CV | 100% a UN1, físicamente ocurre en CV |
| Alquiler bodega BOG compartido UN1+UN2 | Compartido | NULL + `applicable=[UN1,UN2]` | BOG | Se reparte entre UN1 y UN2, ocurre en BOG |
| Asesoría contable corporativa | General | NULL | NULL | Prorrateo a todas las UN, sin sede específica |
| Asesoría legal Willard (sin sede) | Directo | UN2 | NULL | 100% a UN2, sin sede específica |
| Honorarios contador BAQ (CV+JM comparten) | Compartido | NULL + `applicable=[UN1,UN2]` | NULL | Se reparte, sin sede específica (aunque asociado a BAQ) |

El prorrateo 3-tier opera **sin considerar `warehouse_id`**. El reporte de gastos puede pivotar por:

- solo UN (comportamiento actual, decisión #44)
- solo Warehouse (nuevo)
- UN × Warehouse cruzado (nuevo)

Filtros nuevos en endpoints:

- `GET /reports/profit-and-loss?warehouse_id=<CV|JM|BOG|NULL>` — P&L filtrado por sede
- `GET /reports/expenses?warehouse_id=<X>` + `group_by ∈ bu | category | warehouse | bu_then_warehouse | ...`
- `GET /reports/cash-flow?warehouse_id=<X>`
- `GET /money-movements?warehouse_id=<X>` (CSV para multi-select)
- `GET /money-movements/third-party/{id}?warehouse_id=<X>` — filtro READ-ONLY, NO afecta el saldo unificado del tercero (decisión #16 preservada — balance del `ThirdParty` sigue siendo único ORG-WIDE)

### Convención de naming de cuentas

Cuentas corporativas sin sede asignada mantienen `warehouse_id = NULL` en sus `MoneyMovement` y se agrupan en el bucket "Corporativo" en reportes por sede. La convención de nombres sugerida es `CV-Caja`, `JM-Banco`, `BOG-Caja`, `Corp-Bancolombia`, pero los filtros del sistema se basan en el `warehouse_id` explícito de cada movimiento, NO en parsing del nombre de la cuenta. Esto evita ambigüedad si un cliente renombra sus cuentas.

### Invariantes preservadas

- `warehouse_id` en `MoneyMovement` es clasificación gerencial, NO contable. NO afecta el balance del tercero ni del `MoneyAccount`.
- Estado de cuenta unificado del tercero (decisión #16, #55) sigue mostrando saldo único ORG-WIDE. Puede filtrarse por sede como vista READ-ONLY, pero el saldo persistido es uno solo.
- Compras y ventas con `warehouse_id` en su header son inmutables post-registro (ver §7.2, §7.6). Los `MoneyMovement` derivados heredan el `warehouse_id` de la operación origen.

## 9.3 Categorías de gasto JERÁRQUICAS con auxiliares por máquina/vehículo [REUTILIZADO #36, PENDING-DESIGN]

Johana requiere ver los gastos con detalle por máquina o por vehículo específico. Reunion mañana 2026-06-26: "hubo mantenimiento de montacargas, filtro, para qué montacargas fue... discriminado por máquina, por vehículo". La estructura actual de `ExpenseCategory` (decisión #36) soporta jerarquía de máximo dos niveles (padre → hija). Para llegar al tercer nivel (auxiliar: montacargas-1, montacargas-2, camión-1) hay dos alternativas de diseño:

### Alternativa A — Tabla nueva `ExpenseAuxiliary`

Se crea una tabla `ExpenseAuxiliary` con `id`, `organization_id`, `expense_category_id` FK (a la subcategoría "hija" del árbol), `code`, `display_name`, `is_active`. Cada máquina o vehículo es una fila. `MoneyMovement` gana una FK opcional `expense_auxiliary_id`. Es aditivo y no toca la jerarquía existente (que sigue max 2 niveles conforme #36).

Pro: no rompe decisión #36. Contra: modelo nuevo, permisos nuevos, UI nueva.

### Alternativa B — Reuso de `business_unit` como sub-dimensión

Modelar cada máquina/vehículo como una `BusinessUnit` técnica (`is_technical = true`, nuevo flag) y setear `applicable_business_unit_ids` para prorratear si el auxiliar aparece en Compartido. Reusa infraestructura existente pero mezcla dos ejes conceptualmente distintos (UN comerciales vs auxiliares operativos), lo cual puede confundir en reportes.

Pro: reuso máximo. Contra: contamina el concepto de UN.

**Decisión**: [PENDING-DESIGN ExpenseAuxiliary vs reuso business_unit] — a validar antes de implementar. La preferencia técnica inicial es Alternativa A (tabla nueva) por claridad conceptual, pero requiere confirmación.

### Ejemplos de jerarquía + auxiliar

| Categoría (nivel 1) | Subcategoría (nivel 2) | Auxiliar (nivel 3) |
|---|---|---|
| Combustible | Vehículos | Camión-1, Camión-2, Camión-Willard |
| Mantenimiento | Maquinaria | Horno, Crisol, Montacargas-1, Montacargas-2 |
| Mantenimiento | Vehículos | Camión-1, Camión-2 |
| Repuestos | Vehículos | Camión-1, Camión-2 |
| Repuestos | Maquinaria | Horno, Crisol, Molino |
| Baterías nuevas | Vehículos | (auxiliares específicos) |

### Seed system para SAC

Al crear la organización SAC, el skill `/migrate-client` extendido pre-siembra ocho categorías system (`is_system_entity = True`, no editables por UI estándar):

1. Maquila Intersede
2. Maquila Willard
3. Logistica Willard
4. Logistica Interna BOG-BAQ
5. Logistica Interna CV-JM
6. Crisol Refinacion
7. Nomina Comercial
8. Comision Recoleccion

Además siembra subcategorías estándar (`Combustible/Vehiculos`, `Mantenimiento/Maquinaria`, etc.) que Johana podrá extender con auxiliares en su primera semana operativa.

Filtro en reportes: `GET /reports/expenses?expense_category_id=<X>` con expansión automática a subcategorías hijas (comportamiento actual decisión #44). Si se implementa Alternativa A, se agrega `expense_auxiliary_id` como filtro adicional. La lista completa de auxiliares vive en `ExpenseAuxiliary` y se construye con Johana al arranque [CONFIG-ARRANQUE: lista de máquinas y vehículos].

## 9.4 Tesorería Yurani (cajas menores por sede) [MODIFICADO, cerrado en visita 2026-07-02]

Yurani es la administradora de las cajas menores. Decision **CERRADA** (Daniel 2026-06-30 + visita 2026-07-02): hay **una caja menor POR SEDE, todas operadas por Yurani** — una persona, N cajas. Yurani tiene acceso directo a la plataforma con un rol limitado "caja menor". Modelo target unico — no hay modelo intermedio con Johana digitando en su nombre.

**Regla central de sede (corrección al v0.4): el gasto hereda el `warehouse_id` de la CAJA usada, no de un default del usuario.** Cada caja menor es una `MoneyAccount` tipo caja con `warehouse_id` propio (`CV-CajaMenor`, `JM-CajaMenor`, `BOG-CajaMenor` — ver §11.2.6); al registrar un gasto contra una de esas cajas, el `MoneyMovement.warehouse_id` se toma de la cuenta. `Membership.default_warehouse_id` queda degradado a conveniencia de UI a lo sumo (preseleccionar la caja habitual) — NO es la fuente del warehouse en gastos de caja menor.

### Rol RBAC "Caja Menor" (scope por cuentas asignadas)

Se define un rol `caja_menor` con el conjunto acotado de permisos:

- `treasury.create` — crear `MoneyMovement` de tipo gasto (expense) contra las cajas menores que administra
- `treasury.view` — ver `MoneyMovement`, con filtrado transparente a las cajas menores asignadas (no vía multi-tenancy `organization_id`, que sigue siendo SAC como cualquier otro rol)
- `expense_categories.view` — leer categorías y subcategorías/auxiliares para categorizar
- `treasury.edit_classification` — editar clasificación de sus propios movimientos dentro del día (permiso reutilizado de decisión #39)

Yurani NO tiene permisos para:

- Pagar a proveedores de inventario (`treasury.pay_supplier`)
- Ver reportes financieros consolidados (`reports.view_pnl`, `reports.view_balance`)
- Modificar movimientos de otras cuentas ni de otros roles
- Crear o editar terceros
- Aprobar el cierre diario ("OK del día" firma Johana)

El scope se implementa por **cuentas asignadas** (las N cajas menores), no por una sede única: como Yurani opera las cajas de todas las sedes, el backend restringe `account_id ∈ <cajas menores asignadas>` en `POST /money-movements` y filtra `GET /money-movements` a esas cuentas. La dimensión de sede de cada gasto queda garantizada por la herencia desde la cuenta (regla central de arriba).

### Categorización por Yurani

Yurani captura cada gasto con:

- La **caja** desde la que paga (selector de cuenta — esto determina la sede del gasto)
- Categoría → subcategoría → auxiliar (§9.3)
- `business_unit_id` — opcional; si no lo sabe, se registra como General (Tier 3, prorrateo automático) y Johana puede reclasificar después vía `PATCH /money-movements/{id}/classification` (decisión #39 extendida con `warehouse_id`)
- `third_party_id` opcional
- Evidencia (imagen/PDF, decisión #12)

Ejemplos de gastos típicos de Yurani (auxiliares mostrados):

- "Baterías nuevas para vehículos / Camión-1" (caja CV) → 3 baterías × $180.000 = $540.000
- "Mantenimiento maquinaria / Montacargas-1" (caja JM) → filtro + aceite $220.000
- "Combustible vehículos / Camión-Willard" (caja CV) → $150.000
- "Viáticos empleado José, viaje JM-CV, reunión operativa" (caja JM) → $80.000

### Capacitación

Yurani debe recibir capacitación específica sobre categorías/subcategorías/auxiliares (§9.3) y sobre la selección de la caja correcta por sede (la sede del gasto sale de la caja). Formato Excel actual de Yurani: se recoge al arranque para migrar saldos pendientes al momento del corte (dato de configuración, no bloquea el alcance).

# 10. Reportes

Los reportes se dividen en dos bloques: los **17 reportes preservados** (los que EcoBalance ya provee y forman la base contractual heredada) y los **6 reportes nuevos propios de SAC** diseñados específicamente para operar su modelo (Daniel sesion 2026-06-30 confirmó mantenerlos en Fase 1). Adicionalmente, el **panel de excepciones y alarmas** (§10.3) se eleva a módulo de primera clase — con captura única el cuadre renglón-por-renglón desaparece por construcción y el panel solo muestra anomalías (resuelve la triple digitación de Johana) — y el **dashboard SAC personalizado** consolida KPIs kg + caja por sede + P&L. Todos los reportes con exportación Excel siguen el patrón de paridad web/Excel (decisiones #51, #52).

## 10.1 Reportes preservados (17 base heredados de EcoBalance) [REUTILIZADO]

Estos reportes ya existen en EcoBalance, se aplican a SAC tal cual, y forman la base contractual mencionada en la propuesta cliente §2.6. La extensión "por sede" (`warehouse_id`) se hace agregando el filtro opcional en los endpoints existentes, sin duplicar la lógica.

| # | Reporte | Endpoint | Decisión de referencia |
|---|---|---|---|
| 1 | Dashboard ejecutivo | `GET /reports/dashboard` | — |
| 2 | Estado de resultados (P&L) periodo | `GET /reports/profit-and-loss` | #49 (drill-down) |
| 3 | P&L mensual comparativo | `GET /reports/profit-and-loss/monthly` | #50 |
| 4 | Balance general | `GET /reports/balance-sheet` | #31 |
| 5 | Balance detallado | `GET /reports/balance-detailed` | #38 |
| 6 | Balance histórico as_of_date | `GET /reports/balance-sheet?as_of_date=YYYY-MM-DD` | #41 |
| 7 | Flujo de caja | `GET /reports/cash-flow` | #7 |
| 8 | Reporte de gastos con agrupación flexible | `GET /reports/expenses` | #44 |
| 9 | Reporte de compras | `GET /reports/purchases` | #45 |
| 10 | Reporte de ventas | `GET /reports/sales` | #45 |
| 11 | Análisis de margen | `GET /reports/margin-analysis` | — |
| 12 | Rentabilidad por unidad de negocio | `GET /reports/profitability-by-business-unit` | — |
| 13 | Treasury Dashboard | `GET /reports/treasury-dashboard` | — |
| 14 | Estado de cuenta unificado del tercero | `GET /money-movements/third-party/{id}` | #16, #55 |
| 15 | Movimientos de inventario | `GET /inventory/movements` | — |
| 16 | Stock por bodega | `GET /inventory/stock` | — |
| 17 | Activos fijos y depreciación | `GET /fixed-assets/*` | — |

Todos estos reportes ganan el filtro opcional `warehouse_id` en Fase 1 (ver §9.2). El default es sin filtro (consolidado SAC). El filtro persiste en URL (`?warehouse_id=<X>`) con badge visual "Sede: X [×]" en las páginas frontend (patrón establecido decisión #49).

### 10.1.1 Brecha con los "17 reportes esenciales" del doc cliente [NUEVO]

Los "17 esenciales" de la propuesta cliente (§2.6) NO son la misma lista que los 17 heredados de arriba: el corte del cliente incluye **tres reportes que hoy no existen en EcoBalance** y que se construyen en Fase 1:

| Reporte prometido al cliente | Diseño |
|---|---|
| Antigüedad de cartera por cobrar | `GET /api/v1/reports/receivables-aging` [NUEVO] — CxC abiertas por tercero con buckets por rango (`0-30 \| 31-60 \| 61-90 \| >90` días, configurable). Base: balance del tercero > 0 descompuesto por antigüedad de los movimientos que lo componen (estado de cuenta unificado, [REUTILIZADO #16]), asignación FIFO informativa de abonos contra cargos más antiguos. Permiso `reports.view`. Aplica a todos los clientes EcoBalance, no solo SAC |
| Antigüedad de cartera por pagar | `GET /api/v1/reports/payables-aging` [NUEVO] — espejo para CxP (balance del tercero < 0 en proveedores/pasivos). Misma mecánica de buckets |
| Histórico de factores y tarifas | `GET /api/v1/reports/factors-tariffs-history` [NUEVO] — lista completa append-only de `MaterialConversionFormula` y `ServiceTariff` con vigencias (rango implícito entre `created_at` consecutivos), valor, `created_by` (aprobador) y notas. Es una vista de lectura sobre los dos maestros (§6.3, §6.4); permiso `kg_ledger.view` |

El resto de los 17 del cliente mapea a los heredados de la tabla anterior, con tres excepciones cubiertas por los reportes nuevos: el "Panel de excepciones del día" es §10.3, el "Estado de la deuda en plomo Willard" es el estado de cuenta kg + kg-balance (§10.2.1-§10.2.2) y el "Estado de la deuda intersede" es la misma familia sobre la cuenta intersede (§10.2.1, §12.1.1). El "Cuadre semanal Willard" NO está entre los 17 — pertenece a los 6 reportes propios de SAC (§10.2.5). La tabla de mapeo de §0.3 refleja esta brecha como "Divergente reconciliado: 3 reportes nuevos adicionales".

## 10.2 Reportes NUEVOS para SAC (6 propios) [NUEVO]

Estos seis reportes se diseñan específicamente para operar el modelo SAC con `KgLedger`, maquila interna y multi-sede. Daniel (sesion 2026-06-30) confirmó mantenerlos en Fase 1 — no se difieren a Fase 2. Todos siguen el patrón EcoBalance de endpoints (`GET /reports/<name>`), permisos granulares (`kg_ledger.view`, `willard.reconcile`, etc.), y exportación Excel con paridad web/Excel.

### 10.2.1 Reporte 1 — `KgLedger` Balance snapshot (con `as_of_date`)

**Propósito**: dashboard consolidado de los cinco saldos en kg (Willard Baterias, Willard Drosses, Intersede, Intra-horno, Crisol) a fecha actual o histórica. Análogo funcional al Balance General en pesos pero para la dimensión kg de plomo.

**Endpoint**: `GET /api/v1/reports/kg-balance?as_of_date=YYYY-MM-DD` (opcional).

**Permiso**: `kg_ledger.view`.

**Columnas**:

| Cuenta | Tipo | Balance kg | Contraparte (Willard/interna) | Última actualización |
|---|---|---|---|---|
| Willard Baterias — sub-saldo BAQ | willard_baterias | 131.000 kg | Willard S.A. | 2026-07-02 08:32 |
| Willard Baterias — sub-saldo BOG | willard_baterias | 48.000 kg | Willard S.A. | 2026-07-02 08:32 |
| Willard Drosses | willard_drosses | 18.500 kg | Willard S.A. | 2026-06-27 07:15 |
| Intersede CV↔JM | intersede | 3.200 kg | Interno CV/JM | 2026-06-27 09:00 |
| Intra-horno JM | intra_horno | 1.100 kg | Interno JM | 2026-06-27 06:45 |
| Crisol JM | crisol | 450 kg | Interno JM | 2026-06-27 06:45 |

Cálculo histórico: si `as_of_date` está presente, `SUM(delta_kg) WHERE account_id=X AND transaction_date <= as_of_date AND status='confirmed'` (patrón análogo decisión #41). Excluye movimientos `annulled` posteriores al corte.

### 10.2.2 Reporte 2 — Maquila Interna del Periodo

**Propósito**: mostrar la maquila interna **causada** por periodo — horno ($1.500/kg, causada al envío CV→JM) y crisol ($300/kg, causada a la salida del crisol) — como gasto por sede de origen e ingreso de Juan Mina. Reemplaza al reporte "Maquila Pendiente" del v0.4 (con causación al envío ya no existe maquila "represada": lo causado ES lo enviado/refinado del periodo). Permite a Johana y a Hugo ver cuánto le "cobró" JM a CV en el periodo y sostiene la política de utilidad cero (§3.5).

**Endpoint**: `GET /api/v1/reports/internal-maquila?date_from&date_to&concept=<horno|crisol>&from_warehouse=<CV|BOG>`.

**Permiso**: `maquila.view`.

**Columnas** (una fila por par causado, agrupable por concepto y por sede origen):

| Fecha | Concepto | Origen → JM | Documento origen | kg base | Tarifa | Monto | Estado |
|---|---|---|---|---|---|---|---|
| 2026-07-01 | Maquila horno | CV → JM | Transfer #142 | 600 kg | $1.500 | $900.000 | confirmed |
| 2026-07-01 | Crisol | CV → JM | CrucibleDischarge #17 | 600 kg | $300 | $180.000 | confirmed |
| 2026-07-02 | Maquila horno | BOG → JM | Transfer #145 | 300 kg | $1.500 | $450.000 | confirmed |

Totales al pie: por concepto y total del periodo (gasto de sedes origen = ingreso de JM, simetría exacta del par). Drill-down: cada fila lleva al `Transfer` o cierre de crisol origen y al par de `MoneyMovement` enlazado.

### 10.2.3 Reporte 3 — Vista tercero por sede

**Propósito**: filtrar el estado de cuenta unificado del tercero (decisión #16, #55) por `warehouse_id` de las operaciones. NO fragmenta el balance — el saldo del tercero sigue siendo único ORG-WIDE. Es un filtro READ-ONLY para saber "de mis 422 ton con Willard, cuántos vinieron a CV vs JM vs BOG". Útil para conciliación semanal Willard (ver §4.5).

**Endpoint**: `GET /api/v1/money-movements/third-party/{id}?warehouse_id=<X>`.

**Permiso**: `treasury.view` (el acceso a la dimensión de sede es implícito por membership — no existe permiso `warehouse.view`).

**Columnas**: idénticas al estado de cuenta unificado existente (fecha, tipo, descripción, débito/crédito, saldo corrido) más una nueva columna `Sede` visible. Fila "Saldo Inicial" respeta la ventana de fechas (decisión #55). El total al pie muestra `Saldo Contable` (ORG-WIDE, sin filtrar por sede) y `Movimientos filtrados por sede` (subtotal del filtro), aclarando que el saldo real del tercero es el consolidado.

### 10.2.4 Reporte 4 — Top proveedores por sede

**Propósito**: ranking de proveedores de chatarra por volumen y valor, con dimension `warehouse_id` para saber qué proveedor pesa más en cada sede. Insumo para negociación de precios y para detectar concentración excesiva (riesgo operativo).

**Endpoint**: `GET /api/v1/reports/top-suppliers?warehouse_id=<X>&period_from&period_to&limit=20`.

**Permiso**: `reports.view_purchases`.

**Columnas**:

| Ranking | Proveedor | Kg totales | Valor liquidado (COP) | % del total sede | Promedio por entrada | # entradas |
|---|---|---|---|---|---|---|
| 1 | Chatarrería El Sol | 45.200 kg | $189.840.000 | 22% | $4.200.000 | 45 |
| 2 | Reciclajes La Costa | 32.100 kg | $131.610.000 | 15% | $3.500.000 | 38 |

Ejemplo con SAC: los top 5 chatarreros de CV suelen concentrar >60% del volumen. Este reporte lo hace explícito.

### 10.2.5 Reporte 5 — Cuadre Willard semanal

**Propósito**: snapshot semanal firmable para la conciliación de los viernes con Willard (Hugo reunion noche 2026-06-26: "cada viernes se contienen los saldos"). Presenta saldo apertura de la semana + entradas + salidas = saldo cierre, más una tabla de discrepancias detectadas.

**Endpoint**: `GET /api/v1/reports/willard-weekly-reconciliation?week_ending=YYYY-MM-DD` (`week_ending` = viernes de cierre — parámetro canónico único en las tres secciones que lo citan: §4.5, aquí y §12.1.5).

**Permiso**: `willard.reconcile`.

**Estructura**:

- Bloque 1 — Baterías Willard: apertura lunes + N entradas (con detalle por centro de distribución) − N salidas = cierre viernes, con desglose de **sub-saldos por sede** (Barranquilla / Bogotá) y los movimientos entre sub-saldos.
- Bloque 2 — Drosses Willard: apertura + entradas + salidas = cierre.
- Bloque 3 — **Detalle por entrega (fecha, remisión, kg)**: cada entrega de plomo de la semana, línea por línea — la diferencia típica con Willard es una entrega que un lado registró y el otro no; este detalle es lo que permite encontrarla en minutos.
- Bloque 4 — Fletes y maquila facturados: maquila ($2.097/kg) + flete planta ($37/kg) por cada entrega de la semana; flete BOG-BAQ ($216/kg) acumulado del mes para la factura mensual.
- Bloque 5 — Discrepancias detectadas: diferencia entre saldo sistema y cuadre paralelo Willard (si Willard envía su cifra), movimientos sin `willard_distribution_center` (si aplica).

Se firma con botón "OK del viernes" (ver §10.3). Post-firma queda bloqueado a edición salvo admin con bitácora. **Quién lo maneja**: el **coordinador de postconsumo nacional** (persona de SAC, ver §2.4 y §14.2) envía el cuadro semanal a Willard y concilia el saldo nacional; el cuadre consolida los sub-saldos por sede más los centros informativos.

### 10.2.6 Reporte 6 — Reconciliación diaria intersede

**Propósito**: cerrar el día verificando que los movimientos intersede del día (`Transfer` CV→JM, `KgLedgerMovement` intersede, par de maquila interna causado) sean consistentes entre las tres fuentes. Es una salvaguarda de la triple digitación que Johana hoy hace en Excel.

**Endpoint**: `GET /api/v1/reports/daily-intersede-reconciliation?date=YYYY-MM-DD`.

**Permiso**: `reports.view` + `kg_ledger.view`.

**Estructura**:

| # | `Transfer` | `KgLedgerMovement` intersede | Par de maquila interna | ¿Cuadra? |
|---|---|---|---|---|
| 1 | Transfer #142 (1.000 kg scrap CV→JM) | +600 kg intersede (factor 0.6) | expense/income $900.000 (600 × $1.500) | Sí |
| 2 | Transfer #143 (500 kg scrap BOG→JM) | +300 kg intersede | expense/income $450.000 | Sí |
| 3 | Transfer #144 (800 kg scrap CV→JM) | +480 kg intersede | — (FALTA PAR DE MAQUILA) | No |

La fila con "No" alimenta el panel de excepciones (§10.3) como discrepancia crítica. **Nota**: por la atomicidad del paso B del traslado (§7.5), una fila "No" NO debería ocurrir en operación normal — el detector es puramente defensivo (bug, importación de datos, edición admin post-cierre con bitácora). Es el análogo del detector de `InventoryMovement` sin `warehouse_id` de §10.3.

## 10.3 Panel de excepciones y alarmas (módulo de primera clase) [NUEVO, reenfocado en v0.5]

**Reducción de alcance confirmada por Johana en la visita 2026-07-02**: con captura única, el cuadre renglón-por-renglón que hoy hace Johana **desaparece por construcción** — lo que sale de un cuadro ya no puede dejar de entrar en el otro, porque es un solo sistema. El "tablero de cuadre diario" del v0.4 se reenfoca a un **panel de excepciones**: el sistema concilia cada transacción sola y muestra únicamente lo anómalo. **En un día normal el panel está vacío.** Johana lo confirmó: lo que quiere ver es "un cuadro o alarma cuando haya una diferencia entre entrada y salida". No es un reporte más, es una **página con tareas** que Johana revisa al final del día.

### Modelo

Se define `DiscrepancyTask` con:

- `id`, `organization_id`, `discrepancy_type` (enum), `severity` (`normal | high | critical`), `status` (`open | in_review | justified | corrected | closed`)
- `entity_type` y `entity_id` (polimórfico: apunta a un `Transfer`, `MoneyMovement`, `InventoryMovement`, etc.)
- `description`, `detected_at`, `resolved_at`, `resolved_by`, `resolution_notes`

### Qué detecta el panel (detectores automáticos, cron diario 23:00 hora Colombia + evaluación al confirmar cada traslado)

- **Diferencia despacho vs recepción fuera de tolerancia**: los traslados intersede registran **cantidad despachada Y cantidad recibida**; dentro de la tolerancia (**3–5%, configurable**) el ajuste es automático tomando **lo recibido como fuente de verdad** — sin task. Por encima de la tolerancia: task `high` (excepción/alarma).
- **Diferencia de báscula** (entrada vs liquidación): si al liquidar una compra la cantidad final difiere >X% de la registrada, task `normal`.
- **Compras o ventas registradas sin liquidar al cierre del día**: task `normal` (operación incompleta).
- **Diferencias de arqueo físico**: conteo físico vs stock del sistema fuera de tolerancia, task `high`.
- **Saldos cruzados inconsistentes**: deuda Willard vs entregas registradas; deuda intersede vs despachos y salidas del día; saldo Willard kg vs cuadre paralelo Willard (si Johana sube su cifra, por `willard_distribution_center` y tolerancia configurable).
- **Stock negativo no explicado**: si algún material queda con stock negativo sin `warnings[]` justificados, task `high`.
- **Movimientos de inventario con costo cero**: `InventoryMovement` de compra/transformación con `unit_cost = 0` donde debería haber costo, task `normal` (típicamente digitación incompleta).
- **Compra o venta sin tercero asignado**: operación comercial sin `third_party_id`, task `normal`.
- **Saldo intersede antiguo sin movimiento**: kg pendientes en la cuenta intersede sin descarga en > N días (N configurable, default 30), task `normal` — típicamente merma de horno sin ajustar (§7.6).
- **`InventoryMovement` sin `warehouse_id`**: task `critical` (no debería ocurrir por validación de schema, pero si ocurre por importación se detecta).
- **`Transfer` en `JM-TRANSITO` > X días**: task `high` (no se confirmó recepción).
- **Reconciliación diaria intersede sin cuadre** (§10.2.6): cada fila "No" genera task `critical`.
- **Diferencias entre los cuadros Excel actuales de Johana y el sistema** durante el periodo de migración/operación dual.

### Flujo de trabajo por cada discrepancia

1. Cada discrepancia detectada se materializa como una **tarea** con tipo, severidad, monto o kg involucrado, sede y responsable sugerido.
2. Johana o el supervisor abre la tarea y elige una de tres resoluciones: **justificar** (nota explicativa que cierra la tarea), **corregir el documento origen** (genera el ajuste con bitácora), o **solicitar arqueo físico** (pone la tarea en espera hasta que el supervisor de bodega confirme el conteo).
3. La acción de resolución queda en la **bitácora** con usuario, fecha, motivo y trazabilidad al documento afectado.
4. Cuando todas las discrepancias del día quedan resueltas, Johana firma el **"OK del día"** — snapshot con firma que bloquea edición posterior salvo admin con bitácora.

Política post-cierre (Hugo reunion noche 2026-06-26): admin puede auditar sin autorización solo en casos especiales, siempre con bitácora que-quién-por qué. Reporte adicional "Bitácora de ediciones post-cierre" muestra trazabilidad completa.

### Endpoints, sello diario y permisos del panel [NUEVO]

- `GET /api/v1/exceptions?status=&severity=&type=&date_from=&date_to=` — listado de `DiscrepancyTask` (permiso `exceptions.view`).
- `POST /api/v1/exceptions/{id}/justify` — cierra con nota explicativa obligatoria (permiso `exceptions.resolve`).
- `POST /api/v1/exceptions/{id}/correct` — registra la corrección con link al documento corregido; el ajuste en sí se hace en el módulo origen con sus permisos propios (permiso `exceptions.resolve`).
- `POST /api/v1/exceptions/{id}/request-count` — pone la task en espera de arqueo físico (permiso `exceptions.resolve`).
- `POST /api/v1/exceptions/daily-ok?date=YYYY-MM-DD` — firma el **"OK del día"** (permiso `exceptions.sign_daily`, típicamente Johana): valida que no queden tasks `open` del día y emite un **`DailyOkSeal`** (tabla nueva, ver §11.1.11 — análogo diario del `KgLedgerReconciliationSeal` semanal: usuario, timestamp, fecha sellada, contadores de tasks resueltas). Post-firma, editar operaciones de ese día requiere permiso de admin y deja bitácora explícita — misma regla que el sello semanal (§4.5).

**Arqueo físico con aprobación** (módulo 6 del doc cliente): NO se crea un modelo nuevo — el arqueo reusa `InventoryAdjustment` existente (4 tipos, [REUTILIZADO]): el conteo físico se registra como resolución de la task (con el conteo en `resolution_notes`) y el ajuste resultante lo aprueba el supervisor de bodega con su permiso `inventory.adjust`; la task guarda el link al ajuste generado. La aprobación es la combinación `exceptions.resolve` (quien pide/cierra) + `inventory.adjust` (quien ejecuta el ajuste).

**El "OK del viernes" (acta semanal Willard)** es la extensión semanal del mismo mecanismo: acta firmada e inmutable con apertura, entradas, entregas y cierre por cuenta Willard, **con detalle por entrega (fecha, remisión, kg)** — ver §10.2.5. La maneja el coordinador de postconsumo nacional.

**Lo que NO hace el panel**: decidir por SAC qué resolver. La inteligencia operativa sigue siendo de Johana; el sistema le ahorra el trabajo de **encontrar** la discrepancia y le da el contexto para **resolverla** rápido.

### UI

Página `/exceptions` (Panel de Excepciones) con:

- Header: fecha, contador de tasks pendientes por severidad, botón "OK del día" (estado vacío prominente: "Sin excepciones — día cuadrado" en un día normal)
- Tabs por severidad (`critical`, `high`, `normal`)
- Lista de tasks con link al detalle de la entidad
- Toggle "Mostrar cerradas" para ver histórico
- Filtro por tipo de discrepancia

Mobile-responsive obligatorio (regla CLAUDE.md): cards mobile para tasks, sticky "OK del día" en bottom.

## 10.4 Dashboard SAC personalizado (KPIs kg + caja por sede + P&L consolidado) [NUEVO]

Página `/sac-dashboard` diseñada como landing page para Hugo y Johana. Reúne los indicadores críticos de operación diaria en tres bloques verticales.

### Bloque superior — 5 KPI cards de cuentas en kg

Una card por cada cuenta en kg (Willard Baterías, Willard Drosses, Intersede, Intra-horno, Crisol) con: nombre, balance kg actual, delta 7 días (verde/rojo), botón "Ver movimientos" que lleva al estado de cuenta kg del reporte 2 (§10.2.2). Las dos cards Willard muestran además la **antigüedad de la deuda kg** ("deuda Willard con antigüedad" prometida al cliente): bucketing informativo de los `KgLedgerMovement` positivos aún no descargados, asignando descargas FIFO contra los cargos más antiguos por `transaction_date` (buckets `0-30 \| 31-60 \| 61-90 \| >90` días — misma mecánica del aging de cartera, §10.1.1). La card Willard Baterías desglosa los sub-saldos BAQ/BOG. Layout `grid-cols-1 sm:grid-cols-2 md:grid-cols-5` (regla mobile-first CLAUDE.md). El modelo técnico subyacente es `KgLedgerAccount` (ver §11.1.1).

### Bloque medio — 4 KPI cards de caja por sede

Cards para CV-Caja, JM-Banco, BOG-Caja, Corp-Bancolombia. Cada una muestra balance actual, delta 7 días, y drill-down por click al detalle de movimientos filtrado por `warehouse_id`. Con drill-down interactivo (correción review): al hacer click en "Caja CV" se abre modal con tree-view de categorías jerárquicas (§9.3): Combustible → Vehículos → Camión-1 con montos y contadores. Un segundo click va al detalle de movimientos individuales.

### Bloque inferior — Ventas, Compras, A/R Willard, A/P proveedores

Cards agregadas del día actual: total ventas, total compras (liquidadas), cuentas por cobrar Willard (`service_income` con `account_id=NULL` pendientes de cobro — facturas de maquila + fletes causadas, §6.1), cuentas por pagar a proveedores de chatarra. Además, dos bloques por sede prometidos al cliente: **inventario por sede** (valor a costo del stock por `warehouse_id`, per-warehouse stock existente) y **resultado por sede** (utilidad del P&L filtrado por `warehouse_id` del periodo seleccionado, §9.2 — incluye los pares internos de maquila). Drill-down a los reportes de detalle preservados (§10.1).

### Alertas

Sección de alertas persistente: excepciones del panel (§10.3) con conteo por severidad, saldos intersede antiguos sin movimiento (contador), stock crítico (materiales bajo umbral, si se configura umbrales).

### Filtros compartidos

DateRangePicker compartido vía `useDateFilter` store (patrón decisión #50). Toggle "Sede" con persistencia URL (`?warehouse_id=<X>`, patrón decisión #50). Cambiar la sede filtra los bloques medio e inferior; el bloque superior (KgLedger) no se filtra porque los saldos kg son ORG-WIDE por diseño (§4.2).

### Permisos

Permission-gated: solo usuarios con permiso `dashboard.view_sac`. Rol Admin SAC (Hugo, Johana) tiene acceso completo. Rol `caja_menor` (Yurani) tiene `dashboard.view_sac` en **versión reducida por cuentas asignadas** (consistente con §9.4 y la matriz §14.2): ve únicamente las cards de sus cajas menores (todas las sedes — opera una caja por sede) y sus propios movimientos; sin bloques KgLedger, ventas/compras ni resultado.

## 10.5 Reportes Excel con paridad web/Excel [REUTILIZADO #51, #52]

Todos los reportes con exportación Excel siguen los dos patrones ya establecidos:

- **Decisión #51** — Filtros configurables con paridad web/PDF/Excel: los filtros aplicados en pantalla (hide below, sort, filtro sede, filtro categoría) se aplican también al Excel exportado. Helper de transformación se ejecuta antes de renderizar y antes de exportar, garantizando que el usuario vea en Excel exactamente lo que ve en web. Formato monetario negativos como paréntesis `($X)`, valores como `number` (sumables en Excel), sortables.
- **Decisión #52** — Excel de operaciones con hoja Detalle por línea: compras, ventas y doble partidas exportan dos hojas — "Resumen" (una fila por operación) + "Detalle" (una fila por línea de material, con cantidad como número sumable y columna Unidad respetando decisión #54 unit-aware).

Aplicado a los reportes nuevos SAC:

- **Excel KgLedger Balance** (§10.2.1): dos hojas — "Resumen 5 Cuentas" (una fila por cuenta con balance) + "Detalle por Movimiento" (una fila por `KgLedgerMovement` con delta, transaction_date, source_type, description). Columna Balance kg como número sumable.
- **Excel Maquila Interna del Periodo** (§10.2.2): una hoja con los pares causados en el periodo (fecha, concepto, origen, kg base, tarifa, monto) + totales por concepto al pie. Columnas kg y monto como números sumables.
- **Excel Cuadre Semanal Willard** (§10.2.5): snapshot firmable con estructura idéntica a la web (5 bloques). Header del archivo indica "Firmado por: <usuario con `willard.reconcile`, típicamente el coordinador de postconsumo nacional> el viernes DD/MM/AAAA" cuando aplica.
- **Excel Top Proveedores** (§10.2.4): una hoja con ranking, columnas de valor y kg como números sumables, filtro `warehouse_id` visible en header.
- **Excel Reconciliación Diaria Intersede** (§10.2.6): una hoja con las filas del día, columna "¿Cuadra?" con valores `Sí/No`.

**Exportación PDF**: la promesa al cliente es Excel **y** PDF en todos los reportes. Los heredados ya tienen su cobertura actual; para los nuevos SAC se aplica el patrón PDF de decisión #51 (formato mobile/desktop seleccionable) con prioridad en los dos que viajan a externos: el **Cuadre Semanal Willard** (acta firmada — PDF desktop landscape con los 5 bloques + bloque de firma, es el documento que se envía a Willard) y el **KgLedger Balance**. El resto de reportes nuevos ganan PDF con el mismo patrón antes del cierre de Fase 1.

Todos los reportes web utilizan el patrón `exportOverride` (decisión #52) en el `DataTable` compartido cuando el export por defecto no cubre la estructura específica. Filtros de la URL se replican en el header del Excel para que el archivo sea autocontenido (ejemplo: "Reporte de gastos – Sede: CV – Rango: 01/06/2026 – 30/06/2026"). Los formatos monetarios respetan `CURRENCY_FMT` (`"$"#,##0;("$"#,##0)`) para negativos como paréntesis (decisión #51).

# 11. Cambios al modelo de datos

Esta sección consolida los cambios necesarios al esquema de EcoBalance para soportar SAC sin degradar la operación de los 3 clientes existentes (Costa, Biogreen, MetaRecycling). El principio arquitectónico es aditivo y backwards-compatible: nuevas tablas para lo que no encaja en el modelo actual (KgLedger, fórmulas de conversión, tarifas de servicio, sellos de conciliación y panel de excepciones) y extensiones vía columnas nullable para lo que sí encaja (`warehouse_id` en `MoneyMovement`, marcadores en `Sale` e `InboundOrder`). Ningún cambio rompe invariantes globales como el costo promedio único (ver [decision #5]) ni el saldo unificado del tercero (ver [decision #16], [decision #55]).

## 11.1 Nuevas tablas [NUEVO]

Se introducen **doce tablas nuevas** propias del negocio SAC: cinco de dominio kg/tarifas (`KgLedgerAccount`, `KgLedgerMovement`, `MaterialConversionFormula`, `ServiceTariff`, `KgLedgerReconciliationSeal`), dos del panel de excepciones (`DiscrepancyTask` §10.3, `DailyOkSeal` §11.1.11), tres de captura y planta (`InboundOrder` + líneas §11.1.12, `FurnaceCharge`/`CrucibleCharge` §11.1.13), dos maestros mínimos (`Driver`/`Vehicle` §11.1.14) — más los seeds de `ExpenseCategory` (§11.1.8) y una tabla marcada [PENDING-DESIGN] para auxiliares de gasto (§11.1.7). Todas heredan `TimestampMixin` + `OrganizationMixin` (multi-tenant estricto por `organization_id`, ver [decision #25], [decision #26]). Los índices propuestos priorizan las consultas de balance corriente y estado de cuenta.

**Nota v0.5**: las tres tablas del modelo de causación diferida de maquila del v0.4 se **eliminaron del diseño activo** (la visita 2026-07-02 cerró causación al envío — ver nota de decisión en §5.2). Los numerales §11.1.5, §11.1.6 y §11.1.10 se conservan como stubs para no renumerar; la maquila interna se modela ahora con dos tipos nuevos de `MoneyMovement` (ver §11.2.1).

### 11.1.1 `KgLedgerAccount` [NUEVO] — cuenta paralela en kg de plomo

Registra cada cuenta paralela al libro en pesos. SAC tiene **cinco cuentas lógicas confirmadas en la visita 2026-07-02** (ver §4.1): Willard Baterías (con **dos sub-cuentas por sede**: Barranquilla y Bogotá), Willard Drosses, Intersede CV↔JM, Intra-horno JM y Crisol JM — el crisol quedó como cuenta separada para medir la eficiencia por etapa. Total: **6 filas** de `KgLedgerAccount` (la cuenta lógica Willard Baterías son 2 filas, una por sub-saldo).

| Columna | Tipo SQL | Nullable | Descripción |
|---|---|---|---|
| `id` | `UUID` | NO | PK, `GUID` cross-DB. |
| `organization_id` | `UUID` | NO | FK `organizations.id`, filtrado automático por `CRUDBase._base_query()`. |
| `code` | `VARCHAR(32)` | NO | Código corto único por org, convención con guiones (§4.2): `WILLARD-BAT-BAQ`, `WILLARD-BAT-BOG`, `WILLARD-DROSS`, `INTERSEDE-CV-JM`, `INTRA-HORNO-JM`, `CRISOL-JM`. |
| `display_name` | `VARCHAR(120)` | NO | Nombre presentable. |
| `account_type` | `VARCHAR(32)` | NO | Enum: `willard_baterias \| willard_drosses \| intersede \| intra_horno \| crisol`. |
| `warehouse_id` | `UUID` | SÍ | FK `warehouses.id`. Para `willard_baterias` distingue los **sub-saldos por sede** (CV = Barranquilla, BOG = Bogotá); para cuentas internas (intra_horno, crisol) es JM. NULL para `willard_drosses` e `intersede` (org-wide). |
| `third_party_id` | `UUID` | SÍ | FK `third_parties.id`. Solo para cuentas Willard (Baterías, Drosses). NULL para internas. |
| `tolerance_kg` | `DECIMAL(12,4)` | SÍ | Tolerancia (± kg) del bloque de discrepancias del cuadre semanal (§10.2.5, §18.2). NULL = sin alerta. |
| `is_active` | `BOOLEAN` | NO | Soft delete. Default `TRUE`. |
| `created_at` / `updated_at` | `TIMESTAMP` | NO | `TimestampMixin`. |

FK constraints:

- `organization_id → organizations(id)` `ON DELETE CASCADE`.
- `warehouse_id → warehouses(id)` `ON DELETE RESTRICT`.
- `third_party_id → third_parties(id)` `ON DELETE RESTRICT`.

Índices:

- `ix_kg_ledger_account_org_type UNIQUE(organization_id, account_type, warehouse_id)` `NULLS NOT DISTINCT` (PostgreSQL 15+) — impide duplicados semánticos (dos veces "Intersede CV↔JM" en la misma org) incluso con `warehouse_id NULL` en las cuentas org-wide; misma definición que §4.2.
- `ix_kg_ledger_account_org_code UNIQUE(organization_id, code)`.

Invariantes:

- CHECK: si `account_type IN ('willard_baterias', 'willard_drosses')` entonces `third_party_id IS NOT NULL`.
- CHECK: si `account_type = 'willard_baterias'` entonces `warehouse_id IS NOT NULL` (sub-saldo por sede — dos filas por cuenta lógica, ver §4.1).
- CHECK: si `account_type IN ('intra_horno', 'crisol')` entonces `warehouse_id IS NOT NULL AND third_party_id IS NULL`.
- CHECK: `account_type IN ('intersede', 'willard_drosses')` acepta `warehouse_id NULL` (org-wide, ver §4.1).

Ejemplo INSERT — la cuenta lógica Willard Baterías son **dos filas** (sub-saldos por sede, cumpliendo el CHECK `warehouse_id IS NOT NULL`):

```sql
INSERT INTO kg_ledger_accounts (id, organization_id, code, display_name, account_type, warehouse_id, third_party_id)
VALUES
  ('a1b2...', 'sac-org-uuid', 'WILLARD-BAT-BAQ', 'Willard - Baterías (Barranquilla)', 'willard_baterias', 'cv-warehouse-uuid', 'willard-tp-uuid'),
  ('c3d4...', 'sac-org-uuid', 'WILLARD-BAT-BOG', 'Willard - Baterías (Bogotá)', 'willard_baterias', 'bog-warehouse-uuid', 'willard-tp-uuid');
```

### 11.1.2 `KgLedgerMovement` [NUEVO] — cada asiento en kg

Es el análogo en kg del `MoneyMovement`. Cada evento físico (recepción postconsumo, envío intersede, carga a horno, entrega a Willard) genera exactamente un `KgLedgerMovement` con `delta_kg` firmado. El balance corriente de una cuenta es `SUM(delta_kg) WHERE account_id=X AND status='confirmed'` — sin snapshot materializado, análogo a `third_party.balance` unificado ([decision #16]).

| Columna | Tipo SQL | Nullable | Descripción |
|---|---|---|---|
| `id` | `UUID` | NO | PK. |
| `organization_id` | `UUID` | NO | FK. |
| `account_id` | `UUID` | NO | FK `kg_ledger_accounts.id`. |
| `delta_kg` | `DECIMAL(14,4)` | NO | Firmado. Positivo = acumula deuda / carga; negativo = descarga / entrega. |
| `transaction_date` | `TIMESTAMP` | NO | Fecha de negocio. **BusinessDate normalizado a mediodía UTC** vía Pydantic `BeforeValidator` (ver `app/utils/dates.py`) — invariante global CLAUDE.md. NUNCA `Date` plano. |
| `description` | `VARCHAR(500)` | SÍ | Texto libre. |
| `source_type` | `VARCHAR(40)` | NO | Enum: `postconsumo_receipt \| drosses_receipt \| willard_subbalance_move \| intersede_send \| intersede_return \| intersede_discharge \| furnace_charge \| furnace_discharge \| crucible_charge \| crucible_discharge \| willard_delivery \| manual_adjustment \| migration_initial_load`. Catálogo completo en §4.3. |
| `source_id` | `UUID` | SÍ | Referencia polimórfica al evento origen (`InboundOrder.id`, `Transfer.id`, `Sale.id`, etc.), según `source_type`. |
| `inventory_movement_id` | `UUID` | SÍ | FK `inventory_movements.id`. Puebla cuando el evento kg está atado a un movimiento físico (ej: entrega a Willard). NULL para movimientos puros de KgLedger (ej: envío intersede que sólo mueve deuda, no inventario). |
| `conversion_formula_snapshot` | `JSONB` | SÍ | Snapshot exacto de la fórmula aplicada al momento del evento. Ver Anexo D para JSON schemas por `formula_type`. Patrón inspirado en [decision #41] (`MaterialCostHistory` snapshot). |
| `created_by` | `UUID` | NO | FK `users.id`. |
| `created_at` / `updated_at` | `TIMESTAMP` | NO | Timestamps. |
| `status` | `VARCHAR(16)` | NO | Enum: `confirmed \| annulled`. Default `confirmed`. Precedente [decision #48]. |
| `annulled_reason` | `VARCHAR(500)` | SÍ | Motivo de anulación. |
| `annulled_at` | `TIMESTAMP` | SÍ | Cuando se anuló. |
| `annulled_by` | `UUID` | SÍ | FK `users.id`. |

FK constraints:

- `account_id → kg_ledger_accounts(id)` `ON DELETE RESTRICT`.
- `inventory_movement_id → inventory_movements(id)` `ON DELETE SET NULL`.

Índices:

- `ix_kg_movement_account_date(account_id, transaction_date DESC)` — para estado de cuenta con saldo corrido.
- `ix_kg_movement_source(source_type, source_id)` — para navegación desde evento origen.
- `ix_kg_movement_org_status(organization_id, status)`.

Invariantes:

- `delta_kg != 0` (no se permiten movimientos vacíos).
- Anulación no borra el registro (soft): `status='annulled'` + campos `annulled_*` obligatorios. `SUM(delta_kg)` excluye anulados vía filtro `status='confirmed'`.
- `transaction_date` no puede ser posterior a `NOW()` + margen operativo (validación de servicio).

Ejemplo INSERT (recepción postconsumo de 200 unidades de referencia 07, factor 2.5 kg/unidad = 500 kg plomo):

```sql
INSERT INTO kg_ledger_movements
  (id, organization_id, account_id, delta_kg, transaction_date, source_type, source_id,
   conversion_formula_snapshot, description, created_by, status)
VALUES
  ('mov-uuid', 'sac-org-uuid', 'willard-bat-account-uuid', 500.0000, '2026-07-15 12:00:00+00',
   'postconsumo_receipt', 'inbound-order-uuid',
   '{"formula_type":"battery_to_lead","parameters":{"kg_lead_per_unit":2.5},"material_reference":"07"}'::jsonb,
   'Postconsumo Willard - 200 unid ref 07 - BOG', 'user-david-uuid', 'confirmed');
```

### 11.1.3 `MaterialConversionFormula` [NUEVO] — fórmulas de conversión Willard

Tabla maestra de factores por material y sub-cuenta Willard (`escurrido`/`pinza` cuando aplica). Append-only siguiendo el patrón puro de [decision #35] (`PriceList`): la vigente es `max(created_at)` por `(material_id, willard_account_subtype)`. Sin `valid_to`/`valid_from`.

| Columna | Tipo SQL | Nullable | Descripción |
|---|---|---|---|
| `id` | `UUID` | NO | PK. |
| `organization_id` | `UUID` | NO | FK. |
| `material_id` | `UUID` | NO | FK `materials.id`. |
| `formula_type` | `VARCHAR(40)` | NO | Enum: `battery_to_lead \| drosses_to_lead \| scrap_with_terminal_to_lead \| custom`. |
| `parameters` | `JSONB` | NO | Estructura por `formula_type`. Ver Anexo D. Ej `{"lead_percentage": 0.53}` para drosses, `{"kg_lead_per_unit": 2.5}` para baterías, `{"scrap_factor": 0.56, "terminal_weight_kg": 50}` para scrap-con-borne. |
| `willard_account_subtype` | `VARCHAR(16)` | SÍ | Enum: `escurrido \| pinza`. Discriminador de FÓRMULA dentro de la cuenta Willard Drosses (caso SEC, §6.4) — NUNCA cuentas separadas. NULL para materiales de fórmula única. |
| `notes` | `VARCHAR(500)` | SÍ | Contexto del cambio (ej: renegociación IPC 2026). |
| `created_by` | `UUID` | NO | FK. |
| `created_at` | `TIMESTAMP` | NO | Determina vigencia. |

FK constraints: `material_id → materials(id) ON DELETE RESTRICT`.

Índices:

- `ix_mcf_material_current(material_id, willard_account_subtype, created_at DESC)` — soporta la consulta "fórmula vigente".
- `ix_mcf_org(organization_id)`.

Invariantes:

- `parameters` no puede estar vacío.
- Nunca UPDATE ni DELETE — sólo INSERT (append-only). El servicio bloquea explícitamente `PATCH/DELETE`.
- La fórmula vigente en cualquier momento se calcula on-the-fly: no hay campo `is_current`.

Ejemplo INSERT (fórmula scrap-con-borne para SEC ESCURRIDO):

```sql
INSERT INTO material_conversion_formulas
  (id, organization_id, material_id, formula_type, parameters, willard_account_subtype, notes, created_by)
VALUES
  ('mcf-uuid', 'sac-org-uuid', 'sec-material-uuid', 'scrap_with_terminal_to_lead',
   '{"scrap_factor": 0.56, "terminal_weight_kg": 50}'::jsonb,
   'escurrido', 'Vigente contrato Willard 2026-01', 'user-hugo-uuid');
```

### 11.1.4 `ServiceTariff` [NUEVO] — tarifas de servicio (maquila y fletes)

Tabla maestra de tarifas monetarias por servicio. Append-only puro alineado con [decision #35] — sin `valid_to`/`valid_from`. La vigente es `max(created_at)` por `tariff_code`. Toda causación es inmediata al evento (§5, §6): el `MoneyMovement` persiste el monto calculado con la tarifa vigente (y `tariff_id` como referencia de trazabilidad) — no hay snapshots en tablas intermedias. Valores sugeridos y parametrizables.

| Columna | Tipo SQL | Nullable | Descripción |
|---|---|---|---|
| `id` | `UUID` | NO | PK. |
| `organization_id` | `UUID` | NO | FK. |
| `tariff_code` | `VARCHAR(48)` | NO | Enum: `maquila_willard \| maquila_intersede_cv_jm \| maquila_crisol \| flete_willard_bog_baq \| flete_willard_planta_planta`. |
| `unit_price_cop` | `DECIMAL(12,2)` | NO | Precio unitario en pesos colombianos. |
| `unit` | `VARCHAR(24)` | NO | Enum: `per_kg_lead \| per_kg_battery \| per_unit`. |
| `notes` | `VARCHAR(500)` | SÍ | Contexto (renegociación IPC, cambio contractual). |
| `created_by` | `UUID` | NO | FK. |
| `created_at` | `TIMESTAMP` | NO | Determina vigencia. |

FK constraints: estándar.

Índices:

- `ix_st_code_current(organization_id, tariff_code, created_at DESC)`.

Invariantes:

- `unit_price_cop > 0`.
- Append-only; UPDATE/DELETE bloqueados en servicio.
- Cambios anuales por IPC (Índice de Precios al Consumidor) crean un nuevo registro; el histórico queda intacto para trazabilidad.

Ejemplo INSERT (tarifa maquila Willard confirmada por Hugo reunión 2026-06-26):

```sql
INSERT INTO service_tariffs (id, organization_id, tariff_code, unit_price_cop, unit, notes, created_by)
VALUES
  ('st-uuid', 'sac-org-uuid', 'maquila_willard', 2097.00, 'per_kg_lead',
   'Tarifa vigente confirmada Hugo 2026-06-26', 'user-hugo-uuid');
```

### 11.1.5 (Eliminada en v0.5) — tabla de compromisos de maquila diferida

La tabla de compromisos de causación diferida de maquila intersede prevista en v0.4 **se elimina del diseño activo**: la visita a planta del 2026-07-02 cerró la causación **al envío** como par de `MoneyMovement` internos enlazados (ver §5.2, incluida la nota de decisión, y §11.2.1). No se crea ninguna tabla nueva para este mecanismo. Numeral conservado como stub para no renumerar.

### 11.1.6 (Eliminada en v0.5) — tabla de consumos de maquila al liquidar ventas

La tabla de consumos FIFO al liquidar ventas prevista en v0.4 **se elimina del diseño activo** por la misma razón del §11.1.5: con causación inmediata al envío no existe compromiso pendiente que consumir. La liquidación de la venta en JM solo descarga la cuenta kg intersede (`intersede_discharge`, §7.6). Numeral conservado como stub para no renumerar.

### 11.1.7 `ExpenseAuxiliary` [PENDING-DESIGN] — auxiliar de tercer nivel para categorización

Johana (reunión mañana 2026-06-26) requiere categorizar gastos con detalle "por máquina, por vehículo" (montacargas #1, camión-2, horno, crisol). La estructura actual de `ExpenseCategory` es máximo 2 niveles ([decision #36]). Hay dos alternativas de diseño, ninguna cerrada:

1. **`ExpenseAuxiliary` como tabla dedicada** con FK a `expense_categories.id` y `money_movements.expense_auxiliary_id` opcional. Ventaja: separación semántica clara (categoría = tipo de gasto; auxiliar = objeto físico costeado). Desventaja: nueva tabla y modelo mental adicional para el usuario.
2. **Reuso de `BusinessUnit` como sub-dimensión** creando UN internas (`Montacargas-1`, `Camion-1`, `Horno`). Ventaja: cero cambio de modelo, aprovecha el 3-tier existente ([decision #44]). Desventaja: mezcla conceptual (una UN debería ser una línea de negocio, no un activo físico).

Decisión de diseño pendiente — se cierra antes de implementar el módulo de gastos (no depende del cliente). Impacto en §9.3 y §13.2.

### 11.1.8 Seeds de `ExpenseCategory` SAC [NUEVO]

Ocho categorías `is_system_entity=TRUE` sembradas al crear la organización SAC:

| `name` | `is_direct_expense` | `parent_id` | Uso |
|---|---|---|---|
| Maquila Intersede | `TRUE` | NULL | Par `internal_maquila_expense`/`internal_maquila_income` causado al envío CV→JM ($1.500/kg, §5). |
| Crisol Refinación | `TRUE` | NULL | Par de maquila interna adicional $300/kg causado a la salida del crisol (§5). |
| Maquila Willard | `FALSE` | NULL | `service_income` categorizado (para consistencia en reportes). |
| Logística Willard | `FALSE` | NULL | Fletes cobrados a Willard como ingreso. |
| Logística Interna BOG-BAQ | `TRUE` | NULL | Gasto real de transporte entre sedes. |
| Logística Interna CV-JM | `TRUE` | NULL | Gasto real transporte intra-BAQ. |
| Nómina Comercial | `FALSE` | NULL | Nómina fija de comerciales (Hugo, sesión noche 2026-06-26). |
| Comisión Recolección | `FALSE` | NULL | **Corregido en v0.6 — se invirtió respecto de v0.5**: la comisión Green Loop ($100/kg) **SÍ** aterriza en una categoría de gasto de este tipo. [Decisión #83] crea la categoría de sistema **"Comisiones de recolección"** (indirecta, reclasificable desde Configuración) y causa ahí el `expense_accrual` al liquidar. La redacción anterior decía que NO usaba categoría porque se prorrateaba al costo. Ver §7.3 punto 5. |

### 11.1.9 `KgLedgerReconciliationSeal` [NUEVO] — firma inmutable del cuadre semanal Willard

Registro auditable del "OK del viernes" con Willard (ver §4.5). Cada semana el coordinador de postconsumo nacional cuadra los saldos kg con Willard y firma el cierre (Johana cuadra el sub-saldo Barranquilla que lo alimenta); esta tabla persiste el snapshot inmutable de esa firma, incluyendo el hash de los movimientos incluidos — permite auditoría posterior y garantiza que editar/anular movimientos de una semana ya firmada requiere permiso especial (`kg_ledger.edit_after_seal`) con bitácora explícita.

| Columna | Tipo SQL | Nullable | Descripción |
|---|---|---|---|
| `id` | `UUID` | NO | PK. |
| `organization_id` | `UUID` | NO | FK `organizations.id`. |
| `week_ending_date` | `DATE` | NO | Viernes de cierre de la semana. Junto con `account_id` forma UNIQUE. |
| `account_id` | `UUID` | NO | FK `kg_ledger_accounts.id`. Una fila por cuenta kg (típicamente Willard Baterías + Drosses). |
| `saldos_cierre` | `JSONB` | NO | Snapshot de saldo cierre + apertura + totales por tipo de movimiento incluidos. |
| `hash_movements` | `VARCHAR(64)` | NO | SHA-256 sobre la lista ordenada de `KgLedgerMovement.id` incluidos en la semana. Detecta ediciones post-firma. |
| `signed_by` | `UUID` | NO | FK `users.id` que firmó (usuario con `willard.reconcile` — típicamente el coordinador de postconsumo nacional). |
| `signed_at` | `TIMESTAMP` | NO | Timestamp de la firma. |
| `notes` | `TEXT` | SÍ | Contexto o discrepancias justificadas antes de firmar. |

Índices: `UNIQUE(organization_id, account_id, week_ending_date)`.

Referenciada en §4.5. Permiso: `willard.reconcile` para crear; `kg_ledger.edit_after_seal` (admin) para editar movimientos de una semana ya firmada.

### 11.1.10 (Eliminada en v0.5) — tabla de auditoría de ajustes sobre compromisos de maquila

Se elimina junto con el modelo diferido (ver §11.1.5). Los ajustes de kg por merma se cubren con el mecanismo existente `KgLedgerMovement(source_type='manual_adjustment')` sobre la cuenta Intersede (motivo obligatorio, permiso `kg_ledger.manage_adjustments`, ver §7.6) — no requiere tabla adicional. Numeral conservado como stub para no renumerar.

### 11.1.11 `DailyOkSeal` [NUEVO] — firma del "OK del día"

Análogo diario del `KgLedgerReconciliationSeal` (§11.1.9), emitido por `POST /exceptions/daily-ok` (§10.3) cuando todas las `DiscrepancyTask` del día quedan resueltas.

| Columna | Tipo SQL | Nullable | Descripción |
|---|---|---|---|
| `id` | `UUID` | NO | PK. |
| `organization_id` | `UUID` | NO | FK. |
| `sealed_date` | `DATE` | NO | Día de negocio sellado. `UNIQUE(organization_id, sealed_date)`. |
| `tasks_resolved_count` | `INTEGER` | NO | Contadores de tasks del día (justificadas / corregidas / arqueadas) en JSONB si se quiere detalle. |
| `signed_by` | `UUID` | NO | FK `users.id` (permiso `exceptions.sign_daily` — típicamente Johana). |
| `signed_at` | `TIMESTAMP` | NO | Timestamp de la firma. |
| `notes` | `TEXT` | SÍ | Contexto. |

Regla post-firma: editar/anular operaciones con fecha de negocio ≤ `sealed_date` requiere rol admin y deja bitácora explícita (misma política del sello semanal, §4.5). El servicio consulta el último `DailyOkSeal` al validar ediciones.

### 11.1.12 `InboundOrder` [NUEVO] — orden de entrada (captura única en patio)

Es el documento central de la "captura única" de Fase 1 (módulo 1 del doc cliente): cubre compra propia, postconsumo Willard, drosses, recolección en ruta y reventa. NO existe en EcoBalance — es tabla nueva; las compras derivan de ella (una `InboundOrder` de compra propia genera su `Purchase` en `registered`).

| Columna | Tipo SQL | Nullable | Descripción |
|---|---|---|---|
| `id` / `organization_id` | `UUID` | NO | PK / FK multi-tenant. |
| `order_number` | `INTEGER` | NO | Consecutivo por org ([REUTILIZADO] sequential numbering). |
| `inbound_type` | `VARCHAR(24)` | NO | Enum: `purchase \| postconsumo_baterias \| drosses \| ruta \| reventa`. |
| `warehouse_id` | `UUID` | NO | Sede de recepción física. Inmutable post-registro (§7.2). |
| `third_party_id` | `UUID` | **v0.6: SÍ (nullable)** | Proveedor de la entrada. **Cambia en v0.6**: la fuente de verdad pasa a la LÍNEA (`inbound_order_lines.third_party_id`, NOT NULL). Esta columna de cabecera conserva el proveedor **solo cuando todas las líneas comparten uno**; con varios queda NULL. Es campo de presentación y búsqueda — no se lee para derivar efectos. En postconsumo Willard siempre hay uno solo, derivado del titular de la cuenta de kg ([decision #80]). Ver §7.3. |
| `date` | `TIMESTAMP` | NO | BusinessDate noon UTC. |
| `driver_id` / `vehicle_id` | `UUID` | SÍ | FK a maestros `drivers` / `vehicles` (§11.1.14). |
| `willard_distribution_center` | `VARCHAR(24)` | SÍ | Informativo (§6.5). |
| `willard_account_subtype` | `VARCHAR(16)` | SÍ | `escurrido \| pinza` — obligatorio si el material es SEC (§6.4). |
| `goes_directly_to_jm` | `BOOLEAN` | NO | Drosses directo BOG→JM (§7.3). Default FALSE. |
| `status` | `VARCHAR(16)` | NO | `draft \| confirmed \| annulled`. |
| líneas | — | — | `InboundOrderLine`: material, cantidad, unidad, peso báscula, notas de calidad. |
| `created_by`, timestamps, `annulled_*` | | | Patrón estándar. |

Efectos al confirmar (según `inbound_type`): `InventoryMovement in` (transit para compra propia), `KgLedgerMovement` (`postconsumo_receipt` / `drosses_receipt`) para Willard, y creación del `Purchase(registered)` asociado cuando hay compra. Endpoints en §12.1.6.

### 11.1.13 `FurnaceCharge` / `CrucibleCharge` [NUEVO] — eventos de proceso de planta

Registran las cargas y descargas de horno grande y crisol (§4.3, §7.4). Comparten estructura (una tabla por evento o tabla única `ProcessEvent` con `process_type` — decisión de implementación; se especifica como dos tablas para claridad):

| Columna | Tipo SQL | Nullable | Descripción |
|---|---|---|---|
| `id` / `organization_id` | `UUID` | NO | PK / FK. |
| `event_type` | `VARCHAR(16)` | NO | `charge \| discharge`. |
| `date` | `TIMESTAMP` | NO | BusinessDate noon UTC. |
| `material_id` | `UUID` | NO | Aportante cargado (horno) / plomo crudo (crisol). |
| `quantity_kg` | `DECIMAL(14,4)` | NO | Kg físicos del evento. |
| `output_material_id` / `output_quantity_kg` | | SÍ | Solo en `discharge`: plomo crudo producido (horno) / plomo puro (crisol). |
| `status`, `annulled_*`, `created_by`, timestamps | | | Patrón estándar. |
| `batch_id` | `UUID` | SÍ | FK `furnace_batches` — NULL en Fase 1 (trazabilidad 1:1 llega en Fase 2, §7.4). |

Efectos: cada evento inserta su `KgLedgerMovement` (`furnace_charge`/`furnace_discharge`/`crucible_charge`/`crucible_discharge`, §4.3); `CrucibleDischarge` emite además el par de maquila del crisol (§5.1 momento 2) y los `discharge` generan los `InventoryMovement`/`MaterialTransformation` de producción (§7.4). Anular el evento revierte sus efectos en cascade (bloquea con 400 si hay eventos posteriores dependientes). Endpoints en §12.1.6.

### 11.1.14 Maestros mínimos `Driver` y `Vehicle` [NUEVO]

El módulo 3 del doc cliente promete maestros de conductores y vehículos en Fase 1 (necesarios para `InboundOrder`, rutas de recolección y el flete BOG-BAQ; en Fase 2 los usa el móvil del conductor). Modelo mínimo — dos catálogos simples:

- `drivers`: `id`, `organization_id`, `name`, `document_id?`, `phone?`, `is_active`, timestamps.
- `vehicles`: `id`, `organization_id`, `plate`, `display_name?`, `vehicle_type?` (`camion \| montacargas \| otro`), `is_active`, timestamps.

CRUD estándar vía config (`/config/drivers`, `/config/vehicles`, permisos `materials.edit` reutilizado o config genérico). Los **hornos** NO necesitan maestro propio en Fase 1: el horno grande y el crisol están representados por sus cuentas `KgLedgerAccount` (`intra_horno`, `crisol`); si Fase 2 requiere múltiples hornos, se extiende ahí. Los auxiliares de gasto por máquina/vehículo (§9.3, `ExpenseAuxiliary` [PENDING-DESIGN]) pueden referenciar `vehicles` para no duplicar catálogo — se decide junto con §11.1.7.

## 11.2 Tablas modificadas [MODIFICADO]

Todos los cambios son aditivos y backwards-compatible (columnas nullable, defaults sensatos). Los tres clientes existentes no se ven afectados: nuevas columnas quedan en `NULL` y la lógica de servicio degrada gracilmente cuando el valor es `NULL`.

### 11.2.1 `MoneyMovement` +`warehouse_id` + 2 tipos nuevos de maquila interna [MODIFICADO, extiende decision #39]

Dos extensiones a `MoneyMovement`:

**(a) Dos tipos nuevos de movimiento (v0.5)**: `internal_maquila_expense` e `internal_maquila_income` — el catálogo pasa de 21 a 23 tipos. Ambos con `account_id=NULL` (patrón `expense_accrual`, [decision #14]) y `third_party_id=NULL`; siempre emitidos en **par enlazado** reutilizando el mecanismo de linked pair de los transfers (`linked_movement_id`). Auto-creados por la confirmación del traslado intersede (momento 1, $1.500/kg) y por `CrucibleDischarge` (momento 2, $300/kg) — ver §5.2. Regla de reportes: el **P&L consolidado los EXCLUYE por filtro de tipo** (se netean a cero, mismo NIT); el P&L por sede los incluye (CV gasto / JM ingreso). Anulación en cascade del par ([decision #48]).

**(b) Columna `warehouse_id`**: se agrega nullable como **dimensión gerencial persistida** — no derivada. Confirmado por Daniel (sesión 2026-06-30) como decisión cerrada.

**(c) Columnas de trazabilidad de causaciones automáticas (v0.5)**: los MMs auto-creados (pares de maquila §5.2, `service_income` Willard §6.1, flete mensual §6.2) persisten su origen y tarifa — sin esto el drill-down de §12.1.4 y el JSON de ejemplo de §5.2 no tendrían soporte de datos:

```sql
ALTER TABLE money_movements
  ADD COLUMN warehouse_id UUID NULL REFERENCES warehouses(id) ON DELETE SET NULL,
  ADD COLUMN tariff_id UUID NULL REFERENCES service_tariffs(id) ON DELETE SET NULL,
  ADD COLUMN source_type VARCHAR(32) NULL,  -- 'transfer' | 'crucible_discharge' | 'sale' | 'willard_monthly_freight'
  ADD COLUMN source_id UUID NULL;           -- FK polimórfico al documento origen
CREATE INDEX ix_money_movements_org_warehouse ON money_movements(organization_id, warehouse_id);
CREATE INDEX ix_money_movements_source ON money_movements(source_type, source_id);
```

Las cuatro columnas son nullable — los movimientos manuales y los 3 clientes existentes quedan en NULL.

Semántica:

- `warehouse_id` es **ortogonal al 3-tier** ([decision #44]). Un gasto puede ser Directo a UN1 con `warehouse_id=CV`, o Compartido (UN1+UN2) con `warehouse_id=BOG`, o General con `warehouse_id=NULL` (corporativo).
- **No afecta balance del tercero** — el saldo unificado ([decision #16], [decision #55]) sigue siendo un escalar por `third_party_id`. `warehouse_id` es sólo dimensión de reporting.
- Retrocompatibilidad: los 3 clientes existentes tienen `warehouse_id=NULL` en todos sus movimientos actuales — no rompe reportes ni cache.
- `PATCH /money-movements/{id}/classification` ([decision #39]) se extiende para permitir editar `warehouse_id` post-registro.

Ver §9.2 para el modelo funcional y §13.2 para los formularios extendidos.

### 11.2.2 `Sale` — campos de remisión Willard (v0.5)

El flag booleano de "requiere causación de maquila al liquidar" previsto en v0.4 **se elimina junto con el modelo diferido** (§11.1.5): con causación al envío, la venta no dispara maquila. `Sale` SÍ gana dos columnas para las entregas a Willard — la **remisión** es el dato que decide qué cuenta kg se descarga (§4.3) y el detalle por entrega del acta semanal (fecha, remisión, kg — §10.2.5) necesita persistirla:

```sql
ALTER TABLE sales
  ADD COLUMN willard_remission_number VARCHAR(40) NULL,
  ADD COLUMN willard_target_account VARCHAR(16) NULL;  -- enum: baterias | drosses
```

Ambas nullable (solo pobladas en ventas-abono a Willard; obligatorias al liquidar una venta a Willard — validación de servicio). Además del `warehouse_id` en header (§7.6/§12.2.3). Al liquidar desde JM inserta el `KgLedgerMovement` de `intersede_discharge` (y `willard_delivery` contra la cuenta que indique `willard_target_account`).

### 11.2.3 `FixedAsset` `warehouse_id` [PENDING-DESIGN]

`FixedAsset` **ya tiene** `warehouse_id` en el modelo actual (revisar migración de FixedAssets original). Si el code review previo a implementación detecta que no existe, se agrega nullable con el mismo patrón que `MoneyMovement`. No requiere cambios de lógica: sólo alimenta el filtro de reportes por sede.

### 11.2.4 `InboundOrder` — ver §11.1.12 (tabla NUEVA, no modificada)

`InboundOrder` **no existe en EcoBalance** — es una tabla nueva de SAC (corrección v0.5: el v0.4 la listaba erróneamente como ALTER de tabla existente). Su schema completo, incluidos los campos Willard-specific (`willard_distribution_center` informativo §6.5, `willard_account_subtype` obligatorio para SEC §6.4, `goes_directly_to_jm` para drosses BOG→JM §7.3) está en §11.1.12; sus endpoints en §12.1.6. Numeral conservado como puntero para no renumerar.

### 11.2.5 `ExpenseCategory` seeds nuevos [MODIFICADO]

Ver §11.1.8. No hay cambio estructural — sólo `INSERT` de ocho filas `is_system_entity=TRUE` en la migración de seed SAC.

### 11.2.6 `MoneyAccount` +`warehouse_id` y `Membership` +`default_warehouse_id` [MODIFICADO, ajustado en v0.5]

**(a) `MoneyAccount` +`warehouse_id` (fuente de verdad de la sede en cajas menores — visita 2026-07-02).** Cada caja menor es una `MoneyAccount` tipo caja con sede propia; hay **una caja menor por sede** (`CV-CajaMenor`, `JM-CajaMenor`, `BOG-CajaMenor`), todas operadas por Yurani (§9.4). La caja de Green Loop (§7.3) también es una `MoneyAccount` tipo caja.

```sql
ALTER TABLE money_accounts ADD COLUMN warehouse_id UUID NULL
  REFERENCES warehouses(id) ON DELETE SET NULL;
```

Semántica:

- **El gasto hereda la sede de la CAJA usada**: al crear un `MoneyMovement` contra una cuenta con `warehouse_id`, el servicio puebla `MoneyMovement.warehouse_id` desde la cuenta (regla central de §9.4). El usuario puede sobreescribirlo solo en cuentas corporativas sin sede.
- Nullable y backwards-compatible: cuentas corporativas y los 3 clientes existentes quedan con `warehouse_id=NULL`.
- Reemplaza el parsing de prefijos de nombre (`CV-*`) como mecanismo — el naming queda como convención visual.

**(b) `Membership` +`default_warehouse_id` (degradado a conveniencia de UI en v0.5).**

```sql
ALTER TABLE memberships ADD COLUMN default_warehouse_id UUID NULL
  REFERENCES warehouses(id) ON DELETE SET NULL;
```

Semántica:

- Solo preselecciona sede/caja habitual en formularios. **NO es la fuente del `warehouse_id` en gastos de caja menor** — esa es la cuenta (punto a). Corrección respecto al v0.4, que lo usaba como fuente del filtrado de Yurani.
- El scope del rol `caja_menor` (§9.4, §14.2) se implementa por **cuentas asignadas** (las N cajas menores que Yurani administra), no por una sede única del usuario.
- Nullable, backwards-compatible, editable por admin (`users.manage`).

### 11.2.7 Cambios que NO se hacen

- **`Material.current_average_cost` NO se fragmenta por warehouse**. Sigue siendo ORG-WIDE ([decision #5]). Baterías húmedas multireferencia se resuelven a nivel de `PurchaseLine` con costo por referencia (ver §7.2), no de material duplicado.
- **`ThirdParty` NO se fragmenta por sede**. Willard es un solo `ThirdParty` con un solo `balance` en pesos ([decision #16]). Las cuentas kg son dimensión separada.
- **`Warehouse` no cambia estructuralmente**. Se siembran 3 warehouses físicos (CV, JM, BOG) más 3 virtuales (`CV-MOLINO`, `JM-TRANSITO`, `CV-TRANSITO`) al migrar la organización. `CV-TRANSITO` cubre la ruta BOG→CV (llegada física de baterías que mueve los sub-saldos Willard, §4.3 `willard_subbalance_move`) con la misma regla de tolerancia despachado/recibido de §7.5 — el transporte de ese tramo es tercerizado, lo que hace la doble cantidad aún más necesaria.

### 11.2.8 Parámetros de configuración SAC [NUEVO]

Columna aditiva `settings JSONB NULL` en `organizations` (NULL para los 3 clientes existentes). Claves SAC:

- `transfer_tolerance_pct` — tolerancia despachado vs recibido en traslados (default `0.05`, rango operativo 3–5%; Johana, visita 2026-07-02). La usan §5.1, §7.5 y el panel §10.3.
- `intersede_stale_days` — días sin movimiento para alertar saldo intersede huérfano (default `30`, §10.3).
- `aging_buckets` — cortes de antigüedad para cartera y deuda kg (default `[30, 60, 90]`, §10.1.1 y §10.4).

## 11.3 Modelos REUTILIZADOS sin cambios

La mayor parte del modelo funcional de SAC se logra reutilizando estructuras existentes tal cual. Enumeramos los reusos explícitamente para dejar claro el ratio construcción vs reuso.

| Modelo | Decisión de referencia | Uso en SAC |
|---|---|---|
| `Warehouse` | [decision #arquitectónica multi-sede] | 3 sedes físicas + 2 bodegas virtuales. |
| `BusinessUnit` | [decision #44] 3-tier expenses | 4 unidades de negocio ortogonales a sede. |
| `Purchase` (3-step workflow) | [decision #2], [decision #3] | Compras chatarra propia + postconsumo Willard. |
| `Sale` (2-step workflow) | [decision #2] | Ventas a Willard y otros. Gana 2 columnas de remisión Willard (`willard_remission_number`, `willard_target_account` — §11.2.2); al liquidar desde JM descarga la cuenta kg intersede (§7.6). |
| `DoubleEntry` | [decision #1] | Reventa Pasa Mano (UN3). |
| `MaterialTransformation` | [decision #17], [decision #53] | Molino (baterías → fragmentos), picado (fragmentos → scrap). Cambio de unidad soportado. |
| `InventoryMovement` | | Stock físico por warehouse. Per-warehouse stock on-the-fly. |
| `MaterialCostHistory` | [decision #9], [decision #41] | Reversal de costo promedio en anulaciones + snapshot histórico. |
| `PriceList` | [decision #35] | Lista de precios de venta append-only. Sirve de patrón para `MaterialConversionFormula` y `ServiceTariff`. |
| `ScheduledExpense` | [decision #13] | Sin uso especial en SAC v0.5 (el patrón commitment diferido que inspiraba quedó descartado — §5.2). Disponible para gastos diferidos estándar. |
| `ThirdParty` + `ThirdPartyCategory` | [decision #33] | Willard (**Cliente + Proveedor Servicios + Pasivo** — `customer` es obligatorio porque las entregas de plomo se modelan como `Sale` a Willard y la validación de decisión #32 exige behavior_type `customer` en el cliente de una venta; sin él, `Sale.liquidate` fallaría y la CxC Willard quedaría mal clasificada en el Balance Detallado), Green Loop (service_provider), proveedores chatarra (material_supplier), socios (investor), Eco Alloys/Panamá/Prosperidad (generic). |
| `PurchaseCommission` | [decision #30] | **v0.6: ya NO se usa para Green Loop.** Su comisión pasó a gasto causado (`expense_accrual`, [decision #83], §7.3 punto 5). `PurchaseCommission` sigue disponible para comisiones y cargos que sí deban engordar el costo del material (fletes de compra, [decision #70]). |
| `MoneyMovement` (extendido) | [decision #39], [decision #44] | Todos los movimientos financieros. Extiende con `warehouse_id`. |
| `Roles`, `Permissions`, `Membership` | [decision #25], [decision #26] | RBAC completo. Se agregan 15 permisos nuevos SAC (ver §14.1). |
| `ProfitDistribution` | [decision #34], [decision #48] | Repartición a socios. Aplica a SAC como cualquier org. |

## 11.4 Relación con decisiones existentes

Mapa exhaustivo de qué decisiones aplican, cuáles se extienden y cuáles no aplican a SAC.

| Decisión | Aplicación en SAC |
|---|---|
| #1 Doble Partida sin inventario | Aplica sin cambios (UN3 Reventa DP). |
| #2 Estados uniformes | Aplica sin cambios (Compra/Venta/DP en SAC). |
| #3 Stock transit/liquidated | Aplica sin cambios. |
| #5 Costo promedio único ORG-WIDE | **Preservada como invariante crítica**. Baterías húmedas multireferencia no la rompen — se resuelven a nivel `PurchaseLine`. |
| #8 Edición revert-and-reapply | Aplica sin cambios a compras/ventas SAC. |
| #9 Reversal costo con `MaterialCostHistory` | Aplica sin cambios. |
| #13 `ScheduledExpense` | Aplica solo como módulo estándar de gastos diferidos (el patrón commitment que inspiraba en v0.4 quedó descartado en v0.5). |
| #14 `expense_accrual` sin cuenta | **Aplicación crítica**: los tipos `internal_maquila_expense`/`internal_maquila_income` heredan el patrón "sin cuenta" (`account_id=NULL`) y sin tercero. NO se crea tercero intercompany ficticio. |
| #16 Estado de cuenta unificado del tercero | Aplica sin cambios. Willard tiene UN SOLO balance en pesos aunque tenga 2 cuentas kg (dimensión separada). |
| #17 Transformaciones de material | Aplica. Fundición y crisol modelan `MaterialTransformation` cuando cambia composición; `FurnaceCharge`/`CrucibleCharge` son eventos KgLedger distintos que sólo mueven kg (ver §7.4). |
| #23 Comisión causada (`commission_accrual`) | Conceptualmente aplica — el patrón "accrual sin cuenta" es genérico e inspira los tipos internos de maquila. No se usa `commission_accrual` literal (SAC no tiene comisiones por kg de venta). |
| #25 RBAC backend | Aplica sin cambios. 15 permisos nuevos (§14.1). |
| #26 RBAC frontend + admin UI | Aplica. Sidebar filtering, `PermissionGate`. |
| #28 Skill `/migrate-client` | **Extendida** con 3 hojas Excel SAC-specific y validaciones adicionales (ver §15.3–§15.4). |
| #34 `ProfitDistribution` | Aplica. Política "utilidad cero JM/BOG" es gerencial, no contable — no bloquea repartición a socios. |
| #35 `PriceList` append-only | Patrón replicado en `MaterialConversionFormula` y `ServiceTariff`. |
| #36 Subcategorías max 2 niveles | Preservada. Auxiliar de tercer nivel resuelto vía `ExpenseAuxiliary` o reuso de `BusinessUnit` [PENDING-DESIGN]. |
| #39 Editar clasificación de gastos | **Extendida** para permitir editar `warehouse_id`. Impacta reportes por sede. |
| #41 Balance histórico `as_of_date` + snapshot patrón | Patrón replicado en `KgLedgerMovement.conversion_formula_snapshot` y en el reporte kg-balance histórico (§10.2.1). |
| #44 Reporte de gastos 3-tier | **Extendida** con `warehouse_id` como dimensión adicional de agrupación. Ortogonal al 3-tier. |
| #46 Carga histórica `historical_load` en `FixedAsset` | Aplica sin cambios en migración inicial SAC. |
| #48 Anulación de `ProfitDistribution` | Aplica. Precedente para anulación de `KgLedgerMovement` (`status='annulled'` + cascade). |
| #49 Drill-down P&L | Se extiende con filtro `warehouse_id` en las páginas destino. |
| #50 P&L mensual | Aplica sin cambios. Extendido con `warehouse_id` opcional (§10.2). |
| #52 Excel operaciones con hoja Detalle | Aplica sin cambios a compras/ventas SAC. |
| #53 Transformaciones con cambio de unidad | Aplica a fundición (kg aportante → kg plomo, diferente material). |
| #55 Fix Saldo Inicial estado de cuenta | Aplica sin cambios (relevante en migración SAC donde muchos terceros arrancan con `initial_balance != 0`). |
| #18 `received_quantity` | No aplica en SAC (formato de báscula distinto). |
| #30 `PurchaseCommission` | **v0.6: NO aplica a Green Loop.** Su comisión se causa como gasto ([decision #83], §7.3 punto 5) — v0.5 decía que se prorrateaba al costo y quedó obsoleto. #30 sigue vigente para cargos que sí van al costo (fletes de compra, [decision #70]). Comerciales internos siguen sin comisión (nómina fija, §8). |

---

# 12. Endpoints

Se catalogan los endpoints nuevos y los endpoints existentes que ganan parámetros nuevos. Todos respetan el patrón `api/v1/<module>/`, DI via `get_db()` + `get_required_org_context()`, permission-gated con `require_permission()` o `require_any_permission()`, y cache invalidation vía `queryInvalidation.ts` ([decision #27]).

## 12.1 Endpoints nuevos [NUEVO]

### 12.1.1 KgLedger — CRUD y estado de cuenta

**`GET /api/v1/kg-ledger/accounts`** — lista cuentas KgLedger de la organización.

- Query params: `account_type?` (filtro enum), `is_active?` (default `TRUE`).
- Response: `list[KgLedgerAccountResponse]` con `id`, `code`, `display_name`, `account_type`, `warehouse_id`, `third_party_id`, `current_balance_kg` (calculado on-the-fly), `is_active`.
- Permiso: `kg_ledger.view`.
- Side-effects: ninguno.

**`POST /api/v1/kg-ledger/accounts`** — crea cuenta KgLedger.

- Request body: `KgLedgerAccountCreate { code, display_name, account_type, warehouse_id?, third_party_id? }`.
- Response: `KgLedgerAccountResponse` (201).
- Permiso: `kg_ledger.manage`.
- Side-effects: inserta fila. Invalida cache `["kg-ledger", "accounts"]`.

**`PATCH /api/v1/kg-ledger/accounts/{id}`** — edita metadata (nombre, `is_active`).

- Request body: `KgLedgerAccountUpdate { display_name?, is_active? }`. `account_type` y FKs inmutables post-creación.
- Response: `KgLedgerAccountResponse`.
- Permiso: `kg_ledger.manage`.

**`GET /api/v1/kg-ledger/accounts/{id}/movements`** — estado de cuenta con saldo corrido.

- Query params: `date_from?` (default últimos 90 días), `date_to?`, `status?` (default `confirmed`).
- Response: `KgLedgerStatementResponse { account, opening_balance_kg, movements: [{...KgLedgerMovementResponse, balance_after_kg}], current_balance_kg }`.
- Permiso: `kg_ledger.view`.
- Análogo a `GET /money-movements/third-party/{id}` ([decision #16], [decision #55]).

**`GET /api/v1/kg-ledger/summary`** — snapshot consolidado de las 5 cuentas kg.

- Query params: `as_of_date?` (opcional, patrón [decision #41]).
- Response: `KgLedgerSummary { accounts: [{account_id, account_type, display_name, balance_kg}], total_willard_kg, total_intersede_kg, total_intra_horno_kg, total_crisol_kg }`.
- Permiso: `kg_ledger.view`.

**`POST /api/v1/kg-ledger/movements`** — movimiento manual (ajuste auditado).

- Request body: `KgLedgerMovementManualCreate { account_id, delta_kg, transaction_date, description, reason }`.
- Response: `KgLedgerMovementResponse` (201).
- Permiso: `kg_ledger.manage_adjustments` (solo admin/Johana).
- Side-effects: inserta `KgLedgerMovement` con `source_type='manual_adjustment'`. Invalida `["kg-ledger", "accounts", account_id, "movements"]`, `["kg-ledger", "summary"]`.

**`POST /api/v1/kg-ledger/movements/{id}/annul`** — anula movimiento (soft).

- Request body: `{ reason }`.
- Response: `KgLedgerMovementResponse`.
- Permiso: `kg_ledger.manage_adjustments`.
- Side-effects: `status='annulled'`, campos `annulled_*` poblados. Recalcula saldo excluyendo anulados.

### 12.1.2 `MaterialConversionFormula`

**`GET /api/v1/material-conversion-formulas`** — lista todas las fórmulas (histórico completo).

- Query params: `material_id?`, `formula_type?`, `willard_account_subtype?`.
- Response: `list[MaterialConversionFormulaResponse]`.
- Permiso: `formulas.view`.

**`GET /api/v1/material-conversion-formulas/current`** — sólo vigentes.

- Query params: `material_id?`.
- Response: `list[MaterialConversionFormulaResponse]` filtrado a `max(created_at)` por `(material_id, willard_account_subtype)`.
- Permiso: `formulas.view`.

**`POST /api/v1/material-conversion-formulas`** — crea nueva fórmula (append-only).

- Request body: `MaterialConversionFormulaCreate { material_id, formula_type, parameters, willard_account_subtype?, notes? }`.
- Response: `MaterialConversionFormulaResponse` (201).
- Permiso: `formulas.manage`.
- Side-effects: nueva fila. La anterior queda como histórico. Invalida `["formulas", "current"]`.
- Validación: `parameters` debe cumplir el JSON schema según `formula_type` (ver Anexo D).

**Nota**: no hay `PATCH` ni `DELETE` — append-only estricto.

### 12.1.3 `ServiceTariff`

**`GET /api/v1/service-tariffs`** — histórico completo.

- Query params: `tariff_code?`.
- Response: `list[ServiceTariffResponse]`.
- Permiso: `tariffs.view`.

**`GET /api/v1/service-tariffs/current`** — vigentes hoy.

- Response: `list[ServiceTariffResponse]` con las 5 tarifas SAC (maquila Willard, maquila intersede, crisol, flete BOG-BAQ, flete planta-planta).
- Permiso: `tariffs.view`.

**`POST /api/v1/service-tariffs`** — crea nueva tarifa (append-only).

- Request body: `ServiceTariffCreate { tariff_code, unit_price_cop, unit, notes? }`.
- Response: `ServiceTariffResponse` (201).
- Permiso: `tariffs.manage`.
- Side-effects: nueva fila. Invalida `["tariffs", "current"]`.

### 12.1.4 Maquila interna — consulta del par enlazado (v0.5)

Los endpoints de commitments del v0.4 se eliminan junto con el modelo diferido (§11.1.5). La maquila interna no tiene endpoints de escritura propios: **los pares se auto-crean** con la confirmación del traslado CV→JM (§12.2.4) y con el cierre de refinación del crisol, y **se anulan** anulando el documento origen (cascade del par). Para consulta:

**`GET /api/v1/money-movements?movement_type=internal_maquila_expense,internal_maquila_income`** — lista los movimientos de maquila interna (reutiliza el filtro CSV de tipos existente, [decision #49]).

- Query params adicionales: `warehouse_id?`, `date_from?`, `date_to?`, `expense_category_id?` (Maquila Intersede / Crisol Refinación).
- Response: `list[MoneyMovementResponse]` — cada uno con `linked_movement_id` para navegar al otro lado del par y `source_id` para llegar al `Transfer` o cierre de crisol origen.
- Permiso: `maquila.view` OR `treasury.view`.

**Reporte agregado**: `GET /api/v1/reports/internal-maquila` (ver §12.1.5 y §10.2.2).

### 12.1.5 Reportes nuevos

**`GET /api/v1/reports/kg-balance`** — dashboard 5 saldos kg.

- Query params: `as_of_date?` (patrón [decision #41]).
- Response: `KgBalanceReport { as_of_date, accounts: [...], willard_by_center: [...] }` incluye desglose informativo por centro de distribución Willard.
- Permiso: `kg_ledger.view` OR `reports.view`.

**`GET /api/v1/reports/internal-maquila`** — maquila interna causada por periodo (§10.2.2).

- Query params: `date_from`, `date_to`, `concept?` (`horno | crisol`), `from_warehouse_id?`.
- Response: `InternalMaquilaReport { items: [{date, concept, from_warehouse, source_type, source_id, kg_base, tariff_cop, amount, status}], totals_by_concept, total }` — gasto de sedes origen = ingreso de JM (simetría del par).
- Permiso: `maquila.view` OR `reports.view`.

**`GET /api/v1/reports/willard-weekly-reconciliation`** — cuadre semanal. **Contrato canónico** (las menciones de §4.5 y §10.2.5 refieren aquí):

- Query params: `week_ending` (obligatorio, **viernes de cierre** de la semana — coherente con `KgLedgerReconciliationSeal.week_ending_date`).
- Response: `WillardWeeklyReconciliation` con los 5 bloques del acta (§10.2.5):
  - `baterias: { opening_kg, closing_kg, sub_balances: [{warehouse, opening_kg, closing_kg}], subbalance_moves: [...], inflows: [...], outflows: [...] }` — sub-saldos BAQ/BOG (Bloque 1).
  - `drosses: { opening_kg, closing_kg, inflows: [...], outflows: [...] }` (Bloque 2).
  - `deliveries: [{date, remission_number, kg, account}]` — **detalle por entrega** (Bloque 3; `Sale.willard_remission_number`/`willard_target_account`, §11.2.2).
  - `invoiced: { maquila_per_delivery: [...], flete_planta_per_delivery: [...], flete_bog_baq_month_accumulated }` (Bloque 4).
  - `discrepancies: [...]` (Bloque 5).
- Permiso: `willard.reconcile`.
- `POST /api/v1/kg-ledger/reconciliation-seals` — firma el "OK del viernes": valida la semana, emite el `KgLedgerReconciliationSeal` (§11.1.9) por cuenta. Permiso `willard.reconcile`.

**`GET /api/v1/reports/receivables-aging`** y **`GET /api/v1/reports/payables-aging`** — antigüedad de cartera CxC/CxP (§10.1.1): buckets configurables (`aging_buckets`, §11.2.8), agrupado por tercero, asignación FIFO de abonos contra cargos más antiguos. Permiso `reports.view`. Aplican a todos los clientes EcoBalance.

**`GET /api/v1/reports/factors-tariffs-history`** — histórico de factores y tarifas (§10.1.1): vista de lectura sobre `MaterialConversionFormula` + `ServiceTariff` con vigencias, valores, aprobador y notas. Permiso `kg_ledger.view` OR `reports.view`.

### 12.1.6 Captura y planta (InboundOrder, traslados en dos pasos, horno y crisol) [NUEVO]

- **`POST /api/v1/inbound-orders`** — crea la orden de entrada (captura única, §11.1.12). Efectos al confirmar según `inbound_type`: inventario, `KgLedgerMovement` postconsumo/drosses, `Purchase(registered)` asociado. Permiso `purchases.create`. `POST /{id}/annul` revierte en cascade (bloquea si hay eventos posteriores).
- **`POST /api/v1/transfers`** — paso A (despacho): inventario origen → bodega de tránsito. Sin efectos kg ni pesos (§7.5). Permiso `inventory.transfer`.
- **`POST /api/v1/transfers/{id}/receive`** — paso B (recepción confirmada): registra `quantity_received`; dentro de tolerancia emite atómicamente los 3 efectos (§7.5): inventario a bodega destino, `intersede_send` sobre kg recibidos y par de maquila (solo si el material es aportante — existe `MaterialConversionFormula` vigente, §5.1). Fuera de tolerancia: crea `DiscrepancyTask` y retiene efectos. En la ruta BOG→CV de baterías Willard dispara `willard_subbalance_move` (sin par de maquila). Permiso `inventory.transfer`.
- **`POST /api/v1/furnace-charges` / `POST /api/v1/furnace-discharges`** — carga y descargo (agregado en Fase 1) del horno grande (§11.1.13): mueven la cuenta kg `intra_horno` y, en el discharge, generan la producción de plomo crudo. Permiso `inventory.transform`.
- **`POST /api/v1/crucible-charges` / `POST /api/v1/crucible-discharges`** — carga y cierre del crisol: mueven la cuenta kg `crisol`; el discharge produce plomo puro y **auto-crea el par de maquila del crisol** ($300/kg, §5.1 momento 2). Permiso `inventory.transform`.
- Cada evento tiene su `POST /{id}/annul` con reverso en cascade de sus efectos (400 si hay dependientes posteriores).

### 12.1.7 Panel de excepciones [NUEVO]

Catálogo completo en §10.3: `GET /api/v1/exceptions` (permiso `exceptions.view`), `POST /api/v1/exceptions/{id}/justify` / `/correct` / `/request-count` (permiso `exceptions.resolve`), `POST /api/v1/exceptions/daily-ok` (permiso `exceptions.sign_daily`, emite `DailyOkSeal` §11.1.11).

### 12.1.8 Facturación mensual flete BOG-BAQ [NUEVO]

**`POST /api/v1/willard/monthly-freight-invoices`** — `period=YYYY-MM` (§6.2): suma kg físicos de batería de los `Transfer` BOG→CV confirmados del periodo, aplica tarifa vigente `flete_willard_bog_baq` ($216/kg) y emite el `service_income` mensual (`account_id=NULL`, CxC Willard). Idempotente por periodo (409 si ya existe confirmado); anulable con cascade. `GET` de consulta por periodo. Permiso `treasury.create` + `willard.reconcile`.

## 12.2 Endpoints modificados [MODIFICADO]

### 12.2.1 `MoneyMovement` con `warehouse_id`

**`POST /api/v1/money-movements`** — request body extendido:

```python
class MoneyMovementCreate(BaseModel):
    # ... campos existentes
    warehouse_id: Optional[UUID] = None  # NUEVO — dimensión gerencial
```

Semántica (regla central v0.5, §9.2/§11.2.6): si la `MoneyAccount` usada tiene `warehouse_id` (cajas menores, caja Green Loop), **el servicio puebla `MoneyMovement.warehouse_id` desde la cuenta — no sobreescribible**. Solo en cuentas corporativas sin sede aplica el autofill con la "sede default" del usuario (conveniencia de UI). `NULL` mapea a bucket "Corporativo" en reportes.

**`GET /api/v1/money-movements`** — query params extendidos:

- `warehouse_id?` (CSV, para multi-select): `?warehouse_id=cv-uuid,jm-uuid`.
- Sin efecto en balance del tercero.

**`GET /api/v1/money-movements/third-party/{id}`** — query param extendido:

- `warehouse_id?` (opcional, filtro READ-ONLY, NO afecta balance del tercero — [decision #16], [decision #55] preservada).
- Response incluye filas filtradas pero `current_balance` sigue siendo el saldo total unificado del tercero.

**`PATCH /api/v1/money-movements/{id}/classification`** — extendida ([decision #39]):

```python
class MoneyMovementClassificationUpdate(BaseModel):
    expense_category_id: Optional[UUID] = None
    business_unit_id: Optional[UUID] = None
    applicable_business_unit_ids: Optional[list[UUID]] = None
    warehouse_id: Optional[UUID] = None  # NUEVO
```

- Permiso existente `treasury.edit_classification`.
- Side-effects: invalida reportes (`invalidateAfterTreasury`). No modifica balance.

### 12.2.2 Reportes con `warehouse_id`

**`GET /api/v1/reports/profit-and-loss`** — query params extendidos:

- `warehouse_id?` (opcional, filtro).
- `include_internal_maquila?` (boolean): controla la inclusión de los tipos `internal_maquila_expense`/`internal_maquila_income` (ver §3.5, §5.2). Default automático: **excluidos** en consolidado (sin `warehouse_id`), **incluidos** cuando `warehouse_id` está seteado. El flag permite forzar la vista bruta del consolidado para auditoría.
- Permiso: `reports.view` OR `reports.view_pnl`.

**`GET /api/v1/reports/profit-and-loss/monthly`** — extiende [decision #50]:

- Nuevo query param `warehouse_id?`.
- Preserva `cutoff_day`, `date_from`, `date_to`.
- El cap defensivo de 24 meses se mantiene.

**`GET /api/v1/reports/expenses`** y **`/reports/expenses/detail`** — extienden [decision #44]:

- `group_by` acepta valores adicionales: `warehouse | bu_then_warehouse | warehouse_then_bu | category_then_warehouse | warehouse_then_category`.
- Filtro `warehouse_id[]` (multi-select).
- Filtro `warehouse_unassigned?` (boolean) para drill-down al bucket "Corporativo" (`warehouse_id IS NULL`).
- Permiso existente: `reports.view_expenses`.

**`GET /api/v1/reports/cash-flow`** — query param:

- `warehouse_id?` (filtra `MoneyMovement` y liquidaciones de compra/venta por `warehouse_id`).

### 12.2.3 Operaciones con `warehouse_id` inmutable

**`POST /api/v1/purchases`** — header acepta `warehouse_id` (sede de recepción física).

- Request body: `PurchaseCreate { ..., warehouse_id: UUID }` — obligatorio para SAC.
- Response: incluye `warehouse_id`.
- **Inmutable post-registro**: `PATCH /purchases/{id}` rechaza cambios a `warehouse_id`. Si operativa requiere cambiar sede, se anula y se re-crea.

**`POST /api/v1/sales`** — análogo.

- `warehouse_id` en header (sede desde donde se despacha), inmutable post-registro.

**`POST /api/v1/double-entries`** — `warehouse_id` opcional (clasificación gerencial).

### 12.2.4 Traslados disparan KgLedger + par de maquila interna (causación al envío)

**`POST /api/v1/transfers`** (paso A — despacho) y **`POST /api/v1/transfers/{id}/receive`** (paso B — recepción) — ver contrato en §12.1.6 y modelo en §7.5:

- El **despacho** solo mueve inventario a la bodega de tránsito — sin efectos kg ni pesos.
- La **recepción confirmada** de un `Transfer` con `from_warehouse_id ∈ {CV, BOG}`, `to_warehouse_id=JM` y **material aportante** (criterio: existe `MaterialConversionFormula` vigente para el material, §5.1) dispara atómicamente, sobre los **kg recibidos**:
  1. `InventoryMovement` tránsito → bodega JM (tolerancia 3–5%, lo recibido manda — §7.5; fuera de tolerancia: `DiscrepancyTask` y efectos retenidos).
  2. `KgLedgerMovement` de tipo `intersede_send`, `+delta_kg` en cuenta Intersede, con `conversion_formula_snapshot` populado.
  3. **Par enlazado** `internal_maquila_expense` (CV/BOG) + `internal_maquila_income` (JM) con la tarifa vigente `maquila_intersede_cv_jm` ($1.500/kg de plomo equivalente) — §5.2, con `tariff_id`/`source_type='transfer'`/`source_id` persistidos (§11.2.1c).
- La recepción de la ruta BOG→CV de baterías Willard dispara en cambio el `willard_subbalance_move` (par de sub-saldos Willard Baterías, §4.3) — sin par de maquila.
- Al anular `Transfer`, los efectos se revierten (par anulado en cascade). Falla con 400 si el material ya fue cargado al horno o vendido.

**Cierre de refinación (`CrucibleDischarge`)** — comportamiento análogo: descarga la cuenta kg Crisol, ingresa plomo refinado a inventario y auto-crea el **par de maquila del crisol** ($300/kg de plomo puro producido, tarifa vigente `maquila_crisol`). Anular el cierre anula el par.

### 12.2.5 Liquidación de venta: descarga de cuenta kg intersede (SIN causación de maquila)

**`POST /api/v1/sales/{id}/liquidate`** — comportamiento extendido:

- Después de la liquidación estándar (precios, balance cliente, costo promedio), si la venta despacha plomo procesado desde JM, el servicio inserta:
  1. `KgLedgerMovement` de tipo `intersede_discharge` (`delta_kg` negativo, descarga los kg pendientes más antiguos de la cuenta Intersede).
  2. `KgLedgerMovement` de tipo `willard_delivery` si la venta es un abono a Willard — descargando la cuenta (baterías o drosses) que indique la **remisión** de la entrega.
  3. Los `service_income` de maquila Willard ($2.097/kg) y flete planta ($37/kg) — facturados **por cada entrega**, con `account_id=NULL` (causación de CxC Willard, §6.1; el cobro llega como `collection_from_client` separado).
- La venta a Willard exige `willard_remission_number` y `willard_target_account` al liquidar (§11.2.2) — la remisión decide qué cuenta kg descarga el `willard_delivery`.
- **La liquidación NO causa maquila intersede** — se causó al confirmar el envío CV→JM y al salir del crisol (modelo v0.5, visita 2026-07-02; ver §5). Cero movimientos `internal_maquila_*` en este endpoint.
- **Anulación**: anular la venta revierte en cascade los tres ítems — `intersede_discharge`, `willard_delivery` y los `service_income` de maquila/flete (§7.6, test `test_willard_sale_annulment_reverts_service_incomes`).
- Ver §5.3 para el detalle contable del par y §7.6 para los casos que no mueven la cuenta intersede.

Side-effects globales de todos los endpoints modificados: invalidan caches vía `invalidateAfterTreasury`, `invalidateAfterSaleLiquidateOrCancel`, `invalidateAfterPurchaseLiquidateOrCancel` según corresponda (ver [decision #27]).

---

# 13. Frontend

Toda UI nueva y toda extensión a UI existente debe cumplir la regla mobile-first de CLAUDE.md (390px iPhone 12+). Los patrones de responsive (dual render, `FormLineGrid`, sticky bottom, tabs overflow) se reutilizan sin excepciones — no se construyen patrones nuevos si no son estrictamente necesarios.

## 13.1 Módulos NUEVOS en sidebar [NUEVO]

Cinco módulos aparecen en el sidebar para usuarios SAC con los permisos correspondientes. La `PermissionGate` filtra automáticamente por `organization_id` y por permiso, de modo que los 3 clientes existentes no ven estas secciones.

| Módulo sidebar | Ruta | Permiso mínimo | Descripción |
|---|---|---|---|
| Plomo (kg) | `/kg-ledger` | `kg_ledger.view` | Dashboard 5 cuentas kg (Willard Baterías con desglose de sub-saldos por sede), estados de cuenta detallados, botón "Movimiento manual" (si `kg_ledger.manage_adjustments`). |
| Tarifas | `/config/tariffs` | `tariffs.view` | CRUD append-only `ServiceTariff`. Lista histórica + botón "Nueva tarifa" (si `tariffs.manage`). |
| Fórmulas Conversión | `/config/formulas` | `formulas.view` | CRUD append-only `MaterialConversionFormula`. Filtro por material. Vista `parameters` como JSON legible. |
| Maquila Interna | `/maquila/internal` | `maquila.view` | Maquila interna causada por periodo (§10.2.2), con drill-down al Transfer o cierre de crisol origen y al par de MMs enlazado. Filtros por concepto (horno/crisol), sede origen y fechas. |
| Panel de Excepciones | `/exceptions` | `exceptions.view` | Excepciones y alarmas del día (vacío en un día normal), botón "OK del día" (permiso `exceptions.sign_daily`, típicamente Johana). Módulo detallado en §10.3. |

Sub-módulo bajo "Reportes":

- **Cuadre Semanal Willard** (`/reports/willard-weekly`, permiso `willard.reconcile`).
- **Balance KgLedger** (`/reports/kg-balance`, permiso `kg_ledger.view`).

Todos los módulos siguen `sidebar filtering` ([decision #26]) — si el usuario no tiene el permiso, la entrada del sidebar no se renderiza.

### 13.1.1 Componentes shared nuevos

- **`<KgLedgerCard>`**: card para vista mobile del dashboard 5 cuentas. Muestra `display_name`, `current_balance_kg` con formato `#,##0.####`, badge de estado (positivo verde / negativo rojo / cero gris), y link `/kg-ledger/accounts/{id}/movements`. Sigue patrón `<OperationListCard>` mobile.
- **`<InternalMaquilaCard>`**: card mobile para la lista de maquila interna del periodo — fecha, concepto (horno/crisol), origen→JM, kg base, monto, link al par enlazado.
- **`<ExceptionTaskCard>`**: card mobile para las tareas del panel de excepciones — tipo, severidad (badge por color), monto/kg involucrado, sede, acciones justificar/corregir/arqueo.
- **`<WarehouseSelector>`**: componente reutilizable. `<Select>` con opciones filtradas por permisos del usuario. Prop `allowNull` para incluir opción "Corporativo / Sin asignar" (usada en `MoneyMovement`).
- **`<KgFormat>`**: helper de formato `Intl.NumberFormat` con 4 decimales + sufijo " kg".

## 13.2 Formularios extendidos con selector `warehouse` [MODIFICADO]

Los siguientes formularios ganan un campo `<WarehouseSelector>`. En operaciones (Compra/Venta) el campo es **inmutable post-registro** (deshabilitado en el modo edit).

| Formulario | Campo agregado | Ubicación en form | Comportamiento |
|---|---|---|---|
| `MoneyMovementCreate` / `Edit` | `warehouse_id` (opcional) | Después de `account_id`, antes de `business_unit_id`. | Si la cuenta seleccionada tiene `warehouse_id` (cajas menores, caja Green Loop), el selector se **bloquea a la sede de la cuenta** (§9.4, §11.2.6). En cuentas corporativas: autofill con la "sede default" del usuario; permite `NULL` = Corporativo. |
| `PurchaseCreate` | `warehouse_id` (obligatorio en SAC) | Header de la compra, junto a `date` y `supplier_id`. | Inmutable en `PurchaseEdit` (deshabilitado con tooltip). |
| `SaleCreate` | `warehouse_id` (obligatorio en SAC) | Header, junto a `date` y `customer_id`. | Inmutable en `SaleEdit`. |
| `DoubleEntryCreate` / `Edit` | `warehouse_id` (opcional) | Header. | Editable — es clasificación gerencial pura. |
| `FixedAssetCreate` / `Edit` | `warehouse_id` (opcional) | Después de `expense_category_id`. | Editable (traslado de activo entre sedes). |
| Modal "Editar Clasificación" ([decision #39]) | `warehouse_id` | Después de `expense_category_id`. | Editable con permiso `treasury.edit_classification`. |
| `InboundOrderCreate` | `willard_distribution_center`, `willard_account_subtype`, `goes_directly_to_jm` | Sección "Detalle Willard" (colapsable) | Condicional: sólo si el proveedor es Willard. `willard_account_subtype` obligatorio si el material tiene 2 cuentas. |

En mobile, los selectores nuevos usan `w-full`. El header de Compra/Venta usa `<FormLineGrid>` con `md:col-span-4` para `warehouse_id` (fila con `date`, `supplier_id`, `warehouse_id`).

### 13.2.1 Wizard "Transferencia Intersede"

Ruta: `/transfers/new/intersede`. Simplifica la operación crítica CV→JM en 3 pasos guiados:

1. **Origen y material**: selección de `from_warehouse_id` (CV o BOG), `to_warehouse_id` (JM, autocompleta), material, cantidad física, unidad.
2. **Preview de efectos**: muestra cálculo automático de `delta_kg` en Intersede (aplica `MaterialConversionFormula` vigente), tarifa `maquila_intersede_cv_jm` vigente, y el **monto del par de maquila interna que se causará al confirmar** (gasto CV / ingreso JM). Incluye campos de cantidad despachada y (al recibir) cantidad recibida con indicador de tolerancia 3–5%.
3. **Confirmación de despacho**: dispara `POST /transfers` (paso A — inventario a tránsito). La pantalla **"Recibir"** (paso B, accesible desde la lista de traslados pendientes) registra la cantidad recibida con indicador de tolerancia y dispara `POST /transfers/{id}/receive`, que emite los 3 efectos atómicos (§12.2.4).

Ventaja UX: el usuario ve el efecto en KgLedger + el par de maquila interna antes de confirmar. Reduce errores de captura.

## 13.3 Filtros `warehouse` en reportes [MODIFICADO]

Patrón unificado siguiendo [decision #50] (URL params override sobre store de fechas):

- Cada página destino de drill-down (`SalesPage`, `TreasuryPage`, `DoubleEntriesPage`, `AdjustmentsPage`, `TransformationsPage`, `MoneyMovementsPage`) lee `?warehouse_id=` de URL.
- `<WarehouseFilter>` (Select con opción "Todas las sedes" + una por warehouse + "Corporativo") persiste en URL params.
- Badge visual "Sede: X `[×]`" (color indigo, patrón consistente con "Rango: X – Y") cuando hay filtro activo.
- Al limpiar el filtro (`×` en el badge), remueve el URL param.

Páginas afectadas:

| Página | Filtro `warehouse_id` |
|---|---|
| `ProfitAndLossPeriodView` (tab Periodo) | `?warehouse_id=` + toggle `include_internal_maquila` (default: excluido en consolidado, incluido por sede — §12.2.2). |
| `ProfitAndLossMonthlyView` (tab Mensual, [decision #50]) | `?warehouse_id=` propagado a cada mes. |
| `ExpensesReportPage` ([decision #44]) | `?warehouse_id=` + nueva opción en `group_by`. |
| `CashFlowPage` ([decision #7]) | `?warehouse_id=`. |
| `MoneyMovementsPage` (lista) | `?warehouse_id=` CSV multi-select. |
| `TreasuryPage` (tabs) | `?warehouse_id=` propagado entre tabs. |
| `BalanceDetailedPage` | Se mantiene sin filtro warehouse (balance es org-wide por diseño); sub-agrupaciones ya cubiertas por [decision #38]. |

Excel export replica los filtros ([decision #51] paridad web/Excel).

## 13.4 Verificación mobile responsive [OBLIGATORIO]

Antes de merge, cada UI nueva debe pasar verificación explícita:

1. **DevTools mobile mode (iPhone 12, 390×844)**:
   - Dashboard `/kg-ledger`: 5 KpiCards en `grid-cols-1 sm:grid-cols-2 md:grid-cols-5`. `<KgLedgerCard>` mobile cuando el grid apretaría.
   - `/maquila/internal`: dual render `<Table>` desktop + `<InternalMaquilaCard>` mobile. `/exceptions`: cards `<ExceptionTaskCard>` mobile + sticky "OK del día".
   - Wizard Transferencia Intersede: `<FormLineGrid>` con `md:col-span-*`, sticky bottom para "Siguiente"/"Confirmar".
   - `<WarehouseSelector>` en formularios: `w-full sm:w-auto`.
2. **Tablas anchas** (histórico de `KgLedgerMovement` con 8 columnas): overflow wrapper `-mx-3 sm:mx-0` + `Table min-w-[720px]`.
3. **Dialogs**: sin `max-w-md` (rompe mobile). Reutilizar shadcn base.
4. **Rotación portrait↔landscape**: los drawers de filtro no deben quedar colgados.

El estándar es cero regresión visual en desktop 1280px + usabilidad completa en 390px.

---

# 14. Permisos RBAC (nuevos permisos SAC)

Se agregan 15 permisos nuevos siguiendo el patrón master+granular ([decision #26]). El catálogo pasa de 72 a 87 permisos. La lista se persiste en la tabla `permissions` vía migración Alembic — sin migrar, los nuevos permisos no existen y el `require_permission()` falla con 403.

## 14.1 Permisos nuevos [NUEVO]

| Código | Módulo | Descripción | Nivel |
|---|---|---|---|
| `kg_ledger.view` | kg_ledger | Ver saldos y movimientos KgLedger (master). | Master |
| `kg_ledger.manage` | kg_ledger | CRUD `KgLedgerAccount` (metadata). | Granular |
| `kg_ledger.manage_adjustments` | kg_ledger | Crear/anular `KgLedgerMovement` manuales (auditados). | Granular |
| `tariffs.view` | tariffs | Ver `ServiceTariff` (histórico y vigente). | Master |
| `tariffs.manage` | tariffs | Crear nueva `ServiceTariff` (append-only). | Granular |
| `formulas.view` | formulas | Ver `MaterialConversionFormula`. | Master |
| `formulas.manage` | formulas | Crear nueva fórmula (append-only). | Granular |
| `maquila.view` | maquila | Ver la maquila interna causada (pares `internal_maquila_*` y reporte §10.2.2). | Master |
| `maquila.manage` | maquila | Anular pares de maquila interna (vía anulación del documento origen). | Granular |
| `willard.reconcile` | willard | Ejecutar cuadre semanal Willard + firmar "OK del viernes". | Granular |
| `kg_ledger.edit_after_seal` | kg_ledger | Editar/anular movimientos kg de una semana ya sellada (solo admin, deja bitácora — §4.5, §11.1.9). | Granular |
| `exceptions.view` | exceptions | Ver el panel de excepciones (`DiscrepancyTask`, §10.3). | Master |
| `exceptions.resolve` | exceptions | Justificar / corregir / solicitar arqueo sobre tareas del panel. | Granular |
| `exceptions.sign_daily` | exceptions | Firmar el "OK del día" (`DailyOkSeal`, §11.1.11). | Granular |
| `dashboard.view_sac` | dashboard | Ver dashboard SAC personalizado con drill-down. | Granular |

Estos permisos siguen la lógica master+granular ([decision #26]): tener `kg_ledger.view` da acceso a todos los sub-tabs; `maquila.view` da acceso puntual sin necesidad de master. La UI `RoleEditPage` los presenta agrupados por módulo.

Actualización obligatoria del catálogo: migración Alembic con `INSERT INTO permissions` para cada permiso nuevo, ejecutada en dev (5434), test (5433) y prod (vía skill `/deploy`).

## 14.2 Roles SAC sugeridos (tabla exhaustiva rol × permiso)

Se definen **10 roles funcionales** para SAC (los 8 de la tabla principal más el **Coordinador de Postconsumo** y el **Auditor de Inventario — Erwin**, detallados abajo). El rol `Yurani (caja menor)` tiene scope por **cuentas asignadas** (las cajas menores que administra, una por sede — visita 2026-07-02, ver §9.4); la sede de cada gasto se hereda de la caja usada.

Los nombres de roles son etiquetas funcionales; en el sistema son `Role` filas con `is_system_role=FALSE` (custom por org) o `TRUE` si se estandarizan. La tabla lista **explícitamente** cada permiso porque en producción SAC no queremos ambigüedad de scope. Convención de celdas: `R` (read/view), `W` (write/create/edit), `M` (manage/delete/cancel), `—` (sin acceso), `†` (scope por **cuentas asignadas** — las cajas menores que Yurani administra, §9.4; NO es filtro por sede).

| Permiso / Rol | Admin (Hugo) | Liquidador (Johana) | Operador BAQ (David) | Operador JM (Henry) | Comercial | Caja Menor (Yurani) | Viewer | Externo |
|---|---|---|---|---|---|---|---|---|
| **Compras** | | | | | | | | |
| `purchases.view` | R | R | R | R | R | — | R | — |
| `purchases.create` | W | W | W | W | W | — | — | — |
| `purchases.edit` | W | W | W | — | — | — | — | — |
| `purchases.liquidate` | M | M | — | — | — | — | — | — |
| `purchases.cancel` | M | M | — | — | — | — | — | — |
| **Ventas** | | | | | | | | |
| `sales.view` | R | R | R | R | R | — | R | — |
| `sales.create` | W | W | W | W | W | — | — | — |
| `sales.edit` | W | W | W | — | W | — | — | — |
| `sales.liquidate` | M | M | — | — | — | — | — | — |
| `sales.cancel` | M | M | — | — | — | — | — | — |
| **Doble Partida** | | | | | | | | |
| `double_entries.view` | R | R | R | — | R | — | R | — |
| `double_entries.create` | W | W | — | — | W | — | — | — |
| `double_entries.liquidate` | M | M | — | — | — | — | — | — |
| **Inventario** | | | | | | | | |
| `inventory.view` | R | R | R | R | R | — | R | — |
| `inventory.adjust` | M | M | M | M | — | — | — | — |
| `inventory.transfer` | M | M | M | M | — | — | — | — |
| `inventory.transform` | M | M | M | M | — | — | — | — |
| **Tesorería (Money Movements)** | | | | | | | | |
| `treasury.view` | R | R | R | — | — | R† (cuentas asignadas) | R | — |
| `treasury.create` | W | W | — | — | — | W† (cuentas asignadas) | — | — |
| `treasury.annul` | M | M | — | — | — | — | — | — |
| `treasury.edit_classification` | M | M | — | — | — | M† (solo movimientos propios de sus cajas, del día — §9.4) | — | — |
| `treasury.manage_distributions` | M | M | — | — | — | — | — | — |
| **KgLedger** | | | | | | | | |
| `kg_ledger.view` | R | R | R | R | — | — | R | — |
| `kg_ledger.manage` | M | M | — | — | — | — | — | — |
| `kg_ledger.manage_adjustments` | M | M | — | — | — | — | — | — |
| **Tarifas y Fórmulas** | | | | | | | | |
| `tariffs.view` | R | R | R | — | — | — | R | — |
| `tariffs.manage` | M | M | — | — | — | — | — | — |
| `formulas.view` | R | R | R | R | — | — | R | — |
| `formulas.manage` | M | M | — | — | — | — | — | — |
| **Maquila** | | | | | | | | |
| `maquila.view` | R | R | R | R | — | — | R | — |
| `maquila.manage` | M | M | — | — | — | — | — | — |
| **Willard** | | | | | | | | |
| `willard.reconcile` | M | M | — | — | — | — | — | — |
| `kg_ledger.edit_after_seal` | M | — | — | — | — | — | — | — |
| **Excepciones (panel §10.3)** | | | | | | | | |
| `exceptions.view` | R | R | R | R | — | — | R | — |
| `exceptions.resolve` | M | M | M | M | — | — | — | — |
| `exceptions.sign_daily` | M | M | — | — | — | — | — | — |
| **Terceros** | | | | | | | | |
| `third_parties.view` | R | R | R | R | R | R (lectura para asociar tercero al gasto) | R | — |
| `third_parties.create` | W | W | W | W | W | — | — | — |
| `third_parties.edit` | W | W | — | — | — | — | — | — |
| **Materiales / Config** | | | | | | | | |
| `materials.view` | R | R | R | R | R | — | R | — |
| `materials.edit` | W | W | — | — | — | — | — | — |
| `materials.edit_prices` | M | M | — | — | — | — | — | — |
| `expense_categories.view` | R | R | R | R | R | R | R | — |
| **Activos fijos** | | | | | | | | |
| `fixed_assets.view` | R | R | R | R | — | — | R | — |
| `fixed_assets.manage` | M | M | — | — | — | — | — | — |
| **Reportes** | | | | | | | | |
| `reports.view` | R | R | R | R | R (restringido) | — (sin reportes financieros, §9.4) | R | — |
| `reports.view_pnl` | R | R | R | — | — | — | R | — |
| `reports.view_expenses` | R | R | R | — | — | — | R | — |
| `dashboard.view_sac` | R | R | R | R | R | R (versión reducida por cuentas asignadas, §10.4) | R | — |
| **Administración** | | | | | | | | |
| `users.manage` | M | — | — | — | — | — | — | — |
| `roles.manage` | M | — | — | — | — | — | — | — |
| `organization.edit` | M | — | — | — | — | — | — | — |

Notas:

- **Admin SAC (Hugo)**: efectivamente superuser dentro de la organización SAC. En el modelo de datos es un `Membership` con rol admin, no `is_superuser=TRUE` (esa flag es para EcoBalance staff, ver [decision #29]).
- **Liquidador (Johana)**: todos los permisos de negocio + reportes, sin administración de usuarios/roles/org.
- **Operador BAQ (David)**: opera Circunvalar. Digita entradas, transfiere entre sedes, ajusta inventario. No liquida.
- **Operador JM (Henry)**: opera Juan Mina. Similar a David pero enfoque en transformaciones (fundición, crisol) y KgLedger. Alcance final [PENDING-CONFIRM] — la lista de permisos aquí es un piso, se afinará tras sesión 1:1.
- **Comercial**: registra ventas, DP, ve reportes restringidos. Nómina fija — no genera comisiones (Hugo, sesión noche 2026-06-26).
- **Caja Menor (Yurani)**: acceso directo al sistema (Daniel 2026-06-30). **Una caja menor por sede, todas operadas por Yurani** (visita 2026-07-02). Registra `MoneyMovement` tipo `expense` contra las cajas menores que administra; el `warehouse_id` del gasto **se hereda de la caja usada** (ver §9.4 y §11.2.6). El scope se implementa vía middleware que restringe `account_id ∈ <cajas menores asignadas>` en `POST /money-movements` y filtra `GET /money-movements` a esas cuentas. `Membership.default_warehouse_id` es solo conveniencia de UI.
- **Coordinador de Postconsumo (nacional)**: usuario del sistema, persona de SAC. Envía el cuadro semanal a Willard y concilia el saldo nacional (el acta incluye detalle por entrega: fecha, remisión, kg — §10.2.5). Permisos: `willard.reconcile` (M), `kg_ledger.view` (R), `maquila.view` (R), `reports.view` (R), `inventory.view` (R), `sales.view` (R); sin permisos de tesorería, compras ni administración.
- **Auditor de Inventario (Erwin)** — P38, criterio de aceptación 6 del cliente ("Erwin trabaja desde el sistema para auditar inventario"): su rol evoluciona de digitador masivo a auditor/validador. Permisos: `inventory.view` (R), `inventory.adjust` (M — arqueos y ajustes con aprobación), `purchases.view` (R — valida pesos y referencias antes de que Johana liquide, §7.2), `materials.view` (R), `kg_ledger.view` (R), `exceptions.view` (R) y `exceptions.resolve` (M — resuelve tareas de arqueo del panel §10.3); sin liquidación, tesorería, ventas ni administración. Nota de nombre: §7.2 lo describe operativamente como "gestor de compras chatarra" — es la misma persona; el rol funcional en el sistema se llama **Auditor Inventario**.
- **Permisos del panel de excepciones por rol**: `exceptions.view`/`exceptions.resolve` — Admin, Liquidador (Johana), Auditor (Erwin) y supervisores de bodega; `exceptions.sign_daily` — Johana (y Admin). El Coordinador de Postconsumo firma el sello SEMANAL (`willard.reconcile`), no el diario.
- **Viewer**: solo lectura consolidada.
- **Externo**: rol placeholder — Green Loop NO es usuario del sistema, es `ThirdParty` service_provider. Se lista aquí para claridad.
- **"El pelado" / Jose**: mismo actor (confirmado por Daniel, sesión 2026-06-30). Es dev interno SAC. Durante capacitación tiene rol Admin temporal; post-implementación se le asigna rol custom según su función real (probablemente Operador JM extendido).

## 14.3 Aislamiento por `organization_id` [REUTILIZADO #25, #26]

La multi-tenancy actual de EcoBalance es suficiente para aislar SAC de los otros 3 clientes sin cambios.

- **Header obligatorio** `X-Organization-ID` en todas las llamadas API. Rechazado con 400 si falta (excepto endpoints `/system/` que usan `get_current_superuser`).
- **`CRUDBase._base_query()`** filtra `organization_id = current_org_id` automáticamente para todas las tablas con `OrganizationMixin`. Las ~12 tablas nuevas SAC lo heredan (§11.1).
- **Sidebar filtering**: `usePermissions()` en frontend lee el conjunto de permisos del user en la org actual. Los módulos nuevos SAC no aparecen para usuarios de Costa/Biogreen/MetaRecycling.
- **Cross-org access**: sólo `is_superuser=TRUE` de EcoBalance staff. Los usuarios SAC no ven ni pueden llamar endpoints con otros `organization_id` — el interceptor de axios en frontend envía siempre la org actual, y `get_required_org_context()` valida membership.
- **`warehouse_id` es transparente al aislamiento**: filtra dentro de la org, no aisla entre orgs. Yurani ve solo su sede dentro de SAC, pero no cruza a Meta.

Consecuencia importante: si SAC eventualmente pide un usuario que sólo vea su sede, se hace vía filtrado por `warehouse_id` en endpoints y sidebar, NO fragmentando `organization_id`. Fragmentar por sede rompería costo promedio único ([decision #5]).

---

# 15. Migración inicial

El principio guía es reutilizar el skill `/migrate-client` ([decision #28]) sin crear scripts aislados. Extendemos el template Excel con hojas SAC-specific, agregamos validaciones nuevas al skill, y respetamos el flujo dev→confirmación→prod. La operación de migración es **solo saldos iniciales**, no historial transaccional — decisión cerrada en sesión con Hugo y Johana (2026-06-26).

## 15.1 Estrategia: solo saldos iniciales

Sesión 2026-06-26 dejó dos citas explícitas:

- Hugo: "simplemente saldos iniciales… no, imaginate ahora… enloquecemos".
- Johana: "una fecha porque en un solo mes pues el volumen es bastante".

Consecuencias operativas:

- **Se migran** al corte: inventarios físicos por sede, cuentas de dinero con saldo, terceros con `initial_balance`, activos fijos con `historical_load=TRUE` ([decision #46]), 5 saldos KgLedger, tarifas y fórmulas vigentes, categorías de gasto, unidades de negocio.
- **No se migra**: historial transaccional (`Purchase`, `Sale`, `MoneyMovement`, `InventoryMovement` previos al corte). Todo movimiento post-go-live se captura desde día 0 en el sistema.
- **Fecha de corte**: abierta como **P55** (una de las 3 preguntas no técnicas que quedan, §18.2). Idealmente un **viernes**, coincidiendo con el último cuadre Willard antes del arranque. Días de operación dual (Excel paralelo + sistema) se acuerdan con Johana.
- **Reusar Excels existentes de Hugo y Johana**: deuda Willard (422 ton, 131 BAQ + 48 BOG), saldos intersede/intra-horno/crisol, factores conversión, inventarios por sede. NO se pide al cliente rellenar desde cero — se importan los Excels actuales al template EcoBalance.

Aspecto crítico: los saldos iniciales de terceros con `initial_balance != 0` (Willard, Eco Alloys con >$20.000 millones, Panamá, Prosperidad) implican un `cutoff_date` implícito (la fecha de migración). Los saldos exactos se toman al corte de arranque — regla del cliente: no se piden datos confidenciales (saldos) antes de pasar la propuesta comercial. Se documenta como limitación conocida en [decision #55] — el sistema no persiste explícitamente `cutoff_date` hoy, y registrar movimientos con `date` anterior al corte produce presentación inconsistente en el estado de cuenta. Mejora pendiente `mejora_cutoff_date_terceros` en `memory/`.

## 15.2 Hojas Excel del template SAC

El template base `data/migration_template.xlsx` tiene 12 hojas estándar. Para SAC se extiende con 3 hojas nuevas y varias columnas adicionales en hojas existentes. El resultado es `data/migration_template_sac.xlsx` versionado en el repo (siguiendo el patrón de `migration_template_biogreen.xlsx` y `migration_template_biogreen_v2.xlsx`).

### 15.2.1 Hojas nuevas SAC-specific

**Hoja `CuentasPlomo`** — saldos iniciales KgLedger:

| Columna | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `code` | string | SÍ | Código único, convención con guiones (§4.2, §11.1.1): `WILLARD-BAT-BAQ`, `WILLARD-BAT-BOG`, `WILLARD-DROSS`, `INTERSEDE-CV-JM`, `INTRA-HORNO-JM`, `CRISOL-JM`. |
| `display_name` | string | SÍ | Nombre presentable. |
| `account_type` | enum | SÍ | `willard_baterias \| willard_drosses \| intersede \| intra_horno \| crisol`. |
| `warehouse_code` | string | Condicional | Código Warehouse (para internas). Blank para Willard. |
| `third_party_code` | string | Condicional | Código ThirdParty (para Willard). Blank para internas. |
| `saldo_inicial_kg` | decimal | SÍ | Kg en la cuenta al corte. Positivo = deuda / carga. |
| `fecha_corte` | date | SÍ | Fecha del corte contable. |
| `notas` | string | NO | Contexto. |

Migración carga cada fila como `KgLedgerAccount` + un `KgLedgerMovement` de tipo `migration_initial_load` con `delta_kg = saldo_inicial_kg`, `description = "Carga inicial migracion SAC"` (marker análogo a [decision #28] que excluye del reporte operativo). **Willard Baterías se carga como DOS filas** (sub-saldos por sede, §4.1): `WILLARD-BAT-BAQ` (`warehouse_code=CV`, referencia ~131 ton) y `WILLARD-BAT-BOG` (`warehouse_code=BOG`, referencia ~48 ton). El resto de las 422 ton está en otros centros de distribución Willard — informativos, no son bodegas SAC y no se cargan como saldo propio (regla Johana: "no lo estoy debiendo hasta que no ingresen"). Cifras exactas al corte de arranque.

**Hoja `TarifasServicio`** — `ServiceTariff` iniciales:

| Columna | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `tariff_code` | enum | SÍ | Ver §11.1.4. |
| `unit_price_cop` | decimal | SÍ | Precio unitario. |
| `unit` | enum | SÍ | `per_kg_lead \| per_kg_battery \| per_unit`. |
| `notes` | string | NO | Contexto. |

Filas obligatorias mínimas (según Hugo, reunión noche 2026-06-26):

```
maquila_willard, 2097.00, per_kg_lead, "Tarifa vigente Hugo 2026-06-26 - por cada entrega"
maquila_intersede_cv_jm, 1500.00, per_kg_lead, "Tarifa interna - causada al envio (visita 2026-07-02)"
maquila_crisol, 300.00, per_kg_lead, "Adicional crisol - causado a la salida (visita 2026-07-02)"
flete_willard_bog_baq, 216.00, per_kg_battery, "Flete Willard BOG-BAQ - facturado mensual"
flete_willard_planta_planta, 37.00, per_kg_lead, "Flete Willard planta - por cada entrega (corregido en visita 2026-07-02)"
```

Todas son valores **sugeridos y parametrizables** con vigencia histórica.

**Hoja `FormulasConversion`** — `MaterialConversionFormula`:

| Columna | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `material_code` | string | SÍ | Código SAC del material. |
| `formula_type` | enum | SÍ | `battery_to_lead \| drosses_to_lead \| scrap_with_terminal_to_lead \| custom`. |
| `parameters_json` | string | SÍ | JSON crudo con el schema del Anexo D. |
| `willard_account_subtype` | enum | NO | `escurrido \| pinza` cuando aplica (SEC). |
| `notes` | string | NO | Contexto. |

Ejemplo de filas:

```
BAT-07, battery_to_lead, {"kg_lead_per_unit": 2.5}, , "Referencia 07 Willard"
JAMICHE, drosses_to_lead, {"lead_percentage": 0.53}, , "Jamiche 53%"
SEC, drosses_to_lead, {"lead_percentage": 0.56}, escurrido, "SEC ESCURRIDO 56%"
SEC, drosses_to_lead, {"lead_percentage": 0.59}, pinza, "SEC PINZA 59% renegociado"
```

### 15.2.2 Hojas estándar con columnas extendidas

**`Materiales`** gana columnas opcionales `factor_willard_default` (informativo, la fuente real es `FormulasConversion`) y `default_unit` (`kg | unidad`) — ya soportado por [decision #54].

**`Terceros`** — filas obligatorias para SAC:

- Willard (behavior_types: `customer` + `service_provider` + `liability` — `customer` es OBLIGATORIO: las entregas de plomo se modelan como `Sale` a Willard y la validación de decisión #32 lo exige; sin él, `Sale.liquidate` fallaría), sin `initial_balance` en pesos salvo CxC de facturas pendientes al corte (el saldo en kg va en `CuentasPlomo` — 422 ton).
- Green Loop (behavior_type: `service_provider`).
- Eco Alloys (behavior_type: `generic`), `initial_balance = +20.000.000.000` aprox (CxC >$20.000 millones — placeholder; cifra exacta al corte de arranque).
- Panamá (behavior_type: `generic`), `initial_balance` al corte de arranque.
- Prosperidad (behavior_type: `generic`), `initial_balance` al corte de arranque.
- Socios (behavior_type: `investor`) con nombres y `initial_balance` según cierre contable.

**`Bodegas`** — mínimo obligatorio:

```
CV, Circunvalar (BAQ), fisica
JM, Juan Mina (BAQ), fisica
BOG, Bogotá, fisica
CV-MOLINO, CV - Molino (virtual), virtual
JM-TRANSITO, JM - Recepción en tránsito, virtual
```

**`UnidadesNegocio`** — 4 UN obligatorias:

```
UN1, Reciclaje Plomo
UN2, Maquila Willard
UN3, Reventa DP
UN4, Proyectos Especiales
```

**`Cuentas`** — cuentas de dinero. Convención de naming SAC: prefijo por sede (`CV-Caja`, `JM-Banco`, `BOG-Caja`) o `Corp-` (`Corp-Bancolombia`). Corp-* mapean a `warehouse_id=NULL` en movimientos futuros (bucket "Corporativo" en reportes).

**`ActivosFijos`** — usa `historical_load=TRUE` para activos ya depreciados desde otro ERP ([decision #46]). Columna `warehouse_code` alimenta `FixedAsset.warehouse_id`. Columnas `accumulated_depreciation` obligatoria para activos históricos.

**`CategoriaGastos`** — 8 categorías seed SAC (§11.1.8) se agregan en la migración vía seed automático, no en el Excel. Categorías adicionales que Johana defina en visita (auxiliares por máquina/vehículo, §9.3) se agregan post-load a través de la UI de Config.

## 15.3 Workflow migración (skill `/migrate-client` extendido) [REUTILIZADO #28, #46]

El skill existente se extiende sin cambios estructurales al flujo — solo se agregan validaciones y flags:

**Pre-flight**:
- Validar Excel offline (`--dry-run`) — verifica hojas obligatorias SAC (`CuentasPlomo`, `TarifasServicio`, `FormulasConversion`), tipos de datos, referencias cruzadas (`material_code` en `FormulasConversion` existe en `Materiales`).
- Backend up (health check).
- Alembic head — verifica que migración con permisos SAC nuevos, columnas `warehouse_id` (en `money_movements` y `money_accounts`), `willard_*` y los tipos de movimiento `internal_maquila_*` está aplicada en la BD destino.

**Dry-run dev** (BD desarrollo, puerto 5434):
- Carga Excel a BD dev sin `--reset-org`.
- Verifica conteos (6 KgLedgerAccount — 5 cuentas lógicas con Willard Baterías en 2 sub-cuentas —, 5 ServiceTariff, N MaterialConversionFormula, N ThirdParty, N Material, etc.).
- Ejecuta Balance Sheet + Balance Detallado y valida coherencia.
- Reporta discrepancias.

**Apply dev** con `--reset-org SAC`:
- Purga la org SAC completa (soft delete + recreate).
- Recarga desde Excel.
- Aplica validaciones adicionales SAC (ver §15.4).
- `--balance-tolerance` configurable (default $1) para tolerancia en pesos.
- `--kg-tolerance` **flag nuevo** (default 5 kg) para tolerancia en KgLedger.
- Reporte final con todas las verificaciones.

**Confirmación 1 (humana)**: revisión del reporte dry-run + apply dev. Daniel/Eduardo aprueban explícitamente antes de continuar.

**Dry-run prod** (contra BD producción sin `--reset-org`):
- Ejecuta las mismas validaciones contra la BD prod. Sin `--apply`, no toca datos.

**Confirmación 2 crítica (humana + doble)**: dos confirmaciones antes de continuar.

**Apply prod** — skill **NUNCA** pasa `--reset-org` a prod. Ejecuta:
- Backup completo previo (fuera del skill, precondición operativa).
- Carga.
- Validaciones automáticas post-load (§15.4).
- Reporte final con discrepancias detectadas.

**Cleanup opcional** (post-verificación): eliminar hojas de trabajo temporales, verificar migración `alembic upgrade head` no pendiente (ejecutada solo vía `/deploy`, no por el skill de migración).

Nota crítica: el skill `/migrate-client` NUNCA ejecuta `alembic upgrade` — las migraciones a prod son responsabilidad exclusiva del skill `/deploy`. Si el pre-flight detecta que la migración con permisos y columnas SAC no está aplicada en prod, el skill se aborta y solicita al operador correr `/deploy` primero.

## 15.4 Validaciones específicas SAC

Checks post-load integrados directamente en el skill (no en scripts separados):

**Estructurales**:
- 4 `BusinessUnit` obligatorias creadas.
- 3 `Warehouse` físicos (`CV`, `JM`, `BOG`) + 3 virtuales (`CV-MOLINO`, `JM-TRANSITO`, `CV-TRANSITO` — §11.2.7).
- 6 filas de `KgLedgerAccount` creadas — 5 cuentas lógicas confirmadas en visita 2026-07-02: Willard Baterías (2 sub-cuentas: BAQ y BOG), Willard Drosses, Intersede, Intra-horno, Crisol.
- Willard `ThirdParty` existe con behavior_types `customer` + `service_provider` + `liability` (§11.3).
- 5 `ServiceTariff` vigentes con los códigos obligatorios y precios exactos.
- Al menos 1 `MoneyAccount` tipo cash creada.
- 8 `ExpenseCategory` seed SAC creadas con `is_system_entity=TRUE`.
- Eco Alloys, Panamá, Prosperidad presentes como `ThirdParty` generic.

**Numéricas** (dentro de tolerancia configurable):
- `SUM(KgLedgerAccount.saldo_inicial)` por `account_type` coincide con cuadres SAC (422 ton Willard Baterías, X ton Drosses, etc.). Tolerancia `--kg-tolerance` (default 5 kg).
- Balance Sheet coherente: activo = pasivo + patrimonio (tolerancia `--balance-tolerance`).
- `SUM(third_party.initial_balance)` refleja saldos individuales del Excel (por tercero).
- `SUM(FixedAsset.current_value)` refleja saldos de activos migrados con `historical_load=TRUE`.

**Referenciales**:
- Cada `MaterialConversionFormula` referencia un `Material` existente.
- Cada `KgLedgerAccount` de tipo Willard referencia el `ThirdParty` Willard.
- Cada `KgLedgerAccount` interna referencia un `Warehouse` existente cuando aplica.
- `parameters` JSON de `MaterialConversionFormula` cumple el schema del Anexo D según `formula_type` (validación estricta con `pydantic`).

**Reporte final** — tabla "Diferencias detectadas":

| Sección | Esperado | Cargado | Diferencia | Tolerancia | Estado |
|---|---|---|---|---|---|
| KgLedger Willard Baterías BAQ | 131,000.00 kg | 130,998.50 kg | -1.50 kg | 5 kg | OK |
| KgLedger Willard Baterías BOG | 48,000.00 kg | 48,000.00 kg | 0.00 kg | 5 kg | OK |
| KgLedger Willard Drosses | 15,200.00 kg | 15,200.00 kg | 0.00 kg | 5 kg | OK |
| Balance Sheet activo | $1,234,567,890 | $1,234,567,890 | $0.00 | $1 | OK |
| Terceros con initial_balance | 47 | 47 | 0 | 0 | OK |
| ServiceTariff vigentes | 5 | 5 | 0 | 0 | OK |
| KgLedgerAccount count | 6 | 6 | 0 | 0 | OK |

Si cualquier check falla fuera de tolerancia y el operador no aprueba explícitamente (confirmación adicional), el skill aborta antes del apply prod.

**Ejemplo de invocación del skill con SAC**:

```
/migrate-client
  --template data/migration_template_sac.xlsx
  --org-name "Soluciones Ambientales del Caribe"
  --org-nit 900XXXXXXX
  --balance-tolerance 1
  --kg-tolerance 5
  --dry-run  # o --apply-dev / --apply-prod según fase
```

El resultado exitoso deja SAC operativa en producción con: 1 org, 4 UN, 6 warehouses (3 físicos + 3 virtuales), 6 KgLedgerAccount (5 cuentas lógicas), 5 ServiceTariff, N MaterialConversionFormula, N ThirdParty, N Material, N FixedAsset (con `historical_load=TRUE` donde aplica), N MoneyAccount (incluidas las 3 cajas menores por sede y la caja Green Loop), y ningún `Purchase`/`Sale`/`MoneyMovement` de historial — todos los movimientos operativos se capturan post-go-live directamente en el sistema.

# 16. Roadmap por fases

El proyecto SAC se ejecuta en tres fases secuenciales con dependencias explicitas (ver §16.4). Fase 1 consolida el cuadre operativo y financiero — es la que se cotiza y arranca hoy. Fase 2 agrega trazabilidad de planta y movilidad, y depende de sesiones especificas con Henry (P16) y Jose (dev interno SAC, ver Anexo A). Fase 3 cierra el alcance comercial y regulatorio (exportaciones, subproductos completos, reportes DIAN e IDEAM).

La estimacion de esfuerzo se dimensiona en semanas-persona (SP). Backend (BE) y frontend (FE) trabajan en paralelo pero comparten hitos de validacion. Los criterios de aceptacion son verificables al cierre de cada fase — no son aspiracionales, son entregables medibles.

## 16.1 Fase 1 — Cuadre operativo y financiero (foundations)

Fase 1 entrega el cuadre operativo y financiero unificado, elimina la triple digitacion de Johana y reemplaza los cuadernos paralelos por captura unica. Es el equivalente al "MVP contractual" — al cerrar Fase 1, SAC opera desde el sistema en las 3 sedes con las 5 cuentas en kg (confirmadas en visita 2026-07-02) cuadrando diariamente, y el consolidado SAC refleja la realidad sin intervencion manual.

**Alcance modular (capitulos 1-15 de este documento):**

| # | Modulo | Naturaleza | Referencia |
|---|--------|-----------|-----------|
| 1 | Recepcion e InboundOrder unificada (chatarra + postconsumo + drosses) | [NUEVO] | §7.1, §7.3 |
| 2 | Maestros extendidos (materiales con `business_unit_id` + `default_unit`, terceros con behavior_types, Warehouses CV/JM/BOG) | [MODIFICADO #33, #54] | §11.2 |
| 3 | Compras con liquidacion MANUAL por Johana (no automatica) | [MODIFICADO #2] | §7.2 |
| 4 | Maquila Willard (ServiceTariff + factor contractual + fletes ingreso) | [NUEVO] | §6.1-§6.4 |
| 5 | Maquila intersede (par de MoneyMovements internos enlazados, causacion al envio y al cierre de crisol — **simplificado en v0.5**) | [NUEVO] | §5.2-§5.4 |
| 6 | KgLedger (5 cuentas paralelas al libro en pesos) | [NUEVO] | §4.2-§4.3 |
| 7 | Inventario multi-sede unificado con costo promedio global | [REUTILIZADO #5, #7] | §7.1 |
| 8 | Transformaciones internas (molino, picado, fundicion, crisol) con descargo agregado | [MODIFICADO #17, #53] | §7.4 |
| 9 | Traslados intersede (Transfer + KgLedgerMovement + par de maquila interna) | [MODIFICADO] | §7.5 |
| 10 | Ventas + descarga de cuenta kg intersede al liquidar | [MODIFICADO #2, #42] | §7.6 |
| 11 | Tesoreria con `warehouse_id` ortogonal en MoneyMovement | [MODIFICADO #39, #44] | §9.1-§9.2 |
| 12 | Caja menor Yurani (rol con scope por cajas asignadas; el gasto hereda la sede de la caja) | [NUEVO] | §9.4 |
| 13 | Categorias de gasto jerarquicas con auxiliares por maquina/vehiculo | [MODIFICADO #36] | §9.3 |
| 14 | 17 reportes base + 6 reportes propios SAC | [MODIFICADO / NUEVO] | §10.1-§10.2 |
| 15 | Panel de excepciones y alarmas (modulo de primera clase) | [NUEVO] | §10.3 |
| 16 | Dashboard SAC personalizado con drill-down | [NUEVO] | §10.4 |
| 17 | RBAC con roles SAC (Yurani caja menor, David operaciones, comercial DP, etc.) | [MODIFICADO #25, #26] | §14.1-§14.2 |
| 18 | Migracion inicial (skill `/migrate-client` extendido con 3 hojas SAC nuevas) | [MODIFICADO #28] | §15.1-§15.4 |

**Esfuerzo estimado (~10.75 semanas-persona en paralelo BE + FE — reducido desde ~11.5 SP del v0.4 por la simplificacion de maquila):**

| Bloque | BE (SP) | FE (SP) | Notas |
|--------|---------|---------|-------|
| Modelo de datos + migraciones Alembic (KgLedger, ServiceTariff, MaterialConversionFormula, ExpenseCategory jerarquica, `warehouse_id` en MoneyMovement y MoneyAccount, tipos `internal_maquila_*`) | 1.25 | — | 12 tablas [NUEVO] (§11.1), 5 tablas [MODIFICADO] (§11.2) — sin tablas de commitments (simplificado en v0.5) |
| Endpoints KgLedger + par de maquila interna (causacion inmediata al envio/crisol) | 1.25 | — | **Simplificado en v0.5 — causacion inmediata**, sin algoritmo de consumo diferido. Tests: par al confirmar traslado, anulacion cascade, crisol a la salida, exclusion del consolidado (§5.4) |
| Endpoints Maquila Willard + ServiceTariff | 1.0 | — | ~10 endpoints [NUEVO]; facturacion por entrega + flete BOG-BAQ mensual |
| Extension endpoints existentes (Purchase/Sale con `warehouse_id`, transformaciones cross-unit ya cerradas en decision #53) | 0.5 | — | Backwards-compatible |
| Reportes: panel de excepciones, dashboard, 6 reportes SAC, extension P&L/Balance por `warehouse_id` | 1.5 | 1.5 | Paridad web/Excel/PDF (ver decision #51) |
| Frontend: modulos KgLedger, Maquila Interna, ServiceTariff, panel de excepciones | — | 1.75 | Mobile-first obligatorio (ver CLAUDE.md); sin pantalla de commitments |
| Frontend: extension Purchase/Sale/Transfer forms + RBAC + roles SAC | — | 1.0 | Reutiliza patrones existentes |
| Migracion inicial (extension `/migrate-client`, validaciones nuevas, dry-run SAC) | 0.5 | — | Reusa skill decision #28 |
| Tests integracion + guardrail cross-module | 0.5 | — | Meta: paridad P&L/drill-down (#49-#50) + exclusion de tipos internos en consolidado |
| **Total** | **6.5** | **4.25** | **~10.75 SP** (v0.4 estimaba ~11.5 — la causacion inmediata elimina tablas, FIFO y su UI) |

Los tiempos asumen equipo con familiaridad con EcoBalance (patrones establecidos en CLAUDE.md decisiones #1-#55). No incluyen capacitacion a SAC (bloque separado en propuesta comercial) ni migracion historica (Fase 1 solo migra saldos iniciales, decision #15).

**Entregables verificables al cierre de Fase 1:**

1. Captura unica funcional: Johana ya no digita el mismo movimiento en 2 sistemas. Test: crear una `InboundOrder` de postconsumo Willard en CV y verificar que refleja instantaneamente en KgLedger + inventario sin re-digitacion; una compra propia refleja en inventario (transito) **sin efecto financiero ni KgLedger** hasta que Johana liquida (matriz §3.4, decision #3).
2. 5 cuentas KgLedger (confirmadas en visita 2026-07-02; 6 filas con los sub-saldos Willard Baterias) cuadran diariamente. Test: `sum(KgLedgerMovement) == KgLedgerAccount.current_balance` para cada cuenta.
3. Conciliacion viernes con Willard consolidada en 1 reporte con detalle por entrega (fecha, remision, kg). Test: reporte por cuenta Willard (Baterias con sub-saldos BAQ/BOG, y Drosses) refleja los kg exactos que Willard factura — el subtype escurrido/pinza es desglose interno del SEC, no eje del cuadre.
4. P&L por sede (`warehouse_id`) balanceado en JM y BOG cuando "utilidad cero gerencial" esta activa (ver §3.5). Test: consolidado SAC excluye los tipos `internal_maquila_*` y coincide con la suma de P&L por sede neteando los pares.
5. Panel de excepciones detecta lo anomalo (y solo lo anomalo — vacio en un dia normal): diferencias despacho vs recibido fuera de tolerancia 3–5%, operaciones sin liquidar al cierre, diferencias de arqueo, kg fisico vs KgLedger, inventario en transito >48h.
6. Tests bloqueantes de maquila v0.5: par creado al confirmar la recepcion del traslado CV→JM (sobre kg recibidos), par de crisol a la salida, anulacion en cascade con el documento origen, liquidacion de venta NO crea maquila, consolidado excluye tipos internos (§5.4).
7. Migracion inicial de saldos SAC en dev+test corre `--dry-run` sin errores. Skill `/migrate-client` no rompe los 3 clientes existentes (Costa, Biogreen, MetaRecycling).
8. RBAC: Yurani opera las cajas menores de todas las sedes y cada gasto hereda la sede de la caja usada; David digita entradas en CV/JM pero no puede liquidar; Comercial DP solo ve/crea Pasa Mano; el coordinador de postconsumo firma el cuadre semanal Willard.

**Criterios de aceptacion (verificacion presencial durante UAT):**

- Panel de excepciones vacio o con discrepancias justificadas al cierre de cada dia; discrepancia total < 0.5% valor total dia (tolerancia configurable por Johana).
- 100% de las entradas del dia registradas en el sistema (0 cuadernos paralelos).
- Deuda Willard por cuenta (Baterias con sub-saldos BAQ/BOG, y Drosses) reconcilia con el corte semanal (viernes) a ± 100 kg (tolerancia configurable en `KgLedgerAccount.tolerance_kg` — dato de configuracion al arranque).
- Reporte de P&L por UN reconcilia con drill-down (test de oro decision #49-#50) — la suma de items de listado destino = numero del P&L (± $1).
- La liquidacion por peso del caso real descrito por Johana se procesa bajo el modelo cerrado (§7.2: composicion conocida al recibir, reparto por costo promedio historico, liquidacion manual) — criterio 2 del doc cliente §2.7.
- El balance general muestra cifras consistentes con los cuadros Excel actuales de SAC dentro de la tolerancia acordada al inicio (tipicamente bajo 0,5% POR LINEA, no solo en el total) — criterio 3 del doc cliente §2.7.

**Fuera de alcance de Fase 1 (diferido a Fase 2/3):**

- Modulo movil offline (Fase 2, ver Anexo A).
- Trazabilidad 1:1 colada → aportantes consumidos → plomo crudo producido (Fase 2 — Fase 1 usa descargo agregado en `FurnaceCharge/CrucibleCharge` sin `BatchTracking`).
- Refinacion crisol detallada por lote con insumos/fundentes (Fase 2).
- Coexistencia formal con app movil de Jose (Fase 1: app Jose sigue operando en paralelo; Fase 2: Jose se integra al proyecto como dev interno — ver Anexo A).
- Exportaciones con precio provisional + ajuste FX (Fase 3).
- Reportes regulatorios automatizados (Fase 3 — la lista exacta la confirma SAC, P47; candidatos: DIAN, RA-1073, CONPES, IDEAM).
- Balance Sheet contable independiente por sede (fuera v1 — hoy es P&L gerencial por `warehouse_id`, ver §3.5).
- Migracion historica transaccional (fuera v1 — solo saldos iniciales, ver §15.1).

**Supuestos criticos para Fase 1:**

- Confirmacion contable de misma sociedad/NIT ya CERRADA (Daniel, sesion 2026-06-30). Cierra R1.
- Conectividad estable > 90% en las 3 sedes (CV, JM, BOG).
- Dispositivos disponibles: PC de escritorio para Johana/David + tablets/celulares para Erwin/Yurani (mobile responsive obligatorio, ver §13.4).
- Operacion dual durante transicion (2-4 semanas post go-live): SAC opera Excel paralelo + sistema hasta confirmar cuadre.
- Hugo activo como sponsor: cierres semanales presenciales o remotos.

**Riesgos clave de Fase 1 (ver §17 para tabla completa):**

- R13 CERRADA (visita 2026-07-02): maquila intersede se causa al envio ($1.500/kg) y a la salida del crisol ($300/kg) — validado por Hugo y Johana.
- R14 CERRADA (visita 2026-07-02): 5 cuentas KgLedger, crisol separado (medir eficiencia por etapa).
- R2 y R4 RESUELTAS/OBSOLETAS por cambio de modelo: sin FIFO ni consumo diferido, la causacion es automatica e inmediata al evento; el panel de excepciones (§10.3) cubre operaciones sin liquidar al cierre.
- Cero bloqueantes tecnicos activos para el kickoff de Fase 1.

## 16.2 Fase 2 — Trazabilidad de planta y movilidad

Fase 2 agrega la capa de trazabilidad fina que Fase 1 deja intencionalmente agregada. La operacion de horno grande y crisol pasa de descargo agregado (`FurnaceCharge/CrucibleCharge` como eventos de KgLedger) a trazabilidad 1:1 colada → aportantes consumidos → plomo crudo producido, via nuevo modelo `FurnaceBatch` (entidad negocio) y el concepto de trazabilidad `BatchTracking` que lo materializa. En paralelo se libera el modulo movil offline para captura en ruta postconsumo, co-desarrollado con Jose (ver Anexo A).

**Modulos entregables Fase 2:**

- Movil conductor offline (React Native o PWA offline-first) para captura postconsumo en ruta.
- Trazabilidad 1:1 de coladas: modelo `FurnaceBatch` (entidad negocio: colada individual) + concepto `BatchTracking` (trazabilidad genérica) que liga cada `FurnaceCharge` con las lineas fisicas de `InventoryMovement` consumidas y el plomo crudo generado.
- Refinacion crisol con detalle por lote: cada `CrucibleCharge` referencia el `FurnaceBatch` de origen, permite calcular rendimiento por lote y detectar mermas anomalas.
- Insumos/fundentes operativos en costo: gas, oxigeno, sosa, coque, cal. Se cargan como `InventoryMovement` de entrada y se consumen en `FurnaceCharge`/`CrucibleCharge` prorrateando al costo del batch.
- Sub-sub-cuenta intra-horno por horno individual (si SAC opera >1 horno grande) — extension de KgLedger sin romper modelo Fase 1.
- Reportes adicionales: trazabilidad colada, rendimiento por lote, productividad por operario (Henry/Jose input), recolecciones por ruta.
- Integracion progresiva con app movil de Jose (ver Anexo A).

**Bloqueantes para arrancar Fase 2 (sesiones 1:1 con Henry y Jose):**

- Sesion 1:1 con Henry: alcance operativo JM, tamano promedio de colada, frecuencia, operadores, tiempo de proceso, rendimientos historicos, insumos consumidos.
- Sesion 1:1 con Jose: mapeo de funciones de app movil actual, API de sincronizacion, cronograma retiro/integracion.
- Formato dispositivos movil en ruta: Android/iOS, conectividad esperada, capacidad de captura de foto para evidencia.
- [PENDING-CONFIRM Q2 diferido]: si Johana quiere Balance Sheet contable independiente por sede en Fase 2, requiere inter-company eliminations explicitas + journal entries de reparto (fuera v1 confirmado; posible Fase 2 si SAC lo prioriza).

**Estimacion Fase 2:** dimensionamiento se hace despues de sesiones 1:1 con Henry y Jose (rango preliminar: ~8-14 SP dependiendo de complejidad movil offline y sincronizacion con app Jose). No se cotiza hasta cerrar bloqueantes.

## 16.3 Fase 3 — Cierre comercial y regulatorio

Fase 3 cierra el alcance del sistema con las capacidades exportadoras y de compliance regulatorio. Se ejecuta cuando SAC decide iniciar operacion exportadora formal o cuando el marco regulatorio que SAC confirme con su asesor (P47 — candidatos: RA-1073, CONPES, IDEAM, DIAN) requiera reporte automatizado.

**Modulos entregables Fase 3:**

- Exportaciones con precio provisional + ajuste a la cobranza real (mecanismo similar a decision #35 pero para clientes internacionales).
- Diferencia de cambio (FX) en P&L: al cobrar en USD/EUR, la diferencia entre precio provisional y precio final entra como linea separada en P&L ("Diferencia en cambio").
- Subproductos con gestion completa: electrolito, escorias, gases capturados. Modelado con `MaterialCategory` dedicada + gestor externo autorizado como `ThirdParty` service_provider.
- Disposicion regulada: manifiestos, certificaciones de gestor autorizado, adjuntos en cada movimiento.
- Reportes regulatorios automatizados **segun la lista exacta que SAC confirme (P47)** — el doc cliente deliberadamente NO asume regulaciones; candidatos a validar: RA-1073 (residuos peligrosos), CONPES (economia circular), IDEAM (inventarios ambientales), reporte DIAN detallado.
- Dashboards consolidados ejecutivos: KPIs anuales, trends multi-anio, benchmarks vs industria.

**Bloqueantes para arrancar Fase 3:**

- Contador externo SAC valida formato exacto DIAN esperado (retenciones ICA/ReteFte por tipo proveedor, formato de facturacion electronica).
- Marco regulatorio aplicable: SAC confirma con asesor ambiental que resoluciones RA-1073, CONPES, IDEAM son las aplicables a operacion baterias plomo-acido.
- Destino subproductos: gestor autorizado firmado con certificaciones vigentes.
- Clientes exportacion: mercados objetivo (LATAM, USA, Europa), incoterms, moneda de facturacion, mecanismo de precio provisional (LME? formula propia?).

**Estimacion Fase 3:** rango preliminar ~6-10 SP dependiendo de complejidad regulatoria. Puede ejecutarse en paralelo a Fase 2 (ver §16.4) porque el modulo exportacion es independiente.

## 16.4 Dependencias entre fases

Las fases no son puramente secuenciales — hay solapes controlados y dependencias tecnicas explicitas. Este mapa evita cronogramas irrealistas.

| Fase destino | Depende de | Razon |
|--------------|-----------|-------|
| Fase 2 (trazabilidad colada) | Fase 1 cerrada (KgLedger funcionando con descargo agregado) | El modelo `BatchTracking` extiende `FurnaceCharge` — sin `FurnaceCharge` en Fase 1, no hay base sobre la que agregar trazabilidad |
| Fase 2 (movil offline) | Fase 1 cerrada + sesion 1:1 con Jose | El movil sincroniza contra endpoints de Fase 1; requiere API estable |
| Fase 2 (refinacion crisol detallada) | Fase 1 cerrada + sesion 1:1 con Henry | Modelo `CrucibleCharge` de Fase 1 se extiende con `BatchTracking` en Fase 2 |
| Fase 3 (exportaciones) | Fase 1 cerrada | Modulo independiente — puede iniciar en paralelo a Fase 2 |
| Fase 3 (subproductos completo) | Fase 2 refinacion detallada | Los subproductos se generan en el crisol; sin trazabilidad de crisol, la reconciliacion es aproximada |
| Fase 3 (reportes regulatorios) | Fase 1 datos + Fase 2 trazabilidad | De confirmarse aplicables (P47), los formatos tipo RA-1073/CONPES requieren nivel de detalle de Fase 2 para ser completos; con Fase 1 se puede generar version simplificada |

Consecuencia practica: Fase 3 modulo exportacion puede arrancar apenas Fase 1 cierre; Fase 3 modulo subproductos y reportes regulatorios completos requieren Fase 2 avanzada. Se recomienda cronograma con Fase 2 y Fase 3-exportacion en paralelo, Fase 3-subproductos/regulatorios secuencial post-Fase 2.

---

# 17. Riesgos abiertos y mitigaciones

Consolida los riesgos identificados durante el analisis del workflow SAC (R1-R12 originales) mas 3 riesgos nuevos derivados de los reviews adversariales (R13-R15) y 3 riesgos transversales del proyecto. Cada riesgo lleva estado explicito: **CERRADA** (con la decision que lo cierra), **ABIERTA** (con mitigacion propuesta y responsable), o **DIFERIDA** (a Fase 2/3). Cuando aplica, se agrega la etiqueta separada **(BLOQUEANTE)**.

| ID | Riesgo | Estado | Cierre / Mitigacion | Ref |
|----|--------|--------|---------------------|-----|
| R1 | Misma sociedad CV/JM/BOG vs sociedades separadas | **CERRADA** | Daniel confirmo 2026-06-30: 1 NIT, 1 razon social. Se activa eliminacion inter-company automatica en consolidado SAC. Se elimina modo "no eliminar pares intersede" del backlog | Anexo F, §2.1 |
| R2 | FIFO de causacion de maquila no determinista bajo carga | **RESUELTA/OBSOLETA (v0.5)** | El cambio de modelo de la visita 2026-07-02 (causacion inmediata al envio, §5) elimina el algoritmo FIFO y el consumo diferido — el riesgo desaparece por construccion | §5.2 |
| R3 | Perdida de trazabilidad bateria → plomo (imposible reconstruir en el futuro) | **DIFERIDA** (a Fase 2) | Fase 1 usa descargo agregado en `FurnaceCharge/CrucibleCharge`. La arquitectura NO impide agregar `BatchTracking` en Fase 2 (extension aditiva). Cliente debe entender que las coladas de Fase 1 no seran trazables retroactivamente | §7.4, §16.2 |
| R4 | Causacion de maquila dependia de que se liquidara la venta (disciplina operativa) | **RESUELTA/OBSOLETA (v0.5)** | Con causacion al envio (visita 2026-07-02) el par se emite automaticamente al confirmar el traslado — no depende de liquidaciones posteriores. Las operaciones sin liquidar al cierre las detecta el panel de excepciones (§10.3) por su propio merito | §5.1, §10.3 |
| R5 | Cuenta corporativa Bancolombia mezclada entre sedes (gasto CV pagado con cuenta corporativa) | **ABIERTA** | Convencion de naming en `MoneyAccount.name`: prefijo `Corp-*` marca cuentas corporativas → reportes por sede las agrupan en bucket "Corporativo" (`warehouse_id=NULL` en `MoneyMovement`) sin fragmentar la cuenta | §9.2 |
| R6 | Eco Alloys/Panama/Prosperidad como generic — no convertible a operacional si SAC cambia estrategia | **DIFERIDA** (fuera v1) | Documentado como "convert_generic_to_operational" en backlog. Molino re-modelado como `Warehouse` virtual, no como generic (correccion review #2) | §2.6 |
| R7 | Cambio de formula scrap → plomo (Willard renegocia %) recalcularia retroactivamente kg historicos | **CERRADA** | `KgLedgerMovement.conversion_formula_snapshot` (JSON) persiste la formula usada al momento del movimiento. Formula nueva solo aplica a movimientos futuros. Patron identico a `MaterialCostHistory` (decision #9) | §4.2, Anexo D |
| R8 | La venta desde JM podia escaparse de la causacion de maquila → JM aparentaba utilidad ficticia | **RESUELTA/OBSOLETA (v0.5)** | La maquila ya no depende de la venta: se causa al confirmar el traslado (par automatico, §5). Todo material que entra a JM desde CV/BOG causa su maquila en el mismo evento — no hay ruta de escape | §5.1, §12.2.4 |
| R9 | UX P&L por sede vs consolidado confunde a usuarios (Johana ve JM con utilidad y no entiende que es gerencial) | **ABIERTA** | Selector explicito en UI: toggle "Ver consolidado SAC (eliminar pares intersede)" vs "Ver por sede (con pares intersede)". Badge persistente muestra modo activo. Default: consolidado | §3.5, §10.4 |
| R10 | Migracion saldos kg iniciales genera KgLedger inconsistente (dif entre saldo declarado y suma de movimientos futuros) | **ABIERTA** | Hoja `CuentasPlomo` en template Excel SAC, validada en `--dry-run` (skill `/migrate-client`). Marker `migration_initial_load` en `KgLedgerMovement` inicial → excluido de reportes de flujo. Reconciliacion previa al `--apply` con SAC | §15.2, §15.4 |
| R11 | Doble conteo ingresos maquila intersede (par gasto CV + ingreso JM inflando el consolidado) | **CERRADA (mecanismo actualizado en v0.5)** | Par enlazado `internal_maquila_expense`/`internal_maquila_income` con tipos dedicados; el P&L consolidado **excluye ambos tipos por filtro de tipo de movimiento** (se netean a cero, mismo NIT) y las vistas por sede los incluyen. Test bloqueante `test_consolidated_pnl_excludes_internal_types` (§5.4) | §1.4, §3.5, §5.2 |
| R12 | Merma real de horno vs saldo kg intersede (kg enviados 1000, kg producidos 950 — 50 kg huerfanos) | **RESUELTA (reencuadrada en v0.5)** | La merma ya no afecta la causacion en pesos (causada al envio, §5.4). El saldo kg intersede se ajusta con `KgLedgerMovement manual_adjustment` auditado (motivo obligatorio, permiso `kg_ledger.manage_adjustments`); el panel de excepciones alerta saldos antiguos sin movimiento | §5.4, §7.6, §10.3 |
| R13 (NUEVO) | Momento causacion maquila intersede ambiguo (Hugo decia "al facturar venta", Johana decia "al ingreso planta") | **CERRADA (visita 2026-07-02)** | Resuelto (Johana en la visita; Hugo por WhatsApp): **causacion al envio** ($1.500/kg al confirmar el traslado) + adicional **a la salida del crisol** ($300/kg). Validado por Hugo Y por Johana. El modelo diferido FIFO del v0.4 se descarto (§5.2) | §5.1, Q-viva.1 |
| R14 (NUEVO) | 5 vs 4 cuentas KgLedger (Crisol independiente o sub-cuenta de Intra-horno) | **CERRADA (visita 2026-07-02)** | **5 cuentas — crisol confirmado como cuenta separada** para medir la eficiencia de cada etapa. Willard Baterias ademas con sub-saldos por sede (BAQ/BOG) | §4.1, Q-viva.2 |
| R15 (NUEVO) | Liquidacion compras: automatica vs manual entrada-por-entrada | **CERRADA** | Confirmado con Johana 2026-06-26: liquidacion es MANUAL entrada-por-entrada. Outline v0.3 asumia automatica — corregido a manual en §7.2. Sin cambios en decision #2 (workflow 3 pasos) | §7.2 |
| R-trans-1 | Resistencia al cambio (Johana acostumbrada a Excel paralelo) | **ABIERTA** | Plan de capacitacion en propuesta comercial: 2-4 semanas de operacion dual (Excel + sistema) hasta confirmar cuadre. Sponsor Hugo requerido | §16.1 |
| R-trans-2 | Volumen real de operaciones no cuantificado precisamente | **CERRADA** | Confirmado 10-20 entradas/dia entre 3 sedes (Erwin/Johana). Dimensionado suficiente para Fase 1. En operacion se recolectan metricas reales para dimensionar Fase 2 | §2.5 |
| R-trans-3 | Henry y Jose pendientes de sesiones 1:1 para Fase 2 | **DIFERIDA** (a Fase 2) | Bloqueante para arrancar Fase 2, NO bloqueante para Fase 1. Sesiones se agendan durante ejecucion de Fase 1 | Anexo A, §16.2 |

**Total riesgos:** 15 identificados + 3 transversales = 18. Estado tras la visita 2026-07-02: **7 CERRADAS (R1, R7, R11, R13, R14, R15, R-trans-2)**, **4 RESUELTAS/OBSOLETAS por el cambio de modelo (R2, R4, R8, R12)**, **4 ABIERTAS con mitigacion (R5, R9, R10, R-trans-1)**, **3 DIFERIDAS (R3, R6, R-trans-3)**. **Cero bloqueantes activos.**

---

# 18. Preguntas — estado tras la visita a planta (2026-07-02)

Consolida las preguntas dispersas en el v0.3 (71 preguntas) y las Q-viva del v0.4, con su estado actualizado tras la visita a planta del 2026-07-02 (Johana en sitio; Hugo por WhatsApp). **La visita cerro TODAS las preguntas tecnicas**; quedan abiertas solo tres no tecnicas (P1, P55, P64) mas los datos de configuracion que se recogen al arranque.

## 18.1 Preguntas cerradas en la visita (2026-07-02)

| Pregunta | Respuesta cerrada (2026-07-02) |
|---|---|
| **Q-viva.1** — Momento causacion maquila intersede (era BLOQUEANTE, R13) | **Al envio**: la maquila del horno ($1.500/kg de plomo equivalente) se causa al confirmar el traslado CV→JM; el adicional de crisol ($300/kg) se causa a la salida del crisol. En ambos: gasto Circunvalar / ingreso Juan Mina (par de MMs enlazados, §5). Validado por Hugo Y por Johana — la contradiccion de fuentes del v0.4 quedo resuelta (Johana en la visita; Hugo por WhatsApp). El modelo diferido FIFO del v0.4 se descarto (§5.2) |
| **Q-viva.2** — Crisol como cuenta KgLedger separada (era BLOQUEANTE, R14) | **Si — cinco cuentas.** El crisol se mide aparte para conocer la eficiencia de cada etapa. Al horno entran scrap, lodo, retal y demas aportantes; sale plomo crudo en lingote. Al crisol entra plomo crudo y sale plomo puro (§4.1) |
| **Q-viva.3** — Green Loop: estructura de comisiones | Opera con **caja provista por SAC**; compra en ruta **a nombre del proveedor real**; comision de **$100/kg recolectado** liquidada por consignacion aparte y causada como **gasto** (`expense_accrual`, [decision #83]) al liquidar la compra — v0.5 decia "prorrateada al costo via `PurchaseCommission`" y se corrigio en v0.6 (§7.3 punto 5) |
| **P2** — Liquidacion por peso | La composicion se conoce AL RECIBIR; el valor pagado se reparte entre las referencias por **costo promedio historico**. Cita de Hugo: *"Esa es la regla."* Liquidacion manual de Johana, no automatica (§7.2) |
| **V4** — Tolerancia de traslados intersede | 3–5% configurable; dentro del rango, ajuste automatico con **lo recibido como fuente de verdad**; por encima, excepcion/alarma (§7.5, §10.3) |
| **V8** — Asignacion de abonos a Willard / ruta de drosses | La **remision** de cada entrega define si el abono descarga baterias o drosses (dato del documento, no decision al liquidar). Drosses SIEMPRE ingresan por Juan Mina (§4.3, §7.3) |
| Cuadre diario | Se simplifica a **panel de excepciones y alarmas** — el sistema concilia solo; en un dia normal el panel esta vacio (§10.3) |
| Saldo Willard baterias por sede | **Sub-saldos Barranquilla y Bogota** de la misma cuenta logica; los kg pasan al saldo Barranquilla cuando el material llega fisicamente a Circunvalar (§4.1) |
| Fletes internos CV→JM (era Q6) | El transporte CV→JM es con **carros propios** — no hay flete en ese tramo; la maquila $1.500/kg es solo procesamiento (§6.2) |
| Nombre del proyecto de aluminio | **Eco Alloys**. Saldo exacto al corte de arranque |
| Cajas menores | **Una por sede, todas operadas por Yurani**; el gasto hereda la sede de la caja usada (§9.4) |
| Tarifas y momentos de facturacion | Flete planta–Willard **$37/kg** (corrige $38); maquila Willard y flete planta se facturan **por cada entrega**; flete BOG-BAQ $216/kg **mensual** + transporte fisico tercerizado como gasto variable (§6.1, §6.2) |

## 18.2 Abiertas (P1, P55, P64) + datos de configuracion al arranque

**Quedan abiertas SOLO tres preguntas — ninguna es tecnica:**

- **P1. Volumenes pico:** ¿cuantas ordenes de entrada se procesan por dia en promedio y en pico, desagregadas por sede y por tipo? Condiciona el dimensionamiento de los puestos de captura.
- **P55. Fecha de corte para el arranque de Fase 1:** idealmente un **viernes**, coincidiendo con el ultimo cuadre Willard antes del arranque. Define el snapshot inicial de la migracion (§15.1).
- **P64. Presupuesto y modalidad comercial:** rango orientativo y modalidad preferida (suscripcion mensual, pago por hito, implementacion + mantenimiento). **Se resuelve con la propuesta comercial** — no bloquea este documento.

**Datos de configuracion que se recogen al arranque** (no bloquean el cierre del alcance — regla del cliente: NO pedir datos confidenciales, en particular saldos, antes de pasar la propuesta comercial):

- **Tabla de factores por referencia Willard** (Anexo C): lista oficial de las 7 referencias + factores vigentes. Incluye la formula exacta scrap-con-borne — validar `scrap_factor` con Erwin usando al menos 5 casos reales (peso scrap, peso borne, plomo equivalente).
- **Tabla de retenciones por tipo de proveedor:** ICA, ReteFte, Rete IVA — porcentajes por categoria. Confirmar con contador SAC.
- **Lista de maquinas y vehiculos** para los auxiliares de gasto (§9.3): montacargas, camiones, horno, crisol, molino. Alimenta `ExpenseCategory` jerarquica + auxiliares.
- **Saldos iniciales al corte:** kg en transito CV→JM, kg en intra-horno y crisol, sub-saldos Willard (BAQ/BOG) por `willard_account_subtype`, saldos de terceros (incluidos Eco Alloys, Panama, Prosperidad), saldos de cuentas bancarias y cajas. Consolidar en template Excel SAC (§15.2).
- **Formatos Excel actuales** (cuadros de Johana, formato de Yurani) para la migracion y el paralelo de operacion dual.
- **Tolerancia kg del cuadre semanal Willard:** ± 50 kg / ± 100 kg — configurable en `KgLedgerAccount.tolerance_kg`.
- **Formato Willard de facturacion:** Excel, PDF, factura electronica DIAN. Afina el modulo de conciliacion viernes con el coordinador de postconsumo.

**Afinables en implementacion (no cambian arquitectura):**

- **Q14. Fecha de incorporacion de Jose:** el "pelado" es Jose (confirmado 2026-06-30). Fecha exacta de kickoff Fase 2 pendiente.
- **Q15. Alcance de Henry en Fase 1:** ¿solo operativo (no toca sistema) o registra `FurnaceCharge/CrucibleCharge` desde JM? Impacta permisos RBAC.
- **Q17. Retal (aportante):** el retal es un **INSUMO del horno grande** (no su producto). Afinar su clasificacion comercial — ¿se compra a terceros, se genera internamente, ambas? Modela como `Material` con `default_unit=kg`.
- **Q18. Punto de acopio Bogota:** capacidad, layout, ¿es una bodega dentro del `Warehouse` BOG o un sub-warehouse?
- **Q19. Calibracion basculas:** rutina de calibracion, alertas cuando la calibracion vence. Fuera de scope v1, se marca en `Warehouse.calibration_notes`.

## 18.3 Preguntas Fase 2 (sesion 1:1 con Henry y Jose)

Preguntas que se abordan formalmente en las sesiones 1:1 antes de arrancar Fase 2. Se listan aqui para no perderlas.

- **Coladas del horno grande:** tamano promedio (kg por colada), frecuencia (coladas/dia), operadores involucrados, tiempo total de proceso, temperatura, rendimiento esperado (kg plomo crudo / kg input).
- **Refinacion en crisol:** rendimiento esperado (kg plomo refinado / kg plomo crudo), calidad del output (analisis quimico), tiempo por lote, operadores.
- **Insumos horno y fundentes crisol:** lista exacta (gas, oxigeno, coque, cal, sosa), costo unitario, frecuencia de compra, proveedor. Impacta modelo `InventoryMovement` de entrada + `FurnaceCharge` de consumo.
- **Productividad por operario:** metrica esperada, base de reporte, si aplica a comisiones o solo a control gerencial.
- **Movil conductor Fase 2:** dispositivos disponibles (Android/iOS, RAM, capacidad de foto), conectividad esperada en ruta (3G/4G/nada), tolerancia a delay de sincronizacion.
- **App movil de Jose:** modulos que hoy captura (postconsumo, coladas, escritorio, inspeccion vehiculos), cronograma de retiro/integracion, formato de datos, API de sincronizacion, ver Anexo A.
- **Gas y oxigeno por colada:** mecanica de captura — ¿medidor automatico, manual, prorrateo?
- **Sub-sub-cuenta intra-horno:** si SAC opera >1 horno grande, ¿cada horno tiene KgLedger independiente?

## 18.4 Preguntas Fase 3 (contador externo, DIAN, exportaciones)

Preguntas que se abordan con el contador externo SAC + asesor ambiental antes de arrancar Fase 3.

- **Destino subproductos:** gestor autorizado (nombre, certificaciones vigentes, manifiestos requeridos). Modelo `ThirdParty` service_provider con auditoria de certificaciones.
- **Marco regulatorio aplicable:** ¿RA-1073 (residuos peligrosos), CONPES 3874/3934 (economia circular), IDEAM (inventarios ambientales), ANLA (autorizacion ambiental)? Cual aplica a operacion baterias plomo-acido.
- **Frecuencia y formato de reportes regulatorios:** mensual/trimestral/anual, formato Excel/PDF/API. Impacta modulo reportes automatizados.
- **Exportaciones — clientes/mercados:** LATAM, USA, Europa. Impacta modelo de precio provisional + ajuste FX.
- **Exportaciones — moneda:** USD, EUR. Impacta `Sale.currency` y politica de diferencia en cambio.
- **Exportaciones — mecanismo de precio provisional:** LME (London Metal Exchange), formula propia, precio fijo pre-embarque, precio a la cobranza. Impacta `SaleLine.provisional_price` + `SaleLine.final_price`.
- **Incoterms:** FOB Cartagena, CIF destino, EXW. Impacta modelo de fletes y responsabilidades.
- **Facturacion electronica DIAN:** ¿SAC ya factura electronica hoy? Integracion via API DIAN (validador tecnologico) o export a XML/UBL para carga manual.
- **Retenciones internacionales:** IVA, arancel, retencion en fuente para exportaciones.

---

# 19. Anexos

Los anexos consolidan referencias que se citan a lo largo del documento pero que por volumen o naturaleza (tablas exhaustivas, glosarios, propuestas de coexistencia con terceros) merecen espacio propio.

## Anexo A. Plan de coexistencia con app movil de Jose

Contexto validado en sesion 2026-06-30 con Daniel: **Jose es el pelado**. No son dos personas distintas. Jose es un **desarrollador interno de SAC** (no consultor externo) que hoy mantiene una app movil propia usada operativamente en Juan Mina para capturar postconsumo, inicios de colada, escritorio e inspecciones de vehiculos. En sesiones anteriores del v0.3 se referia al "pelado" como un dev distinto — esa distincion se elimina.

El plan de coexistencia es progresivo y respeta el conocimiento acumulado en la app de Jose. Se estructura en tres tramos alineados a las fases del proyecto (ver §16):

**Fase 1 — App Jose sigue operando en paralelo.**

Durante Fase 1, SAC opera el sistema EcoBalance para todo el flujo administrativo/financiero (compras, ventas, KgLedger, tesoreria, panel de excepciones) y la app de Jose sigue capturando lo que hoy captura en JM (postconsumo, inicios de colada, inspecciones). EcoBalance captura los **agregados** de esos eventos (por ejemplo, kg totales de una colada, no la lista de aportantes 1:1). No se le pide a Jose modificar su app durante Fase 1. La responsabilidad de continuidad operativa esta en Jose (app propia) + Johana (digita agregados en EcoBalance).

Se acuerda con Jose un mecanismo de exportacion periodica de datos de su app (Excel semanal o mensual) que Johana o David consolidan en el cierre diario de EcoBalance (OK del dia, §10.3). Este mecanismo es informal en Fase 1 — el objetivo es no romper la operacion mientras se construye la base.

**Fase 2 — Jose se integra al proyecto como co-desarrollador del modulo movil EcoBalance.**

Al iniciar Fase 2, Jose se incorpora formalmente al equipo del proyecto EcoBalance con dos objetivos:

1. **Migrar progresivamente las funciones de su app** al modulo movil offline de EcoBalance. Cada funcion migrada se retira de la app propia y se libera en el modulo movil unificado. Esto asegura que no hay perdida de funcionalidad ni salto abrupto.
2. **Co-desarrollar la experiencia movil offline para conductores en ruta.** Esta funcionalidad es 100% nueva (no existe ni en app Jose ni en EcoBalance actual) y aprovecha el conocimiento de Jose sobre offline-first, sincronizacion y captura en campo.

Se requiere sesion 1:1 previa con Jose (durante Fase 1) para:

- Mapeo exacto de funciones de la app actual → funciones destino en modulo movil EcoBalance.
- API de sincronizacion: endpoints EcoBalance que la app movil consume, formato de sync (delta vs full snapshot), resolucion de conflictos.
- Cronograma de retiro: que funcion se migra primero (postconsumo suele ser la mas simple), cuando se retira la version app-propia.
- Formato de dispositivos: Android/iOS, capacidad esperada, conectividad tipica en ruta.
- Alcance de Jose en el proyecto: horas/semana, remuneracion (interna SAC o contractada por el proyecto).

**Fase 3 — Modulo movil EcoBalance reemplaza completamente.**

Al cierre de Fase 2, todas las funciones que hoy captura la app de Jose estan en el modulo movil EcoBalance. La app propia se retira. Jose queda como referente tecnico del modulo movil dentro de SAC.

**Estado actual del anexo (2026-06-30):**

- [PENDING-CONFIRM] fecha de sesion 1:1 con Jose (necesaria antes de arrancar Fase 2).
- [PENDING-CONFIRM] si la app de Jose sigue activa durante todo el go-live de Fase 1 (recomendado si) o si se retira al momento del go-live (no recomendado — riesgo operativo).
- Si al arranque se descubre que la app de Jose es critica para operar Fase 1 (por ejemplo, si Johana no puede digitar agregados sin la app de Jose funcionando), se marca como bloqueante en §18.1.

## Anexo B. Glosario tecnico completo

Diccionario alfabetico de terminos tecnicos utilizados en este documento, con vocabulario cliente equivalente. Sirve como paridad con `propuesta-alcance-cliente.md` (que no usa vocabulario tecnico EcoBalance) y como referencia para nuevos integrantes del equipo.

**Terminos de negocio y su mapeo tecnico:**

| Termino cliente / negocio | Termino tecnico EcoBalance | Definicion |
|---------------------------|---------------------------|-----------|
| Sede | `Warehouse` (modelo SQL, id UUID) | Ubicacion operativa fisica. SAC tiene 3: CV, JM, BOG |
| Bodega | Instalacion fisica (concepto) | Sinonimo coloquial de sede. Mapeo 1:1 con Warehouse |
| Cuenta en kg de plomo / saldo en kg | `KgLedgerAccount` + `KgLedgerMovement` | Cuenta paralela al libro en pesos que trackea kg de plomo. 5 cuentas confirmadas en visita 2026-07-02 (§4.1) |
| Colada | `FurnaceCharge` + `FurnaceDischarge` (Fase 1 agregado) → `FurnaceBatch` + `BatchTracking` (Fase 2 trazabilidad 1:1) | Proceso de fundicion en horno grande. `FurnaceBatch` = entidad negocio (la colada individual); `BatchTracking` = concepto de trazabilidad genérico que liga colada → aportantes consumidos → plomo producido |
| Cristal / crisol / refinacion | `CrucibleCharge` + `CrucibleDischarge` | Proceso de refinacion posterior a la colada |
| Maquila (Willard) | `ServiceTariff` con `tariff_code=maquila_willard` + `MoneyMovement service_income` (`account_id=NULL`, CxC — §6.1) | Servicio que SAC presta a Willard: procesar su postconsumo. Cobra $2.097/kg por entrega |
| Maquila intersede | Par enlazado `internal_maquila_expense` + `internal_maquila_income` (`MoneyMovement`, sin cuenta ni tercero) | Cargo interno de JM a CV: $1.500/kg causado al envio + $300/kg causado a la salida del crisol (visita 2026-07-02) |
| Factor contractual (Willard) | `MaterialConversionFormula.conversion_formula_snapshot` | Kg de plomo a devolver por unidad/kg de input. Contractual, no fisico |
| Cuadrar / contener saldos | Conciliacion semanal | Proceso viernes con Willard: verificar que kg entregados coinciden con kg facturados |
| Abono / restitution | `KgLedgerMovement willard_delivery` en la Sale de plomo a Willard (descarga la cuenta kg que indique la remisión); la maquila/flete se CAUSAN como `service_income` sin cuenta (§6.1) y el cobro en pesos llega después como `collection_from_client` | Entrega de plomo a Willard reduce la deuda en kg pendiente |
| Aportante | Proveedor + material recibido (relacion InboundOrder ↔ Purchase) | Persona/empresa que entrega chatarra o postconsumo |
| Postconsumo | Canal de recoleccion Willard | Baterias (unidades, 7 refs) + drosses (kg, multiples refs). NO se mezclan |
| Scrap con borne | Formula dual scrap + terminal (Anexo D) | Bateria descargada: kg_plomo = (kg_scrap × factor) + kg_bornes |
| Drosses | Material tipo residuo con `MaterialConversionFormula` | Baterias descargadas troceadas. Factor por tipo (jamiche 53%, SEC ESCURRIDO 56%, SEC PINZA 59%) |
| IPC | Indice de Precios al Consumidor (Colombia) | Tarifas Willard se actualizan anualmente con IPC |
| Pasa Mano / DP / Doble Partida | `DoubleEntry` (decision #1) | Operacion de reventa sin inventario. Comisiones al comerciante — NO aplica en SAC (nomina fija) |
| Comerciales | `ThirdParty` + `MoneyMovement expense` mensual (nomina fija) | Equipo de ventas SAC. NO cobran comision por kg (Hugo 2026-06-26) |
| Green Loop | Gestor externo de recolecciones (`ThirdParty` service_provider) + caja SAC (`MoneyAccount`) + `expense_accrual` | Cerrado 2026-07-02; modelo de comision corregido en v0.6: caja provista por SAC, compras al proveedor real, comision $100/kg **causada como gasto** ([decision #83], §7.3 punto 5) |
| Utilidad cero gerencial | Politica: JM y BOG no dejan utilidad propia | Se logra via P&L por `warehouse_id` con los pares de maquila interna; el consolidado SAC excluye los tipos `internal_maquila_*` por filtro |
| Molino | `Warehouse` virtual dentro de CV (no proyecto ni tercero) | Area de trituracion en CV. Re-modelado (correccion review #2) |
| Panama / Prosperidad / Eco Alloys | `ThirdParty` con `behavior_type=generic` + CXC | Proyectos especiales con cuenta por cobrar. No requieren UN dedicada |
| Corp-* (naming) | Prefijo en `MoneyAccount.name` | Cuentas corporativas Bancolombia — sin `warehouse_id`; las cajas menores por sede SI llevan `warehouse_id` (§11.2.6) |
| Panel de excepciones | Modulo de primera clase (§10.3) | Excepciones y alarmas: solo lo anomalo; vacio en un dia normal. Reemplaza el "tablero de cuadre" del v0.4 |
| Colada agregada (Fase 1) vs 1:1 (Fase 2) | `FurnaceCharge/Discharge` vs `FurnaceBatch + BatchTracking` | Fase 1 registra kg totales; Fase 2 registra aportantes consumidos 1:1 |

**Terminos tecnicos de EcoBalance relevantes (referencia rapida):**

- `Organization` — tenant multi-tenant. SAC = 1 organization.
- `Warehouse` — bodega fisica. 3 en SAC (+ MOLINO virtual + JM-TRANSITO virtual).
- `BusinessUnit` — linea de negocio ortogonal a sede. 4 UN: Reciclaje Plomo, Maquila Willard, Reventa DP, Proyectos Especiales.
- `Material` — SKU. ~25 codigos SAC. Cada uno con `default_unit` (kg o unidad) + `business_unit_id`.
- `ThirdParty` — proveedor/cliente/servicio. `behavior_type` (material_supplier, service_provider, customer, investor, generic, provision, liability).
- `ThirdPartyCategory` — categorias con `behavior_type` (decision #33).
- `Purchase / Sale / DoubleEntry` — 3 workflows con estados uniformes (decision #2).
- `MoneyMovement` — 21 tipos + 2 nuevos SAC (`internal_maquila_expense`/`internal_maquila_income`, par enlazado) = 23. Nuevo campo `warehouse_id` nullable en Fase 1.
- `MoneyAccount` — cuenta bancaria/efectivo.
- `InventoryMovement` — movimiento de stock (in/out).
- `MaterialCostHistory` — historial de costo promedio movil (decision #9).
- `KgLedgerAccount / KgLedgerMovement` — [NUEVO] cuentas paralelas en kg.
- Par de maquila interna (`internal_maquila_expense`/`internal_maquila_income`) — [NUEVO v0.5] causacion al envio y a la salida del crisol; excluido del P&L consolidado por filtro de tipo.
- `ServiceTariff` — [NUEVO] tarifas de servicios (Willard $2.097, intersede $1.500, crisol $300, fletes $216 + $37 — sugeridas y parametrizables).
- `MaterialConversionFormula` — [NUEVO] mapeo N:1 SAC→Willard con formula versionable (append-only, snapshot al movimiento).

## Anexo C. Mapeo N:1 Materiales SAC-Willard

Tabla completa de los ~25 materiales SAC mapeados a las 7 referencias Willard. Incluye factores de conversion, unidades, y casos especiales (SEC ESCURRIDO + SEC PINZA como 2 **formulas** distintas del mismo material fisico — ambas acreditan la cuenta Willard Drosses, §6.4). La tabla vive en produccion como tabla `MaterialConversionFormula` — este anexo es el snapshot conceptual al momento de la migracion inicial.

**Estado:** [CONFIG-ARRANQUE] — la lista oficial de Willard (7 referencias + factores exactos) se solicita al arranque, no antes de la propuesta comercial (§18.2).

**Referencias Willard (7):** 07, 08, 1, 2, 3, 4, 5 (de menor a mayor tamano de bateria).

**Estructura de la tabla:**

| codigo SAC | nombre SAC | tipo | ref Willard | willard_account_subtype | factor | unidad SAC | notas |
|-----------|-----------|------|-------------|-------------------------|--------|------------|-------|
| BAT-07 | Bateria pequena (07) | bateria | 07 | — | 2.5 kg/unidad | unidad | Factor `kg_lead_per_unit` [PENDING-CONFIRM] |
| BAT-08 | Bateria estandar (08) | bateria | 08 | — | 3.2 kg/unidad | unidad | [PENDING-CONFIRM valor exacto] |
| BAT-1 | Bateria referencia 1 | bateria | 1 | — | 4.5 kg/unidad | unidad | [PENDING-CONFIRM] |
| BAT-2 | Bateria referencia 2 | bateria | 2 | — | 6.0 kg/unidad | unidad | [PENDING-CONFIRM] |
| BAT-3 | Bateria referencia 3 | bateria | 3 | — | 8.5 kg/unidad | unidad | [PENDING-CONFIRM] |
| BAT-4 | Bateria referencia 4 | bateria | 4 | — | 12.0 kg/unidad | unidad | [PENDING-CONFIRM] |
| BAT-5 | Bateria grande (5) | bateria | 5 | — | 18.0 kg/unidad | unidad | [PENDING-CONFIRM] |
| DROSS-JAMICHE | Jamiche | drosses | drosses | — | 0.53 (53%) | kg | Factor sobre peso bruto |
| DROSS-SEC-ESC | SEC ESCURRIDO | drosses | SEC | ESCURRIDO | 0.56 (56%) | kg | Mismo material fisico que SEC PINZA, distinta cuenta Willard |
| DROSS-SEC-PINZA | SEC PINZA | drosses | SEC | PINZA | 0.59 (59%) | kg | Mismo material fisico que SEC ESCURRIDO. Willard renegocio % (Hugo 2026-06-26) |
| DROSS-MOTO | Moto | drosses | moto | — | [PENDING-CONFIRM] | kg | |
| DROSS-UPS | UPS | drosses | UPS | — | [PENDING-CONFIRM] | kg | |
| DROSS-ESTACIONARIA | Estacionaria | drosses | estacionaria | — | [PENDING-CONFIRM] | kg | |
| DROSS-VASOS | Vasos | drosses | vasos | — | [PENDING-CONFIRM] | kg | |
| DROSS-SECA | Seca | drosses | seca | — | [PENDING-CONFIRM] | kg | Distinto de SEC ESCURRIDO/SEC PINZA |
| SCRAP-BORNE-* | Scrap con borne (varios) | scrap | segun ref | — | formula dual (Anexo D) | kg | Peso scrap × factor + peso bornes |
| CHATARRA-CHATRRA | Chatarra bateria propia | chatarra | (no aplica) | — | — | kg | Compra chatarra, NO postconsumo — sin cuenta Willard |

**Caso especial SEC ESCURRIDO + SEC PINZA:**

Mismo material fisico, 2 cuentas Willard. Willard renegocio el porcentaje de plomo declarado (56% → 59%) pero mantuvo las cuentas historicas separadas. Al recibir "SEC" de Willard, el sistema requiere el campo `willard_account_subtype ∈ {ESCURRIDO, PINZA}`. Quien decide: David al digitar la `InboundOrder`, basandose en la remision de Willard. Sin este campo, no se puede causar correctamente la deuda kg. **Modelo cerrado (§6.4, §11.1.1)**: una sola cuenta Willard Drosses — el subtipo escurrido/pinza discrimina la FORMULA aplicada y queda trazado en `KgLedgerMovement.conversion_formula_snapshot.willard_account_subtype`; NUNCA se crean sub-cuentas SEC (el enum de `account_type` no las contempla).

**Modelo tecnico:**

El schema canonico es el de §11.1.3 (`material_conversion_formulas`, append-only **puro**: sin `valid_from` ni `is_active` — la vigente es `MAX(created_at)` por `(material_id, willard_account_subtype)`; la referencia Willard vive dentro de `parameters`/mapeo de material, no como columna). Este anexo no duplica el SQL para evitar divergencias.

Es append-only (nunca UPDATE — solo INSERT nueva version). Al crear un `KgLedgerMovement`, se copia el `conversion_formula_snapshot` como JSON al movimiento — asi el cambio futuro de formula no recalcula kg historicos (mitigacion R7).

## Anexo D. Conversiones de scrap (matematica + JSON schemas)

Este anexo define las formulas matematicas exactas para convertir cada material fisico recibido a kg de plomo equivalente (unidad que se registra en KgLedger). Ademas provee los JSON schemas explicitos para el campo `parameters` de `MaterialConversionFormula` — critico porque el schema Pydantic valida cada tipo de formula con reglas distintas.

**Regla general:** cada `KgLedgerMovement` persiste un `conversion_formula_snapshot: JSONB` (copia del `parameters` + `formula_type` de la formula vigente al momento del movimiento). Cualquier cambio futuro a la formula NO recalcula historico. Patron identico a `MaterialCostHistory` (decision #9).

**Tipo 1 — Bateria a plomo (`battery_to_lead`).**

Aplica a las 7 referencias de bateria Willard (07, 08, 1, 2, 3, 4, 5). La bateria se cuenta por unidad, no por kg. El factor es kg de plomo declarados por Willard por unidad de bateria de esa referencia.

Formula: `kg_plomo_equiv = unidades × kg_lead_per_unit`

Ejemplo numerico: 100 unidades de bateria ref 2 con `kg_lead_per_unit=6.0` → `100 × 6.0 = 600 kg` plomo equivalente.

JSON schema:

```json
{
  "formula_type": "battery_to_lead",
  "parameters": {
    "kg_lead_per_unit": 6.0,
    "material_reference": "2"
  }
}
```

Validaciones: `kg_lead_per_unit > 0`, `material_reference ∈ ['07', '08', '1', '2', '3', '4', '5']`. Solo aplica a materiales con `default_unit='unidad'`.

**Tipo 2 — Drosses a plomo (`drosses_to_lead`).**

Aplica a materiales tipo drosses (jamiche, SEC ESCURRIDO, SEC PINZA, moto, UPS, estacionaria, vasos, seca). El drosses se recibe en kg y el factor es un porcentaje que declara Willard como plomo declarado sobre el peso bruto.

Formula: `kg_plomo_equiv = kg_bruto × lead_percentage`

Ejemplo numerico: 1000 kg de SEC ESCURRIDO con `lead_percentage=0.56` → `1000 × 0.56 = 560 kg` plomo equivalente.

JSON schema:

```json
{
  "formula_type": "drosses_to_lead",
  "parameters": {
    "lead_percentage": 0.56,
    "willard_account_subtype": "ESCURRIDO"
  }
}
```

Validaciones: `0 < lead_percentage ≤ 1.0`, `willard_account_subtype` requerido si el material tiene 2 cuentas (SEC), null en otros. Solo aplica a materiales con `default_unit='kg'`.

**Tipo 3 — Scrap con borne (`scrap_with_terminal_to_lead`).**

Aplica a baterias descargadas donde se separa el cuerpo (scrap, plomo con oxidos y sulfatos, ~50-60% plomo declarado) del terminal (bornes, plomo casi puro >90%). Ambos componentes se pesan por separado.

Formula dual: `kg_plomo_equiv = (kg_scrap × scrap_factor) + kg_bornes`

Ejemplo numerico: 1000 kg de scrap con `scrap_factor=0.56` + 50 kg de bornes → `(1000 × 0.56) + 50 = 610 kg` plomo equivalente. Los bornes se cuentan 1:1 porque son plomo casi puro (>90%) — por convencion contractual con Willard entran completos al KgLedger.

JSON schema:

```json
{
  "formula_type": "scrap_with_terminal_to_lead",
  "parameters": {
    "scrap_factor": 0.56,
    "terminal_weight_kg": 50.0,
    "material_reference": null
  }
}
```

Validaciones: `0 < scrap_factor ≤ 1.0`, `terminal_weight_kg ≥ 0`. En el momento de la captura, `terminal_weight_kg` es el peso real medido por Erwin al recibir — se persiste en el snapshot. `material_reference` puede ser null si el scrap no esta clasificado por referencia Willard.

**Tipo 4 — Custom (`custom`, escape hatch).**

Reservado para casos futuros no cubiertos por los 3 tipos anteriores. Permite formula libre expresada como string parseable + variables tipadas. NO se usa en Fase 1 — se documenta por completitud.

Formula: expresion evaluada por servicio con variables mapeadas.

JSON schema:

```json
{
  "formula_type": "custom",
  "parameters": {
    "formula_expression": "(kg_scrap * scrap_factor) + (kg_bornes * borne_purity) + adjustment_kg",
    "variables": {
      "scrap_factor": 0.56,
      "borne_purity": 0.95,
      "adjustment_kg": 0
    }
  }
}
```

Validaciones: `formula_expression` debe pasar sanitizer AST (solo operadores +, -, *, /, parentesis; solo nombres de variables definidas en `variables`). Nunca se ejecuta `eval` crudo.

**[PENDING-CONFIRM] valores exactos scrap_factor por material:**

Los factores `scrap_factor` y `kg_lead_per_unit` en las tablas anteriores son placeholders — se validan con Erwin al arranque usando al menos 5 casos reales de recepcion (peso scrap medido + peso bornes medido + kg plomo declarado por Willard al procesar). La validacion numerica se documenta en un CSV que se anexa al `MaterialConversionFormula` de origen.

**Validacion numerica (proceso operativo):**

1. Erwin proporciona 5 casos reales por material: `(kg_scrap_medido, kg_bornes_medido, kg_plomo_declarado_Willard)`.
2. Se despeja `scrap_factor` de la formula: `scrap_factor = (kg_plomo_declarado - kg_bornes_medido) / kg_scrap_medido`.
3. Si la variacion entre los 5 casos es <5%, el factor se acepta.
4. Si variacion es >5%, se levanta observacion — puede indicar mezcla de materiales o error de calibracion en bascula (ver Q19 §18.2).

## Anexo E. Proximos pasos

Estado actual: las sesiones 2026-06-26 (Hugo + Johana), 2026-06-30 (Daniel) y la **visita a planta del 2026-07-02** cerraron todas las preguntas tecnicas — incluidas Q-viva.1/2/3, P2, V4 y V8 (§18.1). Los pasos siguientes se enfocan en cerrar las 3 preguntas no tecnicas (P1, P55, P64) y arrancar Fase 1.

1. **Revision SAC del v0.5 (este documento y su espejo cliente).** Hugo, Johana, Erwin, Jose leen el documento en su capitulo relevante. Objetivo: identificar donde el modelo no refleja la realidad, que partes son ambiguas, que hay que agregar.

2. **Visita a planta realizada (2026-07-02).** Cerro el momento de la maquila interna (al envio + salida de crisol), el crisol como quinta cuenta, los sub-saldos Willard baterias por sede, Green Loop, la liquidacion por peso, el panel de excepciones con su tolerancia (3–5%), las cajas menores por sede y el nombre Eco Alloys. Queda opcional una jornada de observacion de un dia completo de operacion al arranque.

3. **Sesion tecnica con Daniel (post-visita).** Cerrar temas de implementacion:
   - Prioridad de los 6 reportes nuevos SAC (§10.2) — cual entrega primero.
   - Formato del dashboard SAC (§10.4) — mocks concretos.
   - Detalles del panel de excepciones (§10.3) — tolerancias, alertas.
   - Formato del cronograma Fase 1 semana-a-semana.

4. **Respuestas a P1, P55 y P64 (§18.2) + datos de configuracion al arranque** (factores, retenciones, maquinas/vehiculos, saldos al corte, formatos Excel — sin pedir saldos antes de la propuesta comercial). Se marca el documento como `v1.0-alcance-cerrado` cuando Hugo firme el alcance.

5. **Firma de alcance Fase 1.** Hugo firma la propuesta comercial (documento espejo `propuesta-alcance-cliente.md`) validando alcance, cronograma, precio, criterios de aceptacion.

6. **Kickoff implementacion Fase 1.** Arranca equipo BE + FE en paralelo (ver §16.1 estimacion ~10.75 SP — reducida desde ~11.5 por la simplificacion de maquila v0.5).

7. **Plan de capacitacion + operacion dual.** Simultaneo con implementacion: se prepara material de capacitacion Johana/David/Erwin/Yurani + protocolo de operacion dual (2-4 semanas post go-live).

8. **Sesiones 1:1 Fase 2 durante ejecucion Fase 1.**
   - Sesion Henry (operacion JM, coladas, refinacion).
   - Sesion Jose (app movil, plan de coexistencia — Anexo A).
   Objetivo: dimensionar Fase 2 antes de que Fase 1 cierre.

9. **UAT + go-live Fase 1.** Validacion de los 8 criterios de aceptacion (§16.1). Firma de aceptacion por Hugo. Corte a produccion.

10. **Post go-live: soporte + recoleccion de metricas.** Metricas de volumen real, discrepancias, tiempo de digitacion. Alimentan dimensionamiento definitivo de Fase 2.

11. **Kickoff Fase 2 (o Fase 3-exportacion en paralelo).** Segun prioridad de SAC.

## Anexo F. Decisiones cerradas vs asumidas (sesiones 2026-06-26, 2026-06-30 y visita a planta 2026-07-02)

Tabla explicita de cada decision arquitectonica o operativa tomada en las sesiones, con estado (CERRADA CON CITA / CERRADA SIN CITA / ASUMIDA / PENDING), fuente, fecha, y accion siguiente. Critico para auditoria de scope creep — permite al lector verificar rapidamente que asumimos y con que evidencia.

| # | Decision | Estado | Fuente / Cita | Fecha | Accion siguiente |
|---|----------|--------|---------------|-------|------------------|
| D1 | Misma sociedad/NIT para CV/JM/BOG | **CERRADA** (Daniel) | Sesion 2026-06-30 con Daniel: "una sola sociedad, mismo NIT para CV/JM/BOG". Cierra R1. Elimina modo "no eliminar pares intersede" del backlog | 2026-06-30 | Ninguna. Se implementa eliminacion inter-company automatica en consolidado SAC |
| D2 | Tarifa Willard $2.097/kg plomo entregado | **CERRADA CON CITA** | Hugo (reunion noche 2026-06-26): "2097 pesos" (10:09) | 2026-06-26 | Validar formalmente en factura Willard durante visita |
| D3 | Comisiones comerciales SAC: nomina fija, NO comision por kg | **CERRADA CON CITA** | Hugo (reunion noche 2026-06-26, 19:29): comerciales tienen nomina fija | 2026-06-26 | Ninguna |
| D4 | Tarifa maquila intersede: $1.500/kg + $300/kg si pasa crisol | **CERRADA CON CITA** | Hugo (reunion noche 2026-06-26, 19:29) | 2026-06-26 | Ninguna |
| D5 | Tarifas flete Willard: $216/kg BOG-BAQ (mensual) + flete planta-planta por entrega. La cita original de Hugo decia "$38"; la visita 2026-07-02 corrigio la tarifa vigente a **$37/kg** | **CERRADA CON CITA (tarifa corregida en visita)** | Hugo (reunion noche 2026-06-26, 00:22:55) + visita 2026-07-02 | 2026-07-02 | Ninguna |
| D6 | Politica utilidad cero gerencial JM y BOG | **CERRADA CON CITA** | Hugo (2026-06-26): "no dejamos utilidad en Bogota, simplemente lo que genere el gasto, la compra y la venta" | 2026-06-26 | Implementar toggle "consolidado / por sede" en reportes |
| D7 | 3 sedes operativas (CV, JM, BOG); otras ciudades solo proveedores | **CERRADA CON CITA** | Hugo (2026-06-26). Pereira/Medellin como centros distribucion Willard (informativos) | 2026-06-26 | [PENDING-CONFIRM] si Pereira/Medellin son centros Willard o solo proveedores |
| D8 | Drosses Willard van BOG→BAQ directo a JM (no pasan CV) | **CERRADA CON CITA** | Hugo (2026-06-26) | 2026-06-26 | Modelar `InboundOrder.goes_directly_to_jm` flag |
| D9 | IPC (no PIC) y SEC PINZA (no PIMSA) — nomenclatura correcta | **CERRADA** | Correccion terminologica identificada en review de v0.3 | 2026-06-26 | Actualizar terminologia en documento |
| D10 | Jose = "el pelado" (misma persona) | **CERRADA** (Daniel) | Sesion 2026-06-30 con Daniel: "el pelado es Jose, mismo dev del app movil actual, un solo actor" | 2026-06-30 | Anexo A y §2.4 tratarlo como UN SOLO actor |
| D11 | Yurani tiene acceso directo con rol "caja menor". Refinado en visita 2026-07-02: **una caja menor POR SEDE, todas operadas por Yurani**; el gasto hereda la sede de la CAJA usada (`MoneyAccount.warehouse_id`), no de un default del usuario | **CERRADA** (Daniel + visita) | Sesion 2026-06-30 + visita 2026-07-02. Elimina el flow "Yurani entrega Excel a Johana quien digita" | 2026-07-02 | RBAC rol "caja_menor" con scope por cuentas asignadas (§9.4, §11.2.6) |
| D12 | 6 reportes nuevos SAC (§10.2) se mantienen en Fase 1 (no diferir) | **CERRADA** (Daniel) | Sesion 2026-06-30 con Daniel | 2026-06-30 | Incluir en estimacion Fase 1 (§16.1) |
| D13 | warehouse_id persistido como columna nullable en MoneyMovement (no calcular on-the-fly) | **CERRADA** (Daniel) | Sesion 2026-06-30 con Daniel. Backwards-compatible: NULL en movimientos de los 3 clientes existentes | 2026-06-30 | Migracion Alembic + backfill NULL |
| D14 | Estados uniformes registered/liquidated/cancelled | **CERRADA — REUTILIZADO** | Decision #2 EcoBalance | 2025-* | Ninguna |
| D15 | Costo promedio movil GLOBAL (no fragmentar por sede) | **CERRADA — REUTILIZADO** | Decision #5 EcoBalance | 2025-* | Ninguna. Invariante — no romper |
| D16 | Liquidacion compras: MANUAL por Johana entrada-por-entrada | **CERRADA CON CITA** | Johana (reunion manana 2026-06-26, 10:09): "Ella siempre liquida manualmente" | 2026-06-26 | Corregir §7.2 (outline v0.3 asumia automatica) |
| D17 | Molino = bodega virtual (`Warehouse` interno de CV), NO tercero ni proyecto | **CERRADA** (correccion review #2) | Review #2 identifico gap. Modelado como `Warehouse` con `is_virtual=true` dentro de CV | 2026-06-27 | Ninguna |
| D18 | Panama/Prosperidad/Eco Alloys = ThirdParty generic con CXC (no operativos v1). Nombre "Eco Alloys" confirmado en visita (antes escrito "Equalois" segun transcripcion) | **CERRADA** (nombre) / modelado sin objecion | Outline v0.4 + visita 2026-07-02 | 2026-07-02 | Saldos exactos al corte de arranque (no se piden antes de la propuesta comercial) |
| D19 | Categorias de gasto JERARQUICAS con auxiliares por maquina/vehiculo | **CERRADA CON CITA** | Johana requiere jerarquicas — outline v0.3 asumia planas. Corregido en §9.3 | 2026-06-26 | Extender `ExpenseCategory` (decision #36 ya soporta jerarquia 2 niveles) |
| D20 | Descargo agregado en Fase 1 (no trazabilidad 1:1) | **CERRADA** (correccion review #4) | Fase 1 usa `FurnaceCharge/CrucibleCharge` sin `BatchTracking`. Fase 2 agrega trazabilidad | 2026-06-27 | Explicito en §7.4 y §16.2 |
| D21 | Un solo MoneyMovement expense_accrual en maquila intersede (no doble MM) | **SUPERSEDIDA en v0.5** (visita 2026-07-02, Q-viva.1) | El mecanismo vigente es el **par enlazado** `internal_maquila_expense` + `internal_maquila_income` (§5.2): el cliente exige ver el gasto de CV y el ingreso de JM como asientos reales por sede; el consolidado los excluye por filtro de tipo. Los atributos que D21 corrigio (`third_party_id=NULL`, `business_unit_id` heredada) se conservan en ambos lados del par | 2026-07-02 | §5.2, §5.3 |
| D22 | Willard tiene 1 balance en pesos + 2 cuentas kg (dimension separada) | **CERRADA** (correccion review #2; precision v0.5) | Distincion pesos vs kg. `ThirdParty.balance` de Willard es unico. Las cuentas kg se separan por `account_type` (baterias/drosses) y los sub-saldos de baterias por `warehouse_id` (§11.1.1); el `willard_account_subtype` escurrido/pinza discrimina solo la FORMULA dentro de drosses (§6.4), nunca cuentas | 2026-07-02 | Ninguna |
| Q-viva.1 | Momento causacion maquila intersede: **AL ENVIO** ($1.500/kg de plomo equivalente al confirmar el traslado CV→JM) + adicional **a la salida del crisol** ($300/kg). Par de MMs internos enlazados (gasto CV / ingreso JM). Se descarta el modelo de causacion diferida FIFO del v0.4 — simplifica el diseño | **CERRADA** (visita) | Visita a planta 2026-07-02 (Johana en sitio) + WhatsApp con Hugo — validado por ambos | 2026-07-02 | Ninguna. Ver §5 |
| Q-viva.2 | 5 cuentas KgLedger — **crisol confirmado como cuenta separada** del horno grande. Razon del cliente: medir la eficiencia de cada etapa (horno: entra scrap/lodo/retal, sale plomo crudo en lingote; crisol: entra crudo, sale puro) | **CERRADA** (visita) | Visita a planta 2026-07-02 | 2026-07-02 | Ninguna. Ver §4.1 |
| Q-viva.3 | Green Loop: caja provista por SAC; compras en ruta a nombre del proveedor real, pagadas desde esa caja; rendicion de cuentas contra la caja; comision **$100/kg recolectado** por consignacion aparte, causada como **gasto** (`expense_accrual`, decision #83 — v0.5 decia "prorrateada al costo via PurchaseCommission", corregido en v0.6) | **CERRADA** (visita) | Visita a planta 2026-07-02 | 2026-07-02 | Ninguna. Ver §7.3 punto 5 |
| D23 | Willard Baterias con **sub-saldos por sede** (Barranquilla / Bogota): lo que entra por CV suma a BAQ (el que cuadra Johana); lo de BOG pasa a BAQ cuando el material llega fisicamente a Circunvalar (evento de traslado). Deuda de referencia: 422 ton — 131 BAQ, 48 BOG, resto en centros Willard informativos | **CERRADA** (visita) | Visita a planta 2026-07-02 (Johana) | 2026-07-02 | Detalle del cuadre nacional con el coordinador de postconsumo al arranque |
| D24 | La **remision** de cada entrega a Willard define si el abono descarga baterias o drosses (dato del documento, no decision al liquidar). Drosses SIEMPRE ingresan por Juan Mina | **CERRADA** (visita) | Visita a planta 2026-07-02 | 2026-07-02 | Ninguna. Ver §4.3 |
| D25 | El tablero de cuadre se reenfoca a **panel de excepciones y alarmas**: con captura unica el cuadre renglon-por-renglon desaparece por construccion. Traslados con cantidad despachada Y recibida; tolerancia **3–5% configurable** con lo recibido como fuente de verdad; acta semanal Willard con detalle por entrega (fecha, remision, kg), manejada por el coordinador de postconsumo nacional | **CERRADA** (visita) | Visita a planta 2026-07-02 (Johana) | 2026-07-02 | Ninguna. Ver §10.3 |
| D26 | Momentos de facturacion Willard: maquila $2.097/kg y flete planta $37/kg **por cada entrega**; flete BOG-BAQ $216/kg **mensual**; transporte fisico BOG-BAQ **tercerizado** (gasto variable al facturar la transportadora). Todas las tarifas sugeridas y parametrizables con vigencia historica | **CERRADA** (visita) | Visita a planta 2026-07-02 | 2026-07-02 | Ninguna. Ver §6.1, §6.2 |
| D27 | Liquidacion por peso (P2): la composicion se conoce al recibir; el valor pagado se reparte entre referencias por **costo promedio historico**. Hugo: *"Esa es la regla."* Liquidacion manual de Johana | **CERRADA CON CITA** (visita) | Visita a planta 2026-07-02 (Hugo) | 2026-07-02 | Ninguna. Ver §7.2 |
| D28 | Transporte CV→JM con **carros propios** — no hay flete en ese tramo; la maquila $1.500/kg es solo procesamiento | **CERRADA** (visita) | Visita a planta 2026-07-02 | 2026-07-02 | Ninguna. Ver §6.2 |

**Convencion de estados:**

- **CERRADA CON CITA:** decision con cita textual del cliente en transcripcion. Riesgo bajo. Solo se valida formalmente.
- **CERRADA (Daniel / correccion review):** decision cerrada por Daniel en sesion interna o por correccion de review adversarial. Riesgo bajo. Consenso interno documentado.
- **CERRADA — REUTILIZADO:** decision heredada de EcoBalance (decisiones #1-#55 del CLAUDE.md). Riesgo cero — no requiere validacion.
- **ASUMIDA:** decision tomada por el outline sin cita explicita del cliente. Riesgo medio. Validar en visita.
- **PENDING — BLOQUEANTE:** contradiccion o ambiguedad entre fuentes. Riesgo alto. Cerrar en visita antes de kickoff.
- **PENDING — no bloqueante:** decision pendiente pero no afecta arquitectura. Riesgo bajo. Se resuelve en implementacion.

**Total decisiones documentadas:** 31 (22 previas + Q-viva.1/2/3 cerradas en la visita + D23–D28 nuevas de la visita). **Ratio de cierre tecnico: 100%** — la visita a planta del 2026-07-02 cerro todos los PENDING tecnicos. Quedan abiertas solo P1 (volumenes pico), P55 (fecha de corte) y P64 (modalidad comercial), ninguna tecnica (§18.2).