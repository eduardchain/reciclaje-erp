"""
Operaciones CRUD para BusinessUnit (Unidades de Negocio).

Ejemplos: Fibras, Chatarra, Metales No Ferrosos.
Se usan para analisis de rentabilidad por linea de negocio.
"""
from app.models.business_unit import BusinessUnit
from app.schemas.business_unit import BusinessUnitCreate, BusinessUnitUpdate
from app.services.base import CRUDBase, Select


class CRUDBusinessUnit(CRUDBase[BusinessUnit, BusinessUnitCreate, BusinessUnitUpdate]):
    """Operaciones CRUD para BusinessUnit con busqueda por nombre."""

    def _apply_search_filter(self, query: Select, search: str) -> Select:
        """Buscar por nombre."""
        search_term = f"%{search}%"
        return query.where(self.model.name.ilike(search_term))


# Instancia singleton para uso en endpoints
business_unit = CRUDBusinessUnit(BusinessUnit)
