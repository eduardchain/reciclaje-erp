# Informe de código — Llaves estables para los advisory locks de numeración

**Plan:** `plan-advisory-locks-estables.md` v1.2 (QA GO condicionado → condiciones F1–F5 aplicadas) · **Fecha:** 2026-09-09 · **Tipo:** fix compartido (3 orgs cliente), no SAC · **Migraciones:** 1 (`d1e2f3a4b5c6`, índice único de doble partida con gate de datos)

## 1. Qué cambió

**Helper nuevo** `app/utils/advisory_locks.py` — el único lugar donde se deriva la llave, se toma el lock y se lee el `MAX`:
- `SEQUENCES`: nombre de secuencia → (tabla, columna, columna de partición). Nueve contadores. Nombre desconocido → `ValueError` (fail-closed).
- `sequence_lock_key(org, seq, partition)`: `crc32(f"{org}:{seq}[:{partition}]")` — determinista entre procesos; para salidas produce la misma cadena de #105.
- `lock_sequence(...)`: toma `pg_advisory_xact_lock` y **exige el orden canónico** (`RANK`: documentos 10–13 → purchase 20 → sale 21 → movement 30 → adjustment 40 → transformation 41). Primera adquisición con rango menor al máximo retenido → `LockOrderError`; re-adquirir nunca levanta. El registro vive en `Session.info` y muere con la transacción raíz (`after_transaction_end`), verificado también con `close()` sobre transacción abierta.
- `lock_sequences(db, org, *seqs)`: declaración anticipada — ordena por rango y adquiere.
- `next_number(db, org, seq, partition)`: lock + `COALESCE(MAX(col),0)+1` — **el único generador del sistema**.

**Servicios** (11 sitios → envoltorios de una línea sobre `next_number`): `purchase._generate_purchase_number`, `sale._generate_sale_number` (sale también pierde el `print("🔢 …")`), `double_entry._generate_double_entry_number` (**y borra** sus copias de `_generate_purchase_number`/`_generate_sale_number`; `create` llama `next_number(..., "purchase_number"|"sale_number")`), `money_movement._generate_movement_number`, `inventory_adjustment._generate_adjustment_number`, `material_transformation._generate_transformation_number`, `transfer._generate_transfer_number`, `inbound_order._generate_order_number`, `willard_delivery._lock_key`/`_next_number` (delegan; `import zlib` fuera).

**Declaración anticipada (D4)** en los cuatro flujos que numeran más de un contador en una transacción:

| Flujo | Secuencias retenidas al entrar | Por qué (orden que tenía) | Duración típica |
|---|---|---|---|
| `inbound_order.liquidate` | purchase, movement, adjustment | purchase → movement (pago, si lo hay) → adjustment → movement (accrual): sin pago inmediato el primer movement venía DESPUÉS del ajuste | una liquidación de Entrada: N compras + ajustes + accrual, décimas de segundo a ~2 s con muchas líneas |
| `transfer.receive` | movement, adjustment | adjustment (merma) → movement (par de maquila), por línea | una recepción: milisegundos a ~1 s |
| `transfer.resolve` | movement, adjustment | adjustment (merma/excedente) → movement (par de la línea liberada) — **no estaba en la v1.1 del plan**; lo desmintió leer `_emit_line_effects` | ídem |
| `willard_delivery.liquidate` | sale, movement, adjustment | venta: sale → movement; abono: adjustment (descarga D12) → movement (factura, par). Sin defecto plantado propio (O1 de QA): sin la declaración, `test_par_emite_en_abono_material` (#100) caería por `LockOrderError` — adjustment 40 → movement 30 es el mismo mecanismo probado en P8/P10 | una liquidación de salida: ~1 s |

Consecuencia visible: mientras una Entrada de SAC liquida, un movimiento de tesorería de la MISMA org espera esa transacción (antes no esperaba a nadie). Solo SAC tiene esos flujos; en las 3 orgs cliente nada cambia salvo que compras, ventas y cruces ahora sí se serializan entre sí y entre workers.

**Modelo + migración**: `DoubleEntry.__table_args__` gana `UniqueConstraint(organization_id, double_entry_number)` (`uq_double_entries_org_number`); migración `d1e2f3a4b5c6` con gate de datos.

**Tests**: `tests/test_advisory_locks.py` (8) + `TestLocksDeNumeracionEnElCruce` (2, en `test_api_double_entries.py`) + `TestOrdenDeLocksEnLaEntrada` (1, en `test_sac_entrada_sin_proveedor.py`) = **11 nuevos**. Sin frontend.

## 2. Verificación de la migración en dev (5434), con artefacto

`locks_migracion_dev.log` (scratchpad): (1) estado inicial `b8c9d0e1f2a4`, constraint ausente; (2) se plantó un duplicado en la org demo Pacífico (DP #2 → #1); (3) `alembic upgrade head` **se detuvo** con `GATE: 1 numero(s) … org=934acd81… numero=1 x2`, `alembic current` siguió en `b8c9d0e1f2a4` y el constraint siguió ausente — **la BD quedó como estaba**; (4) restaurado el número, `upgrade head` → `cero duplicados … creando uq_double_entries_org_number`, `current = d1e2f3a4b5c6 (head)`, `pg_constraint` muestra `UNIQUE (organization_id, double_entry_number)`, DP2 de vuelta en #2.

## 3. Gates (artefactos en el scratchpad de la sesión)

| Gate | Artefacto | Resultado |
|---|---|---|
| Tests nuevos (11) | `locks_nuevos.log`, `locks_t10.log` | 10 passed + T10 corregido (mi aserción decía `decrease` y un sobrante es `increase`, #93 D6) → 1 passed |
| Corrida dirigida (locks + SAC + cruces + compras + ventas, 497 tests) | `locks_targeted.log` | **497 passed** en 15:54, EXIT=0 — ningún flujo levantó `LockOrderError` |
| Suite completa a archivo | `locks_full.log` + `locks_full_start.txt` | **1760 passed** en 1:00:18 (1749 + 11), `EXIT=0` como última línea; chequeo fuerte de mtime contra el arranque (17:00:41) sobre `app/`, `tests/`, `alembic/`, `scripts/` y `frontend/src/`: **0 archivos** |
| Parity (modelos vs 5434 migrada) | `locks_parity.log` | **DIFF CERO fuera del baseline** — 65 tablas, 290 índices, 344 constraints (uno y uno más que la corrida de #105: el UNIQUE nuevo y su índice), EXIT=0 |
| C2 de QA (T9 fija la premisa del listener: `flush()` = subtransacción, NO limpia el registro) | `locks_c2.log` (archivo completo, 8 passed, EXIT=0) + `locks_c2_plantado.log` (listener sin la condición `parent is None` → T9 **cae**, EXIT=1; helper restaurado por `cmp`) | ediciones post-GO declaradas: `tests/test_advisory_locks.py` (T9) y el docstring de `lock_sequences` (O2); ruff limpio, `import app.main` OK |
| ruff backend | consola | limpio tras cada edición |
| Golden aislado (HEAD `fb3d946` vs working tree, mismo backend :8001 y misma BD) | `golden_locks/before` (48 + manifest, tomado con 0 archivos de `app/` tocados), `golden_locks/after` (48 + manifest, sobre el árbol final), `golden_locks/diff.log` | **0 diffs reales, 0 claves aditivas** en 48 capturas ×3 orgs, EXIT=0 — y **repetido sobre el árbol reconstruido** (§5): `after2` + `diff2.log`, 48/48 byte-idéntico, EXIT=0; y `after` vs `after2` comparados directamente con `diff -rq`: **idénticos en las 48 capturas** (solo difiere `_manifest.json`) — la reconstrucción produce las mismas respuestas que el archivo perdido |
| eslint / tsc / build | — | no aplica: sin cambios en `frontend/` |

## 4. Defectos plantados (grilla §5 del plan)

Artefactos: `plantado_locks_resumen.txt` (corrida 2 completa + corrida 3 solo P2) y `plant_locks_P1..P10.log`; la corrida 1 quedó archivada como `*_corrida1_invalida*` (§5). Selección por defecto: los 11 tests nuevos + `test_receive_merma_within_tolerance_b1_guardian` (#84) + `test_unliquidate_full_roundtrip` (#93) + `test_llave_del_lock_es_estable` (#105) = 14 tests, ~25 s por defecto. **Los 10 defectos tumban al menos un test y el árbol volvió byte a byte** (respaldo por ruta + `git status`/`diff --stat` contra HEAD = exactamente los 11 archivos del ciclo, ruff limpio).

| Defecto | Predicho (plan §5, v1.2 con GO de QA antes de plantar) | Cayeron | Veredicto |
|---|---|---|---|
| P1 `purchase.py` con `hash()`+`pg_advisory` propio | T3 (+T6 ≥) | T3, T6 | exacto |
| P2 `double_entry.create` con generador propio de compras (`MAX` + `lock_sequence("transfer_number")`) | T3, T4, T6 | T3 + `test_el_cruce_pide_las_tres_secuencias_en_orden` (el recorder ve `transfer_number` donde va `purchase_number`; **cayó en los dos plantados**, P2 y P6 — es el test que el plan etiquetaba T4/T5, ver errata §4 del plan) | **T6 NO cayó** — ver nota |
| P3 helper sin validar contra `SEQUENCES` | T2 | T2 | exacto |
| P4 helper deriva con `hash()` | T1, T8, T11 | T1, T8, T11 | exacto |
| P5 sin `UniqueConstraint` en el modelo | T7 | T7a (`test_constraint_en_el_esquema`) + T7b (`test_dos_cruces_con_el_mismo_numero_no_caben`) | exacto |
| P6 el cruce pide `purchase_number` para la venta | T5, T6 | `test_el_cruce_pide_las_tres_secuencias_en_orden` (la lista ordenada trae `purchase_number` donde va `sale_number`) | **T6 NO cayó** — ver nota |
| P7 `money_movement` pide `adjustment_number` | T6 (≥) | T6 + traslado con merma (`UniqueViolation uq_movement_number_per_org`: los dos MMs del par de maquila nacen con `MAX(adjustment)+1`, el mismo número) | ≥ (un test más que el predicho, por la razón correcta) |
| P8 sin declaración anticipada en `transfer` (receive+resolve) | traslado merma+maquila | ese test (`LockOrderError`) | exacto |
| P9 D4b no levanta | T9 | T9 | exacto |
| P10 sin declaración anticipada en `inbound.liquidate` | T10 (≥ roundtrip) | T10 + `test_unliquidate_full_roundtrip` (`LockOrderError`: pide movement 30 con adjustment 40 retenido) | exacto |

**Nota C3 — las etiquetas T4/T5 mentían.** El plan §4 definía T4/T5 como DOS tests de bloqueo (compra directa vs cruce; ídem ventas). En código quedaron OTROS dos: `test_dos_sesiones_esperan_el_mismo_lock` (evidencia positiva, una secuencia) y `test_el_cruce_pide_las_tres_secuencias_en_orden` (recorder). El recorder discrimina P2 y P6 con un solo test porque asserta la lista ORDENADA exacta de las tres secuencias que pide `create`: cualquier sustitución la rompe. La cobertura no se perdió — los plantados lo prueban —, las etiquetas sí; errata al pie de la lista del plan.

**Nota P2/P6 — la grilla sobre-predijo T6 dos veces.** T6 (`test_cada_generador_pide_su_secuencia`) ejercita los **envoltorios** `_generate_*`, y P2/P6 viven en `double_entry.create`, que no pasa por ningún envoltorio: T6 no puede verlos. Lo que sí los ve es el par del cruce (T4/T5), que cayó en los dos. No es un hueco de cobertura sino un error mío de **atribución** en la grilla — el mismo defecto de #101 ("un test cuyo nombre promete más cobertura de la que tiene"), esta vez en la columna predicha y no en el nombre. La grilla del plan queda como se escribió (compromiso previo) con una errata al pie que remite acá.

**Nota P2 — primera corrida contaminada.** El snippet plantado usaba `text(` y la reconstrucción del servicio (§5) había quitado ese import por quedar sin uso → los dos tests del cruce cayeron con **500 `NameError`**, que es instrumentación, no comportamiento. Corregido el snippet (importa `text` él mismo) y repetido **solo P2** (corrida 3, tras las 10): T3 + T4 caen por la razón correcta y T7b **pasa**, como debe.

## 5. Proceso

- La v1.0 del plan afirmaba "sin ciclos posibles de espera"; QA (F1) lo desmintió con dos flujos en orden cruzado, y al leer el código aparecieron dos más (la Entrada sin pago inmediato y el abono de salidas) y, ya en la v1.2, `transfer.resolve`. Cada uno lo habría atrapado D4b en la suite — que es exactamente por qué el orden se exige en vez de documentarse.
- Los 4 workers de producción pasaron de testimonio mío a **verificado por QA** (`systemctl cat`, solo lectura). La condición final de QA pidió que CLAUDE.md #106 y esta línea dijeran lo mismo: yo NO tenía artefacto propio de ese ssh (solo memoria), así que lo re-leí a archivo — `prod_unit_workers.txt` (2026-09-09 18:21:57, `override.conf` línea 24: `--workers 4`) — y la decisión cita ese archivo.
- 🔴 **El plantado destruyó un archivo del ciclo y su propia verificación lo dio por sano.** El script respaldaba los 7 archivos por `basename`, y dos se llaman `double_entry.py` (`services/` y `models/`): el segundo respaldo pisó al primero, y el `restore` tras P1 copió el MODELO sobre el SERVICIO. Consecuencia: P2 y P6 "no se pudieron plantar" (la línea a editar ya no existía), P3–P10 murieron al importar (`Table 'double_entry_lines' is already defined`, EXIT=4) y la verificación final dijo `== respaldo` para los 7 — **era cierto y no servía**: comparaba contra un respaldo que ya estaba mal. Misma familia que el golden `0 == 0` de #99: una guarda relativa se satisface con los dos lados igual de rotos. `services/double_entry.py` se **reconstruyó desde HEAD + las mismas 4 ediciones** (diff revisado hunk por hunk contra el brief), y se re-verificó con artefactos: `locks_reconstruido.log` (locks + todo `test_api_double_entries.py`) y un **segundo golden AFTER** (`golden_locks/after2`, `diff2.log`) sobre el árbol reconstruido. El script pasó a respaldar por ruta (`app_services_double_entry.py.orig`) y a cerrar con `git status`/`diff --stat` de `app/`, que es una verificación **absoluta** (contra HEAD), no relativa; el plantado se corrió de nuevo completo (§4).
- Cambios de la ronda de QA sobre el plan aplicados en código: F2 (evidencia positiva de bloqueo vía `pg_stat_activity`), F3 en su forma fuerte (un generador en el helper), T9 con `rollback` **y** `close`, y `lock_sequences` probado con la tupla desordenada.
