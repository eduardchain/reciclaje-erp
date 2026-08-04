"""
Tests SAC E3.1 — P&L por sede (plan v1.1 §2.8, E13 recalibrado M1).

Test de ORO (M1 QA): la línea de comisiones por-sede se filtra por
Sale.warehouse_id — el fixture tiene comisión ≠ 0 en la venta de CV, así que
con el filtro equivocado (MoneyMovement.warehouse_id, NULL en accrual) la
línea daría $0 y el assert REVIENTA (no puede pasar en falso).

También: consolidado byte-idéntico (maquila excluida, netea $0 con include),
gastos sin sede → $0 por sede + presentes en consolidado.
"""
import pytest
from decimal import Decimal

from sqlalchemy import select, func

from app.models.money_movement import MoneyMovement
from app.models.kg_ledger import KgLedgerAccount
from app.models.sale import Sale
from app.models.service_tariff import ServiceTariff
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    create_account,
    create_expense_category,
    create_material,
    create_material_category,
    create_warehouse,
)

PNL_URL = "/api/v1/reports/profit-and-loss"
TRANSFERS_URL = "/api/v1/transfers"
FORMULAS_URL = "/api/v1/material-conversion-formulas"
ADJUST_URL = "/api/v1/inventory/adjustments"

SEED_DATE = "2026-07-01T12:00:00"
OP_DATE = "2026-07-10T12:00:00"
PERIOD = {"date_from": "2026-07-01", "date_to": "2026-07-18"}


@pytest.fixture(autouse=True)
def _enable_flags(db_session, test_organization):
    test_organization.settings = {
        "kg_ledger_enabled": True,
        "two_step_transfers_enabled": True,
        "internal_maquila_enabled": True,
    }
    db_session.commit()


@pytest.fixture
def scenario(db_session, test_organization, test_user, client, org_headers):
    """CV: venta 20kg×$2.000 con comisión 2.5% ($1.000) + JM: venta 10kg×$2.000
    sin comisión + traslado CV→JM 40kg recibido exacto (maquila $30.000:
    expense CV / income JM) + gasto org SIN sede ($5.000)."""
    org = test_organization.id
    wh_cv = create_warehouse(db_session, org, "CV")
    wh_jm = create_warehouse(db_session, org, "JM")
    wh_transit = create_warehouse(db_session, org, "JM-TRANSITO")
    wh_transit.is_transit = True
    wh_transit.transit_target_warehouse_id = wh_jm.id

    account = create_account(db_session, org, "Caja", balance=1_000_000)
    exp_cat = create_expense_category(db_session, org, "Administración")

    intersede = KgLedgerAccount(
        organization_id=org,
        code="INTERSEDE",
        display_name="Intersede",
        account_type="intersede",
        is_active=True,
    )
    db_session.add(intersede)
    tariff = ServiceTariff(
        organization_id=org,
        tariff_code="maquila_intersede_cv_jm",
        unit_price_cop=Decimal("1500.00"),
        unit="per_kg_lead",
        created_by=test_user.id,
    )
    db_session.add(tariff)

    customer = create_third_party_with_category(db_session, org, "Cliente PNL", "customer")
    commissioner = create_third_party_with_category(
        db_session, org, "Comisionista PNL", "service_provider"
    )
    db_session.commit()

    cat = create_material_category(db_session, org, "Cat PNL")
    mat = create_material(db_session, org, "DROSS-P", "Dross PNL", cat.id)
    mat.default_unit = "kg"
    db_session.commit()

    # Fórmula 50% (aportante)
    resp = client.post(
        FORMULAS_URL, headers=org_headers,
        json={"material_id": str(mat.id), "formula_type": "drosses_to_lead",
              "parameters": {"lead_percentage": 0.5}},
    )
    assert resp.status_code == 201, resp.text

    # Stock: 100 @ $1.000 en CV, 50 @ $1.000 en JM (mismo material — avg org-wide)
    for wh, qty in ((wh_cv, 100), (wh_jm, 50)):
        resp = client.post(
            f"{ADJUST_URL}/increase", headers=org_headers,
            json={"material_id": str(mat.id), "warehouse_id": str(wh.id),
                  "quantity": qty, "unit_cost": 1000, "date": SEED_DATE,
                  "reason": "Seed stock PNL"},
        )
        assert resp.status_code in (200, 201), resp.text

    def _sale(warehouse, qty, commissions):
        resp = client.post(
            "/api/v1/sales", headers=org_headers,
            json={
                "customer_id": str(customer.id),
                "warehouse_id": str(warehouse.id),
                "date": OP_DATE,
                "lines": [{"material_id": str(mat.id), "quantity": qty,
                           "unit_price": 2000.0}],
                "commissions": commissions,
                "auto_liquidate": False,
            },
        )
        assert resp.status_code == 201, resp.text
        sale_id = resp.json()["id"]
        resp = client.patch(
            f"/api/v1/sales/{sale_id}/liquidate", headers=org_headers,
            json={"liquidation_date": OP_DATE},
        )
        assert resp.status_code == 200, resp.text
        return sale_id

    sale_cv = _sale(wh_cv, 20.0, [{
        "third_party_id": str(commissioner.id),
        "concept": "Comisión CV",
        "commission_type": "percentage",
        "commission_value": 2.5,
    }])
    sale_jm = _sale(wh_jm, 10.0, [])

    # Traslado CV→JM 40 kg exacto → maquila 20 kg eq × 1.500 = $30.000
    resp = client.post(
        TRANSFERS_URL, headers=org_headers,
        json={"from_warehouse_id": str(wh_cv.id), "to_warehouse_id": str(wh_jm.id),
              "dispatch_date": OP_DATE,
              "lines": [{"material_id": str(mat.id), "quantity_dispatched": 40}]},
    )
    assert resp.status_code == 201, resp.text
    transfer = resp.json()
    resp = client.post(
        f"{TRANSFERS_URL}/{transfer['id']}/receive", headers=org_headers,
        json={"lines": [{"transfer_line_id": transfer["lines"][0]["id"],
                         "quantity_received": 40}],
              "receipt_date": "2026-07-12T12:00:00"},
    )
    assert resp.status_code == 200, resp.text

    # Gasto org-level SIN sede
    resp = client.post(
        "/api/v1/money-movements/expense", headers=org_headers,
        json={"amount": 5000, "expense_category_id": str(exp_cat.id),
              "account_id": str(account.id), "description": "Gasto sin sede",
              "date": OP_DATE},
    )
    assert resp.status_code == 201, resp.text

    return {
        "wh_cv": wh_cv, "wh_jm": wh_jm, "sale_cv": sale_cv, "sale_jm": sale_jm,
        "commissioner": commissioner,
    }


