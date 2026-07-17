"""Endpoints InboundOrder — Recepcion unificada (SAC E2, plan §4.2).

Router completo gated por flag kg_ledger_enabled (D10). Permisos: reusa los
de compras (D13 — la Recepcion ES la captura de compras/entradas):
purchases.create (POST), purchases.view (GET), purchases.edit (PATCH D18,
David corrige sus capturas), purchases.cancel (annul, Johana).
"""
from collections import defaultdict, deque
from datetime import date, datetime, time as dt_time, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_org_flag, require_permission
from app.models.inbound_order import InboundOrder
from app.schemas.inbound_order import (
    InboundOrderAnnulRequest,
    InboundOrderCreate,
    InboundOrderLineResponse,
    InboundOrderListResponse,
    InboundOrderResponse,
    InboundOrderUpdate,
)
from app.services.inbound_order import inbound_order_service

router = APIRouter(dependencies=[Depends(require_org_flag("kg_ledger_enabled"))])


def _enrich(
    db: Session,
    order: InboundOrder,
    kg_by_movement: dict,
    receipt_movements: list,
    warnings: Optional[list[str]] = None,
) -> InboundOrderResponse:
    """Arma la response con lineas enriquecidas (#54) y kg emitidos por linea.

    El kg de cada linea se matchea por firma (material, cantidad) contra los
    movimientos inbound_receipt vivos (deque — display only)."""
    kg_by_signature: dict = defaultdict(deque)
    for mov in receipt_movements:
        delta = kg_by_movement.get(mov.id)
        if delta is not None:
            kg_by_signature[(mov.material_id, mov.quantity)].append(delta)

    lines = []
    total_kg = None
    for line in order.lines:
        kg_lead = None
        bucket = kg_by_signature.get((line.material_id, line.quantity))
        if bucket:
            kg_lead = bucket.popleft()
            total_kg = (total_kg or 0) + kg_lead
        lines.append(
            InboundOrderLineResponse(
                id=line.id,
                material_id=line.material_id,
                material_code=line.material.code if line.material else None,
                material_name=line.material.name if line.material else None,
                material_unit=(line.material.default_unit or "kg") if line.material else "kg",
                quantity=line.quantity,
                unit=line.unit,
                unit_price=line.unit_price,
                unit_cost=line.unit_cost,
                scale_weight_kg=line.scale_weight_kg,
                quality_notes=line.quality_notes,
                kg_lead=kg_lead,
            )
        )

    return InboundOrderResponse(
        id=order.id,
        order_number=order.order_number,
        inbound_type=order.inbound_type,
        warehouse_id=order.warehouse_id,
        warehouse_name=order.warehouse.name if order.warehouse else None,
        third_party_id=order.third_party_id,
        third_party_name=order.third_party.name if order.third_party else None,
        date=order.date,
        driver_id=order.driver_id,
        driver_name=order.driver.name if order.driver else None,
        vehicle_id=order.vehicle_id,
        vehicle_plate=order.vehicle.plate if order.vehicle else None,
        willard_distribution_center=order.willard_distribution_center,
        goes_directly_to_jm=order.goes_directly_to_jm,
        status=order.status,
        purchase_id=order.purchase_id,
        purchase_number=order.purchase.purchase_number if order.purchase else None,
        purchase_status=order.purchase.status if order.purchase else None,
        total_kg_lead=total_kg,
        annulled_reason=order.annulled_reason,
        annulled_at=order.annulled_at,
        created_at=order.created_at,
        lines=lines,
        warnings=warnings or [],
    )


def _enrich_one(db: Session, order: InboundOrder, org_id: UUID, warnings=None) -> InboundOrderResponse:
    kg_map = inbound_order_service.kg_deltas_by_movement(db, org_id, [order.id])
    movs = inbound_order_service.receipt_movements(db, org_id, order.id)
    return _enrich(db, order, kg_map, movs, warnings)


@router.post("", response_model=InboundOrderResponse, status_code=status.HTTP_201_CREATED)
def create_inbound_order(
    order_in: InboundOrderCreate,
    org_context: dict = Depends(require_permission("purchases.create")),
    db: Session = Depends(get_db),
):
    """Captura unica en patio — efectos atomicos segun tipo (D2/D5/D7)."""
    order, warnings = inbound_order_service.create(
        db,
        obj_in=order_in,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    order = inbound_order_service.get(db, order.id, org_context["organization_id"])
    return _enrich_one(db, order, org_context["organization_id"], warnings)


@router.get("", response_model=InboundOrderListResponse)
def list_inbound_orders(
    inbound_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status", pattern="^(confirmed|annulled)$"),
    third_party_id: Optional[UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    org_context: dict = Depends(require_permission("purchases.view")),
    db: Session = Depends(get_db),
):
    org_id = org_context["organization_id"]
    orders, total = inbound_order_service.get_multi(
        db,
        organization_id=org_id,
        inbound_type=inbound_type,
        status_filter=status_filter,
        third_party_id=third_party_id,
        date_from=datetime.combine(date_from, dt_time.min, tzinfo=timezone.utc) if date_from else None,
        date_to=datetime.combine(date_to, dt_time.max, tzinfo=timezone.utc) if date_to else None,
        skip=skip,
        limit=limit,
    )
    kg_map = inbound_order_service.kg_deltas_by_movement(db, org_id, [o.id for o in orders])
    items = []
    for o in orders:
        movs = inbound_order_service.receipt_movements(db, org_id, o.id)
        items.append(_enrich(db, o, kg_map, movs))
    return InboundOrderListResponse(items=items, total=total)


@router.get("/{order_id}", response_model=InboundOrderResponse)
def get_inbound_order(
    order_id: UUID,
    org_context: dict = Depends(require_permission("purchases.view")),
    db: Session = Depends(get_db),
):
    order = inbound_order_service.get(db, order_id, org_context["organization_id"])
    return _enrich_one(db, order, org_context["organization_id"])


@router.patch("/{order_id}", response_model=InboundOrderResponse)
def update_inbound_order(
    order_id: UUID,
    order_in: InboundOrderUpdate,
    org_context: dict = Depends(require_permission("purchases.edit")),
    db: Session = Depends(get_db),
):
    """Edicion D18: Willard = revert-and-reapply; tipos compra = solo cabecera
    sin efectos (las lineas viven en la compra derivada)."""
    order, warnings = inbound_order_service.update(
        db,
        order_id=order_id,
        obj_in=order_in,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    order = inbound_order_service.get(db, order.id, org_context["organization_id"])
    return _enrich_one(db, order, org_context["organization_id"], warnings)


@router.post("/{order_id}/annul", response_model=InboundOrderResponse)
def annul_inbound_order(
    order_id: UUID,
    annul_in: InboundOrderAnnulRequest,
    org_context: dict = Depends(require_permission("purchases.cancel")),
    db: Session = Depends(get_db),
):
    """Anulacion D8: remocion ponderada + kg movements anulados + reversal
    backdateado; tipos compra cancelan la derivada registered en el mismo acto."""
    order, warnings = inbound_order_service.annul(
        db,
        order_id=order_id,
        reason=annul_in.reason,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    order = inbound_order_service.get(db, order.id, org_context["organization_id"])
    return _enrich_one(db, order, org_context["organization_id"], warnings)
