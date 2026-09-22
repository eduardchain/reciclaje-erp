"""Schemas de LeadMarketPrice (CC-014, Q-B).

Append-only como ServiceTariff (#35): solo Create y Response, sin Update —
corregir un precio = cargar una version nueva. La diferencia con tarifas es
la vigencia: se decide por `effective_date` (fecha de NEGOCIO), no por
`created_at`. Ver el docstring del modelo para el por que y el costo.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.dates import BusinessDate, business_today


class LeadMarketPriceCreate(BaseModel):
    """Cargar un precio de mercado del plomo (append-only)."""

    price_per_kg: Decimal = Field(..., gt=0, description="Precio de mercado por kg, COP")
    # BusinessDate normaliza a mediodia UTC; sin el, un string "2026-09-30"
    # se parsearia a medianoche y en Colombia se veria el dia anterior (#24).
    effective_date: BusinessDate = Field(..., description="Fecha desde la que rige")
    notes: Optional[str] = Field(None, max_length=500)

    @field_validator("effective_date")
    @classmethod
    def not_future(cls, v: datetime) -> datetime:
        # Reloj de NEGOCIO (#91/#92), no el del sistema ni el UTC: entre las
        # 19:00 y 24:00 de Colombia el dia UTC ya es el siguiente, asi que el
        # reloj equivocado dejaria cargar un precio fechado manana.
        # ⚠️ La forma prohibida no se escribe ni en un comentario: la guarda
        # `test_no_hay_relojes_sin_declarar` lee el texto crudo del archivo.
        # El back-dating SI se permite y es deliberado (D1): lo que no tiene
        # sentido es fechar un precio de mercado que todavia no ocurrio.
        if v.date() > business_today():
            raise ValueError("La fecha de vigencia no puede ser futura")
        return v


class LeadMarketPriceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    price_per_kg: Decimal
    effective_date: datetime
    notes: Optional[str] = None
    created_by: UUID
    created_by_name: Optional[str] = None
    created_at: datetime


class LeadMarketPriceListResponse(BaseModel):
    items: list[LeadMarketPriceResponse]
    total: int
