from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
import re


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
            # Validate slug format: lowercase, hyphens, alphanumeric
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
    created_at: datetime
    member_role: str | None = None  # User's role in this organization
    
    class Config:
        from_attributes = True


class OrganizationMemberCreate(BaseModel):
    """Schema for adding a member to an organization."""
    user_id: UUID
    role: str = Field(..., pattern=r'^(admin|manager|accountant|user|viewer)$')
    
    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid_roles = ['admin', 'manager', 'accountant', 'user', 'viewer']
        if v not in valid_roles:
            raise ValueError(f'Role must be one of: {", ".join(valid_roles)}')
        return v


class OrganizationMemberUpdate(BaseModel):
    """Schema for updating a member's role."""
    role: str = Field(..., pattern=r'^(admin|manager|accountant|user|viewer)$')
    
    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid_roles = ['admin', 'manager', 'accountant', 'user', 'viewer']
        if v not in valid_roles:
            raise ValueError(f'Role must be one of: {", ".join(valid_roles)}')
        return v


class OrganizationMemberResponse(BaseModel):
    """Schema for organization member response with user details."""
    id: UUID
    user_id: UUID
    organization_id: UUID
    role: str
    joined_at: datetime
    user_email: str | None = None
    user_full_name: str | None = None
    
    class Config:
        from_attributes = True
