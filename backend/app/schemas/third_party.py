"""
Pydantic schemas for ThirdParty model.
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr, field_serializer, model_validator


class ThirdPartyCategoryBrief(BaseModel):
    """Categoria asignada a un tercero (embebida en response)."""
    id: UUID
    name: str
    display_name: str
    behavior_type: str


class ThirdPartyBase(BaseModel):
    """Base schema for ThirdParty."""
    name: str = Field(..., min_length=1, max_length=200)
    identification_number: Optional[str] = Field(None, max_length=50, description="Tax ID, DNI, RUC, etc")
    email: Optional[EmailStr] = Field(None, max_length=200)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)


class ThirdPartyCreate(ThirdPartyBase):
    """
    Schema for creating a ThirdParty.

    Note:
    - organization_id comes from context automatically
    - current_balance defaults to 0
    """
    initial_balance: Decimal = Field(Decimal("0.00"), description="Saldo inicial")
    category_ids: list[UUID] = Field(default_factory=list, description="IDs de categorias a asignar")


class ThirdPartyUpdate(BaseModel):
    """Schema for updating a ThirdParty (all fields optional)."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    identification_number: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = Field(None, max_length=200)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    category_ids: Optional[list[UUID]] = Field(None, description="IDs de categorias a asignar (reemplaza todas)")


class ThirdPartyResponse(ThirdPartyBase):
    """Schema for ThirdParty responses."""
    id: UUID
    organization_id: UUID
    initial_balance: float
    current_balance: float
    is_active: bool
    categories: list[ThirdPartyCategoryBrief] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer('initial_balance', 'current_balance')
    def serialize_decimal(self, value: Decimal) -> float:
        """Convert Decimal to float for JSON serialization."""
        return float(value)

    @model_validator(mode="before")
    @classmethod
    def extract_categories(cls, data):
        """Extraer categories de category_assignments ORM."""
        if hasattr(data, "__dict__"):
            assignments = getattr(data, "category_assignments", None)
            if assignments:
                cats = []
                for a in assignments:
                    cat = a.category
                    if cat:
                        # Construir display_name
                        parent = getattr(cat, "parent", None)
                        if parent and hasattr(parent, "name"):
                            display_name = f"{parent.name} > {cat.name}"
                        else:
                            display_name = cat.name
                        cats.append({
                            "id": cat.id,
                            "name": cat.name,
                            "display_name": display_name,
                            "behavior_type": cat.behavior_type or "",
                        })
                data.__dict__["categories"] = cats
            elif "categories" not in data.__dict__:
                data.__dict__["categories"] = []
        elif isinstance(data, dict):
            if "categories" not in data:
                data["categories"] = []
        return data


class ThirdPartyBalanceUpdate(BaseModel):
    """Schema for updating third party balance."""
    amount_delta: float = Field(..., description="Amount to add (positive) or subtract (negative)")


# --- Retenciones: catalogo + entidades (SAC E2 D9 + v2 CC-006) --- #

class RetentionConfigCreate(BaseModel):
    """Tarifa configurada: tipo + municipio (solo ica) + concepto opcional (F3)
    + %. El monto al liquidar se pre-calcula con rate_pct y es editable."""
    retention_type: Literal["retefuente", "reteiva", "ica"]
    municipality: Optional[str] = Field(None, min_length=1, max_length=60)
    concept: Optional[str] = Field(None, min_length=1, max_length=60)
    rate_pct: Decimal = Field(..., gt=0, le=100)

    @model_validator(mode="after")
    def _municipality_iff_ica(self):
        if self.retention_type == "ica" and not (self.municipality or "").strip():
            raise ValueError("El municipio es obligatorio para ICA")
        if self.retention_type != "ica" and self.municipality is not None:
            raise ValueError("El municipio solo aplica para ICA")
        return self


class RetentionConfigUpdate(BaseModel):
    rate_pct: Optional[Decimal] = Field(None, gt=0, le=100)
    is_active: Optional[bool] = None


class RetentionRowResponse(BaseModel):
    """Fila del GET unificado (plan v2 D-v2-1): config y/o entidad.
    entity_id NULL = config sin uso aún (sin Pagar/Estado);
    config_id NULL = entidad sin tarifa configurada (sin precálculo)."""
    config_id: Optional[UUID] = None
    entity_id: Optional[UUID] = None
    retention_type: str
    municipality: Optional[str] = None
    concept: Optional[str] = None
    rate_pct: Optional[float] = None
    name: Optional[str] = None
    current_balance: float
    is_active: bool
