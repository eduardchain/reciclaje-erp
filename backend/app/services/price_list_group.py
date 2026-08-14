"""
Servicio de listas de precios por proveedor (PriceListGroup).

La membresia es exclusiva por tercero (`UNIQUE(third_party_id)` en la base), asi
que asignar un proveedor que ya pertenece a otra lista **lo mueve**. La pantalla
lo avisa antes de guardar; aca se ejecuta.
"""
from typing import Optional
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select, func, delete as sa_delete
from sqlalchemy.orm import Session

from app.models.price_list import PriceList
from app.models.price_list_group import PriceListGroup, PriceListGroupMember
from app.models.third_party import ThirdParty
from app.schemas.price_list_group import (
    PriceListGroupCreate,
    PriceListGroupUpdate,
    SupplierMembershipItem,
)
from app.services.third_party import third_party as third_party_service


class PriceListGroupService:
    """CRUD de listas + membresia + el sembrado del dia uno (Q-26)."""

    def _active_suppliers(self, db: Session, organization_id: UUID) -> list[ThirdParty]:
        """Proveedores de material activos, TODOS.

        ⚠️ Deliberadamente NO usa `third_party_service.get_suppliers`: ese
        devuelve una respuesta paginada con `limit=100` por defecto, y aca una
        pagina incompleta no da un error — hace que el sembrado se salte
        proveedores **en silencio** y que el selector de la pantalla muestre una
        lista corta que parece completa. Se reusa su filtro de behavior_type,
        que es la parte que importa.
        """
        return list(
            db.execute(
                select(ThirdParty)
                .where(
                    ThirdParty.organization_id == organization_id,
                    ThirdParty.is_active == True,  # noqa: E712
                    third_party_service._behavior_type_filter(["material_supplier"]),
                )
                .order_by(ThirdParty.name)
            ).scalars().all()
        )

    # ------------------------------------------------------------------ listas

    def get_or_404(self, db: Session, group_id: UUID, organization_id: UUID) -> PriceListGroup:
        group = db.execute(
            select(PriceListGroup).where(
                PriceListGroup.id == group_id,
                PriceListGroup.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lista de precios no encontrada",
            )
        return group

    def list_groups(
        self, db: Session, organization_id: UUID, include_inactive: bool = False
    ) -> list[dict]:
        """Listas con sus dos conteos (proveedores y materiales con precio)."""
        stmt = select(PriceListGroup).where(
            PriceListGroup.organization_id == organization_id
        )
        if not include_inactive:
            stmt = stmt.where(PriceListGroup.is_active == True)  # noqa: E712
        groups = list(db.execute(stmt.order_by(PriceListGroup.name)).scalars().all())
        if not groups:
            return []

        ids = [g.id for g in groups]

        member_counts = dict(
            db.execute(
                select(
                    PriceListGroupMember.price_list_group_id,
                    func.count(PriceListGroupMember.id),
                )
                .where(PriceListGroupMember.price_list_group_id.in_(ids))
                .group_by(PriceListGroupMember.price_list_group_id)
            ).all()
        )

        # Materiales con precio > 0 VIGENTE (el vigente es el mas reciente por
        # material dentro de la lista — mismo criterio append-only de #35).
        latest = (
            select(
                PriceList.price_list_group_id.label("gid"),
                PriceList.material_id,
                PriceList.purchase_price,
            )
            .where(PriceList.price_list_group_id.in_(ids))
            .distinct(PriceList.price_list_group_id, PriceList.material_id)
            .order_by(
                PriceList.price_list_group_id,
                PriceList.material_id,
                PriceList.created_at.desc(),
            )
            .subquery("latest")
        )
        priced_counts = dict(
            db.execute(
                select(latest.c.gid, func.count())
                .where(latest.c.purchase_price > 0)
                .group_by(latest.c.gid)
            ).all()
        )

        return [
            {
                "id": g.id,
                "organization_id": g.organization_id,
                "name": g.name,
                "is_active": g.is_active,
                "member_count": member_counts.get(g.id, 0),
                "priced_material_count": priced_counts.get(g.id, 0),
                "created_at": g.created_at,
                "updated_at": g.updated_at,
            }
            for g in groups
        ]

    def create(
        self,
        db: Session,
        obj_in: PriceListGroupCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> tuple[PriceListGroup, int, int, int]:
        """Crea la lista y, si se pide, la siembra. Retorna (grupo, precios, asignados, omitidos)."""
        existing = db.execute(
            select(PriceListGroup).where(
                PriceListGroup.organization_id == organization_id,
                func.lower(PriceListGroup.name) == obj_in.name.strip().lower(),
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe una lista llamada '{existing.name}'",
            )

        group = PriceListGroup(
            id=uuid4(),
            name=obj_in.name.strip(),
            organization_id=organization_id,
            is_active=True,
        )
        db.add(group)
        db.flush()

        seeded = self._seed_from_general(db, group, organization_id, user_id) if obj_in.seed_from_general else 0
        assigned, skipped = (
            self._assign_unassigned_suppliers(db, group, organization_id)
            if obj_in.assign_all_suppliers else (0, 0)
        )

        db.commit()
        db.refresh(group)
        return group, seeded, assigned, skipped

    def update(
        self,
        db: Session,
        group_id: UUID,
        obj_in: PriceListGroupUpdate,
        organization_id: UUID,
    ) -> PriceListGroup:
        group = self.get_or_404(db, group_id, organization_id)

        if obj_in.name is not None and obj_in.name.strip().lower() != group.name.lower():
            clash = db.execute(
                select(PriceListGroup).where(
                    PriceListGroup.organization_id == organization_id,
                    func.lower(PriceListGroup.name) == obj_in.name.strip().lower(),
                    PriceListGroup.id != group_id,
                )
            ).scalar_one_or_none()
            if clash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe una lista llamada '{clash.name}'",
                )
            group.name = obj_in.name.strip()

        if obj_in.is_active is not None:
            group.is_active = obj_in.is_active

        db.commit()
        db.refresh(group)
        return group

    # -------------------------------------------------------------- membresia

    def list_supplier_memberships(
        self, db: Session, organization_id: UUID
    ) -> list[SupplierMembershipItem]:
        """
        Todos los proveedores de material, con la lista a la que pertenecen HOY.

        Alimenta el selector de la pantalla: el conflicto ("este ya esta en la
        Lista B") se muestra ANTES de guardar, en vez de descubrirlo cuando la
        base rechaza el UNIQUE.
        """
        suppliers = self._active_suppliers(db, organization_id)

        rows = db.execute(
            select(
                PriceListGroupMember.third_party_id,
                PriceListGroup.id,
                PriceListGroup.name,
            )
            .join(PriceListGroup, PriceListGroup.id == PriceListGroupMember.price_list_group_id)
            .where(PriceListGroupMember.organization_id == organization_id)
        ).all()
        by_tp = {r[0]: (r[1], r[2]) for r in rows}

        items = []
        for sup in suppliers:
            gid, gname = by_tp.get(sup.id, (None, None))
            items.append(
                SupplierMembershipItem(
                    third_party_id=sup.id,
                    third_party_name=sup.name,
                    current_group_id=gid,
                    current_group_name=gname,
                )
            )
        return items

    def set_members(
        self,
        db: Session,
        group_id: UUID,
        third_party_ids: list[UUID],
        organization_id: UUID,
    ) -> int:
        """
        Reemplaza el conjunto de proveedores de la lista (D12).

        Un tercero que venia de OTRA lista se mueve — la unicidad es de la base
        y la pantalla ya lo advirtio. Se validan uno por uno contra la org para
        que un id ajeno no entre por el borde.
        """
        self.get_or_404(db, group_id, organization_id)

        wanted = list(dict.fromkeys(third_party_ids))  # dedup preservando orden
        if wanted:
            found = set(
                db.execute(
                    select(ThirdParty.id).where(
                        ThirdParty.id.in_(wanted),
                        ThirdParty.organization_id == organization_id,
                    )
                ).scalars().all()
            )
            missing = [str(i) for i in wanted if i not in found]
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Tercero(s) no encontrado(s) en esta organizacion: {', '.join(missing)}",
                )

        # Borrar la membresia previa de la lista Y la de los terceros que llegan
        # desde otra: el UNIQUE es por tercero, asi que mover es borrar+crear.
        db.execute(
            sa_delete(PriceListGroupMember).where(
                PriceListGroupMember.price_list_group_id == group_id
            )
        )
        if wanted:
            db.execute(
                sa_delete(PriceListGroupMember).where(
                    PriceListGroupMember.third_party_id.in_(wanted)
                )
            )
            for tp_id in wanted:
                db.add(
                    PriceListGroupMember(
                        id=uuid4(),
                        price_list_group_id=group_id,
                        third_party_id=tp_id,
                        organization_id=organization_id,
                    )
                )

        db.commit()
        return len(wanted)

    # --------------------------------------------------------------- sembrado

    def _seed_from_general(
        self,
        db: Session,
        group: PriceListGroup,
        organization_id: UUID,
        user_id: Optional[UUID],
    ) -> int:
        """
        Copia los precios vigentes de la lista general a la lista nueva.

        🟢 Es la salida de Q-26 y NO es cosmetica. Sin esto, el dia que se
        enciende la funcion ningun proveedor tiene lista y **todos pierden el
        precio sugerido de golpe** (D3: sin lista no se sugiere nada), con un
        campo vacio como unico sintoma — facil de leer como "el sistema se
        daño". Con esto, el dia uno se comporta igual que hoy y mover un
        proveedor a su lista propia es una edicion, no una carga desde cero.

        Ademas ejercita de inmediato la premisa de Q-21 ("la lista trae todos
        los materiales, el cero es deliberado"): si no se sostiene en la
        practica, se ve en la primera semana.

        Copia solo lo que tiene precio de compra > 0 — un cero de la general no
        es una decision de nadie sobre esta lista.
        """
        current = db.execute(
            select(PriceList)
            .where(
                PriceList.organization_id == organization_id,
                PriceList.price_list_group_id.is_(None),
            )
            .distinct(PriceList.material_id)
            .order_by(PriceList.material_id, PriceList.created_at.desc())
        ).scalars().all()

        n = 0
        for src in current:
            if not src.purchase_price or src.purchase_price <= 0:
                continue
            db.add(
                PriceList(
                    id=uuid4(),
                    material_id=src.material_id,
                    purchase_price=src.purchase_price,
                    sale_price=0,
                    notes=f"Sembrado desde la lista general al crear '{group.name}'",
                    price_list_group_id=group.id,
                    organization_id=organization_id,
                    updated_by=user_id,
                )
            )
            n += 1
        return n

    def _assign_unassigned_suppliers(
        self, db: Session, group: PriceListGroup, organization_id: UUID
    ) -> tuple[int, int]:
        """
        Asigna a la lista los proveedores de material que HOY no tienen ninguna.

        🔴 No roba proveedores de otras listas: el sembrado es una red de
        seguridad para el dia uno, no una reasignacion masiva que pise el
        trabajo que alguien ya hizo. Retorna (asignados, omitidos).
        """
        suppliers = self._active_suppliers(db, organization_id)
        taken = set(
            db.execute(
                select(PriceListGroupMember.third_party_id).where(
                    PriceListGroupMember.organization_id == organization_id
                )
            ).scalars().all()
        )

        assigned = skipped = 0
        for sup in suppliers:
            if sup.id in taken:
                skipped += 1
                continue
            db.add(
                PriceListGroupMember(
                    id=uuid4(),
                    price_list_group_id=group.id,
                    third_party_id=sup.id,
                    organization_id=organization_id,
                )
            )
            assigned += 1
        return assigned, skipped


price_list_group_service = PriceListGroupService()
