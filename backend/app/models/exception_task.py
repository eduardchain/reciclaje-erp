"""
Modelos DiscrepancyTask / DailyOkSeal — panel de excepciones (SAC E1, v0.5 §10.3, §11.1.11).

El panel concilia cada transaccion sola y muestra unicamente lo anomalo:
en un dia normal esta vacio. Cada discrepancia detectada se materializa
como una tarea con tipo, severidad, monto o kg involucrado, sede y
responsable sugerido (D9 del plan E1 — shape declarado, la prosa de §10.3
no tipa columnas). Los detectores automaticos llegan en E5; el catalogo de
valores de discrepancy_type se cierra alla.

DailyOkSeal es la firma del "OK del dia": snapshot que bloquea edicion
posterior salvo admin con bitacora (analogo diario del sello semanal).
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.warehouse import Warehouse


class DiscrepancyTask(Base, OrganizationMixin, TimestampMixin):
    """Tarea de discrepancia detectada por el panel de excepciones."""

    __tablename__ = "discrepancy_tasks"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    discrepancy_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        comment="Catalogo de valores se cierra en plan E5 (detectores)",
    )

    severity: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="normal | high | critical",
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="open",
        comment="open | in_review | justified | corrected | closed",
    )

    entity_type: Mapped[Optional[str]] = mapped_column(
        String(40),
        nullable=True,
        comment="Polimorfico: Transfer, MoneyMovement, InventoryMovement, ...",
    )

    entity_id: Mapped[Optional[UUID]] = mapped_column(GUID(), nullable=True)

    description: Mapped[str] = mapped_column(String(500), nullable=False)

    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    warehouse_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("warehouses.id", ondelete="SET NULL"),
        nullable=True,
        comment="Sede de la discrepancia",
    )

    amount_involved: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2), nullable=True
    )

    kg_involved: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4), nullable=True)

    suggested_assignee_role: Mapped[Optional[str]] = mapped_column(
        String(40),
        nullable=True,
        comment="Responsable sugerido (rol, no usuario) — lo fijan los detectores de E5",
    )

    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    resolved_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    resolution_notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    resolution_entity_type: Mapped[Optional[str]] = mapped_column(
        String(40),
        nullable=True,
        comment="Link al ajuste generado por la resolucion (ej: InventoryAdjustment)",
    )

    resolution_entity_id: Mapped[Optional[UUID]] = mapped_column(GUID(), nullable=True)

    __table_args__ = (
        Index("ix_discrepancy_tasks_org_status", "organization_id", "status"),
        Index("ix_discrepancy_tasks_entity", "entity_type", "entity_id"),
    )

    # --- Relationships ---
    warehouse: Mapped[Optional["Warehouse"]] = relationship(
        "Warehouse", foreign_keys=[warehouse_id]
    )

    def __repr__(self) -> str:
        return f"<DiscrepancyTask {self.discrepancy_type} {self.severity} ({self.status})>"


class DailyOkSeal(Base, OrganizationMixin, TimestampMixin):
    """Firma del 'OK del dia' — todas las discrepancias del dia resueltas."""

    __tablename__ = "daily_ok_seals"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    sealed_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Dia de negocio sellado",
    )

    tasks_resolved_count: Mapped[int] = mapped_column(Integer, nullable=False)

    signed_by: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "sealed_date", name="uq_daily_ok_seals_org_date"),
    )

    def __repr__(self) -> str:
        return f"<DailyOkSeal {self.sealed_date} tasks={self.tasks_resolved_count}>"
