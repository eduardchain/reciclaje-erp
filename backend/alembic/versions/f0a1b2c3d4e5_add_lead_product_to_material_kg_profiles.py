"""add lead_product to material_kg_profiles (guard de plomo entregable a Willard)

Marca explicita de "este material es plomo entregable". Reemplaza la heuristica
"sin formula el material ya es plomo", que servia para CALCULAR y se estaba usando
para CLASIFICAR: con ella, cajas plasticas y aluminio saldaban la deuda de plomo
de Willard 1:1 y facturaban maquila por una fundicion que no ocurrio.

Tabla SAC-exclusiva (flag kg_ledger_enabled), cero filas en las 3 orgs cliente.
`server_default='none'` es fail-closed deliberado: ninguna salida funciona hasta
que alguien marque los materiales. Va en la MIGRACION y no solo en el modelo — la
BD de test nace de los modelos y la de produccion de las migraciones, y esa
asimetria no la cubre ningun gate (bug (a) de #100).

Revision ID: f0a1b2c3d4e5
Revises: d3e4f5a6b7c8
"""
from alembic import op
import sqlalchemy as sa

revision = "f0a1b2c3d4e5"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "material_kg_profiles",
        sa.Column(
            "lead_product",
            sa.String(length=16),
            nullable=False,
            server_default="none",
            comment="none | crudo | puro — plomo entregable a Willard (crudo: las 3 modalidades; puro: solo venta)",
        ),
    )
    op.create_check_constraint(
        "ck_material_kg_profiles_lead_product",
        "material_kg_profiles",
        "lead_product IN ('none', 'crudo', 'puro')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_material_kg_profiles_lead_product",
        "material_kg_profiles",
        type_="check",
    )
    op.drop_column("material_kg_profiles", "lead_product")
