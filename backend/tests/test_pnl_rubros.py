"""
Tests del P&L por rubros (plan pnl-por-rubros, requerimiento C).

Cubre:
- Configuracion de pnl_section en categorias (solo raiz, herencia, reset al reparentar).
- Clasificador de 3 niveles con precedencia fuente-gana:
  depreciation_expense → depreciacion; obligation_interest_accrual → financiero;
  resto → seccion de la categoria raiz (default operativo).
- Golden de paridad y cascada (GAP-1 QA): las 4 identidades del plan.
- Param pnl_section del listado de Tesoreria (drill-down #49: paridad por
  construccion + restriccion implicita a tipos de gasto, N1 QA).
- RBAC.
"""
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.models.money_movement import MoneyMovement
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    create_account,
    api_money_movement,
)

CAT_URL = "/api/v1/expense-categories"
MM_URL = "/api/v1/money-movements"
PNL_PARAMS = {"date_from": "2026-03-01", "date_to": "2026-03-31"}


def _dt(d_str: str) -> datetime:
    y, m, day = map(int, d_str.split("-"))
    return datetime(y, m, day, 12, 0, 0, tzinfo=timezone.utc)


def _mk_cat(client, headers, name, **extra):
    resp = client.post(CAT_URL, json={"name": name, **extra}, headers=headers)
    assert resp.status_code == 201, resp.json()
    return resp.json()


# ===========================================================================
# Configuracion de pnl_section en categorias
# ===========================================================================

