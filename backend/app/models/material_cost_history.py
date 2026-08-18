"""
Historial de cambios de costo promedio de materiales.

APPEND-ONLY PURO (#66): cada cambio al current_average_cost escribe un
registro; las reversiones escriben EL SUYO, nunca borran el original. Ya no
existe rewind ni bloqueo por operaciones posteriores (superseded #9/#40).

Consumidores: invariante "avg == ultimo MCH" (stress walk), valuacion
historica _get_inventory_as_of (#41/H2), display avg_cost_after (#83).
previous_stock/new_stock son solo auditoria.
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, GUID

if TYPE_CHECKING:
    from app.models.material import Material


class MaterialCostHistory(Base, TimestampMixin):
    """
    Registro de cada cambio al costo promedio de un material.

    Catalogo COMPLETO de source_type — 12 valores (#93 A4: mantener esta lista
    sincronizada con la realidad; la deriva documental es como se pierden las
    lecciones).

    6 OPERATIVOS:
    - purchase_liquidation: liquidacion de compra (fecha = dia de liquidacion #61c)
    - adjustment_increase: ajuste de inventario tipo aumento
    - transformation_in / transformation_out: destino/origen de transformacion
    - inbound_receipt: recepcion Willard (SAC E2 — identidad D2, checkpoint HOY)
    - inbound_discrepancy: descuadre de entrada valorado a precio de referencia
      (#93 D7 fix 3 — decrease con unit_cost_override; OPERATIVO, NO entra a
      MCH_FASE5_REVERSAL_TYPES por decision A5, fecha = dia de liquidacion D21)

    6 REVERSIONES (escriben su registro; el original nunca se borra):
    - sale_cancellation: reingreso ponderado al cancelar venta liquidada (#65;
      condicional — solo si el avg cambio; FUERA de MCH_FASE5_REVERSAL_TYPES:
      su original nunca escribio MCH, ver dualidad H2 en reports)
    - purchase_cancellation | adjustment_annulment | transformation_annulment
      (Fase 5 #66) e inbound_annulment (SAC E2): en MCH_FASE5_REVERSAL_TYPES
    - purchase_unliquidation: reversa de liquidacion SIN cancelar (#93 D20 —
      la compra vuelve a 'registered'; en MCH_FASE5_REVERSAL_TYPES; el
      purchase_liquidation original PERMANECE en los cortes por decision D20b)
    """
    __tablename__ = "material_cost_histories"

    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid4,
    )

    organization_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    material_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Costo antes y despues de la operacion
    previous_cost: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        comment="Costo promedio ANTES de la operacion (se usa para reversal)",
    )

    new_cost: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        comment="Costo promedio DESPUES de la operacion",
    )

    # Contexto de stock (solo auditoria, NO se usa en reversal)
    previous_stock: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        comment="Stock al momento del cambio (solo auditoria/debugging)",
    )

    new_stock: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        comment="Stock despues del cambio (solo auditoria/debugging)",
    )

    # Origen del cambio — catalogo completo en el docstring de la clase (12).
    # El historial es append-only: revertir una operacion escribe su propio
    # registro en vez de borrar el original.
    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="6 operativos (purchase_liquidation, adjustment_increase, "
                "transformation_in/out, inbound_receipt, inbound_discrepancy) + "
                "6 reversiones (sale_cancellation, purchase_cancellation, "
                "adjustment_annulment, transformation_annulment, inbound_annulment, "
                "purchase_unliquidation) — ver docstring",
    )

    source_id: Mapped[UUID] = mapped_column(
        GUID(),
        nullable=False,
        comment="ID de la compra, ajuste o transformacion que causo el cambio",
    )

    # Fecha de negocio de la operacion (para costo promedio historico)
    transaction_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Fecha de negocio de la operacion (business date, no timestamp servidor)",
    )

    # Relationships
    material: Mapped["Material"] = relationship(
        "Material",
        back_populates="cost_history",
    )

    __table_args__ = (
        Index("ix_mch_org_material", "organization_id", "material_id"),
        Index("ix_mch_source", "source_type", "source_id"),
    )
