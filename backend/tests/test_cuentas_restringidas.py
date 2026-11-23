"""Cuentas restringidas: un miembro con cuentas asignadas solo ve y mueve esas
cuentas (plan docs/planes/plan-cuentas-restringidas.md v1.2, §4).

La regla vive en `app/services/account_access.py`: `accounts_for` decide el
conjunto, un listener `before_flush` corta toda escritura sobre una cuenta no
asignada (403 que nombra la cuenta) y las lecturas por id dan 404 (C1).

El mundo: una org con tres cuentas, nombradas en ASCII y en mayusculas para que
el orden por nombre no dependa de la collation (K2 de QA; el Postgres de test es
Alpine/musl y ordena por bytes):
  K3 «AAA CAJA AJENA»   la que nadie restringido tiene;
  K2 «BBB BANCO»        la segunda del analista;
  K1 «ZZZ CAJA PROPIA»  la asignada; queda TERCERA por nombre (T7).

Usuarios (§4, R3) — los permisos se escriben aca como constantes, sin depender
del sembrado; nunca el admin para medir un permiso (bypassa, #29):
  liquidador        los 32 del liquidador de Costa, K1;
  analista          los 16 del analista de SAC en produccion, K1 y K2;
  cuentas           treasury.manage_accounts + treasury.view_accounts, K1;
  por ruta          exactamente el permiso de la ruta, K1;
  admin             rol admin de sistema con K1 asignada (org_headers);
  sin_asignaciones  los 16 del analista, sin cuentas.

Todo 403 que se atribuye al listener afirma que el detalle nombra la cuenta: un
403 de RBAC dice que falta el permiso y no nombra ninguna (R3).

Los imports de `account_access` van DENTRO de los tests que los usan: T5 se
corre tambien contra la base (4006fb8), donde ese modulo no existe.
"""
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Callable
from uuid import uuid4

import pytest
from sqlalchemy import select, update

from app.api.deps import get_db
from app.api.v1.endpoints import money_movements as mm_endpoint
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.base import Base
from app.models.money_account import MoneyAccount
from app.models.money_movement import MoneyMovement
from app.models.permission import Permission
from app.models.role import Role, RolePermission
from app.models.third_party import ThirdParty
from app.models.third_party_category import ThirdPartyCategory, ThirdPartyCategoryAssignment
from app.models.user import OrganizationMember, User, UserAccountAssignment, UserCollectorScope
from app.utils.dates import business_today
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    create_business_unit, create_expense_category, create_material,
    create_material_category, create_warehouse,
)

API = "/api/v1"
MM = f"{API}/money-movements"
FO = f"{API}/financial-obligations"
FA = f"{API}/fixed-assets"

# Los 32 del rol liquidador de Costa (copia de dev; cuentas_permisos_liquidador_costa.txt,
# sha256 6a4e8235d04b80cf…). Sin view_statements ni view_dashboard.
PERMISOS_LIQUIDADOR = [
    "config.manage_business_units", "config.view_business_units",
    "materials.edit_prices", "materials.view", "materials.view_prices",
    "purchases.cancel", "purchases.create", "purchases.edit", "purchases.edit_prices",
    "purchases.liquidate", "purchases.view", "purchases.view_prices",
    "reports.view_expenses",
    "sales.cancel", "sales.create", "sales.edit", "sales.edit_prices", "sales.liquidate",
    "sales.view", "sales.view_prices",
    "third_parties.create", "third_parties.edit", "third_parties.view",
    "treasury.adjust_balances", "treasury.create_movements", "treasury.edit_classification",
    "treasury.manage_expenses", "treasury.manage_obligations", "treasury.view_accounts",
    "treasury.view_movements", "treasury.view_obligations",
    "warehouses.view",
]
assert len(PERMISOS_LIQUIDADOR) == 32

# Los 16 del rol analista de SAC en produccion (gate-prod/rol_analista_sac_prod.log;
# cuentas_permisos_analista_sac_prod.txt). Con view_statements y view_dashboard.
PERMISOS_ANALISTA = [
    "treasury.adjust_balances", "treasury.create_movements", "treasury.edit_classification",
    "treasury.manage_distributions", "treasury.manage_fixed_assets",
    "treasury.manage_obligations", "treasury.view_accounts", "treasury.view_all_movements",
    "treasury.view_dashboard", "treasury.view_fixed_assets", "treasury.view_liabilities",
    "treasury.view_movements", "treasury.view_obligations", "treasury.view_provisions",
    "treasury.view_scheduled", "treasury.view_statements",
]
assert len(PERMISOS_ANALISTA) == 16

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.4\n%prueba\n"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _past(days=1) -> str:
    return (business_today() - timedelta(days=days)).isoformat()


def _today() -> str:
    return business_today().isoformat()


def _period(months_ago: int) -> str:
    d = business_today().replace(day=1)
    for _ in range(months_ago):
        d = (d - timedelta(days=1)).replace(day=1)
    return d.strftime("%Y-%m")


# Permisos que existen en produccion por migracion pero NO en `PERMISSIONS_CATALOG`,
# de donde siembra la base de test (desfase preexistente; el primero ya lo
# reportaron los tests de Ingrid). Se crean con los campos de su migracion.
_FUERA_DEL_CATALOGO = {
    # migracion 3771a60dccbe
    "treasury.view_all_movements": ("Ver Todos los Movimientos", 83,
                                    "Permite ver todos los movimientos, incluidos los de otros usuarios."),
    # migracion a1b2c3d4e5f7
    "treasury.manage_distributions": ("Gestionar Reparticiones", 91,
                                      "Permite ver y crear reparticiones de utilidades"),
}


def _ensure_fuera_del_catalogo(db) -> None:
    for code, (display, order, desc) in _FUERA_DEL_CATALOGO.items():
        if db.execute(select(Permission).where(Permission.code == code)).scalar_one_or_none() is None:
            db.add(Permission(code=code, display_name=display, module="treasury",
                              sort_order=order, description=desc))
    db.flush()


def _role(db, org_id, name, codes) -> Role:
    _ensure_fuera_del_catalogo(db)
    role = Role(organization_id=org_id, name=name, display_name=name, is_system_role=False)
    db.add(role)
    db.flush()
    perms = db.execute(select(Permission).where(Permission.code.in_(codes))).scalars().all()
    assert len(perms) == len(set(codes)), (sorted(codes), sorted(p.code for p in perms))
    for p in perms:
        db.add(RolePermission(role_id=role.id, permission_id=p.id))
    db.flush()
    return role


def _member(db, org_id, tag, role_id, accounts=(), superuser=False) -> tuple[User, dict]:
    user = User(email=f"{tag}@example.com", hashed_password=get_password_hash("pass1234"),
                full_name=tag, is_active=True, is_superuser=superuser)
    db.add(user)
    db.flush()
    if role_id is not None:
        db.add(OrganizationMember(user_id=user.id, organization_id=org_id, role_id=role_id))
    for acc in accounts:
        db.add(UserAccountAssignment(user_id=user.id, organization_id=org_id, account_id=acc))
    db.flush()
    headers = {"Authorization": f"Bearer {create_access_token(data={'sub': str(user.id)})}",
               "X-Organization-ID": str(org_id)}
    return user, headers


