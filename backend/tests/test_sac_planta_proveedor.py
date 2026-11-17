"""
Tests — planta como proveedor de maquila (plan-sac-planta-como-proveedor v1.1).

Johana (Q-61, WhatsApp del 13-nov) lleva a la planta Juan Mina como un
proveedor al que le debe las maquilas en pesos. Con el setting
`plant_third_party_id`, las cinco maquilas entre sedes se causan como UN
`expense_accrual` a ese tercero en vez del par interno (D1/D2).

Lo que se vigila de verdad:
- El PAR de cada emision (sin setting = par interno de siempre; con setting =
  causado a planta). Sin el contraste, "el setting funciona" y "lo rompi para
  las 6 orgs" se ven identicos (#94/#99). La mitad "sin setting" vive tambien en
  los tests existentes de traslados, Salidas y crisol (P8).
- Fail-closed (D3): un setting que apunta a un tercero que no sirve da 422 y
  NO escribe nada, medido con conteos leidos en OTRA sesion. Nunca cae en
  silencio al par: eso perderia la deuda sin aviso (#98 D10, #100 D4d).
- La anulacion lee `movement.third_party_id` y nunca el setting (D4/C3): un
  documento viejo se anula bien aunque el setting cambie despues.
- El invariante de #55 (saldo corrido del estado de cuenta == saldo vivo) en
  PLANTA y en WILLARD, a la ida y a la vuelta (O5).
"""
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.models.expense_category import ExpenseCategory
from app.models.inventory_adjustment import InventoryAdjustment
from app.models.inventory_movement import InventoryMovement
from app.models.kg_ledger import KgLedgerAccount, KgLedgerMovement
from app.models.material_conversion_formula import MaterialConversionFormula
from app.models.material_kg_profile import MaterialKgProfile
from app.models.material_transformation import MaterialTransformation
from app.models.money_movement import MoneyMovement
from app.models.plant_process import CrucibleCharge
from app.models.sale import Sale
from app.models.service_tariff import ServiceTariff
from app.models.third_party import ThirdParty
from app.models.transfer import Transfer
from app.models.willard_delivery import WillardDelivery
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    create_material,
    create_material_category,
    create_warehouse,
)

TRANSFERS_URL = "/api/v1/transfers"
DELIVERIES_URL = "/api/v1/willard-deliveries"
CRUCIBLE_URL = "/api/v1/crucible-charges"
KG_URL = "/api/v1/kg-ledger"
MM_URL = "/api/v1/money-movements"
ADJUST_URL = "/api/v1/inventory/adjustments"
PURCHASES_URL = "/api/v1/purchases"

SEED_DATE = "2026-07-01T12:00:00"
DISPATCH_DATE = "2026-07-10T12:00:00"
RECEIPT_DATE = "2026-07-12T12:00:00"
DOC_DATE = "2026-07-10T12:00:00"


# --------------------------------------------------------------- fixtures ---

@pytest.fixture
def wh_cv(db_session, test_organization):
    wh = create_warehouse(db_session, test_organization.id, "Circunvalar")
    db_session.commit()
    return wh


@pytest.fixture
def wh_jm(db_session, test_organization):
    wh = create_warehouse(db_session, test_organization.id, "Juan Mina")
    db_session.commit()
    return wh


@pytest.fixture
def wh_transit(db_session, test_organization, wh_jm):
    wh = create_warehouse(db_session, test_organization.id, "JM-TRANSITO")
    wh.is_transit = True
    wh.is_receiving = False
    wh.transit_target_warehouse_id = wh_jm.id
    db_session.commit()
    return wh


@pytest.fixture(autouse=True)
def _flags(db_session, test_organization, wh_cv, wh_jm):
    """Los settings de la SAC de produccion, SIN `plant_third_party_id`: cada
    test lo pone con `_con_planta` cuando prueba la mitad "con setting"."""
    test_organization.settings = {
        "kg_ledger_enabled": True,
        "two_step_transfers_enabled": True,
        "internal_maquila_enabled": True,
        "willard_sede_facturacion": str(wh_cv.id),
        "willard_sede_drosses": str(wh_jm.id),
    }
    db_session.commit()


def _set(db, org, **settings):
    """Reasigna el dict (la columna no es MutableDict: mutar no persiste)."""
    org.settings = {**(org.settings or {}), **settings}
    db.commit()


def _con_planta(db, org, tp):
    _set(db, org, plant_third_party_id=str(tp.id))


@pytest.fixture
def planta(db_session, test_organization):
    """PLANTA JUAN MINA como en produccion: un Pasivo."""
    tp = create_third_party_with_category(
        db_session, test_organization.id, "PLANTA JUAN MINA", "liability"
    )
    db_session.commit()
    return tp


@pytest.fixture
def willard(db_session, test_organization):
    tp = create_third_party_with_category(
        db_session, test_organization.id, "Willard S.A", "customer"
    )
    db_session.commit()
    return tp


