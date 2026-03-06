"""
REST API endpoints for purchase management.

Supports 1-step and 2-step purchase workflows:
- 1-step: POST with auto_liquidate=True
- 2-step: POST then PATCH /liquidate
"""
import logging
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import cast, or_, String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_required_org_context
from app.models.purchase import Purchase
from app.models.user import User
from app.schemas.purchase import (
    PaginatedPurchaseResponse,
    PurchaseCreate,
    PurchaseFullUpdate,
    PurchaseLiquidateRequest,
    PurchaseResponse,
    PurchaseUpdate,
)
from app.services.purchase import purchase as purchase_service

# Setup logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


# ============================================================================
# Helper Functions
# ============================================================================

def _enrich_purchase_response(purchase: Purchase, db: Session = None) -> dict:
    """
    Enrich purchase object with joined data for response.

    Assumes purchase was loaded with proper joinedload options.
    """
    data = {
        **purchase.__dict__,
        "supplier_name": purchase.supplier.name if purchase.supplier else None,
        "payment_account_name": purchase.payment_account.name if purchase.payment_account else None,
        "lines": [
            {
                **line.__dict__,
                "material_code": line.material.code if line.material else None,
                "material_name": line.material.name if line.material else None,
                "warehouse_name": line.warehouse.name if line.warehouse else None,
            }
            for line in purchase.lines
        ],
        "created_by_name": None,
        "liquidated_by_name": None,
        "cancelled_by_name": None,
        "updated_by_name": None,
    }

    # Resolver nombres de usuarios de auditoria
    if db:
        user_ids = {uid for uid in [
            purchase.created_by,
            purchase.liquidated_by,
            getattr(purchase, 'cancelled_by', None),
            getattr(purchase, 'updated_by', None),
        ] if uid}
        if user_ids:
            users = {u.id: u.full_name or u.email for u in db.query(User).filter(User.id.in_(user_ids)).all()}
            data["created_by_name"] = users.get(purchase.created_by)
            data["liquidated_by_name"] = users.get(purchase.liquidated_by)
            data["cancelled_by_name"] = users.get(getattr(purchase, 'cancelled_by', None))
            data["updated_by_name"] = users.get(getattr(purchase, 'updated_by', None))

    return data


# ============================================================================
# Endpoints
# ============================================================================

@router.get(
    "/check-duplicate",
    summary="Check for duplicate purchases",
    description="Verifica si ya existen compras del mismo proveedor en la misma fecha (RN-COMP-02).",
)
async def check_duplicate(
    supplier_id: UUID = Query(...),
    date: datetime = Query(...),
    total_quantity: Optional[float] = Query(None, description="Cantidad total para comparacion ±20%"),
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> dict:
    """Retorna la cantidad de compras existentes del mismo proveedor en la misma fecha (y cantidad similar si se proporciona)."""
    from decimal import Decimal
    qty = Decimal(str(total_quantity)) if total_quantity is not None else None
    count = purchase_service.check_duplicate(
        db=db,
        supplier_id=supplier_id,
        date=date,
        organization_id=org_context["organization_id"],
        total_quantity=qty,
    )
    return {"count": count}


@router.post(
    "",
    response_model=PurchaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new purchase",
    description="""
    Create a new purchase with support for 1-step and 2-step workflows.
    
    **1-step workflow (auto-liquidate):**
    - Set `auto_liquidate=True`
    - Provide `payment_account_id`
    - Purchase is created and immediately liquidated (status='paid')
    
    **2-step workflow:**
    - Set `auto_liquidate=False` (default)
    - Purchase is created with status='registered'
    - Use PATCH /purchases/{id}/liquidate later to complete payment
    
    **Effects:**
    - Generates sequential purchase_number
    - Updates material stock and average cost (weighted average)
    - Creates inventory movements (audit trail)
    - Updates supplier balance (increases debt)
    - If auto_liquidate: Deducts from payment account
    """,
)
async def create_purchase(
    purchase_in: PurchaseCreate,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> PurchaseResponse:
    """Create a new purchase (1-step or 2-step workflow)."""
    try:
        purchase, warnings = purchase_service.create(
            db=db,
            obj_in=purchase_in,
            organization_id=org_context["organization_id"],
            user_id=org_context["user_id"],
        )

        # Enrich with joined data
        response_data = _enrich_purchase_response(purchase, db)
        if warnings:
            response_data["warnings"] = warnings
        
        logger.info(
            f"Purchase #{purchase.purchase_number} created by user {org_context['user_id']} "
            f"in org {org_context['organization_id']}"
        )
        
        return PurchaseResponse(**response_data)
    
    except HTTPException:
        raise  # Re-raise HTTP exceptions from service
    
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error creating purchase: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate purchase number. Please retry.",
        )
    
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error creating purchase: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please contact support.",
        )


