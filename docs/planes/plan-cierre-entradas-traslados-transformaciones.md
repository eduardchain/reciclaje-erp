# Plan de cierre — Entradas, Traslados/Transformaciones y lo demás

**Origen:** reunión SAC 12-ago-2026 (Hugo Bedoya, dueño) + briefing Johana 11-ago
**Estado del repo al escribir:** `develop`, 3 commits locales sin push, working tree limpio salvo `InboundLiquidatePage.tsx`
**Método:** 45 requisitos extraídos del transcript, mapeados contra código con evidencia archivo:línea y verificados adversarialmente (44 sobrevivieron, 4 corregidos, 1 refutado), más 10 requisitos del frente transformaciones analizados aparte. Las cinco afirmaciones que cambian una recomendación —guard de sede/tránsito ausente, cross-unit sin red de conservación, permisos de Erwin, origen singular, sin validador de fecha futura— se re-verificaron a mano contra el código.

---

## 0. Lo primero, porque cambia la conversación del viernes

En el cierre quedaste en llevarte *"las entradas, los traslados, transformaciones"* y dijiste que no sabías si tenías chance el viernes. **Entradas sí. Traslados-transformaciones no, y no por poco.**

Los últimos 13 minutos (transcript 1059–1205) son un módulo nuevo: picadores como inventario alterno, molino con estándar de recuperación del 90–91%, cortes mensuales, alertas de desviación, deuda en scrap. Hugo lo pidió textual — *"en vez de tener un solo módulo de traslados, un módulo para cada proceso"* — y quedó aceptado: *"que tengamos ahí la trazabilidad, las eficiencias, ustedes tengan todo ahí supermedido"*. Y lo condicionó al go-live (1203): *"Después de que organicemos eso, goleamos porque eso es de lo más completo"*.

Ese bloque **depende de una tabla que todavía no se pidió** (los estándares del molino; Johana los mencionó el 11-ago y quedó en pedírselos). Sin esa tabla no se puede construir la parte que a Hugo le importa.

**Recorte honesto para el viernes:** Entradas cerrado + decisiones de traslados/transformaciones **tomadas y escritas**, no construidas. Decírselo antes, no después.

---

## 1. Lo que Hugo pidió y ya funciona

No re-construir. Con evidencia para que no haya duda.

