"""
CRUD operations for DoubleEntry (Pasa Mano) model con soporte multi-material.

Business Rules (2-step workflow):
- REGISTRAR: Crea DP + Purchase + Sale en status='registered'. Sin efectos financieros.
- LIQUIDAR: Confirma precios, actualiza balances proveedor/cliente, paga comisiones.
- Material does NOT enter inventory (no stock movements) en ningun paso.
"""
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func, text, or_, cast, String
from sqlalchemy.orm import Session, joinedload

from app.models.double_entry import DoubleEntry, DoubleEntryLine
from app.models.purchase import Purchase, PurchaseLine
from app.models.sale import Sale, SaleLine, SaleCommission
from app.models.material import Material
from app.models.third_party import ThirdParty
from app.models.money_movement import MoneyMovement
from app.schemas.double_entry import (
    DoubleEntryCreate, DoubleEntryUpdate, DoubleEntryFullUpdate,
    DoubleEntryLiquidateLineUpdate,
)
from app.schemas.sale import SaleCommissionCreate
from app.services.base import CRUDBase
from app.services.money_movement import money_movement as mm_service


class CRUDDoubleEntry(CRUDBase[DoubleEntry, DoubleEntryCreate, DoubleEntryUpdate]):
    """CRUD operations for DoubleEntry with business logic."""

    def _eager_options(self):
        """Opciones de eager loading comunes para todas las queries."""
        return [
            joinedload(DoubleEntry.lines).joinedload(DoubleEntryLine.material),
            joinedload(DoubleEntry.supplier),
            joinedload(DoubleEntry.customer),
            joinedload(DoubleEntry.sale).joinedload(Sale.commissions).joinedload(SaleCommission.third_party),
        ]

    # ========================================================================
    # CREATE (Registro — sin efectos financieros)
    # ========================================================================

    def create(
        self,
        db: Session,
        obj_in: DoubleEntryCreate,
        organization_id: UUID,
        user_id: UUID = None
    ) -> DoubleEntry:
        """
        Registrar doble partida con multiples materiales.
        SIN efectos financieros (balances, comisiones).
        """
        # Step 1: Generar numero secuencial
        double_entry_number = self._generate_double_entry_number(db, organization_id)

        # Step 2: Validar proveedor != cliente
        if obj_in.supplier_id == obj_in.customer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El proveedor y el cliente no pueden ser el mismo tercero"
            )

        # Step 3: Validar proveedor
        supplier = db.get(ThirdParty, obj_in.supplier_id)
        if not supplier or supplier.organization_id != organization_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado")
        if not supplier.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"El proveedor '{supplier.name}' esta inactivo")
        from app.services.third_party import third_party as tp_service
        if not tp_service.has_behavior_type(db, supplier.id, ["material_supplier"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El tercero no es proveedor de material")

        # Step 4: Validar cliente
        customer = db.get(ThirdParty, obj_in.customer_id)
        if not customer or customer.organization_id != organization_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")
        if not customer.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"El cliente '{customer.name}' esta inactivo")
        if not tp_service.has_behavior_type(db, customer.id, ["customer"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El tercero no es cliente")

        # Step 5: Validar materiales y calcular totales
        purchase_total, sale_total = self._validate_and_calc_totals(db, obj_in.lines, organization_id)

        print(f"🔄 Registering double-entry #{double_entry_number} ({len(obj_in.lines)} lineas)")

        # Step 6: Crear Purchase (registered, sin liquidar)
        purchase_number = self._generate_purchase_number(db, organization_id)
        purchase = Purchase(
            organization_id=organization_id,
            purchase_number=purchase_number,
            supplier_id=obj_in.supplier_id,
            date=datetime.combine(obj_in.date, time(12, 0), tzinfo=timezone.utc),
            total_amount=purchase_total,
            status="registered",
            created_by=user_id,
            notes=f"Doble partida #{double_entry_number}" + (f" - {obj_in.notes}" if obj_in.notes else ""),
        )
        db.add(purchase)
        db.flush()

        for line_data in obj_in.lines:
            quantity = Decimal(str(line_data.quantity))
            buy_price = Decimal(str(line_data.purchase_unit_price))
            db.add(PurchaseLine(
                purchase_id=purchase.id,
                material_id=line_data.material_id,
                warehouse_id=None,
                quantity=quantity,
                unit_price=buy_price,
                total_price=quantity * buy_price,
            ))

        # Step 7: Crear Sale (registered, sin liquidar)
        sale_number = self._generate_sale_number(db, organization_id)
        sale = Sale(
            organization_id=organization_id,
            sale_number=sale_number,
            customer_id=obj_in.customer_id,
            warehouse_id=None,
            date=datetime.combine(obj_in.date, time(12, 0), tzinfo=timezone.utc),
            vehicle_plate=obj_in.vehicle_plate,
            invoice_number=obj_in.invoice_number,
            total_amount=sale_total,
            status="registered",
            created_by=user_id,
            notes=f"Doble partida #{double_entry_number}" + (f" - {obj_in.notes}" if obj_in.notes else ""),
        )
        db.add(sale)
        db.flush()

        for line_data in obj_in.lines:
            quantity = Decimal(str(line_data.quantity))
            sell_price = Decimal(str(line_data.sale_unit_price))
            buy_price = Decimal(str(line_data.purchase_unit_price))
            db.add(SaleLine(
                sale_id=sale.id,
                material_id=line_data.material_id,
                quantity=quantity,
                unit_price=sell_price,
                total_price=quantity * sell_price,
                unit_cost=buy_price,
            ))

        # Step 8: Crear comisiones como registros (SIN MoneyMovement, SIN balances)
        if obj_in.commissions:
            total_qty = sum(Decimal(str(l.quantity)) for l in obj_in.lines)
            self._create_commission_records(db, sale.id, obj_in.commissions, sale_total, organization_id, total_qty)

        # Step 9: Crear DoubleEntry (registered)
        double_entry = DoubleEntry(
            organization_id=organization_id,
            double_entry_number=double_entry_number,
            date=obj_in.date,
            supplier_id=obj_in.supplier_id,
            customer_id=obj_in.customer_id,
            invoice_number=obj_in.invoice_number,
            vehicle_plate=obj_in.vehicle_plate,
            notes=obj_in.notes,
            purchase_id=purchase.id,
            sale_id=sale.id,
            status="registered",
            created_by=user_id,
        )
        db.add(double_entry)
        db.flush()

        for line_data in obj_in.lines:
            db.add(DoubleEntryLine(
                double_entry_id=double_entry.id,
                material_id=line_data.material_id,
                quantity=Decimal(str(line_data.quantity)),
                purchase_unit_price=Decimal(str(line_data.purchase_unit_price)),
                sale_unit_price=Decimal(str(line_data.sale_unit_price)),
            ))

        # Step 10: Vincular Purchase y Sale con double_entry_id
        purchase.double_entry_id = double_entry.id
        sale.double_entry_id = double_entry.id

        db.commit()
        db.refresh(double_entry)

        print(f"✅ Double-entry #{double_entry_number} registered ({len(obj_in.lines)} materiales)")

        # Step 11: Auto-liquidar si se solicita
        if obj_in.auto_liquidate:
            print(f"  🔄 Auto-liquidating double-entry #{double_entry_number}...")
            double_entry = self.liquidate(
                db=db,
                double_entry_id=double_entry.id,
                organization_id=organization_id,
                user_id=user_id,
            )

        return double_entry

    # ========================================================================
    # LIQUIDATE (Aplica efectos financieros)
    # ========================================================================

    def liquidate(
        self,
        db: Session,
        double_entry_id: UUID,
        organization_id: UUID,
        user_id: UUID = None,
        line_updates: Optional[List[DoubleEntryLiquidateLineUpdate]] = None,
        commissions_data: Optional[List[SaleCommissionCreate]] = None,
    ) -> DoubleEntry:
        """
        Liquidar doble partida registrada: confirmar precios, actualizar balances, pagar comisiones.
        """
        # Step 1: Cargar DP con relaciones
        double_entry = db.query(DoubleEntry).options(
            joinedload(DoubleEntry.lines),
            joinedload(DoubleEntry.sale).joinedload(Sale.commissions),
        ).filter(
            DoubleEntry.id == double_entry_id,
            DoubleEntry.organization_id == organization_id,
        ).first()

        if not double_entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doble partida no encontrada")

        if double_entry.status != "registered":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede liquidar doble partida con estado '{double_entry.status}'. Debe estar 'registered'"
            )

        purchase = db.get(Purchase, double_entry.purchase_id)
        sale = db.get(Sale, double_entry.sale_id)

        now_utc = datetime.now(timezone.utc)

        # Step 2: Si hay line_updates, actualizar precios
        if line_updates:
            update_map = {str(lu.line_id): lu for lu in line_updates}

            # Actualizar DoubleEntryLines
            for de_line in double_entry.lines:
                lu = update_map.get(str(de_line.id))
                if lu:
                    de_line.purchase_unit_price = lu.purchase_unit_price
                    de_line.sale_unit_price = lu.sale_unit_price

            # Actualizar PurchaseLines
            purchase_lines = db.scalars(select(PurchaseLine).where(PurchaseLine.purchase_id == purchase.id)).all()
            # Mapear por material_id para sincronizar con DE lines
            pl_by_material = {str(pl.material_id): pl for pl in purchase_lines}
            for de_line in double_entry.lines:
                pl = pl_by_material.get(str(de_line.material_id))
                if pl:
                    pl.unit_price = de_line.purchase_unit_price
                    pl.total_price = de_line.quantity * de_line.purchase_unit_price

            # Actualizar SaleLines
            sale_lines = db.scalars(select(SaleLine).where(SaleLine.sale_id == sale.id)).all()
            sl_by_material = {str(sl.material_id): sl for sl in sale_lines}
            for de_line in double_entry.lines:
                sl = sl_by_material.get(str(de_line.material_id))
                if sl:
                    sl.unit_price = de_line.sale_unit_price
                    sl.total_price = de_line.quantity * de_line.sale_unit_price
                    sl.unit_cost = de_line.purchase_unit_price

        # Recalcular totales
        purchase_total = sum(
            de_line.quantity * de_line.purchase_unit_price for de_line in double_entry.lines
        )
        sale_total = sum(
            de_line.quantity * de_line.sale_unit_price for de_line in double_entry.lines
        )
        purchase.total_amount = purchase_total
        sale.total_amount = sale_total

        # Step 3: Si hay commissions_data, reemplazar comisiones
        if commissions_data is not None:
            db.query(SaleCommission).filter(SaleCommission.sale_id == sale.id).delete(synchronize_session=False)
            db.flush()
            if commissions_data:
                total_qty = sum(de_line.quantity for de_line in double_entry.lines)
                self._create_commission_records(db, sale.id, commissions_data, sale_total, organization_id, total_qty)
                db.flush()

        # Step 4: Actualizar balances proveedor/cliente
        supplier = db.get(ThirdParty, double_entry.supplier_id)
        supplier.current_balance -= purchase_total
        print(f"  💰 Supplier '{supplier.name}' balance: {supplier.current_balance + purchase_total} → {supplier.current_balance}")

        customer = db.get(ThirdParty, double_entry.customer_id)
        customer.current_balance += sale_total
        print(f"  💰 Customer '{customer.name}' balance: {customer.current_balance - sale_total} → {customer.current_balance}")

        # Step 5: Pagar comisiones (crear MoneyMovements + actualizar balances)
        commissions = db.scalars(select(SaleCommission).where(SaleCommission.sale_id == sale.id)).all()
        for commission in commissions:
            recipient = db.get(ThirdParty, commission.third_party_id)
            mm_service._create_movement(
                db=db,
                organization_id=organization_id,
                movement_type="commission_accrual",
                amount=commission.commission_amount,
                account_id=None,
                date=sale.date,
                description=f"Comisión DP #{double_entry.double_entry_number} - {commission.concept}",
                third_party_id=commission.third_party_id,
                sale_id=sale.id,
                user_id=user_id,
            )
            recipient.current_balance -= commission.commission_amount
            print(f"  💼 Commission: {commission.concept} - ${commission.commission_amount}")

        # Step 6: Marcar como liquidated
        purchase.status = "liquidated"
        purchase.liquidated_at = now_utc
        purchase.liquidated_by = user_id

        sale.status = "liquidated"
        sale.liquidated_at = now_utc
        sale.liquidated_by = user_id

        double_entry.status = "liquidated"
        double_entry.liquidated_at = now_utc
        double_entry.liquidated_by = user_id

        db.commit()
        db.refresh(double_entry)

        print(f"✅ Double-entry #{double_entry.double_entry_number} liquidated")
        return double_entry

    # ========================================================================
    # EDIT (Solo para registered)
    # ========================================================================

    def edit(
        self,
        db: Session,
        double_entry_id: UUID,
        obj_in: DoubleEntryFullUpdate,
        organization_id: UUID,
        user_id: UUID = None,
    ) -> DoubleEntry:
        """Editar doble partida registrada (lineas, terceros, comisiones, metadata)."""
        double_entry = db.query(DoubleEntry).options(
            joinedload(DoubleEntry.lines),
        ).filter(
            DoubleEntry.id == double_entry_id,
            DoubleEntry.organization_id == organization_id,
        ).first()

        if not double_entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doble partida no encontrada")

        if double_entry.status != "registered":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Solo se pueden editar doble partidas en estado 'registered'. Estado actual: '{double_entry.status}'"
            )

        purchase = db.get(Purchase, double_entry.purchase_id)
        sale = db.get(Sale, double_entry.sale_id)

        # Validar terceros si cambian
        new_supplier_id = obj_in.supplier_id or double_entry.supplier_id
        new_customer_id = obj_in.customer_id or double_entry.customer_id
        if new_supplier_id == new_customer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El proveedor y el cliente no pueden ser el mismo tercero"
            )

        if obj_in.supplier_id and obj_in.supplier_id != double_entry.supplier_id:
            supplier = db.get(ThirdParty, obj_in.supplier_id)
            if not supplier or supplier.organization_id != organization_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado")
            from app.services.third_party import third_party as tp_service
            if not tp_service.has_behavior_type(db, supplier.id, ["material_supplier"]):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El tercero no es proveedor de material")
            double_entry.supplier_id = obj_in.supplier_id
            purchase.supplier_id = obj_in.supplier_id

        if obj_in.customer_id and obj_in.customer_id != double_entry.customer_id:
            customer = db.get(ThirdParty, obj_in.customer_id)
            if not customer or customer.organization_id != organization_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")
            from app.services.third_party import third_party as tp_service
            if not tp_service.has_behavior_type(db, customer.id, ["customer"]):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El tercero no es cliente")
            double_entry.customer_id = obj_in.customer_id
            sale.customer_id = obj_in.customer_id

        # Si cambian lineas: eliminar todo y recrear
        if obj_in.lines is not None:
            # Validar materiales
            purchase_total, sale_total = self._validate_and_calc_totals(db, obj_in.lines, organization_id)

            # Eliminar lineas existentes
            db.query(DoubleEntryLine).filter(DoubleEntryLine.double_entry_id == double_entry.id).delete(synchronize_session=False)
            db.query(PurchaseLine).filter(PurchaseLine.purchase_id == purchase.id).delete(synchronize_session=False)
            db.query(SaleLine).filter(SaleLine.sale_id == sale.id).delete(synchronize_session=False)
            db.query(SaleCommission).filter(SaleCommission.sale_id == sale.id).delete(synchronize_session=False)
            db.flush()

            # Recrear lineas
            for line_data in obj_in.lines:
                quantity = Decimal(str(line_data.quantity))
                buy_price = Decimal(str(line_data.purchase_unit_price))
                sell_price = Decimal(str(line_data.sale_unit_price))

                db.add(DoubleEntryLine(
                    double_entry_id=double_entry.id,
                    material_id=line_data.material_id,
                    quantity=quantity,
                    purchase_unit_price=buy_price,
                    sale_unit_price=sell_price,
                ))
                db.add(PurchaseLine(
                    purchase_id=purchase.id,
                    material_id=line_data.material_id,
                    warehouse_id=None,
                    quantity=quantity,
                    unit_price=buy_price,
                    total_price=quantity * buy_price,
                ))
                db.add(SaleLine(
                    sale_id=sale.id,
                    material_id=line_data.material_id,
                    quantity=quantity,
                    unit_price=sell_price,
                    total_price=quantity * sell_price,
                    unit_cost=buy_price,
                ))

            purchase.total_amount = purchase_total
            sale.total_amount = sale_total

            # Recrear comisiones si se proporcionaron
            if obj_in.commissions is not None and obj_in.commissions:
                total_qty = sum(Decimal(str(l.quantity)) for l in obj_in.lines)
                self._create_commission_records(db, sale.id, obj_in.commissions, sale_total, organization_id, total_qty)
        elif obj_in.commissions is not None:
            # Solo cambio de comisiones (sin cambio de lineas)
            db.query(SaleCommission).filter(SaleCommission.sale_id == sale.id).delete(synchronize_session=False)
            db.flush()
            if obj_in.commissions:
                sale_total_current = sum(
                    de_line.quantity * de_line.sale_unit_price for de_line in double_entry.lines
                )
                total_qty = sum(de_line.quantity for de_line in double_entry.lines)
                self._create_commission_records(db, sale.id, obj_in.commissions, sale_total_current, organization_id, total_qty)

        # Actualizar metadata
        if obj_in.date is not None:
            double_entry.date = obj_in.date
            date_dt = datetime.combine(obj_in.date, time(12, 0), tzinfo=timezone.utc)
            purchase.date = date_dt
            sale.date = date_dt

        if obj_in.invoice_number is not None:
            double_entry.invoice_number = obj_in.invoice_number
            sale.invoice_number = obj_in.invoice_number
        if obj_in.vehicle_plate is not None:
            double_entry.vehicle_plate = obj_in.vehicle_plate
            sale.vehicle_plate = obj_in.vehicle_plate
        if obj_in.notes is not None:
            double_entry.notes = obj_in.notes
            de_num = double_entry.double_entry_number
            purchase.notes = f"Doble partida #{de_num}" + (f" - {obj_in.notes}" if obj_in.notes else "")
            sale.notes = f"Doble partida #{de_num}" + (f" - {obj_in.notes}" if obj_in.notes else "")

        db.commit()
        db.refresh(double_entry)

        print(f"✅ Double-entry #{double_entry.double_entry_number} edited")
        return double_entry

    # ========================================================================
    # CANCEL
    # ========================================================================

    def cancel(
        self,
        db: Session,
        double_entry_id: UUID,
        organization_id: UUID,
        user_id: UUID = None,
    ) -> DoubleEntry:
        """Cancelar doble partida y revertir efectos segun estado."""
        double_entry = db.query(DoubleEntry).options(
            joinedload(DoubleEntry.lines),
            joinedload(DoubleEntry.sale).joinedload(Sale.commissions),
        ).filter(
            DoubleEntry.id == double_entry_id,
            DoubleEntry.organization_id == organization_id,
        ).first()

        if not double_entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doble partida no encontrada")

        if double_entry.status == "cancelled":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La doble partida ya esta cancelada")

        purchase = db.get(Purchase, double_entry.purchase_id)
        sale = db.get(Sale, double_entry.sale_id)
        now_utc = datetime.now(timezone.utc)

        print(f"❌ Cancelling double-entry #{double_entry.double_entry_number} (was: {double_entry.status})")

        if double_entry.status == "liquidated":
            # Revertir balances proveedor/cliente
            supplier = db.get(ThirdParty, double_entry.supplier_id)
            supplier.current_balance += double_entry.total_purchase_cost
            print(f"  💰 Supplier balance reverted: +${double_entry.total_purchase_cost}")

            customer = db.get(ThirdParty, double_entry.customer_id)
            customer.current_balance -= double_entry.total_sale_amount
            print(f"  💰 Customer balance reverted: -${double_entry.total_sale_amount}")

            # Anular movimientos commission_accrual
            comm_movements = db.scalars(
                select(MoneyMovement).where(
                    MoneyMovement.sale_id == sale.id,
                    MoneyMovement.movement_type == "commission_accrual",
                    MoneyMovement.status == "confirmed",
                )
            ).all()
            for mov in comm_movements:
                mov.status = "annulled"
                mov.annulled_at = now_utc
                mov.annulled_reason = f"Cancelación DP #{double_entry.double_entry_number}"

            # Revertir comisiones causadas
            for comm in sale.commissions:
                recipient = db.get(ThirdParty, comm.third_party_id)
                recipient.current_balance += comm.commission_amount
                print(f"  💼 Commission reverted for '{recipient.name}': +${comm.commission_amount}")

        # Marcar como cancelled (para ambos: registered y liquidated)
        purchase.status = "cancelled"
        purchase.cancelled_at = now_utc
        sale.status = "cancelled"
        sale.cancelled_at = now_utc

        double_entry.status = "cancelled"
        double_entry.cancelled_at = now_utc
        double_entry.cancelled_by = user_id

        db.commit()
        db.refresh(double_entry)

        print(f"✅ Double-entry #{double_entry.double_entry_number} cancelled")
        return double_entry

    # ========================================================================
    # READ Methods
    # ========================================================================

    def get(
        self,
        db: Session,
        double_entry_id: UUID,
        organization_id: UUID
    ) -> Optional[DoubleEntry]:
        """Get double_entry por ID con eager loading."""
        return db.query(DoubleEntry).options(
            *self._eager_options()
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
        """Get double_entry por numero secuencial."""
        return db.query(DoubleEntry).options(
            *self._eager_options()
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
        """Get double_entries por proveedor con paginacion."""
        query = db.query(DoubleEntry).filter(
            DoubleEntry.supplier_id == supplier_id,
            DoubleEntry.organization_id == organization_id
        )
        total = query.count()
        double_entries = query.options(
            *self._eager_options()
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
        """Get double_entries por cliente con paginacion."""
        query = db.query(DoubleEntry).filter(
            DoubleEntry.customer_id == customer_id,
            DoubleEntry.organization_id == organization_id
        )
        total = query.count()
        double_entries = query.options(
            *self._eager_options()
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
        """Get multiple double_entries con filtros y paginacion."""
        query = db.query(DoubleEntry).filter(
            DoubleEntry.organization_id == organization_id
        )

        if status:
            query = query.filter(DoubleEntry.status == status)

        if material_id:
            query = query.filter(DoubleEntry.id.in_(
                select(DoubleEntryLine.double_entry_id).where(
                    DoubleEntryLine.material_id == material_id
                )
            ))

        if supplier_id:
            query = query.filter(DoubleEntry.supplier_id == supplier_id)

        if customer_id:
            query = query.filter(DoubleEntry.customer_id == customer_id)

        if date_from:
            query = query.filter(DoubleEntry.date >= date_from)

        if date_to:
            query = query.filter(DoubleEntry.date < date_to)

        if search:
            query = query.filter(
                or_(
                    cast(DoubleEntry.double_entry_number, String).ilike(f"%{search}%"),
                    func.coalesce(DoubleEntry.notes, '').ilike(f"%{search}%"),
                    func.coalesce(DoubleEntry.invoice_number, '').ilike(f"%{search}%"),
                )
            )

        total = query.count()

        double_entries = query.options(
            *self._eager_options()
        ).order_by(DoubleEntry.date.desc()).offset(skip).limit(limit).all()

        return double_entries, total

    def update(
        self,
        db: Session,
        double_entry_id: UUID,
        obj_in: DoubleEntryUpdate,
        organization_id: UUID
    ) -> DoubleEntry:
        """Actualizar metadata de doble partida (notes, invoice, plate)."""
        double_entry = db.get(DoubleEntry, double_entry_id)
        if not double_entry or double_entry.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doble partida no encontrada"
            )

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

    def _validate_and_calc_totals(
        self, db: Session, lines, organization_id: UUID
    ) -> tuple[Decimal, Decimal]:
        """Validar materiales y calcular totales de compra/venta."""
        purchase_total = Decimal("0")
        sale_total = Decimal("0")
        for line_data in lines:
            material = db.get(Material, line_data.material_id)
            if not material or material.organization_id != organization_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Material {line_data.material_id} no encontrado"
                )
            quantity = Decimal(str(line_data.quantity))
            purchase_total += quantity * Decimal(str(line_data.purchase_unit_price))
            sale_total += quantity * Decimal(str(line_data.sale_unit_price))
        return purchase_total, sale_total

    def _create_commission_records(
        self,
        db: Session,
        sale_id: UUID,
        commissions_data: List[SaleCommissionCreate],
        sale_total: Decimal,
        organization_id: UUID,
        total_quantity: Decimal = Decimal("0"),
    ) -> None:
        """Crear SaleCommission records sin efectos financieros."""
        for comm_data in commissions_data:
            recipient = db.get(ThirdParty, comm_data.third_party_id)
            if not recipient or recipient.organization_id != organization_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Receptor de comision {comm_data.third_party_id} no encontrado"
                )
            from app.services.third_party import third_party as tp_service
            if not tp_service.has_behavior_type(db, recipient.id, ["service_provider"]):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El comisionista '{recipient.name}' debe ser proveedor de servicios",
                )
            commission_amount = self._calculate_commission(
                comm_data.commission_type, comm_data.commission_value, sale_total, total_quantity
            )
            db.add(SaleCommission(
                sale_id=sale_id,
                third_party_id=comm_data.third_party_id,
                concept=comm_data.concept,
                commission_type=comm_data.commission_type,
                commission_value=comm_data.commission_value,
                commission_amount=commission_amount,
            ))

    def _generate_double_entry_number(self, db: Session, organization_id: UUID) -> int:
        lock_id = hash(f"double_entries_{organization_id}") % (2**31)
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
        return db.execute(
            text("SELECT COALESCE(MAX(double_entry_number), 0) + 1 FROM double_entries WHERE organization_id = :org_id"),
            {"org_id": str(organization_id)}
        ).scalar()

    def _generate_purchase_number(self, db: Session, organization_id: UUID) -> int:
        lock_id = hash(f"purchases_{organization_id}") % (2**31)
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
        return db.execute(
            text("SELECT COALESCE(MAX(purchase_number), 0) + 1 FROM purchases WHERE organization_id = :org_id"),
            {"org_id": str(organization_id)}
        ).scalar()

    def _generate_sale_number(self, db: Session, organization_id: UUID) -> int:
        lock_id = hash(f"sales_{organization_id}") % (2**31)
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
        return db.execute(
            text("SELECT COALESCE(MAX(sale_number), 0) + 1 FROM sales WHERE organization_id = :org_id"),
            {"org_id": str(organization_id)}
        ).scalar()

    def _calculate_commission(
        self,
        commission_type: str,
        commission_value: Decimal,
        sale_total: Decimal,
        total_quantity: Decimal = Decimal("0"),
    ) -> Decimal:
        if commission_type == "percentage":
            return (commission_value / Decimal("100")) * sale_total
        elif commission_type == "per_kg":
            return commission_value * total_quantity
        elif commission_type == "fixed":
            return commission_value
        else:
            raise ValueError(f"Invalid commission_type: {commission_type}")


# Create singleton instance
crud_double_entry = CRUDDoubleEntry(DoubleEntry)
double_entry = CRUDDoubleEntry(DoubleEntry)
