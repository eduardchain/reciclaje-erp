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
from app.schemas.purchase import (
    PaginatedPurchaseResponse,
    PurchaseCreate,
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

def _enrich_purchase_response(purchase: Purchase) -> dict:
    """
    Enrich purchase object with joined data for response.
    
    Assumes purchase was loaded with proper joinedload options.
    """
    return {
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
    }


# ============================================================================
# Endpoints
# ============================================================================

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
        purchase = purchase_service.create(
            db=db,
            obj_in=purchase_in,
            organization_id=org_context["organization_id"],
        )
        
        # Enrich with joined data
        response_data = _enrich_purchase_response(purchase)
        
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
        # Convert date to datetime if provided
        date_from_dt = datetime.combine(date_from, datetime.min.time()) if date_from else None
        date_to_dt = datetime.combine(date_to, datetime.max.time()) if date_to else None
        
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
        items = [PurchaseResponse(**_enrich_purchase_response(p)) for p in purchases]
        
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
        
        items = [PurchaseResponse(**_enrich_purchase_response(p)) for p in purchases]
        
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
    
    response_data = _enrich_purchase_response(purchase)
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
        
        items = [PurchaseResponse(**_enrich_purchase_response(p)) for p in purchases]
        
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
    
    response_data = _enrich_purchase_response(purchase)
    return PurchaseResponse(**response_data)


@router.patch(
    "/{purchase_id}/liquidate",
    response_model=PurchaseResponse,
    summary="Liquidate purchase (2-step workflow)",
    description="""
    Liquidate a registered purchase (complete payment).
    
    **Requirements:**
    - Purchase status must be 'registered'
    - Payment account must have sufficient funds
    
    **Effects:**
    - Changes purchase status to 'paid'
    - Deducts total_amount from payment_account
    - Sets payment_account_id on purchase
    
    **Use case:** 
    For 2-step workflow where purchase is created first, then paid later.
    """,
)
async def liquidate_purchase(
    purchase_id: UUID,
    liquidate_data: PurchaseLiquidateRequest,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> PurchaseResponse:
    """Liquidate a purchase (2-step workflow)."""
    try:
        purchase = purchase_service.liquidate(
            db=db,
            purchase_id=purchase_id,
            payment_account_id=liquidate_data.payment_account_id,
            organization_id=org_context["organization_id"],
        )
        
        response_data = _enrich_purchase_response(purchase)
        
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
    - Purchase status must NOT be 'paid'
    - Sufficient stock must exist to reverse movements
    
    **Effects:**
    - Changes purchase status to 'cancelled'
    - Creates reversal inventory movements
    - Reverts material stock
    - Reverts supplier balance
    
    **Note:** 
    Cannot cancel paid purchases. Create a reversal transaction instead.
    
    **Warning:**
    Does NOT revert average cost (TODO: Phase 3).
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
        )
        
        response_data = _enrich_purchase_response(purchase)
        
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
