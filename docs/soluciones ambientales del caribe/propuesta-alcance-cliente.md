# Propuesta de Alcance Funcional — Soluciones Ambientales del Caribe (SAC)

**Versión:** 0.5 — Actualizada con los resultados de la visita a planta (2 de julio de 2026)
**Fecha:** Julio 2026
**Autor:** Eduardo Chain

> **Sobre este documento.** Es un resumen ejecutivo de lo que el sistema entregará en cada una de las tres fases. Está pensado para que la gerencia y los responsables operativos de SAC puedan leerlo en una sentada, decidir si el alcance refleja lo que necesitan, y responder las preguntas críticas para cerrar cada fase. Existe una **especificación funcional detallada** que acompaña este documento — la usamos el equipo de implementación; si en algún punto se necesita el detalle de un módulo, flujo o regla específica, está disponible. Aquí está lo que SAC necesita para decidir.

> **Qué cambió respecto a la versión 0.4.** Esta versión incorpora lo cerrado en la visita a planta del 2 de julio de 2026 — sesión de trabajo con Johana, con las decisiones validadas también por Hugo:
>
> - **Modelo de maquila interna cerrado**: $1.500/kg de plomo equivalente al enviar de Circunvalar a Juan Mina, y $300/kg al salir del crisol — en ambos casos gasto de Circunvalar e ingreso de Juan Mina. Validado por Hugo y por Johana.
> - **Cinco cuentas en kilogramos confirmadas** — el crisol es cuenta separada para medir la eficiencia de cada etapa (al horno entra scrap, lodo, retal; sale plomo crudo en lingote; al crisol entra plomo crudo y sale plomo puro). La cuenta Willard baterías se lleva con **sub-saldos por sede**: lo de Bogotá pasa al saldo de Barranquilla cuando el material llega físicamente a Circunvalar.
> - **Tarifas corregidas y con momento de causación definido**: flete planta–Willard $37/kg (antes $38); maquila Willard y flete planta se facturan por cada entrega; el flete Bogotá–Barranquilla ($216/kg) se factura mensual a Willard y el transporte de ese tramo es tercerizado (gasto variable). Todas las tarifas son valores sugeridos y parametrizables.
> - **Green Loop definido**: opera una caja provista por SAC, compra a nombre del proveedor real y cobra comisión de $100/kg liquidada por consignación aparte.
> - **El "tablero de cuadre" se simplifica a panel de excepciones**: el sistema concilia solo cada transacción; el panel muestra únicamente diferencias fuera de tolerancia (3–5% configurable, con lo recibido como fuente de verdad) y operaciones incompletas al cierre.
> - **Liquidación por peso cerrada**: la composición se conoce al recibir y el valor pagado se reparte entre las referencias por costo promedio histórico.
> - **Cajas menores**: una por sede, todas operadas por Yurani con su propio acceso.
> - **Eco Alloys** — nombre correcto del proyecto de aluminio (antes escrito con otra grafía).
> - Solo quedan abiertas la fecha de corte, los volúmenes pico y la modalidad comercial (sección 2.9).

---

## Contenido

1. **Visión del sistema** — qué problema resuelve y cómo se entrega
2. **Fase 1 — Cuadre operativo y financiero unificado** `[prioridad de cierre]`
3. **Fase 2 — Trazabilidad de planta y movilidad en campo**
4. **Fase 3 — Cierre comercial y regulatorio**
5. **Próximos pasos**

---

## 1. Visión del sistema

### 1.1 Qué problema resolvemos

Hoy SAC controla la operación con varios cuadros Excel paralelos (planta, molino, Circunvalar, exportaciones, postconsumo) más un cuadro de cuentas externo, reconciliados a mano por Johana. La doble y triple digitación es estructural: el operario de patio anota la entrada en su cuadro, Erwin la vuelve a digitar en el inventario general, y Johana la digita una tercera vez para liquidar la compra. Cualquier error en una de las tres digitaciones descuadra el balance del día.

En palabras de Hugo: *"Antes la base era tan poca, era muy fácil mantener todo el día. Ahora, como es tanto el volumen, la información es tanta, ya no somos capaces y mantenemos atrasados con la información."*

Y Johana: *"Tengo que tomar renglón por renglón y validar que todo haya sido bien liquidado y bien anotado en los otros cuadros, porque si no se me descuadra el balance, porque como todo está manual, ese es el tema."*

El sistema absorbe ese trabajo de captura y cuadre. Erwin queda liberado de la digitación masiva para auditar y validar. Johana deja el cuadre renglón por renglón: el sistema concilia solo y ella revisa el panel de excepciones para concentrarse en las decisiones de cierre.

### 1.2 Visión del sistema

El sistema apunta a ser **la plataforma única de gestión integral del negocio de SAC**, no un Excel más sofisticado. La información se captura una sola vez en el punto donde ocurren las operaciones; los reportes financieros y operativos se cierran en tiempo real sin requerir cuadres manuales paralelos; el alcance crece por fases incorporando, una a una, las distintas etapas del negocio: desde lo **operativo** (recepción, transformación, fundición, refinación), pasando por lo **comercial** (ventas, abonos a Willard, exportaciones), hasta lo **financiero** (tesorería en pesos y en kilogramos de plomo) y lo **contable** (Estado de Resultados, Balance, conciliaciones, cierres periódicos).

Cada fase entrega valor utilizable desde el primer día y construye sobre la anterior sin romper lo ya implementado.

### 1.3 Capacidades que entrega el sistema

1. **Captura única en el punto donde ocurre el hecho.** Cuando entra un camión al patio, la orden de entrada se hace una sola vez en el sistema; alimenta automáticamente el inventario y, según el tipo de entrada, la deuda en plomo a Willard; la cuenta del proveedor se afecta al liquidar esa entrada (liquidación manual de Johana — sin re-digitación en ningún paso). Cuando una ruta de recolección trae material de varios proveedores, el sistema registra **una entrada por proveedor** — no una entrada global de la ruta.
2. **Inventarios unificados multi-sede.** Las bodegas de Circunvalar, Juan Mina y Bogotá viven en un mismo sistema con visibilidad consolidada y por sede.
3. **Saldos paralelos en pesos y en kilogramos de plomo.** El sistema mantiene cuentas en pesos (CXP, CXC, caja, bancos) y **cinco cuentas independientes en kilogramos de plomo** (confirmadas en la visita a planta): Willard baterías, Willard drosses, la deuda interna intersede, el horno grande y el crisol. El detalle está en la sección 2.3.
4. **Visión gerencial por sede sin partir la contabilidad.** Las tres sedes (Circunvalar, Juan Mina y Bogotá) son la misma sociedad con el mismo NIT. El sistema muestra caja por sede, inventario por sede, gastos por sede y resultado por sede, pero el balance oficial sigue siendo uno solo, consolidado. La "utilidad cero" de Juan Mina y Bogotá es una política gerencial de visualización, no una separación contable.
5. **Trazabilidad de coladas.** Cada colada del horno grande es un lote con identidad propia, vinculado a las remisiones de aportantes que consumió y al plomo crudo que produjo (Fase 2).
6. **Cuadre automático con panel de excepciones.** Al capturarse todo en un solo sistema, el cuadre entre cuadros deja de existir como tarea: cada transacción se concilia sola. Lo que queda para el ojo humano es un **panel de excepciones y alarmas**: diferencias entre lo despachado y lo recibido fuera de tolerancia (3–5%, configurable), operaciones incompletas al cierre y diferencias contra arqueos físicos. En un día normal el panel está vacío. Johana revisa solo lo anómalo y firma el "OK del día".

### 1.4 Mapa general de operaciones

El material fluye en una sola dirección: **Circunvalar → Juan Mina**. La información sobre saldos y deudas en plomo fluye en ambos sentidos: cada despacho de aportantes desde Circunvalar genera una obligación que Juan Mina debe pagar con producción posterior; cada entrega a Willard descarga la deuda postconsumo.

> *[Insertar aquí el diagrama del mapa general de operaciones — flujo desde compra propia / postconsumo / recolección en ruta hasta venta nacional, abono a Willard, exportación y refinación.]*

**Cómo nacen y mueren las deudas en plomo (kg) sobre este flujo:** cada despacho de aportantes Circunvalar → Juan Mina alimenta la **cuenta intersede**, que se descarga cuando sale el plomo procesado. Cada entrada postconsumo Willard alimenta la cuenta que corresponda — **baterías** (por Circunvalar o Bogotá) o **drosses** (por Juan Mina) —, y ambas se descargan al entregar plomo en abono. El horno grande y el crisol mantienen cada uno su propio saldo de proceso — cuentas separadas para medir la eficiencia de cada etapa. El detalle de las cuentas y de cómo cada evento las afecta está en la sección 2.3.

### 1.5 Roadmap de las tres fases

#### FASE 1 — Cuadre operativo y financiero unificado `[PRIORIDAD DE CIERRE]`

| | |
|---|---|
| **Resuelve** | Triple digitación, cuadre manual de Johana, deuda Willard. |
| **Entrega** | Captura única, inventarios unificados en las tres sedes, tesorería en pesos y en kg (cinco cuentas de plomo), ventas + abonos Willard, panel de excepciones + cuadre semanal Willard, visión gerencial por sede, cajas menores por sede, reportes esenciales + 6 reportes propios de SAC. |
| **NO incluye** | Trazabilidad de colada, móvil del conductor, exportaciones, regulatorios, gestión completa de subproductos. |
| **Para cerrar** | 3 preguntas abiertas (volúmenes pico, fecha de corte, modalidad comercial). Las preguntas técnicas quedaron cerradas en la visita del 2 de julio de 2026. |

*▼ Fase 1 cerrada y operando*

#### FASE 2 — Trazabilidad de planta y movilidad en campo

| | |
|---|---|
| **Resuelve** | Trazabilidad uno-a-uno de colada, conductor sin papel, fundición y refinación. |
| **Entrega** | Coladas, refinación, móvil offline del conductor, integración de la app móvil de José (co-desarrollo), insumos y fundentes con costo integrado, rendimiento por horno y operador, conciliación postconsumo. |
| **NO incluye** | Exportaciones, gestión completa de subproductos, reportes regulatorios. |
| **Para cerrar** | 3 preguntas críticas (Henry + José). |

*▼ Fase 2 cerrada y operando*

#### FASE 3 — Cierre comercial y regulatorio

| | |
|---|---|
| **Resuelve** | Exportaciones complejas, subproductos con disposición regulada, reportes regulatorios. |
| **Entrega** | Exportaciones con precio provisional y ajuste, subproductos con disposición a gestor, dashboards consolidados, reportes regulatorios. |
| **Para cerrar** | 2 preguntas críticas. |

> **Sobre cronograma.** Este documento describe únicamente **alcance funcional y criterios de aceptación**. Los tiempos, hitos cronológicos y modelo comercial se cuantifican en una **propuesta comercial separada** una vez cerrado este alcance funcional.

---

## 2. Fase 1 — Cuadre operativo y financiero unificado `[PRIORIDAD CIERRE]`

### 2.1 Qué problema resuelve esta fase

La triple digitación estructural y el cuadre manual renglón por renglón que hoy hace Johana. Al cierre de Fase 1, un día completo de operación de SAC se captura sin recurrir a cuadros Excel paralelos.

### 2.2 Qué módulos contiene

