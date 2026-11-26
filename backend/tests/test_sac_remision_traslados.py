"""
Tests SAC — la remision en los traslados, el talonario con tres fuentes y el
PATCH de la remision: plan docs/planes/plan-sac-remision-traslados.md v1.3 +
adenda 1 (§6 y §12).

La remision del traslado sale del MISMO talonario de las Entradas (Q-75): es
obligatoria al despachar (tambien intra-sede), se avisa si se repite (D8) y los
traslados entran a `GET /remissions` como tercera fuente con la misma
`remission_key`. Todo se lee por HTTP: un aviso se prueba en la respuesta y un
efecto con tablas, no con el estado (leccion de #100/#141).
"""
import itertools
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import inspect, select

from app.core.security import create_access_token, get_password_hash
from app.models.exception_task import DiscrepancyTask
from app.models.inventory_adjustment import InventoryAdjustment
from app.models.inventory_movement import InventoryMovement
from app.models.kg_ledger import KgLedgerAccount, KgLedgerMovement
from app.models.material import Material
from app.models.material_cost_history import MaterialCostHistory
from app.models.money_movement import MoneyMovement
from app.models.permission import Permission
from app.models.role import Role, RolePermission
from app.models.service_tariff import ServiceTariff
from app.models.transfer import Transfer, TransferLine
from app.models.user import OrganizationMember, User, UserCollectorScope
from app.utils.dates import business_today
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    create_material,
    create_material_category,
    create_warehouse,
)

API = "/api/v1"
TRANSFERS = f"{API}/transfers"
INBOUND = f"{API}/inbound-orders"
PROFILES = f"{API}/material-kg-profiles"
DISPATCHES = f"{API}/control-dispatches"
REMISSIONS = f"{API}/remissions"
FORMULAS = f"{API}/material-conversion-formulas"
ADJUST = f"{API}/inventory/adjustments"

SEED_DATE = "2026-07-01T12:00:00"
DISPATCH_DATE = "2026-07-10T12:00:00"
RECEIPT_DATE = "2026-07-12T12:00:00"


# ---------------------------------------------------------------------------
# Fixtures y helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _flags(db_session, test_organization):
    test_organization.settings = {
        "kg_ledger_enabled": True,
        "two_step_transfers_enabled": True,
        "internal_maquila_enabled": True,
    }
    db_session.commit()


def _wh(db, org_id, name):
    w = create_warehouse(db, org_id, name)
    db.commit()
    return w


@pytest.fixture
def wh_cv(db_session, test_organization):
    return _wh(db_session, test_organization.id, "Circunvalar RT")


@pytest.fixture
def wh_jm(db_session, test_organization):
    return _wh(db_session, test_organization.id, "Juan Mina RT")


@pytest.fixture
def wh_mol(db_session, test_organization, wh_cv):
    """Molino: misma sede que Circunvalar (traslado intra-sede, un solo salto)."""
    w = _wh(db_session, test_organization.id, "Molino RT")
    w.sede_warehouse_id = wh_cv.id
    db_session.commit()
    return w


@pytest.fixture
def wh_transit(db_session, test_organization, wh_jm):
    w = _wh(db_session, test_organization.id, "JM-TRANSITO RT")
    w.is_transit = True
    w.is_receiving = False
    w.transit_target_warehouse_id = wh_jm.id
    db_session.commit()
    return w


@pytest.fixture
def intersede_account(db_session, test_organization):
    acc = KgLedgerAccount(
        organization_id=test_organization.id, code="INTERSEDE",
        display_name="Intersede CV/BOG → JM", account_type="intersede", is_active=True,
    )
    db_session.add(acc)
    db_session.commit()
    return acc


@pytest.fixture
def maquila_tariff(db_session, test_organization, test_user):
    db_session.add(ServiceTariff(
        organization_id=test_organization.id, tariff_code="maquila_intersede_cv_jm",
        unit_price_cop=Decimal("1500.00"), unit="per_kg_lead", created_by=test_user.id,
    ))
    db_session.commit()


def _mat(db, org_id, code, unit="kg"):
    cat = create_material_category(db, org_id, f"Cat {code}")
    mat = create_material(db, org_id, code, f"Material {code}", cat.id)
    mat.default_unit = unit
    db.commit()
    return mat


@pytest.fixture
def mat_contrib(db_session, test_organization, client, org_headers, wh_cv):
    """Aportante (formula 50%) con 100 kg @ $1.000 en Circunvalar. El `increase`
    escribe tambien un MCH (control positivo de `material_cost_histories`)."""
    mat = _mat(db_session, test_organization.id, "DROSS-RT")
    r = client.post(FORMULAS, headers=org_headers, json={
        "material_id": str(mat.id), "formula_type": "drosses_to_lead",
        "parameters": {"lead_percentage": 0.5}})
    assert r.status_code == 201, r.text
    r = client.post(f"{ADJUST}/increase", headers=org_headers, json={
        "material_id": str(mat.id), "warehouse_id": str(wh_cv.id), "quantity": 100,
        "unit_cost": 1000, "date": SEED_DATE, "reason": "Seed stock test remision traslados"})
    assert r.status_code in (200, 201), r.text
    return mat


