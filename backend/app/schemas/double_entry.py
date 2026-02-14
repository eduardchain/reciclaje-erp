"""
Pydantic schemas for DoubleEntry (Pasa Mano) model.

A double-entry operation represents a simultaneous purchase from supplier
and sale to customer without the material entering inventory.
"""
from datetime import date as date_type, datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer, model_validator

from app.schemas.sale import SaleCommissionCreate, SaleCommissionResponse


# ============================================================================
# DoubleEntry Schemas
# ============================================================================

class DoubleEntryBase(BaseModel):
    """Base schema for DoubleEntry."""
    material_id: UUID = Field(..., description="Material UUID")
    quantity: Decimal = Field(..., gt=0, description="Quantity traded (must be positive)")
    supplier_id: UUID = Field(..., description="Supplier UUID (must have is_supplier=True)")
    purchase_unit_price: Decimal = Field(..., gt=0, description="Purchase price per unit (must be positive)")
    customer_id: UUID = Field(..., description="Customer UUID (must have is_customer=True)")
    sale_unit_price: Decimal = Field(..., gt=0, description="Sale price per unit (must be positive)")
    date: date_type = Field(..., description="Date of the double-entry operation")
    invoice_number: Optional[str] = Field(None, max_length=50, description="Invoice number (optional)")
    vehicle_plate: Optional[str] = Field(None, max_length=20, description="Vehicle plate for transport (optional)")
    notes: Optional[str] = Field(None, max_length=1000, description="Additional notes")


class DoubleEntryCreate(DoubleEntryBase):
    """
    Schema for creating a DoubleEntry.
    
    Validation:
    - supplier_id != customer_id (cannot buy and sell to the same party)
    - purchase_unit_price > 0
    - sale_unit_price > 0
    - quantity > 0
    
    Business Flow:
    1. Creates Purchase (status='registered', no inventory movement)
    2. Creates Sale (status='registered', no inventory movement)
    3. Updates supplier balance (debt increases)
    4. Updates customer balance (receivable increases)
    5. Creates commissions (if provided, but balances not updated until sale liquidation)
    """
    commissions: List[SaleCommissionCreate] = Field(
        default_factory=list,
        description="Optional sale commissions (balances updated when sale is liquidated)"
    )
    
    @model_validator(mode='after')
    def validate_supplier_not_customer(self):
        """Validate that supplier and customer are different parties."""
        if self.supplier_id == self.customer_id:
            raise ValueError("Supplier and customer cannot be the same third party")
        return self


class DoubleEntryUpdate(BaseModel):
    """
    Schema for updating a DoubleEntry (partial updates only).
    
    Note: Only metadata can be updated. Status changes via /cancel endpoint.
    """
    notes: Optional[str] = Field(None, max_length=1000)
    invoice_number: Optional[str] = Field(None, max_length=50)
    vehicle_plate: Optional[str] = Field(None, max_length=20)


class DoubleEntryResponse(DoubleEntryBase):
    """Schema for DoubleEntry responses with all details."""
    id: UUID
    organization_id: UUID
    double_entry_number: int = Field(..., description="Sequential number within organization")
    purchase_id: UUID = Field(..., description="Linked purchase record UUID")
    sale_id: UUID = Field(..., description="Linked sale record UUID")
    status: str = Field(..., description="completed | cancelled")
    
    # Calculated properties
    total_purchase_cost: float = Field(..., description="purchase_unit_price × quantity")
    total_sale_amount: float = Field(..., description="sale_unit_price × quantity")
    profit: float = Field(..., description="(sale_unit_price - purchase_unit_price) × quantity")
    profit_margin: float = Field(..., description="(profit / total_purchase_cost) × 100")
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    
    # Joined data from related models
    material_code: str = Field(..., description="Material code (e.g., MAT-001)")
    material_name: str = Field(..., description="Material name")
    supplier_name: str = Field(..., description="Supplier name")
    customer_name: str = Field(..., description="Customer name")
    
    # Commissions from linked sale
    commissions: List[SaleCommissionResponse] = Field(
        default_factory=list,
        description="Sale commissions (paid when sale is liquidated)"
    )
    
    model_config = {"from_attributes": True}
    
    @field_serializer(
        'quantity',
        'purchase_unit_price',
        'sale_unit_price',
        'total_purchase_cost',
        'total_sale_amount',
        'profit',
        'profit_margin'
    )
    def serialize_decimals(self, value: Decimal) -> float:
        """Convert Decimal to float for JSON serialization."""
        return float(value)


class PaginatedDoubleEntryResponse(BaseModel):
    """Paginated response for double-entry lists."""
    items: List[DoubleEntryResponse]
    total: int
    skip: int
    limit: int
