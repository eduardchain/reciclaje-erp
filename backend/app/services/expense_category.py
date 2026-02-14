"""
Operaciones CRUD para ExpenseCategory (Categorias de Gastos).

Incluye busqueda por nombre y filtrado por tipo (directo/indirecto).
"""
from app.models.expense_category import ExpenseCategory
from app.schemas.expense_category import ExpenseCategoryCreate, ExpenseCategoryUpdate
from app.services.base import CRUDBase, Select


class CRUDExpenseCategory(CRUDBase[ExpenseCategory, ExpenseCategoryCreate, ExpenseCategoryUpdate]):
    """Operaciones CRUD para ExpenseCategory con busqueda por nombre."""

    def _apply_search_filter(self, query: Select, search: str) -> Select:
        """Buscar por nombre de la categoria."""
        search_term = f"%{search}%"
        return query.where(self.model.name.ilike(search_term))


# Instancia singleton para uso en endpoints
expense_category = CRUDExpenseCategory(ExpenseCategory)
