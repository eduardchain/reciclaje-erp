"""
CRUD operations for ThirdParty model.
"""
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.models.third_party import ThirdParty
from app.schemas.third_party import ThirdPartyCreate, ThirdPartyUpdate
from app.services.base import CRUDBase, Select, PaginatedResponse


class CRUDThirdParty(CRUDBase[ThirdParty, ThirdPartyCreate, ThirdPartyUpdate]):
    """CRUD operations for ThirdParty with custom methods."""
    
    def _apply_search_filter(self, query: Select, search: str) -> Select:
        """Apply search filter to name, identification_number, and email."""
        search_term = f"%{search}%"
        return query.where(
            or_(
                self.model.name.ilike(search_term),
                self.model.identification_number.ilike(search_term),
                self.model.email.ilike(search_term)
            )
        )
    
    # Mapeo de roles a columnas booleanas
    ROLE_COLUMN_MAP = {
        "supplier": "is_supplier",
        "customer": "is_customer",
        "investor": "is_investor",
        "provision": "is_provision",
    }

    def get_multi(
        self,
        db: Session,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        role: Optional[str] = None,
        sort_by: str = "name",
        sort_order: str = "asc"
    ) -> PaginatedResponse:
        """Get third parties con filtro opcional por rol."""
        from sqlalchemy import func

        query = self._base_query(organization_id)

        if role and role in self.ROLE_COLUMN_MAP:
            col = getattr(self.model, self.ROLE_COLUMN_MAP[role])
            query = query.where(col == True)

        if is_active is not None:
            query = query.where(self.model.is_active == is_active)

        if search:
            query = self._apply_search_filter(query, search)

        count_query = select(func.count()).select_from(query.subquery())
        total = db.execute(count_query).scalar_one()

        sort_column = getattr(self.model, sort_by, self.model.name)
        if sort_order.lower() == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        query = query.offset(skip).limit(limit)
        result = db.execute(query)
        items = result.scalars().all()

        items_dict = [
            {c.name: getattr(item, c.name) for c in item.__table__.columns}
            for item in items
        ]

        return PaginatedResponse(
            items=items_dict,
            total=total,
            skip=skip,
            limit=limit
        )

    def create(
        self,
        db: Session,
        obj_in: ThirdPartyCreate,
        organization_id: UUID
    ) -> ThirdParty:
        """
        Create new third party with default balance.
        
        Args:
            db: Database session
            obj_in: Third party creation data
            organization_id: Organization UUID
            
        Returns:
            Created ThirdParty
        """
        # Create with initial_balance mapped to current_balance
        obj_data = obj_in.model_dump(exclude={"initial_balance"})
        obj_data["organization_id"] = organization_id
        obj_data["initial_balance"] = obj_in.initial_balance
        obj_data["current_balance"] = obj_in.initial_balance
        
        db_obj = self.model(**obj_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        
        return db_obj
    
    def delete(
        self,
        db: Session,
        id: UUID,
        organization_id: UUID
    ) -> ThirdParty:
        """
        Soft delete third party.
        
        Validation:
        - Cannot delete third party with current_balance != 0
        
        Args:
            db: Database session
            id: ThirdParty UUID
            organization_id: Organization UUID
            
        Returns:
            Deactivated ThirdParty
            
        Raises:
            HTTPException: 400 if has balance, 404 if not found
        """
        # Get third party
        db_obj = self.get_or_404(db, id, organization_id, detail="Tercero no encontrado")
        
        # Validate zero balance
        if db_obj.current_balance != 0:
            balance_type = "deuda" if db_obj.current_balance < 0 else "credito"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede eliminar el tercero con saldo pendiente de {balance_type} ({db_obj.current_balance}). Liquide el saldo primero."
            )
        
        # Soft delete
        db_obj.is_active = False
        db.commit()
        db.refresh(db_obj)
        
        return db_obj
    
    def get_suppliers(
        self,
        db: Session,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: str = "name",
        sort_order: str = "asc"
    ) -> PaginatedResponse:
        """
        Get all suppliers (is_supplier=True) for organization.
        
        Args:
            db: Database session
            organization_id: Organization UUID
            skip: Pagination offset
            limit: Pagination limit
            is_active: Filter by active status
            search: Search term
            sort_by: Sort field
            sort_order: Sort direction
            
        Returns:
            PaginatedResponse with suppliers
        """
        # Base query with supplier filter
        query = self._base_query(organization_id).where(
            self.model.is_supplier == True
        )
        
        # Apply filters
        if is_active is not None:
            query = query.where(self.model.is_active == is_active)
        
        if search:
            query = self._apply_search_filter(query, search)
        
        # Get total count
        from sqlalchemy import func
        count_query = select(func.count()).select_from(query.subquery())
        total = db.execute(count_query).scalar_one()
        
        # Apply sorting
        sort_column = getattr(self.model, sort_by, self.model.name)
        if sort_order.lower() == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
        
        # Apply pagination
        query = query.offset(skip).limit(limit)
        
        # Execute
        result = db.execute(query)
        items = result.scalars().all()
        
        # Convert ORM models to dicts for Pydantic serialization
        items_dict = [
            {c.name: getattr(item, c.name) for c in item.__table__.columns}
            for item in items
        ]
        
        return PaginatedResponse(
            items=items_dict,
            total=total,
            skip=skip,
            limit=limit
        )
    
    def get_customers(
        self,
        db: Session,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: str = "name",
        sort_order: str = "asc"
    ) -> PaginatedResponse:
        """
        Get all customers (is_customer=True) for organization.
        
        Args:
            db: Database session
            organization_id: Organization UUID
            skip: Pagination offset
            limit: Pagination limit
            is_active: Filter by active status
            search: Search term
            sort_by: Sort field
            sort_order: Sort direction
            
        Returns:
            PaginatedResponse with customers
        """
        # Base query with customer filter
        query = self._base_query(organization_id).where(
            self.model.is_customer == True
        )
        
        # Apply filters
        if is_active is not None:
            query = query.where(self.model.is_active == is_active)
        
        if search:
            query = self._apply_search_filter(query, search)
        
        # Get total count
        from sqlalchemy import func
        count_query = select(func.count()).select_from(query.subquery())
        total = db.execute(count_query).scalar_one()
        
        # Apply sorting
        sort_column = getattr(self.model, sort_by, self.model.name)
        if sort_order.lower() == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
        
        # Apply pagination
        query = query.offset(skip).limit(limit)
        
        # Execute
        result = db.execute(query)
        items = result.scalars().all()
        
        # Convert ORM models to dicts for Pydantic serialization
        items_dict = [
            {c.name: getattr(item, c.name) for c in item.__table__.columns}
            for item in items
        ]
        
        return PaginatedResponse(
            items=items_dict,
            total=total,
            skip=skip,
            limit=limit
        )
    
    def get_provisions(
        self,
        db: Session,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: str = "name",
        sort_order: str = "asc"
    ) -> PaginatedResponse:
        """
        Get all provisions (is_provision=True) for organization.
        
        Args:
            db: Database session
            organization_id: Organization UUID
            skip: Pagination offset
            limit: Pagination limit
            is_active: Filter by active status
            search: Search term
            sort_by: Sort field
            sort_order: Sort direction
            
        Returns:
            PaginatedResponse with provisions
        """
        # Base query with provision filter
        query = self._base_query(organization_id).where(
            self.model.is_provision == True
        )
        
        # Apply filters
        if is_active is not None:
            query = query.where(self.model.is_active == is_active)
        
        if search:
            query = self._apply_search_filter(query, search)
        
        # Get total count
        from sqlalchemy import func
        count_query = select(func.count()).select_from(query.subquery())
        total = db.execute(count_query).scalar_one()
        
        # Apply sorting
        sort_column = getattr(self.model, sort_by, self.model.name)
        if sort_order.lower() == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
        
        # Apply pagination
        query = query.offset(skip).limit(limit)
        
        # Execute
        result = db.execute(query)
        items = result.scalars().all()
        
        # Convert ORM models to dicts for Pydantic serialization
        items_dict = [
            {c.name: getattr(item, c.name) for c in item.__table__.columns}
            for item in items
        ]
        
        return PaginatedResponse(
            items=items_dict,
            total=total,
            skip=skip,
            limit=limit
        )
    
    def update_balance(
        self,
        db: Session,
        third_party_id: UUID,
        amount_delta: float,
        organization_id: UUID
    ) -> ThirdParty:
        """
        Update third party balance by delta amount.
        
        Note: Balance can be negative (represents debt).
        
        Args:
            db: Database session
            third_party_id: ThirdParty UUID
            amount_delta: Amount to add (positive) or subtract (negative)
            organization_id: Organization UUID
            
        Returns:
            Updated ThirdParty
            
        Raises:
            HTTPException: 404 if not found
        
        TODO: Create transaction record in Phase 2
        """
        # Get third party
        third_party = self.get_or_404(
            db,
            third_party_id,
            organization_id,
            detail="Tercero no encontrado"
        )
        
        # Update balance (negative balance = debt is allowed)
        # Convert float to Decimal for arithmetic
        amount_delta_decimal = Decimal(str(amount_delta))
        new_balance = third_party.current_balance + amount_delta_decimal
        third_party.current_balance = new_balance
        
        db.commit()
        db.refresh(third_party)
        
        # TODO: Create transaction record in Phase 2
        # transaction = ThirdPartyTransaction(
        #     third_party_id=third_party_id,
        #     amount=amount_delta,
        #     ...
        # )
        
        return third_party


# Instance for use in endpoints
third_party = CRUDThirdParty(ThirdParty)
