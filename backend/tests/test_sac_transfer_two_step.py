"""
Tests SAC E3.1 — Traslados dos pasos + maquila intersede
(plan-sac-e3-1-traslados-maquila.md v1.1).

Bloqueantes clave:
- B1 guardián: recepción con merma → decrease en tránsito (adjustment_net),
  avg org-wide INTACTO y CERO cost_adjustment en cualquier tabla (invariante 1).
- N2: multi-línea tolerancia mixta (A emite / B retiene en la MISMA recepción).
- N3: recibido>despachado → held SIEMPRE; resolve con excedente → increase
  identidad D2 en destino, tránsito==0 (N-a).
- M2: anular con material ya vendido → 200 + warning, NO 400 (desviación declarada).
- E9: par se anula desde el traslado; annul() de Tesorería → 422.
- Gating E10 (4 combinaciones) + guard operar-contra-tránsito (E12).
"""
import pytest
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, func

from app.models.inventory_adjustment import InventoryAdjustment
from app.models.inventory_movement import InventoryMovement
from app.models.kg_ledger import KgLedgerAccount, KgLedgerMovement
from app.models.material import Material
from app.models.money_movement import MoneyMovement
from app.models.organization import Organization
from app.models.warehouse import Warehouse
from app.models.exception_task import DiscrepancyTask
from app.models.service_tariff import ServiceTariff
from app.models.transfer import Transfer
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    create_material,
    create_material_category,
    create_warehouse,
)

TRANSFERS_URL = "/api/v1/transfers"
FORMULAS_URL = "/api/v1/material-conversion-formulas"
ADJUST_URL = "/api/v1/inventory/adjustments"

SEED_DATE = "2026-07-01T12:00:00"
DISPATCH_DATE = "2026-07-10T12:00:00"
RECEIPT_DATE = "2026-07-12T12:00:00"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _enable_flags(db_session, test_organization):
    test_organization.settings = {
        "kg_ledger_enabled": True,
        "two_step_transfers_enabled": True,
        "internal_maquila_enabled": True,
    }
    db_session.commit()


@pytest.fixture
def wh_cv(db_session, test_organization):
    wh = create_warehouse(db_session, test_organization.id, "Circunvalar")
    db_session.commit()
    return wh


@pytest.fixture
def wh_bog(db_session, test_organization):
    wh = create_warehouse(db_session, test_organization.id, "Bogota")
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


@pytest.fixture
def intersede_account(db_session, test_organization):
    acc = KgLedgerAccount(
        organization_id=test_organization.id,
        code="INTERSEDE",
        display_name="Intersede CV/BOG → JM",
        account_type="intersede",
        is_active=True,
    )
    db_session.add(acc)
    db_session.commit()
    return acc


@pytest.fixture
def maquila_tariff(db_session, test_organization, test_user):
    tariff = ServiceTariff(
        organization_id=test_organization.id,
        tariff_code="maquila_intersede_cv_jm",
        unit_price_cop=Decimal("1500.00"),
        unit="per_kg_lead",
        created_by=test_user.id,
    )
    db_session.add(tariff)
    db_session.commit()
    return tariff


def _mat(db, org_id, code):
    cat = create_material_category(db, org_id, f"Cat {code}")
    mat = create_material(db, org_id, code, f"Material {code}", cat.id)
    mat.default_unit = "kg"
    db.commit()
    return mat


