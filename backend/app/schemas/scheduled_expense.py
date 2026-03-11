"""
Schemas Pydantic para Gastos Diferidos Programados (ScheduledExpense).

Nuevo modelo que reemplaza DeferredExpense.
Flujo: pago upfront (deferred_funding) -> cuotas mensuales (deferred_expense) en P&L.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer


class ScheduledExpenseCreate(BaseModel):
    """Crear un gasto diferido programado."""
    name: str = Field(..., min_length=1, max_length=200, description="Nombre descriptivo")
    total_amount: Decimal = Field(..., gt=0, description="Monto total del gasto")
    total_months: int = Field(..., ge=2, le=60, description="Numero de cuotas (2-60)")
    source_account_id: UUID = Field(..., description="Cuenta de donde sale el pago inicial")
    expense_category_id: UUID = Field(..., description="Categoria del gasto")
    start_date: date = Field(..., description="Fecha de inicio")
    apply_day: int = Field(1, ge=1, le=28, description="Dia del mes para aplicar cuotas (1-28)")
    description: Optional[str] = Field(None, max_length=500)


class ScheduledExpenseApplicationResponse(BaseModel):
    """Respuesta de una cuota aplicada."""
    id: UUID
    application_number: int
    amount: float
    money_movement_id: UUID
    applied_at: datetime
    applied_by: Optional[UUID] = None

    model_config = {"from_attributes": True}

    @field_serializer('amount')
    def serialize_amount(self, value: Decimal) -> float:
        return float(value)


class ScheduledExpenseResponse(BaseModel):
    """Respuesta completa de un gasto diferido programado."""
    id: UUID
    organization_id: UUID
    name: str
    description: Optional[str] = None
    total_amount: float
    monthly_amount: float
    total_months: int
    applied_months: int
    source_account_id: UUID
    source_account_name: Optional[str] = None
    prepaid_third_party_id: UUID
    prepaid_third_party_name: Optional[str] = None
    expense_category_id: UUID
    expense_category_name: Optional[str] = None
    funding_movement_id: Optional[UUID] = None
    start_date: date
    apply_day: int
    next_application_date: Optional[date] = None
    status: str
    created_by: Optional[UUID] = None
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[UUID] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Campos calculados
    remaining_amount: float = 0
    next_amount: float = 0
    prepaid_balance: float = 0
    applications: List[ScheduledExpenseApplicationResponse] = []

    model_config = {"from_attributes": True}

    @field_serializer('total_amount', 'monthly_amount')
    def serialize_decimal(self, value: Decimal) -> float:
        return float(value)


class PaginatedScheduledExpenseResponse(BaseModel):
    """Respuesta paginada."""
    items: List[ScheduledExpenseResponse]
    total: int
    skip: int
    limit: int
