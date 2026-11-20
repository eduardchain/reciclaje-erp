"""Aviso de proveedor parecido por contenido (plan-sac-similar-por-contenido
v1.1, §6). Daniel, 20-nov: autorizó y O1 = «solo avisa».

`GET /third-parties/similar` devuelve `match="exact"` (lo de hoy: el mismo
tercero, la pantalla bloquea) o `match="similar"` (se parece por contenido:
la pantalla avisa y deja crear igual). La regla es `utils/name_match.py`, una
copia exacta de la función que se midió sobre los nombres reales (gate C2).

T1 es puro y sin BD. T2–T10 van contra el endpoint y T11 contra el alcance
de recolector de #129 (Ingrid), que filtra los candidatos ANTES de comparar.
"""
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.models.permission import Permission
from app.models.role import Role, RolePermission
from app.models.user import OrganizationMember, User, UserCollectorScope
from app.utils.name_match import name_match_kind
from tests.conftest import create_third_party_with_category

SIMILAR_URL = "/api/v1/third-parties/similar"


# ---------------------------------------------------------------------------
# T1 — la función pura: frontera del umbral (C3), simetría, vacías, ñ/tildes
# ---------------------------------------------------------------------------

T1_CASES = [
    # (descripción, nuevo, existente, esperado)
    ("exact: tildes y mayúsculas", "  CHATARRERIA munoz ", "Chatarrería Muñoz", "exact"),
    ("A: guion y mayúsculas", "GREEN LOOP - MAQUILA", "Green Loop Maquila", "similar"),
    ("A: concatenación", "GreenLoop", "Green Loop", "similar"),
    ("A: sufijo S.A.S", "Aluica S.A.S", "Aluica", "similar"),
    ("A: ñ y tildes", "CHATARRERÍA MUÑOZ - SAS", "Chatarreria Munoz", "similar"),
    ("C: vacías pegadas", "Dela Rosa", "de la Rosa", "similar"),
    ("C: solo vacías, mismo texto", "S.A.S", "SAS", "similar"),
    ("B: solo vacías no contiene", "S.A.S", "S.A.S Aluica", None),
    ("B: nuevo más largo", "Edwin Garcia (Greenloop)", "Edwin (Greenloop)", "similar"),
    ("B: nuevo más corto", "Carlos Andres Paez", "Ventas Carlos Andres Paez", "similar"),
    ("B: ñ y tildes", "Muñoz Peña", "Carlos Munoz Pena", "similar"),
    ("B frontera: 1 palabra de 7 letras NO", "Ferrosa", "Ferrosa Industrial", None),
    ("B frontera: 1 palabra de 8 letras SÍ", "Ferrosas", "Ferrosas Industrial", "similar"),
    ("B frontera: 2 palabras cortas SÍ", "Ana Maria", "Ana Maria Lopez", "similar"),
    ("B: 1 palabra corta NO", "Ana", "Ana Maria Lopez", None),
    ("B: nombre corto «green» NO", "green", "Bio Green Loop- Maquila", None),
    ("control T5: comparten 1 palabra de 2", "Ferretería El Tornillo", "El Tornillo Feliz", None),
    ("control T5: plural no es la misma palabra", "Ferretería El Tornillo", "Tornillos y Tuercas", None),
]


class TestT1Funcion:

    @pytest.mark.parametrize("desc, new, old, want", T1_CASES, ids=[c[0] for c in T1_CASES])
    def test_t1_caso_y_simetria(self, desc, new, old, want):
        assert name_match_kind(new, old) == want, desc
        assert name_match_kind(old, new) == want, f"simetría: {desc}"


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _flag(db_session, test_organization):
    test_organization.settings = {"kg_ledger_enabled": True}
    db_session.commit()


def _sup(db, org_id, name, **kw):
    tp = create_third_party_with_category(db, org_id, name, "material_supplier", **kw)
    db.commit()
    return tp


