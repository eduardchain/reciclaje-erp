"""Servicios de Driver y Vehicle (SAC E1, v0.5 §11.1.14, plan §4.5).

CRUD estandar sobre CRUDBase (soft delete via is_active). Unicidad de placa
en SERVICIO, no en BD (D14) — patron del repo para maestros con soft delete:
se valida duplicado ACTIVO (422 amistoso) y se permite reusar la placa de un
vehiculo inactivo (caso real: re-digitacion tras error).
"""
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.fleet import Driver, Vehicle
from app.schemas.fleet import DriverCreate, DriverUpdate, VehicleCreate, VehicleUpdate
from app.services.base import CRUDBase


class CRUDDriver(CRUDBase[Driver, DriverCreate, DriverUpdate]):
    pass


class CRUDVehicle(CRUDBase[Vehicle, VehicleCreate, VehicleUpdate]):
    def _check_active_plate(
        self,
        db: Session,
        organization_id: UUID,
        plate: str,
        exclude_id: Optional[UUID] = None,
    ) -> None:
        """422 si ya existe un vehiculo ACTIVO con la misma placa (case-insensitive)."""
        query = select(Vehicle).where(
            Vehicle.organization_id == organization_id,
            Vehicle.is_active == True,  # noqa: E712
            func.upper(Vehicle.plate) == plate.strip().upper(),
        )
        if exclude_id:
            query = query.where(Vehicle.id != exclude_id)
        if db.execute(query).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Ya existe un vehiculo activo con placa {plate.strip().upper()}",
            )

    def create(self, db: Session, obj_in: VehicleCreate, organization_id: UUID) -> Vehicle:
        self._check_active_plate(db, organization_id, obj_in.plate)
        return super().create(db, obj_in, organization_id)

    def update(
        self, db: Session, id: UUID, obj_in: VehicleUpdate, organization_id: UUID
    ) -> Vehicle:
        update_data = obj_in.model_dump(exclude_unset=True)
        # Cambiar placa o reactivar puede chocar con otro vehiculo activo
        if "plate" in update_data or update_data.get("is_active") is True:
            current = self.get_or_404(db, id, organization_id)
            new_plate = update_data.get("plate", current.plate)
            will_be_active = update_data.get("is_active", current.is_active)
            if will_be_active:
                self._check_active_plate(db, organization_id, new_plate, exclude_id=id)
        return super().update(db, id, obj_in, organization_id)


driver = CRUDDriver(Driver)
vehicle = CRUDVehicle(Vehicle)
