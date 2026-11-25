"""Schemas de la Salida de control y del Talonario de remisiones (SAC).

Plan: docs/planes/plan-sac-documentos-control.md v1.2 §4.3 y §4.5.
"""
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.utils.dates import BusinessDate

# La remision sale del MISMO talonario de las Entradas (Q-75): obligatoria.
# strip ANTES de min_length: «  » no pasa (min_length solo cuenta caracteres,
# leccion de #100).
RemissionStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
]


class ControlDispatchLineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: UUID
    quantity: Decimal = Field(..., gt=0)
    scale_weight_kg: Optional[Decimal] = Field(None, gt=0)


class ControlDispatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: BusinessDate
    warehouse_id: UUID
    third_party_id: Optional[UUID] = None
    remission_number: RemissionStr
    notes: Optional[str] = Field(None, max_length=1000)
    lines: list[ControlDispatchLineCreate] = Field(..., min_length=1)


class ControlDispatchUpdate(BaseModel):
    """Parcial. La remision se puede cambiar pero NO borrar: `null` o vacia
    dan 422 (el PATCH no es una puerta de atras a la obligatoriedad)."""
    model_config = ConfigDict(extra="forbid")

    date: Optional[BusinessDate] = None
    warehouse_id: Optional[UUID] = None
    third_party_id: Optional[UUID] = None
    remission_number: Optional[RemissionStr] = None
    notes: Optional[str] = Field(None, max_length=1000)
    lines: Optional[list[ControlDispatchLineCreate]] = Field(None, min_length=1)


class ControlDispatchAnnulRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)
    ]


class ControlDispatchLineResponse(BaseModel):
    id: UUID
    material_id: UUID
    material_code: Optional[str] = None
    material_name: Optional[str] = None
    material_unit: str = "kg"
    quantity: Decimal
    scale_weight_kg: Optional[Decimal] = None


class ControlDispatchResponse(BaseModel):
    id: UUID
    dispatch_number: int
    date: datetime
    warehouse_id: UUID
    warehouse_name: Optional[str] = None
    third_party_id: Optional[UUID] = None
    third_party_name: Optional[str] = None
    remission_number: str
    notes: Optional[str] = None
    status: str
    annulled_reason: Optional[str] = None
    annulled_at: Optional[datetime] = None
    annulled_by_name: Optional[str] = None
    created_at: datetime
    created_by_name: Optional[str] = None
    lines: list[ControlDispatchLineResponse] = []
    # Remision repetida (D8): se AVISA, nunca se rechaza. Llega por HTTP.
    warnings: list[str] = []


class ControlDispatchListResponse(BaseModel):
    items: list[ControlDispatchResponse]
    total: int


class RemissionBookItem(BaseModel):
    """Una fila del talonario: un documento o un hueco («Faltan N»)."""
    kind: Literal["doc", "gap"]
    # doc
    doc_type: Optional[Literal["inbound", "control_dispatch"]] = None
    doc_id: Optional[UUID] = None
    doc_number: Optional[int] = None
    remission: Optional[str] = None
    date: Optional[datetime] = None
    status: Optional[str] = None
    inbound_type: Optional[str] = None
    duplicated: bool = False
    materials: Optional[str] = None
    # gap. Texto y no int: una remision de 20 digitos pasa 2^53 y en el
    # navegador un number la redondearia (16301..12345678901234567889).
    gap_from: Optional[str] = None
    gap_to: Optional[str] = None
    count: Optional[str] = None


class RemissionBookResponse(BaseModel):
    items: list[RemissionBookItem]
    total: int
    documents: int
    inbound_without_remission: int