def _post_formula(client, headers, material_id, pct=0.5):
    resp = client.post(
        FORMULAS_URL,
        headers=headers,
        json={
            "material_id": str(material_id),
            "formula_type": "drosses_to_lead",
            "parameters": {"lead_percentage": pct},
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def mat_contrib(db_session, test_organization, client, org_headers, wh_cv):
    """Aportante (fórmula 50%) con 100 kg @ $1.000 en CV."""
    mat = _mat(db_session, test_organization.id, "DROSS-T")
    _post_formula(client, org_headers, mat.id, 0.5)
    _seed_stock(client, org_headers, mat.id, wh_cv.id, 100, 1000)
    return mat


@pytest.fixture
def mat_simple(db_session, test_organization, client, org_headers, wh_cv):
    """No aportante (sin fórmula) con 100 kg @ $500 en CV."""
    mat = _mat(db_session, test_organization.id, "CHAT-T")
    _seed_stock(client, org_headers, mat.id, wh_cv.id, 100, 500)
    return mat


def _seed_stock(client, headers, material_id, warehouse_id, qty, cost):
    resp = client.post(
        f"{ADJUST_URL}/increase",
        headers=headers,
        json={
            "material_id": str(material_id),
            "warehouse_id": str(warehouse_id),
            "quantity": qty,
            "unit_cost": cost,
            "date": SEED_DATE,
            "reason": "Seed stock test traslados",
        },
    )
    assert resp.status_code in (200, 201), resp.text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dispatch(client, headers, wh_from, wh_to, lines, date=DISPATCH_DATE, expect=201):
    resp = client.post(
        TRANSFERS_URL,
        headers=headers,
        json={
            "from_warehouse_id": str(wh_from.id),
            "to_warehouse_id": str(wh_to.id),
            "dispatch_date": date,
            "lines": lines,
        },
    )
    assert resp.status_code == expect, resp.text
    return resp.json()


def _receive(client, headers, transfer, recv_by_index, date=RECEIPT_DATE, expect=200):
    lines = [
        {"transfer_line_id": transfer["lines"][i]["id"], "quantity_received": qty}
        for i, qty in recv_by_index.items()
    ]
    resp = client.post(
        f"{TRANSFERS_URL}/{transfer['id']}/receive",
        headers=headers,
        json={"lines": lines, "receipt_date": date},
    )
    assert resp.status_code == expect, resp.text
    return resp.json()


def _wh_stock(db, org_id, material_id, warehouse_id) -> Decimal:
    val = db.scalar(
        select(func.coalesce(func.sum(InventoryMovement.quantity), 0)).where(
            InventoryMovement.organization_id == org_id,
            InventoryMovement.material_id == material_id,
            InventoryMovement.warehouse_id == warehouse_id,
        )
    )
    return Decimal(str(val or 0))


def _kg_balance(db, org_id, account_id) -> Decimal:
    val = db.scalar(
        select(func.coalesce(func.sum(KgLedgerMovement.delta_kg), 0)).where(
            KgLedgerMovement.organization_id == org_id,
            KgLedgerMovement.account_id == account_id,
            KgLedgerMovement.status == "confirmed",
        )
    )
    return Decimal(str(val or 0))


def _maquila_mms(db, org_id, status="confirmed"):
    return db.execute(
        select(MoneyMovement).where(
            MoneyMovement.organization_id == org_id,
            MoneyMovement.movement_type.in_(
                ["internal_maquila_expense", "internal_maquila_income"]
            ),
            MoneyMovement.status == status,
        )
    ).scalars().all()


# ---------------------------------------------------------------------------
# Gating (E10 — 4 combinaciones)
# ---------------------------------------------------------------------------

class TestTransferGating:
    def test_flag_off_router_403(self, client, org_headers, db_session, test_organization, wh_cv, wh_jm):
        test_organization.settings = {"kg_ledger_enabled": True}
        db_session.commit()
        resp = client.get(TRANSFERS_URL, headers=org_headers)
        assert resp.status_code == 403

    def test_two_step_on_maquila_off_emits_kg_without_pair(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_contrib,
    ):
        test_organization.settings = {
            "kg_ledger_enabled": True,
            "two_step_transfers_enabled": True,
            "internal_maquila_enabled": False,
        }
        db_session.commit()
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        _receive(client, org_headers, t, {0: 40})
        assert _kg_balance(db_session, test_organization.id, intersede_account.id) == Decimal("20")
        assert _maquila_mms(db_session, test_organization.id) == []

    def test_full_flow_creates_pair(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_contrib,
    ):
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        _receive(client, org_headers, t, {0: 40})
        mms = _maquila_mms(db_session, test_organization.id)
        assert len(mms) == 2

    def test_one_step_transfer_intact_without_flag(
        self, client, org_headers, db_session, test_organization, wh_cv, wh_jm, mat_simple,
    ):
        """No-regresión: 1-paso sigue funcionando (flag off) contra bodegas normales."""
        test_organization.settings = {"kg_ledger_enabled": True}
        db_session.commit()
        resp = client.post(
            f"{ADJUST_URL}/warehouse-transfer",
            headers=org_headers,
            json={
                "material_id": str(mat_simple.id),
                "source_warehouse_id": str(wh_cv.id),
                "destination_warehouse_id": str(wh_jm.id),
                "quantity": 10,
                "date": DISPATCH_DATE,
                "reason": "Traslado 1-paso",
            },
        )
        assert resp.status_code in (200, 201), resp.text

    def test_rbac_viewer_cannot_dispatch(
        self, client, org_headers2, db_session, test_organization2,
    ):
        test_organization2.settings = {"two_step_transfers_enabled": True}
        db_session.commit()
        resp = client.post(
            TRANSFERS_URL,
            headers=org_headers2,
            json={
                "from_warehouse_id": "00000000-0000-0000-0000-000000000001",
                "to_warehouse_id": "00000000-0000-0000-0000-000000000002",
                "lines": [{"material_id": "00000000-0000-0000-0000-000000000003",
                           "quantity_dispatched": 1}],
            },
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Despacho
# ---------------------------------------------------------------------------

class TestTransferDispatch:
    def test_dispatch_happy_path_zero_kg_zero_pesos(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, wh_transit, intersede_account, mat_contrib,
    ):
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        assert t["status"] == "dispatched"
        assert t["transfer_number"] == 1
        assert t["transit_warehouse_id"] == str(wh_transit.id)
        line = t["lines"][0]
        assert line["is_contributor"] is True
        assert float(line["unit_cost"]) == 1000.0
        assert line["effects_emitted"] is False
        # Fisico: CV 60, transito 40
        assert _wh_stock(db_session, test_organization.id, mat_contrib.id, wh_cv.id) == Decimal("60")
        assert _wh_stock(db_session, test_organization.id, mat_contrib.id, wh_transit.id) == Decimal("40")
        # CERO kg, CERO pesos
        assert _kg_balance(db_session, test_organization.id, intersede_account.id) == 0
        assert _maquila_mms(db_session, test_organization.id) == []
        # Avg intacto (invariante 1)
        db_session.refresh(mat_contrib)
        assert mat_contrib.current_average_cost == Decimal("1000.0000")

    def test_dispatch_insufficient_stock_warns(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib,
    ):
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 500}])
        assert any("insuficiente" in w for w in t["warnings"])

    def test_dispatch_same_origin_destination_400(
        self, client, org_headers, wh_cv, mat_contrib,
    ):
        _dispatch(client, org_headers, wh_cv, wh_cv,
                  [{"material_id": str(mat_contrib.id), "quantity_dispatched": 10}],
                  expect=400)

    def test_dispatch_no_transit_route_400(
        self, client, org_headers, wh_cv, wh_bog, mat_contrib,
    ):
        """Destino sin bodega de transito ruteada → 400 guía."""
        resp = client.post(
            TRANSFERS_URL,
            headers=org_headers,
            json={
                "from_warehouse_id": str(wh_cv.id),
                "to_warehouse_id": str(wh_bog.id),
                "dispatch_date": DISPATCH_DATE,
                "lines": [{"material_id": str(mat_contrib.id), "quantity_dispatched": 10}],
            },
        )
        assert resp.status_code == 400
        assert "tránsito" in resp.json()["detail"]

    def test_dispatch_future_date_400(
        self, client, org_headers, wh_cv, wh_jm, wh_transit, mat_contrib,
    ):
        _dispatch(client, org_headers, wh_cv, wh_jm,
                  [{"material_id": str(mat_contrib.id), "quantity_dispatched": 10}],
                  date="2030-01-01T12:00:00", expect=400)

    def test_formula_snapshot_at_dispatch(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_contrib,
    ):
        """E7: cambiar la fórmula a mitad de traslado NO altera el kg (snapshot)."""
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        # Nueva fórmula vigente 80% DESPUÉS del despacho
        _post_formula(client, org_headers, mat_contrib.id, 0.8)
        _receive(client, org_headers, t, {0: 40})
        # kg = 40 × 0.5 (factor del despacho), NO 40 × 0.8
        assert _kg_balance(db_session, test_organization.id, intersede_account.id) == Decimal("20")


