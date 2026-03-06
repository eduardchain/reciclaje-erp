"""
Purchase models for procurement and inventory management.

Supports both 1-step and 2-step purchase workflows:
- 1-step: Create purchase with status='paid' and payment_account_id set
- 2-step: Create with status='registered', later PATCH to 'paid'
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID as GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.third_party import ThirdParty
    from app.models.money_account import MoneyAccount
    from app.models.material import Material
    from app.models.warehouse import Warehouse


class Purchase(Base, OrganizationMixin, TimestampMixin):
    """
    Purchase model for procurement transactions.
    
    Workflow:
    1. Register purchase (status='registered'): Inventory enters warehouse, supplier balance increases
    2. Liquidate (status='paid'): Payment account deducted, purchase fully completed
    
    Status transitions:
    - registered → paid (liquidation)
    - registered → cancelled (reversal)
    - paid → cancelled (reversal with refund logic)
    """
    __tablename__ = "purchases"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid4,
    )
    
    # Primary fields
    purchase_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Sequential number per organization (1, 2, 3...)",
    )
    
    supplier_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("third_parties.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Supplier (must have is_supplier=True)",
    )
    
    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Purchase date (weighing date, not payment date)",
    )
    
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=0,
        comment="Total purchase amount (sum of all line totals)",
    )
    
    status: Mapped[str] = mapped_column(
        Enum("registered", "paid", "cancelled", name="purchase_status"),
        nullable=False,
        default="registered",
        index=True,
        comment="registered=pending payment, paid=completed, cancelled=voided",
    )
    
    payment_account_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("money_accounts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="Account used for payment (required when status='paid')",
    )
    
    # Double-entry link (optional)
    double_entry_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("double_entries.id", ondelete="SET NULL"),
        nullable=True,
        comment="Link to double-entry operation if applicable",
    )
    
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes or observations",
    )

    # Audit and traceability fields
    vehicle_plate: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Vehicle plate number for delivery",
    )

    invoice_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Invoice or bill number",
    )

    created_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who created the purchase (weighing operator)",
    )

    liquidated_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who liquidated/paid the purchase",
    )

    liquidated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the purchase was liquidated/paid",
    )

    updated_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who last edited the purchase",
    )

    # Relationships
    supplier: Mapped["ThirdParty"] = relationship(
        "ThirdParty",
        foreign_keys=[supplier_id],
        back_populates="purchases",
    )

    payment_account: Mapped[Optional["MoneyAccount"]] = relationship(
        "MoneyAccount",
        foreign_keys=[payment_account_id],
        back_populates="purchases",
    )

    lines: Mapped[list["PurchaseLine"]] = relationship(
        "PurchaseLine",
        back_populates="purchase",
        cascade="all, delete-orphan",
        order_by="PurchaseLine.created_at",
    )

    double_entry: Mapped[Optional["DoubleEntry"]] = relationship(
        "DoubleEntry",
        foreign_keys="[DoubleEntry.purchase_id]",
        back_populates="purchase",
        uselist=False,
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "purchase_number",
            name="uq_purchase_number_per_org",
        ),
        Index("ix_purchases_org_status", "organization_id", "status"),
        Index("ix_purchases_org_date", "organization_id", "date"),
        Index("ix_purchases_org_supplier", "organization_id", "supplier_id"),
    )
    
    def calculate_total(self) -> Decimal:
        """
        Calculate total amount from all purchase lines.
        
        Returns:
            Total amount (sum of quantity × unit_price for all lines)
        """
        if not self.lines:
            return Decimal("0.00")
        
        return sum(
            (line.calculate_line_total() for line in self.lines),
            start=Decimal("0.00")
        )


class PurchaseLine(Base, TimestampMixin):
    """
    Purchase line item with material, quantity, price, and destination warehouse.
    
    Note: Each line can go to a different warehouse.
    Example: Scrap metal → Warehouse A, Copper → Warehouse B
    """
    __tablename__ = "purchase_lines"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid4,
    )
    
    # Foreign keys
    purchase_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("purchases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    material_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    
    warehouse_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="Warehouse (nullable for double-entry operations)",
    )
    
    # Line details
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 3),
        nullable=False,
        comment="Quantity purchased (allows decimals: 150.500 kg)",
    )
    
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Price per unit",
    )
    
    total_price: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Line total (quantity × unit_price)",
    )
    
    # Relationships
    purchase: Mapped["Purchase"] = relationship(
        "Purchase",
        back_populates="lines",
    )
    
    material: Mapped["Material"] = relationship(
        "Material",
        foreign_keys=[material_id],
    )
    
    warehouse: Mapped[Optional["Warehouse"]] = relationship(
        "Warehouse",
        foreign_keys=[warehouse_id],
    )
    
    # Indexes
    __table_args__ = (
        Index("ix_purchase_lines_purchase", "purchase_id"),
        Index("ix_purchase_lines_material", "material_id"),
        Index("ix_purchase_lines_warehouse", "warehouse_id"),
    )
    
    def calculate_line_total(self) -> Decimal:
        """
        Calculate line total from quantity and unit price.
        
        Returns:
            Decimal: quantity × unit_price
        """
        return self.quantity * self.unit_price
