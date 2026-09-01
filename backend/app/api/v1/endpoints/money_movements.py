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
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.utils.dates import business_today
from app.api.deps import require_permission, get_db
from app.services.organization import get_user_account_assignments
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
    ExpenseAccrualCreate,
    GenericPaymentCreate,
    GenericCollectionCreate,
    ThirdPartyTransferCreate,
    ThirdPartyAdjustmentCreate,
    BatchExpenseCreate,
    AnnulMovementRequest,
    AnnulMovementResponse,
    UpdateClassificationRequest,
    MoneyMovementResponse,
    MoneyMovementSummary,
)
from app.models.money_movement import MoneyMovement
from app.models.money_account import MoneyAccount
from app.models.third_party import ThirdParty
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
    "expense_accrual": -1,          # Gasto causado: le debemos mas (balance baja)
    "deferred_funding": 1,          # Pago gasto diferido: prepago nos debe (balance sube)
    "deferred_expense": -1,         # Cuota gasto diferido: reduce prepago (balance baja)
    "commission_accrual": -1,        # Comision causada: les debemos comision (balance baja)
    "asset_purchase": -1,            # Compra activo a credito: le debemos (balance baja)
    "payment_to_generic": 1,         # Pagamos a generico: su balance sube
    "collection_from_generic": -1,   # Cobramos a generico: su balance baja
    "tp_transfer_out": -1,           # Transferencia entre terceros: source paga (balance baja)
    "tp_transfer_in": 1,             # Transferencia entre terceros: dest recibe pago (se le abona)
    "tp_adjustment_credit": 1,       # Ajuste credito: saldo sube (hacia cero desde negativo)
    "tp_adjustment_debit": -1,       # Ajuste debito: saldo baja (hacia cero desde positivo)
    "asset_revaluation_credit": -1,     # Revalorizacion activo alza a credito: le debemos (balance baja)
    "asset_devaluation_receivable": 1,  # Devaluacion activo a cargo del tercero: nos debe (balance sube)
    "asset_sale_receivable": 1,         # Venta de activo a credito: nos debe (balance sube)
    "service_income_accrual": 1,        # Servicio facturado sin cobrar (W1): nos debe
    "obligation_disbursement": -1,      # Nos prestan: les debemos mas (balance baja)
    "obligation_interest_accrual": -1,  # Interes causado por pagar: debemos mas (balance baja)
    "obligation_interest_payment": 1,   # Pago de intereses: debemos menos (balance sube)
    "obligation_capital_payment": 1,    # Abono a capital: debemos menos (balance sube)
    "loan_disbursement": 1,             # Prestamos nosotros: nos debe mas (balance sube)
    "loan_interest_accrual": 1,         # Interes causado por cobrar: nos debe mas (balance sube)
    "loan_interest_collection": -1,     # Recaudo de intereses: nos debe menos (balance baja)
    "loan_capital_collection": -1,      # Recaudo de capital: nos debe menos (balance baja)
    "obligation_interest_transfer": 1,  # Traslado a tercero: la obligacion debe menos (balance sube)
    "obligation_capital_transfer": 1,   # Abono desde tercero: la obligacion debe menos (balance sube)
    "loan_interest_transfer": -1,       # Traslado (prestamo): el deudor debe menos (balance baja)
    "loan_capital_transfer": -1,        # Recaudo desde tercero: el deudor debe menos (balance baja)
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
    "deferred_funding": -1,         # Pago inicial gasto diferido: sale dinero de cuenta
    "payment_to_generic": -1,        # Pago a generico: sale dinero
    "collection_from_generic": 1,    # Cobro a generico: entra dinero
    "asset_revaluation_payment": -1,    # Revalorizacion activo alza pagada: sale dinero
    "asset_devaluation_collection": 1,  # Devaluacion activo con reembolso: entra dinero
    "asset_sale_collection": 1,         # Venta de activo a cuenta: entra dinero
    "obligation_disbursement": 1,       # Nos prestan: entra el prestamo
    "obligation_interest_payment": -1,  # Pago de intereses: sale dinero
    "obligation_capital_payment": -1,   # Abono a capital: sale dinero
    "loan_disbursement": -1,            # Prestamos nosotros: sale el prestamo
    "loan_interest_collection": 1,      # Recaudo de intereses: entra dinero
    "loan_capital_collection": 1,       # Recaudo de capital: entra dinero
    # expense_accrual: NO toca cuenta (account_id=None)
    # deferred_expense: NO toca cuenta (account_id=None)
    # obligation_interest_accrual / loan_interest_accrual: NO tocan cuenta
    # *_interest_transfer / *_capital_transfer + sus legs tp_transfer_*:
    # NO tocan cuenta (traslados contra tercero, account_id=None)
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_allowed_accounts(db: Session, ctx: dict) -> list[UUID] | None:
    """Retorna lista de account_ids permitidos o None si ve todo."""
    if ctx["is_admin"]:
        return None
    assigned = get_user_account_assignments(db, ctx["user_id"], ctx["organization_id"])
    return assigned if assigned else None


def _to_response(movement, db: Session = None) -> dict:
    """Convertir MoneyMovement ORM a dict con nombres de relaciones."""
    data = {c.name: getattr(movement, c.name) for c in movement.__table__.columns}
    # Agregar nombres de relaciones (si estan cargadas)
    data["account_name"] = movement.account.name if movement.account else None
    data["third_party_name"] = movement.third_party.name if movement.third_party else None
    data["expense_category_name"] = movement.expense_category.name if movement.expense_category else None
    data["business_unit_name"] = movement.business_unit.name if movement.business_unit else None
    # Resolver nombres de UNs compartidas desde JSONB
    data["applicable_business_unit_names"] = None
    if movement.applicable_business_unit_ids and db is not None:
        from app.models.business_unit import BusinessUnit
        names = db.execute(
            select(BusinessUnit.name).where(
                BusinessUnit.id.in_(movement.applicable_business_unit_ids)
            )
        ).scalars().all()
        data["applicable_business_unit_names"] = list(names)
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
    org_context: dict = Depends(require_permission("treasury.create_movements")),
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
    return _to_response(loaded, db)


