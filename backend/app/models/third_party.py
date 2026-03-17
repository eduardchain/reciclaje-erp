from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from decimal import Decimal

from sqlalchemy import String, Boolean, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, OrganizationMixin, GUID

if TYPE_CHECKING:
    from app.models.purchase import Purchase
    from app.models.sale import Sale, SaleCommission
    from app.models.third_party_category import ThirdPartyCategoryAssignment


class ThirdParty(Base, TimestampMixin, OrganizationMixin):
    """
    Third party model for suppliers, customers, investors, and provision accounts.
    Multi-purpose entity that can act as supplier, customer, investor, or provision.
    """
    
    __tablename__ = "third_parties"
    
    id: Mapped[UUID] = mapped_column(
        GUID(),
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
    
    is_system_entity: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    provision_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )  # e.g., 'tax', 'employee_benefit', 'other'
    
    initial_balance: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=0,
    )

    current_balance: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=0,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    purchases: Mapped[list["Purchase"]] = relationship(
        "Purchase",
        foreign_keys="Purchase.supplier_id",
        back_populates="supplier",
    )
    
    sales: Mapped[list["Sale"]] = relationship(
        "Sale",
        foreign_keys="Sale.customer_id",
        back_populates="customer",
    )
    
    sale_commissions: Mapped[list["SaleCommission"]] = relationship(
        "SaleCommission",
        foreign_keys="SaleCommission.third_party_id",
        back_populates="third_party",
    )

    purchase_commissions: Mapped[list["PurchaseCommission"]] = relationship(
        "PurchaseCommission",
        foreign_keys="PurchaseCommission.third_party_id",
        back_populates="third_party",
    )
    
    category_assignments: Mapped[list["ThirdPartyCategoryAssignment"]] = relationship(
        "ThirdPartyCategoryAssignment",
        cascade="all, delete-orphan",
    )

    double_entries_as_supplier: Mapped[list["DoubleEntry"]] = relationship(
        "DoubleEntry",
        foreign_keys="DoubleEntry.supplier_id",
        back_populates="supplier",
    )
    
    double_entries_as_customer: Mapped[list["DoubleEntry"]] = relationship(
        "DoubleEntry",
        foreign_keys="DoubleEntry.customer_id",
        back_populates="customer",
    )
    
    def __repr__(self) -> str:
        return f"<ThirdParty(id={self.id}, name='{self.name}')>"
