"""
Schemas Pydantic para el modelo MoneyAccount (Cuentas de Dinero).

Tipos de cuenta: cash (efectivo), bank (banco), digital (Nequi, etc.)
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer


class MoneyAccountBase(BaseModel):
    """Schema base para MoneyAccount."""
    name: str = Field(..., min_length=1, max_length=255, description="Nombre de la cuenta")
    account_type: str = Field(..., description="Tipo: 'cash', 'bank', 'digital'")
    account_number: Optional[str] = Field(None, max_length=100, description="Numero de cuenta bancaria")
    bank_name: Optional[str] = Field(None, max_length=255, description="Nombre del banco")


class MoneyAccountCreate(MoneyAccountBase):
    """Schema para crear una cuenta de dinero."""
    initial_balance: Decimal = Field(Decimal("0.00"), ge=0, description="Saldo inicial")


class MoneyAccountUpdate(BaseModel):
    """Schema para actualizar una cuenta de dinero (campos opcionales)."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    account_type: Optional[str] = None
    account_number: Optional[str] = Field(None, max_length=100)
    bank_name: Optional[str] = Field(None, max_length=255)


class MoneyAccountResponse(MoneyAccountBase):
    """Schema de respuesta para MoneyAccount."""
    id: UUID
    organization_id: UUID
    initial_balance: float
    current_balance: float
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer('initial_balance', 'current_balance')
    def serialize_decimal(self, value: Decimal) -> float:
        return float(value)


class PaginatedMoneyAccountResponse(BaseModel):
    """Respuesta paginada de cuentas de dinero."""
    items: list[MoneyAccountResponse]
    total: int
    skip: int
    limit: int