# ---------------------------------------------------------------------------
# Recepción
# ---------------------------------------------------------------------------

class TestTransferReceive:
    def test_receive_exact_full_effects(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_contrib, test_user,
    ):
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        r = _receive(client, org_headers, t, {0: 40})
        assert r["status"] == "received"
        line = r["lines"][0]
        assert line["effects_emitted"] is True
        assert float(line["kg_lead_equivalent"]) == 20.0
        assert float(line["maquila_amount"]) == 30000.0  # 20 kg × 1500

        # Fisico: transito 0, JM 40
        assert _wh_stock(db_session, test_organization.id, mat_contrib.id, wh_transit.id) == 0
        assert _wh_stock(db_session, test_organization.id, mat_contrib.id, wh_jm.id) == Decimal("40")

        # Par simétrico: NULL/NULL, warehouses correctos, enlazado
        mms = _maquila_mms(db_session, test_organization.id)
        assert len(mms) == 2
        by_type = {m.movement_type: m for m in mms}
        exp = by_type["internal_maquila_expense"]
        inc = by_type["internal_maquila_income"]
        assert exp.amount == inc.amount == Decimal("30000.00")
        assert exp.account_id is None and exp.third_party_id is None
        assert inc.account_id is None and inc.third_party_id is None
        assert exp.warehouse_id == wh_cv.id
        assert inc.warehouse_id == wh_jm.id
        assert exp.transfer_pair_id == inc.id and inc.transfer_pair_id == exp.id
        assert exp.source_type == "transfer"
        assert exp.expense_category_id is not None  # categoria sistema
        assert inc.expense_category_id is None

    def test_receive_merma_within_tolerance_b1_guardian(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_contrib,
    ):
        """B1 GUARDIÁN: merma → decrease en tránsito (adjustment_net), avg
        INTACTO y CERO cost_adjustment en cualquier tabla (invariante 1)."""
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        r = _receive(client, org_headers, t, {0: 39})  # merma 1 kg = 2.5% ≤ 5%
        assert r["status"] == "received"

        # Tránsito en CERO (E8)
        assert _wh_stock(db_session, test_organization.id, mat_contrib.id, wh_transit.id) == 0
        assert _wh_stock(db_session, test_organization.id, mat_contrib.id, wh_jm.id) == Decimal("39")

        # Merma = decrease hijo con FK transfer_id
        adj = db_session.execute(
            select(InventoryAdjustment).where(
                InventoryAdjustment.transfer_id == t["id"],
            )
        ).scalar_one()
        assert adj.adjustment_type == "decrease"
        assert adj.quantity == Decimal("-1.0000")
        assert adj.status == "confirmed"
        assert "Merma traslado #1" in adj.reason

        # Invariante 1: avg intacto + CERO cost_adjustment
        db_session.refresh(mat_contrib)
        assert mat_contrib.current_average_cost == Decimal("1000.0000")
        assert adj.cost_adjustment == 0
        # Sin MCH nuevo del traslado (decrease es MCH-silencioso)

        # kg sobre lo RECIBIDO (la verdad)
        assert _kg_balance(db_session, test_organization.id, intersede_account.id) == Decimal("19.5")

    def test_receive_out_of_tolerance_holds_effects(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_contrib,
    ):
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        r = _receive(client, org_headers, t, {0: 30})  # -25% >> 5%
        assert r["status"] == "held_discrepancy"
        line = r["lines"][0]
        assert line["effects_emitted"] is False
        assert line["discrepancy_task_id"] is not None
        # Solo físico entró (30); tránsito retiene 10
        assert _wh_stock(db_session, test_organization.id, mat_contrib.id, wh_jm.id) == Decimal("30")
        assert _wh_stock(db_session, test_organization.id, mat_contrib.id, wh_transit.id) == Decimal("10")
        # Sin kg ni maquila
        assert _kg_balance(db_session, test_organization.id, intersede_account.id) == 0
        assert _maquila_mms(db_session, test_organization.id) == []
        task = db_session.get(DiscrepancyTask, line["discrepancy_task_id"])
        assert task.severity == "high"
        assert task.status == "open"

    def test_receive_zero_is_critical(
        self, client, org_headers, db_session,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_contrib,
    ):
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        r = _receive(client, org_headers, t, {0: 0})
        assert r["status"] == "held_discrepancy"
        task = db_session.get(DiscrepancyTask, r["lines"][0]["discrepancy_task_id"])
        assert task.severity == "critical"

    def test_receive_over_dispatched_always_held(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_contrib,
    ):
        """N3: recibido>despachado → held SIEMPRE aunque variance ≤ tolerancia."""
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        r = _receive(client, org_headers, t, {0: 41})  # +2.5% dentro de 5% numérico
        assert r["status"] == "held_discrepancy"
        # Físico capado a lo despachado → tránsito CERO, sin negativo
        assert _wh_stock(db_session, test_organization.id, mat_contrib.id, wh_transit.id) == 0
        assert _wh_stock(db_session, test_organization.id, mat_contrib.id, wh_jm.id) == Decimal("40")
        assert _kg_balance(db_session, test_organization.id, intersede_account.id) == 0

    def test_receive_multiline_mixed_tolerance(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff,
        mat_contrib, mat_simple,
    ):
        """N2: línea A dentro (emite) + línea B fuera (retiene) misma recepción."""
        t = _dispatch(client, org_headers, wh_cv, wh_jm, [
            {"material_id": str(mat_contrib.id), "quantity_dispatched": 40},
            {"material_id": str(mat_simple.id), "quantity_dispatched": 50},
        ])
        r = _receive(client, org_headers, t, {0: 40, 1: 30})  # B: -40% fuera
        assert r["status"] == "held_discrepancy"
        by_mat = {ln["material_id"]: ln for ln in r["lines"]}
        line_a = by_mat[str(mat_contrib.id)]
        line_b = by_mat[str(mat_simple.id)]
        assert line_a["effects_emitted"] is True
        assert line_b["effects_emitted"] is False
        assert line_b["discrepancy_task_id"] is not None
        # A emitió kg (aportante); B no era aportante pero quedó retenida
        assert _kg_balance(db_session, test_organization.id, intersede_account.id) == Decimal("20")

    def test_tolerance_boundary_inclusive(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_contrib,
    ):
        """variance == tolerance exacta (5%) → dentro (<=, quantize 4 dec)."""
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        r = _receive(client, org_headers, t, {0: 38})  # 2/40 = 5.00% exacto
        assert r["status"] == "received"

    def test_receive_missing_intersede_account_400(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, wh_transit, maquila_tariff, mat_contrib,
    ):
        """Fail-fast ANTES de tocar nada: sin cuenta intersede → 400 y cero efectos."""
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        resp = client.post(
            f"{TRANSFERS_URL}/{t['id']}/receive",
            headers=org_headers,
            json={"lines": [{"transfer_line_id": t["lines"][0]["id"], "quantity_received": 40}],
                  "receipt_date": RECEIPT_DATE},
        )
        assert resp.status_code == 400
        assert "intersede" in resp.json()["detail"]
        # Nada entró a JM (rollback/fail-fast)
        assert _wh_stock(db_session, test_organization.id, mat_contrib.id, wh_jm.id) == 0

    def test_receive_missing_tariff_400(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, wh_transit, intersede_account, mat_contrib,
    ):
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        resp = client.post(
            f"{TRANSFERS_URL}/{t['id']}/receive",
            headers=org_headers,
            json={"lines": [{"transfer_line_id": t["lines"][0]["id"], "quantity_received": 40}],
                  "receipt_date": RECEIPT_DATE},
        )
        assert resp.status_code == 400
        assert "maquila_intersede_cv_jm" in resp.json()["detail"]

    def test_non_contributor_no_kg_no_pair(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_simple,
    ):
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat_simple.id), "quantity_dispatched": 50}])
        assert t["lines"][0]["is_contributor"] is False
        r = _receive(client, org_headers, t, {0: 50})
        assert r["status"] == "received"
        assert _kg_balance(db_session, test_organization.id, intersede_account.id) == 0
        assert _maquila_mms(db_session, test_organization.id) == []

    def test_receive_already_received_400(
        self, client, org_headers,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_contrib,
    ):
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        _receive(client, org_headers, t, {0: 40})
        _receive(client, org_headers, t, {0: 40}, expect=400)

    def test_receive_partial_lines_400(
        self, client, org_headers,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff,
        mat_contrib, mat_simple,
    ):
        """Q-E3.1-b default: atómica — request sin todas las líneas → 400."""
        t = _dispatch(client, org_headers, wh_cv, wh_jm, [
            {"material_id": str(mat_contrib.id), "quantity_dispatched": 40},
            {"material_id": str(mat_simple.id), "quantity_dispatched": 50},
        ])
        _receive(client, org_headers, t, {0: 40}, expect=400)

    def test_bog_to_jm_expense_warehouse_bog(
        self, client, org_headers, db_session, test_organization,
        wh_bog, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_contrib,
    ):
        _seed_stock(client, org_headers, mat_contrib.id, wh_bog.id, 100, 1000)
        t = _dispatch(client, org_headers, wh_bog, wh_jm,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        _receive(client, org_headers, t, {0: 40})
        mms = _maquila_mms(db_session, test_organization.id)
        exp = next(m for m in mms if m.movement_type == "internal_maquila_expense")
        assert exp.warehouse_id == wh_bog.id


# ---------------------------------------------------------------------------
# Resolución de discrepancias
# ---------------------------------------------------------------------------

class TestTransferResolve:
    def _held(self, client, org_headers, wh_cv, wh_jm, mat, recv=30, disp=40):
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat.id), "quantity_dispatched": disp}])
        r = _receive(client, org_headers, t, {0: recv})
        assert r["status"] == "held_discrepancy"
        return r

    def _resolve(self, client, headers, transfer, resolution, final=None, expect=200):
        line = {"transfer_line_id": transfer["lines"][0]["id"], "resolution": resolution}
        if final is not None:
            line["final_quantity"] = final
        resp = client.post(
            f"{TRANSFERS_URL}/{transfer['id']}/resolve",
            headers=headers,
            json={"lines": [line], "notes": "Resolución de prueba"},
        )
        assert resp.status_code == expect, resp.text
        return resp.json()

    def test_resolve_justify_emits_on_received(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_contrib,
    ):
        t = self._held(client, org_headers, wh_cv, wh_jm, mat_contrib)
        r = self._resolve(client, org_headers, t, "justify")
        assert r["status"] == "received"
        # Merma 10 → tránsito CERO; kg sobre 30
        assert _wh_stock(db_session, test_organization.id, mat_contrib.id, wh_transit.id) == 0
        assert _kg_balance(db_session, test_organization.id, intersede_account.id) == Decimal("15")
        task = db_session.get(DiscrepancyTask, t["lines"][0]["discrepancy_task_id"])
        assert task.status == "justified"
        # Avg intacto (B1 sigue rigiendo en resolve)
        db_session.refresh(mat_contrib)
        assert mat_contrib.current_average_cost == Decimal("1000.0000")

    def test_resolve_correct_with_arqueo(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_contrib,
    ):
        t = self._held(client, org_headers, wh_cv, wh_jm, mat_contrib)
        r = self._resolve(client, org_headers, t, "correct", final=35)
        assert r["status"] == "received"
        # Físico ajustado por delta: JM 35, tránsito 0 (merma 5)
        assert _wh_stock(db_session, test_organization.id, mat_contrib.id, wh_jm.id) == Decimal("35")
        assert _wh_stock(db_session, test_organization.id, mat_contrib.id, wh_transit.id) == 0
        assert _kg_balance(db_session, test_organization.id, intersede_account.id) == Decimal("17.5")
        task = db_session.get(DiscrepancyTask, t["lines"][0]["discrepancy_task_id"])
        assert task.status == "corrected"

    def test_resolve_correct_requires_final_quantity(
        self, client, org_headers,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_contrib,
    ):
        t = self._held(client, org_headers, wh_cv, wh_jm, mat_contrib)
        self._resolve(client, org_headers, t, "correct", expect=400)

    def test_resolve_excess_enters_identity_d2(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_contrib,
    ):
        """N3/N-a: excedente → increase en DESTINO identidad D2 (avg intacto),
        tránsito == 0, kg sobre final."""
        t = self._held(client, org_headers, wh_cv, wh_jm, mat_contrib, recv=41, disp=40)
        r = self._resolve(client, org_headers, t, "justify")
        assert r["status"] == "received"
        # JM = 40 (tránsito) + 1 (increase) = 41; tránsito 0 (N-a: sin doble entrada)
        assert _wh_stock(db_session, test_organization.id, mat_contrib.id, wh_transit.id) == 0
        assert _wh_stock(db_session, test_organization.id, mat_contrib.id, wh_jm.id) == Decimal("41")
        # Increase hijo identidad D2: adjustment 0, avg intacto
        adj = db_session.execute(
            select(InventoryAdjustment).where(
                InventoryAdjustment.transfer_id == t["id"],
                InventoryAdjustment.adjustment_type == "increase",
            )
        ).scalar_one()
        assert adj.cost_adjustment == 0
        db_session.refresh(mat_contrib)
        assert mat_contrib.current_average_cost == Decimal("1000.0000")
        # kg sobre lo recibido final (41 × 0.5)
        assert _kg_balance(db_session, test_organization.id, intersede_account.id) == Decimal("20.5")

    def test_resolve_non_held_400(
        self, client, org_headers,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_contrib,
    ):
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        self._resolve(client, org_headers, t, "justify", expect=400)


