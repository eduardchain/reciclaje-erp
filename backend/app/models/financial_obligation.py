"""
Modelo FinancialObligation — Obligaciones financieras bidireccionales.

Terceros que le prestan dinero a la empresa (direction='payable': les debemos)
o a los que la empresa les presta (direction='receivable': nos deben).

Reglas del cliente (plan F, docs/planes/plan-obligaciones-financieras.md):
- Interes SIMPLE mensual sobre capital vigente, base 30/360, prorrateo por dias.
- Devengo: causacion mensual al P&L via batch manual (patron depreciacion #21).
- Intereses pendientes quedan congelados como deuda — NO capitalizan.
- 1 tercero = 1 obligacion activa (validacion en service, no constraint DB).
- Tasa fija de por vida — cambio de tasa = obligacion/tercero nuevo.
- Abonos libres (sin plazo ni cuota); pagos de capital e intereses SEPARADOS.

El signo del saldo del tercero define el lado: payable → balance negativo
(les debemos), receivable → balance positivo (nos deben). Los contadores
capital_balance/pending_interest se actualizan transaccionalmente con cada
MoneyMovement del modulo. Invariante: Δtercero == Δ(capital + pendientes)
con el signo de la direccion.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrganizationMixin, TimestampMixin, GUID

if TYPE_CHECKING:
    from app.models.third_party import ThirdParty
    from app.models.user import User


class FinancialObligation(Base, OrganizationMixin, TimestampMixin):
    """Obligacion financiera (prestamo por pagar o por cobrar)."""

    __tablename__ = "financial_obligations"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    third_party_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("third_parties.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="1 obligacion ACTIVA por tercero (validacion en service)",
    )

    direction: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="payable = nos prestaron | receivable = prestamos nosotros",
    )

    monthly_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        comment="% mensual fijo de por vida (2.00 = 2%)",
    )

    capital_balance: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0"),
        comment="Capital vigente",
    )

    pending_interest: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0"),
        comment="Intereses causados sin pagar/cobrar (congelados, no capitalizan)",
    )

    accrual_start_period: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
        comment='"YYYY-MM": primer mes que causa el modulo (corte anti doble conteo, riesgo R3)',
    )

    last_accrued_period: Mapped[Optional[str]] = mapped_column(
        String(7),
        nullable=True,
        comment='"YYYY-MM": ultimo mes causado — guard retroactivo + cursor del batch',
    )

    disbursement_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Fecha del desembolso inicial (NULL si nacio por migracion de saldo)",
    )

    status: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="active",
        index=True,
        comment="active | settled (cierre manual con capital y pendientes en 0)",
    )

    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # --- Relationships ---
    third_party: Mapped["ThirdParty"] = relationship(
        "ThirdParty",
        foreign_keys=[third_party_id],
    )

    def __repr__(self) -> str:
        return (
            f"<FinancialObligation {self.direction} tp={self.third_party_id} "
            f"capital={self.capital_balance} pendientes={self.pending_interest}>"
        )
