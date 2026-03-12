"""
Endpoints para Activos Fijos (FixedAsset).

POST   /                    — Crear activo fijo
GET    /                    — Listar activos fijos (filtro por status)
GET    /{id}                — Detalle con depreciaciones
PATCH  /{id}                — Actualizar activo
POST   /{id}/depreciate     — Aplicar UNA depreciacion
POST   /apply-pending       — Aplicar depreciaciones pendientes (batch)
POST   /{id}/dispose        — Dar de baja
"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_required_org_context
from app.schemas.fixed_asset import (
    FixedAssetCreate,
    FixedAssetUpdate,
    FixedAssetResponse,
    FixedAssetDisposeRequest,
    AssetDepreciationResponse,
    PaginatedFixedAssetResponse,
    ApplyPendingResult,
)
from app.services.fixed_asset import fixed_asset

router = APIRouter()


def _build_response(asset, include_depreciations: bool = False) -> FixedAssetResponse:
    """Construir respuesta con campos calculados."""
    # Progreso de depreciacion
    depreciable = float(asset.purchase_value - asset.salvage_value)
    if depreciable > 0:
        progress = float(asset.accumulated_depreciation) / depreciable * 100
    else:
        progress = 100.0

    # Meses restantes
    if asset.status == "active" and asset.monthly_depreciation > 0:
        remaining_value = float(asset.current_value - asset.salvage_value)
        remaining_months = max(0, int(remaining_value / float(asset.monthly_depreciation)))
    else:
        remaining_months = 0

    deps = []
    if include_depreciations and asset.depreciations:
        deps = [AssetDepreciationResponse.model_validate(d) for d in asset.depreciations]

    return FixedAssetResponse(
        id=asset.id,
        organization_id=asset.organization_id,
        name=asset.name,
        asset_code=asset.asset_code,
        notes=asset.notes,
        purchase_date=asset.purchase_date,
        depreciation_start_date=asset.depreciation_start_date,
        purchase_value=float(asset.purchase_value),
        salvage_value=float(asset.salvage_value),
        current_value=float(asset.current_value),
        accumulated_depreciation=float(asset.accumulated_depreciation),
        depreciation_rate=float(asset.depreciation_rate),
        monthly_depreciation=float(asset.monthly_depreciation),
        useful_life_months=asset.useful_life_months,
        expense_category_id=asset.expense_category_id,
        expense_category_name=asset.expense_category.name if asset.expense_category else None,
        third_party_id=asset.third_party_id,
        third_party_name=asset.third_party.name if asset.third_party else None,
        purchase_movement_id=asset.purchase_movement_id,
        status=asset.status,
        disposed_at=asset.disposed_at,
        disposed_by=asset.disposed_by,
        disposal_reason=asset.disposal_reason,
        created_by=asset.created_by,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
        remaining_months=remaining_months,
        depreciation_progress=round(progress, 2),
        depreciations=deps,
    )


@router.post("/", response_model=FixedAssetResponse, status_code=201)
def create_fixed_asset(
    data: FixedAssetCreate,
    db: Session = Depends(get_db),
    ctx: dict = Depends(get_required_org_context),
):
    """Crear un activo fijo."""
    asset = fixed_asset.create(
        db=db,
        data=data,
        organization_id=ctx["organization_id"],
        user_id=ctx["user_id"],
    )
    asset = fixed_asset.get(db, asset.id, ctx["organization_id"])
    return _build_response(asset)


@router.get("/", response_model=PaginatedFixedAssetResponse)
def list_fixed_assets(
    status_filter: str = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    ctx: dict = Depends(get_required_org_context),
):
    """Listar activos fijos con filtro opcional por status."""
    items, total = fixed_asset.get_multi(
        db=db,
        organization_id=ctx["organization_id"],
        status_filter=status_filter,
        skip=skip,
        limit=limit,
    )
    return PaginatedFixedAssetResponse(
        items=[_build_response(a) for a in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{asset_id}", response_model=FixedAssetResponse)
def get_fixed_asset(
    asset_id: UUID,
    db: Session = Depends(get_db),
    ctx: dict = Depends(get_required_org_context),
):
    """Detalle de activo fijo con depreciaciones."""
    asset = fixed_asset.get(db, asset_id, ctx["organization_id"])
    return _build_response(asset, include_depreciations=True)


@router.patch("/{asset_id}", response_model=FixedAssetResponse)
def update_fixed_asset(
    asset_id: UUID,
    data: FixedAssetUpdate,
    db: Session = Depends(get_db),
    ctx: dict = Depends(get_required_org_context),
):
    """Actualizar activo fijo (restricciones si ya tiene depreciaciones)."""
    asset = fixed_asset.update(
        db=db,
        asset_id=asset_id,
        organization_id=ctx["organization_id"],
        data=data,
    )
    asset = fixed_asset.get(db, asset.id, ctx["organization_id"])
    return _build_response(asset)


@router.post("/{asset_id}/depreciate", response_model=FixedAssetResponse, status_code=201)
def depreciate_asset(
    asset_id: UUID,
    db: Session = Depends(get_db),
    ctx: dict = Depends(get_required_org_context),
):
    """Aplicar una cuota de depreciacion al activo."""
    asset = fixed_asset.apply_depreciation(
        db=db,
        asset_id=asset_id,
        organization_id=ctx["organization_id"],
        user_id=ctx["user_id"],
    )
    asset = fixed_asset.get(db, asset.id, ctx["organization_id"])
    return _build_response(asset, include_depreciations=True)


@router.post("/apply-pending", response_model=List[ApplyPendingResult])
def apply_pending_depreciations(
    db: Session = Depends(get_db),
    ctx: dict = Depends(get_required_org_context),
):
    """Aplicar depreciaciones pendientes a todos los activos activos del mes."""
    results = fixed_asset.apply_pending(
        db=db,
        organization_id=ctx["organization_id"],
        user_id=ctx["user_id"],
    )
    return [ApplyPendingResult(**r) for r in results]


@router.post("/{asset_id}/dispose", response_model=FixedAssetResponse)
def dispose_asset(
    asset_id: UUID,
    data: FixedAssetDisposeRequest,
    db: Session = Depends(get_db),
    ctx: dict = Depends(get_required_org_context),
):
    """Dar de baja un activo fijo (con depreciacion acelerada si aplica)."""
    asset = fixed_asset.dispose(
        db=db,
        asset_id=asset_id,
        organization_id=ctx["organization_id"],
        user_id=ctx["user_id"],
        reason=data.reason,
    )
    asset = fixed_asset.get(db, asset.id, ctx["organization_id"])
    return _build_response(asset, include_depreciations=True)
