"""
Tests de lo que hace falta para cargar la SAC en produccion sin tocar la base:
archivar la org anterior y darla de baja sin dejar usuarios desactivados
(scripts/archivar_org_sac.py), y los dos cambios del seeder que lo acompanan:
--org-vacia sin --reset y el listado completo de existing_by (N1 de QA).

Todo PURO: el backend es un falso, no hace falta base de datos.
"""
import importlib.util
import pathlib
import sys
from datetime import datetime

import pytest

_SCRIPTS = pathlib.Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))
_spec = importlib.util.spec_from_file_location("archivar_org_sac", _SCRIPTS / "archivar_org_sac.py")
A = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = A
_spec.loader.exec_module(A)
seed = A.seed

AHORA = datetime(2020, 1, 31, 18, 5)
VIEJA, NUEVA, OTRA = "org-vieja", "org-nueva", "org-costa"


def _usuario(uid, email, orgs, superuser=False):
    return {"id": uid, "email": email, "is_superuser": superuser, "is_active": True,
            "memberships": [{"organization_id": o, "role_name": r} for o, r in orgs]}


class _Resp:
    def __init__(self, data, status=200):
        self._data, self.status_code, self.text = data, status, "x"

    def json(self):
        return self._data


ROLES_NUEVA = {"rol-admin": "admin", "rol-bas": "bascula_sac"}


class FakeApi:
    """Backend falso de /system: orgs, usuarios y roles; anota lo que escribe.

    La baja calcula los huerfanos con la MISMA regla del backend
    (delete_system_organization): todo miembro sin otra membresia, en cualquier
    org, superusuario o no. Con un 0 fijo, el test de B2 no podia caer (QA).
    """

    def __init__(self, orgs, usuarios, huerfanos=None):
        self.orgs, self.usuarios, self.huerfanos = orgs, usuarios, huerfanos
        self.base_url, self.is_local = "http://localhost:8000", True
        self.patches, self.posts, self.deletes = [], [], []
        self.session = self

    def _headers(self):
        return {}

    def get(self, path, params=None):
        if path == "/system/organizations":
            # Como el backend (list_all_organizations): sin include_inactive no
            # devuelve las dadas de baja. Con el fake devolviendolas siempre, el
            # test de restaurar una dada de baja pasaba y el script no la hallaba.
            if (params or {}).get("include_inactive"):
                return self.orgs
            return [o for o in self.orgs if o.get("is_active", True)]
        if path == "/system/users":
            return self.usuarios
        if path == f"/system/organizations/{NUEVA}/roles":
            return [{"name": "admin", "id": "rol-admin"}, {"name": "bascula_sac", "id": "rol-bas"}]
        raise AssertionError(path)

    def patch(self, path, body, label=""):
        self.patches.append((path, body))
        org = next(o for o in self.orgs if path.endswith(o["id"]))
        return {**org, **body}

    def post(self, path, body, label=""):
        self.posts.append((path, body))
        if path.endswith("/add-to-org"):
            uid = path.split("/")[3]
            u = next(x for x in self.usuarios if x["id"] == uid)
            u["memberships"].append({"organization_id": body["organization_id"],
                                     "role_name": ROLES_NUEVA[body["role_id"]]})
        return {}

    def delete(self, url, headers=None):
        self.deletes.append(url)
        org = url.rsplit("/", 1)[1]
        if self.huerfanos is not None:
            return _Resp({"orphaned_users_deactivated": self.huerfanos})
        huerfanos = 0
        for u in self.usuarios:
            orgs = [m["organization_id"] for m in u["memberships"]]
            if org in orgs and not [o for o in orgs if o != org]:
                u["is_active"] = False
                huerfanos += 1
        return _Resp({"orphaned_users_deactivated": huerfanos})


def _org(oid, nombre, activa=True):
    return {"id": oid, "name": nombre, "is_active": activa}


ARCHIVADA = A.nombre_archivada(AHORA)


