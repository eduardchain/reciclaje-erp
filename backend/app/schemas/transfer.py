"""
Schemas Transfer — traslado intersede dos pasos (SAC E3.1).

extra="forbid" en los create/request (patron #74). Fechas de negocio via
BusinessDate (mediodia UTC). La tolerancia y los efectos se evaluan POR LINEA;
variance_pct se expone por linea para la UI de recepcion/discrepancia.
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.utils.dates import BusinessDate


# ------------------------------------------------------------------ #
# Requests                                                            #
# ------------------------------------------------------------------ #

class TransferLineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: UUID
    quantity_dispatched: Decimal = Field(..., gt=0)


class TransferDispatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_warehouse_id: UUID
    to_warehouse_id: UUID
    dispatch_date: Optional[BusinessDate] = None
    notes: Optional[str] = Field(None, max_length=500)
    lines: list[TransferLineCreate] = Field(..., min_length=1)


class TransferReceiveLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transfer_line_id: UUID
    quantity_received: Decimal = Field(..., ge=0)


class TransferReceiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lines: list[TransferReceiveLine] = Field(..., min_length=1)
    receipt_date: Optional[BusinessDate] = None
    notes: Optional[str] = Field(None, max_length=500)


class TransferResolveLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transfer_line_id: UUID
    resolution: Literal["justify", "correct"]
    final_quantity: Optional[Decimal] = Field(
        None, ge=0,
        description="Obligatoria en 'correct' (arqueo); en 'justify' se acepta quantity_received",
    )


class TransferResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lines: list[TransferResolveLine] = Field(..., min_length=1)
    notes: str = Field(..., min_length=3, max_length=500)


class TransferAnnulRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=3, max_length=500)


# ------------------------------------------------------------------ #
# Responses                                                           #
# ------------------------------------------------------------------ #

class TransferLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    material_id: UUID
    material_code: Optional[str] = None
    material_name: Optional[str] = None
    material_unit: str = "kg"
    quantity_dispatched: Decimal
    quantity_received: Optional[Decimal] = None
    resolved_quantity: Optional[Decimal] = None
    unit_cost: Decimal
    is_contributor: bool
    kg_lead_equivalent: Optional[Decimal] = None
    maquila_amount: Optional[Decimal] = None
    discrepancy_task_id: Optional[UUID] = None
    effects_emitted: bool
    variance_pct: Optional[Decimal] = Field(
        None, description="|recibido - despachado| / despachado, 4 decimales; NULL sin recibir"
    )


class TransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    transfer_number: int
    from_warehouse_id: UUID
    from_warehouse_name: Optional[str] = None
    to_warehouse_id: UUID
    to_warehouse_name: Optional[str] = None
    # NULL = intra-sede: se completo al registrarlo, sin escala en transito
    transit_warehouse_id: Optional[UUID] = None
    transit_warehouse_name: Optional[str] = None
    dispatch_date: datetime
    received_date: Optional[datetime] = None
    status: str
    notes: Optional[str] = None
    created_by_name: Optional[str] = None
    received_by_name: Optional[str] = None
    annulled_reason: Optional[str] = None
    annulled_at: Optional[datetime] = None
    created_at: datetime
    lines: list[TransferLineResponse] = []
    warnings: list[str] = []


class TransferListResponse(BaseModel):
    items: list[TransferResponse]
    total: int
    pending_receipt_count: int = 0
