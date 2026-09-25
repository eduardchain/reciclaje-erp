# Informe — anulación del precio de mercado del plomo (ciclo corto sobre CC-014)

**Commit:** `6832922` en `develop`, sin push. 10 archivos, 776 inserciones.
**Plan:** `plan-anulacion-precio-plomo.md` v1.1, con la matriz defecto × test commiteada en `97c2aed` **antes** de plantar.
**QA:** GO condicionado (C1–C5) y después GO de commit, con el árbol verificado contra la suite r3.

## 1. Qué lo detonó

No salió de un plan: salió de la pantalla. Daniel tipeó mal la fecha de vigencia de un precio durante la revisión de CC-014 y descubrió que no había forma de corregirlo. El recurso era append-only sin anulación.

**Append-only significa que no se borra, no que no se pueda invalidar.** Es el criterio que el repo ya usa en `MoneyMovement`: la fila queda, tachada y con su motivo.

## 2. La decisión que sostiene el ciclo (D3)

`get_current` es el **único** selector del vigente, y `get_current_response` lo **llama** en vez de repetir el query.

🔴 En el plan v1.0 yo afirmé que "el filtro vive en un solo sitio". **Era falso**, lo desmintió QA y lo verifiqué con grep: lo compartido era `_CURRENT_ORDER`, o sea el **ORDER BY**. Los `WHERE` estaban escritos **tres veces**.

Con el filtro de anulados repartido en copias, el modo de falla es silencioso: el balance usa un precio y la pantalla muestra otro como vigente, y **todo test que mire una sola superficie pasa en verde**. Por eso el test estrella lee las dos por HTTP en el mismo escenario.

Dos corolarios que no son cosméticos:

- El filtro va **fuera** del `if cutoff_dt`. Adentro protegería uno solo de los dos caminos del balance, el vivo o el as-of, y el otro seguiría usando el anulado.
- `get_all` queda **sin filtro a propósito**: un histórico que esconde lo anulado no sirve para auditar nada. Consecuencia: "el primero de la lista" ya no es el vigente, y la pantalla lo pregunta a `/current` comparando **por id, nunca por índice**.

## 3. El hallazgo del ciclo, y es de gates

**`test_a8` era vacuo.** Al plantar "cambiar el permiso de anular de `tariffs.manage` a `tariffs.view`", los **38 tests pasaron**. El test usaba un usuario de **otra organización**, que no tiene **ningún** `tariffs.*`: ese 403 no distinguía `view` de `manage`. Un test cuyo nombre promete más de lo que cubre — misma familia que el `0 == 0` de #98 y el assert vacuo de #110.