@pytest.fixture
def cuentas(db_session, test_organization, willard, wh_cv):
    """Las tres cuentas kg que tocan los flujos: intersede (traslado, venta,
    crisol), drosses (abono de materiales) y baterias de CV (abono de baterias)."""
    org = test_organization.id
    accs = {
        "intersede": KgLedgerAccount(
            organization_id=org, code="INTERSEDE", display_name="Intersede",
            account_type="intersede", is_active=True,
        ),
        "drosses": KgLedgerAccount(
            organization_id=org, code="WILL-DROSS", display_name="Willard Drosses",
            account_type="willard_drosses", third_party_id=willard.id, is_active=True,
        ),
        "baterias": KgLedgerAccount(
            organization_id=org, code="WILL-BAT-CV", display_name="Willard Baterias CV",
            account_type="willard_baterias", warehouse_id=wh_cv.id,
            third_party_id=willard.id, is_active=True,
        ),
    }
    db_session.add_all(accs.values())
    db_session.commit()
    return accs


def _tariff(db, org_id, user_id, code, price):
    t = ServiceTariff(
        organization_id=org_id, tariff_code=code, unit_price_cop=Decimal(str(price)),
        unit="per_kg_lead", created_by=user_id,
    )
    db.add(t)
    db.commit()
    return t


@pytest.fixture
def tarifas(db_session, test_organization, test_user):
    """Los valores reales de la SAC (CC-009, #109): maquila intersede 1.500,
    crisol 300, factura a Willard 2.097 + 37, reparto 1.248 / 566."""
    org, user = test_organization.id, test_user.id
    return {
        code: _tariff(db_session, org, user, code, price)
        for code, price in [
            ("maquila_intersede_cv_jm", 1500),
            ("maquila_crisol", 300),
            ("maquila_willard", 2097),
            ("flete_willard_planta_planta", 37),
            ("abono_planta_por_kg", 1248),
            ("abono_planta_bateria_por_kg", 566),
        ]
    }


def _mat(db, org_id, code, name, lead=None):
    cat = create_material_category(db, org_id, f"Cat {code}")
    mat = create_material(db, org_id, code, name, cat.id)
    mat.default_unit = "kg"
    if lead is not None:
        db.add(MaterialKgProfile(organization_id=org_id, material_id=mat.id, lead_product=lead))
    db.commit()
    return mat


def _formula(db, org_id, user_id, mat, pct):
    db.add(MaterialConversionFormula(
        organization_id=org_id, material_id=mat.id, formula_type="drosses_to_lead",
        parameters={"lead_percentage": pct}, created_by=user_id,
    ))
    db.commit()


def _stock(client, headers, mat, wh, qty="100", cost="2000"):
    r = client.post(f"{ADJUST_URL}/increase", headers=headers, json={
        "material_id": str(mat.id), "warehouse_id": str(wh.id), "quantity": qty,
        "unit_cost": cost, "date": SEED_DATE, "reason": "Seed",
    })
    assert r.status_code == 201, r.text


@pytest.fixture
def mats(db_session, test_organization, test_user, client, org_headers, wh_cv, wh_jm):
    """Un material por flujo:
    - aporte: drosses al 50 % en Circunvalar, para el traslado CV -> JM;
    - crudo y puro en Juan Mina, marcados (#103): Salidas y crisol;
    - dross: 70 % de plomo, sin perfil kg, para el retorno al horno (#109)."""
    org, user = test_organization.id, test_user.id
    aporte = _mat(db_session, org, "DROSS-T", "Drosses traslado")
    _formula(db_session, org, user, aporte, 0.5)
    _stock(client, org_headers, aporte, wh_cv, cost="1000")
    crudo = _mat(db_session, org, "PB-CRU", "Plomo Crudo", "crudo")
    _stock(client, org_headers, crudo, wh_jm)
    puro = _mat(db_session, org, "PB-PUR", "Plomo Puro", "puro")
    _stock(client, org_headers, puro, wh_jm, cost="2500")
    dross = _mat(db_session, org, "DROSS-CRI", "Dross de crisol")
    _formula(db_session, org, user, dross, 0.70)
    return {"aporte": aporte, "crudo": crudo, "puro": puro, "dross": dross}


@pytest.fixture
def escenario(wh_transit, planta, willard, cuentas, tarifas, mats):
    """Todo lo que necesitan los cinco caminos de emision."""
    return {"planta": planta, "willard": willard, "cuentas": cuentas, "mats": mats}


# ----------------------------------------------------------------- flujos ---

def _seed_stage(client, headers, account_id, kg, stage):
    r = client.post(f"{KG_URL}/movements", headers=headers, json={
        "account_id": str(account_id), "delta_kg": str(kg), "transaction_date": SEED_DATE,
        "description": "seed", "reason": "seed de prueba", "stage": stage,
    })
    assert r.status_code == 201, r.text


