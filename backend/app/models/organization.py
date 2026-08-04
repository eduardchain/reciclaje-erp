from uuid import UUID, uuid4
from typing import List

from sqlalchemy import Boolean, String, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, GUID


class Organization(Base, TimestampMixin):
    """Organization model for multi-tenant support."""
    
    __tablename__ = "organizations"
    
    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid4,
    )
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    subscription_plan: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="basic",
    )
    
    subscription_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="active",
    )
    
    max_users: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    settings: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Flags y parametros por org (SAC E1, D3). NULL = flags apagados y "
        "parametros en default. Escritura REPLACE del dict completo, solo superuser. "
        "Sin MutableDict: toda escritura reasigna el dict completo",
    )

    # Relationships
    members: Mapped[List["OrganizationMember"]] = relationship(
        "OrganizationMember",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    roles: Mapped[List["Role"]] = relationship(
        "Role",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name='{self.name}', slug='{self.slug}')>"
