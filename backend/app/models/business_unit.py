from uuid import UUID, uuid4
from typing import List, TYPE_CHECKING

from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, OrganizationMixin, GUID

if TYPE_CHECKING:
    from .material import Material


class BusinessUnit(Base, TimestampMixin, OrganizationMixin):
    """
    Business unit model for segmenting operations.
    Used for P&L analysis by unit.
    """
    
    __tablename__ = "business_units"
    
    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid4,
    )
    
    # Organization FK is inherited from OrganizationMixin
    
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # UN de sistema: 'double_entry' = UN Pasa Mano (gastos directos de doble partida).
    # Lookup por codigo, no por nombre — el cliente puede renombrarla.
    # NULL = UN normal creada por el usuario.
    system_code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    
    # Relationships
    materials: Mapped[List["Material"]] = relationship(
        "Material",
        back_populates="business_unit",
    )
    
    def __repr__(self) -> str:
        return f"<BusinessUnit(id={self.id}, name='{self.name}', is_active={self.is_active})>"
