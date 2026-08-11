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
    # SAC Ciclo B (Q-12): True = recibe de terceros; las internas
    # (molino/transito) se crean/marcan con False
    is_receiving: bool = True
    # SAC E3.1 (E12): bodega virtual de transito intersede + su ruteo a la
    # sede fisica destino. Solo relevante con two_step_transfers_enabled.
    is_transit: bool = False
    transit_target_warehouse_id: Optional[UUID] = None
    # Sede a la que pertenece. NULL = es su propia sede — un traslado entre dos
    # bodegas de la MISMA sede no emite kg intersede ni maquila.
    sede_warehouse_id: Optional[UUID] = None


class WarehouseUpdate(BaseModel):
    """Schema para actualizar una bodega (campos opcionales)."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    address: Optional[str] = Field(None, max_length=500)
    is_receiving: Optional[bool] = None
    is_transit: Optional[bool] = None
    transit_target_warehouse_id: Optional[UUID] = None
    sede_warehouse_id: Optional[UUID] = None


class WarehouseResponse(WarehouseBase):
    """Schema de respuesta para Warehouse."""
    id: UUID
    organization_id: UUID
    is_active: bool
    is_receiving: bool = True
    is_transit: bool = False
    transit_target_warehouse_id: Optional[UUID] = None
    sede_warehouse_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedWarehouseResponse(BaseModel):
    """Respuesta paginada de bodegas."""
    items: list[WarehouseResponse]
    total: int
    skip: int
    limit: int
