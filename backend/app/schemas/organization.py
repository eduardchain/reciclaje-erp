from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
import re


class OrgSettingsPayload(BaseModel):
    """Payload tipado de organization.settings (SAC E1, D3).

    SOLO tipos JSON-NATIVOS (bool/int/float/list[int]) — el write path es
    model_dump() python-mode + json.dumps default del engine (sin
    json_serializer): un Decimal aqui revienta con 500 (H1 QA). PROHIBIDO
    Decimal en este payload; transfer_tolerance_pct es float (porcentaje de
    configuracion, no dinero).

    Semantica REPLACE del JSONB completo: el PATCH de sistema persiste
    exactamente las claves enviadas — un payload con subset BORRA el resto.
    El operador manda siempre el dict completo (runbook post-deploy E1).
    Claves ausentes/null -> get_org_setting retorna el default.

    strict=True: sin coercion lax ("yes" NO es bool, "30" NO es int) — ni
    claves desconocidas ni tipos basura llegan al JSONB (D3).
    """
    model_config = ConfigDict(extra="forbid", strict=True)

    kg_ledger_enabled: bool | None = None
    two_step_transfers_enabled: bool | None = None
    internal_maquila_enabled: bool | None = None
    transfer_tolerance_pct: float | None = Field(
        None, ge=0, le=1,
        description="Tolerancia despachado vs recibido en traslados (0.05 = 5%)",
    )
    intersede_stale_days: int | None = Field(
        None, ge=1,
        description="Dias sin movimiento para alertar saldo intersede huerfano",
    )
    aging_buckets: list[int] | None = Field(
        None,
        description="Cortes de antiguedad para cartera y deuda kg (ej [30,60,90])",
    )
    # SAC E2 (D12): lista de centros de distribucion Willard — "extensible sin
    # migracion" (v0.5 §6.5); el inbound valida pertenencia contra esta lista
    willard_distribution_centers: list[str] | None = Field(
        None,
        description="Centros de distribucion Willard validos en la recepcion (ej ['baq','bog','monteria'])",
    )
    # SAC Ciclo B (B2): sedes deterministas Willard — warehouse IDs como STR
    # (JSON-nativo H1; UUID no es tipo JSON). None = sin configurar -> no valida.
    willard_sede_drosses: str | None = Field(
        None,
        description="Warehouse ID (str) de la planta de drosses — la recepcion drosses valida contra esta bodega (Q-03: Juan Mina)",
    )
    willard_sede_postconsumo_default: str | None = Field(
        None,
        description="Warehouse ID (str) default del selector en recepcion postconsumo (Q-05: Circunvalar); editable entre sedes con cuenta de baterias",
    )


class OrganizationBase(BaseModel):
    """Base organization schema with common attributes."""
    name: str = Field(..., min_length=2, max_length=255)


class OrganizationCreate(OrganizationBase):
    """Schema for creating a new organization."""
    slug: str | None = Field(None, min_length=2, max_length=100)

    @field_validator('slug')
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        if v is not None:
            if not re.match(r'^[a-z0-9-]+$', v):
                raise ValueError('Slug must contain only lowercase letters, numbers, and hyphens')
        return v


class OrganizationUpdate(BaseModel):
    """Schema for updating an organization."""
    name: str | None = Field(None, min_length=2, max_length=255)
    logo_url: str | None = Field(None, max_length=500)
    max_users: int | None = Field(None, ge=1, le=1000)


class OrganizationResponse(OrganizationBase):
    """Schema for organization response."""
    id: UUID
    slug: str
    logo_url: str | None = None
    subscription_plan: str
    subscription_status: str
    max_users: int
    is_active: bool = True
    created_at: datetime
    member_role: str | None = None  # User's role display name in this organization
    settings: dict | None = None  # Flags/parametros SAC (D3) — model_validate lo propaga solo

    class Config:
        from_attributes = True


class OrganizationMemberCreate(BaseModel):
    """Schema for adding a member to an organization."""
    user_id: UUID
    role_id: UUID


class OrganizationMemberUpdate(BaseModel):
    """Schema for updating a member's role."""
    role_id: UUID


class OrganizationMemberResponse(BaseModel):
    """Schema for organization member response with user details."""
    id: UUID
    user_id: UUID
    organization_id: UUID
    role_id: UUID
    role_name: str | None = None
    role_display_name: str | None = None
    joined_at: datetime
    user_email: str | None = None
    user_full_name: str | None = None
    account_ids: list[UUID] = []
    org_count: int = 1

    class Config:
        from_attributes = True


class AccountAssignmentsUpdate(BaseModel):
    """Schema para actualizar cuentas asignadas a un usuario."""
    account_ids: list[UUID] = []


class CreateUserWithMembership(BaseModel):
    """Schema para crear usuario nuevo con membership en la org."""
    email: EmailStr
    full_name: str
    role_id: UUID
