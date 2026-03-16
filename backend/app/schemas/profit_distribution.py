"""Schemas para repartición de utilidades a socios."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.utils.dates import BusinessDate


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

class ProfitDistributionLineCreate(BaseModel):
    third_party_id: UUID
    amount: Decimal


class ProfitDistributionCreate(BaseModel):
    date: BusinessDate
    lines: list[ProfitDistributionLineCreate]
    notes: Optional[str] = None

    @field_validator("lines")
    @classmethod
    def filter_zero_lines(cls, v: list[ProfitDistributionLineCreate]) -> list[ProfitDistributionLineCreate]:
        """Filtrar líneas con amount <= 0 y validar que quede al menos una."""
        filtered = [line for line in v if line.amount > 0]
        if not filtered:
            raise ValueError("Debe asignar monto > 0 a al menos un socio")
        return filtered


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class ProfitDistributionLineResponse(BaseModel):
    id: UUID
    third_party_id: UUID
    third_party_name: str
    amount: float
    money_movement_id: Optional[UUID] = None

    model_config = {"from_attributes": True}


class ProfitDistributionResponse(BaseModel):
    id: UUID
    date: datetime
    total_amount: float
    notes: Optional[str] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    lines: list[ProfitDistributionLineResponse]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Available profit
# ---------------------------------------------------------------------------

class AvailableProfitResponse(BaseModel):
    accumulated_profit: float
    distributed_profit: float
    available_profit: float


# ---------------------------------------------------------------------------
# Partner list
# ---------------------------------------------------------------------------

class PartnerResponse(BaseModel):
    id: UUID
    name: str
    current_balance: float

    model_config = {"from_attributes": True}
