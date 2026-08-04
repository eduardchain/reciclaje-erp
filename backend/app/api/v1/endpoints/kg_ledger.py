"""Endpoints KgLedger — cuentas en kg de plomo (SAC E2, plan §4.1).

Todo el router gated por flag kg_ledger_enabled (D10): 403 incluso para
admins si la org no tiene el modulo. Permisos (D13): kg_ledger.view
(master), kg_ledger.manage (cuentas), kg_ledger.manage_adjustments
(movimientos manuales + su anulacion).

Fechas: query params tipo date (patron statement de tesoreria) —
date_from → medianoche UTC, date_to/as_of → fin de dia inclusivo (los
movimientos viven normalizados a mediodia UTC via BusinessDate).
"""
from datetime import date, datetime, time as dt_time, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_org_flag, require_permission
from app.schemas.kg_ledger import (
    KgLedgerAccountCreate,
    KgLedgerAccountResponse,
    KgLedgerAccountUpdate,
    KgLedgerAnnulRequest,
    KgLedgerMovementManualCreate,
    KgLedgerMovementResponse,
    KgLedgerStatementResponse,
    KgLedgerSummaryResponse,
)
from app.services.kg_ledger import kg_ledger_service

router = APIRouter(dependencies=[Depends(require_org_flag("kg_ledger_enabled"))])


def _day_start(d: Optional[date]) -> Optional[datetime]:
    return datetime.combine(d, dt_time.min, tzinfo=timezone.utc) if d else None


def _day_end(d: Optional[date]) -> Optional[datetime]:
    return datetime.combine(d, dt_time.max, tzinfo=timezone.utc) if d else None


# ---------------------------------------------------------------------- #
# Cuentas                                                                 #
# ---------------------------------------------------------------------- #
@router.get("/accounts", response_model=list[KgLedgerAccountResponse])
def list_kg_accounts(
    account_type: Optional[str] = Query(None, description="Filtrar por tipo de cuenta"),
    include_inactive: bool = Query(False),
    org_context: dict = Depends(require_permission("kg_ledger.view")),
    db: Session = Depends(get_db),
):
    """Cuentas kg con saldo vivo (SUM confirmed, una query agregada)."""
    return kg_ledger_service.list_accounts(
        db,
        organization_id=org_context["organization_id"],
        account_type=account_type,
        is_active=None if include_inactive else True,
    )


@router.post("/accounts", response_model=KgLedgerAccountResponse, status_code=status.HTTP_201_CREATED)
def create_kg_account(
    account_in: KgLedgerAccountCreate,
    org_context: dict = Depends(require_permission("kg_ledger.manage")),
    db: Session = Depends(get_db),
):
    """Crear cuenta kg (coherencia tipo↔FKs validada en servicio, D6)."""
    return kg_ledger_service.create_account(
        db, organization_id=org_context["organization_id"], data=account_in
    )


@router.patch("/accounts/{account_id}", response_model=KgLedgerAccountResponse)
def update_kg_account(
    account_id: UUID,
    account_in: KgLedgerAccountUpdate,
    org_context: dict = Depends(require_permission("kg_ledger.manage")),
    db: Session = Depends(get_db),
):
    """Solo metadata (display_name/tolerance/is_active) — tipo y FKs inmutables."""
    return kg_ledger_service.update_account(
        db,
        organization_id=org_context["organization_id"],
        account_id=account_id,
        data=account_in,
    )


@router.get("/accounts/{account_id}/movements", response_model=KgLedgerStatementResponse)
def get_kg_account_statement(
    account_id: UUID,
    date_from: Optional[date] = Query(None, description="Fecha desde (default: 90 dias)"),
    date_to: Optional[date] = Query(None, description="Fecha hasta (inclusiva)"),
    status_filter: str = Query("confirmed", pattern="^(confirmed|annulled|all)$"),
    org_context: dict = Depends(require_permission("kg_ledger.view")),
    db: Session = Depends(get_db),
):
    """Estado de cuenta en kg con saldo de apertura real de la ventana (#55)."""
    return kg_ledger_service.statement(
        db,
        organization_id=org_context["organization_id"],
        account_id=account_id,
        date_from=_day_start(date_from),
        date_to=_day_end(date_to),
        status_filter=status_filter,
    )


# ---------------------------------------------------------------------- #
# Summary                                                                 #
# ---------------------------------------------------------------------- #
@router.get("/summary", response_model=KgLedgerSummaryResponse)
def get_kg_summary(
    as_of: Optional[date] = Query(None, description="Corte historico (inclusivo)"),
    org_context: dict = Depends(require_permission("kg_ledger.view")),
    db: Session = Depends(get_db),
):
    """Panel de saldos por cuenta + totales por tipo (Willard agrupado)."""
    return kg_ledger_service.summary(
        db, organization_id=org_context["organization_id"], as_of=_day_end(as_of)
    )


# ---------------------------------------------------------------------- #
# Movimientos manuales (D1/D15/D16)                                       #
# ---------------------------------------------------------------------- #
@router.post("/movements", response_model=KgLedgerMovementResponse, status_code=status.HTTP_201_CREATED)
def create_kg_manual_movement(
    movement_in: KgLedgerMovementManualCreate,
    org_context: dict = Depends(require_permission("kg_ledger.manage_adjustments")),
    db: Session = Depends(get_db),
):
    """Ajuste manual auditado (motivo obligatorio, fecha no futura D15)."""
    return kg_ledger_service.create_manual_movement(
        db,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
        data=movement_in,
    )


@router.post("/movements/{movement_id}/annul", response_model=KgLedgerMovementResponse)
def annul_kg_movement(
    movement_id: UUID,
    annul_in: KgLedgerAnnulRequest,
    org_context: dict = Depends(require_permission("kg_ledger.manage_adjustments")),
    db: Session = Depends(get_db),
):
    """Anular ajuste manual (D16: los de negocio se anulan desde su documento)."""
    return kg_ledger_service.annul_movement(
        db,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
        movement_id=movement_id,
        reason=annul_in.reason,
    )
