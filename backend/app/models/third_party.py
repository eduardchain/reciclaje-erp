from uuid import UUID, uuid4
from decimal import Decimal

from sqlalchemy import String, Boolean, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from .base import Base, TimestampMixin, OrganizationMixin


class ThirdParty(Base, TimestampMixin, OrganizationMixin):
    """
    Third party model for suppliers, customers, investors, and provision accounts.
    Multi-purpose entity that can act as supplier, customer, investor, or provision.
    """
    
    __tablename__ = "third_parties"
    
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    # Organization FK is inherited from OrganizationMixin
    
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    identification_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )
    
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Type flags - a third party can be multiple types
    is_supplier: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    is_customer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    is_investor: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    is_provision: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    provision_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )  # e.g., 'tax', 'employee_benefit', 'other'
    
    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )  # Additional categorization
    
    current_balance: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=0,
    )
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    def __repr__(self) -> str:
        types = []
        if self.is_supplier:
            types.append("Supplier")
        if self.is_customer:
            types.append("Customer")
        if self.is_investor:
            types.append("Investor")
        if self.is_provision:
            types.append("Provision")
        
        type_str = ", ".join(types) if types else "None"
        return f"<ThirdParty(id={self.id}, name='{self.name}', types=[{type_str}])>"
