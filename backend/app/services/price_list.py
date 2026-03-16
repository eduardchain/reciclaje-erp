"""
Operaciones CRUD para PriceList (Listas de Precios).

Ademas del CRUD estandar, incluye un metodo especial para obtener
el precio vigente de un material (el registro mas reciente).
"""
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.price_list import PriceList
from app.models.material import Material
from app.models.material import MaterialCategory
from app.models.user import User
from app.schemas.price_list import PriceListCreate, PriceListUpdate, PriceTableItem, PriceTableResponse
from app.services.base import CRUDBase, Select, PaginatedResponse


class CRUDPriceList(CRUDBase[PriceList, PriceListCreate, PriceListUpdate]):
    """Operaciones CRUD para PriceList con consulta de precio vigente."""

    def create(
        self,
        db: Session,
        obj_in: PriceListCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> PriceList:
        """
        Crear un nuevo registro de precio para un material.

        Validaciones:
        - El material debe existir y pertenecer a la misma organizacion.
        """
        # Validar que el material existe en esta organizacion
        material = db.execute(
            select(Material).where(
                Material.id == obj_in.material_id,
                Material.organization_id == organization_id,
            )
        ).scalar_one_or_none()

        if not material:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Material no encontrado en esta organizacion",
            )

        obj_data = obj_in.model_dump()
        obj_data["organization_id"] = organization_id
        obj_data["updated_by"] = user_id

        db_obj = self.model(**obj_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)

        return db_obj

    def get_current_price(
        self,
        db: Session,
        material_id: UUID,
        organization_id: UUID,
    ) -> Optional[PriceList]:
        """
        Obtener el precio vigente (mas reciente) de un material.

        Retorna el registro de PriceList mas reciente para el material dado,
        ordenado por created_at descendente.
        """
        statement = (
            self._base_query(organization_id)
            .where(self.model.material_id == material_id)
            .order_by(self.model.created_at.desc())
            .limit(1)
        )
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def get_all_current_prices(
        self,
        db: Session,
        organization_id: UUID,
    ) -> list[PriceList]:
        """
        Obtener el precio vigente de TODOS los materiales.
        Usa DISTINCT ON para retornar solo el registro mas reciente por material.
        """
        statement = (
            self._base_query(organization_id)
            .distinct(self.model.material_id)
            .order_by(self.model.material_id, self.model.created_at.desc())
        )
        result = db.execute(statement)
        return list(result.scalars().all())

    def get_table(
        self,
        db: Session,
        organization_id: UUID,
        category_id: Optional[UUID] = None,
    ) -> PriceTableResponse:
        """Todos los materiales activos con su precio vigente (o null)."""
        # Subquery: precio vigente por material (DISTINCT ON)
        latest_price = (
            select(
                PriceList.material_id,
                PriceList.purchase_price,
                PriceList.sale_price,
                PriceList.created_at.label("last_updated"),
                PriceList.updated_by,
            )
            .where(PriceList.organization_id == organization_id)
            .distinct(PriceList.material_id)
            .order_by(PriceList.material_id, PriceList.created_at.desc())
            .subquery("latest_price")
        )

        # Query principal: materiales LEFT JOIN precio vigente LEFT JOIN usuario
        query = (
            select(
                Material.id.label("material_id"),
                Material.code.label("material_code"),
                Material.name.label("material_name"),
                Material.category_id,
                MaterialCategory.name.label("category_name"),
                latest_price.c.purchase_price,
                latest_price.c.sale_price,
                latest_price.c.last_updated,
                User.full_name.label("updated_by_name"),
            )
            .outerjoin(MaterialCategory, Material.category_id == MaterialCategory.id)
            .outerjoin(latest_price, Material.id == latest_price.c.material_id)
            .outerjoin(User, latest_price.c.updated_by == User.id)
            .where(
                Material.organization_id == organization_id,
                Material.is_active == True,
            )
        )

        if category_id:
            query = query.where(Material.category_id == category_id)

        query = query.order_by(Material.sort_order, Material.code)

        rows = db.execute(query).all()

        items = [
            PriceTableItem(
                material_id=row.material_id,
                material_code=row.material_code,
                material_name=row.material_name,
                category_id=row.category_id,
                category_name=row.category_name,
                purchase_price=float(row.purchase_price) if row.purchase_price is not None else None,
                sale_price=float(row.sale_price) if row.sale_price is not None else None,
                last_updated=row.last_updated,
                updated_by_name=row.updated_by_name,
            )
            for row in rows
        ]

        return PriceTableResponse(items=items)

    def get_by_material(
        self,
        db: Session,
        material_id: UUID,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> PaginatedResponse:
        """
        Obtener historial de precios de un material (mas reciente primero).
        """
        from sqlalchemy import func

        query = self._base_query(organization_id).where(
            self.model.material_id == material_id
        )

        # Total
        count_query = select(func.count()).select_from(query.subquery())
        total = db.execute(count_query).scalar_one()

        # Ordenar por fecha descendente y paginar
        query = (
            query.order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = db.execute(query)
        items = result.scalars().all()

        items_data = [
            {c.name: getattr(item, c.name) for c in item.__table__.columns}
            for item in items
        ]

        return PaginatedResponse(
            items=items_data,
            total=total,
            skip=skip,
            limit=limit,
        )


# Instancia singleton para uso en endpoints
price_list = CRUDPriceList(PriceList)
