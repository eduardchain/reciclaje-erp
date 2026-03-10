"""
CRUD operations for Material and MaterialCategory models.
"""
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.models.material import Material, MaterialCategory
from app.models.business_unit import BusinessUnit
from app.schemas.material import (
    MaterialCreate,
    MaterialUpdate,
    MaterialCategoryCreate,
    MaterialCategoryUpdate
)
from app.services.base import CRUDBase, Select


class CRUDMaterialCategory(CRUDBase[MaterialCategory, MaterialCategoryCreate, MaterialCategoryUpdate]):
    """CRUD operations for MaterialCategory."""
    
    def _apply_search_filter(self, query: Select, search: str) -> Select:
        """Apply search filter to name and description."""
        search_term = f"%{search}%"
        return query.where(
            or_(
                self.model.name.ilike(search_term),
                self.model.description.ilike(search_term)
            )
        )


class CRUDMaterial(CRUDBase[Material, MaterialCreate, MaterialUpdate]):
    """CRUD operations for Material with custom methods."""
    
    def _apply_search_filter(self, query: Select, search: str) -> Select:
        """Apply search filter to code, name, and description."""
        search_term = f"%{search}%"
        return query.where(
            or_(
                self.model.code.ilike(search_term),
                self.model.name.ilike(search_term),
                self.model.description.ilike(search_term)
            )
        )
    
    def create(
        self,
        db: Session,
        obj_in: MaterialCreate,
        organization_id: UUID
    ) -> Material:
        """
        Create new material with validations.
        
        Validations:
        - Code must be unique within organization
        - Business unit must belong to the same organization
        - Category must belong to the same organization
        
        Args:
            db: Database session
            obj_in: Material creation data
            organization_id: Organization UUID
            
        Returns:
            Created Material
            
        Raises:
            HTTPException: 400 if validations fail
        """
        # Validate code uniqueness within organization
        existing = self.get_by_code(db, obj_in.code, organization_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe un material con codigo '{obj_in.code}' en esta organizacion"
            )
        
        # Validate business unit belongs to organization
        bu_statement = select(BusinessUnit).where(
            BusinessUnit.id == obj_in.business_unit_id,
            BusinessUnit.organization_id == organization_id
        )
        business_unit = db.execute(bu_statement).scalar_one_or_none()
        if not business_unit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La unidad de negocio no pertenece a esta organizacion"
            )
        
        # Validate category belongs to organization
        cat_statement = select(MaterialCategory).where(
            MaterialCategory.id == obj_in.category_id,
            MaterialCategory.organization_id == organization_id
        )
        category = db.execute(cat_statement).scalar_one_or_none()
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La categoria de material no pertenece a esta organizacion"
            )
        
        # Create material with default values
        obj_data = obj_in.model_dump()
        obj_data["organization_id"] = organization_id
        obj_data["current_stock"] = 0.0
        obj_data["current_average_cost"] = 0.0
        
        db_obj = self.model(**obj_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        
        return db_obj
    
    def update(
        self,
        db: Session,
        id: UUID,
        obj_in: MaterialUpdate,
        organization_id: UUID
    ) -> Material:
        """
        Update material with validations.
        
        Validations:
        - If code is updated, must be unique within organization
        - If business_unit_id updated, must belong to organization
        - If category_id updated, must belong to organization
        
        Args:
            db: Database session
            id: Material UUID
            obj_in: Update data
            organization_id: Organization UUID
            
        Returns:
            Updated Material
            
        Raises:
            HTTPException: 400 if validations fail, 404 if not found
        """
        # Get existing material
        db_obj = self.get_or_404(db, id, organization_id, detail="Material no encontrado")
        
        # Get update data
        update_data = obj_in.model_dump(exclude_unset=True)
        
        # Validate code uniqueness if being updated
        if "code" in update_data and update_data["code"] != db_obj.code:
            existing = self.get_by_code(db, update_data["code"], organization_id)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ya existe un material con codigo '{update_data['code']}' en esta organizacion"
                )
        
        # Validate business unit if being updated
        if "business_unit_id" in update_data:
            bu_statement = select(BusinessUnit).where(
                BusinessUnit.id == update_data["business_unit_id"],
                BusinessUnit.organization_id == organization_id
            )
            business_unit = db.execute(bu_statement).scalar_one_or_none()
            if not business_unit:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La unidad de negocio no pertenece a esta organizacion"
                )
        
        # Validate category if being updated
        if "category_id" in update_data:
            cat_statement = select(MaterialCategory).where(
                MaterialCategory.id == update_data["category_id"],
                MaterialCategory.organization_id == organization_id
            )
            category = db.execute(cat_statement).scalar_one_or_none()
            if not category:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La categoria de material no pertenece a esta organizacion"
                )
        
        # Update attributes
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        
        db.commit()
        db.refresh(db_obj)
        
        return db_obj
    
    def delete(
        self,
        db: Session,
        id: UUID,
        organization_id: UUID
    ) -> Material:
        """
        Soft delete material.
        
        Validation:
        - Cannot delete material with current_stock > 0
        
        Args:
            db: Database session
            id: Material UUID
            organization_id: Organization UUID
            
        Returns:
            Deactivated Material
            
        Raises:
            HTTPException: 400 if has stock, 404 if not found
        """
        # Get material
        db_obj = self.get_or_404(db, id, organization_id, detail="Material no encontrado")
        
        # Validate no stock
        if db_obj.current_stock > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede eliminar el material con stock actual ({db_obj.current_stock} {db_obj.default_unit}). Ajuste el stock a cero primero."
            )
        
        # Soft delete
        db_obj.is_active = False
        db.commit()
        db.refresh(db_obj)
        
        return db_obj
    
    def get_by_code(
        self,
        db: Session,
        code: str,
        organization_id: UUID
    ) -> Optional[Material]:
        """
        Get material by code within organization.
        
        Args:
            db: Database session
            code: Material code
            organization_id: Organization UUID
            
        Returns:
            Material or None
        """
        return self.get_by_field(db, "code", code, organization_id)
    
    def get_active_materials(
        self,
        db: Session,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100
    ):
        """
        Get all active materials for organization.
        
        Args:
            db: Database session
            organization_id: Organization UUID
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            PaginatedResponse with active materials
        """
        return self.get_multi(
            db=db,
            organization_id=organization_id,
            skip=skip,
            limit=limit,
            is_active=True
        )
    
    def update_stock(
        self,
        db: Session,
        material_id: UUID,
        quantity_delta: float,
        organization_id: UUID
    ) -> Material:
        """
        Update material stock by delta amount.
        
        Validation:
        - Resulting stock cannot be negative
        
        Args:
            db: Database session
            material_id: Material UUID
            quantity_delta: Amount to add (positive) or subtract (negative)
            organization_id: Organization UUID
            
        Returns:
            Updated Material
            
        Raises:
            HTTPException: 400 if would result in negative stock, 404 if not found
        
        TODO: Create movement record in Phase 2
        """
        # Get material
        material = self.get_or_404(
            db, 
            material_id, 
            organization_id,
            detail="Material no encontrado"
        )
        
        # Convert to Decimal for calculation
        from decimal import Decimal
        quantity_delta_decimal = Decimal(str(quantity_delta))
        
        # Calculate new stock
        new_stock = material.current_stock + quantity_delta_decimal
        
        # Validate non-negative
        if new_stock < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stock insuficiente. Actual: {material.current_stock}, Solicitado: {abs(quantity_delta)}"
            )
        
        # Update stock
        material.current_stock = new_stock
        
        db.commit()
        db.refresh(material)
        
        # TODO: Create movement record in Phase 2
        # movement = MaterialMovement(
        #     material_id=material_id,
        #     quantity=quantity_delta,
        #     ...
        # )
        
        return material


# Instances for use in endpoints
material_category = CRUDMaterialCategory(MaterialCategory)
material = CRUDMaterial(Material)
