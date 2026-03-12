"""
Servicio de reportes y dashboard.

Clase standalone con queries de agregacion read-only.
Todos los calculos internos usan Decimal para precision.
"""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, case, cast, Date
from sqlalchemy.orm import Session

from app.models.double_entry import DoubleEntry, DoubleEntryLine
from app.models.expense_category import ExpenseCategory
from app.models.material import Material, MaterialCategory
from app.models.money_account import MoneyAccount
from app.models.money_movement import MoneyMovement
from app.models.purchase import Purchase, PurchaseLine
from app.models.sale import Sale, SaleLine
from app.models.third_party import ThirdParty

from app.models.sale import SaleCommission
from app.schemas.reports import (
    AccountAuditItem,
    AccountSummary,
    AuditBalancesResponse,
    AuditSummary,
    BalanceSheetAssets,
    BalanceSheetLiabilities,
    BalanceSheetResponse,
    CashFlowInflows,
    CashFlowOutflows,
    CashFlowResponse,
    CustomerBalance,
    CustomerRevenueSummary,
    DailyTrendItem,
    DashboardAlert,
    DashboardMetrics,
    DashboardResponse,
    ExpenseCategoryBreakdown,
    MarginAnalysisResponse,
    MaterialMargin,
    MaterialProfitSummary,
    MetricCard,
    ProfitAndLossResponse,
    ProvisionSummary,
    PurchaseByMaterial,
    PurchaseBySupplier,
    PurchaseReportResponse,
    RecentMovementItem,
    SaleByCustomer,
    SaleByMaterial,
    SalesReportResponse,
    SupplierBalance,
    SupplierVolumeSummary,
    ThirdPartyAuditItem,
    ThirdPartyBalancesResponse,
    TreasuryDashboardResponse,
)

# Direccion del efecto en el balance de la cuenta por tipo de movimiento.
# Positivo = entrada. Negativo = salida.
ACCOUNT_BALANCE_DIRECTION = {
    "collection_from_client": 1,
    "service_income": 1,
    "capital_injection": 1,
    "transfer_in": 1,
    "advance_collection": 1,
    "payment_to_supplier": -1,
    "expense": -1,
    "commission_payment": -1,
    "capital_return": -1,
    "transfer_out": -1,
    "provision_deposit": -1,
    "advance_payment": -1,
    "asset_payment": -1,
}

# Direccion del efecto en el balance del tercero por tipo de movimiento.
# Positivo = tercero nos debe mas. Negativo = tercero nos debe menos.
THIRD_PARTY_BALANCE_DIRECTION = {
    "payment_to_supplier": 1,
    "collection_from_client": -1,
    "capital_injection": -1,
    "capital_return": 1,
    "commission_payment": 1,
    "provision_deposit": -1,
    "provision_expense": 1,
    "advance_payment": 1,
    "advance_collection": -1,
    "expense_accrual": -1,          # Gasto causado: le debemos mas
    "deferred_funding": 1,          # Pago gasto diferido: prepago nos debe
    "deferred_expense": -1,         # Cuota gasto diferido: reduce prepago
    "commission_accrual": -1,        # Comision causada: les debemos comision (balance-=)
}

# Tipos de money_movement que representan inflows a cuentas
INFLOW_TYPES = frozenset([
    "collection_from_client",
    "service_income",
    "capital_injection",
    "transfer_in",
    "advance_collection",
])

# Tipos de money_movement que representan outflows de cuentas
OUTFLOW_TYPES = frozenset([
    "payment_to_supplier",
    "expense",
    "commission_payment",
    "capital_return",
    "transfer_out",
    "provision_deposit",  # Sale dinero de cuenta hacia provision
    "advance_payment",    # Anticipo a proveedor: sale dinero de cuenta
    "asset_payment",      # Pago de activo fijo: sale dinero de cuenta
    "deferred_funding",   # Pago inicial gasto diferido: sale dinero de cuenta
])
# Nota: provision_expense NO va aqui — no afecta cuentas de dinero


