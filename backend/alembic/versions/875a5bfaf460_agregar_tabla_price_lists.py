"""agregar_tabla_price_lists

Revision ID: 875a5bfaf460
Revises: 9e92ce5f1765
Create Date: 2026-02-14 16:41:50.946035

Tabla para registrar precios de compra y venta por material.
Cada registro es un punto en el historial de precios.
El precio vigente es el registro mas reciente por material.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from app.models.base import GUID


# revision identifiers, used by Alembic.
revision: str = '875a5bfaf460'
down_revision: Union[str, Sequence[str], None] = '9e92ce5f1765'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crear tabla price_lists."""
    op.create_table('price_lists',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('material_id', GUID(), nullable=False),
        sa.Column('purchase_price', sa.Numeric(precision=15, scale=2), nullable=False,
                   comment='Precio de compra por unidad del material'),
        sa.Column('sale_price', sa.Numeric(precision=15, scale=2), nullable=False,
                   comment='Precio de venta por unidad del material'),
        sa.Column('notes', sa.String(length=500), nullable=True,
                   comment='Nota o justificacion del cambio de precio'),
        sa.Column('updated_by', GUID(), nullable=True,
                   comment='Usuario que registro este precio'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('organization_id', GUID(), nullable=False),
        sa.ForeignKeyConstraint(['material_id'], ['materials.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_price_lists_material_id'), 'price_lists', ['material_id'], unique=False)
    op.create_index(op.f('ix_price_lists_organization_id'), 'price_lists', ['organization_id'], unique=False)


def downgrade() -> None:
    """Eliminar tabla price_lists."""
    op.drop_index(op.f('ix_price_lists_organization_id'), table_name='price_lists')
    op.drop_index(op.f('ix_price_lists_material_id'), table_name='price_lists')
    op.drop_table('price_lists')
