"""
Pydantic schemas for DoubleEntry (Pasa Mano) model.

Soporta multiples materiales por operacion via DoubleEntryLine.
Workflow de 2 pasos: registrar → liquidar.
"""
from datetime import date as date_type, datetime, time, timezone
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer, model_validator

from app.schemas.sale import SaleCommissionCreate, SaleCommissionResponse


# ============================================================================
# DoubleEntryLine Schemas
# ============================================================================

class DoubleEntryLineCreate(BaseModel):
    """Schema para crear una linea de doble partida."""
    material_id: UUID = Field(..., description="Material UUID")
    quantity: Decimal = Field(..., gt=0, description="Cantidad (positiva)")
    purchase_unit_price: Decimal = Field(..., gt=0, description="Precio de compra por unidad")
    sale_unit_price: Decimal = Field(..., gt=0, description="Precio de venta por unidad")


class DoubleEntryLineResponse(BaseModel):
    """Schema para linea de doble partida en respuestas."""
    id: UUID
    material_id: UUID
    quantity: float
    purchase_unit_price: float
    sale_unit_price: float
    total_purchase: float
    total_sale: float
    profit: float
    material_code: str
    material_name: str

    model_config = {"from_attributes": True}

    @field_serializer('quantity', 'purchase_unit_price', 'sale_unit_price',
                      'total_purchase', 'total_sale', 'profit')
    def serialize_decimals(self, value: Decimal) -> float:
        return float(value)


# ============================================================================
# DoubleEntry Schemas
# ============================================================================

class DoubleEntryCreate(BaseModel):
    """
    Schema para crear (registrar) una doble partida con multiples materiales.

    Validaciones:
    - supplier_id != customer_id
    - Al menos 1 linea (min_length=1)
    - No duplicar material_id entre lineas
    """
    lines: List[DoubleEntryLineCreate] = Field(..., min_length=1, description="Lineas de materiales")
    supplier_id: UUID = Field(..., description="Supplier UUID")
    customer_id: UUID = Field(..., description="Customer UUID")
    date: date_type = Field(..., description="Fecha de la operacion")
    invoice_number: Optional[str] = Field(None, max_length=50)
    vehicle_plate: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = Field(None, max_length=1000)
    commissions: List[SaleCommissionCreate] = Field(
        default_factory=list,
        description="Comisiones de venta (se pagan al liquidar)"
    )
    auto_liquidate: bool = Field(False, description="Liquidar inmediatamente despues de registrar")

    @model_validator(mode='after')
    def validate_create(self):
        if self.supplier_id == self.customer_id:
            raise ValueError("Supplier and customer cannot be the same third party")
        # V-DP-02: No permitir materiales duplicados entre lineas
        material_ids = [line.material_id for line in self.lines]
        if len(material_ids) != len(set(material_ids)):
            raise ValueError("No se permite repetir el mismo material en diferentes lineas")
        return self


class DoubleEntryUpdate(BaseModel):
    """Schema para actualizar metadata de una doble partida."""
    notes: Optional[str] = Field(None, max_length=1000)
    invoice_number: Optional[str] = Field(None, max_length=50)
    vehicle_plate: Optional[str] = Field(None, max_length=20)


class DoubleEntryLiquidateLineUpdate(BaseModel):
    """Precios actualizados para una linea durante liquidacion."""
    line_id: UUID = Field(..., description="ID de la linea de doble partida")
    purchase_unit_price: Decimal = Field(..., gt=0, description="Precio de compra confirmado")
    sale_unit_price: Decimal = Field(..., gt=0, description="Precio de venta confirmado")


class DoubleEntryLiquidateRequest(BaseModel):
    """Schema para liquidar doble partida (confirmar precios, aplicar efectos financieros)."""
    lines: Optional[List[DoubleEntryLiquidateLineUpdate]] = Field(None, description="Precios actualizados por linea")
    commissions: Optional[List[SaleCommissionCreate]] = Field(None, description="Comisiones (reemplazan las existentes)")


class DoubleEntryFullUpdate(BaseModel):
    """Schema para edicion completa de doble partida registrada."""
    supplier_id: Optional[UUID] = None
    customer_id: Optional[UUID] = None
    date: Optional[date_type] = None
    invoice_number: Optional[str] = Field(None, max_length=50)
    vehicle_plate: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = Field(None, max_length=1000)
    lines: Optional[List[DoubleEntryLineCreate]] = Field(None, min_length=1)
    commissions: Optional[List[SaleCommissionCreate]] = None

    @model_validator(mode='after')
    def validate_update(self):
        if self.supplier_id and self.customer_id and self.supplier_id == self.customer_id:
            raise ValueError("Supplier and customer cannot be the same third party")
        if self.lines:
            material_ids = [line.material_id for line in self.lines]
            if len(material_ids) != len(set(material_ids)):
                raise ValueError("No se permite repetir el mismo material en diferentes lineas")
        return self


class DoubleEntryResponse(BaseModel):
    """Schema completo de respuesta de doble partida."""
    id: UUID
    organization_id: UUID
    double_entry_number: int
    date: date_type
    supplier_id: UUID
    customer_id: UUID
    invoice_number: Optional[str] = None
    vehicle_plate: Optional[str] = None
    notes: Optional[str] = None
    purchase_id: UUID
    sale_id: UUID
    status: str = Field(..., description="registered | liquidated | cancelled")

    # Lineas
    lines: List[DoubleEntryLineResponse] = Field(default_factory=list)

    # Resumen para listado
    materials_summary: str = Field("", description="Nombres de materiales concatenados")

    # Totales calculados (desde lineas)
    total_purchase_cost: float
    total_sale_amount: float
    profit: float
    profit_margin: float

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # Audit
    created_by: Optional[UUID] = None
    liquidated_at: Optional[datetime] = None
    liquidated_by: Optional[UUID] = None
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[UUID] = None

    # Joined data
    supplier_name: str
    customer_name: str

    # Comisiones de la venta vinculada
    commissions: List[SaleCommissionResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}

    @field_serializer('date')
    def serialize_date_as_noon_utc(self, value: date_type) -> str:
        """Serializar date como datetime mediodia UTC para display correcto en cualquier timezone."""
        dt = datetime.combine(value, time(12, 0), tzinfo=timezone.utc)
        return dt.isoformat()

    @field_serializer('total_purchase_cost', 'total_sale_amount', 'profit', 'profit_margin')
    def serialize_decimals(self, value: Decimal) -> float:
        return float(value)


class PaginatedDoubleEntryResponse(BaseModel):
    """Paginated response for double-entry lists."""
    items: List[DoubleEntryResponse]
    total: int
    skip: int
    limit: int
