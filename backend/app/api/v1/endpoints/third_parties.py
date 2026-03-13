"""
API endpoints for Third Party operations.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_permission, get_db
from app.schemas.third_party import (
    ThirdPartyCreate,
    ThirdPartyUpdate,
    ThirdPartyResponse,
    ThirdPartyBalanceUpdate
)
from app.services.base import PaginatedResponse
from app.services.third_party import third_party

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
def list_third_parties(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search in name, identification, and email"),
    role: Optional[str] = Query(None, description="Filter by role: supplier, customer, investor, provision"),
    sort_by: str = Query("name", description="Field to sort by"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Sort order"),
    org_context: tuple = Depends(require_permission("third_parties.view")),
    db: Session = Depends(get_db)
):
    """
    List all third parties for the organization with pagination and filters.

    **Filters:**
    - `is_active`: Show only active/inactive third parties
    - `search`: Search by name, identification, or email
    - `role`: Filter by role (supplier, customer, investor, provision)
    - `sort_by`: Field name to sort by (e.g., "name", "identification")
    - `sort_order`: Sort direction ("asc" or "desc")
    """
    org_id = org_context["organization_id"]

    return third_party.get_multi(
        db=db,
        organization_id=org_id,
        skip=skip,
        limit=limit,
        is_active=is_active,
        search=search,
        role=role,
        sort_by=sort_by,
        sort_order=sort_order
    )


@router.get("/suppliers", response_model=PaginatedResponse)
def list_suppliers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("name"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    org_context: tuple = Depends(require_permission("third_parties.view")),
    db: Session = Depends(get_db)
):
    """
    List only third parties marked as suppliers (is_supplier = True).
    """
    org_id = org_context["organization_id"]
    
    return third_party.get_suppliers(
        db=db,
        organization_id=org_id,
        skip=skip,
        limit=limit,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order
    )


@router.get("/customers", response_model=PaginatedResponse)
def list_customers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("name"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    org_context: tuple = Depends(require_permission("third_parties.view")),
    db: Session = Depends(get_db)
):
    """
    List only third parties marked as customers (is_customer = True).
    """
    org_id = org_context["organization_id"]
    
    return third_party.get_customers(
        db=db,
        organization_id=org_id,
        skip=skip,
        limit=limit,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order
    )


@router.get("/provisions", response_model=PaginatedResponse)
def list_provisions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("name"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    org_context: tuple = Depends(require_permission("third_parties.view")),
    db: Session = Depends(get_db)
):
    """
    List only third parties marked as provisions (is_provision = True).
    """
    org_id = org_context["organization_id"]
    
    return third_party.get_provisions(
        db=db,
        organization_id=org_id,
        skip=skip,
        limit=limit,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order
    )


@router.get("/liabilities", response_model=PaginatedResponse)
def list_liabilities(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("name"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    org_context: tuple = Depends(require_permission("third_parties.view")),
    db: Session = Depends(get_db)
):
    """
    List only third parties marked as liabilities (is_liability = True).
    Excluye system entities.
    """
    org_id = org_context["organization_id"]

    return third_party.get_liabilities(
        db=db,
        organization_id=org_id,
        skip=skip,
        limit=limit,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order
    )


@router.post("", response_model=ThirdPartyResponse, status_code=status.HTTP_201_CREATED)
def create_third_party(
    third_party_in: ThirdPartyCreate,
    org_context: tuple = Depends(require_permission("third_parties.create")),
    db: Session = Depends(get_db)
):
    """
    Create a new third party.
    
    **Defaults:**
    - `current_balance`: 0
    - `is_active`: True
    - All boolean flags default to False if not specified
    """
    org_id = org_context["organization_id"]
    
    return third_party.create(
        db=db,
        obj_in=third_party_in,
        organization_id=org_id
    )


@router.get("/{third_party_id}", response_model=ThirdPartyResponse)
def get_third_party(
    third_party_id: UUID,
    org_context: tuple = Depends(require_permission("third_parties.view")),
    db: Session = Depends(get_db)
):
    """
    Get a specific third party by ID.
    
    **Returns:**
    - 404 if third party not found or doesn't belong to organization
    """
    org_id = org_context["organization_id"]
    
    return third_party.get_or_404(
        db=db,
        id=third_party_id,
        organization_id=org_id,
        detail="Tercero no encontrado"
    )


@router.patch("/{third_party_id}", response_model=ThirdPartyResponse)
def update_third_party(
    third_party_id: UUID,
    third_party_in: ThirdPartyUpdate,
    org_context: tuple = Depends(require_permission("third_parties.edit")),
    db: Session = Depends(get_db)
):
    """
    Update a third party.
    
    **Returns:**
    - 404 if third party not found
    """
    org_id = org_context["organization_id"]
    
    return third_party.update(
        db=db,
        id=third_party_id,
        obj_in=third_party_in,
        organization_id=org_id
    )


@router.delete("/{third_party_id}", response_model=ThirdPartyResponse)
def delete_third_party(
    third_party_id: UUID,
    org_context: tuple = Depends(require_permission("third_parties.delete")),
    db: Session = Depends(get_db)
):
    """
    Soft delete a third party (sets is_active = False).
    
    **Validation:**
    - Cannot delete third party with current_balance != 0
    
    **Returns:**
    - 404 if third party not found
    - 400 if third party has outstanding balance
    """
    org_id = org_context["organization_id"]
    
    return third_party.delete(
        db=db,
        id=third_party_id,
        organization_id=org_id
    )


@router.post("/{third_party_id}/balance", response_model=ThirdPartyResponse)
def update_third_party_balance(
    third_party_id: UUID,
    balance_update: ThirdPartyBalanceUpdate,
    org_context: tuple = Depends(require_permission("third_parties.view_balance")),
    db: Session = Depends(get_db)
):
    """
    Update third party balance by adding or subtracting an amount.
    
    **Usage:**
    - Positive `amount_delta`: Increase balance (e.g., invoice issued)
    - Negative `amount_delta`: Decrease balance (e.g., payment received)
    
    **Note:** 
    - Balance can be negative (indicates debt)
    - Transaction records will be created in Phase 2
    
    **Returns:**
    - 404 if third party not found
    """
    org_id = org_context["organization_id"]
    
    return third_party.update_balance(
        db=db,
        third_party_id=third_party_id,
        amount_delta=balance_update.amount_delta,
        organization_id=org_id
    )