| # | Módulo | Qué hace |
|---|---|---|
| 1 | **Recepción y orden de entrada** | Captura única en el patio: cubre compra propia, postconsumo Willard, drosses, recolección en ruta y reventa de batería. Cuando una ruta (ej. Green Loop) trae material de varios proveedores, se registra **una entrada por proveedor** — confirmado por Hugo y Johana. Reemplaza las tres digitaciones de hoy. |
| 2 | **Captura de postconsumo en patio** | El operador de báscula crea la orden desde el acta de papel que entrega el conductor. La captura en ruta desde el celular entra en Fase 2. |
| 3 | **Maestros** | Catálogos de proveedores, clientes, maquilantes (Willard con tabla de factores por referencia, versionada), conductores, vehículos, referencias, materiales, sedes, bodegas, hornos, cuentas bancarias y caja, tarifas de maquila y fletes con vigencia histórica, y máquinas/equipos para el detalle de gastos. |
| 4 | **Compras y liquidación de chatarra** | **Liquidación manual**: Johana liquida cada entrada confirmando precios — el sistema no liquida automático. Retenciones aplicables (estructura preparada para ReteFte/ICA), pago por tesorería. Soporte para **liquidación por peso** con la regla cerrada en la visita: la composición se conoce al recibir y el valor pagado se reparte entre las referencias según su costo promedio histórico. **Green Loop** opera con una caja provista por SAC — sus compras en ruta quedan a nombre del proveedor real y se pagan desde esa caja; su comisión ($100/kg, parametrizable) se liquida por consignación aparte y se incorpora al costo del material. Los comerciales tienen **salario fijo mensual** — no se liquidan comisiones por kg; su costo se maneja como gasto de nómina. |
| 5 | **Maquila y postconsumo Willard** | **Dos cuentas corrientes en kilogramos de plomo** con Willard — baterías y drosses/materiales, que no pueden ir mezclados. La deuda se calcula con el **factor contractual por referencia** (7 referencias). Los centros de distribución Willard (Pereira, Medellín, Montería, Santa Marta, etc.) se registran como dato informativo — las baterías entran físicamente por Circunvalar o Bogotá; los drosses, directamente por Juan Mina. La remisión de cada entrega define si el abono va a la cuenta de baterías o a la de drosses. Cuadre semanal con acta firmada. |
| 6 | **Inventarios multi-sede** | Una sola vista de stock por material, bodega y sede (Circunvalar, Juan Mina, Bogotá). Bodegas virtuales para material en tránsito entre sedes; los traslados registran **cantidad despachada y cantidad recibida** — dentro de la tolerancia el ajuste es automático tomando **lo recibido como fuente de verdad**, por encima genera alarma. Arqueos físicos con aprobación de supervisor. El Molino es un área operativa de Circunvalar — su material vive como inventario en trituración. |
| 7 | **Transformaciones primarias (molino y picado manual)** | Operación atómica que descarga la batería entrada y carga los subproductos resultantes, con balance y manejo de merma. |
| 8 | **Subproductos en su forma básica** | Inventario propio por subproducto (plástico, electrolito, separador, tapas, cajas acrílicas, escoria, polvoducto) y venta simple. Disposición regulada a gestor entra en Fase 3. |
| 9 | **Ventas nacionales, entregas a Willard y reventa de batería** | Las tres operaciones comerciales reales de SAC. |
| 10 | **Tesorería** | Libro en pesos (cuentas bancarias, caja, terceros) + libro en kilogramos de plomo con **cinco cuentas** (ver 2.3). Tarifas de maquila y fletes con vigencia histórica: si cambian (ajuste anual por IPC), las operaciones pasadas conservan la tarifa de su momento. |
| 11 | **Cajas menores con acceso directo** | Hay **una caja menor por sede**, todas operadas por la administradora (Yurani) con su propio acceso al sistema. Cada gasto queda asignado automáticamente a la sede de la caja que use, con categoría, subcategoría y equipo. Ya no pasa por digitación de Johana. |
| 12 | **Gastos con detalle por máquina/vehículo** | Las categorías de gasto admiten hasta tres niveles: categoría → subcategoría → equipo específico (ej: Mantenimiento → Maquinaria → Montacargas-1). Requerimiento explícito de Johana. |
| 13 | **Proyectos especiales como cuentas de tercero** | Panamá (equipos trasladados — cuenta por cobrar), Prosperidad (construcción para unificar Circunvalar y Juan Mina) y Eco Alloys (proyecto de aluminio — cuenta por cobrar superior a $20.000 millones) se manejan como cuentas de tercero con estado de cuenta completo: la inversión queda rastreable sin ensuciar la operación diaria. |
| 14 | **Reportes** | Ver tablas en 2.6. |
| 15 | **Panel de excepciones y alarmas** | El sistema concilia cada transacción sola; el panel muestra únicamente lo anómalo: diferencias despacho vs recepción fuera de tolerancia (3–5% configurable), operaciones sin liquidar al cierre y diferencias de arqueo. Johana revisa las excepciones y firma el "OK del día". |
| 16 | **Administración** | Usuarios, roles personalizables, permisos granulares por sede, parámetros (factores y tarifas con versionado, tolerancias), bitácora de auditoría, cierre de periodo. |

### 2.3 El modelo de las cuentas en kilogramos de plomo en detalle

Este es el corazón del cuadre operativo de SAC y, por su importancia, lo describimos aquí con el nivel de detalle que requiere la validación por parte de Johana. El modelo queda en **cinco cuentas**, confirmadas en la visita a planta del 2 de julio de 2026.

**Las cinco cuentas:**

