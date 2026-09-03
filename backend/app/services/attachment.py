"""
Servicio de adjuntos — compras, ventas y transformaciones.

Un solo modulo para los tres: comparten el 100% de la mecanica (validar
extension, tamano y tope; escribir disco; borrar). Triplicarla garantiza que
diverjan, que es exactamente lo que le paso a la celda editable de las hojas
de precios.
"""
import os
import uuid as uuid_module
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.attachment import Attachment
from app.models.material_transformation import MaterialTransformation
from app.models.purchase import Purchase
from app.models.sale import Sale
from app.models.user import User

# Reusa el set de Tesoreria + HEIC/HEIF: el iPhone fotografia en HEIC por
# defecto y es justo el dispositivo del patio. Ver N2 del plan: si la
# compresion del navegador funciona lo que sube es JPEG, pero el crudo tiene
# que poder entrar igual.
ALLOWED_ATTACHMENT_EXTENSIONS = {
    "jpg", "jpeg", "png", "gif", "webp", "heic", "heif", "pdf",
}

# Tope por operacion (respuesta del cliente: "mantenlos").
MAX_ATTACHMENTS_PER_OWNER = 10

OWNER_MODELS = {
    "purchase": Purchase,
    "sale": Sale,
    "transformation": MaterialTransformation,
}

OWNER_COLUMNS = {
    "purchase": Attachment.purchase_id,
    "sale": Attachment.sale_id,
    "transformation": Attachment.transformation_id,
}

OWNER_LABELS = {
    "purchase": "compra",
    "sale": "venta",
    "transformation": "transformacion",
}

# N1 — el permiso depende del modulo dueno, que se conoce en runtime (por el
# query param o por la fila), NO al declarar la ruta. Por eso el guard vive
# dentro del endpoint y lee este mapa; un `require_permission` estatico en el
# decorador dejaria los tres modulos gobernados por el permiso de uno solo.
#
# GAP-1 — subir y borrar NO son el mismo acto: el rol `bascula` tiene
# `.create` pero no `.edit`, y es quien esta en el patio con el material
# enfrente. La regla del cliente ("borra quien puede editar") se respeta en el
# borrado; subir admite tambien a quien crea la operacion.
# Editar la NOTA usa el verbo `upload`, no `delete`: es metadato de la subida,
# no destruccion. Consecuencia asumida y deliberada: la bascula puede corregir
# la nota de un adjunto que subio el liquidador y viceversa. Con la camara en
# el patio y el nombre del archivo puesto por el celular, poder etiquetar lo
# que uno ve vale mas que la exclusividad.
OWNER_PERMISSIONS = {
    "purchase": {
        "view": ("purchases.view",),
        "upload": ("purchases.create", "purchases.edit"),
        "delete": ("purchases.edit",),
    },
    "sale": {
        "view": ("sales.view",),
        "upload": ("sales.create", "sales.edit"),
        "delete": ("sales.edit",),
    },
    "transformation": {
        # El catalogo no tiene `transformations.edit` (una transformacion no se
        # edita: se anula), asi que ambos verbos caen en `.create`.
        "view": ("transformations.view",),
        "upload": ("transformations.create",),
        "delete": ("transformations.create",),
    },
}


def owner_of(att: Attachment) -> tuple[str, UUID]:
    """Deriva (tipo, id) del dueno. El CHECK garantiza que hay exactamente uno."""
    if att.purchase_id is not None:
        return "purchase", att.purchase_id
    if att.sale_id is not None:
        return "sale", att.sale_id
    return "transformation", att.transformation_id


def validate_owner_exists(db: Session, owner_type: str, owner_id: UUID, organization_id: UUID):
    """El dueno debe existir y ser de la organizacion (multi-tenancy)."""
    model = OWNER_MODELS[owner_type]
    obj = db.execute(
        select(model).where(
            model.id == owner_id, model.organization_id == organization_id
        )
    ).scalar_one_or_none()
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontro la {OWNER_LABELS[owner_type]}",
        )
    return obj


def _uploader_names(db: Session, atts: list[Attachment]) -> dict[UUID, str]:
    """Nombre de quien subio, en UNA query para toda la lista (sin N+1)."""
    ids = {a.uploaded_by for a in atts if a.uploaded_by}
    if not ids:
        return {}
    rows = db.execute(select(User.id, User.full_name).where(User.id.in_(ids))).all()
    return {r[0]: r[1] for r in rows}


