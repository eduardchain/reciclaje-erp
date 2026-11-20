"""
SAC — orden del formato en papel «Materiales recolectados» (plan
plan-sac-orden-formato-materiales.md v1.1).

El orden vive en `material_kg_profiles.form_order` y se escribe SOLO por
`PUT /material-kg-profiles/form-order` (lista completa, REPLACE). El upsert del
perfil no lo conoce, asi que no lo puede borrar (D2, trampa de #103 D4).

T1–T6 del §5 (T7, el del seeder, corre contra dev a archivo).
"""
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.security import create_access_token, get_password_hash
from app.models.material_kg_profile import MaterialKgProfile
from app.models.permission import Permission
from app.models.role import Role, RolePermission
from app.models.user import OrganizationMember, User
from tests.integration_helpers import create_material, create_material_category

PROFILES_URL = "/api/v1/material-kg-profiles"
ORDER_URL = f"{PROFILES_URL}/form-order"


@pytest.fixture(autouse=True)
def _flag(db_session, test_organization):
    test_organization.settings = {"kg_ledger_enabled": True}
    db_session.commit()


def _mat(db, org_id, code, unit="kg"):
    cat = create_material_category(db, org_id, f"Cat {code}")
    mat = create_material(db, org_id, code, f"Material {code}", cat.id)
    mat.default_unit = unit
    db.commit()
    return mat


def _profile(client, headers, mat):
    r = client.put(
        f"{PROFILES_URL}/{mat.id}", headers=headers,
        json={"compra_regular": True, "willard_world": "none", "lead_product": "none"},
    )
    assert r.status_code == 200, r.text


@pytest.fixture
def mats(db_session, test_organization, client, org_headers):
    """Cinco materiales clasificados: A..E."""
    out = []
    for code in ("FMT-A", "FMT-B", "FMT-C", "FMT-D", "FMT-E"):
        m = _mat(db_session, test_organization.id, code)
        _profile(client, org_headers, m)
        out.append(m)
    return out


def _put(client, headers, ids, expect=200):
    r = client.put(
        ORDER_URL, headers=headers,
        json={"material_ids": [str(i) if i is not None else None for i in ids]},
    )
    assert r.status_code == expect, r.text
    return r.json()


def _orden(client, headers):
    """{codigo: form_order} leido por GET (lo que ve la pantalla)."""
    r = client.get(PROFILES_URL, headers=headers)
    assert r.status_code == 200, r.text
    return {p["material_code"]: p["form_order"] for p in r.json()["items"]}


