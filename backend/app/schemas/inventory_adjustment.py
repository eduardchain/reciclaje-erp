"""
Schemas Pydantic para el modelo InventoryAdjustment (Ajustes de Inventario).

Schemas especializados por tipo de ajuste:
- IncreaseCreate: Aumento de stock (requiere unit_cost)
- DecreaseCreate: Disminucion de stock (usa costo promedio actual)
- RecountCreate: Conteo fisico (calcula diferencia automaticamente)
- ZeroOutCreate: Llevar stock a cero
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer


# ---------------------------------------------------------------------------
# Schemas de creacion — uno por tipo de ajuste
# ---------------------------------------------------------------------------

class IncreaseCreate(BaseModel):
    """Aumento de stock — recalcula costo promedio."""
    material_id: UUID = Field(..., description="Material a ajustar")
    warehouse_id: UUID = Field(..., description="Bodega donde se realiza el ajuste")
    quantity: Decimal = Field(..., gt=0, description="Cantidad a agregar")
    unit_cost: Decimal = Field(..., gt=0, description="Costo unitario del material encontrado")
    date: datetime = Field(..., description="Fecha del ajuste")
    reason: str = Field(..., min_length=3, description="Razon del ajuste")
    notes: Optional[str] = None


class DecreaseCreate(BaseModel):
    """Disminucion de stock — usa costo promedio actual."""
    material_id: UUID = Field(..., description="Material a ajustar")
    warehouse_id: UUID = Field(..., description="Bodega donde se realiza el ajuste")
    quantity: Decimal = Field(..., gt=0, description="Cantidad a disminuir")
    date: datetime = Field(..., description="Fecha del ajuste")
    reason: str = Field(..., min_length=3, description="Razon del ajuste")
    notes: Optional[str] = None


class RecountCreate(BaseModel):
    """Conteo fisico — ajusta al stock contado."""
    material_id: UUID = Field(..., description="Material a ajustar")
    warehouse_id: UUID = Field(..., description="Bodega donde se realiza el conteo")
    counted_quantity: Decimal = Field(..., ge=0, description="Cantidad contada fisicamente")
    date: datetime = Field(..., description="Fecha del conteo")
    reason: str = Field(..., min_length=3, description="Razon del conteo")
    notes: Optional[str] = None


class ZeroOutCreate(BaseModel):
    """Llevar stock a cero — elimina todo el stock liquidado."""
    material_id: UUID = Field(..., description="Material a llevar a cero")
    warehouse_id: UUID = Field(..., description="Bodega del ajuste")
    date: datetime = Field(..., description="Fecha del ajuste")
    reason: str = Field(..., min_length=3, description="Razon para llevar a cero")
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Schema de anulacion
# ---------------------------------------------------------------------------

class AnnulAdjustmentRequest(BaseModel):
    """Solicitud de anulacion de ajuste."""
    reason: str = Field(..., min_length=1, max_length=500, description="Razon de anulacion")


# ---------------------------------------------------------------------------
# Schema de traslado entre bodegas
# ---------------------------------------------------------------------------

class WarehouseTransferCreate(BaseModel):
    """Traslado de material entre bodegas."""
    material_id: UUID = Field(..., description="Material a trasladar")
    source_warehouse_id: UUID = Field(..., description="Bodega de origen")
    destination_warehouse_id: UUID = Field(..., description="Bodega de destino")
    quantity: Decimal = Field(..., gt=0, description="Cantidad a trasladar")
    date: datetime = Field(..., description="Fecha del traslado")
    reason: str = Field(..., min_length=3, description="Razon del traslado")
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Schemas de respuesta
# ---------------------------------------------------------------------------

class InventoryAdjustmentResponse(BaseModel):
    """Respuesta completa de un ajuste de inventario."""
    id: UUID
    organization_id: UUID
    adjustment_number: int
    date: datetime
    adjustment_type: str

    # Material y bodega
    material_id: UUID
    material_code: Optional[str] = None
    material_name: Optional[str] = None
    warehouse_id: UUID
    warehouse_name: Optional[str] = None

    # Cantidades
    previous_stock: float
    quantity: float
    new_stock: float
    counted_quantity: Optional[float] = None

    # Costo
    unit_cost: float
    total_value: float

    # Detalles
    reason: str
    notes: Optional[str] = None

    # Estado
    status: str
    annulled_reason: Optional[str] = None
    annulled_at: Optional[datetime] = None
    annulled_by: Optional[UUID] = None

    # Auditoria
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    # Warnings (stock negativo, etc.)
    warnings: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}

    @field_serializer('previous_stock', 'quantity', 'new_stock', 'unit_cost', 'total_value')
    def serialize_decimal(self, value: Decimal) -> float:
        return float(value)

    @field_serializer('counted_quantity')
    def serialize_counted(self, value: Optional[Decimal]) -> Optional[float]:
        return float(value) if value is not None else None


class PaginatedInventoryAdjustmentResponse(BaseModel):
    """Respuesta paginada de ajustes de inventario."""
    items: list[InventoryAdjustmentResponse]
    total: int
    skip: int
    limit: int


class WarehouseTransferResponse(BaseModel):
    """Respuesta de un traslado entre bodegas."""
    material_id: UUID
    material_code: Optional[str] = None
    material_name: Optional[str] = None
    source_warehouse_id: UUID
    source_warehouse_name: Optional[str] = None
    destination_warehouse_id: UUID
    destination_warehouse_name: Optional[str] = None
    quantity: float
    date: datetime
    reason: str
    notes: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}

    @field_serializer('quantity')
    def serialize_quantity(self, value: Decimal) -> float:
        return float(value)
