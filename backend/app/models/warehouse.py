from uuid import UUID, uuid4

from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, OrganizationMixin, GUID


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
    
    def __repr__(self) -> str:
        return f"<Warehouse(id={self.id}, name='{self.name}', is_active={self.is_active})>"
