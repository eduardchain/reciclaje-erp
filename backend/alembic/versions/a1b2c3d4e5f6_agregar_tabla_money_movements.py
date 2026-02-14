"""agregar_tabla_money_movements

Revision ID: a1b2c3d4e5f6
Revises: 05dbf78c0530
Create Date: 2026-02-14 20:00:00.000000

Tabla para registrar todos los movimientos de dinero en tesoreria:
pagos a proveedores, cobros a clientes, gastos, transferencias,
aportes/retiros de capital, y pagos de comisiones.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from app.models.base import GUID


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '05dbf78c0530'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crear tabla money_movements con indexes compuestos."""
    op.create_table('money_movements',
        # Primary key
        sa.Column('id', GUID(), nullable=False),

        # Organization (multi-tenant)
        sa.Column('organization_id', GUID(), nullable=False),

        # Numero secuencial
        sa.Column('movement_number', sa.Integer(), nullable=False),

        # Fecha y tipo
        sa.Column('date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('movement_type', sa.String(length=50), nullable=False,
                   comment='Tipo: payment_to_supplier, collection_from_client, expense, etc.'),

        # Monto
        sa.Column('amount', sa.Numeric(precision=15, scale=2), nullable=False,
                   comment='Monto siempre positivo. El tipo define la direccion.'),

        # Cuenta afectada (siempre una)
        sa.Column('account_id', GUID(), nullable=False),

        # Relaciones opcionales
        sa.Column('third_party_id', GUID(), nullable=True),
        sa.Column('expense_category_id', GUID(), nullable=True),
        sa.Column('purchase_id', GUID(), nullable=True),
        sa.Column('sale_id', GUID(), nullable=True),
        sa.Column('transfer_pair_id', GUID(), nullable=True),

        # Detalles
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column('reference_number', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('evidence_url', sa.String(length=500), nullable=True),

        # Estado y anulacion
        sa.Column('status', sa.String(length=20), nullable=False, server_default='confirmed'),
        sa.Column('annulled_reason', sa.String(length=500), nullable=True),
        sa.Column('annulled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('annulled_by', GUID(), nullable=True),

        # Auditoria
        sa.Column('created_by', GUID(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        # Foreign keys
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['account_id'], ['money_accounts.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['third_party_id'], ['third_parties.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['expense_category_id'], ['expense_categories.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['purchase_id'], ['purchases.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['sale_id'], ['sales.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['transfer_pair_id'], ['money_movements.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['annulled_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),

        # Unique constraint
        sa.UniqueConstraint('organization_id', 'movement_number', name='uq_movement_number_per_org'),
    )

    # Indexes compuestos para queries frecuentes
    op.create_index('ix_money_movements_org_date', 'money_movements', ['organization_id', 'date'])
    op.create_index('ix_money_movements_org_type', 'money_movements', ['organization_id', 'movement_type'])
    op.create_index('ix_money_movements_org_account', 'money_movements', ['organization_id', 'account_id'])
    op.create_index('ix_money_movements_org_third_party', 'money_movements', ['organization_id', 'third_party_id'])
    op.create_index('ix_money_movements_org_status', 'money_movements', ['organization_id', 'status'])

    # Indexes simples
    op.create_index(op.f('ix_money_movements_movement_number'), 'money_movements', ['movement_number'])
    op.create_index(op.f('ix_money_movements_date'), 'money_movements', ['date'])
    op.create_index(op.f('ix_money_movements_movement_type'), 'money_movements', ['movement_type'])
    op.create_index(op.f('ix_money_movements_account_id'), 'money_movements', ['account_id'])
    op.create_index(op.f('ix_money_movements_third_party_id'), 'money_movements', ['third_party_id'])
    op.create_index(op.f('ix_money_movements_status'), 'money_movements', ['status'])


def downgrade() -> None:
    """Eliminar tabla money_movements y todos sus indexes."""
    # Drop compound indexes
    op.drop_index('ix_money_movements_org_status', table_name='money_movements')
    op.drop_index('ix_money_movements_org_third_party', table_name='money_movements')
    op.drop_index('ix_money_movements_org_account', table_name='money_movements')
    op.drop_index('ix_money_movements_org_type', table_name='money_movements')
    op.drop_index('ix_money_movements_org_date', table_name='money_movements')

    # Drop simple indexes
    op.drop_index(op.f('ix_money_movements_status'), table_name='money_movements')
    op.drop_index(op.f('ix_money_movements_third_party_id'), table_name='money_movements')
    op.drop_index(op.f('ix_money_movements_account_id'), table_name='money_movements')
    op.drop_index(op.f('ix_money_movements_movement_type'), table_name='money_movements')
    op.drop_index(op.f('ix_money_movements_date'), table_name='money_movements')
    op.drop_index(op.f('ix_money_movements_movement_number'), table_name='money_movements')

    op.drop_table('money_movements')
