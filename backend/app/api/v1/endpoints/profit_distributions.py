"""Endpoints para repartición de utilidades a socios."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.schemas.profit_distribution import (
    AvailableProfitResponse,
    PartnerResponse,
    ProfitDistributionCreate,
    ProfitDistributionResponse,
)
from app.services.profit_distribution import profit_distribution_service

router = APIRouter()


@router.get("/available", response_model=AvailableProfitResponse)
def get_available_profit(
    org_context: dict = Depends(require_permission("treasury.manage_distributions")),
    db: Session = Depends(get_db),
):
    """Retorna utilidad acumulada, distribuida y disponible."""
    return profit_distribution_service.get_available(
        db, org_context["organization_id"]
    )


@router.get("/partners", response_model=list[PartnerResponse])
def get_partners(
    org_context: dict = Depends(require_permission("treasury.manage_distributions")),
    db: Session = Depends(get_db),
):
    """Lista de socios (investor_type='socio') con saldo actual."""
    return profit_distribution_service.get_partners(
        db, org_context["organization_id"]
    )


@router.post("/", response_model=ProfitDistributionResponse, status_code=201)
def create_distribution(
    data: ProfitDistributionCreate,
    org_context: dict = Depends(require_permission("treasury.manage_distributions")),
    db: Session = Depends(get_db),
):
    """Crear repartición de utilidades."""
    return profit_distribution_service.create_distribution(
        db=db,
        data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context.get("user_id"),
    )


@router.get("/")
def list_distributions(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    org_context: dict = Depends(require_permission("treasury.manage_distributions")),
    db: Session = Depends(get_db),
):
    """Historial de reparticiones de utilidades."""
    return profit_distribution_service.list_distributions(
        db=db,
        organization_id=org_context["organization_id"],
        skip=skip,
        limit=limit,
    )
