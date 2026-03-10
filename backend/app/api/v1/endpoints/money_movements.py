"""
Endpoints API para operaciones de Tesoreria (MoneyMovement).

Modulo independiente de la liquidacion de compras/ventas.
Endpoints especializados por tipo de operacion con un endpoint
generico de listado y filtros.
"""
from datetime import date, datetime, time as dt_time, timedelta, timezone as tz
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_required_org_context, get_db
from app.schemas.money_movement import (
    SupplierPaymentCreate,
    CustomerCollectionCreate,
    ExpenseCreate,
    ServiceIncomeCreate,
    TransferCreate,
    CapitalInjectionCreate,
    CapitalReturnCreate,
    CommissionPaymentCreate,
    ProvisionDepositCreate,
    ProvisionExpenseCreate,
    AnnulMovementRequest,
    AnnulMovementResponse,
    MoneyMovementResponse,
    MoneyMovementSummary,
)
from app.models.money_movement import MoneyMovement
from app.services.money_movement import money_movement

router = APIRouter()

# Direccion del efecto en el balance del tercero por tipo de movimiento.
# Positivo = tercero nos debe mas (o le debemos menos).
# Negativo = tercero nos debe menos (o le debemos mas).
THIRD_PARTY_BALANCE_DIRECTION = {
    "payment_to_supplier": 1,       # Pagamos: su deuda baja (nuestro balance sube)
    "collection_from_client": -1,   # Cobramos: nos deben menos
    "capital_injection": -1,        # Inversor aporta: le debemos mas (balance baja)
    "capital_return": 1,            # Devolvemos: le debemos menos (balance sube)
    "commission_payment": 1,        # Pagamos comision: deuda de comision baja
    "provision_deposit": -1,        # Depositamos a provision: fondos aumentan (balance baja)
    "provision_expense": 1,         # Gastamos de provision: fondos disminuyen (balance sube)
}


# ---------------------------------------------------------------------------
# Helpers para convertir modelo ORM a response con nombres de relaciones
# ---------------------------------------------------------------------------

def _to_response(movement) -> dict:
    """Convertir MoneyMovement ORM a dict con nombres de relaciones."""
    data = {c.name: getattr(movement, c.name) for c in movement.__table__.columns}
    # Agregar nombres de relaciones (si estan cargadas)
    data["account_name"] = movement.account.name if movement.account else None
    data["third_party_name"] = movement.third_party.name if movement.third_party else None
    data["expense_category_name"] = movement.expense_category.name if movement.expense_category else None
    return data


# ---------------------------------------------------------------------------
# Endpoints de creacion — uno por tipo de operacion
# ---------------------------------------------------------------------------

