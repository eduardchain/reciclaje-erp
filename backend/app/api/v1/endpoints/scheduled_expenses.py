"""
Endpoints para Gastos Diferidos Programados (ScheduledExpense).

POST   /                — Crear gasto diferido (pago upfront + prepago)
GET    /                — Listar gastos diferidos (filtro por status)
GET    /pending         — Gastos activos con cuotas pendientes
GET    /{id}            — Detalle con applications
POST   /{id}/apply      — Aplicar siguiente cuota
POST   /{id}/cancel     — Cancelar gasto diferido
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.schemas.scheduled_expense import (
    ScheduledExpenseCreate,
    ScheduledExpenseResponse,
    ScheduledExpenseApplicationResponse,
    PaginatedScheduledExpenseResponse,
)
from app.services.scheduled_expense import scheduled_expense

router = APIRouter()


def _build_response(se, include_applications: bool = False) -> ScheduledExpenseResponse:
    """Construir respuesta con campos calculados."""
    applied_total = se.monthly_amount * se.applied_months
    remaining = float(se.total_amount - applied_total)

    if se.status == "active" and se.applied_months < se.total_months:
        next_number = se.applied_months + 1
        if next_number == se.total_months:
            next_amount = float(se.total_amount - se.monthly_amount * (se.total_months - 1))
        else:
            next_amount = float(se.monthly_amount)
    else:
        next_amount = 0

    prepaid_balance = 0.0
    if se.prepaid_third_party:
        prepaid_balance = float(se.prepaid_third_party.current_balance)

    apps = []
    if include_applications and se.applications:
        apps = [ScheduledExpenseApplicationResponse.model_validate(a) for a in se.applications]

    return ScheduledExpenseResponse(
        id=se.id,
        organization_id=se.organization_id,
        name=se.name,
        description=se.description,
        total_amount=float(se.total_amount),
        monthly_amount=float(se.monthly_amount),
        total_months=se.total_months,
        applied_months=se.applied_months,
        source_account_id=se.source_account_id,
        source_account_name=se.source_account.name if se.source_account else None,
        prepaid_third_party_id=se.prepaid_third_party_id,
        prepaid_third_party_name=se.prepaid_third_party.name if se.prepaid_third_party else None,
        expense_category_id=se.expense_category_id,
        expense_category_name=se.expense_category.name if se.expense_category else None,
        funding_movement_id=se.funding_movement_id,
        start_date=se.start_date,
        apply_day=se.apply_day,
        next_application_date=se.next_application_date,
        status=se.status,
        created_by=se.created_by,
        cancelled_at=se.cancelled_at,
        cancelled_by=se.cancelled_by,
        is_active=se.is_active,
        created_at=se.created_at,
        updated_at=se.updated_at,
        remaining_amount=remaining,
        next_amount=next_amount,
        prepaid_balance=prepaid_balance,
        applications=apps,
    )


@router.post("/", response_model=ScheduledExpenseResponse, status_code=201)
def create_scheduled_expense(
    data: ScheduledExpenseCreate,
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_permission("treasury.manage_expenses")),
):
    """Crear gasto diferido programado con pago upfront."""
    se = scheduled_expense.create(
        db=db,
        data=data,
        organization_id=ctx["organization_id"],
        user_id=ctx["user_id"],
    )
    se = scheduled_expense.get(db, se.id, ctx["organization_id"])
    return _build_response(se)


@router.get("/", response_model=PaginatedScheduledExpenseResponse)
def list_scheduled_expenses(
    status_filter: str = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_permission("treasury.view")),
):
    """Listar gastos diferidos programados."""
    items, total = scheduled_expense.get_multi(
        db=db,
        organization_id=ctx["organization_id"],
        status_filter=status_filter,
        skip=skip,
        limit=limit,
    )
    return PaginatedScheduledExpenseResponse(
        items=[_build_response(se) for se in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/pending", response_model=list[ScheduledExpenseResponse])
def list_pending_scheduled_expenses(
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_permission("treasury.view")),
):
    """Gastos activos con cuotas pendientes, para TreasuryDashboard."""
    items = scheduled_expense.get_pending(
        db=db,
        organization_id=ctx["organization_id"],
    )
    return [_build_response(se) for se in items]


@router.get("/{scheduled_id}", response_model=ScheduledExpenseResponse)
def get_scheduled_expense(
    scheduled_id: UUID,
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_permission("treasury.view")),
):
    """Detalle de gasto diferido con applications."""
    se = scheduled_expense.get(db, scheduled_id, ctx["organization_id"])
    return _build_response(se, include_applications=True)


@router.post("/{scheduled_id}/apply", response_model=ScheduledExpenseApplicationResponse, status_code=201)
def apply_next_installment(
    scheduled_id: UUID,
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_permission("treasury.manage_expenses")),
):
    """Aplicar la siguiente cuota del gasto diferido."""
    application = scheduled_expense.apply_next(
        db=db,
        scheduled_id=scheduled_id,
        organization_id=ctx["organization_id"],
        user_id=ctx["user_id"],
    )
    return ScheduledExpenseApplicationResponse.model_validate(application)


@router.post("/{scheduled_id}/cancel", response_model=ScheduledExpenseResponse)
def cancel_scheduled_expense(
    scheduled_id: UUID,
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_permission("treasury.manage_expenses")),
):
    """Cancelar gasto diferido. Cuotas aplicadas permanecen."""
    se = scheduled_expense.cancel(
        db=db,
        scheduled_id=scheduled_id,
        organization_id=ctx["organization_id"],
        user_id=ctx["user_id"],
    )
    se = scheduled_expense.get(db, se.id, ctx["organization_id"])
    return _build_response(se)