@pytest.fixture
def mat_val(db_session, test_organization, client, org_headers):
    """Material de compra regular: lo que se captura en una Entrada."""
    mat = _mat(db_session, test_organization.id, "MOTO-RT")
    r = client.put(f"{PROFILES}/{mat.id}", headers=org_headers, json={
        "compra_regular": True, "willard_world": "none", "lead_product": "none"})
    assert r.status_code == 200, r.text
    return mat


@pytest.fixture
def mat_est(db_session, test_organization, client, org_headers):
    """Material de control: lo que sale en una Salida de control."""
    mat = _mat(db_session, test_organization.id, "ESTIBAS-RT", unit="unidad")
    r = client.put(f"{PROFILES}/{mat.id}/control", headers=org_headers,
                   json={"control_only": True})
    assert r.status_code == 200, r.text
    return mat


_REM = itertools.count(1)


def _rem() -> str:
    return f"RT-{next(_REM)}"


def _past(days=2):
    return (business_today() - timedelta(days=days)).isoformat()


def _tdispatch(client, h, wh_from, wh_to, mat, qty=10, remission="auto", expect=201, **extra):
    """Despacha un traslado. `remission=None` omite la clave (para los 422)."""
    body = {
        "from_warehouse_id": str(wh_from.id), "to_warehouse_id": str(wh_to.id),
        "dispatch_date": DISPATCH_DATE,
        "lines": [{"material_id": str(mat.id), "quantity_dispatched": qty}],
        **extra,
    }
    if remission == "auto":
        body["remission_number"] = _rem()
    elif remission is not None:
        body["remission_number"] = remission
    r = client.post(TRANSFERS, headers=h, json=body)
    assert r.status_code == expect, r.text
    return r.json()


def _trecv(client, h, t, qty, expect=200):
    r = client.post(f"{TRANSFERS}/{t['id']}/receive", headers=h, json={
        "lines": [{"transfer_line_id": t["lines"][0]["id"], "quantity_received": qty}],
        "receipt_date": RECEIPT_DATE})
    assert r.status_code == expect, r.text
    return r.json()


def _tannul(client, h, t, expect=200):
    r = client.post(f"{TRANSFERS}/{t['id']}/annul", headers=h, json={"reason": "error de captura"})
    assert r.status_code == expect, r.text
    return r.json()


def _tget(client, h, tid):
    r = client.get(f"{TRANSFERS}/{tid}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _patch(client, h, tid, body, expect=200):
    r = client.patch(f"{TRANSFERS}/{tid}/remission", headers=h, json=body)
    assert r.status_code == expect, r.text
    return r.json()


def _line(mat, qty="1", weight="100"):
    body = {"material_id": str(mat.id), "quantity": str(qty)}
    if weight is not None:
        body["scale_weight_kg"] = str(weight)
    return body


def _entrada(client, h, wh, mat, remission=None, expect=201, **extra):
    body = {"inbound_type": "purchase", "warehouse_id": str(wh.id), "date": _past(),
            "lines": [_line(mat)], **extra}
    if remission is not None:
        body["remission_number"] = remission
    r = client.post(INBOUND, headers=h, json=body)
    assert r.status_code == expect, r.text
    return r.json()


def _salida_control(client, h, wh, mat, remission, expect=201, date=None):
    r = client.post(DISPATCHES, headers=h, json={
        "date": date or _past(), "warehouse_id": str(wh.id), "remission_number": remission,
        "lines": [{"material_id": str(mat.id), "quantity": "5"}]})
    assert r.status_code == expect, r.text
    return r.json()


def _book(client, h, expect=200, **params):
    r = client.get(REMISSIONS, headers=h, params=params)
    assert r.status_code == expect, r.text
    return r.json()


def _shape(items):
    """Lista compacta: ('doc', remision) o ('gap', desde, hasta, n)."""
    return [("gap", i["gap_from"], i["gap_to"], i["count"]) if i["kind"] == "gap"
            else ("doc", i["remission"]) for i in items]


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


def _clear_remission(db, tid):
    """Deja el traslado como los anteriores a este ciclo: remision NULL."""
    t = db.get(Transfer, UUID(str(tid)))
    t.remission_number = None
    db.commit()


# ---------------------------------------------------------------------------
# T1–T3 — la remision al despachar
# ---------------------------------------------------------------------------

class TestDespacho:
    def test_t1_cruzado_guarda_sin_espacios_y_la_devuelve(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, intersede_account,
        maquila_tariff, mat_contrib,
    ):
        t = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="  16400 ")
        assert t["remission_number"] == "16400"
        assert t["status"] == "dispatched"
        assert t["warnings"] == []
        assert _tget(client, org_headers, t["id"])["remission_number"] == "16400"
        listado = client.get(TRANSFERS, headers=org_headers).json()["items"]
        assert [i["remission_number"] for i in listado] == ["16400"]

    def test_t1_intra_sede_tambien_la_lleva(
        self, client, org_headers, wh_cv, wh_mol, mat_contrib,
    ):
        """El molino (misma sede): un solo salto, nace recibido, y la remision
        es obligatoria igual (decision de Daniel)."""
        t = _tdispatch(client, org_headers, wh_cv, wh_mol, mat_contrib, remission=" 16401")
        assert t["status"] == "received" and t["transit_warehouse_id"] is None
        assert t["remission_number"] == "16401" and t["warnings"] == []
        assert _tget(client, org_headers, t["id"])["remission_number"] == "16401"

    @pytest.mark.parametrize("valor", ["", "   ", None], ids=["vacia", "espacios", "ausente"])
    def test_t2_obligatoria_da_422_que_nombra_el_campo(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib, valor,
    ):
        body = {
            "from_warehouse_id": str(wh_cv.id), "to_warehouse_id": str(wh_jm.id),
            "dispatch_date": DISPATCH_DATE,
            "lines": [{"material_id": str(mat_contrib.id), "quantity_dispatched": 10}],
        }
        if valor is not None:
            body["remission_number"] = valor
        r = client.post(TRANSFERS, headers=org_headers, json=body)
        assert r.status_code == 422, r.text
        assert any("remission_number" in (e["loc"] or []) for e in r.json()["detail"])
        assert client.get(TRANSFERS, headers=org_headers).json()["total"] == 0

    def test_t3_una_clave_de_mas_da_422(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib,
    ):
        """extra="forbid": la clave correcta MAS una mal escrita (si solo faltara
        la correcta, el 422 saldria igual por el campo obligatorio)."""
        r = client.post(TRANSFERS, headers=org_headers, json={
            "from_warehouse_id": str(wh_cv.id), "to_warehouse_id": str(wh_jm.id),
            "dispatch_date": DISPATCH_DATE, "remission_number": "1",
            "remision_number": "2",
            "lines": [{"material_id": str(mat_contrib.id), "quantity_dispatched": 10}]})
        assert r.status_code == 422, r.text
        assert client.get(TRANSFERS, headers=org_headers).json()["total"] == 0


