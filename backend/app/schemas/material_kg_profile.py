"""Schemas de MaterialKgProfile (SAC, CC-005). Upsert 1:1 por material."""
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

WillardWorld = Literal["none", "postconsumo", "drosses"]
LeadProduct = Literal["none", "crudo", "puro"]


class MaterialKgProfileUpsert(BaseModel):
    """Crea o actualiza el perfil de un material (1:1). willard_world
    single-valued (postconsumo XOR drosses); compra_regular ortogonal."""
    model_config = ConfigDict(extra="forbid")

    compra_regular: bool = False
    willard_world: WillardWorld = "none"

    # SIN default a proposito (C5 del QA de SAC). El schema es `extra="forbid"`
    # pero el PUT reemplaza el perfil entero: un caller que mande solo
    # {compra_regular, willard_world} —como hacia la pantalla de Config— borraria
    # la marca de plomo EN SILENCIO, y es la misma pantalla a la que el guard
    # manda al usuario a marcarla. Obligatorio => 422 si falta => ningun caller
    # parcial puede borrarla. Es el NOT NULL de la columna aplicado al camino de
    # escritura: hacer imposible lo incorrecto en vez de vigilarlo (#94/#102).
    lead_product: LeadProduct


class MaterialKgProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    material_id: UUID
    material_code: Optional[str] = None
    material_name: Optional[str] = None
    material_unit: Optional[str] = None
    compra_regular: bool
    willard_world: str
    lead_product: str
    # Documentos de control (solo lectura; se escribe por /{id}/control).
    control_only: bool = False
    # Orden del formato en papel (solo lectura; se escribe por /form-order).
    form_order: Optional[int] = None
    # F3: un material del formato puede desactivarse despues y conserva su
    # renglon. Config lo marca para que el usuario lo pueda quitar.
    material_is_active: Optional[bool] = None
    created_at: datetime


class MaterialKgProfileListResponse(BaseModel):
    items: list[MaterialKgProfileResponse]
    total: int


class MaterialFormOrderUpdate(BaseModel):
    """Lista COMPLETA del formato, en orden. `null` es un renglon vacio (el 8
    de Batería Húmeda, Q-72): conserva la numeracion del papel. REPLACE: los
    materiales que no esten en la lista salen del formato."""
    model_config = ConfigDict(extra="forbid")

    material_ids: list[Optional[UUID]]


class MaterialControlUpdate(BaseModel):
    """Marca o desmarca un material como solo de control (documentos de
    control §4.1). Endpoint propio: el upsert del perfil no la conoce."""
    model_config = ConfigDict(extra="forbid")

    control_only: bool
