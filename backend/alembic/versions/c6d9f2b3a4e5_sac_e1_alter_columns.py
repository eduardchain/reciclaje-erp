"""SAC E1 Migracion B: 7 ALTERs aditivos + 2 indices (plan-sac-e1-configuracion.md §3.2, D10)

Todas las columnas nullable, default NULL, cero backfill — los 3 clientes
existentes quedan en NULL y el codigo degrada gracilmente (regla §1.1 del
plan de ejecucion: solo ADD COLUMN nullable / indices nuevos).

- organizations.settings JSONB (flags + parametros por org, D3)
- money_movements +4 (warehouse_id, tariff_id, source_type, source_id) + 2 indices
  (source_type VARCHAR(40): unificado con kg_ledger_movements — el doc §11.2.1
  dice 32; desviacion menor declarada, H5 QA)
- money_accounts.warehouse_id (sede de cajas menores, §11.2.6a)
- sales.willard_remission_number + willard_target_account (§11.2.2)
- purchases.warehouse_id header (§12.2.3 — gap interno del doc, hallazgo 4 §0)
- fixed_assets.warehouse_id (§11.2.3)
- expense_categories.is_system_entity (§11.1.8 — el codigo lee bool(x), NULL = false)

FKs sin nombre explicito (None) -> PostgreSQL asigna el default, identico a
create_all — requisito del schema-diff H3. Espejo simultaneo en 7 modelos (D13).

Revision ID: c6d9f2b3a4e5
Revises: b5c8e1a2f3d4
Create Date: 2026-07-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'c6d9f2b3a4e5'
down_revision = 'b5c8e1a2f3d4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1. organizations.settings ---
    op.add_column(
        'organizations',
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                  comment='Flags y parametros por org (SAC E1, D3). NULL = flags apagados y '
                          'parametros en default. Escritura REPLACE del dict completo, solo superuser. '
                          'Sin MutableDict: toda escritura reasigna el dict completo'),
    )

    # --- 2. money_movements +4 columnas + 2 indices ---
    op.add_column(
        'money_movements',
        sa.Column('warehouse_id', sa.UUID(), nullable=True,
                  comment='Dimension gerencial persistida (sede) — ortogonal al 3-tier de UN (v0.5 §11.2.1)'),
    )
    op.add_column(
        'money_movements',
        sa.Column('tariff_id', sa.UUID(), nullable=True,
                  comment='Tarifa aplicada en causaciones automaticas (trazabilidad)'),
    )
    op.add_column(
        'money_movements',
        sa.Column('source_type', sa.String(length=40), nullable=True,
                  comment='Origen de causacion automatica: transfer | crucible_discharge | sale | willard_monthly_freight'),
    )
    op.add_column(
        'money_movements',
        sa.Column('source_id', sa.UUID(), nullable=True,
                  comment='FK polimorfico al documento origen (sin FK fisica)'),
    )
    op.create_foreign_key(None, 'money_movements', 'warehouses',
                          ['warehouse_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(None, 'money_movements', 'service_tariffs',
                          ['tariff_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_money_movements_org_warehouse', 'money_movements',
                    ['organization_id', 'warehouse_id'], unique=False)
    op.create_index('ix_money_movements_source', 'money_movements',
                    ['source_type', 'source_id'], unique=False)

    # --- 3. money_accounts.warehouse_id ---
    op.add_column(
        'money_accounts',
        sa.Column('warehouse_id', sa.UUID(), nullable=True,
                  comment='Sede de la caja (cajas menores por sede, v0.5 §11.2.6a): el gasto '
                          'hereda la sede de la CAJA usada. NULL = cuenta corporativa'),
    )
    op.create_foreign_key(None, 'money_accounts', 'warehouses',
                          ['warehouse_id'], ['id'], ondelete='SET NULL')

    # --- 4. sales: remision Willard ---
    op.add_column(
        'sales',
        sa.Column('willard_remission_number', sa.String(length=40), nullable=True,
                  comment='Remision Willard — decide que cuenta kg se descarga (v0.5 §11.2.2)'),
    )
    op.add_column(
        'sales',
        sa.Column('willard_target_account', sa.String(length=16), nullable=True,
                  comment='baterias | drosses — cuenta kg destino de la entrega Willard'),
    )

    # --- 5. purchases.warehouse_id (header) ---
    op.add_column(
        'purchases',
        sa.Column('warehouse_id', sa.UUID(), nullable=True,
                  comment='Sede de recepcion (header) — NULL para clientes existentes'),
    )
    op.create_foreign_key(None, 'purchases', 'warehouses',
                          ['warehouse_id'], ['id'], ondelete='SET NULL')

    # --- 6. fixed_assets.warehouse_id ---
    op.add_column(
        'fixed_assets',
        sa.Column('warehouse_id', sa.UUID(), nullable=True,
                  comment='Sede del activo (v0.5 §11.2.3) — NULL para clientes existentes'),
    )
    op.create_foreign_key(None, 'fixed_assets', 'warehouses',
                          ['warehouse_id'], ['id'], ondelete='SET NULL')

    # --- 7. expense_categories.is_system_entity ---
    op.add_column(
        'expense_categories',
        sa.Column('is_system_entity', sa.Boolean(), nullable=True,
                  comment='Seeds de sistema SAC (v0.5 §11.1.8) — protegidas de edicion/borrado. '
                          "Sin server_default (regla 'default NULL, cero backfill' del plan E1)"),
    )


def downgrade() -> None:
    op.drop_column('expense_categories', 'is_system_entity')

    op.drop_constraint('fixed_assets_warehouse_id_fkey', 'fixed_assets', type_='foreignkey')
    op.drop_column('fixed_assets', 'warehouse_id')

    op.drop_constraint('purchases_warehouse_id_fkey', 'purchases', type_='foreignkey')
    op.drop_column('purchases', 'warehouse_id')

    op.drop_column('sales', 'willard_target_account')
    op.drop_column('sales', 'willard_remission_number')

    op.drop_constraint('money_accounts_warehouse_id_fkey', 'money_accounts', type_='foreignkey')
    op.drop_column('money_accounts', 'warehouse_id')

    op.drop_index('ix_money_movements_source', table_name='money_movements')
    op.drop_index('ix_money_movements_org_warehouse', table_name='money_movements')
    op.drop_constraint('money_movements_tariff_id_fkey', 'money_movements', type_='foreignkey')
    op.drop_constraint('money_movements_warehouse_id_fkey', 'money_movements', type_='foreignkey')
    op.drop_column('money_movements', 'source_id')
    op.drop_column('money_movements', 'source_type')
    op.drop_column('money_movements', 'tariff_id')
    op.drop_column('money_movements', 'warehouse_id')

    op.drop_column('organizations', 'settings')
