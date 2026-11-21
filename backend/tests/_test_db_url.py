"""Qué base de test usa una corrida (plan-guarda-conftest-worktree v1.1, D5).

UNA sola definición para los dos que recrean la base de test con DROP SCHEMA:
`tests/conftest.py` y `scripts/schema_parity_check.py`. Cada uno llama
`resolve_test_database_url(os.environ, Path(__file__))` con su propio archivo.

Regla (D2):
  - Carpeta principal (`.git` es un directorio), o sin `.git` en ningún padre:
    `TEST_DATABASE_URL` si está; si no, `reciclaje_test`, como siempre.
  - Worktree (`.git` es un ARCHIVO, `gitdir: …/worktrees/<nombre>`): la variable
    es OBLIGATORIA. Sin ella (o vacía), aborta. `reciclaje_test` es la base de la
    suite del checkpoint; el 20-nov un pytest de un worktree cayó ahí por olvido
    y le hizo DROP SCHEMA a la suite en curso.
  - Después, la guarda de siempre: solo `reciclaje_test*` en localhost:5433.

El checkpoint también corre desde un worktree y por eso exporta la suya,
explícita (D3): sin excepciones por nombre de carpeta. La regla exige NOMBRAR una
base, no que sea la propia (riesgo residual declarado en el plan, §5).

Módulo con guion bajo: `pytest.ini` recolecta `test_*.py`, así que esto no es un
test. No va en `app/`, que es lo que llega a producción.
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping, Optional, Tuple

import sqlalchemy

DEFAULT_TEST_DATABASE_URL = "postgresql://admin:test_password@localhost:5433/reciclaje_test"
_SESSION_URL = "postgresql://admin:test_password@localhost:5433/reciclaje_test_{rol}"


def _checkout(anchor: Path) -> Tuple[Optional[Path], bool]:
    """(raíz del checkout, es_worktree) subiendo desde `anchor` hasta el primer `.git`.
    Sin `.git` en ningún padre: (None, False)."""
    for d in [anchor, *anchor.parents]:
        git = d / ".git"
        if git.is_file():
            return d, True
        if git.is_dir():
            return d, False
    return None, False


def resolve_test_database_url(environ: Mapping[str, str], anchor: Path) -> str:
    """URL de la base de test para el checkout de `anchor`, o RuntimeError."""
    url = environ.get("TEST_DATABASE_URL") or ""
    if not url:
        root, worktree = _checkout(Path(anchor).resolve())
        if worktree:
            rol = root.name.replace("-", "_")
            raise RuntimeError(
                f"Este pytest corre desde el worktree «{root.name}» y no tiene TEST_DATABASE_URL: "
                "sin la variable caería en reciclaje_test, la base de la suite del checkpoint, "
                "y la recrearía con DROP SCHEMA.\n"
                "Exporta la de tu sesión en el mismo comando:\n"
                f"  TEST_DATABASE_URL={_SESSION_URL.format(rol=rol)}"
            )
        url = DEFAULT_TEST_DATABASE_URL
    # Guarda de siempre (antes duplicada en conftest y parity): la base se recrea
    # con DROP SCHEMA, así que solo reciclaje_test* en localhost:5433.
    u = sqlalchemy.engine.make_url(url)
    if u.port != 5433 or u.host not in ("localhost", "127.0.0.1") or not (u.database or "").startswith("reciclaje_test"):
        raise RuntimeError(
            "TEST_DATABASE_URL tiene que ser una base reciclaje_test* en localhost:5433 "
            f"(se recrea con DROP SCHEMA); llego host={u.host} port={u.port} db={u.database}"
        )
    return url
