"""
Schemas de Obligaciones Financieras (plan F).

Prestamos por pagar (payable: nos prestaron) y por cobrar (receivable:
prestamos nosotros). La direccion de la obligacion decide el movement type
concreto de cada accion — el frontend solo conoce las acciones.
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.utils.dates import BusinessDate

PERIOD_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


# ======================================================================
# Requests
# ======================================================================

class ObligationDisbursementData(BaseModel):
    """Desembolso inicial (modo 'con desembolso')."""
    account_id: UUID = Field(..., description="Cuenta de donde sale/entra el dinero")
    amount: Decimal = Field(..., gt=0, description="Monto del desembolso")
    date: BusinessDate = Field(..., description="Fecha del desembolso")


class FinancialObligationCreate(BaseModel):
    """Crear obligacion: con desembolso (crea MM) o desde saldo existente (migracion, sin MM)."""
    third_party_id: UUID = Field(..., description="Tercero categoria Obligaciones Financieras")
    direction: Literal["payable", "receivable"] = Field(
        ..., description="payable = nos prestaron | receivable = prestamos nosotros"
    )
    monthly_rate: Decimal = Field(
        ..., gt=0, le=100, description="% mensual fijo de por vida (2.00 = 2%)"
    )
    mode: Literal["disbursement", "from_balance"] = Field(
        ..., description="disbursement = desembolso inicial | from_balance = desde saldo actual del tercero"
    )
    disbursement: Optional[ObligationDisbursementData] = None
    accrual_start_period: Optional[str] = Field(
        None, pattern=PERIOD_PATTERN,
        description='"YYYY-MM": primer mes que causa el modulo. Default: mes del desembolso o mes actual',
    )
    notes: Optional[str] = Field(None, max_length=500)

    @model_validator(mode="after")
    def validate_mode(self):
        if self.mode == "disbursement" and self.disbursement is None:
            raise ValueError("El modo 'disbursement' requiere los datos del desembolso")
        if self.mode == "from_balance" and self.disbursement is not None:
            raise ValueError("El modo 'from_balance' no lleva desembolso (el saldo ya existe)")
        return self


class ObligationMovementCreate(BaseModel):
    """Abono/recaudo de capital, pago/recaudo de intereses o desembolso adicional."""
    amount: Decimal = Field(..., gt=0)
    account_id: UUID = Field(..., description="Cuenta afectada")
    date: BusinessDate = Field(..., description="Fecha del movimiento")
    reference_number: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class AccruePendingRequest(BaseModel):
    """Batch de causacion. La categoria de gasto es obligatoria si hay causaciones payable."""
    expense_category_id: Optional[UUID] = Field(
        None, description="Categoria de gasto para intereses por pagar (ej: Intereses)"
    )


class ObligationAccrueRequest(BaseModel):
    """Causacion individual de una obligacion (vencidos + tramo de cierre opcional)."""
    expense_category_id: Optional[UUID] = Field(
        None, description="Categoria de gasto para intereses por pagar (ej: Intereses)"
    )
    include_current_tranche: bool = Field(
        False,
        description="Causar tambien el tramo del mes en curso (solo con capital en $0)",
    )


class ObligationAnnulRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500, description="Razon de la anulacion")


# ======================================================================
# Responses
# ======================================================================

class FinancialObligationResponse(BaseModel):
    id: UUID
    organization_id: UUID
    third_party_id: UUID
    third_party_name: str = ""
    direction: str
    monthly_rate: Decimal
    capital_balance: Decimal
    pending_interest: Decimal
    accrual_start_period: str
    last_accrued_period: Optional[str] = None
    disbursement_date: Optional[datetime] = None
    status: str
    notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PendingAccrualItem(BaseModel):
    """Preview de una causacion pendiente (un periodo cerrado de una obligacion)."""
    obligation_id: UUID
    third_party_name: str
    direction: str
    period: str
    amount: Decimal
    breakdown: str


class PendingAccrualsResponse(BaseModel):
    items: list[PendingAccrualItem]
    total_payable: Decimal
    total_receivable: Decimal
    has_payable: bool


class AccruePreviewResponse(BaseModel):
    """Preview de causacion de UNA obligacion: vencidos + tramo de cierre disponible."""
    items: list[PendingAccrualItem]
    current_tranche: Optional[PendingAccrualItem] = None
    has_payable: bool


class AccrueResultResponse(BaseModel):
    created_count: int
    total_payable: Decimal
    total_receivable: Decimal


class ObligationDirectionSummary(BaseModel):
    """KPIs de una direccion (tab Por Pagar / Por Cobrar)."""
    direction: str
    count: int
    total_capital: Decimal
    total_pending_interest: Decimal
    weighted_avg_rate: Decimal
    current_month_projection: Decimal


class ObligationSummaryResponse(BaseModel):
    payable: ObligationDirectionSummary
    receivable: ObligationDirectionSummary