def _dispatch(client, headers, wh_from, wh_to, mat, qty=40):
    r = client.post(TRANSFERS_URL, headers=headers, json={
        "from_warehouse_id": str(wh_from.id), "to_warehouse_id": str(wh_to.id),
        "dispatch_date": DISPATCH_DATE,
        "lines": [{"material_id": str(mat.id), "quantity_dispatched": qty}],
    })
    assert r.status_code == 201, r.text
    return r.json()


def _receive_req(client, headers, t, qty):
    return client.post(f"{TRANSFERS_URL}/{t['id']}/receive", headers=headers, json={
        "lines": [{"transfer_line_id": t["lines"][0]["id"], "quantity_received": qty}],
        "receipt_date": RECEIPT_DATE,
    })


def _resolve_req(client, headers, t):
    return client.post(f"{TRANSFERS_URL}/{t['id']}/resolve", headers=headers, json={
        "lines": [{"transfer_line_id": t["lines"][0]["id"], "resolution": "justify"}],
        "notes": "Resolucion de prueba",
    })


def _traslado(client, headers, esc, wh_cv, wh_jm, qty=40):
    """CV -> JM, 40 kg de drosses al 50 % = 20 kg de plomo -> $30.000."""
    t = _dispatch(client, headers, wh_cv, wh_jm, esc["mats"]["aporte"], qty)
    r = _receive_req(client, headers, t, qty)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "received"
    return {"kind": "transfer", "id": t["id"]}


def _create_delivery(client, headers, wh, willard, mat, dtype, qty):
    r = client.post(DELIVERIES_URL, headers=headers, json={
        "delivery_type": dtype, "warehouse_id": str(wh.id),
        "third_party_id": str(willard.id), "date": DOC_DATE,
        "remission_number": "REM-1",
        "lines": [{"material_id": str(mat.id), "quantity": qty}],
    })
    assert r.status_code == 201, r.text
    return r.json()


def _liquidate_req(client, headers, d, price=None):
    body = {"line_prices": []}
    if d["delivery_type"] == "venta":
        body["line_prices"] = [{"line_id": d["lines"][0]["id"], "unit_price": str(price or 3000)}]
    return client.post(f"{DELIVERIES_URL}/{d['id']}/liquidate", headers=headers, json=body)


def _salida(client, headers, esc, wh_jm, dtype, mat_key, qty="50"):
    d = _create_delivery(client, headers, wh_jm, esc["willard"], esc["mats"][mat_key], dtype, qty)
    r = _liquidate_req(client, headers, d)
    assert r.status_code == 200, r.text
    return {"kind": "willard_delivery", "id": d["id"], "body": r.json()}


def _venta_puro(client, headers, esc, wh_jm, qty="20"):
    """Vender 20 kg de puro: $300 x 20 = $6.000 de diferencial (#107 D3)."""
    _seed_stage(client, headers, esc["cuentas"]["intersede"].id, 50, "crisol")
    return _salida(client, headers, esc, wh_jm, "venta", "puro", qty)


def _charge_req(client, headers, wh, mat, kg, event_type):
    return client.post(CRUCIBLE_URL, headers=headers, json={
        "event_type": event_type, "warehouse_id": str(wh.id),
        "material_id": str(mat.id), "quantity_kg": str(kg), "date": DOC_DATE,
    })


def _prep_dross(client, headers, esc, wh_jm):
    _seed_stage(client, headers, esc["cuentas"]["intersede"].id, 100, "horno")
    r = _charge_req(client, headers, wh_jm, esc["mats"]["crudo"], 30, "charge")
    assert r.status_code == 201, r.text


def _dross(client, headers, esc, wh_jm):
    """Retorno de 5 kg de dross al 70 % = 3,5 kg de plomo -> $5.250 (#109)."""
    _prep_dross(client, headers, esc, wh_jm)
    r = _charge_req(client, headers, wh_jm, esc["mats"]["dross"], 5, "dross_return")
    assert r.status_code == 201, r.text
    return {"kind": "crucible_charge", "id": r.json()["id"], "body": r.json()}


ANNUL_URL = {
    "transfer": TRANSFERS_URL,
    "willard_delivery": DELIVERIES_URL,
    "crucible_charge": CRUCIBLE_URL,
}


def _annul_doc(client, headers, doc):
    r = client.post(f"{ANNUL_URL[doc['kind']]}/{doc['id']}/annul", headers=headers,
                    json={"reason": "prueba de anulacion"})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- lecturas ---

def _doc_mms(db, doc, status=None):
    db.expire_all()
    q = select(MoneyMovement).where(
        MoneyMovement.source_type == doc["kind"],
        MoneyMovement.source_id == doc["id"],
    )
    if status:
        q = q.where(MoneyMovement.status == status)
    return db.execute(q).scalars().all()


