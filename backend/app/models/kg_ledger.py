"""
Modelos KgLedger — cuentas paralelas en kg de plomo (SAC E1, v0.5 §11.1.1-§11.1.2, §11.1.9).

El KgLedger es el analogo en kg del MoneyMovement: cada evento fisico
(recepcion postconsumo, envio intersede, carga a horno, entrega a Willard)
genera exactamente un KgLedgerMovement con delta_kg firmado. El balance
corriente de una cuenta es SUM(delta_kg) WHERE status='confirmed' —
sin snapshot materializado (patron decision #16).

E1 solo crea la estructura (tablas vacias + constraints); los CRUDs y la
logica de asientos llegan en E2 (plan-sac-e1-configuracion.md §1.2).
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.third_party import ThirdParty
    from app.models.warehouse import Warehouse


class KgLedgerAccount(Base, OrganizationMixin, TimestampMixin):
    """Cuenta paralela en kg de plomo (Willard, intersede, horno, crisol)."""

    __tablename__ = "kg_ledger_accounts"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    code: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="Codigo corto unico por org (WILLARD-BAT-BAQ, INTERSEDE-CV-JM, ...)",
    )

    display_name: Mapped[str] = mapped_column(String(120), nullable=False)

    account_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="willard_baterias | willard_drosses | intersede | intra_horno | crisol",
    )

    warehouse_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=True,
        comment="Sub-saldo por sede (willard_baterias) o sede fisica (intra_horno/crisol); NULL = org-wide",
    )

    third_party_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("third_parties.id", ondelete="RESTRICT"),
        nullable=True,
        comment="Solo cuentas Willard; NULL para internas",
    )

    tolerance_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 4),
        nullable=True,
        comment="Tolerancia (+/- kg) del bloque de discrepancias del cuadre semanal; NULL = sin alerta",
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_kg_ledger_accounts_org_code"),
        # NULLS NOT DISTINCT (PG15+): impide dos cuentas org-wide del mismo tipo
        # incluso con warehouse_id NULL (v0.5 §11.1.1)
        Index(
            "ix_kg_ledger_account_org_type",
            "organization_id",
            "account_type",
            "warehouse_id",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint(
            "account_type NOT IN ('willard_baterias', 'willard_drosses') OR third_party_id IS NOT NULL",
            name="ck_kg_ledger_accounts_willard_tp",
        ),
        CheckConstraint(
            "account_type != 'willard_baterias' OR warehouse_id IS NOT NULL",
            name="ck_kg_ledger_accounts_willard_bat_wh",
        ),
        CheckConstraint(
            "account_type NOT IN ('intra_horno', 'crisol') "
            "OR (warehouse_id IS NOT NULL AND third_party_id IS NULL)",
            name="ck_kg_ledger_accounts_intra_wh",
        ),
        CheckConstraint(
            "account_type != 'intersede' OR third_party_id IS NULL",
            name="ck_kg_ledger_accounts_intersede_tp",
        ),
    )

    # --- Relationships ---
    warehouse: Mapped[Optional["Warehouse"]] = relationship(
        "Warehouse", foreign_keys=[warehouse_id]
    )
    third_party: Mapped[Optional["ThirdParty"]] = relationship(
        "ThirdParty", foreign_keys=[third_party_id]
    )

    def __repr__(self) -> str:
        return f"<KgLedgerAccount {self.code} ({self.account_type})>"


class KgLedgerMovement(Base, OrganizationMixin, TimestampMixin):
    """Asiento en kg — analogo del MoneyMovement para el libro paralelo."""

    __tablename__ = "kg_ledger_movements"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    account_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("kg_ledger_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )

    delta_kg: Mapped[Decimal] = mapped_column(
        Numeric(14, 4),
        nullable=False,
        comment="Firmado: positivo = acumula deuda / carga; negativo = descarga / entrega",
    )

    transaction_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Fecha de negocio — BusinessDate mediodia UTC via schema (app/utils/dates.py)",
    )

    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    source_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        comment="postconsumo_receipt | drosses_receipt | willard_subbalance_move | intersede_* | "
        "furnace_* | crucible_* | willard_delivery | manual_adjustment | migration_initial_load",
    )

    source_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        nullable=True,
        comment="Referencia polimorfica al evento origen segun source_type (sin FK)",
    )

    inventory_movement_id: Mapped[Optional[UUID]] = mapped_column(
        GUID(),
        ForeignKey("inventory_movements.id", ondelete="SET NULL"),
        nullable=True,
        comment="Poblado cuando el evento kg esta atado a un movimiento fisico",
    )

    conversion_formula_snapshot: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Snapshot exacto de la formula aplicada al momento del evento (Anexo D)",
    )

    created_by: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="confirmed",
        comment="confirmed | annulled (soft, patron decision #48)",
    )

    annulled_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    annulled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    annulled_by: Mapped[Optional[UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        CheckConstraint("delta_kg != 0", name="ck_kg_ledger_movements_delta_nonzero"),
        Index("ix_kg_movement_account_date", "account_id", text("transaction_date DESC")),
        Index("ix_kg_movement_source", "source_type", "source_id"),
        Index("ix_kg_movement_org_status", "organization_id", "status"),
    )

    # --- Relationships ---
    account: Mapped["KgLedgerAccount"] = relationship(
        "KgLedgerAccount", foreign_keys=[account_id]
    )

    def __repr__(self) -> str:
        return f"<KgLedgerMovement {self.source_type} {self.delta_kg}kg ({self.status})>"


class KgLedgerReconciliationSeal(Base, OrganizationMixin, TimestampMixin):
    """Firma inmutable del cuadre semanal Willard ('OK del viernes', v0.5 §11.1.9)."""

    __tablename__ = "kg_ledger_reconciliation_seals"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    week_ending_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Viernes de cierre de la semana",
    )

    account_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("kg_ledger_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Una fila por cuenta kg (tipicamente Willard Baterias + Drosses)",
    )

    saldos_cierre: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Snapshot de saldo cierre + apertura + totales por tipo de movimiento",
    )

    hash_movements: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 sobre la lista ordenada de KgLedgerMovement.id de la semana — detecta ediciones post-firma",
    )

    signed_by: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "account_id",
            "week_ending_date",
            name="uq_kg_seals_org_account_week",
        ),
    )

    def __repr__(self) -> str:
        return f"<KgLedgerReconciliationSeal {self.week_ending_date} account={self.account_id}>"
