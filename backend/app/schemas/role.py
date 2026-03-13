"""Schemas para roles y permisos."""
from uuid import UUID
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field


# === PERMISSION ===


class PermissionResponse(BaseModel):
    id: UUID
    code: str
    display_name: str
    module: str
    description: Optional[str] = None
    sort_order: int

    class Config:
        from_attributes = True


class PermissionsByModule(BaseModel):
    """Permisos agrupados por modulo para UI."""
    module: str
    module_display: str
    permissions: list[PermissionResponse]


# === ROLE ===


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    display_name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    permission_codes: list[str] = Field(
        default_factory=list,
        description="Lista de codigos de permisos a asignar",
    )


class RoleUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    permission_codes: Optional[list[str]] = Field(
        None, description="Lista de codigos de permisos"
    )


class RoleResponse(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    display_name: str
    description: Optional[str] = None
    is_system_role: bool
    created_at: datetime
    updated_at: datetime
    permissions: list[PermissionResponse] = []

    class Config:
        from_attributes = True


class RoleListItem(BaseModel):
    """Item para listar roles con conteos."""
    id: UUID
    name: str
    display_name: str
    description: Optional[str] = None
    is_system_role: bool
    permission_count: int
    member_count: int


# === ASSIGNMENT ===


class UserRoleAssignment(BaseModel):
    user_id: UUID
    role_id: UUID


class MyPermissionsResponse(BaseModel):
    """Permisos del usuario actual."""
    role_id: UUID
    role_name: str
    role_display_name: str
    is_admin: bool
    permissions: list[str]
