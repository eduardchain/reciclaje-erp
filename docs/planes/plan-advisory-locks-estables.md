# Plan — Llaves estables para los advisory locks de numeración (fix compartido, 3 orgs cliente)

**Versión:** 1.2 (F1–F5 de QA aplicadas; v1.2 suma `transfer.resolve` a los flujos declarados) · **Fecha:** 2026-09-09 · **Origen:** backlog de QA en la revisión de #105 (F2) + verificación del unit de producción · **Tipo:** fix propio, no SAC · **Prioridad:** Daniel, 9-sep ("dale con el 1")

## 1. El defecto, verificado

Cada documento numerado (compra, venta, cruce, movimiento de tesorería, ajuste, transformación, traslado, entrada, salida de plomo) toma el siguiente consecutivo con `SELECT MAX(numero)+1` protegido por `pg_advisory_xact_lock(llave)`. La llave se deriva con **`hash()` de Python**, que se aleatoriza **por proceso** (`PYTHONHASHSEED`, Python ≥ 3.3).

**Producción corre con más de un proceso** — leído en el unit del VPS por mí y **verificado por QA** (`systemctl cat reciclaje-backend`, solo lectura; el unit no está en el repo):

```
ExecStart=.../uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --timeout-keep-alive 75 --proxy-headers ...
```

Cuatro workers = cuatro semillas = cuatro llaves distintas para la misma organización. Dos registros simultáneos en la misma org que caigan en workers distintos **no se serializan**: los dos leen el mismo `MAX` y calculan el mismo número. El fix es correcto con 1 o con 4 workers; el conteo solo cambia "latente" por "vivo".

**Defecto A (multi-proceso).** Qué pasa después depende de si el contador tiene índice único:

| Contador | Índice único (org, número) | Colisión hoy |
|---|---|---|
| `purchases.purchase_number` | sí | 500 (IntegrityError), el usuario reintenta |
| `sales.sale_number` | sí | 500 |
| `money_movements.movement_number` | sí | 500 |
| `inventory_adjustments.adjustment_number` | sí | 500 |
| `material_transformations.transformation_number` | sí | 500 |
| `transfers.transfer_number` | sí | 500 |
| `inbound_orders.order_number` | sí | 500 |
| `willard_deliveries` (org, serie, número) | sí | 500 |
| **`double_entries.double_entry_number`** | **NO** (solo pkey, `purchase_id`, `sale_id` — modelo y `pg_constraint` de dev) | **duplicado silencioso**: dos cruces con el mismo número |

**Defecto B (dentro de UN proceso, pre-existente e independiente de los workers).** Un mismo contador tiene **dos generadores con dos llaves distintas**:

| Contador | Generador | Llave |
|---|---|---|
| `purchase_number` | `purchase.py:1825` | `hash(str(org)) % 2**63` |
| `purchase_number` | `double_entry.py:856` | `hash(f"purchases_{org}") % 2**31` |
| `sale_number` | `sale.py:1248` | `hash(f"{org}-sales") % 2**31` |
| `sale_number` | `double_entry.py:864` | `hash(f"sales_{org}") % 2**31` |

Una compra directa y la compra interna de un cruce **nunca se serializaron entre sí**, ni con un solo worker. Lo que lo tapa: el índice único (500) y que rara vez coinciden en el mismo milisegundo.