def _get(client, headers, **params):
    r = client.get(SIMILAR_URL, headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _pairs(data):
    return [(x["name"], x["match"]) for x in data]


class TestEndpoint:

    def test_t2_regla_a_avisa_como_similar(self, client, org_headers, db_session, test_organization):
        _sup(db_session, test_organization.id, "Green Loop Maquila")
        assert _pairs(_get(client, org_headers, name="GREEN LOOP - MAQUILA")) == [
            ("Green Loop Maquila", "similar")]

    def test_t3_nombre_nuevo_mas_largo(self, client, org_headers, db_session, test_organization):
        _sup(db_session, test_organization.id, "Edwin (Greenloop)")
        assert _pairs(_get(client, org_headers, name="Edwin Garcia (Greenloop)")) == [
            ("Edwin (Greenloop)", "similar")]

    def test_t4_nombre_nuevo_mas_corto(self, client, org_headers, db_session, test_organization):
        _sup(db_session, test_organization.id, "Ventas Carlos Andres Paez")
        assert _pairs(_get(client, org_headers, name="Carlos Andres Paez")) == [
            ("Ventas Carlos Andres Paez", "similar")]

    def test_t5_control_lo_que_no_se_parece_no_avisa(
        self, client, org_headers, db_session, test_organization,
    ):
        org = test_organization.id
        _sup(db_session, org, "Tornillos y Tuercas")
        _sup(db_session, org, "El Tornillo Feliz")
        _sup(db_session, org, "Ana María López")
        assert _get(client, org_headers, name="Ferretería El Tornillo") == []
        assert _get(client, org_headers, name="Ana") == []
        # Control positivo del mismo escenario: lo que sí se parece aparece.
        assert _pairs(_get(client, org_headers, name="El Tornillo Feliz SAS")) == [
            ("El Tornillo Feliz", "similar")]

    def test_t6_tope_y_orden(self, client, org_headers, db_session, test_organization):
        org = test_organization.id
        _sup(db_session, org, "Green Loop Maquila")
        for zona in ["Norte", "Sur", "Este", "Oeste", "Centro", "Puerto", "Rural"]:
            _sup(db_session, org, f"Green Loop Maquila {zona}")
        data = _get(client, org_headers, name="GREEN LOOP MAQUILA")
        assert [x["match"] for x in data] == ["exact"] + ["similar"] * 5
        assert data[0]["name"] == "Green Loop Maquila"
        # los 5 parecidos, en orden de nombre normalizado (los primeros 5 de 7)
        assert [x["name"] for x in data[1:]] == [
            "Green Loop Maquila Centro", "Green Loop Maquila Este", "Green Loop Maquila Norte",
            "Green Loop Maquila Oeste", "Green Loop Maquila Puerto"]

    def test_t7_exact_sigue_exact(self, client, org_headers, db_session, test_organization):
        org = test_organization.id
        _sup(db_session, org, "Chatarrería Muñoz", identification_number="900.123.456-7")
        data = _get(client, org_headers, name="  CHATARRERIA munoz ")
        assert _pairs(data) == [("Chatarrería Muñoz", "exact")]
        assert data[0]["is_material_supplier"] is True
        assert _pairs(_get(client, org_headers, identification="9001234567")) == [
            ("Chatarrería Muñoz", "exact")]
        # identificación igual con un nombre que no se parece: exact (D4)
        assert _pairs(_get(client, org_headers, name="Otro Nombre", identification="9001234567")) == [
            ("Chatarrería Muñoz", "exact")]

    def test_t8_inactivos_y_sistema_no_aparecen(
        self, client, org_headers, db_session, test_organization,
    ):
        org = test_organization.id
        _sup(db_session, org, "Green Loop Maquila Inactiva", is_active=False)
        _sup(db_session, org, "Green Loop Maquila Sistema", is_system_entity=True)
        assert _get(client, org_headers, name="Green Loop Maquila") == []
        # Control positivo: uno activo con el mismo parecido sí aparece.
        _sup(db_session, org, "Green Loop Maquila Activa")
        assert _pairs(_get(client, org_headers, name="Green Loop Maquila")) == [
            ("Green Loop Maquila Activa", "similar")]

    def test_t9_otra_org_no_aparece(
        self, client, org_headers, db_session, test_organization, test_organization2,
    ):
        _sup(db_session, test_organization2.id, "Green Loop Maquila Ajena")
        assert _get(client, org_headers, name="Green Loop Maquila") == []
        _sup(db_session, test_organization.id, "Green Loop Maquila Propia")
        assert _pairs(_get(client, org_headers, name="Green Loop Maquila")) == [
            ("Green Loop Maquila Propia", "similar")]

    def test_t10_exact_y_similar_a_la_vez_sale_una_vez(
        self, client, org_headers, db_session, test_organization,
    ):
        # Mismo nombre normalizado (exact) que además cumple A: sale UNA vez.
        _sup(db_session, test_organization.id, "Green Loop Maquila")
        data = _get(client, org_headers, name="green loop maquila")
        assert _pairs(data) == [("Green Loop Maquila", "exact")]


# ---------------------------------------------------------------------------
# T11 — alcance de recolector (#129): el criterio va DESPUÉS de su filtro
# ---------------------------------------------------------------------------

def _scoped_headers(db, org_id, collector_id):
    perm = db.execute(select(Permission).where(Permission.code == "third_parties.view")).scalar_one()
    role = Role(organization_id=org_id, name=f"rc_{uuid4().hex[:6]}", display_name="RC",
                is_system_role=False)
    db.add(role)
    db.flush()
    db.add(RolePermission(role_id=role.id, permission_id=perm.id))
    user = User(email=f"rc_{uuid4().hex[:6]}@example.com", hashed_password=get_password_hash("pass1234"),
                full_name="RC", is_active=True)
    db.add(user)
    db.flush()
    db.add(OrganizationMember(user_id=user.id, organization_id=org_id, role_id=role.id))
    db.add(UserCollectorScope(organization_id=org_id, user_id=user.id, collector_id=collector_id))
    db.commit()
    return {"Authorization": f"Bearer {create_access_token(data={'sub': str(user.id)})}",
            "X-Organization-ID": str(org_id)}


class TestT11Alcance:

    def test_t11_un_parecido_fuera_del_alcance_no_aparece(
        self, client, org_headers, db_session, test_organization,
    ):
        org = test_organization.id
        gl = create_third_party_with_category(db_session, org, "Green Loop", "service_provider")
        db_session.commit()
        _sup(db_session, org, "Chatarrería Muñoz Norte")  # SIN la marca: fuera del alcance
        scoped = _scoped_headers(db_session, org, gl.id)
        assert _get(client, scoped, name="Chatarrería Muñoz") == []
        # Control: sin alcance, el mismo parecido sí aparece.
        assert _pairs(_get(client, org_headers, name="Chatarrería Muñoz")) == [
            ("Chatarrería Muñoz Norte", "similar")]
        # Control positivo CON alcance: marcado con su recolector, aparece.
        _sup(db_session, org, "Chatarrería Muñoz Sur", collector_id=gl.id)
        assert _pairs(_get(client, scoped, name="Chatarrería Muñoz")) == [
            ("Chatarrería Muñoz Sur", "similar")]