class TestArchivar:
    def test_renombra_la_unica_sac_activa(self):
        api = FakeApi([_org(VIEJA, "SAC"), _org(OTRA, "RECICLAJES NACIONALES S.A.S")], [])
        A.archivar(api, apply=True, ahora=AHORA)
        assert api.patches == [(f"/system/organizations/{VIEJA}", {"name": "SAC (archivada 2020-01-31 1805)"})]

    def test_sin_apply_no_escribe(self):
        api = FakeApi([_org(VIEJA, "SAC")], [])
        A.archivar(api, apply=False, ahora=AHORA)
        assert api.patches == []

    def test_si_el_renombre_no_quedo_falla_fuerte(self):
        # El seeder crearia despues una segunda «SAC» activa al lado de esta.
        api = FakeApi([_org(VIEJA, "SAC")], [])
        api.patch = lambda path, body, label="": _org(VIEJA, "SAC")
        with pytest.raises(SystemExit, match="no quedó"):
            A.archivar(api, apply=True, ahora=AHORA)

    @pytest.mark.parametrize("orgs", [
        [],
        [_org(VIEJA, "SAC", activa=False)],
        [_org(VIEJA, "SAC"), _org(NUEVA, "SAC")],
    ])
    def test_se_niega_si_no_hay_exactamente_una(self, orgs):
        api = FakeApi(orgs, [])
        with pytest.raises(SystemExit, match="UNA org activa"):
            A.archivar(api, apply=True, ahora=AHORA)
        assert api.patches == []


class TestBaja:
    def _api(self, usuarios, huerfanos=None, vieja_activa=True, nombre_vieja=ARCHIVADA):
        return FakeApi([_org(VIEJA, nombre_vieja, vieja_activa), _org(NUEVA, "SAC"),
                        _org(OTRA, "RECICLAJES NACIONALES S.A.S")], usuarios, huerfanos)

    def test_con_todos_en_la_nueva_da_de_baja(self):
        api = self._api([_usuario("u1", "hugo@sac.com", [(VIEJA, "admin"), (NUEVA, "admin")]),
                         _usuario("su", "admin@x", [(VIEJA, "admin"), (NUEVA, "admin")], superuser=True)])
        A.dar_de_baja(api, VIEJA, apply=True, copiar=False)
        assert api.deletes == [f"http://localhost:8000{seed.API_PREFIX}/system/organizations/{VIEJA}"]
        assert api.posts == []
        assert all(u["is_active"] for u in api.usuarios)

    def test_el_fake_desactiva_como_el_backend(self):
        # Control del fake: sin esto, «0 desactivados» saldria verde siempre.
        api = self._api([_usuario("u2", "solo@sac.com", [(VIEJA, "admin")])])
        api.delete(f"x/system/organizations/{VIEJA}")
        assert api.usuarios[0]["is_active"] is False

    def test_superusuario_solo_en_la_archivada_detiene_y_se_nombra(self):
        """B2 de QA: el backend tambien desactiva a un superusuario huerfano. Si es
        la cuenta con la que se corre, queda fuera del sistema."""
        api = self._api([_usuario("u1", "hugo@sac.com", [(VIEJA, "admin"), (NUEVA, "admin")]),
                         _usuario("su", "admin@x", [(VIEJA, "admin")], superuser=True)])
        with pytest.raises(SystemExit, match="admin@x"):
            A.dar_de_baja(api, VIEJA, apply=True, copiar=False)
        assert api.deletes == [] and all(u["is_active"] for u in api.usuarios)

    def test_superusuario_se_copia_como_cualquiera(self):
        api = self._api([_usuario("su", "admin@x", [(VIEJA, "admin")], superuser=True)])
        A.dar_de_baja(api, VIEJA, apply=True, copiar=True)
        assert api.posts == [("/system/users/su/add-to-org", {"organization_id": NUEVA, "role_id": "rol-admin"})]
        assert len(api.deletes) == 1 and api.usuarios[0]["is_active"] is True

    def test_un_miembro_que_no_esta_en_la_nueva_detiene_y_se_nombra(self):
        api = self._api([_usuario("u1", "hugo@sac.com", [(VIEJA, "admin"), (NUEVA, "admin")]),
                         _usuario("u2", "david@sac.com", [(VIEJA, "bascula_sac")])])
        with pytest.raises(SystemExit, match="david@sac.com"):
            A.dar_de_baja(api, VIEJA, apply=True, copiar=False)
        assert api.deletes == [] and api.posts == []

    def test_copiar_miembros_los_agrega_con_su_rol_antes_de_la_baja(self):
        api = self._api([_usuario("u2", "david@sac.com", [(VIEJA, "bascula_sac")])])
        A.dar_de_baja(api, VIEJA, apply=True, copiar=True)
        assert api.posts == [("/system/users/u2/add-to-org",
                              {"organization_id": NUEVA, "role_id": "rol-bas"})]
        assert len(api.deletes) == 1

    def test_copiar_sin_el_rol_en_la_nueva_detiene(self):
        api = self._api([_usuario("u2", "x@sac.com", [(VIEJA, "rol_que_no_existe")])])
        with pytest.raises(SystemExit, match="no tiene el rol"):
            A.dar_de_baja(api, VIEJA, apply=True, copiar=True)
        assert api.deletes == [] and api.posts == []

    @pytest.mark.parametrize("nombre", ["SAC", "RECICLAJES NACIONALES S.A.S", "SAC pruebas"])
    def test_solo_da_de_baja_una_org_archivada(self, nombre):
        api = self._api([], nombre_vieja=nombre)
        with pytest.raises(SystemExit, match="solo se da de baja una org archivada"):
            A.dar_de_baja(api, VIEJA, apply=True, copiar=False)
        assert api.deletes == []

    def test_ya_inactiva_no_se_vuelve_a_dar_de_baja(self):
        api = self._api([], vieja_activa=False)
        with pytest.raises(SystemExit, match="ya está dada de baja"):
            A.dar_de_baja(api, VIEJA, apply=True, copiar=False)

    def test_si_la_baja_desactiva_a_alguien_falla_fuerte(self):
        api = self._api([], huerfanos=2)
        with pytest.raises(SystemExit, match="desactivó 2"):
            A.dar_de_baja(api, VIEJA, apply=True, copiar=False)

    def test_sin_apply_no_escribe(self):
        api = self._api([_usuario("u2", "david@sac.com", [(VIEJA, "bascula_sac")])])
        A.dar_de_baja(api, VIEJA, apply=False, copiar=True)
        assert api.deletes == [] and api.posts == []


