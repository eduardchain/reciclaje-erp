"""
Pydantic schemas for Purchase and PurchaseLine models.
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from app.utils.dates import BusinessDate


# ============================================================================
# PurchaseCommission Schemas
# ============================================================================


class PurchaseCommissionBase(BaseModel):
    """Base schema para cargo de compra (comision o flete)."""
    third_party_id: UUID = Field(..., description="UUID del receptor del cargo")
    concept: str = Field(..., max_length=255, description="Concepto del cargo")
    commission_type: Literal["percentage", "fixed", "per_kg"] = Field(..., description="'percentage', 'fixed' o 'per_kg'")
    commission_value: Decimal = Field(..., gt=0, description="Porcentaje (0-100) o monto fijo")
    charge_type: Literal["commission", "freight"] = Field(
        "commission", description="Tipo de cargo: comision o flete (ambos prorratean al costo)"
    )


class PurchaseCommissionCreate(PurchaseCommissionBase):
    """Schema para crear comision de compra. commission_amount se calcula automaticamente."""
    pass


class PurchaseCommissionResponse(PurchaseCommissionBase):
    """Schema para respuesta de comision de compra."""
    id: UUID
    purchase_id: UUID
    commission_amount: float
    created_at: datetime
    third_party_name: str = Field(..., description="Nombre del comisionista")

    model_config = {"from_attributes": True}

    @field_serializer('commission_value', 'commission_amount')
    def serialize_decimals(self, value: Decimal) -> float:
        return float(value)


# ============================================================================
# PurchaseLine Schemas
# ============================================================================

class PurchaseLineBase(BaseModel):
    """Base schema for PurchaseLine."""
    material_id: UUID = Field(..., description="Material UUID")
    quantity: Decimal = Field(..., gt=0, description="Quantity purchased (must be positive)")
    unit_price: Decimal = Field(..., ge=0, description="Price per unit")
    warehouse_id: Optional[UUID] = Field(None, description="Destination warehouse UUID (nullable for double-entry)")


class PurchaseLineCreate(PurchaseLineBase):
    """
    Schema for creating a PurchaseLine.
    
    Note: total_price is calculated automatically (quantity × unit_price)
    """
    pass


class PurchaseLineResponse(PurchaseLineBase):
    """Schema for PurchaseLine responses with joined data."""
    id: UUID
    purchase_id: UUID
    total_price: float
    created_at: datetime
    
    # Joined data from related models
    material_code: str = Field(..., description="Material code (e.g., MAT-001)")
    material_name: str = Field(..., description="Material name")
    material_unit: str = Field("kg", description="Unidad de medida del material (kg, unidad, etc.)")
    warehouse_name: Optional[str] = Field(None, description="Warehouse name (null for double-entry)")
    
    model_config = {"from_attributes": True}
    
    @field_serializer('quantity', 'unit_price', 'total_price')
    def serialize_decimals(self, value: Decimal) -> float:
        """Convert Decimal to float for JSON serialization."""
        return float(value)


# ============================================================================
# Purchase Schemas
# ============================================================================

class PurchaseBase(BaseModel):
    """Base schema for Purchase."""
    supplier_id: UUID = Field(..., description="Supplier UUID (must have is_supplier=True)")
    date: BusinessDate = Field(..., description="Purchase date (weighing date)")
    notes: Optional[str] = Field(None, max_length=1000, description="Additional notes")
    vehicle_plate: Optional[str] = Field(None, max_length=20, description="Vehicle plate number")
    invoice_number: Optional[str] = Field(None, max_length=50, description="Invoice or bill number")
    double_entry_id: Optional[UUID] = Field(None, description="Link to double-entry operation (if applicable)")


class PurchaseCreate(PurchaseBase):
    """
    Schema for creating a Purchase.

    Workflow:
    - auto_liquidate=False: Creates purchase with status='registered', liquidate later
    - auto_liquidate=True: Creates and liquidates in one step (requires all prices > 0)

    Payment to supplier is a separate operation via MoneyMovement.
    """
    lines: List[PurchaseLineCreate] = Field(..., min_length=1, description="Purchase lines (at least 1)")
    # SAC E2 D11: bodega de cabecera opcional — si presente, fuerza el warehouse
    # de TODAS las lineas (recepcion unificada); ausente = comportamiento actual
    warehouse_id: Optional[UUID] = Field(None, description="Bodega header (fuerza las lineas, D11)")
    commissions: List[PurchaseCommissionCreate] = Field(default_factory=list, description="Comisiones opcionales")
    auto_liquidate: bool = Field(False, description="Auto-liquidate after creation (1-step workflow)")
    immediate_payment: bool = Field(False, description="Pagar de contado al liquidar (solo con auto_liquidate)")
    payment_account_id: Optional[UUID] = Field(None, description="Cuenta para pago inmediato")

    @model_validator(mode='after')
    def validate_auto_liquidate(self):
        """Si auto_liquidate=True, todos los precios deben ser > 0."""
        if self.auto_liquidate:
            for i, line in enumerate(self.lines):
                if line.unit_price <= 0:
                    raise ValueError(f"Todos los precios deben ser > 0 para auto-liquidar. Linea {i+1} tiene precio {line.unit_price}")
        if self.immediate_payment:
            if not self.auto_liquidate:
                raise ValueError("immediate_payment requiere auto_liquidate=True")
            if not self.payment_account_id:
                raise ValueError("payment_account_id es requerido cuando immediate_payment=True")
        return self


class PurchaseUpdate(BaseModel):
    """
    Schema for updating a Purchase (partial updates only).

    Note: Only metadata can be updated, not lines or amounts.
    """
    notes: Optional[str] = Field(None, max_length=1000)
    date: Optional[BusinessDate] = None
    vehicle_plate: Optional[str] = Field(None, max_length=20)
    invoice_number: Optional[str] = Field(None, max_length=50)


class PurchaseFullUpdate(BaseModel):
    """
    Edicion completa de compra: metadata + proveedor + lineas.

    Solo permitido para compras con status='registered' y sin double_entry_id.
    Si lines se proporciona, reemplaza TODAS las lineas existentes (estrategia revert+reapply).
    """
    supplier_id: Optional[UUID] = Field(None, description="Nuevo proveedor (debe tener is_supplier=True)")
    date: Optional[BusinessDate] = Field(None, description="Nueva fecha")
    notes: Optional[str] = Field(None, max_length=1000)
    vehicle_plate: Optional[str] = Field(None, max_length=20)
    invoice_number: Optional[str] = Field(None, max_length=50)
    lines: Optional[List[PurchaseLineCreate]] = Field(None, min_length=1, description="Nuevas lineas (reemplazan todas las existentes)")
    commissions: Optional[List[PurchaseCommissionCreate]] = Field(None, description="Comisiones (reemplazan las existentes)")


class PurchaseResponse(PurchaseBase):
    """Schema for Purchase responses with all details."""
    id: UUID
    organization_id: UUID
    purchase_number: int
    total_amount: float
    status: str = Field(..., description="registered | liquidated | cancelled")
    payment_account_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    
    # Audit fields
    created_by: Optional[UUID] = Field(None, description="User who created the purchase")
    liquidated_by: Optional[UUID] = Field(None, description="User who liquidated the purchase")
    liquidated_at: Optional[datetime] = Field(None, description="Timestamp when the purchase was liquidated")
    cancelled_by: Optional[UUID] = Field(None, description="User who cancelled the purchase")
    cancelled_at: Optional[datetime] = Field(None, description="Timestamp when the purchase was cancelled")
    updated_by: Optional[UUID] = Field(None, description="User who last edited the purchase")

    # Audit names (joined from User model)
    created_by_name: Optional[str] = Field(None, description="Name of user who created the purchase")
    liquidated_by_name: Optional[str] = Field(None, description="Name of user who liquidated the purchase")
    cancelled_by_name: Optional[str] = Field(None, description="Name of user who cancelled the purchase")
    updated_by_name: Optional[str] = Field(None, description="Name of user who last edited the purchase")

    # Warnings (duplicados, stock negativo, etc.)
    warnings: Optional[List[str]] = Field(None, description="Advertencias no bloqueantes")

    # Joined data from related models
    supplier_name: str = Field(..., description="Supplier name")
    payment_account_name: Optional[str] = Field(None, description="Payment account name (if liquidated)")

    # Nested lines and commissions
    lines: List[PurchaseLineResponse] = Field(..., description="Purchase lines")
    commissions: List[PurchaseCommissionResponse] = Field(default_factory=list, description="Comisiones de compra")
    # SAC E2 D9 — retenciones aplicadas en la liquidacion (vacio para los 3 clientes actuales)
    retentions: List["PurchaseRetentionResponse"] = Field(default_factory=list, description="Retenciones tributarias")
    
    # Double-entry link
    double_entry_id: Optional[UUID] = Field(None, description="Link to double-entry operation (if applicable)")

    # SAC Ciclo B (B1): origen inbound — lookup inverso InboundOrder.purchase_id
    # (solo en list y detail; None para compras manuales y orgs sin recepcion)
    inbound_order_id: Optional[UUID] = Field(None, description="Recepcion de origen (si la compra fue derivada)")
    inbound_order_number: Optional[int] = Field(None, description="Numero de la recepcion de origen")
    # SAC Ciclo D: recolector capturado en la entrada — la Liquidate page
    # pre-carga la comision (tarifa comision_green_loop x kg, editable)
    collector_id: Optional[UUID] = Field(None, description="Recolector de la entrada de origen")
    collector_name: Optional[str] = Field(None, description="Nombre del recolector")
    # Solo en GET de detalle (patron #63, sin N+1): comision causada confirmed;
    # None si no hay o fue anulada (condonada)
    collector_commission_total: Optional[float] = Field(
        None, description="Comision de recoleccion causada (gasto) — solo detalle"
    )

    # Pago inmediato enlazado vivo (solo en detalle) — para el diálogo de cancelación (decisión #63)
    linked_payment_total: Optional[float] = Field(None, description="Suma de pagos inmediatos enlazados confirmados (payment_to_supplier con purchase_id). null/0 = ninguno")

    model_config = {"from_attributes": True}
    
    @field_serializer('total_amount')
    def serialize_decimal(self, value: Decimal) -> float:
        """Convert Decimal to float for JSON serialization."""
        return float(value)


class PurchaseLiquidateLineUpdate(BaseModel):
    """Actualizacion de precio por linea al liquidar."""
    line_id: UUID = Field(..., description="ID de la linea a actualizar")
    unit_price: Decimal = Field(..., gt=0, description="Precio unitario (debe ser > 0)")


class PurchaseRetentionCreate(BaseModel):
    """Retencion tributaria al liquidar (SAC E2 D9 — data-gated: ausente = cero efecto).

    Fase 1 = captura manual por monto (la tabla de tasas llega del contador).
    ICA es POR MUNICIPIO (Johana 2026-07-16): municipality obligatorio en ica,
    prohibido en retefuente/reteiva.
    """
    retention_type: Literal["retefuente", "reteiva", "ica"]
    municipality: Optional[str] = Field(None, min_length=1, max_length=60)
    rate: Optional[Decimal] = Field(None, gt=0, description="Tasa informativa")
    base: Optional[Decimal] = Field(None, gt=0, description="Base informativa")
    amount: Decimal = Field(..., gt=0)

    @model_validator(mode="after")
    def validate_municipality(self):
        if self.retention_type == "ica":
            if not (self.municipality and self.municipality.strip()):
                raise ValueError("municipality es obligatorio en retenciones ICA (una entidad por municipio)")
        elif self.municipality is not None:
            raise ValueError("municipality solo aplica a retenciones ICA")
        return self


class PurchaseRetentionResponse(BaseModel):
    """Retencion persistida (detalle de compra)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    third_party_id: UUID
    retention_type: str
    municipality: Optional[str] = None
    rate: Optional[Decimal] = None
    base: Optional[Decimal] = None
    amount: Decimal
    reverted_at: Optional[datetime] = None


