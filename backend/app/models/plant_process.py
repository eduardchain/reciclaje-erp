"""
Modelos FurnaceCharge / CrucibleCharge — eventos de proceso de planta
(SAC E1, v0.5 §11.1.13).

Registran cargas y descargas del horno grande y del crisol de Juan Mina.
Dos tablas (no una ProcessEvent con discriminador — D2 del plan E1): sus
efectos difieren (la descarga de crisol emite el par de maquila $300/kg).

batch_id es UUID SIN FK fisica (D7): la tabla furnace_batches es de Fase 2.
E1 solo crea la estructura; los efectos (KgLedgerMovement, produccion,
pares de maquila) llegan en E3.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.material import Material


class _PlantProcessColumns:
    """Columnas compartidas de los eventos de planta (mixin privado)."""

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    event_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="charge | discharge",
    )

    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Fecha de negocio — BusinessDate mediodia UTC via schema",
    )

    quantity_kg: Mapped[Decimal] = mapped_column(
        Numeric(14, 4),
        nullable=False,
        comment="Kg fisicos del evento",
    )

    output_quantity_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 4),
        nullable=True,
        comment="Solo discharge: kg producidos",
    )

    batch_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        nullable=True,
        comment="Lote — SIN FK (furnace_batches es Fase 2, D7). NULL en Fase 1",
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="confirmed",
        comment="confirmed | annulled",
    )

    annulled_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    annulled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class FurnaceCharge(Base, _PlantProcessColumns, OrganizationMixin, TimestampMixin):
    """Evento de horno grande: carga de aportantes / descarga de plomo crudo."""

    __tablename__ = "furnace_charges"

    material_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Aportante cargado (charge) / plomo crudo (discharge)",
    )

    output_material_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=True,
        comment="Solo discharge: plomo crudo producido",
    )

    annulled_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        Index("ix_furnace_charges_org_date", "organization_id", "date"),
    )

    # --- Relationships ---
    material: Mapped["Material"] = relationship("Material", foreign_keys=[material_id])
    output_material: Mapped[Optional["Material"]] = relationship(
        "Material", foreign_keys=[output_material_id]
    )

    def __repr__(self) -> str:
        return f"<FurnaceCharge {self.event_type} {self.quantity_kg}kg ({self.status})>"


class CrucibleCharge(Base, _PlantProcessColumns, OrganizationMixin, TimestampMixin):
    """Evento de crisol: carga de plomo crudo / descarga de plomo refinado."""

    __tablename__ = "crucible_charges"

    material_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Plomo crudo cargado (charge) / refinado (discharge)",
    )

    output_material_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=True,
        comment="Solo discharge: plomo puro producido",
    )

    annulled_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        Index("ix_crucible_charges_org_date", "organization_id", "date"),
    )

    # --- Relationships ---
    material: Mapped["Material"] = relationship("Material", foreign_keys=[material_id])
    output_material: Mapped[Optional["Material"]] = relationship(
        "Material", foreign_keys=[output_material_id]
    )

    def __repr__(self) -> str:
        return f"<CrucibleCharge {self.event_type} {self.quantity_kg}kg ({self.status})>"
