"""
Endpoints API para Transformacion de Materiales.

Permite desintegrar materiales compuestos en sus componentes.
Ejemplo: Motor 500kg → Cobre 200kg + Hierro 180kg + Aluminio 100kg + Merma 20kg
"""
from datetime import date, datetime, time as dt_time, timedelta, timezone as tz
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_required_org_context, get_db
from app.schemas.material_transformation import (
    MaterialTransformationCreate,
    AnnulTransformationRequest,
    MaterialTransformationResponse,
    TransformationLineResponse,
    PaginatedMaterialTransformationResponse,
)
from app.services.material_transformation import material_transformation

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_response(t, warnings: list[str] | None = None) -> dict:
    """Convertir MaterialTransformation ORM a dict con nombres de relaciones."""
    data = {c.name: getattr(t, c.name) for c in t.__table__.columns}
    data["source_material_code"] = t.source_material.code if t.source_material else None
    data["source_material_name"] = t.source_material.name if t.source_material else None
    data["source_warehouse_name"] = t.source_warehouse.name if t.source_warehouse else None
    data["warnings"] = warnings or []
    data["lines"] = [
        {
            **{c.name: getattr(line, c.name) for c in line.__table__.columns},
            "destination_material_code": line.destination_material.code if line.destination_material else None,
            "destination_material_name": line.destination_material.name if line.destination_material else None,
            "destination_warehouse_name": line.destination_warehouse.name if line.destination_warehouse else None,
        }
        for line in t.lines
    ]
    return data


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=MaterialTransformationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_transformation(
    data: MaterialTransformationCreate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Crear transformacion de material.

    Desintegra un material de origen en multiples materiales destino.
    El costo se distribuye proporcionalmente por peso o manualmente.
    """
    transformation, warnings = material_transformation.create(
        db=db, data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = material_transformation.get(db, transformation.id, org_context["organization_id"])
    return _to_response(loaded, warnings)


@router.post(
    "/{transformation_id}/annul",
    response_model=MaterialTransformationResponse,
)
def annul_transformation(
    transformation_id: UUID,
    data: AnnulTransformationRequest,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Anular transformacion — revierte stock de origen y destinos."""
    transformation = material_transformation.annul(
        db=db,
        transformation_id=transformation_id,
        reason=data.reason,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = material_transformation.get(db, transformation.id, org_context["organization_id"])
    return _to_response(loaded)


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=PaginatedMaterialTransformationResponse,
)
def list_transformations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    source_material_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None, alias="status"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Listar transformaciones con filtros."""
    date_from_dt = datetime.combine(date_from, dt_time.min, tzinfo=tz.utc) if date_from else None
    date_to_dt = datetime.combine(date_to + timedelta(days=1), dt_time.min, tzinfo=tz.utc) if date_to else None
    transformations, total = material_transformation.get_multi(
        db=db,
        organization_id=org_context["organization_id"],
        skip=skip,
        limit=limit,
        source_material_id=source_material_id,
        status_filter=status,
        date_from=date_from_dt,
        date_to=date_to_dt,
    )

    items = [MaterialTransformationResponse(**_to_response(t)) for t in transformations]
    return PaginatedMaterialTransformationResponse(
        items=items, total=total, skip=skip, limit=limit
    )


@router.get(
    "/by-number/{number}",
    response_model=MaterialTransformationResponse,
)
def get_transformation_by_number(
    number: int,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Obtener transformacion por numero secuencial."""
    t = material_transformation.get_by_number(
        db=db, number=number,
        organization_id=org_context["organization_id"],
    )
    return _to_response(t)


@router.get(
    "/{transformation_id}",
    response_model=MaterialTransformationResponse,
)
def get_transformation(
    transformation_id: UUID,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Obtener transformacion por ID."""
    t = material_transformation.get(
        db=db,
        transformation_id=transformation_id,
        organization_id=org_context["organization_id"],
    )
    return _to_response(t)
