"""CC-014: precio de mercado del plomo (lead_market_prices)

Aditiva pura: una tabla nueva, cero cambios a tablas compartidas, sin backfill.
La valoracion de la deuda en plomo se lee de aqui; sin filas, el balance se
comporta exactamente como hoy.

Revision ID: d7c9e1f3a5b7
Revises: f3a4b5c6d7e9
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d7c9e1f3a5b7"
down_revision = "f3a4b5c6d7e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lead_market_prices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("price_per_kg", sa.Numeric(12, 2), nullable=False),
        sa.Column("effective_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        # 🔴 server_default REPETIDO a proposito: TimestampMixin lo declara en el
        # modelo, la BD de test se crea desde los modelos y la de prod desde las
        # migraciones, y schema_parity_check excluye server_default a proposito.
        # Esa direccion no la cubre NINGUN gate: es el defecto que costo un 500
        # en el primer POST de las salidas de plomo (#100).
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("price_per_kg > 0", name="ck_lead_market_prices_price_positive"),
    )
    # Indice del OrganizationMixin (index=True en el modelo)
    op.create_index(
        "ix_lead_market_prices_organization_id",
        "lead_market_prices",
        ["organization_id"],
    )
    # Vigencia: el orden canonico es effective_date DESC
    op.create_index(
        "ix_lmp_org_effective",
        "lead_market_prices",
        ["organization_id", sa.text("effective_date DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_lmp_org_effective", table_name="lead_market_prices")
    op.drop_index("ix_lead_market_prices_organization_id", table_name="lead_market_prices")
    op.drop_table("lead_market_prices")
