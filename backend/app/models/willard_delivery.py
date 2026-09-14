"""
Modelos WillardDelivery / WillardDeliveryLine — salida de plomo a Willard (W1).

Espejo de la Entrada (#93): un documento fisico de patio que gobierna, y la
cara financiera derivada. La Entrada recibe y deriva compras; la Salida entrega
y deriva UNA venta — solo en el tipo `venta` (D2).

El modelo del cliente (reunion 24-ago): hay DOS deudas en plomo con Willard y
son de duenos distintos. Las baterias llegan a Circunvalar, asi que la deuda de
postconsumo es de Circunvalar; los materiales (drosses) llegan derecho a planta,
asi que esa deuda es de planta. De ahi salen los tres tipos y sus efectos:

    venta           -> baja `intersede` (planta le paga a Circunvalar con plomo)
    abono_bateria   -> baja `willard_baterias` Y `intersede`, MISMO kg
                       (pago en cadena: planta -> Circunvalar -> Willard)
    abono_material  -> baja `willard_drosses` (Circunvalar nunca estuvo)

El abono de bateria baja dos contadores por la misma cantidad porque es un solo
pago que salda dos deudas encadenadas — no es una regla arbitraria.

Los movimientos de dinero NO cuelgan de columnas FK: se encuentran por
`source_type="willard_delivery"` + `source_id`, el patron del par de #84. La
cabecera guarda los montos para display.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.fleet import Driver, Vehicle
    from app.models.material import Material
    from app.models.sale import Sale
    from app.models.third_party import ThirdParty
    from app.models.warehouse import Warehouse


DELIVERY_TYPES = ("venta", "abono_bateria", "abono_material")
DELIVERY_STATUSES = ("draft", "reviewed", "liquidated", "annulled")

# Consecutivo por SERIE (#105 D1). Hugo, 28-ago: "para los abonos tenemos un
# consecutivo y para la venta otro consecutivo [...] que es el que llevo con
# Willard". Este dict es la UNICA fuente: de aqui salen el CHECK de la tabla,
# `series_of()` y el label que ve el usuario. Un tipo nuevo sin serie declarada
# no puede insertarse — `series` es NOT NULL y el CHECK lo rechaza en la BD, no
# en un test que alguien pueda borrar (F1 de QA: la version con indices
# parciales dejaba un tipo nuevo SIN unicidad, en silencio).
SERIES_OF_TYPE = {
    "venta": "venta",
    "abono_bateria": "abono",
    "abono_material": "abono",
}
DELIVERY_SERIES = ("venta", "abono")
SERIES_LABELS = {"venta": "Venta", "abono": "Abono"}


def series_of(delivery_type: str) -> str:
    """Serie del consecutivo para un tipo. Levanta en tipo desconocido a
    proposito: caer en una serie por descarte es el fail-open de #103."""
    try:
        return SERIES_OF_TYPE[delivery_type]
    except KeyError:
        raise ValueError(
            f"Tipo de salida sin serie declarada en SERIES_OF_TYPE: {delivery_type!r}"
        ) from None


def series_check_sql() -> str:
    """Texto del CHECK tipo<->serie, generado del mapping (no tipeado dos veces).
    La migracion a7b8c9d0e1f3 lleva el mismo texto congelado; el parity check
    los compara."""
    by_series: dict[str, list[str]] = {}
    for dtype, serie in SERIES_OF_TYPE.items():
        by_series.setdefault(serie, []).append(dtype)
    parts = []
    for serie, types in by_series.items():
        listed = ", ".join(f"'{t}'" for t in types)
        parts.append(f"(delivery_type IN ({listed}) AND series = '{serie}')")
    return " OR ".join(parts)


