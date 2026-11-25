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
    MaterialControlUpdate,
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

        # Documentos de control §4.1 — coherencia en la direccion del upsert
        # (#112 D4d): el upsert NO conoce la marca, pero la lee guardada. Un
        # material de control no puede volverse Willard ni plomo: esa es la
        # razon por la que los caminos Willard y Salidas de Plomo no lo ven.
        if profile is not None and profile.control_only:
            self._reject_control_conflict(
                material, obj_in.willard_world, obj_in.lead_product,
                "upsert",
            )

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

    def set_control(
        self,
        db: Session,
        material_id: UUID,
        organization_id: UUID,
        obj_in: MaterialControlUpdate,
        user_id: UUID,
    ) -> MaterialKgProfileResponse:
        """Marca o desmarca un material como solo de control (plan
        documentos de control §4.1). Endpoint propio: el upsert reemplaza el
        perfil entero y una marca con default ahi se borraria en silencio
        (#103 D4). Si el material no tiene perfil, nace con los defaults.

        Marcar no reescribe nada: el estado de una Entrada se decide al leer
        la marca en el momento de cerrar o liquidar (R2)."""
        material = self._get_material(db, material_id, organization_id)
        profile = db.execute(
            select(MaterialKgProfile).where(
                MaterialKgProfile.organization_id == organization_id,
                MaterialKgProfile.material_id == material_id,
            )
        ).scalar_one_or_none()
        if obj_in.control_only and profile is not None:
            self._reject_control_conflict(
                material, profile.willard_world, profile.lead_product,
                "mark",
            )
        if profile is None:
            profile = MaterialKgProfile(
                organization_id=organization_id,
                material_id=material_id,
                created_by=user_id,
            )
            db.add(profile)
        profile.control_only = obj_in.control_only
        db.commit()
        db.refresh(profile)
        return self._enrich(profile, material)

    @staticmethod
    def _reject_control_conflict(
        material: Material, willard_world: str, lead_product: str, direction: str
    ) -> None:
        """Un material de control exige willard_world y lead_product en 'none'
        (§4.1). `direction`: 'mark' (se marca un material que ya es Willard o
        plomo) o 'upsert' (se clasifica como Willard o plomo uno ya marcado)."""
        found = []
        if willard_world != "none":
            found.append(f"tipo Willard ({willard_world})")
        if lead_product != "none":
            found.append(f"marca de plomo ({lead_product})")
        if not found:
            return
        what = " y ".join(found)
        if direction == "mark":
            detail = (
                f"{material.code} no puede ser solo de control: tiene {what}. "
                "Quitelo primero en su clasificacion"
            )
        else:
            detail = (
                f"{material.code} es solo de control: no puede tener {what}. "
                "Quite primero la marca de control"
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail
        )

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


def control_material_ids(db: Session, organization_id: UUID, material_ids) -> set:
    """Materiales marcados solo de control (`control_only`), leidos AL MOMENTO
    (R2 del plan de documentos de control): la marca no se copia a la linea,
    asi que marcar un material despues de capturar sirve para las Entradas ya
    registradas. UN solo predicado para la Entrada, la Salida de control y los
    guards D5 de compras y ventas."""
    ids = list({m for m in material_ids if m is not None})
    if not ids:
        return set()
    return set(
        db.execute(
            select(MaterialKgProfile.material_id).where(
                MaterialKgProfile.organization_id == organization_id,
                MaterialKgProfile.material_id.in_(ids),
                MaterialKgProfile.control_only.is_(True),
            )
        ).scalars()
    )


def guard_no_control_materials(
    db: Session, organization_id: UUID, material_ids, remedy: str
) -> None:
    """D5: Ventas y Compras directas NO llevan materiales de control (estibas,
    tubulares, electrolito a $0). Vendidos o comprados por aca sacan o meten
    inventario a un precio; lo que corresponde es la Salida o la Entrada de
    control, que solo dejan el consecutivo. Espejo de #104 y #80 B3.

    Solo con `kg_ledger_enabled`: sin flag no hay perfiles y el guard es
    inerte (las otras orgs byte a byte; el PAR con y sin flag es la red, #99).
    400, el idioma de compras y ventas."""
    from app.utils.org_settings import get_org_setting
    if not get_org_setting(db, organization_id, "kg_ledger_enabled"):
        return
    ids = control_material_ids(db, organization_id, material_ids)
    if not ids:
        return
    codes = db.execute(select(Material.code).where(Material.id.in_(list(ids)))).scalars().all()
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"El material {', '.join(sorted(set(codes)))} es solo de control (sin valor) — {remedy}",
    )
