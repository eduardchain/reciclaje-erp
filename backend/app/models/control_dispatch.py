"""
Modelos ControlDispatch / ControlDispatchLine — Salida de control (SAC).

Plan: docs/planes/plan-sac-documentos-control.md §4.3.

Documento SIN efectos para lo que sale solo por el consecutivo (estibas,
tubulares, electrolito): no mueve inventario, kg, tesoreria ni saldos. Johana
(24-nov): «no tenerlas en cuenta. Pero por el consecutivo si necesito dejarlas
en el registro del sistema».

La remision sale del MISMO talonario que las Entradas (Q-75, Daniel 24-nov):
por eso es obligatoria y entra a la vista «Talonario de remisiones». El numero
interno (`dispatch_number`) es un consecutivo propio (D7).
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.material import Material
    from app.models.third_party import ThirdParty
    from app.models.warehouse import Warehouse

CONTROL_DISPATCH_STATUSES = ("registered", "annulled")


class ControlDispatch(Base, OrganizationMixin, TimestampMixin):
    """Salida de control — registro sin valor ni efectos."""

    __tablename__ = "control_dispatches"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    dispatch_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Consecutivo propio por org (next_number, secuencia control_dispatch_number)",
    )

    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Fecha de negocio — BusinessDate mediodia UTC via schema",
    )

    warehouse_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Bodega de donde sale",
    )

    third_party_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("third_parties.id", ondelete="RESTRICT"),
        nullable=True,
        comment="A quien (opcional: no se pregunto que anotan, Q-75)",
    )

    remission_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Remision del MISMO talonario de las Entradas (Q-75)",
    )

    notes: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="registered",
        server_default="registered",
        comment="registered | annulled",
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
        UniqueConstraint(
            "organization_id", "dispatch_number", name="uq_control_dispatches_org_number"
        ),
        CheckConstraint(
            "status IN ('registered', 'annulled')", name="ck_control_dispatches_status"
        ),
    )

    warehouse: Mapped["Warehouse"] = relationship("Warehouse", foreign_keys=[warehouse_id])
    third_party: Mapped[Optional["ThirdParty"]] = relationship(
        "ThirdParty", foreign_keys=[third_party_id]
    )
    lines: Mapped[list["ControlDispatchLine"]] = relationship(
        "ControlDispatchLine",
        back_populates="dispatch",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<ControlDispatch #{self.dispatch_number} ({self.status})>"


class ControlDispatchLine(Base, OrganizationMixin, TimestampMixin):
    """Linea de una Salida de control: material de control, cantidad y peso."""

    __tablename__ = "control_dispatch_lines"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    dispatch_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("control_dispatches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    material_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=False,
    )

    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)

    scale_weight_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 3), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "dispatch_id", "material_id", name="uq_control_dispatch_lines_dispatch_material"
        ),
        CheckConstraint("quantity > 0", name="ck_control_dispatch_lines_quantity"),
    )

    dispatch: Mapped["ControlDispatch"] = relationship(
        "ControlDispatch", back_populates="lines"
    )
    material: Mapped["Material"] = relationship("Material", foreign_keys=[material_id])
