# Plan — Multi-proveedor por línea en la Entrada (SAC)

**Versión:** v1.2 — incorpora el micro-QA (🟢 GO condicionado)
**Origen:** reunión SAC 2026-08-03 (00:58:40–01:03:00) + respuestas de Daniel 2026-08-04.

> **Enmienda v1.1 (durante la revisión de QA).** A pedido de Daniel —*"hay que ser cuidadoso que esto
> afecte solo a SAC"*— **D2 cambia**: el vínculo entrada↔compras deja de ser una columna nueva en
> `purchases` (tabla compartida) y pasa a una **tabla puente exclusiva de SAC**. La migración pasa a
> tocar **cero tablas compartidas**. Cambian D2, D3, §4, §5, §6, §7 y aparece D11.
>
> **v1.2 — respuesta al micro-QA (🟢 GO condicionado).** QA revisó la v1.0; esta versión cierra sus
> cuatro condiciones:
> - **H1 adoptado íntegro**: C1 y C3 son la misma pregunta y **#80** —desplegada— la contesta. El
>   argumento de C1 se reescribió sobre ese suelo y la pregunta a Johana se reformuló en los términos
>   de QA. Su lectura era mejor que la mía y así queda escrita.
> - **C2 ampliado**: el error del canon está en **dos** lugares (§7.3 punto 5 y la tabla de actores),
>   no solo en uno. La v0.6 corrige ambos.
> - **Encuadre corregido**: SAC **ya es producción**. El backfill toca datos productivos reales —
>   los de SAC. Van las 3 condiciones de QA al runbook (§7.1).
> - **H2**: el conteo de organizaciones se confirma; el del catálogo de movimientos se **refuta con
>   evidencia** (§4).
>
> ⚠️ QA aprobó la **D2 de la v1.0** (columna en `purchases`). La v1.1 la reemplazó por la tabla
> puente, que es **estrictamente más conservadora** — pero conviene que QA lo vea, no que lo asuma.
**Implementa:** v0.5 §7.3 (recolecciones en ruta), §11.1.12 (InboundOrder), §12 (endpoints).
**Análisis previo:** [analisis-sac-multiproveedor-por-linea.md](analisis-sac-multiproveedor-por-linea.md)
**Decisión CLAUDE.md que le corresponderá:** **#89** (el #88 lo tomó el ciclo de venta de activos
fijos del otro agente, commit `158e8a0`, mientras este plan estaba en QA).

---

## 1. Qué se construye

Una Entrada deja de tener **un** proveedor en la cabecera y pasa a tener **un proveedor por línea de
material**. De una sola Entrada derivan **N compras**, una por proveedor, cada una con su remisión,
su liquidación, sus retenciones y su saldo, exactamente como funcionan hoy las compras de un solo
proveedor.

No es un caso especial de Green Loop: **cualquier recolector o camión** puede traer material de
varios proveedores (respuesta 1 de Daniel, 2026-08-04). El diseño no nombra a Green Loop en ninguna
parte.

### Respuestas que fijan el diseño

