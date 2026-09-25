# Informe de código — SAC, correcciones del cierre con el cliente (16 y 18-sep) · #109

Plan: `docs/planes/plan-sac-correcciones-cierre-0918.md` v1.1 (QA GO). Matriz defecto × test commiteada en `5d4a24d`, ANTES de plantar.

## 1. Qué se construyó

| Pieza | Qué cambia | Fuente (cliente) |
|---|---|---|
| D1 | El abono a baterías reparte a planta 566 por kg, fijo, con tarifa propia `abono_planta_bateria_por_kg`. Mapa tipo → tarifa, fail-closed. Aviso en la respuesta si falta la tarifa | Johana 16-sep, confirmado 18-sep |
| D2 | `abono_planta_por_kg` pasa de 1.500 a 1.248 (seeder) | 18-sep: 1.248 planta, 849 Circunvalar |
| D3 | Dos cantidades en el documento de crisol: kg físicos y kg de plomo. Retorno: crisol −20, horno +14, maquila sobre 14, deuda total −6 | 18-sep, pregunta 5 |
| D4 | El documento de crisol mueve inventario por una transformación enlazada: crudo → puro 1:1; puro → crudo con merma | 18-sep, preguntas 5 y 6 |
| D5 | Guard: transformación manual crudo ↔ puro bloqueada con flag SAC | consecuencia de D4 |
| D6 | `GET /willard-deliveries/summary`: totales por tipo de salida | 18-sep, pregunta 3 (opción b) |
| D7 | Tarifas de reparto visibles en Config → Tarifas | pregunta de Daniel del 18-sep |

## 2. Desviaciones del plan (declaradas)

1. **Baterías sin sede que factura no "hereda el no-emite": se detiene antes con 400.** El plan decía que `:486` ganaba el caso de batería. La cuenta `willard_baterias` es de la sede que factura, así que sin el setting la liquidación ya fallaba antes de llegar al reparto. El test quedó fijando ese 400 y que nada se escribe.
2. **El resumen por tipo compara por DÍA, no por instante.** Lo encontró T17 en su primera corrida: con `datetime`, "hasta hoy" era hoy 00:00 y dejaba afuera lo liquidado hoy. Parámetros a `date`, comparación con `func.date(liquidated_at)`.
3. **`formatWeightPrecise` (3 decimales) es nuevo en `utils/formatters.ts`.** No estaba en el plan; sin él la pantalla mostraba 23,33 donde se guardó 23,333. Función aditiva, nadie más la usa.
4. **El fixture `tarifas` deja `abono_planta_por_kg` en 1.500 a propósito.** T3 necesita dos valores distintos y 38 tests del archivo calculan sobre 1.500. El valor real (1.248) vive en el seeder.
5. **Seeder: `create_tariffs` comparaba contra la versión MÁS VIEJA, no la vigente** (ver §5).
6. **La nota fija que F4 exigía no llegó a la pantalla; se corrigió el 19-sep.** El plan (`:86`) pedía que la tarjeta del resumen dijera que la columna "Queda en Circunvalar" no incluye la maquila del traslado. La advertencia quedó en el docstring de `schemas/willard_delivery.py:179-182`, no en la pantalla; lo hallé yo el 19-sep releyendo la reunión contra lo construido, y QA lo confirmó después de haber dado un GO que no lo vio, como su C5. En la misma pasada salieron dos textos más, los tres sin efecto en el comportamiento: el párrafo del tab Crisol seguía diciendo "no mueven inventario ni deuda", cierto en #107 y falso desde #109 (C4), y cuatro comentarios del servicio y del fixture con cifras y estados superados de Q-27/Q-29 (C6), entre ellos una cita atribuida a Hugo (4-sep) que no tiene fuente en el repo y que pasó a paráfrasis marcada (fail-closed, lección #100). Evidencia: AST equivalente sin docstrings en los 2 `.py`; en el manifiesto normalizado del dist difieren exactamente `CrucibleChargesSection-HASH.js` y `WillardDeliveriesPage-HASH.js`, con el mismo conjunto de 172 nombres lógicos e `index-HASH.js` idéntico; lint 37, build y 113 dirigidos en verde.

## 3. Tests

Tests nuevos y re-semantizados, todos en la matriz de `5d4a24d`:

| Archivo | Antes | Ahora | Qué se sumó |
|---|---|---|---|
| `tests/test_crucible_charges.py` | 10 | 27 | T6 a T16, T18, T19, y R3, R4 re-semantizados. Fixtures: el dross lleva fórmula 0,70, el crudo pide siempre un puro, stock de partida en los dos. **Ronda 2 (§10): T20, guard de mundo Willard, y T21, el guard de dueño con dos documentos; estos dos NO están en la matriz de `5d4a24d`, sus predicciones quedaron escritas en `r2_plantado.log` antes de plantar** |
| `tests/test_willard_deliveries.py` | 80 | 86 | T1 a T5, T17 (resumen y RBAC), R1 (partido en T5 más T1), R2, y el caso de batería sin sede que factura |
| `tests/test_advisory_locks.py` | 10 | 10 | `:328` pasa a declarar 3 secuencias y prueba el orden inverso con la transformación |

