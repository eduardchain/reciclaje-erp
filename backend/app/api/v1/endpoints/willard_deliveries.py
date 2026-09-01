"""Endpoints WillardDelivery — Salidas de plomo a Willard (W1).

Router completo gated por `kg_ledger_enabled` (D7): 403 incluso para admins.
Permisos: reusa los de ventas (la Salida ES la captura de la entrega), mas
`sales.review` propio para el paso que certifica pesos.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, require_org_flag, require_permission
from app.models.material import Material
from app.models.sale import Sale
from app.models.user import User
from app.models.willard_delivery import WillardDelivery
from app.schemas.willard_delivery import (
    WillardDeliveryAnnul,
    WillardDeliveryCreate,
    WillardDeliveryLineResponse,
    WillardDeliveryListResponse,
    WillardDeliveryLiquidate,
    WillardDeliveryResponse,
    WillardDeliveryUpdate,
)
from app.services.willard_delivery import willard_delivery

router = APIRouter(dependencies=[Depends(require_org_flag("kg_ledger_enabled"))])


def _user_names(db: Session, delivery: WillardDelivery) -> dict:
    ids = {
        delivery.created_by,
        delivery.reviewed_by,
        delivery.liquidated_by,
        delivery.annulled_by,
    } - {None}
    if not ids:
        return {}
    rows = db.execute(
        select(User.id, User.full_name).where(User.id.in_(ids))
    ).all()
    return {r[0]: r[1] for r in rows}


def _enrich(db: Session, delivery: WillardDelivery) -> WillardDeliveryResponse:
    names = _user_names(db, delivery)
    materials = {}
    if delivery.lines:
        rows = db.execute(
            select(Material).where(
                Material.id.in_([ln.material_id for ln in delivery.lines])
            )
        ).scalars().all()
        materials = {m.id: m for m in rows}

    lines = []
    total_kg = Decimal("0")
    for ln in delivery.lines:
        material = materials.get(ln.material_id)
        lines.append(
            WillardDeliveryLineResponse(
                id=ln.id,
                material_id=ln.material_id,
                material_code=material.code if material else None,
                material_name=material.name if material else None,
                material_unit=(material.default_unit if material else None) or "kg",
                quantity=ln.quantity,
                unit=ln.unit,
                scale_weight_kg=ln.scale_weight_kg,
                kg_lead_equivalent=ln.kg_lead_equivalent,
                unit_cost=ln.unit_cost,
                unit_price=ln.unit_price,
                total_price=ln.total_price,
            )
        )
        total_kg += ln.kg_lead_equivalent or Decimal("0")

    sale_number = None
    if delivery.sale_id:
        sale_number = db.execute(
            select(Sale.sale_number).where(Sale.id == delivery.sale_id)
        ).scalar_one_or_none()

    return WillardDeliveryResponse(
        id=delivery.id,
        delivery_number=delivery.delivery_number,
        delivery_type=delivery.delivery_type,
        warehouse_id=delivery.warehouse_id,
        warehouse_name=delivery.warehouse.name if delivery.warehouse else None,
        third_party_id=delivery.third_party_id,
        third_party_name=delivery.third_party.name if delivery.third_party else None,
        date=delivery.date,
        driver_id=delivery.driver_id,
        driver_name=delivery.driver.name if delivery.driver else None,
        vehicle_id=delivery.vehicle_id,
        vehicle_plate=delivery.vehicle.plate if delivery.vehicle else None,
        invoice_number=delivery.invoice_number,
        remission_number=delivery.remission_number,
        notes=delivery.notes,
        status=delivery.status,
        reviewed_at=delivery.reviewed_at,
        reviewed_by_name=names.get(delivery.reviewed_by),
        liquidated_at=delivery.liquidated_at,
        liquidated_ts=delivery.liquidated_ts,
        liquidated_by_name=names.get(delivery.liquidated_by),
        annulled_reason=delivery.annulled_reason,
        annulled_at=delivery.annulled_at,
        annulled_by_name=names.get(delivery.annulled_by),
        created_by_name=names.get(delivery.created_by),
        sale_id=delivery.sale_id,
        sale_number=sale_number,
        maquila_amount=delivery.maquila_amount,
        freight_amount=delivery.freight_amount,
        plant_credit_amount=delivery.plant_credit_amount,
        total_kg_lead=total_kg,
        lines=lines,
    )


@router.get("", response_model=WillardDeliveryListResponse)
def list_deliveries(
    db: Session = Depends(get_db),
    context=Depends(require_permission("sales.view")),
    status_filter: Optional[str] = Query(None, alias="status"),
    delivery_type: Optional[str] = Query(None),
    warehouse_id: Optional[UUID] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    org_id = context["organization_id"]
    filters = [WillardDelivery.organization_id == org_id]
    if status_filter:
        filters.append(WillardDelivery.status == status_filter)
    if delivery_type:
        filters.append(WillardDelivery.delivery_type == delivery_type)
    if warehouse_id:
        filters.append(WillardDelivery.warehouse_id == warehouse_id)
    if date_from:
        filters.append(WillardDelivery.date >= date_from)
    if date_to:
        filters.append(WillardDelivery.date <= date_to)

    total = db.execute(
        select(func.count()).select_from(WillardDelivery).where(*filters)
    ).scalar_one()

    rows = db.execute(
        select(WillardDelivery)
        .where(*filters)
        .options(selectinload(WillardDelivery.lines))
        .order_by(WillardDelivery.delivery_number.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()

    return WillardDeliveryListResponse(
        items=[_enrich(db, d) for d in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{delivery_id}", response_model=WillardDeliveryResponse)
def get_delivery(
    delivery_id: UUID,
    db: Session = Depends(get_db),
    context=Depends(require_permission("sales.view")),
):
    delivery = willard_delivery._get_or_404(db, delivery_id, context["organization_id"])
    return _enrich(db, delivery)


@router.post("", response_model=WillardDeliveryResponse, status_code=status.HTTP_201_CREATED)
def create_delivery(
    data: WillardDeliveryCreate,
    db: Session = Depends(get_db),
    context=Depends(require_permission("sales.create")),
):
    delivery = willard_delivery.create(
        db, data, context["organization_id"], user_id=context["user"].id
    )
    return _enrich(db, delivery)


@router.patch("/{delivery_id}", response_model=WillardDeliveryResponse)
def update_delivery(
    delivery_id: UUID,
    data: WillardDeliveryUpdate,
    db: Session = Depends(get_db),
    context=Depends(require_permission("sales.edit")),
):
    delivery = willard_delivery.update(
        db, delivery_id, data, context["organization_id"], user_id=context["user"].id
    )
    return _enrich(db, delivery)


@router.post("/{delivery_id}/review", response_model=WillardDeliveryResponse)
def review_delivery(
    delivery_id: UUID,
    db: Session = Depends(get_db),
    context=Depends(require_permission("sales.review")),
):
    delivery = willard_delivery.review(
        db, delivery_id, context["organization_id"], user_id=context["user"].id
    )
    return _enrich(db, delivery)


@router.post("/{delivery_id}/liquidate", response_model=WillardDeliveryResponse)
def liquidate_delivery(
    delivery_id: UUID,
    data: WillardDeliveryLiquidate,
    db: Session = Depends(get_db),
    context=Depends(require_permission("sales.liquidate")),
):
    delivery, warnings = willard_delivery.liquidate(
        db, delivery_id, data, context["organization_id"], user_id=context["user"].id
    )
    response = _enrich(db, delivery)
    if warnings:
        response.notes = (response.notes or "")
    return response


@router.post("/{delivery_id}/annul", response_model=WillardDeliveryResponse)
def annul_delivery(
    delivery_id: UUID,
    data: WillardDeliveryAnnul,
    db: Session = Depends(get_db),
    context=Depends(require_permission("sales.cancel")),
):
    delivery = willard_delivery.annul(
        db, delivery_id, data.reason, context["organization_id"], user_id=context["user"].id
    )
    return _enrich(db, delivery)
