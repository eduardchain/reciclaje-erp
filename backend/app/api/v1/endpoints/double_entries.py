"""
REST API endpoints for double-entry (Pasa Mano) operations.

A double-entry operation represents buying from a supplier and immediately
selling to a customer without the material entering inventory.
"""
import logging
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_required_org_context
from app.models.double_entry import DoubleEntry
from app.schemas.double_entry import (
    DoubleEntryCreate,
    DoubleEntryUpdate,
    DoubleEntryResponse,
    PaginatedDoubleEntryResponse,
)
from app.services.double_entry import double_entry as double_entry_service

# Setup logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


# ============================================================================
# Helper Functions
# ============================================================================

def _enrich_double_entry_response(double_entry: DoubleEntry) -> dict:
    """
    Enrich double_entry object with joined data for response.
    
    Assumes double_entry was loaded with proper joinedload options.
    """
    return {
        **double_entry.__dict__,
        # Include calculated properties (not in __dict__)
        "total_purchase_cost": double_entry.total_purchase_cost,
        "total_sale_amount": double_entry.total_sale_amount,
        "profit": double_entry.profit,
        "profit_margin": double_entry.profit_margin,
        # Include joined data
        "material_code": double_entry.material.code if double_entry.material else None,
        "material_name": double_entry.material.name if double_entry.material else None,
        "supplier_name": double_entry.supplier.name if double_entry.supplier else None,
        "customer_name": double_entry.customer.name if double_entry.customer else None,
        "commissions": [
            {
                **comm.__dict__,
                "third_party_name": comm.third_party.name if comm.third_party else None,
            }
            for comm in (double_entry.sale.commissions if double_entry.sale else [])
        ],
    }


# ============================================================================
# Endpoints
# ============================================================================

@router.post(
    "",
    response_model=DoubleEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new double-entry operation",
    description="""
    Create a new double-entry (Pasa Mano) operation.
    
    **Business Flow:**
    1. Material does NOT enter inventory (no stock movement)
    2. Creates Purchase record (status='registered', no inventory)
    3. Creates Sale record (status='registered', no inventory)
    4. Updates supplier balance (debt increases - we owe them)
    5. Updates customer balance (receivable increases - they owe us)
    6. Creates commissions (if provided, paid when sale is liquidated)
    7. Net profit = sale_total - purchase_total - commissions
    
    **Validations:**
    - supplier_id != customer_id (cannot trade with same party)
    - Supplier must have is_supplier=True
    - Customer must have is_customer=True
    - Material must belong to organization
    
    **Effects:**
    - Generates sequential double_entry_number
    - Generates sequential purchase_number and sale_number
    - Supplier balance decreases (debt increases)
    - Customer balance increases (receivable increases)
    - NO inventory movements
    - NO stock changes
    """,
)
async def create_double_entry(
    double_entry_in: DoubleEntryCreate,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> DoubleEntryResponse:
    """Create a new double-entry operation."""
    try:
        double_entry_obj = double_entry_service.create(
            db=db,
            obj_in=double_entry_in,
            organization_id=org_context["organization_id"],
        )
        
        # Reload with eager loading to get all relationships
        double_entry_obj = double_entry_service.get(
            db=db,
            double_entry_id=double_entry_obj.id,
            organization_id=org_context["organization_id"],
        )
        
        # Enrich with joined data
        response_data = _enrich_double_entry_response(double_entry_obj)
        
        logger.info(
            f"Double-entry #{double_entry_obj.double_entry_number} created by user {org_context['user_id']} "
            f"in org {org_context['organization_id']}"
        )
        
        return DoubleEntryResponse(**response_data)
    
    except HTTPException:
        db.rollback()
        raise  # Re-raise HTTP exceptions from service
    
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error creating double-entry: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate double-entry number. Please retry.",
        )
    
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error creating double-entry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


@router.get(
    "",
    response_model=PaginatedDoubleEntryResponse,
    summary="List double-entry operations",
    description="""
    Get paginated list of double-entry operations with filters.
    
    **Filters:**
    - status: 'completed' or 'cancelled'
    - material_id: Filter by material
    - supplier_id: Filter by supplier
    - customer_id: Filter by customer
    - date_from, date_to: Filter by date range
    - search: Search in double_entry_number, supplier name, customer name, notes, invoice_number
    
    **Ordering:** By date descending (newest first)
    """,
)
async def list_double_entries(
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    status: Optional[str] = Query(None, description="Filter by status: 'completed' or 'cancelled'"),
    material_id: Optional[UUID] = Query(None, description="Filter by material UUID"),
    supplier_id: Optional[UUID] = Query(None, description="Filter by supplier UUID"),
    customer_id: Optional[UUID] = Query(None, description="Filter by customer UUID"),
    date_from: Optional[date] = Query(None, description="Filter by date from (inclusive)"),
    date_to: Optional[date] = Query(None, description="Filter by date to (inclusive)"),
    search: Optional[str] = Query(None, description="Search in number, names, notes, invoice"),
) -> PaginatedDoubleEntryResponse:
    """Get paginated list of double-entries with filters."""
    double_entries, total = double_entry_service.get_multi(
        db=db,
        organization_id=org_context["organization_id"],
        skip=skip,
        limit=limit,
        status=status,
        material_id=material_id,
        supplier_id=supplier_id,
        customer_id=customer_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )
    
    # Enrich each double_entry
    items = [
        DoubleEntryResponse(**_enrich_double_entry_response(de))
        for de in double_entries
    ]
    
    return PaginatedDoubleEntryResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{double_entry_id}",
    response_model=DoubleEntryResponse,
    summary="Get double-entry by UUID",
    description="Get a single double-entry operation by its UUID.",
)
async def get_double_entry(
    double_entry_id: UUID,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> DoubleEntryResponse:
    """Get a single double-entry by UUID."""
    double_entry_obj = double_entry_service.get(
        db=db,
        double_entry_id=double_entry_id,
        organization_id=org_context["organization_id"],
    )
    
    if not double_entry_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Double-entry operation not found",
        )
    
    response_data = _enrich_double_entry_response(double_entry_obj)
    return DoubleEntryResponse(**response_data)


