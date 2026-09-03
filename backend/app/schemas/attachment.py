"""Schemas de Attachment — adjuntos de compras, ventas y transformaciones."""
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AttachmentOwner = Literal["purchase", "sale", "transformation"]


class AttachmentResponse(BaseModel):
    """Un adjunto. El contenido se pide aparte, por `/attachments/{id}/download`."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_type: AttachmentOwner
    owner_id: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    description: Optional[str] = None
    uploaded_by: Optional[UUID] = None
    uploaded_by_name: Optional[str] = None
    created_at: datetime


class AttachmentListResponse(BaseModel):
    items: list[AttachmentResponse]
    total: int


class AttachmentUpdate(BaseModel):
    """Solo la etiqueta es editable: el archivo se reemplaza borrando y subiendo."""

    description: Optional[str] = Field(None, max_length=200)
