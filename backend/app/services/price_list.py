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
from app.models.price_list_group import PriceListGroup, PriceListGroupMember
from app.models.material import Material
from app.models.material import MaterialCategory
from app.models.user import User
from app.schemas.price_list import PriceListCreate, PriceListUpdate, PriceTableItem, PriceTableResponse
from app.services.base import CRUDBase, Select, PaginatedResponse


class CRUDPriceList(CRUDBase[PriceList, PriceListCreate, PriceListUpdate]):
    """Operaciones CRUD para PriceList con consulta de precio vigente.

    🔴 Listas por proveedor: cada fila pertenece a una lista via
    `price_list_group_id`, y **NULL = la lista general de siempre**. Todo punto
    de lectura tiene que decir a que lista pertenece la pregunta; el default
    explicito es la general, para que agregar una consulta nueva mañana herede
    el comportamiento historico en vez de mezclar precios de listas distintas.
    """

    def _base_query(self, organization_id: UUID) -> Select:
        """Base SEGURA: solo la lista general.

        Se sobrescribe la de `CRUDBase` a proposito. Cualquier metodo que herede
        de aca (`get_multi`, `get_by_field`, y los que se escriban mañana) queda
        acotado a la lista general sin que su autor tenga que acordarse. Los
        metodos que SI saben de listas piden su scope explicito con
        `_scoped_query`.
        """
        return super()._base_query(organization_id).where(
            self.model.price_list_group_id.is_(None)
        )

    def _scoped_query(self, organization_id: UUID, group_id: Optional[UUID]) -> Select:
        """Base para un scope explicito: `None` = lista general, o una lista."""
        stmt = super()._base_query(organization_id)
        if group_id is None:
            return stmt.where(self.model.price_list_group_id.is_(None))
        return stmt.where(self.model.price_list_group_id == group_id)

    def get(
        self,
        db: Session,
        id: UUID,
        organization_id: UUID,
    ) -> Optional[PriceList]:
        """Una fila por su PK, SIN filtro de lista.

        Es la unica lectura que deliberadamente no se acota (decidido en §4 del
        plan): una fila pedida por su identificador es esa fila, y filtrarla por
        grupo solo podria esconderla. Se sobrescribe para saltar el `IS NULL`
        que `_base_query` agrega arriba — sin esto, pedir por PK un precio de
        una lista daria 404.
        """
        statement = super()._base_query(organization_id).where(self.model.id == id)
        return db.execute(statement).scalar_one_or_none()

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

        # 🔴 La lista tiene que existir EN ESTA ORG. Esta validacion es tambien
        # la barrera estructural de D6 sobre este camino: el router de grupos
        # esta gateado por flag, asi que una org sin la funcion no puede tener
        # ninguna lista y por lo tanto **no puede escribir un valor distinto de
        # NULL en esta columna** — no por un chequeo de flag que alguien pueda
        # olvidar, sino porque no existe el id que tendria que mandar.
        if obj_in.price_list_group_id is not None:
            group = db.execute(
                select(PriceListGroup).where(
                    PriceListGroup.id == obj_in.price_list_group_id,
                    PriceListGroup.organization_id == organization_id,
                )
            ).scalar_one_or_none()
            if not group:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Lista de precios no encontrada en esta organizacion",
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
        group_id: Optional[UUID] = None,
    ) -> Optional[PriceList]:
        """
        Obtener el precio vigente (mas reciente) de un material.

        Retorna el registro de PriceList mas reciente para el material dado,
        ordenado por created_at descendente. `group_id=None` = lista general.
        """
        statement = (
            self._scoped_query(organization_id, group_id)
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
        group_id: Optional[UUID] = None,
    ) -> list[PriceList]:
        """
        Obtener el precio vigente de TODOS los materiales.
        Usa DISTINCT ON para retornar solo el registro mas reciente por material.
        `group_id=None` = lista general (comportamiento historico).
        """
        statement = (
            self._scoped_query(organization_id, group_id)
            .distinct(self.model.material_id)
            .order_by(self.model.material_id, self.model.created_at.desc())
        )
        result = db.execute(statement)
        return list(result.scalars().all())

    def resolve_for_supplier(
        self,
        db: Session,
        organization_id: UUID,
        third_party_id: UUID,
    ) -> list[PriceList]:
        """
        🔴 EL RESOLUTOR (D3/D4). Precios que se le sugieren a UN proveedor.

        Regla completa, tal como la fijo Hugo (Q-21/Q-22):

        1. Proveedor CON lista -> los precios de su lista. Un material en cero
           **no se sugiere** (el cero es una decision deliberada, porque la
           lista trae todos los materiales).
        2. Proveedor SIN lista -> **no se sugiere nada**.

        NO hay respaldo a la lista general. Un precio heredado de otra lista
        seria una afirmacion que nadie hizo; un campo vacio es informacion
        honesta ("nadie definio esto").

        ⚠️ Devuelve AUSENCIA, no ceros: quien consume esto no tiene que saber
        interpretar un 0 como "sin precio".

        Vive en el servidor y no en el cliente porque la misma resolucion aplica
        en las 3 pantallas de compras y en la liquidacion de la Entrada, que es
        otro flujo con otro estado. En JS quedaria escrita dos veces — y esta
        regla ya cambio una vez en 24 horas.
        """
        membership = db.execute(
            select(PriceListGroupMember.price_list_group_id)
            .join(PriceListGroup, PriceListGroup.id == PriceListGroupMember.price_list_group_id)
            .where(
                PriceListGroupMember.third_party_id == third_party_id,
                PriceListGroupMember.organization_id == organization_id,
                PriceListGroup.is_active == True,  # noqa: E712
            )
        ).scalar_one_or_none()

        if membership is None:
            # 🔴 D10 — el parametro es INERTE si la org no usa listas.
            #
            # Sin esto, las 3 empresas cliente se quedan SIN NINGUNA sugerencia
            # de precio en compras: las 3 pantallas que llaman a este resolutor
            # son compartidas, asi que en cuanto empiezan a mandar el proveedor,
            # cae aca, no encuentra membresia y devuelve vacio. Ningun test lo
            # veia (todos crean una lista primero) ni el golden (no captura
            # /price-lists) ni abrir la pantalla en SAC (ahi si hay listas).
            #
            # No es un parche: es la semantica correcta — **la funcionalidad
            # esta apagada hasta que alguien cree su primera lista**. Es tambien
            # lo que promete el dialogo de creacion: "desde que exista una, a un
            # proveedor sin lista no se le sugiere ningun precio".
            usa_listas = db.execute(
                select(PriceListGroup.id)
                .where(
                    PriceListGroup.organization_id == organization_id,
                    PriceListGroup.is_active == True,  # noqa: E712
                )
                .limit(1)
            ).scalar_one_or_none()
            if usa_listas is None:
                return self.get_all_current_prices(db, organization_id=organization_id)
            return []

        prices = self.get_all_current_prices(
            db, organization_id=organization_id, group_id=membership
        )
        return [p for p in prices if p.purchase_price and p.purchase_price > 0]

    def get_table(
        self,
        db: Session,
        organization_id: UUID,
        category_id: Optional[UUID] = None,
        group_id: Optional[UUID] = None,
    ) -> PriceTableResponse:
        """Todos los materiales activos con su precio vigente (o null).

        `group_id=None` = la lista general — byte a byte lo de hoy (D7: la
        pantalla de Precios en modo tabla no se toca). Con `group_id`, la misma
        hoja de calculo pero de esa lista: **todos** los materiales activos,
        con precio o vacios, porque la lista trae el catalogo completo y el
        usuario decide a cuales les pone precio (Q-21).
        """
        # Subquery: precio vigente por material (DISTINCT ON) dentro del scope
        group_filter = (
            PriceList.price_list_group_id.is_(None) if group_id is None
            else PriceList.price_list_group_id == group_id
        )
        latest_price = (
            select(
                PriceList.material_id,
                PriceList.purchase_price,
                PriceList.sale_price,
                PriceList.created_at.label("last_updated"),
                PriceList.updated_by,
            )
            .where(PriceList.organization_id == organization_id, group_filter)
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
        group_id: Optional[UUID] = None,
    ) -> PaginatedResponse:
        """
        Obtener historial de precios de un material (mas reciente primero).
        Incluye nombre del usuario que actualizo.

        El historial es POR LISTA: `group_id=None` muestra el de la general, sin
        mezclar los de las listas de proveedor (y al reves).
        """
        base = self._scoped_query(organization_id, group_id).where(
            self.model.material_id == material_id
        )

        # Total
        count_query = select(func.count()).select_from(base.subquery())
        total = db.execute(count_query).scalar_one()

        # Query con JOIN a User para obtener nombre
        group_filter = (
            PriceList.price_list_group_id.is_(None) if group_id is None
            else PriceList.price_list_group_id == group_id
        )
        query = (
            select(PriceList, User.full_name.label("updated_by_name"))
            .select_from(PriceList)
            .outerjoin(User, PriceList.updated_by == User.id)
            .where(
                PriceList.organization_id == organization_id,
                PriceList.material_id == material_id,
                group_filter,
            )
            .order_by(PriceList.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        rows = db.execute(query).all()

        items_data = []
        for row in rows:
            price_obj = row[0]
            item = {c.name: getattr(price_obj, c.name) for c in price_obj.__table__.columns}
            item["updated_by_name"] = row.updated_by_name
            items_data.append(item)

        return PaginatedResponse(
            items=items_data,
            total=total,
            skip=skip,
            limit=limit,
        )


# Instancia singleton para uso en endpoints
price_list = CRUDPriceList(PriceList)
