"""SAC: orden del formato en papel «Materiales recolectados» en el perfil kg

Johana pidio que los materiales de la Entrada salgan en el orden del formato en
papel. El orden vive en `material_kg_profiles.form_order` (NULL = el material no
esta en el formato). Tabla exclusiva de SAC: las demas organizaciones no la usan.
Plan: docs/planes/plan-sac-orden-formato-materiales.md v1.1 (D1, F8).

Indice unico PARCIAL (org, form_order) WHERE form_order IS NOT NULL: dos
materiales no pueden compartir un renglon, y lo garantiza la base.

Revision ID: c5d7e9f1a3b6
Revises: b4c6d8e0f2a5
"""
from alembic import op
import sqlalchemy as sa

revision = "c5d7e9f1a3b6"
down_revision = "b4c6d8e0f2a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "material_kg_profiles",
        sa.Column(
            "form_order",
            sa.Integer(),
            nullable=True,
            comment="Renglon del formato en papel «Materiales recolectados» (NULL = no esta en el formato)",
        ),
    )
    op.create_index(
        "uq_material_kg_profiles_org_form_order",
        "material_kg_profiles",
        ["organization_id", "form_order"],
        unique=True,
        postgresql_where=sa.text("form_order IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_material_kg_profiles_org_form_order", table_name="material_kg_profiles")
    op.drop_column("material_kg_profiles", "form_order")