# ---------------------------------------------------------------------------
# T4–T7 — «Repetida»: se AVISA, no se rechaza (D8), en las dos direcciones
# ---------------------------------------------------------------------------

class TestRepetida:
    def test_t4_contra_una_entrada_avisa_y_la_nombra(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib, mat_val,
    ):
        e = _entrada(client, org_headers, wh_cv, mat_val, remission="16500")
        t = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission=" 16500 ")
        assert len(t["warnings"]) == 1
        assert f"Entrada #{e['order_number']}" in t["warnings"][0]

    def test_t4_contra_una_salida_de_control_avisa_y_la_nombra(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib, mat_est,
    ):
        d = _salida_control(client, org_headers, wh_cv, mat_est, "16501")
        t = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="16501")
        assert len(t["warnings"]) == 1
        assert f"Salida de control #{d['dispatch_number']}" in t["warnings"][0]

    def test_t4_contra_otro_traslado_avisa_y_lo_nombra(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib,
    ):
        a = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="16502")
        b = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="16502")
        assert a["warnings"] == []
        assert len(b["warnings"]) == 1
        assert f"Traslado #{a['transfer_number']}" in b["warnings"][0]

    def test_t5_la_entrada_creada_avisa_del_traslado(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib, mat_val,
    ):
        t = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="16510")
        e = _entrada(client, org_headers, wh_cv, mat_val, remission=" 16510")
        assert any(f"Traslado #{t['transfer_number']}" in w for w in e["warnings"])

    def test_t5_el_update_de_la_entrada_avisa_del_traslado(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib, mat_val,
    ):
        t = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="16511")
        e = _entrada(client, org_headers, wh_cv, mat_val, remission="16512")
        assert e["warnings"] == []
        r = client.patch(f"{INBOUND}/{e['id']}", headers=org_headers,
                         json={"remission_number": "16511"})
        assert r.status_code == 200, r.text
        assert len(r.json()["warnings"]) == 1
        assert f"Traslado #{t['transfer_number']}" in r.json()["warnings"][0]

    def test_t5_la_salida_de_control_creada_avisa_del_traslado(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib, mat_est,
    ):
        t = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="16513")
        d = _salida_control(client, org_headers, wh_cv, mat_est, "16513")
        assert any(f"Traslado #{t['transfer_number']}" in w for w in d["warnings"])

    def test_t6_un_traslado_anulado_no_cuenta_para_el_aviso(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, intersede_account,
        maquila_tariff, mat_contrib, mat_val,
    ):
        a = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="16520")
        _tannul(client, org_headers, a)
        b = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="16520")
        assert b["warnings"] == []
        e = _entrada(client, org_headers, wh_cv, mat_val, remission="16520")
        assert all("Traslado #" + str(a["transfer_number"]) not in w for w in e["warnings"])

    def test_t7_la_llave_normaliza_ceros_y_no_cruza_el_punto(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib, mat_val,
    ):
        e = _entrada(client, org_headers, wh_cv, mat_val, remission="16300")
        t = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="0016300")
        assert len(t["warnings"]) == 1
        assert f"Entrada #{e['order_number']}" in t["warnings"][0]

    def test_t7_doce_punto_cero_no_choca_con_doce(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib, mat_val,
    ):
        _entrada(client, org_headers, wh_cv, mat_val, remission="12")
        t = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="12.0")
        assert t["warnings"] == []

    # Adenda 3 (pasada 2 de QA 2). Los T7 de arriba tienen una ENTRADA como documento
    # existente: el aviso choca en el bloque de Entradas y nunca llega al de traslados.
    # Estos tres usan un TRASLADO existente, que es lo unico que ejercita ese bloque.
    def test_t7c_traslado_contra_traslado_normaliza_ceros_iniciales(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib,
    ):
        a = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="16300")
        assert a["warnings"] == []
        b = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="0016300")
        assert len(b["warnings"]) == 1
        assert f"Traslado #{a['transfer_number']}" in b["warnings"][0]

    def test_t7c_traslado_contra_traslado_en_la_otra_direccion(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib,
    ):
        a = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="0016300")
        assert a["warnings"] == []
        b = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="16300")
        assert len(b["warnings"]) == 1
        assert f"Traslado #{a['transfer_number']}" in b["warnings"][0]

    def test_t7d_traslado_contra_traslado_doce_punto_cero_no_choca(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib,
    ):
        a = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="12")
        b = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="12.0")
        # No vacuo: los dos traslados estan vivos y con esas dos remisiones guardadas, y la
        # unica diferencia entre ellas es el «.0» (el test mide que el punto no se cruza).
        assert _tget(client, org_headers, a["id"])["remission_number"] == "12"
        assert _tget(client, org_headers, b["id"])["remission_number"] == "12.0"
        assert a["status"] != "annulled" and b["status"] != "annulled"
        assert a["id"] != b["id"]
        assert b["warnings"] == []


