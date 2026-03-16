"""
Schemas Pydantic para el modelo ExpenseCategory (Categorias de Gastos).

Distingue entre gastos directos (afectan costo de material) e
indirectos (gastos administrativos). Soporta subcategorias (max 2 niveles).
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ExpenseCategoryBase(BaseModel):
    """Schema base para ExpenseCategory."""
    name: str = Field(..., min_length=1, max_length=255, description="Nombre de la categoria")
    description: Optional[str] = Field(None, max_length=500)
    is_direct_expense: bool = Field(
        False, description="True = gasto directo (afecta costo). False = indirecto."
    )


class ExpenseCategoryCreate(ExpenseCategoryBase):
    """Schema para crear una categoria de gasto."""
    parent_id: Optional[UUID] = Field(None, description="ID de la categoria padre (max 2 niveles)")


class ExpenseCategoryUpdate(BaseModel):
    """Schema para actualizar una categoria de gasto (campos opcionales)."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    is_direct_expense: Optional[bool] = None
    parent_id: Optional[UUID] = None


class ExpenseCategoryResponse(ExpenseCategoryBase):
    """Schema de respuesta para ExpenseCategory."""
    id: UUID
    organization_id: UUID
    parent_id: Optional[UUID] = None
    parent_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def extract_parent_name(cls, data):
        """Extraer parent_name del relationship o del dict."""
        if isinstance(data, dict):
            return data
        # ORM object: extraer nombre del parent relationship
        if hasattr(data, "parent") and data.parent is not None:
            data.__dict__["parent_name"] = data.parent.name
        return data


class PaginatedExpenseCategoryResponse(BaseModel):
    """Respuesta paginada de categorias de gastos."""
    items: list[ExpenseCategoryResponse]
    total: int
    skip: int
    limit: int


class ExpenseCategoryFlat(BaseModel):
    """Item plano para selectors: incluye display_name formateado."""
    id: UUID
    name: str
    display_name: str = Field(..., description="'NÓMINA > Personal' o 'TRANSPORTE'")
    parent_id: Optional[UUID] = None
    is_direct_expense: bool


class ExpenseCategoryFlatResponse(BaseModel):
    """Respuesta de lista plana para selectors."""
    items: list[ExpenseCategoryFlat]
