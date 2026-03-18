"""
Pydantic schemas for Material and MaterialCategory models.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer, model_validator


# ============================================================================
# Material Category Schemas
# ============================================================================

class MaterialCategoryBase(BaseModel):
    """Base schema for MaterialCategory."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)


class MaterialCategoryCreate(MaterialCategoryBase):
    """Schema for creating a MaterialCategory."""
    pass


class MaterialCategoryUpdate(BaseModel):
    """Schema for updating a MaterialCategory (all fields optional)."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)


class MaterialCategoryResponse(MaterialCategoryBase):
    """Schema for MaterialCategory responses."""
    id: UUID
    organization_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================================
# Material Schemas
# ============================================================================

class MaterialBase(BaseModel):
    """Base schema for Material."""
    code: str = Field(..., min_length=1, max_length=50, description="Unique material code")
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    category_id: UUID = Field(..., description="Material category UUID")
    business_unit_id: UUID = Field(..., description="Business unit UUID")
    default_unit: str = Field(..., min_length=1, max_length=20, description="Default unit of measure (kg, ton, m3, etc)")


class MaterialCreate(MaterialBase):
    """
    Schema for creating a Material.
    
    Note: 
    - organization_id comes from context automatically
    - current_stock, current_average_cost default to 0
    """
    pass


class MaterialUpdate(BaseModel):
    """Schema for updating a Material (all fields optional)."""
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    category_id: Optional[UUID] = None
    business_unit_id: Optional[UUID] = None
    default_unit: Optional[str] = Field(None, min_length=1, max_length=20)


class MaterialResponse(MaterialBase):
    """Schema for Material responses."""
    id: UUID
    organization_id: UUID
    current_stock: float
    current_stock_liquidated: float
    current_stock_transit: float
    current_average_cost: float
    sort_order: int = 0
    is_active: bool
    business_unit_name: Optional[str] = None
    category_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def extract_bu_name(cls, data):
        if hasattr(data, "business_unit") and data.business_unit is not None:
            data.__dict__["business_unit_name"] = data.business_unit.name
        return data

    @field_serializer('current_stock', 'current_stock_liquidated', 'current_stock_transit', 'current_average_cost')
    def serialize_decimal(self, value: Decimal) -> float:
        """Convert Decimal to float for JSON serialization."""
        return float(value)


class MaterialStockUpdate(BaseModel):
    """Schema for updating material stock."""
    quantity_delta: float = Field(..., description="Amount to add (positive) or subtract (negative)")
