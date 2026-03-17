"""
Schemas Pydantic para ThirdPartyCategory.

Incluye validacion de behavior_type contra enum BehaviorType,
y schemas flat para selectors con display_name.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator

from app.models.third_party_category import BehaviorType


# --- CRUD Schemas ---

class ThirdPartyCategoryCreate(BaseModel):
    """Crear categoria de tercero."""
    name: str
    description: Optional[str] = None
    parent_id: Optional[UUID] = None
    behavior_type: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError("El nombre no puede estar vacio")
        return v.strip()

    @field_validator("behavior_type")
    @classmethod
    def validate_behavior_type(cls, v):
        if v is not None:
            try:
                BehaviorType(v)
            except ValueError:
                valid = [bt.value for bt in BehaviorType]
                raise ValueError(f"behavior_type invalido. Valores validos: {valid}")
        return v


class ThirdPartyCategoryUpdate(BaseModel):
    """Actualizar categoria de tercero (campos parciales)."""
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[UUID] = None

    model_config = {"from_attributes": True}


class ThirdPartyCategoryResponse(BaseModel):
    """Respuesta de categoria de tercero."""
    id: UUID
    organization_id: UUID
    name: str
    description: Optional[str] = None
    parent_id: Optional[UUID] = None
    parent_name: Optional[str] = None
    behavior_type: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def extract_parent_name(cls, data):
        """Extraer parent_name de la relacion ORM."""
        if hasattr(data, "__dict__"):
            d = data.__dict__
            parent = d.get("parent")
            if parent and hasattr(parent, "name"):
                d["parent_name"] = parent.name
            elif "parent_name" not in d:
                d["parent_name"] = None
        return data


# --- Flat Schemas (para selectors) ---

class ThirdPartyCategoryFlat(BaseModel):
    """Categoria plana para selectors con display_name."""
    id: UUID
    name: str
    display_name: str
    parent_id: Optional[UUID] = None
    behavior_type: str


class ThirdPartyCategoryFlatResponse(BaseModel):
    """Lista plana de categorias para selectors."""
    items: list[ThirdPartyCategoryFlat]