def _maquila_mms(db, doc, status="confirmed"):
    """Los movimientos de maquila del documento: el par interno o el causado
    a planta. La factura de la Salida (service_income_accrual) queda fuera."""
    return [
        m for m in _doc_mms(db, doc, status)
        if m.movement_type in ("internal_maquila_expense", "internal_maquila_income",
                               "expense_accrual")
    ]


def _balance(db, tp):
    db.expire_all()
    return db.get(ThirdParty, tp.id).current_balance


def _corrido_igual_vivo(client, headers, db, tp):
    """Invariante de #55: la ultima fila del estado de cuenta == saldo vivo."""
    r = client.get(f"{MM_URL}/third-party/{tp.id}", headers=headers,
                   params={"date_from": "2026-01-01", "date_to": "2026-12-31"})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items, f"el estado de cuenta de {tp.name} llego vacio"
    vivo = _balance(db, tp)
    corrido = Decimal(str(items[-1]["balance_after"]))
    assert corrido == vivo, f"{tp.name}: corrido {corrido} != vivo {vivo}"
    return vivo


def _category(db, mm):
    return db.get(ExpenseCategory, mm.expense_category_id).name


def _assert_causado(db, doc, planta, amount, warehouse, category):
    """Con setting: UN expense_accrual a planta, sin par interno."""
    maq = _maquila_mms(db, doc)
    assert [m.movement_type for m in maq] == ["expense_accrual"], maq
    mm = maq[0]
    assert mm.third_party_id == planta.id
    assert mm.account_id is None
    assert mm.amount == Decimal(amount)
    assert mm.warehouse_id == warehouse.id, "la sede que paga es la que factura"
    assert mm.tariff_id is not None
    assert mm.transfer_pair_id is None
    assert _category(db, mm) == category
    return mm


def _assert_par(db, doc, amount, wh_paga, wh_recibe):
    """Sin setting: el par interno de siempre, enlazado y sin tercero."""
    maq = _maquila_mms(db, doc)
    exp = [m for m in maq if m.movement_type == "internal_maquila_expense"]
    inc = [m for m in maq if m.movement_type == "internal_maquila_income"]
    assert len(exp) == 1 and len(inc) == 1 and len(maq) == 2, maq
    assert exp[0].amount == inc[0].amount == Decimal(amount)
    assert exp[0].third_party_id is None and inc[0].third_party_id is None
    assert exp[0].warehouse_id == wh_paga.id and inc[0].warehouse_id == wh_recibe.id
    assert exp[0].transfer_pair_id == inc[0].id and inc[0].transfer_pair_id == exp[0].id


# --------------------------------------------------------------- emision ---

class TestEmision:

    def test_t1_traslado_sin_setting_es_el_par_de_siempre(
        self, client, org_headers, db_session, test_organization, wh_cv, wh_jm, escenario,
    ):
        """T1 — la mitad "sin setting", que es la red de las 6 orgs (P8)."""
        doc = _traslado(client, org_headers, escenario, wh_cv, wh_jm)
        _assert_par(db_session, doc, "30000.00", wh_cv, wh_jm)
        assert _balance(db_session, escenario["planta"]) == 0
        assert [m for m in _doc_mms(db_session, doc) if m.movement_type == "expense_accrual"] == []

    def test_t2_traslado_con_setting_se_causa_a_planta(
        self, client, org_headers, db_session, test_organization, wh_cv, wh_jm, escenario,
    ):
        """T2 — 40 kg de drosses al 50 % = 20 kg de plomo x $1.500 = $30.000,
        a deber a PLANTA, con la categoria y la sede del gasto de hoy."""
        planta = escenario["planta"]
        _con_planta(db_session, test_organization, planta)
        doc = _traslado(client, org_headers, escenario, wh_cv, wh_jm)
        _assert_causado(db_session, doc, planta, "30000.00", wh_cv, "Maquila Intersede")
        assert _balance(db_session, planta) == Decimal("-30000.00")
        _corrido_igual_vivo(client, org_headers, db_session, planta)

    def test_t3_resolver_discrepancia_causa_una_sola_vez(
        self, client, org_headers, db_session, test_organization, wh_cv, wh_jm, escenario,
    ):
        """T3 — llegan 30 de 40: queda retenido y NO causa; al resolver se causa
        sobre lo final (30 x 50 % x $1.500 = $22.500), una sola vez."""
        planta = escenario["planta"]
        _con_planta(db_session, test_organization, planta)
        t = _dispatch(client, org_headers, wh_cv, wh_jm, escenario["mats"]["aporte"], 40)
        r = _receive_req(client, org_headers, t, 30)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "held_discrepancy"
        doc = {"kind": "transfer", "id": t["id"]}
        assert _doc_mms(db_session, doc) == []

        r = _resolve_req(client, org_headers, t)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "received"
        _assert_causado(db_session, doc, planta, "22500.00", wh_cv, "Maquila Intersede")
        assert _balance(db_session, planta) == Decimal("-22500.00")

    def test_t4_venta_de_puro_causa_el_diferencial_a_planta(
        self, client, org_headers, db_session, test_organization, wh_cv, wh_jm, escenario,
    ):
        """T4 — 20 kg de puro x $300; la respuesta no cambia (D7)."""
        planta = escenario["planta"]
        _con_planta(db_session, test_organization, planta)
        doc = _venta_puro(client, org_headers, escenario, wh_jm)
        assert Decimal(str(doc["body"]["crucible_amount"])) == Decimal("6000.00")
        _assert_causado(db_session, doc, planta, "6000.00", wh_cv, "Crisol Refinación")
        assert _balance(db_session, planta) == Decimal("-6000.00")

    @pytest.mark.parametrize("dtype, monto", [
        ("abono_material", "62400.00"),   # 50 kg x $1.248
        ("abono_bateria", "28300.00"),    # 50 kg x $566
    ])
    def test_t5_el_reparto_de_los_abonos_se_causa_a_planta(
        self, client, org_headers, db_session, test_organization, wh_cv, wh_jm, escenario,
        dtype, monto,
    ):
        planta = escenario["planta"]
        _con_planta(db_session, test_organization, planta)
        doc = _salida(client, org_headers, escenario, wh_jm, dtype, "crudo")
        assert Decimal(str(doc["body"]["plant_credit_amount"])) == Decimal(monto)
        _assert_causado(db_session, doc, planta, monto, wh_cv, "Maquila Intersede")
        assert _balance(db_session, planta) == -Decimal(monto)
        # la factura a Willard sigue saliendo igual: el setting solo toca la maquila
        assert len(_doc_mms(db_session, doc, "confirmed")) == 3

    def test_t6_retorno_de_dross_causa_a_planta(
        self, client, org_headers, db_session, test_organization, wh_cv, wh_jm, escenario,
    ):
        """T6 (G1) — la maquila del retorno va sobre el PLOMO: 3,5 x $1.500."""
        planta = escenario["planta"]
        _con_planta(db_session, test_organization, planta)
        doc = _dross(client, org_headers, escenario, wh_jm)
        assert Decimal(str(doc["body"]["maquila_amount"])) == Decimal("5250.00")
        _assert_causado(db_session, doc, planta, "5250.00", wh_cv, "Maquila Intersede")
        assert _balance(db_session, planta) == Decimal("-5250.00")


