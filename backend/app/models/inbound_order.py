"""
Modelos InboundOrder / InboundOrderLine / InboundLineAllocation /
InboundOrderPurchase — orden de entrada (SAC E1 §11.1.12, rediseño #93).

Documento central de la "captura unica" en patio. Desde #93 la Entrada tipo
compra NO conoce el proveedor al capturar (en el patio nadie sabe todavia de
quien es el material): el proveedor aparece al LIQUIDAR, cuando el reparto
(InboundLineAllocation) distribuye cada linea entre N proveedores y de ahi
nacen N compras atomicamente (puente InboundOrderPurchase). La diferencia
entre lo pesado y lo repartido es el descuadre de entrada (D5-D7).
Willard intacto (D13): sigue con proveedor fijo y flujo 2 pasos (#81).
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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

    # #93 D1: nullable — la Entrada tipo compra se captura SIN proveedor (el
    # reparto al liquidar lo asigna por linea). Willard lo sigue exigiendo,
    # pero en el SERVICIO (titular de la cuenta kg, addendum Ciclo B), no aca.
    third_party_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("third_parties.id", ondelete="RESTRICT"),
        nullable=True,
        comment="Willard: titular de la cuenta kg. Tipo compra: NULL desde #93 (el proveedor vive en el reparto)",
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
    # willard. En tipo compra la factura vive POR PROVEEDOR (#93 D12: en el
    # reparto — InboundLineAllocation.invoice_number; legacy 1:1 en
    # purchases.invoice_number). Una sola fuente de verdad POR TIPO.
    invoice_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Factura de recepciones Willard (tipo compra: vive en el reparto por proveedor, #93 D12)",
    )

    # #93 D12: remision del camion — UNA por Entrada, se captura en el patio.
    # NO confundir con la factura (que llega con la liquidacion, por proveedor).
    # Columna propia y no invoice_number reciclada: #87 acaba de pagar el costo
    # de un campo con dos semanticas.
    remission_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Remision del camion (documento de patio, D12) — una por entrada",
    )

    # #93 D4: el estado es COLUMNA, ya no se deriva de las compras (se cayo el
    # espejo SQL<->Python del Ciclo C). Vocabularios por tipo:
    #   compra : draft (registrada) -> reviewed (revisada) -> liquidated | annulled
    #   willard: draft (registrada) -> confirmed (liquidada en display) | annulled
    # 'confirmed' queda EXCLUSIVO de willard; las filas legacy tipo compra las
    # re-mapea la migracion b8c9d0e1f2a3 desde el estado de su compra derivada.
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="draft",
        comment="draft | reviewed | liquidated | confirmed (solo willard) | annulled",
    )

    # #93 D10: quien reviso (permiso purchases.review) — auditoria minima
    reviewed_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Hora REAL del clic de liquidar (pruebas de usuario 2026-08-11). No se
    # confunde con `Purchase.liquidated_at`, que es fecha de NEGOCIO (mediodia
    # UTC, #42/#87) y es por donde cortan los reportes. La hora vive aca y no
    # en las 3 tablas compartidas de operaciones porque inbound_orders es
    # exclusiva de SAC: cero riesgo para las otras organizaciones (la deuda
    # declarada en #87 sigue abierta para compras/ventas/DP).
    # Se limpia al des-liquidar y se re-estampa al re-liquidar.
    liquidated_ts: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Instante real de la liquidacion (auditoria) — NO usar para cortes",
    )

    # Columna INERTE desde #93 (regla sin-DROP): el enlace entrada<->compras
    # vive en la puente inbound_order_purchases (1:N). La migracion backfillea
    # las filas legacy 1:1 hacia la puente y esta FK no se vuelve a escribir.
    purchase_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("purchases.id", ondelete="SET NULL"),
        nullable=True,
        comment="INERTE desde #93 — usar inbound_order_purchases",
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
    third_party: Mapped[Optional["ThirdParty"]] = relationship("ThirdParty", foreign_keys=[third_party_id])
    collector: Mapped[Optional["ThirdParty"]] = relationship("ThirdParty", foreign_keys=[collector_id])
    driver: Mapped[Optional["Driver"]] = relationship("Driver", foreign_keys=[driver_id])
    vehicle: Mapped[Optional["Vehicle"]] = relationship("Vehicle", foreign_keys=[vehicle_id])
    purchase: Mapped[Optional["Purchase"]] = relationship("Purchase", foreign_keys=[purchase_id])
    lines: Mapped[list["InboundOrderLine"]] = relationship(
        "InboundOrderLine",
        back_populates="inbound_order",
        cascade="all, delete-orphan",
    )
    purchase_links: Mapped[list["InboundOrderPurchase"]] = relationship(
        "InboundOrderPurchase",
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

    # #93 D3/D6: precio del material EN ESTA ENTRADA — el que la UI pre-llena
    # en cada reparto nuevo y el que valora el descuadre (ambos sentidos).
    # Nace al liquidar; obligatorio si la linea queda con descuadre != 0 (D16).
    reference_unit_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="Precio de referencia del material en esta entrada — valora el descuadre (D6)",
    )

    # #93 D8: una linea SIN asignaciones bloquea la liquidacion (descuido, no
    # descuadre) salvo que Johana declare explicitamente que no es de nadie.
    unallocated_intentional: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Declaracion explicita 'este material no es de nadie' — habilita liquidar sin reparto (D8)",
    )

    __table_args__ = (
        Index("ix_inbound_order_lines_order", "inbound_order_id"),
        # #93 D3: una fila por material — sin esto el mismo material tendria dos
        # precios de referencia el mismo dia y dos descuadres que no conmutan.
        UniqueConstraint(
            "inbound_order_id", "material_id",
            name="uq_inbound_lines_order_material",
        ),
    )

    # --- Relationships ---
    inbound_order: Mapped["InboundOrder"] = relationship(
        "InboundOrder", back_populates="lines"
    )
    material: Mapped["Material"] = relationship("Material", foreign_keys=[material_id])
    allocations: Mapped[list["InboundLineAllocation"]] = relationship(
        "InboundLineAllocation",
        back_populates="line",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<InboundOrderLine material={self.material_id} qty={self.quantity}>"


class InboundLineAllocation(Base, OrganizationMixin, TimestampMixin):
    """
    Reparto de una linea entre proveedores (#93 D1).

    Un material se reparte entre hasta N proveedores (8 sobre un mismo material
    en el Excel real de Johana). quantity es lo que ese proveedor reporta;
    unit_price el precio pactado (normalmente uno por material — la UI lo
    replica — pero la excepcion por proveedor se registra aca, respuesta 7).
    invoice_number es la factura DEL PROVEEDOR (D12: la remision es de la
    Entrada, la factura del reparto).
    """

    __tablename__ = "inbound_line_allocations"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    inbound_line_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("inbound_order_lines.id", ondelete="CASCADE"),
        nullable=False,
    )

    third_party_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("third_parties.id", ondelete="RESTRICT"),
        nullable=False,
    )

    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)

    unit_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    # Q-15 (reunion 12-ago): Johana puede digitar el VALOR TOTAL de la
    # asignacion en vez del precio unitario — "el precio unitario seria una
    # formula, costo total dividido unidades" (Hugo). Se PERSISTE, no solo se
    # deriva: #93 D20 promete que el reparto sobrevive el round-trip de
    # desliquidar/re-liquidar, y un modo de captura que no sobrevive es un
    # reparto que en realidad no se conservo. NULL = se digito el unitario.
    total_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="Valor total digitado (Q-15). NULL = se digito el unit_price",
    )

    # Modo por kg (correccion de Q-15): Johana digita $/kg y el sistema
    # multiplica por el peso PRORRATEADO de la asignacion. Los dos campos se
    # PERSISTEN — no son un cache de un derivado, son los INSUMOS del documento:
    # el peso es funcion de dos campos mutables (scale_weight_kg y quantity de
    # la linea, ambos editables), asi que sin guardarlos, editar la linea
    # despues reescribiria en silencio la historia de una liquidacion anterior.
    # Es la trazabilidad que Hugo pidio explicitamente: "no habia trazabilidad
    # de lo que yo estoy liquidando... no el peso ni el precio unitario".
    # NULL en los dos = se digito el unitario o el total.
    price_per_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="Precio por kg digitado. NULL = se digito unit_price o total_price",
    )

    weight_kg_used: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 3),
        nullable=True,
        comment="Peso prorrateado con el que se calculo el total (kg/unidad de "
                "la linea x cantidad asignada). Se persiste para que la pantalla "
                "LEA y no re-derive",
    )

    invoice_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Factura del proveedor (D12) — llega con la liquidacion",
    )

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_inbound_alloc_qty_positive"),
        CheckConstraint("unit_price >= 0", name="ck_inbound_alloc_price_non_negative"),
        UniqueConstraint(
            "inbound_line_id", "third_party_id",
            name="uq_inbound_alloc_line_third_party",
        ),
        Index("ix_inbound_line_allocations_line", "inbound_line_id"),
    )

    # --- Relationships ---
    line: Mapped["InboundOrderLine"] = relationship(
        "InboundOrderLine", back_populates="allocations"
    )
    third_party: Mapped["ThirdParty"] = relationship(
        "ThirdParty", foreign_keys=[third_party_id]
    )

    def __repr__(self) -> str:
        return f"<InboundLineAllocation tp={self.third_party_id} qty={self.quantity}>"


class InboundOrderPurchase(Base, OrganizationMixin, TimestampMixin):
    """
    Puente entrada <-> compras derivadas (#93 D2, heredada de #89).

    1:N — de una Entrada liquidada nacen N compras (una por proveedor del
    reparto). Exclusiva de SAC: cero filas en orgs sin kg_ledger_enabled.
    UNIQUE(purchase_id): una compra pertenece a lo sumo a una entrada.

    🔴 Trampa 1:N (R2): PROHIBIDO outerjoin(Purchase) en el listado de
    entradas — una de 13 proveedores saldria 13 veces y la paginacion
    perderia filas. Enrich por lookup por pagina (patron #87 B1).
    """

    __tablename__ = "inbound_order_purchases"

    inbound_order_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("inbound_orders.id", ondelete="CASCADE"),
        primary_key=True,
    )

    purchase_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("purchases.id", ondelete="CASCADE"),
        primary_key=True,
    )

    __table_args__ = (
        UniqueConstraint("purchase_id", name="uq_inbound_order_purchases_purchase"),
    )

    # --- Relationships ---
    inbound_order: Mapped["InboundOrder"] = relationship(
        "InboundOrder", back_populates="purchase_links"
    )
    purchase: Mapped["Purchase"] = relationship("Purchase", foreign_keys=[purchase_id])

    def __repr__(self) -> str:
        return f"<InboundOrderPurchase order={self.inbound_order_id} purchase={self.purchase_id}>"
