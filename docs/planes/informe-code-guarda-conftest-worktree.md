# Informe: guarda del conftest por worktree

- Plan: `plan-guarda-conftest-worktree.md` v1.1 (c380616), con GO de QA 1 y la autorización de Daniel vía el Coordinador.
- Nivel: lógica.
- Rama `coder-1/plan-guarda-conftest` sobre develop `161b204`. Código en `c84515c`; matriz en `98e2b5f`, commiteada antes de plantar.
- Cero `app/`, cero migraciones, cero frontend.
- Evidencia: `~/sac-evidencia/2026-11-20/coder-1-guarda-conftest/`.

## 1. Qué cambió

- **`backend/tests/_test_db_url.py` (nuevo).** `resolve_test_database_url(environ, anchor)` sube desde `anchor` hasta el primer `.git`:
  - Si `.git` es un ARCHIVO, es un worktree, y la variable `TEST_DATABASE_URL` es obligatoria. Sin ella, o vacía, lanza `RuntimeError` con el nombre del worktree y la línea para exportar `reciclaje_test_<nombre con _>`.
  - Si `.git` es un directorio (la principal), o si no hay `.git` en ningún padre, usa la variable si está y si no, `reciclaje_test`, como hoy.
  - Después aplica la guarda de siempre (`reciclaje_test*` en localhost:5433), que se movió aquí con el mismo texto; antes estaba duplicada.
- **`backend/tests/conftest.py`.** Las l.54-61 pasan a una llamada: `resolve_test_database_url(os.environ, Path(__file__))`.
- **`backend/scripts/schema_parity_check.py`.** Las l.62-65 y la guarda duplicada de `main()` pasan a la misma llamada, a nivel de módulo, antes de cualquier conexión.
  - Las guardas de la URL de dev (5433 y producción) siguen igual.
  - **Cambio de código de salida (nit de QA 1, aceptado):** una URL de test rechazada ya no sale con `ABORTA … exit 2`, sino con `RuntimeError`, exit 1.

## 2. Tests

`tests/test_conftest_guarda_worktree.py`, 16 tests (`nuevos_r1.log`: 16 passed, EXIT=0, sobre `reciclaje_test_coder_1`).

- **T1–T7: la regla**, sobre árboles falsos en `tmp_path`. El `.git` es un archivo o un directorio, según el caso.
- **T8: el conftest REAL.**
  - Se copia a los dos árboles falsos y se ejecuta con `runpy` en un subprocess, sin la variable.
  - El subprocess corre con `PYTHONPATH` al backend real, cwd neutral y `PGHOSTADDR=0.0.0.1 PGCONNECT_TIMEOUT=1` en los dos casos.
  - Resultado: el worktree lanza `RuntimeError` que nombra a `coder-9`, y la principal termina sin error.
- **T9: el parity REAL**, en las mismas condiciones que T8.
  - El worktree aborta antes de crear un engine: no imprime «Test (create_all):» y no hay OperationalError.
  - El control es la principal: llega a conectar y cae con OperationalError hacia 0.0.0.1. Eso prueba que no abortó y que nada salió hacia 5433.
- **T10: la guarda movida.** 3 URLs prohibidas × principal/worktree. El control (T10c) es una base de sesión, que pasa.

## 3. Gates

| Gate | Resultado | Log |
|---|---|---|
| ruff (los 4 archivos) | limpio | `ruff.log` |
| e2e `--collect-only` desde mi worktree | sin la variable, **EXIT=4** y el mensaje nombra «coder-1» y `reciclaje_test_coder_1`; con la variable, **EXIT=0** y 16 collected | `e2e_collect.log` |
| Plantado P1–P8 | **8/8 en la diagonal, exactos.** Ninguna caída de más ni de menos. Cada corrida recolectó los 16. El cierre por sha256 da HEAD en los 3 archivos plantados y `git status` queda limpio | `plantado_r1.log`, `plantar.py` |
| Dirigidas | **76/76 passed, EXIT=0**, con la predicción (76) escrita antes. El set es el archivo nuevo, `test_org_context_dependency.py` (el conftest sigue cargando para otro archivo) y las 3 guardas. Primera línea del log: base + HEAD `98e2b5f` | `dirigidas.log` |
| Parity real desde mi worktree, con la variable | **DIFF CERO** fuera del baseline: 68 tablas, 306 índices, 375 constraints | `parity.log` |
| Golden | no aplica: cero `app/` y cero migraciones | — |

**Predicciones del plan corregidas en la matriz.** El plan no se reescribió.
- El plan daba P1 → T1, T5, T6 y P2 → T2, T7. Se quedaba corto: T8 y T9 ejecutan la función real, así que caen también con esos dos defectos. La matriz lo escribió antes de plantar, y cayeron exactamente así.
- P3, que el plan dejaba para la matriz, salió exacto: T1, T2, T5, T6, T7, T8 y T9.

## 4. Condiciones y avisos

- **Condición del merge (O1 del plan, en pie):** antes de integrar, `suite.sh` del checkpoint exporta `TEST_DATABASE_URL=…/reciclaje_test` de forma explícita. Desde el worktree `checkpoint`, la sugerencia del mensaje sería `reciclaje_test_checkpoint`, que no existe; por eso el script la exporta en vez de depender del default.
- **O4 de QA 1, para el Coordinador (lo avisa QA):** el Protocolo §1 y `README_TESTS.md` dicen «sin la variable, la de siempre», y eso deja de ser cierto en un worktree.
- **Riesgo residual declarado (§5 del plan):** la guarda exige NOMBRAR una base, no que sea la propia.
