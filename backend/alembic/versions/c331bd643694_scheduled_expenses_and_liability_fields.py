"""scheduled_expenses_and_liability_fields

Revision ID: c331bd643694
Revises: bf0ec8815fdc
Create Date: 2026-03-11 16:49:40.394737

Nuevas tablas scheduled_expenses + scheduled_expense_applications.
Nuevos campos ThirdParty: is_liability, is_system_entity.
DROP tablas viejas: deferred_applications, deferred_expenses.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.models.base  # noqa – para GUID()

# revision identifiers, used by Alembic.
revision: str = 'c331bd643694'
down_revision: Union[str, Sequence[str], None] = 'bf0ec8815fdc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Nuevas tablas
    op.create_table('scheduled_expenses',
        sa.Column('id', app.models.base.GUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('total_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('monthly_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('total_months', sa.Integer(), nullable=False),
        sa.Column('applied_months', sa.Integer(), nullable=False),
        sa.Column('source_account_id', app.models.base.GUID(), nullable=False),
        sa.Column('prepaid_third_party_id', app.models.base.GUID(), nullable=False),
        sa.Column('expense_category_id', app.models.base.GUID(), nullable=False),
        sa.Column('funding_movement_id', app.models.base.GUID(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('apply_day', sa.Integer(), nullable=False),
        sa.Column('next_application_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_by', app.models.base.GUID(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_by', app.models.base.GUID(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('organization_id', app.models.base.GUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['cancelled_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['expense_category_id'], ['expense_categories.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['funding_movement_id'], ['money_movements.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['prepaid_third_party_id'], ['third_parties.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['source_account_id'], ['money_accounts.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scheduled_expenses_next_date', 'scheduled_expenses', ['next_application_date'], unique=False)
    op.create_index('ix_scheduled_expenses_org_status', 'scheduled_expenses', ['organization_id', 'status'], unique=False)
    op.create_index(op.f('ix_scheduled_expenses_organization_id'), 'scheduled_expenses', ['organization_id'], unique=False)

    op.create_table('scheduled_expense_applications',
        sa.Column('id', app.models.base.GUID(), nullable=False),
        sa.Column('scheduled_expense_id', app.models.base.GUID(), nullable=False),
        sa.Column('application_number', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('money_movement_id', app.models.base.GUID(), nullable=False),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('applied_by', app.models.base.GUID(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['applied_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['money_movement_id'], ['money_movements.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['scheduled_expense_id'], ['scheduled_expenses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        op.f('ix_scheduled_expense_applications_scheduled_expense_id'),
        'scheduled_expense_applications', ['scheduled_expense_id'], unique=False,
    )

    # 2. Nuevos campos en third_parties
    op.add_column('third_parties', sa.Column('is_liability', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('third_parties', sa.Column('is_system_entity', sa.Boolean(), nullable=False, server_default=sa.text('false')))

    # 3. DROP tablas viejas (no hay datos en produccion)
    op.drop_table('deferred_applications')
    op.drop_table('deferred_expenses')


def downgrade() -> None:
    """Downgrade schema."""
    # Recrear tablas viejas (estructura minima para rollback)
    op.create_table('deferred_expenses',
        sa.Column('id', app.models.base.GUID(), nullable=False),
        sa.Column('organization_id', app.models.base.GUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('total_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('monthly_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('total_months', sa.Integer(), nullable=False),
        sa.Column('applied_months', sa.Integer(), nullable=False),
        sa.Column('expense_type', sa.String(length=30), nullable=False),
        sa.Column('account_id', app.models.base.GUID(), nullable=True),
        sa.Column('provision_id', app.models.base.GUID(), nullable=True),
        sa.Column('expense_category_id', app.models.base.GUID(), nullable=True),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_by', app.models.base.GUID(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_by', app.models.base.GUID(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('deferred_applications',
        sa.Column('id', app.models.base.GUID(), nullable=False),
        sa.Column('deferred_expense_id', app.models.base.GUID(), nullable=False),
        sa.Column('application_number', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('money_movement_id', app.models.base.GUID(), nullable=False),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('applied_by', app.models.base.GUID(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['deferred_expense_id'], ['deferred_expenses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['money_movement_id'], ['money_movements.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )

    op.drop_column('third_parties', 'is_system_entity')
    op.drop_column('third_parties', 'is_liability')

    op.drop_table('scheduled_expense_applications')
    op.drop_table('scheduled_expenses')
