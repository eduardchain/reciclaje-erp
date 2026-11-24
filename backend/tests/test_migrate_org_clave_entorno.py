"""La clave del superusuario sale del entorno, nunca de la linea de comandos.

Plan: docs/planes/plan-migrate-client-clave-entorno.md v1.3 (matriz de plantado
en matriz-plantado-migrate-client-clave.md). Hallazgo de QA 1 en 635c4b3: la
skill /migrate-client pasaba la clave como --superuser-password, a la vista de
`ps` y escrita en el chat.

- D1: --superuser-password queda definido SOLO para rechazarlo con exit 2 y sin
  repetir el valor. Si se quitara del parser, argparse cortaria con
  "unrecognized arguments: --superuser-password <VALOR>" y la clave iria al log.
- D2: la clave sale de SEED_SU_PASSWORD; --superuser-email es un override del
  email (default SEED_SU_EMAIL). El dry-run de migrate_org no la pide.
- D4 (b): la misma regla en seed_sac_org, archivar_org_sac, load_sac_opening y
  seed_demo_org.

Todos los subprocess corren SIN SEED_SU_* en el entorno y contra 127.0.0.1:9,
donde no escucha nada. seed_demo_org no tiene --api-url: su flag es --base-url,
y ningun test lo corre sin el (su default es localhost:8000, el backend de otra
sesion).
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
from openpyxl import Workbook

BACKEND = Path(__file__).resolve().parent.parent
SCRIPTS = BACKEND / "scripts"
PLANTILLA = BACKEND.parent / "data" / "migration_template.xlsx"
NADIE_ESCUCHA = "http://127.0.0.1:9"

CENTINELA = "CENTINELA-CLAVE-7f3a"
EMAIL_ENV = "su.entorno@example.com"
RECHAZO = "--superuser-password ya no se acepta"


class _LoginNoDebia(Exception):
    """El login no tenia que llamarse."""


class _Corte(Exception):
    """Corta el flujo despues de capturar el login (control positivo)."""


def _cargar(nombre: str, alias: str, monkeypatch):
    spec = importlib.util.spec_from_file_location(alias, SCRIPTS / nombre)
    mod = importlib.util.module_from_spec(spec)
    # seed_demo_org usa @dataclass con `from __future__ import annotations`:
    # dataclasses busca el modulo en sys.modules y sin registrarlo revienta con
    # AttributeError (medido en t6_causa.log). monkeypatch lo saca al terminar.
    monkeypatch.setitem(sys.modules, alias, mod)
    spec.loader.exec_module(mod)
    return mod


def _correr(script: str, *args: str) -> subprocess.CompletedProcess:
    entorno = {k: v for k, v in os.environ.items() if not k.startswith("SEED_SU_")}
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        capture_output=True, text=True, env=entorno, cwd=str(BACKEND), timeout=120,
    )


def _entorno(monkeypatch, email: bool, clave: bool) -> None:
    if email:
        monkeypatch.setenv("SEED_SU_EMAIL", EMAIL_ENV)
    else:
        monkeypatch.delenv("SEED_SU_EMAIL", raising=False)
    if clave:
        monkeypatch.setenv("SEED_SU_PASSWORD", CENTINELA)
    else:
        monkeypatch.delenv("SEED_SU_PASSWORD", raising=False)


def _primera_linea_error(texto: str) -> str:
    lineas = [ln for ln in texto.splitlines() if ln.startswith("ERROR: falta")]
    assert len(lineas) == 1, texto
    return lineas[0]


# (fila, hay email en el entorno, hay clave, nombres que la 1a linea DEBE traer, que NO debe)
FALTANTES = [
    ("falta_clave", True, False, ["SEED_SU_PASSWORD"], ["SEED_SU_EMAIL"]),
    ("falta_email", False, True, ["SEED_SU_EMAIL"], ["SEED_SU_PASSWORD"]),
    ("faltan_las_dos", False, False, ["SEED_SU_EMAIL", "SEED_SU_PASSWORD"], []),
]


# ------------------------------------------------------------------ migrate_org

def _argv_migrate(xlsx: Path, *extra: str) -> list[str]:
    return ["migrate_org.py", "--file", str(xlsx), "--org-name", "Org Clave Entorno",
            "--admin-email", "admin.clave@example.com", "--admin-name", "Admin", *extra]


@pytest.fixture
def xlsx_minimo(tmp_path) -> Path:
    ruta = tmp_path / "minimo.xlsx"
    Workbook().save(ruta)
    return ruta


class TestMigrateOrg:
    @pytest.mark.parametrize("forma", [
        pytest.param(["--superuser-password", CENTINELA], id="espacio"),
        pytest.param([f"--superuser-password={CENTINELA}"], id="igual"),
        pytest.param(["--superuser-pass", CENTINELA], id="abreviatura"),
    ])
    def test_t1_rechazo_sin_eco(self, tmp_path, forma):
        r = _correr("migrate_org.py", "--apply", "--api-url", NADIE_ESCUCHA,
                    *_argv_migrate(tmp_path / "no.xlsx")[1:], *forma)
        salida = r.stdout + r.stderr
        assert r.returncode == 2, salida
        assert RECHAZO in r.stderr and "SEED_SU_PASSWORD" in r.stderr, salida
        assert salida.count(CENTINELA) == 0
        # El rechazo va ANTES de leer el Excel y de cualquier llamada de red.
        assert "no encontrado" not in salida

    def test_t1_control_sin_flag_llega_al_excel(self, tmp_path):
        # Sin este control, «rechaza» y «muere antes por otra causa» se verian igual.
        r = _correr("migrate_org.py", "--apply", "--api-url", NADIE_ESCUCHA,
                    *_argv_migrate(tmp_path / "no.xlsx")[1:])
        salida = r.stdout + r.stderr
        assert r.returncode == 1, salida
        assert "no encontrado" in salida
        assert RECHAZO not in salida

    @pytest.mark.parametrize("fila,email,clave,nombra,no_nombra",
                             FALTANTES, ids=[f[0] for f in FALTANTES])
    def test_t2_apply_sin_entorno(self, monkeypatch, capsys, xlsx_minimo,
                                  fila, email, clave, nombra, no_nombra):
        mod = _cargar("migrate_org.py", f"migrate_org_t2_{fila}", monkeypatch)
        _entorno(monkeypatch, email, clave)

        def login(self, e, p):
            raise _LoginNoDebia(fila)

        monkeypatch.setattr(mod.APIClient, "login", login)
        monkeypatch.setattr(sys, "argv", _argv_migrate(xlsx_minimo, "--apply",
                                                       "--api-url", NADIE_ESCUCHA))
        with pytest.raises(SystemExit) as exc:
            mod.main()
        assert exc.value.code == 1
        out = capsys.readouterr()
        linea = _primera_linea_error(out.out)
        for n in nombra:
            assert n in linea, linea
        for n in no_nombra:
            assert n not in linea, linea
        assert (out.out + out.err).count(CENTINELA) == 0

    def test_t2_control_con_entorno_llama_login(self, monkeypatch, xlsx_minimo):
        mod = _cargar("migrate_org.py", "migrate_org_t2c", monkeypatch)
        _entorno(monkeypatch, True, True)
        llamadas = []

        def login(self, e, p):
            llamadas.append((e, p))
            return False

        monkeypatch.setattr(mod.APIClient, "login", login)
        monkeypatch.setattr(sys, "argv", _argv_migrate(xlsx_minimo, "--apply",
                                                       "--api-url", NADIE_ESCUCHA))
        with pytest.raises(SystemExit):
            mod.main()
        assert len(llamadas) == 1

    def test_t3_login_usa_el_entorno_sin_imprimirlo(self, monkeypatch, capsys, xlsx_minimo):
        mod = _cargar("migrate_org.py", "migrate_org_t3a", monkeypatch)
        _entorno(monkeypatch, True, True)
        llamadas = []

        def login(self, e, p):
            llamadas.append((e, p))
            return False

        monkeypatch.setattr(mod.APIClient, "login", login)
        monkeypatch.setattr(sys, "argv", _argv_migrate(xlsx_minimo, "--apply",
                                                       "--api-url", NADIE_ESCUCHA))
        with pytest.raises(SystemExit) as exc:
            mod.main()
        assert exc.value.code == 1
        assert llamadas == [(EMAIL_ENV, CENTINELA)]
        out = capsys.readouterr()
        assert (out.out + out.err).count(CENTINELA) == 0

    def test_t3_email_por_argv_gana_y_la_clave_sigue_del_entorno(self, monkeypatch, xlsx_minimo):
        mod = _cargar("migrate_org.py", "migrate_org_t3b", monkeypatch)
        _entorno(monkeypatch, True, True)
        llamadas = []

        def login(self, e, p):
            llamadas.append((e, p))
            return False

        monkeypatch.setattr(mod.APIClient, "login", login)
        monkeypatch.setattr(sys, "argv", _argv_migrate(
            xlsx_minimo, "--apply", "--api-url", NADIE_ESCUCHA,
            "--superuser-email", "otro.su@example.com"))
        with pytest.raises(SystemExit):
            mod.main()
        assert llamadas == [("otro.su@example.com", CENTINELA)]

    def test_t4_dry_run_sin_entorno_no_llama_login(self, monkeypatch, capsys):
        assert PLANTILLA.is_file(), PLANTILLA
        mod = _cargar("migrate_org.py", "migrate_org_t4", monkeypatch)
        _entorno(monkeypatch, False, False)

        def login(self, e, p):
            raise _LoginNoDebia("dry-run")

        monkeypatch.setattr(mod.APIClient, "login", login)
        monkeypatch.setattr(sys, "argv", _argv_migrate(PLANTILLA, "--dry-run",
                                                       "--api-url", NADIE_ESCUCHA))
        mod.main()
        out = capsys.readouterr().out
        assert "Done." in out
        assert "Autenticando" not in out


# ------------------------------------------------- los otros cuatro scripts (D4 b)

def _args_otros(script: str, tmp_path: Path) -> list[str]:
    return {
        "seed_sac_org.py": ["--api-url", NADIE_ESCUCHA],
        "archivar_org_sac.py": ["--modo", "revisar", "--api-url", NADIE_ESCUCHA],
        "load_sac_opening.py": ["--file", str(tmp_path / "no.xlsx"), "--corte", "2026-10-31",
                                "--fase", "saldos", "--api-url", NADIE_ESCUCHA],
        # Sin --superuser-email (O3): con required=True y los dos flags, argparse no
        # cortaria y P8 no se mediria. Y --base-url, no --api-url (C5).
        "seed_demo_org.py": ["--base-url", NADIE_ESCUCHA],
    }[script]


OTROS = ["seed_sac_org.py", "archivar_org_sac.py", "load_sac_opening.py", "seed_demo_org.py"]
IDS_OTROS = [s.removesuffix(".py") for s in OTROS]


class TestOtrosScripts:
    @pytest.mark.parametrize("script", OTROS, ids=IDS_OTROS)
    def test_t5_rechazo_en_los_otros_scripts(self, tmp_path, script):
        r = _correr(script, *_args_otros(script, tmp_path), "--superuser-password", CENTINELA)
        salida = r.stdout + r.stderr
        assert r.returncode == 2, salida
        assert RECHAZO in r.stderr and "SEED_SU_PASSWORD" in r.stderr, salida
        assert salida.count(CENTINELA) == 0

    @pytest.mark.parametrize("script", OTROS, ids=IDS_OTROS)
    def test_t5_control_sin_flag_no_rechaza(self, tmp_path, script):
        r = _correr(script, *_args_otros(script, tmp_path))
        assert RECHAZO not in r.stdout + r.stderr


# ---------------------------------------------------------- seed_demo_org (§4.4)

ARGV_DEMO = ["seed_demo_org.py", "--base-url", NADIE_ESCUCHA]


class TestSeedDemoOrg:
    @pytest.mark.parametrize("fila,email,clave,nombra,no_nombra",
                             FALTANTES, ids=[f[0] for f in FALTANTES])
    def test_t6_seed_demo_sin_variable(self, monkeypatch, fila, email, clave, nombra, no_nombra):
        mod = _cargar("seed_demo_org.py", f"seed_demo_org_t6_{fila}", monkeypatch)
        _entorno(monkeypatch, email, clave)

        def login(self, e, p):
            raise _LoginNoDebia(fila)

        monkeypatch.setattr(mod.APIClient, "login", login)
        monkeypatch.setattr(sys, "argv", list(ARGV_DEMO))
        with pytest.raises(SystemExit) as exc:
            mod.main()
        # In-process, raise SystemExit(msg) deja el string en .code; el exit 1 lo
        # pone el interprete (lo mide T6b en un subprocess). O1 de QA 2.
        mensaje = exc.value.code
        assert isinstance(mensaje, str), mensaje
        linea = _primera_linea_error(mensaje)
        for n in nombra:
            assert n in linea, linea
        for n in no_nombra:
            assert n not in linea, linea
        assert 'SEED_SU_EMAIL="$(sed' in mensaje
        assert mensaje.count(CENTINELA) == 0

    def test_t6_control_con_entorno_llama_login(self, monkeypatch, capsys):
        mod = _cargar("seed_demo_org.py", "seed_demo_org_t6c", monkeypatch)
        _entorno(monkeypatch, True, True)
        llamadas = []

        def login(self, e, p):
            llamadas.append((e, p))
            raise _Corte()

        monkeypatch.setattr(mod.APIClient, "login", login)
        monkeypatch.setattr(sys, "argv", list(ARGV_DEMO))
        with pytest.raises(_Corte):
            mod.main()
        assert llamadas == [(EMAIL_ENV, CENTINELA)]
        out = capsys.readouterr()
        assert (out.out + out.err).count(CENTINELA) == 0

    def test_t6b_seed_demo_exit_1_real(self):
        r = _correr("seed_demo_org.py", "--base-url", NADIE_ESCUCHA)
        salida = r.stdout + r.stderr
        assert r.returncode == 1, salida
        assert "ERROR: faltan SEED_SU_EMAIL y SEED_SU_PASSWORD en el entorno." in r.stderr, salida
        # El chequeo va antes del APIClient: nada de red ni tracebacks.
        assert "Traceback" not in salida and "Connection" not in salida
