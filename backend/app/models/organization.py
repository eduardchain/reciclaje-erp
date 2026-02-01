from uuid import UUID, uuid4
from typing import List

from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from .base import Base, TimestampMixin


class Organization(Base, TimestampMixin):
    """Organization model for multi-tenant support."""
    
    __tablename__ = "organizations"
    
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
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
    
    # Relationships
    members: Mapped[List["OrganizationMember"]] = relationship(
        "OrganizationMember",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name='{self.name}', slug='{self.slug}')>"
