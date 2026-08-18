"""
Modelos Transfer / TransferLine — traslado intersede en dos pasos (SAC E3.1).

Documento de patio con cara financiera en kg: despacho (origen → bodega
virtual de transito) y recepcion confirmada (transito → destino fisico).
Todo es POR LINEA (plan E3.1 E2): tolerancia, kg equivalente, par de
maquila y discrepancias se evaluan linea a linea; el estado de cabecera
es derivado (helper _recompute_status del servicio).

Invariante #1 del plan: un traslado NO cambia current_average_cost — los
InventoryMovement de despacho/recepcion salen y entran al mismo unit_cost
(snapshot org-wide al despacho). La merma bascula se cierra con un
InventoryAdjustment decrease hijo (FK inventory_adjustments.transfer_id),
jamas con incorporate/remove_from_pool.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.exception_task import DiscrepancyTask
    from app.models.material import Material
    from app.models.user import User
    from app.models.warehouse import Warehouse


# Estados validos de cabecera (derivados de las lineas, persistidos para bandeja)
VALID_TRANSFER_STATUSES = [
    "dispatched",         # Despachado — en transito, pendiente de recepcion
    "held_discrepancy",   # >=1 linea fuera de tolerancia con task abierta
    "received",           # Todas las lineas recibidas con efectos emitidos
    "annulled",           # Anulado con reversa completa
]


class Transfer(Base, OrganizationMixin, TimestampMixin):
    """Traslado intersede en dos pasos (cabecera)."""

    __tablename__ = "transfers"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    transfer_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Consecutivo por org (advisory lock, patron inbound_order)",
    )

    from_warehouse_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Sede origen (CV o BOG)",
    )

    to_warehouse_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Sede destino fisica final (JM)",
    )

    # NULL = traslado INTRA-SEDE: no hubo transito porque no hubo dos pasos.
    # Dentro de una sede no se pesa al salir ni al llegar, asi que el material
    # va origen -> destino en un solo salto y el traslado nace `received`.
    transit_warehouse_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=True,
        comment="Bodega de transito (NULL = traslado intra-sede, sin transito)",
    )

    dispatch_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Fecha negocio del despacho",
    )

    received_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Fecha negocio de la recepcion (E11: fecha canonica de los efectos)",
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="dispatched",
        server_default="dispatched",
        index=True,
        comment="dispatched | held_discrepancy | received | annulled — derivado de lineas",
    )

    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    received_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    annulled_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    annulled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    annulled_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "transfer_number", name="uq_transfers_org_number"
        ),
        Index("ix_transfers_org_status", "organization_id", "status"),
        Index("ix_transfers_org_dispatch", "organization_id", "dispatch_date"),
    )

    # --- Relationships ---
    lines: Mapped[list["TransferLine"]] = relationship(
        "TransferLine",
        back_populates="transfer",
        cascade="all, delete-orphan",
        order_by="TransferLine.created_at",
    )

    from_warehouse: Mapped["Warehouse"] = relationship(
        "Warehouse", foreign_keys=[from_warehouse_id]
    )
    to_warehouse: Mapped["Warehouse"] = relationship(
        "Warehouse", foreign_keys=[to_warehouse_id]
    )
    transit_warehouse: Mapped["Warehouse"] = relationship(
        "Warehouse", foreign_keys=[transit_warehouse_id]
    )
    created_by_user: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[created_by]
    )
    received_by_user: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[received_by]
    )

    def __repr__(self) -> str:
        return f"<Transfer #{self.transfer_number} ({self.status})>"


class TransferLine(Base, OrganizationMixin, TimestampMixin):
    """Linea de traslado — unidad de tolerancia, kg y maquila."""

    __tablename__ = "transfer_lines"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    transfer_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("transfers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    material_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    quantity_dispatched: Mapped[Decimal] = mapped_column(
        Numeric(15, 4), nullable=False
    )

    quantity_received: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 4),
        nullable=True,
        comment="Bascula destino; ge=0 permite recibido=0 = merma total (bloq-7)",
    )

    resolved_quantity: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 4),
        nullable=True,
        comment="Cantidad final tras resolver discrepancia (preserva la bascula original)",
    )

    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Snapshot current_average_cost ORG-WIDE al despacho (#5, invariante 1)",
    )

    is_contributor: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Snapshot al despacho: tenia MaterialConversionFormula vigente",
    )

    conversion_formula_snapshot: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Snapshot de la formula vigente AL DESPACHO (E7). NULL si no aportante",
    )

    kg_lead_equivalent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 4),
        nullable=True,
        comment="quantity_efectiva x factor_snapshot. NULL hasta emitir efectos",
    )

    maquila_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="kg_lead_equivalent x tarifa maquila_intersede_cv_jm",
    )

    discrepancy_task_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("discrepancy_tasks.id", ondelete="SET NULL"),
        nullable=True,
        comment="Poblado si la linea salio de tolerancia",
    )

    effects_emitted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True cuando intersede + par de esta linea ya se emitieron",
    )

    __table_args__ = (
        CheckConstraint(
            "quantity_dispatched > 0", name="ck_transfer_lines_qty_dispatched_positive"
        ),
        CheckConstraint(
            "quantity_received IS NULL OR quantity_received >= 0",
            name="ck_transfer_lines_qty_received_ge_zero",
        ),
        Index("ix_transfer_lines_org_material", "organization_id", "material_id"),
    )

    # --- Relationships ---
    transfer: Mapped["Transfer"] = relationship("Transfer", back_populates="lines")

    material: Mapped["Material"] = relationship("Material", foreign_keys=[material_id])

    discrepancy_task: Mapped[Optional["DiscrepancyTask"]] = relationship(
        "DiscrepancyTask", foreign_keys=[discrepancy_task_id]
    )

    def __repr__(self) -> str:
        return (
            f"<TransferLine mat={self.material_id} disp={self.quantity_dispatched} "
            f"recv={self.quantity_received}>"
        )
