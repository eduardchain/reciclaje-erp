"""
Schemas InboundOrder (SAC E2, plan-sac-recepcion-y-materiales.md, CC-004).

La Recepcion es la pantalla de captura unica con 2 tipos (colapso 4->2):
- willard: genera efectos propios (inventario a identidad D2 + kg ledger D5);
  el ruteo de la cuenta kg es POR LINEA segun willard_world del material
  (postconsumo->baterias por sede; drosses->drosses org-wide).
- purchase: deriva una Purchase(registered) (D7). Absorbe el viejo tipo `ruta`.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.dates import BusinessDate

InboundType = Literal["purchase", "willard"]

WILLARD_INBOUND_TYPES = {"willard"}
PURCHASE_INBOUND_TYPES = {"purchase"}


class InboundOrderLineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: UUID
    quantity: Decimal = Field(..., gt=0)
    unit_price: Optional[Decimal] = Field(
        None, ge=0, description="Precio de captura (tipos purchase; definitivo al liquidar §7.2)"
    )
    scale_weight_kg: Optional[Decimal] = Field(None, gt=0)
    quality_notes: Optional[str] = Field(None, max_length=500)


class InboundOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inbound_type: InboundType
    warehouse_id: UUID
    third_party_id: UUID
    date: BusinessDate
    driver_id: Optional[UUID] = None
    vehicle_id: Optional[UUID] = None
    willard_distribution_center: Optional[str] = Field(None, max_length=24)
    goes_directly_to_jm: bool = False
    lines: list[InboundOrderLineCreate] = Field(..., min_length=1)

    @field_validator("date")
    @classmethod
    def not_future(cls, v: datetime) -> datetime:
        # D15 — §11.1.2 L1917 + filosofia anti back-dating #62
        if v.date() > datetime.now(timezone.utc).date():
            raise ValueError("La fecha de la orden no puede ser futura")
        return v


class InboundOrderUpdate(BaseModel):
    """Edicion D18 — Willard: revert-and-reapply de lineas; purchase: solo
    cabecera sin efectos. warehouse/tipo/tercero inmutables (anular y recrear)."""
    model_config = ConfigDict(extra="forbid")

    date: Optional[BusinessDate] = None
    driver_id: Optional[UUID] = None
    vehicle_id: Optional[UUID] = None
    willard_distribution_center: Optional[str] = Field(None, max_length=24)
    goes_directly_to_jm: Optional[bool] = None
    lines: Optional[list[InboundOrderLineCreate]] = Field(None, min_length=1)

    @field_validator("date")
    @classmethod
    def not_future(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is not None and v.date() > datetime.now(timezone.utc).date():
            raise ValueError("La fecha de la orden no puede ser futura")
        return v


class InboundOrderAnnulRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class InboundOrderLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    material_id: UUID
    material_code: Optional[str] = None
    material_name: Optional[str] = None
    material_unit: str = "kg"  # patron #54
    quantity: Decimal
    unit: Optional[str] = None
    unit_price: Optional[Decimal] = None
    unit_cost: Optional[Decimal] = None
    scale_weight_kg: Optional[Decimal] = None
    quality_notes: Optional[str] = None
    kg_lead: Optional[Decimal] = Field(
        None, description="delta_kg emitido al KgLedger por esta linea (tipos Willard)"
    )


class InboundOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_number: int
    inbound_type: str
    warehouse_id: UUID
    warehouse_name: Optional[str] = None
    third_party_id: UUID
    third_party_name: Optional[str] = None
    date: datetime
    driver_id: Optional[UUID] = None
    driver_name: Optional[str] = None
    vehicle_id: Optional[UUID] = None
    vehicle_plate: Optional[str] = None
    willard_distribution_center: Optional[str] = None
    goes_directly_to_jm: bool = False
    status: str
    purchase_id: Optional[UUID] = None
    purchase_number: Optional[int] = None
    purchase_status: Optional[str] = None
    total_kg_lead: Optional[Decimal] = Field(
        None, description="Suma de deltas kg emitidos (tipos Willard)"
    )
    annulled_reason: Optional[str] = None
    annulled_at: Optional[datetime] = None
    created_at: datetime
    lines: list[InboundOrderLineResponse] = []
    warnings: list[str] = []


class InboundOrderListResponse(BaseModel):
    items: list[InboundOrderResponse]
    total: int
