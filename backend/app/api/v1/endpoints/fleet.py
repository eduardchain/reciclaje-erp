"""Endpoints de Driver y Vehicle (SAC E1, v0.5 §11.1.14, plan §4.5).

CRUD estandar (patron warehouses): GET/POST /drivers + PATCH /drivers/{id},
idem /vehicles. Soft delete via PATCH is_active=false. Permisos D5:
config.view_fleet / config.manage_fleet.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.schemas.fleet import (
    DriverCreate,
    DriverResponse,
    DriverUpdate,
    VehicleCreate,
    VehicleResponse,
    VehicleUpdate,
)
from app.services.base import PaginatedResponse
from app.services.fleet import driver, vehicle

drivers_router = APIRouter()
vehicles_router = APIRouter()


# --------------------------------------------------------------------------
# Drivers
# --------------------------------------------------------------------------

@drivers_router.get("", response_model=PaginatedResponse)
def list_drivers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    include_inactive: bool = Query(False),
    org_context: dict = Depends(require_permission("config.view_fleet")),
    db: Session = Depends(get_db),
):
    """Listar conductores (activos por default)."""
    return driver.get_multi(
        db=db,
        organization_id=org_context["organization_id"],
        skip=skip,
        limit=limit,
        is_active=None if include_inactive else True,
        sort_by="name",
        sort_order="asc",
    )


@drivers_router.post("", response_model=DriverResponse, status_code=status.HTTP_201_CREATED)
def create_driver(
    driver_in: DriverCreate,
    org_context: dict = Depends(require_permission("config.manage_fleet")),
    db: Session = Depends(get_db),
):
    """Crear conductor."""
    return driver.create(
        db=db, obj_in=driver_in, organization_id=org_context["organization_id"]
    )


@drivers_router.patch("/{driver_id}", response_model=DriverResponse)
def update_driver(
    driver_id: UUID,
    driver_in: DriverUpdate,
    org_context: dict = Depends(require_permission("config.manage_fleet")),
    db: Session = Depends(get_db),
):
    """Editar conductor (incluye soft delete via is_active)."""
    return driver.update(
        db=db,
        id=driver_id,
        obj_in=driver_in,
        organization_id=org_context["organization_id"],
    )


# --------------------------------------------------------------------------
# Vehicles
# --------------------------------------------------------------------------

@vehicles_router.get("", response_model=PaginatedResponse)
def list_vehicles(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    include_inactive: bool = Query(False),
    org_context: dict = Depends(require_permission("config.view_fleet")),
    db: Session = Depends(get_db),
):
    """Listar vehiculos (activos por default)."""
    return vehicle.get_multi(
        db=db,
        organization_id=org_context["organization_id"],
        skip=skip,
        limit=limit,
        is_active=None if include_inactive else True,
        sort_by="plate",
        sort_order="asc",
    )


@vehicles_router.post("", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
def create_vehicle(
    vehicle_in: VehicleCreate,
    org_context: dict = Depends(require_permission("config.manage_fleet")),
    db: Session = Depends(get_db),
):
    """Crear vehiculo (placa activa unica por org — D14, en servicio)."""
    return vehicle.create(
        db=db, obj_in=vehicle_in, organization_id=org_context["organization_id"]
    )


@vehicles_router.patch("/{vehicle_id}", response_model=VehicleResponse)
def update_vehicle(
    vehicle_id: UUID,
    vehicle_in: VehicleUpdate,
    org_context: dict = Depends(require_permission("config.manage_fleet")),
    db: Session = Depends(get_db),
):
    """Editar vehiculo (incluye soft delete / reactivacion via is_active)."""
    return vehicle.update(
        db=db,
        id=vehicle_id,
        obj_in=vehicle_in,
        organization_id=org_context["organization_id"],
    )
