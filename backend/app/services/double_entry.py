"""
CRUD operations for DoubleEntry (Pasa Mano) model con soporte multi-material.

Business Rules:
- Material does NOT enter inventory (no stock movements)
- Creates linked Purchase and Sale records (both status='liquidated')
- Updates supplier balance (debt increases)
- Updates customer balance (receivable increases)
- Commissions paid immediately (sale is liquidated at creation)
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
from app.schemas.double_entry import DoubleEntryCreate, DoubleEntryUpdate
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

    def create(
        self,
        db: Session,
        obj_in: DoubleEntryCreate,
        organization_id: UUID,
        user_id: UUID = None
    ) -> DoubleEntry:
        """
        Crear doble partida con multiples materiales.

        Workflow:
        1. Generar numero secuencial
        2. Validar proveedor != cliente
        3. Validar proveedor y cliente
        4. Validar materiales (todos deben existir en la org)
        5. Calcular totales agregados
        6. Crear Purchase + PurchaseLines
        7. Crear Sale + SaleLines
        8. Crear comisiones (si hay)
        9. Actualizar saldo proveedor y cliente
        10. Crear DoubleEntry + DoubleEntryLines
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
        if not supplier.is_supplier:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El tercero no esta marcado como proveedor")

        # Step 4: Validar cliente
        customer = db.get(ThirdParty, obj_in.customer_id)
        if not customer or customer.organization_id != organization_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")
        if not customer.is_customer:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El tercero no esta marcado como cliente")

        # Step 5: Validar materiales y calcular totales
        materials = {}
        purchase_total = Decimal("0")
        sale_total = Decimal("0")

        for line_data in obj_in.lines:
            material = db.get(Material, line_data.material_id)
            if not material or material.organization_id != organization_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Material {line_data.material_id} no encontrado"
                )
            materials[line_data.material_id] = material

            quantity = Decimal(str(line_data.quantity))
            buy_price = Decimal(str(line_data.purchase_unit_price))
            sell_price = Decimal(str(line_data.sale_unit_price))
            purchase_total += quantity * buy_price
            sale_total += quantity * sell_price

        profit = sale_total - purchase_total

        print(f"🔄 Creating double-entry #{double_entry_number} ({len(obj_in.lines)} lineas)")
        print(f"   Supplier: {supplier.name} | Customer: {customer.name}")
        print(f"   Purchase Total: ${purchase_total} | Sale Total: ${sale_total} | Profit: ${profit}")

        # Step 6: Crear Purchase + PurchaseLines
        purchase_number = self._generate_purchase_number(db, organization_id)
        now_utc = datetime.now(timezone.utc)
        purchase = Purchase(
            organization_id=organization_id,
            purchase_number=purchase_number,
            supplier_id=obj_in.supplier_id,
            date=datetime.combine(obj_in.date, time(12, 0), tzinfo=timezone.utc),
            total_amount=purchase_total,
            status="liquidated",
            liquidated_at=now_utc,
            liquidated_by=user_id,
            notes=f"Double-entry #{double_entry_number}" + (f" - {obj_in.notes}" if obj_in.notes else ""),
        )
        db.add(purchase)
        db.flush()

        for line_data in obj_in.lines:
            quantity = Decimal(str(line_data.quantity))
            buy_price = Decimal(str(line_data.purchase_unit_price))
            purchase_line = PurchaseLine(
                purchase_id=purchase.id,
                material_id=line_data.material_id,
                warehouse_id=None,
                quantity=quantity,
                unit_price=buy_price,
                total_price=quantity * buy_price,
            )
            db.add(purchase_line)

        print(f"   ✅ Created Purchase #{purchase_number}")

        # Step 7: Crear Sale + SaleLines
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
            status="liquidated",
            liquidated_at=now_utc,
            liquidated_by=user_id,
            notes=f"Double-entry #{double_entry_number}" + (f" - {obj_in.notes}" if obj_in.notes else ""),
        )
        db.add(sale)
        db.flush()

        for line_data in obj_in.lines:
            quantity = Decimal(str(line_data.quantity))
            sell_price = Decimal(str(line_data.sale_unit_price))
            buy_price = Decimal(str(line_data.purchase_unit_price))
            sale_line = SaleLine(
                sale_id=sale.id,
                material_id=line_data.material_id,
                quantity=quantity,
                unit_price=sell_price,
                total_price=quantity * sell_price,
                unit_cost=buy_price,
            )
            db.add(sale_line)

        print(f"   ✅ Created Sale #{sale_number}")

        # Step 8: Crear comisiones y pagarlas (la venta ya esta liquidada)
        if obj_in.commissions:
            for comm_data in obj_in.commissions:
                recipient = db.get(ThirdParty, comm_data.third_party_id)
                if not recipient or recipient.organization_id != organization_id:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Receptor de comision {comm_data.third_party_id} no encontrado"
                    )
                commission_amount = self._calculate_commission(
                    comm_data.commission_type, comm_data.commission_value, sale_total
                )
                commission = SaleCommission(
                    sale_id=sale.id,
                    third_party_id=comm_data.third_party_id,
                    concept=comm_data.concept,
                    commission_type=comm_data.commission_type,
                    commission_value=comm_data.commission_value,
                    commission_amount=commission_amount,
                )
                db.add(commission)
                # Crear movimiento commission_accrual para P&L
                mm_service._create_movement(
                    db=db,
                    organization_id=organization_id,
                    movement_type="commission_accrual",
                    amount=commission_amount,
                    account_id=None,
                    date=sale.date,
                    description=f"Comisión DP #{double_entry_number} - {comm_data.concept}",
                    third_party_id=comm_data.third_party_id,
                    sale_id=sale.id,
                    user_id=user_id,
                )
                # Causar comision (les debemos → balance decreases)
                recipient.current_balance -= commission_amount
                print(f"   💼 Commission: {comm_data.concept} - ${commission_amount} (paid)")

        # Step 9: Actualizar saldos
        supplier.current_balance -= purchase_total
        customer.current_balance += sale_total
        print(f"   💰 Supplier balance: {supplier.current_balance + purchase_total} → {supplier.current_balance}")
        print(f"   💰 Customer balance: {customer.current_balance - sale_total} → {customer.current_balance}")

        # Step 10: Crear DoubleEntry + DoubleEntryLines
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
            status="completed",
        )
        db.add(double_entry)
        db.flush()

        for line_data in obj_in.lines:
            de_line = DoubleEntryLine(
                double_entry_id=double_entry.id,
                material_id=line_data.material_id,
                quantity=Decimal(str(line_data.quantity)),
                purchase_unit_price=Decimal(str(line_data.purchase_unit_price)),
                sale_unit_price=Decimal(str(line_data.sale_unit_price)),
            )
            db.add(de_line)

        # Step 11: Vincular Purchase y Sale con double_entry_id
        purchase.double_entry_id = double_entry.id
        sale.double_entry_id = double_entry.id

        db.commit()
        db.refresh(double_entry)

        print(f"✅ Double-entry #{double_entry_number} completed ({len(obj_in.lines)} materiales)")

        return double_entry

    def cancel(
        self,
        db: Session,
        double_entry_id: UUID,
        organization_id: UUID
    ) -> DoubleEntry:
        """Cancelar doble partida y revertir todos los efectos."""
        # Cargar con eager loading: lineas + sale.commissions para reversion
        double_entry = db.query(DoubleEntry).options(
            joinedload(DoubleEntry.lines),
            joinedload(DoubleEntry.sale).joinedload(Sale.commissions),
        ).filter(
            DoubleEntry.id == double_entry_id,
            DoubleEntry.organization_id == organization_id,
        ).first()

        if not double_entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doble partida no encontrada"
            )

        if double_entry.status == "cancelled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La doble partida ya esta cancelada"
            )

        purchase = db.get(Purchase, double_entry.purchase_id)
        sale = db.get(Sale, double_entry.sale_id)

        if not purchase or not sale:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Compra o venta vinculada no encontrada"
            )

        print(f"❌ Cancelling double-entry #{double_entry.double_entry_number}")

        purchase.status = "cancelled"
        sale.status = "cancelled"

        # Revertir saldos usando totales calculados desde lineas
        supplier = db.get(ThirdParty, double_entry.supplier_id)
        supplier.current_balance += double_entry.total_purchase_cost
        print(f"   💰 Supplier balance reverted: +${double_entry.total_purchase_cost}")

        customer = db.get(ThirdParty, double_entry.customer_id)
        customer.current_balance -= double_entry.total_sale_amount
        print(f"   💰 Customer balance reverted: -${double_entry.total_sale_amount}")

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
            mov.annulled_at = datetime.now(timezone.utc)
            mov.annulled_reason = f"Cancelación DP #{double_entry.double_entry_number}"
            print(f"   📝 Commission accrual #{mov.movement_number} anulado")

        # Revertir comisiones causadas (balance was decreased, now increase back)
        for comm in sale.commissions:
            recipient = db.get(ThirdParty, comm.third_party_id)
            recipient.current_balance += comm.commission_amount
            print(f"   💼 Commission reverted for '{recipient.name}': +${comm.commission_amount}")

        double_entry.status = "cancelled"

        db.commit()
        db.refresh(double_entry)

        print(f"✅ Double-entry #{double_entry.double_entry_number} cancelled")

        return double_entry

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
            # Filtrar por material via subquery en lineas
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
        sale_total: Decimal
    ) -> Decimal:
        if commission_type == "percentage":
            return (commission_value / Decimal("100")) * sale_total
        elif commission_type == "fixed":
            return commission_value
        else:
            raise ValueError(f"Invalid commission_type: {commission_type}")


# Create singleton instance
crud_double_entry = CRUDDoubleEntry(DoubleEntry)
double_entry = CRUDDoubleEntry(DoubleEntry)
