"""
CRUD operations for DoubleEntry (Pasa Mano) model with business logic.

Business Rules:
- Material does NOT enter inventory (no stock movements)
- Creates linked Purchase and Sale records (both status='registered')
- Updates supplier balance (debt increases)
- Updates customer balance (receivable increases)
- Commissions created but NOT paid (paid when sale is liquidated)
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func, text, or_, cast, String
from sqlalchemy.orm import Session, joinedload

from app.models.double_entry import DoubleEntry
from app.models.purchase import Purchase, PurchaseLine
from app.models.sale import Sale, SaleLine, SaleCommission
from app.models.material import Material
from app.models.third_party import ThirdParty
from app.schemas.double_entry import DoubleEntryCreate, DoubleEntryUpdate
from app.services.base import CRUDBase


class CRUDDoubleEntry(CRUDBase[DoubleEntry, DoubleEntryCreate, DoubleEntryUpdate]):
    """CRUD operations for DoubleEntry with business logic."""
    
    def create(
        self,
        db: Session,
        obj_in: DoubleEntryCreate,
        organization_id: UUID
    ) -> DoubleEntry:
        """
        Create double-entry operation with linked Purchase and Sale.
        
        Workflow:
        1. Generate sequential double_entry_number
        2. Validate supplier != customer
        3. Validate supplier.is_supplier and customer.is_customer
        4. Validate material belongs to organization
        5. Create Purchase (status='registered', no inventory movement)
        6. Create Sale (status='registered', no inventory movement)
        7. Create SaleCommissions (if provided, balances NOT updated)
        8. Update Supplier.current_balance (increase debt)
        9. Update Customer.current_balance (increase receivable)
        10. Create DoubleEntry linking Purchase and Sale
        11. Set status='completed'
        
        Args:
            db: Database session
            obj_in: DoubleEntry creation data
            organization_id: Organization UUID
            
        Returns:
            Created DoubleEntry with linked records
            
        Raises:
            HTTPException: 400 if supplier == customer or invalid data
            HTTPException: 404 if supplier/customer/material not found
            HTTPException: 403 if resources don't belong to organization
        """
        # Step 1: Generate next double_entry_number with advisory lock
        double_entry_number = self._generate_double_entry_number(db, organization_id)
        
        # Step 2: Validate supplier and customer are different
        if obj_in.supplier_id == obj_in.customer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Supplier and customer cannot be the same third party"
            )
        
        # Step 3: Validate supplier
        supplier = db.get(ThirdParty, obj_in.supplier_id)
        if not supplier or supplier.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier not found"
            )
        if not supplier.is_supplier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ThirdParty is not marked as supplier"
            )
        
        # Step 4: Validate customer
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
        
        # Step 5: Validate material
        material = db.get(Material, obj_in.material_id)
        if not material or material.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Material not found"
            )
        
        print(f"🔄 Creating double-entry #{double_entry_number}")
        print(f"   Material: {material.code} - {material.name}")
        print(f"   Supplier: {supplier.name}")
        print(f"   Customer: {customer.name}")
        print(f"   Quantity: {obj_in.quantity}")
        print(f"   Purchase: ${obj_in.purchase_unit_price}/unit")
        print(f"   Sale: ${obj_in.sale_unit_price}/unit")
        
        # Step 6: Calculate totals
        quantity = Decimal(str(obj_in.quantity))
        purchase_unit_price = Decimal(str(obj_in.purchase_unit_price))
        sale_unit_price = Decimal(str(obj_in.sale_unit_price))
        
        purchase_total = quantity * purchase_unit_price
        sale_total = quantity * sale_unit_price
        profit = sale_total - purchase_total
        
        print(f"   Purchase Total: ${purchase_total}")
        print(f"   Sale Total: ${sale_total}")
        print(f"   Gross Profit: ${profit}")
        
        # Step 7: Generate purchase_number and create Purchase
        purchase_number = self._generate_purchase_number(db, organization_id)
        
        purchase = Purchase(
            organization_id=organization_id,
            purchase_number=purchase_number,
            supplier_id=obj_in.supplier_id,
            date=datetime.combine(obj_in.date, datetime.min.time()),
            total_amount=purchase_total,
            status="registered",
            notes=f"Double-entry #{double_entry_number}" + (f" - {obj_in.notes}" if obj_in.notes else ""),
        )
        db.add(purchase)
        db.flush()  # Get purchase.id
        
        # Create PurchaseLine (warehouse_id=NULL for double-entry)
        purchase_line = PurchaseLine(
            purchase_id=purchase.id,
            material_id=obj_in.material_id,
            warehouse_id=None,  # No physical warehouse for double-entry
            quantity=quantity,
            unit_price=purchase_unit_price,
            total_price=purchase_total,
        )
        db.add(purchase_line)
        
        print(f"   ✅ Created Purchase #{purchase_number} (ID: {purchase.id})")
        
        # Step 8: Generate sale_number and create Sale
        sale_number = self._generate_sale_number(db, organization_id)
        
        sale = Sale(
            organization_id=organization_id,
            sale_number=sale_number,
            customer_id=obj_in.customer_id,
            warehouse_id=None,  # No physical warehouse for double-entry
            date=datetime.combine(obj_in.date, datetime.min.time()),
            vehicle_plate=obj_in.vehicle_plate,
            invoice_number=obj_in.invoice_number,
            total_amount=sale_total,
            status="registered",  # NOT 'paid' - must be liquidated separately
            notes=f"Double-entry #{double_entry_number}" + (f" - {obj_in.notes}" if obj_in.notes else ""),
        )
        db.add(sale)
        db.flush()  # Get sale.id
        
        # Create SaleLine (unit_cost = purchase_unit_price for profit calculation)
        sale_line = SaleLine(
            sale_id=sale.id,
            material_id=obj_in.material_id,
            quantity=quantity,
            unit_price=sale_unit_price,
            total_price=sale_total,
            unit_cost=purchase_unit_price,  # Use purchase price as cost for this operation
        )
        db.add(sale_line)
        
        print(f"   ✅ Created Sale #{sale_number} (ID: {sale.id})")
        
        # Step 9: Create SaleCommissions (if provided)
        if obj_in.commissions:
            for comm_data in obj_in.commissions:
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
                
                print(f"   💼 Commission: {comm_data.concept} - ${commission_amount} ({comm_data.commission_type})")
                print(f"      NOTE: Balance NOT updated (will be paid when sale is liquidated)")
        
        # Step 10: Update Supplier balance (increase debt - we owe them)
        supplier.current_balance -= purchase_total  # Negative balance = debt
        print(f"   💰 Supplier '{supplier.name}' balance: {supplier.current_balance + purchase_total} → {supplier.current_balance} (debt +${purchase_total})")
        
        # Step 11: Update Customer balance (increase receivable - they owe us)
        customer.current_balance += sale_total  # Positive balance = receivable
        print(f"   💰 Customer '{customer.name}' balance: {customer.current_balance - sale_total} → {customer.current_balance} (receivable +${sale_total})")
        
        # Step 12: Create DoubleEntry
        double_entry = DoubleEntry(
            organization_id=organization_id,
            double_entry_number=double_entry_number,
            date=obj_in.date,
            material_id=obj_in.material_id,
            quantity=quantity,
            supplier_id=obj_in.supplier_id,
            purchase_unit_price=purchase_unit_price,
            customer_id=obj_in.customer_id,
            sale_unit_price=sale_unit_price,
            invoice_number=obj_in.invoice_number,
            vehicle_plate=obj_in.vehicle_plate,
            notes=obj_in.notes,
            purchase_id=purchase.id,
            sale_id=sale.id,
            status="completed",
        )
        db.add(double_entry)
        db.flush()
        
        # Step 13: Update Purchase and Sale with double_entry_id
        purchase.double_entry_id = double_entry.id
        sale.double_entry_id = double_entry.id
        
        db.commit()
        db.refresh(double_entry)
        
        print(f"✅ Double-entry #{double_entry_number} completed successfully")
        print(f"   Profit: ${profit} ({double_entry.profit_margin:.2f}% margin)")
        
        return double_entry
    
    def cancel(
        self,
        db: Session,
        double_entry_id: UUID,
        organization_id: UUID
    ) -> DoubleEntry:
        """
        Cancel a double-entry operation and reverse all changes.
        
        Workflow:
        1. Validate double_entry status != 'cancelled'
        2. Validate linked Purchase and Sale are 'registered' (not paid)
        3. Update Purchase status to 'cancelled'
        4. Update Sale status to 'cancelled'
        5. Revert Supplier balance (subtract purchase total)
        6. Revert Customer balance (subtract sale total)
        7. Set double_entry status to 'cancelled'
        8. Note: NO inventory reversal (there was none)
        
        Args:
            db: Database session
            double_entry_id: DoubleEntry UUID
            organization_id: Organization UUID
            
        Returns:
            Cancelled DoubleEntry
            
        Raises:
            HTTPException: 404 if double_entry not found
            HTTPException: 400 if already cancelled or linked records are paid
        """
        # Step 1: Get double_entry
        double_entry = db.get(DoubleEntry, double_entry_id)
        if not double_entry or double_entry.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Double-entry operation not found"
            )
        
        # Step 2: Validate status
        if double_entry.status == "cancelled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Double-entry operation is already cancelled"
            )
        
        # Step 3: Get linked Purchase and Sale
        purchase = db.get(Purchase, double_entry.purchase_id)
        sale = db.get(Sale, double_entry.sale_id)
        
        if not purchase or not sale:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Linked purchase or sale not found"
            )
        
        # Step 4: Validate Purchase and Sale are not paid
        if purchase.status == "paid":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel: Purchase #{purchase.purchase_number} is already paid"
            )
        
        if sale.status == "paid":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel: Sale #{sale.sale_number} is already paid"
            )
        
        print(f"❌ Cancelling double-entry #{double_entry.double_entry_number}")
        
        # Step 5: Update Purchase status
        purchase.status = "cancelled"
        print(f"   ❌ Cancelled Purchase #{purchase.purchase_number}")
        
        # Step 6: Update Sale status
        sale.status = "cancelled"
        print(f"   ❌ Cancelled Sale #{sale.sale_number}")
        
        # Step 7: Revert Supplier balance
        supplier = db.get(ThirdParty, double_entry.supplier_id)
        supplier.current_balance += double_entry.total_purchase_cost  # Reduce debt
        print(f"   💰 Supplier balance reverted: {supplier.current_balance - double_entry.total_purchase_cost} → {supplier.current_balance}")
        
        # Step 8: Revert Customer balance
        customer = db.get(ThirdParty, double_entry.customer_id)
        customer.current_balance -= double_entry.total_sale_amount  # Reduce receivable
        print(f"   💰 Customer balance reverted: {customer.current_balance + double_entry.total_sale_amount} → {customer.current_balance}")
        
        # Step 9: Update double_entry status
        double_entry.status = "cancelled"
        
        # Note: NO inventory movements to reverse (there were none)
        # Note: Commissions were never paid (sale was 'registered', not 'paid')
        
        db.commit()
        db.refresh(double_entry)
        
        print(f"✅ Double-entry #{double_entry.double_entry_number} cancelled successfully")
        
        return double_entry
    
    def get(
        self,
        db: Session,
        double_entry_id: UUID,
        organization_id: UUID
    ) -> Optional[DoubleEntry]:
        """
        Get a single double_entry by ID with eager loading.
        
        Returns None if not found or doesn't belong to organization.
        """
        return db.query(DoubleEntry).options(
            joinedload(DoubleEntry.material),
            joinedload(DoubleEntry.supplier),
            joinedload(DoubleEntry.customer),
            joinedload(DoubleEntry.sale).joinedload(Sale.commissions).joinedload(SaleCommission.third_party),
        ).filter(
            DoubleEntry.id == double_entry_id,
            DoubleEntry.organization_id == organization_id
        ).first()
    
    def get_by_number(
        self,
        db: Session,
        double_entry_number: int,
        organization_id: UUID
    ) -> Optional[DoubleEntry]:
        """Get double_entry by sequential number within organization."""
        return db.query(DoubleEntry).options(
            joinedload(DoubleEntry.material),
            joinedload(DoubleEntry.supplier),
            joinedload(DoubleEntry.customer),
            joinedload(DoubleEntry.sale).joinedload(Sale.commissions).joinedload(SaleCommission.third_party),
        ).filter(
            DoubleEntry.double_entry_number == double_entry_number,
            DoubleEntry.organization_id == organization_id
        ).first()
    
    def get_by_supplier(
        self,
        db: Session,
        supplier_id: UUID,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[DoubleEntry], int]:
        """Get double_entries by supplier with pagination."""
        query = db.query(DoubleEntry).filter(
            DoubleEntry.supplier_id == supplier_id,
            DoubleEntry.organization_id == organization_id
        )
        
        total = query.count()
        
        double_entries = query.options(
            joinedload(DoubleEntry.material),
            joinedload(DoubleEntry.supplier),
            joinedload(DoubleEntry.customer),
            joinedload(DoubleEntry.sale).joinedload(Sale.commissions).joinedload(SaleCommission.third_party),
        ).order_by(DoubleEntry.date.desc()).offset(skip).limit(limit).all()
        
        return double_entries, total
    
    def get_by_customer(
        self,
        db: Session,
        customer_id: UUID,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[DoubleEntry], int]:
        """Get double_entries by customer with pagination."""
        query = db.query(DoubleEntry).filter(
            DoubleEntry.customer_id == customer_id,
            DoubleEntry.organization_id == organization_id
        )
        
        total = query.count()
        
        double_entries = query.options(
            joinedload(DoubleEntry.material),
            joinedload(DoubleEntry.supplier),
            joinedload(DoubleEntry.customer),
            joinedload(DoubleEntry.sale).joinedload(Sale.commissions).joinedload(SaleCommission.third_party),
        ).order_by(DoubleEntry.date.desc()).offset(skip).limit(limit).all()
        
        return double_entries, total
    
    def get_multi(
        self,
        db: Session,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        material_id: Optional[UUID] = None,
        supplier_id: Optional[UUID] = None,
        customer_id: Optional[UUID] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        search: Optional[str] = None
    ) -> tuple[List[DoubleEntry], int]:
        """
        Get multiple double_entries with filtering and pagination.
        
        Search in: double_entry_number, supplier name, customer name, notes, invoice_number
        
        Returns:
            Tuple of (double_entries, total_count)
        """
        # Base query
        query = db.query(DoubleEntry).filter(
            DoubleEntry.organization_id == organization_id
        )
        
        # Apply filters
        if status:
            query = query.filter(DoubleEntry.status == status)
        
        if material_id:
            query = query.filter(DoubleEntry.material_id == material_id)
        
        if supplier_id:
            query = query.filter(DoubleEntry.supplier_id == supplier_id)
        
        if customer_id:
            query = query.filter(DoubleEntry.customer_id == customer_id)
        
        if date_from:
            query = query.filter(DoubleEntry.date >= date_from)
        
        if date_to:
            query = query.filter(DoubleEntry.date <= date_to)
        
        # Search filter (double_entry_number, notes, invoice_number)
        # Note: Searching by supplier/customer name requires JOINs that conflict with eager loading
        if search:
            from sqlalchemy import func
            query = query.filter(
                or_(
                    cast(DoubleEntry.double_entry_number, String).ilike(f"%{search}%"),
                    func.coalesce(DoubleEntry.notes, '').ilike(f"%{search}%"),
                    func.coalesce(DoubleEntry.invoice_number, '').ilike(f"%{search}%"),
                )
            )
        
        # Get total count
        total = query.count()
        
        # Apply eager loading, ordering, and pagination
        double_entries = query.options(
            joinedload(DoubleEntry.material),
            joinedload(DoubleEntry.supplier),
            joinedload(DoubleEntry.customer),
            joinedload(DoubleEntry.sale).joinedload(Sale.commissions).joinedload(SaleCommission.third_party),
        ).order_by(DoubleEntry.date.desc()).offset(skip).limit(limit).all()
        
        return double_entries, total
    
    def update(
        self,
        db: Session,
        double_entry_id: UUID,
        obj_in: DoubleEntryUpdate,
        organization_id: UUID
    ) -> DoubleEntry:
        """
        Update double_entry metadata (notes, invoice_number, vehicle_plate only).
        
        Args:
            db: Database session
            double_entry_id: DoubleEntry UUID
            obj_in: Update data
            organization_id: Organization UUID
            
        Returns:
            Updated DoubleEntry
            
        Raises:
            HTTPException: 404 if not found
        """
        double_entry = db.get(DoubleEntry, double_entry_id)
        if not double_entry or double_entry.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Double-entry operation not found"
            )
        
        # Update fields
        if obj_in.notes is not None:
            double_entry.notes = obj_in.notes
        if obj_in.invoice_number is not None:
            double_entry.invoice_number = obj_in.invoice_number
        if obj_in.vehicle_plate is not None:
            double_entry.vehicle_plate = obj_in.vehicle_plate
        
        db.commit()
        db.refresh(double_entry)
        
        return double_entry
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def _generate_double_entry_number(
        self,
        db: Session,
        organization_id: UUID
    ) -> int:
        """
        Generate next sequential double_entry_number for organization.
        
        Uses advisory lock to prevent race conditions.
        """
        # Acquire advisory lock
        lock_id = hash(f"double_entries_{organization_id}") % (2**31)
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
        
        # Get max number
        result = db.execute(
            text("""
                SELECT COALESCE(MAX(double_entry_number), 0) + 1
                FROM double_entries
                WHERE organization_id = :org_id
            """),
            {"org_id": str(organization_id)}
        ).scalar()
        
        return result
    
    def _generate_purchase_number(
        self,
        db: Session,
        organization_id: UUID
    ) -> int:
        """Generate next sequential purchase_number for organization."""
        lock_id = hash(f"purchases_{organization_id}") % (2**31)
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
        
        result = db.execute(
            text("""
                SELECT COALESCE(MAX(purchase_number), 0) + 1
                FROM purchases
                WHERE organization_id = :org_id
            """),
            {"org_id": str(organization_id)}
        ).scalar()
        
        return result
    
    def _generate_sale_number(
        self,
        db: Session,
        organization_id: UUID
    ) -> int:
        """Generate next sequential sale_number for organization."""
        lock_id = hash(f"sales_{organization_id}") % (2**31)
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
        
        result = db.execute(
            text("""
                SELECT COALESCE(MAX(sale_number), 0) + 1
                FROM sales
                WHERE organization_id = :org_id
            """),
            {"org_id": str(organization_id)}
        ).scalar()
        
        return result
    
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
            Commission amount
        """
        if commission_type == "percentage":
            return (commission_value / Decimal("100")) * sale_total
        elif commission_type == "fixed":
            return commission_value
        else:
            raise ValueError(f"Invalid commission_type: {commission_type}")
    
# Create singleton instance
crud_double_entry = CRUDDoubleEntry(DoubleEntry)
double_entry = CRUDDoubleEntry(DoubleEntry)