class ReportService:
    """Queries de agregacion read-only para reportes y dashboard."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_pct(numerator: Decimal, denominator: Decimal) -> float:
        if denominator == 0:
            return 0.0
        return float((numerator / denominator) * Decimal("100"))

    @staticmethod
    def _safe_divide(numerator: Decimal, denominator: Decimal) -> float:
        if denominator == 0:
            return 0.0
        return float(numerator / denominator)

    @staticmethod
    def _date_range(d_from: date, d_to: date):
        """Convierte date a datetime range [dt_from, dt_to) con UTC timezone.

        dt_to es exclusivo (dia siguiente a medianoche UTC) para cubrir
        offsets negativos como Colombia UTC-5.
        """
        return (
            datetime.combine(d_from, time.min, tzinfo=timezone.utc),
            datetime.combine(d_to + timedelta(days=1), time.min, tzinfo=timezone.utc),
        )

    @staticmethod
    def _change_pct(current: Decimal, previous: Decimal) -> Optional[float]:
        if previous == 0:
            return None
        return float(((current - previous) / abs(previous)) * Decimal("100"))

    # ------------------------------------------------------------------
    # P&L — Estado de Resultados
    # ------------------------------------------------------------------

    def get_profit_and_loss(
        self,
        db: Session,
        organization_id: UUID,
        date_from: date,
        date_to: date,
    ) -> ProfitAndLossResponse:
        dt_from, dt_to = self._date_range(date_from, date_to)

        # 1. Sales Revenue (ventas normales, excluye DE)
        row = db.execute(
            select(
                func.coalesce(func.sum(Sale.total_amount), 0),
                func.count(),
            ).where(
                Sale.organization_id == organization_id,
                Sale.status == "liquidated",
                Sale.double_entry_id.is_(None),
                Sale.date >= dt_from,
                Sale.date < dt_to,
            )
        ).one()
        sales_revenue = Decimal(str(row[0]))
        sales_count = row[1]

        # 2. COGS (metodo directo)
        cogs_val = db.scalar(
            select(
                func.coalesce(func.sum(SaleLine.unit_cost * SaleLine.quantity), 0)
            ).select_from(SaleLine)
            .join(Sale, SaleLine.sale_id == Sale.id)
            .where(
                Sale.organization_id == organization_id,
                Sale.status == "liquidated",
                Sale.double_entry_id.is_(None),
                Sale.date >= dt_from,
                Sale.date < dt_to,
            )
        )
        cogs = Decimal(str(cogs_val))

        # 3. Double Entry Profit (via DoubleEntryLine)
        de_row = db.execute(
            select(
                func.coalesce(
                    func.sum(
                        (DoubleEntryLine.sale_unit_price - DoubleEntryLine.purchase_unit_price)
                        * DoubleEntryLine.quantity
                    ),
                    0,
                ),
                func.count(func.distinct(DoubleEntry.id)),
            )
            .select_from(DoubleEntryLine)
            .join(DoubleEntry, DoubleEntryLine.double_entry_id == DoubleEntry.id)
            .where(
                DoubleEntry.organization_id == organization_id,
                DoubleEntry.status == "completed",
                DoubleEntry.date >= date_from,
                DoubleEntry.date <= date_to,
            )
        ).one()
        de_profit = Decimal(str(de_row[0]))
        de_count = de_row[1]

        # 3.5 Transformation profit (ganancia/perdida por valorizacion)
        from app.models.material_transformation import MaterialTransformation

        trans_row = db.execute(
            select(
                func.coalesce(func.sum(MaterialTransformation.value_difference), 0),
                func.count(),
            ).where(
                MaterialTransformation.organization_id == organization_id,
                MaterialTransformation.status == "confirmed",
                MaterialTransformation.value_difference.isnot(None),
                MaterialTransformation.date >= dt_from,
                MaterialTransformation.date < dt_to,
            )
        ).one()
        transformation_profit = Decimal(str(trans_row[0]))
        transformation_count = trans_row[1]

        # 4. Service income + expenses by category + commissions
        mm_rows = db.execute(
            select(
                MoneyMovement.movement_type,
                ExpenseCategory.id,
                ExpenseCategory.name,
                ExpenseCategory.is_direct_expense,
                func.coalesce(func.sum(MoneyMovement.amount), 0),
            )
            .outerjoin(ExpenseCategory, MoneyMovement.expense_category_id == ExpenseCategory.id)
            .where(
                MoneyMovement.organization_id == organization_id,
                MoneyMovement.status == "confirmed",
                MoneyMovement.movement_type.in_(["expense", "provision_expense", "expense_accrual", "deferred_expense", "commission_payment", "commission_accrual", "service_income"]),
                MoneyMovement.date >= dt_from,
                MoneyMovement.date < dt_to,
            )
            .group_by(
                MoneyMovement.movement_type,
                ExpenseCategory.id,
                ExpenseCategory.name,
                ExpenseCategory.is_direct_expense,
            )
        ).all()

        service_income = Decimal("0")
        operating_expenses = Decimal("0")
        commissions_paid = Decimal("0")
        expenses_by_cat: list[ExpenseCategoryBreakdown] = []

        for mt, cat_id, cat_name, is_direct, total in mm_rows:
            total_dec = Decimal(str(total))
            if mt == "service_income":
                service_income += total_dec
            elif mt in ("expense", "provision_expense", "expense_accrual", "deferred_expense"):
                operating_expenses += total_dec
                expenses_by_cat.append(ExpenseCategoryBreakdown(
                    category_id=cat_id,
                    category_name=cat_name or "Sin categoria",
                    is_direct_expense=bool(is_direct),
                    total_amount=float(total_dec),
                    source_type=mt,
                ))
            elif mt in ("commission_payment", "commission_accrual"):
                commissions_paid += total_dec

        # Calculos
        gross_profit_sales = sales_revenue - cogs
        total_gross_profit = gross_profit_sales + de_profit + service_income + transformation_profit
        net_profit = total_gross_profit - operating_expenses - commissions_paid

        total_revenue_base = sales_revenue + service_income + (
            Decimal(str(de_row[0]))  # DE total sale amount is harder, use profit base
        )
        # Para net_margin usamos sales_revenue + service_income como base
        margin_base = sales_revenue + service_income
        if de_profit > 0:
            # Si hay DE profit, incluir la parte de revenue de DE
            # DE revenue = profit + cost, pero solo tenemos profit.
            # Usamos total_gross_profit como aproximacion
            pass

        return ProfitAndLossResponse(
            period_from=date_from,
            period_to=date_to,
            sales_revenue=float(sales_revenue),
            sales_count=sales_count,
            service_income=float(service_income),
            cost_of_goods_sold=float(cogs),
            gross_profit_sales=float(gross_profit_sales),
            gross_margin_sales=self._safe_pct(gross_profit_sales, sales_revenue),
            double_entry_profit=float(de_profit),
            double_entry_count=de_count,
            transformation_profit=float(transformation_profit),
            transformation_count=transformation_count,
            total_gross_profit=float(total_gross_profit),
            operating_expenses=float(operating_expenses),
            commissions_paid=float(commissions_paid),
            net_profit=float(net_profit),
            net_margin=self._safe_pct(net_profit, margin_base) if margin_base else 0.0,
            expenses_by_category=expenses_by_cat,
        )

    # ------------------------------------------------------------------
    # Cash Flow — Flujo de Caja
    # ------------------------------------------------------------------

    def get_cash_flow(
        self,
        db: Session,
        organization_id: UUID,
        date_from: date,
        date_to: date,
    ) -> CashFlowResponse:
        dt_from, dt_to = self._date_range(date_from, date_to)
        now_dt = datetime.now(tz=timezone.utc)

        # Balance actual de todas las cuentas
        current_total = Decimal(str(
            db.scalar(
                select(func.coalesce(func.sum(MoneyAccount.current_balance), 0))
                .where(
                    MoneyAccount.organization_id == organization_id,
                    MoneyAccount.is_active == True,
                )
            )
        ))

        # --- Flujos en el PERIODO (date_from..date_to) ---

        # A. Ventas cobradas en periodo (inflow por liquidacion)
        sale_collections = Decimal(str(
            db.scalar(
                select(func.coalesce(func.sum(Sale.total_amount), 0))
                .where(
                    Sale.organization_id == organization_id,
                    Sale.status == "liquidated",
                    Sale.date >= dt_from,
                    Sale.date < dt_to,
                )
            )
        ))

        # A. Compras pagadas en periodo (outflow por liquidacion)
        purchase_payments = Decimal(str(
            db.scalar(
                select(func.coalesce(func.sum(Purchase.total_amount), 0))
                .where(
                    Purchase.organization_id == organization_id,
                    Purchase.status == "liquidated",
                    Purchase.date >= dt_from,
                    Purchase.date < dt_to,
                )
            )
        ))

        # B. Money movements en periodo
        mm_period = db.execute(
            select(
                MoneyMovement.movement_type,
                func.coalesce(func.sum(MoneyMovement.amount), 0),
            ).where(
                MoneyMovement.organization_id == organization_id,
                MoneyMovement.status == "confirmed",
                MoneyMovement.date >= dt_from,
                MoneyMovement.date < dt_to,
            ).group_by(MoneyMovement.movement_type)
        ).all()

        mm_map = {mt: Decimal(str(total)) for mt, total in mm_period}

        customer_collections = mm_map.get("collection_from_client", Decimal("0"))
        service_income = mm_map.get("service_income", Decimal("0"))
        capital_injections = mm_map.get("capital_injection", Decimal("0"))
        advance_collections = mm_map.get("advance_collection", Decimal("0"))

        supplier_payments = mm_map.get("payment_to_supplier", Decimal("0"))
        expenses = mm_map.get("expense", Decimal("0"))
        commission_payments = mm_map.get("commission_payment", Decimal("0"))
        capital_returns = mm_map.get("capital_return", Decimal("0"))
        provision_deposits = mm_map.get("provision_deposit", Decimal("0"))
        deferred_fundings = mm_map.get("deferred_funding", Decimal("0"))
        advance_payments = mm_map.get("advance_payment", Decimal("0"))
        asset_payments = mm_map.get("asset_payment", Decimal("0"))

        total_inflows = (
            sale_collections + customer_collections + service_income
            + capital_injections + advance_collections
        )
        total_outflows = (
            purchase_payments + supplier_payments + expenses
            + commission_payments + capital_returns
            + provision_deposits + deferred_fundings
            + advance_payments + asset_payments
        )
        net_flow = total_inflows - total_outflows

        # --- Opening balance: restar todos los cambios desde dt_from hasta AHORA ---

        # Ventas pagadas desde dt_from hasta ahora
        net_sales_since = Decimal(str(
            db.scalar(
                select(func.coalesce(func.sum(Sale.total_amount), 0))
                .where(
                    Sale.organization_id == organization_id,
                    Sale.status == "liquidated",
                    Sale.date >= dt_from,
                )
            )
        ))

        # Compras pagadas desde dt_from hasta ahora
        net_purchases_since = Decimal(str(
            db.scalar(
                select(func.coalesce(func.sum(Purchase.total_amount), 0))
                .where(
                    Purchase.organization_id == organization_id,
                    Purchase.status == "liquidated",
                    Purchase.date >= dt_from,
                )
            )
        ))

        # Money movements net desde dt_from hasta ahora
        mm_since = db.execute(
            select(
                MoneyMovement.movement_type,
                func.coalesce(func.sum(MoneyMovement.amount), 0),
            ).where(
                MoneyMovement.organization_id == organization_id,
                MoneyMovement.status == "confirmed",
                MoneyMovement.date >= dt_from,
            ).group_by(MoneyMovement.movement_type)
        ).all()

        net_mm_since = Decimal("0")
        for mt, total in mm_since:
            amt = Decimal(str(total))
            if mt in INFLOW_TYPES:
                net_mm_since += amt
            elif mt in OUTFLOW_TYPES:
                net_mm_since -= amt

        net_all_since = net_sales_since - net_purchases_since + net_mm_since
        opening_balance = current_total - net_all_since
        closing_balance = opening_balance + net_flow

        return CashFlowResponse(
            period_from=date_from,
            period_to=date_to,
            opening_balance=float(opening_balance),
            inflows=CashFlowInflows(
                sale_collections=float(sale_collections),
                customer_collections=float(customer_collections),
                service_income=float(service_income),
                capital_injections=float(capital_injections),
                advance_collections=float(advance_collections),
                total=float(total_inflows),
            ),
            total_inflows=float(total_inflows),
            outflows=CashFlowOutflows(
                purchase_payments=float(purchase_payments),
                supplier_payments=float(supplier_payments),
                expenses=float(expenses),
                commission_payments=float(commission_payments),
                capital_returns=float(capital_returns),
                provision_deposits=float(provision_deposits),
                deferred_fundings=float(deferred_fundings),
                advance_payments=float(advance_payments),
                asset_payments=float(asset_payments),
                total=float(total_outflows),
            ),
            total_outflows=float(total_outflows),
            net_flow=float(net_flow),
            closing_balance=float(closing_balance),
        )

    # ------------------------------------------------------------------
    # Balance Sheet — Balance General
    # ------------------------------------------------------------------

    def get_balance_sheet(
        self,
        db: Session,
        organization_id: UUID,
    ) -> BalanceSheetResponse:
        # Activos
        cash_and_bank = Decimal(str(
            db.scalar(
                select(func.coalesce(func.sum(MoneyAccount.current_balance), 0))
                .where(
                    MoneyAccount.organization_id == organization_id,
                    MoneyAccount.is_active == True,
                )
            )
        ))

        accounts_receivable = Decimal(str(
            db.scalar(
                select(func.coalesce(func.sum(ThirdParty.current_balance), 0))
                .where(
                    ThirdParty.organization_id == organization_id,
                    ThirdParty.is_customer == True,
                    ThirdParty.current_balance > 0,
                )
            )
        ))

        inventory = Decimal(str(
            db.scalar(
                select(func.coalesce(
                    func.sum(Material.current_stock_liquidated * Material.current_average_cost),
                    0,
                ))
                .where(
                    Material.organization_id == organization_id,
                    Material.is_active == True,
                )
            )
        ))

        # Gastos prepagados (terceros system_entity con balance > 0, ej: gastos diferidos)
        prepaid_expenses = Decimal(str(
            db.scalar(
                select(func.coalesce(func.sum(ThirdParty.current_balance), 0))
                .where(
                    ThirdParty.organization_id == organization_id,
                    ThirdParty.is_system_entity == True,
                    ThirdParty.current_balance > 0,
                )
            )
        ))

        # Fondos en provisiones (is_provision con balance < 0 = fondos disponibles)
        provision_funds = Decimal(str(
            db.scalar(
                select(func.coalesce(func.sum(func.abs(ThirdParty.current_balance)), 0))
                .where(
                    ThirdParty.organization_id == organization_id,
                    ThirdParty.is_provision == True,
                    ThirdParty.current_balance < 0,
                )
            )
        ))

        total_assets = cash_and_bank + accounts_receivable + inventory + prepaid_expenses + provision_funds

        # Pasivos
        accounts_payable = Decimal(str(
            db.scalar(
                select(func.coalesce(func.sum(func.abs(ThirdParty.current_balance)), 0))
                .where(
                    ThirdParty.organization_id == organization_id,
                    ThirdParty.is_supplier == True,
                    ThirdParty.current_balance < 0,
                )
            )
        ))

        investor_debt = Decimal(str(
            db.scalar(
                select(func.coalesce(func.sum(func.abs(ThirdParty.current_balance)), 0))
                .where(
                    ThirdParty.organization_id == organization_id,
                    ThirdParty.is_investor == True,
                    ThirdParty.current_balance < 0,
                )
            )
        ))

        # Pasivos laborales/otros (is_liability con balance < 0 = le debemos)
        liability_debt = Decimal(str(
            db.scalar(
                select(func.coalesce(func.sum(func.abs(ThirdParty.current_balance)), 0))
                .where(
                    ThirdParty.organization_id == organization_id,
                    ThirdParty.is_liability == True,
                    ThirdParty.current_balance < 0,
                )
            )
        ))

        total_liabilities = accounts_payable + investor_debt + liability_debt
        equity = total_assets - total_liabilities

        return BalanceSheetResponse(
            as_of_date=date.today(),
            assets=BalanceSheetAssets(
                cash_and_bank=float(cash_and_bank),
                accounts_receivable=float(accounts_receivable),
                inventory=float(inventory),
                prepaid_expenses=float(prepaid_expenses),
                provision_funds=float(provision_funds),
                total=float(total_assets),
            ),
            total_assets=float(total_assets),
            liabilities=BalanceSheetLiabilities(
                accounts_payable=float(accounts_payable),
                investor_debt=float(investor_debt),
                liability_debt=float(liability_debt),
                total=float(total_liabilities),
            ),
            total_liabilities=float(total_liabilities),
            equity=float(equity),
        )

    # ------------------------------------------------------------------
    # Purchase Report
    # ------------------------------------------------------------------

    def get_purchase_report(
        self,
        db: Session,
        organization_id: UUID,
        date_from: date,
        date_to: date,
        supplier_id: Optional[UUID] = None,
        material_id: Optional[UUID] = None,
    ) -> PurchaseReportResponse:
        dt_from, dt_to = self._date_range(date_from, date_to)

        # Base filters — solo compras liquidadas (con precios confirmados)
        base_filters = [
            Purchase.organization_id == organization_id,
            Purchase.status == "liquidated",
            Purchase.date >= dt_from,
            Purchase.date < dt_to,
        ]
        if supplier_id:
            base_filters.append(Purchase.supplier_id == supplier_id)

        line_filters = list(base_filters)
        if material_id:
            line_filters.append(PurchaseLine.material_id == material_id)

        # Totals
        totals = db.execute(
            select(
                func.coalesce(func.sum(PurchaseLine.total_price), 0),
                func.coalesce(func.sum(PurchaseLine.quantity), 0),
                func.count(func.distinct(Purchase.id)),
            )
            .select_from(PurchaseLine)
            .join(Purchase, PurchaseLine.purchase_id == Purchase.id)
            .where(*line_filters)
        ).one()
        total_amount = Decimal(str(totals[0]))
        total_quantity = Decimal(str(totals[1]))
        purchase_count = totals[2]

        # By supplier
        by_supplier_rows = db.execute(
            select(
                Purchase.supplier_id,
                ThirdParty.name,
                func.coalesce(func.sum(PurchaseLine.total_price), 0),
                func.coalesce(func.sum(PurchaseLine.quantity), 0),
                func.count(func.distinct(Purchase.id)),
            )
            .select_from(PurchaseLine)
            .join(Purchase, PurchaseLine.purchase_id == Purchase.id)
            .join(ThirdParty, Purchase.supplier_id == ThirdParty.id)
            .where(*line_filters)
            .group_by(Purchase.supplier_id, ThirdParty.name)
            .order_by(func.sum(PurchaseLine.total_price).desc())
        ).all()

        by_supplier = [
            PurchaseBySupplier(
                supplier_id=r[0], supplier_name=r[1],
                total_amount=float(r[2]), total_quantity=float(r[3]),
                purchase_count=r[4],
            ) for r in by_supplier_rows
        ]

        # By material
        by_material_rows = db.execute(
            select(
                PurchaseLine.material_id,
                Material.code,
                Material.name,
                func.coalesce(func.sum(PurchaseLine.total_price), 0),
                func.coalesce(func.sum(PurchaseLine.quantity), 0),
            )
            .select_from(PurchaseLine)
            .join(Purchase, PurchaseLine.purchase_id == Purchase.id)
            .join(Material, PurchaseLine.material_id == Material.id)
            .where(*line_filters)
            .group_by(PurchaseLine.material_id, Material.code, Material.name)
            .order_by(func.sum(PurchaseLine.total_price).desc())
        ).all()

        by_material = [
            PurchaseByMaterial(
                material_id=r[0], material_code=r[1], material_name=r[2],
                total_amount=float(r[3]), total_quantity=float(r[4]),
                average_unit_price=self._safe_divide(Decimal(str(r[3])), Decimal(str(r[4]))),
            ) for r in by_material_rows
        ]

        # Daily trend
        trend_rows = db.execute(
            select(
                cast(Purchase.date, Date).label("day"),
                func.coalesce(func.sum(Purchase.total_amount), 0),
                func.count(),
            )
            .where(*base_filters)
            .group_by(cast(Purchase.date, Date))
            .order_by(cast(Purchase.date, Date))
        ).all()

        daily_trend = [
            DailyTrendItem(date=r[0], total_amount=float(r[1]), count=r[2])
            for r in trend_rows
        ]

        return PurchaseReportResponse(
            period_from=date_from,
            period_to=date_to,
            total_amount=float(total_amount),
            total_quantity=float(total_quantity),
            purchase_count=purchase_count,
            average_per_purchase=self._safe_divide(total_amount, Decimal(str(purchase_count))),
            by_supplier=by_supplier,
            by_material=by_material,
            daily_trend=daily_trend,
        )

    # ------------------------------------------------------------------
    # Sales Report
    # ------------------------------------------------------------------

    def get_sales_report(
        self,
        db: Session,
        organization_id: UUID,
        date_from: date,
        date_to: date,
        customer_id: Optional[UUID] = None,
        material_id: Optional[UUID] = None,
    ) -> SalesReportResponse:
        dt_from, dt_to = self._date_range(date_from, date_to)

        base_filters = [
            Sale.organization_id == organization_id,
            Sale.status == "liquidated",
            Sale.date >= dt_from,
            Sale.date < dt_to,
        ]
        if customer_id:
            base_filters.append(Sale.customer_id == customer_id)

        line_filters = list(base_filters)
        if material_id:
            line_filters.append(SaleLine.material_id == material_id)

        # Totals
        totals = db.execute(
            select(
                func.coalesce(func.sum(SaleLine.total_price), 0),
                func.coalesce(func.sum(SaleLine.quantity), 0),
                func.count(func.distinct(Sale.id)),
                func.coalesce(func.sum(SaleLine.unit_cost * SaleLine.quantity), 0),
                func.coalesce(
                    func.sum((SaleLine.unit_price - SaleLine.unit_cost) * SaleLine.quantity),
                    0,
                ),
            )
            .select_from(SaleLine)
            .join(Sale, SaleLine.sale_id == Sale.id)
            .where(*line_filters)
        ).one()
        total_revenue = Decimal(str(totals[0]))
        total_quantity = Decimal(str(totals[1]))
        sale_count = totals[2]
        total_cost = Decimal(str(totals[3]))
        total_profit = Decimal(str(totals[4]))

        # By customer
        by_customer_rows = db.execute(
            select(
                Sale.customer_id,
                ThirdParty.name,
                func.coalesce(func.sum(SaleLine.total_price), 0),
                func.coalesce(func.sum(SaleLine.quantity), 0),
                func.count(func.distinct(Sale.id)),
                func.coalesce(
                    func.sum((SaleLine.unit_price - SaleLine.unit_cost) * SaleLine.quantity),
                    0,
                ),
            )
            .select_from(SaleLine)
            .join(Sale, SaleLine.sale_id == Sale.id)
            .join(ThirdParty, Sale.customer_id == ThirdParty.id)
            .where(*line_filters)
            .group_by(Sale.customer_id, ThirdParty.name)
            .order_by(func.sum(SaleLine.total_price).desc())
        ).all()

        by_customer = [
            SaleByCustomer(
                customer_id=r[0], customer_name=r[1],
                total_amount=float(r[2]), total_quantity=float(r[3]),
                sale_count=r[4], total_profit=float(r[5]),
            ) for r in by_customer_rows
        ]

        # By material
        by_material_rows = db.execute(
            select(
                SaleLine.material_id,
                Material.code,
                Material.name,
                func.coalesce(func.sum(SaleLine.total_price), 0),
                func.coalesce(func.sum(SaleLine.quantity), 0),
                func.coalesce(func.sum(SaleLine.unit_cost * SaleLine.quantity), 0),
                func.coalesce(
                    func.sum((SaleLine.unit_price - SaleLine.unit_cost) * SaleLine.quantity),
                    0,
                ),
            )
            .select_from(SaleLine)
            .join(Sale, SaleLine.sale_id == Sale.id)
            .join(Material, SaleLine.material_id == Material.id)
            .where(*line_filters)
            .group_by(SaleLine.material_id, Material.code, Material.name)
            .order_by(func.sum(SaleLine.total_price).desc())
        ).all()

        by_material = [
            SaleByMaterial(
                material_id=r[0], material_code=r[1], material_name=r[2],
                total_amount=float(r[3]), total_quantity=float(r[4]),
                total_cost=float(r[5]), total_profit=float(r[6]),
                margin_percentage=self._safe_pct(Decimal(str(r[6])), Decimal(str(r[3]))),
            ) for r in by_material_rows
        ]

        # Daily trend
        trend_rows = db.execute(
            select(
                cast(Sale.date, Date).label("day"),
                func.coalesce(func.sum(Sale.total_amount), 0),
                func.count(),
            )
            .where(*base_filters)
            .group_by(cast(Sale.date, Date))
            .order_by(cast(Sale.date, Date))
        ).all()

        daily_trend = [
            DailyTrendItem(date=r[0], total_amount=float(r[1]), count=r[2])
            for r in trend_rows
        ]

        return SalesReportResponse(
            period_from=date_from,
            period_to=date_to,
            total_revenue=float(total_revenue),
            total_quantity=float(total_quantity),
            sale_count=sale_count,
            total_cost=float(total_cost),
            total_profit=float(total_profit),
            overall_margin=self._safe_pct(total_profit, total_revenue),
            by_customer=by_customer,
            by_material=by_material,
            daily_trend=daily_trend,
        )

    # ------------------------------------------------------------------
    # Margin Analysis
    # ------------------------------------------------------------------

    def get_margin_analysis(
        self,
        db: Session,
        organization_id: UUID,
        date_from: date,
        date_to: date,
    ) -> MarginAnalysisResponse:
        dt_from, dt_to = self._date_range(date_from, date_to)

        # 1. Sale side (ventas normales solamente)
        sale_rows = db.execute(
            select(
                SaleLine.material_id,
                Material.code,
                Material.name,
                MaterialCategory.name.label("cat_name"),
                func.coalesce(func.sum(SaleLine.quantity), 0),
                func.coalesce(func.sum(SaleLine.total_price), 0),
                func.coalesce(func.sum(SaleLine.unit_cost * SaleLine.quantity), 0),
            )
            .select_from(SaleLine)
            .join(Sale, SaleLine.sale_id == Sale.id)
            .join(Material, SaleLine.material_id == Material.id)
            .outerjoin(MaterialCategory, Material.category_id == MaterialCategory.id)
            .where(
                Sale.organization_id == organization_id,
                Sale.status == "liquidated",
                Sale.double_entry_id.is_(None),
                Sale.date >= dt_from,
                Sale.date < dt_to,
            )
            .group_by(SaleLine.material_id, Material.code, Material.name, MaterialCategory.name)
        ).all()

        # 2. Purchase side (compras normales)
        purchase_rows = db.execute(
            select(
                PurchaseLine.material_id,
                func.coalesce(func.sum(PurchaseLine.quantity), 0),
                func.coalesce(func.sum(PurchaseLine.total_price), 0),
            )
            .select_from(PurchaseLine)
            .join(Purchase, PurchaseLine.purchase_id == Purchase.id)
            .where(
                Purchase.organization_id == organization_id,
                Purchase.status == "liquidated",
                Purchase.double_entry_id.is_(None),
                Purchase.date >= dt_from,
                Purchase.date < dt_to,
            )
            .group_by(PurchaseLine.material_id)
        ).all()
        purchase_map = {r[0]: (Decimal(str(r[1])), Decimal(str(r[2]))) for r in purchase_rows}

        # 3. Double entry side (via DoubleEntryLine)
        de_rows = db.execute(
            select(
                DoubleEntryLine.material_id,
                func.coalesce(func.sum(DoubleEntryLine.quantity), 0),
                func.coalesce(
                    func.sum(
                        (DoubleEntryLine.sale_unit_price - DoubleEntryLine.purchase_unit_price)
                        * DoubleEntryLine.quantity
                    ),
                    0,
                ),
            )
            .select_from(DoubleEntryLine)
            .join(DoubleEntry, DoubleEntryLine.double_entry_id == DoubleEntry.id)
            .where(
                DoubleEntry.organization_id == organization_id,
                DoubleEntry.status == "completed",
                DoubleEntry.date >= date_from,
                DoubleEntry.date <= date_to,
            )
            .group_by(DoubleEntryLine.material_id)
        ).all()
        de_map = {r[0]: (Decimal(str(r[1])), Decimal(str(r[2]))) for r in de_rows}

        # Merge por material_id
        all_material_ids = set()
        for r in sale_rows:
            all_material_ids.add(r[0])
        all_material_ids.update(purchase_map.keys())
        all_material_ids.update(de_map.keys())

        # Material info map para los que no estan en sale_rows
        mat_info = {}
        for r in sale_rows:
            mat_info[r[0]] = (r[1], r[2], r[3])  # code, name, cat_name

        missing_ids = all_material_ids - set(mat_info.keys())
        if missing_ids:
            extra_mats = db.execute(
                select(Material.id, Material.code, Material.name, MaterialCategory.name)
                .outerjoin(MaterialCategory, Material.category_id == MaterialCategory.id)
                .where(Material.id.in_(missing_ids))
            ).all()
            for m in extra_mats:
                mat_info[m[0]] = (m[1], m[2], m[3])

        sale_map = {}
        for r in sale_rows:
            sale_map[r[0]] = (Decimal(str(r[4])), Decimal(str(r[5])), Decimal(str(r[6])))

        total_revenue_all = Decimal("0")
        total_cost_all = Decimal("0")
        materials = []

        for mid in all_material_ids:
            code, name, cat_name = mat_info.get(mid, ("???", "???", None))
            s_qty, s_rev, s_cost = sale_map.get(mid, (Decimal("0"), Decimal("0"), Decimal("0")))
            p_qty, p_amt = purchase_map.get(mid, (Decimal("0"), Decimal("0")))
            d_qty, d_profit = de_map.get(mid, (Decimal("0"), Decimal("0")))

            gross_profit = s_rev - s_cost
            total_revenue_all += s_rev
            total_cost_all += s_cost

            materials.append(MaterialMargin(
                material_id=mid,
                material_code=code,
                material_name=name,
                category_name=cat_name,
                total_purchased_qty=float(p_qty),
                total_purchased_amount=float(p_amt),
                avg_purchase_price=self._safe_divide(p_amt, p_qty),
                total_sold_qty=float(s_qty),
                total_sold_revenue=float(s_rev),
                total_sold_cost=float(s_cost),
                avg_sale_price=self._safe_divide(s_rev, s_qty),
                gross_profit=float(gross_profit),
                margin_percentage=self._safe_pct(gross_profit, s_rev),
                double_entry_qty=float(d_qty),
                double_entry_profit=float(d_profit),
            ))

        # Ordenar por profit desc
        materials.sort(key=lambda m: m.gross_profit, reverse=True)

        overall_profit = total_revenue_all - total_cost_all
        overall_margin = self._safe_pct(overall_profit, total_revenue_all)

        return MarginAnalysisResponse(
            period_from=date_from,
            period_to=date_to,
            overall_margin=overall_margin,
            materials=materials,
        )

    # ------------------------------------------------------------------
    # Third Party Balances
    # ------------------------------------------------------------------

    def get_third_party_balances(
        self,
        db: Session,
        organization_id: UUID,
        type_filter: Optional[str] = None,
    ) -> ThirdPartyBalancesResponse:
        suppliers = []
        customers = []
        total_payable = Decimal("0")
        total_receivable = Decimal("0")
        total_advances_paid = Decimal("0")
        total_advances_received = Decimal("0")

        if type_filter != "customers":
            rows = db.execute(
                select(ThirdParty.id, ThirdParty.name, ThirdParty.current_balance)
                .where(
                    ThirdParty.organization_id == organization_id,
                    ThirdParty.is_supplier == True,
                    ThirdParty.current_balance != 0,
                )
                .order_by(ThirdParty.current_balance.asc())
            ).all()
            for r in rows:
                suppliers.append(SupplierBalance(id=r[0], name=r[1], balance=float(r[2])))
                if r[2] < 0:
                    total_payable += abs(Decimal(str(r[2])))
                elif r[2] > 0:
                    # Proveedor con balance positivo = nos debe (anticipo)
                    total_advances_paid += Decimal(str(r[2]))

        if type_filter != "suppliers":
            rows = db.execute(
                select(ThirdParty.id, ThirdParty.name, ThirdParty.current_balance)
                .where(
                    ThirdParty.organization_id == organization_id,
                    ThirdParty.is_customer == True,
                    ThirdParty.current_balance != 0,
                )
                .order_by(ThirdParty.current_balance.desc())
            ).all()
            for r in rows:
                customers.append(CustomerBalance(id=r[0], name=r[1], balance=float(r[2])))
                if r[2] > 0:
                    total_receivable += Decimal(str(r[2]))
                elif r[2] < 0:
                    # Cliente con balance negativo = le debemos (anticipo recibido)
                    total_advances_received += abs(Decimal(str(r[2])))

        return ThirdPartyBalancesResponse(
            total_payable=float(total_payable),
            total_receivable=float(total_receivable),
            net_position=float(total_receivable - total_payable),
            total_advances_paid=float(total_advances_paid),
            total_advances_received=float(total_advances_received),
            suppliers=suppliers,
            customers=customers,
        )

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def get_dashboard(
        self,
        db: Session,
        organization_id: UUID,
        date_from: date,
        date_to: date,
    ) -> DashboardResponse:
        dt_from, dt_to = self._date_range(date_from, date_to)

        # Periodo anterior
        period_days = (date_to - date_from).days
        prev_to = date_from - timedelta(days=1)
        prev_from = prev_to - timedelta(days=period_days)
        prev_dt_from, prev_dt_to = self._date_range(prev_from, prev_to)

        # --- Metricas por periodo (actual y anterior) ---
        def _period_sales(dt_f, dt_t):
            return Decimal(str(
                db.scalar(
                    select(func.coalesce(func.sum(Sale.total_amount), 0))
                    .where(
                        Sale.organization_id == organization_id,
                        Sale.status == "liquidated",
                        Sale.date >= dt_f,
                        Sale.date < dt_t,
                    )
                )
            ))

        def _period_purchases(dt_f, dt_t):
            return Decimal(str(
                db.scalar(
                    select(func.coalesce(func.sum(Purchase.total_amount), 0))
                    .where(
                        Purchase.organization_id == organization_id,
                        Purchase.status == "liquidated",
                        Purchase.date >= dt_f,
                        Purchase.date < dt_t,
                    )
                )
            ))

        def _period_gross_profit(dt_f, dt_t, d_from: date, d_to: date):
            """Calcula profit de ventas normales + DE en periodo."""
            sale_profit = Decimal(str(
                db.scalar(
                    select(func.coalesce(
                        func.sum((SaleLine.unit_price - SaleLine.unit_cost) * SaleLine.quantity),
                        0,
                    ))
                    .select_from(SaleLine)
                    .join(Sale, SaleLine.sale_id == Sale.id)
                    .where(
                        Sale.organization_id == organization_id,
                        Sale.status == "liquidated",
                        Sale.double_entry_id.is_(None),
                        Sale.date >= dt_f,
                        Sale.date < dt_t,
                    )
                )
            ))
            de_profit = Decimal(str(
                db.scalar(
                    select(func.coalesce(
                        func.sum(
                            (DoubleEntryLine.sale_unit_price - DoubleEntryLine.purchase_unit_price)
                            * DoubleEntryLine.quantity
                        ),
                        0,
                    ))
                    .select_from(DoubleEntryLine)
                    .join(DoubleEntry, DoubleEntryLine.double_entry_id == DoubleEntry.id)
                    .where(
                        DoubleEntry.organization_id == organization_id,
                        DoubleEntry.status == "completed",
                        DoubleEntry.date >= d_from,
                        DoubleEntry.date <= d_to,
                    )
                )
            ))
            return sale_profit + de_profit

        cur_sales = _period_sales(dt_from, dt_to)
        prev_sales = _period_sales(prev_dt_from, prev_dt_to)
        cur_purchases = _period_purchases(dt_from, dt_to)
        prev_purchases = _period_purchases(prev_dt_from, prev_dt_to)
        cur_profit = _period_gross_profit(dt_from, dt_to, date_from, date_to)
        prev_profit = _period_gross_profit(prev_dt_from, prev_dt_to, prev_from, prev_to)

        # Point-in-time metrics (sin comparacion temporal)
        cash_balance = Decimal(str(
            db.scalar(
                select(func.coalesce(func.sum(MoneyAccount.current_balance), 0))
                .where(
                    MoneyAccount.organization_id == organization_id,
                    MoneyAccount.is_active == True,
                )
            )
        ))

        receivables = Decimal(str(
            db.scalar(
                select(func.coalesce(func.sum(ThirdParty.current_balance), 0))
                .where(
                    ThirdParty.organization_id == organization_id,
                    ThirdParty.is_customer == True,
                    ThirdParty.current_balance > 0,
                )
            )
        ))

        payables = Decimal(str(
            db.scalar(
                select(func.coalesce(func.sum(func.abs(ThirdParty.current_balance)), 0))
                .where(
                    ThirdParty.organization_id == organization_id,
                    ThirdParty.is_supplier == True,
                    ThirdParty.current_balance < 0,
                )
            )
        ))

        metrics = DashboardMetrics(
            total_sales=MetricCard(
                current_value=float(cur_sales),
                previous_value=float(prev_sales),
                change_percentage=self._change_pct(cur_sales, prev_sales),
            ),
            total_purchases=MetricCard(
                current_value=float(cur_purchases),
                previous_value=float(prev_purchases),
                change_percentage=self._change_pct(cur_purchases, prev_purchases),
            ),
            gross_profit=MetricCard(
                current_value=float(cur_profit),
                previous_value=float(prev_profit),
                change_percentage=self._change_pct(cur_profit, prev_profit),
            ),
            cash_balance=MetricCard(
                current_value=float(cash_balance),
                previous_value=float(cash_balance),
                change_percentage=None,
            ),
            pending_receivables=MetricCard(
                current_value=float(receivables),
                previous_value=float(receivables),
                change_percentage=None,
            ),
            pending_payables=MetricCard(
                current_value=float(payables),
                previous_value=float(payables),
                change_percentage=None,
            ),
        )

        # --- Top 5 listas ---

        top_materials = db.execute(
            select(
                SaleLine.material_id,
                Material.name,
                func.coalesce(
                    func.sum((SaleLine.unit_price - SaleLine.unit_cost) * SaleLine.quantity), 0
                ).label("profit"),
                func.coalesce(func.sum(SaleLine.total_price), 0).label("revenue"),
            )
            .select_from(SaleLine)
            .join(Sale, SaleLine.sale_id == Sale.id)
            .join(Material, SaleLine.material_id == Material.id)
            .where(
                Sale.organization_id == organization_id,
                Sale.status == "liquidated",
                Sale.date >= dt_from,
                Sale.date < dt_to,
            )
            .group_by(SaleLine.material_id, Material.name)
            .order_by(func.sum((SaleLine.unit_price - SaleLine.unit_cost) * SaleLine.quantity).desc())
            .limit(5)
        ).all()

        top_materials_list = [
            MaterialProfitSummary(
                material_id=r[0], material_name=r[1],
                total_profit=float(r[2]),
                margin_percentage=self._safe_pct(Decimal(str(r[2])), Decimal(str(r[3]))),
            ) for r in top_materials
        ]

        top_suppliers = db.execute(
            select(
                Purchase.supplier_id,
                ThirdParty.name,
                func.coalesce(func.sum(Purchase.total_amount), 0),
                func.coalesce(func.sum(PurchaseLine.quantity), 0),
            )
            .select_from(Purchase)
            .join(ThirdParty, Purchase.supplier_id == ThirdParty.id)
            .join(PurchaseLine, PurchaseLine.purchase_id == Purchase.id)
            .where(
                Purchase.organization_id == organization_id,
                Purchase.status == "liquidated",
                Purchase.date >= dt_from,
                Purchase.date < dt_to,
            )
            .group_by(Purchase.supplier_id, ThirdParty.name)
            .order_by(func.sum(Purchase.total_amount).desc())
            .limit(5)
        ).all()

        top_suppliers_list = [
            SupplierVolumeSummary(
                supplier_id=r[0], supplier_name=r[1],
                total_amount=float(r[2]), total_quantity=float(r[3]),
            ) for r in top_suppliers
        ]

        top_customers = db.execute(
            select(
                Sale.customer_id,
                ThirdParty.name,
                func.coalesce(func.sum(Sale.total_amount), 0),
                func.coalesce(
                    func.sum((SaleLine.unit_price - SaleLine.unit_cost) * SaleLine.quantity), 0
                ),
            )
            .select_from(Sale)
            .join(ThirdParty, Sale.customer_id == ThirdParty.id)
            .join(SaleLine, SaleLine.sale_id == Sale.id)
            .where(
                Sale.organization_id == organization_id,
                Sale.status == "liquidated",
                Sale.date >= dt_from,
                Sale.date < dt_to,
            )
            .group_by(Sale.customer_id, ThirdParty.name)
            .order_by(func.sum(Sale.total_amount).desc())
            .limit(5)
        ).all()

        top_customers_list = [
            CustomerRevenueSummary(
                customer_id=r[0], customer_name=r[1],
                total_amount=float(r[2]), total_profit=float(r[3]),
            ) for r in top_customers
        ]

        # --- Alertas ---
        alerts: list[DashboardAlert] = []

        pending_purchases_count = db.scalar(
            select(func.count())
            .where(
                Purchase.organization_id == organization_id,
                Purchase.status == "registered",
            )
        )
        if pending_purchases_count > 0:
            alerts.append(DashboardAlert(
                alert_type="pending_purchases",
                severity="info",
                message=f"{pending_purchases_count} compras pendientes de liquidar",
                count=pending_purchases_count,
            ))

        pending_sales_count = db.scalar(
            select(func.count())
            .where(
                Sale.organization_id == organization_id,
                Sale.status == "registered",
            )
        )
        if pending_sales_count > 0:
            alerts.append(DashboardAlert(
                alert_type="pending_sales",
                severity="info",
                message=f"{pending_sales_count} ventas pendientes de cobrar",
                count=pending_sales_count,
            ))

        negative_stock_count = db.scalar(
            select(func.count())
            .where(
                Material.organization_id == organization_id,
                Material.is_active == True,
                Material.current_stock_liquidated < 0,
            )
        )
        if negative_stock_count > 0:
            alerts.append(DashboardAlert(
                alert_type="negative_stock",
                severity="warning",
                message=f"{negative_stock_count} materiales con stock negativo",
                count=negative_stock_count,
            ))

        if receivables > 50_000_000:
            alerts.append(DashboardAlert(
                alert_type="high_receivable",
                severity="warning",
                message=f"Cuentas por cobrar: ${receivables:,.0f}",
                count=None,
            ))

        return DashboardResponse(
            as_of=datetime.now(tz=timezone.utc),
            period_from=date_from,
            period_to=date_to,
            metrics=metrics,
            top_materials_by_profit=top_materials_list,
            top_suppliers_by_volume=top_suppliers_list,
            top_customers_by_revenue=top_customers_list,
            alerts=alerts,
        )


    # ------------------------------------------------------------------
    # Treasury Dashboard
    # ------------------------------------------------------------------

    def get_treasury_dashboard(
        self,
        db: Session,
        organization_id: UUID,
    ) -> TreasuryDashboardResponse:
        """Dashboard financiero de tesoreria con datos actuales y MTD."""
        from sqlalchemy.orm import joinedload

        # 1. Cuentas agrupadas por tipo
        accounts_query = (
            select(MoneyAccount)
            .where(
                MoneyAccount.organization_id == organization_id,
                MoneyAccount.is_active == True,
            )
            .order_by(MoneyAccount.name)
        )
        accounts = list(db.scalars(accounts_query).all())

        cash_accounts = []
        bank_accounts = []
        digital_accounts = []
        for a in accounts:
            summary = AccountSummary(
                id=a.id, name=a.name,
                account_type=a.account_type,
                current_balance=float(a.current_balance),
            )
            if a.account_type == "cash":
                cash_accounts.append(summary)
            elif a.account_type == "bank":
                bank_accounts.append(summary)
            else:
                digital_accounts.append(summary)

        total_cash = sum(a.current_balance for a in cash_accounts)
        total_bank = sum(a.current_balance for a in bank_accounts)
        total_digital = sum(a.current_balance for a in digital_accounts)

        # 2. CxC / CxP (reutilizar logica existente)
        total_receivable = float(db.scalar(
            select(func.coalesce(func.sum(ThirdParty.current_balance), 0))
            .where(
                ThirdParty.organization_id == organization_id,
                ThirdParty.is_customer == True,
                ThirdParty.current_balance > 0,
            )
        ))
        total_payable = float(db.scalar(
            select(func.coalesce(func.sum(func.abs(ThirdParty.current_balance)), 0))
            .where(
                ThirdParty.organization_id == organization_id,
                ThirdParty.is_supplier == True,
                ThirdParty.current_balance < 0,
            )
        ))

        # 3. Provisiones
        prov_rows = db.execute(
            select(ThirdParty.id, ThirdParty.name, ThirdParty.provision_type, ThirdParty.current_balance)
            .where(
                ThirdParty.organization_id == organization_id,
                ThirdParty.is_provision == True,
                ThirdParty.is_active == True,
            )
            .order_by(ThirdParty.name)
        ).all()
        provisions = []
        total_provision_available = Decimal("0")
        for r in prov_rows:
            bal = Decimal(str(r[3]))
            available = abs(bal) if bal < 0 else Decimal("0")
            provisions.append(ProvisionSummary(
                id=r[0], name=r[1], provision_type=r[2],
                current_balance=float(bal),
                available_funds=float(available),
            ))
            total_provision_available += available

        # 4. MTD (mes en curso)
        now = datetime.now(tz=timezone.utc)
        first_of_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

        mtd_rows = db.execute(
            select(
                MoneyMovement.movement_type,
                func.coalesce(func.sum(MoneyMovement.amount), 0),
            )
            .where(
                MoneyMovement.organization_id == organization_id,
                MoneyMovement.status == "confirmed",
                MoneyMovement.date >= first_of_month,
            )
            .group_by(MoneyMovement.movement_type)
        ).all()

        mtd_income = Decimal("0")
        mtd_expense = Decimal("0")
        for mt, total in mtd_rows:
            if mt in INFLOW_TYPES:
                mtd_income += Decimal(str(total))
            elif mt in OUTFLOW_TYPES:
                mtd_expense += Decimal(str(total))

        # 5. Ultimos 10 movimientos
        recent_query = (
            select(MoneyMovement)
            .where(
                MoneyMovement.organization_id == organization_id,
                MoneyMovement.status == "confirmed",
            )
            .options(
                joinedload(MoneyMovement.account),
                joinedload(MoneyMovement.third_party),
            )
            .order_by(MoneyMovement.date.desc(), MoneyMovement.movement_number.desc())
            .limit(10)
        )
        recent = list(db.scalars(recent_query).unique().all())
        recent_items = [
            RecentMovementItem(
                id=m.id,
                movement_number=m.movement_number,
                date=m.date,
                movement_type=m.movement_type,
                amount=float(m.amount),
                description=m.description,
                account_name=m.account.name if m.account else None,
                third_party_name=m.third_party.name if m.third_party else None,
            )
            for m in recent
        ]

        return TreasuryDashboardResponse(
            cash_accounts=cash_accounts,
            bank_accounts=bank_accounts,
            digital_accounts=digital_accounts,
            total_cash=total_cash,
            total_bank=total_bank,
            total_digital=total_digital,
            total_all_accounts=total_cash + total_bank + total_digital,
            total_receivable=total_receivable,
            total_payable=total_payable,
            net_position=total_receivable - total_payable,
            provisions=provisions,
            total_provision_available=float(total_provision_available),
            mtd_income=float(mtd_income),
            mtd_expense=float(mtd_expense),
            recent_movements=recent_items,
        )


    # ------------------------------------------------------------------
    # Audit Balances (Auditoria de saldos)
    # ------------------------------------------------------------------

    def audit_balances(
        self,
        db: Session,
        organization_id: UUID,
    ) -> AuditBalancesResponse:
        """
        Recalcula saldos desde cero y compara con current_balance almacenado.

        Para cuentas: suma movimientos confirmados usando ACCOUNT_BALANCE_DIRECTION.
        Para terceros: suma compras, ventas, comisiones, doble partida y money_movements.
        """
        # =====================================================================
        # 1. Auditoria de cuentas de dinero
        # =====================================================================
        accounts = list(db.scalars(
            select(MoneyAccount)
            .where(
                MoneyAccount.organization_id == organization_id,
                MoneyAccount.is_active == True,
            )
            .order_by(MoneyAccount.name)
        ).all())

        # Sumar movimientos confirmados agrupados por (account_id, movement_type)
        mm_account_rows = db.execute(
            select(
                MoneyMovement.account_id,
                MoneyMovement.movement_type,
                func.coalesce(func.sum(MoneyMovement.amount), 0),
            )
            .where(
                MoneyMovement.organization_id == organization_id,
                MoneyMovement.status == "confirmed",
                MoneyMovement.is_active == True,
                MoneyMovement.account_id.isnot(None),
            )
            .group_by(MoneyMovement.account_id, MoneyMovement.movement_type)
        ).all()

        # Construir dict {account_id: calculated_balance}
        account_calc: dict[UUID, Decimal] = {}
        for acc_id, mv_type, total in mm_account_rows:
            direction = ACCOUNT_BALANCE_DIRECTION.get(mv_type, 0)
            account_calc[acc_id] = account_calc.get(acc_id, Decimal("0")) + Decimal(str(total)) * direction

        account_items: list[AccountAuditItem] = []
        accounts_ok = 0
        accounts_mismatch = 0

        for acc in accounts:
            stored = Decimal(str(acc.current_balance))
            initial = Decimal(str(acc.initial_balance))
            calculated = initial + account_calc.get(acc.id, Decimal("0"))
            diff = stored - calculated
            ok = abs(diff) < Decimal("0.01")
            if ok:
                accounts_ok += 1
            else:
                accounts_mismatch += 1

            account_items.append(AccountAuditItem(
                id=acc.id,
                name=acc.name,
                account_type=acc.account_type,
                stored_balance=float(stored),
                calculated_balance=float(calculated),
                difference=float(diff),
                status="ok" if ok else "mismatch",
            ))

        # =====================================================================
        # 2. Auditoria de terceros
        # =====================================================================
        third_parties = list(db.scalars(
            select(ThirdParty)
            .where(
                ThirdParty.organization_id == organization_id,
                ThirdParty.is_active == True,
            )
            .order_by(ThirdParty.name)
        ).all())

        # Dict acumulador {third_party_id: calculated_balance}
        tp_calc: dict[UUID, Decimal] = {}

        def _add(tp_id: UUID, amount: Decimal) -> None:
            tp_calc[tp_id] = tp_calc.get(tp_id, Decimal("0")) + amount

        # 2a. Compras liquidadas: supplier.balance -= total_amount
        purchase_rows = db.execute(
            select(
                Purchase.supplier_id,
                func.coalesce(func.sum(Purchase.total_amount), 0),
            )
            .where(
                Purchase.organization_id == organization_id,
                Purchase.status == "liquidated",
            )
            .group_by(Purchase.supplier_id)
        ).all()
        for tp_id, total in purchase_rows:
            _add(tp_id, -Decimal(str(total)))

        # 2b. Compras canceladas post-liquidacion: reversal (+total_amount)
        purchase_cancel_rows = db.execute(
            select(
                Purchase.supplier_id,
                func.coalesce(func.sum(Purchase.total_amount), 0),
            )
            .where(
                Purchase.organization_id == organization_id,
                Purchase.status == "cancelled",
                Purchase.liquidated_at.isnot(None),
            )
            .group_by(Purchase.supplier_id)
        ).all()
        for tp_id, total in purchase_cancel_rows:
            _add(tp_id, Decimal(str(total)))

        # 2c. Ventas liquidadas: customer.balance += total_amount
        sale_rows = db.execute(
            select(
                Sale.customer_id,
                func.coalesce(func.sum(Sale.total_amount), 0),
            )
            .where(
                Sale.organization_id == organization_id,
                Sale.status == "liquidated",
            )
            .group_by(Sale.customer_id)
        ).all()
        for tp_id, total in sale_rows:
            _add(tp_id, Decimal(str(total)))

        # 2d. Ventas canceladas post-liquidacion: reversal (-total_amount)
        sale_cancel_rows = db.execute(
            select(
                Sale.customer_id,
                func.coalesce(func.sum(Sale.total_amount), 0),
            )
            .where(
                Sale.organization_id == organization_id,
                Sale.status == "cancelled",
                Sale.liquidated_at.isnot(None),
            )
            .group_by(Sale.customer_id)
        ).all()
        for tp_id, total in sale_cancel_rows:
            _add(tp_id, -Decimal(str(total)))

        # 2e. Comisiones de ventas liquidadas: recipient.balance += commission_amount
        comm_rows = db.execute(
            select(
                SaleCommission.third_party_id,
                func.coalesce(func.sum(SaleCommission.commission_amount), 0),
            )
            .select_from(SaleCommission)
            .join(Sale, SaleCommission.sale_id == Sale.id)
            .where(
                Sale.organization_id == organization_id,
                Sale.status == "liquidated",
            )
            .group_by(SaleCommission.third_party_id)
        ).all()
        for tp_id, total in comm_rows:
            _add(tp_id, Decimal(str(total)))

        # 2f. Comisiones de ventas canceladas post-liquidacion: reversal
        comm_cancel_rows = db.execute(
            select(
                SaleCommission.third_party_id,
                func.coalesce(func.sum(SaleCommission.commission_amount), 0),
            )
            .select_from(SaleCommission)
            .join(Sale, SaleCommission.sale_id == Sale.id)
            .where(
                Sale.organization_id == organization_id,
                Sale.status == "cancelled",
                Sale.liquidated_at.isnot(None),
            )
            .group_by(SaleCommission.third_party_id)
        ).all()
        for tp_id, total in comm_cancel_rows:
            _add(tp_id, -Decimal(str(total)))

        # 2g. MoneyMovements confirmados con third_party_id
        mm_tp_rows = db.execute(
            select(
                MoneyMovement.third_party_id,
                MoneyMovement.movement_type,
                func.coalesce(func.sum(MoneyMovement.amount), 0),
            )
            .where(
                MoneyMovement.organization_id == organization_id,
                MoneyMovement.status == "confirmed",
                MoneyMovement.is_active == True,
                MoneyMovement.third_party_id.isnot(None),
            )
            .group_by(MoneyMovement.third_party_id, MoneyMovement.movement_type)
        ).all()
        for tp_id, mv_type, total in mm_tp_rows:
            direction = THIRD_PARTY_BALANCE_DIRECTION.get(mv_type, 0)
            if direction != 0:
                _add(tp_id, Decimal(str(total)) * direction)

        # Construir items de auditoria de terceros
        tp_items: list[ThirdPartyAuditItem] = []
        tp_ok = 0
        tp_mismatch = 0

        for tp in third_parties:
            stored = Decimal(str(tp.current_balance))
            initial = Decimal(str(tp.initial_balance))
            calculated = initial + tp_calc.get(tp.id, Decimal("0"))
            diff = stored - calculated
            ok = abs(diff) < Decimal("0.01")
            if ok:
                tp_ok += 1
            else:
                tp_mismatch += 1

            roles = []
            if tp.is_supplier:
                roles.append("supplier")
            if tp.is_customer:
                roles.append("customer")
            if tp.is_investor:
                roles.append("investor")
            if tp.is_provision:
                roles.append("provision")

            tp_items.append(ThirdPartyAuditItem(
                id=tp.id,
                name=tp.name,
                roles=roles,
                stored_balance=float(stored),
                calculated_balance=float(calculated),
                difference=float(diff),
                status="ok" if ok else "mismatch",
            ))

        return AuditBalancesResponse(
            accounts=account_items,
            third_parties=tp_items,
            summary=AuditSummary(
                total_accounts=len(account_items),
                accounts_ok=accounts_ok,
                accounts_mismatch=accounts_mismatch,
                total_third_parties=len(tp_items),
                third_parties_ok=tp_ok,
                third_parties_mismatch=tp_mismatch,
            ),
        )


# Instancia singleton
report_service = ReportService()