| # | Cuenta | Qué representa | Notas |
|---|---|---|---|
| 1 | **Willard — postconsumo baterías** | Kg de plomo que SAC debe a Willard por baterías recibidas (unidades × factor por referencia) | **Sub-saldos por sede**: lo que entra por Circunvalar suma al saldo Barranquilla (el que cuadra Johana); lo que entra por Bogotá suma al saldo Bogotá, y pasa al de Barranquilla **cuando el material llega físicamente a Circunvalar** |
| 2 | **Willard — drosses y materiales** | Kg de plomo que SAC debe a Willard por drosses y materiales recibidos | Separada de la de baterías — Johana confirmó que "no pueden ir mezclados" |
| 3 | **Intersede** | Kg de plomo aportante que Circunvalar (o Bogotá) despachó a Juan Mina y que aún no se ha pagado con producción | Se descarga cuando sale el plomo procesado |
| 4 | **Horno grande** | Kg de plomo en proceso dentro del horno grande de Juan Mina | Entra scrap, lodo, retal y demás aportantes (cada uno con rendimiento distinto); sale plomo crudo en lingote |
| 5 | **Crisol** | Kg de plomo en proceso en el crisol de refinación (entra plomo crudo, sale plomo puro) | Cuenta separada del horno — confirmado en la visita: permite medir la eficiencia de cada etapa |

**La deuda actual con Willard:** 422 toneladas de plomo — 131 en el saldo Barranquilla, 48 en el saldo Bogotá y el resto distribuido en otros centros de distribución de Willard. Los saldos Barranquilla y Bogotá son **sub-saldos de la misma cuenta**: Johana cuadra el de Barranquilla; el de Bogotá pasa al de Barranquilla a medida que el material llega físicamente a Circunvalar. El cuadre con Willard consolida el saldo nacional *(detalle a confirmar con el coordinador de postconsumo)*. Los centros de distribución son un dato **informativo** que Willard usa para rastrear el origen del material; para SAC no son bodegas: las baterías entran físicamente por Circunvalar o Bogotá, y los drosses por Juan Mina.

**El factor contractual manda sobre la deuda.** Cuando Willard entrega material, la deuda en kg se calcula con el **factor contractual por referencia** (7 referencias Willard). Si la planta extrae más o menos plomo del que dice el factor, esa diferencia es de SAC — su inventario gana o pierde —, pero la deuda con Willard no cambia. Materiales como "Seco escurrido" (factor 0,56) y "Seco pinza" (factor 0,59) son referencias distintas con factores distintos, aunque para SAC sean físicamente el mismo material. La tabla completa de factores vigente se recoge al arranque.

**Un solo estado de cuenta en pesos.** Willard sigue siendo un único tercero con un único estado de cuenta en pesos; las dos cuentas en kilogramos son una dimensión adicional que se consulta junto al estado de cuenta, no una duplicación del tercero.

**Cómo cada evento alimenta y descarga las cuentas:**

| Evento | Willard baterías | Willard drosses | Intersede | Horno grande | Crisol |
|---|---|---|---|---|---|
| Entrada postconsumo baterías (Circunvalar o Bogotá) | **+** (unidades × factor) | — | — | — | — |
| Entrada drosses/materiales Willard (Juan Mina) | — | **+** (kg × factor) | — | — | — |
| Compra propia de batería | — | — | — | — | — |
| Despacho aportantes Circunvalar → Juan Mina | — | — | **+** (kg × factor) | — | — |
| Llegada física de baterías Bogotá → Circunvalar | **mueve entre sub-saldos** (Bogotá −, Barranquilla +) | — | — | — | — |
| Carga de horno en Juan Mina | — | — | — | **+** (kg cargados) | — |
| Cierre de colada (produce plomo crudo) | — | — | — | **−** | — |
| Paso de plomo crudo al crisol | — | — | — | — | **+** |
| Cierre de refinación (produce plomo refinado) | — | — | — | — | **−** |
| Salida de plomo procesado desde Juan Mina | — | — | **−** (consume los kg pendientes más antiguos) | — | — |
| Entrega de plomo a Willard (abono) | **−** | **−** | — | — | — |

*El abono a Willard descarga la cuenta de baterías o la de drosses según lo defina la **remisión** de la entrega.*

**La maquila interna — modelo cerrado en la visita** *(validado por Hugo y por Johana)*:

1. **Al enviar** material de Circunvalar a Juan Mina se mueve la **deuda en kilogramos** (cuenta intersede) **y se causa la maquila del horno**: $1.500 por kg de **plomo equivalente** (aplicando el factor del material) — gasto para Circunvalar, ingreso para Juan Mina. El transporte de este tramo es con carros propios, sin cobro de flete.
2. **Al salir el material del crisol** se causa el adicional de refinación: $300/kg — gasto para Circunvalar, ingreso para Juan Mina.

Así, el resultado por sede de Juan Mina se mide con sus maquilas internas como ingreso contra sus costos de operación — eso es la política de "utilidad cero". En el balance consolidado de SAC estos cargos internos se eliminan entre sí, porque las sedes comparten NIT.

**Tarifas confirmadas** (reunión del 26 de junio y visita del 2 de julio de 2026):

| Concepto | Tarifa vigente | Momento de causación | Naturaleza |
|---|---|---|---|
| Maquila interna (horno) | $1.500/kg de plomo equivalente | Al enviar de Circunvalar a Juan Mina | Gasto Circunvalar / ingreso Juan Mina |
| Adicional crisol | $300/kg | Al salir el material del crisol | Gasto Circunvalar / ingreso Juan Mina |
| Maquila Willard | $2.097/kg de plomo entregado | A la entrega — se factura **por cada entrega** | Ingreso de SAC (paga Willard) |
| Flete planta – Willard | $37/kg de plomo entregado | A la entrega, junto con la maquila | Ingreso de SAC (paga Willard) |
| Flete Bogotá – Barranquilla | $216/kg de batería trasladada | **Mensual**, al facturar a Willard | Ingreso de SAC (paga Willard) |
| Transporte Bogotá – Barranquilla | Variable por viaje | Cuando factura la transportadora | Gasto de SAC (transporte tercerizado) |
| Comisión Green Loop | $100/kg recolectado | Por recolección; consignación aparte | Gasto de SAC (se incorpora al costo del material) |

