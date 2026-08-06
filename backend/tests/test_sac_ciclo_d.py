"""
Tests SAC Ciclo D — recolector en la entrada + comision como GASTO
(plan-sac-ciclo-d-recolector-gasto.md v1.1, micro-QA GO condicionado).

Decision de producto (Daniel 2026-07-17): la comision del recolector (Green
Loop) NO se prorratea al costo del material (#30) — se causa como
expense_accrual (gasto operativo, categoria sistema 'Comisiones de
recoleccion'), SOLO en compras regulares (Q-02 Johana: nunca en willard).

Correccion Daniel 2026-07-18: el recolector se REGISTRA en AMBOS tipos (Green
Loop tambien recolecta willard) — en willard es informativo, la comision
existe SOLO al liquidar compras regulares (por construccion: willard no tiene
liquidacion de compra).

Cobertura:
- Estrella W-D2: el costo promedio queda IDENTICO (jamas entra al prorrateo).
- W-D1/test 7: data-gate D9 — sin el param, camino byte a byte.
- W-D3: P&L/Reporte de Gastos/balance/estado de cuenta por construccion.
- W-D4: cancel auto-anula solo confirmed (sin doble reversa).
- D-02: filtro source_type en el auto-annul.
- Willard: registra recolector SIN comision (confirmar willard -> cero MMs).
- Guards: no-service_provider 422, sin flag 422, edicion post-liquidacion 422
  (solo tipo compra — willard edita siempre).
"""
import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from app.models.expense_category import ExpenseCategory
from app.models.material import Material
from app.models.money_movement import MoneyMovement
from app.models.third_party import ThirdParty
from tests.integration_helpers import create_material, create_material_category, create_warehouse
from tests.conftest import create_third_party_with_category
from app.utils.dates import business_today

INBOUND_URL = "/api/v1/inbound-orders"
PURCHASES_URL = "/api/v1/purchases"
PROFILES_URL = "/api/v1/material-kg-profiles"
KG_URL = "/api/v1/kg-ledger"
FORMULAS_URL = "/api/v1/material-conversion-formulas"
REPORTS_URL = "/api/v1/reports"
MM_URL = "/api/v1/money-movements"


# ---------------------------------------------------------------------------
# Fixtures / helpers (patron test_sac_ciclo_c)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _enable_flag(db_session, test_organization, test_organization2):
    test_organization.settings = {"kg_ledger_enabled": True}
    test_organization2.settings = {"kg_ledger_enabled": True}
    db_session.commit()


@pytest.fixture
def wh_cv(db_session, test_organization):
    wh = create_warehouse(db_session, test_organization.id, "Circunvalar D")
    db_session.commit()
    return wh


@pytest.fixture
def supplier(db_session, test_organization):
    tp = create_third_party_with_category(
        db_session, test_organization.id, "Proveedor Ciclo D", "material_supplier"
    )
    db_session.commit()
    return tp


@pytest.fixture
def collector(db_session, test_organization):
    """Green Loop — recolector service_provider."""
    tp = create_third_party_with_category(
        db_session, test_organization.id, "Green Loop D", "service_provider"
    )
    db_session.commit()
    return tp


@pytest.fixture
def collector2(db_session, test_organization):
    tp = create_third_party_with_category(
        db_session, test_organization.id, "Recolector Dos", "service_provider"
    )
    db_session.commit()
    return tp


def _mat(db, org_id, code, unit="kg"):
    cat = create_material_category(db, org_id, f"Cat {code}")
    mat = create_material(db, org_id, code, f"Material {code}", cat.id)
    mat.default_unit = unit
    db.commit()
    return mat


def _set_profile(client, headers, material_id, *, compra_regular=False, willard_world="none"):
    resp = client.put(
        f"{PROFILES_URL}/{material_id}",
        headers=headers,
        json={"compra_regular": compra_regular, "willard_world": willard_world},
    )
    assert resp.status_code == 200, resp.text


@pytest.fixture
def mat_compra(db_session, test_organization, client, org_headers):
    mat = _mat(db_session, test_organization.id, "CHATARRA-D", unit="kg")
    _set_profile(client, org_headers, mat.id, compra_regular=True, willard_world="none")
    return mat


