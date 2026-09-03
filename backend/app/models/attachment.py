"""
Modelo Attachment — archivos adjuntos de operaciones.

Pedido del cliente via Bascula: adjuntar VARIOS archivos a compras, ventas y
transformaciones (evidencias de la calidad del material, remisiones).

Convive con `MoneyMovement.evidence_url` (un archivo, Tesoreria) por decision
explicita del cliente: "que convivan las dos y unificamos despues". La
unificacion futura es UNA columna `money_movement_id` mas, no un rediseno.

D1 — el dueno se modela con FKs nullables + CHECK, NO con un par polimorfico
`(entity_type, entity_id)`. Es el precedente del repo (`inventory_adjustments`
gano `transfer_id` #84, `inbound_order_id` #93 y `willard_delivery_id` #100 de
esta misma forma) y hace que "exactamente un dueno" sea imposible de violar por
construccion en vez de algo que se vigile.

D2 — se persiste el nombre ORIGINAL. Tesoreria guarda solo la ruta y el archivo
en disco se llama `{movement_id}_{timestamp}.ext`: el nombre que el usuario le
dio se pierde. Para una remision ("remision-4471.pdf") ese nombre ES el dato.

D5 — el nombre en disco lo genera el servidor (`{uuid4}.{ext}`), nunca el
usuario: `original_filename` viaja en la BD y solo se usa como `filename=` de
la descarga. Path traversal queda cerrado por construccion.
"""
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.material_transformation import MaterialTransformation
    from app.models.purchase import Purchase
    from app.models.sale import Sale


# Modulos que hoy aceptan adjuntos. La tupla es la fuente unica: el servicio
# deriva de aca la columna FK y los permisos de cada uno.
ATTACHMENT_OWNERS = ("purchase", "sale", "transformation")

OWNER_COLUMN = {
    "purchase": "purchase_id",
    "sale": "sale_id",
    "transformation": "transformation_id",
}


class Attachment(Base, OrganizationMixin, TimestampMixin):
    """Un archivo adjunto a una compra, una venta o una transformacion."""

    __tablename__ = "attachments"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    purchase_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("purchases.id", ondelete="CASCADE"), nullable=True
    )
    sale_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("sales.id", ondelete="CASCADE"), nullable=True
    )
    transformation_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("material_transformations.id", ondelete="CASCADE"),
        nullable=True,
    )

    file_path: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="Ruta relativa a UPLOAD_DIR"
    )
    original_filename: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Nombre que le dio el usuario (D2)"
    )
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    description: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="Etiqueta libre: 'Remision 4471', 'Foto humedad'"
    )

    uploaded_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    purchase: Mapped[Optional["Purchase"]] = relationship("Purchase")
    sale: Mapped[Optional["Sale"]] = relationship("Sale")
    transformation: Mapped[Optional["MaterialTransformation"]] = relationship(
        "MaterialTransformation"
    )

    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN purchase_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN sale_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN transformation_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="ck_attachments_exactly_one_owner",
        ),
        Index("ix_attachments_purchase_id", "purchase_id"),
        Index("ix_attachments_sale_id", "sale_id"),
        Index("ix_attachments_transformation_id", "transformation_id"),
    )

    def __repr__(self) -> str:
        return f"<Attachment {self.original_filename} ({self.size_bytes} bytes)>"
