"""T21 — script de la marca inicial del recolector (plan recolector-alcance §9).

Todo PURO: el backend es un doble que copia la FORMA real de las respuestas
(`OrganizationResponse`, `ThirdPartyResponse`) y los defaults que importan del
backend, nunca mas permisivo que el (memoria fake-mas-permisivo):
  - `GET /organizations/{id}` da 404 al superusuario si la org esta inactiva;
  - `GET /third-parties` devuelve tambien los inactivos (no filtra `is_active`);
  - `GET /third-parties/{id}` es por org: uno de otra org da 404.
"""
import importlib.util
import pathlib
import sys

import pytest

_SCRIPTS = pathlib.Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))
_spec = importlib.util.spec_from_file_location("marcar_recolector", _SCRIPTS / "marcar_recolector.py")
M = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = M
_spec.loader.exec_module(M)

ORG = "11111111-1111-1111-1111-111111111111"
COSTA = "22222222-2222-2222-2222-222222222222"
GL = "aaaaaaaa-0000-0000-0000-000000000001"
OTRO_REC = "aaaaaaaa-0000-0000-0000-000000000002"
BIO = "aaaaaaaa-0000-0000-0000-000000000003"

_n = [0]


def _id() -> str:
    _n[0] += 1
    return f"bbbbbbbb-0000-0000-0000-{_n[0]:012d}"


def _org(org_id=ORG, name="SAC", active=True, kg=True) -> dict:
    """Forma de `OrganizationResponse`."""
    return {
        "id": org_id, "name": name, "slug": "sac", "logo_url": None,
        "subscription_plan": "basic", "subscription_status": "active", "max_users": 10,
        "is_active": active, "created_at": "2026-11-10T19:05:00Z", "member_role": None,
        "settings": {"kg_ledger_enabled": kg, "two_step_transfers_enabled": True},
    }


def _cat(bt: str) -> dict:
    return {"id": _id(), "name": bt, "display_name": bt, "behavior_type": bt}


def _tp(name, tp_id=None, org_id=ORG, active=True, collector_id=None, bt="material_supplier") -> dict:
    """Forma de `ThirdPartyResponse`."""
    return {
        "id": tp_id or _id(), "organization_id": org_id, "name": name,
        "identification_number": None, "email": None, "phone": None, "address": None,
        "initial_balance": 0.0, "current_balance": 0.0, "is_active": active,
        "categories": [_cat(bt)], "collector_id": collector_id, "collector_name": None,
        "created_at": "2026-11-10T19:05:00Z", "updated_at": "2026-11-10T19:05:00Z",
    }


class FakeCliente:
    def __init__(self, orgs: list[dict], terceros: list[dict]):
        self.orgs = {o["id"]: o for o in orgs}
        self.terceros = terceros
        self.org_header = None
        self.patches: list[tuple[str, dict]] = []
        self.patch_falla_en: str | None = None

    def usar_org(self, org_id):
        self.org_header = str(org_id)

    def get_opcional(self, path):
        partes = path.strip("/").split("/")
        if partes[0] == "organizations":
            org = self.orgs.get(partes[1])
            # Backend: 404 al superusuario si la org esta inactiva.
            return org if org and org["is_active"] else None
        if partes[0] == "third-parties":
            assert self.org_header, "el tercero se pide sin X-Organization-ID"
            for t in self.terceros:
                if t["id"] == partes[1] and t["organization_id"] == self.org_header:
                    return t
            return None
        raise AssertionError(path)

    def listar_terceros(self):
        assert self.org_header, "el listado se pide sin X-Organization-ID"
        # Sin filtro de is_active, igual que el backend.
        return [t for t in self.terceros if t["organization_id"] == self.org_header]

    def patch(self, path, body):
        if self.patch_falla_en and path.endswith(self.patch_falla_en):
            raise SystemExit(f"PATCH {path} failed [422]")
        self.patches.append((path, body))
        return {}


def _base() -> list[dict]:
    return [
        _tp("Green Loop", tp_id=GL, bt="service_provider"),
        _tp("BIOGREENLOOP", tp_id=BIO),
        _tp("ABRAHAM CABARCAS (GREENLOOP)"),
        _tp("DANIEL DE LA HOZ (GREENLOP)", bt="generic"),
        _tp("ADALBERTO AVILA (GREENLOOP)"),
        _tp("ASOCIACION BIOGREEN RECYCLING"),
        _tp("ECOGREEN"),
        _tp("Otro Recolector", tp_id=OTRO_REC, bt="service_provider"),
    ]


