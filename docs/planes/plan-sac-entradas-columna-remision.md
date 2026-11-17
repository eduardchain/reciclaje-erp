# Plan — Columna Remisión en Entradas, con orden de toda la lista (SAC)

**Versión**: v1.2 (2026-11-17) · **Cliente**: SAC · **Pedido de**: Johana, por Daniel (17-nov). Ya registra Entradas en producción, llena la remisión y quiere verla en la tabla para filtrar, ordenar e identificar.

**Alcance decidido por Daniel (17-nov, ventanita):** «Toda la lista». El orden por remisión lo hace el **servidor**, sobre todas las entradas. Las demás columnas siguen ordenando solo su página, como hoy. Se descartaron dos opciones: ordenar solo la página visible, y llevar al servidor el orden de todas las columnas.

**Estado:**
- La v1.0 (sha256 `c23878fb…4c88`) recibió **GO condicionado de QA**, sesión «QA Ecobalance». La v1.1 (sha256 `e25f0f21…0033`) cierra C1–C4 y recoge N1–N6; las marcas **[C#]** y **[N#]** dicen de dónde sale cada cambio.
- La v1.1 recibió el **GO de QA** con una corrección obligatoria en la matriz, y esta v1.2 la incorpora. Con P5, T5 pasaba en verde por construcción: `newest` es `order_number DESC`, justo lo que T5 afirmaba. T5 suma ahora una cuarta entrada con otra remisión, y T8 fija el orden en que se crean sus dos entradas. Las notas de P3 y P6 y la forma de la llave 3 también están escritas.
- Se construye **después** del commit del ciclo de planta y del OK de Daniel.

## 0. Lo que ya existe (medido en el código, no supuesto)

| Necesidad | Estado hoy |
|---|---|
| El dato | `remission_number` viene en la respuesta del **listado** (`_enrich`, `inbound_orders.py:241`). Se captura en los dos tipos: compra y Willard (`InboundCreatePage`, `InboundEditPage`). El schema no le hace strip, así que «  » es un valor posible. |
| Filtrar | El buscador del servidor ya la encuentra en **todas** las páginas (`inbound_order.py:1830`, #93 D12). El texto del buscador no lo dice. |
| Ordenar | Las flechas de `DataTable` ordenan solo las 20 filas de la página (orden del cliente). El servidor solo conoce `sort=newest|oldest`. |

## 1. Gaps

| # | Gap | Cómo se trata |
|---|---|---|
| G1 | Remisión es texto libre (máx. 50). En orden de texto, «100» queda antes que «9». | Orden natural en el servidor (D2). |
| G2 | Entradas sin remisión, o solo con espacios. | Van **al final en los dos sentidos** (D2): quien ordena por remisión quiere ver primero las que la tienen. |
| G3 | La remisión no es única: no hay UNIQUE y no hay que ponerlo. | Desempate por `order_number DESC`, único por org (`uq_inbound_orders_org_number`). Con eso el orden es total y la paginación con `skip` no repite ni salta filas. |
| G4 | `DataTable` es todo o nada: con `onSortingChange`, **todas** las columnas pasan a orden manual y las demás dejarían de ordenar. | Prop nueva opcional en `DataTable` (D3). |
| G5 | La bandeja (Registradas/Revisadas) ordena FIFO (`sort=oldest`). | Si el orden por remisión está activo, manda él. Al quitarlo vuelve el orden del tab. |
| G6 **[C3]** | La collation de texto de dev y test (Alpine/musl) no es necesariamente la de prod: en dev, `en_US.utf8` ordena por bytes y `'a' < 'B'` da falso (la causa del «minúsculas detrás de la Z» de #108). | El texto se ordena con collation **explícita** (D2, llave 3). Así lo que miden los tests es lo que corre en prod. |

## 2. Decisiones

**D1. Backend: dos valores más en `sort`, sin parámetro nuevo.**
- El patrón pasa a `^(newest|oldest|remission_asc|remission_desc)$`. Un valor fuera de la lista da 422, como hoy.
- Ausente o `newest` da el orden de siempre, byte a byte.
- Solo se tocan `list_inbound_orders` (endpoint) y `get_multi` (servicio).
- El router es exclusivo de SAC y está detrás del flag `kg_ledger_enabled`.

**D2. Orden natural con cuatro llaves.** Con `r = TRIM(remission_number)`:

1. **Vacía al final**, siempre ascendente, sin importar el sentido: `NULLIF(r, '') IS NULL`.
2. **Valor numérico:** `CASE WHEN r ~ '^[0-9]+$' THEN CAST(r AS NUMERIC) END`.
   - El `CASE` es lo que impide castear texto: sin él, la primera remisión de texto da 500.
   - Para el texto es NULL, y la posición de esos NULL va **explícita**: `ASC NULLS LAST` en asc (las numéricas antes del texto) y `DESC NULLS FIRST` en desc (el texto antes).
   - **[C4a]** Esos dos NULLS coinciden con el default de PG. Por eso la llave «grupo numérico/texto» de la v1.0 era redundante, y sale. Escribirlos explícitos es para quien lee; quitarlos no cambia nada medible (ver P9).
3. **Texto:** `lower(r) COLLATE "C"`, en el mismo sentido. En SQLAlchemy es `func.lower(r).collate("C")`. **Nunca** `lower(r COLLATE "C")`: con collation "C", `lower` solo pasa a minúscula el ASCII. Alpine no distingue las dos formas con estos tests, así que se revisa en el diff. Decide entre las de texto, y entre numéricas iguales («12» y «0012»). lower() sigue el precedente de #108.
4. **Desempate:** `order_number DESC` en los dos sentidos.

Resultado: asc da «9, 10, 0012, 100, A-1, B-2, (vacías)», y desc da «B-2, A-1, 100, 0012, 10, 9, (vacías)».

**D3. Frontend: prop opcional `manualSorting?: boolean` en `DataTable`.**
- Su default es `externalOnSortingChange != null`, la expresión de hoy, así que las páginas que no la pasan quedan **idénticas**. Hoy son 7 con orden manual y el resto con orden de página.
- `InboundOrdersPage` pasa `sorting` controlado con `manualSorting={false}`. La tabla sigue ordenando la página para las demás columnas, y la página se entera del orden de Remisión para mandarlo al servidor.
- **[C1] Un solo orden a la vez, impuesto por la página.** TanStack permite orden múltiple con Shift+clic: `enableMultiSort` vale por defecto `!!column.accessorFn` (verificado en `RowSorting.js:182` y `:34`). Con dos órdenes, el cliente reordenaría la página por la segunda columna y rompería el orden del servidor. El handler de la página se queda con `next.slice(-1)`.
- **Columna Remisión:**
  - `sortingFn: () => 0` y `sortUndefined: false`. El cliente no la reordena: TanStack desempata con `rowA.index - rowB.index` (`getSortedRowModel.js:80`), así que queda el orden del servidor;
  - **[N1]** `sortDescFirst: false`. Sin eso, el sentido del primer clic sale de `getAutoSortDir`, y si la primera fila no tiene remisión el primer clic ordenaría desc.
- **[C2] Volver a la página 1 SOLO cuando cambia el `sort` que va al servidor:** activar o quitar Remisión, o cambiar su sentido. Ordenar Placa en la página 3 se queda en la página 3, como hoy.
- **[N6]** El tipo `sort` de `services/inboundOrders.ts:22` se amplía con los dos valores.

**D4. Pantalla:**
- **Columna «Remisión»** después de «Fecha», con `—` si falta.
- **Tarjeta móvil:** «Rem. X» en la descripción.
- **Buscador:** «Buscar #, remisión, placa, conductor, material…».
- **[N4] Excel:** la columna sale en el Excel **de la página**. La página no pasa `onExportAll`, así que el export trae solo las 20 filas visibles. Esa limitación es previa y no cambia.
- **[N2] A 390 px** las tarjetas no tienen cómo ordenar, igual que hoy con cualquier columna; la remisión sí se ve en la tarjeta. Queda declarado por la regla mobile-first.
- **[N3]** El orden vive en `useState` y se pierde al volver del detalle, igual que la búsqueda, los filtros y la página. Hoy solo el tab vive en la URL. `?sort=` queda fuera de alcance.

**D5. Sin migración, sin permisos nuevos y sin cambios en `inbound_order` fuera de `get_multi`.**

## 3. Golden

**No aplica, y está medido:** `grep -c inbound backend/scripts/golden_capture.py` da **0** (QA lo reprodujo). El listado de Entradas no es una captura, el router es exclusivo de SAC y el cambio de `DataTable` es solo frontend.

## 4. Tests (`tests/test_sac_entradas_remision.py`)

| T | Escenario | Afirma |
|---|---|---|
| T1 | Listado sin `sort` | `remission_number` viene en cada item **del listado**, leído por HTTP, y el orden es `order_number DESC` (regresión). |
| T2 | Remisiones «9», «10», «100», «A-1», «B-2», «0012», una sin remisión y una con «  » | `remission_asc` da exactamente 9, 10, 0012, 100, A-1, B-2, y al final las dos vacías. «0012» vale 12: el cero a la izquierda no la adelanta. |
| T3 | El mismo set con `remission_desc` | B-2, A-1, 100, 0012, 10, 9, y las vacías **al final**. |
| T4 | Paginación: `limit=3` recorriendo `skip` | La concatenación de las páginas es igual a la lista completa: sin repetidos ni faltantes, y `total` no cambia. |
| T5 **[N5]** | **Tres** entradas con remisión «R-7», creadas en orden ascendente, y **una cuarta con «R-9» creada al final** | asc: exactamente las tres «R-7» en `order_number DESC` y después «R-9». desc: «R-9» y después las tres «R-7» en `order_number DESC`. La cuarta es la que discrimina contra `newest`: por número va primera y por remisión asc va última (QA, corrección a la v1.1). |
| T6 | Orden + filtro (`display_status` y `search`) | Filtra y ordena a la vez. |
| T7 | `sort=remission` (valor inválido) | 422. |
| T8 **[C3]** | Remisiones «a-2» y «B-1», **creadas en ese orden** (para que `newest` ponga primero «B-1» y no coincida con lo esperado) | En asc, «a-2» antes que «B-1»: el texto no se ordena por bytes de mayúsculas. El par se eligió para que los dos órdenes discrepen: por bytes, «B» (0x42) va antes que «a» (0x61). Con «b-1»/«A-2» los dos coincidirían y el test no mediría nada. |

**Plantado.** La matriz se commitea ANTES de plantar. Cuando el defecto vive en una vía compartida, la predicción se escribe «al menos estos».

| P | Defecto | Tiene que tumbar |
|---|---|---|
| P1 **[C4a]** | Las llaves 2 y 3 se reemplazan por orden de texto puro (sin el valor numérico) | T2, T3 |
| P2 | La llave 1 en descendente: vacías primero en los dos sentidos | T2, T3 |
| P3 | Sin desempate por `order_number` | Al menos T5; probablemente también T2 y T3, por el empate entre las dos vacías, que se crean en orden ascendente y se esperan en `order_number DESC`. Si T5 no cae, es la dirección peligrosa: se refuerza el test, no se reescribe la predicción **[N5]** |
| P4 | `desc` también invierte la llave 1 | T3 |
| P5 | El endpoint ignora `remission_*` y cae a `newest` | T2, T3, T5 (por su mitad asc: la cuarta entrada) y T8 (por el orden de creación fijado) |
| P6 **[C4b]** | `CAST` sin el `CASE` que lo restringe a las numéricas | Al menos T2, T3 y T8; T6 también si su set tiene texto. Con TestClient (`raise_server_exceptions=True`) no se lee un 500 sino la excepción **DataError**: la caída es la misma, y eso es lo que va a decir el log |
| P7 **[C4c]** | Sin `TRIM` en la llave 1 | T2, T3 («  » cae al texto) |
| P8 **[C3]** | Llave 3 sin `lower()` | T8 |
| P8b **[C3]** | Llave 3 sin `COLLATE "C"`, conservando `lower()` | **NO cae en esta máquina**: en Alpine la collation ya ordena por bytes, igual que "C" para minúsculas ASCII. El `COLLATE` existe para prod, cuya collation no se puede medir desde aquí. Se planta para dejar escrito ese límite. |
| P9 **[C4a]** | Llave 2 sin los `NULLS` explícitos | **NO cae ninguno**: son iguales al default de PG. Se planta para dejarlo medido. |
| P10 | Llave 2 con los `NULLS` invertidos | T2, T3 |

**Frontend:** sin infraestructura de tests. Se verifica con tsc, eslint (techo de 37), build y **la pantalla**, a 1280 px y a 390 px:
- con más de 20 entradas en dev, ordenar por Remisión: la página 2 sigue el orden;
- ordenar Placa sigue ordenando la página y **no** vuelve a la página 1 [C2];
- **Shift+clic** en Placa con Remisión activa deja un solo orden [C1];
- el primer clic en Remisión ordena asc aunque la primera fila no tenga remisión [N1];
- la bandeja vuelve al orden FIFO al quitar el orden;
- el Excel de la página trae la columna;
- las otras 7 páginas con orden manual no cambian, porque no pasan la prop.

## 5. Fuera de alcance

- Orden del servidor para las demás columnas: Daniel lo descartó hoy.
- `?sort=` en la URL [N3], y el Excel de todas las páginas [N4].
- Remisión única u obligatoria en Entradas. En Salidas de Plomo sí es obligatoria (#100), pero Johana no lo pidió para Entradas.
- La regla del peso de báscula al revisar (Q-13 reabierta el 17-nov): ciclo aparte, a la espera de la respuesta de Johana.
