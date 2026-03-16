"""
Operaciones CRUD para ExpenseCategory (Categorias de Gastos).

Incluye busqueda por nombre, validacion de jerarquia (max 2 niveles),
y endpoint flat con display_name para selectors.
"""
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.models.expense_category import ExpenseCategory
from app.schemas.expense_category import (
    ExpenseCategoryCreate,
    ExpenseCategoryUpdate,
    ExpenseCategoryFlat,
    ExpenseCategoryFlatResponse,
)
from app.services.base import CRUDBase, Select, PaginatedResponse


class CRUDExpenseCategory(CRUDBase[ExpenseCategory, ExpenseCategoryCreate, ExpenseCategoryUpdate]):
    """Operaciones CRUD para ExpenseCategory con subcategorias (max 2 niveles)."""

    def _apply_search_filter(self, query: Select, search: str) -> Select:
        """Buscar por nombre de la categoria."""
        search_term = f"%{search}%"
        return query.where(self.model.name.ilike(search_term))

    def _validate_parent(
        self,
        db: Session,
        parent_id: UUID,
        organization_id: UUID,
        exclude_id: Optional[UUID] = None,
    ) -> ExpenseCategory:
        """Validar que parent_id existe, misma org, activo, y no tiene parent (max 2 niveles)."""
        parent = db.execute(
            select(ExpenseCategory).where(
                ExpenseCategory.id == parent_id,
                ExpenseCategory.organization_id == organization_id,
                ExpenseCategory.is_active == True,
            )
        ).scalar_one_or_none()

        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoria padre no encontrada en esta organizacion",
            )

        if parent.parent_id is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Solo se permiten 2 niveles de jerarquia (categoria > subcategoria)",
            )

        return parent

    def create(
        self,
        db: Session,
        obj_in: ExpenseCategoryCreate,
        organization_id: UUID,
        **kwargs,
    ) -> ExpenseCategory:
        """Crear categoria con validacion de jerarquia."""
        obj_data = obj_in.model_dump()

        if obj_data.get("parent_id"):
            parent = self._validate_parent(db, obj_data["parent_id"], organization_id)
            # Subcategoria hereda is_direct_expense del padre
            obj_data["is_direct_expense"] = parent.is_direct_expense

        obj_data["organization_id"] = organization_id
        db_obj = self.model(**obj_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        id: UUID,
        obj_in: ExpenseCategoryUpdate,
        organization_id: UUID,
        **kwargs,
    ) -> ExpenseCategory:
        """Actualizar categoria con validacion de jerarquia."""
        db_obj = self.get_or_404(db=db, id=id, organization_id=organization_id)
        update_data = obj_in.model_dump(exclude_unset=True)

        if "parent_id" in update_data:
            new_parent_id = update_data["parent_id"]
            if new_parent_id is not None:
                # No puede asignarse como parent a si misma
                if new_parent_id == id:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Una categoria no puede ser su propia subcategoria",
                    )
                parent = self._validate_parent(db, new_parent_id, organization_id, exclude_id=id)
                # Heredar is_direct_expense del padre
                update_data["is_direct_expense"] = parent.is_direct_expense

            # Si tiene hijos, no puede convertirse en subcategoria
            if new_parent_id is not None:
                has_children = db.execute(
                    select(ExpenseCategory.id).where(
                        ExpenseCategory.parent_id == id,
                        ExpenseCategory.is_active == True,
                    ).limit(1)
                ).scalar_one_or_none()
                if has_children:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="No se puede asignar padre a una categoria que ya tiene subcategorias",
                    )

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_multi_with_parent(
        self,
        db: Session,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: str = "name",
        sort_order: str = "asc",
    ) -> PaginatedResponse:
        """Listar categorias con parent_name incluido."""
        from sqlalchemy import func

        ParentCat = aliased(ExpenseCategory)

        base = (
            select(ExpenseCategory, ParentCat.name.label("parent_name"))
            .outerjoin(ParentCat, ExpenseCategory.parent_id == ParentCat.id)
            .where(ExpenseCategory.organization_id == organization_id)
        )

        if is_active is not None:
            base = base.where(ExpenseCategory.is_active == is_active)
        if search:
            search_term = f"%{search}%"
            base = base.where(ExpenseCategory.name.ilike(search_term))

        # Total
        count_query = select(func.count()).select_from(base.subquery())
        total = db.execute(count_query).scalar_one()

        # Ordenar
        sort_col = getattr(ExpenseCategory, sort_by, ExpenseCategory.name)
        order = sort_col.desc() if sort_order == "desc" else sort_col.asc()
        base = base.order_by(order).offset(skip).limit(limit)

        rows = db.execute(base).all()

        items = []
        for row in rows:
            cat = row[0]
            item = {c.name: getattr(cat, c.name) for c in cat.__table__.columns}
            item["parent_name"] = row.parent_name
            items.append(item)

        return PaginatedResponse(items=items, total=total, skip=skip, limit=limit)

    def get_flat(
        self,
        db: Session,
        organization_id: UUID,
    ) -> ExpenseCategoryFlatResponse:
        """Lista plana con display_name, ordenada alfabeticamente."""
        ParentCat = aliased(ExpenseCategory)

        query = (
            select(
                ExpenseCategory.id,
                ExpenseCategory.name,
                ExpenseCategory.parent_id,
                ExpenseCategory.is_direct_expense,
                ParentCat.name.label("parent_name"),
            )
            .outerjoin(ParentCat, ExpenseCategory.parent_id == ParentCat.id)
            .where(
                ExpenseCategory.organization_id == organization_id,
                ExpenseCategory.is_active == True,
            )
        )

        rows = db.execute(query).all()

        items = []
        for row in rows:
            if row.parent_name:
                display_name = f"{row.parent_name} > {row.name}"
            else:
                display_name = row.name

            items.append(ExpenseCategoryFlat(
                id=row.id,
                name=row.name,
                display_name=display_name,
                parent_id=row.parent_id,
                is_direct_expense=row.is_direct_expense,
            ))

        # Orden alfabetico por display_name
        items.sort(key=lambda x: x.display_name.lower())

        return ExpenseCategoryFlatResponse(items=items)


# Instancia singleton para uso en endpoints
expense_category = CRUDExpenseCategory(ExpenseCategory)
