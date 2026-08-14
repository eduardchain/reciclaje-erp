# Reporte a QA — 2026-08-13

**Sin commitear ni stagear.** Cuatro asuntos, **cuatro commits separados** — cada uno debe
poder revertirse solo. Los dos primeros son del mismo archivo (el endpoint del estado de
cuenta); el tercero es solo tests; el cuarto son los gates que QA pidió no diferir.

| # | Asunto | Migraciones | Tabla compartida | Golden |
|---|---|---|---|---|
| A | 🔴 Fix del 500 en el estado de cuenta del comisionista | ninguna | camino compartido | ver §A.4 |
| B | Orden del estado de cuenta: un solo reloj por posición | ninguna | camino compartido | ver §B.5 |
| D | 16 flakes de reloj (solo `tests/`) | ninguna | no | no aplica |
| E | Gates: `ruff` + guarda del reloj en `tests/` + muestra del golden | ninguna | **1 fix vivo en prod** (§C.1) | mejora la muestra |

**Deploy: NO.** Decisión de Daniel — esto queda en `develop` sin push hasta nuevo aviso.

> **Nota de lectura**: las secciones marcadas *"lo señaló QA"* o *"la v1 no lo decía"* son
> correcciones de la primera ronda, dejadas visibles a propósito en vez de reescritas como si
> siempre hubieran estado.
>
> **Qué se pide en esta ronda.** A, B y D ya tienen GO de la primera. **E es nuevo** y sale de
> las dos insistencias de ese mismo veredicto — pero no es solo tooling: incluye un **arreglo a
> código que corre en producción hoy** (§C.1) y toca dos archivos compartidos más. Se pide un
> **GO único sobre los cuatro**, en vez de commitear tres con un veredicto y el cuarto sin
> ninguno.

---

## A — 🔴 `UnboundLocalError` en el estado de cuenta de cualquier comisionista

### A.1 Qué está roto

