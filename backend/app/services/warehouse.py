"""
Operaciones CRUD para Warehouse (Bodegas).

Las bodegas representan ubicaciones fisicas donde se almacena material.
"""
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

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

    def _validate_sede(
        self,
        db: Session,
        sede_id: UUID | None,
        organization_id: UUID,
        self_id: UUID | None = None,
    ) -> None:
        """Reglas de la sede. Se valida porque un valor malo aqui no da error:
        da NUMEROS equivocados en silencio (un traslado que debia generar
        maquila y deuda de plomo deja de hacerlo, o al reves).
        """
        if sede_id is None:
            return
        if self_id is not None and sede_id == self_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Una bodega no puede ser su propia sede — deje el campo vacío",
            )
        sede = db.get(Warehouse, sede_id)
        if not sede or sede.organization_id != organization_id or not sede.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La sede indicada no existe en esta organización",
            )
        if sede.is_transit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{sede.name}' es una bodega de tránsito — no puede ser sede",
            )
        # Un solo nivel (mismo criterio que las categorias, #36): si se
        # permitieran cadenas, `_sede_of` tendria que recorrer el arbol y un
        # ciclo colgaria el traslado
        if sede.sede_warehouse_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"'{sede.name}' ya pertenece a otra sede — las sedes son de "
                    "un solo nivel"
                ),
            )

    def create(
        self, db: Session, obj_in: WarehouseCreate, organization_id: UUID
    ) -> Warehouse:
        self._validate_sede(db, obj_in.sede_warehouse_id, organization_id)
        return super().create(db=db, obj_in=obj_in, organization_id=organization_id)

    def update(
        self, db: Session, id: UUID, obj_in: WarehouseUpdate, organization_id: UUID
    ) -> Warehouse:
        if "sede_warehouse_id" in obj_in.model_fields_set:
            self._validate_sede(
                db, obj_in.sede_warehouse_id, organization_id, self_id=id
            )
            # El otro extremo de la cadena: si ESTA bodega ya es sede de otras,
            # darle sede propia dejaria a sus hijas apuntando a un nodo
            # intermedio y `_sede_of` daria respuestas incoherentes
            if obj_in.sede_warehouse_id is not None:
                dependents = db.query(Warehouse).filter(
                    Warehouse.sede_warehouse_id == id,
                    Warehouse.is_active.is_(True),
                ).count()
                if dependents:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Esta bodega es sede de {dependents} bodega(s) — "
                            "no puede pertenecer a otra sede"
                        ),
                    )
        return super().update(
            db=db, id=id, obj_in=obj_in, organization_id=organization_id
        )


# Instancia singleton para uso en endpoints
warehouse = CRUDWarehouse(Warehouse)
