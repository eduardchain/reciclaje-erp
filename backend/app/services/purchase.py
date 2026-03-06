"""
CRUD operations for Purchase model with business logic.

Supports 1-step and 2-step purchase workflows:
- 1-step: create() with auto_liquidate=True
- 2-step: create() then liquidate() separately
"""
from datetime import datetime
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
from app.schemas.purchase import PurchaseCreate, PurchaseUpdate, PurchaseFullUpdate
from app.services.base import CRUDBase


class CRUDPurchase(CRUDBase[Purchase, PurchaseCreate, PurchaseUpdate]):
    """CRUD operations for Purchase with inventory and financial logic."""
    
    def create(
        self,
        db: Session,
        obj_in: PurchaseCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None
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
        # Check if this is a double-entry purchase (skip inventory movements)
        is_double_entry = hasattr(obj_in, 'double_entry_id') and obj_in.double_entry_id is not None
        
        purchase = Purchase(
            organization_id=organization_id,
            purchase_number=purchase_number,
            supplier_id=obj_in.supplier_id,
            date=obj_in.date,
            total_amount=Decimal("0.00"),
            status="registered",
            notes=obj_in.notes,
            vehicle_plate=getattr(obj_in, 'vehicle_plate', None),
            invoice_number=getattr(obj_in, 'invoice_number', None),
            created_by=user_id,
            double_entry_id=obj_in.double_entry_id if is_double_entry else None,
        )
        db.add(purchase)
        db.flush()  # Get purchase.id before creating lines
        
        if is_double_entry:
            print(f"📦 Created double-entry purchase #{purchase_number} with ID: {purchase.id} (no inventory movement)")
        else:
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
            
            # Validate warehouse (skip for double-entry)
            if not is_double_entry:
                if not line_data.warehouse_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="warehouse_id is required for normal purchases"
                    )
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
                warehouse_id=line_data.warehouse_id,  # Can be None for double-entry
                quantity=quantity,
                unit_price=unit_price,
                total_price=line_total,
            )
            db.add(purchase_line)
            
            # Skip inventory operations for double-entry
            if not is_double_entry:
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
                user_id=user_id,
            )
        
        db.commit()
        db.refresh(purchase)
        
        return purchase
    
    def liquidate(
        self,
        db: Session,
        purchase_id: UUID,
        payment_account_id: UUID,
        organization_id: UUID,
        user_id: Optional[UUID] = None
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
        
        # Validate: Cannot liquidate purchase that belongs to double-entry
        if purchase.double_entry_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot liquidate purchase that belongs to a double-entry operation. Manage it through the double-entry instead."
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
        purchase.liquidated_by = user_id
        
        # Step 5: Deduct from payment account
        payment_account.current_balance -= purchase.total_amount

        # Step 6: Move stock from transit to liquidated
        # Load lines if not already loaded
        purchase_with_lines = db.query(Purchase).options(
            joinedload(Purchase.lines)
        ).filter(Purchase.id == purchase_id).first()
        self._move_stock_transit_to_liquidated(db, purchase_with_lines)

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
        
        # Validate: Cannot cancel purchase that belongs to double-entry
        if purchase.double_entry_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel purchase that belongs to a double-entry operation. Cancel the double-entry instead."
            )
        
        if purchase.status == "cancelled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Purchase is already cancelled"
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
            
            # Revert stock (cancelled purchases are always 'registered', so stock is in transit)
            material.current_stock -= line.quantity
            material.current_stock_transit -= line.quantity
            
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
    
    def update(
        self,
        db: Session,
        purchase_id: UUID,
        obj_in: PurchaseFullUpdate,
        organization_id: UUID,
        user_id: Optional[UUID] = None
    ) -> Purchase:
        """
        Edicion completa de compra (metadata + proveedor + lineas).

        Estrategia Revert-and-Reapply:
        1. Revertir efectos de lineas actuales (inventario, stock, costo)
        2. Eliminar lineas y movimientos antiguos
        3. Aplicar nuevas lineas (inventario, stock, costo)
        4. Actualizar saldos de proveedor(es)
        5. Actualizar metadata

        Solo permitido para compras con status='registered' y sin double_entry_id.
        """
        # Step 1: Cargar compra con lineas y relaciones
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

        if purchase.status != "registered":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Solo se pueden editar compras con estado 'registered'. Estado actual: '{purchase.status}'"
            )

        if purchase.double_entry_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede editar una compra vinculada a doble partida"
            )

        old_total = purchase.total_amount
        old_supplier_id = purchase.supplier_id

        # Step 2: Si hay cambio de proveedor, validar el nuevo
        new_supplier = None
        if obj_in.supplier_id and obj_in.supplier_id != old_supplier_id:
            new_supplier = db.get(ThirdParty, obj_in.supplier_id)
            if not new_supplier or new_supplier.organization_id != organization_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Nuevo proveedor no encontrado"
                )
            if not new_supplier.is_supplier:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El tercero seleccionado no es proveedor"
                )

        # Step 3: Si hay lineas nuevas, hacer revert+reapply
        if obj_in.lines is not None:
            # 3a. Validar stock suficiente para revertir cada linea actual
            for line in purchase.lines:
                material = line.material
                if material.current_stock < line.quantity:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Stock insuficiente para revertir {material.code}. "
                               f"Actual: {material.current_stock}, Requerido: {line.quantity}"
                    )

            # 3b. Revertir efectos de lineas actuales
            for line in purchase.lines:
                material = line.material
                # Revertir stock
                material.current_stock -= line.quantity
                material.current_stock_transit -= line.quantity
                # Nota: costo promedio no se revierte (limitacion conocida)
                print(f"  ↩️  Revert: {material.code} -{line.quantity} (stock: {material.current_stock})")

            # 3c. Eliminar movimientos de inventario originales
            db.query(InventoryMovement).filter(
                InventoryMovement.reference_type == "purchase",
                InventoryMovement.reference_id == purchase.id,
                InventoryMovement.movement_type == "purchase",
            ).delete(synchronize_session=False)

            # 3d. Eliminar lineas antiguas
            db.query(PurchaseLine).filter(
                PurchaseLine.purchase_id == purchase.id
            ).delete(synchronize_session=False)

            db.flush()

            # 3e. Crear nuevas lineas
            new_total = Decimal("0.00")
            for line_data in obj_in.lines:
                # Validar material
                material = db.get(Material, line_data.material_id)
                if not material or material.organization_id != organization_id:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Material {line_data.material_id} no encontrado"
                    )

                # Validar warehouse
                if not line_data.warehouse_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="warehouse_id es requerido para compras normales"
                    )
                warehouse = db.get(Warehouse, line_data.warehouse_id)
                if not warehouse or warehouse.organization_id != organization_id:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Bodega {line_data.warehouse_id} no encontrada"
                    )

                quantity = Decimal(str(line_data.quantity))
                unit_price = Decimal(str(line_data.unit_price))
                line_total = quantity * unit_price
                new_total += line_total

                # Crear PurchaseLine
                new_line = PurchaseLine(
                    purchase_id=purchase.id,
                    material_id=line_data.material_id,
                    warehouse_id=line_data.warehouse_id,
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=line_total,
                )
                db.add(new_line)

                # Crear InventoryMovement
                movement = InventoryMovement(
                    organization_id=organization_id,
                    material_id=line_data.material_id,
                    warehouse_id=line_data.warehouse_id,
                    movement_type="purchase",
                    quantity=quantity,
                    unit_cost=unit_price,
                    reference_type="purchase",
                    reference_id=purchase.id,
                    date=obj_in.date or purchase.date,
                    notes=f"Purchase #{purchase.purchase_number} (edited)",
                )
                db.add(movement)

                # Actualizar stock y costo promedio
                self._update_material_stock_and_cost(
                    material=material,
                    quantity_delta=quantity,
                    unit_cost=unit_price,
                )

                print(f"  📝 New line: {material.code} x {quantity} @ ${unit_price} = ${line_total}")

            purchase.total_amount = new_total
        else:
            new_total = old_total

        # Step 4: Actualizar saldos de proveedor
        if new_supplier:
            # Revertir saldo del proveedor original
            old_supplier = db.get(ThirdParty, old_supplier_id)
            old_supplier.current_balance += old_total  # Reducir deuda

            # Aplicar saldo al nuevo proveedor
            new_supplier.current_balance -= new_total  # Aumentar deuda

            purchase.supplier_id = obj_in.supplier_id
            print(f"  🔄 Proveedor cambiado: {old_supplier.name} → {new_supplier.name}")
        elif obj_in.lines is not None:
            # Mismo proveedor pero lineas cambiaron: ajustar diferencia
            supplier = db.get(ThirdParty, old_supplier_id)
            balance_diff = new_total - old_total
            supplier.current_balance -= balance_diff  # Ajustar deuda
            print(f"  💰 Saldo proveedor ajustado por ${balance_diff}")

        # Step 5: Actualizar metadata
        if obj_in.date is not None:
            purchase.date = obj_in.date
        if obj_in.notes is not None:
            purchase.notes = obj_in.notes
        if obj_in.vehicle_plate is not None:
            purchase.vehicle_plate = obj_in.vehicle_plate
        if obj_in.invoice_number is not None:
            purchase.invoice_number = obj_in.invoice_number

        db.commit()
        db.refresh(purchase)

        print(f"✏️ Purchase #{purchase.purchase_number} updated")

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
    
    def get(
        self,
        db: Session,
        purchase_id: UUID,
        organization_id: UUID
    ) -> Optional[Purchase]:
        """
        Get a single purchase by ID with eager loading.
        
        Returns None if not found or doesn't belong to organization.
        """
        return db.query(Purchase).options(
            joinedload(Purchase.lines).joinedload(PurchaseLine.material),
            joinedload(Purchase.lines).joinedload(PurchaseLine.warehouse),
            joinedload(Purchase.supplier),
            joinedload(Purchase.payment_account),
        ).filter(
            Purchase.id == purchase_id,
            Purchase.organization_id == organization_id
        ).first()
    
    def get_multi(
        self,
        db: Session,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        supplier_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        search: Optional[str] = None
    ) -> tuple[List[Purchase], int]:
        """
        Get multiple purchases with filtering and pagination.
        
        Returns:
            Tuple of (purchases, total_count)
        """
        from sqlalchemy import or_, cast, String
        
        # Base query
        query = db.query(Purchase).filter(
            Purchase.organization_id == organization_id
        )
        
        # Apply filters
        if status:
            query = query.filter(Purchase.status == status)
        
        if supplier_id:
            query = query.filter(Purchase.supplier_id == supplier_id)
        
        if date_from:
            query = query.filter(Purchase.date >= date_from)
        
        if date_to:
            query = query.filter(Purchase.date <= date_to)
        
        if search:
            # Search in: purchase_number (as text), supplier name, notes
            query = query.join(Purchase.supplier).filter(
                or_(
                    cast(Purchase.purchase_number, String).ilike(f"%{search}%"),
                    ThirdParty.name.ilike(f"%{search}%"),
                    Purchase.notes.ilike(f"%{search}%")
                )
            )
        
        # Get total count before pagination
        total = query.count()
        
        # Apply pagination and eager loading
        purchases = query.options(
            joinedload(Purchase.lines).joinedload(PurchaseLine.material),
            joinedload(Purchase.lines).joinedload(PurchaseLine.warehouse),
            joinedload(Purchase.supplier),
            joinedload(Purchase.payment_account),
        ).order_by(Purchase.date.desc(), Purchase.purchase_number.desc()).offset(skip).limit(limit).all()
        
        return purchases, total
    
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
    
    def delete(
        self,
        db: Session,
        id: UUID,
        organization_id: UUID
    ) -> Purchase:
        """
        Soft delete purchase (set is_active = False).
        
        Validates that purchase is not part of a double-entry operation.
        
        Args:
            db: Database session
            id: Purchase UUID
            organization_id: Organization UUID
            
        Returns:
            Deleted (deactivated) purchase instance
            
        Raises:
            HTTPException: 400 if purchase belongs to double-entry
            HTTPException: 404 if not found
        """
        # Get existing purchase
        purchase = self.get(db, id, organization_id)
        if not purchase:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase not found"
            )
        
        # Validate: Cannot delete purchase that belongs to double-entry
        if purchase.double_entry_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete purchase that belongs to a double-entry operation. Cancel the double-entry instead."
            )
        
        # Soft delete
        purchase.is_active = False
        
        # Commit changes
        db.commit()
        db.refresh(purchase)
        
        return purchase
    
    def _update_material_stock_and_cost(
        self,
        material: Material,
        quantity_delta: Decimal,
        unit_cost: Decimal,
        to_transit: bool = True
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
            to_transit: If True, stock goes to transit; if False, goes to liquidated
        """
        old_stock = material.current_stock
        old_cost = material.current_average_cost
        new_stock = old_stock + quantity_delta

        if quantity_delta > 0:  # Adding stock (purchase)
            if old_stock == 0:
                new_cost = unit_cost
            else:
                total_old_value = old_stock * old_cost
                total_new_value = quantity_delta * unit_cost
                new_cost = (total_old_value + total_new_value) / new_stock

            material.current_average_cost = new_cost

            # Track which bucket the stock goes to
            if to_transit:
                material.current_stock_transit += quantity_delta
            else:
                material.current_stock_liquidated += quantity_delta

        # Update total stock (always)
        material.current_stock = new_stock

        print(f"    📊 {material.code}: stock {old_stock} → {new_stock}, cost ${old_cost} → ${material.current_average_cost}")

    def _move_stock_transit_to_liquidated(
        self,
        db: Session,
        purchase: Purchase
    ) -> None:
        """
        Move stock from transit to liquidated when a purchase is liquidated.

        This doesn't change total stock or average cost, just reclassifies it.
        """
        for line in purchase.lines:
            material = db.get(Material, line.material_id)
            if material:
                material.current_stock_transit -= line.quantity
                material.current_stock_liquidated += line.quantity
                print(f"    📦 {material.code}: transit -{line.quantity}, liquidated +{line.quantity}")


# Instance for use in endpoints
purchase = CRUDPurchase(Purchase)
