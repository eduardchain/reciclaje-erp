"""Quitar el reseteo y el alta con clave constante (plan-quitar-clave-constante v1.1).

Patron #85: la clave la elige quien la fija, nunca vuelve en la respuesta ni en
logs, y ya no existe una clave por defecto. D5: el admin de una org no resetea a
un miembro que tambien pertenece a OTRA org activa.
"""
import importlib.util
import logging
import re
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.models.organization import Organization
from app.models.role import Role
from app.models.third_party import ThirdParty
from app.models.user import OrganizationMember, User, UserCollectorScope
from app.services.role import role_service
from tests.conftest import _seed_permissions_and_roles

API = "/api/v1"
BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
CONSTANT = re.compile(r"(^|[^0-9])(123456|12345678)([^0-9]|$)")


# ------------------------------------------------------------------ helpers

def _role_id(db: Session, org_id, name: str):
    return db.query(Role).filter(Role.organization_id == org_id, Role.name == name).first().id


def _user(db: Session, email: str, password: str = "clave-vieja-1", superuser: bool = False) -> User:
    u = User(email=email, hashed_password=get_password_hash(password), full_name=email.split("@")[0],
             is_active=True, is_superuser=superuser)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _member(db: Session, user: User, org: Organization, role: str = "viewer") -> None:
    db.add(OrganizationMember(user_id=user.id, organization_id=org.id, role_id=_role_id(db, org.id, role)))
    db.commit()


def _inactive_org(db: Session) -> Organization:
    org = Organization(name="Org Dada de Baja", slug="org-dada-de-baja", max_users=5)
    db.add(org)
    db.flush()
    _seed_permissions_and_roles(db, org.id)
    org.is_active = False
    db.commit()
    db.refresh(org)
    return org


def _login(client, email: str, password: str) -> int:
    return client.post(f"{API}/auth/login/json", json={"email": email, "password": password}).status_code


def _reset(client, headers, org, user_id, body):
    return client.post(f"{API}/organizations/{org.id}/members/{user_id}/reset-password",
                       headers=headers, json=body)


def _headers(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(data={'sub': str(user.id)})}"}


# ---------------------------------------------------- T1–T4: el reseteo (D1, D5, D6)

