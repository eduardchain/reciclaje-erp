"""
T6 de plan-sac-retefuente-porcentajes: el seeder no vuelve a crear una tarifa
de retención que Johana desactivó.

El POST de `/third-parties/retention-configs` solo responde 409 ante una
tarifa ACTIVA (#79 D14, `find_active_config`). Antes, `create_retention_configs`
solo toleraba ese 409, así que una tarifa desactivada renacía en cada
provisión — y con ella el default que propone «+ Retención».

El falso se porta como el backend (memoria: fake-mas-permisivo-que-backend):
- el GET devuelve TODAS las configs, activas e inactivas, con su municipio y
  su concepto tal como se guardaron (`list_retention_rows` no filtra estado);
- el POST da 409 SOLO si choca con una ACTIVA, con la misma normalización
  del servicio (`find_active_config`); si no, crea la fila.

Todo PURO: sin base de datos.
"""
import copy

from app.services.retention_entities import normalize_entity_name
from tests.test_archivar_org_sac import seed


def _norm(v):
    return normalize_entity_name(v) if v else None


def _row(tipo, rate, *, muni=None, concept=None, active=True, cid=None):
    return {
        "config_id": cid or f"cfg-{tipo}-{muni or ''}-{concept or ''}-{rate}",
        "entity_id": None,
        "retention_type": tipo,
        "municipality": muni,
        "concept": concept,
        "rate_pct": float(rate),
        "base_kind": "subtotal",
        "name": None,
        "current_balance": 0.0,
        "is_active": active,
    }


class FakeRetentionApi:
    def __init__(self, rows):
        self.rows = copy.deepcopy(rows)
        self.dry_run = False
        self.is_local = True
        self.posts: list[dict] = []
        self.conflicts: list[dict] = []

    def get(self, path, params=None):
        assert path == "/third-parties/retention-entities", path
        return copy.deepcopy(self.rows)

    def post_tolerating(self, path, body, ok_codes, label=""):
        assert path == "/third-parties/retention-configs", path
        self.posts.append(copy.deepcopy(body))
        key = (body["retention_type"], _norm(body.get("municipality")), _norm(body.get("concept")))
        for r in self.rows:
            if r["is_active"] and (
                r["retention_type"], _norm(r["municipality"]), _norm(r["concept"])
            ) == key:
                assert 409 in ok_codes
                self.conflicts.append(copy.deepcopy(body))
                return None
        self.rows.append(_row(
            body["retention_type"], body["rate_pct"],
            muni=body.get("municipality"), concept=body.get("concept"),
        ))
        return {"id": self.rows[-1]["config_id"]}


def _run(rows):
    api = FakeRetentionApi(rows)
    seed.SacSeeder(api, "x").create_retention_configs()
    return api


def _tipos_posteados(api):
    return [(p["retention_type"], p.get("municipality")) for p in api.posts]


class TestCreateRetentionConfigs:
    def test_catalogo_vacio_crea_las_tres(self):
        api = _run([])
        assert _tipos_posteados(api) == [
            ("retefuente", None), ("reteiva", None), ("ica", "Barranquilla"),
        ]
        assert len(api.rows) == 3

    def test_retefuente_inactiva_no_se_vuelve_a_crear(self):
        """El caso del plan: Johana desactivó la general."""
        api = _run([_row("retefuente", "2.5", active=False)])
        assert ("retefuente", None) not in _tipos_posteados(api)
        generales = [r for r in api.rows if r["retention_type"] == "retefuente"]
        assert len(generales) == 1 and generales[0]["is_active"] is False
        # Las que faltan sí se crean
        assert _tipos_posteados(api) == [("reteiva", None), ("ica", "Barranquilla")]

    def test_activa_no_duplica_ni_revienta(self):
        api = _run([_row("retefuente", "2.5")])
        assert ("retefuente", None) not in _tipos_posteados(api)
        assert api.conflicts == []
        assert len([r for r in api.rows if r["retention_type"] == "retefuente"]) == 1

    def test_ica_inactiva_con_otra_grafia_se_reconoce(self):
        """Normalización del servicio: «barranquillá» == «Barranquilla»."""
        api = _run([_row("ica", "0.7", muni="  barranquillá ", active=False)])
        assert ("ica", "Barranquilla") not in _tipos_posteados(api)
        assert len([r for r in api.rows if r["retention_type"] == "ica"]) == 1

    def test_tarifa_con_concepto_no_tapa_a_la_general(self):
        """Una «No declarante» no es la general: la general falta y se crea."""
        api = _run([_row("retefuente", "3.5", concept="No declarante")])
        assert ("retefuente", None) in _tipos_posteados(api)

    def test_ica_de_otro_municipio_no_tapa_a_barranquilla(self):
        api = _run([_row("ica", "0.7", muni="Soledad", active=False)])
        assert ("ica", "Barranquilla") in _tipos_posteados(api)

    def test_dry_run_no_consulta(self):
        api = FakeRetentionApi([])
        api.dry_run = True
        api.get = None  # si se llama, revienta
        seed.SacSeeder(api, "x").create_retention_configs()
        assert len(api.posts) == 3
