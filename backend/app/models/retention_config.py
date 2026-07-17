"""
RetentionConfig — catálogo configurable de retenciones (SAC, CC-006 / plan retenciones v2).

Una fila = una tarifa: tipo (retefuente|reteiva|ica) + municipio (solo ica) +
concepto opcional (F3 QA: ReteFuente varía por concepto — compras 2,5%,
servicios 4%...) + % tarifa. Al liquidar, el selector lista las configs y
pre-llena monto = rate_pct × subtotal (editable — Q-07 Johana).

Unicidad (org, tipo, municipio-normalizado, concepto-normalizado) en SERVICIO,
no BD (precedente D14-E1: maestros con soft delete). Editable in-place: la
auditoría del % usado vive en purchase_retentions.rate/base por liquidación.
"""
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, GUID, OrganizationMixin, TimestampMixin


class RetentionConfig(Base, OrganizationMixin, TimestampMixin):
    """Tarifa configurada de retención (SAC-only, flag-gated en endpoints)."""

    __tablename__ = "retention_configs"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    retention_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="retefuente | reteiva | ica — catálogo cerrado (D9)",
    )

    municipality: Mapped[Optional[str]] = mapped_column(
        String(60),
        nullable=True,
        comment="Obligatorio si ica, NULL en los demás (CHECK)",
    )

    concept: Mapped[Optional[str]] = mapped_column(
        String(60),
        nullable=True,
        comment="Concepto opcional dentro del tipo (F3: compras/servicios/...). NULL = general",
    )

    rate_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        comment="Tarifa % (0 < x <= 100); el monto final es editable al liquidar",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    __table_args__ = (
        # String+CHECK, NO pg_enum (regla schema_parity_check E1/E2)
        CheckConstraint(
            "retention_type IN ('retefuente', 'reteiva', 'ica')",
            name="ck_retention_configs_type",
        ),
        # Municipio va con ica y solo con ica
        CheckConstraint(
            "(retention_type = 'ica') = (municipality IS NOT NULL)",
            name="ck_retention_configs_municipality_ica",
        ),
        CheckConstraint(
            "rate_pct > 0 AND rate_pct <= 100",
            name="ck_retention_configs_rate_range",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<RetentionConfig {self.retention_type}"
            f"{' ' + self.municipality if self.municipality else ''}"
            f"{' [' + self.concept + ']' if self.concept else ''} {self.rate_pct}%>"
        )