# ---------------------------------------------------------------------------
# Anulación (cascade E9)
# ---------------------------------------------------------------------------

class TestTransferAnnul:
    def _annul(self, client, headers, transfer_id, expect=200):
        resp = client.post(
            f"{TRANSFERS_URL}/{transfer_id}/annul",
            headers=headers,
            json={"reason": "Anulación de prueba"},
        )
        assert resp.status_code == expect, resp.text
        return resp.json()

    def test_annul_received_full_cascade(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_contrib,
    ):
        """Cascade completo: física restaurada, merma anulada, kg anulados,
        par anulado — round-trip al estado pre-traslado."""
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        _receive(client, org_headers, t, {0: 39})  # con merma 1
        r = self._annul(client, org_headers, t["id"])
        assert r["status"] == "annulled"

        org = test_organization.id
        # Física restaurada: CV 100, JM 0, tránsito 0
        assert _wh_stock(db_session, org, mat_contrib.id, wh_cv.id) == Decimal("100")
        assert _wh_stock(db_session, org, mat_contrib.id, wh_jm.id) == 0
        assert _wh_stock(db_session, org, mat_contrib.id, wh_transit.id) == 0
        # Stock global restaurado (la merma anulada devolvió su kg)
        db_session.refresh(mat_contrib)
        assert mat_contrib.current_stock_liquidated == Decimal("100")
        # Merma hija anulada
        adj = db_session.execute(
            select(InventoryAdjustment).where(InventoryAdjustment.transfer_id == t["id"])
        ).scalar_one()
        assert adj.status == "annulled"
        # kg anulados
        assert _kg_balance(db_session, org, intersede_account.id) == 0
        # Par anulado (y NO via annul() — el guard lo impediría)
        assert _maquila_mms(db_session, org, status="confirmed") == []
        assert len(_maquila_mms(db_session, org, status="annulled")) == 2

    def test_annul_dispatched_reverses_physics(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_contrib,
    ):
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        self._annul(client, org_headers, t["id"])
        assert _wh_stock(db_session, test_organization.id, mat_contrib.id, wh_cv.id) == Decimal("100")
        assert _wh_stock(db_session, test_organization.id, mat_contrib.id, wh_transit.id) == 0

    def test_annul_with_sold_material_warns_not_blocks(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_contrib,
    ):
        """M2 (desviación declarada): material ya vendido desde JM → 200 +
        warning, NO 400 (filosofía #76)."""
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        _receive(client, org_headers, t, {0: 40})

        # Vender 30 desde JM
        customer = create_third_party_with_category(
            db_session, test_organization.id, "Cliente M2", "customer"
        )
        db_session.commit()
        resp = client.post(
            "/api/v1/sales",
            headers=org_headers,
            json={
                "customer_id": str(customer.id),
                "warehouse_id": str(wh_jm.id),
                "date": RECEIPT_DATE,
                "lines": [{"material_id": str(mat_contrib.id), "quantity": 30.0,
                           "unit_price": 2000.0}],
                "commissions": [],
                "auto_liquidate": False,
            },
        )
        assert resp.status_code == 201, resp.text

        r = self._annul(client, org_headers, t["id"])
        assert r["status"] == "annulled"
        assert any("negativo" in w for w in r["warnings"])

    def test_annul_twice_400(
        self, client, org_headers,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_contrib,
    ):
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        self._annul(client, org_headers, t["id"])
        self._annul(client, org_headers, t["id"], expect=400)

    def test_treasury_annul_maquila_422(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_contrib,
    ):
        """Guard E5/E9: anular el par desde Tesorería → 422."""
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        _receive(client, org_headers, t, {0: 40})
        mm = _maquila_mms(db_session, test_organization.id)[0]
        resp = client.post(
            f"/api/v1/money-movements/{mm.id}/annul",
            headers=org_headers,
            json={"reason": "Intento directo"},
        )
        assert resp.status_code == 422
        assert "Traslados" in resp.json()["detail"]

    def test_kg_ledger_annul_rejects_intersede(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_contrib,
    ):
        """D16 sigue: kg_ledger.annul solo manual_adjustment — intersede_send → 4xx."""
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        _receive(client, org_headers, t, {0: 40})
        kg_mov = db_session.execute(
            select(KgLedgerMovement).where(
                KgLedgerMovement.source_type == "intersede_send",
                KgLedgerMovement.source_id == t["id"],
            )
        ).scalars().first()
        resp = client.post(
            f"/api/v1/kg-ledger/movements/{kg_mov.id}/annul",
            headers=org_headers,
            json={"reason": "Intento directo"},
        )
        assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# Guard operar-contra-tránsito (E12/§2.10)
