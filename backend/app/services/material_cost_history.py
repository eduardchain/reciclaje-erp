"""
Servicio de historial de costo de materiales.

Registro APPEND-ONLY de cambios al costo promedio (Fase 5): las reversiones
(cancelar compra liquidada, anular ajuste/transformacion) ya NO rebobinan el
costo borrando el registro original — hacen remocion/reingreso PONDERADO
(services/inventory_costing.py) y escriben su propio registro con source_type
de reversion (purchase_cancellation | adjustment_annulment |
transformation_annulment | sale_cancellation). Consecuencia: el ultimo
registro de un material SIEMPRE refleja su costo vigente (invariante I4, sin
excepciones), y el historial es una linea de tiempo completa para auditoria
y para la valuacion historica as-of (#41, con el filtro de ops canceladas de
Fase 5 — ver reports._get_inventory_as_of).

previous_stock/new_stock son auditoria.
"""
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

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
        transaction_date: Optional[date] = None,
    ) -> Optional[MaterialCostHistory]:
        """
        Registra un cambio de costo en el historial (append-only).

        Los caminos operativos (liquidacion de compra, ajuste increase,
        transformacion) registran SIEMPRE, incluso si el costo no cambio —
        el registro documenta la operacion en la linea de tiempo del costo y
        la valuacion as-of (#41) lee new_cost del ultimo registro al corte.
        Las reversiones (Fase 5) y el reingreso de cancelacion de venta (#65)
        registran solo si el promedio cambio.
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
            transaction_date=transaction_date,
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

    # NOTA Fase 5: check_can_revert() y revert_cost_change() fueron RETIRADOS.
    # El guard bloqueaba por MCH posterior pero era ciego a extracciones
    # MCH-silenciosas (ventas liquidadas, decreases) → daba falsos permisos y
    # el rewind fugaba valor. Las reversiones ahora usan remocion/reingreso
    # ponderado (services/inventory_costing.py) que conserva valor por
    # construccion y nunca bloquea. Plan:
    # docs/planes/plan-fase5-remocion-ponderada.md


# Singleton
material_cost_history_service = MaterialCostHistoryService()