class TestPnlSectionConfig:

    def test_create_root_financiero(self, client, org_headers):
        cat = _mk_cat(client, org_headers, "Bancaria Cfg", pnl_section="financiero")
        assert cat["pnl_section"] == "financiero"

    def test_create_defaults_operativo(self, client, org_headers):
        cat = _mk_cat(client, org_headers, "Arriendo Cfg")
        assert cat["pnl_section"] == "operativo"

    def test_create_child_financiero_422(self, client, org_headers):
        root = _mk_cat(client, org_headers, "Padre Cfg")
        resp = client.post(
            CAT_URL,
            json={"name": "Hija Cfg", "parent_id": root["id"], "pnl_section": "financiero"},
            headers=org_headers,
        )
        assert resp.status_code == 422
        assert "padre" in resp.json()["detail"]

    def test_patch_child_financiero_422(self, client, org_headers):
        root = _mk_cat(client, org_headers, "Padre Cfg 2")
        child = _mk_cat(client, org_headers, "Hija Cfg 2", parent_id=root["id"])
        resp = client.patch(
            f"{CAT_URL}/{child['id']}",
            json={"pnl_section": "financiero"},
            headers=org_headers,
        )
        assert resp.status_code == 422

    def test_reparent_resets_section(self, client, org_headers):
        """Una raiz financiera que se vuelve hija pierde su seccion propia
        (heredara la del nuevo padre en lectura) — espejo del reset de pct #59."""
        root_op = _mk_cat(client, org_headers, "Padre Operativo Cfg")
        fin = _mk_cat(client, org_headers, "Temp Financiera Cfg", pnl_section="financiero")
        resp = client.patch(
            f"{CAT_URL}/{fin['id']}",
            json={"parent_id": root_op["id"]},
            headers=org_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["pnl_section"] == "operativo"

    def test_invalid_section_422(self, client, org_headers):
        resp = client.post(
            CAT_URL,
            json={"name": "Rara Cfg", "pnl_section": "patrimonio"},
            headers=org_headers,
        )
        assert resp.status_code == 422

    def test_viewer_cannot_patch_section(
        self, client, org_headers2, db_session, test_organization2,
    ):
        """RBAC: viewer (org2) no puede editar la seccion — 403."""
        from app.models.expense_category import ExpenseCategory
        cat = ExpenseCategory(name="RBAC Rubro", organization_id=test_organization2.id)
        db_session.add(cat)
        db_session.commit()
        resp = client.patch(
            f"{CAT_URL}/{cat.id}",
            json={"pnl_section": "financiero"},
            headers=org_headers2,
        )
        assert resp.status_code == 403


# ===========================================================================
# Escenario compartido: gastos de marzo 2026 en las 3 secciones
# ===========================================================================

@pytest.fixture
def rubros_scenario(client, org_headers, db_session, test_organization):
    """Gastos de marzo 2026 cubriendo los 3 niveles del clasificador.

    Montos (a mano):
      operativo   = 100.000 (Arriendo) + 5.000 (sin categoria)        = 105.000
      financiero  =  50.000 (Bancaria) + 10.000 (hija de Bancaria)
                  +  80.000 (expense_accrual bajo Intereses — N2 QA)
                  +  20.000 (obligation_interest_accrual bajo cat OPERATIVA
                             — la fuente gana)                         = 160.000
      depreciacion=  30.000 (depreciation_expense bajo cat FINANCIERA
                             — la fuente gana)                         =  30.000
      operating_expenses (total, campo compat)                        = 295.000
      interest_income = 15.000 (loan_interest_accrual — N2: fuerza cascada no trivial)
      commissions_paid = 25.000 (commission_accrual)
      provision_deposit = 40.000 (NO es gasto — N1: no debe matchear pnl_section)
    """
    org_id = test_organization.id
    h = org_headers

    acc = create_account(db_session, org_id, "Cuenta Rubros", balance=10_000_000)
    db_session.commit()

    cat_op = _mk_cat(client, h, "Arriendo Rubros")  # operativo default
    cat_fin = _mk_cat(client, h, "Bancaria Rubros", pnl_section="financiero")
    cat_fin_child = _mk_cat(client, h, "GMF Rubros", parent_id=cat_fin["id"])
    cat_int = _mk_cat(client, h, "Intereses Rubros", pnl_section="financiero")
    cat_dep = _mk_cat(client, h, "Depreciacion Rubros", pnl_section="financiero")

    liability_tp = create_third_party_with_category(
        db_session, org_id, "Pasivo Rubros", "liability",
    )
    provision_tp = create_third_party_with_category(
        db_session, org_id, "Provision Rubros", "provision",
    )
    comisionista = create_third_party_with_category(
        db_session, org_id, "Comisionista Rubros", "service_provider",
    )
    db_session.commit()

    # Nivel 3 (categoria): expense operativo y financieros
    api_money_movement(client, h, "expense", {
        "account_id": acc.id, "expense_category_id": cat_op["id"],
        "amount": 100_000, "date": "2026-03-05T12:00:00", "description": "Arriendo mes",
    })
    api_money_movement(client, h, "expense", {
        "account_id": acc.id, "expense_category_id": cat_fin["id"],
        "amount": 50_000, "date": "2026-03-06T12:00:00", "description": "Cuota manejo",
    })
    # Herencia: hija de Bancaria clasifica financiero
    api_money_movement(client, h, "expense", {
        "account_id": acc.id, "expense_category_id": cat_fin_child["id"],
        "amount": 10_000, "date": "2026-03-07T12:00:00", "description": "GMF",
    })
    # N2 QA: fuente no-expense clasificada por categoria (expense_accrual)
    api_money_movement(client, h, "expense-accrual", {
        "third_party_id": liability_tp.id, "expense_category_id": cat_int["id"],
        "amount": 80_000, "date": "2026-03-08T12:00:00", "description": "Interes credito",
    })
    # N1 QA: movimiento NO-gasto en el rango (no debe matchear pnl_section)
    api_money_movement(client, h, "provision-deposit", {
        "provision_id": provision_tp.id, "account_id": acc.id,
        "amount": 40_000, "date": "2026-03-09T12:00:00", "description": "Fondeo provision",
    })

    # Niveles 1 y 2 + tipos sistema: insert directo (no hay endpoint publico)
    db_session.add(MoneyMovement(
        organization_id=org_id, movement_type="depreciation_expense",
        amount=Decimal("30000"), expense_category_id=cat_dep["id"],
        description="Dep bajo cat financiera (fuente gana)",
        date=_dt("2026-03-10"), status="confirmed", movement_number=910001,
    ))
    db_session.add(MoneyMovement(
        organization_id=org_id, movement_type="obligation_interest_accrual",
        amount=Decimal("20000"), expense_category_id=cat_op["id"],
        third_party_id=liability_tp.id,
        description="Interes obligacion bajo cat operativa (fuente gana)",
        date=_dt("2026-03-11"), status="confirmed", movement_number=910002,
    ))
    db_session.add(MoneyMovement(
        organization_id=org_id, movement_type="expense",
        amount=Decimal("5000"), expense_category_id=None,
        description="Gasto sin categoria",
        date=_dt("2026-03-12"), status="confirmed", movement_number=910003,
    ))
    db_session.add(MoneyMovement(
        organization_id=org_id, movement_type="loan_interest_accrual",
        amount=Decimal("15000"),
        description="Interes prestamo por cobrar",
        date=_dt("2026-03-13"), status="confirmed", movement_number=910004,
    ))
    db_session.add(MoneyMovement(
        organization_id=org_id, movement_type="commission_accrual",
        amount=Decimal("25000"), third_party_id=comisionista.id,
        description="Comision rubros",
        date=_dt("2026-03-14"), status="confirmed", movement_number=910005,
    ))
    db_session.commit()

    return {"cat_op": cat_op, "cat_fin": cat_fin}


class TestPnlRubrosClassification:

    def _pnl(self, client, org_headers):
        resp = client.get(
            "/api/v1/reports/profit-and-loss", params=PNL_PARAMS, headers=org_headers,
        )
        assert resp.status_code == 200
        return resp.json()

    def test_section_totals(self, client, org_headers, rubros_scenario):
        """Los 3 subtotales con los montos a mano del fixture."""
        pnl = self._pnl(client, org_headers)
        assert pnl["expenses_operating"] == 105_000.0
        assert pnl["expenses_financial"] == 160_000.0
        assert pnl["expenses_depreciation"] == 30_000.0
        # Campo compat: sigue siendo el total de los 3
        assert pnl["operating_expenses"] == 295_000.0

    def test_golden_cascade_identities(self, client, org_headers, rubros_scenario):
        """GAP-1 QA: las 4 identidades de la escalera (con interest_income > 0)."""
        pnl = self._pnl(client, org_headers)
        assert pnl["interest_income"] == 15_000.0
        assert (
            pnl["expenses_operating"] + pnl["expenses_depreciation"] + pnl["expenses_financial"]
            == pytest.approx(pnl["operating_expenses"], abs=0.01)
        )
        assert pnl["gross_profit_before_financial"] == pytest.approx(
            pnl["total_gross_profit"] - pnl["interest_income"], abs=0.01
        )
        assert pnl["operating_result"] == pytest.approx(
            pnl["gross_profit_before_financial"] - pnl["commissions_paid"]
            - pnl["expenses_operating"] - pnl["expenses_depreciation"],
            abs=0.01,
        )
        assert pnl["net_profit"] == pytest.approx(
            pnl["operating_result"] + pnl["interest_income"] - pnl["expenses_financial"],
            abs=0.01,
        )
        # Paridad absoluta calculada a mano (la neta NO cambia con el split):
        # 15.000 - 295.000 - 25.000 = -305.000
        assert pnl["net_profit"] == -305_000.0
        assert pnl["operating_result"] == -160_000.0

    def test_breakdown_rows_carry_section(self, client, org_headers, rubros_scenario):
        pnl = self._pnl(client, org_headers)
        by_name = {
            (row["category_name"], row["source_type"]): row["pnl_section"]
            for row in pnl["expenses_by_category"]
        }
        assert by_name[("Arriendo Rubros", "expense")] == "operativo"
        assert by_name[("Bancaria Rubros", "expense")] == "financiero"
        assert by_name[("GMF Rubros", "expense")] == "financiero"  # herencia
        assert by_name[("Intereses Rubros", "expense_accrual")] == "financiero"  # N2
        assert by_name[("Depreciacion Rubros", "depreciation_expense")] == "depreciacion"
        assert by_name[("Arriendo Rubros", "obligation_interest_accrual")] == "financiero"
        assert by_name[("Sin categoria", "expense")] == "operativo"

    def test_monthly_mirror(self, client, org_headers, rubros_scenario):
        """El tab Mensual expone los mismos subtotales (reusa get_profit_and_loss)."""
        resp = client.get(
            "/api/v1/reports/profit-and-loss/monthly",
            params={**PNL_PARAMS, "cutoff_day": 1},
            headers=org_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        march = body["periods"][0]
        assert march["expenses_operating"] == 105_000.0
        assert march["expenses_financial"] == 160_000.0
        assert march["expenses_depreciation"] == 30_000.0
        assert march["operating_result"] == -160_000.0
        assert body["totals"]["gross_profit_before_financial"] == march["gross_profit_before_financial"]


class TestListingPnlSectionParity:
    """Drill-down #49: el listado con pnl_section suma exactamente el subtotal."""

    def _listing_sum(self, client, org_headers, section):
        resp = client.get(
            MM_URL,
            params={
                "pnl_section": section, "status": "confirmed",
                "date_from": "2026-03-01", "date_to": "2026-03-31", "limit": 1000,
            },
            headers=org_headers,
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        return sum(Decimal(str(i["amount"])) for i in items), items

    def test_financiero_parity(self, client, org_headers, rubros_scenario):
        total, _ = self._listing_sum(client, org_headers, "financiero")
        assert total == Decimal("160000")

    def test_operativo_parity_excludes_non_expense(self, client, org_headers, rubros_scenario):
        """N1 QA: el provision_deposit (40K, sin categoria) NO matchea operativo;
        el loan_interest_accrual (ingreso) y el commission_accrual tampoco."""
        total, items = self._listing_sum(client, org_headers, "operativo")
        assert total == Decimal("105000")
        types = {i["movement_type"] for i in items}
        assert types == {"expense"}

    def test_depreciacion_parity(self, client, org_headers, rubros_scenario):
        total, items = self._listing_sum(client, org_headers, "depreciacion")
        assert total == Decimal("30000")
        assert all(i["movement_type"] == "depreciation_expense" for i in items)

    def test_invalid_section_422(self, client, org_headers):
        resp = client.get(MM_URL, params={"pnl_section": "otros"}, headers=org_headers)
        assert resp.status_code == 422
