"""add_deferred_expenses_and_applications_tables

Revision ID: 22f663ae5d63
Revises: ae239f97fcb5
Create Date: 2026-03-10 09:30:17.144112

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '22f663ae5d63'
down_revision: Union[str, Sequence[str], None] = 'ae239f97fcb5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crear tablas deferred_expenses y deferred_applications."""
    op.create_table('deferred_expenses',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False, comment='Nombre descriptivo del gasto diferido'),
        sa.Column('total_amount', sa.Numeric(precision=15, scale=2), nullable=False, comment='Monto total del gasto'),
        sa.Column('monthly_amount', sa.Numeric(precision=15, scale=2), nullable=False, comment='Cuota mensual'),
        sa.Column('total_months', sa.Integer(), nullable=False, comment='Numero total de cuotas mensuales'),
        sa.Column('applied_months', sa.Integer(), nullable=False, comment='Cuotas ya aplicadas'),
        sa.Column('expense_category_id', postgresql.UUID(as_uuid=True), nullable=False, comment='Categoria del gasto'),
        sa.Column('expense_type', sa.String(length=30), nullable=False, comment='expense o provision_expense'),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=True, comment='Cuenta (para tipo expense)'),
        sa.Column('provision_id', postgresql.UUID(as_uuid=True), nullable=True, comment='Provision (para tipo provision_expense)'),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False, comment='Fecha de inicio'),
        sa.Column('status', sa.String(length=20), nullable=False, comment='active | completed | cancelled'),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['money_accounts.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['cancelled_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['expense_category_id'], ['expense_categories.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['provision_id'], ['third_parties.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_deferred_expenses_org_status', 'deferred_expenses', ['organization_id', 'status'])
    op.create_index('ix_deferred_expenses_organization_id', 'deferred_expenses', ['organization_id'])
    op.create_index('ix_deferred_expenses_status', 'deferred_expenses', ['status'])

    op.create_table('deferred_applications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('deferred_expense_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('application_number', sa.Integer(), nullable=False, comment='Numero secuencial de cuota'),
        sa.Column('amount', sa.Numeric(precision=15, scale=2), nullable=False, comment='Monto de esta cuota'),
        sa.Column('money_movement_id', postgresql.UUID(as_uuid=True), nullable=False, comment='MoneyMovement generado'),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('applied_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['applied_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['deferred_expense_id'], ['deferred_expenses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['money_movement_id'], ['money_movements.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_deferred_applications_deferred_expense_id', 'deferred_applications', ['deferred_expense_id'])


def downgrade() -> None:
    """Eliminar tablas deferred_applications y deferred_expenses."""
    op.drop_table('deferred_applications')
    op.drop_table('deferred_expenses')