def _ok(r, codes=(200, 201)):
    assert r.status_code in codes, (r.status_code, r.text)
    return r.json() if r.text else None


def _detail(r) -> str:
    try:
        return str(r.json().get("detail", ""))
    except Exception:
        return r.text


def _assert_listener_403(r, account_name: str):
    """403 del listener: nombra la cuenta (R3). Uno de RBAC no la nombra."""
    assert r.status_code == 403, (r.status_code, r.text)
    assert f"«{account_name}»" in _detail(r), _detail(r)


def _foto(db) -> dict:
    """Todas las filas de todas las tablas: «nada queda escrito» (N2) se afirma
    sobre la base entera, no sobre una lista de tablas que se pueda quedar corta."""
    db.rollback()
    out = {}
    for table in Base.metadata.tables.values():
        rows = db.execute(table.select()).all()
        out[table.name] = sorted(tuple(str(v) for v in row) for row in rows)
    return out


def _diff(antes: dict, despues: dict) -> list[str]:
    return [t for t in antes if antes[t] != despues.get(t)]


def _send(client, headers, req):
    method, url, kwargs = req
    return client.request(method, url, headers=headers, **kwargs)


def _expense(client, headers, m, account, amount="1000", date=None) -> dict:
    return _ok(client.post(f"{MM}/expense", headers=headers, json={
        "amount": amount, "expense_category_id": str(m.EC.id), "account_id": str(account.id),
        "description": f"gasto {account.name}", "date": date or _past()}), (201,))


def _evidence(client, headers, mid):
    return client.post(f"{MM}/{mid}/evidence", headers=headers,
                       files={"file": ("comprobante.png", PNG, "image/png")})


def _tp_with_category_name(db, org_id, name, behavior, category_name, **kw) -> ThirdParty:
    cat = db.execute(select(ThirdPartyCategory).where(
        ThirdPartyCategory.organization_id == org_id,
        ThirdPartyCategory.name == category_name)).scalar_one_or_none()
    if cat is None:
        cat = ThirdPartyCategory(organization_id=org_id, name=category_name, behavior_type=behavior)
        db.add(cat)
        db.flush()
    tp = ThirdParty(name=name, organization_id=org_id, **kw)
    db.add(tp)
    db.flush()
    db.add(ThirdPartyCategoryAssignment(third_party_id=tp.id, category_id=cat.id))
    db.flush()
    return tp


# ---------------------------------------------------------------------------
# El mundo
# ---------------------------------------------------------------------------

@dataclass
class Mundo:
    db: object
    client: object
    org: object
    admin: dict
    admin_user: User
    liquidador: dict
    liquidador_user: User
    analista: dict
    cuentas: dict
    sin_asignaciones: dict
    K1: MoneyAccount
    K2: MoneyAccount
    K3: MoneyAccount
    S: ThirdParty      # proveedor de material
    C: ThirdParty      # cliente
    I: ThirdParty      # inversionista
    SP: ThirdParty     # proveedor de servicios (comisiones)
    P: ThirdParty      # provision
    G: ThirdParty      # generico
    L: ThirdParty      # pasivo
    EC: object
    EC2: object
    WH: object
    MAT: object
    _por_ruta: dict = field(default_factory=dict)

    def por_ruta(self, perm: str, cuentas=("K1",)) -> dict:
        """Usuario con EXACTAMENTE el permiso de la ruta (R3) y sus cuentas."""
        key = (perm, tuple(cuentas))
        if key not in self._por_ruta:
            tag = f"ruta_{len(self._por_ruta)}"
            role = _role(self.db, self.org.id, tag, [perm])
            _, headers = _member(self.db, self.org.id, tag, role.id,
                                 accounts=[getattr(self, c).id for c in cuentas])
            self.db.commit()
            self._por_ruta[key] = headers
        return self._por_ruta[key]

    def account(self, key: str) -> MoneyAccount:
        return getattr(self, key)


@pytest.fixture
def m(db_session, client, org_headers, test_organization, test_user) -> Mundo:
    db = db_session
    org = test_organization
    acc = lambda name, kind: MoneyAccount(  # noqa: E731
        name=name, account_type=kind, current_balance=Decimal("500000000"),
        organization_id=org.id, is_active=True)
    K3, K2, K1 = acc("AAA CAJA AJENA", "cash"), acc("BBB BANCO", "bank"), acc("ZZZ CAJA PROPIA", "cash")
    db.add_all([K3, K2, K1])
    db.flush()

    tp = lambda name, behavior, **kw: create_third_party_with_category(db, org.id, name, behavior, **kw)  # noqa: E731
    S = tp("Proveedor S", "material_supplier")
    C = tp("Cliente C", "customer")
    I = tp("Socio I", "investor", current_balance=Decimal("-100000000"))  # noqa: E741
    SP = tp("Comisionista SP", "service_provider", current_balance=Decimal("-10000000"))
    P = tp("Provision P", "provision")
    G = tp("Generico G", "generic")
    L = tp("Pasivo L", "liability")
    EC = create_expense_category(db, org.id, "Gastos T")
    EC2 = create_expense_category(db, org.id, "Gastos T2")
    WH = create_warehouse(db, org.id, "Bodega T")
    cat = create_material_category(db, org.id, "Cat T")
    bu = create_business_unit(db, org.id, "UN T")
    MAT = create_material(db, org.id, "MAT-T", "Material T", cat.id, bu_id=bu.id)
    MAT.default_unit = "kg"

    # Admin de sistema (test_user) con K1 asignada: D1, no lo restringe.
    db.add(UserAccountAssignment(user_id=test_user.id, organization_id=org.id, account_id=K1.id))
    rol_liq = _role(db, org.id, "liquidador_t", PERMISOS_LIQUIDADOR)
    rol_ana = _role(db, org.id, "analista_t", PERMISOS_ANALISTA)
    rol_ctas = _role(db, org.id, "cuentas_t", ["treasury.manage_accounts", "treasury.view_accounts"])
    liq_user, liquidador = _member(db, org.id, "liquidador", rol_liq.id, accounts=[K1.id])
    _, analista = _member(db, org.id, "analista", rol_ana.id, accounts=[K1.id, K2.id])
    _, cuentas = _member(db, org.id, "cuentas", rol_ctas.id, accounts=[K1.id])
    _, sin_asignaciones = _member(db, org.id, "sin_asignaciones", rol_ana.id)
    db.commit()
    return Mundo(db=db, client=client, org=org, admin=org_headers, admin_user=test_user,
                 liquidador=liquidador, liquidador_user=liq_user, analista=analista,
                 cuentas=cuentas, sin_asignaciones=sin_asignaciones,
                 K1=K1, K2=K2, K3=K3, S=S, C=C, I=I, SP=SP, P=P, G=G, L=L,
                 EC=EC, EC2=EC2, WH=WH, MAT=MAT)