class TestRestaurar:
    """C1 de QA: si la ronda falla en el paso 2, la vieja ya esta archivada y la
    nueva no existe. Y despues de la baja, la pantalla renombra pero no reactiva."""

    def test_devuelve_el_nombre_y_reactiva_una_dada_de_baja(self):
        api = FakeApi([_org(VIEJA, ARCHIVADA, activa=False), _org(OTRA, "RECICLAJES NACIONALES S.A.S")], [])
        r = A.restaurar(api, VIEJA, apply=True)
        assert api.patches == [(f"/system/organizations/{VIEJA}", {"name": "SAC", "is_active": True})]
        assert r["name"] == "SAC" and r["is_active"] is True

    def test_sin_apply_no_escribe(self):
        api = FakeApi([_org(VIEJA, ARCHIVADA)], [])
        A.restaurar(api, VIEJA, apply=False)
        assert api.patches == []

    def test_con_otra_sac_activa_se_niega(self):
        # Dos «SAC» activas confundirian al seeder y al cargador.
        api = FakeApi([_org(VIEJA, ARCHIVADA), _org(NUEVA, "SAC")], [])
        with pytest.raises(SystemExit, match="Ya hay una org activa"):
            A.restaurar(api, VIEJA, apply=True)
        assert api.patches == []

    @pytest.mark.parametrize("nombre", ["RECICLAJES NACIONALES S.A.S", "SAC"])
    def test_solo_restaura_una_org_archivada(self, nombre):
        # Un id equivocado no puede renombrar a otra empresa.
        api = FakeApi([_org(OTRA, nombre, activa=False)], [])
        with pytest.raises(SystemExit, match="solo se restaura una org archivada"):
            A.restaurar(api, OTRA, apply=True)
        assert api.patches == []

    def test_id_que_no_existe(self):
        api = FakeApi([_org(VIEJA, ARCHIVADA)], [])
        with pytest.raises(SystemExit, match="No existe"):
            A.restaurar(api, "org-x", apply=True)

    def test_si_no_quedo_activa_falla_fuerte(self):
        api = FakeApi([_org(VIEJA, ARCHIVADA, activa=False)], [])
        api.patch = lambda path, body, label="": _org(VIEJA, "SAC", activa=False)
        with pytest.raises(SystemExit, match="no quedó"):
            A.restaurar(api, VIEJA, apply=True)


