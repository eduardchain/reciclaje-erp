"""
Modelo ScheduledExpense — Gastos diferidos con aplicacion de cuotas.

Representa un pago grande que se distribuye en cuotas mensuales en P&L.
Ejemplo: Dotacion $12M pagada en enero, se registra $1M/mes en P&L.

Flujo:
1. Al crear: sale dinero de cuenta (deferred_funding), se crea tercero prepago
2. Cada mes: aplica cuota (deferred_expense) que aparece en P&L
3. Al completar: tercero prepago queda en $0
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrganizationMixin, TimestampMixin, GUID

if TYPE_CHECKING:
    from app.models.expense_category import ExpenseCategory
    from app.models.money_account import MoneyAccount
    from app.models.third_party import ThirdParty
    from app.models.money_movement import MoneyMovement
    from app.models.business_unit import BusinessUnit


VALID_SCHEDULED_STATUSES = ["active", "completed", "cancelled"]


class ScheduledExpense(Base, OrganizationMixin, TimestampMixin):
    """Gasto diferido con aplicacion de cuotas mensuales."""

    __tablename__ = "scheduled_expenses"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    name: Mapped[str] = mapped_column(String(200), nullable=False)

    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Montos
    total_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    monthly_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    total_months: Mapped[int] = mapped_column(Integer, nullable=False)

    applied_months: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Cuenta origen (de donde salio el dinero)
    source_account_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("money_accounts.id", ondelete="RESTRICT"), nullable=False,
    )

    # Tercero prepago (auto-creado, is_system_entity=True)
    prepaid_third_party_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("third_parties.id", ondelete="RESTRICT"), nullable=False,
    )

    # Categoria de gasto
    expense_category_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("expense_categories.id", ondelete="RESTRICT"), nullable=False,
    )

    # Movimiento inicial (el pago)
    funding_movement_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("money_movements.id", ondelete="SET NULL"), nullable=True,
    )

    # Asignacion a Unidad de Negocio (hereda a deferred_expense cuotas)
    business_unit_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("business_units.id", ondelete="SET NULL"), nullable=True,
    )

    applicable_business_unit_ids: Mapped[Optional[list]] = mapped_column(
        JSONB, nullable=True,
    )

    # Programacion
    start_date: Mapped[date] = mapped_column(Date, nullable=False)

    apply_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    next_application_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Estado
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    # Auditoria
    created_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    cancelled_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    source_account: Mapped["MoneyAccount"] = relationship(
        "MoneyAccount", foreign_keys=[source_account_id],
    )

    prepaid_third_party: Mapped["ThirdParty"] = relationship(
        "ThirdParty", foreign_keys=[prepaid_third_party_id],
    )

    expense_category: Mapped["ExpenseCategory"] = relationship(
        "ExpenseCategory", foreign_keys=[expense_category_id],
    )

    business_unit: Mapped[Optional["BusinessUnit"]] = relationship(
        "BusinessUnit", foreign_keys=[business_unit_id],
    )

    applications: Mapped[List["ScheduledExpenseApplication"]] = relationship(
        "ScheduledExpenseApplication",
        back_populates="scheduled_expense",
        order_by="ScheduledExpenseApplication.application_number",
    )

    __table_args__ = (
        Index("ix_scheduled_expenses_org_status", "organization_id", "status"),
        Index("ix_scheduled_expenses_next_date", "next_application_date"),
    )


class ScheduledExpenseApplication(Base, TimestampMixin):
    """Registro de cada cuota aplicada."""

    __tablename__ = "scheduled_expense_applications"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    scheduled_expense_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("scheduled_expenses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    application_number: Mapped[int] = mapped_column(Integer, nullable=False)

    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    money_movement_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("money_movements.id", ondelete="RESTRICT"), nullable=False,
    )

    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    applied_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    scheduled_expense: Mapped["ScheduledExpense"] = relationship(
        "ScheduledExpense", back_populates="applications",
    )

    money_movement: Mapped["MoneyMovement"] = relationship(
        "MoneyMovement", foreign_keys=[money_movement_id],
    )
