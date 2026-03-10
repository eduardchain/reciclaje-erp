"""
Modelo DeferredExpense — Gastos diferidos distribuidos en cuotas mensuales.

Un gasto diferido representa un gasto grande (ej: seguro anual) que se distribuye
en cuotas mensuales. El usuario aplica manualmente cada cuota, generando un
MoneyMovement de tipo 'expense' o 'provision_expense'.

Estados:
- active: Gasto en proceso, con cuotas pendientes por aplicar
- completed: Todas las cuotas fueron aplicadas
- cancelled: Gasto cancelado antes de completar (cuotas ya aplicadas permanecen)

DeferredApplication registra cada cuota aplicada con su MoneyMovement vinculado.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrganizationMixin, TimestampMixin, GUID

if TYPE_CHECKING:
    from app.models.expense_category import ExpenseCategory
    from app.models.money_account import MoneyAccount
    from app.models.third_party import ThirdParty
    from app.models.money_movement import MoneyMovement
    from app.models.user import User


VALID_DEFERRED_EXPENSE_TYPES = ["expense", "provision_expense"]
VALID_DEFERRED_STATUSES = ["active", "completed", "cancelled"]


class DeferredExpense(Base, OrganizationMixin, TimestampMixin):
    """
    Gasto diferido — gasto grande distribuido en cuotas mensuales.

    El campo expense_type determina como se generan los movimientos:
    - 'expense': crea MoneyMovement tipo expense (requiere account_id)
    - 'provision_expense': crea MoneyMovement tipo provision_expense (requiere provision_id)
    """

    __tablename__ = "deferred_expenses"

    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Nombre descriptivo del gasto diferido",
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Monto total del gasto",
    )

    monthly_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Cuota mensual (total / meses, redondeado hacia abajo)",
    )

    total_months: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Numero total de cuotas mensuales",
    )

    applied_months: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Cuotas ya aplicadas",
    )

    expense_category_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("expense_categories.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Categoria del gasto",
    )

    # Tipo de gasto: 'expense' o 'provision_expense'
    expense_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="Tipo: expense (desde cuenta) o provision_expense (desde provision)",
    )

    # Cuenta — requerida si expense_type == 'expense'
    account_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("money_accounts.id", ondelete="RESTRICT"),
        nullable=True,
        comment="Cuenta de dinero (requerida para tipo expense)",
    )

    # Provision — requerida si expense_type == 'provision_expense'
    provision_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("third_parties.id", ondelete="RESTRICT"),
        nullable=True,
        comment="Provision (requerida para tipo provision_expense)",
    )

    description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Descripcion adicional",
    )

    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Fecha de inicio (referencia, no automatico)",
    )

    # Estado
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        index=True,
        comment="active | completed | cancelled",
    )

    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    cancelled_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # --- Relationships ---
    expense_category: Mapped["ExpenseCategory"] = relationship(
        "ExpenseCategory",
        foreign_keys=[expense_category_id],
    )

    account: Mapped[Optional["MoneyAccount"]] = relationship(
        "MoneyAccount",
        foreign_keys=[account_id],
    )

    provision: Mapped[Optional["ThirdParty"]] = relationship(
        "ThirdParty",
        foreign_keys=[provision_id],
    )

    applications: Mapped[List["DeferredApplication"]] = relationship(
        "DeferredApplication",
        back_populates="deferred_expense",
        order_by="DeferredApplication.application_number",
    )

    # --- Table constraints ---
    __table_args__ = (
        Index("ix_deferred_expenses_org_status", "organization_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<DeferredExpense(id={self.id}, name='{self.name}', "
            f"status='{self.status}', {self.applied_months}/{self.total_months})>"
        )


class DeferredApplication(Base, TimestampMixin):
    """
    Registro de una cuota aplicada de un gasto diferido.

    Cada aplicacion genera un MoneyMovement y queda vinculada para trazabilidad.
    """

    __tablename__ = "deferred_applications"

    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid4,
    )

    deferred_expense_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("deferred_expenses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    application_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Numero secuencial de cuota (1, 2, 3...)",
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Monto de esta cuota",
    )

    money_movement_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("money_movements.id", ondelete="RESTRICT"),
        nullable=False,
        comment="MoneyMovement generado por esta cuota",
    )

    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Fecha/hora en que se aplico la cuota",
    )

    applied_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # --- Relationships ---
    deferred_expense: Mapped["DeferredExpense"] = relationship(
        "DeferredExpense",
        back_populates="applications",
    )

    money_movement: Mapped["MoneyMovement"] = relationship(
        "MoneyMovement",
        foreign_keys=[money_movement_id],
    )

    def __repr__(self) -> str:
        return (
            f"<DeferredApplication(id={self.id}, "
            f"#{self.application_number}, amount={self.amount})>"
        )