Primera corrida de `test_crucible_charges.py`: 25 verdes. Primera corrida de los tres archivos: 2 fallas, las dos informativas (desviaciones 1 y 2 de arriba). Ninguna se resolvió aflojando un test.

## 4. Defectos plantados — 17 de 17 en la diagonal

Script `plantar_109.py`: respaldo POR RUTA, restauración verificada por hash tras cada defecto, y cierre absoluto (`git diff HEAD` más `git status` del árbol entero, mismo hash al inicio y al final). Log: `corr_plantado.log`, `CIERRE_ABSOLUTO=OK`.

| P | Predicción (commiteada) | Cayó | Veredicto |
|---|---|---|---|
| P1 | ≥ T3, T1 | T1, T2, T3, T4, R2, T17 | diagonal, colaterales de más |
| P2 | T1 | T1, T2, T3, T4, T17 | diagonal. Los colaterales caen porque el fixture corre con el flag de maquila apagado: es la misma causa |
| P3 | T4 | T4 | exacto |
| P4 | T6 | T6, T18, R4 (los dos) | diagonal, colaterales de más |
| P5 | ≥ T7, R4 | T7, R4, T15 | diagonal. T15 afirma el monto además del orden de locks |
| P6 | T9 | T9 | exacto |
| P7 | ≥ T10 | T10 | exacto |
| P8 | T12 | T12, T19 | diagonal, un colateral |
| P9 | T13 | T13 | exacto (corrió también `test_api_material_transformations.py`: 52 verdes) |
| P10 | T16, el de sin flag | T16 sin flag | exacto |
| P11 | T17 | T17 | exacto |
| P12 | T8 | T8 | exacto |
| P13 | T6 | T6, T9, T18 | diagonal, colaterales de más |
| P14 | T18 | T18 | exacto |
| P15 | no tumba nada | nada (35 verdes, incluye `test_advisory_locks.py`) | predicción cumplida: la declaración de locks del retorno es defensiva |
| P15b | T15 | T15, R4, T7, anular documento | diagonal: `LockOrderError` en todo retorno con par |
| P16 | T19 | T19 | exacto |

Ninguna fila falló en la dirección cara (un test que debía caer y no cayó). P4, P8 y P13 tumbaron colaterales que la matriz no marcaba como "≥": para la próxima, los defectos que viven en la cantidad de plomo del retorno se escriben "≥", porque cuatro tests leen ese número.

## 5. Seeder

`abono_planta_por_kg` 1.500 → 1.248, `abono_planta_bateria_por_kg` 566 nueva, fórmula `drosses_to_lead` 0,70 en DROSS-CRI.

Dos defectos de `create_tariffs` que aparecieron al preguntarse si una tarifa cambiada desde la pantalla sobrevive a la provisión:

1. Leía el histórico, ordenado del más nuevo al más viejo, y el diccionario se quedaba con la última fila por código, o sea la versión más vieja. Con dos versiones de una tarifa re-versionaba en cada corrida. Ahora lee `/service-tariffs/current`.
2. Re-versionaba toda tarifa distinta del seed: la provisión revertía un cambio hecho desde la pantalla. Regla nueva: el seeder solo versiona si la tarifa no existe, si le falta `kg_per_unit`, o si la vigente es un valor que él mismo sembró antes (`TARIFF_SUPERSEDED`). Cualquier otro número se respeta, con aviso.

Las tres ramas corrieron contra dev: `corr_seeder_dev.log` (crea 566, reemplaza 1.500 por 1.248, segunda corrida sin cambios) y `corr_seeder_respeta.log` (un flete de 38 puesto por API se respeta; después se devolvió a 37).

## 6. Gates

| Gate | Resultado | Artefacto |
|---|---|---|
| Migración `f3a4b5c6d7e9` en dev con fila plantada | backfill 1 fila, NOT NULL, CHECK rechaza plomo mayor que físico, índice presente | `correcciones_migracion_dev.log` |
| Parity modelos contra migraciones | DIFF CERO, 65 tablas, 292 índices, 352 constraints | `corr_parity.log` |
| ruff (`app` y los 3 tests) | limpio | `corr_salidas_2.log` |
| tsc, eslint, build | 0, 37 (el techo), 0 | `corr_front_gates.log`, `corr_build.log` |
| Defectos plantados | 17 de 17, cierre absoluto OK | `corr_plantado.log` |
| Golden aislado, develop-HEAD `5d4a24d` contra árbol de trabajo, misma BD | 0 diffs en 48 capturas por 3 orgs, manifest en los dos lados. Los dos backends servían código distinto: la ruta nueva del resumen existe en uno y no en el otro | `corr_golden.log` |
| Suite completa, ronda 1 (la vigente es la de §10.6: 1817) | 1815 verdes, `EXIT=0` capturado dentro del bloque, 14:50:31 a 15:26:12 (35:36). mtime posterior al inicio: 0 archivos en `app`, `tests`, `alembic` y `scripts`; 1 en `frontend/src` (el selector del punto 4 de la sección 7, re-gateado) | `suite_109.log`, `corr_mtime.log` |
| Pantalla de Daniel | pendiente, condición de commit | |