# ---------------------------------------------------------------------------
# Seeder: listado completo (N1) y --org-vacia sin --reset
# ---------------------------------------------------------------------------

class _Sesion:
    """Sesion HTTP falsa para APIClient.get: pagina una lista con skip/limit."""

    def __init__(self, filas, total=None, plana=False, corta_en=None):
        self.filas, self.total, self.plana, self.corta_en = filas, total, plana, corta_en
        self.pedidos = []

    def get(self, url, headers=None, params=None):
        self.pedidos.append(dict(params or {}))
        if self.plana:
            return _Resp(self.filas)
        skip, limit = params["skip"], params["limit"]
        pagina = [] if self.corta_en is not None and skip >= self.corta_en else self.filas[skip:skip + limit]
        return _Resp({"items": pagina, "total": len(self.filas) if self.total is None else self.total})


def _cliente(sesion):
    api = seed.APIClient(dry_run=False, base_url="http://localhost:8000")
    api.session = sesion
    return api


class TestListadoCompleto:
    def test_pagina_hasta_el_total(self):
        filas = [{"name": f"T{i}", "id": str(i)} for i in range(1203)]
        sesion = _Sesion(filas)
        api = _cliente(sesion)
        assert len(api.existing_by("/third-parties", "name")) == 1203
        assert [p["skip"] for p in sesion.pedidos] == [0, 500, 1000]

    def test_si_no_llega_al_total_se_detiene(self):
        filas = [{"name": f"T{i}", "id": str(i)} for i in range(800)]
        api = _cliente(_Sesion(filas, corta_en=500))
        with pytest.raises(SystemExit, match="se leyeron 500 de 800"):
            api.existing_by("/third-parties", "name")

    def test_un_endpoint_que_ignora_skip_no_pasa_con_duplicados(self):
        """O1 de QA: con `< total` el bucle salia con la pagina repetida (1000
        filas de 800) y nadie se enteraba."""
        filas = [{"name": f"T{i}", "id": str(i)} for i in range(800)]
        sesion = _Sesion(filas)
        sesion.get = lambda url, headers=None, params=None: _Resp({"items": filas[:500], "total": 800})
        with pytest.raises(SystemExit, match="se leyeron 1000 de 800"):
            _cliente(sesion).existing_by("/third-parties", "name")

    def test_lista_plana_llena_puede_estar_cortada(self):
        api = _cliente(_Sesion([{"code": str(i)} for i in range(500)], plana=True))
        with pytest.raises(SystemExit, match="sin total"):
            api.existing_by("/kg-ledger/accounts", "code")

    def test_lista_plana_corta_se_acepta(self):
        api = _cliente(_Sesion([{"code": "A"}, {"code": "B"}], plana=True))
        assert set(api.existing_by("/kg-ledger/accounts", "code")) == {"A", "B"}