def to_response(att: Attachment, names: dict[UUID, str] | None = None) -> dict:
    owner_type, owner_id = owner_of(att)
    return {
        "id": att.id,
        "owner_type": owner_type,
        "owner_id": owner_id,
        "original_filename": att.original_filename,
        "content_type": att.content_type,
        "size_bytes": att.size_bytes,
        "description": att.description,
        "uploaded_by": att.uploaded_by,
        "uploaded_by_name": (names or {}).get(att.uploaded_by),
        "created_at": att.created_at,
    }


def list_for_owner(
    db: Session, owner_type: str, owner_id: UUID, organization_id: UUID
) -> list[dict]:
    validate_owner_exists(db, owner_type, owner_id, organization_id)
    col = OWNER_COLUMNS[owner_type]
    atts = list(
        db.execute(
            select(Attachment)
            .where(col == owner_id, Attachment.organization_id == organization_id)
            .order_by(Attachment.created_at)
        ).scalars()
    )
    names = _uploader_names(db, atts)
    return [to_response(a, names) for a in atts]


# D7 — si algun dia se pide un clip con el conteo en el LISTADO de compras o
# ventas, se resuelve con una segunda query `WHERE <owner>_id IN (ids de la
# pagina)`, JAMAS con un outerjoin: la relacion es 1:N y el join duplicaria
# filas rompiendo la paginacion (trampa de #89, re-aprendida en #93 R2). No se
# deja el helper escrito porque v1 es solo el detalle y el codigo sin uso ni
# test es deuda; son ocho lineas cuando haga falta.


def get_or_404(db: Session, attachment_id: UUID, organization_id: UUID) -> Attachment:
    att = db.execute(
        select(Attachment).where(
            Attachment.id == attachment_id,
            Attachment.organization_id == organization_id,
        )
    ).scalar_one_or_none()
    if att is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Adjunto no encontrado"
        )
    return att


def create(
    db: Session,
    *,
    owner_type: str,
    owner_id: UUID,
    file: UploadFile,
    description: Optional[str],
    organization_id: UUID,
    user_id: Optional[UUID],
) -> dict:
    """
    Sube un adjunto.

    Sin guard de estado a proposito: se puede adjuntar a una operacion
    liquidada o cancelada (respuesta del cliente). La factura o la foto de
    calidad llegan tarde, y bloquearlas obligaria a anular la operacion.
    """
    validate_owner_exists(db, owner_type, owner_id, organization_id)

    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if file.filename else ""
    if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Tipo de archivo no permitido. Extensiones validas: "
                f"{', '.join(sorted(ALLOWED_ATTACHMENT_EXTENSIONS))}"
            ),
        )

    content = file.file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"El archivo excede el tamano maximo de "
                f"{settings.MAX_UPLOAD_SIZE // (1024 * 1024)}MB"
            ),
        )

    col = OWNER_COLUMNS[owner_type]
    current = db.execute(
        select(func.count(Attachment.id)).where(
            col == owner_id, Attachment.organization_id == organization_id
        )
    ).scalar_one()
    if current >= MAX_ATTACHMENTS_PER_OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"La {OWNER_LABELS[owner_type]} ya tiene {current} adjuntos "
                f"(maximo {MAX_ATTACHMENTS_PER_OWNER}). Elimine alguno para subir otro."
            ),
        )

    # D5 — el nombre en disco lo genera el servidor. El nombre del usuario NUNCA
    # toca la ruta: asi un "../../etc/passwd" no puede escapar del directorio.
    org_dir = os.path.join(settings.UPLOAD_DIR, "attachments", str(organization_id))
    os.makedirs(org_dir, exist_ok=True)
    stored_name = f"{uuid_module.uuid4()}.{ext}"
    with open(os.path.join(org_dir, stored_name), "wb") as f:
        f.write(content)

    att = Attachment(
        organization_id=organization_id,
        file_path=f"attachments/{organization_id}/{stored_name}",
        original_filename=(file.filename or stored_name)[:255],
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
        description=description,
        uploaded_by=user_id,
        **{OWNER_COLUMNS[owner_type].key: owner_id},
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return to_response(att, _uploader_names(db, [att]))


def delete(db: Session, attachment_id: UUID, organization_id: UUID) -> None:
    """
    N4 — borra la fila Y el archivo del disco.

    Si el `os.remove` falla porque el archivo ya no esta, la fila se borra
    igual: el estado deseado es "no existe".
    """
    att = get_or_404(db, attachment_id, organization_id)
    path = os.path.join(settings.UPLOAD_DIR, att.file_path)
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
    db.delete(att)
    db.commit()


def update_description(
    db: Session, attachment_id: UUID, organization_id: UUID, description: Optional[str]
) -> dict:
    att = get_or_404(db, attachment_id, organization_id)
    att.description = description
    db.commit()
    db.refresh(att)
    return to_response(att, _uploader_names(db, [att]))
