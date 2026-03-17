"""
Endpoints API para CRUD de ThirdPartyCategory (Categorias de Terceros).

Permite clasificar terceros por behavior_type para controlar
donde aparecen en la UI y como se reportan financieramente.
Soporta subcategorias (max 2 niveles) con endpoint flat para selectors.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_permission, get_db
from app.schemas.third_party_category import (
    ThirdPartyCategoryCreate,
    ThirdPartyCategoryUpdate,
    ThirdPartyCategoryResponse,
    ThirdPartyCategoryFlatResponse,
)
from app.services.base import PaginatedResponse
from app.services.third_party_category import third_party_category

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
def list_third_party_categories(
    skip: int = Query(0, ge=0, description="Registros a saltar"),
    limit: int = Query(100, ge=1, le=500, description="Maximo de registros"),
    is_active: Optional[bool] = Query(None, description="Filtrar por estado activo"),
    search: Optional[str] = Query(None, description="Buscar por nombre"),
    sort_by: str = Query("name", description="Campo para ordenar"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Direccion de orden"),
    org_context: dict = Depends(require_permission("third_parties.view")),
    db: Session = Depends(get_db),
):
    """Listar categorias de terceros con paginacion y parent_name."""
    return third_party_category.get_multi_with_parent(
        db=db,
        organization_id=org_context["organization_id"],
        skip=skip,
        limit=limit,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.post("", response_model=ThirdPartyCategoryResponse, status_code=status.HTTP_201_CREATED)
def create_third_party_category(
    category_in: ThirdPartyCategoryCreate,
    org_context: dict = Depends(require_permission("third_parties.create")),
    db: Session = Depends(get_db),
):
    """
    Crear nueva categoria de tercero.

    - behavior_type: obligatorio para nivel 1, heredado en subcategorias
    - parent_id: ID de la categoria padre (max 2 niveles)
    """
    return third_party_category.create(
        db=db,
        obj_in=category_in,
        organization_id=org_context["organization_id"],
    )


@router.get("/flat", response_model=ThirdPartyCategoryFlatResponse)
def get_flat_categories(
    behavior_type: Optional[str] = Query(None, description="Filtrar por behavior_type"),
    org_context: dict = Depends(require_permission("third_parties.view")),
    db: Session = Depends(get_db),
):
    """Lista plana con display_name para selectors (ej: 'PROVEEDORES > Locales')."""
    return third_party_category.get_flat(
        db=db,
        organization_id=org_context["organization_id"],
        behavior_type=behavior_type,
    )


@router.get("/{category_id}", response_model=ThirdPartyCategoryResponse)
def get_third_party_category(
    category_id: UUID,
    org_context: dict = Depends(require_permission("third_parties.view")),
    db: Session = Depends(get_db),
):
    """Obtener una categoria de tercero por ID."""
    return third_party_category.get_or_404(
        db=db,
        id=category_id,
        organization_id=org_context["organization_id"],
        detail="Categoria de tercero no encontrada",
    )


@router.patch("/{category_id}", response_model=ThirdPartyCategoryResponse)
def update_third_party_category(
    category_id: UUID,
    category_in: ThirdPartyCategoryUpdate,
    org_context: dict = Depends(require_permission("third_parties.edit")),
    db: Session = Depends(get_db),
):
    """Actualizar una categoria de tercero (campos parciales)."""
    return third_party_category.update(
        db=db,
        id=category_id,
        obj_in=category_in,
        organization_id=org_context["organization_id"],
    )


@router.delete("/{category_id}", response_model=ThirdPartyCategoryResponse)
def delete_third_party_category(
    category_id: UUID,
    org_context: dict = Depends(require_permission("third_parties.edit")),
    db: Session = Depends(get_db),
):
    """Soft delete de categoria (is_active = False). Falla si tiene hijos o terceros asignados."""
    return third_party_category.delete(
        db=db,
        id=category_id,
        organization_id=org_context["organization_id"],
    )
