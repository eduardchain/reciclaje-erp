"""attachments: adjuntos multiples en compras, ventas y transformaciones

Revision ID: d3e4f5a6b7c8
Revises: b1c2d3e4f5a7
Create Date: 2026-09-01

Tabla NUEVA, cero columnas en tablas existentes -> el golden no aplica
(verificado contra CAPTURES: /purchases, /sales y /material-transformations
no se capturan).

⚠️ `created_at` / `updated_at` llevan `server_default=sa.func.now()` porque
`TimestampMixin` lo declara. La BD de test nace de los modelos y la de
produccion de las migraciones: sin el default aca, el primer POST revienta con
un 500 en prod mientras todos los tests pasan en verde (el bug de #100), y ese
sentido lo excluye a proposito el `schema_parity_check`.
"""
from alembic import op
import sqlalchemy as sa
from app.models.base import GUID


revision = "d3e4f5a6b7c8"
down_revision = "b1c2d3e4f5a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("purchase_id", GUID(), nullable=True),
        sa.Column("sale_id", GUID(), nullable=True),
        sa.Column("transformation_id", GUID(), nullable=True),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=True),
        sa.Column("uploaded_by", GUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["purchase_id"], ["purchases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["transformation_id"], ["material_transformations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "(CASE WHEN purchase_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN sale_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN transformation_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="ck_attachments_exactly_one_owner",
        ),
    )
    op.create_index("ix_attachments_organization_id", "attachments", ["organization_id"])
    op.create_index("ix_attachments_purchase_id", "attachments", ["purchase_id"])
    op.create_index("ix_attachments_sale_id", "attachments", ["sale_id"])
    op.create_index("ix_attachments_transformation_id", "attachments", ["transformation_id"])


def downgrade() -> None:
    op.drop_index("ix_attachments_transformation_id", table_name="attachments")
    op.drop_index("ix_attachments_sale_id", table_name="attachments")
    op.drop_index("ix_attachments_purchase_id", table_name="attachments")
    op.drop_index("ix_attachments_organization_id", table_name="attachments")
    op.drop_table("attachments")
