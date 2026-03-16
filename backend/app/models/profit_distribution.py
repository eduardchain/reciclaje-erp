"""
Modelo ProfitDistribution — Repartición de utilidades a socios.

Registra la distribución de utilidades acumuladas entre los socios
(ThirdParty con is_investor=True, investor_type='socio').

Cada distribución genera un MoneyMovement tipo 'profit_distribution' por línea,
que actualiza el saldo del socio (current_balance -= amount) sin afectar cuentas.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrganizationMixin, TimestampMixin, GUID

if TYPE_CHECKING:
    from app.models.third_party import ThirdParty
    from app.models.money_movement import MoneyMovement
    from app.models.user import User


class ProfitDistribution(Base, OrganizationMixin, TimestampMixin):
    """Registro de una repartición de utilidades."""

    __tablename__ = "profit_distributions"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relaciones
    lines: Mapped[List["ProfitDistributionLine"]] = relationship(
        "ProfitDistributionLine",
        back_populates="distribution",
        order_by="ProfitDistributionLine.created_at",
        cascade="all, delete-orphan",
    )
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])


class ProfitDistributionLine(Base, TimestampMixin):
    """Línea de distribución: monto asignado a un socio."""

    __tablename__ = "profit_distribution_lines"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    distribution_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("profit_distributions.id", ondelete="CASCADE"), nullable=False
    )
    third_party_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("third_parties.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    money_movement_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("money_movements.id", ondelete="SET NULL"), nullable=True
    )

    # Relaciones
    distribution: Mapped["ProfitDistribution"] = relationship(
        "ProfitDistribution", back_populates="lines"
    )
    third_party: Mapped["ThirdParty"] = relationship("ThirdParty")
    money_movement: Mapped[Optional["MoneyMovement"]] = relationship("MoneyMovement")