@router.post(
    "/supplier-payment",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_supplier_payment(
    data: SupplierPaymentCreate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Pago a proveedor.

    Efectos: account(-), supplier.balance(+)
    """
    movement = money_movement.pay_supplier(
        db=db,
        data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    # Recargar con relaciones para la respuesta
    loaded = money_movement.get(db, movement.id, org_context["organization_id"])
    return _to_response(loaded)


@router.post(
    "/customer-collection",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_customer_collection(
    data: CustomerCollectionCreate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Cobro a cliente.

    Efectos: account(+), customer.balance(-)
    """
    movement = money_movement.collect_from_customer(
        db=db,
        data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = money_movement.get(db, movement.id, org_context["organization_id"])
    return _to_response(loaded)


@router.post(
    "/expense",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_expense(
    data: ExpenseCreate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Registrar gasto operativo.

    Efectos: account(-)
    """
    movement = money_movement.create_expense(
        db=db,
        data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = money_movement.get(db, movement.id, org_context["organization_id"])
    return _to_response(loaded)


@router.post(
    "/service-income",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_service_income(
    data: ServiceIncomeCreate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Registrar ingreso por servicio.

    Efectos: account(+)
    """
    movement = money_movement.create_service_income(
        db=db,
        data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = money_movement.get(db, movement.id, org_context["organization_id"])
    return _to_response(loaded)


@router.post(
    "/transfer",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_transfer(
    data: TransferCreate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Transferencia entre cuentas. Crea par de movimientos (transfer_out + transfer_in).

    Efectos: source(-), destination(+)
    Retorna el movimiento transfer_out.
    """
    movement = money_movement.create_transfer(
        db=db,
        data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = money_movement.get(db, movement.id, org_context["organization_id"])
    return _to_response(loaded)


@router.post(
    "/capital-injection",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_capital_injection(
    data: CapitalInjectionCreate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Aporte de capital por inversor.

    Efectos: account(+), investor.balance(-)
    """
    movement = money_movement.create_capital_injection(
        db=db,
        data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = money_movement.get(db, movement.id, org_context["organization_id"])
    return _to_response(loaded)


@router.post(
    "/capital-return",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_capital_return(
    data: CapitalReturnCreate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Retiro de capital por inversor.

    Efectos: account(-), investor.balance(+)
    """
    movement = money_movement.create_capital_return(
        db=db,
        data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = money_movement.get(db, movement.id, org_context["organization_id"])
    return _to_response(loaded)


@router.post(
    "/commission-payment",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_commission_payment(
    data: CommissionPaymentCreate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Pago de comision a tercero.

    Efectos: account(-), third_party.balance(+)
    """
    movement = money_movement.pay_commission(
        db=db,
        data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = money_movement.get(db, movement.id, org_context["organization_id"])
    return _to_response(loaded)


@router.post(
    "/provision-deposit",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_provision_deposit(
    data: ProvisionDepositCreate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Deposito a provision.

    Efectos: account(-), provision.balance(-)
    """
    movement = money_movement.deposit_to_provision(
        db=db,
        data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = money_movement.get(db, movement.id, org_context["organization_id"])
    return _to_response(loaded)


@router.post(
    "/provision-expense",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_provision_expense(
    data: ProvisionExpenseCreate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Gasto desde provision — NO afecta cuentas de dinero.

    Efectos: provision.balance(+)
    """
    movement = money_movement.create_provision_expense(
        db=db,
        data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = money_movement.get(db, movement.id, org_context["organization_id"])
    return _to_response(loaded)


# ---------------------------------------------------------------------------
# Endpoints de lectura
# ---------------------------------------------------------------------------

@router.get("", response_model=dict)
def list_money_movements(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    movement_type: Optional[str] = Query(None, description="Filtrar por tipo de movimiento"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filtrar por estado"),
    account_id: Optional[UUID] = Query(None, description="Filtrar por cuenta"),
    third_party_id: Optional[UUID] = Query(None, description="Filtrar por tercero"),
    date_from: Optional[date] = Query(None, description="Fecha desde"),
    date_to: Optional[date] = Query(None, description="Fecha hasta"),
    search: Optional[str] = Query(None, description="Buscar en descripcion o referencia"),
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Listar movimientos de dinero con filtros y paginacion."""
    date_from_dt = datetime.combine(date_from, dt_time.min, tzinfo=tz.utc) if date_from else None
    date_to_dt = datetime.combine(date_to + timedelta(days=1), dt_time.min, tzinfo=tz.utc) if date_to else None
    movements, total = money_movement.get_multi(
        db=db,
        organization_id=org_context["organization_id"],
        skip=skip,
        limit=limit,
        movement_type=movement_type,
        status_filter=status_filter,
        account_id=account_id,
        third_party_id=third_party_id,
        date_from=date_from_dt,
        date_to=date_to_dt,
        search=search,
    )
    return {
        "items": [_to_response(m) for m in movements],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/summary", response_model=list[MoneyMovementSummary])
def get_movements_summary(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Resumen de movimientos agrupados por tipo para un periodo."""
    date_from_dt = datetime.combine(date_from, dt_time.min, tzinfo=tz.utc) if date_from else None
    date_to_dt = datetime.combine(date_to + timedelta(days=1), dt_time.min, tzinfo=tz.utc) if date_to else None
    return money_movement.get_summary(
        db=db,
        organization_id=org_context["organization_id"],
        date_from=date_from_dt,
        date_to=date_to_dt,
    )


@router.get("/by-number/{movement_number}", response_model=MoneyMovementResponse)
def get_by_number(
    movement_number: int,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Obtener movimiento por numero secuencial."""
    movement = money_movement.get_by_number(db, movement_number, org_context["organization_id"])
    if not movement:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    return _to_response(movement)


@router.get("/account/{account_id}", response_model=dict)
def get_by_account(
    account_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Movimientos de una cuenta especifica."""
    movements, total = money_movement.get_by_account(
        db=db,
        account_id=account_id,
        organization_id=org_context["organization_id"],
        skip=skip,
        limit=limit,
    )
    return {
        "items": [_to_response(m) for m in movements],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/third-party/{third_party_id}", response_model=dict)
def get_by_third_party(
    third_party_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    date_from: Optional[date] = Query(None, description="Fecha desde"),
    date_to: Optional[date] = Query(None, description="Fecha hasta"),
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Estado de cuenta de un tercero con saldo corrido (balance_after).

    Calcula balance iterativo sobre TODOS los movimientos confirmados
    del tercero, luego mapea balance_after a la pagina solicitada.
    Si date_from, calcula saldo de apertura con movimientos anteriores.
    """
    from sqlalchemy import select as sa_select
    from sqlalchemy.orm import joinedload as jl

    org_id = org_context["organization_id"]
    date_from_dt = datetime.combine(date_from, dt_time.min, tzinfo=tz.utc) if date_from else None
    date_to_dt = datetime.combine(date_to + timedelta(days=1), dt_time.min, tzinfo=tz.utc) if date_to else None

    # 1. Query TODOS los movimientos confirmados del tercero (para balance corrido)
    all_query = (
        sa_select(MoneyMovement)
        .where(
            MoneyMovement.organization_id == org_id,
            MoneyMovement.third_party_id == third_party_id,
            MoneyMovement.status == "confirmed",
        )
        .order_by(MoneyMovement.date.asc(), MoneyMovement.movement_number.asc())
    )
    all_movs = list(db.scalars(all_query).all())

    # 2. Calcular balance corrido iterativo
    balance = Decimal("0")
    balance_map = {}
    opening_balance = Decimal("0")

    for m in all_movs:
        direction = THIRD_PARTY_BALANCE_DIRECTION.get(m.movement_type, 0)
        balance += m.amount * direction
        balance_map[m.id] = float(balance)
        # Saldo de apertura: ultimo balance ANTES de date_from
        if date_from_dt and m.date < date_from_dt:
            opening_balance = balance

    # 3. Query paginada con filtros de fecha
    movements, total = money_movement.get_multi(
        db=db,
        organization_id=org_id,
        third_party_id=third_party_id,
        date_from=date_from_dt,
        date_to=date_to_dt,
        skip=skip,
        limit=limit,
    )

    # 4. Construir respuesta con balance_after
    items = []
    for m in movements:
        data = _to_response(m)
        data["balance_after"] = balance_map.get(m.id)
        items.append(data)

    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
        "opening_balance": float(opening_balance) if date_from_dt else None,
    }


@router.get("/{movement_id}", response_model=MoneyMovementResponse)
def get_movement(
    movement_id: UUID,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Obtener un movimiento por ID."""
    movement = money_movement.get_or_404(db, movement_id, org_context["organization_id"])
    return _to_response(movement)


# ---------------------------------------------------------------------------
# Anulacion
# ---------------------------------------------------------------------------

@router.post("/{movement_id}/annul", response_model=AnnulMovementResponse)
def annul_movement(
    movement_id: UUID,
    data: AnnulMovementRequest,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Anular un movimiento confirmado.

    Revierte todos los efectos en saldos.
    Si es transferencia, anula el par automaticamente.
    Retorna warnings si la anulacion deja una provision en sobregiro.
    """
    movement, warnings = money_movement.annul(
        db=db,
        movement_id=movement_id,
        reason=data.reason,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = money_movement.get(db, movement.id, org_context["organization_id"])
    response = _to_response(loaded)
    return {**response, "warnings": warnings}
