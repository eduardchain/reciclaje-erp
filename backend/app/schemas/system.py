"""Schemas para endpoints de super admin (/system/)."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.schemas.organization import OrgSettingsPayload


# --- Organizaciones ---

class SystemOrgCreate(BaseModel):
    """Crear organizacion desde panel de sistema."""
    name: str = Field(..., min_length=2, max_length=255)
    admin_email: EmailStr
    admin_full_name: str | None = Field(None, max_length=255)


class SystemOrgUpdate(BaseModel):
    """Actualizar organizacion desde panel de sistema.

    `settings` (SAC E1, D3): payload tipado con semantica REPLACE — el PATCH
    persiste exactamente las claves enviadas y borra las demas; mandar
    SIEMPRE el dict completo. Escritura solo superuser (guard del router).
    """
    name: str | None = Field(None, min_length=2, max_length=255)
    max_users: int | None = Field(None, ge=1, le=1000)
    subscription_plan: str | None = None
    subscription_status: str | None = None
    is_active: bool | None = None
    settings: OrgSettingsPayload | None = None


class SystemOrgResponse(BaseModel):
    """Organizacion con datos extra para super admin."""
    id: UUID
    name: str
    slug: str
    subscription_plan: str
    subscription_status: str
    max_users: int
    is_active: bool
    member_count: int = 0
    created_at: datetime
    settings: dict | None = None

    class Config:
        from_attributes = True


# --- Usuarios ---

class SystemUserMembership(BaseModel):
    """Membership de un usuario en una org."""
    organization_id: UUID
    organization_name: str
    role_name: str
    role_display_name: str


class ResetPasswordRequest(BaseModel):
    """Reseteo de contrasena por superusuario (D1).

    NO exige la clave actual — ese es justamente el punto: el usuario que
    olvido su clave no puede usar /auth/change-password. La clave la provee
    el operador y NUNCA vuelve en el response (ni se escribe en logs, D5/H3).

    min_length=6 es calco literal de ChangePassword.new_password: misma
    politica de claves, cero drift. Si alguna vez se endurece, se endurece
    en AMBOS schemas a la vez (H4 del micro-QA).
    """
    new_password: str = Field(..., min_length=6)


class SystemUserResponse(BaseModel):
    """Usuario con sus memberships para super admin."""
    id: UUID
    email: str
    full_name: str | None
    is_active: bool
    is_superuser: bool
    created_at: datetime
    memberships: list[SystemUserMembership] = []

    class Config:
        from_attributes = True


class AddUserToOrgRequest(BaseModel):
    """Agregar usuario existente a una organizacion."""
    organization_id: UUID
    role_id: UUID
