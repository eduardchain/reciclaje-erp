"""Schemas de Driver y Vehicle (SAC E1, v0.5 §11.1.14)."""
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

VehicleType = Literal["camion", "montacargas", "otro"]


class DriverCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    document_id: Optional[str] = Field(None, max_length=30)
    phone: Optional[str] = Field(None, max_length=30)


class DriverUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    document_id: Optional[str] = Field(None, max_length=30)
    phone: Optional[str] = Field(None, max_length=30)
    is_active: Optional[bool] = None


class DriverResponse(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    document_id: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class VehicleCreate(BaseModel):
    plate: str = Field(..., min_length=1, max_length=15)
    display_name: Optional[str] = Field(None, max_length=120)
    vehicle_type: Optional[VehicleType] = None


class VehicleUpdate(BaseModel):
    plate: Optional[str] = Field(None, min_length=1, max_length=15)
    display_name: Optional[str] = Field(None, max_length=120)
    vehicle_type: Optional[VehicleType] = None
    is_active: Optional[bool] = None


class VehicleResponse(BaseModel):
    id: UUID
    organization_id: UUID
    plate: str
    display_name: Optional[str] = None
    vehicle_type: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