Golden: verificado contra `CAPTURES` que ninguna ruta toca salidas, tarifas, crisol ni transformaciones. Se corrió igual porque `material_transformation` es un servicio compartido.

## 7. Puntos abiertos para QA y Daniel

1. **La merma del retorno de dross no aparece en el Estado de Resultados por sede.** `waste_loss` quedó a nivel de organización desde #84. El día que hay un retorno, Circunvalar más Juan Mina no suman el consolidado, por el valor de esa merma (14.500 en el escenario de la guía). Antes pasaba igual con la transformación manual; ahora lo causa un documento del flujo normal. El arreglo es el patrón D13 de #100 y toca `reports.py`, con golden. No se hizo en este ciclo.
2. ~~Los números del Estado de Resultados de la guía nueva están calculados a mano.~~ **Cerrado en la ronda 2 (§10.4):** verificados por endpoint sobre una copia de la BD de dev, al peso.
3. **Anular una transformación de crisol desde Inventario** muestra el 400 como aviso, pero el botón sigue visible. El response de transformaciones no dice si tiene dueño. Es un clic de costo; si molesta, se agrega el campo.

4. ~~El selector del retorno de dross filtra más que el servidor.~~ **Cerrado en la ronda 2 (§10.2):** el servidor aplica ahora el mismo predicado que la pantalla.

## 8. Archivos

Backend: `services/willard_delivery.py`, `services/crucible_charge.py`, `services/material_transformation.py`, `models/plant_process.py`, `schemas/crucible_charge.py`, `schemas/willard_delivery.py`, `schemas/service_tariff.py`, `endpoints/crucible_charges.py`, `endpoints/willard_deliveries.py`, migración `f3a4b5c6d7e9`, `scripts/seed_sac_org.py`.

Frontend: `types/crucible-charge.ts`, `types/sac-config.ts`, `types/willard-delivery.ts`, `services/crucibleCharges.ts`, `services/willardDeliveries.ts`, `hooks/useCrucibleCharges.ts`, `hooks/useWillardDeliveries.ts`, `utils/queryInvalidation.ts`, `utils/formatters.ts`, `pages/willard/CrucibleChargeCreatePage.tsx`, `CrucibleChargeDetailPage.tsx`, `CrucibleChargesSection.tsx`, `WillardDeliveriesPage.tsx`, `WillardDeliverySummaryCard.tsx` (nuevo).

## 9. Deploy (decisión de Daniel)

