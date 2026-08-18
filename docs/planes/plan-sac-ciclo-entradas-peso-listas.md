# Plan — Ciclo Entradas: peso, liquidación por total, revisión Willard y listas de precios

**v1.1 · QA: GO condicionado** · SAC (Soluciones Ambientales del Caribe)
**Origen:** reunión 12-ago-2026 con Hugo Bedoya (dueño) + respuestas suyas por teléfono el 13-ago (registradas en `control-cambios-requerimientos.md`, CC-008 y Q-13…Q-20)
**Análisis previo:** `docs/planes/plan-cierre-entradas-traslados-transformaciones.md` (commit `0983d64`), bloque **E · DECISIONES CERRADAS**
> **Construido.** Ítems 1–5 + D17 están implementados y verificados; el ítem 7 sale a ciclo propio. Lo que se construyó, las desviaciones y los gates están en **`docs/planes/informe-code-ciclo-entradas.md`** — este plan queda como el diseño, no como el estado.

**Estado del repo:** `develop`, 4 commits locales sin push (3 con GO previo de QA + el plan de cierre). Sin commitear: el fix del mensaje de retenciones en `InboundLiquidatePage.tsx`, que va en esta misma ronda de QA.

## Corrección de v1.0 — #93 y #94 no están desplegados, y eso NO es un problema

**Hecho verificado:** `origin/develop` está en `2d786f0` y el último tag es `deploy-2026-08-06-1340`, ambos **anteriores** a #93 (`git merge-base --is-ancestor 7a9dff2 deploy-2026-08-06-1340` → falso). `purchases.review` nace en la migración `b8c9d0e1f2a3`, que vive solo en el commit `7a9dff2`, así que **el permiso no existe en la base de producción**.

**Encuadre correcto (Daniel, 13-ago):** el cierre funcional con SAC se hace **contra localhost**; están lejos de la puesta en marcha de estos módulos. Primero se cierra funcionalmente con el cliente y después se sube. **El deploy no es el camino crítico y no bloquea nada de este plan.**

Dos consecuencias, entonces:

1. **El ítem 1 no estaba bloqueado — lo estaba solo en producción, que no es donde David tiene que existir ahora.** Se resuelve **agregándolo al sembrado** (`scripts/seed_sac_org.py`), que es código: aparece en local para las demos, y en producción entra solo cuando se despliegue, por la provisión idempotente. Sin acción manual contra prod y sin clave fija suelta. **Vuelve al ciclo.**
2. **El estado `reviewed` nunca ha existido para un usuario real.** v1.0 argumentaba dos veces contra volver a `draft` porque "cambiaría el comportamiento actual de #93, que ya está en producción". Ese argumento **es falso** y no debe pesar (lo confirmó QA en F2): la decisión se toma por diseño, no por conservadurismo.

---

## 0. Alcance

Siete ítems, en orden de construcción. **Los ítems 1–5 tocan solo tablas exclusivas de SAC** (o nada): sin golden gate. El **ítem 7 toca tablas compartidas con las 3 orgs cliente** y es el único con riesgo de regresión hacia afuera.

| # | Ítem | Backend | Migración | Golden | Estado tras QA |
|---|---|---|---|---|---|
| 1 | Personas y permisos | sembrado | — | — | ✅ **HECHO** — David agregado a `seed_sac_org.py` con `revisor_inventario` |
| 2 | Botón "un solo proveedor" | **cero** | — | — | ✅ GO sin condiciones — se arranca por acá |
| 3 | Peso obligatorio al revisar | sí | — | — | ✅ GO |
| 4 | Willard pasa por revisión | sí | — | — | ✅ GO |
| 5 | Liquidar escribiendo el total | sí | 1 (SAC-only) | — | ✅ GO, **+ la cuantización a 3 decimales entra acá** |
| 6 | % de plomo por material | sí | 1 (SAC-only) | — | ❌ **FUERA** — se construye con su consumidor (el informe). La *pregunta* a Hugo sigue viva |
| 7 | Listas de precios por tercero | sí | 1 (**compartida**) | 🔴 **sí** | ✅ GO, **sin el candado de unicidad** hasta que Hugo conteste Q-20 |

