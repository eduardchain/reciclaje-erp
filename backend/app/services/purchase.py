"""
CRUD operations for Purchase model with business logic.

Supports 1-step and 2-step purchase workflows:
- 1-step: create() with auto_liquidate=True
- 2-step: create() then liquidate() separately
"""
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session, joinedload

from app.models.purchase import Purchase, PurchaseLine
from app.models.inventory_movement import InventoryMovement
from app.models.material import Material
from app.models.third_party import ThirdParty
from app.models.money_account import MoneyAccount
from app.models.warehouse import Warehouse
from app.schemas.purchase import PurchaseCreate, PurchaseUpdate
from app.services.base import CRUDBase


class CRUDPurchase(CRUDBase[Purchase, PurchaseCreate, PurchaseUpdate]):
    """CRUD operations for Purchase with inventory and financial logic."""
    
    def create(
        self,
        db: Session,
        obj_in: PurchaseCreate,
        organization_id: UUID
    ) -> Purchase:
        """
        Create purchase with lines, inventory movements, and balance updates.
        
        Workflow:
        1. Generate sequential purchase_number per organization
        2. Create Purchase with status='registered'
        3. For each line:
           - Create PurchaseLine
           - Create InventoryMovement (type='purchase')
           - Update Material.current_stock (add quantity)
           - Update Material.current_average_cost (weighted average)
        4. Update Supplier.current_balance (increase debt)
        5. Calculate and set purchase.total_amount
        6. If auto_liquidate=True, call liquidate()
        
        Args:
            db: Database session
            obj_in: Purchase creation data
            organization_id: Organization UUID
            
        Returns:
            Created Purchase with lines
            
        Raises:
            HTTPException: 404 if supplier/material/warehouse not found
            HTTPException: 403 if resources don't belong to organization
        """
        # Step 1: Generate next purchase_number with lock
        purchase_number = self._generate_purchase_number(db, organization_id)
        
        # Step 2: Validate supplier
        supplier = db.get(ThirdParty, obj_in.supplier_id)
        if not supplier or supplier.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier not found"
            )
        if not supplier.is_supplier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ThirdParty is not a supplier"
            )
        
        # Step 3: Create Purchase
        purchase = Purchase(
            organization_id=organization_id,
            purchase_number=purchase_number,
            supplier_id=obj_in.supplier_id,
            date=obj_in.date,
            total_amount=Decimal("0.00"),
            status="registered",
            notes=obj_in.notes,
        )
        db.add(purchase)
        db.flush()  # Get purchase.id before creating lines
        
        print(f"📦 Created purchase #{purchase_number} with ID: {purchase.id}")
        
        # Step 4: Process each line
        total_amount = Decimal("0.00")
        
        for line_data in obj_in.lines:
            # Validate material
            material = db.get(Material, line_data.material_id)
            if not material or material.organization_id != organization_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Material {line_data.material_id} not found"
                )
            
            # Validate warehouse
            warehouse = db.get(Warehouse, line_data.warehouse_id)
            if not warehouse or warehouse.organization_id != organization_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Warehouse {line_data.warehouse_id} not found"
                )
            
            # Calculate line total
            quantity = Decimal(str(line_data.quantity))
            unit_price = Decimal(str(line_data.unit_price))
            line_total = quantity * unit_price
            total_amount += line_total
            
            # Create PurchaseLine
            purchase_line = PurchaseLine(
                purchase_id=purchase.id,
                material_id=line_data.material_id,
                warehouse_id=line_data.warehouse_id,
                quantity=quantity,
                unit_price=unit_price,
                total_price=line_total,
            )
            db.add(purchase_line)
            
            # Create InventoryMovement
            movement = InventoryMovement(
                organization_id=organization_id,
                material_id=line_data.material_id,
                warehouse_id=line_data.warehouse_id,
                movement_type="purchase",
                quantity=quantity,
                unit_cost=unit_price,
                reference_type="purchase",
                reference_id=purchase.id,
                date=obj_in.date,
                notes=f"Purchase #{purchase_number}",
            )
            db.add(movement)
            
            # Update Material stock and average cost
            self._update_material_stock_and_cost(
                material=material,
                quantity_delta=quantity,
                unit_cost=unit_price,
            )
            
            print(f"  📝 Line: {material.code} x {quantity} @ ${unit_price} = ${line_total}")
        
        # Step 5: Update purchase total
        purchase.total_amount = total_amount
        
        # Step 6: Update Supplier balance (increase debt)
        supplier.current_balance -= total_amount  # Negative balance = debt
        print(f"  💰 Supplier balance: {supplier.current_balance} (debt increased by ${total_amount})")
        
        db.flush()
        
        # Step 7: Auto-liquidate if requested
        if obj_in.auto_liquidate:
            print(f"  🔄 Auto-liquidating purchase...")
            purchase = self.liquidate(
                db=db,
                purchase_id=purchase.id,
                payment_account_id=obj_in.payment_account_id,
                organization_id=organization_id,
            )
        
        db.commit()
        db.refresh(purchase)
        
        return purchase
    
    def liquidate(
        self,
        db: Session,
        purchase_id: UUID,
        payment_account_id: UUID,
        organization_id: UUID
    ) -> Purchase:
        """
        Liquidate a registered purchase (change status to 'paid').
        
        Workflow:
        1. Validate purchase exists and status='registered'
        2. Validate payment account has sufficient funds
        3. Update purchase status to 'paid'
        4. Deduct amount from payment account
        5. Supplier balance already updated in create(), don't touch again
        
        Args:
            db: Database session
            purchase_id: Purchase UUID
            payment_account_id: Payment account UUID
            organization_id: Organization UUID
            
        Returns:
            Updated Purchase
            
        Raises:
            HTTPException: 400 if already liquidated/cancelled or insufficient funds
            HTTPException: 403 if account not from organization
            HTTPException: 404 if purchase/account not found
        """
        # Step 1: Get and validate purchase
        purchase = self.get_or_404(
            db,
            purchase_id,
            organization_id,
            detail="Purchase not found"
        )
        
        if purchase.status != "registered":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Purchase already {purchase.status}. Can only liquidate registered purchases."
            )
        
        # Step 2: Validate payment account
        payment_account = db.get(MoneyAccount, payment_account_id)
        if not payment_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment account not found"
            )
        
        if payment_account.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Payment account does not belong to your organization"
            )
        
        # Step 3: Validate sufficient funds
        if payment_account.current_balance < purchase.total_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient funds in payment account. Available: ${payment_account.current_balance}, Required: ${purchase.total_amount}"
            )
        
        # Step 4: Update purchase status and account
        purchase.status = "paid"
        purchase.payment_account_id = payment_account_id
        
        # Step 5: Deduct from payment account
        payment_account.current_balance -= purchase.total_amount
        
        print(f"💳 Liquidated purchase #{purchase.purchase_number} for ${purchase.total_amount}")
        print(f"   Account '{payment_account.name}' balance: ${payment_account.current_balance}")
        
        db.commit()
        db.refresh(purchase)
        
        return purchase
    
    def cancel(
        self,
        db: Session,
        purchase_id: UUID,
        organization_id: UUID
    ) -> Purchase:
        """
        Cancel a purchase and reverse all effects.
        
        Workflow:
        1. Validate purchase exists and can be cancelled
        2. Validate sufficient stock to reverse
        3. Update status to 'cancelled'
        4. Create reversal InventoryMovements (negative quantity)
        5. Revert Material.current_stock
        6. Revert Supplier.current_balance
        7. Note: Average cost NOT reverted (small imprecision acceptable)
        
        Args:
            db: Database session
            purchase_id: Purchase UUID
            organization_id: Organization UUID
            
        Returns:
            Cancelled Purchase
            
        Raises:
            HTTPException: 400 if already cancelled, paid, or insufficient stock
            HTTPException: 404 if not found
        """
        # Step 1: Get and validate purchase
        purchase = db.query(Purchase).options(
            joinedload(Purchase.lines).joinedload(PurchaseLine.material)
        ).filter(
            Purchase.id == purchase_id,
            Purchase.organization_id == organization_id
        ).first()
        
        if not purchase:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase not found"
            )
        
        if purchase.status == "cancelled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Purchase already cancelled"
            )
        
        if purchase.status == "paid":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel paid purchase. Create a reversal transaction instead."
            )
        
        # Step 2: Validate sufficient stock to reverse
        for line in purchase.lines:
            material = line.material
            if material.current_stock < line.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot cancel: insufficient stock for {material.code}. Current: {material.current_stock}, Required: {line.quantity}"
                )
        
        # Step 3: Update status
        purchase.status = "cancelled"
        
        # Step 4-5: Create reversal movements and revert stock
        for line in purchase.lines:
            material = line.material
            
            # Create reversal movement
            reversal = InventoryMovement(
                organization_id=organization_id,
                material_id=line.material_id,
                warehouse_id=line.warehouse_id,
                movement_type="purchase_reversal",
                quantity=-line.quantity,  # Negative = out
                unit_cost=line.unit_price,
                reference_type="purchase",
                reference_id=purchase.id,
                date=purchase.date,
                notes=f"Cancellation of purchase #{purchase.purchase_number}",
            )
            db.add(reversal)
            
            # Revert stock
            material.current_stock -= line.quantity
            
            # TODO Phase 3: Implement precise average cost reversal
            # For now, we accept small imprecision in average cost
            
            print(f"  ↩️  Reversed: {material.code} -{line.quantity} (new stock: {material.current_stock})")
        
        # Step 6: Revert supplier balance
        supplier = db.get(ThirdParty, purchase.supplier_id)
        supplier.current_balance += purchase.total_amount  # Reduce debt
        
        print(f"❌ Cancelled purchase #{purchase.purchase_number}")
        print(f"   Supplier balance: {supplier.current_balance} (debt reduced by ${purchase.total_amount})")
        
        db.commit()
        db.refresh(purchase)
        
        return purchase
    
    def get_with_details(
        self,
        db: Session,
        purchase_id: UUID,
        organization_id: UUID
    ) -> Purchase:
        """
        Get purchase with eager-loaded lines and related data.
        
        Includes:
        - Purchase lines with material and warehouse data
        - Supplier data
        - Payment account data (if liquidated)
        """
        purchase = db.query(Purchase).options(
            joinedload(Purchase.lines).joinedload(PurchaseLine.material),
            joinedload(Purchase.lines).joinedload(PurchaseLine.warehouse),
            joinedload(Purchase.supplier),
            joinedload(Purchase.payment_account),
        ).filter(
            Purchase.id == purchase_id,
            Purchase.organization_id == organization_id
        ).first()
        
        if not purchase:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase not found"
            )
        
        return purchase
    
    def get_by_number(
        self,
        db: Session,
        purchase_number: int,
        organization_id: UUID
    ) -> Optional[Purchase]:
        """Get purchase by purchase_number within organization."""
        return db.query(Purchase).filter(
            Purchase.purchase_number == purchase_number,
            Purchase.organization_id == organization_id
        ).first()
    
    def get_by_supplier(
        self,
        db: Session,
        supplier_id: UUID,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[Purchase]:
        """Get all purchases from a specific supplier."""
        return db.query(Purchase).filter(
            Purchase.supplier_id == supplier_id,
            Purchase.organization_id == organization_id
        ).order_by(Purchase.date.desc()).offset(skip).limit(limit).all()
    
    def get_by_status(
        self,
        db: Session,
        status: str,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[Purchase]:
        """Get all purchases with specific status."""
        return db.query(Purchase).filter(
            Purchase.status == status,
            Purchase.organization_id == organization_id
        ).order_by(Purchase.date.desc()).offset(skip).limit(limit).all()
    
    def _generate_purchase_number(self, db: Session, organization_id: UUID) -> int:
        """
        Generate next sequential purchase_number for organization.
        
        Uses PostgreSQL advisory locks to prevent race conditions in concurrent requests.
        
        Returns:
            Next purchase number (1, 2, 3, ...)
        """
        # Use PostgreSQL advisory lock to prevent race conditions
        # Convert UUID to integer for lock (use hash to ensure it fits in bigint)
        lock_id = hash(str(organization_id)) % (2**63)  # Ensure positive bigint
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
        
        # Get max purchase_number for this organization
        max_number_query = select(func.max(Purchase.purchase_number)).where(
            Purchase.organization_id == organization_id
        )
        
        max_number = db.execute(max_number_query).scalar_one_or_none()
        
        next_number = (max_number or 0) + 1
        
        return next_number
    
    def _update_material_stock_and_cost(
        self,
        material: Material,
        quantity_delta: Decimal,
        unit_cost: Decimal
    ) -> None:
        """
        Update material stock and average cost using weighted average formula.
        
        Formula for weighted average cost:
        new_cost = (old_stock × old_cost + new_quantity × new_cost) / (old_stock + new_quantity)
        
        Special cases:
        - If old_stock = 0, new_cost = unit_cost (first purchase)
        - If new_stock becomes 0 after removal, cost stays unchanged
        
        Args:
            material: Material to update
            quantity_delta: Quantity to add (positive) or remove (negative)
            unit_cost: Cost per unit of the delta
        """
        old_stock = material.current_stock
        old_cost = material.current_average_cost
        new_stock = old_stock + quantity_delta
        
        if quantity_delta > 0:  # Adding stock (purchase)
            if old_stock == 0:
                # First purchase: set cost directly
                new_cost = unit_cost
            else:
                # Weighted average formula
                total_old_value = old_stock * old_cost
                total_new_value = quantity_delta * unit_cost
                new_cost = (total_old_value + total_new_value) / new_stock
            
            material.current_average_cost = new_cost
        
        # Update stock (always)
        material.current_stock = new_stock
        
        print(f"    📊 {material.code}: stock {old_stock} → {new_stock}, cost ${old_cost} → ${material.current_average_cost}")


# Instance for use in endpoints
purchase = CRUDPurchase(Purchase)
