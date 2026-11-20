"""Servicio de MaterialKgProfile (SAC, CC-005). Upsert 1:1 por material +
consulta para alimentar los selectores de recepcion filtrados por mundo."""
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.material import Material
from app.models.material_kg_profile import MaterialKgProfile
from app.schemas.material_kg_profile import (
    MaterialFormOrderUpdate,
    MaterialKgProfileResponse,
    MaterialKgProfileUpsert,
)


class MaterialKgProfileService:
    """Clasificacion Willard del material (aislada del maestro compartido)."""

    def upsert(
        self,
        db: Session,
        material_id: UUID,
        organization_id: UUID,
        obj_in: MaterialKgProfileUpsert,
        user_id: UUID,
    ) -> MaterialKgProfileResponse:
        material = self._get_material(db, material_id, organization_id)

        profile = db.execute(
            select(MaterialKgProfile).where(
                MaterialKgProfile.organization_id == organization_id,
                MaterialKgProfile.material_id == material_id,
            )
        ).scalar_one_or_none()

        if profile is None:
            profile = MaterialKgProfile(
                organization_id=organization_id,
                material_id=material_id,
                created_by=user_id,
            )
            db.add(profile)
        profile.compra_regular = obj_in.compra_regular
        profile.willard_world = obj_in.willard_world
        profile.lead_product = obj_in.lead_product

        db.commit()
        db.refresh(profile)
        return self._enrich(profile, material)

    def get_for_material(
        self, db: Session, material_id: UUID, organization_id: UUID
    ) -> MaterialKgProfileResponse:
        material = self._get_material(db, material_id, organization_id)
        profile = db.execute(
            select(MaterialKgProfile).where(
                MaterialKgProfile.organization_id == organization_id,
                MaterialKgProfile.material_id == material_id,
            )
        ).scalar_one_or_none()
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El material no tiene clasificacion Willard",
            )
        return self._enrich(profile, material)

    def list(
        self,
        db: Session,
        organization_id: UUID,
        compra_regular: Optional[bool] = None,
        willard_world: Optional[str] = None,
    ) -> list[MaterialKgProfileResponse]:
        query = (
            select(MaterialKgProfile, Material)
            .join(Material, MaterialKgProfile.material_id == Material.id)
            .where(MaterialKgProfile.organization_id == organization_id)
        )
        if compra_regular is not None:
            query = query.where(MaterialKgProfile.compra_regular.is_(compra_regular))
        if willard_world is not None:
            query = query.where(MaterialKgProfile.willard_world == willard_world)
        query = query.order_by(Material.code)
        return [self._enrich(row[0], row[1]) for row in db.execute(query).all()]

    def set_form_order(
        self,
        db: Session,
        organization_id: UUID,
        obj_in: MaterialFormOrderUpdate,
    ) -> List[MaterialKgProfileResponse]:
        """Reemplaza el formato en papel de la organizacion (D2, REPLACE).

        La posicion de cada material es su indice en la lista + 1; un `null`
        deja el renglon vacio. Todo se valida ANTES de escribir: un 422 no deja
        nada a medias.
        """
        ids = [m for m in obj_in.material_ids if m is not None]

        def _rechazo(detalle: str) -> HTTPException:
            return HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detalle
            )

        vistos: set = set()
        for mid in ids:
            if mid in vistos:
                material = db.get(Material, mid)
                nombre = material.code if material else mid
                raise _rechazo(f"{nombre} esta dos veces en el formato")
            vistos.add(mid)

        profiles: dict = {}
        for mid in ids:
            material = db.get(Material, mid)
            if material is None or material.organization_id != organization_id:
                raise _rechazo(f"El material {mid} no es de esta organizacion")
            if not material.is_active:
                raise _rechazo(
                    f"{material.code} esta inactivo: quitelo del formato antes de guardar"
                )
            profile = db.execute(
                select(MaterialKgProfile).where(
                    MaterialKgProfile.organization_id == organization_id,
                    MaterialKgProfile.material_id == mid,
                )
            ).scalar_one_or_none()
            if profile is None:
                raise _rechazo(
                    f"{material.code} no esta clasificado: clasifiquelo en "
                    f"Configuracion > Materiales (kg) antes de ponerlo en el formato"
                )
            profiles[mid] = profile

        # F2: primero NULL a TODA la organizacion y flush, despues las
        # posiciones. El indice unico no es diferible: asignar fila por fila
        # con otra fila todavia en ese numero (un intercambio de dos renglones,
        # que es lo que hacen las flechas) revienta a mitad de la transaccion.
        db.execute(
            update(MaterialKgProfile)
            .where(MaterialKgProfile.organization_id == organization_id)
            .values(form_order=None)
            .execution_options(synchronize_session="fetch")
        )
        db.flush()
        for posicion, mid in enumerate(obj_in.material_ids, start=1):
            if mid is not None:
                profiles[mid].form_order = posicion
        db.commit()
        return self.list(db, organization_id=organization_id)

    @staticmethod
    def _get_material(db: Session, material_id: UUID, organization_id: UUID) -> Material:
        material = db.get(Material, material_id)
        if not material or material.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Material no encontrado en esta organizacion",
            )
        return material

    @staticmethod
    def _enrich(
        profile: MaterialKgProfile, material: Optional[Material]
    ) -> MaterialKgProfileResponse:
        resp = MaterialKgProfileResponse.model_validate(profile)
        if material is not None:
            resp.material_code = material.code
            resp.material_name = material.name
            resp.material_unit = material.default_unit or "kg"
            resp.material_is_active = material.is_active
        return resp


material_kg_profile_service = MaterialKgProfileService()
