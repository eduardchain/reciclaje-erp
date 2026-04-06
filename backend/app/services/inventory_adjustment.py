"""
Operaciones CRUD para InventoryAdjustment (Ajustes de Inventario).

Cada metodo publico corresponde a un tipo de ajuste:
- increase: Aumento de stock (recalcula costo promedio)
- decrease: Disminucion de stock (usa costo promedio actual)
- recount: Conteo fisico (calcula delta automaticamente)
- zero_out: Llevar stock a cero
- annul: Anular ajuste con reversion de stock

Tambien incluye transfer_between_warehouses para traslados entre bodegas.

Todos los ajustes afectan current_stock_liquidated (no transito).
Stock negativo PERMITIDO con warning (RN-INV-03).
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select, func, text, or_, cast, String
from sqlalchemy.orm import Session, joinedload

from app.models.inventory_adjustment import InventoryAdjustment, VALID_ADJUSTMENT_TYPES
from app.models.inventory_movement import InventoryMovement
from app.models.material import Material
from app.models.warehouse import Warehouse
from app.schemas.inventory_adjustment import (
    IncreaseCreate,
    DecreaseCreate,
    RecountCreate,
    ZeroOutCreate,
    WarehouseTransferCreate,
)


from app.services.material_cost_history import material_cost_history_service


class CRUDInventoryAdjustment:
    """
    Operaciones para ajustes manuales de inventario.

    Cada ajuste afecta current_stock_liquidated de un material.
    Crea un InventoryMovement como audit trail.
    """

    # ======================================================================
    # Metodos publicos — uno por tipo de ajuste
    # ======================================================================

    def increase(
        self,
        db: Session,
        data: IncreaseCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> tuple[InventoryAdjustment, list[str]]:
        """
        Aumento de stock — recalcula costo promedio.

        Efectos:
        - material.current_stock_liquidated += quantity
        - material.current_stock += quantity
        - Recalcula current_average_cost con promedio ponderado
        """
        material = self._validate_material(db, data.material_id, organization_id)
        warehouse = self._validate_warehouse(db, data.warehouse_id, organization_id)
        warnings: list[str] = []

        previous_stock = material.current_stock_liquidated
        new_stock = previous_stock + data.quantity

        # Recalcular costo promedio (solo stock liquidado, transito no afecta costo)
        old_liquidated = material.current_stock_liquidated
        old_cost = material.current_average_cost
        if old_liquidated <= 0:
            material.current_average_cost = data.unit_cost
        else:
            total_old_value = old_liquidated * old_cost
            total_new_value = data.quantity * data.unit_cost
            material.current_average_cost = (total_old_value + total_new_value) / (old_liquidated + data.quantity)

        # Aplicar cambio de stock
        material.current_stock_liquidated = new_stock
        material.current_stock += data.quantity

        # Crear ajuste (necesitamos el ID para el historial de costo)
        adjustment = self._create_adjustment(
            db=db,
            organization_id=organization_id,
            adjustment_type="increase",
            material_id=data.material_id,
            warehouse_id=data.warehouse_id,
            date=data.date,
            previous_stock=previous_stock,
            quantity=data.quantity,
            new_stock=new_stock,
            unit_cost=data.unit_cost,
            total_value=abs(data.quantity * data.unit_cost),
            reason=data.reason,
            notes=data.notes,
            user_id=user_id,
        )

        # Registrar cambio de costo en historial
        material_cost_history_service.record_cost_change(
            db=db,
            material=material,
            previous_cost=old_cost,
            previous_stock=old_liquidated,
            new_cost=material.current_average_cost,
            new_stock=material.current_stock_liquidated,
            source_type="adjustment_increase",
            source_id=adjustment.id,
            organization_id=organization_id,
            transaction_date=data.date.date() if hasattr(data.date, "date") else data.date,
        )

        # Crear InventoryMovement
        self._create_inventory_movement(
            db=db,
            organization_id=organization_id,
            material_id=data.material_id,
            warehouse_id=data.warehouse_id,
            movement_type="adjustment",
            quantity=data.quantity,
            unit_cost=data.unit_cost,
            date=data.date,
            reference_id=adjustment.id,
            notes=f"Ajuste aumento #{adjustment.adjustment_number}: {data.reason}",
        )

        db.commit()
        db.refresh(adjustment)
        return adjustment, warnings

    def decrease(
        self,
        db: Session,
        data: DecreaseCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> tuple[InventoryAdjustment, list[str]]:
        """
        Disminucion de stock — usa costo promedio actual.

        Efectos:
        - material.current_stock_liquidated -= quantity
        - material.current_stock -= quantity
        - NO recalcula costo promedio (salidas usan costo actual)
        """
        material = self._validate_material(db, data.material_id, organization_id)
        warehouse = self._validate_warehouse(db, data.warehouse_id, organization_id)
        warnings: list[str] = []

        previous_stock = material.current_stock_liquidated
        new_stock = previous_stock - data.quantity
        unit_cost = material.current_average_cost

        # Warning si stock resultante es negativo (RN-INV-03: permitido con warning)
        if new_stock < 0:
            warnings.append(
                f"Stock negativo para '{material.name}': resultara en {new_stock} {material.default_unit}"
            )

        # Aplicar cambio de stock (permitir negativo)
        material.current_stock_liquidated = new_stock
        material.current_stock -= data.quantity

        adjustment = self._create_adjustment(
            db=db,
            organization_id=organization_id,
            adjustment_type="decrease",
            material_id=data.material_id,
            warehouse_id=data.warehouse_id,
            date=data.date,
            previous_stock=previous_stock,
            quantity=-data.quantity,
            new_stock=new_stock,
            unit_cost=unit_cost,
            total_value=abs(data.quantity * unit_cost),
            reason=data.reason,
            notes=data.notes,
            user_id=user_id,
        )

        self._create_inventory_movement(
            db=db,
            organization_id=organization_id,
            material_id=data.material_id,
            warehouse_id=data.warehouse_id,
            movement_type="adjustment",
            quantity=-data.quantity,
            unit_cost=unit_cost,
            date=data.date,
            reference_id=adjustment.id,
            notes=f"Ajuste disminucion #{adjustment.adjustment_number}: {data.reason}",
        )

        db.commit()
        db.refresh(adjustment)
        return adjustment, warnings

    def recount(
        self,
        db: Session,
        data: RecountCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> tuple[InventoryAdjustment, list[str]]:
        """
        Conteo fisico — calcula delta automaticamente.

        Si contado > actual: es un increase (recalcula avg cost)
        Si contado < actual: es un decrease (no recalcula avg cost)
        Si contado == actual: crea registro pero sin cambio de stock
        """
        material = self._validate_material(db, data.material_id, organization_id)
        warehouse = self._validate_warehouse(db, data.warehouse_id, organization_id)
        warnings: list[str] = []

        previous_stock = material.current_stock_liquidated
        quantity_delta = data.counted_quantity - previous_stock
        new_stock = data.counted_quantity
        unit_cost = material.current_average_cost

        # Si es aumento (contamos mas de lo registrado), recalcular costo promedio
        if quantity_delta > 0:
            old_total = material.current_stock
            old_cost = material.current_average_cost
            if old_total <= 0:
                pass  # Mantener costo promedio actual para recount
            else:
                total_old_value = old_total * old_cost
                total_new_value = quantity_delta * old_cost  # Recount usa costo actual
                material.current_average_cost = (total_old_value + total_new_value) / (old_total + quantity_delta)

        # Aplicar cambio de stock
        material.current_stock_liquidated = new_stock
        material.current_stock += quantity_delta

        if new_stock < 0:
            warnings.append(
                f"Stock negativo para '{material.name}': resultara en {new_stock} {material.default_unit}"
            )

        adjustment = self._create_adjustment(
            db=db,
            organization_id=organization_id,
            adjustment_type="recount",
            material_id=data.material_id,
            warehouse_id=data.warehouse_id,
            date=data.date,
            previous_stock=previous_stock,
            quantity=quantity_delta,
            new_stock=new_stock,
            counted_quantity=data.counted_quantity,
            unit_cost=unit_cost,
            total_value=abs(quantity_delta * unit_cost),
            reason=data.reason,
            notes=data.notes,
            user_id=user_id,
        )

        if quantity_delta != 0:
            self._create_inventory_movement(
                db=db,
                organization_id=organization_id,
                material_id=data.material_id,
                warehouse_id=data.warehouse_id,
                movement_type="adjustment",
                quantity=quantity_delta,
                unit_cost=unit_cost,
                date=data.date,
                reference_id=adjustment.id,
                notes=f"Conteo fisico #{adjustment.adjustment_number}: contado {data.counted_quantity}, diferencia {quantity_delta}",
            )

        db.commit()
        db.refresh(adjustment)
        return adjustment, warnings

    def zero_out(
        self,
        db: Session,
        data: ZeroOutCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> tuple[InventoryAdjustment, list[str]]:
        """
        Llevar stock a cero — elimina todo el stock liquidado.

        Efectos:
        - material.current_stock_liquidated = 0
        - material.current_stock -= previous_stock_liquidated
        - NO recalcula costo promedio
        """
        material = self._validate_material(db, data.material_id, organization_id)
        warehouse = self._validate_warehouse(db, data.warehouse_id, organization_id)
        warnings: list[str] = []

        previous_stock = material.current_stock_liquidated
        unit_cost = material.current_average_cost

        if previous_stock == 0:
            warnings.append(f"Stock de '{material.name}' ya esta en cero, no se aplica cambio")

        quantity_delta = -previous_stock
        material.current_stock_liquidated = Decimal("0")
        material.current_stock += quantity_delta

        adjustment = self._create_adjustment(
            db=db,
            organization_id=organization_id,
            adjustment_type="zero_out",
            material_id=data.material_id,
            warehouse_id=data.warehouse_id,
            date=data.date,
            previous_stock=previous_stock,
            quantity=quantity_delta,
            new_stock=Decimal("0"),
            unit_cost=unit_cost,
            total_value=abs(quantity_delta * unit_cost),
            reason=data.reason,
            notes=data.notes,
            user_id=user_id,
        )

        if quantity_delta != 0:
            self._create_inventory_movement(
                db=db,
                organization_id=organization_id,
                material_id=data.material_id,
                warehouse_id=data.warehouse_id,
                movement_type="adjustment",
                quantity=quantity_delta,
                unit_cost=unit_cost,
                date=data.date,
                reference_id=adjustment.id,
                notes=f"Llevar a cero #{adjustment.adjustment_number}: {data.reason}",
            )

        db.commit()
        db.refresh(adjustment)
        return adjustment, warnings

    def annul(
        self,
        db: Session,
        adjustment_id: UUID,
        reason: str,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> InventoryAdjustment:
        """
        Anular ajuste — revierte cambios de stock y costo promedio.

        Crea un InventoryMovement de tipo adjustment_reversal.
        Si fue ajuste tipo increase, revierte costo promedio usando historial.
        Bloquea si hay operaciones posteriores de costo.
        """
        adjustment = self._get_or_404(db, adjustment_id, organization_id)

        if adjustment.status != "confirmed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede anular: ajuste esta en estado '{adjustment.status}'",
            )

        material = db.get(Material, adjustment.material_id)

        # Si fue increase, verificar que no hay operaciones posteriores de costo
        if adjustment.adjustment_type == "increase":
            can_revert, blocking = material_cost_history_service.check_can_revert(
                db=db,
                material_id=adjustment.material_id,
                source_type="adjustment_increase",
                source_id=adjustment.id,
            )
            if not can_revert:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No se puede anular: existen operaciones posteriores que afectaron "
                           f"el costo de '{material.name}'. Cancele primero: {', '.join(blocking)}"
                )

        # Revertir cambio de stock (restar el delta que fue aplicado)
        material.current_stock_liquidated -= adjustment.quantity
        material.current_stock -= adjustment.quantity

        # Revertir costo promedio si fue increase
        if adjustment.adjustment_type == "increase":
            material_cost_history_service.revert_cost_change(
                db=db,
                material=material,
                source_type="adjustment_increase",
                source_id=adjustment.id,
            )

        # Crear movimiento de reversal
        self._create_inventory_movement(
            db=db,
            organization_id=organization_id,
            material_id=adjustment.material_id,
            warehouse_id=adjustment.warehouse_id,
            movement_type="adjustment_reversal",
            quantity=-adjustment.quantity,
            unit_cost=adjustment.unit_cost,
            date=adjustment.date,
            reference_id=adjustment.id,
            notes=f"Anulacion de ajuste #{adjustment.adjustment_number}: {reason}",
        )

        # Marcar como anulado
        adjustment.status = "annulled"
        adjustment.annulled_reason = reason
        adjustment.annulled_at = datetime.now(timezone.utc)
        adjustment.annulled_by = user_id

        db.commit()
        db.refresh(adjustment)
        return adjustment

    def transfer_between_warehouses(
        self,
        db: Session,
        data: WarehouseTransferCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> tuple[list[InventoryMovement], list[str]]:
        """
        Traslado de material entre bodegas.

        Crea 2 InventoryMovement (transfer_out + transfer_in).
        Stock global del material NO cambia (solo se mueve entre bodegas).
        """
        material = self._validate_material(db, data.material_id, organization_id)
        source = self._validate_warehouse(db, data.source_warehouse_id, organization_id)
        destination = self._validate_warehouse(db, data.destination_warehouse_id, organization_id)
        warnings: list[str] = []

        if data.source_warehouse_id == data.destination_warehouse_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bodega de origen y destino no pueden ser iguales",
            )

        # Calcular stock en bodega origen (on-the-fly desde movimientos)
        stock_in_source = self._calculate_warehouse_stock(
            db, data.material_id, data.source_warehouse_id, organization_id
        )
        if stock_in_source < data.quantity:
            warnings.append(
                f"Stock en bodega '{source.name}' insuficiente: {stock_in_source} {material.default_unit}, "
                f"trasladando {data.quantity} {material.default_unit}"
            )

        unit_cost = material.current_average_cost
        reference_id = uuid4()  # ID comun para vincular ambos movimientos

        # Movimiento de salida
        mov_out = self._create_inventory_movement(
            db=db,
            organization_id=organization_id,
            material_id=data.material_id,
            warehouse_id=data.source_warehouse_id,
            movement_type="transfer",
            quantity=-data.quantity,
            unit_cost=unit_cost,
            date=data.date,
            reference_id=reference_id,
            notes=f"Traslado a {destination.name}: {data.reason}",
        )

        # Movimiento de entrada
        mov_in = self._create_inventory_movement(
            db=db,
            organization_id=organization_id,
            material_id=data.material_id,
            warehouse_id=data.destination_warehouse_id,
            movement_type="transfer",
            quantity=data.quantity,
            unit_cost=unit_cost,
            date=data.date,
            reference_id=reference_id,
            notes=f"Traslado desde {source.name}: {data.reason}",
        )

        db.commit()
        return [mov_out, mov_in], warnings

    # ======================================================================
    # Queries
    # ======================================================================

    def get(
        self,
        db: Session,
        adjustment_id: UUID,
        organization_id: UUID,
    ) -> InventoryAdjustment:
        """Obtener ajuste por ID con relaciones cargadas."""
        stmt = (
            select(InventoryAdjustment)
            .options(
                joinedload(InventoryAdjustment.material),
                joinedload(InventoryAdjustment.warehouse),
            )
            .where(
                InventoryAdjustment.id == adjustment_id,
                InventoryAdjustment.organization_id == organization_id,
            )
        )
        adjustment = db.scalar(stmt)
        if not adjustment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ajuste de inventario no encontrado",
            )
        return adjustment

    def get_by_number(
        self,
        db: Session,
        number: int,
        organization_id: UUID,
    ) -> InventoryAdjustment:
        """Obtener ajuste por numero secuencial."""
        stmt = (
            select(InventoryAdjustment)
            .options(
                joinedload(InventoryAdjustment.material),
                joinedload(InventoryAdjustment.warehouse),
            )
            .where(
                InventoryAdjustment.adjustment_number == number,
                InventoryAdjustment.organization_id == organization_id,
            )
        )
        adjustment = db.scalar(stmt)
        if not adjustment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ajuste #{number} no encontrado",
            )
        return adjustment

    def get_multi(
        self,
        db: Session,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        material_id: Optional[UUID] = None,
        adjustment_type: Optional[str] = None,
        status_filter: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> tuple[List[InventoryAdjustment], int]:
        """Listar ajustes con filtros y paginacion."""
        query = select(InventoryAdjustment).where(
            InventoryAdjustment.organization_id == organization_id
        )

        if material_id:
            query = query.where(InventoryAdjustment.material_id == material_id)
        if adjustment_type:
            query = query.where(InventoryAdjustment.adjustment_type == adjustment_type)
        if status_filter:
            query = query.where(InventoryAdjustment.status == status_filter)
        if date_from:
            query = query.where(InventoryAdjustment.date >= date_from)
        if date_to:
            query = query.where(InventoryAdjustment.date < date_to)

        count_query = select(func.count()).select_from(query.subquery())
        total = db.scalar(count_query)

        query = (
            query.options(
                joinedload(InventoryAdjustment.material),
                joinedload(InventoryAdjustment.warehouse),
            )
            .order_by(InventoryAdjustment.date.desc(), InventoryAdjustment.adjustment_number.desc())
            .offset(skip)
            .limit(limit)
        )

        adjustments = list(db.scalars(query).unique().all())
        return adjustments, total

    # ======================================================================
    # Helpers internos
    # ======================================================================

    def _generate_adjustment_number(self, db: Session, organization_id: UUID) -> int:
        """Generar numero secuencial con advisory lock."""
        lock_id = hash(f"{organization_id}-adjustments") % (2**31)
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})

        stmt = select(func.max(InventoryAdjustment.adjustment_number)).where(
            InventoryAdjustment.organization_id == organization_id
        )
        max_number = db.scalar(stmt)
        return (max_number or 0) + 1

    def _create_adjustment(
        self,
        db: Session,
        organization_id: UUID,
        adjustment_type: str,
        material_id: UUID,
        warehouse_id: UUID,
        date: datetime,
        previous_stock: Decimal,
        quantity: Decimal,
        new_stock: Decimal,
        unit_cost: Decimal,
        total_value: Decimal,
        reason: str,
        user_id: Optional[UUID] = None,
        notes: Optional[str] = None,
        counted_quantity: Optional[Decimal] = None,
    ) -> InventoryAdjustment:
        """Crear registro de ajuste en BD (sin commit)."""
        number = self._generate_adjustment_number(db, organization_id)

        adjustment = InventoryAdjustment(
            organization_id=organization_id,
            adjustment_number=number,
            date=date,
            adjustment_type=adjustment_type,
            material_id=material_id,
            warehouse_id=warehouse_id,
            previous_stock=previous_stock,
            quantity=quantity,
            new_stock=new_stock,
            counted_quantity=counted_quantity,
            unit_cost=unit_cost,
            total_value=total_value,
            reason=reason,
            notes=notes,
            status="confirmed",
            created_by=user_id,
        )
        db.add(adjustment)
        db.flush()
        return adjustment

    def _create_inventory_movement(
        self,
        db: Session,
        organization_id: UUID,
        material_id: UUID,
        warehouse_id: UUID,
        movement_type: str,
        quantity: Decimal,
        unit_cost: Decimal,
        date: datetime,
        reference_id: Optional[UUID] = None,
        notes: Optional[str] = None,
    ) -> InventoryMovement:
        """Crear InventoryMovement como audit trail."""
        movement = InventoryMovement(
            organization_id=organization_id,
            material_id=material_id,
            warehouse_id=warehouse_id,
            movement_type=movement_type,
            quantity=quantity,
            unit_cost=unit_cost,
            reference_type="adjustment" if "adjustment" in movement_type else "transfer",
            reference_id=reference_id,
            date=date,
            notes=notes,
        )
        db.add(movement)
        db.flush()
        return movement

    def _validate_material(
        self,
        db: Session,
        material_id: UUID,
        organization_id: UUID,
    ) -> Material:
        """Validar que el material existe y pertenece a la org."""
        material = db.get(Material, material_id)
        if not material or material.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Material no encontrado",
            )
        if not material.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Material esta inactivo",
            )
        return material

    def _validate_warehouse(
        self,
        db: Session,
        warehouse_id: UUID,
        organization_id: UUID,
    ) -> Warehouse:
        """Validar que la bodega existe y pertenece a la org."""
        warehouse = db.get(Warehouse, warehouse_id)
        if not warehouse or warehouse.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bodega no encontrada",
            )
        if not warehouse.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bodega esta inactiva",
            )
        return warehouse

    def _calculate_warehouse_stock(
        self,
        db: Session,
        material_id: UUID,
        warehouse_id: UUID,
        organization_id: UUID,
    ) -> Decimal:
        """Calcular stock de un material en una bodega desde InventoryMovement."""
        stmt = select(func.coalesce(func.sum(InventoryMovement.quantity), 0)).where(
            InventoryMovement.organization_id == organization_id,
            InventoryMovement.material_id == material_id,
            InventoryMovement.warehouse_id == warehouse_id,
        )
        return db.scalar(stmt)

    def _get_or_404(
        self,
        db: Session,
        adjustment_id: UUID,
        organization_id: UUID,
    ) -> InventoryAdjustment:
        """Obtener ajuste sin eager loading (para operaciones de escritura)."""
        adjustment = db.get(InventoryAdjustment, adjustment_id)
        if not adjustment or adjustment.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ajuste de inventario no encontrado",
            )
        return adjustment


# Instancia singleton para uso en endpoints
inventory_adjustment = CRUDInventoryAdjustment()
