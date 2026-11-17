# Informe de código — Columna Remisión en Entradas (SAC)

**Plan:** `docs/planes/plan-sac-entradas-columna-remision.md` v1.2 (commit 0a0fe2b, con la matriz antes de plantar) · **Base:** 0862891 · **Nivel:** lógica
**Fecha:** 2026-11-17 · **QA:** «QA Ecobalance» (sesión `d724e9a0…`)

Johana ya registra Entradas en producción y llena la remisión. Pidió, por Daniel, una columna «Remisión» en la tabla para filtrar, ordenar e identificar las entradas. Daniel decidió dos cosas con la ventanita:
- **alcance**: «Toda la lista (Recomendado)», o sea que el servidor ordena por Remisión sobre toda la lista y las demás columnas siguen ordenando la página;
- **construir**: «Sí, construir (Recomendado)», después del commit de planta.

## 1. Qué cambia

| Pieza | Archivo |
|---|---|
| `sort` acepta `remission_asc`/`remission_desc`; un valor desconocido da 422 | `app/api/v1/endpoints/inbound_orders.py` |
| `_remission_order`: cuatro llaves (vacía / valor numérico / texto `lower() COLLATE "C"` / `order_number DESC`) | `app/services/inbound_order.py` |
| Prop opcional `manualSorting` (por defecto, la expresión de antes) y meta `exportAsText` en el export | `components/shared/DataTable.tsx`, `types/tanstack-table.d.ts` |
| Columna «Remisión» después de Fecha, orden controlado, tarjeta móvil «Rem. X» y buscador | `pages/inbound/InboundOrdersPage.tsx` |
| El tipo `sort` se amplía | `services/inboundOrders.ts` |
| 8 tests (T1–T8) | `tests/test_sac_entradas_remision.py` (nuevo) |

Sin migración, sin permisos nuevos y sin escrituras: el ciclo solo cambia cómo se LEE el listado. Las Entradas que Johana ya registró no se tocan.

**El orden (D2).** Con `r = NULLIF(TRIM(remission_number), '')`:
1. las vacías van al final en los dos sentidos;
2. las remisiones solo de dígitos se ordenan por su valor: «0012» vale 12;
3. el texto se ordena por `lower(r) COLLATE "C"`, sin depender de la collation del servidor;
4. el desempate es `order_number DESC`, único por org, así que la paginación es estable.

**Desviación de D2, encontrada al construir.** El plan definía `r = TRIM(...)`. T3 cayó en la primera corrida: en `desc`, la llave de texto ponía el NULL de «sin remisión» antes que el '' de «  », porque PG ordena los NULL primero en descendente. Las dos vacías quedaban desempatadas antes de llegar a `order_number`. T2 pasaba por coincidencia, porque en `asc` ese orden coincidía con el de creación. Ahora hay **una sola definición de «vacía» para las cuatro llaves**. El código anterior al arreglo se plantó como P11.

## 2. QA pasada 1 y correcciones

Pasada 1: `pasada1_remision.patch`, sha256 `53335dc7…4846`. QA dio el GO de código **condicionado a C1**, con dos observaciones:

- **C1, la remisión se corrompía en el Excel.** `exportToExcel` convertía a `Number` todo string que pareciera número, para que los `Decimal` se puedan sumar. Una remisión es un identificador: «0012» salía 12 y una de más de 15–16 dígitos perdía precisión. Es justo el caso que el plan puso en T2, y con los datos de dev (16136, 14744…) «abrir el Excel» no lo detectaba. Arreglo: `meta.exportAsText` en `ColumnMeta`. El exportador salta la conversión en las columnas que lo declaran, Remisión lo declara y las demás páginas quedan igual.
- **N1:** `serverSortOf` había quedado debajo del JSDoc de `daysPending`; se movió arriba.
- **N2:** dos encabezados decían todavía `r = TRIM(...)`. Ahora dicen `NULLIF(TRIM(...), '')`, que es lo que hace el código.

Delta: `delta_c1n1n2.patch`, sha256 `d0f2cb41…be80`. Llevó aviso a QA ANTES de la edición. QA dio GO al delta y la Remisión quedó con GO de código.

## 3. Gates

Logs en `~/sac-evidencia/2026-11-17/remision/`.

- **Estáticos, después del delta:** tsc 0, eslint 37 (igual al techo), build 0, ruff limpio.
- **Dirigidas** (`dirigidos.log`): el test nuevo más `test_sac_ciclo_c.py`, `test_inbound_orders.py` y `test_sac_entrada_sin_proveedor.py`. Dieron **165 passed, EXIT=0**, igual que la predicción tomada de collect-only.
- **Plantado P1–P11** (`plantado_run.log`). Las predicciones se escribieron antes (`plantado_predicciones.md`). Hubo respaldo por ruta completa, un fragmento único por fila, .pyc borrado y cierre por sha256: los 7 archivos quedaron idénticos antes y después.
  - **11 de 12 filas en la diagonal.**
  - P8b (sin `COLLATE "C"`) y P9 (sin `NULLS` explícitos) no tumban nada, como se predijo. En esta máquina Alpine ya ordena por bytes, y los NULLS son el default de PG; las dos quedan medidas.
  - **P1 cayó de más**: T8 además de T2 y T3, en la dirección barata. La hipótesis se escribió ANTES de medirla, junto con la fila P1b. El plantado ponía la llave 2 en `r` crudo, que decide antes que `lower()`, así que también rompía las mayúsculas. **P1b** (`numerica = func.lower(r)`) dio exactamente T2 y T3, y la hipótesis quedó medida.
