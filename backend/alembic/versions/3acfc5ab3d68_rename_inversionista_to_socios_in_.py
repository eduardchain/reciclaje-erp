"""rename Inversionista to Socios in default third party categories

Revision ID: 3acfc5ab3d68
Revises: c5d8e2f47a91
Create Date: 2026-05-13 17:47:33.210781

Razon: profit_distribution.py filtra socios por `name ILIKE '%socio%'`. El seed
default creaba la categoria como "Inversionista" — orgs nuevas no podian repartir
utilidades sin renombrar la categoria manualmente. RDLC ya tenia "Socios" por
configuracion historica; MetaRecycling se quedo con el default y exhibio el bug.

Renombramos la categoria default a "Socios" para orgs que:
 - Tengan la categoria "Inversionista" con behavior_type=investor.
 - NO tengan ya una categoria "Socios" en la misma org (evitar duplicados).

Idempotente. Las orgs sin "Inversionista" o que ya tengan "Socios" no se tocan.
Los terceros asignados quedan automaticamente bajo "Socios" (es la misma fila).

"""
from typing import Sequence, Union

from alembic import op


revision: str = '3acfc5ab3d68'
down_revision: Union[str, Sequence[str], None] = 'c5d8e2f47a91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE third_party_categories tpc
        SET name = 'Socios'
        WHERE tpc.name = 'Inversionista'
          AND tpc.behavior_type = 'investor'
          AND NOT EXISTS (
              SELECT 1 FROM third_party_categories other
              WHERE other.organization_id = tpc.organization_id
                AND other.name = 'Socios'
                AND other.id <> tpc.id
          );
        """
    )


def downgrade() -> None:
    # Rollback: solo renombramos de vuelta si la org NO tiene ya otra "Inversionista".
    op.execute(
        """
        UPDATE third_party_categories tpc
        SET name = 'Inversionista'
        WHERE tpc.name = 'Socios'
          AND tpc.behavior_type = 'investor'
          AND NOT EXISTS (
              SELECT 1 FROM third_party_categories other
              WHERE other.organization_id = tpc.organization_id
                AND other.name = 'Inversionista'
                AND other.id <> tpc.id
          );
        """
    )
