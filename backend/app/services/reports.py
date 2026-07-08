"""
Servicio de reportes y dashboard.

Clase standalone con queries de agregacion read-only.
Todos los calculos internos usan Decimal para precision.
"""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, case, cast, Date, exists, or_, and_
from sqlalchemy.orm import Session, joinedload

from app.models.double_entry import DoubleEntry, DoubleEntryLine
from app.models.expense_category import ExpenseCategory
from app.models.material import Material, MaterialCategory
from app.models.material_cost_history import MaterialCostHistory
from app.models.money_account import MoneyAccount
from app.models.money_movement import MoneyMovement
from app.models.purchase import Purchase, PurchaseLine
from app.models.purchase import PurchaseCommission
from app.models.sale import Sale, SaleLine
from app.models.third_party import ThirdParty
from app.models.third_party_category import ThirdPartyCategory, ThirdPartyCategoryAssignment
from app.models.fixed_asset import FixedAsset, AssetDepreciation
from app.models.inventory_movement import InventoryMovement
from app.models.business_unit import BusinessUnit

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
    DoubleEntryProfitability,
    ExpenseCategoryBreakdown,
    MarginAnalysisResponse,
    MaterialMargin,
    MaterialProfitSummary,
    MetricCard,
    ProfitAndLossMonthlyPeriod,
    ProfitAndLossMonthlyResponse,
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
    BalanceDetailedGroup,
    BalanceDetailedItem,
    BalanceDetailedSection,
    BalanceDetailedVerification,
    BalanceDetailedResponse,
    BusinessUnitProfitability,
    ExpenseByCategoryItem,
    ProfitabilityByBUResponse,
    BusinessUnitOverhead,
    MaterialRealCost,
    RealCostByMaterialResponse,
    ExpenseGroupNode,
    ExpensesReportResponse,
    ExpenseDetailItem,
    ExpenseDetailResponse,
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
    "deferred_funding": -1,
    "payment_to_generic": -1,
    "collection_from_generic": 1,
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
    "asset_purchase": -1,            # Compra activo a credito: le debemos (balance-=)
    "payment_to_generic": 1,         # Pagamos a generico: su balance sube
    "collection_from_generic": -1,   # Cobramos a generico: su balance baja
    "tp_transfer_out": -1,           # Transferencia entre terceros: source paga
    "tp_transfer_in": 1,             # Transferencia entre terceros: dest recibe
    "tp_adjustment_credit": 1,       # Ajuste credito: saldo sube
    "tp_adjustment_debit": -1,       # Ajuste debito: saldo baja
}

# Tipos de money_movement que representan inflows a cuentas
INFLOW_TYPES = frozenset([
    "collection_from_client",
    "service_income",
    "capital_injection",
    "transfer_in",
    "advance_collection",
    "collection_from_generic",
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
    "payment_to_generic", # Pago a tercero generico: sale dinero de cuenta
])
# Nota: provision_expense NO va aqui — no afecta cuentas de dinero