@pytest.fixture
def uploads(tmp_path, monkeypatch) -> Path:
    from app.core.config import settings
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# Prerrequisitos que arma el admin (cuenta libre por D1)
# ---------------------------------------------------------------------------

def _obligacion(m: Mundo, *, accrue: bool) -> str:
    """Obligacion payable de 10M desembolsada desde K1 hace 2 meses; con
    `accrue`, sus dos meses cerrados quedan causados (interes pendiente)."""
    tp = _tp_with_category_name(m.db, m.org.id, f"Banco Obligacion {uuid4().hex[:8]}",
                                "investor", "Obligaciones Financieras")
    m.db.commit()
    ob = _ok(m.client.post(f"{FO}/", headers=m.admin, json={
        "third_party_id": str(tp.id), "direction": "payable", "monthly_rate": "2.00",
        "mode": "disbursement", "accrual_start_period": _period(2),
        "disbursement": {"account_id": str(m.K1.id), "amount": "10000000",
                         "date": f"{_period(2)}-05"}}), (201,))
    if accrue:
        _ok(m.client.post(f"{FO}/accrue-pending", headers=m.admin,
                          json={"expense_category_id": str(m.EC.id)}))
    return ob["id"]


def _activo(m: Mundo, account: MoneyAccount, code: str) -> dict:
    return _ok(m.client.post(f"{FA}/", headers=m.admin, json={
        "name": f"Activo {code}", "asset_code": code, "purchase_date": _past(30),
        "purchase_value": 12000000, "salvage_value": 0, "depreciation_rate": 1.0,
        "depreciation_start_date": _past(30), "expense_category_id": str(m.EC.id),
        "source_account_id": str(account.id)}), (201,))


def _compra(m: Mundo, *, pagada_desde: MoneyAccount | None = None) -> dict:
    body = {"supplier_id": str(m.S.id), "date": _past(),
            "lines": [{"material_id": str(m.MAT.id), "quantity": 10, "unit_price": 1000,
                       "warehouse_id": str(m.WH.id)}]}
    if pagada_desde is not None:
        body.update(auto_liquidate=True, immediate_payment=True,
                    payment_account_id=str(pagada_desde.id))
    return _ok(m.client.post(f"{API}/purchases", headers=m.admin, json=body), (201,))


def _venta(m: Mundo, *, cobrada_en: MoneyAccount | None = None) -> dict:
    body = {"customer_id": str(m.C.id), "warehouse_id": str(m.WH.id), "date": _past(),
            "lines": [{"material_id": str(m.MAT.id), "quantity": 1, "unit_price": 1000}]}
    if cobrada_en is not None:
        body.update(auto_liquidate=True, immediate_collection=True,
                    collection_account_id=str(cobrada_en.id))
    return _ok(m.client.post(f"{API}/sales", headers=m.admin, json=body), (201,))


def _entrada_revisada(m: Mundo) -> str:
    """Entrada de compra revisada (100 kg) en una org con `kg_ledger_enabled`."""
    m.org.settings = {"kg_ledger_enabled": True}
    m.db.commit()
    _ok(m.client.put(f"{API}/material-kg-profiles/{m.MAT.id}", headers=m.admin,
                     json={"compra_regular": True, "willard_world": "none", "lead_product": "none"}))
    oid = _ok(m.client.post(f"{API}/inbound-orders", headers=m.admin, json={
        "inbound_type": "purchase", "warehouse_id": str(m.WH.id), "date": _past(),
        "lines": [{"material_id": str(m.MAT.id), "quantity": "100", "scale_weight_kg": "100"}]}),
        (201,))["id"]
    _ok(m.client.post(f"{API}/inbound-orders/{oid}/review", headers=m.admin))
    return oid


# ---------------------------------------------------------------------------
# T1 — barrido de las escrituras con cuenta en el cuerpo
# ---------------------------------------------------------------------------

def _mm_body(kind: str) -> Callable:
    """Cuerpo de una creacion de tesoreria, por tipo (schemas de money_movement)."""
    def build(m: Mundo, acc: MoneyAccount) -> dict:
        base = {"amount": "1000", "account_id": str(acc.id), "date": _past(),
                "description": f"{kind} {acc.name}"}
        extra = {
            "advance-collection": {"customer_id": str(m.C.id)},
            "advance-payment": {"supplier_id": str(m.S.id)},
            "asset-payment": {},
            "capital-injection": {"investor_id": str(m.I.id)},
            "capital-return": {"investor_id": str(m.I.id)},
            "collection-from-generic": {"third_party_id": str(m.G.id)},
            "commission-payment": {"third_party_id": str(m.SP.id)},
            "customer-collection": {"customer_id": str(m.C.id)},
            "expense": {"expense_category_id": str(m.EC.id)},
            "payment-to-generic": {"third_party_id": str(m.G.id)},
            "provision-deposit": {"provision_id": str(m.P.id)},
            "service-income": {},
            "supplier-payment": {"supplier_id": str(m.S.id)},
        }[kind]
        return {**base, **extra}
    return build


@dataclass
class Ruta:
    perm: str
    # prep(m) arma lo que la ruta necesita y devuelve req(acc) -> (metodo, url, kwargs)
    prep: Callable
    por_id: bool = False          # ruta por id de movimiento: K3 da 404 por C1 antes del listener
    cuentas: tuple = ("K1",)      # cuentas del usuario «por ruta»


def _simple(method, url, body_fn):
    def prep(m):
        return lambda acc: (method, url, {"json": body_fn(m, acc)})
    return prep


def _prep_fo_create(m):
    tp = _tp_with_category_name(m.db, m.org.id, "Banco Nuevo", "investor", "Obligaciones Financieras")
    m.db.commit()
    return lambda acc: ("POST", f"{FO}/", {"json": {
        "third_party_id": str(tp.id), "direction": "payable", "monthly_rate": "2.00",
        "mode": "disbursement",
        "disbursement": {"account_id": str(acc.id), "amount": "1000000", "date": _past()}}})


def _prep_fo_action(action):
    def prep(m):
        ob = _obligacion(m, accrue=True)
        return lambda acc: ("POST", f"{FO}/{ob}/{action}", {"json": {
            "amount": "1000", "account_id": str(acc.id), "date": _today()}})
    return prep


def _prep_fa_create(m):
    return lambda acc: ("POST", f"{FA}/", {"json": {
        "name": "Activo T1", "asset_code": "T1-FA", "purchase_date": _past(30),
        "purchase_value": 12000000, "salvage_value": 0, "depreciation_rate": 1.0,
        "depreciation_start_date": _past(30), "expense_category_id": str(m.EC.id),
        "source_account_id": str(acc.id)}})


