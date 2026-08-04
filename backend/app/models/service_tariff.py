"""
Modelo ServiceTariff — tarifas de servicio de maquila y fletes (SAC E1, v0.5 §11.1.4).

Append-only puro alineado con decision #35 (PriceList): la vigente es
max(created_at, id) por tariff_code — sin valid_from/valid_to ni is_current.
Toda causacion es inmediata al evento: el MoneyMovement persiste el monto
calculado con la tarifa vigente (y tariff_id como trazabilidad).
Cambios anuales por IPC crean un registro nuevo; el historico queda intacto.
"""
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column
from decimal import Decimal

from app.models.base import Base, GUID, OrganizationMixin, TimestampMixin


class ServiceTariff(Base, OrganizationMixin, TimestampMixin):
    """Tarifa de servicio (maquila Willard/intersede/crisol, fletes)."""

    __tablename__ = "service_tariffs"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    tariff_code: Mapped[str] = mapped_column(
        String(48),
        nullable=False,
        comment="maquila_willard | maquila_intersede_cv_jm | maquila_crisol | "
        "flete_willard_bog_baq | flete_willard_planta_planta",
    )

    unit_price_cop: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="Precio unitario en pesos colombianos",
    )

    unit: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        comment="per_kg_lead | per_kg_battery | per_unit",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Contexto del cambio (renegociacion IPC, cambio contractual)",
    )

    created_by: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("unit_price_cop > 0", name="ck_service_tariffs_price_positive"),
        Index(
            "ix_st_code_current",
            "organization_id",
            "tariff_code",
            text("created_at DESC"),
        ),
    )

    def __repr__(self) -> str:
        return f"<ServiceTariff {self.tariff_code} ${self.unit_price_cop}/{self.unit}>"