[money_movements.py:1008](../../backend/app/api/v1/endpoints/money_movements.py#L1008),
bloque **2b (comisiones de compra)**, leía `ret.reverted_at`. `ret` es la variable
del loop de **retenciones**, que arranca ~50 líneas más abajo:

```
UnboundLocalError: cannot access local variable 'ret' where it is not associated with a value
```

Primera comisión que entra al statement → **500**.

### A.2 De dónde salió

Commit `7a9dff2` (#93), el fix que la re-lupa de QA marcó como bloqueante: *"los
eventos del estado de cuenta siguen a la FILA (`reverted_at`), no al status de la
compra"*. La prescripción era correcta y su alcance era **sección 2c, ambos lados**.

El reemplazo se aplicó **tres veces**: las dos de 2c (correctas) y una tercera en 2b,
que no tiene `reverted_at` — su reversa la dispara el status de la compra.

```diff
-  status="confirmed" if purch.status == "liquidated" else "cancelled"
+  status="confirmed" if ret.reverted_at is None else "cancelled"     ← ×3, debían ser ×2
```

`old_string` no único. **No está pusheado** (`7a9dff2` no vive en ningún remoto):
producción está intacta hoy y se rompía el día del deploy.

### A.3 Alcance real, medido contra la réplica de prod

| Tercero | Comisiones | Saldo |
|---|---|---|
| Comision #1- Ditar | 201 | −$5.294.107 |
| Salomon (personal) | 7 | $40.667.113 |
| Jorge Hernandez /Salomon Chain | 4 | −$650 |
| Comision SR | 4 | −$54.650 |
| Mirna guevara SAECO | 2 | $42.800 |

Cinco terceros reales de las 3 empresas cliente con el estado de cuenta caído.

### A.4 El fix y su evidencia

Restauradas las dos líneas originales, con un comentario que dice por qué la comisión
**no** tiene `reverted_at`. **2 tests nuevos** en
[test_purchase_commissions.py](../../backend/tests/test_purchase_commissions.py)
(`TestCommissionRecipientStatement`): el statement vivo y el par evento+reversa al
cancelar la compra — el segundo fija además la semántica que el reemplazo pisó.
**Verificados contra el código con bug: revientan.**

**Golden**: el fix devuelve el bloque a su estado en `main`, byte a byte. No puede
diferir de lo que hoy produce producción.

### A.5 🔴 Por qué ningún gate lo vio — y es lo más importante de este reporte

1. **No había test.** Ningún test pedía el estado de cuenta de un comisionista. El
   hueco es anterior a #93.
2. **No hay linter en el backend.** No hay `ruff`/`pyflakes` en el venv ni en el
   sistema. "Variable local usada antes de asignarse" es exactamente lo que un linter
   marca al escribirlo. Es el gemelo del ESLint que falta en el frontend, y ya van
   **tres** bugs que un linter habría matado (los dos de #93 y este).
3. **El informe describía la intención, no el diff.** El informe de #93 dice *"sección
   2c, ambos lados"*. Quien revisa esa afirmación la verifica en 2c, la encuentra
   correcta, y nunca mira 2b — que nada mencionaba y que leído localmente se ve bien.
   El error no es de lógica de negocio sino de **alcance de un reemplazo**: se ve
   preguntando *"¿esta variable existe en este scope?"*, no *"¿la regla es correcta?"*.
4. **El golden tenía la capacidad y falló por la muestra.** Ver §C — es un hallazgo
   propio y vale más que los dos asuntos juntos.

---

## B — Orden del estado de cuenta: un solo reloj por posición de la llave

### B.1 Qué reportó Daniel

En el estado de cuenta de un proveedor, el 13/08 salía **la compra #7 antes que la #4**.

### B.2 Diagnóstico, verificado contra la BD

```
num | liquidated_at            | ctid
  6 | 2026-08-13 07:00:00-05   | (76,29)
  7 | 2026-08-13 07:00:00-05   | (76,30)   ← #7 físicamente antes que #4
  3 | 2026-08-13 07:00:00-05   | (78,15)
  4 | 2026-08-13 07:00:00-05   | (78,16)
```

La llave de orden era `(fecha de negocio, sort_dt, sort_key)` y los eventos comerciales
pasaban **`liquidated_at`** como `sort_dt`. Ese campo **parece** timestamp y es una
**fecha de negocio** — mediodía UTC, que psql imprime literal como `07:00:00-05`. Es la
trampa de #87 usada como criterio de ordenamiento. Dos consecuencias:

**(a) Las operaciones del mismo día empatan exacto.** Al empatar, Python conserva el
orden de llegada, que es el que Postgres devolvió **sin `ORDER BY`**: orden físico. No
es "por antigüedad" ni "por lo último tocado" — los `ctid` de arriba lo refutan: la
pareja actualizada más recientemente (#6/#7, 15:22) está físicamente primero. Es
arbitrario, y por eso no hay forma de explicárselo a un usuario.

**(b) 🔴 Consecuencia que nadie había visto: el pivote de las 7:00 a. m.** La misma
posición de la llave mezcla ese mediodía-UTC con `created_at`, que sí es un instante
real. Resultado: un movimiento de tesorería del mismo día cae **antes o después** de
las operaciones según si se digitó antes o después de las **7:00 a. m. de Bogotá** (=
mediodía UTC). Y de paso **anula a `sort_key`** — el campo que existe justo para decir
"primero operaciones, luego caja, al final reversas" queda después en la llave y nunca
alcanza a decidir nada.

### B.3 La regla nueva

La doctrina de #91 aplicada al orden: **cada posición de la llave compara UNA sola cosa.**

`(día de negocio, clase de evento, instante real, número de documento, orden de emisión)`

- **día de negocio** — `BusinessDate`. En qué día cae el evento.
- **clase** — `sort_key`: 0 operación comercial, 1 tesorería, 2 reversa.
- **instante real** — 🔴 `created_at` / `cancelled_at` / `reverted_at`. **Nunca** un
  `BusinessDate`. Es homogéneo dentro de cada clase: creación contra creación, reversa
  contra reversa.
- **número de documento** — las N compras que nacen en UNA transacción (#93 D14)
  comparten `created_at` al microsegundo; el consecutivo las ordena #3, #4, #5. Y de
  paso **pega cada operación con sus satélites** (comisión, retención), que llevan el
  número del padre.
- **orden de emisión** — último recurso. Conserva el orden natural de las líneas dentro
  de un documento (vista "operations") en vez de barajarlas por UUID, y hace que el
  orden sea **total**: reproducible entre corridas.

Se lee en una frase: *dentro del día, primero las operaciones, después los movimientos
de caja, al final las reversas; y dentro de cada grupo, por el instante real.*

**Propiedad estructural que la v1 de este reporte no reclamaba (la señaló QA).** Poner
`sort_key` **antes** del instante hace que dos `real_ts` solo se comparen dentro del mismo
día **y la misma clase**. La homogeneidad de tipos deja de ser un requisito global —
"que los 23 call sites pasen algo comparable entre sí"— y pasa a ser un requisito **por
clase**: creación contra creación, reversa contra reversa. Es lo que hace que la llave no
dependa de vigilar 23 sitios, y es un beneficio del reordenamiento, no del cambio de valores.

**Y el par adyacente de #61 sobrevive** (verificado por QA): las cancelaciones se siguen
posicionando en `purch.liquidated_at`, o sea en el día de su original y no en el de la
anulación. Que ahora caigan al final de ese día no rompe la promesa de #61, que era de
**fecha**, no de vecindad de fila.

### B.4 Qué cambió en código

- **13 call sites** de `_evt` pasan ahora el instante real en vez de la fecha de
  negocio (`p.liquidated_at` → `p.created_at`, `de_liq_dt` → `de_dt`). Los otros 10 ya
  pasaban un timestamp real y no se tocaron.
- La llave: `events.sort(key=lambda e: e[:5])` sobre la tupla nueva.
- El contrato de `_evt` quedó escrito arriba de la función, con el porqué.

#### 🔴 Cómo verificar el ALCANCE sin creerme

Esta sección existe por el asunto A: el informe de #93 declaró *"sección 2c, ambos lados"* y
el diff eran tres hunks. **Un artefacto que narra la intención no sirve para revisar el
alcance**, así que acá va la comprobación mecánica en vez de la afirmación.

El invariante es *"ningún `_evt` pasa una fecha de negocio como 2º argumento"*, y se verifica
con un comando:

```bash
grep -oE "_evt\([^,]+, *[^,]+," backend/app/api/v1/endpoints/money_movements.py \
  | sed 's/_evt([^,]*, *//; s/,$//' | sort | uniq -c | sort -rn
```

Salida esperada — **solo instantes reales**, ningún `liquidated_at` ni `de_liq_dt`:

```
5 de_dt              3 purch.created_at    3 cancel_dt
2 s.created_at       2 ret.reverted_at     2 p.created_at
1 sale.created_at    1 sale.cancelled_at   1 s.cancelled_at
1 purch.cancelled_at 1 p.cancelled_at      1 m.created_at
1 real_ts  (la firma de _evt)
```

Y el complemento, que debe dar **0**:

```bash
grep -cE "_evt\([^,]+, *([a-z_]+\.)?liquidated_at|_evt\([^,]+, *de_liq_dt" \
  backend/app/api/v1/endpoints/money_movements.py
```

23 call sites en total: 13 cambiados, 10 que ya pasaban un instante real. Los `cancelled_at`
/ `reverted_at` **no se tocaron** — ya eran correctos.

**3 tests nuevos** ([test_statement_ordering.py](../../backend/tests/test_statement_ordering.py)),
los tres **verificados contra el código viejo — fallan, y con el síntoma exacto**:

| Test | Falla vieja |
|---|---|
| `test_same_day_operations_ordered_by_document` | `[3, 2, 1]` — liquidar en orden inverso invertía el estado de cuenta. **Es el bug de Daniel reproducido.** |
| `test_treasury_lands_after_operations_regardless_of_the_hour` | `['payment_to_supplier', 'purchase_liquidation']` — el abono de las 6 a. m. se colaba antes de la compra |
| `test_operation_and_commission_stay_adjacent` | `[C1, C2, Com1, Com2]` — la comisión se despegaba de su compra |

### B.5 🔴 El golden aquí NO prueba nada, y hay que decirlo

La captura `tp_statement` elige **el tercero con `max |saldo|`**
([golden_capture.py:89](../../backend/scripts/golden_capture.py#L89)). Los tres que
salen elegidos:

| Org | Tercero | Movimientos | Compras | Ventas | DPs |
|---|---|---|---|---|---|
| costa | Tico 1.5% | 3 | **0** | **0** | **0** |
| biogreen | RECICLAJE | 4 | **0** | **0** | **0** |
| metarecycling | Eduardo Chain | 3 | **0** | **0** | **0** |

**Cero operaciones comerciales.** `max |saldo|` selecciona socios e inversionistas
(saldos grandes de inyecciones de capital), no los proveedores con cientos de
operaciones. Como sus eventos son todos de clase 1, la llave nueva los ordena por
`created_at` igual que la vieja → **el golden va a dar 45/45 sin haber ejercitado el
cambio**. Un 45/45 aquí es evidencia de nada.

**Alcance real, medido contra la réplica:**

| Org | Eventos comerciales | En días con empate | Terceros afectados |
|---|---|---|---|
| costa | 2.456 | **1.002** (41%) | 88 |
| biogreen | 122 | 34 | 7 |
| metarecycling | 193 | 52 | 15 |

**110 terceros** tienen al menos un día cuyo orden interno puede cambiar.

**🔴 Y la consecuencia es retroactiva** (lo señaló QA, y la v1 no lo decía): esa captura
**nunca** ha ejercitado las rutas comerciales del estado de cuenta, en ninguna corrida. El
reposicionamiento de eventos comerciales por `liquidated_at` (#61) y los eventos sintéticos
de retención (#93) tampoco estuvieron cubiertos. Los tres cambios pasaron por ese gate y
ninguno fue mirado por él. La muestra no es solo poco representativa: está
**anti-correlacionada** con lo que hay que probar, porque el saldo grande lo producen
inyecciones de capital y no la actividad comercial.

**Evidencia que sí sirve** — smoke contra la réplica de prod, los 110 terceros, con el
código nuevo corriendo:

```
{'ok_http': 110, 'eventos': 4772}   →  Todo verde
```

Verifica lo que importa: responde 200 (el sort nuevo no revienta con formas de dato
reales), **el saldo corrido cierra contra el saldo vivo en los 110** (invariante #55), y
las fechas no decrecen. Script en el scratchpad de la sesión; si QA lo quiere
permanente, va a `backend/scripts/`.

**Lo que sí cambia y hay que aceptar explícitamente:**

1. El `balance_after` de las filas **intermedias** de un día con varias operaciones, porque
   el saldo corrido se calcula en el orden mostrado. El saldo final del día y el
   `current_balance` no se mueven — es lo que verifica el smoke.
2. **Las reversas se van al final de su día.** Antes se ordenaban por su instante de
   anulación mezcladas con el resto; ahora `sort_key` decide primero, así que una
   cancelación del mismo día queda después de los movimientos de tesorería de ese día. Es
   el comportamiento que el código ya declaraba y nunca lograba (§B.2b). No toca saldos:
   los eventos `cancelled`/`annulled` no mueven el corrido.
3. **`opening_balance` NO cambia** — se calcula sobre el conjunto de eventos anteriores a
   la ventana, que es el mismo, y la suma es conmutativa. Por construcción, no por suerte.

### B.6 Hallazgo lateral (no se toca en este ciclo)

Las DP serializan su `date` a **medianoche** de Bogotá mientras el resto lo hace a las
**07:00** — ambas son el mismo día de negocio, es inconsistencia de presentación
preexistente. Invisible en pantalla porque el front usa `formatDate` sobre esos campos
(#87). Se anota porque hizo saltar una falsa alarma en el smoke.

---

## D — Dos flakes de reloj en tests (aparecieron al correr la suite a las 19:22)

La primera corrida completa dio **2 fallas**. Ninguna toca el estado de cuenta, y las
dos son de la clase que documenta #92: **la suite se corrió dentro de la franja**
(19:00–24:00 Colombia = 00:00–05:00 UTC), donde la fecha UTC y la local son días
distintos.

**Exoneración primero, diagnóstico después:** corrí las dos contra `HEAD` sin mis
cambios y **fallan igual**. Son flakes latentes preexistentes, no regresiones de este
paquete.

| Test | Causa |
|---|---|
| `test_avg_cost_model_l.py::TestInventoryStressWalk` | `_today = _dt.now(_tz.utc).date()` fechaba la Entrada con el día **UTC**; el servicio valida contra `business_today()` → `422 "La fecha de la orden no puede ser futura", input "2026-08-14"`. El error lo dice solo. |
| `test_sac_entrada_sin_proveedor.py::test_liquidation_does_not_change_past_cuts` | `_past(1)` = `now(utc) − 1 día` = **2026-08-13** = **hoy** en Colombia. La liquidación se fecha con `business_today()` = el mismo día → el corte "de ayer" sí cambiaba. |

Los dos ahora usan `business_today()`. Verificados **dentro de la franja**, que es la
mejor evidencia posible. Los dos archivos completos: **113 ✅**.

### 🔴 Y no eran dos: eran 16. Mi barrido estaba mal — por segunda vez esta noche.

La segunda corrida completa dio **14 fallas nuevas** (`test_api_purchases` 11,
`test_api_reports` 3). No son regresión: son la **misma clase**, en una forma sintáctica
que mi regex no cubría. La primera corrida las había dado verdes solo porque arrancó a las
18:47 y esos archivos —tempranos en el alfabeto— corrieron **antes** de las 19:00.

```python
"date": datetime.now(timezone.utc).isoformat()   # sin .date()
"date": datetime.utcnow().isoformat()            # naive, otra forma mas
```

El validador `BusinessDate` normaliza eso al **mediodía UTC del día UTC** (14-ago) y el
servicio compara contra el día colombiano (13-ago) → *"La fecha de la compra no puede ser
futura"*. Mi regex exigía `.date()` o `- timedelta`, así que **estas dos formas eran
invisibles**.

**Es exactamente el error de #92, cometido por mí, en el mismo repo, sobre el mismo
problema.** La lección de #92 decía textualmente que *"el grep de una sola forma sintáctica
no es un barrido"*, y volví a declarar completo un barrido que no lo era. Lo que lo cerró
no fue otro grep sino **evidencia empírica**: la corrida 2 ocurrió **entera dentro de la
franja** (19:29→20:08), así que es una muestra completa, no parcial — esos 14 son el
conjunto, y se verifica con una corrida completa in-franja, no con un regex mejor.

Los 14 sitios pasan a `business_today_noon()`. Los otros ~20 usos de `now(utc)` en tests
construyen **objetos de modelo directamente** (no pasan por el validador) o son timestamps
de auditoría: corrieron in-franja en la corrida 2 y pasaron. Se dejan como están —
tocarlos sin necesidad es riesgo sin beneficio.

### 🔴 Corrección a la doctrina de CLAUDE.md

La regla del "un solo reloj" dice hoy:

> cuando el día exacto no importa, una **fecha pasada** (`now(utc) - timedelta(days=N)`)
> es robusta en cualquier zona

**Es falsa para N=1.** Durante la franja, `now(utc) − 1 día` es **hoy** en Colombia, no
ayer. La forma robusta es `business_today() - timedelta(days=N)`. Barrido con el regex
que cruza paréntesis (la lección de #92): los **únicos** usos con día 0 o 1 del reloj
UTC en toda la suite eran esos dos; el resto usa N≥2 (el corrimiento de un día sigue
cayendo en pasado) o ya usa el reloj correcto (`date.today()` naive y
`now(BOGOTA).date()` dan el día colombiano en esta máquina).

---

## C — Los gates: **hecho**, no propuesto (QA insistió, y tenía razón)

> La v1 de este reporte los dejaba como "ciclo propio de infraestructura". QA respondió que
> el linter *"no es un ciclo: es una dependencia y un comando"*, y que extender la guarda del
> reloj es **el arreglo estructural de esta noche**. Ambas cosas están hechas y van como un
> cuarto commit (`E`). Lo que sigue es el resultado, no un plan.

### C.1 🔴 `ruff` encontró un 500 VIVO EN PRODUCCIÓN a los 60 segundos de instalarse

[money_movements.py](../../backend/app/api/v1/endpoints/money_movements.py), función
`get_by_account`: dos `from fastapi import HTTPException` **dentro** de la función, en un
archivo que ya lo importa a nivel de módulo (línea 13). Eso vuelve el nombre **local en todo
el cuerpo**, así que el `raise HTTPException(403)` de más arriba explota con
`UnboundLocalError`.

**Efecto real:** un usuario con cuentas restringidas (`UserAccountAssignment`) que pide una
cuenta ajena recibe **500 en vez de 403**. Está en `main`, o sea vivo hoy. Es la **misma
clase** que el asunto A, en el mismo archivo, y el camino no tenía **ni un test** —
`UserAccountAssignment` no aparecía en toda la suite.

Fix: borrar los dos imports redundantes. **2 tests nuevos** (`TestRestrictedAccountAccess`):
403 en cuenta ajena, 200 en la asignada. Reproducido contra el código con bug: revienta con
el `UnboundLocalError`.

⚠️ Los otros tres archivos con la misma forma (`materials.py`, `price_lists.py`,
`inventory_views.py`) **no** se tocaron: ahí el import local es la única fuente del nombre,
no hay uno de módulo, y usan `HTTPException` solo justo después. Son correctos.

### C.2 El set de reglas: la familia de resolución de nombres, y nada más

[ruff.toml](../../backend/ruff.toml) selecciona **F811, F821, F823** — la clase que ya mordió
tres veces. Un `select = ["F"]` completo da **260 hallazgos** (169 imports sin usar, 34
variables muertas, 27 f-strings sin placeholders): una pared que nadie mira y un gate que
nace rojo. El backlog queda escrito en el propio `ruff.toml` con su conteo y con la
advertencia de que **auto-fixear F401 puede romper el registro de metadata de
SQLAlchemy/Alembic**.

Los 20 `F821` restantes son anotaciones en string (`Mapped[list["DoubleEntryLine"]]`, el
idioma de relaciones de SQLAlchemy): no se evalúan en runtime. Van como `per-file-ignores`
con la razón escrita, en vez de reescribir 8 modelos compartidos.

Los 9 `F811` reales se arreglaron: 5 imports duplicados en tests, y 2 parámetros llamados
`date` que tapan el import del módulo en `purchase.py`/`sale.py` — esos **no se renombraron**
(los callers pueden pasarlos por keyword) sino que quedaron anotados en el sitio.

`./venv/bin/ruff check app tests scripts` → **limpio**. `ruff==0.16.3` pineado en
`requirements.txt`, al lado de pytest, que es la convención del archivo.

### C.3 La guarda del reloj, extendida a `tests/` — inventario **vacío**

`RELOJES_PERMITIDOS_TESTS` en
[test_reloj_de_negocio.py](../../backend/tests/test_reloj_de_negocio.py), con los **31**
sitios migrados a `business_today_noon()` (los 16 que fallaron + 15 que aún no habían
fallado). Vacío, igual que el de `app/` — que es lo que lo hace fuerte.

El patrón persigue el **sumidero** (`"date":` / `date=` alimentado desde un reloj), no la
forma de la expresión. Es exactamente lo que les faltó a mis dos barridos: da igual cómo se
escriba el reloj. Cubre las **cuatro** formas encontradas, incluida `datetime.now()` naive —
que da el día correcto, pero por accidente de la zona de la máquina, no por decisión.

Se prueba a sí mismo **en los dos sentidos**: que atrape las cuatro formas *y* que no toque
los timestamps de auditoría (`created_at=datetime.now(timezone.utc)` es correcto y debe
seguir pasando). La auto-prueba encontró un hueco en mi patrón mientras lo escribía — la
forma `_today = _dt.now(_tz.utc)`, una variable intermedia — y por eso hay una segunda rama.
Verificado además ensuciando un archivo a propósito: la guarda revienta y el mensaje dice qué
hacer.

### C.4 La muestra del golden: dos terceros

[golden_capture.py](../../backend/scripts/golden_capture.py) captura `hot` (más saldo, el de
siempre) **y** `busy` (más eventos). Medido contra la réplica:

| Org | Antes (`max │saldo│`) | Ahora (más eventos) |
|---|---|---|
| costa | Tico 1.5% — **1 evento** | Sop Ch — **490** |
| biogreen | RECICLAJE — 4 | JULIO ACUÑA — 24 |
| metarecycling | Eduardo Chain — **1 evento** | Reciclajes de la costa — **60** |

De **6 eventos en total** a **574**.

⚠️ **Nota operativa que es load-bearing**: `golden_diff.py` cuenta un archivo nuevo en
`after` como diff REAL (`SOBRAN en after`). Como el harness levanta el `before` desde un
worktree de `origin/main`, hay que correr **esta** copia del script contra ambos backends —
solo habla HTTP, así que sirve igual. Está escrito en el encabezado del script.

Y una advertencia ganada en carne propia: la primera versión de este cambio llamaba `s` a la
variable del statement, **shadowing la `requests.Session`**, y convertía cada `s.get(...)`
posterior en `dict.get(...)` — 31 capturas caídas. Lo atrapó correr el script, no leerlo.

---

## C.5 — Lo que sigue pendiente de los gates

Los tres ítems de la v1 están hechos (C.1–C.4). Queda uno solo, y no es de backend:

- **ESLint con `react-hooks/rules-of-hooks` en el frontend.** Es el gemelo exacto de C.2 y
  la única de las cuatro clases de bug de #93/#96 que sigue sin herramienta. Hoy
  `npm run lint` **no corre** (no hay config en `frontend/`), así que la única red frente a
  un bug de runtime del navegador es abrir la pantalla.

---

## Dónde mirar más duro

1. **El alcance de A y de B, con el comando de §B.4, no con mi prosa.** Es la lección del
   día: lo que falló en #93 no fue la regla sino el alcance de un reemplazo, y el artefacto
   que se revisó declaraba un alcance distinto al del diff.
2. **La decisión de fondo de B**: ¿es correcto que `sort_key` mande sobre el instante? Yo
   argumento que sí porque hace homogénea cada comparación (creación contra creación,
   reversa contra reversa) y porque es lo que el código ya declaraba. La alternativa —
   ordenar todo por instante de captura y usar `sort_key` solo como desempate— también es
   defendible y produce otro orden en días mixtos. **Es una decisión de presentación, y si
   QA prefiere la otra, se cambia una línea.**
3. **§B.5, la parte incómoda**: acepto que el golden acá no prueba nada y traigo un smoke en
   su lugar. Si QA considera que eso no alcanza para tocar un camino compartido, el
   siguiente paso natural es un before/after real con dos backends (el harness del golden ya
   sabe hacerlo) apuntado a terceros con operaciones.
4. **Lo que decidí NO tocar** y puede objetarse: la inconsistencia de las DP serializando su
   fecha a medianoche (§B.6), y los tres archivos con `from fastapi import HTTPException` local
   que **no** son redundantes (§C.1) — ahí el import es la única fuente del nombre.

### Y en E, que es lo que nadie ha revisado todavía

5. **§C.1 cambia comportamiento en producción.** El argumento de que borrar los dos imports
   locales es seguro descansa en que el de módulo existe ([línea 13](../../backend/app/api/v1/endpoints/money_movements.py#L13))
   y en que ruff queda limpio de F821/F823 en el archivo. Es verificable en un comando; no hace
   falta creerme. Lo que sí es juicio mío: que el 403 sea la respuesta correcta y no otra cosa.
6. **La selección de reglas de ruff es una decisión, no un hecho.** Elegí `F811, F821, F823`
   —la clase que ya mordió tres veces— en vez de `F` completo, que da 260 hallazgos y un gate
   que nace rojo. Si QA cree que vale la pena pagar la limpieza completa ahora, es un argumento
   razonable y cambia una línea de `ruff.toml`.
7. **Los `# noqa: F811` en `purchase.py` y `sale.py`** son lo único de E que toca código
   compartido fuera de §C.1. Son comentarios, pero la alternativa era renombrar un parámetro
   llamado `date` y eso sí rompería a cualquier caller que lo pase por keyword.
8. **De los 31 sitios migrados en tests, 15 no estaban fallando.** Pasaron todos, pero es un
   cambio mecánico masivo: vale una mirada a que ninguno haya cambiado la semántica de su
   assert al pasar de `datetime.now()` a `business_today_noon()`.
9. **🔴 Trampa operativa del golden**, y es la que más caro sale si se ignora: `golden_diff.py`
   cuenta un archivo nuevo en `after` como diff REAL. Como el harness levanta el `before` desde
   un worktree de `origin/main`, hay que correr **esta** copia de `golden_capture.py` contra los
   dos backends. Está en el encabezado del script, pero conviene que QA lo confirme como parte
   del runbook de deploy.

## Gates corridos

| Gate | Resultado |
|---|---|
| Suite completa | **1602 ✅**, 0 fallas, corrida **entera dentro de la franja** (21:09→21:48 Colombia = 02:09→02:48 UTC). Segunda corrida completa in-franja, ya con los gates encima. Es la primera noche en que la suite pasa completa: antes de este paquete daba 16 rojas. |
| `ruff check app tests scripts` | **limpio** (F811/F821/F823) |
| Captura del golden ×3 orgs | corre y escribe 48 archivos (15+1 por org); de 6 eventos de statement en total a **574** |
| `test_purchase_commissions.py` | 19 ✅ |
| Suites del statement (`integration_14` + `api_money_movements` + `balance_historico`) | 147 ✅ |
| `test_statement_ordering.py` | 3 ✅ (y 3 ❌ contra el código viejo) |
| Smoke ×110 terceros de la réplica de prod | ✅ |
| Golden ×3 orgs | **no corrido** — ver §B.5 sobre por qué acá no es evidencia |
| Parity check | no aplica (cero migraciones) |
