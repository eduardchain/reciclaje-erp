"""
Tests SAC — Entradas y Salidas «de control» (estibas, tubulares, electrolito
a $0): plan docs/planes/plan-sac-documentos-control.md v1.2 §8, T1–T25.

Johana (24-nov): «no tenerlas en cuenta. Pero por el consecutivo si necesito
dejarlas en el registro del sistema». Un documento de control deja numero y
remision, y CERO efectos: ni inventario, ni kg, ni plata, ni saldos.

Las afirmaciones de efectos se hacen por CONTEO de filas antes y despues en las
6 tablas (T3/T13), no mirando el status: un cierre que creara una compra vacia
pasaria cualquier assert sobre el estado.
"""
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import func, select

from app.core.security import create_access_token, get_password_hash
from app.models.inbound_order import InboundOrder, InboundOrderLine, InboundOrderPurchase
from app.models.inventory_adjustment import InventoryAdjustment
from app.models.inventory_movement import InventoryMovement
from app.models.kg_ledger import KgLedgerMovement
from app.models.material_cost_history import MaterialCostHistory
from app.models.money_movement import MoneyMovement
from app.models.permission import Permission
from app.models.purchase import Purchase
from app.models.role import Role, RolePermission
from app.models.service_tariff import ServiceTariff
from app.models.user import OrganizationMember, User, UserCollectorScope
from app.utils.dates import business_today
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    create_material,
    create_material_category,
    create_warehouse,
)
from tests.reparto_slots import con_slots

API = "/api/v1"
INBOUND = f"{API}/inbound-orders"
PROFILES = f"{API}/material-kg-profiles"
DISPATCHES = f"{API}/control-dispatches"
REMISSIONS = f"{API}/remissions"
PURCHASES = f"{API}/purchases"
SALES = f"{API}/sales"
ADJUST = f"{API}/inventory/adjustments"

EFFECT_TABLES = (
    Purchase, InventoryMovement, KgLedgerMovement, MoneyMovement,
    InventoryAdjustment, MaterialCostHistory,
)


# ---------------------------------------------------------------------------
# Fixtures y helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _flag(db_session, test_organization):
    test_organization.settings = {"kg_ledger_enabled": True}
    db_session.commit()


@pytest.fixture
def wh(db_session, test_organization):
    w = create_warehouse(db_session, test_organization.id, "Circunvalar DC")
    db_session.commit()
    return w


def _supplier(db, org_id, name, behavior="material_supplier"):
    tp = create_third_party_with_category(db, org_id, name, behavior)
    db.commit()
    return tp


@pytest.fixture
def sup1(db_session, test_organization):
    return _supplier(db_session, test_organization.id, "Proveedor Uno DC")


@pytest.fixture
def sup2(db_session, test_organization):
    return _supplier(db_session, test_organization.id, "Proveedor Dos DC")


def _mat(db, org_id, code, unit="kg"):
    cat = create_material_category(db, org_id, f"Cat {code}")
    mat = create_material(db, org_id, code, f"Material {code}", cat.id)
    mat.default_unit = unit
    db.commit()
    return mat


def _profile(client, h, mat, *, willard_world="none", lead_product="none", compra_regular=True):
    r = client.put(f"{PROFILES}/{mat.id}", headers=h, json={
        "compra_regular": compra_regular, "willard_world": willard_world,
        "lead_product": lead_product,
    })
    return r


def _mark(client, h, mat, value=True, expect=200):
    r = client.put(f"{PROFILES}/{mat.id}/control", headers=h, json={"control_only": value})
    assert r.status_code == expect, r.text
    return r.json()


@pytest.fixture
def mat_val(db_session, test_organization, client, org_headers):
    mat = _mat(db_session, test_organization.id, "MOTO-DC")
    assert _profile(client, org_headers, mat).status_code == 200
    return mat


@pytest.fixture
def mat_est(db_session, test_organization, client, org_headers):
    mat = _mat(db_session, test_organization.id, "ESTIBAS-DC", unit="unidad")
    _mark(client, org_headers, mat)
    return mat


@pytest.fixture
def mat_tub(db_session, test_organization, client, org_headers):
    mat = _mat(db_session, test_organization.id, "TUBULAR-DC")
    _mark(client, org_headers, mat)
    return mat


def _past(days=2):
    return (business_today() - timedelta(days=days)).isoformat()


def _line(mat, qty, weight="100"):
    body = {"material_id": str(mat.id), "quantity": str(qty)}
    if weight is not None:
        body["scale_weight_kg"] = str(weight)
    return body


def _capture(client, h, wh, lines, expect=201, date=None, **extra):
    r = client.post(INBOUND, headers=h, json={
        "inbound_type": "purchase", "warehouse_id": str(wh.id),
        "date": date or _past(), "lines": lines, **extra,
    })
    assert r.status_code == expect, r.text
    return r.json()


def _review(client, h, oid, expect=200):
    r = client.post(f"{INBOUND}/{oid}/review", headers=h)
    assert r.status_code == expect, r.text
    return r.json()


def _alloc(tp, qty, price="1000"):
    return {"third_party_id": str(tp.id), "quantity": str(qty), "unit_price": str(price)}


def _liq_line(mat, allocs, **extra):
    return {"material_id": str(mat.id), "allocations": allocs, **extra}


def _liquidate(client, h, oid, lines, expect=200, **extra):
    r = client.post(f"{INBOUND}/{oid}/liquidate", headers=h,
                    json=con_slots({"lines": lines, **extra}))
    assert r.status_code == expect, r.text
    return r.json()


def _close(client, h, oid, expect=200):
    r = client.post(f"{INBOUND}/{oid}/close", headers=h)
    assert r.status_code == expect, r.text
    return r.json()


def _reopen(client, h, oid, expect=200):
    r = client.post(f"{INBOUND}/{oid}/reopen", headers=h)
    assert r.status_code == expect, r.text
    return r.json()


