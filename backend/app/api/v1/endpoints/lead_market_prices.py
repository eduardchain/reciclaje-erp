"""Endpoints de LeadMarketPrice (CC-014, Q-B; anulacion en el ciclo corto que sigue).

Append-only: GET historico / GET current / POST / POST /{id}/annul. **Sigue sin
PATCH ni DELETE** — la coleccion da 405 y /{id} da 404, igual que tarifas: anular
no es editar, es un evento mas sobre una fila que no se toca. Por eso el verbo es
POST /{id}/annul, que es el patron del repo (crucible_charges, fixed_assets,
inbound_orders, financial_obligations, inventory_adjustments).
`/current` es ruta literal declarada antes de cualquier /{id}.

Permisos reutilizados `tariffs.view` / `tariffs.manage`: ya existen, estan
gateados por el mismo flag y los administra la misma gente. ⚠️ Ningun rol
custom del seeder los tiene, asi que hoy esta pantalla es solo para
administradores por bypass (Johana lo es). El dia que quieran delegarla hay
que asignar el permiso a un rol, no cambiar esto.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_org_flag, require_permission
from uuid import UUID

from app.schemas.lead_market_price import (
    LeadMarketPriceAnnul,
    LeadMarketPriceCreate,
    LeadMarketPriceListResponse,
    LeadMarketPriceResponse,
)
from app.services.lead_market_price import lead_market_price

router = APIRouter(dependencies=[Depends(require_org_flag("kg_ledger_enabled"))])


@router.get("", response_model=LeadMarketPriceListResponse)
def list_lead_market_prices(
    org_context: dict = Depends(require_permission("tariffs.view")),
    db: Session = Depends(get_db),
):
    """Historico completo de precios (el vigente primero)."""
    items = lead_market_price.get_all(
        db=db, organization_id=org_context["organization_id"]
    )
    return LeadMarketPriceListResponse(items=items, total=len(items))


@router.get("/current", response_model=LeadMarketPriceResponse | None)
def get_current_lead_market_price(
    org_context: dict = Depends(require_permission("tariffs.view")),
    db: Session = Depends(get_db),
):
    """El precio vigente, o null si no hay ninguno cargado."""
    return lead_market_price.get_current_response(
        db=db, organization_id=org_context["organization_id"]
    )


@router.post("", response_model=LeadMarketPriceResponse, status_code=status.HTTP_201_CREATED)
def create_lead_market_price(
    price_in: LeadMarketPriceCreate,
    org_context: dict = Depends(require_permission("tariffs.manage")),
    db: Session = Depends(get_db),
):
    """Cargar un precio nuevo (append-only — corregir = cargar otra version)."""
    return lead_market_price.create(
        db=db,
        obj_in=price_in,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )


@router.post("/{price_id}/annul", response_model=LeadMarketPriceResponse)
def annul_lead_market_price(
    price_id: UUID,
    payload: LeadMarketPriceAnnul,
    org_context: dict = Depends(require_permission("tariffs.manage")),
    db: Session = Depends(get_db),
):
    """Anular un precio cargado por error: deja de regir y queda en el historico.

    Mismo permiso que cargarlo — quien puede poner un precio puede retirarlo.
    ⚠️ Anular reescribe cortes ya impresos, igual que cargar con fecha vieja.
    """
    return lead_market_price.annul(
        db=db,
        price_id=price_id,
        reason=payload.reason,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
