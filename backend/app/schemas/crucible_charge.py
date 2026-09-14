"""
Schemas del documento de crisol (#107 D2) — el 4º "ítem" de Salidas de Plomo.

`charge` = traslado a crisoles (kg de crudo pasan de la etapa horno a la etapa
crisol de la cuenta intersede); `dross_return` = retorno de dross al horno (kg
vuelven de crisol a horno y se causa una nueva maquila). `discharge` — el cierre
de refinacion de la spec — NO se acepta: el Literal lo corta en 422 (en el modelo
de Hugo el crisol no se cierra, baja al vender puro y al devolver dross).

`quantity_kg` son kg de PLOMO (lo que cambia de etapa), no kg fisicos del
material: el documento es control de donde esta el plomo (Hugo 28-ago), no
mueve inventario.
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.utils.dates import BusinessDate

CrucibleEventType = Literal["charge", "dross_return"]


class CrucibleChargeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: CrucibleEventType
    warehouse_id: UUID
    material_id: UUID
    quantity_kg: Decimal = Field(..., gt=0, description="kg de PLOMO que cambian de etapa")
    date: BusinessDate
    notes: Optional[str] = Field(None, max_length=1000)


class CrucibleChargeAnnul(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class CrucibleChargeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    charge_number: int
    label: str
    event_type: str
    warehouse_id: UUID
    warehouse_name: Optional[str] = None
    material_id: UUID
    material_code: Optional[str] = None
    material_name: Optional[str] = None
    quantity_kg: Decimal
    date: datetime
    notes: Optional[str] = None
    status: str
    maquila_amount: Decimal = Decimal("0")
    annulled_reason: Optional[str] = None
    annulled_at: Optional[datetime] = None
    annulled_by_name: Optional[str] = None
    created_by_name: Optional[str] = None
    created_at: datetime
    warnings: list[str] = Field(default_factory=list)


class CrucibleChargeListResponse(BaseModel):
    items: list[CrucibleChargeResponse]
    total: int
    page: int
    page_size: int
