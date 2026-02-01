"""
CRUD operations for InventoryMovement model.

Note: Movements are immutable (no update/delete operations).
Corrections should create new adjustment movements.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from app.models.inventory_movement import InventoryMovement
from app.models.material import Material
from app.models.warehouse import Warehouse
from app.models.purchase import Purchase
from app.schemas.inventory_movement import InventoryMovementCreate
from app.services.base import CRUDBase, Select


class CRUDInventoryMovement(CRUDBase[InventoryMovement, InventoryMovementCreate, None]):
    """
    CRUD operations for InventoryMovement.
    
    Note: Movements are immutable audit records.
    - CREATE: Yes (create new movements)
    - UPDATE: No (movements are immutable)
    - DELETE: No (maintain complete audit trail)
    
    Corrections: Create new 'adjustment' type movements.
    """
    
    def create_from_purchase(
        self,
        db: Session,
        purchase: Purchase,
        organization_id: UUID
    ) -> List[InventoryMovement]:
        """
        Create inventory movements from purchase lines.
        
        This is typically called internally by purchase service.
        Creates one movement per purchase line.
        
        Args:
            db: Database session
            purchase: Purchase with loaded lines
            organization_id: Organization UUID
            
        Returns:
            List of created InventoryMovements
        """
        movements = []
        
        for line in purchase.lines:
            movement = InventoryMovement(
                organization_id=organization_id,
                material_id=line.material_id,
                warehouse_id=line.warehouse_id,
                movement_type="purchase",
                quantity=line.quantity,
                unit_cost=line.unit_price,
                reference_type="purchase",
                reference_id=purchase.id,
                date=purchase.date,
                notes=f"Purchase #{purchase.purchase_number}",
            )
            db.add(movement)
            movements.append(movement)
        
        db.flush()
        return movements
    
    def get_by_material(
        self,
        db: Session,
        material_id: UUID,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[InventoryMovement]:
        """
        Get all movements for a specific material.
        
        Returns movements ordered by date descending (newest first).
        """
        return db.query(InventoryMovement).options(
            joinedload(InventoryMovement.warehouse)
        ).filter(
            InventoryMovement.material_id == material_id,
            InventoryMovement.organization_id == organization_id
        ).order_by(
            InventoryMovement.date.desc()
        ).offset(skip).limit(limit).all()
    
    def get_by_warehouse(
        self,
        db: Session,
        warehouse_id: UUID,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[InventoryMovement]:
        """
        Get all movements for a specific warehouse.
        
        Returns movements ordered by date descending (newest first).
        """
        return db.query(InventoryMovement).options(
            joinedload(InventoryMovement.material)
        ).filter(
            InventoryMovement.warehouse_id == warehouse_id,
            InventoryMovement.organization_id == organization_id
        ).order_by(
            InventoryMovement.date.desc()
        ).offset(skip).limit(limit).all()
    
    def get_by_material_and_warehouse(
        self,
        db: Session,
        material_id: UUID,
        warehouse_id: UUID,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[InventoryMovement]:
        """
        Get movements for specific material in specific warehouse.
        
        Useful for stock reconciliation and detailed tracking.
        """
        return db.query(InventoryMovement).filter(
            InventoryMovement.material_id == material_id,
            InventoryMovement.warehouse_id == warehouse_id,
            InventoryMovement.organization_id == organization_id
        ).order_by(
            InventoryMovement.date.desc()
        ).offset(skip).limit(limit).all()
    
    def calculate_stock_at_date(
        self,
        db: Session,
        material_id: UUID,
        warehouse_id: UUID,
        date: datetime,
        organization_id: UUID
    ) -> Decimal:
        """
        Calculate material stock in warehouse at specific date.
        
        Sums all movements up to and including the specified date.
        Useful for historical stock queries and auditing.
        
        Args:
            db: Database session
            material_id: Material UUID
            warehouse_id: Warehouse UUID
            date: Calculate stock at this date (inclusive)
            organization_id: Organization UUID
            
        Returns:
            Stock quantity at specified date (Decimal)
        """
        # Sum all quantities where date <= specified date
        stock_query = select(
            func.coalesce(func.sum(InventoryMovement.quantity), Decimal("0"))
        ).where(
            InventoryMovement.material_id == material_id,
            InventoryMovement.warehouse_id == warehouse_id,
            InventoryMovement.date <= date,
            InventoryMovement.organization_id == organization_id
        )
        
        stock = db.execute(stock_query).scalar_one()
        
        return stock
    
    def get_by_reference(
        self,
        db: Session,
        reference_type: str,
        reference_id: UUID,
        organization_id: UUID
    ) -> List[InventoryMovement]:
        """
        Get all movements linked to a specific transaction.
        
        Example: Get all movements for purchase_id="xxx"
        
        Args:
            db: Database session
            reference_type: 'purchase' | 'sale' | 'transfer' | etc.
            reference_id: Transaction UUID
            organization_id: Organization UUID
            
        Returns:
            List of related movements
        """
        return db.query(InventoryMovement).options(
            joinedload(InventoryMovement.material),
            joinedload(InventoryMovement.warehouse)
        ).filter(
            InventoryMovement.reference_type == reference_type,
            InventoryMovement.reference_id == reference_id,
            InventoryMovement.organization_id == organization_id
        ).order_by(
            InventoryMovement.created_at
        ).all()
    
    def get_movements_by_type(
        self,
        db: Session,
        movement_type: str,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[InventoryMovement]:
        """
        Get all movements of specific type.
        
        Args:
            db: Database session
            movement_type: 'purchase' | 'sale' | 'adjustment' | etc.
            organization_id: Organization UUID
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of movements filtered by type
        """
        return db.query(InventoryMovement).options(
            joinedload(InventoryMovement.material),
            joinedload(InventoryMovement.warehouse)
        ).filter(
            InventoryMovement.movement_type == movement_type,
            InventoryMovement.organization_id == organization_id
        ).order_by(
            InventoryMovement.date.desc()
        ).offset(skip).limit(limit).all()
    
    def get_movements_in_date_range(
        self,
        db: Session,
        start_date: datetime,
        end_date: datetime,
        organization_id: UUID,
        material_id: Optional[UUID] = None,
        warehouse_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[InventoryMovement]:
        """
        Get movements within date range with optional filters.
        
        Useful for reports and analytics.
        
        Args:
            db: Database session
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            organization_id: Organization UUID
            material_id: Optional material filter
            warehouse_id: Optional warehouse filter
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of movements in date range
        """
        query = db.query(InventoryMovement).options(
            joinedload(InventoryMovement.material),
            joinedload(InventoryMovement.warehouse)
        ).filter(
            InventoryMovement.date >= start_date,
            InventoryMovement.date <= end_date,
            InventoryMovement.organization_id == organization_id
        )
        
        if material_id:
            query = query.filter(InventoryMovement.material_id == material_id)
        
        if warehouse_id:
            query = query.filter(InventoryMovement.warehouse_id == warehouse_id)
        
        return query.order_by(
            InventoryMovement.date.desc()
        ).offset(skip).limit(limit).all()


# Instance for use in endpoints
inventory_movement = CRUDInventoryMovement(InventoryMovement)
