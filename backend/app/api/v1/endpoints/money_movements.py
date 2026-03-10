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

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
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
    AdvancePaymentCreate,
    AdvanceCollectionCreate,
    AssetPaymentCreate,
    AnnulMovementRequest,
    AnnulMovementResponse,
    MoneyMovementResponse,
    MoneyMovementSummary,
)
from app.models.money_movement import MoneyMovement
from app.models.money_account import MoneyAccount
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
    "advance_payment": 1,           # Anticipo a proveedor: proveedor nos debe
    "advance_collection": -1,       # Anticipo de cliente: nosotros debemos al cliente
    # asset_payment: tercero es solo referencia, NO afecta balance
}

# Direccion del efecto en el balance de la cuenta por tipo de movimiento.
# Positivo = entrada de dinero. Negativo = salida de dinero.
ACCOUNT_BALANCE_DIRECTION = {
    "collection_from_client": 1,
    "service_income": 1,
    "capital_injection": 1,
    "transfer_in": 1,
    "advance_collection": 1,
    "payment_to_supplier": -1,
    "expense": -1,
    "commission_payment": -1,
    "capital_return": -1,
    "transfer_out": -1,
    "provision_deposit": -1,
    "advance_payment": -1,
    "asset_payment": -1,
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


@router.post(
    "/advance-payment",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_advance_payment(
    data: AdvancePaymentCreate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Anticipo a proveedor.

    Efectos: account(-), supplier.balance(+) — proveedor nos debe.
    """
    movement = money_movement.pay_advance(
        db=db,
        data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = money_movement.get(db, movement.id, org_context["organization_id"])
    return _to_response(loaded)


@router.post(
    "/advance-collection",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_advance_collection(
    data: AdvanceCollectionCreate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Anticipo de cliente.

    Efectos: account(+), customer.balance(-) — nosotros debemos al cliente.
    """
    movement = money_movement.collect_advance(
        db=db,
        data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = money_movement.get(db, movement.id, org_context["organization_id"])
    return _to_response(loaded)


@router.post(
    "/asset-payment",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_asset_payment(
    data: AssetPaymentCreate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Pago de activo fijo.

    Efectos: account(-), third_party.balance(+) si se indica tercero.
    """
    movement = money_movement.pay_asset(
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
    date_from: Optional[date] = Query(None, description="Fecha desde"),
    date_to: Optional[date] = Query(None, description="Fecha hasta"),
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Estado de cuenta de una cuenta de dinero con saldo corrido.

    Incluye movimientos confirmados y anulados. Anulados aparecen
    pero no afectan el balance. Default: ultimos 90 dias.
    """
    from sqlalchemy import select as sa_select

    org_id = org_context["organization_id"]

    # Default 90 dias
    effective_date_from = date_from if date_from else (date.today() - timedelta(days=90))
    effective_date_to = date_to if date_to else None

    # Query todos los movimientos de esta cuenta (confirmed + annulled)
    query = sa_select(MoneyMovement).where(
        MoneyMovement.organization_id == org_id,
        MoneyMovement.account_id == account_id,
        MoneyMovement.status.in_(["confirmed", "annulled"]),
    ).order_by(MoneyMovement.created_at)

    movements = db.scalars(query).all()

    # Calcular saldo base (initial_balance) = current_balance - efecto neto de todos los movimientos
    account = db.get(MoneyAccount, account_id)
    if not account:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    net_effect = sum(
        m.amount * ACCOUNT_BALANCE_DIRECTION.get(m.movement_type, 0)
        for m in movements if m.status != "annulled"
    )
    base_balance = account.current_balance - net_effect

    # Calcular balance corrido
    balance = base_balance
    opening_balance = base_balance
    all_items = []

    for m in movements:
        direction = ACCOUNT_BALANCE_DIRECTION.get(m.movement_type, 0)
        if m.status != "annulled":
            balance += m.amount * direction
        balance_after = float(balance)

        # Filtro de fechas (usar m.date para filtrar)
        m_date = m.date.date() if isinstance(m.date, datetime) else m.date
        if m_date < effective_date_from:
            opening_balance = balance
            continue
        if effective_date_to and m_date > effective_date_to:
            continue

        item = _to_response(m)
        item["direction"] = direction
        item["balance_after"] = balance_after
        all_items.append(item)

    # Paginar
    total = len(all_items)
    page = all_items[skip:skip + limit]

    return {
        "items": page,
        "total": total,
        "skip": skip,
        "limit": limit,
        "opening_balance": float(opening_balance) if date_from else None,
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
    Estado de cuenta COMPLETO (unified account statement) de un tercero con saldo corrido.

    Incluye TODAS las operaciones que afectan el balance:
    - MoneyMovements confirmados y anulados (pagos, cobros, anticipos, etc.)
    - Compras liquidadas/canceladas (solo standalone, no doble partida)
    - Ventas liquidadas/canceladas (solo standalone, no doble partida)
    - Comisiones de ventas standalone
    - Doble partida (compra+venta simultanea) y sus comisiones

    Cada item incluye source/source_id/source_number para trazar al registro original.
    Si no se provee date_from, default a 90 dias atras.
    """
    from sqlalchemy import select as sa_select
    from sqlalchemy.orm import joinedload

    from app.models.purchase import Purchase
    from app.models.sale import Sale, SaleCommission
    from app.models.double_entry import DoubleEntry

    org_id = org_context["organization_id"]

    # Default: ultimos 90 dias si no se provee date_from
    effective_date_from = date_from if date_from else (date.today() - timedelta(days=90))
    date_from_dt = datetime.combine(effective_date_from, dt_time.min, tzinfo=tz.utc)
    date_to_dt = datetime.combine(date_to + timedelta(days=1), dt_time.min, tzinfo=tz.utc) if date_to else None

    # --- Recopilar TODOS los eventos que afectan el balance del tercero ---
    # Cada evento: (sort_datetime, sort_key, filter_datetime, event_dict)
    # sort_datetime: timestamps del servidor (created_at, liquidated_at) para orden cronologico real
    # filter_datetime: timestamp para aplicar filtros de fecha (= sort_datetime por defecto)
    # sort_key: 0=operacion comercial, 1=movimiento tesoreria, 2=cancelacion/anulacion
    events: list[tuple] = []

    def _evt(sort_dt, sort_key, filter_dt=None, **kwargs):
        events.append((sort_dt, sort_key, filter_dt or sort_dt, kwargs))

    # 1. MoneyMovements confirmados y anulados
    mm_query = sa_select(MoneyMovement).where(
        MoneyMovement.organization_id == org_id,
        MoneyMovement.third_party_id == third_party_id,
        MoneyMovement.status.in_(["confirmed", "annulled"]),
    )
    for m in db.scalars(mm_query).all():
        direction = THIRD_PARTY_BALANCE_DIRECTION.get(m.movement_type, 0)
        _evt(m.created_at, 1, filter_dt=m.date,
             id=str(m.id), date=m.date.isoformat(),
             event_type=m.movement_type, description=m.description or "",
             amount=float(m.amount), direction=direction,
             status=m.status, reference_number=m.reference_number,
             movement_number=m.movement_number,
             source="money_movement", source_id=str(m.id), source_number=m.movement_number)

    # 2. Compras liquidadas (standalone, no doble partida)
    # Proveedor: balance -= total_amount al liquidar
    purch_query = sa_select(Purchase).where(
        Purchase.organization_id == org_id,
        Purchase.supplier_id == third_party_id,
        Purchase.status.in_(["liquidated", "cancelled"]),
        Purchase.liquidated_at.isnot(None),
        Purchase.double_entry_id.is_(None),  # Excluir doble partida
    )
    for p in db.scalars(purch_query).all():
        _evt(p.liquidated_at, 0,
             id=f"purchase-{p.id}", date=p.liquidated_at.isoformat(),
             event_type="purchase_liquidation",
             description=f"Compra #{p.purchase_number} liquidada",
             amount=float(p.total_amount), direction=-1,
             status="confirmed" if p.status == "liquidated" else "cancelled",
             reference_number=None, movement_number=None,
             source="purchase", source_id=str(p.id), source_number=p.purchase_number)
        if p.status == "cancelled" and p.cancelled_at:
            _evt(p.cancelled_at, 2,
                 id=f"purchase-cancel-{p.id}", date=p.cancelled_at.isoformat(),
                 event_type="purchase_cancellation",
                 description=f"Compra #{p.purchase_number} cancelada (reversa)",
                 amount=float(p.total_amount), direction=1,
                 status="annulled", reference_number=None, movement_number=None,
                 source="purchase", source_id=str(p.id), source_number=p.purchase_number)

    # 3. Ventas liquidadas (standalone, no doble partida)
    # Cliente: balance += total_amount al liquidar
    sale_query = sa_select(Sale).where(
        Sale.organization_id == org_id,
        Sale.customer_id == third_party_id,
        Sale.status.in_(["liquidated", "cancelled"]),
        Sale.liquidated_at.isnot(None),
        Sale.double_entry_id.is_(None),  # Excluir doble partida
    )
    for s in db.scalars(sale_query).all():
        _evt(s.liquidated_at, 0,
             id=f"sale-{s.id}", date=s.liquidated_at.isoformat(),
             event_type="sale_liquidation",
             description=f"Venta #{s.sale_number} liquidada",
             amount=float(s.total_amount), direction=1,
             status="confirmed" if s.status == "liquidated" else "cancelled",
             reference_number=None, movement_number=None,
             source="sale", source_id=str(s.id), source_number=s.sale_number)
        if s.status == "cancelled" and s.cancelled_at:
            _evt(s.cancelled_at, 2,
                 id=f"sale-cancel-{s.id}", date=s.cancelled_at.isoformat(),
                 event_type="sale_cancellation",
                 description=f"Venta #{s.sale_number} cancelada (reversa)",
                 amount=float(s.total_amount), direction=-1,
                 status="annulled", reference_number=None, movement_number=None,
                 source="sale", source_id=str(s.id), source_number=s.sale_number)

    # 4. Comisiones de ventas standalone (receptor: balance += commission_amount)
    comm_query = (
        sa_select(SaleCommission, Sale)
        .join(Sale, SaleCommission.sale_id == Sale.id)
        .where(
            Sale.organization_id == org_id,
            SaleCommission.third_party_id == third_party_id,
            Sale.status.in_(["liquidated", "cancelled"]),
            Sale.liquidated_at.isnot(None),
            Sale.double_entry_id.is_(None),  # Excluir doble partida
        )
    )
    for comm, sale in db.execute(comm_query).all():
        _evt(sale.liquidated_at, 0,
             id=f"commission-{comm.id}", date=sale.liquidated_at.isoformat(),
             event_type="sale_commission",
             description=f"Comision Venta #{sale.sale_number}: {comm.concept}",
             amount=float(comm.commission_amount), direction=1,
             status="confirmed" if sale.status == "liquidated" else "cancelled",
             reference_number=None, movement_number=None,
             source="commission", source_id=str(comm.id), source_number=sale.sale_number)
        if sale.status == "cancelled" and sale.cancelled_at:
            _evt(sale.cancelled_at, 2,
                 id=f"commission-cancel-{comm.id}", date=sale.cancelled_at.isoformat(),
                 event_type="commission_cancellation",
                 description=f"Comision Venta #{sale.sale_number} cancelada (reversa)",
                 amount=float(comm.commission_amount), direction=-1,
                 status="annulled", reference_number=None, movement_number=None,
                 source="commission", source_id=str(comm.id), source_number=sale.sale_number)

    # 5. Doble partida — usa created_at como timestamp, Purchase/Sale para montos
    de_query = (
        sa_select(DoubleEntry)
        .options(joinedload(DoubleEntry.purchase), joinedload(DoubleEntry.sale))
        .where(
            DoubleEntry.organization_id == org_id,
            DoubleEntry.status.in_(["completed", "cancelled"]),
        )
        .where(
            (DoubleEntry.supplier_id == third_party_id)
            | (DoubleEntry.customer_id == third_party_id)
        )
    )
    for de in db.scalars(de_query).unique().all():
        de_dt = de.created_at  # datetime del registro
        purchase_amount = float(de.purchase.total_amount) if de.purchase else 0
        sale_amount = float(de.sale.total_amount) if de.sale else 0
        is_active = de.status == "completed"
        evt_status = "confirmed" if is_active else "cancelled"

        # Como proveedor
        if de.supplier_id == third_party_id:
            _evt(de_dt, 0,
                 id=f"de-supplier-{de.id}", date=de_dt.isoformat(),
                 event_type="double_entry_purchase",
                 description=f"Doble Partida #{de.double_entry_number} (como proveedor)",
                 amount=purchase_amount, direction=-1,
                 status=evt_status, reference_number=None, movement_number=None,
                 source="double_entry", source_id=str(de.id), source_number=de.double_entry_number)
        # Como cliente
        if de.customer_id == third_party_id:
            _evt(de_dt, 0,
                 id=f"de-customer-{de.id}", date=de_dt.isoformat(),
                 event_type="double_entry_sale",
                 description=f"Doble Partida #{de.double_entry_number} (como cliente)",
                 amount=sale_amount, direction=1,
                 status=evt_status, reference_number=None, movement_number=None,
                 source="double_entry", source_id=str(de.id), source_number=de.double_entry_number)

        # Cancelacion reversa (usar updated_at como proxy de cancelled_at)
        if de.status == "cancelled":
            cancel_dt = de.updated_at or de_dt
            if de.supplier_id == third_party_id:
                _evt(cancel_dt, 2,
                     id=f"de-cancel-supplier-{de.id}", date=cancel_dt.isoformat(),
                     event_type="double_entry_cancellation",
                     description=f"Doble Partida #{de.double_entry_number} cancelada (reversa proveedor)",
                     amount=purchase_amount, direction=1,
                     status="annulled", reference_number=None, movement_number=None,
                     source="double_entry", source_id=str(de.id), source_number=de.double_entry_number)
            if de.customer_id == third_party_id:
                _evt(cancel_dt, 2,
                     id=f"de-cancel-customer-{de.id}", date=cancel_dt.isoformat(),
                     event_type="double_entry_cancellation",
                     description=f"Doble Partida #{de.double_entry_number} cancelada (reversa cliente)",
                     amount=sale_amount, direction=-1,
                     status="annulled", reference_number=None, movement_number=None,
                     source="double_entry", source_id=str(de.id), source_number=de.double_entry_number)

    # 6. Comisiones de doble partida
    de_comm_query = (
        sa_select(SaleCommission, Sale, DoubleEntry)
        .join(Sale, SaleCommission.sale_id == Sale.id)
        .join(DoubleEntry, DoubleEntry.sale_id == Sale.id)
        .where(
            DoubleEntry.organization_id == org_id,
            SaleCommission.third_party_id == third_party_id,
            DoubleEntry.status.in_(["completed", "cancelled"]),
        )
    )
    for comm, sale, de in db.execute(de_comm_query).all():
        de_dt = de.created_at
        is_active = de.status == "completed"
        _evt(de_dt, 0,
             id=f"de-commission-{comm.id}", date=de_dt.isoformat(),
             event_type="double_entry_commission",
             description=f"Comision DP #{de.double_entry_number}: {comm.concept}",
             amount=float(comm.commission_amount), direction=1,
             status="confirmed" if is_active else "cancelled",
             reference_number=None, movement_number=None,
             source="commission", source_id=str(comm.id), source_number=de.double_entry_number)
        if de.status == "cancelled":
            cancel_dt = de.updated_at or de_dt
            _evt(cancel_dt, 2,
                 id=f"de-comm-cancel-{comm.id}", date=cancel_dt.isoformat(),
                 event_type="double_entry_commission_cancellation",
                 description=f"Comision DP #{de.double_entry_number} cancelada (reversa)",
                 amount=float(comm.commission_amount), direction=-1,
                 status="annulled", reference_number=None, movement_number=None,
                 source="commission", source_id=str(comm.id), source_number=de.double_entry_number)

    # --- Ordenar por fecha, sort_key ---
    events.sort(key=lambda e: (e[0], e[1]))

    # --- Calcular balance corrido ---
    balance = Decimal("0")
    opening_balance = Decimal("0")
    all_items = []

    for _, _, filter_dt, evt in events:
        if evt["status"] not in ("annulled", "cancelled"):
            balance += Decimal(str(evt["amount"])) * evt["direction"]
        evt["balance_after"] = float(balance)

        if date_from_dt and filter_dt < date_from_dt:
            opening_balance = balance
            continue
        if date_to_dt and filter_dt >= date_to_dt:
            continue

        all_items.append(evt)

    # --- Paginar ---
    total = len(all_items)
    page = all_items[skip:skip + limit]

    return {
        "items": page,
        "total": total,
        "skip": skip,
        "limit": limit,
        "opening_balance": float(opening_balance) if date_from_dt else None,
    }


# ---------------------------------------------------------------------------
# Evidencia (upload / download / delete)
# IMPORTANTE: Estos endpoints deben ir ANTES de GET /{movement_id}
# para evitar que FastAPI capture "evidence" como UUID.
# ---------------------------------------------------------------------------

ALLOWED_EVIDENCE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp", "pdf"}


@router.post("/{movement_id}/evidence", response_model=MoneyMovementResponse)
def upload_evidence(
    movement_id: UUID,
    file: UploadFile = File(...),
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Subir comprobante adjunto a un movimiento."""
    import os
    from app.core.config import settings

    org_id = str(org_context["organization_id"])
    mov = money_movement.get_or_404(db, movement_id, org_context["organization_id"])

    # Validar extension
    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if file.filename else ""
    if ext not in ALLOWED_EVIDENCE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de archivo no permitido. Extensiones validas: {', '.join(ALLOWED_EVIDENCE_EXTENSIONS)}",
        )

    # Leer y validar tamano
    content = file.file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Archivo excede el tamano maximo de {settings.MAX_UPLOAD_SIZE // (1024 * 1024)}MB",
        )

    # Crear directorio
    evidence_dir = os.path.join(settings.UPLOAD_DIR, "evidence", org_id)
    os.makedirs(evidence_dir, exist_ok=True)

    # Eliminar archivo previo si existe
    if mov.evidence_url:
        old_path = os.path.join(settings.UPLOAD_DIR, mov.evidence_url)
        if os.path.exists(old_path):
            os.remove(old_path)

    # Guardar nuevo archivo
    timestamp = int(datetime.now(tz=tz.utc).timestamp())
    filename = f"{movement_id}_{timestamp}.{ext}"
    filepath = os.path.join(evidence_dir, filename)
    with open(filepath, "wb") as f:
        f.write(content)

    # Actualizar modelo
    mov.evidence_url = f"evidence/{org_id}/{filename}"
    db.commit()
    db.refresh(mov)
    return _to_response(mov)


@router.get("/{movement_id}/evidence")
def download_evidence(
    movement_id: UUID,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Descargar comprobante adjunto de un movimiento."""
    import os
    import mimetypes
    from app.core.config import settings

    mov = money_movement.get_or_404(db, movement_id, org_context["organization_id"])

    if not mov.evidence_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El movimiento no tiene comprobante adjunto")

    filepath = os.path.join(settings.UPLOAD_DIR, mov.evidence_url)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo no encontrado en disco")

    media_type = mimetypes.guess_type(filepath)[0] or "application/octet-stream"
    filename = os.path.basename(filepath)
    return FileResponse(filepath, media_type=media_type, filename=filename)


@router.delete("/{movement_id}/evidence", response_model=MoneyMovementResponse)
def delete_evidence(
    movement_id: UUID,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Eliminar comprobante adjunto de un movimiento."""
    import os
    from app.core.config import settings

    mov = money_movement.get_or_404(db, movement_id, org_context["organization_id"])

    if not mov.evidence_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El movimiento no tiene comprobante adjunto")

    filepath = os.path.join(settings.UPLOAD_DIR, mov.evidence_url)
    if os.path.exists(filepath):
        os.remove(filepath)

    mov.evidence_url = None
    db.commit()
    db.refresh(mov)
    return _to_response(mov)


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
