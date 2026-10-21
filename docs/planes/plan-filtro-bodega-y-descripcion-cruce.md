# Plan — Filtro por bodega en Compras/Ventas + descripción por lado en el cruce entre terceros

**Versión**: v1.2 (2026-10-21) · **Cliente**: Costa (Reciclajes Nacionales S.A.S) · **Pedido de**: Gustavo Díaz, por WhatsApp
**Estado**: v1.0 → GO condicionado de QA (`QA - Reciclajes de la Costa`, sesión `7158c039…`) a C1–C5 más 8 observaciones → v1.1 las incorpora → **C1–C5 PASAN, GO EN FIRME**, con dos agregados a la grilla (G1, G2) que esta v1.2 incorpora; las marcas **[C#]**/**[O#]** dicen de dónde sale cada cambio. Las preguntas de §4 las cerró Daniel. **No se implementa sin la autorización de Daniel.**

## 0. El pedido, con las palabras de Gustavo

1. *"necesitamos saber las entradas y salidas de cada bodega.. no se si una casilla donde yo seleccione ver las compras de bodega 'San Alberto' y solo me salgan esas. Ahora mismo solo podemos ver las cantidades que hay en cada una."* Y la urgencia: *"lo del inventario si es full U, porque abrimos otra bodega y ya estamos descargando allá y nos toca ir auditando quién nos está despachando en ese punto y ahora mismo me queda difícil buscarlo"*.
2. *"cuando hago 'transferencias entre terceros', algunas veces la descripción o concepto del movimiento no debería ser el mismo en los terceros [...] para uno de ellos simplemente debería ser por ejemplo: 'consignación bancaria' pero para el otro sí debería colocar por ejemplo: 'Dinero para impuesto x' [...] te propongo que me añadas 1 línea de descripción del origen y una línea de descripción del destino"*.

## 1. Lo que ya existe (medido en código y en la réplica de dev del 17-sep; QA lo reprodujo)

| Pieza | Estado hoy |
|---|---|
| `GET /sales?warehouse_id=` | ✅ **El backend ya filtra** por `Sale.warehouse_id` (`sales.py:244` → `sale.py:1115`). La pantalla de Ventas **no ofrece el selector**, y **ningún test** cubre ese filtro. |
| `GET /purchases` | ❌ Sin filtro de bodega. En compras la bodega va **por línea** (`purchase_lines.warehouse_id`). La cabecera (`purchases.warehouse_id`, de E1) está en **NULL en las 3.173 compras de Costa**: el servicio la deja en NULL cuando la compra se crea solo con líneas (`purchase.py:222-243`). |
| Compras con líneas en 2+ bodegas | **1 de 3.173** en Costa, 0 en Meta. |
| Compras con 2+ líneas **en la misma bodega** | **900** en Costa: el caso común. Es el que hace que un `join` duplique filas (C1). |
| Pasa mano (DP) | Sus 679 líneas de compra y sus 676 ventas **no tienen bodega** (nunca tocan inventario, #1). Todas las ventas que no son de pasa mano tienen bodega. |
| `GET /inventory/movements` (Historial de Movimientos) | ✅ Ya filtra por bodega, tipo y fecha, y enlaza a la compra o la venta. **No muestra el tercero.** Gustavo probablemente no sabe que existe; ver §5. |
| Cruce entre terceros (`POST /money-movements/tp-transfer`) | Ya crea **dos movimientos**, `tp_transfer_out` y `tp_transfer_in`, cada uno con **su propia columna `description`**. El servicio les escribe el **mismo** texto. En Costa hay **527** `tp_transfer_out`: **517 salieron del formulario de cruce y 10 son traslados de Obligaciones** (#86, con `financial_obligation_id`) **[O2]**. |
| Editar la descripción de un movimiento ya creado | ❌ No existe. Solo se puede editar la clasificación (#39). |
| `GET /warehouses` | Exige `warehouses.view`. El rol de sistema **`liquidador` NO lo tiene en ninguna organización salvo Costa** (medido en `role_permissions`) **[C3]**. |

"San Alberto" todavía no está en la réplica de dev: es la bodega nueva que menciona Gustavo.

## 2. Pedido 1 — Filtro "Bodega" en Compras y en Ventas

**D1. Compras: nuevo parámetro `warehouse_id` en `GET /purchases`**, aplicado en `purchase_service.get_multi` como
`EXISTS (SELECT 1 FROM purchase_lines WHERE purchase_id = purchases.id AND warehouse_id = :w)`.
- 🔴 **Nunca un `join` a líneas.** 🔴 **[C1] Y no por la razón intuitiva.** Un `join` filtrado por la bodega A sobre una compra con líneas en A y en B devuelve UNA fila, la de A. Duplica cuando la compra tiene **2 o más líneas en la MISMA bodega filtrada**, y eso le pasa a 900 compras de Costa: un `join` agregaría 3.286 filas. ⚠️ El síntoma tampoco es el obvio: la `Query` legacy con `joinedload` de colección **unifica entidades**, así que la lista visible puede verse bien mientras `total`, `active_total` y `amount_sum` están inflados. En pantalla se vería como páginas cortas y el KPI "Total Compras" inflado.
- Se filtra **solo por las líneas, nunca por la cabecera** **[C2]**. Las líneas son la fuente en las dos familias: en Costa la cabecera está en NULL, y en SAC la cabecera fuerza la bodega de las líneas (#75 D11). Filtrar por la cabecera vaciaría Costa entera y en SAC pasaría inadvertido; lo sostiene T1 con fixtures de las dos formas.
- Ausente = la consulta de hoy, byte a byte.

**D2. Ventas: el backend no cambia.** Solo se agrega el selector en la pantalla y el test que falta.

**D3. Semántica de una compra con líneas en varias bodegas: aparece COMPLETA** en cada bodega donde tiene al menos una línea, con su total y todas sus líneas. Medido: 1 compra en Costa.
- **Quedan incluidas también las líneas de otras bodegas** **[O3]** en: el KPI "Total Compras", la columna "Cant. Total" (#72) y la hoja Detalle del Excel. La hoja Detalle tiene columna Bodega y con ella se distinguen, pero **sumar kg en esa hoja para San Alberto cuenta de más** las líneas de otra bodega en una compra mixta. Hoy es 1 compra.
- *Alternativa descartada*: mostrar solo la porción de la bodega filtrada. El monto de una compra cambiaría según el filtro y el KPI no cuadraría con el detalle de la compra. Para la pregunta de Gustavo ("¿quién me despacha ahí?") no hace falta.

**D4. Las compras y ventas de pasa mano desaparecen al filtrar por bodega.** Es lo correcto: nunca pasaron por una bodega. Sin filtro, se ven como hoy.

**D5. Pantalla** (`PurchasesPage`, `SalesPage`):
- 🔴 **[C3] El selector se muestra SOLO si el usuario tiene `warehouses.view`.** Compras y Ventas **hoy no llaman a `GET /warehouses`**, y con el selector lo harían al abrir, en todas las organizaciones. El liquidador no tiene ese permiso fuera de Costa. `api.ts` no avisa los 403 (solo maneja los 401) y no hay manejador de errores global, así que para él fallarían 2 peticiones en silencio y el selector quedaría solo con "Todas": una pantalla que ofrece un filtro que no puede dar (#97). Es el segundo argumento de §6 aplicado a la **petición**, no al parámetro. **Implementación**: un componente hijo, `WarehouseFilterSelect`, que llama a `useWarehouses` y se renderiza solo con `hasPermission("warehouses.view")`. Así, sin el permiso, `useWarehouses` no se monta y no sale ninguna petición. **No se toca ningún rol.** Efecto en Costa: ninguno, porque los roles que ven Compras o Ventas tienen el permiso.
- Opciones: todas las bodegas de la organización **menos las de tránsito** **[O4]** (el guard E12 impide que una compra o una venta tenga bodega de tránsito, y el selector de sede del P&L ya las excluye). **Las inactivas sí se incluyen**, marcadas como tales, para poder auditar una bodega cerrada. La opción por defecto es "Todas".
- 🔴 **[C3, apunte de QA] El nombre del badge NO puede salir de un `useWarehouses` llamado en el componente padre.** Si el padre lo llama para traducir el id a nombre, la petición sale sin el permiso y C3 queda vacía. **El badge vive dentro de `WarehouseFilterSelect`, el componente gateado, o se le pasa el nombre desde ahí.** Sin el permiso, el padre muestra el texto de respaldo sin pedir nada.
- Persistido en la URL como `?warehouse=<id>` (patrón de `?dp=`, #45), con badge "Bodega: X ×" para limpiarlo. **[C3] El nombre del badge no puede depender de la lista de bodegas**: si se abre un link con `?warehouse=<id>` sin el permiso, o antes de que cargue la lista, el badge dice **"Bodega filtrada"**. **[O8] En Ventas, el badge entra en la condición de la fila de badges** (`SalesPage.tsx:493`), o no se ve cuando no hay otros filtros. En Compras se revisa lo mismo.
- 🔴 **Cambiar de bodega resetea `page` a 0.** Si no, se puede quedar en una página vacía.
- **El Excel respeta el filtro**: `handleExportAll` pasa el mismo `warehouse_id` a `fetchAllPages`. El export arma sus parámetros a mano, y si no se agrega ahí, la pantalla muestra una bodega y el Excel descarga todas (#51). **[O7] Además, el nombre del archivo lleva la bodega** cuando hay filtro (por ejemplo `compras_San-Alberto_...xlsx`), para que un archivo filtrado lo diga (precedente #44). Solo el nombre del archivo: el contenido del Excel no cambia.
- Mobile (390px): filtros `w-full sm:w-auto`, patrón establecido.

## 3. Pedido 2 — Descripción del origen y del destino en el cruce entre terceros

**D6. `ThirdPartyTransferCreate` gana `destination_description: Optional[str]`** (`min_length=1`, `max_length=500`, el mismo tope que `description`).
- `description` **sigue siendo obligatoria** y pasa a ser la del **origen**: la etiqueta cambia en la pantalla, el nombre del campo en la API no.
- `destination_description` ausente → la pierna destino lleva `description`, **byte a byte el comportamiento de hoy** (P2 de §4).
- **[C4] El schema pasa a `extra="forbid"`.** Hoy Pydantic ignora las claves desconocidas, así que una clave mal escrita hace que el destino reciba **en silencio** la descripción del origen: el respaldo de D6 se vería idéntico a que funcione. Con `forbid`, eso es un 422. El único llamador es `MovementCreatePage` (lo comprobé con grep en `app/`, `scripts/` y `frontend/src`), y su payload manda hoy exactamente las claves del schema, así que el cambio no lo rompe.
- **Cero migraciones**: cada pierna ya tiene su columna.

**D7. `reference_number` y `notes` siguen compartidos** por las dos piernas. Gustavo no lo pidió; el número de referencia identifica el mismo hecho en los dos terceros.

**D8. Pantalla** (`MovementCreatePage`, tipo "Transferencia entre Terceros"):
- Dos campos: **"Descripción para {nombre del origen}"** (obligatoria) y **"Descripción para {nombre del destino}"** (opcional, con la ayuda *"Si la dejas vacía, se usa la misma del origen"*). Mientras no haya tercero elegido, dicen "origen" y "destino".
- **[C5] "Vacía" significa `trim() === ""`.** En ese caso la pantalla **no manda la clave**: ni `""` ni `" "`. Un espacio que viajara pasaría `min_length=1` y dejaría al destino con la descripción en blanco. Si tiene texto, se manda recortado.
- **[C4] `tpPayload` se anota como `ThirdPartyTransferCreate`**, y el tipo en `types/money-movement.ts` gana `destination_description?: string`. Así `tsc` revisa las claves y una mal escrita no compila.

**D9. Todo lo que muestra la descripción ya lee la de cada pierna**: el estado de cuenta (pantalla, PDF, Excel; lee `m.description` por pierna en `money_movements.py:940`), el listado de Tesorería y el detalle del movimiento (que enlaza al par). No hay nada que cambiar ahí; los tests lo verifican por HTTP.

**D10. [O6] Se corrige el docstring de `create_tp_transfer`** (`money_movement.py:891-893`). Dice que el origen sube y el destino baja, y el código hace lo contrario (líneas 950-951: el origen baja, el destino sube). Coinciden con el código los `Field` del schema y el comentario de las propias líneas. Un docstring que miente sobre el signo es lo que relee quien razona sobre un cruce.

## 4. Preguntas para Daniel — CERRADAS (2026-10-21)

- **P1. Corregir los cruces ya hechos → NO, solo los nuevos.** Son 517 cruces del formulario en Costa al 17-sep, todos con la misma descripción en los dos lados, y hoy no hay forma de editar la descripción de un movimiento. Gustavo habla de los cruces que *hace*. Si algún día lo pide, es un ciclo aparte.
- **P2. Destino vacío → copia la descripción del origen** (D6).
- **P3. Traslados contra tercero de Obligaciones (#86) → fuera de alcance.** Tienen su propio formulario y Gustavo no lo pidió.

QA no agregó preguntas nuevas.

## 5. Lo que se le puede decir a Gustavo sin escribir código

**Inventario → Historial de Movimientos** ya muestra entradas y salidas por bodega: se filtra por la bodega y el tipo (compra o venta), con fechas y un link a cada compra. Lo que no muestra es el proveedor, y por eso el filtro en Compras (§2) es la respuesta directa a "quién nos está despachando".

Si después de usarlo pide totales por bodega (kg entrados/salidos por período), eso es un **reporte nuevo**, no este ciclo.

## 6. No-regresión

- **Golden: NO APLICA, y por la razón exacta.** No observa esta superficie.
  - Las 14 entradas de `CAPTURES` (11 rutas: `/money-accounts`, `/money-movements` GET, 8 de `/reports/*` y `/warehouses`) no incluyen `GET /purchases`, `GET /sales` ni `POST /tp-transfer`.
  - **[O1] El golden también captura `/money-movements/third-party/{id}`** (los dos estados de cuenta, `tp_statement` hot/busy, `golden_capture.py:124` y `:150`), que es justo la superficie que D9 dice que no cambia. Tampoco aplica: el ciclo no toca el código que arma el estado de cuenta ni cambia filas existentes (las descripciones ya guardadas no se reescriben, P1). Solo los cruces **nuevos** pueden traer dos textos.
  - El ciclo no agrega ni cambia ningún campo de respuesta. Correrlo daría "0 diffs y 0 aditivas", el resultado que #110 mostró que no distingue nada.
- **Segundo argumento (#98 D10): ¿qué empieza a enviar una pantalla compartida en una organización que no usa la función?**
  - **Parámetros**: `warehouse_id` solo viaja si el usuario elige una bodega, y `destination_description` solo si escribe algo.
  - **Peticiones [C3]**: el selector pide `GET /warehouses`, que estas pantallas hoy no piden. Por eso está gateado por `warehouses.view`: sin el permiso, no hay petición.
- **Sin flags**: el pedido es de Costa, pero sirve a cualquier organización sin romper nada (criterio de Daniel, 2026-10-21). **SAC tiene otra arquitectura**, y se revisó pieza por pieza. El agente de SAC (`reciclaje-erp-0a`) confirmó la lectura y que no tiene nada abierto en estos archivos.
  - **Compras**: SAC no usa esta pantalla. Está oculta (#82); SAC compra por Entradas, que ya tiene su filtro de Sede y no se toca.
  - **Ventas**: SAC sí ve esta pantalla. ⚠️ El filtro mira la bodega **física** de la venta (`Sale.warehouse_id`, la que sacó el inventario), **no** la sede que factura. Una venta derivada de una Salida de Plomo sale de Juan Mina y la factura Circunvalar (Q-30, #107 D5): con el filtro "Circunvalar" no aparece, y con "Juan Mina" sí. Es coherente con la pregunta de Gustavo y no cambia el P&L por sede. **[O5] Por eso, NO se conecta el drill-down del P&L por sede a este filtro.** `ProfitAndLossPeriodView:100` enlaza a `/sales` sin bodega aunque haya una sede elegida. Agregarle `&warehouse=` parecería el paso natural, pero en SAC no cuadraría, porque el P&L usa `coalesce(billing_warehouse_id, Sale.warehouse_id)`.
  - **Cruce entre terceros**: el mismo formulario para todas las organizaciones. Con el campo nuevo vacío, el resultado es idéntico al de hoy.
- **Sin permisos nuevos, sin tocar roles y sin migraciones.**

## 7. Tests y defectos plantados

La grilla defecto × test (con la predicción de cuáles caen) **se commitea ANTES de plantar**, con G1 y G2 ya incluidos. La columna "esperado" sale de ese commit y no se reescribe. Las predicciones de defectos que viven en una vía compartida se escriben como "al menos estos".

**Fixture de compras [C1/C2]**: en la bodega A, una compra con **3 líneas en A** (forma Costa, cabecera NULL), una compra con líneas en **A y B** (cabecera NULL), una compra con **cabecera puesta en A** (forma SAC, líneas forzadas a A), una de **pasa mano** (líneas sin bodega), una **cancelada** con línea en A (para `active_total`) y **[G1] una compra con líneas SOLO en la bodega B**. Sin ella, la única compra que el filtro A debe excluir es la de pasa mano, y un `EXISTS` con `warehouse_id IS NOT NULL` en vez de `= :w` pasaría T1 y T3 en verde. Los asserts van sobre **`total`, `active_total` y `amount_sum` contra valores calculados a mano**, no sobre `len(items)`.

| # | Test | Qué afirma |
|---|---|---|
| T1 | Filtro por bodega A **y por bodega B** | Con A: exactamente las compras con línea en A (las dos formas, Costa y SAC), la de 3 líneas **una vez** y **la de solo-B ausente** [G1]. Con B: la de solo-B y la mixta A+B. En los dos, `total`, `active_total` y `amount_sum` coinciden con el cálculo a mano |
| T2 | Filtro A + `search` | Sin duplicados y con los mismos conteos (el `search` ya hace `join` al proveedor) |
| T3 | Pasa mano | No aparece con filtro; sí aparece sin filtro |
| T4 | Sin `warehouse_id` | Listado y conteos iguales a los de la llamada sin el parámetro |
| T5 | Bodega de **otra** organización | Lista vacía, sin datos ajenos (control, salvo bajo P11: ahí cae) |
| T6 | Ventas por bodega | Solo las de esa bodega; las de pasa mano no aparecen (test que hoy falta) |
| T7 | Cruce con dos descripciones | Cada pierna guarda la suya, y **el estado de cuenta de cada tercero, leído por HTTP**, muestra la suya |
| T8 | Cruce sin `destination_description` | Las dos piernas iguales (no-regresión) |
| T9 | Validación de `destination_description` | 501 caracteres o `""` → 422 |
| T10 | Clave desconocida en el payload del cruce **[C4]** | 422 (por ejemplo `destination_descripton`) |
| T11 | Anular el cruce | Anula las dos piernas y cada una conserva su descripción (control) |

| Defecto plantado | Debe tumbar (al menos) |
|---|---|
| P1 — `join` a `purchase_lines` en vez de `EXISTS` | T1, T2 (por los conteos; la lista puede verse bien) |
| P2 — filtrar por cabecera con `OR purchases.warehouse_id IS NULL` | T3 |
| P3 — aplicar el filtro aunque no venga el parámetro | T4 |
| P4 — el endpoint de ventas ignora `warehouse_id` | T6 |
| P5 — escribir `description` en las dos piernas | T7 |
| P6 — dejar el destino en NULL cuando no viene | T8 |
| P7 — quitar `min_length`/`max_length` | T9 |
| **P8 [C2]** — filtrar por la cabecera (`Purchase.warehouse_id == w`) | T1 (las compras de forma Costa desaparecen) |
| **P9 [C4]** — quitar `extra="forbid"` | T10 |
| **P10 [G2]** — `EXISTS` **sin** la correlación `PurchaseLine.purchase_id == Purchase.id` (la subconsulta es verdadera para todas las compras de la org en cuanto existe alguna línea en A) | T1, T3 (aparece la de pasa mano). T5 no lo ve |
| **P11 [G1]** — `EXISTS` con `warehouse_id IS NOT NULL` en vez de `= :w` | T1 (la de solo-B aparece con A), **T5** (deja de ser control: devuelve compras propias para una bodega ajena) |

**Entrega a QA**: la grilla commiteada antes de plantar; el resultado del plantado con el motivo de cada caída (`--tb=line`); la suite completa con su `EXIT`, capturado dentro del bloque; y `tsc`, eslint y build. QA corre sus subconjuntos coordinando el turno en 5433: un solo dueño a la vez.

**Frontend** (sin infraestructura de test): `tsc`, eslint (techo 37) y build. Y **en pantalla**, a 390px y a 1280px:
1. Compras y Ventas filtradas por una bodega; el Excel filtrado, con el nombre de la bodega en el archivo.
2. Un link con `?warehouse=` abierto directo: el badge se ve.
3. Un usuario **sin** `warehouses.view`: no ve el selector, y en la pestaña Network **no hay** `GET /warehouses`.
4. **[C4]** Un cruce con **dos descripciones distintas**, y después el estado de cuenta de **los dos** terceros.
5. **[C5]** Un cruce con solo espacios en el campo destino: el destino lleva la descripción del origen.

## 8. Fuera de alcance

- Editar cruces ya hechos (P1).
- Columna "Tercero" en el Historial de Movimientos.
- Reporte de entradas/salidas por bodega.
- Filtro de bodega en Pasa Mano (no tiene bodega) y en los reportes de compras/ventas (#45).
- Conectar el drill-down del P&L por sede a este filtro **[O5]**.
- Descripción por lado en los traslados de Obligaciones (P3).

## 9. Coordinación

Toca código compartido con SAC (`purchase.py`, `PurchasesPage`, `SalesPage`, `money_movement.py`, `MovementCreatePage`). El agente de SAC (`reciclaje-erp-0a`) confirmó que no tiene nada abierto en esos archivos. Su cambio sin commitear en `InboundDetailPage.tsx` (orden alfabético de materiales, de la reunión con Johana) **no se toca**. Se trabaja en un **worktree propio sobre develop**, nunca cambiando de rama en el árbol compartido, que está en `main`. El hash del commit se le pasa al agente de SAC.
