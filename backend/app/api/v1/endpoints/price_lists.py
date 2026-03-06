"""
Endpoints API para operaciones CRUD de PriceList (Listas de Precios).

Permite registrar y consultar precios de compra/venta por material.
Incluye endpoint especial para obtener el precio vigente de un material.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_required_org_context, get_db
from app.schemas.price_list import (
    CurrentPriceItem,
    CurrentPricesResponse,
    PriceListCreate,
    PriceListResponse,
)
from app.services.base import PaginatedResponse
from app.services.price_list import price_list

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
def list_price_lists(
    skip: int = Query(0, ge=0, description="Registros a saltar"),
    limit: int = Query(100, ge=1, le=500, description="Maximo de registros"),
    sort_by: str = Query("created_at", description="Campo para ordenar"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Direccion de orden"),
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Listar todos los registros de precios con paginacion."""
    return price_list.get_multi(
        db=db,
        organization_id=org_context["organization_id"],
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.post("", response_model=PriceListResponse, status_code=status.HTTP_201_CREATED)
def create_price_list(
    price_in: PriceListCreate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Registrar un nuevo precio para un material.

    Cada llamada crea un nuevo registro historico. El precio vigente
    sera siempre el registro mas reciente para cada material.
    """
    return price_list.create(
        db=db,
        obj_in=price_in,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )


@router.get("/current", response_model=CurrentPricesResponse)
def get_all_current_prices(
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Obtener precios vigentes de todos los materiales.
    Retorna el precio mas reciente por material para la organizacion.
    """
    items = price_list.get_all_current_prices(
        db=db, organization_id=org_context["organization_id"]
    )
    return CurrentPricesResponse(
        items=[
            CurrentPriceItem(
                material_id=item.material_id,
                purchase_price=float(item.purchase_price),
                sale_price=float(item.sale_price),
            )
            for item in items
        ]
    )


@router.get("/current/{material_id}", response_model=PriceListResponse)
def get_current_price(
    material_id: UUID,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Obtener el precio vigente (mas reciente) de un material.

    Retorna 404 si no hay precios registrados para el material.
    """
    current = price_list.get_current_price(
        db=db,
        material_id=material_id,
        organization_id=org_context["organization_id"],
    )
    if not current:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay precios registrados para este material",
        )
    return current


@router.get("/material/{material_id}", response_model=PaginatedResponse)
def get_price_history(
    material_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Obtener historial completo de precios de un material.

    Ordenado del mas reciente al mas antiguo.
    """
    return price_list.get_by_material(
        db=db,
        material_id=material_id,
        organization_id=org_context["organization_id"],
        skip=skip,
        limit=limit,
    )


@router.get("/{price_id}", response_model=PriceListResponse)
def get_price_list(
    price_id: UUID,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Obtener un registro de precio por ID."""
    return price_list.get_or_404(
        db=db,
        id=price_id,
        organization_id=org_context["organization_id"],
        detail="Registro de precio no encontrado",
    )
