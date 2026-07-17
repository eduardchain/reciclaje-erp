"""Endpoints de ServiceTariff (SAC E1, v0.5 §12.1.3).

Append-only: GET (historico) / GET current / POST. Sin PATCH ni DELETE —
la ruta no existe (404 en /{id}, 405 sobre la coleccion), invariante 1 del
plan E1. `/current` es ruta literal declarada antes de cualquier /{id} futura.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_org_flag, get_db, require_permission
from app.schemas.service_tariff import (
    ServiceTariffCreate,
    ServiceTariffListResponse,
    ServiceTariffResponse,
)
from app.services.service_tariff import service_tariff

router = APIRouter(dependencies=[Depends(require_org_flag("kg_ledger_enabled"))])  # H2 QA E2: re-gate por flag


@router.get("", response_model=ServiceTariffListResponse)
def list_service_tariffs(
    tariff_code: Optional[str] = Query(None, description="Filtrar historico por codigo"),
    org_context: dict = Depends(require_permission("tariffs.view")),
    db: Session = Depends(get_db),
):
    """Historico completo de tarifas (mas reciente primero)."""
    items = service_tariff.get_all(
        db=db,
        organization_id=org_context["organization_id"],
        tariff_code=tariff_code,
    )
    return ServiceTariffListResponse(items=items, total=len(items))


@router.get("/current", response_model=ServiceTariffListResponse)
def get_current_tariffs(
    org_context: dict = Depends(require_permission("tariffs.view")),
    db: Session = Depends(get_db),
):
    """Tarifa vigente por codigo (max created_at, tiebreaker id)."""
    items = service_tariff.get_current(
        db=db, organization_id=org_context["organization_id"]
    )
    return ServiceTariffListResponse(items=items, total=len(items))


@router.post("", response_model=ServiceTariffResponse, status_code=status.HTTP_201_CREATED)
def create_service_tariff(
    tariff_in: ServiceTariffCreate,
    org_context: dict = Depends(require_permission("tariffs.manage")),
    db: Session = Depends(get_db),
):
    """Crear nueva version de tarifa (append-only — corregir = nueva version)."""
    return service_tariff.create(
        db=db,
        obj_in=tariff_in,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
