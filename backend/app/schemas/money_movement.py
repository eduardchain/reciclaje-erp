"""
Schemas Pydantic para el modelo MoneyMovement (Movimientos de Dinero).

Schemas especializados por tipo de operacion:
- SupplierPaymentCreate: Pago a proveedor
- CustomerCollectionCreate: Cobro a cliente
- ExpenseCreate: Gasto operativo
- ServiceIncomeCreate: Ingreso por servicio
- TransferCreate: Transferencia entre cuentas
- CapitalInjectionCreate: Aporte de capital
- CapitalReturnCreate: Retiro de capital
- CommissionPaymentCreate: Pago de comision
- ProvisionDepositCreate: Deposito a provision
- ProvisionExpenseCreate: Gasto desde provision
- AdvancePaymentCreate: Anticipo a proveedor
- AdvanceCollectionCreate: Anticipo de cliente
- AssetPaymentCreate: Pago de activo fijo
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer, model_validator

from app.utils.dates import BusinessDate


# ---------------------------------------------------------------------------
# Schemas de creacion — uno por tipo de operacion
# ---------------------------------------------------------------------------

class SupplierPaymentCreate(BaseModel):
    """Pago a proveedor — account(-), supplier.balance(+)."""
    supplier_id: UUID = Field(..., description="ID del proveedor (is_supplier=True)")
    amount: Decimal = Field(..., gt=0, description="Monto a pagar")
    account_id: UUID = Field(..., description="Cuenta de donde sale el dinero")
    purchase_id: Optional[UUID] = Field(None, description="Compra vinculada (opcional)")
    date: BusinessDate = Field(..., description="Fecha del pago")
    description: Optional[str] = Field(None, max_length=500)
    reference_number: Optional[str] = Field(None, max_length=100)
    evidence_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None


class CustomerCollectionCreate(BaseModel):
    """Cobro a cliente — account(+), customer.balance(-)."""
    customer_id: UUID = Field(..., description="ID del cliente (is_customer=True)")
    amount: Decimal = Field(..., gt=0, description="Monto cobrado")
    account_id: UUID = Field(..., description="Cuenta donde entra el dinero")
    sale_id: Optional[UUID] = Field(None, description="Venta vinculada (opcional)")
    date: BusinessDate = Field(..., description="Fecha del cobro")
    description: Optional[str] = Field(None, max_length=500)
    reference_number: Optional[str] = Field(None, max_length=100)
    evidence_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None


class ExpenseCreate(BaseModel):
    """Gasto operativo — account(-)."""
    amount: Decimal = Field(..., gt=0, description="Monto del gasto")
    expense_category_id: UUID = Field(..., description="Categoria del gasto")
    account_id: UUID = Field(..., description="Cuenta de donde sale el dinero")
    description: str = Field(..., min_length=1, max_length=500, description="Descripcion del gasto")
    date: BusinessDate = Field(..., description="Fecha del gasto")
    third_party_id: Optional[UUID] = Field(None, description="Tercero receptor (opcional)")
    reference_number: Optional[str] = Field(None, max_length=100)
    evidence_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None
    # Asignacion a Unidad de Negocio
    business_unit_id: Optional[UUID] = Field(None, description="Directo: 100% a esta UN")
    applicable_business_unit_ids: Optional[list[UUID]] = Field(None, description="Compartido: prorrateo entre estas UNs")

    @model_validator(mode="after")
    def validate_business_unit_allocation(self):
        if self.business_unit_id and self.applicable_business_unit_ids:
            raise ValueError("Seleccione asignacion directa O compartida, no ambas")
        # Array vacio = General (normalizar a None)
        if self.applicable_business_unit_ids is not None and len(self.applicable_business_unit_ids) == 0:
            self.applicable_business_unit_ids = None
        return self


class ServiceIncomeCreate(BaseModel):
    """Ingreso por servicio — account(+)."""
    amount: Decimal = Field(..., gt=0, description="Monto del ingreso")
    account_id: UUID = Field(..., description="Cuenta donde entra el dinero")
    description: str = Field(..., min_length=1, max_length=500, description="Descripcion del ingreso")
    date: BusinessDate = Field(..., description="Fecha del ingreso")
    third_party_id: Optional[UUID] = Field(None, description="Tercero (opcional)")
    reference_number: Optional[str] = Field(None, max_length=100)
    evidence_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None


class TransferCreate(BaseModel):
    """Transferencia entre cuentas — crea par transfer_out + transfer_in."""
    amount: Decimal = Field(..., gt=0, description="Monto a transferir")
    source_account_id: UUID = Field(..., description="Cuenta origen")
    destination_account_id: UUID = Field(..., description="Cuenta destino")
    date: BusinessDate = Field(..., description="Fecha de la transferencia")
    description: str = Field(..., min_length=1, max_length=500, description="Descripcion")
    reference_number: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class CapitalInjectionCreate(BaseModel):
    """Aporte de capital — account(+), investor.balance(-)."""
    investor_id: UUID = Field(..., description="ID del inversor (is_investor=True)")
    amount: Decimal = Field(..., gt=0, description="Monto aportado")
    account_id: UUID = Field(..., description="Cuenta donde entra el capital")
    date: BusinessDate = Field(..., description="Fecha del aporte")
    description: Optional[str] = Field(None, max_length=500)
    reference_number: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class CapitalReturnCreate(BaseModel):
    """Retiro de capital — account(-), investor.balance(+)."""
    investor_id: UUID = Field(..., description="ID del inversor (is_investor=True)")
    amount: Decimal = Field(..., gt=0, description="Monto a retirar")
    account_id: UUID = Field(..., description="Cuenta de donde sale el capital")
    date: BusinessDate = Field(..., description="Fecha del retiro")
    description: Optional[str] = Field(None, max_length=500)
    reference_number: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class CommissionPaymentCreate(BaseModel):
    """Pago de comision — account(-), third_party.balance(+)."""
    third_party_id: UUID = Field(..., description="Tercero receptor de la comision")
    amount: Decimal = Field(..., gt=0, description="Monto a pagar")
    account_id: UUID = Field(..., description="Cuenta de donde sale el dinero")
    date: BusinessDate = Field(..., description="Fecha del pago")
    description: Optional[str] = Field(None, max_length=500)
    reference_number: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class ProvisionDepositCreate(BaseModel):
    """Deposito a provision — account(-), provision.balance(-)."""
    provision_id: UUID = Field(..., description="ID de la provision (is_provision=True)")
    amount: Decimal = Field(..., gt=0, description="Monto a depositar")
    account_id: UUID = Field(..., description="Cuenta de donde sale el dinero")
    date: BusinessDate = Field(..., description="Fecha del deposito")
    description: Optional[str] = Field(None, max_length=500)
    reference_number: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class ProvisionExpenseCreate(BaseModel):
    """Gasto desde provision — provision.balance(+), NO afecta cuentas de dinero."""
    provision_id: UUID = Field(..., description="ID de la provision (is_provision=True)")
    amount: Decimal = Field(..., gt=0, description="Monto del gasto")
    expense_category_id: UUID = Field(..., description="Categoria del gasto")
    date: BusinessDate = Field(..., description="Fecha del gasto")
    description: str = Field(..., min_length=1, max_length=500, description="Descripcion del gasto")
    reference_number: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None
    business_unit_id: Optional[UUID] = Field(None, description="Directo: 100% a esta UN")
    applicable_business_unit_ids: Optional[list[UUID]] = Field(None, description="Compartido: prorrateo entre estas UNs")

    @model_validator(mode="after")
    def validate_business_unit_allocation(self):
        if self.business_unit_id and self.applicable_business_unit_ids:
            raise ValueError("Seleccione asignacion directa O compartida, no ambas")
        if self.applicable_business_unit_ids is not None and len(self.applicable_business_unit_ids) == 0:
            self.applicable_business_unit_ids = None
        return self


class AdvancePaymentCreate(BaseModel):
    """Anticipo a proveedor — account(-), supplier.balance(+)."""
    supplier_id: UUID = Field(..., description="ID del proveedor (is_supplier=True)")
    amount: Decimal = Field(..., gt=0, description="Monto del anticipo")
    account_id: UUID = Field(..., description="Cuenta de donde sale el dinero")
    date: BusinessDate = Field(..., description="Fecha del anticipo")
    description: Optional[str] = Field(None, max_length=500)
    reference_number: Optional[str] = Field(None, max_length=100)
    evidence_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None


class AdvanceCollectionCreate(BaseModel):
    """Anticipo de cliente — account(+), customer.balance(-)."""
    customer_id: UUID = Field(..., description="ID del cliente (is_customer=True)")
    amount: Decimal = Field(..., gt=0, description="Monto del anticipo")
    account_id: UUID = Field(..., description="Cuenta donde entra el dinero")
    date: BusinessDate = Field(..., description="Fecha del anticipo")
    description: Optional[str] = Field(None, max_length=500)
    reference_number: Optional[str] = Field(None, max_length=100)
    evidence_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None


class AssetPaymentCreate(BaseModel):
    """Pago de activo fijo — account(-), third_party.balance(+) opcional."""
    amount: Decimal = Field(..., gt=0, description="Monto del pago")
    account_id: UUID = Field(..., description="Cuenta de donde sale el dinero")
    description: str = Field(..., min_length=1, max_length=500, description="Descripcion del activo")
    date: BusinessDate = Field(..., description="Fecha del pago")
    third_party_id: Optional[UUID] = Field(None, description="Tercero vendedor (opcional, cualquier tipo)")
    reference_number: Optional[str] = Field(None, max_length=100)
    evidence_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None


class ExpenseAccrualCreate(BaseModel):
    """Gasto causado (pasivo) — NO cuenta, third_party.balance(-), aparece en P&L."""
    third_party_id: UUID = Field(..., description="Tercero (cualquier tercero activo)")
    amount: Decimal = Field(..., gt=0, description="Monto del gasto causado")
    expense_category_id: UUID = Field(..., description="Categoria del gasto")
    date: BusinessDate = Field(..., description="Fecha del gasto")
    description: str = Field(..., min_length=1, max_length=500, description="Descripcion del gasto")
    reference_number: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None
    business_unit_id: Optional[UUID] = Field(None, description="Directo: 100% a esta UN")
    applicable_business_unit_ids: Optional[list[UUID]] = Field(None, description="Compartido: prorrateo entre estas UNs")

    @model_validator(mode="after")
    def validate_business_unit_allocation(self):
        if self.business_unit_id and self.applicable_business_unit_ids:
            raise ValueError("Seleccione asignacion directa O compartida, no ambas")
        if self.applicable_business_unit_ids is not None and len(self.applicable_business_unit_ids) == 0:
            self.applicable_business_unit_ids = None
        return self


class GenericPaymentCreate(BaseModel):
    """Pago a tercero generico — account(-), generic.balance(+)."""
    third_party_id: UUID = Field(..., description="ID del tercero generico")
    amount: Decimal = Field(..., gt=0, description="Monto a pagar")
    account_id: UUID = Field(..., description="Cuenta de donde sale el dinero")
    date: BusinessDate = Field(..., description="Fecha del pago")
    description: Optional[str] = Field(None, max_length=500)
    reference_number: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class GenericCollectionCreate(BaseModel):
    """Cobro a tercero generico — account(+), generic.balance(-)."""
    third_party_id: UUID = Field(..., description="ID del tercero generico")
    amount: Decimal = Field(..., gt=0, description="Monto a cobrar")
    account_id: UUID = Field(..., description="Cuenta donde entra el dinero")
    date: BusinessDate = Field(..., description="Fecha del cobro")
    description: Optional[str] = Field(None, max_length=500)
    reference_number: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class ThirdPartyTransferCreate(BaseModel):
    """Transferencia entre terceros — NO cuenta, source.balance(-), dest.balance(+)."""
    source_third_party_id: UUID = Field(..., description="Tercero que paga (balance baja)")
    destination_third_party_id: UUID = Field(..., description="Tercero que recibe (balance sube)")
    amount: Decimal = Field(..., gt=0, description="Monto de la transferencia")
    date: BusinessDate = Field(..., description="Fecha de la transferencia")
    description: str = Field(..., min_length=1, max_length=500, description="Descripcion")
    reference_number: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class ThirdPartyAdjustmentCreate(BaseModel):
    """Ajuste de saldo de tercero — NO cuenta, clasificacion P&L por adjustment_class."""
    third_party_id: UUID = Field(..., description="Tercero a ajustar")
    amount: Decimal = Field(..., gt=0, description="Monto del ajuste (siempre positivo)")
    adjustment_class: Literal["loss", "gain"] = Field(..., description="Clasificacion P&L: loss=gasto, gain=ingreso")
    date: BusinessDate = Field(..., description="Fecha del ajuste")
    description: str = Field(..., min_length=1, max_length=500, description="Descripcion del ajuste")
    adjustment_reason: Optional[str] = Field(None, max_length=200, description="Motivo del ajuste")
    notes: Optional[str] = None


class BatchExpenseItem(BaseModel):
    """Un gasto individual dentro del batch."""
    amount: Decimal = Field(..., gt=0, description="Monto del gasto")
    expense_category_id: UUID = Field(..., description="Categoria de gasto")
    account_id: UUID = Field(..., description="Cuenta de dinero")
    date: BusinessDate = Field(..., description="Fecha del gasto")
    description: str = Field(..., min_length=1, max_length=500, description="Descripcion")
    third_party_id: Optional[UUID] = None
    reference_number: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None
    business_unit_id: Optional[UUID] = None
    applicable_business_unit_ids: Optional[list[UUID]] = None

    @model_validator(mode="after")
    def validate_bu_allocation(self):
        if self.business_unit_id and self.applicable_business_unit_ids:
            raise ValueError("Seleccione asignacion directa O compartida, no ambas")
        if self.applicable_business_unit_ids is not None and len(self.applicable_business_unit_ids) == 0:
            self.applicable_business_unit_ids = None
        return self


class BatchExpenseCreate(BaseModel):
    """Batch de gastos — hasta 50 items en una transaccion."""
    items: list[BatchExpenseItem] = Field(..., min_length=1, max_length=50)


# ---------------------------------------------------------------------------
# Schema de anulacion
# ---------------------------------------------------------------------------

class UpdateClassificationRequest(BaseModel):
    """Editar clasificacion de gasto en movimiento existente."""
    expense_category_id: UUID = Field(..., description="Categoria de gasto (obligatoria)")
    business_unit_id: Optional[UUID] = Field(None, description="Directo: 100% a esta UN")
    applicable_business_unit_ids: Optional[list[UUID]] = Field(None, description="Compartido: prorrateo entre estas UNs")

    @model_validator(mode="after")
    def validate_business_unit_allocation(self):
        if self.business_unit_id and self.applicable_business_unit_ids:
            raise ValueError("Seleccione asignacion directa O compartida, no ambas")
        if self.applicable_business_unit_ids is not None and len(self.applicable_business_unit_ids) == 0:
            self.applicable_business_unit_ids = None
        return self


class AnnulMovementRequest(BaseModel):
    """Solicitud de anulacion de movimiento."""
    reason: str = Field(..., min_length=1, max_length=500, description="Razon de anulacion")


# ---------------------------------------------------------------------------
# Schema de respuesta
# ---------------------------------------------------------------------------

class MoneyMovementResponse(BaseModel):
    """Respuesta completa de un movimiento de dinero."""
    id: UUID
    organization_id: UUID
    movement_number: int
    date: datetime
    movement_type: str
    amount: float
    description: str

    # Cuenta (None para provision_expense)
    account_id: Optional[UUID] = None
    account_name: Optional[str] = None

    # Relaciones opcionales
    third_party_id: Optional[UUID] = None
    third_party_name: Optional[str] = None
    expense_category_id: Optional[UUID] = None
    expense_category_name: Optional[str] = None
    purchase_id: Optional[UUID] = None
    sale_id: Optional[UUID] = None
    transfer_pair_id: Optional[UUID] = None

    # Asignacion a Unidad de Negocio
    business_unit_id: Optional[UUID] = None
    business_unit_name: Optional[str] = None
    applicable_business_unit_ids: Optional[list[UUID]] = None
    applicable_business_unit_names: Optional[list[str]] = None

    # Ajuste de terceros
    adjustment_class: Optional[str] = None

    # Detalles
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    evidence_url: Optional[str] = None

    # Estado
    status: str
    annulled_reason: Optional[str] = None
    annulled_at: Optional[datetime] = None
    annulled_by: Optional[UUID] = None

    # Auditoria
    created_by: Optional[UUID] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer('amount')
    def serialize_amount(self, value: Decimal) -> float:
        return float(value)


class AnnulMovementResponse(MoneyMovementResponse):
    """Respuesta de anulacion con posibles warnings."""
    warnings: list[str] = []


class MoneyMovementWithBalance(MoneyMovementResponse):
    """Movimiento con saldo acumulado para estado de cuenta."""
    balance_after: Optional[float] = None


class MoneyMovementSummary(BaseModel):
    """Resumen de movimientos por tipo para un periodo."""
    movement_type: str
    count: int
    total_amount: float


class PaginatedMoneyMovementResponse(BaseModel):
    """Respuesta paginada de movimientos de dinero."""
    items: list[MoneyMovementResponse]
    total: int
    skip: int
    limit: int
