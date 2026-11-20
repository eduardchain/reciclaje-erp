# Plan — SAC: Ingrid / Green Loop, usuario con alcance de recolector (v1.11)

**v1.11 (20-nov):** QA 2 dio GO a la v1.10 (`e6ac14e`; revisión `revision_plan_v1.10.md`, `8f77c2b1…c637`). Entran su condición y sus dos notas, junto con la construcción y antes de plantar:
- **c4:** P58, «9g solo mira `disc > 0`». Tumba el caso de 110 y no tumba el de 60, el de «sin proveedor» ni el control. Sin ella, una 9g de un solo sentido pasaba P55–P57.
- **n13, declarada en la fila 9:** `inbound_order_lines.quantity` es Numeric(15,4) y el reparto se cuantiza a ALLOC_Q (0,001). Una línea pesada con cuarto decimal deja un `disc` que Ingrid nunca puede repartir: esa Entrada la liquida SAC. El Coordinador lo midió en producción: las 604 líneas de las 155 Entradas de SAC tienen cantidades enteras, así que hay **0 casos** (`~/sac-evidencia/2026-11-20/gate-prod/n13_cuarto_decimal_prod.log`).
- **n14:** la promesa «junta todos los materiales en un 422» gana su test: T26 con **dos** materiales exige los dos nombres en el mismo 422. Se suma **P59**, «9g levanta en el primer material», que tumba ese caso.

