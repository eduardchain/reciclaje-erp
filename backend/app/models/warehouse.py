from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, OrganizationMixin, GUID

if TYPE_CHECKING:
    from app.models.inventory_movement import InventoryMovement
    from app.models.sale import Sale


class Warehouse(Base, TimestampMixin, OrganizationMixin):
    """
    Warehouse/Storage location model.
    Used for multi-warehouse inventory management.
    """
    
    __tablename__ = "warehouses"
    
    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid4,
    )
    
    # Organization FK is inherited from OrganizationMixin
    
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    inventory_movements: Mapped[list["InventoryMovement"]] = relationship(
        "InventoryMovement",
        back_populates="warehouse",
        order_by="InventoryMovement.date.desc()",
    )
    
    sales: Mapped[list["Sale"]] = relationship(
        "Sale",
        foreign_keys="Sale.warehouse_id",
        back_populates="warehouse",
    )
    
    def __repr__(self) -> str:
        return f"<Warehouse(id={self.id}, name='{self.name}', is_active={self.is_active})>"
