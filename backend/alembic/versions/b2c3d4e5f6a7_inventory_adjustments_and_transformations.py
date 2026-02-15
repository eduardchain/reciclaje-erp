"""inventory_adjustments_and_transformations

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-14 22:00:00.000000

Tablas para ajustes de inventario y transformacion/desintegracion de materiales.
Tambien agrega 'adjustment_reversal' al enum de tipos de movimiento de inventario.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from app.models.base import GUID


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crear tablas de ajustes de inventario y transformaciones de materiales."""

    # --- Agregar 'adjustment_reversal' al enum inventory_movement_type ---
    # ALTER TYPE ... ADD VALUE no puede ejecutarse dentro de una transaccion
    # Usamos connection directa con autocommit
    op.execute("ALTER TYPE inventory_movement_type ADD VALUE IF NOT EXISTS 'adjustment_reversal'")

    # --- Tabla inventory_adjustments ---
    op.create_table('inventory_adjustments',
        # Primary key
        sa.Column('id', GUID(), nullable=False),

        # Organization (multi-tenant)
        sa.Column('organization_id', GUID(), nullable=False),

        # Numero secuencial
        sa.Column('adjustment_number', sa.Integer(), nullable=False),

        # Fecha y tipo
        sa.Column('date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('adjustment_type', sa.String(length=20), nullable=False,
                   comment='Tipo: increase, decrease, recount, zero_out'),

        # Material y bodega
        sa.Column('material_id', GUID(), nullable=False),
        sa.Column('warehouse_id', GUID(), nullable=False),

        # Cantidades
        sa.Column('previous_stock', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('new_stock', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('counted_quantity', sa.Numeric(precision=15, scale=4), nullable=True),

        # Costo
        sa.Column('unit_cost', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('total_value', sa.Numeric(precision=15, scale=2), nullable=False),

        # Razon y notas
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),

        # Estado y anulacion
        sa.Column('status', sa.String(length=20), nullable=False, server_default='confirmed'),
        sa.Column('annulled_reason', sa.String(length=500), nullable=True),
        sa.Column('annulled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('annulled_by', GUID(), nullable=True),

        # Auditoria
        sa.Column('created_by', GUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        # Foreign keys
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['material_id'], ['materials.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['annulled_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),

        # Unique constraint
        sa.UniqueConstraint('organization_id', 'adjustment_number', name='uq_adjustment_number_per_org'),
    )

    # Indexes para inventory_adjustments
    op.create_index('ix_inventory_adjustments_org_date', 'inventory_adjustments', ['organization_id', 'date'])
    op.create_index('ix_inventory_adjustments_org_material', 'inventory_adjustments', ['organization_id', 'material_id'])
    op.create_index('ix_inventory_adjustments_org_status', 'inventory_adjustments', ['organization_id', 'status'])
    op.create_index(op.f('ix_inventory_adjustments_adjustment_number'), 'inventory_adjustments', ['adjustment_number'])
    op.create_index(op.f('ix_inventory_adjustments_date'), 'inventory_adjustments', ['date'])
    op.create_index(op.f('ix_inventory_adjustments_adjustment_type'), 'inventory_adjustments', ['adjustment_type'])
    op.create_index(op.f('ix_inventory_adjustments_material_id'), 'inventory_adjustments', ['material_id'])
    op.create_index(op.f('ix_inventory_adjustments_warehouse_id'), 'inventory_adjustments', ['warehouse_id'])
    op.create_index(op.f('ix_inventory_adjustments_status'), 'inventory_adjustments', ['status'])

    # --- Tabla material_transformations ---
    op.create_table('material_transformations',
        # Primary key
        sa.Column('id', GUID(), nullable=False),

        # Organization (multi-tenant)
        sa.Column('organization_id', GUID(), nullable=False),

        # Numero secuencial
        sa.Column('transformation_number', sa.Integer(), nullable=False),

        # Fecha
        sa.Column('date', sa.DateTime(timezone=True), nullable=False),

        # Material de origen
        sa.Column('source_material_id', GUID(), nullable=False),
        sa.Column('source_warehouse_id', GUID(), nullable=False),
        sa.Column('source_quantity', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('source_unit_cost', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('source_total_value', sa.Numeric(precision=15, scale=2), nullable=False),

        # Merma
        sa.Column('waste_quantity', sa.Numeric(precision=15, scale=4), nullable=False, server_default='0'),
        sa.Column('waste_value', sa.Numeric(precision=15, scale=2), nullable=False, server_default='0'),

        # Distribucion de costos
        sa.Column('cost_distribution', sa.String(length=30), nullable=False, server_default='proportional_weight'),

        # Razon y notas
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),

        # Estado y anulacion
        sa.Column('status', sa.String(length=20), nullable=False, server_default='confirmed'),
        sa.Column('annulled_reason', sa.String(length=500), nullable=True),
        sa.Column('annulled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('annulled_by', GUID(), nullable=True),

        # Auditoria
        sa.Column('created_by', GUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        # Foreign keys
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_material_id'], ['materials.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['source_warehouse_id'], ['warehouses.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['annulled_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),

        # Unique constraint
        sa.UniqueConstraint('organization_id', 'transformation_number', name='uq_transformation_number_per_org'),
    )

    # Indexes para material_transformations
    op.create_index('ix_material_transformations_org_date', 'material_transformations', ['organization_id', 'date'])
    op.create_index('ix_material_transformations_org_source', 'material_transformations', ['organization_id', 'source_material_id'])
    op.create_index('ix_material_transformations_org_status', 'material_transformations', ['organization_id', 'status'])
    op.create_index(op.f('ix_material_transformations_transformation_number'), 'material_transformations', ['transformation_number'])
    op.create_index(op.f('ix_material_transformations_date'), 'material_transformations', ['date'])
    op.create_index(op.f('ix_material_transformations_source_material_id'), 'material_transformations', ['source_material_id'])
    op.create_index(op.f('ix_material_transformations_status'), 'material_transformations', ['status'])

    # --- Tabla material_transformation_lines ---
    op.create_table('material_transformation_lines',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('transformation_id', GUID(), nullable=False),
        sa.Column('destination_material_id', GUID(), nullable=False),
        sa.Column('destination_warehouse_id', GUID(), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('unit_cost', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('total_cost', sa.Numeric(precision=15, scale=2), nullable=False),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        # Foreign keys
        sa.ForeignKeyConstraint(['transformation_id'], ['material_transformations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['destination_material_id'], ['materials.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['destination_warehouse_id'], ['warehouses.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index(op.f('ix_material_transformation_lines_transformation_id'), 'material_transformation_lines', ['transformation_id'])
    op.create_index(op.f('ix_material_transformation_lines_destination_material_id'), 'material_transformation_lines', ['destination_material_id'])


def downgrade() -> None:
    """Eliminar tablas de transformaciones y ajustes de inventario."""
    # Drop transformation lines first (FK dependency)
    op.drop_index(op.f('ix_material_transformation_lines_destination_material_id'), table_name='material_transformation_lines')
    op.drop_index(op.f('ix_material_transformation_lines_transformation_id'), table_name='material_transformation_lines')
    op.drop_table('material_transformation_lines')

    # Drop transformations
    op.drop_index(op.f('ix_material_transformations_status'), table_name='material_transformations')
    op.drop_index(op.f('ix_material_transformations_source_material_id'), table_name='material_transformations')
    op.drop_index(op.f('ix_material_transformations_date'), table_name='material_transformations')
    op.drop_index(op.f('ix_material_transformations_transformation_number'), table_name='material_transformations')
    op.drop_index('ix_material_transformations_org_status', table_name='material_transformations')
    op.drop_index('ix_material_transformations_org_source', table_name='material_transformations')
    op.drop_index('ix_material_transformations_org_date', table_name='material_transformations')
    op.drop_table('material_transformations')

    # Drop adjustments
    op.drop_index(op.f('ix_inventory_adjustments_status'), table_name='inventory_adjustments')
    op.drop_index(op.f('ix_inventory_adjustments_warehouse_id'), table_name='inventory_adjustments')
    op.drop_index(op.f('ix_inventory_adjustments_material_id'), table_name='inventory_adjustments')
    op.drop_index(op.f('ix_inventory_adjustments_adjustment_type'), table_name='inventory_adjustments')
    op.drop_index(op.f('ix_inventory_adjustments_date'), table_name='inventory_adjustments')
    op.drop_index(op.f('ix_inventory_adjustments_adjustment_number'), table_name='inventory_adjustments')
    op.drop_index('ix_inventory_adjustments_org_status', table_name='inventory_adjustments')
    op.drop_index('ix_inventory_adjustments_org_material', table_name='inventory_adjustments')
    op.drop_index('ix_inventory_adjustments_org_date', table_name='inventory_adjustments')
    op.drop_table('inventory_adjustments')

    # Nota: No se puede hacer DROP VALUE de un enum en PostgreSQL.
    # 'adjustment_reversal' queda en el enum pero sin efecto.
