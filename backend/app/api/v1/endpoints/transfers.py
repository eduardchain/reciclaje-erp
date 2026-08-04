"""Endpoints Transfer — traslados intersede dos pasos (SAC E3.1, plan v1.1 §2.4).

Router completo gated por flag two_step_transfers_enabled (E10): 403 incluso
para admins sin flag. Permisos: inventory.transfer (despacho/anular),
inventory.transfer_receive (recepcion/resolucion — separacion de funciones,
base de la politica "utilidad cero JM"), inventory.view (bandeja/detalle).
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_org_flag, require_permission
from app.models.transfer import Transfer, TransferLine
from app.schemas.transfer import (
    TransferAnnulRequest,
    TransferDispatchCreate,
    TransferLineResponse,
    TransferListResponse,
    TransferReceiveRequest,
    TransferResolveRequest,
    TransferResponse,
)
from app.services.transfer import transfer_service

router = APIRouter(
    dependencies=[Depends(require_org_flag("two_step_transfers_enabled"))]
)


def _line_response(line: TransferLine) -> TransferLineResponse:
    variance = None
    recv = line.resolved_quantity if line.resolved_quantity is not None else line.quantity_received
    if recv is not None and line.quantity_dispatched:
        variance = (
            abs(recv - line.quantity_dispatched) / line.quantity_dispatched
        ).quantize(Decimal("0.0001"))
    material = line.material
    return TransferLineResponse(
        id=line.id,
        material_id=line.material_id,
        material_code=material.code if material else None,
        material_name=material.name if material else None,
        material_unit=(material.default_unit or "kg") if material else "kg",
        quantity_dispatched=line.quantity_dispatched,
        quantity_received=line.quantity_received,
        resolved_quantity=line.resolved_quantity,
        unit_cost=line.unit_cost,
        is_contributor=line.is_contributor,
        kg_lead_equivalent=line.kg_lead_equivalent,
        maquila_amount=line.maquila_amount,
        discrepancy_task_id=line.discrepancy_task_id,
        effects_emitted=line.effects_emitted,
        variance_pct=variance,
    )


def _enrich(transfer: Transfer, warnings: Optional[list[str]] = None) -> TransferResponse:
    def _user_name(user) -> Optional[str]:
        if user is None:
            return None
        return user.full_name or user.email

    return TransferResponse(
        id=transfer.id,
        transfer_number=transfer.transfer_number,
        from_warehouse_id=transfer.from_warehouse_id,
        from_warehouse_name=transfer.from_warehouse.name if transfer.from_warehouse else None,
        to_warehouse_id=transfer.to_warehouse_id,
        to_warehouse_name=transfer.to_warehouse.name if transfer.to_warehouse else None,
        transit_warehouse_id=transfer.transit_warehouse_id,
        transit_warehouse_name=transfer.transit_warehouse.name if transfer.transit_warehouse else None,
        dispatch_date=transfer.dispatch_date,
        received_date=transfer.received_date,
        status=transfer.status,
        notes=transfer.notes,
        created_by_name=_user_name(transfer.created_by_user),
        received_by_name=_user_name(transfer.received_by_user),
        annulled_reason=transfer.annulled_reason,
        annulled_at=transfer.annulled_at,
        created_at=transfer.created_at,
        lines=[_line_response(ln) for ln in transfer.lines],
        warnings=warnings or [],
    )


@router.post("", response_model=TransferResponse, status_code=201)
def dispatch_transfer(
    payload: TransferDispatchCreate,
    db: Session = Depends(get_db),
    org_context: dict = Depends(require_permission("inventory.transfer")),
):
    transfer, warnings = transfer_service.dispatch(
        db, payload,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    transfer = transfer_service.get(db, transfer.id, org_context["organization_id"])
    return _enrich(transfer, warnings)


@router.get("", response_model=TransferListResponse)
def list_transfers(
    db: Session = Depends(get_db),
    org_context: dict = Depends(require_permission("inventory.view")),
    status: Optional[str] = Query(None),
    pending_receipt: bool = Query(False),
    from_warehouse_id: Optional[UUID] = Query(None),
    to_warehouse_id: Optional[UUID] = Query(None),
    material_id: Optional[UUID] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    sort: str = Query("newest"),
):
    items, total, pending_count = transfer_service.get_multi(
        db,
        organization_id=org_context["organization_id"],
        status_filter=status,
        pending_receipt=pending_receipt,
        from_warehouse_id=from_warehouse_id,
        to_warehouse_id=to_warehouse_id,
        material_id=material_id,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
        sort=sort,
    )
    return TransferListResponse(
        items=[_enrich(t) for t in items],
        total=total,
        pending_receipt_count=pending_count,
    )


@router.get("/{transfer_id}", response_model=TransferResponse)
def get_transfer(
    transfer_id: UUID,
    db: Session = Depends(get_db),
    org_context: dict = Depends(require_permission("inventory.view")),
):
    transfer = transfer_service.get(db, transfer_id, org_context["organization_id"])
    return _enrich(transfer)


@router.post("/{transfer_id}/receive", response_model=TransferResponse)
def receive_transfer(
    transfer_id: UUID,
    payload: TransferReceiveRequest,
    db: Session = Depends(get_db),
    org_context: dict = Depends(require_permission("inventory.transfer_receive")),
):
    _, warnings = transfer_service.receive(
        db, transfer_id, payload,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    transfer = transfer_service.get(db, transfer_id, org_context["organization_id"])
    return _enrich(transfer, warnings)


@router.post("/{transfer_id}/resolve", response_model=TransferResponse)
def resolve_transfer(
    transfer_id: UUID,
    payload: TransferResolveRequest,
    db: Session = Depends(get_db),
    org_context: dict = Depends(require_permission("inventory.transfer_receive")),
):
    _, warnings = transfer_service.resolve(
        db, transfer_id, payload,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    transfer = transfer_service.get(db, transfer_id, org_context["organization_id"])
    return _enrich(transfer, warnings)


@router.post("/{transfer_id}/annul", response_model=TransferResponse)
def annul_transfer(
    transfer_id: UUID,
    payload: TransferAnnulRequest,
    db: Session = Depends(get_db),
    org_context: dict = Depends(require_permission("inventory.transfer")),
):
    _, warnings = transfer_service.annul(
        db, transfer_id, payload.reason,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    transfer = transfer_service.get(db, transfer_id, org_context["organization_id"])
    return _enrich(transfer, warnings)
