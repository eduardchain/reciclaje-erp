"""
Modelo DocumentTax — IVA y retenciones de lo que SAC factura (CC-013 / Q-41).

Johana lo introdujo el 2026-09-18 asumiendo que el sistema ya lo hacia
("Al momento de facturar, pues ahi me permite agregar IVA, retencion, todo
eso, verdad?"). No lo hacia. Las dos facturas reales del 2026-09-22 (FE 2118
abono y FE 2127 venta) fijaron las reglas: IVA 19 % por linea, y tres
retenciones cuyas tarifas dependen del CONCEPTO y no del cliente — el mismo
cliente retiene 2,5 % vendiendole un bien y 4 % facturandole un servicio.

SEMANTICA (plan CC-013, D1): el sistema REGISTRA lo que Siigo emitio, no
emite. Los montos se capturan al liquidar con precalculo editable (patron #79)
y el `invoice_number` del documento amarra los dos mundos.

SIGNOS — son OPUESTOS entre el IVA y las retenciones, y por eso viven en un
mapa y no en un `if`:

    IVA generado    cliente +amount / entidad −amount   (se lo cobramos; se lo debemos a la DIAN)
    Retenciones     cliente −amount / entidad +amount   (nos la descuentan; queda a nuestro favor)

Con la FE 2127 el cliente termina debiendo 119.335.609,11, que es exactamente
el "Total a Pagar" impreso en la factura: conservacion por construccion, igual
que en las retenciones de compra (#75 D9).

DUENO UNICO (D3/D10): `sale_id` y `willard_delivery_id` nullables con CHECK de
exactamente uno — el precedente del repo (`attachments` #102, y las tres
columnas que fue ganando `inventory_adjustments` en #84, #93 y #100). Cuando la
Salida de Plomo deriva una venta hay DOS documentos para UNA factura, y el
dueno es la Salida: es el documento que el usuario liquida y el que conoce el
tipo y el concepto.

CERO EFECTO EN EL P&L (D7): el IVA no es ingreso y la retencion no es gasto.
`sale.total_amount` sigue siendo el subtotal, que es lo que el P&L lee.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.sale import Sale
    from app.models.willard_delivery import WillardDelivery


#: Tipos validos. `iva` es lo que cobramos; los otros tres son lo que nos retienen.
TAX_TYPES = ("iva", "retefuente", "reteiva", "ica")

#: Direccion del efecto sobre el TERCERO del documento (el cliente).
#: La entidad de impuestos recibe siempre el signo contrario.
#: ⚠️ Un solo mapa para los cuatro tipos: si esto se escribe como `if tipo ==
#: "iva"` en cada consumidor, el dia que entre un tipo nuevo hay que acordarse
#: de todos los sitios. Es la leccion de la terna de signos (#67, #69, #86).
TAX_SIGN_ON_CUSTOMER = {
    "iva": 1,          # se lo cobramos ademas del subtotal
    "retefuente": -1,  # nos lo descuenta del pago
    "reteiva": -1,
    "ica": -1,
}


class DocumentTax(Base, OrganizationMixin, TimestampMixin):
    """Un impuesto registrado sobre una venta o una Salida de Plomo."""

    __tablename__ = "document_taxes"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    # --- Dueno: exactamente uno de los dos (CHECK abajo) ---
    sale_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("sales.id", ondelete="CASCADE"),
        nullable=True,
    )

    willard_delivery_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("willard_deliveries.id", ondelete="CASCADE"),
        nullable=True,
    )

    third_party_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("third_parties.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Entidad '[Impuestos] X' resuelta o creada al liquidar — el statement y la reversion leen de aca",
    )

    tax_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="iva | retefuente | reteiva | ica (Literal en el schema, patron #70)",
    )

    municipality: Mapped[Optional[str]] = mapped_column(
        String(60),
        nullable=True,
        comment="Obligatorio cuando tax_type='ica' (una entidad por municipio, #75 H4); prohibido en los demas",
    )

    concept: Mapped[Optional[str]] = mapped_column(
        String(60),
        nullable=True,
        comment="Concepto de la tarifa (venta de bien vs servicio) — las facturas muestran 2,5 % y 4 % del MISMO cliente",
    )

    rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(7, 4),
        nullable=True,
        comment="Tasa informativa con la que se precalculo. El monto editado es la verdad (#79 F1)",
    )

    base_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment=(
            "Base sobre la que se aplico, persistida SIEMPRE (D5). Sin esto una reteIVA "
            "configurada como '2,85 % del subtotal' daria el numero correcto solo mientras "
            "el IVA sea 19 %, y quedaria mal en silencio el dia que cambie"
        ),
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Monto del impuesto. Su signo sobre el cliente sale de TAX_SIGN_ON_CUSTOMER",
    )

    reverted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Poblado al cancelar la venta o anular la Salida (auditoria sin delete fisico, #75)",
    )

    __table_args__ = (
        CheckConstraint(
            "(sale_id IS NOT NULL)::int + (willard_delivery_id IS NOT NULL)::int = 1",
            name="ck_document_taxes_single_owner",
        ),
        CheckConstraint("amount > 0", name="ck_document_taxes_amount_positive"),
        CheckConstraint(
            "tax_type IN ('iva', 'retefuente', 'reteiva', 'ica')",
            name="ck_document_taxes_type",
        ),
        CheckConstraint(
            "(tax_type = 'ica') = (municipality IS NOT NULL)",
            name="ck_document_taxes_ica_municipality",
        ),
        Index("ix_document_taxes_sale", "sale_id"),
        Index("ix_document_taxes_delivery", "willard_delivery_id"),
    )

    # --- Relationships ---
    sale: Mapped[Optional["Sale"]] = relationship("Sale", back_populates="taxes")
    willard_delivery: Mapped[Optional["WillardDelivery"]] = relationship(
        "WillardDelivery", back_populates="taxes"
    )

    def __repr__(self) -> str:
        return f"<DocumentTax {self.tax_type} ${self.amount}>"
