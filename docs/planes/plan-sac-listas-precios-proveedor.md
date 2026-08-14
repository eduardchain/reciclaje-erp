# Plan — Listas de precios por proveedor (ítem 7 del ciclo Entradas)

**v1.1 · para QA** (v1.0 corregida con las respuestas de Hugo del 13-ago, 2ª llamada) · SAC (Soluciones Ambientales del Caribe)
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

> Con la columna en `NULL` en las 3 empresas cliente —que es su estado el día del deploy y para siempre, porque la pantalla de listas está detrás del flag SAC— **cualquier consulta a la que se me olvide poner el filtro sigue devolviendo exactamente las mismas filas que hoy.**

La alternativa (una tabla paralela `price_list_items`) obligaría a auditar a mano cada punto de lectura para probar lo mismo, y además duplicaría tres mecanismos que ya existen y funcionan: el append-only, el "vigente = el más reciente por `created_at`" (#35) y el modal de historial por material.

**Costo aceptado:** las filas de una lista de proveedor llevan `sale_price = 0` sin usar. Es una columna muerta en esas filas, no un dato incorrecto.

### D2 — La membresía va en tabla puente, **no** en `third_parties`.

Dos razones, y la segunda es dura:

1. **`UNIQUE(third_party_id)` en la tabla puente hace cumplir D14 en la base** ("un tercero pertenece a una sola lista", respuesta de Hugo), en vez de confiarlo a una validación de servicio.
2. 🔴 **`/third-parties` ES una de las 15 capturas del golden.** Poner la FK en el tercero obligaría a exponerla en `ThirdPartyResponse` y el golden vería una llave nueva en las 3 orgs cliente. Con la tabla puente, esa respuesta no cambia en un byte.

### D3 — 🔴 **NO hay respaldo. La lista asignada es la única fuente.** (Reemplaza al D13 del plan anterior)

Regla, completa:

1. Proveedor **con** lista → el precio de su lista. Si en esa lista el material está en **cero → no se sugiere nada**.
2. Proveedor **sin** lista → **no se sugiere nada**.

**Por qué cambió, y por qué la versión nueva es mejor.** El plan v1.0 tenía una caída en cascada a la lista general, con este argumento: *"sin el respaldo habría que cargar los 37 materiales en cada lista y no lo van a mantener"*. Ese argumento **descansaba en un supuesto falso mío**: que una lista sería un subconjunto disperso de materiales.

Hugo (Q-21) describió otra cosa: **la lista trae TODOS los materiales registrados y el usuario decide a cuáles les pone precio y cuáles deja en cero.** Con eso, el cero deja de ser un hueco y pasa a ser una **decisión deliberada** — y caer a la lista general para "rellenarlo" sería exactamente pisar esa decisión con un precio que el usuario no eligió.

Preguntado de frente por el proveedor sin lista (Q-22) respondió lo mismo: *"entra a ninguna, el sistema no sugiere precios en este caso"*. 🔴 Eso **supersede Q-18(a)**, donde había quedado registrado el respaldo — pero ahí Hugo estaba diciendo "de acuerdo" a una propuesta mía planteada en abstracto, y acá está respondiendo una pregunta concreta. Vale la respuesta directa y posterior.

**Lo que gana el sistema:** nunca adivina un precio. Un campo vacío es información honesta ("nadie definió esto"); un precio heredado de otra lista es una afirmación que nadie hizo. Y desaparece toda la máquina de cascada, con sus casos borde.

🟢 **Además ya está implementado a medias**: `getSuggestedPrice` devuelve `null` cuando el precio es `<= 0` (`usePriceSuggestions.ts:29`). La semántica "cero = sin sugerencia" **ya existe en el hook**; solo hay que no romperla.

### D4 — 🔴 El resolutor vive en el SERVIDOR, en un solo lugar.

`GET /price-lists/current?third_party_id=X` devuelve el mapa ya resuelto. **Por qué no client-side:** la misma resolución tiene que aplicar en las 3 pantallas de compras **y** en la liquidación de la Entrada, que es otro flujo con otro estado. En JS quedaría escrita dos veces, y el día que cambie —esta regla ya cambió una vez en 24 horas, ver D3— se corregiría en una y no en la otra.

Sin el parámetro → `price_list_group_id IS NULL` → **el comportamiento de hoy, byte a byte**. Ese es el seam de no-regresión y es explícito, no accidental.

### D5 — Sin permisos nuevos.

Reusa `materials.view_prices` / `materials.edit_prices`, que ya gobiernan las 7 rutas de precios. Cero migración de permisos, cero wiring de roles, cero cambio en el catálogo.

### D6 — La pantalla de listas va detrás del flag `kg_ledger_enabled`.

Las 3 empresas cliente no ven nada. Es lo que sostiene la afirmación de D1 de que la columna se queda en `NULL` para siempre en esas orgs.

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
| `_base_query` heredado de `CRUDBase` | listado genérico | `IS NULL` por defecto |

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
- **Golden ×3 orgs.** Con una honestidad sobre qué protege: **ninguna de las 15 capturas lee `price_lists`** (lo verifiqué: el único acoplamiento del modelo fuera de su servicio son referencias en docstrings de tarifas y fórmulas). O sea, el golden acá es **cinturón sobre tirantes** — la protección real es el `NULL` de D1. Se corre igual porque la regla es "toca tabla compartida, el golden es gate", y porque el costo de correrlo es bajo comparado con el de equivocarme sobre qué lee qué.
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

### 🟠 Lo único abierto: la transición (Q-26 del canon — la levanto yo, no la preguntó nadie)

Q-22 dice que sin lista no hay sugerencia. Aplicado tal cual, **el día que esto se encienda todos los proveedores de SAC pierden el precio sugerido** hasta que alguien los asigne: hoy compran contra la lista general y mañana no tendrían nada. La operación de Johana se degradaría sin que ella lo haya pedido, y el síntoma sería un campo vacío — fácil de leer como "el sistema se dañó".

Dos salidas, ambas baratas, y es **decisión de operación, no de diseño**:

- **(a)** Sembrar una lista inicial con los precios generales de hoy y asignar a todos los proveedores; después Hugo los reparte entre sus listas con calma.
- **(b)** Cargar y asignar todas las listas antes de encender.

Hay que decidirla **antes del deploy**, no después.

### Nota de coherencia para SAC (no bloquea)

Cuando todos los proveedores estén asignados, la **lista general deja de leerse en SAC** — pero la pantalla de Precios en modo tabla la seguiría editando (D7). Queda una pantalla que edita datos que nadie consume. No rompe nada y para las 3 empresas cliente esa pantalla es la única que importa, así que **no se toca en este ciclo**; se anota por si más adelante conviene que en SAC esa entrada lleve directo a las listas.