| Lo que pidió | Dónde está |
|---|---|
| P&L separado por sede (ventas, COGS, báscula) | `reports.py:519,534,554` + endpoint `endpoints/reports.py:62` |
| Comisiones fragmentadas por la sede de su venta | `reports.py:968-974` — por `Sale.warehouse_id`, nunca por `MoneyMovement.warehouse_id` (nace NULL) |
| *"le resta el balance de ella y se lo abona a planta"* (maquila) | El par ya nace direccionado: `transfer.py:542` expense→sede origen, `:557` income→sede destino; se fragmenta en `reports.py:1016-1019`. Tests verdes: `test_pnl_by_warehouse.py:209-215` (CV −11.000), `:223-226` (JM +40.000) |
| *"una deuda de planta a circunvalar en plomo"* | `transfer.py:477-494`, `source_type='intersede_send'` contra la cuenta kg `intersede` |
| Deuda Willard discriminada por sede (postconsumo) | Obligatoria por CHECK de BD: `models/kg_ledger.py:100-103`. Ya hay 2 cuentas: `seed_sac_org.py:224-225` |
| *"la deuda no me puede afectar al balance"* | Cumplido por construcción: `grep kg_ledger` sobre `reports.py` (4.600 líneas) → **cero**. El libro de plomo es paralelo |
| Bogotá hace su propia entrada contra su propia bodega | `models/inbound_order.py:61` + `is_receiving` (`models/warehouse.py:42-45`). Bogotá ya nace receptora: `seed_sac_org.py:117` |
| Transformación 1→N con bodega origen ≠ destino y cambio de unidad | `models/material_transformation.py:85` y `:283` son campos **independientes**, validados por separado (`services/material_transformation.py:83`, `:100`). Cross-unit resuelto (#53) |
| *"cuando se trasladan del molino a Juan Mina también se genera la misma maquila"* (Johana) + *"genera un plomo a devolver y a su vez una deuda de circunvalar por maquila"* (Hugo) | **Ya funciona, tal cual lo describen.** #84+#94: `transfer.py:117` decide `crosses_sede`, `:183` estampa `is_contributor`, `:477` emite kg intersede y `:497-503` el par de maquila. Como Molino y Circunvalar comparten sede, **CV→Molino no emite y Molino→JM sí**. Test: `test_sac_transfer_two_step.py:1131` |
| *"¿quién salió y quién recibió?"* | `transfer.py:127,135` (`created_by`/`received_by`) — falta confirmar que se pinte |
| El peso de báscula ya se captura, en ambos tipos | `models/inbound_order.py:276`, input en `InboundCreatePage.tsx:754-762` |
| Cualquier cobro a Willard aparecería en su estado de cuenta | `endpoints/money_movements.py:832-857` fusiona todas las fuentes por `third_party_id` |

**El corolario incómodo:** el peso ya se captura y **no lo lee nadie**. `grep scale_weight_kg` en todo el repo da 4 escrituras, 1 serialización y 3 renders — **cero operaciones aritméticas**. Es el dato del que cuelga medio backlog y está muerto en la base. Eso explica literalmente la pregunta de Hugo en vivo: *"¿Dónde sale aquí el peso de lo que acabamos de traer?"* (315) — la pantalla de liquidación no lo muestra (`grep scale_weight` en `InboundLiquidatePage.tsx` → **cero**).

---

## 2. Frentes, ordenados por dependencia

### F0 — Personas y roles. **Bloqueante duro. Cero código.**

Hugo describió la cadena tres veces: **David captura → Erwin revisa → Johana liquida** (867, 1075). En el sembrado:

- **David no existe.** `seed_sac_org.py:60-70`: hugo, johana, yurani, erwin.
- **Erwin no puede revisar.** Su rol `bascula_sac` (`:72-83`) tiene `purchases.create`/`edit`/`view` — **no** `purchases.review`.
- El `REVISOR_ROLE` existe y se crea (`:88-95`, `:493-500`) pero **ningún usuario lo tiene asignado**. El comentario del propio seeder lo anticipó: *"sin nadie con purchases.review, 'revisada' frenaría la operación"*.
- Los 3 admins sí pueden revisar, pero por bypass (`deps.py:227`), no porque el flujo esté armado.
- 🔴 **Y Erwin tampoco puede registrar el molino.** Johana lo señala como quien lleva las cuentas del molino; `bascula_sac` **no tiene `transformations.view` ni `transformations.create`** — ni siquiera `inventory.view`. `revisor_inventario` tampoco. Verificado contra `seed_sac_org.py:75-82,92-96` y el catálogo `services/role.py:68-69`. Hoy Erwin no ve la pantalla de transformaciones.

O sea: el estado `reviewed` de #93 está construido, con permiso y rol, y **la persona que Hugo designó como revisor no puede ejercerlo**; y la persona que Johana designó para el molino no puede registrarlo.

**Trabajo:** crear David, asignarle `bascula_sac`, mover a Erwin a `revisor_inventario` (o darle ambos) y sumarle transformaciones. Media hora de configuración. **Antes de cualquier otra cosa**, o el flujo que Hugo dio por sentado se traba en la primera entrada real.

⚠️ Al abrir transformaciones a Erwin se abre entero: **anular usa el MISMO permiso que crear** (`endpoints/material_transformations.py:61` y `:86`, ambos `transformations.create`). Quien registre el molino podrá anular transformaciones ajenas. Si eso molesta, separar el permiso es un ciclo chico — pero `transformations.*` es catálogo compartido con las 3 orgs.

---

### F1 — Peso obligatorio y consumible en la Entrada. **El habilitador del backlog.**

De esto cuelgan: liquidar por peso, el 53%, el costo por tonelada por proveedor, el peso promedio para renegociar con Willard, y la base del flete por kg.

**Qué se construye:**
1. Volver `scale_weight_kg` obligatorio en captura tipo compra (hoy `Optional ... gt=0`, `schemas/inbound_order.py:40`).
2. **Exponerlo en la liquidación** — hoy Johana liquida sin ver el peso.
3. Decidir el caso de materiales cuya unidad ya es kg (peso == cantidad; exigir ambos es fricción pura).

**Trampas verificadas:**
- El frontend convierte 0 → `null` antes de enviar (`InboundCreatePage.tsx:368`, `InboundEditPage.tsx:66`) con estado inicial 0 (`create:67`): hoy dejar el campo vacío **se descarta en silencio**.
- Las líneas de truncamiento D16 nacen **al liquidar** con `quantity=0` (`services/inbound_order.py:464-469`) y sin peso: la validación no puede correr sobre ellas.
- Entradas SAC ya capturadas sin peso quedan ineditables si se valida sin backfill.

**Toca:** `inbound_order_lines`, tabla exclusiva SAC, router flag-gated. **Sin golden gate.**
**Esfuerzo:** S. **Decisión previa:** bloqueo duro (422) vs. warning ámbar. Recomendación: **warning en captura, bloqueo en liquidación** — ahí el dato es indispensable y quien está al teclado es Johana, no el báscula. Coherente con #17/#76.

---

### F2 — El 53%: dónde vive y si es único. **Decisión de producto, no de código.**

Hugo: *"En las compras regulares es diferente… del peso de la batería el 53% es plomo"* (00:18:29). Se preguntó si aplica a todas las baterías (513) y **Hugo cambió de tema sin responder**.

**El modelo actual no solo no lo tiene: lo impide.**
- Una fórmula vigente por material: `services/material_conversion_formula.py:100-108` (DISTINCT ON `material_id`).
- El tipo está amarrado a la unidad con 422: `schemas/material_conversion_formula.py:29-33` (`battery_to_lead`→`unidad`). **Una batería no puede tener hoy una fórmula de porcentaje** — que es exactamente la forma del 53%.
- El cálculo multiplica siempre por cantidad, nunca por peso: `services/inbound_order.py:1941-1954`.

**Tres opciones, de más barata a más cara:**
- **(a)** Parámetro único de organización en `settings`. Barato, aditivo, sin migración. Sirve si el 53% es uno solo.
- **(b)** Campo en `material_kg_profiles` (tabla SAC-only). Permite variación por referencia.
- **(c)** Tipo de fórmula nuevo (`weight_to_lead {lead_percentage}`) sobre `scale_weight_kg`, con la clave de vigencia pasando de `material_id` a `(material_id, canal)`.

🔴 **La opción (c) tiene un riesgo que no se ve:** el par (fórmula vigente, cantidad) tiene **tres consumidores acoplados** — `inbound_order.py:1922-1939`, `transfer.py:1066-1081` (maquila y deuda intersede: **números de plata**) y `InboundCreatePage.tsx:86-100` (reusado por Stock). Si aparecen dos fórmulas vigentes por material sin que los tres sepan del canal, `.first()` devuelve la que sea. Mismo modo de falla que #77 eliminó al quitar el subtype.

🔴 **Restricción dura, cualquiera sea la opción:** el plomo de compra regular **NO puede generar `KgLedgerMovement`**. Las cuentas kg son deuda con Willard; el plomo de una compra es material propio. Hugo lo separó él mismo: *"son dos temas"*. Si entra al libro, se inventa un pasivo.

**Esfuerzo:** S (a) a M (b/c). **Sin golden gate** salvo que se cuelgue de `materials` — evitar esa ruta.

---

### E — Entradas: cerrar la liquidación. **Es lo entregable el viernes.**

#### E1 · Liquidar por peso, inventariar por unidad
Hugo ya cerró las dos preguntas que quedaban abiertas:
- **Se digita el total, no el precio unitario** (309-315, textual: *"Ahí sería al contrario, no sería precio unitario sino el precio total"*), y confirmó la fórmula (351): *"el precio unitario sería una fórmula, costo total dividido unidades"*.
- **Lo elige Johana al liquidar, entrada por entrada** (331): *"ella toma o cantidades o toma el peso"*. **No es por proveedor** (205).

🟢 **El motor de costo no se entera.** `incorporate_into_pool` (`services/inventory_costing.py:37-70`) consume un costo unitario escalar; entregarle `total/unidades` es transparente. Modelo L (#64-#66) no se toca.

**Tres cosas que muerden:**
1. **Redondeo:** `PurchaseLine.unit_price` es `Numeric(15,2)` y `purchase.liquidate` **re-multiplica** el total desde el unitario (`services/purchase.py:456-458`); ese total mueve el saldo del proveedor (`:560`) y topa las retenciones (`:1606-1614`). $200.000 ÷ 3 = 66.666,67 × 3 = **200.000,01**. Hay que decidir dónde cae el centavo.
2. **Firma de re-liquidación:** el comparador de #93 cuantiza a `PRICE_Q=0,01` (`services/inbound_order.py:303,527,533`); el precio derivado debe cuantizarse igual o cada re-liquidación disparará un revert-and-reapply innecesario.
3. **Quién parte el peso** cuando una línea se reparte entre dos proveedores. Hugo reconoció que hoy lo hace a mano (205) y **no dijo** si quiere que el sistema lo haga.

**Camino barato (recomendado):** derivar el `unit_price` en `inbound_order.liquidate` antes de armar el `PurchaseCreate` → todo queda dentro de SAC. **Camino caro:** persistir un total independiente en `purchase_lines` (simetrizando con `received_quantity` de ventas) → tabla compartida → **golden gate duro**.

**Esfuerzo:** M. **Decisión previa:** ¿el estado de cuenta puede diferir en centavos de la factura?

#### E2 · Botón "un solo proveedor"
🟢 **El backend ya lo soporta sin tocar nada:** el reparto se agrupa por proveedor antes de crear compras (`services/inbound_order.py:504-507`) y de N líneas con el mismo tercero nace **una** compra (`:538-590`). Es 100% UI.

Pero Hugo pidió más de lo que suena (279): *"No le carga las cantidades al llamar el proveedor de lo que tenga pendiente"* — el botón debe **pre-llenar el reparto**, no solo fijar el tercero. Cuidado con las líneas de `quantity=0` (`schemas/inbound_order.py:36` usa `ge=0`): el toggle ingenuo las deja en "sin asignaciones" y `lineProblems` (`InboundLiquidatePage.tsx:510-512`) bloquea.

**Esfuerzo:** S alto. **Cero backend, cero migración. Mejor relación valor/costo de todo el backlog.**

#### E3 · Listas de precios por conjunto de proveedores
**No existe nada.** `price_lists` es `(material_id, purchase_price, sale_price, notes, updated_by)` — sin nombre, sin agrupador (`models/price_list.py:35-62`); "vigente" es el último `created_at` **por material para toda la org** (`services/price_list.py:75-99`); `ThirdParty` no tiene ninguna dimensión de precio.

🔴 `price_lists` y `third_parties` son **compartidas** y el resolutor alimenta **9 pantallas de las 4 orgs** vía `usePriceSuggestions`. Diseño obligado: aditivo con "sin lista = comportamiento actual byte a byte". **Y el golden NO cubre esta regresión** — `golden_capture.py:24-46` no captura `/price-lists` ni `/third-parties`. La red de seguridad son las 9 pantallas leídas a mano.

Además, `InboundLiquidatePage` **no consume listas de precios en absoluto** — hay que cablear el sugeridor por primera vez ahí (el patrón de hint restaurable ya vive tres veces en ese archivo).

**Esfuerzo:** L. **No es del viernes.**

---

### T — Traslados y transformaciones. **El bloque grande. Todo bloqueado por decisiones.**

#### T0 · La decisión que bloquea todo: ¿el molino es traslado, transformación, o algo nuevo?

Hugo lo describe como **traslado** (1083) pero lo que sale son materiales distintos — eso es **transformación**, que sí cambia el costo.

🔴 **El sistema separó los dos mecanismos deliberadamente y la invariante está declarada:** #84 B1 dice *"un traslado NUNCA cambia el avg, cero MCH"*. La merma de traslado se resolvió como `decrease` normal → `adjustment_net`, **jamás** `cost_adjustment`. **No puede existir "el traslado que además transforma".**

Lo bueno: **la transformación ya soporta lo que hace falta** — `source_warehouse_id` y `destination_warehouse_id` son independientes, así que un solo documento puede sacar batería de Circunvalar y meter PP/PE/plomo fino/grueso/lodo en Circunvalar-Molino. Cross-unit resuelto (#53). El UI ya tiene selector de bodega origen y por línea destino.

**Lectura recomendada:** el molino es una **transformación con bodega origen ≠ destino**, no un traslado. Lo mismo picadores. Y "traslado" queda para lo que Hugo mismo aisló: mover sin transformar (Bogotá→Circunvalar, Molino→Juan Mina).

🔴 **Pero esa lectura tiene un precio que hay que pagar antes, no después.** Verificado hoy contra el código:

1. **La transformación no tiene guard de tránsito NI de sede.** `validate_not_transit_warehouse` se llama desde ajustes (`inventory_adjustment.py:892`), compras (`purchase.py:279,1317`) y ventas (`sale.py:147,757`) — **nunca desde `material_transformation.py`**, cuyo `_validate_warehouse` (`:651-669`) solo verifica org e `is_active`. Y `_crosses_sede`/`_sede_of` viven **solo** en `transfer.py:954-968`. Consecuencia **hoy, sin escribir una línea nueva**: una transformación con origen en Circunvalar y destino en Juan Mina mueve material entre sedes **sin tránsito, sin pesaje de recepción, sin deuda de plomo intersede y sin maquila**. Es exactamente el agujero que #94 cerró para traslados, abierto de par en par para transformaciones. Si el molino se modela así, esto pasa de agujero teórico a caño.
2. **El cambio de unidad apaga la única red de conservación.** #53: si origen y destinos no comparten unidad, el chequeo `Σdestinos + merma == origen` **no corre** (`:117-118`) — lo único que queda es exigir merma 0. El molino es exactamente ese caso (batería en `unidad` → kg). O sea: **en el flujo estrella del cliente no hay nada que atrape un peso mal digitado.** Todo control de rendimiento (T1) hay que construirlo; no se hereda ni un pedazo.
3. **El stock se valida org-wide pero el movimiento se estampa por bodega.** `services/material_transformation.py:86` mira `current_stock_liquidated`, columna de `materials`, org-wide. El stock **por bodega** puede quedar negativo en silencio. Para el molino —donde el punto es saber qué hay en el molino— es una fuente directa de números que no cuadran.

Los tres son trabajo acotado y **hay que hacerlo aunque el molino termine siendo otra cosa**: el agujero de sede ya está abierto.

**Y dos límites del modelo actual que definen si "picadores" y "molino" caben:**
- **No hay multi-origen.** `source_material_id` es singular (`models/material_transformation.py:77`), no una lista. Hugo dice del picado *"puede ser seco o batería a su vez, pueden ser todos"* — hoy eso son N transformaciones separadas. Buscado por `source_lines`, `sources`, `input_lines`, `source_materials`, `multi_source`, `ensamble`: cero.
- **No se puede corregir, solo anular y recrear** (`endpoints/material_transformations.py:54,79` — solo `create` y `annul`, no hay update). Con pesos de báscula reales, un dígito mal tecleado es rutina y cambia el consecutivo.
- **No valida fecha futura.** Los 8 validadores "no futura" de #92 cubren compras, ventas, DP, Entrada y kg manual; `schemas/material_transformation.py` **no tiene ninguno**. Se puede registrar un molino de la semana que viene.

#### T1 · Transformación con estándar, desviación y cortes. **XL. Módulo nuevo.**
Verificado: `grep -E "expected_quantity|standard_yield|rendimiento|eficiencia|yield_pct|recovery"` sobre `models/`, `services/`, `schemas/` → **cero**. Los traslados tienen `transfer_tolerance_pct`; **las transformaciones no tienen tolerancia de ningún tipo**.

Lo que pidió Hugo (1129-1159): estándar esperado vs. real, alertas por encima/por debajo, concepto de corte (*"metí tantas toneladas, ese corte ¿cómo me dio?"*, *"colada colada, bacha bacha"*, *"esta de dross me dio 50, pero esta me dio 61"*), ajuste mensual de inventario. No hay agrupación de transformaciones por lote, ni cierre de corte, ni comparativo entre coladas.

**Sin la tabla de estándares del molino esto no se puede construir.** Pedirla hoy.

🔴 **Y acá aparece el golden gate que no se veía:** `material_transformations` / `material_transformation_lines` son **tablas COMPARTIDAS** con las 3 orgs cliente, y alimentan tres líneas del P&L — `value_difference` y `waste_value` (`reports.py:592-625`) y el `cost_adjustment` de línea que entra a la línea de oversell (`:726-745`, `:788-793`). **Cualquier cambio a la matemática de transformación mueve el P&L de Costa y Biogreen.** Si el estándar se construye como tabla aparte que solo lee, el riesgo es bajo; si toca el cálculo, es gate duro.

**Dos trampas de costeo que van a morder en el molino específicamente:**
- **La merma cuesta al promedio del origen** — `waste_value = waste_quantity × source_unit_cost` (`:145`), y sale del valor distribuible antes de repartir (`:148`). En el molino el ácido drenado y el residuo valen cero o menos, no el costo promedio de la batería. (Con cambio de unidad la merma debe ser 0 de todos modos, así que en la práctica el residuo entra como material destino — pero entonces **se lleva valor** que habría que decidir si merece.)
- **`average_cost` es auto-neutral; los otros dos no.** Con `average_cost` cada destino entra a su propio promedio vigente y el descuadre completo cae en `value_difference` → P&L (`:154-166`). Con `proportional_weight` o `manual` el valor se conserva pero se reparte. **Elegir el método equivocado no da error: da un P&L distinto.** Para el molino hay que fijar el método, no dejarlo a criterio de quien registra.

⚠️ El `transaction_date` del MCH difiere entre crear (`data.date.date()`, `:262,312`) y anular (`business_today()`, `:395,441`). Es deliberado (#66 H2 + #91), pero anular un molino de hace un mes escribe su checkpoint **hoy** y redistribuye el P&L entre fechas.

#### T2 · Picadores: ¿bodega o proceso?
Hugo lo llama *"una zona"* y *"inventario alterno"*, y dice *"sí afecta a Johana, pero debe quedar ahí"* (1079). Bodega → configuración (el patrón ya existe: bodegas internas no receptoras, `models/warehouse.py:39-44`). Proceso con estándar → módulo. **Preguntarlo antes de estimar.** Ojo: si un picador procesa seco **y** batería en el mismo turno y sale un solo montón de scrap, eso es un evento con múltiples entradas — **hoy imposible** (T0, sin multi-origen).

#### T2b · Faltan los materiales de salida del molino. **Bloqueante silencioso.**
El seeder SAC tiene `PP-MOL`, `LOD-01` (lodo), `TAP-BOR`, `CAJ-PLA`, `CAJ-ACR` y la familia `SCR-*` (`seed_sac_org.py:160-199`). **No existen** PE (polietileno de alta), *"plomo fino"*, *"plomo grueso"* ni ABS —los cuatro que Hugo y Johana nombran como salida real del molino—. Sin ellos no se puede modelar la salida ni medir rendimiento. Puede que sean nombres de materiales que ya existen; hay que preguntarlo, no adivinarlo.

#### T2c · Horno y crisol: la tabla existe y **nada más**. 
Cadena verificada pieza por pieza:

| Pieza | Estado |
|---|---|
| Tablas en BD | ✅ `b5c8e1a2f3d4:400-403` |
| Modelo SQLAlchemy | ✅ `models/plant_process.py:75` (`FurnaceCharge`), `:116` (`CrucibleCharge`) |
| Schema Pydantic | ❌ no existe |
| Servicio | ❌ no existe |
| Endpoint | ❌ no existe |
| UI | ❌ cero hits en `frontend/src` |

Ni un test. El propio docstring lo dice (`:10-11`): *"E1 solo crea la estructura; los efectos llegan en E3"*. Lo que **sí** funciona son las **cuentas en kg** de horno y crisol (`schemas/kg_ledger.py:18`, KPIs en `KgLedgerPage.tsx:200-201`) — pero solo se alimentan **a mano**: la creación está restringida a `source_type='manual_adjustment'` (`services/kg_ledger.py:370`). Los `furnace_*`/`crucible_*` figuran en un comentario del modelo y **nada los escribe**.

⚠️ `batch_id` (`plant_process.py:56-60`) **no tiene FK y es NULL por diseño** — es un placeholder, no un punto de partida. La trazabilidad por colada (T4) exige crear `furnace_batches` y decidir la FK.

**Tablas exclusivas SAC** → sin golden gate. Es el único bloque grande del backlog donde el blast radius es cero.

#### T2d · Maquila del crisol ($300/kg): tarifa configurable que no produce ningún asiento
`maquila_crisol` existe como código válido y es creable desde Config → Tarifas (`schemas/service_tariff.py:16,29`). **Nadie lo consume**: los únicos `tariff_code` que el backend lee en runtime son `comision_green_loop` y `maquila_intersede_cv_jm`. Igual el `source_type='crucible_discharge'` documentado en `models/money_movement.py:332` — ninguna línea de código lo escribe.

**Riesgo concreto:** un usuario puede cargar hoy la tarifa de $300/kg, verla en pantalla, y no pasará nada nunca. Mismo patrón que los dos fletes Willard (W2). Vale la pena decidir si esas tarifas se ocultan hasta que tengan consumidor.

#### T2e · *"Ese peso entregado, ¿a cuánto scrap corresponde?"* — es una fórmula de otra clase
Hugo (textual): *"buscar una fórmula de que esa batería entregada, ese peso entregado, ¿a cuánto scrap corresponde? ¿A cuánto material?"*.

Las fórmulas de hoy convierten **solo a plomo**: `battery_to_lead` y `drosses_to_lead` (`schemas/material_conversion_formula.py:21-25`), con `custom` explícitamente deshabilitado (`:75`). Lo que él pide es 1→N con proporciones por destino — **una clase distinta, no una variante**. Es la misma estructura que necesita el estándar del molino (T1): conviene diseñarlas juntas, es la misma tabla.

#### T3 · El segundo pesaje intra-sede desapareció, y Hugo pidió lo contrario
Hugo (1031): *"eso debe funcionar así para garantizar que lo que salió de un lado se recibió en un lado"*.

Código actual (`services/transfer.py:117-135,186-187`): `status="dispatched" if crosses_sede else "received"`, `quantity_received=None if crosses_sede else qty`. Con el seeder actual **Circunvalar-Molino tiene `sede_name="Circunvalar"`** → **el traslado al molino nace recibido, sin segundo pesaje**.

La excepción de #94 se justificó citando a Johana (*"Circunvalar y su molino son un solo inventario"*). **Hugo no la validó**, y el molino es exactamente donde quiere medir eficiencia contra un estándar. Decidirlo explícitamente, no dejarlo como efecto colateral.

#### T4 · Bogotá→Barranquilla: traslado **y** entrada
Hugo (1067-1075): *"es un traslado y una entrada… David confirmó, Erwin revisó y Johana liquidó, o sea postconsumo o sea una compra, para abonarle al libro ese de Bogotá"*. Lo repite al cierre (1183).

El módulo de Traslados de hoy no tiene revisión, ni liquidación, ni tercero, ni precio. **No había ítem para esto en ningún backlog.** Depende de T5.

#### T5 · 🔴 "SA Bogotá": el hallazgo que abarata el frente entero
Hugo, textual (1071): *"aquí se conoce solamente como **SA Bogotá**. Aquí no, en el balance de nosotros **no discriminamos los x proveedores que tenemos en Bogotá**"*.

Esto convierte "saldos de terceros por sede" —que es XL y peligroso— en **configuración de terceros**. Le basta un tercero agregado por sede. **Es la mejor noticia del análisis; confirmarla por escrito.**

---

### W — Salidas Willard. **La operación genuinamente nueva.**

#### W1 · Salida como abono al postconsumo. **XL.**
Johana (11-ago): *"cuando es abono al postconsumo se tiene que restar de la deuda del postconsumo y del inventario que planta le tiene a circunvalar"*.

`willard_delivery` existe **solo como texto en un comentario** (`models/kg_ledger.py:154-159`). Los tres únicos sitios que crean `KgLedgerMovement` son `inbound_order.py:1135`, `transfer.py:479` y `kg_ledger.py:364`. `intersede_discharge` no existe. Ventas no toca kg. No hay router `/willard`.

Hay que construir el documento que **ate tres efectos hoy inconexos**: salida física (el `decrease` ya conserva valor por #66), `delta_kg` negativo en `willard_baterias`/`willard_drosses`, y `delta_kg` negativo en `intersede`.

**Andamiaje muerto que cambia el encuadre:** `sales.willard_remission_number` y `sales.willard_target_account` **ya existen** (`models/sale.py:119,125`), declarados *"inertes hasta E4"*. O sea, la salida Willard **se diseñó colgada de la entidad Venta**, lo cual choca con el "sin ingreso" del abono. Verificado: 100% muertas.

🔴 **Decisión de modelo antes de construir:** documento propio (patrón `inbound_orders`, blast radius en SAC) vs. variante de `Sale` (tabla compartida → golden gate). **Fuertemente a favor del documento propio.**

🔴 **Dilema de costeo:** si sale al avg y no hay ingreso, **el valor entero cae a resultados como pérdida**. Probablemente correcto (el ingreso ya se reconoció como maquila), pero hay que decidirlo, no descubrirlo.

⚠️ Johana avisó que el plomo a devolver **puede exceder** lo que planta debe (*"quedaría el inventario negativo en planta. Ha pasado"*) → **avisar, no bloquear** (#17/#76).

**Mientras tanto:** el ajuste manual del KgLedger (`services/kg_ledger.py:353-378`, UI en `KgManualMovementDialog.tsx:104-110`) sirve de paracaídas, queda auditado y es anulable. **El riesgo es de proceso** — ver §5.

#### W2 · Flete Willard: 🔴 el diseño obvio está mal
Hugo lo definió **por ruta**, no por centro (639): *"me la entregan en mi bodega, entonces ahí no hay transporte. Pero de Bogotá para Barranquilla hay un transporte. Yo les cobro ese flete"*.

Y colisiona con lo que él mismo aceptó cinco minutos después: que **Bogotá sea sede propia con su propia entrada**. Si la batería Willard de Bogotá entra en la bodega de Bogotá y —como dice explícitamente (699)— **muchas nunca se traen a Barranquilla**, generar el flete en la **Entrada cobraría flete por material que nunca se transportó**.

**El cobro nace en el traslado Bogotá→Barranquilla, no en la entrada.**

Sobre el catálogo: `flete_willard_bog_baq` y `flete_willard_planta_planta` existen como códigos válidos (`schemas/service_tariff.py:17-18,30-31`) pero **nadie los consume** y **no están sembrados**. Y Hugo mencionó **Medellín** (699), que no está en los 5 centros (`utils/org_settings.py:35`) — el diseño tiene que contemplar centros donde no tenemos sede.

#### W3 · El tipo de movimiento para cobrarle a Willard. 🔴 **Golden gate.**
No existe "ingreso causado contra tercero sin caja". `service_income` **exige cuenta** (`services/money_movement.py:318`) y **no mueve saldo de tercero** (`:338`). Los cargos de #70 son todos salientes. Hace falta el espejo exacto de la comisión del recolector con signo invertido; el embudo ya acepta los 4 kwargs SAC (`:1508-1537`).

🔴 `money_movements` es compartida → **terna de signos en 6-7 sitios** (#67/#69/#86) + línea nueva en el P&L + la conciliación #59 pasa de 7 a 8 líneas. **Mitigante fuerte:** si nace con `account_id=NULL` y fuera de `INFLOW/OUTFLOW`, el cash flow queda intacto por construcción (patrón #86). **Correrlo, no asumirlo.**

**Un solo tipo nuevo sirve para los dos fletes y para la maquila Willard.** Hacerlos en el mismo ciclo abarata mucho.

---

### S — Sedes y balance. **El frente más caro y el que puede esperar.**

#### S0 · Reusar `_sede_of` en reportes. **S. Habilitador.**
`sede_warehouse_id` existe (#94) y sus únicos consumidores son el traslado y su validación — **no aparece en `reports.py`**. Consecuencia hoy: *"Circunvalar - Molino"* sale como sede aparte y **sus ventas no suman a Circunvalar**.

No-regresión demostrable: con `sede_warehouse_id` NULL en las 7 orgs, expandir a "bodegas de la sede" devuelve exactamente la bodega. Aun así el golden ya es gate por #94.

**Bonus barato:** el tab **Mensual** acepta `warehouse_id` en backend (`endpoints/reports.py:96`, test en `test_pnl_by_warehouse.py:263`) pero **no tiene el selector en la UI**.

#### S1 · Gasto por sede. **M. 🔴 Golden gate duro.**
`MoneyMovement.warehouse_id` **existe** (`models/money_movement.py:315`) pero está fuera del schema y de todo filtro. Y el bloque entero de gastos del P&L termina con `mm_filters += _not_by_sede` (`reports.py:884-892`), o sea **WHERE false por sede**. Test que lo clava: `test_pnl_by_warehouse.py:212` → `operating_expenses == 0.0`.

**Hoy el P&L por sede de SAC muestra el margen de cada sede y cero gastos: el neto por sede está inflado.**

⚠️ Al implementarlo convivirán **dos criterios de sede** en el mismo reporte: el gasto por su `warehouse_id` propio y `commission_accrual` por la sede de SU venta. No cruzarlos.

#### S2 · Caja y activos fijos por sede. **S cada uno. Las columnas ya están.**
`MoneyAccount.warehouse_id` y `FixedAsset.warehouse_id` existen desde E1 y están **100% inertes**. El seeder ya crea *"Caja Circunvalar"*, *"Caja Juan Mina"*, *"Caja Bogota"* — hoy son etiquetas de texto. Exponerlas es aditivo; usarlas en el balance toca `reports.py` en 4 caminos → golden.

#### S3 · Inventario valorizado por bodega. **M.**
🔴 **Trampa activa hoy:** el filtro de bodega en Stock es un filtro de **materiales**, no de stock (`StockPage.tsx:390-392`) — filtrar por Bogotá sigue mostrando cantidad, valor y KPI **org-wide**. Es justo el número que Hugo dice que *"no es una realidad para mí"*.

**Trabajo menor de lo que parece:** la query batch de `inventory_views.py:224-235` **ya calcula la matriz (material, bodega)** — solo descarta el valor.

⚠️ `current_average_cost` es org-wide → la valorización por sede sería `stock_sede × avg_org`. Defendible (los traslados ya despachan al avg org-wide) pero **hay que decírselo a Hugo**.
⚠️ El golden **no captura `/inventory/stock`**: gate propio.

#### S4 · Saldos de terceros por sede. **XL → S, si T5 se confirma.**
Sin T5 es un proyecto: `ThirdParty.current_balance` lo mueven ~25 tipos de MM, compras, ventas, DPs, comisiones, retenciones y obligaciones.

🔴 Techo estructural adicional: **el lado que salda la cartera no tiene sede ni puede capturarla** — `MoneyMovementCreate` no expone warehouse. La deuda sí tiene sede rastreable; el **pago** no.

#### S5 · Balance por sede. **XL. El ensamble de S1-S4.**
🔴 **Lo que Hugo pidió y lo que Johana lleva no son el mismo inventario.** Johana (11-ago): *"lo que está en circunvalar, lo que está en el molino, **lo que salió para exportación pero no se ha liquidado**, lo que se le está debiendo a Willard, **lo que está en planta**, lo que tiene en el crisol. **Todo esto hace parte para mí de un solo inventario**"*. Hugo: *"si yo meto todo en una sola bolsa se me vuelve un inventario complejo"*.

Se reconcilian (lo de planta es CxC en plomo, no inventario en bodega), pero **si el balance por sede se construye como `SUM(quantity) GROUP BY warehouse_id`, el número no va a coincidir con el que Johana lleva y ella no lo va a reconocer.** Resolver **antes** de estimar S5.

---

### R — Reportes. **Todos nuevos. Ninguno es ajuste de uno existente.**

Verificado: los 17 endpoints de `endpoints/reports.py` no incluyen nada de plomo; `grep "plomo|lead"` sobre `services/reports.py` → **cero**.

| # | Reporte | Depende de | Esfuerzo |
|---|---|---|---|
| R1 | Costo por tonelada de plomo por proveedor/mes | F1 + F2 | L |
| R2 | Peso promedio por referencia (para renegociar el 5.2 con Willard) | F1 | M |
| R3 | Resumen de stock por sede, en unidades y en plomo | S3 + decidir la fórmula | M |
| R4 | Trazabilidad de kg liquidados al recolector | — | S |

**R1:** el eje proveedor ya existe y está probado (`PurchaseBySupplier`, `reports.py:2913-2934`). Cuidado con la trampa heredada: su `SUM(quantity)` **mezcla kg y unidades** (#54), que es exactamente la distorsión que Hugo quiere evitar.

**R4:** la comisión persiste monto y `tariff_id` pero **no los kg** — la base se calcula en el navegador (`InboundLiquidatePage.tsx:253-267`) y no viaja. Reconstruible, pero **si Johana editó el monto la reconstrucción miente**. Y `GET /money-movements` **no tiene filtro por `source_type`**: hoy no hay por dónde listarlos. Guardar la base en `inbound_orders` (SAC-only) evita el golden.

---

## 3. Camino crítico

```
F0 personas ──▶ F1 peso ──┬──▶ E1 liquidar por peso ──┐
   (0 código)             │                            │
                          └──▶ E2 un solo proveedor ───┼──▶ ENTRADAS CERRADO
                                                       │
T0 decisión molino ──▶ T0' guards ──▶ T1 mínima ───────┼──▶ MOLINO REGISTRABLE
   │                    (sede+tránsito,   (materiales, │
   │                     stock x bodega)   sin estándar)│
   └── T2b materiales ─────────────────────┘           │
                                                       │
W1 salida Willard (documento propio) ──────────────────┴──▶ CICLO CIERRA
```

**T0' es nuevo y es prerequisito real, no higiene:** los guards de sede y tránsito en transformaciones hay que ponerlos **antes** de mandar el molino por ahí, o el primer error de bodega mueve material entre sedes sin deuda de plomo ni maquila y nadie se entera. Es trabajo chico (calcar lo que ya hacen ajustes/compras/ventas) y **hay que hacerlo igual**, porque el agujero ya está abierto hoy.

**Mínimo indispensable:** F0 + F1 + E1 + E2 + T1-mínimo + W1.
Sin **W1** la deuda de plomo solo crece y el ciclo nunca cierra: hoy `intersede` es un acumulador que solo sube (`transfer.py:477-494`, delta siempre positivo).

**Puede esperar sin bloquear la operación:** S1-S5 completo, R1-R4, W2/W3, E3, T1-con-estándar.

**Realista para el viernes:** F0 + F1 + E2, y E1 si la decisión del centavo se toma rápido. **Traslados/transformaciones: decisiones escritas, no código.**

---

## 4. Para preguntarle al cliente antes de construir

Ordenadas por cuánto bloquean.

1. 🔴 **¿El 53% es único para todas las baterías o varía por referencia?** Se preguntó (513) y no contestó. Único → parámetro de org, S. Varía → campo por material, M con el riesgo de los 3 consumidores acoplados.
2. 🔴 **¿El paso al molino es traslado, transformación, o documento nuevo?** Transformación → ya funciona hoy, el trabajo es UI + estándar. Documento nuevo → módulo desde cero. Y define si el paso al molino se pesa dos veces (hoy no).
3. 🔴 **¿"SA Bogotá" como un solo tercero agregado basta?** (Textual en 1071.) Convierte un XL que no había que tocar en configuración. **Mayor retorno de toda la lista.**
4. 🔴 **¿Bogotá→Barranquilla es traslado, entrada, o los dos?** Dijo las dos cosas (1067 y 1183). Define **dónde nace el flete Willard**.
5. **La tabla de estándares del molino.** Johana la tiene; quedó en pedirse y no consta que se pidiera. **Sin ella T1-con-estándar no se puede construir.**
6. **¿Picadores es bodega o proceso?**
7. **¿El "ajuste mensual del inventario por corte" lo hace el sistema o Johana a mano?** Reporte de desviación (M) vs. motor de ajuste automático (L).
8. **¿Existe deuda en scrap o se convierte todo a plomo?** Hugo dejó la salida barata abierta (*"o lo deja también en plomo"*, 1159). El `KgLedger` es plomo-only por construcción (`models/kg_ledger.py:56-59`).
9. **¿El estado de cuenta puede diferir en centavos de la factura?** Decide si E1 es SAC-only (M) o toca `purchase.liquidate` con golden gate (L).
10. **¿Cuál es la tarifa de flete vigente?** *"justo les cambié la tarifa a principio de mes"* (665). No la dictó.
11. **¿Qué es el "precio del húmedo"?** (815). ¿Referencia de material propia, o modo de precio por kg sobre batería mezclada?
12. **¿Quién parte el peso cuando una línea se reparte entre dos proveedores?** Hoy lo hace a mano (205); no dijo si quiere que el sistema lo haga.
13. **¿PE, "plomo fino", "plomo grueso" y ABS son materiales nuevos o nombres de los que ya existen?** (T2b). Sin esto no se modela la salida del molino.
14. **El estándar del molino, ¿es un piso o un porcentaje por material de salida?** Hugo dice *"espero mínimo el 90%"*, *"la sumatoria es 91"* y también *"no es tan fácil de controlar ese estándar"*. Piso que dispara alerta vs. esperado por cada material contra el que se compara el real: **son dos diseños distintos**.
15. **¿El corte es la unidad de medición o el cierre mensual es la única medición real?** Habla de *"colada colada, bacha bacha"* para planta y *"corte corte"* para el molino, y luego de un *"ajuste mensual"*.
16. **¿El picado es un evento con varias entradas o varios eventos?** Si el picador procesa 3 materiales en un turno y sale un montón de scrap: hoy multi-origen **no existe**.
17. **¿La maquila del crisol ($300/kg) sigue vigente?** Está en los requisitos de julio y la tarifa es configurable, pero Hugo **no la mencionó** en esta reunión — solo habló de la maquila del traslado. ¿Se causa al salir del crisol, o quedó absorbida?
18. **¿La transformación se corrige o se anula?** Con pesos de báscula, un dígito mal tecleado es rutina; hoy solo se puede anular y recrear, cambiando el consecutivo.

### Contradicciones del propio cliente — confirmar por escrito

- **Deuda Willard, ¿nacional o por sede?** *"para Willard él no me discrimina, nacional es nacional"* (771) vs. *"igual la deuda la quiero ver discriminada porque no me puede afectar al balance"* (795), **60 segundos después**. El modelo hoy la obliga por sede (CHECK de BD).
- **Peso, ¿en todas o en algunas?** *"en algunas de las 100 vamos a ponerle algún peso"* (237) vs. *"en todas las entradas debe poner cantidad y peso"* (255). Gana el segundo, pero es la instrucción que rompe las entradas ya capturadas sin peso.
- **El estándar del molino: ¿91 o 90%?** Línea 1129 vs. 1137.

### Cosas que se le dijeron a Hugo y no son así

🔴 **Se le confirmó que Willard tiene revisión, y no la tiene.** Hugo (855-867): *"cuando es Willard pasa por los mismos pasos, ¿verdad? Revisión, liquidación… David, Erwin y tú"*. Respuesta: *"Sí, hace todo, hace el registro, revisión"*. **Willard es `draft → confirmed`** (#81); `reviewed` es **exclusivo del tipo compra** (#93). Se validó en reunión un flujo que no existe: corregirlo o construirlo.

🔴 **"Que sea automático el flete por centro" suena a configuración y es golden gate** (W3).

🔴 **"Que el traslado al molino garantice que lo que salió se recibió" ya no pasa** desde #94, sin que nadie lo pidiera (T3).

---

## 5. Riesgos y tensiones de diseño

### Choques con decisiones ya tomadas

| Hugo / Johana piden | Decisión vigente | Cómo se resuelve |
|---|---|---|
| Balances por sede que no se mezclen | Balance es org-wide en sus 4 componentes (`reports.py:1419-1501`) | Parámetro opcional que, ausente, no cambia una sola query. Aditivo o nada |
| *"le resta el balance de ella y se lo abona a planta"* (Hugo 1103) + *"planta como si fuera un proveedor más"* (Johana 11-ago) | El par de maquila nace con `third_party_id=NULL` **a propósito** (#84) | 🔴 **Ya no es pregunta al cliente — los dos usuarios pidieron lo mismo dos días seguidos.** Un `ThirdParty` normal mete un saldo **intercompañía** en el consolidado (`_classify_third_party`) y **no hay mecanismo de eliminación de intercompañía**. Alternativa honesta: tercero interno excluido del consolidado, visible solo en balance por sede — código nuevo en el clasificador → golden |
| Molino con estándar y ajuste | #84 B1: *"un traslado NUNCA cambia el avg, cero MCH"* | El molino es transformación, no traslado (T0) |
| Peso obligatorio en toda entrada | #17/#76: *avisar, no bloquear* | Warning en captura, bloqueo en liquidación |

### Un eje que nadie evaluó: unidad de negocio

Hugo usó el término literal dos veces: *"no sé qué está pasando con esa **unidad de negocio** en Bogotá"* (713) y *"eso de las drosses debería quedar en la **unidad de negocio** de planta Juan Mina"* (907).

`BusinessUnit` existe (`models/business_unit.py:13`), los materiales cuelgan de ella, hay prorrateo de gastos de 3 niveles y un reporte de rentabilidad completo (#44/#58/#59), y el seeder SAC **ya siembra 4 UNs**. Todo el análisis de sedes modela *sede = warehouse* y nunca compara contra la UN. Diferencia práctica: "P&L por sede: gastos operativos" es M **con golden gate duro sobre `money_movements`**; por UN esa captura y ese prorrateo **ya existen y ya se usan en las 3 orgs cliente**.

No es que la UN sea la respuesta (cuelga del material, no del sitio, y un material vive en varias bodegas) — es que no evaluarla deja un hueco en el ítem más caro del frente.

### Trampas del repo que aplican a este trabajo

- 🔴 **Ningún gate ejecuta una pantalla React y no hay ESLint** (`frontend/` sin config). En #93 dos bloqueantes pasaron verde por `tsc`, build, 1533 tests y golden: hooks tras `return` condicional (pantalla en blanco en **toda** liquidación) y `Decimal` serializado como **string** (`acc + x` → "NaN kg"). **Ambos vivían en `InboundLiquidatePage.tsx`, que es justo el archivo que E1/E2 van a tocar.** Abrir la pantalla es parte de terminar.
- **Relación 1:N (#89/#93 R2):** listados con `EXISTS` o lookup por página, **jamás `outerjoin`** ni `join` no-outer sobre columna nullable.
- **Un solo reloj por evento (#90-#92):** `business_today()`. `RELOJES_PERMITIDOS` está **vacío**.
- **Fecha vs. timestamp (#87):** `BusinessDate` → `formatDate`; `now()` → `formatDateTime`.
- **Precisión de cantidades, ya presente:** `InboundLineAllocation.quantity` es `Numeric(15,4)` y `PurchaseLine.quantity` es `Numeric(10,3)`. El descuadre se calcula con las del **reparto** y al inventario entra la de la **compra** → la identidad "pesado = repartido + descuadre" se rompe hasta 0,0005 kg por asignación, **sin warning**. Con pesos en kg los 4 decimales dejan de ser hipotéticos. Fix barato y SAC-only: cuantizar `a.quantity` a 3 decimales al persistir (`:497`) y al calcular `allocated` (`:338`).
- **Golden gate obligatorio en:** S1, S2, S5, W3, E3-si-toca-el-resolutor, E1-camino-caro, **y T1 si toca la matemática de transformación**. **Y el golden no cubre `/price-lists`, `/third-parties` ni `/inventory/stock`** — para esos, red aparte.
- **Mapa de blast radius, para no equivocarse de gate.** COMPARTIDAS con las 3 orgs cliente: `material_transformations`, `material_transformation_lines`, `inventory_movements`, `materials`, `material_cost_history`, `warehouses`, `money_movements`, `price_lists`, `third_parties`, `purchase_lines`. EXCLUSIVAS SAC (cero filas en orgs cliente, golden no aplica): `furnace_charges`, `crucible_charges`, `kg_ledger_*`, `service_tariffs`, `transfers`, `inbound_orders*`, `material_kg_profiles`, `retention_configs`. **El bloque de horno/crisol es el único grande del backlog con blast radius cero** — buen candidato a arrancar por ahí si hace falta avanzar sin gates pesados.

### El riesgo de proceso, que es el más caro

Si SAC arranca en firme sin **W1**, la deuda de plomo se va a gestionar con el ajuste manual del KgLedger (que está a dos clics). Funciona, queda auditado y es anulable — **y después migrar ese histórico a documentos reales es un proyecto en sí mismo**. Si se acepta el puente, decir explícitamente que los movimientos de ese período **no van a tener trazabilidad a documento**.

---

## 6. Cabos sueltos menores, sin ítem propio

- **Ventas y CxC desde Bogotá** (699, 713): *"allá entrego una parte de esas baterías que las vendo"* y quiere *"a quién se le vendió, qué se recibió, dónde se entregó, las cuentas por cobrar"*. El ciclo de **venta desde Bogotá** no tiene ítem en ningún frente.
- **Medellín como origen Willard** (699): no está en los 5 centros. El autoservicio de #87 lo resuelve, pero el flete tiene que contemplar centros **sin sede propia**.
- **¿Cuándo se calcula el plomo?** Pregunta que estaba abierta y Hugo ya contestó (371): *"desde la entrada del inventario cuando Erwin la hace, pues sería lo ideal"*.
- **Auditoría de traslado** (1035): `created_by`/`received_by` ya se persisten; falta confirmar que se pinten.
- **El vocabulario de Transformaciones sigue siendo el de otra empresa.** El ejemplo canónico en los docstrings es *"Motor 500kg → Cobre + Hierro + Aluminio"* (`models/material_transformation.py:5`) y la pantalla es un formulario genérico "material compuesto → componentes". Si el molino se modela ahí, conviene el mismo tratamiento que se le dio a Entradas en el ciclo C (#82): vocabulario y presentación propios del proceso, aunque la entidad de abajo sea la misma. Eso es exactamente lo que Hugo pidió con *"un módulo para cada proceso… que tengamos ahí la trazabilidad, las eficiencias"*.
