"""
Pydantic schemas for Purchase and PurchaseLine models.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer, model_validator


# ============================================================================
# PurchaseLine Schemas
# ============================================================================

class PurchaseLineBase(BaseModel):
    """Base schema for PurchaseLine."""
    material_id: UUID = Field(..., description="Material UUID")
    quantity: Decimal = Field(..., gt=0, description="Quantity purchased (must be positive)")
    unit_price: Decimal = Field(..., ge=0, description="Price per unit")
    warehouse_id: UUID = Field(..., description="Destination warehouse UUID")


class PurchaseLineCreate(PurchaseLineBase):
    """
    Schema for creating a PurchaseLine.
    
    Note: total_price is calculated automatically (quantity × unit_price)
    """
    pass


class PurchaseLineResponse(PurchaseLineBase):
    """Schema for PurchaseLine responses with joined data."""
    id: UUID
    purchase_id: UUID
    total_price: float
    created_at: datetime
    
    # Joined data from related models
    material_code: str = Field(..., description="Material code (e.g., MAT-001)")
    material_name: str = Field(..., description="Material name")
    warehouse_name: str = Field(..., description="Warehouse name")
    
    model_config = {"from_attributes": True}
    
    @field_serializer('quantity', 'unit_price', 'total_price')
    def serialize_decimals(self, value: Decimal) -> float:
        """Convert Decimal to float for JSON serialization."""
        return float(value)


# ============================================================================
# Purchase Schemas
# ============================================================================

class PurchaseBase(BaseModel):
    """Base schema for Purchase."""
    supplier_id: UUID = Field(..., description="Supplier UUID (must have is_supplier=True)")
    date: datetime = Field(..., description="Purchase date (weighing date)")
    notes: Optional[str] = Field(None, max_length=1000, description="Additional notes")


class PurchaseCreate(PurchaseBase):
    """
    Schema for creating a Purchase.
    
    Workflow:
    - auto_liquidate=False: Creates purchase with status='registered', liquidate later
    - auto_liquidate=True: Creates and liquidates in one step (1-step workflow)
    
    Validation:
    - If auto_liquidate=True, payment_account_id is required
    """
    lines: List[PurchaseLineCreate] = Field(..., min_length=1, description="Purchase lines (at least 1)")
    auto_liquidate: bool = Field(False, description="Auto-liquidate after creation (1-step workflow)")
    payment_account_id: Optional[UUID] = Field(None, description="Payment account (required if auto_liquidate=True)")
    
    @model_validator(mode='after')
    def validate_auto_liquidate(self):
        """Validate that payment_account_id is provided when auto_liquidate=True."""
        if self.auto_liquidate and not self.payment_account_id:
            raise ValueError("payment_account_id is required when auto_liquidate=True")
        return self


class PurchaseUpdate(BaseModel):
    """
    Schema for updating a Purchase (partial updates only).
    
    Note: Only metadata can be updated, not lines or amounts.
    """
    notes: Optional[str] = Field(None, max_length=1000)
    date: Optional[datetime] = None


class PurchaseResponse(PurchaseBase):
    """Schema for Purchase responses with all details."""
    id: UUID
    organization_id: UUID
    purchase_number: int
    total_amount: float
    status: str = Field(..., description="registered | paid | cancelled")
    payment_account_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    
    # Joined data from related models
    supplier_name: str = Field(..., description="Supplier name")
    payment_account_name: Optional[str] = Field(None, description="Payment account name (if liquidated)")
    
    # Nested lines with joined data
    lines: List[PurchaseLineResponse] = Field(..., description="Purchase lines")
    
    model_config = {"from_attributes": True}
    
    @field_serializer('total_amount')
    def serialize_decimal(self, value: Decimal) -> float:
        """Convert Decimal to float for JSON serialization."""
        return float(value)


class PurchaseLiquidateRequest(BaseModel):
    """Schema for liquidating a purchase (2-step workflow)."""
    payment_account_id: UUID = Field(..., description="Payment account to deduct funds from")


class PaginatedPurchaseResponse(BaseModel):
    """Paginated response for purchase lists."""
    items: List[PurchaseResponse]
    total: int
    skip: int
    limit: int