class TestResetConClaveElegida:
    def test_t1_la_clave_nueva_entra_y_la_constante_no(self, client, auth_headers, test_organization, db_session):
        target = _user(db_session, "t1@example.com")
        _member(db_session, target, test_organization)
        r = _reset(client, auth_headers, test_organization, target.id, {"new_password": "nueva-t1-xyz"})
        assert r.status_code == 200, r.text
        assert r.json() == {"message": "Contraseña actualizada"}
        assert _login(client, "t1@example.com", "nueva-t1-xyz") == 200
        assert _login(client, "t1@example.com", "123456") == 401
        assert _login(client, "t1@example.com", "clave-vieja-1") == 401

    def test_t2_sin_cuerpo_o_corta_da_422(self, client, auth_headers, test_organization, db_session):
        target = _user(db_session, "t2@example.com")
        _member(db_session, target, test_organization)
        url = f"{API}/organizations/{test_organization.id}/members/{target.id}/reset-password"
        assert client.post(url, headers=auth_headers).status_code == 422
        assert _reset(client, auth_headers, test_organization, target.id, {"new_password": "abcde"}).status_code == 422
        # Control: con 6 entra.
        assert _reset(client, auth_headers, test_organization, target.id, {"new_password": "abcdef"}).status_code == 200
        assert _login(client, "t2@example.com", "clave-vieja-1") == 401

    def test_t3_la_clave_no_vuelve_ni_queda_en_el_log(self, client, auth_headers, test_organization, test_user,
                                                       db_session, caplog):
        target = _user(db_session, "t3@example.com")
        _member(db_session, target, test_organization)
        secret = "Secreto-T3-NoDebeVerse"
        with caplog.at_level(logging.WARNING):
            r = _reset(client, auth_headers, test_organization, target.id, {"new_password": secret})
        assert r.status_code == 200
        assert secret not in r.text
        logs = "\n".join(rec.getMessage() for rec in caplog.records)
        assert secret not in logs
        # Control positivo: la auditoria SI se escribio, con actor, objetivo y org (D6).
        audit = [rec.getMessage() for rec in caplog.records if "member_password_reset" in rec.getMessage()]
        assert len(audit) == 1, logs
        assert str(test_user.id) in audit[0] and str(target.id) in audit[0]
        assert str(test_organization.id) in audit[0] and "t3@example.com" in audit[0]

    def test_t4_d5_otra_org_activa_403_inactiva_200(self, client, auth_headers, test_organization,
                                                     test_organization2, db_session):
        solo = _user(db_session, "t4-solo@example.com")
        activa = _user(db_session, "t4-activa@example.com")
        inactiva = _user(db_session, "t4-inactiva@example.com")
        baja = _inactive_org(db_session)
        for u in (solo, activa, inactiva):
            _member(db_session, u, test_organization)
        _member(db_session, activa, test_organization2)
        _member(db_session, inactiva, baja)

        # El listado expone el predicado (y org_count NO cambia: cuenta tambien la inactiva).
        members = {m["user_email"]: m for m in
                   client.get(f"{API}/organizations/{test_organization.id}/members", headers=auth_headers).json()}
        assert [members[e]["in_other_active_org"] for e in
                ("t4-solo@example.com", "t4-activa@example.com", "t4-inactiva@example.com")] == [False, True, False]
        assert members["t4-inactiva@example.com"]["org_count"] == 2

        r = _reset(client, auth_headers, test_organization, activa.id, {"new_password": "nueva-t4-a"})
        assert r.status_code == 403
        assert "también pertenece a otra organización" in r.json()["detail"]
        assert _login(client, "t4-activa@example.com", "clave-vieja-1") == 200  # no cambio

        # Controles: solo de esta org → 200; y en otra org INACTIVA → 200 (discrimina
        # contra get_user_org_count, que la cuenta).
        assert _reset(client, auth_headers, test_organization, solo.id, {"new_password": "nueva-t4-s"}).status_code == 200
        assert _reset(client, auth_headers, test_organization, inactiva.id,
                      {"new_password": "nueva-t4-i"}).status_code == 200
        assert _login(client, "t4-inactiva@example.com", "nueva-t4-i") == 200


# ------------------------------------------------------------ T5: el alta (D2)

class TestAltaConClaveElegida:
    def test_t5_alta_con_clave(self, client, auth_headers, test_organization, db_session):
        url = f"{API}/organizations/{test_organization.id}/members/create-user"
        base = {"email": "t5@example.com", "full_name": "T5", "role_id": str(_role_id(db_session, test_organization.id, "viewer"))}
        assert client.post(url, headers=auth_headers, json=base).status_code == 422
        assert client.post(url, headers=auth_headers, json={**base, "password": "1234abc"}).status_code == 422
        r = client.post(url, headers=auth_headers, json={**base, "password": "alta-t5-ok"})
        assert r.status_code == 201, r.text
        assert "alta-t5-ok" not in r.text
        assert r.json()["org_count"] == 1 and r.json()["in_other_active_org"] is False
        assert _login(client, "t5@example.com", "alta-t5-ok") == 200
        assert _login(client, "t5@example.com", "123456") == 401
        assert _login(client, "t5@example.com", "12345678") == 401


# ------------------------------------------------------- T6–T7: Sistema (D3)

@pytest.fixture
def su_headers(db_session):
    su = _user(db_session, "su-clave@example.com", superuser=True)
    role_service.seed_permissions(db_session)
    db_session.commit()
    return _headers(su)


