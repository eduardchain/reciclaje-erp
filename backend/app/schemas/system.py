"""Schemas para endpoints de super admin (/system/)."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# --- Organizaciones ---

class SystemOrgCreate(BaseModel):
    """Crear organizacion desde panel de sistema."""
    name: str = Field(..., min_length=2, max_length=255)
    admin_email: EmailStr
    admin_full_name: str | None = Field(None, max_length=255)


class SystemOrgUpdate(BaseModel):
    """Actualizar organizacion desde panel de sistema."""
    name: str | None = Field(None, min_length=2, max_length=255)
    max_users: int | None = Field(None, ge=1, le=1000)
    subscription_plan: str | None = None
    subscription_status: str | None = None
    is_active: bool | None = None


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

    class Config:
        from_attributes = True


# --- Usuarios ---

class SystemUserMembership(BaseModel):
    """Membership de un usuario en una org."""
    organization_id: UUID
    organization_name: str
    role_name: str
    role_display_name: str


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
