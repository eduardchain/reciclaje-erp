# Plan — Listas de precios por proveedor (ítem 7 del ciclo Entradas)

**v1.2 · GO de QA (14-ago) con 3 correcciones aplicadas** — v1.1 = respuestas de Hugo del 13-ago (2ª llamada); v1.0 = reunión del 12 · SAC (Soluciones Ambientales del Caribe)
**Origen:** reunión 12-ago-2026 con Hugo Bedoya + respuestas telefónicas del 13 (canon `control-cambios-requerimientos.md`, Q-18)
**Decisiones ya cerradas:** D12–D15 en `plan-sac-ciclo-entradas-peso-listas.md`, donde este ítem salió a ciclo propio por ser **el único que toca tablas compartidas con las 3 empresas cliente**.
**Estado del repo:** `develop`, 6 commits locales sin push. El ciclo de Entradas (#95) está construido, con GO de QA, validado en el navegador y commiteado (`dce0ce4`, `77cb396`).

---

## 0. Qué pidió el cliente, y qué se le respondió mal una vez

Hugo, en la reunión: *"cuando yo vaya a liquidarle la compra a ese proveedor, me llame la lista que le corresponde"*. Quiere que cada proveedor tenga su lista, con los precios pre-cargados al liquidar y **opción de cambio manual**.

En la reunión mencionó **tres** listas. Preguntado de frente el 13 (Q-21) corrigió el marco: *"debemos poder crear listas, **las que sean**"*. No es un detalle de cantidad — es la diferencia entre un enum de tres y una tabla. El plan siempre asumió tabla, así que la corrección no cambia el diseño; se anota porque **el "tres" no se puede usar como supuesto en ningún lado**.

Corrigió en vivo el sentido de la asignación: *"es al contrario… digamos que para esta lista son estos, estos y estos proveedores"*.

🔴 **Corrección de procedencia (Q-18b).** "También para clientes" estuvo un rato registrado como respuesta de Hugo y **no lo fue**: fue un supuesto mío que Daniel detectó al releer. En la reunión Hugo habla **solo de proveedores**. Las listas son **solo de compra**.

**Lo que eso ahorra, que es la mitad del ítem:** hay **9 pantallas** que sugieren precio (3 de compras, 3 de ventas, 3 de cruces). Al ser solo de compra, el resolutor toca **4**: las 3 de compras más la liquidación de la Entrada. Ventas y cruces no se enteran, y desaparecen la columna de tipo y la ambigüedad de unicidad.

**El dolor concreto que resuelve**, observado en las pruebas del 13-ago: en la liquidación de la Entrada, el botón "Repartir todo a este proveedor" llena proveedor y cantidad pero deja el precio en 0, y la pantalla marca *"Hay asignaciones incompletas"* en rojo. Daniel lo aceptó con una observación exacta: *"igual cuando tengamos listas de precio por proveedor esto se mitiga"*. Es el mismo problema visto desde el otro lado.

---

## 1. Alcance

| # | Pieza | Tablas | Golden |
|---|---|---|---|
| 1 | Tabla de listas + membresía de proveedores | 2 nuevas | — |
| 2 | Precios por lista | **`price_lists`** (compartida, 1 columna nullable) | 🔴 gate |
| 3 | Resolutor por proveedor (servidor) | — | — |
| 4 | Pantalla de administración de listas | — | — |
| 5 | Las 4 pantallas que consumen el precio | — | — |

**Fuera de alcance, explícito:** listas de venta y de clientes (Q-18b); precios por volumen o por rango de fecha; vigencias futuras programadas; listas por sede.

---

## 2. Decisiones

### D1 — 🔴 Los precios de lista viven en `price_lists` con una FK nullable. `NULL` = la lista general de hoy.

Es la decisión central y es la que hace la no-regresión **demostrable en vez de verificable**. Mismo patrón que `warehouses.sede_warehouse_id` (#94):

> Con la columna en `NULL` en las 3 empresas cliente —que es su estado el día del deploy y para siempre, porque **los endpoints que la escriben están gateados en el BACKEND** por `require_org_flag` (D6): un admin de Costa recibe 403 aunque llegue por API— **cualquier consulta a la que se me olvide poner el filtro sigue devolviendo exactamente las mismas filas que hoy.**

⚠️ Ese paréntesis es lo que hace la premisa **estructural** en vez de operativa, y por eso D6 es una decisión y no un detalle de UI. Ver la corrección de QA allá.

La alternativa (una tabla paralela `price_list_items`) obligaría a auditar a mano cada punto de lectura para probar lo mismo, y además duplicaría tres mecanismos que ya existen y funcionan: el append-only, el "vigente = el más reciente por `created_at`" (#35) y el modal de historial por material.

**Costo aceptado:** las filas de una lista de proveedor llevan `sale_price = 0` sin usar. Es una columna muerta en esas filas, no un dato incorrecto.

### D2 — La membresía va en tabla puente, **no** en `third_parties`.

Dos razones:

1. **`UNIQUE(third_party_id)` en la tabla puente hace cumplir D14 en la base** ("un tercero pertenece a una sola lista", respuesta de Hugo), en vez de confiarlo a una validación de servicio.
2. La membresía queda **revocable con un `DELETE` de fila**, sin tocar el registro del tercero ni su historial de actualización.

🔴 **Corrección (QA, 14-ago). La v1.1 traía acá una tercera razón que era FALSA**: *"`/third-parties` es una de las 15 capturas del golden"*. **No lo es.** `CAPTURES` tiene 14 entradas y ninguna es `/third-parties`; la única llamada a ese endpoint (`golden_capture.py:116`) sirve para **elegir** el tercero del `tp_statement` y su respuesta no se escribe como captura — y como la elección es por saldo e `id`, un campo nuevo en `ThirdPartyResponse` tampoco cambiaría al elegido. O sea que poner la FK en `third_parties` **no habría producido ningún diff de golden**.

La decisión sobrevive porque la razón 1 alcanza sola. Se deja escrito el error, y no se borra en silencio, por dos motivos: **(a)** un hecho falso dentro de un plan aprobado se cita después como precedente (*"no podemos agregar campos a terceros porque el golden"*), y esa creencia costaría decisiones futuras; **(b)** ⚠️ el error **contradice mi propio hallazgo correcto del día anterior** — `plan-cierre-entradas-traslados-transformaciones.md:133` dice, bien, que *"el golden NO cubre esta regresión: `golden_capture.py` no captura `/price-lists` ni `/third-parties`"*. Escribí lo correcto el 12 y lo contrario el 13. Cuando una afirmación sobre el golden aparezca en un plan, **verificarla contra `CAPTURES` en vez de recordarla**.

### D3 — 🔴 **NO hay respaldo. La lista asignada es la única fuente.** (Reemplaza al D13 del plan anterior)

Regla, completa:

1. Proveedor **con** lista → el precio de su lista. Si en esa lista el material está en **cero → no se sugiere nada**.
2. Proveedor **sin** lista → **no se sugiere nada**.

**Por qué cambió, y por qué la versión nueva es mejor.** El plan v1.0 tenía una caída en cascada a la lista general, con este argumento: *"sin el respaldo habría que cargar los 37 materiales en cada lista y no lo van a mantener"*. Ese argumento **descansaba en un supuesto falso mío**: que una lista sería un subconjunto disperso de materiales.

Hugo (Q-21) describió otra cosa: **la lista trae TODOS los materiales registrados y el usuario decide a cuáles les pone precio y cuáles deja en cero.** Con eso, el cero deja de ser un hueco y pasa a ser una **decisión deliberada** — y caer a la lista general para "rellenarlo" sería exactamente pisar esa decisión con un precio que el usuario no eligió.

Preguntado de frente por el proveedor sin lista (Q-22) respondió lo mismo: *"entra a ninguna, el sistema no sugiere precios en este caso"*.

🟢 **Por qué el supersede es sólido (argumento de QA, 14-ago — mejor que el que yo había escrito).** La v1.1 se apoyaba en un criterio de *peso de la evidencia*: "la respuesta directa y posterior vale más que un «de acuerdo» a una propuesta abstracta". Es un juicio sano, pero es un juicio: se cae si Hugo hubiera entendido mal Q-22. **No hace falta.** Las dos respuestas ni siquiera se contradicen una vez corregida la premisa falsa:

1. Q-18(a) aceptó un respaldo **para resolver un problema**: "la lista es un subconjunto disperso, los huecos hay que rellenarlos".
2. Q-21 estableció que la lista trae **todos** los materiales y que el cero es una decisión.
3. **Sin huecos, el respaldo no tiene nada que hacer.**

O sea que Q-22 no está *anulando* a Q-18(a): responde una pregunta que Q-18(a) nunca enfrentó. Eso saca la decisión del terreno de *"cuál respuesta pesa más"* y la pone en el de *"cambió el hecho"* — mucho más difícil de voltear después.

🔴 **El riesgo que D3 introduce, nombrado:** si en la práctica los usuarios **no** llenan todos los materiales, las listas quedan dispersas, la premisa de Q-21 se cae, y el sistema deja de sugerir **en masa y sin que nadie lo note** (un campo vacío no avisa). D3 y Q-26 son el mismo riesgo en dos momentos distintos — por eso la salida de Q-26 lo ejercita a propósito en la primera semana.

**Lo que gana el sistema:** nunca adivina un precio. Un campo vacío es información honesta ("nadie definió esto"); un precio heredado de otra lista es una afirmación que nadie hizo. Y desaparece toda la máquina de cascada, con sus casos borde.

🟢 **Además ya está implementado a medias**: `getSuggestedPrice` devuelve `null` cuando el precio es `<= 0` (`usePriceSuggestions.ts:29`). La semántica "cero = sin sugerencia" **ya existe en el hook**; solo hay que no romperla.

### D10 — 🔴 Sin ninguna lista en la org, el parámetro `third_party_id` es INERTE (agregada durante la construcción, 14-ago)

**No estaba en el plan y sin ella el ítem rompía producción.** Las 3 pantallas de compras que consumen el resolutor son **compartidas con las 3 empresas cliente**. Al cablearlas para que pasen el proveedor, Costa empezaría a llamar `/current?third_party_id=X`; el resolutor no le encontraría lista a ese proveedor y devolvería **cero sugerencias de precio en toda la operación de compras**.

Ningún test lo habría atrapado: todos los del ítem crean listas primero. Lo encontré releyendo el cableado, no corriendo nada.

**Regla:** si la organización no tiene **ninguna lista activa**, el parámetro se ignora y se devuelve la lista general. Con al menos una lista, aplica D3 completo.

Es la semántica correcta, no un parche: *la funcionalidad está apagada hasta que alguien cree su primera lista*. Y es exactamente lo que ya prometía el copy del diálogo de creación — *"Es la primera lista. Desde que exista una, a un proveedor sin lista asignada no se le sugiere ningún precio"*.

Se resuelve en el **backend y no gateando el frontend por flag**, por el mismo argumento de D4: gatear en la pantalla deja la regla escrita en dos lados y el día que cambie se corrige en uno. Acá además el backend puede *demostrarlo* — una org sin listas no puede tener membresías.

### D4 — 🔴 El resolutor vive en el SERVIDOR, en un solo lugar.

`GET /price-lists/current?third_party_id=X` devuelve el mapa ya resuelto. **Por qué no client-side:** la misma resolución tiene que aplicar en las 3 pantallas de compras **y** en la liquidación de la Entrada, que es otro flujo con otro estado. En JS quedaría escrita dos veces, y el día que cambie —esta regla ya cambió una vez en 24 horas, ver D3— se corregiría en una y no en la otra.

Sin el parámetro → `price_list_group_id IS NULL` → **el comportamiento de hoy, byte a byte**. Ese es el seam de no-regresión y es explícito, no accidental.

### D5 — Sin permisos nuevos.

Reusa `materials.view_prices` / `materials.edit_prices`, que ya gobiernan las 7 rutas de precios. Cero migración de permisos, cero wiring de roles, cero cambio en el catálogo.

### D6 — 🔴 El flag `kg_ledger_enabled` se aplica en el BACKEND, no solo en la pantalla.

Los endpoints de grupos, de membresía y el resolutor llevan **`require_org_flag("kg_ledger_enabled")` per-endpoint** (precedente directo: #75/#78 gatearon así los routers SAC — **403 incluso para admins**, porque el flag no lo bypassa el admin). La pantalla gated es consecuencia, no la medida.

**Por qué esto es parte de la decisión y no un detalle de implementación** (corrección de QA, 14-ago): D1 afirma que la columna se queda en `NULL` en las 3 orgs cliente *"para siempre"*, y la v1.1 colgaba ese "para siempre" de que **la pantalla** estuviera escondida. Un enunciado de frontend no sostiene una premisa estructural: sin el gate de backend, un admin de Costa puede llegar por API y escribir un `price_list_group_id`, y en ese instante la premisa de D1 deja de ser cierta y toda la no-regresión demostrable se degrada a verificable. Con el gate, el "para siempre" pasa de promesa operativa a **propiedad del sistema**.

### D7 — La lista general se sigue editando donde se edita hoy.

La pantalla de Precios en modo tabla (#35) sigue operando sobre `price_list_group_id IS NULL`. No se toca. Las listas de proveedor tienen su propia pantalla.

### D8 — Al elegir el proveedor en una asignación de la Entrada, se llena el precio.

Es el pago concreto del ítem. Si el usuario ya escribió un precio, **no se pisa** — misma regla del precio sugerido de #10 (auto-fill solo si el campo está vacío, con hint clickable para restaurar).

---

## 3. Migración

Una sola, aditiva:

- `price_list_groups`: `id`, `organization_id`, `name`, `is_active`, timestamps. `UNIQUE(organization_id, name)`.
- `price_list_group_members`: `id`, `organization_id`, `price_list_group_id` FK, `third_party_id` FK, **`UNIQUE(third_party_id)`** (D2/D14).
- `price_lists.price_list_group_id`: FK nullable a `price_list_groups`, **sin backfill** (todo lo existente queda `NULL` = general) + índice compuesto `(organization_id, price_list_group_id, material_id, created_at DESC)` para que el DISTINCT ON siga barato.

---

## 4. 🔴 El inventario de puntos de lectura — la lista que hay que revisar a los ojos

Toda consulta a `price_lists` que hoy existe asume "hay una sola lista". Cada una necesita el filtro. **Ninguna omisión afecta a las orgs cliente** (todo `NULL`), pero dentro de SAC una omisión mezclaría precios de lista con los generales:

| Sitio | Qué hace | Filtro que necesita |
|---|---|---|
| `price_list.py:63 get_current_price` | precio vigente de un material | `IS NULL` o `= group` |
| `price_list.py:84 get_all_current_prices` | mapa completo (lo que consume el hook) | ídem + **resolutor D3** |
| `price_list.py:101 get_table` | modo hoja de cálculo (#35) | 🔴 param `group_id` **opcional, default `NULL`** — sin él, byte a byte lo de hoy (D7); la pantalla nueva lo pasa y obtiene la hoja de esa lista (D9) |
| `price_list.py:169 get_by_material` | historial por material | `IS NULL` o `= group` |
| `price_list.py:25 create` | alta de precio | recibe el grupo (default `NULL`) |
| `_base_query` heredado de `CRUDBase` | listado genérico (`get_multi`, endpoint `GET ""`) | `IS NULL` por defecto |
| `get_or_404` (endpoint `GET /{price_id}`) | trae **una fila por su PK** | 🟢 **ninguno, y la razón importa**: una fila concreta es una fila concreta — filtrar por grupo acá solo podría esconderla. Se anota para que la ausencia sea una decisión y no un olvido |

**Barrido verificado el 2026-08-14** (no es una lista de memoria): `grep -rn "PriceList\|price_list" app/` confirma que **ningún servicio fuera de `app/services/price_list.py` consulta la tabla** — las demás apariciones son el registro de modelos, los schemas, los endpoints que delegan, y docstrings de tarifas/fórmulas que citan el patrón #35. Los 5 números de línea de arriba coinciden exactamente con los `def`. Esa exclusividad es lo que sostiene el argumento del §7.

**Compromiso para la construcción:** ninguna de estas queda "por defecto sin filtro". El default explícito es `IS NULL`, para que agregar un punto de lectura nuevo mañana herede el comportamiento seguro.

---

## 5. Frontend

**Pantalla nueva** (Config, gated), en dos niveles:

1. **Listas** — crear / renombrar / desactivar. Sin tope de cantidad (Q-21).
2. **Dentro de una lista**, dos zonas:
   - **Precios: hoja de cálculo con los 37 materiales**, exactamente el patrón de #35 (celda editable, Enter/blur guarda, check verde 1,5 s). Trae **todos** los materiales activos, con el precio de esa lista o vacío. El usuario deja en vacío/cero lo que no compra — y ese cero es una decisión que el sistema respeta (D3), no un hueco que rellene.
   - **Proveedores asignados** — la asignación se hace **desde la lista** (D12: *"para esta lista son estos, estos y estos proveedores"*). Un proveedor que ya pertenece a otra lista se muestra **con el nombre de esa lista antes de guardar**, no se rechaza al guardar: la unicidad de D2 es un `UNIQUE` de base, y chocar contra él en el submit sería descubrir el conflicto en el peor momento.

**El hook cambia de firma:** `usePriceSuggestions(supplierId?)`. Las 6 pantallas de ventas y cruces **no pasan nada** y quedan idénticas; las 3 de compras pasan el proveedor y refrescan al cambiarlo (cache de React Query por proveedor).

**Liquidación de la Entrada:** al elegir proveedor en una asignación, se llena el precio con su lista (D8). Es lo que hace que "Repartir todo a este proveedor" deje de terminar en rojo.

---

## 6. Tests

1. Proveedor con lista → su precio, no el general.
2. Proveedor con lista y material **en cero** → **sin sugerencia** (D3: el cero es deliberado, NO cae al general).
3. Proveedor **sin** lista → **sin sugerencia** (D3/Q-22).
4. 🔴 **Ninguno de los dos casos anteriores devuelve $0 como precio** — devuelven ausencia. Un $0 sugerido sería un precio afirmado que nadie eligió.
5. **Sin `third_party_id` el endpoint devuelve exactamente lo de hoy** (guardrail de no-regresión, el más importante).
6. Un tercero en dos listas → rechazado por la base (D2).
7. El modo tabla (#35) **sin `group_id`** no ve precios de lista; **con `group_id`** trae **todos los materiales activos** (con precio o vacíos) y solo los precios de esa lista.
8. El historial por material separa general de lista.
9. Append-only por lista: el vigente es el más reciente **dentro de su lista**.
10. RBAC: `materials.edit_prices` para administrar listas.
11. Liquidación de Entrada: el reparto nace con el precio del proveedor.

## 7. Gates

- Suite completa.
- Parity check.
- **Golden ×3 orgs.** Con una honestidad sobre qué protege: **ninguna de las 16 capturas por org lee `price_lists`** (lo verifiqué: el único acoplamiento del modelo fuera de su servicio son referencias en docstrings de tarifas y fórmulas). O sea, el golden acá es **cinturón sobre tirantes** — la protección real es el `NULL` de D1. Se corre igual porque la regla es "toca tabla compartida, el golden es gate", y porque el costo de correrlo es bajo comparado con el de equivocarme sobre qué lee qué.
- **Abrir las pantallas.** Después del ciclo de Entradas esto deja de ser una recomendación: cinco defectos pasaron todos los gates automáticos y aparecieron en el recorrido guiado (§8b del informe de #95).

## 8. Respuestas del cliente (2ª llamada, 13-ago) y lo único que queda abierto

| Pregunta | Respuesta | Efecto en el plan |
|---|---|---|
| ¿Cuántas listas y con qué materiales? | **Las que sean.** Cada lista trae **todos** los materiales; el usuario decide a cuáles les pone precio y cuáles deja en cero | 🔴 **Reescribe D3**: el cero es deliberado → no hay respaldo |
| ¿Proveedor nuevo? | **A ninguna lista, y sin sugerencia** | 🔴 Supersede Q-18(a) |
| ¿Quién administra? | **El administrador del sistema** | ✅ D5 sin cambios |
| ¿Precio editable al liquidar? | **Editable** | ✅ D8 sin cambios |
| ¿Cada cuánto cambian? | **Cada 3 meses** | ✅ Confirma la pantalla tipo hoja de cálculo — ver D9 |

### D9 — La pantalla es una hoja de cálculo por lista, y la razón NO es la frecuencia.

Cada 3 meses suena a "poco", y la conclusión ingenua sería que alcanza con editar fila por fila. Es al revés: como la lista trae **los 37 materiales** (Q-21), cada actualización trimestral es una sesión que toca **muchas filas de una sentada**. Lo que manda es el **ancho** de la sesión, no su frecuencia.

🟢 Ese patrón ya existe y está probado: el modo tabla de precios (#35) — celda editable, Enter/blur guarda, check verde 1,5 s. Se reusa por lista.

### 🟠 Q-26 — no es la transición: es la **configuración del día uno**, y entra al ciclo

Q-22 dice que sin lista no hay sugerencia. Aplicado tal cual, **el día que esto se encienda todos los proveedores de SAC pierden el precio sugerido**: hoy compran contra la lista general y mañana no tendrían nada. El síntoma sería un campo vacío — fácil de leer como *"el sistema se dañó"*.

🔴 **Reencuadre de QA (14-ago), y es correcto:** la v1.1 lo llamaba *"decisión de operación, no de diseño"* y lo mandaba al deploy. No es una arruga de transición — **con D3, «ningún proveedor tiene lista» ES el estado por defecto del día uno**. Y decide si hay que sembrar, que es **trabajo de este ciclo**, no del deploy.

**Salida recomendada (a):** al desplegar, sembrar **una** lista con todos los materiales a los precios generales vigentes y asignarle **todos** los proveedores actuales. Tres beneficios:

1. El día uno se comporta **igual que hoy** — cero sorpresa para Johana.
2. Mover un proveedor a su lista propia pasa a ser una **edición**, no una carga desde cero.
3. 🟢 El mejor: **ejercita la premisa de Q-21 de inmediato.** Si el modelo "todos los materiales, con ceros deliberados" no se sostiene en la práctica, se ve en la **primera semana** y no seis meses después. Es el mitigante directo del riesgo nombrado en D3.

La alternativa (b) —cargar y asignar todas las listas definitivas antes de encender— deja el mismo resultado pero exige que Hugo tenga las listas listas antes del deploy, y no ejercita nada temprano.

**Pendiente de confirmación de Daniel**, porque agrega el sembrado al alcance del ciclo.

### Nota de coherencia para SAC (no bloquea)

Cuando todos los proveedores estén asignados, la **lista general deja de leerse en SAC** — pero la pantalla de Precios en modo tabla la seguiría editando (D7). Queda una pantalla que edita datos que nadie consume. No rompe nada y para las 3 empresas cliente esa pantalla es la única que importa, así que **no se toca en este ciclo**; se anota por si más adelante conviene que en SAC esa entrada lleve directo a las listas.
