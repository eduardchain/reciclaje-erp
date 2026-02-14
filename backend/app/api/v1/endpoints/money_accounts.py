"""
Endpoints API para operaciones CRUD de MoneyAccount (Cuentas de Dinero).

Tipos de cuenta: cash (efectivo), bank (banco), digital (Nequi, etc.)
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_required_org_context, get_db
from app.schemas.money_account import (
    MoneyAccountCreate,
    MoneyAccountUpdate,
    MoneyAccountResponse,
)
from app.services.base import PaginatedResponse
from app.services.money_account import money_account

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
def list_money_accounts(
    skip: int = Query(0, ge=0, description="Registros a saltar"),
    limit: int = Query(100, ge=1, le=500, description="Maximo de registros"),
    is_active: Optional[bool] = Query(None, description="Filtrar por estado activo"),
    search: Optional[str] = Query(None, description="Buscar por nombre, banco o numero de cuenta"),
    sort_by: str = Query("name", description="Campo para ordenar"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Direccion de orden"),
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Listar cuentas de dinero con paginacion y filtros."""
    return money_account.get_multi(
        db=db,
        organization_id=org_context["organization_id"],
        skip=skip,
        limit=limit,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.post("", response_model=MoneyAccountResponse, status_code=status.HTTP_201_CREATED)
def create_money_account(
    account_in: MoneyAccountCreate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Crear nueva cuenta de dinero.

    Tipos validos: cash, bank, digital.
    El saldo inicial (initial_balance) se asigna como current_balance.
    """
    return money_account.create(
        db=db,
        obj_in=account_in,
        organization_id=org_context["organization_id"],
    )


@router.get("/{account_id}", response_model=MoneyAccountResponse)
def get_money_account(
    account_id: UUID,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Obtener una cuenta de dinero por ID."""
    return money_account.get_or_404(
        db=db,
        id=account_id,
        organization_id=org_context["organization_id"],
        detail="Cuenta de dinero no encontrada",
    )


@router.patch("/{account_id}", response_model=MoneyAccountResponse)
def update_money_account(
    account_id: UUID,
    account_in: MoneyAccountUpdate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Actualizar una cuenta de dinero (campos parciales)."""
    return money_account.update(
        db=db,
        id=account_id,
        obj_in=account_in,
        organization_id=org_context["organization_id"],
    )


@router.delete("/{account_id}", response_model=MoneyAccountResponse)
def delete_money_account(
    account_id: UUID,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Soft delete de cuenta de dinero (is_active = False).

    No se puede eliminar una cuenta con saldo != 0.
    """
    return money_account.delete(
        db=db,
        id=account_id,
        organization_id=org_context["organization_id"],
    )
