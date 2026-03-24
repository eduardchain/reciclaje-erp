"""
CRUD operations for ThirdParty model.
"""
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, or_, exists
from sqlalchemy.orm import Session, joinedload

from app.models.third_party import ThirdParty
from app.models.third_party_category import (
    ThirdPartyCategory,
    ThirdPartyCategoryAssignment,
)
from app.schemas.third_party import ThirdPartyCreate, ThirdPartyUpdate, ThirdPartyResponse
from app.services.base import CRUDBase, Select, PaginatedResponse


class CRUDThirdParty(CRUDBase[ThirdParty, ThirdPartyCreate, ThirdPartyUpdate]):
    """CRUD operations for ThirdParty with custom methods."""

    def _apply_search_filter(self, query: Select, search: str) -> Select:
        """Apply search filter to name, identification_number, and email."""
        search_term = f"%{search}%"
        return query.where(
            or_(
                self.model.name.ilike(search_term),
                self.model.identification_number.ilike(search_term),
                self.model.email.ilike(search_term)
            )
        )

    # Mapeo de roles a behavior_types para filtrar
    ROLE_BEHAVIOR_MAP = {
        "supplier": ["material_supplier"],
        "service_provider": ["service_provider"],
        "customer": ["customer"],
        "investor": ["investor"],
        "provision": ["provision"],
        "liability": ["liability"],
        "generic": ["generic"],
    }

    @staticmethod
    def _sync_category_assignments(
        db: Session,
        third_party_id: UUID,
        category_ids: list[UUID],
        organization_id: UUID,
    ) -> None:
        """Sincronizar asignaciones de categorias para un tercero (replace all)."""
        if category_ids:
            # Validar que todas las categorias existen y pertenecen a la org
            cats = db.execute(
                select(ThirdPartyCategory).where(
                    ThirdPartyCategory.id.in_(category_ids),
                    ThirdPartyCategory.organization_id == organization_id,
                    ThirdPartyCategory.is_active == True,
                )
            ).scalars().all()

            found_ids = {c.id for c in cats}
            missing = set(category_ids) - found_ids
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Categorias no encontradas: {[str(m) for m in missing]}",
                )

        # Eliminar asignaciones actuales
        db.execute(
            select(ThirdPartyCategoryAssignment).where(
                ThirdPartyCategoryAssignment.third_party_id == third_party_id,
            )
        )
        db.query(ThirdPartyCategoryAssignment).filter(
            ThirdPartyCategoryAssignment.third_party_id == third_party_id,
        ).delete(synchronize_session="fetch")

        # Crear nuevas asignaciones
        for cat_id in category_ids:
            db.add(ThirdPartyCategoryAssignment(
                third_party_id=third_party_id,
                category_id=cat_id,
            ))

        db.flush()

    @staticmethod
    def has_behavior_type(
        db: Session,
        third_party_id: UUID,
        behavior_types: list[str],
    ) -> bool:
        """Verificar si un tercero tiene asignada alguna categoria con los behavior_types dados."""
        return db.execute(
            select(
                exists(
                    select(ThirdPartyCategoryAssignment.id)
                    .join(ThirdPartyCategory, ThirdPartyCategoryAssignment.category_id == ThirdPartyCategory.id)
                    .where(
                        ThirdPartyCategoryAssignment.third_party_id == third_party_id,
                        ThirdPartyCategory.behavior_type.in_(behavior_types),
                    )
                )
            )
        ).scalar()

    def _behavior_type_filter(self, behavior_types: list[str]) -> exists:
        """Retorna EXISTS clause para filtrar terceros por behavior_type."""
        return exists(
            select(ThirdPartyCategoryAssignment.id)
            .join(ThirdPartyCategory, ThirdPartyCategoryAssignment.category_id == ThirdPartyCategory.id)
            .where(
                ThirdPartyCategoryAssignment.third_party_id == self.model.id,
                ThirdPartyCategory.behavior_type.in_(behavior_types),
            )
        )

    def _get_filtered_list(
        self,
        db: Session,
        organization_id: UUID,
        extra_filter=None,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: str = "name",
        sort_order: str = "asc",
    ) -> PaginatedResponse:
        """Helper generico para listar terceros con filtros."""
        from sqlalchemy import func

        query = self._base_query(organization_id).where(
            self.model.is_system_entity == False
        )

        if extra_filter is not None:
            query = query.where(extra_filter)

        if is_active is not None:
            query = query.where(self.model.is_active == is_active)

        if search:
            query = self._apply_search_filter(query, search)

        count_query = select(func.count()).select_from(query.subquery())
        total = db.execute(count_query).scalar_one()

        sort_column = getattr(self.model, sort_by, self.model.name)
        if sort_order.lower() == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Eager load category_assignments + category + parent para serializar
        query = query.options(
            joinedload(self.model.category_assignments)
            .joinedload(ThirdPartyCategoryAssignment.category)
            .joinedload(ThirdPartyCategory.parent)
        )

        query = query.offset(skip).limit(limit)
        result = db.execute(query)
        items = result.unique().scalars().all()

        # Serializar a ThirdPartyResponse para incluir categories
        items_serialized = [
            ThirdPartyResponse.model_validate(item).model_dump()
            for item in items
        ]

        return PaginatedResponse(
            items=items_serialized,
            total=total,
            skip=skip,
            limit=limit
        )

    def get_multi(
        self,
        db: Session,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        role: Optional[str] = None,
        sort_by: str = "name",
        sort_order: str = "asc"
    ) -> PaginatedResponse:
        """Get third parties con filtro opcional por rol (behavior_type)."""
        extra_filter = None
        if role and role in self.ROLE_BEHAVIOR_MAP:
            extra_filter = self._behavior_type_filter(self.ROLE_BEHAVIOR_MAP[role])

        return self._get_filtered_list(
            db=db,
            organization_id=organization_id,
            extra_filter=extra_filter,
            skip=skip, limit=limit,
            is_active=is_active, search=search,
            sort_by=sort_by, sort_order=sort_order,
        )

    def create(
        self,
        db: Session,
        obj_in: ThirdPartyCreate,
        organization_id: UUID
    ) -> ThirdParty:
        """Crear tercero con asignacion opcional de categorias."""
        category_ids = obj_in.category_ids
        obj_data = obj_in.model_dump(exclude={"initial_balance", "category_ids"})
        obj_data["organization_id"] = organization_id
        obj_data["initial_balance"] = obj_in.initial_balance
        obj_data["current_balance"] = obj_in.initial_balance

        db_obj = self.model(**obj_data)
        db.add(db_obj)
        db.flush()

        if category_ids:
            self._sync_category_assignments(db, db_obj.id, category_ids, organization_id)

        db.commit()
        return self._get_with_categories(db, db_obj.id, organization_id)

    def _get_with_categories(self, db: Session, id: UUID, organization_id: UUID) -> ThirdParty:
        """Cargar tercero con category_assignments eager-loaded."""
        result = db.execute(
            select(ThirdParty)
            .where(ThirdParty.id == id, ThirdParty.organization_id == organization_id)
            .options(
                joinedload(ThirdParty.category_assignments)
                .joinedload(ThirdPartyCategoryAssignment.category)
                .joinedload(ThirdPartyCategory.parent)
            )
        )
        return result.unique().scalars().one()

    def update(
        self,
        db: Session,
        id: UUID,
        obj_in: ThirdPartyUpdate,
        organization_id: UUID,
        **kwargs,
    ) -> ThirdParty:
        """Actualizar tercero con sync opcional de categorias."""
        db_obj = self.get_or_404(db, id, organization_id, detail="Tercero no encontrado")
        update_data = obj_in.model_dump(exclude_unset=True)

        category_ids = update_data.pop("category_ids", None)

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        if category_ids is not None:
            self._sync_category_assignments(db, id, category_ids, organization_id)

        db.commit()
        return self._get_with_categories(db, id, organization_id)

    def delete(
        self,
        db: Session,
        id: UUID,
        organization_id: UUID
    ) -> ThirdParty:
        """Soft delete third party."""
        db_obj = self.get_or_404(db, id, organization_id, detail="Tercero no encontrado")

        if db_obj.current_balance != 0:
            balance_type = "deuda" if db_obj.current_balance < 0 else "credito"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede eliminar el tercero con saldo pendiente de {balance_type} ({db_obj.current_balance}). Liquide el saldo primero."
            )

        db_obj.is_active = False
        db.commit()
        db.refresh(db_obj)

        return db_obj

    def get_suppliers(
        self,
        db: Session,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: str = "name",
        sort_order: str = "asc"
    ) -> PaginatedResponse:
        """Get material suppliers (behavior_type='material_supplier')."""
        return self._get_filtered_list(
            db=db,
            organization_id=organization_id,
            extra_filter=self._behavior_type_filter(["material_supplier"]),
            skip=skip, limit=limit,
            is_active=is_active, search=search,
            sort_by=sort_by, sort_order=sort_order,
        )

    def get_payable_suppliers(
        self,
        db: Session,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: str = "name",
        sort_order: str = "asc"
    ) -> PaginatedResponse:
        """Get suppliers that can receive payments: material_supplier + service_provider."""
        return self._get_filtered_list(
            db=db,
            organization_id=organization_id,
            extra_filter=self._behavior_type_filter(["material_supplier", "service_provider"]),
            skip=skip, limit=limit,
            is_active=is_active, search=search,
            sort_by=sort_by, sort_order=sort_order,
        )

    def get_customers(
        self,
        db: Session,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: str = "name",
        sort_order: str = "asc"
    ) -> PaginatedResponse:
        """Get customers (behavior_type='customer')."""
        return self._get_filtered_list(
            db=db,
            organization_id=organization_id,
            extra_filter=self._behavior_type_filter(["customer"]),
            skip=skip, limit=limit,
            is_active=is_active, search=search,
            sort_by=sort_by, sort_order=sort_order,
        )

    def get_provisions(
        self,
        db: Session,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: str = "name",
        sort_order: str = "asc"
    ) -> PaginatedResponse:
        """Get provisions (behavior_type='provision')."""
        return self._get_filtered_list(
            db=db,
            organization_id=organization_id,
            extra_filter=self._behavior_type_filter(["provision"]),
            skip=skip, limit=limit,
            is_active=is_active, search=search,
            sort_by=sort_by, sort_order=sort_order,
        )

    def get_liabilities(
        self,
        db: Session,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: str = "name",
        sort_order: str = "asc"
    ) -> PaginatedResponse:
        """Get liabilities (behavior_type='liability') — pasivos/obligaciones."""
        return self._get_filtered_list(
            db=db,
            organization_id=organization_id,
            extra_filter=self._behavior_type_filter(["liability"]),
            skip=skip, limit=limit,
            is_active=is_active, search=search,
            sort_by=sort_by, sort_order=sort_order,
        )

    def get_payable_providers(
        self,
        db: Session,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: str = "name",
        sort_order: str = "asc"
    ) -> PaginatedResponse:
        """Get terceros con behavior_type service_provider (comisionistas)."""
        return self._get_filtered_list(
            db=db,
            organization_id=organization_id,
            extra_filter=self._behavior_type_filter(["service_provider"]),
            skip=skip, limit=limit,
            is_active=is_active, search=search,
            sort_by=sort_by, sort_order=sort_order,
        )

    def get_investors(
        self,
        db: Session,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: str = "name",
        sort_order: str = "asc"
    ) -> PaginatedResponse:
        """Get terceros con behavior_type investor."""
        return self._get_filtered_list(
            db=db,
            organization_id=organization_id,
            extra_filter=self._behavior_type_filter(["investor"]),
            skip=skip, limit=limit,
            is_active=is_active, search=search,
            sort_by=sort_by, sort_order=sort_order,
        )

    def get_generic(
        self,
        db: Session,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: str = "name",
        sort_order: str = "asc"
    ) -> PaginatedResponse:
        """Get terceros con behavior_type generic."""
        return self._get_filtered_list(
            db=db,
            organization_id=organization_id,
            extra_filter=self._behavior_type_filter(["generic"]),
            skip=skip, limit=limit,
            is_active=is_active, search=search,
            sort_by=sort_by, sort_order=sort_order,
        )

    def update_balance(
        self,
        db: Session,
        third_party_id: UUID,
        amount_delta: float,
        organization_id: UUID
    ) -> ThirdParty:
        """Update third party balance by delta amount."""
        third_party = self.get_or_404(
            db,
            third_party_id,
            organization_id,
            detail="Tercero no encontrado"
        )

        amount_delta_decimal = Decimal(str(amount_delta))
        new_balance = third_party.current_balance + amount_delta_decimal
        third_party.current_balance = new_balance

        db.commit()
        db.refresh(third_party)

        return third_party


# Instance for use in endpoints
third_party = CRUDThirdParty(ThirdParty)