def _correr(terceros=None, orgs=None, apply=False, esperado=None, collector=GL, org=ORG):
    lineas: list[str] = []
    cli = FakeCliente(orgs if orgs is not None else [_org()], terceros if terceros is not None else _base())
    code = M.ejecutar(cli, org, collector, apply, esperado, out=lineas.append)
    return code, cli, lineas


# ---------------------------------------------------------------------------
# Normalizacion, con los nombres reales
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nombre, cumple", [
    ("ABRAHAM CABARCAS (GREENLOOP)", True),
    ("DANIEL DE LA HOZ (GREENLOP)", True),
    ("Bio Green Loop- Maquila", True),          # espacios y guion (P34)
    ("Maquila Greenloop", True),
    ("GRÉENLOOP SAS", True),                     # sin NFKD queda «grenloop» (P35)
    ("ASOCIACION BIOGREEN RECYCLING", False),
    ("ECOGREEN", False),
    ("CARLOS CASTAÑO (GREENLOOP)", True),        # cordura (n5): la Ñ no rompe nada
])
def test_normalizacion_casos_reales(nombre, cumple):
    assert M.cumple_regla(nombre) is cumple


def test_normalizar_sin_nfkd_no_alcanza_greenloop():
    """Control de P35: lo que hace NFKD es justo lo que este caso necesita."""
    assert M.normalizar("GRÉENLOOP") == "greenloop"
    sin_nfkd = "".join(c for c in "GRÉENLOOP".lower() if "a" <= c <= "z")
    assert "greenloop" not in sin_nfkd


# ---------------------------------------------------------------------------
# El plan
# ---------------------------------------------------------------------------

def test_dry_run_marca_lo_de_la_regla_y_excluye_con_motivo():
    code, cli, lineas = _correr()
    assert code == M.EXIT_OK
    assert cli.patches == []
    texto = "\n".join(lineas)
    assert "a marcar: 3" in texto
    assert "ADALBERTO AVILA (GREENLOOP)" in texto
    assert M.MOTIVO_RECOLECTOR in texto and M.MOTIVO_BIOGREENLOOP in texto
    assert "ASOCIACION BIOGREEN RECYCLING" not in texto and "ECOGREEN" not in texto


def test_apply_escribe_un_patch_por_tercero_con_el_recolector():
    code, cli, _ = _correr(apply=True, esperado=3)
    assert code == M.EXIT_OK
    assert len(cli.patches) == 3
    assert all(body == {"collector_id": GL} for _, body in cli.patches)
    assert not any(p.endswith(GL) or p.endswith(BIO) for p, _ in cli.patches)


def test_sin_biogreenloop_es_sorpresa_y_no_escribe():
    terceros = [t for t in _base() if t["id"] != BIO]
    code, cli, lineas = _correr(terceros=terceros, apply=True)
    assert code == M.EXIT_SORPRESA
    assert cli.patches == []
    assert any("BIOGREENLOOP» aparece 0 veces" in s for s in lineas)


def test_biogreenloop_dos_veces_es_sorpresa():
    terceros = _base() + [_tp("Bio-Greenloop")]
    code, cli, _ = _correr(terceros=terceros, apply=True)
    assert code == M.EXIT_SORPRESA and cli.patches == []


def test_recolector_fuera_de_la_regla_es_sorpresa():
    terceros = _base()
    terceros[0] = _tp("Recolecciones del Caribe", tp_id=GL, bt="service_provider")
    code, cli, lineas = _correr(terceros=terceros, apply=True)
    assert code == M.EXIT_SORPRESA and cli.patches == []
    assert any("el recolector aparece 0 veces" in s for s in lineas)


def test_inactivo_se_salta_sin_sorpresa():
    terceros = _base() + [_tp("JOSE PEREZ (GREENLOOP)", active=False)]
    code, cli, lineas = _correr(terceros=terceros, apply=True, esperado=3)
    assert code == M.EXIT_OK
    assert len(cli.patches) == 3
    assert any("JOSE PEREZ (GREENLOOP)" in s and M.MOTIVO_INACTIVO in s for s in lineas)


def test_idempotencia_ya_marcado_se_salta():
    terceros = _base()
    for t in terceros:
        if "(GREENLOO" in t["name"] or "(GREENLOP" in t["name"]:
            t["collector_id"] = GL
    code, cli, lineas = _correr(terceros=terceros, apply=True, esperado=0)
    assert code == M.EXIT_OK and cli.patches == []
    assert "ya marcados: 3" in lineas


