"""Retenciones v2 (CC-006): catalogo configurable retention_configs

Tabla nueva ADITIVA, sin backfill (plan-retenciones-v2.md v1.1):
- Una fila = una tarifa: tipo + municipio (solo ica) + concepto opcional (F3)
  + rate_pct. El selector de liquidacion pre-llena monto = % x subtotal
  (editable, Q-07 Johana); el % usado se audita en purchase_retentions.rate/base
  (columnas E2 existentes).
- Unicidad en servicio (D14), soft delete is_active. String+CHECK, no pg_enum.

Prod nunca tuvo E1/E2 (flag NULL) — se aplica solo en dev; prod via /deploy.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-07-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "retention_configs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column(
            "retention_type", sa.String(length=20), nullable=False,
            comment="retefuente | reteiva | ica — catálogo cerrado (D9)",
        ),
        sa.Column(
            "municipality", sa.String(length=60), nullable=True,
            comment="Obligatorio si ica, NULL en los demás (CHECK)",
        ),
        sa.Column(
            "concept", sa.String(length=60), nullable=True,
            comment="Concepto opcional dentro del tipo (F3: compras/servicios/...). NULL = general",
        ),
        sa.Column(
            "rate_pct", sa.Numeric(precision=5, scale=2), nullable=False,
            comment="Tarifa % (0 < x <= 100); el monto final es editable al liquidar",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint(
            "retention_type IN ('retefuente', 'reteiva', 'ica')",
            name="ck_retention_configs_type",
        ),
        sa.CheckConstraint(
            "(retention_type = 'ica') = (municipality IS NOT NULL)",
            name="ck_retention_configs_municipality_ica",
        ),
        sa.CheckConstraint(
            "rate_pct > 0 AND rate_pct <= 100",
            name="ck_retention_configs_rate_range",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_retention_configs_organization_id",
        "retention_configs",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_retention_configs_organization_id", table_name="retention_configs")
    op.drop_table("retention_configs")
