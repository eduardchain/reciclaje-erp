"""
CRUD operations for Sale model with business logic.

Supports 1-step and 2-step sale workflows:
- 1-step: create() with auto_liquidate=True
- 2-step: create() then liquidate() separately

Business Rules:
- Stock decreases immediately on sale creation
- Customer balance increases (they owe us)
- unit_cost captured at moment of sale for profit tracking
- Commission balances increase when sale is liquidated
- Paid sales cannot be cancelled (require reversal sale)
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session, joinedload

from app.models.sale import Sale, SaleLine, SaleCommission
from app.models.inventory_movement import InventoryMovement
from app.models.material import Material
from app.models.third_party import ThirdParty
from app.models.money_account import MoneyAccount
from app.models.warehouse import Warehouse
from app.schemas.sale import SaleCreate, SaleUpdate
from app.services.base import CRUDBase


class CRUDSale(CRUDBase[Sale, SaleCreate, SaleUpdate]):
    """CRUD operations for Sale with inventory, financial, and commission logic."""
    
    def create(
        self,
        db: Session,
        obj_in: SaleCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None
    ) -> Sale:
        """
        Create sale with lines, inventory movements, commissions, and balance updates.
        
        Workflow:
        1. Generate sequential sale_number per organization
        2. Validate customer, warehouse, materials, and stock availability
        3. Create Sale with status='registered'
        4. For each line:
           - Validate Material.current_stock >= line.quantity
           - Create SaleLine
           - Capture unit_cost from Material.current_average_cost
           - Create InventoryMovement (type='sale', quantity negative)
           - Update Material.current_stock (subtract quantity)
        5. Create SaleCommissions (calculate amounts)
        6. Update Customer.current_balance (increase debt)
        7. Calculate and set sale.total_amount
        8. If auto_liquidate=True, call liquidate()
        
        Args:
            db: Database session
            obj_in: Sale creation data
            organization_id: Organization UUID
            
        Returns:
            Created Sale with lines and commissions
            
        Raises:
            HTTPException: 404 if customer/material/warehouse not found
            HTTPException: 403 if resources don't belong to organization
            HTTPException: 400 if insufficient stock or invalid data
        """
        # Step 1: Generate next sale_number with advisory lock
        sale_number = self._generate_sale_number(db, organization_id)
        
        # Check if this is a double-entry sale (skip inventory movements)
        is_double_entry = hasattr(obj_in, 'double_entry_id') and obj_in.double_entry_id is not None
        
        # Step 2: Validate customer
        customer = db.get(ThirdParty, obj_in.customer_id)
        if not customer or customer.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )
        if not customer.is_customer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ThirdParty is not marked as customer"
            )
        
        # Step 3: Validate warehouse (skip for double-entry)
        if not is_double_entry:
            if not obj_in.warehouse_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="warehouse_id is required for normal sales"
                )
            warehouse = db.get(Warehouse, obj_in.warehouse_id)
            if not warehouse or warehouse.organization_id != organization_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Warehouse not found"
                )
        
        # Step 4: Validate stock availability for all materials BEFORE creating anything (skip for double-entry)
        # RN-INV-03: Stock negativo PERMITIDO con warning (no bloquea la operacion)
        warnings: list[str] = []
        if not is_double_entry:
            for line_data in obj_in.lines:
                material = db.get(Material, line_data.material_id)
                if not material or material.organization_id != organization_id:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Material {line_data.material_id} not found"
                    )

                if material.current_stock_liquidated < line_data.quantity:
                    resulting_stock = material.current_stock_liquidated - line_data.quantity
                    warnings.append(
                        f"Insufficient stock for '{material.name}'. "
                        f"Available: {material.current_stock_liquidated}, "
                        f"Required: {line_data.quantity}. "
                        f"Stock will be {resulting_stock}"
                    )
        
        # Step 5: Create Sale
        sale = Sale(
            organization_id=organization_id,
            sale_number=sale_number,
            customer_id=obj_in.customer_id,
            warehouse_id=obj_in.warehouse_id,  # Can be None for double-entry
            date=obj_in.date,
            vehicle_plate=obj_in.vehicle_plate,
            invoice_number=obj_in.invoice_number,
            total_amount=Decimal("0.00"),
            status="registered",
            notes=obj_in.notes,
            created_by=user_id,
            double_entry_id=obj_in.double_entry_id if is_double_entry else None,
        )
        db.add(sale)
        db.flush()  # Get sale.id before creating lines
        
        if is_double_entry:
            print(f"📦 Created double-entry sale #{sale_number} with ID: {sale.id} (no inventory movement)")
        else:
            print(f"📦 Created sale #{sale_number} with ID: {sale.id}")
        
        # Step 6: Process each line
        total_amount = Decimal("0.00")
        
        for line_data in obj_in.lines:
            material = db.get(Material, line_data.material_id)
            if not material or material.organization_id != organization_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Material {line_data.material_id} not found"
                )
            
            # Calculate line total
            line_total = line_data.quantity * line_data.unit_price
            total_amount += line_total
            
            # Capture current average cost for profit calculation
            # For double-entry, unit_cost comes from line_data (set by double_entry service)
            if is_double_entry and hasattr(line_data, 'unit_cost'):
                unit_cost = line_data.unit_cost
            else:
                unit_cost = material.current_average_cost
            
            # Create SaleLine
            sale_line = SaleLine(
                sale_id=sale.id,
                material_id=line_data.material_id,
                quantity=line_data.quantity,
                unit_price=line_data.unit_price,
                total_price=line_total,
                unit_cost=unit_cost,
            )
            db.add(sale_line)
            
            # Skip inventory operations for double-entry
            if not is_double_entry:
                # Create InventoryMovement (negative quantity = material leaving)
                inventory_movement = InventoryMovement(
                    organization_id=organization_id,
                    material_id=line_data.material_id,
                    warehouse_id=obj_in.warehouse_id,
                    movement_type="sale",
                    quantity=-line_data.quantity,  # Negative = exit
                    unit_cost=unit_cost,
                    reference_type="sale",
                    reference_id=sale.id,
                    date=obj_in.date,
                    notes=f"Sale #{sale_number}",
                )
                db.add(inventory_movement)
                
                # Update material stock (decrease from liquidated and total)
                material.current_stock -= line_data.quantity
                material.current_stock_liquidated -= line_data.quantity
                # Note: Do NOT update current_average_cost on sales, only on purchases
                
                print(f"  📤 Sold {line_data.quantity} of {material.name} @ ${line_data.unit_price}/unit (cost: ${unit_cost})")
                print(f"     Stock: {material.current_stock + line_data.quantity} → {material.current_stock}")
            else:
                print(f"  📝 Line: {material.code} x {line_data.quantity} @ ${line_data.unit_price} (cost: ${unit_cost})")
        
        # Step 7: Update sale total
        sale.total_amount = total_amount
        
        # Step 8: Process commissions
        if obj_in.commissions:
            self._process_commissions(db, sale, obj_in.commissions, total_amount, organization_id)
        
        # Step 9: Update customer balance (increase debt)
        customer.current_balance += total_amount
        print(f"💰 Customer balance: ${customer.current_balance - total_amount} → ${customer.current_balance}")
        
        db.flush()
        
        # Step 10: If auto_liquidate, liquidate immediately
        if obj_in.auto_liquidate:
            print(f"⚡ Auto-liquidating sale #{sale_number}")
            sale = self.liquidate(db, sale.id, obj_in.payment_account_id, organization_id, user_id=user_id)

        # Attach warnings as transient attribute (no se persiste en BD)
        sale._warnings = warnings
        return sale
    
    def liquidate(
        self,
        db: Session,
        sale_id: UUID,
        payment_account_id: UUID,
        organization_id: UUID,
        user_id: Optional[UUID] = None
    ) -> Sale:
        """
        Liquidate a registered sale (mark as paid and process payments).
        
        Workflow:
        1. Validate sale status is 'registered'
        2. Validate payment account belongs to organization
        3. Update sale status to 'paid'
        4. Credit payment account (receive money)
        5. Debit customer balance (they paid)
        6. Pay commissions (increase recipient balances)
        
        Args:
            db: Database session
            sale_id: Sale UUID
            payment_account_id: Payment account to receive funds
            organization_id: Organization UUID
            
        Returns:
            Updated Sale with status='paid'
            
        Raises:
            HTTPException: 404 if sale/account not found
            HTTPException: 400 if sale is not 'registered'
        """
        # Step 1: Get sale
        sale = db.get(Sale, sale_id)
        if not sale or sale.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sale not found"
            )
        
        # Validate: Cannot liquidate sale that belongs to double-entry
        if sale.double_entry_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot liquidate sale that belongs to a double-entry operation. Manage it through the double-entry instead."
            )
        
        # Step 2: Validate status
        if sale.status != "registered":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot liquidate sale with status '{sale.status}'. Must be 'registered'"
            )
        
        # Step 3: Validate payment account
        payment_account = db.get(MoneyAccount, payment_account_id)
        if not payment_account or payment_account.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment account not found"
            )
        
        # Step 4: Update sale
        sale.status = "paid"
        sale.payment_account_id = payment_account_id
        sale.liquidated_by = user_id
        
        # Step 5: Update payment account balance (receive payment)
        payment_account.current_balance += sale.total_amount
        print(f"💳 Payment account '{payment_account.name}': ${payment_account.current_balance - sale.total_amount} → ${payment_account.current_balance}")
        
        # Step 6: Update customer balance (they paid their debt)
        customer = db.get(ThirdParty, sale.customer_id)
        customer.current_balance -= sale.total_amount
        print(f"👤 Customer '{customer.name}' balance: ${customer.current_balance + sale.total_amount} → ${customer.current_balance}")
        
        # Step 7: Pay commissions (increase recipient balances)
        self._pay_commissions(db, sale)
        
        db.flush()
        
        print(f"✅ Sale #{sale.sale_number} liquidated successfully")
        
        return sale
    
    def cancel(
        self,
        db: Session,
        sale_id: UUID,
        organization_id: UUID
    ) -> Sale:
        """
        Cancel a sale and reverse all changes.
        
        Rules:
        - Can only cancel sales with status='registered'
        - Paid sales cannot be cancelled (require reversal sale instead)
        
        Workflow:
        1. Validate sale status is 'registered' (not paid)
        2. Update status to 'cancelled'
        3. Create reversal inventory movements
        4. Restore material stock
        5. Revert customer balance
        
        Args:
            db: Database session
            sale_id: Sale UUID
            organization_id: Organization UUID
            
        Returns:
            Cancelled Sale
            
        Raises:
            HTTPException: 404 if sale not found
            HTTPException: 400 if sale is paid or already cancelled
        """
        # Step 1: Get sale with lines
        sale = db.get(Sale, sale_id)
        if not sale or sale.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sale not found"
            )
        
        # Validate: Cannot cancel sale that belongs to double-entry
        if sale.double_entry_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel sale that belongs to a double-entry operation. Cancel the double-entry instead."
            )
        
        # Step 2: Validate status
        if sale.status == "cancelled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sale is already cancelled"
            )
        
        if sale.status == "paid":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel paid sale. Create a reversal sale instead"
            )
        
        # Step 3: Load lines
        stmt = select(SaleLine).where(SaleLine.sale_id == sale_id)
        lines = db.scalars(stmt).all()
        
        # Step 4: Update status
        sale.status = "cancelled"
        
        # Step 5: Reverse inventory movements and restore stock
        for line in lines:
            material = db.get(Material, line.material_id)
            
            # Create reversal movement (positive quantity = material returning)
            reversal_movement = InventoryMovement(
                organization_id=organization_id,
                material_id=line.material_id,
                warehouse_id=sale.warehouse_id,
                movement_type="sale_reversal",
                quantity=line.quantity,  # Positive = entry
                unit_cost=line.unit_cost,
                reference_type="sale",
                reference_id=sale.id,
                date=datetime.now(),
                notes=f"Reversal of sale #{sale.sale_number}",
            )
            db.add(reversal_movement)
            
            # Restore material stock (to liquidated and total)
            material.current_stock += line.quantity
            material.current_stock_liquidated += line.quantity
            print(f"  🔄 Restored {line.quantity} of {material.name}, stock: {material.current_stock - line.quantity} → {material.current_stock}")
        
        # Step 6: Revert customer balance
        customer = db.get(ThirdParty, sale.customer_id)
        customer.current_balance -= sale.total_amount
        print(f"👤 Customer '{customer.name}' balance reverted: ${customer.current_balance + sale.total_amount} → ${customer.current_balance}")
        
        # Note: Commissions are NOT reverted because they were never paid
        # (sale was 'registered', not 'paid')
        
        db.flush()
        
        print(f"❌ Sale #{sale.sale_number} cancelled successfully")
        
        return sale
    
    def get_by_number(
        self,
        db: Session,
        sale_number: int,
        organization_id: UUID
    ) -> Optional[Sale]:
        """Get sale by sale_number within organization."""
        stmt = (
            select(Sale)
            .where(
                Sale.organization_id == organization_id,
                Sale.sale_number == sale_number
            )
            .options(
                joinedload(Sale.lines),
                joinedload(Sale.commissions)
            )
        )
        return db.scalar(stmt)
    
    def get_by_customer(
        self,
        db: Session,
        customer_id: UUID,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[Sale]:
        """Get all sales for a specific customer."""
        stmt = (
            select(Sale)
            .where(
                Sale.organization_id == organization_id,
                Sale.customer_id == customer_id
            )
            .options(
                joinedload(Sale.lines),
                joinedload(Sale.commissions)
            )
            .order_by(Sale.date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.scalars(stmt).all())
    
    def get_by_status(
        self,
        db: Session,
        status: str,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[Sale]:
        """Get all sales with specific status."""
        stmt = (
            select(Sale)
            .where(
                Sale.organization_id == organization_id,
                Sale.status == status
            )
            .options(
                joinedload(Sale.lines),
                joinedload(Sale.commissions)
            )
            .order_by(Sale.date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.scalars(stmt).all())
    
    def get_multi(
        self,
        db: Session,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        customer_id: Optional[UUID] = None,
        warehouse_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        search: Optional[str] = None
    ) -> tuple[List[Sale], int]:
        """
        Get multiple sales with filtering and pagination.
        
        Args:
            db: Database session
            organization_id: Organization UUID
            skip: Number of records to skip
            limit: Maximum records to return
            status: Filter by status
            customer_id: Filter by customer
            warehouse_id: Filter by warehouse
            date_from: Filter sales on or after this date
            date_to: Filter sales on or before this date
            search: Search in sale_number, customer name, notes, vehicle_plate, invoice_number
        
        Returns:
            Tuple of (sales, total_count)
        """
        from sqlalchemy import or_, cast, String
        
        # Base query
        query = select(Sale).where(Sale.organization_id == organization_id)
        
        # Apply filters
        if status:
            query = query.where(Sale.status == status)
        
        if customer_id:
            query = query.where(Sale.customer_id == customer_id)
        
        if warehouse_id:
            query = query.where(Sale.warehouse_id == warehouse_id)
        
        if date_from:
            query = query.where(Sale.date >= date_from)
        
        if date_to:
            query = query.where(Sale.date <= date_to)
        
        if search:
            # Search in: sale_number (as text), customer name, notes, vehicle_plate, invoice_number
            query = query.join(Sale.customer).where(
                or_(
                    cast(Sale.sale_number, String).ilike(f"%{search}%"),
                    ThirdParty.name.ilike(f"%{search}%"),
                    Sale.notes.ilike(f"%{search}%"),
                    Sale.vehicle_plate.ilike(f"%{search}%"),
                    Sale.invoice_number.ilike(f"%{search}%")
                )
            )
        
        # Get total count before pagination
        count_query = select(func.count()).select_from(query.subquery())
        total = db.scalar(count_query)
        
        # Apply pagination and eager loading
        query = (
            query
            .options(
                joinedload(Sale.lines).joinedload(SaleLine.material),
                joinedload(Sale.commissions).joinedload(SaleCommission.third_party),
                joinedload(Sale.customer),
                joinedload(Sale.warehouse),
                joinedload(Sale.payment_account),
            )
            .order_by(Sale.date.desc(), Sale.sale_number.desc())
            .offset(skip)
            .limit(limit)
        )
        
        sales = list(db.scalars(query).unique().all())
        
        return sales, total
    
    def get(
        self,
        db: Session,
        sale_id: UUID,
        organization_id: UUID
    ) -> Optional[Sale]:
        """
        Get a single sale by ID with eager loading.
        
        Returns None if not found or doesn't belong to organization.
        """
        stmt = (
            select(Sale)
            .where(
                Sale.id == sale_id,
                Sale.organization_id == organization_id
            )
            .options(
                joinedload(Sale.lines).joinedload(SaleLine.material),
                joinedload(Sale.commissions).joinedload(SaleCommission.third_party),
                joinedload(Sale.customer),
                joinedload(Sale.warehouse),
                joinedload(Sale.payment_account),
            )
        )
        return db.scalar(stmt)
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def _generate_sale_number(self, db: Session, organization_id: UUID) -> int:
        """
        Generate next sequential sale number for organization.
        
        Uses PostgreSQL advisory lock to prevent race conditions.
        Lock is automatically released at transaction end.
        
        Args:
            db: Database session
            organization_id: Organization UUID
            
        Returns:
            Next sale number (1, 2, 3, ...)
        """
        # Acquire advisory lock for this organization's sales
        lock_id = hash(f"{organization_id}-sales") % (2**31)
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
        
        # Get max sale number
        stmt = select(func.max(Sale.sale_number)).where(
            Sale.organization_id == organization_id
        )
        max_number = db.scalar(stmt)
        
        next_number = (max_number or 0) + 1
        print(f"🔢 Generated sale number: {next_number}")
        
        return next_number
    
    def _process_commissions(
        self,
        db: Session,
        sale: Sale,
        commissions_data: List,
        sale_total: Decimal,
        organization_id: UUID
    ) -> None:
        """
        Create commission records and calculate amounts.
        
        Args:
            db: Database session
            sale: Sale instance
            commissions_data: List of SaleCommissionCreate
            sale_total: Total sale amount for percentage calculations
            organization_id: Organization UUID
            
        Raises:
            HTTPException: 404 if commission recipient not found
        """
        for comm_data in commissions_data:
            # Validate commission recipient
            recipient = db.get(ThirdParty, comm_data.third_party_id)
            if not recipient or recipient.organization_id != organization_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Commission recipient {comm_data.third_party_id} not found"
                )
            
            # Calculate commission amount
            commission_amount = self._calculate_commission(
                comm_data.commission_type,
                comm_data.commission_value,
                sale_total
            )
            
            # Create commission record
            commission = SaleCommission(
                sale_id=sale.id,
                third_party_id=comm_data.third_party_id,
                concept=comm_data.concept,
                commission_type=comm_data.commission_type,
                commission_value=comm_data.commission_value,
                commission_amount=commission_amount,
            )
            db.add(commission)
            
            print(f"  💼 Commission: {comm_data.concept} - ${commission_amount} ({comm_data.commission_type})")
    
    def _calculate_commission(
        self,
        commission_type: str,
        commission_value: Decimal,
        sale_total: Decimal
    ) -> Decimal:
        """
        Calculate commission amount based on type and value.
        
        Args:
            commission_type: 'percentage' or 'fixed'
            commission_value: Percentage (0-100) or fixed amount
            sale_total: Total sale amount
            
        Returns:
            Calculated commission amount
        """
        if commission_type == "percentage":
            return (sale_total * commission_value) / Decimal("100")
        else:  # fixed
            return commission_value
    
    def delete(
        self,
        db: Session,
        id: UUID,
        organization_id: UUID
    ) -> Sale:
        """
        Soft delete sale (set is_active = False).
        
        Validates that sale is not part of a double-entry operation.
        
        Args:
            db: Database session
            id: Sale UUID
            organization_id: Organization UUID
            
        Returns:
            Deleted (deactivated) sale instance
            
        Raises:
            HTTPException: 400 if sale belongs to double-entry
            HTTPException: 404 if not found
        """
        # Get existing sale
        sale = self.get(db, id, organization_id)
        if not sale:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sale not found"
            )
        
        # Validate: Cannot delete sale that belongs to double-entry
        if sale.double_entry_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete sale that belongs to a double-entry operation. Cancel the double-entry instead."
            )
        
        # Soft delete
        sale.is_active = False
        
        # Commit changes
        db.commit()
        db.refresh(sale)
        
        return sale
    
    def _pay_commissions(self, db: Session, sale: Sale) -> None:
        """
        Pay commissions by increasing recipient balances.
        
        Called during liquidate() to process commission payments.
        
        Args:
            db: Database session
            sale: Sale instance with loaded commissions
        """
        # Load commissions if not already loaded
        stmt = select(SaleCommission).where(SaleCommission.sale_id == sale.id)
        commissions = db.scalars(stmt).all()
        
        for commission in commissions:
            recipient = db.get(ThirdParty, commission.third_party_id)
            
            # Increase recipient balance (we owe them the commission)
            recipient.current_balance += commission.commission_amount
            
            print(f"  💼 Paid commission to '{recipient.name}': ${commission.commission_amount} ({commission.concept})")
            print(f"     Balance: ${recipient.current_balance - commission.commission_amount} → ${recipient.current_balance}")


# Create singleton instance
crud_sale = CRUDSale(Sale)