# ---------------------------------------------------------------------------
# T8–T11, T14, T16 — el talonario con la tercera fuente
# ---------------------------------------------------------------------------

class TestTalonario:
    def test_t8_el_traslado_sale_como_tercera_fuente(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib,
    ):
        t = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="16600")
        v = _book(client, org_headers)
        docs = [i for i in v["items"] if i["kind"] == "doc"]
        assert len(docs) == 1
        d = docs[0]
        assert d["doc_type"] == "transfer" and d["doc_id"] == t["id"]
        assert d["doc_number"] == t["transfer_number"] and d["remission"] == "16600"
        assert d["status"] == "dispatched" and d["inbound_type"] is None
        assert d["materials"] == "DROSS-RT" and d["duplicated"] is False
        assert d["date"].startswith("2026-07-10")

    def test_t9_un_traslado_anulado_cubre_su_numero(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, intersede_account,
        maquila_tariff, mat_contrib, mat_val,
    ):
        _entrada(client, org_headers, wh_cv, mat_val, remission="100")
        t = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="101")
        _entrada(client, org_headers, wh_cv, mat_val, remission="102")
        _tannul(client, org_headers, t)
        v = _book(client, org_headers, order="asc")
        assert _shape(v["items"]) == [("doc", "100"), ("doc", "101"), ("doc", "102")]
        assert v["items"][1]["status"] == "annulled" and v["items"][1]["doc_type"] == "transfer"

    def test_t10_los_huecos_se_miden_contra_toda_la_org(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib, mat_val,
    ):
        """Un traslado fuera del filtro de fechas sigue cubriendo su numero."""
        _entrada(client, org_headers, wh_cv, mat_val, remission="100")
        _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="102")
        _entrada(client, org_headers, wh_cv, mat_val, remission="104")
        todo = _book(client, org_headers, order="asc")
        assert _shape(todo["items"]) == [
            ("doc", "100"), ("gap", "101", "101", "1"), ("doc", "102"),
            ("gap", "103", "103", "1"), ("doc", "104")]
        # Filtro por fecha que deja afuera al traslado (2026-07-10): el 102 NO
        # se vuelve hueco, y no sale
        dia = _past()
        filtrado = _book(client, org_headers, order="asc", date_from=dia, date_to=dia)
        assert _shape(filtrado["items"]) == [
            ("doc", "100"), ("gap", "101", "101", "1"), ("gap", "103", "103", "1"), ("doc", "104")]

    def test_t11_repetida_entre_un_traslado_y_una_entrada(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, intersede_account,
        maquila_tariff, mat_contrib, mat_val,
    ):
        e = _entrada(client, org_headers, wh_cv, mat_val, remission="200")
        t = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="200")
        v = _book(client, org_headers, order="asc")
        assert [i["duplicated"] for i in v["items"]] == [True, True]
        assert {i["doc_type"] for i in v["items"]} == {"inbound", "transfer"}
        _tannul(client, org_headers, t)
        v = _book(client, org_headers, order="asc")
        assert [i["duplicated"] for i in v["items"]] == [False, False]
        assert e["warnings"] == []

    def test_t14_un_traslado_viejo_devuelve_null_sin_500(
        self, client, org_headers, db_session, wh_cv, wh_jm, wh_transit, mat_contrib,
    ):
        t = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib)
        _clear_remission(db_session, t["id"])
        assert _tget(client, org_headers, t["id"])["remission_number"] is None
        items = client.get(TRANSFERS, headers=org_headers).json()["items"]
        assert [i["remission_number"] for i in items] == [None]

    def test_t14_un_traslado_viejo_no_sale_ni_cuenta_como_entrada_sin_remision(
        self, client, org_headers, db_session, wh_cv, wh_jm, wh_transit, mat_contrib,
    ):
        t = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib)
        _clear_remission(db_session, t["id"])
        v = _book(client, org_headers)
        assert v["items"] == [] and v["documents"] == 0
        assert v["inbound_without_remission"] == 0

    def test_t16_la_remision_de_texto_de_un_traslado_va_al_final(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib, mat_val,
    ):
        _entrada(client, org_headers, wh_cv, mat_val, remission="100")
        _entrada(client, org_headers, wh_cv, mat_val, remission="200")
        _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="R-7")
        asc = _shape(_book(client, org_headers, order="asc")["items"])
        desc = _shape(_book(client, org_headers, order="desc")["items"])
        assert asc == [("doc", "100"), ("gap", "101", "199", "99"), ("doc", "200"), ("doc", "R-7")]
        assert desc == [("doc", "200"), ("gap", "101", "199", "99"), ("doc", "100"), ("doc", "R-7")]


