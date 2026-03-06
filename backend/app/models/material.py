from uuid import UUID, uuid4
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Boolean, Integer, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, OrganizationMixin, GUID

if TYPE_CHECKING:
    from app.models.inventory_movement import InventoryMovement
    from app.models.business_unit import BusinessUnit
    from app.models.sale import SaleLine
    from app.models.material_cost_history import MaterialCostHistory


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
        comment="Total stock (liquidated + transit). Maintained for backward compat.",
    )

    current_stock_liquidated: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        default=0,
        comment="Stock from liquidated (paid) purchases. Available for sale.",
    )

    current_stock_transit: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        default=0,
        comment="Stock from registered (unpaid) purchases. Not yet available for sale.",
    )

    current_average_cost: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        default=0,
    )

    sort_order: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Display order in lists (lower = first)",
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
    
    inventory_movements: Mapped[list["InventoryMovement"]] = relationship(
        "InventoryMovement",
        back_populates="material",
        order_by="InventoryMovement.date.desc()",
    )
    
    sale_lines: Mapped[list["SaleLine"]] = relationship(
        "SaleLine",
        foreign_keys="SaleLine.material_id",
        back_populates="material",
    )
    
    double_entries: Mapped[list["DoubleEntry"]] = relationship(
        "DoubleEntry",
        foreign_keys="DoubleEntry.material_id",
        back_populates="material",
    )

    cost_history: Mapped[list["MaterialCostHistory"]] = relationship(
        "MaterialCostHistory",
        back_populates="material",
        order_by="MaterialCostHistory.created_at.desc()",
    )
    
    def __repr__(self) -> str:
        return f"<Material(id={self.id}, code='{self.code}', name='{self.name}', stock={self.current_stock})>"
