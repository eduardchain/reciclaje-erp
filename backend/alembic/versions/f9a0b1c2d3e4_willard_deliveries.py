"""Salidas de plomo a Willard (W1)

Aditiva pura:
  - willard_deliveries + willard_delivery_lines (tablas nuevas, exclusivas SAC)
  - sales.willard_delivery_id nullable (tabla COMPARTIDA — patron D1 de #94/#98:
    NULL = el comportamiento de las 6 orgs que no son SAC, o sea que la no
    regresion es demostrable y no verificable caso por caso)

Revision ID: f9a0b1c2d3e4
Revises: a2b3c4d5e6f7
Create Date: 2026-08-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f9a0b1c2d3e4"
down_revision: Union[str, None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "willard_deliveries",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("delivery_number", sa.Integer(), nullable=False),
        sa.Column("delivery_type", sa.String(length=20), nullable=False),
        sa.Column("warehouse_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("third_party_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("driver_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("vehicle_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("invoice_number", sa.String(length=50), nullable=True),
        sa.Column("remission_number", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reviewed_by", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("liquidated_by", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("liquidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("liquidated_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sale_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("maquila_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("freight_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("plant_credit_amount", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("annulled_reason", sa.String(length=500), nullable=True),
        sa.Column("annulled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("annulled_by", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["third_party_id"], ["third_parties.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["driver_id"], ["drivers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["liquidated_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["annulled_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "delivery_number", name="uq_willard_delivery_number"),
        sa.CheckConstraint(
            "delivery_type IN ('venta', 'abono_bateria', 'abono_material')",
            name="ck_willard_delivery_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'reviewed', 'liquidated', 'annulled')",
            name="ck_willard_delivery_status",
        ),
    )
    op.create_index("ix_willard_deliveries_organization_id", "willard_deliveries", ["organization_id"])
    op.create_index("ix_willard_deliveries_org_status", "willard_deliveries", ["organization_id", "status"])
    op.create_index("ix_willard_deliveries_org_date", "willard_deliveries", ["organization_id", "date"])

    op.create_table(
        "willard_delivery_lines",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("willard_delivery_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("material_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Numeric(15, 4), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("scale_weight_kg", sa.Numeric(15, 4), nullable=True),
        sa.Column("kg_lead_equivalent", sa.Numeric(15, 4), nullable=True),
        sa.Column("conversion_formula_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("unit_cost", sa.Numeric(15, 4), nullable=True),
        sa.Column("unit_price", sa.Numeric(15, 2), nullable=True),
        sa.Column("total_price", sa.Numeric(15, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["willard_delivery_id"], ["willard_deliveries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("quantity > 0", name="ck_willard_delivery_line_qty"),
    )
    op.create_index("ix_willard_delivery_lines_organization_id", "willard_delivery_lines", ["organization_id"])
    op.create_index("ix_willard_delivery_lines_delivery", "willard_delivery_lines", ["willard_delivery_id"])

    # Tablas COMPARTIDAS — nullable, sin backfill: NULL = comportamiento de hoy (D1).
    # inventory_adjustments.willard_delivery_id: el abono saca inventario
    # valorizado sin venta, y el `decrease` es el vehiculo que lleva ese costo al
    # P&L (adjustment_net). Tercera columna de su clase, mismo precedente que
    # transfer_id (#84) e inbound_order_id (#93): no se serializa.
    op.add_column(
        "inventory_adjustments",
        sa.Column("willard_delivery_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        None, "inventory_adjustments", "willard_deliveries",
        ["willard_delivery_id"], ["id"], ondelete="CASCADE",
    )
    op.add_column("sales", sa.Column("willard_delivery_id", sa.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        None, "sales", "willard_deliveries", ["willard_delivery_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_sales_willard_delivery_id", "sales", ["willard_delivery_id"])


def downgrade() -> None:
    op.drop_index("ix_sales_willard_delivery_id", table_name="sales")
    op.drop_column("sales", "willard_delivery_id")
    op.drop_column("inventory_adjustments", "willard_delivery_id")
    op.drop_index("ix_willard_delivery_lines_delivery", table_name="willard_delivery_lines")
    op.drop_index("ix_willard_delivery_lines_organization_id", table_name="willard_delivery_lines")
    op.drop_table("willard_delivery_lines")
    op.drop_index("ix_willard_deliveries_org_date", table_name="willard_deliveries")
    op.drop_index("ix_willard_deliveries_org_status", table_name="willard_deliveries")
    op.drop_index("ix_willard_deliveries_organization_id", table_name="willard_deliveries")
    op.drop_table("willard_deliveries")