def _prep_fa_revalue(m):
    asset = _activo(m, m.K1, "T1-REV")
    return lambda acc: ("POST", f"{FA}/{asset['id']}/revalue", {"json": {
        "revaluation_type": "increase", "amount": 1000000, "months_extended": 0,
        "source_account_id": str(acc.id)}})


def _prep_fa_sell(m):
    asset = _activo(m, m.K1, "T1-SELL")
    return lambda acc: ("POST", f"{FA}/{asset['id']}/sell", {"json": {
        "sale_price": 5000000, "account_id": str(acc.id)}})


def _prep_inbound_liquidate(m):
    oid = _entrada_revisada(m)
    return lambda acc: ("POST", f"{API}/inbound-orders/{oid}/liquidate", {"json": {
        "lines": [{"material_id": str(m.MAT.id), "allocations": [{
            "third_party_id": str(m.S.id), "purchase_slot": 1, "quantity": "100",
            "unit_price": "1000"}]}],
        "supplier_payments": [{"purchase_slot": 1, "third_party_id": str(m.S.id),
                               "account_id": str(acc.id)}]}})


def _prep_ma_delete(m):
    # Saldo 0 en las dos: sin eso el servicio responde 400 por saldo antes del flush.
    m.db.execute(update(MoneyAccount).where(MoneyAccount.id.in_([m.K1.id, m.K3.id]))
                 .values(current_balance=0))
    m.db.commit()
    return lambda acc: ("DELETE", f"{API}/money-accounts/{acc.id}", {})


def _prep_ma_patch(m):
    return lambda acc: ("PATCH", f"{API}/money-accounts/{acc.id}",
                        {"json": {"name": f"{acc.name} EDITADA"}})


def _prep_batch(m):
    return lambda acc: ("POST", f"{MM}/batch-expenses", {"json": {"items": [{
        "amount": "1000", "expense_category_id": str(m.EC.id), "account_id": str(acc.id),
        "date": _past(), "description": "lote T1"}]}})


def _prep_transfer(m):
    # D2: un traslado exige las dos cuentas. El usuario de la fila tiene K1 y K2.
    return lambda acc: ("POST", f"{MM}/transfer", {"json": {
        "amount": "1000", "source_account_id": str(acc.id),
        "destination_account_id": str(m.K2.id), "date": _past(), "description": "traslado T1"}})


def _movs(m):
    """Un gasto en K3 y otro en K1, creados por el admin, cada uno con evidencia."""
    out = {}
    for key in ("K3", "K1"):
        mv = _expense(m.client, m.admin, m, m.account(key))
        _ok(_evidence(m.client, m.admin, mv["id"]))
        out[key] = mv
    return out


def _prep_by_id(method, suffix, kwargs_fn=lambda m: {}):
    def prep(m):
        movs = _movs(m)
        key_of = {m.K3.id: "K3", m.K1.id: "K1"}
        return lambda acc: (method, f"{MM}/{movs[key_of[acc.id]]['id']}{suffix}", kwargs_fn(m))
    return prep


def _prep_purchase_create(m):
    return lambda acc: ("POST", f"{API}/purchases", {"json": {
        "supplier_id": str(m.S.id), "date": _past(),
        "lines": [{"material_id": str(m.MAT.id), "quantity": 10, "unit_price": 1000,
                   "warehouse_id": str(m.WH.id)}],
        "auto_liquidate": True, "immediate_payment": True, "payment_account_id": str(acc.id)}})


def _prep_purchase_liquidate(m):
    compra = _compra(m)
    return lambda acc: ("PATCH", f"{API}/purchases/{compra['id']}/liquidate", {"json": {
        "immediate_payment": True, "payment_account_id": str(acc.id)}})


def _prep_sale_create(m):
    return lambda acc: ("POST", f"{API}/sales", {"json": {
        "customer_id": str(m.C.id), "warehouse_id": str(m.WH.id), "date": _past(),
        "lines": [{"material_id": str(m.MAT.id), "quantity": 1, "unit_price": 1000}],
        "auto_liquidate": True, "immediate_collection": True,
        "collection_account_id": str(acc.id)}})


def _prep_sale_liquidate(m):
    venta = _venta(m)
    return lambda acc: ("PATCH", f"{API}/sales/{venta['id']}/liquidate", {"json": {
        "immediate_collection": True, "collection_account_id": str(acc.id)}})


def _prep_scheduled(m):
    return lambda acc: ("POST", f"{API}/scheduled-expenses/", {"json": {
        "name": "Seguro T1", "total_amount": "1200000", "total_months": 12,
        "source_account_id": str(acc.id), "expense_category_id": str(m.EC.id),
        "start_date": _past()}})


# La lista es EXPLICITA y esta completa porque sale del inventario v2
# (~/sac-evidencia/2026-11-20/coder-2-recolector-alcance/cuentas_inventario_87c799f_v2.log):
# las 34 filas ESCRITURA (toda ruta con una cuenta en el cuerpo o en la ruta), con el
# permiso de su columna, mas POST /money-accounts (C2). Una ruta nueva que reciba una
# cuenta entra aca a mano: la lista no se deriva, para que agregarla sea una decision
# (#108). La cuenta se compara contra el largo, asi una fila borrada se ve.
RUTAS: dict[str, Ruta] = {
    # financial-obligations (4)
    "fo_create": Ruta("treasury.manage_obligations", _prep_fo_create),
    "fo_capital_payment": Ruta("treasury.manage_obligations", _prep_fo_action("capital-payment")),
    "fo_disbursement": Ruta("treasury.manage_obligations", _prep_fo_action("disbursement")),
    "fo_interest_payment": Ruta("treasury.manage_obligations", _prep_fo_action("interest-payment")),
    # fixed-assets (3)
    "fa_create": Ruta("treasury.manage_fixed_assets", _prep_fa_create),
    "fa_revalue": Ruta("treasury.manage_fixed_assets", _prep_fa_revalue),
    "fa_sell": Ruta("treasury.manage_fixed_assets", _prep_fa_sell),
    # inbound-orders (1), en una org con kg_ledger_enabled
    "inbound_liquidate": Ruta("purchases.liquidate", _prep_inbound_liquidate),
    # money-accounts (2 del inventario)
    "ma_delete": Ruta("treasury.manage_accounts", _prep_ma_delete),
    "ma_patch": Ruta("treasury.manage_accounts", _prep_ma_patch),
    # money-movements, creaciones (15)
    **{f"mm_{k}": Ruta("treasury.create_movements",
                       _simple("POST", f"{MM}/{k}", _mm_body(k)))
       for k in ("advance-collection", "advance-payment", "asset-payment", "capital-injection",
                 "capital-return", "collection-from-generic", "commission-payment",
                 "customer-collection", "expense", "payment-to-generic", "provision-deposit",
                 "service-income", "supplier-payment")},
    "mm_batch-expenses": Ruta("treasury.create_movements", _prep_batch),
    "mm_transfer": Ruta("treasury.create_movements", _prep_transfer, cuentas=("K1", "K2")),
    # money-movements por id (4): C1 da 404 antes del listener
    "mm_annul": Ruta("treasury.create_movements",
                     _prep_by_id("POST", "/annul", lambda m: {"json": {"reason": "Anulacion T1"}}), por_id=True),
    "mm_classification": Ruta("treasury.edit_classification",
                              _prep_by_id("PATCH", "/classification",
                                          lambda m: {"json": {"expense_category_id": str(m.EC2.id)}}),
                              por_id=True),
    "mm_evidence_delete": Ruta("treasury.create_movements", _prep_by_id("DELETE", "/evidence"),
                               por_id=True),
    "mm_evidence_post": Ruta("treasury.create_movements",
                             # Otra extension que la del admin: la URL es `{id}_{segundo}.{ext}`
                             # y en el mismo segundo y con la misma extension la fila queda
                             # IGUAL (sin cambio neto, el listener no tiene nada que mirar; el
                             # disco si cambia, y eso lo cubre C1, que va antes).
                             _prep_by_id("POST", "/evidence", lambda m: {
                                 "files": {"file": ("otro.pdf", PDF, "application/pdf")}}),
                             por_id=True),
    # purchases (2), sales (2), scheduled-expenses (1)
    "purchase_create": Ruta("purchases.create", _prep_purchase_create),
    "purchase_liquidate": Ruta("purchases.liquidate", _prep_purchase_liquidate),
    "sale_create": Ruta("sales.create", _prep_sale_create),
    "sale_liquidate": Ruta("sales.liquidate", _prep_sale_liquidate),
    "scheduled_create": Ruta("treasury.manage_expenses", _prep_scheduled),
}
assert len(RUTAS) == 34, len(RUTAS)  # + POST /money-accounts (test aparte) = 35 (K1 de QA)