@router.get(
    "",
    response_model=PaginatedPurchaseResponse,
    summary="List purchases",
    description="""
    List all purchases for the organization with pagination and filters.
    
    **Filters:**
    - `status`: Filter by purchase status (registered, paid, cancelled)
    - `supplier_id`: Filter by supplier
    - `date_from`: Filter purchases on or after this date
    - `date_to`: Filter purchases on or before this date
    - `search`: Search in purchase number, supplier name, or notes
    
    **Pagination:**
    - `skip`: Number of records to skip (default: 0)
    - `limit`: Maximum records to return (default: 100, max: 1000)
    
    Results are ordered by date (newest first), then by purchase number (descending).
    """,
)
async def list_purchases(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    status: Optional[str] = Query(None, description="Filter by status: registered, paid, cancelled"),
    supplier_id: Optional[UUID] = Query(None, description="Filter by supplier UUID"),
    date_from: Optional[date] = Query(None, description="Filter purchases on or after this date"),
    date_to: Optional[date] = Query(None, description="Filter purchases on or before this date"),
    search: Optional[str] = Query(None, description="Search in purchase number, supplier name, notes"),
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> PaginatedPurchaseResponse:
    """List purchases with filters and pagination."""
    try:
        # Convert date to datetime with timezone (covering full day in UTC-5 Colombia)
        # Colombia is UTC-5, so to capture all purchases on a given local date,
        # we extend the range by +1 day on date_to to cover timezone offsets
        from datetime import time as dt_time, timezone as tz, timedelta
        if date_from:
            date_from_dt = datetime.combine(date_from, dt_time.min, tzinfo=tz.utc)
        else:
            date_from_dt = None
        if date_to:
            # Include the full day even with timezone offsets (up to UTC+14)
            date_to_dt = datetime.combine(date_to + timedelta(days=1), dt_time.min, tzinfo=tz.utc)
        else:
            date_to_dt = None
        
        purchases, total = purchase_service.get_multi(
            db=db,
            organization_id=org_context["organization_id"],
            skip=skip,
            limit=limit,
            status=status,
            supplier_id=supplier_id,
            date_from=date_from_dt,
            date_to=date_to_dt,
            search=search,
        )
        
        # Enrich each purchase with joined data
        items = [PurchaseResponse(**_enrich_purchase_response(p, db)) for p in purchases]
        
        return PaginatedPurchaseResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
        )
    
    except Exception as e:
        logger.error(f"Error listing purchases: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please contact support.",
        )


@router.get(
    "/pending",
    response_model=PaginatedPurchaseResponse,
    summary="List purchases pending liquidation",
    description="""
    List all purchases with status='registered' (pending liquidation).
    
    These purchases have been created but not yet paid.
    Use PATCH /purchases/{id}/liquidate to complete payment.
    """,
)
async def list_pending_purchases(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> PaginatedPurchaseResponse:
    """List purchases pending liquidation (status='registered')."""
    try:
        purchases, total = purchase_service.get_multi(
            db=db,
            organization_id=org_context["organization_id"],
            skip=skip,
            limit=limit,
            status="registered",
        )
        
        items = [PurchaseResponse(**_enrich_purchase_response(p, db)) for p in purchases]
        
        return PaginatedPurchaseResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
        )
    
    except Exception as e:
        logger.error(f"Error listing pending purchases: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please contact support.",
        )


@router.get(
    "/by-number/{purchase_number}",
    response_model=PurchaseResponse,
    summary="Get purchase by number",
    description="Get a single purchase by its sequential purchase_number.",
)
async def get_purchase_by_number(
    purchase_number: int,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> PurchaseResponse:
    """Get purchase by purchase_number."""
    purchase = purchase_service.get_by_number(
        db=db,
        purchase_number=purchase_number,
        organization_id=org_context["organization_id"],
    )
    
    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase #{purchase_number} not found",
        )
    
    # Load with eager loading
    purchase = purchase_service.get(
        db=db,
        purchase_id=purchase.id,
        organization_id=org_context["organization_id"],
    )
    
    response_data = _enrich_purchase_response(purchase, db)
    return PurchaseResponse(**response_data)


@router.get(
    "/supplier/{supplier_id}",
    response_model=PaginatedPurchaseResponse,
    summary="List purchases by supplier",
    description="List all purchases from a specific supplier.",
)
async def list_purchases_by_supplier(
    supplier_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> PaginatedPurchaseResponse:
    """List purchases by supplier."""
    try:
        purchases, total = purchase_service.get_multi(
            db=db,
            organization_id=org_context["organization_id"],
            skip=skip,
            limit=limit,
            supplier_id=supplier_id,
        )
        
        items = [PurchaseResponse(**_enrich_purchase_response(p, db)) for p in purchases]
        
        return PaginatedPurchaseResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
        )
    
    except Exception as e:
        logger.error(f"Error listing purchases by supplier: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please contact support.",
        )


