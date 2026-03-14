"""
CRUD operations for Purchase model with business logic.

Supports 1-step and 2-step purchase workflows:
- 1-step: create() with auto_liquidate=True (prices must be > 0)
- 2-step: create() then liquidate() separately

Liquidation confirms prices, moves stock transit->liquidated, updates avg cost and supplier balance.
Payment to supplier is a separate operation via MoneyMovement (type='payment_to_supplier').
"""
from datetime import datetime, time, timezone
from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session, joinedload

from app.models.purchase import Purchase, PurchaseCommission, PurchaseLine
from app.models.inventory_movement import InventoryMovement
from app.models.material import Material
from app.models.money_account import MoneyAccount
from app.models.third_party import ThirdParty
from app.models.warehouse import Warehouse
from app.schemas.purchase import PurchaseCreate, PurchaseUpdate, PurchaseFullUpdate
from app.services.base import CRUDBase
from app.services.material_cost_history import material_cost_history_service
from app.services.money_movement import money_movement as mm_service


class CRUDPurchase(CRUDBase[Purchase, PurchaseCreate, PurchaseUpdate]):
    """CRUD operations for Purchase with inventory and financial logic."""

    def check_duplicate(
        self,
        db: Session,
        supplier_id: UUID,
        date: datetime,
        organization_id: UUID,
        total_quantity: Optional[Decimal] = None,
    ) -> int:
        """
        Verifica si existen compras del mismo proveedor en la misma fecha (RN-COMP-02).

        Si se proporciona total_quantity, solo cuenta como duplicado si la cantidad
        total esta dentro de ±20% de tolerancia.
        """
        same_day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        same_day_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)

        base_query = db.query(Purchase).filter(
            Purchase.organization_id == organization_id,
            Purchase.supplier_id == supplier_id,
            Purchase.date >= same_day_start,
            Purchase.date <= same_day_end,
            Purchase.status != "cancelled",
        )

        if total_quantity is not None and total_quantity > 0:
            # Filtrar por cantidad total dentro de ±20%
            min_qty = total_quantity * Decimal("0.8")
            max_qty = total_quantity * Decimal("1.2")
            count = 0
            for p in base_query.options(joinedload(Purchase.lines)).all():
                p_qty = sum(line.quantity for line in p.lines)
                if min_qty <= p_qty <= max_qty:
                    count += 1
            return count

        return base_query.count()

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
        # Step 0: Validar fecha no futura (V-COMP-04) — comparar solo fechas (BusinessDate normaliza a mediodia)
        if obj_in.date.date() > datetime.now(timezone.utc).date():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La fecha de la compra no puede ser futura"
            )

        # Step 1: Generate next purchase_number with lock
        purchase_number = self._generate_purchase_number(db, organization_id)

        # Step 2: Validate supplier
        supplier = db.get(ThirdParty, obj_in.supplier_id)
        if not supplier or supplier.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proveedor no encontrado"
            )
        if not supplier.is_supplier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El tercero no es proveedor"
            )

        # Step 2b: Deteccion de duplicados (RN-COMP-02) - warning, no bloquea
        warnings = []
        total_quantity = sum(Decimal(str(l.quantity)) for l in obj_in.lines)
        existing_count = self.check_duplicate(db, obj_in.supplier_id, obj_in.date, organization_id, total_quantity)
        if existing_count > 0:
            warnings.append(
                f"Ya existen {existing_count} compra(s) del mismo proveedor en esta fecha"
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
                    detail=f"Material {line_data.material_id} no encontrado"
                )
            
            # Validate warehouse (skip for double-entry)
            if not is_double_entry:
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
                # Create InventoryMovement (unit_cost=0 hasta liquidar)
                movement = InventoryMovement(
                    organization_id=organization_id,
                    material_id=line_data.material_id,
                    warehouse_id=line_data.warehouse_id,
                    movement_type="purchase",
                    quantity=quantity,
                    unit_cost=Decimal("0"),
                    reference_type="purchase",
                    reference_id=purchase.id,
                    date=obj_in.date,
                    notes=f"Purchase #{purchase_number}",
                )
                db.add(movement)

                # Solo agregar stock a transito (sin recalcular costo promedio)
                material.current_stock += quantity
                material.current_stock_transit += quantity
            
            print(f"  📝 Line: {material.code} x {quantity} @ ${unit_price} = ${line_total}")
        
        # Step 5: Update purchase total
        purchase.total_amount = total_amount

        # Nota: NO se actualiza saldo del proveedor al crear.
        # El saldo se actualiza al liquidar (cuando se confirman precios).

        # Step 6: Procesar comisiones (solo guardar, el prorrateo ocurre al liquidar)
        if obj_in.commissions:
            self._process_commissions(db, purchase, obj_in.commissions, total_amount, organization_id)

        db.flush()

        # Step 7: Auto-liquidate if requested (precios ya validados > 0 en schema)
        if obj_in.auto_liquidate:
            print(f"  🔄 Auto-liquidating purchase...")
            purchase = self.liquidate(
                db=db,
                purchase_id=purchase.id,
                organization_id=organization_id,
                user_id=user_id,
                immediate_payment=obj_in.immediate_payment,
                payment_account_id=obj_in.payment_account_id,
                commissions_data=obj_in.commissions if obj_in.commissions else None,
            )
        
        db.commit()
        db.refresh(purchase)

        return purchase, warnings

    def liquidate(
        self,
        db: Session,
        purchase_id: UUID,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
        line_updates: Optional[List[dict]] = None,
        immediate_payment: bool = False,
        payment_account_id: Optional[UUID] = None,
        commissions_data: Optional[List] = None,
    ) -> Purchase:
        """
        Liquidar compra registrada (cambiar status a 'liquidated').

        Confirma precios, mueve stock de transito a liquidado, recalcula costo
        promedio, y actualiza saldo del proveedor. NO involucra pago (cuenta de dinero).

        Workflow:
        1. Validar compra existe y status='registered'
        2. Si hay line_updates: actualizar precios en lineas
        3. Validar V-LIQ-01: todos los precios > 0
        4. Recalcular total
        5. Actualizar InventoryMovement.unit_cost con precio confirmado
        6. Recalcular costo promedio por material
        7. Mover stock transit -> liquidated
        8. Actualizar saldo proveedor
        9. Cambiar status a 'liquidated'
        """
        # Step 1: Get and validate purchase
        purchase = db.query(Purchase).options(
            joinedload(Purchase.lines).joinedload(PurchaseLine.material),
            joinedload(Purchase.lines).joinedload(PurchaseLine.warehouse),
            joinedload(Purchase.supplier),
            joinedload(Purchase.commissions),
        ).filter(
            Purchase.id == purchase_id,
            Purchase.organization_id == organization_id
        ).first()

        if not purchase:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Compra no encontrada"
            )

        if purchase.double_entry_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede liquidar una compra de doble partida. Gestione desde la doble partida."
            )

        if purchase.status != "registered":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Compra ya esta {purchase.status}. Solo se pueden liquidar compras registradas."
            )

        # Step 2: Actualizar precios si se proporcionan line_updates
        if line_updates:
            price_map = {lu["line_id"]: Decimal(str(lu["unit_price"])) for lu in line_updates}
            for line in purchase.lines:
                if line.id in price_map:
                    line.unit_price = price_map[line.id]
                    line.total_price = line.quantity * line.unit_price

        # Step 3: Validar V-LIQ-01 - todos los precios > 0
        for line in purchase.lines:
            if line.unit_price <= 0:
                material = line.material
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Todos los precios deben ser mayores a 0 al liquidar. "
                           f"Material '{material.name}' tiene precio ${line.unit_price}"
                )

        # Step 4: Recalcular total
        purchase.total_amount = sum(
            line.quantity * line.unit_price for line in purchase.lines
        )

        # Step 4b: Procesar comisiones
        if commissions_data is not None:
            db.query(PurchaseCommission).filter(
                PurchaseCommission.purchase_id == purchase.id
            ).delete(synchronize_session=False)
            db.flush()
            if commissions_data:
                self._process_commissions(
                    db, purchase, commissions_data, purchase.total_amount, organization_id
                )
                db.flush()

        # Step 4c: Calcular prorrateo de comisiones al costo
        # Flush cambios pendientes (precios, total) y refresh para cargar comisiones
        db.flush()
        db.refresh(purchase)
        total_commission = Decimal("0")
        if purchase.commissions:
            total_commission = sum(
                c.commission_amount for c in purchase.commissions
            )
        commission_prorate = {}
        if total_commission > 0 and purchase.total_amount > 0:
            for line in purchase.lines:
                line_value = line.quantity * line.unit_price
                line_weight = line_value / purchase.total_amount
                commission_prorate[line.id] = total_commission * line_weight

        # Step 5 y 6: Actualizar InventoryMovement.unit_cost y recalcular costo promedio
        for line in purchase.lines:
            # Costo ajustado = precio + comision prorrateada
            line_commission = commission_prorate.get(line.id, Decimal("0"))
            adjusted_unit_cost = line.unit_price + (line_commission / line.quantity) if line.quantity > 0 else line.unit_price

            # Actualizar costo en movimiento de inventario
            inv_movement = db.query(InventoryMovement).filter(
                InventoryMovement.reference_type == "purchase",
                InventoryMovement.reference_id == purchase.id,
                InventoryMovement.material_id == line.material_id,
                InventoryMovement.movement_type == "purchase",
            ).first()
            if inv_movement:
                inv_movement.unit_cost = adjusted_unit_cost

            # Recalcular costo promedio del material con costo AJUSTADO
            material = line.material
            old_cost = material.current_average_cost
            old_liquidated_stock = material.current_stock_liquidated
            self._apply_cost_at_liquidation(material, line.quantity, adjusted_unit_cost)

            material_cost_history_service.record_cost_change(
                db=db,
                material=material,
                previous_cost=old_cost,
                previous_stock=old_liquidated_stock,
                new_cost=material.current_average_cost,
                new_stock=old_liquidated_stock + line.quantity,
                source_type="purchase_liquidation",
                source_id=purchase.id,
                organization_id=organization_id,
            )

            if line_commission > 0:
                print(f"  💲 {material.code}: precio=${line.unit_price} + comision=${line_commission} = costo=${adjusted_unit_cost}, costo_prom=${material.current_average_cost}")
            else:
                print(f"  💲 {material.code}: precio=${line.unit_price}, costo_prom=${material.current_average_cost}")

        # Step 7: Mover stock de transito a liquidado
        self._move_stock_transit_to_liquidated(db, purchase)

        # Step 8: Actualizar saldo del proveedor (deuda — solo materiales, sin comisiones)
        supplier = purchase.supplier
        supplier.current_balance -= purchase.total_amount
        print(f"  💰 Saldo proveedor: {supplier.current_balance} (deuda +${purchase.total_amount})")

        # Step 8b: Actualizar saldo de comisionistas (les debemos la comision)
        for comm in (purchase.commissions or []):
            recipient = db.get(ThirdParty, comm.third_party_id)
            recipient.current_balance -= comm.commission_amount
            print(f"  💼 Comision '{comm.concept}': ${comm.commission_amount} → {recipient.name} (saldo: {recipient.current_balance})")

        # Step 9: Cambiar status
        purchase.status = "liquidated"
        purchase.liquidated_by = user_id
        purchase.liquidated_at = datetime.now(timezone.utc)

        print(f"✅ Liquidated purchase #{purchase.purchase_number} for ${purchase.total_amount}")

        # Step 10 (opcional): Pago inmediato
        if immediate_payment and payment_account_id:
            account = db.execute(
                select(MoneyAccount).where(
                    MoneyAccount.id == payment_account_id,
                    MoneyAccount.organization_id == organization_id,
                    MoneyAccount.is_active == True,
                )
            ).scalar_one_or_none()
            if not account:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Cuenta de pago no encontrada",
                )
            if account.current_balance < purchase.total_amount:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Fondos insuficientes. Disponible: ${account.current_balance}, Requerido: ${purchase.total_amount}",
                )

            col_today = datetime.now(ZoneInfo("America/Bogota")).date()
            today_dt = datetime.combine(col_today, time(12, 0), tzinfo=timezone.utc)

            mm_service._create_movement(
                db=db,
                organization_id=organization_id,
                movement_type="payment_to_supplier",
                amount=purchase.total_amount,
                account_id=payment_account_id,
                date=today_dt,
                description=f"Pago compra #{purchase.purchase_number}",
                third_party_id=supplier.id,
                purchase_id=purchase.id,
                user_id=user_id,
            )

            account.current_balance -= purchase.total_amount
            supplier.current_balance += purchase.total_amount
            print(f"  💳 Pago inmediato: ${purchase.total_amount} desde {account.name}")

        db.commit()
        db.refresh(purchase)

        return purchase
    
    def cancel(
        self,
        db: Session,
        purchase_id: UUID,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
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
        7. Revert average cost using MaterialCostHistory (blocks if subsequent operations exist)
        
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
            joinedload(Purchase.lines).joinedload(PurchaseLine.material),
            joinedload(Purchase.commissions),
        ).filter(
            Purchase.id == purchase_id,
            Purchase.organization_id == organization_id
        ).first()

        if not purchase:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Compra no encontrada"
            )

        # Validate: Cannot cancel purchase that belongs to double-entry
        if purchase.double_entry_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede cancelar una compra de doble partida. Cancele la doble partida."
            )
        
        if purchase.status == "cancelled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Purchase is already cancelled"
            )

        was_liquidated = purchase.status == "liquidated"

        # Step 2a: Si liquidada, verificar que no hay operaciones posteriores de costo
        if was_liquidated:
            for line in purchase.lines:
                can_revert, blocking = material_cost_history_service.check_can_revert(
                    db=db,
                    material_id=line.material_id,
                    source_type="purchase_liquidation",
                    source_id=purchase.id,
                )
                if not can_revert:
                    material = line.material
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"No se puede cancelar: existen operaciones posteriores que afectaron "
                               f"el costo de '{material.name}'. Cancele primero: {', '.join(blocking)}"
                    )

        # Step 2b: Validate sufficient stock to reverse (para registered, estricto; para liquidated, permitir negativo con warning)
        if not was_liquidated:
            for line in purchase.lines:
                material = line.material
                if material.current_stock < line.quantity:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"No se puede cancelar: stock insuficiente para {material.code}. Actual: {material.current_stock}, Requerido: {line.quantity}"
                    )

        # Step 3: Update status and audit
        purchase.status = "cancelled"
        purchase.cancelled_by = user_id
        purchase.cancelled_at = datetime.now(timezone.utc)

        # Nota: NO se reembolsa a cuenta de pago. El pago es operacion separada
        # via MoneyMovement y debe anularse por separado si corresponde.

        # Step 5: Create reversal movements and revert stock
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

            # Revert stock del bucket correcto segun estado previo
            material.current_stock -= line.quantity
            if was_liquidated:
                material.current_stock_liquidated -= line.quantity
                # Revertir costo promedio usando historial
                material_cost_history_service.revert_cost_change(
                    db=db,
                    material=material,
                    source_type="purchase_liquidation",
                    source_id=purchase.id,
                )
            else:
                material.current_stock_transit -= line.quantity

            print(f"  ↩️  Reversed: {material.code} -{line.quantity} (new stock: {material.current_stock}, cost: {material.current_average_cost})")

        # Step 6: Revert supplier balance (solo si estaba liquidada, ya que al crear no se modifica)
        supplier = db.get(ThirdParty, purchase.supplier_id)
        if was_liquidated:
            supplier.current_balance += purchase.total_amount  # Reduce debt

            # Step 6b: Revertir saldo de comisionistas
            for comm in (purchase.commissions or []):
                recipient = db.get(ThirdParty, comm.third_party_id)
                recipient.current_balance += comm.commission_amount
                print(f"  ↩️  Comision revertida: ${comm.commission_amount} → {recipient.name}")

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
            joinedload(Purchase.commissions),
        ).filter(
            Purchase.id == purchase_id,
            Purchase.organization_id == organization_id
        ).first()

        if not purchase:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Compra no encontrada"
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

                # Crear InventoryMovement (unit_cost=0, se confirma al liquidar)
                movement = InventoryMovement(
                    organization_id=organization_id,
                    material_id=line_data.material_id,
                    warehouse_id=line_data.warehouse_id,
                    movement_type="purchase",
                    quantity=quantity,
                    unit_cost=Decimal("0"),
                    reference_type="purchase",
                    reference_id=purchase.id,
                    date=obj_in.date or purchase.date,
                    notes=f"Purchase #{purchase.purchase_number} (edited)",
                )
                db.add(movement)

                # Solo agregar stock a transito (sin costo promedio)
                material.current_stock += quantity
                material.current_stock_transit += quantity

                print(f"  📝 New line: {material.code} x {quantity} @ ${unit_price} = ${line_total}")

            purchase.total_amount = new_total
        else:
            new_total = old_total

        # Step 4: Actualizar proveedor si cambio (sin tocar saldos - se actualizan al liquidar)
        if new_supplier:
            purchase.supplier_id = obj_in.supplier_id
            print(f"  🔄 Proveedor cambiado a: {new_supplier.name}")

        # Step 4b: Actualizar comisiones si se proporcionan
        if obj_in.commissions is not None:
            db.query(PurchaseCommission).filter(
                PurchaseCommission.purchase_id == purchase.id
            ).delete(synchronize_session=False)
            db.flush()
            if obj_in.commissions:
                self._process_commissions(
                    db, purchase, obj_in.commissions, new_total, organization_id
                )

        # Step 5: Actualizar metadata
        if obj_in.date is not None:
            purchase.date = obj_in.date
        if obj_in.notes is not None:
            purchase.notes = obj_in.notes
        if obj_in.vehicle_plate is not None:
            purchase.vehicle_plate = obj_in.vehicle_plate
        if obj_in.invoice_number is not None:
            purchase.invoice_number = obj_in.invoice_number

        if user_id:
            purchase.updated_by = user_id

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
            joinedload(Purchase.commissions),
        ).filter(
            Purchase.id == purchase_id,
            Purchase.organization_id == organization_id
        ).first()
        
        if not purchase:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Compra no encontrada"
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
            joinedload(Purchase.commissions),
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
            query = query.filter(Purchase.date < date_to)
        
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
                detail="Compra no encontrada"
            )
        
        # Validate: Cannot delete purchase that belongs to double-entry
        if purchase.double_entry_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede eliminar una compra de doble partida. Cancele la doble partida."
            )
        
        # Soft delete
        purchase.is_active = False
        
        # Commit changes
        db.commit()
        db.refresh(purchase)
        
        return purchase
    
    def _apply_cost_at_liquidation(
        self,
        material: Material,
        quantity: Decimal,
        confirmed_price: Decimal,
    ) -> None:
        """
        Incorporar costo confirmado al promedio ponderado durante liquidacion.

        Usa current_stock_liquidated (NO current_stock) para que el stock en
        transito de compras registradas no diluya el costo promedio.
        Se llama ANTES de _move_stock_transit_to_liquidated, asi que
        current_stock_liquidated aun tiene el valor pre-liquidacion.
        """
        old_liquidated = material.current_stock_liquidated
        if old_liquidated <= 0:
            # Primera liquidacion o todo el stock liquidado es de esta compra
            material.current_average_cost = confirmed_price
        else:
            old_value = old_liquidated * material.current_average_cost
            new_value = old_value + quantity * confirmed_price
            material.current_average_cost = new_value / (old_liquidated + quantity)

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


    def _process_commissions(
        self,
        db: Session,
        purchase: Purchase,
        commissions_data: List,
        purchase_total: Decimal,
        organization_id: UUID,
    ) -> None:
        """Crear registros de comision y calcular montos."""
        for comm_data in commissions_data:
            recipient = db.get(ThirdParty, comm_data.third_party_id)
            if not recipient or recipient.organization_id != organization_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Comisionista {comm_data.third_party_id} no encontrado",
                )

            commission_amount = self._calculate_commission(
                comm_data.commission_type, comm_data.commission_value, purchase_total
            )

            commission = PurchaseCommission(
                purchase_id=purchase.id,
                third_party_id=comm_data.third_party_id,
                concept=comm_data.concept,
                commission_type=comm_data.commission_type,
                commission_value=comm_data.commission_value,
                commission_amount=commission_amount,
            )
            db.add(commission)
            print(f"  💼 Comision: {comm_data.concept} - ${commission_amount} ({comm_data.commission_type})")

    def _calculate_commission(
        self,
        commission_type: str,
        commission_value: Decimal,
        purchase_total: Decimal,
    ) -> Decimal:
        """Calcular monto de comision segun tipo."""
        if commission_type == "percentage":
            return (purchase_total * Decimal(str(commission_value))) / Decimal("100")
        else:
            return Decimal(str(commission_value))


# Instance for use in endpoints
purchase = CRUDPurchase(Purchase)
