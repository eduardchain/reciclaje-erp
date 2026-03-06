"""
Endpoints API para Ajustes de Inventario.

Endpoints especializados por tipo de ajuste:
- POST /increase: Aumento de stock
- POST /decrease: Disminucion de stock
- POST /recount: Conteo fisico
- POST /zero-out: Llevar a cero
- POST /{id}/annul: Anular ajuste
- POST /warehouse-transfer: Traslado entre bodegas

Queries:
- GET /: Listar con filtros
- GET /{id}: Obtener por ID
- GET /by-number/{number}: Obtener por numero
"""
from datetime import date, datetime, time as dt_time, timedelta, timezone as tz
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_required_org_context, get_db
from app.schemas.inventory_adjustment import (
    IncreaseCreate,
    DecreaseCreate,
    RecountCreate,
    ZeroOutCreate,
    AnnulAdjustmentRequest,
    WarehouseTransferCreate,
    InventoryAdjustmentResponse,
    PaginatedInventoryAdjustmentResponse,
    WarehouseTransferResponse,
)
from app.services.inventory_adjustment import inventory_adjustment

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_response(adj, warnings: list[str] | None = None) -> dict:
    """Convertir InventoryAdjustment ORM a dict con nombres de relaciones."""
    data = {c.name: getattr(adj, c.name) for c in adj.__table__.columns}
    data["material_code"] = adj.material.code if adj.material else None
    data["material_name"] = adj.material.name if adj.material else None
    data["warehouse_name"] = adj.warehouse.name if adj.warehouse else None
    data["warnings"] = warnings or []
    return data


# ---------------------------------------------------------------------------
# Endpoints de creacion
# ---------------------------------------------------------------------------

@router.post(
    "/increase",
    response_model=InventoryAdjustmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_increase(
    data: IncreaseCreate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Aumento de stock — recalcula costo promedio."""
    adj, warnings = inventory_adjustment.increase(
        db=db, data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = inventory_adjustment.get(db, adj.id, org_context["organization_id"])
    return _to_response(loaded, warnings)


@router.post(
    "/decrease",
    response_model=InventoryAdjustmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_decrease(
    data: DecreaseCreate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Disminucion de stock — usa costo promedio actual."""
    adj, warnings = inventory_adjustment.decrease(
        db=db, data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = inventory_adjustment.get(db, adj.id, org_context["organization_id"])
    return _to_response(loaded, warnings)


@router.post(
    "/recount",
    response_model=InventoryAdjustmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_recount(
    data: RecountCreate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Conteo fisico — ajusta al stock contado."""
    adj, warnings = inventory_adjustment.recount(
        db=db, data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = inventory_adjustment.get(db, adj.id, org_context["organization_id"])
    return _to_response(loaded, warnings)


@router.post(
    "/zero-out",
    response_model=InventoryAdjustmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_zero_out(
    data: ZeroOutCreate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Llevar stock a cero — elimina todo el stock liquidado."""
    adj, warnings = inventory_adjustment.zero_out(
        db=db, data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = inventory_adjustment.get(db, adj.id, org_context["organization_id"])
    return _to_response(loaded, warnings)


@router.post(
    "/{adjustment_id}/annul",
    response_model=InventoryAdjustmentResponse,
)
def annul_adjustment(
    adjustment_id: UUID,
    data: AnnulAdjustmentRequest,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Anular ajuste — revierte cambios de stock."""
    adj = inventory_adjustment.annul(
        db=db,
        adjustment_id=adjustment_id,
        reason=data.reason,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = inventory_adjustment.get(db, adj.id, org_context["organization_id"])
    return _to_response(loaded)


@router.post(
    "/warehouse-transfer",
    response_model=WarehouseTransferResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_warehouse_transfer(
    data: WarehouseTransferCreate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Traslado de material entre bodegas."""
    from app.models.material import Material
    from app.models.warehouse import Warehouse

    movements, warnings = inventory_adjustment.transfer_between_warehouses(
        db=db, data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )

    material = db.get(Material, data.material_id)
    source_wh = db.get(Warehouse, data.source_warehouse_id)
    dest_wh = db.get(Warehouse, data.destination_warehouse_id)

    return WarehouseTransferResponse(
        material_id=data.material_id,
        material_code=material.code if material else None,
        material_name=material.name if material else None,
        source_warehouse_id=data.source_warehouse_id,
        source_warehouse_name=source_wh.name if source_wh else None,
        destination_warehouse_id=data.destination_warehouse_id,
        destination_warehouse_name=dest_wh.name if dest_wh else None,
        quantity=data.quantity,
        date=data.date,
        reason=data.reason,
        notes=data.notes,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=PaginatedInventoryAdjustmentResponse,
)
def list_adjustments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    material_id: Optional[UUID] = Query(None),
    adjustment_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None, alias="status"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Listar ajustes de inventario con filtros."""
    date_from_dt = datetime.combine(date_from, dt_time.min, tzinfo=tz.utc) if date_from else None
    date_to_dt = datetime.combine(date_to + timedelta(days=1), dt_time.min, tzinfo=tz.utc) if date_to else None
    adjustments, total = inventory_adjustment.get_multi(
        db=db,
        organization_id=org_context["organization_id"],
        skip=skip,
        limit=limit,
        material_id=material_id,
        adjustment_type=adjustment_type,
        status_filter=status,
        date_from=date_from_dt,
        date_to=date_to_dt,
    )

    items = [InventoryAdjustmentResponse(**_to_response(a)) for a in adjustments]
    return PaginatedInventoryAdjustmentResponse(
        items=items, total=total, skip=skip, limit=limit
    )


@router.get(
    "/by-number/{number}",
    response_model=InventoryAdjustmentResponse,
)
def get_adjustment_by_number(
    number: int,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Obtener ajuste por numero secuencial."""
    adj = inventory_adjustment.get_by_number(
        db=db, number=number,
        organization_id=org_context["organization_id"],
    )
    return _to_response(adj)


@router.get(
    "/{adjustment_id}",
    response_model=InventoryAdjustmentResponse,
)
def get_adjustment(
    adjustment_id: UUID,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Obtener ajuste por ID."""
    adj = inventory_adjustment.get(
        db=db, adjustment_id=adjustment_id,
        organization_id=org_context["organization_id"],
    )
    return _to_response(adj)
