"""Servicio de MaterialKgProfile (SAC, CC-005). Upsert 1:1 por material +
consulta para alimentar los selectores de recepcion filtrados por mundo."""
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.material import Material
from app.models.material_kg_profile import MaterialKgProfile
from app.schemas.material_kg_profile import (
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
        return resp


material_kg_profile_service = MaterialKgProfileService()
