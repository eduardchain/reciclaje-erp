"""Endpoints de la Salida de control y del Talonario de remisiones (SAC).

Plan: docs/planes/plan-sac-documentos-control.md v1.2 §4.3 y §4.5.

Router gated por `kg_ledger_enabled` (403 incluso para admins, #75). Permisos
de ventas (la salida de control es una captura de despacho, como la Salida
de Plomo). NO entra a `SCOPED_ENDPOINTS` (#129): Ingrid recibe 403.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_org_flag, require_permission
from app.models.control_dispatch import ControlDispatch
from app.models.user import User
from app.schemas.control_dispatch import (
    ControlDispatchAnnulRequest,
    ControlDispatchCreate,
    ControlDispatchLineResponse,
    ControlDispatchListResponse,
    ControlDispatchResponse,
    ControlDispatchUpdate,
    RemissionBookResponse,
)
from app.services.control_dispatch import control_dispatch_service
from app.services.remission_book import remission_book

router = APIRouter(dependencies=[Depends(require_org_flag("kg_ledger_enabled"))])
remissions_router = APIRouter(dependencies=[Depends(require_org_flag("kg_ledger_enabled"))])


def _names(db: Session, dispatches: list[ControlDispatch]) -> dict:
    ids = {u for d in dispatches for u in (d.created_by, d.annulled_by)} - {None}
    if not ids:
        return {}
    return {r[0]: r[1] for r in db.execute(select(User.id, User.full_name).where(User.id.in_(ids))).all()}


def _enrich(d: ControlDispatch, names: dict, warnings: Optional[list[str]] = None) -> ControlDispatchResponse:
    # Campo por campo (trampa #95): un campo nuevo del schema se agrega ACA.
    return ControlDispatchResponse(
        id=d.id,
        dispatch_number=d.dispatch_number,
        date=d.date,
        warehouse_id=d.warehouse_id,
        warehouse_name=d.warehouse.name if d.warehouse else None,
        third_party_id=d.third_party_id,
        third_party_name=d.third_party.name if d.third_party else None,
        remission_number=d.remission_number,
        notes=d.notes,
        status=d.status,
        annulled_reason=d.annulled_reason,
        annulled_at=d.annulled_at,
        annulled_by_name=names.get(d.annulled_by),
        created_at=d.created_at,
        created_by_name=names.get(d.created_by),
        lines=[
            ControlDispatchLineResponse(
                id=ln.id,
                material_id=ln.material_id,
                material_code=ln.material.code if ln.material else None,
                material_name=ln.material.name if ln.material else None,
                material_unit=(ln.material.default_unit if ln.material else None) or "kg",
                quantity=ln.quantity,
                scale_weight_kg=ln.scale_weight_kg,
            )
            for ln in sorted(d.lines, key=lambda x: (x.material.code if x.material else ""))
        ],
        warnings=warnings or [],
    )


@router.get("", response_model=ControlDispatchListResponse)
def list_control_dispatches(
    db: Session = Depends(get_db),
    context=Depends(require_permission("sales.view")),
    status_filter: Optional[str] = Query(None, alias="status", pattern="^(registered|annulled)$"),
    search: Optional[str] = Query(None, max_length=100),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    rows, total = control_dispatch_service.get_multi(
        db, context["organization_id"], status_filter=status_filter, search=search,
        date_from=date_from, date_to=date_to, skip=skip, limit=limit,
    )
    names = _names(db, rows)
    return ControlDispatchListResponse(items=[_enrich(d, names) for d in rows], total=total)


@router.get("/{dispatch_id}", response_model=ControlDispatchResponse)
def get_control_dispatch(
    dispatch_id: UUID,
    db: Session = Depends(get_db),
    context=Depends(require_permission("sales.view")),
):
    d = control_dispatch_service.get(db, dispatch_id, context["organization_id"])
    return _enrich(d, _names(db, [d]))


@router.post("", response_model=ControlDispatchResponse, status_code=status.HTTP_201_CREATED)
def create_control_dispatch(
    payload: ControlDispatchCreate,
    db: Session = Depends(get_db),
    context=Depends(require_permission("sales.create")),
):
    d, warnings = control_dispatch_service.create(
        db, payload, context["organization_id"], context["user"].id
    )
    return _enrich(d, _names(db, [d]), warnings)


@router.patch("/{dispatch_id}", response_model=ControlDispatchResponse)
def update_control_dispatch(
    dispatch_id: UUID,
    payload: ControlDispatchUpdate,
    db: Session = Depends(get_db),
    context=Depends(require_permission("sales.edit")),
):
    d, warnings = control_dispatch_service.update(
        db, dispatch_id, payload, context["organization_id"]
    )
    return _enrich(d, _names(db, [d]), warnings)


@router.post("/{dispatch_id}/annul", response_model=ControlDispatchResponse)
def annul_control_dispatch(
    dispatch_id: UUID,
    payload: ControlDispatchAnnulRequest,
    db: Session = Depends(get_db),
    context=Depends(require_permission("sales.cancel")),
):
    d = control_dispatch_service.annul(
        db, dispatch_id, payload.reason, context["organization_id"], context["user"].id
    )
    return _enrich(d, _names(db, [d]))


@remissions_router.get("", response_model=RemissionBookResponse)
def list_remissions(
    db: Session = Depends(get_db),
    # AND: la vista muestra Entradas (compras) y Salidas de control (ventas).
    context=Depends(require_permission("purchases.view", "sales.view")),
    remission_from: Optional[int] = Query(None, ge=0),
    remission_to: Optional[int] = Query(None, ge=0),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    search: Optional[str] = Query(None, max_length=50),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    return remission_book(
        db, context["organization_id"],
        remission_from=remission_from, remission_to=remission_to,
        date_from=date_from, date_to=date_to, search=search,
        desc=(order == "desc"), skip=skip, limit=limit,
    )
