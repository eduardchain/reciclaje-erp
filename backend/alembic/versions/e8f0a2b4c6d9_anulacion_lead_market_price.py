"""Anulacion de precios de mercado del plomo (ciclo corto sobre CC-014 / #110)

Tres columnas de auditoria, todas nullable y sin backfill: una fila con
`annulled_at IS NULL` es vigente, que es el estado de todas las existentes.

Aditiva pura sobre `lead_market_prices`, tabla EXCLUSIVA de SAC (0 filas en las
tres organizaciones cliente) y fuera de las 14 capturas del golden, asi que el
golden no aplica. Ver el plan, D9.

Revision ID: e8f0a2b4c6d9
Revises: d7c9e1f3a5b7
"""
from alembic import op
import sqlalchemy as sa

from app.models.base import GUID

revision = "e8f0a2b4c6d9"
down_revision = "d7c9e1f3a5b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lead_market_prices",
        sa.Column(
            "annulled_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp de auditoria de la anulacion (now utc). NULL = vigente",
        ),
    )
    op.add_column(
        "lead_market_prices",
        sa.Column("annulled_by", GUID(), nullable=True),
    )
    op.add_column(
        "lead_market_prices",
        sa.Column(
            "annulled_reason",
            sa.String(500),
            nullable=True,
            comment="Por que se anulo: es el dato que hace auditable la correccion",
        ),
    )
    # ⚠️ SIN nombre explicito, a proposito: `create_all` (que es de donde nace la
    # base de test) deja que PG la nombre `lead_market_prices_annulled_by_fkey`,
    # y una migracion que la bautiza distinto abre una divergencia permanente
    # entre la base de test y la de produccion. El parity check la caza; el
    # baseline del script esta lleno de pares asi, todos pre-existentes.
    op.create_foreign_key(
        None,
        "lead_market_prices",
        "users",
        ["annulled_by"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "lead_market_prices_annulled_by_fkey",
        "lead_market_prices",
        type_="foreignkey",
    )
    op.drop_column("lead_market_prices", "annulled_reason")
    op.drop_column("lead_market_prices", "annulled_by")
    op.drop_column("lead_market_prices", "annulled_at")
