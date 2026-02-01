"""
API endpoints for Material Category operations.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_required_org_context, get_db
from app.schemas.material import (
    MaterialCategoryCreate,
    MaterialCategoryUpdate,
    MaterialCategoryResponse
)
from app.services.base import PaginatedResponse
from app.services.material import material_category

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
def list_material_categories(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search in name and description"),
    sort_by: str = Query("name", description="Field to sort by"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Sort order"),
    org_context: tuple = Depends(get_required_org_context),
    db: Session = Depends(get_db)
):
    """
    List all material categories for the organization with pagination and filters.
    
    **Filters:**
    - `is_active`: Show only active/inactive categories
    - `search`: Search by name or description
    - `sort_by`: Field name to sort by (e.g., "name", "created_at")
    - `sort_order`: Sort direction ("asc" or "desc")
    
    **Response:**
    - `items`: List of material categories
    - `total`: Total count matching filters
    - `skip`: Current offset
    - `limit`: Current page size
    """
    org_id = org_context["organization_id"]
    
    return material_category.get_multi(
        db=db,
        organization_id=org_id,
        skip=skip,
        limit=limit,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order
    )


@router.post("", response_model=MaterialCategoryResponse, status_code=status.HTTP_201_CREATED)
def create_material_category(
    category_in: MaterialCategoryCreate,
    org_context: tuple = Depends(get_required_org_context),
    db: Session = Depends(get_db)
):
    """
    Create a new material category.
    
    **Defaults:**
    - `is_active`: True
    """
    org_id = org_context["organization_id"]
    
    return material_category.create(
        db=db,
        obj_in=category_in,
        organization_id=org_id
    )


@router.get("/{category_id}", response_model=MaterialCategoryResponse)
def get_material_category(
    category_id: UUID,
    org_context: tuple = Depends(get_required_org_context),
    db: Session = Depends(get_db)
):
    """
    Get a specific material category by ID.
    
    **Returns:**
    - 404 if category not found or doesn't belong to organization
    """
    org_id = org_context["organization_id"]
    
    return material_category.get_or_404(
        db=db,
        id=category_id,
        organization_id=org_id,
        detail="Material category not found"
    )


@router.patch("/{category_id}", response_model=MaterialCategoryResponse)
def update_material_category(
    category_id: UUID,
    category_in: MaterialCategoryUpdate,
    org_context: tuple = Depends(get_required_org_context),
    db: Session = Depends(get_db)
):
    """
    Update a material category.
    
    **Returns:**
    - 404 if category not found
    """
    org_id = org_context["organization_id"]
    
    return material_category.update(
        db=db,
        id=category_id,
        obj_in=category_in,
        organization_id=org_id
    )


@router.delete("/{category_id}", response_model=MaterialCategoryResponse)
def delete_material_category(
    category_id: UUID,
    org_context: tuple = Depends(get_required_org_context),
    db: Session = Depends(get_db)
):
    """
    Soft delete a material category (sets is_active = False).
    
    **Returns:**
    - 404 if category not found
    
    **Note:** In future, may add validation to prevent deletion if materials exist.
    """
    org_id = org_context["organization_id"]
    
    return material_category.delete(
        db=db,
        id=category_id,
        organization_id=org_id
    )