# ------------------------------------------------------------- anulacion ---

DOCS = {
    "traslado": lambda c, h, e, cv, jm: _traslado(c, h, e, cv, jm),
    "venta_puro": lambda c, h, e, cv, jm: _venta_puro(c, h, e, jm),
    "abono_material": lambda c, h, e, cv, jm: _salida(c, h, e, jm, "abono_material", "crudo"),
    "dross": lambda c, h, e, cv, jm: _dross(c, h, e, jm),
}


class TestAnulacion:

    @pytest.mark.parametrize("cual", list(DOCS))
    def test_t7_anular_devuelve_el_saldo_de_planta_exacto(
        self, client, org_headers, db_session, test_organization, wh_cv, wh_jm, escenario, cual,
    ):
        """T7 — ida y vuelta, con el invariante de #55 en PLANTA y en WILLARD
        (la Salida con factura mueve a los dos)."""
        planta, willard = escenario["planta"], escenario["willard"]
        _con_planta(db_session, test_organization, planta)
        willard_antes = _balance(db_session, willard)

        doc = DOCS[cual](client, org_headers, escenario, wh_cv, wh_jm)
        assert _balance(db_session, planta) < 0
        _corrido_igual_vivo(client, org_headers, db_session, planta)
        if doc["kind"] == "willard_delivery":
            _corrido_igual_vivo(client, org_headers, db_session, willard)

        _annul_doc(client, org_headers, doc)

        assert _balance(db_session, planta) == 0
        assert _maquila_mms(db_session, doc) == []
        anulados = _maquila_mms(db_session, doc, "annulled")
        assert [m.movement_type for m in anulados] == ["expense_accrual"]
        assert _corrido_igual_vivo(client, org_headers, db_session, planta) == 0
        if doc["kind"] == "willard_delivery":
            assert _corrido_igual_vivo(client, org_headers, db_session, willard) == willard_antes

    @pytest.mark.parametrize("cual, modulo", [
        ("traslado", "Traslados"),
        ("abono_material", "Salida"),
        ("dross", "Crisol"),
    ])
    def test_t8_el_causado_no_se_anula_desde_tesoreria(
        self, client, org_headers, db_session, test_organization, wh_cv, wh_jm, escenario,
        cual, modulo,
    ):
        """T8 (D5) — anularlo aqui borraria la deuda con el documento vivo."""
        planta = escenario["planta"]
        _con_planta(db_session, test_organization, planta)
        doc = DOCS[cual](client, org_headers, escenario, wh_cv, wh_jm)
        mm = _maquila_mms(db_session, doc)[0]
        antes = _balance(db_session, planta)

        r = client.post(f"{MM_URL}/{mm.id}/annul", headers=org_headers, json={"reason": "prueba"})

        assert r.status_code == 422, r.text
        assert modulo in r.json()["detail"]
        assert _balance(db_session, planta) == antes
        assert [m.id for m in _maquila_mms(db_session, doc)] == [mm.id]

    def test_t12_sin_setting_anular_una_salida_con_factura(
        self, client, org_headers, db_session, test_organization, wh_cv, wh_jm, escenario,
    ):
        """T12 — regresion de D4: la factura se revierte ahora por
        `_reverse_effects` y no a mano; el saldo de Willard vuelve igual."""
        willard = escenario["willard"]
        antes = _balance(db_session, willard)
        doc = _salida(client, org_headers, escenario, wh_jm, "abono_material", "crudo")
        _assert_par(db_session, doc, "62400.00", wh_cv, wh_jm)
        # 50 kg x ($2.097 + $37)
        assert _balance(db_session, willard) == antes + Decimal("106700.00")

        _annul_doc(client, org_headers, doc)

        assert _balance(db_session, willard) == antes
        assert _corrido_igual_vivo(client, org_headers, db_session, willard) == antes
        assert _doc_mms(db_session, doc, "confirmed") == []

    @pytest.mark.parametrize("cual", ["traslado", "abono_material", "dross"])
    @pytest.mark.parametrize("despues", ["quitado", "cambiado"])
    def test_t13_la_anulacion_lee_el_tercero_del_movimiento(
        self, client, org_headers, db_session, test_organization, wh_cv, wh_jm, escenario,
        cual, despues,
    ):
        """T13 (C3) — se causa con planta, despues el setting se quita (fase 2,
        D9) o apunta a otro tercero, y se anula: vuelve el saldo de la planta
        ORIGINAL y el otro tercero no se toca."""
        planta = escenario["planta"]
        _con_planta(db_session, test_organization, planta)
        doc = DOCS[cual](client, org_headers, escenario, wh_cv, wh_jm)
        assert _balance(db_session, planta) < 0

        otra = create_third_party_with_category(
            db_session, test_organization.id, "PLANTA NUEVA", "liability"
        )
        db_session.commit()
        if despues == "quitado":
            _set(db_session, test_organization, plant_third_party_id=None)
        else:
            _con_planta(db_session, test_organization, otra)

        _annul_doc(client, org_headers, doc)

        assert _balance(db_session, planta) == 0
        assert _balance(db_session, otra) == 0


