"""
Operaciones CRUD para MaterialTransformation (Transformacion de Materiales).

Permite desintegrar un material compuesto en sus componentes.
Ejemplo: Motor 500kg → Cobre 200kg + Hierro 180kg + Aluminio 100kg + Merma 20kg

Metodos publicos:
- create: Crear transformacion con distribucion de costos
- annul: Anular transformacion revirtiendo stock
- get, get_by_number, get_multi: Consultas con filtros

Cada transformacion crea InventoryMovement como audit trail.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session, joinedload

from app.models.material_transformation import MaterialTransformation, MaterialTransformationLine
from app.models.inventory_movement import InventoryMovement
from app.models.material import Material
from app.models.warehouse import Warehouse
from app.schemas.material_transformation import MaterialTransformationCreate


from app.services.material_cost_history import material_cost_history_service


class CRUDMaterialTransformation:
    """
    Operaciones para transformacion/desintegracion de materiales.

    Cada transformacion descuenta stock del material de origen
    y agrega stock a los materiales destino con costos distribuidos.
    """

    # ======================================================================
    # Metodos publicos
    # ======================================================================

    def create(
        self,
        db: Session,
        data: MaterialTransformationCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> tuple[MaterialTransformation, list[str]]:
        """
        Crear transformacion de material.

        Flujo:
        1. Validar material de origen tiene stock suficiente
        2. Validar materiales destino pertenecen a la org
        3. Validar balance: sum(destinos) + merma == origen
        4. Validar source != destinos
        5. Distribuir costos (proporcional o manual)
        6. Descontar stock del origen
        7. Agregar stock a destinos (recalculando avg cost)
        8. Crear InventoryMovements
        """
        warnings: list[str] = []

        # Validaciones
        source_material = self._validate_material(db, data.source_material_id, organization_id)
        source_warehouse = self._validate_warehouse(db, data.source_warehouse_id, organization_id)

        # V-TRANS-02: Stock suficiente (warning si negativo, no bloquea)
        if source_material.current_stock_liquidated < data.source_quantity:
            resulting_stock = source_material.current_stock_liquidated - data.source_quantity
            warnings.append(
                f"Stock insuficiente para '{source_material.name}'. "
                f"Disponible: {source_material.current_stock_liquidated}, "
                f"Requerido: {data.source_quantity}. "
                f"Stock resultara en {resulting_stock}"
            )

        # V-TRANS-05 y V-TRANS-06: Validar materiales destino
        dest_material_ids = set()
        for line in data.lines:
            dest_material = self._validate_material(db, line.destination_material_id, organization_id)
            self._validate_warehouse(db, line.destination_warehouse_id, organization_id)

            if line.destination_material_id == data.source_material_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Material destino '{dest_material.name}' no puede ser igual al material de origen",
                )
            dest_material_ids.add(line.destination_material_id)

        # Capturar costo promedio actual del origen
        source_unit_cost = source_material.current_average_cost
        source_total_value = data.source_quantity * source_unit_cost

        # Calcular valor de la merma
        waste_value = data.waste_quantity * source_unit_cost if data.waste_quantity > 0 else Decimal("0")

        # Distribuir costos a las lineas
        distributable_value = source_total_value - waste_value
        total_dest_qty = sum(line.quantity for line in data.lines)

        line_costs = []
        value_difference = None  # Solo se calcula para average_cost

        if data.cost_distribution == "average_cost":
            # Usar costo promedio del material DESTINO
            total_dest_value = Decimal("0")
            for line_data in data.lines:
                dest_material = self._validate_material(db, line_data.destination_material_id, organization_id)
                unit_cost = dest_material.current_average_cost or Decimal("0")
                line_total = line_data.quantity * unit_cost
                total_dest_value += line_total
                line_costs.append((unit_cost, line_total))

            # Diferencia vs distributable_value (NO vs source_total_value)
            # La merma ya es perdida fisica conocida, no es diferencia de valorizacion
            value_difference = total_dest_value - distributable_value

        elif data.cost_distribution == "proportional_weight":
            for line_data in data.lines:
                if total_dest_qty > 0:
                    line_total = (line_data.quantity / total_dest_qty) * distributable_value
                    line_unit = line_total / line_data.quantity
                else:
                    line_total = Decimal("0")
                    line_unit = Decimal("0")
                line_costs.append((line_unit, line_total))
        else:  # manual
            total_manual = Decimal("0")
            for line_data in data.lines:
                line_total = line_data.quantity * line_data.unit_cost
                total_manual += line_total
                line_costs.append((line_data.unit_cost, line_total))

            # Validar que costos manuales + merma == valor total origen (tolerancia 1%)
            expected = source_total_value
            actual = total_manual + waste_value
            tolerance = expected * Decimal("0.01")
            if abs(actual - expected) > tolerance:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Costos manuales no cuadran: destinos (${total_manual}) + "
                        f"merma (${waste_value}) = ${actual}, "
                        f"pero valor origen = ${expected}"
                    ),
                )

        # Generar numero secuencial
        number = self._generate_transformation_number(db, organization_id)

        # Crear transformacion
        transformation = MaterialTransformation(
            organization_id=organization_id,
            transformation_number=number,
            date=data.date,
            source_material_id=data.source_material_id,
            source_warehouse_id=data.source_warehouse_id,
            source_quantity=data.source_quantity,
            source_unit_cost=source_unit_cost,
            source_total_value=source_total_value,
            waste_quantity=data.waste_quantity,
            waste_value=waste_value,
            cost_distribution=data.cost_distribution,
            value_difference=value_difference,
            reason=data.reason,
            notes=data.notes,
            status="confirmed",
            created_by=user_id,
        )
        db.add(transformation)
        db.flush()

        # Crear lineas de destino
        for i, line_data in enumerate(data.lines):
            unit_cost, total_cost = line_costs[i]
            line = MaterialTransformationLine(
                transformation_id=transformation.id,
                destination_material_id=line_data.destination_material_id,
                destination_warehouse_id=line_data.destination_warehouse_id,
                quantity=line_data.quantity,
                unit_cost=unit_cost,
                total_cost=total_cost,
            )
            db.add(line)

        db.flush()

        # Aplicar efectos en stock

        # 1. Descontar stock del material de origen
        source_material.current_stock_liquidated -= data.source_quantity
        source_material.current_stock -= data.source_quantity

        # Crear InventoryMovement de salida
        self._create_inventory_movement(
            db=db,
            organization_id=organization_id,
            material_id=data.source_material_id,
            warehouse_id=data.source_warehouse_id,
            movement_type="transformation",
            quantity=-data.source_quantity,
            unit_cost=source_unit_cost,
            date=data.date,
            reference_id=transformation.id,
            notes=f"Transformacion #{number}: salida de {source_material.name}",
        )

        # 2. Agregar stock a cada material destino
        for i, line_data in enumerate(data.lines):
            dest_material = db.get(Material, line_data.destination_material_id)
            unit_cost, total_cost = line_costs[i]

            # Recalcular costo promedio del destino (solo stock liquidado, transito no afecta)
            old_liquidated = dest_material.current_stock_liquidated
            old_cost = dest_material.current_average_cost
            if old_liquidated <= 0:
                dest_material.current_average_cost = unit_cost
            else:
                total_old_value = old_liquidated * old_cost
                dest_material.current_average_cost = (total_old_value + total_cost) / (old_liquidated + line_data.quantity)

            dest_material.current_stock_liquidated += line_data.quantity
            dest_material.current_stock += line_data.quantity

            # Registrar cambio de costo en historial
            material_cost_history_service.record_cost_change(
                db=db,
                material=dest_material,
                previous_cost=old_cost,
                previous_stock=old_liquidated,
                new_cost=dest_material.current_average_cost,
                new_stock=dest_material.current_stock_liquidated,
                source_type="transformation_in",
                source_id=transformation.id,
                organization_id=organization_id,
            )

            # Crear InventoryMovement de entrada
            self._create_inventory_movement(
                db=db,
                organization_id=organization_id,
                material_id=line_data.destination_material_id,
                warehouse_id=line_data.destination_warehouse_id,
                movement_type="transformation",
                quantity=line_data.quantity,
                unit_cost=unit_cost,
                date=data.date,
                reference_id=transformation.id,
                notes=f"Transformacion #{number}: entrada de {dest_material.name}",
            )

        db.commit()
        db.refresh(transformation)
        return transformation, warnings

    def annul(
        self,
        db: Session,
        transformation_id: UUID,
        reason: str,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> MaterialTransformation:
        """
        Anular transformacion — revierte stock de origen y destinos.

        Revierte costo promedio de materiales destino usando historial.
        Bloquea si hay operaciones posteriores de costo.
        """
        transformation = self._get_or_404(db, transformation_id, organization_id)

        if transformation.status != "confirmed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede anular: transformacion esta en estado '{transformation.status}'",
            )

        # Cargar lineas
        stmt = (
            select(MaterialTransformation)
            .options(joinedload(MaterialTransformation.lines))
            .where(MaterialTransformation.id == transformation_id)
        )
        transformation = db.scalar(stmt)

        # Verificar que no hay operaciones posteriores de costo por cada material destino
        for line in transformation.lines:
            can_revert, blocking = material_cost_history_service.check_can_revert(
                db=db,
                material_id=line.destination_material_id,
                source_type="transformation_in",
                source_id=transformation.id,
            )
            if not can_revert:
                dest_material = db.get(Material, line.destination_material_id)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No se puede anular: existen operaciones posteriores que afectaron "
                           f"el costo de '{dest_material.name}'. Cancele primero: {', '.join(blocking)}"
                )

        # Revertir: restaurar stock del material de origen
        source_material = db.get(Material, transformation.source_material_id)
        source_material.current_stock_liquidated += transformation.source_quantity
        source_material.current_stock += transformation.source_quantity

        self._create_inventory_movement(
            db=db,
            organization_id=organization_id,
            material_id=transformation.source_material_id,
            warehouse_id=transformation.source_warehouse_id,
            movement_type="transformation",
            quantity=transformation.source_quantity,
            unit_cost=transformation.source_unit_cost,
            date=transformation.date,
            reference_id=transformation.id,
            notes=f"Anulacion transformacion #{transformation.transformation_number}: restaurar {source_material.name}",
        )

        # Revertir: descontar stock y costo de cada material destino
        for line in transformation.lines:
            dest_material = db.get(Material, line.destination_material_id)
            dest_material.current_stock_liquidated -= line.quantity
            dest_material.current_stock -= line.quantity

            # Revertir costo promedio usando historial
            material_cost_history_service.revert_cost_change(
                db=db,
                material=dest_material,
                source_type="transformation_in",
                source_id=transformation.id,
            )

            self._create_inventory_movement(
                db=db,
                organization_id=organization_id,
                material_id=line.destination_material_id,
                warehouse_id=line.destination_warehouse_id,
                movement_type="transformation",
                quantity=-line.quantity,
                unit_cost=line.unit_cost,
                date=transformation.date,
                reference_id=transformation.id,
                notes=f"Anulacion transformacion #{transformation.transformation_number}: revertir {dest_material.name}",
            )

        # Marcar como anulada
        transformation.status = "annulled"
        transformation.annulled_reason = reason
        transformation.annulled_at = datetime.now(timezone.utc)
        transformation.annulled_by = user_id

        db.commit()
        db.refresh(transformation)
        return transformation

    # ======================================================================
    # Queries
    # ======================================================================

    def get(
        self,
        db: Session,
        transformation_id: UUID,
        organization_id: UUID,
    ) -> MaterialTransformation:
        """Obtener transformacion por ID con relaciones cargadas."""
        stmt = (
            select(MaterialTransformation)
            .options(
                joinedload(MaterialTransformation.source_material),
                joinedload(MaterialTransformation.source_warehouse),
                joinedload(MaterialTransformation.lines)
                .joinedload(MaterialTransformationLine.destination_material),
                joinedload(MaterialTransformation.lines)
                .joinedload(MaterialTransformationLine.destination_warehouse),
            )
            .where(
                MaterialTransformation.id == transformation_id,
                MaterialTransformation.organization_id == organization_id,
            )
        )
        transformation = db.scalar(stmt)
        if not transformation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transformacion no encontrada",
            )
        return transformation

    def get_by_number(
        self,
        db: Session,
        number: int,
        organization_id: UUID,
    ) -> MaterialTransformation:
        """Obtener transformacion por numero secuencial."""
        stmt = (
            select(MaterialTransformation)
            .options(
                joinedload(MaterialTransformation.source_material),
                joinedload(MaterialTransformation.source_warehouse),
                joinedload(MaterialTransformation.lines)
                .joinedload(MaterialTransformationLine.destination_material),
                joinedload(MaterialTransformation.lines)
                .joinedload(MaterialTransformationLine.destination_warehouse),
            )
            .where(
                MaterialTransformation.transformation_number == number,
                MaterialTransformation.organization_id == organization_id,
            )
        )
        transformation = db.scalar(stmt)
        if not transformation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transformacion #{number} no encontrada",
            )
        return transformation

    def get_multi(
        self,
        db: Session,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        source_material_id: Optional[UUID] = None,
        status_filter: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> tuple[List[MaterialTransformation], int]:
        """Listar transformaciones con filtros y paginacion."""
        query = select(MaterialTransformation).where(
            MaterialTransformation.organization_id == organization_id
        )

        if source_material_id:
            query = query.where(MaterialTransformation.source_material_id == source_material_id)
        if status_filter:
            query = query.where(MaterialTransformation.status == status_filter)
        if date_from:
            query = query.where(MaterialTransformation.date >= date_from)
        if date_to:
            query = query.where(MaterialTransformation.date < date_to)

        count_query = select(func.count()).select_from(query.subquery())
        total = db.scalar(count_query)

        query = (
            query.options(
                joinedload(MaterialTransformation.source_material),
                joinedload(MaterialTransformation.source_warehouse),
                joinedload(MaterialTransformation.lines)
                .joinedload(MaterialTransformationLine.destination_material),
                joinedload(MaterialTransformation.lines)
                .joinedload(MaterialTransformationLine.destination_warehouse),
            )
            .order_by(MaterialTransformation.date.desc(), MaterialTransformation.transformation_number.desc())
            .offset(skip)
            .limit(limit)
        )

        transformations = list(db.scalars(query).unique().all())
        return transformations, total

    # ======================================================================
    # Helpers internos
    # ======================================================================

    def _generate_transformation_number(self, db: Session, organization_id: UUID) -> int:
        """Generar numero secuencial con advisory lock."""
        lock_id = hash(f"{organization_id}-transformations") % (2**31)
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})

        stmt = select(func.max(MaterialTransformation.transformation_number)).where(
            MaterialTransformation.organization_id == organization_id
        )
        max_number = db.scalar(stmt)
        return (max_number or 0) + 1

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
            reference_type="transformation",
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
                detail=f"Material '{material.name}' esta inactivo",
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
                detail=f"Bodega '{warehouse.name}' esta inactiva",
            )
        return warehouse

    def _get_or_404(
        self,
        db: Session,
        transformation_id: UUID,
        organization_id: UUID,
    ) -> MaterialTransformation:
        """Obtener transformacion sin eager loading (para operaciones de escritura)."""
        transformation = db.get(MaterialTransformation, transformation_id)
        if not transformation or transformation.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transformacion no encontrada",
            )
        return transformation


# Instancia singleton para uso en endpoints
material_transformation = CRUDMaterialTransformation()
