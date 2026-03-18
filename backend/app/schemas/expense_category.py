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
    default_business_unit_id: Optional[UUID] = Field(None, description="Default: directo a esta UN")
    default_applicable_business_unit_ids: Optional[list[UUID]] = Field(None, description="Default: compartido entre estas UNs")

    @model_validator(mode="after")
    def validate_bu_allocation(self):
        if self.default_business_unit_id and self.default_applicable_business_unit_ids:
            raise ValueError("Seleccione asignacion directa O compartida, no ambas")
        if self.default_applicable_business_unit_ids is not None and len(self.default_applicable_business_unit_ids) == 0:
            self.default_applicable_business_unit_ids = None
        return self


class ExpenseCategoryUpdate(BaseModel):
    """Schema para actualizar una categoria de gasto (campos opcionales)."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    is_direct_expense: Optional[bool] = None
    parent_id: Optional[UUID] = None
    default_business_unit_id: Optional[UUID] = None
    default_applicable_business_unit_ids: Optional[list[UUID]] = None


class ExpenseCategoryResponse(ExpenseCategoryBase):
    """Schema de respuesta para ExpenseCategory."""
    id: UUID
    organization_id: UUID
    parent_id: Optional[UUID] = None
    parent_name: Optional[str] = None
    default_business_unit_id: Optional[UUID] = None
    default_applicable_business_unit_ids: Optional[list[UUID]] = None
    default_business_unit_name: Optional[str] = None
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
    default_business_unit_id: Optional[UUID] = None
    default_applicable_business_unit_ids: Optional[list[UUID]] = None


class ExpenseCategoryFlatResponse(BaseModel):
    """Respuesta de lista plana para selectors."""
    items: list[ExpenseCategoryFlat]