class TestOrgVaciaSinReset:
    def _seeder(self, monkeypatch, existente):
        api = seed.APIClient(dry_run=False, base_url="https://api.ejemplo.test")
        s = seed.SacSeeder(api, "x")
        llamadas = []
        monkeypatch.setattr(s, "_find_existing_org", lambda: existente)
        monkeypatch.setattr(s, "create_or_reset_org", lambda reset: llamadas.append(("org", reset)))
        monkeypatch.setattr(s, "create_users_and_roles", lambda: llamadas.append("usuarios"))
        monkeypatch.setattr(s, "_force_known_passwords", lambda: None)
        return s, llamadas

    def test_con_una_sac_activa_se_niega_sin_crear_nada(self, monkeypatch):
        s, llamadas = self._seeder(monkeypatch, {"id": "org-vieja", "name": "SAC"})
        with pytest.raises(SystemExit, match="Ya hay una org activa"):
            s._run_org_vacia(reset=False)
        assert llamadas == []

    def test_sin_sac_activa_la_crea_vacia(self, monkeypatch):
        s, llamadas = self._seeder(monkeypatch, None)
        s._run_org_vacia(reset=False)
        assert llamadas == [("org", False), "usuarios"]

    def test_reset_sigue_prohibido_contra_un_servidor_remoto(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["seed", "--apply", "--reset", "--org-vacia",
                                          "--api-url", "https://api.ejemplo.test",
                                          "--superuser-email", "a@b", "--superuser-password", "x"])
        with pytest.raises(SystemExit, match="prohibido"):
            seed.main()


# ---------------------------------------------------------------------------
# --modo revisar: solo lectura, lo que la SAC nueva no heredaria (C3 de QA)
# ---------------------------------------------------------------------------

def _paginado(filas):
    return {"items": filas, "total": len(filas)}


def _como_el_seeder():
    """Las respuestas de una org recien provista por el seeder: cero avisos."""
    bodegas = [{"name": w[0], "id": f"wh-{w[0]}", "is_active": True} for w in seed.WAREHOUSES]
    roles = [{"id": "r-admin", "name": "admin", "is_system_role": True},
             {"id": "r-bas", "name": seed.BASCULA_ROLE["name"], "is_system_role": False},
             {"id": "r-rev", "name": seed.REVISOR_ROLE["name"], "is_system_role": False}]
    r = {
        "/materials": _paginado([{"code": m[0], "is_active": True} for m in seed.MATERIALS]),
        "/warehouses": _paginado(bodegas),
        "/money-accounts": _paginado([{"name": a["name"], "current_balance": 0} for a in seed.ACCOUNTS]),
        "/third-parties": _paginado([{"name": t[0], "current_balance": 0} for t in seed.THIRD_PARTIES]),
        "/expense-categories/flat": {"items": [{"name": c[0]} for c in seed.EXPENSE_CATEGORIES]},
        "/business-units": _paginado([{"name": b} for b in seed.BUSINESS_UNITS]
                                     + [{"name": "Pasa Mano", "system_code": "double_entry"}]),
        "/material-categories": _paginado([{"name": c} for c in seed.MATERIAL_CATEGORIES]),
        "/service-tariffs/current": _paginado([{"tariff_code": t["tariff_code"], "unit_price_cop": t["unit_price_cop"]}
                                               for t in seed.TARIFFS]),
        "/material-conversion-formulas/current": _paginado([
            {"material_code": m[0], "formula_type": m[6], "parameters": {"valor": m[7]}}
            for m in seed.MATERIALS if m[6]]),
        "/material-kg-profiles": _paginado([
            {"material_code": m[0], "willard_world": m[4], "compra_regular": m[5], "lead_product": m[8]}
            for m in seed.MATERIALS]),
        "/third-parties/retention-entities": [
            {"config_id": f"c{i}", "entity_id": None, "retention_type": c["retention_type"],
             "municipality": c.get("municipality"), "concept": None, "rate_pct": float(c["rate_pct"]),
             "is_active": True, "current_balance": 0.0, "name": None}
            for i, c in enumerate(seed.RETENTION_CONFIGS)],
        "/lead-market-prices": _paginado([]),
        "/kg-ledger/summary": {"accounts": []},
        "/roles": roles,
        "/roles/r-bas": {"permissions": [{"code": c} for c in seed.BASCULA_ROLE["permission_codes"]]},
        "/roles/r-rev": {"permissions": [{"code": c} for c in seed.REVISOR_ROLE["permission_codes"]]},
        f"/organizations/{VIEJA}": {"settings": seed.settings_de_la_org({b["name"]: b["id"] for b in bodegas})},
    }
    for ruta, _ in A.DOCUMENTOS + A.SIN_SEMBRAR:
        r[ruta] = _paginado([])
    r["/price-list-groups"] = {"items": []}  # el backend real no trae total
    return r