**v1.10 (20-nov):** QA 2 dio la pasada 1 OK sobre `9d8cc33` y GO a la v1.9 (`71c3fde`; revisión `pasada1_9d8cc33.md`, `89cb33e8…4ffc`, en `~/sac-evidencia/2026-11-20/qa-2-ingrid/`). Entran tres cosas:
- **9g — con alcance no se liquida con descuadre.** Lo decidió Daniel sobre la O1 de QA 2 («Que no deje descuadre», por ventanita, 20-nov ~15:05, vía el Coordinador). Con alcance, una Entrada se liquida solo si **todo lo pesado** queda repartido. Si algún material queda con descuadre (falta o sobra, sin importar la tolerancia), o se marca «sin proveedor» en un material pesado, sale un 422 que lista lo que falta y dice que, si no se puede repartir todo, esta Entrada la liquida SAC.
  - **Por qué:** el descuadre se valora al precio de referencia y aterriza en los libros de SAC (ajuste de inventario a resultados, #93 D6/D7). Con alcance, ese precio lo fijaría Ingrid. Sin descuadre no hay ajuste, así que el `reference_unit_price` que mande no tiene efecto contable. Se sigue guardando en la línea como hoy: si SAC re-liquida, es una precarga que puede editar.
  - **Mecanismo:** un kwarg `require_full_allocation` de `inbound_order_service.liquidate()`, que por defecto es False (sin él, todo queda byte a byte igual) y que el endpoint enciende solo con alcance. La regla corre en el mismo lazo que ya calcula `disc = pesado − repartido`, con la misma cuantización, así que el descuadre tiene **una sola definición**.
    - Va **antes** de D8 y D16, para que Ingrid no reciba el mensaje del precio de referencia, que no le corresponde.
    - Junta **todos** los materiales con problema y da **un** 422.
  - **Material que la báscula no pesó (#93 D16):** repartirlo deja descuadre (sobra), así que cae en la regla. Una línea con pesado 0 marcada «sin proveedor» no tiene descuadre y pasa, porque «todo lo pesado repartido» se cumple. La marca «sin proveedor» solo da 422 cuando el material tiene algo pesado. Es más angosto que la letra del pedido («si se marca sin proveedor, 422»), y se declara aquí.
  - **Pantalla:** con alcance, el aviso sale en la lista de problemas **antes** de mandar y Liquidar queda deshabilitado. Se esconden la casilla «Sin proveedor (intencional)» y el bloque «¿Un proveedor reporta un material que la báscula no pesó?», que con alcance solo pueden terminar en 422.
  - **Tests:** T26. **Matriz:** P55–P57.
- **n11:** se declara en §4. No se deja pasar el `null` sin flag, por dos razones: la pantalla de Usuarios esconde el alcance cuando el flag está apagado, así que solo serviría por API; y una fila solo puede nacer con el flag encendido.
- **n12:** T25e gana el caso «los usuarios con alcance GL están inactivos → sin aviso». **Matriz:** P54.

**v1.9 (20-nov):** responde a QA 2. Dio GO a la v1.7 (`9b09307`) y a la v1.8 (`de0d714`); las revisiones son `revision_plan_v1.7.md` (`edac1352…a8f5`) y `revision_plan_v1.8.md` (`87f93baa…6acc`), en `~/sac-evidencia/2026-11-20/qa-2-ingrid/`.
- **c3, una celda vacía en T25e.** §5.6 dice «sin marca, o con la de otro recolector», pero ningún caso ponía un proveedor con la marca de **otro** recolector, así que un aviso escrito `collector_id IS NULL` pasaba T25e entero. Se agregan el caso «E_GL con C (marca X) → un aviso que nombra a C» y **P53**.
- **n6:** el invariante de `last_liquidation_batch` va en su docstring con las líneas: sin commit entre el MCH y las filas de retención e IVA. QA 2 verificó la sospecha de `reverted_at` contra el código: es **real en las retenciones** (`purchase.py:1023`, `datetime.now()` por fila) y **no en el IVA** (`document_tax.py:206`, un solo `now`). Predicción para T25d contra el código viejo: con dos retenciones, la precarga trae **una**.
- **n7:** en P49, «T25d no cae».
- **n8:** el usuario con alcance que dispara el aviso tiene que estar **activo** (`User.is_active`).
- **n9:** en el caso 1 de T25e, B va en **dos** compras de la misma Entrada (Q-65), y se exige **un** aviso.
- **n10:** §5.6 declara el camino vecino: si alguien le quita la marca a un proveedor **después** de liquidar, no hay aviso, y la red es la nota del detalle (§8).

**v1.8 (20-nov): Daniel eligió D-E2(b)** («Sí, aviso al liquidar», por ventanita, 20-nov ~14:25, vía el Coordinador). Con eso cambia la decisión 3 de la mañana, que había sido (a) (§15). La v1.7 (`9b09307`) ya estaba con QA 2, así que esto va encima como v1.8, sin reescribirla.
- **El aviso** (§5.6). Cuando alguien liquida una Entrada con recolector y reparte a un proveedor que no tiene esa marca, la **respuesta de liquidar** trae un aviso en `warnings[]`, y la pantalla lo muestra en el toast que ya existe. Avisa, no bloquea (#17/#76).
- **Solo si alguien lo pierde:** avisa únicamente cuando el recolector tiene al menos un usuario con alcance en la org. Sin ese usuario nadie deja de ver nada, y el aviso sería ruido en cada Entrada (decisión mía, va a QA 2).
- **El texto dice qué hacer:** «El proveedor X no tiene la marca de Green Loop: Ingrid verá esta compra en la Entrada, pero no podrá abrirla. Si es de Green Loop, márcalo en Terceros → Recolector.» El nombre del usuario sale de su alcance, no está escrito a mano.
- **T25e:** el aviso se lee de la **respuesta HTTP**, no del servicio (lección de #100 D4d), y va con su PAR, de modo que el control positivo es que con la marca no hay aviso. **Matriz:** P51 y P52.
- La nota del detalle de Ingrid (§8) se queda: el aviso no bloquea, así que el caso puede pasar igual.

**v1.7 (20-nov):** responde a la revisión de Eco QA 2 sobre la v1.6 (`919157a`, `~/sac-evidencia/2026-11-20/qa-2-ingrid/revision_plan_v1.6.md`, sha256 `29d8139a…3273`). QA 2 dio GO a la 9e y a T25 tal como estaban. La 9f quedó condicionada a c1, y c2 era de redacción.
- **c1, la 9f mira el lote de la ÚLTIMA liquidación.** Los dos helpers de hoy (`_last_retention_batch` y `_last_tax_batch`, en el endpoint) devuelven «las vivas, o si no, el lote revertido más reciente que exista». Una liquidación sin retenciones no deja filas, así que esta secuencia rompía la regla:
  - L1 con retención → des-liquidar;
  - Johana re-liquida sin retención (L2) → des-liquidar;
  - el helper devolvía el lote de L1, y la 9f le daba 422 a Ingrid para siempre en una Entrada que SAC ya corrigió.

  Ahora hay **una sola función** en el servicio: `last_liquidation_batch(db, purchase_ids)`.
  - Definición: el lote es lo que nació en la transacción de la última liquidación de cada compra. Esa liquidación se identifica por el checkpoint `purchase_liquidation` de su costo (MCH append-only, D20b de #93: des-liquidar no lo borra), y las filas de retención e IVA de esa liquidación tienen `created_at` igual a ese checkpoint, porque `now()` de PG vale lo mismo en toda la transacción.
  - Si la última liquidación no tuvo retenciones ni IVA, el lote está vacío.
  - La usan la regla 9f **y** la precarga (`InboundPurchaseSummary.retentions`/`taxes`). Los dos helpers del endpoint se borran: no queda copia.
- **Consecuencia declarada: la precarga de Johana cambia.** Es el hallazgo preexistente que QA 2 le pasó al Coordinador (#93): después de un L2 sin retenciones, la precarga resucitaba las de L1. Al compartir la función, eso queda arreglado por construcción. Pantalla solo de SAC (router con flag); hoy tiene 0 casos (medición (a)).
- **Una sospecha más, a medir antes de afirmarla:** `_revert_liquidation_effects` estampa `reverted_at = datetime.now()` **por fila** (`services/purchase.py:1023`), y el helper viejo agrupa por `reverted_at ==` el máximo. Con dos retenciones en una liquidación, la precarga podría traer solo una. La función nueva agrupa por `created_at`, así que si el defecto existe también queda cubierto. Lo mide T25d contra el código viejo, y el resultado va al informe con su artefacto.
- **c2:** el encabezado de la v1.6 decía T25b = 9e y T25c = 9f. Lo correcto es T25b = 9f y T25c = 9e, como en el cuerpo y la matriz. Corregido.
- **Tests:** T25b suma los dos controles de c1 (retención e IVA) y T25d (precarga). **Matriz:** P49 y P50.

**v1.6 (20-nov):** las Entradas que ya existen en producción. El Coordinador midió R1 en producción (API, solo lectura, `~/sac-evidencia/2026-11-20/gate-prod/gl_entradas_prod.log`): de 149 Entradas de SAC, **25 tienen recolector y las 25 son Green Loop**, 18 revisadas y 7 liquidadas. Ingrid las encuentra el día del deploy sin que nadie las haya creado con el código nuevo. Revisé cada regla contra ese hecho y encontré dos supuestos que solo valían para Entradas nacidas con el código nuevo. Hoy ninguno tiene casos (mediciones (a) y (b) del Coordinador), pero los dos pueden aparecer el día que Johana des-liquide o reparta una Entrada de Green Loop, así que las defensas van igual (Coordinador).
- **(1) Una Entrada des-liquidada por SAC que Ingrid vuelve a liquidar.** Des-liquidar conserva el reparto (#93 D20), y las compras vuelven a registradas con su último lote de retenciones e IVA. Con alcance, la pantalla no carga el catálogo de retenciones, así que **las retenciones de Johana se perdían en silencio** al re-liquidar; el IVA precargado viajaba escondido y daba el 422 de S5 sin explicación. Y si el reparto tenía un proveedor fuera de su alcance, Ingrid podía cambiarlo por uno suyo en la misma compra: la regla de la fila 9 pasaba (todo el payload es suyo) y **el servicio cancelaba la compra del proveedor ajeno**, un documento que ella ni siquiera puede abrir (R6 de #122). Se cierra con **dos reglas nuevas en la fila 9** (9e y 9f) y su espejo en la pantalla (§8). Medición (a): 0 de las 18 revisadas tienen reparto o compras en el puente, y 0 retenciones en el último lote; el IVA de compra todavía no existe en producción (llega con #122).
- **(2) Una Entrada liquidada por SAC con un proveedor sin la marca.** Ingrid ve la compra en el detalle de su Entrada (es la fuga D-E2, declarada, §5.6), pero el link le da 404. Criterio: **marcar, no esconder**. Lo marca Johana, o quien tenga `third_parties.edit`, desde Terceros → «Recolector»; los que ya existen los marca el script al deploy (§16 paso 2); y después, la pantalla de Ingrid le dice qué compra no puede abrir y que se la pida a SAC (§8). Medición (b): 0 proveedores sin marca en las 7 liquidadas (5 proveedores, todos con «(GREENLOOP)»).
  - **Aviso a Johana al liquidar: NO va en este ciclo sin Daniel.** Es exactamente la opción (b) de D-E2 (§5.6), y Daniel eligió la (a) el 20-nov (§15, decisión 3). Lo dejo como propuesta en §5.6; si Daniel la quiere, es un delta propio con su test.
- **Tests:** T25 (las Entradas preexistentes en sus dos estados), T25b (regla 9f) y T25c (regla 9e). **Matriz:** P45 a P48. El cuerpo aprobado no cambia fuera de esto. *(v1.7, c2: corregido; la v1.6 los tenía al revés.)*

**v1.5 (20-nov):** un hueco de la v1.4 que encontré midiendo la pantalla, y la regla de la categoría de conductor. El resto del cuerpo aprobado no cambia.
- **El hueco.** Fila 15 exige `category_ids`, y Ingrid no tenía forma de conocerlos: `GET /third-party-categories/flat` no estaba en la lista blanca. `CreateSupplierDialog` quedaba sin categorías («No hay una categoría de proveedor de material»), así que con la v1.4 no podía crear un proveedor desde la liquidación.
  - Lo medí con un sondeo de red: Playwright como un usuario con alcance contra `:8012`/`:5182`, 10 pantallas, anotando toda respuesta ≥ 400 (`sondeo_red_r1.log`). Dio 26 respuestas 403.
  - 25 de esas 403 son de la pantalla: piden lo que el backend ya le niega. Se cierran en el frontend (§8).
  - La que queda es este hueco, y se cierra con la **fila 15b**.
  - Visto bueno de Eco QA 2 a la idea, y el Coordinador confirma que no hace falta Daniel: cumple lo ya decidido (Ingrid crea sus proveedores y, por H5, sus conductores) y solo expone nombres de categorías.
- **La categoría de conductor** (Coordinador, 20-nov): una sola, con un nombre fijo, **«Empleados»**.
  - Ya existe en producción, porque la crea la carga del Sheet (Tipo «empleado», #114), y es donde Johana clasifica hoy al único conductor de Green Loop, DANIEL DE LA HOZ (GREENLOP). No hace falta ninguna escritura en prod.
  - Se reconoce **por nombre** con `normalize_entity_name` y **falla cerrado** (lección de #112 D4b): si alguien la renombra o la desactiva, Ingrid solo puede crear proveedores. Nunca se abre a «cualquier generic».
  - Lo fija T24.
- **Una sola fuente** (pedido de Eco QA 2): la función `scoped_create_categories(db, org)` decide lo que la 15b **ofrece** y lo que la fila 15 **acepta**. Con dos listas, la pantalla podría ofrecer una categoría que el servidor rechaza, o al revés. Reemplaza a la constante `SCOPED_CREATE_BEHAVIORS`. T23 lo mide de punta a punta: «un id que trae el flat → 201».
- **Frontend (§8), medido:** el menú, el inicio, Entradas, el detalle, la liquidación y Nuevo Movimiento dejan de pedir lo que el backend niega, **solo con alcance**.
  - Para cualquier otro usuario, cada pantalla queda byte a byte igual.
  - La prueba (Coordinador, la misma que le pidió QA 1 a Coder 1) es doble: el registro de red de un usuario normal de Costa, con 0 requests de más o de menos antes y después, y una captura de Costa de cada pantalla tocada.
  - Para el usuario con alcance, el sondeo se re-corre con **0 respuestas ≥ 400** (pedido de Eco QA 2).
  - El 403 del servidor sigue siendo la red: el frontend solo esconde.
- **Matriz:** P41 a P44.

**v1.4 (20-nov):** dos hallazgos de la construcción, los dos llevados al Coordinador, y los nits n4/n5 de la revisión de la v1.3 (`ad8f5a2`, `~/sac-evidencia/2026-11-20/qa-2-ingrid/revision_plan_v1.3.md`). El cuerpo aprobado no cambia fuera de lo que sigue.
- **(a) Celda del cuadrante quién × flag:** «con alcance, flag off» en `GET /inbound-orders/{id}` decía 200/404, y eso no puede pasar: el router de Entradas tiene `require_org_flag`, que corta con 403 a todos, incluido el admin (#75), antes de que el alcance opine. Queda 403/403, y **T16b se mide en las rutas sin flag** (`/third-parties`, `/purchases`, `/money-movements`). P15 sigue cayendo por T16b. Acordado con el Coordinador.
- **(b) El rol «Recolector» pasa a 13 permisos** (decisión de Daniel, 20-nov, vía el Coordinador): se suma `treasury.view_all_movements`, que ya existe. Sin él, el listado general de Tesorería (`GET /money-movements`) le muestra a Ingrid solo lo que ella creó (`money_movements.py`, `can_view_all`), así que el fondeo de su caja que hace Johana no aparecía ahí, aunque sí en el estado de la cuenta. Ninguna ruta exige ese permiso como dependencia (es un `if` dentro del listado), así que las 89 rutas de §5.1 no cambian. Con el permiso, el filtro de alcance de la fila 24 es la única barrera del listado, y lo prueba **T22** en las dos direcciones; P40 es su plantado.
- **n4:** en el dry-run de §16 paso 2 se verifica que «ADALBERTO AVILA (GREENLOOP)» está en «a marcar».
- **n5:** en P35, «CARLOS CASTAÑO (GREENLOOP)» es un chequeo de cordura, no el control; el control que discrimina es «GRÉENLOOP SAS».

**v1.3 (20-nov):** Daniel autorizó la construcción sobre el cuerpo de la v1.2 (`700c87a`, GO de Eco QA 2, revisión `~/sac-evidencia/2026-11-20/qa-2-ingrid/revision_plan_v1.2.md`, sha256 `d11d1fe1…d247`) y, antes de arrancar, **cambió la decisión 4** (vía el Coordinador). Solo cambia la **marca inicial**; el cuerpo aprobado (alcance, lista blanca, tests T1–T20, matriz P1–P33) no se toca.
- **Decisión 4 nueva:** «todo lo que diga green loop es green loop». No se le manda lista a Johana; la marca sale de una **regla sobre el nombre normalizado**, con dos exclusiones (§9, §15.4, §16 paso 2).
- **Lo que pidió Eco QA 2 para la regla** (`~/sac-evidencia/2026-11-20/qa-2-ingrid/medir_regla_greenloop.log`): la org por id, las exclusiones ruidosas, los inactivos decididos, la idempotencia, dry-run por defecto con exit ≠ 0 ante cualquier sorpresa, y un test de la normalización con los casos reales (§9, T21, P34–P39).
- **Nits de QA 2 a la v1.2:** n1, la FK autorreferente pasa a NO ACTION (§10); n2, el 128 de §2.7 explicado con su artefacto; n3, se limpian las marcas «pendiente de Daniel» de S2, S6, S7, §5.1, la fila 27b y el cuadrante.

**v1.2 (20-nov):** cambios después del GO de Eco QA 2 a la v1.1 (`d271135`, revisión `~/sac-evidencia/2026-11-20/qa-2-ingrid/revision_plan_v1.1.md`, sha256 `97a97be2…a92c`).
- **§15.3 decidida** por Daniel, vía el Coordinador: todas las recomendadas. Ninguna fila del cuerpo cambia.
- **Riesgo de S5** (retención o IVA en compras de Green Loop).
- **Notas de QA 2:** N1 (RESTRICT, §10 y T20), N2 (422 si el alcance es para un superusuario, §4 y T16d) y N3 (prefijo «Fuera de tu alcance» en T1 y T1c).
- **Matriz:** P32 y P33.
- **Corrección de un dato:** el «0 de 34 Entradas con recolector» se había medido sobre Entradas de **prueba** de la copia de dev, no de producción (§2.7 y R1).

**v1.1 (20-nov):** responde al NO-GO de Eco QA 2 sobre la v1.0 (`409e857`, revisión `~/sac-evidencia/2026-11-20/qa-2-ingrid/revision_plan_v1.0.md`, sha256 `e918ab25…10f8`) y a la revisión de producto del Coordinador. Verifiqué los cinco hallazgos contra el código antes de aceptarlos.
- **H1:** el alta de terceros con alcance no acepta saldo inicial y las categorías se restringen (§5.2 fila 15).
- **H2:** anular y la evidencia solo valen para sus propios tipos de pago, y una transferencia nunca (filas 28–30).
- **H3:** lista blanca de CAMPOS, nueva §5.7.
- **H4:** las rutas sin contexto de org, nueva §5.0, con T1b y T1c.
- **H5:** los conductores van por `payment-to-generic`, fila 27b.
- **Decisiones nuevas en §15:** D-a (quién fija la comisión) y D-b (compras por marca o por Entrada).
- **Menores:** M1 (el 422 sin nombre), M2 (P22–P29) y M3 (T2 con métodos).
- **Coordinador:** R1 pasa a condición de uso (§14), runbook de deploy (§16) y nota sobre Adalberto (§2.7).

**Autor:** Eco Coder 2 · **Revisa:** Eco QA 2 · **Nivel:** lógica · **Rama:** `coder-2/recolector-alcance` (base `de32530`)
**Evidencia:** `~/sac-evidencia/2026-11-20/coder-2-recolector-alcance/` (inventarios, mediciones y los scripts que los producen).
**Estado:** construcción autorizada por Daniel (20-nov, vía el Coordinador) sobre el cuerpo de `700c87a`. La v1.7 (`9b09307`) y la v1.8 (`de0d714`) tienen GO de Eco QA 2; la v1.9 (c3 y notas) va con el commit de la matriz, antes de plantar.

---

## 0. En una línea

Se agregan dos cosas: una **marca** por tercero (`third_parties.collector_id`, «este tercero es de Green Loop») y un **alcance** por usuario (`user_collector_scopes`, «este usuario solo opera Green Loop»). Un usuario con alcance pasa por una **lista blanca de ~30 rutas** en `get_required_org_context` (la cifra exacta la fija T2b), y cada una filtra o rechaza por la marca y recorta los campos que son de SAC (§5.7). Cualquier otra ruta le devuelve 403, aunque su rol tenga el permiso. Lo mismo pasa con las rutas de miembros de la org, que no pasan por ese contexto (§5.0). El balance detallado agrupa a los terceros marcados por aparte.

## 1. Qué pidió el cliente

Las citas llevan su grado: (a) textual, (b) Daniel lo afirmó y el cliente asintió, (c) inferencia nuestra. La fuente es `inventario-preguntas-cliente.md`, sección G (Q-69, Q-70, Q-71 y la fila «Proveedores de Green Loop aparte»), reunión del 20-nov.

- Ingrid «es la persona encargada de hacer las liquidaciones y llevar la caja de Green Loop», y la idea es que «sea la que liquide directamente las entradas de ellos» (L38-40, a).
- Al liquidar, que «solamente le aparezcan los proveedores de ellos» (L74, a).
- Ingrid ve los proveedores de Green Loop, sus estados de cuenta, las liquidaciones de sus proveedores y su caja (L213-217 + «Es correcto. Así es», b).
- Ve las Entradas que tienen recolector Green Loop: lo propuso Daniel (L226) y ella respondió «Correcto. Así es» (L229, b).
- En el informe, «que aparezcan pues divididos los proveedores de nosotros de los proveedores que son de Green Look… en las cuentas por cobrar y por pagar» (L76-80, a).
- Marca de los proveedores: «los que dicen Green Look, pues son de él. Hay como dos que no» (L49, a): Adalberto Ávila y «Daniel de la OS» (L51, a). Daniel: «con el nombre no alcanza» (L58).

### Supuestos (se construye con ellos; los decide Daniel en §12)

| # | Supuesto | Por qué así |
|---|---|---|
| **S1 (Q-70)** | Un tercero marcado de Green Loop sigue siéndolo aunque alguna vez le venda directo a SAC. El filtro es **estricto para Ingrid** y **no cambia nada para quien no tiene alcance**: Johana sigue viendo todos los proveedores en todas las Entradas. | Con esto, la respuesta de Q-70 no cambia el modelo. Si es «sí, venden directo», Johana igual los ve; si es «no», tampoco cambia nada. |
| S2 | La marca va en **cualquier tercero**, no solo en proveedores de material: los conductores reciben anticipos desde la caja de Green Loop (fila «Provisionales de Green Loop a conductores», 11-ago). Un conductor *generic* no se le puede pagar con `supplier-payment` ni con `advance-payment`, porque exigen material_supplier/service_provider/liability (`money_movement.py:105` y `:642`). **Decidido (H5 = a, §15.3):** `payment-to-generic` entra al alcance (fila 27b). | En la copia de dev, «DANIEL DE LA HOZ (GREENLOP)» es de la categoría *Empleados* (generic), no proveedor (medido). |
| S3 | El recolector mismo (el tercero «Green Loop», service_provider) **no** entra al alcance de Ingrid: su saldo con SAC (comisiones) es asunto de Johana. | No lo pidió el cliente. |
| S4 | Ingrid **no** crea, revisa, edita, desliquida ni anula Entradas: solo las ve y las liquida. | La captura es de báscula y la revisión de Erwin (Q-19). |
| S5 | En la liquidación de Ingrid **no** van retenciones (#93) ni IVA de compra (#122): si vienen en el payload, da 422. Johana sí los puede poner. | Las entidades `[Retenciones]`/`[Impuestos]` son pasivos de SAC, y su selector expone esos saldos. ⚠️ **Riesgo, se le pregunta a Johana aparte (Coordinador):** si una compra de Green Loop lleva retención o IVA, esa Entrada la tiene que liquidar Johana, no Ingrid. No cambia el plan. |
| S6 (**D-a = a**, decidida, §15.3) | La comisión del recolector (#83 D11) la causa la liquidación de Ingrid, pero **el monto lo fija el servidor**: tarifa vigente `comision_green_loop` × la base sugerida de #93 D11 (kg + unidades × `kg_per_unit`). El tercero es siempre su recolector. Si manda un `amount` distinto al calculado → 422. Para Johana (sin alcance) no cambia nada: el monto digitado manda (#79 F1). | Es la deuda de SAC con Green Loop, y la digitaría una empleada de Green Loop: conflicto de interés (QA 2, D-a). La comisión nace en la liquidación y no se agrega después, así que dejarla a Johana exige un camino nuevo. |
| S7 | Desde su caja, Ingrid solo puede hacer pagos a proveedor (`supplier-payment`), anticipos (`advance-payment`) y (H5 = a, decidida) pagos a terceros generic (`payment-to-generic`, conductores), siempre a terceros de su alcance, y anular **esos mismos** movimientos. Fondear la caja es un `transfer` que hace Johana. | Es lo mínimo que describe «llevar la caja». Gastos de la caja de Green Loop: no se pidieron. |
| S8 (**D-b**, §15) | Una Entrada es de Ingrid **solo si su recolector es el de su alcance**. En cambio, una **compra** es suya si su **proveedor** tiene la marca, así venga de una Entrada sin recolector o sea directa. | Son las dos reglas que asintió el cliente: «Entradas con recolector Green Loop» (L226-229, b) y «las liquidaciones de sus proveedores» (L213-217, b). Alinearlas es la decisión D-b. |

## 2. Lo medido (cada dato con su artefacto)

1. **La restricción de cuentas es por USUARIO, no por rol.** Vive en la tabla `user_account_assignments` (modelo `UserAccountAssignment`, `app/models/user.py:106`) y se edita con `PUT /organizations/{org}/members/{user}/account-assignments`, solo para admins. `RoleResponse` no tiene cuentas: `assigned_account_ids` sale en `my-permissions` y se lee del usuario. El brief decía «account_ids del rol», y está corregido aquí.
2. **Con la lista vacía el usuario ve todo** (fail-open): `_get_allowed_accounts` devuelve `None` si no hay asignaciones (`money_accounts.py:26-31`, `money_movements.py:137-142`). Para un usuario con alcance tiene que ser al revés.
3. **La restricción de cuentas solo se aplica en 4 lecturas:** `GET /money-accounts`, `GET /money-accounts/{id}`, `GET /money-movements` (más `/summary`) y los dos estados de cuenta, por cuenta y por tercero (`money_movements.py:673,719,759,926`). **No** la miran:
   - `GET /money-movements/{id}`;
   - `GET /money-movements/by-number/{n}`;
   - la evidencia (GET, POST y DELETE);
   - **ninguno de los 17 POST de creación**.
   Eco QA 2 llegó a lo mismo por su cuenta (inventario de 301 rutas en `~/sac-evidencia/2026-11-20/qa-2-ingrid/`).
4. **El listado de movimientos con cuentas restringidas filtra mal:** deja pasar todo movimiento con `account_id IS NULL` (`services/money_movement.py:1328-1331`). Eso incluye todas las causaciones de la org (`expense_accrual`, `commission_accrual`, intereses…), de cualquier tercero.
5. **El estado de cuenta de un tercero, para un usuario restringido, rompe el invariante de #55.** Filtra los movimientos por cuenta (`money_movements.py:926-934`) pero sigue cerrando contra el saldo vivo del tercero, así que el saldo corrido deja de cuadrar.
6. **Costa tiene hoy 2 usuarios con cuentas restringidas (6 asignaciones).** Lo midió el Coordinador en dev y lo re-medí en mi copia (`medicion_asignaciones_dev.log`). Los defectos 3 a 5 ya afectan a un cliente.
7. **Datos de Green Loop en la copia de dev** (`reciclaje_coder_2`, org SAC activa; `medicion_gl_dev.log`). ⚠️ La copia **no es una réplica limpia**: trae las pruebas locales que se hicieron sobre `reciclaje_db` (`medicion_origen_lista.log`). Los terceros de abajo sí vienen de producción: **128 = los 124 con sufijo + 4 sin sufijo** que un patrón amplio también atrapa («Green Loop», «BIOGREENLOOP», «ASOCIACION BIOGREEN RECYCLING» y «ECOGREEN»), y los 128 nacieron en la carga del 10-nov a las 19:05. Lo dice `created_at` agrupado por minuto: `medicion_origen_lista.log` (primera línea, `2026-11-10 19:05 | 128 | 124`), producido por `scripts/medir_origen_lista.sql`.
   - **124 terceros** con el sufijo `(GREENLOOP)` o `(GREENLOP)` en el nombre. 123 son *Proveedor Material* y 1 es *Empleados* (generic): «DANIEL DE LA HOZ (GREENLOP)».
   - Las dos «excepciones» que nombró Johana **ya llevan el sufijo en esta copia**: «ADALBERTO AVILA (GREENLOOP)» y «DANIEL DE LA HOZ (GREENLOP)». Según el Coordinador, que tiene la transcripción, Johana dijo de Adalberto que «es Greenloop, pero no dice Greenloop» (L51). La cita me llega de otra sesión y no la medí yo. Si es así, alguien ya lo renombró después de la reunión (Daniel le mostró cómo, L56). No cambia nada: con la decisión 4 nueva (v1.3) los dos entran por la regla del nombre, y a Johana ya no se le manda lista.
   - Hay nombres parecidos que **no** llevan el sufijo y que un patrón amplio atraparía: «BIOGREENLOOP» (−$150.000.000), «ASOCIACION BIOGREEN RECYCLING», «ECOGREEN». **v1.3:** la marca inicial sale de la regla de §9 (nombre normalizado que contiene «greenloop» o «greenlop»). «ASOCIACION BIOGREEN RECYCLING» y «ECOGREEN» no la cumplen; «BIOGREENLOOP» sí, y se excluye por decisión de Daniel. Medido en la SAC activa de mi copia: **126 cumplen la regla, 0 inactivos, 124 después de las dos exclusiones** (`medicion_regla_v13.log`, de `scripts/medir_regla_v13.sql`). Eco QA 2 midió lo mismo en su copia (`medir_regla_greenloop.log`).
   - ~~0 de 34 Entradas tienen recolector~~ **Dato retirado (v1.2):** las 34 Entradas de la copia son en su mayoría **pruebas locales**. Hay remisiones «REM-DEV-ORDEN», «SMOKE-REDONDEO» y «PANTALLA-P6», creadas en dev por johana@sac.com, hugo@sac.com y admin.revision@example.com; johana y hugo también son usuarios de prueba en dev. Artefactos: `medicion_fechas_lista.log` (las Entradas de prueba, con remisión y usuario) y `medicion_origen_lista.log` (34 Entradas en total: 3 con remisión de prueba por patrón y 1 de un usuario @example.com; las demás no se distinguen por esos dos criterios, y por eso el número entero se retira). Así que el número no dice nada sobre producción. Cuántas Entradas de producción tienen recolector lo mide el Coordinador por lectura. R1 sigue en pie como condición de uso.
8. **La agrupación por categoría del balance detallado (#38) no sirve para esto.** `_load_tp_behavior_map` guarda «la primera categoría por behavior_type» de una consulta **sin ORDER BY** (`services/reports.py:222-266`), así que un proveedor con dos categorías de material cae en un grupo arbitrario.
9. **Inventario de rutas:** hay **300 rutas montadas** en `/api/v1`, más `/health`. Mi conteo por decoradores da 306; las 6 de diferencia son de `endpoints/deferred_expenses.py`, que **no está montado**. Conciliado contra el de QA 2 con `comm` (`inventario_endpoints_todos.tsv`).

## 3. Cómo se marca un tercero: vínculo vs. categoría de sistema

| Criterio | (A) Vínculo `third_parties.collector_id` → recolector | (B) Categoría de sistema por código (patrón #112 D4b) |
|---|---|---|
| Qué expresa | «es de **este** recolector» | «es de Green Loop» |
| Un segundo recolector | gratis: es otro valor de la columna | otra categoría más un mapa categoría→recolector (otra columna igual) |
| ¿La puede borrar el formulario de terceros? | no: el formulario de categorías no la toca | **sí**: `_sync_category_assignments` borra y recrea, y hacen falta los guards de dos direcciones de #112 D4d. Un admin que edita categorías desmarcaría al proveedor y, en silencio, se lo quitaría a Ingrid |
| ¿Cambia la clasificación del balance? | **no** | **sí**: una categoría lleva `behavior_type`; marcar a un *Empleado* con una categoría `material_supplier` lo vuelve proveedor y cambia su sección en `_classify_third_party` (S2 lo exige) |
| Agrupación del balance | código nuevo, determinista | igual hace falta código nuevo (§2.8) |
| Predicado de filtro | `tp.collector_id = :scope` | `EXISTS` por asignaciones en cada listado |
| Tabla compartida | sí (`third_parties`), NULL en las otras orgs | no (filas solo en SAC), pero lee la tabla compartida de asignaciones |

**Recomendación: (A).** La razón que decide es la cuarta fila: con (B), marcar a un tercero cambia cómo lo clasifica el balance, y con (A) no cambia nada. Además, (A) no se puede deshacer desde el formulario de categorías por accidente.

**Reglas de la marca (422 que nombra el motivo):**
- el recolector es de la misma org, está activo y tiene `service_provider` (#32, el mismo criterio de `inbound_orders.collector_id`, #83);
- no puede ser el mismo tercero;
- **un solo nivel en las dos puntas** (como #94): un tercero que es recolector de otros no puede tener recolector, y no se le puede poner recolector a un tercero que lo es de otros;
- se escribe solo con el flag `kg_ledger_enabled` encendido. En otra org da 422, y el PAR con/sin flag es la red (#99);
- quitarla (`null`) está permitido (patrón `fields_set` de #87).

Se escribe por `PATCH /third-parties/{id}` (permiso `third_parties.edit`, ya existente). `ThirdPartyResponse` gana `collector_id` y `collector_name`, que viajan `null` en las otras orgs.

## 4. Cómo se le da el alcance a un usuario

- **Tabla nueva `user_collector_scopes`** (`id`, `organization_id`, `user_id`, `collector_id`, `created_at` con `server_default=now()` en el modelo **y** en la migración, por la lección de #100), con **UNIQUE (`organization_id`, `user_id`)**: un usuario tiene un solo alcance por org. Calca `user_account_assignments`, que también es por usuario. No se toca `organization_members`, que es el corazón del login de las 7 orgs.
- **Endpoint** `PUT /organizations/{org}/members/{user}/collector-scope` con body `{collector_id: UUID | null}`. Lleva el mismo guard que `account-assignments` (solo admin de la org, más el flag) y `null` borra el alcance. Da 422 en tres casos:
  - si el usuario destino tiene rol admin, porque el admin bypassa permisos y un alcance sobre él sería confuso;
  - **si es superusuario** (N2): `get_required_org_context` le hace un return temprano (`deps.py:119`), así que la fila nunca restringiría nada, y no se escribe un alcance que no restringe;
  - si el recolector no cumple las reglas de §3.
- **Contexto:** `get_required_org_context` lee el alcance con una consulta por índice único y lo deja en `ctx["collector_scope_id"]`. El superusuario sintetizado no tiene alcance.
- **🔴 El alcance lo decide la FILA, no el flag** (patrón #109: «el predicado es el dato»). Si alguien apaga `kg_ledger_enabled`, el alcance sigue restringiendo. **Tampoco lo salta el admin**: si una fila de alcance existe sobre un usuario admin (escrita por ORM o por un cambio de rol posterior), igual restringe. Es fail-closed (test T16c).
- **n11 (v1.10):** con el flag apagado, el PUT tampoco **quita** el alcance (`collector_id: null` → 422), y la fila sigue restringiendo (T16b). Se declara y no se cambia, por tres razones:
  - una fila solo puede nacer con el flag encendido;
  - en SAC el flag es el módulo entero;
  - la pantalla de Usuarios esconde el alcance cuando el flag está apagado, así que dejar pasar el `null` solo serviría por API.
  
  Si alguna vez se apagara el flag con un alcance vivo, se quita volviendo a encenderlo.
- `GET /roles/my-permissions` gana `collector_scope: {id, name} | null`, para que la pantalla lo sepa.

## 5. Dónde se impone: lista blanca en el backend (deny-by-default)

**Mecanismo.** `get_required_org_context` recibe el `Request`. Si el usuario tiene alcance y la función que atiende la ruta (`request.scope["endpoint"]`, identificada como `módulo.función`) no está en `SCOPED_ENDPOINTS` (`app/services/collector_scope.py`), devuelve **403** con un detalle que empieza con «Fuera de tu alcance:» y nombra al recolector.

**Por qué ahí y no ruta por ruta.** Por ese dependency pasan las 300 rutas de org, también las de adjuntos y roles, que no usan `require_permission`. Una ruta nueva que alguien agregue mañana queda **cerrada** para Ingrid hasta que se la agregue a la lista con su filtro y su test.

Que un admin le sume un permiso al rol de Ingrid **no abre** una ruta fuera de la lista: ampliar la lista es un cambio de código. El permiso sigue aplicando dentro de la lista, porque el alcance no da permisos (T14).

### 5.0 Las 27 rutas que NO pasan por `get_required_org_context` (H4)

QA 2 las midió en runtime (`~/sac-evidencia/2026-11-20/qa-2-ingrid/rutas_sin_contexto.txt`). La v1.0 decía que «ninguna sirve datos», y es falso: `GET /organizations/{id}/members` la puede pedir cualquier miembro y devuelve email, nombre, rol y cuentas asignadas de todo el personal de SAC (`organizations.py:253-290`; verificado).

| Grupo | Rutas | Con alcance |
|---|---|---|
| `/auth/*` y `/health` | 7 (`register`, `login`, `login/json`, `change-password`, `me` y los dos `/health`) | sin cambio: no son de una org |
| `/system/*` | 8 | sin cambio: son de superusuario, y el superusuario no tiene alcance |
| `GET /organizations` | 1 | sin cambio: lista las orgs del propio usuario |
| `POST /organizations` | 1 | sin cambio. ⚠️ **Preexistente:** cualquier usuario autenticado crea una org nueva. Con eso no ve nada de SAC; se reporta y queda fuera de alcance |
| `GET /organizations/{id}` | 1 | **permitida**: la pantalla lee de ahí los settings y los flags (`useOrgSettings`). Devuelve la org con sus `settings`: flags, sedes, centros Willard, `plant_third_party_id`. Son ids de configuración, sin saldos; queda declarado |
| las otras 9 de `/organizations/{id}/…` (miembros: listar, crear, editar, borrar, resetear clave, cuentas asignadas; `PATCH` de la org; `leave`) | 9 | **403 «Fuera de tu alcance»**. Lo hace un helper `deny_if_collector_scoped(db, org_id, user)`, llamado al entrar en cada una. Va también en las que ya exigen admin: por T16c, un admin con fila de alcance tampoco administra |

Son 7 + 8 + 1 + 1 + 1 + 9 = **27**. Las tres pruebas:
- **T1b:** el conjunto de rutas montadas **sin** `get_required_org_context` es igual a un **set literal** de esas 27, escrito en el test. Si mañana aparece una ruta que se salta el contexto, T1b la nombra en vez de dejarla fuera de T1 en silencio.
- **T1c:** el usuario con alcance recibe 403 **con el prefijo «Fuera de tu alcance»** (N3) en las 9 rutas de miembros, y 200 en `GET /organizations/{id}`.
- **Control positivo de T1c:** el mismo rol sin alcance recibe 200 en `GET …/members`, que es el comportamiento de hoy y no se toca.

### 5.1 Inventario: a qué llega el rol propuesto

Rol propuesto «Recolector» (13 permisos existentes, **cero permisos nuevos**): `purchases.view`, `purchases.view_prices`, `purchases.liquidate`, `third_parties.view`, `third_parties.create`, `treasury.view_statements`, `treasury.view_accounts`, `treasury.view_movements`, `treasury.view_all_movements` (v1.4, decisión de Daniel), `treasury.create_movements`, `materials.view`, `materials.view_prices`, `tariffs.view`.

`scripts/alcance_rol.py` sobre el inventario AST da **89 rutas** a las que llegan esos permisos (v1.4: `treasury.view_all_movements` no lo exige ninguna ruta como dependencia, así que el número no cambia) (`alcance_rol_ingrid.tsv`). Las **32 filas** de §5.2 están todas dentro de esas 89 (la 27b, `payment-to-generic`, entra por H5 = a, decidida; la 15b, `GET /third-party-categories/flat`, está en la línea 88 del tsv con `third_parties.view`). Lo medí con un `grep -F` de las 31 de la v1.4 contra `alcance_rol_ingrid.tsv`: aparecen las 31, una vez cada una; la 15b la agrega la v1.5. Las **otras 57 quedan cerradas para el usuario con alcance**. La cifra exacta la fija T2b. Por ejemplo, quedan cerradas:
- los 15 POST de tesorería fuera de S7;
- `PATCH /purchases/{id}/liquidate`, la liquidación directa sin pasar por la Entrada;
- `POST /inbound-orders/{id}/confirm`, que confirma una Willard;
- `/third-parties/customers`, `/investors`, `/liabilities`, `/provisions`, `/generic` y `/payable-suppliers`;
- `/third-parties/retention-entities` y `retention-configs` (S5);
- las demás rutas de categorías de terceros: el listado paginado, el detalle `GET /third-party-categories/{id}`, el alta, la edición y la baja. Solo `/flat` se abre (fila 15b);
- las listas de precios por proveedor (`/price-list-groups/*`, que revelan la membresía de los proveedores de SAC);
- `/purchases/pending`, `/by-number`, `/supplier/{id}`, `check-duplicate` y `check-invoice`;
- `/money-movements/summary` y `/by-number`;
- el PATCH y el DELETE de adjuntos;
- `GET /roles` y `GET /roles/{id}`.

### 5.2 La lista blanca y la regla de cada ruta

Notación: `alc(tp)` = `tp.collector_id == scope`; `cta(k)` = `k ∈ cuentas asignadas` (con alcance, lista vacía = ninguna); fuera de alcance → **404** (no revela que existe).

| # | Ruta | Regla con alcance |
|---|---|---|
| 1 | `GET /roles/my-permissions` | sin filtro; devuelve `collector_scope` |
| 2 | `GET /materials` | todos los materiales, **sin** stock ni costo (§5.7) |
| 3 | `GET /materials/{id}` | lo mismo |
| 4 | `GET /material-kg-profiles` | sin filtro: orden del formato (#121) y unidad; los campos de §5.7 |
| 5 | `GET /service-tariffs/current` | **solo** `comision_green_loop` (§5.7) |
| 6 | `GET /price-lists/current` | `third_party_id` **obligatorio** y `alc`: sin él → 422, ajeno → 404. Solo `purchase_price`, sin `sale_price` (§5.7) |
| 7 | `GET /inbound-orders` | se **fuerza** `collector_id = scope`; un `collector_id` del query se ignora |
| 8 | `GET /inbound-orders/{id}` | 404 si `order.collector_id != scope` |
| 9 | `POST /inbound-orders/{id}/liquidate` | Todo se valida **antes de escribir** (D14 de #93): un rechazo no deja nada. Las reglas:<br>• 404 como en la fila 8.<br>• Todo proveedor del reparto tiene que ser `alc`. Si no, 422 **genérico**, «Hay un proveedor fuera de tu alcance»: no nombra a lo ajeno (M1), porque su selector solo ofrece lo suyo y el nombre solo le llegaría a quien arma UUIDs a mano.<br>• Toda cuenta de `supplier_payments` tiene que ser `cta` (si no, 403).<br>• Comisión (S6/D-a): el tercero es su recolector, y el monto lo calcula el servidor. Si viene otro tercero u otro `amount` → 422.<br>• Si vienen `supplier_retentions` o impuestos → 422 (S5).<br>• **9e (v1.6):** si alguna compra **viva** (no cancelada) del puente de la Entrada es de un proveedor que no es `alc` → 422 «Esta Entrada tiene una compra de un proveedor fuera de tu alcance: la vuelve a liquidar SAC». Sin ella, cambiar ese proveedor por uno suyo en la misma compra pasaba la regla del reparto y el servicio cancelaba la compra ajena (R6 de #122).<br>• **9f (v1.6, definición de la v1.7):** si el lote de la **última liquidación** de alguna compra viva del puente trae retenciones o IVA → 422 «Esta Entrada tuvo retenciones o IVA en su liquidación anterior: la vuelve a liquidar SAC». Sin ella, se perdían en silencio. El lote lo da `last_liquidation_batch`, la misma función de la precarga (v1.7); una liquidación posterior sin retenciones ni IVA lo deja vacío.<br>Las dos solo existen en una Entrada que SAC ya liquidó y des-liquidó; en la primera liquidación el puente está vacío. Los mensajes no nombran a nadie (M1) y son distintos entre sí, para que cada test sepa qué regla disparó.<br>• **9g (v1.10, Daniel):** todo lo pesado queda repartido. Si en algún material el descuadre es distinto de cero (falta o sobra, sin importar la tolerancia) → 422 «Con tu alcance hay que repartir todo lo pesado — <material: qué falta>; …. Si no se puede repartir todo, esta Entrada la liquida SAC».<br>&nbsp;&nbsp;– El mensaje nombra **materiales**, no terceros: son de la Entrada que ella ve.<br>&nbsp;&nbsp;– Corre en el servicio (`require_full_allocation`), en el mismo lazo del descuadre y antes de D8/D16.<br>&nbsp;&nbsp;– Razón: el descuadre se valora al precio de referencia y aterriza en los libros de SAC; sin descuadre, el precio que ella mande no tiene efecto.<br>&nbsp;&nbsp;– **n13 (v1.11):** una línea pesada con cuarto decimal (Numeric(15,4) contra ALLOC_Q 0,001) deja un descuadre que ella no puede repartir: esa Entrada la liquida SAC. En producción hay 0 casos (604 líneas enteras, `gate-prod/n13_cuarto_decimal_prod.log`). |
| 10 | `GET /third-parties` | se fuerza `alc` |
| 11 | `GET /third-parties/suppliers` | se fuerza `alc` |
| 12 | `GET /third-parties/similar` | se fuerza `alc` (no revela nombres de proveedores de SAC) |
| 13 | `GET /third-parties/payable-providers` | devuelve solo el recolector de su alcance (selector de la comisión, S6) |
| 14 | `GET /third-parties/{id}` | 404 si no `alc` |
| 15 | `POST /third-parties` | `collector_id` = scope, **forzado por el servidor**, con lo que venga en el payload. **H1:** `initial_balance ≠ 0` → 422, porque si no Ingrid podría inventar una CxP sin movimiento (rompe #55) y pagarla desde K1. `category_ids`: cada categoría tiene que estar en `scoped_create_categories` (v1.5, la **misma** función que alimenta la fila 15b): toda categoría activa de proveedor de material, y la de conductor solo si es «Empleados» (S2). Cualquier otra → 422: investor/«Socios», customer, liability, provision, service_provider, y también un generic que no sea «Empleados» (por ejemplo «Genérico»). Vacío → 422 (un tercero sin categoría no sirve en su selector). `ThirdPartyCreate` no cambia para quien no tiene alcance. |
| 15b | `GET /third-party-categories/flat` | (v1.5) Devuelve **solo** `scoped_create_categories(db, org)`, en la forma de siempre. El `behavior_type` del query se aplica como intersección: con `customer`, la respuesta va vacía. La función:<br>• toda categoría **activa** con `behavior_type = material_supplier`;<br>• la generic cuyo nombre, pasado por `normalize_entity_name`, es igual al de la constante `SCOPED_CONDUCTOR_CATEGORY = "Empleados"`.<br>**Falla cerrado:** renombrada o desactivada, no aparece ninguna generic, y nunca «cualquier generic». El esquema solo trae id, nombre, nombre a mostrar, padre, tipo y activo, sin montos (verificado por Eco QA 2). Las categorías de sistema (Retenciones, Impuestos) son liability, así que quedan fuera. Las demás rutas de categorías siguen cerradas (T1) |
| 16 | `GET /purchases` | se fuerza `alc(purchase.supplier)` |
| 17 | `GET /purchases/{id}` | 404 si no `alc(supplier)` |
| 18 | `GET /attachments` | solo dueño compra con `alc(supplier)`; venta y transformación → 404 |
| 19 | `GET /attachments/{id}/download` | igual que la fila 18 |
| 20 | `GET /money-movements/third-party/{id}` | 404 si no `alc`; si es `alc`, **historia completa sin filtro de cuentas** (D-E1) |
| 21 | `GET /money-accounts` | solo `cta`; lista vacía = **ninguna** |
| 22 | `GET /money-accounts/{id}` | 403 si no `cta` (comportamiento actual) |
| 23 | `GET /money-movements/account/{id}` | 403 si no `cta` (actual) |
| 24 | `GET /money-movements` | `cta(account)` **o** (`account IS NULL` **y** `alc(tp)`) |
| 25 | `GET /money-movements/{id}` | el mismo predicado; si no, 404 |
| 26 | `POST /money-movements/supplier-payment` | `cta(account)` (si no, 403) y `alc(tp)` (si no, 404). El guard de tipo de tercero existente no se toca |
| 27 | `POST /money-movements/advance-payment` | igual |
| 27b | `POST /money-movements/payment-to-generic` | **H5 = a, decidida.** Mismas reglas que la fila 26: es el pago o anticipo a un conductor *generic* de su alcance (S2) |
| 28 | `POST /money-movements/{id}/annul` | **H2:** cuatro condiciones, todas:<br>• `movement_type ∈ PROPIOS = {payment_to_supplier, advance_payment, payment_to_generic}`;<br>• `alc(tp)`;<br>• `cta(account)`;<br>• `transfer_pair_id IS NULL`.<br>Si falta alguna → 404. Así no anula un `transfer_in` de K1 que hizo Johana (`annul` anula también el par en K2, `money_movement.py:1126-1133`), ni un pago de Johana a B desde K1, ni una causación |
| 29 | `GET /money-movements/{id}/evidence` | el predicado de la fila 25 (solo lectura) |
| 30 | `POST /money-movements/{id}/evidence` | **H2:** el predicado de la fila 28. Así no reemplaza la evidencia de un movimiento de Johana |

Son 32 filas (30 más la 15b y la 27b). Las filas 2 y 3, y las 29 y 30, pueden reducirse si la pantalla no las usa; se cierran en la construcción y **la lista final la fija T2b** (doble entrada, §12).

### 5.7 Lista blanca de CAMPOS (H3)

Green Loop es otra empresa: que una ruta esté permitida no quiere decir que todos sus campos lo estén. Con alcance:

| Ruta | Campo de SAC | Con alcance | Por qué |
|---|---|---|---|
| `GET /materials`, `/materials/{id}` | `current_stock`, `current_stock_liquidated`, `current_stock_transit`, `current_average_cost` (`schemas/material.py:83-86`) | **`null`** | Son el inventario y el costo de SAC. Los cuatro campos pasan a `Optional[float]` en `MaterialResponse`. Sin alcance llegan con su número de siempre: el JSON no cambia, porque un `float` no nulo se serializa igual. `/materials` no es captura del golden (se verifica con `grep` sobre `CAPTURES`) |
| `GET /price-lists/current` | `sale_price` | **`null`**, y `third_party_id` obligatorio y `alc` (fila 6) | Son los precios de venta de SAC. Sin `third_party_id` y con #98 D10 (org sin listas activas) devolvería la lista general entera |
| `GET /service-tariffs/current` | las demás tarifas (maquila Willard, abono a planta, flete, crisol, maquila intersede) | **fuera**; solo `comision_green_loop` | Son los precios de SAC con Willard y con su planta |
| `GET /material-kg-profiles` | `willard_world`, `compra_regular`, `lead_product`, `form_order` | se quedan | Es la clasificación de cada material, no tiene montos. La pantalla los usa para el orden del formato (#121). Queda declarado |
| `GET /inbound-orders/{id}` | `discrepancy_adjustments` (valorado al precio de referencia), `liquidated_by_name` y demás nombres de usuarios | se quedan | Es su Entrada; el descuadre lo valoró ella misma al liquidar (#93) |
| `GET /money-movements/third-party/{id}` | nombre de una cuenta de SAC en un pago viejo | se queda (D-E1) | El saldo corrido tiene que cuadrar con el vivo (#55) |
| `GET /third-parties*` | `current_balance` de sus terceros | se queda | Es el saldo de lo suyo |
| `GET /third-party-categories/flat` (v1.5) | las demás categorías de terceros de SAC | **fuera**: solo las de `scoped_create_categories` | Ve los nombres de las categorías de proveedor de SAC y el de «Empleados». No hay montos ni miembros |

**Test:** T19, «ausencia de lo de SAC», con usuario con alcance y su control sin alcance en el mismo test:
- en `/materials`, los cuatro campos son `null` en **todas** las filas; el control ve números distintos de 0 en al menos una fila (contra la vacuidad: el fixture siembra stock por API);
- en `/price-lists/current`, no hay ningún `sale_price` distinto de `null`; el control ve al menos uno distinto de 0;
- en `/service-tariffs/current`, el conjunto de `tariff_code` es exactamente `{comision_green_loop}`; el control ve ≥ 2.

### 5.3 Códigos: una regla para cada uno

- **404**: el objeto existe, pero está fuera de su alcance. Aplica a terceros, Entradas, compras, movimientos, adjuntos y al `third_party_id` de precios. No revela que existe.
- **403 «Fuera de tu alcance: …»**: la ruta no está en la lista blanca.
- **403 «No tienes acceso a esta cuenta»**: la cuenta no está asignada, en lectura o en escritura. Es el mensaje que ya existe; se conserva para no partir el código ni cambiarles el mensaje a los usuarios de Costa.
- **422**: un payload que mezcla lo suyo con lo ajeno, por ejemplo un proveedor ajeno en el reparto, la comisión a otro recolector, saldo inicial o una categoría no permitida. El mensaje es **genérico y no nombra lo ajeno** (M1): en su pantalla lo ajeno no aparece, así que el nombre solo le llegaría a quien arma el payload a mano.

### 5.4 Por número, export, PDF, búsqueda y contadores (QA 2, punto 2)

- **Por número:** `GET /purchases/by-number/{n}` y `GET /money-movements/by-number/{n}` quedan **fuera** de la lista: 403 de ruta, con test en T1. Ninguna pantalla de Ingrid los necesita.
- **Export a Excel y PDF:** son client-side (#52, #119) y se arman con lo que devuelven el listado y el detalle, ya filtrados. No hay endpoint de export que filtrar. `fetchAllPages` (#72) pagina sobre el mismo listado.
- **Búsqueda de Entradas** (`search`, que usa EXISTS sobre tercero, material y placa, y el `third_party_id` del query): corre **dentro** del filtro forzado por recolector, así que solo acota lo suyo. Test: `search` con el nombre de B → 0 resultados para Ingrid y ≥ 1 para el control.
- **Contadores:** el badge de Entradas del sidebar (`usePendingEntriesCount` / `useEntriesStatusCounts`) sale del mismo `GET /inbound-orders`, así que cuenta solo lo suyo. Test: el `total` del listado con alcance es 1, y con el mismo rol sin alcance es 3.
- **`amount_sum` / `total`** de los listados de compras y movimientos se calculan **después** del filtro (test: suma igual a la de sus filas).

### 5.5 Escrituras que podrían ampliar el alcance (QA 2, punto 4)

| Escritura | Con alcance | Test |
|---|---|---|
| Cambiar el `collector_id` de una Entrada (`PATCH /inbound-orders/{id}`) | fuera de la lista → 403 (S4) | T1 + caso explícito |
| Crear una Entrada (`POST /inbound-orders`) | fuera de la lista → 403 | T1 |
| Crear un tercero | nace con su recolector, **forzado** (fila 15) | fila 15 |
| Editar un tercero (`PATCH /third-parties/{id}`), o sea poner o quitar la marca | fuera de la lista → 403 | T1 + caso explícito |
| Poner o quitar el alcance (`PUT /organizations/…/collector-scope`) | no pasa por el contexto de org: guard `is_admin`, y Ingrid no es admin → 403 | T16 |
| Asignarse cuentas (`PUT …/account-assignments`) | mismo guard admin → 403 | T16 |
| Editar roles (`/roles` POST, PATCH y DELETE) | fuera de la lista → 403 (además, `admin.manage_roles`) | T1 |
| Liquidar con un proveedor ajeno | 422 (fila 9) | fila 9 |
| Pagar o anticipar a un tercero ajeno | 404 (fila 26) | fila 26 |

### 5.6 Fugas laterales que quedan, declaradas

- **D-E2, una Entrada suya con un proveedor ajeno adentro.** Si Johana (sin alcance, S1) liquida E_GL con el proveedor B, Ingrid ve en el detalle de E_GL el nombre de B y el resumen de su compra, porque la Entrada es de ella (S8). La compra de B, en cambio, le da 404. Para cerrarlo hay dos opciones: (a) declararlo como está (recomendado: es la Entrada de Green Loop y lo puso alguien de SAC a propósito); (b) en una Entrada con recolector GL, que Johana reciba un **aviso** (no un bloqueo) al repartir a un proveedor sin la marca. Lo decide Daniel junto con Q-70 (decisión 3). **Decidido: (a)** (§15, decisión 3).
  - **v1.6, el link de esa compra.** Con (a), el criterio es marcar, no esconder: el detalle de Ingrid pinta esa compra **sin link** y con la nota «Proveedor sin la marca de Green Loop: pídele a SAC que lo marque en Terceros» (§8). Así no hay un link que dé 404, y ella sabe qué pedir. La marca la pone Johana, o quien tenga `third_parties.edit`, desde Terceros → «Recolector».
  - ~~**v1.6, propuesta que reabre D-E2 y decide Daniel:** que la respuesta de liquidar traiga un aviso cuando quien liquida una Entrada con recolector reparte a un proveedor que no tiene esa marca. No se construye sin el OK de Daniel.~~ **Decidido (v1.8): (b)**, Daniel, 20-nov ~14:25.
  - **El aviso (v1.8).** Lo arma `inbound_order_service.liquidate` y viaja en `warnings[]` de la respuesta; `useLiquidateInboundOrder` ya lo muestra en un toast. Avisa, no bloquea (#17/#76).
    - **Cuándo:** la Entrada tiene recolector, un proveedor del reparto no tiene esa marca (sin marca, o con la de otro recolector), y ese recolector tiene al menos un usuario con alcance en la org. Sin ese usuario nadie pierde nada y no se avisa.
    - **Uno por proveedor**, ordenados por nombre. El texto es «El proveedor {X} no tiene la marca de {recolector}: {usuario} verá esta compra en la Entrada, pero no podrá abrirla. Si es de {recolector}, márcalo en Terceros → Recolector.» `{usuario}` es el nombre de quien tiene el alcance; con más de uno, se nombran todos y el verbo va en plural.
    - Un usuario con alcance nunca lo recibe: la fila 9 le exige que todo el reparto sea suyo.
    - **n8 (v1.9):** cuenta solo un usuario con alcance **activo** (`User.is_active`).
    - **n10, camino vecino (v1.9):** el aviso sale solo al liquidar. Si la marca se quita después (`PATCH /third-parties/{id}`), no hay aviso, y la red es la nota del detalle de Ingrid (§8).
- **Su caja muestra todo lo que pasa por su caja.** Si Johana paga a B desde K1, Ingrid ve ese movimiento con el nombre de B, porque la cuenta es suya (fila 24). Es correcto por definición de «su caja».
- **D-E1:** en el estado de cuenta de un proveedor suyo puede aparecer el nombre de una cuenta de SAC (§5.2).

**D-E1, la historia completa del estado de cuenta en alcance.** Si se filtrara por cuenta, el saldo corrido de un proveedor de Green Loop no cerraría contra su saldo vivo (§2.5), justo en los proveedores que tienen saldo inicial o pagos hechos desde una cuenta de SAC. El tercero ya es suyo; lo que le restringe la cuenta es la **caja que opera**, no la historia que lee. Costo: Ingrid ve el nombre de la cuenta de SAC desde la que se pagó a uno de sus proveedores.

## 6. El hueco preexistente de cuentas (Costa ya lo tiene)

Para el usuario con alcance, el hueco se cierra **en este ciclo**, decida lo que decida Daniel sobre Costa. Su caja queda cerrada por dos razones independientes:
- todas las rutas de tesorería que él puede tocar (filas 21 a 30) llevan el chequeo de cuenta escrito en su regla;
- todas las demás (by-number, los otros 15 POST de creación, el DELETE de evidencia) están **fuera de la lista blanca** y le dan 403 antes de llegar al código.

Ninguna ruta que mueva o muestre dinero queda sin una de las dos, y lo prueban T1 más las filas 21 a 30. Para el usuario restringido **sin** alcance (los 2 de Costa), propongo un helper único `account_access(db, ctx)` que aplicarían todos los caminos:

- **C1** `GET /money-movements/{id}`, `/by-number/{n}` y la evidencia → 404 si la cuenta no está asignada.
- **C2** los 17 POST de creación, más `transfer` (las dos cuentas) y los pagos inmediatos al liquidar compra, venta o Entrada → 403 si la cuenta no está asignada.
- **C3** listado: el `account_id IS NULL` deja de pasar entero. Opción a decidir: o se ocultan las causaciones, o pasan solo las de terceros con los que el usuario tiene movimientos.
- **C4** estado de cuenta por tercero: se deja como está (D-E1 aplica solo con alcance).

**C2 cambia lo que pueden hacer hoy los 2 usuarios de Costa:** si hoy registran un pago desde una cuenta no asignada, mañana recibirían 403.

**Decidido por Daniel (20-nov, me lo pasó el Coordinador; decisión 1): CICLO PROPIO, justo después de este. Este ciclo no le cambia nada a Costa.** Para los usuarios sin alcance, `_get_allowed_accounts` y los cuatro caminos C1–C4 quedan como hoy; T18 lo afirma. El helper y los cuatro puntos quedan escritos aquí como insumo de ese ciclo.

## 7. El balance: Green Loop por aparte

- **Balance Detallado, vivo y as-of.** En cada sección de terceros (CxP proveedores, anticipos a proveedores, CxC, etc.), los terceros con `collector_id` van en un grupo «Recolector: <nombre>», que manda sobre el grupo de categoría. Usa el esquema existente `BalanceDetailedGroup` (#38): **cero claves nuevas**.
- **Costo:** una consulta `SELECT id, collector_id WHERE organization_id=? AND collector_id IS NOT NULL`, vacía en las otras 6 orgs, así que el agrupado queda idéntico por construcción.
- **Balance General: no cambia.** Decidido por Daniel (20-nov, vía el Coordinador; decisión 2): solo el Detallado agrupa, sin claves nuevas en el General.
- **Terceros:** filtro y columna «Recolector» en `ThirdPartiesPage` (`GET /third-parties?collector_id=`, gated por el flag). Es el «estado de las cuentas… por aparte» de la fila del 19-nov.

## 8. Pantalla

Va con capturas a 1440 y 390; la de Daniel es condición de deploy.

- **Config → Usuarios:** selector «Alcance: recolector» junto a la asignación de cuentas, gated por flag y admin.
- **Terceros:** en el formulario, selector «Recolector», gated por el flag y `third_parties.edit`; en el listado, columna y filtro.
- **Con alcance**, la pantalla deja de pedir lo que el backend le niega:
  - en la liquidación, sin `useKgAccounts` (hoy excluye al titular Willard del selector; con alcance, el servidor ya filtra), sin `useRetentionRows` y sin el bloque de IVA;
  - la comisión, con el recolector fijo;
  - en Entradas, sin el filtro de sede ni la pestaña de crear.
  Todo es `enabled: !scope` en los hooks, para que no salgan 403 en la consola.
- **Barra superior:** chip «Green Loop» para que Ingrid sepa por qué ve menos.
- **Sin alcance**, ninguna pantalla compartida cambia: el selector de Johana sigue igual (S1).
- **v1.6, Entradas que SAC ya tocó (solo con alcance):**
  - **Liquidar una Entrada des-liquidada.** La página ya trae, por compra del puente, el último lote de retenciones e IVA, y ya carga los proveedores de su alcance (fila 11). Si una compra viva trae retenciones o IVA, o es de un proveedor que no está en esa lista, la página muestra un aviso con el mismo texto de la regla 9e o 9f y **deshabilita Liquidar**. Ella se entera al abrir, no al enviar. El 422 del servidor sigue siendo la red.
  - **Detalle de la Entrada.** Una compra cuyo proveedor no está en su alcance se pinta **sin link**, con la nota de §5.6. Se mide con el sondeo de red: 0 respuestas ≥ 400.
- **v1.10, 9g (solo con alcance):** en la liquidación, cada material con descuadre suma un problema en la lista que ya existe: «<material>: faltan N por repartir — con tu alcance hay que repartir todo lo pesado; si no se puede, esta Entrada la liquida SAC». Liquidar queda deshabilitado. Se esconden la casilla «Sin proveedor (intencional)» y el bloque del material que la báscula no pesó. Sin alcance, la pantalla queda igual.

**v1.5, lo que medí y cómo se cierra.** Sondeo de red como usuario con alcance (`sondeo_red_r1.log`). Toda respuesta ≥ 400, por pantalla:

| Pantalla | Rutas con 403 de alcance | Cierre, **solo con alcance** |
|---|---|---|
| `/` Dashboard | `/reports/dashboard` | el inicio redirige a Entradas |
| `/inbound` | `/warehouses` (filtro de sede) | `enabled: !scope`, sin el filtro |
| `/inbound/:id` | `/material-conversion-formulas/current` (kg estimados de Willard) | `enabled: !scope` |
| `/inbound/:id/liquidate` | `/kg-ledger/accounts`, `/third-parties/retention-entities` | `enabled: !scope`; sin retenciones ni IVA, comisión fija |
| `/third-parties` | `/third-party-categories/flat` | **fila 15b (backend)** |
| `/treasury/new` | `payable-suppliers`, `customers`, `provisions`, `liabilities` (×2), `generic`, `/expense-categories/flat` | solo los tres tipos de S7, y el selector de tercero sale de `GET /third-parties` (fila 10, filtrado por el servidor) |

Además, el **menú**: con alcance muestra solo Entradas, Tesorería (Movimientos, Terceros, Cuentas) y Terceros. Las otras entradas que su rol alcanzaría (Gastos Masivos, Retenciones, Listas de Precios, Cat. Terceros, Tarifas, Precio del Plomo) le darían 403.

**Prueba de que las pantallas compartidas no cambian** (Coordinador):
- un usuario normal de Costa (sin alcance) recorre las pantallas tocadas antes y después del cambio, y el registro de red es igual: **0 requests de más o de menos**;
- una captura de Costa de cada pantalla tocada, a 1440 y 390;
- con alcance, el sondeo se re-corre con **0 respuestas ≥ 400** (`sondeo_red_r2.log`, pedido de Eco QA 2).

El frontend solo esconde; el 403 del servidor sigue siendo la red.

## 9. Marca inicial (carga)

**Decisión 4 nueva (Daniel, 20-nov, vía el Coordinador; reemplaza la de la v1.2):** «todo lo que diga green loop es green loop». A Johana **no** se le manda lista. La regla corre contra la base que se marca (en producción, al deploy), nunca contra una lista sacada de dev, porque los ids de producción son otros.

`scripts/marcar_recolector.py --api-url <url> --org-id <uuid> --collector-id <uuid> [--apply] [--esperado N]`. Las credenciales salen solo de `SEED_SU_EMAIL`/`SEED_SU_PASSWORD` y no se imprimen (#114).

**La regla.** Se marca un tercero si cumple las cuatro condiciones:
1. es de la org de `--org-id`. **Nunca por nombre:** en dev hay cinco orgs «SAC» (cuatro inactivas) y cuatro «SAC (archivada …)», y la regla atraparía 876 terceros. Costa tiene «Bio Green Loop- Maquila» y «Maquila Greenloop», que también la cumplen (Eco QA 2, `medir_regla_greenloop.log`). Es la trampa de #93 y #112;
2. su **nombre normalizado** contiene `greenloop` o `greenlop`. Normalizar es: NFKD, quitar las marcas diacríticas, minúsculas y dejar solo `a-z`; se borra todo lo demás (espacios, guiones, paréntesis, dígitos). La función es una sola y la cubre T21;
3. está activo;
4. no está en las exclusiones.

**Exclusiones.** Cada una se imprime con su motivo:
- el **recolector mismo**, por su id (`--collector-id`). Es S3, y además la marca no puede apuntar a su propio tercero (§3);
- **«BIOGREENLOOP»**, por nombre normalizado exacto `biogreenloop`. Es proveedor de material con saldo −$150.000.000. Decisión de Daniel del 20-nov: queda fuera, como el recolector, porque parece la cuenta de la empresa Green Loop con SAC, y esa la maneja Johana.

Si una exclusión **no aparece** entre los que cumplen la regla, o aparece más de una vez, la corrida es ruidosa y sale con **exit 3** (fail-loud). El nombre pudo cambiar en producción, y entonces ese tercero quedaría marcado sin que nadie lo viera.

«ASOCIACION BIOGREEN RECYCLING» y «ECOGREEN» no cumplen la regla y no se marcan.

**Inactivos: se saltan.** Se listan con el motivo «inactivo» y no cambian el exit. Un tercero inactivo tiene saldo 0, porque desactivar lo exige, y no aparece en los selectores; si se reactiva, se marca a mano con `PATCH`. En la SAC activa de las dos copias hay 0.

**Idempotencia:**
- ya marcado con el mismo recolector → se salta, con el motivo «ya marcado»;
- marcado con **otro** recolector → no se pisa, y **exit 3**;
- marcado con este recolector pero fuera de la regla (una marca hecha a mano) → se lista como informativo, no se desmarca y no cambia el exit.

**Antes de la primera escritura, aborta con exit 2 si:**
- la org no existe o está inactiva: `GET /organizations/{id}` le da 404 al superusuario;
- la org no tiene `kg_ledger_enabled`;
- el recolector no existe en esa org, está inactivo o no es service_provider. Son las reglas de §3; el `PATCH` las volvería a validar, pero así se detecta antes de escribir la primera fila;
- el listado de terceros no trae `len == total`. Se pagina hasta el total, como `list_all` de #115.

**Salida.** Dry-run por defecto; `--apply` escribe con `PATCH /third-parties/{id}` y `{"collector_id": …}`.
- Imprime los conteos: cumplen la regla, activos, excluidos por motivo, ya marcados y a marcar. Después, la lista de los que marca y la de los excluidos con su motivo.
- `--esperado N` (opcional): si los «a marcar» no son N, sale con exit 3 sin escribir. El Coordinador escribe la predicción antes de correr.
- **Con cualquier sorpresa (exit 3) no escribe nada**, ni con `--apply`. El plan entero se arma antes de la primera escritura.
- Un `PATCH` que falla detiene la corrida con exit 1. Lo ya marcado queda y se re-corre: es idempotente.
- **Exit 0 solo si no hubo sorpresas.** Un script que muere no se puede leer como «nada que marcar».

Contra producción la corre solo el Coordinador, con el OK de Daniel (§16).

## 10. Migración: una sola línea

`e7f9a1b3c5d8_recolector_alcance.py`, `down_revision = d6e8f0a2b4c7` (cabeza actual, `alembic heads`). El id está libre (grep vacío). Cambios:
- `third_parties.collector_id` UUID nullable, FK `third_parties.id` con nombre por defecto (`create_foreign_key(None, …)`, lección de #111), **sin `ondelete`, o sea NO ACTION** (n1 de QA 2 a la v1.2), e índice `ix_third_parties_collector_id`. Es una FK **autorreferente**: en PostgreSQL, RESTRICT se chequea fila por fila durante la sentencia, así que un DELETE de varias filas que incluya al recolector y a sus marcados podría fallar según el orden. NO ACTION se chequea al final de la sentencia. Las dos impiden borrar solo al recolector, que es lo que importa. Hoy no hay borrados masivos (grep vacío en `app/`, `scripts/` y `tests/`, QA 2). **Sin `relationship` inversa en el ORM:** con la cascada por defecto de SQLAlchemy, la sesión pondría NULL en los marcados antes del DELETE, y T20 dejaría de medir la base;
- tabla `user_collector_scopes` con `UNIQUE(organization_id, user_id)` e índice por `organization_id` (lo declara el mixin, lección de #100). Sus tres FKs llevan **`ondelete="RESTRICT"` explícito** (N1). Ninguna es autorreferente, así que el problema del orden de n1 no aplica: la fila de alcance vive en otra tabla y un DELETE de terceros no la puede borrar en la misma sentencia. Tampoco hay `relationship` inversa hacia el alcance, por la misma razón que en `collector_id`. **No se calca el CASCADE de `user_account_assignments`** (`models/user.py:113-119`): con CASCADE, borrar al recolector borra la fila de alcance, y entonces Ingrid **ve todo** (fail-open). Hoy el borrado de un tercero es lógico (`third_parties.py:473`) y no se llega a eso por API; con RESTRICT queda imposible por construcción. El parity check compara el `ondelete` entre modelo y migración.

El modelo declara lo mismo, y la paridad se verifica con `schema_parity_check.py`. Es aditiva pura: NULL y tabla vacía en las 7 orgs.

**Downgrade:** borra las marcas y los alcances. Después de re-subir, hay que volver a marcar y volver a asignar.

Turno de migración: lo asigna el Coordinador. Si `develop` recibe otra antes, cambio el `down_revision` y eso es un delta para QA.

## 11. Golden: **aplica**

- **Por qué aplica:**
  - columna nueva en tabla compartida (`third_parties`);
  - código en el camino de **todas** las orgs: `get_required_org_context` (cada request), los listados de terceros, compras y movimientos, y `reports.py` (balance detallado).
  - Cinco de las capturas pasan por lo tocado: `balance_detailed`, `balance_detailed_asof`, `money_accounts`, `money_movements` y los dos `tp_statement`.
- **Qué se espera:** **0 diffs y 0 claves aditivas.** `ThirdPartyResponse` no es captura: `/third-parties` solo se llama para *elegir* el tercero del statement, y se re-verifica con un `grep` sobre `CAPTURES` antes de correr. Y en las 3 orgs no hay marcas ni alcances.
- **Como «0/0» no distingue nada de nada (#110), lleva dos pruebas propias:**
  - **Prueba de vida:** `PUT …/collector-scope` da 404/405 en la base y 401/403/200 en la rama.
  - **Control positivo fuera de CAPTURES (smoke):** en mi BD de dev, marcar 3 proveedores de SAC y pedir el detallado de SAC en los dos procesos. El grupo «Recolector: Green Loop» aparece solo en la rama.
- **Forma:** una sola BD (la migración es aditiva). Se corre con `golden_run.sh` (procedencia: PID y log), puertos 8091/8092 y `lockf`.

## 12. Tests

Archivo nuevo `tests/test_sac_recolector_alcance.py`.

**Fixture:** org con flag; recolectores **GL** y **X** (service_provider); terceros **A** y **A2** (GL), **B** (sin marca), **C** (de X), **D** (conductor generic de GL) y **E** (generic sin marca); Entradas **E_GL**, **E_none** y **E_X**; cuentas **K1**, asignada a Ingrid, y **K2**.

**Usuarios** (nunca admin, que bypassa, #29):
- `ingrid`: rol Recolector, alcance GL, K1;
- `ingrid_libre`: el **mismo rol sin alcance**, que es el control positivo de cada filtro;
- `ingrid_todo`: rol con **todos** los permisos del catálogo y alcance GL;
- `todo_libre`: todos los permisos, sin alcance;
- `johana`: admin.

**El cuadrante, dibujado** (lección de *dibujar-el-cuadrante*). Cada fila de §5.2 tiene sus tres celdas:

| Ruta (fila §5.2) | con alcance, objeto en alcance | con alcance, objeto fuera | sin alcance, mismo rol (control) |
|---|---|---|---|
| 7 Entradas lista | ve E_GL | no ve E_none ni E_X; con `?collector_id=X` sigue viendo solo E_GL | ve las 3 |
| 8 Entrada detalle | 200 | 404 (E_none, E_X) | 200 |
| 9 liquidar | 200 con A; la comisión queda en tarifa × base aunque no se mande `amount` (D-a = a) | 422 con B, 422 con C (los dos **sin el nombre**, M1), 403 con K2, 422 comisión a X, 422 `amount` distinto del calculado (D-a = a), 422 con retención/IVA; **las 7 tablas sin cambios**. Cada caso afirma también el **mensaje**, no solo el código: un 422 de validación del schema pasaría por el status (v1.6). Des-liquidada por SAC: 9e y 9f (T25b, T25c) | 200 con B; la comisión toma el `amount` digitado |
| 10–13 listados de terceros | solo GL (+ D en 10) | sin B ni C | ven B y C |
| 14 tercero detalle | 200 A | 404 B | 200 B |
| 15 crear tercero | nace con GL aunque el payload diga X; con categoría material_supplier → 201; con «Empleados» → 201 (v1.5) | `initial_balance` ≠ 0 → 422; categoría investor, customer o liability → 422; generic «Genérico» → 422 (v1.5); sin categoría → 422. **Ninguna fila escrita** | nace sin marca, con su `initial_balance` y cualquier categoría (comportamiento de hoy) |
| 15b categorías (v1.5) | solo las categorías de proveedor de material y «Empleados»; un id de ese flat sirve para crear (201) | con `?behavior_type=customer` → vacío; «Genérico» no aparece | ve todas, con o sin `behavior_type` |
| 16–17 compras | lista y detalle de A, **también la que nació en E_none** (S8, D-b = a) | 404 compra de B | ven la de B |
| 18–19 adjuntos | lista y descarga de la compra de A | 404 compra de B y venta | 200 |
| 20 estado de cuenta | A: **corrido == vivo** con un pago desde K2 adentro | 404 B | B 200 |
| 21–23 caja | solo K1; sin asignaciones → **ninguna** | K2 403 | sin asignaciones ve K1 y K2 (comportamiento actual, regresión) |
| 24–25 movimientos | ve K1, **incluido el fondeo K2→K1 que hizo Johana** (con `view_all_movements`, v1.4), y la causación de A | no ve la causación de B (cuenta NULL); detalle de K2 404 | ve todo |
| 26–27 pagar/anticipar | K1→A 201 | K2 403; →B 404; **→D 400 (guard de tipo existente, intacto)** | K2→B 201 |
| 27b pago a generic (H5 = a) | K1→D 201 | K2 403; →E (generic sin marca) 404 | K2→E 201 |
| 28 anular | su pago K1→A | transferencia K1↔K2 de Johana: **404, y el par en K2 sigue `confirmed`**; pago de Johana K1→B 404; causación de A (cuenta NULL) 404; movimiento de K2 404 | anula todo lo que hoy anula |
| 29–30 evidencia | ver y subir en su pago K1→A | subir en el pago de Johana K1→B 404 (su evidencia no cambia); ver la de un movimiento de K2 404 | 200 |
| §5.0 miembros | `GET /organizations/{id}` 200 (con `settings`) | `GET …/members` 403 y las otras 8 de miembros 403 | `GET …/members` 200 |
| §5.7 campos | ver T19 | ver T19 | ver T19 |

**El cuadrante de quién × flag × recurso** (QA 2, punto 7). Ruta de muestra: `GET /inbound-orders/{id}`; la misma tabla vale para la familia T1 cambiando «200/404» por «pasa / 403 de ruta».

| Usuario | Flag | Recurso propio (E_GL) | Recurso ajeno (E_none) | Test |
|---|---|---|---|---|
| con alcance (rol Recolector) | on | 200 | 404 | fila 8 |
| con alcance | **off** (apagado después) | **403** (router flag-gated: corta antes que el alcance) | **403** | v1.4; T16b se mide en las rutas sin flag |
| sin alcance, mismo rol | on | 200 | 200 | control de la fila 8 |
| sin alcance, mismo rol | off | 403 (router flag-gated, comportamiento de hoy) | 403 | T18 |
| admin sin fila de alcance | on | 200 | 200 | T16 (control) |
| admin sin fila de alcance | off | 403 (el flag no lo salta el admin, #75) | 403 | existente (`test_inbound_orders`) |
| admin **con** fila de alcance (puesta por ORM) | on | 200 | **404**: fail-closed | T16c |
| admin con fila de alcance | off | 403 (router) | 403 | T16c, segunda mitad |

En las rutas que no tienen flag (`/purchases`, `/third-parties`, `/money-movements`, `/money-accounts`), «off» no cambia nada para el usuario sin alcance (T18). Para el usuario con alcance, el alcance **sigue** restringiendo ahí: eso es T16b (v1.4).

**Además:**

- **T1, familia (deny-by-default):** parametrizada sobre las **rutas montadas** (`app.routes`, no una lista a mano) que dependen de `get_required_org_context` y no están en la lista blanca. `ingrid_todo` → 403 **y el detalle empieza con «Fuera de tu alcance»** (N3: `require_org_flag` y los permisos también devuelven 403, y sin el prefijo un 403 que viene por otra puerta pasaría). **Conteo:** la cantidad de casos == rutas con contexto de org − largo de la lista, comparado **antes** del parametrizado (lección de #108). **Control positivo:** en las mismas rutas, `todo_libre` **no** recibe el 403 de alcance; sin eso, un 403 por cualquier otra puerta pasaría el test.
- **T1b y T1c:** las rutas sin contexto de org (§5.0).
- **T2** (M3): cada entrada de `SCOPED_ENDPOINTS` se identifica como `módulo.función` y resuelve a **≥ 1 ruta montada**. Se afirma el conjunto exacto de pares (método, path) de cada entrada, para que una función montada en dos paths no abra el segundo sin que se vea. Nada queda muerto.
- **T19:** la ausencia de lo de SAC (§5.7).
- **T2b, doble entrada:** `SCOPED_ENDPOINTS` == un set literal escrito en el test. Ampliar la lista obliga a venir a declararla donde se lee, como `TestClaveAditiva` (#112).
- **T14, permisos con control positivo** (memoria *test-de-permiso…*). Un rol con alcance y `purchases.view` pero **sin** `purchases.liquidate` → `GET /inbound-orders/{E_GL}` 200 (control) y `POST …/liquidate` 403 «Permisos insuficientes»: el alcance no da permisos. Lo mismo con `third_parties.view` sin `treasury.view_statements` (la lista de terceros da 200 y el estado de cuenta 403). Y el barrido por `grep` de los dos permisos de escritura del rol (`purchases.liquidate`, `treasury.create_movements`) sobre la lista blanca: cada uno con su par 200/403.
- **T15, la marca:**
  - válida → 200;
  - el recolector no es service_provider → 422;
  - el recolector es de otra org → 422;
  - el tercero se marca a sí mismo → 422;
  - en las dos puntas del nivel único → 422;
  - org sin flag → 422, y el par con flag → 200;
  - **regresión de (B):** editar las categorías del tercero no le toca `collector_id`.
- **T16, el alcance:**
  - un no-admin pone el alcance → 403;
  - alcance sobre un usuario admin → 422;
  - org sin flag → 422;
  - `my-permissions` con alcance y con `null`;
  - **T16b:** con el flag apagado después, el alcance **sigue** restringiendo en las rutas sin flag: `GET /third-parties/{B}` y `GET /purchases/{compra de B}` → 404, y `GET /third-parties/{A}` → 200 como control (v1.4: en `/inbound-orders` el router da 403 a todos y no mide el alcance);
  - **T16c:** una fila de alcance sobre un admin, puesta por ORM, **sigue** restringiendo (fail-closed).
  - **T16d** (N2): poner alcance a un superusuario → 422, y no se escribe ninguna fila.
- **T22, el listado de Tesorería con `view_all_movements`** (v1.4, pedido del Coordinador). `ingrid` con el rol de 13 permisos; Johana hace por API una transferencia K2→K1 (el fondeo) y un ajuste de tercero (`tp_adjustment_debit`, cuenta NULL) contra B y otro contra A. En `GET /money-movements`:
  - **aparece** el lado K1 del fondeo, que creó Johana (sin el permiso no aparecería: el `created_by` lo filtraría);
  - **no aparece** el ajuste de B ni el lado K2 del fondeo;
  - **aparece** el ajuste de A (cuenta NULL, tercero marcado);
  - control: `ingrid_libre` (mismo rol, sin alcance) ve el ajuste de B, así que su ausencia en `ingrid` la produce el alcance y no el escenario. Contra la vacuidad, antes de comparar se exige que la lista de `ingrid` no esté vacía.
- **T23, la fila 15b** (v1.5):
  - `ingrid` recibe en el flat **exactamente** las categorías activas de proveedor de material más «Empleados»;
  - **de punta a punta, la misma función:** cada id del flat que recibe sirve para crear un tercero con alcance (201), y un id que **no** está en su flat (por ejemplo «Genérico») da 422 al crear;
  - con `?behavior_type=customer`, `ingrid` recibe la lista vacía, y el control no;
  - control: `ingrid_libre` recibe ≥ 3 behaviors distintos.
- **T24, el conductor por nombre, fallando cerrado** (v1.5, condición del Coordinador):
  - con «Empleados» activa, aparece en el flat y sirve para crear;
  - renombrada por ORM a «EMPLEADOS» (otra caja), **sigue** apareciendo: `normalize_entity_name`;
  - renombrada a «Empleados SAC», **desaparece** del flat, crear con su id da 422, y **ninguna** otra generic toma su lugar;
  - desactivada, desaparece.
  - Contra la vacuidad: antes de renombrar se exige que aparezca.
- **T20** (N1): borrar físicamente por ORM al recolector cuando tiene un alcance o terceros marcados → `IntegrityError`. La fila de alcance y la marca siguen ahí.
- **T21, el script de la marca** (v1.3, §9). Archivo propio `tests/test_marcar_recolector.py`. Las funciones son puras (normalizar, verificar la org, armar el plan) y reciben los JSON con la forma real de las respuestas: los campos se copian de `OrganizationResponse` y `ThirdPartyResponse`, nunca más permisivos que el backend (memoria *fake-más-permisivo*). Casos:
  - **normalización**, con los nombres reales:
    - «ABRAHAM CABARCAS (GREENLOOP)» → cumple;
    - «DANIEL DE LA HOZ (GREENLOP)» → cumple;
    - «Bio Green Loop- Maquila» → cumple (espacios y guion);
    - «Maquila Greenloop» → cumple;
    - «GRÉENLOOP SAS» → cumple: **sin NFKD no cumple**, porque al borrar la «É» queda «grenloop»;
    - «ASOCIACION BIOGREEN RECYCLING» → no cumple;
    - «ECOGREEN» → no cumple;
    - «CARLOS CASTAÑO (GREENLOOP)» → cumple y la «Ñ» no rompe nada;
  - **exclusiones:** el recolector y «BIOGREENLOOP» salen con su motivo; sin «BIOGREENLOOP» en la lista → sorpresa (exit 3); con dos → sorpresa; el recolector fuera de la regla → sorpresa;
  - **inactivo** → saltado con su motivo, sin sorpresa;
  - **idempotencia:** ya marcado con el mismo → saltado; marcado con otro → sorpresa, y la lista «a marcar» no lo trae;
  - **org:** sin `kg_ledger_enabled` → aborta (exit 2); recolector que no es service_provider → aborta;
  - **`--esperado`:** distinto → sorpresa, sin escrituras;
  - **con sorpresa y `--apply` no se escribe nada:** el cliente HTTP es un doble que cuenta las llamadas, y se afirma 0 `PATCH`.
  - **Ensayo a archivo contra mi backend de dev** (`:8012`, la SAC activa de mi copia): dry-run → 124 a marcar y exit 0; `--apply --esperado 124` → 124 `PATCH`; re-correr → 0 a marcar, 124 «ya marcado» y exit 0; un tercero re-marcado por ORM con el recolector X → exit 3 y 0 escrituras. Las 4 corridas van con su comando y su `EXIT` en el log (`ensayo_marcar_recolector.log`). (v1.5: suma una quinta, `--apply --esperado 123` → exit 3 y 0 escrituras.)
- **T17, el balance:** en el detallado vivo y as-of, A y A2 van en el grupo «Recolector: GL» dentro de CxP y de anticipos, con totales iguales a los de antes de marcar. Contra la vacuidad: se exige `total != 0` y `grupos ≥ 2` **antes** de comparar (#110). Y en una org sin marcas, el response es igual campo por campo al de sin código, con cero claves nuevas.
- **T25, las Entradas preexistentes** (v1.6, R1 medido en producción). Nacen igual que allá: por la API de siempre y con Johana, que no tiene alcance.
  - E_GL revisada y una Entrada GL liquidada por Johana con A y B (B sin la marca) y la comisión editada a mano (777): Ingrid ve **las dos** en el listado, con su estado, y el detalle de las dos da 200.
  - La compra de A está en su listado y abre; la de B no está y da 404. Control: Johana abre la de B.
  - Re-liquidar la liquidada → rechazo por estado, y la comisión sigue en 777, sin recalcular.
- **T25b, regla 9f** (v1.6). Johana liquida una Entrada GL con A y con retención, y la des-liquida. Ingrid re-liquida con el mismo reparto → 422 con el mensaje de 9f, y **las 7 tablas sin cambios**. Lo mismo con IVA de compra en vez de retención: es un caso propio, porque cada mitad de la regla tiene su plantado. Control positivo: una Entrada des-liquidada sin retenciones ni IVA, toda de A → Ingrid 200. Sin ese control, una regla que bloqueara toda des-liquidada pasaría el test. Segundo control: Johana re-liquida la de la retención → 200.
  - **Controles de c1 (v1.7), uno con retención y otro con IVA:** L1 con retención (o IVA) → des-liquidar → Johana re-liquida **sin** retención (L2) → des-liquidar → Ingrid re-liquida → **200**. Contra la vacuidad, antes del último paso se afirma que el lote de L1 sigue en la base, revertido. Si no estuviera, el control no mediría nada.
- **T25d, la precarga usa la misma función** (v1.7). Mismo escenario L1/L2 → el detalle de la Entrada (`GET /inbound-orders/{id}`, leído como Johana) trae `retentions == []` y `taxes == []` en esa compra. Y una liquidación con **dos** retenciones (ReteFuente e ICA), des-liquidada → el detalle trae las **dos**. Este segundo caso mide la sospecha de `reverted_at` por fila: se corre una vez contra el código viejo, con el resultado a archivo, antes de afirmar en el informe si el defecto existía.
- **T25c, regla 9e** (v1.6). Johana liquida una Entrada GL con A en la compra 1 y B en la compra 2, y la des-liquida. Ingrid manda la compra 2 con A: el reparto es todo suyo, así que solo 9e la puede rechazar → 422 con el mensaje de 9e, y la compra de B sigue `registered`. Control: Johana manda el mismo cuerpo → 200, y la compra de B queda cancelada (R6). El control prueba que el escenario sí cancela la compra ajena, o sea que el 422 es lo que la protege. Segundo control: Johana des-liquida otra vez; ahora la compra de B está **cancelada** en el puente y todas las vivas son de A → Ingrid re-liquida → 200. Sin él, una regla que contara las canceladas bloquearía para siempre una Entrada que SAC ya corrigió (P48).
- **T25e, el aviso de D-E2(b)** (v1.8). Se lee de la **respuesta HTTP** del `POST …/liquidate`, no del retorno del servicio (#100 D4d). Johana liquida:
  - E_GL con A y B, con B en **dos** compras (Q-65, n9) → `warnings` trae **un** aviso, que nombra a B, a Green Loop y a Ingrid y dice «Terceros → Recolector»;
  - **c3 (v1.9):** E_GL con A y C (marca de X) → un aviso que nombra a C;
  - **control positivo**, otra Entrada GL toda de A → `warnings` no trae ningún aviso de marca;
  - E_X (recolector X, sin usuario con alcance) con B → sin aviso. Es la condición «solo si alguien lo pierde».
  - Contra la vacuidad, en el caso 1 se exige que la compra de B exista y que Ingrid reciba 404 al abrirla: el aviso dice la verdad.
  - **n12 (v1.10):** con los dos usuarios de alcance GL (ingrid e ingrid_todo) puestos **inactivos**, Johana liquida E_GL con B → sin aviso. El control positivo es el caso 1, con los mismos usuarios activos.
- **T26, regla 9g** (v1.10). Todo por HTTP, sobre una E_GL revisada con un material pesado (100):
  - Ingrid reparte 60 a A, con precio de referencia → 422 con el mensaje de 9g, que nombra el material y dice «esta Entrada la liquida SAC». Las 7 tablas quedan sin cambios.
  - Lo mismo **sin** precio de referencia → 422 de 9g, no el de D16. Esto mide el orden de las reglas.
  - Ingrid reparte 110 → 422 de 9g («de más»).
  - Ingrid marca el material «sin proveedor», sin asignaciones → 422 de 9g («sin proveedor»).
  - **n14 (v1.11):** una E_GL con **dos** materiales (100 y 50), con 60 y 70 repartidos → **un** 422 que nombra a los dos («faltan 40» y «20 de más»).
  - **Control positivo:** Ingrid reparte 100 → 200, con **cero** ajustes de descuadre de la Entrada.
  - **Par sin alcance:** Johana manda el mismo cuerpo de 60 → 200 y nace el ajuste de descuadre, como hoy.
- **T18, no-regresión de la otra org:** una org sin flag y sin alcances; un usuario restringido por cuentas sigue viendo lo que ve hoy en las 4 lecturas, salvo lo que decida Daniel en §6.

**Dirigidas.** Son la única red de develop hasta el checkpoint. El comando queda fijo aquí, se re-corre igual en la entrega y se escribe en el log. Eco QA 2 corre esa misma lista.

```bash
cd /Users/daniel.chain/Projects/reciclaje-erp-wt/coder-2/backend
grep -lE '/api/v1/(third-parties|purchases|inbound-orders|money-movements|money-accounts|attachments|roles|organizations)|/api/v1/reports/balance-detailed|collector_id|account_assignments|UserAccountAssignment' tests/*.py | sort > $EV/dirigidas.txt
printf '%s\n' tests/test_reloj_de_negocio.py tests/test_advisory_locks.py tests/test_crucible_charges.py tests/test_sac_recolector_alcance.py tests/test_marcar_recolector.py >> $EV/dirigidas.txt
sort -u -o $EV/dirigidas.txt $EV/dirigidas.txt
TEST_DATABASE_URL=postgresql://admin:test_password@localhost:5433/reciclaje_test_coder_2 \
  lockf -k ~/.cache/ecobalance/tests.lock ./venv/bin/pytest $(cat $EV/dirigidas.txt) -q -p no:cacheprovider > $EV/dirigidas.log 2>&1; echo "EXIT=$?" >> $EV/dirigidas.log
```

`$EV` = `~/sac-evidencia/<fecha>/coder-2-recolector-alcance`.

- Medido hoy sobre la base `de32530`: el grep da **59 de 95** archivos de `tests/` (`dirigidas_grep_plan.txt`). Ya incluye `test_reloj_de_negocio.py` y `test_crucible_charges.py`; el `printf` agrega la guarda de locks y el archivo nuevo.
- Se esperan muchos archivos: el cambio de `deps.py` pasa por toda ruta de org, y los nueve prefijos son los que se tocan.
- La predicción del conteo se escribe en el log **antes** de correr: `--collect-only -q` sobre la misma lista.
- La suite completa queda diferida al checkpoint («suite diferida al checkpoint»).

## 13. Matriz de plantado

Se commitea **antes** de plantar. Las filas que tocan una vía compartida (marcadas «vía») predicen «al menos estos».

| P | Defecto plantado | Debe caer |
|---|---|---|
| P1 | se quita la lista blanca en `deps.py` | T1 (todas sus filas) — vía |
| P2 | se agrega `GET /purchases/pending` a la lista sin filtro | T2b |
| P3 | el listado de Entradas no fuerza el recolector | fila 7 (incluido el `?collector_id=X`) |
| P4 | el detalle de Entrada sin el 404 | fila 8 |
| P5 | liquidar sin validar el proveedor en alcance | fila 9 B y C |
| P6 | liquidar sin validar la cuenta de contado | fila 9 K2 |
| P7 | `/third-parties/suppliers` sin el filtro (los otros 3 con él) | fila 11 (prueba que la familia está parametrizada) |
| P8 | `POST /third-parties` usa el `collector_id` del payload | fila 15 |
| P9 | el listado de compras sin el filtro | fila 16 |
| P10 | el estado de cuenta en alcance filtra por cuentas (como hoy) | fila 20 (corrido ≠ vivo) |
| P11 | con alcance, lista vacía de cuentas = todas | fila 21 |
| P12 | el listado de movimientos deja pasar `account IS NULL` de cualquier tercero | fila 24 |
| P13 | la marca se valida sin mirar el flag | T15 sin flag |
| P14 | el balance agrupa por categoría, ignorando `collector_id` | T17 |
| P15 | el alcance se impone solo con el flag encendido | T16b |
| P16 | `is_admin` sale antes del chequeo de alcance | T16c |
| P17 | descarga de adjuntos sin el chequeo | fila 19 |
| P18 | `annul` acepta una causación (cuenta NULL) | fila 28 |
| P19 | la búsqueda de Entradas se aplica en OR con el filtro de recolector (precedencia) | §5.4: `search` B → 0 |
| P20 | se agrega `GET /money-movements/by-number/{n}` a la lista | T2b y T1 |
| P21 | el listado de compras calcula `amount_sum` antes del filtro | §5.4: suma == filas |
| P22 | el alta de tercero con alcance acepta `initial_balance` | fila 15 (422 y ninguna fila escrita) |
| P23 | el alta de tercero con alcance acepta cualquier categoría | fila 15 (investor y customer) |
| P24 | `annul` sin la condición `transfer_pair_id IS NULL` (plantado **solo** en annul) | fila 28: transferencia de Johana, con el par en K2 todavía `confirmed`. **No debe caer** la fila 30: si cae, el predicado está compartido y P25 no se distingue de P24 |
| P25 | subir evidencia sin el filtro de PROPIOS (plantado **solo** en evidencia) | fila 30, el pago de Johana K1→B. **No debe caer** la fila 28 |
| P26 | `/materials` con alcance devuelve stock y costo | T19, materiales |
| P27 | `/price-lists/current` con alcance acepta la ausencia de `third_party_id`, o devuelve `sale_price` | T19, precios, y fila 6 |
| P28 | `/service-tariffs/current` sin el filtro | T19, tarifas |
| P29 | `GET …/members` sin el `deny_if_collector_scoped` | T1c |
| P30 | una ruta nueva sin contexto de org (se monta una de prueba en el plantado) | T1b |
| P31 | con alcance, se respeta el `amount` digitado de la comisión (D-a = a) | fila 9, comisión |
| P32 | `PUT …/collector-scope` acepta a un superusuario | T16d |
| P33 | `ondelete="CASCADE"` en `user_collector_scopes.collector_id` (en modelo y migración) | T20 |
| P34 | la normalización no borra lo que no es letra (espacios, guiones, paréntesis) | T21: «Bio Green Loop- Maquila» |
| P35 | la normalización sin NFKD | T21: «GRÉENLOOP SAS», que es el control que discrimina. «CARLOS CASTAÑO (GREENLOOP)» es un chequeo de cordura (n5): cumple con o sin NFKD, así que no distingue nada; si cayera, la Ñ rompería la regla por otro motivo |
| P36 | si la exclusión de «BIOGREENLOOP» no aparece, se sigue en silencio | T21: exclusión ausente → exit 3 |
| P37 | un tercero marcado con otro recolector se pisa | T21: marcado con otro |
| P38 | la org se valida sin mirar `kg_ledger_enabled` | T21: org sin flag |
| P39 | con sorpresa, `--apply` escribe lo que no es sorpresa | T21: 0 `PATCH` con sorpresa |
| P40 | con alcance, el listado de movimientos sigue filtrando por `created_by` aunque el rol tenga `view_all_movements` (v1.4) | T22: el fondeo de Johana no aparece |

| P41 | la fila 15b sin el filtro forzado: el flat con alcance devuelve todas las categorías (v1.5) | T23 |
| P42 | `scoped_create_categories` reconoce al conductor por `behavior_type = generic`, sin mirar el nombre | T24 («Empleados SAC» renombrada sigue apareciendo) y T23 («Genérico» aparece) — vía |
| P43 | la fila 15 valida con su propia lista de behaviors (`material_supplier`, `generic`) en vez de llamar a la función (plantado **solo** en la validación) | T23 y T24: crear con «Genérico» da 201. **No debe caer** la parte del flat de T23: si cae, la validación y el flat no están separados y P43 no se distingue de P42 |
| P44 | el nombre se compara con `==` sin `normalize_entity_name` | T24: «EMPLEADOS» desaparece |
| P45 | sin la regla 9f (v1.6) | T25b, los dos casos (retención e IVA) |
| P46 | la regla 9f mira solo las retenciones, no el IVA (plantado **solo** en el IVA) | T25b, el caso del IVA. **No debe caer** el de la retención |
| P47 | sin la regla 9e (v1.6) | T25c: la compra de B queda cancelada |
| P48 | la regla 9e cuenta también las compras canceladas del puente | T25c, el segundo control: con la compra de B ya cancelada, Ingrid recibe 422 en vez de 200 |
| P49 | la 9f usa «el último lote que exista» (el criterio de los helpers viejos) en vez del de la última liquidación (v1.7) | T25b, los dos controles de c1 (retención e IVA): Ingrid recibe 422 en vez de 200. **T25d no cae** (n7): la precarga sigue con la función nueva |
| P50 | la precarga vuelve a su helper propio y la regla sigue con `last_liquidation_batch` (plantado **solo** en la precarga) | T25d, el escenario L1/L2. **No deben caer** T25b ni sus controles: si caen, la regla y la precarga no están separadas en el plantado y P50 no se distingue de P49 |
| P51 | sin el aviso de D-E2(b) (v1.8) | T25e, caso 1 |
| P52 | el aviso no mira si el recolector tiene un usuario con alcance | T25e, caso E_X. **No debe caer** el caso 1 |
| P53 | el aviso solo mira `collector_id IS NULL`: no avisa por un proveedor con la marca de otro recolector (v1.9, c3) | T25e, el caso de C. **No debe caer** el caso 1 |
| P54 | el aviso no filtra `User.is_active` (n12) | T25e, el caso de los inactivos. **No debe caer** el caso 1 |
| P55 | sin la regla 9g (el endpoint no enciende `require_full_allocation`) | T26: los cuatro casos de 422. **No debe caer** el par de Johana |
| P56 | 9g encendida para todos (`require_full_allocation` por defecto True) — vía | T26, el par de Johana, y al menos los tests de descuadre de `test_sac_entrada_sin_proveedor.py` |
| P57 | 9g evaluada **después** de D16 | T26, el caso sin precio de referencia (sale el mensaje de D16). **No deben caer** los otros casos de 422 |
| P58 | 9g solo mira `disc > 0` (c4, v1.11) | T26 `[110]` y el de dos materiales (COBRE-AL sobra). **No deben caer** `[60_con_precio]`, `[60_sin_precio]`, `[sin_proveedor]` ni el control |
| P59 | 9g levanta en el **primer** material, sin juntar (n14, v1.11) | T26, el caso de dos materiales. **No deben caer** los cuatro `[…]` de un material |
| — | **v1.11:** los cuatro rechazos de T26 son un test parametrizado (`test_t26_9g_rechazo_no_escribe_nada[…]`), uno por caso, para que P55–P58 digan cuál cae. Releídas así: P55 tumba los cuatro y el de dos materiales; P57 tumba solo `[60_sin_precio]` | |

**Dirección peligrosa a buscar celda por celda antes de plantar:** un test que debía caer y no cae. El candidato más probable es P7 si los cuatro listados comparten helper. Por eso el test se parametriza por ruta y el defecto se planta en una sola.

## 14. Riesgos y fuera de alcance

- **R1 — CONDICIÓN DE USO, no solo riesgo** (Coordinador, revisión de producto): sin recolector en la Entrada, Ingrid no ve nada. **Medido en producción (v1.6):** 25 de 149 Entradas de SAC tienen recolector, las 25 Green Loop (18 revisadas, 7 liquidadas); el «0 de 34» de la v1.1 era de Entradas de prueba (§2.7). Las reglas que tocan Entradas ya existentes están en la fila 9 (9e, 9f) y en T25. **Báscula tiene que poner el recolector en cada Entrada de Green Loop**, y **Daniel se lo comunica a Johana** antes de que Ingrid entre. Johana lo puede corregir mientras la Entrada no esté liquidada (#83/#93). El aviso «¿Recolector?» en la captura queda fuera de este ciclo y es el **primer candidato a v2**.
- **R2 — una consulta más por request** para todo miembro de las 7 orgs (índice único `(org, user)`). Se mide en la construcción con `EXPLAIN ANALYZE` sobre la copia.
- **R3 — el selector de Johana no cambia (S1).** Si en la pantalla Daniel quiere que también a ella, en una Entrada con recolector GL, se le ofrezcan primero los de GL, es un orden visual y va como sugerencia.
- **Fuera de alcance:**
  - gastos de la caja de Green Loop (S7);
  - líneas propias en el Balance General (decisión 2);
  - el aviso de recolector en la captura;
  - un alcance de Ingrid sobre las Willard (Q-02: Green Loop también recolecta postconsumo; con S4 ella no confirma Willard, pero las ve en el listado si tienen su recolector, y su detalle muestra kg).

## 15. Decisiones de Daniel

Las pide el Coordinador; me las pasa él. Se anotan con su fuente: un mensaje de QA no es una decisión de Daniel.

**Decididas (20-nov, vía el Coordinador):**

1. **El hueco de cuentas de §6 para las orgs sin alcance (Costa):** CICLO PROPIO, justo después. Este ciclo no le cambia nada a Costa (T18).
2. **Balance General:** solo el Detallado agrupa a Green Loop, sin claves nuevas en el General (§7).
4. **Marca inicial — cambiada por Daniel antes de construir (v1.3):** «todo lo que diga green loop es green loop». Se marca por la regla del nombre normalizado de §9, con dos exclusiones: el recolector y «BIOGREENLOOP». No se le manda lista a Johana; el xlsx de la v1.2 queda como evidencia y no sale a ningún lado. *(La versión anterior, «a Johana se le proponen los 124 con sufijo y ella confirma», queda sin efecto.)*

3. **Supuestos S1–S8 y las cuatro decisiones abiertas: Daniel aceptó todas las recomendadas** (20-nov, vía el Coordinador):
   - S1–S8 tal como están; los gastos desde la caja de Ingrid quedan fuera (S7);
   - **D-E2** (§5.6): ~~(a), se declara la fuga~~ — **queda sin efecto**. **(b), aviso al liquidar** (Daniel, 20-nov ~14:25, por ventanita, vía el Coordinador; v1.8);
   - **H5**: (a), `payment-to-generic` entra al alcance con las reglas de la fila 27b;
   - **D-a**: (a), el servidor fija el monto de la comisión;
   - **D-b**: (a), las compras son de Ingrid por la marca del proveedor.

   El cuerpo del plan ya se leía con estas opciones desde la v1.1, así que ninguna fila cambia. Las marcas «pendiente de Daniel» y «solo si Daniel elige (a)» de S2, S6, S7, §5.1, la fila 27b y el cuadrante se limpiaron en la v1.3.

5. **9g — sin descuadre con alcance** (Daniel, O1 de QA 2, «Que no deje descuadre», por ventanita, 20-nov ~15:05, vía el Coordinador; v1.10). Con alcance, una Entrada se liquida solo si todo lo pesado queda repartido. Si no, la liquida SAC (fila 9, 9g).

## 16. Runbook de deploy

Revisión de producto del Coordinador. Todo lo hace el Coordinador con el OK de Daniel, porque son escrituras en producción.

1. **Migración** `e7f9a1b3c5d8`, vía `/deploy` (aditiva: columna NULL y tabla vacía).
2. **Marca inicial (v1.3):**
   - **Antes:** se leen en producción el id de la org SAC activa y el del tercero «Green Loop», que tiene que ser service_provider y estar activo. Los dos ids van escritos en el log, nunca resueltos por nombre dentro del script.
   - **Predicción:** se escribe en el log cuántos se espera marcar. En la copia de dev son 124; en producción se cuentan antes con una lectura que aplique la misma regla.
   - **Dry-run:** `scripts/marcar_recolector.py --api-url <prod> --org-id <id> --collector-id <id> --esperado <N>`. Se revisan los marcados y los excluidos con su motivo, y se verifica que «ADALBERTO AVILA (GREENLOOP)» está en «a marcar» (n4, v1.4). Exit ≠ 0 detiene todo y decide Daniel.
   - **Corrida real:** la misma línea con `--apply`, con el OK de Daniel.
   - **Re-corrida:** tiene que dar 0 a marcar y exit 0.
3. **El usuario de Ingrid:**
   - se crea por la vía de superusuario;
   - **su clave se fija solo con el reseteo de #85** (`POST /system/users/{id}/reset-password`), con la clave que defina Daniel, **NUNCA con la clave fija** que dejan las altas de miembros (la deuda de #85);
   - su rol es «Recolector», con los 13 permisos de §5.1 (v1.4); `payment-to-generic` (H5 = a) usa el mismo `treasury.create_movements`. Ningún permiso es nuevo.
4. **Su caja:** `PUT /organizations/{org}/members/{ingrid}/account-assignments` con la cuenta real de la caja de Green Loop (K1 de producción). **Antes** de poner el alcance, para que en ningún momento vea cuentas que no son suyas. Igual, con alcance y sin asignaciones vería cero (fila 21).
5. **Su alcance:** `PUT /organizations/{org}/members/{ingrid}/collector-scope` con el id del tercero «Green Loop».
   - **Antes (v1.5), una lectura:** que exista la categoría de terceros «Empleados», activa y generic, en la SAC activa. Si no existe, Ingrid solo puede crear proveedores (falla cerrado), y Daniel decide si se crea.
6. **Verificación**, con lecturas en producción y su usuario:
   - `my-permissions` trae `collector_scope`;
   - `GET /inbound-orders` da solo Entradas con recolector Green Loop: el 20-nov eran 25 (18 revisadas y 7 liquidadas, v1.6). Se compara contra una lectura de Johana con el filtro `collector_id`, hecha en el mismo momento;
   - `GET /third-parties/suppliers` da solo los marcados;
   - `GET /money-accounts` da solo su caja;
   - `GET /third-party-categories/flat` da solo las de proveedor de material y «Empleados» (v1.5);
   - `GET /organizations/{org}/members` da 403.
7. **Condición de uso (R1):** Daniel le comunica a Johana que báscula tiene que poner el recolector en las Entradas de Green Loop.
