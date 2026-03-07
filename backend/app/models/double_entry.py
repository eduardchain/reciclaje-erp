"""
Double-Entry (Pasa Mano) model for simultaneous purchase + sale operations.

Soporta multiples materiales por operacion via DoubleEntryLine.

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
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Numeric,
    String,
    Text,
    ForeignKey,
    Index,
    Date,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrganizationMixin, TimestampMixin, GUID

if TYPE_CHECKING:
    from app.models.material import Material
    from app.models.third_party import ThirdParty
    from app.models.purchase import Purchase
    from app.models.sale import Sale


class DoubleEntryLine(Base, TimestampMixin):
    """Linea de doble partida — un material con precios de compra y venta."""
    __tablename__ = "double_entry_lines"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    double_entry_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("double_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    material_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 3),
        nullable=False,
        comment="Cantidad del material (positiva)",
    )

    purchase_unit_price: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Precio de compra por unidad",
    )

    sale_unit_price: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Precio de venta por unidad",
    )

    # Relationships
    double_entry: Mapped["DoubleEntry"] = relationship(
        "DoubleEntry", back_populates="lines"
    )
    material: Mapped["Material"] = relationship("Material", back_populates="double_entry_lines")

    @property
    def total_purchase(self) -> Decimal:
        return self.purchase_unit_price * self.quantity

    @property
    def total_sale(self) -> Decimal:
        return self.sale_unit_price * self.quantity

    @property
    def profit(self) -> Decimal:
        return (self.sale_unit_price - self.purchase_unit_price) * self.quantity


class DoubleEntry(Base, OrganizationMixin, TimestampMixin):
    """
    Double-Entry (Pasa Mano) operation model.

    Representa compra+venta simultanea de uno o mas materiales
    sin que el material entre a inventario.
    """
    __tablename__ = "double_entries"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    double_entry_number: Mapped[int] = mapped_column(
        nullable=False,
        comment="Sequential number per organization"
    )

    date: Mapped[date] = mapped_column(
        Date, nullable=False, index=True,
        comment="Date of the double-entry operation"
    )

    # Purchase side
    supplier_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("third_parties.id", ondelete="RESTRICT"),
        nullable=False, index=True,
        comment="Supplier from whom we purchase"
    )

    # Sale side
    customer_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("third_parties.id", ondelete="RESTRICT"),
        nullable=False, index=True,
        comment="Customer to whom we sell"
    )

    # Optional fields
    invoice_number: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="Invoice number (optional)"
    )

    vehicle_plate: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="Vehicle plate for transport (optional)"
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Additional notes"
    )

    # Linked records
    purchase_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("purchases.id", ondelete="RESTRICT"),
        nullable=False, unique=True,
        comment="Linked purchase record"
    )

    sale_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("sales.id", ondelete="RESTRICT"),
        nullable=False, unique=True,
        comment="Linked sale record"
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="completed", index=True,
        comment="Status: 'completed' or 'cancelled'"
    )

    # Relationships
    lines: Mapped[list["DoubleEntryLine"]] = relationship(
        "DoubleEntryLine",
        back_populates="double_entry",
        cascade="all, delete-orphan",
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

    __table_args__ = (
        Index("ix_double_entries_org_supplier", "organization_id", "supplier_id"),
        Index("ix_double_entries_org_customer", "organization_id", "customer_id"),
        Index("ix_double_entries_org_date", "organization_id", "date"),
        Index("ix_double_entries_org_status", "organization_id", "status"),
        Index("ix_double_entries_date_status", "date", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<DoubleEntry(id={self.id}, number={self.double_entry_number}, "
            f"lines={len(self.lines) if self.lines else 0}, "
            f"profit={self.profit}, status={self.status})>"
        )

    # ========================================================================
    # Calculated Properties (agregados desde lineas)
    # ========================================================================

    @property
    def total_purchase_cost(self) -> Decimal:
        return sum((line.total_purchase for line in self.lines), Decimal("0"))

    @property
    def total_sale_amount(self) -> Decimal:
        return sum((line.total_sale for line in self.lines), Decimal("0"))

    @property
    def profit(self) -> Decimal:
        return sum((line.profit for line in self.lines), Decimal("0"))

    @property
    def profit_margin(self) -> Decimal:
        total_cost = self.total_purchase_cost
        if total_cost == 0:
            return Decimal("0.00")
        return (self.profit / total_cost) * Decimal("100")