def _usuarios_del_seeder():
    return [_usuario(f"u{i}", u["email"], [(VIEJA, u["role"])]) for i, u in enumerate(seed.USERS)]


class FakeApiRevisar(FakeApi):
    """Ademas de /system, responde las lecturas de la org y anota con que org."""

    def __init__(self, usuarios=None, respuestas=None, fallan=(), remoto=False):
        super().__init__([_org(VIEJA, "SAC"), _org(OTRA, "RECICLAJES NACIONALES S.A.S")],
                         _usuarios_del_seeder() if usuarios is None else usuarios)
        if remoto:
            self.base_url, self.is_local = "https://api.ejemplo.test", False
        self.respuestas = respuestas or _como_el_seeder()
        self.fallan, self.org_id, self.lecturas_con_org = set(fallan), None, []

    def get(self, path, params=None):
        if path.startswith("/system/"):
            return super().get(path, params)
        self.lecturas_con_org.append(self.org_id)
        if path in self.fallan:
            raise SystemExit(f"GET {path} failed [500]")
        r = self.respuestas[path]
        if isinstance(r, dict) and "total" in r and (params or {}).get("skip"):
            return {"items": [], "total": r["total"]}
        return r


def _con(cambio):
    r = _como_el_seeder()
    cambio(r)
    return r


def _primer(r, ruta):
    filas = r[ruta]["items"] if isinstance(r[ruta], dict) else r[ruta]
    return filas[0]