| # | Pregunta | Respuesta | Consecuencia |
|---|---|---|---|
| 1 | ¿De dónde salen los kilos de cada proveedor? | El recolector trae su documento con la relación, pero **"lo que recibe SAC es lo que cuenta"** | **No hay reparto de diferencias.** El peso de la línea es el que mide SAC; la relación del recolector es referencia, no fuente de verdad. Se cae el sub-problema más caro que anticipábamos. |
| 2 | ¿La comisión del recolector es una o N? | **Por proveedor** | Cae sola: la comisión ya se causa dentro de `purchase.liquidate()` (#83). Con N compras salen N causaciones sin tocar esa lógica. |
| 3 | ¿Liquidación parcial? | **Sí, gradual** | El estado de la Entrada deja de ser binario → nace `partially_liquidated`. Es el cambio de mayor superficie. |
| 4 | ¿Remisión por proveedor? | **Una por proveedor** | La remisión vive en cada compra derivada — donde `invoice_number` ya vive hoy para el tipo compra (#87 A). La estructura ya lo soporta; cambia la captura. |
| 5 | ¿Puede la misma persona registrar y revisar? | **Sí** | Pertenece al ciclo de "revisada". Se anota: el visto bueno es punto de control, no segregación de funciones. |

### Fuera de alcance

- El camino **Willard** completo (§7.3 primera mitad, §4.3, §6.4): libro de kg, fórmulas,
  confirmación en dos pasos (#81), sede determinista y titular fijo (#80). Ver conflicto C3.
- El estado **"revisada"** — ciclo propio, bloqueado por usuarios faltantes.
- Liquidación **en bloque** de las N compras. La reunión pidió capturar rápido, no liquidar rápido:
  Ingrid sigue liquidando de a una. Si al usarlo lo piden, es ciclo propio.
- El consecutivo de arranque configurable — pospuesto a la puesta en marcha.

---

## 2. Conflictos con los documentos canónicos — declarados

La regla del proyecto es que un plan que contradice el canon sin declararlo es hallazgo BLOQUEANTE.
Hay tres, y el primero es de fondo.

### C1 — 🔴 v0.5 §7.3 exige EXACTAMENTE LO CONTRARIO de este plan

El canon dice, textual:

> *"Cuando un camión recoge material de N proveedores en una ruta (patrón habitual de Green Loop), el
> modelo antiguo era generar UNA sola entrada global. **Se corrige en v0.4** según Hugo: 'Tendrá que
> ser que nosotros en la entrada no hagamos una sola, sino que hagamos cada entrada por cada
> proveedor' y **Johana**: 'la idea seria que hagan una entrada por proveedor y no una global'."*

O sea: en junio, Hugo **y Johana** pidieron explícitamente una entrada por proveedor, y el documento
lo registra como una **corrección deliberada** del modelo anterior. Este plan revierte esa corrección.

**La resolución no es "gana el más reciente".** El canon da dos razones concretas para la regla, y
este plan **conserva las dos**:

| Razón de §7.3 | ¿Sobrevive? |
|---|---|
| *"permite liquidar precios individualmente por proveedor según lo negociado"* | **Sí, intacta.** Cada proveedor sigue teniendo su propia `Purchase`, liquidada por separado y en el momento que quiera Ingrid — la respuesta 3 lo refuerza. |
| *"mantener trazabilidad de origen para el saldo Willard por centro de distribución"* | **Sí, intacta.** El proveedor baja al nivel de línea, que es una granularidad **mayor**, no menor. Nada se agrega ni se mezcla. |

Lo único que cambia es **cuántos documentos de captura** hay que digitar para una misma realidad
física: hoy 15, después 1. Y ese punto es justo el que Johana levantó el 3 de agosto, ya viendo el
formulario real:

> **Johana:** *"ellos tienen un montón de compras en una sola entrada… cuando ellos hacen una ruta le
> van recogiendo varios proveedores y cuando llegan acá y se les descarga, se les hace una sola
> entrada."* … *"Ajá. Es que ahí es donde está el tema."*

En junio la discusión fue sobre el **modelo contable** (no mezclar proveedores) y la respuesta correcta
fue separarlos. En agosto la discusión es sobre la **ergonomía de captura** de un hecho físico único.
Son dos preguntas distintas con la misma respuesta aparente.

**Acción requerida:** actualizar `requerimientos-funcionales.md` §7.3 a v0.6 registrando el cambio y
su fecha. **No se codifica hasta que el canon esté corregido** — es la regla del proyecto, y dejar el
doc diciendo lo contrario del código es exactamente lo que produce el próximo malentendido.

### C2 — el canon dice la comisión mal, y en DOS lugares

El canon dice que la comisión de Green Loop *"se prorratea al costo del material vía
`PurchaseCommission` ([decisión #30])"*. **Eso ya no es cierto**: la decisión **#83** (Ciclo D,
desplegada) la cambió a **gasto causado** (`expense_accrual`), por decisión de producto explícita de
Daniel.

QA localizó el error repetido en dos lugares (§7.3 punto 5 y la tabla de actores). **Al barrer el
documento aparecieron ocho**: §2.4 tabla de actores, §7.3 punto 5, §8 excepción Green Loop —el
enunciado más detallado y más equivocado, decía explícitamente *"NO va a P&L como gasto separado"*—,
la tabla de categorías de gasto —que afirmaba lo contrario de lo que #83 hace: que Green Loop **no**
usa categoría—, la tabla de entidades reutilizadas, la de decisiones aplicables, Q-viva.3 y el log de
preguntas. Más el resumen de la v0.5 en la cabecera.

✅ **CERRADO — los ocho corregidos en v0.6**, junto con `inbound_orders.third_party_id` en §11.1.12,
que pasa a nullable por D1.

No afecta a este plan —la comisión se causa dentro de `purchase.liquidate()` y con N compras salen N
causaciones sin tocar nada— pero se declara para que se corrija en la misma pasada que C1.

### C3 — "Green Loop = postconsumo" (§7.3) vs *"los de ellos siempre es regular"* (3-ago)

**Reescrito en v1.2 adoptando H1 de QA.** El argumento de v1.1 era una intuición; el suelo firme es
otro y ya está en el código.

§7.3 describe a Green Loop bajo el título **"Recolecciones postconsumo"** y —dato que la v1.1 no
citaba y que juega **en contra** de la reconciliación— la línea 1248 dice: *"una ruta = N
`InboundOrder`, uno por proveedor visitado, cada uno con su pesaje, **su factor Willard si aplica**, y
su `ThirdParty` proveedor específico"*. Es evidencia textual de que el modelo de junio **sí**
contemplaba rutas multi-proveedor cargando material Willard: justo lo que D9 bloquearía.

**Lo que la salva no es la intuición de "dos flujos distintos", sino la decisión #80, desplegada:** el
tercero de una entrada Willard **se deriva del titular de la cuenta de kg**, amarrado por CHECK en la
base de datos, con defensa 422 en el backend y el campo deshabilitado en el frontend. Una entrada
Willard con dos proveedores **no es un caso que este plan decida prohibir: es imposible por
construcción desde #80**. El *"factor Willard si aplica"* de la línea 1248 es legado anterior a esa
decisión, igual que C2.

Sobre ese suelo, D9 no inventa una restricción — **hace explícita una invariante que ya existe**.

**Y esto reencuadra la pregunta** (condición 1 del GO). No es "¿las rutas son regulares?" sino:

> **¿Alguna ruta trae material Willard de más de un proveedor?**

Porque si la respuesta hubiera sido **sí**, el conflicto no sería con este plan sino con **#80, que ya
está en producción** — un incidente de diseño sobre una decisión desplegada, con su propio alcance.

✅ **CERRADO — Daniel, 2026-08-04: "Willard es un solo proveedor (Willard)".** La reconciliación se
confirma, D9 queda validado y no hay incidente sobre #80. Condición 1 del GO cumplida.

### C1 — el argumento fuerte (reescrito en v1.2)

C1 y C3 no son dos conflictos: son la misma pregunta, y #80 la contesta.

La v1.1 defendía la segunda razón de §7.3 diciendo que sobrevive *"porque el proveedor baja a la
línea, granularidad mayor"*. Es cierto pero débil. El argumento fuerte es que esa razón está escrita
en el canon como **"trazabilidad de origen para el saldo Willard por centro de distribución"** —
explícitamente Willard— y **D9 conserva el modelo de junio literalmente intacto justo ahí**.

O sea: la regla de junio **no se revierte donde vive su razón**. Se relaja únicamente en compra
regular de chatarra, donde esa razón no aplica y donde la única consecuencia es cuántos formularios
digita Ingrid. Esa formulación es la que debe quedar en el §7.3 de la v0.6.

---

## 3. Decisiones de diseño

### D1 — La línea es la fuente de verdad del proveedor; la cabecera queda como conveniencia

`inbound_order_lines.third_party_id` **NOT NULL**: toda línea sabe su proveedor, siempre, también en
las entradas de un solo proveedor. Sin ramas ni *fallbacks* en lectura.

`inbound_orders.third_party_id` pasa a **nullable** y cambia de significado: guarda el proveedor
**solo cuando todas las líneas comparten uno**; con varios queda NULL. Se calcula al escribir y nunca
se lee para derivar efectos — es campo de presentación y de búsqueda.

**Por qué así y no al revés** (cabecera con *fallback* en la línea): un *fallback* obliga a que cada
uno de los ~19 puntos que hoy leen el proveedor decida "línea o cabecera", y basta olvidar uno para
que una compra derive al proveedor equivocado. Escribir el valor resuelto en la línea mata la clase
de bug entera. El precio es un `UPDATE` de backfill, barato hoy (§7).

El botón *"todas estas líneas van al mismo proveedor"* prometido en la reunión sale gratis: el
frontend copia el proveedor elegido a cada línea antes de enviar.

### D2 — Tabla puente `inbound_order_purchases` (enmienda v1.1)

Hoy el vínculo vive en `inbound_orders.purchase_id`, FK único hacia UNA compra; `purchases` no tiene
columna de vuelta (el enrich B1 de #80 resuelve el sentido inverso con una consulta por página).

Una entrada con N compras exige el sentido contrario. Hay dos formas y **la elección la decide el
alcance del daño posible, no la elegancia**:

| Opción | Vínculo | Tablas compartidas tocadas |
|---|---|---|
| A (v1.0, descartada) | `purchases.inbound_order_id` | **`purchases`** — la tabla con más filas del sistema en las 3 organizaciones cliente |
| **B (elegida)** | tabla puente `inbound_order_purchases` | **ninguna** |

Se elige **B**:

```
inbound_order_purchases
  inbound_order_id  FK → inbound_orders   ondelete=CASCADE
  purchase_id       FK → purchases        ondelete=CASCADE, UNIQUE
  organization_id, created_at             (OrganizationMixin + TimestampMixin)
  PK (inbound_order_id, purchase_id)
```

`UNIQUE` en `purchase_id` es la invariante dura: **una compra pertenece a lo sumo a una entrada**.
La tabla es la **única fuente de verdad** del vínculo; `inbound_orders.purchase_id` queda **inerte**
(regla sin-DROP del repo, igual que `goes_directly_to_jm` en #80 B4), con comentario de columna
diciéndolo. Nadie la lee tras este ciclo — no hay doble escritura, que es lo que produce deriva.

**Por qué B pese a costar un join:** la opción A era segura *por argumento* (`ADD COLUMN` nullable es
metadata-only en PG11+, sin reescritura de tabla). B es segura *por construcción*: la migración crea y
altera exclusivamente objetos que ya son de SAC, y eso se verifica mecánicamente leyendo el archivo de
migración, sin tener que confiar en el razonamiento de nadie. Con las 3 organizaciones cliente
operando sobre `purchases` todos los días, la diferencia entre "seguro porque lo argumenté" y "seguro
porque no lo toqué" vale un join.

**Tabla nueva = permitida sin discusión** por la regla de no-regresión del briefing de QA
(*"Tablas nuevas: libres"*), a diferencia de A, que exigía declarar una desviación.

### D3 — 🔴 El listado NO puede usar `join`: 1:1 pasa a 1:N

`get_multi` hace hoy `q.outerjoin(Purchase, InboundOrder.purchase_id == Purchase.id)`, seguro porque
la relación es 1:1. Con la tabla puente, **ese mismo join duplicaría la Entrada una vez por compra
derivada**: una entrada de 12 proveedores aparecería 12 veces en la bandeja, y con paginación el
efecto es peor que cosmético (filas perdidas al final).

Todo el filtro por estado pasa a subconsultas **`EXISTS` / `NOT EXISTS`**, que no multiplican filas.
Mismo criterio ya aplicado a la búsqueda por factura (#87 A) y a `willard_world` (#82).

El total en pesos y el conteo de comisiones, que hoy salen del `purchase` único, pasan a agregados por
entrada (una consulta agregada por página, patrón `_page_context()`).

### D4 — Estado derivado con un cuarto valor: `partially_liquidated`

`display_status_of()` y su espejo SQL ganan un estado. Precedencia, ignorando las compras canceladas
salvo en el caso 3:

1. Orden `annulled` → **annulled**
2. Tipo willard → como hoy (`draft`→registered, `confirmed`→liquidated)
3. Sin compras vivas: todas canceladas → **annulled**; ninguna derivada → **registered** (defensivo)
4. Todas las vivas liquidadas → **liquidated**
5. Alguna liquidada y alguna registrada → **partially_liquidated**
6. Ninguna liquidada → **registered**

El guardarraíl `test_filter_parity_with_field` (Python vs SQL) se extiende al estado nuevo y es
**bloqueante**: si el espejo SQL y la función Python se separan, la bandeja miente.

**Etiqueta al usuario:** "Parcial". La bandeja de pendientes (`sort=oldest`, semáforo de días) incluye
`registered` **y** `partially_liquidated` — una entrada con 10 de 12 liquidadas sigue teniendo trabajo
pendiente y no puede desaparecer de la vista de Ingrid.

### D5 — La remisión viaja por proveedor, no por línea

El payload gana `supplier_invoices: [{third_party_id, invoice_number}]` en la cabecera, que el backend
reparte a cada `PurchaseCreate`. **No** va en la línea: un proveedor con 3 materiales tiene UNA
remisión, y ponerla en la línea la repetiría 3 veces con riesgo de que difieran.

Validación: todo `third_party_id` de la lista debe aparecer en las líneas (422 si no) y no puede
repetirse (422).

Lectura (interacción con #87 A): `InboundOrderResponse.invoice_number` devuelve la remisión **cuando
la entrada tiene una sola compra derivada**; con varias devuelve NULL y el detalle las muestra por
grupo. Willard intacto (su remisión sigue en la columna propia). La condición de lectura sigue siendo
espejo de la de escritura — que es lo que hace imposible la desincronización.

### D6 — Derivación: agrupar por proveedor y crear N compras en la misma transacción

`create` deja de armar un `PurchaseCreate` y pasa a agrupar `lines` por `third_party_id`, creando una
compra por grupo con `commit=False` (patrón ya existente). Todo en una transacción: o entran las 12
compras o no entra ninguna.

Orden de creación estable (por nombre de proveedor) para que los consecutivos de compra sean
predecibles y los tests deterministas.

### D7 — Edición: revert-and-reapply por grupo, bloqueando solo el proveedor liquidado

- Si **ninguna** compra está liquidada: se editan líneas libremente (agregar o quitar proveedores
  incluido) → se recalculan los grupos y se aplica revert-and-reapply sobre las registradas.
- Si **alguna** está liquidada: se bloquean con 422 las líneas de **ese proveedor**, nombrándolo, y se
  permite editar el resto. La cabecera (conductor, vehículo, notas, fecha) sigue editable siempre,
  como hoy.

**Por qué por proveedor y no todo o nada:** con liquidación gradual (respuesta 3), una entrada de 12
va a estar casi siempre parcialmente liquidada; bloquear la edición completa la volvería intocable
justo en su estado normal.

### D8 — Anulación: atómica, se niega si hay alguna liquidada

`annul()` cancela todas las compras **registradas**. Si alguna está liquidada → **422 nombrando
cuáles**, sin cancelar nada. Misma regla de hoy escalada a N, consistente con #82: una compra
liquidada se cancela directo desde Compras con la elección de #63, y después se anula la entrada.

### D9 — Guard: multi-proveedor solo en tipo compra

`inbound_type='willard'` con proveedores distintos → **422**. Ver conflicto C3: es la defensa
explícita de una invariante que hoy existe implícita (el titular willard está amarrado a la cuenta de
kg, #80).

### D10 — Cero permisos nuevos

David captura con `purchases.create` / `purchases.edit`; Ingrid liquida con `purchases.liquidate`,
compra por compra, desde la bandeja. Nada que asignar en producción.

### D11 — 🔴 Los dos caminos de código COMPARTIDO que sí cambian (enmienda v1.1)

La tabla puente elimina el riesgo de esquema, pero **quedan dos funciones que hoy corren para todas
las organizaciones** y que necesariamente cambian de tabla consultada. Se declaran acá porque son el
punto exacto donde este ciclo podría filtrarse fuera de SAC:

| Función | Dónde | Hoy | Después |
|---|---|---|---|
| `_inbound_origin_map` | `endpoints/purchases.py:42` — corre en **cada listado de compras de cada organización**, sin *gate* de flag | `SELECT … FROM inbound_orders WHERE org=? AND purchase_id IN (…)` | igual, pero desde la tabla puente |
| Guard D7b | `services/purchase.py:706` — corre en **cada cancelación de compra registrada de cada organización** | `SELECT order_number FROM inbound_orders WHERE purchase_id=?` | igual, con un join a la tabla puente |

**Por qué el cambio es inocuo, y cómo se prueba en vez de afirmarlo:** ambas consultas filtran por
`organization_id` y las organizaciones sin `kg_ledger_enabled` **no tienen ni una fila** en
`inbound_orders` ni en la tabla puente. El resultado es vacío antes y después, así que
`PurchaseResponse` sale idéntico y el guard sigue sin disparar. Eso deja de ser un argumento y pasa a
ser el **test 23**: una organización sin el flag, con compras, listadas y canceladas, con el response
comparado campo por campo contra el de hoy.

**Optimización deliberadamente NO incluida:** se podría saltar `_inbound_origin_map` cuando el flag
está apagado y ahorrarles esa consulta a las otras 6 organizaciones. Es tentador y es una mejora real,
pero es un cambio de comportamiento en camino compartido que no pide este ciclo — entra como ítem
propio si se quiere, no de contrabando acá.

---

## 4. No-regresión

Hay 6 organizaciones en producción además de SAC (Costa, MetaRecycling, Biogreen y 3 demo).

**La migración toca CERO tablas compartidas** (enmienda v1.1). Los tres objetos con cambio de esquema
son exclusivos de SAC:

| Objeto | Cambio | Filas fuera de SAC |
|---|---|---|
| `inbound_order_purchases` | tabla nueva | — |
| `inbound_order_lines.third_party_id` | nullable → backfill → NOT NULL | **0** |
| `inbound_orders.third_party_id` | NOT NULL → nullable | **0** |

`inbound_orders` y `inbound_order_lines` nacieron en E2 detrás de `kg_ledger_enabled`, con el router
*gated* (403 incluso para admins). El backfill lee y escribe únicamente esas tablas.

**El resto de lo que protege a las otras organizaciones, por construcción:**

1. **Cero tipos de MoneyMovement nuevos** → P&L / cash flow / conciliación (#59, #65, #69) intactos
   por construcción.

   > **Sobre H2 (conteo del catálogo).** Cuando QA revisó, el "47" salía del árbol de trabajo sucio:
   > los dos tipos de diferencia (`asset_sale_collection`, `asset_sale_receivable`) eran del ciclo de
   > **venta de activos fijos** de otro agente, entonces sin commitear — contra `HEAD` eran 45. Ese
   > ciclo aterrizó después (commit `158e8a0`, decisión **#88**), así que **hoy son 47 también en
   > `HEAD`** y QA tenía razón por adelantado.
   >
   > Justamente por eso el claim se deja **sin número**: **este ciclo no agrega ni quita tipos**. Es
   > la propiedad que importa y no caduca cada vez que aterriza un ciclo vecino.

2. **6 organizaciones en producción además de SAC** — confirmado hoy contra el servidor durante el
   deploy: Costa, MetaRecycling, Biogreen, Pacífico Demo, Norte Demo y Reciclaje Demo. Que ninguna
   tenga filas en `inbound_orders` es la premisa del backfill y **se verifica empíricamente antes de
   correrlo** (§7.1, condición 2 de QA), no se asume.
3. **Cero permisos nuevos** → ningún rol cambia.
4. **`display_status` y `partially_liquidated` no existen fuera del módulo de Entradas**, que solo se
   monta con el flag encendido.
5. Los **dos caminos de código compartido** que sí cambian están aislados y probados — ver **D11** y
   el test 23.

**Desviación declarada de la regla de migraciones.** El §4 del briefing de QA prohíbe *"ALTER de tipo
y backfill que toque datos existentes"*.

QA aportó una precisión técnica a favor del plan: **cambiar nulabilidad no es un `ALTER` de tipo**. La
cláusula que este plan sí viola es la del **backfill sobre datos existentes**, y solo esa.

Y corrigió un encuadre que la v1.1 tenía mal: decir *"cero filas fuera de SAC"* es cierto pero
tramposo, porque **SAC ya es producción**. El backfill toca datos productivos reales — los de SAC, que
llevan días operando. Lo que hace aceptable la desviación no es que no toque producción, sino que:

- los dos backfills son **copias puras de una FK que ya existe** (`line.third_party_id` ←
  `order.third_party_id`; puente ← `inbound_orders.purchase_id`), deterministas, sin cómputo ni
  criterio;
- el `SET NOT NULL` **revienta la migración** si algo quedó suelto, en vez de dejar datos corruptos;
- y la ventana es real: hoy son decenas de filas, en tres meses son miles con retenciones y pagos
  encima.

La alternativa formalmente conforme —dejar la línea nullable con *fallback* a la cabecera— compra el
cumplimiento a cambio de la clase de bug que D1 elimina, en el camino que mueve dinero. Se prefiere la
migración honesta y acotada, **con las tres condiciones de QA en el runbook (§7.1)**.

**Gates:** suite completa verde (hoy 1445), `tsc` y build limpios, y `schema_parity_check.py` con cero
divergencias propias. **Golden ×3 orgs: no aplica** — ningún objeto tocado tiene filas en las
organizaciones cliente y ningún reporte lee la tabla puente. Si QA lo considera insuficiente, se corre:
cuesta una hora y cierra la discusión con evidencia en vez de argumento.

---

## 5. Superficie de cambio

### Backend

| Archivo | Qué |
|---|---|
| `models/inbound_order.py` | `third_party_id` nullable; `purchase_id` inerte; la línea gana `third_party_id`; modelo `InboundOrderPurchase` nuevo |
| `models/purchase.py` | **sin cambios** (enmienda v1.1) |
| `schemas/inbound_order.py` | línea gana `third_party_id`; cabecera gana `supplier_invoices`; response gana `partially_liquidated` y `suppliers[]` |
| `services/inbound_order.py` | `create` (D6), `update` (D7), `annul` (D8), `display_status_of` (D4), `get_multi` (D3), `_page_context` (agregados) |
| `services/purchase.py` | 🔴 **compartido** — guard D7b apunta a la tabla puente (D11) |
| `api/v1/endpoints/purchases.py` | 🔴 **compartido** — `_inbound_origin_map` apunta a la tabla puente (D11) |
| `api/v1/endpoints/inbound_orders.py` | enrich: proveedor(es), remisión condicional, totales agregados |
| Migración | 1 tabla + 2 columnas + backfill (§7) |

### Frontend

`InboundCreatePage`, `InboundEditPage`, `InboundDetailPage`, `InboundOrdersPage` (~2.300 líneas) y el
`returnTo` de `PurchaseLiquidatePage`. Sin cambios en `queryInvalidation.ts` (las llaves ya existen).

El formulario de captura se organiza **por grupos de proveedor**: interruptor "un solo proveedor /
varios"; con "varios", cada grupo tiene su selector, su remisión y sus líneas de material. El detalle
muestra un bloque por proveedor con su compra, su estado y su acción de liquidar.

Móvil (regla obligatoria, 390px): los grupos son tarjetas apiladas, nunca una tabla ancha.

---

## 6. Tests

Contrato del repo: caso feliz, validaciones, edge cases de negocio, side-effects cross-módulo, RBAC.

**Estructurales**
1. Entrada con 3 proveedores → 3 compras, cada una con sus líneas y su remisión
2. 🔴 Entrada con 1 proveedor → 1 compra, comportamiento idéntico al de hoy (no-regresión)
3. Mismo material de dos proveedores distintos en la misma entrada → 2 líneas, 2 compras
4. `supplier_invoices` con proveedor ausente de las líneas → 422; repetido → 422

**Estado derivado**
5. 0 de 3 liquidadas → `registered`
6. 1 de 3 → `partially_liquidated`
7. 3 de 3 → `liquidated`
8. Una cancelada + dos liquidadas → `liquidated`
9. Todas canceladas → `annulled`
10. 🔴 Paridad Python↔SQL extendida a los 4 estados (`filtro == campo`)
11. 🔴 Anti-duplicación: entrada con 12 compras aparece **una sola vez** en el listado

**Edición y anulación**
12. Editar líneas sin nada liquidado → revert-and-reapply correcto
13. Editar líneas de un proveedor liquidado → 422 nombrándolo
14. Editar líneas de otro proveedor con un tercero liquidado → 200
15. Anular con todas registradas → todas canceladas + entrada anulada
16. Anular con una liquidada → 422, **nada cancelado** (atomicidad)

**Side-effects cross-módulo**
17. 3 proveedores liquidados → 3 causaciones de comisión, saldo del recolector = suma
18. Retenciones por proveedor, sin cruce entre compras
19. Costo promedio idéntico liquidando 3 compras pequeñas o 1 grande equivalente (#65)

**Guards y RBAC**
20. Willard con dos proveedores → 422 (D9)
21. Sin `kg_ledger_enabled` → 403
22. Liquidar sin `purchases.liquidate` → 403

**No-regresión de los caminos compartidos (enmienda v1.1)**
23. 🔴 Organización **sin** `kg_ledger_enabled`, con compras propias: el listado devuelve
    `PurchaseResponse` con `inbound_order_id`/`inbound_order_number` en NULL, y cancelar una compra
    registrada **no** dispara el guard D7b. Es la prueba de D11 — el único punto por donde este ciclo
    podría filtrarse a Costa, MetaRecycling o Biogreen.

---

## 7. Migración y datos

```
CREATE TABLE inbound_order_purchases        -- tabla nueva, exclusiva SAC
inbound_order_lines.third_party_id          NOT NULL (crear nullable → backfill → SET NOT NULL)
inbound_orders.third_party_id               NOT NULL → nullable
-- purchases: SIN CAMBIOS
```

Backfill, en este orden:

1. `inbound_order_purchases` ← una fila por cada `inbound_orders.purchase_id` no nulo
2. `inbound_order_lines.third_party_id` ← desde la cabecera de su orden
3. `SET NOT NULL` en la línea

Todo el backfill lee y escribe tablas exclusivas de SAC. `purchases` no se lee ni se escribe.

### 7.1 Runbook del backfill — las 3 condiciones de QA

Son **gate de deploy**, no recomendaciones. El backfill toca datos productivos de SAC.

1. **Backup completo de la base de producción antes del deploy.** Es la mitigación estándar del repo
   para tocar datos reales (precedente #43, migración de `liquidated_at`). El paso ya existe en la
   skill `/deploy`; acá se declara explícitamente como bloqueante: sin backup verde, no se migra.

2. **Verificar empíricamente el conteo por organización, antes de correr el backfill:**

   ```sql
   SELECT organization_id, COUNT(*) FROM inbound_orders      GROUP BY 1;
   SELECT organization_id, COUNT(*) FROM inbound_order_lines GROUP BY 1;
   ```

   La premisa del plan es que **solo SAC aparece**. Si aparece cualquier otra organización —una demo
   con el flag encendido, por ejemplo— la premisa de no-regresión se rompe y **la migración se
   detiene** hasta reevaluar. No se asume: se mira.

3. **Downgrade documentado.** El `downgrade()` de la migración debe dejar el esquema en su forma
   anterior y **declarar explícitamente qué pasa con los datos**: al volver `inbound_order_lines`
   nullable no se pierde nada, pero las entradas creadas con varios proveedores **no caben en el
   modelo viejo** — al revertir, sus líneas conservan su proveedor mientras que la cabecera queda
   NULL, que es un estado que el código anterior no espera. La instrucción operativa es: **revertir
   solo antes de que se capture la primera entrada multi-proveedor**; después, el camino es hacia
   adelante. Se escribe en el docstring de la migración, no solo acá.

Ventana: `inbound_orders` lleva días de datos reales y solo en SAC. Dentro de tres meses el backfill
son miles de filas con retenciones y pagos encima. **Es la ventana más barata que va a haber.**

---

## 8. Riesgos

| Riesgo | Mitigación |
|---|---|
| 🔴 Duplicación de filas por el join 1:N | D3 (EXISTS) + test 11 |
| 🔴 Fuga a otras organizaciones por los 2 caminos compartidos | D11 + test 23. La migración ya no toca `purchases`. |
| 🔴 Deriva entre el estado Python y el SQL | Test 10, bloqueante |
| 🔴 C3 falso: las rutas SÍ traen postconsumo multi-proveedor | D9 bloquearía el caso real. Confirmar con Johana antes de codificar. |
| Backfill deja líneas sin proveedor | El `SET NOT NULL` revienta la migración en vez de dejar datos rotos |
| Ingrid sigue liquidando 12 veces | Declarado fuera de alcance (§1). Ciclo propio si lo piden. |
| La respuesta 1 viene de Daniel, no de Johana | Si Johana contradice el "lo que recibe SAC es lo que cuenta", cambia el peso de la línea, no la arquitectura |

---

## 9. Criterios de aceptación

1. Una Entrada con 12 proveedores se captura en un solo formulario y deriva 12 compras.
2. Cada compra tiene su remisión, retenciones, saldo y liquidación independientes.
3. Ingrid liquida de a una y la Entrada muestra "Parcial" hasta terminar.
4. Una entrada de un solo proveedor se comporta **exactamente** como hoy.
5. Ninguna entrada aparece duplicada en la bandeja.
6. La comisión del recolector se causa una vez por proveedor liquidado.
7. Las otras 6 organizaciones no ven ningún cambio: la migración no toca ninguna tabla suya y el
   test 23 lo demuestra sobre el listado y la cancelación de compras.
8. Usable en 390px.
9. 🔴 **Gate duro previo a codificar** (condición 2 del GO de QA): `requerimientos-funcionales.md`
   actualizado a **v0.6** con C1 (la regla se relaja solo en compra regular, se conserva donde vive su
   razón) y C2 **en los dos lugares** — §7.3 punto 5 y la tabla de actores.
10. 🔴 **Gate duro previo a codificar** (condición 1 del GO de QA): respuesta de Johana a *"¿alguna
    ruta trae material Willard de más de un proveedor?"*. Si es que sí, el asunto escala como
    incidente sobre #80 y este plan espera.
11. Las 3 condiciones del backfill (§7.1) cumplidas antes del deploy.
