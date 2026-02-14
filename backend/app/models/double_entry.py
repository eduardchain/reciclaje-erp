"""
Double-Entry (Pasa Mano) model for simultaneous purchase + sale operations.

A double-entry operation represents buying material from a supplier and
immediately selling it to a customer without the material entering inventory.

Business Flow:
1. Material does NOT enter inventory (no stock movement)
2. Creates linked Purchase record (status='registered', no inventory movement)
3. Creates linked Sale record (status='registered', no inventory movement)
4. Supplier balance increases (we owe them)
5. Customer balance increases (they owe us)
6. Net profit = sale_total - purchase_total - commissions
"""
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Numeric,
    String,
    Text,
    ForeignKey,
    Index,
    Date,
)
from sqlalchemy.dialects.postgresql import UUID as GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrganizationMixin, TimestampMixin


class DoubleEntry(Base, OrganizationMixin, TimestampMixin):
    """
    Double-Entry (Pasa Mano) operation model.
    
    Represents a simultaneous purchase from supplier and sale to customer
    of the same material quantity, without the material entering inventory.
    
    The operation creates linked Purchase and Sale records but does not
    generate inventory movements. Both supplier and customer balances are
    updated accordingly.
    """
    __tablename__ = "double_entries"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    
    # Sequential number per organization
    double_entry_number: Mapped[int] = mapped_column(
        nullable=False,
        comment="Sequential number per organization"
    )
    
    # Operation date
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Date of the double-entry operation"
    )
    
    # Material (single material per operation)
    material_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Material being traded"
    )
    
    # Quantity
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 3),
        nullable=False,
        comment="Quantity of material (must be positive)"
    )
    
    # Purchase side
    supplier_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("third_parties.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Supplier from whom we purchase"
    )
    
    purchase_unit_price: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Purchase price per unit"
    )
    
    # Sale side
    customer_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("third_parties.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Customer to whom we sell"
    )
    
    sale_unit_price: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Sale price per unit"
    )
    
    # Optional fields
    invoice_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Invoice number (optional)"
    )
    
    vehicle_plate: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Vehicle plate for transport (optional)"
    )
    
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes"
    )
    
    # Linked records
    purchase_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("purchases.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        comment="Linked purchase record"
    )
    
    sale_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("sales.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        comment="Linked sale record"
    )
    
    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="completed",
        index=True,
        comment="Status: 'completed' or 'cancelled'"
    )
    
    # Relationships
    material: Mapped["Material"] = relationship(
        "Material",
        foreign_keys=[material_id],
        back_populates="double_entries"
    )
    
    supplier: Mapped["ThirdParty"] = relationship(
        "ThirdParty",
        foreign_keys=[supplier_id],
        back_populates="double_entries_as_supplier"
    )
    
    customer: Mapped["ThirdParty"] = relationship(
        "ThirdParty",
        foreign_keys=[customer_id],
        back_populates="double_entries_as_customer"
    )
    
    purchase: Mapped["Purchase"] = relationship(
        "Purchase",
        foreign_keys=[purchase_id],
        back_populates="double_entry"
    )
    
    sale: Mapped["Sale"] = relationship(
        "Sale",
        foreign_keys=[sale_id],
        back_populates="double_entry"
    )
    
    # Composite indexes for common queries
    __table_args__ = (
        Index("ix_double_entries_org_material", "organization_id", "material_id"),
        Index("ix_double_entries_org_supplier", "organization_id", "supplier_id"),
        Index("ix_double_entries_org_customer", "organization_id", "customer_id"),
        Index("ix_double_entries_org_date", "organization_id", "date"),
        Index("ix_double_entries_org_status", "organization_id", "status"),
        Index("ix_double_entries_date_status", "date", "status"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<DoubleEntry(id={self.id}, number={self.double_entry_number}, "
            f"material_id={self.material_id}, qty={self.quantity}, "
            f"profit={self.profit}, status={self.status})>"
        )
    
    # ========================================================================
    # Calculated Properties
    # ========================================================================
    
    @property
    def total_purchase_cost(self) -> Decimal:
        """
        Calculate total purchase cost.
        
        Returns:
            purchase_unit_price × quantity
        """
        return self.purchase_unit_price * self.quantity
    
    @property
    def total_sale_amount(self) -> Decimal:
        """
        Calculate total sale amount.
        
        Returns:
            sale_unit_price × quantity
        """
        return self.sale_unit_price * self.quantity
    
    @property
    def profit(self) -> Decimal:
        """
        Calculate gross profit (before commissions).
        
        Returns:
            (sale_unit_price - purchase_unit_price) × quantity
        """
        return (self.sale_unit_price - self.purchase_unit_price) * self.quantity
    
    @property
    def profit_margin(self) -> Decimal:
        """
        Calculate profit margin as percentage.
        
        Returns:
            (profit / total_purchase_cost) × 100
            Returns 0 if total_purchase_cost is 0
        """
        if self.total_purchase_cost == 0:
            return Decimal("0.00")
        return (self.profit / self.total_purchase_cost) * Decimal("100")
    
    def calculate_profit(self) -> Decimal:
        """
        Calculate gross profit (method version).
        
        Returns:
            Same as self.profit property
        """
        return self.profit
    
    def calculate_profit_margin(self) -> Decimal:
        """
        Calculate profit margin (method version).
        
        Returns:
            Same as self.profit_margin property
        """
        return self.profit_margin
