"""
Pydantic schemas for Sale, SaleLine, and SaleCommission models.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer, model_validator


# ============================================================================
# SaleCommission Schemas
# ============================================================================

class SaleCommissionBase(BaseModel):
    """Base schema for SaleCommission."""
    third_party_id: UUID = Field(..., description="Commission recipient UUID")
    concept: str = Field(..., max_length=255, description="Commission description (e.g., 'Comisión facturación', 'Intermediario')")
    commission_type: str = Field(..., description="'percentage' or 'fixed'")
    commission_value: Decimal = Field(..., gt=0, description="Percentage (0-100) or fixed amount")


class SaleCommissionCreate(SaleCommissionBase):
    """
    Schema for creating a SaleCommission.
    
    Note: commission_amount is calculated automatically based on sale total.
    """
    pass


class SaleCommissionResponse(SaleCommissionBase):
    """Schema for SaleCommission responses with calculated data."""
    id: UUID
    sale_id: UUID
    commission_amount: float
    created_at: datetime
    
    # Joined data from related models
    third_party_name: str = Field(..., description="Commission recipient name")
    
    model_config = {"from_attributes": True}
    
    @field_serializer('commission_value', 'commission_amount')
    def serialize_decimals(self, value: Decimal) -> float:
        """Convert Decimal to float for JSON serialization."""
        return float(value)


# ============================================================================
# SaleLine Schemas
# ============================================================================

class SaleLineBase(BaseModel):
    """Base schema for SaleLine."""
    material_id: UUID = Field(..., description="Material UUID")
    quantity: Decimal = Field(..., gt=0, description="Quantity sold (must be positive)")
    unit_price: Decimal = Field(..., ge=0, description="Selling price per unit")


class SaleLineCreate(SaleLineBase):
    """
    Schema for creating a SaleLine.
    
    Note: 
    - total_price is calculated automatically (quantity × unit_price)
    - unit_cost is captured from Material.current_average_cost at moment of sale
    """
    pass


class SaleLineResponse(SaleLineBase):
    """Schema for SaleLine responses with joined data and profit calculation."""
    id: UUID
    sale_id: UUID
    total_price: float
    unit_cost: float
    profit: float = Field(..., description="(unit_price - unit_cost) × quantity")
    created_at: datetime
    
    # Joined data from related models
    material_code: str = Field(..., description="Material code (e.g., MAT-001)")
    material_name: str = Field(..., description="Material name")
    
    model_config = {"from_attributes": True}
    
    @field_serializer('quantity', 'unit_price', 'total_price', 'unit_cost', 'profit')
    def serialize_decimals(self, value: Decimal) -> float:
        """Convert Decimal to float for JSON serialization."""
        return float(value)


# ============================================================================
# Sale Schemas
# ============================================================================

class SaleBase(BaseModel):
    """Base schema for Sale."""
    customer_id: UUID = Field(..., description="Customer UUID (must have is_customer=True)")
    warehouse_id: Optional[UUID] = Field(None, description="Source warehouse UUID (nullable for double-entry)")
    date: datetime = Field(..., description="Sale date")
    vehicle_plate: Optional[str] = Field(None, max_length=20, description="Vehicle plate number for delivery/pickup")
    invoice_number: Optional[str] = Field(None, max_length=50, description="Invoice or bill number")
    notes: Optional[str] = Field(None, max_length=1000, description="Additional notes")
    double_entry_id: Optional[UUID] = Field(None, description="Link to double-entry operation (if applicable)")


class SaleCreate(SaleBase):
    """
    Schema for creating a Sale.
    
    Workflow:
    - auto_liquidate=False: Creates sale with status='registered', liquidate later (2-step)
    - auto_liquidate=True: Creates and liquidates in one step (1-step workflow)
    
    Validation:
    - At least one line is required
    - Stock validation: All materials must have sufficient stock
    """
    lines: List[SaleLineCreate] = Field(..., min_length=1, description="Sale lines (at least 1)")
    commissions: List[SaleCommissionCreate] = Field(default_factory=list, description="Optional sale commissions")
    auto_liquidate: bool = Field(False, description="Auto-liquidate after creation (1-step workflow)")


class SaleUpdate(BaseModel):
    """
    Schema for updating a Sale (partial updates only).

    Note: Only metadata can be updated, not lines, amounts, or status.
    """
    notes: Optional[str] = Field(None, max_length=1000)
    vehicle_plate: Optional[str] = Field(None, max_length=20)
    invoice_number: Optional[str] = Field(None, max_length=50)


class SaleFullUpdate(BaseModel):
    """
    Edicion completa de venta: metadata + cliente + bodega + lineas + comisiones.

    Solo aplica a ventas con status='registered' y sin doble partida.
    Si lines se envia, reemplaza todas las lineas (revert + re-apply).
    Si commissions se envia, reemplaza todas las comisiones.
    """
    customer_id: Optional[UUID] = Field(None, description="Nuevo cliente")
    warehouse_id: Optional[UUID] = Field(None, description="Nueva bodega")
    date: Optional[datetime] = Field(None, description="Nueva fecha")
    notes: Optional[str] = Field(None, max_length=1000)
    vehicle_plate: Optional[str] = Field(None, max_length=20)
    invoice_number: Optional[str] = Field(None, max_length=50)
    lines: Optional[List[SaleLineCreate]] = Field(None, min_length=1, description="Nuevas lineas (reemplazan todas)")
    commissions: Optional[List[SaleCommissionCreate]] = Field(None, description="Nuevas comisiones (reemplazan todas)")


class SaleResponse(SaleBase):
    """Schema for Sale responses with all details."""
    id: UUID
    organization_id: UUID
    sale_number: int
    total_amount: float
    total_profit: float = Field(..., description="Total profit (sum of all line profits)")
    status: str = Field(..., description="registered | liquidated | cancelled")
    payment_account_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    
    # Audit fields
    created_by: Optional[UUID] = Field(None, description="User who created the sale")
    liquidated_by: Optional[UUID] = Field(None, description="User who liquidated the sale")
    updated_by: Optional[UUID] = Field(None, description="User who last edited the sale")
    liquidated_at: Optional[datetime] = Field(None, description="Timestamp when the sale was liquidated")
    cancelled_by: Optional[UUID] = Field(None, description="User who cancelled the sale")
    cancelled_at: Optional[datetime] = Field(None, description="Timestamp when the sale was cancelled")

    # Audit names (joined from User model)
    created_by_name: Optional[str] = Field(None, description="Name of user who created the sale")
    liquidated_by_name: Optional[str] = Field(None, description="Name of user who liquidated the sale")
    updated_by_name: Optional[str] = Field(None, description="Name of user who last edited the sale")

    # Joined data from related models
    customer_name: str = Field(..., description="Customer name")
    warehouse_name: Optional[str] = Field(None, description="Warehouse name (null for double-entry)")
    payment_account_name: Optional[str] = Field(None, description="Payment account name (if liquidated)")
    
    # Nested lines and commissions with joined data
    lines: List[SaleLineResponse] = Field(..., description="Sale lines")
    commissions: List[SaleCommissionResponse] = Field(default_factory=list, description="Sale commissions")
    
    # Double-entry link
    double_entry_id: Optional[UUID] = Field(None, description="Link to double-entry operation (if applicable)")

    # Warnings (stock negativo, etc.) — RN-INV-03
    warnings: List[str] = Field(default_factory=list, description="Warnings (e.g., negative stock)")

    model_config = {"from_attributes": True}

    @field_serializer('total_amount', 'total_profit')
    def serialize_decimals(self, value: Decimal) -> float:
        """Convert Decimal to float for JSON serialization."""
        return float(value)


class SaleLiquidateLineUpdate(BaseModel):
    """Precio actualizado para una línea durante liquidación."""
    line_id: UUID = Field(..., description="ID de la línea de venta")
    unit_price: Decimal = Field(..., gt=0, description="Nuevo precio unitario (debe ser > 0)")


class SaleLiquidateRequest(BaseModel):
    """Schema para liquidar venta (confirmar precios, actualizar saldo cliente). Sin pago a cuenta."""
    lines: Optional[List[SaleLiquidateLineUpdate]] = Field(None, description="Precios actualizados por línea")
    commissions: Optional[List[SaleCommissionCreate]] = Field(None, description="Comisiones (reemplazan las existentes)")


class PaginatedSaleResponse(BaseModel):
    """Paginated response for sale lists."""
    items: List[SaleResponse]
    total: int
    skip: int
    limit: int
