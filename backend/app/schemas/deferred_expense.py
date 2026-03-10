"""
Schemas Pydantic para Gastos Diferidos (DeferredExpense).

- DeferredExpenseCreate: Crear un nuevo gasto diferido
- DeferredExpenseResponse: Respuesta con datos calculados (remaining_amount, next_amount)
- DeferredApplicationResponse: Detalle de cada cuota aplicada
- PaginatedDeferredExpenseResponse: Lista paginada
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer, model_validator


class DeferredExpenseCreate(BaseModel):
    """Crear un gasto diferido."""
    name: str = Field(..., min_length=1, max_length=200, description="Nombre descriptivo")
    total_amount: Decimal = Field(..., gt=0, description="Monto total del gasto")
    total_months: int = Field(..., ge=2, le=60, description="Numero de cuotas (2-60)")
    expense_category_id: UUID = Field(..., description="Categoria del gasto")
    expense_type: str = Field(..., description="'expense' o 'provision_expense'")
    account_id: Optional[UUID] = Field(None, description="Cuenta (requerida si expense_type='expense')")
    provision_id: Optional[UUID] = Field(None, description="Provision (requerida si expense_type='provision_expense')")
    description: Optional[str] = Field(None, max_length=500)
    start_date: date = Field(..., description="Fecha de inicio")

    @model_validator(mode="after")
    def validate_type_fields(self):
        if self.expense_type not in ("expense", "provision_expense"):
            raise ValueError("expense_type debe ser 'expense' o 'provision_expense'")
        if self.expense_type == "expense" and not self.account_id:
            raise ValueError("account_id es requerido para tipo 'expense'")
        if self.expense_type == "provision_expense" and not self.provision_id:
            raise ValueError("provision_id es requerido para tipo 'provision_expense'")
        return self


class DeferredApplicationResponse(BaseModel):
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


class DeferredExpenseResponse(BaseModel):
    """Respuesta completa de un gasto diferido."""
    id: UUID
    organization_id: UUID
    name: str
    total_amount: float
    monthly_amount: float
    total_months: int
    applied_months: int
    expense_category_id: UUID
    expense_category_name: Optional[str] = None
    expense_type: str
    account_id: Optional[UUID] = None
    account_name: Optional[str] = None
    provision_id: Optional[UUID] = None
    provision_name: Optional[str] = None
    description: Optional[str] = None
    start_date: date
    status: str
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[UUID] = None
    created_by: Optional[UUID] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Campos calculados
    remaining_amount: float = 0
    next_amount: float = 0
    applications: List[DeferredApplicationResponse] = []

    model_config = {"from_attributes": True}

    @field_serializer('total_amount', 'monthly_amount')
    def serialize_decimal(self, value: Decimal) -> float:
        return float(value)


class PaginatedDeferredExpenseResponse(BaseModel):
    """Respuesta paginada de gastos diferidos."""
    items: List[DeferredExpenseResponse]
    total: int
    skip: int
    limit: int
