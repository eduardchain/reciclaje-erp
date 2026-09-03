"""
Schemas de WillardDelivery — salida de plomo a Willard (W1).

El precio solo existe en el tipo `venta`. Ahi la linea acepta `unit_price` XOR
`total_price` (patron #95 D8: Johana a veces tiene el total y no el unitario).
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.utils.dates import BusinessDate

DeliveryType = Literal["venta", "abono_bateria", "abono_material"]


# ---------------------------------------------------------------- Lineas ---

class WillardDeliveryLineCreate(BaseModel):
    material_id: UUID
    quantity: Decimal = Field(..., gt=0)
    scale_weight_kg: Optional[Decimal] = Field(
        None, gt=0, description="Opcional al capturar, obligatorio al revisar (#95)"
    )


class WillardDeliveryLinePrice(BaseModel):
    """Precio de una linea al liquidar — solo tipo `venta`."""
    line_id: UUID
    unit_price: Optional[Decimal] = Field(None, gt=0)
    total_price: Optional[Decimal] = Field(None, gt=0)

    @model_validator(mode="after")
    def _xor_price(self):
        if (self.unit_price is None) == (self.total_price is None):
            raise ValueError(
                "Indique precio unitario O valor total de la linea, no ambos ni ninguno"
            )
        return self


class WillardDeliveryLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    material_id: UUID
    material_code: Optional[str] = None
    material_name: Optional[str] = None
    material_unit: str = "kg"
    quantity: Decimal
    unit: Optional[str] = None
    scale_weight_kg: Optional[Decimal] = None
    kg_lead_equivalent: Optional[Decimal] = None
    unit_cost: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    total_price: Optional[Decimal] = None


# ------------------------------------------------------------- Cabecera ---

class WillardDeliveryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delivery_type: DeliveryType
    warehouse_id: UUID
    third_party_id: UUID
    date: BusinessDate
    driver_id: Optional[UUID] = None
    vehicle_id: Optional[UUID] = None
    invoice_number: Optional[str] = Field(None, max_length=50)
    remission_number: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = Field(None, max_length=1000)
    lines: list[WillardDeliveryLineCreate] = Field(..., min_length=1)


class WillardDeliveryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    warehouse_id: Optional[UUID] = None
    date: Optional[BusinessDate] = None
    driver_id: Optional[UUID] = None
    vehicle_id: Optional[UUID] = None
    invoice_number: Optional[str] = Field(None, max_length=50)
    remission_number: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = Field(None, max_length=1000)
    lines: Optional[list[WillardDeliveryLineCreate]] = Field(None, min_length=1)


class WillardDeliveryLiquidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_prices: list[WillardDeliveryLinePrice] = Field(
        default_factory=list,
        description="Solo tipo `venta`: una entrada por linea",
    )
    customer_id: Optional[UUID] = Field(
        None, description="Solo tipo `venta`: cliente de la venta derivada (default Willard)"
    )


class WillardDeliveryAnnul(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class WillardDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    delivery_number: int
    delivery_type: DeliveryType
    warehouse_id: UUID
    warehouse_name: Optional[str] = None
    third_party_id: UUID
    third_party_name: Optional[str] = None
    date: datetime
    driver_id: Optional[UUID] = None
    driver_name: Optional[str] = None
    vehicle_id: Optional[UUID] = None
    vehicle_plate: Optional[str] = None
    invoice_number: Optional[str] = None
    remission_number: Optional[str] = None
    notes: Optional[str] = None
    status: str

    reviewed_at: Optional[datetime] = None
    reviewed_by_name: Optional[str] = None
    liquidated_at: Optional[datetime] = None
    liquidated_ts: Optional[datetime] = None
    liquidated_by_name: Optional[str] = None
    annulled_reason: Optional[str] = None
    annulled_at: Optional[datetime] = None
    annulled_by_name: Optional[str] = None
    created_by_name: Optional[str] = None

    sale_id: Optional[UUID] = None
    sale_number: Optional[int] = None

    maquila_amount: Decimal = Decimal("0")
    freight_amount: Decimal = Decimal("0")
    plant_credit_amount: Decimal = Decimal("0")

    total_kg_lead: Decimal = Decimal("0")

    lines: list[WillardDeliveryLineResponse] = Field(default_factory=list)


class WillardDeliveryListResponse(BaseModel):
    items: list[WillardDeliveryResponse]
    total: int
    page: int
    page_size: int
