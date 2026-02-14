"""
Schemas Pydantic para el modelo BusinessUnit (Unidades de Negocio).

Ejemplo: Fibras, Chatarra, Metales No Ferrosos.
Se usan para analisis de rentabilidad por linea.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class BusinessUnitBase(BaseModel):
    """Schema base para BusinessUnit."""
    name: str = Field(..., min_length=1, max_length=255, description="Nombre de la unidad de negocio")
    description: Optional[str] = Field(None, max_length=500)


class BusinessUnitCreate(BusinessUnitBase):
    """Schema para crear una unidad de negocio."""
    pass


class BusinessUnitUpdate(BaseModel):
    """Schema para actualizar una unidad de negocio (campos opcionales)."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)


class BusinessUnitResponse(BusinessUnitBase):
    """Schema de respuesta para BusinessUnit."""
    id: UUID
    organization_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedBusinessUnitResponse(BaseModel):
    """Respuesta paginada de unidades de negocio."""
    items: list[BusinessUnitResponse]
    total: int
    skip: int
    limit: int