- **P12, Excel** (`p12_*.log/.xlsx`). Se midió por artefacto porque el frontend no tiene infraestructura de tests.
  - Exporté desde la pantalla de dev (`:8001` arrancado después del último cambio de `app/`, prueba de vida con `sort=remission_asc` = 200) y leí el archivo con openpyxl. Las dos mitades usan el mismo par de remisiones, «0012» y una de 20 dígitos.
  - Plantado: `'n'` 12 y `'n'` 12345678901234567000.
  - Restaurado: `'s'` '0012' y `'s'` con los 20 dígitos exactos.
- **Suite completa** (`suite_remision.log`, sha256 `cd05e319…6ea2`): **2148 passed, EXIT=0, capturado dentro del bloque**. Corrió de 13:25:50 a 14:40:36 (1:14:40).
  - La predicción, 2148, se escribió antes y sale de dos mediciones: `git diff --name-only 26283a2 -- backend/tests`, que da 0 archivos, más el archivo nuevo (8 tests, 0 parametrize); y `--collect-only`, que también da 2148.
  - No hay ningún FAILED, ERROR ni Traceback en todo el recorrido.
  - 5433 tenía 0 sesiones antes de arrancar.
  - `ARBOL_FIN == ARBOL_INICIO` (`4cb29969…f751`).
  - mtime posterior al inicio: 0 archivos en los cinco directorios, con control positivo de 671.
- **Golden: no aplica, medido.**
  - `grep -c inbound backend/scripts/golden_capture.py` = 0. El listado de Entradas no es una captura, y su router es exclusivo de SAC y está detrás del flag.
  - El golden no observa el frontend.
  - En `DataTable`, compartido con Costa y las demás orgs, la no-regresión es por construcción. El default de `manualSorting` es la expresión de antes, y `exportAsText` es opt-in: en las demás páginas `asText` es todo `false` y el export no cambia.
  - Una corrida daría «0 diffs y 0 aditivas», que no distingue nada (#110).
  - QA revisó la misma medición para todo el tren del deploy, `origin/main..HEAD` más la Remisión: cero migraciones. Lo compartido en `app/` es:
    1. el guard de `money_movement.annul` de #116, que el golden no ejerce;
    2. la clave nueva de settings, que tampoco se captura;
    3. helpers de SAC detrás del flag.

## 4. Observaciones

- **Las remisiones numéricas salen como TEXTO en el Excel de Entradas.** Es lo buscado para un identificador, pero Excel puede marcarlas con el triángulo de «número almacenado como texto».
- **Defecto PREEXISTENTE en código compartido, fuera de alcance y a decidir por Daniel.** El export genérico de `DataTable` sigue convirtiendo a `Number` otras columnas de identificadores: Identificación y Teléfono en Terceros, Número en Cuentas y Código en Materiales. Medido el 17-nov: 18 páginas con `<DataTable>`, 3 con `exportOverride` y 15 por el export genérico; `exportAsText` lo declara solo Remisión. El efecto es que una cuenta bancaria o una cédula con cero adelante, o con más de 15 dígitos, sale corrupta en el Excel, incluido el de Costa. El arreglo es declarar `meta: { exportAsText: true }` en esas columnas.
- **Dentro del texto, el orden NO es natural, y es comportamiento declarado.** El orden natural (por valor) aplica solo a remisiones de puros dígitos. Una alfanumérica se ordena carácter a carácter: en asc «r-12» va antes que «R-5», porque se compara el «1» contra el «5». Lo decidió el plan (D2) y T6 lo fija explícitamente (R-20 < R-30 < R-4). Si Willard o los proveedores usan remisiones alfanuméricas con un número de largo variable y Johana quiere verlas por número, eso es un ciclo aparte.
- **El orden de Remisión se pierde al volver del detalle**, igual que la búsqueda, los filtros y la página: hoy solo el tab vive en la URL (N3 del plan, fuera de alcance).
- **En producción la collation no se puede medir desde aquí.** El `COLLATE "C"` está para que no importe.
- **Pantalla de Daniel: «Todo bien» (17-nov, ventanita), sobre SAC dev con 22 entradas:**
  - el orden por Remisión sigue en la página 2, con las vacías al final en los dos sentidos;
  - ordenar Placa no vuelve a la página 1;
  - Shift+clic deja un solo orden;
  - la bandeja vuelve al orden FIFO;
  - el Excel saca «0012» como texto;
  - la tarjeta a 390 px dice «Rem. X».
  - En la misma ventanita quedó cerrada la pantalla de la Entrada #4 (orden alfabético, commit 0862891), que era condición de deploy de ese commit. El orden esperado, leído del servidor antes de la revisión, está en `pantalla_orden_esperado.log`.