@pytest.fixture
def mat_bat(db_session, test_organization, client, org_headers):
    mat = _mat(db_session, test_organization.id, "BAT-D", unit="unidad")
    resp = client.post(
        FORMULAS_URL, headers=org_headers,
        json={"material_id": str(mat.id), "formula_type": "battery_to_lead",
              "parameters": {"kg_lead_per_unit": 2.5}},
    )
    assert resp.status_code == 201, resp.text
    _set_profile(client, org_headers, mat.id, willard_world="postconsumo")
    return mat


@pytest.fixture
def kg_bat_cv(client, org_headers, wh_cv, supplier):
    resp = client.post(
        f"{KG_URL}/accounts", headers=org_headers,
        json={
            "code": "W-BAT-D", "display_name": "Willard Baterias D",
            "account_type": "willard_baterias", "warehouse_id": str(wh_cv.id),
            "third_party_id": str(supplier.id),
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _past(days=2):
    return (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()


def _entrada_compra(client, headers, wh, tp, mat, qty="100", price="900", **extra):
    resp = client.post(
        INBOUND_URL, headers=headers,
        json={
            "inbound_type": "purchase",
            "warehouse_id": str(wh.id),
            "third_party_id": str(tp.id),
            "date": _past(),
            "lines": [{"material_id": str(mat.id), "quantity": qty, "unit_price": price}],
            **extra,
        },
    )
    return resp


def _liquidate(client, headers, purchase_id, **payload):
    return client.patch(
        f"{PURCHASES_URL}/{purchase_id}/liquidate",
        headers=headers,
        json={"liquidation_date": _past(), **payload},
    )


def _collector_accruals(db, purchase_id):
    db.expire_all()
    return db.query(MoneyMovement).filter(
        MoneyMovement.purchase_id == UUID(str(purchase_id)),
        MoneyMovement.movement_type == "expense_accrual",
        MoneyMovement.source_type == "collector_commission",
    ).all()


def _system_categories(db, org_id):
    db.expire_all()
    return db.query(ExpenseCategory).filter(
        ExpenseCategory.organization_id == org_id,
        ExpenseCategory.is_system_entity == True,  # noqa: E712
    ).all()


# ---------------------------------------------------------------------------
# Captura del recolector en la entrada
# ---------------------------------------------------------------------------

class TestCollectorCapture:
    def test_create_with_collector_exposes_in_responses(
        self, client, org_headers, db_session, wh_cv, supplier, mat_compra, collector,
    ):
        resp = _entrada_compra(
            client, org_headers, wh_cv, supplier, mat_compra,
            collector_id=str(collector.id),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["collector_id"] == str(collector.id)
        assert body["collector_name"] == "Green Loop D"

        # Detail de la entrada
        detail = client.get(f"{INBOUND_URL}/{body['id']}", headers=org_headers).json()
        assert detail["collector_name"] == "Green Loop D"

        # B1 enrich: la compra derivada expone el recolector (pre-carga de la
        # Liquidate page) — detail Y listado
        pd = client.get(f"{PURCHASES_URL}/{body['purchase_id']}", headers=org_headers).json()
        assert pd["collector_id"] == str(collector.id)
        assert pd["collector_name"] == "Green Loop D"

    def test_collector_on_willard_records_without_commission(
        self, client, org_headers, db_session, test_organization,
        wh_cv, supplier, mat_bat, kg_bat_cv, collector,
    ):
        """Correccion Daniel 2026-07-18: Green Loop tambien recolecta willard —
        el recolector SE REGISTRA (informativo) pero la comision existe SOLO
        al liquidar compras regulares. Confirmar willard: CERO gasto causado."""
        resp = client.post(
            INBOUND_URL, headers=org_headers,
            json={
                "inbound_type": "willard",
                "warehouse_id": str(wh_cv.id),
                "third_party_id": str(supplier.id),
                "date": _past(),
                "collector_id": str(collector.id),
                "lines": [{"material_id": str(mat_bat.id), "quantity": "10"}],
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["collector_name"] == "Green Loop D"

        # Confirmar (efectos willard) — NINGUNA comision nace
        confirm = client.post(
            f"{INBOUND_URL}/{body['id']}/confirm", headers=org_headers,
        )
        assert confirm.status_code == 200, confirm.text
        assert confirm.json()["collector_name"] == "Green Loop D"

        db_session.expire_all()
        mms = db_session.query(MoneyMovement).filter(
            MoneyMovement.organization_id == test_organization.id,
            MoneyMovement.source_type == "collector_commission",
        ).all()
        assert mms == []
        assert _system_categories(db_session, test_organization.id) == []
        tp = db_session.get(ThirdParty, collector.id)
        assert tp.current_balance == Decimal("0.00")

    def test_collector_editable_on_willard_anytime(
        self, client, org_headers, wh_cv, supplier, mat_bat, kg_bat_cv, collector,
    ):
        """Willard no tiene compra derivada -> el recolector (informativo) se
        edita siempre, incluso tras confirmar."""
        resp = client.post(
            INBOUND_URL, headers=org_headers,
            json={
                "inbound_type": "willard",
                "warehouse_id": str(wh_cv.id),
                "third_party_id": str(supplier.id),
                "date": _past(),
                "lines": [{"material_id": str(mat_bat.id), "quantity": "10"}],
            },
        )
        assert resp.status_code == 201, resp.text
        oid = resp.json()["id"]

        patch = client.patch(
            f"{INBOUND_URL}/{oid}", headers=org_headers,
            json={"collector_id": str(collector.id)},
        )
        assert patch.status_code == 200, patch.text
        assert patch.json()["collector_name"] == "Green Loop D"

        # Confirmar y seguir editando (informativo, sin efectos)
        client.post(f"{INBOUND_URL}/{oid}/confirm", headers=org_headers)
        remove = client.patch(
            f"{INBOUND_URL}/{oid}", headers=org_headers, json={"collector_id": None},
        )
        assert remove.status_code == 200, remove.text
        assert remove.json()["collector_id"] is None

    def test_collector_not_service_provider_422(
        self, client, org_headers, wh_cv, supplier, mat_compra,
    ):
        # El proveedor de materiales NO es service_provider -> 422
        resp = _entrada_compra(
            client, org_headers, wh_cv, supplier, mat_compra,
            collector_id=str(supplier.id),
        )
        assert resp.status_code == 422
        assert "Proveedor de Servicios" in resp.json()["detail"]

    def test_edit_collector_lifecycle(
        self, client, org_headers, wh_cv, supplier, mat_compra, collector, collector2,
    ):
        # Sin recolector al capturar -> se agrega editando (registered)
        resp = _entrada_compra(client, org_headers, wh_cv, supplier, mat_compra)
        assert resp.status_code == 201, resp.text
        oid = resp.json()["id"]
        pid = resp.json()["purchase_id"]

        patch = client.patch(
            f"{INBOUND_URL}/{oid}", headers=org_headers,
            json={"collector_id": str(collector.id)},
        )
        assert patch.status_code == 200, patch.text
        assert patch.json()["collector_name"] == "Green Loop D"

        # Cambiarlo (registered) -> OK
        patch2 = client.patch(
            f"{INBOUND_URL}/{oid}", headers=org_headers,
            json={"collector_id": str(collector2.id)},
        )
        assert patch2.status_code == 200
        assert patch2.json()["collector_name"] == "Recolector Dos"

        # Quitarlo con null explicito (registered) -> OK
        patch3 = client.patch(
            f"{INBOUND_URL}/{oid}", headers=org_headers, json={"collector_id": None},
        )
        assert patch3.status_code == 200
        assert patch3.json()["collector_id"] is None

        # Re-poner y liquidar la compra -> despues 422
        client.patch(
            f"{INBOUND_URL}/{oid}", headers=org_headers,
            json={"collector_id": str(collector.id)},
        )
        liq = _liquidate(client, org_headers, pid)
        assert liq.status_code == 200, liq.text

        blocked = client.patch(
            f"{INBOUND_URL}/{oid}", headers=org_headers,
            json={"collector_id": str(collector2.id)},
        )
        assert blocked.status_code == 422
        assert "no se puede cambiar" in blocked.json()["detail"]


# ---------------------------------------------------------------------------
# Efectos: gasto causado, jamas al costo
# ---------------------------------------------------------------------------

class TestCollectorCommissionEffects:
    def test_estrella_no_prorrateo_avg_cost_intact(
        self, client, org_headers, db_session, test_organization,
        wh_cv, supplier, mat_compra, collector,
    ):
        """W-D2: con comision de recolector el costo promedio es IDENTICO al
        de liquidar sin ella (con #30 seria price + comision/qty)."""
        resp = _entrada_compra(client, org_headers, wh_cv, supplier, mat_compra)
        pid = resp.json()["purchase_id"]

        liq = _liquidate(
            client, org_headers, pid,
            collector_commission={"third_party_id": str(collector.id), "amount": "50000"},
        )
        assert liq.status_code == 200, liq.text

        db_session.expire_all()
        mat = db_session.get(Material, mat_compra.id)
        # Prorrateo #30 habria dado 900 + 50000/100 = 1400. Gasto NO toca costo:
        assert mat.current_average_cost == Decimal("900.0000")

        # MM: expense_accrual sin cuenta, con firma D-01 completa
        accruals = _collector_accruals(db_session, pid)
        assert len(accruals) == 1
        mm = accruals[0]
        assert mm.account_id is None
        assert mm.status == "confirmed"
        assert mm.amount == Decimal("50000.00")
        assert mm.third_party_id == collector.id
        assert mm.source_type == "collector_commission"
        assert str(mm.source_id) == resp.json()["id"]  # entrada de origen
        assert mm.warehouse_id is not None  # header de la compra (D11)
        assert "Comisión recolección" in mm.description
        assert f"Entrada #{resp.json()['order_number']}" in mm.description

        # Categoria sistema INDIRECTA (decision Daniel: no entra al Costo Real)
        cat = db_session.get(ExpenseCategory, mm.expense_category_id)
        assert cat.is_system_entity is True
        assert cat.is_direct_expense is False
        assert cat.name == "Comisiones de recolección"

        # Saldo del recolector: le debemos (pasivo)
        tp = db_session.get(ThirdParty, collector.id)
        assert tp.current_balance == Decimal("-50000.00")

    def test_pnl_and_expenses_report_include(
        self, client, org_headers, db_session, wh_cv, supplier, mat_compra, collector,
    ):
        resp = _entrada_compra(client, org_headers, wh_cv, supplier, mat_compra)
        pid = resp.json()["purchase_id"]
        liq = _liquidate(
            client, org_headers, pid,
            collector_commission={"third_party_id": str(collector.id), "amount": "40000"},
        )
        assert liq.status_code == 200, liq.text

        date_from, date_to = _past(5), business_today().isoformat()
        pnl = client.get(
            f"{REPORTS_URL}/profit-and-loss",
            headers=org_headers,
            params={"date_from": date_from, "date_to": date_to},
        ).json()
        assert pnl["operating_expenses"] >= 40000
        match = [
            c for c in pnl["expenses_by_category"]
            if c["category_name"] == "Comisiones de recolección"
            and c["source_type"] == "expense_accrual"
        ]
        assert match and match[0]["total_amount"] == 40000.0
        assert match[0]["pnl_section"] == "operativo"

        # Reporte de Gastos #44 agrupado por categoria
        expenses = client.get(
            f"{REPORTS_URL}/expenses",
            headers=org_headers,
            params={"date_from": date_from, "date_to": date_to, "group_by": "category"},
        )
        assert expenses.status_code == 200, expenses.text
        assert "Comisiones de recolección" in expenses.text

    def test_statement_and_balance_detailed(
        self, client, org_headers, db_session, wh_cv, supplier, mat_compra, collector,
    ):
        resp = _entrada_compra(client, org_headers, wh_cv, supplier, mat_compra)
        pid = resp.json()["purchase_id"]
        liq = _liquidate(
            client, org_headers, pid,
            collector_commission={"third_party_id": str(collector.id), "amount": "30000"},
        )
        assert liq.status_code == 200, liq.text

        # Estado de cuenta del recolector: el evento aparece (es un MM normal)
        stmt = client.get(
            f"{MM_URL}/third-party/{collector.id}", headers=org_headers,
        ).json()
        descs = [i.get("description") or "" for i in stmt["items"]]
        assert any("Comisión recolección" in d for d in descs)
        assert stmt["current_balance"] == -30000.0

        # Balance detallado: clasifica en service_provider_payable (#32/#38)
        bd = client.get(f"{REPORTS_URL}/balance-detailed", headers=org_headers).json()
        section = bd["liabilities"].get("service_provider_payable")
        assert section is not None
        names = [i["name"] for i in section["items"]]
        assert "Green Loop D" in names

    def test_category_get_or_create_idempotent_h4(
        self, client, org_headers, db_session, test_organization,
        wh_cv, supplier, mat_compra, collector,
    ):
        """2 liquidaciones -> 1 categoria; matching H4 reusa una pre-existente
        sin acentos/casing en vez de duplicar."""
        # Pre-crear la categoria SIN acento y en minusculas (variacion H4)
        pre = ExpenseCategory(
            organization_id=test_organization.id,
            name="comisiones de recoleccion",
            is_direct_expense=False,
            is_system_entity=True,
        )
        db_session.add(pre)
        db_session.commit()
        pre_id = pre.id

        for _ in range(2):
            resp = _entrada_compra(client, org_headers, wh_cv, supplier, mat_compra)
            liq = _liquidate(
                client, org_headers, resp.json()["purchase_id"],
                collector_commission={"third_party_id": str(collector.id), "amount": "10000"},
            )
            assert liq.status_code == 200, liq.text

        cats = _system_categories(db_session, test_organization.id)
        assert len(cats) == 1  # reuso, cero duplicados
        assert cats[0].id == pre_id

        db_session.expire_all()
        mms = db_session.query(MoneyMovement).filter(
            MoneyMovement.source_type == "collector_commission",
            MoneyMovement.organization_id == test_organization.id,
        ).all()
        assert len(mms) == 2
        assert all(m.expense_category_id == pre_id for m in mms)

    def test_condonada_entrada_con_recolector_sin_comision(
        self, client, org_headers, db_session, test_organization,
        wh_cv, supplier, mat_compra, collector,
    ):
        """Liquidar SIN collector_commission aunque la entrada tenga recolector
        -> no se causa nada (condonada / no aplica)."""
        resp = _entrada_compra(
            client, org_headers, wh_cv, supplier, mat_compra,
            collector_id=str(collector.id),
        )
        pid = resp.json()["purchase_id"]
        liq = _liquidate(client, org_headers, pid)
        assert liq.status_code == 200, liq.text

        assert _collector_accruals(db_session, pid) == []
        assert _system_categories(db_session, test_organization.id) == []
        tp = db_session.get(ThirdParty, collector.id)
        assert tp.current_balance == Decimal("0.00")

    def test_without_flag_422(
        self, client, org_headers, db_session, test_organization,
        wh_cv, supplier, collector,
    ):
        """Org sin kg_ledger_enabled (tipo Costa): el param -> 422 (D9)."""
        mat = _mat(db_session, test_organization.id, "PLAIN-D")
        test_organization.settings = {"kg_ledger_enabled": False}
        db_session.commit()

        resp = client.post(
            PURCHASES_URL, headers=org_headers,
            json={
                "supplier_id": str(supplier.id),
                "date": _past(),
                "lines": [{
                    "material_id": str(mat.id), "warehouse_id": str(wh_cv.id),
                    "quantity": "10", "unit_price": "500",
                }],
            },
        )
        assert resp.status_code == 201, resp.text
        liq = _liquidate(
            client, org_headers, resp.json()["id"],
            collector_commission={"third_party_id": str(collector.id), "amount": "5000"},
        )
        assert liq.status_code == 422
        assert "no habilitado" in liq.json()["detail"]

    def test_byte_identical_without_param(
        self, client, org_headers, db_session, test_organization,
        wh_cv, supplier, mat_compra,
    ):
        """W-D1 guard: liquidar SIN el param -> cero MMs nuevos, efectos de
        siempre (avg = precio, saldo proveedor = -total)."""
        resp = _entrada_compra(client, org_headers, wh_cv, supplier, mat_compra)
        pid = resp.json()["purchase_id"]
        liq = _liquidate(client, org_headers, pid)
        assert liq.status_code == 200, liq.text

        db_session.expire_all()
        mat = db_session.get(Material, mat_compra.id)
        assert mat.current_average_cost == Decimal("900.0000")
        sup = db_session.get(ThirdParty, supplier.id)
        assert sup.current_balance == Decimal("-90000.00")
        mms = db_session.query(MoneyMovement).filter(
            MoneyMovement.purchase_id == UUID(str(pid)),
        ).all()
        assert mms == []  # sin pago inmediato ni accruals: cero movimientos

    def test_amount_invalid_422(
        self, client, org_headers, wh_cv, supplier, mat_compra, collector,
    ):
        resp = _entrada_compra(client, org_headers, wh_cv, supplier, mat_compra)
        pid = resp.json()["purchase_id"]
        for bad in ("0", "-100"):
            liq = _liquidate(
                client, org_headers, pid,
                collector_commission={"third_party_id": str(collector.id), "amount": bad},
            )
            assert liq.status_code == 422

    def test_liquidate_collector_not_service_provider_422(
        self, client, org_headers, wh_cv, supplier, mat_compra,
    ):
        resp = _entrada_compra(client, org_headers, wh_cv, supplier, mat_compra)
        liq = _liquidate(
            client, org_headers, resp.json()["purchase_id"],
            collector_commission={"third_party_id": str(supplier.id), "amount": "5000"},
        )
        assert liq.status_code == 422
        assert "Proveedor de Servicios" in liq.json()["detail"]

    def test_detail_exposes_collector_commission_total(
        self, client, org_headers, wh_cv, supplier, mat_compra, collector,
    ):
        """Addendum pruebas Daniel: el costo de recoleccion se ve en el detalle
        de la compra Y en la cara financiera de la entrada; anulada (cancel) ->
        None en ambos (condonada se oculta)."""
        resp = _entrada_compra(client, org_headers, wh_cv, supplier, mat_compra)
        oid, pid = resp.json()["id"], resp.json()["purchase_id"]

        # Antes de liquidar: None
        pd = client.get(f"{PURCHASES_URL}/{pid}", headers=org_headers).json()
        assert pd["collector_commission_total"] is None

        liq = _liquidate(
            client, org_headers, pid,
            collector_commission={"third_party_id": str(collector.id), "amount": "25000"},
        )
        assert liq.status_code == 200, liq.text

        pd = client.get(f"{PURCHASES_URL}/{pid}", headers=org_headers).json()
        assert pd["collector_commission_total"] == 25000.0
        od = client.get(f"{INBOUND_URL}/{oid}", headers=org_headers).json()
        assert od["collector_commission_total"] == 25000.0

        # Cancelar -> auto-annul -> el detalle la oculta (None)
        cancel = client.patch(f"{PURCHASES_URL}/{pid}/cancel", headers=org_headers)
        assert cancel.status_code == 200, cancel.text
        pd = client.get(f"{PURCHASES_URL}/{pid}", headers=org_headers).json()
        assert pd["collector_commission_total"] is None
        od = client.get(f"{INBOUND_URL}/{oid}", headers=org_headers).json()
        assert od["collector_commission_total"] is None


# ---------------------------------------------------------------------------
# Cancelacion: auto-annul round-trip (W-D4 + D-02)
# ---------------------------------------------------------------------------

class TestCollectorCancelRoundtrip:
    def _setup_liquidated(self, client, org_headers, wh_cv, supplier, mat_compra, collector):
        resp = _entrada_compra(client, org_headers, wh_cv, supplier, mat_compra)
        pid = resp.json()["purchase_id"]
        liq = _liquidate(
            client, org_headers, pid,
            collector_commission={"third_party_id": str(collector.id), "amount": "50000"},
        )
        assert liq.status_code == 200, liq.text
        return pid

    def test_cancel_auto_annuls_roundtrip(
        self, client, org_headers, db_session, wh_cv, supplier, mat_compra, collector,
    ):
        pid = self._setup_liquidated(
            client, org_headers, wh_cv, supplier, mat_compra, collector
        )
        # Derivada liquidada se cancela directo (fix deadlock Ciclo C)
        cancel = client.patch(f"{PURCHASES_URL}/{pid}/cancel", headers=org_headers)
        assert cancel.status_code == 200, cancel.text

        accruals = _collector_accruals(db_session, pid)
        assert len(accruals) == 1
        assert accruals[0].status == "annulled"
        assert "Cancelación compra" in accruals[0].annulled_reason

        # Round-trip exacto: el saldo del recolector vuelve al origen
        tp = db_session.get(ThirdParty, collector.id)
        assert tp.current_balance == Decimal("0.00")

    def test_cancel_after_manual_annul_noop(
        self, client, org_headers, db_session, wh_cv, supplier, mat_compra, collector,
    ):
        """W-D4: anulado a mano en Tesoreria primero (= condonar despues),
        el cancel NO lo re-anula ni duplica la reversa de saldo."""
        pid = self._setup_liquidated(
            client, org_headers, wh_cv, supplier, mat_compra, collector
        )
        mm_id = _collector_accruals(db_session, pid)[0].id

        annul = client.post(
            f"{MM_URL}/{mm_id}/annul", headers=org_headers,
            json={"reason": "Condonada por acuerdo"},
        )
        assert annul.status_code == 200, annul.text
        db_session.expire_all()
        assert db_session.get(ThirdParty, collector.id).current_balance == Decimal("0.00")

        cancel = client.patch(f"{PURCHASES_URL}/{pid}/cancel", headers=org_headers)
        assert cancel.status_code == 200, cancel.text

        db_session.expire_all()
        mm = db_session.get(MoneyMovement, mm_id)
        assert mm.status == "annulled"
        assert mm.annulled_reason == "Condonada por acuerdo"  # NO sobreescrita
        # Saldo NO doble-revertido: sigue en 0, no +50000
        assert db_session.get(ThirdParty, collector.id).current_balance == Decimal("0.00")

    def test_cancel_does_not_touch_manual_expense_accrual(
        self, client, org_headers, db_session, test_organization,
        wh_cv, supplier, mat_compra, collector,
    ):
        """D-02: el auto-annul filtra por source_type — un expense_accrual
        MANUAL asociado a la compra sobrevive la cancelacion."""
        pid = self._setup_liquidated(
            client, org_headers, wh_cv, supplier, mat_compra, collector
        )
        # Simular un accrual manual etiquetado a la compra (source_type NULL)
        from app.services.money_movement import money_movement as mm_service
        manual = mm_service._create_movement(
            db=db_session,
            organization_id=test_organization.id,
            movement_type="expense_accrual",
            amount=Decimal("7000"),
            account_id=None,
            date=datetime.now(timezone.utc),
            description="Accrual manual de prueba",
            third_party_id=collector.id,
            purchase_id=UUID(str(pid)),
        )
        db_session.commit()
        manual_id = manual.id

        cancel = client.patch(f"{PURCHASES_URL}/{pid}/cancel", headers=org_headers)
        assert cancel.status_code == 200, cancel.text

        db_session.expire_all()
        assert db_session.get(MoneyMovement, manual_id).status == "confirmed"
        # El de recolector si cayo
        accruals = _collector_accruals(db_session, pid)
        assert accruals[0].status == "annulled"


# ---------------------------------------------------------------------------
# Fix display avg (pruebas Daniel, foto BAT-08)
# ---------------------------------------------------------------------------

class TestMovementAvgDisplayWillard:
    """La columna Costo Prom. del historial lee del libro MCH: una recepcion
    willard entra a identidad D2 y la fila lo MUESTRA (promedio sin cambio) —
    antes una reconstruccion ingenua pintaba promedios que nunca existieron."""

    def test_willard_receipt_shows_unchanged_avg(
        self, client, org_headers, db_session, test_organization,
        wh_cv, supplier, mat_bat, kg_bat_cv,
    ):
        # Semilla de costo: ajuste increase 10 @ 500 -> avg 500 (escribe MCH)
        adj = client.post(
            "/api/v1/inventory/adjustments/increase", headers=org_headers,
            json={
                "material_id": str(mat_bat.id),
                "warehouse_id": str(wh_cv.id),
                "quantity": 10,
                "unit_cost": 500,
                "date": _past(3),
                "reason": "Semilla avg display",
            },
        )
        assert adj.status_code == 201, adj.text

        # Willard capturar + confirmar 8 unidades — identidad D2
        resp = client.post(
            INBOUND_URL, headers=org_headers,
            json={
                "inbound_type": "willard",
                "warehouse_id": str(wh_cv.id),
                "third_party_id": str(supplier.id),
                "date": _past(2),
                "lines": [{"material_id": str(mat_bat.id), "quantity": "8"}],
            },
        )
        assert resp.status_code == 201, resp.text
        conf = client.post(f"{INBOUND_URL}/{resp.json()['id']}/confirm", headers=org_headers)
        assert conf.status_code == 200, conf.text

        movs = client.get(
            "/api/v1/inventory/movements",
            params={"material_id": str(mat_bat.id)},
            headers=org_headers,
        ).json()["items"]
        by_type = {it["movement_type"]: it for it in movs}
        # La recepcion muestra el MISMO promedio que ya existia — cero cambio
        assert by_type["inbound_receipt"]["avg_cost_after"] == 500.0
        assert by_type["adjustment"]["avg_cost_after"] == 500.0

        # Y el promedio VIVO coincide (identidad real, no solo display)
        db_session.expire_all()
        mat = db_session.get(Material, mat_bat.id)
        assert float(mat.current_average_cost) == 500.0
