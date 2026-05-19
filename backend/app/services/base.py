"""
Generic CRUD base class for all models with organization context.

This module provides a reusable base class for CRUD operations with:
- Automatic organization_id filtering
- Type safety with generics
- SQLAlchemy 2.0 syntax
- Pagination support
- Soft delete (is_active flag)
"""
from decimal import Decimal
from typing import Generic, TypeVar, Type, Optional, Any
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func, Select
from sqlalchemy.orm import Session

from app.models.base import Base

# Type variables for generic CRUD
ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class PaginatedResponse(BaseModel):
    """Standard paginated response model."""
    items: list[Any]
    total: int
    skip: int
    limit: int


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    Generic CRUD base class with organization context.
    
    All operations automatically filter by organization_id.
    Supports soft delete via is_active flag.
    
    Type Parameters:
        ModelType: SQLAlchemy model class
        CreateSchemaType: Pydantic schema for creation
        UpdateSchemaType: Pydantic schema for updates
    """
    
    def __init__(self, model: Type[ModelType]):
        """
        Initialize CRUD object with model class.
        
        Args:
            model: SQLAlchemy model class
        """
        self.model = model
    
    def _base_query(self, organization_id: UUID) -> Select:
        """
        Create base query filtered by organization.
        
        Args:
            organization_id: Organization UUID
            
        Returns:
            SQLAlchemy select statement
        """
        return select(self.model).where(
            self.model.organization_id == organization_id
        )
    
    def get(
        self,
        db: Session,
        id: UUID,
        organization_id: UUID
    ) -> Optional[ModelType]:
        """
        Get single record by ID within organization.
        
        Args:
            db: Database session
            id: Record UUID
            organization_id: Organization UUID
            
        Returns:
            Model instance or None if not found
        """
        statement = self._base_query(organization_id).where(
            self.model.id == id
        )
        result = db.execute(statement)
        return result.scalar_one_or_none()
    
    def get_or_404(
        self,
        db: Session,
        id: UUID,
        organization_id: UUID,
        detail: str = "Record not found"
    ) -> ModelType:
        """
        Get single record or raise 404.
        
        Args:
            db: Database session
            id: Record UUID
            organization_id: Organization UUID
            detail: Error message if not found
            
        Returns:
            Model instance
            
        Raises:
            HTTPException: 404 if not found
        """
        obj = self.get(db, id, organization_id)
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail
            )
        return obj

    # Allowlist de columnas ordenables. Cada subclase la define para sort
    # server-side seguro (previene SQL injection via column name arbitrario).
    # Si esta vacia (default), CRUDBase usa el fallback de created_at.
    SORTABLE_COLUMNS: set[str] = set()
    DEFAULT_SORT_COLUMN: str = "created_at"

    def _resolve_sort_column(self, sort_by: Optional[str], sort_dir: str):
        """Retorna (column, direction) validados contra el modelo.

        - Si la subclase define SORTABLE_COLUMNS (non-empty), `sort_by` debe estar
          en ese set para ser aceptada; de lo contrario fallback silencioso a
          DEFAULT_SORT_COLUMN. Fallback silencioso (no 422) para no romper
          deep-links viejos si una columna se renombra en el futuro.
        - Si SORTABLE_COLUMNS esta vacia (subclase legacy sin allowlist), se
          acepta cualquier nombre de columna que exista en el modelo (compat).
        - sort_dir invalido => 'desc'.
        """
        if self.SORTABLE_COLUMNS:
            col_name = sort_by if (sort_by and sort_by in self.SORTABLE_COLUMNS) else self.DEFAULT_SORT_COLUMN
        else:
            # Legacy: sin allowlist, aceptar cualquier columna que exista en el modelo
            col_name = sort_by or self.DEFAULT_SORT_COLUMN
        column = getattr(self.model, col_name, None)
        if column is None:
            column = self.model.created_at
        direction = "asc" if str(sort_dir).lower() == "asc" else "desc"
        return column, direction

    def get_multi(
        self,
        db: Session,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> PaginatedResponse:
        """
        Get multiple records with pagination and filters.
        
        Args:
            db: Database session
            organization_id: Organization UUID
            skip: Number of records to skip
            limit: Maximum records to return
            is_active: Filter by active status (None = all)
            search: Search term (implementation in subclass)
            sort_by: Field name to sort by
            sort_order: 'asc' or 'desc'
            
        Returns:
            PaginatedResponse with items and metadata
        """
        # Base query
        query = self._base_query(organization_id)
        
        # Filter by active status
        if is_active is not None:
            query = query.where(self.model.is_active == is_active)
        
        # Apply search if provided (subclasses can override)
        if search:
            query = self._apply_search_filter(query, search)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = db.execute(count_query).scalar_one()
        
        # Apply sorting (con allowlist si la subclase la define)
        sort_column, sort_dir = self._resolve_sort_column(sort_by, sort_order)
        order_clause = sort_column.desc() if sort_dir == "desc" else sort_column.asc()
        # Tiebreaker estable para paginacion consistente cuando hay ties
        query = query.order_by(order_clause, self.model.id.asc())
        
        # Apply pagination
        query = query.offset(skip).limit(limit)
        
        # Execute query
        result = db.execute(query)
        items = result.scalars().all()
        
        # Convert ORM models to dicts for serialization
        items_data = []
        for item in items:
            # Use Pydantic's model_validate if item is an ORM model
            if hasattr(item, '__dict__'):
                item_dict = {
                    c.name: float(v) if isinstance(v := getattr(item, c.name), Decimal) else v
                    for c in item.__table__.columns
                }
                items_data.append(item_dict)
            else:
                items_data.append(item)
        
        return PaginatedResponse(
            items=items_data,
            total=total,
            skip=skip,
            limit=limit
        )
    
    def _apply_search_filter(self, query: Select, search: str) -> Select:
        """
        Apply search filter to query.
        Override in subclasses to implement custom search logic.
        
        Args:
            query: Base query
            search: Search term
            
        Returns:
            Modified query
        """
        # Default: no search filtering
        # Subclasses should override this method
        return query
    
    def create(
        self,
        db: Session,
        obj_in: CreateSchemaType,
        organization_id: UUID
    ) -> ModelType:
        """
        Create new record.
        
        Args:
            db: Database session
            obj_in: Creation schema with data
            organization_id: Organization UUID
            
        Returns:
            Created model instance
        """
        # Convert Pydantic model to dict
        obj_data = obj_in.model_dump()
        
        # Add organization_id
        obj_data["organization_id"] = organization_id
        
        # Create model instance
        db_obj = self.model(**obj_data)
        
        # Add to session and commit
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        
        return db_obj
    
    def update(
        self,
        db: Session,
        id: UUID,
        obj_in: UpdateSchemaType,
        organization_id: UUID
    ) -> ModelType:
        """
        Update existing record.
        
        Args:
            db: Database session
            id: Record UUID
            obj_in: Update schema with data
            organization_id: Organization UUID
            
        Returns:
            Updated model instance
            
        Raises:
            HTTPException: 404 if not found
        """
        # Get existing object
        db_obj = self.get_or_404(db, id, organization_id)
        
        # Get update data, excluding unset fields
        update_data = obj_in.model_dump(exclude_unset=True)
        
        # Update object attributes
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        
        # Commit changes
        db.commit()
        db.refresh(db_obj)
        
        return db_obj
    
    def delete(
        self,
        db: Session,
        id: UUID,
        organization_id: UUID
    ) -> ModelType:
        """
        Soft delete record (set is_active = False).
        
        Args:
            db: Database session
            id: Record UUID
            organization_id: Organization UUID
            
        Returns:
            Deleted (deactivated) model instance
            
        Raises:
            HTTPException: 404 if not found
        """
        # Get existing object
        db_obj = self.get_or_404(db, id, organization_id)
        
        # Soft delete
        db_obj.is_active = False
        
        # Commit changes
        db.commit()
        db.refresh(db_obj)
        
        return db_obj
    
    def get_by_field(
        self,
        db: Session,
        field_name: str,
        field_value: Any,
        organization_id: UUID
    ) -> Optional[ModelType]:
        """
        Get single record by custom field within organization.
        
        Args:
            db: Database session
            field_name: Name of the field to filter by
            field_value: Value to match
            organization_id: Organization UUID
            
        Returns:
            Model instance or None if not found
        """
        # Get field from model
        field = getattr(self.model, field_name)
        
        # Build query
        statement = self._base_query(organization_id).where(
            field == field_value
        )
        
        # Execute query
        result = db.execute(statement)
        return result.scalar_one_or_none()
