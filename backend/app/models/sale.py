"""
Sale models for sales and revenue management.

Supports both 1-step and 2-step sale workflows:
- 1-step: Create sale with status='paid' and payment_account_id set
- 2-step: Create with status='registered', later PATCH to 'paid'

Business logic:
- Material exits warehouse immediately (stock decreases)
- unit_cost captured at moment of sale (from Material.current_average_cost)
- Profit per line = (unit_price - unit_cost) × quantity
- Customer balance increases (they owe us)
- Optional commissions (0 to many per sale)
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING, List
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


class Sale(Base, OrganizationMixin, TimestampMixin):
    """
    Sale model for revenue transactions.
    
    Workflow:
    1. Register sale (status='registered'): Inventory exits warehouse, customer balance increases
    2. Collect payment (status='paid'): Payment account credited, sale fully completed
    
    Status transitions:
    - registered → paid (collection)
    - registered → cancelled (reversal)
    - paid → cancelled (reversal with refund logic)
    
    Note: All lines in a sale come from the same warehouse (specified at sale level).
    """
    __tablename__ = "sales"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    
    # Sequential number per organization
    sale_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Sequential sale number within organization (1, 2, 3...)"
    )
    
    # Foreign keys
    customer_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("third_parties.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Customer (ThirdParty with is_customer=True)"
    )
    
    warehouse_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=True,  # NULL for double-entry operations (no physical inventory)
        index=True,
        comment="Source warehouse for sale lines. NULL for double-entry operations."
    )
    
    payment_account_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("money_accounts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="Payment account (set when status='paid')"
    )
    
    # Sale details
    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Sale date"
    )
    
    vehicle_plate: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Vehicle plate number for delivery/pickup"
    )
    
    invoice_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Invoice or bill number"
    )
    
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total sale amount (sum of all lines)"
    )
    
    status: Mapped[str] = mapped_column(
        Enum("registered", "liquidated", "cancelled", name="sale_status"),
        nullable=False,
        default="registered",
        index=True,
        comment="Sale status: registered | liquidated (confirmada, cliente debe) | cancelled"
    )
    
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes or observations"
    )

    # Audit and traceability fields
    created_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who created the sale"
    )

    liquidated_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who liquidated/collected the sale"
    )

    updated_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who last edited the sale"
    )

    liquidated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the sale was liquidated"
    )

    cancelled_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who cancelled the sale"
    )

    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the sale was cancelled"
    )

    # Double-entry link (optional)
    double_entry_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("double_entries.id", ondelete="SET NULL"),
        nullable=True,
        comment="Link to double-entry operation if applicable"
    )
    
    # Relationships
    customer: Mapped["ThirdParty"] = relationship(
        "ThirdParty",
        foreign_keys=[customer_id],
        back_populates="sales"
    )
    
    warehouse: Mapped["Warehouse"] = relationship(
        "Warehouse",
        foreign_keys=[warehouse_id],
        back_populates="sales"
    )
    
    payment_account: Mapped[Optional["MoneyAccount"]] = relationship(
        "MoneyAccount",
        foreign_keys=[payment_account_id],
        back_populates="sales"
    )
    
    lines: Mapped[List["SaleLine"]] = relationship(
        "SaleLine",
        back_populates="sale",
        cascade="all, delete-orphan",
        order_by="SaleLine.created_at"
    )
    
    commissions: Mapped[List["SaleCommission"]] = relationship(
        "SaleCommission",
        back_populates="sale",
        cascade="all, delete-orphan",
        order_by="SaleCommission.created_at"
    )
    
    double_entry: Mapped[Optional["DoubleEntry"]] = relationship(
        "DoubleEntry",
        foreign_keys="[DoubleEntry.sale_id]",
        back_populates="sale",
        uselist=False,
    )
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "sale_number",
            name="uq_sales_org_number"
        ),
        Index("ix_sales_org_customer", "organization_id", "customer_id"),
        Index("ix_sales_org_warehouse", "organization_id", "warehouse_id"),
        Index("ix_sales_org_status", "organization_id", "status"),
        Index("ix_sales_org_date", "organization_id", "date"),
        Index("ix_sales_date_status", "date", "status"),
    )
    
    def __repr__(self) -> str:
        return f"<Sale(id={self.id}, number={self.sale_number}, status={self.status}, total={self.total_amount})>"
    
    def calculate_total(self) -> Decimal:
        """
        Calculate total amount from all sale lines.
        
        Returns:
            Total amount (sum of line.total_price)
        """
        return sum(
            (line.total_price for line in self.lines),
            start=Decimal("0.00")
        )
    
    def calculate_total_profit(self) -> Decimal:
        """
        Calculate total profit from all sale lines.
        
        Returns:
            Total profit (sum of line.calculate_profit())
        """
        return sum(
            (line.calculate_profit() for line in self.lines),
            start=Decimal("0.00")
        )
    
    def calculate_total_cost(self) -> Decimal:
        """
        Calculate total cost from all sale lines.
        
        Returns:
            Total cost (sum of line.unit_cost × line.quantity)
        """
        return sum(
            (line.unit_cost * line.quantity for line in self.lines),
            start=Decimal("0.00")
        )


class SaleLine(Base, TimestampMixin):
    """
    Sale line item linking a sale to a material with quantity and pricing.
    
    Each line represents one material sold with its quantity, price, and cost.
    The unit_cost is captured at the moment of sale for profit calculation.
    """
    __tablename__ = "sale_lines"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    
    # Foreign keys
    sale_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("sales.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    material_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    
    # Line details
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 3),
        nullable=False,
        comment="Quantity sold (must be positive)"
    )

    received_quantity: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 3),
        nullable=True,
        default=None,
        comment="Cantidad recibida por el cliente (si difiere de quantity)",
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Selling price per unit"
    )
    
    total_price: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Total line price (quantity × unit_price)"
    )
    
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average cost at moment of sale (for profit calculation)"
    )
    
    # Relationships
    sale: Mapped["Sale"] = relationship(
        "Sale",
        back_populates="lines"
    )
    
    material: Mapped["Material"] = relationship(
        "Material",
        back_populates="sale_lines"
    )
    
    def __repr__(self) -> str:
        return f"<SaleLine(id={self.id}, material_id={self.material_id}, qty={self.quantity}, price={self.unit_price})>"
    
    def calculate_line_total(self) -> Decimal:
        """
        Calculate total price for this line.
        
        Returns:
            quantity × unit_price
        """
        return self.quantity * self.unit_price
    
    def calculate_profit(self) -> Decimal:
        """
        Calculate profit for this line.

        Returns:
            total_price - (unit_cost × quantity)
            Usa total_price que ya refleja received_quantity si aplica.
        """
        return self.total_price - (self.unit_cost * self.quantity)
    
    def calculate_profit_margin(self) -> Decimal:
        """
        Calculate profit margin percentage for this line.
        
        Returns:
            ((unit_price - unit_cost) / unit_price) × 100
            Returns 0 if unit_price is 0
        """
        if self.unit_price == 0:
            return Decimal("0.00")
        return ((self.unit_price - self.unit_cost) / self.unit_price) * Decimal("100")


class SaleCommission(Base, TimestampMixin):
    """
    Sale commission for third parties (salespeople, brokers, etc.).
    
    Commissions can be:
    - percentage: A percentage of the sale total (e.g., 5% = 5.00)
    - fixed: A fixed amount (e.g., $100.00)
    
    Multiple commissions can be assigned to a single sale.
    """
    __tablename__ = "sale_commissions"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    
    # Foreign keys
    sale_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("sales.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    third_party_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("third_parties.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Person/entity receiving the commission"
    )
    
    # Commission details
    concept: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Commission description (e.g., 'Comisión facturación', 'Intermediario')"
    )
    
    commission_type: Mapped[str] = mapped_column(
        Enum("percentage", "fixed", "per_kg", name="commission_type"),
        nullable=False,
        comment="percentage (of sale total) or fixed amount"
    )
    
    commission_value: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Percentage (0-100) or fixed amount"
    )
    
    commission_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Calculated commission amount"
    )
    
    # Relationships
    sale: Mapped["Sale"] = relationship(
        "Sale",
        back_populates="commissions"
    )
    
    third_party: Mapped["ThirdParty"] = relationship(
        "ThirdParty",
        foreign_keys=[third_party_id],
        back_populates="sale_commissions"
    )
    
    def __repr__(self) -> str:
        return f"<SaleCommission(id={self.id}, concept='{self.concept}', type={self.commission_type}, amount={self.commission_amount})>"
    
    def calculate_commission_amount(self, sale_total: Decimal) -> Decimal:
        """
        Calculate commission amount based on type and value.
        
        Args:
            sale_total: Total amount of the sale
            
        Returns:
            Calculated commission amount
        """
        if self.commission_type == "percentage":
            return (sale_total * self.commission_value) / Decimal("100")
        else:  # fixed
            return self.commission_value
