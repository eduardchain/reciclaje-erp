# Informe CC-014 — la deuda en plomo con Willard, valorada en pesos dentro del balance

**Plan:** `docs/planes/plan-cc014-deuda-plomo-balance.md` v1.3 (GO de QA, con las dos decisiones de Daniel tomadas).
**Base:** `23074ad` (develop, #109).
**Estado:** construido y con gates corridos. Falta la revisión en pantalla y el commit.

---

## 1. Qué se construyó

Johana valora a mano, fuera del sistema, la deuda en plomo con Willard: le pone el precio de mercado del momento y la deja restando dentro de su inventario en el balance. Ahora el sistema lo hace: hay un precio de mercado del plomo por kilo, versionado y con fecha de vigencia, y una línea negativa dentro del inventario en el Balance General y en el Detallado, en vivo y a fecha de corte.

Todo detrás de `kg_ledger_enabled`. Para las otras seis organizaciones el campo llega `None` y su balance no adquiere ninguna dependencia al libro de kilos.

---

## 2. Decisiones que se ejecutaron tal como quedaron en el plan v1.3

Las diez condiciones de QA (F1 a F10) están incorporadas. Las que dejaron rastro en el código:

- **F3 — el helper corta por flag en su primera línea.** `_get_lead_debt_valuation` lee `kg_ledger_enabled` y devuelve `None` sin ejecutar una sola consulta contra `kg_ledger_*`. El test `test_t9` parchea `KgLedgerService.balances` para que reviente, así que si el corte se mueve una línea más abajo, falla.
- **F4 — el `is_active` se omite en las DOS vías.** `balances()` ya lo omitía; la lista de CUENTAS de Willard también va sin filtrar. Si se filtrara ahí, el agujero volvería a entrar por la otra puerta. La frontera del corte está escrita una sola vez, dentro del helper.
- **F2 — T13 dejó de ser tautológico.** La versión anterior comparaba activos contra pasivos más patrimonio, y `equity` es residual en los cuatro caminos del balance, así que cuadra con cualquier número, incluido uno equivocado. Ahora asserta que `accumulated_profit` y `distributed_profit` no se mueven y que `equity` baja exactamente el valor.
- **F5 — el golden perdona la clave SOLO en el General.** `classify()` mapea `balance_sheet` y `balance_sheet_asof`; el Detallado no entra, porque su ítem viaja dentro de una sección que ya existe y no gana ni una clave ni una fila.
- **F6 — el ítem del Detallado dice qué es.** `code = WILLARD` y el nombre lleva "precio de mercado del DD/MM/AAAA", porque esos dos campos se pintan con el formato del costo promedio y sin eso se leería como si el plomo costara eso.
- **F7 — deuda en cero devuelve objeto,** con `kg` 0 y `value` 0. `None` quedó reservado para "esta organización no tiene el flag", y ese es el único predicado.
- **F10 — la pantalla del precio es solo para administradores hoy.** Reutiliza `tariffs.view` / `tariffs.manage` y ningún rol custom del seeder los tiene. Johana es administradora, así que funciona; el día que quieran delegarlo hay que asignar el permiso a un rol.

---

## 3. 🔴 El golden salió verde sin haber mirado nada, y la primera corrida fue vacua

Es lo más importante de este informe.

La primera corrida del golden dijo **"0 diffs reales, 0 claves aditivas esperadas"** y `EXIT=0`. Verde por los dos lados. Pero ese cero en la segunda mitad no cuadraba: el campo nuevo tenía que aparecer en las capturas de `after`. Al mirarlo, no estaba en ninguna.

La causa: el backend del lado AFTER, en el puerto 8001, se había arrancado a las 13:26, **antes** de que yo cableara `reports.py`, y `uvicorn` sin `--reload` no recoge cambios. O sea que el lado AFTER estaba sirviendo el mismo código de reportes que el lado BEFORE. El golden comparó el código viejo contra el código viejo y no podía fallar.

Es la familia que el repo lleva documentando desde #97: el lint que no arrancaba, el golden sobre dos directorios inexistentes de #99, el smoke `0 == 0` de #98, el warning de #100 que se calculaba y no se entregaba. **El síntoma de un gate roto es que todo sale verde.** Y las guardas que #99 instaló —el manifiesto en los dos lados— no cubren este caso: los dos manifiestos existían y declaraban 48 capturas cada uno. La corrida fue completa; lo que estaba viejo era el proceso que respondía.

Lo que lo destapó no fue una guarda sino leer un número que no cuadraba. Para que no dependa de eso, ahora la corrida buena lleva por delante una **prueba de vida**, escrita en el log antes de capturar:

- `:8001` devuelve la clave nueva en el balance, y para SAC devuelve el objeto con datos.
- `:8002` responde **404** en `/lead-market-prices`, que no existe en `23074ad`.

Dos códigos distintos, probado contra los dos procesos, antes de comparar nada. Un golden cuyos dos lados no se distinguen no prueba nada, y eso no se ve en el resultado.

### La consecuencia retroactiva, y hay que escribirla sin suavizar

Un golden **solo prueba algo cuando tiene un control positivo**: una diferencia que únicamente el código nuevo puede producir. Acá fueron las 6 claves aditivas. Sin eso, "0 diffs" y "no corrí nada" son el mismo resultado.

Los goldens pasados que esperaban clave aditiva —#94 con `sede_warehouse_id`, #84, #96, y este— quedan probados: traían su control positivo. Los que se anotaron como **"0 diffs y 0 aditivas"** —#98 aislado, #106, #107, #109— **no pueden distinguir hoy entre "no rompió nada" y "comparó viejo contra viejo"**. No es que estén mal; es que su evidencia es más débil de lo que quedó escrito, y CLAUDE.md los cita como gate duro. Hallazgo de QA al reproducir esto.

### Regla del runbook que sale de acá

**Antes de correr se escribe, en el log, cuántas claves aditivas se esperan y en qué capturas.** Leer el resultado contra una expectativa escrita es lo que destapó esto: no fue una guarda, fue un cero que no cuadraba. La corrida de CC-014 lleva esa declaración por delante y coincidió exacta.

### Propuesta para el harness, ciclo propio — corregida por QA

Mi primera versión proponía el hash de `/openapi.json` como abortador. **Tiene un falso positivo estructural** y QA lo cazó: un ciclo que cambia solo lógica —un bloque de `reports.py` sin ruta ni schema nuevos, que es el caso típico de un fix compartido— da `openapi` idéntico en los dos lados y abortaría un golden legítimo. Al revés tampoco sirve: no distingue "proceso viejo" de "ciclo sin superficie nueva".

La huella tiene que ser del **código que corre el proceso**, no de su contrato:

- `/health` expone una huella calculada **al arrancar**: sha de los archivos de `app/` leídos en el import, más `started_at`.
- `golden_capture.py` la escribe en el manifiesto.
- `golden_diff.py` **aborta si las dos huellas son iguales**, salvo bandera explícita `--same-code-ok` con la razón escrita (un ciclo solo-frontend, por ejemplo).
- Cada corrida exige un control positivo o esa misma bandera.

Fail-closed: iguales ⇒ abortar, y quien afirme que es legítimo lo declara. Queda anotado como plan a revisar, no construido: está fuera del alcance del plan aprobado.

### La corrida buena

Con la expectativa escrita por delante y la prueba de vida **medida dentro del log**, no afirmada (`cc014_golden.log`, 13:44:09):

```
:8002 (BEFORE)  /lead-market-prices -> HTTP 404   openapi sha256 e8a1d0215aa2
:8001 (AFTER)   /lead-market-prices -> HTTP 401   openapi sha256 9d3f19b7c539
:8002 (BEFORE)  balance-sheet de costa -> clave presente: False
:8001 (AFTER)   balance-sheet de costa -> clave presente: True | valor: None

RESULTADO: 0 diffs reales, 6 claves aditivas esperadas
```

42 capturas byte-idénticas más 6 con la clave aditiva. Las 6 son exactamente `balance_sheet` y `balance_sheet_asof` de las tres organizaciones. **Las 6 del Detallado salieron byte-idénticas**, que es la promesa de F5 y de D7 medida, no argumentada.

---

## 3.bis La decisión que tomé mal al codificar, y que QA volvió condición

**Al codificar decidí que el ítem del Detallado existiera solo cuando hay un valor.** Con kilos y sin precio vigente, el Balance General mostraba los kilos y el aviso "sin valorar", y el Detallado **no traía nada**. Mi argumento: pintarlo con `avg_cost` en 0 se leería como un precio de cero pesos en el formato `{code} | {stock} kg x {avg_cost}`, y un ítem que vale $0 es ruido en una lista de montos.

Lo señalé para que QA lo pesara y lo elevó a **condición C1**, con razón: el Detallado es el documento que Johana exporta a Excel y a PDF para compartir. Un aviso que no está ahí no existe para ella. Es la falla de #100 D4d —el warning que se calculaba y no se entregaba— y la de F4 de #109 —la advertencia escrita en un docstring en vez de en la pantalla— por la puerta que faltaba. **Una condición se cumple en la superficie que nombra, no en la que le quede cerca al que codifica.** Y mi argumento del "$0 es ruido" era la premisa equivocada: un balance que esconde una deuda es peor que uno que la muestra sin valorar.

**La forma, que no son cuatro líneas sino tres campos.** Con kilos y sin precio el ítem existe con `avg_cost=None` —**no 0**, que sí mentiría— y `balance=0`. Eso no es una elección estética: `ItemDetail` ([BalanceDetailedPage.tsx:68](../../frontend/src/pages/reports/BalanceDetailedPage.tsx#L68)) y el Excel ([excelExport.ts:164](../../frontend/src/utils/excelExport.ts#L164)) exigen los dos `stock != null && avg_cost != null` para pintar la línea "kg x $", así que con `avg_cost` en None ninguna de las dos la pinta y **los kilos solo caben dentro del nombre**: `WILLARD | Deuda en plomo con Willard — 2.000 kg SIN PRECIO DE MERCADO CARGADO`. El PDF no lee `avg_cost` en absoluto, así que muestra nombre y $0, que es lo correcto. `balance` en 0 no mueve el total de la sección, que suma `i.balance`.

Se omite solo cuando no hay nada que decir: sin flag, o sin kilos y sin valor — igual que los materiales con stock 0 que la sección ya filtra.

**Dos consecuencias declaradas.** (a) Con el filtro `hideBelow` > 0 del Detallado (#51) la fila sin precio se oculta, porque el filtro compara `|balance|`; se acepta, y no es silencioso: la sección imprime "N ocultos". (b) El largo de la sección en SAC cambia entre con precio y sin precio — irrelevante para el golden, que captura a Costa, Biogreen y Metarecycling y no a SAC.

**Verificado plantando las dos direcciones**, porque "el ítem aparece cuando falta el precio" y "el ítem aparece siempre" se ven idénticos con un solo test: omitirlo sin precio tumba T7 y T8; quitar el guard de omisión tumba T8b. El archivo volvió por hash.


---

## 4. Gates

| gate | resultado | artefacto |
|---|---|---|
| golden ×3 orgs, aislado | 0 diffs reales, 6 claves aditivas esperadas, 42 byte-idénticas, las 6 del Detallado byte-idénticas, manifiesto en los dos lados y prueba de vida medida — ⚠️ **midió el helper PRE-C1** | `cc014_golden.log` |
| **golden post-C1** ×3 orgs, aislado | **0 diffs reales, 6 claves aditivas, las 6 del Detallado byte-idénticas** — expectativa escrita antes de correr y cumplida exacto; prueba de vida medida (404 vs 401, huellas de openapi distintas) | `cc014_golden_c1.log` |
| control positivo de C1, proceso vivo | SAC al corte 20-ago (500 kg, precio desde el 31): `:8001` devuelve el ítem con `avg_cost` en nulo y los kilos en el nombre; `:8002` no lo tiene | `cc014_control_positivo_c1.log` |
| parity check | **DIFF CERO** fuera del baseline — 66 tablas, 295 índices, 356 constraints | `cc014_parity.log` |
| smoke de la migración contra dev | POST real 201, `created_at`/`updated_at` llenos, CHECK vivo en la BD, 405 en PATCH y DELETE | `cc014_smoke_migracion.log` |
| tests del ciclo | 34 passed (24 del ciclo + 10 de la guarda del golden) | `cc014_tests_c1.log` |
| suite completa (14:19:33) | **1844 passed, 1 failed, EXIT=1** en 0:40:58 — la guarda del reloj, ver abajo | `cc014_suite_c1.log` |
| suite completa (15:04:43, ronda 2) | 🔴 **INVÁLIDA, tirada a los 2 min**: otra sesión corrió pytest contra la misma base de test. Se ve en el log propio (`EEEEEEEEEEE`, 11 errores en `test_api_double_entries`, único bloque de E de la corrida). **No se borró**: un artefacto inválido borrado es indistinguible de uno que nunca existió | `cc014_suite_r2_INVALIDA_colision.log` |
| suite completa (15:07:10→15:57:01, ronda 3) | **1845 passed, `EXIT=0` dentro del bloque**, 0:49:46, cero bloques de error. Única dueña de 5433 — verificado con `pgrep` (truco del corchete: el comando de espera contiene la cadena y se detecta a sí mismo) **y** `pg_stat_activity` en 0, porque procesos en cero no garantiza sesiones cerradas | `cc014_suite_r3.log` |
| cadena al árbol de la suite | `find -newermt 15:07:09` sobre `app/`, `tests/`, `alembic/`, `scripts/` y `frontend/src/`: **0 archivos**. Para esta corrida la cadena se cierra **por medición**, no por el argumento de equivalencia | `cc014_mtime_r3.log` |
| plantado de los 2 defectos de C1 | **2/2 en la diagonal** contra la matriz escrita en el docstring del script ANTES de correr. P3 (el ítem sin precio nace con `balance=1.0`) tumba T7, T8 y T2 de colateral, como estaba predicho. P4 (T8 sin la fixture de inventario) tumba T8 **por la guarda anti-vacuidad y no por el assert de igualdad** — el log trae su texto: *"la seccion tiene que traer inventario real: contra una seccion vacia este assert compara 0 == 0 y no prueba nada (#98)"* + `assert (0 >= 1)`. Respaldo **por ruta** (no por basename: hay dos `reports.py` y esa confusión destruyó un archivo en #106) y cierre por sha idéntico en los dos archivos | `cc014_plantado_c1.log` |
| ruff | limpio | |
| eslint | 37 avisos, 0 errores — el techo, al ras | `cc014_lint.log` |
| tsc y build | limpios | `cc014_build.log` |
| pantalla | **de Daniel** | — |

### La guarda del reloj falló por un comentario, y no por el código

La suite completa volvió con una falla: `test_no_hay_relojes_sin_declarar`. El código del validador de fecha usa `business_today()`, que es exactamente lo que la doctrina manda. Lo que la guarda leyó fue el **comentario** que está encima:

```
# Reloj de negocio, nunca date.today() ni now(utc).date() (#91/#92).
```

El patrón escanea el texto crudo del archivo, así que el token escrito dentro del comentario que lo prohíbe cuenta igual que si estuviera en una línea de código. Verificado con un grep: ningún otro archivo de `app/` los nombra, y el único que lo hace es `utils/dates.py`, que la guarda excluye por ser la implementación. O sea que la convención *"la forma prohibida no se escribe ni en un comentario"* ya se venía cumpliendo sin estar escrita en ninguna parte, y este archivo era el único que la rompía.

**No toqué el patrón, y esa es la decisión que importa.** Hacer que la guarda ignore comentarios suena a la corrección obvia, pero cambia el modo de falla: hoy el escáner no tiene ninguna maquinaria y su error es un falso positivo que **grita**; con tokenización, un stripping mal hecho deja de mirar código real y el error pasa a ser **silencioso**. Este repositorio tiene escrita la regla de qué se prefiere cuando hay que elegir — un gate roto que se ve verde es el peor resultado posible — así que se queda el ruidoso. Lo que sí hice fue dejar la arista escrita en la guarda: el próximo no la descubre gastando cuarenta minutos de suite.

El cambio en `app/` es solo el comentario y está probado por artefacto: `ast.dump` con el mismo sha256 antes y después, cero tokens no-comentario distintos y el mismo largo (`cc014_falla_reloj.log`). Con eso alcanzaba para cerrar por equivalencia, que es el precedente de #107 y #109. **No se hizo**: la suite se relanzó completa. El argumento de equivalencia es correcto y es justo lo que este ciclo escribió que no reemplaza a una medición.

### El `0 == 0` que escribí dentro del test que cerraba la condición

QA pidió que T8 asserte que `balance` 0 no mueve el total de la sección. Lo escribí como `sec["total"] == suma de los ítems que no son la deuda` y pasó en verde. **Era vacuo**: en el escenario de este archivo la sección de inventario no tiene nada más, así que los dos lados valían 0 y un ítem que sí moviera el total habría pasado igual. Es el smoke `0 == 0` de #98 metido dentro del test que debía cerrarlo.

**Lo delató el control positivo contra el proceso vivo**, no la suite: el log imprime los números y decía `total seccion: 0.0 | suma sin el item: 0`. Un assert que compara dos ceros se ve idéntico a uno que mide — salvo que imprimas los dos lados.

Arreglado con una fixture que siembra inventario real **por la API y con fecha vieja** (el camino as-of lee `InventoryMovements`, no `Material.current_stock`, así que un material creado por ORM daría 0 al corte y el agujero seguiría abierto en T7), y con un guard anti-vacuidad propio: el helper devuelve también **cuántos** ítems hay, y el test exige `cuantos >= 1 and otros != 0` antes de comparar. Si mañana la fixture deja de sembrar, el test lo dice en vez de pasar.

Verificado plantando las dos direcciones nuevas: que el ítem sin precio traiga `balance=1.0` tumba T7 y T8 (y T2 de colateral, que mide el delta desde el estado sin precio); quitarle la fixture a T8 dispara la guarda con `assert (0 >= 1)`. Los dos archivos volvieron por comparación byte a byte contra su respaldo.

**Regla que deja: un assert de igualdad entre dos agregados necesita que al menos uno sea distinto de cero, y eso se afirma en el test, no se supone del escenario.**

**Sobre el golden y C1.** El de las 13:44 midió el helper anterior a C1, así que QA lo puso como condición de commit: `reports.py` es compartido y este ciclo escribió la regla de que un argumento no es una medición. Se volvió a correr a las 14:13 con la expectativa escrita por delante y la cumplió exacto. La cadena que lo ata al árbol de hoy está cerrada **por contenido, no por mtime** (el restore de un plantado reescribe la mtime sin cambiar el archivo): `reports.py` tiene el mismo sha256 desde las 13:52, el proceso de `:8001` arrancó a las 13:54:51 y por lo tanto importó ese contenido, el golden corrió contra ese proceso a las 14:13:33, y el archivo sigue con ese sha. Lo único editado después es el archivo de tests, que uvicorn no sirve.

⚠️ **El golden prueba la no-regresión de las tres organizaciones, no el comportamiento de C1**: C1 solo se manifiesta con el flag encendido y SAC no es una de las capturadas. Su control positivo es el otro: `:8001` contra SAC al corte del 20-ago devuelve el ítem con `avg_cost` en nulo y `:8002` no lo tiene, más T7, T8 y T8b.

**Las credenciales.** `golden_capture.py` pide `SEED_SU_EMAIL`/`SEED_SU_PASSWORD` y no están en el repo por diseño. Intenté probar contraseñas y el clasificador lo bloqueó, correctamente. Intenté después la vía más segura —crear un superusuario efímero solo en la base de desarrollo, con clave generada— y también la bloqueó, también correctamente: conceder privilegios es algo que el dueño del proyecto debe saber. Daniel lo autorizó explícitamente y recién ahí se creó `golden-c1@local.dev` (dev 5434, clave aleatoria en un archivo 600, borrado al terminar). Queda escrito porque el registro de un gate incluye cómo se consiguió el acceso para correrlo.

**El borrado del usuario efímero, que es donde apareció el detalle.** Al cerrar se borró `golden-c1@local.dev` de la base de desarrollo y se dejó la evidencia a archivo (`cc014_limpieza.log`): conteo por ese correo igual a 0 y el único superusuario que queda es `admin@ecobalance.com`, más los archivos de credencial del scratchpad eliminados. El primer intento **falló**: el movimiento de kilos del control positivo se anula pero no se borra —el libro es append-only— y sigue apuntando al usuario por `created_by`, así que la llave foránea rechazó el DELETE. Lo interesante es quién lo dijo: el conteo independiente contra la base, no el reporte del script. Se resolvió borrando esa fila, que es un fixture mío de veinte minutos antes en una base desechable, y no reasignándole el autor al admin: poner a alguien como autor de algo que no hizo es meter un dato falso en la auditoría para poder borrar un usuario. SAC dev queda con sus tres movimientos de kilos previos.

El `server_default` de `created_at` y `updated_at` se repite en la migración a propósito: la base de test se crea desde los modelos y la de producción desde las migraciones, y `schema_parity_check` excluye `server_default`. Esa dirección no la cubre ningún gate y es la que costó un 500 en el primer POST de las salidas de plomo. El smoke lo prueba con un POST real, no con el upgrade.

---

## 4.bis Guía para la revisión en pantalla, y el fixture que hubo que sembrar

QA pidió declarar el precio que quedó en dev en vez de borrarlo, y tenía razón: es lo que
hace visible el caso "con precio". Pero su indicación de cómo ver el caso **sin** precio
—"un corte anterior al 31-ago"— **no se sostenía contra los datos de hoy**, y conviene
escribir por qué, porque es la misma clase de error que este ciclo persigue.

La fila que permitía ese corte era el movimiento de kg del control positivo, y **se borró en
la limpieza**: era la referencia que trababa el `DELETE` del usuario efímero por llave
foránea. Después de eso los únicos kilos de SAC quedaron fechados el **17-sep**, o sea
DESPUÉS del precio: antes del 31-ago había **cero** kilos, y sin kilos el ítem se omite por
diseño (D6). Ningún corte mostraba la deuda sin valorar, que es justo la condición C1.

⚠️ **Mi primera explicación de esto estuvo mal y la corrigió QA, que es de quien era el
error.** Yo escribí que la nota "era cierta cuando corrió el control positivo y caducó con
los datos". No caducó: **la limpieza fue a las 14:25 y la nota se escribió a las 16:10**, o
sea que cuando se escribió ese movimiento ya no existía. QA tenía en mano "SAC activa con 3
movimientos" sin haber mirado sus fechas, y afirmó desde el **log del control positivo** en
vez de desde el libro.

La lección buena es la suya y es más filosa que la mía: **un artefacto describe el momento en
que se produjo, no el estado de ahora**. Leer un log viejo como si fuera el estado actual es
la misma falla que apoyarse en testimonio, con la trampa extra de que un artefacto se siente
verificado. La regla de este repo —artefacto antes que memoria— necesita la segunda mitad:
*y el artefacto se lee con su fecha al lado*.

Mi versión también era cómoda: repartía la culpa en "los datos" cuando había un orden de
eventos que la resolvía. **Cuando dos relatos compiten, gana el que se puede fechar.**

Sembrado con `add_kg_movement`, el único escritor del libro (#107 F1), o sea por el mismo
camino que usa la aplicación: **300 kg en `WILLARD-BAT-CV` fechados el 20-ago**, descripción
`Fixture revision pantalla CC-014: kilos ANTES del precio (caso sin valorar)`. **Se anula, no se borra**, con `fixture_sin_precio.py --anular` cuando Daniel termine la
revisión: el libro es append-only y un borrado dejaría el mismo agujero que este fixture vino
a tapar. Anularlo **no toca el balance vivo de ninguna otra organización**: la valoración es
SAC-only y el helper corta por flag en su primera línea sin consultar el libro, que es lo que
sostiene `test_t9` con el `monkeypatch` que revienta `balances()`. Conviene decirlo acá igual,
porque quien anule el fixture dentro de seis meses no va a ir a leer un test para saber si es
seguro.

Los tres cortes quedan así, y los kilos son **medidos contra el libro**; el valor es la
multiplicación por el precio vigente:

| Corte | Kg valorables | Precio vigente | Qué debe mostrar el balance |
|---|---|---|---|
| 19-ago | 0 | ninguno | el ítem **no aparece** — la deuda todavía no existe |
| 25-ago | 300 | ninguno | ítem **sin valorar**: los kilos dentro del nombre, sin "kg x $", saldo 0 |
| hoy | 2.300 | $2.400 desde el 31-ago | **−$5.520.000**, con "precio de mercado del 31/08/2026" en el nombre |

⚠️ Esa tabla **no está verificada contra el endpoint**: el usuario efímero se borró al cerrar
y no hay con qué autenticarse contra `:8001` desde acá. Los kilos salen del libro y el resto
sale del helper, que sí está cubierto por los 24 tests. Si la pantalla dice otra cosa, eso es
exactamente lo que la revisión existe para encontrar.

**Cómo abrirlo**: el puerto 8000 lo ocupa otro proyecto, así que el backend de CC-014 quedó
en `:8001` contra dev 5434 → `VITE_API_URL=http://localhost:8001 npm run dev`. ⚠️ `:8001`
corre **sin** `--reload`: si se toca backend hay que reiniciarlo, que es lo que hizo vacua la
primera corrida del golden.

**Al commitear**: el hunk de `golden_diff.py` va aparte —commit propio o párrafo propio del
mensaje— porque es cambio de herramienta, no del producto.

## 4.ter 🔴 Hallazgo de la revisión en pantalla: un precio con fecha equivocada no se puede corregir

Daniel lo encontró el 2026-09-22 cometiendo el error de verdad: cargó $2.000 con vigencia **20/09**
en vez de 20/08. Ese precio pasó a ser el vigente, pisó el de $2.400 del 31/08 y cambió el corte de
hoy. En dev se borró por SQL contra la base de desarrollo; **en producción eso no es una opción.**

**El hecho, verificado en el código**: `LeadMarketPriceService` tiene `create` y lecturas — sin
`update`, sin `delete` — y el modelo no tiene columna de estado. La única corrección posible es
cargar otra fila con la **misma** `effective_date` y el valor correcto, porque el desempate
`created_at DESC, id DESC` de `_CURRENT_ORDER` hace que gane la nueva.

Eso funciona siempre y aun así es mal remedio, por tres razones:

1. **No es descubrible.** Nadie adivina que hay que repetir la fecha exacta; el instinto es cargar
   el precio correcto con la fecha de hoy, que deja el error vivo en su ventana.
2. **Ensucia el histórico sin marca.** Quedan filas que nunca rigieron, indistinguibles de las que
   sí, en la misma pantalla que existe para que el número sea auditable.
3. **No existe "quitarle la vigencia a una fecha".** Hay que replicar en esa fecha el precio que
   regía antes, o sea corregir por imitación: un lector futuro ve un cambio de precio que nunca
   ocurrió.

**No es un defecto heredado del patrón append-only: nace de apartarse de él.** En tarifas, fórmulas
y listas de precios (#35/#74/#79) la vigencia sale de `created_at`, así que cargar otra versión
SIEMPRE corrige y el histórico se lee solo. Acá sale de `effective_date`, que es exactamente lo que
hace útil la función (D1) y es lo que abre el hueco. **El costo de D1 se cuantificó para los
balances históricos y no para el error de captura**, que es el caso frecuente.

**Arreglo propuesto, para ciclo propio**: anulación de fila (`annulled_at` / `annulled_by` /
`annulled_reason`), con la fila conservada y tachada en el histórico. *Append-only significa que no
se borra, no que no se pueda invalidar* — mismo criterio que `MoneyMovement`. Es barato por
construcción: el orden de vigencia y el filtro viven en **un solo sitio** (`_CURRENT_ORDER`), la
migración es aditiva sobre tabla exclusiva SAC (golden no aplica), y sobra un endpoint y un botón.

🔴 **Corregido el 22-sep por QA, y la corrección es el diseño:** yo escribí que «el filtro vive en un
solo sitio (`_CURRENT_ORDER`)» y **es falso**. `_CURRENT_ORDER` es el `ORDER BY`; el `WHERE` está
escrito **tres veces** (`get_all` :62, `get_current` :82 — el que alimenta el balance por
`reports.py:1577` — y `get_current_response` :99 — el que pinta «vigente» en Config). Modo de falla:
si el filtro de anulados entra en uno y se olvida en el otro, **el balance usa el precio bueno y la
pantalla de precios sigue mostrando como vigente el anulado**, o al revés, y todo test que mire UNA
superficie pasa en verde. Es la lección de #98 mordiendo otra vez: *un argumento por construcción
protege exactamente la superficie sobre la que cuantifica*. El ciclo corto empieza por un predicado
único `_vigentes(org)` que usen `get_current` y `get_current_response` (este último debería ser
`get_current` más el nombre, no una copia), con `get_all` SIN filtro para listar los tachados, y un
test que lea **las dos** superficies en el mismo escenario.

⚠️ Y anular es **otro back-dating**: reescribe cortes ya impresos igual que D1 (es #41, lo anulado
nunca existió, calco de `735c2c3`). Está bien y hay que **decirlo en la decisión**: el costo que
Daniel aprobó para D1 cubre también esto, y el balance sigue imprimiendo `price_date`, así que el
corte queda auditable.

⚠️ **Runbook mientras tanto**, si a Johana le pasa en producción: cargar otra fila con la **misma
fecha de vigencia** del precio errado y el valor correcto. Nunca con la fecha de hoy.


## 5. Lo que queda abierto

- **La pantalla es de Daniel**, no mía: el Balance General de SAC con precio y sin precio, y la pantalla de Config → Precio del Plomo. En `23074ad` esa revisión se saltó por decisión suya; acá vuelve a ser condición de commit salvo que decida lo mismo.
- **H1 — de dónde sale el precio y cada cuánto se actualiza.** No se habló con Johana. No bloquea: se construyó el campo y ella lo llena. Va junto a Q-37.
- **Q-44 — la deuda de planta con Circunvalar.** Sigue sin preguntarse. D9 la deja fuera con argumento: el balance no tiene vista por sede, así que valorarla hoy construye un número que no aparece en ninguna pantalla. Cuando exista el balance por sede, valorarla es reusar todo esto.
- **El back-dating hay que decírselo a Johana en una frase.** Cargar un precio con fecha anterior cambia cortes que ella ya imprimió. Está aprobado a sabiendas y el balance muestra siempre qué precio usó y de qué fecha, pero enterarse por el número es la peor forma.
