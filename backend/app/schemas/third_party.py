"""
Pydantic schemas for ThirdParty model.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr, field_serializer


class ThirdPartyBase(BaseModel):
    """Base schema for ThirdParty."""
    name: str = Field(..., min_length=1, max_length=200)
    identification_number: Optional[str] = Field(None, max_length=50, description="Tax ID, DNI, RUC, etc")
    email: Optional[EmailStr] = Field(None, max_length=200)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    is_supplier: bool = Field(default=False, description="Is this third party a supplier?")
    is_customer: bool = Field(default=False, description="Is this third party a customer?")
    is_investor: bool = Field(default=False, description="Is this third party an investor?")
    is_provision: bool = Field(default=False, description="Is this third party a provision?")


class ThirdPartyCreate(ThirdPartyBase):
    """
    Schema for creating a ThirdParty.

    Note:
    - organization_id comes from context automatically
    - current_balance defaults to 0
    """
    initial_balance: Decimal = Field(Decimal("0.00"), description="Saldo inicial")


class ThirdPartyUpdate(BaseModel):
    """Schema for updating a ThirdParty (all fields optional)."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    identification_number: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = Field(None, max_length=200)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    is_supplier: Optional[bool] = None
    is_customer: Optional[bool] = None
    is_investor: Optional[bool] = None
    is_provision: Optional[bool] = None


class ThirdPartyResponse(ThirdPartyBase):
    """Schema for ThirdParty responses."""
    id: UUID
    organization_id: UUID
    initial_balance: float
    current_balance: float
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer('initial_balance', 'current_balance')
    def serialize_decimal(self, value: Decimal) -> float:
        """Convert Decimal to float for JSON serialization."""
        return float(value)


class ThirdPartyBalanceUpdate(BaseModel):
    """Schema for updating third party balance."""
    amount_delta: float = Field(..., description="Amount to add (positive) or subtract (negative)")