class TestT1BarridoDeEscrituras:

    @pytest.mark.parametrize("key", sorted(RUTAS))
    def test_t1_k3_da_403_y_no_escribe_k1_pasa(self, m, client, db_session, uploads, key):
        ruta = RUTAS[key]
        req = ruta.prep(m)
        headers = m.por_ruta(ruta.perm, ruta.cuentas)

        antes = _foto(db_session)
        r = _send(client, headers, req(m.K3))
        if ruta.por_id:
            assert r.status_code == 404, (r.status_code, r.text)  # C1, antes del listener
        else:
            _assert_listener_403(r, m.K3.name)
        assert _diff(antes, _foto(db_session)) == []

        _ok(_send(client, headers, req(m.K1)))

    @pytest.mark.parametrize("key", sorted(k for k, ruta in RUTAS.items() if ruta.por_id))
    def test_t1_por_id_sin_c1_la_red_es_el_listener(self, m, client, db_session, uploads,
                                                    monkeypatch, key):
        """Sin C1, el listener corta igual (§2.1: queda como red). La evidencia
        en disco no es del listener; aca se mira la base."""
        ruta = RUTAS[key]
        req = ruta.prep(m)
        headers = m.por_ruta(ruta.perm, ruta.cuentas)
        monkeypatch.setattr(mm_endpoint, "_require_movement_visible", lambda *a, **k: None)
        antes = _foto(db_session)
        _assert_listener_403(_send(client, headers, req(m.K3)), m.K3.name)
        assert _diff(antes, _foto(db_session)) == []

    def test_t1_post_money_accounts_siempre_403(self, m, client, db_session):
        """C2/D6: un restringido no crea cuentas; la cuenta nueva no esta en su
        conjunto. Control: el mismo permiso sin asignaciones crea (201)."""
        headers = m.por_ruta("treasury.manage_accounts")
        body = {"name": "CCC NUEVA", "account_type": "cash"}
        antes = _foto(db_session)
        _assert_listener_403(client.post(f"{API}/money-accounts", headers=headers, json=body),
                             "CCC NUEVA")
        assert _diff(antes, _foto(db_session)) == []
        libre = m.por_ruta("treasury.manage_accounts", cuentas=())
        _ok(client.post(f"{API}/money-accounts", headers=libre, json=body), (201,))


# ---------------------------------------------------------------------------
# T2 — las 6 indirectas: reversas de un movimiento con cuenta
# ---------------------------------------------------------------------------

def _ind_purchase_cancel(m, acc):
    compra = _compra(m, pagada_desde=acc)
    return ("PATCH", f"{API}/purchases/{compra['id']}/cancel",
            {"params": {"annul_linked_payments": "true"}})


def _ind_sale_cancel(m, acc):
    venta = _venta(m, cobrada_en=acc)
    return ("PATCH", f"{API}/sales/{venta['id']}/cancel",
            {"params": {"annul_linked_payments": "true"}})


def _ind_fo_annul(m, acc):
    ob = _obligacion(m, accrue=False)
    mv = _ok(m.client.post(f"{FO}/{ob}/capital-payment", headers=m.admin, json={
        "amount": "1000", "account_id": str(acc.id), "date": _today()}))
    return ("POST", f"{FO}/movements/{mv['id']}/annul", {"json": {"reason": "Anulacion T2"}})


def _ind_fa_cancel(m, acc):
    asset = _activo(m, acc, f"T2-CAN-{acc.name[:3]}")
    return ("POST", f"{FA}/{asset['id']}/cancel", {})


def _ind_fa_sale_annul(m, acc):
    asset = _activo(m, m.K1, f"T2-VEN-{acc.name[:3]}")
    _ok(m.client.post(f"{FA}/{asset['id']}/sell", headers=m.admin,
                      json={"sale_price": 5000000, "account_id": str(acc.id)}))
    return ("POST", f"{FA}/{asset['id']}/sale/annul", {"json": {"reason": "Anulacion T2"}})


def _ind_fa_reval_annul(m, acc):
    asset = _activo(m, m.K1, f"T2-REV-{acc.name[:3]}")
    rev = _ok(m.client.post(f"{FA}/{asset['id']}/revalue", headers=m.admin, json={
        "revaluation_type": "increase", "amount": 1000000, "months_extended": 0,
        "source_account_id": str(acc.id)}))
    rev_id = rev["revaluations"][0]["id"]
    return ("POST", f"{FA}/{asset['id']}/revaluations/{rev_id}/annul", {"json": {"reason": "Anulacion T2"}})


INDIRECTAS = {
    "purchase_cancel": ("purchases.cancel", _ind_purchase_cancel),
    "sale_cancel": ("sales.cancel", _ind_sale_cancel),
    "fo_movement_annul": ("treasury.manage_obligations", _ind_fo_annul),
    "fa_cancel": ("treasury.manage_fixed_assets", _ind_fa_cancel),
    "fa_sale_annul": ("treasury.manage_fixed_assets", _ind_fa_sale_annul),
    "fa_revaluation_annul": ("treasury.manage_fixed_assets", _ind_fa_reval_annul),
}
assert len(INDIRECTAS) == 6  # las 6 ESCRITURA_INDIRECTA del inventario v2