# ---------------------------------------------------------------------------

class TestTransitGuard:
    def test_adjustment_against_transit_400(
        self, client, org_headers, wh_transit, mat_contrib,
    ):
        resp = client.post(
            f"{ADJUST_URL}/increase",
            headers=org_headers,
            json={
                "material_id": str(mat_contrib.id),
                "warehouse_id": str(wh_transit.id),
                "quantity": 10,
                "unit_cost": 100,
                "date": SEED_DATE,
                "reason": "Intento contra transito",
            },
        )
        assert resp.status_code == 400
        assert "tránsito" in resp.json()["detail"]

    def test_one_step_transfer_to_transit_400(
        self, client, org_headers, wh_cv, wh_transit, mat_contrib,
    ):
        resp = client.post(
            f"{ADJUST_URL}/warehouse-transfer",
            headers=org_headers,
            json={
                "material_id": str(mat_contrib.id),
                "source_warehouse_id": str(wh_cv.id),
                "destination_warehouse_id": str(wh_transit.id),
                "quantity": 10,
                "date": DISPATCH_DATE,
                "reason": "1-paso a transito",
            },
        )
        assert resp.status_code == 400

    def test_sale_from_transit_400(
        self, client, org_headers, db_session, test_organization, wh_transit, mat_contrib,
    ):
        customer = create_third_party_with_category(
            db_session, test_organization.id, "Cliente Transit", "customer"
        )
        db_session.commit()
        resp = client.post(
            "/api/v1/sales",
            headers=org_headers,
            json={
                "customer_id": str(customer.id),
                "warehouse_id": str(wh_transit.id),
                "date": RECEIPT_DATE,
                "lines": [{"material_id": str(mat_contrib.id), "quantity": 5.0,
                           "unit_price": 1000.0}],
                "commissions": [],
                "auto_liquidate": False,
            },
        )
        assert resp.status_code == 400

    def test_purchase_into_transit_400(
        self, client, org_headers, db_session, test_organization, wh_transit, mat_contrib,
    ):
        supplier = create_third_party_with_category(
            db_session, test_organization.id, "Proveedor Transit", "material_supplier"
        )
        db_session.commit()
        resp = client.post(
            "/api/v1/purchases",
            headers=org_headers,
            json={
                "supplier_id": str(supplier.id),
                "date": RECEIPT_DATE,
                "lines": [{"material_id": str(mat_contrib.id), "quantity": 5.0,
                           "unit_price": 1000.0,
                           "warehouse_id": str(wh_transit.id)}],
                "auto_liquidate": False,
            },
        )
        assert resp.status_code == 400

    def test_guard_inert_without_flag(
        self, client, org_headers, db_session, test_organization, wh_transit, mat_contrib,
    ):
        """Flag off → guard cortocircuita (prod byte-idéntico)."""
        test_organization.settings = {"kg_ledger_enabled": True}
        db_session.commit()
        resp = client.post(
            f"{ADJUST_URL}/increase",
            headers=org_headers,
            json={
                "material_id": str(mat_contrib.id),
                "warehouse_id": str(wh_transit.id),
                "quantity": 10,
                "unit_cost": 100,
                "date": SEED_DATE,
                "reason": "Sin flag el guard es inerte",
            },
        )
        assert resp.status_code in (200, 201)


