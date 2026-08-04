"""
Schemas KgLedger (SAC E2, v0.5 §12.1.1, plan-sac-e2 D1/D6/D14/D15/D16).

El Literal de creacion manual solo permite 'manual_adjustment' (D1): los
source_types de negocio (postconsumo_receipt, drosses_receipt) los emite SOLO
el servicio de inbound; los 9 restantes de §4.3 llegan con E3/E4.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.dates import BusinessDate

KgAccountType = Literal[
    "willard_baterias", "willard_drosses", "intersede", "intra_horno", "crisol"
]


class KgLedgerAccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1, max_length=32)
    display_name: str = Field(..., min_length=1, max_length=120)
    account_type: KgAccountType
    warehouse_id: Optional[UUID] = None
    third_party_id: Optional[UUID] = None
    tolerance_kg: Optional[Decimal] = Field(
        None, ge=0, description="Tolerancia del cuadre semanal (± kg); NULL = sin alerta"
    )


class KgLedgerAccountUpdate(BaseModel):
    """Solo metadata — account_type y FKs son inmutables post-creacion (§12.1.1)."""
    model_config = ConfigDict(extra="forbid")

    display_name: Optional[str] = Field(None, min_length=1, max_length=120)
    tolerance_kg: Optional[Decimal] = Field(None, ge=0)
    is_active: Optional[bool] = None


class KgLedgerAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    display_name: str
    account_type: str
    warehouse_id: Optional[UUID] = None
    warehouse_name: Optional[str] = None
    third_party_id: Optional[UUID] = None
    third_party_name: Optional[str] = None
    tolerance_kg: Optional[Decimal] = None
    current_balance_kg: Decimal = Decimal("0")
    is_active: bool
    created_at: datetime


class KgLedgerMovementManualCreate(BaseModel):
    """Movimiento manual auditado (source_type='manual_adjustment', §4.3)."""
    model_config = ConfigDict(extra="forbid")

    account_id: UUID
    delta_kg: Decimal
    transaction_date: BusinessDate
    description: str = Field(..., min_length=1, max_length=300)
    reason: str = Field(..., min_length=1, max_length=180, description="Motivo obligatorio")

    @field_validator("delta_kg")
    @classmethod
    def delta_nonzero(cls, v: Decimal) -> Decimal:
        if v == 0:
            raise ValueError("delta_kg no puede ser 0 — los movimientos nulos se anulan, no se insertan")
        return v

    @field_validator("transaction_date")
    @classmethod
    def not_future(cls, v: datetime) -> datetime:
        # Canon §11.1.2 L1917 + filosofia anti back-dating #62 (D15)
        if v.date() > datetime.now(timezone.utc).date():
            raise ValueError("transaction_date no puede ser futura")
        return v


class KgLedgerMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    delta_kg: Decimal
    transaction_date: datetime
    description: Optional[str] = None
    source_type: str
    source_id: Optional[UUID] = None
    inventory_movement_id: Optional[UUID] = None
    conversion_formula_snapshot: Optional[dict] = None
    status: str
    annulled_reason: Optional[str] = None
    annulled_at: Optional[datetime] = None
    created_at: datetime


class KgLedgerStatementRow(KgLedgerMovementResponse):
    balance_after_kg: Decimal


class KgLedgerStatementResponse(BaseModel):
    account: KgLedgerAccountResponse
    opening_balance_kg: Decimal
    movements: list[KgLedgerStatementRow]
    current_balance_kg: Decimal


class KgLedgerSummaryAccount(BaseModel):
    account_id: UUID
    code: str
    display_name: str
    account_type: str
    warehouse_id: Optional[UUID] = None
    warehouse_name: Optional[str] = None
    balance_kg: Decimal
    tolerance_kg: Optional[Decimal] = None
    last_movement_at: Optional[datetime] = None
    is_active: bool


class KgLedgerSummaryResponse(BaseModel):
    accounts: list[KgLedgerSummaryAccount]
    total_willard_kg: Decimal
    total_intersede_kg: Decimal
    total_intra_horno_kg: Decimal
    total_crisol_kg: Decimal


class KgLedgerAnnulRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)
