"""
Schemas Pydantic para el modelo PriceList (Listas de Precios).

Registro historico de precios de compra y venta por material.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer


class PriceListBase(BaseModel):
    """Schema base para PriceList."""
    material_id: UUID = Field(..., description="ID del material")
    purchase_price: Decimal = Field(
        Decimal("0.00"), ge=0, description="Precio de compra por unidad"
    )
    sale_price: Decimal = Field(
        Decimal("0.00"), ge=0, description="Precio de venta por unidad"
    )
    notes: Optional[str] = Field(None, max_length=500, description="Nota o justificacion")


class PriceListCreate(PriceListBase):
    """Schema para crear un registro de precios."""
    pass


class PriceListUpdate(BaseModel):
    """Schema para actualizar precios (crea un nuevo registro historico)."""
    purchase_price: Optional[Decimal] = Field(None, ge=0)
    sale_price: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = Field(None, max_length=500)


class PriceListResponse(PriceListBase):
    """Schema de respuesta para PriceList."""
    id: UUID
    organization_id: UUID
    updated_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("purchase_price", "sale_price")
    def serialize_decimal(self, value: Decimal) -> float:
        return float(value)


class CurrentPriceItem(BaseModel):
    """Precio vigente de un material (version ligera)."""
    material_id: UUID
    purchase_price: float
    sale_price: float


class CurrentPricesResponse(BaseModel):
    """Respuesta con todos los precios vigentes."""
    items: list[CurrentPriceItem]


class PaginatedPriceListResponse(BaseModel):
    """Respuesta paginada de listas de precios."""
    items: list[PriceListResponse]
    total: int
    skip: int
    limit: int


class PriceTableItem(BaseModel):
    """Fila de la tabla de precios: material + precio vigente."""
    material_id: UUID
    material_code: str
    material_name: str
    category_id: Optional[UUID] = None
    category_name: Optional[str] = None
    purchase_price: Optional[float] = None
    sale_price: Optional[float] = None
    last_updated: Optional[datetime] = None
    updated_by_name: Optional[str] = None


class PriceTableResponse(BaseModel):
    """Respuesta de la tabla de precios completa."""
    items: list[PriceTableItem]