class TestRevisar:
    def test_sin_diferencias_no_avisa_nada(self):
        api = FakeApiRevisar()
        assert A.revisar(api) == []
        # Todas las lecturas de la org con el id de la SAC, nada escrito, y el
        # header de org se limpia al salir.
        assert set(api.lecturas_con_org) == {VIEJA} and api.org_id is None
        assert api.patches == api.posts == api.deletes == []

    @pytest.mark.parametrize("cambio, esperado, cuantos", [
        (lambda r: r["/purchases"].update(total=2), "2 compras", 1),
        (lambda r: r["/drivers"].update(total=1), "1 conductores", 1),
        (lambda r: r["/price-list-groups"].update(items=[{}]), "listas de precios", 1),
        (lambda r: r["/materials"]["items"].append({"code": "XYZ", "is_active": True})
         or r["/materials"].update(total=len(r["/materials"]["items"])),
         "materiales que el seeder no siembra: XYZ", 1),
        (lambda r: r["/third-parties"]["items"].append({"name": "Nuevo", "current_balance": 5})
         or r["/third-parties"].update(total=len(r["/third-parties"]["items"])),
         "terceros con saldo distinto de 0: Nuevo", 2),
        (lambda r: r["/money-accounts"]["items"][0].update(current_balance=10), "cuentas de dinero con saldo", 1),
        (lambda r: _primer(r, "/service-tariffs/current").update(unit_price_cop="1"), "vigente en 1", 1),
        (lambda r: _primer(r, "/material-conversion-formulas/current").update(parameters={"valor": 1.0}),
         "fórmulas vigentes distintas", 1),
        (lambda r: _primer(r, "/material-kg-profiles").update(lead_product="crudo"), "perfiles kg distintos", 1),
        (lambda r: _primer(r, "/third-parties/retention-entities").update(rate_pct=4.0), "Tarifas de retención distintas", 1),
        (lambda r: r["/third-parties/retention-entities"].append(
            {"config_id": None, "entity_id": "e1", "name": "[Retenciones] ICA", "current_balance": -3.0}),
         "entidades de retención con saldo: [Retenciones] ICA", 1),
        (lambda r: r["/lead-market-prices"]["items"].extend([{"annulled_at": None}, {"annulled_at": "2026-11-01"}])
         or r["/lead-market-prices"].update(total=2),
         "1 precio(s) del plomo", 1),
        (lambda r: r["/kg-ledger/summary"]["accounts"].append({"code": "INTERSEDE", "balance_kg": "10.0000"}),
         "cuentas kg con saldo: INTERSEDE", 1),
        (lambda r: r["/roles"].append({"id": "r-x", "name": "contador", "is_system_role": False}),
         "Rol custom «contador»", 1),
        (lambda r: r["/roles/r-bas"]["permissions"].append({"code": "sales.view"}),
         "Rol «bascula_sac»: permisos distintos", 1),
        (lambda r: r[f"/organizations/{VIEJA}"]["settings"].update(transfer_tolerance_pct=0.1),
         "Setting transfer_tolerance_pct = 0.1", 1),
        (lambda r: r[f"/organizations/{VIEJA}"]["settings"].update(willard_sede_drosses="wh-Circunvalar"),
         "willard_sede_drosses = bodega Circunvalar; la nueva nace con bodega Juan Mina", 1),
    ])
    def test_cada_diferencia_se_avisa(self, cambio, esperado, cuantos):
        avisos = A.revisar(FakeApiRevisar(respuestas=_con(cambio)))
        assert any(esperado in a for a in avisos), avisos
        assert len(avisos) == cuantos, avisos

    def test_miembros_fuera_del_seeder_y_superusuarios(self):
        usuarios = _usuarios_del_seeder()[1:] + [  # falta hugo en el servidor
            _usuario("x", "contadora@sac.com", [(VIEJA, "contador")]),
            _usuario("su", "admin@x", [(VIEJA, "admin")], superuser=True),
        ]
        texto = "\n".join(A.revisar(FakeApiRevisar(usuarios=usuarios)))
        assert "Usuario del seeder hugo@sac.com no existe" in texto
        assert "contadora@sac.com (contador) no está en el seeder" in texto
        assert "rol «contador»" in texto
        # B2: el superusuario NO queda exento, la baja tambien lo desactivaria.
        assert "admin@x (superusuario) (admin) no está en el seeder: --copiar-miembros" in texto

    def test_un_listado_que_falla_o_viene_incompleto_se_avisa_y_no_corta(self):
        r = _como_el_seeder()
        r["/service-tariffs/current"] = {"items": [], "total": 5}
        texto = "\n".join(A.revisar(FakeApiRevisar(respuestas=r, fallan={"/transfers", "/roles"})))
        assert "No se pudo leer /transfers" in texto
        assert "No se pudo leer completo /roles" in texto
        assert "se leyeron 0 de 5" in texto


class TestSeederNoCreaUsuariosEnRemoto:
    """Contra un remoto, un usuario del seeder que no exista naceria con
    --users-password, una clave constante (#85). El seeder se detiene ANTES de
    crear la org, para no dejarla a medias."""

    class _Sesion:
        def __init__(self):
            self.posts = []

        def post(self, url, json=None, headers=None):
            self.posts.append(url)
            return _Resp({}, 201)

    def _seeder(self, monkeypatch, url, emails):
        api = seed.APIClient(dry_run=False, base_url=url)
        api.session = self._Sesion()
        escrito = []
        monkeypatch.setattr(api, "get", lambda path, params=None: [{"email": e} for e in emails]
                            if path == "/system/users" else [])
        monkeypatch.setattr(api, "post", lambda path, body, label="": escrito.append(path) or {"id": "org"})
        s = seed.SacSeeder(api, "12345678")
        monkeypatch.setattr(s, "_find_existing_org", lambda: None)
        return s, escrito

    def test_falta_un_usuario_y_se_detiene_sin_crear_la_org(self, monkeypatch):
        todos = [u["email"] for u in seed.USERS]
        s, escrito = self._seeder(monkeypatch, "https://api.ejemplo.test", todos[:-1])
        with pytest.raises(SystemExit, match=todos[-1]):
            s.create_or_reset_org(reset=False)
        assert escrito == [] and s.api.session.posts == []

    def test_con_todos_no_registra_a_nadie(self, monkeypatch):
        s, escrito = self._seeder(monkeypatch, "https://api.ejemplo.test", [u["email"] for u in seed.USERS])
        s.create_or_reset_org(reset=False)
        assert escrito == ["/system/organizations"] and s.api.session.posts == []

    def test_en_local_sigue_registrando(self, monkeypatch):
        s, _ = self._seeder(monkeypatch, "http://localhost:8000", [])
        s._pre_register_user(seed.USERS[0])
        assert s.api.session.posts == [f"http://localhost:8000{seed.API_PREFIX}/auth/register"]


