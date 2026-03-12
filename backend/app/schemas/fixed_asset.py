"""
Schemas Pydantic para Activos Fijos (FixedAsset).

Flujo: registrar activo → depreciar mensualmente → dar de baja.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer, model_validator


class FixedAssetCreate(BaseModel):
    """Crear un activo fijo."""
    name: str = Field(..., min_length=1, max_length=200)
    asset_code: Optional[str] = Field(None, max_length=50)
    purchase_date: date
    purchase_value: Decimal = Field(..., gt=0)
    salvage_value: Decimal = Field(Decimal("0"), ge=0)
    depreciation_rate: Decimal = Field(..., ge=Decimal("0.01"), le=Decimal("100"))
    depreciation_start_date: date
    expense_category_id: UUID
    third_party_id: Optional[UUID] = None
    purchase_movement_id: Optional[UUID] = None
    notes: Optional[str] = Field(None, max_length=500)

    @model_validator(mode="after")
    def validate_values(self):
        if self.purchase_value <= self.salvage_value:
            raise ValueError("El valor de compra debe ser mayor al valor residual")
        if self.depreciation_start_date < self.purchase_date:
            raise ValueError(
                "La fecha de inicio de depreciación no puede ser anterior a la fecha de compra"
            )
        return self


class FixedAssetUpdate(BaseModel):
    """Actualizar un activo fijo. Restricciones aplicadas en servicio."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    asset_code: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = Field(None, max_length=500)
    purchase_value: Optional[Decimal] = Field(None, gt=0)
    salvage_value: Optional[Decimal] = Field(None, ge=0)
    depreciation_rate: Optional[Decimal] = Field(None, ge=Decimal("0.01"), le=Decimal("100"))
    expense_category_id: Optional[UUID] = None


class FixedAssetDisposeRequest(BaseModel):
    """Solicitud para dar de baja un activo."""
    reason: str = Field(..., min_length=1, max_length=500)


class AssetDepreciationResponse(BaseModel):
    """Respuesta de una cuota de depreciación aplicada."""
    id: UUID
    depreciation_number: int
    period: str
    amount: float
    accumulated_after: float
    current_value_after: float
    money_movement_id: UUID
    applied_at: datetime
    applied_by: Optional[UUID] = None

    model_config = {"from_attributes": True}

    @field_serializer('amount', 'accumulated_after', 'current_value_after')
    def serialize_decimal(self, value: Decimal) -> float:
        return float(value)


class FixedAssetResponse(BaseModel):
    """Respuesta completa de un activo fijo."""
    id: UUID
    organization_id: UUID
    name: str
    asset_code: Optional[str] = None
    notes: Optional[str] = None
    purchase_date: date
    depreciation_start_date: date
    purchase_value: float
    salvage_value: float
    current_value: float
    accumulated_depreciation: float
    depreciation_rate: float
    monthly_depreciation: float
    useful_life_months: int
    expense_category_id: UUID
    expense_category_name: Optional[str] = None
    third_party_id: Optional[UUID] = None
    third_party_name: Optional[str] = None
    purchase_movement_id: Optional[UUID] = None
    status: str
    disposed_at: Optional[datetime] = None
    disposed_by: Optional[UUID] = None
    disposal_reason: Optional[str] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    # Campos calculados (set en endpoint)
    remaining_months: int = 0
    depreciation_progress: float = 0.0
    depreciations: List[AssetDepreciationResponse] = []

    model_config = {"from_attributes": True}

    @field_serializer(
        'purchase_value', 'salvage_value', 'current_value',
        'accumulated_depreciation', 'depreciation_rate',
        'monthly_depreciation',
    )
    def serialize_decimal(self, value: Decimal) -> float:
        return float(value)


class PaginatedFixedAssetResponse(BaseModel):
    """Respuesta paginada."""
    items: List[FixedAssetResponse]
    total: int
    skip: int
    limit: int


class ApplyPendingResult(BaseModel):
    """Resultado de aplicar depreciación pendiente a un activo."""
    asset_id: UUID
    asset_name: str
    amount: float
    new_status: str
