"""
Endpoints de Obligaciones Financieras (plan F).

La direccion de la obligacion decide el movement type concreto de cada accion —
el frontend no conoce los 8 tipos, solo las acciones. Anulacion de movimientos
SOLO por aca (Tesoreria directa responde 422, patron #67).
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.financial_obligation import FinancialObligation
from app.schemas.financial_obligation import (
    AccruePendingRequest,
    AccruePreviewResponse,
    AccrueResultResponse,
    FinancialObligationCreate,
    FinancialObligationResponse,
    ObligationAccrueRequest,
    ObligationAnnulRequest,
    ObligationMovementCreate,
    ObligationTransferCreate,
    ObligationSummaryResponse,
    PendingAccrualsResponse,
)
from app.schemas.money_movement import MoneyMovementResponse
from app.services.financial_obligation import financial_obligation as service

router = APIRouter()


def _to_response(obligation: FinancialObligation) -> FinancialObligationResponse:
    response = FinancialObligationResponse.model_validate(obligation)
    response.third_party_name = (
        obligation.third_party.name if obligation.third_party else ""
    )
    return response


# ======================================================================
# Lectura
# ======================================================================

@router.get("/", response_model=list[FinancialObligationResponse])
def list_obligations(
    direction: Optional[str] = Query(None, pattern="^(payable|receivable)$"),
    status: Optional[str] = Query(None, pattern="^(active|settled)$"),
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_permission("treasury.view_obligations")),
):
    obligations = service.get_list(
        db, ctx["organization_id"], direction=direction, status_filter=status
    )
    return [_to_response(o) for o in obligations]


@router.get("/summary", response_model=ObligationSummaryResponse)
def get_summary(
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_permission("treasury.view_obligations")),
):
    return service.get_summary(db, ctx["organization_id"])


@router.get("/pending-accruals", response_model=PendingAccrualsResponse)
def get_pending_accruals(
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_permission("treasury.view_obligations")),
):
    """Preview del batch: periodos vencidos sin causar, con monto calculado."""
    return service.get_pending_accruals(db, ctx["organization_id"])


@router.get("/{obligation_id}", response_model=FinancialObligationResponse)
def get_obligation(
    obligation_id: UUID,
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_permission("treasury.view_obligations")),
):
    return _to_response(service.get(db, obligation_id, ctx["organization_id"]))


@router.get("/{obligation_id}/statement", response_model=list[MoneyMovementResponse])
def get_obligation_statement(
    obligation_id: UUID,
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_permission("treasury.view_obligations")),
):
    movements = service.get_statement(db, obligation_id, ctx["organization_id"])
    return [MoneyMovementResponse.model_validate(m) for m in movements]


@router.get("/{obligation_id}/accrue-preview", response_model=AccruePreviewResponse)
def get_accrue_preview(
    obligation_id: UUID,
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_permission("treasury.view_obligations")),
):
    """Preview individual: vencidos sin causar + tramo de cierre (si capital $0)."""
    return service.get_accrue_preview(db, ctx["organization_id"], obligation_id)


# ======================================================================
# Escritura
# ======================================================================

@router.post("/", response_model=FinancialObligationResponse, status_code=201)
def create_obligation(
    data: FinancialObligationCreate,
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_permission("treasury.manage_obligations")),
):
    obligation = service.create(
        db, data, ctx["organization_id"], user_id=ctx["user_id"]
    )
    return _to_response(obligation)


@router.post("/accrue-pending", response_model=AccrueResultResponse)
def accrue_pending(
    data: AccruePendingRequest,
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_permission("treasury.manage_obligations")),
):
    """Batch de causacion (patron depreciacion #21). Idempotente, solo meses vencidos."""
    return service.accrue_pending(
        db, ctx["organization_id"], data, user_id=ctx["user_id"]
    )


@router.post("/{obligation_id}/accrue", response_model=AccrueResultResponse)
def accrue_obligation(
    obligation_id: UUID,
    data: ObligationAccrueRequest,
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_permission("treasury.manage_obligations")),
):
    """Causacion individual: vencidos de esta obligacion + tramo de cierre opcional."""
    return service.accrue_obligation(
        db, ctx["organization_id"], obligation_id, data, user_id=ctx["user_id"]
    )


@router.post("/{obligation_id}/capital-payment", response_model=MoneyMovementResponse)
def create_capital_payment(
    obligation_id: UUID,
    data: ObligationMovementCreate,
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_permission("treasury.manage_obligations")),
):
    movement = service.create_capital_payment(
        db, obligation_id, ctx["organization_id"], data, user_id=ctx["user_id"]
    )
    return MoneyMovementResponse.model_validate(movement)


@router.post("/{obligation_id}/interest-payment", response_model=MoneyMovementResponse)
def create_interest_payment(
    obligation_id: UUID,
    data: ObligationMovementCreate,
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_permission("treasury.manage_obligations")),
):
    movement = service.create_interest_payment(
        db, obligation_id, ctx["organization_id"], data, user_id=ctx["user_id"]
    )
    return MoneyMovementResponse.model_validate(movement)


@router.post("/{obligation_id}/interest-transfer", response_model=MoneyMovementResponse)
def create_interest_transfer(
    obligation_id: UUID,
    data: ObligationTransferCreate,
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_permission("treasury.manage_obligations")),
):
    """Traslada intereses pendientes a un tercero contraparte — sin caja."""
    movement = service.create_interest_transfer(
        db, obligation_id, ctx["organization_id"], data, user_id=ctx["user_id"]
    )
    return MoneyMovementResponse.model_validate(movement)


@router.post("/{obligation_id}/capital-transfer", response_model=MoneyMovementResponse)
def create_capital_transfer(
    obligation_id: UUID,
    data: ObligationTransferCreate,
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_permission("treasury.manage_obligations")),
):
    """Abono/recaudo de capital fondeado por un tercero contraparte — sin caja."""
    movement = service.create_capital_transfer(
        db, obligation_id, ctx["organization_id"], data, user_id=ctx["user_id"]
    )
    return MoneyMovementResponse.model_validate(movement)


@router.post("/{obligation_id}/disbursement", response_model=MoneyMovementResponse)
def create_additional_disbursement(
    obligation_id: UUID,
    data: ObligationMovementCreate,
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_permission("treasury.manage_obligations")),
):
    movement = service.create_additional_disbursement(
        db, obligation_id, ctx["organization_id"], data, user_id=ctx["user_id"]
    )
    return MoneyMovementResponse.model_validate(movement)


@router.post("/{obligation_id}/settle", response_model=FinancialObligationResponse)
def settle_obligation(
    obligation_id: UUID,
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_permission("treasury.manage_obligations")),
):
    return _to_response(service.settle(db, obligation_id, ctx["organization_id"]))


@router.post("/movements/{movement_id}/annul", response_model=MoneyMovementResponse)
def annul_obligation_movement(
    movement_id: UUID,
    data: ObligationAnnulRequest,
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_permission("treasury.manage_obligations")),
):
    """Anular un movimiento de obligacion con las reglas del plan F §5."""
    movement = service.annul_movement(
        db, movement_id, ctx["organization_id"], data.reason, user_id=ctx["user_id"]
    )
    return MoneyMovementResponse.model_validate(movement)
