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
    created_at: datetime


class MaterialKgProfileListResponse(BaseModel):
    items: list[MaterialKgProfileResponse]
    total: int
