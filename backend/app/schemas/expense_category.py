"""
Schemas Pydantic para el modelo ExpenseCategory (Categorias de Gastos).

Distingue entre gastos directos (afectan costo de material) e
indirectos (gastos administrativos).
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ExpenseCategoryBase(BaseModel):
    """Schema base para ExpenseCategory."""
    name: str = Field(..., min_length=1, max_length=255, description="Nombre de la categoria")
    description: Optional[str] = Field(None, max_length=500)
    is_direct_expense: bool = Field(
        False, description="True = gasto directo (afecta costo). False = indirecto."
    )


class ExpenseCategoryCreate(ExpenseCategoryBase):
    """Schema para crear una categoria de gasto."""
    pass


class ExpenseCategoryUpdate(BaseModel):
    """Schema para actualizar una categoria de gasto (campos opcionales)."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    is_direct_expense: Optional[bool] = None


class ExpenseCategoryResponse(ExpenseCategoryBase):
    """Schema de respuesta para ExpenseCategory."""
    id: UUID
    organization_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedExpenseCategoryResponse(BaseModel):
    """Respuesta paginada de categorias de gastos."""
    items: list[ExpenseCategoryResponse]
    total: int
    skip: int
    limit: int
