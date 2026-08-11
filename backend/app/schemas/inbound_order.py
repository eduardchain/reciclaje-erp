"""
Schemas InboundOrder (SAC E2 CC-004, rediseño #93 plan-sac-entrada-sin-proveedor).

La Entrada es la pantalla de captura unica con 2 tipos:
- willard: genera efectos propios al confirmar (inventario a identidad D2 +
  kg ledger D5); proveedor = titular de la cuenta kg (fijo).
- purchase (#93): la captura NO conoce el proveedor — registra solo el hecho
  fisico (material + cantidad pesada + remision D12). El proveedor aparece al
  LIQUIDAR: el reparto (allocations) distribuye cada linea entre N proveedores
  y de ahi nacen N compras atomicamente (D14). La diferencia pesado-repartido
  es el descuadre (D5-D7), valorado al precio de referencia de la linea (D6).
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.purchase import PurchaseRetentionCreate
from app.utils.dates import BusinessDate, business_today

InboundType = Literal["purchase", "willard"]

WILLARD_INBOUND_TYPES = {"willard"}
PURCHASE_INBOUND_TYPES = {"purchase"}


class InboundOrderLineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: UUID
    # #93 D16: ge=0 (era gt=0) — el reparto de un material que los proveedores
    # reportan y la bascula no vio (truncamiento D5) cuelga de una linea con
    # cantidad pesada 0. Willard sigue exigiendo > 0 en el servicio.
    quantity: Decimal = Field(..., ge=0)
    unit_price: Optional[Decimal] = Field(
        None, ge=0, description="Precio de captura (tipos purchase; definitivo al liquidar §7.2)"
    )
    scale_weight_kg: Optional[Decimal] = Field(None, gt=0)
    quality_notes: Optional[str] = Field(None, max_length=500)


class InboundOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inbound_type: InboundType
    warehouse_id: UUID
    # #93 D1: la captura tipo compra NO conoce el proveedor (nullable);
    # willard lo sigue exigiendo — validacion en el SERVICIO (titular de la
    # cuenta kg, addendum Ciclo B), no aca.
    third_party_id: Optional[UUID] = None
    date: BusinessDate
    driver_id: Optional[UUID] = None
    vehicle_id: Optional[UUID] = None
    # SAC Ciclo D: recolector (service_provider) — AMBOS tipos (Green Loop
    # tambien recolecta willard, Q-02). En willard es informativo: la comision
    # existe SOLO al liquidar compras regulares, como GASTO (jamas al costo #30).
    collector_id: Optional[UUID] = None
    willard_distribution_center: Optional[str] = Field(None, max_length=24)
    # goes_directly_to_jm retirado (Ciclo B B4, Q-03: drosses SIEMPRE a la
    # planta — peso muerto). extra="forbid" -> enviarlo da 422 (F1 QA).
    notes: Optional[str] = Field(None, max_length=1000)
    # #93 D12: factura SOLO willard — en tipo compra la factura llega con la
    # liquidacion, POR PROVEEDOR (en el reparto); enviarla en la captura → 422
    # del servicio (explicito > silencioso). max_length calcado de
    # PurchaseCreate.invoice_number (cero drift).
    invoice_number: Optional[str] = Field(None, max_length=50)
    # #93 D12: remision del camion — UNA por Entrada, capturada en el patio.
    remission_number: Optional[str] = Field(None, max_length=50)
    lines: list[InboundOrderLineCreate] = Field(..., min_length=1)

    @field_validator("date")
    @classmethod
    def not_future(cls, v: datetime) -> datetime:
        # D15 — §11.1.2 L1917 + filosofia anti back-dating #62
        if v.date() > business_today():
            raise ValueError("La fecha de la orden no puede ser futura")
        return v


class InboundOrderUpdate(BaseModel):
    """Edicion D18 — Willard: revert-and-reapply de lineas; purchase: solo
    cabecera sin efectos. warehouse/tipo/tercero inmutables (anular y recrear)."""
    model_config = ConfigDict(extra="forbid")

    date: Optional[BusinessDate] = None
    driver_id: Optional[UUID] = None
    vehicle_id: Optional[UUID] = None
    # Ciclo D: editable (incl. None explicito para quitar). Willard: siempre
    # (informativo). Tipo compra: solo mientras la derivada este registered —
    # tras liquidar, la comision ya se causo
    collector_id: Optional[UUID] = None
    willard_distribution_center: Optional[str] = Field(None, max_length=24)
    notes: Optional[str] = Field(None, max_length=1000)
    # Ajustes 2026-08-03 (A, D2): editable SIEMPRE en willard y en legacy 1:1.
    # #93: en tipo compra nuevo la factura vive en el reparto → 422 del servicio.
    invoice_number: Optional[str] = Field(None, max_length=50)
    # #93 D12: remision editable como dato de referencia (criterio de notes)
    remission_number: Optional[str] = Field(None, max_length=50)
    lines: Optional[list[InboundOrderLineCreate]] = Field(None, min_length=1)

    @field_validator("date")
    @classmethod
    def not_future(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is not None and v.date() > business_today():
            raise ValueError("La fecha de la orden no puede ser futura")
        return v


class InboundOrderAnnulRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


# ------------------------------------------------------------------ #
# #93 — Reparto y liquidacion                                          #
# ------------------------------------------------------------------ #

class InboundAllocationCreate(BaseModel):
    """Una asignacion proveedor x cantidad x precio sobre una linea (D1)."""
    model_config = ConfigDict(extra="forbid")

    third_party_id: UUID
    quantity: Decimal = Field(..., gt=0)
    # gt=0 en el API (purchase.liquidate exige precios > 0 — V-LIQ-01);
    # el CHECK de BD queda >= 0 per D1
    unit_price: Decimal = Field(..., gt=0)
    invoice_number: Optional[str] = Field(
        None, max_length=50, description="Factura del proveedor (D12)"
    )


class InboundLiquidateLine(BaseModel):
    """Reparto de UNA linea (por material — D3 garantiza unicidad).

    Materiales que no estan en la entrada (truncamiento D5) entran aca con
    allocations y el servicio crea la linea con cantidad pesada 0 (D16).
    """
    model_config = ConfigDict(extra="forbid")

    material_id: UUID
    # D6: precio de referencia — obligatorio si la linea queda con descuadre
    # != 0 (D16, validado en servicio ANTES de empezar a liquidar)
    reference_unit_price: Optional[Decimal] = Field(None, gt=0)
    # D8: declaracion explicita "este material no es de nadie" — sin ella,
    # una linea sin asignaciones bloquea la liquidacion (descuido != descuadre)
    unallocated_intentional: bool = False
    allocations: list[InboundAllocationCreate] = []


class InboundCollectorCommission(BaseModel):
    """D11: comision del recolector — UNA por entrada, sobre lo PESADO.

    El monto sugerido (tarifa x base con la regla de los 14 kg/unidad) lo
    calcula la UI; el monto editado es la fuente de verdad (F1 #79).
    """
    model_config = ConfigDict(extra="forbid")

    third_party_id: UUID
    amount: Decimal = Field(..., gt=0)


class InboundSupplierRetentions(BaseModel):
    """Addendum retenciones #93 (hallazgo QA 2026-08-06): bloques OPCIONALES
    por proveedor del reparto — Daniel: "si les descuenta, pero no a todas, es
    opcional". Reusa PurchaseRetentionCreate (#79): mismas validaciones de
    ICA/municipio y mismo contrato F1 (el monto editado es la verdad; rate y
    base son informativos). El servicio los pasa a purchase.liquidate() de la
    compra del proveedor -> hereda flag-guard, tope < total y matching H4."""
    model_config = ConfigDict(extra="forbid")

    third_party_id: UUID
    retentions: list[PurchaseRetentionCreate] = Field(..., min_length=1)


class InboundSupplierPayment(BaseModel):
    """Pago de contado POR PROVEEDOR del reparto (pruebas de usuario 2026-08-11).

    Misma familia que las retenciones: el canal unico (#80) dejo el
    `immediate_payment` de PurchaseLiquidateRequest (#20) inalcanzable en SAC.
    Por proveedor y opcional — Johana le paga de contado a unos y a otros no; si
    quiere pagarles a todos, elige la misma cuenta en cada uno. El monto NO se
    captura: purchase.liquidate() paga el NETO de la compra (Σlineas − Σret,
    #75), asi que no puede desalinearse del saldo."""
    model_config = ConfigDict(extra="forbid")

    third_party_id: UUID
    account_id: UUID


class InboundLiquidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lines: list[InboundLiquidateLine] = Field(..., min_length=1)
    collector_commission: Optional[InboundCollectorCommission] = None
    # Ausente/vacio = cero efecto (data-gated D9) — el camino sin retenciones
    # queda byte a byte
    supplier_retentions: Optional[list[InboundSupplierRetentions]] = None
    supplier_payments: Optional[list[InboundSupplierPayment]] = None


class InboundAllocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    third_party_id: UUID
    third_party_name: Optional[str] = None
    quantity: Decimal
    unit_price: Decimal
    invoice_number: Optional[str] = None


class InboundRetentionDetail(BaseModel):
    """Una retencion viva de la compra — alimenta el display del neto y la
    PRECARGA al re-liquidar (pruebas Daniel: si el reparto se conserva, la
    retencion tambien debe; es justo lo que mas se corrige)."""
    retention_type: str
    municipality: Optional[str] = None
    rate: Optional[Decimal] = None
    base: Optional[Decimal] = None
    amount: Decimal


class InboundPurchaseSummary(BaseModel):
    """Cara financiera por proveedor — via puente, lookup por pagina (R2)."""
    purchase_id: UUID
    purchase_number: int
    supplier_id: UUID
    supplier_name: Optional[str] = None
    status: str
    total_amount: float
    invoice_number: Optional[str] = None
    # Suma de retenciones VIVAS (reverted_at IS NULL) — display: el proveedor
    # quedo acreditado neto (total - retenciones)
    retentions_total: Optional[float] = None
    retentions: list[InboundRetentionDetail] = []


class InboundDiscrepancyAdjustment(BaseModel):
    """Ajuste de descuadre generado al liquidar (D7) — visible en la Entrada.

    Sin esto la ganancia/perdida del descuadre solo se ve yendo a Reportes o a
    Inventario: Johana liquida y no se entera de la plata que genero (hallazgo
    de las pruebas de usuario)."""
    adjustment_id: UUID
    adjustment_number: Optional[int] = None
    material_id: UUID
    material_code: Optional[str] = None
    material_unit: str = "kg"
    adjustment_type: str            # increase | decrease
    quantity: Decimal               # SIEMPRE positiva; el signo lo da el tipo
    unit_cost: Optional[Decimal] = None
    total_value: Decimal            # signed: + ganancia, − perdida
    status: str


class InboundOrderLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    material_id: UUID
    material_code: Optional[str] = None
    material_name: Optional[str] = None
    material_unit: str = "kg"  # patron #54
    quantity: Decimal
    unit: Optional[str] = None
    unit_price: Optional[Decimal] = None
    unit_cost: Optional[Decimal] = None
    scale_weight_kg: Optional[Decimal] = None
    quality_notes: Optional[str] = None
    kg_lead: Optional[Decimal] = Field(
        None, description="delta_kg emitido al KgLedger por esta linea (tipos Willard)"
    )
    # #93: reparto y descuadre (tipo compra)
    reference_unit_price: Optional[Decimal] = None
    unallocated_intentional: bool = False
    allocations: list["InboundAllocationResponse"] = []
    allocated_quantity: Optional[Decimal] = Field(
        None, description="Suma del reparto de la linea (tipo compra)"
    )
    discrepancy: Optional[Decimal] = Field(
        None, description="pesado - repartido (D5): + sobrante, - faltante"
    )


class InboundOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_number: int
    inbound_type: str
    warehouse_id: UUID
    warehouse_name: Optional[str] = None
    # #93 D1: NULL en capturas tipo compra (el proveedor vive en el reparto)
    third_party_id: Optional[UUID] = None
    third_party_name: Optional[str] = None
    date: datetime
    driver_id: Optional[UUID] = None
    driver_name: Optional[str] = None
    vehicle_id: Optional[UUID] = None
    vehicle_plate: Optional[str] = None
    # Ciclo D: recolector — informativo en willard, con comision en compras
    collector_id: Optional[UUID] = None
    collector_name: Optional[str] = None
    # Solo en GET de detalle (cara financiera): comision causada confirmed
    collector_commission_total: Optional[float] = None
    willard_distribution_center: Optional[str] = None
    notes: Optional[str] = None
    # Willard: columna propia. Legacy 1:1: purchase.invoice_number. Tipo compra
    # #93: NULL aca — la factura vive POR PROVEEDOR en purchases[]
    invoice_number: Optional[str] = None
    # #93 D12: remision del camion (documento de patio)
    remission_number: Optional[str] = None
    status: str
    display_status: str = Field(
        "registered",
        description=(
            "#93 D4: estado UNICO visible, ahora columna-driven "
            "(registered|reviewed|liquidated|annulled)"
        ),
    )
    # Legacy 1:1 (ciclos B-D) — poblados solo si la fila vieja tiene purchase_id
    purchase_id: Optional[UUID] = None
    purchase_number: Optional[int] = None
    purchase_status: Optional[str] = None
    # #93: las N compras del reparto (via puente, lookup por pagina — R2)
    purchases: list[InboundPurchaseSummary] = []
    # #93 D7: los ajustes de descuadre generados al liquidar (SOLO en el
    # detalle — el listado no los necesita y serian una query por pagina)
    discrepancy_adjustments: list[InboundDiscrepancyAdjustment] = []
    # #93 D10: auditoria de revision
    reviewed_by_name: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    willard_world: Optional[str] = Field(
        None, description="Mundo de la orden willard (drosses|postconsumo); null tipo compra"
    )
    total_kg_lead: Optional[Decimal] = Field(
        None, description="Suma de deltas kg emitidos (tipos Willard)"
    )
    annulled_reason: Optional[str] = None
    annulled_at: Optional[datetime] = None
    created_at: datetime
    # Ciclo C (C-5): quien hizo que — capa de confianza del flujo a 2 personas
    created_by_name: Optional[str] = None
    liquidated_by_name: Optional[str] = None
    # Fecha de NEGOCIO (mediodia UTC) — se pinta SIN hora (#87)
    liquidated_at: Optional[datetime] = None
    # Instante real del clic — este SI se pinta con hora (columna propia de
    # inbound_orders, ver el modelo). Null en entradas liquidadas antes de #93.
    liquidated_ts: Optional[datetime] = None
    annulled_by_name: Optional[str] = None
    lines: list[InboundOrderLineResponse] = []
    warnings: list[str] = []


class InboundOrderListResponse(BaseModel):
    items: list[InboundOrderResponse]
    total: int
