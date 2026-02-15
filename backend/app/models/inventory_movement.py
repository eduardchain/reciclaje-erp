"""
Inventory movement model for tracking material flows.

Records all material movements: purchases, sales, adjustments, transfers, and transformations.
Maintains complete audit trail for inventory tracking and costing.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.material import Material
    from app.models.warehouse import Warehouse


class InventoryMovement(Base, OrganizationMixin, TimestampMixin):
    """
    Inventory movement for tracking material flows.
    
    Movement Types:
    - purchase: Material entering from supplier purchase
    - sale: Material leaving from customer sale
    - adjustment: Manual inventory correction (positive or negative)
    - transfer: Movement between warehouses
    - purchase_reversal: Reversal of purchase (cancelled order)
    - sale_reversal: Reversal of sale (return)
    - transformation: Material converted to another material (Phase 2+)
    
    Reference Types:
    - purchase: Links to Purchase.id
    - sale: Links to Sale.id (Phase 2)
    - adjustment: Manual adjustment (no reference)
    - transfer: Links to Transfer.id (Phase 2)
    - transformation: Links to Transformation.id (Phase 3)
    
    Business Rules:
    - Positive quantity = material entering warehouse (purchase, adjustment+, transfer-in)
    - Negative quantity = material leaving warehouse (sale, adjustment-, transfer-out)
    - Always create movement when material stock changes
    - Reference can be NULL for manual adjustments
    
    TODO Phase 3: Auto-create reversals on purchase/sale cancellation
    """
    __tablename__ = "inventory_movements"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid4,
    )
    
    # Material and location
    material_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Material being moved",
    )
    
    warehouse_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Warehouse where movement occurred",
    )
    
    # Movement details
    movement_type: Mapped[str] = mapped_column(
        Enum(
            "purchase",
            "sale",
            "adjustment",
            "transfer",
            "purchase_reversal",
            "sale_reversal",
            "transformation",
            "adjustment_reversal",
            name="inventory_movement_type",
        ),
        nullable=False,
        index=True,
        comment="Type of inventory movement",
    )
    
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 3),
        nullable=False,
        comment="Quantity moved (positive=in, negative=out)",
    )
    
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Cost per unit at time of movement",
    )
    
    # Reference to source transaction
    reference_type: Mapped[Optional[str]] = mapped_column(
        Enum(
            "purchase",
            "sale",
            "adjustment",
            "transfer",
            "transformation",
            name="inventory_reference_type",
        ),
        nullable=True,
        comment="Type of referenced transaction",
    )
    
    reference_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        nullable=True,
        index=True,
        comment="ID of referenced transaction (NULL for manual adjustments)",
    )
    
    # Metadata
    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Date of movement",
    )
    
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes or reason for movement",
    )
    
    # Relationships
    material: Mapped["Material"] = relationship(
        "Material",
        foreign_keys=[material_id],
        back_populates="inventory_movements",
    )
    
    warehouse: Mapped["Warehouse"] = relationship(
        "Warehouse",
        foreign_keys=[warehouse_id],
        back_populates="inventory_movements",
    )
    
    # Indexes for common queries
    __table_args__ = (
        Index("ix_inventory_movements_org_material", "organization_id", "material_id"),
        Index("ix_inventory_movements_org_warehouse", "organization_id", "warehouse_id"),
        Index("ix_inventory_movements_org_date", "organization_id", "date"),
        Index("ix_inventory_movements_reference", "reference_type", "reference_id"),
        Index("ix_inventory_movements_org_type", "organization_id", "movement_type"),
    )
