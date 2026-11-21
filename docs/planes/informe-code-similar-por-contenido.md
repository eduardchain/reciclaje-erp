# Informe: aviso de proveedor parecido por contenido

Plan: `plan-sac-similar-por-contenido.md` v1.1 (GO de QA 1; Daniel autorizó, O1 = solo avisa). Nivel: lógica. Rama `coder-1/aviso-similar` sobre develop `d3c6919`, con develop `693a85f` traído en `4926ee9`. Cero migraciones.

Evidencia: `~/sac-evidencia/2026-11-20/coder-1-similar-contenido/`.

## 1. Qué cambió

- **`backend/app/utils/name_match.py` (nuevo).** `name_match_kind(new, old)` devuelve `exact`, `similar` o None, y es simétrica. Decide en este orden:
  1. `normalize_entity_name` igual → `exact`.
  2. Regla A: concatenación de palabras significativas igual.
  3. Camino C: concatenación cruda igual.
  4. Regla B: el conjunto de palabras significativas de un nombre está contenido en el del otro, en cualquier dirección, y el lado contenido tiene ≥ 2 palabras o ≥ 8 letras.

  Es la función `c_final` que se midió en el plan, y C2 lo comprueba par por par (§3).
- **`find_similar`.** Cada resultado lleva `match`.
  - Los exact van todos y primero; los similar van ordenados por nombre normalizado y con tope `SIMILAR_LIMIT = 5`.
  - La identificación igual sigue siendo `exact` (D4).
  - El criterio corre solo sobre `candidates`, que ya están filtrados por org, activos, sin entidades de sistema y por el alcance de recolector (#129). No abre una consulta propia, así que no puede revelar lo que el alcance esconde.
- **`CreateSupplierDialog`.**
  - Con algún exact, bloquea como hoy: «Ya existe(n):» y el botón deshabilitado.
  - Con solo parecidos, muestra «Se parece a:» y el botón «Crear igual», que crea sin volver a buscar.
  - Si un resultado llega sin `match`, cuenta como exact, que es la dirección conservadora.
- **`SimilarThirdParty.match`** en `types/third-party.ts`.

## 2. Tests

`tests/test_similar_por_contenido.py`, 29 tests (`nuevos_r2.log`: 29 passed, EXIT=0, sobre `reciclaje_test_coder_1`).

- **T1:** 19 casos de la función, cada uno en las dos direcciones.
- **T2–T11:** el endpoint. T5, T8, T9 y T11 llevan control positivo en el mismo escenario.
- **«Ana Paz» ⊂ «Ana Paz Lopez»** se agregó a T1 durante la construcción, con aviso previo a QA 1. El plan daba «Ana Maria» como frontera del umbral de palabras, pero «anamaria» tiene 8 letras y pasa también por el umbral de letras. Sin el caso nuevo, P9a no tumbaba nada (`prediccion_frontera.log`: 0 diferencias; `_r2`: 2).

## 3. Gates

| Gate | Resultado | Log |
|---|---|---|
| C2, paridad `name_match_kind` ↔ `c_final` | **IGUALES.** SAC: 383 terceros, 26 pares de cada lado. Costa: 484 terceros, 28 pares de cada lado (2 exact, 26 similar). 0 diferencias de par o de clase; frontera 13/13; control positivo con una variante de una dirección: 5 diferencias. Corrió sobre HEAD `99996cc`, sin cambios sin commit y con el sha de `name_match.py` | `c2_paridad.log` |
| Dirigidas | **190/190 passed, EXIT=0**, la predicción escrita antes. Set del grep `find_similar\|/similar\|SimilarThirdParty\|name_match`: `test_sac_reparto_por_compra.py`, `test_sac_recolector_alcance.py`, el archivo nuevo, más las 3 guardas | `dirigidas.log` |
| Plantado backend | **9/9 en la diagonal, todos exactos**, sin caídas de más ni de menos. Cada corrida recolectó 29 tests; el cierre del sha es igual a HEAD y `git status` queda limpio | `plantado_r1.log` |
| Plantado front (P7, P8) | **2/2 en la diagonal** | `plantado_front_r2.log` |
| e2e E1–E4 a 1440 y 390 | **7/7.** E2 crea UN tercero (lo cuenta la API antes y después) sin volver a llamar a `/similar`, y lo da de baja | `e2e_r2.log`, capturas en `capturas/` |
| Frontend | lint 37 (el techo), tsc y build: EXIT=0 | `lint.log`, `tsc.log`, `build.log` |
| Golden | no aplica, medido | `golden_no_aplica.log` |
| Parity | no aplica: cero migraciones | — |

**O3 (predicción del plan):** `test_t11` de #122 (`:703`, compara la lista exacta de nombres), su t12 y la fila `/similar` de Ingrid quedaron verdes sin cambios. Antes de correrlas lo calculé con la función: ningún fixture gana un parecido.

## 4. Dos corridas que no cuentan (se conservan)

- **`t1_sin_variable_INVALIDA_colision.log`.** Lancé un pytest sin `TEST_DATABASE_URL`, así que corrió contra la base compartida `reciclaje_test` y chocó con la suite del checkpoint del Coordinador. Le avisé en el acto, y él paró y relanzó la suya. Desde entonces, todo pytest mío escribe la base en la primera línea de su log.
- **Instrumento, no producto:**
  - `e2e_r1_INSTRUMENTO_creado_no_dado_de_baja.log`: el tercero creado en E2@1440 seguía activo a 390, y ahí el diálogo bloqueó con un exact, que es lo correcto. Ahora se da de baja enseguida.
  - `plantado_front_r1_INSTRUMENTO_esbuild_quita_comentario.log`: el chequeo de «Vite sirve el plantado» buscaba un comentario, y esbuild los quita. P7 había caído igual, exactamente lo predicho. Ahora se verifica que el código original ya no se sirva.

## 5. Correcciones a las predicciones del plan

Están en `matriz-plantado-similar-por-contenido.md` (commiteada antes de plantar). El plan no se reescribió:

- P9a se corrige con «Ana Paz».
- P5 no tumba T2, porque la regla B también marca ese par. Solo cae `T1[A: sufijo S.A.S]`.
- P5b (sin el camino C) es una fila nueva.

## 6. Lo que queda

- Nit de QA 1, no bloquea: mientras «Crear igual» crea, el botón dice «Buscando...». Ya pasaba al crear sin parecidos.
- El fixture «Recuperadora Zelmira Quintero E2E» queda en la BD dev propia (`reciclaje_coder_1`) para la próxima corrida del e2e.