class TestOrdenTotal:
    def test_t17_empate_total_se_desempata_por_tipo_de_documento(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib, mat_val, mat_est,
    ):
        """C1 de QA 2 (pasada 1): tres fuentes con contador PROPIO. Entrada #1,
        Traslado #1 y Salida de control #1 con la MISMA remision y la MISMA fecha
        empatan en todo lo demas: el orden lo fija `doc_type` (desc), no el azar
        de Postgres. La premisa del empate se afirma, no se supone."""
        dia = "2026-07-10"  # el mismo dia del despacho del traslado
        _entrada(client, org_headers, wh_cv, mat_val, remission="777", date=dia)
        _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="777")
        _salida_control(client, org_headers, wh_cv, mat_est, "777", date=dia)
        esperado = ["transfer", "inbound", "control_dispatch"]
        for order in ("asc", "desc"):
            docs = [i for i in _book(client, org_headers, order=order)["items"]
                    if i["kind"] == "doc"]
            # Premisa: empate total en remision, fecha y numero de documento
            assert len(docs) == 3
            assert {i["remission"] for i in docs} == {"777"}
            assert len({i["date"] for i in docs}) == 1, [i["date"] for i in docs]
            assert {i["doc_number"] for i in docs} == {1}
            assert [i["doc_type"] for i in docs] == esperado, order
        # Estable entre corridas: la misma lista cada vez
        otra = [i["doc_type"] for i in _book(client, org_headers, order="desc")["items"]
                if i["kind"] == "doc"]
        assert otra == esperado


# ---------------------------------------------------------------------------
# T12, T13, T15 — quien ve las filas de traslado (D-a, D-b)
# ---------------------------------------------------------------------------

DOS = ["purchases.view", "sales.view"]


class TestVerYMedir:
    def test_t12a_sin_inventory_view_no_sale_la_fila_ni_un_hueco_falso(
        self, client, org_headers, db_session, test_organization, wh_cv, wh_jm, wh_transit,
        mat_contrib, mat_val,
    ):
        """C1 de QA 2 (cobertura): el traslado 101 va ENTRE dos Entradas visibles
        consecutivas. Quien no puede leer traslados no ve la fila, pero el 101
        sigue cubierto: no hay un «Sin documento» donde hay un documento."""
        _entrada(client, org_headers, wh_cv, mat_val, remission="100")
        _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="101")
        _entrada(client, org_headers, wh_cv, mat_val, remission="102")
        sin = _member(db_session, test_organization.id, "sin-inv-a", DOS)
        v = _book(client, sin, order="asc")
        assert _shape(v["items"]) == [("doc", "100"), ("doc", "102")]
        assert all(i["doc_type"] != "transfer" for i in v["items"])

    def test_t12b_sin_inventory_view_la_repetida_se_conserva(
        self, client, org_headers, db_session, test_organization, wh_cv, wh_jm, wh_transit,
        mat_contrib, mat_val,
    ):
        """C1 de QA 2 (marca): un traslado oculto con la MISMA remision que una
        Entrada visible; sin vecinos en la serie, para que no haya huecos."""
        _entrada(client, org_headers, wh_cv, mat_val, remission="300")
        _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="300")
        sin = _member(db_session, test_organization.id, "sin-inv-b", DOS)
        v = _book(client, sin, order="asc")
        assert [(i["doc_type"], i["duplicated"]) for i in v["items"]] == [("inbound", True)]

    def test_t12c_control_positivo_con_inventory_view_salen_las_filas(
        self, client, org_headers, db_session, test_organization, wh_cv, wh_jm, wh_transit,
        mat_contrib, mat_val,
    ):
        _entrada(client, org_headers, wh_cv, mat_val, remission="100")
        _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="101")
        _entrada(client, org_headers, wh_cv, mat_val, remission="102")
        _entrada(client, org_headers, wh_cv, mat_val, remission="300")
        _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="300")
        con = _member(db_session, test_organization.id, "con-inv", DOS + ["inventory.view"])
        v = _book(client, con, order="asc")
        trs = [i for i in v["items"] if i["doc_type"] == "transfer"]
        assert sorted(i["remission"] for i in trs) == ["101", "300"]
        assert ("doc", "101") in _shape(v["items"])

    def test_t12d_un_rol_con_inventory_view_y_sin_sales_view_recibe_403(
        self, client, db_session, test_organization,
    ):
        solo_inv = _member(db_session, test_organization.id, "inv-compras",
                           ["inventory.view", "purchases.view"])
        assert client.get(REMISSIONS, headers=solo_inv).status_code == 403
        las_dos = _member(db_session, test_organization.id, "dos-sin-inv", DOS)
        assert client.get(REMISSIONS, headers=las_dos).status_code == 200

    def test_t13_sin_el_flag_de_traslados_las_filas_no_salen(
        self, client, org_headers, db_session, test_organization, wh_cv, wh_jm, wh_transit,
        mat_contrib, mat_val,
    ):
        """El PAR del flag: con kg_ledger y SIN two_step las filas existentes no
        salen aunque el usuario las pueda leer, y su numero sigue cubierto."""
        _entrada(client, org_headers, wh_cv, mat_val, remission="100")
        _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="101")
        _entrada(client, org_headers, wh_cv, mat_val, remission="102")
        test_organization.settings = {"kg_ledger_enabled": True}
        db_session.commit()
        v = _book(client, org_headers, order="asc")
        assert _shape(v["items"]) == [("doc", "100"), ("doc", "102")]

    def test_t13_con_el_flag_las_filas_salen(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib, mat_val,
    ):
        _entrada(client, org_headers, wh_cv, mat_val, remission="100")
        _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="101")
        _entrada(client, org_headers, wh_cv, mat_val, remission="102")
        v = _book(client, org_headers, order="asc")
        assert _shape(v["items"]) == [("doc", "100"), ("doc", "101"), ("doc", "102")]

    def test_t15_ingrid_no_ve_el_talonario_ni_despacha_ni_corrige(
        self, client, org_headers, db_session, test_organization, wh_cv, wh_jm, wh_transit,
        mat_contrib,
    ):
        """Alcance de recolector (#129): las tres rutas dan 403. El PATCH apunta a
        un traslado que EXISTE, para que un 404 no tape el 403."""
        gl = create_third_party_with_category(
            db_session, test_organization.id, "Green Loop RT", "service_provider")
        db_session.commit()
        t = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="16700")
        ingrid = _member(db_session, test_organization.id, "ingrid-rt", [
            "purchases.view", "sales.view", "inventory.view", "inventory.transfer",
            "inventory.transfer_receive"], scope=gl.id)
        assert client.get(REMISSIONS, headers=ingrid).status_code == 403
        r = client.post(TRANSFERS, headers=ingrid, json={
            "from_warehouse_id": str(wh_cv.id), "to_warehouse_id": str(wh_jm.id),
            "remission_number": "16701",
            "lines": [{"material_id": str(mat_contrib.id), "quantity_dispatched": 1}]})
        assert r.status_code == 403, r.text
        r = client.patch(f"{TRANSFERS}/{t['id']}/remission", headers=ingrid,
                         json={"remission_number": "16702"})
        assert r.status_code == 403, r.text
        assert _tget(client, org_headers, t["id"])["remission_number"] == "16700"