class TestT2Indirectas:

    @pytest.mark.parametrize("key", sorted(INDIRECTAS))
    def test_t2_reversa_de_k3_da_403_k1_pasa(self, m, client, db_session, key):
        perm, build = INDIRECTAS[key]
        headers = m.por_ruta(perm)
        req3 = build(m, m.K3)
        req1 = build(m, m.K1)
        antes = _foto(db_session)
        _assert_listener_403(_send(client, headers, req3), m.K3.name)
        assert _diff(antes, _foto(db_session)) == []
        _ok(_send(client, headers, req1))


# ---------------------------------------------------------------------------
# T3, T4 — admin (D1) y sin asignaciones
# ---------------------------------------------------------------------------

class TestT3T4:

    def test_t3_admin_con_asignacion_no_se_restringe(self, m, client):
        """Orden FIJO: el admin primero (N3). Un cache a nivel de modulo le daria
        al liquidador el `None` del admin, y solo este orden lo atrapa (P13)."""
        _expense(client, m.admin, m, m.K3)
        r = client.post(f"{MM}/expense", headers=m.liquidador, json={
            "amount": "1000", "expense_category_id": str(m.EC.id), "account_id": str(m.K3.id),
            "description": "gasto liquidador", "date": _past()})
        _assert_listener_403(r, m.K3.name)

    def test_t4_sin_asignaciones_escribe_en_cualquiera(self, m, client):
        _expense(client, m.sin_asignaciones, m, m.K3)


# ---------------------------------------------------------------------------
# T5 — estado de cuenta por tercero (D4 + C3)
# ---------------------------------------------------------------------------

class TestT5EstadoDeCuenta:

    def _escenario(self, m, client):
        compra = _compra(m)
        _ok(client.patch(f"{API}/purchases/{compra['id']}/liquidate", headers=m.admin, json={}))
        pagos = {}
        for key, amount in (("K3", "3000"), ("K1", "2000")):
            pagos[key] = _ok(client.post(f"{MM}/supplier-payment", headers=m.admin, json={
                "supplier_id": str(m.S.id), "amount": amount, "account_id": str(m.account(key).id),
                "date": _past(), "description": f"pago {key}"}), (201,))["id"]
        return pagos

    def test_t5_el_analista_ve_todo_y_cierra(self, m, client):
        pagos = self._escenario(m, client)
        r = client.get(f"{MM}/third-party/{m.S.id}", headers=m.analista)
        assert r.status_code == 200, (r.status_code, r.text)  # primero el status
        data = r.json()
        items = data["items"]
        assert items[-1]["balance_after"] == pytest.approx(data["current_balance"])
        por_id = {i.get("source_id"): i for i in items}
        assert str(pagos["K3"]) in por_id  # el pago de K3 aparece
        assert por_id[str(pagos["K3"])]["source"] == "money_movement_restricted"  # C3
        assert por_id[str(pagos["K1"])]["source"] == "money_movement"

    def test_t5_control_admin(self, m, client):
        pagos = self._escenario(m, client)
        data = _ok(client.get(f"{MM}/third-party/{m.S.id}", headers=m.admin))
        por_id = {i.get("source_id"): i for i in data["items"]}
        assert por_id[str(pagos["K3"])]["source"] == "money_movement"
        assert por_id[str(pagos["K1"])]["source"] == "money_movement"
        assert data["items"][-1]["balance_after"] == pytest.approx(data["current_balance"])


# ---------------------------------------------------------------------------
# T6 — dashboard de tesoreria
# ---------------------------------------------------------------------------

class TestT6Dashboard:

    def test_t6_el_analista_ve_solo_sus_cuentas(self, m, client):
        for key, amount in (("K3", "7000"), ("K1", "1000"), ("K2", "500")):
            _expense(client, m.admin, m, m.account(key), amount=amount, date=_today())
        _ok(client.post(f"{MM}/expense-accrual", headers=m.admin, json={
            "third_party_id": str(m.L.id), "amount": "300", "expense_category_id": str(m.EC.id),
            "date": _today(), "description": "causacion sin cuenta"}), (201,))

        def cuentas(d):
            return {a["id"] for k in ("cash_accounts", "bank_accounts", "digital_accounts")
                    for a in d[k]}

        ana = _ok(client.get(f"{API}/reports/treasury-dashboard", headers=m.analista))
        assert cuentas(ana) == {str(m.K1.id), str(m.K2.id)}
        m.db.expire_all()
        k1, k2 = m.db.get(MoneyAccount, m.K1.id), m.db.get(MoneyAccount, m.K2.id)
        assert ana["total_all_accounts"] == pytest.approx(float(k1.current_balance + k2.current_balance))
        assert {r["account_name"] for r in ana["recent_movements"]} <= {m.K1.name, m.K2.name, None}
        assert None in {r["account_name"] for r in ana["recent_movements"]}  # la NULL sigue (D3)

        adm = _ok(client.get(f"{API}/reports/treasury-dashboard", headers=m.admin))
        assert cuentas(adm) == {str(m.K1.id), str(m.K2.id), str(m.K3.id)}
        assert m.K3.name in {r["account_name"] for r in adm["recent_movements"]}
        # el MTD del analista no cuenta el gasto de K3 (7000)
        assert adm["mtd_expense"] - ana["mtd_expense"] == pytest.approx(7000)


# ---------------------------------------------------------------------------
# T7 — GET /money-accounts filtra en la consulta
# ---------------------------------------------------------------------------

class TestT7ListadoDeCuentas:

    def test_t7_la_asignada_tercera_por_nombre_sale_en_la_pagina_1(self, m, client):
        r = _ok(client.get(f"{API}/money-accounts", headers=m.liquidador, params={"limit": 1}))
        assert r["total"] == 1
        assert [i["id"] for i in r["items"]] == [str(m.K1.id)]
        # control: sin restriccion, K1 es la tercera por nombre (si no, el defecto no se veria)
        todas = _ok(client.get(f"{API}/money-accounts", headers=m.admin, params={"limit": 3}))
        assert [i["id"] for i in todas["items"]] == [str(m.K3.id), str(m.K2.id), str(m.K1.id)]


# ---------------------------------------------------------------------------
# T8 — C1: movimiento de otra cuenta = 404 en toda ruta por id
# ---------------------------------------------------------------------------