class TestSistemaAdminNuevo:
    def test_t6_admin_nuevo_exige_su_clave(self, client, su_headers, db_session):
        body = {"name": "Org T6", "admin_email": "t6@example.com", "admin_full_name": "Admin T6"}
        r = client.post(f"{API}/system/organizations", headers=su_headers, json=body)
        assert r.status_code == 400 and "admin_password" in r.json()["detail"]
        assert db_session.query(User).filter(User.email == "t6@example.com").first() is None
        assert client.post(f"{API}/system/organizations", headers=su_headers,
                           json={**body, "admin_password": "corta7"}).status_code == 422
        r = client.post(f"{API}/system/organizations", headers=su_headers, json={**body, "admin_password": "admin-t6-ok"})
        assert r.status_code == 201, r.text
        assert "admin-t6-ok" not in r.text
        assert _login(client, "t6@example.com", "admin-t6-ok") == 200
        assert _login(client, "t6@example.com", "123456") == 401

    def test_t7_admin_existente_conserva_su_clave(self, client, su_headers, db_session):
        _user(db_session, "t7@example.com", password="la-suya-t7")
        r = client.post(f"{API}/system/organizations", headers=su_headers,
                        json={"name": "Org T7", "admin_email": "t7@example.com", "admin_password": "otra-clave-t7"})
        assert r.status_code == 201, r.text
        assert _login(client, "t7@example.com", "la-suya-t7") == 200
        assert _login(client, "t7@example.com", "otra-clave-t7") == 401


# ------------------------------------------------------------ T8: guarda D4

def _scan(root: Path) -> list[str]:
    """`archivo:linea` de toda linea con 123456/12345678 con limites de digito, bajo
    backend/app y frontend/src de `root`. Recorre TODO archivo de texto (no solo
    .py/.ts/.tsx: un .json o .js futuro tambien cuenta) y salta los que no
    decodifican como UTF-8 (binarios). La misma funcion corre sobre el arbol vivo
    y sobre el de 161b204 (control positivo)."""
    hits = []
    for top in ("backend/app", "frontend/src"):
        for p in sorted((root / top).rglob("*")):
            if not p.is_file() or "__pycache__" in p.parts:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if CONSTANT.search(line):
                    hits.append(f"{p.relative_to(root)}:{i}")
    return hits


EXPECTED_161B204 = [
    "backend/app/api/v1/endpoints/organizations.py:351",
    "backend/app/api/v1/endpoints/organizations.py:354",
    "backend/app/api/v1/endpoints/organizations.py:509",
    "backend/app/api/v1/endpoints/system.py:88",
    "backend/app/services/user.py:108",
    "backend/app/services/user.py:112",
    "frontend/src/hooks/useRoles.ts:133",
    "frontend/src/hooks/useRoles.ts:145",
    "frontend/src/pages/admin/UsersPage.tsx:447",
    "frontend/src/pages/admin/UsersPage.tsx:468",
    "frontend/src/pages/system/SystemOrganizationsPage.tsx:317",
]


