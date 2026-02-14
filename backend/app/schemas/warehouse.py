"""
Schemas Pydantic para el modelo Warehouse (Bodegas).
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class WarehouseBase(BaseModel):
    """Schema base para Warehouse."""
    name: str = Field(..., min_length=1, max_length=255, description="Nombre de la bodega")
    description: Optional[str] = Field(None, max_length=500)
    address: Optional[str] = Field(None, max_length=500, description="Direccion fisica")


class WarehouseCreate(WarehouseBase):
    """Schema para crear una bodega."""
    pass


class WarehouseUpdate(BaseModel):
    """Schema para actualizar una bodega (campos opcionales)."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    address: Optional[str] = Field(None, max_length=500)


class WarehouseResponse(WarehouseBase):
    """Schema de respuesta para Warehouse."""
    id: UUID
    organization_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedWarehouseResponse(BaseModel):
    """Respuesta paginada de bodegas."""
    items: list[WarehouseResponse]
    total: int
    skip: int
    limit: int