class ReportService:
    """Queries de agregacion read-only para reportes y dashboard."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tp_has_behavior(*behavior_types: str):
        """EXISTS subquery: tercero tiene alguno de los behavior_types."""
        return exists(
            select(ThirdPartyCategoryAssignment.id)
            .join(ThirdPartyCategory, ThirdPartyCategoryAssignment.category_id == ThirdPartyCategory.id)
            .where(
                ThirdPartyCategoryAssignment.third_party_id == ThirdParty.id,
                ThirdPartyCategory.behavior_type.in_(behavior_types),
            )
        )

    @staticmethod
    def _load_tp_behavior_map(db: Session, organization_id: UUID) -> tuple[dict, dict, dict]:
        """Pre-carga behavior_types, category_names y categoria por behavior para terceros.

        Returns:
            (tp_behaviors, tp_cat_names, tp_cat_by_behavior)
            - tp_behaviors: dict[UUID, set[str]] — behavior_types del tercero
            - tp_cat_names: dict[UUID, set[str]] — nombres de categorias
            - tp_cat_by_behavior: dict[UUID, dict[str, str]] — {tp_id: {behavior_type: display_name}}
        """
        from sqlalchemy.orm import aliased
        ParentCat = aliased(ThirdPartyCategory)
        rows = db.execute(
            select(
                ThirdPartyCategoryAssignment.third_party_id,
                ThirdPartyCategory.behavior_type,
                ThirdPartyCategory.name,
                ParentCat.name.label("parent_name"),
            )
            .join(ThirdPartyCategory, ThirdPartyCategoryAssignment.category_id == ThirdPartyCategory.id)
            .outerjoin(ParentCat, ThirdPartyCategory.parent_id == ParentCat.id)
            .where(ThirdPartyCategory.organization_id == organization_id)
        ).all()
        tp_behaviors: dict[UUID, set[str]] = {}
        tp_cat_names: dict[UUID, set[str]] = {}
        tp_cat_by_behavior: dict[UUID, dict[str, str]] = {}
        for tp_id, bt, name, parent_name in rows:
            tp_behaviors.setdefault(tp_id, set()).add(bt)
            tp_cat_names.setdefault(tp_id, set()).add(name)
            display = f"{parent_name} > {name}" if parent_name else name
            # Solo guardar la primera categoria por behavior_type (evitar duplicados M:N)
            tp_cat_by_behavior.setdefault(tp_id, {}).setdefault(bt, display)
        return tp_behaviors, tp_cat_names, tp_cat_by_behavior

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

    def _calculate_profit(
        self,
        db: Session,
        organization_id: UUID,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        cutoff_dt: Optional[datetime] = None,
    ) -> dict:
        """Calcula componentes de P&L. Sin fechas = acumulado historico.

        cutoff_dt: si se pasa, usa _active_at_cutoff para incluir operaciones
        canceladas/anuladas despues del corte (snapshot historico).

        Retorna dict con: sales_revenue, sales_count, cogs, de_profit, de_count,
        transformation_profit, transformation_count, service_income,
        operating_expenses, commissions_paid, expenses_by_cat,
        gross_profit_sales, total_gross_profit, net_profit.
        """
        has_dates = date_from is not None and date_to is not None
        if has_dates:
            dt_from, dt_to = self._date_range(date_from, date_to)

        # 1. Sales Revenue (ventas normales, excluye DE)
        sale_filters = [
            Sale.organization_id == organization_id,
            self._active_at_cutoff(Sale.status),
            Sale.double_entry_id.is_(None),
        ]
        if has_dates:
            sale_filters += [Sale.liquidated_at >= dt_from, Sale.liquidated_at < dt_to]

        row = db.execute(
            select(
                func.coalesce(func.sum(Sale.total_amount), 0),
                func.count(),
            ).where(*sale_filters)
        ).one()
        sales_revenue = Decimal(str(row[0]))
        sales_count = row[1]

        # 2. COGS (metodo directo)
        cogs_filters = [
            Sale.organization_id == organization_id,
            self._active_at_cutoff(Sale.status),
            Sale.double_entry_id.is_(None),
        ]
        if has_dates:
            cogs_filters += [Sale.liquidated_at >= dt_from, Sale.liquidated_at < dt_to]

        cogs_val = db.scalar(
            select(
                func.coalesce(func.sum(SaleLine.unit_cost * SaleLine.quantity), 0)
            ).select_from(SaleLine)
            .join(Sale, SaleLine.sale_id == Sale.id)
            .where(*cogs_filters)
        )
        cogs = Decimal(str(cogs_val))

        # 3. Double Entry Profit (via DoubleEntryLine)
        de_filters = [
            DoubleEntry.organization_id == organization_id,
            self._active_at_cutoff(DoubleEntry.status),
        ]
        if has_dates:
            de_filters += [DoubleEntry.liquidated_at >= dt_from, DoubleEntry.liquidated_at < dt_to]

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
            .where(*de_filters)
        ).one()
        de_profit = Decimal(str(de_row[0]))
        de_count = de_row[1]

        # 3.5 Transformation profit (ganancia/perdida por valorizacion)
        from app.models.material_transformation import MaterialTransformation

        trans_filters = [
            MaterialTransformation.organization_id == organization_id,
            self._active_at_cutoff(MaterialTransformation.status, "confirmed"),
            MaterialTransformation.value_difference.isnot(None),
        ]
        if has_dates:
            trans_filters += [MaterialTransformation.date >= dt_from, MaterialTransformation.date < dt_to]

        trans_row = db.execute(
            select(
                func.coalesce(func.sum(MaterialTransformation.value_difference), 0),
                func.count(),
            ).where(*trans_filters)
        ).one()
        transformation_profit = Decimal(str(trans_row[0]))
        transformation_count = trans_row[1]

        # 3.6 Perdida por merma en transformaciones
        waste_filters = [
            MaterialTransformation.organization_id == organization_id,
            self._active_at_cutoff(MaterialTransformation.status, "confirmed"),
            MaterialTransformation.waste_value > 0,
        ]
        if has_dates:
            waste_filters += [MaterialTransformation.date >= dt_from, MaterialTransformation.date < dt_to]

        waste_loss = Decimal(str(
            db.scalar(
                select(func.coalesce(func.sum(MaterialTransformation.waste_value), 0))
                .where(*waste_filters)
            )
        ))

        # 3.7 Ganancia/perdida por ajustes de inventario
        from app.models.inventory_adjustment import InventoryAdjustment

        adj_filters = [
            InventoryAdjustment.organization_id == organization_id,
            self._active_at_cutoff(InventoryAdjustment.status, "confirmed"),
            # Excluir seeds de migracion: estos ajustes representan inventario inicial
            # absorbido por el patrimonio de los socios (ya reflejado en sus saldos),
            # no una ganancia operativa. El script de migracion usa el prefix
            # "Carga inicial migracion" en el reason para marcarlos.
            ~func.coalesce(InventoryAdjustment.reason, "").ilike("Carga inicial migracion%"),
        ]
        if has_dates:
            adj_filters += [InventoryAdjustment.date >= dt_from, InventoryAdjustment.date < dt_to]

        # quantity > 0 = ganancia (increase/recount+), < 0 = perdida (decrease/recount-/zero_out)
        adjustment_net = Decimal(str(
            db.scalar(
                select(func.coalesce(
                    func.sum(
                        case(
                            (InventoryAdjustment.quantity > 0, InventoryAdjustment.total_value),
                            else_=-InventoryAdjustment.total_value,
                        )
                    ), 0
                )).where(*adj_filters)
            )
        ))

        # 4. Ajustes de terceros (perdida/ganancia)
        tp_adj_filters = [
            MoneyMovement.organization_id == organization_id,
            self._active_at_cutoff(MoneyMovement.status, "confirmed"),
            MoneyMovement.movement_type.in_(["tp_adjustment_credit", "tp_adjustment_debit"]),
        ]
        if has_dates:
            tp_adj_filters += [MoneyMovement.date >= dt_from, MoneyMovement.date < dt_to]

        tp_adj_rows = db.execute(
            select(
                MoneyMovement.adjustment_class,
                func.coalesce(func.sum(MoneyMovement.amount), 0),
            ).where(*tp_adj_filters)
            .group_by(MoneyMovement.adjustment_class)
        ).all()

        tp_adj_loss = Decimal("0")
        tp_adj_gain = Decimal("0")
        for adj_class, total in tp_adj_rows:
            if adj_class == "loss":
                tp_adj_loss += Decimal(str(total))
            elif adj_class == "gain":
                tp_adj_gain += Decimal(str(total))

        # 5. Service income + expenses by category (sin commission_accrual — se calcula aparte abajo)
        mm_filters = [
            MoneyMovement.organization_id == organization_id,
            self._active_at_cutoff(MoneyMovement.status, "confirmed"),
            MoneyMovement.movement_type.in_(["expense", "provision_expense", "expense_accrual", "deferred_expense", "depreciation_expense", "service_income"]),
        ]
        if has_dates:
            mm_filters += [MoneyMovement.date >= dt_from, MoneyMovement.date < dt_to]

        mm_rows = db.execute(
            select(
                MoneyMovement.movement_type,
                ExpenseCategory.id,
                ExpenseCategory.name,
                ExpenseCategory.is_direct_expense,
                func.coalesce(func.sum(MoneyMovement.amount), 0),
            )
            .outerjoin(ExpenseCategory, MoneyMovement.expense_category_id == ExpenseCategory.id)
            .where(*mm_filters)
            .group_by(
                MoneyMovement.movement_type,
                ExpenseCategory.id,
                ExpenseCategory.name,
                ExpenseCategory.is_direct_expense,
            )
        ).all()

        service_income = Decimal("0")
        operating_expenses = Decimal("0")
        expenses_by_cat: list[ExpenseCategoryBreakdown] = []

        for mt, cat_id, cat_name, is_direct, total in mm_rows:
            total_dec = Decimal(str(total))
            if mt == "service_income":
                service_income += total_dec
            elif mt in ("expense", "provision_expense", "expense_accrual", "deferred_expense", "depreciation_expense"):
                operating_expenses += total_dec
                expenses_by_cat.append(ExpenseCategoryBreakdown(
                    category_id=cat_id,
                    category_name=cat_name or "Sin categoria",
                    is_direct_expense=bool(is_direct),
                    total_amount=float(total_dec),
                    source_type=mt,
                ))

        # Comisiones causadas (commission_accrual) — split por origen:
        # - Sale.double_entry_id IS NULL → comision de venta regular
        # - Sale.double_entry_id IS NOT NULL → comision de doble partida
        # - sale_id IS NULL (orfana, defensivo) → cuenta como venta regular
        comm_filters = [
            MoneyMovement.organization_id == organization_id,
            self._active_at_cutoff(MoneyMovement.status, "confirmed"),
            MoneyMovement.movement_type == "commission_accrual",
        ]
        if has_dates:
            comm_filters += [MoneyMovement.date >= dt_from, MoneyMovement.date < dt_to]

        comm_rows = db.execute(
            select(
                case(
                    (Sale.double_entry_id.is_not(None), "double_entry"),
                    else_="sale",
                ).label("source"),
                func.coalesce(func.sum(MoneyMovement.amount), 0),
            )
            .select_from(MoneyMovement)
            .outerjoin(Sale, MoneyMovement.sale_id == Sale.id)
            .where(*comm_filters)
            .group_by("source")
        ).all()

        commissions_paid_sales = Decimal("0")
        commissions_paid_dp = Decimal("0")
        for source, total in comm_rows:
            total_dec = Decimal(str(total))
            if source == "double_entry":
                commissions_paid_dp += total_dec
            else:
                commissions_paid_sales += total_dec
        commissions_paid = commissions_paid_sales + commissions_paid_dp

        # Calculos
        gross_profit_sales = sales_revenue - cogs
        total_gross_profit = gross_profit_sales + de_profit + service_income + transformation_profit - waste_loss + adjustment_net + tp_adj_gain - tp_adj_loss
        net_profit = total_gross_profit - operating_expenses - commissions_paid

        return {
            "sales_revenue": sales_revenue,
            "sales_count": sales_count,
            "cogs": cogs,
            "de_profit": de_profit,
            "de_count": de_count,
            "transformation_profit": transformation_profit,
            "transformation_count": transformation_count,
            "waste_loss": waste_loss,
            "adjustment_net": adjustment_net,
            "tp_adjustment_loss": tp_adj_loss,
            "tp_adjustment_gain": tp_adj_gain,
            "service_income": service_income,
            "operating_expenses": operating_expenses,
            "commissions_paid": commissions_paid,
            "commissions_paid_sales": commissions_paid_sales,
            "commissions_paid_dp": commissions_paid_dp,
            "expenses_by_cat": expenses_by_cat,
            "gross_profit_sales": gross_profit_sales,
            "total_gross_profit": total_gross_profit,
            "net_profit": net_profit,
        }

    # ------------------------------------------------------------------
    # P&L Mensual — helper de split por meses contables (decision #50)
    # ------------------------------------------------------------------

    _SPANISH_MONTHS = [
        "Ene", "Feb", "Mar", "Abr", "May", "Jun",
        "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
    ]

    @classmethod
    def _split_into_accounting_months(
        cls,
        date_from: date,
        date_to: date,
        cutoff_day: int,
    ) -> list[tuple[date, date, str]]:
        """Genera lista de (period_from, period_to, label) de meses contables que
        intersectan [date_from, date_to].

        - `cutoff_day=1` produce meses calendario (label "Mar 2026").
        - `cutoff_day>1` produce meses con borde personalizado: empiezan el dia
          `cutoff_day` y terminan el dia `cutoff_day - 1` del mes siguiente
          (label "4 Mar – 3 Abr" o "4 Dic 2025 – 3 Ene 2026" cuando cruza año).
        - Limita `cutoff_day` a [1, 28] para evitar dias invalidos en febrero.

        Incluye TODO mes contable que intersecte el rango (no snap a bordes).
        """
        if not (1 <= cutoff_day <= 28):
            raise ValueError(f"cutoff_day fuera de rango: {cutoff_day} (debe ser 1-28)")
        if date_from > date_to:
            raise ValueError(f"date_from > date_to: {date_from} > {date_to}")

        cross_year = date_from.year != date_to.year

        def _add_month(year: int, month: int) -> tuple[int, int]:
            return (year + 1, 1) if month == 12 else (year, month + 1)

        # Primer mes contable: el que contiene date_from.
        if date_from.day >= cutoff_day:
            start_year, start_month = date_from.year, date_from.month
        else:
            # Empezo antes del cutoff -> el mes contable arranco el mes anterior.
            if date_from.month == 1:
                start_year, start_month = date_from.year - 1, 12
            else:
                start_year, start_month = date_from.year, date_from.month - 1

        results: list[tuple[date, date, str]] = []
        cur_year, cur_month = start_year, start_month
        # Cap para evitar loops infinitos (no deberia pasar dado le=24 en endpoint).
        for _ in range(60):
            period_from = date(cur_year, cur_month, cutoff_day)
            next_year, next_month = _add_month(cur_year, cur_month)
            if cutoff_day == 1:
                # Mes calendario: termina ultimo dia del mes (=> cutoff_day-1 del siguiente
                # daria dia 0; usamos next_month_first - 1 day en su lugar).
                period_to = date(next_year, next_month, 1) - timedelta(days=1)
                label = f"{cls._SPANISH_MONTHS[cur_month - 1]} {cur_year}"
            else:
                period_to = date(next_year, next_month, cutoff_day) - timedelta(days=1)
                if cross_year or cur_year != next_year:
                    label = (
                        f"{cutoff_day} {cls._SPANISH_MONTHS[cur_month - 1]} {cur_year} – "
                        f"{cutoff_day - 1} {cls._SPANISH_MONTHS[next_month - 1]} {next_year}"
                    )
                else:
                    label = (
                        f"{cutoff_day} {cls._SPANISH_MONTHS[cur_month - 1]} – "
                        f"{cutoff_day - 1} {cls._SPANISH_MONTHS[next_month - 1]} {cur_year}"
                    )

            results.append((period_from, period_to, label))

            # Si este mes ya contiene date_to, terminamos.
            if period_to >= date_to:
                break
            cur_year, cur_month = next_year, next_month

        return results

    def get_profit_and_loss_monthly(
        self,
        db: Session,
        organization_id: UUID,
        date_from: date,
        date_to: date,
        cutoff_day: int = 1,
    ) -> ProfitAndLossMonthlyResponse:
        """P&L mensual: una columna por mes contable derivado de cutoff_day.

        `totals` corresponde al rango exacto [date_from, date_to], NO a la suma
        aritmetica de las columnas — los meses contables pueden extenderse
        mas alla del rango y la suma de columnas estaria sobrestimada.

        Performance: cada mes invoca `get_profit_and_loss` (~7 queries SQL).
        Con 12 meses ~ 84 queries < 2s; con 24 meses ~168 queries < 4s.
        Mas alla → el endpoint rechaza con 422.
        """
        months = self._split_into_accounting_months(date_from, date_to, cutoff_day)
        periods: list[ProfitAndLossMonthlyPeriod] = []
        for period_from, period_to, label in months:
            period_pnl = self.get_profit_and_loss(db, organization_id, period_from, period_to)
            periods.append(ProfitAndLossMonthlyPeriod(
                **period_pnl.model_dump(),
                label=label,
            ))
        totals = self.get_profit_and_loss(db, organization_id, date_from, date_to)
        return ProfitAndLossMonthlyResponse(
            cutoff_day=cutoff_day,
            range_from=date_from,
            range_to=date_to,
            periods=periods,
            totals=totals,
        )

    def get_profit_and_loss(
        self,
        db: Session,
        organization_id: UUID,
        date_from: date,
        date_to: date,
    ) -> ProfitAndLossResponse:
        r = self._calculate_profit(db, organization_id, date_from, date_to)

        margin_base = r["sales_revenue"] + r["service_income"]

        return ProfitAndLossResponse(
            period_from=date_from,
            period_to=date_to,
            sales_revenue=float(r["sales_revenue"]),
            sales_count=r["sales_count"],
            service_income=float(r["service_income"]),
            cost_of_goods_sold=float(r["cogs"]),
            gross_profit_sales=float(r["gross_profit_sales"]),
            gross_margin_sales=self._safe_pct(r["gross_profit_sales"], r["sales_revenue"]),
            double_entry_profit=float(r["de_profit"]),
            double_entry_count=r["de_count"],
            transformation_profit=float(r["transformation_profit"]),
            transformation_count=r["transformation_count"],
            waste_loss=float(r["waste_loss"]),
            adjustment_net=float(r["adjustment_net"]),
            tp_adjustment_loss=float(r["tp_adjustment_loss"]),
            tp_adjustment_gain=float(r["tp_adjustment_gain"]),
            total_gross_profit=float(r["total_gross_profit"]),
            operating_expenses=float(r["operating_expenses"]),
            commissions_paid=float(r["commissions_paid"]),
            commissions_paid_sales=float(r["commissions_paid_sales"]),
            commissions_paid_dp=float(r["commissions_paid_dp"]),
            net_profit=float(r["net_profit"]),
            net_margin=self._safe_pct(r["net_profit"], margin_base) if margin_base else 0.0,
            expenses_by_category=r["expenses_by_cat"],
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
        # Solo MoneyMovements reales (no phantom de liquidaciones).
        # Pagos a proveedores y cobros a clientes se capturan por
        # payment_to_supplier y collection_from_client respectivamente.
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
        generic_payments = mm_map.get("payment_to_generic", Decimal("0"))
        generic_collections = mm_map.get("collection_from_generic", Decimal("0"))

        total_inflows = (
            customer_collections + service_income
            + capital_injections + advance_collections
            + generic_collections
        )
        total_outflows = (
            supplier_payments + expenses
            + commission_payments + capital_returns
            + provision_deposits + deferred_fundings
            + advance_payments + asset_payments
            + generic_payments
        )
        net_flow = total_inflows - total_outflows

        # --- Opening balance: balance actual - cambios reales desde dt_from ---
        # Solo MoneyMovements (flujo real de caja), no phantom de liquidaciones.
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

        opening_balance = current_total - net_mm_since
        closing_balance = opening_balance + net_flow

        return CashFlowResponse(
            period_from=date_from,
            period_to=date_to,
            opening_balance=float(opening_balance),
            inflows=CashFlowInflows(
                sale_collections=0,
                customer_collections=float(customer_collections),
                service_income=float(service_income),
                capital_injections=float(capital_injections),
                advance_collections=float(advance_collections),
                generic_collections=float(generic_collections),
                total=float(total_inflows),
            ),
            total_inflows=float(total_inflows),
            outflows=CashFlowOutflows(
                purchase_payments=0,
                supplier_payments=float(supplier_payments),
                expenses=float(expenses),
                commission_payments=float(commission_payments),
                capital_returns=float(capital_returns),
                provision_deposits=float(provision_deposits),
                deferred_fundings=float(deferred_fundings),
                advance_payments=float(advance_payments),
                asset_payments=float(asset_payments),
                generic_payments=float(generic_payments),
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
        as_of_date: Optional[date] = None,
    ) -> BalanceSheetResponse:
        if as_of_date is not None:
            return self._get_balance_sheet_historical(db, organization_id, as_of_date)
        return self._get_balance_sheet_current(db, organization_id)

    def _get_balance_sheet_current(
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

        # Activos fijos (valor actual de activos no dados de baja ni cancelados)
        fixed_assets_value = Decimal(str(
            db.scalar(
                select(func.coalesce(func.sum(FixedAsset.current_value), 0))
                .where(
                    FixedAsset.organization_id == organization_id,
                    FixedAsset.status.notin_(["disposed", "cancelled"]),
                )
            )
        ))

        # Clasificar terceros usando _classify_third_party (misma logica que Balance Detallado)
        # Evita doble conteo de terceros con multiples behavior_types
        all_tps = list(db.scalars(
            select(ThirdParty).where(
                ThirdParty.organization_id == organization_id,
                ThirdParty.is_active == True,
                ThirdParty.current_balance != 0,
            )
        ).all())
        tp_behaviors, tp_cat_names, _ = self._load_tp_behavior_map(db, organization_id)

        ASSET_SECTIONS = {
            "customers_receivable", "supplier_advances", "service_provider_advances",
            "liability_advances", "investor_receivable", "provision_funds",
            "prepaid_expenses", "generic_receivable",
        }
        LIABILITY_SECTIONS = {
            "suppliers_payable", "service_provider_payable", "liability_debt",
            "investors_partners", "investors_obligations", "investors_legacy",
            "customer_advances", "provision_obligations", "generic_payable",
        }

        from collections import defaultdict
        tp_buckets: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for tp in all_tps:
            behaviors = tp_behaviors.get(tp.id, set())
            cat_names = tp_cat_names.get(tp.id, set())
            section = self._classify_third_party(tp, behaviors, cat_names)
            balance = Decimal(str(tp.current_balance))
            if section in ASSET_SECTIONS:
                tp_buckets[section] += abs(balance) if section == "provision_funds" else balance
            elif section in LIABILITY_SECTIONS:
                tp_buckets[section] += abs(balance)

        # Mapear secciones detalladas → secciones del Balance General
        accounts_receivable = tp_buckets["customers_receivable"]
        advances = (tp_buckets["supplier_advances"] + tp_buckets["service_provider_advances"]
                    + tp_buckets["liability_advances"] + tp_buckets["generic_receivable"])
        investor_receivable = tp_buckets["investor_receivable"]
        prepaid_expenses = tp_buckets["prepaid_expenses"]
        provision_funds = tp_buckets["provision_funds"]

        total_assets = (cash_and_bank + accounts_receivable + inventory + advances
                        + investor_receivable + prepaid_expenses + provision_funds + fixed_assets_value)

        accounts_payable = tp_buckets["suppliers_payable"]
        investor_debt = (tp_buckets["investors_partners"] + tp_buckets["investors_obligations"]
                        + tp_buckets["investors_legacy"])
        liability_debt = tp_buckets["liability_debt"]
        service_provider_payable = tp_buckets["service_provider_payable"]
        customer_advances = tp_buckets["customer_advances"]
        provision_obligations = tp_buckets["provision_obligations"]
        generic_payable = tp_buckets["generic_payable"]

        total_liabilities = accounts_payable + investor_debt + liability_debt + service_provider_payable + customer_advances + provision_obligations + generic_payable
        equity = total_assets - total_liabilities

        # Desglose patrimonio: utilidad acumulada y distribuida
        accumulated_profit = self._calculate_profit(db, organization_id)["net_profit"]
        from app.services.profit_distribution import profit_distribution_service
        distributed_profit = profit_distribution_service.calculate_distributed_profit(db, organization_id)

        return BalanceSheetResponse(
            as_of_date=date.today(),
            assets=BalanceSheetAssets(
                cash_and_bank=float(cash_and_bank),
                accounts_receivable=float(accounts_receivable),
                inventory=float(inventory),
                advances=float(advances),
                investor_receivable=float(investor_receivable),
                prepaid_expenses=float(prepaid_expenses),
                provision_funds=float(provision_funds),
                fixed_assets=float(fixed_assets_value),
                total=float(total_assets),
            ),
            total_assets=float(total_assets),
            liabilities=BalanceSheetLiabilities(
                accounts_payable=float(accounts_payable),
                investor_debt=float(investor_debt),
                liability_debt=float(liability_debt),
                service_provider_payable=float(service_provider_payable),
                customer_advances=float(customer_advances),
                provision_obligations=float(provision_obligations),
                generic_payable=float(generic_payable),
                total=float(total_liabilities),
            ),
            total_liabilities=float(total_liabilities),
            equity=float(equity),
            accumulated_profit=float(accumulated_profit),
            distributed_profit=float(distributed_profit),
        )

    def _get_balance_sheet_historical(
        self,
        db: Session,
        organization_id: UUID,
        as_of_date: date,
    ) -> BalanceSheetResponse:
        """Balance Sheet calculado a una fecha de corte historica."""
        cutoff_dt = datetime.combine(as_of_date + timedelta(days=1), time.min, tzinfo=timezone.utc)

        # Activos: cuentas
        account_balances = self._get_account_balances_as_of(db, organization_id, cutoff_dt)
        cash_and_bank = sum(account_balances.values(), Decimal("0"))

        # Activos: inventario
        inventory_by_mat = self._get_inventory_as_of(db, organization_id, cutoff_dt)
        inventory = sum((stock * avg_cost for stock, avg_cost in inventory_by_mat.values()), Decimal("0"))

        # Activos fijos
        fixed_assets_value = self._get_fixed_assets_as_of(db, organization_id, cutoff_dt)

        # Terceros historicos
        tp_balances = self._get_tp_balances_as_of(db, organization_id, cutoff_dt)

        # Pre-cargar metadatos de terceros
        tp_behaviors, tp_cat_names, _ = self._load_tp_behavior_map(db, organization_id)
        tp_objs = {
            tp.id: tp for tp in db.scalars(
                select(ThirdParty).where(
                    ThirdParty.organization_id == organization_id,
                    ThirdParty.is_active == True,
                )
            ).all()
        }

        ASSET_SECTIONS = {
            "customers_receivable", "supplier_advances", "service_provider_advances",
            "liability_advances", "investor_receivable", "provision_funds",
            "prepaid_expenses", "generic_receivable",
        }
        LIABILITY_SECTIONS = {
            "suppliers_payable", "service_provider_payable", "liability_debt",
            "investors_partners", "investors_obligations", "investors_legacy",
            "customer_advances", "provision_obligations", "generic_payable",
        }

        from collections import defaultdict
        tp_buckets: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for tp_id, balance in tp_balances.items():
            tp = tp_objs.get(tp_id)
            if tp is None:
                continue
            behaviors = tp_behaviors.get(tp_id, set())
            cat_names = tp_cat_names.get(tp_id, set())
            section = self._classify_tp_by_balance(tp, balance, behaviors, cat_names)
            if section in ASSET_SECTIONS:
                tp_buckets[section] += abs(balance) if section == "provision_funds" else balance
            elif section in LIABILITY_SECTIONS:
                tp_buckets[section] += abs(balance)

        accounts_receivable = tp_buckets["customers_receivable"]
        advances = (tp_buckets["supplier_advances"] + tp_buckets["service_provider_advances"]
                    + tp_buckets["liability_advances"] + tp_buckets["generic_receivable"])
        investor_receivable = tp_buckets["investor_receivable"]
        prepaid_expenses = tp_buckets["prepaid_expenses"]
        provision_funds = tp_buckets["provision_funds"]

        total_assets = (cash_and_bank + accounts_receivable + inventory + advances
                        + investor_receivable + prepaid_expenses + provision_funds + fixed_assets_value)

        accounts_payable = tp_buckets["suppliers_payable"]
        investor_debt = (tp_buckets["investors_partners"] + tp_buckets["investors_obligations"]
                        + tp_buckets["investors_legacy"])
        liability_debt = tp_buckets["liability_debt"]
        service_provider_payable = tp_buckets["service_provider_payable"]
        customer_advances = tp_buckets["customer_advances"]
        provision_obligations = tp_buckets["provision_obligations"]
        generic_payable = tp_buckets["generic_payable"]

        total_liabilities = (accounts_payable + investor_debt + liability_debt
                             + service_provider_payable + customer_advances
                             + provision_obligations + generic_payable)
        equity = total_assets - total_liabilities

        accumulated_profit = self._calculate_profit(
            db, organization_id,
            date_from=date(1970, 1, 1), date_to=as_of_date,
            cutoff_dt=cutoff_dt,
        )["net_profit"]
        distributed_profit = self._get_distributed_profit_as_of(db, organization_id, cutoff_dt)

        return BalanceSheetResponse(
            as_of_date=as_of_date,
            assets=BalanceSheetAssets(
                cash_and_bank=float(cash_and_bank),
                accounts_receivable=float(accounts_receivable),
                inventory=float(inventory),
                advances=float(advances),
                investor_receivable=float(investor_receivable),
                prepaid_expenses=float(prepaid_expenses),
                provision_funds=float(provision_funds),
                fixed_assets=float(fixed_assets_value),
                total=float(total_assets),
            ),
            total_assets=float(total_assets),
            liabilities=BalanceSheetLiabilities(
                accounts_payable=float(accounts_payable),
                investor_debt=float(investor_debt),
                liability_debt=float(liability_debt),
                service_provider_payable=float(service_provider_payable),
                customer_advances=float(customer_advances),
                provision_obligations=float(provision_obligations),
                generic_payable=float(generic_payable),
                total=float(total_liabilities),
            ),
            total_liabilities=float(total_liabilities),
            equity=float(equity),
            accumulated_profit=float(accumulated_profit),
            distributed_profit=float(distributed_profit),
        )

    # ------------------------------------------------------------------
    # Balance Detallado
    # ------------------------------------------------------------------

    def get_balance_detailed(
        self,
        db: Session,
        organization_id: UUID,
        as_of_date: Optional[date] = None,
    ) -> BalanceDetailedResponse:
        """Balance general desglosado por item individual."""
        if as_of_date is not None:
            return self._get_balance_detailed_historical(db, organization_id, as_of_date)

        def _section(
            label: str,
            items: list[BalanceDetailedItem],
            section_key: str | None = None,
        ) -> BalanceDetailedSection:
            total = sum(i.balance for i in items)
            groups = None
            if section_key:
                groups = self._group_by_category(
                    items, section_key, tp_cat_by_behavior, self.SECTION_BEHAVIORS,
                )
            return BalanceDetailedSection(
                label=label, total=round(total, 2), items=items, groups=groups,
            )

        # --- Activos ---

        # 1. Efectivo y Bancos
        accounts = db.execute(
            select(MoneyAccount).where(
                MoneyAccount.organization_id == organization_id,
                MoneyAccount.is_active == True,
                MoneyAccount.current_balance != 0,
            )
        ).scalars().all()
        cash_items = [
            BalanceDetailedItem(
                id=str(a.id), name=a.name,
                balance=float(a.current_balance),
                account_type=a.account_type,
            ) for a in accounts
        ]

        # 2. Inventario Liquidado
        materials = db.execute(
            select(Material).where(
                Material.organization_id == organization_id,
                Material.is_active == True,
                Material.current_stock_liquidated != 0,
            )
        ).scalars().all()
        inv_liq_items = [
            BalanceDetailedItem(
                id=str(m.id), name=m.name,
                code=m.code,
                stock=float(m.current_stock_liquidated),
                avg_cost=float(m.current_average_cost),
                balance=round(float(m.current_stock_liquidated * m.current_average_cost), 2),
            ) for m in materials
        ]

        # 3. Activos Fijos
        fixed_assets = db.execute(
            select(FixedAsset).where(
                FixedAsset.organization_id == organization_id,
                FixedAsset.status.notin_(["disposed", "cancelled"]),
                FixedAsset.current_value > 0,
            )
        ).scalars().all()
        fa_items = [
            BalanceDetailedItem(
                id=str(fa.id), name=fa.name,
                current_value=float(fa.current_value),
                purchase_value=float(fa.purchase_value),
                accumulated_depreciation=float(fa.accumulated_depreciation),
                balance=float(fa.current_value),
            ) for fa in fixed_assets
        ]

        # 5. Terceros — cargar todos con balance != 0, clasificar
        third_parties = db.execute(
            select(ThirdParty).where(
                ThirdParty.organization_id == organization_id,
                ThirdParty.is_active == True,
                ThirdParty.current_balance != 0,
            )
        ).scalars().all()

        # Pre-cargar behavior_types y category_names
        tp_behaviors, tp_cat_names, tp_cat_by_behavior = self._load_tp_behavior_map(db, organization_id)

        # Buckets para clasificacion
        tp_buckets: dict[str, list[BalanceDetailedItem]] = {
            # activos
            "customers_receivable": [],
            "supplier_advances": [],
            "service_provider_advances": [],
            "liability_advances": [],
            "investor_receivable": [],
            "provision_funds": [],
            "prepaid_expenses": [],
            "generic_receivable": [],
            # pasivos
            "suppliers_payable": [],
            "service_provider_payable": [],
            "liability_debt": [],
            "investors_partners": [],
            "investors_obligations": [],
            "investors_legacy": [],
            "customer_advances": [],
            "provision_obligations": [],
            "generic_payable": [],
        }

        for tp in third_parties:
            behaviors = tp_behaviors.get(tp.id, set())
            cat_names = tp_cat_names.get(tp.id, set())
            section = self._classify_third_party(tp, behaviors, cat_names)
            if section and section in tp_buckets:
                bal = float(tp.current_balance)
                tp_buckets[section].append(BalanceDetailedItem(
                    id=str(tp.id), name=tp.name,
                    balance=abs(bal),
                ))

        # Construir secciones de activos
        assets: dict[str, BalanceDetailedSection] = {}
        asset_sections = [
            ("cash_and_bank", "Efectivo y Bancos", cash_items),
            ("inventory_liquidated", "Inventario Liquidado", inv_liq_items),
            ("customers_receivable", "CxC Clientes", tp_buckets["customers_receivable"]),
            ("supplier_advances", "Anticipos a Proveedores Material", tp_buckets["supplier_advances"]),
            ("service_provider_advances", "Anticipos a Proveedores Servicios", tp_buckets["service_provider_advances"]),
            ("liability_advances", "Anticipos a Pasivos", tp_buckets["liability_advances"]),
            ("investor_receivable", "CxC Inversionistas", tp_buckets["investor_receivable"]),
            ("provision_funds", "Fondos en Provisiones", tp_buckets["provision_funds"]),
            ("prepaid_expenses", "Gastos Prepagados", tp_buckets["prepaid_expenses"]),
            ("generic_receivable", "Otras Cuentas por Cobrar", tp_buckets["generic_receivable"]),
            ("fixed_assets", "Activos Fijos", fa_items),
        ]
        for key, label, items in asset_sections:
            assets[key] = _section(label, items, section_key=key)

        total_assets = round(sum(s.total for s in assets.values()), 2)

        # Construir secciones de pasivos
        liabilities: dict[str, BalanceDetailedSection] = {}
        liability_sections = [
            ("suppliers_payable", "CxP Proveedores Material", tp_buckets["suppliers_payable"]),
            ("service_provider_payable", "CxP Proveedores Servicios", tp_buckets["service_provider_payable"]),
            ("liability_debt", "CxP Pasivos", tp_buckets["liability_debt"]),
            ("investors_partners", "Socios", tp_buckets["investors_partners"]),
            ("investors_obligations", "Obligaciones Financieras", tp_buckets["investors_obligations"]),
            ("investors_legacy", "Inversionistas", tp_buckets["investors_legacy"]),
            ("customer_advances", "Anticipos de Clientes", tp_buckets["customer_advances"]),
            ("provision_obligations", "Obligaciones Provisiones", tp_buckets["provision_obligations"]),
            ("generic_payable", "Otras Cuentas por Pagar", tp_buckets["generic_payable"]),
        ]
        for key, label, items in liability_sections:
            liabilities[key] = _section(label, items, section_key=key)

        total_liabilities = round(sum(s.total for s in liabilities.values()), 2)

        equity = round(total_assets - total_liabilities, 2)
        verification_result = round(total_assets - total_liabilities - equity, 2)

        # Desglose patrimonio
        accumulated_profit = float(self._calculate_profit(db, organization_id)["net_profit"])
        from app.services.profit_distribution import profit_distribution_service
        distributed_profit = float(profit_distribution_service.calculate_distributed_profit(db, organization_id))

        return BalanceDetailedResponse(
            as_of_date=date.today(),
            assets=assets,
            total_assets=total_assets,
            liabilities=liabilities,
            total_liabilities=total_liabilities,
            equity=equity,
            accumulated_profit=accumulated_profit,
            distributed_profit=distributed_profit,
            verification=BalanceDetailedVerification(
                formula="Activos - Pasivos - Patrimonio",
                result=verification_result,
                is_balanced=verification_result == 0,
            ),
        )

    def _get_balance_detailed_historical(
        self,
        db: Session,
        organization_id: UUID,
        as_of_date: date,
    ) -> BalanceDetailedResponse:
        """Balance Detallado calculado a una fecha de corte historica."""
        cutoff_dt = datetime.combine(as_of_date + timedelta(days=1), time.min, tzinfo=timezone.utc)

        # Pre-cargar metadatos de terceros
        tp_behaviors, tp_cat_names, tp_cat_by_behavior = self._load_tp_behavior_map(db, organization_id)
        tp_objs = {
            tp.id: tp for tp in db.scalars(
                select(ThirdParty).where(
                    ThirdParty.organization_id == organization_id,
                    ThirdParty.is_active == True,
                )
            ).all()
        }

        def _section(
            label: str,
            items: list[BalanceDetailedItem],
            section_key: str | None = None,
        ) -> BalanceDetailedSection:
            total = sum(i.balance for i in items)
            groups = None
            if section_key:
                groups = self._group_by_category(
                    items, section_key, tp_cat_by_behavior, self.SECTION_BEHAVIORS,
                )
            return BalanceDetailedSection(
                label=label, total=round(total, 2), items=items, groups=groups,
            )

        # 1. Cuentas de dinero
        account_balances = self._get_account_balances_as_of(db, organization_id, cutoff_dt)
        acc_objs = {a.id: a for a in db.scalars(
            select(MoneyAccount).where(
                MoneyAccount.organization_id == organization_id,
                MoneyAccount.is_active == True,
            )
        ).all()}
        cash_items = [
            BalanceDetailedItem(
                id=str(acc_id), name=acc_objs[acc_id].name,
                balance=float(bal),
                account_type=acc_objs[acc_id].account_type,
            )
            for acc_id, bal in account_balances.items()
            if acc_id in acc_objs
        ]

        # 2. Inventario historico
        inventory_by_mat = self._get_inventory_as_of(db, organization_id, cutoff_dt)
        mat_objs = {m.id: m for m in db.scalars(
            select(Material).where(
                Material.organization_id == organization_id,
                Material.is_active == True,
            )
        ).all()}
        inv_liq_items = [
            BalanceDetailedItem(
                id=str(mat_id),
                name=mat_objs[mat_id].name if mat_id in mat_objs else str(mat_id),
                code=mat_objs[mat_id].code if mat_id in mat_objs else None,
                stock=float(stock),
                avg_cost=float(avg_cost),
                balance=round(float(stock * avg_cost), 2),
            )
            for mat_id, (stock, avg_cost) in inventory_by_mat.items()
        ]

        # 3. Activos fijos historicos
        fa_items = self._get_fixed_assets_detailed_as_of(db, organization_id, cutoff_dt)

        # 4. Terceros historicos
        tp_balances = self._get_tp_balances_as_of(db, organization_id, cutoff_dt)

        tp_buckets: dict[str, list[BalanceDetailedItem]] = {
            "customers_receivable": [], "supplier_advances": [],
            "service_provider_advances": [], "liability_advances": [],
            "investor_receivable": [], "provision_funds": [],
            "prepaid_expenses": [], "generic_receivable": [],
            "suppliers_payable": [], "service_provider_payable": [],
            "liability_debt": [], "investors_partners": [],
            "investors_obligations": [], "investors_legacy": [],
            "customer_advances": [], "provision_obligations": [], "generic_payable": [],
        }
        for tp_id, balance in tp_balances.items():
            tp = tp_objs.get(tp_id)
            if tp is None:
                continue
            behaviors = tp_behaviors.get(tp_id, set())
            cat_names = tp_cat_names.get(tp_id, set())
            section = self._classify_tp_by_balance(tp, balance, behaviors, cat_names)
            if section and section in tp_buckets:
                tp_buckets[section].append(BalanceDetailedItem(
                    id=str(tp_id), name=tp.name,
                    balance=abs(float(balance)),
                ))

        assets: dict[str, BalanceDetailedSection] = {}
        asset_sections = [
            ("cash_and_bank", "Efectivo y Bancos", cash_items),
            ("inventory_liquidated", "Inventario Liquidado", inv_liq_items),
            ("customers_receivable", "CxC Clientes", tp_buckets["customers_receivable"]),
            ("supplier_advances", "Anticipos a Proveedores Material", tp_buckets["supplier_advances"]),
            ("service_provider_advances", "Anticipos a Proveedores Servicios", tp_buckets["service_provider_advances"]),
            ("liability_advances", "Anticipos a Pasivos", tp_buckets["liability_advances"]),
            ("investor_receivable", "CxC Inversionistas", tp_buckets["investor_receivable"]),
            ("provision_funds", "Fondos en Provisiones", tp_buckets["provision_funds"]),
            ("prepaid_expenses", "Gastos Prepagados", tp_buckets["prepaid_expenses"]),
            ("generic_receivable", "Otras Cuentas por Cobrar", tp_buckets["generic_receivable"]),
            ("fixed_assets", "Activos Fijos", fa_items),
        ]
        for key, label, items in asset_sections:
            assets[key] = _section(label, items, section_key=key)

        total_assets = round(sum(s.total for s in assets.values()), 2)

        liabilities: dict[str, BalanceDetailedSection] = {}
        liability_sections = [
            ("suppliers_payable", "CxP Proveedores Material", tp_buckets["suppliers_payable"]),
            ("service_provider_payable", "CxP Proveedores Servicios", tp_buckets["service_provider_payable"]),
            ("liability_debt", "CxP Pasivos", tp_buckets["liability_debt"]),
            ("investors_partners", "Socios", tp_buckets["investors_partners"]),
            ("investors_obligations", "Obligaciones Financieras", tp_buckets["investors_obligations"]),
            ("investors_legacy", "Inversionistas", tp_buckets["investors_legacy"]),
            ("customer_advances", "Anticipos de Clientes", tp_buckets["customer_advances"]),
            ("provision_obligations", "Obligaciones Provisiones", tp_buckets["provision_obligations"]),
            ("generic_payable", "Otras Cuentas por Pagar", tp_buckets["generic_payable"]),
        ]
        for key, label, items in liability_sections:
            liabilities[key] = _section(label, items, section_key=key)

        total_liabilities = round(sum(s.total for s in liabilities.values()), 2)
        equity = round(total_assets - total_liabilities, 2)
        verification_result = round(total_assets - total_liabilities - equity, 2)

        accumulated_profit = float(self._calculate_profit(
            db, organization_id,
            date_from=date(1970, 1, 1), date_to=as_of_date,
            cutoff_dt=cutoff_dt,
        )["net_profit"])
        distributed_profit = float(self._get_distributed_profit_as_of(db, organization_id, cutoff_dt))

        return BalanceDetailedResponse(
            as_of_date=as_of_date,
            assets=assets,
            total_assets=total_assets,
            liabilities=liabilities,
            total_liabilities=total_liabilities,
            equity=equity,
            accumulated_profit=accumulated_profit,
            distributed_profit=distributed_profit,
            verification=BalanceDetailedVerification(
                formula="Activos - Pasivos - Patrimonio",
                result=verification_result,
                is_balanced=verification_result == 0,
            ),
        )

    @staticmethod
    def _classify_third_party(
        tp: ThirdParty,
        behavior_types: set[str],
        category_names: set[str],
    ) -> str | None:
        """Clasifica un tercero en una unica seccion del balance segun prioridad."""
        bal = float(tp.current_balance)
        if bal == 0:
            return None
        # System entities (prepagados)
        if tp.is_system_entity and bal > 0:
            return "prepaid_expenses"
        # Provisiones
        if "provision" in behavior_types:
            return "provision_funds" if bal < 0 else "provision_obligations"
        if bal > 0:
            # Nos deben / tenemos a favor
            if "customer" in behavior_types:
                return "customers_receivable"
            if "investor" in behavior_types:
                return "investor_receivable"
            if "material_supplier" in behavior_types:
                return "supplier_advances"
            if "service_provider" in behavior_types:
                return "service_provider_advances"
            if "liability" in behavior_types:
                return "liability_advances"
            if "generic" in behavior_types:
                return "generic_receivable"
        else:
            # Debemos
            if "material_supplier" in behavior_types:
                return "suppliers_payable"
            if "service_provider" in behavior_types:
                return "service_provider_payable"
            if "liability" in behavior_types:
                return "liability_debt"
            if "investor" in behavior_types:
                # Distinguir socios de obligaciones financieras por nombre de categoria
                lowered = {n.lower() for n in category_names}
                if any("socio" in n for n in lowered):
                    return "investors_partners"
                if any("obligaci" in n for n in lowered):
                    return "investors_obligations"
                return "investors_legacy"
            if "customer" in behavior_types:
                return "customer_advances"
            if "generic" in behavior_types:
                return "generic_payable"
        return None

    # Mapeo seccion → behavior_types relevantes para agrupacion por categoria
    SECTION_BEHAVIORS = {
        "customers_receivable": ["customer"],
        "supplier_advances": ["material_supplier"],
        "service_provider_advances": ["service_provider"],
        "liability_advances": ["liability"],
        "investor_receivable": ["investor"],
        "suppliers_payable": ["material_supplier"],
        "service_provider_payable": ["service_provider"],
        "liability_debt": ["liability"],
        "customer_advances": ["customer"],
        "investors_partners": ["investor"],
        "investors_obligations": ["investor"],
        "investors_legacy": ["investor"],
        "provision_funds": ["provision"],
        "provision_obligations": ["provision"],
        "generic_receivable": ["generic"],
        "generic_payable": ["generic"],
    }

    @staticmethod
    def _group_by_category(
        items: list[BalanceDetailedItem],
        section_key: str,
        tp_cat_by_behavior: dict,
        section_behaviors: dict,
    ) -> list[BalanceDetailedGroup] | None:
        """Agrupa items por categoria de tercero. Retorna None si no hay agrupacion util."""
        behaviors = section_behaviors.get(section_key)
        if not behaviors or len(items) < 2:
            return None

        groups: dict[str, list[BalanceDetailedItem]] = {}
        for item in items:
            tp_id_uuid = UUID(item.id)
            cat_map = tp_cat_by_behavior.get(tp_id_uuid, {})
            # Buscar la primera categoria que matchee algun behavior_type de la seccion
            cat_name = None
            for bt in behaviors:
                if bt in cat_map:
                    cat_name = cat_map[bt]
                    break
            label = cat_name or "Sin Categoría"
            groups.setdefault(label, []).append(item)

        # Solo agrupar si hay mas de 1 grupo distinto
        if len(groups) <= 1:
            return None

        # Ordenar por total descendente, "Sin Categoría" siempre al final
        result = []
        for label, group_items in groups.items():
            total = round(sum(i.balance for i in group_items), 2)
            result.append(BalanceDetailedGroup(label=label, total=total, items=group_items))
        result.sort(key=lambda g: (g.label == "Sin Categoría", -g.total))
        return result

    @staticmethod
    def _active_at_cutoff(status_col, active_status: str = "liquidated"):
        """Operaciones activas: excluye cualquier cancelacion/anulacion sin importar fecha."""
        return status_col == active_status

    # ------------------------------------------------------------------
    # Helpers de balance historico (as_of_date)
    # ------------------------------------------------------------------

    def _get_account_balances_as_of(
        self,
        db: Session,
        organization_id: UUID,
        cutoff_dt: datetime,
    ) -> dict[UUID, Decimal]:
        """Saldo de cada cuenta activa a la fecha de corte."""
        accounts = db.scalars(
            select(MoneyAccount).where(
                MoneyAccount.organization_id == organization_id,
                MoneyAccount.is_active == True,
            )
        ).all()

        result: dict[UUID, Decimal] = {}
        for acc in accounts:
            delta = db.scalar(
                select(func.coalesce(func.sum(
                    case(
                        *[
                            (MoneyMovement.movement_type == mt, MoneyMovement.amount * direction)
                            for mt, direction in ACCOUNT_BALANCE_DIRECTION.items()
                        ],
                        else_=Decimal("0"),
                    )
                ), Decimal("0")))
                .where(
                    MoneyMovement.account_id == acc.id,
                    MoneyMovement.date < cutoff_dt,
                    self._active_at_cutoff(MoneyMovement.status, "confirmed"),
                )
            ) or Decimal("0")
            balance = Decimal(str(acc.initial_balance)) + Decimal(str(delta))
            if balance != 0:
                result[acc.id] = balance
        return result

    def _get_tp_balances_as_of(
        self,
        db: Session,
        organization_id: UUID,
        cutoff_dt: datetime,
    ) -> dict[UUID, Decimal]:
        """Saldo de cada tercero a la fecha de corte (5 fuentes)."""
        from collections import defaultdict
        balances: dict[UUID, Decimal] = defaultdict(Decimal)

        # Base: initial_balance de cada tercero
        tps = db.scalars(
            select(ThirdParty).where(
                ThirdParty.organization_id == organization_id,
                ThirdParty.is_active == True,
            )
        ).all()
        for tp in tps:
            balances[tp.id] += Decimal(str(tp.initial_balance))

        # Fuente 1: MoneyMovements
        mm_rows = db.execute(
            select(
                MoneyMovement.third_party_id,
                MoneyMovement.movement_type,
                func.sum(MoneyMovement.amount),
            ).where(
                MoneyMovement.organization_id == organization_id,
                MoneyMovement.third_party_id.isnot(None),
                MoneyMovement.date < cutoff_dt,
                self._active_at_cutoff(MoneyMovement.status, "confirmed"),
            ).group_by(MoneyMovement.third_party_id, MoneyMovement.movement_type)
        ).all()

        for tp_id, mt, total in mm_rows:
            direction = THIRD_PARTY_BALANCE_DIRECTION.get(mt, 0)
            if direction != 0:
                balances[tp_id] += Decimal(str(total)) * direction

        # Fuente 2: Compras liquidadas al corte (incluye DPs)
        purchase_rows = db.execute(
            select(
                Purchase.supplier_id,
                func.sum(Purchase.total_amount),
            ).where(
                Purchase.organization_id == organization_id,
                Purchase.liquidated_at < cutoff_dt,
                self._active_at_cutoff(Purchase.status),
            ).group_by(Purchase.supplier_id)
        ).all()
        for tp_id, total in purchase_rows:
            balances[tp_id] -= Decimal(str(total))

        # Fuente 3: Ventas liquidadas al corte (incluye DPs)
        sale_rows = db.execute(
            select(
                Sale.customer_id,
                func.sum(Sale.total_amount),
            ).where(
                Sale.organization_id == organization_id,
                Sale.liquidated_at < cutoff_dt,
                self._active_at_cutoff(Sale.status),
            ).group_by(Sale.customer_id)
        ).all()
        for tp_id, total in sale_rows:
            balances[tp_id] += Decimal(str(total))

        # Fuente 4: Comisiones de compra
        purchase_comm_rows = db.execute(
            select(
                PurchaseCommission.third_party_id,
                func.sum(PurchaseCommission.commission_amount),
            ).join(Purchase, PurchaseCommission.purchase_id == Purchase.id)
            .where(
                Purchase.organization_id == organization_id,
                Purchase.liquidated_at < cutoff_dt,
                self._active_at_cutoff(Purchase.status),
            ).group_by(PurchaseCommission.third_party_id)
        ).all()
        for tp_id, total in purchase_comm_rows:
            balances[tp_id] -= Decimal(str(total))

        # Fuente 5: Comisiones de venta standalone (sin double_entry_id en la venta)
        # Excluir las que tienen commission_accrual MM activo al corte (evitar doble conteo)
        accrual_sale_ids = db.scalars(
            select(MoneyMovement.sale_id).where(
                MoneyMovement.organization_id == organization_id,
                MoneyMovement.movement_type == "commission_accrual",
                MoneyMovement.sale_id.isnot(None),
                MoneyMovement.date < cutoff_dt,
                self._active_at_cutoff(MoneyMovement.status, "confirmed"),
            )
        ).all()
        accrual_sale_ids_set = set(accrual_sale_ids)

        sale_comm_rows = db.execute(
            select(
                SaleCommission.third_party_id,
                func.sum(SaleCommission.commission_amount),
            ).join(Sale, SaleCommission.sale_id == Sale.id)
            .where(
                Sale.organization_id == organization_id,
                Sale.double_entry_id.is_(None),
                Sale.liquidated_at < cutoff_dt,
                self._active_at_cutoff(Sale.status),
                ~SaleCommission.sale_id.in_(accrual_sale_ids_set) if accrual_sale_ids_set else True,
            ).group_by(SaleCommission.third_party_id)
        ).all()
        for tp_id, total in sale_comm_rows:
            balances[tp_id] -= Decimal(str(total))

        return {k: v for k, v in balances.items() if v != 0}

    def _get_inventory_as_of(
        self,
        db: Session,
        organization_id: UUID,
        cutoff_dt: datetime,
    ) -> dict[UUID, tuple[Decimal, Decimal]]:
        """Stock liquidado y costo promedio por material a la fecha de corte.

        Returns dict[material_id, (stock, avg_cost)]
        Excluye:
        - Compras registradas (unit_cost=0, solo transito)
        - Ventas no liquidadas al corte
        """
        # cutoff_dt = as_of_date + 1 día (00:00 UTC del día siguiente).
        # Para comparar con MaterialCostHistory.transaction_date (date),
        # necesitamos as_of_date original, no cutoff_dt.date() que da as_of_date+1.
        cutoff_date = (cutoff_dt - timedelta(days=1)).date()

        # Movimientos de inventario hasta el corte
        # Excluir compras en transito (unit_cost=0 + reference_type='purchase' sin venta liquidada)
        # y ventas aun no liquidadas al corte
        movement_rows = db.execute(
            select(
                InventoryMovement.material_id,
                func.sum(InventoryMovement.quantity),
            ).where(
                InventoryMovement.organization_id == organization_id,
                InventoryMovement.date < cutoff_dt,
                # Excluir compras en transito (unit_cost = 0)
                or_(
                    InventoryMovement.movement_type != "purchase",
                    InventoryMovement.unit_cost != 0,
                ),
                # Excluir ventas no liquidadas al corte (original y reversal)
                # Razón: sale_reversal de ventas canceladas (no liquidadas) quedaba incluido
                # pero su original (-X) quedaba excluido, generando stock fantasma.
                ~and_(
                    InventoryMovement.movement_type.in_(["sale", "sale_reversal"]),
                    InventoryMovement.reference_type == "sale",
                    exists(
                        select(Sale.id).where(
                            Sale.id == InventoryMovement.reference_id,
                            ~self._active_at_cutoff(Sale.status),
                        )
                    ),
                ),
            ).group_by(InventoryMovement.material_id)
        ).all()

        stock_by_mat: dict[UUID, Decimal] = {
            mat_id: Decimal(str(qty))
            for mat_id, qty in movement_rows
            if qty and Decimal(str(qty)) != 0
        }

        # Costo promedio historico via MaterialCostHistory.transaction_date
        # Ultimo registro con transaction_date <= corte
        cost_by_mat: dict[UUID, Decimal] = {}
        if stock_by_mat:
            cost_rows = db.execute(
                select(
                    MaterialCostHistory.material_id,
                    MaterialCostHistory.new_cost,
                ).distinct(MaterialCostHistory.material_id)
                .where(
                    MaterialCostHistory.organization_id == organization_id,
                    MaterialCostHistory.material_id.in_(list(stock_by_mat.keys())),
                    MaterialCostHistory.transaction_date <= cutoff_date,
                ).order_by(
                    MaterialCostHistory.material_id,
                    MaterialCostHistory.transaction_date.desc(),
                    MaterialCostHistory.created_at.desc(),
                )
            ).all()
            for mat_id, cost in cost_rows:
                if mat_id not in cost_by_mat:
                    cost_by_mat[mat_id] = Decimal(str(cost))

            # Fallback 1: materiales sin historial al corte → previous_cost del primer registro posterior
            missing = [mid for mid in stock_by_mat if mid not in cost_by_mat]
            if missing:
                fallback_rows = db.execute(
                    select(
                        MaterialCostHistory.material_id,
                        MaterialCostHistory.previous_cost,
                    ).distinct(MaterialCostHistory.material_id)
                    .where(
                        MaterialCostHistory.organization_id == organization_id,
                        MaterialCostHistory.material_id.in_(missing),
                    ).order_by(
                        MaterialCostHistory.material_id,
                        MaterialCostHistory.transaction_date.asc(),
                        MaterialCostHistory.created_at.asc(),
                    )
                ).all()
                for mat_id, cost in fallback_rows:
                    if mat_id not in cost_by_mat:
                        cost_by_mat[mat_id] = Decimal(str(cost))

            # Fallback 2: materiales sin ningun registro en MaterialCostHistory
            # (ajustes legacy sin historial de costo) → unit_cost del último movimiento
            # de compra/ajuste antes del corte. El costo está guardado en el movimiento.
            missing2 = [mid for mid in stock_by_mat if mid not in cost_by_mat]
            if missing2:
                movement_cost_rows = db.execute(
                    select(
                        InventoryMovement.material_id,
                        InventoryMovement.unit_cost,
                    ).distinct(InventoryMovement.material_id)
                    .where(
                        InventoryMovement.organization_id == organization_id,
                        InventoryMovement.material_id.in_(missing2),
                        InventoryMovement.date < cutoff_dt,
                        InventoryMovement.unit_cost > 0,
                        InventoryMovement.movement_type.in_(["purchase", "adjustment"]),
                    ).order_by(
                        InventoryMovement.material_id,
                        InventoryMovement.date.desc(),
                    )
                ).all()
                for mat_id, cost in movement_cost_rows:
                    if mat_id not in cost_by_mat:
                        cost_by_mat[mat_id] = Decimal(str(cost))

        result: dict[UUID, tuple[Decimal, Decimal]] = {}
        for mat_id, stock in stock_by_mat.items():
            avg_cost = cost_by_mat.get(mat_id, Decimal("0"))
            if stock != 0:
                result[mat_id] = (stock, avg_cost)
        return result

    def _fa_value_at_cutoff(self, db: Session, fa, cutoff_period: str) -> Decimal:
        """Valor de un activo fijo en un período de corte dado.

        Lógica de 2 niveles:
        1. Si existen depreciaciones aplicadas con period <= cutoff_period,
           usar current_value_after del último período cubierto.
        2. Si no hay registros al corte (activo cargado con depreciación acumulada
           histórica pre-sistema), reconstruir el valor revirtiendo las depreciaciones
           posteriores al corte: current_value + SUM(amount para period > cutoff_period).
           Esto da el valor exacto que tenía el activo en el corte.
        """
        last_dep = db.scalar(
            select(AssetDepreciation.current_value_after)
            .where(
                AssetDepreciation.fixed_asset_id == fa.id,
                AssetDepreciation.is_active == True,
                AssetDepreciation.period <= cutoff_period,
            ).order_by(AssetDepreciation.period.desc())
            .limit(1)
        )
        if last_dep is not None:
            return Decimal(str(last_dep))

        # Sin registros al corte: revertir depreciaciones posteriores
        future_dep = db.scalar(
            select(func.coalesce(func.sum(AssetDepreciation.amount), 0))
            .where(
                AssetDepreciation.fixed_asset_id == fa.id,
                AssetDepreciation.is_active == True,
                AssetDepreciation.period > cutoff_period,
            )
        )
        return Decimal(str(fa.current_value)) + Decimal(str(future_dep))

    def _get_fixed_assets_as_of(
        self,
        db: Session,
        organization_id: UUID,
        cutoff_dt: datetime,
    ) -> Decimal:
        """Valor total de activos fijos a la fecha de corte.

        Usa AssetDepreciation.period ("YYYY-MM") como fecha contable,
        no applied_at (cuándo el usuario clickó aplicar).
        """
        cutoff_date = (cutoff_dt - timedelta(days=1)).date()
        cutoff_period = cutoff_date.strftime("%Y-%m")
        assets = db.scalars(
            select(FixedAsset).where(
                FixedAsset.organization_id == organization_id,
                FixedAsset.purchase_date <= cutoff_date,
                FixedAsset.status.notin_(["disposed", "cancelled"]),
            )
        ).all()

        return sum(
            (self._fa_value_at_cutoff(db, fa, cutoff_period) for fa in assets),
            Decimal("0"),
        )

    def _get_fixed_assets_detailed_as_of(
        self,
        db: Session,
        organization_id: UUID,
        cutoff_dt: datetime,
    ) -> list[BalanceDetailedItem]:
        """Items de activos fijos para Balance Detallado historico."""
        cutoff_date = (cutoff_dt - timedelta(days=1)).date()
        cutoff_period = cutoff_date.strftime("%Y-%m")
        assets = db.scalars(
            select(FixedAsset).where(
                FixedAsset.organization_id == organization_id,
                FixedAsset.purchase_date <= cutoff_date,
                FixedAsset.status.notin_(["disposed", "cancelled"]),
            )
        ).all()

        items = []
        for fa in assets:
            current_value = self._fa_value_at_cutoff(db, fa, cutoff_period)
            if current_value > 0:
                # Depreciacion acumulada historica = diferencia vs purchase_value
                acc_dep = Decimal(str(fa.purchase_value)) - current_value
                items.append(BalanceDetailedItem(
                    id=str(fa.id), name=fa.name,
                    current_value=float(current_value),
                    purchase_value=float(fa.purchase_value),
                    accumulated_depreciation=float(acc_dep),
                    balance=float(current_value),
                ))
        return items

    def _get_distributed_profit_as_of(
        self,
        db: Session,
        organization_id: UUID,
        cutoff_dt: datetime,
    ) -> Decimal:
        """Total de utilidades distribuidas hasta la fecha de corte."""
        val = db.scalar(
            select(func.coalesce(func.sum(MoneyMovement.amount), 0))
            .where(
                MoneyMovement.organization_id == organization_id,
                MoneyMovement.movement_type == "profit_distribution",
                MoneyMovement.date < cutoff_dt,
                self._active_at_cutoff(MoneyMovement.status, "confirmed"),
            )
        )
        return Decimal(str(val))

    @staticmethod
    def _classify_tp_by_balance(
        tp: ThirdParty,
        balance: Decimal,
        behavior_types: set[str],
        category_names: set[str],
    ) -> str | None:
        """Como _classify_third_party pero usa balance externo (historico)."""
        bal = float(balance)
        if bal == 0:
            return None
        if tp.is_system_entity and bal > 0:
            return "prepaid_expenses"
        if "provision" in behavior_types:
            return "provision_funds" if bal < 0 else "provision_obligations"
        if bal > 0:
            if "customer" in behavior_types:
                return "customers_receivable"
            if "investor" in behavior_types:
                return "investor_receivable"
            if "material_supplier" in behavior_types:
                return "supplier_advances"
            if "service_provider" in behavior_types:
                return "service_provider_advances"
            if "liability" in behavior_types:
                return "liability_advances"
            if "generic" in behavior_types:
                return "generic_receivable"
        else:
            if "material_supplier" in behavior_types:
                return "suppliers_payable"
            if "service_provider" in behavior_types:
                return "service_provider_payable"
            if "liability" in behavior_types:
                return "liability_debt"
            if "investor" in behavior_types:
                lowered = {n.lower() for n in category_names}
                if any("socio" in n for n in lowered):
                    return "investors_partners"
                if any("obligaci" in n for n in lowered):
                    return "investors_obligations"
                return "investors_legacy"
            if "customer" in behavior_types:
                return "customer_advances"
            if "generic" in behavior_types:
                return "generic_payable"
        return None

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
        dp_filter: str = "all",
    ) -> PurchaseReportResponse:
        dt_from, dt_to = self._date_range(date_from, date_to)

        # Base filters — solo compras liquidadas (con precios confirmados)
        base_filters = [
            Purchase.organization_id == organization_id,
            Purchase.status == "liquidated",
            Purchase.liquidated_at >= dt_from,
            Purchase.liquidated_at < dt_to,
        ]
        if supplier_id:
            base_filters.append(Purchase.supplier_id == supplier_id)
        if dp_filter == "exclude":
            base_filters.append(Purchase.double_entry_id.is_(None))
        elif dp_filter == "only":
            base_filters.append(Purchase.double_entry_id.is_not(None))

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
        dp_filter: str = "all",
    ) -> SalesReportResponse:
        dt_from, dt_to = self._date_range(date_from, date_to)

        base_filters = [
            Sale.organization_id == organization_id,
            Sale.status == "liquidated",
            Sale.liquidated_at >= dt_from,
            Sale.liquidated_at < dt_to,
        ]
        if customer_id:
            base_filters.append(Sale.customer_id == customer_id)
        if dp_filter == "exclude":
            base_filters.append(Sale.double_entry_id.is_(None))
        elif dp_filter == "only":
            base_filters.append(Sale.double_entry_id.is_not(None))

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
                Sale.liquidated_at >= dt_from,
                Sale.liquidated_at < dt_to,
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
                Purchase.liquidated_at >= dt_from,
                Purchase.liquidated_at < dt_to,
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
                DoubleEntry.status == "liquidated",
                DoubleEntry.liquidated_at >= dt_from,
                DoubleEntry.liquidated_at < dt_to,
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
                    self._tp_has_behavior("material_supplier", "service_provider", "liability"),
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
                    self._tp_has_behavior("customer"),
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
                        Sale.liquidated_at >= dt_f,
                        Sale.liquidated_at < dt_t,
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
                        Purchase.liquidated_at >= dt_f,
                        Purchase.liquidated_at < dt_t,
                    )
                )
            ))

        def _period_gross_profit(dt_f, dt_t):
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
                        Sale.liquidated_at >= dt_f,
                        Sale.liquidated_at < dt_t,
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
                        DoubleEntry.status == "liquidated",
                        DoubleEntry.liquidated_at >= dt_f,
                        DoubleEntry.liquidated_at < dt_t,
                    )
                )
            ))
            return sale_profit + de_profit

        cur_sales = _period_sales(dt_from, dt_to)
        prev_sales = _period_sales(prev_dt_from, prev_dt_to)
        cur_purchases = _period_purchases(dt_from, dt_to)
        prev_purchases = _period_purchases(prev_dt_from, prev_dt_to)
        cur_profit = _period_gross_profit(dt_from, dt_to)
        prev_profit = _period_gross_profit(prev_dt_from, prev_dt_to)

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
                    self._tp_has_behavior("customer"),
                    ThirdParty.current_balance > 0,
                )
            )
        ))

        payables = Decimal(str(
            db.scalar(
                select(func.coalesce(func.sum(func.abs(ThirdParty.current_balance)), 0))
                .where(
                    ThirdParty.organization_id == organization_id,
                    self._tp_has_behavior("material_supplier", "service_provider", "liability"),
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
                Sale.liquidated_at >= dt_from,
                Sale.liquidated_at < dt_to,
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
                func.coalesce(func.sum(PurchaseLine.unit_price * PurchaseLine.quantity), 0),
                func.coalesce(func.sum(PurchaseLine.quantity), 0),
            )
            .select_from(Purchase)
            .join(ThirdParty, Purchase.supplier_id == ThirdParty.id)
            .join(PurchaseLine, PurchaseLine.purchase_id == Purchase.id)
            .where(
                Purchase.organization_id == organization_id,
                Purchase.status == "liquidated",
                Purchase.liquidated_at >= dt_from,
                Purchase.liquidated_at < dt_to,
            )
            .group_by(Purchase.supplier_id, ThirdParty.name)
            .order_by(func.sum(PurchaseLine.unit_price * PurchaseLine.quantity).desc())
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
                func.coalesce(func.sum(SaleLine.unit_price * SaleLine.quantity), 0),
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
                Sale.liquidated_at >= dt_from,
                Sale.liquidated_at < dt_to,
            )
            .group_by(Sale.customer_id, ThirdParty.name)
            .order_by(func.sum(SaleLine.unit_price * SaleLine.quantity).desc())
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
                self._tp_has_behavior("customer"),
                ThirdParty.current_balance > 0,
            )
        ))
        total_payable = float(db.scalar(
            select(func.coalesce(func.sum(func.abs(ThirdParty.current_balance)), 0))
            .where(
                ThirdParty.organization_id == organization_id,
                self._tp_has_behavior("material_supplier", "service_provider", "liability"),
                ThirdParty.current_balance < 0,
            )
        ))

        # 3. Provisiones
        prov_rows = db.execute(
            select(ThirdParty.id, ThirdParty.name, ThirdParty.provision_type, ThirdParty.current_balance)
            .where(
                ThirdParty.organization_id == organization_id,
                self._tp_has_behavior("provision"),
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

        tp_behaviors, _, _ = self._load_tp_behavior_map(db, organization_id)

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

        # 2b. Compras canceladas post-liquidacion: neto es 0
        # (step 2a ya las excluye porque status != 'liquidated', asi que no sumar)

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

        # 2d. Ventas canceladas post-liquidacion: neto es 0
        # (step 2c ya las excluye porque status != 'liquidated', asi que no restar)

        # 2e. Comisiones: capturadas via commission_accrual MoneyMovement en paso siguiente
        # (no contar SaleCommission directamente para evitar doble conteo)

        # 2e2. Comisiones de compra (PurchaseCommission): no crean MoneyMovement,
        # actualizan third_party.balance directamente al liquidar la compra.
        # Solo compras liquidadas (canceladas revierten el saldo).
        pc_rows = db.execute(
            select(
                PurchaseCommission.third_party_id,
                func.coalesce(func.sum(PurchaseCommission.commission_amount), 0),
            )
            .join(Purchase, Purchase.id == PurchaseCommission.purchase_id)
            .where(
                Purchase.organization_id == organization_id,
                Purchase.status == "liquidated",
            )
            .group_by(PurchaseCommission.third_party_id)
        ).all()
        for tp_id, total in pc_rows:
            _add(tp_id, -Decimal(str(total)))  # commission_amount reduce el saldo (les debemos)

        # 2f. MoneyMovements confirmados con third_party_id
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

            behaviors = tp_behaviors.get(tp.id, set())
            roles = list(behaviors) if behaviors else []

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


    # ==================================================================
    # Tipos de movimiento que son gastos P&L (para reportes por UN)
    # ==================================================================
    EXPENSE_MOVEMENT_TYPES = [
        "expense", "provision_expense", "expense_accrual",
        "deferred_expense", "depreciation_expense",
    ]

    # ==================================================================
    # Rentabilidad por Unidad de Negocio
    # ==================================================================

    def _get_purchases_by_bu(
        self, db: Session, organization_id: UUID,
        dt_from: datetime, dt_to: datetime,
    ) -> dict[str, Decimal]:
        """Valor de compras liquidadas por business_unit_id del material.
        Retorna {bu_id_str: total_value}. Materiales sin UN van a key 'unassigned'.
        """
        rows = db.execute(
            select(
                Material.business_unit_id,
                func.coalesce(func.sum(PurchaseLine.total_price), 0),
            )
            .select_from(PurchaseLine)
            .join(Purchase, PurchaseLine.purchase_id == Purchase.id)
            .join(Material, PurchaseLine.material_id == Material.id)
            .where(
                Purchase.organization_id == organization_id,
                Purchase.status == "liquidated",
                Purchase.double_entry_id.is_(None),
                Purchase.liquidated_at >= dt_from,
                Purchase.liquidated_at < dt_to,
            )
            .group_by(Material.business_unit_id)
        ).all()
        result: dict[str, Decimal] = {}
        for bu_id, total in rows:
            key = str(bu_id) if bu_id else "unassigned"
            result[key] = Decimal(str(total))
        return result

    def _get_kg_purchased_by_bu(
        self, db: Session, organization_id: UUID,
        dt_from: datetime, dt_to: datetime,
    ) -> dict[str, Decimal]:
        """Kg comprados liquidados por UN del material."""
        rows = db.execute(
            select(
                Material.business_unit_id,
                func.coalesce(func.sum(PurchaseLine.quantity), 0),
            )
            .select_from(PurchaseLine)
            .join(Purchase, PurchaseLine.purchase_id == Purchase.id)
            .join(Material, PurchaseLine.material_id == Material.id)
            .where(
                Purchase.organization_id == organization_id,
                Purchase.status == "liquidated",
                Purchase.double_entry_id.is_(None),
                Purchase.liquidated_at >= dt_from,
                Purchase.liquidated_at < dt_to,
            )
            .group_by(Material.business_unit_id)
        ).all()
        result: dict[str, Decimal] = {}
        for bu_id, total in rows:
            key = str(bu_id) if bu_id else "unassigned"
            result[key] = Decimal(str(total))
        return result

    def _prorate_expense(
        self, amount: Decimal,
        applicable_bu_ids: list[str] | None,
        purchases_by_bu: dict[str, Decimal],
    ) -> dict[str, Decimal]:
        """Prorratear un gasto entre UNs segun valor de compras.
        applicable_bu_ids=None -> General (todas las UNs).
        """
        if applicable_bu_ids:
            target_bus = applicable_bu_ids
        else:
            target_bus = list(purchases_by_bu.keys())

        total_purchases = sum(purchases_by_bu.get(bu, Decimal("0")) for bu in target_bus)
        if total_purchases == 0:
            return {}

        result: dict[str, Decimal] = {}
        for bu in target_bus:
            bu_purchases = purchases_by_bu.get(bu, Decimal("0"))
            if bu_purchases > 0:
                result[bu] = amount * (bu_purchases / total_purchases)
        return result

    def get_profitability_by_business_unit(
        self, db: Session, organization_id: UUID,
        date_from: date, date_to: date,
    ) -> ProfitabilityByBUResponse:
        """Reporte de rentabilidad por Unidad de Negocio (SOLO bodega).

        Doble partida se analiza aparte en la seccion `double_entry` con logica
        propia: margen bruto + comisiones DP + gastos directos a la UN sistema.
        Ver plan-rentabilidad-un-pasamano.md.
        """
        dt_from, dt_to = self._date_range(date_from, date_to)

        # 1. Obtener UNs activas.
        # La UN de sistema (Pasa Mano) se EXCLUYE de la tabla bodega — sus
        # gastos directos van a la seccion double_entry.
        # ⚠️ Esta exclusion va SOLO aca, NUNCA en _compute_expense_allocations
        # (el Reporte de Gastos DEBE mostrar la UN Pasa Mano como grupo).
        bus = db.execute(
            select(BusinessUnit.id, BusinessUnit.name, BusinessUnit.system_code)
            .where(
                BusinessUnit.organization_id == organization_id,
                BusinessUnit.is_active == True,
            )
            .order_by(BusinessUnit.name)
        ).all()
        system_bu_id: Optional[str] = None
        system_bu_name = "Pasa Mano"
        for bu in bus:
            if bu.system_code == "double_entry":
                system_bu_id = str(bu.id)
                system_bu_name = bu.name
                break
        bu_names = {str(bu.id): bu.name for bu in bus if not bu.system_code}
        all_bu_keys = list(bu_names.keys()) + ["unassigned"]

        # 2. Compras por UN (base para prorrateo)
        purchases_by_bu = self._get_purchases_by_bu(db, organization_id, dt_from, dt_to)

        total_purchases_all = sum(purchases_by_bu.values())

        # 3. Ingresos y COGS de ventas por UN
        sale_filters = [
            Sale.organization_id == organization_id,
            Sale.status == "liquidated",
            Sale.double_entry_id.is_(None),
            Sale.liquidated_at >= dt_from,
            Sale.liquidated_at < dt_to,
        ]
        sale_rows = db.execute(
            select(
                Material.business_unit_id,
                func.coalesce(func.sum(SaleLine.total_price), 0),
                func.coalesce(func.sum(SaleLine.unit_cost * SaleLine.quantity), 0),
            )
            .select_from(SaleLine)
            .join(Sale, SaleLine.sale_id == Sale.id)
            .join(Material, SaleLine.material_id == Material.id)
            .where(*sale_filters)
            .group_by(Material.business_unit_id)
        ).all()
        revenue_by_bu: dict[str, Decimal] = {}
        cogs_by_bu: dict[str, Decimal] = {}
        for bu_id, revenue, cogs in sale_rows:
            key = str(bu_id) if bu_id else "unassigned"
            revenue_by_bu[key] = Decimal(str(revenue))
            cogs_by_bu[key] = Decimal(str(cogs))

        # 4. Totales de Doble Partida (seccion Pasa Mano — NO entra a las filas por UN).
        # ⚠️ NO confundir con el `de_profit` local de _calculate_profit (P&L):
        # ese es otro calculo con el mismo nombre y NO se toca.
        de_filters = [
            DoubleEntry.organization_id == organization_id,
            DoubleEntry.status == "liquidated",
            DoubleEntry.liquidated_at >= dt_from,
            DoubleEntry.liquidated_at < dt_to,
        ]
        de_row = db.execute(
            select(
                func.coalesce(
                    func.sum(DoubleEntryLine.sale_unit_price * DoubleEntryLine.quantity), 0
                ),
                func.coalesce(
                    func.sum(DoubleEntryLine.purchase_unit_price * DoubleEntryLine.quantity), 0
                ),
            )
            .select_from(DoubleEntryLine)
            .join(DoubleEntry, DoubleEntryLine.double_entry_id == DoubleEntry.id)
            .where(*de_filters)
        ).one()
        de_sales_total = Decimal(str(de_row[0]))
        de_purchases_total = Decimal(str(de_row[1]))
        de_gross_profit = de_sales_total - de_purchases_total

        # 5. Gastos P&L por tipo de asignacion
        expense_filters = [
            MoneyMovement.organization_id == organization_id,
            MoneyMovement.status == "confirmed",
            MoneyMovement.movement_type.in_(self.EXPENSE_MOVEMENT_TYPES),
            MoneyMovement.date >= dt_from,
            MoneyMovement.date < dt_to,
        ]
        expense_rows = db.execute(
            select(
                MoneyMovement.id,
                MoneyMovement.amount,
                MoneyMovement.business_unit_id,
                MoneyMovement.applicable_business_unit_ids,
                MoneyMovement.expense_category_id,
                ExpenseCategory.name.label("cat_name"),
                ExpenseCategory.is_direct_expense,
            )
            .outerjoin(ExpenseCategory, MoneyMovement.expense_category_id == ExpenseCategory.id)
            .where(*expense_filters)
        ).all()

        # Acumuladores por UN
        direct_by_bu: dict[str, Decimal] = {k: Decimal("0") for k in all_bu_keys}
        shared_by_bu: dict[str, Decimal] = {k: Decimal("0") for k in all_bu_keys}
        general_by_bu: dict[str, Decimal] = {k: Decimal("0") for k in all_bu_keys}
        # Desglose directo por categoria
        direct_detail: dict[str, dict[str, Decimal]] = {k: {} for k in all_bu_keys}
        # Acumuladores Pasa Mano (gastos directos a la UN sistema)
        pasamano_direct = Decimal("0")
        pasamano_direct_detail: dict[str, Decimal] = {}

        for row in expense_rows:
            amt = Decimal(str(row.amount))
            bu_id = str(row.business_unit_id) if row.business_unit_id else None
            applicable = row.applicable_business_unit_ids  # JSONB: list of UUID strings or None

            if bu_id:
                # DIRECTO a la UN sistema -> seccion Pasa Mano.
                # ⚠️ Sin este branch caeria en "unassigned" (la UN sistema no
                # esta en bu_names) — punto fragil marcado por QA en el plan.
                if system_bu_id and bu_id == system_bu_id:
                    pasamano_direct += amt
                    cat_name = row.cat_name or "Sin Categoría"
                    pasamano_direct_detail[cat_name] = (
                        pasamano_direct_detail.get(cat_name, Decimal("0")) + amt
                    )
                    continue
                # DIRECTO: 100% a esta UN
                key = bu_id if bu_id in bu_names else "unassigned"
                direct_by_bu[key] = direct_by_bu.get(key, Decimal("0")) + amt
                cat_name = row.cat_name or "Sin Categoría"
                if key not in direct_detail:
                    direct_detail[key] = {}
                direct_detail[key][cat_name] = direct_detail[key].get(cat_name, Decimal("0")) + amt
            elif applicable:
                # COMPARTIDO: prorrateo entre UNs especificas
                prorated = self._prorate_expense(amt, applicable, purchases_by_bu)
                for k, v in prorated.items():
                    shared_by_bu[k] = shared_by_bu.get(k, Decimal("0")) + v
            else:
                # GENERAL: ambos NULL
                # Movimientos historicos: si is_direct_expense=True y sin UN -> "Sin Asignar"
                if row.is_direct_expense and row.business_unit_id is None:
                    direct_by_bu["unassigned"] = direct_by_bu.get("unassigned", Decimal("0")) + amt
                    cat_name = row.cat_name or "Sin Categoría"
                    if "unassigned" not in direct_detail:
                        direct_detail["unassigned"] = {}
                    direct_detail["unassigned"][cat_name] = direct_detail["unassigned"].get(cat_name, Decimal("0")) + amt
                else:
                    prorated = self._prorate_expense(amt, None, purchases_by_bu)
                    for k, v in prorated.items():
                        general_by_bu[k] = general_by_bu.get(k, Decimal("0")) + v

        # 6. Comisiones de venta por UN (prorrateo por valor de linea).
        # Split bodega vs DP: las comisiones de ventas con double_entry_id van a
        # la seccion Pasa Mano — antes contaminaban las UN de bodega (fuga #2
        # del plan: ~$48M de comisiones pasamano caian en "Chatarra").
        commission_rows = db.execute(
            select(
                MoneyMovement.sale_id,
                MoneyMovement.amount,
                Sale.double_entry_id,
            )
            .join(Sale, MoneyMovement.sale_id == Sale.id)
            .where(
                MoneyMovement.organization_id == organization_id,
                MoneyMovement.status == "confirmed",
                MoneyMovement.movement_type == "commission_accrual",
                MoneyMovement.sale_id.isnot(None),
                MoneyMovement.date >= dt_from,
                MoneyMovement.date < dt_to,
            )
        ).all()

        commissions_by_bu: dict[str, Decimal] = {k: Decimal("0") for k in all_bu_keys}
        pasamano_commissions = Decimal("0")
        if commission_rows:
            # Agrupar comisiones por sale_id (solo bodega; DP va al total pasamano)
            sale_commissions: dict[UUID, Decimal] = {}
            sale_ids_set: set[UUID] = set()
            for sale_id, comm_amt, de_id in commission_rows:
                if de_id is not None:
                    pasamano_commissions += Decimal(str(comm_amt))
                    continue
                sale_commissions[sale_id] = sale_commissions.get(sale_id, Decimal("0")) + Decimal(str(comm_amt))
                sale_ids_set.add(sale_id)

            # Obtener lineas de esas ventas con UN del material
            if sale_ids_set:
                line_rows = db.execute(
                    select(
                        SaleLine.sale_id,
                        Material.business_unit_id,
                        func.coalesce(func.sum(SaleLine.total_price), 0),
                    )
                    .select_from(SaleLine)
                    .join(Material, SaleLine.material_id == Material.id)
                    .where(SaleLine.sale_id.in_(sale_ids_set))
                    .group_by(SaleLine.sale_id, Material.business_unit_id)
                ).all()

                # Construir mapa sale_id -> [(bu_key, value)]
                sale_lines_map: dict[UUID, list[tuple[str, Decimal]]] = {}
                for sale_id, bu_id, line_total in line_rows:
                    key = str(bu_id) if bu_id else "unassigned"
                    if sale_id not in sale_lines_map:
                        sale_lines_map[sale_id] = []
                    sale_lines_map[sale_id].append((key, Decimal(str(line_total))))

                # Prorratear cada comision
                for sale_id, total_comm in sale_commissions.items():
                    lines = sale_lines_map.get(sale_id, [])
                    total_sale = sum(v for _, v in lines)
                    if total_sale > 0:
                        for bu_key, line_val in lines:
                            peso = line_val / total_sale
                            commissions_by_bu[bu_key] = commissions_by_bu.get(bu_key, Decimal("0")) + total_comm * peso

        # 7. Construir resultado por UN
        result_bus: list[BusinessUnitProfitability] = []
        totals = BusinessUnitProfitability(
            business_unit_name="TOTAL",
        )

        for bu_key in all_bu_keys:
            bu_name = bu_names.get(bu_key, "Sin Asignar")
            revenue = revenue_by_bu.get(bu_key, Decimal("0"))
            cogs = cogs_by_bu.get(bu_key, Decimal("0"))
            # Sin DP: utilidad bruta de la UN = solo operacion de bodega
            gross_profit = revenue - cogs

            direct = direct_by_bu.get(bu_key, Decimal("0"))
            shared = shared_by_bu.get(bu_key, Decimal("0"))
            general = general_by_bu.get(bu_key, Decimal("0"))
            comms = commissions_by_bu.get(bu_key, Decimal("0"))
            total_exp = direct + shared + general + comms
            net = gross_profit - total_exp
            margin = self._safe_pct(net, revenue) if revenue > 0 else 0.0

            # Desglose directo
            detail = [
                ExpenseByCategoryItem(
                    category_name=cat, amount=float(val)
                )
                for cat, val in sorted(
                    direct_detail.get(bu_key, {}).items(),
                    key=lambda x: -x[1],
                )
                if val != 0
            ]

            # Solo incluir si tiene alguna actividad
            has_activity = any([revenue, cogs, direct, shared, general, comms])
            if not has_activity:
                continue

            bu_purchases = purchases_by_bu.get(bu_key, Decimal("0"))
            bu_weight = self._safe_pct(bu_purchases, total_purchases_all) if total_purchases_all > 0 else 0.0

            bu_item = BusinessUnitProfitability(
                business_unit_id=bu_key if bu_key != "unassigned" else None,
                business_unit_name=bu_name,
                purchases_total=float(bu_purchases),
                purchases_weight_pct=bu_weight,
                sales_revenue=float(revenue),
                sales_cogs=float(cogs),
                sales_gross_profit=float(revenue - cogs),
                total_gross_profit=float(gross_profit),
                direct_expenses=float(direct),
                shared_expenses=float(shared),
                general_expenses=float(general),
                sale_commissions=float(comms),
                total_expenses=float(total_exp),
                direct_expenses_detail=detail,
                net_profit=float(net),
                net_margin=margin,
            )
            result_bus.append(bu_item)

            # Acumular totales
            totals.purchases_total += float(bu_purchases)
            totals.sales_revenue += float(revenue)
            totals.sales_cogs += float(cogs)
            totals.sales_gross_profit += float(revenue - cogs)
            totals.total_gross_profit += float(gross_profit)
            totals.direct_expenses += float(direct)
            totals.shared_expenses += float(shared)
            totals.general_expenses += float(general)
            totals.sale_commissions += float(comms)
            totals.total_expenses += float(total_exp)
            totals.net_profit += float(net)

        totals.purchases_weight_pct = 100.0
        if totals.sales_revenue > 0:
            totals.net_margin = self._safe_pct(
                Decimal(str(totals.net_profit)),
                Decimal(str(totals.sales_revenue)),
            )

        # 8. Seccion Pasa Mano: margen DP + comisiones DP + gastos directos a
        # la UN sistema. Sin prorrateo de generales (decision del cliente).
        pasamano_detail = [
            ExpenseByCategoryItem(category_name=cat, amount=float(val))
            for cat, val in sorted(pasamano_direct_detail.items(), key=lambda x: -x[1])
            if val != 0
        ]
        pasamano_net = de_gross_profit - pasamano_commissions - pasamano_direct
        double_entry_section = DoubleEntryProfitability(
            business_unit_id=system_bu_id,
            label=system_bu_name,
            sales_total=float(de_sales_total),
            purchases_total=float(de_purchases_total),
            gross_profit=float(de_gross_profit),
            commissions=float(pasamano_commissions),
            direct_expenses=float(pasamano_direct),
            direct_expenses_detail=pasamano_detail,
            net_profit=float(pasamano_net),
            net_margin=(
                self._safe_pct(pasamano_net, de_sales_total)
                if de_sales_total > 0 else 0.0
            ),
        )

        return ProfitabilityByBUResponse(
            period_from=date_from,
            period_to=date_to,
            business_units=result_bus,
            totals=totals,
            double_entry=double_entry_section,
            grand_total_net=totals.net_profit + float(pasamano_net),
        )

    # ==================================================================
    # Costo Real por Material
    # ==================================================================

    def get_real_cost_by_material(
        self, db: Session, organization_id: UUID,
        date_from: date, date_to: date,
    ) -> RealCostByMaterialResponse:
        """Reporte de costo real por material = costo promedio + overhead rate."""
        dt_from, dt_to = self._date_range(date_from, date_to)

        # 1. UNs activas.
        # La UN de sistema (Pasa Mano) se excluye: sus gastos directos son costo
        # de doble partida, NO overhead de material. Sin este skip, generaria
        # una fila fantasma (gastos > 0, kg = 0, sin materiales) o — peor — sus
        # gastos caerian en "Sin Asignar".
        bus = db.execute(
            select(BusinessUnit.id, BusinessUnit.name, BusinessUnit.system_code)
            .where(
                BusinessUnit.organization_id == organization_id,
                BusinessUnit.is_active == True,
            )
            .order_by(BusinessUnit.name)
        ).all()
        system_bu_id: Optional[str] = next(
            (str(bu.id) for bu in bus if bu.system_code == "double_entry"), None
        )
        bu_names = {str(bu.id): bu.name for bu in bus if not bu.system_code}
        all_bu_keys = list(bu_names.keys()) + ["unassigned"]

        # 2. Compras por UN (valor + kg)
        purchases_by_bu = self._get_purchases_by_bu(db, organization_id, dt_from, dt_to)
        kg_by_bu = self._get_kg_purchased_by_bu(db, organization_id, dt_from, dt_to)

        # 3. Gastos P&L — misma logica que profitability
        expense_filters = [
            MoneyMovement.organization_id == organization_id,
            MoneyMovement.status == "confirmed",
            MoneyMovement.movement_type.in_(self.EXPENSE_MOVEMENT_TYPES),
            MoneyMovement.date >= dt_from,
            MoneyMovement.date < dt_to,
        ]
        expense_rows = db.execute(
            select(
                MoneyMovement.amount,
                MoneyMovement.business_unit_id,
                MoneyMovement.applicable_business_unit_ids,
                ExpenseCategory.is_direct_expense,
            )
            .outerjoin(ExpenseCategory, MoneyMovement.expense_category_id == ExpenseCategory.id)
            .where(*expense_filters)
        ).all()

        total_expenses_by_bu: dict[str, Decimal] = {k: Decimal("0") for k in all_bu_keys}

        for row in expense_rows:
            amt = Decimal(str(row.amount))
            bu_id = str(row.business_unit_id) if row.business_unit_id else None
            applicable = row.applicable_business_unit_ids

            if bu_id:
                # Gasto directo a la UN sistema (Pasa Mano): costo de doble
                # partida, no overhead de material — fuera de este reporte.
                if system_bu_id and bu_id == system_bu_id:
                    continue
                key = bu_id if bu_id in bu_names else "unassigned"
                total_expenses_by_bu[key] = total_expenses_by_bu.get(key, Decimal("0")) + amt
            elif applicable:
                prorated = self._prorate_expense(amt, applicable, purchases_by_bu)
                for k, v in prorated.items():
                    total_expenses_by_bu[k] = total_expenses_by_bu.get(k, Decimal("0")) + v
            else:
                if row.is_direct_expense and row.business_unit_id is None:
                    total_expenses_by_bu["unassigned"] = total_expenses_by_bu.get("unassigned", Decimal("0")) + amt
                else:
                    prorated = self._prorate_expense(amt, None, purchases_by_bu)
                    for k, v in prorated.items():
                        total_expenses_by_bu[k] = total_expenses_by_bu.get(k, Decimal("0")) + v

        # 4. Materiales activos con costo promedio
        material_rows = db.execute(
            select(
                Material.id,
                Material.code,
                Material.name,
                Material.current_average_cost,
                Material.business_unit_id,
            )
            .where(
                Material.organization_id == organization_id,
                Material.is_active == True,
            )
            .order_by(Material.code)
        ).all()

        # 5. Construir resultado por UN
        result_bus: list[BusinessUnitOverhead] = []

        for bu_key in all_bu_keys:
            bu_name = bu_names.get(bu_key, "Sin Asignar")
            total_exp = total_expenses_by_bu.get(bu_key, Decimal("0"))
            kg = kg_by_bu.get(bu_key, Decimal("0"))
            overhead_rate = (total_exp / kg) if kg > 0 else Decimal("0")

            # Materiales de esta UN
            materials: list[MaterialRealCost] = []
            for m in material_rows:
                m_bu_key = str(m.business_unit_id) if m.business_unit_id else "unassigned"
                if m_bu_key != bu_key:
                    continue
                avg_cost = Decimal(str(m.current_average_cost))
                real_cost = avg_cost + overhead_rate
                materials.append(MaterialRealCost(
                    material_id=str(m.id),
                    material_code=m.code,
                    material_name=m.name,
                    average_cost=float(avg_cost),
                    overhead_rate=float(overhead_rate),
                    real_cost=float(real_cost),
                ))

            if not materials and total_exp == 0:
                continue

            result_bus.append(BusinessUnitOverhead(
                business_unit_id=bu_key if bu_key != "unassigned" else None,
                business_unit_name=bu_name,
                total_expenses=float(total_exp),
                kg_purchased=float(kg),
                overhead_rate=float(overhead_rate),
                materials=materials,
            ))

        return RealCostByMaterialResponse(
            period_from=date_from,
            period_to=date_to,
            business_units=result_bus,
        )

    # ==================================================================
    # Reporte de Gastos (agrupacion flexible por UN/Categoria)
    # ==================================================================

    def _expand_categories_to_children(
        self, db: Session, organization_id: UUID, category_ids: list[UUID],
    ) -> set[UUID]:
        """Expandir categoria padre a {padre} ∪ {hijas}.

        Si una categoria tiene parent_id=NULL y otras categorias la referencian
        como parent, se incluyen todas. Consistente con la jerarquia de 2 niveles.
        """
        if not category_ids:
            return set()
        result: set[UUID] = set(category_ids)
        children = db.execute(
            select(ExpenseCategory.id).where(
                ExpenseCategory.organization_id == organization_id,
                ExpenseCategory.parent_id.in_(category_ids),
            )
        ).all()
        for (child_id,) in children:
            result.add(child_id)
        return result

    def _compute_expense_allocations(
        self, db: Session, organization_id: UUID, dt_from: datetime, dt_to: datetime,
    ) -> tuple[list[dict], dict[str, str], dict[str, dict]]:
        """Calcular alocaciones (mov_id, bu_id, cat_id, allocated_amount, allocation_type)
        para todos los gastos del periodo, replicando la logica 3-tier de
        get_profitability_by_business_unit.

        ⚠️ NO "sincronizar" con profitability: aca la UN de sistema (Pasa Mano)
        SI se incluye en bu_names — el Reporte de Gastos DEBE mostrarla como
        grupo con sus gastos directos. La exclusion de la UN sistema aplica
        SOLO en get_profitability_by_business_unit y get_real_cost_by_material.

        Returns:
            (allocations, bu_names, cat_info)
            - allocations: lista de dicts con keys: movement_id, bu_id (str|None),
              cat_id (UUID|None), parent_cat_id (UUID|None), cat_name (str),
              amount (Decimal), allocation_type (direct|shared|general),
              source_movement_id (UUID).
            - bu_names: {bu_id_str: name} incluyendo "unassigned"
            - cat_info: {cat_id_str: {"name", "parent_id", "is_direct_expense"}} y
              key especial "none" para "Sin Categoría".
        """
        # 1. UNs activas
        bus = db.execute(
            select(BusinessUnit.id, BusinessUnit.name)
            .where(
                BusinessUnit.organization_id == organization_id,
                BusinessUnit.is_active == True,
            )
            .order_by(BusinessUnit.name)
        ).all()
        bu_names: dict[str, str] = {str(bu.id): bu.name for bu in bus}
        bu_names["unassigned"] = "Sin Asignar"

        # 2. Compras por UN (base prorrateo)
        purchases_by_bu = self._get_purchases_by_bu(db, organization_id, dt_from, dt_to)

        # 3. Categorias (incluye parent_id para jerarquia)
        cat_rows = db.execute(
            select(
                ExpenseCategory.id,
                ExpenseCategory.name,
                ExpenseCategory.parent_id,
                ExpenseCategory.is_direct_expense,
            ).where(ExpenseCategory.organization_id == organization_id)
        ).all()
        cat_info: dict[str, dict] = {}
        for cat in cat_rows:
            cat_info[str(cat.id)] = {
                "name": cat.name,
                "parent_id": str(cat.parent_id) if cat.parent_id else None,
                "is_direct_expense": cat.is_direct_expense,
            }
        cat_info["none"] = {"name": "Sin Categoría", "parent_id": None, "is_direct_expense": False}

        # 4. Movimientos de gasto del periodo
        expense_filters = [
            MoneyMovement.organization_id == organization_id,
            MoneyMovement.status == "confirmed",
            MoneyMovement.movement_type.in_(self.EXPENSE_MOVEMENT_TYPES),
            MoneyMovement.date >= dt_from,
            MoneyMovement.date < dt_to,
        ]
        rows = db.execute(
            select(
                MoneyMovement.id,
                MoneyMovement.amount,
                MoneyMovement.business_unit_id,
                MoneyMovement.applicable_business_unit_ids,
                MoneyMovement.expense_category_id,
                ExpenseCategory.is_direct_expense,
            )
            .outerjoin(ExpenseCategory, MoneyMovement.expense_category_id == ExpenseCategory.id)
            .where(*expense_filters)
        ).all()

        allocations: list[dict] = []
        for row in rows:
            amt = Decimal(str(row.amount))
            bu_id_str = str(row.business_unit_id) if row.business_unit_id else None
            applicable = row.applicable_business_unit_ids
            cat_id_str = str(row.expense_category_id) if row.expense_category_id else "none"
            cat_meta = cat_info.get(cat_id_str, cat_info["none"])
            parent_cat_id = cat_meta["parent_id"]
            cat_name = cat_meta["name"]

            base = {
                "movement_id": row.id,
                "cat_id": cat_id_str,
                "parent_cat_id": parent_cat_id,
                "cat_name": cat_name,
            }

            if bu_id_str:
                # DIRECTO: 100% a esta UN
                key = bu_id_str if bu_id_str in bu_names else "unassigned"
                allocations.append({
                    **base,
                    "bu_id": key,
                    "allocated_amount": amt,
                    "allocation_type": "direct",
                })
            elif applicable:
                # COMPARTIDO: prorrateo entre UNs especificas
                prorated = self._prorate_expense(amt, applicable, purchases_by_bu)
                for k, v in prorated.items():
                    allocations.append({
                        **base,
                        "bu_id": k,
                        "allocated_amount": v,
                        "allocation_type": "shared",
                    })
            else:
                # GENERAL: ambos NULL.
                # Edge case legacy: is_direct_expense=True + UN NULL -> "unassigned" directo
                # (replica logica de get_profitability_by_business_unit:3216-3222)
                if row.is_direct_expense:
                    allocations.append({
                        **base,
                        "bu_id": "unassigned",
                        "allocated_amount": amt,
                        "allocation_type": "direct",
                    })
                else:
                    prorated = self._prorate_expense(amt, None, purchases_by_bu)
                    for k, v in prorated.items():
                        allocations.append({
                            **base,
                            "bu_id": k,
                            "allocated_amount": v,
                            "allocation_type": "general",
                        })

        return allocations, bu_names, cat_info

    def get_expenses_report(
        self,
        db: Session,
        organization_id: UUID,
        date_from: date,
        date_to: date,
        group_by: str = "bu_then_category",
        business_unit_ids: Optional[list[UUID]] = None,
        category_ids: Optional[list[UUID]] = None,
    ) -> ExpensesReportResponse:
        """Reporte de gastos con agrupacion flexible por UN/Categoria.

        group_by: "bu" | "category" | "bu_then_category" | "category_then_bu"
        """
        dt_from, dt_to = self._date_range(date_from, date_to)

        allocations, bu_names, cat_info = self._compute_expense_allocations(
            db, organization_id, dt_from, dt_to
        )

        # Filtrar alocaciones segun UI (post-calculo de prorrateo)
        bu_filter_set: Optional[set[str]] = None
        if business_unit_ids:
            bu_filter_set = {str(b) for b in business_unit_ids}

        cat_filter_set: Optional[set[str]] = None
        if category_ids:
            expanded = self._expand_categories_to_children(
                db, organization_id, category_ids
            )
            cat_filter_set = {str(c) for c in expanded}

        if bu_filter_set or cat_filter_set:
            allocations = [
                a for a in allocations
                if (bu_filter_set is None or a["bu_id"] in bu_filter_set)
                and (cat_filter_set is None or a["cat_id"] in cat_filter_set)
            ]

        # Stats agregadas (sobre el set ya filtrado)
        total_global = Decimal("0")
        total_direct = Decimal("0")
        total_shared = Decimal("0")
        total_general = Decimal("0")
        for a in allocations:
            amt = a["allocated_amount"]
            total_global += amt
            atype = a["allocation_type"]
            if atype == "direct":
                total_direct += amt
            elif atype == "shared":
                total_shared += amt
            elif atype == "general":
                total_general += amt
        movement_count = len({a["movement_id"] for a in allocations})

        # Construir arbol segun group_by
        groups = self._build_expense_tree(allocations, group_by, bu_names, cat_info)

        return ExpensesReportResponse(
            period_from=date_from,
            period_to=date_to,
            group_by=group_by,
            total=float(total_global),
            total_direct=float(total_direct),
            total_shared=float(total_shared),
            total_general=float(total_general),
            movement_count=movement_count,
            groups=groups,
        )

    def _build_expense_tree(
        self,
        allocations: list[dict],
        group_by: str,
        bu_names: dict[str, str],
        cat_info: dict[str, dict],
    ) -> list[ExpenseGroupNode]:
        """Construir arbol jerarquico segun el modo de agrupacion."""

        if group_by == "none":
            return []

        def cat_node_builder(allocs: list[dict], level: int) -> list[ExpenseGroupNode]:
            """Construir nodos de categoria con jerarquia padre/hijo."""
            # Indexar alocaciones por cat_id (hoja)
            by_cat: dict[str, list[dict]] = {}
            for a in allocs:
                by_cat.setdefault(a["cat_id"], []).append(a)

            # Agrupar por padre (cat con parent → hijo bajo padre; cat sin parent → top)
            top_level: dict[str, dict] = {}
            for cat_id, items in by_cat.items():
                meta = cat_info.get(cat_id, cat_info["none"])
                parent_id = meta["parent_id"]
                if parent_id and parent_id in cat_info:
                    parent_node = top_level.setdefault(parent_id, {
                        "name": cat_info[parent_id]["name"],
                        "children_by_cat": {},
                        "direct_items": [],
                    })
                    parent_node["children_by_cat"][cat_id] = items
                else:
                    parent_node = top_level.setdefault(cat_id, {
                        "name": meta["name"],
                        "children_by_cat": {},
                        "direct_items": [],
                    })
                    parent_node["direct_items"].extend(items)

            result: list[ExpenseGroupNode] = []
            for cat_id, info in top_level.items():
                child_nodes: list[ExpenseGroupNode] = []
                # Items directos del padre (si la cat se uso como hoja sin parent)
                node_total = sum(
                    (a["allocated_amount"] for a in info["direct_items"]),
                    Decimal("0"),
                )
                node_has_shared = any(
                    a["allocation_type"] != "direct" for a in info["direct_items"]
                )
                # Hijos
                for child_cat_id, child_items in info["children_by_cat"].items():
                    child_total = sum(
                        (a["allocated_amount"] for a in child_items),
                        Decimal("0"),
                    )
                    child_has_shared = any(
                        a["allocation_type"] != "direct" for a in child_items
                    )
                    child_nodes.append(ExpenseGroupNode(
                        key=f"cat:{child_cat_id}",
                        label=cat_info[child_cat_id]["name"],
                        level=level + 1,
                        category_id=UUID(child_cat_id) if child_cat_id != "none" else None,
                        parent_category_id=UUID(cat_id) if cat_id != "none" else None,
                        total=float(child_total),
                        has_shared_allocations=child_has_shared,
                    ))
                    node_total += child_total
                    node_has_shared = node_has_shared or child_has_shared

                child_nodes.sort(key=lambda n: -n.total)
                result.append(ExpenseGroupNode(
                    key=f"cat:{cat_id}",
                    label=info["name"],
                    level=level,
                    category_id=UUID(cat_id) if cat_id != "none" else None,
                    total=float(node_total),
                    has_shared_allocations=node_has_shared,
                    children=child_nodes,
                ))
            result.sort(key=lambda n: -n.total)
            return result

        if group_by == "bu":
            by_bu: dict[str, list[dict]] = {}
            for a in allocations:
                by_bu.setdefault(a["bu_id"], []).append(a)
            nodes: list[ExpenseGroupNode] = []
            for bu_key, items in by_bu.items():
                total = sum((a["allocated_amount"] for a in items), Decimal("0"))
                has_shared = any(a["allocation_type"] != "direct" for a in items)
                nodes.append(ExpenseGroupNode(
                    key=f"bu:{bu_key}",
                    label=bu_names.get(bu_key, "Sin Asignar"),
                    level=0,
                    business_unit_id=UUID(bu_key) if bu_key != "unassigned" else None,
                    total=float(total),
                    has_shared_allocations=has_shared,
                ))
            nodes.sort(key=lambda n: -n.total)
            return nodes

        if group_by == "category":
            return cat_node_builder(allocations, level=0)

        if group_by == "bu_then_category":
            by_bu: dict[str, list[dict]] = {}
            for a in allocations:
                by_bu.setdefault(a["bu_id"], []).append(a)
            nodes: list[ExpenseGroupNode] = []
            for bu_key, items in by_bu.items():
                total = sum((a["allocated_amount"] for a in items), Decimal("0"))
                has_shared = any(a["allocation_type"] != "direct" for a in items)
                cat_children = cat_node_builder(items, level=1)
                nodes.append(ExpenseGroupNode(
                    key=f"bu:{bu_key}",
                    label=bu_names.get(bu_key, "Sin Asignar"),
                    level=0,
                    business_unit_id=UUID(bu_key) if bu_key != "unassigned" else None,
                    total=float(total),
                    has_shared_allocations=has_shared,
                    children=cat_children,
                ))
            nodes.sort(key=lambda n: -n.total)
            return nodes

        if group_by == "category_then_bu":
            # Primero arbol de categorias; dentro de cada categoria/subcategoria, sub-nodos por UN.
            cat_nodes = cat_node_builder(allocations, level=0)

            # Para cada nodo (top y children), reemplazar children por UN-breakdown
            # Si el nodo top tiene children-categorias, agregamos children dentro de cada hijo
            def add_bu_children(node: ExpenseGroupNode, items_for_node: list[dict], level: int):
                by_bu_inner: dict[str, list[dict]] = {}
                for a in items_for_node:
                    by_bu_inner.setdefault(a["bu_id"], []).append(a)
                bu_kids: list[ExpenseGroupNode] = []
                for bu_key, items in by_bu_inner.items():
                    t = sum((a["allocated_amount"] for a in items), Decimal("0"))
                    hs = any(a["allocation_type"] != "direct" for a in items)
                    bu_kids.append(ExpenseGroupNode(
                        key=f"{node.key}|bu:{bu_key}",
                        label=bu_names.get(bu_key, "Sin Asignar"),
                        level=level + 1,
                        business_unit_id=UUID(bu_key) if bu_key != "unassigned" else None,
                        category_id=node.category_id,
                        parent_category_id=node.parent_category_id,
                        total=float(t),
                        has_shared_allocations=hs,
                    ))
                bu_kids.sort(key=lambda n: -n.total)
                return bu_kids

            # Indexar items por (cat_top, cat_child)
            by_top_and_child: dict[str, dict[str, list[dict]]] = {}
            for a in allocations:
                meta = cat_info.get(a["cat_id"], cat_info["none"])
                if meta["parent_id"] and meta["parent_id"] in cat_info:
                    top_id = meta["parent_id"]
                    child_id = a["cat_id"]
                else:
                    top_id = a["cat_id"]
                    child_id = "_self_"
                by_top_and_child.setdefault(top_id, {}).setdefault(child_id, []).append(a)

            for top_node in cat_nodes:
                top_id = str(top_node.category_id) if top_node.category_id else "none"
                if top_node.children:
                    # Cada child es una categoria hija → agregar UN-breakdown dentro
                    new_children: list[ExpenseGroupNode] = []
                    for child_node in top_node.children:
                        child_id = str(child_node.category_id) if child_node.category_id else "none"
                        items = by_top_and_child.get(top_id, {}).get(child_id, [])
                        child_node.children = add_bu_children(child_node, items, level=1)
                        new_children.append(child_node)
                    # Si el padre tiene tambien items directos (hojas sin sub-categoria),
                    # agregarlos como un sub-nodo "Directo al padre" con desglose por UN
                    self_items = by_top_and_child.get(top_id, {}).get("_self_", [])
                    if self_items:
                        self_total = sum(
                            (a["allocated_amount"] for a in self_items), Decimal("0")
                        )
                        self_hs = any(a["allocation_type"] != "direct" for a in self_items)
                        self_node = ExpenseGroupNode(
                            key=f"cat:{top_id}|self",
                            label=f"{top_node.label} (sin subcategoría)",
                            level=1,
                            category_id=top_node.category_id,
                            total=float(self_total),
                            has_shared_allocations=self_hs,
                        )
                        self_node.children = add_bu_children(self_node, self_items, level=1)
                        new_children.append(self_node)
                    new_children.sort(key=lambda n: -n.total)
                    top_node.children = new_children
                else:
                    # Cat hoja sin hijos → desglose directo por UN
                    items = [a for a in allocations if a["cat_id"] == top_id]
                    top_node.children = add_bu_children(top_node, items, level=0)

            return cat_nodes

        raise ValueError(f"group_by invalido: {group_by}")

    def get_expenses_detail(
        self,
        db: Session,
        organization_id: UUID,
        date_from: date,
        date_to: date,
        business_unit_id: Optional[UUID] = None,
        category_id: Optional[UUID] = None,
        business_unit_ids: Optional[list[UUID]] = None,
        category_ids: Optional[list[UUID]] = None,
        include_child_categories: bool = True,
        business_unit_unassigned: bool = False,
        category_uncategorized: bool = False,
    ) -> ExpenseDetailResponse:
        """Detalle de movimientos de gasto que componen un grupo del reporte.

        Filtra alocaciones por UN/categoria y devuelve los movimientos con su
        monto original y la porcion alocada al grupo. Acepta single (drill-down
        de un grupo) o multi (modo "sin agrupar" con multi-select de la UI).
        Para drill-down sobre "Sin Asignar"/"Sin Categoría" usar los flags.
        """
        dt_from, dt_to = self._date_range(date_from, date_to)

        allocations, bu_names, cat_info = self._compute_expense_allocations(
            db, organization_id, dt_from, dt_to
        )

        # Resolver filtro de categoria (multi tiene precedencia sobre single)
        cat_filter: Optional[set[str]] = None
        if category_uncategorized:
            cat_filter = {"none"}
        elif category_ids:
            expanded = self._expand_categories_to_children(
                db, organization_id, category_ids
            )
            cat_filter = {str(c) for c in expanded}
        elif category_id:
            if include_child_categories:
                expanded = self._expand_categories_to_children(
                    db, organization_id, [category_id]
                )
                cat_filter = {str(c) for c in expanded}
            else:
                cat_filter = {str(category_id)}

        bu_filter_set: Optional[set[str]] = None
        if business_unit_unassigned:
            bu_filter_set = {"unassigned"}
        elif business_unit_ids:
            bu_filter_set = {str(b) for b in business_unit_ids}
        elif business_unit_id:
            bu_filter_set = {str(business_unit_id)}

        # Filtrar alocaciones
        filtered = []
        for a in allocations:
            if bu_filter_set is not None and a["bu_id"] not in bu_filter_set:
                continue
            if cat_filter is not None and a["cat_id"] not in cat_filter:
                continue
            filtered.append(a)

        if not filtered:
            return ExpenseDetailResponse(items=[], total_allocated=0.0, total_count=0)

        # Cargar metadatos de los movimientos involucrados (eager)
        mov_ids = list({a["movement_id"] for a in filtered})
        movs = db.execute(
            select(MoneyMovement)
            .where(MoneyMovement.id.in_(mov_ids))
            .options(
                joinedload(MoneyMovement.third_party),
                joinedload(MoneyMovement.business_unit),
                joinedload(MoneyMovement.expense_category),
            )
        ).unique().scalars().all()
        mov_by_id = {m.id: m for m in movs}

        # Sumar allocated por movimiento (un mov puede tener varias alocaciones —
        # ej. shared con 2 UNs y filtro de UN matchea solo 1)
        items: list[ExpenseDetailItem] = []
        total_alloc = Decimal("0")
        per_mov_alloc: dict[UUID, Decimal] = {}
        per_mov_type: dict[UUID, str] = {}
        for a in filtered:
            per_mov_alloc[a["movement_id"]] = (
                per_mov_alloc.get(a["movement_id"], Decimal("0")) + a["allocated_amount"]
            )
            # Si tiene tipos mezclados, prevalece el primero (raro)
            per_mov_type.setdefault(a["movement_id"], a["allocation_type"])

        for mov_id, alloc in per_mov_alloc.items():
            mov = mov_by_id.get(mov_id)
            if not mov:
                continue
            items.append(ExpenseDetailItem(
                movement_id=mov.id,
                movement_number=mov.movement_number,
                date=mov.date.date() if hasattr(mov.date, "date") else mov.date,
                amount=float(mov.amount),
                allocated_amount=float(alloc),
                allocation_type=per_mov_type[mov_id],
                description=mov.description,
                third_party_id=mov.third_party_id,
                third_party_name=mov.third_party.name if mov.third_party else None,
                business_unit_id=mov.business_unit_id,
                business_unit_name=mov.business_unit.name if mov.business_unit else None,
                expense_category_id=mov.expense_category_id,
                expense_category_name=mov.expense_category.name if mov.expense_category else None,
                movement_type=mov.movement_type,
            ))
            total_alloc += alloc

        # Ordenar por fecha desc
        items.sort(key=lambda i: i.date, reverse=True)

        return ExpenseDetailResponse(
            items=items,
            total_allocated=float(total_alloc),
            total_count=len(items),
        )


# Instancia singleton
report_service = ReportService()
