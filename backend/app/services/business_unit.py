"""
Operaciones CRUD para BusinessUnit (Unidades de Negocio).

Ejemplos: Fibras, Chatarra, Metales No Ferrosos.
Se usan para analisis de rentabilidad por linea de negocio.

UN de sistema (system_code='double_entry' = "Pasa Mano"): recibe SOLO gastos
directos de doble partida. Sin materiales, excluida del prorrateo de generales
y de gastos compartidos. Ver plan-rentabilidad-un-pasamano.md.
"""
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.business_unit import BusinessUnit
from app.schemas.business_unit import BusinessUnitCreate, BusinessUnitUpdate
from app.services.base import CRUDBase, Select

DOUBLE_ENTRY_SYSTEM_CODE = "double_entry"


class CRUDBusinessUnit(CRUDBase[BusinessUnit, BusinessUnitCreate, BusinessUnitUpdate]):
    """Operaciones CRUD para BusinessUnit con busqueda por nombre."""

    def _apply_search_filter(self, query: Select, search: str) -> Select:
        """Buscar por nombre."""
        search_term = f"%{search}%"
        return query.where(self.model.name.ilike(search_term))


# Instancia singleton para uso en endpoints
business_unit = CRUDBusinessUnit(BusinessUnit)


def get_system_bu(
    db: Session, organization_id: UUID, code: str = DOUBLE_ENTRY_SYSTEM_CODE
) -> Optional[BusinessUnit]:
    """Retorna la UN de sistema de la org (o None si no existe)."""
    return db.execute(
        select(BusinessUnit).where(
            BusinessUnit.organization_id == organization_id,
            BusinessUnit.system_code == code,
        )
    ).scalar_one_or_none()


def validate_not_shared_with_system_bu(
    db: Session,
    organization_id: UUID,
    applicable_business_unit_ids: Optional[list],
    field_label: str = "gasto compartido",
) -> None:
    """Rechaza (422) si la UN de sistema esta en una asignacion COMPARTIDA.

    La UN Pasa Mano no tiene base de prorrateo (sin compras) — incluirla en un
    compartido le asignaria $0 silenciosamente. Solo acepta asignacion DIRECTA
    (business_unit_id), que es su proposito.
    """
    if not applicable_business_unit_ids:
        return
    system_bu = get_system_bu(db, organization_id)
    if not system_bu:
        return
    ids_as_str = {str(uid) for uid in applicable_business_unit_ids}
    if str(system_bu.id) in ids_as_str:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"La UN '{system_bu.name}' es de sistema (Pasa Mano) y no puede "
                f"incluirse en un {field_label}. Use asignacion directa."
            ),
        )


def validate_not_system_bu(
    db: Session,
    organization_id: UUID,
    business_unit_id: Optional[UUID],
    action_label: str,
) -> None:
    """Rechaza (400) si business_unit_id es la UN de sistema. Para acciones
    prohibidas sobre ella (asignar materiales)."""
    if not business_unit_id:
        return
    system_bu = get_system_bu(db, organization_id)
    if system_bu and str(system_bu.id) == str(business_unit_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"La UN '{system_bu.name}' es de sistema (Pasa Mano): {action_label}."
            ),
        )