**Fuera de alcance, explícito:** el "precio del húmedo" como modo de precio $/kg (Hugo confirmó que Johana digita el **valor total**, no un precio por kilo — el húmedo es cómo ella decide ese total, fuera del sistema); el reparto de un lote mezclado entre referencias (Erwin **pesa por referencia**, así que no hay lote que repartir); comisiones y fletes en la Entrada (diferidos por Daniel desde #93); los informes de peso promedio y costo por tonelada (ciclo propio).

---

## 1. Decisiones

**D1 — El peso es opcional al capturar y obligatorio al REVISAR.** Decisión de Hugo, y es mejor que la propuesta original (bloquear al liquidar): el revisor es exactamente quien certifica las cantidades pesadas, y el pesador —el eslabón apurado— no queda trabado. La validación vive en **un solo punto**, `review()`.

**D2 — Si el material ya se mide en kg, el peso se autocompleta con la cantidad.** Pedir los dos sería fricción pura. Se resuelve en `review()` (servidor), no solo en la pantalla, para que el dato quede persistido y no dependa de por dónde entró.

**D3 — Willard pasa por revisión.** Queda `draft → reviewed → confirmed`. 🟢 **`display_status_of` y el espejo SQL NO se tocan**: desde #93 el estado es columna y `reviewed` se mapea genéricamente sin mirar el tipo (`services/inbound_order.py:1690-1701` y `:1536-1547`). El test de paridad `test_filter_parity_with_field` sigue verde por construcción.

**D4 — El peso obligatorio aplica también a Willard**, que es consecuencia de D1+D3 y **no es carga extra**: es justo el dato que habilita el informe de peso promedio por referencia, la carta con la que Hugo va a renegociar el 5,2 kg/unidad con Willard (*"voy a Willard y le digo: el promedio de la 07 es 11 y tu batería me está dando nueve"*).

**D5 — Al liquidar, Johana digita el VALOR TOTAL de la asignación**; el unitario sale de `total / cantidad`. Confirmado por Hugo en la reunión: *"el precio unitario sería una fórmula, costo total dividido unidades"*. 🟢 **El peso NO participa en el cálculo del precio** — ella lo mira para decidir, el sistema no computa desde él.

**D6 — El total va por ASIGNACIÓN (proveedor), no por línea.** Con reparto multi-proveedor una línea puede tener N asignaciones y cada proveedor negocia su precio.

**D7 — El total digitado se PERSISTE** (columna nueva en `inbound_line_allocations`, SAC-only). Sin persistirlo, des-liquidar y re-liquidar (#93 D20 conserva el reparto) obligaría a re-digitar y el modo se perdería en silencio.

**D8 — El centavo del redondeo se acepta, pero se muestra.** $200.000 ÷ 3 = 66.666,67 → el total vuelve como $200.000,01. La pantalla muestra **el total resultante** antes de guardar, así nunca es una sorpresa contra la factura. Hacerlo exacto obligaría a persistir un total en `purchase_lines`, tabla compartida, por un centavo.

**D9 — El precio derivado se cuantiza igual que la firma de re-liquidación** (`PRICE_Q = 0.01`, `services/inbound_order.py:303,527,533`). Sin esto, cada re-liquidación vería una firma distinta y dispararía un revert-and-reapply innecesario.

**D10 — El % de plomo vive por material y se hereda de un valor de organización.** El campo por material nace **NULL = usa el de la org**. Patrón ya usado dos veces en el repo (#59 `double_entry_general_pct`, #71 `pnl_section`): herencia en LECTURA, no copia al crear. Copiar 53 en 37 filas lo congela y "cambiarlo para todas" se vuelve trabajo manual.

**D11 — 🔴 El plomo de compra regular NO genera `KgLedgerMovement`.** Las cuentas en kg son deuda con Willard; el plomo de una compra es material propio. Hugo lo separó él mismo (*"son dos temas"*). Si entra al libro, se inventa un pasivo.

**D12 — Los terceros se asignan DESDE la lista, no la lista desde el tercero.** Hugo corrigió esto en vivo: *"es al contrario… digamos que para esta lista son estos, estos y estos proveedores"*. La pantalla de asignación vive en la lista.

**D13 — Tercero sin lista → lista general de hoy, que además es el RESPALDO** cuando su lista no tiene precio cargado para un material. Sin el respaldo habría que cargar los 37 materiales en cada lista y no lo mantendrían. Y es lo que deja el comportamiento **byte a byte** para las otras 3 empresas.

**D14 — Un tercero pertenece a una sola lista** (unicidad en la tabla puente). Respuesta de Hugo.

**D15 — Las listas son SOLO DE COMPRA. Sin tipo, sin clientes.** 🔴 Corrección de procedencia (13-ago): "también para clientes" se registró un rato como respuesta de Hugo y **no lo fue** — fue un supuesto, detectado por Daniel al releer. En la reunión Hugo habla solo de proveedores: *"cuando yo vaya a liquidarle la compra a ese proveedor, me llame la lista que le corresponde"*.

**Lo que esto ahorra, que es mucho para el ítem más riesgoso:** el resolutor deja de tocar las 6 pantallas de ventas y cruces — solo las 3 de compras más la liquidación de la Entrada. Y desaparecen el tipo, la ambigüedad de unicidad y Q-20 entera. Si más adelante piden listas de venta, se agrega una columna de tipo con default `compra`: migración aditiva sobre una tabla que para entonces será solo de SAC.

**D16 — Erwin captura, David revisa, Johana liquida.** ⚠️ La grabación afirma lo contrario, y lo hace completo (línea 1075: *"David, que es el de recepción, confirmó; Erwin revisó"*); mandó la confirmación de Hugo por teléfono. **Registrado como canon en `control-cambios-requerimientos.md` Q-19** — sin ese registro, una relectura futura del transcript "corregiría" los roles al revés con toda la razón aparente.

**D17 — Editar una entrada revisada: las LÍNEAS la devuelven a `draft`; la CABECERA no.** La respuesta no es binaria, y el modelo ya trae la distinción: el set bloqueado de #93 D7b es `{lines, date, willard_distribution_center}` — o sea, **las líneas ya son el contenido certificable**. La revisión certifica pesos y cantidades, que son líneas; cambiar la factura, la nota o el vehículo no toca lo que David certificó. Eso cierra el hueco (certificar y después cambiar cantidades sin re-certificar) sin cobrarle fricción a lo que no la merece. 🟢 Y **no hay comportamiento en producción que preservar**: `reviewed` nunca existió para un usuario real.

---

## 2. Los siete ítems

### Ítem 1 · Personas y permisos. ✅ **Hecho, vía sembrado.**

**David agregado a `USERS` en `scripts/seed_sac_org.py` con el rol `revisor_inventario`.** El rol ya existía y ya se creaba (`:88-95`, `:493-500`) — faltaba únicamente el usuario. Erwin conserva `bascula_sac`.

**Por qué por el sembrado y no por la API contra producción:** así aparece en local para el cierre funcional con el cliente, y en producción entra solo cuando se despliegue, por la provisión idempotente — sin acción manual y sin dejar suelto un usuario con la clave fija. En dev las claves se fuerzan por ORM (`_force_known_passwords`); en prod, cuando llegue, se resetea con #85.

⚠️ Contra producción, hoy, el sembrado **fallaría** al crear el rol: `REVISOR_ROLE.permission_codes` incluye `purchases.review`, que solo existe a partir de la migración de #93. Es una razón más para no tocar prod hasta el deploy.

Hoy el estado `reviewed` está construido, con permiso (`purchases.review`, sort 148) y rol (`REVISOR_ROLE` en `scripts/seed_sac_org.py:88-95`, creado en `:493-500`) — **y ningún usuario lo tiene asignado**. El comentario del propio seeder lo anticipó: *"sin nadie con purchases.review, 'revisada' frenaría la operación"*.

- Crear **David** (`david@sac.com`) con `revisor_inventario`.
- **Erwin conserva `bascula_sac`** (captura).
- Los 3 admins ya pueden revisar, pero por bypass (`deps.py:227`), no porque el flujo esté armado.

🔴 **Es un cambio en producción** (SAC está en vivo desde el 2026-08-04) y **el usuario nace con la clave fija** — hay que resetearla apenas entre, con el mecanismo de #85. Es la deuda del reseteo-a-constante ya identificada.

### Ítem 2 · Botón "un solo proveedor". **100% frontend. Cero backend, cero migración.**

🟢 El backend ya lo soporta sin tocar nada: el reparto se agrupa por proveedor (`services/inbound_order.py:504-507`) y de N líneas con el mismo tercero nace **una** compra (`:538-590`).

Hugo pidió más de lo que suena (*"No le carga las cantidades al llamar el proveedor de lo que tenga pendiente"*): el botón debe **pre-llenar el reparto con lo pendiente**, no solo fijar el tercero.

**Trampas:**
- Líneas con `quantity=0` (el schema usa `ge=0`, `schemas/inbound_order.py:36`): un toggle ingenuo las deja "sin asignaciones" y `lineProblems` (`InboundLiquidatePage.tsx:510-512`) bloquea.
- 🔴 Es el archivo con el peor historial del repo — ver §5.

### Ítem 3 · Peso obligatorio al revisar.

Hoy: `scale_weight_kg: Optional[Decimal] = Field(None, gt=0)` (`schemas/inbound_order.py:40`). **No se vuelve obligatorio en el schema de captura** (D1) — la validación se agrega en `review()`: toda línea debe tener peso > 0, salvo D2.

**Trampas verificadas:**
- 🔴 **El frontend convierte 0 → `null` antes de enviar** (`InboundCreatePage.tsx:368`, `InboundEditPage.tsx:66`) con estado inicial 0 (`create:67`): hoy dejar el campo vacío **se descarta en silencio**. Si no se toca, el pesador creerá que puso peso y la revisión lo rebotará sin que él entienda por qué.
- **Entradas SAC ya capturadas sin peso** quedan sin poder revisarse. El camino de salida existe —`update()` permite editar líneas en `draft`/`reviewed` para tipo compra— pero hay que confirmarlo con datos reales antes de deployar.
- Las líneas de truncamiento D16 de #93 nacen **al liquidar** con `quantity=0` (`services/inbound_order.py:464-469`): son posteriores a la revisión, no la afectan.

### Ítem 4 · Willard pasa por revisión.

- `review()` (`services/inbound_order.py`): **quitar el guard** `if order.inbound_type in WILLARD_INBOUND_TYPES: raise "Una recepcion Willard no se revisa — se confirma"`.
- `confirm()`: exigir `status == "reviewed"` en vez de `"draft"`, con mensaje que guíe (*"revísela primero"*).
- Frontend: botón Revisar visible para Willard; badge y bandeja ya funcionan sin cambios.
- 🟢 `display_status_of` y el espejo SQL **no se tocan** (D3).

✅ **Resuelto por D17:** hoy editar una entrada ya revisada **la deja revisada** (`update()` permite líneas en `draft`/`reviewed`), lo que permitiría certificar y después cambiar las cantidades sin re-certificar. Se cierra distinguiendo: **editar líneas devuelve a `draft`; editar cabecera no**. Aplica a los dos tipos.

### Ítem 5 · Liquidar escribiendo el total de la asignación.

- Columna nueva `total_price` **nullable** en `inbound_line_allocations` (hoy: `quantity` `Numeric(15,4)`, `unit_price` `Numeric(15,2)`, `invoice_number`). NULL = se digitó el unitario, comportamiento actual.
- Al liquidar: si viene `total_price`, `unit_price = quantize(total_price / quantity, PRICE_Q)` **antes** de armar el `PurchaseCreate` (D9). El resto del camino de #93 no se entera.
- 🟢 **El motor de costo no se entera**: `incorporate_into_pool` (`services/inventory_costing.py:37-70`) consume un costo unitario escalar. Modelo L (#64-#66) intacto.
- Frontend: conmutador por asignación "precio unitario / valor total", y **el total resultante visible** antes de guardar (D8).

**Trampa de precisión, ya presente y ahora más visible — ✅ ENTRA en este ciclo (QA).** `InboundLineAllocation.quantity` es `Numeric(15,4)` (`models/inbound_order.py:255`) y `PurchaseLine.quantity` es `Numeric(10,3)` (`models/purchase.py:309`). El descuadre se calcula con las del reparto (`services/inbound_order.py:336-339`) y al inventario entra la de la compra → la identidad "pesado = repartido + descuadre" se rompe hasta 0,0005 kg por asignación, **sin warning**. Fix: cuantizar a 3 decimales al persistir (`:497`) y al calcular `allocated` (`:338`).

**Razón de QA para no separarlo, que es mejor que la mía:** el ítem 5 **se apoya más fuerte en esa identidad**, así que hacerlo aparte sería construir encima de un invariante que ya se sabe roto. Es SAC-only, no necesita golden, y el test que lo cubre ya está en §4.

### Ítem 6 · % de plomo por material. ❌ **FUERA del ciclo (QA aceptó la objeción).**

**El código se difiere al ciclo del informe, que es donde nace su consumidor. La pregunta a Hugo NO se difiere** — preguntar es gratis, construir no, y la respuesta define el esquema de ese informe. Ver Q-17 en el canon: en el transcript Hugo lo llamó *"Promedio"* (541), lo cual inclina a parámetro único pero no lo resuelve, y cuando se le preguntó de frente (513) cambió de tema.

Lo que sigue queda como diseño listo para ese ciclo.

- Columna `lead_percentage` **nullable** en `material_kg_profiles` (SAC-only).
- Clave nueva en `SETTING_DEFAULTS` (`app/utils/org_settings.py`), ej. `lead_percentage_default: 53.0`.
- Lectura con herencia: NULL → valor de la org (D10). Escritura por la pantalla Materiales (kg), que ya existe.
- 🔴 D11: no genera `KgLedgerMovement`.

🔴 **Objeción propia, para que QA la juzgue:** en este ciclo **nadie lo lee**. Sus dos consumidores son informes que no están en el alcance (costo por tonelada; y el peso teórico dejó de hacer falta cuando Hugo confirmó que pesan por referencia). Construir un campo configurable que no produce ningún efecto es exactamente el patrón que critiqué en el análisis con `maquila_crisol` — una tarifa que el usuario puede cargar, ver en pantalla, y que no genera ningún asiento nunca. **Mi recomendación es moverlo al ciclo del informe**, que es donde nace su consumidor. Lo dejo en el plan porque Daniel lo pidió explícitamente.

### Ítem 7 · Listas de precios por tercero. **El grande. Ciclo propio.**

Hoy `price_lists` es `(material_id, purchase_price, sale_price, notes, updated_by)` — sin dimensión de lista ni de tercero (`models/price_list.py:35-62`) — y "vigente" es el registro más reciente **por material para toda la organización** (`services/price_list.py:75-99`).

**Forma:**
- Tabla nueva **`price_list_definitions`** (org, nombre, tipo `compra|venta`, `is_active`) — vacía para las otras empresas.
- **`price_lists.price_list_id` nullable**: NULL = la lista general de hoy → todo lo existente **byte a byte**.
- Tabla puente **`price_list_members`** (`price_list_id`, `third_party_id`), unicidad por `(third_party_id, tipo de la lista)` (D14+D15). **`third_parties` no se toca.**
- Resolutor: precio del material M para el tercero T = último registro en la lista de T; si no hay, **respaldo a la lista general** (D13). Sin `third_party_id` → comportamiento actual exacto.
- Cablear el sugeridor en `InboundLiquidatePage`, que **hoy no consume listas de precios en absoluto**. El patrón de hint restaurable ya vive tres veces en ese archivo (comisión `:824-838`, retenciones `:967-973`): es replicar, no traer.

🔴 **Riesgo hacia afuera.** `price_lists` y `third_parties` son compartidas, y el resolutor alimenta **9 pantallas** de compras, ventas y cruces de las 4 empresas (`usePriceSuggestions` en `PurchaseCreate/Edit/Liquidate`, `SaleCreate/Edit/Liquidate`, `DoubleEntryCreate/Edit/Liquidate`).

🔴 **Y el golden no cubre esta regresión**: `golden_capture.py:24-46` captura reportes, cuentas, bodegas y movimientos — **no captura `/price-lists` ni `/third-parties`**. La red hay que armarla aparte (ver §5).

---

## 3. Migraciones

| Ítem | Migración | Tabla | Compartida |
|---|---|---|---|
| 5 | `inbound_line_allocations.total_price` nullable | SAC-only | no |
| 6 | `material_kg_profiles.lead_percentage` nullable | SAC-only | no |
| 7 | `price_list_definitions` + `price_list_members` (nuevas) + `price_lists.price_list_id` nullable | **`price_lists` compartida** | 🔴 sí |

Todas aditivas y nullable: sin backfill, sin cambio de comportamiento para datos existentes.
⚠️ IDs de revisión hechos a mano: `grep` del ID antes de crear — un ID repetido da *"Cycle is detected"*, no *"duplicate revision"* (lección de #94).

---

## 4. Tests

**Ítem 3 — peso al revisar**
- Revisar con una línea sin peso → error; el mensaje nombra el material.
- Revisar con todas las líneas pesadas → 200 y `reviewed`.
- Material en kg sin peso → se autocompleta con la cantidad y la revisión pasa (D2).
- Entrada legacy sin peso: editarla para agregarlo y luego revisar.

**Ítem 4 — revisión Willard**
- Willard: `draft → review → confirm` completo, con los efectos (inventario, kg, MCH) **idénticos** al camino de dos pasos previo. **Test estrella: byte a byte contra el resultado de hoy** — la revisión no puede cambiar ningún efecto.
- `confirm()` sobre una Willard en `draft` → error que guía a revisar.
- Peso obligatorio también en Willard.
- Paridad de `display_status` (el test existente debe seguir verde **sin tocarlo**).

**Ítem 5 — total por asignación**
- Total 200.000 / 3 unidades → `unit_price` 66.666,67, total de la compra 200.000,01, saldo del proveedor coherente.
- Mezcla: una asignación por unitario y otra por total en la misma entrada.
- **Des-liquidar y re-liquidar sin tocar nada → mismos números y SIN revert-and-reapply** (D7+D9). Es el test que atrapa la firma mal cuantizada.
- Retenciones sobre un total derivado (el tope es el subtotal, `services/purchase.py:1606-1614`).
- Cuantización a 3 decimales: la identidad "pesado = repartido + descuadre" cierra exacto.

**Ítem 6 — % de plomo**
- NULL hereda el de la org; con valor propio, gana el del material; cambiar el de la org mueve a todos los que heredan.
- 🔴 **Test guardián de D11: liquidar una compra regular de una batería con % NO crea ningún `KgLedgerMovement`.**

**Ítem 7 — listas**
- Tercero sin lista → precio idéntico al de hoy (**no-regresión**).
- Tercero con lista → su precio; material sin precio en su lista → respaldo a la general.
- Un tercero no puede estar en dos listas del mismo tipo; sí en una de compra y una de venta.
- Lista inactiva → se comporta como sin lista.

**Stress walk:** extender con revisión de Willard y con liquidación por total.

---

## 5. Gates

1. **Suite completa** (hoy 1571). ⚠️ Un solo dueño del puerto 5433 a la vez: no correr el parity check con pytest en curso, y **no editar código backend con la suite corriendo**.
2. **Parity check** (`scripts/schema_parity_check.py`) — debe dar **DIFF CERO**. El normalizador de CHECKs de #94 ya está y tiene su test propio.
3. **Golden ×3 orgs** — **obligatorio solo para el ítem 7**. Los ítems 1–6 tocan tablas exclusivas de SAC con router flag-gated: cero filas en Costa, Biogreen y Metarecycling.
4. 🔴 **Red propia para el ítem 7**, porque el golden no captura listas de precios ni terceros: un test de paridad del resolutor (sin tercero → resultado idéntico al actual) **más** las 9 pantallas leídas a mano.
5. 🔴 **Abrir las pantallas.** Ningún gate ejecuta una pantalla React y `frontend/` **no tiene configuración de ESLint** (`npm run lint` no corre). En #93 dos bloqueantes pasaron `tsc`, build, 1533 tests y golden: hooks declarados tras un `return` condicional (pantalla en blanco en **toda** liquidación) y `Decimal` serializado como **string** (`acc + x` concatena → "NaN kg"). **Ambos vivían en `InboundLiquidatePage.tsx`, que es el archivo que los ítems 2, 5 y 7 van a tocar.** Montar ESLint con `react-hooks/rules-of-hooks` sigue siendo ciclo propio pendiente.

---

## 6. Dictámenes de QA sobre las preguntas de v1.0

| # | Pregunta de v1.0 | Dictamen |
|---|---|---|
| 1 | ¿El ítem 6 ahora o con su consumidor? | **Con su consumidor.** La objeción propia gana; el paralelo con `maquila_crisol` es exacto — un campo que el usuario carga, ve en pantalla y no produce ningún efecto **es peor que no tenerlo, porque genera expectativa**. Pero se difiere el *código*, no la *pregunta*: preguntarle a Hugo si el 53% es uniforme sigue en pie (Q-17) |
| 2 | ¿Editar una revisada vuelve a `draft`? | **Sí, pero no todo** → D17: líneas sí, cabecera no. Y el argumento conservador de v1.0 era falso: **#93 no está en producción** |
| 3 | ¿Persistir el total (D7)? | **Sí**, con una razón más dura que la de v1.0: la promesa de #93 D20 es que **el reparto sobrevive el round-trip**. Un modo de captura que no sobrevive es un reparto que en realidad no se conservó — el operador vuelve y ve otra cosa de la que guardó |
| 4 | ¿Listas tipadas (D15)? | **La columna sí, el candado no** → D15 enmendada. Des-tipar después es más difícil que tipar después; la unicidad espera Q-20 |
| 5 | ¿La cuantización entra acá? | **Acá.** El ítem 5 se apoya más fuerte en la identidad "pesado = repartido + descuadre"; separarlo sería construir sobre un invariante ya roto |
| 6 | ¿Falta algo del transcript? | El barrido del transcript ya estaba hecho. **Lo que faltaba era de proceso:** las respuestas telefónicas del 13-ago no vivían en ningún archivo, y **Q-19 invierte lo que la grabación dice** — sin registro, una relectura futura "corregiría" los roles al revés. ✅ Escritas en `control-cambios-requerimientos.md` (CC-008, Q-13…Q-20) |

## 7. Lo que sigue abierto

**Ninguna pregunta al cliente queda pendiente** — las dos que había se cerraron el 13-ago:

- **Q-17 (el 53%) · cerrada por diseño.** El modelo es parámetro por defecto de la organización con sobreescritura por material, así que sirve igual si es uniforme o si varía. Lo único que cambia según la realidad es quién carga los números por referencia: captura de datos, no esquema.
- **Q-20 (lista compartida proveedor/cliente) · sin objeto.** Nació de un supuesto que no era del cliente; sin clientes en alcance no hay tipo que definir.

Queda pendiente **el deploy de #93 + #94** — pero **no bloquea nada de este plan**: el cierre funcional con SAC se hace contra localhost y están lejos de la puesta en marcha de estos módulos. Se sube cuando el módulo esté cerrado con el cliente.