@router.get(
    "/{purchase_id}",
    response_model=PurchaseResponse,
    summary="Get purchase by ID",
    description="""
    Get a single purchase by its UUID.
    
    Returns full details including:
    - Purchase header (number, date, total, status, etc.)
    - All purchase lines with material and warehouse details
    - Supplier information
    - Payment account information (if liquidated)
    """,
)
async def get_purchase(
    purchase_id: UUID,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> PurchaseResponse:
    """Get a single purchase by ID."""
    purchase = purchase_service.get(
        db=db,
        purchase_id=purchase_id,
        organization_id=org_context["organization_id"],
    )
    
    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase not found",
        )
    
    response_data = _enrich_purchase_response(purchase, db)
    return PurchaseResponse(**response_data)


@router.patch(
    "/{purchase_id}",
    response_model=PurchaseResponse,
    summary="Update purchase",
    description="""
    Edicion completa de compra: metadata, proveedor y/o lineas.

    **Requisitos:**
    - La compra debe tener status='registered'
    - No puede estar vinculada a una doble partida

    **Estrategia para lineas:**
    Si se envian lineas, se reemplazan TODAS las existentes usando
    la estrategia Revert-and-Reapply (revertir inventario antiguo,
    aplicar inventario nuevo).

    **Campos opcionales:** Solo se actualizan los campos enviados.
    """,
)
async def update_purchase(
    purchase_id: UUID,
    purchase_in: PurchaseFullUpdate,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> PurchaseResponse:
    """Editar compra registrada (metadata + proveedor + lineas)."""
    try:
        purchase = purchase_service.update(
            db=db,
            purchase_id=purchase_id,
            obj_in=purchase_in,
            organization_id=org_context["organization_id"],
            user_id=org_context["user_id"],
        )

        response_data = _enrich_purchase_response(purchase, db)

        logger.info(
            f"Purchase #{purchase.purchase_number} updated by user {org_context['user_id']}"
        )

        return PurchaseResponse(**response_data)

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error updating purchase: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please contact support.",
        )


@router.patch(
    "/{purchase_id}/liquidate",
    response_model=PurchaseResponse,
    summary="Liquidar compra (confirmar precios)",
    description="""
    Liquidar una compra registrada: confirmar precios, mover stock a liquidado,
    recalcular costo promedio, actualizar saldo del proveedor.

    **Requirements:**
    - Purchase status must be 'registered'
    - All line prices must be > 0 (V-LIQ-01)

    **Effects:**
    - Changes purchase status to 'liquidated'
    - Moves stock from transit to liquidated
    - Recalculates material average cost
    - Updates supplier balance (debt)

    **Note:** Payment to supplier is a separate operation via MoneyMovement.
    """,
)
async def liquidate_purchase(
    purchase_id: UUID,
    liquidate_data: PurchaseLiquidateRequest,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> PurchaseResponse:
    """Liquidar compra (confirmar precios, mover stock, actualizar saldo)."""
    try:
        # Convertir line updates a lista de dicts si se proporcionan
        line_updates = None
        if liquidate_data.lines:
            line_updates = [
                {"line_id": lu.line_id, "unit_price": lu.unit_price}
                for lu in liquidate_data.lines
            ]

        purchase = purchase_service.liquidate(
            db=db,
            purchase_id=purchase_id,
            organization_id=org_context["organization_id"],
            user_id=org_context["user_id"],
            line_updates=line_updates,
        )
        
        response_data = _enrich_purchase_response(purchase, db)
        
        logger.info(
            f"Purchase #{purchase.purchase_number} liquidated by user {org_context['user_id']}"
        )
        
        return PurchaseResponse(**response_data)
    
    except HTTPException:
        raise  # Re-raise HTTP exceptions from service
    
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error liquidating purchase: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please contact support.",
        )


@router.patch(
    "/{purchase_id}/cancel",
    response_model=PurchaseResponse,
    summary="Cancel purchase",
    description="""
    Cancel a purchase and reverse all effects.

    **Requirements:**
    - Purchase status must be 'registered' or 'paid'
    - For registered: sufficient stock must exist to reverse
    - For paid: stock reversal from liquidated bucket + refund to payment account

    **Effects:**
    - Changes purchase status to 'cancelled'
    - Creates reversal inventory movements
    - Reverts material stock (transit for registered, liquidated for paid)
    - Reverts supplier balance
    - If paid: returns funds to payment account

    **Warning:**
    Does NOT revert average cost.
    """,
)
async def cancel_purchase(
    purchase_id: UUID,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> PurchaseResponse:
    """Cancel a purchase and reverse effects."""
    try:
        purchase = purchase_service.cancel(
            db=db,
            purchase_id=purchase_id,
            organization_id=org_context["organization_id"],
            user_id=org_context["user_id"],
        )
        
        response_data = _enrich_purchase_response(purchase, db)
        
        logger.info(
            f"Purchase #{purchase.purchase_number} cancelled by user {org_context['user_id']}"
        )
        
        return PurchaseResponse(**response_data)
    
    except HTTPException:
        raise  # Re-raise HTTP exceptions from service
    
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error cancelling purchase: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please contact support.",
        )