class WillardDelivery(Base, OrganizationMixin, TimestampMixin):
    """Salida de plomo a Willard — documento fisico de despacho."""

    __tablename__ = "willard_deliveries"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    delivery_number: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Consecutivo por organizacion Y serie (#105)"
    )

    series: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Serie del consecutivo (#105 D1): venta | abono. Derivada del tipo; la BD la exige",
    )

    delivery_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="venta | abono_bateria | abono_material"
    )

    warehouse_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Bodega de origen — planta (D8: el plomo sale de Juan Mina)",
    )

    third_party_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("third_parties.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Willard — titular de la cuenta kg que se descarga",
    )

    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="BusinessDate del despacho"
    )

    driver_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True
    )
    vehicle_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True
    )

    invoice_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    remission_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        comment="draft (Registrada) | reviewed | liquidated | annulled",
    )

    reviewed_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    liquidated_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    liquidated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Fecha de NEGOCIO de la liquidacion (mediodia UTC) — sin hora",
    )
    liquidated_ts: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Instante real del clic (#93): esta si lleva hora",
    )

    # D2 — solo el tipo `venta` deriva una Sale
    sale_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("sales.id", ondelete="SET NULL"), nullable=True
    )

    # Montos facturados y repartidos (display; los MoneyMovement se buscan por
    # source_type/source_id, patron #84)
    maquila_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=0, server_default="0"
    )
    freight_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=0, server_default="0"
    )
    plant_credit_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=0,
        server_default="0",
        comment="Porcion de la maquila que Circunvalar le abona a planta (D5)",
    )
    crucible_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=0,
        server_default="0",
        comment="Diferencial del crisol: $300/kg de puro VENDIDO, planta->CV (#107 D4)",
    )
    billing_warehouse_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("warehouses.id", ondelete="SET NULL"),
        nullable=True,
        comment="Sede que factura, estampada al liquidar (snapshot de willard_sede_facturacion; Q-30, #107 D5)",
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

    warehouse: Mapped["Warehouse"] = relationship(
        "Warehouse", foreign_keys=[warehouse_id]
    )
    third_party: Mapped["ThirdParty"] = relationship(
        "ThirdParty", foreign_keys=[third_party_id]
    )
    driver: Mapped[Optional["Driver"]] = relationship(
        "Driver", foreign_keys=[driver_id]
    )
    vehicle: Mapped[Optional["Vehicle"]] = relationship(
        "Vehicle", foreign_keys=[vehicle_id]
    )
    sale: Mapped[Optional["Sale"]] = relationship("Sale", foreign_keys=[sale_id])
    lines: Mapped[list["WillardDeliveryLine"]] = relationship(
        "WillardDeliveryLine",
        back_populates="delivery",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "series",
            "delivery_number",
            name="uq_willard_delivery_series_number",
        ),
        CheckConstraint(series_check_sql(), name="ck_willard_delivery_series"),
        CheckConstraint(
            "delivery_type IN ('venta', 'abono_bateria', 'abono_material')",
            name="ck_willard_delivery_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'reviewed', 'liquidated', 'annulled')",
            name="ck_willard_delivery_status",
        ),
        Index("ix_willard_deliveries_org_status", "organization_id", "status"),
        Index("ix_willard_deliveries_org_date", "organization_id", "date"),
    )

    @property
    def label(self) -> str:
        """El numero que ve el usuario: "Venta #n" / "Abono #n" (#105 D5)."""
        return f"{SERIES_LABELS[self.series]} #{self.delivery_number}"

    def __repr__(self) -> str:
        return f"<WillardDelivery {self.label} ({self.delivery_type})>"


class WillardDeliveryLine(Base, OrganizationMixin, TimestampMixin):
    """Linea de salida — un material despachado."""

    __tablename__ = "willard_delivery_lines"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    willard_delivery_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("willard_deliveries.id", ondelete="CASCADE"), nullable=False
    )

    material_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("materials.id", ondelete="RESTRICT"), nullable=False
    )

    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)

    unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    scale_weight_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 4),
        nullable=True,
        comment="Peso certificado. Opcional al capturar, OBLIGATORIO al revisar (#95)",
    )

    # --- Se llenan al liquidar ---
    kg_lead_equivalent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 4),
        nullable=True,
        comment="kg de plomo que descargan la deuda — del snapshot de formula",
    )
    conversion_formula_snapshot: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
    )
    unit_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 4), nullable=True, comment="Costo promedio al que sale del inventario"
    )

    # --- Solo tipo `venta` (XOR, patron #95 D8) ---
    unit_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    total_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="Se persiste: el reparto sobrevive al des-liquidar (#95 D8)",
    )

    delivery: Mapped["WillardDelivery"] = relationship(
        "WillardDelivery", back_populates="lines"
    )
    material: Mapped["Material"] = relationship("Material", foreign_keys=[material_id])

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_willard_delivery_line_qty"),
        Index("ix_willard_delivery_lines_delivery", "willard_delivery_id"),
    )

    def __repr__(self) -> str:
        return f"<WillardDeliveryLine {self.material_id} x {self.quantity}>"
