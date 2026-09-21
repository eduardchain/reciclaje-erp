"""
Schemas del documento de crisol (#107 D2) — el 4º "ítem" de Salidas de Plomo.

`charge` = traslado a crisoles (kg de crudo pasan de la etapa horno a la etapa
crisol de la cuenta intersede); `dross_return` = retorno de dross al horno (kg
vuelven de crisol a horno y se causa una nueva maquila). `discharge` — el cierre
de refinacion de la spec — NO se acepta: el Literal lo corta en 422 (en el modelo
de Hugo el crisol no se cierra, baja al vender puro y al devolver dross).

🔴 #109 SUPERSEDE la semantica de #107: `quantity_kg` son los kg FISICOS del
material del documento (crudo en un traslado, DROSS en un retorno) y `lead_kg`
—calculado por el servidor, nunca digitado— son los kg de plomo. En un traslado
coinciden; en un retorno lead_kg = quantity_kg x el factor de la formula
`drosses_to_lead` vigente del material (Hugo 16-sep: "los 20 kg es dross... tiene
un plomo a devolver, que serian 14"). Y el documento SI mueve inventario
(Johana 18-sep, cita compuesta de dos turnos suyos: L555 "En el crisol no hay
ninguna transformación," + L579 "salen 200 de crudo, ingresan 200 de puro").
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
    quantity_kg: Decimal = Field(
        ..., gt=0,
        description="kg FISICOS del material del documento (crudo en charge, dross en dross_return)",
    )
    date: BusinessDate
    notes: Optional[str] = Field(None, max_length=1000)
    # Solo hacen falta si la org tiene MAS DE UN material marcado puro/crudo
    # (SAC tiene uno de cada uno): sin ambiguedad el servidor los resuelve solo.
    puro_material_id: Optional[UUID] = None
    crudo_material_id: Optional[UUID] = None


class CrucibleInventoryLeg(BaseModel):
    material_id: UUID
    material_code: Optional[str] = None
    material_name: Optional[str] = None
    quantity: Decimal


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
    lead_kg: Decimal
    date: datetime
    notes: Optional[str] = None
    status: str
    maquila_amount: Decimal = Decimal("0")
    # Inventario que movio el documento (#109 D4); None en documentos previos.
    transformation_id: Optional[UUID] = None
    transformation_number: Optional[int] = None
    inventory_out: Optional[CrucibleInventoryLeg] = None
    inventory_in: Optional[CrucibleInventoryLeg] = None
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
