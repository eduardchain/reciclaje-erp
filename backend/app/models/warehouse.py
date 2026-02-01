from uuid import UUID, uuid4

from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from .base import Base, TimestampMixin, OrganizationMixin


class Warehouse(Base, TimestampMixin, OrganizationMixin):
    """
    Warehouse/Storage location model.
    Used for multi-warehouse inventory management.
    """
    
    __tablename__ = "warehouses"
    
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
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
