# Informe — Salidas a Willard: el material correcto y los campos determinados

**Plan:** `plan-sac-salidas-material-correcto.md` v1.2 (línea base **`c3ef149`**, criterio de
auditabilidad en **`4ae7433`**) · **Fecha:** 2026-09-08

> La columna *esperado* de la matriz de §2 es **la del plan commiteado en `c3ef149`**, sin
> reescribir. Donde lo observado difirió, hay fila que lo explica — ninguna predicción se movió.

---

## 1. Qué se construyó

**El guard (D1–D6).** Columna `lead_product` (`none | crudo | puro`) en `material_kg_profiles`,
migración `f0a1b2c3d4e5`, `server_default='none'` **en la migración y en el modelo** — la asimetría
que ningún gate cubre (bug (a) de #100; el parity check excluye `server_default` a propósito).

`_validate_lead_products` es **un solo validador** invocado desde `create`, `update`, `review` y
`liquidate` — calco de `_validate_willard_capture` (#81). `annul` queda fuera a propósito (#99):
anular no valida, una salida vieja tiene que poder anularse aunque su material hoy no pasara.

La clasificación sale de `lead_product` y **de nada más**. El comentario de `_compute_lead_kg` ahora
dice explícitamente que la ausencia de fórmula **calcula** (1:1) y no clasifica: usarla para
clasificar es el defecto que este ciclo cierra.

**El tercero (D7).** La regla se partió por tipo, porque como estaba escrita en la v1.1 era
**inimplementable**: una venta descarga `intersede` y esa cuenta no puede tener titular (CHECK en
`kg_ledger.py:110`). Abonos → titular de la cuenta que se descarga (422); venta → cualquier
`customer`, sin cambio.

**Lo demás.** Bodega derivada y bloqueada (D8); tarjetas Horno/Crisol ocultas hasta que exista el
circuito de planta; pantalla de edición nueva + botón *Editar* (D9); las dos etiquetas de maquila
en los 4 mapas que las tenían en inglés y en la unión de tipos (D10).

**El seeder.** 39 materiales con el 9º campo y **PLOMO CRUDO / PLOMO PURO creados**: los dos
productos que Hugo describe como lo entregable no existían en el catálogo. Los `PLO-*` quedan en
`none` hasta Q-31 — marcar uno de más es el único error caro.

---

## 2. Matriz defecto × test — esperado (de `c3ef149`) vs observado

🔴 = el test cae · · = sigue pasando. **Las 9 filas coinciden.**

| Defecto plantado | 1 | 2 | 3 | 4 | 5a | 5b | 6 | 7 | 8 | 9 | 10 | 11 | esperado == observado |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| **a.** Eliminar el validador y sus llamadas | 🔴 | · | 🔴 | 🔴 | · | · | 🔴 | 🔴 | 🔴 | · | 🔴 | 🔴 | ✅ |
| **b.** Clasificar por fórmula, var. A | · | · | 🔴 | 🔴 | · | · | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 | ✅ |
| **c.** Clasificar por fórmula, var. B (= hoy) | 🔴 | · | 🔴 | 🔴 | · | · | 🔴 | 🔴 | 🔴 | · | 🔴 | 🔴 | ✅ |
| **d.** Validador solo en `liquidate` | · | · | · | · | · | · | · | · | 🔴 | · | 🔴 | 🔴 | ✅ |
| **e.** *Belt and suspenders* | · | · | · | · | · | · | · | · | · | 🔴 | · | · | ✅ |
| **f.** No cablear `warnings` en `create` | · | · | · | · | · | · | · | · | · | · | 🔴 | · | ✅ |
| **g.** Quitar la validación de tercero | · | · | · | · | 🔴 | · | · | · | · | · | · | · | ✅ |
| **h.** Comparación invertida (`== 'none'`) | 🔴 | 🔴 | 🔴 | 🔴 | · | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 | ✅ |
| **i.** Sin la llamada en `update` | · | · | · | · | · | · | · | · | · | · | · | 🔴 | ✅ |

Las dos filas que aportó el QA de SAC son las que más pagan: **`e` y `i` caen en un solo test cada
una**, y sin ese test los dos defectos se entregaban **con la suite entera en verde**.

### Las tres divergencias de la primera corrida, y por qué ninguna movió una predicción

| Fila | Primera medición | Causa | Resolución |
|---|---|---|---|
| `h` | caía también el test 5 | **Mi matriz colapsaba 5a y 5b en una columna** y bajo `h` se comportan distinto: 5a pasa (el guard de tercero corre antes), 5b cae | Se **separó la columna**. La predicción original se confirma |
| `b` | caía también el test 1 | Mi defecto plantado usaba un mensaje genérico, y el test 1 verifica el **texto** además del estado | Se hizo **fiel el mensaje** (el que un desarrollador escribiría). La predicción se confirma |
| `e` | idem | idem | idem |

Las tres eran de **instrumentación**, no de comportamiento. La de `h` es la más instructiva: un
par de contraste metido en una sola columna **esconde justo lo que el par existe para mostrar**.

---

## 3. El incidente de la suite, y lo que dejó

La primera corrida completa dio **`11 failed, 1528 passed, 187 errors`** — y el harness reportó
`exit code 0`, que era **el de `tail`**, no el de pytest: la tubería enmascaró el resultado. Misma
familia que el lint sin config de #97 y el golden sobre directorios vacíos de #99, cometida en el
mismo turno en que se estaba citando la lección.

**La causa la introdujo la condición C5.** Hacer `lead_product` obligatorio es correcto —convierte
el borrado silencioso en un 422— pero rompe a **todo** caller que mandaba solo los dos campos
viejos. El plan declaró la re-semantización de los tests de Willard (C3) y **no anticipó los otros
siete archivos** que crean perfiles kg. Producción estaba cubierta (seeder y servicio del
frontend); el daño era todo de tests, y seis de ellos compartían el mismo helper.

**Lo que el incidente aportó de verdad**: dos tests nuevos en `test_material_kg_profile.py` que
van al corazón de C5 y que **no existían** — que omitir el campo dé 422, y **el escenario exacto
que describió QA**: marcar un material como crudo, editarle después el mundo desde Config, y
verificar que la marca sobrevive.

**Lección para el plan siguiente:** una condición que vuelve **obligatorio** un campo de un schema
de escritura tiene un alcance que no se lee en el schema — se lee en **la lista de callers**. La
declaración de re-semantización tiene que salir de `grep` sobre el endpoint, no de la memoria de
qué tests parecen relacionados.

---

## 4. Gates

| Gate | Resultado |
|---|---|
| `ruff` | limpio |
| `tsc` | limpio |
| `eslint` | 0 errores (37/37 del presupuesto, al ras) |
| `npm run build` | OK |
| `schema_parity_check.py` | **DIFF CERO** fuera del baseline |
| Matriz 9 × 12 | **9/9 filas == esperado** |
| Suite completa | **1728 passed, exit 0** (57:02). Exit echado explícito, no el de una tubería — el de la corrida anterior era el de `tail`. Chequeo **fuerte** de mtime limpio: ningún fuente se movió después del **arranque** (no solo del fin). Reconciliación: `1714 − 38 − 8 = 1728 − 50 − 10 = 1668` ⇒ el +14 es enteramente los dos archivos tocados |
| Golden ×3 orgs | **no aplica** — verificado contra `CAPTURES` **con un comando, no de memoria** (`ast.literal_eval` sobre la lista y `set()` de la 2ª posición de cada tupla): **14 entradas / 11 rutas únicas**, ninguna toca willard/kg/tarifas/perfiles; la migración es sobre tabla SAC-exclusiva con 0 filas en las orgs cliente; el router es flag-gated (403 sin `kg_ledger_enabled`, incluso admin) |

🔴 **Esa cifra la conté mal dos veces, y el revisor tenía razón.** El informe decía "12 rutas"; al
verificarlo dije "14 entradas / 14 únicas" y sostuve que el número del revisor (11) estaba mal. Las dos
veces me equivoqué yo: mi extracción tomaba **la primera cadena de cada tupla, que es el NOMBRE de la
captura**, no la ruta — `("pnl_period", "/reports/profit-and-loss", {...})`. Con la 2ª posición dan
**14 entradas / 11 rutas únicas** (`/reports/profit-and-loss` ×2, `balance-sheet` ×2, `balance-detailed` ×2).
La conclusión no se movió — ninguna ruta toca willard/kg/tarifas/perfiles — pero el número sí, y el modo de
falla es el de #98: **verificar contra `CAPTURES` no basta si la extracción mira la columna equivocada**; lo
que cierra el asunto es pegar el comando, no el recuerdo de haberlo corrido.

⚠️ **Lo que ningún gate cubre y hay que mirar en pantalla:** los toasts de aviso (crudo/puro), el
campo de tercero bloqueado, y la pantalla de edición nueva.
