"""
Operaciones CRUD para ThirdPartyCategory.

Incluye validacion de jerarquia (max 2 niveles), herencia de behavior_type,
validacion de behavior_type obligatorio para nivel 1, y endpoint flat.
"""
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, exists
from sqlalchemy.orm import Session, aliased

from app.models.third_party_category import (
    ThirdPartyCategory,
    ThirdPartyCategoryAssignment,
    BehaviorType,
)
from app.schemas.third_party_category import (
    ThirdPartyCategoryCreate,
    ThirdPartyCategoryUpdate,
    ThirdPartyCategoryFlat,
    ThirdPartyCategoryFlatResponse,
)
from app.services.base import CRUDBase, Select, PaginatedResponse


class CRUDThirdPartyCategory(
    CRUDBase[ThirdPartyCategory, ThirdPartyCategoryCreate, ThirdPartyCategoryUpdate]
):
    """CRUD para ThirdPartyCategory con subcategorias (max 2 niveles)."""

    def _apply_search_filter(self, query: Select, search: str) -> Select:
        """Buscar por nombre de la categoria."""
        search_term = f"%{search}%"
        return query.where(self.model.name.ilike(search_term))

    def _validate_parent(
        self,
        db: Session,
        parent_id: UUID,
        organization_id: UUID,
    ) -> ThirdPartyCategory:
        """Validar que parent existe, misma org, activo, y no tiene parent (max 2 niveles)."""
        parent = db.execute(
            select(ThirdPartyCategory).where(
                ThirdPartyCategory.id == parent_id,
                ThirdPartyCategory.organization_id == organization_id,
                ThirdPartyCategory.is_active == True,
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
        obj_in: ThirdPartyCategoryCreate,
        organization_id: UUID,
        **kwargs,
    ) -> ThirdPartyCategory:
        """Crear categoria con validacion de jerarquia y behavior_type."""
        obj_data = obj_in.model_dump()

        if obj_data.get("parent_id"):
            parent = self._validate_parent(db, obj_data["parent_id"], organization_id)
            # Subcategoria hereda behavior_type del padre
            obj_data["behavior_type"] = parent.behavior_type
        else:
            # Nivel 1: behavior_type es obligatorio
            if not obj_data.get("behavior_type"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="behavior_type es obligatorio para categorias de nivel 1",
                )

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
        obj_in: ThirdPartyCategoryUpdate,
        organization_id: UUID,
        **kwargs,
    ) -> ThirdPartyCategory:
        """Actualizar categoria con validacion de jerarquia."""
        db_obj = self.get_or_404(db=db, id=id, organization_id=organization_id)
        update_data = obj_in.model_dump(exclude_unset=True)

        if "parent_id" in update_data:
            new_parent_id = update_data["parent_id"]
            if new_parent_id is not None:
                if new_parent_id == id:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Una categoria no puede ser su propia subcategoria",
                    )
                parent = self._validate_parent(db, new_parent_id, organization_id)
                update_data["behavior_type"] = parent.behavior_type

            if new_parent_id is not None:
                has_children = db.execute(
                    select(ThirdPartyCategory.id).where(
                        ThirdPartyCategory.parent_id == id,
                        ThirdPartyCategory.is_active == True,
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

    def delete(
        self,
        db: Session,
        id: UUID,
        organization_id: UUID,
        **kwargs,
    ) -> ThirdPartyCategory:
        """Soft delete con validacion de hijos y asignaciones."""
        db_obj = self.get_or_404(db=db, id=id, organization_id=organization_id)

        # No eliminar si tiene subcategorias activas
        has_children = db.execute(
            select(ThirdPartyCategory.id).where(
                ThirdPartyCategory.parent_id == id,
                ThirdPartyCategory.is_active == True,
            ).limit(1)
        ).scalar_one_or_none()
        if has_children:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No se puede eliminar una categoria con subcategorias activas",
            )

        # No eliminar si tiene terceros asignados
        has_assignments = db.execute(
            select(ThirdPartyCategoryAssignment.id).where(
                ThirdPartyCategoryAssignment.category_id == id,
            ).limit(1)
        ).scalar_one_or_none()
        if has_assignments:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No se puede eliminar una categoria con terceros asignados",
            )

        db_obj.is_active = False
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

        ParentCat = aliased(ThirdPartyCategory)

        base = (
            select(ThirdPartyCategory, ParentCat.name.label("parent_name"))
            .outerjoin(ParentCat, ThirdPartyCategory.parent_id == ParentCat.id)
            .where(ThirdPartyCategory.organization_id == organization_id)
        )

        if is_active is not None:
            base = base.where(ThirdPartyCategory.is_active == is_active)
        if search:
            search_term = f"%{search}%"
            base = base.where(ThirdPartyCategory.name.ilike(search_term))

        count_query = select(func.count()).select_from(base.subquery())
        total = db.execute(count_query).scalar_one()

        sort_col = getattr(ThirdPartyCategory, sort_by, ThirdPartyCategory.name)
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
        behavior_type: Optional[str] = None,
    ) -> ThirdPartyCategoryFlatResponse:
        """Lista plana con display_name, ordenada alfabeticamente."""
        ParentCat = aliased(ThirdPartyCategory)

        query = (
            select(
                ThirdPartyCategory.id,
                ThirdPartyCategory.name,
                ThirdPartyCategory.parent_id,
                ThirdPartyCategory.behavior_type,
                ParentCat.name.label("parent_name"),
            )
            .outerjoin(ParentCat, ThirdPartyCategory.parent_id == ParentCat.id)
            .where(
                ThirdPartyCategory.organization_id == organization_id,
                ThirdPartyCategory.is_active == True,
            )
        )

        if behavior_type:
            query = query.where(ThirdPartyCategory.behavior_type == behavior_type)

        rows = db.execute(query).all()

        items = []
        for row in rows:
            if row.parent_name:
                display_name = f"{row.parent_name} > {row.name}"
            else:
                display_name = row.name

            items.append(ThirdPartyCategoryFlat(
                id=row.id,
                name=row.name,
                display_name=display_name,
                parent_id=row.parent_id,
                behavior_type=row.behavior_type,
            ))

        items.sort(key=lambda x: x.display_name.lower())

        return ThirdPartyCategoryFlatResponse(items=items)


# Singleton
third_party_category = CRUDThirdPartyCategory(ThirdPartyCategory)
