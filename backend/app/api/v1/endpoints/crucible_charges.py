"""Endpoints de los documentos de crisol (#107 D2) — tab "Crisol" de Salidas de Plomo.

Router gated por `kg_ledger_enabled` (403 incluso para admins); permisos reusan
los de Salidas de Plomo (sales.view / sales.create / sales.cancel). Los warnings
del servicio viajan en la RESPUESTA desde el primer dia (leccion #100 D4d).
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_org_flag, require_permission
from app.models.plant_process import CrucibleCharge
from app.models.user import User
from app.schemas.crucible_charge import (
    CrucibleChargeAnnul,
    CrucibleChargeCreate,
    CrucibleChargeListResponse,
    CrucibleChargeResponse,
)
from app.services.crucible_charge import crucible_charge_service

router = APIRouter(dependencies=[Depends(require_org_flag("kg_ledger_enabled"))])


def _user_names(db: Session, charges: list[CrucibleCharge]) -> dict:
    ids = {c.created_by for c in charges} | {c.annulled_by for c in charges}
    ids -= {None}
    if not ids:
        return {}
    rows = db.execute(select(User.id, User.full_name).where(User.id.in_(ids))).all()
    return {r[0]: r[1] for r in rows}


def _enrich(charge: CrucibleCharge, names: dict) -> CrucibleChargeResponse:
    # Campo por campo a proposito (trampa #95): un campo nuevo en el modelo y
    # el schema que no se agregue aqui llega en None sin que nada falle.
    return CrucibleChargeResponse(
        id=charge.id,
        charge_number=charge.charge_number,
        label=charge.label,
        event_type=charge.event_type,
        warehouse_id=charge.warehouse_id,
        warehouse_name=charge.warehouse.name if charge.warehouse else None,
        material_id=charge.material_id,
        material_code=charge.material.code if charge.material else None,
        material_name=charge.material.name if charge.material else None,
        quantity_kg=charge.quantity_kg,
        date=charge.date,
        notes=charge.notes,
        status=charge.status,
        maquila_amount=charge.maquila_amount,
        annulled_reason=charge.annulled_reason,
        annulled_at=charge.annulled_at,
        annulled_by_name=names.get(charge.annulled_by),
        created_by_name=names.get(charge.created_by),
        created_at=charge.created_at,
    )


@router.get("", response_model=CrucibleChargeListResponse)
def list_crucible_charges(
    db: Session = Depends(get_db),
    context=Depends(require_permission("sales.view")),
    event_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    rows, total = crucible_charge_service.list_charges(
        db,
        context["organization_id"],
        event_type=event_type,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
    )
    names = _user_names(db, rows)
    return CrucibleChargeListResponse(
        items=[_enrich(c, names) for c in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{charge_id}", response_model=CrucibleChargeResponse)
def get_crucible_charge(
    charge_id: UUID,
    db: Session = Depends(get_db),
    context=Depends(require_permission("sales.view")),
):
    charge = crucible_charge_service._get_or_404(db, charge_id, context["organization_id"])
    return _enrich(charge, _user_names(db, [charge]))


@router.post("", response_model=CrucibleChargeResponse, status_code=status.HTTP_201_CREATED)
def create_crucible_charge(
    data: CrucibleChargeCreate,
    db: Session = Depends(get_db),
    context=Depends(require_permission("sales.create")),
):
    charge, warnings = crucible_charge_service.create(
        db, data, context["organization_id"], user_id=context["user"].id
    )
    charge = crucible_charge_service._get_or_404(db, charge.id, context["organization_id"])
    response = _enrich(charge, _user_names(db, [charge]))
    response.warnings = warnings or []
    return response


@router.post("/{charge_id}/annul", response_model=CrucibleChargeResponse)
def annul_crucible_charge(
    charge_id: UUID,
    data: CrucibleChargeAnnul,
    db: Session = Depends(get_db),
    context=Depends(require_permission("sales.cancel")),
):
    charge = crucible_charge_service.annul(
        db, charge_id, data.reason, context["organization_id"], user_id=context["user"].id
    )
    return _enrich(charge, _user_names(db, [charge]))
