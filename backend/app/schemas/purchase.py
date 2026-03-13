"""
Pydantic schemas for Purchase and PurchaseLine models.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer, model_validator

from app.utils.dates import BusinessDate


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

    # Nested lines with joined data
    lines: List[PurchaseLineResponse] = Field(..., description="Purchase lines")
    
    # Double-entry link
    double_entry_id: Optional[UUID] = Field(None, description="Link to double-entry operation (if applicable)")
    
    model_config = {"from_attributes": True}
    
    @field_serializer('total_amount')
    def serialize_decimal(self, value: Decimal) -> float:
        """Convert Decimal to float for JSON serialization."""
        return float(value)


class PurchaseLiquidateLineUpdate(BaseModel):
    """Actualizacion de precio por linea al liquidar."""
    line_id: UUID = Field(..., description="ID de la linea a actualizar")
    unit_price: Decimal = Field(..., gt=0, description="Precio unitario (debe ser > 0)")


class PurchaseLiquidateRequest(BaseModel):
    """Schema for liquidating a purchase (confirmar precios, mover stock, actualizar saldo proveedor)."""
    lines: Optional[List[PurchaseLiquidateLineUpdate]] = Field(None, description="Actualizacion opcional de precios por linea")
    immediate_payment: bool = Field(False, description="Crear pago inmediato al liquidar")
    payment_account_id: Optional[UUID] = Field(None, description="Cuenta para pago inmediato")

    @model_validator(mode="after")
    def validate_immediate_payment(self):
        if self.immediate_payment and not self.payment_account_id:
            raise ValueError("payment_account_id es requerido cuando immediate_payment=True")
        return self


class PaginatedPurchaseResponse(BaseModel):
    """Paginated response for purchase lists."""
    items: List[PurchaseResponse]
    total: int
    skip: int
    limit: int