# ------------------------------------------------- lo que sigue anulable ---

class TestTesoreriaSigueAnulando:
    """T8b (C2) — el guard es por LISTA CERRADA de `source_type`, no por
    "todo source_type no nulo"."""

    def test_t8b_un_causado_manual_a_planta_se_anula(
        self, client, org_headers, db_session, test_organization, planta,
    ):
        cat = ExpenseCategory(organization_id=test_organization.id, name="Varios planta")
        db_session.add(cat)
        db_session.commit()
        r = client.post(f"{MM_URL}/expense-accrual", headers=org_headers, json={
            "third_party_id": str(planta.id), "amount": 12345,
            "expense_category_id": str(cat.id), "date": "2026-07-10T12:00:00",
            "description": "Registrado a mano contra planta",
        })
        assert r.status_code == 201, r.text
        assert _balance(db_session, planta) == Decimal("-12345.00")

        r = client.post(f"{MM_URL}/{r.json()['id']}/annul", headers=org_headers,
                        json={"reason": "error de captura"})

        assert r.status_code == 200, r.text
        assert _balance(db_session, planta) == 0

    def test_t8b_la_comision_del_recolector_se_condona(
        self, client, org_headers, db_session, test_organization, wh_cv,
    ):
        """#83: anular en Tesoreria el accrual del recolector = condonarlo."""
        from app.utils.dates import business_today
        from datetime import timedelta

        org = test_organization.id
        supplier = create_third_party_with_category(db_session, org, "Proveedor", "material_supplier")
        collector = create_third_party_with_category(db_session, org, "Green Loop", "service_provider")
        mat = _mat(db_session, org, "CHAT-1", "Chatarra")
        db_session.add(MaterialKgProfile(organization_id=org, material_id=mat.id,
                                         compra_regular=True, willard_world="none",
                                         lead_product="none"))
        db_session.commit()
        fecha = (business_today() - timedelta(days=2)).isoformat()
        r = client.post(PURCHASES_URL, headers=org_headers, json={
            "supplier_id": str(supplier.id), "date": fecha, "warehouse_id": str(wh_cv.id),
            "lines": [{"material_id": str(mat.id), "warehouse_id": str(wh_cv.id),
                       "quantity": "100", "unit_price": "900"}],
        })
        assert r.status_code == 201, r.text
        r = client.patch(f"{PURCHASES_URL}/{r.json()['id']}/liquidate", headers=org_headers, json={
            "liquidation_date": fecha,
            "collector_commission": {"third_party_id": str(collector.id), "amount": "50000"},
        })
        assert r.status_code == 200, r.text
        db_session.expire_all()
        mm = db_session.execute(select(MoneyMovement).where(
            MoneyMovement.source_type == "collector_commission",
        )).scalar_one()
        assert _balance(db_session, collector) == Decimal("-50000.00")

        r = client.post(f"{MM_URL}/{mm.id}/annul", headers=org_headers, json={"reason": "condonada"})

        assert r.status_code == 200, r.text
        assert _balance(db_session, collector) == 0


