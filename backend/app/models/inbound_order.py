"""
Modelos InboundOrder / InboundOrderLine — orden de entrada (SAC E1, v0.5 §11.1.12).

Documento central de la "captura unica" de Fase 1: cubre compra propia,
postconsumo Willard, drosses, recoleccion en ruta y reventa. Las compras
derivan de ella (una InboundOrder de compra propia genera su Purchase en
'registered' — logica de E2; E1 solo crea la estructura).
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.fleet import Driver, Vehicle
    from app.models.material import Material
    from app.models.third_party import ThirdParty
    from app.models.warehouse import Warehouse


class InboundOrder(Base, OrganizationMixin, TimestampMixin):
    """Orden de entrada — captura unica en patio."""

    __tablename__ = "inbound_orders"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    order_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Consecutivo por org (patron sequential numbering del repo)",
    )

    inbound_type: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        comment="purchase | postconsumo_baterias | drosses | ruta | reventa",
    )

    warehouse_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Sede de recepcion fisica — inmutable post-registro (v0.5 §7.2)",
    )

    third_party_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("third_parties.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Proveedor real (una entrada POR proveedor, v0.5 §7.3)",
    )

    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Fecha de negocio — BusinessDate mediodia UTC via schema",
    )

    driver_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True
    )

    vehicle_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True
    )

    willard_distribution_center: Mapped[Optional[str]] = mapped_column(
        String(24),
        nullable=True,
        comment="Informativo (v0.5 §6.5)",
    )

    willard_account_subtype: Mapped[Optional[str]] = mapped_column(
        String(16),
        nullable=True,
        comment="escurrido | pinza — obligatorio si el material es SEC (v0.5 §6.4)",
    )

    goes_directly_to_jm: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Drosses directo BOG->JM (v0.5 §7.3)",
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="draft",
        comment="draft | confirmed | annulled",
    )

    annulled_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    annulled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    annulled_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "order_number", name="uq_inbound_orders_org_number"),
    )

    # --- Relationships ---
    warehouse: Mapped["Warehouse"] = relationship("Warehouse", foreign_keys=[warehouse_id])
    third_party: Mapped["ThirdParty"] = relationship("ThirdParty", foreign_keys=[third_party_id])
    driver: Mapped[Optional["Driver"]] = relationship("Driver", foreign_keys=[driver_id])
    vehicle: Mapped[Optional["Vehicle"]] = relationship("Vehicle", foreign_keys=[vehicle_id])
    lines: Mapped[list["InboundOrderLine"]] = relationship(
        "InboundOrderLine",
        back_populates="inbound_order",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<InboundOrder #{self.order_number} {self.inbound_type} ({self.status})>"


class InboundOrderLine(Base, OrganizationMixin, TimestampMixin):
    """Linea de orden de entrada: material, cantidad, peso bascula, calidad."""

    __tablename__ = "inbound_order_lines"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    inbound_order_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("inbound_orders.id", ondelete="CASCADE"),
        nullable=False,
    )

    material_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=False,
    )

    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)

    unit: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="Snapshot de la unidad al capturar (kg | unidad)",
    )

    scale_weight_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 4),
        nullable=True,
        comment="Peso de bascula cuando la cantidad viene en otra unidad",
    )

    quality_notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        Index("ix_inbound_order_lines_order", "inbound_order_id"),
    )

    # --- Relationships ---
    inbound_order: Mapped["InboundOrder"] = relationship(
        "InboundOrder", back_populates="lines"
    )
    material: Mapped["Material"] = relationship("Material", foreign_keys=[material_id])

    def __repr__(self) -> str:
        return f"<InboundOrderLine material={self.material_id} qty={self.quantity}>"
