"""
Endpoints API para operaciones CRUD de Warehouse (Bodegas).
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_required_org_context, get_db
from app.schemas.warehouse import (
    WarehouseCreate,
    WarehouseUpdate,
    WarehouseResponse,
)
from app.services.base import PaginatedResponse
from app.services.warehouse import warehouse

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
def list_warehouses(
    skip: int = Query(0, ge=0, description="Registros a saltar"),
    limit: int = Query(100, ge=1, le=500, description="Maximo de registros"),
    is_active: Optional[bool] = Query(None, description="Filtrar por estado activo"),
    search: Optional[str] = Query(None, description="Buscar por nombre o direccion"),
    sort_by: str = Query("name", description="Campo para ordenar"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Direccion de orden"),
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Listar bodegas con paginacion y filtros."""
    return warehouse.get_multi(
        db=db,
        organization_id=org_context["organization_id"],
        skip=skip,
        limit=limit,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.post("", response_model=WarehouseResponse, status_code=status.HTTP_201_CREATED)
def create_warehouse(
    warehouse_in: WarehouseCreate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Crear nueva bodega."""
    return warehouse.create(
        db=db,
        obj_in=warehouse_in,
        organization_id=org_context["organization_id"],
    )


@router.get("/{warehouse_id}", response_model=WarehouseResponse)
def get_warehouse(
    warehouse_id: UUID,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Obtener una bodega por ID."""
    return warehouse.get_or_404(
        db=db,
        id=warehouse_id,
        organization_id=org_context["organization_id"],
        detail="Bodega no encontrada",
    )


@router.patch("/{warehouse_id}", response_model=WarehouseResponse)
def update_warehouse(
    warehouse_id: UUID,
    warehouse_in: WarehouseUpdate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Actualizar una bodega (campos parciales)."""
    return warehouse.update(
        db=db,
        id=warehouse_id,
        obj_in=warehouse_in,
        organization_id=org_context["organization_id"],
    )


@router.delete("/{warehouse_id}", response_model=WarehouseResponse)
def delete_warehouse(
    warehouse_id: UUID,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Soft delete de bodega (is_active = False)."""
    return warehouse.delete(
        db=db,
        id=warehouse_id,
        organization_id=org_context["organization_id"],
    )
