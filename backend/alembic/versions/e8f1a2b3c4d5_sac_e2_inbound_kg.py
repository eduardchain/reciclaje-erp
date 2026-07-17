"""SAC E2: valores de enum inbound + purchase_retentions + columnas InboundOrder

Plan: docs/planes/plan-sac-e2-kgledger-inbound.md (Migracion D, §3.1).
Todo ADITIVO (plan-ejecucion §1.1): ADD VALUE / CREATE TABLE / ADD COLUMN nullable.

⚠️ Los ALTER TYPE ADD VALUE corren en autocommit_block (D3): env.py ejecuta todas
las migraciones pendientes en UNA transaccion y una migracion futura del mismo
chain que inserte filas con el valor nuevo reventaria con 55P04. El downgrade de
los valores de enum es NO-OP (PostgreSQL no soporta DROP VALUE) — valores inertes
si se revierte el codigo, documentado en el plan.

Revision ID: e8f1a2b3c4d5
Revises: d7e0a3c4b5f6
Create Date: 2026-07-16
"""
from alembic import op
import sqlalchemy as sa

from app.models.base import GUID

# revision identifiers, used by Alembic.
revision = "e8f1a2b3c4d5"
down_revision = "d7e0a3c4b5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1. Valores nuevos de enum (autocommit — ver docstring) ---
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE inventory_movement_type ADD VALUE IF NOT EXISTS 'inbound_receipt'"
        )
        op.execute(
            "ALTER TYPE inventory_movement_type ADD VALUE IF NOT EXISTS 'inbound_reversal'"
        )
        op.execute(
            "ALTER TYPE inventory_reference_type ADD VALUE IF NOT EXISTS 'inbound'"
        )

    # --- 2. purchase_retentions (D9 — estructura de retenciones Fase 1) ---
    op.create_table(
        "purchase_retentions",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("purchase_id", GUID(), nullable=False),
        sa.Column(
            "third_party_id",
            GUID(),
            nullable=False,
            comment="Entidad de retencion '[Retenciones] X' (resuelta/creada al liquidar) — el statement y el revert leen de aca",
        ),
        sa.Column(
            "retention_type",
            sa.String(length=16),
            nullable=False,
            comment="ica | retefuente | reteiva (Literal en schema, patron #70)",
        ),
        sa.Column(
            "municipality",
            sa.String(length=60),
            nullable=True,
            comment="Obligatorio cuando retention_type='ica' (entidad por municipio, Johana 2026-07-16); prohibido en los demas",
        ),
        sa.Column(
            "rate",
            sa.Numeric(7, 4),
            nullable=True,
            comment="Tasa informativa (la tabla oficial llega del contador SAC — CONFIG-ARRANQUE)",
        ),
        sa.Column("base", sa.Numeric(15, 2), nullable=True, comment="Base informativa"),
        sa.Column(
            "amount",
            sa.Numeric(15, 2),
            nullable=False,
            comment="Monto retenido — resta del credito al proveedor, acredita a la entidad",
        ),
        sa.Column(
            "reverted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Poblado al cancelar la compra (auditoria sin delete fisico)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["purchase_id"], ["purchases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["third_party_id"], ["third_parties.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("amount > 0", name="ck_purchase_retentions_amount_positive"),
    )
    op.create_index(
        "ix_purchase_retentions_organization_id", "purchase_retentions", ["organization_id"]
    )
    op.create_index(
        "ix_purchase_retentions_purchase", "purchase_retentions", ["purchase_id"]
    )

    # --- 3. Columnas nuevas en inbound_orders / inbound_order_lines ---
    op.add_column(
        "inbound_orders",
        sa.Column(
            "purchase_id",
            GUID(),
            nullable=True,
            comment="Purchase(registered) derivada para tipos purchase/ruta (D7)",
        ),
    )
    op.create_foreign_key(
        None, "inbound_orders", "purchases", ["purchase_id"], ["id"], ondelete="SET NULL"
    )
    op.add_column(
        "inbound_orders",
        sa.Column(
            "annul_cost_adjustment",
            sa.Numeric(15, 2),
            server_default="0",
            nullable=False,
            comment="Diferencia de remocion ponderada al anular (D8, patron #66) — 8a fuente linea P&L oversell",
        ),
    )
    op.add_column(
        "inbound_order_lines",
        sa.Column(
            "unit_price",
            sa.Numeric(15, 2),
            nullable=True,
            comment="Precio de captura opcional (tipos purchase; el definitivo lo fija la liquidacion §7.2)",
        ),
    )
    op.add_column(
        "inbound_order_lines",
        sa.Column(
            "unit_cost",
            sa.Numeric(15, 2),
            nullable=True,
            comment="Snapshot del costo promedio de entrada (tipos Willard, D8 — la reversa exacta lee de aca)",
        ),
    )


def downgrade() -> None:
    op.drop_column("inbound_order_lines", "unit_cost")
    op.drop_column("inbound_order_lines", "unit_price")
    op.drop_column("inbound_orders", "annul_cost_adjustment")
    op.drop_constraint("inbound_orders_purchase_id_fkey", "inbound_orders", type_="foreignkey")
    op.drop_column("inbound_orders", "purchase_id")
    op.drop_index("ix_purchase_retentions_purchase", table_name="purchase_retentions")
    op.drop_index("ix_purchase_retentions_organization_id", table_name="purchase_retentions")
    op.drop_table("purchase_retentions")
    # Los valores de enum NO se remueven (PG no soporta DROP VALUE) — quedan inertes.
