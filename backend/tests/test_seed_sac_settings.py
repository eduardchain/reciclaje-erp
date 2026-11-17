"""
Tests D11 de plan-sac-planta-como-proveedor (C1 de QA): el seeder no pisa
settings que no son suyos ni valores que alguien cambio.

Antes `patch_settings` mandaba en cada provision un REPLACE con
`settings_de_la_org()`, que no conoce `plant_third_party_id`: una re-provision
lo borraba en silencio y las maquilas volvian al par interno — justo lo que D3
de ese plan prohibe, entrando por otra puerta.

El falso hace REPLACE DE VERDAD, como el backend (`system.py`:
`model_dump(exclude_unset=True)` sobre `OrgSettingsPayload`, que ademas
rechaza claves y tipos que el backend rechazaria). Un falso que fusionara en
vez de reemplazar dejaria pasar justo el defecto que estos tests persiguen
(memoria: fake-mas-permisivo-que-backend).

Todo PURO: sin base de datos.
"""
import copy
import logging
import sys

import pytest

from app.schemas.organization import OrgSettingsPayload
from tests.test_archivar_org_sac import VIEJA, A, FakeApiRevisar, _con, seed

ORG = "org-sac"
BODEGAS = {w[0]: f"wh-{w[0]}" for w in seed.WAREHOUSES}
PLANTA = "8f0e2a52-5c1d-4f0e-9d6b-2b1d7f5e0a11"


class FakeOrgApi:
    """GET de la org y PATCH de sistema con semantica REPLACE."""

    def __init__(self, settings):
        self.stored = copy.deepcopy(settings)
        self.org_id = ORG
        self.dry_run = False
        self.is_local = True
        self.patches: list[dict] = []

    def get(self, path, params=None):
        assert path == f"/organizations/{ORG}", path
        return {"id": ORG, "settings": copy.deepcopy(self.stored)}

    def patch(self, path, body, label=""):
        assert path == f"/system/organizations/{ORG}", path
        self.patches.append(copy.deepcopy(body))
        payload = OrgSettingsPayload.model_validate(body["settings"])
        self.stored = payload.model_dump(exclude_unset=True)
        return {"id": ORG, "settings": copy.deepcopy(self.stored)}

    def login(self, email, password):
        pass


def _seeder(api, provisioning=True):
    s = seed.SacSeeder(api, "x")
    s.warehouses = dict(BODEGAS)
    s.provisioning = provisioning
    return s


def _del_seed():
    return seed.settings_de_la_org(BODEGAS)


class TestPatchSettings:
    """T14 (C1)."""

    def test_conserva_la_clave_ajena_y_escribe_las_que_faltan(self):
        vivos = {k: v for k, v in _del_seed().items() if k != "aging_buckets"}
        vivos["plant_third_party_id"] = PLANTA
        api = FakeOrgApi(vivos)
        s = _seeder(api)

        s.patch_settings()

        assert api.stored["plant_third_party_id"] == PLANTA
        assert api.stored["aging_buckets"] == [30, 60, 90]
        assert api.stored == {**_del_seed(), "plant_third_party_id": PLANTA}
        assert s.respected_settings == []

    def test_al_dia_no_escribe(self):
        api = FakeOrgApi({**_del_seed(), "plant_third_party_id": PLANTA})
        s = _seeder(api)
        s.patch_settings()
        assert api.patches == []
        assert s.respected_settings == []

    def test_no_pisa_una_clave_del_seeder_editada_y_la_lista(self):
        """Los centros Willard que Johana edita desde la pantalla (#87): antes la
        provision los revertia; ahora se respetan y deciden en DECISION
        PENDIENTE."""
        editados = ["baq", "bog", "pereira"]
        api = FakeOrgApi({**_del_seed(), "willard_distribution_centers": editados,
                          "plant_third_party_id": PLANTA})
        s = _seeder(api)

        s.patch_settings()

        assert api.stored["willard_distribution_centers"] == editados
        assert api.stored["plant_third_party_id"] == PLANTA
        assert len(s.respected_settings) == 1
        assert "willard_distribution_centers" in s.respected_settings[0]
        assert "pereira" in s.respected_settings[0]

    def test_una_clave_del_seeder_en_none_se_respeta(self):
        """H1 de QA — None PRESENTE no es "falta": el PATCH guarda con
        exclude_unset, asi que alguien lo mando a proposito. Apagar el reparto
        poniendo la sede que factura en None (#100 D4c) no puede volver a
        prenderse solo en la proxima provision."""
        api = FakeOrgApi({**_del_seed(), "willard_sede_facturacion": None})
        s = _seeder(api)

        s.patch_settings()

        assert api.stored["willard_sede_facturacion"] is None
        assert len(s.respected_settings) == 1
        assert "willard_sede_facturacion" in s.respected_settings[0]
        assert "None" in s.respected_settings[0]

    def test_org_vacia_recibe_todas_las_claves(self):
        """Una org recien creada no tiene settings (columna NULL): el flujo de
        --org-vacia -> provision sigue igual."""
        api = FakeOrgApi(None)
        s = _seeder(api)
        s.patch_settings()
        assert api.stored == _del_seed()
        assert s.respected_settings == []

    def test_org_creada_en_la_misma_corrida_no_lee_y_escribe_todo(self):
        api = FakeOrgApi(None)
        api.get = lambda path, params=None: pytest.fail("no deberia leer una org recien creada")
        s = _seeder(api, provisioning=False)
        s.patch_settings()
        assert api.stored == _del_seed()

    def test_decision_pendiente_sale_con_exit_3(self, monkeypatch, caplog):
        """El gate de #109 extendido a settings: una provision encadenada con
        `&&` se detiene, y el aviso es lo ultimo del log."""
        api = FakeOrgApi({**_del_seed(), "transfer_tolerance_pct": 0.1})

        def run(self, reset, org_vacia=False):
            self.warehouses = dict(BODEGAS)
            self.provisioning = True
            try:
                self.patch_settings()
            finally:
                self._report_respected_tariffs()

        monkeypatch.setattr(seed, "APIClient", lambda dry_run, base_url: api)
        monkeypatch.setattr(seed.SacSeeder, "run", run)
        monkeypatch.setattr(sys, "argv", ["seed", "--apply", "--superuser-email", "a@b",
                                          "--superuser-password", "x"])

        with caplog.at_level(logging.WARNING), pytest.raises(SystemExit) as exc:
            seed.main()

        assert exc.value.code == 3
        assert api.stored["transfer_tolerance_pct"] == 0.1
        assert "DECISION PENDIENTE" in caplog.text
        assert "transfer_tolerance_pct" in caplog.text


class TestRevisarClaveAjena:
    """T15 (C1) — `archivar_org_sac.py --modo revisar` informa la clave ajena a
    sabiendas, con el remedio, y no como una diferencia contra el seeder."""

    def test_la_clave_ajena_se_avisa_para_reaplicar(self):
        r = _con(lambda r: r[f"/organizations/{VIEJA}"]["settings"].update(
            plant_third_party_id=PLANTA))
        avisos = A.revisar(FakeApiRevisar(respuestas=r))
        assert len(avisos) == 1, avisos
        assert "plant_third_party_id" in avisos[0]
        assert "fuera del seeder" in avisos[0]
        assert "id NUEVO" in avisos[0]
        assert "la nueva nace con" not in avisos[0]
