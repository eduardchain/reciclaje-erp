"""
Modelo PurchaseRetention — retenciones tributarias al liquidar compras (SAC E2, D9).

Estructura Fase 1 del handoff H6 (v0.5 §7.2: "la estructura queda preparada desde
Fase 1"; §18.2: tasas por tipo de proveedor = CONFIG-ARRANQUE, captura manual).

Semantica (plan-sac-e2-kgledger-inbound.md D9): al liquidar, el proveedor recibe
credito por (total − Σ retenciones) y cada retencion acredita a un tercero de
sistema "[Retenciones] {tipo}" con categoria liability — el pasivo total se
conserva al peso. Cero efecto en P&L y en costo del material. ICA es POR
MUNICIPIO (Johana 2026-07-16): municipality obligatorio en ica, prohibido en
retefuente/reteiva. Cancelar la compra revierte y marca reverted_at (auditoria
sin delete fisico).
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.purchase import Purchase


class PurchaseRetention(Base, OrganizationMixin, TimestampMixin):
    """Retencion tributaria aplicada en la liquidacion de una compra."""

    __tablename__ = "purchase_retentions"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    purchase_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("purchases.id", ondelete="CASCADE"),
        nullable=False,
    )

    third_party_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("third_parties.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Entidad de retencion '[Retenciones] X' (resuelta/creada al liquidar) — el statement y el revert leen de aca",
    )

    retention_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="ica | retefuente | reteiva (Literal en schema, patron #70)",
    )

    municipality: Mapped[Optional[str]] = mapped_column(
        String(60),
        nullable=True,
        comment="Obligatorio cuando retention_type='ica' (entidad por municipio, Johana 2026-07-16); prohibido en los demas",
    )

    rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(7, 4),
        nullable=True,
        comment="Tasa informativa (la tabla oficial llega del contador SAC — CONFIG-ARRANQUE)",
    )

    base: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2), nullable=True, comment="Base informativa"
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Monto retenido — resta del credito al proveedor, acredita a la entidad",
    )

    reverted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Poblado al cancelar la compra (auditoria sin delete fisico)",
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_purchase_retentions_amount_positive"),
        Index("ix_purchase_retentions_purchase", "purchase_id"),
    )

    # --- Relationships ---
    purchase: Mapped["Purchase"] = relationship(
        "Purchase", back_populates="retentions"
    )

    def __repr__(self) -> str:
        return f"<PurchaseRetention {self.retention_type} ${self.amount}>"