class TestT8LecturasPorId:

    def test_t8_k3_da_404_y_no_toca_el_disco(self, m, client, db_session, uploads):
        movs = _movs(m)
        mv3, mv1 = movs["K3"], movs["K1"]
        h = m.liquidador
        carpeta = uploads / "evidence" / str(m.org.id)
        archivos = sorted(p.name for p in carpeta.iterdir())
        assert len(archivos) == 2
        antes = _foto(db_session)

        llamadas = [
            ("GET", f"{MM}/{mv3['id']}", {}),
            ("GET", f"{MM}/by-number/{mv3['movement_number']}", {}),
            ("GET", f"{MM}/{mv3['id']}/evidence", {}),
            ("POST", f"{MM}/{mv3['id']}/evidence", {"files": {"file": ("x.png", PNG, "image/png")}}),
            ("DELETE", f"{MM}/{mv3['id']}/evidence", {}),
            ("POST", f"{MM}/{mv3['id']}/annul", {"json": {"reason": "Anulacion T8"}}),
            ("PATCH", f"{MM}/{mv3['id']}/classification",
             {"json": {"expense_category_id": str(m.EC2.id)}}),
        ]
        for req in llamadas:
            r = _send(client, h, req)
            assert r.status_code == 404, (req[0], req[1], r.status_code, r.text)
        assert sorted(p.name for p in carpeta.iterdir()) == archivos  # ni nuevo ni borrado
        assert _diff(antes, _foto(db_session)) == []

        # control con K1, el mismo usuario
        _ok(client.get(f"{MM}/{mv1['id']}", headers=h))
        _ok(client.get(f"{MM}/by-number/{mv1['movement_number']}", headers=h))
        assert client.get(f"{MM}/{mv1['id']}/evidence", headers=h).status_code == 200
        _ok(_evidence(client, h, mv1["id"]))
        _ok(client.delete(f"{MM}/{mv1['id']}/evidence", headers=h))
        _ok(client.patch(f"{MM}/{mv1['id']}/classification", headers=h,
                         json={"expense_category_id": str(m.EC2.id)}))
        _ok(client.post(f"{MM}/{mv1['id']}/annul", headers=h, json={"reason": "Anulacion T8"}))


# ---------------------------------------------------------------------------
# T9 — traslado entre cuentas (D2)
# ---------------------------------------------------------------------------

class TestT9Traslados:

    def _transfer(self, client, headers, src, dst):
        return client.post(f"{MM}/transfer", headers=headers, json={
            "amount": "1000", "source_account_id": str(src.id),
            "destination_account_id": str(dst.id), "date": _past(), "description": "T9"})

    def test_t9_exige_las_dos_cuentas(self, m, client, db_session):
        antes = _foto(db_session)
        _assert_listener_403(self._transfer(client, m.analista, m.K1, m.K3), m.K3.name)
        _assert_listener_403(self._transfer(client, m.analista, m.K3, m.K1), m.K3.name)
        assert _diff(antes, _foto(db_session)) == []
        _ok(self._transfer(client, m.analista, m.K1, m.K2), (201,))

    def test_t9_anular_un_traslado_que_cruza(self, m, client, db_session):
        """Al CREAR, cada pata hace su propio flush, asi que el de K3 lleva solo K3 y
        corta igual con «alguna» que con «todas» (P6 dejaba verde el test de arriba).
        ANULAR revierte las dos patas y commitea en UN flush: ahi se mide «todas»."""
        out = _ok(self._transfer(client, m.admin, m.K1, m.K3), (201,))
        antes = _foto(db_session)
        r = client.post(f"{MM}/{out['id']}/annul", headers=m.analista, json={"reason": "Anulacion T9"})
        _assert_listener_403(r, m.K3.name)
        assert _diff(antes, _foto(db_session)) == []


# ---------------------------------------------------------------------------
# T10 — movimientos sin cuenta (D3)
# ---------------------------------------------------------------------------

class TestT10SinCuenta:

    def test_t10_el_liquidador_crea_y_anula_los_sin_cuenta(self, m, client):
        h = m.liquidador
        creados = [
            _ok(client.post(f"{MM}/expense-accrual", headers=h, json={
                "third_party_id": str(m.L.id), "amount": "1000",
                "expense_category_id": str(m.EC.id), "date": _past(),
                "description": "causacion T10"}), (201,)),
            _ok(client.post(f"{MM}/tp-transfer", headers=h, json={
                "source_third_party_id": str(m.S.id), "destination_third_party_id": str(m.G.id),
                "amount": "1000", "date": _past(), "description": "cruce T10"}), (201,)),
            _ok(client.post(f"{MM}/tp-adjustment-debit", headers=h, json={
                "third_party_id": str(m.S.id), "amount": "1000", "adjustment_class": "loss",
                "date": _past(), "description": "ajuste debito T10"}), (201,)),
            _ok(client.post(f"{MM}/tp-adjustment-credit", headers=h, json={
                "third_party_id": str(m.S.id), "amount": "1000", "adjustment_class": "gain",
                "date": _past(), "description": "ajuste credito T10"}), (201,)),
        ]
        for mv in creados:
            assert mv["account_id"] is None
            _ok(client.post(f"{MM}/{mv['id']}/annul", headers=h, json={"reason": "Anulacion T10"}))


# ---------------------------------------------------------------------------
# T11 — sin contexto, el listener no actua
# ---------------------------------------------------------------------------

class TestT11SinContexto:

    def test_t11_servicio_directo_escribe_en_k3(self, m, db_session):
        """Scripts y seeds no pasan por un request: el listener no los mira.
        Fija que nadie lo vuelva fail-closed sin decidirlo."""
        from app.schemas.money_movement import ExpenseCreate
        from app.services.account_access import ACTOR_KEY
        from app.services.money_movement import money_movement

        assert ACTOR_KEY not in db_session.info
        mv = money_movement.create_expense(
            db=db_session,
            data=ExpenseCreate(amount=Decimal("1000"), expense_category_id=m.EC.id,
                               account_id=m.K3.id, description="script T11", date=_past()),
            organization_id=m.org.id, user_id=m.liquidador_user.id)
        assert mv.account_id == m.K3.id


# ---------------------------------------------------------------------------
# T12 — con alcance (Ingrid), la red sola tambien corta
# ---------------------------------------------------------------------------

class TestT12ConAlcance:

    def test_t12_sin_el_chequeo_explicito_el_listener_corta(self, m, client, db_session,
                                                           monkeypatch):
        m.org.settings = {"kg_ledger_enabled": True}
        GL = create_third_party_with_category(m.db, m.org.id, "Green Loop T", "service_provider")
        A = create_third_party_with_category(m.db, m.org.id, "Proveedor A (GL)",
                                             "material_supplier", collector_id=GL.id)
        rol = _role(m.db, m.org.id, "recolector_t", ["treasury.create_movements"])
        user, h = _member(m.db, m.org.id, "ingrid_t", rol.id, accounts=[m.K1.id])
        m.db.add(UserCollectorScope(organization_id=m.org.id, user_id=user.id, collector_id=GL.id))
        m.db.commit()

        def pago(acc):
            return client.post(f"{MM}/supplier-payment", headers=h, json={
                "supplier_id": str(A.id), "amount": "1000", "account_id": str(acc.id),
                "date": _past(), "description": "pago T12"})

        r = pago(m.K3)  # con el chequeo explicito: su 403 de siempre, sin nombre
        assert r.status_code == 403 and _detail(r) == "No tienes acceso a esta cuenta", r.text

        monkeypatch.setattr(mm_endpoint, "require_account_in_scope", lambda *a, **k: None)
        antes = _foto(db_session)
        _assert_listener_403(pago(m.K3), m.K3.name)
        assert _diff(antes, _foto(db_session)) == []
        _ok(pago(m.K1), (201,))


