"""
Operaciones CRUD para Warehouse (Bodegas).

Las bodegas representan ubicaciones fisicas donde se almacena material.
"""
from sqlalchemy import or_

from app.models.warehouse import Warehouse
from app.schemas.warehouse import WarehouseCreate, WarehouseUpdate
from app.services.base import CRUDBase, Select


class CRUDWarehouse(CRUDBase[Warehouse, WarehouseCreate, WarehouseUpdate]):
    """Operaciones CRUD para Warehouse con busqueda por nombre/direccion."""

    def _apply_search_filter(self, query: Select, search: str) -> Select:
        """Buscar por nombre o direccion."""
        search_term = f"%{search}%"
        return query.where(
            or_(
                self.model.name.ilike(search_term),
                self.model.address.ilike(search_term),
            )
        )


# Instancia singleton para uso en endpoints
warehouse = CRUDWarehouse(Warehouse)