class TestFormatoEnPapel:

    def test_t1_orden_con_hueco(self, client, org_headers, mats):
        """F1: la ruta estatica responde (si fuera despues de /{material_id},
        FastAPI la tomaria por un UUID y daria 422). El `null` deja el renglon
        vacio y conserva la numeracion del papel."""
        a, b, c, *_ = mats
        _put(client, org_headers, [a.id, None, b.id, c.id])
        assert _orden(client, org_headers) == {
            "FMT-A": 1, "FMT-B": 3, "FMT-C": 4, "FMT-D": None, "FMT-E": None,
        }

    def test_t2_replace(self, client, org_headers, mats):
        a, b, c, d, e = mats
        _put(client, org_headers, [a.id, b.id, c.id])
        _put(client, org_headers, [d.id, e.id])
        assert _orden(client, org_headers) == {
            "FMT-A": None, "FMT-B": None, "FMT-C": None, "FMT-D": 1, "FMT-E": 2,
        }

    def test_t2b_intercambio_de_dos_renglones(self, client, org_headers, mats):
        """F2: lo que hacen las flechas subir/bajar. Asignar fila por fila con
        otra fila todavia en ese numero choca contra el indice unico."""
        a, b, c, d, _ = mats
        _put(client, org_headers, [a.id, b.id, c.id, d.id])
        _put(client, org_headers, [a.id, b.id, d.id, c.id])
        orden = _orden(client, org_headers)
        assert orden["FMT-C"] == 4 and orden["FMT-D"] == 3

    def test_t3_el_upsert_del_perfil_no_borra_el_orden(self, client, org_headers, mats):
        """D2: el PUT del perfil reemplaza el perfil entero, pero no conoce
        `form_order`, asi que no lo puede borrar (#103 D4)."""
        a, b, *_ = mats
        _put(client, org_headers, [a.id, b.id])
        r = client.put(
            f"{PROFILES_URL}/{a.id}", headers=org_headers,
            json={"compra_regular": False, "willard_world": "none", "lead_product": "none"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["form_order"] == 1
        assert _orden(client, org_headers)["FMT-A"] == 1

    @pytest.mark.parametrize("caso", ["repetido", "otra_org", "inactivo", "sin_perfil"])
    def test_t4_validaciones_sin_escribir(
        self, client, org_headers, db_session, test_organization2, mats, caso,
    ):
        a, b, c, *_ = mats
        _put(client, org_headers, [a.id, b.id])
        if caso == "repetido":
            ids = [c.id, c.id]
        elif caso == "otra_org":
            ajeno = _mat(db_session, test_organization2.id, "FMT-AJENO")
            ids = [c.id, ajeno.id]
        elif caso == "inactivo":
            c.is_active = False
            db_session.commit()
            ids = [c.id]
        else:
            sin = _mat(db_session, a.organization_id, "FMT-SIN-PERFIL")
            ids = [sin.id]
        resp = _put(client, org_headers, ids, expect=422)
        assert resp["detail"]
        # nada se escribio: el formato anterior sigue igual
        orden = _orden(client, org_headers)
        assert orden["FMT-A"] == 1 and orden["FMT-B"] == 2 and orden["FMT-C"] is None

    def test_t4b_material_ordenado_que_se_desactiva(
        self, client, org_headers, db_session, mats,
    ):
        """F3: conserva su renglon y el GET lo marca, para que Config lo
        ofrezca para quitar."""
        a, b, *_ = mats
        _put(client, org_headers, [a.id, b.id])
        b.is_active = False
        db_session.commit()
        r = client.get(PROFILES_URL, headers=org_headers)
        fila = next(p for p in r.json()["items"] if p["material_code"] == "FMT-B")
        assert fila["form_order"] == 2
        assert fila["material_is_active"] is False

    def test_t5_permiso_y_flag(self, client, db_session, test_organization, mats):
        """Rol con materials.view y SIN materials.edit: 403 al ordenar. El GET
        en 200 es el control positivo — sin el, el 403 podria venir del flag o
        de la membresia (#111)."""
        user = User(email="formato-t5@example.com", hashed_password=get_password_hash("x1234567"),
                    full_name="Solo ver", is_active=True)
        db_session.add(user)
        db_session.flush()
        role = Role(organization_id=test_organization.id, name="solo_ver_materiales_t5",
                    display_name="Solo ver", is_system_role=False)
        db_session.add(role)
        db_session.flush()
        perm = db_session.execute(
            select(Permission).where(Permission.code == "materials.view")
        ).scalar_one()
        db_session.add(RolePermission(role_id=role.id, permission_id=perm.id))
        db_session.add(OrganizationMember(user_id=user.id, organization_id=test_organization.id,
                                          role_id=role.id))
        db_session.commit()
        headers = {
            "Authorization": f"Bearer {create_access_token(data={'sub': str(user.id)})}",
            "X-Organization-ID": str(test_organization.id),
        }
        assert client.get(PROFILES_URL, headers=headers).status_code == 200
        _put(client, headers, [mats[0].id], expect=403)

    def test_t5_sin_flag(self, client, org_headers, db_session, test_organization, mats):
        test_organization.settings = {"kg_ledger_enabled": False}
        db_session.commit()
        _put(client, org_headers, [mats[0].id], expect=403)

    def test_t6_la_base_impide_dos_materiales_en_un_renglon(
        self, client, org_headers, db_session, mats,
    ):
        """El indice unico parcial, no el servicio, es lo que lo garantiza."""
        a, b, *_ = mats
        _put(client, org_headers, [a.id])
        perfil_b = db_session.execute(
            select(MaterialKgProfile).where(MaterialKgProfile.material_id == b.id)
        ).scalar_one()
        perfil_b.form_order = 1
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()
