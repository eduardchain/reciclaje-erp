"""Crear tabla user_account_assignments y eliminar treasury.view_own

Revision ID: e8f9a0b1c2d3
Revises: d6e7f8a9b0c1
Create Date: 2026-03-13

"""
from typing import Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, None] = "d6e7f8a9b0c1"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    """Crear tabla user_account_assignments y eliminar permiso treasury.view_own."""
    # 1. Crear tabla
    op.create_table(
        "user_account_assignments",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "account_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("money_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "account_id"),
    )

    # 2. Eliminar permiso treasury.view_own
    conn = op.get_bind()
    perm = conn.execute(
        sa.text("SELECT id FROM permissions WHERE code = 'treasury.view_own'")
    ).fetchone()

    if perm:
        conn.execute(
            sa.text("DELETE FROM role_permissions WHERE permission_id = :pid"),
            {"pid": perm[0]},
        )
        conn.execute(
            sa.text("DELETE FROM permissions WHERE id = :pid"),
            {"pid": perm[0]},
        )


def downgrade() -> None:
    """Restaurar treasury.view_own y eliminar tabla."""
    from uuid import uuid4

    conn = op.get_bind()

    # Restaurar permiso
    conn.execute(
        sa.text(
            "INSERT INTO permissions (id, code, display_name, module, description, sort_order) "
            "VALUES (:id, 'treasury.view_own', 'Ver Solo Mi Caja', 'treasury', "
            "'Permite ver solo la caja asignada', 83) "
            "ON CONFLICT (code) DO NOTHING"
        ),
        {"id": str(uuid4())},
    )

    op.drop_table("user_account_assignments")