# ---------------------------------------------------------------------------
# TP — el PATCH de la remision (D-e)
# ---------------------------------------------------------------------------

def _en_estado(client, h, estado, wh_cv, wh_jm, mat, remission):
    t = _tdispatch(client, h, wh_cv, wh_jm, mat, qty=40, remission=remission)
    if estado == "received":
        assert _trecv(client, h, t, 40)["status"] == "received"
    elif estado == "held_discrepancy":
        assert _trecv(client, h, t, 30)["status"] == "held_discrepancy"
    return t


class TestPatchRemision:
    @pytest.mark.parametrize("estado", ["dispatched", "received", "held_discrepancy"])
    def test_tp1_caso_feliz_en_los_tres_estados(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, intersede_account,
        maquila_tariff, mat_contrib, estado,
    ):
        t = _en_estado(client, org_headers, estado, wh_cv, wh_jm, mat_contrib, "16800")
        r = _patch(client, org_headers, t["id"], {"remission_number": "  16801 "})
        assert r["remission_number"] == "16801" and r["warnings"] == []
        assert r["status"] == estado
        assert _tget(client, org_headers, t["id"])["remission_number"] == "16801"
        items = client.get(TRANSFERS, headers=org_headers).json()["items"]
        assert [i["remission_number"] for i in items] == ["16801"]

    @pytest.mark.parametrize("valor", ["", "   ", None, "AUSENTE"],
                             ids=["vacia", "espacios", "null", "ausente"])
    def test_tp2_obligatoria_y_no_se_puede_vaciar(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib, valor,
    ):
        t = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="16810")
        body = {} if valor == "AUSENTE" else {"remission_number": valor}
        r = client.patch(f"{TRANSFERS}/{t['id']}/remission", headers=org_headers, json=body)
        assert r.status_code == 422, r.text
        assert _tget(client, org_headers, t["id"])["remission_number"] == "16810"

    def test_tp3_una_clave_de_mas_da_422(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib,
    ):
        t = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="16820")
        r = client.patch(f"{TRANSFERS}/{t['id']}/remission", headers=org_headers,
                         json={"remission_number": "16821", "remision_number": "x"})
        assert r.status_code == 422, r.text
        assert _tget(client, org_headers, t["id"])["remission_number"] == "16820"

    def test_tp4_repetida_contra_una_entrada_avisa_y_cambia(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib, mat_val,
    ):
        e = _entrada(client, org_headers, wh_cv, mat_val, remission="16830")
        t = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="16831")
        r = _patch(client, org_headers, t["id"], {"remission_number": " 16830"})
        assert len(r["warnings"]) == 1 and f"Entrada #{e['order_number']}" in r["warnings"][0]
        assert r["remission_number"] == "16830"

    def test_tp4_repetida_contra_una_salida_de_control_avisa_y_cambia(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib, mat_est,
    ):
        d = _salida_control(client, org_headers, wh_cv, mat_est, "16840")
        t = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="16841")
        r = _patch(client, org_headers, t["id"], {"remission_number": "16840"})
        assert len(r["warnings"]) == 1
        assert f"Salida de control #{d['dispatch_number']}" in r["warnings"][0]
        assert r["remission_number"] == "16840"

    def test_tp4_repetida_contra_otro_traslado_avisa_y_cambia(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib,
    ):
        a = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="16850")
        b = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="16851")
        r = _patch(client, org_headers, b["id"], {"remission_number": "16850"})
        assert len(r["warnings"]) == 1 and f"Traslado #{a['transfer_number']}" in r["warnings"][0]
        assert r["remission_number"] == "16850"

    def test_tp5_sin_cambio_no_avisa(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib, mat_val,
    ):
        _entrada(client, org_headers, wh_cv, mat_val, remission="16860")
        t = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="16860")
        assert t["warnings"]  # al despachar si avisa
        r = _patch(client, org_headers, t["id"], {"remission_number": "  16860  "})
        assert r["warnings"] == [] and r["remission_number"] == "16860"

    def test_tp6_un_traslado_anulado_no_se_corrige(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, intersede_account,
        maquila_tariff, mat_contrib,
    ):
        t = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="16870")
        _tannul(client, org_headers, t)
        r = client.patch(f"{TRANSFERS}/{t['id']}/remission", headers=org_headers,
                         json={"remission_number": "16871"})
        assert r.status_code == 400, r.text
        assert "anulado" in r.json()["detail"] and "antes de anular" in r.json()["detail"]
        assert _tget(client, org_headers, t["id"])["remission_number"] == "16870"

    def test_tp7a_quien_solo_lee_y_recibe_no_corrige(
        self, client, org_headers, db_session, test_organization, wh_cv, wh_jm, wh_transit,
        mat_contrib,
    ):
        t = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="16880")
        recibe = _member(db_session, test_organization.id, "recibe-rt",
                         ["inventory.view", "inventory.transfer_receive"])
        r = client.patch(f"{TRANSFERS}/{t['id']}/remission", headers=recibe,
                         json={"remission_number": "16881"})
        assert r.status_code == 403, r.text
        assert _tget(client, org_headers, t["id"])["remission_number"] == "16880"

    def test_tp7b_control_positivo_inventory_transfer_corrige(
        self, client, org_headers, db_session, test_organization, wh_cv, wh_jm, wh_transit,
        mat_contrib,
    ):
        t = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="16890")
        despacha = _member(db_session, test_organization.id, "despacha-rt", ["inventory.transfer"])
        r = client.patch(f"{TRANSFERS}/{t['id']}/remission", headers=despacha,
                         json={"remission_number": "16891"})
        assert r.status_code == 200, r.text
        assert r.json()["remission_number"] == "16891"

    def test_tp8_no_mueve_nada(
        self, client, org_headers, db_session, wh_cv, wh_jm, wh_transit, intersede_account,
        maquila_tariff, mat_contrib,
    ):
        """A: cruzado, recibido con merma y par de maquila. B: fuera de tolerancia
        (held, con su tarea). Se vuelcan las siete tablas, los materiales y los
        traslados (menos la remision) antes y despues del PATCH a los dos."""
        a = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, qty=40, remission="16900")
        assert _trecv(client, org_headers, a, 39)["status"] == "received"   # merma 1 kg (2,5 %)
        b = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, qty=40, remission="16901")
        assert _trecv(client, org_headers, b, 30)["status"] == "held_discrepancy"

        antes = _snapshot(db_session)
        # Control positivo POR TABLA: sin filas, la igualdad seria 0 == 0
        for nombre in ("inventory_movements", "kg_ledger_movements", "transfer_lines",
                       "money_movements", "inventory_adjustments",
                       "material_cost_histories", "discrepancy_tasks"):
            assert antes[nombre], f"{nombre} esta vacia antes del PATCH: el control no dice nada"

        _patch(client, org_headers, a["id"], {"remission_number": "16910"})
        _patch(client, org_headers, b["id"], {"remission_number": "16911"})

        despues = _snapshot(db_session)
        assert despues == antes
        assert _tget(client, org_headers, a["id"])["remission_number"] == "16910"
        assert _tget(client, org_headers, b["id"])["remission_number"] == "16911"

    def test_tp10_aislamiento_por_org_e_id_inexistente_dan_404(
        self, client, org_headers, db_session, test_organization2,
    ):
        w1 = _wh(db_session, test_organization2.id, "Origen Org2")
        w2 = _wh(db_session, test_organization2.id, "Destino Org2")
        ajeno = Transfer(
            organization_id=test_organization2.id, transfer_number=1,
            from_warehouse_id=w1.id, to_warehouse_id=w2.id,
            dispatch_date=datetime(2026, 7, 10, 12, tzinfo=timezone.utc),
            status="dispatched", remission_number="ORG2-1")
        db_session.add(ajeno)
        db_session.commit()
        for tid in (ajeno.id, uuid4()):
            r = client.patch(f"{TRANSFERS}/{tid}/remission", headers=org_headers,
                             json={"remission_number": "HACK"})
            assert r.status_code == 404, r.text
        db_session.expire_all()
        assert db_session.get(Transfer, ajeno.id).remission_number == "ORG2-1"

    def test_tp11_el_talonario_sigue_la_correccion(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib, mat_val,
    ):
        _entrada(client, org_headers, wh_cv, mat_val, remission="100")
        t = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="101")
        _entrada(client, org_headers, wh_cv, mat_val, remission="103")
        antes = _shape(_book(client, org_headers, order="asc")["items"])
        assert antes == [("doc", "100"), ("doc", "101"), ("gap", "102", "102", "1"), ("doc", "103")]
        _patch(client, org_headers, t["id"], {"remission_number": "102"})
        despues = _shape(_book(client, org_headers, order="asc")["items"])
        assert despues == [("doc", "100"), ("gap", "101", "101", "1"), ("doc", "102"), ("doc", "103")]

    def test_tp12_un_traslado_viejo_sin_remision_la_fija(
        self, client, org_headers, db_session, wh_cv, wh_jm, wh_transit, mat_contrib,
    ):
        """C1 de QA 2: la guardada es NULL (anterior a este ciclo); comparar con
        `x.strip()` sobre NULL daria 500."""
        t = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib)
        _clear_remission(db_session, t["id"])
        r = _patch(client, org_headers, t["id"], {"remission_number": "OLD-1"})
        assert r["remission_number"] == "OLD-1" and r["warnings"] == []
        assert _tget(client, org_headers, t["id"])["remission_number"] == "OLD-1"
        assert _shape(_book(client, org_headers)["items"]) == [("doc", "OLD-1")]

    def test_tp13_la_linea_de_log(
        self, client, org_headers, db_session, test_user, wh_cv, wh_jm, wh_transit,
        intersede_account, maquila_tariff, mat_contrib, caplog,
    ):
        """Adenda 1: una linea por correccion GUARDADA, con actor, traslado,
        numero anterior y nuevo. Nunca el cuerpo del request (H3 de #85)."""
        def lineas():
            return [r for r in caplog.records
                    if r.getMessage().startswith("transfer_remission_changed")]

        a = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="LOG-1")
        c = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib)
        _clear_remission(db_session, c["id"])
        b = _tdispatch(client, org_headers, wh_cv, wh_jm, mat_contrib, remission="LOG-B")
        _tannul(client, org_headers, b)

        with caplog.at_level(logging.WARNING, logger="app.services.transfer"):
            # 1. Un cambio (con espacios): exactamente una linea con los cinco datos
            _patch(client, org_headers, a["id"], {"remission_number": " LOG-2 "})
            assert len(lineas()) == 1
            msg = lineas()[0].getMessage()
            assert str(test_user.id) in msg and test_user.email in msg
            assert a["id"] in msg and f"transfer_number={a['transfer_number']}" in msg
            assert "previous='LOG-1'" in msg and "new='LOG-2'" in msg
            # 2. Nunca el cuerpo del request (el corazon de H3)
            assert "remission_number" not in msg
            assert '{"remission_number"' not in msg
            # 3. Sin cambio: no se agrega otra
            _patch(client, org_headers, a["id"], {"remission_number": "LOG-2"})
            assert len(lineas()) == 1
            # 4. Control, no red: el 422 sale en el schema, antes del servicio; el
            #    400 de un anulado es la red de P37
            client.patch(f"{TRANSFERS}/{a['id']}/remission", headers=org_headers,
                         json={"remission_number": ""})
            r = client.patch(f"{TRANSFERS}/{b['id']}/remission", headers=org_headers,
                             json={"remission_number": "LOG-B2"})
            assert r.status_code == 400
            assert len(lineas()) == 1
            # 5. Un traslado viejo sin remision: una linea mas, con previous=None
            _patch(client, org_headers, c["id"], {"remission_number": "LOG-C"})
            assert len(lineas()) == 2
            assert "previous=None" in lineas()[1].getMessage()
            assert "new='LOG-C'" in lineas()[1].getMessage()


# ---------------------------------------------------------------------------
# Volcado de tablas para TP8
# ---------------------------------------------------------------------------

_TABLAS = (InventoryMovement, KgLedgerMovement, MoneyMovement, InventoryAdjustment,
           MaterialCostHistory, DiscrepancyTask, TransferLine)


def _filas(db, model, omitir=()):
    cols = [a.key for a in inspect(model).mapper.column_attrs if a.key not in omitir]
    return sorted(
        tuple(repr(getattr(r, c)) for c in cols)
        for r in db.execute(select(model)).scalars().all()
    )


def _snapshot(db) -> dict:
    """Conteo + huella de cada fila de las siete tablas, mas los materiales
    (existencias y costo promedio) y los traslados MENOS lo que el PATCH escribe
    legitimamente (la remision y su `updated_at`)."""
    db.expire_all()
    snap = {m.__tablename__: _filas(db, m) for m in _TABLAS}
    snap["materials"] = _filas(db, Material)
    snap["transfers"] = _filas(db, Transfer, omitir=("remission_number", "updated_at"))
    return snap