def _pnl(client, headers, **params):
    resp = client.get(PNL_URL, headers=headers, params={**PERIOD, **params})
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestPnlByWarehouse:
    def test_consolidated_excludes_maquila_and_keys_zero(self, client, org_headers, scenario):
        """Consolidado sin flags: claves nuevas presentes con 0.0 (golden-safe)
        y la maquila NO participa del neto."""
        pnl = _pnl(client, org_headers)
        assert pnl["internal_maquila_income"] == 0.0
        assert pnl["internal_maquila_expense"] == 0.0
        # Ventas de ambas sedes + gasto sin sede presentes
        assert pnl["sales_revenue"] == pytest.approx(60000.0)  # 40.000 + 20.000
        assert pnl["operating_expenses"] == pytest.approx(5000.0)
        assert pnl["commissions_paid"] == pytest.approx(1000.0)

    def test_consolidated_include_flag_nets_zero(self, client, org_headers, scenario):
        """include_internal_maquila: ambas líneas visibles (≠0) y el neto NO
        cambia (el par netea $0 por construcción)."""
        base = _pnl(client, org_headers)
        with_maquila = _pnl(client, org_headers, include_internal_maquila=True)
        assert with_maquila["internal_maquila_income"] == pytest.approx(30000.0)
        assert with_maquila["internal_maquila_expense"] == pytest.approx(30000.0)
        assert with_maquila["net_profit"] == pytest.approx(base["net_profit"])

    def test_pnl_sede_cv(self, client, org_headers, scenario):
        """CV: ventas+COGS propios, comisión ≠ 0, maquila como GASTO, cero
        gastos org (sin sede)."""
        pnl = _pnl(client, org_headers, warehouse_id=str(scenario["wh_cv"].id))
        assert pnl["sales_revenue"] == pytest.approx(40000.0)
        assert pnl["cost_of_goods_sold"] == pytest.approx(20000.0)  # 20 × 1.000
        # TEST DE ORO M1: con el filtro equivocado esto daría 0.0 y revienta
        assert pnl["commissions_paid"] == pytest.approx(1000.0)
        assert pnl["commissions_paid"] > 0
        assert pnl["internal_maquila_expense"] == pytest.approx(30000.0)
        assert pnl["internal_maquila_income"] == 0.0
        # Gastos sin sede NO se fragmentan (M1: $0 por sede hasta E4)
        assert pnl["operating_expenses"] == 0.0
        assert pnl["service_income"] == 0.0
        # Neto CV: (40.000 − 20.000) − 30.000 − 1.000 = −11.000
        assert pnl["net_profit"] == pytest.approx(-11000.0)

    def test_pnl_sede_jm(self, client, org_headers, scenario):
        """JM: su venta + maquila como INGRESO; sin comisiones ni gastos."""
        pnl = _pnl(client, org_headers, warehouse_id=str(scenario["wh_jm"].id))
        assert pnl["sales_revenue"] == pytest.approx(20000.0)
        assert pnl["cost_of_goods_sold"] == pytest.approx(10000.0)
        assert pnl["commissions_paid"] == 0.0
        assert pnl["internal_maquila_income"] == pytest.approx(30000.0)
        assert pnl["internal_maquila_expense"] == 0.0
        # Neto JM: (20.000 − 10.000) + 30.000 = 40.000
        assert pnl["net_profit"] == pytest.approx(40000.0)

    def test_golden_commission_parity_by_sede(
        self, client, org_headers, db_session, test_organization, scenario,
    ):
        """Oro M1: comisiones por-sede == Σ commission_accrual de las ventas de
        ESA sede (±$1), y ≠ 0."""
        pnl = _pnl(client, org_headers, warehouse_id=str(scenario["wh_cv"].id))
        db_total = db_session.scalar(
            select(func.coalesce(func.sum(MoneyMovement.amount), 0))
            .select_from(MoneyMovement)
            .join(Sale, MoneyMovement.sale_id == Sale.id)
            .where(
                MoneyMovement.organization_id == test_organization.id,
                MoneyMovement.movement_type == "commission_accrual",
                MoneyMovement.status == "confirmed",
                Sale.warehouse_id == scenario["wh_cv"].id,
            )
        )
        db_total = float(db_total)
        assert db_total > 0
        assert abs(pnl["commissions_paid"] - db_total) <= 1.0

    def test_pnl_non_attributable_lines_zero_by_sede(self, client, org_headers, scenario):
        """DP/transformaciones/ajustes/oversell/tp_adj → $0 por sede (solo
        consolidado). El seed increase (ajuste) infla adjustment_net del
        consolidado pero NO el de la sede."""
        consolidated = _pnl(client, org_headers)
        by_sede = _pnl(client, org_headers, warehouse_id=str(scenario["wh_cv"].id))
        assert consolidated["adjustment_net"] > 0  # seeds del fixture
        assert by_sede["adjustment_net"] == 0.0
        assert by_sede["double_entry_profit"] == 0.0
        assert by_sede["transformation_profit"] == 0.0
        assert by_sede["oversell_cost_adjustment"] == 0.0
        assert by_sede["tp_adjustment_gain"] == 0.0
        assert by_sede["tp_adjustment_loss"] == 0.0

    def test_pnl_monthly_accepts_warehouse(self, client, org_headers, scenario):
        """Smoke: el endpoint mensual acepta warehouse_id y sus totals
        coinciden con el endpoint de periodo."""
        period = _pnl(client, org_headers, warehouse_id=str(scenario["wh_cv"].id))
        resp = client.get(
            f"{PNL_URL}/monthly", headers=org_headers,
            params={**PERIOD, "warehouse_id": str(scenario["wh_cv"].id)},
        )
        assert resp.status_code == 200, resp.text
        totals = resp.json()["totals"]
        assert totals["net_profit"] == pytest.approx(period["net_profit"])
        assert totals["internal_maquila_expense"] == pytest.approx(30000.0)

    def test_reconciliation_unaffected_with_maquila_present(
        self, client, org_headers, scenario,
    ):
        """Conciliación #59: residual $0 con eventos de maquila presentes —
        el consolidado los ignora por construcción (N5 allowlist inline)."""
        resp = client.get(
            "/api/v1/reports/profitability-by-business-unit",
            headers=org_headers, params=PERIOD,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        rec = data.get("reconciliation")
        if rec is not None:
            pnl = _pnl(client, org_headers)
            grand = data.get("grand_total_net", 0.0)
            residual = pnl["net_profit"] - (
                grand
                + rec.get("service_income", 0.0)
                + rec.get("interest_income", 0.0)
                + rec.get("transformation_net", 0.0)
                + rec.get("inventory_adjustment_net", 0.0)
                + rec.get("tp_adjustment_net", 0.0)
                + rec.get("oversell_cost_adjustment", 0.0)
            )
            assert abs(residual) <= 1.0
