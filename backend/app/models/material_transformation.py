"""
Modelo MaterialTransformation — Transformacion/desintegracion de materiales.

Permite registrar la desintegracion de un material compuesto en sus componentes.
Ejemplo: Motor Electrico 500kg → Cobre 200kg + Hierro 180kg + Aluminio 100kg + Merma 20kg

Cada transformacion:
- Tiene UN material de origen (source) que se descuenta del stock liquidado
- Tiene N materiales de destino (lines) que se agregan al stock liquidado
- Puede tener merma (waste) que se pierde
- Validacion: sum(destinos) + merma == cantidad origen
- Distribucion de costos: proporcional por peso o manual

Estado:
- confirmed: Transformacion registrada y aplicada (default)
- annulled: Transformacion anulada con reversion de stock
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


class MaterialTransformation(Base, OrganizationMixin, TimestampMixin):
    """
    Transformacion de un material de origen en multiples materiales destino.

    El material de origen se descuenta del stock liquidado.
    Cada linea destino se agrega al stock liquidado con su costo distribuido.
    La merma (waste) es material perdido en el proceso.
    """

    __tablename__ = "material_transformations"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid4,
    )

    # Numero secuencial por organizacion
    transformation_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Numero secuencial por organizacion (1, 2, 3...)",
    )

    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Fecha de la transformacion",
    )

    # Material de origen
    source_material_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Material de origen que se desintegra",
    )

    source_warehouse_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Bodega donde se realiza la transformacion",
    )

    source_quantity: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        comment="Cantidad de material de origen",
    )

    source_unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        comment="Costo promedio del material de origen al momento de la transformacion",
    )

    source_total_value: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Valor total del origen: source_quantity * source_unit_cost",
    )

    # Merma/desperdicio
    waste_quantity: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        default=Decimal("0"),
        comment="Cantidad de merma/desperdicio del proceso",
    )

    waste_value: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0"),
        comment="Valor monetario perdido por la merma",
    )

    # Metodo de distribucion de costos
    cost_distribution: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="proportional_weight",
        comment="Metodo: proportional_weight (por peso) o manual",
    )

    # Razon y notas
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Razon de la transformacion (obligatoria)",
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
        comment="confirmed = aplicada, annulled = anulada con reversion",
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
        comment="Usuario que anulo la transformacion",
    )

    # Auditoria de creacion
    created_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Usuario que creo la transformacion",
    )

    # --- Relationships ---
    source_material: Mapped["Material"] = relationship(
        "Material",
        foreign_keys=[source_material_id],
    )

    source_warehouse: Mapped["Warehouse"] = relationship(
        "Warehouse",
        foreign_keys=[source_warehouse_id],
    )

    lines: Mapped[list["MaterialTransformationLine"]] = relationship(
        "MaterialTransformationLine",
        back_populates="transformation",
        cascade="all, delete-orphan",
        order_by="MaterialTransformationLine.created_at",
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
            "transformation_number",
            name="uq_transformation_number_per_org",
        ),
        Index("ix_material_transformations_org_date", "organization_id", "date"),
        Index("ix_material_transformations_org_source", "organization_id", "source_material_id"),
        Index("ix_material_transformations_org_status", "organization_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<MaterialTransformation(id={self.id}, #{self.transformation_number}, "
            f"source={self.source_quantity}, waste={self.waste_quantity}, "
            f"status='{self.status}')>"
        )


class MaterialTransformationLine(Base, TimestampMixin):
    """
    Linea de destino de una transformacion de materiales.

    Cada linea representa un material que resulta de la desintegracion.
    El costo se distribuye proporcionalmente por peso o manualmente.
    """

    __tablename__ = "material_transformation_lines"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid4,
    )

    # FK a la transformacion padre
    transformation_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("material_transformations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Transformacion a la que pertenece esta linea",
    )

    # Material destino
    destination_material_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Material destino resultante de la transformacion",
    )

    destination_warehouse_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Bodega donde se almacena el material destino",
    )

    # Cantidades y costos
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        comment="Cantidad de material destino resultante",
    )

    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        comment="Costo por unidad distribuido",
    )

    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Costo total: quantity * unit_cost",
    )

    # --- Relationships ---
    transformation: Mapped["MaterialTransformation"] = relationship(
        "MaterialTransformation",
        foreign_keys=[transformation_id],
        back_populates="lines",
    )

    destination_material: Mapped["Material"] = relationship(
        "Material",
        foreign_keys=[destination_material_id],
    )

    destination_warehouse: Mapped["Warehouse"] = relationship(
        "Warehouse",
        foreign_keys=[destination_warehouse_id],
    )

    def __repr__(self) -> str:
        return (
            f"<MaterialTransformationLine(id={self.id}, "
            f"qty={self.quantity}, cost={self.unit_cost})>"
        )
