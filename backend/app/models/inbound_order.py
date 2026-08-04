"""
Modelos InboundOrder / InboundOrderLine — orden de entrada (SAC E1, v0.5 §11.1.12).

Documento central de la "captura unica" de Fase 1: cubre compra propia,
postconsumo Willard, drosses, recoleccion en ruta y reventa. Las compras
derivan de ella (una InboundOrder de compra propia genera su Purchase en
'registered' — logica de E2; E1 solo crea la estructura).
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.fleet import Driver, Vehicle
    from app.models.material import Material
    from app.models.purchase import Purchase
    from app.models.third_party import ThirdParty
    from app.models.warehouse import Warehouse


class InboundOrder(Base, OrganizationMixin, TimestampMixin):
    """Orden de entrada — captura unica en patio."""

    __tablename__ = "inbound_orders"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    order_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Consecutivo por org (patron sequential numbering del repo)",
    )

    inbound_type: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        comment="purchase | willard (CC-004: colapso 4->2; el ruteo kg es por-linea "
        "segun willard_world del material)",
    )

    warehouse_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Sede de recepcion fisica — inmutable post-registro (v0.5 §7.2)",
    )

    third_party_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("third_parties.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Proveedor real (una entrada POR proveedor, v0.5 §7.3)",
    )

    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Fecha de negocio — BusinessDate mediodia UTC via schema",
    )

    driver_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True
    )

    vehicle_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True
    )

    # SAC Ciclo D: recolector (service_provider) — se registra en AMBOS tipos
    # (Green Loop tambien recolecta willard, Q-02). En willard es informativo;
    # la comision existe SOLO al liquidar compras regulares y se causa como
    # GASTO (expense_accrual) — jamas entra al prorrateo de costo #30.
    collector_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("third_parties.id", ondelete="SET NULL"),
        nullable=True,
        comment="Recolector (service_provider) — informativo en willard; en compras la comision se causa como gasto al liquidar",
    )

    willard_distribution_center: Mapped[Optional[str]] = mapped_column(
        String(24),
        nullable=True,
        comment="Informativo (v0.5 §6.5)",
    )

    # Columna INERTE desde Ciclo B (B4, Q-03: peso muerto) — fuera de schemas
    # y UI; se conserva por la regla "migraciones sin DROP"
    goes_directly_to_jm: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Drosses directo BOG->JM (v0.5 §7.3)",
    )

    # Ciclo B addendum (feedback pruebas Daniel): nota informativa de cabecera
    # — captura libre en patio, editable en ambos tipos (sin efectos)
    notes: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
        comment="Nota informativa de la captura en patio",
    )

    # Ajustes reunion 2026-08-03 (A, D1): factura de la captura — SOLO tipo
    # willard. En tipo compra la factura vive en purchases.invoice_number (el
    # documento comercial) y esta columna queda NULL: una sola fuente de verdad
    # POR TIPO, jamas dos para la misma fila. La lectura del response es
    # condicional (purchase si existe, si no esta columna).
    invoice_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Factura de recepciones Willard (tipo compra: vive en purchases.invoice_number)",
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="draft",
        comment="draft | confirmed | annulled",
    )

    # SAC E2 (espejo migracion e8f1a2b3c4d5)
    purchase_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("purchases.id", ondelete="SET NULL"),
        nullable=True,
        comment="Purchase(registered) derivada para tipos purchase/ruta (D7)",
    )

    annul_cost_adjustment: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
        comment="Diferencia de remocion ponderada al anular (D8, patron #66) — 8a fuente linea P&L oversell",
    )

    annulled_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    annulled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    annulled_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "order_number", name="uq_inbound_orders_org_number"),
    )

    # --- Relationships ---
    warehouse: Mapped["Warehouse"] = relationship("Warehouse", foreign_keys=[warehouse_id])
    third_party: Mapped["ThirdParty"] = relationship("ThirdParty", foreign_keys=[third_party_id])
    collector: Mapped[Optional["ThirdParty"]] = relationship("ThirdParty", foreign_keys=[collector_id])
    driver: Mapped[Optional["Driver"]] = relationship("Driver", foreign_keys=[driver_id])
    vehicle: Mapped[Optional["Vehicle"]] = relationship("Vehicle", foreign_keys=[vehicle_id])
    purchase: Mapped[Optional["Purchase"]] = relationship("Purchase", foreign_keys=[purchase_id])
    lines: Mapped[list["InboundOrderLine"]] = relationship(
        "InboundOrderLine",
        back_populates="inbound_order",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<InboundOrder #{self.order_number} {self.inbound_type} ({self.status})>"


class InboundOrderLine(Base, OrganizationMixin, TimestampMixin):
    """Linea de orden de entrada: material, cantidad, peso bascula, calidad."""

    __tablename__ = "inbound_order_lines"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    inbound_order_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("inbound_orders.id", ondelete="CASCADE"),
        nullable=False,
    )

    material_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=False,
    )

    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)

    unit: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="Snapshot de la unidad al capturar (kg | unidad)",
    )

    # SAC E2 (espejo migracion e8f1a2b3c4d5)
    unit_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="Precio de captura opcional (tipos purchase; el definitivo lo fija la liquidacion §7.2)",
    )

    unit_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="Snapshot del costo promedio de entrada (tipos Willard, D8 — la reversa exacta lee de aca)",
    )

    scale_weight_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 4),
        nullable=True,
        comment="Peso de bascula cuando la cantidad viene en otra unidad",
    )

    quality_notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        Index("ix_inbound_order_lines_order", "inbound_order_id"),
    )

    # --- Relationships ---
    inbound_order: Mapped["InboundOrder"] = relationship(
        "InboundOrder", back_populates="lines"
    )
    material: Mapped["Material"] = relationship("Material", foreign_keys=[material_id])

    def __repr__(self) -> str:
        return f"<InboundOrderLine material={self.material_id} qty={self.quantity}>"
