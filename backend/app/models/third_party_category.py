"""
Modelo ThirdPartyCategory — Categorias de terceros con behavior_type.

Permite clasificar terceros por tipo de comportamiento:
- material_supplier: proveedor de material (aparece en compras)
- service_provider: proveedor de servicios (aparece en gastos)
- customer: cliente (aparece en ventas)
- investor: inversionista/socio
- generic: cuenta genérica (empleados, proyectos, varios)
- provision: provision (fondos reservados)

Maxima jerarquia: 2 niveles (categoria > subcategoria).
Subcategoria hereda behavior_type del padre.
"""
import enum
from uuid import UUID, uuid4
from typing import Optional

from sqlalchemy import String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, OrganizationMixin, GUID


class BehaviorType(str, enum.Enum):
    """Tipos de comportamiento para categorias de terceros."""
    material_supplier = "material_supplier"
    service_provider = "service_provider"
    customer = "customer"
    investor = "investor"
    generic = "generic"
    provision = "provision"


class ThirdPartyCategory(Base, TimestampMixin, OrganizationMixin):
    """
    Categoria de tercero con behavior_type.

    behavior_type determina donde aparece el tercero en la UI
    y como se clasifica en reportes financieros.
    """

    __tablename__ = "third_party_categories"

    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )

    description: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
    )

    parent_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("third_party_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="ID de la categoria padre (max 2 niveles).",
    )

    behavior_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Tipo de comportamiento. Obligatorio en nivel 1, heredado en nivel 2.",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
    )

    parent: Mapped[Optional["ThirdPartyCategory"]] = relationship(
        "ThirdPartyCategory",
        remote_side="ThirdPartyCategory.id",
        foreign_keys="ThirdPartyCategory.parent_id",
    )

    def __repr__(self) -> str:
        return f"<ThirdPartyCategory(id={self.id}, name='{self.name}', behavior={self.behavior_type})>"


class ThirdPartyCategoryAssignment(Base):
    """Relacion M:N entre ThirdParty y ThirdPartyCategory."""

    __tablename__ = "third_party_category_assignments"

    __table_args__ = (
        UniqueConstraint("third_party_id", "category_id", name="uq_tp_category_assignment"),
    )

    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid4,
    )

    third_party_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("third_parties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    category_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("third_party_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    category: Mapped["ThirdPartyCategory"] = relationship(
        "ThirdPartyCategory",
        foreign_keys="ThirdPartyCategoryAssignment.category_id",
    )
