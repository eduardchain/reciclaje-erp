# Matriz de plantado: guarda del conftest por worktree

Plan: `plan-guarda-conftest-worktree.md` v1.1 (c380616). Código: `c84515c`. Se commitea ANTES de plantar y no se reescribe.

## Cómo se planta

- Un defecto por corrida, sobre el árbol de `c84515c`. El respaldo es por RUTA y el cierre se verifica por sha256 contra HEAD, con `git status` limpio.
- `PYTHONDONTWRITEBYTECODE=1` y se borran los `__pycache__` del archivo plantado antes de cada corrida: dos defectos del mismo tamaño en el mismo segundo medirían el `.pyc` anterior.
- Cada corrida: `pytest tests/test_conftest_guarda_worktree.py` con `TEST_DATABASE_URL=…/reciclaje_test_coder_1` en el mismo comando. La primera línea del log lleva la base y el `git rev-parse --short HEAD`.
- La corrida tiene que RECOLECTAR los 16 tests. Si un defecto rompe un import, la fila no cuenta.
- cwd de pytest: `~/Projects/reciclaje-erp-wt/coder-1/backend`, o sea dentro del worktree «coder-1». P3 depende de eso.

En las corridas, el conftest real que carga pytest tiene la variable, así que ningún defecto cambia la base contra la que corre la propia suite.

## Los 16 tests

T1, T2, T3, T4, T5, T6, T7, T8, T9, T10×6 (parametrizado: 3 URLs × principal/worktree) y T10c (`test_t10_control_una_base_de_sesion_pasa`).

## Matriz

| P | Defecto plantado (exacto) | Cae (predicción exacta) | No cae |
|---|---|---|---|
| P1 | `_test_db_url.py`: `if worktree:` → `if False:` | T1, T5, T6, T8, T9 | T2, T3, T4, T7, T10×6, T10c |
| P2 | `_test_db_url.py`: `if worktree:` → `if True:` | T2, T7, T8, T9 | T1, T3, T4, T5, T6, T10×6, T10c |
| P3 | `_test_db_url.py`: `_checkout(Path(anchor).resolve())` → `_checkout(Path.cwd())` | T1, T2, T5, T6, T7, T8, T9 | T3, T4, T10×6, T10c |
| P4 | `_test_db_url.py`: en `_checkout`, `git.is_file()` ↔ `git.is_dir()` | T1, T2, T5, T6, T8, T9 | T3, T4, T7, T10×6, T10c |
| P5 | `_test_db_url.py`: `environ.get("TEST_DATABASE_URL") or ""` → `environ.get("TEST_DATABASE_URL")` y `if not url:` → `if url is None:` | T5 | los otros 15 |
| P6 | `conftest.py`: la llamada → `os.environ.get("TEST_DATABASE_URL") or "postgresql://admin:test_password@localhost:5433/reciclaje_test"` | T8 | los otros 15 |
| P7 | `schema_parity_check.py`: la llamada → el `os.environ.get(...) or "…/reciclaje_test"` de sus l.62-65 de 161b204 | T9 | los otros 15 |
| P8 | `_test_db_url.py`: se borra el bloque `if u.port != 5433 … raise RuntimeError(...)` | T10×6 | T1–T9, T10c |

## Por qué cada predicción

- **T8 y T9 ejecutan la función REAL** a través del conftest y del parity copiados. Por eso caen con todo defecto que cambie la decisión en un worktree o en la principal sin variable: P1, P2, P3 y P4.
  - El plan daba P1 → «T1, T5, T6» y P2 → «T2, T7». Esas predicciones se quedaban cortas: no contaban a T8 y T9. Esta matriz las corrige; el plan no se reescribe.
- **P1:** ningún worktree aborta.
  - Caen T1, T5 y T6.
  - T8: el worktree termina sin error.
  - T9: el worktree llega a conectar, con OperationalError y sin RuntimeError.
- **P2:** la principal y la carpeta sin `.git` también abortan.
  - Caen T2 y T7. En T7, `root` es None, así que revienta con AttributeError: cae igual, por otra excepción.
  - También caen los controles de T8 y T9 (la principal aborta).
- **P3:** la cwd de pytest está dentro de «coder-1», así que todo árbol falso parece ese worktree.
  - T1 cae porque el mensaje dice «coder-1» y no «coder-9».
  - T5 cae porque `match="coder-9"` falla.
  - T6 cae porque busca «reciclaje_test_qa_2».
  - T2 y T7 caen porque abortan.
  - Los subprocess de T8 y T9 corren con cwd en `tmp_path/cwd`, sin `.git`: el worktree no aborta, así que caen por su caso worktree.
  - Con la variable presente nadie mira la cwd, así que T3, T4 y T10 pasan.
- **P4:** el worktree se toma por principal, y al revés.
  - T1, T5, T6, T8 y T9 caen por el worktree que no aborta.
  - T2 cae porque la principal aborta.
  - T7 no tiene `.git`, así que no cae.
- **P5:** `make_url("")` lanza `ArgumentError`, no `RuntimeError`, así que solo cae T5. T8 y T9 no ponen la variable (la quitan del entorno), así que no pasan por el vacío.
- **P6 y P7:** cada uno lo ve solo el test que ejecuta ese archivo real.
- **P8:** caen las 6 URLs prohibidas, y el control T10c sigue pasando.

## Dirección peligrosa

Un test que debía caer y no cayó. Una caída de más se explica en el informe, y la matriz no se cambia.
