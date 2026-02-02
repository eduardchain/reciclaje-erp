"""
REST API endpoints for sales management.

Supports 1-step and 2-step sale workflows:
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
from app.models.sale import Sale
from app.schemas.sale import (
    PaginatedSaleResponse,
    SaleCreate,
    SaleLiquidateRequest,
    SaleResponse,
    SaleUpdate,
)
from app.services.sale import crud_sale

# Setup logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


# ============================================================================
# Helper Functions
# ============================================================================

def _enrich_sale_response(sale: Sale) -> dict:
    """
    Enrich sale object with joined data for response.
    
    Assumes sale was loaded with proper joinedload options.
    """
    return {
        **sale.__dict__,
        "customer_name": sale.customer.name if sale.customer else None,
        "warehouse_name": sale.warehouse.name if sale.warehouse else None,
        "payment_account_name": sale.payment_account.name if sale.payment_account else None,
        "total_profit": float(sale.calculate_total_profit()),
        "lines": [
            {
                **line.__dict__,
                "material_code": line.material.code if line.material else None,
                "material_name": line.material.name if line.material else None,
                "profit": float(line.calculate_profit()),
            }
            for line in sale.lines
        ],
        "commissions": [
            {
                **comm.__dict__,
                "third_party_name": comm.third_party.name if comm.third_party else None,
            }
            for comm in sale.commissions
        ],
    }


# ============================================================================
# Endpoints
# ============================================================================

@router.post(
    "",
    response_model=SaleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new sale",
    description="""
    Create a new sale with support for 1-step and 2-step workflows.
    
    **1-step workflow (auto-liquidate):**
    - Set `auto_liquidate=True`
    - Provide `payment_account_id`
    - Sale is created and immediately liquidated (status='paid')
    
    **2-step workflow:**
    - Set `auto_liquidate=False` (default)
    - Sale is created with status='registered'
    - Use PATCH /sales/{id}/liquidate later to complete payment
    
    **Effects:**
    - Generates sequential sale_number
    - Validates stock availability (blocks if insufficient)
    - Updates material stock (decreases)
    - Captures unit_cost for profit calculation
    - Creates inventory movements (audit trail)
    - Updates customer balance (increases debt)
    - Creates commissions (if provided)
    - If auto_liquidate: Credits payment account, pays commissions
    """,
)
async def create_sale(
    sale_in: SaleCreate,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> SaleResponse:
    """Create a new sale (1-step or 2-step workflow)."""
    try:
        sale = crud_sale.create(
            db=db,
            obj_in=sale_in,
            organization_id=org_context["organization_id"],
        )
        
        db.commit()
        db.refresh(sale)
        
        # Reload with eager loading to get all relationships
        sale = crud_sale.get(
            db=db,
            sale_id=sale.id,
            organization_id=org_context["organization_id"],
        )
        
        # Enrich with joined data
        response_data = _enrich_sale_response(sale)
        
        logger.info(
            f"Sale #{sale.sale_number} created by user {org_context['user_id']} "
            f"in org {org_context['organization_id']}"
        )
        
        return SaleResponse(**response_data)
    
    except HTTPException:
        db.rollback()
        raise  # Re-raise HTTP exceptions from service
    
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error creating sale: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate sale number. Please retry.",
        )
    
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error creating sale: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please contact support.",
        )


@router.get(
    "",
    response_model=PaginatedSaleResponse,
    summary="List sales",
    description="""
    List all sales for the organization with pagination and filters.
    
    **Filters:**
    - `status`: Filter by sale status (registered, paid, cancelled)
    - `customer_id`: Filter by customer
    - `warehouse_id`: Filter by warehouse
    - `date_from`: Filter sales on or after this date
    - `date_to`: Filter sales on or before this date
    - `search`: Search in sale number, customer name, notes, vehicle_plate, invoice_number
    
    **Pagination:**
    - `skip`: Number of records to skip (default: 0)
    - `limit`: Maximum records to return (default: 100, max: 1000)
    
    Results are ordered by date (newest first), then by sale number (descending).
    """,
)
async def list_sales(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    status: Optional[str] = Query(None, description="Filter by status: registered, paid, cancelled"),
    customer_id: Optional[UUID] = Query(None, description="Filter by customer UUID"),
    warehouse_id: Optional[UUID] = Query(None, description="Filter by warehouse UUID"),
    date_from: Optional[date] = Query(None, description="Filter sales on or after this date"),
    date_to: Optional[date] = Query(None, description="Filter sales on or before this date"),
    search: Optional[str] = Query(None, description="Search in sale number, customer name, notes, vehicle_plate, invoice_number"),
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> PaginatedSaleResponse:
    """List sales with filters and pagination."""
    try:
        # Convert date to datetime if provided
        date_from_dt = datetime.combine(date_from, datetime.min.time()) if date_from else None
        date_to_dt = datetime.combine(date_to, datetime.max.time()) if date_to else None
        
        sales, total = crud_sale.get_multi(
            db=db,
            organization_id=org_context["organization_id"],
            skip=skip,
            limit=limit,
            status=status,
            customer_id=customer_id,
            warehouse_id=warehouse_id,
            date_from=date_from_dt,
            date_to=date_to_dt,
            search=search,
        )
        
        # Enrich each sale with joined data
        items = [SaleResponse(**_enrich_sale_response(s)) for s in sales]
        
        return PaginatedSaleResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
        )
    
    except Exception as e:
        logger.error(f"Error listing sales: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please contact support.",
        )


@router.get(
    "/pending",
    response_model=PaginatedSaleResponse,
    summary="List sales pending liquidation",
    description="""
    List all sales with status='registered' (pending liquidation).
    
    These sales have been created but not yet paid.
    Use PATCH /sales/{id}/liquidate to complete payment.
    """,
)
async def list_pending_sales(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> PaginatedSaleResponse:
    """List sales pending liquidation (status='registered')."""
    try:
        sales, total = crud_sale.get_multi(
            db=db,
            organization_id=org_context["organization_id"],
            skip=skip,
            limit=limit,
            status="registered",
        )
        
        items = [SaleResponse(**_enrich_sale_response(s)) for s in sales]
        
        return PaginatedSaleResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
        )
    
    except Exception as e:
        logger.error(f"Error listing pending sales: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please contact support.",
        )


@router.get(
    "/by-number/{sale_number}",
    response_model=SaleResponse,
    summary="Get sale by number",
    description="Get a single sale by its sequential sale_number.",
)
async def get_sale_by_number(
    sale_number: int,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> SaleResponse:
    """Get sale by sale_number."""
    sale = crud_sale.get_by_number(
        db=db,
        sale_number=sale_number,
        organization_id=org_context["organization_id"],
    )
    
    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sale #{sale_number} not found",
        )
    
    # Load with eager loading
    sale = crud_sale.get(
        db=db,
        sale_id=sale.id,
        organization_id=org_context["organization_id"],
    )
    
    response_data = _enrich_sale_response(sale)
    return SaleResponse(**response_data)


@router.get(
    "/customer/{customer_id}",
    response_model=PaginatedSaleResponse,
    summary="List sales by customer",
    description="List all sales from a specific customer.",
)
async def list_sales_by_customer(
    customer_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> PaginatedSaleResponse:
    """List sales by customer."""
    try:
        sales, total = crud_sale.get_multi(
            db=db,
            organization_id=org_context["organization_id"],
            skip=skip,
            limit=limit,
            customer_id=customer_id,
        )
        
        items = [SaleResponse(**_enrich_sale_response(s)) for s in sales]
        
        return PaginatedSaleResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
        )
    
    except Exception as e:
        logger.error(f"Error listing sales by customer: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please contact support.",
        )


@router.get(
    "/{sale_id}",
    response_model=SaleResponse,
    summary="Get single sale",
    description="""
    Get a single sale by ID with all details.
    
    Includes:
    - Sale lines with material details and profit calculation
    - Commissions with recipient details
    - Customer, warehouse, and payment account information
    """,
)
async def get_sale(
    sale_id: UUID,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> SaleResponse:
    """Get sale by ID."""
    sale = crud_sale.get(
        db=db,
        sale_id=sale_id,
        organization_id=org_context["organization_id"],
    )
    
    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sale not found",
        )
    
    response_data = _enrich_sale_response(sale)
    return SaleResponse(**response_data)


@router.patch(
    "/{sale_id}/liquidate",
    response_model=SaleResponse,
    summary="Liquidate sale (2-step workflow)",
    description="""
    Liquidate a registered sale (complete payment).
    
    **Effects:**
    - Updates status to 'paid'
    - Credits payment account (receives money)
    - Debits customer balance (they paid)
    - Pays commissions to recipients (increases their balances)
    
    **Requirements:**
    - Sale must have status='registered'
    - Payment account must belong to organization
    """,
)
async def liquidate_sale(
    sale_id: UUID,
    liquidate_in: SaleLiquidateRequest,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> SaleResponse:
    """Liquidate a sale (2-step workflow)."""
    try:
        sale = crud_sale.liquidate(
            db=db,
            sale_id=sale_id,
            payment_account_id=liquidate_in.payment_account_id,
            organization_id=org_context["organization_id"],
        )
        
        db.commit()
        db.refresh(sale)
        
        # Reload with eager loading
        sale = crud_sale.get(
            db=db,
            sale_id=sale.id,
            organization_id=org_context["organization_id"],
        )
        
        response_data = _enrich_sale_response(sale)
        
        logger.info(
            f"Sale #{sale.sale_number} liquidated by user {org_context['user_id']}"
        )
        
        return SaleResponse(**response_data)
    
    except HTTPException:
        db.rollback()
        raise
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error liquidating sale: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please contact support.",
        )


@router.patch(
    "/{sale_id}/cancel",
    response_model=SaleResponse,
    summary="Cancel sale",
    description="""
    Cancel a sale and reverse all effects.
    
    **Effects:**
    - Updates status to 'cancelled'
    - Creates reversal inventory movements
    - Restores material stock
    - Reverts customer balance
    
    **Restrictions:**
    - Cannot cancel paid sales (use reversal sale instead)
    - Cannot cancel already cancelled sales
    - Must have status='registered'
    """,
)
async def cancel_sale(
    sale_id: UUID,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> SaleResponse:
    """Cancel a sale."""
    try:
        sale = crud_sale.cancel(
            db=db,
            sale_id=sale_id,
            organization_id=org_context["organization_id"],
        )
        
        db.commit()
        db.refresh(sale)
        
        # Reload with eager loading
        sale = crud_sale.get(
            db=db,
            sale_id=sale.id,
            organization_id=org_context["organization_id"],
        )
        
        response_data = _enrich_sale_response(sale)
        
        logger.info(
            f"Sale #{sale.sale_number} cancelled by user {org_context['user_id']}"
        )
        
        return SaleResponse(**response_data)
    
    except HTTPException:
        db.rollback()
        raise
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error cancelling sale: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please contact support.",
        )
