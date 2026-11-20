"""Ingrid / Green Loop: usuario con alcance de recolector (plan
docs/planes/plan-sac-recolector-alcance.md v1.4, §12).

Johana (20-nov): Ingrid, de Green Loop, liquida las Entradas de Green Loop y
lleva la caja de Green Loop; ve solo lo suyo. Un tercero «es de Green Loop» por
su marca `third_parties.collector_id` (§3) y un usuario tiene alcance por una
fila de `user_collector_scopes` (§4). El alcance se impone con una lista blanca
de rutas (deny-by-default, §5) y un filtro por ruta.

El mundo (§12): org con flag; recolectores GL y X (service_provider); terceros
A y A2 (marca GL), B (sin marca), C (marca X), D (conductor generic de GL) y E
(generic sin marca); Entradas E_GL, E_none y E_X; cuentas K1 (de Ingrid) y K2.

Usuarios — nunca el admin para medir permisos (bypassa, #29):
  ingrid       rol Recolector (13 permisos), alcance GL, cuenta K1;
  ingrid_libre el MISMO rol sin alcance: control positivo de cada filtro;
  ingrid_todo  rol con TODOS los permisos y alcance GL;
  todo_libre   todos los permisos, sin alcance;
  johana       admin (org_headers).
"""
import io
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_required_org_context
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.inbound_order import InboundOrder, InboundOrderPurchase
from app.models.money_account import MoneyAccount
from app.models.money_movement import MoneyMovement
from app.models.permission import Permission
from app.models.purchase import Purchase
from app.models.role import Role, RolePermission
from app.models.third_party import ThirdParty
from app.models.third_party_category import ThirdPartyCategoryAssignment
from app.models.user import OrganizationMember, User, UserAccountAssignment, UserCollectorScope
from app.services import collector_scope as cs
from app.services.collector_scope import (
    OUT_OF_SCOPE_PAYLOAD, SCOPE_DENIED_PREFIX, SCOPED_ENDPOINTS, endpoint_key,
)
from app.utils.dates import business_today
from tests.conftest import _get_or_create_category, create_third_party_with_category
from tests.integration_helpers import (
    create_business_unit, create_material, create_material_category, create_warehouse,
)

API = "/api/v1"
INBOUND = f"{API}/inbound-orders"
TP = f"{API}/third-parties"
MM = f"{API}/money-movements"
PURCHASES = f"{API}/purchases"
ATTACH = f"{API}/attachments"

