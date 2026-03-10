"""
Endpoints para Gastos Diferidos (DeferredExpense).

POST   /                — Crear gasto diferido
GET    /                — Listar gastos diferidos (filtro por status)
GET    /pending         — Gastos activos con cuotas pendientes
GET    /{id}            — Detalle con applications
POST   /{id}/apply      — Aplicar siguiente cuota
POST   /{id}/cancel     — Cancelar gasto diferido
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_required_org_context
from app.schemas.deferred_expense import (
    DeferredExpenseCreate,
    DeferredExpenseResponse,
    DeferredApplicationResponse,
    PaginatedDeferredExpenseResponse,
)
from app.services.deferred_expense import deferred_expense

router = APIRouter()


def _build_response(de, include_applications: bool = False) -> DeferredExpenseResponse:
    """Construir respuesta con campos calculados y nombres de relaciones."""
    applied_total = de.monthly_amount * de.applied_months
    remaining = float(de.total_amount - applied_total)

    # Calcular monto de la siguiente cuota
    if de.status == "active" and de.applied_months < de.total_months:
        next_number = de.applied_months + 1
        if next_number == de.total_months:
            next_amount = float(de.total_amount - de.monthly_amount * (de.total_months - 1))
        else:
            next_amount = float(de.monthly_amount)
    else:
        next_amount = 0

    apps = []
    if include_applications and de.applications:
        apps = [DeferredApplicationResponse.model_validate(a) for a in de.applications]

    return DeferredExpenseResponse(
        id=de.id,
        organization_id=de.organization_id,
        name=de.name,
        total_amount=float(de.total_amount),
        monthly_amount=float(de.monthly_amount),
        total_months=de.total_months,
        applied_months=de.applied_months,
        expense_category_id=de.expense_category_id,
        expense_category_name=de.expense_category.name if de.expense_category else None,
        expense_type=de.expense_type,
        account_id=de.account_id,
        account_name=de.account.name if de.account else None,
        provision_id=de.provision_id,
        provision_name=de.provision.name if de.provision else None,
        description=de.description,
        start_date=de.start_date,
        status=de.status,
        cancelled_at=de.cancelled_at,
        cancelled_by=de.cancelled_by,
        created_by=de.created_by,
        is_active=de.is_active,
        created_at=de.created_at,
        updated_at=de.updated_at,
        remaining_amount=remaining,
        next_amount=next_amount,
        applications=apps,
    )


@router.post("/", response_model=DeferredExpenseResponse, status_code=201)
def create_deferred_expense(
    data: DeferredExpenseCreate,
    db: Session = Depends(get_db),
    ctx: dict = Depends(get_required_org_context),
):
    """Crear un nuevo gasto diferido."""
    de = deferred_expense.create(
        db=db,
        data=data,
        organization_id=ctx["organization_id"],
        user_id=ctx["user_id"],
    )
    # Cargar relaciones para respuesta
    de = deferred_expense.get(db, de.id, ctx["organization_id"])
    return _build_response(de)


@router.get("/", response_model=PaginatedDeferredExpenseResponse)
def list_deferred_expenses(
    status_filter: str = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    ctx: dict = Depends(get_required_org_context),
):
    """Listar gastos diferidos con filtro opcional por status."""
    items, total = deferred_expense.get_multi(
        db=db,
        organization_id=ctx["organization_id"],
        status_filter=status_filter,
        skip=skip,
        limit=limit,
    )
    return PaginatedDeferredExpenseResponse(
        items=[_build_response(de) for de in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/pending", response_model=list[DeferredExpenseResponse])
def list_pending_deferred_expenses(
    db: Session = Depends(get_db),
    ctx: dict = Depends(get_required_org_context),
):
    """Gastos activos con cuotas pendientes, para TreasuryDashboard."""
    items = deferred_expense.get_pending(
        db=db,
        organization_id=ctx["organization_id"],
    )
    return [_build_response(de) for de in items]


@router.get("/{deferred_id}", response_model=DeferredExpenseResponse)
def get_deferred_expense(
    deferred_id: UUID,
    db: Session = Depends(get_db),
    ctx: dict = Depends(get_required_org_context),
):
    """Obtener detalle de gasto diferido con applications."""
    de = deferred_expense.get(db, deferred_id, ctx["organization_id"])
    return _build_response(de, include_applications=True)


@router.post("/{deferred_id}/apply", response_model=DeferredApplicationResponse, status_code=201)
def apply_next_installment(
    deferred_id: UUID,
    db: Session = Depends(get_db),
    ctx: dict = Depends(get_required_org_context),
):
    """Aplicar la siguiente cuota del gasto diferido."""
    application = deferred_expense.apply_next(
        db=db,
        deferred_id=deferred_id,
        organization_id=ctx["organization_id"],
        user_id=ctx["user_id"],
    )
    return DeferredApplicationResponse.model_validate(application)


@router.post("/{deferred_id}/cancel", response_model=DeferredExpenseResponse)
def cancel_deferred_expense(
    deferred_id: UUID,
    db: Session = Depends(get_db),
    ctx: dict = Depends(get_required_org_context),
):
    """Cancelar gasto diferido. Las cuotas ya aplicadas permanecen."""
    de = deferred_expense.cancel(
        db=db,
        deferred_id=deferred_id,
        organization_id=ctx["organization_id"],
        user_id=ctx["user_id"],
    )
    return _build_response(de)