Una migración más al tren pendiente (#105 por dos, #106, #107, y esta). Después de `/deploy`, seeder en modo provisión contra producción: crea la tarifa 566, reemplaza 1.500 por 1.248 y crea la fórmula del dross. Con el arreglo de esta sesión, la provisión ya no revierte una tarifa cambiada desde la pantalla.

**Runbook de la provisión contra producción (C1 de QA):**

1. Se espera ver, en el paso `[12] Tarifas de servicio`, estas líneas de reemplazo si producción conserva lo sembrado el 1 de septiembre: `maquila_willard: 1500 -> 2097`, `flete_willard_planta_planta: 200 -> 37`, `abono_planta_por_kg: 600 -> 1248` (o `1500 -> 1248` si alguien ya corrió CC-009). Más la creación de `maquila_crisol` 300 y `abono_planta_bateria_por_kg` 566 si no existen.
2. **Si la corrida termina con el bloque `DECISION PENDIENTE`, el deploy se DETIENE.** Ese bloque lista tarifas cuya vigente no coincide con el seed y tampoco es un valor que el seeder haya sembrado. Decide Daniel, con Johana si hace falta. El operador del deploy no decide. **El remedio depende del motivo, y el bloque imprime el que corresponde** (O1 de QA):
   - `[AJENA]` — la versionó otro usuario. Si el seed es el correcto, se versiona desde Configuración, Tarifas. Agregar el valor a `TARIFF_SUPERSEDED` **no sirve**: la autoría la frena igual.
   - `[PROPIA]` — la versionó la misma cuenta del seeder con un valor fuera de la tabla. O es un cambio hecho desde la pantalla con esa cuenta (se deja), o es un valor viejo del seed que falta en `TARIFF_SUPERSEDED` (se agrega, derivado del historial de git, y se vuelve a correr).
   - `[SIN_IDENTIDAD]` — `/auth/me` no respondió y todo se trató como ajeno. Se vuelve a correr cuando responda; no se versiona nada a mano por ese aviso.
3. **Patrón específico: exit 3 con los tres valores viejos listados (`maquila_willard` 1500, `abono_planta_por_kg` 600, `flete_willard_planta_planta` 200) y el motivo "la versionó otro usuario".** Significa que el 1 de septiembre se provisionó con una cuenta distinta a la de hoy. Remedio: versionar 2097, 1248 y 37 desde Configuración, Tarifas, o volver a correr con la cuenta original. **Jamás aflojar el predicado de autoría ni volver a clasificar por valor "solo esta vez".**
4. La provisión se encadena con `&&`: el exit 3 detiene lo que venga después.
5. Nadie consulta la base de producción para anticipar el resultado: la evidencia de qué hay allá es el historial del seeder, y la corrida misma lo confirma.

## 10. Ronda 2 — condiciones de QA sobre el código (18-sep, tarde)

Veredicto de QA: GO condicionado a C1, C2 y C3 más la pantalla de Daniel. Aviso a QA enviado antes de editar. Todo lo de abajo tiene su archivo en el scratchpad de la sesión.

### 10.1 C1 — la tabla de valores sembrados estaba incompleta, y en producción eso invertía el resultado

La regla "el seeder nunca pisa un valor que no puso él" es correcta. Mi primera versión de `TARIFF_SUPERSEDED` traía una sola entrada, escrita de memoria. El historial del archivo dice otra cosa.

Comando (salida completa en `c1_historial_tarifas_seeder.log`):

```
git log -p --reverse --format='@@COMMIT %h %ad %s' --date=format:'%Y-%m-%d %H:%M' -- backend/scripts/seed_sac_org.py \
  | grep -E '^@@COMMIT|^[+-].*tariff_code'
```

| Código | Sembrado antes (commit, fecha) | Hoy | Entrada en la tabla |
|---|---|---|---|
| `maquila_willard` | 1500 (`32bf2d0`, 01-sep) | 2097 (`8e6a20b`, 08-sep) | 1500 |
| `abono_planta_por_kg` | 600 (`32bf2d0`), luego 1500 (`8e6a20b`) | 1248 (#109) | 600 y 1500 |
| `flete_willard_planta_planta` | 200 (`32bf2d0`, 01-sep) | 37 (`8e6a20b`) | 200 |
| `comision_green_loop` | 100 (`203718e`, 04-ago) | 100 | ninguna: nunca cambió |
| `maquila_intersede_cv_jm` | 1500 (`203718e`) | 1500 | ninguna |
| `maquila_crisol` | 300 (`cf003c7`, 14-sep) | 300 | ninguna |
| `abono_planta_bateria_por_kg` | — | 566 (#109) | ninguna: nace en este ciclo |

Por qué importa: W1 se deployó el 2 de septiembre con los valores del 1 de septiembre, y CC-009 nunca corrió contra producción. Con la tabla vieja, la provisión habría respetado los tres valores equivocados: a Willard se le facturarían 597 por kilo de menos. El comportamiento anterior, con su defecto, los habría corregido.

Regla que queda escrita en el archivo: un precio que sale de `TARIFFS` entra a `TARIFF_SUPERSEDED` en el mismo commit, y la tabla se deriva del historial, no de la memoria.

La rama corrió (`c1_provision_combinada.log`, un solo archivo):

1. Se versionaron por API 1500, 600 y 200 en los tres códigos, y 123 en la comisión, que es un valor que el seeder nunca puso. El log muestra las vigentes antes de provisionar.
2. La provisión versionó las tres (`1500 -> 2097`, `200 -> 37`, `600 -> 1248`) y respetó la comisión en 123.
3. La corrida cerró con el bloque `DECISION PENDIENTE` nombrando la comisión. Ese bloque es nuevo: el aviso de respeto antes se perdía en la mitad del log.
4. Se devolvió la comisión a 100 por API y una última provisión dio cero líneas de reemplazo o respeto.

Dev queda en 2097, 1248, 37, 566, 300, 1500 y comisión 100.

**Autoría, no solo valor (hallazgo de la revisión propia, §10.5).** La tabla completa abría el problema inverso: `ours` miraba solo el precio, así que una tarifa que el cliente repusiera desde la pantalla con un valor que el seeder sembró alguna vez se pisaba en silencio, con la etiqueta "valor sembrado antes". El caso concreto es el 1.500 de `abono_planta_por_kg`, que es literalmente la respuesta de Hugo del 4 de septiembre, y este mismo ciclo hizo ese código versionable desde Config, Tarifas. Ahora reemplazar exige las dos cosas: precio en la tabla **y** `created_by` igual al usuario con el que corre el seeder (leído una vez de `/auth/me`; identificadores normalizados; si `/auth/me` falla, todo se trata como ajeno).

Contraste a archivo (`c1_provision_autoria.log`): el mismo valor viejo con dos autores. El superusuario versiona maquila 1500 y flete 200: se reemplazan. Hugo versiona abono 1500: se respeta, el bloque final lo nombra con autor y fecha, y la corrida sale con **exit 3**. Después se devolvió a 1.248 y la provisión final dio cero líneas y exit 0.

El bloque `DECISION PENDIENTE` es ahora un gate y no un aviso: se imprime en `finally`, después del resumen, así que es lo último del log aunque una etapa posterior aborte; el exit 3 se decide en `main()`, en el camino normal, para no tapar el traceback de un fallo verdadero. Los mensajes muestran precio, unidad y `kg_per_unit`: antes una diferencia solo de `kg_per_unit` imprimía "vigente 100 / seed 100".

Dos residuos declarados, no arreglados: (a) "este usuario" es la cuenta superusuario, que puede ser la misma con la que Daniel entra a la pantalla; la autoría distingue a Hugo y Johana del seeder, no a Daniel por pantalla del seeder. (b) Nadie puede ver desde aquí quién creó las filas de producción.

### 10.2 C2 — el servidor aplica el mismo predicado que la pantalla

`_require_crucible_dross` en `services/crucible_charge.py`, llamado antes de `_dross_lead_kg`: si el material tiene perfil con mundo Willard distinto de `none`, responde 422 nombrando el material y explicando por qué. Sin fila de perfil es `none` y pasa, igual que en la pantalla.

Test `test_dross_return_rechaza_material_de_willard`, leído de la respuesta HTTP: los DOS mundos Willard (`drosses` y `postconsumo`; en SAC 2 de los 15 materiales con esa fórmula son postconsumo) dan 422 que nombra el material y el mundo, y no dejan nada escrito en cinco tablas (kg, inventario, documento, par, transformación); perfil con mundo `none` da 201; sin fila de perfil da 201.

Defectos plantados con la predicción escrita antes (`r2_plantado.log`, tres filas, 3 de 3 en la diagonal, 1 de 27 cada una): quitar la llamada al guard; un guard escrito solo para `drosses`, que deja pasar postconsumo; y revertir el `.first()` (§10.3). La primera corrida de una sola fila está en `c2_plantado.log`. La respuesta del caso plantado es el defecto que QA describió: GUARRU pasa, `lead_kg` 8,2, y salen 20 de puro y entran 8,2 de crudo. Respaldo por ruta, hash del árbol idéntico al inicio y al final.

### 10.3 C3

- `_guard_owned_by_crucible` usa `.scalars().first()` con orden por número de documento. `transformation_id` no es único. La revisión propia notó que ningún test lo sostenía: revertirlo dejaba todo verde. Test nuevo `test_guard_de_dueno_aguanta_dos_documentos_con_la_misma_transformacion`: clona por ORM un segundo documento confirmado con la misma transformación (copia todas las columnas, así pasa el CHECK de `lead_kg`; toma el número siguiente a mano, sin `next_number()`, que solo vive en `app/`) y exige 400 que nombra, no 500. Plantado: revertir a `scalar_one_or_none()` tumba exactamente ese test, con `MultipleResultsFound` en la traza.
- CLAUDE.md: los flujos con declaración anticipada de locks son 6, no 5. Verificado con `grep -rn "lock_sequences(" backend/app`: traslado por dos, Entrada, Salida, y los dos del crisol.
- CLAUDE.md #109 lleva el predicado real del guard, la tabla de C1 y la merma con su número.

### 10.4 El Estado de Resultados de la guía, por endpoint

QA pidió verificarlo antes de la pantalla. Para no tocar la base que Daniel usa para probar, se copió `reciclaje_db` a una base aparte dentro del mismo contenedor, se levantó un segundo backend en el puerto 8012 contra la copia, se recorrió la guía completa por API y se borró la copia. Archivo: `guia_pnl_copia.log`.

| Línea | Guía | Endpoint |
|---|---|---|
| Utilidad neta consolidada | 551.033 | 551.033 |
| Utilidad neta Circunvalar | 225.733 | 225.733 |
| Utilidad neta Juan Mina | 339.800 | 339.800 |
| Merma del retorno de dross | 14.500, solo consolidado | `waste_loss` 14.500 en consolidado; ausente en las dos sedes |
| Pares internos por lado | 1.939.800 | 1.939.800 |
| PLO-LIN y PLO-PUR al cierre | 914 y 1.080 | 914 y 1.080 (leído de la base y del endpoint de stock) |

La base de dev quedó idéntica: los conteos de once tablas y la versión de alembic antes y después están en el mismo archivo y el `diff` entre los dos bloques da vacío.

El recorrido reportó 14 diferencias y las 14 son del instrumento: el lector de stock del script pedía un campo que no existe (`current_stock`; el real es `current_stock_total`) y esperaba la cantidad del ajuste en positivo cuando se guarda con signo. El stock se verificó por dos vías aparte.

### 10.5 Revisión adversarial propia antes de la suite

Cuatro revisores de solo lectura sobre C1, C2, la familia de `scalar_one_or_none()` y el inventario de preguntas, y un refutador por hallazgo. Quince agentes; un hallazgo refutado, el resto se sostuvo.

| Hallazgo | Qué se hizo |
|---|---|
| El seeder clasifica por valor y no por autoría | Arreglado (§10.1) |
| El bloque final no es un gate: exit 0 y se pierde si algo aborta después | Arreglado: `finally` y exit 3 |
| Los mensajes solo muestran el precio | Arreglado |
| El test de C2 no cubre `postconsumo` | Arreglado, con su fila plantada |
| El `.first()` no lo sostiene ningún test | Arreglado, con su fila plantada |
| El selector ofrece materiales Willard mientras cargan los perfiles | Refutado: sin perfiles no hay destino y el botón Guardar queda deshabilitado |
| Inventario de preguntas: Q-40 y otras seis filas con texto anterior al 18-sep | Arreglado; Q-B y Q-41 pasan a "respondida, sin construir"; Q-42 nueva |

Deudas declaradas, fuera de C1 a C3:

1. **`create_materials` tiene para las fórmulas los dos defectos que #109 arregló en tarifas.** Lee el histórico y se queda con la versión más vieja, y versionaría todo lo que difiera. Hoy los dos defectos se cancelan: la más vieja es el valor sembrado, así que nunca ve diferencia. **Disparador exacto: revienta el día que el seed cambie un parámetro de una fórmula ya sembrada**, y entonces versionaría en cada corrida. No es de este ciclo: la fórmula 0,70 de DROSS-CRI es **nueva** (en `HEAD` el material tenía fórmula `None`, y en `main` el material no existe), no un cambio de parámetro.
2. `transfer._get_intersede_account` resuelve la cuenta intersede con un predicado distinto al de crisol y salidas. Es de #84 y está inerte con una sola cuenta.
3. Una retención que el cliente desactivó se vuelve a crear al provisionar. Decisión de producto.

### 10.6 Gates de la ronda 2

| Gate | Resultado | Archivo |
|---|---|---|
| Suite completa | **1817 passed**, `EXIT=0` dentro del bloque, 16:09:58 a 16:49:19 (39:16), desacoplada con `nohup` | `suite_109_r2.log` |
| Reconciliación | 1815 de la ronda 1 más 2 tests nuevos (T20 y T21) = 1817 | |
| Mtime fuerte | 0 archivos posteriores al inicio en `app/`, `tests/`, `alembic/`, `scripts/` y `frontend/src/` | `r2_mtime.log` |
| Dirigidos | 150 passed antes de la ampliación; 27 de 27 en el archivo del crisol después | `c2_tests_dirigidos.log`, `r2_crisol_file.log` |
| Plantados | 3 de 3 en la diagonal, hash del árbol idéntico al inicio y al final | `r2_plantado.log` |
| ruff | limpio en `app`, `tests` y `scripts` | `r2_ruff.log` |
| Seeder | historial, provisión combinada, contraste de autoría con exit 3, corrida final en cero | `c1_historial_tarifas_seeder.log`, `c1_provision_combinada.log`, `c1_provision_autoria.log` |
| Estado de Resultados de la guía | al peso, sobre una copia; dev intacto | `guia_pnl_copia.log` |
| Golden | no se repite: el delta de la ronda 2 sobre código compartido es una consulta dentro de `annul`, y las 14 rutas capturadas son lecturas | `r2_golden_aplica.log` |
| Parity | no se repite: la ronda 2 no toca esquema | |
| Frontend | sin cambios en la ronda 2; valen tsc, eslint y build de la ronda 1 | |

Nota sobre el primer archivo de tests dirigidos: pasé pytest por `tail`, así que su exit no quedó capturado; vale el "150 passed" de la última línea, y la suite completa lleva el exit propio.

El backend de dev en el puerto 8001 se reinició con el código final. Comprobado contra un material real de SAC: un retorno de dross con MR01 GUARRU HUMEDO responde 422 nombrándolo y no deja nada escrito. La organización SAC de dev sigue en el punto de partida de la guía.

### 10.7 R1 y O1 del re-veredicto (17:00)

QA dio GO para commit condicionado a una corrida más: la última edición del seeder (16:05:22) era posterior a la última provisión (16:04:50). Esa edición **era lógica y no texto**: el `try/except` alrededor de `/auth/me`, la normalización del UUID en los dos lados y `mine = bool(my_id) and …`. Tenía razón: la versión final no había corrido.

**O1, hecho antes de R1 para que la corrida lo cubra.** El bloque final decía "versionarla desde Config → Tarifas, o agregar el valor viejo a TARIFF_SUPERSEDED". Para una tarifa ajena el segundo consejo no hace nada, y empuja al operador hacia aflojar el predicado de autoría. Ahora cada tarifa respetada lleva su motivo (`AJENA`, `PROPIA`, `SIN_IDENTIDAD`) y el bloque imprime un remedio por motivo presente. El tercer motivo no estaba en el pedido de QA: salió al escribir los otros dos, porque con `/auth/me` caído el mensaje viejo decía "la versionó Administrador", que es cierto y engaña.

| Qué | Resultado | Artefacto |
|---|---|---|
| Motivo `AJENA`: Hugo versiona la comisión en 123 | exit 3, remedio `AJENA` 1 vez, remedio `PROPIA` 0 | `r1_provision_final.log` paso A |
| Motivo `PROPIA`: el superusuario la versiona en 124 (fuera de tabla) | exit 3, remedio `PROPIA` 1 vez, remedio `AJENA` 0 | paso B |
| **R1: provisión final con el árbol actual** | **exit 0, 0 líneas de versión o respeto, 7 vigentes con autor** | paso R1 |
| Rama `except` de `/auth/me`, sobre una copia de la BD y con un wrapper que no toca el árbol | maquila 1500 del propio superusuario: respetada `[SIN_IDENTIDAD]`, exit 3, vigente sigue en 1500 | `r1_rama_except.log` paso 2 |
| Contraste: misma copia, mismo seeder, `/auth/me` vivo | 1500 → 2097 reemplazada, exit 0 | paso 3 |
| Dev antes y después de la copia | idéntico (conteos + versión de alembic) | cierre del mismo log |
| Diff del seeder desde las 16:05:22 | +53 −12, solo texto y clasificación de motivo | `r1_diff_seeder_O1.diff` |
| ruff | limpio, el archivo y todo el backend | `r1_ruff.log` |

Las tres versiones de prueba de la comisión mandaron precio, unidad `per_kg_material` y `kg_per_unit` 14, iguales al seed salvo el precio: sin eso la corrida final habría caído en la rama `missing_kg` y parecería un defecto del seeder siendo del instrumento (cuidado 1 de QA). Solo se tocó `comision_green_loop`, el único código que la guía de pruebas de Daniel no usa.

**Lo que Daniel va a ver:** el historial de `comision_green_loop` en dev tiene ahora versiones 123, 124 y 100 de hoy, además del 123 de la ronda anterior. Son de estas pruebas. La vigente es 100, igual que antes. Las tarifas son append-only, así que no se borran.

No hubo suite nueva: desde el arranque de la última (16:09:58) el único archivo de código con cambios es `scripts/seed_sac_org.py`, que ningún test importa.

### 10.8 El registro del 18-sep, verificado contra la transcripción real (19-sep)

**Qué pasó.** Todo lo del 18-sep se registró como "Johana, vía Daniel": Daniel me lo dictó por chat después de la reunión. El 19-sep por la mañana entregó la transcripción automática de esa reunión y pidió confirmarlo todo. La transcripción es local y está en `.gitignore`. Hugo no asistió el 18.

**Cómo se verificó.** Leí las 684 líneas. Como el registro lo había escrito yo, no me bastó mi lectura: dos lectores ciegos de la transcripción, un auditor de lo registrado, un revisor de impacto en código y un verificador adversarial de citas (`wf_0c3aafac-b19`). QA hizo además su propia lectura completa. Resultado: 17 puntos confirmados, 11 a corregir, 9 nuevos y cero citas inventadas. Los problemas eran de alcance, no de invención.

**Resultado para el código: nada de lo construido en #109 contradice a Johana.**

| Pieza construida | Qué dijo ella | Línea | Grado |
|---|---|---|---|
| Baterías: planta recibe 566 | "566" | L155 | a |
| Baterías: Circunvalar se queda 1.531 | "1531", corrigiendo el 1.561 de Daniel | L159 | a |
| 566 fijo por kilo | "Sí, fijo por kilo" | L183 | a |
| Materiales: 1.248 y 749 de 1.997 | "1248 y 749"; "1997" | L237, L249 | a |
| Flete entero en Circunvalar | "Si el flet es de circunval" | L399 | a |
| Crisol 1:1, sin porcentaje | "En el crisol no hay ninguna transformación"; "no hay porcentaje"; "salen 200 de crudo, ingresan 200 de puro" | L555, L559, L579 | a |
| Retorno de dross: crisol baja 20 | "etapa crisol baja 20. Esa sí está" (ella lee la hoja en voz alta y la confirma) | L433 | a |
| Retorno de dross: horno sube 14 | "no subiría 20, sino 14" | L451 | a |
| La deuda total baja 6 | "ya la deuda total cambiaría en 6 kilos" | L517 | a |
| Salen 20, entran 14 | "Correcto. Salen 20 del crisol, entran 14 al horno grande" | L649 | a |
| "Materiales Willard" es la opción B | "Es la B" | L385-389 | b |

Grados: (a) lo dijo con sus palabras; (b) Daniel lo leyó o afirmó y ella respondió "Correcto" o "Así es"; (c) inferencia o redacción nuestra. Entre comillas solo va lo textual; las palabras dañadas por el transcriptor se dejan dañadas.

⚠️ **19-sep: la última fila volvió a 🟠 (Q-37).** El "Es la B" llegó después de que Daniel descartara la A en voz alta (L385), y el 16-sep (L577) Johana había dicho que lo facturado por materiales "no es un ingreso para circunval, sino una cuenta por pagar", lo contrario de como lo registra el sistema. Los números de #109 no cambian: es decisión de producto de Daniel.

**Lo que el registro decía de más o de menos, ya corregido.**

| Punto | Qué decía el registro | Qué dice la transcripción |
|---|---|---|
| Q-B y CC-014 | Valoración a precio de mercado para Willard e intersede | Solo la deuda con Willard (L599-605). La de planta con Circunvalar Daniel la saltó a propósito (L585-595). Nueva Q-44, no preguntada |
| Cargos por compra | "Solo Green Loop" | Existen, y "ellos lo pasan como gastos por aparte… gastos de nosotros de SA de circunval" (L621). El diseño no cambia |
| Q-41 y CC-013 | Retenciones "cualquiera" | La palabra no aparece. Firme solo IVA 19 % al facturar (L277, L279-281, L651-653). Johana ofreció una factura de ejemplo (L653-657): pedido nuevo |
| Q-34 | "Sin objeto" | La mitad del margen del plomo propio nunca se preguntó (L595) |
| Q-27 | "La del 4-sep queda sin efecto" | La frase la dijo solo Daniel (L375). Es conclusión nuestra. A Hugo nadie le ha dicho que su 1.500 y 597 quedó reemplazado |
| 849 de Circunvalar | "Ingreso de Circunvalar" | Aritmética nuestra. Ella separa 749 (16-sep L585-589) de 100 de utilidad dentro de la cuenta de materiales (L361) |
| Sin registrar | | Remanente de plomo de fin de mes del negocio de materiales (L335-339). Nueva Q-43, sin interpretar |
| Sin registrar | | Expectativa creada: Daniel dijo "lo que vamos a hacer entonces es una cuenta por pagar llamada materiales will" y ella dijo "Correcto" (L305-307). Lo construido es un resumen, sin cuenta |

**Documentos corregidos:** `inventario-preguntas-cliente.md` (nota de fuente, once filas, Q-43, Q-44 y el pedido de la factura), `preguntas-cierre-2026-09-17.md` (los siete bloques de respuesta), `control-cambios-requerimientos.md` (CC-013, CC-014 y la sección del 16-sep), una errata fechada arriba del plan sin reescribirlo, y la decisión #109 de `CLAUDE.md`.

**Camino (B): citas del cliente dentro del código.** Diez archivos llevaban citas en comentarios o docstrings. Se editaron solo ahí, con aviso previo a QA y copias por ruta de la versión que corrió la suite.

| Archivo | Qué se tocó |
|---|---|
| `backend/app/services/crucible_charge.py` | docstring del módulo |
| `backend/app/schemas/crucible_charge.py` | docstring del módulo |
| `backend/app/services/willard_delivery.py` | un comentario `#` |
| `backend/app/api/v1/endpoints/willard_deliveries.py` | docstring de `deliveries_summary` |
| `backend/scripts/seed_sac_org.py` | comentarios `#` en dos sitios |
| `backend/app/schemas/service_tariff.py` | un comentario `#` |
| `backend/tests/test_crucible_charges.py` | tres docstrings |
| `backend/tests/test_willard_deliveries.py` | un docstring |
| `frontend/src/pages/willard/WillardDeliverySummaryCard.tsx` | bloque `/** */` |
| `frontend/src/types/willard-delivery.ts` | un comentario `//` |

Declaración: el docstring de `deliveries_summary` es la descripción OpenAPI del endpoint. Cambia el texto que muestra `/docs`. No cambia el comportamiento.

**Equivalencia probada por artefacto, no por mtime.**

| Chequeo | Resultado | Artefacto |
|---|---|---|
| `ast.dump` completo en los 3 `.py` de solo comentario | idéntico, 0 tokens no-comentario distintos | `b_artefacto_python.log`, `n1_artefacto.log` |
| `ast.dump` sin docstrings en los otros 5 `.py` | idéntico; difieren 1, 1, 1, 3 y 1 tokens, todos STRING de docstring | mismos |
| ruff | limpio | mismos |
| tsc, eslint, build | exit 0; eslint 37, igual al techo | `b_artefacto_frontend.log`, `n1_artefacto.log` |
| `dist` de vite antes contra después | los 172 archivos con el mismo nombre y el mismo sha1 | `b_dist_antes.sha1`, `n1_dist_despues.sha1` |
| Tests dirigidos de salidas y crisol | 113 passed, `EXIT=0` dentro del bloque | `b_tests_dirigidos.log` |

Precisión: `386dfa2bde3b` es el sha1 del `ast.dump` del seeder, igual antes y después. No es el sha1 del archivo, que pasó de `1d6397001514` a `061a1f2dfbc8`. QA reprodujo la equivalencia con sus propias copias y su propio script.

**N1 de QA: la corrección metió una glosa nueva.** Al reescribir dos comentarios puse que "Materiales Willard" es "un nombre interno, no una cuenta". La opción B no dice eso, y Johana la llama cuenta cinco veces con sus palabras (L323, L335, L347, L361, L373). Es una cuenta interna con saldo en sus libros. Lo que la opción B descarta es un acreedor externo. Corregido en los dos comentarios, en Q-37, en la errata del plan y en `CLAUDE.md`, con la equivalencia vuelta a probar. Consecuencia de producto, fuera de este ciclo: el resumen por tipo no lleva saldo y puede quedarse corto frente a lo que ella espera ver (Q-37 y Q-43). Método: mi `grep` de la frase encontró un solo sitio porque en el otro la frase cruzaba un salto de línea.

**La suite completa no se volvió a correr.** El conteo sigue en 1817. Desde la suite se editaron diez archivos de los cinco directorios vigilados, así que el chequeo de mtime ya no da cero. Lo que sostiene el conteo es la equivalencia de arriba.
