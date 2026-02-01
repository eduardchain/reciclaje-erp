"""
API endpoints for Material operations.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_required_org_context, get_db
from app.schemas.material import (
    MaterialCreate,
    MaterialUpdate,
    MaterialResponse,
    MaterialStockUpdate
)
from app.services.base import PaginatedResponse
from app.services.material import material

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
def list_materials(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search in code, name, and description"),
    sort_by: str = Query("name", description="Field to sort by"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Sort order"),
    org_context: tuple = Depends(get_required_org_context),
    db: Session = Depends(get_db)
):
    """
    List all materials for the organization with pagination and filters.
    
    **Filters:**
    - `is_active`: Show only active/inactive materials
    - `search`: Search by code, name, or description
    - `sort_by`: Field name to sort by (e.g., "name", "code", "created_at")
    - `sort_order`: Sort direction ("asc" or "desc")
    
    **Response:**
    - `items`: List of materials
    - `total`: Total count matching filters
    - `skip`: Current offset
    - `limit`: Current page size
    """
    org_id = org_context["organization_id"]
    
    return material.get_multi(
        db=db,
        organization_id=org_id,
        skip=skip,
        limit=limit,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order
    )


@router.post("", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
def create_material(
    material_in: MaterialCreate,
    org_context: tuple = Depends(get_required_org_context),
    db: Session = Depends(get_db)
):
    """
    Create a new material.
    
    **Validations:**
    - Code must be unique within organization
    - Business unit must belong to organization
    - Material category must belong to organization
    
    **Defaults:**
    - `current_stock`: 0
    - `current_average_cost`: 0
    - `is_active`: True
    """
    org_id = org_context["organization_id"]
    
    return material.create(
        db=db,
        obj_in=material_in,
        organization_id=org_id
    )


@router.get("/code/{code}", response_model=MaterialResponse)
def get_material_by_code(
    code: str,
    org_context: tuple = Depends(get_required_org_context),
    db: Session = Depends(get_db)
):
    """
    Get a material by its code.
    
    **Returns:**
    - 404 if material not found or doesn't belong to organization
    """
    org_id = org_context["organization_id"]
    
    result = material.get_by_code(
        db=db,
        code=code,
        organization_id=org_id
    )
    
    if not result:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with code '{code}' not found"
        )
    
    return result


@router.get("/{material_id}", response_model=MaterialResponse)
def get_material(
    material_id: UUID,
    org_context: tuple = Depends(get_required_org_context),
    db: Session = Depends(get_db)
):
    """
    Get a specific material by ID.
    
    **Returns:**
    - 404 if material not found or doesn't belong to organization
    """
    org_id = org_context["organization_id"]
    
    return material.get_or_404(
        db=db,
        id=material_id,
        organization_id=org_id,
        detail="Material not found"
    )


@router.patch("/{material_id}", response_model=MaterialResponse)
def update_material(
    material_id: UUID,
    material_in: MaterialUpdate,
    org_context: tuple = Depends(get_required_org_context),
    db: Session = Depends(get_db)
):
    """
    Update a material.
    
    **Validations:**
    - If code updated, must remain unique within organization
    - If business_unit_id updated, must belong to organization
    - If category_id updated, must belong to organization
    
    **Returns:**
    - 404 if material not found
    - 400 if validations fail
    """
    org_id = org_context["organization_id"]
    
    return material.update(
        db=db,
        id=material_id,
        obj_in=material_in,
        organization_id=org_id
    )


@router.delete("/{material_id}", response_model=MaterialResponse)
def delete_material(
    material_id: UUID,
    org_context: tuple = Depends(get_required_org_context),
    db: Session = Depends(get_db)
):
    """
    Soft delete a material (sets is_active = False).
    
    **Validation:**
    - Cannot delete material with current_stock > 0
    
    **Returns:**
    - 404 if material not found
    - 400 if material has stock
    """
    org_id = org_context["organization_id"]
    
    return material.delete(
        db=db,
        id=material_id,
        organization_id=org_id
    )


@router.post("/{material_id}/stock", response_model=MaterialResponse)
def update_material_stock(
    material_id: UUID,
    stock_update: MaterialStockUpdate,
    org_context: tuple = Depends(get_required_org_context),
    db: Session = Depends(get_db)
):
    """
    Update material stock by adding or subtracting quantity.
    
    **Usage:**
    - Positive `quantity_delta`: Add stock (e.g., purchase, production)
    - Negative `quantity_delta`: Subtract stock (e.g., sale, consumption)
    
    **Validation:**
    - Resulting stock cannot be negative
    
    **Returns:**
    - 404 if material not found
    - 400 if would result in negative stock
    
    **Note:** Movement records will be created in Phase 2
    """
    org_id = org_context["organization_id"]
    
    return material.update_stock(
        db=db,
        material_id=material_id,
        quantity_delta=stock_update.quantity_delta,
        organization_id=org_id
    )