# ---------------------------------------------------------------------------
# T13 — el contexto carga al usuario en la sesion
# ---------------------------------------------------------------------------

class TestT13ElContextoLoCarga:

    def test_t13_account_actor_en_la_sesion_del_request(self, m, client, db_session):
        from app.services.account_access import ACTOR_KEY
        from tests.conftest import TestingSessionLocal

        sesiones = []

        def capturing_get_db():
            db = TestingSessionLocal()
            sesiones.append(db)
            try:
                yield db
            finally:
                db.close()

        su, su_headers = _member(m.db, m.org.id, "super_t", None, superuser=True)
        m.db.commit()
        app.dependency_overrides[get_db] = capturing_get_db

        _ok(client.get(f"{API}/money-accounts", headers=m.liquidador))
        actor = sesiones[-1].info[ACTOR_KEY]
        assert actor["user_id"] == m.liquidador_user.id
        assert actor["organization_id"] == m.org.id
        assert actor["is_admin"] is False

        _ok(client.get(f"{API}/money-accounts", headers=su_headers))
        assert sesiones[-1].info[ACTOR_KEY]["is_admin"] is True
        assert sesiones[-1].info[ACTOR_KEY]["user_id"] == su.id


# ---------------------------------------------------------------------------
# T14 — cambia SOLO la cuenta (C1 de QA 2)
# ---------------------------------------------------------------------------

class TestT14SoloLaCuenta:

    def test_t14_patch_delete_post_de_cuentas(self, m, client, db_session):
        m.db.execute(update(MoneyAccount).where(MoneyAccount.id == m.K3.id).values(current_balance=0))
        m.db.commit()
        h = m.cuentas
        antes = _foto(db_session)
        _assert_listener_403(client.patch(f"{API}/money-accounts/{m.K3.id}", headers=h,
                                          json={"name": "AAA RENOMBRADA"}), m.K3.name)
        _assert_listener_403(client.delete(f"{API}/money-accounts/{m.K3.id}", headers=h), m.K3.name)
        _assert_listener_403(client.post(f"{API}/money-accounts", headers=h,
                                         json={"name": "CCC NUEVA", "account_type": "cash"}),
                             "CCC NUEVA")
        assert _diff(antes, _foto(db_session)) == []
        m.db.expire_all()
        k3 = m.db.get(MoneyAccount, m.K3.id)
        assert (k3.name, k3.is_active) == ("AAA CAJA AJENA", True)
        _ok(client.patch(f"{API}/money-accounts/{m.K1.id}", headers=h,
                         json={"name": "ZZZ CAJA PROPIA 2"}))


# ---------------------------------------------------------------------------
# T15 — updates de movimientos y de cuentas, en el listener (C4)
# ---------------------------------------------------------------------------

class TestT15UpdatesEnElListener:

    def _sesion(self, m):
        from app.services.account_access import register_actor
        from tests.conftest import TestingSessionLocal
        db = TestingSessionLocal()
        register_actor(db, {"organization_id": m.org.id, "user_id": m.liquidador_user.id,
                            "is_admin": False, "collector_scope_id": None})
        return db

    def _flush_403(self, db, account_name):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            db.flush()
        assert exc.value.status_code == 403 and f"«{account_name}»" in str(exc.value.detail)
        db.rollback()

    def test_t15_cambiar_la_cuenta_mira_la_vieja_y_la_nueva(self, m, client):
        mv3 = _expense(client, m.admin, m, m.K3)
        mv1 = _expense(client, m.admin, m, m.K1)
        db = self._sesion(m)
        try:
            mov = db.get(MoneyMovement, mv3["id"])
            mov.account_id = m.K1.id          # K3 -> K1: la VIEJA no es suya
            self._flush_403(db, m.K3.name)
            mov = db.get(MoneyMovement, mv1["id"])
            mov.account_id = m.K3.id          # K1 -> K3: la NUEVA no es suya
            self._flush_403(db, m.K3.name)
        finally:
            db.close()

    def _nuevo(self, m, account) -> MoneyMovement:
        from app.utils.dates import business_today_noon
        return MoneyMovement(
            organization_id=m.org.id, movement_number=999999, movement_type="expense",
            amount=Decimal("1000"), date=business_today_noon(), description="por relacion",
            status="confirmed", account=account)

    # Por la RELACION `account` (PC1 de QA 2): la FK se sincroniza dentro del flush,
    # asi que una cuenta asignada por la relacion no esta en `account_id` cuando corre
    # el listener. Una celda por test, para que el plantado de P17 se lea por celda.

    def test_t15_relacion_insert_con_k3(self, m, client):
        db = self._sesion(m)
        try:
            db.add(self._nuevo(m, db.get(MoneyAccount, m.K3.id)))
            self._flush_403(db, m.K3.name)
        finally:
            db.close()

    def test_t15_relacion_de_k1_a_k3(self, m, client):
        mv1 = _expense(client, m.admin, m, m.K1)
        db = self._sesion(m)
        try:
            db.get(MoneyMovement, mv1["id"]).account = db.get(MoneyAccount, m.K3.id)
            self._flush_403(db, m.K3.name)
        finally:
            db.close()

    def test_t15_relacion_de_k3_a_k1(self, m, client):
        """Con P17 queda verde a proposito: `account_id` todavia tiene la vieja (K3)."""
        mv3 = _expense(client, m.admin, m, m.K3)
        db = self._sesion(m)
        try:
            db.get(MoneyMovement, mv3["id"]).account = db.get(MoneyAccount, m.K1.id)
            self._flush_403(db, m.K3.name)
        finally:
            db.close()

    def test_t15_relacion_control_insert_con_k1(self, m, client):
        db = self._sesion(m)
        try:
            db.add(self._nuevo(m, db.get(MoneyAccount, m.K1.id)))
            db.flush()                        # la cuenta es suya: no hay 403
            assert db.execute(select(MoneyMovement.account_id).where(
                MoneyMovement.movement_number == 999999,
                MoneyMovement.organization_id == m.org.id)).scalar_one() == m.K1.id
            db.rollback()
        finally:
            db.close()

    def test_t15_sin_cambio_neto_no_hay_403(self, m, client):
        mv3 = _expense(client, m.admin, m, m.K3)
        db = self._sesion(m)
        try:
            mov = db.get(MoneyMovement, mv3["id"])
            mov.account_id = mov.account_id
            mov.description = mov.description
            cuenta = db.get(MoneyAccount, m.K3.id)
            cuenta.name = cuenta.name
            db.flush()                        # sin cambio neto: no hay 403
            db.rollback()
        finally:
            db.close()