# ------------------------------------------------------------ fail-closed ---

def _count(db, model, org_id):
    return db.execute(
        select(func.count()).select_from(model).where(model.organization_id == org_id)
    ).scalar_one()


def _foto(db, org_id):
    """Todo lo que un flujo podria escribir, leido en la sesion del test (cada
    request usa su propia sesion, asi que esto es "otra sesion")."""
    db.expire_all()
    foto = {
        m.__name__: _count(db, m, org_id)
        for m in (MoneyMovement, KgLedgerMovement, InventoryMovement, InventoryAdjustment,
                  Sale, CrucibleCharge, MaterialTransformation)
    }
    foto["saldos"] = dict(db.execute(
        select(ThirdParty.id, ThirdParty.current_balance).where(ThirdParty.organization_id == org_id)
    ).all())
    foto["traslados"] = dict(db.execute(
        select(Transfer.id, Transfer.status).where(Transfer.organization_id == org_id)
    ).all())
    foto["salidas"] = dict(db.execute(
        select(WillardDelivery.id, WillardDelivery.status).where(WillardDelivery.organization_id == org_id)
    ).all())
    return foto


def _preparar(camino, client, headers, esc, wh_cv, wh_jm):
    """Deja el documento a UN paso de emitir y devuelve ese paso."""
    if camino == "receive":
        t = _dispatch(client, headers, wh_cv, wh_jm, esc["mats"]["aporte"], 40)
        return lambda: _receive_req(client, headers, t, 40)
    if camino == "resolve":
        t = _dispatch(client, headers, wh_cv, wh_jm, esc["mats"]["aporte"], 40)
        assert _receive_req(client, headers, t, 30).json()["status"] == "held_discrepancy"
        return lambda: _resolve_req(client, headers, t)
    if camino == "venta_puro":
        _seed_stage(client, headers, esc["cuentas"]["intersede"].id, 50, "crisol")
        d = _create_delivery(client, headers, wh_jm, esc["willard"], esc["mats"]["puro"], "venta", "20")
        return lambda: _liquidate_req(client, headers, d)
    if camino == "abono":
        d = _create_delivery(client, headers, wh_jm, esc["willard"], esc["mats"]["crudo"],
                             "abono_material", "50")
        return lambda: _liquidate_req(client, headers, d)
    if camino == "dross":
        _prep_dross(client, headers, esc, wh_jm)
        return lambda: _charge_req(client, headers, wh_jm, esc["mats"]["dross"], 5, "dross_return")
    raise AssertionError(camino)


def _invalido(cual, db, org, org2):
    if cual == "malformado":
        return "no-es-un-uuid"
    if cual == "inexistente":
        return str(uuid4())
    if cual == "otra_org":
        tp = create_third_party_with_category(db, org2.id, "PLANTA OTRA ORG", "liability")
    elif cual == "inactivo":
        tp = create_third_party_with_category(db, org.id, "PLANTA INACTIVA", "liability", is_active=False)
    elif cual == "sistema":
        tp = create_third_party_with_category(db, org.id, "[Sistema] Planta", "liability",
                                              is_system_entity=True)
    elif cual == "sin_categoria":
        tp = create_third_party_with_category(db, org.id, "PLANTA CLIENTE", "customer")
    else:
        raise AssertionError(cual)
    db.commit()
    return str(tp.id)


class TestFailClosed:

    @pytest.mark.parametrize("invalido", [
        "malformado", "inexistente", "otra_org", "inactivo", "sistema", "sin_categoria",
    ])
    @pytest.mark.parametrize("camino", ["receive", "resolve", "venta_puro", "abono", "dross"])
    def test_t9_setting_invalido_422_y_nada_escrito(
        self, client, org_headers, db_session, test_organization, test_organization2,
        wh_cv, wh_jm, escenario, camino, invalido,
    ):
        """T9 (C5) — 422 que nombra el setting, sin 500, y NADA escrito: ni
        kilos, ni inventario, ni pesos, ni el estado del documento."""
        paso = _preparar(camino, client, org_headers, escenario, wh_cv, wh_jm)
        valor = _invalido(invalido, db_session, test_organization, test_organization2)
        _set(db_session, test_organization, plant_third_party_id=valor)
        antes = _foto(db_session, test_organization.id)

        r = paso()

        assert r.status_code == 422, r.text
        assert "plant_third_party_id" in r.json()["detail"]
        assert _foto(db_session, test_organization.id) == antes

    def test_el_payload_rechaza_un_id_malformado(self):
        """N4 — por el PATCH de sistema ni siquiera entra."""
        from pydantic import ValidationError

        from app.schemas.organization import OrgSettingsPayload

        with pytest.raises(ValidationError, match="plant_third_party_id"):
            OrgSettingsPayload(plant_third_party_id="no-es-un-uuid")
        tp_id = uuid4()
        assert OrgSettingsPayload(plant_third_party_id=str(tp_id).upper()).plant_third_party_id == str(tp_id)
        assert OrgSettingsPayload().plant_third_party_id is None