# ---------------------------------------------------------------------------
# Guardianes de no-regresión
# ---------------------------------------------------------------------------

class TestNoRegression:
    def test_sale_liquidation_does_not_create_maquila(
        self, client, org_headers, db_session, test_organization,
        wh_jm, mat_simple, wh_cv,
    ):
        """Guardián §5.4: liquidar una venta jamás crea tipos internal_maquila."""
        customer = create_third_party_with_category(
            db_session, test_organization.id, "Cliente Guardian", "customer"
        )
        db_session.commit()
        resp = client.post(
            "/api/v1/sales",
            headers=org_headers,
            json={
                "customer_id": str(customer.id),
                "warehouse_id": str(wh_jm.id),
                "date": RECEIPT_DATE,
                "lines": [{"material_id": str(mat_simple.id), "quantity": 10.0,
                           "unit_price": 900.0}],
                "commissions": [],
                "auto_liquidate": False,
            },
        )
        assert resp.status_code == 201
        sale_id = resp.json()["id"]
        resp = client.patch(
            f"/api/v1/sales/{sale_id}/liquidate",
            headers=org_headers,
            json={"liquidation_date": RECEIPT_DATE},
        )
        assert resp.status_code == 200, resp.text
        assert _maquila_mms(db_session, test_organization.id) == []

    def test_transfer_movements_write_no_mch(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_contrib,
    ):
        """Invariante 1: despacho+recepción no escriben MaterialCostHistory."""
        from app.models.material_cost_history import MaterialCostHistory

        before = db_session.scalar(
            select(func.count(MaterialCostHistory.id)).where(
                MaterialCostHistory.organization_id == test_organization.id
            )
        )
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        _receive(client, org_headers, t, {0: 39})
        after = db_session.scalar(
            select(func.count(MaterialCostHistory.id)).where(
                MaterialCostHistory.organization_id == test_organization.id
            )
        )
        assert after == before


