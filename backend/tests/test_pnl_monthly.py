"""
Tests del P&L Mensual (decision #50).

Cubre:
- Helper `_split_into_accounting_months`: 4 escenarios (calendario, cutoff, partial, year rollover).
- Endpoint: paridad columna↔total alineado, RBAC, validacion cutoff_day, cap 24 meses.
- 🔴 Guardrail BLOQUEANTE: `test_pnl_monthly_cell_drilldown_matches_listing` —
  cada celda mensual debe coincidir con el listado destino al pasar los bounds
  del mes contable en `date_from`/`date_to`. Sin este test no hay garantia de
  paridad.

Total: 9 tests.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.services.reports import report_service
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    create_material_category,
    create_business_unit,
    create_material,
    create_warehouse,
    create_account,
    create_expense_category,
    api_create_purchase,
    api_create_sale,
    api_create_double_entry,
    api_money_movement,
)


def _dt(d_str: str, *, hour: int = 12) -> datetime:
    """Helper: 'YYYY-MM-DD' -> datetime UTC mediodia."""
    y, m, day = map(int, d_str.split("-"))
    return datetime(y, m, day, hour, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Tests del helper de split (unit tests, no requieren DB/fixtures)
# ---------------------------------------------------------------------------


class TestSplitAccountingMonths:
    def test_split_accounting_months_calendar(self):
        """cutoff_day=1, rango cubre 3 meses calendario → 3 columnas con labels 'Mar 2026' etc."""
        months = report_service._split_into_accounting_months(
            date(2026, 3, 1), date(2026, 5, 31), 1,
        )
        assert len(months) == 3
        assert months[0] == (date(2026, 3, 1), date(2026, 3, 31), "Mar 2026")
        assert months[1] == (date(2026, 4, 1), date(2026, 4, 30), "Abr 2026")
        assert months[2] == (date(2026, 5, 1), date(2026, 5, 31), "May 2026")

    def test_split_accounting_months_with_cutoff(self):
        """cutoff_day=4, rango 2026-03-01 → 2026-06-30 → 5 columnas con labels '4 Feb – 3 Mar' etc."""
        months = report_service._split_into_accounting_months(
            date(2026, 3, 1), date(2026, 6, 30), 4,
        )
        assert len(months) == 5
        assert months[0] == (date(2026, 2, 4), date(2026, 3, 3), "4 Feb – 3 Mar 2026")
        assert months[1] == (date(2026, 3, 4), date(2026, 4, 3), "4 Mar – 3 Abr 2026")
        assert months[2] == (date(2026, 4, 4), date(2026, 5, 3), "4 Abr – 3 May 2026")
        assert months[3] == (date(2026, 5, 4), date(2026, 6, 3), "4 May – 3 Jun 2026")
        assert months[4] == (date(2026, 6, 4), date(2026, 7, 3), "4 Jun – 3 Jul 2026")

    def test_split_accounting_months_partial_range(self):
        """Rango de 10 dias dentro de un mes contable → 1 columna."""
        months = report_service._split_into_accounting_months(
            date(2026, 3, 10), date(2026, 3, 20), 1,
        )
        assert len(months) == 1
        assert months[0] == (date(2026, 3, 1), date(2026, 3, 31), "Mar 2026")

    def test_split_accounting_months_year_rollover(self):
        """cutoff_day=15, rango 2025-12-20 → 2026-02-10 → 2 columnas con año disambiguado."""
        months = report_service._split_into_accounting_months(
            date(2025, 12, 20), date(2026, 2, 10), 15,
        )
        # "15 Dic 2025 – 14 Ene 2026" contiene date_from (2025-12-20).
        # "15 Ene 2026 – 14 Feb 2026" contiene date_to (2026-02-10).
        assert len(months) == 2
        assert months[0] == (date(2025, 12, 15), date(2026, 1, 14), "15 Dic 2025 – 14 Ene 2026")
        assert months[1] == (date(2026, 1, 15), date(2026, 2, 14), "15 Ene 2026 – 14 Feb 2026")

    def test_split_invalid_cutoff_raises(self):
        with pytest.raises(ValueError):
            report_service._split_into_accounting_months(date(2026, 3, 1), date(2026, 3, 31), 0)
        with pytest.raises(ValueError):
            report_service._split_into_accounting_months(date(2026, 3, 1), date(2026, 3, 31), 29)


# ---------------------------------------------------------------------------
# Fixture para tests con datos reales en DB
# ---------------------------------------------------------------------------


@pytest.fixture
def monthly_scenario(db_session, test_organization, client, org_headers):
    """Escenario rico distribuido en Feb y Mar 2026 para tests del P&L Mensual.

    - Compra inicial feb 1 (stock + costo promedio)
    - Venta feb 10 (regular, dentro de mes feb)
    - Venta cross-month: reg feb 28, liq mar 3 — debe contar en mes "4 Feb – 3 Mar"
      con cutoff_day=4 y en "Mar 2026" con cutoff_day=1
    - Venta mar 15 con comision a service_provider (commissions_paid_sales)
    - DP mar 5 con comision (commissions_paid_dp)
    - expense en feb y mar para operating_expenses cross-month
    """
    org_id = test_organization.id
    h = org_headers

    cat = create_material_category(db_session, org_id, "MonthlyMat")
    bu = create_business_unit(db_session, org_id, "MonthlyBU")
    mat = create_material(db_session, org_id, "MM-CH", "Chatarra MM", cat.id, bu.id)
    wh = create_warehouse(db_session, org_id, "Bodega MM")
    acc = create_account(db_session, org_id, "Cuenta MM", balance=10_000_000)

    exp_cat = create_expense_category(db_session, org_id, "Admin MM", is_direct=False)

    supplier = create_third_party_with_category(db_session, org_id, "Prov MM", "material_supplier")
    customer = create_third_party_with_category(db_session, org_id, "Cli MM", "customer")
    supplier_dp = create_third_party_with_category(db_session, org_id, "Prov DP MM", "material_supplier")
    customer_dp = create_third_party_with_category(db_session, org_id, "Cli DP MM", "customer")
    comisionista = create_third_party_with_category(db_session, org_id, "Com MM", "service_provider")

    db_session.commit()

    # Compra inicial feb 1 (asegura stock + costo promedio para ventas)
    api_create_purchase(
        client, h, supplier_id=supplier.id,
        lines=[{"material_id": mat.id, "quantity": 500, "unit_price": 5000, "warehouse_id": wh.id}],
        auto_liquidate=True, date="2026-02-01",
    )

    # Venta A: feb 10 liq feb 10 → cuenta en Feb 2026 (mes calendario)
    #           o en "4 Feb – 3 Mar" (cutoff=4) [feb 10 esta entre feb 4 y mar 3]
    api_create_sale(
        client, h, customer_id=customer.id, warehouse_id=wh.id,
        lines=[{"material_id": mat.id, "quantity": 10, "unit_price": 8000}],
        auto_liquidate=True, date="2026-02-10",
    )

    # Venta B: reg feb 28 / liq mar 3 — CROSS-MONTH
    # Con date_field=liquidated_at:
    #   cutoff=1: cuenta en Mar 2026 (liq mar 3)
    #   cutoff=4: cuenta en "4 Feb – 3 Mar" (mes contable que termina mar 3)
    sale_b = api_create_sale(
        client, h, customer_id=customer.id, warehouse_id=wh.id,
        lines=[{"material_id": mat.id, "quantity": 20, "unit_price": 8500}],
        auto_liquidate=False, date="2026-02-28",
    )
    resp = client.patch(
        f"/api/v1/sales/{sale_b['id']}/liquidate",
        json={"liquidation_date": "2026-03-03"},
        headers=h,
    )
    assert resp.status_code == 200, resp.json()

    # Venta C: mar 15 / liq mar 15 con comision a service_provider → commissions_paid_sales
    api_create_sale(
        client, h, customer_id=customer.id, warehouse_id=wh.id,
        lines=[{"material_id": mat.id, "quantity": 15, "unit_price": 9000}],
        commissions=[{
            "third_party_id": str(comisionista.id),
            "concept": "Venta C com",
            "commission_type": "fixed",
            "commission_value": 10000,
        }],
        auto_liquidate=True, date="2026-03-15",
    )

    # DP A: mar 5 con comision → commissions_paid_dp
    api_create_double_entry(
        client, h, supplier_id=supplier_dp.id, customer_id=customer_dp.id,
        lines=[{"material_id": mat.id, "quantity": 30, "purchase_unit_price": 4000, "sale_unit_price": 6000}],
        commissions=[{
            "third_party_id": str(comisionista.id),
            "concept": "DP A com",
            "commission_type": "fixed",
            "commission_value": 5000,
        }],
        auto_liquidate=True, date="2026-03-05",
    )

    # expense feb 12 (operating_expenses en Feb)
    api_money_movement(client, h, "expense", {
        "account_id": acc.id, "expense_category_id": exp_cat.id,
        "amount": 50_000, "date": "2026-02-12T12:00:00", "description": "Gasto Feb",
    })
    # expense mar 20 (operating_expenses en Mar)
    api_money_movement(client, h, "expense", {
        "account_id": acc.id, "expense_category_id": exp_cat.id,
        "amount": 75_000, "date": "2026-03-20T12:00:00", "description": "Gasto Mar",
    })

    return {"mat": mat, "wh": wh, "acc": acc, "comisionista": comisionista}


# ---------------------------------------------------------------------------
# Tests del endpoint y RBAC
# ---------------------------------------------------------------------------


def _get_monthly(client, headers, *, date_from, date_to, cutoff_day=1, expect_status=200):
    resp = client.get(
        "/api/v1/reports/profit-and-loss/monthly",
        params={"date_from": date_from, "date_to": date_to, "cutoff_day": cutoff_day},
        headers=headers,
    )
    assert resp.status_code == expect_status, resp.json()
    return resp.json() if expect_status == 200 else resp


class TestPnlMonthlyEndpoint:
    def test_pnl_monthly_periods_sum_to_total_when_aligned(self, client, org_headers, monthly_scenario):
        """Rango alineado a meses calendario completos → sum(periods) == totals (campo por campo)."""
        data = _get_monthly(
            client, org_headers,
            date_from="2026-02-01", date_to="2026-03-31", cutoff_day=1,
        )
        assert len(data["periods"]) == 2  # Feb + Mar
        assert data["periods"][0]["label"] == "Feb 2026"
        assert data["periods"][1]["label"] == "Mar 2026"

        # Paridad campo por campo: suma de periods == totals
        fields = ["sales_revenue", "cost_of_goods_sold", "double_entry_profit",
                  "operating_expenses", "commissions_paid_sales", "commissions_paid_dp",
                  "net_profit"]
        for f in fields:
            period_sum = sum(p[f] for p in data["periods"])
            assert period_sum == pytest.approx(data["totals"][f], abs=1.0), \
                f"Mismatch {f}: periods sum={period_sum}, totals={data['totals'][f]}"

    def test_pnl_monthly_rbac(self, client, org_headers, monthly_scenario, db_session, test_organization):
        """Sin permisos reports.view ni reports.view_pnl → 403."""
        # Crear usuario sin permisos
        from app.models.user import User, OrganizationMember
        from app.models.role import Role
        from app.core.security import get_password_hash, create_access_token

        bare_user = User(
            email="bare_monthly@test.com",
            hashed_password=get_password_hash("test_password"),
            full_name="Bare Monthly",
            is_active=True,
        )
        db_session.add(bare_user)
        db_session.flush()

        # Crear rol sin permisos relevantes
        bare_role = Role(
            organization_id=test_organization.id,
            name="bare_monthly_role",
            display_name="Sin Permisos Monthly",
            description="Sin permisos de reportes",
            is_system_role=False,
        )
        db_session.add(bare_role)
        db_session.flush()

        db_session.add(OrganizationMember(
            organization_id=test_organization.id,
            user_id=bare_user.id,
            role_id=bare_role.id,
        ))
        db_session.commit()

        token = create_access_token(data={"sub": str(bare_user.id)})
        bare_headers = {
            "Authorization": f"Bearer {token}",
            "X-Organization-ID": str(test_organization.id),
        }

        resp = client.get(
            "/api/v1/reports/profit-and-loss/monthly",
            params={"date_from": "2026-02-01", "date_to": "2026-03-31"},
            headers=bare_headers,
        )
        assert resp.status_code == 403, resp.json()

    def test_pnl_monthly_cutoff_day_validation(self, client, org_headers):
        """cutoff_day=0 o 29 → 422 (Pydantic Query ge=1, le=28)."""
        resp = client.get(
            "/api/v1/reports/profit-and-loss/monthly",
            params={"date_from": "2026-02-01", "date_to": "2026-03-31", "cutoff_day": 0},
            headers=org_headers,
        )
        assert resp.status_code == 422

        resp = client.get(
            "/api/v1/reports/profit-and-loss/monthly",
            params={"date_from": "2026-02-01", "date_to": "2026-03-31", "cutoff_day": 29},
            headers=org_headers,
        )
        assert resp.status_code == 422

    def test_pnl_monthly_24_months_cap(self, client, org_headers):
        """Rango que produce 25+ meses → 422 con detail descriptivo."""
        # 26 meses calendario: 2024-01-01 → 2026-02-28
        resp = client.get(
            "/api/v1/reports/profit-and-loss/monthly",
            params={
                "date_from": "2024-01-01",
                "date_to": "2026-02-28",
                "cutoff_day": 1,
            },
            headers=org_headers,
        )
        assert resp.status_code == 422, resp.json()
        detail = resp.json().get("detail", "")
        assert "meses" in detail.lower(), f"Detail no menciona 'meses': {detail}"


# ---------------------------------------------------------------------------
# 🔴 Guardrail BLOQUEANTE: paridad celda↔listado
# ---------------------------------------------------------------------------


class TestPnlMonthlyCellDrilldownParity:
    """Para cada mes M y cada linea clave del P&L, sum(listado destino) == celda.

    Sin este guardrail, no hay garantia de que el drill-down por celda en el
    tab Mensual respete los bounds del mes contable. Equivalente mensual de
    `test_pnl_drilldown_parity.py`.

    Cubre ≥2 meses × ≥3 lineas = 6 aserciones minimas. Incluye una venta
    cross-month (reg feb 28 / liq mar 3) para validar boundaries de
    date_field=liquidated_at en el dia del cutoff.
    """

    def _sum_listing(self, client, headers, url, params, amount_key="amount"):
        total = Decimal("0")
        skip = 0
        limit = 100
        while True:
            p = {**params, "skip": skip, "limit": limit}
            resp = client.get(url, params=p, headers=headers)
            assert resp.status_code == 200, f"{url} -> {resp.status_code}: {resp.json()}"
            data = resp.json()
            items = data.get("items", data) if isinstance(data, dict) else data
            for it in items:
                total += Decimal(str(it[amount_key]))
            if len(items) < limit:
                break
            skip += limit
        return total

    def test_pnl_monthly_cell_drilldown_matches_listing(self, client, org_headers, monthly_scenario):
        """Test BLOQUEANTE: cada celda del tab Mensual coincide con su listado destino.

        Configura cutoff_day=1 (mes calendario) y rango Feb-Mar 2026 → 2 columnas.
        Verifica 3 lineas clave por cada mes contable:
          - sales_revenue (drill: /sales con dp_filter=exclude, date_field=liquidated_at)
          - commissions_paid_sales (drill: /money-movements con commission_source=sale)
          - operating_expenses (drill: /money-movements con movement_type=expense
            agregado por source_type='expense' del breakdown)

        El cross-month sale (reg feb 28 / liq mar 3) debe contar en Mar (liq),
        NO en Feb. Si el drill-down ignora date_field=liquidated_at o no respeta
        los bounds mes-especificos, el assert revienta.
        """
        data = _get_monthly(
            client, org_headers,
            date_from="2026-02-01", date_to="2026-03-31", cutoff_day=1,
        )
        periods = data["periods"]
        assert len(periods) == 2

        for period in periods:
            period_from = period["period_from"]
            period_to = period["period_to"]
            label = period["label"]

            # --- Linea 1: sales_revenue (drill #49 con dp_filter + date_field) ---
            sales_listing = self._sum_listing(
                client, org_headers, "/api/v1/sales",
                params={
                    "date_from": period_from, "date_to": period_to,
                    "dp_filter": "exclude", "date_field": "liquidated_at",
                    "status_filter": "liquidated",
                },
                amount_key="total_amount",
            )
            assert sales_listing == pytest.approx(period["sales_revenue"], abs=1.0), \
                f"[{label}] sales_revenue: cell={period['sales_revenue']}, listing={sales_listing}"

            # --- Linea 2: commissions_paid_sales (drill con commission_source=sale) ---
            comm_sales_listing = self._sum_listing(
                client, org_headers, "/api/v1/money-movements/",
                params={
                    "date_from": period_from, "date_to": period_to,
                    "movement_type": "commission_accrual",
                    "commission_source": "sale",
                    "status_filter": "confirmed",
                },
            )
            assert comm_sales_listing == pytest.approx(period["commissions_paid_sales"], abs=1.0), \
                f"[{label}] commissions_paid_sales: cell={period['commissions_paid_sales']}, listing={comm_sales_listing}"

            # --- Linea 3: operating_expenses (sum del breakdown 'expense' del mes) ---
            # El drill por linea de gasto agregada va a /money-movements
            # con movement_type=expense; lo verifico contra el breakdown_total
            # del mismo source_type — es lo que muestra el tab Periodo.
            expense_breakdown = sum(
                Decimal(str(b["total_amount"]))
                for b in period.get("expenses_by_category", [])
                if b.get("source_type") == "expense"
            )
            expense_listing = self._sum_listing(
                client, org_headers, "/api/v1/money-movements/",
                params={
                    "date_from": period_from, "date_to": period_to,
                    "movement_type": "expense",
                    "status_filter": "confirmed",
                },
            )
            assert expense_listing == pytest.approx(float(expense_breakdown), abs=1.0), \
                f"[{label}] expense breakdown: cell={expense_breakdown}, listing={expense_listing}"