ROL_RECOLECTOR = [
    "purchases.view", "purchases.view_prices", "purchases.liquidate",
    "third_parties.view", "third_parties.create",
    "treasury.view_statements", "treasury.view_accounts", "treasury.view_movements",
    "treasury.view_all_movements",  # v1.4, decision de Daniel
    "treasury.create_movements",
    "materials.view", "materials.view_prices", "tariffs.view",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _past(days=2) -> str:
    return (business_today() - timedelta(days=days)).isoformat()


def _today() -> str:
    return business_today().isoformat()


def _ensure_view_all_movements(db) -> None:
    """`treasury.view_all_movements` existe en produccion por la migracion
    `3771a60dccbe` (2026-04-14), pero NO esta en `PERMISSIONS_CATALOG`, y la base
    de test siembra desde el catalogo (desfase preexistente, reportado). Se crea
    con los mismos campos de esa migracion."""
    if db.execute(select(Permission).where(
            Permission.code == "treasury.view_all_movements")).scalar_one_or_none() is None:
        db.add(Permission(
            code="treasury.view_all_movements", display_name="Ver Todos los Movimientos",
            module="treasury", sort_order=83,
            description="Permite ver todos los movimientos, incluidos los de otros usuarios. "
                        "Sin este permiso, solo se ven los movimientos propios."))
        db.flush()


def _role(db, org_id, name, codes) -> Role:
    _ensure_view_all_movements(db)
    role = Role(organization_id=org_id, name=name, display_name=name, is_system_role=False)
    db.add(role)
    db.flush()
    perms = db.execute(select(Permission).where(Permission.code.in_(codes))).scalars().all()
    assert len(perms) == len(set(codes)), (sorted(codes), sorted(p.code for p in perms))
    for p in perms:
        db.add(RolePermission(role_id=role.id, permission_id=p.id))
    db.flush()
    return role


def _member(db, org_id, tag, role_id, scope=None, accounts=()) -> tuple[User, dict]:
    user = User(email=f"{tag}@example.com", hashed_password=get_password_hash("pass1234"),
                full_name=tag, is_active=True)
    db.add(user)
    db.flush()
    db.add(OrganizationMember(user_id=user.id, organization_id=org_id, role_id=role_id))
    for acc in accounts:
        db.add(UserAccountAssignment(user_id=user.id, organization_id=org_id, account_id=acc))
    if scope is not None:
        db.add(UserCollectorScope(organization_id=org_id, user_id=user.id, collector_id=scope))
    db.flush()
    headers = {"Authorization": f"Bearer {create_access_token(data={'sub': str(user.id)})}",
               "X-Organization-ID": str(org_id)}
    return user, headers


def _ok(r, code=200):
    assert r.status_code == code, (r.status_code, r.text)
    return r.json() if r.text else None


def _ids(items) -> set[str]:
    return {i["id"] for i in items}


@dataclass
class World:
    org: object
    johana: dict
    ingrid: dict
    ingrid_libre: dict
    ingrid_todo: dict
    todo_libre: dict
    ingrid_user: User
    role_recolector: Role
    GL: ThirdParty
    X: ThirdParty
    A: ThirdParty
    A2: ThirdParty
    B: ThirdParty
    C: ThirdParty
    D: ThirdParty
    E: ThirdParty
    K1: MoneyAccount
    K2: MoneyAccount
    wh: object
    m1: object
    E_GL: str
    E_none: str
    E_X: str
    compra_A: str = ""
    compra_B: str = ""
    extra: dict = field(default_factory=dict)


def _entrada(client, headers, wh, mat, qty, collector=None) -> str:
    body = {"inbound_type": "purchase", "warehouse_id": str(wh.id), "date": _past(),
            "lines": [{"material_id": str(mat.id), "quantity": str(qty),
                       "scale_weight_kg": str(qty)}]}
    if collector is not None:
        body["collector_id"] = str(collector.id)
    oid = _ok(client.post(INBOUND, headers=headers, json=body), 201)["id"]
    _ok(client.post(f"{INBOUND}/{oid}/review", headers=headers))
    return oid


def _alloc(tp, slot, qty, price="1000"):
    return {"third_party_id": str(tp.id), "purchase_slot": slot,
            "quantity": str(qty), "unit_price": str(price)}


def _liq_body(mat, *allocs, **extra):
    return {"lines": [{"material_id": str(mat.id), "allocations": list(allocs)}], **extra}


@pytest.fixture
def w(db_session, client, org_headers, test_organization) -> World:
    db = db_session
    org = test_organization
    org.settings = {"kg_ledger_enabled": True}
    db.commit()

    sp = lambda name: create_third_party_with_category(db, org.id, name, "service_provider")  # noqa: E731
    GL = sp("Green Loop")
    X = sp("Otro Recolector")
    sup = lambda name, **kw: create_third_party_with_category(db, org.id, name, "material_supplier", **kw)  # noqa: E731
    A = sup("ABRAHAM (GREENLOOP)", collector_id=GL.id)
    A2 = sup("ADALBERTO (GREENLOOP)", collector_id=GL.id)
    B = sup("Proveedor B de SAC")
    C = sup("Proveedor C de X", collector_id=X.id)
    gen = lambda name, **kw: create_third_party_with_category(db, org.id, name, "generic", **kw)  # noqa: E731
    D = gen("Conductor D (GREENLOOP)", collector_id=GL.id)
    E = gen("Conductor E de SAC")

    K1 = MoneyAccount(name="Caja Green Loop", account_type="cash",
                      current_balance=Decimal("50000000"), organization_id=org.id, is_active=True)
    K2 = MoneyAccount(name="Banco SAC", account_type="bank",
                      current_balance=Decimal("90000000"), organization_id=org.id, is_active=True)
    db.add_all([K1, K2])
    wh = create_warehouse(db, org.id, "Circunvalar AL")
    cat = create_material_category(db, org.id, "Cat AL")
    # Con unidad de negocio: MaterialResponse la exige (las 580 de dev la tienen).
    bu = create_business_unit(db, org.id, "UN AL")
    m1 = create_material(db, org.id, "HIERRO-AL", "Hierro AL", cat.id, bu_id=bu.id)
    m1.default_unit = "kg"
    db.commit()
    _ok(client.put(f"{API}/material-kg-profiles/{m1.id}", headers=org_headers,
                   json={"compra_regular": True, "willard_world": "none", "lead_product": "none"}))
    _ok(client.post(f"{API}/service-tariffs", headers=org_headers, json={
        "tariff_code": "comision_green_loop", "unit_price_cop": "100",
        "unit": "per_kg_material", "kg_per_unit": "14"}), 201)
    _ok(client.post(f"{API}/service-tariffs", headers=org_headers, json={
        "tariff_code": "maquila_intersede_cv_jm", "unit_price_cop": "1500",
        "unit": "per_kg_lead"}), 201)

    E_GL = _entrada(client, org_headers, wh, m1, 100, collector=GL)
    E_none = _entrada(client, org_headers, wh, m1, 50)
    E_X = _entrada(client, org_headers, wh, m1, 30, collector=X)

    rol = _role(db, org.id, "recolector_t", ROL_RECOLECTOR)
    all_codes = [p.code for p in db.execute(select(Permission)).scalars().all()]
    rol_todo = _role(db, org.id, "todo_t", all_codes)
    ingrid_user, ingrid = _member(db, org.id, "ingrid", rol.id, scope=GL.id, accounts=[K1.id])
    _, ingrid_libre = _member(db, org.id, "ingrid_libre", rol.id)
    _, ingrid_todo = _member(db, org.id, "ingrid_todo", rol_todo.id, scope=GL.id, accounts=[K1.id])
    _, todo_libre = _member(db, org.id, "todo_libre", rol_todo.id)
    db.commit()

    world = World(org=org, johana=org_headers, ingrid=ingrid, ingrid_libre=ingrid_libre,
                  ingrid_todo=ingrid_todo, todo_libre=todo_libre, ingrid_user=ingrid_user,
                  role_recolector=rol, GL=GL, X=X, A=A, A2=A2, B=B, C=C, D=D, E=E,
                  K1=K1, K2=K2, wh=wh, m1=m1, E_GL=E_GL, E_none=E_none, E_X=E_X)
    # Johana liquida E_none con A y B: la compra de A nace en una Entrada SIN
    # recolector (S8, D-b = a) y la de B es la ajena.
    _ok(client.post(f"{INBOUND}/{E_none}/liquidate", headers=org_headers,
                    json=_liq_body(m1, _alloc(A, 1, 20), _alloc(B, 2, 30))))
    db.expire_all()
    compras = {p.supplier_id: str(p.id) for p in db.execute(
        select(Purchase).where(Purchase.organization_id == org.id)).scalars()}
    world.compra_A = compras[A.id]
    world.compra_B = compras[B.id]
    return world


def _pago(client, headers, kind, account, tp, amount="1000"):
    """Pago desde una cuenta: supplier-payment, advance-payment o payment-to-generic."""
    key = "third_party_id" if kind == "payment-to-generic" else "supplier_id"
    return client.post(f"{MM}/{kind}", headers=headers, json={
        key: str(tp.id), "account_id": str(account.id), "amount": amount,
        "date": _past(1), "description": f"{kind} prueba"})


def _ajuste(client, headers, tp, amount="5000"):
    return _ok(client.post(f"{MM}/tp-adjustment-debit", headers=headers, json={
        "third_party_id": str(tp.id), "amount": amount, "adjustment_class": "loss",
        "date": _past(1), "description": f"ajuste {tp.name}"}), 201)


def _fondeo(client, headers, w, amount="2000000"):
    """Johana fondea la caja de Ingrid: transferencia K2 -> K1."""
    return _ok(client.post(f"{MM}/transfer", headers=headers, json={
        "amount": amount, "source_account_id": str(w.K2.id),
        "destination_account_id": str(w.K1.id), "date": _past(1),
        "description": "fondeo caja Green Loop"}), 201)



def _detail(r) -> str:
    try:
        return str(r.json().get("detail", ""))
    except Exception:
        return ""


def _scope_denied(r) -> bool:
    return r.status_code == 403 and _detail(r).startswith(SCOPE_DENIED_PREFIX)


# ===========================================================================
# Lista blanca: T2, T2b, T1, T1b, T1c
# ===========================================================================

# T2b, doble entrada: ampliar la lista obliga a venir a declararla aca, donde
# se lee, con el par (metodo, path) de cada funcion (T2, M3).
LISTA_BLANCA = {
    "attachments.download_attachment": {("GET", "/attachments/{attachment_id}/download")},
    "attachments.list_attachments": {("GET", "/attachments")},
    "inbound_orders.get_inbound_order": {("GET", "/inbound-orders/{order_id}")},
    "inbound_orders.liquidate_inbound_order": {("POST", "/inbound-orders/{order_id}/liquidate")},
    "inbound_orders.list_inbound_orders": {("GET", "/inbound-orders")},
    "material_kg_profiles.list_material_kg_profiles": {("GET", "/material-kg-profiles")},
    "materials.get_material": {("GET", "/materials/{material_id}")},
    "materials.list_materials": {("GET", "/materials")},
    "money_accounts.get_money_account": {("GET", "/money-accounts/{account_id}")},
    "money_accounts.list_money_accounts": {("GET", "/money-accounts")},
    "money_movements.annul_movement": {("POST", "/money-movements/{movement_id}/annul")},
    "money_movements.create_advance_payment": {("POST", "/money-movements/advance-payment")},
    "money_movements.create_payment_to_generic": {("POST", "/money-movements/payment-to-generic")},
    "money_movements.create_supplier_payment": {("POST", "/money-movements/supplier-payment")},
    "money_movements.download_evidence": {("GET", "/money-movements/{movement_id}/evidence")},
    "money_movements.get_by_account": {("GET", "/money-movements/account/{account_id}")},
    "money_movements.get_by_third_party": {("GET", "/money-movements/third-party/{third_party_id}")},
    "money_movements.get_movement": {("GET", "/money-movements/{movement_id}")},
    "money_movements.list_money_movements": {("GET", "/money-movements")},
    "money_movements.upload_evidence": {("POST", "/money-movements/{movement_id}/evidence")},
    "price_lists.get_all_current_prices": {("GET", "/price-lists/current")},
    "purchases.get_purchase": {("GET", "/purchases/{purchase_id}")},
    "purchases.list_purchases": {("GET", "/purchases")},
    "roles.get_my_permissions": {("GET", "/roles/my-permissions")},
    "service_tariffs.get_current_tariffs": {("GET", "/service-tariffs/current")},
    "third_parties.create_third_party": {("POST", "/third-parties")},
    "third_party_categories.get_flat_categories": {("GET", "/third-party-categories/flat")},
    "third_parties.find_similar_third_parties": {("GET", "/third-parties/similar")},
    "third_parties.get_third_party": {("GET", "/third-parties/{third_party_id}")},
    "third_parties.list_payable_providers": {("GET", "/third-parties/payable-providers")},
    "third_parties.list_suppliers": {("GET", "/third-parties/suppliers")},
    "third_parties.list_third_parties": {("GET", "/third-parties")},
}

# T1b (§5.0): las rutas montadas que NO pasan por `get_required_org_context`.
# 27 del plan + `PUT .../collector-scope`, que nace en este ciclo con su guard.
SIN_CONTEXTO = {
    ("GET", "/health"), ("GET", "/api/v1/health"),
    ("POST", "/api/v1/auth/register"), ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/login/json"), ("POST", "/api/v1/auth/change-password"),
    ("GET", "/api/v1/auth/me"),
    ("GET", "/api/v1/system/organizations"), ("POST", "/api/v1/system/organizations"),
    ("PATCH", "/api/v1/system/organizations/{org_id}"),
    ("DELETE", "/api/v1/system/organizations/{org_id}"),
    ("GET", "/api/v1/system/organizations/{org_id}/roles"), ("GET", "/api/v1/system/users"),
    ("POST", "/api/v1/system/users/{user_id}/add-to-org"),
    ("POST", "/api/v1/system/users/{user_id}/reset-password"),
    ("GET", "/api/v1/organizations"), ("POST", "/api/v1/organizations"),
    ("GET", "/api/v1/organizations/{organization_id}"),
    ("PATCH", "/api/v1/organizations/{organization_id}"),
    ("GET", "/api/v1/organizations/{organization_id}/members"),
    ("POST", "/api/v1/organizations/{organization_id}/members"),
    ("POST", "/api/v1/organizations/{organization_id}/members/create-user"),
    ("PATCH", "/api/v1/organizations/{organization_id}/members/{user_id}"),
    ("DELETE", "/api/v1/organizations/{organization_id}/members/{user_id}"),
    ("POST", "/api/v1/organizations/{organization_id}/members/{user_id}/reset-password"),
    ("POST", "/api/v1/organizations/{organization_id}/leave"),
    ("PUT", "/api/v1/organizations/{organization_id}/members/{user_id}/account-assignments"),
    ("PUT", "/api/v1/organizations/{organization_id}/members/{user_id}/collector-scope"),
}


def _uses_org_context(dependant) -> bool:
    stack = [dependant]
    while stack:
        d = stack.pop()
        if d.call is get_required_org_context:
            return True
        stack.extend(d.dependencies)
    return False


def _pares():
    """[(metodo, ruta)] de todas las rutas montadas."""
    return [(m, r) for r in app.routes if isinstance(r, APIRoute) for m in sorted(r.methods)]


def _fill(route) -> str:
    path = route.path
    for p in route.dependant.path_params:
        val = "1" if p.field_info.annotation is int else str(uuid4())
        path = path.replace("{" + p.name + "}", val)
    return path


def _short(key: str) -> str:
    return key.replace("app.api.v1.endpoints.", "")


class TestListaBlanca:

    def test_t2b_la_lista_es_exactamente_la_declarada(self, db_session):
        assert {_short(k) for k in SCOPED_ENDPOINTS} == set(LISTA_BLANCA)
        assert len(SCOPED_ENDPOINTS) == 32  # v1.5: + fila 15b (flat de categorias)

    def test_t2_cada_entrada_resuelve_a_sus_rutas_montadas(self, db_session):
        montadas: dict[str, set] = {}
        for m, r in _pares():
            k = endpoint_key(r.endpoint)
            if k in SCOPED_ENDPOINTS:
                montadas.setdefault(_short(k), set()).add((m, r.path.replace(API, "", 1)))
        assert montadas == LISTA_BLANCA

    def test_t1b_rutas_sin_contexto_de_org(self, db_session):
        sin = {(m, r.path) for m, r in _pares() if not _uses_org_context(r.dependant)}
        assert sin == SIN_CONTEXTO

    def test_t1_familia_deny_by_default(self, w):
        pares = _pares()
        con = [(m, r) for m, r in pares if _uses_org_context(r.dependant)]
        # Conteo con dos mediciones independientes (leccion de #108): todas las
        # rutas menos el set literal de T1b == las que tienen contexto.
        assert len(con) == len(pares) - len(SIN_CONTEXTO)
        casos = [(m, r) for m, r in con if endpoint_key(r.endpoint) not in SCOPED_ENDPOINTS]
        assert len(casos) == len(con) - sum(len(v) for v in LISTA_BLANCA.values())
        assert len(casos) >= 200, len(casos)  # 243 al escribirlo

        cli = TestClient(app, raise_server_exceptions=False)
        fallas, control = [], []
        for m, r in casos:
            url = _fill(r)
            resp = cli.request(m, url, headers=w.ingrid_todo)
            if not _scope_denied(resp):
                fallas.append((m, r.path, resp.status_code, _detail(resp)[:80]))
            # Control positivo: sin alcance, el 403 de alcance no aparece.
            resp2 = cli.request(m, url, headers=w.todo_libre)
            if _detail(resp2).startswith(SCOPE_DENIED_PREFIX):
                control.append((m, r.path))
        assert fallas == []
        assert control == []

    def test_t1_casos_explicitos_s4_y_por_numero(self, w, client):
        """§5.4/§5.5 con ids REALES: cambiar el recolector de una Entrada,
        poner o quitar la marca y buscar por numero -> 403 de ruta."""
        reales = [
            ("PATCH", f"{INBOUND}/{w.E_GL}", {"collector_id": str(w.X.id)}),
            ("POST", INBOUND, {}),
            ("PATCH", f"{TP}/{w.A.id}", {"collector_id": None}),
            ("PATCH", f"{TP}/{w.B.id}", {"collector_id": str(w.GL.id)}),
            ("GET", f"{PURCHASES}/by-number/1", None),
            ("GET", f"{MM}/by-number/1", None),
            ("GET", f"{MM}/summary", None),
        ]
        for m, url, body in reales:
            r = client.request(m, url, headers=w.ingrid, json=body)
            assert _scope_denied(r), (m, url, r.status_code, r.text)
        w_db = w  # la marca de B y la Entrada siguen como estaban
        r = client.get(f"{TP}/{w_db.B.id}", headers=w.johana)
        assert r.json()["collector_id"] is None
        r = client.get(f"{INBOUND}/{w.E_GL}", headers=w.johana)
        assert r.json()["collector_id"] == str(w.GL.id)

    def test_t1c_rutas_de_miembros(self, w, client):
        org = w.org.id
        uid = uuid4()
        rutas = [
            ("PATCH", f"{API}/organizations/{org}", {"name": "SAC renombrada"}),
            ("GET", f"{API}/organizations/{org}/members", None),
            ("POST", f"{API}/organizations/{org}/members/create-user",
             {"email": "nuevo@example.com", "full_name": "Nuevo", "role_id": str(w.role_recolector.id)}),
            ("POST", f"{API}/organizations/{org}/members",
             {"user_id": str(uid), "role_id": str(w.role_recolector.id)}),
            ("PATCH", f"{API}/organizations/{org}/members/{uid}", {"role_id": str(w.role_recolector.id)}),
            ("POST", f"{API}/organizations/{org}/members/{uid}/reset-password", None),
            ("DELETE", f"{API}/organizations/{org}/members/{uid}", None),
            ("POST", f"{API}/organizations/{org}/leave", None),
            ("PUT", f"{API}/organizations/{org}/members/{uid}/account-assignments", {"account_ids": []}),
            ("PUT", f"{API}/organizations/{org}/members/{uid}/collector-scope", {"collector_id": None}),
        ]
        for m, url, body in rutas:
            r = client.request(m, url, headers=w.ingrid, json=body)
            assert _scope_denied(r), (m, url, r.status_code, r.text)
        r = client.get(f"{API}/organizations/{org}", headers=w.ingrid)
        assert r.status_code == 200 and "settings" in r.json()
        # Control positivo: el mismo rol sin alcance ve los miembros (hoy).
        assert client.get(f"{API}/organizations/{org}/members", headers=w.ingrid_libre).status_code == 200
        # Y la org sigue con su nombre y con Ingrid adentro.
        assert client.get(f"{API}/organizations/{org}", headers=w.johana).json()["name"] == w.org.name


# ===========================================================================
# Filas 7-9: Entradas
# ===========================================================================

class TestEntradas:

    def test_fila7_listado_forzado_y_contadores(self, w, client):
        r = _ok(client.get(INBOUND, headers=w.ingrid, params={"collector_id": str(w.X.id)}))
        assert _ids(r["items"]) == {w.E_GL} and r["total"] == 1
        r = _ok(client.get(INBOUND, headers=w.ingrid_libre))
        assert _ids(r["items"]) == {w.E_GL, w.E_none, w.E_X} and r["total"] == 3

    def test_fila7_busqueda_dentro_del_filtro(self, w, client):
        """§5.4 (P19): la busqueda corre DENTRO del filtro del recolector."""
        q = {"search": "HIERRO-AL"}
        assert _ok(client.get(INBOUND, headers=w.ingrid, params=q))["total"] == 1
        assert _ok(client.get(INBOUND, headers=w.ingrid_libre, params=q))["total"] == 3

    def test_fila8_detalle(self, w, client):
        assert client.get(f"{INBOUND}/{w.E_GL}", headers=w.ingrid).status_code == 200
        for oid in (w.E_none, w.E_X):
            assert client.get(f"{INBOUND}/{oid}", headers=w.ingrid).status_code == 404
            assert client.get(f"{INBOUND}/{oid}", headers=w.ingrid_libre).status_code == 200


def _conteos(db) -> dict:
    """Las tablas que toca una liquidacion (D14 de #93: un rechazo no deja nada)."""
    from app.models.document_tax import DocumentTax
    from app.models.inbound_order import InboundOrderPurchase
    from app.models.inventory_movement import InventoryMovement
    from app.models.material_cost_history import MaterialCostHistory
    from app.models.purchase_retention import PurchaseRetention
    from sqlalchemy import func
    db.expire_all()
    return {m.__tablename__: db.scalar(select(func.count()).select_from(m)) for m in (
        Purchase, InboundOrderPurchase, InventoryMovement, MaterialCostHistory,
        MoneyMovement, DocumentTax, PurchaseRetention)}


class TestLiquidar:

    def _liq(self, client, headers, oid, body):
        return client.post(f"{INBOUND}/{oid}/liquidate", headers=headers, json=body)

    def test_fila9_feliz_comision_la_fija_el_servidor(self, w, client, db_session):
        r = self._liq(client, w.ingrid, w.E_GL, _liq_body(w.m1, _alloc(w.A, 1, 100)))
        assert r.status_code == 200, r.text
        db_session.expire_all()
        mm = db_session.execute(select(MoneyMovement).where(
            MoneyMovement.source_type == "collector_commission",
            MoneyMovement.source_id == UUID(w.E_GL))).scalars().all()
        # tarifa 100 x 100 kg pesados, aunque el payload no mando comision
        assert [(m.third_party_id, m.amount, m.status) for m in mm] == [
            (w.GL.id, Decimal("10000.00"), "confirmed")]

    def test_fila9_comision_con_el_monto_calculado_pasa(self, w, client):
        body = _liq_body(w.m1, _alloc(w.A, 1, 100),
                         collector_commission={"third_party_id": str(w.GL.id), "amount": "10000"})
        assert self._liq(client, w.ingrid, w.E_GL, body).status_code == 200

    def test_fila9_rechazos_no_escriben_nada(self, w, client, db_session):
        antes = _conteos(db_session)
        # El MENSAJE, no solo el codigo: un 422 de validacion del schema pasaria
        # igual por el status y el caso no probaria la regla (anti-vacuidad).
        ajeno = OUT_OF_SCOPE_PAYLOAD
        comision = "la calcula el sistema"
        s5 = "sin retenciones ni IVA"
        casos = [
            (_liq_body(w.m1, _alloc(w.B, 1, 100)), 422, ajeno),
            (_liq_body(w.m1, _alloc(w.C, 1, 100)), 422, ajeno),
            (_liq_body(w.m1, _alloc(w.A, 1, 50), _alloc(w.B, 2, 50)), 422, ajeno),
            (_liq_body(w.m1, _alloc(w.A, 1, 100), supplier_payments=[
                {"purchase_slot": 1, "third_party_id": str(w.A.id), "account_id": str(w.K2.id)}]),
             403, "No tienes acceso a esta cuenta"),
            (_liq_body(w.m1, _alloc(w.A, 1, 100),
                       collector_commission={"third_party_id": str(w.X.id), "amount": "10000"}), 422, comision),
            (_liq_body(w.m1, _alloc(w.A, 1, 100),
                       collector_commission={"third_party_id": str(w.GL.id), "amount": "9999"}), 422, comision),
            (_liq_body(w.m1, _alloc(w.A, 1, 100), supplier_retentions=[
                {"purchase_slot": 1, "third_party_id": str(w.A.id),
                 "retentions": [{"retention_type": "retefuente", "amount": "100"}]}]), 422, s5),
            (_liq_body(w.m1, _alloc(w.A, 1, 100), purchase_taxes=[
                {"purchase_slot": 1, "third_party_id": str(w.A.id),
                 "taxes": [{"tax_type": "iva", "amount": "100"}]}]), 422, s5),
        ]
        for body, code, msg in casos:
            r = self._liq(client, w.ingrid, w.E_GL, body)
            assert r.status_code == code, (body, r.status_code, r.text)
            assert msg in _detail(r), (body, r.text)
            # M1: el 422 no nombra lo ajeno
            assert w.B.name not in r.text and w.C.name not in r.text and w.X.name not in r.text
        r = self._liq(client, w.ingrid, w.E_none, _liq_body(w.m1, _alloc(w.A, 1, 50)))
        assert r.status_code == 404
        assert _conteos(db_session) == antes
        assert client.get(f"{INBOUND}/{w.E_GL}", headers=w.johana).json()["status"] == "reviewed"

    def test_fila9_control_sin_alcance_respeta_lo_digitado(self, w, client, db_session):
        body = _liq_body(w.m1, _alloc(w.B, 1, 30),
                         collector_commission={"third_party_id": str(w.X.id), "amount": "777"})
        assert self._liq(client, w.ingrid_libre, w.E_X, body).status_code == 200
        db_session.expire_all()
        mm = db_session.execute(select(MoneyMovement).where(
            MoneyMovement.source_type == "collector_commission",
            MoneyMovement.source_id == UUID(w.E_X))).scalar_one()
        assert mm.amount == Decimal("777.00")


# ===========================================================================
# T25 — Entradas PREEXISTENTES (R1 medido en prod por el Coordinador, 20-nov:
# 25 de 148 Entradas de SAC ya tienen recolector Green Loop, 18 revisadas y 7
# liquidadas). Ingrid las encuentra el dia del deploy sin que nadie las haya
# creado con el codigo nuevo. Aca nacen IGUAL que alla: por la API de siempre,
# con el usuario SIN alcance (Johana), y la liquidada con un proveedor que la
# regla del nombre no marco (B) y con la comision editada a mano (#79 F1).
# ===========================================================================

class TestEntradasPreexistentes:

    def _liquidada_por_johana(self, w, client) -> str:
        e = _entrada(client, w.johana, w.wh, w.m1, 80, collector=w.GL)
        _ok(client.post(f"{INBOUND}/{e}/liquidate", headers=w.johana, json=_liq_body(
            w.m1, _alloc(w.A, 1, 40), _alloc(w.B, 2, 40),
            collector_commission={"third_party_id": str(w.GL.id), "amount": "777"})))
        return e

    def test_t25_las_ve_en_sus_dos_estados(self, w, client):
        e_liq = self._liquidada_por_johana(w, client)
        items = {i["id"]: i for i in _ok(client.get(INBOUND, headers=w.ingrid))["items"]}
        # La revisada (E_GL, creada y revisada por Johana) y la liquidada: las dos
        assert items[w.E_GL]["status"] == "reviewed"
        assert items[e_liq]["status"] == "liquidated"
        assert set(items) == {w.E_GL, e_liq}
        # Detalle de las dos: 200 (fila 8 mira order.collector_id, que ya existia)
        for oid in (w.E_GL, e_liq):
            assert client.get(f"{INBOUND}/{oid}", headers=w.ingrid).status_code == 200

    def test_t25_compra_de_un_proveedor_sin_marca(self, w, client, db_session):
        e_liq = self._liquidada_por_johana(w, client)
        db_session.expire_all()
        compras = {p.supplier_id: str(p.id) for p in db_session.execute(
            select(Purchase).join(InboundOrderPurchase, InboundOrderPurchase.purchase_id == Purchase.id)
            .where(InboundOrderPurchase.inbound_order_id == UUID(e_liq))).scalars()}
        assert set(compras) == {w.A.id, w.B.id}
        # La de A (marcado) la ve; la de B, que la regla del nombre no marco, no:
        # ni en el listado (fila 16) ni por id (fila 17, 404). Control: Johana si.
        listado = {p["id"] for p in _ok(client.get(PURCHASES, headers=w.ingrid))["items"]}
        assert compras[w.A.id] in listado and compras[w.B.id] not in listado
        assert client.get(f"{PURCHASES}/{compras[w.A.id]}", headers=w.ingrid).status_code == 200
        assert client.get(f"{PURCHASES}/{compras[w.B.id]}", headers=w.ingrid).status_code == 404
        assert client.get(f"{PURCHASES}/{compras[w.B.id]}", headers=w.johana).status_code == 200

    def test_t25_la_comision_de_antes_no_se_recalcula(self, w, client, db_session):
        e_liq = self._liquidada_por_johana(w, client)
        # Ingrid no puede re-liquidar una liquidada (la fila 9 no le abre ese
        # camino: el servicio la rechaza por estado) y nada recalcula la comision
        # que Johana edito: sigue en 777, no en tarifa x pesado (8.000).
        r = client.post(f"{INBOUND}/{e_liq}/liquidate", headers=w.ingrid,
                        json=_liq_body(w.m1, _alloc(w.A, 1, 80)))
        assert r.status_code in (400, 409, 422), r.text
        db_session.expire_all()
        mm = db_session.execute(select(MoneyMovement).where(
            MoneyMovement.source_type == "collector_commission",
            MoneyMovement.source_id == UUID(e_liq))).scalars().all()
        assert [(m.amount, m.status) for m in mm] == [(Decimal("777.00"), "confirmed")]

    # ---- Des-liquidadas por SAC: reglas 9e y 9f (v1.6/v1.7) ---------------

    def _liq_j(self, client, w, e, body):
        return _ok(client.post(f"{INBOUND}/{e}/liquidate", headers=w.johana, json=body))

    def _desliq(self, client, w, e):
        _ok(client.post(f"{INBOUND}/{e}/unliquidate", headers=w.johana))

    def _liq_i(self, client, w, e, body):
        return client.post(f"{INBOUND}/{e}/liquidate", headers=w.ingrid, json=body)

    @staticmethod
    def _extra(w, kind):
        if kind == "retencion":
            return {"supplier_retentions": [{
                "purchase_slot": 1, "third_party_id": str(w.A.id),
                "retentions": [{"retention_type": "retefuente", "amount": "2000"}]}]}
        return {"purchase_taxes": [{
            "purchase_slot": 1, "third_party_id": str(w.A.id),
            "taxes": [{"tax_type": "iva", "rate": "19", "amount": "15200"}]}]}

    @staticmethod
    def _filas_del_lote(db, e, kind):
        from app.models.document_tax import DocumentTax
        from app.models.purchase_retention import PurchaseRetention
        db.expire_all()
        ids = [pid for (pid,) in db.execute(select(InboundOrderPurchase.purchase_id).where(
            InboundOrderPurchase.inbound_order_id == UUID(e))).all()]
        model = PurchaseRetention if kind == "retencion" else DocumentTax
        return db.execute(select(model).where(model.purchase_id.in_(ids))).scalars().all()

    @pytest.mark.parametrize("kind", ["retencion", "iva"])
    def test_t25b_9f_el_ultimo_lote_con_retencion_o_iva(self, w, client, db_session, kind):
        e = _entrada(client, w.johana, w.wh, w.m1, 80, collector=w.GL)
        base = _liq_body(w.m1, _alloc(w.A, 1, 80))
        self._liq_j(client, w, e, {**base, **self._extra(w, kind)})
        self._desliq(client, w, e)
        antes = _conteos(db_session)
        # Todo el reparto es de A: solo la 9f la puede rechazar
        r = self._liq_i(client, w, e, base)
        assert r.status_code == 422, r.text
        assert cs.RELIQUIDATE_TAXES in _detail(r), r.text
        assert _conteos(db_session) == antes
        # Segundo control: SAC la vuelve a liquidar con su lote
        assert client.post(f"{INBOUND}/{e}/liquidate", headers=w.johana,
                           json={**base, **self._extra(w, kind)}).status_code == 200

    def test_t25b_control_desliquidada_limpia_es_de_ingrid(self, w, client):
        # Sin este control, una regla que bloqueara TODA des-liquidada pasaria
        e = _entrada(client, w.johana, w.wh, w.m1, 80, collector=w.GL)
        base = _liq_body(w.m1, _alloc(w.A, 1, 80))
        self._liq_j(client, w, e, base)
        self._desliq(client, w, e)
        r = self._liq_i(client, w, e, base)
        assert r.status_code == 200, r.text

    @pytest.mark.parametrize("kind", ["retencion", "iva"])
    def test_t25b_c1_una_liquidacion_posterior_sin_lote_la_libera(self, w, client, db_session, kind):
        # c1 de QA 2: L1 con retencion (o IVA) -> des-liquidar -> L2 sin nada
        # -> des-liquidar. El lote que cuenta es el de L2, que esta vacio.
        e = _entrada(client, w.johana, w.wh, w.m1, 80, collector=w.GL)
        base = _liq_body(w.m1, _alloc(w.A, 1, 80))
        self._liq_j(client, w, e, {**base, **self._extra(w, kind)})
        self._desliq(client, w, e)
        self._liq_j(client, w, e, base)
        self._desliq(client, w, e)
        # Contra la vacuidad: el lote de L1 sigue en la base, revertido
        filas = self._filas_del_lote(db_session, e, kind)
        assert filas and all(f.reverted_at is not None for f in filas)
        r = self._liq_i(client, w, e, base)
        assert r.status_code == 200, r.text

    def test_t25c_9e_compra_viva_ajena(self, w, client, db_session):
        e = _entrada(client, w.johana, w.wh, w.m1, 80, collector=w.GL)
        self._liq_j(client, w, e, _liq_body(w.m1, _alloc(w.A, 1, 40), _alloc(w.B, 2, 40)))
        self._desliq(client, w, e)
        # La compra 2 pasa a A: el reparto es todo suyo, solo la 9e la rechaza
        swap = _liq_body(w.m1, _alloc(w.A, 1, 40), _alloc(w.A, 2, 40))

        def estado_de_b():
            db_session.expire_all()
            return db_session.execute(
                select(Purchase.status)
                .join(InboundOrderPurchase, InboundOrderPurchase.purchase_id == Purchase.id)
                .where(InboundOrderPurchase.inbound_order_id == UUID(e),
                       Purchase.supplier_id == w.B.id)).scalar_one()

        antes = _conteos(db_session)
        r = self._liq_i(client, w, e, swap)
        assert r.status_code == 422, r.text
        assert cs.RELIQUIDATE_FOREIGN_SUPPLIER in _detail(r), r.text
        assert w.B.name not in r.text  # M1
        assert _conteos(db_session) == antes
        assert estado_de_b() == "registered"
        # Control 1: el mismo cuerpo, por Johana, SI cancela la compra de B (R6)
        self._liq_j(client, w, e, swap)
        assert estado_de_b() == "cancelled"
        # Control 2 (P48): con B ya cancelada, la Entrada vuelve a ser de Ingrid
        self._desliq(client, w, e)
        r = self._liq_i(client, w, e, swap)
        assert r.status_code == 200, r.text

    # ---- Precarga: la misma funcion que la 9f (v1.7) ----------------------

    @staticmethod
    def _compra_viva(detalle):
        [p] = [p for p in detalle["purchases"] if p["status"] != "cancelled"]
        return p

    def test_t25d_precarga_lote_de_la_ultima_liquidacion(self, w, client):
        e = _entrada(client, w.johana, w.wh, w.m1, 80, collector=w.GL)
        base = _liq_body(w.m1, _alloc(w.A, 1, 80))
        self._liq_j(client, w, e, {**base, **self._extra(w, "retencion"),
                                   **self._extra(w, "iva")})
        self._desliq(client, w, e)
        # Contra la vacuidad: tras L1 la precarga SI trae su lote
        p = self._compra_viva(_ok(client.get(f"{INBOUND}/{e}", headers=w.johana)))
        assert len(p["retentions"]) == 1 and len(p["taxes"]) == 1
        self._liq_j(client, w, e, base)
        self._desliq(client, w, e)
        p = self._compra_viva(_ok(client.get(f"{INBOUND}/{e}", headers=w.johana)))
        assert p["retentions"] == [] and p["taxes"] == []

    def test_t25d_precarga_trae_las_dos_retenciones_del_lote(self, w, client):
        e = _entrada(client, w.johana, w.wh, w.m1, 80, collector=w.GL)
        body = {**_liq_body(w.m1, _alloc(w.A, 1, 80)), "supplier_retentions": [{
            "purchase_slot": 1, "third_party_id": str(w.A.id),
            "retentions": [{"retention_type": "retefuente", "amount": "2000"},
                           {"retention_type": "ica", "municipality": "Barranquilla",
                            "amount": "500"}]}]}
        self._liq_j(client, w, e, body)
        self._desliq(client, w, e)
        p = self._compra_viva(_ok(client.get(f"{INBOUND}/{e}", headers=w.johana)))
        assert sorted(r["retention_type"] for r in p["retentions"]) == ["ica", "retefuente"]


    # ---- D-E2(b): el aviso al liquidar (v1.8/v1.9) ------------------------

    @staticmethod
    def _avisos(r) -> list[str]:
        """Lo que trae la RESPUESTA HTTP (leccion de #100 D4d), no el servicio."""
        return [x for x in r.json()["warnings"] if "Terceros → Recolector" in x]

    def test_t25e_aviso_por_proveedor_sin_la_marca(self, w, client):
        # Caso 1 (n9): B en DOS compras de la misma Entrada -> UN aviso
        r = client.post(f"{INBOUND}/{w.E_GL}/liquidate", headers=w.johana, json=_liq_body(
            w.m1, _alloc(w.A, 1, 40), _alloc(w.B, 2, 30), _alloc(w.B, 3, 30)))
        assert r.status_code == 200, r.text
        [aviso] = self._avisos(r)
        assert w.B.name in aviso and w.GL.name in aviso and "ingrid" in aviso
        assert w.A.name not in aviso
        # Contra la vacuidad: lo que dice es cierto, Ingrid no abre la compra de B
        compras_b = [p["purchase_id"] for p in r.json()["purchases"] if p["supplier_id"] == str(w.B.id)]
        assert len(compras_b) == 2
        assert client.get(f"{PURCHASES}/{compras_b[0]}", headers=w.ingrid).status_code == 404

    def test_t25e_control_toda_con_la_marca_sin_aviso(self, w, client):
        e = _entrada(client, w.johana, w.wh, w.m1, 80, collector=w.GL)
        r = client.post(f"{INBOUND}/{e}/liquidate", headers=w.johana,
                        json=_liq_body(w.m1, _alloc(w.A, 1, 40), _alloc(w.A2, 2, 40)))
        assert r.status_code == 200, r.text
        assert self._avisos(r) == []

    def test_t25e_c3_proveedor_con_la_marca_de_otro_recolector(self, w, client):
        # c3 de QA 2: C tiene la marca de X; un aviso que solo mirara
        # `collector_id IS NULL` no lo veria
        e = _entrada(client, w.johana, w.wh, w.m1, 80, collector=w.GL)
        r = client.post(f"{INBOUND}/{e}/liquidate", headers=w.johana,
                        json=_liq_body(w.m1, _alloc(w.A, 1, 40), _alloc(w.C, 2, 40)))
        assert r.status_code == 200, r.text
        [aviso] = self._avisos(r)
        assert w.C.name in aviso and w.GL.name in aviso

    def test_t25e_recolector_sin_usuario_con_alcance_sin_aviso(self, w, client):
        # X no tiene ningun usuario con alcance: nadie pierde nada
        r = client.post(f"{INBOUND}/{w.E_X}/liquidate", headers=w.johana,
                        json=_liq_body(w.m1, _alloc(w.B, 1, 30)))
        assert r.status_code == 200, r.text
        assert self._avisos(r) == []


# ===========================================================================
# Filas 10-15: terceros
# ===========================================================================

def _lista(r) -> list:
    data = _ok(r)
    return data["items"] if isinstance(data, dict) else data


class TestTerceros:

    @pytest.mark.parametrize("ruta, esperado", [
        ("", {"A", "A2", "D"}),
        ("/suppliers", {"A", "A2"}),
        ("/payable-providers", {"GL"}),
        ("/similar", {"A"}),
    ])
    def test_filas_10_a_13_listados(self, w, client, ruta, esperado):
        params = {"name": "ABRAHAM (GREENLOOP)"} if ruta == "/similar" else {}
        if ruta == "":
            params["collector_id"] = str(w.X.id)  # se ignora con alcance
        got = {i["id"] for i in _lista(client.get(f"{TP}{ruta}", headers=w.ingrid, params=params))}
        assert got == {str(getattr(w, n).id) for n in esperado}
        # Control: el mismo rol sin alcance ve a los ajenos.
        ajenos = {"": {w.B, w.C}, "/suppliers": {w.B, w.C}, "/payable-providers": {w.X},
                  "/similar": {w.B}}[ruta]
        params_libre = {"name": "Proveedor B de SAC"} if ruta == "/similar" else {}
        got_libre = {i["id"] for i in _lista(
            client.get(f"{TP}{ruta}", headers=w.ingrid_libre, params=params_libre))}
        assert {str(t.id) for t in ajenos} <= got_libre
        if ruta == "/similar":
            assert _lista(client.get(f"{TP}/similar", headers=w.ingrid,
                                     params={"name": "Proveedor B de SAC"})) == []

    def test_fila14_detalle(self, w, client):
        assert client.get(f"{TP}/{w.A.id}", headers=w.ingrid).status_code == 200
        assert client.get(f"{TP}/{w.B.id}", headers=w.ingrid).status_code == 404
        assert client.get(f"{TP}/{w.B.id}", headers=w.ingrid_libre).status_code == 200

    def test_fila15_crear_nace_con_su_recolector(self, w, client, db_session):
        cat = _get_or_create_category(db_session, w.org.id, "material_supplier")
        db_session.commit()
        r = client.post(TP, headers=w.ingrid, json={
            "name": "Nuevo GL", "category_ids": [str(cat.id)], "collector_id": str(w.X.id)})
        assert r.status_code == 201, r.text
        assert r.json()["collector_id"] == str(w.GL.id)
        # v1.5: el conductor nace en «Empleados», la unica generic permitida.
        emp = _cat(db_session, w.org.id, "Empleados", "generic")
        r = client.post(TP, headers=w.ingrid, json={"name": "Conductor nuevo", "category_ids": [str(emp.id)]})
        assert r.status_code == 201 and r.json()["collector_id"] == str(w.GL.id)

    def test_fila15_rechazos_no_escriben(self, w, client, db_session):
        from sqlalchemy import func
        cats = {b: _get_or_create_category(db_session, w.org.id, b)
                for b in ("material_supplier", "investor", "customer", "liability", "generic")}
        db_session.commit()
        antes = db_session.scalar(select(func.count()).select_from(ThirdParty))
        casos = [
            {"name": "Con saldo", "initial_balance": "1000", "category_ids": [str(cats["material_supplier"].id)]},
            {"name": "Socio", "category_ids": [str(cats["investor"].id)]},
            {"name": "Cliente", "category_ids": [str(cats["customer"].id)]},
            {"name": "Pasivo", "category_ids": [str(cats["liability"].id)]},
            # v1.5: una generic que no es «Empleados» («Genérico») tampoco.
            {"name": "Generico", "category_ids": [str(cats["generic"].id)]},
            {"name": "Sin categoria", "category_ids": []},
        ]
        for body in casos:
            r = client.post(TP, headers=w.ingrid, json=body)
            assert r.status_code == 422, (body, r.text)
        db_session.expire_all()
        assert db_session.scalar(select(func.count()).select_from(ThirdParty)) == antes
        # Control: sin alcance, nace sin marca, con su saldo y cualquier categoria.
        r = client.post(TP, headers=w.ingrid_libre, json={
            "name": "Socio libre", "initial_balance": "500", "category_ids": [str(cats["investor"].id)]})
        assert r.status_code == 201, r.text
        assert r.json()["collector_id"] is None and r.json()["initial_balance"] == 500


# ===========================================================================
# Fila 15b (v1.5): categorias para crear un tercero — T23 y T24
# ===========================================================================

FLAT = f"{API}/third-party-categories/flat"


def _cat(db, org_id, name, behavior):
    """Categoria con nombre propio (el helper del conftest reusa la primera de
    su behavior_type, y aca hacen falta dos generic distintas)."""
    from app.models.third_party_category import ThirdPartyCategory
    c = ThirdPartyCategory(name=name, behavior_type=behavior, organization_id=org_id)
    db.add(c)
    db.commit()
    return c


def _flat_ids(client, headers, **params):
    return {i["id"] for i in _ok(client.get(FLAT, headers=headers, params=params))["items"]}


class TestCategorias:

    def test_t23_el_flat_ofrece_lo_que_el_alta_acepta(self, w, client, db_session):
        from app.models.third_party_category import ThirdPartyCategory
        sup = _get_or_create_category(db_session, w.org.id, "material_supplier")
        gen = _get_or_create_category(db_session, w.org.id, "generic")  # «Genérico»
        for b in ("customer", "investor", "liability", "service_provider"):
            _get_or_create_category(db_session, w.org.id, b)
        db_session.commit()
        emp = _cat(db_session, w.org.id, "Empleados", "generic")
        proveedores = {str(c.id) for c in db_session.scalars(select(ThirdPartyCategory).where(
            ThirdPartyCategory.organization_id == w.org.id,
            ThirdPartyCategory.is_active.is_(True),
            ThirdPartyCategory.behavior_type == "material_supplier"))}
        assert str(sup.id) in proveedores

        ofrecidas = _flat_ids(client, w.ingrid)
        assert ofrecidas == proveedores | {str(emp.id)}
        # De punta a punta, la MISMA funcion: todo id que ofrece el flat sirve
        # para crear, y uno que no ofrece da 422.
        for n, cid in enumerate(sorted(ofrecidas)):
            r = client.post(TP, headers=w.ingrid, json={"name": f"Nuevo {n}", "category_ids": [cid]})
            assert r.status_code == 201, (cid, r.text)
        assert str(gen.id) not in ofrecidas
        r = client.post(TP, headers=w.ingrid, json={"name": "Genérico GL", "category_ids": [str(gen.id)]})
        assert r.status_code == 422, r.text
        # El behavior_type del query es interseccion.
        assert _flat_ids(client, w.ingrid, behavior_type="customer") == set()
        assert _flat_ids(client, w.ingrid_libre, behavior_type="customer") != set()
        # Control: sin alcance ve todo.
        libre = _ok(client.get(FLAT, headers=w.ingrid_libre))["items"]
        assert len({i["behavior_type"] for i in libre}) >= 3
        assert str(gen.id) in {i["id"] for i in libre}
        # Las demas rutas de categorias siguen cerradas (T1).
        r = client.get(f"{API}/third-party-categories/{sup.id}", headers=w.ingrid)
        assert r.status_code == 403 and r.json()["detail"].startswith(SCOPE_DENIED_PREFIX)

    def test_t24_conductor_por_nombre_falla_cerrado(self, w, client, db_session):
        _get_or_create_category(db_session, w.org.id, "generic")  # «Genérico», nunca ofrecida
        db_session.commit()
        emp = _cat(db_session, w.org.id, "Empleados", "generic")

        def generic():
            return _flat_ids(client, w.ingrid, behavior_type="generic")

        assert generic() == {str(emp.id)}  # contra la vacuidad: antes de renombrar, aparece
        for nombre in ("EMPLEADOS", "Empleados ", "Émpleados"):
            emp.name = nombre
            db_session.commit()
            assert generic() == {str(emp.id)}, nombre  # normalize_entity_name
        emp.name = "Empleados SAC"
        db_session.commit()
        assert generic() == set()  # ninguna otra generic toma su lugar
        r = client.post(TP, headers=w.ingrid, json={"name": "Conductor X", "category_ids": [str(emp.id)]})
        assert r.status_code == 422, r.text
        emp.name = "Empleados"
        emp.is_active = False
        db_session.commit()
        assert generic() == set()
        emp.is_active = True
        db_session.commit()
        assert generic() == {str(emp.id)}  # control: reactivada vuelve


# ===========================================================================
# Filas 16-19: compras y adjuntos
# ===========================================================================

class TestCompras:

    def test_filas_16_17(self, w, client):
        data = _ok(client.get(PURCHASES, headers=w.ingrid))
        assert _ids(data["items"]) == {w.compra_A} and data["total"] == 1
        # §5.4: la suma del listado sale DESPUES del filtro
        assert data["total_amount_sum"] == pytest.approx(sum(i["total_amount"] for i in data["items"]))
        assert client.get(f"{PURCHASES}/{w.compra_A}", headers=w.ingrid).status_code == 200
        assert client.get(f"{PURCHASES}/{w.compra_B}", headers=w.ingrid).status_code == 404
        libre = _ok(client.get(PURCHASES, headers=w.ingrid_libre))
        assert {w.compra_A, w.compra_B} <= _ids(libre["items"])
        assert client.get(f"{PURCHASES}/{w.compra_B}", headers=w.ingrid_libre).status_code == 200

    def test_filas_18_19_adjuntos(self, w, client):
        ids = {}
        for k, pid in (("A", w.compra_A), ("B", w.compra_B)):
            r = client.post(ATTACH, headers=w.johana, data={"purchase_id": pid},
                            files={"file": ("foto.jpg", io.BytesIO(b"x"), "image/jpeg")})
            assert r.status_code == 201, r.text
            ids[k] = r.json()["id"]
        r = _ok(client.get(ATTACH, headers=w.ingrid, params={"purchase_id": w.compra_A}))
        assert [i["id"] for i in r["items"]] == [ids["A"]]
        assert client.get(f"{ATTACH}/{ids['A']}/download", headers=w.ingrid).status_code == 200
        assert client.get(ATTACH, headers=w.ingrid, params={"purchase_id": w.compra_B}).status_code == 404
        assert client.get(f"{ATTACH}/{ids['B']}/download", headers=w.ingrid).status_code == 404
        assert client.get(ATTACH, headers=w.ingrid, params={"sale_id": str(uuid4())}).status_code == 404
        # Control
        assert client.get(ATTACH, headers=w.ingrid_libre, params={"purchase_id": w.compra_B}).status_code == 200
        assert client.get(f"{ATTACH}/{ids['B']}/download", headers=w.ingrid_libre).status_code == 200


# ===========================================================================
# Filas 20-30: tesoreria
# ===========================================================================

def _mm(db, **where) -> MoneyMovement:
    db.expire_all()
    q = select(MoneyMovement)
    for k, v in where.items():
        q = q.where(getattr(MoneyMovement, k) == v)
    return db.execute(q).scalar_one()


def _evidencia(client, headers, mid):
    return client.post(f"{MM}/{mid}/evidence", headers=headers,
                       files={"file": ("comprobante.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 50),
                                       "image/png")})


class TestTesoreria:

    def test_fila20_estado_de_cuenta_historia_completa(self, w, client, db_session):
        # Johana le paga a A desde K2: es parte de la historia de A (D-E1).
        pago = _ok(_pago(client, w.johana, "supplier-payment", w.K2, w.A), 201)
        data = _ok(client.get(f"{MM}/third-party/{w.A.id}", headers=w.ingrid))
        assert pago["id"] in {i.get("source_id") for i in data["items"]}
        db_session.expire_all()
        vivo = Decimal(str(db_session.get(ThirdParty, w.A.id).current_balance))
        assert vivo != 0  # contra la vacuidad
        assert Decimal(str(data["items"][-1]["balance_after"])) == vivo
        assert Decimal(str(data["current_balance"])) == vivo
        assert client.get(f"{MM}/third-party/{w.B.id}", headers=w.ingrid).status_code == 404
        assert client.get(f"{MM}/third-party/{w.B.id}", headers=w.ingrid_libre).status_code == 200

    def test_filas_21_a_23_caja(self, w, client, db_session):
        cuentas = _lista(client.get(f"{API}/money-accounts", headers=w.ingrid))
        assert _ids(cuentas) == {str(w.K1.id)}
        assert client.get(f"{API}/money-accounts/{w.K2.id}", headers=w.ingrid).status_code == 403
        assert client.get(f"{MM}/account/{w.K2.id}", headers=w.ingrid).status_code == 403
        assert client.get(f"{MM}/account/{w.K1.id}", headers=w.ingrid).status_code == 200
        # Con alcance y SIN asignaciones: ninguna (fail-closed).
        _, sin_cuentas = _member(db_session, w.org.id, "ingrid_sin_cuentas",
                                 w.role_recolector.id, scope=w.GL.id)
        db_session.commit()
        assert _lista(client.get(f"{API}/money-accounts", headers=sin_cuentas)) == []
        assert client.get(f"{MM}/account/{w.K1.id}", headers=sin_cuentas).status_code == 403
        # Control: sin alcance y sin asignaciones ve las dos (comportamiento de hoy).
        libre = _ids(_lista(client.get(f"{API}/money-accounts", headers=w.ingrid_libre)))
        assert {str(w.K1.id), str(w.K2.id)} <= libre

    def test_filas_24_25_y_t22_listado_con_view_all(self, w, client, db_session):
        """T22 (v1.4): con `view_all_movements` el filtro de alcance es la unica
        barrera del listado. El fondeo de Johana aparece; el ajuste ajeno no."""
        _fondeo(client, w.johana, w)
        aj_A = _ajuste(client, w.johana, w.A)
        aj_B = _ajuste(client, w.johana, w.B)
        pago_K1_B = _ok(_pago(client, w.johana, "supplier-payment", w.K1, w.B), 201)
        in_K1 = _mm(db_session, account_id=w.K1.id, movement_type="transfer_in")
        out_K2 = _mm(db_session, account_id=w.K2.id, movement_type="transfer_out")

        data = _ok(client.get(MM, headers=w.ingrid, params={"limit": 500}))
        vistos = _ids(data["items"])
        assert vistos, "lista vacia: el test no mediria nada"
        assert str(in_K1.id) in vistos           # el fondeo, lo creo Johana
        assert aj_A["id"] in vistos              # cuenta NULL, tercero marcado
        assert pago_K1_B["id"] in vistos         # su caja muestra todo (§5.6)
        assert aj_B["id"] not in vistos          # cuenta NULL, tercero ajeno
        assert str(out_K2.id) not in vistos      # cuenta no asignada
        assert data["total"] == len(data["items"])
        assert data["total_amount_sum"] == pytest.approx(sum(float(i["amount"]) for i in data["items"]))
        # Control: el mismo rol sin alcance ve el ajuste de B.
        libre = _ids(_ok(client.get(MM, headers=w.ingrid_libre, params={"limit": 500}))["items"])
        assert aj_B["id"] in libre and str(out_K2.id) in libre

        # Fila 25: el detalle con el mismo predicado.
        assert client.get(f"{MM}/{aj_A['id']}", headers=w.ingrid).status_code == 200
        assert client.get(f"{MM}/{in_K1.id}", headers=w.ingrid).status_code == 200
        assert client.get(f"{MM}/{aj_B['id']}", headers=w.ingrid).status_code == 404
        assert client.get(f"{MM}/{out_K2.id}", headers=w.ingrid).status_code == 404
        assert client.get(f"{MM}/{aj_B['id']}", headers=w.ingrid_libre).status_code == 200

    @pytest.mark.parametrize("kind", ["supplier-payment", "advance-payment"])
    def test_filas_26_27_pagar_y_anticipar(self, w, client, kind):
        assert _pago(client, w.ingrid, kind, w.K1, w.A).status_code == 201
        assert _pago(client, w.ingrid, kind, w.K2, w.A).status_code == 403
        assert _pago(client, w.ingrid, kind, w.K1, w.B).status_code == 404
        # El guard de tipo de tercero de siempre sigue: D es generic.
        r = _pago(client, w.ingrid, kind, w.K1, w.D)
        assert r.status_code == 400, r.text
        assert _pago(client, w.ingrid_libre, kind, w.K2, w.B).status_code == 201

    def test_fila27b_pago_a_generic(self, w, client):
        assert _pago(client, w.ingrid, "payment-to-generic", w.K1, w.D).status_code == 201
        assert _pago(client, w.ingrid, "payment-to-generic", w.K2, w.D).status_code == 403
        assert _pago(client, w.ingrid, "payment-to-generic", w.K1, w.E).status_code == 404
        assert _pago(client, w.ingrid_libre, "payment-to-generic", w.K2, w.E).status_code == 201

    def test_fila28_anular(self, w, client, db_session):
        propio = _ok(_pago(client, w.ingrid, "supplier-payment", w.K1, w.A), 201)
        _fondeo(client, w.johana, w)
        in_K1 = _mm(db_session, account_id=w.K1.id, movement_type="transfer_in")
        de_johana_B = _ok(_pago(client, w.johana, "supplier-payment", w.K1, w.B), 201)
        aj_A = _ajuste(client, w.johana, w.A)
        en_K2 = _ok(_pago(client, w.johana, "supplier-payment", w.K2, w.A), 201)
        anular = lambda h, mid: client.post(f"{MM}/{mid}/annul", headers=h, json={"reason": "prueba"})  # noqa: E731

        for mid in (in_K1.id, de_johana_B["id"], aj_A["id"], en_K2["id"]):
            r = anular(w.ingrid, mid)
            assert r.status_code == 404, (mid, r.text)
        db_session.expire_all()
        par = db_session.get(MoneyMovement, in_K1.transfer_pair_id)
        assert in_K1.status == "confirmed" and par.status == "confirmed"
        assert anular(w.ingrid, propio["id"]).status_code == 200
        # Control: sin alcance anula lo que hoy anula.
        assert anular(w.ingrid_libre, de_johana_B["id"]).status_code == 200

    def test_filas_29_30_evidencia(self, w, client, db_session):
        propio = _ok(_pago(client, w.ingrid, "supplier-payment", w.K1, w.A), 201)
        assert _evidencia(client, w.ingrid, propio["id"]).status_code == 200
        assert client.get(f"{MM}/{propio['id']}/evidence", headers=w.ingrid).status_code == 200

        de_johana_B = _ok(_pago(client, w.johana, "supplier-payment", w.K1, w.B), 201)
        antes = _ok(_evidencia(client, w.johana, de_johana_B["id"]))["evidence_url"]
        assert _evidencia(client, w.ingrid, de_johana_B["id"]).status_code == 404
        db_session.expire_all()
        assert db_session.get(MoneyMovement, UUID(de_johana_B["id"])).evidence_url == antes

        en_K2 = _ok(_pago(client, w.johana, "supplier-payment", w.K2, w.A), 201)
        _ok(_evidencia(client, w.johana, en_K2["id"]))
        assert client.get(f"{MM}/{en_K2['id']}/evidence", headers=w.ingrid).status_code == 404
        assert client.get(f"{MM}/{en_K2['id']}/evidence", headers=w.ingrid_libre).status_code == 200


# ===========================================================================
# T19 (§5.7): lista blanca de CAMPOS
# ===========================================================================

class TestCampos:

    def test_t19_materiales_sin_stock_ni_costo(self, w, client):
        campos = ("current_stock", "current_stock_liquidated", "current_stock_transit",
                  "current_average_cost")
        items = _lista(client.get(f"{API}/materials", headers=w.ingrid))
        assert items and all(i[c] is None for i in items for c in campos)
        detalle = _ok(client.get(f"{API}/materials/{w.m1.id}", headers=w.ingrid))
        assert all(detalle[c] is None for c in campos)
        # Control del detalle: sin alcance, el mismo material trae sus numeros.
        det_libre = _ok(client.get(f"{API}/materials/{w.m1.id}", headers=w.ingrid_libre))
        assert det_libre["current_stock"] not in (None, 0)
        libre = _lista(client.get(f"{API}/materials", headers=w.ingrid_libre))
        assert any(i["current_stock"] not in (None, 0) and i["current_average_cost"] not in (None, 0)
                   for i in libre)

    def test_t19_precios(self, w, client):
        _ok(client.post(f"{API}/price-lists", headers=w.johana, json={
            "material_id": str(w.m1.id), "purchase_price": "900", "sale_price": "1500"}), 201)
        r = client.get(f"{API}/price-lists/current", headers=w.ingrid)
        assert r.status_code == 422
        assert client.get(f"{API}/price-lists/current", headers=w.ingrid,
                          params={"third_party_id": str(w.B.id)}).status_code == 404
        items = _ok(client.get(f"{API}/price-lists/current", headers=w.ingrid,
                               params={"third_party_id": str(w.A.id)}))["items"]
        assert items and all(i["sale_price"] is None for i in items)
        libre = _ok(client.get(f"{API}/price-lists/current", headers=w.ingrid_libre))["items"]
        assert any(i["sale_price"] not in (None, 0) for i in libre)

    def test_t19_tarifas(self, w, client):
        items = _ok(client.get(f"{API}/service-tariffs/current", headers=w.ingrid))["items"]
        assert {i["tariff_code"] for i in items} == {"comision_green_loop"}
        libre = _ok(client.get(f"{API}/service-tariffs/current", headers=w.ingrid_libre))["items"]
        assert len({i["tariff_code"] for i in libre}) >= 2


# ===========================================================================
# T14: el alcance no da permisos
# ===========================================================================

class TestPermisos:

    def _sin(self, w, db, tag, quitar):
        rol = _role(db, w.org.id, f"rol_{tag}", [c for c in ROL_RECOLECTOR if c not in quitar])
        _, h = _member(db, w.org.id, tag, rol.id, scope=w.GL.id, accounts=[w.K1.id])
        db.commit()
        return h

    def test_t14_sin_liquidate(self, w, client, db_session):
        h = self._sin(w, db_session, "sin_liq", {"purchases.liquidate"})
        assert client.get(f"{INBOUND}/{w.E_GL}", headers=h).status_code == 200
        r = client.post(f"{INBOUND}/{w.E_GL}/liquidate", headers=h,
                        json=_liq_body(w.m1, _alloc(w.A, 1, 100)))
        assert r.status_code == 403 and _detail(r).startswith("Permisos insuficientes"), r.text

    def test_t14_sin_view_statements(self, w, client, db_session):
        h = self._sin(w, db_session, "sin_stmt", {"treasury.view_statements"})
        assert client.get(TP, headers=h).status_code == 200
        r = client.get(f"{MM}/third-party/{w.A.id}", headers=h)
        assert r.status_code == 403 and _detail(r).startswith("Permisos insuficientes")

    def test_t14_sin_create_movements(self, w, client, db_session):
        """Barrido de `treasury.create_movements` sobre la lista blanca: las 5
        escrituras de tesoreria dan 403 de permiso, no de alcance."""
        h = self._sin(w, db_session, "sin_create", {"treasury.create_movements"})
        propio = _ok(_pago(client, w.ingrid, "supplier-payment", w.K1, w.A), 201)
        escrituras = [
            _pago(client, h, "supplier-payment", w.K1, w.A),
            _pago(client, h, "advance-payment", w.K1, w.A),
            _pago(client, h, "payment-to-generic", w.K1, w.D),
            client.post(f"{MM}/{propio['id']}/annul", headers=h, json={"reason": "x"}),
            _evidencia(client, h, propio["id"]),
        ]
        for r in escrituras:
            assert r.status_code == 403 and _detail(r).startswith("Permisos insuficientes"), r.text
        assert client.get(f"{MM}/{propio['id']}", headers=h).status_code == 200  # control


# ===========================================================================
# T15: la marca
# ===========================================================================

class TestMarca:

    def _marcar(self, client, w, tp, collector):
        return client.patch(f"{TP}/{tp.id}", headers=w.johana,
                            json={"collector_id": str(collector.id) if collector else None})

    def test_t15_valida_y_quitar(self, w, client):
        r = self._marcar(client, w, w.B, w.GL)
        assert r.status_code == 200, r.text
        assert r.json()["collector_id"] == str(w.GL.id) and r.json()["collector_name"] == "Green Loop"
        r = self._marcar(client, w, w.B, None)
        assert r.status_code == 200 and r.json()["collector_id"] is None

    def test_t15_rechazos(self, w, client, db_session, test_organization2):
        otra_org = create_third_party_with_category(
            db_session, test_organization2.id, "Recolector otra org", "service_provider")
        db_session.commit()
        casos = [
            (w.B, w.E),        # E no es service_provider
            (w.B, otra_org),   # de otra org
            (w.GL, w.GL),      # se marca a si mismo
            (w.B, w.A),        # nivel unico: el recolector ya esta marcado
            (w.GL, w.X),       # nivel unico: GL es recolector de otros
        ]
        for tp, rec in casos:
            r = self._marcar(client, w, tp, rec)
            assert r.status_code == 422, (tp.name, rec.name, r.text)
        assert client.get(f"{TP}/{w.B.id}", headers=w.johana).json()["collector_id"] is None

    def test_t15_flag(self, w, client, db_session):
        w.org.settings = {"kg_ledger_enabled": False}
        db_session.commit()
        assert self._marcar(client, w, w.B, w.GL).status_code == 422
        w.org.settings = {"kg_ledger_enabled": True}
        db_session.commit()
        assert self._marcar(client, w, w.B, w.GL).status_code == 200

    def test_t15_editar_categorias_no_toca_la_marca(self, w, client, db_session):
        """Regresion de (B): `_sync_category_assignments` borra y recrea las
        categorias; la marca vive en otra columna y no se entera."""
        gen = _get_or_create_category(db_session, w.org.id, "generic")
        db_session.commit()
        r = client.patch(f"{TP}/{w.A.id}", headers=w.johana, json={"category_ids": [str(gen.id)]})
        assert r.status_code == 200, r.text
        assert r.json()["collector_id"] == str(w.GL.id)


# ===========================================================================
# T16: el alcance
# ===========================================================================

def _scope_url(w, user_id):
    return f"{API}/organizations/{w.org.id}/members/{user_id}/collector-scope"


class TestAlcance:

    def test_t16_poner_y_quitar(self, w, client, db_session):
        libre_id = db_session.execute(select(User.id).where(
            User.email == "ingrid_libre@example.com")).scalar_one()
        assert client.get(f"{TP}/{w.B.id}", headers=w.ingrid_libre).status_code == 200
        r = client.put(_scope_url(w, libre_id), headers=w.johana, json={"collector_id": str(w.GL.id)})
        assert r.status_code == 200, r.text
        assert r.json()["collector_id"] == str(w.GL.id)
        assert client.get(f"{TP}/{w.B.id}", headers=w.ingrid_libre).status_code == 404
        r = client.put(_scope_url(w, libre_id), headers=w.johana, json={"collector_id": None})
        assert r.status_code == 200
        assert client.get(f"{TP}/{w.B.id}", headers=w.ingrid_libre).status_code == 200
        # El listado de miembros lo muestra (para la pantalla de usuarios).
        miembros = _ok(client.get(f"{API}/organizations/{w.org.id}/members", headers=w.johana))
        por_id = {m["user_id"]: m.get("collector_scope_id") for m in miembros}
        assert por_id[str(w.ingrid_user.id)] == str(w.GL.id) and por_id[str(libre_id)] is None

    def test_t16_rechazos(self, w, client, db_session, test_user):
        libre_id = db_session.execute(select(User.id).where(
            User.email == "ingrid_libre@example.com")).scalar_one()
        # un no-admin no pone alcances
        r = client.put(_scope_url(w, libre_id), headers=w.ingrid_libre, json={"collector_id": str(w.GL.id)})
        assert r.status_code == 403
        # alcance sobre un admin
        r = client.put(_scope_url(w, test_user.id), headers=w.johana, json={"collector_id": str(w.GL.id)})
        assert r.status_code == 422
        # org sin flag
        w.org.settings = {"kg_ledger_enabled": False}
        db_session.commit()
        r = client.put(_scope_url(w, libre_id), headers=w.johana, json={"collector_id": str(w.GL.id)})
        assert r.status_code == 422
        db_session.expire_all()
        assert db_session.execute(select(UserCollectorScope).where(
            UserCollectorScope.user_id.in_([libre_id, test_user.id]))).first() is None

    def test_t16_my_permissions(self, w, client):
        r = _ok(client.get(f"{API}/roles/my-permissions", headers=w.ingrid))
        assert r["collector_scope"] == {"id": str(w.GL.id), "name": "Green Loop"}
        assert _ok(client.get(f"{API}/roles/my-permissions", headers=w.ingrid_libre))["collector_scope"] is None

    def test_t16b_flag_apagado_despues(self, w, client, db_session):
        """v1.4: en las rutas SIN flag el alcance sigue restringiendo; en las
        Entradas el router corta con 403 a todos antes que el alcance."""
        w.org.settings = {"kg_ledger_enabled": False}
        db_session.commit()
        assert client.get(f"{TP}/{w.B.id}", headers=w.ingrid).status_code == 404
        assert client.get(f"{PURCHASES}/{w.compra_B}", headers=w.ingrid).status_code == 404
        assert client.get(f"{TP}/{w.A.id}", headers=w.ingrid).status_code == 200  # control
        assert client.get(f"{INBOUND}/{w.E_GL}", headers=w.ingrid).status_code == 403
        assert client.get(f"{INBOUND}/{w.E_none}", headers=w.ingrid).status_code == 403

    def test_t16c_admin_con_fila_de_alcance(self, w, client, db_session, test_user):
        """Fail-closed: la fila manda, aunque el rol sea admin."""
        db_session.add(UserCollectorScope(organization_id=w.org.id, user_id=test_user.id,
                                          collector_id=w.GL.id))
        db_session.commit()
        assert client.get(f"{INBOUND}/{w.E_GL}", headers=w.johana).status_code == 200
        assert client.get(f"{INBOUND}/{w.E_none}", headers=w.johana).status_code == 404
        assert client.get(f"{TP}/{w.B.id}", headers=w.johana).status_code == 404
        assert _scope_denied(client.get(f"{API}/organizations/{w.org.id}/members", headers=w.johana))
        assert _scope_denied(client.get(f"{API}/inventory/stock", headers=w.johana))
        w.org.settings = {"kg_ledger_enabled": False}
        db_session.commit()
        assert client.get(f"{INBOUND}/{w.E_GL}", headers=w.johana).status_code == 403

    def test_t16d_superusuario(self, w, client, db_session):
        su = User(email="su@example.com", hashed_password=get_password_hash("x1234567"),
                  full_name="SU", is_active=True, is_superuser=True)
        db_session.add(su)
        db_session.flush()
        db_session.add(OrganizationMember(user_id=su.id, organization_id=w.org.id,
                                          role_id=w.role_recolector.id))
        db_session.commit()
        r = client.put(_scope_url(w, su.id), headers=w.johana, json={"collector_id": str(w.GL.id)})
        assert r.status_code == 422, r.text
        db_session.expire_all()
        assert db_session.execute(select(UserCollectorScope).where(
            UserCollectorScope.user_id == su.id)).first() is None


# ===========================================================================
# T17: el balance detallado, vivo y as-of
# ===========================================================================

def _secciones(data) -> dict:
    return {**data["assets"], **data["liabilities"]}


class TestBalance:

    def _detallado(self, client, w, as_of=None):
        params = {"as_of_date": as_of} if as_of else {}
        return _ok(client.get(f"{API}/reports/balance-detailed", headers=w.johana, params=params))

    @pytest.mark.parametrize("as_of", [None, "hoy"])
    def test_t17_grupo_del_recolector(self, w, client, db_session, as_of):
        as_of = _today() if as_of == "hoy" else None
        # A2 queda en anticipos con un anticipo de Johana desde K2.
        _ok(_pago(client, w.johana, "advance-payment", w.K2, w.A2, amount="3000"), 201)
        con = _secciones(self._detallado(client, w, as_of))
        cxp = con["suppliers_payable"]
        assert cxp["total"] != 0 and cxp["groups"] and len(cxp["groups"]) >= 2  # contra la vacuidad
        gl = [g for g in cxp["groups"] if g["label"] == "Recolector: Green Loop"]
        assert len(gl) == 1 and {i["id"] for i in gl[0]["items"]} == {str(w.A.id)}
        assert str(w.B.id) not in {i["id"] for i in gl[0]["items"]}
        anticipos = con["supplier_advances"]
        assert anticipos["total"] != 0
        assert any(g["label"] == "Recolector: Green Loop" and {i["id"] for i in g["items"]} == {str(w.A2.id)}
                   for g in anticipos["groups"] or [])

        # Sin marcas: mismos totales, ningun grupo de recolector.
        for tp in (w.A, w.A2, w.D):
            db_session.get(ThirdParty, tp.id).collector_id = None
        db_session.commit()
        sin = _secciones(self._detallado(client, w, as_of))
        assert {k: v["total"] for k, v in sin.items()} == {k: v["total"] for k, v in con.items()}
        assert not any(g["label"].startswith("Recolector:")
                       for s in sin.values() for g in (s["groups"] or []))
        assert all(set(s) == {"label", "total", "items", "groups"} for s in sin.values())


# ===========================================================================
# T18: no-regresion en una org sin alcances (el caso de Costa)
# ===========================================================================

class TestOtraOrg:

    def test_t18_usuario_restringido_por_cuentas_como_hoy(self, w, client, db_session):
        w.org.settings = {}
        db_session.commit()
        _, h = _member(db_session, w.org.id, "restringido", w.role_recolector.id, accounts=[w.K1.id])
        db_session.commit()
        aj_B = _ajuste(client, w.johana, w.B)
        assert _ids(_lista(client.get(f"{API}/money-accounts", headers=h))) == {str(w.K1.id)}
        assert client.get(f"{API}/money-accounts/{w.K2.id}", headers=h).status_code == 403
        assert client.get(f"{MM}/account/{w.K2.id}", headers=h).status_code == 403
        # Hoy deja pasar la cuenta NULL de cualquier tercero (§2.4): no se toca.
        assert aj_B["id"] in _ids(_ok(client.get(MM, headers=h, params={"limit": 500}))["items"])
        assert client.get(f"{MM}/third-party/{w.B.id}", headers=h).status_code == 200
        assert client.get(f"{TP}/{w.B.id}", headers=h).status_code == 200


# ===========================================================================
# T20 (N1): RESTRICT sobre el recolector
# ===========================================================================

class TestRestrict:

    def test_t20_borrar_al_recolector_falla(self, w, db_session):
        gl = db_session.get(ThirdParty, w.GL.id)
        db_session.delete(gl)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()
        db_session.expire_all()
        assert db_session.get(ThirdParty, w.GL.id) is not None
        assert db_session.get(ThirdParty, w.A.id).collector_id == w.GL.id
        assert db_session.execute(select(UserCollectorScope).where(
            UserCollectorScope.collector_id == w.GL.id)).first() is not None
