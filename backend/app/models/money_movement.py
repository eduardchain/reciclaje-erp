"""
Modelo MoneyMovement — Movimientos de dinero para tesoreria.

Registra todos los movimientos financieros de la organizacion:
- Pagos a proveedores (payment_to_supplier)
- Cobros a clientes (collection_from_client)
- Gastos operativos (expense)
- Ingresos por servicios (service_income)
- Transferencias entre cuentas (transfer_out / transfer_in)
- Aportes de capital (capital_injection)
- Retiros de capital (capital_return)
- Pagos de comisiones (commission_payment)
- Depositos a provisiones (provision_deposit)
- Gastos desde provisiones (provision_expense)
- Pagos de activos fijos (asset_payment)

Cada movimiento afecta exactamente UNA cuenta de dinero (excepto provision_expense).
Las transferencias crean un par de movimientos vinculados por transfer_pair_id.

Estado:
- confirmed: Movimiento registrado y aplicado (default)
- annulled: Movimiento anulado con reversion de saldos
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrganizationMixin, TimestampMixin, GUID

if TYPE_CHECKING:
    from app.models.money_account import MoneyAccount
    from app.models.third_party import ThirdParty
    from app.models.expense_category import ExpenseCategory
    from app.models.purchase import Purchase
    from app.models.sale import Sale
    from app.models.user import User
    from app.models.business_unit import BusinessUnit


# Tipos de movimiento validos
VALID_MOVEMENT_TYPES = [
    "payment_to_supplier",      # Pago a proveedor: account(-), supplier.balance(+)
    "collection_from_client",   # Cobro a cliente: account(+), customer.balance(-)
    "expense",                  # Gasto operativo: account(-)
    "service_income",           # Ingreso por servicio: account(+)
    "transfer_out",             # Transferencia salida: account(-)
    "transfer_in",              # Transferencia entrada: account(+)
    "capital_injection",        # Aporte de capital: account(+), investor.balance(-)
    "capital_return",           # Retiro de capital: account(-), investor.balance(+)
    "commission_payment",       # Pago de comision: account(-), third_party.balance(+)
    "provision_deposit",        # Deposito a provision: account(-), provision.balance(-)
    "provision_expense",        # Gasto desde provision: provision.balance(+), NO afecta cuenta
    "advance_payment",          # Anticipo a proveedor: account(-), supplier.balance(+)
    "advance_collection",       # Anticipo de cliente: account(+), customer.balance(-)
    "asset_payment",            # Pago de activo fijo: account(-), third_party.balance(+) opcional
    "asset_purchase",           # Compra activo a credito: NO cuenta, supplier.balance(-)
    "expense_accrual",          # Gasto causado (pasivo): NO cuenta, third_party.balance(-), P&L
    "deferred_funding",         # Pago inicial gasto diferido: account(-), third_party.balance(+), NO P&L
    "deferred_expense",         # Cuota gasto diferido: NO cuenta, third_party.balance(-), P&L
    "commission_accrual",       # Comision causada: NO cuenta, third_party.balance(-), P&L
    "depreciation_expense",     # Depreciacion activo: NO cuenta, NO tercero, expense_category, P&L
    "profit_distribution",      # Reparticion utilidades: NO cuenta, socio.balance(-), NO P&L
    "payment_to_generic",       # Pago a tercero generico: account(-), generic.balance(+)
    "collection_from_generic",  # Cobro a tercero generico: account(+), generic.balance(-)
]


class MoneyMovement(Base, OrganizationMixin, TimestampMixin):
    """
    Movimiento de dinero en tesoreria.

    Cada movimiento afecta exactamente una cuenta (account_id).
    El tipo de movimiento define la direccion del efecto y los campos requeridos.
    Las transferencias crean un par vinculado por transfer_pair_id.
    """

    __tablename__ = "money_movements"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid4,
    )

    # Numero secuencial por organizacion
    movement_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Numero secuencial por organizacion (1, 2, 3...)",
    )

    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Fecha del movimiento",
    )

    # Tipo de movimiento (ver VALID_MOVEMENT_TYPES)
    movement_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Tipo: payment_to_supplier, collection_from_client, expense, etc.",
    )

    # Monto (siempre positivo, el tipo define la direccion)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Monto del movimiento (siempre positivo)",
    )

    # Cuenta afectada (None solo para provision_expense)
    account_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("money_accounts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="Cuenta de dinero afectada (None para provision_expense)",
    )

    # Relaciones opcionales segun tipo
    third_party_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("third_parties.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="Tercero involucrado (proveedor, cliente, inversor, comisionista)",
    )

    expense_category_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("expense_categories.id", ondelete="RESTRICT"),
        nullable=True,
        comment="Categoria de gasto (solo para tipo expense)",
    )

    purchase_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("purchases.id", ondelete="SET NULL"),
        nullable=True,
        comment="Compra vinculada (para pagos a proveedor)",
    )

    sale_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("sales.id", ondelete="SET NULL"),
        nullable=True,
        comment="Venta vinculada (para cobros a cliente)",
    )

    # Autorreferencia para pares de transferencia
    transfer_pair_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("money_movements.id", ondelete="SET NULL"),
        nullable=True,
        comment="Movimiento par en transferencias (transfer_out ↔ transfer_in)",
    )

    # Detalles
    description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Descripcion del movimiento",
    )

    reference_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Numero de referencia externo (cheque, transferencia bancaria)",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notas adicionales",
    )

    evidence_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="URL del comprobante adjunto",
    )

    # Estado y auditoria de anulacion
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="confirmed",
        index=True,
        comment="confirmed = aplicado, annulled = anulado con reversion",
    )

    annulled_reason: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Razon de anulacion",
    )

    annulled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Fecha/hora de anulacion",
    )

    annulled_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Usuario que anulo el movimiento",
    )

    # Auditoria de creacion
    created_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Usuario que creo el movimiento",
    )

    # Asignacion a Unidad de Negocio (solo tipos P&L: expense, expense_accrual, etc.)
    # Directo: business_unit_id set, applicable_business_unit_ids NULL
    # Compartido: business_unit_id NULL, applicable_business_unit_ids = [uuid, ...]
    # General: ambos NULL
    business_unit_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("business_units.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Asignacion directa a 1 unidad de negocio",
    )

    applicable_business_unit_ids: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        comment="UNs para prorrateo compartido (array de UUIDs)",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # --- Relationships ---
    business_unit: Mapped[Optional["BusinessUnit"]] = relationship(
        "BusinessUnit",
        foreign_keys=[business_unit_id],
    )

    account: Mapped[Optional["MoneyAccount"]] = relationship(
        "MoneyAccount",
        foreign_keys=[account_id],
    )

    third_party: Mapped[Optional["ThirdParty"]] = relationship(
        "ThirdParty",
        foreign_keys=[third_party_id],
    )

    expense_category: Mapped[Optional["ExpenseCategory"]] = relationship(
        "ExpenseCategory",
        foreign_keys=[expense_category_id],
    )

    purchase: Mapped[Optional["Purchase"]] = relationship(
        "Purchase",
        foreign_keys=[purchase_id],
    )

    sale: Mapped[Optional["Sale"]] = relationship(
        "Sale",
        foreign_keys=[sale_id],
    )

    transfer_pair: Mapped[Optional["MoneyMovement"]] = relationship(
        "MoneyMovement",
        foreign_keys=[transfer_pair_id],
        remote_side=[id],
        uselist=False,
    )

    # --- Table constraints e indexes compuestos ---
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "movement_number",
            name="uq_movement_number_per_org",
        ),
        Index("ix_money_movements_org_date", "organization_id", "date"),
        Index("ix_money_movements_org_type", "organization_id", "movement_type"),
        Index("ix_money_movements_org_account", "organization_id", "account_id"),
        Index("ix_money_movements_org_third_party", "organization_id", "third_party_id"),
        Index("ix_money_movements_org_status", "organization_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<MoneyMovement(id={self.id}, #{self.movement_number}, "
            f"type='{self.movement_type}', amount={self.amount}, "
            f"status='{self.status}')>"
        )