class CollectorCommissionIn(BaseModel):
    """Comision de recolector al liquidar (SAC Ciclo D — data-gated D9).

    NO es PurchaseCommission (#30): no se prorratea al costo. Se causa como
    GASTO (expense_accrual, categoria sistema 'Comisiones de recoleccion').
    El monto editado por Johana es la fuente de verdad — la tarifa
    comision_green_loop solo pre-sugiere en el frontend (patron F1 #79).
    """
    third_party_id: UUID
    amount: Decimal = Field(..., gt=0)


class PurchaseLiquidateRequest(BaseModel):
    """Schema for liquidating a purchase (confirmar precios, mover stock, actualizar saldo proveedor)."""
    lines: Optional[List[PurchaseLiquidateLineUpdate]] = Field(None, description="Actualizacion opcional de precios por linea")
    commissions: Optional[List[PurchaseCommissionCreate]] = Field(None, description="Comisiones (reemplazan las existentes)")
    immediate_payment: bool = Field(False, description="Crear pago inmediato al liquidar")
    payment_account_id: Optional[UUID] = Field(None, description="Cuenta para pago inmediato")
    liquidation_date: Optional[BusinessDate] = Field(None, description="Fecha de liquidacion (default: fecha del documento)")
    # SAC E2 D9: data-gated — ausente/vacio = camino actual byte a byte;
    # presente exige flag kg_ledger_enabled (422 en servicio)
    retentions: Optional[List[PurchaseRetentionCreate]] = Field(
        None, description="Retenciones tributarias (proveedor recibe neto; requiere kg_ledger_enabled)"
    )
    # SAC Ciclo D: mismo data-gate D9 — ausente = camino actual byte a byte
    collector_commission: Optional[CollectorCommissionIn] = Field(
        None, description="Comision de recolector como gasto (requiere kg_ledger_enabled)"
    )

    @model_validator(mode="after")
    def validate_immediate_payment(self):
        if self.immediate_payment and not self.payment_account_id:
            raise ValueError("payment_account_id es requerido cuando immediate_payment=True")
        return self


class PaginatedPurchaseResponse(BaseModel):
    """Paginated response for purchase lists.

    `total_amount_sum` cubre TODO el set filtrado EXCLUYENDO canceladas
    (paridad con P&L). `active_total` es el count tambien excluyendo canceladas
    (para el KPI "Operaciones"). `total` sigue contando canceladas para la
    paginacion del listado.
    """
    items: List[PurchaseResponse]
    total: int
    active_total: int = 0
    skip: int
    limit: int
    total_amount_sum: float = 0.0
