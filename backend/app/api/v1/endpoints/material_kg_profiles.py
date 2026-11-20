"""Endpoints de MaterialKgProfile — clasificacion Willard del material (SAC, CC-005).

Router gated por flag kg_ledger_enabled (D10): 403 incluso para admins si la org
no tiene el modulo — aisla la clasificacion del maestro compartido (3 orgs prod).
Permisos: reusa los de materials (materials.view lectura, materials.edit escritura).
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_org_flag, require_permission
from app.schemas.material_kg_profile import (
    MaterialFormOrderUpdate,
    MaterialKgProfileListResponse,
    MaterialKgProfileResponse,
    MaterialKgProfileUpsert,
)
from app.services.material_kg_profile import material_kg_profile_service

router = APIRouter(dependencies=[Depends(require_org_flag("kg_ledger_enabled"))])


@router.get("", response_model=MaterialKgProfileListResponse)
def list_material_kg_profiles(
    compra_regular: Optional[bool] = Query(None),
    willard_world: Optional[str] = Query(None, pattern="^(none|postconsumo|drosses)$"),
    org_context: dict = Depends(require_permission("materials.view")),
    db: Session = Depends(get_db),
):
    """Perfiles de clasificacion — alimenta los selectores de recepcion por mundo."""
    items = material_kg_profile_service.list(
        db,
        organization_id=org_context["organization_id"],
        compra_regular=compra_regular,
        willard_world=willard_world,
    )
    return MaterialKgProfileListResponse(items=items, total=len(items))


# F1: ruta ESTATICA declarada ANTES de las de `/{material_id}` — si va despues,
# FastAPI intenta parsear "form-order" como UUID y responde 422.
@router.put("/form-order", response_model=MaterialKgProfileListResponse)
def set_material_form_order(
    order_in: MaterialFormOrderUpdate,
    org_context: dict = Depends(require_permission("materials.edit")),
    db: Session = Depends(get_db),
):
    """Reemplaza el orden del formato en papel «Materiales recolectados»
    (lista completa; `null` = renglon vacio). Los materiales que no vienen
    salen del formato."""
    items = material_kg_profile_service.set_form_order(
        db, organization_id=org_context["organization_id"], obj_in=order_in
    )
    return MaterialKgProfileListResponse(items=items, total=len(items))


@router.get("/{material_id}", response_model=MaterialKgProfileResponse)
def get_material_kg_profile(
    material_id: UUID,
    org_context: dict = Depends(require_permission("materials.view")),
    db: Session = Depends(get_db),
):
    """Perfil de un material (404 si no tiene clasificacion)."""
    return material_kg_profile_service.get_for_material(
        db, material_id=material_id, organization_id=org_context["organization_id"]
    )


@router.put("/{material_id}", response_model=MaterialKgProfileResponse)
def upsert_material_kg_profile(
    material_id: UUID,
    profile_in: MaterialKgProfileUpsert,
    org_context: dict = Depends(require_permission("materials.edit")),
    db: Session = Depends(get_db),
):
    """Crea o actualiza el perfil (1:1 por material)."""
    return material_kg_profile_service.upsert(
        db,
        material_id=material_id,
        organization_id=org_context["organization_id"],
        obj_in=profile_in,
        user_id=org_context["user_id"],
    )
