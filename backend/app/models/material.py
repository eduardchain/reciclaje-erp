from uuid import UUID, uuid4
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, Boolean, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, OrganizationMixin, GUID


class MaterialCategory(Base, TimestampMixin, OrganizationMixin):
    """Material category for grouping materials."""
    
    __tablename__ = "material_categories"
    
    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid4,
    )
    
    # Organization FK is inherited from OrganizationMixin
    
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    materials: Mapped[list["Material"]] = relationship(
        "Material",
        back_populates="category",
    )
    
    def __repr__(self) -> str:
        return f"<MaterialCategory(id={self.id}, name='{self.name}')>"


class Material(Base, TimestampMixin, OrganizationMixin):
    """
    Material model for recyclable materials (metals, plastics, etc.).
    Tracks inventory with moving average cost.
    """
    
    __tablename__ = "materials"
    
    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid4,
    )
    
    # Organization FK is inherited from OrganizationMixin
    
    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    category_id: Mapped[UUID | None] = mapped_column(
        GUID(),
        ForeignKey("material_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    business_unit_id: Mapped[UUID | None] = mapped_column(
        GUID(),
        ForeignKey("business_units.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    default_unit: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="kg",
    )  # e.g., 'kg', 'ton', 'unit'
    
    current_stock: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        default=0,
    )
    
    current_average_cost: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        default=0,
    )
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    category: Mapped[Optional["MaterialCategory"]] = relationship(
        "MaterialCategory",
        back_populates="materials",
    )
    
    business_unit: Mapped[Optional["BusinessUnit"]] = relationship(
        "BusinessUnit",
        back_populates="materials",
    )
    
    def __repr__(self) -> str:
        return f"<Material(id={self.id}, code='{self.code}', name='{self.name}', stock={self.current_stock})>"
