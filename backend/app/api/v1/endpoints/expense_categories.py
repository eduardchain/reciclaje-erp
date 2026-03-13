"""
Endpoints API para operaciones CRUD de ExpenseCategory (Categorias de Gastos).

Permite clasificar gastos en directos e indirectos para tesoreria.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_permission, get_db
from app.schemas.expense_category import (
    ExpenseCategoryCreate,
    ExpenseCategoryUpdate,
    ExpenseCategoryResponse,
)
from app.services.base import PaginatedResponse
from app.services.expense_category import expense_category

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
def list_expense_categories(
    skip: int = Query(0, ge=0, description="Registros a saltar"),
    limit: int = Query(100, ge=1, le=500, description="Maximo de registros"),
    is_active: Optional[bool] = Query(None, description="Filtrar por estado activo"),
    search: Optional[str] = Query(None, description="Buscar por nombre"),
    sort_by: str = Query("name", description="Campo para ordenar"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Direccion de orden"),
    org_context: dict = Depends(require_permission("treasury.manage_expenses")),
    db: Session = Depends(get_db),
):
    """Listar categorias de gastos con paginacion y filtros."""
    return expense_category.get_multi(
        db=db,
        organization_id=org_context["organization_id"],
        skip=skip,
        limit=limit,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.post("", response_model=ExpenseCategoryResponse, status_code=status.HTTP_201_CREATED)
def create_expense_category(
    category_in: ExpenseCategoryCreate,
    org_context: dict = Depends(require_permission("treasury.manage_expenses")),
    db: Session = Depends(get_db),
):
    """
    Crear nueva categoria de gasto.

    - is_direct_expense=True: gasto directo (flete, pesaje — afecta costo material)
    - is_direct_expense=False: gasto indirecto (arriendo, servicios — administrativo)
    """
    return expense_category.create(
        db=db,
        obj_in=category_in,
        organization_id=org_context["organization_id"],
    )


@router.get("/{category_id}", response_model=ExpenseCategoryResponse)
def get_expense_category(
    category_id: UUID,
    org_context: dict = Depends(require_permission("treasury.manage_expenses")),
    db: Session = Depends(get_db),
):
    """Obtener una categoria de gasto por ID."""
    return expense_category.get_or_404(
        db=db,
        id=category_id,
        organization_id=org_context["organization_id"],
        detail="Categoria de gasto no encontrada",
    )


@router.patch("/{category_id}", response_model=ExpenseCategoryResponse)
def update_expense_category(
    category_id: UUID,
    category_in: ExpenseCategoryUpdate,
    org_context: dict = Depends(require_permission("treasury.manage_expenses")),
    db: Session = Depends(get_db),
):
    """Actualizar una categoria de gasto (campos parciales)."""
    return expense_category.update(
        db=db,
        id=category_id,
        obj_in=category_in,
        organization_id=org_context["organization_id"],
    )


@router.delete("/{category_id}", response_model=ExpenseCategoryResponse)
def delete_expense_category(
    category_id: UUID,
    org_context: dict = Depends(require_permission("treasury.manage_expenses")),
    db: Session = Depends(get_db),
):
    """Soft delete de categoria de gasto (is_active = False)."""
    return expense_category.delete(
        db=db,
        id=category_id,
        organization_id=org_context["organization_id"],
    )