# ----------------------------------------------- flag y regimenes de gate ---

class TestRegimenesDeGate:
    """T10 (C4) — el setting cambia la FORMA de la emision, nunca SI se emite.
    Dos regimenes (F4a de #107): traslado, crisol y dross dependen del flag;
    el reparto de los abonos depende del TIPO e ignora el flag."""

    def test_t10_flag_apagado_los_gateados_no_emiten(
        self, client, org_headers, db_session, test_organization, wh_cv, wh_jm, escenario,
    ):
        planta = escenario["planta"]
        _con_planta(db_session, test_organization, planta)
        _set(db_session, test_organization, internal_maquila_enabled=False)

        traslado = _traslado(client, org_headers, escenario, wh_cv, wh_jm)
        venta = _venta_puro(client, org_headers, escenario, wh_jm)
        dross = _dross(client, org_headers, escenario, wh_jm)

        assert Decimal(str(venta["body"]["crucible_amount"])) == 0
        assert Decimal(str(dross["body"]["maquila_amount"])) == 0
        for doc in (traslado, venta, dross):
            assert _maquila_mms(db_session, doc) == []
        assert _balance(db_session, planta) == 0

    @pytest.mark.parametrize("dtype, monto", [
        ("abono_material", "62400.00"),
        ("abono_bateria", "28300.00"),
    ])
    def test_t10_flag_apagado_el_reparto_si_se_causa(
        self, client, org_headers, db_session, test_organization, wh_cv, wh_jm, escenario,
        dtype, monto,
    ):
        planta = escenario["planta"]
        _con_planta(db_session, test_organization, planta)
        _set(db_session, test_organization, internal_maquila_enabled=False)
        doc = _salida(client, org_headers, escenario, wh_jm, dtype, "crudo")
        _assert_causado(db_session, doc, planta, monto, wh_cv, "Maquila Intersede")


# --------------------------------------------------------------- reportes ---

def _pnl(client, headers, warehouse_id=None):
    params = {"date_from": "2026-07-12", "date_to": "2026-07-12"}
    if warehouse_id:
        params["warehouse_id"] = str(warehouse_id)
    r = client.get("/api/v1/reports/profit-and-loss", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()


class TestReportes:

    @pytest.mark.parametrize("con_setting", [False, True])
    def test_t11_balance_y_resultados(
        self, client, org_headers, db_session, test_organization, wh_cv, wh_jm, escenario,
        con_setting,
    ):
        """T11 (D8, O5) — con el setting la maquila es un PASIVO con planta y un
        gasto operativo del consolidado; por sede da $0, asi que CV + JM deja
        de cuadrar con el consolidado justo por la maquila. Sin el setting es
        el par: por sede se ve y el consolidado lo netea. Los dos lados del
        PAR, para que "funciona" y "lo rompi" no se vean iguales."""
        planta = escenario["planta"]
        if con_setting:
            _con_planta(db_session, test_organization, planta)
        _traslado(client, org_headers, escenario, wh_cv, wh_jm)  # $30.000 el 12-jul

        bs = client.get("/api/v1/reports/balance-sheet", headers=org_headers)
        assert bs.status_code == 200, bs.text
        cons = _pnl(client, org_headers)
        cv = _pnl(client, org_headers, wh_cv.id)
        jm = _pnl(client, org_headers, wh_jm.id)

        if con_setting:
            assert bs.json()["liabilities"]["liability_debt"] == 30000.0
            assert cons["operating_expenses"] == 30000.0
            assert cons["expenses_operating"] == 30000.0
            for p in (cons, cv, jm):
                assert p["internal_maquila_income"] == 0
                assert p["internal_maquila_expense"] == 0
            assert cv["operating_expenses"] == 0 and jm["operating_expenses"] == 0
            assert cons["net_profit"] == -30000.0
            assert cv["net_profit"] + jm["net_profit"] - cons["net_profit"] == 30000.0
        else:
            assert bs.json()["liabilities"]["liability_debt"] == 0
            assert cons["operating_expenses"] == 0
            assert cv["internal_maquila_expense"] == 30000.0
            assert jm["internal_maquila_income"] == 30000.0
            assert cons["net_profit"] == 0
            assert cv["net_profit"] + jm["net_profit"] == cons["net_profit"]
