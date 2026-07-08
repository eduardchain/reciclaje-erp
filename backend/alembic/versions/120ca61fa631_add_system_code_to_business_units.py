"""add system_code to business_units + seed UN Pasa Mano

Revision ID: 120ca61fa631
Revises: 9cff249f95cf
Create Date: 2026-07-07

Razon (plan-rentabilidad-un-pasamano.md, requerimiento A reunion 2026-07-06):
el cliente necesita asignar gastos directos al Pasa Mano (doble partida) para
calcular su utilidad neta. Se introduce una UN de sistema con
system_code='double_entry' — sin materiales, excluida del prorrateo y de la
tabla bodega del reporte de rentabilidad.

Backfill por organizacion (idempotente):
 1. Si la org ya tiene una UN con system_code='double_entry' -> no hacer nada.
 2. Si tiene una UN llamada exactamente 'Pasa Mano' SIN materiales -> adoptarla
    (set system_code) para no duplicar.
 3. Si la UN 'Pasa Mano' existente tiene materiales -> crear una nueva
    'Pasa Mano (DP)' (no se puede adoptar: los materiales inflarian el prorrateo).
 4. Si no existe -> crear 'Pasa Mano'.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '120ca61fa631'
down_revision: Union[str, Sequence[str], None] = '9cff249f95cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SYSTEM_CODE = 'double_entry'


def upgrade() -> None:
    op.add_column(
        'business_units',
        sa.Column('system_code', sa.String(length=50), nullable=True),
    )
    op.create_index(
        'ix_business_units_system_code', 'business_units', ['system_code']
    )

    # Paso 2: adoptar UN 'Pasa Mano' existente sin materiales
    op.execute(
        f"""
        UPDATE business_units bu
        SET system_code = '{SYSTEM_CODE}'
        WHERE bu.name = 'Pasa Mano'
          AND bu.system_code IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM materials m WHERE m.business_unit_id = bu.id
          )
          AND NOT EXISTS (
              SELECT 1 FROM business_units other
              WHERE other.organization_id = bu.organization_id
                AND other.system_code = '{SYSTEM_CODE}'
          );
        """
    )

    # Pasos 3 y 4: crear la UN para orgs que aun no la tienen.
    # Nombre 'Pasa Mano (DP)' si ya existe una 'Pasa Mano' (con materiales,
    # no adoptable); 'Pasa Mano' en caso contrario.
    op.execute(
        f"""
        INSERT INTO business_units (id, organization_id, name, description, is_active, system_code, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            o.id,
            CASE WHEN EXISTS (
                SELECT 1 FROM business_units bu2
                WHERE bu2.organization_id = o.id AND bu2.name = 'Pasa Mano'
            ) THEN 'Pasa Mano (DP)' ELSE 'Pasa Mano' END,
            'Unidad de sistema para gastos directos de doble partida',
            TRUE,
            '{SYSTEM_CODE}',
            NOW(),
            NOW()
        FROM organizations o
        WHERE NOT EXISTS (
            SELECT 1 FROM business_units bu
            WHERE bu.organization_id = o.id
              AND bu.system_code = '{SYSTEM_CODE}'
        );
        """
    )


def downgrade() -> None:
    # Eliminar solo las UNs de sistema SIN gastos asociados; las que tengan
    # movimientos se conservan (quedan como UN normal al quitar la columna).
    op.execute(
        f"""
        DELETE FROM business_units bu
        WHERE bu.system_code = '{SYSTEM_CODE}'
          AND NOT EXISTS (
              SELECT 1 FROM money_movements mm WHERE mm.business_unit_id = bu.id
          )
          AND NOT EXISTS (
              SELECT 1 FROM fixed_assets fa WHERE fa.business_unit_id = bu.id
          )
          AND NOT EXISTS (
              SELECT 1 FROM scheduled_expenses se WHERE se.business_unit_id = bu.id
          )
          AND NOT EXISTS (
              SELECT 1 FROM expense_categories ec WHERE ec.default_business_unit_id = bu.id
          );
        """
    )
    op.drop_index('ix_business_units_system_code', table_name='business_units')
    op.drop_column('business_units', 'system_code')