def _get(client, h, oid):
    r = client.get(f"{INBOUND}/{oid}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _counts(db) -> dict:
    db.expire_all()
    return {t.__tablename__: db.execute(select(func.count()).select_from(t)).scalar_one()
            for t in EFFECT_TABLES}


def _purchases_of(db, oid):
    db.expire_all()
    return db.execute(
        select(Purchase)
        .join(InboundOrderPurchase, InboundOrderPurchase.purchase_id == Purchase.id)
        .where(InboundOrderPurchase.inbound_order_id == UUID(str(oid)))
        .order_by(Purchase.purchase_number)
    ).scalars().all()


def _role(db, org_id, name, codes) -> Role:
    role = Role(organization_id=org_id, name=name, display_name=name, is_system_role=False)
    db.add(role)
    db.flush()
    perms = db.execute(select(Permission).where(Permission.code.in_(codes))).scalars().all()
    assert len(perms) == len(set(codes)), (sorted(codes), sorted(p.code for p in perms))
    for p in perms:
        db.add(RolePermission(role_id=role.id, permission_id=p.id))
    db.flush()
    return role


def _member(db, org_id, tag, codes, scope=None) -> dict:
    role = _role(db, org_id, f"rol_{tag}", codes)
    user = User(email=f"{tag}@example.com", hashed_password=get_password_hash("pass1234"),
                full_name=tag, is_active=True)
    db.add(user)
    db.flush()
    db.add(OrganizationMember(user_id=user.id, organization_id=org_id, role_id=role.id))
    if scope is not None:
        db.add(UserCollectorScope(organization_id=org_id, user_id=user.id, collector_id=scope))
    db.commit()
    return {"Authorization": f"Bearer {create_access_token(data={'sub': str(user.id)})}",
            "X-Organization-ID": str(org_id)}


def _dispatch(client, h, wh, lines, remission="16300", expect=201, **extra):
    r = client.post(DISPATCHES, headers=h, json={
        "date": _past(), "warehouse_id": str(wh.id), "remission_number": remission,
        "lines": lines, **extra,
    })
    assert r.status_code == expect, r.text
    return r.json()


def _dline(mat, qty="10"):
    return {"material_id": str(mat.id), "quantity": str(qty)}


# ---------------------------------------------------------------------------
# T1, T2 — la marca de control
# ---------------------------------------------------------------------------

class TestMarca:
    def test_t1_marcar_crea_el_perfil_si_falta(
        self, client, org_headers, db_session, test_organization,
    ):
        mat = _mat(db_session, test_organization.id, "ELECTROLITO-DC")
        assert client.get(f"{PROFILES}/{mat.id}", headers=org_headers).status_code in (200, 404)
        body = _mark(client, org_headers, mat)
        assert body["control_only"] is True
        assert body["willard_world"] == "none" and body["lead_product"] == "none"
        leido = client.get(f"{PROFILES}/{mat.id}", headers=org_headers).json()
        assert leido["control_only"] is True

    def test_t1_marcar_un_willard_o_un_plomo_da_422_que_lo_nombra(
        self, client, org_headers, db_session, test_organization,
    ):
        drosses = _mat(db_session, test_organization.id, "DROSS-DC")
        assert _profile(client, org_headers, drosses, willard_world="drosses",
                        compra_regular=False).status_code == 200
        r = client.put(f"{PROFILES}/{drosses.id}/control", headers=org_headers,
                       json={"control_only": True})
        assert r.status_code == 422, r.text
        assert "DROSS-DC" in r.json()["detail"] and "Willard" in r.json()["detail"]

        plomo = _mat(db_session, test_organization.id, "PLOMO-DC")
        assert _profile(client, org_headers, plomo, lead_product="crudo").status_code == 200
        r = client.put(f"{PROFILES}/{plomo.id}/control", headers=org_headers,
                       json={"control_only": True})
        assert r.status_code == 422, r.text
        assert "plomo" in r.json()["detail"]

    def test_t2_el_upsert_no_borra_la_marca(self, client, org_headers, mat_est):
        """#103 D4: el upsert reemplaza el perfil ENTERO; si `control_only`
        viajara ahi con default, guardar la clasificacion la borraria."""
        r = _profile(client, org_headers, mat_est, compra_regular=False)
        assert r.status_code == 200, r.text
        assert r.json()["control_only"] is True
        assert client.get(f"{PROFILES}/{mat_est.id}", headers=org_headers).json()["control_only"] is True

    def test_t2_upsert_con_mundo_willard_sobre_marcado_da_422(self, client, org_headers, mat_tub):
        r = _profile(client, org_headers, mat_tub, willard_world="drosses", compra_regular=False)
        assert r.status_code == 422, r.text
        assert "TUBULAR-DC" in r.json()["detail"] and "control" in r.json()["detail"]

    def test_t2_el_upsert_rechaza_control_only_en_su_payload(self, client, org_headers, mat_val):
        """La marca tiene su endpoint; el upsert es extra=forbid."""
        r = client.put(f"{PROFILES}/{mat_val.id}", headers=org_headers, json={
            "compra_regular": True, "willard_world": "none", "lead_product": "none",
            "control_only": True,
        })
        assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# T3, T4, T5, T8, T9, T18 — cerrar sin valor
# ---------------------------------------------------------------------------

class TestCerrar:
    def test_t3_cerrar_desde_reviewed_y_desde_draft_sin_efectos(
        self, client, org_headers, db_session, wh, mat_est, mat_tub,
    ):
        rev = _capture(client, org_headers, wh, [_line(mat_est, 40, weight=None)])
        _review(client, org_headers, rev["id"])
        draft = _capture(client, org_headers, wh, [_line(mat_tub, 25)])
        antes = _counts(db_session)
        for oid in (rev["id"], draft["id"]):
            body = _close(client, org_headers, oid)
            assert body["status"] == "closed"
            assert body["display_status"] == "closed"
            assert body["closed_at"] is not None
            assert body["closed_by_name"]
            assert body["is_control_only"] is True
            assert all(ln["is_control"] for ln in body["lines"])
        assert _counts(db_session) == antes
        assert _purchases_of(db_session, rev["id"]) == []

    def test_t4_cerrar_una_mixta_da_422_que_nombra_el_material_con_valor(
        self, client, org_headers, db_session, wh, mat_est, mat_val,
    ):
        o = _capture(client, org_headers, wh, [_line(mat_est, 40), _line(mat_val, 100)])
        _review(client, org_headers, o["id"])
        r = client.post(f"{INBOUND}/{o['id']}/close", headers=org_headers)
        assert r.status_code == 422, r.text
        assert "MOTO-DC" in r.json()["detail"]
        assert "ESTIBAS-DC" not in r.json()["detail"]
        assert _get(client, org_headers, o["id"])["status"] == "reviewed"

    def test_t4_liquidar_una_solo_de_control_manda_a_cerrar(
        self, client, org_headers, db_session, wh, mat_est, sup1,
    ):
        o = _capture(client, org_headers, wh, [_line(mat_est, 40)])
        _review(client, org_headers, o["id"])
        antes = _counts(db_session)
        # El schema exige al menos una linea; aun repartiendo la estiba, el
        # servidor responde por la Entrada entera («cierrela»), no por la linea.
        r = client.post(f"{INBOUND}/{o['id']}/liquidate", headers=org_headers,
                        json=con_slots({"lines": [_liq_line(mat_est, [_alloc(sup1, 40)])]}))
        assert r.status_code == 422, r.text
        assert "cierrela sin valor" in r.json()["detail"]
        assert _counts(db_session) == antes

    def test_t5_paridad_del_filtro_con_el_campo(
        self, client, org_headers, db_session, wh, mat_est, mat_val, sup1,
    ):
        """Extiende `test_filter_parity_with_field` (ciclo C) con `closed`: para
        cada valor del filtro, los ids == los del campo. Vive aca porque los
        fixtures de ciclo C no tienen material de control."""
        draft = _capture(client, org_headers, wh, [_line(mat_val, 100)])
        rev = _capture(client, org_headers, wh, [_line(mat_val, 100)])
        _review(client, org_headers, rev["id"])
        liq = _capture(client, org_headers, wh, [_line(mat_val, 100)])
        _review(client, org_headers, liq["id"])
        _liquidate(client, org_headers, liq["id"], [_liq_line(mat_val, [_alloc(sup1, 100)])])
        ann = _capture(client, org_headers, wh, [_line(mat_val, 100)])
        assert client.post(f"{INBOUND}/{ann['id']}/annul", headers=org_headers,
                           json={"reason": "prueba"}).status_code == 200
        cerr = _capture(client, org_headers, wh, [_line(mat_est, 40)])
        _close(client, org_headers, cerr["id"])

        items = client.get(INBOUND, headers=org_headers, params={"limit": 100}).json()["items"]
        valores = ("registered", "reviewed", "liquidated", "annulled", "closed")
        por_campo = {v: {i["id"] for i in items if i["display_status"] == v} for v in valores}
        assert por_campo["closed"] == {cerr["id"]}
        assert {draft["id"], rev["id"], liq["id"], ann["id"]} <= set().union(*por_campo.values())
        for v in valores:
            filtrado = client.get(INBOUND, headers=org_headers,
                                  params={"display_status": v, "limit": 100}).json()["items"]
            assert {i["id"] for i in filtrado} == por_campo[v], v
        # Las bandejas (status registered / reviewed) no traen la cerrada
        for st in ("draft", "reviewed"):
            bandeja = client.get(INBOUND, headers=org_headers,
                                 params={"status": st, "limit": 100}).json()["items"]
            assert cerr["id"] not in {i["id"] for i in bandeja}
        assert client.get(INBOUND, headers=org_headers,
                          params={"status": "closed"}).json()["total"] == 1

    def test_r1_willard_no_se_cierra(self, client, org_headers, db_session, wh, mat_est):
        """O2 de QA 2. La Willard se fabrica por ORM sobre una captura: la rama
        de R1 mira solo `inbound_type` y va antes que cualquier otra."""
        o = _capture(client, org_headers, wh, [_line(mat_est, 40)])
        row = db_session.get(InboundOrder, UUID(o["id"]))
        row.inbound_type = "willard"
        db_session.commit()
        r = client.post(f"{INBOUND}/{o['id']}/close", headers=org_headers)
        assert r.status_code == 400, r.text
        assert "Willard" in r.json()["detail"]
        assert _get(client, org_headers, o["id"])["status"] == "draft"

    @pytest.mark.parametrize("estado,texto", [
        ("liquidated", "esta liquidada"),
        ("annulled", "esta anulada"),
        ("closed", "ya esta cerrada sin valor"),
    ])
    def test_r3_estados_que_no_se_cierran(
        self, client, org_headers, db_session, wh, mat_est, mat_val, sup1, estado, texto,
    ):
        """O2 de QA 2: cada estado llega por su camino REAL (liquidar, anular,
        cerrar), no por ORM."""
        if estado == "liquidated":
            o = _capture(client, org_headers, wh, [_line(mat_val, 100)])
            _review(client, org_headers, o["id"])
            _liquidate(client, org_headers, o["id"], [_liq_line(mat_val, [_alloc(sup1, 100)])])
        else:
            o = _capture(client, org_headers, wh, [_line(mat_est, 40)])
            if estado == "annulled":
                assert client.post(f"{INBOUND}/{o['id']}/annul", headers=org_headers,
                                   json={"reason": "error"}).status_code == 200
            else:
                _close(client, org_headers, o["id"])
        r = client.post(f"{INBOUND}/{o['id']}/close", headers=org_headers)
        assert r.status_code == 400, r.text
        assert texto in r.json()["detail"]
        assert _get(client, org_headers, o["id"])["status"] == estado

    def test_r7c_liquidar_una_cerrada_manda_a_reabrir(
        self, client, org_headers, db_session, wh, mat_est, sup1,
    ):
        o = _capture(client, org_headers, wh, [_line(mat_est, 40)])
        _close(client, org_headers, o["id"])
        antes = _counts(db_session)
        r = client.post(f"{INBOUND}/{o['id']}/liquidate", headers=org_headers,
                        json=con_slots({"lines": [_liq_line(mat_est, [_alloc(sup1, 40)])]}))
        assert r.status_code == 400, r.text
        assert "reabrala para liquidarla" in r.json()["detail"]
        assert _counts(db_session) == antes

    def test_t8_reabrir_vuelve_al_estado_de_antes(
        self, client, org_headers, wh, mat_est,
    ):
        rev = _capture(client, org_headers, wh, [_line(mat_est, 40)])
        _review(client, org_headers, rev["id"])
        _close(client, org_headers, rev["id"])
        body = _reopen(client, org_headers, rev["id"])
        assert body["status"] == "reviewed"
        assert body["closed_at"] is None and body["closed_by_name"] is None

        draft = _capture(client, org_headers, wh, [_line(mat_est, 10)])
        _close(client, org_headers, draft["id"])
        assert _reopen(client, org_headers, draft["id"])["status"] == "draft"

        r = client.post(f"{INBOUND}/{draft['id']}/reopen", headers=org_headers)
        assert r.status_code == 400, r.text

    def test_t9_editar_anular_y_desliquidar_una_cerrada(
        self, client, org_headers, db_session, wh, mat_est,
    ):
        o = _capture(client, org_headers, wh, [_line(mat_est, 40)])
        _close(client, org_headers, o["id"])
        for body in ({"lines": [_line(mat_est, 41)]}, {"date": _past(3)}):
            r = client.patch(f"{INBOUND}/{o['id']}", headers=org_headers, json=body)
            assert r.status_code == 422, r.text
            assert "reabrirla" in r.json()["detail"]
        r = client.patch(f"{INBOUND}/{o['id']}", headers=org_headers,
                         json={"notes": "estibas devueltas", "remission_number": "16310"})
        assert r.status_code == 200, r.text
        assert r.json()["remission_number"] == "16310"
        assert r.json()["status"] == "closed"

        r = client.post(f"{INBOUND}/{o['id']}/unliquidate", headers=org_headers)
        assert r.status_code == 400, r.text

        antes = _counts(db_session)
        r = client.post(f"{INBOUND}/{o['id']}/annul", headers=org_headers,
                        json={"reason": "capturada por error"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "annulled"
        assert _counts(db_session) == antes

    def test_t18_desliquidada_con_compras_vivas_no_se_cierra(
        self, client, org_headers, db_session, wh, mat_val, mat_est, sup1,
    ):
        """C1 de QA 2: una Entrada desliquidada conserva sus compras registered
        en el puente. Cerrarla las dejaria vivas y congeladas (#134)."""
        o = _capture(client, org_headers, wh, [_line(mat_val, 100), _line(mat_est, 40)])
        _review(client, org_headers, o["id"])
        _liquidate(client, org_headers, o["id"], [_liq_line(mat_val, [_alloc(sup1, 100)])])
        assert client.post(f"{INBOUND}/{o['id']}/unliquidate",
                           headers=org_headers).status_code == 200
        # El material con valor pasa a ser de control: ahora es «solo control»
        _mark(client, org_headers, mat_val)
        compras = _purchases_of(db_session, o["id"])
        assert [p.status for p in compras] == ["registered"]

        r = client.post(f"{INBOUND}/{o['id']}/close", headers=org_headers)
        assert r.status_code == 422, r.text
        assert f"#{compras[0].purchase_number}" in r.json()["detail"]
        assert _get(client, org_headers, o["id"])["status"] == "reviewed"
        assert [p.status for p in _purchases_of(db_session, o["id"])] == ["registered"]

    def test_t18_residuo_de_costo_sin_compras_vivas_no_se_cierra(
        self, client, org_headers, db_session, wh, mat_est,
    ):
        o = _capture(client, org_headers, wh, [_line(mat_est, 40)])
        _review(client, org_headers, o["id"])
        order = db_session.get(InboundOrder, UUID(o["id"]))
        order.annul_cost_adjustment = Decimal("125.50")
        db_session.commit()
        r = client.post(f"{INBOUND}/{o['id']}/close", headers=org_headers)
        assert r.status_code == 422, r.text
        assert "diferencia de costo" in r.json()["detail"]
        assert _get(client, org_headers, o["id"])["status"] == "reviewed"


# ---------------------------------------------------------------------------
# T6, T6b, T6c, T7, T10 — la Entrada mixta
# ---------------------------------------------------------------------------

class TestMixta:
    def test_t6_liquidar_sin_las_lineas_de_control(
        self, client, org_headers, db_session, wh, mat_val, mat_est, sup1,
    ):
        o = _capture(client, org_headers, wh, [_line(mat_val, 100), _line(mat_est, 40)])
        _review(client, org_headers, o["id"])
        antes = _counts(db_session)
        body = _liquidate(client, org_headers, o["id"],
                          [_liq_line(mat_val, [_alloc(sup1, 100, "1000")])])
        assert body["status"] == "liquidated"
        # C2 de QA 2 — control positivo de `_counts`: los tests de «cero
        # efectos» comparan `_counts == antes`, y eso solo prueba algo si
        # `_counts` VE lo que la app escribe. Aca la app si escribe: crece.
        despues = _counts(db_session)
        assert despues["purchases"] > antes["purchases"]
        assert despues["inventory_movements"] > antes["inventory_movements"]
        assert body["is_control_only"] is False
        assert {ln["material_code"]: ln["is_control"] for ln in body["lines"]} == {
            "MOTO-DC": False, "ESTIBAS-DC": True,
        }
        compras = _purchases_of(db_session, o["id"])
        assert len(compras) == 1
        assert {ln.material_id for ln in compras[0].lines} == {mat_val.id}
        assert compras[0].total_amount == Decimal("100000.00")
        ajustes = db_session.execute(select(InventoryAdjustment).where(
            InventoryAdjustment.inbound_order_id == UUID(o["id"]))).scalars().all()
        assert ajustes == []

    def test_t6_mandar_el_material_de_control_en_el_reparto_da_422(
        self, client, org_headers, db_session, wh, mat_val, mat_est, sup1,
    ):
        o = _capture(client, org_headers, wh, [_line(mat_val, 100), _line(mat_est, 40)])
        _review(client, org_headers, o["id"])
        antes = _counts(db_session)
        r = client.post(f"{INBOUND}/{o['id']}/liquidate", headers=org_headers, json=con_slots({
            "lines": [_liq_line(mat_val, [_alloc(sup1, 100)]),
                      _liq_line(mat_est, [_alloc(sup1, 40, "100")])],
        }))
        assert r.status_code == 422, r.text
        assert "ESTIBAS-DC" in str(r.json()["detail"])
        assert _counts(db_session) == antes

    def test_t6b_reliquidar_tras_marcar_conserva_la_compra_sin_la_linea(
        self, client, org_headers, db_session, wh, mat_val, sup1, test_organization,
    ):
        """C1: el slot conserva otras lineas -> la compra existente se EDITA
        sin la linea de control; su numero no cambia."""
        cal = _mat(db_session, test_organization.id, "CAJAS-DC")
        assert _profile(client, org_headers, cal).status_code == 200
        o = _capture(client, org_headers, wh, [_line(mat_val, 100), _line(cal, 50)])
        _review(client, org_headers, o["id"])
        _liquidate(client, org_headers, o["id"], [
            _liq_line(mat_val, [_alloc(sup1, 100, "1000")]),
            _liq_line(cal, [_alloc(sup1, 50, "200")]),
        ])
        antes = _purchases_of(db_session, o["id"])
        assert len(antes) == 1
        numero = antes[0].purchase_number
        assert client.post(f"{INBOUND}/{o['id']}/unliquidate",
                           headers=org_headers).status_code == 200
        _mark(client, org_headers, cal)
        _liquidate(client, org_headers, o["id"],
                   [_liq_line(mat_val, [_alloc(sup1, 100, "1000")])])
        despues = _purchases_of(db_session, o["id"])
        vivas = [p for p in despues if p.status != "cancelled"]
        assert [p.purchase_number for p in vivas] == [numero]
        assert {ln.material_id for ln in vivas[0].lines} == {mat_val.id}
        assert vivas[0].total_amount == Decimal("100000.00")

    def test_t6c_slot_que_tenia_solo_el_control_queda_cancelado(
        self, client, org_headers, db_session, wh, mat_val, sup1, sup2, test_organization,
    ):
        cal = _mat(db_session, test_organization.id, "CAJAS2-DC")
        assert _profile(client, org_headers, cal).status_code == 200
        o = _capture(client, org_headers, wh, [_line(mat_val, 100), _line(cal, 50)])
        _review(client, org_headers, o["id"])
        _liquidate(client, org_headers, o["id"], [
            _liq_line(mat_val, [_alloc(sup1, 100, "1000")]),
            _liq_line(cal, [_alloc(sup2, 50, "200")]),
        ])
        assert len(_purchases_of(db_session, o["id"])) == 2
        assert client.post(f"{INBOUND}/{o['id']}/unliquidate",
                           headers=org_headers).status_code == 200
        _mark(client, org_headers, cal)
        body = _liquidate(client, org_headers, o["id"],
                          [_liq_line(mat_val, [_alloc(sup1, 100, "1000")])])
        compras = {p.supplier_id: p for p in _purchases_of(db_session, o["id"])}
        assert compras[sup2.id].status == "cancelled"
        assert compras[sup1.id].status == "liquidated"
        assert any("reparto" in w for w in body["warnings"]), body["warnings"]

    def test_t7_comision_sin_el_control(
        self, client, org_headers, db_session, wh, mat_val, mat_est, test_organization,
        test_user,
    ):
        from app.services.inbound_order import inbound_order_service
        db_session.add(ServiceTariff(
            organization_id=test_organization.id, tariff_code="comision_green_loop",
            unit="per_kg_material", unit_price_cop=Decimal("100"), kg_per_unit=Decimal("14"),
            created_by=test_user.id,
        ))
        db_session.commit()
        mixta = _capture(client, org_headers, wh, [_line(mat_val, 100), _line(mat_est, 40)])
        sola = _capture(client, org_headers, wh, [_line(mat_val, 100)])
        db_session.expire_all()
        c_mixta = inbound_order_service.suggested_collector_commission(
            db_session, db_session.get(InboundOrder, UUID(mixta["id"])), test_organization.id)
        c_sola = inbound_order_service.suggested_collector_commission(
            db_session, db_session.get(InboundOrder, UUID(sola["id"])), test_organization.id)
        assert c_sola == Decimal("10000.00")
        assert c_mixta == c_sola  # 40 estibas x 14 kg x $100 no suman

    def test_t10_bascula_no_se_exige_al_control(
        self, client, org_headers, wh, mat_val, mat_est,
    ):
        o = _capture(client, org_headers, wh, [_line(mat_val, 100), _line(mat_est, 40, weight=None)])
        assert _review(client, org_headers, o["id"])["status"] == "reviewed"

        unidad_con_valor = _capture(
            client, org_headers, wh,
            [_line(mat_est, 40, weight=None)],
        )
        _mark(client, org_headers, mat_est, value=False)
        r = client.post(f"{INBOUND}/{unidad_con_valor['id']}/review", headers=org_headers)
        assert r.status_code in (400, 422), r.text
        assert "ESTIBAS-DC" in r.json()["detail"]


# ---------------------------------------------------------------------------
# T11, T14, T17 — alcance, flag y permisos
# ---------------------------------------------------------------------------

class TestAccesos:
    def test_t11_ingrid_no_cierra_ni_reabre_ni_ve_salidas(
        self, client, org_headers, db_session, test_organization, wh, mat_est, mat_val,
    ):
        gl = _supplier(db_session, test_organization.id, "Green Loop DC", "service_provider")
        prov = _supplier(db_session, test_organization.id, "Proveedor GL DC")
        prov.collector_id = gl.id
        db_session.commit()
        ingrid = _member(db_session, test_organization.id, "ingrid-dc", [
            "purchases.view", "purchases.liquidate", "purchases.cancel", "purchases.review",
            "sales.view", "sales.create",
        ], scope=gl.id)
        o = _capture(client, org_headers, wh, [_line(mat_est, 40)], collector_id=str(gl.id))
        for path in ("close", "reopen"):
            r = client.post(f"{INBOUND}/{o['id']}/{path}", headers=ingrid)
            assert r.status_code == 403, r.text
        assert client.get(DISPATCHES, headers=ingrid).status_code == 403
        assert client.get(REMISSIONS, headers=ingrid).status_code == 403

        # Su liquidacion con require_full_allocation (9g) no cuenta la estiba
        mix = _capture(client, org_headers, wh, [_line(mat_val, 100), _line(mat_est, 40)],
                       collector_id=str(gl.id))
        _review(client, org_headers, mix["id"])
        body = _liquidate(client, ingrid, mix["id"],
                          [_liq_line(mat_val, [_alloc(prov, 100, "1000")])])
        assert body["status"] == "liquidated"

    def test_t14_sin_flag_403(self, client, org_headers, db_session, test_organization,
                              wh, mat_est):
        o = _capture(client, org_headers, wh, [_line(mat_est, 40)])
        test_organization.settings = {"kg_ledger_enabled": False}
        db_session.commit()
        assert client.post(f"{INBOUND}/{o['id']}/close", headers=org_headers).status_code == 403
        assert client.put(f"{PROFILES}/{mat_est.id}/control", headers=org_headers,
                          json={"control_only": False}).status_code == 403
        assert client.get(DISPATCHES, headers=org_headers).status_code == 403
        assert client.get(REMISSIONS, headers=org_headers).status_code == 403

    def test_t17_permisos_con_control_positivo(
        self, client, org_headers, db_session, test_organization, wh, mat_est,
    ):
        o = _capture(client, org_headers, wh, [_line(mat_est, 40)])
        # close exige purchases.liquidate
        solo_ver = _member(db_session, test_organization.id, "ver-compras-dc", ["purchases.view"])
        assert client.get(f"{INBOUND}/{o['id']}", headers=solo_ver).status_code == 200
        assert client.post(f"{INBOUND}/{o['id']}/close", headers=solo_ver).status_code == 403
        # /control-dispatches: crear exige sales.create
        ver_ventas = _member(db_session, test_organization.id, "ver-ventas-dc", ["sales.view"])
        assert client.get(DISPATCHES, headers=ver_ventas).status_code == 200
        r = client.post(DISPATCHES, headers=ver_ventas, json={
            "date": _past(), "warehouse_id": str(wh.id), "remission_number": "1",
            "lines": [_dline(mat_est)]})
        assert r.status_code == 403, r.text
        # /remissions: AND de purchases.view y sales.view
        assert client.get(REMISSIONS, headers=solo_ver).status_code == 403
        assert client.get(REMISSIONS, headers=ver_ventas).status_code == 403
        las_dos = _member(db_session, test_organization.id, "ver-las-dos-dc",
                          ["purchases.view", "sales.view"])
        assert client.get(REMISSIONS, headers=las_dos).status_code == 200


# ---------------------------------------------------------------------------
# T12, T13, T15, T19 — la Salida de control
# ---------------------------------------------------------------------------

class TestSalidaDeControl:
    def test_t12_crear_y_leer_numero_propio(
        self, client, org_headers, wh, mat_est, mat_tub, mat_val,
    ):
        e1 = _capture(client, org_headers, wh, [_line(mat_val, 100)])
        e2 = _capture(client, org_headers, wh, [_line(mat_val, 100)])
        assert e2["order_number"] == e1["order_number"] + 1
        d1 = _dispatch(client, org_headers, wh, [_dline(mat_est, 40), _dline(mat_tub, "12.5")],
                       remission="  16400 ")
        assert d1["dispatch_number"] == 1
        assert d1["remission_number"] == "16400"
        assert d1["status"] == "registered" and d1["created_by_name"]
        assert {ln["material_code"] for ln in d1["lines"]} == {"ESTIBAS-DC", "TUBULAR-DC"}
        d2 = _dispatch(client, org_headers, wh, [_dline(mat_est)], remission="16401")
        assert d2["dispatch_number"] == 2
        e3 = _capture(client, org_headers, wh, [_line(mat_val, 100)])
        assert e3["order_number"] == e2["order_number"] + 1
        leido = client.get(f"{DISPATCHES}/{d1['id']}", headers=org_headers).json()
        assert leido["dispatch_number"] == 1 and len(leido["lines"]) == 2

    def test_t12_material_sin_marca_da_422_que_lo_nombra(self, client, org_headers, wh,
                                                         mat_val, mat_est):
        r = client.post(DISPATCHES, headers=org_headers, json={
            "date": _past(), "warehouse_id": str(wh.id), "remission_number": "1",
            "lines": [_dline(mat_est), _dline(mat_val)]})
        assert r.status_code == 422, r.text
        assert "MOTO-DC" in r.json()["detail"] and "ESTIBAS-DC" not in r.json()["detail"]

    def test_t12_bodega_de_transito_se_rechaza(
        self, client, org_headers, db_session, test_organization, mat_est,
    ):
        """El plan dice 422; el guard compartido de transito
        (`validate_not_transit_warehouse`, el de compras/ventas/ajustes)
        responde 400. Desviacion declarada: se reusa el guard, no se copia."""
        test_organization.settings = {"kg_ledger_enabled": True,
                                      "two_step_transfers_enabled": True}
        dest = create_warehouse(db_session, test_organization.id, "Juan Mina DC")
        tr = create_warehouse(db_session, test_organization.id, "Transito DC")
        tr.is_transit = True
        tr.transit_target_warehouse_id = dest.id
        db_session.commit()
        r = client.post(DISPATCHES, headers=org_headers, json={
            "date": _past(), "warehouse_id": str(tr.id), "remission_number": "1",
            "lines": [_dline(mat_est)]})
        assert r.status_code == 400, r.text
        assert "tránsito" in r.json()["detail"]

    def test_t12_entidad_de_sistema_y_misma_linea_dos_veces(
        self, client, org_headers, db_session, test_organization, wh, mat_est,
    ):
        tp = _supplier(db_session, test_organization.id, "[Impuestos] IVA DC", "liability")
        tp.is_system_entity = True
        db_session.commit()
        r = client.post(DISPATCHES, headers=org_headers, json={
            "date": _past(), "warehouse_id": str(wh.id), "remission_number": "1",
            "third_party_id": str(tp.id), "lines": [_dline(mat_est)]})
        assert r.status_code == 422, r.text
        r = client.post(DISPATCHES, headers=org_headers, json={
            "date": _past(), "warehouse_id": str(wh.id), "remission_number": "1",
            "lines": [_dline(mat_est), _dline(mat_est, 3)]})
        assert r.status_code == 422, r.text
        assert "ESTIBAS-DC" in r.json()["detail"]

    def test_t13_crear_editar_y_anular_sin_efectos(
        self, client, org_headers, db_session, test_organization, wh, mat_est, mat_tub,
    ):
        cliente = _supplier(db_session, test_organization.id, "Cliente DC", "customer")
        antes = _counts(db_session)
        d = _dispatch(client, org_headers, wh, [_dline(mat_est, 40)],
                      third_party_id=str(cliente.id))
        assert d["third_party_name"] == "Cliente DC"
        r = client.patch(f"{DISPATCHES}/{d['id']}", headers=org_headers, json={
            "lines": [_dline(mat_tub, 5)], "notes": "cambio", "third_party_id": None})
        assert r.status_code == 200, r.text
        assert [ln["material_code"] for ln in r.json()["lines"]] == ["TUBULAR-DC"]
        assert r.json()["third_party_id"] is None
        r = client.post(f"{DISPATCHES}/{d['id']}/annul", headers=org_headers,
                        json={"reason": "por error"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "annulled" and r.json()["annulled_by_name"]
        assert _counts(db_session) == antes
        # Anulada: no se edita ni se re-anula
        assert client.patch(f"{DISPATCHES}/{d['id']}", headers=org_headers,
                            json={"notes": "x"}).status_code == 400
        assert client.post(f"{DISPATCHES}/{d['id']}/annul", headers=org_headers,
                           json={"reason": "otra vez"}).status_code == 400

    def test_t15_secuencia_registrada_con_llave_estable(self, test_organization):
        import zlib
        from app.utils.advisory_locks import RANK, SEQUENCES, sequence_lock_key
        assert SEQUENCES["control_dispatch_number"] == (
            "control_dispatches", "dispatch_number", None)
        assert RANK["control_dispatch_number"] == 15
        assert len(set(RANK.values())) == len(RANK)
        org = test_organization.id
        assert sequence_lock_key(org, "control_dispatch_number") == zlib.crc32(
            f"{org}:control_dispatch_number".encode("utf-8"))

    @pytest.mark.parametrize("valor", [None, "", "   "])
    def test_t19_remision_obligatoria(self, client, org_headers, wh, mat_est, valor):
        body = {"date": _past(), "warehouse_id": str(wh.id), "lines": [_dline(mat_est)]}
        if valor is not None:
            body["remission_number"] = valor
        assert client.post(DISPATCHES, headers=org_headers, json=body).status_code == 422

    @pytest.mark.parametrize("valor", [None, "", "   "])
    def test_t19_el_patch_no_la_deja_vaciar(self, client, org_headers, wh, mat_est, valor):
        d = _dispatch(client, org_headers, wh, [_dline(mat_est)], remission="16500")
        r = client.patch(f"{DISPATCHES}/{d['id']}", headers=org_headers,
                         json={"remission_number": valor})
        assert r.status_code == 422, r.text
        assert client.get(f"{DISPATCHES}/{d['id']}",
                          headers=org_headers).json()["remission_number"] == "16500"


# ---------------------------------------------------------------------------
# T16 — D5: Ventas y Compras directas no llevan control (PAR con y sin flag)
# ---------------------------------------------------------------------------

class TestSalidaDeControlBordes:
    def test_o5_date_to_con_la_fecha_sola_incluye_ese_dia(self, client, org_headers, wh, mat_est):
        """O5 de QA 2: `date_to=<dia>` sin hora incluye lo de ese dia (la fecha
        de negocio es mediodia UTC; un datetime pelado cortaba a las 00:00)."""
        dia = _past(2)
        d = _dispatch(client, org_headers, wh, [_dline(mat_est)], remission="16330")
        r = client.get(DISPATCHES, headers=org_headers, params={"date_from": dia, "date_to": dia})
        assert r.status_code == 200, r.text
        assert [i["id"] for i in r.json()["items"]] == [d["id"]]
        # control positivo: hasta el dia ANTERIOR no la trae
        antes = (business_today() - timedelta(days=3)).isoformat()
        r = client.get(DISPATCHES, headers=org_headers, params={"date_to": antes})
        assert r.status_code == 200 and r.json()["items"] == []
        # el talonario con la misma regla
        b = _book(client, org_headers, date_from=dia, date_to=dia)
        assert [i["remission"] for i in b["items"] if i["kind"] == "doc"] == ["16330"]
        assert _book(client, org_headers, date_to=antes)["items"] == []

    def test_o7_cantidad_que_redondea_a_cero_da_422_no_500(
        self, client, org_headers, db_session, wh, mat_est,
    ):
        """O7 de QA 2: `gt=0` valida ANTES de redondear a la escala de la
        columna; 0,00004 se guardaria en 0 y el CHECK daria 500."""
        antes = _counts(db_session)
        r = client.post(DISPATCHES, headers=org_headers, json={
            "date": _past(), "warehouse_id": str(wh.id), "remission_number": "16340",
            "lines": [_dline(mat_est, "0.00004")]})
        assert r.status_code == 422, r.text
        assert "ESTIBAS-DC" in r.json()["detail"] and "queda en 0" in r.json()["detail"]
        r = client.post(DISPATCHES, headers=org_headers, json={
            "date": _past(), "warehouse_id": str(wh.id), "remission_number": "16340",
            "lines": [{**_dline(mat_est, "5"), "scale_weight_kg": "0.0004"}]})
        assert r.status_code == 422, r.text
        assert "peso de bascula" in r.json()["detail"]
        assert client.get(DISPATCHES, headers=org_headers).json()["total"] == 0
        assert _counts(db_session) == antes
        # control positivo: 0,00005 redondea HALF_UP a 0,0001 (la regla de PG) y pasa
        d = _dispatch(client, org_headers, wh, [_dline(mat_est, "0.00005")], remission="16341")
        assert Decimal(d["lines"][0]["quantity"]) == Decimal("0.0001")


def _venta(client, h, customer, wh, mat):
    return client.post(SALES, headers=h, json={
        "customer_id": str(customer.id), "warehouse_id": str(wh.id), "date": _past(),
        "lines": [{"material_id": str(mat.id), "quantity": "10", "unit_price": "100"}],
        "commissions": [], "auto_liquidate": False,
    })


def _compra(client, h, sup, wh, mat):
    return client.post(PURCHASES, headers=h, json={
        "supplier_id": str(sup.id), "date": _past(),
        "lines": [{"material_id": str(mat.id), "warehouse_id": str(wh.id),
                   "quantity": "10", "unit_price": "100"}],
    })


class TestD5:
    @pytest.fixture
    def cliente(self, db_session, test_organization):
        return _supplier(db_session, test_organization.id, "Cliente D5", "customer")

    def test_t16_con_flag_venta_y_compra_dan_400(
        self, client, org_headers, wh, mat_est, mat_val, sup1, cliente,
    ):
        r = _venta(client, org_headers, cliente, wh, mat_est)
        assert r.status_code == 400, r.text
        assert "ESTIBAS-DC" in r.json()["detail"] and "Salidas de control" in r.json()["detail"]
        r = _compra(client, org_headers, sup1, wh, mat_est)
        assert r.status_code == 400, r.text
        assert "ESTIBAS-DC" in r.json()["detail"] and "Entrada" in r.json()["detail"]
        # control positivo: el material con valor pasa
        assert _venta(client, org_headers, cliente, wh, mat_val).status_code == 201
        assert _compra(client, org_headers, sup1, wh, mat_val).status_code == 201

    def test_t16_editar_metiendo_control_da_400(
        self, client, org_headers, wh, mat_est, mat_val, sup1, cliente,
    ):
        v = _venta(client, org_headers, cliente, wh, mat_val).json()
        r = client.patch(f"{SALES}/{v['id']}", headers=org_headers, json={
            "lines": [{"material_id": str(mat_est.id), "quantity": "1", "unit_price": "1"}]})
        assert r.status_code == 400, r.text
        # O3 de QA 2: el texto, para que otro 400 futuro no lo tape
        assert "ESTIBAS-DC" in r.json()["detail"] and "Salidas de control" in r.json()["detail"]
        c = _compra(client, org_headers, sup1, wh, mat_val).json()
        r = client.patch(f"{PURCHASES}/{c['id']}", headers=org_headers, json={
            "lines": [{"material_id": str(mat_est.id), "warehouse_id": str(wh.id),
                       "quantity": "1", "unit_price": "1"}]})
        assert r.status_code == 400, r.text
        assert "ESTIBAS-DC" in r.json()["detail"] and "Entrada" in r.json()["detail"]

    def test_t16_sin_flag_el_guard_es_inerte(
        self, client, org_headers, db_session, test_organization, wh, mat_est, sup1, cliente,
    ):
        test_organization.settings = {"kg_ledger_enabled": False}
        db_session.commit()
        assert _venta(client, org_headers, cliente, wh, mat_est).status_code == 201
        assert _compra(client, org_headers, sup1, wh, mat_est).status_code == 201


# ---------------------------------------------------------------------------
# T20, T23 — remision repetida y la llave unica
# ---------------------------------------------------------------------------

class TestRemisionRepetida:
    def test_t20_salida_con_la_remision_de_una_entrada_avisa_por_http(
        self, client, org_headers, wh, mat_est, mat_val,
    ):
        e = _capture(client, org_headers, wh, [_line(mat_val, 100)], remission_number="16300")
        d = _dispatch(client, org_headers, wh, [_dline(mat_est)], remission="0016300")
        assert len(d["warnings"]) == 1
        assert f"Entrada #{e['order_number']}" in d["warnings"][0]

    def test_t20_entrada_con_la_remision_de_una_salida_avisa(
        self, client, org_headers, wh, mat_est, mat_val,
    ):
        d = _dispatch(client, org_headers, wh, [_dline(mat_est)], remission="16301")
        e = _capture(client, org_headers, wh, [_line(mat_val, 100)], remission_number=" 16301")
        assert any(f"Salida de control #{d['dispatch_number']}" in w for w in e["warnings"])

    def test_t20_contra_una_anulada_no_avisa_y_un_update_igual_tampoco(
        self, client, org_headers, wh, mat_est, mat_val,
    ):
        e = _capture(client, org_headers, wh, [_line(mat_val, 100)], remission_number="16302")
        assert client.post(f"{INBOUND}/{e['id']}/annul", headers=org_headers,
                           json={"reason": "error"}).status_code == 200
        d = _dispatch(client, org_headers, wh, [_dline(mat_est)], remission="16302")
        assert d["warnings"] == []
        # Otra salida con la misma -> avisa; reenviar la misma en un PATCH no
        d2 = _dispatch(client, org_headers, wh, [_dline(mat_est)], remission="16302")
        assert d2["warnings"]
        r = client.patch(f"{DISPATCHES}/{d2['id']}", headers=org_headers,
                         json={"remission_number": "16302", "notes": "x"})
        assert r.status_code == 200 and r.json()["warnings"] == []
        # Cambiarla a una libre no avisa; cambiarla a una ocupada si
        r = client.patch(f"{DISPATCHES}/{d2['id']}", headers=org_headers,
                         json={"remission_number": "16399"})
        assert r.json()["warnings"] == []
        r = client.patch(f"{DISPATCHES}/{d2['id']}", headers=org_headers,
                         json={"remission_number": "16302"})
        assert r.json()["warnings"]

    def test_t20_update_de_la_entrada_avisa_por_http(
        self, client, org_headers, wh, mat_est, mat_val,
    ):
        """C1 de QA 2: el aviso del PATCH de la Entrada, leido de la RESPUESTA
        HTTP (leccion de #100), en sus tres casos."""
        e1 = _capture(client, org_headers, wh, [_line(mat_val, 100)], remission_number="16300")
        d = _dispatch(client, org_headers, wh, [_dline(mat_est)], remission="16310")
        e2 = _capture(client, org_headers, wh, [_line(mat_val, 100)], remission_number="16320")
        assert e2["warnings"] == []
        # 1. A una ocupada: el aviso nombra el documento
        r = client.patch(f"{INBOUND}/{e2['id']}", headers=org_headers,
                         json={"remission_number": "16310"})
        assert r.status_code == 200, r.text
        assert len(r.json()["warnings"]) == 1
        assert f"Salida de control #{d['dispatch_number']}" in r.json()["warnings"][0]
        # 2. Reenviar la misma: sin aviso
        r = client.patch(f"{INBOUND}/{e2['id']}", headers=org_headers,
                         json={"remission_number": "16310", "notes": "x"})
        assert r.status_code == 200, r.text
        assert r.json()["warnings"] == []
        # 3. «0016300» contra «16300»: la normalizacion es la de SQL tambien aca
        r = client.patch(f"{INBOUND}/{e2['id']}", headers=org_headers,
                         json={"remission_number": "0016300"})
        assert r.status_code == 200, r.text
        assert len(r.json()["warnings"]) == 1
        assert f"Entrada #{e1['order_number']}" in r.json()["warnings"][0]

    def test_t23_paridad_de_la_llave_en_el_conjunto_de_frontera(
        self, client, org_headers, wh, mat_val, mat_est,
    ):
        """C1 de QA 2: UNA llave SQL decide «misma remision» para el aviso, la
        marca «Repetida» y el orden. Se mide por HTTP en los tres."""
        base = {}
        for rem in ("0012", "012a", "R-12", "12.0", "16.300", "١٢",
                    "", "   ", "12345678901234567890"):
            body = _capture(client, org_headers, wh, [_line(mat_val, 1)], remission_number=rem)
            base[rem] = body
            assert body["warnings"] == [], (rem, body["warnings"])

        # Aviso: «12» y « 12 » chocan con «0012»; «r-12 » con «R-12»
        for rem, otra in (("12", "0012"), (" 12 ", "0012"), ("r-12 ", "R-12")):
            d = _dispatch(client, org_headers, wh, [_dline(mat_est)], remission=rem)
            assert d["warnings"] and f"Entrada #{base[otra]['order_number']}" in d["warnings"][0], rem
        # Texto distinto de numero: ninguno de estos choca con 12 ni con 16300
        d = _dispatch(client, org_headers, wh, [_dline(mat_est)], remission="16300")
        assert d["warnings"] == []
        # Dos vacias no son repetidas entre si
        assert _capture(client, org_headers, wh, [_line(mat_val, 1)],
                        remission_number="  ")["warnings"] == []

        vista = client.get(REMISSIONS, headers=org_headers, params={"order": "asc"}).json()
        docs = [i for i in vista["items"] if i["kind"] == "doc"]
        rep = {(i["doc_type"], i["remission"]): i["duplicated"] for i in docs}
        for rem in ("0012", "R-12"):
            assert rep[("inbound", rem)] is True, rem
        for rem in ("12", " 12 ", "r-12 "):
            assert rep[("control_dispatch", rem.strip())] is True, rem
        for rem in ("012a", "12.0", "16.300", "١٢", "12345678901234567890"):
            assert rep[("inbound", rem)] is False, rem
        assert rep[("control_dispatch", "16300")] is False
        # Las vacias no salen en la vista y se cuentan en el encabezado
        assert all((i["remission"] or "").strip() for i in docs)
        assert vista["inbound_without_remission"] == 3
        # Orden (asc): numericas por valor (el de 20 digitos al final de ellas),
        # despues el texto
        nums = [i["remission"] for i in docs if i["remission"] and i["remission"].isascii()
                and i["remission"].isdigit()]
        assert nums[-1] == "12345678901234567890"
        primera_texto = next(n for n, i in enumerate(docs)
                             if not (i["remission"].isascii() and i["remission"].isdigit()))
        assert all(not (i["remission"].isascii() and i["remission"].isdigit())
                   for i in docs[primera_texto:])
        assert "١٢" in [i["remission"] for i in docs[primera_texto:]]


# ---------------------------------------------------------------------------
# T21, T22, T24, T25 — la vista del talonario
# ---------------------------------------------------------------------------

def _book(client, h, **params):
    r = client.get(REMISSIONS, headers=h, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _shape(items):
    """Lista compacta: ('doc', remision) o ('gap', desde, hasta, n)."""
    return [("gap", i["gap_from"], i["gap_to"], i["count"]) if i["kind"] == "gap"
            else ("doc", i["remission"]) for i in items]


class TestTalonario:
    def test_t21_vista_intercalada_con_hueco_anulada_texto_y_repetida(
        self, client, org_headers, db_session, test_organization, wh, mat_val, mat_est, sup1,
    ):
        _capture(client, org_headers, wh, [_line(mat_val, 1)], remission_number="16300")
        d = _dispatch(client, org_headers, wh, [_dline(mat_est)], remission="16303")
        e304 = _capture(client, org_headers, wh, [_line(mat_val, 1)], remission_number="16304")
        assert client.post(f"{INBOUND}/{e304['id']}/annul", headers=org_headers,
                           json={"reason": "x"}).status_code == 200
        _dispatch(client, org_headers, wh, [_dline(mat_est)], remission="16305")
        _capture(client, org_headers, wh, [_line(mat_val, 1)], remission_number="16305")
        _capture(client, org_headers, wh, [_line(mat_val, 1)], remission_number="R-77")
        _capture(client, org_headers, wh, [_line(mat_val, 1)])  # sin remision
        # O3: una Salida de Plomo con remision 16301 NO tapa el hueco
        from app.models.willard_delivery import WillardDelivery
        db_session.add(WillardDelivery(
            organization_id=test_organization.id, delivery_number=1, series="venta",
            delivery_type="venta", warehouse_id=wh.id, third_party_id=sup1.id,
            date=business_today(), remission_number="16301", status="draft",
        ))
        db_session.commit()

        v = _book(client, org_headers, order="asc")
        assert _shape(v["items"]) == [
            ("doc", "16300"), ("gap", "16301", "16302", "2"), ("doc", "16303"),
            ("doc", "16304"), ("doc", "16305"), ("doc", "16305"), ("doc", "R-77"),
        ]
        docs = [i for i in v["items"] if i["kind"] == "doc"]
        assert docs[1]["doc_type"] == "control_dispatch" and docs[1]["doc_id"] == d["id"]
        assert docs[2]["status"] == "annulled" and docs[2]["duplicated"] is False
        assert docs[3]["duplicated"] is True and docs[4]["duplicated"] is True
        assert {docs[3]["doc_type"], docs[4]["doc_type"]} == {"inbound", "control_dispatch"}
        assert docs[0]["materials"] == "MOTO-DC" and docs[1]["materials"] == "ESTIBAS-DC"
        assert v["inbound_without_remission"] == 1
        assert v["documents"] == 6
        # Descendente: los tramos tambien se invierten, y el texto va al
        # FINAL tambien aca (O1 de QA 2: solo en el talonario; Entradas #117
        # conserva el texto arriba en desc)
        desc = _book(client, org_headers, order="desc")
        assert _shape(desc["items"])[:1] == [("doc", "16305")]
        assert _shape(desc["items"])[-1:] == [("doc", "R-77")]
        assert ("gap", "16301", "16302", "2") in _shape(desc["items"])

    def test_t22_el_hueco_entre_paginas_sale_igual(self, client, org_headers, wh, mat_val):
        for rem in ("100", "101", "104", "105"):
            _capture(client, org_headers, wh, [_line(mat_val, 1)], remission_number=rem)
        todo = _shape(_book(client, org_headers, order="asc")["items"])
        assert todo == [("doc", "100"), ("doc", "101"), ("gap", "102", "103", "2"),
                        ("doc", "104"), ("doc", "105")]
        p1 = _shape(_book(client, org_headers, order="asc", skip=0, limit=2)["items"])
        p2 = _shape(_book(client, org_headers, order="asc", skip=2, limit=3)["items"])
        assert p1 + p2 == todo

    def test_t24_hueco_medido_contra_la_org(self, client, org_headers, db_session, wh, mat_val):
        dic = (business_today().replace(day=1) - timedelta(days=1)).isoformat()
        nov = (business_today().replace(day=1) - timedelta(days=40)).isoformat()
        a = _capture(client, org_headers, wh, [_line(mat_val, 1)], remission_number="16304", date=dic)
        b = _capture(client, org_headers, wh, [_line(mat_val, 1)], remission_number="16306", date=dic)
        assert a and b
        # O5 de QA 2: la fecha SOLA, como la manda la pantalla; el servidor la
        # combina con el final del dia (las fechas de negocio son mediodia UTC).
        rango = {"date_from": dic, "date_to": dic, "order": "asc"}
        # Sin la 16305 en ningun lado: hay hueco
        assert ("gap", "16305", "16305", "1") in _shape(_book(client, org_headers, **rango)["items"])
        # La 16305 fechada en otro mes lo tapa, aunque no se muestre
        e305 = _capture(client, org_headers, wh, [_line(mat_val, 1)],
                        remission_number="16305", date=nov)
        assert _shape(_book(client, org_headers, **rango)["items"]) == [
            ("doc", "16304"), ("doc", "16306")]
        # Anulada tambien lo tapa (cubre su numero)
        assert client.post(f"{INBOUND}/{e305['id']}/annul", headers=org_headers,
                           json={"reason": "x"}).status_code == 200
        assert _shape(_book(client, org_headers, **rango)["items"]) == [
            ("doc", "16304"), ("doc", "16306")]

    def test_t25_busqueda_sin_huecos_y_rango_numerico(self, client, org_headers, wh, mat_val):
        for rem in ("16290", "16300", "16303", "16320", "R-16301"):
            _capture(client, org_headers, wh, [_line(mat_val, 1)], remission_number=rem)
        busq = _book(client, org_headers, search="163", order="asc")
        assert all(i["kind"] == "doc" for i in busq["items"])
        assert {i["remission"] for i in busq["items"]} == {"16300", "16303", "16320", "R-16301"}
        r = _shape(_book(client, org_headers, remission_from=16300, remission_to=16310,
                         order="asc")["items"])
        # N1: el texto no sale con el rango; los huecos de dentro si, los de fuera no
        assert r == [("doc", "16300"), ("gap", "16301", "16302", "2"), ("doc", "16303")]

    def test_t25b_remision_de_20_digitos_exacta(self, client, org_headers, wh, mat_val):
        """Encontrado en el e2e (dev tiene una remision de 20 digitos): pasa
        2^53, asi que un hueco entregado como number llega redondeado al
        navegador. El hueco y su conteo viajan como TEXTO, exactos, y el
        filtro desde/hasta acepta los 20 digitos sin perder precision."""
        for rem in ("12345678901234567890", "12345678901234567893"):
            _capture(client, org_headers, wh, [_line(mat_val, 1)], remission_number=rem)
        v = _book(client, org_headers, order="asc")
        assert _shape(v["items"]) == [
            ("doc", "12345678901234567890"),
            ("gap", "12345678901234567891", "12345678901234567892", "2"),
            ("doc", "12345678901234567893"),
        ]
        # Control: el par vecino como float de 64 bits es el MISMO numero, o
        # sea que como number estos dos limites serian indistinguibles.
        assert float("12345678901234567891") == float("12345678901234567892")
        solo = _shape(_book(client, org_headers, order="asc",
                            remission_from="12345678901234567893",
                            remission_to="12345678901234567893")["items"])
        assert solo == [("doc", "12345678901234567893")]


class TestTipoControl:
    """Plan v1.3.2 §11.2 y §11.6: tipo «Control» deducido. El campo
    `is_control_only` vale solo sin efectos (C1 de QA 2, CONTROL_ONLY_STATUSES)
    y el filtro `control_only` espeja ese mismo predicado."""

    def _escenario(self, client, h, db, wh, mat_est, mat_tub, mat_val, sup1, test_organization):
        ids = {}
        ids["ctrl_draft"] = _capture(client, h, wh, [_line(mat_est, 40)])["id"]
        ids["ctrl_closed"] = _capture(client, h, wh, [_line(mat_tub, 10)])["id"]
        _close(client, h, ids["ctrl_closed"])
        ids["mixta"] = _capture(client, h, wh, [_line(mat_val, 100), _line(mat_est, 5)])["id"]
        ids["compra"] = _capture(client, h, wh, [_line(mat_val, 100)])["id"]
        # Willard por ORM sobre una captura (como R1): nunca es de control
        w = _capture(client, h, wh, [_line(mat_val, 50)])
        row = db.get(InboundOrder, UUID(w["id"]))
        row.inbound_type = "willard"
        row.status = "confirmed"
        ids["willard"] = w["id"]
        # N2 de QA 2: sin lineas no es solo de control (por ORM; la API exige 1)
        vacia = _capture(client, h, wh, [_line(mat_est, 3)])
        for ln in db.execute(select(InboundOrderLine).where(
                InboundOrderLine.inbound_order_id == UUID(vacia["id"]))).scalars():
            db.delete(ln)
        ids["sin_lineas"] = vacia["id"]
        db.commit()
        # C1 de QA 2, por el camino real: liquidada a $1 con el material SIN la
        # marca, y el material marcado DESPUES (el caso de G-prod 2)
        mat_liq = _mat(db, test_organization.id, "ESTIBAS-LIQ", unit="unidad")
        assert _profile(client, h, mat_liq).status_code == 200
        liq = _capture(client, h, wh, [_line(mat_liq, 40)])
        _review(client, h, liq["id"])
        _liquidate(client, h, liq["id"], [_liq_line(mat_liq, [_alloc(sup1, 40, price="1")])])
        _mark(client, h, mat_liq)
        ids["liq_a_1"] = liq["id"]
        ann = _capture(client, h, wh, [_line(mat_est, 7)])
        assert client.post(f"{INBOUND}/{ann['id']}/annul", headers=h,
                           json={"reason": "prueba"}).status_code == 200
        ids["ctrl_anulada"] = ann["id"]
        return ids

    def test_t26_paridad_del_filtro_control_only_con_el_campo(
        self, client, org_headers, db_session, wh, mat_est, mat_tub, mat_val, sup1,
        test_organization,
    ):
        ids = self._escenario(client, org_headers, db_session, wh, mat_est, mat_tub,
                              mat_val, sup1, test_organization)
        todas = client.get(INBOUND, headers=org_headers, params={"limit": 100}).json()["items"]
        campo = {i["id"]: i["is_control_only"] for i in todas}
        assert set(ids.values()) <= set(campo)
        por_campo_true = {k for k, v in campo.items() if v}
        por_campo_false = {k for k, v in campo.items() if not v}
        # Guarda anti-vacuidad (#110): las dos ramas traen algo
        assert por_campo_true and por_campo_false
        for valor, esperado in (("true", por_campo_true), ("false", por_campo_false)):
            filtrado = client.get(INBOUND, headers=org_headers,
                                  params={"control_only": valor, "limit": 100}).json()
            assert {i["id"] for i in filtrado["items"]} == esperado, valor
            assert filtrado["total"] == len(esperado), valor
        # Por nombre: que es de control y que no
        assert por_campo_true == {ids["ctrl_draft"], ids["ctrl_closed"]}
        for k in ("mixta", "compra", "willard", "sin_lineas", "liq_a_1", "ctrl_anulada"):
            assert ids[k] in por_campo_false, k
        # C1: la liquidada a $1 sigue con su compra viva y su total
        liq = next(i for i in todas if i["id"] == ids["liq_a_1"])
        assert liq["display_status"] == "liquidated"
        assert liq["is_control_only"] is False
        vivas = [c for c in liq["purchases"] if c["status"] != "cancelled"]
        assert len(vivas) == 1 and vivas[0]["total_amount"] == 40.0
        # ... aunque todas sus lineas ya son de control (la marca se lee al momento)
        assert all(ln["is_control"] for ln in _get(client, org_headers, ids["liq_a_1"])["lines"])

    def test_t27_compra_regular_excluye_el_control(
        self, client, org_headers, db_session, wh, mat_est, mat_tub, mat_val, sup1,
        test_organization,
    ):
        ids = self._escenario(client, org_headers, db_session, wh, mat_est, mat_tub,
                              mat_val, sup1, test_organization)
        compra = client.get(INBOUND, headers=org_headers, params={
            "inbound_type": "purchase", "control_only": "false", "limit": 100}).json()["items"]
        got = {i["id"] for i in compra}
        assert {ids["mixta"], ids["compra"], ids["liq_a_1"]} <= got
        assert not ({ids["ctrl_draft"], ids["ctrl_closed"], ids["willard"]} & got)
        assert all(not i["is_control_only"] and i["inbound_type"] == "purchase" for i in compra)
        # El filtro Control combinado con la pestana «Cerradas sin valor»
        cerradas = client.get(INBOUND, headers=org_headers, params={
            "control_only": "true", "display_status": "closed", "limit": 100}).json()["items"]
        assert {i["id"] for i in cerradas} == {ids["ctrl_closed"]}
        # «Compra regular» en la pestana «Cerradas sin valor»: vacio
        assert client.get(INBOUND, headers=org_headers, params={
            "inbound_type": "purchase", "control_only": "false",
            "display_status": "closed"}).json()["total"] == 0
