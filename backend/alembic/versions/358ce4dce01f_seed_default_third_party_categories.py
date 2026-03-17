"""seed_default_third_party_categories

Crear 6 categorías default por organización existente y migrar terceros
existentes según sus flags legacy (ya eliminados del modelo, pero los
assignments se crean para los terceros que quedaron sin categoría).

Nota: las columnas de flags ya fueron eliminadas en 9ad2a3d1f90c.
No hay datos en producción — esta migración es preventiva para dev/test.

Revision ID: 358ce4dce01f
Revises: 9ad2a3d1f90c
Create Date: 2026-03-16 23:34:15.692134

"""
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '358ce4dce01f'
down_revision: Union[str, Sequence[str], None] = '9ad2a3d1f90c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Categorías default que se crean por organización
DEFAULT_CATEGORIES = [
    ("Proveedor Material", "material_supplier"),
    ("Proveedor Servicios", "service_provider"),
    ("Cliente", "customer"),
    ("Inversionista", "investor"),
    ("Genérico", "generic"),
    ("Provisión", "provision"),
]


def upgrade() -> None:
    """Seed 6 categorías default por cada org existente."""
    conn = op.get_bind()

    orgs = conn.execute(sa.text("SELECT id FROM organizations")).fetchall()

    for (org_id,) in orgs:
        for cat_name, behavior_type in DEFAULT_CATEGORIES:
            # Idempotente: solo crear si no existe
            exists = conn.execute(
                sa.text(
                    "SELECT 1 FROM third_party_categories "
                    "WHERE organization_id = :org_id "
                    "AND behavior_type = :bt "
                    "AND parent_id IS NULL "
                    "LIMIT 1"
                ),
                {"org_id": org_id, "bt": behavior_type},
            ).fetchone()

            if not exists:
                conn.execute(
                    sa.text(
                        "INSERT INTO third_party_categories "
                        "(id, name, behavior_type, is_active, organization_id, "
                        "created_at, updated_at) "
                        "VALUES (:id, :name, :bt, true, :org_id, now(), now())"
                    ),
                    {
                        "id": str(uuid4()),
                        "name": cat_name,
                        "bt": behavior_type,
                        "org_id": org_id,
                    },
                )


def downgrade() -> None:
    """Eliminar categorías default seeded y sus assignments."""
    conn = op.get_bind()

    # Primero eliminar assignments que apuntan a categorías default
    conn.execute(
        sa.text(
            "DELETE FROM third_party_category_assignments "
            "WHERE category_id IN ("
            "  SELECT id FROM third_party_categories "
            "  WHERE parent_id IS NULL "
            "  AND behavior_type IN ("
            "    'material_supplier', 'service_provider', 'customer', "
            "    'investor', 'generic', 'provision'"
            "  )"
            "  AND name IN ("
            "    'Proveedor Material', 'Proveedor Servicios', 'Cliente', "
            "    'Inversionista', 'Genérico', 'Provisión'"
            "  )"
            ")"
        )
    )

    # Luego eliminar las categorías default
    conn.execute(
        sa.text(
            "DELETE FROM third_party_categories "
            "WHERE parent_id IS NULL "
            "AND behavior_type IN ("
            "  'material_supplier', 'service_provider', 'customer', "
            "  'investor', 'generic', 'provision'"
            ") "
            "AND name IN ("
            "  'Proveedor Material', 'Proveedor Servicios', 'Cliente', "
            "  'Inversionista', 'Genérico', 'Provisión'"
            ")"
        )
    )
