# Traslados conscientes de sede — informe

**Fecha:** 2026-08-11
**Detonante:** pruebas de Daniel en dev — "Traslado CV → Molino: el módulo sirve;
falta configurar la ruta de tránsito del molino, que es por lo que te salió *no
existe tránsito que rota*."

---

## 1. Por qué esto no era un problema de configuración

La petición original era preconfigurar el tránsito del molino en el seeder. Es
un cambio de dos líneas y **habría producido números equivocados en silencio.**

El traslado dos pasos (#84) decide si una línea genera deuda de plomo intersede
y cargo de maquila con una sola pregunta, estampada al despacho:

```python
is_contributor = formula is not None
```

O sea: **por el hecho de que el material tenga fórmula, sin mirar el recorrido.**
Con el tránsito del molino configurado, mover material de Circunvalar a su propio
molino habría emitido:

- un `KgLedgerMovement` de tipo `intersede_send` — deuda de plomo entre dos
  bodegas que son la misma operación;
- el par `internal_maquila_expense` / `internal_maquila_income` — un cargo de
  maquila que se resta a una sede y se suma a la otra en el P&L por sede (#84).

Johana fue explícita en la reunión del 11-ago: **Circunvalar y su molino son un
solo inventario.** El módulo habría "funcionado" —sin error, sin warning— y
habría inventado un pasivo de plomo y movido plata entre sedes por material que
nunca salió de la sede.

La configuración no arregla eso. Le falta al modelo la noción de sede.

---

## 2. Qué se construyó

### 2.1 El dato: `warehouses.sede_warehouse_id`

Auto-FK nullable. **NULL = la bodega es su propia sede.**

Esa elección de default es la que hace la no-regresión demostrable, no algo que
haya que verificar caso por caso: con NULL en todas las bodegas —el estado de las
7 orgs al momento de la migración— dos bodegas distintas son siempre dos sedes
distintas, así que **todo traslado sigue siendo intersede y el comportamiento
queda byte a byte.** Solo cambia donde alguien agrupe explícitamente.

Migración `d0e1f2a3b4c5`. 🔴 **Tabla compartida (las 7 orgs) → el golden es gate
duro**, y `warehouses` es además una de las 15 capturas del golden.

### 2.2 Segunda vuelta: dentro de una sede no hay dos pasos

Al ver la primera versión, Daniel cerró la otra mitad del problema:

> *"Para el caso del molino no hace sentido dos pasos, es la misma sede. No se
> pesa al salir y al llegar en la misma sede."*

Tiene razón, y explica por qué la bodega de tránsito del molino se sentía
inútil: **lo era**. El tránsito es el limbo donde el material espera entre el
pesaje de salida y el de llegada. Si no hay dos pesajes, no hay espera, y no hay
limbo que modelar.

Entonces la sede decide **dos** cosas, no una:

| | Intra-sede | Entre sedes |
|---|---|---|
| Pasos | **1** — nace `received` | 2 — despacho → recepción |
| Tránsito | ninguno (`transit_warehouse_id` NULL) | bodega virtual |
| Movimiento físico | un salto origen → destino | dos saltos |
| Merma / discrepancia | no aplica (un solo pesaje) | tolerancia + `DiscrepancyTask` |
| kg intersede + maquila | no | sí, si el material tiene fórmula |

`transfers.transit_warehouse_id` pasa a nullable (migración `f1a2b3c4d5e6`).
`transfers` es tabla exclusiva SAC con cero filas en las orgs cliente y **no es
una de las 15 capturas del golden** — a diferencia de `warehouses`.

Dos cosas que salieron gratis:

- **`annul()` no se tocó.** Refleja *todos* los `InventoryMovement` con
  `reference_id = transfer.id`, sin importar cuántos saltos hubo — un salto se
  revierte igual de bien que dos. Hay un test que lo clava.
- **`receive()` ya bloqueaba** (el estado no es `dispatched`). Solo se le mejoró
  el mensaje: en vez de *"estado actual: 'received'"* dice *"es dentro de la
  misma sede: se completó al registrarlo"*.

Y la consecuencia directa de la pregunta de Daniel: **la bodega
`Circunvalar - Molino - Transito` se quitó del seeder.** No servía para nada.

### 2.3 La regla: un solo punto de decisión

```python
transit = self._resolve_transit_warehouse(db, organization_id, dest)
crosses_sede = self._crosses_sede(origin, dest)
...
    is_contributor=formula is not None and crosses_sede,
```

Todo lo demás del módulo —recepción, resolución de discrepancias, anulación— ya
**lee** `is_contributor` (líneas 241, 421, 638) en lugar de recalcularlo. Por eso
la regla de sede vive en el despacho y en ningún otro lado: no hay una segunda
copia que pueda desincronizarse.

```python
@staticmethod
def _sede_of(warehouse: Warehouse) -> UUID:
    """La sede de una bodega. NULL = la bodega ES su propia sede."""
    return warehouse.sede_warehouse_id or warehouse.id
```

### 2.3 Validación — porque un valor malo aquí no da error, da números equivocados

`CRUDWarehouse._validate_sede` rechaza con 400:

| Regla | Por qué |
|---|---|
| No puede ser su propia sede | `_sede_of` ya lo resuelve con NULL; el dato redundante confunde |
| La sede no puede ser de otra org / inactiva | multi-tenancy |
| Una bodega de tránsito no puede ser sede | nunca es origen ni destino de un traslado |
| Un solo nivel: la sede apuntada debe ser su propia sede | sin esto `_sede_of` tendría que recorrer un árbol, y un ciclo colgaría el despacho |
| Una bodega que **ya es sede de otras** no puede tener sede | el otro extremo de la misma cadena: dejaría a sus hijas apuntando a un nodo intermedio |

Los dos últimos son la misma regla vista desde cada punta. El primero se me
ocurrió solo; el segundo apareció al preguntarme qué pasa si alguien edita la
bodega padre después.

### 2.5 Configuración SAC (seeder)

`WAREHOUSES` gana una 5ª posición `sede_name`, y el molino la usa:

```python
("Circunvalar - Molino", False, False, None, "Circunvalar"),
```

Y nada más: **el molino no lleva bodega de tránsito.** Lo que Daniel pidió
originalmente resultó ser innecesario una vez que el modelo entendió las sedes.

Sigue siendo idempotente: la 2ª pasada del PATCH incluye `sede_warehouse_id`, así
que contra la SAC de producción (donde las 6 bodegas ya existen) alinea el molino
sin recrear nada.

### 2.6 Frontend

- **Config → Bodegas**: selector "Pertenece a la sede" (gated por
  `two_step_transfers_enabled`, que es el flag que hace que la sede importe) con
  opción explícita *"Es su propia sede"*, y columna Sede en la tabla. El selector
  solo ofrece candidatas válidas (activas, no tránsito, no ella misma, que sean su
  propia sede) — la validación del backend queda como red, no como primera línea.
- **Nuevo Traslado**: aviso vivo apenas se eligen origen y destino —
  gris *"dentro de la misma sede: se completa de inmediato"* vs índigo *"entre
  sedes: en dos pasos"*. **Avisa, no bloquea** (#17/#76). Sin esto el operador
  solo descubre cuál de los dos casos era al ver el resultado. El botón muta a
  "Registrar Traslado" y el toast a *"material ya en destino"* — decir
  "despachado" mandaría a buscar una recepción que no existe.
- Las etiquetas del formulario decían "Sede origen / Sede destino" para referirse
  a bodegas. Con *sede* ahora significando algo preciso, pasaron a **"Bodega
  origen / Bodega destino"**.

---

## 3. Tests

15 nuevos en `test_sac_transfer_two_step.py` (40 → 55, archivo completo verde).

**El estrella** — `test_intra_sede_un_solo_paso_sin_kg_ni_maquila`: en esa prueba
**no existe bodega de tránsito que rutee al molino, ni cuenta intersede, ni
tarifa de maquila**. Si el traslado intentara ir en dos pasos o emitir,
reventaría con 400. Que pase en verde es la prueba de que no lo intentó, no una
aserción sobre un contador en cero.

Los demás cubren: recibir un intra-sede → 400 con el mensaje que explica; el avg
intacto (invariante 1 de #84); **anulación de un traslado de un solo salto** (el
material vuelve completo a origen); molino → Juan Mina sí va en dos pasos, emite,
y carga el gasto a la sede que despacha; **no-regresión explícita** con dos
bodegas de sede NULL (sigue en dos pasos); dos hijas de la misma sede tampoco
cruzan entre sí *aunque ninguna sea la sede*; y las 6 validaciones.

Nota de semántica que costó un ciclo: `TransferLine.effects_emitted` significa
*"la línea terminó de procesarse"*, **no** *"emitió kg"* — una línea no aportante
también lo marca en True. Lo que hay que asertar es `kg_lead_equivalent is None`
y el par de maquila vacío.

---

## 4. Gates

| Gate | Estado |
|---|---|
| `test_sac_transfer_two_step.py` | ✅ 55/55 (40 → 55) |
| Suite completa | ✅ **1562/1562** en 30:25 |
| `tsc --noEmit` / `npm run build` | ✅ limpios |
| Parity check (modelos ↔ migraciones) | ✅ **DIFF CERO** |
| **Golden ×3 orgs prod** | ✅ **0 diffs reales** en 45 capturas |
| Seeder idempotente (modo prod) | ✅ 2ª corrida: 0 materiales nuevos, 0 fórmulas, 6 bodegas |

**Golden.** BEFORE = worktree de `origin/main` en `:8001`, AFTER = árbol de
trabajo en `:8002`, ambos contra la **misma** BD de dev — así se mide solo el
delta de código y no se destruyen los datos de dev. Resultado: **0 diffs reales,
6 claves aditivas**, que son `sede_warehouse_id` una vez por bodega (Costa 4 +
Biogreen 1 + Meta 1), **todas `None`**. `golden_diff.py` acepta la clave nueva
**solo con ese valor exacto**, así que una sede poblada en una org cliente saldría
como diff real.

**Parity check.** Salía rojo con 4 divergencias desde #87 — las mismas 4
"renderizaciones cosméticas de CHECK" que ese ciclo documentó y cuyo arreglo
correcto ya había prescrito: *normalizar el comparador, no ampliar el baseline*.
Se pagó acá porque un gate que sale rojo siempre deja de ser gate, y porque no
podía certificar "DIFF CERO" sin hacerlo. La normalización es deliberadamente
estrecha (dos formas de castear el mismo array) y está probada contra un CHECK
genuinamente distinto y contra un operador distinto: en ambos casos sigue
reportando. Meterlas al baseline habría además apagado el guard `E1_MARKERS`
sobre esas tablas, que es justo el que hay que dejar encendido.

**Migración: cero divergencias nuevas.** La FK de `sede_warehouse_id` se creó sin
nombre explícito (default de PG), que es lo que produce `create_all` — por eso no
aparece en el parity check.

---

## 5. Pendiente de discutir (pedido de Daniel, 2026-08-11)

**Ver el stock de la bodega origen en el desplegable de materiales del traslado.**
Hoy el selector muestra `CÓDIGO - Nombre (unidad)` y el operador no sabe cuánto
hay hasta que despacha y le llega el warning de stock insuficiente (#76: avisa,
no bloquea).

Las piezas existen: `GET /inventory/stock` ya devuelve el desglose por bodega
(`WarehouseStockDetail`) y el servicio ya calcula `_warehouse_stock` al despachar
para emitir ese warning. Lo que falta es decidir la presentación:

- ¿En la etiqueta del desplegable (`BAT-G1 - … (unidad) · 340 disp.`) o como hint
  bajo el campo de cantidad al elegir el material?
- Los materiales **sin stock en el origen**: ¿se ocultan, se muestran en gris al
  final, o entran normales? Ocultarlos choca con que el inventario negativo es
  válido en toda la app.
- El dato depende de la **bodega origen**, así que cambia al cambiar el selector
  de arriba — hay que invalidar/refrescar, no calcularlo una sola vez.

## 6. Lo que queda fuera, a propósito

- **La sede afecta la emisión de kg/maquila y el número de pasos, nada más.** No
  cambia el P&L por sede (sigue siendo por `warehouse_id`) ni el stock por bodega.
- **Agrupar el P&L por sede** (sumar Circunvalar + su molino en una columna). No
  se hizo —nadie lo pidió y el P&L por sede de #84 filtra por bodega exacta— pero
  hay una consecuencia concreta que conviene decirle a Daniel:

  > El cargo de maquila se estampa en la bodega **que despacha**. Un traslado
  > Molino → Juan Mina deja el gasto en `warehouse_id = Molino`, así que un P&L
  > filtrado a "Circunvalar" **no lo incluye**: hay que pedirlo para el Molino.

  Hoy no molesta porque el molino no despacha a otra sede en la operación real
  (el material sale por Circunvalar). Si eso cambia, este es el punto a cerrar.
- **Traslado de un paso**: intacto. Nunca emitió kg ni maquila.
