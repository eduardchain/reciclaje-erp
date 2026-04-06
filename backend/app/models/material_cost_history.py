"""
Historial de cambios de costo promedio de materiales.

Registra cada cambio al current_average_cost para:
1. Revertir con precision al cancelar/anular operaciones
2. Detectar operaciones posteriores que bloquean la cancelacion

Solo previous_cost se usa en reversal. previous_stock/new_stock son solo para auditoria.
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, GUID

if TYPE_CHECKING:
    from app.models.material import Material


class MaterialCostHistory(Base, TimestampMixin):
    """
    Registro de cada cambio al costo promedio de un material.

    source_type values:
    - purchase_liquidation: Liquidacion de compra
    - adjustment_increase: Ajuste de inventario tipo aumento
    - transformation_in: Material destino de transformacion
    """
    __tablename__ = "material_cost_histories"

    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid4,
    )

    organization_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    material_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Costo antes y despues de la operacion
    previous_cost: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        comment="Costo promedio ANTES de la operacion (se usa para reversal)",
    )

    new_cost: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        comment="Costo promedio DESPUES de la operacion",
    )

    # Contexto de stock (solo auditoria, NO se usa en reversal)
    previous_stock: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        comment="Stock al momento del cambio (solo auditoria/debugging)",
    )

    new_stock: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        comment="Stock despues del cambio (solo auditoria/debugging)",
    )

    # Origen del cambio
    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="purchase_liquidation | adjustment_increase | transformation_in | transformation_out",
    )

    source_id: Mapped[UUID] = mapped_column(
        GUID(),
        nullable=False,
        comment="ID de la compra, ajuste o transformacion que causo el cambio",
    )

    # Fecha de negocio de la operacion (para costo promedio historico)
    transaction_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Fecha de negocio de la operacion (business date, no timestamp servidor)",
    )

    # Relationships
    material: Mapped["Material"] = relationship(
        "Material",
        back_populates="cost_history",
    )

    __table_args__ = (
        Index("ix_mch_org_material", "organization_id", "material_id"),
        Index("ix_mch_source", "source_type", "source_id"),
    )
