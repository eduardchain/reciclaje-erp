"""Schemas de MaterialKgProfile (SAC, CC-005). Upsert 1:1 por material."""
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

WillardWorld = Literal["none", "postconsumo", "drosses"]


class MaterialKgProfileUpsert(BaseModel):
    """Crea o actualiza el perfil de un material (1:1). willard_world
    single-valued (postconsumo XOR drosses); compra_regular ortogonal."""
    model_config = ConfigDict(extra="forbid")

    compra_regular: bool = False
    willard_world: WillardWorld = "none"


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
    created_at: datetime


class MaterialKgProfileListResponse(BaseModel):
    items: list[MaterialKgProfileResponse]
    total: int
