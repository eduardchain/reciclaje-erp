"""
Endpoints API para operaciones CRUD de BusinessUnit (Unidades de Negocio).

Ejemplos: Fibras, Chatarra, Metales No Ferrosos.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_permission, require_any_permission, get_db
from app.schemas.business_unit import (
    BusinessUnitCreate,
    BusinessUnitUpdate,
    BusinessUnitResponse,
)
from app.services.base import PaginatedResponse
from app.services.business_unit import business_unit

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
def list_business_units(
    skip: int = Query(0, ge=0, description="Registros a saltar"),
    limit: int = Query(100, ge=1, le=500, description="Maximo de registros"),
    is_active: Optional[bool] = Query(None, description="Filtrar por estado activo"),
    search: Optional[str] = Query(None, description="Buscar por nombre"),
    sort_by: str = Query("name", description="Campo para ordenar"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Direccion de orden"),
    org_context: dict = Depends(require_any_permission("config.view_business_units", "config.manage_business_units")),
    db: Session = Depends(get_db),
):
    """Listar unidades de negocio con paginacion y filtros."""
    return business_unit.get_multi(
        db=db,
        organization_id=org_context["organization_id"],
        skip=skip,
        limit=limit,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.post("", response_model=BusinessUnitResponse, status_code=status.HTTP_201_CREATED)
def create_business_unit(
    unit_in: BusinessUnitCreate,
    org_context: dict = Depends(require_permission("config.manage_business_units")),
    db: Session = Depends(get_db),
):
    """Crear nueva unidad de negocio."""
    return business_unit.create(
        db=db,
        obj_in=unit_in,
        organization_id=org_context["organization_id"],
    )


@router.get("/{unit_id}", response_model=BusinessUnitResponse)
def get_business_unit(
    unit_id: UUID,
    org_context: dict = Depends(require_any_permission("config.view_business_units", "config.manage_business_units")),
    db: Session = Depends(get_db),
):
    """Obtener una unidad de negocio por ID."""
    return business_unit.get_or_404(
        db=db,
        id=unit_id,
        organization_id=org_context["organization_id"],
        detail="Unidad de negocio no encontrada",
    )


@router.patch("/{unit_id}", response_model=BusinessUnitResponse)
def update_business_unit(
    unit_id: UUID,
    unit_in: BusinessUnitUpdate,
    org_context: dict = Depends(require_permission("config.manage_business_units")),
    db: Session = Depends(get_db),
):
    """Actualizar una unidad de negocio (campos parciales)."""
    return business_unit.update(
        db=db,
        id=unit_id,
        obj_in=unit_in,
        organization_id=org_context["organization_id"],
    )


@router.delete("/{unit_id}", response_model=BusinessUnitResponse)
def delete_business_unit(
    unit_id: UUID,
    org_context: dict = Depends(require_permission("config.manage_business_units")),
    db: Session = Depends(get_db),
):
    """Soft delete de unidad de negocio (is_active = False)."""
    return business_unit.delete(
        db=db,
        id=unit_id,
        organization_id=org_context["organization_id"],
    )
