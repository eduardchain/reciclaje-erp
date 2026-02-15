"""
Modelo InventoryAdjustment — Ajustes manuales de inventario.

Tipos de ajuste:
- increase: Material encontrado/recibido sin compra (recalcula costo promedio)
- decrease: Faltante, merma, perdida (usa costo promedio actual)
- recount: Conteo fisico — calcula diferencia automaticamente
- zero_out: Llevar stock a cero (tipo especial de decrease)

Todos los ajustes afectan unicamente current_stock_liquidated (no transito).
El transito se maneja exclusivamente por el workflow de compras.

Estado:
- confirmed: Ajuste registrado y aplicado (default)
- annulled: Ajuste anulado con reversion de stock
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrganizationMixin, TimestampMixin, GUID

if TYPE_CHECKING:
    from app.models.material import Material
    from app.models.warehouse import Warehouse
    from app.models.user import User


# Tipos de ajuste validos
VALID_ADJUSTMENT_TYPES = [
    "increase",   # Aumento: material encontrado/recibido, recalcula costo promedio
    "decrease",   # Disminucion: faltante/merma, usa costo promedio actual
    "recount",    # Conteo fisico: ajusta a cantidad exacta
    "zero_out",   # Llevar a cero: elimina todo el stock liquidado
]


class InventoryAdjustment(Base, OrganizationMixin, TimestampMixin):
    """
    Ajuste manual de inventario.

    Cada ajuste afecta current_stock_liquidated de un material.
    El campo quantity es el delta aplicado (positivo o negativo).
    El tipo define las reglas de costo y validacion.
    """

    __tablename__ = "inventory_adjustments"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid4,
    )

    # Numero secuencial por organizacion
    adjustment_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Numero secuencial por organizacion (1, 2, 3...)",
    )

    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Fecha del ajuste",
    )

    # Tipo de ajuste
    adjustment_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Tipo: increase, decrease, recount, zero_out",
    )

    # Material y bodega afectados
    material_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Material ajustado",
    )

    warehouse_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Bodega donde se realiza el ajuste",
    )

    # Cantidades
    previous_stock: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        comment="Stock liquidado antes del ajuste",
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        comment="Delta aplicado (positivo=aumento, negativo=disminucion)",
    )

    new_stock: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        comment="Stock liquidado despues del ajuste",
    )

    # Solo para recount: la cantidad contada fisicamente
    counted_quantity: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 4),
        nullable=True,
        comment="Cantidad contada fisicamente (solo para tipo recount)",
    )

    # Costo
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        comment="Costo unitario usado (proporcionado en increase, promedio en decrease/recount)",
    )

    total_value: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Valor total del ajuste: |quantity| * unit_cost",
    )

    # Razon y notas
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Razon del ajuste (obligatoria)",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notas adicionales",
    )

    # Estado y auditoria de anulacion
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="confirmed",
        index=True,
        comment="confirmed = aplicado, annulled = anulado con reversion",
    )

    annulled_reason: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Razon de anulacion",
    )

    annulled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Fecha/hora de anulacion",
    )

    annulled_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Usuario que anulo el ajuste",
    )

    # Auditoria de creacion
    created_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Usuario que creo el ajuste",
    )

    # --- Relationships ---
    material: Mapped["Material"] = relationship(
        "Material",
        foreign_keys=[material_id],
    )

    warehouse: Mapped["Warehouse"] = relationship(
        "Warehouse",
        foreign_keys=[warehouse_id],
    )

    annulled_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[annulled_by],
    )

    created_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by],
    )

    # --- Constraints e indexes ---
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "adjustment_number",
            name="uq_adjustment_number_per_org",
        ),
        Index("ix_inventory_adjustments_org_date", "organization_id", "date"),
        Index("ix_inventory_adjustments_org_material", "organization_id", "material_id"),
        Index("ix_inventory_adjustments_org_status", "organization_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<InventoryAdjustment(id={self.id}, #{self.adjustment_number}, "
            f"type='{self.adjustment_type}', qty={self.quantity}, "
            f"status='{self.status}')>"
        )
