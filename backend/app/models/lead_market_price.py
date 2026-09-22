"""
Modelo LeadMarketPrice — precio de mercado del plomo por kilo (CC-014, Q-B).

Johana (18-sep, con sus palabras): "yo siempre la coloco pues negativo en el
balance, en pesos. le doy un valor de acuerdo al precio del mercado en ese
momento y la tengo como un valor negativo, o sea, restando dentro de mi
inventario". Hoy lo hace a mano fuera del sistema; esta tabla es el dato.

Append-only como ServiceTariff (#35), con UNA diferencia que importa
(D1 del plan): la vigencia se decide por `effective_date`, una fecha de
NEGOCIO, no por `created_at`. El balance de fin de mes siempre se calcula
despues: si Johana carga el precio de septiembre el 2 de octubre y el vigente
saliera de `created_at`, el corte del 30 de septiembre no encontraria precio
y la linea saldria vacia justo en el caso que motivo el requerimiento.

🔴 Consecuencia aprobada por Daniel el 2026-09-21, con las dos opciones y sus
costos a la vista: cargar un precio con fecha anterior CAMBIA cortes historicos
ya impresos. Es la #61 al reves, a proposito — alla el pasado cambiaba sin que
nadie lo viera; aca el balance muestra siempre que precio uso y de que fecha.
"""
from typing import Optional
from uuid import UUID, uuid4

from decimal import Decimal
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from datetime import datetime

from app.models.base import Base, GUID, OrganizationMixin, TimestampMixin


class LeadMarketPrice(Base, OrganizationMixin, TimestampMixin):
    """Precio de mercado del plomo por kg, con fecha de vigencia de negocio."""

    __tablename__ = "lead_market_prices"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    price_per_kg: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="Precio de mercado del plomo por kg, en pesos colombianos",
    )

    # Fecha de NEGOCIO (mediodia UTC via BusinessDate), no timestamp de carga.
    # Precedente en el repo: KgLedgerMovement.transaction_date.
    effective_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Fecha desde la que rige el precio (fecha de negocio, mediodia UTC)",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="De donde salio el precio (bolsa, cotizacion, acuerdo)",
    )

    created_by: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("price_per_kg > 0", name="ck_lead_market_prices_price_positive"),
        Index(
            "ix_lmp_org_effective",
            "organization_id",
            text("effective_date DESC"),
        ),
    )

    def __repr__(self) -> str:
        return f"<LeadMarketPrice ${self.price_per_kg}/kg desde {self.effective_date:%Y-%m-%d}>"
