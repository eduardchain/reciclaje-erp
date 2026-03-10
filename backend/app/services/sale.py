"""
CRUD operations for Sale model with business logic.

Workflow de 3 pasos (igual que compras):
1. CREATE → registered: Stock se resta, unit_cost se captura. SIN efecto en saldo cliente.
2. LIQUIDATE → liquidated: Confirmar precios, actualizar saldo cliente (+deuda), pagar comisiones.
3. COLLECT → Via POST /money-movements/customer-collection (modulo tesoreria).

auto_liquidate=True ejecuta paso 1+2 en una sola llamada.

Cancelacion:
- registered: revierte stock solamente
- liquidated: revierte stock + saldo cliente + comisiones pagadas
"""
from datetime import datetime, timezone
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
from app.schemas.sale import SaleCreate, SaleUpdate, SaleFullUpdate
from app.models.material_cost_history import MaterialCostHistory
from app.services.base import CRUDBase


class CRUDSale(CRUDBase[Sale, SaleCreate, SaleUpdate]):
    """CRUD operations for Sale with inventory, financial, and commission logic."""

    def _get_last_known_cost(self, db: Session, material_id: UUID, organization_id: UUID) -> Decimal:
        """Busca el ultimo costo conocido desde MaterialCostHistory cuando avg_cost = 0."""
        last = db.query(MaterialCostHistory.new_cost).filter(
            MaterialCostHistory.material_id == material_id,
            MaterialCostHistory.organization_id == organization_id,
        ).order_by(MaterialCostHistory.created_at.desc()).first()
        return last[0] if last else Decimal("0")
    
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
        # Validar fecha no futura
        sale_date = obj_in.date.replace(tzinfo=None) if obj_in.date.tzinfo else obj_in.date
        if sale_date > datetime.now(timezone.utc).replace(tzinfo=None):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La fecha de venta no puede ser futura"
            )

        # Step 1: Generate next sale_number with advisory lock
        sale_number = self._generate_sale_number(db, organization_id)
        
        # Check if this is a double-entry sale (skip inventory movements)
        is_double_entry = hasattr(obj_in, 'double_entry_id') and obj_in.double_entry_id is not None
        
        # Step 2: Validate customer
        customer = db.get(ThirdParty, obj_in.customer_id)
        if not customer or customer.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cliente no encontrado"
            )
        if not customer.is_customer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El tercero no esta marcado como cliente"
            )
        
        # Step 3: Validate warehouse (skip for double-entry)
        if not is_double_entry:
            if not obj_in.warehouse_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="warehouse_id es requerido para ventas normales"
                )
            warehouse = db.get(Warehouse, obj_in.warehouse_id)
            if not warehouse or warehouse.organization_id != organization_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Bodega no encontrada"
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
                        detail=f"Material {line_data.material_id} no encontrado"
                    )

                # Validacion por bodega (stock especifico en la bodega de la venta)
                warehouse_stock = db.execute(
                    select(func.coalesce(func.sum(InventoryMovement.quantity), 0)).where(
                        InventoryMovement.material_id == material.id,
                        InventoryMovement.warehouse_id == obj_in.warehouse_id,
                        InventoryMovement.organization_id == organization_id,
                    )
                ).scalar()
                warehouse_stock = Decimal(str(warehouse_stock))

                if warehouse_stock < line_data.quantity:
                    resulting_stock = warehouse_stock - line_data.quantity
                    warnings.append(
                        f"Stock insuficiente de '{material.name}' en bodega. "
                        f"Disponible en bodega: {warehouse_stock}, "
                        f"Requerido: {line_data.quantity}. "
                        f"Stock resultante: {resulting_stock}"
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
                    detail=f"Material {line_data.material_id} no encontrado"
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
                if unit_cost == 0:
                    unit_cost = self._get_last_known_cost(db, material.id, organization_id)
            
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
        
        # Step 9: Customer balance NO se actualiza aqui — se hace en liquidate()

        db.flush()

        # Step 10: If auto_liquidate, liquidate immediately
        if obj_in.auto_liquidate:
            print(f"⚡ Auto-liquidating sale #{sale_number}")
            sale = self.liquidate(db, sale.id, organization_id, user_id=user_id)

        # Attach warnings as transient attribute (no se persiste en BD)
        sale._warnings = warnings
        return sale
    
    def liquidate(
        self,
        db: Session,
        sale_id: UUID,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
        line_updates: Optional[List] = None,
        commissions_data: Optional[List] = None
    ) -> Sale:
        """
        Liquidar venta registrada: confirmar precios, actualizar saldo cliente, pagar comisiones.

        NO recibe payment_account_id — el cobro es un paso separado via MoneyMovement.

        Acepta opcionalmente:
        - line_updates: precios editados por linea (para ventas creadas con precio=0)
        - commissions_data: comisiones nuevas que REEMPLAZAN las existentes

        V-VENTA-04: Todas las lineas deben tener unit_price > 0 al liquidar.
        """
        # Step 1: Get sale
        sale = db.get(Sale, sale_id)
        if not sale or sale.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Venta no encontrada"
            )

        # Validate: Cannot liquidate sale that belongs to double-entry
        if sale.double_entry_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede liquidar una venta de doble partida. Gestione desde la doble partida."
            )

        # Step 2: Validate status
        if sale.status != "registered":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede liquidar venta con estado '{sale.status}'. Debe estar 'registered'"
            )

        # Step 3: Si hay line_updates, actualizar precios de las lineas
        if line_updates:
            price_map = {str(lu.line_id): lu.unit_price for lu in line_updates}
            stmt = select(SaleLine).where(SaleLine.sale_id == sale.id)
            lines = db.scalars(stmt).all()

            new_total = Decimal("0.00")
            for line in lines:
                if str(line.id) in price_map:
                    line.unit_price = price_map[str(line.id)]
                    line.total_price = line.quantity * line.unit_price
                new_total += line.total_price

            sale.total_amount = new_total

        # V-VENTA-04: Validar que todas las lineas tengan precio > 0
        stmt = select(SaleLine).where(SaleLine.sale_id == sale.id)
        all_lines = db.scalars(stmt).all()
        zero_price_lines = [l for l in all_lines if l.unit_price <= 0]
        if zero_price_lines:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Todas las lineas deben tener precio > 0 para liquidar (V-VENTA-04)"
            )

        # Step 4: Si hay commissions_data, reemplazar comisiones existentes
        if commissions_data is not None:
            # Eliminar comisiones existentes (nunca fueron pagadas en status=registered)
            db.query(SaleCommission).filter(
                SaleCommission.sale_id == sale.id
            ).delete(synchronize_session=False)
            db.flush()

            # Crear nuevas comisiones con el total actualizado
            if commissions_data:
                self._process_commissions(db, sale, commissions_data, sale.total_amount, organization_id)

        # Step 5: Update sale status
        sale.status = "liquidated"
        sale.liquidated_by = user_id
        sale.liquidated_at = datetime.now(timezone.utc)

        # Step 6: Update customer balance (ahora el cliente nos debe)
        customer = db.get(ThirdParty, sale.customer_id)
        customer.current_balance += sale.total_amount
        print(f"  💰 Customer '{customer.name}' balance: ${customer.current_balance - sale.total_amount} -> ${customer.current_balance}")

        # Step 7: Pay commissions (increase recipient balances — les debemos la comision)
        self._pay_commissions(db, sale)

        db.flush()

        print(f"✅ Sale #{sale.sale_number} liquidated for ${sale.total_amount}")

        return sale
    
    def cancel(
        self,
        db: Session,
        sale_id: UUID,
        organization_id: UUID,
        user_id: UUID = None
    ) -> Sale:
        """
        Cancelar venta y revertir todos los efectos.

        Permite cancelar ventas en estado 'registered' o 'liquidated'.
        - registered: solo revierte stock (saldo cliente nunca se aplico)
        - liquidated: revierte stock + saldo cliente + comisiones pagadas

        Args:
            db: Database session
            sale_id: Sale UUID
            organization_id: Organization UUID
            user_id: Usuario que cancela (para auditoria)

        Returns:
            Venta cancelada

        Raises:
            HTTPException: 404 si no existe
            HTTPException: 400 si ya esta cancelada o pertenece a doble partida
        """
        # Step 1: Get sale with lines and commissions
        sale = db.get(Sale, sale_id)
        if not sale or sale.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Venta no encontrada"
            )

        # Validate: Cannot cancel sale that belongs to double-entry
        if sale.double_entry_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede cancelar una venta de doble partida. Cancele la doble partida."
            )

        # Step 2: Validate status
        if sale.status == "cancelled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La venta ya esta cancelada"
            )

        was_liquidated = sale.status == "liquidated"

        # Step 3: Load lines
        stmt = select(SaleLine).where(SaleLine.sale_id == sale_id)
        lines = db.scalars(stmt).all()

        # Step 4: Update status and audit
        sale.status = "cancelled"
        sale.cancelled_by = user_id
        sale.cancelled_at = datetime.now(timezone.utc)

        # Step 5: Reverse inventory movements and restore stock
        for line in lines:
            material = db.get(Material, line.material_id)

            reversal_movement = InventoryMovement(
                organization_id=organization_id,
                material_id=line.material_id,
                warehouse_id=sale.warehouse_id,
                movement_type="sale_reversal",
                quantity=line.quantity,  # Positivo = material regresa
                unit_cost=line.unit_cost,
                reference_type="sale",
                reference_id=sale.id,
                date=datetime.now(timezone.utc),
                notes=f"Reversal of sale #{sale.sale_number}",
            )
            db.add(reversal_movement)

            material.current_stock += line.quantity
            material.current_stock_liquidated += line.quantity
            print(f"  🔄 Restored {line.quantity} of {material.name}, stock: {material.current_stock - line.quantity} → {material.current_stock}")

        # Step 6: Si estaba liquidada, revertir saldo cliente y comisiones
        if was_liquidated:
            customer = db.get(ThirdParty, sale.customer_id)
            customer.current_balance -= sale.total_amount
            print(f"👤 Customer '{customer.name}' balance reverted: ${customer.current_balance + sale.total_amount} → ${customer.current_balance}")

            # Revertir comisiones pagadas
            stmt_comm = select(SaleCommission).where(SaleCommission.sale_id == sale_id)
            commissions = db.scalars(stmt_comm).all()
            for comm in commissions:
                recipient = db.get(ThirdParty, comm.third_party_id)
                recipient.current_balance -= comm.commission_amount
                print(f"  💰 Commission reverted for '{recipient.name}': -${comm.commission_amount}")

        db.flush()

        print(f"❌ Sale #{sale.sale_number} cancelled (was {('liquidated' if was_liquidated else 'registered')})")

        return sale

    def update(
        self,
        db: Session,
        sale_id: UUID,
        obj_in: SaleFullUpdate,
        organization_id: UUID,
        user_id: UUID = None
    ) -> Sale:
        """
        Edicion completa de venta con estrategia Revert and Re-apply.

        Solo aplica a ventas status='registered' sin doble partida.
        Si se envian lineas, revierte efectos de inventario y re-aplica.
        Si se envian comisiones, las reemplaza todas.
        Stock negativo genera warning, no error (RN-INV-03).
        """
        # Step 1: Validar venta existe y es editable
        sale = db.query(Sale).options(
            joinedload(Sale.lines).joinedload(SaleLine.material),
            joinedload(Sale.commissions),
        ).filter(
            Sale.id == sale_id,
            Sale.organization_id == organization_id
        ).first()

        if not sale:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Venta no encontrada"
            )

        if sale.status != "registered":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Solo se pueden editar ventas con estado 'registered'. Estado actual: '{sale.status}'"
            )

        if sale.double_entry_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede editar una venta vinculada a doble partida"
            )

        old_total = sale.total_amount
        old_customer_id = sale.customer_id
        warnings: list[str] = []

        # Step 2: Si hay cambio de cliente, validar el nuevo
        new_customer = None
        if obj_in.customer_id and obj_in.customer_id != old_customer_id:
            new_customer = db.get(ThirdParty, obj_in.customer_id)
            if not new_customer or new_customer.organization_id != organization_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Nuevo cliente no encontrado"
                )
            if not new_customer.is_customer:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El tercero seleccionado no es cliente"
                )

        # Step 2b: Si hay cambio de bodega, validar
        if obj_in.warehouse_id is not None:
            warehouse = db.get(Warehouse, obj_in.warehouse_id)
            if not warehouse or warehouse.organization_id != organization_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Bodega no encontrada"
                )

        # Step 3: Si hay lineas nuevas, hacer revert+reapply
        if obj_in.lines is not None:
            # 3a. Revertir efectos de lineas actuales (devolver stock)
            for line in sale.lines:
                material = line.material
                material.current_stock += line.quantity
                material.current_stock_liquidated += line.quantity
                # Stock revertido para material {material.code}

            # 3b. Eliminar movimientos de inventario originales
            db.query(InventoryMovement).filter(
                InventoryMovement.reference_type == "sale",
                InventoryMovement.reference_id == sale.id,
                InventoryMovement.movement_type == "sale",
            ).delete(synchronize_session=False)

            # 3c. Eliminar lineas antiguas
            db.query(SaleLine).filter(
                SaleLine.sale_id == sale.id
            ).delete(synchronize_session=False)

            db.flush()

            # 3d. Crear nuevas lineas
            new_total = Decimal("0.00")
            effective_warehouse_id = obj_in.warehouse_id or sale.warehouse_id

            for line_data in obj_in.lines:
                material = db.get(Material, line_data.material_id)
                if not material or material.organization_id != organization_id:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Material {line_data.material_id} no encontrado"
                    )

                quantity = Decimal(str(line_data.quantity))
                unit_price = Decimal(str(line_data.unit_price))
                line_total = quantity * unit_price
                new_total += line_total
                unit_cost = material.current_average_cost
                if unit_cost == 0:
                    unit_cost = self._get_last_known_cost(db, material.id, organization_id)

                # Check stock por bodega (RN-INV-03: warning, no bloqueo)
                warehouse_stock = db.execute(
                    select(func.coalesce(func.sum(InventoryMovement.quantity), 0)).where(
                        InventoryMovement.material_id == material.id,
                        InventoryMovement.warehouse_id == effective_warehouse_id,
                        InventoryMovement.organization_id == organization_id,
                    )
                ).scalar()
                warehouse_stock = Decimal(str(warehouse_stock))

                if warehouse_stock < quantity:
                    resulting_stock = warehouse_stock - quantity
                    warnings.append(
                        f"Stock insuficiente de '{material.name}' en bodega. "
                        f"Disponible en bodega: {warehouse_stock}, "
                        f"Requerido: {quantity}. "
                        f"Stock resultante: {resulting_stock}"
                    )

                # Crear SaleLine
                new_line = SaleLine(
                    sale_id=sale.id,
                    material_id=line_data.material_id,
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=line_total,
                    unit_cost=unit_cost,
                )
                db.add(new_line)

                # Crear InventoryMovement
                movement = InventoryMovement(
                    organization_id=organization_id,
                    material_id=line_data.material_id,
                    warehouse_id=effective_warehouse_id,
                    movement_type="sale",
                    quantity=-quantity,
                    unit_cost=unit_cost,
                    reference_type="sale",
                    reference_id=sale.id,
                    date=obj_in.date or sale.date,
                    notes=f"Sale #{sale.sale_number} (edited)",
                )
                db.add(movement)

                # Actualizar stock
                material.current_stock -= quantity
                material.current_stock_liquidated -= quantity
                # Nueva linea: {material.code} x {quantity}

            sale.total_amount = new_total
        else:
            new_total = old_total

        # Step 4: Si hay comisiones nuevas, reemplazar
        if obj_in.commissions is not None:
            # Eliminar comisiones existentes (nunca fueron pagadas en status=registered)
            db.query(SaleCommission).filter(
                SaleCommission.sale_id == sale.id
            ).delete(synchronize_session=False)
            db.flush()

            # Crear nuevas comisiones
            if obj_in.commissions:
                self._process_commissions(db, sale, obj_in.commissions, new_total, organization_id)

        # Step 5: Si cambio de cliente, actualizar FK (sin ajuste de saldo — se aplica en liquidate)
        if new_customer:
            sale.customer_id = obj_in.customer_id

        # Step 6: Actualizar metadata
        if obj_in.date is not None:
            sale.date = obj_in.date
        if obj_in.notes is not None:
            sale.notes = obj_in.notes
        if obj_in.vehicle_plate is not None:
            sale.vehicle_plate = obj_in.vehicle_plate
        if obj_in.invoice_number is not None:
            sale.invoice_number = obj_in.invoice_number
        if obj_in.warehouse_id is not None:
            sale.warehouse_id = obj_in.warehouse_id

        if user_id:
            sale.updated_by = user_id

        db.flush()

        # Adjuntar warnings
        sale._warnings = warnings

        return sale

    def check_duplicate(
        self,
        db: Session,
        customer_id: UUID,
        date: datetime,
        organization_id: UUID
    ) -> int:
        """Contar ventas del mismo cliente en la misma fecha (no canceladas)."""
        sale_date = date.date() if hasattr(date, 'date') else date
        stmt = select(func.count()).select_from(Sale).where(
            Sale.organization_id == organization_id,
            Sale.customer_id == customer_id,
            func.date(Sale.date) == sale_date,
            Sale.status != "cancelled"
        )
        return db.scalar(stmt) or 0

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
            query = query.where(Sale.date < date_to)
        
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
                    detail=f"Receptor de comision {comm_data.third_party_id} no encontrado"
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
                detail="Venta no encontrada"
            )
        
        # Validate: Cannot delete sale that belongs to double-entry
        if sale.double_entry_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede eliminar una venta de doble partida. Cancele la doble partida."
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