Todas las tarifas son **valores sugeridos y parametrizables** — se ajustan cuando corresponda (típicamente por IPC anual) y viven en el sistema con **vigencia histórica**: si cambian, las operaciones pasadas conservan la tarifa de su momento.

**Aclaración Fase 1 vs Fase 2.** En Fase 1, el cierre de colada se registra como un evento agregado (entra el lote del día, sale plomo crudo) y descarga las cuentas con base en proporciones promedio. En Fase 2, el cierre de colada gana **trazabilidad uno-a-uno** con referencia explícita a las remisiones de aportantes consumidos. Las cuentas se siguen llevando igual; lo que cambia es la granularidad del soporte documental.

### 2.4 El cuadre automático y el panel de excepciones en detalle

Con la captura única, el cuadre que hoy hace Johana renglón por renglón desaparece por construcción: lo que sale de un cuadro ya no puede dejar de entrar en el otro, porque es un solo sistema. Lo que queda para el ojo humano es un **panel de excepciones**: el sistema concilia cada transacción sola y muestra únicamente lo que se salió de tolerancia o quedó incompleto. En un día normal, el panel está vacío. Johana lo confirmó en la visita: lo que quiere ver es "un cuadro o alarma cuando haya una diferencia entre entrada y salida".

**Qué detecta el panel:**

- Diferencias entre lo despachado y lo recibido por encima de la tolerancia configurada (3–5%, según definió Johana). Dentro de la tolerancia, el ajuste es automático tomando **lo recibido como fuente de verdad**.
- Diferencias entre conteo de unidades en la orden de entrada y conteo en la liquidación de la compra.
- Saldos cruzados inconsistentes: deuda Willard vs entregas registradas, deuda intersede vs despachos y salidas del día.
- Compras o ventas registradas sin liquidar al cierre del día.
- Movimientos de inventario con costo cero, sin tercero asignado o sin sede de origen/destino cuando aplica.
- Diferencias entre los cuadros Excel actuales de Johana y el sistema durante el periodo de migración inicial.
- Despachos intersede cuyos kilogramos o cargos de maquila causados no cuadran entre sí (reconciliación diaria intersede).

**El flujo de trabajo por cada discrepancia:**

1. Cada discrepancia detectada se materializa como una **tarea** con tipo, severidad, monto o kg involucrado, sede y responsable sugerido.
2. Johana o el supervisor de planta abre la tarea y elige una de tres resoluciones: **justificar** (registrar nota explicativa que cierra la tarea), **corregir** el documento origen (genera el ajuste con bitácora), o **solicitar arqueo físico** (pone la tarea en espera hasta que el supervisor de bodega confirme el conteo).
3. La acción de resolución queda en la bitácora con usuario, fecha, motivo y trazabilidad al documento afectado.
4. Cuando todas las discrepancias del día quedan resueltas, Johana firma el **"OK del día"**. Después de la firma, editar operaciones de ese día requiere permiso de administrador y deja registro explícito en la bitácora.

**El "OK del viernes".** El cuadre semanal con Willard — el ritual de cada viernes — genera desde el sistema un **acta firmada e inmutable**: saldo de apertura, entradas, entregas y saldo de cierre por cada cuenta Willard, **con el detalle de cada entrega (fecha, remisión, kilogramos)** — porque la diferencia típica con Willard es una entrega que un lado ya registró y el otro no. SAC envía el cuadro (lo maneja el coordinador de postconsumo a nivel nacional) y lo concilia con Willard. Una vez firmada, el acta queda bloqueada a edición salvo administrador con bitácora.

**Lo que NO hace el panel:** decidir por SAC qué resolver. La inteligencia operativa sigue siendo de Johana; el sistema le ahorra el trabajo de **encontrar** la discrepancia y le ofrece el contexto para **resolverla** rápido.

### 2.5 Qué valor concreto entrega Fase 1

- Un día completo de operación de SAC se captura sin recurrir a cuadros Excel paralelos.
- La doble y triple digitación queda eliminada por construcción.
- La deuda en plomo con Willard queda cuadrada en tiempo real, separada en baterías y drosses, y con acta semanal firmada.
- La gerencia consulta caja, inventario, gastos y resultado **por sede**, con un solo balance oficial consolidado.
- Johana deja el cuadre renglón por renglón: el sistema concilia solo, y ella revisa únicamente el panel de excepciones.
- Erwin queda liberado de la digitación masiva para auditar y validar.
- Yurani captura los gastos de las cajas menores de cada sede directamente, con detalle por máquina o vehículo, sin pasar por Johana.

### 2.6 Reportes que SAC recibe en Fase 1

**Los 17 reportes esenciales:**

| Reporte | Audiencia | Qué muestra |
|---|---|---|
| Dashboard ejecutivo | Gerencia | Caja por sede; inventario por sede; resultado por sede; deuda Willard con antigüedad; deuda intersede; CXP y CXC abiertas; alertas de cuadre del día |
| Estado de Resultados (P&L) | Gerencia, contador | Ingresos por canal, costo de la mercancía vendida, gastos operativos, utilidad |
| P&L mensual comparativo | Gerencia | Comparativo mes a mes con día de corte configurable |
| Balance general | Gerencia, contador | Activos, pasivos, patrimonio, P&L acumulado — un solo balance consolidado SAC |
| Balance detallado | Gerencia, contador | Balance con desglose por tercero y sub-categorías |
| Estado de la deuda en plomo Willard | Gerencia, coord. postconsumo | kg debidos por cuenta (baterías / drosses) y por sub-saldo (Barranquilla / Bogotá), acumulaciones, abonos, antigüedad, factor aplicado |
| Estado de la deuda intersede | Gerencia, liquidador | kg debidos por la planta a Circunvalar |
| Cuadre de inventario por sede | Liquidador, auditor | Stock por material y bodega; valor a costo; movimientos del periodo; diferencias |
| Antigüedad de cartera por cobrar | Liquidador, gerencia | CXC abiertas por cliente, por rango de antigüedad |
| Antigüedad de cartera por pagar | Liquidador, gerencia | CXP abiertas por proveedor |
| Compras del periodo | Liquidador, comercial | Por proveedor, referencia, fecha; exportable a Excel detallado por línea |
| Ventas del periodo | Comercial, gerencia | Por cliente, material, tipo; exportable a Excel detallado por línea |
| Reporte de gastos | Liquidador, contador | Gastos desagregados por línea de negocio, sede, categoría, subcategoría y equipo específico |
| Flujo de caja | Gerencia, liquidador | Entradas y salidas por cuenta y categoría |
| Estado de cuenta de tercero | Liquidador, comercial | Movimientos en pesos y en kg de plomo cuando aplica — incluye proyectos especiales (Panamá, Prosperidad, Eco Alloys) |
| Histórico de factores y tarifas | Administrador, gerencia | Factores Willard y tarifas de maquila/fletes vigentes y anteriores, con fechas y aprobador |
| Panel de excepciones del día | Liquidador, supervisores | Excepciones abiertas y resueltas por tipo, severidad y asignado |