class TestGuardaSinConstante:
    def test_t8_cero_constantes_en_app_y_front(self):
        assert _scan(REPO) == []

    def test_t8_control_positivo_el_arbol_de_161b204_da_los_11(self, tmp_path):
        """La misma funcion de recorrido sobre `git archive 161b204` encuentra
        EXACTAMENTE los 11 sitios del plan (D4). Uno sintetico no mostraria que
        el recorrido mira donde tiene que mirar."""
        tar = subprocess.run(["git", "-C", str(REPO), "archive", "161b204", "backend/app", "frontend/src"],
                             capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", str(tmp_path)], input=tar, check=True)
        assert _scan(tmp_path) == EXPECTED_161B204


# ---------------------------------------------- T9: los 403 de hoy se conservan

class TestLos403SeConservan:
    def test_t9_no_admin_superusuario_y_alcance(self, client, auth_headers, test_organization, test_user,
                                                 test_user2, auth_headers_user2, db_session):
        target = _user(db_session, "t9@example.com")
        _member(db_session, target, test_organization)
        _member(db_session, test_user2, test_organization)  # viewer
        body = {"new_password": "nueva-t9-x"}

        # No admin → 403; control: el admin → 200.
        assert _reset(client, auth_headers_user2, test_organization, target.id, body).status_code == 403
        assert _reset(client, auth_headers, test_organization, target.id, body).status_code == 200

        # Superusuario como objetivo → 403; control: el mismo admin sobre un miembro normal → 200 (arriba).
        su = _user(db_session, "t9-su@example.com", superuser=True)
        _member(db_session, su, test_organization)
        r = _reset(client, auth_headers, test_organization, su.id, body)
        assert r.status_code == 403 and "superadmin" in r.json()["detail"]

        # Admin con alcance de recolector → 403 de alcance; control: sin la fila → 200.
        tp = ThirdParty(name="Recolector T9", organization_id=test_organization.id)
        db_session.add(tp)
        db_session.flush()
        scope = UserCollectorScope(organization_id=test_organization.id, user_id=test_user.id, collector_id=tp.id)
        db_session.add(scope)
        db_session.commit()
        r = _reset(client, auth_headers, test_organization, target.id, body)
        assert r.status_code == 403 and "Fuera de tu alcance" in r.json()["detail"], r.text
        db_session.delete(scope)
        db_session.commit()
        assert _reset(client, auth_headers, test_organization, target.id, body).status_code == 200


# --------------------------------------- T10: el borrado no cambia (C2 de QA)

class TestBorradoIntacto:
    def test_t10_quitar_a_quien_esta_en_una_org_inactiva_no_lo_borra(self, client, auth_headers,
                                                                     test_organization, db_session):
        en_baja = _user(db_session, "t10-baja@example.com")
        solo = _user(db_session, "t10-solo@example.com")
        baja = _inactive_org(db_session)
        _member(db_session, en_baja, test_organization)
        _member(db_session, en_baja, baja)
        _member(db_session, solo, test_organization)
        en_baja_id, solo_id = en_baja.id, solo.id

        assert client.delete(f"{API}/organizations/{test_organization.id}/members/{en_baja_id}",
                             headers=auth_headers).status_code == 204
        db_session.expire_all()
        kept = db_session.get(User, en_baja_id)
        assert kept is not None and kept.is_active
        assert db_session.query(OrganizationMember).filter_by(user_id=en_baja_id, organization_id=baja.id).count() == 1

        # Control: quitar a un miembro solo de esta org lo borra, como hoy.
        assert client.delete(f"{API}/organizations/{test_organization.id}/members/{solo_id}",
                             headers=auth_headers).status_code == 204
        db_session.expire_all()
        gone = db_session.get(User, solo_id)
        assert gone is None or gone.is_active is False


# ---------------------------------------------- T11: migrate_org.py (D3b, C1)

def _migrate_module():
    spec = importlib.util.spec_from_file_location("migrate_org_t11", BACKEND / "scripts" / "migrate_org.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestMigrateOrg:
    @pytest.mark.parametrize("modo", [["--dry-run"], ["--apply", "--superuser-email", "su@x.com",
                                                     "--superuser-password", "x"]])
    @pytest.mark.parametrize("valor", [None, "7letras"])
    def test_t11_sin_clave_aborta_antes_de_tocar_nada(self, tmp_path, modo, valor):
        import os
        env = {k: v for k, v in os.environ.items() if k != "MIGRATE_ADMIN_PASSWORD"}
        if valor is not None:
            env["MIGRATE_ADMIN_PASSWORD"] = valor
        # Puerto 9: nadie escucha. Si el script llegara al API, el error seria otro.
        r = subprocess.run(
            [sys.executable, str(BACKEND / "scripts" / "migrate_org.py"), "--file", str(tmp_path / "no.xlsx"),
             "--api-url", "http://127.0.0.1:9", "--org-name", "Org T11", "--admin-email", "t11@example.com",
             "--admin-name", "Admin T11", *modo],
            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60,
        )
        out = r.stdout + r.stderr
        assert r.returncode == 1, out
        assert "MIGRATE_ADMIN_PASSWORD" in r.stderr
        assert "MIGRACION" not in r.stdout and "Autenticando" not in out and "Hojas:" not in out
        if valor:
            assert valor not in out

    def test_t11_control_con_clave_el_post_la_lleva(self):
        mod = _migrate_module()
        assert mod.admin_password_from_env({"MIGRATE_ADMIN_PASSWORD": "ocho-ok-1"}) == "ocho-ok-1"

        class FakeApi:
            def __init__(self):
                self.posts = []

            def get(self, path, params=None):
                return 200, []

            def post(self, path, data=None):
                self.posts.append((path, data))
                return 201, {"id": "org-t11"}

        api = FakeApi()
        assert mod.ensure_org_and_admin(api, "Org T11", "t11@example.com", "Admin T11", False, "ocho-ok-1") == "org-t11"
        assert api.posts == [("/api/v1/system/organizations", {
            "name": "Org T11", "admin_email": "t11@example.com",
            "admin_full_name": "Admin T11", "admin_password": "ocho-ok-1"})]
