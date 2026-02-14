"""separar_stock_liquidado_vs_transito_en_materiales

Revision ID: 9e92ce5f1765
Revises: beb1e434a605
Create Date: 2026-02-14 12:44:51.007800

Separa el stock total en dos categorias:
- current_stock_liquidated: stock disponible para venta (compras pagadas)
- current_stock_transit: stock en transito (compras registradas pero no pagadas)

El campo current_stock se mantiene como total (liquidated + transit) para
compatibilidad con el codigo existente.

Migracion de datos: todo el stock existente se asume como liquidado.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e92ce5f1765'
down_revision: Union[str, Sequence[str], None] = 'beb1e434a605'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Agregar columnas de stock separado y migrar datos existentes."""
    # Paso 1: Agregar nuevas columnas con default 0
    op.add_column('materials', sa.Column(
        'current_stock_liquidated', sa.Numeric(precision=15, scale=4),
        nullable=False, server_default='0',
        comment='Stock de compras liquidadas (pagadas). Disponible para venta.'
    ))
    op.add_column('materials', sa.Column(
        'current_stock_transit', sa.Numeric(precision=15, scale=4),
        nullable=False, server_default='0',
        comment='Stock de compras registradas (sin pagar). No disponible para venta.'
    ))
    op.add_column('materials', sa.Column(
        'sort_order', sa.Integer(),
        nullable=False, server_default='0',
        comment='Orden de despliegue en listas (menor = primero)'
    ))

    # Paso 2: Migrar datos existentes — todo el stock actual es liquidado
    op.execute("""
        UPDATE materials
        SET current_stock_liquidated = current_stock,
            current_stock_transit = 0
    """)

    # Paso 3: Actualizar comentario de current_stock
    op.alter_column('materials', 'current_stock',
               existing_type=sa.NUMERIC(precision=15, scale=4),
               comment='Stock total (liquidated + transit). Se mantiene por compatibilidad.',
               existing_nullable=False)


def downgrade() -> None:
    """Revertir: quitar columnas nuevas."""
    op.alter_column('materials', 'current_stock',
               existing_type=sa.NUMERIC(precision=15, scale=4),
               comment=None,
               existing_comment='Stock total (liquidated + transit). Se mantiene por compatibilidad.',
               existing_nullable=False)
    op.drop_column('materials', 'sort_order')
    op.drop_column('materials', 'current_stock_transit')
    op.drop_column('materials', 'current_stock_liquidated')
