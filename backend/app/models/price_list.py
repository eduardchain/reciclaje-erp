"""
Modelo PriceList — Registro historico de precios por material.

Cada registro representa un precio de compra y/o venta vigente para un material.
El precio "actual" es el registro mas reciente (por created_at) para cada material.

Esto permite:
- Trazabilidad: saber quien cambio que precio y cuando
- Analisis: ver la evolucion de precios en el tiempo
- Auditoria: justificar decisiones de compra/venta
"""
from uuid import UUID, uuid4
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Numeric, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, OrganizationMixin, GUID

if TYPE_CHECKING:
    from app.models.material import Material
    from app.models.user import User


class PriceList(Base, TimestampMixin, OrganizationMixin):
    """
    Registro de precio de compra/venta por material.

    El precio vigente es el registro mas reciente para cada material.
    Se crea un nuevo registro cada vez que se actualiza un precio,
    formando un historial completo de cambios.
    """

    __tablename__ = "price_lists"
    __table_args__ = (
        # El "vigente" es un DISTINCT ON (material) ORDER BY created_at DESC que
        # ahora discrimina por lista. Sin este indice, cada sugerencia de precio
        # se paga con un scan.
        Index(
            "ix_price_lists_org_group_material_created",
            "organization_id",
            "price_list_group_id",
            "material_id",
            text("created_at DESC"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid4,
    )

    material_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("materials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    purchase_price: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=0,
        comment="Precio de compra por unidad del material",
    )

    sale_price: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=0,
        comment="Precio de venta por unidad del material",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Nota o justificacion del cambio de precio",
    )

    # 🔴 NULL = la lista general de siempre. Ese default es lo que hace que las
    # 3 orgs cliente no cambien en un byte: con la columna en NULL en todas sus
    # filas, filtrar por grupo devuelve exactamente el mismo conjunto que no
    # filtrar. Ver D1 del plan de listas por proveedor.
    price_list_group_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("price_list_groups.id", ondelete="CASCADE"),
        nullable=True,
        comment="Lista a la que pertenece este precio (NULL = lista general)",
    )

    updated_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Usuario que registro este precio",
    )

    # Relaciones
    material: Mapped["Material"] = relationship(
        "Material",
        foreign_keys=[material_id],
    )

    user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[updated_by],
    )

    def __repr__(self) -> str:
        return (
            f"<PriceList(id={self.id}, material_id={self.material_id}, "
            f"purchase={self.purchase_price}, sale={self.sale_price})>"
        )