def test_marcado_con_otro_recolector_no_se_pisa():
    terceros = _base()
    otro = _tp("PEDRO (GREENLOOP)", collector_id=OTRO_REC)
    terceros.append(otro)
    code, cli, lineas = _correr(terceros=terceros, apply=True)
    assert code == M.EXIT_SORPRESA and cli.patches == []
    plan = M.armar_plan(terceros, ORG, GL)
    assert otro not in plan.a_marcar


def test_marcado_a_mano_fuera_de_la_regla_es_informativo():
    terceros = _base() + [_tp("CONDUCTOR RUIZ", collector_id=GL, bt="generic")]
    code, cli, lineas = _correr(terceros=terceros, apply=True, esperado=3)
    assert code == M.EXIT_OK and len(cli.patches) == 3
    assert any("CONDUCTOR RUIZ" in s and "fuera de la regla" in s for s in lineas)


def test_esperado_distinto_es_sorpresa_sin_escrituras():
    code, cli, lineas = _correr(apply=True, esperado=124)
    assert code == M.EXIT_SORPRESA and cli.patches == []
    assert any("la prediccion escrita era 124" in s for s in lineas)


def test_con_sorpresa_no_escribe_lo_que_no_es_sorpresa():
    """P39: con una sorpresa, ni los tres que si cumplen se escriben."""
    terceros = _base() + [_tp("PEDRO (GREENLOOP)", collector_id=OTRO_REC)]
    code, cli, _ = _correr(terceros=terceros, apply=True)
    assert code == M.EXIT_SORPRESA
    assert len(cli.patches) == 0


# ---------------------------------------------------------------------------
# Org y recolector: abortan antes de leer terceros
# ---------------------------------------------------------------------------

def test_org_sin_flag_aborta():
    code, cli, lineas = _correr(orgs=[_org(kg=False)], apply=True)
    assert code == M.EXIT_ABORTO and cli.patches == []
    assert any("kg_ledger_enabled" in s for s in lineas)


def test_org_inactiva_aborta():
    code, cli, _ = _correr(orgs=[_org(active=False)], apply=True)
    assert code == M.EXIT_ABORTO and cli.patches == []


def test_org_de_otra_org_no_mezcla_terceros():
    """La org va por id: los «greenloop» de Costa no entran."""
    terceros = _base() + [_tp("Bio Green Loop- Maquila", org_id=COSTA),
                          _tp("Maquila Greenloop", org_id=COSTA)]
    code, cli, _ = _correr(terceros=terceros, orgs=[_org(), _org(COSTA, "Costa")],
                           apply=True, esperado=3)
    assert code == M.EXIT_OK and len(cli.patches) == 3


def test_recolector_que_no_es_service_provider_aborta():
    terceros = _base()
    terceros[0] = _tp("Green Loop", tp_id=GL, bt="material_supplier")
    code, cli, lineas = _correr(terceros=terceros, apply=True)
    assert code == M.EXIT_ABORTO and cli.patches == []
    assert any("no es service_provider" in s for s in lineas)


def test_recolector_de_otra_org_aborta():
    terceros = _base()
    terceros[0] = _tp("Green Loop", tp_id=GL, org_id=COSTA, bt="service_provider")
    code, cli, _ = _correr(terceros=terceros, orgs=[_org(), _org(COSTA, "Costa")], apply=True)
    assert code == M.EXIT_ABORTO and cli.patches == []


def test_listado_incompleto_aborta():
    cli = FakeCliente([_org()], _base())

    def _corto():
        raise SystemExit("/third-parties: se leyeron 100 de 128. No se sigue.")
    cli.listar_terceros = _corto
    code = M.ejecutar(cli, ORG, GL, True, None, out=lambda *_: None)
    assert code == M.EXIT_ABORTO and cli.patches == []


def test_patch_que_falla_detiene_con_exit_1():
    cli = FakeCliente([_org()], _base())
    a_marcar = M.armar_plan(_base(), ORG, GL).a_marcar
    cli.terceros = _base()
    # El segundo de la lista, en el orden en que se escriben.
    cli.patch_falla_en = M.armar_plan(cli.terceros, ORG, GL).a_marcar[1]["id"]
    code = M.ejecutar(cli, ORG, GL, True, len(a_marcar), out=lambda *_: None)
    assert code == M.EXIT_PATCH
    assert len(cli.patches) == 1