# ---------------------------------------------------------------------------
# Sedes — kg intersede y maquila SOLO si el traslado cruza de sede
# ---------------------------------------------------------------------------

class TestTransferSedes:
    """Antes, un traslado emitia kg y maquila por el solo hecho de que el
    material tuviera formula, sin mirar el recorrido: mover material de
    Circunvalar a su molino inventaba deuda de plomo y un cargo de maquila por
    material que nunca salio de la sede ("es un solo inventario", Johana).

    Ahora la sede decide DOS cosas: si se emiten kg/maquila, y si el traslado es
    de dos pasos. Dentro de una sede no se pesa al salir ni al llegar (Daniel),
    asi que el traslado se completa al registrarlo, en un solo salto y sin
    transito. NULL = la bodega es su propia sede, que es el estado de las 7 orgs:
    por eso todos los demas tests de este archivo siguen en dos pasos sin
    tocarlos.
    """

    @pytest.fixture
    def wh_molino(self, db_session, test_organization, wh_cv):
        """Molino de Circunvalar: misma sede que CV."""
        wh = create_warehouse(db_session, test_organization.id, "CV - Molino")
        wh.is_receiving = False
        wh.sede_warehouse_id = wh_cv.id
        db_session.commit()
        return wh

    def test_intra_sede_un_solo_paso_sin_kg_ni_maquila(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_molino, mat_contrib,
    ):
        """El test estrella. En esta prueba NO existe bodega de transito que
        rutee al molino, ni cuenta intersede, ni tarifa de maquila: si el
        traslado intentara ir en dos pasos o emitir, reventaria con 400."""
        t = _dispatch(client, org_headers, wh_cv, wh_molino,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])

        # Nace completo: sin transito, sin recepcion pendiente
        assert t["status"] == "received"
        assert t["transit_warehouse_id"] is None
        assert t["received_date"] is not None
        line = t["lines"][0]
        assert line["is_contributor"] is False
        assert float(line["quantity_received"]) == 40.0
        assert line["kg_lead_equivalent"] is None
        assert line["maquila_amount"] is None

        # El material paso directo de CV al molino
        assert _wh_stock(db_session, test_organization.id, mat_contrib.id,
                         wh_molino.id) == Decimal("40")
        assert _wh_stock(db_session, test_organization.id, mat_contrib.id,
                         wh_cv.id) == Decimal("60")

        # Cero kg, cero maquila y cero ajustes (no hay merma sin segundo pesaje)
        assert db_session.scalar(
            select(func.count(KgLedgerMovement.id)).where(
                KgLedgerMovement.organization_id == test_organization.id
            )
        ) == 0
        assert _maquila_mms(db_session, test_organization.id) == []
        assert db_session.execute(
            select(InventoryAdjustment).where(
                InventoryAdjustment.organization_id == test_organization.id,
                InventoryAdjustment.transfer_id == t["id"],
            )
        ).scalars().all() == []

    def test_intra_sede_no_admite_recepcion(
        self, client, org_headers, wh_cv, wh_molino, mat_contrib,
    ):
        """Recibir algo que ya llego: 400 que explica por que, no un estado raro."""
        t = _dispatch(client, org_headers, wh_cv, wh_molino,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        r = _receive(client, org_headers, t, {0: 40}, expect=400)
        assert "misma sede" in r["detail"]

    def test_intra_sede_no_toca_el_avg(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_molino, mat_contrib,
    ):
        """Invariante 1: un traslado JAMAS cambia el costo promedio."""
        db_session.expire_all()  # el seed entro por API, en otra sesion
        avg_before = db_session.get(Material, mat_contrib.id).current_average_cost
        assert avg_before == Decimal("1000.0000")
        _dispatch(client, org_headers, wh_cv, wh_molino,
                  [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        db_session.expire_all()
        assert db_session.get(Material, mat_contrib.id).current_average_cost == avg_before

    def test_intra_sede_anulacion_devuelve_el_material(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_molino, mat_contrib,
    ):
        """El annul refleja TODOS los movimientos del traslado, sin importar
        cuantos saltos tuvo — un salto tambien se revierte entero."""
        t = _dispatch(client, org_headers, wh_cv, wh_molino,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        resp = client.post(
            f"{TRANSFERS_URL}/{t['id']}/annul",
            headers=org_headers,
            json={"reason": "Error de captura"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "annulled"
        assert _wh_stock(db_session, test_organization.id, mat_contrib.id,
                         wh_molino.id) == 0
        assert _wh_stock(db_session, test_organization.id, mat_contrib.id,
                         wh_cv.id) == Decimal("100")

    def test_del_molino_a_otra_sede_si_emite(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_molino, wh_jm, wh_transit,
        intersede_account, maquila_tariff, mat_contrib,
    ):
        """Molino → Juan Mina cruza de sede (CV vs JM): dos pasos y emite."""
        # Llevar material al molino primero (intra-sede, un solo paso)
        _dispatch(client, org_headers, wh_cv, wh_molino,
                  [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])

        t2 = _dispatch(client, org_headers, wh_molino, wh_jm,
                       [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        assert t2["status"] == "dispatched"
        assert t2["transit_warehouse_id"] is not None
        assert t2["lines"][0]["is_contributor"] is True
        r = _receive(client, org_headers, t2, {0: 40})
        assert r["lines"][0]["effects_emitted"] is True
        assert float(r["lines"][0]["kg_lead_equivalent"]) == 20.0

        assert _kg_balance(db_session, test_organization.id,
                           intersede_account.id) != 0
        mms = _maquila_mms(db_session, test_organization.id)
        assert len(mms) == 2
        # El gasto se carga a la sede que despacha: el molino
        by_type = {m.movement_type: m for m in mms}
        assert by_type["internal_maquila_expense"].warehouse_id == wh_molino.id
        assert by_type["internal_maquila_income"].warehouse_id == wh_jm.id

    def test_dos_bodegas_sin_sede_siguen_cruzando(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, wh_transit, intersede_account, maquila_tariff, mat_contrib,
    ):
        """No-regresion explicita: con sede NULL en ambas —el estado de las 7
        orgs— cada bodega es su propia sede y el traslado sigue emitiendo."""
        assert wh_cv.sede_warehouse_id is None and wh_jm.sede_warehouse_id is None
        t = _dispatch(client, org_headers, wh_cv, wh_jm,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 40}])
        assert t["status"] == "dispatched"  # sigue siendo de dos pasos
        assert t["lines"][0]["is_contributor"] is True
        r = _receive(client, org_headers, t, {0: 40})
        assert r["lines"][0]["effects_emitted"] is True
        assert len(_maquila_mms(db_session, test_organization.id)) == 2

    def test_misma_sede_entre_dos_hijas(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_molino, wh_bog, mat_contrib,
    ):
        """Dos bodegas que apuntan a la MISMA sede tampoco cruzan entre si —
        aunque ninguna de las dos SEA la sede."""
        wh_bog.sede_warehouse_id = wh_cv.id
        db_session.commit()

        t = _dispatch(client, org_headers, wh_molino, wh_bog,
                      [{"material_id": str(mat_contrib.id), "quantity_dispatched": 0.5}])
        assert t["status"] == "received"
        assert t["transit_warehouse_id"] is None
        assert t["lines"][0]["is_contributor"] is False


class TestSedeValidation:
    """Un valor malo aca no da error: da numeros equivocados en silencio."""

    def _patch(self, client, headers, wh_id, sede_id, expect):
        resp = client.patch(
            f"/api/v1/warehouses/{wh_id}",
            headers=headers,
            json={"sede_warehouse_id": str(sede_id) if sede_id else None},
        )
        assert resp.status_code == expect, resp.text
        return resp

    def test_no_puede_ser_su_propia_sede(self, client, org_headers, wh_cv):
        r = self._patch(client, org_headers, wh_cv.id, wh_cv.id, 400)
        assert "propia sede" in r.json()["detail"]

    def test_transito_no_puede_ser_sede(self, client, org_headers, wh_cv, wh_transit):
        r = self._patch(client, org_headers, wh_cv.id, wh_transit.id, 400)
        assert "tránsito" in r.json()["detail"]

    def test_un_solo_nivel(self, client, org_headers, db_session, test_organization,
                           wh_cv, wh_jm, wh_bog):
        wh_jm.sede_warehouse_id = wh_cv.id
        db_session.commit()
        r = self._patch(client, org_headers, wh_bog.id, wh_jm.id, 400)
        assert "un solo nivel" in r.json()["detail"]

    def test_una_sede_no_puede_tener_sede(self, client, org_headers, db_session,
                                          wh_cv, wh_jm, wh_bog):
        """El otro extremo de la cadena: CV ya es sede de JM."""
        wh_jm.sede_warehouse_id = wh_cv.id
        db_session.commit()
        r = self._patch(client, org_headers, wh_cv.id, wh_bog.id, 400)
        assert "es sede de" in r.json()["detail"]

    def test_sede_de_otra_org_rechazada(self, client, org_headers, db_session, wh_cv):
        ajena = Organization(name="Org Ajena", slug="org-ajena-sede", max_users=5)
        db_session.add(ajena)
        db_session.flush()
        otra = create_warehouse(db_session, ajena.id, "Ajena")
        db_session.commit()
        r = self._patch(client, org_headers, wh_cv.id, otra.id, 400)
        assert "no existe" in r.json()["detail"]

    def test_limpiar_sede_permitido(self, client, org_headers, db_session,
                                    wh_cv, wh_jm):
        wh_jm.sede_warehouse_id = wh_cv.id
        db_session.commit()
        self._patch(client, org_headers, wh_jm.id, None, 200)
        db_session.expire_all()
        assert db_session.get(Warehouse, wh_jm.id).sede_warehouse_id is None
