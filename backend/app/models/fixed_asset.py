"""
Modelo FixedAsset — Activos fijos con depreciacion mensual.

Representa equipos y bienes de la empresa que se deprecian mensualmente.
Ejemplo: Retroexcavadora $630M, tasa 1% mensual → cuota $6.3M/mes.

Flujo:
1. Al crear: se registra el activo con su valor de compra
2. Cada mes: se aplica depreciacion (depreciation_expense en P&L)
3. Al completar: status = fully_depreciated, current_value = salvage_value
4. Dar de baja: depreciacion acelerada si queda valor pendiente
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrganizationMixin, TimestampMixin, GUID

if TYPE_CHECKING:
    from app.models.expense_category import ExpenseCategory
    from app.models.third_party import ThirdParty
    from app.models.money_movement import MoneyMovement
    from app.models.business_unit import BusinessUnit


VALID_ASSET_STATUSES = ["active", "fully_depreciated", "disposed"]


class FixedAsset(Base, OrganizationMixin, TimestampMixin):
    """Activo fijo con depreciacion lineal mensual."""

    __tablename__ = "fixed_assets"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    name: Mapped[str] = mapped_column(String(200), nullable=False)

    asset_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Fechas
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)

    depreciation_start_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Valores financieros
    purchase_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    salvage_value: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0"),
    )

    current_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    accumulated_depreciation: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0"),
    )

    # Depreciacion
    depreciation_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    monthly_depreciation: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    useful_life_months: Mapped[int] = mapped_column(Integer, nullable=False)

    # Categoria de gasto (para P&L)
    expense_category_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("expense_categories.id", ondelete="RESTRICT"), nullable=False,
    )

    # Proveedor (referencia opcional)
    third_party_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("third_parties.id", ondelete="SET NULL"), nullable=True,
    )

    # Vinculo a asset_payment (opcional)
    purchase_movement_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("money_movements.id", ondelete="SET NULL"), nullable=True,
    )

    # Asignacion a Unidad de Negocio (hereda a depreciation_expense)
    business_unit_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("business_units.id", ondelete="SET NULL"), nullable=True,
    )

    applicable_business_unit_ids: Mapped[Optional[list]] = mapped_column(
        JSONB, nullable=True,
    )

    # Estado
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    # Baja
    disposed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    disposed_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    disposal_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Auditoria
    created_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    # Relationships
    expense_category: Mapped["ExpenseCategory"] = relationship(
        "ExpenseCategory", foreign_keys=[expense_category_id],
    )

    third_party: Mapped[Optional["ThirdParty"]] = relationship(
        "ThirdParty", foreign_keys=[third_party_id],
    )

    purchase_movement: Mapped[Optional["MoneyMovement"]] = relationship(
        "MoneyMovement", foreign_keys=[purchase_movement_id],
    )

    business_unit: Mapped[Optional["BusinessUnit"]] = relationship(
        "BusinessUnit", foreign_keys=[business_unit_id],
    )

    depreciations: Mapped[List["AssetDepreciation"]] = relationship(
        "AssetDepreciation",
        back_populates="fixed_asset",
        order_by="AssetDepreciation.depreciation_number",
    )

    __table_args__ = (
        Index("ix_fixed_assets_org_status", "organization_id", "status"),
    )


class AssetDepreciation(Base, TimestampMixin):
    """Registro de cada cuota de depreciacion aplicada."""

    __tablename__ = "asset_depreciations"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    fixed_asset_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("fixed_assets.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    depreciation_number: Mapped[int] = mapped_column(Integer, nullable=False)

    period: Mapped[str] = mapped_column(String(10), nullable=False)  # "YYYY-MM" o "YYYY-MMB" (baja)

    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    accumulated_after: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    current_value_after: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    money_movement_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("money_movements.id", ondelete="RESTRICT"), nullable=False,
    )

    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    applied_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    fixed_asset: Mapped["FixedAsset"] = relationship(
        "FixedAsset", back_populates="depreciations",
    )

    money_movement: Mapped["MoneyMovement"] = relationship(
        "MoneyMovement", foreign_keys=[money_movement_id],
    )

    __table_args__ = (
        UniqueConstraint("fixed_asset_id", "period", name="uq_asset_depreciation_period"),
    )
