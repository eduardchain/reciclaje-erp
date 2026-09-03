"""
Endpoints de adjuntos — compras, ventas y transformaciones.

Un router unico para los tres modulos. El dueno viaja como query param
(`purchase_id` | `sale_id` | `transformation_id`), exactamente uno.
"""
import mimetypes
import os
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_required_org_context
from app.core.config import settings
from app.schemas.attachment import (
    AttachmentListResponse,
    AttachmentResponse,
    AttachmentUpdate,
)
from app.services import attachment as attachment_service
from app.services.attachment import OWNER_PERMISSIONS

router = APIRouter()


def _check(org_context: dict, owner_type: str, action: str) -> None:
    """
    N1 — el guard NO puede ser una dependency estatica.

    `require_permission(...)` se evalua al declarar la ruta, pero aca el modulo
    dueno se conoce recien tras leer el query param (o cargar la fila). Un
    guard estatico dejaria los tres modulos gobernados por el permiso de uno
    solo — y los tests felices pasarian igual.

    Replica la semantica de `require_any_permission`, bypass de admin incluido
    (#29): admin pasa siempre.
    """
    if org_context["is_admin"]:
        return
    perms = OWNER_PERMISSIONS[owner_type][action]
    if not (set(perms) & org_context["user_permissions"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permisos insuficientes: se requiere {' o '.join(sorted(perms))}",
        )


def _resolve_owner(
    purchase_id: Optional[UUID],
    sale_id: Optional[UUID],
    transformation_id: Optional[UUID],
) -> tuple[str, UUID]:
    given = [
        ("purchase", purchase_id),
        ("sale", sale_id),
        ("transformation", transformation_id),
    ]
    present = [(t, i) for t, i in given if i is not None]
    if len(present) != 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Indique exactamente un dueno: purchase_id, sale_id o "
                "transformation_id"
            ),
        )
    return present[0]


@router.get("", response_model=AttachmentListResponse)
def list_attachments(
    purchase_id: Optional[UUID] = Query(None),
    sale_id: Optional[UUID] = Query(None),
    transformation_id: Optional[UUID] = Query(None),
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Adjuntos de una operacion."""
    owner_type, owner_id = _resolve_owner(purchase_id, sale_id, transformation_id)
    _check(org_context, owner_type, "view")
    items = attachment_service.list_for_owner(
        db, owner_type, owner_id, org_context["organization_id"]
    )
    return {"items": items, "total": len(items)}


@router.post("", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
def upload_attachment(
    file: UploadFile = File(...),
    purchase_id: Optional[UUID] = Form(None),
    sale_id: Optional[UUID] = Form(None),
    transformation_id: Optional[UUID] = Form(None),
    # max_length espeja String(200) del modelo: sin esto una nota larga pasa la
    # validacion, revienta en el INSERT y el usuario recibe un 500 por un dato suyo.
    description: Optional[str] = Form(None, max_length=200),
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Sube un adjunto (max 5MB, hasta 10 por operacion)."""
    owner_type, owner_id = _resolve_owner(purchase_id, sale_id, transformation_id)
    _check(org_context, owner_type, "upload")
    return attachment_service.create(
        db,
        owner_type=owner_type,
        owner_id=owner_id,
        file=file,
        description=description,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )


@router.get("/{attachment_id}/download")
def download_attachment(
    attachment_id: UUID,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Descarga el archivo. El nombre original (D2) viaja como filename."""
    att = attachment_service.get_or_404(
        db, attachment_id, org_context["organization_id"]
    )
    owner_type, _ = attachment_service.owner_of(att)
    _check(org_context, owner_type, "view")

    path = os.path.join(settings.UPLOAD_DIR, att.file_path)
    if not os.path.exists(path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archivo no encontrado en disco",
        )
    media_type = (
        att.content_type
        or mimetypes.guess_type(path)[0]
        or "application/octet-stream"
    )
    return FileResponse(path, media_type=media_type, filename=att.original_filename)


@router.patch("/{attachment_id}", response_model=AttachmentResponse)
def update_attachment(
    attachment_id: UUID,
    data: AttachmentUpdate,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Edita la etiqueta del adjunto (el archivo no se reemplaza: se borra y se sube)."""
    att = attachment_service.get_or_404(
        db, attachment_id, org_context["organization_id"]
    )
    owner_type, _ = attachment_service.owner_of(att)
    _check(org_context, owner_type, "upload")
    return attachment_service.update_description(
        db, attachment_id, org_context["organization_id"], data.description
    )


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(
    attachment_id: UUID,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """Borra un adjunto: la fila y el archivo del disco (N4)."""
    att = attachment_service.get_or_404(
        db, attachment_id, org_context["organization_id"]
    )
    owner_type, _ = attachment_service.owner_of(att)
    _check(org_context, owner_type, "delete")
    attachment_service.delete(db, attachment_id, org_context["organization_id"])