**Los 6 reportes nuevos específicos del negocio SAC:**

| Reporte | Audiencia | Qué muestra |
|---|---|---|
| Saldo de cuentas en kg de plomo | Gerencia, liquidador | Las cuentas en kg con su saldo actual **o a cualquier fecha de corte histórica** |
| Maquila interna del periodo | Gerencia, liquidador | Maquila causada por periodo (horno $1.500/kg al envío, crisol $300/kg a la salida): gasto por sede de origen e ingreso de Juan Mina |
| Movimientos de tercero por sede | Liquidador, gerencia | Estado de cuenta de un tercero filtrado por sede — el saldo oficial sigue siendo el consolidado |
| Top proveedores por sede | Comercial, gerencia | Ranking de proveedores por volumen y valor en cada sede |
| Cuadre semanal Willard | Gerencia, Willard | Apertura + entradas − entregas = cierre, por cuenta, **con detalle por entrega (fecha, remisión, kg)**; se firma como acta inmutable ("OK del viernes") |
| Reconciliación diaria intersede | Liquidador | Verifica que los despachos, kilogramos y cargos de maquila causados del día cuadren entre sí |

Todos los reportes son **exportables a Excel** (con números sumables) y **PDF** (listo para enviar al destinatario externo), con filtros por rango de fechas y sede en todos los reportes; filtros por material y tercero, e histórico consultable a fecha pasada, en los reportes donde aplican (balances, cuentas en kilogramos, listados de operaciones y estados de cuenta).

### 2.7 Criterios de aceptación de Fase 1

Cómo medimos que la fase está cerrada con éxito:

1. Una orden de entrada típica (de cada tipo) se captura una sola vez y alimenta correctamente inventario, compra y cuenta postconsumo según corresponda — incluida una ruta de recolección con varios proveedores, que produce una entrada por proveedor.
2. La liquidación por peso del caso real descrito por Johana se procesa correctamente bajo el modelo acordado, con liquidación manual de Johana.
3. El balance general muestra cifras consistentes con los cuadros Excel actuales de SAC dentro de la tolerancia que se acuerde con Johana y la gerencia al inicio del proyecto (típicamente bajo 0,5% por línea).
4. La deuda en plomo con Willard (baterías y drosses por separado) cuadra cada viernes con el cuadro de Johana, y el acta del cuadre semanal se genera y firma desde el sistema.
5. El panel de excepciones está disponible y Johana lo usa como vista de cierre del día, con el "OK del día" firmado.
6. Erwin trabaja desde el sistema, no desde Excel, para auditar inventario.
7. La gerencia consulta caja, inventario y resultado por sede desde el sistema, sin cuadros paralelos.

### 2.8 Qué NO incluye Fase 1

- Experiencia móvil offline para conductores en ruta (entra en Fase 2 — en Fase 1, el conductor entrega acta de papel y el operador de báscula la transcribe).
- La app móvil de José **no se reemplaza en Fase 1**: sigue operando en Juan Mina y sus datos se concilian en el cuadre diario. Su integración al sistema, con José incorporado al proyecto, entra en Fase 2.
- Coladas con trazabilidad uno-a-uno (Fase 2).
- Refinación en crisol con fundentes (Fase 2).
- Insumos del horno grande y fundentes del crisol con costo integrado (Fase 2).
- Exportaciones con liquidación diferida (Fase 3).
- Disposición regulada formal de subproductos a gestor autorizado (Fase 3).
- Reportes regulatorios automáticos (Fase 3).
- Integración con la báscula electrónica por conexión directa — Bluetooth o cable (Fase 2+).
- Integración con facturación electrónica (Fase 3+).
- Migración de toda la historia transaccional (Fase 1 migra **saldos iniciales y maestros**, no movimientos históricos — confirmado con Hugo y Johana).

### 2.9 Estado de las preguntas de cierre

La visita a planta del 2 de julio de 2026 (sesión de trabajo con Johana; decisiones validadas también por Hugo) cerró **todas las preguntas técnicas** que quedaban abiertas:

| Pregunta | Respuesta cerrada |
|---|---|
| Momento de la maquila interna | Al envío se causa la maquila del horno ($1.500/kg de plomo equivalente); al salir del crisol, el adicional ($300/kg). En ambos casos: gasto Circunvalar, ingreso Juan Mina. Validado por Hugo y por Johana |
| Crisol: ¿cuenta separada? | Sí — cinco cuentas. El crisol se mide aparte para conocer la eficiencia de cada etapa |
| Green Loop | Opera con caja provista por SAC; compra a nombre del proveedor real; comisión de $100/kg por consignación aparte |
| Proyecto de aluminio | Se llama **Eco Alloys**; el saldo exacto se toma al corte de arranque |
| Liquidación por peso | La composición se conoce al recibir; el valor pagado se reparte entre las referencias por costo promedio histórico |
| Cajas menores | Una por sede, todas operadas por Yurani |
| Tolerancia de traslados | 3–5% configurable; dentro del rango, ajuste automático con lo recibido como fuente de verdad |
| Cuadre diario | Se simplifica a panel de excepciones y alarmas — el sistema concilia solo |
| Asignación de abonos a Willard | Viene definida en la remisión de cada entrega (baterías o drosses) |
| Drosses | Siempre ingresan directo por Juan Mina |
| Saldo Willard baterías por sede | Sub-saldos Barranquilla y Bogotá; los kg pasan al saldo Barranquilla cuando el material llega físicamente a Circunvalar (Johana) |

