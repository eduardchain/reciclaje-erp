"""
Servicio de historial de costo de materiales.

Registra cambios al costo promedio y permite reversion precisa.
Bloquea cancelacion/anulacion si hay operaciones posteriores que
afectaron el costo del mismo material.

Solo previous_cost se usa en reversal. previous_stock/new_stock son auditoria.
"""
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.material_cost_history import MaterialCostHistory
from app.models.material import Material


class MaterialCostHistoryService:

    def record_cost_change(
        self,
        db: Session,
        material: Material,
        previous_cost: Decimal,
        previous_stock: Decimal,
        new_cost: Decimal,
        new_stock: Decimal,
        source_type: str,
        source_id: UUID,
        organization_id: UUID,
    ) -> Optional[MaterialCostHistory]:
        """
        Registra un cambio de costo en el historial.
        Siempre crea registro, incluso si el costo no cambio,
        porque check_can_revert() depende de la EXISTENCIA del registro
        para detectar operaciones posteriores y bloquear cancelaciones.
        """
        history = MaterialCostHistory(
            organization_id=organization_id,
            material_id=material.id,
            previous_cost=previous_cost,
            previous_stock=previous_stock,
            new_cost=new_cost,
            new_stock=new_stock,
            source_type=source_type,
            source_id=source_id,
        )
        db.add(history)
        return history

    def get_history_record(
        self,
        db: Session,
        material_id: UUID,
        source_type: str,
        source_id: UUID,
    ) -> Optional[MaterialCostHistory]:
        """Obtiene el registro de historial para una operacion especifica."""
        return db.query(MaterialCostHistory).filter(
            MaterialCostHistory.material_id == material_id,
            MaterialCostHistory.source_type == source_type,
            MaterialCostHistory.source_id == source_id,
        ).first()

    def check_can_revert(
        self,
        db: Session,
        material_id: UUID,
        source_type: str,
        source_id: UUID,
    ) -> tuple[bool, list[str]]:
        """
        Verifica si se puede revertir un cambio de costo.

        Returns:
            (can_revert, blocking_descriptions)
            - (True, []) si se puede revertir
            - (False, [...]) si hay operaciones posteriores bloqueantes
        """
        history = self.get_history_record(db, material_id, source_type, source_id)

        if not history:
            # No hubo cambio de costo registrado → se puede cancelar sin revertir
            return True, []

        # Buscar operaciones posteriores del mismo material
        # Ordenar por created_at + id como tiebreaker
        subsequent = db.query(MaterialCostHistory).filter(
            MaterialCostHistory.material_id == material_id,
            MaterialCostHistory.created_at > history.created_at,
        ).filter(
            # Excluir la operacion misma
            ~(
                (MaterialCostHistory.source_type == source_type)
                & (MaterialCostHistory.source_id == source_id)
            )
        ).order_by(
            MaterialCostHistory.created_at.asc(),
            MaterialCostHistory.id.asc(),
        ).all()

        if subsequent:
            blocking = []
            source_labels = {
                "purchase_liquidation": "Liquidacion compra",
                "adjustment_increase": "Ajuste aumento",
                "transformation_in": "Transformacion",
            }
            for op in subsequent:
                label = source_labels.get(op.source_type, op.source_type)
                date_str = op.created_at.strftime("%d/%m/%Y %H:%M")
                blocking.append(f"{label} (ID: {str(op.source_id)[:8]}..., Fecha: {date_str})")
            return False, blocking

        return True, []

    def revert_cost_change(
        self,
        db: Session,
        material: Material,
        source_type: str,
        source_id: UUID,
    ) -> bool:
        """
        Revierte un cambio de costo restaurando el valor anterior.
        Elimina el registro de historial.

        IMPORTANTE: Llamar check_can_revert() primero para validar.

        Returns:
            True si se revirtio, False si no habia registro.
        """
        history = self.get_history_record(db, material.id, source_type, source_id)

        if not history:
            return False

        material.current_average_cost = history.previous_cost
        db.delete(history)
        return True


# Singleton
material_cost_history_service = MaterialCostHistoryService()