@router.get(
    "/by-number/{double_entry_number}",
    response_model=DoubleEntryResponse,
    summary="Get double-entry by sequential number",
    description="Get a single double-entry operation by its sequential number within the organization.",
)
async def get_double_entry_by_number(
    double_entry_number: int,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> DoubleEntryResponse:
    """Get a single double-entry by sequential number."""
    double_entry_obj = double_entry_service.get_by_number(
        db=db,
        double_entry_number=double_entry_number,
        organization_id=org_context["organization_id"],
    )
    
    if not double_entry_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Double-entry #{double_entry_number} not found",
        )
    
    response_data = _enrich_double_entry_response(double_entry_obj)
    return DoubleEntryResponse(**response_data)


@router.get(
    "/supplier/{supplier_id}",
    response_model=PaginatedDoubleEntryResponse,
    summary="List double-entries by supplier",
    description="Get paginated list of double-entry operations for a specific supplier.",
)
async def list_double_entries_by_supplier(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> PaginatedDoubleEntryResponse:
    """Get double-entries by supplier."""
    double_entries, total = double_entry_service.get_by_supplier(
        db=db,
        supplier_id=supplier_id,
        organization_id=org_context["organization_id"],
        skip=skip,
        limit=limit,
    )
    
    items = [
        DoubleEntryResponse(**_enrich_double_entry_response(de))
        for de in double_entries
    ]
    
    return PaginatedDoubleEntryResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/customer/{customer_id}",
    response_model=PaginatedDoubleEntryResponse,
    summary="List double-entries by customer",
    description="Get paginated list of double-entry operations for a specific customer.",
)
async def list_double_entries_by_customer(
    customer_id: UUID,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> PaginatedDoubleEntryResponse:
    """Get double-entries by customer."""
    double_entries, total = double_entry_service.get_by_customer(
        db=db,
        customer_id=customer_id,
        organization_id=org_context["organization_id"],
        skip=skip,
        limit=limit,
    )
    
    items = [
        DoubleEntryResponse(**_enrich_double_entry_response(de))
        for de in double_entries
    ]
    
    return PaginatedDoubleEntryResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.patch(
    "/{double_entry_id}/cancel",
    response_model=DoubleEntryResponse,
    summary="Cancel double-entry operation",
    description="""
    Cancel a double-entry operation and reverse all changes.
    
    **Requirements:**
    - Double-entry status must be 'completed'
    - Linked Purchase must be 'registered' (not paid)
    - Linked Sale must be 'registered' (not paid)
    
    **Effects:**
    - Sets double_entry status to 'cancelled'
    - Sets Purchase status to 'cancelled'
    - Sets Sale status to 'cancelled'
    - Reverts supplier balance (reduces debt)
    - Reverts customer balance (reduces receivable)
    - NO inventory movements (there were none)
    - Commissions are not paid (they were never paid)
    """,
)
async def cancel_double_entry(
    double_entry_id: UUID,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> DoubleEntryResponse:
    """Cancel a double-entry operation."""
    try:
        double_entry_obj = double_entry_service.cancel(
            db=db,
            double_entry_id=double_entry_id,
            organization_id=org_context["organization_id"],
        )
        
        # Reload with eager loading
        double_entry_obj = double_entry_service.get(
            db=db,
            double_entry_id=double_entry_obj.id,
            organization_id=org_context["organization_id"],
        )
        
        response_data = _enrich_double_entry_response(double_entry_obj)
        
        logger.info(
            f"Double-entry #{double_entry_obj.double_entry_number} cancelled by user {org_context['user_id']}"
        )
        
        return DoubleEntryResponse(**response_data)
    
    except HTTPException:
        db.rollback()
        raise
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error cancelling double-entry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


@router.patch(
    "/{double_entry_id}",
    response_model=DoubleEntryResponse,
    summary="Update double-entry metadata",
    description="""
    Update double-entry metadata (notes, invoice_number, vehicle_plate only).
    
    **Allowed updates:**
    - notes
    - invoice_number
    - vehicle_plate
    
    **Not allowed:**
    - Cannot change amounts, dates, or parties
    - Cannot change status (use /cancel endpoint)
    """,
)
async def update_double_entry(
    double_entry_id: UUID,
    double_entry_update: DoubleEntryUpdate,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> DoubleEntryResponse:
    """Update double-entry metadata."""
    try:
        double_entry_obj = double_entry_service.update(
            db=db,
            double_entry_id=double_entry_id,
            obj_in=double_entry_update,
            organization_id=org_context["organization_id"],
        )
        
        # Reload with eager loading
        double_entry_obj = double_entry_service.get(
            db=db,
            double_entry_id=double_entry_obj.id,
            organization_id=org_context["organization_id"],
        )
        
        response_data = _enrich_double_entry_response(double_entry_obj)
        
        return DoubleEntryResponse(**response_data)
    
    except HTTPException:
        db.rollback()
        raise
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating double-entry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )
