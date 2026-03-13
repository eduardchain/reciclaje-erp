"""Modelo Permission — catalogo global de permisos del sistema."""
from uuid import UUID, uuid4

from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, GUID


class Permission(Base):
    """Permiso del sistema — catalogo global, no por organizacion."""

    __tablename__ = "permissions"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    module: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    roles: Mapped[list["RolePermission"]] = relationship(
        "RolePermission", back_populates="permission"
    )
