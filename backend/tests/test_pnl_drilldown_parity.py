"""
Test de paridad P&L ↔ Listados (drill-down).

Guardrail del feature: si alguno de estos asserts falla, la promesa de
"suma del listado = línea del P&L" se rompe. Cada línea del P&L tiene un
endpoint destino con filtros que deben replicar EXACTAMENTE la lógica del
`_calculate_profit` para que la suma de los items coincida con el número
del reporte.

Estrategia:
- Setup: operaciones distribuidas en febrero y marzo 2026, algunas
  registradas en febrero y liquidadas en marzo (cross-month) para
  verificar que `date_field=liquidated_at` se respeta.
- Consulta P&L para `date_from=2026-03-01`, `date_to=2026-03-31`.
- Para cada métrica del P&L, consulta el listado destino con los filtros
  del drill-down y verifica que `sum(items) == métrica` (tolerancia $1).
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.models.money_movement import MoneyMovement
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
    api_create_adjustment,
    api_create_transformation,
    api_money_movement,
)


# Mes del P&L bajo prueba
PNL_FROM = "2026-03-01"
PNL_TO = "2026-03-31"


def _dt(d_str: str, *, hour: int = 12) -> datetime:
    """Helper: 'YYYY-MM-DD' -> datetime UTC mediodía."""
    y, m, day = map(int, d_str.split("-"))
    return datetime(y, m, day, hour, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def scenario(db_session, test_organization, client, org_headers):
    """Construye un escenario rico con operaciones en feb/mar 2026.

    Marzo es el mes auditado. Incluye:
    - Venta normal registrada y liquidada en marzo
    - Venta registrada feb 28, liquidada mar 3 (cross-month — drill por liquidated_at)
    - Venta DP-asociada (debe excluirse de Ingresos por Ventas)
    - DP registrada y liquidada en marzo
    - DP registrada feb 28, liquidada mar 3 (cross-month)
    - Ajuste de inventario (aumento + disminución)
    - Ajuste con marker de migración (debe excluirse)
    - service_income, commission_accrual
    - tp_adjustment_credit (gain) + tp_adjustment_debit (loss)
    - expense, provision_expense, expense_accrual (vía endpoints)
    - deferred_expense, depreciation_expense (vía DB directo)
    - Transformación con ganancia + merma
    """
    org_id = test_organization.id
    h = org_headers

    cat = create_material_category(db_session, org_id, "Metales PNL")
    bu = create_business_unit(db_session, org_id, "BU PNL")
    mat = create_material(db_session, org_id, "PNL-CH", "Chatarra PNL", cat.id, bu.id)
    mat_dest = create_material(db_session, org_id, "PNL-CU", "Cobre PNL", cat.id, bu.id)
    wh = create_warehouse(db_session, org_id, "Bodega PNL")
    acc = create_account(db_session, org_id, "Cuenta PNL", balance=10_000_000)

    exp_cat_direct = create_expense_category(db_session, org_id, "Flete PNL", is_direct=True)
    exp_cat_admin = create_expense_category(db_session, org_id, "Admin PNL", is_direct=False)
    exp_cat_prov = create_expense_category(db_session, org_id, "Provision PNL", is_direct=False)
    exp_cat_accr = create_expense_category(db_session, org_id, "Pasivo PNL", is_direct=False)
    exp_cat_def = create_expense_category(db_session, org_id, "Diferido PNL", is_direct=False)
    exp_cat_dep = create_expense_category(db_session, org_id, "Depreciacion PNL", is_direct=False)

    supplier = create_third_party_with_category(db_session, org_id, "Prov PNL", "material_supplier")
    customer = create_third_party_with_category(db_session, org_id, "Cli PNL", "customer")
    supplier_dp = create_third_party_with_category(db_session, org_id, "Prov DP PNL", "material_supplier")
    customer_dp = create_third_party_with_category(db_session, org_id, "Cli DP PNL", "customer")
    comisionista = create_third_party_with_category(db_session, org_id, "Com PNL", "service_provider")
    liability_tp = create_third_party_with_category(db_session, org_id, "Pasivo TP PNL", "liability")
    provision_tp = create_third_party_with_category(db_session, org_id, "Prov TP PNL", "provision")
    service_tp = create_third_party_with_category(db_session, org_id, "Servicio PNL", "service_provider")
    customer_adj = create_third_party_with_category(db_session, org_id, "Cli Ajuste", "customer")

    db_session.commit()

    # ----- Inventario inicial: 1 compra grande liquidada en febrero -----
    api_create_purchase(
        client, h, supplier_id=supplier.id,
        lines=[{"material_id": mat.id, "quantity": 1000, "unit_price": 5000, "warehouse_id": wh.id}],
        auto_liquidate=True, date="2026-02-01",
    )
    # Compra de mat_dest para que tenga avg_cost (necesario para transformacion average_cost)
    api_create_purchase(
        client, h, supplier_id=supplier.id,
        lines=[{"material_id": mat_dest.id, "quantity": 50, "unit_price": 7000, "warehouse_id": wh.id}],
        auto_liquidate=True, date="2026-02-01",
    )

    # ----- Marzo: ventas normales -----
    # Venta A: feb 28 / liq feb 28 → NO debe contar en P&L marzo
    api_create_sale(
        client, h, customer_id=customer.id, warehouse_id=wh.id,
        lines=[{"material_id": mat.id, "quantity": 10, "unit_price": 7000}],
        auto_liquidate=True, date="2026-02-28",
    )

    # Venta B: feb 28 / liq mar 3 → SI debe contar (drill por liquidated_at)
    sale_b = api_create_sale(
        client, h, customer_id=customer.id, warehouse_id=wh.id,
        lines=[{"material_id": mat.id, "quantity": 20, "unit_price": 8000}],
        auto_liquidate=False, date="2026-02-28",
    )
    # Liquidar con liquidation_date=mar 3
    resp = client.patch(
        f"/api/v1/sales/{sale_b['id']}/liquidate",
        json={"liquidation_date": "2026-03-03"},
        headers=h,
    )
    assert resp.status_code == 200, resp.json()

    # Venta C: mar 10 / liq mar 10 → SI debe contar
    api_create_sale(
        client, h, customer_id=customer.id, warehouse_id=wh.id,
        lines=[{"material_id": mat.id, "quantity": 15, "unit_price": 9000}],
        auto_liquidate=True, date="2026-03-10",
    )

    # ----- DPs -----
    # DP A: mar 5 / liq mar 5 — con comision para testear split commissions_paid_dp
    api_create_double_entry(
        client, h, supplier_id=supplier_dp.id, customer_id=customer_dp.id,
        lines=[{"material_id": mat.id, "quantity": 50, "purchase_unit_price": 4000, "sale_unit_price": 6000}],
        commissions=[{
            "third_party_id": str(comisionista.id),
            "concept": "Intermediario DP",
            "commission_type": "fixed",
            "commission_value": 15000,
        }],
        auto_liquidate=True, date="2026-03-05",
    )
    # DP B: feb 28 reg / liq mar 3 (cross-month)
    dp_b = api_create_double_entry(
        client, h, supplier_id=supplier_dp.id, customer_id=customer_dp.id,
        lines=[{"material_id": mat.id, "quantity": 30, "purchase_unit_price": 4500, "sale_unit_price": 6500}],
        auto_liquidate=False, date="2026-02-28",
    )
    resp = client.patch(
        f"/api/v1/double-entries/{dp_b['id']}/liquidate",
        json={"liquidation_date": "2026-03-03"},
        headers=h,
    )
    assert resp.status_code == 200, resp.json()

    # ----- Ajustes de inventario en marzo -----
    api_create_adjustment(
        client, h, adjustment_type="increase",
        material_id=mat.id, warehouse_id=wh.id,
        quantity=10, unit_cost=5000, date="2026-03-08",
        reason="Sobrante encontrado",
    )
    api_create_adjustment(
        client, h, adjustment_type="decrease",
        material_id=mat.id, warehouse_id=wh.id,
        quantity=5, date="2026-03-09",
        reason="Faltante físico",
    )
    # Seed de migración: debe EXCLUIRSE del P&L (decisión #28)
    api_create_adjustment(
        client, h, adjustment_type="increase",
        material_id=mat.id, warehouse_id=wh.id,
        quantity=100, unit_cost=5000, date="2026-03-01",
        reason="Carga inicial migracion PNL",
    )

    # ----- service_income en marzo -----
    api_money_movement(client, h, "service-income", {
        "account_id": acc.id, "amount": 200_000,
        "date": "2026-03-12T12:00:00", "description": "Servicio",
    })

    # ----- tp_adjustment_credit (gain) en marzo -----
    api_money_movement(client, h, "tp-adjustment-credit", {
        "third_party_id": customer_adj.id, "amount": 150_000,
        "adjustment_class": "gain",
        "date": "2026-03-14T12:00:00", "description": "Ajuste favor",
    })
    # tp_adjustment_debit (loss) en marzo
    api_money_movement(client, h, "tp-adjustment-debit", {
        "third_party_id": customer_adj.id, "amount": 90_000,
        "adjustment_class": "loss",
        "date": "2026-03-15T12:00:00", "description": "Ajuste contra",
    })

    # ----- expense en marzo -----
    api_money_movement(client, h, "expense", {
        "account_id": acc.id, "expense_category_id": exp_cat_admin.id,
        "amount": 100_000, "date": "2026-03-16T12:00:00", "description": "Gasto",
    })

    # ----- fondear provision (en feb, fuera del rango P&L) -----
    api_money_movement(client, h, "provision-deposit", {
        "provision_id": provision_tp.id, "account_id": acc.id,
        "amount": 100_000, "date": "2026-02-15T12:00:00", "description": "Deposito provision",
    })
    # provision_expense en marzo (gasta de la provision)
    api_money_movement(client, h, "provision-expense", {
        "provision_id": provision_tp.id,
        "expense_category_id": exp_cat_prov.id,
        "amount": 60_000, "date": "2026-03-17T12:00:00", "description": "Provision gasto",
    })

    # ----- expense_accrual en marzo -----
    api_money_movement(client, h, "expense-accrual", {
        "third_party_id": liability_tp.id,
        "expense_category_id": exp_cat_accr.id,
        "amount": 80_000, "date": "2026-03-18T12:00:00", "description": "Causacion",
    })

    # ----- deferred_expense y depreciation_expense: insert directo (no hay endpoint público) -----
    db_session.add(MoneyMovement(
        organization_id=org_id, movement_type="deferred_expense",
        amount=Decimal("40000"), expense_category_id=exp_cat_def.id,
        description="Cuota diferida PNL",
        date=_dt("2026-03-19"), status="confirmed", movement_number=900001,
    ))
    db_session.add(MoneyMovement(
        organization_id=org_id, movement_type="depreciation_expense",
        amount=Decimal("30000"), expense_category_id=exp_cat_dep.id,
        description="Depreciacion PNL",
        date=_dt("2026-03-20"), status="confirmed", movement_number=900002,
    ))

    # ----- commission_accrual en marzo (insert directo — normalmente auto-creado al liquidar) -----
    db_session.add(MoneyMovement(
        organization_id=org_id, movement_type="commission_accrual",
        amount=Decimal("25000"),
        third_party_id=comisionista.id,
        description="Comision PNL",
        date=_dt("2026-03-21"), status="confirmed", movement_number=900003,
    ))
    db_session.commit()

    # ----- Transformación en marzo (gain + waste) -----
    # 100 kg fuente a $5000 = $500.000.
    # waste_value = 5 × 5000 = $25.000 (perdida)
    # distributable = 500.000 - 25.000 = 475.000
    # average_cost: 95 kg dest × $7000 (avg_cost mat_dest) = $665.000
    # value_difference = 665.000 - 475.000 = +190.000 (ganancia)
    api_create_transformation(
        client, h,
        source_material_id=mat.id, source_warehouse_id=wh.id,
        source_quantity=100, waste_quantity=5,
        cost_distribution="average_cost",
        lines=[{"destination_material_id": mat_dest.id,
                "destination_warehouse_id": wh.id,
                "quantity": 95}],
        reason="Transform PNL", date="2026-03-22",
    )

    return {
        "mat": mat, "wh": wh, "acc": acc,
        "supplier": supplier, "customer": customer,
        "supplier_dp": supplier_dp, "customer_dp": customer_dp,
        "comisionista": comisionista,
    }


# ---------------------------------------------------------------------------
# Helpers de listado: sumar todos los items paginados.
# ---------------------------------------------------------------------------

def _sum_listing(client, headers, url: str, params: dict, amount_key: str = "amount") -> Decimal:
    """Página por página, suma `amount_key` de todos los items del listado."""
    total = Decimal("0")
    skip = 0
    limit = 100
    while True:
        p = {**params, "skip": skip, "limit": limit}
        resp = client.get(url, params=p, headers=headers)
        assert resp.status_code == 200, f"GET {url} -> {resp.status_code}: {resp.json()}"
        data = resp.json()
        items = data.get("items", data) if isinstance(data, dict) else data
        for it in items:
            total += Decimal(str(it[amount_key]))
        n = len(items)
        if n < limit:
            break
        skip += limit
    return total


def _get_pnl(client, headers, *, date_from=PNL_FROM, date_to=PNL_TO) -> dict:
    resp = client.get(
        "/api/v1/reports/profit-and-loss",
        params={"date_from": date_from, "date_to": date_to},
        headers=headers,
    )
    assert resp.status_code == 200, resp.json()
    return resp.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPnLDrilldownParity:
    """Cada test compara una línea del P&L contra la suma del listado destino.

    Si alguno falla → la URL del drill-down no produce el mismo set que el P&L.
    """

    def test_sales_revenue_parity(self, client, org_headers, scenario):
        """#1 Ingresos por Ventas == sum(sales.total_amount) con
        dp_filter=exclude, date_field=liquidated_at, status=liquidated.
        """
        pnl = _get_pnl(client, org_headers)

        listing_total = _sum_listing(
            client, org_headers, "/api/v1/sales",
            params={
                "date_from": PNL_FROM, "date_to": PNL_TO,
                "dp_filter": "exclude", "date_field": "liquidated_at",
                "status_filter": "liquidated",
            },
            amount_key="total_amount",
        )

        assert listing_total == pytest.approx(pnl["sales_revenue"], abs=1.0), \
            f"sales_revenue parity: P&L={pnl['sales_revenue']}, listing={listing_total}"

    def test_cogs_parity(self, client, org_headers, scenario):
        """#3 COGS == sum(total_amount - total_profit) sobre mismo set que ventas."""
        pnl = _get_pnl(client, org_headers)

        # Sumar `total_amount - total_profit` por venta liquidada.
        total_amount = Decimal("0")
        total_profit = Decimal("0")
        skip = 0
        while True:
            resp = client.get(
                "/api/v1/sales",
                params={
                    "date_from": PNL_FROM, "date_to": PNL_TO,
                    "dp_filter": "exclude", "date_field": "liquidated_at",
                    "status_filter": "liquidated",
                    "skip": skip, "limit": 100,
                },
                headers=org_headers,
            )
            assert resp.status_code == 200
            items = resp.json()["items"]
            for it in items:
                total_amount += Decimal(str(it["total_amount"]))
                total_profit += Decimal(str(it["total_profit"]))
            if len(items) < 100:
                break
            skip += 100

        derived_cogs = total_amount - total_profit
        assert derived_cogs == pytest.approx(pnl["cost_of_goods_sold"], abs=1.0), \
            f"COGS parity: P&L={pnl['cost_of_goods_sold']}, derived={derived_cogs}"

    def test_double_entry_profit_parity(self, client, org_headers, scenario):
        """#4 Utilidad Pasa Mano == sum(dp.profit) con date_field=liquidated_at."""
        pnl = _get_pnl(client, org_headers)

        listing_total = _sum_listing(
            client, org_headers, "/api/v1/double-entries",
            params={
                "date_from": PNL_FROM, "date_to": PNL_TO,
                "date_field": "liquidated_at",
                "status_filter": "liquidated",
            },
            amount_key="profit",
        )

        assert listing_total == pytest.approx(pnl["double_entry_profit"], abs=1.0), \
            f"DE profit parity: P&L={pnl['double_entry_profit']}, listing={listing_total}"

    def test_service_income_parity(self, client, org_headers, scenario):
        """#2 Ingresos por Servicios == sum(mm.amount) con CSV de tipos.

        Desde W1 la linea suma tambien la factura de maquila/flete de las
        Salidas a Willard (`service_income_accrual`), que va en un bloque de
        query propio para poder fragmentar por sede sin crear linea nueva. El
        listado tiene que consultar los DOS o el drill-down deja de cuadrar.
        """
        pnl = _get_pnl(client, org_headers)

        listing_total = _sum_listing(
            client, org_headers, "/api/v1/money-movements/",
            params={
                "date_from": PNL_FROM, "date_to": PNL_TO,
                "movement_type": "service_income,service_income_accrual",
                "status_filter": "confirmed",
            },
        )

        assert listing_total == pytest.approx(pnl["service_income"], abs=1.0), \
            f"service_income parity: P&L={pnl['service_income']}, listing={listing_total}"

    def test_tp_adjustment_gain_parity(self, client, org_headers, scenario):
        """#8 Ganancia Ajuste Terceros == sum(amount) con CSV de tipos + adjustment_class=gain."""
        pnl = _get_pnl(client, org_headers)

        listing_total = _sum_listing(
            client, org_headers, "/api/v1/money-movements/",
            params={
                "date_from": PNL_FROM, "date_to": PNL_TO,
                "movement_type": "tp_adjustment_credit,tp_adjustment_debit",
                "adjustment_class": "gain",
                "status_filter": "confirmed",
            },
        )

        assert listing_total == pytest.approx(pnl["tp_adjustment_gain"], abs=1.0), \
            f"tp_adj_gain parity: P&L={pnl['tp_adjustment_gain']}, listing={listing_total}"

    def test_tp_adjustment_loss_parity(self, client, org_headers, scenario):
        """#9 Pérdida Ajuste Terceros == sum(amount) con CSV de tipos + adjustment_class=loss."""
        pnl = _get_pnl(client, org_headers)

        listing_total = _sum_listing(
            client, org_headers, "/api/v1/money-movements/",
            params={
                "date_from": PNL_FROM, "date_to": PNL_TO,
                "movement_type": "tp_adjustment_credit,tp_adjustment_debit",
                "adjustment_class": "loss",
                "status_filter": "confirmed",
            },
        )

        assert listing_total == pytest.approx(pnl["tp_adjustment_loss"], abs=1.0), \
            f"tp_adj_loss parity: P&L={pnl['tp_adjustment_loss']}, listing={listing_total}"

    def test_expense_direct_parity(self, client, org_headers, scenario):
        """#10 Gastos Directos == sum(amount) con movement_type=expense."""
        pnl = _get_pnl(client, org_headers)

        listing_total = _sum_listing(
            client, org_headers, "/api/v1/money-movements/",
            params={
                "date_from": PNL_FROM, "date_to": PNL_TO,
                "movement_type": "expense",
                "status_filter": "confirmed",
            },
        )

        # `expense` aporta a operating_expenses pero el P&L lo agrega; comparamos directo
        # contra suma del breakdown de categoría para mt=expense.
        expense_total = sum(
            Decimal(str(b["total_amount"]))
            for b in pnl.get("expenses_by_category", [])
            if b.get("source_type") == "expense"
        )
        assert listing_total == pytest.approx(expense_total, abs=1.0), \
            f"expense parity: P&L breakdown={expense_total}, listing={listing_total}"

    def test_provision_expense_parity(self, client, org_headers, scenario):
        """#11 Gastos desde Provisiones == sum(amount) con movement_type=provision_expense."""
        pnl = _get_pnl(client, org_headers)

        listing_total = _sum_listing(
            client, org_headers, "/api/v1/money-movements/",
            params={
                "date_from": PNL_FROM, "date_to": PNL_TO,
                "movement_type": "provision_expense",
                "status_filter": "confirmed",
            },
        )

        expense_total = sum(
            Decimal(str(b["total_amount"]))
            for b in pnl.get("expenses_by_category", [])
            if b.get("source_type") == "provision_expense"
        )
        assert listing_total == pytest.approx(expense_total, abs=1.0), \
            f"provision_expense parity: P&L breakdown={expense_total}, listing={listing_total}"

    def test_expense_accrual_parity(self, client, org_headers, scenario):
        """#12 Gastos Causados == sum(amount) con movement_type=expense_accrual."""
        pnl = _get_pnl(client, org_headers)

        listing_total = _sum_listing(
            client, org_headers, "/api/v1/money-movements/",
            params={
                "date_from": PNL_FROM, "date_to": PNL_TO,
                "movement_type": "expense_accrual",
                "status_filter": "confirmed",
            },
        )

        expense_total = sum(
            Decimal(str(b["total_amount"]))
            for b in pnl.get("expenses_by_category", [])
            if b.get("source_type") == "expense_accrual"
        )
        assert listing_total == pytest.approx(expense_total, abs=1.0), \
            f"expense_accrual parity: P&L breakdown={expense_total}, listing={listing_total}"

    def test_deferred_expense_parity(self, client, org_headers, scenario):
        """#13 Gastos Diferidos == sum(amount) con movement_type=deferred_expense."""
        pnl = _get_pnl(client, org_headers)

        listing_total = _sum_listing(
            client, org_headers, "/api/v1/money-movements/",
            params={
                "date_from": PNL_FROM, "date_to": PNL_TO,
                "movement_type": "deferred_expense",
                "status_filter": "confirmed",
            },
        )

        expense_total = sum(
            Decimal(str(b["total_amount"]))
            for b in pnl.get("expenses_by_category", [])
            if b.get("source_type") == "deferred_expense"
        )
        assert listing_total == pytest.approx(expense_total, abs=1.0), \
            f"deferred_expense parity: P&L breakdown={expense_total}, listing={listing_total}"

    def test_depreciation_expense_parity(self, client, org_headers, scenario):
        """#14 Depreciación == sum(amount) con movement_type=depreciation_expense."""
        pnl = _get_pnl(client, org_headers)

        listing_total = _sum_listing(
            client, org_headers, "/api/v1/money-movements/",
            params={
                "date_from": PNL_FROM, "date_to": PNL_TO,
                "movement_type": "depreciation_expense",
                "status_filter": "confirmed",
            },
        )

        expense_total = sum(
            Decimal(str(b["total_amount"]))
            for b in pnl.get("expenses_by_category", [])
            if b.get("source_type") == "depreciation_expense"
        )
        assert listing_total == pytest.approx(expense_total, abs=1.0), \
            f"depreciation_expense parity: P&L breakdown={expense_total}, listing={listing_total}"

    def test_commission_accrual_parity(self, client, org_headers, scenario):
        """#15 Comisiones Pagadas (total) == sum(amount) con movement_type=commission_accrual."""
        pnl = _get_pnl(client, org_headers)

        listing_total = _sum_listing(
            client, org_headers, "/api/v1/money-movements/",
            params={
                "date_from": PNL_FROM, "date_to": PNL_TO,
                "movement_type": "commission_accrual",
                "status_filter": "confirmed",
            },
        )

        assert listing_total == pytest.approx(pnl["commissions_paid"], abs=1.0), \
            f"commissions parity: P&L={pnl['commissions_paid']}, listing={listing_total}"

    def test_commission_accrual_sale_split_parity(self, client, org_headers, scenario):
        """#15a Comisiones de Ventas == sum con commission_source=sale (decision #49+)."""
        pnl = _get_pnl(client, org_headers)

        listing_total = _sum_listing(
            client, org_headers, "/api/v1/money-movements/",
            params={
                "date_from": PNL_FROM, "date_to": PNL_TO,
                "movement_type": "commission_accrual",
                "status_filter": "confirmed",
                "commission_source": "sale",
            },
        )

        assert listing_total == pytest.approx(pnl["commissions_paid_sales"], abs=1.0), \
            f"commissions sale parity: P&L={pnl['commissions_paid_sales']}, listing={listing_total}"

    def test_commission_accrual_dp_split_parity(self, client, org_headers, scenario):
        """#15b Comisiones de Pasa Mano == sum con commission_source=double_entry."""
        pnl = _get_pnl(client, org_headers)

        listing_total = _sum_listing(
            client, org_headers, "/api/v1/money-movements/",
            params={
                "date_from": PNL_FROM, "date_to": PNL_TO,
                "movement_type": "commission_accrual",
                "status_filter": "confirmed",
                "commission_source": "double_entry",
            },
        )

        assert listing_total == pytest.approx(pnl["commissions_paid_dp"], abs=1.0), \
            f"commissions DP parity: P&L={pnl['commissions_paid_dp']}, listing={listing_total}"

        # Sanity: la fixture inserta una comision DP de $15.000 explicita
        assert pnl["commissions_paid_dp"] > 0, "Fixture debe tener al menos una comision DP"
        # Y el split debe sumar al total
        assert pnl["commissions_paid_sales"] + pnl["commissions_paid_dp"] == pytest.approx(
            pnl["commissions_paid"], abs=1.0
        ), "sales + DP debe igualar total commissions_paid"

    def test_inventory_adjustments_parity(self, client, org_headers, scenario):
        """#7 Ajustes de Inventario == signed sum con exclude_migration_seeds=true."""
        pnl = _get_pnl(client, org_headers)

        # adjustment_net = SUM(+total_value si quantity>0, -total_value si quantity<0)
        total_signed = Decimal("0")
        skip = 0
        while True:
            resp = client.get(
                "/api/v1/inventory/adjustments",
                params={
                    "date_from": PNL_FROM, "date_to": PNL_TO,
                    "exclude_migration_seeds": "true",
                    "status": "confirmed",
                    "skip": skip, "limit": 100,
                },
                headers=org_headers,
            )
            assert resp.status_code == 200
            items = resp.json()["items"]
            for it in items:
                qty = Decimal(str(it["quantity"]))
                tv = Decimal(str(it["total_value"]))
                total_signed += tv if qty > 0 else -tv
            if len(items) < 100:
                break
            skip += 100

        assert total_signed == pytest.approx(pnl["adjustment_net"], abs=1.0), \
            f"adjustment_net parity: P&L={pnl['adjustment_net']}, listing={total_signed}"

    def test_transformation_profit_parity(self, client, org_headers, scenario):
        """#5 Ganancia/Pérdida Transformaciones == sum(value_difference)."""
        pnl = _get_pnl(client, org_headers)

        total = Decimal("0")
        skip = 0
        while True:
            resp = client.get(
                "/api/v1/inventory/transformations",
                params={
                    "date_from": PNL_FROM, "date_to": PNL_TO,
                    "status": "confirmed",
                    "skip": skip, "limit": 100,
                },
                headers=org_headers,
            )
            assert resp.status_code == 200
            items = resp.json().get("items", resp.json())
            for it in items:
                vd = it.get("value_difference")
                if vd is not None:
                    total += Decimal(str(vd))
            if len(items) < 100:
                break
            skip += 100

        assert total == pytest.approx(pnl["transformation_profit"], abs=1.0), \
            f"transformation_profit parity: P&L={pnl['transformation_profit']}, listing={total}"

    def test_waste_loss_parity(self, client, org_headers, scenario):
        """#6 Pérdida por Merma == sum(waste_value)."""
        pnl = _get_pnl(client, org_headers)

        total = Decimal("0")
        skip = 0
        while True:
            resp = client.get(
                "/api/v1/inventory/transformations",
                params={
                    "date_from": PNL_FROM, "date_to": PNL_TO,
                    "status": "confirmed",
                    "skip": skip, "limit": 100,
                },
                headers=org_headers,
            )
            assert resp.status_code == 200
            items = resp.json().get("items", resp.json())
            for it in items:
                wv = it.get("waste_value")
                if wv is not None:
                    total += Decimal(str(wv))
            if len(items) < 100:
                break
            skip += 100

        assert total == pytest.approx(pnl["waste_loss"], abs=1.0), \
            f"waste_loss parity: P&L={pnl['waste_loss']}, listing={total}"

    def test_cross_month_sale_appears_with_liquidated_at_only(
        self, client, org_headers, scenario
    ):
        """Smoke test: venta feb 28 / liq mar 3 aparece SOLO con date_field=liquidated_at."""
        # Con date_field=date (default), buscando marzo, NO debería aparecer
        # (su `date` es feb 28).
        resp_date = client.get(
            "/api/v1/sales",
            params={
                "date_from": PNL_FROM, "date_to": PNL_TO,
                "date_field": "date",
                "status_filter": "liquidated",
                "dp_filter": "exclude",
            },
            headers=org_headers,
        )
        assert resp_date.status_code == 200
        amounts_by_date = {Decimal(str(it["total_amount"])) for it in resp_date.json()["items"]}

        # Con date_field=liquidated_at, SI debería aparecer
        resp_liq = client.get(
            "/api/v1/sales",
            params={
                "date_from": PNL_FROM, "date_to": PNL_TO,
                "date_field": "liquidated_at",
                "status_filter": "liquidated",
                "dp_filter": "exclude",
            },
            headers=org_headers,
        )
        assert resp_liq.status_code == 200
        amounts_by_liq = {Decimal(str(it["total_amount"])) for it in resp_liq.json()["items"]}

        # Venta B: 20 × 8000 = 160_000
        sale_b_total = Decimal("160000")
        assert sale_b_total in amounts_by_liq, \
            f"Venta cross-month no apareció con date_field=liquidated_at: {amounts_by_liq}"
        assert sale_b_total not in amounts_by_date, \
            f"Venta cross-month apareció erróneamente con date_field=date: {amounts_by_date}"