**Inventario completo** (grep `pg_advisory` en `app/`, no de memoria; QA lo reprodujo): **11 llamadas reales en 9 servicios**; 10 con `hash()`, 1 ya estable (`willard_delivery._lock_key`, crc32, #105). Los tres que usan `hash(str(org))` a secas (compras, traslados, entradas) comparten HOY la misma llave dentro de un proceso — sobre-serializan tres contadores independientes; no es un bug, es un acoplamiento accidental.

**Datos al corte** (réplica de prod en dev, Costa al 2026-09-02): **cero duplicados** en los 9 contadores. El índice de doble partida se puede crear sin conflicto (la migración lo verifica igual, D5).

## 2. Diseño

**D1 — un helper, una forma de derivar la llave.** `app/utils/advisory_locks.py`:

```python
# nombre de secuencia -> (tabla, columna, columna de partición | None)
SEQUENCES = {
    "double_entry_number":   ("double_entries", "double_entry_number", None),
    "inbound_order_number":  ("inbound_orders", "order_number", None),
    "transfer_number":       ("transfers", "transfer_number", None),
    "willard_delivery":      ("willard_deliveries", "delivery_number", "series"),
    "purchase_number":       ("purchases", "purchase_number", None),
    "sale_number":           ("sales", "sale_number", None),
    "movement_number":       ("money_movements", "movement_number", None),
    "adjustment_number":     ("inventory_adjustments", "adjustment_number", None),
    "transformation_number": ("material_transformations", "transformation_number", None),
}

def sequence_lock_key(organization_id, sequence, partition=None) -> int:
    # KeyError/ValueError si `sequence` no está en SEQUENCES (fail-closed: un nombre
    # nuevo se registra, no se inventa — dos nombres para un contador es el defecto B)
    key = f"{organization_id}:{sequence}" + (f":{partition}" if partition else "")
    return zlib.crc32(key.encode("utf-8"))          # determinista; cabe en bigint

def lock_sequence(db, organization_id, sequence, partition=None) -> None: ...   # toma el lock (D4b)
def lock_sequences(db, organization_id, *sequences) -> None: ...                 # varios, en orden canónico (D4)
def next_number(db, organization_id, sequence, partition=None) -> int: ...      # lock + MAX(col)+1 (F3)
```

El nombre de la secuencia es **el contador**, no el módulo que lo llama: `purchase_number` se pide igual desde compras y desde cruces. `partition` cubre la serie de salidas y produce **exactamente la misma cadena** que `_lock_key` de #105 (`f"{org}:willard_delivery:{series}"`) → el test T11 de #105 sigue verde por construcción. Colisión crc32 entre dos secuencias de la misma org → sobre-serialización, nunca error (nota de QA).

**D2 / F3 — un generador por contador, y vive en el helper.** No-regresión de los NÚMEROS (QA leyó los nueve en HEAD): **los nueve generadores son la misma consulta** — `MAX(col) WHERE organization_id` liso (los de traslados y cruces con `COALESCE(...,0)+1`, equivalente; salidas con la partición por serie), sin filtro por estado, año ni `is_active` — así que centralizarlos no cambia ningún número. `next_number(db, org, sequence, partition)` hace el lock y el `SELECT COALESCE(MAX(col),0)+1 FROM tabla WHERE organization_id=:org [AND partition_col=:partition]` leyendo tabla y columna del mapa `SEQUENCES`. Los nueve `_generate_*_number` de los servicios quedan como **envoltorios de una línea** (`return next_number(db, org, "purchase_number")`) para no tocar a sus llamadores; `double_entry.py` **borra** sus copias de compras/ventas y llama `next_number(db, org, "purchase_number"|"sale_number")` — ningún guion bajo cruza módulos (F3). El defecto B queda imposible por construcción: hay UN generador.

**D3 — willard delega.** `_lock_key(org, series)` → `sequence_lock_key(org, "willard_delivery", series)`; `_next_number` → `next_number(db, org, "willard_delivery", series)`. Misma llave que hoy.

**D4 — orden canónico de adquisición (F1: la v1.0 decía "sin ciclos posibles" y era falso).** Con la llave por fin efectiva entre workers, dos flujos que toman los mismos locks en orden cruzado pasan de "no contienden" a "se esperan en cruz" y PG aborta uno (40P01 → 500). Orden real leído en código, **por primera adquisición** (las repeticiones dentro de la misma transacción son re-entrantes y no cuentan):

| Flujo | Locks en el orden en que se toman hoy | Líneas |
|---|---|---|
| Cruce `double_entry.create` (+ `liquidate`) | double_entry → purchase → sale (→ movement al liquidar) | de:71/105/132, de:340 |
| Compra directa `purchase.create` con `auto_liquidate` + pago | purchase → movement | purchase:126, :622 |
| Venta directa `sale.create` + `liquidate` | sale → movement (comisiones :1412, cobro :476) | |
| **Entrada `inbound_order.liquidate`** | purchase (N compras) → movement (pago inmediato, SI lo hay) → **adjustment** (descuadres) → **movement** (accrual del recolector) | io:766, :812, :834/:847, :886 |
| **Traslado `transfer.receive`** (por línea) | **adjustment** (merma) → **movement** (par de maquila) | tr:396, :539 |
| **Traslado `transfer.resolve`** | **adjustment** (merma / excedente) → **movement** (par de maquila de la línea liberada, vía `_emit_line_effects`) | tr:693, :714, :758 — ⚠️ la v1.1 lo tenía como "solo uno": lo desmintió leer `_emit_line_effects`, y D4b lo habría tumbado en la suite |
| **Salida `willard_delivery.liquidate`** | venta: sale → (movement si la venta liquida con cargos); abono: **adjustment** (descarga D12) → **movement** (factura, par) | wd:410/428, :465, :569/:681 |
| Ajuste, transformación, tesorería, activos, obligaciones, diferidos, distribución | uno solo (adjustment / transformation / movement) | |

Dos cruces reales: **Entrada con pago inmediato** (movement → adjustment) contra **Traslado con merma y maquila** (adjustment → movement); y el mismo Traslado contra... nada más hoy, pero la **Entrada SIN pago inmediato** (adjustment → movement por el accrual) y el **abono de Salida** (adjustment → movement) van en el orden contrario a la Entrada CON pago: el mismo flujo cambia de orden según sus datos. Solo SAC (las orgs cliente no tienen Entradas, traslados en dos pasos ni salidas), probabilidad ínfima, sin corrupción — pero es una clase, y se cierra por construcción, no por documentación.

**Decisión: (i) orden canónico único + declaración anticipada.** Rango por secuencia: `double_entry_number` 10, `inbound_order_number` 11, `transfer_number` 12, `willard_delivery` 13, `purchase_number` 20, `sale_number` 21, `movement_number` 30, `adjustment_number` 40, `transformation_number` 41. Los flujos que toman más de un lock lo **declaran al entrar**, en orden canónico, con `lock_sequences(db, org, ...)` — una línea al inicio, sin mover ningún paso de negocio (el orden compras → ajustes de #93 D14 y el de la descarga de #100 D12 quedan intactos):

- `inbound_order.liquidate`: `lock_sequences(db, org, "purchase_number", "movement_number", "adjustment_number")` antes de crear las compras.
- `transfer.receive`: `lock_sequences(db, org, "movement_number", "adjustment_number")` antes del loop de líneas.
- `transfer.resolve`: ídem, antes del loop de líneas (corrección v1.2).
- `willard_delivery.liquidate`: `lock_sequences(db, org, "sale_number", "movement_number", "adjustment_number")` al entrar (los tres tipos).
- `double_entry.create` ya toma DE → purchase → sale en orden: no necesita declaración.

Costo: cada uno de esos flujos retiene locks que quizá no use (un traslado sin maquila retiene `movement_number`) durante su transacción — milisegundos, aceptado. Beneficio: **ningún par de flujos puede esperarse en cruz**, porque todo el mundo adquiere en el mismo orden.

**D4b — el orden se EXIGE, no se documenta.** `lock_sequence` lleva en `Session.info` el conjunto de secuencias ya tomadas en la transacción raíz (se limpia con el evento `after_transaction_end` de la transacción raíz; SQLAlchemy 2.0). En la **primera** adquisición de una secuencia, si su rango es **menor** que el máximo ya retenido → `LockOrderError` (un `RuntimeError` con las dos secuencias en el mensaje). Re-adquirir una secuencia ya retenida es siempre válido. Con eso, un flujo nuevo que tome `adjustment` y después `movement` **revienta en la suite**, no en producción un martes a las 3 (#90/#91: un docstring en el mismo archivo no evitó que #88 repitiera la clase). La suite completa es la evidencia de que ningún flujo existente viola el orden — y si alguno lo hiciera, es exactamente lo que hay que saber antes del deploy.

**D5 — índice único para doble partida** (`uq_double_entries_org_number`, migración con **gate de datos**: si hay duplicados en `(organization_id, double_entry_number)` la migración **se detiene** con el listado, patrón G1/G2 de #93; con cero duplicados crea el constraint). Va **en este ciclo** (F4, de acuerdo con QA): sin el índice, el fix del lock deja a los cruces sin red. `alembic/env.py` corre las migraciones pendientes en UNA transacción y el skill de deploy encadena `alembic upgrade head && systemctl restart` → **si el gate para, NADA se despliega**: ni el esquema cambia ni el backend se reinicia con código nuevo sobre esquema viejo; se corrigen los datos (decide Daniel cómo renumerar) y se re-corre. Toca **tabla compartida** → parity y **golden ×3 orgs** son gate (regla de la casa) aunque ninguna respuesta HTTP cambie.

**D6 — sin cambios de comportamiento visibles.** Ninguna respuesta, número ni fecha cambia. Lo único que cambia es *qué peticiones esperan a cuáles*: ahora las correctas, y siempre en el mismo orden. Se quita de paso el `print("🔢 Generated sale number…")` del generador de ventas (stdout en producción). Argumento #98 D10 (qué empieza a enviar el cliente): nada — es todo servidor.

## 3. Tabla de sitios

| # | Archivo:línea | Generador | Hoy | Después |
|---|---|---|---|---|
| 1 | `purchase.py:1825` | `_generate_purchase_number` | `hash(str(org)) % 2**63` | `next_number(db, org, "purchase_number")` |
| 2 | `sale.py:1248` | `_generate_sale_number` | `hash(f"{org}-sales") % 2**31` | `next_number(db, org, "sale_number")` |
| 3 | `double_entry.py:848` | `_generate_double_entry_number` | `hash(f"double_entries_{org}")` | `next_number(db, org, "double_entry_number")` |
| 4 | `double_entry.py:856` | `_generate_purchase_number` | `hash(f"purchases_{org}")` | **se borra**; `create` llama `next_number(..., "purchase_number")` |
| 5 | `double_entry.py:864` | `_generate_sale_number` | `hash(f"sales_{org}")` | **se borra**; `create` llama `next_number(..., "sale_number")` |
| 6 | `money_movement.py:1523` | `_generate_movement_number` | `hash(f"{org}-movements")` | `"movement_number"` |
| 7 | `inventory_adjustment.py:768` | `_generate_adjustment_number` | `hash(f"{org}-adjustments")` | `"adjustment_number"` |
| 8 | `material_transformation.py:601` | `_generate_transformation_number` | `hash(f"{org}-transformations")` | `"transformation_number"` |
| 9 | `transfer.py:1226` | `_generate_transfer_number` | `hash(str(org)) % 2**63` | `"transfer_number"` |
| 10 | `inbound_order.py:2165` | `_generate_order_number` | `hash(str(org)) % 2**63` | `"inbound_order_number"` |
| 11 | `willard_delivery.py:1098` | `_lock_key` / `_next_number` | crc32 propio (#105) | delega en el helper con `partition=series` |
| + | `inbound_order.py:~760`, `transfer.py:~380`, `willard_delivery.py:~215` | flujos multi-lock | orden por datos | `lock_sequences(...)` al entrar (D4) |

## 4. Tests (`tests/test_advisory_locks.py`, + 1 en el modelo)

- **T1** `test_llave_estable_entre_procesos` — dos subprocesos con `PYTHONHASHSEED=1` y `=2` imprimen `sequence_lock_key(org, "purchase_number")` y `hash(str(org))`: el helper da el **mismo** valor, `hash()` da valores **distintos**. Es la prueba de la clase del defecto, no de "dos llamadas iguales" (dentro de un proceso `hash()` también es determinista).
- **T2** `test_secuencias_conocidas_distintas_y_fail_closed` — cada nombre de `SEQUENCES` da llave distinta para la misma org; misma secuencia en orgs distintas → distinta; partición distinta → distinta; nombre desconocido → error.
- **T3** `test_ningun_lock_ni_contador_fuera_del_helper` (guarda, patrón `RELOJES_PERMITIDOS`) — en `app/`, `pg_advisory` aparece **solo** en `utils/advisory_locks.py`; ninguna línea deriva un `lock_id` con `hash(`; y ningún servicio hace `MAX(<x>_number)` por su cuenta (inventario permitido: **vacío**).
- **T4** `test_compra_directa_y_compra_de_cruce_esperan_el_mismo_lock` — **evidencia positiva (F2)**: sesión A toma `lock_sequence(org, "purchase_number")` y NO cierra; un hilo abre sesión B, publica su `pg_backend_pid()` y llama al generador de compras de cruces; el test hace poll (≤ 5 s) sobre `pg_stat_activity` hasta ver ese pid con `wait_event_type='Lock' AND wait_event='advisory'` — **eso** es "bloqueado", distinto de "no arrancó"; después A hace rollback y B tiene que terminar (join ≤ 5 s). Con el código de hoy B nunca entra en espera `advisory` → cae.
- **T5** ídem para ventas (`sale_number`).

> **Errata post-código (C3 de QA):** T4 y T5 **no existen con esos nombres ni con esa forma**. La evidencia positiva de bloqueo (F2) quedó en UN test de una sola secuencia, `test_dos_sesiones_esperan_el_mismo_lock` (`purchase_number`, sesión A retiene, sesión B espera en `pg_stat_activity`), y el par compra/venta del cruce lo cubre `test_el_cruce_pide_las_tres_secuencias_en_orden` (`test_api_double_entries.py`), que parchea `next_number` con un recorder y asserta la lista ORDENADA exacta `[double_entry_number, purchase_number, sale_number]` que pide `create`. Por eso un solo test discrimina P2 y P6: cualquier sustitución en esa lista (purchase→transfer en P2, sale→purchase en P6) la rompe. La grilla §5 se lee con esa traducción; las filas P2/P6 del informe §4 llevan el nombre real.
- **T6** `test_cada_generador_pide_su_secuencia` — se parchea `sequence_lock_key` para registrar `(sequence, partition)` y se llama cada uno de los 9 envoltorios con una org cualquiera: el mapa registrado == el de la tabla §3.
- **T7** `test_doble_partida_unicidad_en_bd` — `db_session`: dos `DoubleEntry` con el mismo `(org, número)` → `IntegrityError` (D5). La migración se verifica en dev con `psql` antes/después, y su gate plantando un duplicado en dev y viendo que se detiene (y que deja la BD como estaba).
- **T8** `test_particion_willard_conserva_la_llave_de_105` — `sequence_lock_key(org, "willard_delivery", "venta") == zlib.crc32(f"{org}:willard_delivery:venta")`; el T11 de #105 sigue sin cambios.
- **T9** `test_orden_canonico_se_exige` (D4b) — en una sesión: `movement` → `adjustment` OK; `adjustment` → `movement` → `LockOrderError`; re-adquirir `adjustment` con `movement` retenido OK; tras rollback el registro se limpia y `adjustment` → `movement` vuelve a fallar (o sea, no quedó basura de la transacción anterior).
- **T10** `test_entrada_sin_pago_inmediato_con_comision_y_descuadre_liquida` — el caso que HOY toma adjustment → movement: con la declaración anticipada pasa (200); sin ella, D4b la tumba. Los otros dos flujos ya tienen tests que los recorren (traslado con merma + maquila en `test_sac_transfer_two_step.py`; abono en materiales con factura en `test_willard_deliveries.py`).

## 5. Matriz defecto × test (compromiso previo, se commitea antes de plantar)

Defectos plantables: **P1** un sitio vuelve a `hash()` con `pg_advisory` propio · **P2** `double_entry` recupera un generador propio de compras (`MAX` + `lock_sequence` con otro nombre registrado) · **P3** el helper no valida contra `SEQUENCES` · **P4** el helper deriva con `hash()` en vez de crc32 · **P5** se quita el `UniqueConstraint` del modelo de doble partida · **P6** el `create` de cruces pide `"purchase_number"` para el número de venta · **P7** un envoltorio pide un nombre registrado que no es el de su contador · **P8** se quita la declaración anticipada de `transfer.receive` · **P9** D4b deja de levantar (solo registra) · **P10** se quita la declaración anticipada de `inbound_order.liquidate`.

| Test | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 | P9 | P10 |
|---|---|---|---|---|---|---|---|---|---|---|
| T1 llave estable entre procesos | | | | ✓ | | | | | | |
| T2 registro fail-closed | | | ✓ | | | | | | | |
| T3 guarda: nada fuera del helper | ✓ | ✓ | | | | | | | | |
| T4 compra directa vs cruce | | ✓ | | | | | | | | |
| T5 venta directa vs cruce | | | | | | ✓ | | | | |
| T6 cada generador pide su secuencia | | ✓ | | | | ✓ | ✓ | | | |
| T7 unicidad doble partida en BD | | | | | ✓ | | | | | |
| T8 partición willard == #105 | | | | ✓ | | | | | | |
| T9 orden canónico se exige | | | | | | | | | ✓ | |
| T10 Entrada sin pago, con comisión y descuadre | | | | | | | | | | ✓ |
| traslado con merma + maquila (existentes, #84) | | | | | | | | ✓ | | |
| T11 de #105 (`_lock_key`) | | | | ✓ | | | | | | |

**Vías compartidas (regla #105): P2/P6 ≥ (T4/T5/T6 se ejercitan desde cualquier test que cree cruces); P8/P10 ≥ (D4b tumba cualquier test que recorra ese flujo con más de un lock: los de traslados en #84 y los de Entrada en #93); P4 ≥ (T11).**

> **Errata post-plantado (informe §4):** T6 ejercita los envoltorios `_generate_*` y P2/P6 viven en `double_entry.create` → T6 **no** los ve; los atrapan T4/T5 (cayeron los dos). Las celdas T6×P2 y T6×P6 estaban mal atribuidas. Resultado real: 10/10 defectos tumban al menos un test, 8 filas exactas, 2 con esa sobre-predicción.

## 6. Gates

Suite completa a archivo con `EXIT=$?` y mtime fuerte (criterio ampliado de QA: `app/`, `tests/`, `alembic/`, `scripts/`, `frontend/src/`); ruff; `schema_parity_check.py` con `alembic upgrade head` en 5434 (D5 suma un constraint: DIFF CERO fuera del baseline); **golden aislado** (F5): develop-HEAD `fb3d946` vs working tree, **mismo backend y misma BD** (:8001, como #98), `_manifest.json` en los dos lados (#99), 48 capturas ×3 orgs, expectativa **0 diffs** — NO main vs develop (arrastraría los 72 de #96 B). La captura BEFORE ya está tomada contra HEAD con cero archivos de `app/` modificados. Plantado de los 10 defectos con log por defecto. Sin frontend → sin eslint/tsc/build.

## 7. Deploy

Una migración (`uq_double_entries_org_number`, con gate) vía `/deploy`. El helper y el orden canónico hacen efecto al reiniciar con `--workers 4`; nada que configurar. **Si el gate para por duplicados en prod (la réplica del 2-sep dice que no hay), no se despliega nada**: alembic revierte su transacción, la cadena `&&` del skill no reinicia el backend, se listan los duplicados y **decide Daniel** cómo renumerar antes de re-correr. El fix del lock no depende del índice en el código, pero sí en el deploy: viajan juntos o no viaja ninguno.

## 8. Fuera de alcance

- Cambiar el mecanismo de numeración (secuencias de PG por org, `INSERT ... RETURNING`): más grande y no hace falta para cerrar el defecto.
- Los `print` sueltos de otros servicios; solo sale el que vive dentro del generador que se toca.
