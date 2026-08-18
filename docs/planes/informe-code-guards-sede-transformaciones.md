# Informe de construcción — Guards de sede y tránsito en transformaciones (T0')

**Fecha:** 2026-08-18 · **Plan:** `plan-guards-sede-transformaciones.md` (GO de QA sin condiciones)
**Migraciones:** ninguna · **Rama:** develop, sin commitear

---

## 1. Lo que se construyó

| Pieza | Dónde |
|---|---|
| `sede_of()` — función de módulo | `services/transfer.py` |
| `validate_same_sede()` — guard T0' (H2) | `services/transfer.py`, al lado de `validate_not_transit_warehouse` |
| Llamada al guard de tránsito (H1) | `services/material_transformation.py::_validate_warehouse` |
| Llamada al guard de sede (H2) | `services/material_transformation.py::create`, dentro del loop de líneas |
| `TransferService._sede_of` delega | `services/transfer.py` |
| 8 tests | `tests/test_api_material_transformations.py::TestGuardsSedeYTransito` |

**Tránsito** entra en `_validate_warehouse`, que es el único punto por el que pasan **tanto el
origen como cada destino** — un renglón cubre los dos huecos. **Sede** necesita el par, así que va
en el loop, usando el warehouse que `_validate_warehouse` ya devolvía y que antes se descartaba.

`TransferService._sede_of` ahora delega en la función de módulo: **"sede" está definido una sola
vez** para traslados y para el guard (D4 del plan, mismo criterio que D4 de #98).

---

## 2. Dos cosas que cambié respecto de lo que escribí en el plan

**El argumento de fondo es el de QA, no el mío.** El plan apoyaba la decisión de bloquear en los
transcripts de Johana y Hugo. QA señaló —con razón— que eso es *testimonio*: el cliente describiendo
su operación de hoy no decide por sí solo cómo debe modelarse. El argumento estructural es más
difícil de voltear y quedó escrito en el docstring del guard, que es donde lo va a leer quien lo
herede:

> **Una transformación no tiene recepción.** El traslado está en dos pasos justamente para
> garantizar que lo que salió llegó — segundo pesaje, tolerancia, `DiscrepancyTask` — y de ese
> control cuelgan la deuda de plomo intersede y la maquila. Emitirlas desde una transformación
> crearía el efecto financiero **soltando el control físico que lo justifica**: una deuda que nadie
> pesó.

Los transcripts quedan como evidencia de apoyo: confirman que el camino soportado es el que el
cliente ya usa, o sea que bloquear no le cuesta nada a SAC.

**El mensaje del 400 nombra las dos bodegas**, no solo el hecho (pedido de QA): con seis bodegas en
pantalla, *"pertenecen a sedes distintas"* obliga a adivinar cuál. Hay un test que lo fija
(`test_mensaje_nombra_las_dos_bodegas`), porque un mensaje se degrada en el primer refactor si nada
lo sostiene.

**Y una nota que QA pidió dejar escrita para no re-derivarla:** `create` tiene **un solo llamador**
—su propio endpoint— verificado en este ciclo. Fuera de ahí, `material_transformations` solo
aparece en `reports.py` leyendo los modelos para las tres líneas del P&L, y en el registro del
router. Por eso el riesgo de #98 (el daño entrando por los llamadores, no por los datos) no se
repite acá.

---

## 3. Verificación de los tests contra defectos plantados

Los 8 pasaron a la primera, así que se rompió el código a propósito:

| Defecto plantado | Qué falló |
|---|---|
| Quitar el cortocircuito por flag de `validate_same_sede` | 🔴 `test_org_sin_flag_transforma_entre_bodegas` — **la regresión de las 6 orgs** — y de paso el test de `annul`, que crea sin flag |
| No llamar `validate_same_sede` | `test_con_flag_cruzar_sedes_bloquea` y `test_mensaje_nombra_las_dos_bodegas` |
| No llamar `validate_not_transit_warehouse` | `test_origen_en_transito_bloquea` y `test_destino_en_transito_bloquea` |

El primero es el que importa: es el defecto que un guard escrito de la forma obvia habría tenido, y
el que ningún gate automático habría visto.

---

## 4. Gates

| Gate | Estado |
|---|---|
| Tests del ítem | ✅ 8 (suite del archivo: 28) |
| Suite completa | ✅ **1639 passed** (42:08) |
| `ruff check app tests scripts` | ✅ |
| **Golden ×3 orgs** | ✅ **0 diffs reales, 0 claves aditivas** — 48 capturas por lado |
| Parity check | no aplica (sin migraciones) |

El golden se corrió aislado: `origin/main` (que ya trae el tren deployado hoy) en :8001 contra el
árbol de trabajo en :8002.

**Corrección de un conteo del canon, encontrada al cerrar este informe:** CLAUDE.md decía
`Current: 1657 tests` y el número real es **1639**. El error fue mío en #98: sumé los 29 tests del
ítem a una corrida de 1628 que **ya incluía 26 de ellos** (los 3 restantes, los de D10, se
escribieron después de esa corrida). El cuadre exacto es `1628 + 3 + 8 = 1639`. Corregido en el
canon y anotado en la decisión #98.

### 🔴 El golden dio un verde falso en la primera corrida

Vale contarlo porque es un defecto **del gate**, no del ciclo.

La primera corrida reportó *"RESULTADO: 0 diffs reales"* — y era mentira: `golden_capture.py` había
abortado en los dos lados por faltarle `SEED_SU_EMAIL`/`SEED_SU_PASSWORD`, así que `golden_diff.py`
comparó **dos directorios inexistentes** y no se quejó. Se detectó mirando el conteo de archivos, no
el veredicto.

Es la misma familia que el smoke `0 == 0` de #98: **un gate que no corrió se ve idéntico a un gate
que pasó.** Corregido en la corrida real (48 archivos por lado, verificado antes de leer el
resultado).

**Propuesta, fuera del alcance de este ciclo:** que `golden_diff.py` aborte si algún lado tiene cero
capturas o si los dos lados no tienen el mismo conteo. Son dos líneas y convierten un verde falso en
un error. Pendiente de la decisión de Daniel.

---

## 5. Lo que este ciclo NO hace

- **No decide qué es el molino.** Ese es T0/T1 y sigue bloqueado por la tabla de estándares que no
  se le ha pedido a Johana. Este guard hay que ponerlo igual, cualquiera sea la respuesta.
- **No emite kg ni maquila desde una transformación** — ver §2.
- **No toca el frontend.** El 400 se muestra como cualquier otro error del backend. Si la operación
  resulta frecuente, avisar antes de guardar es un ciclo aparte.
- **No revisa datos históricos.** El guard aplica de aquí en adelante; la transformación de Costa
  que cruza bodegas sigue existiendo y sigue siendo anulable.

---

## 6. Dónde mirar más duro

1. **El par de tests de sede.** Es lo único que distingue *"el guard funciona"* de *"lo apagué para
   todos"*. Si alguna vez uno de los dos se borra por parecer redundante, el guard queda sin red.
2. **`validate_same_sede` vive en `transfer.py`.** Es donde está su hermana y donde viven los
   helpers de sede, pero el nombre del archivo ya no describe todo su contenido. Si aparece un
   tercer consumidor, vale mover los tres guards a un módulo propio.
3. **El flag como predicado.** `two_step_transfers_enabled` significa hoy "esta organización piensa
   en sedes". Si algún día se separan los dos conceptos —traslados en dos pasos por un lado, sedes
   por otro— este guard hay que revisarlo.
