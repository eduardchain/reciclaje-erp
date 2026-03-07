"""Double entry multi-line: crear tabla double_entry_lines y migrar datos escalares

Revision ID: c4a1b2d3e5f6
Revises: b7d2e4f6a8c1
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c4a1b2d3e5f6"
down_revision = "b7d2e4f6a8c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Crear tabla double_entry_lines
    op.create_table(
        "double_entry_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("double_entry_id", sa.Uuid(), nullable=False),
        sa.Column("material_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column("purchase_unit_price", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("sale_unit_price", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["double_entry_id"], ["double_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_del_double_entry_id", "double_entry_lines", ["double_entry_id"])
    op.create_index("ix_del_material_id", "double_entry_lines", ["material_id"])

    # 2. Migrar datos existentes: cada double_entry escalar → 1 double_entry_line
    op.execute("""
        INSERT INTO double_entry_lines (id, double_entry_id, material_id, quantity, purchase_unit_price, sale_unit_price, created_at, updated_at)
        SELECT gen_random_uuid(), id, material_id, quantity, purchase_unit_price, sale_unit_price, created_at, updated_at
        FROM double_entries
        WHERE material_id IS NOT NULL
    """)

    # 3. Eliminar columnas escalares de double_entries
    op.drop_index("ix_double_entries_org_material", table_name="double_entries")
    op.drop_constraint("double_entries_material_id_fkey", "double_entries", type_="foreignkey")
    op.drop_column("double_entries", "material_id")
    op.drop_column("double_entries", "quantity")
    op.drop_column("double_entries", "purchase_unit_price")
    op.drop_column("double_entries", "sale_unit_price")


def downgrade() -> None:
    # 1. Re-agregar columnas escalares (nullable temporalmente)
    op.add_column("double_entries", sa.Column("material_id", sa.Uuid(), nullable=True))
    op.add_column("double_entries", sa.Column("quantity", sa.Numeric(precision=10, scale=3), nullable=True))
    op.add_column("double_entries", sa.Column("purchase_unit_price", sa.Numeric(precision=15, scale=2), nullable=True))
    op.add_column("double_entries", sa.Column("sale_unit_price", sa.Numeric(precision=15, scale=2), nullable=True))

    # 2. Copiar primera linea de vuelta a double_entries
    op.execute("""
        UPDATE double_entries de
        SET material_id = del.material_id,
            quantity = del.quantity,
            purchase_unit_price = del.purchase_unit_price,
            sale_unit_price = del.sale_unit_price
        FROM (
            SELECT DISTINCT ON (double_entry_id)
                double_entry_id, material_id, quantity, purchase_unit_price, sale_unit_price
            FROM double_entry_lines
            ORDER BY double_entry_id, created_at ASC
        ) del
        WHERE de.id = del.double_entry_id
    """)

    # 3. Hacer columnas NOT NULL y agregar FK
    op.alter_column("double_entries", "material_id", nullable=False)
    op.alter_column("double_entries", "quantity", nullable=False)
    op.alter_column("double_entries", "purchase_unit_price", nullable=False)
    op.alter_column("double_entries", "sale_unit_price", nullable=False)
    op.create_foreign_key(
        "double_entries_material_id_fkey", "double_entries",
        "materials", ["material_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index("ix_double_entries_org_material", "double_entries", ["organization_id", "material_id"])

    # 4. Eliminar tabla double_entry_lines
    op.drop_index("ix_del_material_id", table_name="double_entry_lines")
    op.drop_index("ix_del_double_entry_id", table_name="double_entry_lines")
    op.drop_table("double_entry_lines")
