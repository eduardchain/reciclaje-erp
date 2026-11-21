"""Guarda de la base de test por worktree (plan-guarda-conftest-worktree v1.1).

Un pytest lanzado desde un worktree sin TEST_DATABASE_URL caía en
`reciclaje_test`, la base de la suite del checkpoint, y le hacía DROP SCHEMA
(20-nov). La regla vive en `tests/_test_db_url.py` y la usan el conftest y
`scripts/schema_parity_check.py`.

Todos los árboles son FALSOS, dentro de `tmp_path`: un worktree se reconoce por
`.git` de ARCHIVO y la carpeta principal por `.git` de DIRECTORIO. Ningún test
de este archivo depende de dónde está el checkout que lo corre, y ninguno puede
tocar `reciclaje_test` (T8/T9: ver su docstring).
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests._test_db_url import DEFAULT_TEST_DATABASE_URL, resolve_test_database_url

BACKEND = Path(__file__).resolve().parents[1]
SESSION_URL = "postgresql://admin:test_password@localhost:5433/reciclaje_test_coder_9"


def _worktree(tmp_path: Path, name: str = "coder-9") -> Path:
    """<tmp>/wt/<name>/ con `.git` de ARCHIVO, como lo deja `git worktree add`.
    Devuelve el ancla (un archivo dentro de backend/tests/)."""
    root = tmp_path / "wt" / name
    (root / "backend" / "tests").mkdir(parents=True)
    (root / ".git").write_text(f"gitdir: {tmp_path}/main/.git/worktrees/{name}\n")
    return root / "backend" / "tests" / "conftest.py"


def _main(tmp_path: Path) -> Path:
    """<tmp>/main/ con `.git` de DIRECTORIO: la carpeta principal."""
    root = tmp_path / "main"
    (root / "backend" / "tests").mkdir(parents=True)
    (root / ".git").mkdir()
    return root / "backend" / "tests" / "conftest.py"


# ---------------------------------------------------------------- la regla (D2)

def test_t1_worktree_sin_variable_aborta_y_dice_que_exportar(tmp_path):
    with pytest.raises(RuntimeError) as e:
        resolve_test_database_url({}, _worktree(tmp_path))
    msg = str(e.value)
    assert "TEST_DATABASE_URL" in msg
    assert "coder-9" in msg
    assert "reciclaje_test_coder_9" in msg


def test_t2_principal_sin_variable_usa_la_de_siempre(tmp_path):
    """Control de T1: la carpeta principal no cambia de comportamiento."""
    assert resolve_test_database_url({}, _main(tmp_path)) == DEFAULT_TEST_DATABASE_URL


def test_t3_worktree_con_su_base_la_usa(tmp_path):
    assert resolve_test_database_url({"TEST_DATABASE_URL": SESSION_URL}, _worktree(tmp_path)) == SESSION_URL


def test_t4_worktree_que_nombra_reciclaje_test_explicita_pasa(tmp_path):
    """El checkpoint corre desde un worktree y exporta `reciclaje_test` a propósito (D3):
    la regla exige NOMBRAR una base, no que sea la propia (riesgo residual, §5)."""
    anchor = _worktree(tmp_path, "checkpoint")
    assert resolve_test_database_url({"TEST_DATABASE_URL": DEFAULT_TEST_DATABASE_URL}, anchor) == DEFAULT_TEST_DATABASE_URL


def test_t5_variable_vacia_cuenta_como_ausente(tmp_path):
    with pytest.raises(RuntimeError, match="coder-9"):
        resolve_test_database_url({"TEST_DATABASE_URL": ""}, _worktree(tmp_path))


def test_t6_el_guion_del_worktree_pasa_a_guion_bajo(tmp_path):
    with pytest.raises(RuntimeError) as e:
        resolve_test_database_url({}, _worktree(tmp_path, "qa-2"))
    assert "reciclaje_test_qa_2" in str(e.value)
    assert "«qa-2»" in str(e.value)


def test_t7_sin_git_en_ningun_padre_usa_la_de_siempre(tmp_path):
    anchor = tmp_path / "suelto" / "backend" / "tests" / "conftest.py"
    anchor.parent.mkdir(parents=True)
    assert not any((d / ".git").exists() for d in anchor.parents)
    assert resolve_test_database_url({}, anchor) == DEFAULT_TEST_DATABASE_URL


# ------------------------------------------------- el cableado real (T8 y T9)

def _env_sin_variable() -> dict:
    """Entorno del subprocess: SIN TEST_DATABASE_URL, con el backend real en el path,
    y con PGHOSTADDR no ruteable (D7). libpq respeta PGHOSTADDR aunque la URL diga
    localhost (medido: «No route to host» en 0,04 s), así que si el módulo llegara a
    conectar, falla hacia 0.0.0.1 y no toca `reciclaje_test`."""
    env = {k: v for k, v in os.environ.items() if k != "TEST_DATABASE_URL"}
    env.update(
        PYTHONPATH=str(BACKEND),
        PGHOSTADDR="0.0.0.1",
        PGCONNECT_TIMEOUT="1",
        PYTHONDONTWRITEBYTECODE="1",
    )
    return env


def _run(script: Path, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", f"import runpy; runpy.run_path({str(script)!r}, run_name='__main__')"],
        cwd=cwd, env=_env_sin_variable(), capture_output=True, text=True, timeout=120,
    )


def test_t8_el_conftest_real_aborta_en_worktree_y_no_en_principal(tmp_path):
    """Copia el conftest.py REAL a los dos árboles falsos y lo ejecuta sin la variable.

    El control (principal → termina sin error) depende de que el conftest no conecte a
    nivel de módulo: hoy solo hace `create_engine` (perezoso) y `sessionmaker`, y los DROP
    SCHEMA viven en fixtures. Si un día conecta, el control falla con OperationalError
    hacia 0.0.0.1 por PGHOSTADDR, en vez de tocar `reciclaje_test`."""
    real = BACKEND / "tests" / "conftest.py"
    wt = _worktree(tmp_path)
    main = _main(tmp_path)
    shutil.copy(real, wt)
    shutil.copy(real, main)
    neutral = tmp_path / "cwd"
    neutral.mkdir()

    r = _run(wt, neutral)
    assert r.returncode != 0, r.stdout + r.stderr
    assert "RuntimeError" in r.stderr and "coder-9" in r.stderr, r.stderr[-2000:]
    assert "reciclaje_test_coder_9" in r.stderr

    c = _run(main, neutral)
    assert c.returncode == 0, c.stdout + c.stderr[-2000:]


def test_t9_el_parity_real_aborta_antes_de_conectar_en_worktree(tmp_path):
    """Lo mismo con `scripts/schema_parity_check.py` REAL (C1 de QA).

    Worktree: sale con el mensaje de D2 ANTES de crear un engine — no imprime
    «Test (create_all):» ni hay OperationalError. Control, principal: pasa la resolución,
    llega a conectar y falla hacia 0.0.0.1 (PGHOSTADDR); eso prueba que la resolución no
    abortó y que nada salió hacia 5433."""
    real = BACKEND / "scripts" / "schema_parity_check.py"
    wt = _worktree(tmp_path).parents[1] / "scripts" / "schema_parity_check.py"
    main = _main(tmp_path).parents[1] / "scripts" / "schema_parity_check.py"
    for dst in (wt, main):
        dst.parent.mkdir(parents=True)
        shutil.copy(real, dst)
    neutral = tmp_path / "cwd"
    neutral.mkdir()

    r = _run(wt, neutral)
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    assert "RuntimeError" in r.stderr and "coder-9" in r.stderr, out[-2000:]
    assert "Test (create_all):" not in out
    assert "OperationalError" not in out

    c = _run(main, neutral)
    out = c.stdout + c.stderr
    assert c.returncode != 0, out
    assert "Test (create_all):" in c.stdout, out[-2000:]
    assert "reciclaje_test" in c.stdout
    assert "OperationalError" in c.stderr and "0.0.0.1" in c.stderr, out[-2000:]


# --------------------------------------------------- la guarda de siempre (T10)

@pytest.mark.parametrize("url", [
    "postgresql://admin:localdev123@localhost:5434/reciclaje_db",   # desarrollo
    "postgresql://admin:test_password@127.0.0.1:5433/otra",         # prefijo
    "postgresql://admin:test_password@otrohost:5433/reciclaje_test",  # host
])
@pytest.mark.parametrize("donde", ["principal", "worktree"])
def test_t10_la_guarda_movida_sigue_rechazando(tmp_path, url, donde):
    anchor = _main(tmp_path) if donde == "principal" else _worktree(tmp_path)
    with pytest.raises(RuntimeError, match="reciclaje_test\\* en localhost:5433"):
        resolve_test_database_url({"TEST_DATABASE_URL": url}, anchor)


def test_t10_control_una_base_de_sesion_pasa(tmp_path):
    assert resolve_test_database_url({"TEST_DATABASE_URL": SESSION_URL}, _worktree(tmp_path)) == SESSION_URL
