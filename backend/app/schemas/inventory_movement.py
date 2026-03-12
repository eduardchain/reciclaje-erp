"""
Pydantic schemas for InventoryMovement model.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer

from app.utils.dates import BusinessDate


class InventoryMovementBase(BaseModel):
    """Base schema for InventoryMovement."""
    material_id: UUID = Field(..., description="Material UUID")
    warehouse_id: UUID = Field(..., description="Warehouse UUID")
    movement_type: str = Field(
        ...,
        description="Movement type: purchase | sale | adjustment | transfer | purchase_reversal | sale_reversal | transformation"
    )
    quantity: Decimal = Field(..., description="Quantity moved (positive=in, negative=out)")
    unit_cost: Decimal = Field(..., ge=0, description="Cost per unit at time of movement")
    reference_type: Optional[str] = Field(
        None,
        description="Reference type: purchase | sale | adjustment | transfer | transformation"
    )
    reference_id: Optional[UUID] = Field(None, description="Referenced transaction ID (NULL for manual adjustments)")
    date: BusinessDate = Field(..., description="Movement date")
    notes: Optional[str] = Field(None, max_length=1000, description="Additional notes")


class InventoryMovementCreate(InventoryMovementBase):
    """
    Schema for creating an InventoryMovement.
    
    Note: Movements are immutable. No update/delete operations.
    Corrections should create new adjustment movements.
    """
    pass


class InventoryMovementResponse(InventoryMovementBase):
    """Schema for InventoryMovement responses with joined data."""
    id: UUID
    organization_id: UUID
    created_at: datetime
    
    # Joined data from related models
    material_code: str = Field(..., description="Material code")
    material_name: str = Field(..., description="Material name")
    warehouse_name: str = Field(..., description="Warehouse name")
    
    model_config = {"from_attributes": True}
    
    @field_serializer('quantity', 'unit_cost')
    def serialize_decimal(self, value: Decimal) -> float:
        """Convert Decimal to float for JSON serialization."""
        return float(value)


class PaginatedInventoryMovementResponse(BaseModel):
    """Paginated response for inventory movement lists."""
    items: list[InventoryMovementResponse]
    total: int
    skip: int
    limit: int