**Quedan abiertas (ninguna es técnica):**

**P1.** ¿Cuántas órdenes de entrada se procesan por día en promedio y en pico, desagregadas por sede y por tipo? Este dato condiciona el dimensionamiento de los puestos de captura.

**P55.** ¿Cuál es la fecha de corte deseada para el arranque de Fase 1? Idealmente un viernes, coincidiendo con el último cuadre Willard antes del arranque.

**P64.** ¿Cuál es el rango de presupuesto orientativo y la modalidad preferida (suscripción mensual, pago por hito, implementación más mantenimiento)? Se resuelve con la propuesta comercial.

**Datos de configuración que se recogen al arranque** (no bloquean el cierre del alcance): tabla de factores por referencia, tabla de retenciones por tipo de proveedor, lista de máquinas y vehículos para el detalle de gastos, saldos iniciales de todas las cuentas al corte, y formatos Excel actuales para la migración.

---

## 3. Fase 2 — Trazabilidad de planta y movilidad en campo

> Esta fase se activa una vez Fase 1 está cerrada y operando.

### 3.1 Qué problema resuelve esta fase

Dos dolores independientes:
1. La fundición y refinación se llevan hoy con cuadros propios sin trazabilidad uno-a-uno; cada colada no se puede vincular hacia atrás (a sus aportantes origen) ni hacia adelante (a sus destinos comerciales).
2. El conductor en ruta sigue llenando actas en papel, que el operador de báscula transcribe en planta — doble digitación operativa que se eliminó en otros puntos pero subsiste aquí.

### 3.2 Qué módulos contiene

| # | Módulo | Qué hace |
|---|---|---|
| 1 | **Experiencia móvil offline del conductor** | El conductor opera desde el navegador del celular, con captura sin internet (acta con foto, firma capturada en pantalla, geolocalización) y sincronización automática al volver la señal. |
| 2 | **Integración de la app móvil de José** | José, desarrollador interno de SAC, se incorpora al proyecto para co-desarrollar el módulo móvil. Las funciones de su app (que siguió operando en Juan Mina durante Fase 1) se migran progresivamente al sistema, sin salto abrupto ni pérdida de funcionalidad. Es una fortaleza del proyecto: se aprovecha el conocimiento interno en captura de campo. |
| 3 | **Coladas del horno grande con trazabilidad uno-a-uno** | Cada colada es una unidad individual con referencia explícita a las remisiones de aportantes consumidos, a los insumos cargados, y al plomo crudo producido. Rendimiento real vs esperado por colada. |
| 4 | **Refinación en horno crisol con fundentes** | Plomo crudo → plomo puro con captura de fundentes consumidos. Cada lote de puro conserva referencia proporcional a las coladas origen. |
| 5 | **Insumos y fundentes con costo integrado** | Compra, inventario y consumo de insumos del horno grande y fundentes del crisol, con costo asignado al plomo producido en cada colada / refinación. |

> Los módulos 3, 4 y 5 quedan marcados como **borrador hasta cerrar la sesión específica con Henry** (Jefe de Planta Juan Mina), quien no participó en la reunión inicial. La sesión con Henry es prerrequisito para cerrar el alcance de Fase 2.

### 3.3 Qué valor concreto entrega Fase 2

- Cada colada del horno grande es un lote individualmente trazable: desde la orden de entrada del proveedor hasta el destino del plomo producido.
- Los conductores capturan actas desde el celular en ruta sin papel.
- El rendimiento de cada colada es visible y comparable contra teórico esperado.
- José y el equipo del proyecto **co-desarrollan** los módulos de coladas y la experiencia móvil, asegurando continuidad operativa y transferencia del conocimiento acumulado en su app.

### 3.4 Reportes adicionales en Fase 2

| Reporte | Audiencia | Qué muestra |
|---|---|---|
| Trazabilidad por colada | Gerencia, comercial | Aportantes → colada → lote → destino (y viceversa) |
| Rendimiento por colada / horno / operador | Gerencia, fundición | Real vs esperado por colada |
| Recolecciones en ruta | Coord. postconsumo, gerencia | Rutas, conductores, kg recolectados |
| Productividad por operario | Supervisores, gerencia | KPI por operario |

### 3.5 Criterios de aceptación de Fase 2

1. Una colada se abre, se carga, se cierra y produce trazabilidad uno-a-uno entre remisión origen, colada y lote de plomo producido.
2. La descarga de las cuentas en plomo (Willard, intersede, horno, crisol) ocurre correctamente al cerrar cada colada según el modelo validado con Henry y Johana.
3. Un conductor captura un acta en ruta sin internet, regresa, sincroniza, y el operador de báscula recibe el camión con los datos preservados.
4. Los insumos y fundentes consumidos en cada colada y refinación alimentan correctamente el costo del plomo producido bajo la política definida con Henry.
5. Las funciones acordadas de la app de José quedan integradas al sistema según el plan de migración pactado con él.

### 3.6 Preguntas que SAC debe responder para cerrar Fase 2

**3 preguntas bloqueantes.** Las dos primeras dependen de la sesión específica con Henry; la tercera requiere sesión 1:1 con José.