@router.post(
    "/customer-collection",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_customer_collection(
    data: CustomerCollectionCreate,
    org_context: dict = Depends(require_permission("treasury.create_movements")),
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
    return _to_response(loaded, db)


@router.post(
    "/expense",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_expense(
    data: ExpenseCreate,
    org_context: dict = Depends(require_permission("treasury.create_movements")),
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
    return _to_response(loaded, db)


@router.post(
    "/service-income",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_service_income(
    data: ServiceIncomeCreate,
    org_context: dict = Depends(require_permission("treasury.create_movements")),
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
    return _to_response(loaded, db)


@router.post(
    "/transfer",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_transfer(
    data: TransferCreate,
    org_context: dict = Depends(require_permission("treasury.create_movements")),
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
    return _to_response(loaded, db)


@router.post(
    "/capital-injection",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_capital_injection(
    data: CapitalInjectionCreate,
    org_context: dict = Depends(require_permission("treasury.create_movements")),
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
    return _to_response(loaded, db)


@router.post(
    "/capital-return",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_capital_return(
    data: CapitalReturnCreate,
    org_context: dict = Depends(require_permission("treasury.create_movements")),
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
    return _to_response(loaded, db)


@router.post(
    "/commission-payment",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_commission_payment(
    data: CommissionPaymentCreate,
    org_context: dict = Depends(require_permission("treasury.create_movements")),
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
    return _to_response(loaded, db)


@router.post(
    "/provision-deposit",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_provision_deposit(
    data: ProvisionDepositCreate,
    org_context: dict = Depends(require_permission("treasury.create_movements")),
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
    return _to_response(loaded, db)


@router.post(
    "/provision-expense",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_provision_expense(
    data: ProvisionExpenseCreate,
    org_context: dict = Depends(require_permission("treasury.create_movements")),
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
    return _to_response(loaded, db)


@router.post(
    "/advance-payment",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_advance_payment(
    data: AdvancePaymentCreate,
    org_context: dict = Depends(require_permission("treasury.create_movements")),
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
    return _to_response(loaded, db)


@router.post(
    "/advance-collection",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_advance_collection(
    data: AdvanceCollectionCreate,
    org_context: dict = Depends(require_permission("treasury.create_movements")),
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
    return _to_response(loaded, db)


@router.post(
    "/asset-payment",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_asset_payment(
    data: AssetPaymentCreate,
    org_context: dict = Depends(require_permission("treasury.create_movements")),
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
    return _to_response(loaded, db)


@router.post(
    "/expense-accrual",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_expense_accrual(
    data: ExpenseAccrualCreate,
    org_context: dict = Depends(require_permission("treasury.create_movements")),
    db: Session = Depends(get_db),
):
    """
    Gasto causado (pasivo) — NO mueve dinero de cuentas.

    Efectos: third_party.balance(-), aparece en P&L.
    """
    movement = money_movement.create_expense_accrual(
        db=db,
        data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = money_movement.get(db, movement.id, org_context["organization_id"])
    return _to_response(loaded, db)


@router.post(
    "/payment-to-generic",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_payment_to_generic(
    data: GenericPaymentCreate,
    org_context: dict = Depends(require_permission("treasury.create_movements")),
    db: Session = Depends(get_db),
):
    """
    Pago a tercero generico — account(-), third_party.balance(+).
    """
    movement = money_movement.pay_generic(
        db=db,
        data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = money_movement.get(db, movement.id, org_context["organization_id"])
    return _to_response(loaded, db)


@router.post(
    "/collection-from-generic",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_collection_from_generic(
    data: GenericCollectionCreate,
    org_context: dict = Depends(require_permission("treasury.create_movements")),
    db: Session = Depends(get_db),
):
    """
    Cobro a tercero generico — account(+), third_party.balance(-).
    """
    movement = money_movement.collect_from_generic(
        db=db,
        data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = money_movement.get(db, movement.id, org_context["organization_id"])
    return _to_response(loaded, db)


@router.post("/tp-transfer", response_model=MoneyMovementResponse, status_code=status.HTTP_201_CREATED)
def create_tp_transfer(
    data: ThirdPartyTransferCreate,
    org_context: dict = Depends(require_permission("treasury.create_movements")),
    db: Session = Depends(get_db),
):
    """
    Transferencia entre terceros — cruce de cuentas sin mover dinero.
    Un tercero paga directamente a otro, sin pasar por cuentas de la empresa.
    """
    movement = money_movement.create_tp_transfer(
        db=db,
        data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = money_movement.get(db, movement.id, org_context["organization_id"])
    return _to_response(loaded, db)


@router.post(
    "/tp-adjustment-credit",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_tp_adjustment_credit(
    data: ThirdPartyAdjustmentCreate,
    org_context: dict = Depends(require_permission("treasury.adjust_balances")),
    db: Session = Depends(get_db),
):
    """Ajuste credito: saldo del tercero sube (tercero con saldo negativo hacia cero)."""
    movement = money_movement.adjust_tp_credit(
        db=db, data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = money_movement.get(db, movement.id, org_context["organization_id"])
    return _to_response(loaded, db)


@router.post(
    "/tp-adjustment-debit",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_tp_adjustment_debit(
    data: ThirdPartyAdjustmentCreate,
    org_context: dict = Depends(require_permission("treasury.adjust_balances")),
    db: Session = Depends(get_db),
):
    """Ajuste debito: saldo del tercero baja (tercero con saldo positivo hacia cero)."""
    movement = money_movement.adjust_tp_debit(
        db=db, data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    loaded = money_movement.get(db, movement.id, org_context["organization_id"])
    return _to_response(loaded, db)


@router.post("/batch-expenses", status_code=status.HTTP_201_CREATED)
def create_batch_expenses(
    data: BatchExpenseCreate,
    org_context: dict = Depends(require_permission("treasury.create_movements")),
    db: Session = Depends(get_db),
):
    """Crear multiples gastos en una sola transaccion (all-or-nothing)."""
    movements = money_movement.create_batch_expenses(
        db=db,
        data=data,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    return {
        "created": len(movements),
        "movements": [{"id": str(m.id), "movement_number": m.movement_number} for m in movements],
    }


# ---------------------------------------------------------------------------
# Endpoints de lectura
# ---------------------------------------------------------------------------

@router.get("", response_model=dict)
def list_money_movements(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=10000),
    movement_type: Optional[str] = Query(None, description="Filtrar por tipo de movimiento (acepta CSV: 'type1,type2')"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filtrar por estado"),
    account_id: Optional[UUID] = Query(None, description="Filtrar por cuenta"),
    third_party_id: Optional[UUID] = Query(None, description="Filtrar por tercero"),
    date_from: Optional[date] = Query(None, description="Fecha desde"),
    date_to: Optional[date] = Query(None, description="Fecha hasta"),
    search: Optional[str] = Query(None, description="Buscar en descripcion o referencia"),
    adjustment_class: Optional[str] = Query(None, pattern="^(gain|loss)$", description="Filtra tp_adjustment por clase P&L: gain o loss"),
    commission_source: Optional[str] = Query(None, pattern="^(sale|double_entry)$", description="Filtra commission_accrual por origen: sale (venta regular) o double_entry (Pasa Mano)"),
    pnl_section: Optional[str] = Query(None, pattern="^(operativo|financiero|depreciacion)$", description="Filtra gastos por seccion del P&L por rubros (restringe implicitamente a tipos de gasto)"),
    sort_by: Optional[str] = Query(None, description="Columna a ordenar (allowlist en service, fallback silencioso a 'date')"),
    sort_dir: str = Query("desc", regex="^(asc|desc)$", description="Direccion: asc | desc"),
    org_context: dict = Depends(require_permission("treasury.view_movements")),
    db: Session = Depends(get_db),
):
    """Listar movimientos de dinero con filtros y paginacion."""
    date_from_dt = datetime.combine(date_from, dt_time.min, tzinfo=tz.utc) if date_from else None
    date_to_dt = datetime.combine(date_to + timedelta(days=1), dt_time.min, tzinfo=tz.utc) if date_to else None
    allowed = _get_allowed_accounts(db, org_context)

    # Sin permiso view_all_movements: solo ver movimientos propios (created_by = user_id).
    # Admin siempre ve todo.
    can_view_all = org_context["is_admin"] or "treasury.view_all_movements" in org_context["user_permissions"]
    created_by_filter = None if can_view_all else org_context["user_id"]

    movements, total, amount_sum = money_movement.get_multi(
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
        allowed_account_ids=allowed,
        created_by_filter=created_by_filter,
        adjustment_class=adjustment_class,
        commission_source=commission_source,
        pnl_section=pnl_section,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return {
        "items": [_to_response(m, db) for m in movements],
        "total": total,
        "skip": skip,
        "limit": limit,
        "total_amount_sum": float(amount_sum),
    }


@router.get("/summary", response_model=list[MoneyMovementSummary])
def get_movements_summary(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    org_context: dict = Depends(require_permission("treasury.view_movements")),
    db: Session = Depends(get_db),
):
    """Resumen de movimientos agrupados por tipo para un periodo."""
    date_from_dt = datetime.combine(date_from, dt_time.min, tzinfo=tz.utc) if date_from else None
    date_to_dt = datetime.combine(date_to + timedelta(days=1), dt_time.min, tzinfo=tz.utc) if date_to else None
    allowed = _get_allowed_accounts(db, org_context)
    return money_movement.get_summary(
        db=db,
        organization_id=org_context["organization_id"],
        date_from=date_from_dt,
        date_to=date_to_dt,
        allowed_account_ids=allowed,
    )


@router.get("/by-number/{movement_number}", response_model=MoneyMovementResponse)
def get_by_number(
    movement_number: int,
    org_context: dict = Depends(require_permission("treasury.view_movements")),
    db: Session = Depends(get_db),
):
    """Obtener movimiento por numero secuencial."""
    movement = money_movement.get_by_number(db, movement_number, org_context["organization_id"])
    if not movement:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    return _to_response(movement, db)


@router.get("/account/{account_id}", response_model=dict)
def get_by_account(
    account_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=5000),
    date_from: Optional[date] = Query(None, description="Fecha desde"),
    date_to: Optional[date] = Query(None, description="Fecha hasta"),
    org_context: dict = Depends(require_permission("treasury.view_accounts")),
    db: Session = Depends(get_db),
):
    """
    Estado de cuenta de una cuenta de dinero con saldo corrido.

    Incluye movimientos confirmados y anulados. Anulados aparecen
    pero no afectan el balance. Default: ultimos 90 dias.
    """
    # Verificar acceso a la cuenta
    allowed = _get_allowed_accounts(db, org_context)
    if allowed is not None and account_id not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a esta cuenta",
        )

    from sqlalchemy import select as sa_select

    org_id = org_context["organization_id"]

    # Default 90 dias
    effective_date_from = date_from if date_from else (business_today() - timedelta(days=90))
    effective_date_to = date_to if date_to else None

    # Query todos los movimientos de esta cuenta (confirmed + annulled)
    query = sa_select(MoneyMovement).where(
        MoneyMovement.organization_id == org_id,
        MoneyMovement.account_id == account_id,
        MoneyMovement.status.in_(["confirmed", "annulled"]),
    ).order_by(MoneyMovement.date, MoneyMovement.created_at)

    movements = db.scalars(query).all()

    # Calcular saldo base (initial_balance) = current_balance - efecto neto de todos los movimientos
    account = db.get(MoneyAccount, account_id)
    if not account:
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

        item = _to_response(m, db)
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
    limit: int = Query(500, ge=1, le=5000),
    date_from: Optional[date] = Query(None, description="Fecha desde"),
    date_to: Optional[date] = Query(None, description="Fecha hasta"),
    view: Optional[str] = Query(None, description="Vista: null=financiera, 'operations'=detalle comercial"),
    org_context: dict = Depends(require_permission("treasury.view_statements")),
    db: Session = Depends(get_db),
):
    """
    Estado de cuenta COMPLETO (unified account statement) de un tercero con saldo corrido.

    Incluye TODAS las operaciones que afectan el balance:
    - MoneyMovements confirmados y anulados (pagos, cobros, anticipos, etc.)
    - Compras liquidadas/canceladas (solo standalone, no doble partida)
    - Ventas liquidadas/canceladas (solo standalone, no doble partida)
    - Comisiones de compras standalone
    - Comisiones de ventas standalone
    - Doble partida (compra+venta simultanea) y sus comisiones

    Cada item incluye source/source_id/source_number para trazar al registro original.
    Si no se provee date_from, default a 90 dias atras.
    """
    from sqlalchemy import select as sa_select
    from sqlalchemy.orm import joinedload

    from app.models.purchase import CHARGE_TYPE_LABELS, Purchase, PurchaseCommission, PurchaseLine
    from app.models.sale import Sale, SaleCommission, SaleLine
    from app.models.double_entry import DoubleEntry, DoubleEntryLine

    org_id = org_context["organization_id"]

    # Default: ultimos 90 dias si no se provee date_from
    effective_date_from = date_from if date_from else (business_today() - timedelta(days=90))
    date_from_dt = datetime.combine(effective_date_from, dt_time.min, tzinfo=tz.utc)
    date_to_dt = datetime.combine(date_to + timedelta(days=1), dt_time.min, tzinfo=tz.utc) if date_to else None

    # --- Recopilar TODOS los eventos que afectan el balance del tercero ---
    # Cada evento: (transaction_date, real_ts, sort_key, filter_datetime, event_dict)
    #
    # 🔴 UN SOLO RELOJ POR POSICION DE LA LLAVE (doctrina #91 aplicada al orden).
    # La llave de orden es (dia de negocio, clase de evento, instante real, numero,
    # orden de emision) y cada posicion compara UNA sola cosa:
    #
    #   transaction_date: fecha de NEGOCIO (BusinessDate). En que dia cae el evento.
    #   sort_key:         clase. 0=operacion comercial, 1=tesoreria, 2=cancelacion/anulacion.
    #   real_ts:          🔴 instante REAL del servidor (`created_at`, `cancelled_at`,
    #                     `reverted_at`). NUNCA un BusinessDate.
    #
    # Hasta 2026-08-13 los eventos comerciales pasaban `liquidated_at` aca — que
    # PARECE timestamp y es una fecha de negocio (mediodia UTC, la trampa de #87).
    # Dos consecuencias: (a) todas las operaciones del mismo dia empataban exacto y
    # el orden lo decidia lo que Postgres devolviera sin ORDER BY (orden fisico);
    # (b) mezclar mediodia-UTC con `created_at` real hacia que un movimiento de
    # tesoreria del dia cayera antes o despues de las operaciones segun si se
    # digito antes o despues de las 7:00 a.m. de Bogota, y anulaba a `sort_key`,
    # que quedaba despues en la llave y nunca llegaba a decidir nada.
    events: list[tuple] = []

    # Campos nulos para vista "operations" en eventos que no son lineas de detalle
    _null_ops: dict = {}
    if view == "operations":
        _null_ops = {
            "vehicle_plate": None, "invoice_number": None,
            "material_code": None, "material_name": None,
            "quantity": None, "unit_price": None,
            "received_quantity": None, "is_line_item": False,
            "parent_source_id": None,
        }

    def _evt(txn_date, real_ts, sort_key, filter_dt=None, **kwargs):
        # Normalizar transaction_date a date (DoubleEntry.date es Date, otros son DateTime)
        if isinstance(txn_date, datetime):
            txn_date = txn_date.date()
        # Filtrar por fecha de negocio (no por timestamp servidor) para evitar
        # que operaciones liquidadas en otra timezone caigan fuera del rango
        if filter_dt is None:
            filter_dt = datetime.combine(txn_date, dt_time(12, 0), tzinfo=tz.utc)
        # Desempates finales, cuando el instante real tambien empata:
        #   numero de documento: N compras nacidas en UNA transaccion (#93 D14)
        #     comparten `created_at` al microsegundo. El consecutivo las ordena
        #     #3, #4, #5 — y de paso pega cada operacion con sus satelites
        #     (comision, retencion), que llevan el numero del padre.
        #   orden de emision: ultimo recurso. Conserva el orden natural de las
        #     lineas dentro de un documento (vista "operations") en vez de
        #     barajarlas por UUID, y garantiza que el orden sea TOTAL —
        #     reproducible entre corridas, que es lo que el golden compara.
        num = kwargs.get("source_number")
        events.append((txn_date, sort_key, real_ts,
                       num if isinstance(num, int) else 0,
                       len(events), filter_dt, kwargs))

    # 1. MoneyMovements confirmados y anulados
    allowed = _get_allowed_accounts(db, org_context)
    mm_query = sa_select(MoneyMovement).where(
        MoneyMovement.organization_id == org_id,
        MoneyMovement.third_party_id == third_party_id,
        MoneyMovement.status.in_(["confirmed", "annulled"]),
    )
    if allowed is not None:
        mm_query = mm_query.where(
            (MoneyMovement.account_id.in_(allowed)) | (MoneyMovement.account_id.is_(None))
        )
    for m in db.scalars(mm_query).all():
        direction = THIRD_PARTY_BALANCE_DIRECTION.get(m.movement_type, 0)
        _evt(m.date, m.created_at, 1, filter_dt=m.date,
             id=str(m.id), date=m.date.isoformat(),
             event_type=m.movement_type, description=m.description or "",
             amount=float(m.amount), direction=direction,
             status=m.status, reference_number=m.reference_number,
             movement_number=m.movement_number,
             source="money_movement", source_id=str(m.id), source_number=m.movement_number,
             **_null_ops)

    # 2. Compras liquidadas (standalone, no doble partida)
    # Proveedor: balance -= total_amount al liquidar
    purch_query = sa_select(Purchase).where(
        Purchase.organization_id == org_id,
        Purchase.supplier_id == third_party_id,
        Purchase.status.in_(["liquidated", "cancelled"]),
        Purchase.liquidated_at.isnot(None),
        Purchase.double_entry_id.is_(None),  # Excluir doble partida
    )
    if view == "operations":
        purch_query = purch_query.options(
            joinedload(Purchase.lines).joinedload(PurchaseLine.material)
        )
    for p in db.scalars(purch_query).unique().all():
        if view == "operations":
            # Una fila por linea de compra con detalle de material
            for line in p.lines:
                ops_fields = {
                    "vehicle_plate": p.vehicle_plate,
                    "invoice_number": p.invoice_number,
                    "material_code": line.material.code if line.material else None,
                    "material_name": line.material.name if line.material else None,
                    "quantity": float(line.quantity),
                    "unit_price": float(line.unit_price),
                    "received_quantity": None,
                    "is_line_item": True,
                    "parent_source_id": str(p.id),
                }
                # Posicionado en liquidated_at (fecha canonica de efecto
                # financiero, decision #42) — document_date conserva la fecha
                # del documento para mostrar ambas.
                _evt(p.liquidated_at, p.created_at, 0,
                     id=f"purchase-line-{line.id}", date=p.liquidated_at.isoformat(),
                     document_date=p.date.isoformat(),
                     event_type="purchase_liquidation",
                     description=f"Compra #{p.purchase_number} liquidada",
                     amount=float(line.total_price), direction=-1,
                     status="confirmed" if p.status == "liquidated" else "cancelled",
                     reference_number=None, movement_number=None,
                     source="purchase", source_id=str(p.id), source_number=p.purchase_number,
                     **ops_fields)
        else:
            _evt(p.liquidated_at, p.created_at, 0,
                 id=f"purchase-{p.id}", date=p.liquidated_at.isoformat(),
                 document_date=p.date.isoformat(),
                 event_type="purchase_liquidation",
                 description=f"Compra #{p.purchase_number} liquidada",
                 amount=float(p.total_amount), direction=-1,
                 status="confirmed" if p.status == "liquidated" else "cancelled",
                 reference_number=None, movement_number=None,
                 source="purchase", source_id=str(p.id), source_number=p.purchase_number)
        # Cancelacion siempre como evento unico (usa total para reversa).
        # Posicionada junto a su liquidacion (par adyacente, display-only:
        # los eventos annulled/cancelled no mueven el balance).
        if p.status == "cancelled" and p.cancelled_at:
            _evt(p.liquidated_at, p.cancelled_at, 2,
                 id=f"purchase-cancel-{p.id}", date=p.liquidated_at.isoformat(),
                 document_date=p.date.isoformat(),
                 event_type="purchase_cancellation",
                 description=f"Compra #{p.purchase_number} cancelada (reversa)",
                 amount=float(p.total_amount), direction=1,
                 status="annulled", reference_number=None, movement_number=None,
                 source="purchase", source_id=str(p.id), source_number=p.purchase_number,
                 **_null_ops)

    # 2b. Comisiones de compras standalone
    # Comisionista: balance -= commission_amount al liquidar
    purch_comm_query = (
        sa_select(PurchaseCommission, Purchase)
        .join(Purchase, PurchaseCommission.purchase_id == Purchase.id)
        .where(
            Purchase.organization_id == org_id,
            PurchaseCommission.third_party_id == third_party_id,
            Purchase.status.in_(["liquidated", "cancelled"]),
            Purchase.liquidated_at.isnot(None),
            Purchase.double_entry_id.is_(None),
        )
    )
    for comm, purch in db.execute(purch_comm_query).all():
        _charge_label = CHARGE_TYPE_LABELS.get(comm.charge_type, "Comisión")
        _evt(purch.liquidated_at, purch.created_at, 0,
             id=f"purch-commission-{comm.id}", date=purch.liquidated_at.isoformat(),
             document_date=purch.date.isoformat(),
             event_type="purchase_commission",
             description=f"{_charge_label} Compra #{purch.purchase_number}: {comm.concept}",
             amount=float(comm.commission_amount), direction=-1,
             # La comision NO tiene `reverted_at` propio (eso es de las
             # retenciones, 2c): su reversa la dispara el status de la COMPRA.
             status="confirmed" if purch.status == "liquidated" else "cancelled",
             reference_number=None, movement_number=None,
             source="purchase_commission", source_id=str(comm.id), source_number=purch.purchase_number,
             **_null_ops)
        if purch.status == "cancelled" and purch.cancelled_at:
            _evt(purch.liquidated_at, purch.cancelled_at, 2,
                 id=f"purch-comm-cancel-{comm.id}", date=purch.liquidated_at.isoformat(),
                 document_date=purch.date.isoformat(),
                 event_type="purchase_commission_cancellation",
                 description=f"Comision Compra #{purch.purchase_number} cancelada (reversa)",
                 amount=float(comm.commission_amount), direction=1,
                 status="annulled", reference_number=None, movement_number=None,
                 source="purchase_commission", source_id=str(comm.id), source_number=purch.purchase_number,
                 **_null_ops)

    # 2c. Retenciones de compras (SAC E2 D9) — eventos sinteticos, patron #70.
    # Sin ellos el saldo corrido diverge del vivo (clase de bug #55): el evento
    # compra carga −total al proveedor pero la liquidacion lo acredito NETO.
    from app.models.purchase_retention import PurchaseRetention
    _RET_LABELS = {"retefuente": "ReteFuente", "reteiva": "ReteIVA", "ica": "ICA"}

    def _ret_label(ret) -> str:
        label = _RET_LABELS.get(ret.retention_type, ret.retention_type)
        return f"{label} {ret.municipality}" if ret.municipality else label

    # Lado PROVEEDOR: +amount compensatorio en liquidated_at
    ret_supplier_query = (
        sa_select(PurchaseRetention, Purchase)
        .join(Purchase, PurchaseRetention.purchase_id == Purchase.id)
        .where(
            Purchase.organization_id == org_id,
            Purchase.supplier_id == third_party_id,
            Purchase.status.in_(["liquidated", "cancelled"]),
            Purchase.liquidated_at.isnot(None),
        )
    )
    # El estado del evento y el contra-evento siguen a la FILA (reverted_at),
    # no al status de la compra (fix QA addendum #93): una compra re-liquidada
    # (D20) queda 'liquidated' con filas viejas revertidas + filas nuevas
    # vivas — con el disparador por status, las revertidas se mostraban como
    # confirmadas y el statement divergia del saldo (#55). En canceladas el
    # comportamiento es identico al de siempre: el cancel SIEMPRE estampa
    # reverted_at (#75), asi que todas sus filas emiten su par evento+reversa.
    def _ret_reversal_desc(ret, purch) -> str:
        if purch.status == "cancelled":
            return (f"Retencion {_ret_label(ret)} Compra #{purch.purchase_number} "
                    "cancelada (reversa)")
        return (f"Retencion {_ret_label(ret)} Compra #{purch.purchase_number} "
                "revertida (des-liquidacion)")

    for ret, purch in db.execute(ret_supplier_query).all():
        _evt(purch.liquidated_at, purch.created_at, 0,
             id=f"purch-retention-sup-{ret.id}", date=purch.liquidated_at.isoformat(),
             document_date=purch.date.isoformat(),
             event_type="purchase_retention",
             description=f"Retencion {_ret_label(ret)} Compra #{purch.purchase_number}",
             amount=float(ret.amount), direction=1,
             status="confirmed" if ret.reverted_at is None else "cancelled",
             reference_number=None, movement_number=None,
             source="purchase_retention", source_id=str(ret.id), source_number=purch.purchase_number,
             **_null_ops)
        if ret.reverted_at is not None:
            _evt(purch.liquidated_at, ret.reverted_at, 2,
                 id=f"purch-ret-sup-cancel-{ret.id}", date=purch.liquidated_at.isoformat(),
                 document_date=purch.date.isoformat(),
                 event_type="purchase_retention_cancellation",
                 description=_ret_reversal_desc(ret, purch),
                 amount=float(ret.amount), direction=-1,
                 status="annulled", reference_number=None, movement_number=None,
                 source="purchase_retention", source_id=str(ret.id), source_number=purch.purchase_number,
                 **_null_ops)

    # Lado ENTIDAD "[Retenciones] X": −amount (le debemos la retencion a la DIAN/municipio)
    ret_entity_query = (
        sa_select(PurchaseRetention, Purchase)
        .join(Purchase, PurchaseRetention.purchase_id == Purchase.id)
        .where(
            Purchase.organization_id == org_id,
            PurchaseRetention.third_party_id == third_party_id,
            Purchase.status.in_(["liquidated", "cancelled"]),
            Purchase.liquidated_at.isnot(None),
        )
    )
    for ret, purch in db.execute(ret_entity_query).all():
        _evt(purch.liquidated_at, purch.created_at, 0,
             id=f"purch-retention-ent-{ret.id}", date=purch.liquidated_at.isoformat(),
             document_date=purch.date.isoformat(),
             event_type="purchase_retention",
             description=f"Retencion {_ret_label(ret)} Compra #{purch.purchase_number}",
             amount=float(ret.amount), direction=-1,
             status="confirmed" if ret.reverted_at is None else "cancelled",
             reference_number=None, movement_number=None,
             source="purchase_retention", source_id=str(ret.id), source_number=purch.purchase_number,
             **_null_ops)
        if ret.reverted_at is not None:
            _evt(purch.liquidated_at, ret.reverted_at, 2,
                 id=f"purch-ret-ent-cancel-{ret.id}", date=purch.liquidated_at.isoformat(),
                 document_date=purch.date.isoformat(),
                 event_type="purchase_retention_cancellation",
                 description=_ret_reversal_desc(ret, purch),
                 amount=float(ret.amount), direction=1,
                 status="annulled", reference_number=None, movement_number=None,
                 source="purchase_retention", source_id=str(ret.id), source_number=purch.purchase_number,
                 **_null_ops)

    # 3. Ventas liquidadas (standalone, no doble partida)
    # Cliente: balance += total_amount al liquidar
    sale_query = sa_select(Sale).where(
        Sale.organization_id == org_id,
        Sale.customer_id == third_party_id,
        Sale.status.in_(["liquidated", "cancelled"]),
        Sale.liquidated_at.isnot(None),
        Sale.double_entry_id.is_(None),  # Excluir doble partida
    )
    if view == "operations":
        sale_query = sale_query.options(
            joinedload(Sale.lines).joinedload(SaleLine.material)
        )
    for s in db.scalars(sale_query).unique().all():
        if view == "operations":
            # Una fila por linea de venta con detalle de material
            for line in s.lines:
                ops_fields = {
                    "vehicle_plate": s.vehicle_plate,
                    "invoice_number": s.invoice_number,
                    "material_code": line.material.code if line.material else None,
                    "material_name": line.material.name if line.material else None,
                    "quantity": float(line.quantity),
                    "unit_price": float(line.unit_price),
                    "received_quantity": float(line.received_quantity) if line.received_quantity else None,
                    "is_line_item": True,
                    "parent_source_id": str(s.id),
                }
                _evt(s.liquidated_at, s.created_at, 0,
                     id=f"sale-line-{line.id}", date=s.liquidated_at.isoformat(),
                     document_date=s.date.isoformat(),
                     event_type="sale_liquidation",
                     description=f"Venta #{s.sale_number} liquidada",
                     amount=float(line.total_price), direction=1,
                     status="confirmed" if s.status == "liquidated" else "cancelled",
                     reference_number=None, movement_number=None,
                     source="sale", source_id=str(s.id), source_number=s.sale_number,
                     **ops_fields)
        else:
            _evt(s.liquidated_at, s.created_at, 0,
                 id=f"sale-{s.id}", date=s.liquidated_at.isoformat(),
                 document_date=s.date.isoformat(),
                 event_type="sale_liquidation",
                 description=f"Venta #{s.sale_number} liquidada",
                 amount=float(s.total_amount), direction=1,
                 status="confirmed" if s.status == "liquidated" else "cancelled",
                 reference_number=None, movement_number=None,
                 source="sale", source_id=str(s.id), source_number=s.sale_number)
        # Cancelacion siempre como evento unico (usa total para reversa)
        if s.status == "cancelled" and s.cancelled_at:
            _evt(s.liquidated_at, s.cancelled_at, 2,
                 id=f"sale-cancel-{s.id}", date=s.liquidated_at.isoformat(),
                 document_date=s.date.isoformat(),
                 event_type="sale_cancellation",
                 description=f"Venta #{s.sale_number} cancelada (reversa)",
                 amount=float(s.total_amount), direction=-1,
                 status="annulled", reference_number=None, movement_number=None,
                 source="sale", source_id=str(s.id), source_number=s.sale_number,
                 **_null_ops)

    # Sale IDs que ya tienen commission_accrual (evitar duplicacion con seccion 4/6)
    sales_with_accrual = set(
        db.scalars(
            sa_select(MoneyMovement.sale_id).where(
                MoneyMovement.organization_id == org_id,
                MoneyMovement.movement_type == "commission_accrual",
                MoneyMovement.sale_id.isnot(None),
            )
        ).all()
    )

    # 4. Comisiones de ventas standalone SIN commission_accrual (compatibilidad ventas antiguas)
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
        if sale.id in sales_with_accrual:
            continue
        _evt(sale.liquidated_at, sale.created_at, 0,
             id=f"commission-{comm.id}", date=sale.liquidated_at.isoformat(),
             document_date=sale.date.isoformat(),
             event_type="sale_commission",
             description=f"Comision Venta #{sale.sale_number}: {comm.concept}",
             amount=float(comm.commission_amount), direction=1,
             status="confirmed" if sale.status == "liquidated" else "cancelled",
             reference_number=None, movement_number=None,
             source="commission", source_id=str(comm.id), source_number=sale.sale_number,
             **_null_ops)
        if sale.status == "cancelled" and sale.cancelled_at:
            _evt(sale.liquidated_at, sale.cancelled_at, 2,
                 id=f"commission-cancel-{comm.id}", date=sale.liquidated_at.isoformat(),
                 document_date=sale.date.isoformat(),
                 event_type="commission_cancellation",
                 description=f"Comision Venta #{sale.sale_number} cancelada (reversa)",
                 amount=float(comm.commission_amount), direction=-1,
                 status="annulled", reference_number=None, movement_number=None,
                 source="commission", source_id=str(comm.id), source_number=sale.sale_number,
                 **_null_ops)

    # 5. Doble partida — usa created_at como timestamp, Purchase/Sale para montos
    de_query = (
        sa_select(DoubleEntry)
        .options(joinedload(DoubleEntry.purchase), joinedload(DoubleEntry.sale))
        .where(
            DoubleEntry.organization_id == org_id,
            DoubleEntry.status.in_(["liquidated", "cancelled"]),
        )
        .where(
            (DoubleEntry.supplier_id == third_party_id)
            | (DoubleEntry.customer_id == third_party_id)
        )
    )
    if view == "operations":
        de_query = de_query.options(
            joinedload(DoubleEntry.lines).joinedload(DoubleEntryLine.material)
        )
    for de in db.scalars(de_query).unique().all():
        de_dt = de.created_at  # datetime del registro
        purchase_amount = float(de.purchase.total_amount) if de.purchase else 0
        sale_amount = float(de.sale.total_amount) if de.sale else 0
        is_active = de.status == "liquidated"
        evt_status = "confirmed" if is_active else "cancelled"
        de_date_iso = datetime.combine(de.date, dt_time(12, 0), tzinfo=tz.utc).isoformat()
        # Fecha canonica de efecto financiero (decision #42); fallback a la
        # fecha del documento para DPs canceladas sin liquidar (liquidated_at NULL)
        de_liq_dt = de.liquidated_at or datetime.combine(de.date, dt_time(12, 0), tzinfo=tz.utc)
        de_liq_iso = de_liq_dt.isoformat()
        de_vehicle = getattr(de, "vehicle_plate", None) or (de.purchase.vehicle_plate if de.purchase else None) or (de.sale.vehicle_plate if de.sale else None)

        if view == "operations":
            # Una fila por linea con detalle de material
            for line in de.lines:
                base_ops = {
                    "vehicle_plate": de_vehicle,
                    "invoice_number": de.invoice_number if hasattr(de, "invoice_number") else None,
                    "material_code": line.material.code if line.material else None,
                    "material_name": line.material.name if line.material else None,
                    "quantity": float(line.quantity),
                    "received_quantity": None,
                    "is_line_item": True,
                    "parent_source_id": str(de.id),
                }
                # Como proveedor — precio de compra
                if de.supplier_id == third_party_id:
                    _evt(de_liq_dt, de_dt, 0,
                         id=f"de-supplier-line-{line.id}", date=de_liq_iso, document_date=de_date_iso,
                         event_type="double_entry_purchase",
                         description=f"Doble Partida #{de.double_entry_number} (como proveedor)",
                         amount=float(line.quantity * line.purchase_unit_price), direction=-1,
                         status=evt_status, reference_number=None, movement_number=None,
                         source="double_entry", source_id=str(de.id), source_number=de.double_entry_number,
                         unit_price=float(line.purchase_unit_price), **base_ops)
                # Como cliente — precio de venta
                if de.customer_id == third_party_id:
                    _evt(de_liq_dt, de_dt, 0,
                         id=f"de-customer-line-{line.id}", date=de_liq_iso, document_date=de_date_iso,
                         event_type="double_entry_sale",
                         description=f"Doble Partida #{de.double_entry_number} (como cliente)",
                         amount=float(line.quantity * line.sale_unit_price), direction=1,
                         status=evt_status, reference_number=None, movement_number=None,
                         source="double_entry", source_id=str(de.id), source_number=de.double_entry_number,
                         unit_price=float(line.sale_unit_price), **base_ops)
        else:
            # Como proveedor
            if de.supplier_id == third_party_id:
                _evt(de_liq_dt, de_dt, 0,
                     id=f"de-supplier-{de.id}", date=de_liq_iso, document_date=de_date_iso,
                     event_type="double_entry_purchase",
                     description=f"Doble Partida #{de.double_entry_number} (como proveedor)",
                     amount=purchase_amount, direction=-1,
                     status=evt_status, reference_number=None, movement_number=None,
                     source="double_entry", source_id=str(de.id), source_number=de.double_entry_number)
            # Como cliente
            if de.customer_id == third_party_id:
                _evt(de_liq_dt, de_dt, 0,
                     id=f"de-customer-{de.id}", date=de_liq_iso, document_date=de_date_iso,
                     event_type="double_entry_sale",
                     description=f"Doble Partida #{de.double_entry_number} (como cliente)",
                     amount=sale_amount, direction=1,
                     status=evt_status, reference_number=None, movement_number=None,
                     source="double_entry", source_id=str(de.id), source_number=de.double_entry_number)

        # Cancelacion reversa siempre como evento unico (usar updated_at como proxy de cancelled_at)
        if de.status == "cancelled":
            cancel_dt = de.updated_at or de_dt
            if de.supplier_id == third_party_id:
                _evt(de_liq_dt, cancel_dt, 2,
                     id=f"de-cancel-supplier-{de.id}", date=de_liq_iso, document_date=de_date_iso,
                     event_type="double_entry_cancellation",
                     description=f"Doble Partida #{de.double_entry_number} cancelada (reversa proveedor)",
                     amount=purchase_amount, direction=1,
                     status="annulled", reference_number=None, movement_number=None,
                     source="double_entry", source_id=str(de.id), source_number=de.double_entry_number,
                     **_null_ops)
            if de.customer_id == third_party_id:
                _evt(de_liq_dt, cancel_dt, 2,
                     id=f"de-cancel-customer-{de.id}", date=de_liq_iso, document_date=de_date_iso,
                     event_type="double_entry_cancellation",
                     description=f"Doble Partida #{de.double_entry_number} cancelada (reversa cliente)",
                     amount=sale_amount, direction=-1,
                     status="annulled", reference_number=None, movement_number=None,
                     source="double_entry", source_id=str(de.id), source_number=de.double_entry_number,
                     **_null_ops)

    # 6. Comisiones de doble partida
    de_comm_query = (
        sa_select(SaleCommission, Sale, DoubleEntry)
        .join(Sale, SaleCommission.sale_id == Sale.id)
        .join(DoubleEntry, DoubleEntry.sale_id == Sale.id)
        .where(
            DoubleEntry.organization_id == org_id,
            SaleCommission.third_party_id == third_party_id,
            DoubleEntry.status.in_(["liquidated", "cancelled"]),
        )
    )
    for comm, sale, de in db.execute(de_comm_query).all():
        if sale.id in sales_with_accrual:
            continue
        de_dt = de.created_at
        is_active = de.status == "liquidated"
        # Redefinir por loop: este bloque NO comparte scope de iteracion con el
        # bloque 5 (fallback a fecha documento si la DP nunca se liquido)
        de_doc_iso = datetime.combine(de.date, dt_time(12, 0), tzinfo=tz.utc).isoformat()
        de_liq_dt = de.liquidated_at or datetime.combine(de.date, dt_time(12, 0), tzinfo=tz.utc)
        de_liq_iso = de_liq_dt.isoformat()
        _evt(de_liq_dt, de_dt, 0,
             id=f"de-commission-{comm.id}", date=de_liq_iso, document_date=de_doc_iso,
             event_type="double_entry_commission",
             description=f"Comision DP #{de.double_entry_number}: {comm.concept}",
             amount=float(comm.commission_amount), direction=1,
             status="confirmed" if is_active else "cancelled",
             reference_number=None, movement_number=None,
             source="commission", source_id=str(comm.id), source_number=de.double_entry_number,
             **_null_ops)
        if de.status == "cancelled":
            cancel_dt = de.updated_at or de_dt
            _evt(de_liq_dt, cancel_dt, 2,
                 id=f"de-comm-cancel-{comm.id}", date=de_liq_iso, document_date=de_doc_iso,
                 event_type="double_entry_commission_cancellation",
                 description=f"Comision DP #{de.double_entry_number} cancelada (reversa)",
                 amount=float(comm.commission_amount), direction=-1,
                 status="annulled", reference_number=None, movement_number=None,
                 source="commission", source_id=str(comm.id), source_number=de.double_entry_number,
                 **_null_ops)

    # --- Ordenar: dia de negocio, clase de evento, instante real, numero, emision ---
    # Los 5 primeros elementos SON la llave, en orden. Orden TOTAL: no quedan
    # empates, asi que dos corridas sobre los mismos datos dan la misma lista.
    events.sort(key=lambda e: e[:5])

    # --- Obtener initial_balance del tercero ---
    tp = db.query(ThirdParty).filter(
        ThirdParty.id == third_party_id,
        ThirdParty.organization_id == org_id,
    ).first()
    initial = tp.initial_balance if tp and tp.initial_balance else Decimal("0")

    # --- Calcular balance corrido (arranca desde initial_balance) ---
    balance = initial
    opening_balance = initial
    all_items = []
    in_range_items = []

    # Primera pasada: calcular el saldo corrido sobre TODOS los eventos.
    # Los movimientos ANTERIORES a la ventana (date_from_dt) se absorben en
    # opening_balance (= saldo de apertura real del periodo visible) y NO se
    # listan. Asi el saldo corrido queda trazable aunque el default de 90 dias
    # deje operaciones fuera de la vista (sin esto, el saldo "saltaba" sin
    # mostrar el movimiento que lo movio).
    for *_, filter_dt, evt in events:
        if evt["status"] not in ("annulled", "cancelled"):
            balance += Decimal(str(evt["amount"])) * evt["direction"]
        evt["balance_after"] = float(balance)

        if date_from_dt and filter_dt < date_from_dt:
            opening_balance = balance
            continue
        if date_to_dt and filter_dt >= date_to_dt:
            continue

        in_range_items.append(evt)

    # Fila sintetica de saldo inicial: refleja el SALDO DE APERTURA de la ventana
    # (opening_balance, que ya incluye lo ocurrido antes del rango), NO el
    # initial_balance crudo del tercero. Solo cuando el usuario no filtro por fecha.
    if opening_balance != 0 and not date_from:
        all_items.append({
            "id": f"initial-{third_party_id}",
            "date": tp.created_at.isoformat() if tp.created_at else None,
            "event_type": "initial_balance",
            "description": "Saldo Inicial",
            "amount": float(abs(opening_balance)),
            "direction": 1 if opening_balance > 0 else -1,
            "balance_after": float(opening_balance),
            "status": "confirmed",
            "reference_number": None,
            "movement_number": None,
            "source": "system",
            "source_id": None,
            "source_number": None,
        })

    all_items.extend(in_range_items)

    # --- Paginar ---
    total = len(all_items)
    page = all_items[skip:skip + limit]

    return {
        "items": page,
        "total": total,
        "skip": skip,
        "limit": limit,
        "opening_balance": float(opening_balance) if date_from_dt else None,
        # Saldo actual del tercero, fresco desde BD — el KPI "Saldo Contable" debe
        # usar este y no el current_balance de la lista de terceros (cacheada en el
        # front), que se desfasa cuando hay movimientos recientes sin invalidar cache.
        "current_balance": float(tp.current_balance) if tp and tp.current_balance is not None else 0.0,
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
    org_context: dict = Depends(require_permission("treasury.create_movements")),
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
    return _to_response(mov, db)


@router.get("/{movement_id}/evidence")
def download_evidence(
    movement_id: UUID,
    org_context: dict = Depends(require_permission("treasury.view_movements")),
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
    org_context: dict = Depends(require_permission("treasury.create_movements")),
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
    return _to_response(mov, db)


@router.get("/{movement_id}", response_model=MoneyMovementResponse)
def get_movement(
    movement_id: UUID,
    org_context: dict = Depends(require_permission("treasury.view_movements")),
    db: Session = Depends(get_db),
):
    """Obtener un movimiento por ID."""
    movement = money_movement.get_or_404(db, movement_id, org_context["organization_id"])
    return _to_response(movement, db)


# ---------------------------------------------------------------------------
# Anulacion
# ---------------------------------------------------------------------------

@router.post("/{movement_id}/annul", response_model=AnnulMovementResponse)
def annul_movement(
    movement_id: UUID,
    data: AnnulMovementRequest,
    org_context: dict = Depends(require_permission("treasury.create_movements")),
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
    response = _to_response(loaded, db)
    return {**response, "warnings": warnings}


# ---------------------------------------------------------------------------
# Edicion de clasificacion
# ---------------------------------------------------------------------------

@router.patch("/{movement_id}/classification", response_model=MoneyMovementResponse)
def update_movement_classification(
    movement_id: UUID,
    data: UpdateClassificationRequest,
    org_context: dict = Depends(require_permission("treasury.edit_classification")),
    db: Session = Depends(get_db),
):
    """
    Editar clasificacion de un movimiento tipo gasto.

    Solo permite modificar: expense_category_id, business_unit_id, applicable_business_unit_ids.
    Solo para movimientos confirmed de tipo: expense, expense_accrual, provision_expense,
    deferred_expense, depreciation_expense.
    """
    movement = money_movement.update_classification(
        db=db,
        movement_id=movement_id,
        organization_id=org_context["organization_id"],
        expense_category_id=data.expense_category_id,
        business_unit_id=data.business_unit_id,
        applicable_business_unit_ids=(
            [str(uid) for uid in data.applicable_business_unit_ids]
            if data.applicable_business_unit_ids else None
        ),
    )
    loaded = money_movement.get(db, movement.id, org_context["organization_id"])
    return _to_response(loaded, db)