Se cierra con un rol custom que tiene `view` y no `manage` (el admin bypassa y no prueba nada, #29) y con el **GET en 200 como control positivo**: sin él, un 403 podría venir de la bandera de la organización o de la membresía, y el test diría que el permiso funciona sin haberlo tocado nunca.

🔴 **Y el mismo agujero estaba del lado de cargar, en código ya commiteado de CC-014** (`86101b0`). Lo encontró QA yendo al verbo hermano: el `POST` de creación también exige `manage` y tampoco se probaba.

> **Regla que deja, y es de alcance: cuando un test de permiso resulta vacuo, el barrido correcto es enumerar por grep todos los endpoints que piden ese permiso, no arreglar el que saltó.**

Es #92/#96 ("el grep de una sola forma sintáctica no es un barrido") y #108 ("verifiqué un miembro de una familia y lo apliqué a nueve") en su versión más barata de cometer. Yo arreglé el que saltó.

## 4. El parity check también encontró lo suyo

Le había puesto **nombre explícito** a la llave foránea, y `create_all` —de donde nace la base de test— la nombra como la nombra Postgres. Divergencia permanente entre la base de test y la de producción.

El detalle que confirma que era error mío: **las otras dos llaves de esa misma tabla, creadas por la migración de CC-014, ya usaban el nombre por defecto.** Rompí la convención de mi propia tabla.

Se corrigió **en la migración**, no con un `ALTER` a mano sobre dev, y se verificó bajándola y volviéndola a subir para que el nombre correcto salga de ella. El primer `downgrade` falló por la trampa ya documentada en #100: editar una migración ya aplicada deja el downgrade buscando lo que la versión vieja nunca creó.

## 5. Gates

| Gate | Resultado | Artefacto |
|---|---|---|
| Suite completa | 1861 passed, `EXIT=0` dentro del bloque, 1:30:00 | `/tmp/anul_suite_r3.log` |
| Cobertura del árbol | 0 archivos fuente tocados desde el inicio | `find` sin `__pycache__` |
| Parity check | DIFF CERO, 66 tablas / 295 índices / 357 constraints | `/tmp/parity_anul.log` |
| Plantado, tanda 1 | 11 defectos, cierre por sha256 OK | `/tmp/plantado_anul.log` |
| Plantado, tanda 2 (C1–C4) | 4 defectos, cierre por sha256 OK | `/tmp/plantado_qa_c1c4.log` |
| tsc / eslint / build | limpio, 37 = techo sin subirlo, OK | — |
| Pantalla | cerrada por Daniel **con control positivo** | testimonio, registrado como tal |

**Tres rondas de suite, y las dos primeras quedaron invalidadas por cambios propios, no por fallas.** La r1 (1859) por el test que nació del plantado de P7; la r2 (1860) por el que pidió QA para el `POST`. En las dos se relanzó entera en vez de argumentar equivalencia, que es la regla que #110 dejó escrita.

⚠️ **El chequeo de mtime da 1 si no se excluye `__pycache__`**, y es un falso positivo: la propia corrida escribe los `.pyc` a los dos segundos de arrancar. El `find` lleva `-not -path "*/__pycache__/*"`.

## 6. El control positivo de la pantalla

El primer intento **no discriminaba**. Daniel anuló un precio que no era el de mayor vigencia, así que la fila correcta seguía siendo la primera de la lista y el código viejo —que marcaba el vigente por índice— se habría visto exactamente igual.

Se cargó un precio de mayor vigencia y se anuló **ese**: el distintivo de vigente quedó en la **segunda** fila. Eso es lo único que distingue el arreglo de no haber arreglado nada.

Verificado también por endpoint con todo anulado: `/current` en `null`, el balance con 2.100 kg y precio y valor en `null`, y el ítem del Detallado dentro de la sección de inventario con `avg_cost` en `null` —no en 0— y los kilos dentro del nombre.

## 7. Golden: no aplica, y se midió

No es que pasaría: es que el código nuevo es **inalcanzable** para las tres organizaciones del golden.

| Medición | Resultado |
|---|---|
| ¿`reports.py` cambia? | no, `git diff --name-only` |
| ¿Quién alcanza el servicio? | 5 llamadores, los 4 del router detrás de `require_org_flag` y el de `reports.py:1577` dentro del helper que corta por bandera en 1548 — el `import` vive **después** del `return None` |
| ¿Filas fuera de SAC? | cero |

Y una razón para no correrlo igual: este ciclo no agrega ninguna clave a las capturas, así que daría "0 diffs y 0 aditivas", que es exactamente el resultado que #110 demostró que **no distingue** entre no haber roto nada y haber comparado el código viejo contra sí mismo.

## 8. Donde mis predicciones fallaron, sin reescribir la matriz

- **P10**: escribí "cae A3 y solo A3" y cayeron cinco. Vive en `reports.py`, la vía por la que pasan todos los tests del balance. Lo notable es que **la matriz commiteada era más correcta que mi predicción del día**, y que la regla ya estaba escrita en el propio plan, a propósito de otro defecto: *un defecto en vía compartida cae de más, y la predicción se escribe "al menos estos"*.
- **P9**: predije cuatro caídas y cayó una. Me equivoqué yo, no la cobertura: `get_current` filtra los anulados **antes**, así que todos los candidatos empatan en ese criterio y el orden efectivo no cambia. Solo `get_all`, que incluye anulados, se ve afectado.
- **P11**: anuncié que tumbaría casi todo y tumbó dos.

**Ninguna caída fue en la dirección peligrosa** —un test que debía caer y no cayó— en ninguno de los 15 defectos. Esa es la única que importa, y es la que destapó el problema de los permisos.

## 9. Residuos declarados

1. **Anular es otro back-dating.** El precio deja de regir en todos los cortes, incluidos los ya impresos. Coherente con #41 y cubierto por el costo que Daniel aprobó el 21-sep para la vigencia por fecha de negocio. El balance sigue imprimiendo `price_date`, así que el corte queda auditable.
2. **Sigue sin PATCH ni DELETE.** Anular no afloja el append-only; dos tests lo fijan.
3. **El aviso previo al guardar** (§7 del plan) no entró: lo decide Daniel.
4. **La pantalla del precio es hoy solo para administradores.** Reutiliza los permisos de tarifas y ningún rol del sembrado los tiene. Delegarla exige asignar el permiso a un rol.
5. **Dev queda con los tres precios anulados**, que es el estado en que Daniel cerró la revisión.