class TestTercerosDePruebaSoloEnLocal:
    """Daniel, 10-nov: la carga de muestra en prod no trae los PRUEBA-*."""

    def test_el_catalogo_comun_no_tiene_terceros_de_prueba(self):
        assert [t[0] for t in seed.THIRD_PARTIES] == ["Willard S.A", "Green Loop"]
        assert all(t[0].startswith("PRUEBA - ") for t in seed.THIRD_PARTIES_LOCAL)

    def test_revisar_remoto_avisa_los_prueba_que_la_nueva_no_tendra(self):
        r = _como_el_seeder()
        r["/third-parties"]["items"].append({"name": "PRUEBA - Cliente Nacional", "current_balance": 0})
        r["/third-parties"]["total"] += 1
        avisos = A.revisar(FakeApiRevisar(respuestas=r, remoto=True))
        assert avisos == ["1 terceros que el seeder no siembra: PRUEBA - Cliente Nacional"], avisos

    def test_revisar_local_no_los_avisa(self):
        r = _como_el_seeder()
        r["/third-parties"]["items"].append({"name": "PRUEBA - Cliente Nacional", "current_balance": 0})
        r["/third-parties"]["total"] += 1
        assert A.revisar(FakeApiRevisar(respuestas=r)) == []


class TestVerificarUsuarios:
    """C1 de QA: el paso 0 de ronda_remota.sh se detiene, ANTES de archivar, si
    el paso 2 se fuera a detener por un usuario faltante."""

    def _seeder(self, monkeypatch, url, emails):
        api = seed.APIClient(dry_run=True, base_url=url)
        leidos = []
        monkeypatch.setattr(api, "get", lambda path, params=None: leidos.append(path)
                            or [{"email": e} for e in emails])
        return seed.SacSeeder(api, "x"), leidos

    def test_remoto_con_uno_faltante_se_detiene_y_lo_nombra(self, monkeypatch):
        todos = [u["email"] for u in seed.USERS]
        s, _ = self._seeder(monkeypatch, "https://api.ejemplo.test", todos[1:])
        with pytest.raises(SystemExit, match=todos[0]):
            s.verificar_usuarios()

    def test_remoto_con_todos_pasa(self, monkeypatch):
        s, leidos = self._seeder(monkeypatch, "https://api.ejemplo.test", [u["email"] for u in seed.USERS])
        s.verificar_usuarios()
        assert leidos == ["/system/users"]

    def test_local_no_verifica_porque_los_crea(self, monkeypatch):
        s, leidos = self._seeder(monkeypatch, "http://localhost:8000", [])
        s.verificar_usuarios()
        assert leidos == []

    def test_main_con_la_bandera_no_corre_el_seeder(self, monkeypatch):
        # Con --apply incluido: la bandera es de solo lectura igual.
        monkeypatch.setattr(sys, "argv", ["seed", "--apply", "--verificar-usuarios",
                                          "--api-url", "https://api.ejemplo.test",
                                          "--superuser-email", "a@b", "--superuser-password", "x"])
        monkeypatch.setattr(seed.APIClient, "login", lambda self, e, p: None)
        monkeypatch.setattr(seed.APIClient, "get", lambda self, path, params=None:
                            [{"email": u["email"]} for u in seed.USERS])
        monkeypatch.setattr(seed.SacSeeder, "run", lambda self, **kw: pytest.fail("corrió el seeder"))
        seed.main()