**P16.** Sesión específica con Henry para levantar: lista exacta de insumos del horno grande, lista exacta de fundentes del crisol, recetas vigentes, rendimientos típicos por receta, política de etiquetado físico del plomo crudo (lingote marcado vs granel), modo de medición de gas y oxígeno.

**P17.** Modelo exacto del saldo del horno y del paso crudo → crisol: cómo se acumula y descarga cada cuenta, qué eventos disparan qué cascada. Validación con Johana y con Henry (complementa lo confirmado en la visita: crisol como cuenta separada).

**P61.** Sesión 1:1 con José para acordar: capacidad disponible, modalidad de incorporación al equipo del proyecto, plan concreto de migración de datos de su app al sistema central por cada módulo (postconsumo, coladas, escritorio, inspección de vehículos), criterios para retirar progresivamente los módulos de su app a medida que el sistema central los absorbe.

---

## 4. Fase 3 — Cierre comercial y regulatorio

> Esta fase se activa una vez Fase 2 está cerrada y operando.

### 4.1 Qué problema resuelve esta fase

- El flujo de exportaciones queda completamente integrado: precio provisional, ajuste por liquidación final, diferencia en cambio.
- Los subproductos pasan de inventario básico a canal con margen visible y disposición regulada cuando aplique.
- El cumplimiento regulatorio queda asistido por el sistema según las regulaciones que SAC confirme.

### 4.2 Qué módulos contiene

| # | Módulo | Qué hace |
|---|---|---|
| 1 | **Exportaciones con liquidación diferida** | Precio provisional al embarcar, ajuste al cobrar (cuando el cliente hace ensayos en destino), diferencia en cambio separada como ingreso/gasto financiero. |
| 2 | **Subproductos en su gestión completa** | Disposición a gestor autorizado con manifiesto (cuando aplique), reproceso interno con marca de "origen recirculado" para no inflar costos, alertas por acumulación, indicadores de margen por subproducto. |
| 3 | **Reportes regulatorios y dashboards consolidados** | Reportes al ente que aplique (según lo que SAC confirme), dashboards ejecutivos (margen por canal, productividad consolidada entre sedes, alertas inteligentes). |

### 4.3 Reportes adicionales en Fase 3

| Reporte | Audiencia | Qué muestra |
|---|---|---|
| Exportaciones pendientes de liquidación | Comercial, liquidador | Embarques sin precio final |
| Margen por canal | Gerencia | Margen de venta nacional, abonos Willard, reventa, subproductos |
| Reportes regulatorios | Coordinador ambiental, gerencia | A definir según regulación aplicable (P47) |

### 4.4 Criterios de aceptación de Fase 3

1. Una exportación se procesa de principio a fin con precio provisional, ajuste al cobrar y diferencia en cambio correctamente registrada.
2. La venta o disposición de los subproductos identificados (plástico, electrolito, escoria, polvoducto, tapas, cajas acrílicas) está soportada con los documentos que la regulación exija.
3. Los reportes regulatorios que SAC confirme se generan automáticamente al cierre del periodo.

### 4.5 Preguntas que SAC debe responder para cerrar Fase 3

**2 preguntas bloqueantes.**

**P24.** ¿Cuál es el destino real actual de cada subproducto (plástico/PP, electrolito, separador, escoria, polvoducto, tapas, cajas acrílicas, plomo retal)? Por cada uno: ¿se vende, a quién, a qué precio aproximado; se entrega a gestor; se acumula sin destino; se reprocesa internamente?

**P47.** ¿Qué reportes regulatorios entrega hoy SAC efectivamente, a quién, con qué frecuencia, y en qué formato? Necesitamos la lista exacta directamente de SAC (con copias o referencias) para dimensionar el módulo de Fase 3 — evitamos asumir cuáles regulaciones aplican.

---

## 5. Próximos pasos

1. **Revisión de este documento con SAC.** Hugo, Johana, Erwin y José leen v0.5 y marcan: dónde el modelo descrito no refleja la realidad, qué partes son ambiguas, qué hay que agregar. La sección 2.3 fue revisada y validada con Johana durante la visita.
2. **Visita a planta realizada (2 de julio de 2026)** — cerró todas las preguntas técnicas pendientes (ver 2.9). Si se considera útil, queda opcional una jornada de observación de un día completo de operación al arranque.
3. **Sesión 1:1 con Johana** — avanzada en la visita: modelo de cuentas y maquila validado, regla de liquidación por peso cerrada, panel de excepciones definido con su tolerancia. Queda para el arranque: validación de saldos al corte y detalle fino del acta semanal Willard.
4. **Sesión 1:1 con Erwin** sobre la transformación de su rol: de digitador masivo a auditor de inventario y validador. Sin acuerdo no hay adopción del módulo de inventario.
5. **Sesión 1:1 con José** sobre el plan concreto de coexistencia en Fase 1 y co-desarrollo en Fase 2 (P61).
6. **Sesión específica con Henry**, Jefe de Planta Juan Mina, antes de cerrar el alcance de Fase 2 (P16).
7. **Respuestas a P1, P55 y P64** (sección 2.9) — las de Fase 2 y Fase 3 se pueden cerrar después.
8. **Iteración del documento** integrando el resultado de la visita y las respuestas pendientes.
9. **Cierre de alcance** firmado por Hugo como aprobación, dando paso a v1.0.
10. **Propuesta comercial separada** con cronograma detallado, hitos, criterios de aceptación cuantificados, condiciones comerciales y modelo de soporte posterior al arranque.

---

**Fin del documento.**

> Una **especificación funcional detallada** acompaña este documento. Contiene glosario completo, mapa de operaciones, descripción detallada de cada módulo de Fase 1 y Fase 2, los flujos críticos paso a paso, las reglas de negocio formales, la matriz de roles × módulos, supuestos y riesgos en detalle, y el listado completo de preguntas. Está disponible cuando SAC quiera profundizar en cualquier punto.